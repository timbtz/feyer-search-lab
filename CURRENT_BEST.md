# Current best submission

**Status:** admitted_campaign_best

**Exact simulator revision:** [ee4fea28c04d482566be16e916b609d7c6a99e5e](https://github.com/timbtz/feyer-search-lab/tree/ee4fea28c04d482566be16e916b609d7c6a99e5e)

The larger official benchmark is the primary objective. aLIGO is reported separately.
This is the best admitted candidate in this campaign; it is not an official judging verdict.

- grid: median 0.801577684 s; range 0.794424996–0.822483830 s.
- aligo: median 0.548555156 s; range 0.544719348–0.551624214 s.

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
- [Selected candidate evidence](experiments/campaigns/overnight-20261122/candidates/e4f7b59d3b094a8e9c6dd41263cab78e/record.json)

Search selection requires at least three fresh runs of each official benchmark, a large-case gain of at least max(3 ms, 0.5%), no more than 2% aLIGO regression, and relative timing range at most 10%. Under selection-v2, the candidate large-case maximum must also be strictly below the incumbent minimum. Overlapping candidates remain provisional for further paired investigation. Observed nonoverlap is not statistical proof. These are team heuristics, not organizer scoring rules. Failed and provisional trials remain in the candidate receipts.
