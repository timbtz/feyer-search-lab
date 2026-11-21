# Feyer experiment rules

## Scope

This repository contains the public Differometor challenge plus the team's experiment infrastructure. Follow explicit task ownership. Infrastructure maintenance may change the lab and documentation when requested by the user or coordinating maintainer. The rules below apply to optimization agents evaluating simulator changes.

## Optimization agents

- Work only in your assigned isolated worktree and branch. One active writer owns each branch. Do not edit another agent's files or force-push shared experiment history.
- Unless your task explicitly expands scope, edit only `differometor/**` and your notes beneath `experiments/notes/**`.
- Never modify `benchmark.py`, `plot_timings.py`, `examples/data/**`, `requirements.txt`, `pyproject.toml`, `setup.py`, the lab evaluator, the queue, shared environment configuration or baseline artifacts.
- Keep all 101 frequencies, all 193 design variables, the complete optical setup, double precision, physical outputs and gradients. Do not cache/precompute answers or enable persistent compilation caching. Preserve the official benchmark's three JIT stages.
- Use the fixed `/workspace/venv-feyer` environment through the evaluator. Never install PyTorch or modify the image's Python. Do not change shared dependencies during evaluation.
- Evaluate exact committed revisions through the lab. Under `lab.agent_loop`, edit permitted files and return the required structured response; the supervisor checks paths, commits, pushes, submits and waits. Do not make Git commits or GitHub/SSH calls from the managed agent. Manual operators use the evaluation client. Do not start independent remote benchmarks or change CPU affinity to obtain a better score. CPU 2 and serial execution are the initial policy.
- Treat `screen` results as provisional. A shared best candidate requires the unchanged official full benchmark to pass. For numerical changes, inspect the saved full outputs and gradient comparison as well.
- Record the candidate SHA, hypothesis, run identifiers, results, failures and next decision in your notes. Never claim an expected optimization is measured.
- Preserve failed trials in branch history. Distinguish import time, compilation time, warm runtime, complete first-run time and total job duration.
- Do not merge into `main` without the coordinating maintainer's instruction.
- Do not spawn additional agents, create new services or increase evaluator concurrency during the initial exploration session.
- Keep credentials in the environment or approved credential tooling, never in Git or experiment notes. Do not copy private keys or account tokens to the instance.

## Initial session budget

The first optimization session is limited to four distinct candidate revisions or one hour from its first work, whichever is reached first. Repeated screen/full runs of one revision are not new candidates. Return `summary`, `hypothesis`, `ready_for_evaluation`, `stop` and `notes` as required by the supervisor's schema. Both readiness and stop may be true when the last candidate should be evaluated before finishing. At the limit, finish safe bookkeeping, write a handoff and preserve the session identifier so the session can be resumed explicitly. Do not silently extend the budget.

Read `.wiki/README.md` and `experiments/initial-agent.md` before starting the first exploration. Use the checked-in client help for the actual queue commands; do not guess commands or bypass failures.
