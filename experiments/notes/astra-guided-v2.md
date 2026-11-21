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


## Candidate 2 result: retain provisionally, confirmation outstanding

Exact SHA **`3581734de67e45f701259839d640442add500777`**; screen `382fb3eb33924c60854a743c24b23075`, full **`445a35d5836749ae92a4f30d0b70e41b`**. Local saved report and all comparison checks inspected. Official/strict/resource/source/workload/precision all pass; full cohort `10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c`, concurrent exploratory timing. This is a valid new combination, not a confirmed shared best. The supervisor's automatic parent list records candidate 1 as history parent; scientific parents remain the restored seed plus slicing donor documented above.

Screen first run 19.935477491 s, compilation/lowering 8.876356849 s, wall 20.912261374 s, RSS 6,945,104 KiB; cheap checks pass. Full first run **19.698403006 s**, -0.359314619 s relative to seed job `7e6ce3c3bf5148af93351918fda06e22` (20.057717625 s). Forward 8.301623050 s, -0.298854981 s; gradient 1.456364272 s, -0.061666677 s; combined compilation/lowering 8.736152118 s, -0.082263229 s. Build rose to 0.905320648 s. The observed direction is consistent with the layout hypothesis but native copy costs remain unknown.

Warm median 10.260291660 s, samples 10.270717381, 9.924800375, 10.260291660 s; wall 82.807315163 s. Full peak RSS 6,953,972 KiB, -847,692 KiB from seed; sampled peak 7,121,915,904 bytes. Memory and warm/job-wall metrics remain distinct from first run. Matched quiet serial confirmation against seed and relevant compatible parents is still needed; no promotion requested on a single observation.

Full phase ledger, seconds:

| Phase | Seconds |
| --- | ---: |
| imports | 0.293269549 |
| initialize | 0.002913747 |
| load | 0.001534173 |
| build | 0.905320648 |
| forward_lower | 0.696097840 |
| forward_compile | 3.370378388 |
| forward | 8.301623050 |
| sensitivity_lower | 0.077736806 |
| sensitivity_compile | 0.305117520 |
| sensitivity | 0.000900123 |
| gradient_lower | 0.293137388 |
| gradient_compile | 3.993684176 |
| gradient | 1.456364272 |
| host_transfer | 0.000325326 |

Saved outputs and complete gradient (last warm scope):

| Output | Max absolute error | Relative L2 error | Max normalized error | Failures |
| --- | ---: | ---: | ---: | ---: |
| carrier | 0 | 0 | 0 | 0 |
| signal | 0 | 0 | 0 | 0 |
| noise | 0 | 0 | 0 | 0 |
| sensitivity | 0 | 0 | 0 | 0 |
| powers | 0 | 0 | 0 | 0 |
| gradient | 4.54747350886464e-13 | 6.6472216603647e-18 | 1.63809701493981e-08 | 0 |
| parameters | 0 | 0 | 0 | 0 |
| frequencies | 0 | 0 | 0 | 0 |

All finite; all failure lists empty; exact parameters and frequencies unchanged. Gradient norm 70517.10686388786, shape 193. Official sensitivity error 5.374104176780747e-6; finite-difference gradient check passes; loss 9.793036291535532e-8. Candidate 2 is retained for further experiments; candidate 1 remains a valid but slower rejected trial.

Turn-3 shared feed generated Unix `1795296762.015154`, instance `amd-tim`, collector `trusted-local-artifacts-v1`; team digest changed to `922c284037a5d8f7be5e5b299abffb478d7441b59b987196ed74184b846da99d`, unchanged policy digest `54fffa2b291a30d2d20eb7b881da57f3f127ed0d3559330d7d5685838532e01c`, evidence digest `552b881a671a55201c05a0dd61a786c57030116b6a7a0a230bdc9cc7342222aa`, content digest `00e4b4a5912b4ad2cd31e5c6358bf7611c0ad7bc400cae301203d243b427c02e`. Matching cohort remains concurrent epoch 14; feed predates candidate 2 full completion. Claude guided recorded full `01ae324501d64448a29f71dca05e82a8` / `5b2169697d359f6a1c1f7fd6b5f66e08e9906969` passes, total 21.724829946 s with build 0.300624622 s but compilation 11.026949693 s. Read-only commit summary says this is not the assigned combination, so it is not evidence that the intended combination has been tested. No code is adopted from it. Independent session facts remain one-way feed evidence only.

## Candidate 3: retain only real nonlinear component residuals

Exact scientific parent **`3581734de67e45f701259839d640442add500777`**; candidate SHA and evaluator IDs pending. No new source combination or layout/solver change. Parent full **`445a35d5836749ae92a4f30d0b70e41b`** has largest phases forward 8.301623050 s (42.14%), gradient compile 3.993684176 s (20.27%), forward compile 3.370378388 s (17.11%), gradient execution 1.456364272 s (7.39%). Total compilation/lowering 8.736152118 s (44.35%). These measurements justify investigating reverse compilation, without attributing cost to individual primitives.

Focused change: add `_save_component_residuals` as the policy of the existing component-values checkpoint. Preserve the parent's discrete-index policy for all other operations; additionally permit unary exp/sqrt/sin/cos/sinh/cosh/asin only with one input whose abstract dtype is explicitly non-null and a real floating subtype. These unary operations preserve input dtype, so complex residuals cannot be selected by this added branch. No casts, precision settings, manual derivatives, additional JIT stage or formula changes. Complex phases continue to recompute.

New reason relative to historical failed trial **`e63f627129ed9d59da5b5f7189dbf54944e2a151`**, screen **`069cb2e8ae004d2b8f1b10de5d01097a`**: that policy selected nonlinear results irrespective of dtype and failed on checkpoint reduce_precision for complex128. Exact historical diff and failure notes inspected. This policy deliberately rejects complex inputs and missing dtypes; it also acts on the smaller current component checkpoint rather than the historical entire-assembly boundary. The failed trial provided no timing or correctness result. It is not repeated unchanged, and no dependency workaround is introduced.

Mechanism: retained real nonlinear results can reduce recomputation in the reverse graph, potentially reducing the measured 3.993684176 s gradient compilation phase and some gradient execution. Real-valued square roots and trigonometric factors occur in component formulas; their native cost and how much the compiler already eliminates are unknown. Tentative total first-run opportunity 0–0.4 s, unmeasured. Increased saved residual traffic, forward compile graph and storage could outweigh it. Reduction in one phase alone does not justify retention if total worsens.

Checks: simulator syntax and whitespace pass. Removing the new policy and restoring its decorator reference reproduces the exact parent module AST. A policy-only standard-library check with disjoint stand-in dtype families verifies acceptance of the real unary case, rejection of complex/integer/bool/missing dtype and wrong arity, and delegation of other primitives to the original index policy. This is control-flow validation, not NumPy/JAX runtime validation. No JAX, benchmark, environment changes, new test infrastructure, Git writes, SSH or agents used.

Next: supervisor screen/full and strict saved outputs/full gradient at unchanged tolerances. Reject trace errors, numerical failures and slower complete totals; retain all trials in history. Preserve candidate 2 for matched serial confirmation before any promotion. Continue within fixed deadline 2026-11-21 22:22:45.341115 UTC, session `astra-guided-v2`, thread `01a1fffd-808b-7df1-9718-3c929f0deb90`.


## Candidate 3 result: valid, no demonstrated benefit; restore candidate 2

Exact SHA **`bec798863aad0b08d647eed97aeeecf3fcaddf06`**. Screen **`a9fd3d2d091440b087ecc8f287b84a69`**: first run 19.822412597 s, compilation/lowering 8.875407524 s, job wall 20.918383630 s, peak RSS 6,947,060 KiB. Cheap checks pass; screening is provisional.

Full **`7d4e18e2793245c98fc991a22f30cd5b`**: official and strict pass, resource/source/workload/precision pass. First run **19.750739865 s**, +0.052336859 s versus retained candidate 2 `3581734de67e45f701259839d640442add500777`, full `445a35d5836749ae92a4f30d0b70e41b` (19.698403006 s). Combined compilation/lowering 8.737734802 s versus 8.736152118 s. Gradient compilation 4.044509476 s versus 3.993684176 s: the intended saving did not materialize. Forward compilation 3.360813309 s; forward execution 8.293144941 s; gradient execution 1.587247977 s; build 0.828894872 s. Dominant phases remain forward (41.99%), gradient compilation (20.48%) and forward compilation (17.02%). Native operation costs remain unknown.

Warm median 10.263154171 s (samples 10.318893671, 10.263154171, 10.250296798); job wall 82.636283191 s; RSS 6,948,708 KiB, sampled peak 7,116,525,568 bytes. These are separate from the first-run objective. Results are exploratory, not quiet matched confirmation. Restoring candidate 2 is a conservative development decision, not a claim that the small measured difference is repeatable.

Inspected the local saved full report and every saved-output/gradient comparison. Carrier, signal, noise, sensitivity, powers, parameters and frequencies have zero absolute error; parameters/frequencies meet exact checks. Full gradient max absolute error 4.547473508864641e-13, relative L2 6.6472216603647045e-18, max normalized error 1.6380970149398136e-8; all finite, zero failing entries. Gradient shape 193, norm 70517.10686388786. Official spot finite-difference check passes; sensitivity max log error 5.374104176780747e-6; loss 9.793036291535532e-8. Candidate 3 remains preserved in history but its real-residual policy is removed for candidate 4.

## Candidate 4: combine constant input-slot pruning with component checkpoint

Scientific combination parents: retained **`3581734de67e45f701259839d640442add500777`** and mechanism donor **`10a311f6dbe4e8b71fa98654d015493ab8b3ef27`**. Git history includes rejected candidate 3 and supervisor feedback. Candidate 4 SHA and evaluator IDs pending supervisor. Working tree was clean at entry; no interrupted edits.

Read the donor's exact simulator diff and committed notes. Donor full **`3a030c65057c4134ae07d46f012d674a`**, supplied shared evidence, passes official/strict/resource/source/workload/precision: total 19.766133159 s, forward compilation 6.619912855 s, gradient compilation 1.318031559 s, forward execution 8.394968893 s, gradient execution 1.506213591 s, build 0.295687027 s. Same amd-tim cohort `10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c`, concurrent epoch 14; single exploratory observation, not confirmed promotion. The donor's checkpoint architecture and build differ, so those numbers cannot predict this combination's savings. The Claude-owned build-plus-seed combination is not duplicated: build.py remains unchanged.

Measured target: retained parent full **`445a35d5836749ae92a4f30d0b70e41b`** spends 8.301623050 s in forward execution, 3.993684176 s in gradient compilation, and 3.370378388 s in forward compilation. Latest candidate 3 job **`7d4e18e2793245c98fc991a22f30cd5b`** has the same dominant pattern, 8.293144941 / 4.044509476 / 3.360813309 s. Target gradient compilation and, secondarily, forward compilation by reducing derivative expressions inside the component checkpoint. Runtime effects and native costs remain unknown. Tentative total first-run opportunity 0–1 s is unmeasured, not promised; added column slicing or interaction with rematerialization can instead lose overall.

One attributable mechanism transferred: host-derived per-group differentiable input-slot metadata plus scalar-slot component evaluation. A slot remains differentiable if ANY component row reads ANY optimized index or linking output; otherwise its derivative with respect to the optimized inputs is zero. Separate scalar arguments allow stop_gradient on these constant slots to yield symbolic-zero tangents rather than generating component derivative terms for every element of a dense parameter row. All linking outputs are conservatively included. Metadata contains only static dictionary keys with empty tuple values. Missing metadata or unsupported input rank uses the original group function. The `_ParameterSlots` and `_evaluate_component_group_slots` helpers match the donor exactly; the branch is adapted to `_component_values` and no new global tuning switch is introduced. Current component functions access parameter slots with static integer indices; lower-sideband wrappers may reconstruct arrays and obtain less pruning.

The mask specializes derivatives to the optimized parameter interface described by optimization_pairs; it is not a promise of gradients with respect to undeclared base constants or sweep values. Changing optimized selectors/pairs requires rebuilding metadata, as documented. All 193 required physical design variables and all linking dependencies remain represented; values, all 101 frequencies, double precision, full outputs, formulas, solver arithmetic and three official JIT stages are preserved. No residuals from candidate 3 are retained and no benchmark/solver/build tuning setting changed.

Validation: every simulator module parses; whitespace passes; AST comparison confirms exact donor helper bodies/decorators and unchanged parent solver, simulation assembly, checkpoint policy and other executable functions except `_component_values` and run_build_step. Update only gains metadata documentation. Static inspection confirms all component parameter accesses use integer slots. No local JAX, simulator or benchmark execution. These checks establish source structure, not numerical equivalence or speed; supervisor must run screen/full and inspect all strict saved outputs/gradient. Reject numerical failures and slower complete totals despite isolated phase improvements. Compare with retained candidate 2 and donor where appropriate, with matched quiet confirmation before promotion.

Turn-4 shared evidence generated Unix `1795297076.1527739`, collector trusted-local-artifacts-v1, instance amd-tim. Team digest `922c284037a5d8f7be5e5b299abffb478d7441b59b987196ed74184b846da99d`, policy digest `54fffa2b291a30d2d20eb7b881da57f3f127ed0d3559330d7d5685838532e01c`, evidence digest `ad15ce108fe222fc437484e817ff41128833856915b0919c341722aac0a4f527`, content digest `23cf374a2b871f4209c4569c6f46ad74d6210328224ce6c646d27bd343fe2841`. Other cohorts and unknown contexts remain incomparable.

Continue after candidate four while time remains. Session `astra-guided-v2`, thread `01a1fffd-808b-7df1-9718-3c929f0deb90`; unchanged deadline 2026-11-21 22:22:45.341115 UTC. Supervisor owns commits/evaluation. No agents, SSH, Git writes or protected-path changes.


## Candidate 4 result: retain provisionally

Exact SHA **`c99bd28b0ba6201e10176997813b3327040da151`**, screen **`7478ae1ce24341a3bad8f3f53301e580`**, full **`93b9c1726a99441eb8441caf5878687e`**. Official/strict/resource/source/workload/precision pass. Local full report and every saved-output/gradient check inspected. Screen first run 18.063763388 s, compilation/lowering 7.224385235 s, wall 19.074162744 s; provisional evidence only.

Full first run **18.017013432 s**, compared with retained exact parent candidate 2 `3581734de67e45f701259839d640442add500777`, full `445a35d5836749ae92a4f30d0b70e41b`, 19.698403006 s: observed reduction **1.681389574 s**. Compilation/lowering 7.072752636 s versus 8.736152118 s, reduction 1.663399482 s. Gradient compilation 2.449156754 s versus 3.993684176 s, reduction 1.544527423 s. This supports the pruning hypothesis on this combination; individual primitive/kernel time was not measured. Forward execution rose slightly to 8.372780466 s from 8.301623050 s. Full remains one exploratory observation in amd-tim cohort `10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c`, concurrent epoch 14. Quiet matched confirmation against candidate 2 and compatible donor parents remains outstanding; no promotion claim.

Warm median 10.307053125 s; samples 10.307053125, 10.307959644, 10.303746864 s. Job wall 81.349728243 s; peak RSS 6,902,564 KiB; sampled peak 7,066,820,608 bytes. Warm execution and job wall are distinct from first run.

| Phase | Seconds |
| --- | ---: |
| imports | 0.290794786 |
| initialize | 0.002879091 |
| load | 0.001499444 |
| build | 0.831181817 |
| forward_lower | 0.715897029 |
| forward_compile | 3.340866249 |
| forward | 8.372780466 |
| sensitivity_lower | 0.077279421 |
| sensitivity_compile | 0.275532052 |
| sensitivity | 0.000904489 |
| gradient_lower | 0.214021131 |
| gradient_compile | 2.449156754 |
| gradient | 1.443781896 |
| host_transfer | 0.000438808 |

All saved checks (last warm scope):

| Output | Max absolute error | Relative L2 | Max normalized error | Failures |
| --- | ---: | ---: | ---: | ---: |
| carrier | 0 | 0 | 0 | 0 |
| signal | 0 | 0 | 0 | 0 |
| noise | 0 | 0 | 0 | 0 |
| sensitivity | 0 | 0 | 0 | 0 |
| powers | 0 | 0 | 0 | 0 |
| gradient | 4.54747350886464e-13 | 6.64722166067799e-18 | 1.63809701493981e-08 | 0 |
| parameters | 0 | 0 | 0 | 0 |
| frequencies | 0 | 0 | 0 | 0 |

All failure lists empty. Official finite-difference spot check passes; sensitivity max log error 5.374104176780747e-6. Gradient shape 193, norm 70517.10686388786; loss 9.793036291535532e-8. Candidate 4 is retained as the new scientific parent; candidate 2 remains preserved for confirmation.

## Candidate 5: preserve scalar input slots through lower-sideband wrappers

Scientific combination parents: **`c99bd28b0ba6201e10176997813b3327040da151`** and mechanism donor **`3b805077bb5c61d85115faf38af243cc001d0fee`**. Candidate SHA and screen/full IDs pending supervisor. Initial worktree clean.

Exact measured parent full **`93b9c1726a99441eb8441caf5878687e`** is dominated by forward execution **8.372780466 s (46.47%)**, forward compilation **3.340866249 s (18.54%)**, and gradient compilation **2.449156754 s (13.59%)**. Total lowering/compilation is 7.072752636 s (39.26%). This candidate targets both compilation phases, with the largest likely effect on gradient compilation because component rematerialization is there. It does not attribute the forward 8.37 s to a particular native operation.

The three lower-sideband functions reconstruct a dense array of `[-p[0], p[1], ...]` before calling their base function. This can discard symbolic-zero tangent information from constant scalar slots. The focused change routes their existing slot evaluator directly to the identical base function using `_ParameterSlots` with only slot 0 negated. Function-identity lookup covers space_lower, space_modulation_lower and laser_frequency_modulation_lower; all other functions retain the existing path. No component formula, dtype, input dependency mask, checkpoint boundary, build logic, solver arithmetic, batching setting or physical workload changes. No new tuning flag. The original public wrapper functions and generic evaluation path remain intact.

Read donor's exact simulator diff and its recorded result in completed `633689f9bf054a90ca21b7b6087120cd86fa0d0e` notes. Donor full **`57ef1df7269d4b56acf28bcd89958873`** passes official/strict/resource/source/workload/precision in the same cohort and concurrent epoch 14: total 19.566764480 s, forward compile 6.472866856 s, gradient compile 1.288536770 s. Its parent `10a311f6...` full `3a030c65057c4134ae07d46f012d674a` was 19.766133159 s, forward compile 6.619912855 s, gradient compile 1.318031559 s. The small observed improvement is not repeat-confirmed. Its build and checkpoint structure differ from ours, so savings are not assumed additive. Also inspected the newer peer row-splitting diff (`633689f9...`) but did not transfer it: it is a distinct transformation requiring adaptation to our flat output indices.

Hypothesis: avoiding array reconstruction should let AD omit constant-slot derivative terms within these lower-sideband groups, reducing forward/gradient compilation and perhaps lowering. Execution should be similar; native costs are unknown. Tentative first-run opportunity 0–0.3 s is unmeasured. The compiler may already eliminate some terms, or layout/trace changes may outweigh the savings. Keep only if complete first-run results and strict outputs justify it, not because one phase improves.

Validation: simulator syntax and whitespace pass. AST checks establish that the new evaluator equals the enabled donor implementation, and every other parent function/class is unchanged. Checked original wrapper ASTs explicitly: each applies exactly one negation to slot 0 and passes the required remaining slots unchanged to the mapped base. This verifies the source-level scalar/sign mapping, not compiled numerical identity. No local JAX/simulator/benchmark execution. Supervisor screen/full and all strict physical-output/full-gradient checks remain required. Preserve all 101 frequencies, 193 variables, double precision and the official three JIT stages.

Shared feed generated Unix `1795297510.331399`, amd-tim trusted-local-artifacts-v1. Team digest `922c284037a5d8f7be5e5b299abffb478d7441b59b987196ed74184b846da99d`, policy digest `54fffa2b291a30d2d20eb7b881da57f3f127ed0d3559330d7d5685838532e01c`, evidence digest `68516222c08d64da74a3b577626ad87b80c329f07a971233c829698bc3ddfd07`, content digest `63401845a3d39c1ba004f38acb69b24863b7ab74aa8fafae06462c52cd8d5a92`. Feed precedes our candidate 4 completion; supplied exact feedback is authoritative for this result. Other cohorts/unknown contexts remain separate.

Continue within fixed deadline 2026-11-21 22:22:45.341115 UTC; session astra-guided-v2, thread `01a1fffd-808b-7df1-9718-3c929f0deb90`. No candidate cap, agents, Git writes, SSH or protected-path modifications.


## Candidate 5 result: retain provisionally

Exact SHA **5392f38b6b2afa10da2ecb3afbed36a3d0ef3d1f**. Screen **5fd7ccbb7af64ea6aa7cbdcf1ce8f3f5** passed provisional checks at 17.876223736 s first run (wall 18.811351165 s). Full **8e0ef4764ae740598dcff781cfd31b73** passed official, strict, resource, source, workload and precision checks. Inspected the local saved full comparison: carrier, signal, noise, sensitivity, powers, parameters and frequencies all have zero error. Gradient max absolute error 4.547473508864641e-13, relative L2 6.6472216606779924e-18, max normalized error 1.6380970149398136e-8; all eight checks finite, passing and zero failing elements. Exact parameter/frequency checks pass. Official finite-difference spot check passes; gradient shape 193, norm 70517.10686388786, loss 9.793036291535532e-8.

Full first run **17.891528219 s**, versus exact parent candidate 4 c99bd28b0ba6201e10176997813b3327040da151 / full 93b9c1726a99441eb8441caf5878687e at 18.017013432 s: observed reduction **0.125485213 s**. Lowering/compilation 6.981913082 s versus 7.072752636 s. This small difference remains exploratory, not repeat-confirmed. Retain candidate 5 provisionally; matched quiet confirmation remains outstanding. Warm median 9.858649263 s (samples 9.858649263, 9.993132269, 9.800916916 s) and job wall 81.283668501 s are separate evidence. RSS 6,895,364 KiB, sampled process-group peak 7,061,901,312 bytes, within budget.

Full phases in seconds: imports .297824509, initialize .002948347, load .001424134, build .862332765, forward_lower .708765930, forward_compile 3.317127109, forward 8.332447458, sensitivity_lower .078772778, sensitivity_compile .272742290, sensitivity .000879619, gradient_lower .200753490, gradient_compile 2.403751487, gradient 1.411321810, host_transfer .000436494.

## Candidate 6: separate constant rows within mixed component groups

Retained exact parent **5392f38b6b2afa10da2ecb3afbed36a3d0ef3d1f**; scientific mechanism donor **633689f9bf054a90ca21b7b6087120cd86fa0d0e**. Candidate SHA and run identifiers pending supervisor. Worktree clean at entry; no interrupted edits. One attributable change: stable partition mixed component groups into rows reading optimized/linked parameters and rows reading only constants, then evaluate the latter with all scalar slots gradient-stopped. This prunes their derivative expressions inside the existing checkpoint. All linking outputs remain conservatively live; no value-based pruning, precomputed answers or persistent cache. Uniform groups keep their existing evaluation. Metadata is static dictionary keys; neither subgroup is empty.

Exact parent full **8e0ef4764ae740598dcff781cfd31b73** is dominated by **forward execution 8.332447458 s (46.57%)**, **forward compilation 3.317127109 s (18.54%)** and **gradient compilation 2.403751487 s (13.44%)**. Hypothesis: separating constant rows reduces differentiated component graph size, primarily affecting gradient compilation and possibly forward compilation/lowering; native-operation costs remain unknown. The 8.33 s forward phase is not attributed to particular kernels. Extra subgroups/concatenations may outweigh pruning, so no improvement is promised or measured. Complete first-run time, rather than any isolated phase, decides retention.

Read donor exact diff and completed notes. Donor full **ef7e77be6044490e8d7dc99e41d0ecf6** passed all official/strict/resource/source/workload/precision checks: first run 19.542833529 s, forward 8.415414024 s, forward compile 6.393606933 s, gradient compile 1.304919772 s. Its parent 3b805077bb5c61d85115faf38af243cc001d0fee / full 57ef1df7269d4b56acf28bcd89958873 was 19.566764480 s; donor notes classify the difference as neutral/within noise. Different checkpoint and assembly structures prevent assuming additive savings. Also inspected completed peer aac9904cb4dd9b2caae377d8d4694f6782ec3498 (full afea41cd5469435e9be97d2c1cdffa0b, 17.849646132 s), whose distinct new change transfers our existing component-values checkpoint onto the peer branch; no additional mechanism from it is copied. The Claude-owned build-plus-seed combination is not duplicated.

Adaptation to this branch: reordering input rows must remap both original-to-group output_rows and composed flat_output_indices. The global old-to-new row permutation changes only the row portion of each flattened selector and preserves its column. function_rows is reordered consistently with parameter_indices. Output selection sequence, duplicate scatter order, carrier coupling, formulas, solver/batching settings, dtypes, checkpoint boundary and all three official JIT stages are unchanged. Build.py and all protected files remain unchanged. Constant is relative to the declared optimized-input interface, as with candidate 4 slot masks; rebuild metadata when optimization/link selectors change.

Validation: every simulator module parses, git diff --check passes, AST comparison with exact parent finds only _component_values and run_build_step changed. A pure-Python selector model checked 53,769 combinations of group sizes, dependency masks and original row permutations, including empty/uniform/mixed groups and negative original row selectors, preserving every column in both selector forms. This is source/mapping validation, not compiled numerical or speed evidence. No local JAX, simulator or benchmark execution. Supervisor must run screen/full and inspect all saved physical outputs and the full 193-entry gradient; screening is provisional. Reject numerical failures or a slower total despite individual phase improvements. All 101 frequencies and 193 physical variables remain included.

Shared evidence generated Unix 1795297999.731334, instance amd-tim, trusted-local-artifacts-v1. Cohort 10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c, concurrent epoch 14; other cohorts/unknown contexts remain incomparable. Evidence digest 8d4b09c6502c954744b698bd7b183299cdc2b44a888c91eb4822de82631390ad; content digest e2a7400fcf79eadb98b4acb89db1e3871a43aa1f842a58289025edbf387e95a4. Own exact feedback supplies candidate 5 results missing from the frontier listing.

Session astra-guided-v2, thread 01a1fffd-808b-7df1-9718-3c929f0deb90; fixed deadline 2026-11-21 22:22:45.341115 UTC. No candidate cap. Supervisor owns Git/evaluation; no agents, SSH, commits, pushes or protected-path edits.


## Candidate 6 result: valid, timing neutral; retain provisionally

Exact SHA **800f8ea5da9e4c873df9ba2729ac5b76328d0cc5**. Screen **2bbaa47bff3c47f9a8a1e96476ac47de** first run 17.851596370 s, wall 18.869970320 s; provisional checks pass. Full **e525903bcb6e440c83edd56abd4cf4b8** passes official/strict/resource/source/workload/precision. Inspected all eight saved-output/full-gradient comparison checks: carrier, signal, noise, sensitivity, powers, parameters and frequencies have zero error. Gradient max absolute error 4.547473508864641e-13, relative L2 6.6472216606779924e-18, max normalized error 1.6380970149398136e-8. All finite, zero failing entries; exact parameter/frequency and official finite-difference checks pass. Saved scope is last warm evaluation.

Full first run **17.850141203 s**, versus retained parent 5392f38b6b2afa10da2ecb3afbed36a3d0ef3d1f / full 8e0ef4764ae740598dcff781cfd31b73 at 17.891528219 s, an observed 0.041387016 s reduction. Combined lowering/compilation **6.990810866 s** increased by 0.008897783 s; gradient compile fell only 0.006029451 s. These observations do not establish the pruning hypothesis or a repeatable speed improvement. Retain as a numerically valid, timing-neutral development parent; preserve candidate 5 for confirmation. Warm median **10.242307758 s** is slower than candidate 5's 9.858649263 s; this is separate evidence, with parent matching still needed. Warm samples 10.234131495, 10.329793487, 10.242307758 s. Job wall **80.653285200 s**; peak RSS 6,902,432 KiB, sampled peak 7,069,138,944 bytes, within budget. No promotion claim.

Full phases, seconds: imports 0.292453194; initialize 0.002911298; load 0.001502613; build 0.842991494; forward_lower 0.705121282; forward_compile 3.333262190; forward 8.309957352; sensitivity_lower 0.075587507; sensitivity_compile 0.277607914; sensitivity 0.000902252; gradient_lower 0.201509936; gradient_compile 2.397722036; gradient 1.408172123; host_transfer 0.000440013.

## Candidate 7: move guarded sideband conjugation before dense assembly

Exact retained parent **800f8ea5da9e4c873df9ba2729ac5b76328d0cc5**; scientific mechanism donor **9aea8857d4112bca33f189d526fc3b1ecd47db58**. Candidate SHA and evaluator IDs pending supervisor. Initial worktree clean. One attributable implementation change in update and _assemble_signal_and_noise only; no build, solver, checkpoint, component formula or frozen setting changes.

Measured target: full **e525903bcb6e440c83edd56abd4cf4b8** spends **8.309957352 s forward (46.55%)**, **3.333262190 s compiling forward (18.67%)**, and **2.397722036 s compiling gradients (13.43%)**. Hypothesis: commuting destination-based conjugation through the unique component scatter allows reverse mode to gather selected matrix cotangents before conjugating a small vector, and moves forward base conjugation to an unbatched, frequency-invariant input. Target forward execution and gradient compilation/execution; forward compilation may also change. Native operation costs and actual compiler hoisting remain unknown. No numeric speedup is predicted or promised; extra mask selection/layout effects may increase total time.

The identity is C(scatter(B,I,v)) = scatter(C(B),I,C[I](v)) for the same destination mask and replacement values. Guard requires existing complete carrier-output mapping and proven unique/in-bounds flat destinations. Conjugation is applied AFTER unary minus/carrier multiplication. Untouched entries retain conjugated base values, including complex constants and signed zeros; augmented RHS and mechanical/sideband boundaries are included. Generic callers retain dense conjugation after all updates. The optional mask defaults to None for carrier/noise/general update calls. No new indexing proof, value-based pruning, physical-output caching or custom derivative is introduced.

Historical caution: inspected donor exact diff and experiments/notes/codex-profile-guided-v1.md. Donor full **a9d15d75b3354adab3f3f67c1ae7791d** passed official and strict but was **21.854730275 s**, 0.028801749 s slower than its parent 2085ff2c9a1f30cb3effaa9281d22942219e575a / full 90519617eff2459a976172ff96a1ffad. Forward 8.538123004 s, forward compile 4.594758270 s, gradient compile 4.667640183 s. It was correctly rejected as an improvement. The present test is motivated by the intervening checkpoint architecture change: dense assembly/conjugation is now outside the component-only recomputation region, whereas that older trial wrapped all assembly in a checkpoint. The dependency pruning and separate coefficient/RHS loop outputs also differ. This is an unmeasured combination, not evidence that the earlier failure disappears. No additivity assumption. Restore the exact retained parent if complete total worsens or any numerical check fails.

Validation: all simulator modules parse; git diff --check passes. AST comparison confirms only update and _assemble_signal_and_noise changed; the latter matches donor executable AST exactly. One hundred deterministic standard-library complex cases pass bitwise equality of pre-scatter versus dense post-scatter conjugation, including signed-zero base entries, empty/reordered replacement sets, varied carrier subsets, sideband/mechanical boundaries and augmented RHS. These are source/algebra checks, not JAX differentiation, physical or performance validation. No local simulator/JAX/benchmark execution. Supervisor screen/full and every saved physical output/full 193-coordinate gradient remain required. Preserve all 101 frequencies, double precision and the three official JIT stages.

Shared feed generated 1795298374.5214772, amd-tim, trusted-local-artifacts-v1; same full cohort 10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c, concurrent epoch 14. Own exact feedback covers the candidate 6 completion after that snapshot. Team digest 435c14288ee6ad5dd1177076c40e50274ce55ec379fc31bc98f5291f7b505220; evidence digest db96450a02c3e20b1b5275bf623c3df792dcae59ef5e4fc42ae3f04050a17002; content digest a81f539dcc5a504d69e44496de515ef2944aa0d679941a034b738e161ac56373. Read completed peer diffs ae180410c4375fff1ca3f755fb057ffc0641db75 and 5466dc1b1a7516650eb91c67513644a49b9c2067: those switch direct versus direct_implicit adjoint solves; no mechanism adopted here. Other cohorts and unknown contexts remain incomparable. Quiet matched confirmation is outstanding.

Session astra-guided-v2, thread 01a1fffd-808b-7df1-9718-3c929f0deb90, fixed deadline 2026-11-21 22:22:45.341115 UTC. No candidate cap, agents, Git writes, SSH or protected-file edits; supervisor handles evaluation.


## Candidate 7 result: valid, reject timing and restore candidate 6

Exact SHA **47007cc389e115b050d35d96bbbd9324f5276512**. Screen **62e8429dc05642fdbee37836dd423a63** passed provisional checks: first run 18.124635037 s, wall 19.132584604 s. Full **16e00a2387844cc9b77f3ff2ae01aa29** passed official, strict, resource, source, workload and precision checks. Inspected all saved full comparison entries from experiments/runs/astra-guided-v2/candidate-07.json: carrier, signal, noise, sensitivity, powers, parameters and frequencies have zero error; gradient max absolute error 4.547473508864641e-13, relative L2 6.6472216606779924e-18, max normalized error 1.6380970149398136e-8. All eight checks finite with zero failing entries, exact parameter/frequency checks pass, and official finite-difference check passes. Saved-output scope is last warm evaluation.

Full first run **17.969176523 s**, versus exact retained candidate 6 **800f8ea5da9e4c873df9ba2729ac5b76328d0cc5**, full **e525903bcb6e440c83edd56abd4cf4b8**, at **17.850141203 s**: slower by 0.119035320 s. Combined lowering/compilation 7.074944464 s versus 6.990810866 s, also slower. Dominant phases are forward execution **8.341455286 s (46.42%)**, forward compilation **3.418802569 s (19.03%)**, gradient compilation **2.389919389 s (13.30%)**. The slight gradient compilation decrease does not justify a slower total. This retry provides no timing support for the conjugation change; reject and restore candidate 6 while preserving candidate 7 in supervisor history. These are exploratory concurrent observations, not matched quiet confirmation.

Other phases, seconds: imports .295935279, initialize .002884718, load .001411716, build .844160516, forward_lower .708140146, sensitivity_lower .075972930, sensitivity_compile .280254658, sensitivity .000847992, gradient_lower .201854773, gradient 1.406967970, host_transfer .000568584. Warm median **10.294995740 s**, samples 10.501358952, 10.294995740, 10.272434978 s; job wall **81.401667336 s**. These are separate from the first-run objective. RSS 6,910,364 KiB, sampled peak 7,077,261,312 bytes, within budget.

## Candidate 8: express the separately factored adjoint solve through A

Retained exact parent **800f8ea5da9e4c873df9ba2729ac5b76328d0cc5**; scientific mechanism donor **aac9904cb4dd9b2caae377d8d4694f6782ec3498**. Candidate SHA and run IDs pending supervisor. Worktree was clean on entry. Restored candidate 6's simulate.py before making this single solver change; candidate 7 conjugation is removed. The only function changed relative to candidate 6 is _solve_signal_and_noise.

Measured target: candidate 7 full **16e00a2387844cc9b77f3ff2ae01aa29** is dominated by forward 8.341455286 s and compilation (forward 3.418802569 s, gradient 2.389919389 s). The retained exact parent's full **e525903bcb6e440c83edd56abd4cf4b8** similarly spends **8.309957352 s forward**, **3.333262190 s forward compilation**, **2.397722036 s gradient compilation** and **1.408172123 s gradient execution**. Native-operation costs within these phases remain unknown.

Mechanism: preserve the separate explicit conjugate-transpose A^H and its stop-gradient LU factorization for detector weights, but expose the solve through custom_linear_solve whose differentiable matvec contracts conjugate(A) with transposed indices. The original A is already an input to the signal and covariance solve derivatives. This representation may avoid retaining another dense transposed matrix for AD and reduce forward memory traffic or reverse graph work. Forward execution is the primary predicted target; gradient compilation/execution may also decrease. Compilation or layout changes could instead increase total time. No speedup is measured or promised, and no solve/kernel duration is inferred from source counts. This does NOT reuse A's LU to solve A^H: that known strict-failing transformation remains disabled. The transpose solve uses trans=1 on the separately factored A^H, consistent with the bilinear complex linear transpose used by AD.

Transferred the donor's direct_implicit branch body into the existing direct implementation, without adding or changing any frozen setting, mode menu, chunk size, checkpoint, component formula, noise contraction or build code. Its executable branch AST exactly matches the donor. Signal/covariance solves remain unchanged, as do the off/all implementations. All 101 frequencies, 193 design variables, double precision and three official JIT stages remain intact. No caching/precomputed physical answers.

Donor evidence: read exact simulator source and completed claude-profile-guided-v1 and claude-guided-v2 notes at recorded commits. Donor full **afea41cd5469435e9be97d2c1cdffa0b** passed all official/strict/resource/source/workload/precision checks, first run 17.849646132 s, forward 8.463278916 s, forward compile 3.469677711 s, gradient compile 2.424082940 s, gradient 1.549607553 s. Peer **ae180410c4375fff1ca3f755fb057ffc0641db75**, full **2dd450e4b63d4e159fa49a98de58f56c**, switched only to the original direct adjoint implementation: still valid, but total 17.955824388 s, forward 8.558109239 s, gradient compile 2.404522080 s and gradient 1.581869798 s. Peer notes reject it for no gain; forward outputs were bitwise identical, gradient normalized error rose from 1.6e-8 to about 6e-7, still passing. Reversion **5466dc1b1a7516650eb91c67513644a49b9c2067**, full **359c740c1f75451d8283135ce140e1f3**, was valid at 17.921362976 s. These small differences are not repeat-confirmed gains, and the peer build/assembly differs. We do not transfer its build changes or assume additive savings.

Validation: all simulator modules compile as Python source; git diff --check passes. AST comparison to retained candidate 6 shows only _solve_signal_and_noise changed. New adjoint factorization, custom solve and vectorization statements match the donor executable AST exactly. One hundred deterministic standard-library complex-matrix cases verify the transposed-index matvec equals explicit A^H multiplication and its bilinear transpose equals conjugate(A). This is source/algebra validation only, not a JAX/LU/numerical/performance test. No local simulator or benchmark ran. Supervisor must evaluate screen/full and inspect all saved physical-output/full-gradient comparisons; screening is provisional. Compare complete first-run time with retained parent 800f8ea5, reject strict failures or slower totals despite phase improvements, and preserve rejected trials.

Shared evidence: generated Unix 1795298666.214025, amd-tim trusted-local-artifacts-v1, full cohort 10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c, concurrent epoch 14. Evidence digest 6ec12f44345424d85d31afb881cc54094ae274d89c8782bceffcc7ca977d0018; content digest e890085032c007a05e699716ece53e600834bc7ff5bf93a7b1448e3ca83efa72. Other cohorts and unknown comparison contexts remain incomparable. Quiet matched confirmation remains outstanding.

Session astra-guided-v2, thread 01a1fffd-808b-7df1-9718-3c929f0deb90. Fixed deadline 2026-11-21 22:22:45.341115 UTC; no candidate-count cap. Supervisor handles Git and evaluation. No agents, commits, pushes, SSH or protected-file edits.
