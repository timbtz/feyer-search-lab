# Final verification of the fast host solver

Target: **53f38d342c3228c052785e8c9d63b6ce9c832dd1**, unchanged throughout this audit.
No fallback was activated. The original audit respected the then-active Claude
stop instruction; these diagnostics launched no models. The user subsequently
authorized a separate [overnight campaign](https://github.com/timbtz/feyer-search-lab/blob/control/overnight-20261122/CURRENT_BEST.md).
That campaign does not retroactively change the verdicts below.

**Both official public benchmarks pass in three fresh processes each.** The
extended numerical review is not entirely green: six additional finite-difference
coordinates remain inconclusive, and two ill-conditioned random setups disagree
with the retained dense reference. Independent precision diagnostics favor the
fast solver, but do not prove arbitrary hidden-setup agreement.

## Official results

The unchanged upstream scripts are pinned to `83f8d2f40fc75218a1d8ec7908cc0bf1c8f99a75`.
Each process ran on logical **CPU 2 only**, `--cpus 1`, all numerical thread limits
one, double precision, and no persistent compilation cache. Complete first-run
totals include imports, setup, all three compilation stages, forward, sensitivity,
gradients and transfer. All source/setup/reference/harness hashes were checked.

| Setup | Workload | Fresh candidate totals | Median | Same-host pristine |
|---|---|---|---:|---:|
| Large grid | 101 frequencies / 193 variables | 0.997344, 0.986992, 0.986434 s | **0.986992 s** | 36.013788 s |
| Official aLIGO | 101 frequencies / 29 variables | 0.626026, 0.632717, 0.623395 s | **0.626026 s** | 21.946608 s |

Every run passes public sensitivity and gradient sanity checks with finite outputs
and nonzero gradients. Reports and complete phase accounting are under `official/`.
These are support measurements, not promotion into an old queue timing cohort.
Both queue locks were reserved, but unrelated host workloads cannot be excluded.

The final implementation performs host assembly with NumPy, sparse SuperLU solves
with iterative refinement, explicit reverse derivatives through JAX callbacks,
and the two package-set compiler options permitted by the organizer clarification.
Factorizations are shared within an evaluation; every fresh forward factors again.
The physical workload and official three-stage benchmark were not changed.

## What Claude had already established, and what was rechecked

Claude's prior official passes, modulation cases and BLAS variation were real
evidence. The new exact-candidate run covers all **14** custom cases, including
amplitude/frequency modulation. All produce complete finite outputs, nonzero
gradients, positive sensitivities, and identical input arrays to the retained
reference. The modulation log-sensitivity discrepancies are approximately
7.1e-15 and 5.2e-14. See `fourteen-cases.json` and the raw execution log.

Two random cases exceed the custom 1e-5 dense-reference log-sensitivity comparison:
`uifo_rand1` ~2.04e-4 and `uifo_rand3` ~5.81e-5. Historical archives have preserved
hashes; unlike the new runs, their original code binding is not retroactively
authenticated. The pristine checkout was independently verified clean at
`02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f`.

Two fresh diagnostics investigate those differences without changing tolerances:

1. **Same-assembly extended residuals:** refine the candidate's linear solves
   using 63-bit long-double mantissas instead of 52-bit double mantissas.
   Candidate log-sensitivity distances to that result are 7.5e-11 / 2.7e-8 on the
   disputed cases; dense-reference distances are 2.04e-4 / 5.81e-5. Candidate
   gradient relative-L2 distances are 5.5e-13 / 2.9e-9, versus 4.9e-6 / 1.5e-5
   for the dense reference. This shares candidate assembly and adjoint formulas.
2. **Independent pristine JAX assembly:** rebuild the matrices using the unchanged
   simulator, then solve with extended-residual refinement. Candidate signal
   relative-L2 differences are 1.5e-15 / 4.2e-15, versus dense-reference
   2.2e-10 / 1.7e-11. Detected-amplitude differences are 8.9e-11 / **1.43e-5**
   for the candidate and 2.04e-4 / 4.38e-5 for the dense reference. The second
   detector remains sensitive to assembly/carrier rounding; do not describe it
   as an exact-arithmetic oracle or a universal sub-1e-5 certificate.

Both diagnostics support the refined sparse solver's numerical accuracy. Merely
observing BLAS variability would not have established that. Neither diagnostic
changes the judges' comparison procedure or guarantees a hidden reference pass.

## Extra all-coordinate gradient sanity

The additional check perturbs every coordinate, with a three-step finite-difference
ladder and the public sanity-style 1% relative / 1e-6 absolute bounds. A fixed
alternative step menu probes truncation and cancellation on initially flagged
coordinates. Original results are preserved rather than overwritten.

- Large grid: **187/193** coordinates confirmed; indices **54, 59, 63, 136, 161,
  163** remain inconclusive due to unstable step ladders. The initial two apparent
  failures resolve with alternative steps; no settled failure remains in this
  diagnostic, but inconclusive does not mean passed.
- aLIGO: **29/29** confirmed.
- The unchanged official benchmark's own gradient check passes in all six runs.

Our stricter saved-array regression still flags three large-grid gradient entries,
some signal entries and near-zero losses. That additional regression policy is
not the organizers' exact correctness rule. Its raw results remain visible in
`official/execution.json` and `strict-fourteen-cases.json`; they were not waived
or converted to passes. The extended review must not be summarized as "all checks
green" or as a proof that all 193 derivatives match a high-precision oracle.

## Follow-up on the six unresolved coordinates

Two completed precision-assisted experiments are now archived, including all
unsuccessful step attempts. Both compare alternative diagnostic primals with the
**unmodified exact candidate's autodiff gradient**; neither reruns the official
benchmark or changes simulator source.

| Diagnostic primal | Additional supported coordinates | Still unresolved | Wall time / sampled peak RSS |
| --- | --- | --- | --- |
| Extended residual solves and long-double readout | 59 (`mr22.reflectivity`), 136 (`m20.reflectivity`) | 54, 63, 161, 163 | 178.28 s / 902,103,040 bytes |
| Long-double component/assembly calculations, residual refinement and readout | None | 54, 59, 63, 136, 161, 163 | 169.88 s / 947,789,824 bytes |

The first diagnostic supports **2 of the 6** previously unresolved coordinates
under its declared 1% relative / 1e-6 absolute criterion; four remain unresolved.
The second leaves **all six unresolved**, including a stable but mismatching
step ladder for index 59. The first likewise retains a stable but mismatching
attempt at index 161. These attempts are not discarded or renamed successes.
Because the diagnostic primal differs from the original double-precision
black-box function, those observations do not by themselves prove a settled
failure of the submitted gradient either.

**The original count stays 187/193**, not 189/193 or 193/193. These are numerical
investigations, not a new validation pass, an independent physics oracle, or
scored timing evidence. Long double alone did not resolve the outstanding
questions; near-zero readouts, step-size sensitivity and finite precision still
need care. No tolerance, official result, fallback decision or candidate source
was changed. Both reports explicitly retain `passed: false`.

See [follow-up summary](gradient-followup-summary.json),
[residual/readout report](precision-gradients/gradient-grid.json) and
[extended-assembly report](extended-assembly-gradients/gradient-grid.json).
Each directory also includes its execution receipt and complete stdout log;
`artifact-manifest.json` records hashes matching the retained local originals.

## Classification and fallback

Public benchmark PASS, extra numerical review, infrastructure-policy rejection,
and timing promotion are separate outcomes. A real reproducible physics failure
blocks acceptance of that revision; it calls for diagnosis/repair. An inconclusive
finite difference or obsolete package-flag guard does not automatically select
the slower dense candidate. `summary.json` records `fallback_activated: false`.
No search-controller promotion or selection policy was silently changed.

The original queue's no-XLA-flags guard is still deployed. The separate reviewed
allowlist change exists, but the earlier automatic approval rejection prevented
stopping/redeploying that shared worker. This audit did not attempt that restart.
Updating worker and report-consumer policy coherently is still separate
infrastructure work; these support reports already establish the official passes.

## Reproduction and retained evidence

- `lab.transfer_run`: four matched pristine/candidate official runs, runtime d804f35.
- `lab.final_candidate_check`: all-coordinate checks, fourteen cases and precision
  diagnostics, runtime e7b0aab. Its four extra repeat commands initially exited
  before measurement due to an import-path error. Those errors remain recorded.
- The corrected launcher, runtime fb9f79c, ran the step rechecks and all four
  official repetitions successfully. Candidate source was unchanged.
- `run_independent_probe.py` / `independent_accuracy_probe.py`: fresh pristine
  assembly diagnostics, versioned before execution. No dependencies were changed.

Both evaluator queue locks were respected, each benchmark/diagnostic used CPU2,
and subprocess groups had a sampled 16GB RSS watchdog and bounded deadlines.
No worker service was stopped or redeployed. No managed model was started.

Reports/logs, commands, hashes, unsuccessful attempts and precision outputs are
committed here. Large raw arrays remain in the local/AMD paths listed in
`artifact-manifest.json`. The same raw files support the comparisons; no result
was inferred from an HTTP success, model prose, or a screen timing.

Validation tools: **54 focused tests passed** (gradient, transfer, worker and
array comparison); branch CI passed. Review is in PR20 against the existing
generalization branch; no main merge or live acceptance-policy deployment.
