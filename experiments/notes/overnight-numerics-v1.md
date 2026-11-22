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

### Candidate 9 feedback (2026-11-22, Codex continuation)

- SHA `5dde09458eadb2721b44ad2159a63f3a3ea1ffa1`, dual evaluation
  `87a7fb6f3777432fae00df6e6197f6e4`; grid-1/2/3 and aligo-1/2/3 all official PASS.
  Large samples: 0.8113777526, 0.7860681415, 0.7801716551 s;
  median 0.7860681415, range 0.7801716551–0.8113777526 s (3.97%).
  aLIGO samples: 0.5426084753, 0.5584980734, 0.5419364572 s;
  median 0.5426084753, range 0.5419364572–0.5584980734 s (3.05%).
- Forward phase large: 171.31, 169.78, 170.00 ms, versus admitted candidate 7's
  177.4/181.2/182.9 ms. Gradient 85.45/86.61/84.44 ms is unchanged within observed spread.
  Large import times 289.91/263.78/263.74 ms; build 72.25/73.74/68.26 ms. The first sample
  remains included: total ranges overlap. aLIGO forward 32.68/32.38/31.23 ms; gradient
  14.54/14.59/14.50 ms. Complete medians are 15.51 ms and 5.95 ms below candidate 7,
  respectively, but source review and paired confirmation are still missing.
- All six official output archives have the same SHA as candidate 7 (grid `112c040763a3...`,
  aLIGO `9c1ce936bf40...`), verified against the checked-in exact-revision receipts.
  Seed comparison passes for every array/gradient and all 14 generalization cases. Seed grid
  gradient max difference 5.68635e-6 / relL2 8.18145e-11; aLIGO 3.63798e-11 / 1.29494e-15.
  No newly reported pristine discrepancy: grid 131 signal / 3 gradient / 1 loss mismatches,
  aLIGO 1 loss mismatch; rand1/rand3 sensitivity log errors remain 2.03610e-4 / 5.81009e-5.
- Investigated changing generalization archive hashes. The exact evaluator gencheck.py
  (SHA `a1110a4efe81c370e198085b605fbf7409f6b1de47c968d32c9bda747a7d3094`) is available
  read-only at `.lab/transfer-audit-20261122/fastest/prior/gencheck.py` outside this worktree.
  Lines 188 and 203 store JSON timing strings inside each NPZ archive. Therefore archive hash
  changes alone are not evidence of changed physical outputs. Physical arrays themselves are
  not downloaded in the local campaign evidence; exact parent-vs-candidate generalization
  element comparisons excluding `/timings` remain requested. Do not infer exact equality from
  the artifact self-comparison, nor infer a numerical regression from the full archive hash.
- Peak sampled RSS: large 530681856 B, aLIGO 306753536 B, generalization 885895168 B.
  One CPU (2), thread limits one; other-host contention not excluded. Source review null;
  `confirmed_improvement=false`, reasons source review and overlapping ranges.
- Decision: retain as promising experimental parent for one narrower allocation refinement.
  Candidate 7 remains admitted best. Request at least five paired fresh runs of candidate 9
  and candidate 7, both official workloads, plus independent source review. Two submissions
  since candidate 7 have no admitted total gain; if the next also lacks repeat-supported gain,
  stop this allocation mechanism and return to admitted source or obtain the requested profile.

## Candidate 10: solve-local residual scratch reuse (parent candidate 9)

- Candidate SHA and evaluation IDs pending supervisor. Production changes only host_pass.py;
  no other-lane transfer. This is candidate 9 plus a local workspace for residual products.
- `_Products.bind(values, trans, rhs_shape)` allocates contribution, reduced-row and result
  buffers once per `_solve`. Each correction fills contributions with `np.take`, multiplies
  in place, performs the same `np.add.reduceat` with an output buffer, then assigns present
  rows into the result. Missing rows remain zero. The result is consumed immediately by
  `rhs - product(solution)` before the next call overwrites it. All buffers are private to one
  solve, independent of other evaluations; the static plan retains no numerical scratch.
- `np.take(..., mode="clip")` avoids its default exception-safety output buffer. This does not
  alter indexing: the indices are topology coordinates and are in bounds for the factor's
  solution size. The initial factor solve validates RHS size first. No fixture dispatch,
  structural zero pruning, changed corrections or tolerance, or different reduction order.
- Source allocation count: candidate 9 creates gather, product, reduced and result arrays on
  each residual (four arrays). Candidate 10 prepares three arrays once; take/multiply/reduce
  write into them. NumPy may allocate internal temporaries for noncontiguous inputs, so this
  is an explicit-array count, not a measured allocator profile or a guaranteed timing gain.
  The one-correction case may see little benefit; small-case overhead needs official checking.
- Synthetic checker extended for repeated products with changed vectors, missing rows and
  columns, plus ill-conditioned Hilbert systems. 306 product checks and 156 refined solves
  match committed candidate 7 byte-for-byte. Same correction counts: 111 with one, 33 with
  two, 12 with all three. The independent dense-product scaled error maximum remains
  4.3028432462288176e-16. No official workloads or local timings were executed. Diff check passes.
- Request both official benchmarks on the new exact SHA, complete physical/gradient diagnostics
  and generalization checks versus candidate 9 and candidate 7, independent review, and paired
  fresh timing confirmation if promising. If worse than candidate 9, discard only this scratch
  refinement. Candidate 9 must still earn admission separately; no warm-only or cross-cohort
  timing claim is promoted. All previously unresolved numerical/transform caveats persist.

## End of residual-allocation hypothesis: candidate 10 feedback and handoff

- Candidate 10 SHA `10e63deac66a5c8b4d5265efe7b97e1e8c0f0b6d`, evaluation
  `bfbee01b11c64b0d9b94f342cbf7a84c`. Official grid-1/2/3 and aligo-1/2/3 all PASS.
  Large samples 0.8686032258, 0.7747887578, 0.7814419530 s; median 0.7814419530,
  range 0.7747887578–0.8686032258 s, relative range 12.01%, above the 10% team threshold.
  aLIGO samples 0.5410033129, 0.5430320539, 0.5427588578 s; median 0.5427588578,
  range 0.5410033129–0.5430320539 s (0.374%). No combined score.
- Large forward 221.80/162.61/168.06 ms; gradient 83.97/83.64/84.89 ms. The first forward
  sample is retained. Its cause is unknown; do not attribute it to contention or allocation
  without a profile. aLIGO forward 32.15/31.55/33.02 ms, gradient 14.30/14.67/14.19 ms.
  Imports large 289.76/263.57/262.55 ms; compilation remains in the usual range except
  first sensitivity lower 29.66 ms. Warm runtimes do not decide this experiment.
- All official output archive hashes still equal candidate 7. All physical array and gradient
  comparisons to the seed pass, including 14 additional cases. Gradient seed differences and
  the pristine mismatch profile are unchanged from candidate 9. Generalization archive includes
  timings, as established above; no full-archive byte-identity claim. Strict pristine comparisons
  and six grid finite-difference coordinates remain open; no universal correctness claim.
  Peak sampled RSS: grid 629415936 B; aLIGO 305397760 B; generalization 808505344 B.
  CPU2 and single library threads; other-host overlap is not ruled out. No source review supplied.
- Decision: three consecutive unconfirmed submissions (8/9/10) end this implementation search.
  Candidate 8 did not reduce large gradient time; candidate 9 consistently lowered forward time
  in its cohort but complete-run ranges overlap; candidate 10 has an unstable large cohort.
  Do not produce another residual-allocation variant from these numbers. All commits remain.
- Restored only `differometor/host_pass.py` to this branch's admitted candidate 7 content, without
  resetting Git history. All `differometor/**` source now equals `ee4fea2` exactly. This restoration
  is a bookkeeping submission, not a new optimization. Supervisor may evaluate the restored SHA
  on both official benchmarks as a current recalibration before ending this hypothesis.
- The synthetic checker now accepts `--candidate-ref` to inspect preserved candidates 9/10
  without editing production source. Default checks restored source. Tests remain small synthetic
  kernels, excluding all official workloads and elapsed-time comparisons.
- Next coordinator actions, before further changes in this lane:
  1. Obtain independent source review and at least five paired/interleaved fresh-process dual
     runs for candidate 9 `5dde094` versus admitted `ee4fea2`. If useful, separately pair candidate
     10 `10e63de` against 9 to investigate its spread. Retain every sample and resource record.
  2. Profile host forward/backward under the evaluator's fixed environment on the supplied setup,
     separately from official timing runs. Attribute `_assemble`, `_factor`, `_solve`, residual
     product, `SystemPlan.backward`, `function_jacobian` and scatter costs. Record correction-count
     distributions, factor fill, allocations and first-forward variability. Do not alter harnesses.
  3. A distinct next hypothesis is sharing primal component intermediates across derivative slots:
     `function_jacobian` calls the full `HOST_FUNCTIONS[f]` once per slot, including repeated primal
     transcendental operations. Source establishes repetition, but its share of the remaining
     ~85 ms gradient phase is unmeasured. Require that profile before introducing a derivative
     evaluator; preserve structural-zero derivatives, complex conventions and undefined-domain
     behavior. This idea is not implemented or timed.
- Handoff session `overnight-numerics-v1`; inherited thread
  `57c7de44-c9ff-460f-88f1-9ffa79a35479`. Stop is for this hypothesis, not the campaign or budget.
  The authorized campaign deadline remains 2026-11-22 09:27:44 UTC. Strongest admitted source
  remains candidate 7; candidate 9 is an unadmitted promising trial, candidate 10 unconfirmed.

## Restored-parent recalibration and new direction (2026-11-22)

- Restored simulator SHA `cb04c3c2b5aa7e6ff2b44b298a102e7511aee81e` has source equal
  to admitted candidate 7. Evaluation `d12a722629874f57a7f578a9c0b981e7`, grid-1/2/3 and
  aligo-1/2/3: all official PASS. This was a recalibration, not an optimization claim.
- Large fresh samples: 0.8287269529, 0.8084255047, 0.7973537017 s; median 0.8084255047,
  range 0.7973537017–0.8287269529. Forward 184.44/185.22/183.41 ms; reverse
  89.05/85.79/83.50 ms. aLIGO samples: 0.5420756359, 0.5420307629, 0.5428591091 s;
  median 0.5420756359, range 0.5420307629–0.5428591091. Forward 32.37/32.44/33.67 ms;
  reverse 14.22/14.22/13.83 ms. No paired phase delta establishes a gain.
- Official archives match candidate 7. All seed physical-array/gradient checks and 14 additional
  seed comparisons pass. Pristine discrepancies remain: grid signal/gradient/loss, aLIGO loss,
  and the documented random-case disagreements. Generalization archive timing metadata remains
  excluded from numerical conclusions. Raw remote arrays are not locally available; this inspection
  uses evaluator per-array reports, not a new independent array audit.
- Peak sampled RSS large 632836096 B, aLIGO 309452800 B, generalization 873349120 B.
  One logical CPU (2), single library threads, external overlap not excluded. No independent
  review or requested execution profile accompanied this feedback. No promotion expected.
- Residual-allocation exploration stays closed after three unconfirmed proposals. The following
  is a separate conservative source-level coefficient optimization, on restored admitted source;
  it does not introduce a new derivative evaluator or combine candidates 9/10.

## Candidate 11: share surface coefficient intermediates

- Candidate SHA and evaluator job IDs pending supervisor. Only production delta is
  `differometor/components.py::surface`; scientific parent is `ee4fea2`, recalibrated as `cb04c3c`.
- Source establishes repeated phase shifts for the left/right indices, left incidence cosine,
  and reflection amplitude square root in the three scalar coefficient helper calls. Surface now
  computes each shared intermediate once per invocation. Each coefficient keeps its original
  multiplication grouping, exponential arguments, and sign conventions. Right reflection and
  transmission deliberately retain their distinct Snell-law argument orders. No numerical values
  persist between invocations; no value-based pruning or topology/fixture dispatch is introduced.
- Target phases: forward component assembly and reverse `function_jacobian`, which invokes the
  surface separately for each differentiated slot. Under a seven-slot synthetic Jacobian, measured
  shim call counts change: sqrt 21->14, phase_shift 28->14, radians 56->35, cos 28->21;
  exp 21, sin 14, arcsin 14 unchanged. This is operation-count evidence, not a timed profile.
  The fraction of official forward/reverse spent in this component remains unmeasured. Benefit
  may be small; require fresh-process paired complete timings before claiming improvement.
- `experiments/notes/overnight-numerics-surface-check.py` executes source-derived component/dual
  definitions without JAX, against committed parent. Twelve synthetic array cases, 33 parameter
  rows each: unequal refractive indices, positive/negative frequency, complex perturbations,
  zero tuning/frequency/loss, reflectivity 0/1, loss 1, zero indices, grazing incidence and total
  internal reflection. Across four slot menus (including all seven), all 48 output/J/K comparisons
  pass; finite entries match bit-for-bit, nonfinite entries compare equal. Every slot is retained.
- Fourteen independent central-difference directions (real and imaginary for each input) at a
  nonsingular random point pass; maximum error scaled by max(1, derivative magnitude) is
  1.6010981992459505e-9. This is bounded local derivative evidence, not a certificate for ill-
  conditioned optical networks. Local existing NumPy environment only; no official workload,
  simulator benchmark, dependency installation, or timing run performed.
- The JAX dense path also sees the shared source. Its reverse accumulation graph may change
  even though host Dual arithmetic matched exactly. Request a small dense-versus-parent component
  value/VJP check under evaluator JAX, including unequal indices and zero tuning. Production
  host path still uses the same first-order Dual/J/K and scatter routines.
- Request both unchanged full official benchmarks on the new exact SHA, every saved output and
  gradient comparison against parent and seed, all 14 generalization cases including modulation,
  and independent source review. If promising, pair/interleave at least five fresh dual runs
  against restored parent under matching CPU/thread/resource policy. Keep all samples, phase
  deltas, peak RSS and overlap records. No change to refinement, package flags, JIT stages,
  physical design variables, imported other-lane code, or workload.
- Existing strict signal/gradient findings (33,161,180), rand1/rand3 sensitivity disagreements,
  six unresolved grid finite-difference coordinates and lack of whole-pass JVP/Hessian support
  remain explicitly unresolved. Candidate 7 remains strongest admitted until new evidence.

## Candidate 11 feedback and profiling handoff

- Candidate SHA `36be9bb71fb28d795acd689173d14a4851720ec4`; evaluation
  `9a02513386664f23b99efe5c95b8f882`. Both full official workloads pass all three fresh
  runs: grid-1/2/3 and aligo-1/2/3. No source review or paired parent runs accompanied feedback.
- Large samples 0.8293322213, 0.7968566921, 0.7953469604 s; median 0.7968566921,
  range 0.7953469604–0.8293322213 s. aLIGO samples 0.5493552908, 0.5450734869,
  0.5419835243 s; median 0.5450734869, range 0.5419835243–0.5493552908 s.
  Neither setup is combined into a score. Admission explicitly unconfirmed: overlapping large
  ranges and missing source review. The large median alone does not establish a stable gain.
- Large forward 182.627/178.738/178.500 ms; reverse 87.544/88.669/83.250 ms.
  Relative to restored-parent request d12a7226, unpaired median phase deltas are forward
  -5.704 ms, reverse +1.755 ms, imports -1.924 ms, build +0.974 ms. aLIGO forward
  33.261/32.475/32.704 ms and reverse 15.304/14.232/14.149 ms; corresponding unpaired
  median deltas +0.268 and +0.012 ms. These descriptive differences are not causal evidence.
  The component-operation reduction did not produce a clear reverse-phase improvement.
- All official saved-array archives match candidate 7 hashes. Seed comparisons pass every
  physical array and gradient, both official setups and all 14 generalization cases. Seed
  gradient differences remain large max 5.686350050382316e-6 / relL2 8.181451454702114e-11,
  aLIGO max 3.637978807091713e-11 / relL2 1.294943745154708e-15. Pristine mismatch counts
  and random-case log sensitivity errors are unchanged. Extra generalization is therefore
  seed-compatible but not pristine-passing. Raw archives remain remote; per-array reports and
  official hashes were inspected, not newly recomputed here. Generalization hashes include timing
  metadata and cannot establish physical byte-identity. Six grid FD coordinates remain unresolved.
- Peak sampled RSS large 533561344 B, aLIGO 294830080 B, generalization 954093568 B.
  CPU2, one library thread, no persistent cache; external contention not excluded. No infrastructure
  failure reported. Source review is null and universal correctness is not claimed.
- Decision: stop this source-level coefficient refinement pending attribution. Keep candidate 11
  as a preserved experimental revision, not a promoted parent. Restored components.py to admitted
  candidate 7 without resetting history; all production files again match ee4fea2. No new simulator
  candidate is proposed by this handoff, and another identical restoration benchmark is unnecessary.
- Added `experiments/notes/overnight-numerics-profile.py`: an opt-in diagnostic context for the
  supervisor's synchronized diagnostic driver. It wraps only host_forward/host_backward, profiles
  each invocation using cProfile inside its calling thread, records callback ordinal, function
  counts/self/cumulative times and success, and restores both functions on exit. No workload is
  defined or launched by this helper. It changes no validation, numerical inputs or returned outputs.
  Instrumentation overhead and pre-imports make resulting times ineligible for official comparison.
- Tested helper with small fake entry points: exact return-object identity, separate invocation
  ordinals, JSON serialization, exception propagation and restoration all pass. No optical run.
  Coordinator should load the helper and surround its existing diagnostic execution with
  `collect_host_profiles()`, synchronize all JAX outputs before leaving, and serialize the records.
  Use the fixed evaluator environment/resource policy. This has not been exercised under JAX
  locally (JAX is unavailable); verify callback coverage before interpreting results.
- Specific requested evidence before another implementation variant:
  (1) On admitted ee4fea2 and experimental 36be9bb, get first-forward/first-backward profiles;
      attribute _assemble, _factor, _solve, _Products.apply, SystemPlan.values/backward,
      function_jacobian and NumPy reductions/scatters. Do not add cumulative times of nested
      functions. Keep profiled diagnostics separate from unchanged official results.
  (2) Independent source review and at least five paired/interleaved fresh full dual runs for
      36be9bb versus ee4fea2 (or the byte-identical restored cb04c3c), retaining every sample.
      Prior candidate 9's paired-review request remains open; do not combine it with 11 by default.
  (3) Requested small JAX dense-component VJP check remains pending; host synthetic equivalence
      is established but is not blanket evidence for a modified JAX reverse accumulation graph.
- This stops the current hypothesis only. Session overnight-numerics-v1 and absolute deadline
  2026-11-22 09:27:44 UTC remain unchanged. Strongest admitted simulator remains candidate 7;
  all existing strict numerical and whole-pass JVP/Hessian limitations stay visible.

## Candidate 12: stream component Jacobian contraction into input cotangents

- Supervisor resumed after the profiling handoff and explicitly requested a concrete next
  implementation. No new evaluation or profile was supplied; candidate 11 feedback above remains
  the latest official evidence. Preserved edits from turn 15 are retained (restoration and profiler).
- Scientific parent is admitted candidate 7 `ee4fea28c04d482566be16e916b609d7c6a99e5e`.
  Components.py is restored exactly to that parent; the unconfirmed surface change from candidate
  11 is not combined. Candidate 12 SHA and dual job identifiers pending supervisor.
- New production delta: host.function_pullback evaluates the existing scalar-seeded Dual for
  each requested input slot, materializes its four linear/antilinear output derivatives, multiplies
  by output cotangents, reduces those four outputs and writes that input cotangent immediately.
  Two four-output buffers are reused within this one function invocation. SystemPlan.backward
  calls it instead of materializing both full Jacobians and their broadcast products. The input
  cotangent scatter retains the original slot order and np.add.at, including duplicate indices.
- This is a derivative-contraction storage change, not a new symbolic derivative evaluator,
  residual-product refinement variant or new factor-reuse claim. The derivative formulas, component
  call count, physical inputs, all slots and four-output contributions, conjugation convention,
  forward values, solve/refinement routines and JAX wrappers are unchanged from admitted source.
  Zero derivative entries still multiply their cotangents; no zero-valued numerical entry is pruned.
  Both holomorphic and antilinear terms are retained for every slot. function_jacobian itself stays
  unchanged for its other callers and serves as the synthetic oracle.
- Source-derived storage: parent keeps two arrays of 4*B*R*S complex entries before contraction,
  plus product/reduction temporaries. Candidate keeps two arrays of 4*B*R and the B*R*S result,
  plus per-slot component arithmetic and reduction temporaries. No scratch survives the call.
  Target is the ~85 ms large reverse phase. Extra per-slot NumPy reduction dispatch could offset
  the memory savings, particularly for small groups; no execution speedup is claimed.
- `overnight-numerics-pullback-check.py` uses AST-extracted source and the existing NumPy-only
  component loader. NumPy 2.5.5 matches the evaluator version, although local OS/CPU differ.
  3,078 comparisons cover all 19 functions, scalar/vector/batched inputs, real and complex inputs,
  each of seven parameters set to zero in turn, six slot menus including empty/single/all/reordered,
  and reversed-stride complex output cotangents. The unchanged full-Jacobian contraction is the
  oracle. All finite result entries match bit-for-bit; nonfinite entries compare equal. The exact
  four-output reduction matches in these tests, not a universal cross-platform arithmetic proof.
- Four SystemPlan integration cases (one/five batch rows, unique/duplicate writes and output
  selections) compare full assembled values, parameter cotangents and base cotangents against
  admitted-parent SystemPlan. Parameter indices repeat across components and slots. Both ordinary
  and NaN/infinite cotangents were exercised. All finite entries match bit-for-bit; nonfinite entries
  compare equal. This tests scatter/overwrite semantics in addition to the local contraction.
- Small synthetic allocation inspection (7 batches * 31 surface rows, all seven input slots,
  fully materialized input cotangent): tracemalloc peak parent 415352 B, candidate 155152 B.
  This includes component arithmetic in both paths. It is local allocation evidence only, not
  official process RSS, a timing benchmark, or a promise of the same ratio on optical setups.
  No official workload, dependency installation or timing run was launched locally.
- Submit the complete implementation for both unchanged official benchmarks on the same new SHA,
  all saved physical arrays/gradients and 14 generalization cases versus admitted parent and seed,
  plus independent source review. Preserve pristine strict failures separately. If promising,
  request at least five paired/interleaved fresh dual runs versus admitted parent with phase,
  RSS and overlap records. The diagnostic profile context is still available to attribute
  function_pullback versus previous function_jacobian costs separately from official timings.
- All inherited strict numerical issues remain open: signal and gradients 33/161/180, random1/3
  dense-reference sensitivity disagreements, six grid finite-difference coordinates, and first-order
  whole-pass custom-VJP compatibility limits. No changes to tolerances, fixtures, frequencies,
  variable counts, arithmetic precision, compiler options or the three JIT stages.


## Candidate 12 feedback and candidate 13: contiguous derivative output planes

- Candidate 12 exact SHA `75825cda098864218c0431d2e12d5dbfdfeb4bb0`, dual request
  `ec814a60fa034b4dbab804b00d2f2cdc` (grid-1/2/3 and aligo-1/2/3), completed with
  all six official passes. Large fresh complete samples: 0.8300696089863777,
  0.8003530371934175, 0.794034855440259 s; median 0.8003530371934175, range
  0.794034855440259–0.8300696089863777. Official aLIGO samples: 0.5444993507117033,
  0.5506514385342598, 0.5417988393455744 s; median 0.5444993507117033, range
  0.5417988393455744–0.5506514385342598. These are separate workloads, not a score.
- Large forward phases 182.765/184.455/179.476 ms; reverse 81.903/82.717/83.264 ms.
  aLIGO forward 32.069/34.193/32.596 ms; reverse 14.310/14.154/14.276 ms.
  Relative to the restored-parent cb04c3c cohort, unpaired median reverse deltas are
  approximately -3.072 ms large and +0.056 ms aLIGO. Large forward median also fell
  1.677 ms despite unchanged forward code, demonstrating the limitation of attributing
  small unpaired phase differences. Complete large median improves only 1.225 ms versus
  admitted candidate 7's recorded median, below the selection threshold, with overlapping
  ranges. This is NOT a confirmed improvement. Source review is still absent.
- Maximum sampled process-group RSS: large 585527296 B, aLIGO 302116864 B,
  generalization 924569600 B. No reported infrastructure failure or budget exceedance.
  CPU 2, one logical CPU, all library threads one, no persistent compilation cache;
  external contention was not excluded. Sampling can miss short peaks.
- Both official output archive hashes are unchanged from prior candidate receipts:
  large 112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5,
  aLIGO 9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195.
  All reported physical-array/gradient comparisons against initial seed pass, including
  all 14 generalization cases. Generalization archive hashing also includes timing metadata;
  a differing archive hash does not alone identify a physical-array difference. The receipt's
  candidate-self artifact comparison is not independent seed evidence. Raw remote arrays
  were not independently reopened locally; the per-array receipt and official hashes are
  the available evidence. All inherited pristine discrepancies remain: grid 131 signal,
  three gradient and one loss mismatches; official aLIGO one loss mismatch; random1/3
  sensitivity log errors about 2.0361e-4 and 5.8101e-5. Other recorded pristine failures,
  six unresolved grid finite-difference coordinates and whole-pass JVP/Hessian limitations
  remain open. No new physical discrepancy is reported by this receipt.
- Decision: preserve candidate 12 in history without promotion. Candidate 13 is one narrow
  refinement of the same new contraction mechanism, not a return to the closed residual
  allocation or surface common-subexpression trials. Scientific baseline remains admitted
  candidate 7 ee4fea2. Candidate 13 retains only candidate 12's contraction implementation
  on that baseline, with no new cross-lane transfer or combined numerical shortcut.
- Candidate 13 changes host.function_pullback derivative buffers from (batch, rows, 4)
  to (4, batch, rows), with the analogous arrangement for arbitrary leading dimensions.
  A single output derivative plane is now contiguous: the 217-row synthetic group has
  a 16-byte row stride instead of 64 bytes. The cotangent uses a moveaxis view, all four
  derivatives are multiplied, and sum(axis=0) contracts the same four outputs. Buffers
  remain local to the call; no numerical values or outputs persist across evaluations.
  All slots, zeros, nonfinite products and both Wirtinger terms remain present. No solver,
  factorization, iterative refinement, physics formula, scatter or JAX wrapper changes.
- Hypothesis: contiguous derivative writes and reductions reduce memory access costs in
  the large reverse phase. Cotangent strides may offset this benefit. Neither execution
  gain nor a first-run gain is established. This is a storage-layout experiment, not a
  further allocation reduction: synthetic tracemalloc peak 155344 B versus candidate 12's
  155152 B and the materialized-Jacobian baseline's 415352 B.
- Local check: overnight-numerics-pullback-check.py, NumPy 2.5.5, 3078 component
  comparisons across all 19 functions plus four SystemPlan integration cases pass;
  finite entries bitwise equal, nonfinite entries array-equal to the unchanged full-Jacobian
  oracle/admitted-parent scatter. Includes complex and zero parameters, reordered/empty
  slots, noncontiguous cotangents, duplicate writes and parameter indices, NaN/infinite
  cotangents. No official workloads or local timing benchmarks were launched.
- Candidate 13 SHA and job identifiers pending supervisor. Request both unchanged full
  official benchmarks on the same exact SHA, all output/gradient comparisons and 14-case
  generalization against admitted parent and seed, with pristine discrepancies retained,
  followed by independent source review. If promising, require paired/interleaved fresh
  complete runs against candidate 7 (and candidate 12 to isolate the layout delta), with
  every sample, phases, RSS and overlap conditions recorded. If this contraction direction
  remains unhelpful, return to admitted parent and obtain the already requested callback
  profile before expanding the mechanism. No performance promotion on synthetic evidence.
