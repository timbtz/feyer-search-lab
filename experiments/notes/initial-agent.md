# Initial exploration: seed-agent

- Assigned worktree: `/Users/t.betz/Documents/Feyer challenge agents/codex-seed`
- Assigned branch: `explore/seed-agent`
- Starting checkout / candidate parent: `0bf57ae2af4a377f72cb34a3d6a328c714baafc8`
- Public simulator baseline: `02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f`
- Managed session label: `seed-agent`; conversation identifier unavailable in supplied context. Local `.lab/sessions/seed-agent/status.json` is absent. Supervisor owns session continuity and submission.
- Budget: four distinct candidates or one hour; candidate 2/4 is now prepared. Initial supervisor allowance: 3599 seconds; allowance at start of candidate 2 turn: 3260 seconds. No commits, pushes, SSH calls, local benchmark runs, or evaluator submissions made by agent.

## Baseline evidence supplied by maintainer

Unchanged AMD official complete first-evaluation totals: 35.821919, 35.614326, 35.737065 seconds; median 35.737065 seconds. All three official checks passed. Reported warm medians approximately 15.49–15.73 seconds. Baseline import, compilation and total job-duration breakdowns were not supplied in this turn.

## Candidate 1: defer visualization import

- Candidate SHA: `2f190c5cffdaf8f86701dfae49dddae6a1efe028`; parent above.
- Hypothesis: avoiding `differometor.plot` and its Plotly import during benchmark package initialization reduces import time and complete first-run time. Simulation/compilation/warm runtime should be unaffected, but this is unmeasured.
- Static import inspection: `__init__.py` eagerly imported `visualize_setup`; `plot.py` imports `plotly.graph_objects`, NumPy, dataclasses and collections and creates rendering constants at import time. No other simulator module imports `plot.py`. The benchmark imports `differometor as df` and does not import the visualization function.
- Change: replace the eager re-export with module `__getattr__`, loading and retaining the original function on first attribute access. Explicit public exports retain wildcard access to visualization; `__dir__` retains discovery without loading Plotly. Named imports and the original callable signature, identity and documentation are preserved. A wildcard import intentionally still loads visualization.
- Local validation: Python syntax compilation and isolated package-export smoke checks with stubbed simulator/plot modules passed. Checked that package initialization and `dir()` do not load plot, missing attributes raise `AttributeError`, named import returns the original callable, repeat lookup is cached, and wildcard imports resolve all eight public exports. This is export-machinery validation only, not physics or real dependency validation. No dependencies installed or modified.
- Tool failures: first execution host timed out before a response; retry succeeded. Two commands involving `rg` exited 137; import and instruction inspection completed using Python AST/path reads instead. These were local tooling failures, not evaluator failures.

### Candidate 1 screen result

- Run: `de1c765c98d34a1eb4ab795480294e36`; verdict: `screened`.
- Complete first-run: 36.932242520 s; process wall time: 38.528558584 s; peak RSS: 15146280 KiB.
- Trace/lower/compile total: 20.415553268 s; warm median: None s.

| Phase | Seconds |
| --- | ---: |
| imports | 0.312570592 |
| initialize | 0.004929187 |
| load | 0.002366476 |
| build | 0.761417372 |
| forward_lower | 1.190352339 |
| forward_compile | 13.319029011 |
| forward | 12.407103729 |
| sensitivity_lower | 0.104208760 |
| sensitivity_compile | 0.552228406 |
| sensitivity | 0.001135498 |
| gradient_lower | 0.361856993 |
| gradient_compile | 4.887877759 |
| gradient | 3.026635902 |
| host_transfer | 0.000530496 |

### Candidate 1 full result

- Run: `1f2688d7b01e4ed99a4d18b61c3cd770`; verdict: `validated`.
- Complete first-run: 36.996297654 s; process wall time: 125.815408235 s; peak RSS: 15140604 KiB.
- Trace/lower/compile total: 20.755015159 s; warm median: 15.402737079188228 s.

| Phase | Seconds |
| --- | ---: |
| imports | 0.279067064 |
| initialize | 0.003326595 |
| load | 0.001405405 |
| build | 0.851080032 |
| forward_lower | 1.254856288 |
| forward_compile | 13.498421660 |
| forward | 12.145592211 |
| sensitivity_lower | 0.102794476 |
| sensitivity_compile | 0.568329312 |
| sensitivity | 0.000873093 |
| gradient_lower | 0.298296092 |
| gradient_compile | 5.032317331 |
| gradient | 2.959627908 |
| host_transfer | 0.000310188 |

### Candidate 1 correctness and decision

- Full official sensitivity and finite-difference gradient checks passed. All physical outputs and the 193-element gradient were finite. Maximum absolute log-sensitivity error versus public reference: 5.374104176780747e-06.
- Full saved-array comparison passed at rtol=1e-7 and absolute allowance=1e-12 times each array's reference scale. Carrier, signal, noise, sensitivity, powers and full gradient all had maximum absolute error 0 and relative L2 error 0. Parameters/frequencies matched exactly. Thus there are no nonzero pointwise relative errors in these compared arrays. Loss was not among saved NPZ comparison keys; the reported loss 9.793036291535532e-08 exactly equals the baseline reports' loss (absolute difference 0).
- Baseline phase reports were found read-only in `/Users/t.betz/tmp/amd-hackathon-results/base{1,2,3}.json`. Their import times were 0.290996524, 0.269085106 and 0.265148256 s. Candidate full import time 0.279067064 s falls within this range; no import-time reduction is demonstrated.
- Candidate full total 36.996297654 s is 1.259232654 s (3.52%) slower than the supplied 35.737065 s baseline median. Queue calibration full total was 36.331948 s, also faster. Compilation/lowering accounts for much of the difference. One full run does not establish causality or a repeatable regression, but the proposed performance benefit is unsupported.
- Decision: reject candidate 1 as a performance improvement. Preserve its validated commit in history; restore the original initializer for the separate numerical experiment. Best measured validated reference remains the unchanged baseline. Candidate 1 is correctness-validated, not a validated gain.

## Candidate 2: contract noise directly with existing adjoint weights

- Candidate SHA: pending supervisor commit. Current parent checkout after supervisor feedback commit: `ad2e4e6b7b44c24a1ea6c8c5e276012573d9eccd`.
- Attribution: `differometor/__init__.py` restored byte-for-byte from the public baseline. The only simulator difference from that baseline is the noise contraction in `differometor/simulate.py`; the rejected import experiment is not combined with it.
- Actual workload dimensions established from saved output shapes, the fixture and builder: carrier 286 unknowns with one carrier sample; signal 751 unknowns at 101 frequencies. The fixture contains one non-auxiliary `qnoised` and no `qhd`, hence D=1. Builder selection vectors are `(1, 1, 751)`, broadcast selections/weights/sources are `(1, 101, 751)`, signal augmented matrices are `(101, 751, 752)`, and both signal/noise coefficients are `(101, 751, 751)`. Dimensions are traced from source and actual fixture/output evidence, not collected from live intermediate arrays.
- The detector `vmap` shares the coefficient matrix, but D=1 means there are no multiple detector right-hand sides to consolidate in this benchmark. The signal solve and final noise covariance solve use the same A; the adjoint noise solve uses A^H.
- Inspected the evaluator-version [JAX 0.9.0 solve source](https://raw.githubusercontent.com/jax-ml/jax/jax-v0.9.0/jax/_src/lax/linalg.py), `_solve` lines 2450–2470: LU is computed from stop-gradient A and reused by `custom_linear_solve` for derivatives; matrix RHS columns are mapped after LU. Thus nested `vmap` is not evidence of repeated LU. Actual optimized HLO and cross-call common-subexpression elimination have NOT been inspected; no claim is made that the final A factorization survives separately. The fixed remote environment is available only through the supervisor, and no independent remote/local simulator evaluation was started.
- A simpler avoidable operation is explicit in the current code: its final covariance solve exists only to evaluate one scalar contraction. Let A be the complex signal matrix, d the detector selection, N the noise source matrix, w=A^(-H)d, and z=Nw. The old scalar is Re(d^H A^(-1) z). Since d^H A^(-1)=(A^(-H)d)^H=w^H, it equals Re(w^H z). This holds for general nonsingular complex A and does not assume Hermitian N. The change substitutes the existing weights in the contraction and removes the covariance solve, retaining all source terms and the same final ASD normalization.
- Hypothesis: removing that primal solve and its automatic-differentiation work reduces lowering/compilation, execution and saved residual costs even if A's LU is already shared. This is not a claim of one fewer LU or a measured speedup. Measured candidate 1 forward/gradient execution (12.145592/2.959628 s) and compilation (13.498422/5.032317 s) justify testing work removal in this path.
- No custom derivative, sparse solve, environment change, reduced frequency/parameter workload, or benchmark change. JAX differentiates the rewritten ordinary operations using its existing rules.
- Independent local algebra check used Python complex arithmetic with pivoted Gaussian elimination on 50 deterministic nonsingular complex 3x3 systems, including non-Hermitian N. Maximum old/new scalar absolute difference: 5.551115123125783e-17. Central finite differences across all real and imaginary coordinates of A, N and d (2100 coordinate checks, step 1e-4) differed by at most 8.326672684688674e-13. Syntax checks passed. This checks the conjugation identity, not JAX autodiff, conditioning of the optical system or the official workload.
- Screen/full IDs, exact candidate SHA, timings and all physical/gradient array errors: pending. Reject or revise if strict comparisons fail; algebraic equivalence does not guarantee acceptable floating-point errors.

## Handoff / precise next action

Supervisor should commit and screen candidate 2, then fully validate that same SHA if eligible. Return all phase timings, RSS, full official check results, saved-array comparison and reported loss. Inspect carrier, signal, noise, sensitivity, powers and all 193 gradients. The existing comparison records maximum absolute and relative L2 errors, not maximum pointwise relative error; a numerical candidate also needs maximum pointwise relative errors (with explicit zero-reference handling) from the saved arrays, and loss comparison against the baseline report. Do not modify the protected comparator to obtain those supplemental diagnostics.

Actual compiled lowering remains an open diagnostic for any later explicit factorization-reuse proposal. Candidate 2 is justified independently by eliminating a solve via an exact scalar identity. If candidate 2 fails numerical checks, preserve its failure and inspect the affected arrays before choosing the next revision. The original baseline remains best validated; no improvement has yet been measured. Submission ownership remains with the supervisor, and the worktree/branch/session label above remain unchanged.
