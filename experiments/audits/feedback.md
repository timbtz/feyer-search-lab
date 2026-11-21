# Feedback, queue and reporting audit

Audit date: 2026-11-21. Scope: read-only examination of supervisor/queue operation, plus root-authorized fixes in the client and phase reporting code. No simulator edits, benchmark launches or queue mutations were performed.

## What is working

- Queue claims and ownership transitions are transactional (`BEGIN IMMEDIATE`); candidates are pinned by full commit SHA under per-job refs. Repeated evaluations remain distinct queue jobs. Worker-level serial locking is covered by the evaluator audit.
- The supervisor persists candidate SHA, submission state, job IDs, conversation ID and feedback. It resumes the same conversation and recovers already-submitted jobs before asking the model for new code. It never silently retries an ambiguous submission.
- Every completed full run supplies the complete official report, strict comparison, log tails and exact SHA to the resumed agent. The reports include all 14 first-run phases, warm phase medians and resource data where available.
- The agent does not receive a new coding turn immediately after a promising screen. The supervisor waits for full validation and then resumes it with both results. This is a deliberate serial feedback design, not an omission.
- Candidate 2 is an official pass with an internal strict-gradient failure. The raw record already preserved this distinction, but earlier summary displays compressed it to “not validated.” It was excluded from the conservative frontier, as intended.

## Confirmed reporting defects fixed

1. **Manual submissions were invisible to the collector.** Previously only `experiments/runs/*/candidate-*.json` in local worktrees was read. Those records are created by the supervisor; `lab.client submit/wait` alone does not create them. Added `sync_ledger` in `lab/client.py` and `phase_report --sync`: read terminal queue jobs and store immutable envelopes by job ID under `.lab/phase-ledger`. The collector now uses this shared ledger alongside supervised records. Root should restart the watcher with `--sync`.
2. **Evaluator/timing identity was missing from comparability.** Prior `signature` compared CPU/model/affinity/dependencies/workload inputs, but not the executed benchmark hash, report schema or timing scope. Added these comparisons and checked execution hash against the report hash when both are present. Original screen-v1 and the audited log-only revision have explicit reviewed mappings to the canonical full first-run timing schema. Unknown changed evaluators are not silently comparable.
3. **Repeat runs could collapse graph nodes.** Collection identified rows by SHA/job, but Mermaid node IDs used SHA alone. Two full reruns of one SHA would therefore overwrite graph labels. Nodes now use job ID. Each full run remains a separate row with its own validity, timing and resource evidence; screen jobs are associated by exact SHA/agent/branch/direction without claiming a one-to-one pairing.
4. **Ancestry used evaluation order rather than the nearest code ancestor.** Evaluating an old revision after a descendant could choose a farther ancestor. The graph now chooses the nearest recorded Git ancestor, preserving run identity separately. It still labels ancestry as non-causal evidence.
5. **Official and internal validity were visually conflated.** Added separate `official_check`, `strict_check` and `execution_status` fields and columns. Candidate 2 now displays `passed / failed`. Conservative frontier eligibility remains unchanged. Failed execution with no validation evidence remains unknown rather than being fabricated as a numerical rejection.
6. **Historical resource absence could be misread.** Added explicit resource evidence: budget, sampled process-group enforcement, kernel-cap flag, GNU-time peak, shared-container limit and comparison-stage memory monitoring. Old records remain `unknown_historical`; they are not silently assigned a 32 GB cap. Resource uncertainty is displayed separately from valid same-environment timing comparisons.

## Design choices and remaining limitations

### Exact Pareto membership is not a useful sole search score

At audit start, seven of eight fully validated candidates were on the exact six-axis frontier, including the slower first candidate. Sub-millisecond sensitivity/transfer variation prevents strict dominance. This is mathematically correct and already disclosed; it is not a statistical demonstration of distinct useful tradeoffs.

Keep complete first-run total as the primary ranking, show exact frontier for transparency, and use the separate noise-band phase classification to discuss practical improvements. The heuristic is max(20 ms, 3% of each baseline phase median, baseline phase range), not a confidence interval. Do not automatically claim a formal epsilon-Pareto frontier without defining transitive bins or a repeated-measurement uncertainty model.

### Screening promotion optimizes total score, not broad exploration

`agent_loop.py` only promotes candidate 1 automatically or later successful screens at <=102% of the configured baseline. It can skip a slower-total candidate that improves memory or one phase substantially. This is a deliberate economy policy, but the new multiobjective exploration use case may warrant a manual force-full option or a small exploration allowance. Do not remove the speed gate blindly: that would increase full-run costs and give no correctness benefit to clearly unpromising changes. Record the decision and allow explicit exceptions.

### Submission recovery is safe but brittle

The durable marker precedes `Client.submit`, but the remote enqueue has no idempotency key. Recovery searches for matching SHA/profile/agent/direction after a local timestamp minus one second. Local/server clock skew or a crash before enqueue can leave zero matches and require operator intervention. The current fail-closed behavior is safer than blind duplicate submissions. A future robust fix is an explicit request ID stored before upload, a unique server-side enqueue key and recovery by that key, rather than timestamp matching. This needs coordinated client/remote/queue migration and was left out of the reporting patch.

### The reporting watcher does not drive agent decisions

The agent already receives raw phase measurements. The Pareto/phase classifications are currently an external report, not an automatic multiobjective search controller or an appended supervisor prompt. Do not describe this as a Pareto-guided autonomous algorithm. Attaching concise classifications in future feedback is straightforward, but selection policy should be agreed first.

### Scope of comparable hardware remains incomplete

Environment signature still cannot prove the same physical instance from CPU model alone; historical reports do not contain an instance identity or 32 GB enforcement evidence. New worker provenance helps. A future cross-machine queue needs an explicit machine/instance identity and resource policy in every job. Current same-instance historical runs remain useful, with their limitations stated.

### Sync scale and snapshot semantics

The queue API caps listing at 10,000 jobs. Sync reports `truncated: true` at that ceiling; pagination is not implemented. Local ledger and dashboard can refresh; published GitHub reports remain explicit snapshots. Missing local Git objects prevent inferred ancestry but do not prevent displaying remote job measurements. Independent reruns are retained rather than averaged; a separate confirmation analysis should summarize repeated first-run scores without mixing screening and full profiles.

## Verification

- 14 phase-report unit tests passed, including manual-run ingestion, two full reruns of one SHA remaining distinct, official-pass/strict-failure separation, evaluator mismatch, reviewed screen equivalence, historical resource unknowns and monitored-versus-kernel memory distinction.
- 2 existing client tests passed.
- Read-only live sync retrieved all 22 jobs visible at that point, with `truncated: false`, and rendered 11 evaluation rows including calibration jobs that were absent from the earlier worktree-only collector.
- The generated viewer passed a Node DOM smoke check: table rows, chart rendering, changing axes and selecting a candidate.
- `git diff --check` passed for the working changes. No generated `experiments/analysis` snapshot was edited by this subagent; root owns regeneration/publication.
