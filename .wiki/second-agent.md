# A second interactive agent

The existing manual worktree is `/Users/t.betz/Documents/Feyer challenge agents/claude-first-pass`, on `explore/claude-first-pass`. It is separate from the supervised `codex-seed` worktree. The repository remote is shared by Git worktrees and now points to `timbtz/feyer-search-lab`.

To open Claude there:

```bash
cd '/Users/t.betz/Documents/Feyer challenge agents/claude-first-pass'
claude
```

To fork a Codex conversation into a newly managed worktree, the installed CLI supports:

```bash
codex fork --all --worktree -C '/Users/t.betz/Documents/Feyer challenge'
```

Choose the intended conversation in the picker; avoid `--last` because the supervised agent also creates activity. Forking conversation history alone does not isolate files. The in-app fork created from this conversation uses the same directory until the new session explicitly moves its work to a separate worktree.

Suggested first message:

> Help me explore another Feyer optimization direction. First discuss ideas with me and explain the existing measurements. Before editing, use a separate worktree and branch. Read the current main checkout's AGENTS.md and .wiki/runbook.md; older agent branches may contain superseded four-candidate instructions. Pick a direction distinct from the running agent. Preserve the official benchmark, all 101 frequencies, 193 variables and double precision. Commit each focused candidate to your own branch and submit through the shared evaluation queue. Use screen for early feedback and full validation before claiming correctness. Inspect phase timings, numerical differences and Pareto tradeoffs. Do not edit the supervised codex-seed worktree, shared environment or evaluation infrastructure. Keep credentials out of commits.

The manual client commands are in the runbook. A manually launched agent does not automatically join the supervised Codex conversation or acquire its feedback loop; it must submit and wait through the client as instructed. Both agents share the serial AMD evaluator, so jobs may wait in the same queue.
