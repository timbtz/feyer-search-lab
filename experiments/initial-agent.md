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

Stop after four distinct candidate revisions or one hour, whichever comes first. Do not spawn additional agents. Finish with a concise report naming the best validated revision, measured improvement or lack of improvement, numerical evidence, failed approaches and next steps. Preserve the worktree, branch, commits, notes and session so the investigation can be resumed.
