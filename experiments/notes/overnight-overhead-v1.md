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
