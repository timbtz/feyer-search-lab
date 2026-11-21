# Numerical correctness audit

Audit scope: read the immutable official harness, screening implementation, strict comparator, candidate records and candidate-2 source diff. Read saved remote arrays with NumPy; no simulator changes, no benchmark runs and no environment/package changes. The only implementation changes are richer comparator diagnostics and their focused tests, as requested by the coordinator.

## Main finding

Candidate 2 passes the published executable checks but fails the team's additional regression gate in **3 of 193 gradient entries**. That establishes a reproducible difference under our policy, not an official challenge disqualification and not proof that the new arithmetic is physically wrong. Do not silently relax the gate or label the candidate numerically safe. Classify it as **official checks passed; strict regression review required** until independent evidence resolves the discrepancy.

The current strict gate is a useful conservative regression guard, but it is not a mathematically calibrated error bound. It can be simultaneously too strict for harmless rearrangements and too lenient for very small components.

## Exact candidate-2 evidence

- Candidate SHA: `7f3cf9c316ce87a98afccb402bffc34e4ff71532`.
- Full job: `a7b341dc0cc64363922bcb3023a14537`.
- Saved candidate arrays: `/workspace/feyer-lab/runs/a7b341dc0cc64363922bcb3023a14537/arrays.npz`.
- Reference: `/workspace/feyer-pristine/base1.npz`; parameter names come from that job's `report.json` → `inputs.optimization_pairs`.
- Strict per-entry rule: `abs(candidate-reference) <= 1e-7*abs(reference) + 1e-12*max(abs(reference_array))`.
- Gradient-array absolute floor: `5.7585650888075384e-8`.

| Index | Parameter | Baseline derivative | Candidate derivative | Absolute error | Allowed error | Error / allowance |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 33 | mb13.reflectivity | -68.82591682002862 | -68.82594164082013 | 2.48207915e-5 | 6.94017733e-6 | 3.576 |
| 161 | boundary01.power | -29.61288925877842 | -29.612926349352314 | 3.70905739e-5 | 3.01887458e-6 | 12.286 |
| 180 | m03.reflectivity | 1.50237893885408 | 1.5023793964105558 | 4.57556476e-7 | 2.07823545e-7 | 2.202 |

Relative errors for those entries are approximately `3.61e-7`, `1.25e-6` and `3.05e-7`. The previously reported largest absolute error, `0.00279785`, belongs to **mr13.reflectivity, index 29**, whose much larger reference magnitude means it actually passes the gate. A global maximum or relative L2 norm alone therefore hides which coordinates caused rejection. Relative L2 gradient error is only `4.7521e-8`.

Carrier, signal, powers, parameters and frequencies are identical. Noise and sensitivity differ slightly but pass the strict gate. The maximum absolute public-reference log-sensitivity error is `5.3759e-6`, below the official `1e-5` threshold.

The gradients saved by original baseline runs 2 and 3 are bitwise identical to run 1. Thus candidate 2's discrepancy is not explained by variation between those three unchanged-code runs. This does not establish an error bound for algebraically rearranged code.

## What the algebra says, and does not say

The candidate replaces a final noise solve with an existing adjoint contraction. Let `A^H w = d`; then `w^H = d^H A^-1`, so `d^H A^-1 N w = w^H N w`. The source transformation matches this identity, which does not require `N` to be Hermitian. In exact arithmetic, with invertible systems and differentiable operations, the scalar and its derivatives agree.

The changed solve/contraction path can accumulate different floating-point error. The saved arrays alone cannot tell us which implementation is closer to the exact value. We did not measure condition numbers, solve residuals or higher-precision reference derivatives, so any claim that conditioning or cancellation explains the difference remains a hypothesis. The loss is a mean of log-sensitivity ratios close to zero, which makes raw relative loss differences a poor correctness criterion. Inspect frequency-resolved outputs and absolute/directional loss errors instead.

## Screening and official checks

`lab/screen.py` checks the entire workload's sensitivity reference tolerance, finite outputs/loss/gradients, positive sensitivities, gradient shape and a nonzero full gradient. It explicitly records the finite-difference check as not run. The log line at line 236 nevertheless says it is validating a finite-difference gradient; that wording is misleading and should be corrected without changing the mathematics.

The official harness (`benchmark.py`, lines 250–265) checks **one coordinate**, `mb11.tuning`, with central differences at physical steps `1e-3` and `5e-4`. It compares autodiff against both estimates and the two estimates against each other with `rtol=0.01`, `atol=1e-6`. It does not independently differentiate all 193 coordinates. Candidate 2 passes this spot check; its autodiff value is `7.61616949e-5` and the two estimates are `7.54940957e-5` and `7.59564512e-5`.

Full validation and saved arrays use the last warm repetition's `host` outputs, because the official loop overwrites `host` before validation. Screening validates the first evaluation. For ordinary pure JAX code the workload is identical, but one should not claim that the full harness separately checks the timed first execution's output. Keep the official harness immutable; any first-versus-warm output consistency check should be a separate trusted diagnostic.

The shared worker currently treats an official pass plus strict mismatch as a failed internal run; reporting must expose both statuses independently. Screening success must never be called full correctness.

## Strict-gate limitations and recommended policy

The all-gradient comparison adds broad regression coverage, but raw derivatives use mixed physical units. A single absolute floor derived from the largest entry is not physically uniform. For example, the baseline derivative for `m01sus.mass` is about `1.945e-30`, yet this gate allows an absolute error near `5.76e-8`. Setting sufficiently tiny entries to zero can therefore pass even though their relative error is 100%. Conversely, the candidate's largest failing relative discrepancy is approximately one part per million.

Recommended design:

1. Preserve separate statuses: execution/workload integrity, official check outcome, strict regression outcome, independent derivative audit, and timing repeatability. Never overwrite an official pass with an undifferentiated correctness failure.
2. Retain the existing strict tolerance for automated safe promotion for now. Treat strict-only failures as reviewable candidates, not permanently discarded ideas or official failures.
3. Version any future tolerance policy and document its numerical justification. Do not tune tolerances after seeing one attractive speedup.
4. Design parameter-scaled diagnostics using dimensionless coordinates `p = p0 + S*q`, so the compared gradient is `S*g`. Choose physical scales by parameter type and allowed range, not a single arbitrary array maximum. This is additional diagnostic evidence until independently calibrated.
5. Report each failing index, its parameter name, reference/candidate values, allowed error and error/tolerance ratio; retain all 193 gradient diagnostics and bound large non-gradient payloads.

## Independent derivative protocol for solver rewrites

This is a proposed diagnostic protocol, not work already executed. Run it through the serial evaluation process outside the score timer and retain the exact candidate, seeds, points, steps, scales and reference implementation.

**Component level:** compare the rewritten linear-algebra primitive against the untouched dense JAX primitive on small, seeded real and complex systems, multiple right-hand sides and a controlled range of conditioning. Check primal residuals, output differences, JVP/VJP directional identities and reverse derivatives of real scalar projections. Test real and imaginary perturbations separately. For exact complex solve differentials, use `dx = A^-1(db - dA*x)` as an independent derivation and check the implementation's cotangent convention. Higher-precision small-system references can help decide whether a discrepancy is baseline error or candidate error.

**Full objective:** start with the three candidate-2 failing coordinates plus the official tuning coordinate and representative coordinates from other parameter families. Use a step-size sweep and require a stable finite-difference plateau; a lack of convergence means the test is inconclusive, not that the candidate passes. Never apply `1e-3` to every parameter: `boundary01.power` is only `1.0179e-12`, while the two failing reflectivities are `0.9990442` and `0.00030495`. Use bound-aware relative/scaled perturbations. Preserve the public parameter ties.

**Directional coverage:** test several fixed random directions in dimensionless parameter coordinates, at the public point and a small documented set of admissible perturbations. Compare the finite-difference scalar directional derivative with `g·direction` for both candidate and baseline. Also test several projections of the 101 log-sensitivities; checking only their mean can hide frequency-wise derivative cancellations. Expensive exhaustive coordinate checks should be reserved for serious solver changes/finalists, with retained evidence.

**JAX-specific cautions:** `jax.test_util.check_grads` checks one randomly chosen direction per invocation, not every coordinate. It is useful for primitive checks but not complete coverage. Its default forward mode is unsuitable for a reverse-only `custom_vjp`; use supported reverse-mode checks and independently constructed directional tests. JAX's complex VJP convention uses a bilinear cotangent pairing, so generic conjugate-transpose formulas must be checked against the actual complex-to-real derivative representation. These points are documented by [check_grads](https://docs.jax.dev/en/latest/_autosummary/jax.test_util.check_grads.html), [custom VJP limitations](https://docs.jax.dev/en/latest/301/custom-jvp-vjp.html#custom-vjp-functions-can-t-be-forward-differentiated), and [complex differentiation](https://docs.jax.dev/en/latest/301/cookbook.html#complex-numbers-and-differentiation).

## Implemented diagnostics and validation

`lab/compare_arrays.py` now records failing counts and indices, per-entry reference/candidate/error/tolerance, normalized error ratios, and explicit truncation. Gradient details retain every entry; other arrays cap failure details at 20 while preserving the total count. Complex diagnostics are JSON-safe objects; infinite ratios are represented with a null numeric value and an explicit infinity flag. The acceptance inequality, constants and exact parameter/frequency checks are unchanged.

Six focused tests passed in the existing `/workspace/venv-feyer` environment using an isolated temporary directory that was deleted afterward. Tests cover all 193 gradient failures, bounded non-gradient diagnostics, exact-match zero tolerance, complex values, passing differences and non-finite values. The updated comparator was also run against the saved candidate-2 arrays and reproduced exactly three failures. The local stdlib test suite skips these six when NumPy is unavailable; this is explicit, not an untested pass. No packages were installed.

## Remaining uncertainties

- Whether candidate 2 or the baseline is closer to exact derivatives: unresolved.
- Official organizer tolerance for all 193 gradients beyond the published spot check: unresolved; ask organizers before relying on a strict-only failure for a final submission.
- Numerical conditioning/residuals of the affected full workload systems: not measured in this audit.
- Which physical perturbation scales should define expanded gradient diagnostics: needs documented engineering choices, ideally confirmed with Feyer.
- Independent derivative suite for custom solvers: proposed above, not yet implemented or run.
