# SMAC3 in the optimization process

SMAC3 2.4.1 is an optional selector in the existing campaign runner. Its
random-forest surrogate and expected-improvement acquisition select among
registered simulator implementation choices. Our evaluator still owns physics,
correctness checks, exact commit submission and CPU policy. SMAC never calls a
simulator function or its own optimize/validate methods.

## When to use each strategy

The CLI now defaults to `--selector auto`. At initialization, auto selects
enumeration when at most 32 untested configurations remain and the evaluation
count budget can cover a screen/full pair for each. Otherwise it selects SMAC.
The threshold is a transparent engineering heuristic, not a measured optimal
cutoff. Wall time can still prevent complete coverage. The resolved strategy,
reason and settings are frozen; there is no mid-campaign policy replacement.

Use explicit `--selector local-search` for controlled local ablations and
neighborhood exploration. Use `--selector smac` for a bounded model-guided pilot
or when expensive evaluations require choosing a subset. The current renderer
still has only 15 legal configurations; enumeration remains the natural
coverage baseline. The adapter does not invent additional dimensions. Agents
must implement/review a larger versioned space before it can be searched.

In the wider process, agents introduce structural ideas and numerical solver
alternatives; SMAC tunes the admitted choices; repeated full validation confirms
finalists. The Hetzner proposer broker is a separate source of new operators.
There is no claim that SMAC outperforms the simpler selectors on this workload.

## Learning and recovery

One observation per configuration is the median complete first-run time from
its eligible full measurements, within the frozen cohort. Screens,
infrastructure errors, pending jobs and incompatible cohorts never supply
training times. A full scientific rejection is retained with a fixed cost of
1,000,000 seconds and SMAC CRASHED status. This is an explicit infeasibility
penalty, not a measured duration. A previously invalid configuration cannot
become eligible through a later fast measurement.

The first four distinct observations provide startup coverage; after that SMAC
fits its surrogate. For the registered finite space, a small maximizer extension
scores every unseen option with SMAC's own acquisition function and sorting.
This avoids duplicate proposals from its general-purpose neighborhood search;
these scores are cheap model predictions, not additional physics evaluations.
Startup choices can be random; expected improvement supplies exploration after
startup, without extra interleaved random proposals.
Each decision records the actual `selection_origin`, training count, random
seed, settings, package versions, source hashes, full input context and elapsed
selection time. An acquisition-guided choice is distinguished from startup or
random exploration. There is no silent fallback to enumeration.

Each decision reconstructs the bounded model from immutable campaign evidence.
The random seed is fixed, and the selected proposal is persisted through the
existing pending-recipe mechanism before evaluation. Recovery reuses that
proposal and its durable queue IDs. Deduplication uses rendered source content;
the host rejects an already-seen or unregistered returned configuration.
SMAC's deterministic scenario setting prevents it from scheduling repeated
seeds; timings are still noisy, and our separate confirmation policy remains.

`prevent_cse` is conditionally active only with checkpointing. Categorical
encoding preserves all 15 legal assignments and cannot emit the forbidden
checkpoint-off/prevent-CSE-on combination. Batching remains a categorical
implementation choice rather than an assumed smooth numerical axis.

## Isolated controller environment

Install `ops/smac/requirements.lock` in a separate Python 3.12 virtual
environment. Never install it in `/workspace/venv-feyer` or change benchmark
dependencies. The requirements include dependencies pulled by SMAC; the adapter
uses one worker, 32 trees and the registered finite set of challengers, with no Dask cluster
or GPU inference. Use single-thread numerical-library environment settings.

The library can run in the controller process or via a bounded SSH helper:

```bash
python3 -m lab.evolution_run init \
  --state /absolute/path/to/campaign --name smac-pilot \
  --selector smac --search-seed 0 --max-model-calls 0 \
  --seed-report seed-full-1.json --seed-report seed-full-2.json \
  --seed-report seed-full-3.json --prior-full prior-exact-full.json \
  --smac-host Hetzner-VPS-Dev \
  --smac-python /home/developer/feyer-agents/smac-search/.venv/bin/python \
  --smac-root /home/developer/feyer-agents/smac-search/releases/CONTROLLER_SHA \
  --minutes 30 --max-evaluations 6 --publish
```

The remote directory must contain this exact committed adapter and renderer.
Initialization checks package versions and code hashes; every decision rejects
runtime drift. The SSH request sends parameters and timing evidence only, not
credentials or physical fixtures. The Linux helper uses GNU timeout to terminate
after 75 seconds (with a five-second kill grace), inside a 90-second SSH timeout.
The ordinary queue/evaluator SSH connection is independent of this helper.

For a policy handoff, stop/drain the old campaign, recover all exact results,
and import them into a new campaign. Carry over the earlier deadline with
`--deadline-unix` and allocate only remaining evaluation budget. This option
can shorten the relative deadline and cannot extend it. A pilot is not a new
authorization to extend the original exploration window.

References: [SMAC ask-and-tell](https://automl.github.io/SMAC3/latest/advanced_usage/5_ask_and_tell/),
[SMAC 2.4.1 implementation](https://github.com/automl/SMAC3/tree/v2.4.1).
