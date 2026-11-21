# Codex profiler-guided session v1

## Launch and ownership

- Session name: `codex-profile-guided-v1`; conversation `01a1ffba-57ec-7191-8ba9-c6163633a3b3`.
- Branch: `explore/codex-profile-guided-v1`.
- Worktree: `/Users/t.betz/Documents/Feyer challenge/.lab/worktrees/codex-profile-guided-v1`.
- Scientific seed and retained best eligible revision: `96474bdd4d83bb02c163640f63fae1c4bd7a21d4`.
- Launch source: `/Users/t.betz/Documents/Feyer challenge/.lab/sessions/codex-profile-guided-v1/launch.json`, read before edits. Model `gpt-6-astra`, reasoning `high`, pinned by supervisor wrapper.
- Start Unix `1795291764.088367`; absolute deadline Unix `1795295364.088367`, **2026-11-21 21:09:24.088367 UTC**. New independent 60-minute budget, no candidate-count cap; includes evaluation and queue time. No older budget extended.
- Supervisor runtime commit `3176d58b44014d33d138492d72756531b7670040`; control commit `c3ada6070e2b9690845d07ea2b4e3c58be35093e`; brief SHA256 `e0fce937e4eab2716daf570efda98f0836e2e86124b69dbcc1cbd195dd7e7bb6`.
- Read `AGENTS.md`, `.wiki/README.md`, `experiments/initial-agent.md`, retained noise-reuse notes and relevant component-specialization/frequency-batching history. The current request supersedes the old four-candidate cap in the initial brief.
- Independent Claude initially owns noise-contraction scheduling. This first change addresses structural matrix indexing; it does not alter contraction scheduling or solve algorithms. No other branch edited.

## Exact-parent evidence

Source: supervisor `feedback.full`, job **`ab12c14c29354bad9aa6dc024c91f8e6`**, profile **full**, exact SHA `96474bdd4d83bb02c163640f63fae1c4bd7a21d4`. Profiler schema `feyer-profiler-feedback-v1` / `feyer-profiler-v1`, cohort digest `10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c`. Launch profile source `/Users/t.betz/Documents/Feyer challenge/.lab/audits/claude-window-confirmation-v1/ab12c14c29354bad9aa6dc024c91f8e6.json`. User reports three exact-SHA full passes with median 22.365550714 s; only this run's detailed attribution is supplied.

Official and strict regression pass; resource/source/workload/precision checks pass. Complete first run **22.365550714 s**; warm median **10.609400719 s** (10.295973090–10.619015552); worker job wall **88.068521352 s**. GNU time peak RSS **8,127,128 KiB**, sampled process-group peak **8,323,227,648 bytes**, below 32,000,000,000-byte budget. These are separate metrics, not interchangeable.

All 14 first-run phases, seconds:

| Phase | Seconds | Share where relevant |
| --- | ---: | ---: |
| Imports | 0.296916710 | 1.33% |
| CPU initialize | 0.003079884 | |
| Input load | 0.001589352 | |
| Build/prepare | 0.821073705 | 3.67% |
| Forward trace/lower | 0.824146703 | 3.68% |
| Forward compile | 7.633823741 | 34.13% |
| Forward execute + AD residuals | 8.608745126 | 38.49% |
| Sensitivity trace/lower | 0.092092374 | |
| Sensitivity compile | 0.459229367 | |
| Sensitivity execute | 0.000863161 | |
| Gradient trace/lower | 0.187000735 | |
| Gradient compile | 1.961982764 | 8.77% |
| Gradient execute | 1.474652428 | 6.59% |
| Host transfer | 0.000354663 | |

Combined trace/lower/compile **11.158275684 s (49.89%)**. Ranking: forward execution, forward compilation, gradient compilation, gradient execution, forward lowering, build. No native-operation timing or internal scatter attribution is available. Prior notes' interpretations about counts of factorizations are hypotheses/history, not new operator measurements.

Saved-array strict comparison: carrier, signal, noise, sensitivity, powers, parameters and frequencies all have max absolute error, relative L2 error, max normalized error and failing count **0**. Gradient max absolute error **5.093170329928398e-10**, relative L2 **7.576529280174932e-15**, max normalized error **6.039550882495327e-7**, failing count **0**, no mismatch indices/details; finite throughout. Parameters/frequencies require exact equality. Strict rtol `1e-7`, scale_atol `1e-12`; saved scope is last warm evaluation. Gradient has all 193 coordinates; outputs retain complex128/float64. Official log-sensitivity max error `5.374104176780747e-6`; finite-difference spot check also passes but is not substituted for full-gradient comparison. Seed margin is comfortably away from strict failure.

Evaluation provenance: evaluator release `861601b9c5d31390caca420b078f09ff7ad83156`; evaluator SHA256 `d5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e`; worker SHA256 `d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58`; comparison evaluator SHA256 `1bc9b39fe0023afc3db93211b9e3d6cd37ed2b13ee281f142749c2237a16ea8f`; reference arrays SHA256 `c3f6cba045f8b41f488dc19c960f5056b5f2e75cfa64f9a687b52f2a9ba2751e`. Fixed CPU 2, serial AMD queue, `/workspace/venv-feyer/bin/python`, persistent compilation cache disabled.

## Candidate 1 — prepared flat component scatter

Exact parent: seed above. Candidate SHA and screen/full IDs pending supervisor.

Measured target: forward compile **7.633823741 s, 34.13%** in full job `ab12c14c29354bad9aa6dc024c91f8e6`; secondary possible effects on forward lowering and gradient compilation. The structural indexing cost inside those phases is unknown.

Source mechanism: `update` uses generic two-coordinate `.at[row, column].set` after computing component values. The builder already proves the destination pairs unique and in bounds, normalizing negative aliases in its proof. Prepare the corresponding row-major flat offsets in setup, then use a rank-one `lax.scatter` on the flattened matrix with proven unique/in-bounds indices. This removes traced coordinate normalization and index packing from that path and may simplify scatter lowering/AD. No output is precomputed; only integer topology indices are prepared. All original update values and their ordering, component functions, 101 frequencies, 193 physical parameters, linear solves and noise contractions remain unchanged. Official three JIT stages remain unchanged.

Focused implementation in `build.py` and `simulate.py`: attach `flat_matrix_indices` only where the existing uniqueness/bounds proof passes; use the direct scatter when that metadata exists. Dummy, overlapping, invalid or metadata-free paths retain the prior scatter. Metadata must be rebuilt after shape/destination edits, documented in `update`.

Prediction (unmeasured): modest forward compile/lower reduction, perhaps 0–0.5 s as a working expectation, not an operator attribution or promised saving. The entire **7.633823741 s forward compile duration is the absolute ceiling for eliminating that phase alone**; this change affects only a subset. Any gradient-compile effect is separate. Added host preparation/array storage, altered compiler optimization or layout may offset the reduction or regress execution/memory. Floating-point values are not intentionally reordered, but changed compiled scatter transposes/fusion still require strict full-gradient comparison. No gain claimed before evaluation.

Checks: AST syntax parsing and `git diff --check` pass; standard-library-only offset identity checks cover positive coordinates, negative aliases and a 751x752 shape. No JAX imports, simulator execution, local benchmark, new test infrastructure, dependency change, commit, publication or evaluation launch. No performance/numerical measurements for this candidate yet.

Decision: ready for supervisor screen, then unchanged official full and every saved-output/full-gradient check if eligible. Retained best remains seed. Next action on resume: record exact candidate SHA and run IDs; compare complete first run, all 14 phase deltas, warm time, memory and job wall against exact parent under matching conditions. Reject numerical failures or total regressions; treat a single low result as provisional pending repeat/noise policy. Re-rank phases before choosing another hypothesis. If structural scatter work has no useful effect, request coordinator-owned deeper compile attribution rather than inventing internal timing.
