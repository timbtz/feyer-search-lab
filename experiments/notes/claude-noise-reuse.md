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

### Results
- Candidate SHA: (supervisor fills in). Screen/full: pending.

## Proposed knobs (draft, not admitted)
```json
{
  "best_validated_sha": "f3139c71ae2a5c9de2b015aad7db1a730fac0e1e",
  "file": "differometor/simulate.py",
  "symbols": ["NOISE_ROW_REUSE", "NOISE_REUSE_MODE", "run_build_step (Predicate S -> component_groups['noise_row_reuse'])", "_assemble_signal_and_noise", "_solve_signal_and_noise"],
  "knobs": [
    {"symbol": "NOISE_ROW_REUSE", "legal": [true, false], "safe_default": false,
     "conditions": "effective only when run_build_step set component_groups['noise_row_reuse'] (Predicate S) and the chunked path is not FREQUENCY_LOOP_SCOPE='signal_noise'",
     "invalid": "none; guard failure falls back automatically"},
    {"symbol": "NOISE_REUSE_MODE", "legal": ["broadcast", "shared"], "safe_default": "broadcast",
     "conditions": "only read when NOISE_ROW_REUSE is effective; scope 'solve' always uses broadcast",
     "invalid": "'shared' is unvalidated until candidate 2 passes strict"}
  ]
}
```
