# Operator runbook

The local repository is `/Users/t.betz/Documents/Feyer challenge`. The existing SSH alias is `amd-hackathon`. The AMD instance runs Linux, and its persistent working directory is `/workspace`.

## Connect

```bash
ssh amd-hackathon
```

In VS Code Remote Explorer, select `amd-hackathon`. The `orb` entry belongs to local OrbStack. The established remote working copy is `/workspace/work`; use an agent's separate worktree for an isolated experiment.

Each teammate uses their own private key. Adding a public key to the running instance's `authorized_keys` grants that key access immediately; adding it only to the Radeon Cloud account after launch does not install it in the existing instance. Do not share a private key.

SSH local forwarding to the instance's loopback addresses was explicitly approved and enabled for VS Code. Forwarding to other hosts remains disallowed. VS Code files are stored beneath `/workspace/.vscode-server` so persistent storage can retain them across instance recreation. The active SSH daemon configuration is outside `/workspace`; recheck forwarding after a relaunch.

## Python environment

The fixed evaluation environment is `/workspace/venv-feyer`. For manual inspection in a remote terminal:

```bash
source /workspace/venv-feyer/bin/activate
```

The evaluator should invoke that environment's Python by its absolute path. Do not install packages into the environment during an evaluation or change dependencies for one candidate without creating a separately identified environment and matching baseline.

The challenge benchmark uses the CPU. The image's separate PyTorch/ROCm installation was verified with the library paths supplied by `/workspace/activate-rocm.sh`. That helper is for the image's GPU tools; it does not install PyTorch in the Feyer virtual environment.

## Start an experiment

1. Assign a direction, one branch and one agent identifier.
2. Create a separate agent worktree from the agreed starting commit.
3. Read `AGENTS.md`, the direction brief and prior findings.
4. Make one focused change. For a managed agent, the supervisor checks the allowed paths, commits and pushes the candidate. Manual operators commit their changes and submit through the client.
5. Submit the full commit SHA with the direction, agent identifier, hypothesis and `screen` profile. The local client relays a Git bundle over SSH; no personal GitHub token is copied to the instance.
6. Wait for the run's recorded result. Inspect failures before submitting another candidate.
7. Send a promising candidate through `full`, then compare it with the matching baseline.
8. Record the decision and next idea in `experiments/notes/`.

## Client and supervisor commands

The client is deployed and the unchanged screening baseline has passed through the queue. Run these commands from the team repository so the `lab` module is available.

```bash
python3 -m lab.client submit \
  --repo '/path/to/agent-worktree' \
  --branch explore/seed-agent \
  --agent seed-agent \
  --direction first-pass \
  --profile screen \
  --hypothesis 'Defer plotting imports until visualization is requested'

python3 -m lab.client status JOB_ID
python3 -m lab.client wait JOB_ID
python3 -m lab.client list
```

Submission defaults to that checkout's `HEAD`; the resulting run must record its full SHA. The client defaults to `amd-hackathon` and `/workspace/feyer-lab`; override them with the global `--host` and `--root` options before the command.

The first supervised agent uses a separate worktree:

```bash
python3 -m lab.agent_loop \
  --repo '/Users/t.betz/Documents/Feyer challenge' \
  --worktree '/path/to/separate-seed-worktree' \
  --branch explore/seed-agent \
  --max-minutes 60 \
  --name seed-agent
```

The supervisor handles allowed-path checks, commits, candidate publication, submission and feedback. Its agent edits files and returns the required structured response without making Git commits or GitHub/SSH calls. Do not also submit its commits manually. It resumes the saved Codex conversation after evaluations; keeping the same operating-system process alive is not required for continuity.

Do not infer that an enqueued run has started or that process completion means all correctness checks passed.

## Inspect and resume

Inspect the queue for the run identifier returned at submission. Read that run's log and report, then its saved arrays when a numerical comparison is needed. A branch's latest commit may differ from the commit under evaluation.

The existing `hack` tmux session can be inspected with:

```bash
tmux attach -t hack
```

A managed worker should have a dedicated process/session and log. After a disconnect or restart, check whether a worker is already alive before starting another one. The global worker lock is an additional guard against duplicate evaluation.

Resume an agent using its saved session identifier, original worktree and branch. Read its last notes and outstanding run status first. Do not silently give the same branch to a second live agent.

## Recovery

| Symptom | Action |
| --- | --- |
| GitHub fetch fails | Leave the candidate unacknowledged or visibly failed; retain its local commit and retry the transfer. Never evaluate a different revision as a substitute. |
| Worker stops during a run | Inspect the heartbeat and process state; record interruption and explicitly queue a new run. |
| Evaluation times out | Retain logs and the candidate SHA; inspect the bottleneck before changing the timeout. |
| Memory pressure or killed process | Stop increasing concurrency; record the failure and peak memory evidence before retrying. |
| Correctness fails | Keep the failed result; examine sensitivity and array differences before pursuing its timing result. |
| Protected files changed | Restore the benchmark, fixtures or dependency files; submit a new commit. Do not weaken the guard. |
| Agent exits while waiting | Keep the evaluation running; resume the same agent session with the resulting run identifier. |

## Back up and stop

Push agent commits and written findings regularly. Copy valuable result artifacts off the instance; persistent storage is not an independent backup. Keep API keys and credentials out of Git.

Destroying the instance stops compute billing. Closing SSH, VS Code or the browser does not. Before destroying it, stop workers cleanly, save agent session identifiers, push work and copy the important results.

## Agent worktrees

The manual Claude worktree is `/Users/t.betz/Documents/Feyer challenge agents/claude-first-pass`, on branch `explore/claude-first-pass`. Claude Code is installed locally. Run it from that directory and give it `experiments/initial-agent.md` as its starting brief; specify that it is a manual agent and should commit and submit through the client. Do not run a second agent in the same worktree.

The supervised Codex worktree will be `/Users/t.betz/Documents/Feyer challenge agents/codex-seed`, on `explore/seed-agent`. Its supervisor handles commits and evaluation. The two workflows share the serial AMD queue.

## Worker deployment

`python3 -m lab.deploy` uploads the committed evaluator files and starts the worker in the remote `feyer-worker` tmux session. Releases are immutable directories under `/workspace/feyer-lab/releases`; the active worker resolves its trusted evaluator directory at startup. Deployment refuses to switch an already-running worker. Inspect `state/worker.log` and stop an idle worker before updating it. Do not terminate it during an evaluation.

## Supervised session status and recovery

The live local state is `.lab/sessions/seed-agent/status.json`; the process log is `.lab/sessions/seed-agent/supervisor.log`. Each Codex turn has a JSONL event log, stderr log and structured response in that directory. Agent transcripts stay local; measured evaluator summaries are committed under `experiments/runs/seed-agent/` and linked from GitHub commit statuses.

There is no candidate-count limit by default. The session starts no new coding turn or submission after 60 minutes. An already-submitted evaluation may finish and save feedback after that deadline. A lost connection does not cancel remote evaluation.

To resume, run the same `lab.agent_loop` command with `--resume`. It restores the saved conversation and reconciles pending jobs before new coding. Explicit resumption grants the requested new time window; the candidate count continues. Omit `--max-candidates` for no count limit; optionally supply it to bound a different session. Session and worktree locks prevent duplicate supervisors.

For the initial run use `--baseline-seconds 36.177949`, the measured screening calibration. The first successful candidate gets full validation; later candidates get full validation when screening is within 2% of that baseline or faster. This is an exploration gate, not a claim that a small timing difference is a speedup.
