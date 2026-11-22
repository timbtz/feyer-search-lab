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


## Candidate 13 feedback: freeze source for paired confirmation

- Exact simulator SHA `2117c2e8293722508055852ad7f614ed8959bb12`, request
  `dc07a2130411485ca7088fdcb2f5981c`; grid-1/2/3 and aligo-1/2/3 all official PASS.
  Large complete fresh samples [0.8103161100298166, 0.785075806081295,
  0.7955721952021122] s; median 0.7955721952021122, range
  0.785075806081295–0.8103161100298166. Official aLIGO samples
  [0.5411639176309109, 0.5458533503115177, 0.5450098384171724] s;
  median 0.5450098384171724, range 0.5411639176309109–0.5458533503115177.
- Large forward 178.749/178.000/178.626 ms, reverse 70.280/72.020/70.066 ms.
  aLIGO forward 32.703/32.923/32.698 ms, reverse 13.755/13.826/13.655 ms.
  Unpaired large reverse median is 12.437 ms lower than candidate 12 and 15.078 ms
  lower than admitted candidate 7; aLIGO reverse median is 0.520 ms below candidate 12
  and 0.629 ms below candidate 7. Complete large median is only 6.005 ms below
  candidate 7: import median rose 6.981 ms while unchanged forward median fell
  2.537 ms. These are descriptive phase deltas, not causal paired evidence.
- Maximum sampled group RSS large 540340224 B, aLIGO 291217408 B,
  generalization 817172480 B. No infrastructure error or memory exceedance reported;
  CPU 2/logical CPU one/library threads one, no persistent compilation cache.
  External contention not excluded; sampled peaks do not certify actual peak memory.
- Official archive hashes still equal those listed for candidate 12. Inspected all
  per-array checks: seed comparisons pass carrier, signal, noise, powers, sensitivity,
  loss and gradient in both official workloads and all 14 generalization cases.
  Pristine failures remain unchanged, including grid signal/gradient/loss, aLIGO loss,
  and random1/3 log sensitivity disagreements 2.036099e-4 and 5.810092e-5.
  Existing six unresolved grid finite-difference coordinates are not resolved by this
  result. Generalization NPZ hash includes timing metadata; no new claim of bytewise
  equality to initial seed, or independent local inspection of remote raw arrays.
- Outcome: confirmed_improvement=false; promotion reasons are requires_source_review
  and overlapping large first-run ranges. ranking_eligible=false. The admitted parent
  remains candidate 7. Candidate 13 is promising phase evidence, not a shared winner.
- No candidate 14 or simulator edit in this turn. All ten local simulator file SHA-256s
  verified equal to this exact candidate 13 receipt. Stop refining this mechanism until
  paired evidence is obtained; preserve candidates 11–13 and other trials in history.
  Candidate 13 stays frozen for confirmation rather than accumulating new changes.
- Added own-note diagnostic `overnight-numerics-pullback-fd.py`: real scalar linear
  objectives of all 19 component outputs, three nonsingular random real/complex points
  per function, all seven input slots in real and imaginary directions, both central
  difference steps 1e-5 and 5e-6 required to pass. Cotangents normalize by primal output
  scale. 1596 direction/step checks pass fixed scaled-error bound 2e-7; maximum error
  3.7198357667473056e-9 (susceptibility). Oracle uses primal component evaluations,
  no Dual derivative or Jacobian. This supplements shared-code equivalence checks;
  it is not full-system/ill-conditioned validation or universal physics certification.
- Coordinator action requested: independent source review of the full candidate 13
  delta versus ee4fea2, and at least five paired/interleaved fresh complete dual runs
  of exact 2117c2e versus exact ee4fea2 on the same CPU/environment/resource policy.
  Retain every sample and recorded overlap status, phases and sampled RSS; compare
  large and official aLIGO separately. A notes-only supervisor commit must not be
  described as a new optimization. Additional unchanged candidate runs are useful
  confirmation, but without interleaved parent runs do not resolve the paired request.
  If paired results reject the gain, restore admitted source and move to a genuinely
  different mechanism after callback profiling; do not keep tuning contraction layout.
  Absolute deadline remains 2026-11-22 09:27:44 UTC; campaign continues via supervisor.


## Candidate 14: direct component-group assembly, on admitted parent

- Supervisor explicitly requested a new evaluable simulator change after the frozen-source
  confirmation handoff. No new evaluation, paired cohort or independent review was provided;
  candidate 13 receipt dc07a213 and its pending confirmation request remain as recorded above.
  Candidate 13 is preserved at 2117c2e8293722508055852ad7f614ed8959bb12, without promotion.
- Change direction: return production host.py and host_pass.py to admitted candidate 7
  ee4fea28c04d482566be16e916b609d7c6a99e5e, then apply only this forward assembly variant.
  This is a working-file restoration, not a history reset. The streamed Jacobian contraction
  and its output-plane layout (12/13) are not included. Candidate 11's component formula
  variant and 9/10's residual allocation variants are also absent. Pending confirmation of
  those preserved revisions can proceed independently through the supervisor.
- Concrete redundant operation: SystemPlan.values previously retained all group outputs in
  a list, copied them into a concatenated (B, total_rows, 4) array, gathered all selected
  outputs, then gathered last-write survivors again to assign the final structural values.
  Only surviving write destinations determine the final matrix vector. The existing plan
  already calculates which writes survive; no inference from current numerical values is used.
- Implementation: partition surviving write destinations and their selected output offsets by
  component group once during SystemPlan construction. NumPy-style negative output indices
  are normalized before partitioning. During each assembly, repeat the base vector as before,
  evaluate each full group, and gather its surviving entries directly into final destinations.
  No list of all blocks, concatenated output array or gather of overwritten writes remains.
  All groups are still evaluated even if every destination from that group is overwritten.
  Duplicate output reads and last-write semantics are retained; destinations of surviving
  writes are distinct for the builder's structural indices. Every evaluation uses fresh
  numerical inputs and freshly evaluated outputs. The plan stores indices only.
- Only host_pass.py differs from admitted source. Backward formulas/scatters, component
  functions, precision, factorization and iterative refinement are exactly admitted source.
  The plan key already includes all groups, selectors and destinations from which group_writes
  is deterministically derived; no additional numerical cache or cache-key assumption added.
- Hypothesis: reduce temporary memory traffic during the measured ~178–183 ms large forward
  phase. The fraction spent in assembly is still unprofiled; this is not a claim assembly
  dominates that phase. Extra static partitioning costs build time and per-group destinations
  cost memory. Both must be included in the complete first-run evaluator result. No tuning menu
  or dynamic threshold is introduced, and no workload identity or known shape is recognized.
- Small local AST/NumPy 2.5.5 inspection: overnight-numerics-assembly-check.py passed 37
  forward/backward comparisons against admitted-parent SystemPlan. Covers all 19 component
  functions, variable group sizes, one/three/seven batch rows, repeated input indices,
  duplicate destinations and output selections, negative output indices, real/complex and
  all-zero input rows. Finite results match bit-for-bit; nonfinite results compare equal.
  A separate counted case confirms a wholly overwritten group still executes, alongside
  a repeated output read and cross-group destination overwrites. Backward is unchanged but
  tested to check that new plan metadata does not interfere with it.
- Synthetic allocation inspection with 19 groups * 17 rows * 7 batch rows and 800 writes:
  fully materialized matrix values in both paths, tracemalloc peak parent 395112 B,
  candidate 154304 B. This is allocation evidence, not timing or official process RSS.
  No optical benchmark was run locally. The earlier pullback/FD scripts and results refer
  to preserved candidate 13; they are historical diagnostics, not checks of this restored host.
- Candidate 14 SHA and both benchmark/job identifiers pending supervisor. Request both full
  unchanged official workloads on the exact same new SHA, all saved outputs/gradients and
  the generalization suite versus admitted source/initial seed, independent source review,
  and paired fresh-process confirmations if promising. Compare against admitted candidate 7,
  not candidate 13, to isolate this hypothesis. Record build/forward/reverse phase tradeoffs,
  all samples and ranges, memory and overlapping jobs. Keep the previously requested paired
  review of frozen candidate 13 separate; do not automatically combine these variants.
- All existing pristine signal/gradient/loss discrepancies, random1/3 sensitivity errors,
  six unresolved grid finite-difference coordinates, and whole-pass JVP/Hessian limitations
  remain open. No tolerance, fixture, workload, compiler policy or JIT-stage changes.


## Candidate 14 feedback and decision (2026-11-22 03:09 UTC)

- Exact simulator SHA a6979b7e880c1c893251370a80b24335c191a96f; dual job
  8a8fbba697e34c869554f612ae4a8598, grid-1/2/3 and aligo-1/2/3. All six official
  runs passed. No confirmed improvement; independent source review is still absent.
- Large complete first runs: [0.8384488299489021, 0.8022003620862961,
  0.8193489741533995] s; median 0.8193489741533995 s, range
  [0.8022003620862961, 0.8384488299489021] s. Forward samples
  [184.196614, 183.277691, 180.195555] ms; reverse
  [89.392554, 83.280908, 88.963116] ms. Build [74.130319, 73.818663, 75.672487] ms.
  Against admitted candidate 7's earlier cohort, median forward is +2.114604 ms,
  reverse +3.605692 ms, total +17.771291 ms. These are unpaired observations,
  not causal estimates. One gradient compilation took 64.029695 ms with unchanged
  gradient code, further illustrating variation in complete totals.
- Official aLIGO complete first runs: [0.5483746789395809, 0.5518810488283634,
  0.5476594641804695] s; median 0.5483746789395809 s, range
  [0.5476594641804695, 0.5518810488283634] s. Forward
  [32.826960, 33.283606, 32.526543] ms; reverse
  [14.597578, 14.665509, 14.827415] ms. Versus candidate 7 median forward
  -0.063190 ms, reverse +0.281357 ms and total -0.180477 ms; no established gain.
- Sampled peak RSS maxima: large 682930176 B, aLIGO 289861632 B,
  generalization 907698176 B. No infrastructure failure or exceeded memory budget.
  CPU2, threads1, no persistent cache; other-host contention not excluded. No
  quiet ranking claim or combined score. Selection rejected below-threshold large
  gain, overlapping ranges and missing independent source review.
- All per-array receipt comparisons (carrier, signal, noise, powers, sensitivity,
  loss, gradient) pass versus initial seed for both official workloads and all 14
  extra cases. Official archives remain grid 112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5
  and aLIGO 9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195.
  This statement uses supplied receipt evidence, not a new local raw-array audit.
  Pristine grid has 131 signal, 3 gradient and 1 loss mismatch; aLIGO has 1 loss
  mismatch. Extra random1/3 log sensitivity errors remain 2.036099068405406e-4 and
  5.8100919558157216e-5. The six unresolved grid FD coordinates and first-order-only
  custom VJP limitation remain. Official passes do not resolve these findings.
- Decision: stop direct group-write assembly. Its synthetic allocation reduction did
  not translate into a measured forward improvement. Preserve the failed revision
  in history; restore admitted candidate 7 assembly in working source. Candidate 13
  remains separately preserved at 2117c2e, with paired confirmation/review still
  outstanding; do not combine its derivative storage with this next trial.

## Candidate 15: reuse correctly typed CSC index arrays

- Parent provenance: admitted ee4fea28c04d482566be16e916b609d7c6a99e5e (candidate 7).
  Restore only host_pass.py's candidate 14 assembly changes, then change only the
  two integer conversions in _factor to astype(np.intc, copy=False). All other
  simulator files equal admitted source. No branch reset, commit or external call.
- Genuine redundant operation: SparsePattern constructs its CSC indices and indptr
  once as int32. _factor's unconditional astype(np.intc) made two fresh copies at
  every numerical factorization, even when their dtype already matched C int.
  copy=False returns the original arrays on matching platforms and retains the
  original conversion on other dtypes. This changes allocation/traffic inside
  forward execution; it does not reduce numerical assembly, factorization or
  refinement work. Expected benefit is small and entirely unmeasured in official
  first-run timing. Do not claim this dominates the forward phase.
- No mathematical or structural pruning, permutation option change, new cache,
  refinement reduction, physical parameter change, workload detection or policy
  setting. Numerical values and factors remain fresh for every forward. Generic
  backward fallback uses the same factor routine. Public SciPy fallback is unchanged.
- Small local check overnight-numerics-factor-check.py extracts _factor and
  SparsePattern via AST, runs actual SciPy 1.18.1 / NumPy 2.5.5 SuperLU and compares
  admitted and candidate factors. 72 factor pairs, 648 solves passed bit-for-bit,
  including factor L/U data and structure, row/column permutations, N/T/H, vector
  and 1/3-column RHS, sizes 7/19/43, structural zeros becoming nonzero on subsequent
  calls, changed random complex values, and row scaling from 1e-7 to 1e7. Both direct
  extension and public fallback paths exercised, writable/read-only index arrays
  and int32/int64 inputs. Data and structural bytes remained unchanged.
- The copy-count check observed 18 direct calls sharing both C-int arrays and 18
  direct calls converting int64 arrays. The shared calls eliminated 36 array copies,
  totaling 12168 B for these small synthetic patterns. This is not a timing, process
  RSS measurement, optical generalization test or universal non-mutation proof.
  Local SciPy's public splu itself uses safely_cast_index_arrays, whose CSC branch
  also uses astype(..., copy=False); that source inspection supports the same
  read-only input convention. An initial inspection for an older helper name
  (_safe_downcast_indices) raised AttributeError; inspecting the actual splu source
  located the current helper. Production/check execution did not fail.
- New SHA and both official job identifiers pending supervisor. Request unchanged
  full large and official aLIGO workloads on one exact new SHA, all saved arrays and
  gradients, the existing generalization comparisons against initial seed/admitted
  source and pristine, and independent source review before any promotion. If the
  small allocation change appears promising, obtain paired fresh candidate/parent
  dual runs with samples, phase tradeoffs, RSS and overlap information. A synthetic
  copy reduction alone is not sufficient evidence of improvement. If timing stays
  indistinguishable, reject this variant and keep candidate 7 admitted; pending
  candidate 13 confirmation remains a separate useful next action.


## Candidate 15 feedback: no demonstrated benefit

- SHA bedb89e6b0360042f60e7519fa0a24983c715ea8, request
  981c3b3fbcd241c2b32a03c563639a64 (grid-1/2/3 and aligo-1/2/3).
  Six official passes. No confirmed improvement or independent source review.
- Large complete first runs [0.8455780781805515, 0.7983885705471039,
  0.8056562822312117] s; median 0.8056562822312117, range
  [0.7983885705471039, 0.8455780781805515]. Forward
  [190.654168, 178.886898, 187.850546] ms, reverse
  [88.974800, 84.959472, 84.344190] ms; build
  [71.519103, 73.717209, 68.958111] ms. Unpaired median deltas versus admitted
  candidate 7: total +4.078599 ms, forward +6.687459 ms, reverse -0.397952 ms.
- Official aLIGO first runs [0.5537967570126057, 0.5524643007665873,
  0.5420569684356451] s; median 0.5524643007665873, range
  [0.5420569684356451, 0.5537967570126057]. Forward
  [32.594452, 32.848397, 32.486092] ms, reverse
  [14.728509, 14.703605, 14.281003] ms; build
  [39.204380, 38.183991, 37.798736] ms. Unpaired median deltas versus admitted
  candidate 7: total +3.909145 ms, forward -0.295698 ms, reverse +0.319453 ms.
- Sampled peak RSS maxima: large 653504512 B, aLIGO 295723008 B,
  generalization 872075264 B. No infrastructure failure or memory-budget exceedance;
  CPU2, one thread, no persistent cache; external contention not excluded.
  Ranges overlap, large gain below selection threshold, source review absent.
- Read the local stored evaluation receipt and all supplied per-array comparisons:
  both official setups and all 14 extra cases pass against initial seed; official
  archive hashes remain 112c0407... (grid) and 9c1ce936... (aLIGO) as recorded above.
  No local reopening of remote raw arrays. Pristine mismatches remain (grid signal,
  gradient, loss; official aLIGO loss; additional random and perturbed cases).
  In particular random1/random3 sensitivity log errors and six unresolved grid FD
  coordinates are not resolved by these passes. First-order-only VJP unchanged.
- Decision: retire CSC index-copy variant. The actual allocation saving is too small
  to establish a complete-run benefit in this evidence. Restore admitted factor
  routine without rewriting history. Do not keep stacking unconfirmed small changes.

## Candidate 16: full Jacobian storage with contiguous derivative planes

- Parent: admitted candidate 7, ee4fea28c04d482566be16e916b609d7c6a99e5e.
  All simulator source equals that parent except function_jacobian's two buffer
  layouts in host.py. host_pass.py restored from parent; no candidate 14/15 changes.
  Candidate 13 remains a separate preserved experiment, not an admitted parent.
- Source observation: for each seeded slot, function_jacobian assigns each output's
  derivative over all batch/component rows into (...,4,slots) C-order arrays. Those
  planes are strided by 4*slots complex entries. The contraction also traverses these
  full arrays. Candidate 13's earlier reverse-phase reduction suggests contiguous
  derivative storage is worth isolating, but its complete-run gain was unconfirmed.
- Narrower implementation: allocate (slots,4)+input_batch_shape arrays, then expose
  (...,4,slots) views with moveaxis. Full Jacobian API, shapes, values, precision,
  zero initialization and full allocation size are unchanged. Each derivative plane
  now fills contiguous storage. Original component seeding, all Dual operations,
  four-output contraction expressions, slot iteration and np.add.at scatters remain.
  No streamed function_pullback API or hand-written derivative is introduced.
- This is a simpler isolated layout trial, not a combination with candidate 13.
  No claim of fewer mathematical operations. Stride layout can alter NumPy reduction
  kernels, so equivalence and full numerical evaluation are required even though
  source-level contraction order is unchanged. The extra moveaxis views have overhead
  counted in reverse execution. No persistent or cross-evaluation numerical cache.
- Small synthetic overnight-numerics-jacobian-layout-check.py: 3078 comparisons of
  all 19 functions and contractions passed; scalar, vector and batched inputs,
  real/complex parameters, each zero-valued parameter slot, empty/reordered/full
  differentiation slots and noncontiguous cotangents. Eight SystemPlan.backward
  comparisons passed across 1/5 batch rows, repeated parameter indices, repeated
  output selections/destinations, and nonfinite cotangents. Finite entries bitwise
  equal; nonfinite entries array-equal. These are component checks, not a new optical
  certificate or resolution of the existing ill-conditioned-system disagreements.
- Structural measurement on a small (7,31,7) synthetic input: each Jacobian retains
  97216 bytes. Old exposed strides (13888,448,112,16); new (496,16,3472,13888).
  Fixed-output/fixed-slot planes are now C-contiguous. No timing run was performed
  locally, and no expected millisecond gain is asserted.
- Candidate SHA/job IDs pending. Request both unchanged official full workloads on
  the same exact SHA, complete saved outputs/gradients and 14-case generalization
  comparisons, followed by independent source review and paired fresh-process
  confirmation against admitted candidate 7 if promising. Report large and aLIGO
  separately, including reverse/build/compile tradeoffs and RSS. Keep preserved
  candidate 13's pending paired confirmation separate. If this narrower layout does
  not show a stable gain, close derivative-storage tuning until profiling or paired
  evidence supplies a stronger reason to revisit it. Retain admitted candidate 7.


## Candidate 16 feedback and derivative-storage handoff (2026-11-22 03:18 UTC)

- SHA 3033fcc29482f5d0bca96c6e53c87c48f17f5cfd; request
  1199c6ddb84c4b249c86748688755312, grid-1/2/3 and aligo-1/2/3. Six official
  passes; confirmed_improvement=false. No independent source review supplied.
- Large complete first runs [0.8291760943830013, 0.8071782477200031,
  0.8021924458444118] s; median 0.8071782477200031, range
  [0.8021924458444118, 0.8291760943830013]. Forward
  [180.059340, 183.386384, 182.026068] ms; reverse
  [89.901935, 87.664612, 88.213574] ms; build
  [73.609309, 73.837614, 69.967989] ms. Unpaired median deltas from admitted
  candidate 7: total +5.600564 ms, forward +0.862981 ms, reverse +2.856150 ms.
- Official aLIGO complete first runs [0.5447305403649807, 0.5469193495810032,
  0.546897329390049] s; median 0.546897329390049, range
  [0.5447305403649807, 0.5469193495810032]. Forward
  [32.754388, 32.664398, 34.995005] ms; reverse
  [14.879223, 15.341669, 14.720855] ms; build
  [38.889872, 38.384017, 37.408777] ms. Unpaired median deltas from admitted
  candidate 7: total -1.657827 ms, forward -0.135762 ms, reverse +0.495071 ms.
  No causal speedup claim from these separate cohorts, and no combined score.
- Sampled process-group peak RSS maxima: large 728645632 B, aLIGO 302936064 B,
  extra generalization 839630848 B. No infrastructure failure or memory-budget
  exceedance. CPU2, library threads1, no persistent cache. Other-host contention
  not excluded. Selection reasons: missing source review, large gain below threshold,
  overlapping first-run ranges. This is support evidence, not a ranking cohort.
- Inspected stored receipt's complete array-comparison summaries: carrier, signal,
  noise, powers, sensitivity, loss and gradients pass versus initial seed for all
  six official runs and 14 extra cases. Official archives unchanged from candidate 7
  (grid 112c0407..., aLIGO 9c1ce936..., full hashes above). This is receipt inspection,
  not a fresh local inspection of remote raw arrays. Pristine comparisons still fail:
  grid 131 signal entries, gradients 33/161/180 and loss; official aLIGO loss; extra
  random1/3 log sensitivity errors 2.036099068405406e-4 / 5.8100919558157216e-5
  and other previously recorded mismatches. Six grid FD coordinates remain open.
  No tolerance change, numerical certification or JVP/Hessian support claim.
- Decision: reject candidate 16. Contiguous full Jacobian planes alone did not improve
  the measured reverse phase. Close derivative-storage tuning now: candidates 12,
  13 and 16 all lack a repeat-supported complete-run gain. Candidate 13 remains
  promising only at the phase level, not promoted. Direct group assembly (14) and
  CSC-index copying (15) also failed to establish gains; do not stack them.
- Restored host.py to admitted candidate 7. Read-only git diff confirms ALL simulator
  files now exactly match ee4fea28c04d482566be16e916b609d7c6a99e5e. The restoration
  is a working-file change, with failed commits preserved. No new performance
  candidate is being submitted; no redundant dual evaluation of this restoration
  is requested. Supervisor may record the restoration normally without history reset.

Concrete next action for the coordinator, before another numerical variant:

1. Obtain five paired fresh complete dual runs of preserved candidate 13
   2117c2e8293722508055852ad7f614ed8959bb12 versus admitted candidate 7
   ee4fea28c04d482566be16e916b609d7c6a99e5e, using the same fixed evaluator policy.
   Candidate 13's receipt dc07a2130411485ca7088fdcb2f5981c showed large reverse
   median 70.279835 ms, but complete range [0.7850758061, 0.8103161100] s overlapped
   the parent's [0.7944249958, 0.8224838302] s. Its aLIGO median was 0.5450098384 s.
   Keep numerical comparisons and independent exact-SHA source review mandatory.
   If paired complete timing does not support it, retire it without more layout tuning.
2. Independently collect the first forward and first backward callback profiles of
   admitted candidate 7 under the fixed CPU/thread policy. The existing opt-in context
   experiments/notes/overnight-numerics-profile.py is ready for a coordinator-owned
   diagnostic driver; it launches no workload. Inspect self and cumulative costs of
   _factor, _solve, _Products.apply, SystemPlan.values/backward, function_jacobian,
   and scatter operations. Keep instrumented timings separate from official totals.
   Do not sum nested cumulative times. No such profile has yet been supplied here.
3. Choose a genuinely different mechanism only from that breakdown. Structural
   reuse of component rows across sweep axes is an unexplored possibility, but needs
   an explicit dependency proof including changing zero-valued parameters and reverse
   contributions; no implementation or performance claim for it is made in this handoff.

This stop closes the present derivative-storage hypothesis, not the authorized
campaign. Deadline remains 2026-11-22 09:27:44 UTC. Source is the strongest admitted
parent; all failed trials, diagnostics and numerical caveats remain available.

## Candidate 17 — exact-index component-row reuse (2026-11-22)

Supervisor requested a concrete new experiment after the candidate-16 stop
handoff. This changes the mechanism from derivative storage to structural reuse
within a component function group. Candidate SHA and job IDs are pending the
supervisor; nothing in this section is an official timing result.

Provenance: current committed HEAD is candidate 16,
3033fcc29482f5d0bca96c6e53c87c48f17f5cfd. Its unsuccessful timing outcome and
request 1199c6ddb84c4b249c86748688755312 are recorded above. The preserved
host.py restoration removes candidate 16's Jacobian-layout experiment. Relative
to admitted candidate 7, ee4fea28c04d482566be16e916b609d7c6a99e5e, the sole
simulator delta for candidate 17 is SystemPlan in host_pass.py. No candidate-13
pullback, residual-allocation trial or other-lane change is added.

Evidence and mechanism:

- build.py's _group_component_indices groups by function ID without deduplicating
  input rows. Repeated vacuum-source instructions use the same padded parameter
  index row (build.py around line 866), establishing a real source of duplicate
  work. The multiplicity and cost in either official setup have not been measured.
- Each SystemPlan now computes unique full parameter-index rows within each
  function group. Repeated rows evaluate the same function on identical inputs
  for every batch and every parameter point. This equality does not depend on
  physical values, on a zero at the current point, or on fixture identity.
- Primal results and both Wirtinger Jacobians are expanded to the original row
  order before the existing writes, contractions and slot-ordered np.add.at.
  Every output and derivative contribution remains present; cotangents are not
  aggregated ahead of multiplication. The no-duplicate path keeps original
  indices and avoids the expansion. All numeric evaluation remains inside the
  forward/backward calls, with no additional numeric state cache.
- Hypothesis: fewer repeated component calculations can lower forward/reverse
  execution. Static uniqueness analysis adds build cost, and inverse gathers add
  execution allocations for duplicated groups. Small or cheap duplicate groups
  may lose overall. This is deliberately a provisional complete-cost experiment,
  not a claim that the synthetic work reduction yields an official speedup.

Local validation (no workloads or timing):

- overnight-numerics-row-reuse-check.py passed 120 forward/backward comparisons
  against admitted candidate 7: all 19 component functions, batch sizes 1/3/9,
  duplicate and unique index rows, empty/full/reordered derivative slots,
  repeated writes/reads, negative output selections, real/complex inputs,
  zeros, ones and subsequent changed values using the same plan. Finite results
  match bitwise including signed zero; nonfinite result locations also match.
- In its duplicate-heavy synthetic case, counted component rows fell 171 to 57
  and differentiated rows 684 to 228. These are work counts, not milliseconds.
- Existing assembly diagnostic passed another 37 comparisons, including groups
  whose writes are overwritten. Its no-duplicate synthetic allocation peak was
  395112 bytes for both implementations. git diff --check passed.
- Checks use AST-extracted actual host/component functions with local NumPy;
  local JAX is unavailable. They do not establish callback/JIT compatibility or
  full optical correctness. No independent review has occurred for this delta.

Decision: submit candidate 17 for both unchanged exact-SHA official benchmarks
and all saved-output/gradient/generalization comparisons. Record build, forward,
reverse and complete totals separately for grid and aLIGO; retain memory and
contention notes. Request independent source review and paired fresh-process
confirmation against candidate 7 if promising. A source-derived duplicate-row
count in coordinator diagnostics would help interpret a null result. If the
planning/gather cost outweighs reuse, retire this mechanism rather than claiming
an operation-count win. Candidate 13's separate paired-evidence request remains
pending and is not evidence for candidate 17.

Inherited strict disagreements remain unresolved: grid signal entries and
33/161/180 gradients; uifo_rand1/rand3 log-sensitivity discrepancies about
2.04e-4/5.81e-5; grid finite-difference coordinates 54/59/63/136/161/163.
Prior aLIGO 29/29 extra coordinate checks and official passes do not erase them.
The host custom VJP still lacks forward-mode JVP/Hessian support. Deadline stays
2026-11-22 09:27:44 UTC.

## Candidate 17 feedback: no execution gain established

SHA 3dee003b7b8c913f57c5856e84cb181677d55378; dual request
0d14134c56fa4302ae0e2adbce4dca11 (grid-1/2/3 and aligo-1/2/3).

- Grid fresh complete seconds: 0.8217093646526337, 0.8099264372140169,
  0.8075800202786922; median 0.8099264372140169; range
  [0.8075800202786922, 0.8217093646526337].
- aLIGO fresh complete seconds: 0.5588315296918154, 0.5449592173099518,
  0.5497273728251457; median 0.5497273728251457; range
  [0.5449592173099518, 0.5588315296918154].
- Grid build ms 70.328653/76.730838/74.885411, forward
  182.568124/182.243131/181.025848, reverse 84.167758/87.277632/85.448883.
  Unpaired median deltas from admitted candidate 7: complete +8.348754 ms,
  build +0.891331 ms, forward +1.080044 ms, reverse +0.091459 ms.
- aLIGO build ms 41.913426/38.833935/38.502777, forward
  32.094724/32.546908/32.641437, reverse 14.585467/14.755264/14.688604.
  Unpaired median deltas: complete +1.172217 ms, build +0.871390 ms,
  forward -0.343242 ms, reverse +0.304452 ms. No stable improvement claimed.
- Maximum sampled RSS bytes: grid 604778496, aLIGO 289603584,
  generalization 872001536. No infrastructure failures. Fixed CPU2/thread-one
  policy; other-host contention not excluded. No paired parent cohort supplied.
- All six official runs passed. Inspected receipt comparison records for every
  output/gradient and all 14 generalization cases: all seed comparisons pass.
  Both official arrays archive hashes match previous candidates (grid 112c0407...,
  aLIGO 9c1ce936...). All six strict-comparison records and both seed/pristine
  14-case comparison lists equal candidate 16's records exactly. Raw remote
  archives were not reopened locally. The generalization archive hash includes
  timing metadata and is not treated as proof of numerical identity.
- Pristine strict failures remain unchanged, including rand1/rand3 sensitivity
  discrepancies. Independent source review is absent; confirmed_improvement=false;
  admission declined for missing review, insufficient large gain and range overlap.

Decision: retire exact-index row deduplication and restore host_pass.py to admitted
candidate 7. Do not combine it with the next experiment. Failed source remains in
its committed history. The prior candidate-13 paired-confirmation and callback
profiling requests remain outstanding.

## Candidate 18 — share primal arithmetic across derivative directions

Candidate SHA and both benchmark/job identifiers pending supervisor. Relative to
admitted ee4fea28c04d482566be16e916b609d7c6a99e5e, only host.py changes. The
candidate-17 host_pass.py restoration is part of the submission. No other-lane
transfer or combination with candidate 13 is included.

Hypothesis and proof of redundant work: function_jacobian currently calls the same
component function once for every requested differentiated input slot. Each call
recomputes its primal intermediates. Candidate 18 calls the component once with
independent Wirtinger directions sharing those intermediates. A new internal
_Directions object holds a primal and a dictionary of (a,b) per active seed.
Operators implement the existing Dual formulas independently for each seed.
Membership is structural: a derivative currently equal to zero stays present.
When a direction exists in only one operand, use the corresponding original
scalar-operand/reflected rule; do not replace absent derivatives with zero arrays.
That distinction preserves singular/nonfinite propagation. Conjugation still
swaps and conjugates a/b. Slot aliases and duplicate requests preserve all columns.
The full J/K interface, output layout, contractions and parameter scatter remain.
No values or derivative results are cached between calls. All forward assembly,
factors, refinement settings, physical formulas and JAX boundaries remain those
of admitted candidate 7.

This is a computation-sharing experiment, not another derivative-storage variant.
It adds interpreter bookkeeping and may lose for cheap functions or small groups;
only complete exact-SHA official results can decide. There are no tuning knobs.

Local evidence from overnight-numerics-directions-check.py:

- 4104 component/Jacobian/contraction comparisons against separately extracted
  admitted host source, all 19 functions, scalar/2-D/3-D batches, complex inputs,
  each slot at zero, empty/partial/full/reordered/duplicate/negative/numpy-array
  slot specifications. Finite values match bitwise including signed zeros;
  nonfinite values compare array-equal.
- Eight SystemPlan backward integration checks, including duplicate writes and
  nonfinite cotangents, match the admitted Jacobian implementation.
- 133 extra all-zero/one/negative/extreme (1e-12,1e12)/infinite/NaN input checks.
- 1596 independent component central-difference checks (real and imaginary
  coordinates, three points/function, both step sizes required) pass the unchanged
  2e-7 normalized bound. Worst normalized error 1.7286649972079704e-9. This does
  not resolve any full-system finite-difference question.
- Seven-direction synthetic surface evaluation: transcendental shim calls
  98 -> 14, argument elements 3234 -> 462. No official workload or timing run.
  This count omits derivative-slope internals and is not a speedup estimate.
- Local NumPy AST checks do not exercise JAX callbacks/JIT; no dependencies were
  installed. git diff --check passes. The shared diagnostic loader now recognizes
  _Directions so its source extraction remains usable with the candidate.

Request both unchanged full official benchmarks and all saved-output/gradient and
14-case comparisons on the new exact SHA, independent source review, and at least
five paired fresh-process complete candidate/parent runs if phase and total results
are promising. Inspect reverse execution and all first-run costs separately for
grid and aLIGO, memory and contention. Investigate any newly introduced numerical
mismatch before further tuning. No gain or universal compatibility claimed.

All inherited strict/pristine discrepancies and unresolved grid FD coordinates
54/59/63/136/161/163 remain open; prior aLIGO extra checks were 29/29. Whole-pass
custom VJP JVP/Hessian limits remain. Deadline is 2026-11-22 09:27:44 UTC.

## Candidate 18 feedback — preserve exact source for paired confirmation

Evaluated simulator SHA: 457d0eaa2b4ab4fe1005ad0cd0cbd47999864575.
Dual request: da9fbd3f38fd48bdb8315da1d541bbc6; jobs grid-1/2/3 and
aligo-1/2/3. Current branch HEAD e913358b666ad9298c8436dcd53feb9e9643b0f2
only adds the supervisor feedback record; its simulator files match evaluated
457d0ea exactly. No simulator edit is made in this feedback turn.

Complete first-run seconds, retaining every sample:

- Grid: [0.8228696137666702, 0.7973811868578196, 0.7856276277452707];
  median 0.7973811868578196; range [0.7856276277452707, 0.8228696137666702].
- Official aLIGO: [0.5446561574935913, 0.5517825614660978, 0.5451968312263489];
  median 0.5451968312263489; range [0.5446561574935913, 0.5517825614660978].
- Admitted candidate-7 historical samples remain grid
  [0.8224838301539421, 0.8015776835381985, 0.7944249957799911], median
  0.8015776835381985; aLIGO [0.5516242142766714, 0.5485551562160254,
  0.544719347730279], median 0.5485551562160254. These are unpaired cohorts.

Phase samples in ms:

- Grid forward [180.501174, 183.435922, 178.890375], reverse
  [81.142511, 75.831190, 75.750163], build [72.900463, 78.095555, 73.386939],
  imports [295.892328, 265.809149, 264.072431].
- aLIGO forward [32.469302, 34.067383, 32.828897], reverse
  [13.977902, 14.031840, 13.505267], build [37.679261, 37.626436, 37.908709],
  imports [262.657933, 272.126909, 266.147738].
- Relative to candidate 7's historical medians: grid complete -4.196497 ms,
  forward -0.661913 ms, reverse -9.526234 ms; aLIGO complete -3.358325 ms,
  forward -0.061253 ms, reverse -0.406250 ms. This is a promising reverse-phase
  observation, not a repeat-confirmed complete improvement. The slow first grid
  sample remains in the cohort; no import outlier is discarded.
- Max sampled process-group RSS bytes: grid 612876288, aLIGO 305053696,
  generalization 882380800. CPU2, one logical CPU and one library thread,
  no persistent cache. No infrastructure failures or memory-budget exceedances.
  Other-host contention is not excluded; no new overlap evidence was supplied.

Numerical receipt inspection:

- All six unchanged official benchmarks pass. All saved carrier, signal, noise,
  powers, sensitivity, loss and gradient seed comparisons pass on each run.
  The three grid archive hashes are all 112c040763a3659519d4fd21272c47f649d302ee2b5d3fc6ee1422006a8cb4a5;
  the three aLIGO hashes are all 9c1ce936bf401a6b48abf017df1e3980d8cfa7b04c800a1f9d7d47195da25195,
  matching prior candidates. Raw remote NPZ files were not reopened locally.
- Programmatically compared every strict-comparison record with candidate 17:
  all six records and all fourteen initial-seed/pristine generalization case
  records are exactly unchanged. Seed generalization passes 14/14; pristine
  strict comparisons still fail. The self-comparison in generalization.artifacts
  is not used as independent validation. Timing metadata affects archive hashes.
- Grid seed gradient max absolute difference remains 5.686350050382316e-6,
  relative L2 8.181451454702114e-11; aLIGO 3.637978807091713e-11 and
  1.294943745154708e-15. This is tolerance agreement, not byte identity to seed.
- Pristine grid has 131 signal/3 gradient/1 loss failures, aLIGO 1 loss failure;
  rand1/rand3 log sensitivity errors remain 2.036099068405406e-4 and
  5.8100919558157216e-5. Six grid FD coordinates 54/59/63/136/161/163 remain
  unresolved. Prior aLIGO extra coordinate checks were 29/29, not a universal
  certificate. Whole-pass custom VJP JVP/Hessian limits remain.

Decision: candidate 18 is provisional, not admitted. confirmed_improvement=false,
source_review=null, ranking_eligible=false. Admission reasons are missing review
and overlapping complete grid ranges. Freeze this exact source rather than mix
another change into a promising but unconfirmed mechanism. Candidate 7 remains
the strongest admitted parent; candidate 18 remains an isolated experiment.

Concrete coordinator request before further shared-primal tuning:

1. Independently review the delta ee4fea28c04d482566be16e916b609d7c6a99e5e ->
   457d0eaa2b4ab4fe1005ad0cd0cbd47999864575. Focus on structural direction
   membership, absent-versus-zero derivative behavior, scalar/reflected binary
   rules, conjugation, slot aliases and the unchanged full J/K/scatter boundary.
2. Run five fresh complete grid and five fresh complete official aLIGO processes
   for EACH of those exact simulator SHAs, interleaving parent/candidate in
   balanced order under the existing evaluator CPU/thread/environment/resource
   policy. Keep each setup's samples, median, range, paired differences, phases,
   memory and overlap evidence separate. Do not change fixtures or use profiled
   times as official results. Retain numerical checks on both revisions.
3. If this confirms a meaningful complete gain and source review accepts it,
   advance through normal admission. Otherwise retire shared-primal tuning or
   obtain the already requested callback profile before changing representation.
   Do not automatically combine with candidate 13, whose separate confirmation
   request remains pending.

No new candidate or redundant unpaired evaluation is requested. This handoff
ends the present hypothesis turn, not the user-authorized campaign. The absolute
deadline remains 2026-11-22 09:27:44 UTC. All failed trials remain in history.

## Candidate 19: scalar arithmetic without empty direction objects

The supervisor requested a concrete next experiment after the candidate 18 freeze
handoff. This bounded refinement continues 18's shared-primal mechanism; it does
not promote 18 or combine another pending candidate. Production parent is
457d0eaa2b4ab4fe1005ad0cd0cbd47999864575 (request
da9fbd3f38fd48bdb8315da1d541bbc6). Candidate SHA and official job identifiers are
pending supervisor commit/evaluation. Candidate 7 ee4fea28 remains the admitted
comparison parent. Candidate 18's review and paired confirmation remain pending.

Source inspection found that `_Directions` scalar binary operations constructed
an empty dictionary and a union of keys, despite only one operand carrying
derivatives. Reflected operations additionally constructed a temporary direction
object for the ordinary operand. Candidate 19 applies those existing scalar
rules directly, with the same arithmetic operand order. Add/subtract still copy
the direction dictionary, preserving independent maps. Reflected division
computes its common slope once, and retains the empty-direction guard. The
both-active-operand rules remain unchanged; no numerical zero removes a seed.

Hypothesis: fewer interpreter allocations and dictionary lookups may reduce
reverse execution. Candidate 18's measured grid reverse median was 75.831190 ms
and aLIGO reverse median 13.977902 ms, but its complete-run improvement remains
unconfirmed. Candidate 19 changes only host.py arithmetic, not forward assembly,
solves, refinement, parameter values, JAX stages or wrapper/import settings.

Local synthetic evidence, using existing NumPy environment and AST-extracted
kernels (no JAX, optical workload, benchmark or timing run):

- `overnight-numerics-scalar-directions-check.py` reruns the independent admitted
  host comparison: 4,104 component/contraction checks, eight SystemPlan backward
  integrations, 133 extreme/nonfinite cases, and 1,596 finite differences pass.
  Maximum scaled FD error 1.7286649972079704e-9 with the existing 2e-7 bound.
- 1,344 direct scalar/reflected operator cases match candidate 18, including
  empty maps, explicitly zero derivatives, signed zero, complex constants,
  infinity and NaN. Python scalar zero-division exceptions also match. Finite
  results are checked bitwise; nonfinite results use array equality with NaNs.
  Each result retains a distinct direction map.
- 76 additional component comparisons against exact candidate 18 pass. Across
  these small synthetic calls, direction-object constructions fall from 1,149
  to 974 (175 fewer). This is an operation count, not a measured speedup or an
  estimate of official workload multiplicity.
- Initial diagnostic runs exposed scalar-incompatible assumptions in the test
  helper (array indexing of Python floats, then uncaught scalar division by
  zero). The diagnostic now normalizes comparison values and compares exception
  types. No simulator correction or tolerance relaxation was needed.

Request both unchanged full official benchmarks on the new exact SHA, all saved
output/gradient comparisons and the fourteen generalization cases, then an
independent source review. If promising, obtain balanced paired fresh-process
confirmation against candidate 7 and candidate 18 to distinguish the incremental
change. Keep phase/memory/overlap evidence and each benchmark's samples, median
and range separate. No candidate-19 official measurements exist yet. Existing
pristine signal/gradient/loss mismatches, rand1/rand3 sensitivity disagreements,
six unresolved grid finite-difference coordinates and JVP/Hessian limitations
remain unresolved. Failed trials and the superseded freeze request remain above.

## Candidate 19 feedback: no confirmed incremental reverse gain

Simulator SHA 11c37f92622e8eace7a62656d7f9dbb4ee3f37e6, evaluator request
b7c860a7c71c417b941859d7ca12c5ba. Jobs grid-1/2/3 and aligo-1/2/3 all passed
the unchanged official benchmarks. Complete fresh-process seconds:

- Grid: [0.8205914627760649, 0.78706637583673, 0.7878785859793425], median
  0.7878785859793425, range [0.78706637583673, 0.8205914627760649].
- aLIGO: [0.5410497728735209, 0.5445662662386894, 0.5395652372390032], median
  0.5410497728735209, range [0.5395652372390032, 0.5445662662386894].

Phase samples in milliseconds:

- Grid forward [183.165085, 176.607188, 182.860600], reverse [79.894790,
  76.238820, 76.452700], imports [289.420856, 267.301988, 265.002145], build
  [75.174522, 73.072582, 69.090500]. Relative to candidate 18's unpaired medians:
  forward +2.359426 ms, reverse +0.621511 ms, imports +1.492839 ms,
  build -0.314357 ms. Complete median -9.502601 ms.
- aLIGO forward [32.699630, 32.751160, 32.216866], reverse [13.741620,
  13.411511, 13.235277], imports [263.004463, 266.489267, 263.894254], build
  [37.354199, 37.972262, 37.107212]. Unpaired deltas versus 18: forward
  -0.129268 ms, reverse -0.566391 ms, imports -2.253484 ms, build -0.325061 ms.
  Complete median -4.147058 ms.
- Versus admitted candidate 7, unpaired complete medians are lower by
  13.699098 ms grid and 7.505383 ms aLIGO. These are observations, not a
  confirmed gain. All samples are retained; overlapping grid ranges remain.
- Max sampled process-group RSS bytes: grid 627326976, aLIGO 295616512,
  generalization 809222144. CPU2 / one logical CPU / threads1 / no persistent
  cache. No infrastructure failure or memory exceedance. Other-host contention
  remains possible; no additional overlap evidence was supplied.

Inspected every per-array strict-comparison receipt and programmatically checked
against candidate 18: all six official comparison records and all fourteen
seed/pristine generalization case records are exactly unchanged. All seed
comparisons pass. Official saved-array hashes match candidate 18 for both setups;
remote raw NPZ files were not reopened. Pristine comparisons still fail: grid
131 signal/3 gradient/1 loss entries, aLIGO 1 loss entry; rand1/rand3 log sensitivity
errors remain 2.036099068405406e-4 and 5.8100919558157216e-5. Seed gradient max
absolute differences remain 5.686350050382316e-6 grid and 3.637978807091713e-11
aLIGO. Generalization self-comparison is not independent seed evidence. The six
unresolved grid FD coordinates and whole-pass JVP/Hessian limitation remain.

Decision: confirmed_improvement=false, source_review=null, ranking_eligible=false.
Admission requires source review and paired evidence for overlapping ranges.
The scalar allocation refinement has no observed incremental grid reverse gain.
Stop tuning this representation now; preserve candidates 18/19 and their pending
confirmation requests. Return production host.py to admitted candidate 7 for a
distinct structural forward-assembly experiment. No history is reset or hidden.

## Candidate 20: reuse sweep-independent component values within assembly

New candidate SHA and both official job IDs pending supervisor commit/evaluation.
Production source is exactly admitted ee4fea28c04d482566be16e916b609d7c6a99e5e
except the following host_pass.py change. Candidate 18/19 derivative changes are
absent. No transfer of another lane's unreviewed source is involved.

Concrete redundancy: `_assemble` tiles carrier parameter rows for the signal
sweep; `SystemPlan.values` evaluates every component at every resulting row,
including components whose entire input-index list excludes the changing
parameter indices. Those component inputs are identical in repeated blocks.
The measured parent forward phase (~181 ms grid, ~33 ms aLIGO) includes this
assembly. Its exact fraction and official invariant multiplicities remain
unmeasured; the evaluator determines whether avoiding this work outweighs the
new plan construction, splitting and replication costs.

Implementation:

- During signal SystemPlan construction, partition each group by whether any
  input index refers to a swept parameter. Normalize negative aliases for this
  comparison. Numerical values and derivative slots do not influence it.
- `_assemble` supplies the original carrier-row block length. On a matching
  parameter width and repeated-block shape, evaluate independent components on
  the original block and tile their outputs; evaluate dependent components on
  every row. Mixed groups preserve original component/output order. The normal
  values path remains for calls without a repeated-block contract.
- Plan identity includes the parameter count and sweep indices. There is no
  numerical cache, retained output, cross-evaluation reuse or work outside the
  evaluation. Each forward still assembles all matrices and factors afresh.
- Backward Jacobians and scatters are unchanged. A swept input at numerical zero
  remains structurally dependent. All input slots are inspected conservatively,
  even unused padding. No coefficient, gradient or physical output is dropped.

Local validation via `overnight-numerics-sweep-check.py`, in the existing NumPy
venv with AST-extracted kernels; no benchmarks or timings:

- Existing 37 assembly/backward cases pass.
- 240 new forward/backward comparisons against admitted source pass, covering
  all 19 functions, 1/2 original rows, 1/3/7 repetitions, no/partial/all swept
  columns, negative aliases, duplicate reads/writes, complex inputs, zero-valued
  swept parameters, entirely zero rows and nonfinite invariant inputs. Finite
  results are bitwise equal including signed zeros; nonfinite entries use array
  equality. The same plan is reevaluated with changed inputs in these checks.
- A small arbitrary sweep reduces evaluated component rows from 798 to 342.
  This establishes redundant arithmetic elimination, not an official speedup or
  the multiplicity of either official optical setup.

Request both unchanged official benchmarks and all saved outputs/gradients,
14-case generalization and independent source review on the new exact SHA.
For promising results obtain paired fresh-process complete runs against admitted
candidate 7, including phase/memory/overlap evidence. Keep all inherited numerical
findings explicit. Do not combine pending derivative/residual candidates. If
splitting overhead erases this saving, reject it rather than infer a warm gain.

## Candidate 20 feedback: forward reuse not established

Exact SHA 9ebf922193244d29ef9be1f8b126765d06873ca5, request
6164d6189e504fe88aa2ea64b274cd81, jobs grid-1/2/3 and aligo-1/2/3. All six
unchanged official runs pass. Complete fresh-process seconds:

- Grid [0.8735452610999346, 0.8006555959582329, 0.7933855932205915]; median
  0.8006555959582329, range [0.7933855932205915, 0.8735452610999346].
- aLIGO [0.5486961435526609, 0.550493536517024, 0.6647725906223059]; median
  0.550493536517024, range [0.5486961435526609, 0.6647725906223059].

Phase samples in ms: grid forward [192.554573, 186.639916, 177.407047], reverse
[88.942500, 84.881224, 84.554538], build [93.592238, 69.272416, 74.030554],
imports [293.179242, 263.995320, 264.748184]; aLIGO forward [32.893861,
33.608083, 32.125410], reverse [14.403755, 15.227593, 14.347833], build
[39.100345, 43.285580, 37.470493], imports [268.023575, 266.712012, 263.800686].
aLIGO gradient compilation [53.267438, 53.214891, 176.677136] accounts for much
of its slow third sample; no sample is removed and its cause is not established.
Relative to admitted candidate 7's historical medians: grid complete -0.922088 ms,
forward +5.476829 ms, reverse -0.476200 ms; aLIGO complete +1.938380 ms, forward
+0.003711 ms, reverse +0.019603 ms. These unpaired observations show no established
forward or complete improvement.

Max sampled process-group RSS bytes: grid 593416192, aLIGO 305176576,
generalization 855490560. Fixed CPU2 / one logical CPU / library threads1 / no
persistent cache. No infrastructure failures or memory-budget exceedances;
external contention is not excluded. Grid relative range 10.011754%, aLIGO
21.085887%. Admission rejects both timing stability checks, missing source
review, below-threshold large gain and overlapping large ranges. confirmed=false,
review=null, ranking_eligible=false. Do not describe this as an admitted gain.

Programmatically compared every official per-array strict record and every
initial-seed/pristine generalization case record against candidate 19: unchanged.
Both official archive hashes remain the same as 19, seed comparisons pass and
seed generalization passes 14/14. Raw remote NPZ files were not reopened. Pristine
grid still has 131 signal/3 gradient/1 loss mismatches, aLIGO 1 loss mismatch;
rand1/rand3 log sensitivity errors remain about 2.04e-4 and 5.81e-5. Seed gradient
max absolute differences remain 5.686350050382316e-6 grid and 3.637978807091713e-11
aLIGO. Six grid FD coordinates 54/59/63/136/161/163 and broader JVP/Hessian
compatibility remain unresolved. Generalization self-comparison is not used as
independent validation.

Decision: remove forward reuse for the next trial, retaining 20 in branch history.
Its structural partition enables a distinct phase test below. Do not add another
forward-assembly variant without attribution showing material cost there.

## Candidate 21: sweep-independent Jacobians, original forward assembly

Candidate SHA and official job IDs pending supervisor commit/evaluation. Production
source equals admitted ee4fea28 except host_pass.py. Forward SystemPlan.values
and its `_assemble` call are restored exactly to that parent. Shared-primal
candidates 18/19 and all other pending execution variants are absent.

Hypothesis: the admitted reverse phase (~85.36 ms grid, ~14.38 ms aLIGO) repeats
component derivative arithmetic for identical input blocks. Each active slot in
function_jacobian executes the component's Dual rules anew. The topology-derived
partition from 20 can limit that repeated calculation to the original block,
while preserving all per-row cotangents. This is a second structural-sweep trial,
not promotion of 20's unsuccessful forward change.

Implementation: signal SystemPlan.backward accepts the original carrier-row
block length, provided only by host_backward after the same parameter expansion.
It evaluates sweep-independent components' J/K blocks once per original row and
tiles those Jacobians back to full shape. Dependent components retain every row.
The subsequent multiply, reduction, conjugation and parameter scatter are exactly
the admitted operations in the same order. No cotangents are summed early, no
zero derivative entries are pruned, and nothing numerical survives this call.
Changing all indices keeps the ordinary path. Plan identity includes sweep
indices and parameter width; negative aliases are normalized structurally.

`overnight-numerics-sweep-jacobian-check.py` passes the existing 37 assembly checks
plus 240 repeated-block forward/backward comparisons across all 19 component
functions, multiple original block lengths, repetition counts, empty/partial/full
sweeps, negative index aliases, repeated destinations, real/complex/zero/nonfinite
inputs. Finite results are bitwise equal including signed zero, nonfinite results
array-equal. Synthetic Jacobian-row evaluations decrease 798 -> 342. These are
small AST-extracted NumPy inspections, not optical benchmarks or timing evidence.
`git diff --check` passes. No additional numerical accuracy claim is made.

Request both unchanged exact-SHA official benchmarks, full output/gradient and
14-case generalization comparisons, and independent review. If promising, request
paired fresh-process complete runs against admitted candidate 7. For attribution,
please additionally report each signal group's independent/dependent row counts
from `host_plan.signal.sweep_partition` and callback profiling in a separate
untimed diagnostic job. Official timing must include plan construction. No plan
multiplicity for either official setup is currently claimed. Preserve all inherited
strict disagreements, phase samples, memory and contention evidence. If there is
no meaningful saving, retire structural sweep reuse rather than combine it with
unconfirmed derivative/storage candidates.


## Candidate 21 feedback and structural-sweep handoff

Evaluated SHA `2803e9158e78b4bcbf2766fd32cb9ba7f9b376d9`, request
`d55e0e34766f4c1b984e9a99f75c92c7`; jobs grid-1/2/3 and aligo-1/2/3.
All six unchanged official runs passed. Complete fresh-process seconds:

- Grid: 0.8268340174108744, 0.7930844146758318, 0.8006586339324713;
  median 0.8006586339324713, range 0.7930844146758318–0.8268340174108744.
- Official aLIGO: 0.545679084956646, 0.5461974944919348, 0.5469981133937836;
  median 0.5461974944919348, range 0.545679084956646–0.5469981133937836.

Grid forward milliseconds: 181.103174, 176.656852, 183.080725; reverse:
86.647019, 81.383996, 82.546156. aLIGO forward: 34.445215, 33.935232,
32.404780; reverse: 14.224285, 13.893938, 14.474554.
Compared with admitted candidate 7's historical cohort, median grid complete
-0.919050 ms, forward -0.059913 ms, reverse -2.811268 ms, build +0.062106 ms,
imports +2.709905 ms. aLIGO complete -2.357662 ms, forward +1.045082 ms,
reverse -0.159867 ms, build +0.257209 ms, imports +1.101728 ms. These are
unpaired observations, not causal phase savings. Grid ranges overlap; no
repeat-supported improvement is established. Relative ranges: grid 4.215230%,
aLIGO 0.241493%.

Maximum sampled process-group RSS bytes: grid 649666560, aLIGO 313384960,
generalization 834813952. No infrastructure failure or memory exceedance.
Fixed CPU2 / one logical CPU / library threads1 / no persistent cache. Other-host
contention is not excluded. confirmed_improvement=false, source_review=null,
ranking_eligible=false. Admission reasons: requires_source_review,
large_gain_below_selection_threshold, and overlapping large first-run ranges.

Inspected all six official per-array strict comparison records and all fourteen
initial-seed/pristine generalization case records; programmatic comparison with
candidate 20 finds them unchanged. Both official archive hashes are unchanged.
All seed comparisons pass, including all 14 generalization cases. Remote raw NPZ
files were not reopened. Pristine strict review still fails: grid 131 signal,
3 gradient and 1 loss entries, aLIGO 1 loss entry; rand1/rand3 sensitivity log
errors about 2.04e-4 and 5.81e-5 remain. Seed-relative gradient max absolute
differences are 5.686350050382316e-6 grid and 3.637978807091713e-11 aLIGO.
The six grid FD coordinates 54/59/63/136/161/163 remain unresolved; prior aLIGO
29/29 checks remain separate evidence. Whole-pass JVP/Hessians remain unsupported.
Do not treat the generalization artifact's self-comparison as independent proof.

Decision: close structural sweep reuse after candidates 20 and 21 did not show
a meaningful complete-run gain. Restore host_pass.py exactly from admitted
`ee4fea28c04d482566be16e916b609d7c6a99e5e`. All production simulator files now
match that admitted revision; no other lane changes are transferred. This is a
working-tree restoration for the supervisor to record, not a history reset.
Failed/unconfirmed revisions and their revision-specific synthetic scripts stay
preserved. No new performance candidate is submitted by this handoff.

Next evidence requested from coordinator: use the existing opt-in
`experiments/notes/overnight-numerics-profile.py::collect_host_profiles` around a
separate synchronized diagnostic driver on admitted candidate 7, with unchanged
full inputs and fixed resource policy. Archive first forward and first backward
callback records separately, including self/cumulative times and call counts for
_assemble, SystemPlan.values/backward, function_jacobian, _factor, _solve,
_Products.apply and add.at. If additional instrumentation is approved, record
actual refinement correction counts and component-group multiplicities. Keep
instrumented measurements separate from unchanged official timing; do not edit
public harnesses. No callback profile has yet been supplied to this lane.

Use that attribution before choosing another implementation: if derivative
contractions dominate, the preserved candidate 13 evidence and its outstanding
paired request deserve examination; if residual products dominate, examine
candidate 9. Shared-primal candidates 18/19 also remain unconfirmed. None should
be combined or promoted automatically. Existing requests for paired fresh-process
candidate/parent dual-official runs and independent source review remain pending;
this turn does not claim they were performed. A subsequent proposal requires both
exact-SHA official benchmarks and full numerical/generalization inspection anew.
This stop handoff closes the sweep-reuse hypothesis, not the authorized campaign.


## Candidate 22: one ordered parameter scatter per component group

Supervisor requested a concrete experiment after the candidate 21 stop handoff;
no new evaluator/profile evidence was supplied. Retain the preceding 21 feedback
and failed-trial history. Candidate SHA and job IDs pending supervisor submission.
Production source is admitted ee4fea28 plus this host_pass.py change only; the
preserved restoration removes 21's sweep reuse. No other lane is combined.

Hypothesis: SystemPlan.backward repeatedly invokes np.add.at for each derivative
slot after computing a group's entire input cotangent tensor. Coalesce those
calls into one group scatter, with a topology-derived destination array prepared
once at build. This targets reverse execution (admitted grid median 85.357424 ms,
aLIGO 14.384152 ms), although no callback attribution has established the fraction
spent here. The measured redundancy is call/index preparation, not repeated
factorization or repeated physical solves. No runtime saving is claimed.

Destination order is slot-major, then component row, matching the original nested
loop's order for each parameter accumulator. Contributions are transposed from
(B,R,S) to (B,S,R), then reshaped to (B,S*R). Different batch rows never share a
parameter accumulator, so grouping their updates does not change per-destination
addition order. Groups retain their original order. Negative parameter aliases,
negative and repeated slots, and duplicate destinations remain intact; no
uniqueness assumption or zero pruning is introduced. Jacobians, contraction
expressions, outputs, physical inputs, all refinement/solve paths and all JAX
boundaries are unchanged. The new structural arrays are deterministic functions
of existing groups already covered by the plan key.

This is a different scatter mechanism from candidate 8's per-slot uniqueness
shortcut and batched solve-free reverse algebra, neither of which is included.
It also does not revisit the retired sweep-independent derivative mechanism.
Cost tradeoff: one static R*S integer destination array per group and, when
reshape requires it, one B*R*S complex contribution copy at reverse execution,
in exchange for replacing S scatter calls by one. No implementation tuning knob.
The official build/gradient phases must count these costs.

Validation: overnight-numerics-group-scatter-check.py passes 37 inherited
assembly/backward checks, 684 real-component comparisons across all 19 functions,
and 160 prescribed-Jacobian cancellation checks: 881 total. Includes negative
parameter aliases, negative/repeated/empty slots, duplicate groups/destinations,
complex and zero inputs, signed zero/nonfinite cotangents, extreme cancellation,
and empty batch rows. Finite entries match admitted parent bitwise (including
signed zero); nonfinite entries compare array-equal. In a small synthetic
19-group, 7-slot case, actual np.add.at call counts fall from 133 to 19 with equal
results. These are AST-extracted host-kernel checks, not official workloads,
timings, or a universal correctness certificate. Syntax and git diff checks pass.

Request unchanged full grid and official aLIGO runs on the same exact simulator
SHA, numerical array/gradient and fourteen-case generalization comparisons, and
independent source review. If the full-run result looks promising, obtain paired
fresh-process repetitions against admitted ee4fea28 under matching CPU/resource
policy; report each workload separately. Callback profiling remains requested
separately from official timings. Preserve all inherited pristine disagreements
and unresolved FD coordinates detailed above. Do not promote based on call counts
or an isolated reverse-phase reduction. If this narrowly scoped change fails to
improve, retire group-scatter coalescing without bundling unrelated optimizations.


## Candidate 22 feedback: retire group-scatter coalescing

SHA `c3e5e266b9a99e7e7513d8897e91f10c9548420e`; request
`c2e4ff0e96c7436785dbd822f281f63b`, jobs grid-1/2/3 and aligo-1/2/3.
All six unchanged official runs passed. Complete fresh-process seconds:

- Grid: 0.8337271902710199, 0.8021378945559263, 0.7915780618786812;
  median 0.8021378945559263, range 0.7915780618786812–0.8337271902710199.
- Official aLIGO: 0.5452605132013559, 0.5413661487400532, 0.542662775143981;
  median 0.542662775143981, range 0.5413661487400532–0.5452605132013559.

Grid forward ms 186.761927/183.446730/178.069087; reverse
84.817791/82.909863/86.196870. aLIGO forward
32.981979/32.609781/32.476936; reverse14.579657/14.517339/14.559438.
Median deltas versus historical admitted candidate7, in ms: grid complete
+0.560211, forward +2.283643, reverse -0.539633, build -0.653427,
imports -0.740286; aLIGO complete -5.892381, forward -0.280369,
reverse +0.175286, build +0.020165, imports +1.163602. Unpaired phase
observations do not establish causality. Grid complete median is slower; no
meaningful reverse saving is demonstrated. Retire this mechanism after one trial.

Maximum sampled process-group RSS bytes grid642359296, aLIGO295714816,
generalization788893696. No infrastructure failure or memory exceedance. Fixed
CPU2/one logical CPU/threads1/no persistent cache; external contention not excluded.
Confirmed=false, source_review=null, ranking_eligible=false. Admission reasons
missing review, below-threshold large gain, overlapping large timing ranges.

Compared every official strict record and every initial-seed/pristine
14-case generalization record programmatically against21: unchanged. Both
official archive hashes unchanged. All initial-seed checks pass. Remote raw NPZ
files were not reopened. Pristine strict disagreements remain grid131 signal/
3 gradient/1 loss and aLIGO1 loss; rand1/rand3 sensitivity log errors about2.04e-4
and5.81e-5 remain. Six grid FD coordinates54/59/63/136/161/163 unresolved;
prior aLIGO29/29 and first-order-only custom VJP caveats unchanged. The artifact
self-comparison is not independent validation. No tolerance change or numerical
failure suppression is justified. Retained22 in history; source restored to7
before the single new change below.

## Candidate 23: bound live Jacobian storage by independent batch rows

Candidate SHA/job IDs pending supervisor submission. Only host_pass.py differs
from admitted ee4fea28. Scatter coalescing22, sweep reuse20/21 and all other
unconfirmed variants are absent. No other-lane transfer or combination.

Hypothesis: the admitted reverse phase materializes two full complex Jacobian
blocks per component group, followed by equally shaped multiplication temporaries.
Split only independent batch rows into blocks before these operations to reduce
live allocations/cache pressure. This is execution blocking, not Jacobian layout
permutation (16), streamed derivative-slot contraction (12/13), reuse of identical
inputs (17/20/21), or shared primal differentiation (18/19). All derivative slots
and all group rows are still computed. It may cost more Python/Dual dispatch.
Historical derivative-phase observations motivate the target, but no full callback
profile was supplied, and no timing improvement is claimed.

SystemPlan._group_pullback derives a batch-block length from the actual group's
component count and derivative-slot count. Each block invokes the unchanged
function_jacobian and the exact same axis2 multiply/sum/conjugate expressions.
It places the resulting independent row cotangents in a full inputs_bar array;
original per-slot scatter order and np.add.at are preserved. No early cotangent
summation, zero pruning, precision change, factor/solve change, output removal,
input-value detection or numerical cache is introduced. A one-row block may
exceed the memory target: the row is retained intact. Empty/small batches use
the original whole-group calculation.

Implementation menu for attributable future trials: class constant
SystemPlan.JACOBIAN_BLOCK_BYTES defaults to262144 bytes (256KiB). Legal settings
are positive integer byte targets; change only between exact-revision evaluations.
block_rows=max(1,target//max(1,2*components*4*slots*16)). The target describes
just the live pair of complex128 Jacobians, not a hard process memory bound.
It is generic for arbitrary topology, batch lengths and slot counts. No official
shape or frequency count is encoded. Do not vary physical design variables as
tuning parameters. No further parameter search is proposed before this trial.

Validation: overnight-numerics-block-pullback-check.py passes37 inherited
assembly/backward comparisons,2736 local component-contraction comparisons and
19 blocked integration comparisons:2792 total. All19 component functions,
empty/small/blocked batches, different component counts, empty/single/negative/
repeated slots, complex/zero/nonfinite inputs and cotangents, negative parameter
aliases, duplicate parameter destinations are covered. Finite entries equal
parent bitwise including signed zero; nonfinite entries array-equal. Integration
checks preserve the original scatter semantics. Tests are small AST-extracted
host kernels; no full optical workload or official benchmark was run locally.

One illustrative synthetic surface group (37 independent rows,43 component rows,
7 derivative slots) allocates1,425,536 bytes for the parent's Jacobian pair.
Candidate pairs are231168 bytes six times then38528 bytes, i.e. seven calls
instead of one. Measured traced peak allocation falls2,496,720->672,488 bytes;
this excludes pre-existing input arrays and is not process RSS. Both resulting
cotangent arrays match bitwise. No runtime saving follows from allocation alone.
Syntax and git diff checks pass.

Request both unchanged official full benchmarks on this same exact new SHA,
complete array/gradient comparisons,14-case seed/pristine generalization, and
independent source review. Keep inherited numerical disagreements visible. If
promising, request paired fresh-process complete candidate/parent runs with
separate grid/aLIGO samples, medians/ranges, phase tradeoffs, RSS and contention
status. Count all setup and callback work. Separate profiling should report
function_jacobian call counts and actual block triggering in arbitrary setups;
no triggering rate for either official workload has been claimed here. If the
added dispatch loses time, retire this blocking choice instead of bundling it
with unrelated pending candidates.

## Candidate 23 feedback: retire batch blocking

SHA b4165e54df9bac152c10af67b5583c60a1f520ba, dual job
 a29a27a2a070405dafad4de8a21b723c (grid-1/2/3, aligo-1/2/3).
Both unchanged official benchmarks pass all three fresh processes. Seconds:

- Grid: 0.8398048356175423, 0.8014963883906603, 0.8129627462476492;
  median 0.8129627462476492; range 0.8014963883906603–0.8398048356175423.
- Official aLIGO: 0.5417727902531624, 0.5452161803841591, 0.571299472823739;
  median 0.5452161803841591; range 0.5417727902531624–0.571299472823739.

Grid forward ms184.827859/177.489083/185.769409; reverse
97.015653/93.049452/94.574656. aLIGO forward
32.458628/32.921391/33.793151; reverse14.453920/14.556237/14.511038.
Median deltas versus historical admitted7, ms: grid complete +11.385063,
forward +3.664772, reverse +9.217232, build -0.639553, imports +0.504041;
aLIGO complete -3.338976, forward +0.031241, reverse +0.126886.
These are unpaired observations, not causal phase attribution.
The third aLIGO sample includes289.607815ms imports versus262.666350/263.567248ms
in the other two; retain all samples. Allocation reduction did not demonstrate
runtime improvement. Stop this blocking mechanism without tuning its byte target.

Maximum sampled process-group RSS bytes grid596303872, aLIGO294883328,
generalization897134592. No infrastructure failure or memory exceedance. CPU2,
one logical CPU, threads1, no persistent cache. External contention not excluded.
confirmed_improvement=false, source_review=null, ranking_eligible=false;
selection reasons missing review, below-threshold gain, overlapping grid ranges.

All six official per-array strict records and all14 initial-seed/pristine
comparison records were compared programmatically with22: unchanged. Initial
seed comparisons pass for every output/gradient; this is tolerance agreement,
not bitwise identity to seed. Official saved archive hashes are unchanged from22.
Raw remote NPZ arrays were not reopened. The candidate self-comparison is not
independent evidence. Pristine disagreements remain grid131 signal/3 gradient/
1 loss, official aLIGO1 loss; rand1/rand3 sensitivity log discrepancies about
2.04e-4/5.81e-5. Grid finite-difference coordinates54/59/63/136/161/163 remain
unresolved, earlier aLIGO29/29 checks remain separate, and custom VJP lacks
JVP/Hessians. No new numerical discrepancy is reported by these comparisons.

## Candidate 24: reuse private Jacobian arrays for cotangent products

Candidate SHA and dual job IDs pending supervisor. Restore host_pass.py to the
admitted ee4fea28 source before this single change; no reset or history rewrite.
All failed proposals remain in history. Production differs from admitted7 only
by six added lines and one replaced line in SystemPlan.backward. No transfer
from another lane, no combination with22/23 or other unconfirmed candidates.

The original contraction builds linear*output_bar and antilinear*output_bar
arrays before reducing each along the four component outputs. function_jacobian
unconditionally creates independent writable complex128 linear and antilinear
arrays with np.zeros; these arrays have no other consumer in backward. Use
np.multiply(...,out=...) to place products in those private buffers. Keep the
same axis2 sums, conjugation, addition, full-group Jacobian call, and per-slot
np.add.at order. No structural/numerical zero is skipped, no dtype/layout change,
no reused numerical state, no parameter tuning, no solve/refinement modification.
The eliminated product allocations scale as B*R*4*S*16 bytes each; this does not
mean two extra tensors are simultaneously live in the parent. The actual peak
benefit can be much smaller because Jacobian construction also allocates storage.

This narrower refinement addresses23's memory hypothesis without additional
component calls or blocking. It is distinct from changing storage order, grouping
scatters, streaming slots or reusing evaluations at equal inputs. There is no
configurable threshold or topology-dependent dispatch. Hypothesis: less transient
memory traffic might lower the reverse phase, but this is not yet a measured
runtime bottleneck or a speed improvement. The previously requested separate
callback profile has not been supplied; no profile result is invented here.

Validation: overnight-numerics-inplace-jacobian-check.py passes2736 complete
synthetic backward comparisons plus37 inherited assembly/backward cases (2773).
All19 component functions; B0/1/7/37; component counts1/5/43; empty, single,
repeated and negative slots; negative/repeated parameter destinations; complex,
zero and nonfinite inputs/cotangents; duplicate and overwritten output writes.
Finite entries match admitted parent bitwise including signed zero; nonfinite
entries array-equal. Caller inputs/cotangents remain unchanged. Allocation probe
also verifies Jacobian buffer ownership/non-aliasing. These AST-extracted local
host checks are not official workloads, optical generalization or JAX tests.

Illustrative surface group B37,R43,S7: both versions make one Jacobian call,
allocating the same1,425,536-byte Jacobian pair. Traced complete backward peak
falls2,822,384 to2,649,008 bytes (173,376 bytes), excluding pre-existing inputs.
This modest synthetic peak saving is not process RSS or timing evidence.
No benchmark was run locally. Syntax and git diff checks pass.

Request supervisor evaluation of both unchanged official workloads on the same
new exact SHA, saved all-output/gradient comparisons to seed and admitted parent,
all14 generalization cases including modulated/random setups, and independent
source review before promotion. If promising, obtain matched fresh-process parent
and candidate repetitions with separate grid/aLIGO samples, medians/ranges,
phases, RSS and overlap information. Keep inherited strict/pristine findings
visible. Retire this refinement if complete-run gain is not repeat-supported;
do not infer speed from fewer allocations or combine pending candidates.

## Candidate 24 feedback and contraction/allocation handoff

SHA e091febbb132c65ffd412c89778d7520785c2a1a; dual job
1ebdbb09b0a24511ae182429e9b0c979, grid-1/2/3 and aligo-1/2/3.
Both unchanged official workloads pass all three fresh runs. Seconds:

- Grid samples0.8760746754705906,0.8320770859718323,0.8043785057961941;
  median0.8320770859718323; range0.8043785057961941–0.8760746754705906.
- Official aLIGO samples0.5471797585487366,0.5447073206305504,0.5493837613612413;
  median0.5471797585487366; range0.5447073206305504–0.5493837613612413.

Grid forward ms181.289311/193.822512/181.690447; reverse
84.723640/82.618972/84.840089. aLIGO forward
32.779921/32.225138/32.966817; reverse14.464036/14.156878/14.783233.
Against historical admitted7, median deltas in ms: grid complete+30.499402,
forward+0.527360, reverse-0.633784, build+0.556977, imports+2.103361;
aLIGO complete-1.375398, forward-0.110229, reverse+0.079884,
build+0.962654, imports+2.547294. These unpaired observations do not isolate
causality. Grid first imports341.626432ms versus265.827404/267.703975ms;
second forward/build also higher. No samples removed. A sub-ms historical
reverse delta does not establish a stable complete-run gain.

Maximum sampled process-group RSS bytes grid616017920, aLIGO302800896,
generalization868126720. No infrastructure failures or memory exceedance.
CPU2/one logical CPU/threads1/no persistent compilation cache; other-host
contention not excluded. confirmed_improvement=false, source_review=null,
ranking_eligible=false. Selection rejected missing review, below-threshold large
gain and overlapping large ranges. This is not an organizer ranking rule.

Programmatically compared all six official strict-comparison records and all14
seed/pristine generalization records against23: unchanged. All initial-seed
array/gradient comparisons pass; official archive hashes unchanged. Raw remote
NPZ files were not reopened. Seed tolerance agreement is not bitwise agreement.
Pristine grid131 signal/3 gradient/1 loss, official aLIGO1 loss, rand1/rand3
sensitivity log disagreements about2.04e-4/5.81e-5 persist. Grid FD coordinates
54/59/63/136/161/163 remain unresolved; prior aLIGO29/29 checks and first-order
custom VJP scope remain separate. No new numerical mismatch is reported by these
records. Generalization self-comparison is not independent validation.

Decision: close trials22–24 as unconfirmed. Their grid complete medians are
0.802137895,0.812962746,0.832077086 seconds; reverse medians84.817791,
94.574656,84.723640ms. Admitted7 historical grid complete0.801577684s,
reverse85.357424ms. Neither ordered scatter coalescing, batch blocking, nor
private Jacobian product-buffer reuse earned promotion. Do not tune more
contraction buffers or combine these variants. All commits/diagnostics retained.

Restored host_pass.py to admitted ee4fea28 by a working-tree edit; read-only
comparison confirms the entire differometor tree equals that revision. No history
reset, commit, push or independent benchmark. This restoration is not a newly
measured candidate; ready_for_evaluation=false. Stop this hypothesis, not the
user-authorized campaign. Existing unresolved numerical findings remain intact.

Next supervisor action: use the existing opt-in
experiments/notes/overnight-numerics-profile.py in a separate, explicitly profiled
admitted-parent evaluation. Request call counts and cumulative/self times for
_assemble, SystemPlan.values/backward, function_jacobian, _factor, _solve and
_Products.apply; record refinement iteration counts separately if instrumented.
Keep profiling separate from official timing confirmation and preserve the public
harness. The source inspection confirms signal solves already batch direct RHS
and covariance columns, and factors are reused in backward. Do not propose those
as new duplication. Forward residual products and numerical factorization remain
possible targets, but their relative costs have not been measured here. Select
a distinct execution mechanism only from that profile or a proven redundant
operation, with both official exact-SHA checks and independent review afterward.
Earlier candidate13 paired confirmations and candidate18 review requests remain
unfulfilled; their lower observed reverse times are not admitted improvements.

## Candidate 25: reuse column ordering within a fresh forward call

Supervisor resumed after the24 handoff and explicitly requested a concrete next
experiment. No new evaluator result arrived:24 feedback above is unchanged.
Candidate SHA/jobs pending. Production parent is admitted ee4fea28; only
host_pass.py changes. The preserved restoration of24 is included, not evaluated
as a separate candidate. No other-lane combination or unconfirmed contraction,
scatter, buffer, component or residual-product variant is included.

Hypothesis: each signal row currently calls gstrf with ColPerm=COLAMD despite
sharing exactly the same supplied sparse pattern. Numerical matrices differ and
must be factored afresh, but recomputing a fill-reducing column permutation is
redundant structural work. Forward execution remains about181ms on historical
admitted grid versus33ms on aLIGO. This trial changes symbolic column ordering
work rather than numerical factor reuse. No callback profile has been supplied;
its actual fraction of forward time is unknown. No speed claim is made.

Implementation: first signal row follows the existing factorization path. For a
multirow forward using the native extension, _ColumnOrdering extracts its perm_c,
derives the CSC permutation of columns and all structural entries, then factors
every later row's newly assembled values with ColPerm=NATURAL. All other SuperLU
options remain unchanged. No competing ordering or physical-input tuning is used.
Pattern entries with numerical zero remain included. The ordering object is local
to that forward call; every subsequent forward starts with a new COLAMD factor.
No symbolic or numerical data are cached across evaluations by this change.

For B=A[:,columns], normal solve maps y=B^-1 b back as x=y[inverse]; transpose
and adjoint solves use rhs[columns] with the B factors. _PermutedFactor exposes
only the private solve interface used by host execution. These wrappers enter the
existing within-evaluation forward/backward state, so reverse solves also operate
in original coordinates. _solve still computes residuals against the ORIGINAL
matrix and retains its three-step maximum,1e-14 correction criterion and every
existing correction operation. No coefficient or gradient convention changes.
The no-matching-forward backward fallback continues to use ordinary COLAMD factors.
Public SciPy fallback is unchanged and does not enable this optimization; single
row forwards also retain the ordinary path. The condition is generic batch count
and native-extension availability, never topology identity or known workload shape.

Costs/risks: plan construction allocates structural permutation arrays; each later
factor gathers its coefficients, normal solves gather returned solutions, and
transpose/adjoint solves gather RHS arrays. These overheads could erase any
ordering saving, especially on aLIGO. Native SuperLU may make different internal
choices on untested patterns even though the column-permutation algebra is exact.
Bitwise agreement on local cases is bounded evidence, not a general stability
certificate. Inspect every official/generalization output and gradient before
accepting this numerical execution change. No exception is suppressed.

Local evidence: preliminary540 random small factor comparisons (including scaled
matrices and both inspected symmetric-mode choices) showed identical solutions;
production changes ONLY ColPerm, not SymmetricMode. The retained reproducible
check is experiments/notes/overnight-numerics-column-order-check.py. It passes
196 factor pairs,1752 refined N/T/H solves (vector/1-column/3-column RHS), and48
actual host_forward loop comparisons. Refined solve results match parent bitwise;
refinement counts agree:1579 one-step,149 two-step,24 three-step. Covers sparse
random complex patterns, offdiagonal structural zeros that later become nonzero,
strong pivoting, similarity scaling from1e-9 to1e9 and nearly singular Hilbert
systems. Forward checks cover1/5/11 rows,1/3 detectors, changing or reused noise,
all five host_forward outputs, and saved-factor solves in original coordinates.
Each forward is called again with changed matrices; both assemble afresh and the
native path requests exactly1 COLAMD plus(count-1) NATURAL factorizations each
call. Eleven numerical factorizations remain eleven; only ten ordering requests
are eliminated in that illustrative case. Both extension and public fallback
paths are exercised; RHS/data/index inputs stay unchanged. No actual optical
fixture, official timing, full gradient or JAX transformation was run locally.
Syntax and whitespace checks pass. No dependencies installed or settings changed.

Request both unchanged full official benchmarks on one exact new SHA, complete
saved-output/gradient comparisons to initial seed and admitted parent, all14
random/modulated generalization cases and independent review. Preserve inherited
pristine signal/gradient/loss discrepancies, rand1/rand3 sensitivity disagreements,
six unresolved grid FD coordinates, earlier aLIGO29/29 checks, and JVP/Hessian
limitations. If promising, obtain repeated matched candidate/parent complete
fresh-process runs, separately reporting grid/aLIGO samples/median/range, forward
and reverse tradeoffs, RSS and job overlap. If a discrepancy is new, investigate
ordering/pivot/refinement behavior rather than loosening tolerance. If no stable
gain, retire this choice without combining it with pending historical candidates.

### Candidate25 feedback and candidate26: preserve solver output layout

25 SHA8aa393502844782c85bb84f381cad67b4d83296c, evaluator job
fb04003661e946e38638f38f3e19b06b (grid-1/2/3 and aligo-1/2/3).
All six official runs passed; no confirmed improvement, no source review yet.
Grid complete samples seconds:0.8338793199509382,0.7940353136509657,
0.7943721208721399; median0.7943721208721399,
range[0.7940353136509657,0.8338793199509382].
aLIGO samples:0.54917286708951,0.5458456967025995,0.5436431616544724;
median0.5458456967025995,range[0.5436431616544724,0.54917286708951].
Ranges overlap admitted7; selection did not promote. Historical median differences
are -7.206ms grid and -2.709ms aLIGO, not matched-cohort evidence of a gain.
Median phases ms (difference from historical admitted7): grid forward178.100144
(-3.062943),reverse87.398566(+2.041142),build69.674807(-4.319273),
imports268.407753(+2.807138); aLIGO forward32.737512(-0.152638),
reverse14.665924(+0.281772),build38.246561(+0.284016),
imports267.511480(+4.002672). Grid forward's apparent saving is partly offset by
reverse, with unrelated build/import variation. Peak sampled RSS bytes:
grid711069696,aligo294592512,generalization893956096. No infrastructure failure
or budget exceedance; external job contention remains unexcluded.

Official output archives and detailed comparison records match24 (grid112c0407...
/aligo9c1ce936...). All14 generalization cases pass initial-seed tolerances, but
numerical equality is NOT established. Newly nonzero sensitivity log errors vs
initial seed: uifo_20_5000=7.105427357601002e-15,
uifo_rand1=8.065725864980777e-11,uifo_rand2=2.1241675085548195e-11,
uifo_rand3=1.96489065018568e-08. All reported array pass/failure counts are
unchanged, including gradients. Against pristine, rand1 sensitivity error changes
from0.0002036099068405406 to0.00020360993885759626; rand2 from
9.538787537621829e-10 to9.584653071215143e-10; rand3 from
5.8100919558157216e-05 to5.80965652936527e-05. These are newly observed changes,
not evidence that the old disagreements are resolved. Inspected saved JSON
per-array reports; remote NPZ files were not independently reopened locally.
Generalization archive96f64113... also contains non-numerical metadata; its hash
alone is not an array-equality test. Candidate-self comparison is not independent.

Decision: investigate a narrow layout repair before any promotion of25. No
additional contraction/scatter variant or other-lane source is combined. The
admitted parent remains7, and25 remains preserved in history. This is a repair
of the distinct column-order hypothesis, not another trial of closed22–24.

Concrete inspection: SuperLU returns multi-column solutions in Fortran order.
25's normal-solve advanced row gather returns a C-order array, which propagates
through iterative-refinement addition. This is a proven execution difference,
not a proven cause of the remote numerical changes. An initial400 small complex
sparse cases (sizes6–74, changing coefficients, strong pivoting and similarity
scales10^-12–10^12) showed no direct N/T/H numerical differences. No actual optical
fixture or benchmark was run locally, and the local platform differs from the
Linux evaluator. Neither rounding nor a pivoting explanation is established.

26 hypothesis: retain the parent solver's output layout while reusing structural
column ordering. Its only numerical execution change relative25 replaces the
normal-solve row gather with np.empty_like(permuted) and
solution[columns]=permuted. For B=A[:,columns], x[columns]=B^-1 rhs exactly.
empty_like preserves the source layout; each element is assigned once because
columns is a permutation. Remove the now-unused inverse permutation and its
construction. No extra full copy is added: the gather's result allocation is
replaced by the equally sized scatter destination. Transpose/adjoint solves,
factorization policy, all original-coordinate residuals and refinement stopping
criteria remain unchanged. Every forward still assembles and factors afresh.
This may change scatter locality/performance; speed remains unmeasured.

Retained inspection overnight-numerics-column-layout-check.py compares admitted7,
committed25 and current26 on400 factor triples,3600 direct and refined solve
triples (N/T/H,1/2/5 RHS). All results are bitwise equal on these cases; all
refinement counts match and RHS inputs remain unchanged.25 changes layout in800
direct and800 refined results;26 changes layout in zero. Also reran the original
column-order inspection:196 factor pairs,1752 refined solves and48 forward calls
remain bitwise equal, correction-count distribution1579/149/24 unchanged.
These synthetic checks bound implementation behavior; they do not reproduce or
resolve the remote rand3 sensitivity change or validate optical gradients.

26 SHA/jobs pending supervisor commit. Request both unchanged official benchmarks,
all saved outputs/gradients against7,25 and initial seed, all14 generalization
cases, and independent source review before promotion. Specifically report whether
the four new sensitivity errors disappear, persist or grow. If they persist,
request evaluator-side per-matrix factor permutation, pivot and refined residual
comparisons for the affected arbitrary setups; do not invent an explanation or
continue blind permutation variants. If timing looks promising, obtain matched
fresh-process parent/candidate repetitions, including RSS and overlap records.
Inherited pristine signal/gradient/loss disagreements, six unresolved grid FD
coordinates54/59/63/136/161/163, prior aLIGO29/29 confirmation, and absent
JVP/Hessian support all remain explicit. No tolerances or workload changed.

### Candidate26 result: ordering-reuse hypothesis closed pending diagnostics

SHA ed51e8ed99c1abdc12e2f12065e5acd9b7bd662a; job
09ed095148424412ba56e990d89eaa94, grid-1/2/3 and aligo-1/2/3.
All six official runs passed. All14 generalization cases passed initial-seed
bounds; pristine strict comparisons remain failing. No source review, matched
parent repetitions or confirmed improvement was supplied. Selection reasons:
requires_source_review and overlapping large first-run ranges.

Grid complete seconds: [0.824301715940237,0.7941282782703638,
0.791149789467454], median0.7941282782703638,
range[0.791149789467454,0.824301715940237].
aLIGO complete seconds: [0.5497319493442774,0.5464204661548138,
0.5462490785866976], median0.5464204661548138,
range[0.5462490785866976,0.5497319493442774].
Median phase ms / difference from historical admitted7:
grid forward178.332029/-2.831059, reverse84.928872/-0.428552,
build72.830860/-1.163220, imports265.383678/-0.216937;
aLIGO forward33.201344/+0.311194, reverse14.859032/+0.474880,
build38.130740/+0.168195, imports264.834862/+1.326054.
Versus25 the forward median increased0.231884ms grid and0.463832ms aLIGO;
reverse changed-2.469694ms grid and+0.193108ms aLIGO. These unpaired small
changes do not establish a causal speed improvement. Peak sampled RSS bytes:
grid623939584,aligo289366016,generalization1004404736. No infrastructure failure
or memory exceedance; other-host contention remains unexcluded.

Programmatically compared every supplied official strict comparison and output
archive hash to25: identical. Also compared all14 case records against both
initial_seed and pristine: identical to25. Thus the layout repair DID NOT remove
the four newly nonzero sensitivity log errors documented above (rand3 remains
1.96489065018568e-08 versus initial seed). This rejects the proposed layout repair
as a resolution on the recorded cases; it does not identify a root cause. No
new failing counts, but passing a bound does not explain the numerical change.
Raw remote arrays were not independently available locally; these statements
refer to the evaluator's complete per-array comparison records. No numerical
agreement claim is based on the candidate-self audit or generalization ZIP hash.

Decision: retire25/26 from active optimization rather than submit another blind
permutation variant. Restore production host_pass.py exactly to admitted
 ee4fea28c04d482566be16e916b609d7c6a99e5e. All production differometor files now
match that parent; failed evaluated commits and diagnostic scripts remain in
history. This is a source restoration, not an unevaluated new optimization or
claim that26 was promoted. No additional official run is requested for identical
restored source. Three recent submissions24–26 had no confirmed improvement;
closed contraction/scatter ideas also remain closed.

Concrete supervisor diagnostic request before reopening ordering reuse:
use committed26 and admitted7 in the fixed evaluator environment, separately
from timing/promotion runs. For the four affected generalization cases, compare
the same assembled matrices and RHS at the first differing frequency/solve.
Record coefficient and RHS equality first; then compare ordinary COLAMD with
26's preordered NATURAL factors in ORIGINAL coordinates. Report effective column
permutations, row pivot permutations, factor sparsity, direct N/T/H solution
errors, each iterative-refinement correction and stopping iteration, and residuals
accumulated independently in extended precision. Track the first resulting
signal/noise/gradient discrepancy through readout. Keep every structural zero;
do not change tolerances or force either answer. This differentiates changed
factor/pivot behavior from refinement or downstream differences without guessing
that an observed error is harmless rounding. Factor inspection overhead must not
be interpreted as production timing. Both25/26 have only bounded local synthetic
bitwise evidence; the actual affected matrices may expose different behavior.

Next performance experiment, after this closed hypothesis: obtain the previously
requested host_forward/host_backward callback profile for admitted7, reporting
factorization, residual products, component evaluation/Jacobians and scatters
separately. The opt-in helper is experiments/notes/overnight-numerics-profile.py;
no profile has yet been supplied. Choose the largest measured remaining cost
before a new implementation. Continue within this numerical lane, without
combining unconfirmed historical candidates or changing import/JAX wrapper code.

Inherited caveats remain: pristine signal and gradients33/161/180 disagreements,
rand1/rand3 sensitivity disagreement, grid FD54/59/63/136/161/163 unresolved,
aLIGO29/29 prior confirmation, first-order reverse-only custom VJP. This handoff
ends the ordering-reuse hypothesis, not the authorized overnight campaign.

### Candidate27: masked conjugation of private coefficient buffers

Supervisor resumed after the26 handoff and requested a concrete new experiment.
No new feedback/profile/ordering diagnostic arrived.26's authoritative outcome
above is unchanged. Start from restored admitted7 source, not25/26. Pending new
SHA and benchmark jobs. Only production host_pass.py changes; the restoration of
26 is carried in the working diff and failed history remains intact.

Inspection considered parameter expansion, then identified a larger concrete
assembly allocation: after raw_signal.copy() and carrier scaling, np.where(mask,
np.conj(placed),placed) allocates another full complex coefficient buffer for the
conjugation and a full selected result. Reverse repeats the same operation on
signal_values_bar, a freshly allocated private zero buffer populated by the
adjoint loop. Neither unconjugated buffer is needed after this point. The mask is
boolean structural metadata constructed by SparseSystem.mask; it is independent
of numerical coefficient values, including coefficients zero at this point.

Hypothesis: remove those two full-buffer temporaries in each direction to reduce
assembly memory traffic and allocation variance. Forward/reverse historical
admitted-grid phases are181.163/85.357ms; aLIGO32.890/14.384ms. The share spent on
these copies is unprofiled, so measured total speedup is NOT claimed. This targets
sideband assembly ownership, not the closed component-Jacobian contraction or
column-ordering mechanisms. It includes no changes from those unconfirmed trials.

Implementation: forward performs np.conjugate(placed,out=placed,where=mask), then
uses placed as final. raw_signal remains independently allocated and unchanged for
the pullback. Reverse aliases placed_bar to the private signal_values_bar and
applies the same masked conjugation before the existing raw_bar copy, carrier
scaling and scatter. All cotangent entries and conjugation conventions remain;
no sparse entry is removed and no runtime zero is treated as structural zero.
The original private signal_values_bar has no subsequent unconjugated use. This
mutation does not touch callback inputs, saved forward outputs or raw_signal.
Numerical factorization, ordering, residual products, all refinement iterations
and stopping criteria are exactly the admitted parent. No JAX/import changes.

Retained check: experiments/notes/overnight-numerics-conjugation-check.py extracts
and executes the actual _assemble function and actual sideband pullback statements
from parent/current source, with small synthetic component outputs and a stubbed
carrier solve (no claim of optical-solver validation).150 cases cover1/2/5 carrier
rows and1/3/13 sweep counts where broadcasting is supported, scalar/all/no/mixed
and broadcast masks, complex values, signed zeros, NaNs/infinities, repeated
carrier indices, and reused/per-row noise. Every returned assembly array and
placed/raw/carrier cotangent matches bitwise. Saved raw_signal is unchanged and
shares no memory with final signal values. Synthetic17x1024 complex coefficient
forward step peak traced allocations: parent845608bytes,candidate288152bytes,
reduction557456bytes, consistent with eliminating two278528-byte buffers. This is
an allocation inspection, not an official or independent timing benchmark.
No dependencies, fixtures, physical parameters or tolerance settings changed.

Request both unchanged official benchmarks on the same new SHA, saved full output
and gradient comparisons against admitted7 and initial seed, all14 existing
parameter/frequency/modulation generalization cases, and independent source review.
In particular verify that25/26's newly nonzero seed sensitivity errors disappear
with their source removal. Do not claim they were fixed or explained by this new
change. Inspect any new discrepancies before further trials. For a promising
result request matched repeated fresh-process parent/candidate complete runs,
separate grid/aLIGO samples/median/range, phase tradeoffs, RSS and overlap records.
If copy reduction has no stable end-to-end benefit, retire this narrow variant.
Inherited pristine disagreement, unresolved grid FD coordinates and first-order
reverse-only compatibility caveats remain as documented above.

### Candidate27 feedback and retirement

Exact SHA72940d62fc545d0fefa7d9b3401a1c6ebbdd10d1, dual-official job
 dec34554b31c4da1b655fafdd8a57f8b (grid-1/2/3 and aligo-1/2/3).
All six official runs pass; confirmed_improvement=false, source_review=null.
Large fresh seconds [.8291872125118971,.8023864179849625,.7948901876807213],
median .8023864179849625, range [.7948901876807213,.8291872125118971].
aLIGO [.5432056952267885,.543520376086235,.5454824231564999],
median .543520376086235, range [.5432056952267885,.5454824231564999].
Admitted7 medians .8015776835381985/.5485551562160254: large +.809ms,
aLIGO -5.035ms, with overlapping large ranges and different cohorts. No stable
large improvement. These are separate setup results, not an averaged score.

Median phases in ms (27 versus historical admitted7): grid forward182.700 versus
181.163 (+1.537), reverse84.768 versus85.357 (-.589), build69.423 versus73.994
(-4.571), imports267.174 versus265.601 (+1.573). aLIGO forward32.434 versus32.890
(-.456), reverse14.661 versus14.384 (+.277), build38.480 versus37.963 (+.517),
imports263.859 versus263.509 (+.350). Not paired timing evidence. Peak sampled
RSS grid560984064, aLIGO295440384, generalization1124888576 bytes. No reported
infrastructure or memory-budget failure; external contention remains unexcluded.

Inspected supplied per-array/gradient comparison records and archive hashes;
raw remote arrays were not reopened locally. All official output comparison
records remain those of26. All14 generalization cases pass initial-seed bounds,
with sensitivity log difference now0.0 in every case;25/26's four new nonzero
log differences disappeared after their ordering implementation was removed.
This does not explain the ordering discrepancy or attribute its removal to27's
conjugation change. Pristine comparisons still fail: grid131 signal,3 gradient,
1 loss entries; aLIGO1 loss; rand1/rand3 sensitivity log errors approximately
.0002036099068405406/.000058100919558157216. All inherited numerical caveats
remain, including grid finite differences and first-order-only transform support.
Decision: retire the unconfirmed masked-copy variant. It remains preserved in27's
commit. The next experiment explicitly restores the two sites to admitted7.

### Candidate28: native sparse products, numerical/performance experiment

Pending supervisor SHA and dual-official job. Production source is admitted7
plus only the native-product implementation in host_pass.py. No column-ordering,
component-Jacobian or27 masked-conjugation change is combined. This changes the
sparse-product execution backend, distinct from the closed9/10 NumPy temporary
reuse experiments. No callback profile was supplied; the proportion of total
runtime attributable to products remains unmeasured. No speedup is claimed.

Concrete operation removed: _Products.apply currently gathers x at every
structural entry, materializes the complex nnz-by-RHS product, and for normal
products gathers/reorders that array before reduceat. Every refinement correction
calls it. The new path uses SciPy's native csr_matvecs loop with static CSR layouts
for A and A^T. Coordinates include all structural entries, including currently
zero coefficients; numerical values are reordered afresh for every call. H uses
conjugated current coefficients. It allocates the full result and any necessary
contiguous operands, but no nnz-by-RHS intermediate. Same function supports
vectors and arbitrary RHS counts. No sparse factors or numerical matrices persist
across evaluations. Factorization and _solve's three-step refinement and1e-14
stopping criterion are unchanged. Native arithmetic remains complex128.

The extension loader follows the existing SuperLU loader's approach: first use
an already-loaded scipy.sparse._sparsetools, otherwise load that extension file
from the installed SciPy package. It runs during the first host callback; its
startup and CSR-index construction must be included in complete official timing.
If the extension cannot load, retain the original NumPy path. This is a package
availability fallback, independent of optical inputs. Native kernel errors are
not swallowed. No new dependencies or launch settings. Public SciPy source in
the existing local installation was inspected for csr_matvecs' argument order.

Numerical distinction: native accumulation has a different summation order from
NumPy reduceat. This is NOT a claim of bitwise equivalence or a harmless-rounding
assertion. Saved local check and full report:
 experiments/notes/overnight-numerics-native-products-check.py
 experiments/notes/overnight-numerics-native-products-result.json
The check AST-extracts actual production kernels and compares against admitted7;
it does not import JAX or execute an optical benchmark.360 sparse products and
360 refined solves cover random complex matrices, changing coefficients including
new zeros, N/T/H, vector and1/2/5 RHS, Fortran inputs, sizes5/13/37, scaling1e-8 to
1e8 and Hilbert6/9/12.340 products and336 solutions differ bitwise;3 solve pairs
change correction count. Ordinary/scaled maximum relative solution differences
are3.8588283487298117e-16/8.193077684207589e-16. All solutions remain finite and
inputs unchanged.360 forced NumPy fallback products match parent bitwise.
Additional empty-pattern/empty-row/nonfinite cases agree including NaN locations.
The cold direct extension loader and already-imported-SciPy path both worked.

A significant ill-conditioned difference is retained: max native/parent solution
relative difference .07038003065674561 for a12x12 Hilbert N solve with2 RHS.
Local longdouble has only52 mantissa bits: its residual results do NOT provide
extended-precision evidence. The reported ~1e-16 backward errors and zero maximum
native/dense product difference must be interpreted as ordinary double checks.
To investigate independently, the check performs70-digit Decimal pivoted Gaussian
elimination on the exact binary64 matrix and real/imaginary RHS components for
all36 unperturbed Hilbert solves. Every reference rounded to binary64 is unchanged
at90 digits. Native is more accurate in20 cases and less accurate in16. Maximum
relative forward errors: parent .0727785086307816; native .05546192276396677.
For the largest parent/native disagreement specifically: parent .0727785086307816,
native .009643985644328048 against the Decimal reference. All per-case errors are
retained in the JSON. Thus changing summation can improve OR degrade accuracy;
the lower worst error in this small sample does not certify arbitrary setups.
Do not hide this finding behind small residuals or public benchmark passing.

Allocation-only synthetic inspection: size127, degree9,3 RHS, one normal product;
peak traced allocations parent172176 bytes, native24768 bytes (-147408). This
excludes already-built static layouts/imports, so is only a per-product allocation
measurement. No local timing benchmark was run. First-use layouts occupy extra
O(nnz+size) index storage for normal and transposed products. Count its build,
first-forward, memory and fallback costs in official evidence.

Evaluation request: both unchanged full official workloads on the same new SHA,
all saved physical arrays and gradients versus admitted7 and initial seed, all14
optical parameter/frequency/modulation cases, and independent source review.
Any newly introduced optical discrepancies require investigation of the exact
assembled coefficients/RHS, high-precision residual/solution diagnostics and
full sensitivity/gradient effects; do not automatically classify them as rounding.
Given the local mixed accuracy, numerical review is mandatory even if official
checks pass. No tolerance relaxation or refinement reduction is proposed. Retain
admitted7 as shared best unless numerical review and matched repeated fresh-process
complete timings support this candidate. If promising, request parent/candidate
paired runs with separate grid/aLIGO samples, medians, ranges, phase deltas, RSS
and overlap records. If native accumulation causes new unresolved optical errors
or no stable gain, close this backend hypothesis rather than multiply variants.

### Candidate28 feedback: faster forward phase, new strict failures; not admitted

Exact SHA a1e10d9a0cf9a8aa022e597abb0c69f69593121d; both official workloads under
job8f48011306b24a4f8a784b3325c11ee8 (grid-1/2/3, aligo-1/2/3). All6 official
runs pass, confirmed_improvement=false, promotion_ready=false, source_review=null.
Full supplied per-array comparison records and phase samples retained in
experiments/notes/overnight-numerics-native-feedback.json. This is an inspection
of evaluator records/hashes, not a claim that remote NPZ arrays were reopened.

Grid fresh seconds [.8082562908530235,.7692052610218525,.7723937276750803], median
.7723937276750803, range [.7692052610218525,.8082562908530235]. aLIGO fresh seconds
[.5430818609893322,.5420670192688704,.5386770088225603], median .5420670192688704,
range [.5386770088225603,.5430818609893322]. Versus historical admitted7 medians,
large -29.184ms (about3.64%), aLIGO -6.488ms (about1.18%). Large ranges overlap;
there is no matched parent/candidate cohort, so this is not a confirmed stable
gain. First large import293.696ms versus266.244/268.350ms in subsequent fresh
processes remains included, not discarded as an outlier. No combined score.

Median phases ms: grid forward151.080, reverse86.050, build71.120, imports268.350;
aLIGO forward27.510, reverse14.319, build38.115, imports265.292. Versus historical
admitted7 these are grid -30.083,+.693,-2.874,+2.749; aLIGO -5.380,-.065,+.152,
+1.783ms respectively. Forward is consistently150.777--153.618ms across28's
three runs, making native products a credible execution mechanism to investigate,
but numerical correctness takes precedence. Peak sampled RSS grid624418816,
aLIGO296755200, generalization947744768 bytes. No infrastructure failure or memory
limit exceedance. Other-host contention is not excluded.

New numerical failures versus initial seed: both official setups fail the scalar
loss comparison (one entry each) while carrier, signal, noise, powers, sensitivity
and gradients pass their elementwise bounds. Grid log sensitivity difference
6.577778322025551e-10; gradient maxabs2.4814275093376637e-05, relative L2
4.533077315746321e-10. aLIGO log sensitivity1.2150280781497713e-12; gradient
maxabs3.73624061467126e-07, relative L21.0167147507959856e-11. These increased
versus27; public PASS does not erase them. All three fresh output hashes match
within each setup: grid b3e3b0bf0cf4c67f99251753cad956b39aa949cdd39a15e06099e0ddf1be7f76,
aLIGO ee3e6c4fe784f32b46d2f50444a5a474fe945a71e041b4263404aa5fb6b785a6.

Generalization initial-seed failures: dev loss1 and voyager signal363. The other
12 cases pass bounds, but all14 sensitivity differences are now nonzero. Largest
log sensitivity difference is rand3 3.5302113232660304e-08. rand1
1.1826273293991107e-10; rand2 2.9174884730309714e-11. Voyager log sensitivity is
3.055333763768431e-13 despite its363 signal failures: sensitivity alone would hide
the new output discrepancy. All14 gradients pass initial-seed bounds. The
candidate-self artifacts section is NOT independent evidence; this decision uses
the initial_seed and pristine comparisons explicitly.

Pristine differences persist: grid131 signal/3 gradient/1 loss and aLIGO1 loss;
Voyager398 signal failures versus395 previously. Rand1/rand3 pristine log errors
.00020360991047141397/.00005811041570424891 with previous failure counts retained.
The complete per-case records preserve other unchanged and changed discrepancies.
No new numerical differences are dismissed as harmless or resolved by local
Hilbert examples. Existing grid FD54/59/63/136/161/163, gradient33/161/180,
rand1/rand3 dense-reference disagreements, aLIGO29/29 prior FD confirmation and
first-order reverse-only support remain distinct caveats.

Decision: do not promote28 or stack further tuning onto it. Restore production
host_pass.py to admitted7, leaving28 and its tests/results in committed history.
All production files now match admitted7. No new official evaluation requested
for the restoration. This closes the native backend optimization hypothesis
pending actual-matrix diagnostics; it does not end the overnight campaign.

### Concrete diagnostic handoff for28's numerical failures

Added experiments/notes/overnight-numerics-product-diagnostics.py. This opt-in
context runs no workload by itself and writes no files. The supervisor can load
it in a separate synchronized diagnostic driver on exact candidate28, supplying
exact admitted7 host_pass.py source as reference_source. It wraps _Products.apply
and _solve, compares the actual candidate against the parent's product and
refinement at identical current coefficients/RHS and the SAME SuperLU factor,
and returns original candidate results unchanged. It records every call count,
changed refinement counts, and the largest product/solution discrepancies
(default8 of each per context) with complete structural coordinates, numerical
values, RHS, both outputs and every initial/correction factor-solve RHS/result.
Products outside _solve are included, so noise-source products are not omitted.
The supervisor must retain a fresh context for each optical case and serialize
its arrays separately. It adds substantial computation/copying; NEVER treat an
instrumented run as an official timing or promotion result. It requires no
fixture detection, numerical pruning or tolerance change.

Local synthetic inspection of the helper used actual28 kernels, a9x9 random
complex matrix and N/T/H with2 RHS. All3 instrumented refined outputs remained
bitwise identical to uninstrumented28;4 product calls and3 solves were captured,
including an external product. Both record lists respected max_records=2;
original methods were restored after normal exit and a deliberately raised
exception. This checks the diagnostic plumbing, not the optical disagreements.

Coordinator request: run the diagnostic on dev, official101-frequency aLIGO,
voyager and rand3, separately from timing. Also return exact candidate/seed scalar
loss values and per-entry signal/gradient difference maxima/indices from the
existing saved arrays (not only pass counts). Use captured identical coefficients
and RHS to compute genuinely extended-precision or arbitrary-precision residuals
and forward-error estimates for BOTH solutions, documenting actual precision.
Trace the first changed correction/stopping decision through the differing signal,
noise, loss and gradient. If upstream assembly differs because carrier solutions
changed, compare carrier first; do not conflate identical-RHS probe results with
whole-simulation equivalence. Local longdouble52 cannot provide that evidence.

Only after resolving the new loss and Voyager failures should the supervisor
request independent source review and repeated matched fresh-process dual-official
runs of28 versus admitted7. No such diagnostic, source review or paired cohort
has been supplied yet. A source-portable way of preserving NumPy's reduction
semantics would need proof/testing; do not guess its internal pairwise summation
order or selectively fall back on known fixtures. If the numerical investigation
does not justify28, retain admitted7 and use the already-requested callback
profile to select a different conservative execution mechanism.

### Candidate29: consume private parameter-row cotangents

Supervisor resumed after28's stop handoff and requested one concrete next
experiment. No actual-matrix diagnostics, independent review or paired cohort for
28 were supplied. Its loss/Voyager failures remain open and its native backend
is excluded. Source starts from restored admitted7. Pending candidate SHA and
both official benchmark job IDs. All preserved28 feedback and diagnostic files
remain; the working diff includes its production restoration, not a history reset.

Selected a separate conservative allocation mechanism: _expand_backward gathers
sweep cotangents, copies the entire tiled row cotangent, clears the overwritten
sweep destinations, then sums over replicas. Both production callers relinquish
their input immediately. The signal call receives signal_rows_bar freshly created
by SystemPlan.backward with np.zeros(rows.shape), after adding noise_rows_bar;
no operation uses its old contents after this call. The carrier call receives
the new temporary carrier_rows_bar + component_bar. Neither input aliases saved
forward state, callback inputs or public outputs. The gather is advanced indexing
and already allocates values_bar independently before clearing destinations.
Thus the full C-order row-cotangent copies are redundant at these two callers.

Implementation adds a keyword-only consume=False to the private helper and sets
consume=True at those two call sites. Writable C-contiguous inputs can be cleared
in place. The default still copies, and Fortran, strided or read-only inputs retain
the original C-order copy even when consume=True. All index construction, gather,
clearing and sum operations remain, in the same order. This is a storage-ownership
change, not parameter pruning: every sweep cotangent including zero-valued
physical parameters is gathered as before. Duplicate and negative indices retain
the existing helper's behavior. No sparse product, factor, refinement, component
Jacobian, import or JAX wrapper changes are included.

Hypothesis: eliminate one full expanded parameter-row copy for each of the two
expansion pullbacks, reducing allocation/memory traffic in reverse execution.
The admitted large/aLIGO reverse medians were85.357/14.384ms; the fraction spent
on these copies remains unprofiled, so no expected millisecond or total speedup
is claimed. This targets parameter-expansion ownership, rather than27's sideband
coefficient conjugation or28's changed sparse-product arithmetic.

Retained check experiments/notes/overnight-numerics-expansion-ownership-check.py
AST-extracts actual parent/current _expand_backward and verifies both production
call sites explicitly request consumption.960 synthetic cases cover1/2/5 base
rows,0/1/3/17 replica counts,9/31 parameter columns, empty/single/multiple/full,
repeated and negative indices, random complex/signed-zero/NaN/infinite values,
C/F/strided/read-only storage. Both returned arrays match parent bitwise for
consume=False and consume=True; default inputs remain unchanged, eligible
consumed inputs change exactly the cleared destinations, and gathered values_bar
never shares storage with the consumed input. Input layouts requiring the copy
are explicitly exercised. No optical benchmark or timings were run locally.

Initial unguarded ownership implementation failed a synthetic Fortran-layout
case (base_rows1,count17,columns9,empty indices) because ndarray.copy() defaults
to C order and the changed reduction layout altered addition behavior. This
failure motivated the C-contiguity guard; it is not dismissed as rounding. The
repaired960-case check passes bitwise, including that case. Read-only copying was
also retained for compatibility. Production-owned inputs are C-contiguous and
writable by their allocation sites; the guards preserve arbitrary helper usage.

One small allocation inspection,37 replicas x1024 parameters with7 sweep entries:
parent peak632648 bytes, consumed candidate26400 bytes, reduction606248 bytes.
The removed full complex row copy is606208 bytes. The caller's initial allocation
is outside this per-kernel probe and must remain inside complete official timing.
There is no answer cache, persisted numerical state or new numerical fallback.

Request both unchanged official workloads on the same new SHA; inspect all
physical outputs/gradients and all14 frequency/parameter/modulation cases against
admitted7 and initial seed, keeping pristine disagreement separate. Specifically
verify that28's new loss/Voyager mismatches disappear after its removal, without
claiming that29 itself explained or repaired native accumulation. Independent
source review must verify buffer ownership and operation-order preservation.
If promising, obtain matched repeated fresh-process parent/candidate full runs,
separate grid/aLIGO samples, medians, ranges, phase/RSS/overlap evidence. Retire
this allocation variant if gains are below noise; do not combine it with other
unconfirmed trials. Existing pristine disagreements, six unresolved grid FD
coordinates and first-order reverse-only transform limits remain unchanged.


### Candidate29 feedback and retirement (2026-11-22)

Exact candidate45cd39d4e2d00d34ec9fb233cc7aba67f2fc4e86;
request45844d011e5a4664b5b508ab1d8de0d3, grid-1/2/3 and aligo-1/2/3.
All six unchanged official runs passed. Confirmed improvement=false; independent
source review=null. The runner's promotion_ready flag is true, but the selection
receipt rejects promotion for missing review, insufficient gain and overlapping
large ranges. No infrastructure failure or memory-budget exceedance was reported.

Complete fresh-process grid samples in seconds:
[0.8354148138314486, 0.7940657176077366, 0.8060999065637589];
median0.8060999065637589, range0.7940657176077366–0.8354148138314486.
Official aLIGO samples separately:
[0.5460673924535513, 0.5478089991956949, 0.5594915952533484];
median0.5478089991956949, range0.5460673924535513–0.5594915952533484.
Relative ranges5.130% and2.451%, respectively. These are support measurements,
not an organizer ranking score or a paired quiet cohort; contention not excluded.
Against admitted7's earlier medians, grid is4.522223ms slower and aLIGO0.746157ms
faster. Neither difference establishes a stable improvement.

Grid median forward184.913263ms, reverse84.186221ms, build73.242808ms,
imports266.931552ms. Corresponding deltas from admitted7 are +3.750176,
-1.171203, -0.751272 and +1.330938ms (unpaired descriptive differences).
aLIGO median forward33.147972ms, reverse14.778912ms, build40.017767ms,
imports265.836217ms; deltas +0.257822, +0.394760, +2.055222 and +2.327409ms.
Sampled peak RSS maxima: grid581050368 bytes, aLIGO294432768 bytes;
generalization865243136 bytes. No speedup is established by the synthetic
606248-byte allocation reduction or the small unpaired reverse delta.

Inspected every saved-array comparison record supplied by the evaluator, not
remote NPZ payloads unavailable in this worktree. All six official archive hashes
and complete initial-seed/pristine comparison records equal candidate27's
corresponding setup records. Both official initial-seed checks pass, with zero
log-sensitivity error. Gradient differences are not bitwise zero versus seed:
grid maxabs5.686350050382316e-6 / relativeL2 8.181451454702114e-11;
aLIGO maxabs3.637978807091713e-11 / relativeL2 1.294943745154708e-15.
All14 generalization cases pass against initial seed, with zero log-sensitivity
error; every initial-seed and pristine per-case record equals27's record exactly.
The candidate-self archive check is not independent evidence. Pristine mismatches
remain: grid131 signal entries,3 gradients and scalar loss; official aLIGO loss;
random-topology sensitivity/gradient disagreements and other signal entries.
The six unresolved grid finite-difference coordinates54,59,63,136,161,163 remain;
prior additional aLIGO29/29 checks and first-order-only transform limits remain.

The new initial-seed loss and Voyager signal failures from28 disappeared after
removing its native sparse products. This is evidence of restoration, not an
explanation or certification of28's changed accumulation. Its actual-matrix
precision investigation remains pending and its implementation remains excluded.

Decision: retire29. Copy/allocation variants24,27 and29 reduced local allocations
without a repeat-supported complete-run improvement; do not continue blind
in-place-buffer variants or combine them. Restored only owned host_pass.py to
admitted7, leaving every failed revision in history. All production files now
match ee4fea28c04d482566be16e916b609d7c6a99e5e exactly. Historical synthetic
helpers remain tied to their recorded revisions; the29 ownership helper is not
a test of the restored parent. No new simulator candidate is submitted.

Concrete next measurement for the coordinator: use the existing supervisor-only
collect_host_profiles context in overnight-numerics-profile.py on admitted7,
in a separate diagnostic execution under the same CPU/thread policy. Return
first-forward and first-backward call counts and self/cumulative times for both
unchanged full workloads, especially _factor/gstrf, SuperLU.solve, _Products.apply,
SystemPlan.values/backward, function_jacobian and _expand_backward. Keep profiler
overhead and subsequent callbacks separate from official timings. No such profile
has been supplied despite earlier requests. Select a genuinely distinct mechanism
from those results before another optimization submission. The second independent
pending action is the recorded28 product-diagnostics capture on its exact failing
matrices. Both helpers are already implemented; neither runs a workload itself.
This stops the unproductive allocation hypothesis, not the authorized campaign.

### Candidate30: stage the existing Dual formulas as static NumPy programs

Supervisor resumed after29 retirement and explicitly requested a concrete next
experiment. No callback profile or28 actual-matrix diagnostics accompanied the
request. Source starts from restored admitted7;29 ownership changes and28 native
products remain excluded. Candidate SHA and both official job IDs pending.
This submission includes29's documented source restoration, preserving its commit.

Distinct mechanism: the parent function_jacobian calls the original component
function once for every differentiated slot, using Dual(v,a,b). Each pass repeats
primal formulas and many identical derivative subexpressions. Candidate18 shared
primal work through a runtime direction dictionary, without a confirmed complete
run gain. Candidate30 instead stages the unchanged existing Dual implementation
with symbolic column objects, interns identical ordered operation nodes, and emits
a straight-line Python function calling the same NumPy ufuncs and Python arithmetic
operators. There is no runtime Dual graph traversal or direction dictionary.
No parent Dual rule or component formula is edited. No new optical formulas,
hand-coded derivatives, coefficient pruning or physical variable tuning appear.

New differometor/host_program.py builds a graph from HOST_FUNCTIONS and the
supplied slot layout, using symbolic inputs rather than numerical probes. Keys
include the callable, slot tuple, number of input columns and the Dual/_Slots
types. Function/slot structure is generic across setups, frequencies and shapes;
no fixture identity or known workload dimensions are inspected. Cache bound128
stores only generated code, scalar constants from component/Dual source and
operation callables. It stores no physical input arrays, numerical component
values, matrices, factors or outputs. It is process-local and writes nothing to
disk. Every numerical call executes the program on fresh supplied columns.
All initial graph construction and Python compilation happen in the first
function_jacobian call and therefore remain inside complete first-run accounting.
No JAX/XLA settings, persistent compilation cache or three-stage boundary changes.

Interning requires the same operation and ordered operand identities; operands
are never commuted, reassociated or algebraically simplified. Scalar types and
signed zeros are retained in constant keys. All zero derivative multiplication,
division and nonfinite propagation remain. Expression arithmetic defers to Dual
reflected operators just as an ndarray does. NumPy ufunc identity is preserved;
operator calls remain operator calls. The generated source contains fixed
identifiers and integer indices only, while constants/functions are bound directly
in its namespace. Physical input text is never compiled. The existing complex128
Jacobian buffers retain their shape and layout; each independent destination is
written as its value becomes available. Temporaries are released after their last
arithmetic use. All structural derivative slots remain, including repeated and
negative slots, and zero-valued physical parameters are differentiated normally.

Numerical validation: experiments/notes/overnight-numerics-program-check.py loads
actual source kernels through AST without unavailable local JAX, reusing the
preserved comprehensive Dual checker.4104 component/Jacobian/contraction checks,
8 SystemPlan pullbacks,133 extreme/nonfinite cases, and912 extra checks pass.
Extra cases exercise empty batches, changing input-column counts, repeated and
negative seed slots, strided inputs, fresh changed numerical values after cache
hits, and with_outputs=False. Finite outputs match parent bitwise; nonfinite
outputs match elementwise including NaN positions. Independent central finite
differences in both complex directions at two step sizes pass1596 checks,
maximum scaled error1.7286649972079704e-9 (existing bound2e-7). These are local
synthetic checks, not either optical benchmark or a universal physics certificate.

Established operation redundancy with actual runtime ufunc counting on a
seven-slot surface Jacobian: parent sqrt27/cos30/exp21/sin22/arcsin14 (114 total),
candidate sqrt4/cos3/exp3/sin3/arcsin2 (15 total). This includes derivative slopes.
The previous shim-level counter reports zero for generated calls because it no
longer observes runtime execution; that metric is explicitly discarded in the
new checker. Test-only wrappers count generated NumPy callables directly and
restore them afterwards; production code contains no counters or test switches.
No elapsed-time benchmark was run locally and these counts do not establish speed.

First implementation retained every graph temporary until returning, with a
synthetic warm allocation peak2292536 bytes versus parent531448 bytes. The final
implementation releases intermediates after their last use, reducing the warm
peak to543304 bytes in that same17x23-row surface probe. Cold peak2538365 bytes
includes graph construction and code compilation and is larger than the parent;
this is an explicit first-run cost/risk, not excluded from the proposed evaluation.
The measured phase target is admitted7's85.357ms large reverse execution, with
14.384ms aLIGO reverse as the transfer constraint. The fraction attributable to
this interpreter remains unprofiled; net first-run gain is unknown. Compilation
cost may outweigh saved arithmetic, particularly for small setups.

Request the supervisor's unchanged full101-frequency grid193-variable and
101-frequency aLIGO29-variable evaluations on the same new SHA. Compare every
saved output/gradient with admitted7 and initial seed, keeping pristine failures
separate, plus all14 varied frequency/parameter/modulation cases. Review the new
program generator independently for exact operation semantics, fresh input use,
cache contents and included compilation costs. If it passes and appears promising,
request paired repeated fresh-process candidate/parent runs under matching policy,
including each sample, separate medians/ranges, phase changes, RSS and overlap.
Do not promote based on operation counts, synthetic agreement, a warm-only gain,
a single run or candidate-self comparisons. No combination with prior unconfirmed
trials. If first-run staging dominates, reject this implementation rather than
moving compilation outside the timer. Existing pristine disagreements,28's open
new failures, six grid FD questions and whole-pass JVP/Hessian limitation remain.


### Candidate30 feedback; candidate31 direct graph execution

Evaluated30 SHA c4dc5ae7d4536c754d186ba31e546659f2ef7cbd;
request b41a623cd23946a3a39c563e03ba9469, grid-1/2/3 and aligo-1/2/3.
All six official runs passed, but confirmed_improvement=false, no source review,
and selection rejected unstable timing, inadequate large gain, overlapping ranges
and aLIGO regression. The runner's promotion_ready=true is not promotion.

Large complete fresh-process samples (seconds):
[0.8904174827039242, 0.7973683625459671, 0.802862286567688];
median0.802862286567688, range0.7973683625459671–0.8904174827039242,
relative range11.590%. Official aLIGO separately:
[0.5600046403706074, 0.5712345577776432, 0.6612497363239527];
median0.5712345577776432, range0.5600046403706074–0.6612497363239527,
relative range17.724%. All samples retained. The first grid sample had elevated
imports, gradient lowering/compilation and execution; aLIGO3 imports373.495ms
were elevated. These fluctuations are not evidence that derivative staging caused
all total-time changes. Host contention is not excluded; no paired cohort supplied.
Compared to admitted7's earlier medians: large +1.284603ms, aLIGO +22.679402ms.

Large median forward182.987805ms/reverse87.573757ms/build73.763885ms/
imports265.433796ms; deltas versus admitted7: +1.824718/+2.216333/-0.230195/
-0.166818ms. aLIGO medians32.826757/22.846971/38.303858/282.689825ms;
deltas -0.063393/+8.462819/+0.341313/+19.181017ms. Each aLIGO reverse sample
was22.564–23.073ms, compared with admitted7's earlier14.384ms median. The repeat
reverse increase motivates investigating first-use graph/source construction;
that attribution is a hypothesis, since no callback profile isolates the cost.
Sampled peak RSS maxima: large594616320, aLIGO293654528, generalization1037729792
bytes. No infrastructure failure or budget exceedance reported.

Inspected every returned official and14-case comparison record. All official
archive hashes and initial-seed/pristine comparison records exactly match29.
All14 initial-seed cases pass, zero log-sensitivity error; all14 seed and pristine
per-case records equal29. Gradient differences versus seed remain nonzero within
tolerance (large maxabs5.686350050382316e-6, aLIGO3.637978807091713e-11).
Pristine signal/gradient/loss and random-topology sensitivity disagreements remain
unchanged. Remote NPZ payloads were not available locally; comparison records and
archive hashes are the inspected evidence. Candidate-self comparisons are not an
independent certificate. Six unresolved grid FD coordinates, prior aLIGO29/29
checks, first-order-only transform support and28's unresolved native-product
failures remain separate.30 is preserved in history and is not an admitted gain.

Candidate31 is a focused simplification of30, not a merge with another trial.
Retain its symbolic tracing, ordered operation interning and last-use lifetime
plan, but remove generated Python source, compile and exec entirely. _Graph.program
now returns a callable _Program with static node/destination/release tuples.
Each invocation allocates its own local values list, reads fresh supplied columns,
calls the same operation functions on the same ordered operands, writes each
Jacobian destination, and clears local references after their last use. No input
array or result is stored in the program or cache. No numerical arithmetic,
reductions, scatter order, component formulas or physical outputs are changed.
A Python loop and argument gathering replace the generated straight-line function;
this introduces runtime overhead but avoids first-call Python compilation cost.
All symbolic graph construction remains inside the first numerical call and timer.
The process-local128-entry structural cache has the same keys and bounded scope;
no persistent cache or timing-policy changes. There is no shape-size threshold or
fixture dispatch, and no zero derivative pruning.

Re-ran overnight-numerics-program-check.py on31:4104 component/Jacobian/contraction,
8 SystemPlan pullback,133 extreme/nonfinite,912 extra shape/layout/slot checks and
1596 independent finite-difference directions pass. Finite values match admitted7
bitwise; nonfinite values match elementwise. Maximum scaled finite-difference
error1.7286649972079704e-9 under the unchanged2e-7 synthetic bound. Actual surface
transcendental counts remain parent114 versus candidate15. The test-only counter
now wraps operation-node callables and restores the node tuple; it does not alter
production modules, NumPy or benchmark validation.

Same small17x23-row surface allocation probe: parent531448 bytes;31 first-call
peak616578 bytes, later-call547288 bytes.30's corresponding cold/warm figures
were2538365/543304 bytes. Reduced cold allocation confirms removal of construction
work, not elapsed-time gain. No benchmark or local timing was run.31 has no assigned
SHA/job IDs yet. Independent review and both unchanged complete official workloads
on one exact SHA are required, with every saved output/gradient and all14 cases
compared to admitted7/seed and pristine separately. If promising, require matched
repeated fresh-process parent/candidate samples, medians/ranges, phases, RSS and
contention evidence. If direct execution still loses, retire this staging path;
do not hide compilation outside the timer or promote a warm-only benefit.


## Candidate31 feedback — hold exact source for paired evidence

Candidate31 SHA316df3dd0e65d2d6edac263e24cf14ea9b80972b, dual request
 de0216be0f48433bb3591ecb6542d935 (grid-1/2/3 and aligo-1/2/3).
All six unchanged official runs passed. confirmed_improvement=false; independent
source review is absent. Selection withheld for missing review and overlapping
large first-run ranges. The runner's promotion_ready field is not an admission.

Large complete fresh-process seconds:
[0.8311645332723856, 0.7864642404019833, 0.7932619396597147];
median0.7932619396597147, range0.7864642404019833–0.8311645332723856,
relative range5.635%. Official aLIGO seconds:
[0.5451211351901293, 0.5425091609358788, 0.546032851561904];
median0.5451211351901293, range0.5425091609358788–0.546032851561904,
relative range0.646%. These are separate diagnostics, not a combined score or
an organizer ranking claim. All samples retained, including grid-1's294.213ms
imports. External contention is not excluded; no matched parent cohort supplied.

Compared with admitted7's earlier medians, large is8.315744ms lower (about1.04%)
and aLIGO3.434021ms lower (about0.63%). Large ranges overlap. These unpaired
observations are promising but do not establish a gain. Large median phases:
forward182.861671ms, reverse79.023715ms, build72.593059ms, imports265.772404ms;
versus admitted7: +1.698584/-6.333709/-1.401021/+0.171790ms respectively.
aLIGO medians32.743787/16.462708/37.812274/263.508771ms;
versus admitted7: -0.146363/+2.078556/-0.150271/-0.000037ms respectively.
Reverse medians decreased versus30 by8.550042ms large and6.384263ms aLIGO;
this is consistent with reducing first-call construction, but is not isolated
causal evidence. Sampled peak RSS maxima: large639741952, aLIGO315441152,
generalization963862528 bytes. No infrastructure failure or memory exceedance.

Inspected all six returned official array-comparison records/hashes and every
initial-seed/pristine record across14 generalization cases. Official archive
hashes and complete strict comparison records equal30. All14 seed comparisons
pass with zero log-sensitivity error; their complete seed and pristine case
records equal30. This does not mean bitwise agreement with the initial seed:
official gradient maxabs differences remain5.686350050382316e-6 large and
3.637978807091713e-11 aLIGO. Remote raw NPZ payloads were not reopened locally.
Pristine grid131 signal/3 gradient/1 loss failures and aLIGO1 loss failure remain;
uifo_rand1/uifo_rand3 sensitivity discrepancies remain about2.04e-4/5.81e-5.
No new discrepancy is reported by these comparisons. The six unresolved grid
finite-difference coordinates54/59/63/136/161/163, earlier aLIGO29/29 checks,
and first-order-only custom VJP limitation remain visible. Candidate28's separate
native-product disagreements remain unresolved and its implementation is retired.

Decision: hold simulator source exactly31; do not introduce candidate32 or stack
another allocation variant. The three-trial search rule is not grounds to call
this an admitted gain. This step seeks missing confirmation of a promising result,
not another unproductive implementation variant. Admitted7 remains the strongest
reviewed parent. No simulator changes or independent benchmarks in this turn.

Supervisor request: independently review exact31, especially ordered operation
interning, typed scalar constants, symbolic Dual dispatch, last-use release,
Jacobian destination writes, bounded structural-only cache and fresh numerical
inputs per invocation. Existing synthetic tests cover zero/repeated derivative
slots, strided/empty inputs and nonfinite cases; these are bounded evidence only.
Review the delta from admitted7, not merely the smaller30-to31 delta.

Request matched repeated complete fresh-process runs of exact31 and exact
 ee4fea28c04d482566be16e916b609d7c6a99e5e under the same fixed CPU/thread/cache
policy, preferably five per setup per revision with paired/interleaved ordering
chosen by the supervisor. Run both unchanged official workloads on each revision,
retain every sample and phase/RSS record, record overlap/contention, and compare
all saved outputs/gradients plus the generalization cases independently against
parent, seed and pristine. Do not exclude the slow first sample. No timing gain or
promotion is claimed until paired evidence and independent review arrive. If the
supervisor cannot supply that evidence, retain admitted7 rather than infer a win
from these medians. Candidate SHA for this request remains316df3dd0e65d2d6edac263e24cf14ea9b80972b;
a note-only commit must not be confused with a new simulator mechanism.

## Candidate32 — direct unary/binary operation dispatch

The supervisor requested a concrete follow-up instead of another identical
hold/repeat handoff. No new evaluator or independent-review evidence arrived;
31 remains provisional and its paired-run request above remains open.32 is a
narrow refinement of31's arithmetic interpreter, not an admission or merge.

Source inspection establishes that31 builds a generator and expanded argument
tuple for every operation, although all19 inspected component graphs contain
only unary and binary operations.32 directly invokes the same callable with
one or two indexed operands; the generic generator path remains for other
arities. Every operation, operand order, value lifetime, Jacobian write and
conjugation is retained. No constant folding, algebraic simplification, numerical
zero pruning, changed reduction/scatter order or solve/refinement change.
First-use structural graph construction remains within the numerical invocation;
all numerical arrays remain local, fresh and uncached. No fixture/shape dispatch.

An alternative inspected in this turn was graph reachability pruning: each
component had only0–4 dead operation nodes for all7 seeds (surface3 out of304).
It was not implemented. Direct call dispatch instead removes interpreter work
on every arithmetic node without dropping any numerical operation or changing
which operations encounter exceptional inputs. Expected phase: reverse execution,
including its first-call interpreter overhead.31's measured reverse medians were
79.023715ms large and16.462708ms aLIGO, versus admitted7's85.357424/14.384152ms;
the small-case overhead makes this conservative Python-overhead refinement worth
one bounded trial. The full-run improvement remains unconfirmed.

Re-ran overnight-numerics-program-check.py:4104 component/Jacobian/contraction,
8 SystemPlan pullbacks,133 extreme/nonfinite,912 extra shapes/layouts/slots,
1596 independent finite-difference directions pass. Finite values bitwise match
admitted7; nonfinite values match elementwise. Maximum scaled finite-difference
error1.7286649972079704e-9 (unchanged2e-7 bound). Surface transcendental work
remains114 parent versus15 candidate. Small17x23-row allocation probe including
first graph construction: parent531448,32 cold611146/warm546224 bytes;
31 previously616578/547288. These are allocations, not elapsed-time claims.

Added overnight-numerics-dispatch-check.py, which loads exact31's interpreter
read-only from Git and compares it with32 on identical graph plans and random
complex128 inputs. All19 component graphs match; additional zero-argument and
three-argument generic call tests match (21 checks). Operation inventory:
1149 total =162 unary +987 binary. An isolated temporary Python profile hook
counts3285 generator-resume events in31 and0 in32 during those calls; this
corresponds to eliminating1149 generator creations. The test restores any prior
profile hook and never changes the production code or benchmark validation.
No independent workload, benchmark, elapsed timing or environment changes run.

Candidate32 SHA and job IDs pending supervisor. Request both unchanged complete
official benchmarks on one exact revision, saved full-output/gradient comparisons
and all14 generalization cases versus31/admitted7/seed and pristine separately,
plus independent review. If promising, matched repeated fresh-process parent and
candidate samples are required; retain every sample, phases, RSS and contention
information. No new numerical discrepancies appeared in the bounded synthetic
checks; all inherited pristine and finite-difference questions remain unresolved.
This is the third arithmetic-program implementation trial (30/31/32). If32 also
has no repeat-supported improvement, retire further interpreter variants and
return to admitted7 for a distinct mechanism; do not stack another tiny dispatch
variant or claim31's overlapping timing ranges were confirmation.

## Candidate32 feedback and retirement of arithmetic-program variants

SHA c8cd23baa84a14017b5d11e0297056b9d9580b6e, request
05ebd8de4c4a4b97bfb38febd3000d5e, grid-1/2/3 and aligo-1/2/3.
All six official runs passed. confirmed_improvement=false, source_review=null;
selection reasons are missing independent review and overlapping large ranges.
No matched parent repeats were returned. No infrastructure/memory failure.

Large complete fresh-process seconds:
[0.8347152415663004, 0.7874145731329918, 0.7879157122224569];
median0.7879157122224569, range0.7874145731329918–0.8347152415663004,
relative range6.003%. Official aLIGO seconds:
[0.5519249495118856, 0.5487538296729326, 0.5459981542080641];
median0.5487538296729326, range0.5459981542080641–0.5519249495118856,
relative range1.080%. Keep every sample, including grid-1 imports295.975ms.
External contention remains unexcluded; these are unpaired support observations.
Relative to admitted7's earlier medians, large is13.661971ms lower and aLIGO
0.198673ms higher. The large maximum exceeds admitted7's minimum794.425ms.
No combined score or confirmed gain is inferred.

Large median phases ms: imports264.279258, build73.976772, forward178.928969,
reverse79.211289. Relative to admitted7: -1.321356/-0.017308/-2.234118/
-6.146135ms respectively. aLIGO medians264.634872/37.868606/34.012673/
16.313627; deltas +1.126064/-0.093939/+1.122523/+1.929475ms.
Versus31, the target reverse median changed +0.187574ms large and -0.149081ms
 aLIGO: the generator reduction did not produce a clear target-phase win.
Sampled maximum RSS: large598085632, aLIGO315387904,
generalization1067003904 bytes. Sampled RSS is not a strict peak bound.

Read and compared every returned official hash/strict record and all14 seed and
pristine generalization case records against31: all are unchanged. Official
archives match31; all14 seed cases pass with zero log-sensitivity error. This is
not bitwise agreement with the seed: official gradient maxabs differences remain
5.686350050382316e-6 large and3.637978807091713e-11 aLIGO. Raw remote NPZs were
not reopened locally. Inherited pristine grid signal131/gradient3/loss1 and
 aLIGO loss1 failures remain; random-topology sensitivity differences remain
about2.04e-4 and5.81e-5. The unresolved six grid finite-difference coordinates,
prior aLIGO29/29 checks and lack of JVP/Hessian support remain separate findings.
The earlier native-product28 failures remain unresolved and are not reintroduced.

Decision follows the recorded third-trial rule: retire further arithmetic-program
variants30/31/32 without claiming they are numerically invalid or disproven speedups.
Their dual-official passes and provisional timing improvements remain preserved
in their exact commits, notes and receipts; none has paired confirmation/review.
Return the active simulator to admitted7's reviewed implementation by restoring
host.py and removing host_program.py. A read-only diff of all differometor/**
against ee4fea28c04d482566be16e916b609d7c6a99e5e is empty. No history reset, no
commit, no benchmark and no other-lane source change. Historical program-check
and dispatch-check scripts target the preserved30–32 sources; run them on those
revisions, not on the restored parent lacking host_program.py.

Next direction: obtain the already prepared opt-in callback profile on admitted7
(overnight-numerics-profile.py, separately from official timings) to distinguish
component/Jacobian time, sparse product/refinement time, factorization and scatter.
Use that evidence to choose a distinct mechanism, rather than a fourth interpreter
or another unpaired tiny allocation variant. The provisional31/32 benefit can
still be resolved by coordinator-run exact-SHA paired repeats and independent
source review without further source edits. Existing actual-matrix diagnostic
requests for28 remain open. This handoff ends the interpreter hypothesis only;
the campaign deadline remains2026-11-22 09:27:44 UTC.

## Candidate33: materialize signal right-hand sides at the solve boundary

The supervisor requested a concrete next experiment after the retirement handoff.
No callback profile or paired confirmation accompanied that request. This is a
narrow conservative refinement on admitted7, not another interpreter, ordering,
or sparse accumulation variant. Scientific parent:
ee4fea28c04d482566be16e916b609d7c6a99e5e. Candidate SHA and both official job IDs
are pending supervisor commit/evaluation. The only simulator delta from that
parent is14 lines in host_pass.py. The host.py restoration and host_program.py
deletion relative to branch HEAD retire32; all earlier commits remain preserved.

Source-established redundancy: host_forward calls _split to allocate a dense
(frequency_rows, system_size) signal RHS, then copies each row into a newly
concatenated signal/noise RHS for _solve. host_backward calls _split and discards
the same dense RHS entirely. None of those arrays is an AD output or residual.
The new forward creates one C-contiguous (system_size,1+detectors) buffer locally,
clears its signal column, scatters the current row's augmented entries and fills
all noise columns before each solve. The backward takes the coefficient slice
directly. This removes two B*N complex arrays per forward/backward pair and
replaces B concatenate allocations with one N*(D+1) buffer. Carrier _split,
all source entries, factors, products, refinement arithmetic and stopping rules
are unchanged. The buffer is not retained or reused across forward evaluations.

Target is allocation/copy work inside forward execution (historical admitted
median181.163ms grid/32.890ms aLIGO), plus the unused reverse RHS allocation.
The fraction of either measured phase attributable to this work is unknown.
This might save too little to distinguish from first-run noise; operation-count
evidence is not a timing claim. No new numerical or architecture parameter is
introduced. Requests for callback profiling remain useful and outstanding.

Local synthetic inspection: existing NumPy/SciPy venv, AST-extracted actual
forward/backward/product/solve functions, no JAX import or optical benchmark.
Run experiments/notes/overnight-numerics-rhs-check.py with python -B.

-72 forward and72 backward pairs match admitted7 bit-for-bit for every returned
 array. Cases vary1/3/9 rows,1/2/4 detectors, augmented/unaugmented matrices,
 noise-row reuse, explicit structural zeros, permuted RHS destinations and
 diagonal scaling spanning1e10. Same-topology reevaluations change both matrix
 coefficients and source values, including zero-to-nonzero sources.
-All1008 refined solve RHS and results match bit-for-bit. Both versions make
 2016 factor.solve calls and384 fresh factorizations. RHS immutability and
 nonaliasing solve outputs are asserted. The production solver is unchanged.
-The source-extracted _split counter measures144 redundant dense RHS arrays,
 totaling69888 bytes across these small checks, reduced to zero for the signal
 path. This measures eliminated materializations, not peak RSS or elapsed time.
-The component pullback stand-in only isolates orchestration and preserves
 base cotangents; these checks do not validate optical differentiation, JAX
 callback integration or modulation physics. Full evaluator checks remain
 mandatory. git diff --check passes.

Request both unchanged official benchmarks on the new exact SHA, all saved
physical outputs and gradients, all14 generalization cases (including modulation),
and independent source review. If promising, obtain paired fresh-process complete
runs against admitted7 on matching CPU/environment, retaining every sample and
reporting phase, RSS and overlap evidence separately for grid and aLIGO. Reject
this refinement if no stable gain is established; do not infer benefit from its
allocation counts or combine it with an unconfirmed historical candidate.

Inherited pristine signal/gradient33,161,180 and random-case disagreements remain
unresolved, as do grid finite-difference54,59,63,136,161,163; prior aLIGO checks
confirmed29/29. Whole-pass custom VJP remains first-order reverse-only. No official
outcome, phase delta, memory improvement or correctness certificate exists for33.

## Candidate33 feedback: retire RHS packing; no gain established

Evaluated SHA ce9d76a7c4ac62acaccb142ceec163e7afa2f4bb, request
f1b9c8cac83c43df9d83a2931288a52a, jobs grid-1/2/3 and aligo-1/2/3.
All six unchanged official benchmarks pass. Complete fresh-process seconds:

- Grid [0.8363840915262699,0.8179306425154209,0.8043074533343315];
  median0.8179306425154209, range[0.8043074533343315,0.8363840915262699].
- aLIGO [0.5528130028396845,0.5587303917855024,0.5564036127179861];
  median0.5564036127179861, range[0.5528130028396845,0.5587303917855024].

Compared with the historical admitted7 cohort, complete medians increased
16.352959ms grid and7.848457ms aLIGO. This is unpaired evidence, not a causal
regression estimate, but it provides no justification to keep this optimization.
Median phase ms / difference from historical admitted7:
grid forward185.768826/+4.605738, reverse84.887264/-0.470160,
build73.965676/-0.028403, imports267.713113/+2.112499;
aLIGO forward32.803399/-0.086751, reverse14.470506/+0.086354,
build42.328773/+4.366228, imports267.888037/+4.379230.
Retain every sample, including grid1 imports296.341499ms. Other-host contention
is not excluded; no cause is assigned to timing variation. Sampled peak RSS:
grid635387904 B, aLIGO295038976 B, generalization942047232 B. No infrastructure
failure or memory exceedance. No independent review or paired parent runs were
supplied. confirmed_improvement=false; selection cites missing source review,
insufficient large gain and overlapping ranges.

Programmatically inspected all six official archive hashes and full strict
comparison records: each equals32's corresponding record. Also compared all14
generalization records against BOTH initial_seed and pristine: unchanged.
All14 pass seed bounds, including zero sensitivity log difference, while only4
pass pristine strict checks. This is inspection of evaluator per-array records;
raw remote NPZ arrays were not independently reopened locally. Archive hash
changes in generalization do not establish numerical differences because those
archives include timing metadata. The candidate-self artifact comparison is not
used as independent correctness evidence.

Decision: reject the RHS packing optimization for promotion and stop this
hypothesis after its first evaluated trial. No speed benefit was established;
do not generate further packing/buffer variants from allocation counts alone.
Restore only host_pass.py to admitted ee4fea2. All differometor/** source again
matches that reviewed parent exactly. This preserves33's committed trial,
synthetic checker and feedback, without resetting history. No reevaluation is
requested merely for this identical parent restoration.

Concrete next experiment is a diagnostic, not another timed candidate: supervisor
should run admitted ee4fea2 under collect_host_profiles from
experiments/notes/overnight-numerics-profile.py in a separate synchronized driver
using the fixed evaluator CPU/thread environment. Supply first host_forward and
host_backward function call counts, self/cumulative times and total profiled
callback time, separately for both unchanged optical setups. Attribute assembly,
factorization, refined solves/products and component Jacobians/scatters. Do not
compare instrumented elapsed times with official first-run totals. This helper
is already implemented and does not execute a workload by itself. The missing
profile is the specific evidence needed to select a materially different
bottleneck; previous repeated requests have not yielded that artifact. Paired
confirmation/review of preserved promising9/13/18/31 can proceed separately;
none is silently promoted or combined here.

Inherited signal and gradients33/161/180 disagreements, rand1/rand3 sensitivity
disagreements and grid finite-difference54/59/63/136/161/163 remain unresolved.
Prior additional aLIGO coordinates confirmed29/29. First-order reverse-only
custom VJP limitations remain. Handoff session overnight-numerics-v1. This stop
ends RHS packing only, not the authorized campaign or its09:27:44 UTC deadline.

## Candidate34: exact Hermitian guard, a numerical repair experiment

Supervisor requested a concrete next experiment after33's retirement. Rather
than another buffer/interpreter variant, inspect the admitted adjoint shortcut's
numerical premise. Scientific parent remains reviewed
ee4fea28c04d482566be16e916b609d7c6a99e5e; candidate SHA and dual job IDs pending.
The only simulator delta from that parent is _is_hermitian and its comments.
Candidate33's RHS changes remain absent. This is a correctness repair experiment,
not an established performance improvement or a claim that prior review was a
universal certificate.

Concrete failure of the old guard on arbitrary supplied coefficients:
A=diag(1,1e-12), N=[[1,e],[0,1]], s=[1,0], e=4*binary64_eps.
A has condition number1e12. The guard accepts N as Hermitian because its
asymmetry8.881784197001252e-16 is below8*eps*max|N|. Forward w=A^-H s and
cov=A^-1 N w are both[1,0]. The shortcut reuses conj(cov), but the explicit
adjoint is conj(A^-1 N^H w)=[1,0.0008881784197001252]. For the real selection
derivative of Re(s^H A^-1 N A^-H s), the old result is[2,0], whereas the
explicit result is[2,0.0008881784197001252]. An independent70-digit Decimal
central difference of the scalar quadratic, using exact binary64 input values,
confirms that nonzero coordinate. This is amplification of a supplied coefficient
asymmetry, not an assertion about the published optical fixtures or a dismissal
of their existing disagreements. Merely bounding the source perturbation by
roundoff does not bound the adjoint error without conditioning information.

Change: accept the noise shortcut only when every supplied coefficient is finite
and equals its conjugate-transposed partner exactly. Unpaired structural entries
must be zero. Any nonzero mismatch keeps the existing explicit refined solve.
Retain structural zeros and their derivative contributions. No coefficients,
conjugation rules, refinement counts/tolerance, forward solve or Jacobian change.
The guard replaces magnitude/subtraction/max reductions with finite/equality
checks. This could alter guard overhead slightly, but speed is not the rationale
and is unmeasured. Rejecting additional rows may increase reverse execution time;
count triggers and include their cost in both complete official benchmarks.

Local evidence: experiments/notes/overnight-numerics-hermitian-check.py,
existing NumPy/SciPy environment, AST-extracted actual guard/product/refinement
functions; no optical workload or benchmark timing.

-360 checks agree with an independent dense exact-Hermitian predicate, covering
 sizes1/2/5/11, random sparsity, paired/unpaired entries, zero and changed values,
 small asymmetries, imaginary diagonals and nonfinite values.
-28 source-derived physical noise component cases (vacuum, real loss, real
 squeeze strength and angle variations) retain the shortcut in both versions.
 Initial test used flattened output order for squeezer and failed; repaired the
 synthetic mapping to its documented [upper diagonal, upper off-diagonal,
 lower diagonal, lower off-diagonal] order. Production source was not changed
 to accommodate this diagnostic error.
-The analytic example above rejects the old shortcut and uses the unchanged
 refined solve; resulting selection derivative matches the independent70-digit
 finite difference. Both accepted and rejected guard paths are exercised.
-No full optical gradient, modulation or JAX callback validation is claimed
 from these small checks. git diff --check passes.

Separate newly identified open issue: _collinear_coefficient accepts direction
[1,0] and vector[1,e] with alpha1 under the same tolerance. With the diagonal A
above, reusing its solution omits the same8.881784197001252e-4 component. That
guard is intentionally unchanged in34 to keep the repair attributable. Its
legacy constant HERMITIAN_TOLERANCE remains for that caller; comments now make
the distinction explicit. Exact Hermiticity does not fix this separate gap or
prove safety of every adjoint shortcut.

Supervisor request: both unchanged official benchmarks on the new exact SHA,
all saved carrier/signal/noise/power/sensitivity/loss/gradient comparisons,
14-case generalization including amod/fmod and independent source review. In a
separate diagnostic, count old-accepted/new-rejected noise rows for each supplied
setup, with maximum coefficient asymmetry and the resulting gradient changes.
Investigate every new discrepancy rather than declaring it harmless or correct
from this one example. Report forward/reverse phase and complete first-run/RSS
tradeoffs. If numerical results and timing warrant promotion, obtain paired
fresh-process repetitions against7 under matching hardware/resources. No shared
best or performance claim is made for34 before that evidence.

All previous pristine signal/gradient33,161,180 and rand1/rand3 disagreements,
unresolved grid FD54,59,63,136,161,163 and first-order reverse-only compatibility
limits remain visible. Earlier aLIGO extra coordinate confirmation was29/29.

## Candidate34 feedback and candidate35 collinearity repair

Candidate34 SHA86860bdcbf4b02888b5db6ca2aa563234db0721a, dual job
0040cde2d2cd4b8b8be168f2ae794354 (grid-1/2/3 and aligo-1/2/3).
All six official runs pass. Large complete fresh-process samples in seconds:
[0.830339940264821,0.8017230369150639,0.8163026496767998], median
0.8163026496767998, range0.8017230369150639–0.830339940264821.
Official aLIGO samples separately:
[0.5522543229162693,0.5516744591295719,0.5491008665412664], median
0.5516744591295719, range0.5491008665412664–0.5522543229162693.
No confirmed improvement; independent review absent, ranges overlap admitted7.
Against7's earlier unpaired medians this is +14.724966ms large/+3.119303ms
aligo, not a causal regression estimate. No new paired parent cohort was supplied.
Retain all samples, including grid-1 imports294.057457ms and grid-3
forward200.199405ms. CPU2/one logical CPU/library threads1/no persistent cache;
external job overlap remains unknown. No combined score or organizer ranking claim.

Median measured phases (ms), with deltas against7's earlier cohort:
large forward186.227094 (+5.064007), reverse84.672386 (-0.685038),
build72.366131 (-1.627949), imports266.551157 (+0.950543).
aLIGO forward33.085752 (+0.195602), reverse14.608346 (+0.224194),
build38.302202 (+0.339657), imports266.015533 (+2.506725).
Sampled peak RSS maxima large535625728 bytes, aligo313241600 bytes,
generalization881901568 bytes. Sampling is not a peak-memory guarantee.

Inspected every saved per-array comparison record (carrier, signal, noise,
powers, sensitivity, loss, gradient). All six official array archive hashes and
strict comparison records are identical to33. All14 generalization initial-seed
case records and pristine case records are also identical to33; seed14/14 pass,
pristine4/14 pass. Raw remote NPZ arrays were not reopened locally. Candidate and
seed are within comparison bounds, not asserted bitwise identical: official
large gradient max difference5.686350050382316e-6, relativeL2
8.181451454702114e-11; aligo3.637978807091713e-11 and1.294943745154708e-15.
Pristine grid131 signal/3 gradient/1 loss failures and official aligo1 loss
failure persist. Generalization rand1/rand3 log sensitivity errors remain
2.036099068405406e-4/5.8100919558157216e-5; other inherited failures remain.
No requested noise-guard trigger counts or source review were returned.

Decision: retain34 provisionally for its demonstrated synthetic correctness
repair, not as a timing winner or admitted shared improvement. Candidate35 fixes
the separate collinearity issue recorded in34. This is a conservative guard
repair on34, not a renewed allocation/interpreter optimization or an automatic
combination of phase winners. Admitted7 remains the strongest reviewed timing
reference. Candidate35 SHA pending supervisor commit. Other simulator files
remain as in7; only host_pass.py has these two guard repairs.

The old _collinear_coefficient admits vector[1,e], direction[1,0] with alpha1,
e=4*binary64_eps, discarding the second cotangent coordinate. For
A=diag(1,1e-12), A^-T vector has second coordinate8.881784197001252e-4,
which the reused solution omits. The component scales linearly with input scale.
This is a generic numeric example, not a claim that the official workload
triggers the failure.

Change35: keep the least-squares alpha calculation but accept reuse only when
np.array_equal(vector, alpha*direction). Every nonzero computed residual keeps
the existing refined transpose solve. Zero vectors accept finite directions;
nonfinite directions now reject even for a zero vector. Remove the now unused
HERMITIAN_TOLERANCE constant. No numerical input, derivative contribution,
factorization, correction-count limit, correction tolerance, transpose convention,
physical workload or JAX stage changes. This computed equality test is a narrower
sufficient condition for this implementation's reuse decision, not a proof of
exact real-arithmetic collinearity or universal accuracy of reused solutions.
Floating multiplication and the already computed forward solve retain their
normal numerical errors. Mathematically collinear vectors can be rejected when
the least-squares alpha or product rounds differently; overhead must be counted.

Local small synthetic evidence:
experiments/notes/overnight-numerics-collinearity-check.py AST-loads actual35
and34 guard functions plus unchanged sparse product/refined solver; no JAX or
optical benchmark is executed and no timings are collected.
-480 random guard checks across sizes2/5/13, complex strided directions, four
 scaling coefficients and changed numeric inputs.171 accepted products equal
 supplied vectors exactly;309 reject, including all240 deliberately perturbed
 vectors. Thus69 of240 unperturbed computed scalar multiples fall back too.
-23 special checks cover zero directions/vectors, signed zero, real/complex
 values, exact accepted scalars, NaN and infinities.
-18 transpose-solve repair checks vary diagonal conditioning1/1e8/1e12,
 input scales2^-20/1/2^20 and real/imaginary perturbations. Old guard accepts
 and new guard rejects all18. Fallback results agree with independent70-digit
 Decimal central differences of a diagonal linear loss (max absolute difference
0.0 in binary64 comparison); maximum old absolute error931.3225746154785 at
 largest input scale and conditioning. This is an absolute error, not normalized
 optical accuracy. Subsequent exactly collinear inputs retain reuse.
-git diff --check and syntax parsing pass. Historical hermitian-check.py records
 candidate34's then-unrepaired collinearity assertion and is revision-specific;
 it is not a current35 test. No historical failure has been erased.

Request supervisor evaluation on one exact new SHA: both unchanged official
benchmarks, all saved output/gradient comparisons, all14 generalization cases
including amod/fmod, and independent review of both guard repairs. Separately
measure old-accepted/new-rejected signal vectors and noise rows, guard/fallback
cost and gradient changes on varied parameters/frequencies/modulation. Investigate
any new discrepancy before attributing it to improved accuracy. Timing impact
unknown; this is ready for correctness/performance evaluation, not promotion.
If promising, obtain paired fresh-process candidate/parent repetitions under
matching resource policy. Keep all existing pristine disagreements and unresolved
grid FD54,59,63,136,161,163 visible; earlier extra aligo coordinates29/29 passed.
Whole-pass custom VJP still lacks forward-mode JVP and Hessian support.
