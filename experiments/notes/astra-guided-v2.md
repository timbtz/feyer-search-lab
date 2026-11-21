# Astra guided continuation v2

## Session and evidence

- Session identifier `astra-guided-v2`, branch `explore/astra-guided-v2`; assigned worktree only. Supervisor owns commits and evaluations. Candidate count is unlimited within the fixed window.
- Launch record read from `.lab/sessions/astra-guided-v2/launch.json` in the repository root: actual launch Unix `1795296165.341115` (2026-11-21 21:22:45.341115 UTC), fixed deadline `1795299765.341115` (22:22:45.341115 UTC). No extension. Conversation identifier was not supplied.
- Starting and retained scientific parent: `7d1ccc59cef3d7436870bb0e6c941dbde4c30770`. Initial worktree was clean. Read `.wiki/README.md`, `experiments/initial-agent.md`, experiment rules and historical profiler notes. Current user instructions supersede the historical four-candidate cap.
- Exact-parent full job `7e6ce3c3bf5148af93351918fda06e22`: official and strict comparison pass; first run 20.057717625 s, combined lowering/compilation 8.818415347 s, warm median 10.762214443 s, total worker wall 86.067681324 s, peak RSS 7,801,664 KiB. These timings are distinct metrics.
- Dominant parent phases: forward 8.600478031 s (42.88%), gradient compile 4.058656961 s (20.23%), forward compile 3.314519804 s (16.52%), gradient execution 1.518030949 s (7.57%). Setup/build 0.823499076 s; imports 0.291449912 s. Native operation costs are unknown.
- Supplied complete strict comparison inspected: carrier, signal, noise, sensitivity, powers, parameters and frequencies exact; gradient max absolute error 5.093170329928398e-10, relative L2 7.576529280174932e-15, max normalized error 6.039550882495327e-7, zero failures. Parameters/frequencies require exact equality; all outputs finite, gradient shape 193. Official sensitivity max log error 5.374104176780747e-6 and finite-difference check pass. Saved comparison scope is last warm evaluation.

Shared feed generated Unix `1795296099.3428102` (21:21:39.342810 UTC), collector `trusted-local-artifacts-v1`, instance `amd-tim`, team digest `788879fb135abfe2c1d5c2737a25df0ac568ecf87f9fef92903068a3f8fe0695`, evidence digest `1ce373aeb6eef374439c48c19c9e90eeeeb04e746bd3fd9e6bb3872777e6d018`, content digest `d7104025dd21259343e293c59b77496ae04d9c4ccdd432156b728c631fcb9672`. Parent cohort `10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c`, concurrent regime epoch 14. Other cohort `d78b193...` is separate; unknown contexts are unranked. Frontier entries are individual exploratory observations, not confirmed dominance. Quiet matched serial confirmation is required before promotion.

Read-only Git inspection considered these complementary mechanisms:

- `eca3eda479a2a4dce778957e4f0081d076af7714`: exact diff from the seed moves output selection outside a still-monolithic component-evaluation checkpoint. Full `924cd65171cd4eb4badeb084ba0f0f97` passes but total 20.084588245 s and gradient compile 4.143367484 s do not establish an improvement over the seed. This motivates testing a different boundary, not blindly adopting that revision.
- `3a2073ad5add8770eab0d37b55ad67cea71b448b`: inspected source diff and recorded layout notes. Its shared-noise contraction sits on coefficient/RHS separation with scientific parents `28566a64a9efbdddc104762ac1f8212eb1d8370c` and `423bcc4ad6e99b85cd651980bee541612ed2ee20`; this overlaps the seed's assembly/solver code. Full `d9a90c7ee1974e64a4aebcef47572111` has forward 7.905136498 s and gradient 1.231270667 s, but total 21.199837675 s and compilation 10.947299596 s. Phase gains cannot be assumed additive. No solver/layout code or frozen menu setting is transferred in candidate 1.
- Build combination `aa2b1ab44180af8dd1cd3a9796adb911b1a3986a` plus seed belongs to Claude and is not duplicated. No independent Astra worktree/source/notes inspected or guidance sent; only the supplied completed facts were available as evidence.

## Candidate 1: checkpoint homogeneous component groups

Scientific and Git parent `7d1ccc59cef3d7436870bb0e6c941dbde4c30770`. Candidate SHA and screen/full run identifiers pending supervisor publication/evaluation.

One attributable transformation in `differometor/simulate.py`: move checkpointing from the entire `_component_values` helper to each `_evaluate_component_group` invocation. The group function ID is static for both its existing inline JIT and its new checkpoint. Retain the existing discrete-only saving policy and `prevent_cse=False`. Parameter gathers, concatenation, output routing, carrier multiplication and dense assembly now lie outside grouped recomputation. The dynamic fallback still uses its existing checkpointed component branches. Component expressions, arithmetic order, dispatch and destination indices are unchanged.

Hypothesis grounded in parent full job `7e6ce3c3bf5148af93351918fda06e22`: with gradient compilation at 4.058656961 s, smaller per-group recomputation regions and retained gathered inputs may reduce reverse compilation and repeated gather work. Forward compilation (3.314519804 s) and execution (8.600478031 s) may change with residual storage/layout. Tentative total opportunity 0–0.7 s, unmeasured; it is not a promise. More retained gathered inputs and fragmented checkpoint graphs may instead increase memory, compilation or execution enough to lose overall. No native-operation time is inferred from source counts.

This is distinct from candidate 12's output-gather-only boundary change: parameter gathers also leave recomputation, and each homogeneous function becomes a separate rematerialization region. Historical component-specialization removed per-group checkpoints before the later frequency-assembly/checkpoint architecture existed; that history cautions against assuming a benefit. The present comparison replaces a monolithic checkpoint on the exact validated seed instead of adding checkpoints to a checkpoint-free baseline. The earlier complex128 saving failure is not repeated: no inexact residual is explicitly selected by the policy.

Validation before submission: all simulator files parse, `git diff --check` passes. A standard-library AST comparison against exact HEAD confirms every executable function body and all module statements match after removing only the two affected functions' decorators/docstrings and ignoring function-definition order. No local JAX/simulator/benchmark execution, dependency/environment changes, commits, network/SSH or agents. This structural check does not establish numerical correctness or timing. All 101 frequencies, 193 variables, double precision, full optical setup, physical outputs and gradients, and three official JIT stages remain required.

Next decision: supervisor screen, then unchanged official full and all saved output/full-gradient checks if eligible. Compare complete first run with exact retained seed; retain failures in history and reject numerical failures or slower totals despite phase wins. Any promising full result still requires isolated matched parent confirmation before promotion. Continue the session after feedback while the fixed deadline permits.


## Candidate 1 result: valid, rejected for further development

Candidate `d947905c9b73e310257235cf00cb065c31572ecd`, screen `0fc68df47712495589237c4557203c8d`, full `ba4ea97d96204243bab88e9b156dbebe`. Local saved report and every comparison check inspected, alongside supplied feedback. Official/strict/resource/source/workload/precision all pass under full cohort `10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c`; timing remains exploratory, not matched serial confirmation.

Screen first run 20.767633673 s, compilation/lowering 9.552572789 s, wall 21.688565230 s; cheap checks pass, strict and finite-difference checks not run. Full first run 20.735073345 s, +0.677355720 s against retained seed. Compilation/lowering 9.533256035 s, +0.714840688 s. Gradient compile increased from 4.058656961 to 4.561758185 s, contradicting the proposed saving. Forward compile increased from 3.314519804 to 3.497142816 s. Forward execution 8.551208688 s and gradient execution 1.512069307 s are slightly lower, insufficient to offset compilation. Restore seed implementation for candidate 2, preserving candidate 1 in history.

Warm median 10.206435006 s (samples 10.299204323, 10.206435006, 10.198279995), worker wall 86.175094632 s, peak RSS 7,846,156 KiB, sampled peak 8,035,512,320 bytes. Warm improvement does not excuse the slower first run. No native operation cost was measured.

Full phases, seconds:

| Phase | Seconds |
| --- | ---: |
| imports | 0.295122759 |
| initialize | 0.002881121 |
| load | 0.001424683 |
| build | 0.837948337 |
| forward_lower | 0.708779361 |
| forward_compile | 3.497142816 |
| forward | 8.551208688 |
| sensitivity_lower | 0.076790789 |
| sensitivity_compile | 0.363857845 |
| sensitivity | 0.000868259 |
| gradient_lower | 0.324927039 |
| gradient_compile | 4.561758185 |
| gradient | 1.512069307 |
| host_transfer | 0.000294155 |

All saved-array checks (last warm scope):

| Output | Max absolute error | Relative L2 error | Max normalized error | Failures |
| --- | ---: | ---: | ---: | ---: |
| carrier | 0 | 0 | 0 | 0 |
| signal | 0 | 0 | 0 | 0 |
| noise | 0 | 0 | 0 | 0 |
| sensitivity | 0 | 0 | 0 | 0 |
| powers | 0 | 0 | 0 | 0 |
| gradient | 5.0931703299284e-10 | 7.57652928017493e-15 | 6.03955088249533e-07 | 0 |
| parameters | 0 | 0 | 0 | 0 |
| frequencies | 0 | 0 | 0 | 0 |

All finite and all failure lists empty. Official sensitivity max log error 5.374104176780747e-6; finite-difference spot check passes. Loss 9.793036291535532e-8; gradient shape 193, norm 70517.10686388829. Full numerical evidence supports correctness, not performance promotion.

Conversation/thread identifier now supplied: `01a1fffd-808b-7df1-9718-3c929f0deb90`. Deadline remains 2026-11-21 22:22:45.341115 UTC.

Shared feed for turn 2 generated Unix `1795296433.429441`, source instance `amd-tim`, collector `trusted-local-artifacts-v1`, evidence digest `b8182202b381f85d58840e114c35195f25acfea57c00f704102477b366bc713a`, content digest `32ebbe318c15d973e61ee4d6176477419825cfe34a1a2a5dcf7d64dfa639f9a7`. Same team/policy digests and concurrent epoch 14 as turn 1. It predates candidate 1's full completion; own supplied feedback is the evidence for that run. Cross-cohort and unknown-regime observations remain incomparable for promotion.

## Candidate 2: split coefficient/RHS outputs inside assembly loop

Git history parent includes rejected candidate 1 and its feedback commit `99cdd9d`; restored scientific parent **`7d1ccc59cef3d7436870bb0e6c941dbde4c30770`**. Mechanism donor **`423bcc4ad6e99b85cd651980bee541612ed2ee20`**, also incorporated in full-valid **`3a2073ad5add8770eab0d37b55ad67cea71b448b`**. Candidate SHA/run IDs pending supervisor. Declared scientific combination parents: seed `7d1ccc59cef3d7436870bb0e6c941dbde4c30770` and donor `423bcc4ad6e99b85cd651980bee541612ed2ee20`; the latter's historical job has conflicting artifacts in the feed, so no independent eligibility claim is based on it. Supporting recorded composite full `d9a90c7ee1974e64a4aebcef47572111` for `3a2073...` is valid in the matching cohort/regime, with total 21.199837675 s, forward 7.905136498 s, gradient 1.231270667 s, compilation 10.947299596 s. That composite also changes noise contraction and solver/layout surroundings, so its phase savings are not attributed solely to slicing.

Read the donor's exact simulator diff, the full-valid composite's differences from seed, and its declared layout parents. Transfer only exact coefficient/RHS slicing inside the existing assembly loop and the optional separated-input solver signature. Do not transfer its merged RHS solves, shared contraction, old component assembly, build changes, or tuning flags. In the seed's assembly-only scope, `block_assemble` now returns coefficient and RHS arrays separately, plus the existing per-row noise output only when needed. The solver normalizes augmented or separated inputs before executing the same operations. All other loop scopes keep the augmented input interface. Parent component checkpoints, direct LU reuse, separate adjoint factorization and broadcast noise contraction remain intact. No frozen search-space setting changed and no Claude-owned build combination duplicated.

Measured target: restored parent full `7e6ce3c3bf5148af93351918fda06e22` spends 8.600478031 s forward and 1.518030949 s gradient execution, with 3.314519804 s forward compilation and 4.058656961 s gradient compilation. Latest rejected candidate full `ba4ea97d96204243bab88e9b156dbebe` likewise ranks forward 8.551208688 s first and gradient compile 4.561758185 s second. Separating coefficient/RHS outputs before stacking may avoid large augmented-batch slice/copy operations and improve buffer layout around the solves; target primarily forward execution, with possible gradient and compiler effects. Native slice/copy/solve times are unknown. Tentative total opportunity 0–0.7 s is unmeasured and may be negative if extra loop outputs or reverse concatenation increase cost. No additivity assumption.

Validation: all simulator modules parse and whitespace checks pass. AST comparison to scientific seed confirms all helpers except the solver are unchanged; substituting the normalized coefficient/RHS inputs back into the solver yields exactly its parent executable AST. The only other changed function is simulate's assembly-only branch. Standard-library slice/stack checks cover 1, 2, 5 and 101 rows, chunk sizes 1, 2 and 4, matrix sizes 1 and 3 including padding/discard; retained values match exactly. No local JAX or benchmark execution. These checks do not establish compiler layout, strict AD equivalence or performance.

Next: exact-candidate screen/full, inspect all saved physical outputs and gradients under unchanged tolerances, compare total with retained seed and preserve any failures. Confirm promising full results against matching scientific parents before promotion. Session `astra-guided-v2`, thread `01a1fffd-808b-7df1-9718-3c929f0deb90`, fixed deadline 22:22:45.341115 UTC; no candidate cap.
