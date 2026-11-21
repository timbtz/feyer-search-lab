# Run the team search from independent clones

The shared repository is **`timbtz/feyer-search-lab`**. It contains the simulator,
unchanged official benchmark and fixtures, evaluator, controllers, tests and
instructions. Each colleague uses their own Claude or Codex account locally and
their own AMD evaluator. Qwen, SMAC, a model API, and a central server are **not
required** for this workflow.

The Git branch [`control/team-search`](https://github.com/timbtz/feyer-search-lab/tree/control/team-search)
is the shared task queue and scientific history. Its rendered README shows
ownership and lineage; `state.json` contains the full machine-readable record.
Every queue mutation makes an ordinary commit and non-force push. A concurrent
claim loses the push race, reloads current state, and refuses a task already
claimed. No shared SQLite file, database merge, or issue-comment race is involved.
GitHub Issues/PRs are useful discussion surfaces; the control branch is the
authoritative assignment record. Keep this private team repository private unless
its owner explicitly chooses publication beyond the team.

## Clone, prepare, and see the next task

```bash
git clone https://github.com/timbtz/feyer-search-lab.git
cd feyer-search-lab
gh auth login
gh auth setup-git
python3 -m lab.team_search --help
```

Use Python 3.12 for the lab. The queue CLI uses the standard library; recording
evidence also imports the existing evaluator adapter. No model framework needs
installation. Prepare each **new** evaluator with [portable AMD setup](portable-amd.md).
Keep personal credentials on your laptop. Give each physical instance a stable
identity such as `amd-alice`; do not reuse an identity for a replacement host.

In your laptop shell, substitute your GitHub username:

```bash
team() {
  python3 -m lab.team_search \
    --remote https://github.com/timbtz/feyer-search-lab.git --actor alice "$@"
}
team next
mkdir -p .lab/team
team list > .lab/team/state.json
team claim frequency-layout --instance amd-alice
```

`next` lists ready tasks in ascending priority, then ID order. It is a suggestion,
not a claim. Tasks may declare `depends_on` IDs; these must be `done` or `stalled`
before the dependent task is offered or can be claimed. Only start after `claim`
succeeds. Save the returned `claim_id` and
task specification in your ignored `.lab/` directory. A claim never expires
automatically: after a crashed laptop, the same owner reads it with `list` and
resumes, or explicitly hands it back after checking that all jobs have drained.
If a command loses its network reply, inspect `list` before trying another claim.

The actor name is cooperative attribution, **not authentication**. Repository
write access is the security boundary. Do not edit or force-push the control
branch manually. Claims coordinate trusted teammates, not hostile tenants.

## Two search iterations

1. **Explore, then refine.** Start different implementation hypotheses from an
   exact reference. Record the mechanism and target functions before changing
   code. Run the complete screen; promising candidates need official full and
   strict saved-output/gradient checks. Compare complete first-run totals, retaining
   compilation, warm runtime and memory separately. Refine a useful topology with
   focused code changes or its reviewed finite tuning menu.
2. **Combine, then refine again.** When an iteration stalls, preserve its best
   validated revision. Select two complementary approaches with explicit parent
   SHAs and overlap/compatibility notes. Create a fresh combination branch from a
   known common base; apply or reimplement the transformations. Evaluate A, B and
   A+B on the same host, then tune the new combined topology. A clean merge is not
   a successful experiment. The combined candidate must beat the **better** parent
   in total time before it replaces that parent.

The result is a **DAG**, because a combination has two scientific parents. Git
ancestry may differ after cherry-picks or reimplementation. Repeated combinations
can reduce several surviving directions to one submission candidate, but a
regressing combination never forces the team to discard the faster parent.

The unexplored search space is represented by ready `explore`/`diagnose` tasks;
active branches by claims; exhausted directions by `stalled` tasks and their
reasons. Record negative results. Add new questions when results expose a gap.
Useful separate directions include frequency mapping/layout, component
specialization, factorization reuse, numerical derivative diagnostics and setup
overhead. These are hypotheses, not guaranteed speedups.

## Work on one branch and submit an exact candidate

Read `AGENTS.md` before editing. Create an owned worktree from the task's exact
parent SHA. For example:

```bash
git fetch origin
git worktree add ../alice-frequency -b explore/alice/frequency PARENT_SHA
```

Give your personal agent the task, parent SHAs, allowed files, hypothesis, budget,
deadline, and existing evidence. Keep the official workload and benchmark intact.
The task owner is the manual operator; if you use `lab.agent_loop`, explicitly
hand submission ownership to that supervisor instead. Never have both submit.
Do not restart or extend another session's existing deadline.

Commit and publish the candidate on its owned branch. Then reserve the exact SHA
in the shared task **before** evaluation:

```bash
team candidate frequency-layout --sha CANDIDATE_SHA --claim-id CLAIM_ID \
  --code-branch explore/alice/frequency
```

Reservation checks the fixed task deadline and candidate budget. These are manual
operator admission checks, not a process watchdog: the existing evaluator and
supervisor enforce execution limits. Do not run extra jobs after the task expires.
Repeated runs of the same candidate do not use another candidate slot. Completed
results may still be recorded after the deadline for safe bookkeeping.

Use the checked-in client; persist a UUID **before each deliberate measurement**:

```bash
mkdir -p .lab/team
python3 -c 'import uuid; print(uuid.uuid4())' > .lab/team/full-request-id
python3 -m lab.client --host amd-alice submit \
  --repo ../alice-frequency --branch explore/alice/frequency \
  --sha CANDIDATE_SHA --agent alice --direction frequency-layout \
  --hypothesis 'Describe the exact change and expected mechanism' --profile full \
  --request-id "$(cat .lab/team/full-request-id)"
python3 -m lab.client --host amd-alice status JOB_ID > .lab/team/job.json
team record --task frequency-layout --claim-id CLAIM_ID \
  --instance amd-alice --job .lab/team/job.json
```

Use `--profile screen` first when appropriate; its own measurement gets its own
saved UUID. Retry a lost submission with the **same UUID and identical payload**;
the client looks up the original job. An intentional fresh run gets a new UUID.
Do not overwrite a request-ID file for a pending request. `status` must be terminal
before `record`; `python3 -m lab.client wait JOB_ID` is also available (include
`--host amd-alice` before `wait`). A queue job ID alone is not evidence of success.
Fetch plots/logs with `lab.client fetch` and retain numerical arrays on the instance.

`record` publishes the job's numerical/source report and normalized evidence. It
omits stdout and provider transcripts. Review evidence for sensitive content before
publication; no credentials, SSH keys, environment dumps or personal chat belong
in the ledger. This adapter checks evidence consistency, not cryptographic worker
attestation: obtain files from the trusted evaluator, never hand-author a PASS.

## Stop, preserve alternatives, and choose combinations

```bash
team assess frequency-layout --sha CANDIDATE_SHA \
  --instance amd-alice --cohort COHORT_DIGEST
team resolve frequency-layout --claim-id CLAIM_ID --outcome stalled \
  --reason 'Repeated totals failed the frozen gain threshold; retain candidate X for its lower compilation cost. Next: test combination with Y.'
```

`assess` requires at least three eligible full observations of the candidate and
**each parent on the same instance and exact cohort**. The default useful gain is
greater than `max(0.02 seconds, 3% of the better parent, observed candidate range,
observed parent range)`. These explicit defaults
can be frozen differently when the coordinator admits a task. Inspect run ranges
and use alternating fresh parent/candidate runs; the median rule is a scheduling
threshold, not a statistical significance claim. Screens, missing artifacts,
strict failures and other hosts cannot satisfy it.

Stop refinement after a confirmed non-improvement under the task policy; mark it
`stalled` and open a new task only for a new mechanism or combination. A noisy or
incomplete result needs confirmation, not a scientific strike. Infrastructure
failures are `blocked` work with a recovery action. A human `done`/`stalled` label
is a routing decision and never promotes code or changes the evidence verdict.

The compile/runtime/memory Pareto descriptors preserve complementary approaches
for later combinations. They do **not** override the first-run time objective or
justify unlimited refinement. Keep a phase-efficient candidate as a combination
parent while stopping its unproductive local branch.

If an owner hands work back, check the local supervisor and remote job IDs first:

```bash
team release frequency-layout --claim-id CLAIM_ID \
  --reason 'No supervisor remains; all listed evaluator jobs are terminal. Notes: ...'
```

## Coordinator: admit work and import references

Only the coordinator ID recorded at initialization can add tasks or import seed
evidence without a claim. Initialize **once**, not once per clone:

```bash
team init
team record --instance amd-tim --job .lab/trusted-full-job.json
```

An example task spec (choose an actual future deadline, exact SHA and concrete
budget; the deadline shown is deliberately a placeholder):

```json
{
  "id": "frequency-layout",
  "kind": "explore",
  "priority": 20,
  "hypothesis": "Investigate whether frequency layout reduces compilation while keeping all 101 frequencies and 193 gradients.",
  "parents": ["EXACT_40_CHARACTER_PARENT_SHA"],
  "max_candidates": 3,
  "deadline_unix": 0,
  "minimum_full_runs": 3,
  "minimum_gain_fraction": 0.03,
  "minimum_gain_seconds": 0.02
}
```

Save it locally and run `team add --spec task.json`. Admitted specs are immutable;
new budgets require a new explicit task, not editing the old deadline. Use kinds
`explore`, `refine`, `combine`, `confirm`, or `diagnose`. Refine/confirm parents
need eligible full evidence; combinations need at least two distinct eligible
parents. They need not share a host to propose a combination, but **comparison**
requires measuring both on the chosen destination host/cohort. The CLI never
automatically dispatches a model, executes a merge, or starts a benchmark.

Use this team layer for human assignments. Existing `Campaign`/`topology_run`
controllers remain the richer per-campaign option for admitted finite searches.
Do not make this ledger and an autonomous controller compete for submission
ownership. Link a controller's campaign/session in task notes and hand it an
explicit subset of the task budget.

## Final integration and submission

Choose a single confirmation host. Re-run surviving candidate/reference revisions
there under one evaluator release and resource policy. Create a PR for the winning
simulator change and include exact candidate SHA, scientific parents, full job IDs,
output/gradient errors, repeated first-run totals, warm timings, resource evidence
and reproduction commands. Review numerical rewrites and semantic merge conflicts.

The coordinating maintainer merges the selected implementation into the final
submission branch. Re-evaluate that **exact merged SHA** before calling it the final
winner, even if its simulator files appear unchanged. Keep earlier branches and
failures. Package the code, before/after JSON reports and plots, and reproduction
instructions according to the original challenge. No automatic promotion or
merge into `main` is performed by the team queue.
