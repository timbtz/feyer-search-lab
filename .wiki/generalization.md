# Generalization to other optical setups

The challenge repository clarified on 21 November 2026 ([upstream commit `2bb437a`](https://github.com/feyerlabs/start-hack-munich-2026/commit/2bb437a223)) that **final evaluation uses a different optical setup, a slight variation of the supplied example**. The prizes rank the complete first-run total on that final setup. A candidate that is fast only on `uifo_800_3000.json`, or that relies on its sizes, detector count, frequency count or index layout, may fail or lose its gain at judging.

The queue evaluator still runs only the supplied development benchmark. `lab.gencheck` adds a separate cross-setup comparison against the unchanged simulator. It is evidence for review, not a replacement for the official or strict queue checks.

## Cases

| Case | What varies |
| --- | --- |
| `dev` | Supplied example, public frequencies and reference sensitivity |
| `dev_perturbed` | Same topology; reflectivity, tuning, length and power values perturbed (seed 7) |
| `uifo_20_5000` | Different saved 3×3 UIFO: balanced homodyne (two detector ports), 192 variables, 100 log-spaced frequencies |
| `uifo_rand1`–`3` | Randomly generated 3×3 UIFOs (`setups.uifo(3, random=True, random_seed=s)`), different centers and boundaries |
| `voyager`, `aligo` | Different published detector topologies, 45 and 29 variables |

Each case runs the benchmark's three stages: `jit(vjp(simulate))`, `jit(vjp(readout))` and `jit(backward)`. It records carrier, signal, noise, sensitivity, powers, loss, gradient and per-stage timings.

A case **holds** when all outputs and gradients are finite, max |Δ log sensitivity| ≤ 1e-5 (the official bound) and gradient relative L2 ≤ 1e-4 against the unchanged simulator. This gradient bound is intentionally looser than the team's strict 1e-7 saved-array check. A solver with different pivoting can differ at ~1e-7 because the dev signal matrix has a condition number near 1e30. Report the actual magnitudes. Do not weaken either queue check.

## Run

The script is standalone so it can be copied to an evaluator host. Use a CPU outside the evaluator lanes (2 and 34) and run one heavy process at a time. The unchanged simulator peaks near 14 GiB.

```bash
scp lab/gencheck.py amd-hackathon:/tmp/claude-gencheck/gencheck.py
ssh amd-hackathon
cd /tmp/claude-gencheck
PY=/workspace/venv-feyer/bin/python
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 taskset -c 101 $PY -u gencheck.py run \
  --tree /workspace/feyer-pristine --out pristine.npz          # once per reference
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 taskset -c 101 $PY -u gencheck.py run \
  --tree /path/to/candidate-tree --out candidate.npz           # tree holds differometor/ and examples/data/
$PY gencheck.py compare pristine.npz candidate.npz
$PY gencheck.py report pristine.npz candidate.npz --sha FULL_SHA --label 'short description' \
  --branch explore/... --cpu 101 --output report.json
```

Copy `report.json` to `.lab/generalization/report.json` in the main checkout. The live dashboard's **Other setups** tab reads it read-only. `report` replaces an existing record for the same SHA. Timings in these records are exploratory development measurements without imports on a non-evaluator CPU. They are not scored queue results.

## Results, 21 November 2026

AMD EPYC 9334, CPU 101, against the unchanged source `02ec741` (`/workspace/feyer-pristine`). Snapshot: [`experiments/generalization/2026-11-21.json`](../experiments/generalization/2026-11-21.json).

| Candidate | Setups held | Outputs | Worst gradient Δ | Speedup per setup |
| --- | ---: | --- | --- | --- |
| `3b80507` dense slot pruning | 8/8 | bitwise identical | 1.1e-12 normalized (`uifo_rand3`) | 41–59% |
| `aac9904` dense row-split pruning | 8/8 | bitwise identical | 1.1e-12 normalized (`uifo_rand3`) | 46–64% |
| `0dea4ec` sparse SuperLU, no refinement | 4/8 | max \|Δ log S\| 3.4e-3 (voyager), 2.8e-5 (`uifo_20_5000`) | 5.2e-3 normalized (voyager) | 62–79% |
| `4af20b7` sparse SuperLU + iterative refinement | 6/8 | ≤ 6.7e-8 on held setups; 2.0e-4 (`uifo_rand1`), 5.8e-5 (`uifo_rand3`) | 1.5e-5 rel. L2 (`uifo_rand3`) | 61–78% |

Both dense-path candidates carry their speedup to every tested setup without changing physical outputs.

The sparse path needs review before it can be the final submission. Without refinement, it misses the official sensitivity bound against the unchanged simulator on voyager and `uifo_20_5000`. Iterative refinement (`4af20b7`) repairs both to ~1e-11, and the supplied and perturbed examples stay at ≤ 6.7e-8. Two random UIFOs still differ from the unchanged simulator above 1e-5 in log sensitivity, even though carrier, signal and noise agree to about 1e-10 relative to their largest entries. The disagreement sits in small-magnitude frequencies. The branch notes report an extended-precision arbitration on the dev fixture where the unchanged dense solve is the less accurate one. That arbitration has not yet been done for `uifo_rand1` and `uifo_rand3`. Final judging compares against Feyer's own reference for the final setup. Matching that reference matters more than being closer to an exact solution.
