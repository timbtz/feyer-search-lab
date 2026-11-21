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

### Candidate 2 evaluator outcome: strict gradient failure

SHA `332711932fd574654d7c126c08214963dfa936de`; screen
`6e229f962370431d80ea2dbeb30ca7ce` passed its limited checks, first run
23.858653 s. Full run `f35960545cc84aa590113a7e4373a099` passed the official
benchmark but FAILED the separate strict gradient comparison. First run
24.163514 s, warm median 10.550067 s, job wall 83.661997 s, peak RSS
11,787,536 KiB. Forward execution 7.966104 s, forward compile 8.131370 s,
gradient execution 2.927165 s, gradient compile 2.605498 s.

Official maximum log sensitivity error 5.374693557769206e-6. Gradient norm
70517.10415767653. Spot check AD 7.616168789635325e-5, finite differences
7.615022986170543e-5 and 7.634971240986935e-5, both passed.
Strict comparison: carrier, signal, powers, parameters, frequencies exact.
Noise max absolute error 6.47193338752091e-17, relative L2 2.2428226645922417e-8;
sensitivity max absolute error 9.264707375859949e-33, relative L2
3.533068791353602e-9; both passed (max normalized errors approximately 0.6445).
Gradient max absolute error 0.002276105820783414, relative L2
3.852202505287248e-8; three failures at indices 33, 161, 180. Their absolute
errors were 2.108833427882928e-5, 4.4243855700898393e-5, 3.3806126520374846e-7;
normalized errors 3.038587, 14.655745, 1.626675. This candidate is not accepted
as numerically equivalent despite passing official checks and running faster.

## Candidate 3: preserve independent adjoint factorization

Repair candidate 2 by restoring the original `solve` on the conjugate transpose.
Keep explicit LU reuse only between the signal and covariance solves, which use
identical matrices. Simplify the factor-aware solver to ordinary solves and
their plain-transpose AD solves. Candidate 2's exact signal and carrier outputs
support focusing the repair on the adjoint pathway; this remains a hypothesis.

Expected result (unmeasured): restore strict agreement while potentially keeping
some factor-reuse benefit. The removed adjoint reuse may surrender most of
candidate 2's speedup; measurement must determine that. Candidate 1 remains the
last fully validated candidate. All checks and workloads remain unchanged.

Local checks: AST parsing and git diff --check passed. No local numerical check
or benchmark; supervisor evaluation pending.

### Candidate 3 evaluator outcome: validated

SHA `496ccefe934a87e55e695db450f24520bd47fbac`; screen
`731decb118644bb3b01497d23bcf3db0`: 27.316873 s, limited checks passed.
Full `d8e402872b1d40fbac3aeb9ab7490894`: official AND strict regression passed.
First run 27.188263 s; warm median 14.067015 s; job wall 109.401669 s;
peak RSS 12,677,304 KiB. Forward lower/compile/execute
0.808863 / 8.056939 / 11.153533 s; gradient lower/compile/execute
0.218092 / 2.589088 / 2.772124 s. Build 0.721193 s.

Official max log sensitivity error 5.374104176780747e-6; gradient norm
70517.10686388786; finite-difference checks passed with the same values as
candidate 1. Strict saved physical outputs, parameters, and frequencies exact;
gradient max absolute error 2.6020852139652106e-18, relative L2
3.69040600052152e-23, maximum normalized error 4.5036895692410154e-11.
The independent adjoint factorization repaired candidate 2's discrepancy.
Candidate 3 is the current validated working basis. Its recorded first run is
1.147006 s lower than candidate 1's; shared-host observations are exploratory.

## Candidate 4: assemble conjugated matrix blocks directly

Replace three dense slice scatters in the sideband conjugation step with
concatenation of disjoint blocks. Middle-row conjugated blocks are adjacent,
including the RHS, so they can be conjugated together. The top rows and other
blocks retain exactly the original values. No solve or physical formula changes.

Hypothesis (unmeasured): simpler block assembly reduces large scatter lowering,
compilation, and reverse-AD memory traffic. Candidate 3 still spends about
8 seconds compiling the forward stage and 11 seconds executing it.

Local validation: Python AST parsing, git diff --check, and nine pure-Python
complex block-partition equivalence cases passed (including empty mechanical
blocks and the RHS column). JAX/full numerical validation awaits supervisor;
no benchmark was run locally.
