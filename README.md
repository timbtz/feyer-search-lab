# Team search queue

Human-driven search; Qwen and SMAC are optional. See `.wiki/team-search.md` on main.

Claims and decisions live in this branch. Timing comparisons require the same instance and cohort.

| Task | Kind | State | Owner / instance | Parents |
| --- | --- | --- | --- | --- |
| inventory-search-frontier-v1 | diagnose | ready | — / — | f3139c71ae2a, 4c12600ce07d |

## Comparison regime

Current mode: **concurrent**, epoch 14.

Concurrent and unverified timing imports are exploratory and excluded from winner assessment.

Receipt: https://github.com/timbtz/feyer-search-lab/issues/6

User authorized expanded CPU capacity. Conservatively exclude new timing imports until all overlapping work drains and fresh serial confirmation begins; this admission does not assert that lane 2 has started.

## Scientific lineage

```mermaid
graph TD
  c0["05508471e6b6"]
  c1["211f65a5f18d"]
  c2["28566a64a9ef"]
  c3["39b23e3c6e84"]
  c4["3e94580ec446"]
  c5["423bcc4ad6e9"]
  c6["4c12600ce07d"]
  c7["7d1ccc59cef3"]
  c8["7d6f99624be6"]
  c9["96474bdd4d83"]
  c10["aa2b1ab44180"]
  c11["bb9a183fd64f"]
  c12["d09dc1d08fb0"]
  c13["e0a1dc69f495"]
  c14["e525ee5ee4ef"]
  c15["f3139c71ae2a"]
  c1 -->|explore| c7
  c2 -->|combine| c13
  c4 -->|explore| c5
  c5 -->|combine| c13
  c6 -->|combine| c2
  c10 -->|explore| c8
  c12 -->|explore| c0
  c12 -->|explore| c3
  c12 -->|explore| c4
  c12 -->|explore| c6
  c12 -->|explore| c9
  c12 -->|explore| c11
  c12 -->|explore| c14
  c12 -->|explore| c15
  c15 -->|combine| c2
```

Every edge records intended inputs, not proof of speedup.

Recorded jobs: 13. Decisions/events: 30.

## External research records

| Executor | Kind | Candidate | Target phases | Recorded status |
| --- | --- | --- | --- | --- |
| claude-noise-reuse | explore | f3139c71ae2a | unknown | completed |
| claude-noise-reuse | explore | e525ee5ee4ef | unknown | completed |
| claude-noise-reuse | explore | bb9a183fd64f | unknown | completed |
| claude-noise-reuse | explore | 96474bdd4d83 | unknown | completed |
| claude-noise-reuse | explore | 05508471e6b6 | unknown | completed |
| claude-noise-reuse | combine | 28566a64a9ef | unknown | completed |
| claude-structure-solve | explore | 4c12600ce07d | unknown | completed |
| claude-structure-solve | explore | 39b23e3c6e84 | unknown | completed |
| claude-structure-solve | explore | 3e94580ec446 | unknown | completed |
| claude-structure-solve | explore | 423bcc4ad6e9 | unknown | completed |
| layout-numerical-v2 | combine | e0a1dc69f495 | unknown | evaluated |
| codex-profile-guided-v1 | explore | 7d1ccc59cef3 | unknown | completed |
| claude-profile-guided-v1 | explore | 7d6f99624be6 | unknown | completed |
| claude-profile-guided-v1 | explore | unknown | compilation | current |
| codex-profile-guided-v1 | explore | unknown | compilation, forward | proposed |

These records are evidence, not competing task claims or winner declarations.
