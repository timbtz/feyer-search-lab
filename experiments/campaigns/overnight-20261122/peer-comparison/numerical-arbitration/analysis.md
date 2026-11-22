# Saved-array numerical arbitration

No new benchmark, optimization or tolerance change was performed. A bounded read-only script loaded existing AMD NPZ archives in the fixed environment and returned statistics only. Archive paths/hashes and every inspected value are recorded in `saved-array-analysis.json`; the script is `inspect_saved.py`. All compared input arrays were identical.

## Conclusions

1. **The scalar dev loss disagreement is tiny in absolute units, but not within the existing scalar-relative check.** Finite choice01 differs from the initial seed by 1.2290e-12 at a reference loss of 9.72506e-8: relative 1.26375e-5, allowed absolute 9.72516e-15. Its maximum log-sensitivity difference is only 5.3204e-10. A cancellation-sensitive small loss is plausible, but the saved arrays alone do not prove that explanation or authorize accepting the mismatch.
2. **Voyager signal disagreement is small globally but not uniformly small per component.** Finite choice01 has 342 failing signal entries, maximum absolute difference 227356.4 and norm-relative error 3.79769e-11 against global magnitude 9.33305e14. However, one failing reference component is 78,085,715−9,184,722i; its difference is 227356 (about 0.29% of that component), versus allowed 941.2. This is not merely an exactly zero entry. Its log-sensitivity difference is 2.13e-13, so the readout is much less affected than some internal signal components. Norm agreement must not replace elementwise validation.
3. **The patched peer uifo_rand3 disagreement is not just near-zero noise.** All 101 sensitivities and 41 gradient entries disagree with the seed. Maximum log-sensitivity difference 1.513358e-5 exceeds the unchanged 1e-5 generalization bound; sensitivity and gradient norm-relative differences are about 1.509e-5. A representative gradient changes by 3187 on a reference 2.112e8. Peer IR3 remains at 1.511436e-5 log difference; extra refinement did not remove this discrepancy.
4. **The repaired 3b revision matches the initial seed exactly on all inspected dev, Voyager and uifo_rand3 outputs.** It still differs from the pristine solver; this is inherited evidence, not proof the seed is physically exact. On uifo_rand3 the seed/repaired log-sensitivity difference from pristine is 5.81009e-5, while patched peer is 7.31888e-5. Without a trusted higher-accuracy reference, these comparisons do not establish which solver is closest to the true physics.
5. **Our 1/1 option does not solve the strict failures.** Dev loss differs by 6.2482e-12; Voyager has 364 signal failures. Its uifo_rand3 log-sensitivity difference from seed is 2.2240e-8, so it does not exhibit the peer’s larger uifo_rand3 deviation.

## Compact evidence versus the exact initial seed

| Variant | dev loss absolute difference | Voyager signal failures / norm-relative error | uifo_rand3 max log-sensitivity difference |
|---|---:|---:|---:|
| repaired | 0 | 0 / 0 | 0 |
| finite_choice01 | 1.22901e-12 | 342 / 3.79769e-11 | 2.94898e-08 |
| peer_builder | 2.34142e-11 | 358 / 5.58595e-11 | 1.51336e-05 |
| peer_ir3 | 2.48899e-11 | 354 / 5.04003e-11 | 1.51144e-05 |
| own_1_1 | 6.24823e-12 | 364 / 4.75423e-11 | 2.22401e-08 |

The additional strict policy is rtol 1e-7 plus 1e-12 times the reference array maximum. That policy remains unchanged. Official public benchmark PASS and these extra review failures must remain separately reported. No candidate is accepted by this analysis.

Investigated request IDs: repaired fbe23beea6e049ccbb5e971232a00955; finite choice01 fa0b0b291fb7410eadade23ac6f4c1a8; patched peer 26ff7e5e15a046dcbd580cc27a433357; peer IR3 16bf79efb24f4c57a7505758def7a1a0; own 1/1 eaf471b3b75845a1a0d0f097092d38d3.
