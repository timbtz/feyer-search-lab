# Current best submission

**Status:** source_review_hold — not currently cleared for submission

**Exact simulator revision:** [ee4fea28c04d482566be16e916b609d7c6a99e5e](https://github.com/timbtz/feyer-search-lab/tree/ee4fea28c04d482566be16e916b609d7c6a99e5e)

The larger official benchmark is the primary objective. aLIGO is reported separately.
This was the fastest admitted candidate. A later source audit found a generalization risk shared by this revision and the faster provisional finalists. Its recorded benchmark passes remain valid, but submission clearance is suspended pending repair.

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

## New source-review hold

Approximate collinearity/Hermitian shortcuts can amplify discarded residuals through an ill-conditioned inverse. This is an algebraic counterexample, not an observed failure of the two official fixtures. We are restoring explicit adjoint solves before the new finite solver-tuning experiment. [Review evidence](experiments/campaigns/overnight-20261122/final-confirmation/source-review.json).

## Tested conservative candidate and current peer comparison

**Tested conservative candidate: [3b107d69](https://github.com/timbtz/feyer-search-lab/tree/3b107d69d9d083f7aaa5f11b952f0098ed0ba528)**. It restores explicit adjoints, passed six official processes and all 14 seed-relative cases, and received an independent local source review. This is not a new speed promotion or proof of correctness on every unknown setup. The historical fastest record above remains under source-review hold.

The current teammate simulator from `akshat-bhat/Feyer@7615f59` was imported byte-for-byte as `be4949e1`, not reimplemented. On this AMD instance, three balanced cold-checkout pairs gave medians **0.703439 s peer vs 0.855262 s conservative repair** on the large workload; **0.542659 s vs 0.538566 s** on aLIGO. All 12 official checks passed. The peer has separate seed-relative disagreements and generic builder concerns; timings alone do not establish suitability for the judges' unknown topology. [Comparison and evidence](experiments/campaigns/overnight-20261122/peer-comparison/analysis.md).

The six-point SuperLU scheduling sweep found no admissible improvement: all five nondefault settings failed additional regression checks despite official PASS. Follow-up small-supernode and refinement trials are recorded separately. [Finite search](experiments/campaigns/overnight-finite-v1/README.md).

Autonomous Codex/Claude optimization is stopped at the user's request. No new model calls or budget extension are authorized by this record.
