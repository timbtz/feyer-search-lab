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
- SHA `34e637d1e0a1dbf518697c19b160fe7799d3a8b2`, request `ff20917c53cb40478b0a4aacd84181da`.
  Official PASS 3/3 + 3/3; arrays bitwise identical to the seed; generalization 14/14 identical.
  - Grid 0.92547, 0.89466, 0.87557 s (median 0.89466; incumbent cohort 0.95429, 0.91127, 0.90719,
    median 0.91127). Forward compile 32.8-33.0 ms (incumbent effect); forward exec 188.7, 179.0,
    177.3 ms; gradient exec 174.1, 181.5, 168.9 ms.
  - aLIGO 0.57678, 0.55640, 0.55742 s (median 0.55742; incumbent 0.56009).
  - Not promoted: needs source review; ranges overlap (candidate max 0.9255 > incumbent min 0.9072).
    Best numerically clean revision of this branch. Paired runs vs 2b4654f still requested.

## Candidate 5: drop the covariance columns from the backward A^T solve (parent = candidate 4)
- Exact identity: covariance cotangent x_bar = t_bar conj(s) (t_bar real per row/detector). The
  forward solved A^H w = s; conjugating gives A^T conj(w) = conj(s), so the A^T solution for those
  columns is r_cov = t_bar conj(w). The backward now solves only the signal column (1 instead of
  1 + D right-hand sides) and forms r_cov from the forward's refined w.
- Numerics: not bitwise. w carries the forward refinement (same factor, same tolerance); the signal
  column's refinement stop test no longer includes the covariance column. Expected differences vs
  seed at refinement level (~1e-14 relative); strict-vs-seed (rtol 1e-7) should pass. Any larger
  difference, especially on uifo_rand1/rand3, voyager or gradient indices 33/161/180, means reject.
- Expected: grid gradient exec falls by the cost of one RHS column in each of the 101 refined
  T solves (unmeasured; plausibly 10-25 ms). aLIGO proportional.
- SHA `5bbb91e38ff993a10486f296a738860339cd05e0`, request/evaluation `2c7810bfe84648299731e98a6bb133ae`.
  **Confirmed improvement, admitted campaign best** (approved independent source review).
  Official PASS 3/3 + 3/3. Strict vs seed PASS: grid gradient relL2 9.7e-10 (max abs 5.65e-5),
  aLIGO gradient relL2 6.5e-13, log-sensitivity error 0.0; generalization 14/14 pass vs seed;
  pristine profile unchanged (grid signal 131 / gradient 3 / loss 1; rand1 2.04e-4, rand3 5.81e-5).
  - Grid 0.88236, 0.85061, 0.85267 s (median 0.85267; range non-overlapping with 2b4654f's).
    Gradient exec 140.6, 142.3, 139.4 ms (candidate 4: 169-182). Forward 184.7, 180.1, 179.6 ms.
  - aLIGO 0.55571, 0.55179, 0.55841 s (median 0.55571); gradient 24.2, 23.0, 23.4 ms.

## Candidate 6: Hermitian noise source -> no second backward solve (parent = candidate 5)
- After candidate 5 the backward still does a refined A-solve per row for the noise adjoint:
  g = A^-1 conj(w_bar), w_bar = N^T sources_bar = t_bar N^T conj(w), so conj(w_bar) = t_bar N^H w.
  If N^H = N this equals t_bar N w = t_bar * (forward sources), whose solution the forward already
  computed: g = t_bar * cov. So adjoint = t_bar conj(cov) and the second solve disappears.
- Generic, measured trigger: per evaluation and noise row, `_is_hermitian` compares every structural
  noise entry with the conjugate of its transposed entry (static transpose index per pattern;
  unpaired entries must be ~0) with relative tolerance 8 eps * max|N| (`HERMITIAN_TOLERANCE`).
  Non-Hermitian, non-finite or augmented noise values keep the explicit solve. Overhead: one vector
  comparison on ~272 entries per evaluation. Whether it triggers on grid/aLIGO is not known to me
  (no shell): if gradient exec stays ~140 ms the check did not trigger (correct, just no gain).
- Numerics: not bitwise vs candidate 5 when triggered (forward covariance refinement replaces a
  fresh refined solve; tolerance-level N vs N^H). Expected refinement-level differences.
- SHA `9de89099ee118ba4c559b9fdfbdb433ea5995f65`, request `6a58fcea615240de86d57273c9d0f057`.
  Triggered on both setups (arrays changed: grid 108746cc..., aLIGO e82569f4...). Official PASS
  3/3 + 3/3; strict vs seed PASS (grid gradient relL2 7.5e-10, max abs 4.4e-5 -- closer to the seed
  than candidate 5's 9.7e-10; aLIGO 2.7e-14); generalization 14/14 pass vs seed; pristine profile
  unchanged.
  - Grid 0.85607, 0.81876, 0.82230 s (median 0.82230 vs c5 0.85267). Gradient exec 109.3, 109.1,
    111.2 ms (c5 ~140). Forward 181.7, 179.3, 182.4 ms.
  - aLIGO 0.54800, 0.54971, 0.54957 s (median 0.54957); gradient 18.5, 18.5, 18.7 ms (c5 ~23.5).
  - Not promoted yet: needs source review; first grid sample (imports 0.293 s) overlaps the incumbent
    minimum 0.8506. Paired runs vs 5bbb91e requested.

## Candidate 7: signal-column cotangent in span of conj(s) -> no backward solve (parent = candidate 6)
- The readout `signal_detector` is linear in the signal: conj(c_p) sig_upper[p] + c_p sig_lower[p],
  so its cotangent is y_bar * [conj(c_p), c_p] at the port entries. The noise selection vector for
  a detector at that port is s = [sel c_p, conj(sel c_p)]; for real sel, conj(s) is proportional to the
  cotangent. Then A^T r = alpha conj(s) has r = alpha conj(w) with the forward's refined w.
- Generic, measured trigger: per row and detector, least-squares alpha and acceptance only if
  max|signal_bar - alpha conj(s_d)| <= 8 eps max|signal_bar| (`_collinear_coefficient`). A zero
  cotangent gives r = 0. Otherwise the refined T-solve is kept. Nothing depends on which readout or
  setup is used; it is a property of the supplied cotangent.
- If it triggers on grid, the backward has no signal-system solves left (only the carrier adjoint),
  so gradient exec should fall well below 110 ms. If arrays equal candidate 6 bitwise, it did not
  trigger (e.g. qhd phase makes sel complex, or a differential readout).
- SHA `ee4fea28c04d482566be16e916b609d7c6a99e5e`, evaluation `e4f7b59d3b094a8e9c6dd41263cab78e`.
  **Confirmed improvement, admitted campaign best** (approved independent source review, which
  covered all mechanisms of candidates 1, 5, 6, 7 and the ported incumbent diff).
  Official PASS 3/3 + 3/3; strict vs seed PASS (grid gradient relL2 8.2e-11, aLIGO 1.3e-15);
  generalization archive byte-identical to the seed reference (14/14); pristine profile unchanged.
  - Grid 0.82248, 0.80158, 0.79442 s (median 0.80158; range non-overlapping with 5bbb91e).
    Gradient exec 85.4, 86.9, 84.6 ms (c6 ~110); forward 177.4, 181.2, 182.9 ms.
  - aLIGO 0.55162, 0.54856, 0.54472 s (median 0.54856); gradient 14.5, 14.4, 14.4 ms.
- Cumulative in this lane vs seed (single cohorts, not paired): grid gradient exec 187 -> 85 ms.

## Candidate 8: solve-free backward rows batched + unique-index scatters (parent = candidate 7)
- After candidate 7 the common backward path has no signal solves; what remains per row is ~15 small
  NumPy calls (gathers over 2533 nnz x 2 columns) x 101 rows, plus `SystemPlan.backward`'s per-slot
  `np.add.at` scatters into the parameter rows.
- Change 1: if every row takes both shortcuts (checked first, exactly as before), the row arithmetic
  runs once for all rows with the same elementwise operations and same last-axis reductions; the
  shared noise-row cotangent still accumulates row by row. Otherwise the original loop runs.
- Change 2: in `SystemPlan.backward`, a slot whose parameter columns are distinct across the group's
  rows (checked once per plan) uses `rows_bar[:, cols] += values`, which performs the same single
  addition per element as `np.add.at`; repeated columns keep `np.add.at`.
- Expected: outputs bitwise identical to candidate 7 (up to signed zeros); grid gradient exec below
  ~85 ms. Unlike candidate 2 there are no SuperLU solves or `reduceat` products in the batched part.
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

## Codex continuation: candidate 8 feedback and preserved turn 10

- Session remains `overnight-numerics-v1`; inherited Claude thread
  `57c7de44-c9ff-460f-88f1-9ffa79a35479`. Fixed deadline remains 2026-11-22 09:27:44 UTC.
  Codex continuation has shell access. No agents, installs, commits, network calls or official
  workload executions were used. Local synthetic inspection uses the existing read-only
  `.lab/venv-topology-smac` Python (NumPy/SciPy, no JAX), not the official timing environment.
- Candidate 8 SHA `f950024546139ea943c5ddeda948e015aef235d2`, request
  `a3a819f27eab41379d9ecf9fa05c0092`: all six official runs passed.
  Grid samples 0.8341007065, 0.8038977999, 0.7956203520 s; median 0.8038977999,
  range 0.7956203520–0.8341007065 s. Forward 185.06/183.26/181.00 ms;
  gradient 85.82/86.95/85.48 ms. No gradient reduction versus candidate 7's 84.6–86.9 ms.
  aLIGO samples 0.5483614039, 0.5439532716, 0.5498941857 s; median 0.5483614039,
  range 0.5439532716–0.5498941857 s; gradient 13.24/13.64/13.61 ms.
  Peak sampled RSS: grid up to 609701888 B, aLIGO up to 306778112 B,
  generalization 841793536 B. Other-host contention not excluded.
- Seed comparisons pass for all physical arrays and gradients on both benchmarks and 14 extra
  cases. Grid gradient max difference 5.68635e-6, relL2 8.18145e-11 versus initial seed;
  aLIGO 3.63798e-11, relL2 1.29494e-15. Pristine comparisons still fail: grid signal 131,
  gradient 3, loss 1; aLIGO loss 1; random-topology sensitivity disagreements persist.
  Generalization top-level `passed=false` reflects the pristine comparison; its seed comparison
  passes. No new numerical regression is reported. Source review was not supplied.
- Correction to earlier byte-identity shorthand: initial-seed generalization archive in this
  receipt is `a64192e8...`, whereas candidate 8 is `4a1ca4c5...`. Passing tolerance checks do
  not establish byte identity to the original seed. The separately labelled artifact reference
  equals the candidate archive; do not confuse these references.
- Decision: reject candidate 8 as an unconfirmed speed experiment. Its ranges overlap candidate
  7 and large median is slightly slower. Do not repeat whole-row batching. The partial turn 10
  edit had already removed both candidate 8 changes. Verified that the resulting simulator
  sources were exactly candidate 7 (`git diff ee4fea2 -- differometor` empty) before new edits.
  History is preserved; no reset or cross-lane transfer occurred.

## Candidate 9: prepare residual-product coefficients once per refined solve

- Scientific parent/source is admitted candidate 7 `ee4fea28c04d482566be16e916b609d7c6a99e5e`;
  Git parent is feedback commit `a1ab6a8` after candidate 8. Candidate SHA/job IDs pending
  supervisor commit/evaluation. Only production change versus candidate 7 is in host_pass.py.
- Concrete redundant work: `_Products.apply` in each refinement iteration formed N products in
  CSC order, then gathered the entire (nnz, RHS-count) product into stable row order. H products
  conjugated the same coefficients every iteration. `_solve` can perform three iterations with
  unchanged coefficients; the solution vector changes each time.
- Add one topology-derived `row_columns` index array. `_Products.bind` prepares row-ordered
  coefficients for N, conjugated coefficients for H, or unchanged coefficients for T once per
  solve. Its callable still gathers the current solution, multiplies complex128 entries and
  uses the same stable `np.add.reduceat` segments in the same order. The original `apply` remains
  for one-off products. Coefficients stay local to a solve; factors, matrices and outputs are
  still recomputed each forward. No zero-valued entry or derivative is removed.
- Allocation accounting, not elapsed-time evidence: for m nonzeros, K RHS columns and r
  corrections, N previously copied r*m*K complex products in permutations; now it copies m
  coefficients once. H conjugations fall from r*m to m entries. At the recorded grid m=2533,
  K=2, r=1..3 this removes 40528..202640 bytes of permutation allocation per N solve.
  This is generic in m/K/r, not a dispatch condition. Closure/setup overhead may erase the gain,
  especially for one correction or a small setup. No claimed millisecond improvement yet.
- Refinement limit 3, tolerance 1e-14, stop criterion, SuperLU ordering, solve RHS and correction
  arithmetic are unchanged. Both fallback/shortcut derivative paths remain candidate 7's.
- Local validation: `experiments/notes/overnight-numerics-products-check.py` extracts only the
  actual `_Products` and `_solve` AST definitions, comparing candidate against committed
  candidate 7. 144 products and 144 solves are byte-identical, with identical refinement counts
  (111 one-correction, 33 two-correction). Sizes 5/13/37, N/T/H, vector and 1/2/4 RHS, ordinary
  and badly scaled matrices, perturbed values and structural zero entries. Maximum product
  difference against independent dense multiplication divided by max(1,max|dense result|)
  was 4.3028432462288176e-16. This is kernel evidence, not an optical/gradient certificate.
  `git diff --check` passes. No local official benchmark was run.
- Supervisor next step: both unchanged full official benchmarks on the new exact SHA, all saved
  arrays/gradients versus candidate 7 and seed, 14-case diagnostics including modulation and
  difficult random cases, independent review. Expect byte identity to candidate 7 on this
  evaluator; investigate any difference rather than labelling it rounding. For a promising phase
  result, obtain matching paired fresh-process repeats versus candidate 7. Keep candidate 7 as
  strongest admitted revision unless the new exact revision clears all acceptance requirements.
- Existing strict-reference and finite-difference questions above remain unresolved. First-order
  reverse-only compatibility is unchanged. This submission does not claim a universal certificate.
