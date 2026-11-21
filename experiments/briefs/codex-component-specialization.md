# Codex: specialize component dispatch without changing physics

You own explore/component-specialization. This new 60-minute session is distinct from the expired seed-agent session. Your starting simulator is validated candidate 8, 1e552d675c3795265be8af1ac23ffb61f90f30b1, whose repeated full measurements on the audited AMD policy are approximately 28.09 seconds versus 35.72 seconds for unchanged code. It uses scalar component mapping, a reusable JIT helper, a conjugation mask and branch-local checkpointing. Preserve these gains unless evidence justifies an isolated alternative.

Read AGENTS.md and this brief. Read experiments/context/search-initial.md and inspect experiments/context/search-initial.json for the committed search-context snapshot with prior hypotheses and failures. Its evidence is context, not permission to weaken rules. All 101 frequencies and 193 design variables remain fixed required work; do not optimize a subset of physical variables. Do not run independent benchmarks or change the environment.

## Direction

Investigate whether component types and matrix-update structure can be classified during setup so the traced simulator performs less runtime branch selection. The seed agent explored scalar lax.map versus batched switching and checkpoint placement, but did not implement a measured, static grouping of component updates by type. Claude owns factorization sharing and block/Schur solvers; leave that direction alone. Its first shared-LU rewrite passed the official check but failed three strict gradient comparisons. Do not combine that unvalidated numerical rewrite with your candidate.

First write source-based evidence and one proposal in experiments/notes/component-specialization.md. Determine whether grouping is safe and compatible with the public setup/build API and the unchanged three JIT stages. Function indices currently arrive as JAX arrays, so do not assume they are Python constants or attempt host conversion of traced values. Consider preparing structural groups in the builder and retaining the full dynamic parameter dependence. Parameter-dependent zeros must never be dropped. Setup cost counts; compile-time savings must outweigh extra preparation.

If the design is justified, implement one focused change in differometor/**. Preserve generic simulator behavior and the full optical fixture. It is acceptable to reject grouping after investigation and choose a smaller related matrix-assembly/dispatch improvement, provided you record why it is distinct from prior trials. Do not invent HLO measurements or speedups.

The supervisor commits and publishes each candidate, submits its exact SHA through the shared serial CPU2 queue, runs screen then full validation when eligible, and resumes this conversation with results. Do not commit, push, use GitHub/SSH, spawn agents, change the evaluator or run the benchmark yourself. Return summary, hypothesis, ready_for_evaluation, stop and notes. A full official and strict saved-output/gradient pass is needed for shared promotion; keep strict-only failures as unresolved evidence. At the time limit write a handoff and preserve all history; no silent extension.

## Combination policy

Your parent candidate is the validated seed8. Additional combinations require named parent SHAs, compatible implementation assumptions, a separate candidate and fresh full evaluation. Shared physical parameters or overlapping files are not proof of compatibility. Track total first-run time as the ranking objective and phase times/memory as explanatory objectives; observed Pareto membership does not establish repeatable superiority.
