# claude-profile-guided-v1

- Branch: `explore/claude-profile-guided-v1`. Seed (exact parent): `96474bdd4d83bb02c163640f63fae1c4bd7a21d4`, which is claude-noise-reuse candidate 4: `NOISE_FACTOR_REUSE="direct"`, `NOISE_REUSE_MODE="broadcast"`.
- Model: `claude-opus-5-5`. Managed session: no shell and no local runs; the supervisor commits and evaluates.
- Session identifier: as recorded in the supervisor launch record, which was not shown in the prompt.
- Budget: 3599 s remaining at candidate 1. There is no candidate cap.

## Parent evidence: full job `ab12c14c29354bad9aa6dc024c91f8e6`

- Verdict: official PASS, strict PASS.

| Measure | Value |
| --- | --- |
| Complete first run | 22.366 s |
| Imports | 0.297 s |
| Build | 0.821 s |
| Forward lower | 0.824 s |
| Forward compile | 7.634 s (34.1%) |
| Forward execute | 8.609 s (38.5%) |
| Sensitivity lower + compile | 0.551 s |
| Gradient lower | 0.187 s |
| Gradient compile | 1.962 s (8.8%) |
| Gradient execute | 1.475 s (6.6%) |
| Warm median | 10.609 s (forward 8.936 s, gradient 1.505 s) |
| Job wall time | 88.1 s |
| Peak RSS | 8.13 GB |

- Strict comparison: carrier, signal, noise, sensitivity and powers are bitwise identical (error 0).
- Gradient: max normalized error 6.0e-7, max absolute error 5.1e-10, relative L2 error 7.6e-15.

## Ranked bottleneck (from source run comparisons; these are not operator profiles)

1. **Forward execute (8.61 s).** Candidate 3 (`bb9a183`, full `f62c5c80`) dropped the separate LU of `A^H` and measured 5.17 s forward, but failed strict on the gradient (indices 33, 161 and 180). So the `A^H` LU plus its transpose costs about 3.4 s, measured across two different revisions.
   - Both LUs are locked numerically. Any other factorization of the `A^H` system shifts noise by about 2e-8 relative, and the ill-conditioned gradient coordinates amplify that past the strict limit.
   - Everything else in forward is not attributed: assembly loop, triangular solves, broadcast/residual traffic.
2. **Forward compile (7.63 s).** No operator or HLO attribution is available. A coordinator diagnostic is needed: an HLO size/pass breakdown of the forward vjp.
3. **Gradient compile (1.96 s) and gradient execute (1.47 s).**

## Candidate 1: `NOISE_REUSE_MODE="rowmap"`

### Hypothesis
- **Target:** the forward execute phase (8.61 s, job `ab12c14c`), plus secondarily the gradient phase.
- **Mechanism:** in the parent's `"broadcast"` mode, the single noise matrix N (751×751) is broadcast to (101,751,751) for the batched `bij,bdj` einsum.
  - Candidate 1 → candidate 2 of claude-noise-reuse (`f3139c7` → `e525ee5`) removed that broadcast via a GEMM. It measured −0.9 GB RSS, forward −0.35 s, gradient −0.22 s, compiles −0.2 s and total −0.76 s. Those are single runs, not paired.
  - Candidate 2's GEMM changed rounding: gradient margin 0.949.
- **Change:** `"rowmap"` contracts each row in `lax.map` as `einsum("ij,dj->di", N, W_b)`. Per row, that is the same (751×751)·(751×D) product the batched dot performs per batch element, without the broadcast operand and its residual.
  - The reverse pass accumulates N's cotangent in a scan carry instead of reducing a (101,751,751) outer-product array.
- **Expected:**
  - Lower peak RSS, by up to about 0.9 GB.
  - Forward and gradient execute a few tenths of a second lower.
  - Ceiling: about the 0.76 s measured between noise-reuse candidates 1 and 2. That is an opportunity bound, not a promise.
  - Possible costs: loop overhead, and forward/gradient compile could rise slightly.
- **Numerics:**
  - Forward noise is intended to be bitwise identical, assuming XLA CPU emits the same Eigen matmul per row. This is unverified: if XLA picks a different dot kernel, the noise may round differently.
  - The noise-parameter gradient coordinates change summation order (rows are accumulated sequentially), as in candidate 1 of noise-reuse (passed at 1.6e-8).
- **Fallback:** `NOISE_REUSE_MODE="broadcast"`, which is the parent.

### Results: candidate SHA `b879706b1590bba8dee303c2d82ddbd1493eb48f` — **REJECTED (strict FAIL)**

**Screen** (`00e53390c7674cb7a06120f83631761d`): first run 21.943 s. Provisional.

**Full** (`a6981b9d7ffb4cc4b1bb52bee69cc3e6`): official PASS, **strict FAIL**.

| Phase | Seconds | vs parent |
| --- | --- | --- |
| Complete first run | 22.130 | −0.24 |
| Forward compile | 7.934 | +0.30 |
| Forward execute | 8.208 | −0.40 |
| Gradient compile | 1.977 | — |
| Gradient execute | 1.380 | −0.09 |

- Warm median: 10.111 s (forward 8.548 s, gradient 1.369 s).
- Total job wall time: 84.9 s.
- Peak RSS: 7.24 GB, against the parent's 8.13 GB (−0.9 GB, as predicted).

**Strict comparison:**
- Carrier, signal and powers: bitwise identical.
- Noise: max normalized error 1.2e-5, relative L2 error 2.5e-13. So the per-row unbatched dot is **not** bitwise equal to the batched dot; the hypothesis was wrong.
- Sensitivity: 1.2e-5.
- **Gradient fails at index 161:** normalized error 6.85 (absolute 2.07e-5 against a tolerance of 3.0e-6; reference −29.61289).

**Decision:** reject. Reverted to `NOISE_REUSE_MODE="broadcast"`. The timing gain (−0.24 s, single run) is within noise.

**Lesson:** gradient index 161 amplifies any rounding change in the forward noise (≈1e-13 relative → normalized 7). Any change on the noise path must keep the forward arithmetic bitwise.

## Candidate 2: `NOISE_FACTOR_REUSE="direct_implicit"`

### Hypothesis
- **Target:** forward execute and gradient execute. Parent: job `ab12c14c`, forward 8.609 s and gradient 1.475 s.
- **Mechanism:** in "direct" mode, the `A^H` noise-weight solve is `jnp.linalg.solve(explicit A^H)`. Its `custom_linear_solve` matvec closes over the transposed copy, so the copy (101×751×751 complex, 0.9 GB) is kept as an AD residual next to `A` itself. The new mode:
  - Factors the **same explicit `A^H`** with `lax.linalg.lu`, so LAPACK gets an identical input and returns identical pivots.
  - Solves with `lu_solve` trans=0 for the solve and trans=1 for the transpose solve, which is the same structure as `jnp.linalg.solve`.
  - Uses a matvec `x -> einsum("bji,bj", conj(A), x)` that reads `A`, which the direct solves already keep as a residual.
- **Expected:**
  - Forward outputs bitwise identical: same LU input, and the same lu_solve route that `"direct"` already showed to be bitwise for `A`.
  - The gradient's `A` cotangent from this solve has elementwise-identical products; only the order of accumulation with the other two solve contributions may differ.
  - Lower peak RSS (up to about 0.9 GB) and slightly lower forward/gradient execute.
  - Ceiling: well under 0.5 s; this has not been measured.
- **Risk:** gradient index 161 if the accumulation order changes rounding. Fallback is `NOISE_FACTOR_REUSE="direct"` (the parent).

### Results: candidate SHA `745f5c3417b2c75246d634c9ddddb0c852978da9` — **KEPT (best eligible revision)**

**Screen** (`748276a7a33c45f1a128e7a80b162be7`): 22.036 s. Provisional.

**Full** (`f60d64b6a10a4ed8a292a0b30df2fb65`): **official PASS, strict PASS**.

| Phase | Seconds | Parent |
| --- | --- | --- |
| Complete first run | **22.051** | 22.366 |
| Forward compile | 7.664 | 7.634 |
| Forward execute | 8.396 | 8.609 |
| Gradient compile | 1.948 | 1.962 |
| Gradient execute | 1.501 | 1.475 |
| Build | 0.807 | 0.821 |

- Warm median: 10.060 s, against the parent's 10.609 s (forward median 8.377 s against 8.936 s).
- Total job wall time: 87.0 s.
- Peak RSS: 8.12 GB, **unchanged**. The predicted 0.9 GB drop did not happen; XLA apparently did not keep the extra residual, or reuses it.

**Strict comparison:**
- All outputs are bitwise identical (error 0).
- Gradient: max absolute error 4.5e-13, normalized 1.6e-8. That is better than the parent's 6.0e-7 and equal to noise-reuse candidate 1's level.

**Interpretation:**
- First run −0.32 s and warm −0.55 s against the parent. These are single runs, and run-to-run noise is about ±0.3 s, so this is not a confirmed gain.
- It is kept because it is no worse, numerically cleaner and observed faster. A repeat full run is recommended.

## Candidate 3: NumPy initial base-matrix entries in `build` (build phase)

### Hypothesis
- **Target:** the build phase, 0.807 s in job `f60d64b6` (3.7% of the first run). It is host-side Python plus eager JAX.
- **Mechanism:** `build()` evaluates the following eagerly with JAX:
  - `mirror_matrix` / `beamsplitter_matrix`: about 30 scalar jnp ops each, plus a `np.array` conversion of JAX scalars, for every mirror and beamsplitter;
  - `space(jnp.array([...]))[0]`, for every space edge.
  
  That is hundreds of eager dispatches, first-use compilations of each primitive, and device-to-host syncs.
- **Why outputs are unaffected:** the code shows that each of these off-diagonal base entries is overwritten at the identical (row, column) by the carrier instructions:
  - mirror: rows `[1,1,3,3]`, columns `[0,2,0,2]`;
  - beamsplitter: rows `[1,1,3,3,5,5,7,7]`, columns `[2,4,0,6,0,6,2,4]`;
  - space: both directed entries.
  
  The signal instructions overwrite them in both sidebands. So their values never reach a solve.
- **Change:** `differometor/build.py` gets NumPy versions of the same formulas: `_np_mirror_matrix`, `_np_beamsplitter_matrix` and `_np_space_entry`. The base values can differ from the JAX ones by an ulp, but they are overwritten.
- **Expected:**
  - Build phase lower by some fraction of 0.8 s; the eager-JAX share is unmeasured.
  - All outputs and the gradient bitwise equal to candidate 2. Any nonzero output error would prove a base entry survives, and would be grounds to reject.
- **Ceiling:** 0.81 s (the whole build phase). A realistic saving is likely ≤0.3 s, and it is not measured.

### Results
- Candidate SHA: pending.
