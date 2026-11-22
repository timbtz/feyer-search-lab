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


### Candidate20 feedback — bounds hypothesis closed, reviewed parent retained

- Evaluated SHA **558d1d18ca4d68a1296ede6536980b2d07213ab8**, request
  **d76a2f2deee34b9e996f5f5c873097bf**, grid-1/2/3 and aligo-1/2/3.
  Both unchanged official benchmarks pass3/3. Every reported physical array and gradient
  passes initial-seed tolerances, as do all14 generalization cases. Pristine comparisons
  remain failing; independent source review is absent. confirmed_improvement=false.
- Large fresh-process seconds:0.8317801412194967,0.7977231331169605,0.7970464248210192;
  median0.7977231331169605, range0.7970464248210192–0.8317801412194967.
  Official aLIGO:0.5465619154274464,0.5429943576455116,0.5425329990684986;
  median0.5429943576455116, range0.5425329990684986–0.5465619154274464.
  Historical ee4fea2 median differences are3.855 ms lower large (about0.481%) and
  5.561 ms lower aLIGO. These are separate unpaired cohorts; large ranges overlap and
  the relative improvement misses the selection threshold. No combined score or gain claim.
- Phase medians ms large/aLIGO: imports265.393/265.242; build72.520/38.050;
  forward lower19.791/19.246, compile33.319/33.728, execute184.598/32.627;
  sensitivity lower25.442/26.358, compile41.174/41.529, execute0.906/0.469;
  gradient lower15.066/14.547, compile52.881/53.023, execute84.318/14.545.
  Gradient lowering is about1.799/2.106 ms below candidate17's separate cohort, but forward
  lowering and compilation show no comparable reduction. Without paired parent timing or
  lowered-graph attribution this is a possible mechanism, not a confirmed total-time gain.
- Sampled peak RSS bytes large633970688/682823680/620421120;
  aLIGO280842240/295092224/288018432; generalization931201024. No infrastructure failure
  or memory-budget exceedance. EPYC9334 CPU2, one logical CPU, threads1, x64, unchanged
  package flags and no persistent cache. Host contention is not excluded; ranking_eligible=false.
- Generalization archive9383841a32aa7d2f559cb89aeb1c7159b374414995cf77e802563809c7c0915a.
  Initial-seed gradient maximum absolute differences remain5.686350050382316e-6 large
  and3.637978807091713e-11 aLIGO. No newly reported tolerance failure. Do not equate these
  passing comparisons or self-comparison archive hashes with bitwise seed equivalence.
  Inherited pristine grid signal/gradients33/161/180/loss, uifo_rand1/rand3 sensitivity
  disagreements, grid FD54/59/63/136/161/163 and first-order-only host VJP remain unresolved.
- Decision: close the bounds mechanism. Repeated readout, builder and boundary microtrials
  have not established a repeat-supported shared improvement. Restore simulate.py exactly
  to reviewed ee4fea2; all10 simulator Python modules now match that parent byte-for-byte.
  Failed candidate20 and previous trials remain in history; no reset or commit performed.
- Next experiment for coordinator: the existing candidate15 confirmation request above
  remains unanswered. Independently review exact **2e50e7cffc8c7feb5ae53dc770e26cbb45250ab8**
  versus **ee4fea28c04d482566be16e916b609d7c6a99e5e**, run its empty-phase synthetic check,
  and obtain five interleaved fresh complete runs per revision for each official setup,
  direct full-array/gradient comparisons and varied nonempty/zero-phase generalization.
  Its previous medians0.7853874359279871 large and0.5305512081831694 aLIGO are promising
  but unpaired, overlapping on large, and unreviewed. Do not promote or combine it yet.
  Alternatively obtain the pending import/build profile before further implementation
  microtrials. No new candidate is claimed by this restoration.
- Synthetic JAX diagnostics remain UNEXECUTED locally (NumPy/JAX unavailable). No benchmarks,
  installs, network calls, commits or agents launched. This stop handoff closes this hypothesis,
  not the authorized campaign. Absolute deadline09:27:44 UTC remains unchanged.


### Confirmation submission21 — replay candidate15 exactly, no new mechanism

- The supervisor resumed after the candidate20 stop handoff and requested a concrete
  evaluable simulator change. The repeated d76a2f2deee34b9e996f5f5c873097bf receipt is
  still candidate20 feedback, not a test of the restored parent or this submission.
- Concrete experiment: restored simulate.py from **2e50e7cffc8c7feb5ae53dc770e26cbb45250ab8**.
  ALL10 simulator modules now match that previously evaluated candidate byte-for-byte;
  the other9 modules also match reviewed **ee4fea28c04d482566be16e916b609d7c6a99e5e**.
  This is a confirmation replay, not a novel optimization or a combination. The supervisor
  will supply the new revision SHA and jobs. Historical passes do not certify that revision.
  Candidate20 bounds logic and candidate19 arithmetic remain removed. History is preserved.
- Mechanism remains only structural empty-phase elimination: both static phase parameter
  and destination arrays must be empty before the gather/exp/scatter are omitted. Nonempty
  zero phase values and zero selectors keep their operations and derivative contributions.
  Every public physical output, optimized input, frequency and the three JIT stages remain.
  There is no fixture/shape identity dispatch, new cache, preload or solver/adjoint change.
- Rationale for replay: candidate15 evaluation **b699b389623a46c98a1e34c803ca18d8** had
  forward-lowering medians14.091/13.617 ms and gradient-lowering12.989/13.046 ms
  (large/aLIGO), compared with candidate20's19.791/19.246 and15.066/14.547 ms.
  These unmatched phase observations motivate confirmation only. Candidate15 complete
  large samples0.8227882608771324,0.7784748841077089,0.7853874359279871,
  median0.7853874359279871, range0.7784748841077089–0.8227882608771324;
  aLIGO0.5328888855874538,0.5305512081831694,0.5279352385550737,
  median0.5305512081831694, range0.5279352385550737–0.5328888855874538.
  Large ranges overlap the reviewed parent. No independent review or paired confirmation
  has arrived. Previous official passes and initial-seed tolerance passes are recorded in
  candidate15's feedback above; pristine disagreements remain. No validated gain claimed.
- Source inspection considered build list lookup, group staging, dense position metadata
  and sweep-copy costs. Prior trials already covered the first three without established
  gains; the remaining single sweep-copy redundancy lacks evidence of material cost.
  None is added. Confirm the stronger isolated tracing signal before further microtrials.
- Validation performed locally: exact10-file source equality to candidate15; all simulator
  syntax; AST restoration of just the empty-phase branch, scatter guard and docstring
  reproduces the entire parent simulate.py AST. Thus the nonempty phase code is unchanged.
  The existing eight-case JIT primal/VJP diagnostic remains UNEXECUTED locally because
  NumPy/JAX are unavailable. No installations, benchmarks, commits or agents launched.
- Evaluation request: both unchanged official benchmarks on the new exact SHA, independent
  review against ee4fea2, `overnight-overhead-empty-phase-check.py`, all saved physical
  arrays/gradients against the parent and seed, and the14 varied-setup generalization cases.
  Include additional nonempty homodyne phase and zero-phase derivative coverage. Obtain
  five interleaved fresh runs per revision per official setup against ee4fea2 on identical
  CPU/thread/environment policy; report samples, separate medians/ranges, phases, memory
  and overlap status. This repeated confirmation is not a request to relax admission rules.
- Inherited strict grid signal/gradient33/161/180/loss issues, uifo_rand1/rand3 sensitivity
  errors, unresolved grid FD54/59/63/136/161/163 and no JVP/Hessian host-pass support remain
  visible. Prior aLIGO FD29/29 does not certify all setups. New discrepancies need investigation.
  ready_for_evaluation=true refers to the actual replay implementation now in this worktree.
  Deadline09:27:44 UTC unchanged; this submission does not extend it.


### Submission21 feedback — tracing signal reproduced, promotion unresolved

- SHA **f90fa964a73aca5515ba93a3517ec1d26ae32a32**, evaluation
  **a4d2cd8dcf5f448aafa8d2817fb59644**, grid-1/2/3 and aligo-1/2/3. Source is exactly
  candidate15's simulator implementation. Both official benchmarks pass3/3; all reported
  physical output/gradient categories and14 generalization cases pass initial-seed tolerances.
  No new reported regression. Pristine checks still fail. Independent source review and
  requested synthetic results are absent; no paired current-parent cohort supplied.
- Large fresh seconds0.8098749481141567,0.7841489966958761,0.7943564131855965;
  median0.7943564131855965, range0.7841489966958761–0.8098749481141567.
  Official aLIGO0.5375279970467091,0.5347207505255938,0.5324668753892183;
  median0.5347207505255938, range0.5324668753892183–0.5375279970467091.
  Historical ee4fea2 medians are7.221 ms higher large and13.834 ms higher aLIGO, but
  large ranges overlap. Admission: confirmed_improvement=false, requires_source_review,
  large_first_run_ranges_overlap_requires_paired_evidence. Do not pool separate cohorts
  to conceal spread, infer a quiet ranking cohort, or report an average competition score.
- Phase medians ms large/aLIGO: imports269.715/266.587; build72.201/37.938;
  forward lower14.234/13.697, compile30.744/31.207, execute180.251/32.822;
  sensitivity lower25.666/26.133, compile39.885/41.362, execute0.883/0.483;
  gradient lower13.308/13.350, compile52.618/52.894, execute85.307/14.715.
  Forward lowering is within0.143/0.080 ms of candidate15's earlier phase medians;
  gradient lowering within0.319/0.304 ms. The targeted tracing signal reproduced in this
  candidate-only cohort. Complete totals still vary, and causal speedup against a matched
  parent remains unconfirmed. No further empty-phase variant is justified by this receipt.
- Sampled peak RSS bytes large507691008/496709632/577581056;
  aLIGO294842368/294936576/294637568; generalization831197184. No infrastructure failure
  or budget exceedance. CPU2, one logical CPU, threads1, x64, reviewed flags, no persistent
  cache; host contention not excluded, ranking_eligible=false.
- Generalization archive5463a96afd9c95ad78c8e2a40700708ce1dd1a3a6c04b9808de09dda6af9237e.
  Seed gradient max absolute differences5.686350050382316e-6 large and3.637978807091713e-11
  aLIGO remain. Pristine grid signal/gradients33/161/180/loss, uifo_rand1/rand3 sensitivity,
  unresolved grid FD54/59/63/136/161/163, and no host-pass JVP/Hessian support remain open.
- Retain exact f90fa96/2e50e7c in history as an unpromoted candidate for independent review
  and paired parent confirmation. For the next independent experiment restore simulate.py
  to reviewed ee4fea2; do not combine this unreviewed change with a builder modification.

### Candidate22 — concatenate sideband instruction indices once

- Semantic parent **ee4fea28c04d482566be16e916b609d7c6a99e5e**. Only build.py differs from
  it. Candidate SHA and jobs pending supervisor commit. This is distinct from previous
  name lookup, group classification/staging, matrix allocation and phase-boundary trials.
- Actual repeated work: set_instructions copies each index array before appending up to
  three sideband blocks. Each np.concatenate then copies the entire growing prefix again.
  `_append_sideband_indices` collects the same original and selected blocks and performs
  one final concatenation per result. With m output arrays and k active masks, it removes
  m initial prefix copies and replaces k*m concatenations with m concatenations (k>0).
  With no active mask it still returns fresh copies, preserving aliasing behavior.
  Boolean selections and nonzero offset additions remain, so this is not a count of all
  allocations or a measured time saving. Common one-mask calls still avoid the initial copy.
- Preserved semantics: masks and appended-signal in-place shifts are unchanged. Blocks remain
  original, only-row, only-column, then row-and-column, keeping duplicate write order. All
  duplicates read the shifted originals, never an already-expanded prefix. Output row/column
  selectors are copied in that same order; carrier source IDs are not shifted. Optional
  output rows, carrier-copy isolation and the no-sideband path remain. No floating optical
  arithmetic, solver, adjoint, derivative pruning, array staging, import or compiler changes.
  The helper depends solely on supplied instructions, not optical values or fixture identity.
- Target is build, currently72.201 ms large and37.938 ms aLIGO in submission21. These are
  complete build-phase medians, not attributed recoverable time. Python helper/list overhead
  could outweigh saved copies for short instructions; both complete first-run totals must
  count it. No expected gain is represented as measured.
- Local validation:2,000 randomized stdlib list-backed executions of the ACTUAL new helper
  agree with sequential append order and shifts, preserve fresh result objects, and verify
  one concatenation per output array whenever any mask is active. This is an algorithmic
  check, not NumPy dtype/aliasing or optical validation. Unrelated build definitions/statements
  match parent AST; nine other simulator modules match parent bytes; syntax/diff checks pass.
- Prepared `experiments/notes/overnight-overhead-sidebands-check.py` with parent set_instructions
  source embedded verbatim from ee4fea2. Its480 NumPy comparisons exercise complete instruction
  dictionaries, dtype equality, caller-array mutations and output/input memory sharing across
  int32/int64/float64, empty and varied lengths, absent/zero/positive sideband sizes, all mixed
  regions (including negative indices), optional output rows, carrier coupling and padded
  parameter widths. UNEXECUTED locally because NumPy is unavailable; no packages installed.
- Request supervisor synthetic check, both unchanged full official benchmarks on the exact
  new SHA, full outputs/gradients and14 varied-setup generalization comparisons, independent
  review, then matched parent/candidate fresh-process confirmation if promising. Report every
  sample, separate medians/ranges, phases, memory and overlap. Initial-seed tolerance passes
  would not resolve inherited pristine discrepancies; investigate any new difference.
- If no material build reduction appears, retire sideband concatenation rather than extend
  it to more builder loops without profiling. Pending import/build attribution remains the
  next evidence request. No benchmarks, commits, external calls or agents launched locally.
  Absolute campaign deadline09:27:44 UTC unchanged.

### Candidate22 feedback — sideband concatenation retired

- SHA **18d8799ac7e4d5ad6a4463c399e9a26e6a3e5842**, request/evaluation
  **08dee50b38a644b4aa857e409b2f615d**, grid-1/2/3 and aligo-1/2/3. Both official
  benchmarks pass3/3. All reported output/gradient categories and14 generalization
  cases pass initial-seed tolerances; pristine comparisons still fail. Independent
  source review and the480 synthetic NumPy comparisons were not supplied.
- Large fresh seconds0.8339520487934351,0.8138816673308611,0.87968092225492;
  median0.8339520487934351, range0.8138816673308611–0.87968092225492.
  Official aLIGO0.5574252754449844,0.5896702744066715,0.5418223775923252;
  median0.5574252754449844, range0.5418223775923252–0.5896702744066715.
  Historical reviewed-parent medians are32.374 ms lower large and8.870 ms lower
  aLIGO; this is unpaired evidence, not a causal regression estimate.
  Admission confirmed_improvement=false: requires_source_review,
  large_gain_below_selection_threshold, ranges overlap requiring paired evidence.
- Phase medians ms large/aLIGO: imports282.322/268.555; build74.095/44.053;
  forward lower20.053/19.329, compile33.407/34.356, execute182.275/32.646;
  sensitivity lower25.715/26.134, compile40.174/41.407, execute0.902/0.467;
  gradient lower17.251/16.586, compile52.056/53.284, execute86.401/14.485.
  Build samples ms large73.970/74.095/75.558, aLIGO44.053/52.959/37.356.
  There is no measured build-time benefit. Grid3 forward227.135 ms and sensitivity
  lowering47.060 ms are elevated; their cause is unknown. Do not attribute to
  contention without evidence or remove samples to improve the result.
- Sampled peak RSS bytes large519794688/526860288/588611584;
  aLIGO282181632/287334400/315400192; generalization781201408. No infrastructure
  failure or memory exceedance. EPYC9334, CPU2, one logical CPU, threads1, x64,
  unchanged reviewed flags, no persistent cache. Overlap unknown; ranking_eligible=false.
- Generalization archive033c0555b6a71a0a7a127254c4c5a207cab87689dff921fc6740bee121bb903d.
  Seed gradient max absolute differences remain5.686350050382316e-6 large and
  3.637978807091713e-11 aLIGO. Pristine signal/gradient/loss disagreements, random
  setup sensitivity failures, grid FD54/59/63/136/161/163 and first-order-only host
  VJP limitations remain unresolved. No tolerance changes or new correctness claim.
- Decision: retire this builder mechanism and restore build.py from reviewed ee4fea2.
  Preserve22 in history; do not extend adjacent concatenation/staging loops without
  the pending profile attribution. The next experiment below uses a distinct boundary
  mechanism and does not combine any unpromoted phase or builder modifications.

### Candidate23 — return only active input cotangents across the callback

- Semantic parent **ee4fea28c04d482566be16e916b609d7c6a99e5e**. Only host_pass.py differs
  from that source; nine other simulator modules match it byte-for-byte. Candidate SHA
  and benchmark job IDs pending supervisor commit/evaluation. Actual host_forward,
  host_backward, assembly, solver, refinement and adjoint mathematics are unchanged.
- Source inspection: the backward pure_callback declares seven input-cotangent results
  unconditionally. Differentiation of a subset of inputs discards inactive cotangents
  after the callback. New code opts into JAX's symbolic_zeros metadata, saves the seven
  perturbed flags as a hashable static tuple with no array leaves, and unwraps every
  primal before the same forward callback. The backward still evaluates the COMPLETE
  host_backward and selects only active results before returning across the callback.
  Its outer VJP returns None for inactive inputs, as allowed by JAX. When all inputs
  participate, all seven are returned. No argument is assumed inactive by identity,
  size, setup, name, value or benchmark. Numerical zero values remain differentiable.
- Unused output cotangents can now be symbolic too; these are materialized with each
  output's shape/dtype before calling the unchanged host derivative. All three physical
  public outputs and all five forward residual arrays remain. Forward assembly/factors
  are unchanged, no new cache is introduced, and no work leaves the timed evaluation.
  Every requested design-variable gradient is retained through its active parameter row.
- Target: callback result descriptors, result buffer handling and gradient lowering/compile,
  currently17.251+52.056 ms large and16.586+53.284 ms aLIGO in22. These phase totals are
  not recoverable-cost estimates. Actual active-result counts in the official trace have
  NOT been measured locally. The toy diagnostic asserts expected callback arities for
  arbitrary active subsets. This is a hypothesis about boundary overhead, not a measured
  speedup; CPU callback transfers may be cheap and metadata handling may offset savings.
- Public API references inspected (documentation may be newer than evaluator JAX0.9.0):
  [custom_vjp.defvjp](https://docs.jax.dev/en/latest/_autosummary/jax.custom_vjp.defvjp.html)
  documents perturbed primal flags and symbolic output cotangents;
  [register_static](https://docs.jax.dev/en/latest/_autosummary/jax.tree_util.register_static.html)
  documents hashable no-leaf metadata. Exact-version execution is still required.
- Local verification:1,024 stdlib stub executions of the ACTUAL new boundary functions
  cover all128 active-input masks and all8 symbolic-output masks. They check forward
  value/residual preservation, callback result shape/count, cotangent routing and the
  no-active-input case. These verify Python routing ONLY, not JAX semantics. Syntax and
  git diff checks pass. AST comparison verifies all non-boundary definitions/statements
  in host_pass.py match reviewed parent (apart from defvjp registration).
- Prepared `experiments/notes/overnight-overhead-active-cotangents-check.py`:44 synthetic
  comparisons against the parent callback rule, including40 JIT gradients and JAXPR
  arity assertions for every single input, all inputs and mixed subsets, each output
  alone and all outputs; zero-valued primals with nonzero derivatives; stop_gradient;
  explicit VJP with complex/zero cotangents; sequential vmap; plain JIT primal equality.
  It executes the actual boundary AST in an isolated toy namespace, without patching
  simulator or validation modules. UNEXECUTED locally: NumPy/JAX unavailable. No installs.
- Request supervisor run this diagnostic first, then both unchanged official benchmarks,
  full saved output/gradient and14 generalization comparisons on the exact new SHA,
  and independent source review. If promising, obtain matched fresh parent/candidate
  repetitions, separate samples/medians/ranges, phase deltas, memory and overlap evidence.
  Do not promote on public passes or archive self-comparison alone. Inherited pristine
  numerical questions and JVP/Hessian limitations remain; no transform expansion claimed.
- If this does not produce a meaningful phase reduction, retire result filtering; do not
  begin deleting host adjoint calculations or suppressing zero-valued derivative paths.
  The pending import/build profile is the next evidence request. No local benchmark,
  commit, GitHub/SSH, evaluator change or agent spawning. Deadline09:27:44 UTC unchanged.

### Candidate23 feedback and mechanism stop

- Candidate SHA **61e375cd2b712d9f2812aed686090586aec31b2c**, request/evaluation
  **edcaafd3a1754454bfbb9847e8ccfa42**, grid-1/2/3 and aligo-1/2/3. Read the complete
  own-branch receipt at experiments/runs/overnight-20261122/overnight-overhead-v1/
  edcaafd3a1754454bfbb9847e8ccfa42.json. Both official benchmarks pass3/3. Every
  reported physical output/gradient category and all14 generalization cases pass
  initial-seed tolerances. Pristine comparisons still fail with inherited patterns.
  No independent source review or results for the44 synthetic checks were supplied.
- Large fresh seconds0.8391586150974035,0.806842653080821,0.8026107437908649;
  median0.806842653080821, range0.8026107437908649–0.8391586150974035.
  Official aLIGO0.5457160733640194,0.5481212455779314,0.5545543003827333;
  median0.5481212455779314, range0.5457160733640194–0.5545543003827333.
  Historical reviewed-parent median difference: large+5.265 ms, aLIGO-0.434 ms.
  These are unpaired observations, not causal estimates. confirmed_improvement=false;
  requires_source_review, large_gain_below_selection_threshold, overlapping large
  ranges require paired evidence. Do not pool the workloads or treat medians as an
  organizer ranking policy.
- Phase medians ms large/aLIGO, computed from all three receipt samples:
  imports268.738/265.888; initialize3.606/3.600; load1.420/0.213;
  build72.766/38.241; forward lower19.654/19.229, compile33.015/33.457,
  execute187.806/32.563; sensitivity lower25.682/26.419, compile40.007/41.549,
  execute0.873/0.468; gradient lower17.074/16.581, compile51.944/53.396,
  execute87.553/14.830; host transfer0.194/0.149.
  Compared with22 (which used the parent callback), target gradient lower deltas are
  -0.177/-0.005 ms and compile deltas -0.112/+0.112 ms. These tiny, mixed, unpaired
  changes do not establish a useful phase reduction. Do not extend this mechanism
  into host derivative pruning to manufacture a larger gain.
- Sampled peak RSS bytes large628232192/645423104/508420096;
  aLIGO282529792/294793216/288849920; generalization816816128. No infrastructure
  failure or memory exceedance. CPU2, one logical CPU, library threads1, EPYC9334,
  x64, reviewed compiler flags and no persistent cache. Other-job overlap is unknown,
  contention not excluded, ranking_eligible=false.
- Generalization archiveeab46cfd48108865efcc893b94fd8a8b46cdc343ce04f8f2acfdca0e851ee2fd.
  Official array hashes112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5
  large and9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195 aLIGO.
  Seed gradient max absolute differences5.686350050382316e-6 and3.637978807091713e-11
  remain unchanged. No reported new tolerance failure; this does not certify universal
  correctness. Pristine grid signal/gradient33/161/180/loss disagreements, random
  uifo_rand1/3 log sensitivity errors2.0361e-4/5.8101e-5, unresolved grid FD coordinates
  54/59/63/136/161/163, and no host-pass JVP/Hessian support remain explicitly open.
- Decision: retire active-cotangent filtering. Restored host_pass.py to reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e; all ten simulator modules verified byte-identical
  to that strongest reviewed parent. No history reset; candidate23, its diagnostic and
  receipt remain preserved. Syntax and diff checks pass. This restoration is not a new
  speedup candidate and does not justify another unpaired benchmark-only replay.

### Coordinator handoff — obtain attribution before another variant

- End this hypothesis with ready_for_evaluation=false and stop=true. This does not end
  the authorized campaign or move its09:27:44 UTC deadline. Recent isolated sideband
  concatenation and callback-result changes supplied no meaningful phase reduction;
  repeated empty-phase confirmation supplied a tracing signal but remains unreviewed
  and lacks matched-parent evidence. Retain reviewed ee4fea2 as current simulator source.
- Next useful evidence request: run existing supervisor-only
  experiments/notes/overnight-overhead-profile.py against the restored source in fresh
  fixed-policy processes, with arbitrary supplied setup JSON and actual caller optimization
  pairs/sweep pairs/values. Obtain large, official aLIGO and one varied optical setup.
  Report function self/cumulative times and call counts for imports and build. The script
  does no forward simulation and is an instrumented attribution diagnostic, not a new
  official timing sample. Its import set is simulator/JAX/NumPy, not the complete harness
  import graph. No profiling results have been returned yet; local NumPy/JAX unavailable.
- Separately, the reproducible empty-phase tracing candidate2e50e7c/f90fa96 needs the
  pending independent review and empty/nonempty detector-phase derivative checks, then
  interleaved fresh-process candidate versus ee4fea2 on both official workloads before
  any claim of a stable gain. Do not merely resubmit identical candidate-only samples.
- Future implementation should target an attributed repeated operation, not another
  small allocation/API rewrite inferred from a whole-phase total. Possible next direction
  is reducing repeated builder-to-JAX setup dispatch only if the profile demonstrates it;
  previous whole-host staging/group staging attempts are preserved failures, not permission
  to replay them. This handoff requests evidence through the supervisor and starts no job.

### Candidate24 — linear base-matrix gather coordinates

- Supervisor resumed with an explicit request for a concrete evaluable experiment.
  No additional profile or paired-parent data accompanied that request. Candidate23
  retirement remains in force. Starting simulator is verified reviewed parent
  **ee4fea28c04d482566be16e916b609d7c6a99e5e**, not23 or an unreviewed combination.
  New candidate SHA/job identifiers pending supervisor commit and evaluation.
- Inspection found builder indexing already host-side; do not claim another removed
  eager JAX indexing compilation. The selected distinct mechanism is the representation
  of the three traced SparseSystem.base_values gathers. Each currently consumes an
  (nnz,2) coordinate constant and a rank-two matrix. New code reshapes the matrix to
  rank one and gathers with (row*width+column) offsets of shape(nnz,1). It preserves
  exact entry order, all structural entries (including current zeros), and all matrix
  derivative destinations. The transpose is the corresponding flattened scatter followed
  by reshape. No reduction, reassociation or changed optical arithmetic is introduced.
- Linear offsets are prepared from the current arbitrary setup at construction time.
  If base_values receives another width, offsets are recomputed from its actual static
  width and the same coordinates; this preserves valid direct-method calls with wider
  operands. This is metadata derived from the supplied matrix, not known-workload dispatch.
  The original base_coordinates attribute remains for compatibility. Additional stored
  offset memory is8*nnz_total bytes per system plus a width scalar. All construction is
  inside ordinary timed build; no new cache or outside-timer work.
- Cost hypothesis: one coordinate component per gathered entry instead of two may reduce
  gather lowering/address calculation and constant handling in forward and gradient
  compilation. Three matrix reshape operations are added and may cost more than this
  saves. Latest observed phase medians from23 were forward lower19.654/19.229 ms and
  compile33.015/33.457 ms large/aLIGO; gradient lower17.074/16.581 and compile51.944/53.396.
  These are whole-phase observations, not attributed recoverable costs. No new timing or
  stable gain is claimed. This differs from previous compact host-position metadata10,
  contiguous parameter scatter14, and callback-result filtering23.
- Only SparseSystem.__init__ metadata and SparseSystem.base_values differ from reviewed
  parent. Solver, refinement, adjoint, callbacks and public output functions are unchanged.
  Nine other simulator modules match parent bytes. Candidate23 restoration remains a diff
  against the last evaluated branch revision but is not part of this new mechanism.
- Local validation:2,000 executions of the ACTUAL changed base_values method with stdlib
  matrix/index stubs pass, covering1,000 arbitrary patterns with shuffled/empty selections
  at original and wider widths. They verify index arithmetic and gather options, not JAX
  transforms or performance. All simulator and diagnostic syntax checks and diff checks pass.
- Prepared experiments/notes/overnight-overhead-linear-gather-check.py with30 exact JAX
  primal/VJP comparisons against the reviewed two-coordinate gather: square/augmented
  systems, duplicate and negative writes, reserved zero-valued entries with nonzero
  derivatives, real/complex128 operands, wider matrices, empty sparse patterns, and two
  sequentially batched cases. It imports the real SparseSystem and never patches a simulator,
  benchmark or validation module. UNEXECUTED locally because NumPy/JAX are unavailable.
- Request supervisor synthetic check, both unchanged full official benchmarks on the exact
  new SHA, all saved physical outputs/gradients and14 varied-setup comparisons, independent
  source review, and paired fresh-process parent confirmation if a meaningful phase change
  appears. Report separate samples/medians/ranges, phase deltas, memory and overlap.
  Existing pristine signal/gradient/loss disagreements, uifo_rand1/3 sensitivity differences,
  unresolved grid FD54/59/63/136/161/163 and host-pass no-JVP/Hessian limitation persist.
- If this representation change has no meaningful effect, retire it without further
  flatten/slice/scatter variants absent compiler attribution. Pending import/build profiling
  remains useful; it was not supplied or launched here. No commits, remote calls, benchmarks,
  installs or agents. Absolute campaign deadline09:27:44 UTC unchanged.

### Candidate24 feedback, retirement and targeted tracing attribution

- Evaluated SHA **297e24239a332411f17963007fa9c6ceb1d1f50d**, request/job **f9eeff16240e4e14b37607ff1cd01cb1** (grid-1/2/3 and aligo-1/2/3). Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/f9eeff16240e4e14b37607ff1cd01cb1.json.
- Both unchanged official workloads passed3/3. All saved carrier/signal/noise/powers/sensitivity/loss/gradient arrays passed seed-relative policy;14 generalization cases passed seed-relative policy. This is not bitwise seed equality. Pristine comparisons still fail: grid131 signal entries,3 gradients and loss; aLIGO loss; varied setups include the inherited uifo_rand1/3 sensitivity discrepancies. No new discrepancy is identified by this receipt. Strict_passed=false, confirmed_improvement=false, source_review=null. The30 prepared synthetic JAX comparisons still have no execution result.
- grid: samples seconds=[0.8352016191929579, 0.8171110264956951, 0.8280034642666578]; median=0.828003464267; range=0.817111026496–0.835201619193. Phase medians ms={'imports': 280.052, 'initialize': 3.593, 'load': 1.516, 'build': 76.107, 'forward_lower': 20.25, 'forward_compile': 33.928, 'forward': 187.023, 'sensitivity_lower': 25.519, 'sensitivity_compile': 41.328, 'sensitivity': 0.852, 'gradient_lower': 16.638, 'gradient_compile': 53.695, 'gradient': 86.152, 'host_transfer': 0.186}.
- grid sampled process-group peak RSS bytes=[646955008, 633712640, 618778624].
- aligo: samples seconds=[0.5515841860324144, 0.5514951888471842, 0.5516271963715553]; median=0.551584186032; range=0.551495188847–0.551627196372. Phase medians ms={'imports': 265.192, 'initialize': 3.578, 'load': 0.215, 'build': 38.549, 'forward_lower': 19.711, 'forward_compile': 34.636, 'forward': 32.62, 'sensitivity_lower': 26.367, 'sensitivity_compile': 41.269, 'sensitivity': 0.496, 'gradient_lower': 16.632, 'gradient_compile': 54.966, 'gradient': 15.177, 'host_transfer': 0.159}.
- aligo sampled process-group peak RSS bytes=[280166400, 283123712, 287735808].
- Generalization peak RSS800702464 bytes. No infrastructure or memory-budget failure. Fixed EPYC9334, CPU2 affinity(one logical CPU), threads1, x64, permitted package flags, persistent cache disabled. Other-host overlap unknown; ranking_eligible=false. No combined benchmark score.
- Relative to the historical reviewed ee4fea2 cohort, medians are26.426 ms slower large and3.029 ms slower aLIGO. Unpaired cohorts do not establish causation. Forward trace/compile and gradient trace/compile provide no evidence of a useful flattened-gather effect. Do not promote or repeat flatten/slice/scatter variants without attributed compiler evidence.
- Retired24 by restoring sparse.py bytes from reviewed **ee4fea28c04d482566be16e916b609d7c6a99e5e**. All10 simulator modules now match that parent. The failed trial remains in branch history; no reset, commit or remote operation was made. This restoration is not a new performance candidate and does not warrant another candidate-only official timing run.
- Distinct next experiment prepared: extended own-branch overnight-overhead-profile.py with optional --trace-forward and --optimized-values-json. It inventories the actual built input pytree leaf counts and array bytes per argument, then cProfiles the public simulator VJP trace/lower without compiling or executing callbacks. All leaves and operations are retained; no metadata pruning or simulated optical execution. Supply actual caller optimized values, optimization pairs, sweep pairs and values with arbitrary setup JSON. Defaults are not equivalent to either official workload.
- Motivation from source: the public forward stage passes the entire built dictionary as a dynamic pytree. component_groups contains function_rows, parameter_indices and output_rows array leaves even though the valid host path returns through HostPlan without reading these dynamic groups. JAX must flatten/abstract those inputs before unused arguments are eliminated. The cost is not measured; static wrapping could alter mutation/rebuild and transform behavior and should not be implemented speculatively. This experiment will distinguish pytree/abstractification overhead from actual scatter/gather/callback lowering and import/build time. Ask the supervisor to run this diagnostic on the reviewed parent for large, official aLIGO and a third supplied setup, in separate fresh fixed-policy processes. No diagnostic launched here.
- Diagnostic results are instrumented attribution, not official timing, speedup or numerical validation. Local syntax/CLI checks only: NumPy/JAX unavailable. Pending general import/build profiling and matched-parent confirmation of candidate15/21 remain separate; do not replay candidate-only samples as confirmation.
- Existing grid FD54/59/63/136/161/163, pristine gradients33/161/180, random-case sensitivity disagreements and first-order-only host VJP remain unresolved. No tolerances, fixtures, workloads, flags or solver mathematics changed. This closes the unproductive coordinate-representation hypothesis; the newly authorized campaign deadline remains09:27:44 UTC.

### Candidate25 — static immutable component dispatch metadata

- Supervisor explicitly resumed after24 retirement and requested one concrete evaluable
  implementation. No import/build/trace profile accompanied the request. This is a new
  hypothesis based on source-proven unused dynamic inputs, not a measured attribution.
  Simulator parent is reviewed ee4fea28c04d482566be16e916b609d7c6a99e5e. Candidate SHA and
  both official job identifiers are pending supervisor commit/evaluation. No changes from
  unpromoted15/21/23/24 are combined. The sparse.py diff against branch HEAD retires24.
- The public forward JIT receives the complete simulation_arrays pytree. The host path
  reads its static HostPlan and does not use component_groups' integer leaves, but those
  leaves still participate in input flattening, abstractification and initial tracing.
  New StaticComponentGroups is registered as a no-leaf static mapping. It snapshots the
  nested dictionary structure while retaining immutable integer JAX arrays; rejects
  floating/complex arrays and mutable host arrays/lists. It stores no physical values,
  computed simulation output, gradient or factorization. Ordinary physical arguments and
  the other integer selector arguments retain their existing dynamic representation.
- Wrap only after successful host-plan construction and when HOST_PASS is enabled.
  Sparse/dense fallback inside simulate converts the full mapping back to dictionaries;
  _build_sparse_structure and build_host_plan also accept the wrapper for explicit rebuilds.
  Keys, indexing, iteration, get/items and the actual metadata arrays remain accessible.
  to_dict()/copy() produce fresh mutable nested dictionaries. Hand-supplied ordinary dicts
  remain supported and dynamic. No changes to gathers, scatters, callback signatures,
  physical functions, solver, refinement or adjoint arithmetic.
- Compatibility tradeoff is explicit: builder-returned component_groups is a read-only
  Mapping rather than a dict on successful host builds. Direct in-place structural edits
  raise; callers should rebuild plans after index changes as already required. Tree-map
  operations no longer transform these structural leaves. Equality/hash use object identity;
  every new build has a new identity and retraces even for equal-shaped or identical layouts.
  This avoids content-dependent stale JIT reuse but can increase recompilation for repeated
  builds. This is not a claim of unrestricted JAX transform/API compatibility. Frozen nested
  dictionaries prevent mutation of the source dictionary or a returned copy from changing
  an existing static object. Private object.__setattr__ bypasses are not a supported API.
- Cost hypothesis: fewer dynamic inputs may reduce forward trace/lower overhead, measured
  around20.250 ms large and19.711 ms aLIGO in24, and possibly downstream AD bookkeeping.
  Full forward compile was33.928/34.636 ms, gradient trace16.638/16.632 ms and compile
  53.695/54.966 ms. These whole-phase medians are not recoverable-cost estimates. Building
  nested mapping snapshots adds Python allocation; import registration and retained static
  objects also have cost. No timing gain claimed. All work stays inside ordinary build/import.
- Local checks:100 executions of the actual class with stdlib array stubs validate snapshot
  isolation, nested copy independence, immutability guards and distinct build identities;
  six unsupported leaf types rejected. These do not test JAX. All simulator and new diagnostic
  AST checks pass; eight otherwise untouched simulator modules match reviewed parent bytes.
- Prepared overnight-overhead-static-groups-check.py for the supervisor: eight actual optical
  component JIT primal/VJP comparisons across empty/single/multiple groups and real/complex
  parameter values including zeros; four metadata round trips; no-leaf tree registration;
  two equal-shaped builds with changed indices and JIT retrace checks; rejected mutations;
  a small laser/space/mirror graph with a three-frequency sweep and two optimized parameters
  verifies actual builder integration and sparse/host plan reconstruction from both metadata
  representations. This script is UNEXECUTED locally: NumPy/JAX are unavailable. It reads
  no fixtures and runs no official benchmark or timing loop. Run it against this candidate,
  not retired candidates' incompatible diagnostic scripts.
- Request both unchanged full official benchmarks on the exact new SHA; inspect all saved
  physical outputs/gradients and14 varied generalization cases against parent/seed/pristine;
  run independent source review with particular attention to metadata mutation and fallback
  behavior. If tracing improves meaningfully, obtain matched interleaved fresh-process parent
  and candidate cohorts, separate large/aLIGO samples/medians/ranges, phase tradeoffs, RSS and
  overlap state. Do not infer success from fewer leaves alone or from a single timing sample.
- Existing pristine signal/gradient/loss differences, uifo_rand1/3 sensitivity disagreements,
  unresolved grid FD54/59/63/136/161/163 and first-order-only host VJP remain open. Candidate24
  failure remains recorded above. No tolerance, arithmetic flag, benchmark or fixture changes.
  No commits, pushes, remote jobs, installs or agents. Deadline remains09:27:44 UTC.

### Candidate25 feedback and retirement

- Evaluated SHA **6e1b40c40a91f75e48b162d06ba6a9f5ec6e525a**, request/job **f9bd5bf1345840e7b14f688361d7c8eb**, grid-1/2/3 and aligo-1/2/3. Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/f9bd5bf1345840e7b14f688361d7c8eb.json.
- Both unchanged official benchmarks passed3/3. All physical arrays and gradients passed initial-seed policy in six official runs and14 generalization cases. No new numerical failure is identified by this receipt. Strict pristine comparisons remain failing, including grid signal/gradient/loss, aLIGO loss and uifo_rand1/3 sensitivity. source_review=null and confirmed_improvement=false. The prepared static-groups JAX diagnostic has no returned execution result.
- grid: fresh-process samples seconds=[0.8357062265276909, 0.8071517646312714, 0.8087208960205317]; median=0.808720896021; range=0.807151764631–0.835706226528. Phase medians ms={'imports': 269.67, 'initialize': 3.621, 'load': 1.501, 'build': 73.54, 'forward_lower': 19.327, 'forward_compile': 33.106, 'forward': 181.993, 'sensitivity_lower': 25.705, 'sensitivity_compile': 41.333, 'sensitivity': 0.907, 'gradient_lower': 17.298, 'gradient_compile': 52.346, 'gradient': 88.129, 'host_transfer': 0.195}.
- grid: sampled process-group peak RSS bytes=[670035968, 540426240, 506347520].
- aligo: fresh-process samples seconds=[0.550236152485013, 0.5601429101079702, 0.5492269955575466]; median=0.550236152485; range=0.549226995558–0.560142910108. Phase medians ms={'imports': 267.443, 'initialize': 3.559, 'load': 0.209, 'build': 39.079, 'forward_lower': 18.711, 'forward_compile': 34.589, 'forward': 32.613, 'sensitivity_lower': 26.614, 'sensitivity_compile': 41.898, 'sensitivity': 0.486, 'gradient_lower': 16.991, 'gradient_compile': 54.18, 'gradient': 14.475, 'host_transfer': 0.151}.
- aligo: sampled process-group peak RSS bytes=[279416832, 286810112, 294367232].
- Generalization peak RSS893042688 bytes; archive8821ecf63fd7d4512d134a8835bfece3ac4c1ea37a6ea2352cd45926afc8fc4f. Official arrays retain hashes112c0407...large and9c1ce936...aLIGO. Seed maximum absolute gradient differences remain5.686350050382316e-6 large and3.637978807091713e-11 aLIGO; tolerance agreement is not bitwise seed equality. No infrastructure or budget failure. CPU2/one logical CPU, library threads1, EPYC9334, x64, permitted flags and no persistent cache. Other-host overlap unknown; ranking_eligible=false.
- Compared with historical reviewed ee4fea2, median totals are7.143 ms slower large and1.681 ms slower aLIGO. Ranges overlap; these are unpaired observations, not causal regressions. Against recent ordinary-metadata candidate23, forward trace medians differ by only-0.327 ms large/-0.518 ms aLIGO; gradient trace differs by+0.224/+0.410 ms. Candidate23 changed callback filtering, so this comparison is contextual, not a matched-parent test. No repeat-supported gain justifies immutable-metadata API restrictions or extra repeated-build recompilation.
- Decision: retire25 and restore host_pass.py and simulate.py from reviewed ee4fea2. All10 simulator modules verified byte-identical to that parent. Failed25 remains committed in branch history, and its diagnostic remains for audit but requires25 source. Restoration removes the wrapper and all changed metadata semantics. Do not submit the restoration as another performance candidate.
- Search direction: no further static-wrapper, leaf-pruning or gather-coordinate variants without attribution. The next concrete experiment is the prepared supervisor-only overnight-overhead-profile.py --trace-forward on the reviewed parent with actual caller setup/pairs/optimized values/sweep inputs. Capture cProfile self/cumulative times and input leaf counts for large, official aLIGO and a third supplied setup. Its results must distinguish JAX input processing from callback/scatter lowering and builder dispatch. No profiling result has been supplied; do not report the hypothesis as measured or launch independent profiling/benchmarks from this managed agent.
- Separate outstanding evidence: candidate15/21 empty-phase change has repeated candidate-only tracing reductions but still lacks independent source review, nonempty detector-phase derivative checks and interleaved parent comparison. Request that confirmation rather than another identical candidate-only replay. No merge or new performance claim is authorized by these observations.
- Inherited pristine gradients33/161/180, uifo_rand1/3 sensitivities and grid FD54/59/63/136/161/163 remain unresolved; first-order-only host VJP limitation remains. No tolerance, arithmetic setting, workload or fixture edits. This closes the static-metadata hypothesis only; the campaign deadline remains09:27:44 UTC.


### Candidate26 — remove redundant normalized sweep copy

- Supervisor resumed explicitly requesting a concrete implementation after25 retirement.
  Parent for this experiment is reviewed **ee4fea28c04d482566be16e916b609d7c6a99e5e**.
  Candidate SHA and large/aLIGO job identifiers are pending supervisor commit/evaluation.
  host_pass.py/simulate.py changes against branch HEAD remove25; the only new delta against
  ee4fea2 is the replacement below in build.py. No other unpromoted trial is combined.
- Source-proven redundant operation: prepare_arrays converts supplied sweep values through
  np.asarray, normalizes one-dimensional input to a row, then calls jnp.asarray. It immediately
  copies that normalized JAX array back to NumPy with np.array and calls jnp.asarray again
  for signal_changing_values. Reuse the already normalized immutable JAX array instead.
  This removes one host copy/device-to-host conversion and one JAX conversion per supplied
  sweep. In carrier-only/no-active-sweep paths the second converted array was discarded
  when the signal dummy was assigned, so its removal also avoids that unused allocation.
- Existing initial conversion, dtype canonicalization, shape normalization, errors, dummy
  values and returned JAX array representation remain. Only one of carrier/signal sweeps
  may be active; their simultaneous use still raises. This does not omit the initial
  np.asarray of a caller-provided JAX array or relax the existing concrete build boundary.
  No values are cached between builds/evaluations. Public metadata remains ordinary dicts.
  No solver, physical function, derivative rule, callback, JIT stage or compiler flag changes.
- Cost breakdown available from25 receipt (whole-phase medians, not candidate26 measurements):
  large imports269.670 ms, build73.540 ms, trace/lower total62.330 ms, compile126.785 ms;
  aLIGO imports267.443 ms, build39.079 ms, trace/lower62.316 ms, compile130.667 ms.
  The targeted redundant copy is only a fraction of build time and transfers a small sweep
  array on the official workloads. It may fall below timing noise or the selection threshold.
  No measured speedup, per-operation cost or recovered percentage is claimed. This narrow
  copy removal does not repeat18's metadata staging or25's static-pytree/API changes.
- Local checks: all10 simulator modules parse; byte comparison against ee4fea2 confirms the
  exact one-assignment replacement plus its comment is the entire new simulator delta.
  git diff --check passed. NumPy/JAX runtime checks were not run locally because the local
  environment lacks those dependencies; no installs or independent benchmarks were started.
- Request both unchanged full official benchmarks on the supervisor's exact new SHA, all
  saved outputs/gradients and the14 varied generalization cases. Include ordinary carrier
  and signal sweeps in review; dtype/shape/signed-zero behavior should match because the
  original first conversion is retained. Independent source review is required for promotion.
  If a benefit appears, compare interleaved fresh parent/candidate cohorts under identical
  CPU/thread policy, reporting separate large/aLIGO samples, medians, ranges, phases, RSS
  and overlap. Do not infer a gain from eliminating a copy alone.
- If26 is below threshold, retire it rather than accumulate further tiny conversion variants.
  Next evidence request remains supervisor import/build/trace profiling using the prepared
  diagnostic on ee4fea2; no such profile has been returned. Candidate15/21 phase reductions
  remain a separate unreviewed experiment awaiting paired-parent and nonempty-phase checks.
- Candidate25 failures remain above and in history. Inherited pristine signal/gradient/loss
  disagreements, gradients33/161/180, uifo_rand1/3 sensitivity errors, unresolved grid
  FD54/59/63/136/161/163 and the first-order-only host VJP remain open. No tolerances,
  fixtures or workloads changed. This is an unevaluated setup candidate, not a promotion.
  Deadline remains2026-11-22 09:27:44 UTC; prepared04:33 UTC.


### Candidate26 feedback and retirement

- Evaluated SHA **7666a10f3deb2a6b1aa32c32d8bfeb9436b81d29**, request/job **8eeab1988cdd45fb875394e403e49cb0**; grid-1/2/3 and aligo-1/2/3. Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/8eeab1988cdd45fb875394e403e49cb0.json.
- Both unchanged official benchmarks passed3/3; all saved arrays/gradients passed initial-seed policy in six official runs and14 generalization cases. Strict pristine comparisons retain the inherited disagreements. No new numerical failure is identified in this receipt. source_review=null; confirmed_improvement=false; no promotion.
- grid: samples seconds=[0.8304953221231699, 0.7930362112820148, 0.8082717321813107]; median=0.808271732181; range=0.793036211282–0.830495322123. Phase medians ms={'imports': 266.201, 'initialize': 3.495, 'load': 1.461, 'build': 73.998, 'forward_lower': 19.544, 'forward_compile': 33.026, 'forward': 184.235, 'sensitivity_lower': 25.539, 'sensitivity_compile': 39.744, 'sensitivity': 0.863, 'gradient_lower': 16.548, 'gradient_compile': 52.25, 'gradient': 86.168, 'host_transfer': 0.188}.
- grid: sampled process-group peak RSS bytes=[686661632, 525324288, 623800320].
- aligo: samples seconds=[0.5472959391772747, 0.5450863540172577, 0.5440386086702347]; median=0.545086354017; range=0.544038608670–0.547295939177. Phase medians ms={'imports': 265.331, 'initialize': 3.594, 'load': 0.209, 'build': 38.33, 'forward_lower': 19.139, 'forward_compile': 33.143, 'forward': 32.895, 'sensitivity_lower': 26.084, 'sensitivity_compile': 41.172, 'sensitivity': 0.48, 'gradient_lower': 16.776, 'gradient_compile': 53.062, 'gradient': 14.466, 'host_transfer': 0.151}.
- aligo: sampled process-group peak RSS bytes=[282034176, 314556416, 315469824].
- Generalization archive cc0a1950b691acf1ed2d127f4958a0c26ac089f4bdffea89d84e87d1de1db623; peak RSS949866496 bytes. Official array hashes remain112c0407...large and9c1ce936...aLIGO. Initial-seed maximum absolute gradient differences remain5.686350050382316e-6 large and3.637978807091713e-11 aLIGO; tolerance agreement does not establish bitwise seed equality. No infrastructure or memory-budget failure. EPYC9334, CPU2(one logical CPU), threads1, x64, unchanged permitted flags, no persistent compilation cache. Other-host overlap unknown; ranking_eligible=false.
- Versus historical reviewed ee4fea2 totals, large median is6.694 ms slower and aLIGO3.469 ms faster; both ranges overlap the parent. These are unpaired observations, not causal changes. The targeted build medians are73.998 ms large and38.330 ms aLIGO; compared with25 they differ by+0.458/-0.749 ms. Candidate25 had a different metadata implementation, so this is contextual only. One large build was68.881 ms, but the other two were73.998/75.127 ms: no stable targeted gain is established.
- Decision: retire26 and restore build.py to reviewed **ee4fea28c04d482566be16e916b609d7c6a99e5e**. All10 simulator modules match that parent byte-for-byte. Failed26 stays in branch history. Do not evaluate this restoration as a new optimization. No further small conversion/copy variants without measured attribution.
- Next coordinator action: run the existing experiments/notes/overnight-overhead-profile.py diagnostic on reviewed ee4fea2 with --trace-forward, supplying actual setup JSON, optimization pairs, optimized values, changing pairs and changing values for each caller. Request large, official aLIGO and a third optical setup as separate fresh-process attribution runs. This instrumented diagnostic does not substitute for official timings; it identifies import/build/trace call costs. No profiling result has been returned and this agent has not launched the diagnostic or any benchmark.
- A separate stronger confirmation target remains candidate15/21 structural empty-phase elimination: request independent source review, the prepared empty/nonempty phase derivative check, and interleaved fresh parent/candidate cohorts on matching resource policy. Do not combine26 or infer confirmation from another candidate-only replay. This request preserves the stronger hypothesis without inventing a new simulator variant.
- Existing pristine gradients33/161/180, uifo_rand1/3 sensitivity disagreements, grid FD54/59/63/136/161/163 and first-order-only custom VJP limitations remain unresolved. No tolerance, fixture, workload or flags changed. Syntax and diff checks passed. Stops the sweep-copy hypothesis, not the new campaign; absolute deadline remains2026-11-22 09:27:44 UTC.


### Candidate27 — isolate structurally empty selector scatter

- Supervisor explicitly resumed after26 retirement and requested a concrete next experiment.
  Parent: reviewed ee4fea28c04d482566be16e916b609d7c6a99e5e. Candidate SHA and both official
  job identifiers pending. build.py restoration retires26; the sole new simulator change
  against ee4fea2 is inside _simulate_host_pass in simulate.py. No unpromoted changes combined.
- Evidence motivating this narrower experiment:15 (2e50e7cffc8c7feb5ae53dc770e26cbb45250ab8,
  b699b389623a46c98a1e34c803ca18d8) and its replay21 (f90fa964a73aca5515ba93a3517ec1d26ae32a32,
  a4d2cd8dcf5f448aafa8d2817fb59644) both showed forward trace around14 ms and gradient trace
  around13 ms, compared with26's19.544/16.548 ms large and19.139/16.776 ms aLIGO. Those were
  candidate-only observations, not matched-parent confirmation or promotion.15 eliminated
  both phase construction and scatter, passing None through the helper.27 isolates the
  empty scatter only, retaining all arrays and the original phase construction/API.
- Mechanism: a scatter multiplication with no updates/destinations is the identity. For an
  empty one-dimensional complex128 update array, zero integer destination entries and a
  rank-three complex128 selector operand, bypass that scatter. Conditions depend only on
  static array metadata, never values, setup identity or workload size. All other cases
  execute the exact original lax.scatter_mul. No current zero phases or selectors are pruned.
  Physical outputs, callback inputs/residuals, solver mathematics and three JIT stages remain.
- Unlike15, exp/radians/gather for phases still trace. Expected benefit is limited to empty
  scatter lowering and its AD bookkeeping; it may be smaller than15 or absent.26 measured
  forward compile33.026/33.143 ms and gradient compile52.250/53.062 ms (large/aLIGO); these
  whole phases are not estimates of recoverable cost. No27 timing or speedup claimed.
- Local checks:72 executions of the actual guard expression with stdlib shape/dtype stubs
  cover empty/nonempty/malformed-rank phases, destinations, integer/noninteger indices,
  selector ranks and complex128/complex64. Nonempty scatter AST matches parent exactly.
  Nine other simulator files match ee4fea2; syntax/diff checks pass. These are structural
  checks, not JAX execution or a derivative certificate.
- Prepared experiments/notes/overnight-overhead-empty-scatter-check.py for supervisor use:
  extracts actual phase construction and actual conditional scatter; compares JIT primal
  and VJPs with the unconditional parent operation in ten cases. Includes two empty selector
  layouts, nonempty placements, repeated phase parameter indices with unique destinations,
  nonzero/zero phases, and zero-valued selectors. Checks that empty cases omit scatter while
  retaining exp, and nonempty cases retain both primitives. UNEXECUTED locally: NumPy/JAX
  unavailable. No fixtures, benchmark calls or timing loop in this diagnostic.
- Request both unchanged official benchmarks and full saved arrays/gradients on exact new SHA;
  fourteen varied generalization cases, the focused diagnostic and independent source review.
  If the phase reduction recurs, require interleaved fresh parent/candidate measurements on
  matched CPU/thread policy, separate samples/medians/ranges, phase deltas, RSS and overlap.
  Compare with15 only as attribution, not as evidence that combining edits is validated.
-26 remains retired and preserved. Inherited pristine signal/gradient/loss disagreements,
  gradients33/161/180, uifo_rand1/3 sensitivity errors, unresolved grid FD54/59/63/136/161/163
  and first-order-only host VJP remain open. No tolerances, fixtures, flags or workloads changed.
  If27 does not isolate a useful effect, end this empty-scatter refinement and obtain the
  outstanding supervisor profile rather than more equivalent scatter variants.

### Candidate27 feedback — freeze for confirmation, no promotion

- Evaluated SHA **7213fe61c461f63824d1632de3ee22c075abbe62**, request/job
  **fc011736e58c4fadae64c96444b347c4**, grid-1/2/3 and aligo-1/2/3. Receipt:
  experiments/runs/overnight-20261122/overnight-overhead-v1/fc011736e58c4fadae64c96444b347c4.json.
  Both unchanged official benchmarks passed 3/3. All six saved official output/gradient
  comparisons and all fourteen generalization cases passed initial-seed tolerances.
  Pristine comparisons retain the inherited disagreements. No new numerical failure is
  identified by these results; source_review=null and confirmed_improvement=false.
- Large complete fresh-process seconds: [0.8174483720213175, 0.792569087818265,
  0.7870335020124912]; median 0.792569087818265, range
  0.7870335020124912–0.8174483720213175. aLIGO separately:
  [0.53992441855371, 0.6041343584656715, 0.5329861268401146]; median
  0.53992441855371, range 0.5329861268401146–0.6041343584656715.
  Large range overlaps reviewed ee4fea2; aLIGO relative range 13.1774% exceeds the
  team's 10% stability heuristic. Keep all samples, including aLIGO-2.
- Phase medians in milliseconds, large/aLIGO: imports 266.698/270.294;
  initialize 3.527/3.514; load 1.508/0.255; build 74.394/37.831;
  forward lower 17.370/16.800, compile 30.681/31.012, execution 179.307/32.651;
  sensitivity lower 25.560/26.610, compile 39.662/41.543, execution 0.866/0.484;
  gradient lower 13.293/13.301, compile 51.507/52.424, execution 84.920/14.409;
  host transfer 0.187/0.142. Against26, forward lowering is lower by 2.174/2.339 ms
  and gradient lowering by 3.255/3.475 ms. These are unpaired observations of different
  revisions, not causal attribution or a confirmed complete-run gain. Against historical
  ee4fea2 totals, median differences are -9.009 ms large and -8.631 ms aLIGO; these
  likewise do not satisfy matched-parent confirmation.
- The slow aLIGO-2 has larger import, forward lowering/compilation and sensitivity
  lowering/compilation times; gradient compilation is similar. This does not identify
  the cause of the slowdown, establish external contention, or justify discarding it.
- Sampled peak process-group RSS bytes: large [507854848, 510963712, 524447744];
  aLIGO [295366656, 281542656, 295178240]; generalization 804278272.
  No infrastructure or memory-budget failure. EPYC9334, CPU2 (one logical CPU), threads1,
  x64, unchanged permitted flags, no persistent compilation cache. Other-host overlap
  unknown; ranking_eligible=false. RSS sampling can miss brief peaks.
- Official array archives remain 112c0407... large and 9c1ce936... aLIGO. Generalization
  archive f4fc6263bb6ad41c6d883baee45241e31c723332594e184be8a6fd7b992d6d4b.
  Initial-seed maximum absolute gradient differences remain 5.686350050382316e-6 large
  and 3.637978807091713e-11 aLIGO; tolerance agreement is not bitwise seed equality.
  Pristine signal/gradient/loss discrepancies, gradients33/161/180, uifo_rand1/3
  sensitivity disagreements, grid FD54/59/63/136/161/163 and first-order-only host VJP
  limitations remain unresolved. The focused JAX empty/nonempty scatter diagnostic
  is still UNEXECUTED locally; no supervisor result for it has been supplied.
- Decision: preserve27 exactly for confirmation, with no additional simulator edits.
  Stop further empty-scatter variants. Reviewed ee4fea2 remains the admitted parent;
  27 is not promoted. This differs from retiring26: the targeted trace reduction warrants
  a controlled confirmation, but the existing candidate-only cohort is insufficient.
- Concrete next supervisor experiment: independently review ee4fea2..7213fe6, execute
  experiments/notes/overnight-overhead-empty-scatter-check.py on27, then collect five
  interleaved fresh-process runs per revision per unchanged official setup under identical
  resource policy. Compare27 with exact ee4fea2, retain every sample, report phase deltas,
  RSS and known job overlap separately for large and aLIGO, and retain full arrays/gradients
  plus the fourteen-case generalization audit. No new candidate-only replay or combination
  is requested. If this fails to establish a stable gain, retire27 and obtain the already
  prepared import/build/trace profile before choosing another implementation mechanism.
- This handoff stops the empty-scatter hypothesis pending that evidence, not the authorized
  campaign. No independent benchmark, install, commit or agent spawn was performed.
  Recorded 2026-11-22 04:45 UTC; absolute deadline remains 2026-11-22 09:27:44 UTC.

### Candidate28 — retain the already computed unique write positions

- Supervisor resumed with a request for a concrete evaluable change. Candidate27 remains
  preserved at7213fe61c461f63824d1632de3ee22c075abbe62 with its confirmation request above;
  it is not combined into28. Restored simulate.py to reviewed ee4fea2. Candidate28's sole
  simulator delta against ee4fea28c04d482566be16e916b609d7c6a99e5e is in SystemPlan.__init__.
  New SHA and both official job identifiers are pending supervisor submission.
- Source evidence: the constructor calls np.unique(writes[::-1], return_index=True),
  discards its unique-values result, then calls np.unique(writes) for self.written.
  These inputs are the same flattened int64 positions in reverse order; their sorted
  unique values are identical. Retain the first result for self.written. The original
  return_index calculation and last-write mask remain unchanged, including duplicates
  and empty arrays. No numerical values, zero-valued parameters or derivative slots
  are removed. The metadata digest and all forward/backward methods are unchanged.
- Cost hypothesis: remove one redundant np.unique invocation and its result allocation
  from each of the carrier, signal and noise SystemPlan constructors (three per build).
  No cache, extra build pass or new mutable state. This is a small setup experiment;
  no timing benefit is claimed. NumPy versions may use different uniqueness algorithms,
  so the initial description of two sorts is not a measured algorithm attribution.
  The actual established redundancy is computing the same unique values twice.
- Available cost context from27: build medians74.394 ms large and37.831 ms aLIGO;
  imports266.698/270.294 ms; forward lowering17.370/16.800 ms and gradient lowering
  13.293/13.301 ms. Those are phase totals from a different candidate, not the expected
  savings or a current parent calibration.28 does not retain27's scatter tracing reduction.
- Local validation: all ten simulator modules compile as Python source; nine match
  reviewed ee4fea2 byte-for-byte. Reversing the two changed assignments/comment restores
  host_pass.py byte-for-byte to that parent. No NumPy/JAX execution was performed locally
  because those dependencies are unavailable, and no dependencies were installed.
  No independent timings or benchmarks were launched.
- Request both unchanged full official benchmarks on the exact new SHA, complete saved
  outputs/gradients, fourteen-case seed/pristine generalization comparisons and independent
  source review. The metadata equivalence argument covers arbitrary integer write orders,
  including repeated destinations; evaluation must still confirm unchanged physical results.
  Any apparent millisecond gain requires matched interleaved fresh parent/candidate runs,
  separate phase medians/ranges and memory/overlap reporting. Do not promote a single sample.
- If no stable setup gain appears, retire28 rather than try further unique/sort microvariants.
  Next evidence request is the already prepared supervisor import/build/trace profile;
  candidate27 confirmation remains separate. Inherited pristine signal/gradient/loss
  discrepancies, gradients33/161/180, uifo_rand1/3 sensitivity errors, unresolved grid
  FD54/59/63/136/161/163 and first-order-only host VJP remain open. No workload, tolerance,
  fixture, flags, solver/refinement or adjoint mathematics changed.

### Candidate28 feedback and retirement

- Exact SHA **e29fe2a18582f332aa755ec7141adb066e5e901c**, evaluation
  **41d353f067ba4ee7a6b45621704d61f7**, grid-1/2/3 and aligo-1/2/3. Receipt:
  experiments/runs/overnight-20261122/overnight-overhead-v1/41d353f067ba4ee7a6b45621704d61f7.json.
  Both official benchmarks passed3/3; all saved physical outputs/gradients passed the
  initial-seed comparison policy, as did fourteen generalization cases. Pristine failures
  remain inherited. No new numerical failure identified; no source review supplied.
- Large seconds [0.8387086167931557, 0.7954129409044981, 0.8073403798043728];
  median0.8073403798043728, range0.7954129409044981–0.8387086167931557.
  aLIGO separately [0.5467080846428871, 0.5456180926412344, 0.5434959325939417];
  median0.5456180926412344, range0.5434959325939417–0.5467080846428871.
  confirmed_improvement=false. Historical ee4fea2 median differences +5.763 ms large,
  -2.937 ms aLIGO; ranges overlap. These unpaired observations do not establish causality.
- Phase medians ms, large/aLIGO: imports267.076/265.117; initialize3.516/3.548;
  load1.558/0.211; build73.789/38.207; forward lower19.560/19.185,
  compile32.929/33.548, execute185.004/32.570; sensitivity lower25.563/26.447,
  compile41.044/41.328, execute0.876/0.468; gradient lower16.658/16.537,
  compile53.124/53.150, execute85.614/14.270; host transfer0.187/0.153.
  Build medians differ from26 by only -0.209/-0.123 ms, and from27 by -0.605/+0.376 ms.
  Those revisions differ in other ways; none supplies matched-parent attribution.
  No stable targeted build gain or complete-first-run improvement is established.
- Sampled peak process-group RSS bytes: large [608301056,506638336,622731264];
  aLIGO [281747456,295309312,295772160]; generalization874868736. No infrastructure
  or memory-budget failure. EPYC9334 CPU2, one logical CPU, library threads1, x64,
  unchanged permitted flags, no persistent compilation cache. Overlap unknown;
  ranking_eligible=false. Sampling can miss brief memory peaks.
- Generalization archive17a321c86c92eddee5e7a15955dca818ae4a53956243b1edefced4f90cd33c5b.
  Official archive hashes remain112c0407...large and9c1ce936...aLIGO; seed maximum
  absolute gradient differences remain5.686350050382316e-6 and3.637978807091713e-11.
  Seed tolerance passes do not establish bitwise equality or pristine agreement.
- Decision: retire28, preserve its evaluated commit/results, and restore host_pass.py
  to reviewed ee4fea28c04d482566be16e916b609d7c6a99e5e. All ten simulator modules now
  match that parent byte-for-byte. The restoration is not a new optimization candidate.
  No further unique/sort metadata variants without attribution evidence.
- Next experiment is measurement, not another implementation guess: supervisor to run
  the existing overnight-overhead-profile.py with --trace-forward on exact ee4fea2,
  supplying actual setup, optimization pairs/values and sweep pairs/values for large,
  official aLIGO and a third setup. Return import/build/trace call costs and pytree inventory.
  No such profile has been supplied. Separately,27's independent review, focused derivative
  diagnostic and matched-parent cohort remain pending; do not combine or promote27.
- Pristine signal/gradient/loss mismatches, gradients33/161/180, uifo_rand1/3 sensitivity
  disagreements, unresolved grid FD54/59/63/136/161/163 and first-order-only custom VJP
  remain open. Stop this metadata-reuse hypothesis, not the authorized campaign.
  Absolute deadline remains2026-11-22 09:27:44 UTC. No independent benchmark or install.

### Candidate29 — stage the callback adapter behind a nested JIT boundary

- Supervisor explicitly resumed after28's retirement and requested a concrete new
  experiment. Retain28's restoration of host_pass.py to reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e; do not retain28's unique-write reuse.
  All simulator modules match that reviewed parent except simulate.py, whose only
  executable delta is @jit on _simulate_host_pass. New SHA and both official job
  identifiers are pending supervisor submission. History and prior feedback remain.
- This is a different mechanism from metadata reuse, empty-operation removal or
  callback orientation. The adapter performs phase scatter, sparse base gathers,
  casts, the existing custom-VJP callback and output transposes. A nested JIT gives
  JAX a staged call boundary for forward linearization and transpose generation.
  Hypothesis: reducing Python-level transformation work across this boundary may
  reduce forward/gradient lowering overhead. No redundant physical calculation is
  alleged or removed. First staging has overhead and may make this candidate slower.
- There is no precompile, warm-up, evaluation-result cache, persistent compilation
  cache or launch change. The decorator creates a callable at import; its staging
  happens when called. The official outer forward, sensitivity and gradient JIT
  stages remain. Every callback and all solver/refinement/adjoint math are unchanged.
  The existing HostPlan static pytree registration supplies structure; numeric inputs
  remain dynamic. Passing phase placement indices through a nested call may add
  operands to the staged program; count that overhead rather than assume elimination.
  Eager calls to this internal adapter now compile it, a compatibility/performance
  tradeoff requiring review. No new JVP/Hessian support is claimed.
- Cost context from evaluated28, not a matched-parent baseline: median forward lower
  19.560/19.185 ms and gradient lower16.658/16.537 ms (large/aLIGO); forward compile
  32.929/33.548 ms, gradient compile53.124/53.150 ms. Sensitivity lower/compile remain
  25.563/41.044 ms large and26.447/41.328 ms aLIGO. Imports267.076/265.117 ms and
  build73.789/38.207 ms are not the target. Complete first-run medians of28 were
  0.8073403798043728 s large and0.5456180926412344 s aLIGO; no29 timings exist.
- Local checks: all ten simulator modules compile as Python source; nine are exactly
  reviewed-parent bytes. Removing the one new decorator yields an AST identical to
  the reviewed simulate.py. git diff --check passes. No NumPy/JAX execution locally,
  no installs, independent benchmarks, commits or spawned agents.
- Prepared experiments/notes/overnight-overhead-nested-jit-check.py, UNEXECUTED.
  It extracts the actual adapter and custom-VJP boundary into an isolated namespace,
  uses actual SparseSystem gathers, and substitutes only toy host math reused from
  the older callback diagnostic. It compares the nested wrapper with its unwrapped
  reference for twelve tiny cases: two structural patterns, empty/one/two phase
  placements and repeated calls with changed numeric inputs. It checks primals and
  all eight differentiable input cotangents, including zero current base entries,
  zero selectors and zero phase angles. This diagnoses staging compatibility only;
  it is not an optical solver or universal transform correctness certificate.
- Supervisor request: run that focused diagnostic, then both unchanged full official
  benchmarks on the exact candidate SHA, all saved arrays/gradients, fourteen-case
  seed and pristine comparisons, and independent source review. Compare with exact
  ee4fea2 in matched interleaved fresh processes if promising; report each sample,
  separate medians/ranges, all phase costs, RSS and known overlap. Three official
  stages must remain visible and all compilation included. Do not promote from a
  warm-only result or unpaired millisecond shift. Earlier27 confirmation is separate.
- If no stable lowering and complete-first-run gain appears, retire this boundary
  experiment and return to reviewed parent; do not cycle decorator options blindly.
  Next evidence request remains the prepared supervisor import/build/trace profile.
- Inherited pristine signal/gradient/loss discrepancies, gradients33/161/180,
  uifo_rand1/3 sensitivity disagreements, unresolved grid FD54/59/63/136/161/163 and
  first-order-only host VJP remain open. Candidate29 changes no tolerance or physical
  workload. Absolute deadline remains2026-11-22 09:27:44 UTC.

### Candidate29 feedback and retirement

- Exact SHA **7b7a6d391f820ae7acf49336ff84896005c688a4**, evaluation
  **48f282121cdc44c09eaf485c10f5f248**, grid-1/2/3 and aligo-1/2/3. Receipt:
  experiments/runs/overnight-20261122/overnight-overhead-v1/48f282121cdc44c09eaf485c10f5f248.json.
  Official passes3/3 for each workload; saved arrays/gradients and all fourteen
  generalization cases pass initial-seed tolerance checks. Pristine comparisons
  retain inherited failures. No infrastructure failure or new numerical failure
  identified. Independent source review and focused synthetic test results were not
  supplied; the prepared diagnostic remains unexecuted on the evidence available.
- Large seconds [0.8827177360653877,0.7992416713386774,0.7992088962346315];
  median0.7992416713386774, range0.7992088962346315–0.8827177360653877.
  aLIGO separately [0.550218353047967,0.5518978741019964,0.5532072186470032];
  median0.5518978741019964, range0.550218353047967–0.5532072186470032.
  confirmed_improvement=false. Large relative range10.4485% exceeds the team's10%
  heuristic. Historical ee4fea2 median deltas -2.336 ms large and +3.343 ms aLIGO;
  ranges overlap and no matched-parent causal estimate is available.
- Phase medians ms, large/aLIGO: imports266.284/265.766; initialize3.584/3.618;
  load1.505/0.216; build73.871/38.929; forward lower21.525/21.443,
  compile34.912/35.234, execute181.541/33.117; sensitivity lower25.448/26.271,
  compile39.708/41.397, execute0.860/0.474; gradient lower17.764/17.134,
  compile53.433/54.315, execute85.248/14.479; host transfer0.187/0.147.
  Against28's observed phase medians, forward lowering increased1.965/2.258 ms,
  forward compilation1.983/1.686 ms, and gradient lowering1.106/0.597 ms.
  These are unpaired observations, but the targeted phases provide no support for
  the proposed tracing reduction. Large1 also had slower imports/build/compilation;
  retain that sample and do not assign its cause without evidence.
- Sampled peak process-group RSS bytes: large[579211264,481406976,581120000],
  aLIGO[281972736,294412288,294899712], generalization999202816. No memory-budget
  failure; sampling can miss brief peaks. EPYC9334 CPU2, one logical CPU and library
  threads1, x64, unchanged package flags, persistent cache disabled. Other-job
  overlap unknown; ranking_eligible=false.
- Generalization archive deaa6e46f581c61ebee98516f581d30ef4de3a25e34d8dd386fee3a0c65b8d5d.
  Official archive hashes remain112c0407...large and9c1ce936...aLIGO; seed maximum
  absolute gradient differences remain5.686350050382316e-6 and3.637978807091713e-11.
  Tolerance agreement does not establish bitwise seed equality or pristine agreement.
- Decision: retire nested-JIT adapter staging; remove its decorator/comment and
  restore all ten simulator modules to reviewed ee4fea28c04d482566be16e916b609d7c6a99e5e.
  Keep29's commit, diagnostic and evidence in history. Do not try inline/different
  decorator boundaries without new tracing evidence. This restoration is not a new
  optimization candidate and should not trigger another performance submission.
- Next: supervisor import/build/trace profiling on reviewed parent using the prepared
  overnight-overhead-profile.py --trace-forward and actual setup/optimization/sweep
  inputs. Return call attribution before further setup or staging variants. Candidate27
  remains a separate pending confirmation/review request, not a validated gain.
  Pristine signal/gradient/loss mismatches, gradients33/161/180, uifo_rand1/3 sensitivity
  disagreements, unresolved grid FD54/59/63/136/161/163 and first-order-only custom VJP
  remain open. Stop this hypothesis, not the campaign; deadline2026-11-22 09:27:44 UTC.

### Candidate30 — static slices for consecutive parameter selections

- Supervisor explicitly resumed after29's retirement requesting a concrete experiment.
  Keep29 retired and preserve its restoration. Parent for this isolated refinement is
  reviewed ee4fea28c04d482566be16e916b609d7c6a99e5e. Candidate SHA and both benchmark/job
  identifiers are pending. Only _static_take in simulate.py differs from that parent.
- Source mechanism: _static_take always emits a one-dimensional lax.gather for the
  builder's concrete indices. If a nonempty one-dimensional index vector is ascending
  by exactly one and its entire interval is in bounds, it is exactly a static slice.
  Emit lax.slice_in_dim in that case. Otherwise retain the original gather, including
  empty, repeated, unordered and nonconsecutive selections. No matrix or parameter
  values are inspected. A zero-valued selected parameter retains its derivative.
- Hypothesis: a static slice can avoid a gather index operand and the gather's scatter
  transpose in parameter insertion/linking/phase readout, reducing small JAX lowering
  or compilation costs. Full-span selections can simplify to identity. This is not an
  assertion that the compiler currently fails to simplify them: XLA may already do so,
  and the NumPy index scan introduces trace-time work. No benefit has been measured.
  Metadata is not cached; each invocation examines the actual supplied index vector.
- This is a narrow selection refinement, not another nested-JIT boundary. Candidate14
  tested contiguous parameter writes (dynamic_update_slice replacing scatter), without
  a demonstrated gain;30 instead tests reads and their transpose, against reviewed
  parent and without14 or any other unreviewed change. Retire this read-selection
  refinement if it gives no stable benefit rather than cycling indexing variants.
- Current cost context from29, not matched parent: forward lower21.525/21.443 ms,
  compile34.912/35.234 ms; gradient lower17.764/17.134 ms, compile53.433/54.315 ms
  (large/aLIGO).29's nested-JIT overhead is absent from30. Parent-like28 observed
  forward lower19.560/19.185 ms, compile32.929/33.548 ms; gradient lower16.658/16.537
  ms, compile53.124/53.150 ms. Import/build are not expected savings from30. No30
  phase deltas, first-run samples or memory observations yet exist.
- Local verification: all ten simulator modules compile as Python; nine match parent
  bytes exactly. Replacing _static_take's AST with the parent's restores simulate.py's
  complete parent AST, verifying no29 decorator remains. git diff --check passes.
  An exhaustive standard-library index enumeration for lengths1–6 and selection lengths
  0–4 verified52 eligible contiguous intervals against explicit index selection. This
  is a logical index-equivalence check, not execution of NumPy/JAX implementation.
- Prepared overnight-overhead-static-slice-check.py, UNEXECUTED because NumPy/JAX are
  unavailable locally. It extracts the actual helper and compares it with the parent
  lax.gather under JIT/VJP for54 tiny real/complex cases. Includes singleton/full-span/
  partial/reversed/repeated/random/empty selections, selected current zeros, sign bits
  and duplicate-index gradient accumulation. It does not benchmark optical fixtures.
- Request focused diagnostic plus both unchanged full official benchmarks, full saved
  outputs/gradients and fourteen-case seed/pristine generalization on the same exact
  new SHA. Independent source review and interleaved fresh parent/candidate confirmation
  are required before promotion. Report samples, separate medians/ranges, all phase
  tradeoffs, RSS and known overlap. No new compiler setting, outside-timer work, cache,
  fixture modification, solver/refinement/adjoint math or official-stage change.
- Candidate29's failed timing evidence and all prior trials remain preserved. The
  supervisor profiling request and27's separate confirmation request remain pending;
  neither is supplied by this trial. Inherited pristine signal/gradient/loss failures,
  gradients33/161/180, uifo_rand1/3 sensitivity discrepancies, unresolved grid
  FD54/59/63/136/161/163 and first-order-only host VJP remain explicit open questions.
  Absolute deadline2026-11-22 09:27:44 UTC remains unchanged.

### Candidate30 feedback — freeze for confirmation, not promotion

- Exact simulator candidate7baa78dd15196b74b6f6e6fdb2bfbac07cfb8f72;
  evaluation d2b5d7f493674c4bb905a3e019d2d488, jobs grid-1/2/3 and aligo-1/2/3.
  Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/
  d2b5d7f493674c4bb905a3e019d2d488.json. All six official runs passed.
- Large complete fresh-process seconds: 0.8237706832587719, 0.7947273701429367,
  0.7867102511227131; median0.7947273701429367, range0.7867102511227131–
  0.8237706832587719. Official aLIGO: 0.5331904906779528, 0.5345235411077738,
  0.5374267045408487; median0.5345235411077738, range0.5331904906779528–
  0.5374267045408487. Relative ranges4.6633% and0.7925%, respectively.
- Phase medians in ms (large/aLIGO): imports265.177/263.154,
  initialize3.527/3.559, load1.520/0.210, build72.466/38.092;
  forward lower19.486/18.981, compile32.869/32.882, execute181.827/33.976;
  sensitivity lower25.545/26.312, compile39.689/41.707, execute0.875/0.498;
  gradient lower16.376/15.902, compile48.943/44.267, execute86.071/14.066;
  host transfer0.193/0.149. Separately computed phase medians need not sum to
  the median complete first run.
- Gradient compile samples in ms: large49.662/48.943/48.795,
  aLIGO44.267/43.993/44.379. Compared with parent-like28's phase medians,
  gradient compilation is lower by4.181/8.883 ms. This supports the proposed
  mechanism provisionally;28 is a different unpaired revision, not a controlled
  parent comparison. Imports/build changes are not attributable to this patch.
  Historical admitted ee4fea2 total medians exceed30's by6.850/14.032 ms,
  but large ranges overlap. confirmed_improvement=false; publication explicitly
  requires source review and paired evidence. No claim of a stable gain.
- Sampled process-group peak RSS bytes: large502157312/504774656/523550720;
  aLIGO312762368/333729792/281370624; generalization903008256. No budget
  exceedance. CPU2, one logical CPU, library threads1, EPYC9334, x64,
  no persistent compilation cache and unchanged package flags. External overlap
  was not excluded; no claim that it explains a particular sample.
- All14 generalization cases pass initial-seed regression tolerances, as do
  official saved arrays. This is not bitwise seed equality: official maximum
  absolute gradient differences are5.686350050382316e-6 large and
  3.637978807091713e-11 aLIGO. Generalization archive SHA256:
  d2a8221ede427a0cf610d90dcf55b394b3e4dee8867756811a675b578a918b3f.
  The receipt's archive self-comparison is not independent seed validation.
  Pristine signal/gradient/loss disagreements remain; strict_passed=false.
  Inherited gradients33/161/180, uifo_rand1/3 sensitivity discrepancies and
  grid FD54/59/63/136/161/163 remain unresolved. Whole-pass VJP still supports
  only first-order reverse mode. These findings are separate from official passes.
- Decision: preserve30's exact simulator unchanged pending confirmation; do not
  combine it with27,15 or another lane. Source inspection confirms the only delta
  against reviewed ee4fea28c04d482566be16e916b609d7c6a99e5e is _static_take.
  The prepared54-case static-slice JIT/VJP diagnostic remains UNEXECUTED locally
  and has no supplied supervisor result; request it before independent review.
- Concrete next experiment for supervisor: interleave five fresh complete runs
  per revision per official setup, comparing exact7baa78dd15196b74b6f6e6fdb2bfbac07cfb8f72
  with exactee4fea28c04d482566be16e916b609d7c6a99e5e under the same resource policy.
  Preserve every sample and report separate medians/ranges, phase deltas, RSS,
  environment and known overlap. Obtain independent source review on30's exact
  delta; both official benchmarks and generalization already have this SHA's
  initial results, but confirmation remains missing. No new implementation is
  submitted with this note, and no candidate-only repeat should replace the
  matched comparison. If confirmation fails, retire this read-selection mechanism
  and return to reviewed parent plus the pending supervisor profiling experiment.

### Candidate31 — direct CSC order validation during setup

- Supervisor resumed after30's confirmation handoff and requested a concrete new
  experiment. Preserve30 at7baa78dd15196b74b6f6e6fdb2bfbac07cfb8f72 with its results
  and pending review/paired-confirmation request. Restore simulate.py to reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e for this isolated experiment. This is not
  a combination or a conclusion that30 failed correctness. Candidate31 SHA and both
  benchmark/job identifiers are pending supervisor submission.
- Distinct observed operation: SparsePattern.__init__ invokes np.lexsort on concrete
  rows/columns only to assert that the resulting permutation is identity. It never
  uses that permutation to reorder a matrix. For equal-shape one-dimensional integer
  vectors, replace sorting and permutation allocation with adjacent comparisons:
  columns must not decrease; within equal columns, rows must not decrease. Equal
  coordinate pairs remain accepted (stable lexsort also keeps their input order).
  No subtraction avoids overflow at int64 extremes. Other dimensions/shapes retain
  the original lexsort behavior. CSC arrays, hashes, gathers, matrix values, solver,
  refinement and derivatives are unchanged.
- Hypothesis targets setup only: direct order validation removes three coordinate
  sorts for a standard carrier/signal/noise structure and their permutation/arange
  allocations. It may reduce setup allocation/validation costs; no gain is measured.
  NumPy lexsort can be efficient on already-ordered vectors, and comparison temporaries
  may erase this small saving. Prior28 removed a redundant unique call without a
  stable benefit;31 changes a different validation algorithm, not unique caching or
  an extension of that implementation. This conservative refinement should be retired
  if insignificant, not followed by repeated sorting microvariants without profiling.
- Current cost context (30, unpaired and different source): build medians72.466 ms
  large /38.092 ms aLIGO; imports265.177/263.154 ms. Compilation and execution are
  not targeted. No31 phase deltas, memory observations or timing samples yet exist.
- Local checks: all simulator files and the new diagnostic compile as Python;
  nine modules other than sparse.py are byte-identical to reviewed parent. Exhaustive
  standard-library mathematical comparison checked7381 coordinate sequences with
  entries drawn from {-1,0,1} pairs and lengths0–4, including duplicates. This verifies
  order logic, not execution of NumPy or a physical workload.
- Prepared experiments/notes/overnight-overhead-csc-order-check.py (UNEXECUTED locally,
  NumPy unavailable). Extracts the actual SparsePattern class and substitutes the
  original validation block for a reference. Compares913 small constructions:
  random/sorted/reversed, empty/singleton/duplicate, int64 extrema, and malformed
  dimensions/shapes. Checks exceptions and successful rows/cols/indices/indptr,
  sizes, keys and hashes. No fixtures, solver invocations or timing loop.
- Request this diagnostic, both unchanged complete official workloads, all saved
  outputs/gradients and seed/pristine generalization on the same new SHA. Independent
  source review and matching fresh parent/candidate confirmations remain necessary
  before any promotion. No benchmark settings/workload changes or work outside timers.
  Report each sample, separate medians/ranges, phase tradeoffs, RSS and known overlap.
- Inherited strict pristine disagreements remain open: signal, loss, gradients33/161/180,
  uifo_rand1/3 sensitivity, unresolved grid FD54/59/63/136/161/163. First-order reverse
  custom-VJP scope unchanged. Prior official passes do not resolve these questions.
  Next decision: inspect31's build phase and full costs; if no credible benefit,
  retain reviewed parent and obtain the already-prepared supervisor profiling evidence.
  Absolute deadline2026-11-22 09:27:44 UTC unchanged.

### Candidate31 feedback — retire direct CSC validation experiment

- Exact candidate ee629404f16c652b61313d185f6aca9af0718ec6; evaluation
  09c51c7c3efd43eb95a9b6ff8662d8cd, jobs grid-1/2/3 and aligo-1/2/3.
  Receipt experiments/runs/overnight-20261122/overnight-overhead-v1/
  09c51c7c3efd43eb95a9b6ff8662d8cd.json. Both official benchmarks passed3/3.
- Large fresh complete seconds:0.8371940702199936,0.8019133750349283,
  0.7954988665878773; median0.8019133750349283, range0.7954988665878773–
  0.8371940702199936. Official aLIGO:0.5523254368454218,0.5459437370300293,
  0.5422520395368338; median0.5459437370300293, range0.5422520395368338–
  0.5523254368454218. Separate medians, no combined score. Relative ranges5.1995%
  and1.8451%. No matched-parent confirmation or independent review was supplied.
- Phase medians ms (large/aLIGO): imports267.611/264.398, initialize3.560/3.557,
  load1.449/0.207, build73.382/38.267; forward lower19.536/19.249,
  compile33.102/33.506, execute183.364/32.815; sensitivity lower25.618/26.111,
  compile41.442/41.650, execute0.906/0.475; gradient lower16.972/16.620,
  compile53.793/53.634, execute83.981/14.060; transfer0.187/0.153.
  Against parent-like28, build is lower0.407 ms large and higher0.060 ms aLIGO;
  this unpaired submillisecond difference does not establish the hypothesized gain.
  Historical reviewed-parent complete medians differ by+0.336 ms large and
  -2.611 ms aLIGO; ranges overlap. confirmed_improvement=false; publication reasons:
  requires_source_review, large_gain_below_selection_threshold,
  large_first_run_ranges_overlap_requires_paired_evidence.
- Sampled process-group peak RSS bytes: large608600064/624238592/489033728;
  aLIGO281276416/315015168/294731776; generalization1003548672. No memory budget
  exceedance. EPYC9334, CPU2, one logical CPU, library threads1, x64, no persistent
  cache, unchanged compiler defaults. External contention not excluded; no inference
  that contention caused any specific sample. ranking_eligible=false.
- All14 generalization cases and official outputs pass initial-seed regression
  tolerances. This does not mean bitwise seed equality: official max absolute gradient
  differences5.686350050382316e-6 large /3.637978807091713e-11 aLIGO. Generalization
  archive25782157465800949ebd1144a69e0739f7aaf429090450d81f690b0681122cf9.
  Pristine comparisons still fail; no new numerical failure is reported relative
  to seed. The913-case focused NumPy diagnostic remains unexecuted locally, and
  no supervisor result for it was supplied. Official passes are separate evidence.
- Decision: retire31 and restore sparse.py to reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e. Verified all ten simulator modules
  byte-identical to that parent and syntactically valid. Preserve31's commit,
  diagnostic and failed timing evidence. Restoration is not an optimization candidate
  and does not need a new candidate-only timing submission. Stop this hypothesis,
  not the authorized campaign. Do not cycle further unique/order-validation variants.
- Next experiment: supervisor attribution with the existing
  experiments/notes/overnight-overhead-profile.py --trace-forward on reviewed parent,
  using actual setup, optimization and sweep arguments. Return import/build/trace call
  attribution for large, official aLIGO and a third setup before more builder changes.
  Candidate30's focused diagnostic, independent review and matched-parent confirmation
  request remains separate and pending; do not combine30 with31 or treat30 as promoted.
- Inherited strict signal/gradient/loss disagreements, gradients33/161/180,
  uifo_rand1/3 sensitivity discrepancies, grid FD54/59/63/136/161/163 and
  first-order-only whole-pass custom VJP remain open. Deadline unchanged:
  2026-11-22 09:27:44 UTC.

### Candidate32 — empty static parameter reads as empty slices

- Resumed after31 retirement at supervisor request for one concrete experiment.
  Candidate SHA and benchmark/job IDs pending supervisor commit/evaluation. Working
  source is reviewed ee4fea28c04d482566be16e916b609d7c6a99e5e plus only the
  _static_take change in simulate.py. sparse.py's working diff restores31 to that
  parent; it is not a second optimization. All nine other simulator modules match
  the reviewed parent byte for byte. Preserve prior failed commits and notes.
- Hypothesis: a statically empty parameter read can produce its empty result with
  a slice, avoiding construction of the gather and its scatter transpose during
  tracing. This targets forward/gradient trace and compilation, not solver work or
  numerical arithmetic. It is a narrow boundary refinement after unsuccessful
  builder trials. No benchmark identity, known fixture shape, parameter value or
  numerical-zero test is used. Current-point zero derivative contributions remain.
- The fast path requires a nonempty one-dimensional operand and a one-dimensional
  empty index vector. Keeping the nonempty-operand guard preserves the original
  gather's slice-size validation for an empty operand. Other inputs retain exactly
  the original gather and options. Empty slices preserve dtype and have a zero
  transpose for every operand entry, just like an empty gather. All phase operations,
  scatters, callbacks, linking functions, physical outputs and three JIT stages stay.
- This is not candidate30's nonempty contiguous-read optimization, nor candidate15's
  None phase shortcut or27's skipped phase scatter. None of those changes is combined.
  Candidate30 remains preserved at7baa78dd15196b74b6f6e6fdb2bfbac07cfb8f72, awaiting
  its requested diagnostic, independent review and matched-parent confirmations.
- Cost context only: evaluated31's phase medians ms (large/aLIGO) were forward
  lower19.536/19.249, compile33.102/33.506; gradient lower16.972/16.620,
  compile53.793/53.634. Imports267.611/264.398 and build73.382/38.267 are not this
  proposal's target. These are31's observations, not32 measurements or a matched
  parent comparison. JAX may already simplify the empty operation; saved tracing
  work may be negligible. No speedup, phase delta or memory benefit is claimed.
- Local validation: syntax passes; AST comparison proves the fallback gather is
  unchanged after substituting normalized indices and the rest of simulate.py is
  unchanged.49 standard-library stub cases check dispatch across scalar, empty,
  vector and higher-rank operands/index arrays. These are structural checks, not
  JAX execution or physical correctness evidence.
- Prepared experiments/notes/overnight-overhead-empty-gather-check.py, UNEXECUTED
  locally because NumPy/JAX are unavailable. It extracts the actual helper and checks
  54 small JIT primal/VJP comparisons against the original gather: real/complex,
  empty/singleton/full/partial/reversed/repeated/random indices, zeros and sign bits.
  Four invalid operand/index shape cases compare exception types. No optical fixture,
  timing loop or official workload is run by this diagnostic.
- Request the focused diagnostic, both unchanged complete official benchmarks and
  all saved output/gradient/generalization comparisons on the exact new SHA. Obtain
  independent source review and matching fresh-process candidate/parent confirmations
  before promotion. Report separate complete samples, medians/ranges, phase costs,
  sampled RSS and known job overlap; keep pristine failures distinct from seed checks.
- Inherited issues remain: pristine signal/gradient/loss disagreements including
  gradients33/161/180, uifo_rand1/3 sensitivity discrepancies, unresolved grid finite
  differences54/59/63/136/161/163. Whole-pass custom VJP supports first-order reverse
  mode only. This structural change does not resolve any of those findings.
- Next decision: reject32 if no repeat-supported compilation/complete-run gain.
  Do not accumulate more empty-boundary variants without attribution; use the pending
  supervisor profile and candidate30 confirmation evidence. Deadline remains
  2026-11-22 09:27:44 UTC. No benchmarks, installs, commits or agents launched here.

### Candidate32 feedback — retire empty-gather refinement

- Exact evaluated SHA301c46fa997dfbc763f4924b3068903f7fe4e938; evaluation
  ecf529ba1ffb448dacd55c57b2727755, jobs grid-1/2/3 and aligo-1/2/3.
  Receipt experiments/runs/overnight-20261122/overnight-overhead-v1/
  ecf529ba1ffb448dacd55c57b2727755.json; publisher
  bd9743e197878e3a281877b9b26aca867eaef62d. Both official benchmarks passed3/3.
- Large complete fresh-process samples seconds:0.8293256852775812,
  0.7961510177701712,0.805237153545022; median0.805237153545022,
  range0.7961510177701712–0.8293256852775812, relative range4.1199%.
  Official aLIGO:0.5476876273751259,0.5464055705815554,0.5480974521487951;
  median0.5476876273751259, range0.5464055705815554–0.5480974521487951,
  relative range0.3089%. No combined score. Historical admitted-parent median
  differences are+3.659 ms large and-0.868 ms aLIGO; unpaired ranges overlap.
  confirmed_improvement=false; no independent source review supplied. Publication
  requires_source_review, large_gain_below_selection_threshold and
  large_first_run_ranges_overlap_requires_paired_evidence.
- Phase medians ms (large/aLIGO): imports270.699/267.001, initialize3.562/3.636,
  load1.544/0.211, build70.022/37.780; forward lower19.962/19.194,
  compile34.317/33.325, execute182.295/32.579; sensitivity lower25.552/26.201,
  compile39.695/41.317, execute0.893/0.477; gradient lower17.199/16.566,
  compile51.851/53.359, execute85.879/14.704; transfer0.189/0.155.
  Against preceding31 observations, forward lower changes+0.426/-0.055 ms and
  gradient lower+0.227/-0.054 ms; no clear target tracing benefit. Gradient compile
  changes-1.942/-0.275 ms, forward compile+1.215/-0.181 ms. These are unpaired
  observations, not causal phase gains. Build/import changes are not attributable
  to the empty-gather mechanism. This result does not justify its extra branch.
- Sampled process-group peak RSS bytes large540045312/518770688/489443328,
  aLIGO315043840/295477248/312152064; generalization873996288. No budget exceedance.
  CPU2, one logical CPU, EPYC9334, library threads1, x64, no persistent cache,
  unchanged allowed compiler defaults. Other-host contention not excluded and no
  specific slow sample is attributed to contention. ranking_eligible=false.
- All saved official arrays and all14 generalization cases pass initial-seed
  regression tolerances. Official array archives match preceding31's archives:
  large112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5,
  aLIGO9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195.
  This does not imply bitwise equality to seed: maximum absolute gradient differences
  are5.686350050382316e-6 large and3.637978807091713e-11 aLIGO. Generalization archive
  2183cdbb7c64deda5e4189980018b057f6e8abc8f80aa971504fb8e98642d6bd.
  Pristine comparisons still fail. No new seed-relative numerical discrepancy is
  reported; inherited disagreements remain unresolved, not waived by official passes.
  The54 primal/VJP and four invalid-shape focused checks remain unexecuted locally;
  no supervisor result for that diagnostic was returned.
- Decision: retire32; restored simulate.py to reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e and verified all ten simulator modules
  byte-identical and syntactically valid. Preserve32's committed source, diagnostic
  and full results. This restoration is not a new optimization submission.
- Search-direction change: stop isolated empty-read/empty-boundary variants without
  attribution. The concrete next investigation is the already-prepared supervisor
  profiling script experiments/notes/overnight-overhead-profile.py --trace-forward
  on the reviewed parent, with actual caller setup/optimization/sweep inputs for
  large, official aLIGO and a third setup. Return import/build/trace call attribution
  before selecting another builder or boundary rewrite. Candidate30 at7baa78dd remains
  a separate pending confirmation request, not an admitted improvement or combination.
- Inherited pristine signal/loss/gradient findings, gradients33/161/180,
  uifo_rand1/3 sensitivity discrepancies, grid FD54/59/63/136/161/163 and first-order
  reverse-only whole-pass custom VJP remain visible. Stopping this hypothesis does
  not end the authorized campaign or extend deadline2026-11-22 09:27:44 UTC.

### Candidate33 — directly initialize constant component-row labels

- Supervisor resumed after32 retirement and requested a concrete new experiment.
  New SHA and both benchmark job IDs pending. Isolated against reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e; only build.py differs from that parent.
  simulate.py's working diff restores32 to the reviewed version, not a combined
  optimization. All nine other simulator modules remain byte-identical to parent.
- Source inspection found two repeated constructions in pairs_to_arrays:
  np.ones(number_of_outputs) * component_row_offset. Both create constant row-label
  metadata, not physical values. Replace them with np.full(number_of_outputs,
  component_row_offset, dtype=float). This removes the length-N ones temporary and
  elementwise multiplication while preserving float64 labels before _host_array's
  final int64 conversion. The offset starts at0 and increments by nonnegative row
  counts, or is len(components)-1 after append. Index ordering, duplicate component
  handling, explicit output rows, grouping, linking and every simulation stage stay.
- Mechanism is direct constant-array construction during setup; it does not repeat
  retired32's empty-gather tracing or31's CSC validation. No unique/sort rewrite,
  physical zero pruning, topology/fixture recognition, cached results or solver change.
  Candidate30 and other unconfirmed mechanisms are not combined.
- Cost context:32's observed build medians70.022 ms large /37.780 ms aLIGO, complete
  medians0.805237154/0.547687627 s. Imports270.699/267.001 ms and compilation are not
  targeted. Saving scales with instructions that synthesize output-row labels, for
  arbitrary supplied setups; no known workload counts enter the implementation.
  No33 timing, phase delta or memory measurement exists. np.full has its own Python
  overhead; for these small arrays the allocation saving may not improve wall time.
- Local checks: Python syntax and git diff whitespace checks; an AST transformation
  replacing exactly the two np.full calls by the old expressions reproduces the
  entire reviewed build.py AST.10004 Python scalar conversion comparisons pass,
  including offsets around2**53 and at2**63-1. These checks do not execute NumPy.
- Prepared experiments/notes/overnight-overhead-row-label-check.py, UNEXECUTED locally
  (NumPy unavailable). Extracts actual pairs_to_arrays and its helpers and compares
  to an AST reference restoring the two old expressions.48 synthetic instruction
  collections vary component counts, output counts including empty, repeated/reversed
  optimization requests, explicit versus implicit signal output rows, and sweep
  selection. Compares all returned index arrays, group metadata and pre-cast arrays
  including dtypes/sign bits.21 additional NumPy cases check scalar conversion near
  float64 integer precision limits and empty lengths. No optical fixture or timing.
- Request the focused diagnostic, both unchanged official full benchmarks, saved
  arrays/gradients and generalization on the same exact SHA. Independent source review
  and matched fresh-process parent/candidate confirmation remain required for promotion.
  Report samples, separate medians/ranges, phase tradeoffs, RSS and known contention.
- Inherited strict pristine signal/loss/gradient disagreements, gradients33/161/180,
  uifo_rand1/3 sensitivity discrepancies and grid FD54/59/63/136/161/163 persist;
  first-order reverse-only whole-pass custom VJP scope unchanged. Neither structural
  equivalence nor official success is a universal correctness certificate.
- Next: inspect33's setup and total costs; retire if gains are not repeat-supported.
  Supervisor import/build/trace attribution and candidate30 confirmation remain
  pending and preferable to further speculative allocation variants. Deadline remains
  2026-11-22 09:27:44 UTC. No benchmarks, commits, installs or agents launched here.


### Candidate33 feedback — retire constant-row allocation variant

- Exact SHA6f058f36f9db49c1c7fc0301077036566e952212; evaluation
  28631be62fe54a5ea0b5914446a25713, jobs grid-1/2/3 and aligo-1/2/3.
  Receipt experiments/runs/overnight-20261122/overnight-overhead-v1/
  28631be62fe54a5ea0b5914446a25713.json; publisher
  c705e6532ee8675a1943871ee8905f1664a8e52c. Both official benchmarks pass3/3.
  confirmed_improvement=false; source review absent. Promotion withheld for missing
  review, insufficient large gain and overlapping large first-run ranges.
- Large fresh complete samples [0.840653020888567,0.809885386377573,
  0.7940295897424221] seconds; median0.809885386377573, range
  0.7940295897424221–0.840653020888567 (relative range5.7568%).
  Official aLIGO samples [0.5526398476213217,0.5477518364787102,
  0.5449389312416315]; median0.5477518364787102, range
  0.5449389312416315–0.5526398476213217 (relative range1.4059%).
  Against historical reviewed ee4fea2 medians: large+8.308 ms and aLIGO-0.803 ms.
  This is an unpaired comparison, not a causal delta or organizer ranking score.
- Phase medians in ms, large / aLIGO: imports264.427/262.971,
  initialization3.548/3.548, load1.473/0.215, build72.607/38.348;
  forward lower19.696/19.400, compile33.168/33.865, execute184.998/32.704;
  sensitivity lower25.653/26.248, compile40.895/41.735, execute0.878/0.474;
  gradient lower17.240/16.635, compile53.646/54.596, execute87.352/15.024;
  host transfer0.193/0.160. Build is+2.585/+0.568 ms versus32 and
  -0.775/+0.081 ms versus31; these unpaired observations show no stable setup gain.
  Import/solver timing changes cannot be attributed to these two metadata expressions.
- Sampled process-group peak RSS bytes: large605339648/573042688/514437120;
  aLIGO280338432/295047168/294912000; generalization878579712. No budget exceeded.
  EPYC9334, CPU2, one logical CPU and library threads1, x64, no persistent cache,
  unchanged package compiler defaults. Other-host contention is not excluded;
  no specific slow sample is attributed to contention. ranking_eligible=false.
- All saved official output/gradient comparisons and all14 generalization cases
  pass initial-seed tolerances. Official archives are the same as32:
  large112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5;
  aLIGO9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195.
  This does not imply bitwise seed equality: maximum absolute gradient differences
  remain5.686350050382316e-6 large and3.637978807091713e-11 aLIGO.
  Generalization archive3f0e7ea166e0a7ab2165f46d503f4bcc18be888f324f1e693f999d8e8fa96342.
  Pristine comparisons still fail; no new seed-relative discrepancy is reported.
  Focused48 metadata/21 conversion checks remain unexecuted locally; no supervisor
  result for that diagnostic was supplied.
- Decision: retire33. Restored build.py from reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e, preserving failed committed source,
  diagnostics and evidence. This restoration is not a new optimization candidate.
  Stop further speculative constant-allocation variants without cost attribution.
- Concrete next investigation: supervisor executes the existing
  experiments/notes/overnight-overhead-profile.py --trace-forward diagnostic on
  reviewed ee4fea2 with actual large, official aLIGO and third-setup caller inputs.
  Use import/build/trace call attribution to choose a distinct, measured bottleneck.
  Candidate30 at7baa78dd15196b74b6f6e6fdb2bfbac07cfb8f72 still awaits focused
  diagnostic, independent review and interleaved matched-parent confirmation;
  do not combine it or treat candidate-only runs as that confirmation.
- Inherited pristine signal/loss/gradient findings (including gradients33/161/180),
  uifo_rand1/3 sensitivity disagreements, unresolved grid FD54/59/63/136/161/163,
  and first-order reverse-only whole-pass custom VJP remain visible. Prior additional
  aLIGO coordinate checks confirmed29/29; this is not a universal certificate.
  This stop ends33's hypothesis, not the campaign; deadline2026-11-22 09:27:44 UTC.

### Candidate34 — parameter insertion as a single source-map gather

- Supervisor resumed after33 retirement and requested a concrete next experiment.
  Candidate SHA and both official job IDs pending. Isolated against reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e. Only host_pass.py and simulate.py
  differ from that parent; build.py's working diff is the retirement of33.
  No unconfirmed candidate30/27/15 mechanism is combined.
- Distinct mechanism: replace the optimized-value gather followed by a unique
  parameter-row scatter with one gather from concatenated base/optimized inputs.
  ParameterLayout.from_arrays derives a source map after its existing bounds and
  unique-destination validation. Initially source[i]=i; every optimized destination
  receives parameter_count+optimized_value_index. This is metadata from arbitrary
  supplied layouts, not physical values or recognized workload shapes.
- simulate casts optimized inputs to the existing row dtype, concatenates them with
  the original row, and selects the full row with that map. Linking and phase steps
  remain in their original order. Repeated optimized-value indices are allowed:
  gather transposition accumulates all of their cotangents. Untouched base entries
  retain their gradients; overwritten base entries receive zero cotangents. Zero
  valued design variables are not removed. The map is derived from already-hashed
  layout inputs; the existing rebuild requirement still applies when indices change.
  Directly constructed layouts and unequal insertion/source lengths retain the
  original gather/scatter expression. Existing applies() bounds-checks optimized
  input length before the static path is used. Invalid builder layouts retain the
  generic simulation path under the existing validation.
- Cost hypothesis: two indexing operations become one gather plus concatenation;
  their reverse program becomes a gather transpose and concatenation transpose.
  This can reduce forward/gradient compilation work at optimization level0, though
  materializing concatenated inputs and reading the full row can offset the saving.
  Source-map allocation is counted in setup. No solver/refinement/adjoint formula,
  callback signature, compiler flags, public output or three-stage execution changed.
  This differs from14's contiguous-write dynamic_update_slice,30's contiguous-read
  slicing and32's empty-gather special case; it works for noncontiguous destinations.
- Measured context only (33, not34): build medians72.607/38.348 ms large/aLIGO;
  forward lower19.696/19.400 and compile33.168/33.865 ms; gradient lower17.240/16.635
  and compile53.646/54.596 ms. Those phases motivate testing the indexing program.
  No34 complete, phase, memory or generalization measurement exists. This is a
  structural hypothesis, not a profiling result or established improvement.
- Local checks:2371 exhaustive small Python cases enumerate unique destination
  permutations for row sizes1–6, including empty/full/reordered/noncontiguous writes
  and repeated optimized sources. Source-map primals and both input cotangent models
  equal the original overwrite semantics. Syntax and whitespace checks pass. Eight
  other simulator modules are byte-identical to reviewed parent. These checks do
  not execute NumPy/JAX and cannot establish their compiled derivative behavior.
- Prepared experiments/notes/overnight-overhead-row-source-check.py, UNEXECUTED
  locally (NumPy/JAX unavailable). Extracts actual ParameterLayout, helpers and
  insertion statements from this source.96 small JIT primal/VJP cases vary row
  size, empty/singleton/full/reversed/strided destinations, shared optimized inputs,
  real/complex base and optimized inputs, zero values and signed zeros. Compares
  exact primal values/sign bits and both input cotangents to the reviewed expression.
  Six layout guard/fallback checks cover negative/out-of-range/duplicate destinations,
  invalid source index, insufficient optimized length and direct construction.
  No optical fixture, benchmark execution or timing code. Cast warnings in mixed
  complex-to-real synthetic cases have the same meaning as in the original cast.
- Request focused diagnostic plus both unchanged full official benchmarks and14
  generalization cases on one exact supervisor-committed SHA. Inspect all saved
  outputs and gradients, including possible accumulation-order differences for
  shared optimized inputs. Independent source review and interleaved matched-parent
  fresh-process confirmation remain required before promotion; report every sample,
  separate medians/ranges, phase tradeoffs, RSS and known overlap. No claim is made
  from candidate-only medians against historical parent timings.
- Inherited pristine signal/loss/gradient disagreements (including33/161/180),
  uifo_rand1/3 sensitivity differences and unresolved grid FD54/59/63/136/161/163
  persist. Prior additional aLIGO29/29 checks and seed-relative successes do not
  certify universal accuracy. Whole-pass custom VJP remains first-order reverse-only.
- Next: inspect34's phase and numerical feedback; retire if the full-row gather
  fails to show a repeat-supported benefit. Supervisor profiling and candidate30's
  separate matched-parent confirmation remain pending. Do not repeat this mapping
  mechanism after three unsuccessful evaluated variants. Deadline unchanged:
  2026-11-22 09:27:44 UTC. No benchmarks, commits, installs or agents launched here.

### Candidate34 feedback — retire full-row source-map gather

- SHA cc288e51f081992190bea3480cbdff9f59ac6856; evaluation
  5e4f4623c76f49c498c06be1a4af223b, jobs grid-1/2/3 and aligo-1/2/3.
  Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/5e4f4623c76f49c498c06be1a4af223b.json.
  Publisher475378429d50cf2099e40a8defcc42b1b58c3e33. Official3/3 each;
  confirmed_improvement=false, no independent source review. Selection rejected
  missing review, insufficient large gain and overlapping first-run ranges.
- Large fresh complete samples [0.834713775664568,0.8167882431298494,
  0.7990507762879133] s: median0.8167882431298494, range
  0.7990507762879133–0.834713775664568 (relative4.3662%).
  Official aLIGO samples [0.5458212047815323,0.5465039424598217,
  0.5490178875625134] s: median0.5465039424598217, range
  0.5458212047815323–0.5490178875625134 (relative0.5849%). Historical reviewed
  ee4fea2 median deltas+15.211 ms large/-2.051 ms aLIGO; unpaired, not causal.
- Phase medians ms, large/aLIGO: imports277.044/265.900, init3.647/3.596,
  load1.499/0.212, build73.531/39.786, forward lower19.536/19.936,
  forward compile27.964/28.953, forward execute184.465/33.153,
  sensitivity lower25.416/26.443, compile41.303/41.519, execute0.919/0.470,
  gradient lower17.238/16.398, compile56.427/55.050, execute85.649/14.565,
  host transfer0.198/0.147. Versus33, forward compile-5.204/-4.912 ms,
  gradient compile+2.781/+0.454 ms, build+0.924/+1.438 ms. The forward
  compile signal is useful evidence, but total benefit is not established and
  these unpaired phase deltas do not prove attribution. Import variance is not
  a demonstrated consequence of the row-source mechanism.
- Sampled peak process-group RSS bytes: large638914560/550719488/514240512;
  aLIGO283086848/295243776/295440384; generalization776028160. No budget exceedance.
  Fixed EPYC9334 CPU2, one logical CPU and library threads1, x64, no persistent
  cache, unchanged package flags. External contention not excluded; no slow sample
  discarded or attributed to overlap. ranking_eligible=false.
- All official saved arrays/gradients pass initial-seed tolerances; archives remain
  large112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5 and
  aLIGO9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195.
  This does not imply bitwise seed equality: gradient maximum absolute differences
  remain5.686350050382316e-6 and3.637978807091713e-11 respectively. All14 additional
  cases pass seed-relative checks; generalization archive
  2a67dbff99c2a0b4f7869e286eb7ccb137d4024140efa11a132ceb5fc5e8f6f2.
  Pristine comparisons retain the inherited disagreements. No newly introduced
  seed-relative discrepancy is reported. Focused96 primal/VJP and six guard checks
  remain unexecuted locally; no supervisor diagnostic result was supplied.
- Decision: retire34 and restore host_pass.py/simulate.py to reviewed ee4fea2;
  all ten simulator modules verified byte-identical and syntactically valid.
  Preserve the evaluated revision, diagnostic and evidence. Do not extend source-map
  variants to linking or add a new custom derivative on this unconfirmed evidence.
  This restoration is not a new optimization candidate or history reset.
- Next concrete investigation remains supervisor import/build/trace profiling with
  experiments/notes/overnight-overhead-profile.py --trace-forward on reviewed
  ee4fea2, using actual caller inputs for large, official aLIGO and a third setup.
  Attribute costs before another boundary variant. Candidate30's separate source
  review and interleaved matched-parent confirmation request remains pending.
- Inherited pristine signal/loss/gradient findings including33/161/180,
  uifo_rand1/3 sensitivity discrepancies, unresolved grid FD54/59/63/136/161/163
  and first-order reverse-only whole-pass custom VJP remain explicit. Additional
  aLIGO29/29 checks do not certify general accuracy. Stop ends34's hypothesis,
  not the authorized campaign; deadline stays2026-11-22 09:27:44 UTC.


### Candidate35 — remove only full identity parameter gathers before AD

- Supervisor resumed after34 retirement and requested a concrete experiment.
  Current branch HEAD a8b5e887e1b1463958c9e6956ba4a217cfb3c548; retain the pending
  removal of34's source-map implementation. Scientific parent is reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e. Only _static_take differs from that
  parent; nine other simulator modules match it exactly. New candidate SHA and
  official job identifiers are pending supervisor submission. No history reset.
- Narrow candidate30's provisional compilation signal to full identity reads.
  If the actual concrete index vector equals the complete nonempty ascending
  index range of a 1-D input, return jnp.asarray(values). For traced/JAX inputs
  this is an identity before differentiation, with no gather or scatter transpose.
  The conversion preserves the old helper's JAX-array result for eager NumPy inputs.
  Empty, partial, repeated, reversed and nonconsecutive selections retain the
  original gather. No slicing variant, source-map insertion or empty-phase change
  is combined. No derivative rule is hand-written.
- Generic source evidence: pairs_to_arrays enumerates optimization_pairs and appends
  the enumeration index for each found parameter. When each supplied optimization
  pair maps to one parameter and covers the supplied input vector, its value-index
  selection is a full identity. Shared or missing mappings are checked from the
  actual indices and keep gather semantics unless genuinely identity. This does
  not inspect a fixture, shape constant, current parameter value or benchmark.
  Current zero entries keep their derivatives. Index checks run during tracing
  and their cost is counted; nothing is cached or moved outside the timer.
- Measured motivation, not35 results: candidate30 (7baa78dd15196b74b6f6e6fdb2bfbac07cfb8f72,
  evaluation d2b5d7f493674c4bb905a3e019d2d488) had gradient compile medians
  48.943/44.267 ms large/aLIGO, versus parent-like28's53.124/53.150 ms.
  Its forward lower19.486/18.981 ms and gradient lower16.376/15.902 ms still
  contain transformation overhead. Complete medians0.794727370/0.534523541 s
  were unconfirmed, with overlapping large ranges and no independent review.
  This narrower experiment tests whether eliminating the identity before AD
  retains that signal with simpler generated code; partial slices may instead
  have caused the signal, or the compiler may already eliminate identity work.
  Extra index comparison/allocation can offset any benefit. No35 timings exist.
- Local validation: 2837 standard-library stub checks exercise the actual helper's
  control flow over small index products, including duplicate/reversed/partial/
  empty cases and invalid input rank. Four complete identity cases use the new
  path; all others keep gather. These are structural checks, not NumPy/JAX
  execution. The initial stub's gather signature omitted a positional argument;
  corrected the stub and reran successfully, with no simulator change required.
  Python syntax and whitespace checks pass. Replacing this helper's AST with
  the parent's restores simulate.py's complete parent AST.
- Prepared experiments/notes/overnight-overhead-identity-gather-check.py:
  54 tiny real/complex JIT primal/VJP cases (selected current zeros, primal sign
  bits, duplicate-index cotangent accumulation), six forward/transpose trace
  checks and six eager NumPy input/result-type checks. UNEXECUTED locally:
  NumPy/JAX are unavailable; no dependency installation or benchmark launched.
  Trace checks test elimination of gather/scatter-add, not compilation speed.
- Request this focused diagnostic, both unchanged full official benchmarks and
  all14 additional generalization cases on the exact supervisor-committed SHA.
  Inspect all output/gradient arrays against seed and pristine separately.
  Independent source review and matched interleaved fresh-process parent/candidate
  confirmation remain required before promotion. Report each sample, separate
  large/aLIGO medians/ranges, phase tradeoffs, sampled RSS and known overlap.
  Candidate30's independent pending confirmation is not replaced by this experiment.
- Decision after feedback: if identity-only elimination has no stable phase and
  complete-first-run benefit, retire it and do not extend to more partial-slice
  variants. Next evidence remains supervisor profiling on reviewed parent using
  overnight-overhead-profile.py --trace-forward, not another source-map rewrite.
- Inherited pristine signal/loss/gradient findings including33/161/180,
  uifo_rand1/3 sensitivity discrepancies, unresolved grid FD54/59/63/136/161/163
  and first-order reverse-only host custom VJP remain open. Prior aLIGO29/29
  checks are bounded evidence. No solver/refinement/adjoint formula, compiler
  flag, official stage, workload or tolerance changes. Deadline remains
  2026-11-22 09:27:44 UTC. No commits, agents, installs or benchmark launches here.


### Candidate35 feedback — retire identity-only gathers

- Candidate800acf5fbfc8eae3846d262b4d702c20d8939af7, evaluation
  56cb75e36ea44298b4d2d55fdb59fd66, jobs grid-1/2/3 and aligo-1/2/3.
  Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/56cb75e36ea44298b4d2d55fdb59fd66.json.
  Publisher37c930ba9bf61bbacf453548f33aec7096dac320. Both official benchmarks
  passed3/3; confirmed_improvement=false, independent source_review=null.
  Selection rejected missing review, insufficient large gain and overlapping ranges.
- Large fresh complete samples [0.8333641663193703,0.7963257115334272,
  0.7994784880429506] s: median0.7994784880429506, range
  0.7963257115334272–0.8333641663193703 (relative4.6328%).
  Official aLIGO samples [0.5365756079554558,0.5376485530287027,
  0.5407672077417374] s: median0.5376485530287027, range
  0.5365756079554558–0.5407672077417374 (relative0.7796%).
  Historical reviewed ee4fea2 median deltas -2.099 ms large/-10.907 ms aLIGO;
  these are unpaired observations, not a demonstrated shared improvement.
- Phase medians ms, large/aLIGO: imports271.584/265.453, init3.543/3.622,
  load1.516/0.301, build74.895/37.938, forward lower19.657/18.679,
  forward compile33.009/32.854, forward execute179.615/32.676,
  sensitivity lower25.677/26.233, compile39.637/41.280, execute0.877/0.478,
  gradient lower16.808/16.076, compile52.106/47.084, execute85.436/14.689,
  host transfer0.192/0.152. Phase medians need not sum to the total median.
  Compared with30's measured gradient compile48.943/44.267 ms, identity-only
 35 is +3.163/+2.817 ms; compared with parent-like28's53.124/53.150 ms,
  it is -1.018/-6.066 ms. A transfer compilation signal remains plausible,
  but neither comparison is a matched-parent causal measurement. This narrower
  mechanism did not reproduce30's full observed compilation reduction and did
  not establish the required large complete-run gain. No slow sample discarded.
- Sampled peak process-group RSS bytes: large520572928/541638656/504217600;
  aLIGO294862848/295333888/293765120; generalization871612416. No exceedance.
  EPYC9334 CPU2, one logical CPU, library threads1, x64, no persistent cache,
  unchanged compiler flags. External contention not excluded; ranking_eligible=false.
- Inspected receipt comparisons for all saved physical outputs and gradients:
  six official and all14 additional cases pass initial-seed regression tolerances.
  Official archives remain large112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5
  and aLIGO9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195.
  Seed maximum absolute gradient differences remain5.686350050382316e-6
  large and3.637978807091713e-11 aLIGO. Generalization archive
  428a220aed616ade541a6dd80d7cf09d9b28b41da4f95b9f79070bb842535725 differs
  from the initial-seed archive; tolerance passes do not imply bitwise equality.
  The receipt's archive self-comparison is not independent seed evidence.
  Pristine strict comparisons still fail inherited signal/gradient/loss checks;
  uifo_rand1/3 log-sensitivity errors remain2.036099068405406e-4/5.8100919558157216e-5.
  No new seed-relative failing entries are reported. The focused54 primal/VJP,
  six trace and six eager-input checks remain unexecuted locally; no supervisor
  diagnostic result was supplied. No new universal correctness claim.
- Decision: retire35 and restore simulate.py to reviewed ee4fea2. All ten simulator
  modules verified byte-identical to that reviewed parent. Preserve35's evaluated
  revision, diagnostic and evidence. No further gather/slice/identity variants
  without profiling or matched-parent confirmation; repeated unconfirmed variants
  do not justify increasing complexity. This restoration is not a new candidate.
- Next concrete step is supervisor profiling of reviewed ee4fea2 using
  experiments/notes/overnight-overhead-profile.py --trace-forward with actual
  large, official aLIGO and third-setup inputs. Return import/build/trace costs
  and pytree inventory before choosing a distinct setup mechanism. Candidate30's
  exact revision remains preserved for its separate focused diagnostic, independent
  review and matched interleaved fresh-process confirmation; do not silently
  substitute35 or combine candidates. No profile or paired cohort has been supplied.
- Inherited pristine gradients33/161/180, uifo_rand1/3 sensitivity disagreements,
  unresolved grid FD54/59/63/136/161/163 and first-order reverse-only host VJP
  remain explicit. Prior extra aLIGO29/29 checks do not certify general accuracy.
  Stop ends35's hypothesis, not the authorized campaign. Absolute deadline remains
  2026-11-22 09:27:44 UTC. No benchmarks, commits, installations or agents launched.


### Candidate36 — set membership for builder component deduplication

- Supervisor resumed after35 retirement and requested a concrete next experiment.
  Keep the restoration of simulate.py; do not retain35 or combine other pending
  variants. Scientific parent ee4fea28c04d482566be16e916b609d7c6a99e5e.
  Only build.py differs from this parent, in pairs_to_arrays' private bookkeeping.
  Candidate SHA and both official job IDs pending supervisor submission.
- Distinct setup mechanism: carrier_components and noise_components were lists
  used only for membership tests, appending a new component and len(). Source
  inspection confirms they are not iterated, returned or passed elsewhere.
  Use sets and add() instead. Component keys are already instruction-dictionary
  keys, so hashability is required before this check in the original code.
  Array append order follows the existing instruction/optimization/sweep loops;
  row labels still use len(components)-1 after a first insertion. Duplicate calls
  still return before appending arrays. The instruction lookup before membership
  remains in place, preserving missing-key behavior. No physical inputs inspected.
- Proven redundant work: list membership scans every earlier component when a new
  component is encountered and scans again on repeated optimization/sweep calls.
  Set membership avoids that linear scan for ordinary distinct hashes. On a tiny
  synthetic sequence of128 unique keys then64 repeats, equality comparisons fall
  from10144 to0 with identical accumulated arrays and counts. These are operation
  counts, not elapsed-time or official workload observations; collision-heavy
  keys can still require linear membership work. Set allocation/hash overhead is
  counted in build and may offset this saving on small setups.
- Measured context only:35 build medians74.895 ms large/37.938 ms aLIGO;
  imports271.584/265.453 ms and gradient compilation52.106/47.084 ms are not
  targeted. No profile attributes a fraction of build time to this helper, and
  no36 timing exists. This test is motivated by the source-proven repeated scan,
  not a promise to recover the entire build phase. Candidate17's name-to-index
  lookup and33's constant row allocation were retired; neither is retained here.
- Local validation: experiments/notes/overnight-overhead-seen-components-check.py
  executes the actual nested helper against the reviewed parent's helper using
  a stdlib stub only for the unchanged np.ones expression.612 cases cover0–16
  components, string/tuple/colliding-hash keys, empty/forward/reverse/repeated/
  randomized insertion sequences and zero/multiple output slots. All accumulated
  dictionaries and distinct-component counts match. An initial Python3.9 annotation
  evaluation error was fixed in the diagnostic using future annotations; simulator
  behavior was unaffected. The diagnostic is structural, not NumPy/JAX execution.
- Reversing the two set initializers, helper annotation/docstring and add() change
  reproduces build.py's parent bytes exactly. Nine other simulator modules match
  parent bytes. All simulator Python syntax and git diff --check pass. No runtime
  benchmarks, dependency installs, commits, agent spawns or launch changes here.
- Request both unchanged official full benchmarks, all saved outputs/gradients and
  fourteen-case seed/pristine generalization on the same exact new revision.
  Independent source review is required before promotion. If promising, compare
  with reviewed parent in interleaved fresh processes under matching CPU/resource
  policy, reporting each sample, separate large/aLIGO medians/ranges, build/total
  tradeoffs, RSS and known overlap. No warm-only or unpaired millisecond claim.
- Decision after feedback: retire if build and complete first-run improvement are
  not repeat-supported. Do not expand to unordered output iteration or global
  setup caches. Next evidence remains supervisor import/build/trace profiling;
  specifically attribute append_information call counts/time and membership costs
  before considering any further builder bookkeeping refinement.
- Inherited pristine signal/loss/gradient findings including33/161/180,
  uifo_rand1/3 sensitivity differences, unresolved grid FD54/59/63/136/161/163
  and first-order reverse-only host VJP remain open. Prior aLIGO29/29 checks are
  bounded evidence. No solver/refinement/adjoint mathematics, compiler flags,
  official stage, frequency/design-variable count or tolerances change.
  Deadline remains2026-11-22 09:27:44 UTC; this is not an evaluated gain.


### Candidate36 feedback — retire membership variant

- Evaluated SHA b2e4eef5090f78e3f0f4af715af3815df5d8d66f;
  evaluation c9a10d266e2541719388392febd33a2f (grid-1/2/3 and aligo-1/2/3).
  Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/c9a10d266e2541719388392febd33a2f.json.
  Both unchanged official benchmarks passed 3/3. confirmed_improvement=false;
  independent source review absent. This is not an admitted improvement.
- Large fresh-process seconds: 0.8383957836776972, 0.803311750292778,
  0.8130866773426533; median 0.8130866773426533; range
  0.803311750292778–0.8383957836776972 (relative range 4.315%).
  Official aLIGO: 0.5479739662259817, 0.5441044643521309,
  0.5454107876867056; median 0.5454107876867056; range
  0.5441044643521309–0.5479739662259817 (relative range 0.709%).
  Versus historical reviewed ee4fea2 medians: large +11.509 ms,
  aLIGO -3.144 ms. These unpaired cohorts overlap; no gain attribution.
- Phase medians in ms (large / aLIGO): imports 273.597 / 263.112;
  initialize 3.534 / 3.550; load 1.525 / 0.210; build 69.950 / 38.362;
  forward lower 19.774 / 19.446, compile 33.943 / 33.890,
  execute 184.014 / 33.295; sensitivity lower 26.752 / 26.265,
  compile 41.227 / 41.415, execute 0.887 / 0.480;
  gradient lower 17.376 / 16.529, compile 52.084 / 53.357,
  execute 83.547 / 14.697; host transfer 0.189 / 0.152.
  Build samples large 69.950, 75.399, 69.209 ms; aLIGO 38.362,
  37.623, 38.738 ms. Against candidate35 build medians, differences
  are -4.945 / +0.424 ms, but35 used a different boundary variant and
  was unpaired. Candidate32's large build median was already70.022 ms.
  Reduced list scans have not established a stable complete-run improvement.
- Sampled peak RSS bytes: large 511107072, 525635584, 508678144;
  aLIGO 305045504, 295251968, 313913344; generalization 928632832.
  No sampled budget exceedance. EPYC9334, CPU2, one logical CPU and
  library threads one, x64, no persistent cache, existing package flags.
  Other-host contention was not excluded; no quiet paired cohort supplied.
- Saved-output comparisons: all carrier/signal/noise/powers/sensitivity/loss/
  gradient checks pass against initial-seed tolerances in six official and
  fourteen generalization cases. Official array archives match candidate35's
  archives. Generalization archive f5fc911e9d380b2bd9aff6bb173cb88e95a54bf07428ecdbc2677232ea6b6834
  differs from the initial-seed archive; passes are not bitwise-seed claims.
  Pristine strict failures persist (including grid signal, loss and gradients;
  aLIGO loss; uifo_rand1/3 sensitivity log differences approximately
  2.0361e-4 / 5.8101e-5). No newly failing seed-relative entries reported.
  Grid FD54/59/63/136/161/163 remain unresolved; prior aLIGO29/29 checks
  remain bounded evidence. Whole-pass VJP remains first-order reverse only.
- Decision: retire36 and restore build.py byte-for-byte to reviewed
  ee4fea28c04d482566be16e916b609d7c6a99e5e. Preserve evaluated revision,
  612-case structural diagnostic and these results; no history reset.
  This restoration is not a new candidate. Do not repeat membership variants
  without attribution evidence. Next: supervisor-run existing
  experiments/notes/overnight-overhead-profile.py --trace-forward with actual
  large, official aLIGO and a third setup; attribute append_information calls
  and build time before selecting another bookkeeping change. No such profile
  has been supplied. Candidate30 remains separately preserved for focused
  diagnostics, independent review and matched-parent confirmation.
- All ten simulator modules match reviewed parent after restoration; syntax and
  whitespace checks passed. No benchmarks, commits, installs or agents launched.
  Stop ends36's hypothesis, not the campaign; deadline remains
  2026-11-22 09:27:44 UTC.


### Candidate37 — construct padded component-input rows in one allocation

- Resumed after36 retirement at supervisor request for a concrete next experiment.
  Keep36 restored; scientific parent ee4fea28c04d482566be16e916b609d7c6a99e5e.
  Only set_instructions' input-padding block differs from this parent. This
  candidate does not retain membership, gather, source-map or row-label variants.
  Candidate SHA and both official job identifiers pending supervisor submission.
- Source-proven redundant work: each function-input row shorter than seven slots
  allocates a float64 zero tail and then a concatenated output, copying the tail
  into that output. For ordinary numeric NumPy arrays, allocate one zero-filled
  output of shape (rows,7), dtype result_type(input.dtype,float64), then copy all
  existing columns into its prefix. This matches the original dtype promotion,
  retains signed zeros in existing values, and leaves positive-zero padding.
  The caller's array is not modified. Width seven and over retain original
  control flow/assertions. Non-numeric arrays and ndarray subclasses retain
  the exact original concatenation path; the guard concerns array semantics,
  not setup identity, shape identity or physical values.
- Distinct target from36: NumPy array allocation/copying inside set_instructions,
  not component membership. Candidate33 removed scalar multiplication of output
  row labels and did not establish a total gain; it is not included. This is a
  narrowly scoped allocation experiment, not evidence that allocation dominates.
  Allocation count falls from two arrays to one per eligible padding call, at
  the cost of a dtype/type guard and result_type call. Their overhead may erase
  the benefit. No physical arithmetic, derivative pruning or solver changes.
- Measured context only:36 build medians69.950 ms large/38.362 ms aLIGO;
  total medians813.087/545.411 ms and import medians273.597/263.112 ms.
  No profile isolates padding time; no37 timing exists. Do not claim this
  recovers an appreciable fraction of build until complete fresh runs show it.
- Local diagnostic experiments/notes/overnight-overhead-padding-check.py
  --structural-only passed918 cases, executing the actual old/new padding AST
  using a small stdlib array model. Covers0–16 rows, widths0–8, numeric and
  fallback dtype-kind guards, caller nonmutation and unchanged identity when
  no padding occurs. This does not validate NumPy casting or JAX gradients.
  Default diagnostic remains UNEXECUTED:960 NumPy full instruction comparisons
  across ten dtypes (including object/string fallback), empty/single/multiple
  rows, widths0–7, contiguous/strided inputs, negative zero, NaN, and sideband
  expansion; plus16 ndarray-subclass/masked-array fallback comparisons.
  Supervisor should execute this focused diagnostic in the fixed environment.
- AST restoration of only this padding block equals the reviewed parent's entire
  build.py AST. Nine other simulator modules match parent bytes. Simulator and
  diagnostic syntax plus git diff --check passed.36's retirement restoration
  remains visible against branch HEAD; no history reset or independent benchmark.
- Request both unchanged full official benchmarks on the exact new revision,
  saved-output/gradient checks and all fourteen generalization cases against
  initial seed and pristine references. If promising, obtain independent source
  review and matched interleaved fresh-process candidate/ee4fea2 samples with
  separate large/aLIGO medians, ranges, phase tradeoffs, memory and overlap.
  Retire if no repeat-supported total improvement; do not expand this into
  further allocation variants without profiling. Existing supervisor-only
  overhead-profile.py is still pending and should attribute set_instructions.
- Inherited pristine signal/loss/gradient disagreements (including33/161/180),
  uifo_rand1/3 sensitivity differences and unresolved grid FD54/59/63/136/161/163
  remain open. Prior aLIGO29/29 checks are bounded; host VJP remains first-order
  reverse only. No change to tolerances, fixtures, workload, outputs, compiler
  settings or three JIT stages. Deadline2026-11-22 09:27:44 UTC unchanged.


### Candidate37 feedback — retire one-allocation padding

- SHA18f3dc6a164d5c402d53afcb5453a4903ddd4580; evaluation
  f69e2e1fae5e4a37a02a2774daa25797, grid-1/2/3 and aligo-1/2/3.
  Receipt: experiments/runs/overnight-20261122/overnight-overhead-v1/f69e2e1fae5e4a37a02a2774daa25797.json.
  Both official benchmarks passed3/3; confirmed_improvement=false and no
  independent source review. Publication declined for insufficient large gain,
  overlapping ranges and missing source review.
- Large fresh-process seconds:0.8274971060454845,0.7945214826613665,
  0.7996367327868938; median0.7996367327868938, range
  0.7945214826613665–0.8274971060454845 (relative4.124%).
  Official aLIGO:0.5615444909781218,0.550166567787528,0.5507460087537766;
  median0.5507460087537766, range0.550166567787528–0.5615444909781218
  (relative2.066%). Historical ee4fea2 median deltas -1.941 ms large and
  +2.191 ms aLIGO are unpaired and do not establish improvement.
- Phase medians ms (large/aLIGO): imports266.635/266.966;
  initialize3.490/3.606; load1.567/0.213; build73.835/39.136;
  forward lower19.661/19.392, compile32.982/33.650, execute179.561/33.120;
  sensitivity lower25.785/26.673, compile40.292/41.296, execute0.887/0.508;
  gradient lower17.012/17.044, compile52.181/53.308, execute84.108/14.364;
  host transfer0.198/0.153. Build samples73.838,73.835,72.404 ms large,
  and39.136,39.522,38.781 ms aLIGO. Compared with36's different bookkeeping
  variant, build medians rise3.885/0.774 ms; this is not a paired attribution.
  There is no demonstrated target-phase saving to justify expanding this idea.
- Sampled peak RSS bytes: large640585728,527347712,522162176;
  aLIGO318533632,295055360,295239680; generalization775553024.
  No sampled budget exceedance. EPYC9334 CPU2, single logical CPU and
  library threads one, x64, no persistent cache, reviewed compiler flags.
  Other-host contention not excluded; no matched quiet parent cohort supplied.
- All saved carrier/signal/noise/powers/sensitivity/loss/gradient comparisons
  pass initial-seed tolerances for six official runs and fourteen generalization
  cases. Official archives equal36's archives. Generalization archive
  cc8efad11c50c2330c4c3475830d8781f96e3ac4ee11200f89866094aa251d59
  is not the initial-seed archive; self-comparison is not independent seed proof.
  Pristine strict mismatches remain inherited: grid signal/loss/gradient,
  aLIGO loss, and uifo_rand1/3 sensitivity log errors2.036099068405406e-4 /
  5.8100919558157216e-5, among recorded generalization disagreements.
  No new seed-relative failures reported. Focused NumPy padding diagnostic
  remains unexecuted locally and no supervisor result was supplied.
- Decision: retire37 and restore build.py to reviewed ee4fea2; all ten simulator
  modules verified byte-identical to parent, syntax and whitespace checks pass.
  Preserve37's exact evaluated revision and diagnostic; no reset or rewritten
  history. This is bookkeeping, not a new evaluated candidate.
  Do not continue row-allocation or membership microvariants without profiling.
  Next concrete experiment is supervisor profiling of set_instructions and
  builder array/device conversion costs using the existing own-note
  overhead-profile.py (full filename overnight-overhead-profile.py), with actual
  large, official aLIGO and third-setup inputs. The narrower candidate30 remains
  preserved separately for focused diagnostics, review and matched-parent runs;
  do not combine pending candidates or replay one noisy cohort as a gain.
- Grid FD54/59/63/136/161/163 remain unresolved; prior extra aLIGO29/29
  does not certify general accuracy. Pristine gradients33/161/180 stay visible.
  Host custom VJP remains first-order reverse only. No benchmarks, installs,
  commits or agents launched. Stop ends37's hypothesis, not the authorized
  campaign. Absolute deadline2026-11-22 09:27:44 UTC remains unchanged.

### Candidate38 — compose the forward output selection with final writes

- New focused experiment following the explicit supervisor continuation request.
  Reviewed simulator parent: ee4fea28c04d482566be16e916b609d7c6a99e5e.
  Branch HEAD before submission: c624d18321bf7386f5ec747edfaa408f32a0c58b.
  Candidate SHA and evaluation/job identifiers: pending supervisor assignment.
  The preserved build.py edit retires37; it restores that module exactly to
  ee4fea2. Candidate38 changes only SystemPlan.values in host_pass.py relative
  to that reviewed simulator. No transfer of additional solver-lane changes.
- Actual redundancy: the forward assembly first gathers every requested output
  with flat_selection, then gathers the last writes with last. SystemPlan already
  stores last_selection=flat_selection[last] and last_positions=writes[last]
  for its reverse pass. Use those existing indices directly in forward assembly.
  Concatenation and evaluation of ALL component groups remain in their original
  order; no current-value test or component/derivative suppression is introduced.
  No arithmetic, solver, refinement, adjoint or callback interface changes.
- Hypothesis: eliminating the intermediate (batch, number-of-writes) gather and
  repeated write-position selection may reduce host forward assembly overhead.
  This is a distinct selection-composition experiment, not another builder
  padding/membership variant or gather-to-JAX-slice trial. It adds no allocation
  strategy, metadata, cache or build-time work. Setup/compile improvements are
  not predicted. It may be too small to distinguish from first-run timing noise.
- Evidence for target phase is limited to candidate37's evaluator observations:
  forward execution medians179.561 ms large /33.120 ms official aLIGO; build
  73.835/39.136 ms; imports266.635/266.966 ms. These are NOT measurements of38
  or an attribution to SystemPlan.values. Candidate38 phase deltas, memory and
  complete first-run timings are unmeasured. The pending profiling artifact
  remains useful; no claim of a measured gain or quiet cohort is made.
- Local validation: 7,381 exhaustive stdlib selection-composition cases passed
  (zero through four writes, repeated destinations and repeated output indices).
  Syntax and whitespace checks passed. AST isolation confirms only values changed
  in host_pass.py; the other nine simulator modules exactly match ee4fea2.
  This is indexing evidence, not NumPy execution or a physical correctness test.
- Focused diagnostic: experiments/notes/overnight-overhead-final-selection-check.py.
  --structural-only was executed. Default NumPy execution remains UNEXECUTED
  locally: this Python lacks NumPy and no dependencies were installed. The default
  extracts the actual candidate values method and compares it with the original
  method over72 cases varying batch size, group widths including an empty group,
  zero/repeated writes, repeated selections, finite values, NaNs, infinities and
  signed zeros. It checks byte-identical results, unchanged component-call order
  and no input mutation. This is a small synthetic check, not an optical benchmark.
- Supervisor request: run the focused NumPy diagnostic, then both unchanged full
  official benchmarks on one exact candidate SHA, save all arrays/gradients,
  run the fourteen-case generalization checks and obtain independent source review.
  If target-phase and complete first-run evidence warrants it, compare repeated
  fresh candidate and ee4fea2 processes interleaved under matching resource policy.
  Report large and aLIGO separately, with every sample, median/range, phase costs,
  sampled memory and overlap information. Do not promote merely on official PASS.
  If no stable improvement, retire38; next step is actual supervisor profiling
  rather than extending this into component pruning or changing derivative math.
- Inherited pristine signal/loss/gradient disagreements, including gradients
  33/161/180, and uifo_rand1/3 sensitivity disagreements remain open. Grid finite
  differences54/59/63/136/161/163 remain unresolved; prior aLIGO29/29 is bounded
  evidence. Whole-pass custom VJP remains first-order reverse mode only.
  All frequencies, design variables, physical outputs, gradients, three JIT
  stages and package compiler settings are preserved. No independent benchmarks,
  installs, commits, agents or infrastructure edits. Deadline unchanged.
