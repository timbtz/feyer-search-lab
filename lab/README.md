# Challenge lab

The lab operates the experiment loop: coordinate a hypothesis, version a candidate, evaluate its exact SHA, retain evidence, and feed the result into the next decision.

[Combined project overview](../README.md) · [Architecture and code map](../docs/ARCHITECTURE.md) · [Operating guides](../.wiki/README.md) · [Frontend repository](https://github.com/timbtz/feyer-search-frontend)

## Start with the observatory

From the repository root:

```bash
python3 -m lab.live_dashboard --repo . --port 8765
```

Open <http://localhost:8765/#story> for the challenge and solution, or use the graph, submission dossier and run archive to inspect available records. This reads local state; a new checkout has no private `.lab` history. Remote synchronization is opt-in and needs existing access.

## Operate experiments

Use the [runbook](../.wiki/runbook.md) and [portable evaluator setup](../.wiki/portable-amd.md). Read [AGENTS.md](../AGENTS.md) before agent work. The checked-in client help is the command reference:

```bash
python3 -m lab.client --help
python3 -m lab.agent_loop --help
```

A managed agent edits permitted source and returns structured readiness; its supervisor owns commits and submissions. The evaluator owns execution. Opening the frontend never starts either.

## Frontend boundary

[`dashboard/`](dashboard/) contains the embedded frontend. The standalone repository owns its own server and saved snapshot. Both share the project story and original slide assets; changes are synchronized deliberately, preserving independent graph work. See the [dashboard guide](../.wiki/live-dashboard.md) for development and design-system details.
