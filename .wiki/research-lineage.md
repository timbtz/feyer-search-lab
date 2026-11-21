# Evidence-backed research graph

The scientific DAG answers which exact implementations informed a candidate.
Operational feedback answers which recorded results a later model turn consumed.
They are separate edge sets: a feedback loop is not backwards scientific ancestry.
The graph is a read-only projection of the existing executor and receipts, not a
new scheduler, Git merge engine or winner-selection algorithm.

## Captured evidence and remaining gaps

The supervised loop commits per-candidate feedback containing its exact SHA,
screen/full job reports, hypothesis, change summary, declared parent candidates
and profiler attribution. The queue and campaign ledgers retain exact jobs,
resource/cohort evidence, legal menus, proposals, decisions and stopping events.
The team ledger retains manual tasks, claims, source-backed observations and the
comparison regime. External supervised sessions deliberately do not masquerade
as finite task claims.

Older feedback does **not** consistently declare structured target phases,
iteration numbers, semantic combination parents, stopping reasons or exact next
inputs. Prose, Git ancestry, a fast timing and a high profiler row cannot fill
those gaps automatically. `target_phases=[]` means unknown. A finite-menu stop
means that reviewed menu is exhausted; it does not prove a local or global optimum.

Recorded evaluator feedback is not necessarily the complete prompt dispatched to
the next agent. Prompts also include policy, brief, profiler guidance and remaining
time. New runtime input receipts identify the exact dispatched prompt; old prompts
are not reconstructed and presented as originals. Prompt content stays on private
local disk. A path in a receipt is not a working hosted download link.

## Additive external record contract

`team_search.research_records` maps immutable IDs to `feyer-research-record-v1`.
The coordinator imports these records without claiming or dispatching work.
Required fields are:

- `record_id`, `kind` (`explore`, `refine`, `combine`, `diagnose`),
  `executor: {kind: supervisor|campaign|manual, id}` and recorded `status`.
- `hypothesis`, `change_summary`, `parents` (declared distinct full SHAs), and
  `candidate_sha` (full SHA or null while proposed). A combination declares at
  least two parents; its transformations must have a source-reviewed receipt.
- `target_phases`: canonical keys from the 14 benchmark phases or group keys
  `setup`, `compilation`, `forward`, `sensitivity`, `gradient`, `transfer`.
  Parser work has no separately measured phase; explicitly target `load` or
  `build` only when the owner declares that mapping, otherwise leave it unknown.
- `source_ref` and `source_digest`: immutable artifact location and SHA-256.
  The feedback converter uses canonical JSON (sorted keys, compact separators,
  UTF-8, no nonfinite values), identified by `source_digest_kind`.
- `evaluations`: exact `{job_id, candidate_sha, profile}` output references.
  `target_evidence` optionally names prior jobs motivating the phase hypothesis.
  References alone do not assert full eligibility or a measured gain.

`stopping_reason` is required for `stalled`, `failed`, `budget_exhausted`,
`deadline_reached` and `menu_exhausted`. The last also requires
`menu: {manifest_digest, legal_count, covered_count}`, with complete finite coverage.
`completed` and `evaluated` describe record/executor progress, not validation.
New facts append new record IDs; existing records cannot be rewritten.
An updated assignment can include `assignment_id`, `observed_at` and `supersedes`
pointing to an existing record. Its `record_update` control edge preserves the
earlier proposed receipt while showing a later dispatched state; no scientific
ancestry is inferred from this operational transition.

Optional `feedback_ref`, `checkpoint` and `next_input` contain `artifact_ref` and
`artifact_digest`. Optional `session_id` and `iteration` are copied only when known.
`input_receipt` retains the runtime's local `path`, `sha256`, `turn`, `thread_id`
and, when actually captured, `consumed_feedback_digest` / `consumed_candidate_sha`.
This is the input to the **current** candidate's turn, not that candidate's next
input. Missing fields remain missing across runtime versions.

## Import and display

Import trusted, committed supervisor feedback without guessing targets or ancestry:

```bash
team research --feedback candidate-01.json --executor claude-profile-guided-v1 \
  --source-ref https://github.com/OWNER/REPO/blob/FULL_RECEIPT_SHA/PATH.json
```

For an explicitly reviewed phase target, combination, external proposal or stop,
prepare a record matching the contract and run `team research --spec record.json`.
Record its authoritative source digest. Keep credentials, raw private prompts and
unrelated transcripts out of the shared ledger. Importing facts does not give a
second actor ownership of the supervisor's branch or budget.

The frontend integration calls:

```python
from lab.research_lineage import build_lineage
snapshot['search_lineage'] = build_lineage(snapshot)
```

The result is `feyer-search-lineage-v1` with stable `nodes`, `edges`,
`control_edges`, `records`, `issues` and explicit `limits`. Inputs are the team
ledger, exact-joined `jobs[].recorded_feedback`, jobs and existing campaign
snapshots. The builder never reads files, runs jobs or changes state.

Scientific edges are `scientific_parent` or `hypothesis_combination`; task,
campaign and research membership are explicit. `targets_phase` links declared
phase targets. `research_input` connects declared input candidates to a proposed
or current research record whose output SHA is still unknown; it does not create
a fictional successor or a successful-combination edge. `evaluation` links exact
candidate/job/profile identities.
Cycles and unresolved parents are reported, not fabricated. Campaign parent IDs
resolve only within their own campaign. No Git branch name alone creates ancestry.

Operational `control_edges` include recorded feedback artifacts, prior target
evidence and dispatched input. A `control_feedback` link is emitted only when a
captured consumed-feedback digest and candidate match a prior artifact, or an
explicit next-input receipt binds its feedback digest. Feedback availability by
itself is not proof of delivery. Local input artifacts have
`available_in_export=false` until a separate export actually includes them.

Evaluation nodes retain instance, cohort and `comparison_context` from exact
evidence matches. Official/strict facts are separate from adapter-policy
eligibility: CPU-34 data rejected by a CPU-2 default policy is not thereby a
physical correctness failure. No cross-lane timing average, green improvement
verdict or final winner is inferred here. The existing comparison guard and quiet
serial confirmation policy continue to govern promotion.
