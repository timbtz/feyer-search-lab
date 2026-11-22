# Final paired confirmation: descriptive results, source hold

All 20 preregistered requests completed; all 40 official checks passed. Each candidate also passed the refreshed 14-case comparison with the exact initial seed. One CPU (logical CPU 2), double precision, fixed threads/cache rules, unchanged benchmark, and all samples were verified. No sample was discarded.

**No finalist is approved for promotion:** all four contain the approximate adjoint substitutions now under source-review hold. These measurements describe the original revisions, not the repaired successor.

| Candidate | Large median (s) | Large SD (ms) | Large CV | aLIGO median (s) | aLIGO SD (ms) | aLIGO CV |
|---|---:|---:|---:|---:|---:|---:|
| incumbent `ee4fea28` | 0.824692 | 7.880 | 0.95% | 0.548087 | 4.642 | 0.85% |
| latest `f856aafd` | 0.805754 | 6.764 | 0.84% | 0.525253 | 1.282 | 0.24% |
| layout `1ea70bfb` | 0.804962 | 4.774 | 0.59% | 0.521044 | 1.929 | 0.37% |
| stable `f90fa964` | 0.821303 | 3.289 | 0.40% | 0.532240 | 3.309 | 0.62% |

The layout candidate has the lowest observed medians on both benchmarks; the stable candidate has the smallest large-benchmark SD/CV, and latest has the smallest aLIGO SD/CV. Five observations cannot establish permanent variance ordering.

| Candidate | Large paired reduction (95% interval) | aLIGO paired reduction (95% interval) |
|---|---:|---:|
| latest | 2.14% (1.93%–3.38%) | 3.85% (3.40%–5.18%) |
| layout | 3.07% (1.56%–4.40%) | 4.44% (3.77%–6.44%) |
| stable | 1.29% (0.20%–2.02%) | 2.29% (1.77%–3.65%) |

Every non-incumbent candidate was faster than the incumbent in all five matched blocks on both benchmarks. Intervals use the preregistered median-log-ratio estimator and 20,000 whole-block resamples, fixed seed 20261123. With only five selected blocks, this is descriptive uncertainty, not a universal significance guarantee.

Each request uses a new checkout and one fresh process per benchmark; grid runs first, then aLIGO. Historical three-process-per-checkout medians are a separate timing scope. Grid import medians here are about 0.292–0.298 seconds, consistent with the earlier first-process penalty; source bytecode caching remains a hypothesis, and no OS cache flush was performed.

Full samples, phases, report/state digest bindings, provenance and paired ratios: `analysis.json`. Source risks: `local-semantic-audit.md`, `adjoint-counterexample.json`, `review-latest-metadata.json`. Physics tolerances were not changed.
