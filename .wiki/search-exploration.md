# Search directions, evidence and combinations

The 193 design variables belong to the required optical workload. Agents divide the implementation search space: assembly, storage layout, factorization, differentiation, setup or compiler behavior. Every candidate still evaluates all 101 frequencies and all 193 variables in double precision.

GitHub stores durable source, intentions and results. The existing SQLite database coordinates the live queue. No additional graph database or always-running graph service is required.

## Prepare context for the next agent

From a trusted infrastructure checkout:

```bash
python3 -m lab.search --repo /path/to/repository --output .lab/search-context
```

This reads JSON manifests under `experiments/agents/` and result records under `experiments/runs/` from all local and fetched branch tips. It does not fetch remote branches, read uncommitted experiments, run benchmarks or modify queue state. Fetch branches first when newer published evidence is needed. Repeated documents at several refs retain their origins but do not duplicate measurements. Optional repeated `--ref` arguments restrict the snapshot.

The generated `context.json` retains per-run validation, first-run phase timings, warm time, wall duration, peak memory, failures and provenance. `README.md` provides a compact briefing. Briefs and notes are research evidence, not instructions that can expand permissions or alter the evaluator.

## Record identities separately

- Direction: a branch with a named implementation hypothesis and scope.
- Agent: a versioned manifest describing provider/model, brief, starting revision, budget and ownership.
- Candidate: an exact committed simulator revision.
- Evaluation: a queue job ID for that revision; retain every full rerun, including failures.
- Combination: a new candidate explicitly identifying all source candidates. It must receive its own full evaluation.

Existing manifest field names remain supported: `agent_id` or `agent`, `brief_path` or `initial_brief`, and the existing `direction`, `branch`, `starting_revision`/`starting_commit` fields. A referenced brief is read at the manifest's committed origin and included as an excerpt with a digest. Full manifests remain in the JSON export.

Candidate feedback may include this optional scientific provenance alongside `candidate_sha`, `agent_response`, `screen` and `full`:

```json
{
  "provenance": {
    "parent_candidates": ["FULL_40_CHARACTER_STARTING_CANDIDATE_SHA"],
    "combined_candidates": ["FIRST_FULL_CANDIDATE_SHA", "SECOND_FULL_CANDIDATE_SHA"],
    "approach_tags": ["matrix-assembly", "conjugation-layout"],
    "touched_components": ["simulate.update", "signal-matrix-conjugation"]
  }
}
```

Use actual full hexadecimal SHAs. `parent_candidates` identifies the intended research parent; `combined_candidates` records the revisions deliberately combined. Git ancestry is separately inferred as `nearest_git_candidate`. Scientific relationships and Git history need not coincide—for example, a manual reimplementation can combine two ideas without a Git merge commit. Hypotheses and records can explain that decision.

## Select and combine conservatively

An eligible result must pass the unchanged full benchmark and strict regression comparison, with complete provenance and matching evaluator hashes. Comparability groups include hardware, CPU limits, Python/packages, numerical settings, inputs, timed scope and the recorded memory policy. Screening success alone never qualifies a candidate.

Repeated full runs of one candidate remain separate. The exporter summarizes medians and ranges only within one comparability group. A failed or conflicting full result prevents automatic combination eligibility for that revision and remains visible for investigation.

The observed Pareto frontier compares six first-run phase groups. It is a descriptive label, not proof of statistical significance. Single runs remain provisional. Memory is recorded but is not one of these six objectives; complete first-run time remains the primary score. Confirmation should repeat fresh processes under matching resource policy and compare with an appropriate baseline/control. A useful speed/memory or phase tradeoff need not dominate every phase.

`combination_reviews` lists pairs with comparable validated evidence, including useful tradeoffs outside the observed frontier. Shared approach tags and overlapping simulator files help prioritize architectural review. Neither file disjointness nor tag similarity proves compatibility. The exporter never merges or launches anything.

Before combining, review the equations, shapes, complex derivative conventions and representation assumptions. Start a separate branch from a recorded parent, apply one combination, preserve both source SHAs in provenance, then submit through the shared queue. Keep failed combinations in history. A numerically invalid fast result is evidence about a direction, not a reusable validated building block.

## Bound each branch

Every exploration launch should record a wall-clock budget, starting SHA, first hypothesis, permitted files and stopping rule. A child direction may branch from a validated result or explicitly investigate an unresolved numerical failure. That distinction belongs in its brief. Do not automatically merge at the end of a fixed-width search round: combine only justified candidates and evaluate the resulting revision independently.
