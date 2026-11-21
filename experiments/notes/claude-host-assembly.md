# claude-host-assembly: component functions off XLA, full JAX semantics kept

## Ancestry and constraints
- Branch `explore/claude-host-assembly`, worker `claude-host-assembly` (manual operator, coordinator-assigned).
- Parent `ac49ee4dcc23443f5ffdf4eb740fcdc2e09b1ff7` (claude-sparse-adjoint candidate 3: sparse SuperLU +
  refinement, shared component columns). Full job `4f57030f`: official PASS, strict FAIL (by design,
  dense reference rounding), first run 7.738 s. Parent forward-vjp compile ~4.5 s, gradient compile ~1.1 s.
- Deadline epoch 1795305419. Dev CPU 102 on amd-hackathon (2/34 evaluator lanes, 100 first worker, 101 coordinator).
- Requirement update (coordinator, from the organizer's talk): the simulator must remain an ordinary JAX
  function usable in other tasks. No `custom_vjp` boundaries (they break jvp/jacfwd/forward-over-reverse).
  The first design (a whole-pass `custom_vjp` around a NumPy forward/adjoint) was discarded before any
  candidate for this reason.

## Inventory (8 gencheck setups)
All 19 `FUNCTIONS` are supported by construction (re-bound source, see below); every function used by any
setup goes through the host path. Only `squeezer` and `corrected_optomechanical_phase_right` depend on
conj(input) (probed: antilinear part nonzero), the other 17 are holomorphic in their complex inputs.

## Candidate 1: host component evaluation (custom_jvp) + custom_linear_solve
- `differometor/host.py`: the original component functions are re-bound (`types.FunctionType` with a copied
  globals dict) to a NumPy namespace whose operations accept arrays or first-order Wirtinger duals
  (dy = a dz + b conj(dz); conj swaps a/b). `component_outputs(f, slots, x)` is a `jax.custom_jvp`:
  primal = `pure_callback` (NumPy values); tangent = J dx + K conj(dx) with J, K per-row Jacobian blocks from
  a host callback, contracted by JAX `einsum` (JAX-linear, so JAX transposes it for reverse mode). Only slots
  that read optimized or linked parameters carry tangents (same set as the parent's gradient-stopped slots).
- `differometor/sparse.py`: `sparse_solve` is now `lax.custom_linear_solve` (JAX segment-sum matvec of the
  traced values, SuperLU + refinement callbacks as solve / transpose_solve). The previous custom_vjp is gone.
- `simulate.HOST_COMPONENTS = True` switches `_evaluate_component_columns` to the host path.
- Second order: the solves support it; the component Jacobians come from a callback without a JVP rule, so
  second derivatives through components raise JAX's explicit pure_callback JVP error (documented in host.py).
- Unit verification (CPU 102, all 19 functions x 5 input sets incl. both total-internal-reflection
  orientations of the complex asin, random complex inputs): values, jvp, vjp and jit-vjp match the original
  JAX functions within 6.3e-14 relative (worst: corrected_optomechanical_phase_right); vmap over an extra
  batch axis 4.7e-16.
- Dev smoke (official benchmark.py on CPU 102, not a scored run): PASS; first run 5.270 s: imports 0.273,
  build 0.296, forward lower 0.386 / compile 1.589, forward 0.311, sensitivity lower 0.027 / compile 0.198,
  gradient lower 0.109 / compile 1.879, gradient 0.197; warm median 0.372 s. FD check mb11.tuning autodiff
  7.61617e-5 vs 7.61660e-5 / 7.61582e-5; max |log S - log ref| 5.374e-6.
  Observation: forward compile fell ~3 s; gradient compile rose ~0.8 s (custom_linear_solve transposes and
  matvec linearization instead of the parent's single bwd callback). Unattributed until profiled.
- SHA `4e944016ac4e90680b0b9539e62b9fb915c1a767`. Screen `1df7571460da4618a984990d95f88415`
  (request in .lab/c1-screen-request-id): first run **5.358 s** (parent 7.738 s full), wall 5.87 s,
  peak RSS 0.57 GB. Full `100b6be71db24c7b9766ef74f6143bfb` submitted (result below when recorded).
- Cross-setup (exact tree, CPU 102): vs sparse parent arrays (exact-4af20b7) all 8 OK: grad relL2
  <= 2.0e-10, carrier bitwise, max |dlog S| 2.4e-8 (uifo_rand3, where refined SuperLU itself is ~2.5e-8
  from the extended-precision truth per the first worker), dev 6.5e-10, others <= 6.5e-11. vs pristine:
  same profile as the parent (rand1 2.0e-4 / rand3 5.8e-5 flagged; dense pristine is the inaccurate side).
- jaxcompat (voyager): 9/11 ok — value_and_grad_jit, descent, vmap, jvp, jacfwd, eager, public_run,
  checkpoint, second setup; both HVPs raise the explicit "Pure callbacks do not support JVP" error
  (parent ac49ee4: 7/11, jvp and jacfwd also unsupported because of its custom_vjp).

## Candidate 2: whole-pass host evaluation with an explicit VJP (HOST_PASS = True)
- Coordinator correction: NumPy internals are allowed; reverse-mode gradients on any setup with random
  parameters are mandatory; forward mode is preferred, not mandatory. Keep a faster custom_vjp variant as a
  separate candidate if full semantics cost a substantial part of the compile win.
- `differometor/host_pass.py`: after insertion, linking and qhd phases (JAX), one `custom_vjp` whose fwd/bwd
  are NumPy callbacks: component values and Wirtinger Jacobians from the re-bound source (`host.py`),
  ordered last-write assembly, carrier scaling, sideband conjugation, SuperLU + refinement with one
  factorization per row for the N/H forward and T/N adjoint solves, noise and its adjoint, and the exact
  adjoint of parameter expansion. `HOST_PASS = False` returns to candidate 1.
- Limitation (explicit, never silent): custom_vjp -> jvp, jacfwd and second order raise JAX's errors.
- In-process check vs candidate 1 (JAX autodiff path), jit(value_and_grad): dev loss 8.4e-12, signal 4.3e-10,
  noise 3.3e-10, grad relL2 2.1e-11 (worst normalized 1.0e-9); uifo_20_5000 (2 ports) grad relL2 7.0e-13.
  jit+run of value_and_grad 4.58 s -> 0.88 s. (A first comparison was invalid: `import
  differometor.simulate` binds the re-exported function, not the module, so the flag had not switched.)
- Dev smoke (benchmark.py, CPU 102): PASS, first run 3.141 s: imports 0.295, build 0.825, forward lower
  0.038 / compile 0.265, forward 0.540, sensitivity lower 0.026 / compile 0.207, gradient lower 0.018 /
  compile 0.211, gradient 0.711; warm median 0.425 s; FD autodiff 7.61617e-5 vs 7.61662e-5 / 7.61548e-5.
- SHA `38e356cc2c3eea3165fbffd655262943ba31174c`. Screen `b26c6e365c2b429faa385d8c31cdb72e`: first run
  **1.747 s**: imports 0.300, build 0.305, forward lower 0.036 / compile 0.238, forward 0.219, sensitivity
  lower 0.026 / compile 0.178, gradient lower 0.017 / compile 0.184, gradient 0.239.
  Full `0023e18edcd74c82879c824759364aa6`: **official PASS** (FD mb11.tuning autodiff 7.61617e-5 vs
  7.61662e-5 / 7.61548e-5; max |log S - log ref| 5.374e-6), strict FAIL (same class as the sparse parent),
  first run **1.814 s**, warm median 0.363 s, peak RSS 0.41 GB.
  TIMING CONTAMINATION FLAG: both the screen and this full run overlapped my own dev load on CPU 102 (gencheck
  during the screen, the cProfile run during the full; gradient phase 0.298 s in the full vs 0.239 s in the
  screen). Candidate 1's screen `1df75714` also overlapped a gencheck run. A clean repeat full is queued.
  The dev smoke's 0.825 s build was a cold-cache artifact (queue: 0.305 s).
- Cross-setup (12 cases incl. the coordinator's random-parameter cases): vs sparse parent and vs candidate 1
  all OK (grad relL2 <= 6.4e-10, max |dlog S| 3.2e-8 on uifo_rand3); vs pristine all four random-parameter
  cases hold (max 4.2e-7), only rand1/rand3 flagged as for every sparse candidate.
- jaxcompat (voyager): 7/11 ok; jvp and jacfwd raise "can't apply forward-mode autodiff (jvp) to a
  custom_vjp function", both HVPs raise the pure-callback JVP error. Every first-order test passes.
- Candidate 1 random-parameter cases (dev_randparams, uifo_randparams1-3): all hold vs pristine (max 4.2e-7);
  candidate 1's JAX-autodiff gradient vs candidate 3's hand-written adjoint on those cases: relL2 <= 4.1e-15.
- Context from the coordinator: in the first worker's paired runs, full JAX semantics cost only +0.11 s
  (custom_linear_solve vs custom_vjp solves). Here the gap between candidate 1 (5.36 s screen / 5.70 s full)
  and candidate 2 (1.75 s) is the XLA compile of the JAX-side assembly and solve linearization (forward +
  gradient compile ~3.5 s in candidate 1 vs ~0.4 s), not the solves themselves.

## Candidate 3: candidate 2 + direct SuperLU, NumPy products, factorization reuse
- Profiling candidate 2 (CPU 102): the first forward call spent 0.156 s importing scipy.sparse and
  scipy.sparse.linalg (iterative solvers, array-API layer) of the ~0.31 s first call; the backward refactored
  all 101 signal matrices (0.047 s) and used scipy.sparse products.
- Change (`host_pass.py` only): load SciPy's `_superlu` extension directly and call `gstrf` with exactly the
  options `splu(A, permc_spec="COLAMD")` passes (fallback to `splu` on any failure); a 50x50 probe gave
  bitwise-identical solutions to `splu`. Refinement and noise products use NumPy `add.reduceat` over the
  static pattern, so no scipy.sparse import at all. The backward consumes the forward's signal factorizations
  after a blake2b digest check of the coefficients and drops them; each forward factors afresh, so repeated
  evaluations never reuse a factorization.
- Dev smoke (CPU 102, PASS): first run 1.646 s: imports 0.297, build 0.294, forward lower 0.035 / compile 0.233,
  forward 0.187, sensitivity lower 0.026 / compile 0.173, gradient lower 0.017 / compile 0.179, gradient
  0.201; warm median 0.366 s; FD autodiff 7.61617e-5 vs 7.61623e-5 / 7.61499e-5.
- SHA `645a388be66ba314800f5920615b864d90ef617f`. Cross-setup vs candidate 2: all 12 OK (grad relL2 <= 9.2e-10,
  max |dlog S| 3.5e-8 on uifo_rand3; summation order of the refinement products differs). vs pristine: same
  profile as candidate 2. jaxcompat: 7/11, identical support profile to candidate 2.
- Queue (submitted with no dev load running): screen `f748d1b50ce44488b71fec7f907eee8c`, full
  `3a8c596e5b984d7785045d42e1bd83cf`; candidate 2 clean repeat full `da966d2fe4af4ae2b8bb38517fa9bdc5`.
- Queue results (no dev load during these runs):
  - Candidate 2 clean repeat full `da966d2fe4af4ae2b8bb38517fa9bdc5`: **official PASS**, strict FAIL,
    first run **1.793 s** (contaminated first sample 1.814 s): imports 0.300, build 0.307, forward lower 0.036 /
    compile 0.234, forward 0.251, sensitivity lower 0.026 / compile 0.182, gradient lower 0.027 / compile
    0.199, gradient 0.225; warm median 0.348 s.
  - Candidate 3 screen `f748d1b50ce44488b71fec7f907eee8c`: 1.698 s. Full `3a8c596e5b984d7785045d42e1bd83cf`:
    **official PASS** (FD autodiff 7.61617e-5 vs 7.61623e-5 / 7.61499e-5; max |log S - log ref| 5.374e-6),
    strict FAIL, first run **1.681 s**: imports 0.302, build 0.310, forward lower 0.036 / compile 0.233,
    forward 0.183, sensitivity lower 0.026 / compile 0.181, gradient lower 0.018 / compile 0.183, gradient
    0.203; warm median 0.369 s; peak RSS 0.50 GB; job wall 4.36 s.

## Candidate 4: compile-free host conversions in build
- Build profile (candidate 3, CPU 102): 0.335 s, of which ~0.29 s were 32 eager XLA compilations
  (`jnp.array(x, dtype=...)` binds convert_element_type even for matching dtypes; eager indexing in
  `prepare_arrays`, 11 compilations from one `jnp.array([parameters[0][idx]])`). The Python builder itself
  took ~0.09 s.
- Change (`build.py`): the same values through NumPy (`_host_array`, `jnp.asarray`), no eager jnp ops.
  Remaining eager compilations in the build phase: 2, both in benchmark.py's own input conversion.
- Verification: all 572 built leaves (dev, uifo_20_5000, voyager, random uifo) bitwise identical in values,
  dtypes and shapes to candidate 3 under a fixed PYTHONHASHSEED. Without a fixed seed, voyager's noise index
  order differs between any two processes, including two runs of unchanged candidate 3 (pre-existing string
  hash order in the builder, not this change). Dev benchmark arrays bitwise identical to candidate 3.
- SHA `c4153e7d0058231e80cc56147e139279df929c07`. Dev smoke 1.388 s (build 0.066 s). Cross-setup 12/12
  identical to candidate 3 (zero difference); jaxcompat 7/11, same profile as candidates 2-3.
- Screen `b9b8e08d42474eb597c7254d6b87abb3`: 1.475 s. Full `11dfc8a865af4c3e8c3868f7734983f6`: **official PASS**
  (FD autodiff 7.61617e-5 vs 7.61623e-5 / 7.61499e-5; max |log S - log ref| 5.374e-6), strict FAIL (same class),
  first run **1.446 s**: imports 0.301, build 0.073, forward lower 0.036 / compile 0.247 / exec 0.186,
  sensitivity lower 0.026 / compile 0.179, gradient lower 0.017 / compile 0.184 / exec 0.191; warm median
  0.372 s; peak RSS 0.54 GB. Branch best.

## Candidate 5: package-level XLA compiler settings (final candidate)
- Organizer answers relayed by the coordinator: custom_vjp + SciPy host code allowed, forward mode not required;
  XLA/JAX settings set by the package are allowed if correctness holds and the gain transfers. Final evaluation:
  one logical CPU, JIT counts, setup "similar to the bigger one"; upstream added benchmark_aligo.py (83f8d2f).
- Screening of single settings on candidate 4 (benchmark.py, CPU 102, fresh processes, two runs each, set via the
  process environment): baseline 1.386-1.407 s (compile f/s/g 0.24/0.175/0.18); jax_disable_most_optimizations
  1.168-1.170 s; --xla_backend_optimization_level=0 1.163-1.178 s (same effect); --xla_cpu_use_fusion_emitters=false
  1.25 s (gradient compile unchanged); --xla_llvm_disable_expensive_passes no change. Combination opt-level 0 +
  fusion emitters off: 0.958-0.964 s (compile 0.074/0.038/0.052); with jax_disable_most_optimizations instead of
  the opt-level flag: identical. Execution and warm times unchanged within noise.
- Change (`differometor/__init__.py`): append `--xla_backend_optimization_level=0 --xla_cpu_use_fusion_emitters=false`
  to XLA_FLAGS before importing submodules (never overriding flags the user set; DIFFEROMETOR_XLA_DEFAULTS=0 opts
  out). Effective because benchmark.py (old and upstream 83f8d2f) imports differometor at module level before
  `jax.devices("cpu")` creates the backend. Verified in-package (no shell flags): 0.958 / 1.000 s, compile
  0.074/0.038/0.052, report `environment.xla_flags` shows the flags; opt-out run 1.389 s. Applies to every XLA
  program in the process.
- Numerics vs candidate 4: carrier, signal, noise bitwise identical; dev gradient relL2 4.2e-10 (worst normalized
  4.2e-9 on a small entry; deterministic across runs), sensitivity max rel 2.7e-16. 12-case gencheck vs c4153e7:
  forward outputs bitwise on all 12 setups, grad relL2 <= 4.2e-10, max |dlog S| 9.1e-9 (uifo_rand3); vs pristine
  same profile as all sparse candidates (rand1/rand3 dense-side flags; random-parameter cases hold <= 4.2e-7).
  jaxcompat 7/11 (unchanged profile).
- SHA `53f38d342c3228c052785e8c9d63b6ce9c832dd1`. Queue (idle host, no dev load): screen
  `c27c4dcbb4a142bd9e0dc26f68e9a59d`, full `fe365a2f512a446a8357e53e6cb45ec4`. BOTH REJECTED BY THE LAB WORKER'S
  CONFIGURATION GUARD (`lab/worker.py:227`: "Report has unexpected OpenMP or XLA configuration"), which still
  enforces the earlier no-XLA-flags policy. Not modified or bypassed (protected evaluator); needs a maintainer
  policy update. The benchmark itself completed and printed PASS in the full run: first run **1.005 s** (screen
  1.014 s): imports 0.302, build 0.071, forward lower 0.037 / compile 0.079 / exec 0.186, sensitivity lower 0.026 /
  compile 0.040, gradient lower 0.017 / compile 0.054 / exec 0.188; warm median 0.360 s; FD mb11.tuning
  autodiff 7.61617e-5 vs 7.61623e-5 / 7.61499e-5 (passed); max |log S - log ref| 5.374e-6. No official/strict
  verdict was recorded by the queue because of the guard.
- aLIGO transfer (upstream benchmark.py + benchmark_aligo.py from 83f8d2f in scratch trees on AMD CPU 102, never
  committed; 101 frequencies, 29 gradients, tolerance 1e-6, FD on sq1.db): pristine 20.731 s (compile
  13.363/0.196/4.610), max log error 1.23e-10, PASS; c4153e7 1.069 s (compile 0.238/0.175/0.182), 2.87e-11, PASS;
  53f38d3 **0.642 s** (compile 0.074/0.039/0.054, flags shown in report), 2.87e-11, PASS. vs pristine: max |dlog S|
  1.2e-10, grad relL2 2.7e-10; 53f38d3 vs c4153e7 forward bitwise, gradient 1.1e-15. Warm 0.048 -> 0.057 s
  (opt-level 0 slows the small XLA parts slightly; first run unaffected).
- Stop: coordinator instruction; no further candidates.
