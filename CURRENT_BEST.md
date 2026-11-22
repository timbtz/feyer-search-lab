# Current best submission

**Status:** admitted_campaign_best

**Exact simulator revision:** [5bbb91e38ff993a10486f296a738860339cd05e0](https://github.com/timbtz/feyer-search-lab/tree/5bbb91e38ff993a10486f296a738860339cd05e0)

The larger official benchmark is the primary objective. aLIGO is reported separately.
This is the best admitted candidate in this campaign; it is not an official judging verdict.

- grid: median 0.852666680 s; range 0.850608243–0.882359037 s.
- aligo: median 0.555709917 s; range 0.551790904–0.558408344 s.

## Evidence and limitations

- [Machine-readable current best](experiments/campaigns/overnight-20261122/current-best.json)
- [All candidate receipts](experiments/campaigns/overnight-20261122/candidates)
- Only exact-source, matching-cohort results with both official benchmarks and generalization admission can replace this record.
- Strict signal and gradient mismatches at indices33,161,180 remain visible.
- Custom uifo_rand1/uifo_rand3 exceed dense sensitivity agreement bound; precision diagnostics support candidate accuracy but do not certify every case.
- Grid finite-difference coordinates54,59,63,136,161,163 unresolved; extra aLIGO29/29 confirmed.
- Whole-pass custom VJP lacks JVP/Hessian support.
- Support audit, ranking_eligible=false; CPU2 and threads1, other-host contention not excluded. Recalibrate current cohort.
- grid pristine-reference disagreements remain; see complete candidate receipt.
- aligo pristine-reference disagreements remain; see complete candidate receipt.
- Generalization pristine-reference disagreements remain; see complete candidate receipt.
- [Selected candidate evidence](experiments/campaigns/overnight-20261122/candidates/2c7810bfe84648299731e98a6bb133ae/record.json)

Search selection requires at least three fresh runs of each official benchmark, a large-case gain of at least max(3 ms, 0.5%), no more than 2% aLIGO regression, and relative timing range at most 10%. Under selection-v2, the candidate large-case maximum must also be strictly below the incumbent minimum. Overlapping candidates remain provisional for further paired investigation. Observed nonoverlap is not statistical proof. These are team heuristics, not organizer scoring rules. Failed and provisional trials remain in the candidate receipts.
