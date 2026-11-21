# Generalization to other optical setups

The challenge repository clarified on 21 November 2026 ([upstream commit `2bb437a`](https://github.com/feyerlabs/start-hack-munich-2026/commit/2bb437a223)) that **final evaluation uses a different optical setup, a slight variation of the supplied example**. The prizes rank the complete first-run total on that final setup. In the challenge talk the organizers described the final test as "a random setup with random parameters". The `*_randparams` cases follow upstream's own protocol (`examples/uifo_optimization.py`): `setups.uifo(size=3, random=True, random_seed=…)`, with each optimized property uniform in `db [0, 10]`, `angle/tuning [-360, 360]`, `power [0, 200]`, `mass [0.01, 200]`, `length [0.1, 4000]` and `reflectivity [0, 1]`. A candidate that is fast only on `uifo_800_3000.json`, or that relies on its sizes, detector count, frequency count or index layout, may fail or lose its gain at judging.

The queue evaluator still runs only the supplied development benchmark. `lab.gencheck` adds a separate cross-setup comparison against the unchanged simulator. It is evidence for review, not a replacement for the official or strict queue checks.

## Cases

| Case | What varies |
| --- | --- |
| `dev` | Supplied example, public frequencies and reference sensitivity |
| `dev_perturbed` | Same topology; reflectivity, tuning, length and power values perturbed (seed 7) |
| `uifo_20_5000` | Different saved 3×3 UIFO: balanced homodyne (two detector ports), 192 variables, 100 log-spaced frequencies |
| `uifo_rand1`–`3` | Randomly generated 3×3 UIFOs (`setups.uifo(3, random=True, random_seed=s)`), different centers and boundaries |
| `voyager`, `aligo` | Different published detector topologies, 45 and 29 variables |
| `dev_randparams` | Supplied topology; every optimized property drawn uniformly from upstream `property_bounds` |
| `uifo_randparams1`–`3` | Random 3×3 UIFO topology (seeds 101–103) **and** uniform random parameters, the upstream random-design protocol |
| `uifo_amod1`, `uifo_fmod1` (opt-in via `--cases`) | Random UIFO in amplitude- and frequency-modulation mode with random parameters. They exercise the laser modulation functions the supplied example never uses |

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

The sparse path needs review before it can be the final submission. Without refinement, it misses the official sensitivity bound against the unchanged simulator on voyager and `uifo_20_5000`. Iterative refinement (`4af20b7`) repairs both to ~1e-11, and the supplied and perturbed examples stay at ≤ 6.7e-8. Two random UIFOs still differ from the unchanged simulator above 1e-5 in log sensitivity, even though carrier, signal and noise agree to about 1e-10 relative to their largest entries. The disagreement sits in small-magnitude frequencies. The branch notes (`experiments/notes/claude-sparse-adjoint.md` on `explore/claude-sparse-adjoint`) arbitrate these cases with x86 extended-precision iterative refinement as a truth proxy. Against that reference, the detected signal's relative error is:

| Setup | Unchanged dense | Plain SuperLU | SuperLU + refinement |
| --- | ---: | ---: | ---: |
| `uifo_rand1` | **2.6e-4** | 6.6e-5 | 9.1e-11 |
| `uifo_rand3` | **3.8e-5** | 2.0e-8 | 2.5e-8 |

On these two setups the unchanged simulator is the inaccurate side. On the dev fixture its signal solve is also the less accurate one (strict-style error 2.34 against 0.005 for refined SuperLU). The risk for judging remains. Feyer compares against its own reference for the final setup, which was probably produced with the dense code. A badly conditioned final setup could therefore reject a more accurate result. The supplied and perturbed examples, the closest analogues of a "slight variation", agree with the unchanged simulator to ≤ 6.7e-8.

## Final candidate and reference reproducibility, 22 November 2026

`53f38d3` (host pass + package XLA flags, `explore/claude-host-assembly`) against the unchanged simulator, AMD CPU 101:
- **Held:** 12 of 14 cases. Every random-parameter case agrees to ≤ 4.2e-7 in log sensitivity, and both modulation modes agree to ≤ 5.2e-14.
- **Speed:** first run without imports drops from about 34 s to 0.3–0.7 s per setup.
- **Flagged:** only `uifo_rand1` and `uifo_rand3`, as before.

**Is the reference itself reproducible?** We reran the unchanged simulator with `OPENBLAS_CORETYPE=HASWELL`. That is a different, legitimate OpenBLAS kernel path; the default on this AMD EPYC is SkylakeX. The bundled OpenBLAS has no Sapphire Rapids kernel, so Feyer's Intel Xeon 8468 very likely uses SkylakeX as well. Maximum |Δ log S|:

| Setup | Unchanged vs unchanged (Haswell kernels) | `53f38d3` vs unchanged |
| --- | ---: | ---: |
| `dev` | 5.8e-8 | 6.8e-8 |
| `dev_randparams` | 1.1e-7 | 5.1e-8 |
| `uifo_randparams1` / `2` / `3` | 4.5e-8 / 5.4e-7 / 7.8e-8 | 3.0e-8 / 4.2e-7 / 3.6e-8 |
| `uifo_rand1` | **3.1e-4** | 2.0e-4 |
| `uifo_rand3` | **6.8e-5** | 5.8e-5 |

The candidate's deviation never exceeds the unchanged simulator's own variation under a different BLAS kernel path. On `uifo_rand1` and `uifo_rand3`, the original Differometor fails the 1e-5 check against itself. A reference computed there is not reproducible across machines, for any submission.
