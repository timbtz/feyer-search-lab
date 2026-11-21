# Machine and baseline

Three unchanged official baseline runs passed on the AMD instance on 21 November 2026. Each run used one logical CPU, all 101 frequencies, all 193 design variables and three warm repetitions. The first-run totals differ by 0.581% of their median.

## Machine

| Resource | Observed allocation or configuration |
| --- | --- |
| CPU | AMD EPYC 9334 host; container CPU quota equivalent to 16 CPUs |
| Evaluation affinity | Logical CPU 2 |
| System RAM limit | 55 GiB |
| GPU | One AMD Radeon Pro W7900D, approximately 48 GiB VRAM |
| Python | 3.12.15 |
| Persistent directory | `/workspace` |
| Python environment | `/workspace/venv-feyer` |
| Baseline source | `/workspace/feyer-pristine` |
| Separate working copy | `/workspace/work` |

The host exposes 128 logical CPUs and much more RAM to some system tools. Those values are not the instance's allocated budget. The challenge benchmark uses the CPU; the Radeon GPU is available for separate work.

## Results

| Run | Complete first-run total | Median warm evaluation |
| --- | ---: | ---: |
| 1 | 35.821919 s | 15.734179 s |
| 2 | 35.614326 s | 15.635303 s |
| 3 | 35.737065 s | 15.489660 s |

The median complete first-run total is **35.737065 s**. All three runs passed the reference-sensitivity and numerical-gradient checks. Their source was upstream commit `02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f`.

The measured first-run total includes imports, initialization, input preparation, tracing/lowering and compilation, forward simulation, sensitivity, gradients and result transfer. Warm repetitions, validation and reporting are outside that total. The entire benchmark process consequently takes longer than the first-run score.

## Evidence

Remote baseline reports and artifacts are `/workspace/feyer-pristine/base1.*`, `base2.*` and `base3.*`. Never overwrite or edit them. Machine and environment records are under `/workspace`, including `machine-info.txt`, `baseline-environment.txt`, `baseline-commit.txt` and `baseline-summary.json`.

A local copy of reports, plots and logs is in `/Users/t.betz/tmp/amd-hackathon-results`. The original saved arrays remain in the remote baseline directory. Keep an independent copy of valuable artifacts before deleting or replacing the instance.

## Memory interpretation

The upstream README reports roughly **14.4 GiB peak RAM** for its reference benchmark. That is temporary system memory during computation, not the input size, repository size or GPU VRAM use. Peak RAM for the AMD runs has not yet been measured. The new evaluator should record peak resident memory for future runs before increasing concurrency.

The reference workload is one fixed optical setup evaluated at all 101 frequencies, including the gradient for all 193 physical design variables. Removing warm repetitions reduces total evaluation time but need not reduce peak memory. A different algorithm may use more or less memory.

## Queue calibration

The first end-to-end screening job used unchanged simulator code at commit `0c011fbbff6edb4ca095f12b5c762652da788f73`. Job `69624b40ab5e4add8480a9af84e90092` passed the screening checks: 36.177949 seconds measured first evaluation, 37.529310 seconds process wall time, and 15,134,648 KiB peak RSS (14.43 GiB). The independent finite-difference check was explicitly not run in this screening profile.

The memory figure above is measured on this AMD instance. The earlier 14.4 GiB figure in the challenge README described its reference run.

The full queue calibration job `f668a9b0ab2c44c791aff3f0b9ccdeb1` passed both the official checks and the stricter saved-array comparison. Its first evaluation was 36.331948 seconds, total benchmark process wall time 126.070111 seconds, and peak RSS 14.4464 GiB. The screening process completed in about 30% of that wall time. This comparison uses unchanged simulator code and the same CPU and environment.

Single candidate timings are preliminary measurements. Small differences near the observed noise level require repeated fresh-process runs before claiming a speedup. A validated candidate has passed the checks; that label alone does not establish a repeatable performance gain.
