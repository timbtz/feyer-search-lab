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
  c4["3b805077bb5c"]
  c5["3e94580ec446"]
  c6["423bcc4ad6e9"]
  c7["4c12600ce07d"]
  c8["5b2169697d35"]
  c9["633689f9bf05"]
  c10["7d1ccc59cef3"]
  c11["7d6f99624be6"]
  c12["96474bdd4d83"]
  c13["aa2b1ab44180"]
  c14["bb9a183fd64f"]
  c15["d09dc1d08fb0"]
  c16["d947905c9b73"]
  c17["e0a1dc69f495"]
  c18["e525ee5ee4ef"]
  c19["f3139c71ae2a"]
  c1 -->|explore| c10
  c2 -->|combine| c17
  c4 -->|explore| c9
  c5 -->|explore| c6
  c6 -->|combine| c17
  c7 -->|combine| c2
  c13 -->|explore| c8
  c13 -->|explore| c11
  c15 -->|explore| c0
  c15 -->|explore| c3
  c15 -->|explore| c5
  c15 -->|explore| c7
  c15 -->|explore| c12
  c15 -->|explore| c14
  c15 -->|explore| c18
  c15 -->|explore| c19
  c19 -->|combine| c2
```

Every edge records intended inputs, not proof of speedup.

Recorded jobs: 13. Decisions/events: 40.

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
| codex-profile-guided-v1 | explore | unknown | compilation, forward | current |
| layout-numerical-v2 | refine | unknown | unknown | menu_exhausted |
| layout-numerical-lane1 | refine | unknown | unknown | budget_exhausted |
| astra-independent-v1 | explore | unknown | unknown | current |
| claude-guided-v2 | combine | unknown | setup, compilation | current |
| astra-guided-v2 | explore | unknown | compilation, forward, gradient | current |
| astra-group-numerical-v3 | refine | unknown | gradient_compile, forward_compile, gradient, forward | current |
| claude-guided-v2 | explore | 633689f9bf05 | unknown | completed |
| claude-guided-v2 | diagnose | unknown | unknown | current |
| claude-guided-v2 | explore | 5b2169697d35 | unknown | completed |

These records are evidence, not competing task claims or winner declarations.
