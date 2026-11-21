# Feyer search: candidate DAG, adaptive policies and tiered agents

Status: design and repository inspection, 21 November 2026. A finite-space DAG controller and runner have now been implemented; see [implementation and evidence ledger](dag-search.md). This design remains broader than the pilot: the full EvoHarness package, adaptive bandit scheduling and a large worker swarm are not deployed by this change.

## Decision

Use the team's EvoHarness search policies as the first integration target. Preserve the Feyer evaluator, exact candidate commits, request IDs, and correctness contract. Use Qwen for short bounded mutation recipes and combinations; use Claude and Codex with their designated session models for substantial implementation work, new mutation operators, numerical investigations, and difficult combinations. An orchestrator assigns work and reviews evidence; deterministic code enforces admission and budgets.

The search variable is the simulator implementation and its permitted algorithm choices. The required 193 physical design variables and 101 frequencies remain unchanged. This is a discrete, structured program search, not an invitation to change the physical problem.

## What Claude produced

Evidence: `explore/linear-algebra-audit`, final solver revision `b68b6a18328bb898c01d80eedf2fd2bb544623aa`; detailed notes are in that branch's `experiments/notes/claude-linear-algebra.md`.

| Experiment | Full first-run time | Outcome |
| --- | ---: | --- |
| Shared LU factorization, candidate 1 | 31.509 s | Official pass; 3 of 193 gradients fail strict comparison |
| Block/Schur solver, candidate 2 | 31.239 s | Official pass; broader numerical differences; warm benefit did not establish a first-run improvement |
| Restore shared LU, candidate 3 | 31.821 s | Official pass; same strict discrepancies as candidate 1 |

Compare against the local baseline median 35.737 s, not the published Intel result. These are individual full measurements, not an alternating confirmation study. Do not average screen and full times into a confirmed speedup. Candidate 3's full warm median is 10.743 s. Claude also documented matrix structure and possible diagnostics; actual sparsity/fill-in measurements remain unperformed. Pivoting is a proposed explanation for gradient differences, not an independent diagnosis.

Claude's branch is useful repair/research evidence, not a validated winner. The earlier seed8 confirmation study measured 28.094 s versus 35.720 s in matching repeated runs. The newer component-specialization session has since reported faster individual full passes; these need repeated confirmation before replacing that confirmed result.

## Reuse from EvoHarness

Inspected repository: https://github.com/timbtz/evoharness-search-algorithm at `99284aca0ee612f41b093ffe827e547a941afff2`.

| Component | Reusable behavior | Feyer adaptation |
| --- | --- | --- |
| `strategies/search_space.py` | UCB-style improvement/coverage allocation; pending work counts as visits; ancestry and frontier | Replace physical-loss/power axes with benchmark phases and RSS; explicit screen/full/review/validated states |
| `strategies/swarm.py` | Completion-order proposals and queue-pressure backpressure | Submit through the audited remote queue; preserve durable IDs and recover existing jobs on restart |
| `strategies/bandit_search.py` | Epsilon-greedy lineage allocation and fork-on-stall | Reward confirmed timing gains; keep diversity without claiming every fork is better |
| `strategies/qd_gate.py` | Retain best candidates within distinct behavioral cells | Use stable algorithm/phase/memory descriptors; code similarity alone is insufficient |
| `strategies/coordinated.py` | Structured assignments, parent IDs, cheap/strong roles, bounded context | Use designated Codex/Claude sessions and Qwen recipes; host controls validation |
| Engine ledgers/resources | Record attempts, budgets and costs | Link to exact queue IDs, evaluator versions, phase reports and immutable source |

Do not transplant this package's task contract unchanged. `train`/`val` are not equivalent to screen/full: both Feyer profiles use the same full physical workload; screening omits the finite-difference sanity check. Its physical feasibility fields and wall-clock evaluation-cost objective are different from Feyer's complete first-run time. A completed finite candidate may be useful as a repair parent without qualifying for promotion.

The package requires Python >=3.11 and two sibling distributions (`evoharness-api-definitions`, `evoharness-benchmark-architecture`). Inspection used a shallow checkout under ignored `.lab/vendor/`; dependencies were not installed in the benchmark environment. A full integration should pin all three components in a separate controller environment. In particular, do not import the existing coordinator's restart behavior blindly: Feyer's request lookup must recover pending jobs rather than mark and resubmit them.

ShinkaEvolve is a useful comparison implementation: it documents CLI-backed Codex/Claude mutations, separate proposal/evaluation concurrency, and evolutionary archives. OpenEvolve documents island/MAP-Elites search. Neither replaces the required Feyer integration. Sources: [ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve), [configuration](https://github.com/SakanaAI/ShinkaEvolve/blob/main/docs/configuration.md), [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve).

## Graph semantics

There are two DAGs and one feedback loop:

1. **Candidate lineage DAG:** immutable source/configuration nodes; mutation, combination, repair and revert edges. A mutation has one parent; a combination has multiple parents. A revert makes a new proposal event pointing at old content, not an edge backwards that introduces a cycle. Deduplicate identical content for evaluation while retaining every proposal's provenance.
2. **Task DAG:** propose -> schema/path checks -> materialize and commit -> screen -> full validation -> archive. Diagnostic/repair tasks can branch from failures; confirmation runs depend on completed validation. Every combination is a new candidate and must run its own checks.
3. **Search feedback loop:** results update parent/operator selection, which creates future nodes. This loop does not make candidate ancestry cyclic.

The current system supplies serial evaluation, durable request IDs, per-agent loops and evidence export (`lab.search` on `infra/server-agents`). It does not yet autonomously allocate work over this graph. Branches represent owned research episodes; commits identify candidates; runs identify measurements. Do not create a long-lived branch per tiny recipe.

## Selection and Pareto evidence

Maintain four views: all attempts, provisional screens, numerical-review/repair candidates, and validated candidates. A promotion requires full official and strict checks plus provenance/resource checks. Record both correctness verdicts; never silently convert strict failures into passes.

The ranking objective remains complete first-run time. Keep all raw phases and show total, setup, compile, forward, sensitivity, gradient, transfer and peak RSS. For diversity selection, start with coarse compile/runtime/memory cells and algorithm tags so microsecond noise does not preserve every point as a supposed Pareto improvement. Cells are scheduling aids, not acceptance tests. Freeze their definitions per campaign.

Compare only matching hardware/environment/evaluator/profile/resource-policy cohorts. Distinguish observed single-run frontier membership from repeat-confirmed improvement. Repeat promising candidates and their parents in alternating fresh processes; retain sample counts, ranges and phase deltas. A phase regression may still produce the best total. A currently dominated approach can remain a useful stepping stone or combination parent.

Start with a transparent mixture of best-parent refinement, underexplored-lineage sampling, and complementary-parent combinations. Use EvoHarness's UCB-style rule to allocate more attempts to productive operators/lineages, with pending assignments counted to avoid duplicating work. Treat this as a heuristic, not a convergence guarantee. Bandit rewards should use validated measured gain and actual cost; compiler errors, duplicate proposals and numerical failures remain in denominators. Preserve occasional exploration and allow dormant branches to reopen after new evidence.

## Agent roles and operators

Qwen receives a compact menu, selected parent summaries and recent failures, rather than the complete repository and history. It returns a strict recipe: parent IDs, operator/version, target function, allowed parameter values and a short prediction. Candidate operations include a permitted map/chunk variant, selecting a reviewed checkpoint location, recombining existing validated transformations, or reverting one transformation. These are proposed operator families: implementations and legal parameter ranges still need to be registered and checked.

Existing deterministic operators should be enumerated or randomly sampled without an LLM when that is cheaper. Qwen adds value when choosing combinations, proposing a small patch, or interpreting bounded feedback. A schema-valid recipe is not evidence of a valid implementation or speedup. Host code rejects unknown operations, invalid parameters, stale parent IDs and incompatible preconditions before materializing a candidate.

Claude/Codex create new operators, investigate gradients, inspect compiler output, and resolve semantic conflicts. The orchestrator periodically revises priorities using completed evidence. It should not spend a large-model call on every dispatch. Keep model identity/settings in manifests; the framework must not silently substitute models.

Combinations need exact parent revisions and a semantic compatibility check. Apply transformations to a known common base or explicitly reimplement the selected pieces. Never concatenate whole source files or assume clean Git merges imply compatibility. Measure A, B and A+B under matching conditions and record interaction: gains can reinforce, cancel or break correctness.

## Required logging

Each event records campaign/decision ID, parent revisions, source-tree digest, candidate commit, operation/version, target symbols, parameters before/after, model/settings, prompt/response references, token usage, provider latency and cost units, dispatch/queue/runtime durations, request IDs and job IDs, evaluation contract, correctness results, numerical error diagnostics, per-phase timings, RSS, selection reason and promotion decision.

Keep proposed target phase separate from measured phase changes. A single edge gives an association; repeated paired comparisons and ablation give stronger attribution. Log invalid proposals, timeouts, duplicates, rejected mutations, and cancellations as well as winners. API credits/points are not assumed to be dollars. Keep append-only events and atomic state snapshots; enforce budget reservations before dispatch.

A logical evaluation request retains one durable ID across retries. A deliberate fresh measurement gets a new ID. No duplicate execution should be inferred merely because the client lost a response. The framework database is a searchable index; queue results and versioned artifacts remain authoritative.

## Scale by measured bottlenecks

Separate proposal concurrency from evaluation concurrency. Begin with a small ready queue and increase Qwen concurrency only when valid, nonduplicate proposals arrive reliably and the evaluator is starved. Previous short API checks succeeded at eight concurrent requests but did not establish a sustainable limit. Long Qwen coding prompts failed to produce useful proposals; short recipe probes are a new test, not proof of optimization ability.

At roughly 2-2.5 minutes for screen plus full evaluation, one continuously busy serial evaluator has a rough ceiling of 24-30 such candidates/hour before extra repeats, coding and failures. Thousands of proposals do not imply thousands of validated experiments. Preflight and content deduplication are therefore important; use smaller diagnostic tests for rejection only, never as full validation.

The server has about 55 GiB host RAM and separate 48 GB GPU VRAM. Two simultaneous jobs reserving 32 GB each do not fit the host budget. Current 13-16 GiB observations cannot guarantee future mutations stay that small. Keep official timing runs serial; any future concurrent exploratory lane needs explicit memory admission and separate timing labels, followed by serial confirmation. More identical evaluator instances are the clean horizontal scaling path. GPU-hosted small-model inference is a separate optional deployment and cannot supply CPU benchmark memory.

Keep proposal models on the Mac while AMD provider connectivity is blocked. The hosted Qwen model consumes Token Factory allowance, not the instance's GPU. A self-hosted model is an independent experiment with its own performance and operational cost.

### Short recipe probe

The [saved probe](../experiments/audits/qwen-recipe-probe.json) contains three synthetic prompts, exact responses and usage: one bare JSON recipe passed, one valid recipe required removal of a single Markdown JSON fence, and one request returned HTTP 502. The two completed responses took about 11 seconds each, using 143 and 257 completion tokens respectively. There were at most two concurrent requests, no retries, and no generated code execution. Headers reported a 20 requests/minute user limit; this does not establish sustained service throughput. This supports testing bounded recipes next, not claiming that Qwen can yet implement useful simulator mutations. The probe is deliberately simple and partially prescribes the answers.

## Integration sequence

1. Adapt archived Feyer evidence into EvoHarness graph nodes/edges with explicit profile and eligibility semantics. Replay the existing history offline; verify failed/screen-only candidates cannot become validated winners and duplicates do not produce new evaluations.
2. Connect operator/parent allocation to existing supervisors and queue through one adapter, preserving request IDs and original budgets. Keep the trusted evaluator fixed.
3. Run a bounded Qwen recipe pilot. Measure parse rate, applicability, duplicate rate, strict-pass rate, improvement rate, tokens, latency and end-to-end gain per evaluator-hour. Existing larger Codex/Claude sessions remain separate producers.
4. Add crossover and strong-agent escalation, then compare against simple random operator sampling and best-parent refinement at equal budgets. Increase throughput only after this demonstrates useful candidate yield.

This sequence can scale without replacing the evaluator or prematurely committing to another evolution framework. The implemented pilot uses a deterministic lane schedule, a finite seed8 renderer, bounded Qwen recipes and the existing queue. Larger adaptive policies and broader operator discovery remain follow-up work.
