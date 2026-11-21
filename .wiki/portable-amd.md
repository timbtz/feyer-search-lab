# Prepare a teammate's AMD evaluator

Each teammate gets an independent instance, SSH alias, serial queue and baseline.
Clone the complete `timbtz/feyer-search-lab` repository; the simulator and lab
tools travel together. A teammate can develop locally with Codex or Claude and
submit exact commits to their own instance. GPU VRAM is separate from system RAM;
this challenge's evaluator uses one logical CPU, not the Radeon GPU.

The commands below are an operator runbook for a **new** instance. They have not
been executed on teammates' hosts. Do not run them against the existing shared
instance, replace its environment, overwrite baseline files or restart its worker.
They deliberately retain the existing worker's fixed `/workspace` paths.

## 1. Access and isolated dependencies

Add the teammate's public SSH key before launching a Notebook in the Hackathon
pool with persistent `/workspace`. Copy its SSH command into a distinct laptop
alias, for example `amd-alice`. Keep private keys and GitHub authentication on
the laptop. Transfer a Git bundle from the authenticated local clone; the
instance needs no GitHub token:

```bash
git bundle create /tmp/feyer-search-lab.bundle --all
scp /tmp/feyer-search-lab.bundle amd-alice:/workspace/feyer-search-lab.bundle
```

On the new instance, install missing OS tools (`git`, `tmux`, GNU `time`, and
`taskset` from `util-linux`) using its package manager, then:

```bash
git clone /workspace/feyer-search-lab.bundle /workspace/feyer-search-lab
git clone --no-hardlinks /workspace/feyer-search-lab /workspace/feyer-pristine
git -C /workspace/feyer-pristine checkout --detach 02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f
python3.12 -m venv /workspace/venv-feyer
/workspace/venv-feyer/bin/python -m pip install -r /workspace/feyer-pristine/requirements.txt
```

Stop if any target already exists: inspect it rather than overwriting it. Use an
isolated venv without `--system-site-packages`. The official pinned requirements
provide CPU JAX; do not install torch or alter the image's Python environment.
Use the same reviewed lab release on all three hosts. The existing deployed
worker was last audited at `861601b`; newer controller commits do not mean the
live evaluator was upgraded. Record the chosen full release SHA and actual
worker/comparison hashes. Upgrades need a drained queue and a new calibration.

## 2. Establish this host's reference

Check `taskset -pc $$`, `lscpu`, `free -h`, `df -h /workspace`, and the container's
`/sys/fs/cgroup/memory.max`. CPU 2 must be available for this release: both the
deployment and evidence adapter require it. If unavailable, stop setup and use
a compatible instance. Another CPU requires a reviewed, versioned worker and
evidence policy change before its results can enter this workflow.

The following commands **run benchmarks**; a teammate executes them when ready.
Ensure `base1.*`, `base2.*`, `base3.*` do not already exist. Run each sequentially
from a fresh Python process and retain its report, arrays, plot and log:

```bash
cd /workspace/feyer-pristine
unset XLA_FLAGS JAX_COMPILATION_CACHE_DIR PYTHONPATH PYTHONHOME
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=true JAX_ENABLE_COMPILATION_CACHE=false
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONNOUSERSITE=1 MPLBACKEND=Agg
for n in 1 2 3; do
  taskset -c 2 /workspace/venv-feyer/bin/python benchmark.py --cpus 1 --repeats 3 \
    --output "base$n.json" --save-arrays "base$n.npz" > "base$n.log" 2>&1 || break
done
```

Inspect all three official PASS results before proceeding. `base1.npz` becomes
this host's strict comparison reference. Do not substitute an optimized
candidate's arrays or copy another machine's reference to hide numerical drift.
The manual initial calibration does not use the queue's sampled RAM watchdog;
subsequent queue jobs do. Preserve environment/version records and calibration
timings, and compare candidates against a parent measured on the **same host**.

## 3. Readiness and worker deployment

From the lab clone, check readiness without executing simulation:

```bash
cd /workspace/feyer-search-lab
/workspace/venv-feyer/bin/python -m lab.amd_preflight --repo . --cpu 2
```

This checks Python, official dependency pins, CPU availability, clean pristine
source, tool paths and reference presence/digest. Passing is not numerical
validation or deployment. The command exits nonzero when a prerequisite fails.

The existing deployment command, run **on the laptop in a clean, pinned lab
checkout**, uploads committed evaluator code and starts one worker:

```bash
python3 -m lab.deploy --repo . --host amd-alice --root /workspace/feyer-lab
```

It expects the prepared pristine checkout and venv above. It creates a mirror,
immutable release and `control` link, then the `feyer-worker` tmux session. An
existing tmux session prevents a switch; do not delete it to force an upgrade.
The deployment command starts CPU 2, matching this release's evidence policy.

Submit unchanged baseline code through the existing client to each new queue,
first screen and then full (see `python3 -m lab.client --help`). Import only a
full official-and-strict passing job as that host's validated search seed.
Screening evaluates the full physical workload but omits independent gradient
sanity and strict saved-array comparison. It cannot promote a candidate.

## 4. Three hosts, three evidence cohorts

Assign one durable host identity and SSH alias per instance. Route each claimed
task to exactly one queue and persist its request ID before submission. A lost
SSH response is recovered by looking up that ID, not creating another job.
Keep one evaluator process per instance. Parallelism across hosts does not
authorize parallel benchmark processes on a host.

Record host identity, exact source SHA, evaluator/checker hashes, Python and
dependency versions, reference-array digest, CPU affinity, resource limits and
full job ID. The worker enforces a sampled **32,000,000,000-byte process-group
RSS budget**; this is not a kernel memory cap. Its environment and actual
container limits remain part of evidence.

Do not pool raw seconds across machines or compare them directly to the
published Intel score. Per-host reference arrays can differ bytewise and create
different cohorts even on matching CPU models. Compare local parent/candidate
ratios and keep their provenance, then re-evaluate finalists together on one
chosen host. A candidate passing on one host is a proposal for another host,
not an automatically transferable correctness or speed result.

No bootstrap step starts agents, extends their budgets, enables SMAC, or grants
concurrent writes to a branch. Human-driven team task routing is separate from
the instance's trusted serial evaluator.
