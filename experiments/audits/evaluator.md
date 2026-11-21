# Evaluator and hardware integrity audit

Audited 21 November 2026. No simulator, canonical benchmark or baseline artifact was changed. Inspection included local source, the deployed release, saved reports, container limits and focused unit tests. No new physics benchmark was launched by this subagent.

## Verified evidence

- Deployed release before audit changes: `/workspace/feyer-lab/releases/0c011fbbff6edb4ca095f12b5c762652da788f73`.
- Deployed worker SHA256 `38f7af8ff487cbbbe01939c8eb3f926b2c08eec687984dd2f99977d2de359c04` matched the pre-audit local worker.
- Deployed screening SHA256 `5cb1e5b8013dde1249845e3d6ce24b1f85240a0fb14b5cb966340188559c390a` matched the pre-audit local screen.
- Canonical benchmark SHA256 `d5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e` matched the pristine remote benchmark and remains unchanged.
- CPU quota: `cpu.max = 1600000 100000`, equivalent to 16 CPUs for the whole instance; cpuset `0-127`. Each benchmark command adds `taskset -c 2` and `--cpus 1`. Report affinity `[2]` is checked.
- Shared container RAM: `memory.max = 59055800320`, exactly 55 GiB; `memory.swap.max = 0`. This is not a 32 GB per-evaluation allocation. GPU VRAM is separate.
- The source protects canonical benchmark, plotting harness, public input data and package configuration by comparing their trees against the challenge baseline. Each queued job has a pinned Git reference and a detached, clean checkout.
- Serial queue claims use SQLite transactions. The worker holds an exclusive flock and passes its descriptor into the benchmark process. Timeouts terminate the process group, including descendants; heartbeat updates happen while the child runs.

## Screen versus full

The screening code uses the same complete setup, 101 frequencies, 193 variables and three staged JIT phases. It retains all first-run timings and uses `jax.block_until_ready` in each timed stage. Its small extra argument parser is inside import timing, so screening and full imports are not byte-for-byte identical instrumentation; full remains authoritative for scoring.

Screen omits warm repetitions, finite-difference spot checks and plot generation. Those omissions do not remove physics from the first evaluation. The previous screening log incorrectly claimed finite-difference validation; this has been corrected, without changing numerical operations. New screening SHA256: `2bf4249e453271d1f665c35356485739ad66a9b0327153d678a5b34d81192458`.

One important upstream distinction: `benchmark.py:222-239` overwrites the stored `host` outputs during each warm repeat. Its correctness checks and saved NPZ therefore refer to the **last warm evaluation**, while the score refers to the **first evaluation**. Screening checks and saves its first evaluation. Deterministic, pure implementations should agree; a substantial rewrite should compare screen-first and full-last arrays explicitly rather than assuming the full saved archive independently certifies first-run outputs. Canonical code was not modified to change this behavior.

## Concrete gaps found and fixed

The pre-audit `_validate_report` accepted in-memory copies of a real candidate report with a wrong source commit/dirty checkout, library thread limits changed to 16, or an invented 0.001-second total inconsistent with its phases. These were report-integrity gaps, not evidence that previous candidates exploited them.

Changes in `lab/worker.py` now require:

- Correct profile/benchmark identifier, submitted source SHA, clean source state and matching executed evaluator digest.
- Canonical input hashes, complete variable/frequency counts, expected physical output/gradient shapes and double-precision physical types.
- CPU backend, CPU 2 affinity, exactly one requested/effective CPU, thread limits of one, Python 3.12, no XLA flags and no persistent cache.
- Exactly the 14 expected first-run phases, with correct categories, finite nonnegative times and totals that match the phase sums.
- Finite validation scalars, nonzero gradient norm and sensitivity error within the public tolerance.
- Explicit `official_passed` and `regression_passed` fields. An official pass with a numerical disagreement gets `official_pass_numerical_review_needed`; the queue remains failed under the conservative promotion policy. Checker crashes/missing reports get `official_pass_regression_check_error`, distinct from demonstrated numerical disagreement. A claimed successful checker exit requires an affirmative comparison report.
- Resource limits, effective execution configuration, worker/evaluator/references hashes and validated-output scope in result metadata. Inherited `JAX_*`/`XLA_*` overrides are cleared before setting the canonical CPU/x64/no-cache environment.

## Requested 32 GB envelope

The README describes 32 GB as recommended/reference hardware, not an explicit rejection threshold. The user has now requested matching that envelope for local evaluations. Root independently established that the cgroup mount is read-only, so a true delegated per-job cgroup cannot be created from this instance.

Integrated root's `MemoryMonitor` into both screen/full execution and the comparison process. Default is **32,000,000,000 bytes** (decimal 32 GB, conservatively below 32 GiB). It samples process-group RSS at each worker poll, terminates the group when over budget, and labels the result `resource_budget_exceeded`. A GNU-time peak over budget also causes rejection after a completed benchmark. The overall instance/GPU allocation is unchanged.

This is explicitly a **sampled RSS watchdog, not a kernel memory cap**. It can miss brief peaks; summing RSS can double-count shared pages; it neither reserves memory nor prevents contention from other instance work. Result metadata records these limits honestly. Kernel-enforced matching requires host/container delegation from the provider. Confirm whether final judging uses decimal GB or GiB; the current choice is conservative.

## Remaining design limits

- The evaluator is a cooperative development harness, not an adversarial sandbox. Candidate Python runs as the same root user and can technically alter files, imports or process state. Protected-path checks and report consistency improve error detection but do not make untrusted code safe. Manual agents must follow the same code scope as supervised agents; a future multi-tenant service should use an unprivileged user, read-only evaluator mounts, isolated dependencies and process/cgroup containment.
- Shared venv dependencies are recorded but not independently pinned by the worker against an immutable environment manifest. Current rules prohibit changing them, and the reporting layer compares package identities. If dependencies change, rerun matching baselines and separate the results; avoid silent cross-environment rankings.
- `/usr/bin/time` peak RSS is not a complete synchronized sum of all descendant resident memory. The new process-group monitor supplements it but remains sampled.
- Full validation's public gradient spot check is narrow. Independent numerical tests for solver rewrites remain a separate correctness task.
- First-run improvements require repeated fresh processes on the same settings. Warm repetitions do not establish compilation-time variability or Intel-versus-AMD equivalence.

## Validation performed

- All **17 worker tests** passed, covering source/evaluator mismatch, thread drift, invalid/duplicate/missing phases, inconsistent totals, changed workload/precision, real process-group timeouts, numerical-review verdicts, inherited environment cleanup, sampled memory termination and high GNU-time peak rejection.
- New schema successfully accepted all **24 existing complete candidate/calibration reports** available at audit time and all **3 original baseline reports**. This guards against accidental rejection of valid canonical output.
- `git diff --check` passed for owned files. Root owns full-suite verification, deployment and paired confirmation runs.
