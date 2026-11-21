# Live search dashboard

The dashboard is a local, read-only view of the optimization system. It displays evidence already recorded by the controller and workers; opening it does not start agents, submit evaluations, change round specifications, or merge code.

## Run locally

From a checkout containing `lab/live_dashboard.py`:

```bash
python3 -m lab.live_dashboard \
  --repo '/Users/t.betz/Documents/Feyer challenge' \
  --port 8765 --sync-remote --sync-team
```

Open <http://localhost:8765>. `--repo` points to the main repository holding `.lab`, even when the dashboard runs from an isolated worktree. `--sync-remote` uses the existing `amd-hackathon` SSH configuration to read queue records; omit it for an offline view. The server only binds `127.0.0.1`, provides no mutation endpoints, and refreshes browser data every five seconds. Remote queue polling is every fifteen seconds after the previous poll finishes. It never launches benchmarks or models.

Campaigns are discovered from `.lab/campaigns/*/campaign.sqlite3`; legacy workers from `.lab/sessions/*/status.json`; optional host/worker observations from `.lab/agent-status/*.json`. A worker observation can include `id`, `name`, `host`, `provider`, `actual_model`, `status`, `observed_at` (Unix seconds), `pid`, `process_match` for local identity verification, `session_id`, `branch`, `started_at`, `deadline_unix`, `runtime_commit`, `direction`, `reason` and `usage`. Remote records are timestamped observations, not perpetual heartbeats. Never put credentials in these records.

Stop the foreground server with Ctrl-C. This only stops the dashboard; it does not cancel a remote evaluation or agent.

## Interface and design system

The default **Search graph** fills the workspace with an automatically laid out DAG. It maps recorded research workers and model invocations, frozen topology/operator spaces, small-parameter search lanes, candidate ancestry, research guidance, and optional individual evaluations. **Overview**, **How it works**, and **Results** remain supporting reports. The graph is a read-only map; it has no node dragging, connection editing, or workflow construction. Raw event records, queue payloads and bounded log tails are behind **Technical details**. Individual results expose phase timings, validation records, SMAC acquisition ranks, and GitHub links on demand.

The frontend uses the actual [Porsche Design System v4](https://designsystem.porsche.com/v4/), pinned to `@porsche-design-system/components-js@4.10.1`, with Feyer branding. The official loader and global CSS are generated without modification from the npm package. Component chunks and font resources load from `https://cdn.ui.porsche.com`; the server permits only that additional asset origin in its CSP. Local campaign data stays on the existing localhost API. No Porsche logo, crest or wordmark is used. The package license and third-party notices are retained in `lab/dashboard`.

The generated assets are committed, so starting the Python server does not require npm. To reproduce them:

```bash
npm ci --prefix lab/dashboard --ignore-scripts
npm run build:pds --prefix lab/dashboard
npm run check --prefix lab/dashboard
```

If the design-system CDN is unavailable, native navigation and readable content remain available with fallback styling. The dashboard still cannot mutate workers or evaluations.

## How the system fits together

The scientific lineage is a directed acyclic graph: immutable candidate commits point to their parent candidates. The execution pipeline has feedback: a completed evaluation informs the next proposal. Solid graph edges represent explicit recorded dependencies (including all combination parents, model-call provenance, research starting points, and exact candidate evaluations). Dashed edges show grouping or lane membership, not scientific ancestry. Worker identity is linked only by recorded IDs, session IDs, or historical branch identity. Unlinked workers remain visible without an invented candidate relationship. The view distinguishes research proposals from admitted search spaces and validated candidates; it does not claim to reconstruct the simulator’s internal computational graph from source code. Feedback is a decision to create a subsequent attempt, not a backwards edge in source ancestry.

1. A coordinator assigns a bounded task to headless Codex or Claude. Strong agents investigate an approach and propose code or a future operator. Qwen is optional for narrow tasks.
2. Reviewed operators become a frozen round: legal parameters, constraints, parent candidates, objective, ownership and budget are recorded before search begins. The 193 physical variables and 101 frequencies remain fixed workload requirements.
3. A selector chooses an untested legal configuration. Enumeration/local search needs no model calls. SMAC is a separate selector integration; an installed package or proposed configuration does not establish that a SMAC campaign is running.
4. A materializer creates an exact candidate commit on an owned branch. The controller reserves a durable request ID, publishes the commit, and submits it to the shared AMD queue.
5. Screening executes the complete workload and checks sensitivity, finite results and a nonzero gradient. It omits the supplied finite-difference gradient sanity check and the additional strict saved-array comparison. A screen pass is provisional.
6. Full evaluation executes the unchanged official benchmark and the separate strict regression comparison. The official and strict outcomes remain separate: a strict mismatch is not automatically an official challenge rejection.
7. The controller records phase timings, checks, resource evidence and provenance. Only eligible full results in the same cohort participate in the validated frontier. New combinations require their own exact commit and evaluation; measured gains are not added together.
8. A lane's frozen stall limit or exhaustion leads to a coordinator decision. The default is three terminal non-improvements; finite enumeration can explicitly use a different frozen limit. New operators require a new reviewed round. Deadlines are not silently extended.

The Mac runs the local controller, dashboard and authorized local agent sessions. Hetzner hosts the native Codex execution broker and isolated search tooling. AMD executes the CPU benchmarks in the fixed environment. The Radeon GPU's VRAM is separate from system RAM and is not the memory budget for these CPU evaluations. GitHub carries immutable commits, assignments, guidance and published evidence.

## Graph navigation

The initial map includes all campaign evidence and observed workers. Use **Scope** for the selected campaign, **Earlier experiments** for historical research results, and **Evaluation runs** for individual screen/full requests. **Fit graph**, zoom buttons, scrolling, and **Expand** navigate the graph without moving its nodes. Search matches models, hypotheses, IDs, commits, and source records; Enter focuses the first match. Selecting a node highlights its recorded ancestors and descendants and opens metrics, parameters, connected evidence, and the original sanitized record. Grouping edges do not pull unrelated siblings into a lineage trace. Refresh preserves selection and camera position. Cyclic or missing relationships are reported rather than silently invented.

Graph regression checks use `node --test lab/dashboard/tests/graph.test.cjs`; API checks use `python3 -m unittest tests.test_live_dashboard`.

## Shared team workflow

The default **Team workflow** scope renders `feyer-team-search-v1` as a top-down DAG: exact reference implementations feed explore/refine/combine/confirm/diagnose tasks, and tasks produce exact candidate SHAs. Combinations retain all parents. A refine task admits one successor to the frozen incumbent. Claimed/done/stalled/blocked are task-routing states, never evidence of a live model or final winner. The next-work panel respects recorded dependencies and deadlines.

`--sync-team` uses local GitHub CLI authentication to read only `control/team-search/state.json` every 30 seconds. It does not claim tasks, change the ledger, or launch agents. `team_search_source` distinguishes successful observation time, source event time, unavailable data, and staleness (90 seconds or fetch error). Without the flag, the optional `.lab/team/state.json` export is read locally; its file age is preserved. Last-good data remains visible on failure. A missing source is not an empty queue.

See the [three-instance workflow and architecture diagram](https://github.com/timbtz/feyer-search-frontend/blob/main/docs/SEARCH_WORKFLOW.md) and the [team CLI runbook](team-search.md). Every host keeps its own serial evaluator and reference cohort; the UI never pools timing values across hosts. Historical/finite Campaign evidence is a separate graph scope, not retroactive team ownership.

## Timing profile

The optional `.lab/profiler/report.json` collection is exposed as `profiler_reports` plus `profiler_source`. The Timing profile tab filters by exact SHA/job and ranks recorded first-run phases by contribution, with warm timing and job wall time shown separately. Invalid or conflicting artifacts remain visible with their issues and do not produce phase rankings. The frontend does not run the collector or infer source-code hotspots, successful optimizations, or a champion from these profiles. File observation age and last-good/error status remain explicit.

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

## Search progression view

The main map presents the algorithm in order: baseline, independent research directions, compact candidate histories, bounded numerical tuning, stopping, combination and exact confirmation. Select a direction or candidate marker to inspect its receipts; use **Exact evidence DAG** for recorded scientific parent edges. **Focus map** removes the page header. **Architecture** includes the editable search diagram.

Dashed guide lines express intended progression, not measured ancestry. The first three directions are chosen by observed activity and recency, with all directions available. Candidate markers represent exact revisions in time order. Latest full observations are not winners or pooled cross-host scores. Unlinked receipts remain available separately. Completed worker status is not a scientific verdict.

## Expandable run cards

Search progression retains each exact evaluation. Use **Expand decisions & feedback** to open recorded changes, targets, five timing objectives, nested 14 phases, validation evidence and checkpoint/input receipts. Scientific/execution graph consumes `search_lineage`; control feedback is an optional separate overlay. Absent history is unknown. Parent timing deltas require compatible exact evidence; cross-host or cross-regime results are not ranked together.

The default Topology map uses compact candidate nodes and declared parent arrows. Direct node selection opens the side inspector; profiler and run details can expand locally. Collapse all restores the overview. Topology, admitted implementation space, and declared phase focus are labelled distinctly; absent topology stays unclassified. Branch dropdowns have been removed.

The process overview now flows horizontally. Recorded agent sessions expand into candidate revisions and separate evaluation jobs. Same-agent sessions remain distinct; shared-branch ambiguity stays unassigned. Numerical menus are blue rectangles; decisions are orange circles with explicit reasons. Complete menu coverage and controller budget exhaustion remain separate. Disable Group agent sessions for the individual-candidate view. Aggregated candidate ancestry links are not evidence of model-feedback delivery.

## Other setups

The **Other setups** tab reads `.lab/generalization/report.json` (`feyer-generalization-collection-v1`), written by `python -m lab.gencheck report`. Each record compares one exact candidate with the unchanged simulator on several optical setups and shows per-setup sensitivity, output and gradient differences and exploratory timings. A missing file means no comparison has been recorded. It does not mean a candidate generalizes. These records do not change official, strict, eligibility or Pareto status. See [Generalization to other setups](generalization.md).
