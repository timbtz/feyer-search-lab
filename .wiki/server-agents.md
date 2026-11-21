# Server supervisor migration

The portable runtime adds `--agent-provider codex|claude`, `--transport ssh|local`, `--queue-root`, `--brief` and `--manifest` to the audited supervisor. LocalClient invokes the deployed trusted queue protocol in a separate process; it does not start an evaluator or import an evaluator from a candidate checkout. New requests retain durable request IDs before submission. GitHub publication remains required; a missing gh command only skips optional commit-status badges, not Git pushes.

Runtime commit/path, provider/model, brief hash, declared parent/combination candidates and session identity are recorded in session state and candidate feedback. `python3 -m lab.search --repo PATH --output DIR` reconstructs a search-context snapshot from committed branch records. Every candidate is an exact SHA; directions have branches; runs have job IDs. The 193 optical parameters are a fixed required workload, not a partition of the optimization search space.

## Current readiness

The AMD evaluator remains on audited release 861601b and is unchanged by migration. The shared queue is serial on CPU2 with the existing sampled 32e9-byte RSS budget, not a kernel memory reservation. Agent CLI work should avoid CPU2 and its SMT sibling; benchmark affinity must not change.

The server's outbound proxy denied chatgpt.com and claude.ai; API probes to OpenAI failed and Anthropic returned `Request not allowed`. Installation does not establish authenticated inference. Fresh server authentication and successful inference are required before transferring branch ownership. Do not copy laptop tokens or private keys or bypass network policy. GitHub publishing access must also be independently provisioned and tested.

Until those checks pass, existing local sessions may continue on the audited runtime. Preserve conversation IDs, outstanding job IDs, uncommitted edits and the original deadline during handoff. Never run two supervisors on one branch. A new Codex direction is prepared in experiments/briefs/codex-component-specialization.md; it must not be reported as running until a live session is verified.

## Evidence-driven exploration

Use bounded branches for distinct implementation approaches. Keep failed trials. After an exploration wave, review complete first-run totals, phase tradeoffs, memory, correctness and repeatability within matching measurement cohorts. Prioritize repeatably useful parents; do not make an automatic merge solely because a point appears on a noisy Pareto frontier or two changes touch the same parameters. Create a separate combination branch with both parent SHAs and compatibility notes, then revalidate the combination from a fresh process. The context exporter prepares input for an orchestrator; it does not automatically launch agents or merge branches.
