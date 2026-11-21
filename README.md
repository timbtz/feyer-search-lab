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
  c1["10a311f6dbe4"]
  c2["211f65a5f18d"]
  c3["28566a64a9ef"]
  c4["39b23e3c6e84"]
  c5["3b805077bb5c"]
  c6["3e94580ec446"]
  c7["423bcc4ad6e9"]
  c8["4c12600ce07d"]
  c9["5b2169697d35"]
  c10["633689f9bf05"]
  c11["7d1ccc59cef3"]
  c12["7d6f99624be6"]
  c13["96474bdd4d83"]
  c14["aa2b1ab44180"]
  c15["bb9a183fd64f"]
  c16["d09dc1d08fb0"]
  c17["d947905c9b73"]
  c18["e0a1dc69f495"]
  c19["e525ee5ee4ef"]
  c20["f3139c71ae2a"]
  c1 -->|explore| c5
  c2 -->|explore| c11
  c3 -->|combine| c18
  c5 -->|explore| c10
  c6 -->|explore| c7
  c7 -->|combine| c18
  c8 -->|combine| c3
  c9 -->|explore| c1
  c14 -->|explore| c9
  c14 -->|explore| c12
  c16 -->|explore| c0
  c16 -->|explore| c4
  c16 -->|explore| c6
  c16 -->|explore| c8
  c16 -->|explore| c13
  c16 -->|explore| c15
  c16 -->|explore| c19
  c16 -->|explore| c20
  c20 -->|combine| c3
```

Every edge records intended inputs, not proof of speedup.

Recorded jobs: 13. Decisions/events: 42.

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
| claude-guided-v2 | explore | 10a311f6dbe4 | unknown | completed |
| claude-guided-v2 | explore | 3b805077bb5c | unknown | completed |

These records are evidence, not competing task claims or winner declarations.
