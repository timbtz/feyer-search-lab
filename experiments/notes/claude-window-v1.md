# Claude exploration and topology tuning, 2026-11-21

Two independent managed Claude Opus 5.5 sessions explored numerical implementation structures from exact parent `d09dc1d08fb046d08b3b699685d8ff780d611e87`. All evaluations used the existing serial AMD CPU-2 queue and unchanged workload, precision and full correctness checks. The new authorization ends at Unix 1795288990 (19:23:10 UTC); no later submissions are authorized. Previously admitted jobs may drain.

## Exact-revision confirmation

Reference candidate `96474bdd4d83bb02c163640f63fae1c4bd7a21d4` reuses the noise-matrix construction and LU(A), keeping the A^H solve separate. It has three full official-and-strict passes in the same source/evaluation cohort:

| Full job | Complete first run, seconds |
| --- | ---: |
| [ab12c14c29354bad9aa6dc024c91f8e6](../runs/claude-window-confirmation-v1/ab12c14c29354bad9aa6dc024c91f8e6.json) | 22.365550714 |
| [f952aea691ba45ff9859c2e2104d8b45](../runs/claude-window-confirmation-v1/f952aea691ba45ff9859c2e2104d8b45.json) | 22.659418643 |
| [c04de1b4b49440739ae3ea7713984561](../runs/claude-window-confirmation-v1/c04de1b4b49440739ae3ea7713984561.json) | 22.261753045 |

Median **22.365550714 s**, range **22.261753045–22.659418643 s**. All three gradients have zero failing entries, maximum absolute error 5.093170329928398e-10 and relative L2 error 7.576529280174932e-15 against the fixed reference.

These are exact-SHA repeats, not a paired comparison with the parent. The parent's recorded full time is 23.840 s; its independent interleaved repeats were not collected in this window. No final challenge submission or simulator merge is implied.

## Exploration outcomes

- Noise lane: `f3139c7` guarded broadcast reuse passed at 23.320 s; `e525ee5` shared contraction passed at 22.564 s with normalized gradient error about 0.949 of the tolerance; `bb9a183` shared A/A^H factorization ran 18.653 s but failed strict gradients and is rejected. `96474bdd` is the repeat-validated reference above. `05508471` direct-factorization reuse plus shared contraction passed once at 21.649 s, also with a narrow strict margin; it is not repeat-confirmed.
- Structure lane: `4c12600` merged same-matrix right-hand sides passed at 22.495 s. Slice conjugation `39b23e3c` was slower at 22.794 s. Restoration `3e94580e` passed at 22.423 s but is a different SHA, not an exact-SHA repeat. Separate coefficient/RHS assembly `423bcc4a` passed once at 22.361 s, effectively tied with the confirmed reference within observed timing variation.
- Combination `28566a64a9efbdddc104762ac1f8212eb1d8370c` combines exact parents `f3139c7` and `4c12600` (broadcast reuse plus multi-RHS solve); its result was pending when this report was prepared. Source and all individual feedback remain on `explore/claude-noise-reuse` and `explore/claude-structure-solve`.
- Alternate detector counts, carrier batches, padding and fallback shapes were audited from source by Claude but not benchmark-tested in this window. Do not infer generic coverage from the official workload alone.

## Numerical configuration search

Infrastructure `2ae00b7` is merged with standard and isolated-SMAC CI passing ([run](https://github.com/timbtz/feyer-search-lab/actions/runs/44938187937)). The new exact-topology adapter pins the source map, SHA, legal menu, cohort and deadline. It never substitutes the older seed8 renderer for this new topology.

Campaign `explore/topology-smac-v1` varies guarded noise reuse and assembly chunk size on exact `f3139c7`. Four full observations precede actual SMAC3 random-forest/expected-improvement selection. The first learned acquisition is `4a354d07` (reuse off, chunk 4), rank 1, source-bound evidence/context published in the campaign. No timing from another topology or screen trains the model.

| Reuse | Chunk | Status | First run, seconds | Learned SMAC |
| --- | ---: | --- | ---: | --- |
| True | 1 | valid | 23.320120 | None |
| False | 1 | valid | 23.883759 | False |
| True | 2 | valid | 24.194216 | False |
| True | 4 | valid | 24.634591 | False |
| False | 4 | valid | 25.487122 | True |
| True | 8 | evaluating_full | pending | True |

The tuning run has not improved its 23.320 s seed in the completed trials. This demonstrates the connected measurement/selection loop, not an efficiency advantage for SMAC. No campaign budget or deadline was extended.
