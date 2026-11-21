# claude-sparse-adjoint: sparse SuperLU solves with custom VJP

- Branch `explore/claude-sparse-adjoint`; parent `3b805077bb5c61d85115faf38af243cc001d0fee`
  (claude-guided-v2 candidate 3, full job 57ef1df7: official+strict PASS, 19.567 s).
- Manual operator (Claude worker forked from the coordinating session). Deadline epoch 1795303326.

## Motivation (measured, AMD CPU 100 dev prototype)
- Signal system 751x751 per frequency with a static 2533-entry structural pattern (0.45 %);
  carrier 286x286 (680 nnz); noise source matrix 272 nnz. cond(A) ~ 1e30 (scaling).
- SuperLU (COLAMD) factor + 3 solves for 101 frequencies: 0.091 s; numpy dense solve 2.5 s.
- Incremental `scipy.sparse.linalg` import after JAX: 0.081 s.

## Design (generic for any built setup)
- `differometor/sparse.py`: `SparsePattern`/`SparseSystem`/`SparseStructure` are static pytree
  nodes (`register_static`, content-hashed) derived on the host in `run_build_step` from the
  concrete base matrices and update destinations: union of base nonzeros, every update write
  position, carrier placing positions. Nothing depends on the uifo fixture.
- `sparse_solve(pattern, transpose, values, rhs)`: `jax.custom_vjp` + `jax.pure_callback`
  (`vmap_method="broadcast_all"`) to SciPy `splu`. bwd: b_bar = op(A)^-T x_bar,
  A_bar[i,j] = -b_bar[i] x[j] (transposed for op=T). A^H solves = transposed solves of conj(A).
- Convention test vs `jnp.linalg.solve` VJP (random complex 30x30, both modes, conj path,
  jit, vmap, grad of real loss): all max diffs <= 4e-15.
- `simulate(..., sparse_structure=...)`: carrier/signal/noise assembled as value vectors with
  the same ordered scatter, placing scaling and sideband conjugation; parent's grouped,
  slot-pruned component evaluation retained. Signal + covariance solves share one
  factorization (1 + D right-hand sides). Dense path retained when the structure is absent
  or `SPARSE_SOLVES = False`.

## Candidate 1
- Dev smoke (CPU 100, NOT a scored run): official benchmark PASS; first run 8.49 s
  (imports 0.298, build 0.324, fwd lower 0.527 / compile 5.574, fwd 0.216, sens 0.03/0.18,
  grad lower 0.102 / compile 1.112, grad 0.120); warm median 0.226 s.
- Arrays vs pristine base1.npz: sensitivity max |dlog| 6.8e-8 (official limit 1e-5);
  noise relL2 2.3e-8; carrier relL2 4.8e-12; powers 6.7e-12; gradient relL2 8.7e-8,
  strict (rtol 1e-7) fails 3/193 at indices 161 (rel 7.8e-7), 33 (6.9e-7), 180 (5.1e-7) — the
  same indices that failed strict for every earlier factorization change (dense shared-LU).
- SHA `0dea4ec707f970e2003cd8f43fcb629be710d5ac`. Screen `b24872db821b4678a6be01a63ff9233c`
  (request e27eb152-95f8-4351-915a-d738da086424): first run **8.525 s** (parent 19.567 s full;
  screen profile runs no official checks); wall 9.05 s; peak RSS 0.80 GB (parent ~14 GB).
- Cross-setup harness (coordinator's /tmp/claude-gencheck, vs pristine): FAILS on 4/8 setups —
  max |dlog S| voyager 3.4e-3, uifo_rand1 2.2e-4, uifo_rand3 5.8e-5, uifo_20_5000 2.8e-5.
- Diagnosis with extended-precision (x86 clongdouble residual) iterative refinement as a truth
  proxy (refinement converges to 1e-16 in 2 steps):
  - voyager noise^2: dense LU error 6.3e-13, plain SuperLU 5.5e-3 (COLAMD/MMD/Equil same;
    NATURAL ordering 1.1e-12), SuperLU + 1 double-precision refinement step 6.0e-13.
  - uifo_rand1 noise^2: dense 1.3e-12, SuperLU 4.4e-16. |detected| (2-port differential):
    **dense 2.6e-4**, SuperLU 6.6e-5, SuperLU + 1 refinement 9.1e-11.
  - uifo_rand3 |detected|: **dense 3.8e-5**, SuperLU 2.0e-8, + refinement 2.5e-8.
  - => plain SuperLU is not accurate enough; on rand1/rand3 the pristine dense result itself is
    the inaccurate one, so "match pristine" is not the right target there.
- Decision: reject candidate 1 for numerics (fast, but voyager/uifo_20_5000 wrong).

## Candidate 2 — candidate 1 + iterative refinement in every sparse solve
- `_host_solve`: after the SuperLU solve, refine x += solve(b - op(A) x) (double precision),
  1 to 3 steps, stop when max|dx| <= 1e-14 max|x|. Applies to forward and backward solves.
- Cross-setup (vs pristine): aligo 1.3e-10, dev 6.7e-8, dev_perturbed 3.3e-8, uifo_20_5000
  4.9e-11, uifo_rand2 9.7e-10, voyager 1.0e-11 (all OK); uifo_rand1 2.0e-4 and uifo_rand3
  5.8e-5 differ from pristine where pristine itself deviates from the refined truth (above).
  Gradient relL2 vs pristine <= 1.5e-5 everywhere (rand3); dev 8.7e-8.
- SHA `4af20b7baa9e363f46177c92a7b979794032a167`.
  - Screen `779751db31504f8eaa6ccffaa62c6768` (request in .lab/c2-screen-request-id): first run 8.695 s.
  - Full `3723bee87d1b4b1a87656141f017dc8f`: **official PASS**, strict FAIL (as predicted).
    First run **8.639 s** (parent 19.567 s; -55.8 %; single sample). Phases: imports 0.294,
    initialize 0.003, load 0.002, build 0.305, forward lower 0.525 / compile 5.583, forward
    0.274, sensitivity lower 0.030 / compile 0.191 / exec 0.001, gradient lower 0.102 /
    compile 1.124, gradient 0.207, host transfer 0.000. Warm median 0.355 s (parent 10.16 s).
    Peak RSS 0.81 GB (parent ~14 GB). Job wall 14.35 s.
  - Official: max |log S - log ref| 5.374e-6 (baseline 5.374e-6); FD check mb11.tuning autodiff
    7.61617e-5 vs central differences 7.61660e-5 / 7.61625e-5 (pass).
  - Strict vs baseline arrays: carrier/noise/sensitivity/powers pass (noise max normalized 0.78,
    sensitivity 0.67); signal fails 131 entries (max normalized 1.53, rel ~1.5e-7); gradient
    fails indices 33 (6.81), 161 (7.68), 180 (3.65) — rel <= 7.7e-7.
  - Truth arbitration on the dev fixture (extended-precision refinement, signal solve):
    strict-style max normalized error vs truth: **pristine dense 2.34**, plain SuperLU 1.91,
    **SuperLU + refinement 0.005**; |detected| rel error: dense 1.4e-7, sparse+ref 5.2e-10.
    The strict signal failure therefore measures the dense reference's own rounding error.
    The gradient indices 33/161/180 were not arbitrated against a truth (open).

## Compile investigation (dev, CPU 100)
- Forward-only compile 2.9 s; forward vjp 5.3-5.6 s; gradient 1.0-1.1 s. 373 fused kernels in
  the forward vjp; ~half are dominated by complex sqrt (96) and complex asin (82) from the
  surface/incidence-angle component math on complex-typed parameters.
- Parent's COMPONENT_SLOT_PRUNING still pays in the sparse path (off: fwd vjp +0.9 s, grad
  +0.7 s); LOWER_SLOT_PRUNING neutral. Kept both.
- Rejected without a candidate: real-arithmetic component evaluation (complex asin is needed
  for total internal reflection at angled beamsplitters with refractive-index sides — unsafe
  for varied setups); alpha==0 specialisation (beamsplitter rows keep the asin kernels).

## Next decision
- Keep candidate 2 as the branch best (official PASS, 8.64 s).
- Next: compile is 6.7 s of 8.6 s. Candidates: share component kernels between carrier and
  signal systems (same functions), compile-cheaper formulations of complex sqrt/asin that are
  provably identical on all branches, or moving component Jacobians out of the forward stage
  only if total compile drops (parent's remat moved compile without net gain).

## Candidate 3 — candidate 2 + shared statically gathered component columns
- Op attribution: ~60 % of forward-vjp StableHLO ops come from grouped component evaluation;
  the six 54-row signal groups (surface, susceptibility, force_calculation_left/right,
  corrected_optomechanical_phase_left/right) dominate. incidence_angle_right (complex asin)
  is evaluated 5x per surface and sqrt(R(1-loss)) 3x, each on separately gathered inputs
  (traced index leaves), so XLA could not CSE them.
- Change (sparse path only): `SparseStructure.group_indices` holds static host copies of the
  per-group parameter indices; `_shared_component_outputs` gathers each distinct index column
  once per system/row and passes the same value to every group (`SHARED_COMPONENT_COLUMNS`).
  Component arithmetic, slot pruning and lower-variant handling are unchanged.
- Dev (CPU 100): forward vjp compile 5.43 -> 4.50 s (A/B, same process type), forward lower
  +0.09 s, gradient compile unchanged (1.07 vs 1.01 s).
- Numerics: dev arrays bitwise identical to candidate 2 full job 3723bee8 for carrier, signal,
  noise, sensitivity, powers; gradient max rel 1.7e-15. Cross-setup vs candidate 2: forward
  outputs bitwise identical on all 8 setups; gradient relL2 <= 8e-17; every case 0.4-0.7 s
  faster (harness first-run excl. imports, e.g. dev 8.12 -> 7.45 s, voyager 7.88 -> 7.10 s).
- SHA `ac49ee4dcc23443f5ffdf4eb740fcdc2e09b1ff7`. Screen `3f07f5a979a54981b7c1d4075e4e571e`:
  7.733 s. Full `4f57030fada14a84b5d2eb30d61cd277`: **official PASS**, strict FAIL (same
  failure class as candidate 2); first run **7.738 s**.
- Candidate 2 repeat full `6b9deb9657e64992bf65e562ee77b670` (same SHA 4af20b7): 8.634 s
  (first sample 8.639 s) — two samples 0.005 s apart.

## Rejected experiment — rematerialized component evaluation (flag COMPONENT_REMAT, off)
- Dev A/B: forward vjp compile 4.50 -> 3.25 s, gradient compile 1.07 -> 3.25 s: net +0.9 s.

## Candidate 4 — candidate 3 + joint evaluation of lower variants with their base
- `JOINT_LOWER_GROUPS`: `space`+`space_lower`, `space_modulation`+`space_modulation_lower`
  (and laser frequency modulation when present) evaluated by the base function on
  concatenated rows with slot 0 negated for the lower rows; gradient-stop masks are the OR of
  both groups' masks.
- Dev A/B: forward vjp compile 4.41 -> 4.07 s; gradient compile 1.07 -> 1.04 s.
- Numerics: forward outputs bitwise identical to candidate 3 on all 8 setups; gradient relL2
  <= 6.7e-17. Harness first run (excl. imports) 0.1-0.5 s lower per case (dev 7.45 -> 6.91 s).
- SHA `b890b981d280ec70ef033cc96f427e61fd605ab4`. Screen `2c3235e649b04fe0863cb9ea8b185592`:
  7.372 s. Full `3151c9a9173c4c27bf77fcccafebebfa`: **official PASS**, strict FAIL (same class);
  first run **7.388 s**.

## Rejected experiment — cross-system joint component evaluation (flag off)
- One evaluation per component function across carrier/signal/noise rows. Same-window A/B:
  forward vjp compile 4.31 s vs 4.31/4.33 s (unchanged), gradient compile +0.14 s. Off.
- Static output selection (STATIC_OUTPUT_SELECTION, on): forward vjp compile -0.09 s,
  gradient -0.02 s (marginal); bitwise identical on all 8 setups incl. gradients.

## Candidate 6 — custom_linear_solve instead of custom_vjp (JAX transformation semantics)
- Requirement (organizer, via coordinator): keep full JAX transformation semantics
  (jvp/jacfwd/hessian/vmap/jit(value_and_grad)); custom_vjp cannot be forward-differentiated.
- `sparse_solve` now uses `lax.custom_linear_solve`: matvec = JAX scatter-add over the value
  vector (differentiable in the values), solve/transpose_solve = SuperLU callbacks with the
  same iterative refinement (vmap_method broadcast_all). No custom_vjp remains.
- Primitive tests vs dense jnp.linalg.solve (random complex 30x30, both transpose modes):
  vjp/grad/vmap/vmap-grad <= 2.7e-15, jvp <= 7e-16, hessian <= 5.6e-17, jacfwd == grad.
- jaxcompat.py (voyager) vs pristine: OVERALL COMPATIBLE — value_and_grad_jit 4.0e-10,
  descent_3_steps 1.4e-8, vmap_value_and_grad 4.0e-10, jvp 2.1e-10, jacfwd_2 1.5e-9,
  hvp fwd-over-rev / rev-over-rev 2.4e-12, eager 4.0e-10, public_run 9.3e-12,
  checkpoint_grad 4.0e-10, second_setup_same_process 4.0e-10.
- Dev (CPU 100): forward vjp compile 4.29 s, gradient compile 1.05 s (within host noise of the
  custom_vjp version); first run 7.31 s; official benchmark PASS.
- Numerics: forward outputs bitwise identical to candidate 4 (job 3151c9a9 arrays); gradient max
  rel 2.8e-10, relL2 2.8e-12 (JAX-transposed summation order). Cross-setup vs pristine unchanged
  from candidate 4; gradient vs candidate 4 worst 4.4e-11 (dev), <= 5.6e-13 elsewhere.
