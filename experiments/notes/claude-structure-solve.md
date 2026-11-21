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
- SHA `3e94580ec44609e7156f7f0acad1f2884db8b030`. Screen `e61db6fefd344eab8d45592b009a7dcf` 22.333 s.
  Full `0e841841f0bc491fa29b6178a908ef4c` (request `2f21c93109ea45bd92fbfa8466e405c4`): **official PASS,
  strict PASS**. First run 22.423 s (cand. 1: 22.495); forward lower 0.837 / compile 7.661, forward exec
  8.602, gradient compile 1.804, gradient exec 1.665; compile/lower total 11.034; warm median 10.841 s;
  RSS 8135116 KiB; wall 89.12 s. Gradient identical to cand. 1 (max abs 8.076e-10).
- Two full samples of the merged-RHS computation: 22.495 / 22.423 s (parent 23.840, single sample).

## Candidate 4 — split coefficients/RHS inside the assembly loop (coordinator follow-up)
- Source analysis: with scope "assemble", `_map_row_chunks` stacks the augmented (101, 751, 752)
  signal blocks (~0.91 GB). `_solve_signal_and_noise` then takes `[:, :, :-1]` (a non-contiguous slice
  → full copy for LU / A^H transpose) and `[:, :, -1:]`. In reverse, the slice transpose is a pad of the
  cotangent to (101, 751, 752) before entering the reverse scan.
- Change: `SPLIT_SIGNAL_RHS = True` — the loop body returns `M[:, :, :-1]`, `M[:, :, -1]` and noise; the
  stacked coefficients (101, 751, 751) and RHS (101, 751) feed `_solve_signal_and_noise(…, signal_rhs)`
  directly. Exact slicing; A cotangent contributions (merged solve + A^H path) are still summed at top
  level exactly as before, and pad/concat into the per-row augmented cotangent happens per frequency
  (disjoint entries, no additions) → gradient expected bitwise equal to candidate 1.
- Hypothesis: removes one full-stack strided copy in forward and one full-stack pad in reverse (if XLA
  had not already fused them); expected small saving (≤0.3 s), possibly zero. Unmeasured.
- SHA `423bcc4ad6e99b85cd651980bee541612ed2ee20`. Screen `c068a2f99ce54aafbeb8dabbd6122470` 22.285 s.
  Full `4ace8bcd73364c7cbde02c8dc9c1de16` (request `3a4d057301fe40afad9a36c26aa2ec15`): **official PASS,
  strict PASS**. First run 22.360748 s; build 0.831; forward lower 0.831 / compile 7.749; forward exec
  8.522; gradient lower 0.182 / compile 1.876; gradient exec 1.701; compile/lower 11.013; warm median
  10.736 s (forward 8.965, gradient 1.657); RSS 8131440 KiB; wall 87.84 s.
- Comparison: outputs bitwise exact; gradient max abs 7.57e-10, rel L2 1.14e-14, max normalized 1.10e-6.
  **The bitwise-equal-gradient prediction was wrong**: gradient differs from candidate 1 (8.08e-10) at
  rounding level. Cause not identified (HLO not inspected); no attribution claimed.
- Timing: 22.361 s vs candidate 1/3 samples 22.495 / 22.423 — within the observed spread; no
  superiority claim. Neutral, strict-safe layout change.

## FINAL SOURCE AUDIT (notes only; source unchanged after 423bcc4)

Established from source reading (not executed):
1. **Merged RHS shapes, D detectors.** `noise_sources` is (D, B, N); `moveaxis(…, 0, 2)` → (B, N, D);
   concat with `signal_rhs[:, :, None]` (B, N, 1) → (B, N, 1+D). `jnp.linalg.solve(a (B,N,N), b (B,N,1+D))`
   treats b as a matrix RHS because b.ndim == a.ndim and b.shape != a.shape[:-1]. Column 0 → signal
   (B, N); columns 1: → `moveaxis(…, 2, 0)` → (D, B, N) = old `covariances` layout. Correct for any D≥1.
   Proof obligation for D=0: concat of (B,N,1) with (B,N,0) is valid, covariances (0,B,N), noise (0,B);
   the parent path with vmap over a size-0 axis is likewise degenerate. Untested.
2. **Carrier batch > 1** (`carrier.shape[0] != 1`) takes the full-vmap branch with the legacy caller
   (`signal_rhs=None` → slices of the augmented matrix); only the merged solve applies. Shapes unchanged
   from the parent apart from (1). Untested by the benchmark (carrier batch is 1).
3. **FREQUENCY_CHUNK_SIZE None / count ≤ k / scopes "solve", "signal_noise"** use the legacy augmented
   caller; SPLIT_SIGNAL_RHS has no effect there. In "solve"/"signal_noise" the merged solve runs inside
   the scan — that combination was never evaluated (earlier scan-solve variants failed strict).
4. **Partial chunks (k ∤ 101).** `_map_row_chunks` pads by repeating the last row, and each output is
   reshaped (C, k, …) → (C·k, …)[:count]. That is valid for the 3-tuple output: coefficients (C,k,N,N),
   RHS (C,k,N) and noise (C,k,NN,NN). Padded rows receive zero cotangent. Only k=1 (no padding) is exercised.
5. **component_groups None vs grouped**: assembly code is identical for both; the split happens after
   `assemble`, so neither path is affected. The benchmark exercises the grouped path only.
6. **Dependency paths**: A feeds (a) the merged solve (matvec of custom_linear_solve) and (b) the A^H
   noise-weight solve; RHS feeds only the merged solve; the noise matrix feeds only `noise_sources`. All are
   preserved, and no parameter dependence is dropped (slicing only). `signal_matrix = None` inside
   `_solve_signal_and_noise` only rebinds a local name.
7. **Not established**: whether the benchmark's improvement comes from one fewer LU or from fewer residuals
   (no HLO evidence), and why the 423bcc4 gradient differs from 4c12600 at the 1e-10 level.

Exercised by the full benchmark: D=1, carrier batch 1, k=1, scope "assemble", grouped components,
101 frequencies, uifo_800_3000 setup.

Test plan (proposed, not run):
- T1 shapes: a synthetic setup with 2 detectors (e.g. two QHDs). Compare MERGE_SAME_MATRIX_SOLVES True vs
  False: signal identical (max abs ≤ 1e-12 relative), noise (2, B) agreeing to ≤1e-12 relative.
- T2 carrier sweep: `run_setups`-style with changing carrier parameter values (CV=3) → full-vmap branch;
  compare merged vs unmerged outputs and `jax.grad` of sum(log noise).
- T3 chunk padding: FREQUENCY_CHUNK_SIZE ∈ {2, 4, 8} with scope "assemble", SPLIT True vs False; outputs
  bitwise equal, gradients within strict tolerance; check shape (N, 101) and (D, 101).
- T4 component_groups=None: pass `component_groups=None` to `simulate`; compare to grouped.
- T5 directional derivative: 3 random dimensionless directions, central differences with a step sweep,
  for merged vs parent (audit protocol), focusing on indices 33, 161, 180.

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
  },
  {
    "name": "split_signal_rhs",
    "symbol": "differometor.simulate.SPLIT_SIGNAL_RHS",
    "file": "differometor/simulate.py",
    "function": "simulate (scope 'assemble' branch), _solve_signal_and_noise(signal_rhs=)",
    "legal_values": [false, true],
    "safe_default": false,
    "conditions": "only active with FREQUENCY_CHUNK_SIZE not None and FREQUENCY_LOOP_SCOPE='assemble'; exact layout change",
    "invalid_combinations": "no effect for other scopes",
    "candidate_sha": "423bcc4ad6e99b85cd651980bee541612ed2ee20",
    "status": "validated (22.361 s, official+strict pass); timing neutral within spread, gradient not bitwise equal to merge-only"
  }
]
```
