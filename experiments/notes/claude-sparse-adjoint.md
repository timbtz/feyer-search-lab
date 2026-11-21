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
