# Overnight supervisor review — 2026-11-22 08:36 UTC

Read-only audit. No controller, code, queue, job or runtime was changed. Original deadline: 09:27:44 UTC.

## Main conclusion

The loop produced real improvements and many distinct experiments, but is now poorly equipped to resolve its remaining uncertainty. Shared-best delivery works. The bottleneck is the missing path from an agent’s request for paired confirmation or diagnostics to actual evaluator work. The conservative range rule and cost-saving review gate reinforce that dead end.

| Lane | Completed model turns | No-candidate turns | Evaluations/public passes | Distinct simulator trees | Promotions | Current nonimproving |
|---|---:|---:|---:|---:|---:|---:|
| overnight-numerics-v1 | 84 | 27 | 55/55 | 53 | 2 | 47 |
| overnight-overhead-v1 | 94 | 38 | 55/55 | 52 | 1 | 52 |

Counts are a snapshot near 08:33 UTC; active sessions can advance. Three numerics trials had additional generalization failures despite public passes. Strict pristine-reference caveats remain, so these counts do not mean universal feasibility.

## What is and is not stuck

- Shared-best snapshots in both pending inputs select exact `ee4fea28c04d482566be16e916b609d7c6a99e5e` and verify its reviewed artifact. Earlier overhead `1ea70bf` explicitly combines that incumbent with callback-boundary simplifications. This is not a broken peer-feed problem.
- There are 105 distinct simulator trees among 110 evaluations. Five repetitions are same-tree reconstructions under different commits; do not relabel these as exact-SHA repeats.
- No-candidate responses are mostly evidence recording/handoffs between experiments. The maximum consecutive streak is two for numerics and one for overhead. The failure is repeatedly proceeding past an unresolved handoff, not a long empty-response loop.
- Numerics requested paired evidence in 27 completed turns and profiling in 33 (keyword counts); overhead requests also recur explicitly, especially turns70–75. These are unresolved operational requests, not permission to fabricate success.
- `ready_for_evaluation` only creates a job if simulator files are dirty. No response field dispatches an unchanged-SHA repeat, a matched parent run, or a focused diagnostic. After three nonpromotions the prompt repeats the same general advice; it does not change experiment allocation.
- Current source-review preflight skips every overlap case. Thus a plausibly faster candidate gets neither paired confirmation nor source review, while another source edit is encouraged.

## Measured order effect

Among 110 three-repetition large-case evaluations, repetition1 was slowest in103. Its median excess over the median of repetitions2–3 was **32.79ms total**, including **27.98ms imports**. This is an observed order/phase effect; its exact system cause is not established. Do not delete these samples, prewarm the fixture, or move imports outside the timer.

The current rule requires candidate maximum below the historical incumbent minimum. Incumbent grid range is0.794425–0.822484s; its median is0.801578s. This rule can block gains around20–28ms because it compares the slower-position candidate sample with the faster-position historical reference.105/110 evaluations have the overlap rejection reason.

## Candidate-specific confirmation targets

| Exact candidate | Grid median [min,max] s | aLIGO median [min,max] s | Current evidence |
|---|---|---|---|
| `ee4fea28c04d482566be16e916b609d7c6a99e5e` | 0.801578 [0.794425, 0.822484] | 0.548555 [0.544719, 0.551624] | Both public passes;14 seed cases; reviewed incumbent |
| `1ea70bfbde9bcf42fce836846a4e1e92aee36a3b` | 0.779121 [0.773867, 0.806567] | 0.517428 [0.517229, 0.521618] | Both public passes;14 seed cases; source review still missing |
| `f856aafd5552f433aa08bd3dc923acb31d5adf4e` | 0.773872 [0.770791, 0.807729] | 0.523577 [0.520752, 0.528641] | Both public passes;14 seed cases; source review still missing |
| `23a9895cba361144a1d88b91b1454d634659250c` | 0.775672 [0.773959, 0.805157] | 0.522109 [0.521057, 0.522640] | Both public passes;14 seed cases; source review still missing |

`f856aafd` is3.46% lower in historical grid median and4.55% lower in aLIGO median than the incumbent, but this is not a paired confirmation. Its official saved-array hashes match the incumbent on all six runs. Its own immediate change versus `23a9895` only adds group lengths to the SystemPlan digest: a correctness safeguard, not an explanation for the whole speed difference.

The earlier boundary simplification `1ea70bf` removes about25.55ms from the sum of median forward/gradient trace+compile phases on grid. Two later byte-identical source reconstructions (`39b7575`, `c723457`) retain this phase signature but show noisy totals. These cannot establish a final timing verdict by selectively pooling favourable runs.

Later source `1acb98c3d02274b9ed241bba558bedfe50f9f6de` also contains selector-offset and deterministic-order repairs (grid0.779679s, aLIGO0.526419s), and may be preferable as the correctness finalist if independent review validates them. The prepared focused NumPy/JAX tests are still described as unexecuted by the agent. Do not pick older source solely because one unpaired median is lower.

## Bounded repair recommendation

1. At a safe controller boundary, allocate20–25minutes to exact-source confirmation rather than another stream of speculative edits. This audit has not paused anything.
2. Pre-register A=`ee4fea2`, B=`f856aafd`; optionally compare the latest corrected `1acb98c3` if source review supports it. Run serial balanced AB/BA blocks, fresh processes, both official setups, same CPU/thread settings. Keep all samples and the complete first-run timer. At leastfive independent blocks per selected comparison are preferable; stay within09:27:44.
3. Obtain independent fullseed-to-finalist source review and execute the prepared focused structural/gradient diagnostics separately from ranked timings. Preserve every inherited discrepancy and new failure.
4. Keep the incumbent unless correctness and predeclared matched evidence justify replacement. A paired verdict requires an explicit versioned decision; do not silently rewrite the v2 rejection or lower numerical tolerances.
5. After the campaign, add an explicit bounded `confirm`/`diagnose` experiment request to the supervisor schema. A repeated handoff should trigger this capability or an honest blocked status, not merely another nearly identical instruction to edit code.

## Evidence

- `supervisor-review.json`: structured conclusions, exact IDs, raw source paths, phase comparisons and bounded plan.
- `supervisor-review-data.json`:110 evaluation summaries, unique source-tree IDs, hypotheses and rejection reasons.
- `supervisor-review-phase-diagnostics.json`: all-sample order effect and detailed finalist phase/array/generalization evidence.
- `supervisor-review-search-dynamics.json`: ready-false streaks and unpaired source trajectory summaries.
- Live runtime630ea27: `lab/overnight_search.py:381–388,617–633,671–673`; `lab/overnight_client.py:261–268,304–319`; `lab/overnight_publish.py:159–170`.

No new scientific validation was run in this audit. Synthetic-check and source-correctness assertions quoted from agents remain assertions until the listed diagnostics/reviews execute.

## Additional read-only bytecode observation

The runner creates one fresh checkout, then reuses it for grid1, aLIGO1, grid2, aLIGO2, grid3, aLIGO3. It starts fresh Python processes but does not explicitly disable package bytecode writes. Read-only inspection of completed f856 request `075955848ff84927b548f902cbdea660` found eight generated package `.pyc` files, all timestamped during the initial import window (1795335130.052–1795335130.079, a27ms span). This supports an additional mechanism: grid1 pays source-bytecode compilation while later processes can reuse the generated files. It does not prove the entire28ms import difference is bytecode cost. Preserve this distinction in confirmation: fresh process is not the same as fresh checkout. Use balanced same-position comparisons; do not strip imports or selectively discard grid1. Metadata is saved in `supervisor-review-bytecode-metadata.json`.
