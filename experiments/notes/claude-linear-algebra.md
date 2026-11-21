# Claude linear algebra investigation

- Branch: `explore/linear-algebra-audit`, starting commit `84754db` (unchanged simulator from `main` plus lab infrastructure). No seed-agent changes are included.
- Agent: Claude Opus 5.5 (`claude-opus-5-5`), supervised session. This launcher has file tools only: I ran no Python, JAX or HLO tooling. **Nothing below is a measurement unless it cites a run identifier.** Every count is inferred from reading the source and the benchmark brief.

## 1. Dimensions and structure (from source, not measured)

Sizes come from the brief (carrier output (286,1), signal (751,101)) together with `differometor/build.py:650-663`:

- Carrier system: `CN = system_size = 286`. The augmented matrix is (286, 287), one parameter row (`CV = 1`).
- Signal system: `SN = 2*CN + signal_size = 751`, so `signal_size = 179`. The augmented matrix is (751, 752), batched over 101 frequencies.
- Noise matrix: (751, 751) per frequency (`build.py:663`). Selection vectors are (D, 1, 751). The brief says D = 1, which I have not verified at runtime; `quantum_detector_number` comes from the fixture.

The signal matrix has this block structure, from `build.py:1373-1374` and `simulate.py:323-333`:

```
        [ C        0        X  ]   rows 0..285     (upper sideband = carrier pattern)
  A  =  [ 0        conj(C') conj(X') ]   rows 286..571 (lower sideband, conjugated)
        [ Y        conj(Y') M  ]   rows 572..750   (signal/mechanical nodes)
```

`C` starts from the carrier pattern: identity plus component couplings written by `update`. `X` holds the laser/space modulation connector columns (`build.py:1039,1340`), which are scaled by the carrier solution (`simulate.py:315-321`).

- **Always-zero blocks:** the (0,1) and (1,0) off-diagonal sideband blocks never receive a write in the build or update paths I read. They are structural zeros for every parameter value.
- **Parameter-dependent entries:** the entries written by `update` (`matrix_indices`) and the connector entries. Some of these can be zero at the starting parameters (for example a zero tuning or a reflectivity bound) but still carry gradient. Any sparsity pattern must come from the union of the `*_matrix_indices` and the base identity, not from the nonzeros of one evaluated matrix.
- **Not measured:** actual nnz counts and the fill-in under partial pivoting. The next diagnostic would compute `len(unique(signal_matrix_indices)) + 751` over the built arrays, plus the nnz of `C`. Rough expectation: a few thousand entries out of 564,001, which would be well under 1% dense. That is an estimate, not a fact.

## 2. Factorization use in the current code (source trace)

`simulate.solve` calls `jnp.linalg.solve`. The installed JAX implementation is `lax_linalg._solve`: it runs `lu(stop_gradient(a))` and wraps the result in `custom_linear_solve`, so that transpose solves reuse the same LU during differentiation. Per frequency, the forward pass contains these 751×751 complex factorizations:

1. `signal = solve(A, rhs)`: LU(A).
2. `noise_weights = solve(A^H, carrier_selections)`: LU(A^H), computed from an explicitly materialized `transposed_conjugated_signal_matrix` (101×751×751 complex, about 0.91 GB). **This is a separate factorization of a different matrix, and XLA CSE cannot merge it with (1).**
3. `covariances = solve(A, noise_sources)`: LU(A) again. This could be CSE-merged with (1) because the operand is the identical slice and the LAPACK getrf custom call has no side effects, but whether that happens is **unverified without HLO**.

So the forward pass performs either 2 or 3 LU batches of 101 × (751³ complex). The backward pass uses only triangular solves from the saved factors. Under `jax.vjp`, the residuals include each LU (about 0.91 GB each) and the materialized `A^H`.

Mathematics of sharing: if `P A = L U` (JAX's `lax.linalg.lu` returns a permutation with `A[perm] = L U`), then `A^H = U^H L^H P`. Solving `A^H x = b` therefore takes two conjugate-transposed triangular solves followed by an inverse permutation. It costs O(n²) per right-hand side, compared with O(n³) for a new factorization.

Rough cost estimate, not measured: one batch of 101 complex LUs at n = 751 is about 101 × 8/3 × 751³ ≈ 1.1e11 real flops. On one Zen core with LAPACK that should take several seconds, which is a meaningful share of the roughly 15.5 s warm time.

## 3. Proposal: explicit factorization sharing (selected candidate)

Factor `A` once per frequency with `lax.linalg.lu(stop_gradient(A))`. Run all three signal-system solves through `lax.custom_linear_solve` using those factors:

- signal and covariance solves: `matvec = A x`, `solve` uses trans=0 and `transpose_solve` uses trans=1. This matches JAX's own `_solve`.
- noise-weight solve with `M = A^H`: `matvec = conj(A)^T x`, and `solve` uses trans=2 (conjugate transpose) on LU(A). `transpose_solve` must solve `M^T y = conj(A) y = b`. It is computed as `conj(lu_solve_trans0(conj(b)))`, which is complex-linear in `b`, as `custom_linear_solve` requires.

Derivative correctness: the linear operator and its JVP and transpose are mathematically identical to the original. Only the inner solve differs: a different pivot sequence for the A^H system. The factors are stop-gradient'd exactly as in `jnp.linalg.solve`. Gradients with respect to `A` still flow through `matvec`, as before.

Expected effects (hypotheses):

- One fewer LU batch in the forward stage (guaranteed for the A^H system, and it also removes any reliance on CSE for (1) vs (3)).
- About 0.9–1.8 GB smaller AD residual footprint: one LU and the materialized A^H are no longer saved.
- A slightly smaller forward HLO. Compile time should change little; the gradient stage still contains only triangular solves.
- Numerics: rounding-level differences in `noise`, `sensitivity`, `loss` and the gradient. `carrier` and `signal` should be bitwise identical or nearly so, because the same getrf runs on the same matrix.

Alternatives considered and deferred:

- **Block or Schur decomposition** on the 572 sideband rows plus 179 signal rows: the (0,1) and (1,0) blocks are structurally zero, so the sideband blocks decouple except through the 179-row coupling. This would need two LUs of 286 plus a 179 Schur complement, but correct conjugation handling and gradients make it a bigger rewrite. Consider it after measuring candidate 1.
- **Sparse solves (SciPy callback or custom sparse LU):** these need measured nnz, fill-in and the callback/VJP cost first. Host callbacks would also add copies and break XLA fusion. Not justified without measured sparsity.

## Compiled diagnostics still needed (queued follow-up, not run)

1. Count of `lapack_zgetrf` custom calls (and their shapes) in the optimized HLO of the forward stage, for both baseline and candidate. This shows whether baseline (1) and (3) were already CSE-merged.
2. Forward-stage peak RSS and residual size, baseline vs candidate.
3. Runtime nnz of the signal matrix (union of write indices) and of its LU factors, if a sparse or block direction is pursued.

## Candidate log

| # | SHA | Hypothesis | Runs | Result | Decision |
|---|-----|-----------|------|--------|----------|
| 1 | `3db9b657f8496d40a9f195fd9864e5e048c7df5b` | Share one LU(A) across signal, A^H noise-weight and covariance solves | screen `af18c37444224d31a69ced471361ef2d`, full `cd271462a63446a997264fb26882b711` | Official pass; strict array check FAILED (3 gradient entries) | Keep as speed evidence; numerical review needed |
| 2 | `0ed67104f64ad82059b3465d20e56489762b4312` | Block/Schur factorization of A using structurally zero sideband cross blocks | screen `be819ed2f7d94e859c762f85a57d8665`, full `99b1182cb5bc4d178563a06507da4010` | Official pass; strict FAILED (signal, noise, sensitivity, gradient) | **Rejected** |
| 3 | (assigned by supervisor) | Revert to candidate 1's dense shared-LU solver (repeat measurement / branch head = best config) | pending | pending | pending |

### Candidate 2 measured results and rejection

- First run: screen 32.139 s, full 31.239 s. Candidate 1 measured 31.429 and 31.509 s. There is no reliable first-run gain.
- Warm median 9.534 s vs 10.876 s, a −1.34 s gain: forward 6.75 s vs 7.94 s, gradient 2.62 s vs 2.74 s.
- Compile grew: forward compile 13.66 to 14.26 s vs 12.97 s; gradient compile 5.07 s vs 4.73 s; total trace+compile 20.75 s vs 19.66 s. The larger compile time cancelled the runtime saving in the first-run metric.
- Peak RSS 12.25 GB.
- Numerics got about 10–100× worse than candidate 1, which is consistent with losing global pivoting:
  - signal relative L2 error 2.6e-6, with 5644 failing entries (max normalized error 400);
  - noise relative L2 error 1.7e-6, 60 failing entries;
  - sensitivity: 4 failing entries;
  - gradient relative L2 error 1.1e-7, 9 failing entries, with idx 161 at relative 6.4e-6.
- The official checks still passed: |Δlog sens| 5.372e-6, and the FD check passed.
- Decision: reject. The structural-zero claim is consistent with the outputs, which were correct to about 1e-6, but the block route trades accuracy and compile time for a warm-runtime gain that the first-run metric does not reward.

### Candidate 1 measured results

Results from full run `cd271462…`, single runs on AMD EPYC 9334 pinned to CPU 2:

- **First run 31.509 s** (screen run: 31.429 s), vs the 35.737 s baseline median: −4.2 s (−11.8%).
- Warm runtime median 10.876 s (forward 7.94 s, gradient 2.74 s), vs the baseline warm ~15.5–15.7 s.
- Compile: forward 12.97 s, gradient 4.73 s, trace/lower+compile 19.66 s in total. I have no baseline per-phase compile numbers in hand, so the phase-by-phase compile comparison is still open.
- Peak RSS 12.48 GB (GNU time).
- Official checks passed: max |Δlog sens| 5.37e-6 (limit 1e-5); FD gradient check passed for mb11.tuning.
- Strict comparison (rtol 1e-7): carrier, signal and powers were **bitwise identical**. Noise had relative L2 error 2.2e-8 and passed. The gradient FAILED at 3 of 193 entries: idx 33 (rel 3.1e-7), idx 161 (rel 1.5e-6), idx 180 (rel 2.3e-7). Gradient relative L2 error was 3.85e-8 and loss 9.745414349309313e-08.
- Interpretation: the expected mechanism is the pivoting change, since A^H is now solved via LU(A)^H instead of LU(A^H). The sensitive entries suggest an ill-conditioned noise path. The official FD estimates themselves disagree between step sizes at the 2.6e-3 relative level, far above these diffs. Whether 1.5e-6 relative gradient drift is acceptable is a **maintainer decision**. The candidate does not pass the lab's strict check as is.

Candidate 1 implementation (`differometor/simulate.py`): adds `lu_factor`, `_lu_solve` (public `lax.linalg.triangular_solve`, trans 0/1/2) and `solve_factored` (`lax.custom_linear_solve`). `simulate` now factors `signal_matrix[:, :, :-1]` once and uses those factors for all three signal-system solves. The explicit `A^H` copy is removed. The carrier solve and the public `solve` function are unchanged. I have not executed this code locally: no runtime is available in this launcher. Possible failure modes to check in the screening run are tracing errors in the `custom_linear_solve` batching, and gradient mismatches, which would point to the transpose convention.

### Candidate 2 (built on candidate 1)

Source evidence for the structural zeros: `set_instructions` (`build.py:177-266`) duplicates carrier-block signal entries only diagonally (r+N, c+N). Mixed entries go to rows/columns ≥ 2N. The base is identity plus carrier copies on both diagonal blocks (`build.py:1373-1374`), and space writes are block-diagonal pairs. The squeezer cross-sideband entries (`build.py:813-825`) go only to `noise_instructions`. So `A[:N, N:2N]` and `A[N:2N, :N]` are zero for every parameter value. I have not verified this at runtime.

Change: `block_factor` computes LU(B1), LU(B2) (286×286), W = P⁻¹Q (572×179), S = M − R W and LU(S) (179×179). `_block_solve` solves trans 0/1/2 via A = [[P,0],[R,S]]·[[I,W],[0,I]]. The `custom_linear_solve` wrapper, matvec and derivative structure are unchanged from candidate 1.

Rough flop estimate per frequency (not measured): 2·(286³·2/3) + 2·286²·179·2 + 179·572·179 + 179³·2/3 ≈ 1.1e8 complex FMA, vs 2.8e8 for one 751 LU. Candidate 1 suggests one 751-LU batch costs about 4.5 s, so this could save roughly 2–3 s of forward time if LAPACK efficiency at the smaller sizes holds up.

Numerical risk: pivoting is now restricted to within blocks (B1, B2, S), so a nearly singular B1/B2 or S would amplify error. Expect larger output differences than candidate 1. The official log-sensitivity margin is 5.37e-6 of 1e-5 (dominated by the reference itself). If the screen fails the sensitivity check, or noise/gradient diffs grow by orders of magnitude, reject the candidate and revert to candidate 1.

## Handoff (end of the linear-algebra session)

- **Best result:** candidate 1, the shared dense LU(A) with A^H solved via LU(A)^H. First run 31.43 s (screen) and 31.51 s (full), vs the 35.74 s baseline median. Official checks passed. Strict array check failed only on 3 gradient entries, max relative 1.5e-6. It is **not validated** under the lab's strict rule until the maintainer accepts that tolerance or changes the criterion.
- Candidate 3 restores the candidate 1 solver so the branch head is the best configuration and gets a repeat measurement. The only code difference from candidate 1 is that `_lu_solve` also accepts matrix right-hand sides, and the vector path is unchanged.
- Candidate 1 changes only the linear-algebra path, so it is likely orthogonal to the seed agent's candidate 5 (scalar dispatch and conjugation, 28.97 s). The combination must be measured, not assumed additive. `simulate.py` overlaps near the conjugation block, so the merge needs care.
- Compile now dominates: ~13 s forward and ~4.7 s gradient out of ~31.5 s. Further linear-algebra runtime work (block, sparse) has low first-run leverage unless it also cuts compile time.
- Open diagnostics (need queued, authorized runs): count of zgetrf calls in the baseline HLO (did CSE merge (1) and (3)?), a forward compile-time breakdown by op, and runtime nnz of the signal matrix.
- Not pursued: sparse solves. With compile dominant and candidate 2's experience, host-callback or sparse-LU cost is unlikely to pay off in first-run time.

Earlier next-decision text (historical): if the screen passes, compare the noise/sensitivity/gradient arrays against the baseline and request full validation. If the forward-stage time does not drop, the HLO getrf count diagnostic decides whether the baseline was already sharing factors. If it helps, the block/Schur decomposition is the next candidate.
