# Overnight actual-work audit

Snapshot: 2026-11-22T08:35:29.735747+00:00. Fixed deadline: 2026-11-22 09:27:44 UTC.

Attribution comes from exact recorded model-turn parent SHA and hypothesis matched to the submitted request. It does not infer ownership from branch names or Git authors. Counts exclude in-progress turns. Shared code may originate in a different session.

| Lane | Provider | Completed model turns | Evaluated candidates | Official passes | Numerical admission | Promotions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| overnight-numerics-v1 | claude | 15 | 12 | 12 | 12 | 2 |
| overnight-numerics-v1 | codex | 70 | 44 | 44 | 41 | 0 |
| overnight-overhead-v1 | claude | 12 | 9 | 9 | 9 | 1 |
| overnight-overhead-v1 | codex | 84 | 46 | 46 | 46 | 0 |

Across the two lanes: **111 evaluated candidates**, **111 official dual passes**, **3 promotions**. All promotions were from Claude turns. Official passes alone did not imply generalization admission, source approval or timing promotion. Current controller statuses: overnight-numerics-v1=stopped (codex), overnight-overhead-v1=stopped (codex). These are timestamped status observations, not independent process probes.

## Current best and promising provisional work

Current admitted best is `ee4fea28c04d482566be16e916b609d7c6a99e5e` from Claude numerics turn 8: large **0.801578s**, aLIGO **0.548555s**. Its inherited numerical caveats remain unchanged.

| Candidate | Recorded provider/lane | Large median / range (s) | aLIGO median (s) | Status |
| --- | --- | --- | ---: | --- |
| `ee4fea2` | claude / overnight-numerics-v1 | 0.801578 / 0.794425–0.822484 | 0.548555 | Admitted best |
| `1ea70bf` | claude / overnight-overhead-v1 | 0.779121 / 0.773867–0.806567 | 0.517428 | requires_source_review; large_first_run_ranges_overlap_requires_paired_evidence |
| `f856aaf` | codex / overnight-overhead-v1 | 0.773872 / 0.770791–0.807729 | 0.523577 | requires_source_review; large_first_run_ranges_overlap_requires_paired_evidence |
| `5dde094` | codex / overnight-numerics-v1 | 0.786068 / 0.780172–0.811378 | 0.542608 | requires_source_review; large_first_run_ranges_overlap_requires_paired_evidence |
| `10e63de` | codex / overnight-numerics-v1 | 0.781442 / 0.774789–0.868603 | 0.542759 | grid_unstable_timing; requires_source_review; large_first_run_ranges_overlap_requires_paired_evidence |
| `a1e10d9` | codex / overnight-numerics-v1 | 0.772394 / 0.769205–0.808256 | 0.542067 | runner_not_promotion_ready; incomplete_generalization; unresolved_new_failures; requires_source_review; large_first_run_ranges_overlap_requires_paired_evidence |
| `1acb98c` | codex / overnight-overhead-v1 | 0.779679 / 0.776156–0.816582 | 0.526419 | requires_source_review; large_first_run_ranges_overlap_requires_paired_evidence |

Claude numerics removed reverse solve work, including a guarded cotangent-collinearity path. Compared with the seed, the admitted best grid gradient phase fell from approximately 190ms to 85ms and total compilation from approximately 249ms to 187ms. These describe recorded medians, not an additive attribution proof across combined changes.

Claude overhead candidate `1ea70bf` removes callback-boundary operations and incorporates the shared numerical improvements. Its large compilation phase falls further, and aLIGO transfer is faster; it remains provisional because full-run ranges overlap and source review was skipped by the timing preflight. Three different commits have exactly the same simulator tree (`1ea70bf`, `39b7575`, `c723457`) but large medians vary about 0.779–0.817s. Those are code-equivalent observations, not exact-SHA repeats.

Codex numerical candidate `5dde094` changes residual-product coefficient ordering/reuse. Its forward samples are approximately 171.3,169.8,170.0ms versus the admitted best 177.4,181.2,182.9ms. This is a promising phase signature with passing numerical admission, but still unreviewed/provisional for full-run promotion. `10e63de` adds buffer reuse and is faster in the same phase, but its grid range exceeds 10%. The fastest raw `a1e10d9` changes the CSR multiplication path and fails extra seed/generalization checks; do not select it based on 0.772s.

Codex overhead `f856aaf` has the fastest numerically admissible Codex total in this snapshot. Its immediate hypothesis is a structural-plan key correctness fix, not a claimed speed optimization; it inherits earlier callback-boundary work. `1acb98c` makes unused-port instruction ordering deterministic, but its three fresh samples still span about 40ms. This does not demonstrate reduced whole-run variance.

## Variance and next measurement

In **102/109 numerically admissible records** (including seed calibration), the first grid process is the slowest. Its median import penalty versus later repeats is **28.075ms**; forward adds approximately 2.980ms. This systematic run-order effect can defeat a millisecond nonoverlap gate even when a particular phase improves.

Do not discard first samples, preload imports outside the timer, or label warm results as complete first-run results. Investigate filesystem/import caching and host load as hypotheses; use controlled interleaved A/B runs of exact revisions, preserving all samples and the same policy. More overlapping repetitions alone do not satisfy the present conservative nonoverlap rule. Any different confidence protocol needs an explicit versioned decision.

No launches, evaluations, active-state changes or policy changes were performed by this audit. Full candidate attribution, hypotheses, numerical failures, phase samples and source-equivalence groups are in [actual-work-0831.json](actual-work-0831.json).
