# Current best submission

**Status:** seed_pending_fresh_calibration

**Exact simulator revision:** [53f38d342c3228c052785e8c9d63b6ce9c832dd1](https://github.com/timbtz/feyer-search-lab/tree/53f38d342c3228c052785e8c9d63b6ce9c832dd1)

The larger official benchmark is the primary objective. aLIGO is reported separately.
This is the best admitted candidate in this campaign; it is not an official judging verdict.

- grid: median 0.986991538 s; range 0.986434275–0.997343801 s.
- aligo: median 0.626026371 s; range 0.623395482–0.632716989 s.

## Evidence and limitations

- [Machine-readable current best](experiments/campaigns/overnight-20261122/current-best.json)
- [All candidate receipts](experiments/campaigns/overnight-20261122/candidates)
- Only exact-source, matching-cohort results with both official benchmarks and generalization admission can replace this record.
- Strict signal and gradient mismatches at indices33,161,180 remain visible.
- Custom uifo_rand1/uifo_rand3 exceed dense sensitivity agreement bound; precision diagnostics support candidate accuracy but do not certify every case.
- Grid finite-difference coordinates54,59,63,136,161,163 unresolved; extra aLIGO29/29 confirmed.
- Whole-pass custom VJP lacks JVP/Hessian support.
- Support audit, ranking_eligible=false; CPU2 and threads1, other-host contention not excluded. Recalibrate current cohort.
- Historical seed evidence is retained; current-cohort fresh dual calibration is pending.

Search selection requires at least three fresh runs of each official benchmark, a large-case gain of at least max(3 ms, 0.5%), no more than 2% aLIGO regression, and relative timing range at most 10%. These are team heuristics, not organizer scoring rules. Failed and provisional trials remain in the candidate receipts.
