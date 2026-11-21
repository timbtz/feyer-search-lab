# Hetzner proposer execution

The developer account on `Hetzner-VPS-Dev` already has working Codex and GitHub authentication. A real no-tools Codex call succeeded on 2026-11-21. Existing EvoHarness services are separate and remain unchanged. Feyer's host processes use no new Docker containers.

## Responsibilities and capacity

The broker runs one assigned proposer turn at a time. The DAG coordinator chooses directions, owns actor claims and rounds, validates receipts and submits accepted proposals to the trusted AMD queue. The broker does not freeze rounds, decide Pareto promotion, alter the evaluator, run physics locally or extend old sessions.

Both screen and full benchmarks stay on AMD. Screen still evaluates the complete physical workload and can consume roughly 13–14 GiB; it is not a small local solver. The inspected VPS has about 7.6 GiB RAM with about 3.8 GiB available, and its existing 4 GiB swap was fully occupied. The new service therefore requires 2 GiB available before starting an assignment, has one agent slot, a 1.5 GiB cgroup memory maximum, no swap allowance, and one CPU equivalent. These are native process resource controls, not a container. They cover the broker and its descendants, not unrelated existing services. Actual usage and OOM events must be monitored before raising capacity.

## GitHub transport

Operator-owned assignments are read from `control/hetzner-assignments`, beneath `assignments/hetzner-codex-1/`. They follow `feyer-dag-task-v1` from the coordinating `infra/search-dag` branch: task UUID hex, campaign and round identity, immutable parent SHAs, brief/context paths plus commits and SHA-256 hashes, actor and claim version, provider/model policy, one-turn deadline, narrow allowed paths and kind.

The first parent is the checkout base. Each fresh assignment gets a fresh `explore/hetzner/*` branch and its own worktree. Guidance permits notes only; candidate tasks can edit only the registered simulator and notes paths. The operator must explicitly assign the task; arbitrary GitHub issues and PR comments are not launch instructions. This transport assumes the assignment branch is controlled by trusted operators. It is not an authorization service for untrusted contributors.

The broker creates `worker-claims/hetzner-codex-1/TASK_ID` atomically through GitHub before executing. This prevents two hosts from claiming the same task. The coordinator's claim version is a separate authority: the broker never grants or renews it, and ingestion must reject stale claims or rounds.

Successful candidates, briefing copies and responses are committed to the assigned branch. A dedicated `worker-results/hetzner-codex-1/TASK_ID` branch contains `receipt.json`, including exact candidate and publication SHAs, parent/context/brief identities, session/runtime/model evidence, token counts, changed paths and parameters. It is marked `not_evaluated`; only the coordinator may attach trusted evaluator results. Failed owned tasks get a failure receipt. Raw CLI transcripts remain under the server's private task-state directory.

Task IDs and contents are immutable. Publication retries reuse the already committed revision. Interrupted or uncertain coding turns are not automatically repeated or given new time: their state requires operator review and a new authorized assignment. A completed task is never relaunched just because its file is still present. A provider login failure is a failed execution, not a successful proposal.

## Process lifetime

The user systemd service is `feyer-proposer.service`, with sources in `ops/hetzner/`. The developer account has lingering enabled, so the service can survive SSH logout and laptop shutdown. It polls every 30 seconds; no task means no model call. The runtime is a pinned checkout at `/home/developer/feyer-agents/control`, with state and isolated worktrees under `/home/developer/feyer-agents/state`.

```bash
systemctl --user status feyer-proposer
journalctl --user -u feyer-proposer -n 50 --no-pager
systemctl --user show feyer-proposer -p MainPID -p MemoryCurrent -p MemoryMax -p MemorySwapMax
```

The user owns `~/feyer-agents/broker.json`; it contains no credentials. The broker uses the account's existing Codex and GitHub credential tooling. A task can specify a model, or explicitly inherit the designated model recorded in that configuration. It does not implicitly change models or use another account.

## AMD connection

The dedicated `feyer-amd-evaluator` SSH alias pins the already verified AMD host key. Its private key was generated on Hetzner and stays there. On AMD the public key is source-restricted and forced through `lab/evaluator_ssh_relay.py`, permitting only trusted queue RPC and bounded bundle uploads. General shell commands, forwarding and PTYs are unavailable through that key. Existing laptop/team access is unchanged.

Queue access can be checked from the trusted control checkout with:

```bash
python3 -m lab.client --host feyer-amd-evaluator list
```

Do not run the benchmark directly on Hetzner. The broker itself does not submit evaluations; the coordinator uses the same audited client and durable request IDs when scheduling AMD work.
