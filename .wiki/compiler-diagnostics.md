# Compiler diagnostics

The `diagnostic` queue profile inspects the compiler structure of an exact candidate. It runs through the same durable queue, lane lock, pinned CPU, fixed Python environment, process-group timeout and sampled memory watchdog as ordinary evaluations. It never supplies a benchmark score or correctness promotion.

This is a separate diagnostic execution. The official `benchmark.py`, screening harness, physical inputs, three JIT boundaries and default worker environment remain unchanged. The harness imports the unchanged official benchmark's `forward_with_pullback`, `sensitivity_with_pullback` and `backward` functions, reconstructs its complete 101-frequency/193-parameter inputs, and lowers, compiles and executes each stage once. It synchronizes the full returned pytrees. It does not run warm repetitions, save a replacement baseline, or perform the official finite-difference check.

## What it captures

For forward, sensitivity and gradient separately:

- Instrumented lowering, compilation and first execution durations. These are diagnostic observations, never replacements for ordinary screen/full timing.
- StableHLO, pre-optimization HLO and optimized HLO text, where the backend supports them.
- Bounded opcode counts, largest textual subcomputations, and custom-call examples that include operand shapes. These can expose large dispatch graphs, factorization dimensions and repeated solve structure.
- Backend cost and memory analyses, or an explicit unavailable reason. These are estimates/inspection aids, not native operator timings or process peak RSS.

The `feyer-compiler-diagnostic-v1` JSON binds the exact clean candidate SHA, simulator file hashes, diagnostic harness digest, unchanged benchmark digest, fixture digests and execution environment. Its `ranking_eligible` is false. The worker records `verdict: diagnostic_completed` with `official_passed` and `regression_passed` unset, and **does not create `first_run_seconds`**. Existing scientific normalization rejects this profile, so it cannot enter the validated frontier or SMAC objective.

HLO text and each summary scan are capped at 2 MiB per representation. The report records original byte length, full-text hash, retained bytes, truncation, artifact name and compressed-artifact hash. There are at most nine `.txt.gz` exports plus a JSON summary capped at 1 MiB. Full untruncated text is not retained when it exceeds the cap. Remote retrieval uses fixed filenames and the existing 4 MiB per-file transfer limit; symlinks are excluded. Never treat partial opcode counts as counts for the entire program.

Native CPU traces, per-compiler-pass timing and Jaxpr exports are **not implemented** in this minimal profile. HLO instruction counts are not timing attribution. A follow-up trace is justified if IR identifies an ambiguity that the next algorithmic proposal cannot resolve.

## Deployment and ownership

Commit and test the complete diagnostic release before installing it. The release must include `lab/diagnostic.py` and the matching worker, queue, remote and client changes. Deploy only with the lane owner's coordination after its current evaluation finishes. Restart the idle worker on that same release; updating request-side code alone does not upgrade an already-running worker. Do not interrupt or restart a busy worker. Existing lane concurrency, environment, CPU assignments and agent deadlines do not change.

The client checks the remote `capabilities` action for this diagnostic schema before publishing or transferring a new candidate. An older server fails explicitly without substituting screen/full. This check identifies request-side support; the operator must still verify that the active worker uses the release. A requested diagnostic job on an outdated worker is not valid diagnostic evidence.

## Submit and inspect

After the coordinated deployment, use the checked-in client. Choose the exact scientifically relevant candidate, an owned branch containing it, the assigned lane root and a fresh persisted UUID. A diagnostic uses queue time and must fit the owning research budget.

```bash
python3 -m lab.client --host HOST_ALIAS --root LANE_ROOT submit \
  --repo OWNED_CANDIDATE_WORKTREE --branch OWNED_BRANCH \
  --sha EXACT_CANDIDATE_SHA --agent OWNER --direction compiler-inspection \
  --profile diagnostic --request-id PERSISTED_UUID \
  --hypothesis 'Inspect forward graph size and factorization shapes before an algorithmic rewrite'
python3 -m lab.client --host HOST_ALIAS --root LANE_ROOT wait JOB_ID
python3 -m lab.client --host HOST_ALIAS --root LANE_ROOT fetch JOB_ID \
  --output .lab/diagnostics/JOB_ID
```

Reuse the same UUID only when retrying the identical submission after an uncertain response. Deliberate repeated diagnostics get a new UUID. Do not invoke the diagnostic script directly on a shared evaluator outside queue ownership.

`status`/`wait` returns `diagnostic.json` alongside the job; `fetch` retrieves that summary and available compressed IR. Inspect `result.json` for resource/timeout failures even if partial artifacts exist. Successful diagnostic completion establishes only that the capture passed its provenance, environment and output-shape/finite sanity checks. It does not establish official or strict numerical correctness.

Pass the compact diagnostic summary and relevant IR excerpts to the existing agent as reference evidence. Record the exact source SHA and job. Ask for a specific structural mechanism—such as eliminating redundant factorization, reducing branch expansion, or retaining fewer AD residuals—and a separately evaluated successor. After changing code, ordinary screen/full jobs remain the only timing and correctness evidence. A competitor's reported execution/compile split is a hypothesis until workload and measurement scope are known.

## Implementation references

JAX's [ahead-of-time APIs](https://docs.jax.dev/en/latest/aot.html) expose lowered/compiled text and backend-dependent cost and memory analyses. [OpenXLA's HLO guide](https://openxla.org/xla/hlo_dumps) documents pre- and post-optimization representations and targeted compiler-pass dumps. The worker intentionally continues to remove inherited `JAX_` and `XLA_` environment settings; this profile does not enable dump flags, persistent compilation caches, or compiler optimization overrides.

If later evidence requires a CPU trace, the pinned [JAX 0.9.0 profiler source](https://raw.githubusercontent.com/jax-ml/jax/jax-v0.9.0/jax/_src/profiler.py) supports nonblocking Perfetto export. Such a capture needs its own bounded diagnostic implementation and remains excluded from the objective.
