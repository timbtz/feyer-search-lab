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
- SHA: (assigned by supervisor)
- Status: submitted for screen then full. No local run. Timings, memory, strict outcome unmeasured.
- Next decision: if forward execute/RSS drop and strict passes, try k=4/8 (padding) to trade
  per-iteration overhead; if forward/gradient regress, try k=16 or record obstruction.
