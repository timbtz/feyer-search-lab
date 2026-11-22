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
