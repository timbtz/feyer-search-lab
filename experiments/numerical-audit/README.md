# Independent numerical and acceptance audit

Audit target: teammate import `e2fd659e6f426289c526f79ae758bed4182879a9`; compatibility harness `b093f74efa76c6457ffef04ccb6c27436524565d`. Local diagnostics used saved independent arrays and NumPy, not new simulator timing runs. No official benchmark or simulator code was changed here.

## Acceptance bugs reproduced

`harness-false-positives.json` reproduces original acceptance of NaN candidates, changed array shapes, missing leaves, renamed dictionary keys, an empty test inventory and unavailable reference results. Each prints `OVERALL COMPATIBLE`; the hardened comparator rejects them. Original CLI also exits zero after an explicit mismatch. The original synthetic `custom_linear_solve` loop prints `ok` for both a 99-fold relative discrepancy and NaN. Those loop tests execute the original AST with injected scalar outputs; they do not execute JAX or validate a simulator fix.

The updated comparator preserves dictionary keys, array shapes and all eleven required test IDs, rejects nonfinite/empty outputs, treats unavailable references as unavailable, emits structured checks and fails the CLI. Partial runs require identical source, harness, setup and execution-environment fingerprints before merging. The toy probe now checks numerical agreement/finiteness and exits nonzero when unavailable or different. Its scope remains one nonlinear complex 30x30 linear-system example, not full simulator semantics or timing. Source hashes and local metadata alone are not an independently trusted execution provenance certificate.

Reproduction:

```sh
python -m unittest lab.test_jaxcompat -v
python experiments/numerical-audit/reproduce_harness_audit.py  # NumPy required
python lab/jaxcompat.py compare reference.json candidate.json --out comparison.json
python lab/custom_linear_solve_probe.py --out toy-probe.json  # pinned JAX/SciPy environment
```

Eight adversarial unit tests passed locally. Both changed runners compile. JAX/SciPy toy execution was not rerun locally: local audit Python has NumPy, but no JAX.

## Actual receipt and physical-domain findings

Rechecking `.lab/review-teammate/patch-jaxcompat-reference.json` and `patch-jaxcompat.json` with the strict comparator yields **5 passing comparisons, 1 nonfinite output failure, 5 unavailable comparisons** for candidate cb502. The vmap test's original `status: ok` hides NaN in batch member 1's loss and all 45 gradients. All eleven dense reference outputs are finite. `cb502-strict-comparison.json` preserves the numerical comparison; source provenance remains supplied by the parent evaluator.

The historical test's claim that scaling keeps all parameters physical is false. Voyager coordinate 7 is `etmy.reflectivity`, initialized to `(1 - 1.5e-5 - 5e-6)/(1 - 5e-6) = 0.9999849999249997`. The reference gradient at that coordinate is -4182.660996830135. The very first historical descent update raises reflectivity to **1.0006842902687312**, and the saved final value is **1.001011042774878**. The positive vmap perturbation raises `etmy.reflectivity` to **1.0001542873183744** and `fm2.reflectivity` to **1.0001713455255787**. Reflectivity is constrained to [0,1]. Thus descent and batch failures demonstrate an API discrepancy for these supplied inputs but cannot establish a failure on admissible optical designs. The four forward/second-order transformation failures remain separate limitations. Preserve the old tests as unconstrained API stress and run bounded trajectories separately; never replace their existing raw results.

`PARAMETER_BOUNDS` includes optimizer sampling ranges, such as tuning [0,90], which even the built-in Voyager violates (fm2 tuning -0.014). These ranges must not all be called universal physical bounds. New annotations use only basic physical restrictions: reflectivity/transmissivity/loss in [0,1], nonnegative power and length, positive mass.

## Where the cross-setup discrepancy originates

Independent saved fields localize mismatches to signal readout rather than noise:

| Case | Worst frequency | Candidate/reference log sensitivity | Log noise difference | Cancellation |
|---|---:|---:|---:|---|
| rand1 | 1240 Hz | -2.0360985100964513e-4 | 5.0826e-13 | Balanced detector subtraction ~120 |
| rand3 | 2890 Hz | -7.318880999207522e-5 | 2.1272e-13 | Upper/lower sideband sum ~5.25e10 |

Cancellation measures are sum of magnitudes divided by magnitude of sum (or detector difference). They explain sensitivity to numerical perturbations; they do not establish which solver is correct. Stored float64 fields cannot recover lost bits. The strict official-array comparison also identifies 131 signal entries and gradient coordinates 33/161/180 beyond its tolerance, despite an official public PASS.

The teammate's `roundoff_study.py` performs eight residual corrections with extended-precision residuals, float64 LU correction solves, and a final float64 cast. This is not a correct-rounding certificate. It starts from the same float64 host assembly, so cannot diagnose assembly error independently; even its named benchmark case uses 60 frequencies from 10 to 5000 rather than the official 101-frequency grid. Its condition number alone is insufficient evidence because matrix scaling can dominate that number.

`check_setups.py` uses the modified package's own reference path, only 60 frequencies, special Voyager log thresholds, and omits gradient acceptance in those special cases. `scripts/compare.py` reports arrays_pass=true for two empty NPZ files because it skips absent baseline fields. Existing complete saved arrays remain useful evidence, but these harnesses cannot certify arbitrary future artifacts without inventory checks.

## Bounded arbitration procedure

1. Freeze pristine and candidate source SHA, harness SHA, all101 frequencies, all193 parameters, x64, hardware/CPU limits and fresh-process state. Preserve all raw outputs, not only PASS text. Verify full array inventory, shape, dtype, finiteness and positive sensitivity before numerical comparison.
2. Start with the identified failing frequencies/designs. Capture pristine and candidate assembled carrier and signal matrices and RHS values at identical inputs. Compare both assemblies directly; an assembly mismatch must be investigated before attributing error to LU roundoff.
3. Solve the same captured systems independently at increasing precision (e.g. 80 then120 decimal digits), including detector sums, sensitivity and noise. Check componentwise/scaled residuals and stabilization of the actual output and derivatives. If float64 assembly remains contested, independently evaluate assembly in higher precision from original input constants as a separate calculation. Precision stabilization is evidence; claim certified rounding only with a rigorous enclosure/error bound.
4. Differentiate linear systems independently via `A dx = db - dA x`, including every parameter-dependent readout/noise term, and compare all193 coordinates on the official setup plus a small set of physical interior perturbations. Use centered finite differences at multiple decreasing step sizes as corroboration, not proof; cancellation and solver error can contaminate finite differences too.
5. Run bounded descent and batching separately from historical unbounded API stress. Run forward/second-order transformations as their own internal acceptance gate. Official PASS, stronger physics checks, JAX compatibility and complete first-run timing are separate results.
6. Only after correctness gates pass, rerun complete first-run timings on matching pinned hardware in fresh processes. There is no source evidence that the existing official timer omitted asynchronous execution: it blocks on returned results, includes build/tracing, and the host engine assembles/solves on each evaluation. Token-cache reuse for a matching backward pass is not itself evidence of precomputed answers.

The new all193-coordinate finite-difference check at an interior point strengthens first-order evidence for that point. It does not settle arbitrary designs, second derivatives, full JAX compatibility or the ill-conditioned failing readouts.
