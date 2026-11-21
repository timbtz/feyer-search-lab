# Initial exploration: seed-agent

- Assigned worktree: `/Users/t.betz/Documents/Feyer challenge agents/codex-seed`
- Assigned branch: `explore/seed-agent`
- Starting checkout / candidate parent: `0bf57ae2af4a377f72cb34a3d6a328c714baafc8`
- Public simulator baseline: `02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f`
- Managed session label: `seed-agent`; conversation identifier unavailable in supplied context. Local `.lab/sessions/seed-agent/status.json` is absent. Supervisor owns session continuity and submission.
- Budget: four distinct candidates or one hour; this is candidate 1/4. Initial supervisor allowance: 3599 seconds. No commits, pushes, SSH calls, local benchmark runs, or evaluator submissions made by agent.

## Baseline evidence supplied by maintainer

Unchanged AMD official complete first-evaluation totals: 35.821919, 35.614326, 35.737065 seconds; median 35.737065 seconds. All three official checks passed. Reported warm medians approximately 15.49–15.73 seconds. Baseline import, compilation and total job-duration breakdowns were not supplied in this turn.

## Candidate 1: defer visualization import

- Candidate SHA: pending supervisor commit; parent above.
- Hypothesis: avoiding `differometor.plot` and its Plotly import during benchmark package initialization reduces import time and complete first-run time. Simulation/compilation/warm runtime should be unaffected, but this is unmeasured.
- Static import inspection: `__init__.py` eagerly imported `visualize_setup`; `plot.py` imports `plotly.graph_objects`, NumPy, dataclasses and collections and creates rendering constants at import time. No other simulator module imports `plot.py`. The benchmark imports `differometor as df` and does not import the visualization function.
- Change: replace the eager re-export with module `__getattr__`, loading and retaining the original function on first attribute access. Explicit public exports retain wildcard access to visualization; `__dir__` retains discovery without loading Plotly. Named imports and the original callable signature, identity and documentation are preserved. A wildcard import intentionally still loads visualization.
- Local validation: Python syntax compilation and isolated package-export smoke checks with stubbed simulator/plot modules passed. Checked that package initialization and `dir()` do not load plot, missing attributes raise `AttributeError`, named import returns the original callable, repeat lookup is cached, and wildcard imports resolve all eight public exports. This is export-machinery validation only, not physics or real dependency validation. No dependencies installed or modified.
- Tool failures: first execution host timed out before a response; retry succeeded. Two commands involving `rg` exited 137; import and instruction inspection completed using Python AST/path reads instead. These were local tooling failures, not evaluator failures.
- Screen run / status / phase timings: pending.
- Full run / official checks / saved-array errors: pending.
- Import time, compilation time, warm runtime, complete first-run time and total job duration: no candidate measurements yet.
- Decision: submit this isolated import candidate for screening; no gain claimed and no new validated candidate yet.

## Handoff / next action

Supervisor should commit and screen candidate 1, then return its exact SHA, run identifier, import timing and complete first-run total. If promising, fully validate the same SHA before treating it as a validated improvement. Record all phase timings and correctness results here on resumption. Baseline remains the only validated reference.

After resolving candidate 1, inspect noise-system coefficient and RHS shapes and the fixed evaluator JAX lowering to establish whether factorization is already shared. Only then consider a separately attributable numerical rewrite, requiring saved carrier, signal, noise, sensitivity, powers, loss and full-gradient maximum absolute and relative errors plus the official gradient check. No noise or numerical edits have been made.
