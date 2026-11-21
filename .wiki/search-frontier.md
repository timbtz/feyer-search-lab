# Shared evidence for guided search

`python -m lab.search_frontier` reads trusted local full-result artifacts and the
team ledger. It does not submit jobs, steer a running agent, merge source, change
budgets, or select a final winner. The guided supervisor reads the resulting
`feyer-search-frontier-v1` snapshot once per new turn and records the exact bytes
and digest actually dispatched. Recovery of a pending turn uses its frozen input.

Independence is one-way: an evidence-only session must never receive this feed.
Guided sessions may learn from its published terminal full results. The collector
accepts independent feedback only when its exact JSON matches a blob in an
already-known origin branch; it does not fetch, contact that session, read its
prompts, or inspect its uncommitted implementation.

## Comparison contract

Each point names an exact SHA/job, instance, cohort, checks, source artifacts,
first-run total, six phase-group objectives and all 14 phase timings. Full official,
strict, source, workload, precision and resource eligibility are recomputed using
the existing evidence normalizer. CPU34 requires an independently approved policy
manifest; candidate-reported CPU or memory does not authorize a policy override.
The separate physical facts and eligibility failures remain visible.

Groups match physical instance, complete evaluator cohort, execution regime and
epoch. Regime classification uses start/end timestamps and recorded transitions,
never import time. Missing timestamps, a transition-crossing interval, a conflicting
ledger label or contradictory copies cannot become comparable evidence. No quiet
epoch is inferred before the first recorded transition. Such full-valid results
remain `unranked`. Caller `--instance` explicitly attests which physical host the
local corpus came from; do not combine artifact corpora from different machines.

`observed_frontier` uses exact job-level dominance across total and all six phase
groups; it is not a noise-qualified improvement. `own_best_observed` selects each
executor's lowest recorded full-valid total **within that group**. Neither a
single observation nor multiple observations automatically confirms a gain.
Quiet serial confirmation and existing team assessment still govern promotion.
Scientific failures are retained and exclude successful samples for the same
candidate/cohort. Conflicting terminal copies conservatively quarantine every
candidate SHA they mention on that physical instance, including separate reruns.

Declared combinations come only from source-backed research records. A phase
tradeoff can motivate a combination experiment; it does not establish compatible
changes, causal attribution, an automatic merge or a local optimum. Review source
compatibility, declare exact parents and evaluate the resulting committed code.

## Snapshot and refresh

The report contains `generated_at` (Unix seconds), `source_provenance`, `groups`,
`unranked`, `failures`, `declared_combinations`, `issues`, `limits`, and
`content_digest`. The digest is SHA256 of JSON excluding `content_digest`, encoded
with Python `json.dumps(sort_keys=True, separators=(',', ':'), allow_nan=False)`
and UTF-8 (default `ensure_ascii=True`). The runtime separately hashes raw bytes.
Provenance binds the input team ledger, policy manifest and evidence corpus with
canonical digests. Local artifact references are not hosted download links or
cryptographic attestations. Each point carries exact artifact digests.

Output is capped at 256 KiB. Frontier and unranked lists are bounded; counts and
omitted counts disclose truncation. Failures also have explicit retained/omitted
counts. Missing context and unavailable results remain gaps, not silent winners.

Example for this deployment, using a coordinator-prepared CPU-string-to-policy
mapping in `.lab/frontier/policies.json`:

```bash
python -m lab.search_frontier \
  --repo '/path/to/feyer-search-lab' \
  --team-state '/path/to/feyer-search-lab/.lab/team/state.json' \
  --instance amd-tim \
  --policies '/path/to/feyer-search-lab/.lab/frontier/policies.json' \
  --policy-source 'https://github.com/OWNER/REPO/blob/EXACT_COMMIT/DEPLOYMENT_RECEIPT.json' \
  --output '/path/to/feyer-search-lab/.lab/frontier/current.json'
```

Every successful refresh atomically publishes an immutable
`artifacts/<content_digest>.json` and atomically replaces `current.json`. Initial
snapshots can be committed with their code release for review. Later dispatches
bind their own exact content-addressed artifacts in runtime receipts.
Optional `--watch-seconds 20 --until-unix FIXED_DEADLINE` refreshes only until the
specified deadline. It performs no network calls or evaluations. In watch mode,
filesystem errors are logged and retried at the next interval until the original
deadline. Failed writes leave the last complete snapshot and its timestamp intact;
partial temporary files are cleaned up. If the log filesystem is also full, the
bounded retry continues even when the error cannot be written. Propagated semantic
evidence, digest or size errors still stop the producer; one-shot commands propagate
errors. Per-artifact collection issues remain explicitly reported in the feed.
The consumer must enforce its freshness limit and report an unavailable/stale feed
rather than imply new data. Recovery always collects a new snapshot; it never
changes the timestamp of an old snapshot to make it look fresh.
The broker owns starting/stopping this bounded local refresher with the new guided
session window. It does not extend old sessions or numerical campaigns.
