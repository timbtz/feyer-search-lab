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
