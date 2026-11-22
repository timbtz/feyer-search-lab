# Overnight campaign: import, setup and small-compilation overhead (overnight-overhead-v1)

- Branch `explore/overnight-overhead-v1`; seed / parent `53f38d342c3228c052785e8c9d63b6ce9c832dd1`.
- Campaign deadline 2026-11-22 09:27:44 UTC (supervisor epoch 1795339664). Supervisor commits, pushes and
  evaluates; this agent makes no commits, remote calls or benchmarks. Local tools here have no shell, so
  no local timing or execution is available; every timing claim must come from evaluator feedback.
- Seed reference (supplied audit, not recalibrated in the current evaluator): large median 0.986991538 s,
  aLIGO median 0.626026371 s. Single-run seed phases: grid imports 0.30075, build 0.07331, trace/lower +
  compile ~0.2493 s; aLIGO imports 0.27080, build 0.03848, compile ~0.2502 s.

## Candidate 1: defer imports unused by the simulation path

- Parent `53f38d3`. Candidate SHA: supplied by supervisor feedback (pending).
- Import graph (static inspection): benchmark times `import jax`, `jax.numpy`, `numpy`, `differometor`,
  `differometor.setups`. Beyond JAX/NumPy, differometor's package import pulled in:
  - `differometor.plot` → `plotly.graph_objects` (plotly 7.1.0, which also loads narwhals), only for
    `visualize_setup`; no simulator module uses it.
  - `jax.scipy.linalg` at top of `simulate.py`, used only by the dense `_solve_signal_and_noise` path
    (`lu_solve`). The default path (sparse structure + `HOST_PASS`) never calls it.
  - SciPy is already lazy (`sparse._scipy`, `host_pass._superlu_gstrf` loads only `_superlu`).
  - No module-level jnp computations in components/build/setups (no eager XLA work at import).
- Change: `__init__.py` exposes `visualize_setup` via PEP 562 `__getattr__` (loaded and cached on first
  access; `__all__`/`__dir__` still list it; `from differometor import visualize_setup`,
  `df.visualize_setup` and `from differometor.plot import visualize_setup` keep working, returning the
  original function). `simulate.py` imports `jax.scipy.linalg as jax_scipy_linalg` inside the dense branch
  (aliased so `jax` is not rebound as a local name). No numerical code changes; outputs/gradients must be
  bitwise identical.
- Hypothesis: lower `imports` phase and complete first-run time for both benchmarks by the cost of Plotly
  (+narwhals) and jax.scipy.linalg module loading. Size unknown: the 2025 initial agent saw no gain from
  the plotly part on a 36 s workload where ±25 ms import noise was invisible; plotly may already lazy-load
  graph_objs, and jax.numpy may already import parts of jax.scipy. A null result is plausible and would
  show imports are dominated by JAX/jaxlib itself (not in our control without launch tricks).
- Validation needed: official large + aLIGO pass, strict comparison identical to seed (no numerical
  change), repeated fresh-process imports-phase comparison vs parent.
- Next ideas (in lane): (a) profile `trace/lower` of the three stages — callback signature size (host_pass
  passes base value vectors and 5 outputs incl. covariances/weights as residuals); (b) build phase
  (~73 ms large): Python builder loops and `run_build_step` set comprehensions; (c) sensitivity readout
  stage compile (~0.08 s) for a tiny program.
