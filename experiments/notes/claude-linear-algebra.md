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
| 1 | (assigned by supervisor) | Share one LU(A) across signal, A^H noise-weight and covariance solves | pending | pending | pending |

Candidate 1 implementation (`differometor/simulate.py`): adds `lu_factor`, `_lu_solve` (public `lax.linalg.triangular_solve`, trans 0/1/2) and `solve_factored` (`lax.custom_linear_solve`). `simulate` now factors `signal_matrix[:, :, :-1]` once and uses those factors for all three signal-system solves. The explicit `A^H` copy is removed. The carrier solve and the public `solve` function are unchanged. I have not executed this code locally: no runtime is available in this launcher. Possible failure modes to check in the screening run are tracing errors in the `custom_linear_solve` batching, and gradient mismatches, which would point to the transpose convention.

Next decision: if the screen passes, compare the noise/sensitivity/gradient arrays against the baseline and request full validation. If the forward-stage time does not drop, the HLO getrf count diagnostic decides whether the baseline was already sharing factors. If it helps, the block/Schur decomposition is the next candidate.
