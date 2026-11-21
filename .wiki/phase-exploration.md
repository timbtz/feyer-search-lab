# Candidate phases and Pareto exploration

Open `.lab/phase-dashboard/index.html` in a browser for the live local snapshot. It offers selectable scatter-plot axes, a candidate table, all 14 first-run phase timings, savings versus the baseline, and savings versus the previous evaluated code ancestor. Click a point or table row for details. Use Refresh snapshot after a new evaluation finishes.

The checked-in [comparison](../experiments/analysis/README.md), JSON, CSV and standalone HTML under `experiments/analysis` are a published snapshot. GitHub renders the Markdown and ancestry graph; download/open `index.html` for the interactive view. The local dashboard updates automatically while the watcher is running; the GitHub snapshot changes only when explicitly regenerated and committed.

## What the labels mean

The primary score remains complete first-run total. The six Pareto objectives are setup, tracing/lowering plus compilation, forward execution, sensitivity execution, gradient execution and host transfer. All are minimized. Setup and compilation also have detailed subphase comparisons. Warm medians and peak RAM are retained separately and are not mixed into these objectives.

The baseline is three independent official runs on the same AMD CPU and environment. Each phase uses its own baseline median; those medians need not sum to the median complete total.

An **observed Pareto frontier** candidate is not dominated by another fully validated candidate or the baseline phase-median point: no other point is at least as fast in all six groups and strictly faster in one. This is exact dominance of measured numbers, not a significance test. Tiny timing differences can leave several candidates on this frontier even when one has a much worse overall score. A failed or merely screened candidate is displayed but excluded from the frontier. Different hardware, workload, dependencies or execution settings are excluded from comparisons.

An **observed improvement** flag requires a phase change exceeding the largest of 20 milliseconds, 3% of that baseline phase's median, and that phase's range across the three baseline runs. The same rule flags regressions. This is a practical noise heuristic, not a confidence interval. Classification distinguishes improvement without detected regression, a tradeoff, regression, and changes inside the noise band. Repeat independent first-run evaluations before treating a gain as established.

An aggregate phase improvement can conceal a subphase regression. For example, candidate 4 reduced aggregate compilation, including forward and gradient compilation, but increased forward tracing/lowering. Its gradient execution improvement was much smaller. The detailed table preserves that distinction.

## Regenerate

From the main checkout:

```bash
python3 -m lab.phase_report --output .lab/phase-dashboard
python3 -m lab.phase_report --output experiments/analysis
```

The collector reads immutable `experiments/runs/*/candidate-*.json` records from the main checkout and all registered local Git worktrees, deduplicating the same SHA/job pair. To include a remote-only agent branch in a fresh clone, fetch it and create a local worktree for it first. Ancestry edges come from Git commit relationships; they are not claims of causal attribution.

For continuous local updates during the supervised run:

```bash
python3 -u -m lab.phase_report --output .lab/phase-dashboard \
  --watch-session .lab/sessions/seed-agent/status.json
```

The watcher refreshes every ten seconds and exits after the session completes, stops or fails. Restart it if the supervisor is resumed later. It does not run benchmarks, change the queue, start agents or extend the agent's deadline. Existing raw phase reports already reach the optimization agent through evaluator feedback.

For finer breakdowns inside matrix assembly, factorization, solves or setup construction, use a separate diagnostic profiling experiment. Keep profiling overhead out of the canonical benchmark score.
