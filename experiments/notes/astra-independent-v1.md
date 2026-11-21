# Independent session: astra-independent-v1

Original public baseline: `02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f`.
All candidates in this log belong to this independent session. The supervisor
owns the launch time, fixed one-hour deadline, commits, and evaluations.

## Candidate 1: group component function dispatch

Code inspection: `simulate.update` batches a dynamic `lax.switch` over the full
component registry. Carrier, signal, and noise updates all use this operation.
The component type of each instruction is already known to the builder.

Change: the builder emits a dictionary mapping function IDs to original input
row indices. JAX treats dictionary keys as pytree structure. The update function
vectorizes each selected function on only its own rows and restores outputs to
the original ordering before the unchanged matrix scatter. Legacy array-form
function selectors retain their original implementation. The dictionaries store
only topology; all component values and derivatives are computed for each call.

Hypothesis (unmeasured): avoiding evaluation and differentiation of unrelated
component branches will reduce lowering/compilation cost and AD residual size,
potentially improving forward and reverse execution as well. No speedup is
claimed before supervisor measurements.

Preserved: optical formulas, complete matrices, frequencies, design variables,
complex128/double precision, solves, noise propagation, readout, and the three
official JIT stages. Benchmark, fixtures, dependencies, and evaluator untouched.

Local checks: both edited modules passed Python AST parsing. The available
`python3` cannot import JAX (`No module named 'jax'`), so no local numerical
check was possible. No benchmark was run and no dependencies were installed.

Measured outcomes: none yet. Await the unchanged full benchmark, its official
sensitivity and gradient sanity checks, and the separate strict comparison of
all saved physical outputs and gradients. Any changed floating-point fusion or
reduction behavior must be judged by those numerical checks.

### Candidate 1 evaluator outcome

SHA: `8463bab9382e890c98b59768115d0f431a2a5e7e`.
Screen run `740885ac873844be93a382e054a43751`: first run 28.279287 s;
screen checks passed (finite-difference check not run).
Full run `742073c9586d457d913b4f4e96cf25a9`: first run 28.335268 s,
warm median 15.234937 s, evaluator wall time 113.845467 s. These are separate
metrics. Full first-run phases: build 0.734471 s, forward lower 0.796093 s,
forward compile 8.107484 s, forward execution 12.154792 s, sensitivity lower
0.090337 s, sensitivity compile 0.490607 s, gradient lower 0.207830 s,
gradient compile 2.560971 s, gradient execution 2.894920 s.
Peak RSS 14,461,752 KiB. One pinned CPU, AMD EPYC 9334; timings remain exploratory
under shared evaluation conditions. No baseline timing was supplied in this
session, so no baseline speedup is established here.

Official checks passed: max absolute log sensitivity error 5.374104176780747e-6;
193 finite, nonzero gradients, norm 70517.10686388786. Gradient spot-check AD
7.616169103001766e-5; finite differences 7.567622019997994e-5 (step 1e-3) and
7.609197854652979e-5 (step 5e-4), both passed.
Separate strict regression passed at rtol 1e-7 and scale_atol 1e-12. Carrier,
signal, noise, sensitivity, powers, parameters, and frequencies were exact.
Gradient max absolute error 2.6020852139652106e-18, relative L2 error
3.69040600052152e-23, max normalized error 4.5036895692410154e-11.

## Candidate 2: reuse signal-system LU factors

Based on candidate 1. Compute one LU factorization per frequency and use it for
the signal field, adjoint noise weights, and propagated noise covariances.
Use `lax.custom_linear_solve` to retain differentiation through the defining
linear equations, including matrix dependence. Factors are stop-gradient
implementation intermediates computed anew inside every simulation; no answers
or factors are cached between evaluations. Complex transpose and adjoint solves
are distinguished explicitly. The carrier solve remains unchanged.

Hypothesis (unmeasured): reusing factors will reduce forward factorization work,
residual storage, and reverse solve overhead. Main numerical risk: solving the
adjoint via the original matrix's factors rather than independently factoring
the adjoint can change rounding in this sensitive system. Full official and
strict saved-array checks are required, with neither replacing the other.

Local checks: Python AST parsing and git diff --check passed. JAX remains
unavailable locally, so no numerical run was made. Await supervisor evaluation.
