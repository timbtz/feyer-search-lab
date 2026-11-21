# claude-guided-v2

- Branch: `explore/claude-guided-v2`. Exact start: `aa2b1ab44180af8dd1cd3a9796adb911b1a3986a` (claude-profile-guided-v1 candidate 5).
- Model: `claude-opus-5-5`. Managed session: no shell and no local runs; the supervisor commits and evaluates. Window: 3599 s at candidate 1.

## Starting evidence: aa2b1ab, full job `35abe628`

- Official PASS, strict PASS. Outputs are bitwise identical to the reference; gradient max absolute error 4.5e-13.

| Phase | Seconds |
| --- | --- |
| Complete first run | 21.550 |
| Imports | 0.293 |
| Build | 0.303 |
| Forward lower | 0.789 |
| Forward compile | 7.622 |
| Forward execute | 8.432 |
| Sensitivity lower + compile | 0.445 |
| Gradient lower | 0.181 |
| Gradient compile | 1.959 |
| Gradient execute | 1.519 |

- Warm median: 10.55 s.
- This is one observation in the concurrent epoch 14, cohort 10567ad0. It is exploratory.

## Owned combination: aa2b1ab build changes + Astra `7d1ccc59` — BLOCKED (source not inspectable)

- The managed file tools are confined to this worktree. There is no shell, and `.git` points outside the sandbox.
- As a result I cannot read Astra's (codex-profile-guided-v1 candidate 9) exact diff or its declared parents. No run JSON for it exists in this worktree.
- Per the rules (read exact diffs; do not merge blindly), I did **not** author the combination.
- What the shared feed shows for 7d1ccc5 (job `7e6ce3c3`, concurrent epoch 14, single observation):

  | Phase | 7d1ccc5 | aa2b1ab |
  | --- | --- | --- |
  | Total | 20.06 s | 21.55 s |
  | Build | 0.82 s | 0.30 s |
  | Forward compile | 3.31 s | 7.62 s |
  | Gradient compile | 4.06 s | 1.96 s |
  | Forward lower | 0.69 s | 0.79 s |
  | Gradient lower | 0.30 s | 0.18 s |
  | Forward execute | 8.60 s | 8.43 s |
  | Gradient execute | 1.52 s | 1.52 s |

- Build is clearly complementary. aa2b1ab's build gain (−0.5 s, attributed over 4 runs of the lineage) lives in `build.py`. Whether 7d1ccc5 touched `build.py` is unknown.
- **Needed from the coordinator to unblock:** the exact 7d1ccc5 diff against its parent, delivered into this worktree, for example as a file under `experiments/context/`.

## Candidate 1: rematerialize the per-row assembly loop body (`ASSEMBLY_REMAT=True`)

This is my own hypothesis. It is *not* a transfer of 7d1ccc5's code, which I could not read. It was motivated by 7d1ccc5's phase pattern: compile time moves from forward to gradient while execution is unchanged. That pattern is what remat of forward residuals would produce.

### Hypothesis
- **Target:** forward compile, 7.62 s in job `35abe628` (35% of the first run). It is the largest compile phase.
- **Mechanism:** the benchmark's forward stage is `jit(vjp(simulate))`. That means it compiles the primal *plus* the partial-eval of every linearization residual.
  - In the `"assemble"` loop (`lax.map` over 101 rows, k=1), every grouped component function's residuals (for example the sin/cos and exp factors of each component type) become stacked per-row scan outputs.
  - Wrapping the loop body in `jax.checkpoint(prevent_cse=False)` makes the forward scan emit only its outputs; the residuals are its inputs.
  - The reverse scan then recomputes the primal assembly per row before transposing.
- **Prediction:**
  - Forward compile and forward lower decrease, and gradient lower and compile increase. Forward execute changes slightly (fewer residual writes).
  - Gradient execute increases by the recompute of the assembly. That cost is unknown; it is component math, not LU.
  - The total improves only if the forward compile saving exceeds the gradient compile and execute increase. That is unknown. The 7d1ccc5 pattern (net compile −2.2 s) is an analogy, not evidence for this code.
- **Numerics:**
  - Forward outputs are expected to be bitwise identical: same primal ops, and the solves are untouched.
  - The gradient uses recomputed residuals from identical ops, so I expect it to stay at or near the 4.5e-13 level.
  - Any forward output difference, or a strict gradient failure (index 161 is the sensitive one), rejects the candidate.
- **Fallback:** `ASSEMBLY_REMAT=False`, which is byte-equivalent behaviour to aa2b1ab.
- **Source delta vs aa2b1ab:** `differometor/simulate.py` only — the new flag and a 4-line wrap of `block_assemble`. `build.py` is unchanged.

### Results
- Pending.
