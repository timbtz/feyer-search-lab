# Feyer experiment lab

The lab separates optimization work from evaluation. Agents explore a direction in their own branch and working directory. A supervisor commits and submits their changes, then returns the AMD evaluator's results so they can decide what to try next. A screening result is provisional; a validated result passes the unchanged official benchmark.

The team repository is [timkireply/feyer-search-lab](https://github.com/timkireply/feyer-search-lab). The challenge source and README remain at the repository root.

## Start here

- [Architecture](architecture.md) explains branches, candidates, agent sessions and the worker queue.
- [Runbook](runbook.md) covers access, evaluation and recovery.
- [Experiment rules](experiment-rules.md) defines correctness and promotion requirements.
- [Optimization hypotheses](hypotheses.md) records ideas to investigate without assuming they will work.
- [Machine and baseline](baseline.md) records the measured starting point.
- [Storage and retention](storage.md) explains what to retain and what can be recreated.
- [Initial agent brief](../experiments/initial-agent.md) defines the first bounded exploration session.

## Status

The AMD instance, SSH access, VS Code connection, isolated Python environment and three official baseline runs have been verified. The experiment queue, screening tool and first agent session are being integrated. Their operational status must be established by an end-to-end test before treating queued results as available.

## Working model

One direction can outlive an agent session. One agent can produce several candidate commits. One candidate can have several evaluation runs. Keep those identities separate so a replacement agent can resume from the written findings and every timing remains attributable to exact code.

The initial evaluator policy is one benchmark at a time. The instance's CPU quota permits more concurrent work, but memory use and shared-machine timing noise must be measured before increasing concurrency.
