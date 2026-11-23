# Feyer lab — operating guides

[Combined project overview](../README.md) · [System architecture](../docs/ARCHITECTURE.md) · [Results & evidence](../docs/RESULTS.md) · [Final presentation](../presentation/faster-answers.pdf) · [Frontend](https://github.com/timbtz/feyer-search-frontend)

The lab separates optimization from evaluation. Agents explore owned branches; a supervisor commits and submits exact candidates; the evaluator produces recorded evidence. Measured feedback determines what happens next. The frontend observes this process.

This directory contains operating guides and historical records from the hackathon. Launch notes, host layouts, budgets and capacity figures describe their recorded sessions, not current service status. Use the dashboard’s source timestamps and the CLI for current observations. A screen result remains provisional; promotion requires the applicable full checks.

## Start and operate

| Guide | Use it to |
| --- | --- |
| [Runbook](runbook.md) | Access, evaluate and recover work using the supported client |
| [Portable AMD setup](portable-amd.md) | Prepare a fixed environment, calibrated baseline and serial worker |
| [Team search](team-search.md) | Coordinate tasks, branches, evidence and combinations across participants |
| [Experiment rules](experiment-rules.md) | Understand correctness, permitted changes and promotion requirements |
| [Detailed architecture](architecture.md) | Follow candidate identity, commit relay, queue lifecycle and feedback |
| [Live dashboard](live-dashboard.md) | View local or synchronized records without launching experiments |
| [Machine and baseline](baseline.md) | Interpret the initial measured reference |
| [Storage and retention](storage.md) | Preserve evidence and distinguish recreatable data |

## Follow the evidence

- [Profiling feedback](profiling.md): measured first-run phase attribution.
- [Research lineage](research-lineage.md): scientific parents and separately recorded feedback artifacts.
- [Phase exploration](phase-exploration.md): timing comparisons and observed tradeoffs.
- [Search frontier](search-frontier.md): bounded Pareto evidence for guided sessions.
- [System audit](system-audit.md): correctness decisions and unresolved questions at the time of review.
- [Compiler diagnostics](compiler-diagnostics.md): separately admitted diagnostic work.

## Search controllers

- [DAG controller and evidence ledger](dag-search.md): frozen rounds, ownership and submissions.
- [Deterministic search](discrete-search.md): enumeration and discrete local search.
- [SMAC3 integration](smac-search.md): model-guided search over registered implementation choices.
- [Topology tuning](topology-tuning.md): refine an admitted implementation space.
- [Evolution search design](evolution-search-design.md): design rationale and early measured lineage.
- [Optimization hypotheses](hypotheses.md): proposed directions, not promised gains.

The final six-setting SuperLU sweep used **enumeration**, and found no admissible improvement under its extra seed-relative checks. See [results and exact revisions](../docs/RESULTS.md). Earlier search designs and campaigns remain useful history.

## Session and deployment history

[Initial agent brief](../experiments/initial-agent.md) · [Second-agent workflow](second-agent.md) · [Capacity](capacity.md) · [Evaluator lanes](evaluator-lanes.md) · [Queue initialization](queue-initialization.md) · [Token Factory](token-factory.md) · [Optional Qwen reviews](qwen-worker.md)

A direction may outlive one conversation. A session may produce many candidate commits. A candidate may have many runs. Preserve those identities, failed trials, fixed deadlines and handoff notes so later work can resume without inventing history.
