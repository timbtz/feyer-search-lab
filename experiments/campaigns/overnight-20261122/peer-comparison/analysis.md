# Same-machine peer comparison: current pinned implementations

**The peer is faster on the large benchmark in this comparison.** All 12 official checks passed across six preregistered paired requests. This result does not establish that either implementation is correct for every unseen optical topology.

Peer: imported `be4949e104da90968b426e4cbdd5c9c725eb2c12`, exact `differometor` tree from upstream `akshat-bhat/Feyer@7615f59ced23a5988e66eddc8408ff823dcd3651`. Ours: repaired `3b107d69d9d083f7aaa5f11b952f0098ed0ba528`. The superseded c38/e2 version was not used.

| Implementation | Large median | Large range | Large CV | aLIGO median | aLIGO range | aLIGO CV |
|---|---:|---:|---:|---:|---:|---:|
| peer | 0.703439 s | 0.699938–0.705492 s | 0.40% | 0.542659 s | 0.537799–0.547924 s | 0.93% |
| repaired | 0.855262 s | 0.846512–0.935072 s | 5.55% | 0.538566 s | 0.536406–0.539975 s | 0.33% |

The peer wins the large benchmark in all three matched blocks. Our paired time ratio is **1.2123×** the peer (about **21.23% longer**); the descriptive three-block bootstrap interval is 1.2094–1.3293×. Our aLIGO time is slightly lower in all three blocks, paired ratio **0.9951×** (about **0.49% shorter**), interval 0.9829–0.9974×. These few selected observations give weak uncertainty; they are not a universal ranking or a prediction for the judges’ hardware.

The repaired large-run samples were 0.935072, 0.846512 and 0.855262 seconds. The first slower observation remains included. The three peer samples were 0.703439, 0.699938 and 0.705492 seconds. All sample arrays and phase values are in `analysis.json`.

## Fairness and official validation

Both ran serially on the same AMD instance and logical CPU 2 with the same fixed environment, unchanged vendored official harness, one requested/effective CPU, numerical threads set to one, double precision and persistent compilation caching disabled. Each request had a new checkout and a fresh process per benchmark; grid ran first, then aLIGO, with three internal warm repetitions. No warmup/sample removal or OS-cache reset is claimed. Both launches had DIFFEROMETOR_XLA_DEFAULTS unset, permitting each package’s own declared compiler defaults. No package/dependency or evaluator changes were made for the comparison.

All large runs retained 101 frequencies and 193 design variables; aLIGO retained 101 frequencies and 29 variables. The unchanged official sensitivity and gradient sanity checks passed, and saved output/gradient finiteness checks passed. Every paired request/report hash and exact source identity was checked by the analyzer.

## Broader feasibility remains separate

Separate three-process dual/full 14-case preflights are attached for the exact revisions. Both passed the official benchmark checks. The repaired revision matched the initial seed across all 14 cases. The peer differed from that seed in **dev, uifo_rand3 and voyager**. These are strict-reference disagreements, not failures of the official public benchmark; comparison with our seed alone does not establish which answer is physically more accurate. Both implementations also have differences versus the pristine numerical reference, preserved case by case in the evidence.

Source inspection found three generic builder concerns in the peer-derived builder: grouped optimization pairs scheduled only the final member’s carrier update; the no-link placeholder assumed registry slot 0 even after real links were registered; and carrier readers of a parameter owned by another component were not generally scheduled. These can matter for other setups and are distinct from the three numerical disagreement cases—no causal attribution between them is established here. A separate proposed combination `d785b5bb` adds only these builder fixes and retains the peer solver unchanged. It is not part of this frozen head-to-head, and no result for it is inferred from these numbers.

Unknown final optical setups require generic correctness. Passing two public benchmarks and 14 cases is useful bounded evidence, not a guarantee for unseen topology or all gradients. This report grants no automatic promotion. The source-review hold on earlier approximate-adjoint candidates remains unrelated and unchanged.

Evidence: `plan.json`, `peer-source-provenance.json`, `analysis.json`, all six raw states under `results/`, and attached preflight states e499f5510f9d4895b7063359b1e18380 / fbe23beea6e049ccbb5e971232a00955.
