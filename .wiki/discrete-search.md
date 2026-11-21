# Deterministic implementation optimization

The existing campaign runner now supports `--selector enumeration` and
`--selector local-search`. Both use the same source renderer, durable queue IDs,
screen/full pipeline, strict numerical comparison, resource checks and evidence
ledger as the Qwen recipe pilot. They require no API credentials or model calls.
The selector and a zero model-call budget are frozen at campaign initialization.
The CLI also supports SMAC3 and an automatic choice at initialization; see
[SMAC3 integration](smac-search.md) for the selection policy and separate dependencies.

The current space has 15 legal configurations of component checkpointing,
`prevent_cse` and mapping batch size. This is optimization of implementation
choices for complete first-run time. It does not optimize the 193 physical
parameters, change their gradients, or move the official benchmark to the GPU.

`enumeration` visits each unseen legal configuration in a stable order.
`local-search` searches categorical Hamming neighborhoods of the incumbent:
one-choice moves first, then two-choice and larger moves after nearer choices
are exhausted. A significant improvement recenters the search. Content hashes
exclude all previously proposed configurations, including numerical failures.
The finite-space lane does not stop after three unsuccessful moves; its frozen
stall limit covers the entire registered space. Time and evaluation budgets
still apply. No new operators or rounds are created automatically.

The incumbent changes only when a full eligible result improves total time by
more than the maximum of 1%, 0.02 seconds, and the observed timing ranges of both
candidates. This is a conservative heuristic, not a confidence interval or proof
of a speedup. Screens cannot select an incumbent. New finalists still need
alternating repeated full confirmation. Exhaustion means coverage of these 15
configurations, not global optimality among simulator implementations.

Initialize from a clean committed controller checkout, using three distinct
matching full seed8 reports. For example (replace report paths):

```bash
python3 -m lab.evolution_run init \
  --state '/absolute/path/to/.lab/campaigns/discrete-local-v1' \
  --name discrete-local-v1 --selector local-search \
  --seed-report seed-full-1.json --seed-report seed-full-2.json \
  --seed-report seed-full-3.json \
  --minutes 60 --max-evaluations 28 --max-model-calls 0 --publish

python3 -m lab.evolution_run run \
  --state '/absolute/path/to/.lab/campaigns/discrete-local-v1'
```

There are at most 14 new configurations after the seed; 28 evaluations allow a
screen/full pair for each. Full validation is dispatched only after a passing
screen. Actual run count can be lower because of failures, prior imports or the
deadline. Re-running `run` recovers pending work with its original request IDs;
it does not reset the deadline. `--once` drains one candidate. The existing
`STOP` file mechanism stops at an evaluation boundary. The status and export
subcommands continue to work.

Use repeatable `--prior-full /path/to/job.json` at initialization to reuse a
completed experiment from another campaign. The adapter requires a full
scientific verdict, matching cohort, exact candidate SHA and a complete source
hash map matching one registered configuration; every other simulator file
must match the seed. Valid and invalid results are retained. Existing content
at a different SHA is never relabeled as evidence for a new commit. Imported
jobs do not consume fresh evaluation budget. Coordinate with other campaign
owners before launch; deduplication is campaign-local, not a global queue lock.

Agents and the Hetzner proposer broker remain producers of new reviewed
transformations. Admitting those transformations requires a new versioned
materializer and campaign/round policy. The search controller runs locally and
submits expensive numerical work to the existing serial AMD CPU evaluator.
No packages are added to `/workspace/venv-feyer`.
