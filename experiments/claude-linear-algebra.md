# Claude linear algebra investigation

You own explore/linear-algebra-audit and its isolated worktree. This is a simulator optimization direction, not evaluator maintenance. The coordinating user has explicitly requested this new Claude Opus 5.5 session. Its separate initial time budget is at most 60 minutes; it does not extend the Codex seed session. No candidate-count cap applies, but this first stage ends after the investigation deliverable.

Read AGENTS.md, .wiki/README.md, .wiki/experiment-rules.md and .wiki/runbook.md. The managed supervisor owns commits, pushes, SSH, queue submission and result collection. Do not run those operations yourself. Do not modify lab/**, tests/**, benchmark.py, plot_timings.py, dependencies, fixtures, the shared environment or another worktree. Do not spawn agents or services.

## First stage: investigate and propose, then stop

1. Establish matrix dimensions and structural sparsity. Distinguish entries that are always zero from entries that happen to be zero at the starting parameters, since those can contribute to gradients. Trace assembly and parameter dependence; do not claim counts inferred from source are measured counts.
2. Investigate factorization reuse across signal and noise solves. The installed JAX solver already reuses LU within differentiation; that alone does not prove sharing across separate calls. Compiled HLO has not yet been inspected. You have file tools only in this initial launcher, so report precisely which compiled diagnostics need an authorized queued follow-up; do not invent measurements or bypass the evaluator.
3. Propose one focused next experiment: factorization sharing, a block decomposition or sparse assembly/solves, selected from your evidence. Explain derivative correctness, conversion cost, setup/compilation and first-run cost. A negative conclusion is useful.
4. Write the evidence, unresolved questions and proposal to experiments/notes/claude-linear-algebra.md. For this first stage do not edit differometor or submit an evaluation. Return the supervisor JSON with ready_for_evaluation=false and stop=true. This ends the investigation for user review, retaining a resumable Claude conversation.

## Existing evidence

The unchanged AMD baseline median first-run time is 35.737065 seconds. Full workload: 101 frequencies, 193 physical parameters, float64/complex128, one logical CPU pinned to CPU 2, three official JIT stages, no persistent compilation cache. Carrier output is (286,1), signal (751,101), noise (101). Source/fixture analysis by the other agent found one noise detector; verify rather than assuming a multiple-detector optimization helps.

The earlier candidate 5 (3c9717f9254e94d5b441401a75dbc79b7b4b4d8c) measured 28.971828 seconds, with official and strict array checks passing. It changes scalar component dispatch and matrix conjugation, not sparse linear algebra. Later results may supersede that best time. Do not edit or take ownership of explore/seed-agent. Your starting code is the unchanged simulator plus lab infrastructure on main, so distinguish baseline analysis from combining another candidate's changes.

If later authorized to implement: the supervisor submits the exact commit through the shared serial queue, screens it, runs full validation when eligible, then resumes this conversation with feedback. Compare first-run and phase timings, memory, all saved physical outputs and gradients. Screen results alone are provisional. Keep the full optical setup, all frequencies and variables, double precision and physics. No hardcoded answers or persistent compilation caching.
