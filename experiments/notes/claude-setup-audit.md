# Claude guidance: setup and matrix-assembly audit

- Branch: `explore/claude-setup-audit`. Scientific parent: seed8 `1e552d675c3795265be8af1ac23ffb61f90f30b1`.
- Scope: source inspection only. No benchmarks, shell, Git/GitHub/SSH, simulator edits or evaluator submissions. No candidate has been produced and no timing claim is made.
- Measured context reused from `experiments/notes/initial-agent.md`: N=751 signal unknowns, C=286 carrier unknowns, 101 frequencies, one carrier sample, D=1 noise detector. Candidate 5 full run: build 0.745 s, forward execute 12.37 s, reverse 1.84 s, peak RSS 13.79 GB. Candidate 6 showed build moving from 0.75 to 1.28 s with no builder change, so differences in build time below about 0.5 s cannot be told apart from run-to-run noise.

## Proposed operator: build the noise matrix once per evaluation instead of once per frequency

### Source evidence

- `differometor/simulate.py:316` expands `parameters` to one row per signal frequency (101 rows). The noise update at `simulate.py:392-399` then runs `vmap(update)` over **all 101 rows**. That runs the scalar `lax.map`/`switch` over every noise component 101 times and scatters into 101 dense copies of the `(751, 751)` base matrix.
- `simulate.py:420` then multiplies those copies against `noise_weights` (`einsum("bij,bj->bi")`). By shape arithmetic, a `(101, 751, 751)` complex128 tensor is 101·751²·16 = 911,393,616 bytes. Reverse-mode AD produces a cotangent of the same shape. This is calculated, not measured. Whether XLA actually materializes either tensor has not been inspected in HLO.
- All noise instructions are created in `differometor/build.py` with inputs that do not depend on frequency:
  - `vacuum_quantum_noise` (`build.py:788-797`, `build.py:1389-1398`) takes only `[[0]]`, the carrier frequency F. The function ignores its input (`components.py:734`).
  - `loss_quantum_noise` (`build.py:1017-1026`) takes only the surface's `loss_position`.
  - `squeezer` (`build.py:813-825`) takes only `db` and `angle`.
  - No noise instruction reads `signal_frequency_position`. `set_instructions` pads inputs to length 7 with index 0 (`build.py:157-162`), and index 0 is F, which cannot be swept by name because `parameter_names[0] == ""`.
- Linking (`simulate.py:290-294`) runs before expansion. After that, `expand_parameters` only overwrites `carrier_changing_parameter_indices` and `signal_changing_parameter_indices`. So the 101 noise matrices are bitwise identical whenever the noise input indices don't overlap the real changing indices. In the benchmark, the only changing pair is `("f", "frequency")` (`benchmark.py:204`).
- In the benchmark, `db` and `angle` are optimized properties (`benchmark.py:47`), so the noise matrix sits on the gradient path. It cannot be treated as a constant.

### Transformation

1. **Host side, once per complete evaluation (`run_build_step`/`pairs_to_arrays`).** Collect the *real* changing indices: carrier ∪ signal, taken from `pairs_to_arrays` **before** `prepare_arrays` fills in the dummy `[0]` placeholders. Collect every noise function input index, including padding. If the two sets are disjoint, emit a new int array `noise_parameter_rows = [0]` with shape `(1,)`. Otherwise emit `arange(R)` with shape `(R,)`.
   - Inside `jit`, `simulate`'s arguments are traced (`benchmark.py:165, 211`). The decision therefore has to be carried by the array's static **shape**, not its values.
   - This is structural preparation only. It contains no physical values.
2. **Inside `simulate`:**
   - Set `noise_parameters = parameters[noise_parameter_rows]` and run the unchanged `vmap(update, ...)` over it.
   - If the leading dimension is 1, which is a trace-time static check, contract with `einsum("ij,dbj->dbi", noise_matrix[0], noise_weights)`. Otherwise keep the current `vmap(matmul_single_batch)` path.
   - The dense base `noise_matrix`, the scatter `.set` semantics, the component functions and all solves stay unchanged. No entry is assumed structurally zero.
3. **API.** Append `noise_parameter_rows=None` as the **last** parameter of `simulate` and append the array last in `run_build_step`'s `all_arrays`. This keeps the existing argument-count check (`simulate.py:483-491`) valid.
   - `None`, which is a static Python value, keeps the current per-row path. Manual callers such as `start_here.py` and the examples then keep working.
   - Callers that go through `run_build_step`, including the benchmark, get the new array automatically.

### Expected trade-offs (none measured)

- **Forward:** noise component evaluations drop from 101·K to K, where K is the number of noise components (not counted here). The 101 dense scatters become one, and 101 batched matrix-vector products become one complex GEMM of shape `(751×751)·(751×101)`.
- **Reverse:** the cotangent of `noise_matrix` shrinks from `(101,751,751)` to `(751,751)`, because the einsum's transpose sums over frequency. Residuals saved for the noise `lax.map` also shrink by about 101×.
- **Memory:** the largest benefit is a possible removal of about 0.9 GB of noise-matrix buffers, plus their cotangent, from the 13.8 GB peak. Whether those buffers exist after XLA fusion is **unverified**.
- **Compile:** shapes change, but no new branches are added, so compile time should change little. This is an expectation, not a measurement.
- **Ceiling:** forward time is dominated by the 101 dense 751×751 LU solves. The noise path is a small share of the flops, so any time gain probably comes from memory traffic and could be well under 1 s. It is worth a single screen if the coordinator wants a memory-focused operator. It should not take priority over larger solve-side ideas.

### Compatibility and numerical risks

- **Summation order:** the `db`/`angle` gradient changes order. Previously each frequency's cotangent was gathered at the scatter indices and the scan/vmap transpose summed over frequency. Now the einsum transpose sums over frequency first. The forward GEMM may also accumulate differently from batched GEMV.
  - The strict comparator (rtol=1e-7 + 1e-12·scale) already rejected candidate 2 over gradient differences.
  - Treat bitwise equality as **not** guaranteed and check the squeezer coordinates specifically.
- **The overlap test must use the real changing indices, not the dummy ones.** Using the dummy-filled arrays would always see index 0 in both sets and wrongly fall back. Missing a real overlap, for example a sweep over squeezer `db`, which is a signal component, would give **wrong physics**. So the test must be conservative: any shared index means fallback.
- **Possible conflict with Codex's scatter work:** the noise scatter itself is unchanged. If Codex's assembly-scatter work touches the noise `update`, the coordinator should sequence the two.
- **What stays the same:** all 101 frequencies, 193 variables, float64/complex128, all three outputs, the full gradient and the benchmark's three JIT stages are preserved. Nothing is cached across evaluations, because the row selector is rebuilt in every `run_build_step` call.

### Validation a later candidate needs

1. Unchanged official full benchmark: sensitivity reference check and finite-difference gradient spot check.
2. Strict saved-array comparison against seed8 for carrier, signal, noise, sensitivity, powers and the full 193-element gradient. Also compare the reported loss. Look specifically at the maximum pointwise absolute and relative error on the `db`/`angle` gradient coordinates, not only the relative L2 error.
3. Before claiming the memory mechanism, check the lowered forward HLO: the `c128[101,751,751]` noise buffer should be gone. Then compare peak RSS and forward/reverse execution against seed8 with repeated fresh-process full runs.
4. Run the fallback correctness check outside the benchmark, through an approved route: (a) a sweep over a squeezer `db`, which must take the `(R,)` path and match the old code exactly; (b) a carrier-side sweep with R>1. Neither changes the official benchmark.

## Considered and not proposed

- **Build-time eager JAX calls:** `build.py:1288` calls the JAX `space` function eagerly for each edge just to fill initial matrix values. A NumPy equivalent, like the existing `laser_np`, would avoid per-edge dispatch. But the whole build phase is about 0.75 s and its run-to-run variation is about 0.5 s, so the ceiling is too small to resolve. Not prioritized.
- **Signal entries that don't depend on frequency:** `signal_function` and `force_calculation_*` are also evaluated per frequency. Splitting the signal update into frequency-dependent and frequency-independent parts overlaps Codex's component-grouping and scatter work. Left to them.
- **Sparse noise application** (`z = Σ v·w[col]` at instruction indices): this would require treating the zero base as structurally zero and would change scatter semantics. It is excluded under the brief's constraints. Most of its memory benefit is already captured by the operator above.

## Decision

The proposal above is the one new future-round operator for coordinator review. It has not been registered or launched, and no AMD job was submitted.

---

## Follow-up (turn 2): feasibility challenge and corrections

Same session, same one-hour budget (absolute deadline 1795286839.545374). This turn used source and mathematical reasoning only. Nothing was executed, and the simulator is unchanged. The findings above are kept as written; corrections are listed in F7.

### F1. Dependency trace: when are the per-row noise inputs identical?

Data flow inside `simulate`, in order:

1. `parameters` has shape `(1, P)` and complex dtype (`build.py:1424`). Optimized values are inserted at `simulate.py:285-287`.
2. Linking runs at `simulate.py:290-294`, on that single row. Linked outputs are computed once from the pre-expansion values. If a linked parameter feeds a noise function, it is identical in every expanded row, unless its index is itself a changing index, which the overlap check catches.
3. Carrier expansion happens at `simulate.py:302` (`expand_parameters`, `simulate.py:158-162`). The row is tiled and only the `carrier_changing_parameter_indices` columns are overwritten.
4. Signal expansion happens at `simulate.py:316`. The rows are tiled again and only the `signal_changing_parameter_indices` columns are overwritten.
   - `prepare_arrays` raises if both kinds of changing index are real (`build.py:1745-1746`), so at most one expansion has R>1.
   - Benchmark: carrier dummy `R_c=1`; signal `R_s=101` (`("f","frequency")`, `benchmark.py:204`). The changing index is `signal_frequency_position`, because node `f` is a `frequency` component and is therefore registered as a signal component (`build.py:642-646`).
5. The noise update vmaps over the 101 expanded rows (`simulate.py:392-399`). Each row is gathered at `noise_function_input_indices`.

**Consequence.** Two expanded rows can differ only in the real changing columns. In addition, dummy fills write `parameters[0][0]` back onto column 0 (`build.py:1750-1751, 1766-1767`), so dummy columns are value-identical across rows. Therefore:

> **Predicate S (sufficient for bitwise-identical noise inputs on every row):** `set(int(i) for i in noise_function_input_indices.ravel())` ∩ (`real_carrier_changing` ∪ `real_signal_changing`) = ∅.

Here `real_*` are `arrays_to_prepare[2]` and `arrays_to_prepare[3]` returned by `pairs_to_arrays` (`build.py:1676-1679`), taken **before** `prepare_arrays` inserts dummy `[0]`s.

Details the check must handle:

- **Padding.** `set_instructions` pads with a float `np.zeros` (`build.py:159-162`), so the vertically stacked index array is float until `jnp.array(..., dtype=int)` (`build.py:1668`). Cast to int before taking the set. Padding entries refer to index 0. Index 0 can never be a real changing index, because `parameter_names[0] == ""` and every changing-pair name contains `_` (`build.py:1610, 1612`). So padding cannot cause a false overlap, and including it in the set is harmless and conservative.
- **Empty noise instructions.** The dummy is `[[0,0,0]]` with `dummy_function` (`build.py:1636-1641`). Predicate S holds trivially, and reusing one row is correct.
- **Rejected alternative.** Applying the check to the dummy-filled arrays would always see index 0 on both sides. It would therefore always fall back: safe, but the operator would never fire.

Predicate S is sufficient, not necessary. It is conservative: it ignores whether a component function actually *uses* the indexed input. For example, `vacuum_quantum_noise` ignores its input entirely (`components.py:754`). That conservatism is deliberate.

### F2. Counterexamples and expected path for each case

| Case | Real changing indices | Overlaps noise inputs? | Path |
| --- | --- | --- | --- |
| Benchmark: `("f","frequency")` | {signal_frequency_position} | No. Noise inputs are F (index 0), surface loss, squeezer db/angle (`build.py:788-825, 1017-1026, 1389-1398`) | **Reuse** |
| Sweep of squeezer `db` or `angle` (squeezer is a signal component, `build.py:613-614`) | that db/angle index | **Yes** | Fallback (reuse would be **wrong physics**) |
| Sweep of mirror/beamsplitter `loss` (carrier component) | loss index, `R_c>1` | **Yes**, `loss_position` (`build.py:1020`) | Fallback |
| Sweep of laser `power` (carrier) | power index | No | Reuse is valid. Rows = `R_c`; carrier batch >1 |
| Sweep of a linked parameter's *source* | source index | Only if the source index is itself a noise input | The linked target is evaluated before expansion (existing semantics) and is not swept |
| No sweep at all | ∅ | No | Reuse; R=1, so both paths coincide |

No counterexample was found in which Predicate S holds but the per-row noise matrices differ. Any future noise component that reads `signal_frequency_position`, for example a frequency-dependent loss, is caught automatically, because the frequency index is the real changing index in the benchmark.

### F3. Concrete guarded design (revised)

To avoid computing R on the host, encode the decision as a **shape sentinel** rather than `arange(R)`:

- `run_build_step` (`simulate.py:477-493`) computes Predicate S from `arrays_to_prepare` and `noise_arrays[0]`. It then appends `noise_parameter_rows = jnp.array([0], int)` (shape `(1,)`, reuse) or `jnp.zeros((0,), int)` (shape `(0,)`, fallback) as the **last** element of `all_arrays`.
- `simulate` gets a new trailing parameter `noise_parameter_rows=None`. Shapes are static under `jit`, so the branch below is decided at trace time and only one path is ever traced. No `lax.cond` and no second compiled branch:
  - `None`, or shape `(0,)`: the current code, unchanged (`vmap` over all rows, `einsum("bij,bj->bi")`).
  - Shape `(1,)`: `noise_matrix_1 = update(parameters[0], noise_matrix, ...)`, i.e. one unbatched `update` call with the same component switch and the same `.at[].set`. Then `noise_sources = jnp.einsum("ij,dbj->dbi", noise_matrix_1, noise_weights)`. The covariance solve, contraction and ASD formula are unchanged.
- Gathering from `parameters[0]` (expanded row 0) is equivalent to gathering from the pre-expansion row on all noise inputs, by Predicate S.

**Fallback behaviour:** whenever Predicate S fails, or the caller supplies no selector, the existing code runs unchanged, so its outputs and gradients are bitwise the current ones.

**Rejected variant: `jnp.broadcast_to(N, (R,N,N))` in the old einsum.** The broadcast value would be the einsum operand, so JAX would save it as a residual (see F5) and the memory benefit would be lost.

**Lower-risk variant A.** Evaluate the noise component outputs once, then broadcast those K outputs into the existing per-row scatter and einsum. The forward result is bitwise unchanged. It removes only the 100/101 duplicated component evaluations, not the dense buffers, so its upside is small. It is listed as a fallback design if variant B fails strict comparison.

### F4. Gradient analysis (corrects the first turn)

- **Mathematical equivalence.** Write N_r(θ) = N(θ) for all r, with θ including the optimized `db`/`angle`. Then dL/dθ through N is Σ_r ⟨∂L/∂N_r, dN/dθ⟩ = ⟨Σ_r ∂L/∂N_r, dN/dθ⟩. The old path applies the component VJP per row and sums the parameter cotangents through the `vmap`/`tile`/scatter transposes (`simulate.py:158-162`). The new path sums the cotangent over b inside the einsum transpose (a `(751×R)·(R×751)` contraction) and then applies one component VJP. The two are exactly equal in real arithmetic but round differently.
- **Correction.** In turn 1 I said the differences would be confined to the db/angle coordinates. That is wrong. The noise sources also feed the covariance solve (`simulate.py:421`), and `noise_weights` depends on the signal matrix, so every design variable has a gradient path through `noise_sources`. The cotangent with respect to `noise_weights` is `Nᵀ·ct` (`ij` GEMM versus batched GEMV `bij`), which has a different accumulation order. The forward `noise` output can also differ at ULP level. **Any of the 193 coordinates, and the `noise`/`sensitivity`/loss outputs, may deviate.** Exact bitwise equality is not expected for variant B.
- **Risk level.** The loss is near zero (9.79e-8), and candidate 2 failed strict comparison with a max |Δgradient| of 2.8e-3. Variant B's changes are pure reassociation, which is much smaller in kind than candidate 2's algebraic rewrite, but a strict failure is plausible. No custom derivative is involved; JAX's standard rules apply. If strict comparison fails, do not loosen tolerances. Reject variant B, or test variant A, whose forward output is bitwise unchanged and whose only reordering is the db/angle VJP sum.

### F5. Buffer estimates vs. compiled materialization

Each item below is labelled by the kind of evidence behind it:

- **Shape-derived (certain as array shapes; says nothing about memory):** the per-row noise matrix and its cotangent are both `c128[101,751,751]` = 911,393,616 bytes. In the reuse path they become `c128[751,751]` = 9,024,016 bytes.
- **Source-implied materialization (moderately strong, not compiled evidence):**
  - The benchmark returns the pullback from the forward JIT stage (`benchmark.py:112-115, 211-212`), so every residual is an **output buffer** of the compiled forward function. Fusion cannot remove a residual.
  - The einsum at `simulate.py:420` is bilinear, and its `noise_weights` operand has a nonzero tangent, because it depends on the signal matrix and hence on the parameters. Standard linearization therefore keeps the primal `N` operand as a residual.
  - **Inference:** the `(101,751,751)` noise matrix is very probably stored as a forward residual today. This must be confirmed by listing the pullback's leaf shapes.
- **Unknown:** whether the reverse cotangent `bi,bj->bij` is ever materialized at full size, or whether XLA fuses the outer product into the scatter-transpose gather. The forward scatter output is probably materialized, being the residual just mentioned, but the old code may also keep a separate base broadcast copy; that has not been inspected.
- Candidate 2 cut peak RSS by about 1.78 GB by removing one solve path. This shows that buffers of this order of magnitude matter here, but **it is not evidence for this operator**.

**Savings claim:** none. Plausible upside is up to about 0.9 GB of forward residual, plus possibly reverse temporaries, and a GEMM instead of a memory-bound batched GEMV. The time effect is unknown and probably small relative to the 12.3 s forward stage, which is dominated by the LU solves.

### F6. Compatibility with callers and the three JIT stages

- **Argument-count check.** `run_build_step` maps `all_arrays` positionally onto `simulate.__code__.co_varnames` (`simulate.py:483-493`). `co_argcount` includes defaulted parameters, so the new parameter must be last and its array appended last. If either is missing, the existing `ValueError` fires, which is a safe failure.
- **Callers found.** All pass the `run_build_step` dictionary by keyword, so they pick up the new key automatically:
  - `benchmark.py:115, 253`;
  - `start_here.py:37-50`;
  - `examples/voyager_optimization.py:62-82`;
  - `examples/uifo_optimization.py:138-154`.
  - `run_simulation_step` (`simulate.py:540-547`) uses the same dictionary.
  - No caller passes positional arguments or uses `vmap(simulate, in_axes=...)`. The `run_with_parameter_sets` named in the module docstring does not exist in source.
- **Other callers.** Third-party code that builds the keyword dictionary by hand keeps working through the `None` default, on the unchanged path.
- **The three JIT stages.** The benchmark dictionary is a traced pytree argument of the forward stage (`benchmark.py:165, 211`). A new `int64[1]` leaf only adds a parameter, and its shape fixes the trace-time branch. The sensitivity stage is untouched. The gradient stage's input pullback gets different residual shapes, but there are still three stages and nothing is cached. No persistent cache and no environment flags are involved.
- **Overlap with other agents.** The change sits in noise contraction and row selection. The noise `update` call and its scatter are reused as they are. Component assembly internals (`update`, `_evaluate_component`) are not modified. If the other agent's component-assembly implementation changes the signature or semantics of `update`, rebase onto it rather than merging changes inside it.

### F7. Corrections to the turn-1 text

1. Gradient risk applies to **all** coordinates and to the noise, sensitivity and loss outputs, not only db/angle (F4).
2. `arange(R)` is replaced by a shape `(0,)` sentinel, so the host never needs R (F3).
3. "Whether those buffers exist after XLA fusion is unverified" is refined: the forward residual is source-implied to exist because of the split VJP; the reverse temporaries remain unknown (F5).
4. "Compile: no new branches" stands. The branch is decided by static shape and only one path is traced.
5. The validation step "squeezer-db sweep must match old code exactly" holds because that case takes the unchanged fallback path. The reuse path needs tolerance-based comparison (F8).

### F8. Minimal validation matrix for a later approved implementation

| # | Check | Path | Pass criterion |
| --- | --- | --- | --- |
| V1 | Unchanged official full benchmark (screen, then full) | reuse | Official sensitivity and FD gradient checks pass; all outputs and gradients finite |
| V2 | Strict saved-array comparison against seed8 `1e552d6` | reuse | carrier and signal bitwise (assembly unchanged); noise, sensitivity, powers and all 193 gradient coordinates within rtol=1e-7 + 1e-12·scale; report max pointwise abs/rel error, with db/angle coordinates and the loss called out separately |
| V3 | Path assertion | reuse | Benchmark build emits a selector of shape `(1,)` |
| V4 | Residual and HLO evidence | reuse vs seed8 | Pullback leaf shapes no longer contain `c128[101,751,751]`; lowered forward HLO shows `c128[751,751]` for the noise scatter; compare `compiled.memory_analysis()` if available |
| V5 | RSS and timing | reuse vs seed8 | At least 3 fresh-process full runs each; compare peak RSS, forward/reverse execute, compile and complete first-run time. Claim gains only from these |
| V6 | Fallback: squeezer `db` sweep (signal side) | fallback | Selector shape `(0,)`; outputs and gradient **bitwise** equal to the pre-change code |
| V7 | Fallback: mirror `loss` sweep (carrier side, `R_c>1`) | fallback | Selector shape `(0,)`; bitwise equal |
| V8 | Reuse with a carrier sweep: laser `power`, `R_c>1` | reuse | Selector shape `(1,)`; within strict tolerance of the old code, including gradients |
| V9 | No-selector caller (`None`) | old | Bitwise equal to the current code |

V6–V9 are synthetic checks outside the benchmark. They are deferred to an approved numerical experiment and must not alter the official benchmark. If V2 fails, reject variant B as it stands and consider variant A (F3) as a separate candidate. Do not loosen tolerances.

### Turn-2 decision

The proposal stands, revised: the source contradicts no core assumption, and reuse on the benchmark is justified by Predicate S. Its expected upside is mainly memory. Strict-gradient risk is real and applies to all coordinates. Priority: medium-low. Recommend one screen, then a full run if the coordinator schedules it. Not registered, not launched, nothing measured.
