# Candidate DAG search and evidence ledger

This implementation adds a durable experiment record around the existing Feyer evaluator. It does not replace the challenge benchmark, infer correctness from an LLM response, or turn a clean Git merge into a validated combination. The initial reviewed search space is deliberately finite; broader solver research remains separate agent work until its operators are reviewed and admitted in a new round.

The design takes inspiration from AdaEvolve's three levels: adapting mutation behavior within a population, allocating resources between populations, and asking for new tactics when progress stalls. Here those ideas map to versioned operators, owned search lanes, and guidance proposals. This is an engineering adaptation, not a reproduction of AdaEvolve or a claim to its benchmark results. [AdaEvolve paper](https://arxiv.org/abs/2602.20133)

## What is frozen, and who may change it

A campaign identifies its budgets, evaluation contract, initial evidence and designated actors. A round freezes its operator versions, parameter domains, lanes and scheduling rules. Proposers choose from those admitted operations. Guidance can recommend a different tactic or a new round; the coordinator must validate and freeze that new round before dispatch. Guidance cannot silently change the active round's budget, ownership, correctness thresholds or workload.

The initial seed is a strong Codex-produced candidate with saved full evidence. Qwen chooses short recipes from a reviewed finite menu; it does not generate unrestricted simulator code in this pilot. The initial renderer considers checkpoint enablement, `prevent_cse`, and map batching, with invalid combinations excluded. Fifteen assignments are syntactically reviewed; syntax checking is not numerical validation. Every distinct materialized implementation still goes through the required evaluator.

The actor/model manifest must identify the actual provider, model and settings. Existing designated Codex/Claude sessions can investigate a new operator or resolve a difficult combination. The framework does not silently substitute another model or automatically spawn an unfamiliar named model. A new operator topology requires review and an admitted round rather than a free-form recipe that bypasses the host renderer.

Ownership is cooperative coordination between team agents, not OS-level isolation against hostile code. Distinct actors use owned lanes and worktrees; the evaluator remains serial. The evaluator's existing CPU, numerical and memory-policy checks remain authoritative.

## Three distinct identities

| Identity | Meaning | Recorded evidence |
| --- | --- | --- |
| Proposal | A chosen operation, including an invalid or duplicate attempt | Proposal/round/lane/actor IDs, scientific parents, recipe, before/after parameters, hypothesis, model manifest, context and prompt/response hashes |
| Candidate | One immutable materialized implementation | Exact commit and content digest, ownership version, scientific parents, explicit Git ancestry if supplied |
| Evaluation | One intentional measurement of a candidate | Durable request ID, actual queue job ID, profile, evidence digest, environment/cohort, checks, phases, resource usage and errors |

Scientific parents mean “the implementations selected as inputs to this experiment.” Git parents mean source-control ancestry. They must not be conflated: a combination may have two scientific parents but one ordinary Git parent, and a revert can create a new proposal pointing to existing content without inserting a cycle into scientific lineage. Duplicate content should preserve proposal provenance without inventing another scientific success.

The exporter renders scientific edges only. It assigns its own unique Mermaid node IDs and sanitizes labels. An edge records a hypothesis/history relationship, not proof of causality. Establishing that a specific edit caused an improvement requires controlled comparisons or ablations under matching conditions.

## Feedback and learning

Keep these outcomes distinct:

- Provisional screen: the complete workload ran, but the full public gradient sanity check was not run.
- Eligible full result: the official checks, additional numerical comparison and required provenance/resource checks all passed.
- Invalid candidate: a documented numerical or implementation failure; retained as repair evidence.
- Infrastructure error: missing/malformed evidence, transport failure or evaluator failure without a scientific verdict. It must not count as a numerical failure or a lane's scientific strike.

Each result belongs to its exact candidate SHA and queue job. The evidence adapter supplies explicit eligibility, check states, cohort digest, all first-run phase values, separate warm timing, cost and uncertainty notes. A completed job alone does not imply a valid candidate. Never average screen and full observations into a confirmed speedup, mix hardware/resource cohorts, or promote a single measurement as repeat-confirmed evidence.

Improvement is measured against the chosen parent/reference, with the baseline and phase deltas retained. Total first-run time remains the primary objective. Compile/runtime/memory diversity descriptors and Pareto views help choose work; they are scheduling aids, not acceptance tests. A gradient improvement can coexist with a compilation regression. All attempts, including duplicate recipes, rejected proposals, cancellations, failures and stalled lanes, remain in the event history.

Guidance should receive a compact context containing current ownership and round policy, eligible parents, recent failures, numerical-review cases, phase outcomes and stalled-lane reasons. Its reply should name the evidence supporting its recommendation and propose a next action. The coordinator records whether that recommendation was admitted, rejected or deferred, with the relevant context hash. No outcome is automatically merged into the submission branch merely because it is exported.

## Immutable context and prompt provenance

Before a proposer call, freeze the **actual context sent** using `freeze_context`, or pass it as `context=` to `export_campaign`. Canonical JSON bytes are written to `contexts/<sha256>.json`; the returned hash is recorded in the proposal/decision. The same input produces the same hash regardless of object key ordering. A content-addressed artifact is never overwritten with different content.

`store_text_artifact` preserves exact authorized worker briefs, prompts and responses as UTF-8 files under `briefs/`, `prompts/` or `responses/`, returning path/hash/byte count. The caller records those references in proposal provenance. These are the pilot's actual artifacts; the exporter does not claim to possess or reconstruct the entire chat transcript. Credentials, ownership capability tokens and raw process environments do not belong in published artifacts. The exporter removes known private fields and rejects recognized credential-shaped strings; callers must still construct a deliberate public context instead of dumping arbitrary process state.

If no explicit context is supplied, the exporter creates a bounded summary of recent candidate and decision evidence. This default is useful for inspection, but a caller must not claim its hash identifies a different prompt/context that was actually sent. Model usage counts and provider cost units are useful evidence; authentication tokens are not.

## Exported files

`lab/evolution_report.py` accepts the campaign snapshot and event list. It makes no provider calls, benchmark submissions, Git commits or GitHub writes. The coordinator owns publication.

| File beneath `experiments/campaigns/<campaign_id>/` | Purpose |
| --- | --- |
| `README.md` | Ownership, scientific DAG, candidate outcomes, round policy, decisions and failures |
| `snapshot.json` | Current public state, including complete candidate/evaluation metadata |
| `snapshots/<sha256>.json` | Immutable versions of public state |
| `events.jsonl` | Ordered event trail; later exports may append but may not rewrite or shorten the prefix |
| `context.json`, `contexts/<sha256>.json` | Current and immutable proposer/guidance context |
| `manifest.json` | Export schema, campaign/spec identity, content hashes, event count and context reference |
| `candidates.csv` | Per-candidate phase metrics and scientific/Git ancestry for analysis |
| `briefs/`, `prompts/`, `responses/` | Optional exact artifacts written explicitly by the runner |

The current `snapshot.json` and `context.json` are convenience aliases; historical references must use the immutable hashed paths. The event hash chain is owned by the campaign state engine. Export additionally enforces append-only publication and records a hash of the whole exported stream. Rendering a ledger does not authorize more work or establish correctness.

Example integration:

```python
from pathlib import Path
from lab.evolution_report import export_campaign, store_text_artifact

snapshot = campaign.snapshot()
context = campaign.context()  # the exact public context used by the caller
manifest = export_campaign(
    snapshot, snapshot['events'], Path('experiments/campaigns'), context=context,
)
context_hash = manifest['context_sha256']
prompt_ref = store_text_artifact(worker_prompt, manifest['directory'], 'prompts')
# Record context_hash and prompt_ref on the proposal before dispatch.
```

For an already saved public state:

```bash
python3 -m lab.evolution_report --snapshot campaign-snapshot.json \
  --context actual-proposer-context.json --output experiments/campaigns
```

A candidate commit must exist before its evaluation request. Subsequent result/publication commits may update campaign files without changing that candidate's simulator contents. Use the exact candidate SHA in reports rather than treating the tracking branch's newest documentation commit as the measured implementation.

## Boundaries still requiring explicit evidence

The initial finite menu is an implementation starting point, not evidence that Qwen yields useful proposals. Live parse/applicability/duplicate rates, strict-pass rate, improvement rate and gain per evaluator-hour must be measured. Expanding operators or models requires a new reviewed policy. Independent derivative diagnostics remain necessary for substantial numerical rewrites. Sampled RSS monitoring is not a kernel memory cap. Repeat-confirmation and causal ablation remain separate experiments, even when a candidate is on an observed frontier.
