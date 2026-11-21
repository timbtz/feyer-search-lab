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
| Official checks passed | Unchanged official full benchmark passed for that exact commit |
| Validated for automatic promotion | Official checks and the team's additional strict saved-array regression check both passed |
| Numerical review needed | Official checks passed, but the additional strict regression check failed |
| Confirmed improvement | Repeated full runs under matching conditions show a reproducible improvement over the baseline |

A failed or incomplete candidate cannot enter the internally validated ranking. An official pass with a strict-only failure is a reviewable idea, not an official disqualification. Screening helps allocate evaluation time; it is not the final correctness gate. A reduced smoke test, if added, is only a debugging result.

For numerical changes, compare the saved carrier, signal, noise, sensitivity, powers and full-gradient arrays against the baseline; parameters and frequencies must match exactly. Loss is checked for finiteness by the official harness and recorded in JSON, but is not one of its saved NPZ arrays. Record failing entries and error/tolerance ratios, not only global error norms. Do not assume a linear algebra rewrite changes results only by harmless rounding. The current mixed-unit gradient tolerance is a conservative regression policy, not an independently calibrated numerical error bound. Substantial solver or derivative rewrites need independent, parameter-scaled derivative diagnostics before endorsement.

The official full harness validates and saves the last warm repetition's outputs; screening validates its first-run outputs. Preserve this distinction when describing validation coverage. Never edit the canonical benchmark to change it.

## Fair comparisons

Start a fresh Python process, use the same environment and CPU affinity, and retain double precision. The initial worker uses CPU 2 and runs serially. Keep exploratory concurrent timings separate from final sequential comparisons. Changes that interact must be evaluated again after integration rather than combining their individual speedup percentages.

Both screening and full evaluation use a 32,000,000,000-byte monitored process-group RSS budget. This conservative interpretation of 32 GB is a watchdog and post-run rejection rule, not a kernel cgroup cap: the AMD container's cgroup mount is read-only. Record the enforcement mode and actual peaks. Do not claim strict hardware equivalence with the final Intel machine. The whole instance remains at its 55 GiB system-RAM allocation; the GPU's approximately 48 GB VRAM is separate and not consumed by this CPU budget.

The agent session has no candidate-count limit. Its existing one-hour deadline remains in force. Repeated evaluations of the same revision do not create a new candidate. Finish by writing a handoff and preserving the session so it can be resumed explicitly.
