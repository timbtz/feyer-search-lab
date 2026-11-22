# Overnight GitHub publication contract

The coordinator invokes `lab.overnight_publish`; managed optimization agents must not invoke it. The publisher owns only a dedicated, clean worktree on `control/overnight-20261122`. It never checks out or writes the main worktree or `experiments/submission`.

Initialize from the audited seed manifest:

```sh
python3 -m lab.overnight_publish init --worktree CONTROL_WORKTREE \
  --evidence-root TRUSTED_RUNNER_ROOT \
  --manifest experiments/campaigns/overnight-20261122/seed-manifest.json
```

After each trusted dual-evaluator receipt:

```sh
python3 -m lab.overnight_publish publish --worktree CONTROL_WORKTREE \
  --evidence-root TRUSTED_RUNNER_ROOT \
  --receipt TRUSTED_RUNNER_ROOT/requests/UUID/receipt.json
```

`CURRENT_BEST.md` links the exact simulator commit and the machine-readable `experiments/campaigns/overnight-20261122/current-best.json`. The initial record names seed53 with its historical dual-benchmark medians and **pending current-cohort calibration**. It is not silently promoted from inherited reports.

Each evaluation gets an immutable UUID directory beneath `experiments/campaigns/overnight-20261122/candidates`. It preserves the exact raw trusted-runner receipt, its SHA256, archived official reports and their hashes, candidate code link, prior best, selection decision and reasons. Faster but unadmitted candidates remain visible there, without moving current best. Reusing a UUID with different receipt bytes is rejected. The runner receipt should contain its generalization diagnostics, not merely an inaccessible local filename.

The accepted schema is `feyer-overnight-evaluation-v1`, with:

- `evaluation_id`, exact `candidate_sha`, `cohort_digest`;
- `admission.promotion_ready`, matching `admission.candidate_sha`, `admission.comparison_cohort_passed`;
- `benchmarks.grid.samples` and `benchmarks.aligo.samples`, each with seconds, exact candidate SHA, `fresh_process`, `official_passed`, report path under the trusted runner root and SHA256;
- `generalization.case_count` 14, `all_finite`, `inputs_identical`, `seed_comparison_passed`, and `new_failures`;
- `inherited_caveats`/`caveats`, preserving known pristine-reference disagreements.

New winners additionally require `source_review` with approved=true, matching candidate SHA, parent SHA, diff SHA256, reviewer/provider/model/session ID, scope `no-fixture-specialization-and-integrity`, review artifact path+SHA256, and reviewed diff path. Both files must be inside the trusted evidence root. Their bytes and metadata are cross-checked and archived. Tests alone are not evidence of non-specialization. Missing or rejected review leaves the candidate provisional with `requires_source_review`; matching known-seed calibration is exempt. Complete the independent review before first publication, or issue a new immutable evaluation/publication UUID referencing the original evaluation for later reviewed admission; never mutate an already published UUID.

The evidence root is a coordinator-controlled directory outside candidate-owned worktrees. This path boundary and runner ownership establish the trust model; a boolean supplied by candidate code is not sufficient. The publisher checks report byte hashes, clean exact source, reported official verdicts, full workload and timing consistency. It does not rerun mathematics or redefine the evaluator's seed-comparison tolerances. The evaluator decides numerical admission, including appropriate treatment of near-zero reference outputs.

Search selection requires runner admission, all14 cases finite with identical inputs and acceptable seed comparison, no unresolved new failures, at least three distinct fresh official repetitions on each benchmark, matching comparison cohort, and relative timing range at most10%. After fresh seed calibration, replace best only if the large-case median improves by at least `max(0.003 seconds, 0.5%)` and aLIGO median is at most `1.02 × current best`. The larger benchmark remains primary; no averaged competition score is invented. These are team selection heuristics, not organizer judging rules. Inherited seed caveats remain explicit after promotion.

A filesystem lock serializes the two worker hooks. Each transaction first persists its intended bytes in the worktree's Git metadata, then atomically replaces local files, commits only owned paths, and pushes the control branch. Git is the consistent published snapshot boundary. Process death before or just after commit is recoverable; unknown branch movement or unrelated dirty files fail closed. A failed push leaves a durable outbox and returns `published:false`/exit2. It must not be described as a successful GitHub update. Retry without another model call:

```sh
python3 -m lab.overnight_publish retry --worktree CONTROL_WORKTREE \
  --evidence-root TRUSTED_RUNNER_ROOT
```

Retries preserve UUID and commit; no force push or history reset is used. A pending rejected push blocks later publication until repaired. The coordinator owns GitHub issue updates and may link the stable `CURRENT_BEST.md`; this module does not send messages or edit issues.

## Selection-v2: overlapping timing ranges stay provisional

For future promotions, `overnight-selection-v2` additionally requires the candidate's **largest** observed complete large-benchmark first-run time to be strictly below the incumbent's **smallest**, in the same comparison cohort. A few-millisecond median reduction is insufficient when incumbent samples already vary by tens of milliseconds. The existing minimum-gain, aLIGO regression, spread, numerical and source-review gates remain in force. Missing incumbent range evidence fails closed.

This is a deliberately conservative observed-range heuristic, not a confidence interval, a statistical guarantee, or an organizer judging rule. Passing it does not prove universal speedup. An overlapping candidate remains published as provisional with reason `large_first_run_ranges_overlap_requires_paired_evidence`; its source and measurements are retained. Further controlled paired measurements and review may justify a later decision, but merely accumulating more overlapping samples does not waive this gate. No extra evaluations are automatically launched by the publisher.

The known seed's initial fresh calibration remains eligible, and older admission receipts are not rewritten. New records identify policy-v2 explicitly; existing runs and deployed runtimes are untouched until the coordinator adopts the new publisher.
