# Claude headless supervisor

Claude Code 2.1.323 is installed on the Mac and authenticated through the user's Claude account. Credentials stay in Claude's local credential tooling; none are sent to AMD or Git.

`lab.agent_loop --agent-provider claude` uses the same commit guards, serial queue, screen/full promotion, feedback files, locks and deadlines as the Codex path. `--agent-model claude-opus-5-5` selects the explicitly requested model. `--brief` selects a direction-specific brief. Session provider and model are saved and cannot silently change during resume.

The CLI is a local process, not a Docker container. It uses restricted file tools and an explicit edit allowlist for differometor/** and experiments/notes/**. Shell execution, subagents and MCP tools are unavailable. Safe mode disables optional customizations; administrator-managed policies still apply. The supervisor validates changed paths before committing. There is no per-agent RAM cap. The AMD evaluator runs in the existing cloud container and remains serial on CPU 2.

A live connection test verified file reading, schema-validated output and continuation of the same session with supplied feedback. Unit/integration tests cover provider selection, guarded edits, candidate submission and feedback using a fake evaluator. No real Claude optimization candidate has yet passed the AMD queue.

Initial launch uses experiments/claude-linear-algebra.md, requiring an investigation and proposed experiment before any simulator edits, then allowing evidence-backed candidates within the new 60-minute session. Logs and session state remain under .lab/sessions/claude-linear-algebra/. At the deadline, preserve notes and session identity. Extending the session requires explicit resumption. Do not attach an interactive writer to a live supervised session; first let it finish. For an idle session, `claude --resume SESSION_ID` in the same worktree reopens the conversation.
