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

### Results
- Candidate SHA: (supervisor fills in) — screen: pending — full: pending.

## Proposed knob (draft, not admitted)
```json
{
  "candidate_sha": "TBD",
  "file": "differometor/simulate.py",
  "knobs": [
    {"symbol": "NOISE_ROW_REUSE", "legal": [true, false], "safe_default": false,
     "conditions": "effective only when run_build_step set component_groups['noise_row_reuse'] (Predicate S) and FREQUENCY_LOOP_SCOPE != 'signal_noise' on the chunked path",
     "invalid": "none; guard failure falls back automatically"}
  ]
}
```
