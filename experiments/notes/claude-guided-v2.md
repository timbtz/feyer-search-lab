# claude-guided-v2

- Branch: `explore/claude-guided-v2`. Exact start: `aa2b1ab44180af8dd1cd3a9796adb911b1a3986a` (claude-profile-guided-v1 candidate 5).
- Model: `claude-opus-5-5`. Managed session: no shell and no local runs; the supervisor commits and evaluates. Window: 3599 s at candidate 1.

## Starting evidence: aa2b1ab, full job `35abe628`

- Official PASS, strict PASS. Outputs are bitwise identical to the reference; gradient max absolute error 4.5e-13.

| Phase | Seconds |
| --- | --- |
| Complete first run | 21.550 |
| Imports | 0.293 |
| Build | 0.303 |
| Forward lower | 0.789 |
| Forward compile | 7.622 |
| Forward execute | 8.432 |
| Sensitivity lower + compile | 0.445 |
| Gradient lower | 0.181 |
| Gradient compile | 1.959 |
| Gradient execute | 1.519 |

- Warm median: 10.55 s.
- This is one observation in the concurrent epoch 14, cohort 10567ad0. It is exploratory.

## Owned combination: aa2b1ab build changes + Astra `7d1ccc59` — BLOCKED (source not inspectable)

- The managed file tools are confined to this worktree. There is no shell, and `.git` points outside the sandbox.
- As a result I cannot read Astra's (codex-profile-guided-v1 candidate 9) exact diff or its declared parents. No run JSON for it exists in this worktree.
- Per the rules (read exact diffs; do not merge blindly), I did **not** author the combination.
- What the shared feed shows for 7d1ccc5 (job `7e6ce3c3`, concurrent epoch 14, single observation):

  | Phase | 7d1ccc5 | aa2b1ab |
  | --- | --- | --- |
  | Total | 20.06 s | 21.55 s |
  | Build | 0.82 s | 0.30 s |
  | Forward compile | 3.31 s | 7.62 s |
  | Gradient compile | 4.06 s | 1.96 s |
  | Forward lower | 0.69 s | 0.79 s |
  | Gradient lower | 0.30 s | 0.18 s |
  | Forward execute | 8.60 s | 8.43 s |
  | Gradient execute | 1.52 s | 1.52 s |

- Build is clearly complementary. aa2b1ab's build gain (−0.5 s, attributed over 4 runs of the lineage) lives in `build.py`. Whether 7d1ccc5 touched `build.py` is unknown.
- **Needed from the coordinator to unblock:** the exact 7d1ccc5 diff against its parent, delivered into this worktree, for example as a file under `experiments/context/`.

## Candidate 1: rematerialize the per-row assembly loop body (`ASSEMBLY_REMAT=True`)

This is my own hypothesis. It is *not* a transfer of 7d1ccc5's code, which I could not read. It was motivated by 7d1ccc5's phase pattern: compile time moves from forward to gradient while execution is unchanged. That pattern is what remat of forward residuals would produce.

### Hypothesis
- **Target:** forward compile, 7.62 s in job `35abe628` (35% of the first run). It is the largest compile phase.
- **Mechanism:** the benchmark's forward stage is `jit(vjp(simulate))`. That means it compiles the primal *plus* the partial-eval of every linearization residual.
  - In the `"assemble"` loop (`lax.map` over 101 rows, k=1), every grouped component function's residuals (for example the sin/cos and exp factors of each component type) become stacked per-row scan outputs.
  - Wrapping the loop body in `jax.checkpoint(prevent_cse=False)` makes the forward scan emit only its outputs; the residuals are its inputs.
  - The reverse scan then recomputes the primal assembly per row before transposing.
- **Prediction:**
  - Forward compile and forward lower decrease, and gradient lower and compile increase. Forward execute changes slightly (fewer residual writes).
  - Gradient execute increases by the recompute of the assembly. That cost is unknown; it is component math, not LU.
  - The total improves only if the forward compile saving exceeds the gradient compile and execute increase. That is unknown. The 7d1ccc5 pattern (net compile −2.2 s) is an analogy, not evidence for this code.
- **Numerics:**
  - Forward outputs are expected to be bitwise identical: same primal ops, and the solves are untouched.
  - The gradient uses recomputed residuals from identical ops, so I expect it to stay at or near the 4.5e-13 level.
  - Any forward output difference, or a strict gradient failure (index 161 is the sensitive one), rejects the candidate.
- **Fallback:** `ASSEMBLY_REMAT=False`, which is byte-equivalent behaviour to aa2b1ab.
- **Source delta vs aa2b1ab:** `differometor/simulate.py` only — the new flag and a 4-line wrap of `block_assemble`. `build.py` is unchanged.

### Results: SHA `5b2169697d359f6a1c1f7fd6b5f66e08e9906969` — official PASS, strict PASS, **no gain (not kept)**

**Screen** (`630661aa`): 21.781 s. Provisional.

**Full** (`01ae3245`):

| Phase | Candidate 1 | aa2b1ab (`35abe628`) | Change |
| --- | --- | --- | --- |
| Complete first run | 21.725 | 21.550 | +0.18 |
| Forward lower | 0.701 | 0.789 | −0.09 |
| Forward compile | 4.703 | 7.622 | **−2.92** |
| Forward execute | 8.500 | 8.432 | +0.07 |
| Gradient lower | 0.315 | 0.181 | +0.13 |
| Gradient compile | 4.774 | 1.959 | **+2.81** |
| Gradient execute | 1.602 | 1.519 | +0.08 |

- Warm median: 10.588 s. Total job wall time: 87.3 s. Peak RSS: 7.81 GB (parent 8.05 GB).
- Strict comparison: carrier, signal, noise, sensitivity and powers are all bitwise identical (error 0). Gradient max absolute error 2.9e-11, max normalized error 1.1e-6 (parent: 1.6e-8). The run passes, with a smaller margin than the parent.
- **Interpretation:**
  - Remat moved about 2.9 s of compile from the forward program to the gradient program almost one-for-one. Total compile time is essentially unchanged.
  - Measured inference: about 2.9 s of compile is attributable to the assembly *linearization* (the derivative residuals of the component functions), wherever it is placed.
  - 7d1ccc5's lower total compile must therefore come from something other than plain remat.
- **Decision:** not kept. `ASSEMBLY_REMAT=False` is restored in candidate 2.

## Candidate 2: gradient-stop constant component input slots (`COMPONENT_SLOT_PRUNING=True`)

### Hypothesis
- **Target:** the compile cost of the assembly linearization: about 2.9 s, attributed by candidate 1, inside forward compile (7.62 s, job `35abe628`), plus the matching transposes in gradient compile (1.96 s).
- **Mechanism:**
  - After `expand_parameters`, the whole parameter row carries one dense tangent. So JAX forms derivative terms for *every* component input, including inputs that never depend on a design variable: frequency, loss, refractive indices and incidence angle. For `surface`, 5 of 7 inputs are like this.
  - On the host, the builder now records per function group which input slots read an optimized index or a linking output (`component_groups[name]["diff_slots"]`). It is stored as static dict keys with empty-tuple values, so it adds no traced leaves.
  - `update` passes each group's columns as separate scalars, with `lax.stop_gradient` on constant slots, through a `_ParameterSlots` stand-in for the parameter vector. Their tangents are symbolic zeros, so neither their residuals nor their transposes are generated.
- **Exactness:**
  - The derivative of a constant slot is exactly zero, and stop_gradient is the identity in the forward pass.
  - Forward outputs are expected bitwise identical. The gradient is expected identical or within reordering: the dropped terms were exact `0*x` contributions.
- **Prediction:**
  - Forward compile and gradient compile decrease, and forward lower and gradient lower probably decrease slightly.
  - Execute times are unchanged or slightly lower.
  - Size unknown; the ceiling is well under the 2.9 s linearization share. The `*_lower` component variants re-stack their inputs into a dense vector, so they get no pruning.
- **Reject if:** any forward output differs from the reference, or strict fails.
- **Source delta vs aa2b1ab:** simulate.py only:
  - `_ParameterSlots`;
  - `_evaluate_component_group_slots`;
  - a branch in `update`;
  - `diff_slots` computed in `run_build_step`;
  - the `ASSEMBLY_REMAT` flag, now False.
  
  Fallback: `COMPONENT_SLOT_PRUNING=False`.

### Results: SHA `10a311f6dbe4e8b71fa98654d015493ab8b3ef27`: official PASS, strict PASS, **kept (new branch best)**

**Screen** (`d6028ac4`): 19.853 s. Provisional.

**Full** (`3a030c65`):

| Phase | Candidate 2 | aa2b1ab (`35abe628`) | Change |
| --- | --- | --- | --- |
| Complete first run | **19.766** | 21.550 | **−1.78** |
| Forward lower | 0.731 | 0.789 | −0.06 |
| Forward compile | 6.620 | 7.622 | **−1.00** |
| Forward execute | 8.395 | 8.432 | −0.04 |
| Gradient lower | 0.132 | 0.181 | −0.05 |
| Gradient compile | 1.318 | 1.959 | **−0.64** |
| Gradient execute | 1.506 | 1.519 | −0.01 |

- Warm median: 10.487 s. Job wall time: 84.9 s. Peak RSS: 7.97 GB.
- Strict comparison: carrier, signal, noise, sensitivity and powers are all bitwise identical (error 0). Gradient max absolute error 4.5e-13, max normalized error 1.6e-8, the same margin as the parent.
- The prediction held: both compiles and both lowers decreased, and execute times were unchanged. One full observation only; it has not yet had a quiet serial confirmation.
- **Decision:** keep. Candidate 3 builds on it.

## Candidate 3: slot pruning for the `*_lower` variants (`LOWER_SLOT_PRUNING=True`)

### Hypothesis
- **Target:** forward compile (6.62 s) and gradient compile (1.32 s) in job `3a030c65`.
- **Mechanism:**
  - `space_lower`, `space_modulation_lower` and `laser_frequency_modulation_lower` each compute `base(jnp.array([-p[0], p[1], ...]))`.
  - The `jnp.array` re-stack turns the per-slot symbolic-zero tangents back into a dense tangent vector, so candidate 2's pruning did not apply to these groups.
  - `_evaluate_component_group_slots` now calls the base function directly through `_ParameterSlots`, with slot 0 negated. Only the length slot stays differentiable, where the mask allows it.
- **Exactness:** the same scalars reach the same base function (`-x` is computed in both versions). Forward outputs are expected bitwise identical, and the gradient identical or within reordering.
- **Prediction:** a small decrease in forward and gradient compile, probably ≤0.3 s in total; execute unchanged.
- **Reject if:** any forward difference, strict failure, or a slower total than 19.77 s beyond noise.
- **Source delta vs 10a311f:** simulate.py only. It adds `_LOWER_TO_BASE`, a branch in `_evaluate_component_group_slots`, and the `LOWER_SLOT_PRUNING` flag. Fallback: set the flag to False.

### Results: SHA `3b805077bb5c61d85115faf38af243cc001d0fee`: official PASS, strict PASS, **kept (new branch best)**

**Screen** (`44aca418`): 19.596 s. Provisional.

**Full** (`57ef1df7`):

| Phase | Candidate 3 | 10a311f (`3a030c65`) | Change |
| --- | --- | --- | --- |
| Complete first run | **19.567** | 19.766 | **−0.20** |
| Forward lower | 0.712 | 0.731 | −0.02 |
| Forward compile | 6.473 | 6.620 | −0.15 |
| Forward execute | 8.403 | 8.395 | +0.01 |
| Sensitivity lower | 0.079 | 0.172 | −0.09 (harness-side; likely noise) |
| Gradient lower | 0.166 | 0.132 | +0.03 |
| Gradient compile | 1.289 | 1.318 | −0.03 |
| Gradient execute | 1.514 | 1.506 | +0.01 |

- Warm median: 10.164 s. Job wall time: 84.7 s.
- Strict comparison: all forward outputs bitwise identical; gradient max normalized error 1.6e-8, unchanged.
- The prediction (≤0.3 s from compile) held: about 0.18 s of compile was saved. This is one observation, and part of the gain is within noise.
- This is the lowest full-valid total observed in cohort `10567ad0` so far (astra 3581734: 19.70). It is unconfirmed and needs a quiet serial confirmation.
- **Decision:** keep. Candidate 4 builds on it.

## Candidate 4: row-level split of constant rows (`ROW_SPLIT_PRUNING=True`)

### Hypothesis
- **Target:** forward compile (6.47 s) and gradient compile (1.29 s) in job `57ef1df7`.
- **Mechanism:**
  - The slot masks are per group. If any one row reads an optimized index in a slot, every row's input in that slot is differentiable. For example, `surface` reflectivity and tuning are optimized for some mirrors but not for others, and `space` length is optimized for only some spaces.
  - On the host, the builder now reorders each mixed group as [rows reading any optimized/linked index, all-constant rows]. It does this stably and applies the same permutation to `parameter_indices` and `output_rows`.
  - The split count is stored as a static dict key.
  - `update` evaluates the constant rows with every slot gradient-stopped, so they produce no linearization residuals or transposes.
- **Exactness:**
  - Each row runs the same elementwise computation on the same inputs, and the output selection is remapped exactly.
  - Forward outputs are expected bitwise identical. That assumes XLA's elementwise kernels give per-element identical results at a different batch size; this is unverified, but strict rtol 1e-7 covers it.
  - The gradient is expected identical or within reordering.
- **Prediction:** forward and gradient compile decrease by an unknown amount, depending on how many rows are constant; probably 0.1–0.5 s. Execute is unchanged or slightly lower; there are two vmaps per mixed group instead of one.
- **Reject if:** strict fails, or the total is slower than 19.57 s beyond noise.
- **Source delta vs 3b80507:** simulate.py only. It adds the `ROW_SPLIT_PRUNING` flag, a reorder block in `run_build_step`, and a branch in `update`. Fallback: set the flag to False.

### Results: SHA `633689f9bf054a90ca21b7b6087120cd86fa0d0e`: official PASS, strict PASS, **neutral (kept, within noise)**

**Screen** (`afdab87c`): 19.530 s.

**Full** (`ef7e77be`):
- First run 19.543 s vs 19.567 s (−0.02).
- Forward compile 6.394 vs 6.473 (−0.08); gradient compile 1.305 vs 1.289 (+0.02). Execute unchanged.
- Warm median: 10.070 s.
- Strict comparison: forward outputs bitwise identical; gradient max normalized error 1.6e-8.
- **Interpretation:** the predicted direction held, but the size (~0.06 s of compile) is within run-to-run noise. Most of the slot pruning was already captured at group level.
- **Decision:** keep as parent, since there is no regression and it is exact. Do not claim it as a gain.

## Candidate 5: narrow component-value remat (`COMPONENT_VALUE_REMAT=True`). Transferred from peer 7d1ccc5

### Source and attribution
- **Source:** the coordinator delivered the exact `simulate.py` diff aa2b1ab→7d1ccc5 (diff sha256 `4a6f50c0…0a0912`).
- **Mechanisms in that diff:**
  1. `_component_values`: `jax.checkpoint` with a policy that saves only integer/bool index results. It covers just the component evaluation and output selection; the dense matrix scatter and carrier coupling stay outside.
  2. `flat_matrix_indices` and `flat_output_indices` scatter/gather paths.
  3. Carrier scaling fused into `update` through `carrier_output_positions`.
  4. `NOISE_FACTOR_REUSE` reverted to "direct", with `direct_implicit` and `rowmap` removed.
- **Not transferred:** items 2 and 3 need builder keys that come from peer build.py changes, which are not in the delivered diff, so they cannot be used. Item 4 is a separate, unattributed solve change, so it is left out to keep this candidate attributable.

### Hypothesis
- **Scientific parents:** 633689f (own branch: slot and row pruning, build.py improvements) and 7d1ccc5 (mechanism 1 only).
- **Target:** forward compile (6.39 s) and gradient compile (1.30 s) in job `ef7e77be`.
- **Evidence:**
  - Candidate 1 rematerialized the whole per-row `block_assemble`, including the dense scatter and conjugation. Compile moved almost one-for-one: forward+gradient compile was 9.48 s vs 9.58 s for aa2b1ab.
  - 7d1ccc5's checkpoint is narrow. It recomputes only the component arithmetic and saves integer index results. Its job `7e6ce3c3` measured forward 3.31 s + gradient 4.06 s = 7.37 s.
  - That 7.37 s figure is confounded with its flat-index and carrier-fusion changes, so the share due to the narrow remat alone is unknown.
- **Mechanism:**
  - The forward vjp no longer contains the component linearization. The reverse program recomputes the component values only; the matrix scatter, solves and carrier coupling are not recomputed.
  - Slot and row pruning still apply inside the checkpoint, so the recomputed linearization is the already-pruned one.
- **Exactness:** remat recomputes the same primal ops, so forward outputs are expected bitwise identical. The gradient is expected identical or within reordering.
- **Prediction:**
  - Forward compile decreases and gradient compile increases.
  - The net change is unknown: it improves only if the narrow scope avoids candidate 1's one-for-one transfer.
  - Gradient execute may rise slightly because of the recomputation.
- **Reject if:** a strict failure, or a total slower than 19.54 s beyond noise.
- **Source delta vs 633689f:** simulate.py only.
  - `update` now calls `_component_values`, which is the existing body moved out unchanged.
  - Adds the `_save_assembly_indices` policy (copied from 7d1ccc5) and the `COMPONENT_VALUE_REMAT` flag.
  - Fallback: set the flag to False.

### Results
- Pending.
