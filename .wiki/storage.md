# Storage and retention

The persistent `/workspace` filesystem was measured at **98 GB total, 2.2 GB used and 91 GB available** during setup. The larger filesystem reported for `/` is ephemeral shared infrastructure and is not the persistent storage budget.

## Current use

| Item | Approximate size at setup |
| --- | ---: |
| Feyer virtual environment | 753 MB |
| Baseline checkout and artifacts | 38 MB |
| Separate working checkout | 34 MB |
| Downloaded Python wheels | 164 MB |
| VS Code installation | 758 MB |
| VS Code transfer chunks | 233 MB |
| Verified VS Code archive | 233 MB |

The transfer chunks and archive are setup artifacts. They can be removed after the operator confirms that the persistent VS Code installation works and no recovery operation needs them. Cleanup has not been assumed or performed by this document.

## Retention policy

- Reuse the pinned Python environment for code-only experiments. Do not copy it into every worktree.
- Keep source commits, research notes, compact timing reports, logs and plots for every experiment.
- Preserve full arrays for the original baseline, validated improvements and numerical investigations. Other large artifacts can be pruned after their summaries are retained.
- Remove completed evaluation worktrees after preserving their results and commit references. Keep active agent worktrees and uncommitted work.
- Preserve enough queued and completed commit references that cleanup cannot remove code still needed by a run.
- Check free space before accepting work and leave headroom for compilation, temporary arrays and reports. A suggested initial reserve is 10 GB; the operator should enforce and adjust it based on actual use.

Git worktrees share history but each still occupies space for its checked-out files. The principal savings come from sharing dependencies and avoiding redundant images, environments and large artifacts.

## Persistence and backup

Keep queue state, worker configuration, agent worktrees, reports and environment records under `/workspace`. Persistence protects against instance recreation only when persistent workspace storage was selected at launch. It does not replace a separate backup.

Push commits and notes to the private GitHub repository. Copy important result artifacts to a laptop or another approved destination. Do not commit virtual environments, package caches, credentials, API keys, private SSH keys or unrestricted agent session logs.
