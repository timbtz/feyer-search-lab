# Claude frequency batching (explore/claude-frequency-batching)

- Agent: Claude Opus 5.5, managed headless session (60 min budget; session ID held by supervisor).
- Parent: component-specialization candidate 11, `6dc993a06cf2de5ae2ae3afa83304a46b2ead4d0`.
  Full run `80863bdee23a48d2b000e3b32e481ecc`: official+strict pass, first-run 24.657326162 s,
  compile/lower 10.233 s (forward lower 0.680, forward compile 6.982, gradient compile 1.913),
  first forward execute 11.508 s, first gradient execute 1.808 s, build 0.814 s,
  warm median 13.801646521 s, peak RSS 12547788 KiB, job wall 104.70 s. Single measurement.
- Scope: `differometor/simulate.py` and this note only.

## Source evidence (read from source, not measured)

- Axes: carrier sweep has one row in the benchmark (carrier output (286,1)), so after
  `expand_parameters` the signal parameters are (101, P). Every signal/noise array has a
  leading frequency axis B=101: `signal_matrix` (101, 751, 752) complex128 ≈ 0.91 GB per
  materialized copy; `transposed_conjugated_signal_matrix` another ≈ 0.91 GB; noise matrix
  (101, NN, NN); covariances (D, 101, 751).
- Detector axis: `noise_selection_vectors` (D, 1, N); vmap over D with the matrix unbatched
  (`in_axes=(None, 0)`), so LU is not replicated per detector. Fixture has D=1.
- Solves per frequency: `solve(A, b)` (signal), `solve(A^H, w)` (noise weights; separate LU),
  `solve(A, s)` (covariances; same operand A as the signal solve, so XLA may CSE the two
  getrf calls — not verified by HLO). Forward execute 11.5 s ≈ 2–3 batches of 101 complex
  n=751 LUs (~1.1 GFLOP real each) — an inference, not a measurement.
- Frequency independence: after the carrier solve and the frequency-independent detector
  selection preparation, every operation in signal/noise is row-wise in B. Carrier enters only
  as a (1, ·) broadcast. Hence a row-block decomposition is mathematically identical per row.
- Three JIT stages: forward `jax.vjp(simulate)` saves residuals across the stage boundary;
  gradient stage applies the pullback. With `lax.map` the residuals are stacked scan
  residuals (same total size); the reverse becomes a reverse scan.
- 101 is prime: any chunk other than 1/101 needs a remainder. `lax.map(batch_size=)` traces the
  body twice for the remainder (more compile). This candidate instead pads by repeating the last
  row (single body trace; extra wasted LU work = padded rows, e.g. 3/101 for k=8).

## Hypothesis (candidate 1, k=1)

Sequential per-frequency execution keeps each 9 MB matrix and its copies (scatter, carrier
scaling, conjugation `where`, astype, explicit A^H transpose) near cache and avoids allocating
and first-touching many ~0.9 GB intermediates. Expected: lower forward execution and lower
peak RSS; compile roughly unchanged (one body trace, same ops), gradient compile may change
because the reverse becomes a scan. Risks: scan residual stacking via dynamic-update-slice
adds copies; reverse scan may be slower than batched reverse; batch-1 dot/einsum may round
differently from batch-101 (strict comparison must confirm). Within-frequency CSE between the
signal and covariance LU(A) is preserved since both are in the same body. No LU sharing
between A and A^H is introduced.

## Operator proposal: `frequency_chunk_size`

- Name: `frequency_chunk_size`; symbol `differometor.simulate.FREQUENCY_CHUNK_SIZE`
  (module constant read at trace time; never a traced argument, so the benchmark arrays dict is
  unchanged).
- Legal values: `None` (full vmap, parent behaviour), 1, 4, 8, 16. Default for the space: `None`
  until measured. Candidate 1 materializes 1.
- Conditions: chunked path only when carrier batch == 1 and B > k; else full vmap (generic
  carrier sweeps, tiny sweeps). Remainder padded with the last row and discarded.
- Affected symbols: `simulate` (signal/noise section split), new `_signal_and_noise`,
  `_map_frequency_chunks`. Detector-selection preparation hoisted before the frequency
  section (identical operations, computed once).
- Compatibility: orthogonal to component grouping (`component_groups` passed unchanged into the
  body; `update` still vmapped over the block rows) and to checkpoint/prevent_cse settings
  (branch-local `jax.checkpoint(prevent_cse=False)` is the scan-safe setting). Not combined
  with shared-LU or Schur paths.
- Validation for admission: unchanged full benchmark, official + strict pass, full saved-output
  and gradient comparison per value; record forward/gradient compile and execute separately,
  peak RSS; repeat before any superiority claim.

## Candidates

### Candidate 1 — `FREQUENCY_CHUNK_SIZE = 1`
- SHA `aa4d230f4af70946be5c0f1f784eac2888c6bbe6`.
- Screen `26280ae1f2ec423e91700cf06f2b2cbf` (request `830a514242554cca835a6bf0800bad13`): passed cheap
  checks; first-run 21.676263 s; compile/lower 10.883 s; forward exec 8.987 s; gradient exec
  0.689 s; peak RSS 7267128 KiB; wall 22.55 s.
- Full `4230614b363b4a75a92f331df5e84eef` (request `4889a61d90d24fffbe2d37797f8da470`):
  **official PASS, strict FAIL**. First-run 22.076372 s (parent 24.657326). Phases: imports
  0.291, build 1.096 (parent 0.814; no builder change), forward lower 0.835 / compile 7.777
  (parent 0.680 / 6.982), forward exec 9.117 (parent 11.508), gradient lower 0.183 / compile
  1.788 (parent 0.132 / 1.913), gradient exec 0.679 (parent 1.808). Compile/lower total 10.888
  (parent 10.233). Warm median 10.071 s (parent 13.802); warm forward median 9.385, gradient
  0.683. Peak RSS 7270196 KiB (parent 12547788, −42%). Job wall 78.93 s (parent 104.70).
- Comparison: carrier, signal, noise, sensitivity, powers, parameters, frequencies **exactly**
  equal (max abs 0). Gradient relative L2 9.18e-10, max abs 5.61e-5 (on large entries, within
  tolerance). One failing coordinate: index 161 = `boundary01.power` (laser power), reference
  −29.61288925877842, candidate −29.612894755369226, abs 5.50e-6 vs tolerance 3.02e-6
  (normalized 1.82; rel 1.9e-7 vs rtol 1e-7). Official FD check passed.
- Diagnosis (source reasoning, not verified by HLO): laser power influences the loop only via
  the carrier solution, which is a frequency-shared closure constant of the `lax.map`. Scan
  transpose accumulates closure-constant cotangents sequentially over 101 iterations, whereas
  the vmapped layout sums a (101, ·) cotangent with one broadcast-transpose reduction. Different
  summation order → rounding-level difference in carrier-dependent gradients.
- Decision: strict failure blocks validation. Timing evidence is strong (−2.58 s first run, single
  run) so keep the direction and fix the accumulation order.

### Candidate 2 — k=1, frequency-shared parameter-dependent inputs fed as scanned rows
- Change vs candidate 1: gather `carrier[:, signal_carrier_indices]` before the loop (as the
  vmapped body effectively did before broadcasting), `broadcast_to` it and the detector
  `carrier_selections` to the full 101 rows outside the loop and pass them as scanned `xs`
  (selections moved to row-major (B, D, N) and back inside the body). Reverse: cotangents are
  stacked per frequency and summed by the broadcast transpose (one reduction over B), then flow
  through the gather transpose — same association as the vmapped layout. `_signal_and_noise`
  now receives `carrier_entries` and static `carrier_size` instead of `carrier`.
  `_map_frequency_chunks` takes a tuple of row arrays (padding each identically).
- Hypothesis: restores strict gradient agreement (coordinate 161) while keeping candidate 1's
  forward/gradient/memory gains; extra cost is a few small broadcasts (≈ 101×N complex).
- Remaining risk: other closure constants (`signal_matrix`, `noise_matrix` bases, index arrays)
  do not depend on optimized parameters, so they should produce no accumulated cotangents.
  XLA reduction order is still not guaranteed bitwise identical.
- SHA `aa7c3f93b89fd7149eca1a4303c817459c0db676`.
- Screen `5a06505a3c984268bd488907a5f2df01` (request `670f0cb7a206425b82b9319d109d4ef2`): first-run
  21.782536 s, compile/lower 10.987, forward exec 9.002, gradient exec 0.683, RSS 7272856 KiB.
- Full `f226b47b58644cf5b408f8eb82638c42` (request `a734cf365cd04f78bac00f649730fefc`): **official
  PASS, strict FAIL**. First-run 21.797833 s; imports 0.295, build 0.835, forward lower 0.838 /
  compile 7.773, forward exec 9.052, gradient lower 0.188 / compile 1.861, gradient exec 0.702;
  compile/lower total 10.908; warm median 10.068 s (forward 9.387, gradient 0.683); RSS 7311336
  KiB; job wall 78.68 s.
- Comparison: all physical outputs exact; gradient rel L2 9.18e-10, max abs 5.61e-5; same single
  failure at index 161 (candidate −29.61289475536929 vs candidate 1 −29.612894755369226 — identical
  to ~1e-14). **Hypothesis rejected**: carrier closure accumulation order is not the source.
- Re-diagnosis: parent gradient error vs baseline was 4.55e-13 max abs; candidates 1–2 show
  rel L2 ~9e-10 across the whole gradient, so per-frequency reverse computation differs. Since the
  forward is bitwise identical, the difference is in reverse-only kernels (contraction transposes,
  transposed triangular solves, cotangent scatters). Leading suspicion (unverified, no HLO):
  with k=1 every inner batch dimension has size 1 and XLA's simplifier removes the degenerate
  dimension, selecting a different (unbatched) dot/solve lowering than the batched parent.
  Index 161 (laser power) is a small entry (−29.6 vs gradient norm 7e4) produced by heavy
  cancellation, so it amplifies rounding differences most.

### Candidate 3 — k=2 (padded to 102 rows)
- Change vs candidate 2: only `FREQUENCY_CHUNK_SIZE = 2`. 51 loop iterations; the final block
  repeats frequency 101 once and the duplicate is sliced off (≈1% extra solve work).
- Hypothesis: a non-degenerate inner batch keeps the parent's batched kernel lowering in the
  reverse pass, restoring strict gradient agreement, while blocks of 2 (≈18 MB per matrix copy)
  retain most of candidate 1's cache/memory benefit. Expect forward exec slightly above 9.0 s
  (padding), peak RSS modestly above 7.3 GB.
- If strict still fails at the same magnitude, batching granularity per se changes reverse
  rounding; then record that the operator is only official-check-qualified at tested values, or
  test whether the residual difference lies in the parameter-cotangent reduction.
- SHA / runs: pending.
