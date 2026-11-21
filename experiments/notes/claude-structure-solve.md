# claude-structure-solve: bounded structural optimization

## Ancestry
- Branch `explore/claude-structure-solve`; scientific parent `d09dc1d08fb046d08b3b699685d8ff780d611e87`
  (frequency-batching candidate 8, k=1 scope "assemble"). Parent full job
  `0c413080dbce47fd80211ca9525a3a89`: official + strict pass, first run 23.840 s (candidate 6 `1d5a796f`
  same code: 23.558 s). Not paired repeats.
- Deadline 1795288990 UTC; session started with ~2230 s remaining.

## Structural audit (source-based, no HLO/measurements available in this session)
- Signal matrix A (n≈751 per frequency, 101 frequencies). Per frequency the parent issues three dense
  solves: `solve(A, b)` (signal), `solve(A^H, s_d)` (noise weights), `solve(A, N w_d)` (covariances).
  Each `jnp.linalg.solve` call carries its own `lu(stop_gradient(A))` + `custom_linear_solve`.
- Whether XLA CSE already merges the two identical LU custom calls on A is **unknown** (not
  verified by HLO). If not, the parent does 3 LUs per frequency; if yes, 2.
- Rejected inside lane (time + strict risk): sharing LU(A) for the A^H solve (prior shared-LU failed
  strict on 3 gradients: indices 33, 161, 180); Schur/block elimination over upper/lower/mechanical
  blocks (prior Schur failed strict; also any permutation changes LAPACK pivot order and therefore
  rounding, and index 161 is sensitive at the ~1e-9 rel-L2 level per frequency-batching candidates
  1–4); BTF/constant-equation elimination (needs host-side structural analysis of matrix indices and
  proof that eliminated rows are constant identity rows — unverifiable without running code in this
  restricted session; would also change pivoting).

## Candidate 1 — merge the two same-matrix (A, untransposed) solves into one multi-RHS solve
- Change (`differometor/simulate.py`, `_solve_signal_and_noise`, new constant
  `MERGE_SAME_MATRIX_SOLVES = True`): RHS columns `[b, N w_0..N w_{D-1}]` → one
  `solve(A, (B, n, 1+D))`. A^H noise-weight solve unchanged and still first. Assembly loop (k=1,
  "assemble") unchanged. `False` restores parent code path exactly.
- Hypothesis: one guaranteed LU(A) per frequency (saves one LU per frequency if XLA did not CSE),
  one `custom_linear_solve` instead of two → fewer triangular-solve custom calls in forward and
  reverse, slightly less compile. Numerics: same LU, same pivots; only multi-column vs single-column
  triangular solves and the association of A's cotangent contributions (λ_b x_b^T + Σ λ_d x_d^T as one
  contraction) change — rounding-level, analogous to frequency-batching candidate 7 which passed strict
  (max normalized 6e-7). Risk: index 161 strict sensitivity. Expected gain unmeasured; could be ~0 if
  LU was already CSE'd.
- SHA / runs: pending (supervisor).

## Proposed operator (draft; evidence pending)
```json
{
  "name": "merge_same_matrix_solves",
  "symbol": "differometor.simulate.MERGE_SAME_MATRIX_SOLVES",
  "file": "differometor/simulate.py",
  "function": "_solve_signal_and_noise",
  "legal_values": [false, true],
  "safe_default": false,
  "conditions": "trace-time constant; independent of FREQUENCY_CHUNK_SIZE/SCOPE when solves are full-vmap (scope 'assemble' or None)",
  "invalid_combinations": "untested with solve-in-loop scopes ('solve', 'signal_noise') and with any shared-LU/Schur rewrite",
  "candidate_sha": "pending",
  "status": "unvalidated"
}
```
