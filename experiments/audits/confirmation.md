# Fresh-process confirmation study

Candidate: `1e552d675c3795265be8af1ac23ffb61f90f30b1` (candidate-08).

Three alternating baseline/candidate pairs, using the unchanged official benchmark, one logical CPU (CPU 2), fixed Python/JAX environment, and a 32,000,000,000-byte sampled RSS budget. Each job starts a new Python process; the worker runs serially.

| Pair | Baseline seconds | Candidate seconds | Reduction | Official + strict checks |
| --- | ---: | ---: | ---: | --- |
| 1 | 35.720092 | 28.093522 | 21.35% | PASS / PASS |
| 2 | 35.946923 | 28.040049 | 22.00% | PASS / PASS |
| 3 | 35.638327 | 28.574264 | 19.82% | PASS / PASS |

Median complete first-run time: **35.720092 → 28.093522 seconds**, a **21.35% reduction**.

## Phase medians

| First-run phase group | Baseline seconds | Candidate seconds |
| --- | ---: | ---: |
| setup | 1.031184 | 1.032353 |
| compilation | 19.630032 | 12.777620 |
| forward | 12.119104 | 12.399473 |
| sensitivity | 0.000880 | 0.000918 |
| gradient | 2.956292 | 1.882860 |
| transfer | 0.000373 | 0.000406 |
| total | 35.720092 | 28.093522 |

Phase medians are calculated separately and need not sum to the median total.

This is not a strict Pareto improvement across all phase groups: median forward execution increased by about 0.28 seconds. Compilation and gradient savings more than compensate in the complete first-run score.

## Memory evidence

- baseline: sampled process-group RSS peaks **15.509–15.524 GB**.
- candidate: sampled process-group RSS peaks **13.755–13.768 GB**.

The watchdog observes process-group RSS and rejects over-budget jobs. It is not a cgroup cap and can miss brief peaks; the container itself remains at 55 GiB system RAM. GPU VRAM is separate.

All six jobs used the same worker process and matching environment/timing signatures. The canonical benchmark hash is unchanged.

## Reproduction and evidence

Run the same baseline SHA and candidate SHA through `lab.client submit --profile full`, using a fresh request ID for each independent measurement. Alternate baseline/candidate order across pairs, preserve CPU/environment/resource policy, and compare `timing_seconds.end_to_end`; do not substitute warm medians.

[Machine-readable study, exact job IDs and resource observations](confirmation.json). Raw run artifacts remain at `/workspace/feyer-lab/runs/JOB_ID/` and can be fetched with `python3 -m lab.client fetch JOB_ID`.

Three pairs on one shared AMD instance, not an Intel result or formal confidence interval.
Each score starts a fresh Python process with persistent compilation cache disabled; OS file caches are not flushed.
RSS monitoring is not a kernel memory cap. Full validation checks last-warm outputs; separate first-versus-warm checks cover candidate8.
