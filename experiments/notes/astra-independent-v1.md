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
