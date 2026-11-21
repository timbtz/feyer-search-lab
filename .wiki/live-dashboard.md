# Live search dashboard

The dashboard is a local, read-only view of the optimization system. It displays evidence already recorded by the controller and workers; opening it does not start agents, submit evaluations, change round specifications, or merge code.

## Run locally

From a checkout containing `lab/live_dashboard.py`:

```bash
python3 -m lab.live_dashboard \
  --repo '/Users/t.betz/Documents/Feyer challenge' \
  --port 8765 --sync-remote
```

Open <http://localhost:8765>. `--repo` points to the main repository holding `.lab`, even when the dashboard runs from an isolated worktree. `--sync-remote` uses the existing `amd-hackathon` SSH configuration to read queue records; omit it for an offline view. The server only binds `127.0.0.1`, provides no mutation endpoints, and refreshes browser data every five seconds. Remote queue polling is every fifteen seconds after the previous poll finishes. It never launches benchmarks or models.

Campaigns are discovered from `.lab/campaigns/*/campaign.sqlite3`; legacy workers from `.lab/sessions/*/status.json`; optional host/worker observations from `.lab/agent-status/*.json`. A worker observation can include `id`, `name`, `host`, `provider`, `actual_model`, `status`, `observed_at` (Unix seconds), `pid`, `process_match` for local identity verification, `session_id`, `branch`, `started_at`, `deadline_unix`, `runtime_commit`, `direction`, `reason` and `usage`. Remote records are timestamped observations, not perpetual heartbeats. Never put credentials in these records.

Stop the foreground server with Ctrl-C. This only stops the dashboard; it does not cancel a remote evaluation or agent.

## Run locally

From the checkout containing `lab/live_dashboard.py`:

```bash
python3 -m lab.live_dashboard \
  --repo "/Users/t.betz/Documents/Feyer challenge" \
  --port 8765 \
  --sync-remote
```

Open `http://localhost:8765`. `--repo` points to the main repository containing `.lab` campaign/session data, even when the dashboard code runs from an isolated worktree. Omit `--sync-remote` for local records only. Remote refresh uses the existing SSH configuration to read queue lists and reports; it does not submit work. The default evaluator alias is `amd-hackathon`.

The server binds only to `127.0.0.1`. Stop the foreground process with Ctrl-C. Refreshing the page does not restart workers or change their budgets.

## How the system fits together

The scientific lineage is a directed acyclic graph: immutable candidate commits point to their parent candidates. The execution pipeline has feedback: a completed evaluation informs the next proposal. The dashboard separates these two views so that a feedback loop is not mistaken for a cycle in candidate ancestry.

1. A coordinator assigns a bounded task to headless Codex or Claude. Strong agents investigate an approach and propose code or a future operator. Qwen is optional for narrow tasks.
2. Reviewed operators become a frozen round: legal parameters, constraints, parent candidates, objective, ownership and budget are recorded before search begins. The 193 physical variables and 101 frequencies remain fixed workload requirements.
3. A selector chooses an untested legal configuration. Enumeration/local search needs no model calls. SMAC is a separate selector integration; an installed package or proposed configuration does not establish that a SMAC campaign is running.
4. A materializer creates an exact candidate commit on an owned branch. The controller reserves a durable request ID, publishes the commit, and submits it to the shared AMD queue.
5. Screening executes the complete workload and checks sensitivity, finite results and a nonzero gradient. It omits the supplied finite-difference gradient sanity check and the additional strict saved-array comparison. A screen pass is provisional.
6. Full evaluation executes the unchanged official benchmark and the separate strict regression comparison. The official and strict outcomes remain separate: a strict mismatch is not automatically an official challenge rejection.
7. The controller records phase timings, checks, resource evidence and provenance. Only eligible full results in the same cohort participate in the validated frontier. New combinations require their own exact commit and evaluation; measured gains are not added together.
8. A lane's frozen stall limit or exhaustion leads to a coordinator decision. The default is three terminal non-improvements; finite enumeration can explicitly use a different frozen limit. New operators require a new reviewed round. Deadlines are not silently extended.

The Mac runs the local controller, dashboard and authorized local agent sessions. Hetzner hosts the native Codex execution broker and isolated search tooling. AMD executes the CPU benchmarks in the fixed environment. The Radeon GPU's VRAM is separate from system RAM and is not the memory budget for these CPU evaluations. GitHub carries immutable commits, assignments, guidance and published evidence.

## Reading results

The primary objective is complete first-run time, including imports, initialization, input loading/building, all three compilation stages, forward simulation, sensitivity, gradient and result transfer. Validation and reporting are outside that timer. Worker wall time includes additional overhead and must not be substituted for the objective.

`runtime` is the sum of first-run forward, sensitivity, gradient and transfer phases. It is not the warm median. Detailed phase times and warm measurements are separate evidence fields.

Candidate metrics summarize eligible full observations. Display the number of observations and their range alongside a median: a single low result is not a repeat-confirmed gain. Exact observed Pareto membership is distinct from noise-qualified primary or Pareto progress. The active round's recorded thresholds govern its decisions; a historical phase dashboard may use a different threshold.

The memory policy records a 32,000,000,000-byte sampled process-group RSS budget. It is not a kernel-enforced 32 GB container cap. Comparisons require matching CPU, affinity, software, workload, evaluator and checker identities.

## Freshness and ownership

“Last refreshed” means the browser successfully read the dashboard API. “Last evidence” means a source record changed. A controller's old PID or a pending queue reservation does not prove a worker is currently running. A stale or unavailable source remains explicitly unknown; it must not be colored as a live success.

Campaign SQLite databases use WAL. Read-only consumers must include committed WAL data and avoid opening the mutation-oriented `Campaign` constructor. The dashboard does not read capability tokens, environment secrets or private keys. Ownership claims and versions are coordination evidence, not host-level security boundaries.

Remote results can exist before their local copies arrive. After a controller interruption, the owning controller reconciles durable request IDs with the AMD queue; the dashboard only reports the discrepancy. Historical logs may still contain an old error after recovery, so the last log line alone does not define current state.

## Provenance links

Use candidate SHA links for code identity, branch links for browsing, job IDs for individual measurements, and content hashes for the supplied prompt/context. Guidance is displayed as an unevaluated proposal until a reviewed operator and validated candidate exist. A worker's scaffold commit is distinct from its scientific parent and its model-authored commit.

Raw model conversations are not automatically published. Only authorized briefs, responses, receipts and bounded sanitized log excerpts belong in this view. The dashboard is bound to localhost and is not a public administration interface.
