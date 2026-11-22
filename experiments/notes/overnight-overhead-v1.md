# Overnight campaign: import, setup and small-compilation overhead (overnight-overhead-v1)

- Branch `explore/overnight-overhead-v1`; seed / parent `53f38d342c3228c052785e8c9d63b6ce9c832dd1`.
- Campaign deadline 2026-11-22 09:27:44 UTC (supervisor epoch 1795339664). Supervisor commits, pushes and
  evaluates; this agent makes no commits, remote calls or benchmarks. The successor has a local shell
  and Python standard library, but no JAX, NumPy or Plotly in that Python. No dependencies installed.
  Official timing and runtime validation remain with the evaluator.
- Seed reference (supplied audit, not recalibrated in the current evaluator): large median 0.986991538 s,
  aLIGO median 0.626026371 s. Single-run seed phases: grid imports 0.30075, build 0.07331, trace/lower +
  compile ~0.2493 s; aLIGO imports 0.27080, build 0.03848, compile ~0.2502 s.

## Candidate 1: defer imports unused by the simulation path

- Parent `53f38d3`. Candidate SHA: `c7c3e7a5aa257400d3036ccebb29b76293b60887`.
- Import graph (static inspection): benchmark times `import jax`, `jax.numpy`, `numpy`, `differometor`,
  `differometor.setups`. Beyond JAX/NumPy, differometor's package import pulled in:
  - `differometor.plot` → `plotly.graph_objects` (plotly 7.1.0, which also loads narwhals), only for
    `visualize_setup`; no simulator module uses it.
  - `jax.scipy.linalg` at top of `simulate.py`, used only by the dense `_solve_signal_and_noise` path
    (`lu_solve`). The default path (sparse structure + `HOST_PASS`) never calls it.
  - SciPy is already lazy (`sparse._scipy`, `host_pass._superlu_gstrf` loads only `_superlu`).
  - No module-level jnp computations in components/build/setups (no eager XLA work at import).
- Change: `__init__.py` exposes `visualize_setup` via PEP 562 `__getattr__` (loaded and cached on first
  access; `__all__`/`__dir__` still list it; `from differometor import visualize_setup`,
  `df.visualize_setup` and `from differometor.plot import visualize_setup` keep working, returning the
  original function). `simulate.py` imports `jax.scipy.linalg as jax_scipy_linalg` inside the dense branch
  (aliased so `jax` is not rebound as a local name). No numerical code changes; outputs/gradients must be
  bitwise identical.
- Hypothesis: lower `imports` phase and complete first-run time for both benchmarks by the cost of Plotly
  (+narwhals) and jax.scipy.linalg module loading. Size unknown: the 2025 initial agent saw no gain from
  the plotly part on a 36 s workload where ±25 ms import noise was invisible; plotly may already lazy-load
  graph_objs, and jax.numpy may already import parts of jax.scipy. A null result is plausible and would
  show imports are dominated by JAX/jaxlib itself (not in our control without launch tricks).
- Validation needed: official large + aLIGO pass, strict comparison identical to seed (no numerical
  change), repeated fresh-process imports-phase comparison vs parent.
- Next ideas (in lane): (a) profile `trace/lower` of the three stages — callback signature size (host_pass
  passes base value vectors and 5 outputs incl. covariances/weights as residuals); (b) build phase
  (~73 ms large): Python builder loops and `run_build_step` set comprehensions; (c) sensitivity readout
  stage compile (~0.08 s) for a tiny program.

### Candidate 1 feedback, inspected by the Codex successor

- Request `9e437ccea88849d5907eb314bba685a5`; both unchanged official benchmarks passed
  all three fresh processes. Artifacts: `grid-1`, `grid-2`, `grid-3`, `aligo-1`, `aligo-2`,
  `aligo-3` under that request. Checked-in feedback:
  `experiments/runs/overnight-20261122/overnight-overhead-v1/9e437ccea88849d5907eb314bba685a5.json`.
- Large totals: 1.007968012, 1.014233978, 0.969120832 s; median 1.007968012 s,
  range 0.969120832–1.014233978 s.
- aLIGO totals: 0.626467375, 0.679160602, 0.659511628 s; median 0.659511628 s,
  range 0.626467375–0.679160602 s. These are separate setup measurements, no combined score.
- Phase medians in milliseconds (individual medians do not sum to the median total):

  | Phase | Large | aLIGO |
  | --- | ---: | ---: |
  | Imports | 265.992 | 264.010 |
  | Build | 73.355 | 38.522 |
  | Forward lower | 36.926 | 37.333 |
  | Forward compile | 77.367 | 88.757 |
  | Sensitivity lower | 25.848 | 31.253 |
  | Sensitivity compile | 39.739 | 48.867 |
  | Gradient lower | 16.869 | 17.727 |
  | Gradient compile | 53.522 | 55.412 |
  | Forward execute | 187.969 | 45.321 |
  | Gradient execute | 192.709 | 28.846 |

- Compared with supplied *single-run* seed observations, import medians are 34.758 ms lower
  (large) and 6.790 ms lower (aLIGO); these are unmatched phase differences, not measured causal gains.
  Total medians exceed the historical audit medians. No matching current parent cohort was supplied.
- Sampled peak RSS: large 495906816, 496816128, 558010368 bytes; aLIGO 307466240,
  307871744, 305655808 bytes. Benchmark job walls: large 3.818/3.828/3.822 s;
  aLIGO 1.641/1.644/1.638 s. Whole evaluation elapsed ~26.376 s including extra checks.
  Warm timings are not supplied here. External contention was not excluded.
- Official saved arrays match the initial seed exactly (including gradients); all 14 additional
  generalization cases have zero differences against the seed. This does not resolve pristine-reference
  failures: large signal 131 entries, gradients 3 entries, loss; official aLIGO loss; additional
  uifo_rand1/uifo_rand3 sensitivity log errors ~2.0361e-4/5.8101e-5, and other reported signal/gradient
  mismatches remain. The six unresolved grid finite-difference coordinates remain unresolved.
- `confirmed_improvement=false`, `strict_passed=false`, `numerical_review_required=true`.
  Independent source review has `approved=false`, model/session null; no substantive review explanation
  was supplied. Promotion decision says `requires_source_review`. Do not treat the receipt's separate
  `promotion_ready=true` field as approval. Coordinator must obtain the independent review.
- Decision: no timing promotion; one evaluated submission without a confirmed gain. Retain the import
  changes only as the immediate experimental parent, and move to a distinct small-compilation mechanism.
  The strongest prior verified parent remains seed `53f38d3`, with its stated numerical limitations.

## Candidate 2: explicit static base-matrix gathers

- Campaign/session: `overnight-20261122` / `overnight-overhead-v1`; deadline unchanged.
  Worktree HEAD `0eb5ae8` is feedback bookkeeping on simulator candidate `c7c3e7a`; new candidate SHA
  pending supervisor commit. No other lane's code incorporated.
- Focused source change: `SparseSystem` packs its already-derived row/column coordinates into one
  NumPy index operand during construction. `base_values` uses one explicit `jax.lax.gather` instead
  of general two-axis advanced indexing. The three host-pass base-matrix gathers use this method.
  No factorization, refinement, component evaluation, adjoint mathematics or callback results changed.
- Hypothesis: general advanced indexing traces index normalization, broadcasting and packing around
  the actual gather. Supplying its known coordinates directly should reduce forward lower/compile
  work, possibly reverse compile work, while adding a small host stack to build. Primitive-count
  reduction and timing effect are **unmeasured**, pending fixed-environment synthetic inspection and
  both official evaluations. Sensitivity compilation should be unchanged. No promised size of gain.
- Correctness argument: coefficient coordinates come from `nonzero(mask.T)`, RHS coordinates from
  `nonzero(mask[:, size])`. They are unique, nonnegative, in bounds and disjoint; stored order is
  unchanged. Thus `unique_indices=True` and `promise_in_bounds` are justified for the built matrix.
  Structural zero entries included by writes/extra entries remain present. Matrix values remain traced
  inputs, with ordinary JAX gather JVP/VJP; no values are frozen or precomputed. Coordinate metadata
  is a deterministic function of existing hashed rows/columns, so no new independent cache key is needed.
  As before, rebuild structural metadata when matrix layout changes. No cross-evaluation answer cache.
- Local validation: Python AST parsing passed for the implementation and the focused synthetic check.
  Runtime checks could not execute because local Python has no JAX/NumPy; no benchmark was launched.
  `experiments/notes/overnight-overhead-gather-check.py` compares old/new primal, jit, JVP, VJP and
  jit-vmap, on square/augmented/empty patterns, repeated and negative original write coordinates,
  current zeros and changed complex matrix values. It prints JAXPR primitives for mechanism inspection.
  This small check is for the gather only, not a claim that whole-pass JVP/Hessians are supported.
- Supervisor request: run that synthetic script with this repo on PYTHONPATH in the fixed environment,
  then both unchanged official benchmarks and saved-array/generalization comparisons. Expect exact
  seed equality. Obtain independent source review before any promotion. For timing confirmation,
  compare repeated fresh candidate and immediate parent `c7c3e7a` on matching policy/hardware; compare
  the original seed too before attributing or promoting combined gains. Do not promote a millisecond
  difference without stable evidence.
- Next decision: reject on new output/gradient discrepancies, failed empty-pattern/AD checks, or no
  stable total gain. A genuinely different next mechanism is builder conversion work; inspect its
  redundant host/device copies before changing it. Do not repeatedly tweak this gather without evidence.

### Candidate 2 feedback (inspected by Claude)

- Candidate SHA `453b494b8d2b6e3f04f106749b6ebe052807793b`; request `246046dc70c94ea098f67ce8151bf783`;
  publication commit `d2b6095`. Both official benchmarks passed all three fresh processes.
- Large totals: 0.985600688, 0.958901810, 0.958477251 s; median **0.958901810**, range 0.958477–0.985601.
- aLIGO totals: 0.611746792, 0.614207480, 0.621004220 s; median **0.614207480**, range 0.611747–0.621004.
- Current-cohort seed calibration (evaluation `411b23262c7b481391a712264743b0e5`, same SHA 53f38d3):
  large 1.005881, 0.976064, 0.980870 (median 0.980870); aLIGO 0.627573, 0.623209, 0.627954 (median 0.627573).
  Unpaired median differences: large −21.97 ms (−2.24%), aLIGO −13.37 ms (−2.13%). Ranges overlap on large
  (candidate max 0.985601 > seed min 0.976064), so the selection policy refuses promotion without paired
  evidence; aLIGO ranges do not overlap (candidate max 0.621004 < seed min 0.623209). Not a confirmed gain.
- Phase medians, ms (candidate 2 vs candidate 1; large / aLIGO): imports 264.9/265.0 vs 266.0/264.0;
  build 69.9/37.8 vs 73.4/38.5; forward lower 32.0/32.2 vs 36.9/37.3; forward compile 74.8/75.4 vs 77.4/88.8;
  sensitivity lower 25.4/25.3 vs 25.8/31.3; sensitivity compile 39.7/40.0 vs 39.7/48.9; gradient lower
  17.0/16.8 vs 16.9/17.7; gradient compile 53.2/55.1 vs 53.5/55.4; forward exec 185.2/33.3; gradient exec
  191.9/28.9. Forward lower −4.9 ms is consistent across all six runs (31.98–32.30 ms vs 36.9 ms median),
  matching the gather mechanism. aLIGO candidate-1 medians were inflated (noisier cohort).
- Numerics: saved official arrays and all 14 generalization cases bitwise equal to seed. Pristine-reference
  disagreements unchanged (large signal 131, gradient 3, loss; aLIGO loss; uifo_rand1/rand3 log errors
  2.036e-4/5.81e-5, others). `strict_passed=false` is the inherited pristine comparison, not new.
- Peak RSS: large 516/571/536 MB; aLIGO 308/307/311 MB. Job walls 3.82/3.55/3.55 s and 1.64 s.
- Source review: none yet (`requires_source_review`). The gather-check script result was not in feedback.
- Decision: candidate 2 is the strongest lane candidate so far, provisional. Request paired interleaved
  fresh-process runs (candidate 453b494 vs seed 53f38d3, ≥5 each, large and aLIGO) and independent review.
  Candidate 3 below builds on it (stacked; attribute only via its own paired comparison against 453b494).

## Candidate 3: static parameter-row layout on the host path

- Parent `453b494` (candidate 2) plus notes. Candidate SHA pending supervisor commit.
- Mechanism: `simulate` begins with three traced-index steps — insert optimized values
  (`parameters.at[[0], idx].set(opt[vidx])`), linking (`parameters[0, linked]` → switch → `.at[...].set`)
  and detector phases (`parameters[0, qhd_idx]`, then `scatter_mul` with traced placing indices). These
  index arrays are jit arguments, so generic indexing emits dynamic index normalization/clamping, and
  `.at[].set` cannot assume unique destinations: JAX's non-unique scatter JVP builds an id-tagging
  scatter/gather/compare/select construction that then also has to be transposed in the gradient program.
- Change: `host_pass.ParameterLayout` copies the builder's concrete indices into the static `HostPlan`
  (included in its hash key) after verifying nonnegative, in-bounds indices and unique write destinations
  (insertion and link destinations); otherwise `None` and the generic path is used. On the host path
  `simulate` uses explicit `lax.gather` / `lax.scatter(unique_indices=True, promise_in_bounds)` with these
  static indices, and passes static qhd placing indices to the unchanged `scatter_mul`. A trace-time
  shape check (`applies`) falls back if parameters/optimized shapes don't match the layout. Linking
  function dispatch (vmap of `lax.switch` with traced function indices) is unchanged. Dense/sparse paths and
  all host numerics are unchanged. Flag `simulate.STATIC_PARAMETER_LAYOUT` toggles it.
- Precedent/invalidation: the host plan already uses static copies of the sweep indices
  (`carrier_changing`, `signal_changing`) instead of the traced arrays; same rule now documented in the
  `simulate` docstring: re-run `run_build_step` if any index array changes. No answers or values cached:
  parameter values remain traced and differentiated.
- Expected values: bitwise identical outputs and gradients (copies/casts only; unique scatter derivative is
  gather/scatter of the same values). Hypothesis: lower forward lower/compile and gradient lower/compile
  by a few ms on both setups. Size unmeasured; it could be within noise.
- Local validation: none executable (no JAX locally). `experiments/notes/overnight-overhead-layout-check.py`
  compares flag on/off bitwise (value, outputs, full gradient) on aLIGO space/amplitude/frequency modulation
  at default and perturbed parameters, and prints forward-vjp jaxpr equation counts.
- Decision rule: reject on any output/gradient difference vs seed, or if lower+compile phases do not drop.

### Candidate 3 feedback (inspected by Claude): promoted

- Candidate SHA `2b4654f294414590f760fe972edd69f6774fe9e1`; request/evaluation `b986ad1181484aec96966fdbd4d39e55`;
  publication commit `a5cd6c0`. `confirmed_improvement=true`, policy `promote=true`; independent source review
  approved (claude-opus-5-5, session `647f858f-bcb8-4a19-bb68-fe4ea6934aff`, bounded scope). Now the admitted
  campaign best.
- Large: 0.954289085, 0.911267346, 0.907194179 s; median **0.911267**, range 0.907194–0.954289. Candidate max is
  below the seed cohort minimum (0.976064). aLIGO: 0.560094250, 0.578337485, 0.559704069 s; median **0.560094**,
  range 0.559704–0.578337 (seed cohort median 0.627573). Unpaired median deltas vs seed cohort: large −69.6 ms
  (−7.1%), aLIGO −67.5 ms (−10.8%). Vs candidate 2: large −47.6 ms, aLIGO −54.1 ms.
- Phase medians, ms (large / aLIGO), candidate 3 vs candidate 2: forward lower 19.5/19.2 vs 32.0/32.2;
  **forward compile 33.4/33.4 vs 74.8/75.4**; gradient lower 17.3/16.7 vs 17.0/16.8; gradient compile 52.0/53.2 vs
  53.2/55.1; sensitivity lower 25.6/26.4 and compile 39.8/41.1 (unchanged, benchmark readout); imports
  265.2/269.4; build 75.2/38.0; forward exec 188/33.8; gradient exec 191.7/28.0. The gain is almost entirely
  forward lower+compile (~54 ms), as hypothesised (non-unique scatter JVP removed); the gradient program barely moved.
- Numerics: official arrays and all 14 generalization cases bitwise equal to seed; inherited pristine
  disagreements unchanged (large signal 131 / gradient 3 / loss; aLIGO loss; uifo_rand1/rand3 log errors
  2.036e-4/5.81e-5; etc.). Six unresolved grid FD coordinates remain unresolved. Peak RSS large 545/671/578 MB,
  aLIGO 296/299/318 MB. External contention not excluded. The layout/gather check scripts' outputs were not
  reported in feedback.
- Remaining fixed costs (large): imports ~265, build ~75, lower+compile ~190 (forward 53, sensitivity 65,
  gradient 69), execution ~380 (other lane).

## Candidate 4: vectorized host bookkeeping in the build phase

- Parent `2b4654f` (campaign best). Candidate SHA pending supervisor commit. Distinct mechanism (Python host
  work in `build`, not JAX indexing).
- Change: replace per-element Python loops over NumPy arrays with exact vectorized equivalents:
  `build._matrix_indices_are_unique` (int truncation, one negative wrap, bounds, `np.unique` of flattened
  destinations), `build._group_component_indices` (stable argsort grouping; same keys/order/dtypes/values),
  `run_build_step` noise-reuse predicate and diff-slot masks (`np.isin`), and `parameter_names.index`
  linear scans in `pairs_to_arrays`/`build` replaced by a first-occurrence dictionary that raises the same
  `ValueError` when a name is absent. No change to built values; same pytree structure.
- Hypothesis: lower `build` phase time on both setups by several ms (larger for the 193-variable grid, whose
  optimization pairs each scanned the parameter-name list and whose signal system has thousands of
  destinations checked one by one). Size unmeasured; could be within noise (build spread ~2–5 ms).
- Local validation: none executable. `experiments/notes/overnight-overhead-build-check.py` compares the new
  helpers with verbatim seed copies on 3000 randomized cases (negative/out-of-bounds/duplicate/empty/float indices).
- Decision rule: reject on any built/output/gradient difference, or if `build` does not drop.

### Candidate 4 feedback (inspected by Claude): rejected, no measurable gain

- Candidate SHA `e5affda7cf786113b86e6724f37c4f286e90cd7f`; request `9200caeda0664274a596b934baadfdd1`; publication
  `c924bc2`. Official passed 3/3 both setups; official arrays and all 14 generalization cases bitwise equal to seed.
  `confirmed_improvement=false`; policy reasons: aligo_unstable_timing, requires_source_review,
  large_gain_below_selection_threshold, aligo_regression_over_two_percent, ranges overlap.
- Large: 0.963635, 0.918378, 0.918064 s (median 0.918378) vs parent 2b4654f median 0.911267. aLIGO: 0.575421,
  0.561713, 0.631368 s (median 0.575421); the 0.631 s sample has a forward compile of 104.5 ms (vs ~33.5 ms in every
  other run of this code) — an isolated outlier, not attributable to a build-only change, but it is recorded.
- Build phase: large 75.27/73.08/73.15 ms (median 73.15) vs parent 75.76/75.18/73.64 (median 75.18); aLIGO
  40.72/38.14/38.50 (median 38.50) vs 37.21/42.39/37.97 (median 37.97). ≈2 ms on large, nothing on aLIGO: within noise.
  The per-element loops were not where build time goes; without a profile the real build hotspot is unknown
  (likely the per-component instruction construction in `build()`, the device puts, and the benchmark's own eager
  conversions, which are outside our code).
- Decision: reject. Code reverted to the parent's implementations (preserved in history at e5affda).
  `experiments/notes/overnight-overhead-build-check.py` now compares identical code and is kept only as history.
  Consecutive evaluated submissions without a confirmed gain since the last promotion: 1.

## Candidate 5: remove structurally redundant XLA ops at the host-pass boundary

- Parent `2b4654f` (campaign best); candidate 4 reverted. Candidate SHA pending supervisor commit.
- Mechanism: the same op-count lever that gave candidate 3's ~54 ms (compile cost here scales with the number of
  HLO ops in tiny programs), applied to the ops that remain around the callback:
  1. Transposes: `simulate` returned `carrier.T`, `signal.T`, so the forward program had transpose kernels and the
     gradient program transposes of their cotangents. The host callback now returns (CN, Bc)/(N, Bs) directly, plus
     separate untransposed copies used only as residuals, so no buffer is both a primal output and a residual
     (avoids XLA copy insertion). The backward callback transposes the incoming cotangents to C-contiguous copies,
     so `host_backward` sees identical values and memory layout.
  2. Placeholder link: when a setup has no linked parameters the builder adds a link from parameter 0 to itself.
     It now uses a named `build.identity_link` (it was `lambda x: x`). The static layout records the builder's
     linking-function indices; if every link uses `identity_link` and reads/writes the same index, the gather,
     `vmap(switch)` and scatter are omitted. That is exactly the identity for values and derivatives (up to the
     sign of a zero cotangent, which compares equal). Any real link, or a stale global index that points at another
     function, keeps the original path.
  3. Empty detector phases: with no qhd placings, the `exp(radians(...))` of an empty gather and the `scatter_mul`
     with zero updates are omitted (scatter_mul with no updates returns its operand).
  All decisions use static builder structure, never parameter values. `simulate.SKIP_STATIC_NOOPS` toggles 2–3.
- Hypothesis: a few fewer ops in the forward and gradient programs → a few ms less forward/gradient lower+compile on
  both setups. Small; may be within noise. Host-side transposes add microseconds of copying.
- Expected numerics: bitwise identical outputs and gradients vs seed/2b4654f.
- Local validation: none executable (no JAX). `overnight-overhead-layout-check.py` now compares (static off),
  (static on, skip off), (static on, skip on) bitwise on aLIGO in three modes, and reports whether the identity-link
  and detector-phase conditions apply and the forward-vjp jaxpr equation counts.
- Decision rule: reject on any array difference, or if forward+gradient lower+compile does not drop vs 2b4654f
  (forward 19.5/33.4 ms, gradient 17.3/52.0 ms large medians).

### Candidate 5 feedback (inspected by Claude): mechanism confirmed vs its parent; not promoted (incumbent moved)

- Candidate SHA `c3c4ab0a9118529b0e3afa33284ab3e5cc6f2523`; request `366ba7a5aaf54ae381861d49dcf004cc`; publication
  `c5fe984`. Official passed 3/3 on both setups; official arrays and all 14 generalization cases bitwise equal to seed.
  Inherited pristine disagreements unchanged.
- Large: 0.908242, 0.882519, 0.875051 s (median 0.882519) vs parent 2b4654f 0.911267: −28.7 ms (−3.2%).
  aLIGO: 0.532373, 0.532223, 0.532545 s (median 0.532373, range 0.06%) vs 0.560094: −27.7 ms (−4.9%).
- Phase medians large/aLIGO vs 2b4654f: forward lower 11.25/11.28 vs 19.5/19.2 ms; forward compile 27.15/27.33 vs
  33.4/33.4; gradient lower 11.56/11.52 vs 17.3/16.7; gradient compile 45.67/47.07 vs 52.0/53.2. Sensitivity
  (benchmark readout) and execution unchanged. ≈26 ms of lower+compile removed, consistent in all six runs, i.e.
  the improvement is attributable to the mechanism, not noise. Peak RSS large 578/591/582 MB, aLIGO 301/310/311 MB.
- Not promoted: the admitted campaign best had moved to `5bbb91e` (evaluation `2c7810bf…`: candidate 3 plus the
  solver lane's backward changes; large median 0.852667 s, range 0.850608–0.882359; aLIGO 0.555710 s). Policy
  compared c3c4ab0 against that incumbent (requires_source_review, large gain below threshold, ranges overlap).
  Not a failed mechanism: the incumbent includes a different, complementary change.
- Consecutive submissions without a promoted gain: 2 (c4 no effect; c5 effective but superseded parent).

## Candidate 6: candidate 5's boundary-op removal transferred onto the campaign best 5bbb91e

- Parents: `5bbb91e38ff993a10486f296a738860339cd05e0` (admitted campaign best, approved review, evaluation
  `2c7810bfe84648299731e98a6bb133ae`) and `c3c4ab0` (candidate 5). Candidate SHA pending supervisor commit.
- Construction: this branch already held candidate 3 (common to both). The remaining 5bbb91e delta was applied
  hunk by hunk from its published diff: `host.function_jacobian(with_outputs=...)`; `SystemPlan` last-write
  cotangent fields and assignment-vs-add.at backward; `_ASSEMBLY` forward→backward state replacing `_FACTORS`
  (with carrier factors); exact covariance-cotangent shortcut in `host_backward`; carrier factor reuse.
  Candidate 5's changes (transposed callback outputs with separate residual copies, `identity_link`/no-op link
  skip, empty-detector-phase skip, `SKIP_STATIC_NOOPS`) were kept unchanged. The two touch disjoint code: c5 changes
  the callback wrappers/shapes and `simulate`; 5bbb91e changes the host backward internals. The c5 backward
  wrapper hands `host_backward` untransposed residuals and C-contiguous re-transposed cotangents, i.e. exactly the
  arguments 5bbb91e's `host_backward` received before.
- Hypothesis: the ~26 ms lower+compile saving of c5 is additive to 5bbb91e's execution saving (different phases).
  Expected large ≈ 0.85 − 0.026 ≈ 0.825–0.83 s and aLIGO ≈ 0.53 s; unmeasured.
- Expected numerics: bitwise identical to 5bbb91e (whose arrays equal the seed in every audited case).
- Needs: both official benchmarks, strict/generalization comparisons, fresh independent source review of the
  combined diff, and preferably paired runs against 5bbb91e.

### Candidate 6 feedback (inspected by Claude): additive vs its parent; incumbent moved again

- Candidate SHA `5aaf391162fee4cb752a6872e74fc854ba1a2cc3`; request `27a46d5a39094e64951b8de6048ca96c`; publication
  `5d548b2`. Official 3/3 both setups; strict vs seed passed (gradient max abs diff 5.65e-5, rel L2 9.7e-10 large;
  2.1e-8 / 6.5e-13 aLIGO — rounding from 5bbb91e's exact-identity backward shortcut, not from the boundary ops); all
  14 generalization cases pass vs seed. Pristine disagreements unchanged.
- Large 0.855195, 0.835383, 0.824027 s (median 0.835383) vs 5bbb91e median 0.852667: −17.3 ms. aLIGO 0.524702,
  0.527734, 0.544907 s (median 0.527734) vs 0.555710: −28.0 ms. Phases large: forward lower 11.3, compile 26.9;
  gradient lower 11.6, compile 46.2; gradient exec 141 ms (5bbb91e's backward saving retained). The boundary
  mechanism's ~26 ms lower+compile saving carried over unchanged.
- Not promoted: incumbent became `ee4fea2` (evaluation `e4f7b59d…`, large median 0.801578, aLIGO 0.548555), which
  adds the collinear-signal-cotangent and Hermitian-noise backward shortcuts. Third evaluated submission in a row
  without a confirmed promotion, but c5/c6 show the same reproducible ~26 ms phase gain each time; the misses are
  incumbent movement, not mechanism failure. Coordination note: the boundary-op change touches only callback
  wrappers/`simulate`/`build.identity_link`, and composes cleanly with backward-math changes.

## Candidate 7: boundary-op removal on the current campaign best ee4fea2 (search-direction note)

- Parents: `ee4fea28c04d482566be16e916b609d7c6a99e5e` (admitted best, approved review, evaluation
  `e4f7b59d3b094a8e9c6dd41263cab78e`) and `5aaf391` (candidate 6). Candidate SHA pending.
- Construction: candidate 6 plus ee4fea2's two additional published hunks, applied verbatim: `HERMITIAN_TOLERANCE`,
  `_transpose_index`, `_collinear_coefficient`, `_is_hermitian`; and in `host_backward` the collinear-signal shortcut
  and Hermitian-noise adjoint branch. No other change. This is not a new mechanism; it is the conservative way to put
  the already-validated lane gain on top of the incumbent rather than racing it again.
- Hypothesis: same ~26 ms lower+compile saving on top of ee4fea2 → large ≈ 0.78 s, aLIGO ≈ 0.52 s; unmeasured.
  Numerics expected identical to ee4fea2 (boundary changes are exact copies/no-ops).
- If not promoted for incumbent-movement reasons again, I recommend the coordinator apply this lane's diff to
  whatever the incumbent is at the time (it is small and disjoint) rather than another chase from this branch.

### Candidate 7 feedback and hypothesis handoff (Codex, 2026-11-22 02:35 UTC)

- Exact candidate `1ea70bfbde9bcf42fce836846a4e1e92aee36a3b`; evaluation
  `dacbeb43d6a740f49d2dccc765449298`, publication `21ebd736a144b7b783a1c75fd8984274713f3349`;
  local feedback HEAD `a241374`. Both official benchmarks passed 3/3. No evaluator failure.
- Large samples: 0.806567159, 0.779120542, 0.773866884 s; median **0.779120542 s**,
  range 0.773866884–0.806567159 s. aLIGO samples: 0.517428415, 0.517229011, 0.521617815 s;
  median **0.517428415 s**, range 0.517229011–0.521617815 s.
- Against admitted incumbent `ee4fea28c04d482566be16e916b609d7c6a99e5e`, unpaired median differences
  are -22.457 ms large and -31.127 ms aLIGO. Large candidate maximum 0.806567 exceeds incumbent
  minimum 0.794425; ranges overlap. **Not a confirmed improvement or promotion.** Source review is
  null. Policy reasons: `requires_source_review`, `large_first_run_ranges_overlap_requires_paired_evidence`.
  The incumbent did not move in this comparison; repeating the incumbent-chasing explanation would be wrong.
- Phase medians, ms, large / aLIGO: imports 266.277 / 264.398; build 74.523 / 37.255;
  forward lower 12.002 / 11.212, compile 27.872 / 27.223, execute 181.160 / 32.702;
  sensitivity lower 25.730 / 26.418, compile 39.787 / 41.388, execute 0.858 / 0.471;
  gradient lower 11.575 / 11.598, compile 45.929 / 46.981, execute 86.548 / 14.690.
  The boundary phase reduction remains consistent with candidates 5 and 6. The further gradient-execution
  reduction versus candidate 6 (141.413 / 23.532 ms) belongs to the transferred numerical lane changes.
  It is not a new gain from this lane. No repeated matched phase comparison to ee4fea2 was supplied.
- Sampled RSS bytes large: 523784192, 573317120, 523735040; aLIGO: 294809600, 294731776,
  293302272. Benchmark job walls large: 3.020475, 3.017903, 3.018821 s; aLIGO: 1.371973,
  1.372252, 1.646331 s. Whole evaluation 20.685640 s, including generalization (~6.585431 s).
  Warm runtime is not supplied here. Other-host contention was not excluded. No timing sample discarded.
- Numerical evidence: all official arrays pass the initial-seed tolerances; sensitivity log difference
  is zero. Gradient maximum absolute difference versus seed is 5.686350e-6 (relative L2 8.181451e-11)
  for large and 3.637979e-11 (relative L2 1.294944e-15) for aLIGO. All 14 additional cases pass the
  initial-seed comparisons. These are **not bitwise-equality findings** for gradients. The generalization
  `artifacts` block compares the candidate archive to itself; its matching digest does not establish
  identity to the initial seed or ee4fea2. Compare the saved ee4fea2 and candidate arrays directly before
  accepting the handoff's expected exact equality. No such direct comparison was supplied this turn.
  Pristine-reference mismatches (including uifo_rand1/rand3 log errors ~2.0361e-4/5.8101e-5) and six
  unresolved grid FD coordinates persist; no universal correctness claim. Whole-pass JVP/Hessians remain unsupported.
- Source inspection: the remaining simulator diff versus ee4fea2 is precisely the boundary/no-op work in
  build.py, host_pass.py and simulate.py. No new solver transfer is useful: its supplied mathematical
  changes are already present. This inspection is not the required independent review.
- Validation repair: the existing layout-check script imported `simulate` from the package, which exports
  a **function**, then tried to use it as the implementation module. Replaced that import with
  `importlib.import_module("differometor.simulate")`. This only fixes our notes-side diagnostic; no simulator
  source changed. AST parsing and `git diff --check` pass; runtime remains unexecuted locally (no JAX/NumPy).
  Previous notes reported no runtime result for this script; do not infer one from official passes.

### Decision and concrete coordinator follow-up

- End this boundary-compilation hypothesis with no new simulator submission. Preserve every failed trial;
  keep candidate 7 available for evaluation and retain **ee4fea2 as the admitted best**, not candidate 7.
  Three-plus unconfirmed submissions justify stopping further variants of this mechanism. No branch reset,
  cherry-pick, merge or promotion is performed. This handoff ends the hypothesis, not the eight-hour campaign.
- First resolve existing evidence: independent review of exact candidate 1ea70bf versus ee4fea2; direct
  saved-array comparison to that parent; run the repaired layout check and prior gather check in the fixed
  environment. The checks supplement, and never replace, the two unchanged official benchmarks.
- Request at least five interleaved fresh-process complete runs per exact SHA (1ea70bf and ee4fea2),
  separately for large and aLIGO, under the same CPU 2/thread/resource policy. Retain every sample, phase,
  memory measurement and overlap observation. Use the existing supervisor/evaluator route; no launch changes.
  This tests the measured ~26 ms boundary hypothesis without inventing another candidate or changing arithmetic.
- Distinct next direction: profile setup before changing it. Imports remain ~264–266 ms, build ~37–75 ms.
  Static inspection finds no additional eager optional plotting dependency on the simulation path.
  Candidate 4 already showed that vectorizing builder bookkeeping did not give a clear transferable benefit.
  `prepare_arrays` does contain a host→JAX→NumPy→JAX conversion of changing values, but its cost is unknown;
  eliminating that tiny conversion blindly is not justified as the next full submission.
- Requested diagnostics, through the coordinator: a fresh-process import-time tree for the actual import
  sequence; and cProfile attribution of build_inputs/run_build_step on both official setups. Keep profiled
  runs diagnostic-only and separate from clean timing samples; do not modify the official files. Attribute
  JAX device puts, matrix/instruction construction, sparse-plan construction and benchmark-owned setup work
  separately. Select one demonstrated hotspot afterward, using ee4fea2 (or a subsequently admitted reviewed
  parent) as the starting point. No speculative implementation or new official run was launched here.
- Continuity: campaign `overnight-20261122`, lane/session `overnight-overhead-v1`, branch
  `explore/overnight-overhead-v1`, absolute deadline **2026-11-22 09:27:44 UTC / 1795339664** unchanged.

## Candidate 8: host-first construction with one final batched array transfer

- The supervisor explicitly resumed after the hypothesis handoff and requested a concrete next experiment.
  No new evaluator result has arrived; candidate 7's feedback above remains authoritative.
- Deliberate source parent: admitted, independently reviewed **ee4fea28c04d482566be16e916b609d7c6a99e5e**,
  evaluation `e4f7b59d3b094a8e9c6dd41263cab78e`. The unpromoted boundary/no-op changes of candidates 5–7
  were removed from this working copy only. Candidate 7 remains preserved at `1ea70bf`; no Git history was
  reset. New candidate SHA and run IDs pending supervisor commit/evaluation. This follows the search-policy
  change of direction; it does not stack another optimization on the unreviewed boundary variant.
- Measured target: build remains ~74.5 ms large / 37.3 ms aLIGO in candidate 7. Earlier vectorized Python
  bookkeeping (candidate 4) was rejected. This experiment instead changes when arrays are transferred.
- Established source-level redundancy: `build`, `pairs_to_arrays` and `_group_component_indices` eagerly
  convert each NumPy array to JAX; `prepare_arrays`, diff-slot/noise-reuse checks, `_build_sparse_structure`
  and `build_host_plan` then convert those arrays back to NumPy for structural inspection. The finalized
  arrays are eventually needed as JAX inputs, but the intermediate device-array wrappers and host reads
  are avoidable. Their time share is not profiled, so no magnitude of gain is promised.
- Implementation: the four internal array producers accept private `_host_arrays=True`; their public
  defaults keep the original JAX-returning behavior. `run_build_step` uses NumPy intermediates while
  deriving all structural plans, then `_put_built_arrays` transfers only ndarray leaves with one
  `jax.device_put(tuple(...))` and reconstructs the built dict/list/tuple containers, preserving dictionary
  insertion order (including the public port map). Python metadata (including port-map
  integers), None, empty tuples and registered-static plans are preserved. `HOST_BUILD_ARRAYS=False`
  selects the original path for diagnosis. All arrays are still created and transferred during the build
  call; any asynchronous completion remains inside the complete first-run evaluation. No result caching,
  preloading, fixture dispatch, compilation-policy change or work outside the timer.
- Net simulator diff versus ee4fea2 is **build.py and simulate.py only**. Confirmed byte-identical to
  ee4fea2: host.py, host_pass.py, sparse.py, components.py. Solver/refinement/adjoint mathematics unchanged.
  Matrix values, selection order, structural zero entries, diff-slot predicates and index dtypes unchanged.
  The change may affect host-buffer lifetime and memory; the evaluator must measure that tradeoff too.
- Hypothesis: fewer per-array dispatches and readbacks reduce setup/build and complete first-run time on
  arbitrary supplied setups. Compilation and execution should be unchanged relative to ee4fea2. A null
  result is plausible if instruction construction or benchmark-owned work dominates. Compare against
  ee4fea2, **not candidate 7**, whose separate ~26 ms boundary reduction has intentionally been removed.
- Local checks: AST parsing and `git diff --check` passed. A standard-library AST comparison of all four
  changed producers found their arithmetic/control-flow AST identical to ee4fea2 after removing only the
  new conversion-selector assignments/keywords and normalizing converter names. This is source evidence,
  not a runtime equivalence result. No NumPy/JAX installed locally; no benchmark or runtime check launched.
  The extracted transfer helper also passed a standard-library test using explicit array/JAX stand-ins
  for one transfer call, container order, opaque-plan identity and metadata preservation; this verifies
  traversal only and is not numerical/JAX validation.
- Added `experiments/notes/overnight-overhead-host-build-check.py`: build-only equivalence of old/new
  paths on three aLIGO modulation modes, sparse on/off, optimized/default/grouped inputs, and arbitrary
  three-point sweeps. It compares pytree/static-plan equality, shapes, dtypes, weak typing and exact array
  bytes, plus empty arrays and Python metadata preservation. The link registry is restored between its
  two synthetic builds so function-index assignment starts from identical state. No official validation
  is altered. The preserved layout diagnostic is now also compatible with the parent without no-op helpers.
- Supervisor request: run this focused build check in the fixed environment, then both unchanged full
  benchmarks and generalization on the new exact SHA, with saved-array comparisons to ee4fea2 and seed.
  Expect identical arrays to ee4fea2; investigate any difference rather than relaxing tolerance. Retain all
  inherited pristine-reference failures and unresolved FD coordinates. Obtain fresh independent review.
  For promising results request repeated interleaved fresh candidate/ee4fea2 runs, retaining all samples,
  phase breakdowns, RSS and contention observations. Profiled diagnostics remain separate from clean timings.
- Decision: reject if any returned structure/value differs, new numerical failures occur, or setup gains
  do not survive matched timing. Do not add a second conversion variant without evidence. Deadline/session
  unchanged; this is an evaluable new setup hypothesis, not a claim that candidate 7 was promoted.


### Candidate 8 feedback and decision (2026-11-22)

- Exact candidate: `ddfb639cb16271550c5d0de799665210ce4290ee`; dual-official job
  `d35ea4aa620d457a88c1ac4a68ab0c8f`, grid-1/2/3 and aligo-1/2/3. Source review absent.
- Large complete first-run samples: 0.841352144, 0.864800531, 0.791974228 s;
  median **0.841352144**, range **0.791974228–0.864800531**.
- Official aLIGO samples: 0.543858401, 0.543838736, 0.599401077 s;
  median **0.543858401**, range **0.543838736–0.599401077**.
- Build samples large: 73.737, 71.866, 70.792 ms; aLIGO: 37.582, 36.894, 36.104 ms.
  No matching parent phase cohort is supplied, so no measured build delta is established.
  Large forward execution varied 176.259–252.999 ms; aLIGO gradient varied 14.384–63.480 ms.
  All samples are retained. External contention is unknown; those variations are not proof of
  either a simulator regression or an infrastructure cause.
- All six unchanged official runs passed. All 14 generalization cases passed comparison against
  initial seed tolerances. The pristine comparisons still fail: grid signal, loss, three gradients;
  uifo_rand1/rand3 sensitivity errors ~2.0361e-4/5.8101e-5, plus the other recorded inherited
  discrepancies. Official output archives match candidate 7's hashes, but this is not a claim
  of byte equality to the seed or admitted parent. Seed gradient maximum absolute differences
  remain 5.686350e-6 large and 3.637979e-11 aLIGO. Six unresolved grid finite-difference
  coordinates remain unresolved; extra aLIGO coordinate checks remain 29/29 from prior evidence.
- Sampled peak RSS large: 614457344, 541024256, 521797632 bytes; aLIGO: 280952832,
  288124928, 288210944 bytes. Generalization peak: 908480512 bytes. No budget exceedance.
  Sampling can miss peaks. No infrastructure failure reported; numerical review still required.
- Not promoted: unstable aLIGO timing, missing source review, insufficient large gain and overlapping
  ranges. Decision: retire host-first conversion from the working simulator because useful benefit
  is unestablished and it adds conversion/container complexity. This does not assert a measured
  slowdown. Preserve candidate 8 and its diagnostic in history. Restore build.py and simulate.py
  byte-for-byte from reviewed ee4fea2; keep ee4fea2 as admitted best.

## Candidate 9: joint sideband split in the public signal readout

- Source parent: reviewed `ee4fea28c04d482566be16e916b609d7c6a99e5e`. Candidate SHA/job IDs
  pending supervisor. Net simulator diff versus this parent: components.py only (11 additions,
  2 deletions). Other nine simulator modules checked byte-for-byte against parent. No combination
  with unadmitted candidate 7 or 8; their history remains preserved.
- Distinct target: small readout reverse graph, not another builder-transfer or callback variant.
  Candidate 8 gradient trace/lower+compile medians are about 69.9 ms large and 69.7 ms aLIGO.
  These include the whole backward stage, not solely this operation. Sensitivity trace/lower and
  compile remain roughly 65–68 ms. Expected gain magnitude is unknown and may be negligible.
- Established redundant work: signal_detector slices the same signal into upper and lower
  sidebands independently. Their reverse passes each pad to the full signal shape and add the
  two cotangents. A single joint split transposes by concatenation. JAX 0.9 source confirms this:
  [split transpose and lowering](https://raw.githubusercontent.com/jax-ml/jax/jax-v0.9.0/jax/_src/lax/lax.py),
  `_split_transpose_rule` / `_split_lower`;
  [public split implementation](https://raw.githubusercontent.com/jax-ml/jax/jax-v0.9.0/jax/_src/numpy/lax_numpy.py),
  `_split` calls `lax.split`. This is structural evidence, not a timing measurement.
- Implementation: `jnp.split` at clipped N and 2N boundaries yields the same upper/lower slices
  and an unused tail. Clipping preserves old slice behavior for short vectors, including the old
  broadcasting rules. Trailing mechanical coordinates still receive zero cotangents. Conjugation,
  two multiplications, addition, dtype promotion and broadcasting are unchanged. Uses standard
  JAX differentiation, no hand-coded abs rule, custom derivative or approximation. The public
  power readout is unchanged: it is auxiliary to the official loss, so a derivative rewrite there
  would not address this workload. No solver/refinement/adjoint mathematics changed.
- Signed-zero caveat to inspect: removing zero-pad additions can retain a negative zero in a
  cotangent where the original addition canonicalized it. The diagnostic reports these separately;
  no claim of bitwise derivative identity. No abs/sqrt convention is replaced. Non-finite tests
  check compatibility of the readout, not physical validity of non-finite optical setups.
- Local checks: all simulator and new diagnostic files parse; git diff --check passes. A pure-Python
  interval check exhaustively confirmed upper/lower slice identity and partition coverage for
  900 (carrier length, signal length) pairs, including zero and short vectors. NumPy/JAX are absent
  locally; no numerical runtime, official benchmark or independent benchmark was launched.
- Added `experiments/notes/overnight-overhead-readout-check.py`: exact value/JVP/VJP comparisons to
  the old expression, eager and JIT, real/complex mixtures, broadcasted sweeps, mixed ranks,
  empty and short vectors, tails, signed zeros, infinities/NaNs, vmap and standalone real Hessian.
  Reports signed-zero differences and recursive JAX primitive counts for the two VJP graphs.
  This does not extend the whole-pass host simulator's first-order-only compatibility claim.
- Supervisor request: run that synthetic diagnostic first; inspect actual pad/add versus concatenate
  counts. Evaluate both unchanged full benchmarks on the same new SHA, all saved arrays/gradients,
  14-case generalization and direct admitted-parent comparison. Obtain independent source review.
  If promising, use interleaved fresh-process parent/candidate runs on matching CPU/environment,
  report every sample, separate medians/ranges, phase tradeoffs, RSS and overlap. Do not promote
  merely from an isolated compilation saving or claim pristine disagreements are resolved.
- Next decision: reject if numerical checks introduce discrepancies or complete first-run gains do
  not survive paired timing. Do not stack more readout algebra without measured graph/phase evidence;
  the next distinct investigation would require the previously requested import/build profile.


### Candidate 9 feedback and retirement (2026-11-22)

- Exact candidate `27c951e5cf854b1ff352e19fa706d81c794af37f`; evaluation
  `53b3f5fd10724c96b85344729acd6f42`, grid-1/2/3 and aligo-1/2/3.
- Large complete first-run samples: 0.823984342, 0.801257059, 0.800967131 s;
  median **0.801257059**, range **0.800967131–0.823984342**.
- Official aLIGO samples: 0.545446666, 0.547231529, 0.542567078 s;
  median **0.545446666**, range **0.542567078–0.547231529**.
- Unpaired median differences from admitted ee4fea2: -0.321 ms large and -3.108 ms aLIGO.
  Large ranges overlap; no meaningful repeat-supported improvement. Source review absent.
  Reject the readout experiment as an optimization, retaining its commit and diagnostic.
- Target gradient trace/lower+compile samples large: 68.888, 69.791, 71.178 ms;
  aLIGO: 69.257, 70.595, 70.437 ms. Sensitivity lower+compile samples large:
  64.885, 66.256, 65.404 ms; aLIGO: 67.215, 67.225, 67.517 ms. No matched parent
  phase samples supplied; no reliable target-phase delta established. Requested synthetic
  readout diagnostic/primitive counts are not included in feedback, so remain unconfirmed.
- Official 3/3 passes for both setups; all 14 generalization cases pass initial-seed comparison
  tolerances. Official array hashes equal those recorded for candidates 7 and 8. Pristine strict
  failures remain (including grid signal/three gradients/loss and uifo_rand1/rand3 sensitivity),
  along with six unresolved grid FD coordinates. No new numerical discrepancy reported, but no
  universal correctness claim. Whole-pass custom VJP still lacks forward-mode/Hessian support.
- Sampled peak RSS large: 541880320, 618713088, 500736000 bytes; aLIGO: 281800704,
  282968064, 289210368 bytes; generalization: 861216768 bytes. No infrastructure failure or
  memory-budget exceedance reported. External job overlap remains unknown.
- Restore components.py from reviewed ee4fea2. No additional readout-algebra variants and no
  combination with candidates 7/8. Admitted best remains ee4fea2.

## Candidate 10: compact coordinate-to-position metadata

- Deliberate source parent: `ee4fea28c04d482566be16e916b609d7c6a99e5e`. Candidate SHA and
  evaluation IDs pending supervisor. Net simulator delta against parent is sparse.py only,
  25 insertions/7 deletions; all other nine simulator modules byte-identical. Despite the module
  name, this changes structural setup metadata only, not sparse solving, refinement or adjoints.
- Actual redundant allocation: every SparseSystem builds and retains an int64 dense matrix
  `_position`, filling every element with -1 and replacing structural entries with their sparse
  positions. It is only used for coordinate lookups (repository search found no external reader).
  Each table costs 8*N*(N+augmented) bytes even when almost all positions are absent. This work
  occurs during run_build_step; no cache or persisted state is involved.
- Existing coordinates already arrive in CSC order, followed by RHS entries sorted by row.
  Their column-major integer keys `col*N + row` are consequently sorted and distinct. Store
  only these keys and resolve coordinate positions with np.searchsorted. Check bounds first,
  normalize legal negative coordinates once, preserve NumPy coordinate broadcasting and
  repeated queries, and reject missing pattern entries. Empty patterns/queries are supported.
  Out-of-bounds and incompatible broadcast queries remain IndexError; absent entries remain
  ValueError. Exception wording changes. `_position` was private and is replaced by private
  `_position_keys`; the public positions method and its return dtype/shape are preserved.
- Pattern discovery, explicit write/extra destinations (including current zero values), CSC
  ordering, write order/duplicates, base-value gathers, structural hashes and all numerical
  code are unchanged. No design-parameter dependence is pruned. Rebuilding a setup creates
  a fresh key vector. There is no fixture/shape identity dispatch or numerical fallback.
- Hypothesis: avoiding initialization and lifetime of dense inverse tables reduces setup time
  and retained memory for sparse optical systems. The new lookup costs O(log nnz) per query
  instead of direct indexing and adds validation, so small/dense setups may gain nothing or
  regress. No speedup is measured. Existing build phase remains roughly 70–74 ms large and
  38–40 ms aLIGO; table construction's share has not been profiled. This is a different mechanism
  from the retired host/JAX conversion experiment, not a retry of generic sparse solving.
- Local checks: all simulator/new diagnostic sources parse and git diff --check passes.
  A pure-Python dense-dictionary versus sorted-key/bisect model matched 8,540 coordinates
  across varied dimensions, square/augmented layouts and negative indices. This checks the
  indexing argument, not actual NumPy execution. Local NumPy/JAX remain unavailable.
- Added `experiments/notes/overnight-overhead-position-check.py`: compares real SparseSystem
  construction and lookup to an independent dense-table reference over random/empty/full
  patterns; tests duplicates, structural zeros, extra destinations, negative/out-of-bounds
  coordinates, query broadcasting, zero-sized matrices, errors, rebuild invalidation, exact
  hashes/order/dtypes and metadata bytes. Run alongside the existing gather diagnostic to
  check structural-zero tangent contributions. Neither script has been executed locally.
- Supervisor: run those focused diagnostics, then both unchanged full benchmarks on the same
  SHA and saved-array/generalization comparisons against admitted parent and initial seed.
  Expect unchanged physical arrays/gradients; investigate any discrepancy without changing
  tolerances. Obtain independent review before promotion. If promising, use interleaved fresh
  parent/candidate runs with separate medians/ranges, target build-phase deltas, RSS and job
  overlap. A smaller metadata allocation alone does not establish first-run improvement.
- Next decision: if setup gain is not stable, reject rather than tuning lookup algorithms blindly;
  retain ee4fea2 and request a supervised build profile before another structural variant.


### Candidate 10 feedback and search-direction handoff (2026-11-22)

- Exact candidate `890af63d7c7da2d08a33fe945d391571690e1b5a`; evaluation
  `82170c2372534c88b82296452b4631fd`, grid-1/2/3 and aligo-1/2/3.
- Large complete first-run samples: **0.833215686, 0.801084740, 0.790944828 s**;
  median **0.801084740**, range **0.790944828–0.833215686**.
- Official aLIGO samples: **0.544145374, 0.542451084, 0.543524455 s**;
  median **0.543524455**, range **0.542451084–0.544145374**.
- Unpaired median deltas against admitted ee4fea2: -0.493 ms large, -5.031 ms aLIGO.
  These do not establish improvement: large gain below selection threshold, overlapping ranges,
  source review missing. No samples discarded. No combined score calculated.
- Target build samples: large 72.047, 72.364, 71.515 ms (median 72.047); aLIGO 38.792,
  37.980, 37.417 ms (median 37.980). No matching parent phase cohort, so no attributable delta.
  Large forward execution 176.643–185.142 ms, imports 263.893–293.011 ms. Import and execution
  variability are larger than the observed large median difference; their causes are unproven.
- Sampled peak RSS large: 566087680, 529248256, 539631616 bytes; aLIGO: 280870912,
  284540928, 287014912 bytes; generalization: 864940032 bytes. No memory-budget exceedance
  or infrastructure failure. Sampling misses brief peaks; overlapping external work is unknown.
  Reduced metadata storage from the algorithm does not establish a measured RSS reduction.
- Both official benchmarks passed 3/3; all 14 generalization cases pass initial-seed tolerances.
  Official output archive hashes equal the recent candidates' hashes. Pristine comparisons still
  fail: grid signal/gradients 33,161,180/loss; aLIGO loss; custom uifo_rand1/rand3 sensitivity
  (~2.0361e-4/~5.8101e-5 log errors), plus previously recorded cases. Seed comparison gradient
  maximum absolute differences remain 5.686350e-6 large and 3.637979e-11 aLIGO. No new discrepancy
  reported, but saved parent-versus-candidate inspection and source review are not supplied.
  Six grid FD coordinates 54,59,63,136,161,163 remain unresolved; prior aLIGO checks passed 29/29.
  Whole-pass custom VJP remains first-order reverse mode only. No universal physics claim.
- The position/gather diagnostic outputs requested for candidate 10 are absent from feedback;
  do not mark them passed. Retain candidate 10 and all previous failed/unconfirmed commits.
- Decision: retire compact metadata as a performance proposal for this campaign cohort, restore
  sparse.py from ee4fea2, and stop this sequence of speculative small setup/readout changes.
  All ten current simulator modules checked byte-for-byte against admitted reviewed ee4fea2.
  This is a working-source restoration only; no Git reset, commit, merge or promotion performed.

### Concrete next experiment: supervised attribution before another simulator edit

- Candidates 8 (host-first transfer), 9 (joint readout split) and 10 (compact inverse lookup) all
  passed official validation but none yielded a meaningful confirmed large-case improvement.
  Their large medians were 0.841352144, 0.801257059 and 0.801084740 s respectively; these are
  separate unmatched cohorts, not an average or a controlled ranking. Source-level redundancy
  alone has not reliably predicted end-to-end benefit. Do not produce another lookup/readout
  variation without new phase attribution.
- Added **experiments/notes/overnight-overhead-profile.py**, a concrete supervisor-run diagnostic.
  It accepts arbitrary setup JSON, optional optimization-pair JSON and optional changing-pair/value
  JSON; no fixture names or shape dispatch. Use the exact caller inputs for relevant attribution.
  It checks that imports come from this checkout and that JAX/NumPy/simulator were not preloaded.
  It captures cProfile call counts, self/cumulative time and instrumented wall durations for
  simulator/library imports, backend initialization, input load, Setup.from_data, sweep transfer
  and run_build_step, with completion synchronization. It reports sparse system dimensions,
  entry counts and retained dense/compact inverse-lookup bytes. It never calls simulation, edits
  inputs, starts a subprocess, writes files or changes thread/CPU policy. Output is JSON on stdout.
- CLI: `python experiments/notes/overnight-overhead-profile.py --setup-json <supplied-setup.json>
  --optimization-pairs-json <supplied-pairs.json> --changing-pairs-json <supplied-sweep-pairs.json>
  --changing-values-json <supplied-sweep-values.json>`. Place the checkout on PYTHONPATH and use
  the supervisor's fixed environment/resource policy. Do not invent omitted pairs from the fixture:
  omitted inputs explicitly exercise public builder defaults, not the official build workload.
- Profile ee4fea2-equivalent source in fresh processes for the two official setups and one other
  setup. These are instrumented diagnostic runs, never clean timing samples or replacements for
  the unchanged official benchmarks. The script's import sequence covers simulator dependencies,
  not all benchmark imports (e.g. benchmark-owned optax). For the actual import sequence request
  a supervised Python import-time tree separately. Likewise benchmark-owned parameter grouping
  and frequency generation need separate attribution; this script makes no claim to include them.
- Local validation: profiler CLI help ran using standard library only; all edited Python sources
  parsed; simulator identity and git diff --check passed. No profiling run or independent benchmark
  executed locally; JAX/NumPy remain unavailable. The profiling artifact is prepared, not measured.
- Before further experimentation, select a hotspot with enough measured cost to exceed timing
  spread, then formulate one conservative change. Independently, candidate 7 (`1ea70bf`) remains
  the strongest unadmitted boundary hypothesis: inspect its source and direct parent arrays, and
  request interleaved fresh-process confirmation against ee4fea2 as already specified above.
  Do not silently combine it with any of these failed/unconfirmed refinements.
- Handoff stops this hypothesis, not the authorized campaign. Lane/session overnight-overhead-v1,
  branch explore/overnight-overhead-v1, deadline 2026-11-22 09:27:44 UTC (1795339664) unchanged.
  No new optimization revision is ready for official evaluation; restored parent and diagnostic
  are ready for supervisor bookkeeping and attribution work.

### Candidate 11: homogeneous linking-function dispatch (prepared, unmeasured)

- Explicit supervisor continuation requests one concrete implementation after the no-change
  handoff. No new timing or profiling feedback arrived. Keep candidate 10's unsuccessful result
  above; do not retry the compact lookup, host-first build or scalar readout sequence. Switch to
  a narrow JAX-boundary hypothesis on reviewed simulator source **ee4fea28c04d482566be16e916b609d7c6a99e5e**.
  Candidate SHA and new job identifiers are pending supervisor commit/evaluation. The profile
  diagnostic remains available and unexecuted; it is not evidence for this proposal.
- Evidence for targeting compilation: latest evaluated candidate 10 spends roughly 19.5 ms
  forward lowering, 33.4 ms forward compilation, 16.7 ms gradient lowering and 53.1 ms gradient
  compilation on the large case (individual samples span the values recorded above). These
  costs are similar on aLIGO. Earlier combined boundary candidate 7 improved these phases but
  was not admitted; it does not establish a gain for this narrower change. Imports and build
  remain about 264 ms and 72 ms large, 264 ms and 38 ms aLIGO in ordinary samples, with import
  outliers. New complete first-run and phase deltas are **unknown**.
- Concrete redundancy: the builder supplies integer linking-function indices, yet the static
  parameter path uses a vmapped lax.switch over the global callable registry. When every link
  selects the same function, all inputs can instead pass directly through vmap of that original
  callable. ParameterLayout now owns a copy of these indices, includes them in its plan key,
  and records a single selected index only when the indices are nonempty, homogeneous and
  match both source and destination counts. Runtime shape and registry bounds checks guard
  dispatch. Mixed links, missing optional metadata, empty links and out-of-range indices retain
  the original switch; its clamping behavior remains available. Invalid builder metadata dtype
  or rank disables the static layout. No global registry mutation is added to simulator code.
- This calls the actual registered callable, never assumes index zero is identity, never
  inspects Python bytecode, and never interprets custom-JVP/custom-VJP calls as primal calls.
  JAX still handles the original function and its derivative rules. Inputs are all read before
  any destination write, preserving parallel-link semantics when sources/destinations overlap.
  The existing documented rebuild requirement now explicitly includes linking-function indices.
  Changing static index arrays without rebuilding is not supported. In-place changes to callable
  definitions after JIT tracing retain the existing global-registry/JIT limitations.
- Scope relative to ee4fea2: only ParameterLayout metadata and its homogeneous-link dispatch
  in simulate.py. Sparse.py is restored exactly to ee4fea2, retiring candidate 10 without rewriting
  Git history. No transposed callbacks, no detector-phase shortcut, no candidate 7 merge, no
  solver/refinement/adjoint changes, no package/launch changes, no workload or fixture edits.
- Added `experiments/notes/overnight-overhead-link-check.py` for the supervisor's fixed environment.
  It compares original vmapped switch and direct dispatch, eager and jitted primal/VJP/JVP
  where supported, at real/complex signed zero and varied finite values. It includes real/complex
  abs, a deliberately nonstandard custom JVP, a deliberately nonstandard custom VJP (reverse
  checks only for that registry), mixed/clamped/empty inputs, a nonidentity entry zero, overlapping
  and repeated source indices, plan-key invalidation, owned index copies and registry growth.
  It prints JAX equation counts, not performance claims. Registry replacement is confined to
  this standalone synthetic diagnostic and restored in finally; no official validation is patched.
- Local checks executed: Python AST syntax, git diff --check, and 3,907 pure-Python cases using
  the extracted dispatcher with a minimal scalar-vmap/switch model passed. These establish
  control-flow/index routing only; they do **not** test NumPy metadata or JAX derivatives.
  Local NumPy/JAX are unavailable and nothing was installed. The new numerical diagnostic,
  both official benchmarks and generalization have **not** run for this candidate.
- Supervisor request: run the synthetic link check, unchanged large and official 101-frequency
  aLIGO benchmarks on the same new SHA, and the 14-case saved-array audit against both ee4fea2
  and the seed/pristine references. Inspect every output and gradient, including any new
  signed-zero/custom-derivative discrepancy. Require independent source review. If promising,
  obtain paired/interleaved fresh-process parent/candidate repetitions with phase/RSS reporting,
  fixed CPU/thread policy and overlap status. No promotion based on a single sample or on
  reductions in synthetic equation count. If the isolated dispatch gain is too small, retire it
  rather than stacking unvalidated changes; next evidence should be the prepared import/build
  profile or the already-requested paired review of candidate 7.
- Inherited unresolved findings stay open: pristine grid signal/gradients 33,161,180/loss;
  uifo_rand1/rand3 log sensitivity differences ~2.04e-4/~5.81e-5; grid finite-difference coordinates
  54,59,63,136,161,163. Earlier aLIGO coordinate checks passed 29/29. Whole-pass custom VJP
  still does not provide JVP/Hessian support. This proposal makes no universal correctness claim.

### Candidate 11 feedback: no observed compilation benefit; retire

- Evaluated SHA **f53dc8ced6ac62bf053010fe28fd80b2037a8502**, job
  **90acd518b01f4f549cbc4f7a9f66c754**; reports grid-1/2/3 and aligo-1/2/3 under
  that request. Both unchanged official benchmarks passed 3/3. No infrastructure failure.
- Large complete fresh-process seconds: **0.834042285, 0.808584839, 0.797800824**;
  median **0.808584839**, range **0.797800824–0.834042285**. aLIGO separately:
  **0.541520478, 0.544266449, 0.553098986**; median **0.544266449**, range
  **0.541520478–0.553098986**. Relative to the unmatched admitted ee4fea2 cohort,
  large median is 7.007 ms slower and aLIGO is 4.289 ms faster. Neither comparison
  establishes a stable improvement; ranges overlap and source review is absent.
- Phase medians (ms), large / aLIGO: imports 264.525 / 264.277; build 72.931 / 37.721;
  forward lower 19.500 / 19.064, compile 33.462 / 33.451, execute 182.421 / 32.775;
  sensitivity lower 25.473 / 26.195, compile 40.653 / 41.129;
  gradient lower 16.645 / 16.720, compile 53.227 / 53.358, execute 88.165 / 14.586.
  These compilation costs are essentially the preceding candidate's scale. No evidence
  supports the proposed switch removal as a useful official-workload optimization.
- Sampled peak RSS bytes: large 510935040, 608702464, 512163840; aLIGO 283422720,
  284921856, 287924224; generalization 705449984. Budget not exceeded; sampling limitations
  and unknown external contention persist. CPU2, one logical CPU, library threads1, x64,
  package flags unchanged, no persistent cache. These are support timings, not ranking samples.
- All 14 generalization cases pass initial-seed tolerances. Official archive hashes match
  candidate 10's; generalization archive hash differs, so do not assert byte-identical arrays.
  Direct saved-array comparison with ee4fea2 is still requested. Maximum absolute official
  seed gradient differences remain 5.686350050e-6 large and 3.637978807e-11 aLIGO.
  Pristine strict review still fails with the inherited signal/gradient/loss and random-case
  discrepancies recorded above. No new tolerance failure is reported; this is not a proof
  of general correctness. Link diagnostic results are absent and remain unexecuted here.
- Decision: preserve f53dc8c, remove its added static dispatch metadata/code from the working
  source, and retain reviewed ee4fea2 as the parent. Do not expand homogeneous dispatch into
  mixed-link grouping or stack it with another experiment.

### Candidate 12: isolate callback output orientation from candidate 7

- Parent simulator source: **ee4fea28c04d482566be16e916b609d7c6a99e5e**. Selective source
  transfer: only the callback-boundary suffix of host_pass.py from preserved candidate 7,
  **1ea70bfbde9bcf42fce836846a4e1e92aee36a3b**, plus removal of the two corresponding
  public-output transposes in _simulate_host_pass. New candidate SHA/jobs pending supervisor.
  No branch reset or Git merge; all failed trials remain in history.
- This is a narrower refinement of measured boundary evidence, not a promotion of candidate 7.
  Candidate 7 combined callback orientation with no-op skipping and had forward lower/compile
  medians 12.002/27.872 ms and gradient lower/compile 11.575/45.929 ms on large, compared with
  roughly 19.5/33.5 and 16.6/53.2 ms now. Its large total median 0.779120542 s had overlapping
  ranges with the incumbent and no source review, so these unmatched observations cannot
  attribute the benefit to transposes alone. Candidate 11 found no useful reduction from
  direct linking-function dispatch; this trial isolates a different boundary operation.
- Mechanism: return carrier and signal in the public (node, batch) orientation from the timed
  NumPy callback, retaining separate (batch, node) callback outputs as backward residuals.
  Transpose incoming carrier/signal cotangents inside the backward callback before passing
  them to the unchanged host_backward. Exact array permutation, no arithmetic or reduction
  changes. Residual arrays and public outputs retain every entry; all three JIT stages remain.
- Tradeoff: forward callback outputs increase from five to seven; NumPy transposes may copy
  arrays, and residual/public orientations may use additional memory and transfer bandwidth.
  The execution and memory costs must be counted against lower/compile savings in complete
  fresh-process runs. No work moves outside the timer, and no cross-evaluation state is added.
  Hypothesis is transferable to arbitrary carrier/signal batch sizes and detector counts.
- Scope checks: host_pass.py prefix through all solver, refinement, assembly, backward math
  and ParameterLayout definitions is byte-identical to ee4fea2. build.py is unchanged; no
  placeholder identity recognition or empty detector-phase scatter skipping is transferred.
  Relative to ee4fea2 only host_pass.py callback boundary and simulate.py return orientation
  change. Candidate 11's homogeneous dispatch is absent.
- Added `experiments/notes/overnight-overhead-callback-check.py`: extracts the actual callback
  boundary functions into an isolated namespace with toy host math and compares them with
  the original boundary under JIT, VJP over every callback input, and sequential vmap. Cases
  include singleton/batched carrier and signal sweeps and multiple detectors. The toy backward
  checks every saved residual and cotangent shape. This does not patch simulator/benchmark
  modules and does not exercise or replace optical solver validation. Runtime execution is
  pending the fixed NumPy/JAX environment; AST syntax and source-prefix checks passed locally.
- Request supervisor synthetic boundary check, both unchanged full official benchmarks on the
  exact same new SHA, saved outputs/full gradients against parent and seed, the 14-case
  generalization review, and independent source review. If promising, require interleaved
  parent/candidate fresh-process confirmation, separate large/aLIGO medians and ranges,
  phase/RSS accounting and job-overlap status. No gain is claimed before those results.
- All inherited pristine disagreements and six unresolved grid finite-difference coordinates
  remain open. The whole-pass custom VJP still does not support JVP/Hessians. If this isolated
  boundary trial fails to improve robustly, restore ee4fea2 and obtain the prepared import/build
  attribution rather than another permutation of unconfirmed boundary changes.

### Candidate 12 feedback and boundary-search handoff

- Evaluated SHA **3f436ce6531bf90e3e5ec864321e2c760c76911c**, evaluation
  **e9963be7b002421f93f2c16c311729ca**. Large jobs grid-1/2/3; official aLIGO jobs
  aligo-1/2/3. Both unchanged official benchmarks passed all three fresh runs.
- Large complete first-run seconds: **0.828883981, 0.795384802, 0.799623925**;
  median **0.799623925**, range **0.795384802–0.828883981**. Official aLIGO separately:
  **0.547551330, 0.542284621, 0.540851843**; median **0.542284621**, range
  **0.540851843–0.547551330**. Relative to the unmatched admitted ee4fea2 cohort,
  observed median reductions are 1.954 ms large and 6.271 ms aLIGO. The large reduction
  misses the team selection threshold and ranges overlap. No confirmed improvement.
- Phase medians (ms), large / aLIGO: imports 265.410 / 264.915; build 73.323 / 37.897;
  forward lower 18.978 / 18.355, compile 33.250 / 33.419, execute 179.539 / 32.752;
  sensitivity lower 25.997 / 26.078, compile 39.531 / 41.539;
  gradient lower 16.483 / 16.230, compile 51.563 / 53.265, execute 87.427 / 14.718.
  Thus isolated transpose transfer did not reproduce candidate 7's roughly 26 ms combined
  compilation-phase reduction. Relative to candidate 11's unmatched phase medians, the six
  lowering/compile medians sum to about 3.2 ms less large and 1.0 ms less aLIGO; this is not
  a controlled causal comparison or an end-to-end timing result. Grid-1 import was 291.325 ms,
  while grid-2/3 were 265.410/263.680 ms; external contention and its causes remain unknown.
- Sampled peak RSS bytes: large **524574720, 524943360, 532213760**; aLIGO
  **279805952, 287674368, 293363712**; generalization **896102400**. No budget exceedance
  or infrastructure failure. No controlled memory reduction is established. CPU2, one logical
  CPU, library threads one, x64 and permitted package flags unchanged; no persistent cache.
- All 14 extra generalization cases pass initial-seed tolerances; pristine comparisons remain
  failing. Official archive hashes match recent candidates. Generalization archive hash is
  ddac9c5749501202f1dab52420e3bd970d41227df145cd77889bb93028f689b5; its differing archive
  hash alone is not a per-array difference diagnosis. No new tolerance failure is reported.
  Official seed gradient maximum absolute differences remain 5.686350050e-6 large and
  3.637978807e-11 aLIGO. The requested synthetic callback diagnostic and direct ee4fea2
  saved-array comparison are not present in feedback; do not mark them passed. Independent
  source review is absent. Official PASS is not a numerical correctness certificate.
- Decision: retire the transpose-only performance proposal. Restored host_pass.py and
  simulate.py from **ee4fea28c04d482566be16e916b609d7c6a99e5e**; all ten simulator modules
  verified byte-identical to that reviewed parent. No Git reset/commit/merge was performed.
  Candidates 10, 11 and 12 (and earlier trials) remain in branch history with their failures.
  The callback diagnostic is historical and must be run against candidate 12's exact source,
  since restored ee4fea2 does not define its transposed callback wrappers.
- Stop this sequence of implementation variants. Candidates 10/11/12 yielded large medians
  0.801084740 / 0.808584839 / 0.799623925 s in separate cohorts, none a confirmed improvement.
  Homogeneous linking dispatch and callback transposes have not provided compelling phase
  evidence alone. Candidate 7 remains unadmitted, not a new baseline. Do not merge its remaining
  no-op shortcuts on the assumption that subtraction of unmatched timings proves their benefit.
- Concrete next experiment for the supervisor: run the existing
  `experiments/notes/overnight-overhead-profile.py` on restored ee4fea2 source, with each
  caller's actual setup, optimization pairs and sweep values, in fresh fixed-environment
  processes for large, official aLIGO and one other setup. Return full top-self/top-cumulative
  import/build tables, not just total wall time. Separately collect the unchanged harness's
  import-time tree so benchmark-owned imports are counted. These are instrumented attribution
  runs, not clean official timing samples. The exact CLI and omitted-input caveat are recorded
  in the earlier profiling section. Do not run the historical candidate checks against the
  restored parent as though their implementation were still present.
- Use that attribution to select a distinct hotspot with material measured cost before another
  simulator edit. If no such hotspot appears, retain ee4fea2 honestly. Alternatively, obtain the
  already requested independent review/direct parent array audit/interleaved timings for exact
  candidate 7; that is a validation task, not permission to promote it based on old medians.
- Unresolved findings remain: pristine grid signal/gradients 33,161,180/loss; uifo_rand1/rand3
  logarithmic sensitivity discrepancies ~2.04e-4/~5.81e-5; grid finite-difference coordinates
  54,59,63,136,161,163. Earlier aLIGO coordinate checks passed 29/29. Whole-pass custom VJP
  remains first-order reverse mode only, without JVP/Hessians. Tolerances unchanged.
- Handoff: no new optimization candidate for evaluation. Restored parent and recorded evidence
  are ready for supervisor bookkeeping. Lane/branch overnight-overhead-v1; deadline remains
  **2026-11-22 09:27:44 UTC**, epoch1795339664. This ends the boundary hypothesis, not the
  authorized campaign. Profiling and new clean paired timings remain outstanding.


### Candidate 13: initialize augmented identities in place

- Resumed at the supervisor's explicit request for a concrete next experiment. Candidate SHA
  and evaluation/job identifiers are pending supervisor commit and submission. Branch HEAD
  at preparation is a24a97975527c130cd61f7032157f73c6bc1157c. Scientific comparison parent is
  **ee4fea28c04d482566be16e916b609d7c6a99e5e**, not the retired candidate 12. Relative to that
  reviewed parent, the entire simulator delta is **two statements in build.py**. The pending
  host_pass.py/simulate.py diff against branch HEAD restores the parent and removes candidate
  12's transposed callbacks; no solver/refinement/adjoint mathematics changes.
- Distinct conservative mechanism: the builder first allocates zero-filled complex augmented
  carrier/signal matrices, then creates square complex identity temporaries and copies their
  entire contents into the already-zero left blocks. Replace those two assignments with
  np.fill_diagonal(matrix, 1). A rectangular (n, n+1) matrix has exactly n diagonal entries;
  the right-hand-side column stays zero, including empty/singleton systems. No reduction,
  arithmetic ordering, indexing metadata, physical parameter or derivative path changes.
- Actual redundant operation established by source: two np.eye allocations and two dense
  left-block copies. For carrier order C and signal order S, this avoids 16*(C*C+S*S) bytes
  of temporary complex128 array capacity, and replaces C*C+S*S destination element writes
  with C+S writes. This is an allocation/work count, NOT a measured RSS or time saving;
  allocator reuse, lazy zero pages and later matrix writes can affect observed memory/time.
  Dimensions come solely from the supplied setup. All dense public matrices remain allocated
  with the original shapes and dtype and are fully populated as before. No caches are added.
- Cost context: most recent evaluated candidate 12 had build phase medians 73.323 ms large /
  37.897 ms official aLIGO; import medians 265.410 / 264.915 ms and summed six lower/compile
  phase medians about 185.8 / 188.9 ms. Those measurements describe candidate 12, not this
  candidate or a contemporaneous parent. Only build/allocation work is targeted here. There
  is no measured attribution of the identity allocation cost; benefit could be below noise.
  The outstanding supervisor profiling request remains useful and has not been run locally.
- Search direction: candidates 10/11/12 remain retired and preserved. This is neither another
  callback/signature permutation nor a repetition of candidate 4's Python bookkeeping or
  candidate 10's dense position-map rewrite. It reduces implementation complexity without
  replacing any structural metadata representation. The small source-proven redundancy is
  sufficient to submit a conservative experiment, not sufficient to claim a speedup.
- Local checks: AST parsing passed for all ten simulator modules. Verified exact source identity
  with ee4fea2 for the other nine modules, and verified the build.py delta consists only of
  the two expected statement replacements. Pure Python rectangular-index models passed for
  all orders 0 through 128 (129 cases). This models diagonal positions, not NumPy execution.
  Local NumPy/JAX are unavailable; no runtime simulation or benchmark was launched. Do not
  mark a NumPy/JAX runtime check as passed.
- Evaluation request: supervisor commits this exact candidate, runs both unchanged full
  official benchmarks and compares every saved output and gradient to ee4fea2 and the seed;
  include the existing generalization cases and independent source review. If the build/total
  reduction appears promising, obtain paired interleaved fresh-process parent/candidate runs
  on matching CPU/thread policy, with separate large/aLIGO samples, medians, ranges, phases,
  memory and overlap status. No acceptance from a small warm allocation test. If gain is
  unconfirmed, retain ee4fea2 and use the requested profile before selecting another hotspot.
- Inherited unresolved pristine-reference signal/gradient/loss disagreements, uifo_rand1/rand3
  sensitivity errors, six grid finite-difference coordinates and first-order-only custom VJP
  support remain exactly as recorded above. No tolerance or validation policy changes.
- Prepared before the unchanged 2026-11-22 09:27:44 UTC deadline. Candidate is ready for
  supervisor evaluation; no performance or numerical outcome is claimed yet.


### Candidate 13 feedback: no confirmed gain

- SHA **7f9098048a796aba7bff133bb40cecb75a98a7fe**, evaluation
  **3174de049b084289b49bd2d4264e87a8**, jobs grid-1/2/3 and aligo-1/2/3.
  Both unchanged official benchmarks passed all three fresh processes.
- Large samples: **0.822865605, 0.800564464, 0.809530795** seconds; median
  **0.809530795**, range **0.800564464–0.822865605**. Official aLIGO separately:
  **0.549647892, 0.550030932, 0.546282323**; median **0.549647892**, range
  **0.546282323–0.550030932**. Against the unmatched admitted ee4fea2 cohort these
  medians are 7.953 ms / 1.093 ms higher. No confirmed improvement, no promotion.
- Build samples large **74.242, 72.503, 72.270 ms**, median72.503; aLIGO
  **38.780, 38.425, 37.543 ms**, median38.425. Relative to candidate12's separate
  cohort, build medians differ by -0.820 / +0.528 ms: no stable evidence of benefit.
  Other phase medians large/aLIGO ms: imports266.190/268.248; forward lower19.515/19.353,
  compile33.561/33.727, execute181.849/33.948; sensitivity lower25.782/26.292,
  compile39.889/41.548; gradient lower17.172/16.687, compile51.891/53.406,
  execute85.733/14.395. These are observational cohorts, not causal paired deltas.
- Sampled peak RSS bytes large **516026368, 525770752, 503201792**; aLIGO
  **280772608, 304865280, 308436992**; generalization **988848128**. No budget
  exceedance or infrastructure failure. CPU2/one logical CPU/library threads1/x64,
  permitted package flags and no persistent cache unchanged. External contention unknown.
  Reduced theoretical temporary allocation does not establish a measured RSS improvement.
- All 14 generalization cases pass initial-seed tolerances, including all saved physical
  outputs/gradients; pristine-reference comparisons still fail. Official archive hashes
  unchanged from candidate12. Generalization archive2617a00ec9ccafd5ac149b331c5bd8663e1e2075fa38a2150608c682a4d4958f;
  no direct parent byte comparison supplied. Initial-seed gradient maximum differences
  remain5.686350050e-6 large/3.637978807e-11 aLIGO. No newly reported tolerance failure.
  Independent review absent. These passes do not settle inherited pristine disagreements.
- Retired candidate13 and restored build.py exactly to ee4fea2; failed revision remains
  in history. Do not continue tweaking dense identity allocations. Profiling remains pending.

### Candidate 14: slice replacement for consecutive static parameter destinations

- Candidate SHA and jobs pending supervisor. Scientific parent **ee4fea28c04d482566be16e916b609d7c6a99e5e**.
  Only simulate.py differs from that parent; build.py restoration retires candidate13.
- Mechanism: _static_set already receives concrete, unique, in-bounds 1-D destinations.
  If those destinations form a consecutive increasing run (including a single destination),
  express replacement with lax.dynamic_update_slice; otherwise retain the original lax.scatter.
  Empty destinations keep the scatter path. Same update dtype conversion and all updates
  retained. No setup names, dimension thresholds, physical values or callable identities are
  inspected. This is a narrower refinement of static indexing, distinct from the retired
  callback-transpose and homogeneous-linking-dispatch proposals.
- The replacement is exact for every qualifying index sequence: destination[start:start+k]
  receives the k updates in order. Its transpose zeros that slice in the input cotangent and
  extracts it for the update cotangent. Equal-valued writes and zero parameters still retain
  their derivative paths. In particular, no identity-function/no-op recognition is introduced.
  No host plan state, solver or adjoint mathematics changes, no new cache, no workload/stage
  changes. Existing requirement to rebuild after changing static index arrays remains.
- Cost hypothesis: avoid scatter lowering/code generation and its reverse scatter/gather work
  for slice-shaped updates. Candidate13's forward lower+compile medians sum to roughly53 ms
  and gradient lower+compile to69 ms in large; only an unknown portion is attributable to
  this indexing. Added trace-time NumPy contiguous-index inspection is included in the timer.
  Build/import/solve gains are not claimed. Compilers may already optimize this well; reject
  if no repeat-supported complete first-run improvement.
- Added experiments/notes/overnight-overhead-slice-check.py for the supervisor's fixed
  environment: extracts the actual helper into a separate namespace, compares original
  scatter and candidate under JIT primal/JVP/VJP for both array inputs, checks primitive
  selection, covers empty/singleton/full/interior/irregular/reversed index sequences and
  real/complex updates, signed zero and updates equal to existing values. 56 cases planned.
  This is synthetic helper coverage only, not optical solver coverage or a benchmark.
  Local NumPy/JAX unavailable: runtime check remains UNEXECUTED; syntax/scope checks only.
- Request this focused diagnostic, both unchanged official benchmarks on the new exact SHA,
  all saved output/gradient comparisons to parent and seed, existing generalization suite and
  independent source review. Require paired fresh-process parent/candidate confirmations,
  separate large/aLIGO samples/medians/ranges, phase/RSS and overlap accounting before
  promotion. No gain or numerical pass is claimed at preparation.
- Inherited pristine signal/gradients33,161,180/loss disagreements, uifo_rand1/rand3 sensitivity
  errors and grid FD54,59,63,136,161,163 remain unresolved. Prior aLIGO FD29/29 confirmed.
  Helper JVP coverage does not imply whole-pass JVP/Hessian support; that remains unsupported.
- If this indexing refinement is unhelpful, restore ee4fea2 and prioritize the outstanding
  import/build profile or exact candidate7 review/paired-evidence request; do not stack
  unconfirmed variants. Deadline unchanged:2026-11-22 09:27:44 UTC.


### Candidate 14 feedback and end of speculative small-variant sequence

- Evaluated SHA **8e111f16fe84ed923db379bd4221bf214066858c**, evaluation
  **aead632620a9464498344b59d10b8638**. Large jobs grid-1/2/3, official aLIGO
  jobs aligo-1/2/3. All six unchanged official fresh-process runs passed.
- Large samples **0.829137923, 0.806818409, 0.807451569** seconds; median
  **0.807451569**, range **0.806818409–0.829137923**. Official aLIGO samples
  **0.543226795, 0.544487456, 0.551004561**; median **0.544487456**, range
  **0.543226795–0.551004561**. The large median is 5.874 ms higher than the
  unmatched admitted ee4fea2 cohort, while aLIGO is 4.068 ms lower. Neither is
  controlled paired evidence. Ranges overlap the incumbent; no confirmed improvement.
- Phase medians in milliseconds (descriptive only):

  | Phase | Large | aLIGO |
  | --- | ---: | ---: |
  | imports | 271.428 | 264.573 |
  | build | 73.354 | 38.926 |
  | forward_lower | 19.899 | 19.402 |
  | forward_compile | 33.555 | 33.347 |
  | forward | 183.765 | 32.717 |
  | sensitivity_lower | 25.621 | 26.720 |
  | sensitivity_compile | 40.063 | 41.774 |
  | gradient_lower | 16.701 | 16.642 |
  | gradient_compile | 51.743 | 52.316 |
  | gradient | 86.383 | 14.681 |

- Compared with candidate13's separate cohort, forward-lower+compile and gradient-lower+
  compile sums of phase medians decrease only about0.242 ms large and1.466 ms aLIGO.
  This does not demonstrate useful compilation savings. Build spans69.799–77.770 ms large,
  and imports span267.089–294.380 ms; timing variability cannot be assigned to this edit.
  No instrumented primitive/HLO result or synthetic slice-check result was returned.
- Sampled process-group peak RSS bytes: large **552873984, 505016320, 623030272**;
  aLIGO **281092096, 293494784, 281124864**; generalization **782561280**. No budget
  exceedance or infrastructure failure. CPU2, one logical CPU, library threads1, x64,
  package flags and no persistent cache unchanged. Other-host contention not excluded.
- Every official saved-array category passes initial-seed tolerances, with identical official
  archive hashes to candidate13. All14 generalization cases pass initial-seed tolerances.
  Generalization archive65522650411773be25a7ced683ae0456e074c3f454f24220c8f27e39fb8ba05f;
  the self-comparison archive match is not evidence of bitwise equality to the initial seed.
  No new tolerance failure is reported. Official gradient maximum seed differences remain
  5.686350050e-6 large and3.637978807e-11 aLIGO. Direct ee4fea2 array comparison and
  independent source review were not supplied. Pristine comparisons remain failing.
- Decision: retire candidate14. Restored simulate.py exactly from reviewed
  **ee4fea28c04d482566be16e916b609d7c6a99e5e** and verified all ten simulator modules
  byte-identical to that parent. No history reset, commit or merge. Candidate14 and its
  diagnostic remain preserved; the slice-check must be run on candidate14, since its
  primitive-selection assertions intentionally do not hold on the restored scatter helper.
- Candidates12/13/14 large medians were0.799623925/0.809530795/0.807451569 s in separate
  cohorts; none was a repeat-supported improvement. Candidate13 reduced source complexity
  but no measured benefit; candidate14's narrower indexing did not establish a compilation
  improvement. End speculative small implementation variants here, retaining ee4fea2.

### Required next evidence for this lane

- First choice: supervisor-run import/build attribution on ee4fea2 using the existing
  experiments/notes/overnight-overhead-profile.py. Use the unchanged caller's actual setup,
  optimization pairs, changing pairs and changing values for large and official101-frequency
  aLIGO, plus one unrelated optical setup. Its CLI has been inspected; required setup flag is
  --setup-json, optional flags --optimization-pairs-json, --changing-pairs-json and
  --changing-values-json (the last two must be supplied together), and --top 60. Supply the
  checkout through PYTHONPATH, a fresh fixed-environment process, and the existing resource
  policy. Paths/serialized caller inputs are coordinator-owned; no new fixture is authorized
  by this note. Omitting inputs profiles public defaults and must not be called official.
- Return top-self and top-cumulative tables for simulator_imports, setup_from_data,
  prepare_sweep and run_build_step, plus an import-time tree covering the actual benchmark's
  imports (the helper alone does not include all benchmark-owned imports). These diagnostic
  runs are not clean official timing samples and cannot replace either official benchmark.
  The managed agent did not launch them or change evaluator policy. No profile has been
  received despite prior requests; select the next implementation only after attribution.
- Alternative evidence task, already requested: independent source review and direct parent
  output/gradient comparison for candidate7 **1ea70bfbde9bcf42fce836846a4e1e92aee36a3b**,
  then five interleaved fresh runs per revision per official setup against ee4fea2 if review
  permits. That combined boundary candidate had the strongest observed phase reduction, but
  remains unadmitted with overlapping ranges. No silent restoration, merge or promotion.
- Inherited open findings remain explicit: pristine grid signal/gradients33,161,180/loss;
  uifo_rand1/rand3 log-sensitivity errors~2.04e-4/~5.81e-5; unresolved grid FD54,59,63,
  136,161,163. Prior aLIGO FD29/29 passed. Whole-pass customVJP does not support JVP/Hessians.
  No tolerance changes or universal-physics claim.
- Handoff at2026-11-22 around03:18 UTC: ready_for_evaluation=false, stop=true for this
  hypothesis sequence, not for the authorized campaign. Deadline remains09:27:44 UTC,
  epoch1795339664.0. Lane/branch overnight-overhead-v1. Restored reviewed source and all
  failed-trial evidence are preserved for the supervisor; no new optimization candidate.

### Candidate15 — isolate structurally empty detector-phase work (2026-11-22 03:20 UTC)

- New supervisor instruction requests one concrete experiment despite the prior stop
  handoff. Candidate14 remains retired; its measured results above are unchanged.
  This delta uses reviewed simulator parent **ee4fea28c04d482566be16e916b609d7c6a99e5e**.
  Branch history/HEAD remains supervisor-owned; candidate SHA and job IDs pending.
- Mechanism: the static parameter-layout path currently traces an empty phase gather,
  radians/exponential and scatter-multiply when both phase index arrays are empty.
  Mark only that structurally empty case with an internal None sentinel and omit its
  phase scatter. Nonempty layouts, including all phase values currently zero, execute
  exactly the original expressions. Require BOTH index arrays empty; inconsistent
  nonempty metadata does not enter this shortcut. Generic non-static paths are unchanged.
  This removes no design variables, physical outputs, differentiation contributions or
  JIT stages. No solver/refinement/adjoint changes, answer reuse or launch changes.
- Why this experiment: combined boundary candidate7 had observed forward/gradient trace
  and compile reductions, while its isolated callback-transpose candidate12 did not
  establish a meaningful gain. The empty-phase part has not been evaluated alone.
  Candidate11 retained the link gather/scatter and therefore did not isolate candidate7's
  full identity-link shortcut either. This experiment tests ONLY phase emptiness, leaving
  identity linking and callback layouts unchanged. Candidate7 is unadmitted; its numbers
  are motivation for attribution, not evidence this isolated change is faster.
- Cost target: forward and gradient tracing/compilation. Candidate14 observations provide
  separate phase medians: large forward lower/compile19.899/33.555 ms and gradient
  lower/compile16.701/51.743 ms; aLIGO19.402/33.347 and16.642/52.316 ms. Imports/build
  were271.428/73.354 ms large and264.573/38.926 ms aLIGO. No candidate15 timing exists;
  the removed primitives may already be eliminated by lowering and give no total gain.
- Local checks passed: Python AST parsing, exact AST equality of nonempty phase expression
  and scatter against ee4fea2, and byte identity of every other simulator module to ee4fea2.
  An initial source-check assertion selected the generic phase assignment by AST traversal
  order; selecting the static-layout assignment correctly resolved that check. This was
  a diagnostic selection error, not an executed simulator failure.
- Prepared **experiments/notes/overnight-overhead-empty-phase-check.py** for the supervisor.
  It extracts the actual phase code and compares JIT primals plus VJPs for parameter row
  and complex selection vectors against the unconditional original path, in eight small
  synthetic cases: empty layout, one/multiple destinations, repeated parameter references,
  irregular placement, zero/nonzero phases and a zero selector. It checks absence of phase
  primitives only for empty layouts and their retention for nonempty layouts. Local JAX/
  NumPy unavailable: runtime checks are UNEXECUTED, no numerical validation claimed.
- Request this diagnostic, both unchanged official benchmarks on the new exact SHA, all
  output/gradient comparisons against ee4fea2 and initial seed, existing14 generalization
  cases, and independent source review. If promising, obtain matching interleaved fresh
  parent/candidate samples rather than promoting against old unmatched timings. Preserve
  phase breakdowns/RSS and report contention status. Import/build attribution remains
  useful; no profile or direct parent-array report has arrived.
- Inherited pristine and finite-difference disagreements listed above remain unresolved;
  first-order reverse support only. Candidate15 ready for evaluation, not promotion.
  Next decision: if empty-phase removal offers no stable reduction, retire this isolated
  mechanism; inspect actual lowered primitive evidence or import/build profiles before
  further implementation changes. Deadline remains09:27:44 UTC, epoch1795339664.0.

### Candidate15 feedback — preserve exact source for confirmation (03:24 UTC)

- Evaluated SHA **2e50e7cffc8c7feb5ae53dc770e26cbb45250ab8**; request
  **b699b389623a46c98a1e34c803ca18d8**, jobs grid-1/2/3 and aligo-1/2/3 under that
  request. Both unchanged official benchmarks passed in all three fresh processes.
  No confirmed improvement or source review: admission reasons are requires_source_review
  and large_first_run_ranges_overlap_requires_paired_evidence. ee4fea2 remains admitted best.
- Large complete first-run seconds: **0.8227882608771324, 0.7784748841077089,
  0.7853874359279871**; median **0.7853874359279871**, range
  **0.7784748841077089–0.8227882608771324**. Against the old unmatched ee4fea2 median,
  observed difference16.190 ms (2.020%); not a confirmed gain. Keep the slower first
  sample: its imports296.661 ms exceed the other two265.328/264.786 ms, but imports
  are part of the required total and cannot be excluded or normalized away.
- Official101-frequency aLIGO seconds: **0.5328888855874538, 0.5305512081831694,
  0.5279352385550737**; median **0.5305512081831694**, range
  **0.5279352385550737–0.5328888855874538**. Difference from old unmatched parent
  median18.004 ms (3.282%); separate transfer evidence, never a combined score.
- Phase medians in milliseconds, large / aLIGO:

  | phase | large | aLIGO |
  | --- | ---: | ---: |
  | imports | 265.328 | 262.744 |
  | build | 73.325 | 37.717 |
  | forward_lower | 14.091 | 13.617 |
  | forward_compile | 30.738 | 30.869 |
  | forward | 182.602 | 32.423 |
  | sensitivity_lower | 25.595 | 26.115 |
  | sensitivity_compile | 39.758 | 41.184 |
  | gradient_lower | 12.989 | 13.046 |
  | gradient_compile | 51.117 | 52.595 |
  | gradient | 84.548 | 14.675 |

- Compared with candidate14's separate cohort, forward lowering is about5.808/5.785 ms
  lower and gradient lowering3.712/3.596 ms lower (large/aLIGO). Forward compilation
  falls2.817/2.478 ms; gradient compilation falls0.626 ms large and rises0.279 ms aLIGO.
  These repeated phase observations support this mechanism more clearly than the previous
  slice/allocation trials, but they are not paired measurements against ee4fea2. Do not
  attribute execution/import fluctuations to this change. No lowered-IR diagnostic supplied.
- All saved official array categories and all14 generalization cases pass initial-seed
  tolerances. Official archives match recent candidates; gradient maximum seed differences
  remain5.686350050e-6 large and3.637978807e-11 aLIGO. Generalization archive is
  **4cda4a02afc191bc87b2e7534024496a464c73d34a73a715c1a217f9d52e0171**; differs from
  candidate14's archive. All supplied initial-seed checks pass, but no direct parent archive
  comparison is supplied, so no bitwise-equality or universal correctness assertion.
  Pristine disagreements persist: grid signal/gradients33,161,180/loss; custom uifo_rand1/3
  log-sensitivity errors~2.04e-4/~5.81e-5 and associated gradients. Grid FD54,59,63,136,161,
  163 remain unresolved; prior aLIGO FD29/29 confirmed. Whole-pass JVP/Hessians unsupported.
- Sampled peak RSS bytes: large **622108672, 545058816, 504066048**; aLIGO
  **282267648, 294612992, 290766848**; generalization **813125632**. No budget exceedance
  or infrastructure failure. CPU2, one logical CPU, library threads1, double precision,
  package flags and no persistent cache unchanged. Other-host contention not excluded.
- Decision: retain candidate15 UNMODIFIED for confirmation, not promotion. Do not stack
  another speculative boundary edit onto it. This changes the next task from implementation
  variants to evaluating the existing focused hypothesis. All failed trials remain in history.
- Supervisor request: independently review the exact ee4fea2-to-2e50e7c delta; run the
  prepared empty-phase synthetic check, including nonempty zero-phase derivatives, and
  compare every parent/candidate physical array and gradient directly. If review permits,
  run five interleaved fresh-process repetitions per revision per official setup for
  **ee4fea28c04d482566be16e916b609d7c6a99e5e** and
  **2e50e7cffc8c7feb5ae53dc770e26cbb45250ab8** with matching resource policy. Return
  every sample, phase breakdown and overlap information. Existing three samples alone
  do not resolve the overlapping large ranges. This is a repeat request for the exact
  candidate, not a new simulator submission or an instruction to relax admission policy.
- Synthetic runtime remains unreported; local source checks only. No simulator edits,
  benchmarks, commits, network calls or agent spawning in this feedback turn. Deadline
  remains09:27:44 UTC. ready_for_evaluation=true requests confirmation of the EXISTING
  candidate SHA; no new simulator SHA is needed for this experiment.

### Candidate16 — isolate exact identity-link elimination

- The supervisor returned the same candidate15 receipt and requested an evaluable simulator
  change instead of another repeat-only handoff. No additional timing or source review has
  arrived. Candidate15 remains a promising, unconfirmed experiment preserved at
  **2e50e7cffc8c7feb5ae53dc770e26cbb45250ab8**; its paired-confirmation request remains open.
- Source baseline for this distinct isolated trial is reviewed
  **ee4fea28c04d482566be16e916b609d7c6a99e5e**. Restored its simulate.py content before
  applying this change; no reset, commit or lost history. Candidate15's phase shortcut is
  NOT included. No callback-transpose variant, slice update or solver change is included.
- Builder placeholder becomes a named exact `_identity_link` instead of an anonymous
  identity lambda. The existing dummy branch index remains unchanged. In the static-layout
  path, `_static_link` bypasses gather/switch/scatter only if every registered branch is
  this exact function object, the source and destination arrays are identical, and the
  dynamic function-index array has the expected shape and integer dtype. Any custom branch,
  even unused, or different destinations retains the original linking operations.
- This deliberately conservative condition does not freeze dynamic branch-index VALUES:
  all possible branches, including lax.switch's clamped choices, are identical. No function
  is inferred to be identity from its name, bytecode or current numerical output. No
  phase/optical parameter is suppressed because it currently equals zero. Existing layout
  bounds/unique-destination checks remain in force; global function-registry mutation has
  the same trace/retrace limitations as the original lax.switch branch list.
- Distinction from candidate11: that trial specialized homogeneous branch dispatch but kept
  the parameter gather/scatter. Candidate16 removes that entire provable identity update.
  Candidate7 included a broader identity-link shortcut alongside empty phases and callback
  transposes. Candidate15 isolated phase emptiness and observed about9.4 ms less combined
  forward/gradient lowering than candidate14 in separate cohorts. Testing identity linking
  alone can attribute the remaining candidate7 reduction without silently combining trials.
  Target is forward/gradient trace and compile time; new candidate has no timing evidence.
  Full first-run cost must count the small Python registry/index checks too.
- Local validation: AST parsing passed; four stdlib-only tests execute the actual helper
  with stand-in operations and verify identity/multiple-identity eligibility, non-self
  destination fallback, and custom-branch fallback. These are control-flow checks, not JAX
  numerical validation. Other simulator modules match ee4fea2; only build.py/simulate.py differ.
- Prepared **experiments/notes/overnight-overhead-identity-check.py** for fixed-environment
  execution. Twelve synthetic JIT primal/VJP comparisons cover real/complex rows, signed
  real zero, current zero values, dynamic/clamped branch indices, repeated registered exact
  identities, non-self destination permutations, custom linear branches and an anonymous
  identity function that must keep the generic path. Runtime UNEXECUTED locally (no JAX).
- Candidate SHA/job IDs pending. Request both unchanged full official benchmarks, direct
  parent and initial-seed array/gradient comparisons, all14 generalization cases, the
  synthetic check and independent source review. Measure candidate16 alone; do not merge
  with candidate15 without separate review and exact combined re-evaluation. If no meaningful
  effect appears, retire this isolated mechanism and prefer the existing candidate15
  confirmation/import-build attribution tasks over further speculative indexing changes.
- All inherited pristine-reference discrepancies and unresolved finite differences above
  remain visible. No change to tolerances, three JIT stages, physical workload, compiler
  settings or first-order-only custom-VJP scope. Deadline09:27:44 UTC unchanged.

### Candidate16 feedback and end of boundary-variant sequence

- Evaluated SHA **479a5c1283c700d423bf369e5eabbaee113d5d53**, dual-official request
  **7edb79c9069548d188dd96841cda457e** (grid-1/2/3 and aligo-1/2/3).
  Both official benchmarks passed all three fresh processes. All14 generalization cases
  pass the initial-seed comparison tolerance. Independent source review remains absent;
  confirmed_improvement=false. No infrastructure failure or memory-budget exceedance.
- Large samples seconds: **0.8216858301311731, 0.7836411092430353,
  0.7903760205954313**; median **0.7903760205954313**, range
  **0.7836411092430353–0.8216858301311731**.
- Official aLIGO samples seconds: **0.5373751949518919, 0.5320959351956844,
  0.5331667233258486**; median **0.5331667233258486**, range
  **0.5320959351956844–0.5373751949518919**.
  Separate historical parent medians differ by11.202 ms large and15.388 ms aLIGO;
  these are unmatched observations, not confirmed improvements. Large ranges overlap.
- Phase medians ms (large / aLIGO): imports265.631 /264.571; build74.149 /37.870;
  forward lowering18.199 /17.737, compilation30.387 /29.976, execution181.632 /32.703;
  sensitivity lowering25.580 /26.077, compilation40.400 /41.289;
  gradient lowering15.739 /15.704, compilation46.969 /48.430, execution85.272 /14.315.
  Versus separate candidate14 observations, gradient compilation is lower by about
  4.774 /3.886 ms. This supports a phase-level hypothesis only: it is neither a paired
  comparison to ee4fea2 nor proof of a total-time gain. Candidate15 lowers tracing more;
  candidate16 lowers gradient compilation more. Do not automatically combine them.
- Sampled process-group peak RSS bytes: large511279104 /478326784 /611266560;
  aLIGO323584000 /294666240 /314937344; generalization927752192. Sampling can miss
  brief peaks. AMD EPYC9334, CPU2, one logical CPU and library threads1, x64, no
  persistent compilation cache; inherited package flags unchanged. External contention
  was not excluded; ranking_eligible=false. No claim about organizer ranking medians.
- Full official output archive hashes match the preceding candidate's saved archives:
  large112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5,
  aLIGO9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195.
  Generalization archive aa376d173e2d8d21151b22c0159806058aca2a59010900f6224322258605cf7f.
  The receipt's self-comparison is not evidence of byte identity to the seed. Initial-seed
  tolerance checks pass; pristine checks remain false. Official grid maximum gradient
  difference from seed is5.686350050382316e-6; aLIGO3.637978807091713e-11.
  Pristine grid signal/gradient33,161,180/loss disagreements, uifo_rand1/rand3 sensitivity
  disagreements and six unresolved grid finite differences remain open. Prior additional
  aLIGO29/29 coordinate checks remain distinct. Whole-pass VJP is first-order reverse only.
- Decision: end this speculative boundary-variant sequence. Candidate16 has not established
  a repeat-supported full-run gain, and the requested synthetic JAX run/source review is
  still unreported. Restore **build.py and simulate.py to ee4fea28c04d482566be16e916b609d7c6a99e5e**
  in this worktree; all simulator Python modules are verified byte-identical to that reviewed
  parent. No history reset or commit was made. Candidate15 and16 implementations, notes and
  diagnostic scripts remain preserved in history; their evidence is not discarded.
- Next task is evidence collection through the supervisor, not another boundary variant:
  independent review and prepared synthetic checks on exact candidate15 and16 revisions;
  direct parent/candidate physical-array comparisons; then five interleaved fresh runs per
  revision per official setup against ee4fea2 if review permits. Separately obtain the
  already-prepared import/build profile on supplied setups before proposing another builder
  change. Neither paired confirmation nor profiling has been supplied yet.
- ready_for_evaluation=false: restored parent does not warrant a duplicate candidate job.
  stop=true ends this hypothesis sequence, not the authorized overnight campaign. Supervisor
  may continue the campaign with the evidence tasks above. Deadline09:27:44 UTC unchanged.

### Candidate17 — index parameter names once per builder call

- Supervisor resumed after the sequence-ending handoff and requested a concrete next
  experiment. Keep the prior restoration to reviewed simulator parent
  **ee4fea28c04d482566be16e916b609d7c6a99e5e**. Candidate17 changes only build.py relative
  to that parent; it includes neither candidate15 nor16 nor their combinations.
- Distinct mechanism: `pairs_to_arrays` called `parameter_names.index` for every optimized
  and swept parameter (four call sites, including grouped optimization pairs). Each call
  restarted a linear search of the same unchanged name list. Build a local first-position
  dictionary once, then resolve these queries from it. For N names and Q queries this
  changes worst-case search work from O(NQ) to expected O(N+Q), with O(N) temporary memory.
  The table is rebuilt for each call and is never persisted or shared across setups.
- Only exact Python lists of exact strings use the dictionary. `setdefault` preserves the
  first occurrence for duplicate names (including the builder's empty-name placeholders).
  Missing names raise the same ValueError/message: optimization queries remain ignored by
  their existing catch, while invalid sweep queries still fail. Tuples, custom containers,
  string subclasses and non-string/unhashable items keep the original `.index` behavior.
  Calls with no optimized or changing pairs skip table construction. Instruction order,
  optimized-value indices and all array construction are unchanged.
- Target is setup/build, not JAX compilation or solver execution. Latest candidate16 phase
  medians were74.149 ms large and37.870 ms official aLIGO, but these include all build work
  and do NOT measure name-search cost. No detailed builder profile has arrived. The actual
  redundant operation is established from source; no millisecond saving is claimed.
  Table construction may outweigh savings for short lists or very few queries. Measure
  complete first-run cost and build phase on both official workloads before retaining it.
- Local validation: `experiments/notes/overnight-overhead-name-lookup-check.py` passed
  2,106 comparisons against original `.index`, plus three fresh-call checks. It covers
  empty/duplicate names, Unicode, missing names, tuples, unhashable items, a custom list
  override and rebuilding after name mutation. Initial test exposed tuple missing-name
  message mismatch; repaired by retaining tuple `.index`, then all checks passed.
  An AST comparison undid exactly the four lookup substitutions and local initialization,
  removed the helper, and matched the entire parent build.py AST. All nine other simulator
  Python modules remain byte-identical to ee4fea2. Syntax checks passed. These are small
  stdlib correctness inspections, not optical/JAX validation or performance benchmarks.
- Candidate SHA and job IDs pending supervisor commit. Request both unchanged full official
  benchmarks, complete output/gradient and14-case generalization comparisons, independent
  review, and paired fresh-process parent/candidate measurements if the build phase improves.
  Record phase medians, all total samples/ranges, memory and overlap information separately
  for large and aLIGO. Existing candidate15/16 review/confirmation requests remain open.
- No changes to physical inputs, gradients, three JIT stages, package compiler settings,
  public harness/data or caches. Inherited pristine disagreements (including uifo_rand1/3
  and grid gradients33/161/180), unresolved grid finite differences and first-order-only
  VJP compatibility remain unresolved. Deadline09:27:44 UTC unchanged. If this search
  removal has no meaningful effect, use the requested import/build profile to choose the
  next mechanism instead of iterating on lookup-table variants.

### Candidate17 feedback — lookup change retired

- Exact SHA **e9781b8c50c796ea9d5737152f55ff00110f4482**, request
  **f177375645ff451c918657dc8cadb3b8**, grid-1/2/3 and aligo-1/2/3.
  Official3/3 passes per setup; initial-seed tolerance comparisons pass every output and
  gradient, including all14 generalization cases. Pristine comparisons still fail the
  inherited signal/gradient/loss and uifo_rand1/rand3 sensitivity checks. No new numerical
  discrepancy is reported by these checks; this is not a universal correctness certificate.
- Large samples seconds:0.8377355355769396,0.8026807140558958,0.8052605800330639;
  median0.8052605800330639, range0.8026807140558958–0.8377355355769396.
  Official aLIGO:0.5527297761291265,0.5479395072907209,0.5479968544095755;
  median0.5479968544095755, range0.5479395072907209–0.5527297761291265.
  Historical parent large median0.801577684 is lower by3.683 ms; aLIGO difference is only
  0.558 ms in the candidate's favor. These unmatched cohorts establish no improvement.
- Phase medians ms large/aLIGO: imports264.697/266.652; build72.520/38.506;
  forward lowering19.585/19.381, compilation32.942/33.396, execution186.436/33.928;
  sensitivity lowering25.476/26.262, compilation41.479/41.378;
  gradient lowering16.865/16.653, compilation53.294/53.499, execution87.506/14.321.
  Build samples large76.739,72.520,69.080 ms; aLIGO40.651,38.506,38.062 ms. The
  separate candidate16 build medians were74.149/37.870 ms: opposite directions and
  substantial spread, not convincing attribution to the name lookup mechanism.
- Sampled peak RSS bytes large593010688/621879296/606384128;
  aLIGO280526848/304758784/308908032; generalization961556480. No budget exceeded or
  infrastructure failure. CPU2, one library thread, x64, no persistent compilation cache;
  external contention not excluded, ranking_eligible=false. Source review absent;
  confirmed_improvement=false, below large gain threshold and ranges overlap.
- Decision: remove the local lookup implementation and return build.py to reviewed
  ee4fea2 before the next isolated trial. Candidate17 and its test remain preserved in
  history. Do not iterate on lookup variants without profile evidence. Existing unresolved
  grid finite differences and first-order-only VJP scope remain unchanged.

### Candidate18 — retain component-group metadata in NumPy

- Baseline simulator **ee4fea28c04d482566be16e916b609d7c6a99e5e**; only build.py differs.
  Exactly three conversions within `_group_component_indices` change from `_host_array`
  (NumPy then JAX) to `np.asarray(..., dtype=np.int64)`: function rows, output-row
  permutation and grouped parameter indices. Grouping, ordering, values and dtype are
  unchanged. These structural arrays are subsequently read by NumPy to compute derivative
  slots, SparseStructure and HostPlan. The default host simulation consumes those plans.
- This establishes actual avoidable staging: the original helper creates2G+1 JAX arrays
  for G function groups with parameter indices; plan construction reads the same metadata
  back through NumPy. Candidate18 avoids those eager device conversions. If a dense/JAX
  path consumes the arrays, its ordinary array-leaf handling supplies them at the point of
  use, counted within evaluation. No physical values, outputs or derivatives are cached.
- Distinction from unsuccessful candidate8: this does not convert the whole builder to
  host-first assembly or add a final batched device_put; the main matrices, parameters,
  update selectors and returned physical metadata keep their reviewed preparation. Only
  the private component-group metadata avoids premature staging. No candidate15/16/17
  optimization is combined. Candidate8's failure remains evidence against broader changes.
- Target is build overhead and temporary object creation; no measured saving yet. The
  latest measured build medians72.520 ms large and38.506 ms aLIGO are whole-phase costs,
  not estimates of recoverable conversion time. JAX argument processing may offset savings.
  Full first-run timing on both unchanged official workloads must decide retention.
- Compatibility: NumPy arrays are ordinary JAX pytree leaves; dynamic uses must retain
  identical compiled primal/gradient behavior. Unlike former JAX leaves these metadata
  arrays are mutable; callers must still rebuild static plans whenever selectors change,
  as already documented. No cross-setup metadata cache or invalidation rule is added.
- Local AST validation reversed exactly the three conversions and the helper docstring,
  matching the entire reviewed parent build.py AST. Other nine simulator modules match
  parent bytes. All simulator and diagnostic syntax checks pass. No local numerical test
  or timing was run because local Python lacks NumPy/JAX.
- Prepared `experiments/notes/overnight-overhead-group-host-check.py`: ten metadata-tree
  comparisons against the same helper with eager device conversion restored, plus ten
  JIT primal/gradient comparisons using both real and complex synthetic parameters.
  Includes empty, singleton, repeated and interleaved groups and omitted input metadata.
  Runtime UNEXECUTED. Request its execution in the fixed environment, both full official
  benchmarks, all physical output/gradient and14-case generalization comparisons, and
  independent source review. Candidate SHA/job IDs pending supervisor commit.
- Preserve inherited pristine-reference and finite-difference caveats. No physics, workload,
  compiler policy, fixture, benchmark, three-stage structure or shared environment changes.
  If this narrower staging trial is also unsuccessful, request the pending import/build
  profile before another staging variant. Deadline09:27:44 UTC unchanged.


### Candidate18 feedback and staging-hypothesis handoff

- Evaluated SHA **f1acd5ba7f2f80dba8076599ead8c01aef6545be**, request
  **5b7dff8c3ca6444ca76139f97a5307ca**, jobs grid-1/2/3 and aligo-1/2/3.
  Both unchanged official benchmarks passed 3/3. All saved physical-array/gradient
  comparisons against the initial seed passed the evaluator tolerances, as did all14
  generalization cases. Pristine comparisons still fail the inherited checks; no new
  discrepancy was reported. Independent source review is absent. The prepared synthetic
  metadata/JAX diagnostic has no reported execution result.
- Large complete first-run samples seconds: 0.8362261410802603, 0.7882700376212597,
  0.7978439573198557; median0.7978439573198557, range0.7882700376212597–0.8362261410802603.
  Official aLIGO samples: 0.5429688971489668, 0.5398643594235182, 0.5404376741498709;
  median0.5404376741498709, range0.5398643594235182–0.5429688971489668.
  Against historical reviewed ee4fea2 medians, observed reductions are3.734 ms large
  (about0.466%) and8.117 ms aLIGO. These are unmatched cohorts, not confirmed gains.
  Supervisor confirmed_improvement=false; large gain below selection threshold,
  overlapping ranges, and independent review still required.
- Phase medians ms large/aLIGO: imports266.906/262.858; build74.421/36.499;
  forward lowering19.663/19.105, compile30.391/33.380, execution179.801/32.940;
  sensitivity lowering25.522/26.278, compile39.955/41.369;
  gradient lowering16.484/16.556, compile52.628/53.214, execution85.952/14.748.
  Relative to candidate17's separate cohort, build rose1.902 ms large and fell2.006 ms
  aLIGO. Large forward execution fell6.635 ms despite this candidate changing only build
  metadata. Attribution to the three conversions is therefore not established.
- Sampled peak RSS bytes: large583942144/501895168/508186624;
  aLIGO284164096/294166528/282296320; generalization722591744. No infrastructure failure
  or memory-budget exceedance. EPYC9334, CPU2, one logical CPU and library threads1,
  x64, unchanged package flags, no persistent compilation cache. Other-host contention
  was not excluded; ranking_eligible=false. No combined benchmark score is used.
- Decision: retire candidate18 without further staging variants. Restored build.py bytes
  from **ee4fea28c04d482566be16e916b609d7c6a99e5e**; all10 simulator Python modules are
  checked against that reviewed parent. This is a working-tree source restoration for
  supervisor bookkeeping, not a Git reset or a proposed new performance candidate.
  Candidate18 and every earlier trial remain in history, and diagnostic files remain
  explicitly provisional. No automatic combination with candidates15/16/17.
- Next experiment requires attribution: run the already prepared
  `experiments/notes/overnight-overhead-profile.py` through the supervisor in fresh fixed
  evaluator processes, using the actual caller inputs for large, official aLIGO and one
  different optical setup. Obtain import/setup/build self and cumulative profiles before
  proposing another builder staging change. Its scope excludes simulation and benchmark-
  owned imports such as optax; it is diagnostic evidence, not an official timing score.
  Existing candidates15/16 still lack requested independent review and paired confirmation.
- Source inspection also finds `prepare_arrays` immediately converts changing_values
  NumPy→JAX→NumPy→JAX. This is a real redundant copy, but its recoverable cost is unmeasured;
  do not submit another tiny transfer variant without attribution after this unsuccessful
  sequence. Required JAX/SciPy imports dominate remaining dependencies; reviewed lazy
  Plotly and dense-path JAX SciPy loading are already present.
- Preserve unresolved pristine signal/gradient/loss discrepancies, grid gradients33/161/180,
  uifo_rand1/rand3 log sensitivity disagreements, grid finite-difference coordinates
  54/59/63/136/161/163, and first-order reverse-only custom-VJP compatibility. Prior aLIGO
  finite differences29/29 remain distinct evidence. No universal correctness claim.
- End this hypothesis with ready_for_evaluation=false, stop=true. The eight-hour campaign
  remains separately authorized until09:27:44 UTC; this handoff does not extend its deadline
  or claim that the overall optimization objective is complete.

### Candidate19 — direct complex power magnitude squared

- Resumed under the explicit request for a concrete experiment. Change direction from
  builder staging to scalar readout arithmetic. Semantic baseline remains reviewed
  **ee4fea28c04d482566be16e916b609d7c6a99e5e**. Candidate18 restoration remains in the
  working diff against latest evaluated f1acd5b; it is not retained or combined.
- Only components.py differs from ee4fea2: power_detector uses real(z)**2 + imag(z)**2
  for complex inputs, then the identical0.5*EPSILON_0C scale. Real inputs retain the
  original abs-square implementation and dtype conventions. Dispatch uses dtype alone,
  never workload identity or physical parameter values. Every field and power output is
  still computed. No solver, refinement, adjoint, cache, compiler or harness changes.
- Actual redundancy: complex abs computes a magnitude, which power_detector immediately
  squares. Removing that magnitude/square-root operation may reduce the sensitivity-stage
  compiled graph and execution. Last official sensitivity lower/compile medians were
  25.522/39.955 ms large and26.278/41.369 ms aLIGO, with execution below1 ms. These whole
  phase costs are NOT estimates of recoverable savings. Both unchanged full benchmarks
  must establish whether this small arithmetic rewrite helps complete first-run time.
- Important attribution: official readout returns power_detector(carrier) as has_aux=True
  data, so its derivative is not part of the official loss pullback. Do not claim official
  gradient-stage savings from this change. Direct callers differentiating power_detector
  still require correct reverse derivatives, including complex zero; no custom derivative
  rule or host interpreter is introduced.
- An initial detector-first utility idea was rejected before editing: the official harness
  calls df.signal_detector directly, bypassing calculate_sensitivities. Changing that
  utility alone would miss this measured workload. No utility modification is submitted.
- Numerical classification: mathematically equivalent finite complex power, but rounding
  can differ from magnitude-then-square. This is a numerical candidate requiring full
  saved power/output/gradient inspection, not a bitwise-preserving metadata change.
  Stdlib math.hypot comparison over2,000 random scalar pairs with scales1e-150..1e150
  found maximum relative power difference6.325459876663449e-16. This is only a small
  scalar sanity check, not a JAX/XLA, extreme-domain or optical correctness certificate.
- Prepared supervisor diagnostic `experiments/notes/overnight-overhead-power-square-check.py`:
  48 JIT primal/VJP comparisons covering float32/64 and complex64/128, scalar/empty/vector/
  matrix shapes, signed zeros, tiny/ordinary/large finite scales; additional imaginary-axis
  and equal-component cases check the analytical reverse derivative. UNEXECUTED locally
  because NumPy/JAX are unavailable; no dependencies installed or benchmarks launched.
  AST removal of the single new complex branch matches parent components.py exactly;
  all nine other simulator modules match parent bytes. Syntax and diff checks pass.
- Candidate SHA/job identifiers pending supervisor commit. Request both unchanged full
  official benchmarks on that exact SHA, saved arrays and full gradient comparisons,
  14-case varied-setup/frequency/modulation checks, the synthetic diagnostic and independent
  review. If promising, request paired fresh parent/candidate complete timings, individual
  samples, separate medians/ranges/phases, memory and overlap status before promotion.
- Inherited pristine signal/gradient/loss disagreements, uifo_rand1/rand3 sensitivities,
  unresolved grid finite differences54/59/63/136/161/163, and first-order-only host VJP
  remain open. Investigate any new disagreement rather than loosening tolerances. If the
  sensitivity-phase saving is absent or lost in total variance, retire this direct-square
  trial and use the still-pending import/build attribution before further micro-variants.
  No measured gain is claimed. Campaign deadline09:27:44 UTC unchanged.

### Candidate19 feedback — direct-square readout retired

- SHA **0a705c5a28401324dc214a82fcab69a1ceca931a**, evaluation
  **9eec33c1266745fdbd3a2bd5c0a33056**, grid-1/2/3 and aligo-1/2/3.
  Official3/3 passes each. Reported full-array comparisons, including powers and every
  gradient entry, pass against initial-seed tolerances; all14 generalization cases also
  pass those tolerances. Pristine signal/gradient/loss and uifo sensitivity failures remain.
  Archive hashes changed (large df2fcce0..., aLIGO d1a462e8...); no bitwise-equivalence
  claim is made. Raw per-entry power deltas and synthetic diagnostic results were not
  supplied. No independent review; no promotion or universal numerical claim.
- Large first-run seconds:0.8354643564671278,0.8035739101469517,0.793807327747345;
  median0.8035739101469517, range0.793807327747345–0.8354643564671278.
  Official aLIGO:0.5448887161910534,0.5519863422960043,0.5455458797514439;
  median0.5455458797514439, range0.5448887161910534–0.5519863422960043.
  Against historical ee4fea2 medians, large is1.996 ms slower and aLIGO3.009 ms faster.
  Unpaired ranges overlap. Supervisor confirmed_improvement=false; large gain below
  threshold, overlapping ranges, independent source review absent.
- Phase medians ms large/aLIGO: imports266.086/264.119; build72.097/37.693;
  forward lower19.657/19.290, compile32.740/33.656, execute184.710/32.804;
  sensitivity lower26.651/27.362, compile39.969/41.575, execute0.859/0.487;
  gradient lower17.286/17.050, compile52.211/53.671, execute84.821/14.384.
  Relative to preceding candidate18's separate cohort, sensitivity lowering rose about
  1.129/1.084 ms; sensitivity compilation is essentially unchanged. No targeted phase
  gain established. Retire arithmetic rewrite rather than extending it to another formula.
- Sampled peak RSS bytes large518868992/672632832/523542528;
  aLIGO295395328/283484160/295043072; generalization956096512. No memory-limit excess or
  infrastructure failure. Same EPYC9334 CPU2, one logical CPU, threads1, x64, unchanged
  package flags, no persistent cache; contention not excluded, ranking_eligible=false.
- Restored components.py exactly to reviewed ee4fea2; candidate19 remains in history.
  Inherited grid33/161/180 discrepancies, grid finite differences54/59/63/136/161/163,
  uifo_rand1/rand3 sensitivity disagreements and first-order-only host VJP remain open.

### Candidate20 — validate static phase-scatter bounds

- Semantic baseline **ee4fea28c04d482566be16e916b609d7c6a99e5e**. Only simulate.py differs;
  candidate19's power change is removed. New `_phase_scatter_mode` returns
  PROMISE_IN_BOUNDS only for NumPy integer coordinates of shape(K,3) whose entries are
  nonnegative and less than the corresponding current selection-array dimensions.
  Otherwise it returns None, retaining lax.scatter_mul's existing default behavior.
- Target: tracing/lowering and compilation of the phase scatter and its reverse pass.
  The host plan already supplies concrete phase destinations, but the scatter still uses
  default bounds behavior. The check proves bounds from arbitrary supplied coordinates
  and the current traced operand shape, allowing JAX to omit generic bounds handling.
  Latest forward lower/compile medians19.657/32.740 ms large,19.290/33.656 ms aLIGO;
  gradient lower/compile17.286/52.211 ms large,17.050/53.671 ms aLIGO are whole-phase costs,
  not recoverable-cost estimates. Host validation itself costs time and must be counted.
- This is distinct from candidate15's empty-phase elimination: all exp/gather/scatter
  operations remain, including empty arrays. It does not combine15/16/18/19. No current
  zero value is treated as structural absence. No additional uniqueness promise is made;
  the scatter retains its parent's existing unique_indices=True contract. Traced JAX
  indices, negative indices, out-of-bounds coordinates, noninteger arrays and unrecognized
  shapes retain the default. Structural metadata still requires rebuild after mutation,
  as already documented; no cache or new invalidation mechanism is introduced.
- Pure source verification removed exactly the helper and one mode keyword and matched
  the entire parent simulate.py AST. All nine other simulator Python modules match parent
  bytes. Syntax and diff checks pass. No numerical or performance test run locally.
- Prepared `experiments/notes/overnight-overhead-phase-bounds-check.py` for supervisor:
  twelve JIT primal/VJP comparisons against the actual scatter with mode omitted, covering
  static and dynamic indices, empty/valid/negative/out-of-range coordinates, zero selectors
  and zero updates; additional dtype/shape/JAX-array fallback checks. Runtime UNEXECUTED
  because local NumPy/JAX are absent. No installations or independent benchmarks.
- Candidate SHA/jobs pending supervisor commit. Request the synthetic checks, both unchanged
  official benchmarks, every output and gradient, varied-setup/frequency/modulation checks,
  and independent review. Any apparent gain needs paired fresh parent/candidate confirmation
  with separate total samples, medians/ranges, phase tradeoffs, memory and overlap status.
  Existing pristine and finite-difference disagreements remain open; no tolerance changes.
  If bounds simplification does not improve its target phases, do not pursue another scatter
  mode variant without lowered-graph attribution. Pending import/build profile remains a
  separate next direction. Deadline09:27:44 UTC unchanged; no measured gain claimed.
