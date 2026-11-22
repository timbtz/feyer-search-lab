# Validation update after organizer clarification

**Latest target is the fast `53f38d3`, not a fallback to dense `aac9904`.** The
[final verification packet](../experiments/audits/2026-11-22-fastest/README.md)
contains three fresh official passes on each public benchmark, the 14-case rerun,
all-coordinate gradient diagnostics and independent precision investigation.
Large/aLIGO medians are 0.987/0.626 seconds on one CPU including compilation.
No fallback was activated. Six additional large-grid finite differences remain
inconclusive; two ill-conditioned random-reference disagreements are documented
with precision evidence favoring the fast solver. Earlier evidence below is
retained history, not the current submission recommendation.

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

## Executed evidence

The bounded support run finished and released both evaluator locks. No Claude
headless model was launched. Raw official reports, execution/memory receipts and
re-audit results are in
[`experiments/audits/2026-11-22-transfer`](../experiments/audits/2026-11-22-transfer/summary.json).
The original run used immutable runtime `f8817a4`; the loss-inclusive supplemental
comparison and historical archive re-audit used `d804f35`. No running code was
modified during the test.

| Official setup | Pristine first run | Dense `aac9904` first run | Official / full-array comparison |
|---|---:|---:|---|
| Large grid (101/193) | 35.8830 s | 17.9702 s | Both pass |
| aLIGO (101/29) | 21.2450 s | 7.7202 s | Both pass |

Loss-inclusive comparison also passed for both setups. These are single fresh
process measurements on AMD, explicitly nonranking; they do not establish a
leaderboard win, final hidden-setup correctness or repeated timing confidence.

The 12-case retained-archive strict re-audit passed 12/12 for dense `aac9904`,
but only 2/12 for host solver `c4153e7` and its compiler-settings variant `53f38d3`.
Both host variants exceed the custom 1e-5 log-sensitivity comparison bound on
`uifo_rand1` (~2.04e-4) and `uifo_rand3` (~5.81e-5), and have additional elementwise
strict discrepancies. This is disagreement with the retained dense reference,
**not proof which solver is more accurate** on ill-conditioned systems. The
compiler variant shows the same pattern; these results do not isolate compiler
settings as its cause. Independent numerical arbitration remains necessary.
Historical archives lack independently authenticated code bindings; the new
official run has clean exact-commit checkouts and recorded artifact hashes.

Validation: 25 new focused tests plus 23 existing worker/array tests passed;
GitHub tests and SMAC jobs passed. Four synthetic legacy false-pass reproductions
(changed power, NaN loss, float32 gradient, missing reference) are recorded and
all fail under the new audit. The extension is a reviewed-branch candidate;
historical queue verdicts, deployed workers and acceptance policy are untouched.

## Review of the later guard and reproducibility report

Guard commit `a5a1069` allows exactly two package-set flags: XLA optimization
level zero and fusion emitters disabled. It leaves the inherited environment
sanitization intact. Read-only verification after the reported deployment denial
still found primary worker PID44394, release `861601b9`, worker digest
`d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58`.
No deployment or worker restart was performed by this audit.

A future deployment also needs the report consumers updated/versioned:
`lab.evolution_evidence.normalize_job` invokes its locally imported
`Worker._validate_report`. Updating only the remote worker can leave current
dashboard/search consumers rejecting the same reports under their old validator.
The recorded launch environment should remain sanitized (`XLA_FLAGS=None`);
package-set flags belong in the reported effective environment. New worker hashes
and comparison-policy cohorts must be recorded, not substituted into old evidence.

The later `0900bb4` reproducibility note is useful evidence of sensitivity to
BLAS implementation, but its statement that candidate error "never exceeds"
baseline self-variation is too strong: its own `dev` row gives candidate 6.8e-8
versus baseline variation 5.8e-8. Both are below the public tolerance; the
overstatement matters mainly for interpretation. Changing BLAS kernels and
observing a larger baseline disagreement does not define a new acceptance
tolerance, prove which result is closer to the physical solution, or establish
the judges' final reference procedure. Organizer questions must distinguish
experimental evidence from actual organizer confirmation. The new modulation
cases are additional positive evidence, not a waiver of the flagged random cases
or the elementwise strict checks reported above.
