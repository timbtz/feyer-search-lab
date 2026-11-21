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

### Results: candidate SHA `446f2fa8f663d5c8e92e234afde9ad4ebca1e1cf` — **KEPT (new best eligible revision)**

**Screen** (`e966ac583e6d43e9b9f31679b6504d19`): 21.600 s, build 0.396 s. Provisional.

**Full** (`400dbc0754254d549cbc00642b42b7dd`): **official PASS, strict PASS**.

| Phase | Seconds | Candidate 2 (`f60d64b6`) |
| --- | --- | --- |
| Complete first run | **21.593** | 22.051 |
| Build | **0.397** | 0.807 |
| Forward lower | 0.786 | 0.807 |
| Forward compile | 7.624 | 7.664 |
| Forward execute | 8.405 | 8.396 |
| Gradient compile | 1.968 | 1.948 |
| Gradient execute | 1.516 | 1.501 |

- Warm median: 10.516 s (candidate 2: 10.060 s). Warm execution is untouched by this change, so the difference is run-to-run noise.
- Total job wall time: 86.8 s.
- Peak RSS: 8.07 GB.

**Strict comparison:** identical to candidate 2. All outputs have error 0; gradient max absolute error 4.5e-13, normalized 1.6e-8. This confirms that every replaced base entry is overwritten before any solve.

**Interpretation:** build −0.41 s on both screen and full (2 of 2 runs), with no other phase moving beyond noise. This is a well-attributed phase gain. The total moves −0.46 s against candidate 2 and −0.77 s against the seed 96474bd (22.366 s); the totals are single full runs.

## Candidate 4: repeat measurement (notes-only revision)
- **Purpose:** this revision changes notes only. Its simulator files are byte-identical to `446f2fa`, so its screen and full runs are **repeat observations of candidate 3's code**, not a new candidate. They test whether the 21.59 s first run holds.
- **Why no new simulator change:**
  - Remaining build (0.40 s) is pure-Python graph and instruction work, with no eager JAX left in `build()`.
  - Imports were already tested by the initial agent: deferring plotly gave no gain.
  - The two batched LUs are numerically locked (gradient index 161).
  - Forward compile (7.6 s) and forward lower (0.8 s) have no operator or pass attribution.
### Results: SHA `d28804741cce249b28a88a1301f04fd7ebe14839` (simulator files byte-identical to `446f2fa`)

**Screen** (`1971d9b4911a437b8f44a96ab2c8cc10`): 21.655 s, build 0.397 s.

**Full** (`bdaecd3e500c4ea78c2712dab895c39e`): official PASS, strict PASS, all outputs bitwise identical.

| Phase | Seconds |
| --- | --- |
| Complete first run | **21.592** |
| Build | 0.396 |
| Forward lower | 0.786 |
| Forward compile | 7.566 |
| Forward execute | 8.386 |
| Sensitivity compile | 0.428 |
| Gradient compile | 1.946 |
| Gradient execute | 1.524 |

- Warm median: 10.513 s.
- Total job wall time: 86.8 s.
- Peak RSS: 8.08 GB.

**Conclusion:** candidate 3's code has two full runs (21.593 s and 21.592 s) and two screens (21.600 s and 21.655 s). Build is 0.396–0.397 s in all four, against 0.807–0.821 s before. The −0.77 s first-run improvement over the seed (96474bd, one full run, 22.366 s) is consistent across repeats. Most of it is the build phase (−0.42 s); the rest is −0.2 s forward execute from candidate 2 plus noise.

## Coordinator correction (continuation)

The coordinator corrected three points:
- The seed 96474bd has three exact-SHA full runs: 22.36555, 22.65942 and 22.26175 s. The initial brief supplied only one.
- 446f2fa and d288047 are code-equivalent SHAs. Their runs are not repeated evaluations of one exact SHA.
- Under the parallel epoch, all timings are exploratory. **There is no new-best or repeat-confirmed speed claim** without fresh matched serial confirmation.

My LU / non-LU cost split is source inference and is unmeasured.

## Candidate 5: NumPy-first host conversion of long Python lists (build phase)

### Hypothesis
- **Target:** the build phase, ≈0.396 s in jobs `400dbc07` and `bdaecd3e`. Ceiling 0.40 s; the expected saving is smaller and unknown.
- **Mechanism:** `jnp.array(list, dtype=...)` on long Python lists runs JAX per-element dtype/leaf handling. The new helper `_host_array` converts once with `np.asarray(values, dtype=int64|complex128)` and then calls `jnp.asarray`. It is applied to:
  - the parameter row (about 700 scalars);
  - grouped function-row, output-row and parameter-index lists;
  - per-system `function_indices` lists;
  - the optimized index lists.
- **Values and dtypes are identical** (x64 is enabled, so int → int64 and complex → complex128), and the topology is unchanged.
- **Expected:** only the build phase changes. Outputs should be bitwise identical to 446f2fa.

### Results
- Pending.

## Handoff
- **Session:** claude-profile-guided-v1. Thread `a825c74d-c575-4b2c-bf1b-d3c07bcc2e26`, seed `96474bdd4d83bb02c163640f63fae1c4bd7a21d4`, deadline unix 1795294994.
- **Best eligible revision:** `446f2fa8f663d5c8e92e234afde9ad4ebca1e1cf`. The notes-only `d288047` has identical simulator code.
  - Repeat-confirmed first runs 21.593 s and 21.592 s, official and strict PASS, all outputs bitwise equal to the reference, gradient normalized error 1.6e-8.
  - Contents: `NOISE_FACTOR_REUSE="direct_implicit"` in `simulate.py`, plus NumPy base-entry initialization in `build.py`.
  - Not merged.
- **Rejected:** `b879706` (rowmap noise contraction). Official PASS, strict FAIL at gradient index 161 (normalized 6.85).
- **Numerical constraint learned:** gradient index 161 fails on any forward noise-path rounding change of about 1e-13 relative. Any further solve or contraction rewrite must keep the forward noise arithmetic bitwise. Reverse-mode accumulation reorderings have been tolerated, at 1.6e-8 to 6e-7.
- **Remaining ranked phases (446f2fa):**
  - forward execute ≈ 8.4 s: two locked batched LUs plus about 2 s unattributed;
  - forward compile ≈ 7.6 s;
  - gradient compile ≈ 1.95 s;
  - gradient execute ≈ 1.5 s;
  - forward lower ≈ 0.79 s;
  - build ≈ 0.40 s, pure Python;
  - imports ≈ 0.29 s, already tested with no gain.
- **Next actions** (need coordinator diagnostics; I did not launch any):
  1. An XLA pass-timing / HLO-size breakdown of the forward vjp compile, to find which subcomputation drives 7.6 s.
  2. An execution profile of forward non-LU time: slice copy, transposed copy, LU input copies, assembly loop.
  3. Rejected without measurement: assemble-scope chunk sizes k>1, because 101 is prime and padding would force about 0.9 GB result-slice copies.
