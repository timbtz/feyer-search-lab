# Critical review: teammate host engine and internal sparse solver

Source: [akshat-bhat/Feyer at de67f012553d00621fc25404ddecde33e2318493](https://github.com/akshat-bhat/Feyer/tree/de67f012553d00621fc25404ddecde33e2318493). Last simulator change: 8d39af76ffce6d3e92e949c621ceac8e578f6b05. Reviewed 21 November 2026.

## Independent result

The sub-second result is feasible and independently reproduced on the supplied workload. It is not a certified general-purpose replacement or a repeat-confirmed winner. The unchanged official benchmark passes; the team's additional strict comparison fails.

Imported candidate e2fd659e6f426289c526f79ae758bed4182879a9 has simulator files byte-identical to the reviewed source. Trusted full job fd0afab1916546eea718f9bfeb261947 measured **0.781889 s complete first-run**, **0.234269 s lowering/compilation**, **0.124100 s median warm execution**, and peak RSS **482596 KiB**. All 101 frequencies, 193 gradients, complex128/float64 outputs, CPU affinity [2], and disabled persistent compilation cache were retained. This is one fresh-process observation with three warm repeats, not three first-run measurements. Quiet-host timing was not independently established.

## Challenge rules versus additional lab policy

The supplied challenge ranks complete first-run time, including setup, all compilation, forward physics, sensitivity, gradients and transfer. It requires the complete setup, double precision, finite results, nonzero gradients, positive reference-matching sensitivity (natural-log error <= 1e-5), and the supplied gradient sanity check. It does not require expensive XLA compilation, dense algebra, GPUs, or second derivatives. CPU callbacks and interpreted NumPy are not inherently disqualifying. All three official JIT stages remain unchanged; callback work is inside their execution timers.

Independent validation: maximum log-sensitivity error **5.374214e-6**, finite physical outputs and gradients, and the two-step finite-difference check passed. That check covers **one coordinate**, mb11.tuning; it does not certify all 193 derivatives.

Our additional comparator uses rtol=1e-7 plus 1e-12 times the reference maximum. It fails **131 signal entries** (worst normalized error **1.511774**) and **3 gradient entries, indices 33, 161, 180** (worst **7.686611**). Sensitivity, noise, carrier, powers and exact inputs pass. Relative L2 gradient difference is **8.722537e-8**. The teammate uses rtol=1e-6 plus 1e-9 times the maximum and a 1e-6 norm check: both pointwise tolerances are looser. A small norm error does not establish correctness of every derivative. Conversely, disagreement with an ill-conditioned baseline does not itself prove wrong physics. Do not silently weaken the lab check or call its failure an organizer disqualification.

## Review findings

1. **Generalization PASS is conditional.** `scripts/check_setups.py` assigns Voyager amplitude/frequency modulation special log-error limits of 1e-4 and **0.5**. The frequency case reports about **0.15** log-sensitivity disagreement and **2.9e-4** gradient norm difference. The submitted engine is reportedly about **9.2e-3** from its own refined reference there. SETUPS PASS therefore does not mean these cases meet the challenge's 1e-5 criterion. They are different setups without the official reference: the original may be worse, but neither is certified by this check. Perturbation timings keep exact-boundary values fixed and do not cover all topology-changing variations.
2. **“Correctly rounded” is unproved.** `scripts/roundoff_study.py` uses eight extended-precision residual corrections and casts back to complex128. It provides no interval/error enclosure or rounding certificate and constructs its reference with the new engine's assembly. This is useful evidence about linear-solve roundoff, not independent proof of the whole physics or correctly rounded gradients. Extended precision is platform-dependent. Call it an “extended-precision refined reference” unless a certificate is added.
3. **API compatibility is narrower.** The CPU callback/custom-VJP engine supplies first-order reverse derivatives, not general Hessian/JVP/GPU behavior. Its real-valued parameter assumptions and interpreter coverage need testing on the actual withheld variant. Those limitations are not automatic benchmark violations. The singular-system safety net is also narrower than the prose: sparse signal factorization handles singularity, while the dense carrier path still calls `numpy.linalg.solve`, which can raise.
4. **Portability remains unverified on the judges' CPU.** `host.py` directly loads the private SciPy `_superlu.gstrf` extension and uses private options. A public `splu` fallback handles loader failure, but private-call compatibility is not established across versions. The 48x AMD ratio is not guaranteed on Intel; compare fresh baseline and candidate under the same environment/core.
5. **Residual reuse is not stored-answer evidence.** Every forward call assembles and solves anew. Small token-indexed caches keep current residuals/factors for the reverse pass and recompute after eviction. No persistent compilation cache or saved workload answers were found in the executed path. However, mutable tokens from `pure_callback` warrant transformation, reentrancy, batching and pullback-after-eviction tests before broad API claims.

## Internal 8-second Claude work

Committed source notes: `explore/claude-sparse-adjoint`, `experiments/notes/claude-sparse-adjoint.md`.

- Candidate **0dea4ec707f970e2003cd8f43fcb629be710d5ac**: screen **b24872db821b4678a6be01a63ff9233c**, **8.524777 s**. This omits official finite-difference and strict full checks. Its own notes reject plain SuperLU after failures on 4/8 setups, including Voyager and uifo_20_5000.
- Candidate **4af20b7baa9e363f46177c92a7b979794032a167** adds iterative refinement. Full jobs **3723bee87d1b4b1a87656141f017dc8f** and **6b9deb9657e64992bf65e562ee77b670** measured **8.639402 s** and **8.634406 s**, both official PASS / strict FAIL. The first spends **7.553893 s** compiling and **0.274052 s** executing forward physics.
- That session found the numerical problem and refinement. The remaining opportunity is removing component-physics compilation: the external engine reduces compilation to 0.234269 s in our run. This explains the gap without assuming that a model generally performs better or worse.

## Before promotion

Keep the fast candidate and failure evidence. Test the actual organizer variant when available, full gradients across well-conditioned perturbations and boundary/topology changes, and discrepant coordinates against an independent high-precision or well-scaled reference. Resolve organizer acceptance if ill-conditioned baseline disagreement matters. Confirm repeated fresh baseline/candidate runs on one quiet host/core/environment, then rerun the exact final submitted SHA. Do not replace first-run time with warm timing, cross-host ratios, or the external comparator.

## Preserved evidence

`experiments/reviews/teammate-host-engine/` contains the independent full job, representative source reports, external ledger, generalization notes and five explicitly external measurement records. The frontend retains compilation phases and source tolerance policies while excluding externally reported results from lab eligibility and ranked deltas. Internal feedback is imported from exact committed artifacts; missing phase declarations, prompts and feedback-delivery receipts remain unknown.
