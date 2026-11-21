# Feyer experiment lab

The lab separates optimization work from evaluation. Agents explore a direction in their own branch and working directory. A supervisor commits and submits their changes, then returns the AMD evaluator's results so they can decide what to try next. A screening result is provisional; a validated result passes the unchanged official benchmark.

The team repository is [timbtz/feyer-search-lab](https://github.com/timbtz/feyer-search-lab). The challenge source and README remain at the repository root.

## Start here

- [Architecture](architecture.md) explains branches, candidates, agent sessions and the worker queue.
- [Runbook](runbook.md) covers access, evaluation and recovery.
- [Experiment rules](experiment-rules.md) defines correctness and promotion requirements.
- [Optimization hypotheses](hypotheses.md) records ideas to investigate without assuming they will work.
- [Machine and baseline](baseline.md) records the measured starting point.
- [Storage and retention](storage.md) explains what to retain and what can be recreated.
- [Token Factory](token-factory.md) covers the Qwen API client, credentials and measured request limits.
- [Phase exploration](phase-exploration.md) explains candidate comparisons, the interactive viewer and observed Pareto tradeoffs.
- [A second interactive agent](second-agent.md) explains isolated worktrees and conversation forks.
- [System audit](system-audit.md) records correctness/resource decisions, fixes and unresolved organizer questions.
- [Evolution search design](evolution-search-design.md) maps EvoHarness policies to the candidate DAG, Qwen mutations, larger-agent roles and validated timing evidence.
- [Deterministic search](discrete-search.md) runs enumeration or discrete local search through the existing AMD evaluator without model calls.
- [DAG controller and evidence ledger](dag-search.md) documents the implemented frozen rounds, write ownership, worker artifacts and three-submission rule.
- [Initial agent brief](../experiments/initial-agent.md) defines the first bounded exploration session.

## Status

The AMD instance, SSH access, VS Code connection, isolated Python environment and three official baseline runs have been verified. The serial experiment queue is deployed. Unchanged code passed end-to-end screening and full validation, including strict baseline array comparison. Screening took 37.5 seconds wall time; full validation took 126.1 seconds. The initial supervised Codex session has launched in the separate `codex-seed` worktree on `explore/seed-agent`. Its live status is recorded under `.lab/sessions/seed-agent/status.json`; the launch record is [seed-agent](../experiments/agents/seed-agent.json). It inherits the existing user configuration, `gpt-6-astra` with high reasoning effort. No optimization result is implied by launch status.

## Working model

The first Codex candidate completed the entire feedback cycle: committed on `explore/seed-agent`, screened, fully validated, published its results, and resumed the same Codex conversation for candidate two. Its lazy visualization import preserved all saved arrays exactly. Complete first-run time was 37.00 seconds versus the lab calibration's 36.33 seconds, so this single measurement does not demonstrate a speed gain. See the [candidate report](https://github.com/timbtz/feyer-search-lab/blob/explore/seed-agent/experiments/runs/seed-agent/candidate-01.json).

One direction can outlive an agent session. One agent can produce several candidate commits. One candidate can have several evaluation runs. Keep those identities separate so a replacement agent can resume from the written findings and every timing remains attributable to exact code.

The initial evaluator policy is one benchmark at a time. The instance's CPU quota permits more concurrent work, but memory use and shared-machine timing noise must be measured before increasing concurrency.
