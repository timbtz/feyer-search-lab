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
  bitwise identical to candidate 1 / seed (same per-row operations and reduction order).
- SHA `214b4fa7f2a68fb38464b4235780ee790c355f4e`, request `dba4a2c9f0d64e778b4cfdc21c343995`.
  Official PASS 3/3 grid + 3/3 aLIGO; arrays bitwise identical to the seed again (same SHAs;
  generalization 14/14 identical to seed).
  - Grid first run 1.10924, 1.01959, 1.03415 s (median 1.03415; sample 1 had imports 0.359 s).
  - Grid forward exec 216.2, 213.0, 214.3 ms; gradient 204.1, 203.1, 208.7 ms => both ~+35 ms
    slower than candidate 1 (179 / 172 ms). aLIGO: forward 31.9/31.8/32.0, gradient 23.1/23.7/23.0 ms
    (slightly faster than c1), aLIGO total median 0.62103 s.
  - **Rejected.** Mechanism disproved for the large setup: row batching (3-D gathers, `reduceat`
    along axis 1, stacking) costs more than the Python overhead it removes. Inference: the per-row
    loop is not dominated by NumPy call overhead; the backward (no factorization, 2 refined solves
    per row) costs ~1.7 ms per row, so the SuperLU triangular solves themselves (x1 initial + up to
    3 refinement corrections each) are the likely dominant cost. Reverted to candidate 1's loops.

## Candidate 3: fill-minimizing column ordering for the signal factors (parent = candidate 1 code)
- Hypothesis: triangular-solve and factor cost scale with nnz(L+U). The seed always uses COLAMD.
  For nearly structurally symmetric optical matrices, MMD on A^T + A often gives less fill.
- Change: per evaluation, the first signal row is factored with COLAMD and MMD_AT_PLUS_A; the
  ordering with smaller SuperLU `nnz` (nnz(L)+nnz(U)) is used for all rows of that evaluation (ties
  or missing attribute keep COLAMD). Every row is still factored afresh from its own values; partial
  pivoting and the refinement (steps, tolerance, residual against the original A) are unchanged.
  Ordering is selected from the actual factorization of each supplied setup, not by recognising it.
  Cost: one extra factorization per evaluation.
- Numerics: if MMD wins, results differ from the seed at rounding level (different elimination
  order before refinement). Strict vs seed and generalization must be inspected; if arrays are
  bitwise identical to the seed, either COLAMD won or `nnz` is unavailable (inconclusive).
- Parameter menu (implementation choice, not physics): `COLUMN_ORDERINGS` in host_pass.py; legal
  SuperLU values NATURAL, MMD_ATA, MMD_AT_PLUS_A, COLAMD. Default ("COLAMD", "MMD_AT_PLUS_A").
- SHA `bca5a246d9ab233a79daa691be9815cd6e048888`, request `3c2472328d6a4565af9d9a287fcb4805`.
  Official PASS 3/3 grid + 3/3 aLIGO. Arrays **bitwise identical to the seed** (grid 5124476e...,
  aLIGO 75df8515...; generalization 14/14 identical) => COLAMD was kept on every setup, either
  because it had the smaller fill or because `SuperLU.nnz` is not exposed. Inconclusive about MMD.
  - Grid first run 0.98164, 0.95484, 0.95280 s (median 0.95484, range 3.0 %); forward exec 178.4,
    178.0, 180.0 ms; gradient 169.7, 170.3, 175.2 ms (same as candidate 1).
  - aLIGO first run 0.62619, 0.62670, 0.62282 s (median 0.62619); forward 33.0/32.6/32.6 ms,
    gradient 24.9/25.4/25.1 ms.
  - Decision: no effect; reverted (extra factorization and code without benefit).

## Policy change after three unconfirmed submissions (c1, c2, c3)
- Back on the strongest numerically clean parent: the source is again candidate 1's
  mechanism (e4b3509); the only difference is cosmetic whitespace in one line.
- Pooled evidence for the candidate 1 mechanism (c1 and c3 runs, identical execution code paths
  apart from c3's one extra factorization): grid first run 0.98762, 0.95325, 0.98992, 0.98164,
  0.95484, 0.95280 s (median 0.9682); gradient exec 170.5-175.2 ms in all six vs seed 187.44 ms
  (one audit sample). Admitted seed cohort 411b2326: grid 1.00588, 0.97606, 0.98087 s (median
  0.98087); aLIGO 0.62757, 0.62321, 0.62795 s. Candidate aLIGO medians 0.6669 (c1, compile/import
  noise in sample 1), 0.6261 (c3). The ranges overlap; a paired, interleaved seed-vs-candidate
  run is required before any claim.
- Requests to the supervisor / coordinator:
  1. Paired interleaved fresh-process runs (>= 5 each) of seed 53f38d3 and this restored candidate 1
     source, both benchmarks, plus independent source review of the candidate 1 diff.
  2. A diagnostic run (not a candidate) of host_forward / host_backward on the grid setup with
     cProfile and a histogram of refinement corrections per `_solve` call (steps taken, final
     max|dx|/max|x|), plus SuperLU `nnz` for COLAMD vs MMD_AT_PLUS_A on one signal row. Without it
     the next solver mechanism (refinement work, ordering, pivot threshold) would be another blind
     guess. Managed agents in this session have no shell, so they cannot run it themselves.
- Restored candidate 1 source: SHA `b2943970c6108d9ceeedc7394413b0854d6f5168`, request
  `544787cb74bf424e88f0f97c1a0f68f1`. Official PASS 3/3 + 3/3, bitwise identical to the seed,
  generalization 14/14 identical. Grid 0.98597, 0.94583, 0.94994 s (median 0.94994); gradient
  172.1, 172.0, 170.1 ms; forward 180.7, 175.2, 176.0 ms. aLIGO 0.62057, 0.62483, 0.62017 s
  (median 0.62057; flagged "aligo regression > 2 %" only against the new incumbent 2b4654f, whose
  aLIGO median is 0.5601 because of its import/wrapper changes, not because of this mechanism).
  The gradient-phase reduction has now reproduced in 9/9 samples (170.1-175.2 ms vs seed 187.44).

## Candidate 4: candidate 1 mechanism on top of the admitted incumbent 2b4654f
- Provenance: the incumbent `2b4654f294414590f760fe972edd69f6774fe9e1` (evaluation b986ad11,
  approved independent source review, grid median 0.91127 s, aLIGO 0.56009 s, bitwise identical to
  the seed) changes imports and the JAX-side wrapper only: lazy `visualize_setup`, deferred
  `jax.scipy.linalg` import (dense path only), static parameter-row layout gathers/scatters
  (`ParameterLayout` in host_pass.py, `_static_take`/`_static_set` in simulate.py), and an explicit
  gather in `SparseSystem.base_values`. I applied its supplied diff verbatim to this branch
  (`__init__.py`, `simulate.py`, `sparse.py`, and the `ParameterLayout`/`HostPlan` parts of
  `host_pass.py`). It does not touch `host_forward`/`host_backward`/`SystemPlan.backward`.
- My lane's change on top (unchanged from candidate 1): backward consumes the forward's assembly
  state and carrier/signal factorizations (digest of the small assembly inputs), no 4 MB
  coefficient hashes, no discarded primal evaluation in Jacobians, last-write-only cotangent scatter.
- Expected: grid gradient exec about -15 ms against the incumbent; everything else as the incumbent;
  arrays bitwise identical to the seed. Needs paired incumbent-vs-candidate runs before a claim.
- Evidence so far on where the time goes: the backward phase (no factorization; two refined solves
  plus small products per row) costs ~1.7 ms/row, about the same as the forward (factor + two
  refined solves). So factorization is a small share; triangular solves + refinement dominate.

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
