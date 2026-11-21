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
