# Experiment rules

The objective is the lowest correct complete first-run evaluation time on matching hardware and CPU limits. The experiment system must preserve enough evidence to reproduce both improvements and failures.

## Challenge invariants

- Keep the complete public optical setup, all 101 frequencies, all 193 physical design variables and double precision.
- Preserve physical outputs and gradients. Sensitivities must be positive and satisfy `abs(log(sensitivity) - log(reference)) <= 1e-5` at every frequency.
- Carrier, signal, noise, sensitivity, powers, loss and gradients must be finite. The full gradient must not be identically zero.
- Full validation must pass the official numerical gradient check.
- Keep the official benchmark's staged timing and include setup, imports, initialization, all compilation, simulation, sensitivity, gradients and result transfer.
- Do not enable persistent JAX compilation caching, omit work, precompute answers or merge the official benchmark's three separately compiled stages.

The official rules and repository are authoritative. Treat uncertain rule interpretations, including unusual XLA configuration changes, as questions for the Feyer organizers before relying on them in a submission.

## Protected files and environment

Optimization candidates may modify `differometor/` and their own research notes. They may not modify `benchmark.py`, `plot_timings.py`, `examples/data/`, `requirements.txt`, `pyproject.toml`, `setup.py`, the trusted evaluator or its runtime configuration. The evaluator compares protected content with the fixed upstream baseline.

Use `/workspace/venv-feyer` for Feyer evaluation. Do not reinstall the image's PyTorch, change global Python or mutate the shared virtual environment during experimentation. A dependency experiment requires a separately identified environment and a fresh matching baseline, outside the first agent's scope.

## Candidate and run records

Every candidate needs a full commit SHA, direction, agent identifier, hypothesis and parent candidate. Every run needs a unique identifier, selected profile, environment information, CPU assignment, status and artifact paths. Record failures as well as successes. Never overwrite a previous run or baseline artifact.

Write a short note after each result: what changed, the evidence, whether the hypothesis survived, and the next action. Notes should cite commit and run identifiers. An expected speedup is not a measured result.

## Promotion

| State | Evidence required |
| --- | --- |
| Screened | Complete workload evaluated once; screening checks passed; timing recorded |
| Validated | Unchanged official full benchmark passed for that exact commit |
| Confirmed improvement | Repeated full runs under matching conditions show a reproducible improvement over the baseline |

A failed or incomplete candidate cannot enter the validated ranking. Screening helps allocate evaluation time; it is not the final correctness gate. A reduced smoke test, if added, is only a debugging result.

For numerical changes, compare saved carrier, signal, noise, sensitivity, powers, loss and full-gradient arrays against the baseline. Record maximum absolute and relative errors with the chosen tolerances; near-zero values need an absolute-error criterion. Do not assume a linear algebra rewrite changes results only by harmless rounding. Array comparison supplements the official checks.

## Fair comparisons

Start a fresh Python process, use the same environment and CPU affinity, and retain double precision. The initial worker uses CPU 2 and runs serially. Keep exploratory concurrent timings separate from final sequential comparisons. Changes that interact must be evaluated again after integration rather than combining their individual speedup percentages.

The initial agent session has a limit of four distinct candidate revisions or one hour, whichever is reached first. Repeated evaluations of the same revision do not create a new candidate. Finish by writing a handoff and preserving the session so it can be resumed explicitly.
