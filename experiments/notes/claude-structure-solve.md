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
- SHA `4c12600ce07d6d46518c230bae17248d9df75a39`.
- Screen `5b2c3e3993814b98ad2eb1d9ec40e8c2` (request `7a3a21850e994055ae5e29aa1664bf7e`): first run
  22.507 s; forward exec 8.559; gradient exec 1.643; RSS 8133252 KiB.
- Full `2183e6e63bcd4e9aa91e6e7313ad6107` (request `33bd66b4fcfc4e57b306a9aa1c1abaa7`): **official
  PASS, strict PASS (validated)**. First run 22.494883 s (parent 23.840, −1.345 s, −5.6%; single run,
  no paired repeat). Phases: imports 0.291, build 0.827, forward lower 0.855 / compile 7.762, forward
  exec 8.545 (cand. 6: 9.305), sensitivity lower 0.093 / compile 0.342, gradient lower 0.206 / compile
  1.899, gradient exec 1.668 (cand. 6: 2.117). Compile/lower total 11.157 (cand. 6: 11.018, ≈ equal).
  Warm median 10.809 s (cand. 6: 12.394; warm forward 8.996, gradient 1.638). Peak RSS 8131196 KiB
  (cand. 6: 10798984, −25%). Job wall 88.98 s.
- Comparison: carrier/signal/noise/sensitivity/powers bitwise identical (max abs 0). Gradient max abs
  8.08e-10, rel L2 1.23e-14, max normalized 2.2e-6, zero failures (cand. 6: 4.5e-13). Official FD
  spot check passed (autodiff 7.61617e-5).
- Interpretation: the forward-exec drop (−0.76 s) and reverse drop (−0.45 s) and lower memory show the
  two separate A-solves were **not** fully deduplicated before (consistent with one LU and one set of
  residuals removed; HLO not inspected, so the exact mechanism is inferred). Compile time is unchanged.

## Candidate 2 — candidate 1 + slice-based conjugation of the static sideband blocks
- Change: new constant `SLICE_CONJUGATION = True` in `_assemble_signal_and_noise`; the two
  conjugated static blocks (rows [cs,2cs) × cols [cs, n+1) incl. RHS; rows [2cs, n) × cols [0, cs))
  are conjugated with `.at[...].set(conj(slice))` instead of `where(mask, conj(M), M)` over the whole
  (1, 751, 752) matrix. Value-exact; reverse is copy/conj only (no additions), so gradient should be
  bitwise equal to candidate 1. `False` restores the mask path.
- Hypothesis: small saving in the per-frequency assembly loop (no full-matrix conj+select, no mask
  iota/compare) in forward and reverse; expected ≤0.2 s, possibly within noise. Unmeasured.
- SHA `39b23e3c6e84b2a7498c7bce932a2f6ba41f227e`.
- Screen `d45bc12dcf0a4bdcac51dac0f9bbed3f` (request `ee7e4b04aa4e49a58f533e30eb8128cf`): first run
  23.133 s.
- Full `4cc17640e44446f887b613d035af7125` (request `091b607bb7a24bfeb0ae46f5c689a312`): **official
  PASS, strict PASS**. First run 22.793836 s (cand. 1: 22.495, +0.30 s). Imports 0.289, build 0.831,
  forward lower 0.836 / compile 7.755, forward exec 8.618, gradient lower 0.184 / compile 1.972,
  gradient exec 1.864 (cand. 1: 1.668). Warm median 10.668 s (forward 8.607, gradient 1.850 vs cand. 1
  1.638 — consistent across all 3 repeats). RSS 8132756 KiB. Wall 90.35 s.
- Comparison: gradient bitwise identical to candidate 1 (max abs 8.076e-10, same rel L2) as predicted.
- **Hypothesis rejected (timing)**: slice updates are slower in reverse (~+0.2 s; likely the two
  dynamic-update-slice transposes produce extra full-matrix copies vs one fused select). Decision:
  `SLICE_CONJUGATION = False`.

## Candidate 3 — candidate 1 code path restored (repeat measurement)
- Change: `SLICE_CONJUGATION = False` only; executed code path equals candidate 1 (`4c12600`).
- Purpose: second full first-run sample for candidate 1's computation; branch head on best validated
  configuration. Expectation ≈22.5 s, gradient identical to cand. 1 (8.08e-10 max abs). Not a new idea.
- SHA / runs: pending.

## Final handoff
- **Best fully validated: candidate 1 `4c12600ce07d6d46518c230bae17248d9df75a39`** — 22.495 s first
  run vs parent 23.840 s (−1.35 s), official + strict pass, outputs bitwise exact, RSS −25%. One full
  run; candidate 3 repeats the same computation.
- Failed/rejected: slice conjugation (strict-safe, slower). Not attempted (strict risk / time): shared
  LU for A^H, Schur/block elimination, BTF permutation, constant-equation elimination.
- Remaining uncertainty: run-to-run variance (need ≥3 paired repeats vs parent); mechanism (duplicate
  LU vs residual savings) not confirmed by HLO; untested with FREQUENCY_CHUNK_SIZE=None or solve-in-loop
  scopes; D>1 detectors untested (code is general).
- Suggested next experiment: paired repeats of 4c12600 vs d09dc1d; then HLO dump count of getrf/trsm
  calls to confirm the mechanism; combine with the other worker's noise-construction change only
  after both validate separately (no assumed additivity).

## Proposed operators
```json
[
  {
    "name": "merge_same_matrix_solves",
    "symbol": "differometor.simulate.MERGE_SAME_MATRIX_SOLVES",
    "file": "differometor/simulate.py",
    "function": "_solve_signal_and_noise",
    "legal_values": [false, true],
    "safe_default": false,
    "recommended": true,
    "conditions": "trace-time constant; validated with FREQUENCY_CHUNK_SIZE=1, FREQUENCY_LOOP_SCOPE='assemble' (solves full-vmap)",
    "invalid_combinations": "untested with solve-in-loop scopes ('solve', 'signal_noise'), with FREQUENCY_CHUNK_SIZE=None, and with any shared-LU(A/A^H)/Schur rewrite",
    "candidate_sha": "4c12600ce07d6d46518c230bae17248d9df75a39",
    "status": "validated (one full run: official+strict pass, 22.495 s)"
  },
  {
    "name": "slice_conjugation",
    "symbol": "differometor.simulate.SLICE_CONJUGATION",
    "file": "differometor/simulate.py",
    "function": "_assemble_signal_and_noise",
    "legal_values": [false, true],
    "safe_default": false,
    "conditions": "trace-time constant; exact transformation, any loop scope",
    "invalid_combinations": "none known",
    "candidate_sha": "39b23e3c6e84b2a7498c7bce932a2f6ba41f227e",
    "status": "validated but slower (22.794 s); do not admit — recommend fixed false"
  }
]
```
