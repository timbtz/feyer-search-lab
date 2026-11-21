# Faster Physics — START Hack Munich 2026

Make **Differometor** faster while preserving its physical predictions and gradients.

## Team optimization lab

To clone the **complete team setup**, including the simulator, official benchmark,
serial evaluator and shared search workflow:

```bash
git clone https://github.com/timbtz/feyer-search-lab.git
cd feyer-search-lab
```

Follow the [three-instance team workflow](.wiki/team-search.md) and
[new AMD instance setup](.wiki/portable-amd.md). Each teammate uses their own local
Claude/Codex account and evaluator; Qwen and SMAC are optional. The
[shared GitHub queue](https://github.com/timbtz/feyer-search-lab/tree/control/team-search)
tracks task ownership, exact candidates, evidence, stalled directions and combinations.
The [lab documentation](.wiki/README.md) covers existing automated controllers.
The original challenge instructions follow below.

This repository includes the public simulator source, example data, [challenge PDF](challenge.pdf), [judging criteria PDF](judging-criteria.pdf), [editable brief](challenge.docx), a short [start-here example](start_here.py), and a [full benchmark](benchmark.py). No separate simulator checkout or GPU is required.

## Start here

Use **Python 3.12 on Linux or WSL2**, with **32 GB RAM recommended**. Clone the repository:

```bash
git clone https://github.com/feyerlabs/start-hack-munich-2026.git
cd start-hack-munich-2026
```

Alternatively, [download the ZIP](https://github.com/feyerlabs/start-hack-munich-2026/archive/refs/heads/main.zip), unpack it and open a terminal in its root folder. Then install and run:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python start_here.py
```

[`start_here.py`](start_here.py) walks through one complete simulation and gradient calculation in five steps. It prints setup time, compilation time, and combined simulation/sensitivity/gradient runtime. It runs once using the CPUs available to the process.

For reproducible measurements, numerical checks and the five-bar plot, use the full benchmark:

```bash
python benchmark.py --cpus 1 --output benchmark-baseline.json
```

`--cpus 1` pins the process to one logical CPU on Linux/WSL. The full benchmark takes roughly 5 minutes for ten repetitions and validation, prints `PASS`, and writes `benchmark-baseline.json` and `benchmark-baseline.png`. Use `--repeats 3` for a shorter run or `--save-arrays baseline.npz` to save outputs. The measured peak memory was about 14.4 GiB.

## If setup fails

- **Python missing:** install Python 3.12 first. On Debian/Ubuntu, the matching `python3.12-venv` package may also be needed for virtual environments.
- **Windows:** use WSL2 and make enough RAM available to it. The single-CPU command uses Linux process affinity.
- **Process killed / out of memory:** close other memory-heavy applications or use a machine with more available RAM. Reducing `--repeats` shortens the run but does not reduce peak memory.
- **Numerical check fails:** restore the unchanged public fixtures and run the unmodified baseline with the pinned dependencies before investigating your changes.

## The workload

One complete saved 3×3 optical setup, all **101 frequencies from 800–3000 Hz**, and gradients for **193 physical design variables**. Every evaluation computes carrier fields, signal, quantum noise, detector sensitivity, powers and the gradient of mean log sensitivity relative to the public reference.

In `benchmark.py`, the complete first-run total includes input preparation, all compilation, the forward simulation, sensitivity and gradients. Imports, CPU initialization and result transfer are included. Validation and benchmark logging/report/plot generation are excluded. There is no optimization loop.

The benchmark’s five bars group the detailed measurements without dropping work. Setup includes imports, initialization and loading/building inputs. Compilation combines lowering and compilation for all stages. Sensitivity includes readout and host transfer. The raw JSON retains every stage and all warm repetitions.

## Improve and compare

1. Run the unmodified baseline in a fresh Python process.
2. Use the phase plot to find a bottleneck, then edit `differometor/`.
3. Run `python benchmark.py --cpus 1 --output benchmark-candidate.json`.
4. Compare complete time, including compilation, on matching hardware, CPU affinity and software. Report median warm runtime separately and repeat measurements to assess variability.

Keep the setup, every frequency, double precision, physical outputs and gradients. The full benchmark runs the quick correctness checks described below. Precomputed answers and omitted calculations do not count.

Submit your code, before/after JSON reports and plots, and reproduction commands. A short note on your approach and correctness checks is welcome.

## Judging and prizes

Download the standalone [Judging Criteria PDF](judging-criteria.pdf), including timing rules and correctness checks.

- **First prize:** Lowest complete evaluation time among correct submissions.
- **Second prize:** Second-lowest complete evaluation time among correct submissions.
- **Special prize:** The most surprising solution, chosen by the Feyer team.

The speed prizes use the **complete first-run benchmark total** on matching hardware and CPU limits. Include imports, initialization, input preparation, all compilation, forward simulation, sensitivity, gradients and result transfer. Validation and benchmark reporting remain outside the timer; warm runtime is reported separately.

AI coding tools are welcome. A high-level explanation of your approach, why it helps and what you learned is encouraged and helps the Feyer team understand your work.

## Correctness: quick checks

A correct submission evaluates the complete setup with all **101 frequencies**, all **193 design variables** and double precision. It preserves the physical results and gradients.

The supplied checks require:

- **Correct sensitivities:** positive sensitivity at every frequency, matching the public reference with `abs(log(sensitivity) - log(reference)) <= 1e-5` (natural logarithm; about 0.001% relative difference).
- **Finite results:** carrier, signal, noise, sensitivity, powers, loss and all 193 gradient values contain no NaN or infinity; the gradient is not identically zero.
- **Consistent gradients:** gradients should pass the supplied sanity check.

Run a shorter check with:

```bash
python benchmark.py --cpus 1 --repeats 3 --output benchmark-check.json
```

A successful run prints `PASS`. These quick checks cover the supplied workload and run outside the scored time. For larger numerical changes, comparing saved arrays or trying another public setup is helpful.

## CPU baseline

Tested on **16 November 2026** on an **Intel Xeon Platinum 8468**, pinned to **one logical CPU** with **32 GB RAM** allocated. CPU affinity and numerical-library thread limits are recorded in the [raw report](benchmarks/cpu-baseline.json). No GPU was used.

![Time per phase](benchmarks/cpu-baseline.png)

| Measurement | Seconds |
| --- | ---: |
| Complete first-run total, including compilation | **44.204** |
| Total tracing/lowering and compilation | 22.918 |
| Median warm evaluation, ten repetitions | **17.679** |
| Warm minimum / maximum | 17.118 / 18.282 |

All 101 frequencies and 193 gradients were evaluated. The public sensitivity test and two-step numerical gradient check passed. This was measured on a shared worker, so record your own baseline. The full benchmark adds archive support and output-path checks to the measured version; its numerical workload is unchanged. The short starter compiles simulation and differentiation together, so its timings are not directly comparable to this staged benchmark.

Replot any saved report without running the simulation:

```bash
python plot_timings.py benchmark-baseline.json --output benchmark-baseline.png
```

## Public source and license

The simulator is the unmodified public [Artificial Scientist Lab Differometor](https://github.com/artificial-scientist-lab/Differometor) at commit `b0dc7c79e7c72a1b010174f6bdcad01efa51d6ff`. This repository adds the Feyer hackathon brief and benchmarking tools. The full upstream instructions remain in [README.upstream.md](README.upstream.md); the upstream [MIT license](LICENSE) is retained.

[UPSTREAM.json](UPSTREAM.json) records the original simulator and fixture hashes.
