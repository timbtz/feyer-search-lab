# Overnight optimization, 22 November 2026

This newly authorized campaign has one fixed eight-hour window: **01:27:44–09:27:44 UTC on 22 November 2026** (02:27:44–10:27:44 Berlin). It does not renew the expired budgets of earlier sessions. No new model work or evaluation admission starts after the deadline; admitted jobs may finish within the recorded drain allowance. Launch receipts and session status establish whether a worker is actually running—this document describes the campaign contract.

Two independent writers start from simulator `53f38d342c3228c052785e8c9d63b6ce9c832dd1`:

| Lane | Direction | Branch |
| --- | --- | --- |
| Overhead | Imports, setup allocations and small JAX compilation costs | `explore/overnight-overhead-v1` |
| Numerics | Stable assembly, sparse solve and reverse execution costs | `explore/overnight-numerics-v1` |

The [overhead brief](../experiments/briefs/overnight-20261122-overhead.md), [numerics brief](../experiments/briefs/overnight-20261122-numerics.md) and [seed manifest](../experiments/campaigns/overnight-20261122/seed-manifest.json) preserve the initial rationale and evidence. Claude Opus 5.5 is preferred first. Account quota/authentication failure permits fallback to the pinned Codex Astra configuration; transient errors receive bounded retries. Provider sessions, failures, usage and recovery state remain recorded. A provider reset permits a bounded retry within the same campaign deadline, not another eight hours.

The same proposing agent receives evaluator feedback and repairs its candidate. Three consecutive evaluated proposals without a confirmed improvement trigger conservative refinement or a distinct in-lane hypothesis. Failed trials stay in history. There is no arbitrary candidate-count cap, automatic acceptance of a fast screen, or automatic merge between the two writers.

## What is evaluated

The larger official benchmark remains the primary objective. The official `benchmark_aligo.py` tests transfer. Both use the unchanged upstream harness pinned to `83f8d2f40fc75218a1d8ec7908cc0bf1c8f99a75`, exact committed simulator source, one logical CPU, numerical-library threads one, double precision and no persistent compilation cache. The large workload retains all 101 frequencies/all 193 design variables; official aLIGO retains all 101 frequencies/all 29 variables. Imports, initialization, setup, all three compilation stages, forward simulation, sensitivity, gradients and result transfer count in complete first-run time.

Each candidate's admission evidence contains at least three fresh-process runs of each official benchmark and the 14-case generalization suite. The additional suite checks original and perturbed setups, changed frequency ranges, random parameter cases, Voyager, aLIGO and amplitude/frequency modulation. It checks finite physical outputs and gradients, exact input identity and agreement with the fixed initial seed, with pristine-reference comparisons retained separately. It supplements the published benchmarks; a custom 100-frequency aLIGO probe is not the official 101-frequency transfer test.

The selected seed has three historical official passes on each benchmark: large median 0.986991538s, range 0.986434275–0.997343801s; aLIGO median 0.626026371s, range 0.623395482–0.632716989s. These are support-audit measurements. Fresh current-cohort calibration is required before the campaign promotes another candidate.

Known inherited issues remain explicit: additional dense-reference signal/gradient disagreements, two sensitive random cases and six unresolved grid finite-difference coordinates. Precision diagnostics favor the refined sparse solver in several disputed cases, but do not prove correctness for every possible optical setup. An official pass, an extra regression pass and an independent numerical investigation are different evidence. New regressions cannot be excused by relabeling an inherited issue. No tolerance is loosened to make a winner.

## Source integrity and selection

The organizers permit package JAX/XLA settings and implementations outside JAX when results remain correct and speed transfers. That does not permit fixture detection, hardcoded outputs, reduced workload, hidden precomputation, persistent answer/compilation caches, harness changes or inaccurate arithmetic. Generic algorithms may derive structure from arbitrary supplied setups; they must retain derivative contributions from entries currently zero.

New winners require an independent source review bound to the exact candidate, parent/baseline, diff hash, reviewer identity and review artifact. Review must cover the complete simulator delta from the trusted seed, or a fully reviewed ancestor chain—not merely the latest edit atop an unapproved parent. Tests alone do not certify absence of benchmark specialization. The initial known seed's fresh calibration is exempt from a new source review; novel revisions without approval stay provisional.

The publisher uses these explicit **team selection heuristics**, not organizer scoring rules:

- Trusted evaluator admission, both official benchmarks and all 14 generalization cases, no unresolved new failures, and independent source approval.
- At least three distinct fresh runs per benchmark; relative timing range at most 10%.
- Same comparison cohort: hardware, affinity, environment, dependencies, harness, runner/resource policy and timing regime. Package compiler options are candidate changes and stay visible in evidence.
- Large-case median improvement of at least `max(3 ms, 0.5%)`, with aLIGO median no more than 2% slower than current best.

Large and aLIGO medians/ranges are shown separately. We do not invent a combined score or claim the organizers choose winners by our median. Final quiet confirmation should be distinguished from exploratory timing with possible external contention.

## Current submission and recovery

The stable GitHub entry point is [CURRENT_BEST.md on the campaign control branch](https://github.com/timbtz/feyer-search-lab/blob/control/overnight-20261122/CURRENT_BEST.md). It links the exact source SHA, measured totals, caveats and [machine-readable current best](https://github.com/timbtz/feyer-search-lab/blob/control/overnight-20261122/experiments/campaigns/overnight-20261122/current-best.json). Immutable per-evaluation records retain raw runner receipts, report hashes, source review/diff, decisions and provisional candidates. The initial publication is explicitly pending fresh calibration.

The two model controllers run locally on the Mac and need the Mac awake and connected. Closing a chat is different from suspending the laptop: detached processes can continue after the chat closes, but a sleeping/offline Mac cannot request new turns or deliver feedback. The AMD runner persists requests and executes admitted evaluation work independently. It serializes numerical evaluation, reserves the existing evaluator locks, preserves CPU 2 policy and does not replace the existing queue workers. Two model writers do not mean two simultaneous benchmark processes.

The trusted client bundles exact candidate commits, registers a durable UUID, polls the same request and copies verified evidence. Lost responses are retried with the same identity; they do not start a new benchmark. A started request whose owner is lost becomes interrupted rather than being silently executed again. An intentional fresh measurement requires a new UUID. Source-review and publication failures preserve the raw numerical result and do not turn it into a passing submission.

For an operator replay, use the committed runtime and the **same trusted client configuration and saved request**:

```sh
python3 -m lab.overnight_client --config TRUSTED_CLIENT_CONFIG.json < SAVED_REQUEST.json
```

Do not run this beside the owning supervisor for the same request. The client preserves SHA/deadline/request identity and obtains fixed policy from operator configuration. For numerical reproduction, the archived reports retain the actual official command, source SHA, harness hashes, environment, CPU and arrays hashes. A new validation request should use that same policy and a new UUID; do not recreate measurements from an edited working tree or compare a different host as the same cohort.

The publisher uses a dedicated clean `control/overnight-20261122` worktree, a local lock and durable outbox. Commits are immutable published snapshots; failed pushes are **pending publication**, not GitHub success. Retry publication without another model call or evaluation:

```sh
python3 -m lab.overnight_publish retry --worktree CONTROL_WORKTREE \
  --evidence-root TRUSTED_RUNNER_ROOT
```

See the [publication contract](../experiments/briefs/overnight-20261122-publication.md) for initialization and schema details. Nothing in this path overwrites another session's worktree, main, or frontend-owned submission files.

## Optional cross-lane handoff

A safe later handoff is a read-only snapshot of the published current-best record at a new turn boundary, with its exact source SHA, record hash and source-review link. It must be captured in that turn's input receipt, not read as a moving target mid-edit. Assign one writer to any proposed combination, record both intended parents, and independently review/re-evaluate the resulting exact commit on both benchmarks. A shared-best snapshot is evidence and motivation, not proof that a transplant works. This is a suggested handoff mechanism; this document does not assert it is already wired into the supervisors.
