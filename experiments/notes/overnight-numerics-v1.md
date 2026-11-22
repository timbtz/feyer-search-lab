# overnight-numerics-v1: stable assembly and numerical execution lane

- Branch `explore/overnight-numerics-v1`, seed `53f38d342c3228c052785e8c9d63b6ce9c832dd1`.
- Deadline 2026-11-22 09:27:44 UTC (epoch 1795339664).
- Seed audit (support, not a final cohort): large median 0.986991538 s (0.997, 0.987, 0.986),
  aLIGO median 0.626026371 s. Seed grid phases: forward exec 181.08 ms, gradient exec 187.44 ms.
- Tooling note: this managed session has file tools only (no shell), so no local profile or
  numerical run was possible; every number below comes from evaluator feedback.

## Source inspection of the hot path (`HOST_PASS = True`, `differometor/host_pass.py`)
Large setup: signal 751x751 (2533 structural nnz), carrier 286x286, 101 signal rows, 1 carrier row,
D = 1 noise detector.
- The forward callback assembles everything (parameter expansion, all carrier/signal/noise component
  values, carrier factor + refined solve), then per signal row: factor, refined A^H solve, noise
  product, refined A solve with 1 + D right-hand sides.
- The backward callback (the whole "gradient" phase) **re-ran the complete `_assemble`**: all
  component evaluations again (101 signal rows, carrier, noise), the carrier factorization again
  and the refined carrier solve again. The carrier was then **factored a third time** for the
  carrier adjoint solve.
- Signal-factor reuse between forward and backward was gated by a blake2b digest of the full
  (101, nnz) coefficient array, i.e. ~4 MB hashed once in the forward and once in the backward.
- `SystemPlan.backward` evaluated every component's primal outputs inside `function_jacobian` and
  threw them away, and scattered output cotangents with 2-D `np.add.at` over all writes
  (101 x writes elements), although only last writes have nonzero cotangents.

## Candidate 1: consume the forward's assembly state in the backward (no numerical change intended)
- `host_forward` stores the assembly state (incl. carrier and signal SuperLU factors) under a digest
  of the small assembly inputs (parameters, sweep values, three base value vectors; plus plan key).
  `host_backward` pops it when the digest matches, else reassembles and refactors as before. The
  store is cleared on every forward/backward; each forward still assembles and factors afresh.
- The 4 MB coefficient digests are gone (coefficients are deterministic in the digested inputs).
- Carrier adjoint solve reuses the forward's carrier factorization.
- `function_jacobian(..., with_outputs=False)` skips the unused primal evaluation (Jacobian code path
  unchanged; `host.py` custom JVP still uses the default).
- Output-cotangent scatter restricted to last writes; plain assignment when those read distinct
  component outputs (checked once per plan), `np.add.at` otherwise. Difference vs seed only possible
  in the sign of exact zeros (x + 0 vs assignment).
- Expected: gradient exec phase falls (removed re-assembly, carrier re-factor x2, two hashes,
  scatter); forward exec roughly unchanged (one 4 MB hash removed). All outputs and gradients should
  be bitwise identical to the seed apart from signed zeros. Unmeasured until evaluator feedback.
- SHA `e4b3509cf9b5c630b057175b139b44db05b08195`, dual request `9a08fddaa9cd48a8b26a4a09478c7e33`.
  Official PASS on all 3 grid and 3 aLIGO fresh processes. Arrays bitwise identical to the seed
  (grid arrays sha 5124476e..., aLIGO 75df8515... = seed references; strict-vs-seed 0 failures,
  gradient max abs diff 0.0); generalization 14/14 cases identical to the seed. Strict vs pristine
  fails exactly as the seed does (pre-existing: grid signal 131, gradient 3, loss 1; rand1/rand3 etc.).
  - Grid first run: 0.98762, 0.95325, 0.98992 s (median 0.98762, range 3.7 %). Seed audit median
    0.98699 => no total gain visible; total noise (imports 0.274-0.303 s) exceeds the phase gain.
  - Grid gradient exec: 173.2, 170.5, 172.3 ms (seed grid-1 187.44 ms, single sample) => ~-15 ms.
    Grid forward exec: 179.4, 178.3, 209.5 ms (seed 181.08; third sample noisy).
  - aLIGO first run: 0.67145, 0.66687, 0.63206 s (median 0.66687; seed audit median 0.62603).
    aLIGO gradient exec 25.3, 25.3, 25.1 ms (seed 28.66); forward 43.2 (noisy), 33.5, 32.8 ms (seed 33.93).
    The aLIGO total difference comes from imports/compile phases (e.g. forward compile 97.6 ms in
    sample 1), which this change does not touch; not attributable without paired parent runs.
  - Decision: numerically clean, small but consistent gradient-phase reduction; not a confirmed
    total improvement (no paired seed samples in the same window). Kept as parent for candidate 2.
    Source review: pending (`requires_source_review`).

## Candidate 2: row-batched refinement products (parent = candidate 1)
- Remaining phases are ~170-180 ms each for 101 rows, i.e. ~1.7 ms per row, dominated by the
  per-row Python loop: per row and per solve, an initial SuperLU solve plus up to 3 refinement steps,
  each issuing ~6 small NumPy calls for the residual product and 2 reductions for the stop test,
  for 2533 nnz x 1-2 columns.
- Change: `_solve_batch` keeps each row's SuperLU solves and each row's own stop test (at most
  REFINEMENT_STEPS, max|dx| <= 1e-14 max|x| per row; converged rows drop out), but evaluates the
  residual products (`_Products.apply_batch`, same products and same sequential `add.reduceat`
  segments as `apply`) and stop-test reductions for all still-refining rows at once. Forward:
  factor all rows, batched H solves, one batched noise-source product, batched N solves. Backward:
  batched T solves, coefficient/noise cotangent terms, noise transpose product and conj N solves;
  the shared noise-row cotangent is still accumulated row by row in order.
- Expected: forward and gradient exec phases fall (fewer Python-level NumPy calls); outputs expected
  bitwise identical to candidate 1 / seed (same per-row operations and reduction order). Unmeasured.

## Open numerical findings carried forward unchanged
Strict dense-reference flags (signal entries, gradients 33/161/180), uifo_rand1 2.04e-4 / uifo_rand3
5.81e-5 log-sensitivity vs dense, six unresolved grid FD coordinates (54, 59, 63, 136, 161, 163).
Candidate 1 is not intended to touch any of them.

## Next ideas (not yet evaluated)
- Exact identity: the covariance columns of the backward A^T solve equal t_bar * conj(w) (w is the
  forward's refined A^H solution, t_bar real), which would drop D columns from that solve. Numerical
  change (different rounding), needs strict comparison; gain probably small at D = 1.
- Measure refinement step counts per solve; only consider a different stop criterion with
  ill-conditioned/modulated evidence.
