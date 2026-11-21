# claude-noise-reuse

- Branch: `explore/claude-noise-reuse`. Scientific parent: `d09dc1d08fb046d08b3b699685d8ff780d611e87` (frequency-batching candidate 8: assembly-only loop, k=1). Parent full job `0c413080dbce47fd80211ca9525a3a89` passed official and strict checks with a complete first run of 23.840 s. Equivalent candidate 6 (`1d5a796f`) ran 23.558 s. These are not paired repeats.
- Source evidence: `experiments/context/noise-reuse-audit.md` (F1–F9). It is a design proposal, not a measurement.
- Session: managed. No shell, no local runs. The supervisor commits and evaluates.

## Candidate 1: guarded variant A (one noise build, broadcast to all rows)

### Hypothesis
In the parent, every iteration of the per-frequency `lax.map` (k=1, scope `assemble`) re-runs the noise components and does a dense 751×751 scatter. That is 101 builds and about 0.9 GB of copies. When Predicate S holds, every row's noise inputs are bitwise identical. Building the noise matrix once outside the loop and broadcasting it into the unchanged `_solve_signal_and_noise` should give the following:

- The **forward** output stays bitwise identical: same base, same component values, same scatter, same `bij,bj` einsum and same solves.
- The loop body becomes smaller.
- The only rounding change in the **gradient** should be the order of the db/angle and loss-position reduction. The noise-matrix cotangent is summed over rows before one component VJP, where the parent applied a VJP per row and then summed.

The time gain is expected but not measured, and probably small (well under 1 s).

### Change (`differometor/simulate.py`)
- `run_build_step`: implements Predicate S. It takes the real changing indices from `arrays_to_prepare[2]` and `[3]` (from `pairs_to_arrays`, before `prepare_arrays` inserts the dummy `[0]`). It takes the noise input indices from `noise_arrays[0]`, which includes padding, plus the grouped noise `parameter_indices`. If the two sets are disjoint, it sets the static pytree key `component_groups["noise_row_reuse"] = ()`. There is no `simulate` signature change.
- `simulate`: `reuse_noise` is True only when all of these hold:
  - the module flag `NOISE_ROW_REUSE` is set;
  - the builder key is present;
  - the active path is not the in-loop-solve `signal_noise` scope.

  When it is True, `simulate` calls the unbatched `update(parameters[0], noise_matrix, ...)` once with the noise component groups, then `jnp.broadcast_to(..., (count, NN, NN))`. In the `assemble` scope the loop body returns only the signal matrix. The full-vmap and `solve` scopes use the same broadcast.
- `_assemble_signal_and_noise`: if `noise_matrix is None`, it skips the noise update.
- Fallback: a caller without `component_groups`, a guard failure, or `NOISE_ROW_REUSE=False` runs the parent code unchanged.

### Risks
- **Strict gradient rounding** (db/angle coordinates especially; see audit F4). If strict comparison fails, I will not loosen tolerances: I will set `NOISE_ROW_REUSE=False` or look for another approach.
- The residual for the broadcast operand of the `bij` einsum may still be materialized as `(101,751,751)`, so memory may not fall.

### Results: candidate SHA `f3139c71ae2a5c9de2b015aad7db1a730fac0e1e`

**Screen** (`289867298598498aad72af58cab120c1`): first run 23.360 s, peak RSS 9.93 GB. Provisional.

**Full** (`5089ae06eb04473a87bc1207cb411d8c`): **official PASS, strict PASS** (verdict "validated").

| Phase | Seconds |
| --- | --- |
| Complete first run | 23.320 |
| Imports | 0.298 |
| Build | 0.820 |
| Forward lower | 0.812 |
| Forward compile | 7.680 |
| Forward execute (incl. AD residuals) | 9.221 |
| Sensitivity lower + compile | 0.434 |
| Gradient lower | 0.175 |
| Gradient compile | 1.963 |
| Gradient execute | 1.912 |

- Warm runs: median 11.872 s (11.388–11.872 s; forward median 9.810 s, gradient 1.887 s).
- Total job wall time: 92.9 s.
- Peak RSS (GNU time): 9.93 GB.

**Strict comparison:**
- Carrier, signal, noise, sensitivity and powers: max absolute error **0.0**, so the forward outputs are bitwise identical.
- Gradient: max absolute error 4.5e-13, max normalized error 1.64e-8 (limit 1), relative L2 error 6.6e-18.

**Interpretation:** −0.52 s against the parent's single full run (23.840 s). This is *not* a paired repeat, and run-to-run noise is about ±0.3 s (candidate 6 ran 23.558 s), so the gain is unconfirmed. The parent's RSS was not given in the brief, so I make no memory claim.

## Candidate 2: variant B (shared unbatched noise contraction)
- **Hypothesis:** feed the single `(NN,NN)` noise matrix straight into `einsum("ij,dbj->dbi", N, noise_weights)` instead of the broadcast `bij,bj`. This removes the possible `(101,751,751)` broadcast residual and turns 101 GEMVs into one GEMM.
  - Expected: lower RSS (up to about 0.9 GB) and a little less forward time. Not measured.
  - Risk: forward noise and every gradient coordinate can round differently (audit F4).
- **Change:** new module knob `NOISE_REUSE_MODE` (`"shared"` | `"broadcast"`). In `_solve_signal_and_noise`, a 2-D noise matrix selects the unbatched einsum. The `solve` scope always uses the broadcast form, because its loop slices noise rows.
- **Fallback:** if strict fails, set `NOISE_REUSE_MODE="broadcast"`, which is the validated candidate 1 behaviour.

### Results: candidate SHA `e525ee5ee4efabeeee9b3188b906fa560c0990a2`

**Screen** (`518c46e9b88f471f92b79f82c35ed008`): 22.599 s, peak RSS 9.02 GB.

**Full** (`ab7f50a0967e446db98e716cf8ea088a`): **official PASS, strict PASS**.

| Phase | Seconds |
| --- | --- |
| Complete first run | **22.564** |
| Imports | 0.290 |
| Build | 0.832 |
| Forward lower | 0.799 |
| Forward compile | 7.608 |
| Forward execute | 8.871 |
| Gradient compile | 1.843 |
| Gradient execute | 1.694 |

- Warm runs: median 11.265 s (forward 9.399 s, gradient 1.693 s).
- Total job wall time: 88.5 s.
- Peak RSS: 9.03 GB, against candidate 1's 9.93 GB, a measured drop of about 0.9 GB. This matches the predicted broadcast residual.

**Strict comparison:**
- Carrier, signal and powers: bitwise identical.
- Noise: max normalized error 1.6e-8. Sensitivity: 1.5e-8.
- **Gradient: max normalized error 0.949 (limit 1.0), max absolute error 2.45e-4, relative L2 error 4.1e-9.**

**Interpretation:** this passes, but with a thin margin. The reassociation in the shared GEMM moves one gradient coordinate to 95% of the strict tolerance. It is the fastest validated revision in this lane: −1.28 s against the parent's single run and −0.76 s against candidate 1. These are single runs, not paired repeats. Treat it as fragile: any further numerical change stacked on top is likely to cross the strict limit.

## Candidate 3: shared LU factorization for the signal, adjoint noise-weight and covariance solves
- **Lane note:** this reuses factorizations on the noise path. It is not block elimination or permutation, which belong to the other worker. The coordinator should sequence it against that worker's solve changes.
- **Hypothesis:** the parent factors `A` (signal and covariance solves; XLA may or may not CSE these) and separately factors `A^H` for the noise weights. One `lax.linalg.lu(stop_gradient(A))` per row, with `lu_solve` `trans=0/1/2` inside `lax.custom_linear_solve` (the same structure as `jnp.linalg.solve`), should remove at least the `A^H` factorization: one of two or three batched 751×751 complex LUs. Expected effect is a lower forward execute time. Not measured.
- **Base:** `NOISE_REUSE_MODE="broadcast"` (variant A). This isolates the effect from variant B's thin gradient margin.
- **Numerical risk:** the noise weights now come from `A`'s LU through a conjugate-transpose triangular solve instead of an LU of `A^H`. Every gradient coordinate can change. Earlier in-loop solve changes failed strict at 1.9e-7.
- **New knob:** `NOISE_FACTOR_REUSE` (bool at the time; now a string, see candidate 4).

### Results: candidate SHA `bb9a183fd64f80e322ff90b3161edbcdfd29c4ab` — **REJECTED (strict FAIL)**

**Screen** (`e8f8bf17c95f418596328d8de5ab10a3`): 18.677 s, peak RSS 6.37 GB.

**Full** (`f62c5c8053f84088a013f742fbe429a3`): official PASS, **strict FAIL**. Verdict: `official_pass_numerical_review_needed`.

| Phase | Seconds |
| --- | --- |
| Complete first run | 18.653 |
| Forward compile | 7.628 |
| Forward execute | **5.166** (candidate 1: 9.221) |
| Gradient compile | 1.955 |
| Gradient execute | 1.399 |

- Warm runs: median 7.091 s.
- Total job wall time: 62.3 s.
- Peak RSS: 6.37 GB.

**Strict comparison:**
- Carrier, signal and powers: bitwise identical. So the replicated direct `custom_linear_solve` matches `jnp.linalg.solve` exactly.
- Noise: max normalized error 0.644. Sensitivity: 0.644.
- **Gradient fails at indices 33, 161 and 180:**

| Index | Normalized error |
| --- | --- |
| 33 | 3.04 |
| 161 | 14.66 |
| 180 | 1.63 |

  Max absolute error 2.3e-3, relative L2 error 3.9e-8.

**Diagnosis:** solving `A^H y = s` through `A`'s LU (`trans=2`) instead of a separate LU of `A^H` changes noise at about 2e-8 relative. The ill-conditioned gradient coordinates (161 also failed in earlier solve experiments) amplify that. Tolerances not loosened.

**What the measurement shows:** the forward pass does many separate LUs. Removing them saved about 4 s of forward time and about 3.5 GB of RSS, so XLA was apparently not CSE-ing the `A` factorizations.

## Candidate 4: repair, sharing the LU only for solves on `A`
- **Change:** `NOISE_FACTOR_REUSE="direct"`. One LU of `A` is shared by the signal and covariance `custom_linear_solve`s. The noise weights use the original `jnp.linalg.solve` on the explicitly formed `A^H`, so they get their own LU, exactly as in the parent. `"all"` keeps candidate 3's failing behaviour; `"off"` keeps candidate 1.
- Base: `NOISE_REUSE_MODE="broadcast"`.
- **Hypothesis:** the covariance solve should be bitwise identical to the parent, since it uses the same LU and the same solve structure, as candidate 3 showed for the signal. So strict should match candidate 1's margin. Expected forward saving is about half of candidate 3's (one of the removed LUs), roughly 2 s. Not measured.

### Results: candidate SHA `96474bdd4d83bb02c163640f63fae1c4bd7a21d4` — **VALIDATED, best strict margin**

**Screen** (`ebd893f35b5a4497a8ea6e81bd8ca82b`): 22.139 s, peak RSS 8.11 GB.

**Full** (`ab12c14c29354bad9aa6dc024c91f8e6`): **official PASS, strict PASS**.

| Phase | Seconds |
| --- | --- |
| Complete first run | **22.366** |
| Imports | 0.297 |
| Build | 0.821 |
| Forward lower | 0.824 |
| Forward compile | 7.634 |
| Forward execute | 8.609 |
| Gradient compile | 1.962 |
| Gradient execute | 1.475 |

- Warm runs: median 10.609 s (forward 8.936 s, gradient 1.505 s).
- Total job wall time: 88.1 s.
- Peak RSS: 8.13 GB.

**Strict comparison:**
- Carrier, signal, noise, sensitivity and powers: **bitwise identical**.
- Gradient: max normalized error **6.0e-7**, max absolute error 5.1e-10.

**Interpretation:** the forward pass is 0.61 s faster than candidate 1 (9.22 s), less than the roughly 2 s predicted. Most of candidate 3's 4 s gain therefore came from dropping the separate `A^H` LU, or from residual and memory effects, not from the duplicated `A` LUs. RSS fell about 1.8 GB against candidate 1. This is the fastest revision in this lane with a large strict margin. Single runs, not paired repeats.

## Candidate 5 (final): candidate 4 plus variant B
- **Change:** `NOISE_FACTOR_REUSE="direct"` and `NOISE_REUSE_MODE="shared"`.
- **Hypothesis:** the two changes affect separate parts of the computation, so their savings could add up (about −0.7 s from variant B), for an expected first run of about 21.6 s. Not measured.
- **Gradient risk:** variant B alone used 0.949 of the strict budget. Candidate 4 is almost exact, so the combination is expected near 0.95. A pass is not guaranteed.
- If it fails, candidate 4 (`96474bd`) remains the fallback.

### Results
- Candidate SHA: (supervisor fills in). Pending. The session deadline may arrive before this result is recorded.

## Final handoff
- **Best fully validated revision with a robust margin:** `96474bdd4d83bb02c163640f63fae1c4bd7a21d4` (candidate 4).
  - First run 22.366 s against the parent's 23.840 s.
  - Bitwise forward outputs, gradient error 6e-7 normalized, RSS 8.13 GB.
- **Validated but fragile:** `e525ee5` (candidate 2, 22.564 s, gradient 0.949).
- **Validated, conservative:** `f3139c7` (candidate 1, 23.320 s).
- **Failed:** `bb9a183` (candidate 3, `NOISE_FACTOR_REUSE="all"`). 18.65 s, official PASS, strict FAIL on gradient indices 33/161/180. Do not admit.
- **Remaining uncertainty:**
  - Every timing is a single unpaired run. Noise is about ±0.3 s.
  - No HLO inspection was done, so why the `A^H` LU is so expensive in the forward pass (it carries about 3.4 s and 1.8 GB of residuals) is unexplained.
  - The fallback paths have not been exercised by any test: sweeps that would make Predicate S fail, and the `None` component_groups case.
- **Suggested next experiment:** inspect the forward pullback residuals and HLO for the noise-weight solve. Then look for a strict-safe way to avoid forming and factoring `A^H` explicitly, for example `lu_solve(trans=2)` with iterative refinement. That 4 s ceiling is the largest gain left in this lane. Also run paired repeats of candidate 4 against the parent.

## Proposed knobs (draft, not admitted)
```json
{
  "best_validated_sha": "96474bdd4d83bb02c163640f63fae1c4bd7a21d4",
  "best_validated_config": {"NOISE_ROW_REUSE": true, "NOISE_REUSE_MODE": "broadcast", "NOISE_FACTOR_REUSE": "direct"},
  "file": "differometor/simulate.py",
  "symbols": ["NOISE_ROW_REUSE", "NOISE_REUSE_MODE", "run_build_step (Predicate S -> component_groups['noise_row_reuse'])", "_assemble_signal_and_noise", "_solve_signal_and_noise"],
  "knobs": [
    {"symbol": "NOISE_ROW_REUSE", "legal": [true, false], "safe_default": false,
     "conditions": "effective only when run_build_step set component_groups['noise_row_reuse'] (Predicate S) and the chunked path is not FREQUENCY_LOOP_SCOPE='signal_noise'",
     "invalid": "none; guard failure falls back automatically"},
    {"symbol": "NOISE_REUSE_MODE", "legal": ["broadcast", "shared"], "safe_default": "broadcast",
     "conditions": "only read when NOISE_ROW_REUSE is effective; scope 'solve' always uses broadcast",
     "invalid": "'shared' validated (e525ee5) but strict gradient margin 0.949; avoid stacking with other numerical changes"},
    {"symbol": "NOISE_FACTOR_REUSE", "legal": ["off", "direct", "all"], "safe_default": "off",
     "conditions": "'direct' validated (96474bd, bitwise forward, gradient 6e-7 normalized); touches solves, sequence against block-elimination worker",
     "invalid": "'all' fails strict gradient (bb9a183); do not admit"}
  ]
}
```
