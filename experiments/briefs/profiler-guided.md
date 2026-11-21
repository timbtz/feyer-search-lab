# Profiler-guided implementation research

This brief applies to a new bounded Claude Opus 5.5 session supervised by the lab. Use the exact model identifier `claude-opus-5-5`, exact seed SHA, owned branch/worktree, session identifier and deadline supplied by the launch record and supervisor. Fable 5.2 was checked first but the account requires usage credits; the user explicitly selected Opus 5.5 for this run. Available models are documented in the [official model overview](https://platform.claude.com/docs/en/models/overview). Do not infer a seed from a historical fastest row or restart an older session's budget.

Your task is to improve the complete first-run time of the unchanged optical workload using measured phase evidence. Read `AGENTS.md`, `.wiki/README.md`, the supplied launch record and retained parent notes before proposing a change. The supervisor supplies the profiling policy from its committed runtime; an older seed checkout need not contain the newer infrastructure documentation. The supervisor supplies attribution and evaluation feedback; retain their exact source identities in your notes.

## One research cycle

1. Identify an expensive measured phase on the supplied seed or current retained candidate. Cite its exact SHA, run identifier, profile, seconds and share of first-run total. Distinguish an official/full observation from a provisional screen and distinguish first-run from warm time. If evidence is absent, say what is unknown; do not invent operator attribution.
2. Explain one plausible implementation mechanism that affects that phase. State the expected direction of change, possible costs elsewhere and a predicted saving ceiling. A phase's entire measured duration is an upper bound on savings from eliminating that phase alone, not a promise of achievable improvement.
3. Make one focused, attributable simulator change within the permitted paths. Preserve all 101 frequencies, all 193 physical variables and their values, the complete optical setup, double precision, physical outputs, full gradient and the official benchmark's three JIT stages. Do not enable persistent compilation caching, precompute answers or change shared dependencies or evaluator configuration.
4. Return the structured readiness response. The supervisor checks paths, commits the exact candidate, submits screen/full jobs to the serial evaluator and resumes this conversation. Do not independently commit, call GitHub/SSH, launch benchmarks or profiling jobs, create services, alter affinity, or run a competing test workload. Do not add independent test or benchmark infrastructure in this research session.
5. Inspect the resulting complete first-run time, all phase deltas, warm evidence, memory evidence, official outcome and strict saved-array comparisons. For numerical changes, inspect every output check and the full gradient's absolute, relative and normalized errors, failing counts and available mismatch details. A finite-difference spot check alone is insufficient. A strict pass near its error boundary warrants explicit discussion and a conservative next step.
6. Keep or reject the change based on measured evidence against its exact parent and retained best eligible candidate under matching conditions. A screen result is provisional; a shared best requires unchanged official full evaluation. Preserve failures and regressions in history. Never substitute a weaker reference, baseline score, changed workload or expected speedup for measured improvement.
7. Update the ranked bottleneck and choose the next focused hypothesis. A reduced compile phase may make execution the next priority. Do not repeatedly pursue an old bottleneck after the evidence changes.

The objective is complete first-run time. A local phase improvement that increases the total is a tradeoff to record, not a primary-objective win. A single low full result is an observation; use repeat evidence and the lab's noise policy before describing a robust gain.

## Search algorithms and attribution limits

The initial profiler ranks the existing 14 synchronized timing phases. It does not establish internal operator runtimes. Source inspection can suggest redundant factorization, memory traffic, dispatch or assembly as hypotheses, but cannot certify their cost. Request a coordinator-owned diagnostic when deeper evidence is necessary; do not launch one yourself or change JIT boundaries merely to obtain attractive section timings.

Do not tune the physical design variables. If a measured bottleneck suggests a small discrete set of implementation choices, describe the legal options and constraints in your handoff. Enumeration or SMAC requires a new frozen reviewed search round and explicit ownership; this session does not silently expand into one.

## Notes and response contract

Record the launch record's seed, branch, worktree, session identifier and deadline. For every attempt, retain the hypothesis, measured target and run, candidate SHA when supplied by the supervisor, screen/full identifiers, numerical errors, phase and total timings, failures, keep/reject decision and precise next action. Note import time, compilation, warm runtime, complete first run and total job duration separately.

Return exactly the supervisor's required fields:

```json
{
  "summary": "The focused change or handoff",
  "hypothesis": "Measured phase and source run; mechanism; predicted effect and ceiling",
  "ready_for_evaluation": true,
  "stop": false,
  "notes": "Evidence, numerical risks, retained best, decision and next action"
}
```

Set readiness only when the permitted candidate edits are complete. Both readiness and stop may be true for a final candidate to evaluate before finishing. If no candidate is ready, use readiness false and explain the outstanding issue. At the recorded deadline, finish safe bookkeeping and hand off the exact session identifier, best eligible revision, unfinished hypotheses and next action. Do not extend the deadline, reset the budget, spawn agents or increase evaluator concurrency yourself.
