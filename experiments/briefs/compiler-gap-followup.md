# Compiler and algorithmic gap: focused continuation

Coordinator research guidance, not measured speed claims. The user reports a
different team's compilation at roughly four seconds, versus our approximately
eleven seconds combined lowering/compilation. A separate team reportedly achieved
three seconds under an unspecified timing boundary. Do not combine these reports
into one benchmark or change our full first-run objective.

Keep existing session identity, deadline, full workload, double precision, strict
output/gradient validation and managed editing rules. Let an active candidate
finish before applying a new direction. One owned candidate per turn; preserve
failed trials. Numerical controller menus remain separately owned.

## Claude: specialize genuinely structural indexing metadata

Inspect `build._group_component_indices`: component parameter indices, output
permutations and destination offsets currently become JAX array leaves. They pass
through the official runtime `arrays` pytree, preventing tracing-time
specialization of fixed topology. Begin with one family of integer indices,
represented as immutable hashable pytree auxiliary data; materialize constants
where required inside the trace. Keep design parameters, frequencies, matrices
and computed physical values dynamic. Do not bake in answers or cache compiled
executables. A generic static topology representation must derive from the setup,
not from challenge-specific expected outputs.

Hypothesis: remove dynamic gather/index/transpose bookkeeping rather than merely
save or recompute it. Constants can also increase HLO and compilation, so verify
the complete first-run and combined compilation costs. This is unmeasured. Do
not continue optimizing tiny build costs without a source-grounded larger lever.

## Astra: emit sparse update values from the frequency scan

Finish the current narrowed-checkpoint experiment first; another agent must not
duplicate it. A distinct next hypothesis is changing `block_assemble` inside
`_map_row_chunks` to emit component update values rather than complete dense
signal matrices. Preserve component evaluation and carrier-scaling arithmetic
order. Outside the scan, broadcast the base matrices and perform batched
scatter/conjugation; retain the full-vmap solves and separate adjoint pivoting.
Preserve duplicate-index guards/fallback, all parameter-dependent updates and
every frequency. Do not move solves into the scan: that topology was already
tried and is not this hypothesis.

Hypothesis: reduce dense loop outputs/residuals and the assembly graph that
reverse-mode transforms. First establish update-count versus matrix-size and
the exact existing duplicate semantics. No speed or numerical-equivalence claim
is established until full evaluation.

## Evidence and longer structural research

Astra candidate 6 recorded first-run 21.826 seconds, forward compile 4.567,
gradient compile 4.613, forward execute 8.522, gradient execute 1.476. Whole-body
checkpointing largely redistributed compilation, so optimizing one compile stage
alone is insufficient. These are individual observations in an exploratory
execution regime, not confirmed improvement.

The fixture has 71 prescribed signal sources and 54 free masses. Source rows are
unit equations; optical ports have input/output pairs; force/displacement add
auxiliary equations. Proving a unit-triangular elimination partition could reduce
the factorization dimension substantially while reconstructing all outputs.
That is distinct from the failed ill-conditioned block Schur attempt. It needs
structural union-of-writes analysis and arbitrary-RHS/transpose derivation before
implementation, including noise RHS. Do not naively reuse A's LU for A^H: prior
attempts failed strict gradients. Sparse solvers are not a drop-in substitute;
batching, pivoting, differentiation and full costs require separate design.

Deeper HLO/Jaxpr diagnostics are being prepared separately and do not yet exist
as a runnable evaluator profile. Do not invent attribution or bypass the queue.
If blocked, name the exact structural fact or diagnostic required in the handoff.
