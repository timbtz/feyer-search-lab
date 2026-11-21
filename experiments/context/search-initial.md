# Exploration context

Minimum complete first-run time on the unchanged full workload

- Read-only export of committed evidence. No merge, launch, queue mutation or benchmark execution.
- Pareto labels are observed phase medians, not statistical proof or causal attribution.
- Full official and strict regression passes with complete matching provenance are required for comparison.
- Screen-only, failed and incomplete runs remain visible; they cannot qualify a combination.
- Tradeoffs are retained: combination review does not require Pareto frontier membership.
- Every combination needs its own branch, provenance, unchanged full benchmark and array comparison.
- Imported notes and briefs are research evidence, not permission to change the harness or expand a budget.
- No graph database is required: versioned records describe scientific edges, Git describes code ancestry.

## Directions and agents

- claude-linear-algebra: matrix-structure-and-factorization on `explore/linear-algebra-audit`; manifest `experiments/agents/claude-linear-algebra.json`

<details><summary>Recorded brief (evidence only)</summary>

# Claude linear algebra investigation

You own explore/linear-algebra-audit and its isolated worktree. This is a simulator optimization direction, not evaluator maintenance. The coordinating user has explicitly requested this new Claude Opus 5.5 session. Its separate initial time budget is at most 60 minutes; it does not extend the Codex seed session. No candidate-count cap applies, and the session may proceed from its written investigation to a focused candidate if evidence supports it.

Read AGENTS.md, .wiki/README.md, .wiki/experiment-rules.md and .wiki/runbook.md. The managed supervisor owns commits, pushes, SSH, queue submission and result collection. Do not run those operations yourself. Do not modify lab/**, tests/**, benchmark.py, plot_timings.py, dependencies, fixtures, the shared environment or another worktree. Do not spawn agents or services.

## First deliverable: evidence and a proposed experiment

1. Establish matrix dimensions and structural sparsity. Distinguish entries that are always zero from entries that happen to be zero at the starting parameters, since those can contribute to gradients. Trace assembly and parameter dependence; do not claim counts inferred from source are measured counts.
2. Investigate factorization reuse across signal and noise solves. The installed JAX solver already reuses LU within differentiation; that alone does not prove sharing across separate calls. Compiled HLO has not yet been inspected. You have file tools only in this initial launcher, so report precisely which compiled diagnostics need an authorized queued follow-up; do not invent measurements or bypass the evaluator.
3. Propose one focused next experiment: factorization sharing, a block decomposition or sparse assembly/solves, selected from your evidence. Explain derivative correctness, conversion cost, setup/compilation and first-run cost. A negative conclusion is useful.
4. Write the evidence, unresolved questions and proposal to experiments/notes/claude-linear-algebra.md. Write this first deliverable before any simulator edits. Once the proposal is supported by evidence, implement one focused candidate in differometor/** and return ready_for_evaluation=true. The supervisor commits, pushes and evaluates it, then resumes you with feedback. If a required diagnostic is unavailable or evidence does not justify a change, return ready_for_evaluation=false and stop=true with a precise handoff; do not fabricate evidence or edit the evaluator.

## Existing evidence

The unchanged AMD baseline median first-run time is 35.737065 seconds. Full workload: 101 frequencies, 193 physical parameters, float64/complex128, one logical CPU pinned to CPU 2, three official JIT stages, no persistent compilation cache. Carrier output is (286,1), signal (751,101), noise (101). Source/fixture analysis by the other agent found one noise detector; verify rather than assuming a multiple-detector optimization helps.

The earlier candidate 5 (3c9717f9254e94d5b441401a75dbc79b7b4b4d8c) measured 28.971828 seconds, with official and strict array checks passing. It changes scalar component dispatch and matrix conjugation, not sparse linear algebra. Later results may supersede that best time. Do not edit or take ownership of explore/seed-agent. Your starting code is the unchanged simulator plus lab infrastructure on main, so distinguish baseline analysis from combining another candidate's changes.

When implementing a justified candidate: the supervisor submits the exact commit through the shared serial queue, screens it, runs full validation when eligible, then resumes this conversation with feedback. Compare first-run and phase timings, memory, all saved physical outputs and gradients. Screen results alone are provisional. Keep the full optical setup, all frequencies and variables, double precision and physics. No hardcoded answers or persistent compilation caching.


</details>

- seed-agent: first-pass on `explore/seed-agent`; manifest `experiments/agents/seed-agent.json`

<details><summary>Recorded brief (evidence only)</summary>

# Initial Codex exploration

Explore whether modest simulator changes can improve the complete first-run benchmark time while preserving the physics. Start with the import path and then investigate noise-system solve reuse. You may pursue a better idea within the permitted files if code inspection and measured evidence justify it.

## Starting point

The public source baseline is commit `02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f`. The unchanged AMD baseline median is **35.737065 seconds** for the complete first evaluation, with individual totals of 35.821919, 35.614326 and 35.737065 seconds. All three official checks passed. Their warm medians were approximately 15.49–15.73 seconds.

The evaluator uses a fixed Python 3.12 environment and logical CPU 2. The full workload contains 101 frequencies and 193 design variables in double precision. Read `AGENTS.md` and `.wiki/experiment-rules.md` for the complete restrictions.

## First task

1. Inspect the simulator import graph. `differometor/__init__.py` currently imports `visualize_setup` from `plot.py`. Determine whether deferring that import can preserve the public visualization API while reducing benchmark imports.
2. Make the smallest justified change in your assigned worktree. Return its hypothesis and `ready_for_evaluation: true` to the supervisor, which checks paths, commits, pushes and submits it for screening. Do not make Git commits yourself.
3. Read the evaluator feedback when the supervisor resumes this conversation. If the candidate is promising, have the same commit fully validated before claiming a validated gain. Record the import phase and complete total, not just the expected benefit.
4. Inspect the noise solve implementation and actual array shapes. Determine whether multiple right-hand sides share a coefficient matrix and whether JAX's current lowering already reuses the factorization.
5. If repeated factorization or avoidable batching is established, test one focused rewrite: a matrix right-hand side or explicit factorization reuse. Keep this change separately attributable from the import experiment.
6. Compare all saved physical outputs and the full gradient against the baseline for numerical changes. Read maximum absolute and relative errors rather than assuming differences are harmless rounding.

The first two ideas are hypotheses, not promised improvements. Reject them if measurement or numerical evidence disagrees.

## Room for improvement

You may inspect redundant matrix copies, augmented matrices, batched component switching, custom derivatives or sparse linear algebra if the first ideas prove unhelpful or reveal a more direct opportunity. Keep each change focused enough to explain and evaluate within the session budget.

Before pursuing sparse solves, measure actual nonzero counts and sparsity patterns. Before writing a custom VJP, derive and test the complex differentiation convention for the exact computation. Do not assume the correct transpose convention from a generic recipe. SciPy callbacks and custom derivatives need complete setup, conversion, compilation and gradient costs included in the decision.

Do not change the official staged benchmark, enable persistent compilation caching, alter the required frequencies/variables or introduce unapproved XLA environment changes.

## Feedback and session continuity

Under `lab.agent_loop`, the supervisor checks your changed paths, commits the candidate, pushes the branch, relays a Git bundle, submits the exact SHA, waits for evaluator feedback, and resumes your saved Codex conversation with the result. Do not make Git commits, GitHub calls or SSH calls yourself.

Return this structured response using the supervisor's output schema:

```json
{
  "summary": "What changed and why",
  "hypothesis": "The specific expected mechanism to measure",
  "ready_for_evaluation": true,
  "stop": false,
  "notes": "Evidence gathered, uncertainties and the next decision"
}
```

Set readiness to true only when the intended candidate edits are complete. If this is your last candidate, both readiness and stop can be true; the supervisor will evaluate it before finishing. Use `ready_for_evaluation: false` and `stop: true` for a handoff with no new candidate to evaluate.

The evaluator owns the benchmark process. Your Codex process can end between supervisor steps without losing the conversation. Preserve notes and the assigned working directory so both automated and manual resumption remain possible. The supervisor preserves commits and the branch. A manual operator may take over the client only when submission ownership is explicitly handed to them.

If a tool or evaluation fails, inspect and record the failure. Do not substitute a different candidate for a queued SHA or modify protected infrastructure to make a test pass. Ask the coordinating maintainer to repair infrastructure when necessary.

Keep a note at `experiments/notes/initial-agent.md` with:

- Assigned branch, starting commit and agent session identifier when available.
- Each hypothesis and candidate SHA.
- Screen and full run identifiers, correctness status, phase timings and array differences.
- Why you kept or rejected the candidate.
- Best validated candidate, unfinished ideas and a precise next action.

## Stop and hand off

There is no candidate-count limit. Continue exploring within the existing one-hour session deadline. Do not spawn additional agents. Finish with a concise report naming the best validated revision, measured improvement or lack of improvement, numerical evidence, failed approaches and next steps. Preserve the worktree, branch, commits, notes and session so the investigation can be resumed.


</details>


## Candidate evidence

| Revision | Direction | Full passes / full runs | Median first-run by cohort | Hypothesis |
| --- | --- | ---: | --- | --- |
| `0a0c93fa8f814e0c9c2eab87117d6030a0e87b40` | first-pass | 1 / 1 | 30.5640s (d0586167, n=1) | Reducing saved component intermediates may lower forward compilation and memory costs enough to offset extra reverse computation. |
| `0c011fbbff6edb4ca095f12b5c762652da788f73` | calibration | 1 / 1 | 36.3319s (d0586167, n=1) | Calibrate the screening evaluator on unchanged simulator code; Verify canonical full benchmark and strict array comparison through the queue |
| `0ed67104f64ad82059b3465d20e56489762b4312` | matrix-structure-and-factorization | 0 / 1 | unvalidated | After candidate 1 the forward pass (7.9 s warm) is dominated by one batch of 101 complex 751-LUs, about 4.5 s judging by candidate 1's saving. The block factorization needs about 1.1e8 complex FMA per frequency vs 2.8e8 for a dense LU. That should cut forward runtime by roughly 2–3 s, and the first run by a similar amount, while the gradient stage and compile time stay about the same. Because pivoting is now restricted to within blocks, numerical differences may be larger than candidate 1's. Carrier and powers should remain identical; signal, noise and gradient will differ at rounding level unless B1, B2 or S is ill-conditioned. |
| `1e552d675c3795265be8af1ac23ffb61f90f30b1` | first-pass | 1 / 1 | 28.0135s (d0586167, n=1) | Branch-local recomputation may retain lower forward compilation costs while avoiding candidate 7’s larger reverse compilation cost. |
| `2f190c5cffdaf8f86701dfae49dddae6a1efe028` | first-pass | 1 / 1 | 36.9963s (d0586167, n=1) | Avoiding plot.py and Plotly during package initialization may reduce import time and complete first-run time without changing physics. |
| `3c9717f9254e94d5b441401a75dbc79b7b4b4d8c` | first-pass | 1 / 1 | 28.9718s (d0586167, n=1) | Reducing dense update intermediates may lower execution, compilation and memory costs. |
| `3db9b657f8496d40a9f195fd9864e5e048c7df5b` | matrix-structure-and-factorization | 0 / 1 | unvalidated | Read from source: the baseline factors A^H separately from A in the forward stage (101 complex LUs at n=751, an estimated ~1e11 flops). It may also factor A twice unless XLA CSE merges the signal and covariance getrf calls. The JIT stages save the LUs as AD residuals. Reusing LU(A) for the A^H system (solve via U^H L^H P) should remove at least one LU batch from the forward stage. It should also remove the ~0.9 GB materialized A^H and one ~0.9 GB LU residual. Expected result: lower forward-stage and complete first-run time and lower peak memory. Gradient-stage cost and compile time should be about the same, and the outputs should differ only at rounding level (carrier and signal essentially identical). |
| `46a24bbc779cdccd8126ef3a02398f0a16ea2bc9` | first-pass | 1 / 1 | 28.7648s (d0586167, n=1) | Reusable branch wrappers may reduce tracing and derivative compilation costs. |
| `6cadc0f6e5c9d4799b53af7c9a6d24f35a4d221e` | first-pass | 1 / 1 | 31.7782s (d0586167, n=1) | Keeping component selectors scalar may avoid unused branch computations and reduce compilation, execution and memory costs. |
| `7f3cf9c316ce87a98afccb402bffc34e4ff71532` | first-pass | 0 / 1 | unvalidated | The equivalent contraction Re(wᴴNw), where Aᴴw=d, may reduce solve and differentiation costs while preserving physics. |
| `b68b6a18328bb898c01d80eedf2fd2bb544623aa` | matrix-structure-and-factorization | 0 / 1 | unvalidated | Restoring candidate 1's solver should reproduce its measurements: first run about 31.4–31.5 s, warm about 10.9 s, carrier, signal and powers bitwise identical to baseline, noise relative L2 about 2e-8, and the same 3 gradient entries failing strict comparison at relative ≤1.5e-6. That gives a repeat timing sample for the best linear-algebra configuration and leaves the branch head on it. |
| `c33dafe112eab30fda33ff9d794e2ca1a333d158` | first-pass | 1 / 1 | 28.7739s (d0586167, n=1) | Inlining may reduce reverse compilation costs by allowing optimization across the helper boundary. |
| `c4c7260e9db22591182f434eb25e6a566c2096f8` | first-pass | 1 / 1 | 30.7190s (d0586167, n=1) | Block assembly may reduce candidate 5’s forward overhead while retaining its reverse-pass savings. |
| `fbcfaa3a889e5d1e21a6054a50a8bdb05d7d8685` | first-pass | 1 / 1 | 29.9210s (d0586167, n=1) | Reusing the component trace may reduce candidate 3’s increased tracing/lowering time without changing its numerical operations. |

## Failures and unresolved evidence

- `0ed67104f64ad82059b3465d20e56489762b4312` / `99b1182cb5bc4d178563a06507da4010`: official=True, strict=False; Official benchmark passed, but strict baseline array comparison failed.
- `3db9b657f8496d40a9f195fd9864e5e048c7df5b` / `cd271462a63446a997264fb26882b711`: official=True, strict=False; Official benchmark passed, but strict baseline array comparison failed.
- `7f3cf9c316ce87a98afccb402bffc34e4ff71532` / `a7b341dc0cc64363922bcb3023a14537`: official=True, strict=False; Official benchmark passed, but strict baseline array comparison failed.
- `b68b6a18328bb898c01d80eedf2fd2bb544623aa` / `9f2375e5f2d84465bf59b432d82c0749`: official=True, strict=False; Official benchmark passed, but strict baseline array comparison failed.

## Combination review

45 pairs have comparable validated evidence. None is automatically merged.
Inspect JSON for per-phase measurements, repeat counts, conflicting evidence, declared parents and file overlap.

A new agent should identify a direction, exact starting SHA, parent candidates, scope tags, budget and falsifiable hypothesis before editing.
