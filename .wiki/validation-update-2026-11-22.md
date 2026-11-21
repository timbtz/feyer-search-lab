# Validation update after organizer clarification

The user supplied the organizers' Discord answers and asked to stop managed Claude
headless sessions to free compute. At inspection all six managed Claude sessions
were complete and no Claude headless process was running locally, on AMD, or on
the Hetzner broker. Interactive terminals, saved edits and unrelated running
benchmarks were preserved. No Claude session may resume without a new instruction.

## Challenge contract

- Final evaluation uses **one logical CPU**. Compilation, imports, initialization,
  preparation, forward simulation, sensitivity, gradients and transfer count in
  the complete first run. Warm execution alone is not the objective.
- Use a pristine baseline on the same machine, affinity and environment; an AMD
  time cannot be compared directly with the published Intel baseline.
- Implementations outside JAX, including SciPy callbacks and handwritten reverse
  derivatives, are allowed when inputs, physical outputs and gradients agree.
  Forward mode, Hessians and GPU support are useful compatibility diagnostics,
  not newly invented mandatory challenge gates.
- Package-level compiler settings are allowed when correctness and transfer hold.
  The existing queue's no-XLA-flags policy remains unchanged for historical cohort
  consistency. New support checks record flags and use a distinct policy; they
  do not relabel an old infrastructure rejection as a numerical failure.
- Improvements must transfer to other optical setups. The new aLIGO benchmark is
  a transfer example, not the final judged setup, which is similar to the large one.
- Keep the original full workload and precision. A faster reduced-frequency test
  cannot satisfy either official benchmark.

## Official aLIGO is different from our custom aligo probe

The upstream release is pinned to
[`83f8d2f40fc75218a1d8ec7908cc0bf1c8f99a75`](https://github.com/feyerlabs/start-hack-munich-2026/commit/83f8d2f40fc75218a1d8ec7908cc0bf1c8f99a75).
The unchanged entrypoint, shared benchmark and plot script are vendored under
`experiments/vendor/official-transfer`, with SHA-256 manifest verification.

| Test | Frequencies | Variables | Public log-sensitivity tolerance |
|---|---:|---:|---:|
| Official large grid | 101 | 193 | 1e-5 |
| Official aLIGO | 101 | 29 | **1e-6** |
| Existing custom `gencheck` aligo | 100 | 29 | 1e-5 against a fresh baseline |

Both official tests include their own finite-difference gradient sanity check.
The wrapper verifies the exact setup/reference hashes, source commit, harness
hashes, all fourteen phases and their totals, one CPU, numerical thread limits,
double precision, nonzero finite gradient and disabled persistent cache.
It then compares every saved physical output and all gradients elementwise to
the matched pristine result, using the unchanged internal `rtol=1e-7` plus
`1e-12 * max(abs(reference))` scale floor. Input arrays must match exactly.
This strict comparison is additional review evidence, not an organizer mandate
for that exact tolerance. Official PASS and strict agreement remain separate.

## Audit findings in the earlier custom comparison

`gencheck.compare_cases` printed physical-output error magnitudes but did not use
them in acceptance. It omitted loss from the finiteness gate, accepted gradients
by relative L2 only, did not enforce dtype or identical parameter/frequency
arrays, and could leave a missing reference outside the aggregate failure result.
An empty suite could therefore be reported OK. These are acceptance gaps, not
evidence that every prior numerical result was wrong.

`lab.transfer_validation` provides a separate fail-closed re-audit. It requires
an explicit case list, complete reference and candidate arrays, no recorded
execution errors, identical inputs/shapes/double precision, finite outputs and
loss, positive sensitivity and nonzero gradients. Elementwise comparison prevents
a large gradient coordinate from hiding an incorrect small coordinate. Historical
reports remain untouched. Unknown/missing cases cannot count as passed.

```bash
python -m lab.transfer_validation \
  --reference pristine.npz --candidate candidate.npz \
  --cases dev,dev_perturbed,uifo_20_5000,uifo_rand1,uifo_rand2,uifo_rand3,voyager,aligo,dev_randparams,uifo_randparams1,uifo_randparams2,uifo_randparams3 \
  --output strict-transfer-audit.json
```

## Bounded official support run

Only an operator runs this, using a committed isolated runtime and the existing
fixed Python. It locks **both existing evaluator queues**, requires both drained,
and refuses insufficient cgroup memory headroom. It never kills an evaluator or
changes a queue, dependencies, source branch, affinity policy or worker release.
One fresh process runs at a time on CPU2, with a sampled 16GB RSS guard and a
900-second overall execution budget (maximum accepted budget 1200 seconds).
Sampled RSS is not a kernel hard cap. Other user workloads may still cause
contention, so all support timings are explicitly nonranking.

```bash
/workspace/venv-feyer/bin/python -m lab.transfer_run \
  --mirror /workspace/feyer-lab/repo.git \
  --candidate EXACT_COMMIT_SHA \
  --lock-state /workspace/feyer-lab/state \
  --lock-state /workspace/feyer-lab-lane1/state \
  --output /workspace/feyer-transfer/RUN_ID
```

The run produces four reports: pristine and candidate on large grid and aLIGO.
Each starts a fresh Python process; no warmup or compilation occurs before its
official import timer. All reports, logs, arrays, source checkouts and the durable
receipt are retained. A blocked reservation returns failure instead of bypassing
an active job. This is a separate validation path, not an automatic search worker.

## Remaining limits

Two public setups and a finite collection of random cases cannot prove universal
correctness. Keep the broader UIFO perturbation/topology/parameter suite, and
investigate ill-conditioned disagreements independently rather than loosening
tolerances. The official saved arrays validate the last warm evaluation; separate
checks would be needed to prove every intermediate or first-run output. Package
compiler choices must remain visible in candidate source and results. This update
does not authorize caching answers, omitting compilation from totals, or changing
the physical workload.
