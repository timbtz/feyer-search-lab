# Component specialization session

- Branch: `explore/component-specialization`; managed session: `codex-component-specialization` (supervisor retains the conversation identifier).
- New 60-minute session, distinct from expired seed-agent. Candidate 1 started with 3599 seconds remaining. No candidate-count limit; evaluation time also counts.
- Starting checkout: `7ae7127923b37473773066a2716c6a71248ffdd9`. Simulator files match validated seed8 `1e552d675c3795265be8af1ac23ffb61f90f30b1` exactly (`git diff` inspected). This is the sole numerical parent; no linear-algebra candidate is combined.
- Objective: total first-run time including setup/imports, all three compilation stages, execution and transfer. Phase times, warm runtime, memory and total job duration are explanatory, separate measurements.

## Evidence and proposal, written before simulator edits

Read AGENTS.md, .wiki/README.md, experiment rules, initial-agent brief, and both search-initial context files. The user's new session and removed candidate cap supersede older seed-session limits. Snapshot seed8 full run `2cab1e4043ea42849eff58278d16bab6` passed official and strict checks: total 28.013465 s, setup 1.030558 s (build 0.737631 s), compilation 12.769458 s, forward 12.313662 s, gradient 1.898460 s, warm median 14.571260 s, job wall 112.319362 s, peak RSS 13435756 KiB. The user's later repeated audited-policy result is approximately 28.09 s versus 35.72 s unchanged. These are historical results, not candidate-1 measurements.

The snapshot records scalar-map, reusable-helper, conjugation-mask, checkpoint and inline-helper trials, but no measured static grouping by component type. Shared-LU, Schur and direct-noise-contraction experiments include strict gradient failures despite official passes; none is an eligible parent for this change.

Source evidence:

- `build.py:set_instructions` records Python function-registry indices and padded parameter-index rows. `pairs_to_arrays` collects these host instruction lists before `combine_arrays` converts them into JAX arrays. This is a suitable place to classify structural function types; parameter values need not be inspected.
- `simulate.py:update` currently gathers current parameters, maps a scalar dynamic switch with 19 checkpointed branches, gathers selected outputs, then makes one matrix scatter. The function-index arrays are dynamic JIT arguments. Host conversion or Python branching on their traced elements would be invalid.
- The builder's output-row indices can repeat (several matrix entries use one function result). Matrix destinations can also overlap in generic inputs. Grouping destination scatters by type could change overwrite behavior; retain the original single final scatter and its original index order.
- Component functions produce four complex outputs. Grouping function evaluation alone, then restoring original function-row order before the existing output gather/scatter, preserves all entries, including parameter-dependent zeros. No sparsity pruning or formula simplification is proposed.
- `run_build_step` maps positional build tuples to `simulate` positional argument names. New grouping metadata can be an optional keyword-only argument, leaving that positional contract intact. A dictionary's integer keys provide structural function IDs while its row-index array leaves remain ordinary JAX arguments. Older callers without metadata retain seed8 dispatch. Structural metadata must be rebuilt or omitted if callers change function selectors.
- Parameter linking, shared optimization values, frequency expansion, carrier coupling, conjugation mask, dense solves and noise projection are independent of this dispatch choice and stay unchanged. All 101 frequencies and 193 variables are retained.

Proposal: optionally collect per-system dictionaries `{function_id: original_function_rows}` in `pairs_to_arrays` before JAX conversion. Have `run_build_step` attach those groups. For each nonempty group, call a reusable JIT helper with a static function ID, using scalar `lax.map` and the same per-function checkpoint setting as seed8. Reassemble the full function output matrix in original row order, then use the unchanged output selection and single destination scatter. Keep the existing dynamic-switch path for calls without groups.

Hypothesis: homogeneous scalar maps remove runtime component switching and mixed-branch reverse residual handling, reducing compilation and possibly runtime enough to repay extra setup and small output scatters. This is distinct from scalar-versus-batched dynamic switching and checkpoint-placement trials. More separately compiled groups, gathers/scatters and changed reverse accumulation order may instead worsen total time or strict gradients. No HLO inspection or speedup is claimed.

## Candidate 1 status

Candidate SHA and screen/full run IDs: pending supervisor. No benchmark or simulator run performed locally. Next: implement this one proposal, perform source/syntax checks, then submit via the supervisor for screen and eligible full official plus strict saved-output/gradient validation. Promotion requires both checks and measured first-run evidence.

Implementation completed in `build.py` and `simulate.py`: optional host-side group collection, keyword-only simulator metadata, a static-ID JIT helper mapping checkpointed functions, and reconstruction of the original output rows. Existing positional build/simulate arguments, dynamic fallback, scalar component mapping, conjugation mask, all component formulas and all solve operations are preserved. The original function-index arrays remain in the API; groups describe the same selectors structurally. Callers editing selectors after build must remove `component_groups` to use dynamic dispatch or rebuild the metadata.

Local checks (no JAX/dependency imports or simulator execution):

- Python syntax compilation and `git diff --check` passed.
- Executed only the host grouping helper with an array-construction stub: 104 deterministic cases passed, covering all 19 function IDs, empty/dummy groups, repeated types, full row coverage, reconstruction under sorted dictionary traversal, repeated output selections and overlapping final destinations. This validates metadata/order mechanics, not numerical JAX behavior.
- AST comparison against seed8 confirms only the intended builder/dispatch functions changed. After stripping the three extra group arguments and their `vmap` axes, the entire physical `simulate` body is identical; its positional signature is unchanged. Component/solve functions remain unchanged.
- Changed paths are only the two permitted simulator files and this note. No commits, pushes, queue calls, benchmarks, dependency changes, additional agents or persistent compilation caching.

Candidate is ready for supervisor evaluation. First-run speed, setup overhead, compilation, warm execution, peak memory, strict output and gradient errors are all unmeasured for this revision. Await exact SHA and screen/full run identifiers before accepting or rejecting the hypothesis. A strict-only failure remains unresolved and blocks promotion even if the official check passes.

## Candidate 1 evaluation and decision

- SHA: `302e886f6297a80d92b4428d97dfd9b56fd75f52`; sole numerical parent seed8 `1e552d675c3795265be8af1ac23ffb61f90f30b1`.
- Session/thread identifier now supplied by supervisor: `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`; agent `codex-component-specialization`. Candidate 2 resumed with 3157 seconds remaining in this same session.
- Screen `b066c6dab83a47cf82dfc6422ef14f75`, request `d7794ab9bce646a8be42b8e7968bb6f1`: passed screening, first-run 27.244300950 s, compilation/lowering 11.464690378 s, process wall 28.687271535 s, peak RSS 13338128 KiB. No warm or finite-difference check in screen.
- Full `5d4499b7a50840ec92a209c176ef637e`, request `77451640e6e5460bb9cf24dff43a7100`: official and strict comparison passed, first-run 26.997383825 s, compilation/lowering 11.359630290 s, warm median 14.715443436 s, process wall 110.158885954 s, peak RSS 13386580 KiB. Serial CPU2, fixed environment, all 101 frequencies/193 variables, no persistent cache.

| Full first-run phase | Seconds |
| --- | ---: |
| imports | 0.293467354 |
| initialize | 0.002894489 |
| load | 0.001416886 |
| build | 0.787700910 |
| forward lower | 0.838619985 |
| forward compile | 4.587969666 |
| forward execute | 12.426714513 |
| sensitivity lower | 0.082042860 |
| sensitivity compile | 0.380342463 |
| sensitivity execute | 0.000918571 |
| gradient lower | 0.326705433 |
| gradient compile | 5.143949883 |
| gradient execute | 2.124302907 |
| host transfer | 0.000337904 |

Saved-array comparison inspected: carrier, signal, noise, sensitivity, powers, parameters and frequencies have zero maximum absolute and relative-L2 error. Gradient maximum absolute error is 1.5178830414797062e-18, relative L2 2.153189561034473e-23, maximum normalized tolerance error 2.627152248723926e-11, zero failing coordinates at rtol=1e-7 and scale_atol=1e-12. Loss reported as 9.793036291535532e-08, unchanged from the baseline report; loss is not an NPZ comparison key. Full saved arrays represent the last warm evaluation. Official two-step finite-difference check passed; maximum reference log-sensitivity error 5.374104176780747e-06.

Decision: retain candidate 1 as this direction's best fully validated candidate. Its one full first-run sample is about 1.09 s faster than the supplied approximately 28.09 s seed8 repeated result; repeated full timing is still needed to establish superiority. Against the historical seed8 full breakdown, the observed benefit is mainly compilation (11.36 versus 12.77 s), while build, forward and first gradient execution are slightly higher. The warm median is not improved against that historical single run. No HLO evidence or causal attribution beyond this phase observation is claimed.

## Candidate 2 proposal

- Parent candidate: validated `302e886f6297a80d92b4428d97dfd9b56fd75f52`, itself descended from seed8. Current supervisor bookkeeping HEAD: `e535134920301946a2b8fc6382010ec2fc23f54f`. No additional branch or numerical candidate combined.
- Focused change: replace `lax.map` with `vmap` only inside `_evaluate_component_group`. Keep the JIT boundary, static function ID, function-local checkpoint with `prevent_cse=False`, all structural groups, output reconstruction and the dynamic fallback unchanged.
- Source justification: each group now selects a single Python function before mapping. There is no mixed-type `lax.switch` inside this helper, unlike the original batched-switch implementation that seed3 replaced. Thus homogeneous vectorization need not evaluate unused component types. This is an isolated alternative to scalar iteration enabled by candidate 1, not a repeat of heterogeneous batched switching.
- Hypothesis: removing the per-type scalar loop may reduce compilation and iteration costs while retaining the exclusion of unused function branches. Larger vectorized intermediates, altered fusion/reduction order and checkpoint batching may instead increase memory/time or fail strict comparison. All group members, parameters, zeros and frequency samples remain evaluated.
- Candidate SHA/run IDs and measurements pending supervisor. Require a new screen and full official plus strict saved-output/gradient validation before acceptance; candidate 1 remains the fallback.

Implementation complete. Syntax and `git diff --check` passed. AST isolation check confirms that only the homogeneous helper's map expression and docstring changed relative to candidate 1; checkpoint configuration is identical. `build.py` is byte-identical to candidate 1. No local numerical evaluation, benchmark, environment change or protected-file edit. Ready for evaluation; no candidate-2 speedup is claimed.

## Candidate 2 evaluation and decision

- SHA `1b0def4a91575f7fb5bf9d062b3bff46b6c1593d`; implementation parent is candidate 1 `302e886f6297a80d92b4428d97dfd9b56fd75f52`. Supervisor provenance still lists the original seed8 direction parent; this note identifies the immediate candidate ancestry explicitly. No external candidate combined.
- Screen `a6ac6d33ff5d45dcb7c4f828343683f9`, request `414d0fc64e464acf8fae0a8045ed98f8`: passed, first-run 26.948518388 s, compilation/lowering 11.648736611 s, process wall 28.175187925 s, peak RSS 13319728 KiB.
- Full `e967936d11324615ab060a031d2dd111`, request `a8540aa17b7942268cd1bf9bef40a56c`: official and strict checks passed. First-run 26.808539582 s, compilation/lowering 11.591000492 s, warm median 14.294151178 s, process wall 109.171114543 s, peak RSS 13347880 KiB. Full workload and fixed CPU2 environment unchanged.

| Full first-run phase | Seconds |
| --- | ---: |
| imports | 0.285187881 |
| initialize | 0.002887400 |
| load | 0.001398889 |
| build | 0.781435676 |
| forward lower | 0.780527916 |
| forward compile | 4.792930365 |
| forward execute | 12.275597235 |
| sensitivity lower | 0.076766603 |
| sensitivity compile | 0.372278752 |
| sensitivity execute | 0.000874709 |
| gradient lower | 0.271917293 |
| gradient compile | 5.296579564 |
| gradient execute | 1.869828904 |
| host transfer | 0.000328396 |

Saved-array comparison inspected: all physical outputs, parameters and frequencies have zero maximum absolute and relative-L2 errors. Full gradient maximum absolute error 2.168404344971009e-18, relative L2 3.0759654812695556e-23, normalized tolerance error 3.7530746410341796e-11, zero failing coordinates. Tolerances remain rtol=1e-7, scale_atol=1e-12. Reported loss unchanged at 9.793036291535532e-08; official finite-difference check passed and maximum log-sensitivity error remains 5.374104176780747e-06. Saved-array scope is last warm evaluation.

Decision: retain candidate 2 for the next isolated experiment. Its first-run sample is 0.188844 s below candidate 1, with lower first forward/gradient execution and warm median but slightly higher compilation. This does not establish repeatable superiority; both candidates remain validated alternatives. Candidate 2 is the lowest observed fully validated first-run result in this session.

## Candidate 3 proposal

Resumed with 2903 seconds remaining; same session/thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`. Numerical parent `1b0def4a91575f7fb5bf9d062b3bff46b6c1593d`; no other combination.

Source evidence: `update` reconstructs the K-by-4 function-output matrix using a separate `.at[rows].set(...)` for every type. The builder's groups partition the original rows exactly once, so these scatters do not overlap. Their order is therefore immaterial. This is different from the final physical matrix scatter, whose ordering must remain unchanged.

Proposal: concatenate all evaluated group outputs and their original row indices, then restore the complete function-output matrix with one scatter. Leave homogeneous vectorization, checkpointing, JIT boundaries, all original output selection and the final physical matrix scatter unchanged. Keep the empty-group case and dynamic fallback. No parameter values or zero entries are filtered.

Hypothesis: one reconstruction scatter may reduce intermediate update/transpose work and compilation compared with a chain of per-type scatters. Concatenation costs may offset this benefit; backend elimination of the previous intermediates has not been measured. No HLO or speedup claim. Require fresh full official and strict checks before accepting candidate 3; candidate 2 remains the validated fallback.

Implementation complete. Syntax and diff whitespace checks passed. AST comparison against candidate 2 confirms that only the grouped output-reconstruction branch changed. Executed the actual old and new reconstruction AST blocks with list-backed array/scatter stubs on 104 deterministic cases, including empty groups, all 19 possible IDs, shuffled group order and zero-valued entries: restored outputs matched in every case. This verifies indexing/ordering mechanics, not JAX lowering, derivatives or physics. No local simulator or benchmark run. Candidate SHA and evaluation run IDs pending supervisor.

## Candidate 3 evaluation and decision

- SHA `e82b74c1d27425b9e0b44a377c222fb1654b895b`, immediate implementation parent `1b0def4a91575f7fb5bf9d062b3bff46b6c1593d`. No external combination.
- Screen `e79786a7df314069a9485c60fa61c566`, request `c743d7eb0161415b8a000a01fc890e95`: screening passed; first-run 26.790161006 s, compilation/lowering 11.584146068 s, process wall 27.945163185 s, peak RSS 13280664 KiB.
- Full `d78ce650cedf4fce844709e3f9e7eddc`, request `d585118ae73a4815a223d326e0e6fe9c`: official and strict passed; first-run 26.887085902 s, compilation/lowering 11.671893857 s, warm median 14.292649498 s, process wall 109.722902566 s, peak RSS 13299248 KiB. Full CPU2 workload/environment unchanged.

| Full first-run phase | Seconds |
| --- | ---: |
| imports | 0.291335378 |
| initialize | 0.002913447 |
| load | 0.001423476 |
| build | 0.784298800 |
| forward lower | 0.742282812 |
| forward compile | 4.843130931 |
| forward execute | 12.238698130 |
| sensitivity lower | 0.079772426 |
| sensitivity compile | 0.378169376 |
| sensitivity execute | 0.000833191 |
| gradient lower | 0.301539470 |
| gradient compile | 5.326998843 |
| gradient execute | 1.895360677 |
| host transfer | 0.000328945 |

Comparison inspected: carrier, signal, noise, sensitivity, powers, parameters and frequencies match exactly (zero maximum absolute/relative-L2 errors). Gradient maximum absolute error 2.168404344971009e-18, relative L2 3.0759654812695556e-23, normalized tolerance error 3.7530746410341796e-11 and zero failures, at unchanged rtol=1e-7/scale_atol=1e-12. Loss is unchanged at 9.793036291535532e-08 in the report. Official gradient check passed; reference log-sensitivity error remains 5.374104176780747e-06. Saved comparisons cover last warm evaluation.

Decision: reconstruction consolidation is correctness-validated but has no demonstrated timing advantage. Its full first-run is 0.078546 s slower than candidate 2, whereas screen is faster; warm medians differ by only 0.001502 s. Peak RSS is 48632 KiB lower in the full run, but repeat evidence is absent. Retain this simpler single-scatter implementation for the next experiment, not as a claim of measured speedup. Candidate 2 still holds the lowest observed validated full first-run time.

## Candidate 4 proposal

Same session/thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`, 2595 seconds remaining on resumption; continue beyond candidate 4 within the existing deadline. Immediate numerical parent is validated candidate 3 `e82b74c1d27425b9e0b44a377c222fb1654b895b`; seed8 remains the original ancestor, and no external candidate is combined.

Focused change: remove `jax.checkpoint` only from `_evaluate_component_group`, leaving its static-ID JIT helper, `vmap`, grouping/reconstruction and all physical operations intact. The dynamic fallback keeps seed8's checkpointed scalar switch.

Rationale: checkpoint placement was previously evaluated around heterogeneous dispatch. Homogeneous groups no longer share a switch residual structure, and candidate 3 still spends 5.327 s compiling the gradient. Test whether ordinary autodiff of each homogeneous function yields a smaller reverse compilation and avoids recomputation, at the expense of retaining more forward intermediates. This is a new execution structure, not a re-run of seed7/seed8 checkpoint placement. It may worsen forward compilation, residual memory or total time. No claim that checkpointing caused the measured gradient compilation cost, and no HLO inspection. The full first-run objective, memory and strict full gradient determine acceptance.

Candidate 4 SHA and run IDs pending supervisor; candidate 2/3 remain validated fallbacks. No local benchmark or numerical execution.

Implementation ready. Syntax and whitespace checks passed; AST comparison to candidate 3 confirms only the homogeneous helper body changed. The dynamic fallback checkpoint and every builder, reconstruction, component and solve operation remain unchanged. Numerical correctness and timing require the supervisor's new evaluation.

## Candidate 4 evaluation and decision

- SHA `4ffe2a0bd4dec631e36d037a8f922880446312e7`, immediate parent `e82b74c1d27425b9e0b44a377c222fb1654b895b`.
- Screen `ca4797d991fe4223aafe067223960b67`, request `f3ce5fca656f454593fa9dddc2a44810`: passed; first-run 26.392501418 s, compilation/lowering 11.211467676 s, process wall 27.700641869 s, peak RSS 13551036 KiB.
- Full `d8bc935d342d4c879f784ab3282bd813`, request `a68f850431654bcf95065d591299b4dd`: official and strict passed; first-run 26.431100650 s, compilation/lowering 11.240360152 s, warm median 14.477085605 s, process wall 108.898283318 s, peak RSS 13565068 KiB. CPU2, precision and complete workload unchanged.

| Full first-run phase | Seconds |
| --- | ---: |
| imports | 0.289147345 |
| initialize | 0.002909500 |
| load | 0.001511564 |
| build | 0.774656579 |
| forward lower | 0.711232491 |
| forward compile | 7.806842657 |
| forward execute | 12.277531415 |
| sensitivity lower | 0.073109210 |
| sensitivity compile | 0.388262665 |
| sensitivity execute | 0.000846399 |
| gradient lower | 0.195211111 |
| gradient compile | 2.065702019 |
| gradient execute | 1.843756368 |
| host transfer | 0.000381326 |

Comparison inspected: all saved physical outputs, parameters and frequencies match exactly. Gradient maximum absolute error 2.168404344971009e-18, relative L2 3.0759654812695556e-23, normalized tolerance error 3.7530746410341796e-11, zero failures at unchanged strict tolerances. Loss unchanged at 9.793036291535532e-08; official finite-difference gradient check passed. Maximum reference log-sensitivity error remains 5.374104176780747e-06. Saved comparison is of the last warm evaluation.

Decision: retain candidate 4 as lowest observed validated first-run result. Versus candidate 3, forward compilation rose from 4.843 to 7.807 s while reverse compilation fell from 5.327 to 2.066 s. Total fell by 0.455985 s; full peak RSS rose by 265820 KiB and warm median rose by 0.184436 s. The expected reverse-compilation reduction occurred, but with material phase tradeoffs; repeated full measurements are still required for superiority claims.

## Candidate 5 proposal

Same thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`; resumed with 2318 seconds remaining. Immediate numerical parent `4ffe2a0bd4dec631e36d037a8f922880446312e7`; no external candidate combination.

Source evidence: candidate 4 concatenates groups, scatters the resulting K-by-4 array back into original function-row order, then gathers `output_indices`. The permutation is already completely determined by the builder's function-index list. If concatenated group order is `p`, construct `inverse[p[j]] = j` during setup. Then `restored[output_rows, columns]` equals `concatenated[inverse[output_rows], columns]`. This removes the floating-point reconstruction scatter and its derivative while retaining all rows and the exact final matrix-update sequence.

Proposal: store a sorted function-group dictionary plus this inverse permutation in structural metadata; gather selected outputs directly from concatenated results. Explicitly sort function IDs in both builder and consumer, avoiding dependence on dictionary insertion order versus JAX pytree traversal. Existing dynamic function-index arrays, input rows, output indices and final matrix indices stay unchanged. Legacy calls without metadata keep the dynamic fallback. The experimental grouping metadata changes representation and must be rebuilt with the new builder; it is not an array of physical answers.

Hypothesis: replacing output reconstruction with an integer index gather reduces assembly/transpose compilation and work. Extra setup permutation construction and runtime index gathering may offset the gain. No entries, parameter-dependent zeros or gradient coordinates are omitted. No solve change or HLO claim. New full official and strict checks required; candidate 4 remains the fallback.

Implemented `function_rows` and `output_rows` metadata, with direct grouped-output selection. Syntax and whitespace checks passed. AST scope checks found only `_group_component_indices`, its caller's documentation and `update` changed relative to candidate 4; `pairs_to_arrays` executable body is identical. Executed the actual host grouping helper using an array-construction stub on 104 cases: the inverse permutation covers every row and preserves selected values and final writes, including repeated output selections, overlapping destinations, zeros and all function IDs. No JAX/physics execution locally. Candidate SHA/run IDs and measurements remain pending supervisor.

## Candidate 5 evaluation and decision

- SHA `1ccbecf572eb90c4866a8d077b5d15d6bd28124d`, immediate parent `4ffe2a0bd4dec631e36d037a8f922880446312e7`.
- Screen `da53834d9b734caebba838d75732fdce`, request `fbc26e7434ef4514ae698926b6dc8098`: passed, first-run 26.174530830 s, compilation/lowering 10.901315639 s, process wall 27.483429043 s, peak RSS 13521588 KiB.
- Full `c1de187ffa7747b48684605ff08e96e5`, request `ccd064953f764f3e860dac805068d54d`: official and strict passed, first-run 25.988602759 s, compilation/lowering 10.737356391 s, warm median 14.474465085 s, process wall 108.610561408 s, peak RSS 13531880 KiB. Same full CPU2 workload/environment.

| Full first-run phase | Seconds |
| --- | ---: |
| imports | 0.287937399 |
| initialize | 0.002976298 |
| load | 0.001411846 |
| build | 0.804368744 |
| forward lower | 0.696012985 |
| forward compile | 7.473001687 |
| forward execute | 12.301107166 |
| sensitivity lower | 0.076449912 |
| sensitivity compile | 0.406053616 |
| sensitivity execute | 0.000896560 |
| gradient lower | 0.191199237 |
| gradient compile | 1.894638954 |
| gradient execute | 1.852221217 |
| host transfer | 0.000327138 |

Comparison inspected: physical outputs, parameters and frequencies match exactly. Gradient max absolute error 1.5178830414797062e-18, relative L2 2.153189561034473e-23, max normalized tolerance error 2.627152248723926e-11, zero failing coordinates with unchanged strict tolerances. Reported loss remains 9.793036291535532e-08; official finite-difference check passed; max reference log-sensitivity error 5.374104176780747e-06. Saved comparison covers last warm evaluation.

Decision: retain candidate 5 as lowest observed validated full first-run result. Compared with candidate 4, first-run fell 0.442498 s and compilation/lowering fell 0.503004 s, while build rose 0.029712 s and warm medians remain nearly equal. This supports further investigation of structural assembly metadata, but repeated full runs are needed before claiming repeatable superiority.

## Candidate 6 proposal

Same thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`; 1957 seconds remaining on resumption. Immediate numerical parent `1ccbecf572eb90c4866a8d077b5d15d6bd28124d`. No external combination.

Source evidence: `update` always uses a generic `.at[row, column].set(outputs)` even when all destination pairs are distinct. Unlike the earlier function-output reconstruction, this scatter operates on the full carrier/signal/noise matrix. The builder has host-side destination indices, and `run_build_step` has matrix shapes before tracing. This permits proving destination uniqueness without inspecting physical parameter values.

Proposal: check each system's full destination list at setup, normalize negative indices against the actual matrix shape, and only mark uniqueness when all normalized destinations are in bounds and distinct. Carry the verified property as the presence of an empty-tuple metadata key (static dictionary structure, no traced Boolean conversion). Pass that property as the scatter's `unique_indices` hint. If metadata, shapes or the proof are absent, retain the default overlapping-index behavior. No sorting, dropping, summation or physical matrix-write reordering. This proof concerns destination indices only; parameter-dependent zeros remain included.

Hypothesis: exposing proven non-overlap may simplify scatter differentiation and compilation, particularly the forward AD residual preparation. No claim is made that current HLO contains redundant duplicate-resolution work or that the public fixture is proven unique before the builder runs. Setup checks count in the objective. Generic callers modifying selectors or destination indices must rebuild or omit grouping metadata. Require fresh full official and strict validation; candidate 5 remains fallback.

Implemented the host-only proof and static key marker, with actual matrix shapes supplied by `run_build_step`. Absent metadata/shapes, unproved dummy updates, overlapping/aliased indices, unequal coordinate-list lengths and out-of-bounds indices retain `unique_indices=False`. Syntax and diff checks passed. Tested the extracted proof helper against an independent Python nested-list indexing oracle on 3600 cases over matrix dimensions 1–6, plus explicit negative aliases, duplicate and invalid cases; all passed. AST scope comparison confirms the physical `simulate` body is unchanged (documentation only), and modifications are limited to structural setup and the scatter hint. No local numerical/JAX execution or benchmark. Candidate SHA/run IDs and performance remain pending supervisor.

## Candidate 6 evaluation and decision

- SHA `4e8292e6dead5c681fd4622016c6ab614ccbde07`, immediate parent `1ccbecf572eb90c4866a8d077b5d15d6bd28124d`.
- Screen `a3c3e46a7dde46a98937690fcdacd1b1`, request `f96d70255d954985b5424b50dc13eee9`: passed, first-run 25.750595091 s, compilation/lowering 10.601917751 s, process wall 26.985850697 s, peak RSS 13510388 KiB.
- Full `56a6c98700e44d8db3aae748f5f87a92`, request `7208b5d5e9bc4a989f814c2b5b833baa`: official and strict passed; first-run 25.703418577 s, compilation/lowering 10.620367493 s, warm median 14.226642456 s, process wall 108.144107947 s, peak RSS 13515180 KiB. Full CPU2 workload/environment unchanged.

| Full first-run phase | Seconds |
| --- | ---: |
| imports | 0.293313367 |
| initialize | 0.002878660 |
| load | 0.001419147 |
| build | 0.807291880 |
| forward lower | 0.691843785 |
| forward compile | 7.299492361 |
| forward execute | 12.128427580 |
| sensitivity lower | 0.076930014 |
| sensitivity compile | 0.483766779 |
| sensitivity execute | 0.000862632 |
| gradient lower | 0.188822137 |
| gradient compile | 1.879512416 |
| gradient execute | 1.848562000 |
| host transfer | 0.000295816 |

Comparison inspected: saved physical outputs, parameters and frequencies exactly match. Gradient max absolute error 1.5178830414797062e-18, relative L2 2.153189561034473e-23, normalized tolerance error 2.627152248723926e-11, no failures at unchanged strict tolerances. Loss unchanged at 9.793036291535532e-08, official gradient check passed, reference log-sensitivity error 5.374104176780747e-06. Saved comparison scope remains last warm evaluation.

Decision: retain candidate 6 as lowest observed validated full first-run result. Versus candidate 5, first-run fell 0.285184 s, compilation/lowering fell 0.116989 s and warm median fell 0.247823 s. Single full timing is not repeat confirmation. The evaluator did not report which systems received the uniqueness marker, so no measured per-system application count or compiled-work removal is claimed.

## Candidate 7 proposal

Same thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`; resumed with 1653 seconds remaining. Immediate numerical parent `4e8292e6dead5c681fd4622016c6ab614ccbde07`; no external combination.

Source evidence: immediately after signal component assembly, `simulate` gathers carrier-coupled entries, scales them by the solved carrier, then overwrites them with another `.at[:, rows, columns].set(signal_entries)`. These destinations are separately available as host `carrier_solution_placing_indices` in the signal builder. Candidate 6's proof only applies to the component-update scatter and says nothing about this second destination list.

Proposal: run the existing negative-alias-aware uniqueness proof independently on the carrier-coupling destination list. Store a separate static marker only on success and use it for this signal scaling scatter. Distinct row/column pairs imply disjoint updates across the leading frequency batch: each frequency has its own matrix, and the batch slice occurs once. No scaling arithmetic, carrier gather, destination ordering or conjugation change. Unknown/overlapping cases retain generic scatter behavior.

Hypothesis: this independent hint may reduce duplicate-handling residual/compilation work for the large frequency-batched signal scatter. Its actual compiled effect is unmeasured, and extra setup also counts. Candidate 6 remains the validated fallback; require fresh official and strict validation.

Implementation ready. Syntax/whitespace checks passed. Exact AST isolation verifies only the independently guarded builder marker and the signal-scaling scatter's `unique_indices` keyword changed relative to candidate 6. The existing proof helper is unchanged; batch-coordinate non-overlap was additionally checked for 1, 2 and 101 samples. No local simulator/benchmark run. Candidate SHA, run IDs and measurements pending supervisor.

## Candidate 7 evaluation and decision

- SHA `585f25ce1f9113597c9e69eea50ccfdccb532ab5`, immediate parent `4e8292e6dead5c681fd4622016c6ab614ccbde07`.
- Screen `38c7f31332b84f1d9cca3c0cafbd160c`, request `70d0a14d9f964d9caf6958697df30be8`: passed, first-run 24.881597809 s, compilation/lowering 10.425714251 s, process wall 25.945307883 s, peak RSS 12551556 KiB.
- Full `2d83c6ba8dc342c381e3814716d6eeb0`, request `dcad521294cb4f64bd3a515b1d5d3347`: official and strict passed; first-run 24.902803898 s, compilation/lowering 10.431022622 s, warm median 13.822272493 s, process wall 105.298484385 s, peak RSS 12551088 KiB. Full CPU2 workload/environment unchanged.

| Full first-run phase | Seconds |
| --- | ---: |
| imports | 0.297318654 |
| initialize | 0.002855640 |
| load | 0.001487916 |
| build | 0.772625009 |
| forward lower | 0.688575095 |
| forward compile | 7.161918430 |
| forward execute | 11.532702982 |
| sensitivity lower | 0.086579068 |
| sensitivity compile | 0.400828812 |
| sensitivity execute | 0.000875631 |
| gradient lower | 0.191577937 |
| gradient compile | 1.901543280 |
| gradient execute | 1.863590948 |
| host transfer | 0.000324495 |

Comparison inspected: all saved physical outputs, parameters and frequencies exactly match. Gradient max absolute error 1.5178830414797062e-18, relative L2 2.153189561034463e-23, normalized tolerance error 2.627152248723926e-11, zero failing coordinates at unchanged strict tolerances. Loss remains 9.793036291535532e-08; official finite-difference check passed; max reference log-sensitivity error 5.374104176780747e-06. Comparison scope: last warm evaluation.

Decision: retain candidate 7 as lowest observed validated first-run result. Versus candidate 6, full first-run fell 0.800615 s, first forward execution fell 0.595725 s, warm median fell 0.404370 s and peak RSS fell 964092 KiB (about 0.92 GiB). This is promising timing/memory evidence from a separate screen and one full run, not repeated-full confirmation or proof of a particular HLO optimization.

## Candidate 8 proposal

Same thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`; resumed with 1373 seconds remaining. Immediate numerical parent `585f25ce1f9113597c9e69eea50ccfdccb532ab5`; no external combination.

Source evidence: candidate 7's signal-scaling scatter has verified non-overlapping coordinates, but the immediately preceding gather uses ordinary indexing at the same coordinates. Its reverse operation accumulates cotangents into the full signal matrix. The existing proof, including negative-index aliases and leading batch disjointness, applies to this gather too. It does not apply to the carrier-solution gather, which can legitimately repeat entries and must remain unchanged.

Proposal: use `.at[:, rows, columns].get(unique_indices=verified)` for only the signal-matrix gather, reusing the same Boolean computed from static metadata for its following scatter. Keep normal gather/scatter behavior when uniqueness is not proven. No new setup, changed arithmetic, dropped entries or extra physical assumptions.

Hypothesis: informing the gather's transpose of disjoint destinations may reduce reverse accumulation work or compilation. Actual lowered effects and performance are unmeasured. Candidate 7 remains fallback; new full official and strict validation required.

Implementation complete. Syntax/whitespace checks passed; exact AST normalization verifies only the signal-matrix gather hint and reuse of the existing scatter flag changed. Builder is byte-identical to candidate 7. Existing uniqueness proof is reused; no new structural inference or local numerical/benchmark run. SHA, run IDs and results pending supervisor.

## Candidate 8 evaluation and decision

- SHA `a4923527a59fb15d2bdf4ac553bf4b3fdd76bfc4`, immediate parent `585f25ce1f9113597c9e69eea50ccfdccb532ab5`.
- Screen `f6c9675ccda64a8f9014f6e155b65fb3`, request `117192a06d274aef88cd7cdc1d95b618`: passed; first-run 24.904913539 s, compilation/lowering 10.462944172 s, process wall 26.206730263 s, peak RSS 12548568 KiB.
- Full `fc1c8ed8c6e24a0ca5b3a8e7aff28881`, request `264b027a59de41acbe20131523eca6a5`: official and strict passed; first-run 24.992129887 s, compilation/lowering 10.607761912 s, warm median 13.556135844 s, process wall 104.846886175 s, peak RSS 12556792 KiB. Full CPU2 workload unchanged.

Full first-run phase seconds: imports 0.289227687; initialize 0.002961870; load 0.001516815; build 0.772823865; forward lower 0.692426173; forward compile 7.256156135; forward execute 11.507096585; sensitivity lower 0.086774582; sensitivity compile 0.401428452; sensitivity execute 0.000879541; gradient lower 0.192533428; gradient compile 1.978443142; gradient execute 1.809534656; host transfer 0.000326956.

Comparison inspected: physical outputs, parameters and frequencies match exactly; gradient max absolute error 1.5178830414797062e-18, relative L2 2.153189561034463e-23, max normalized tolerance error 2.627152248723926e-11, zero failing coordinates at unchanged strict tolerances. Loss unchanged at 9.793036291535532e-08; official gradient check passed; max reference log-sensitivity error 5.374104176780747e-06. Saved comparison covers last warm evaluation.

Decision: no clear first-run improvement from the gather hint. Full first-run rose 0.089326 s versus candidate 7 while warm median fell 0.266137 s; peak RSS is nearly unchanged. Keep the correctness-validated hint for the next test, without attributing the warm difference to it. Candidate 7 remains the lowest observed full first-run result. Repeats of the final best revision remain necessary for repeatable-superiority claims.

## Candidate 9 proposal

Same thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`, 1124 seconds remaining on resumption. Immediate numerical parent `a4923527a59fb15d2bdf4ac553bf4b3fdd76bfc4`; no external combination.

Focused change: add `inline=True` only to `_evaluate_component_group`'s existing JIT decorator. Its function ID remains static; function formulas, homogeneous `vmap`, no-checkpoint policy and all indexing/uniqueness metadata remain identical.

Hypothesis: exposing homogeneous component computation to its caller may simplify optimization of parameter gathers, saved residuals and selected outputs, lowering the still-dominant forward compilation cost. It can instead duplicate work or worsen compiler optimization. Seed9 tested inlining around a dynamic switch and was slower; this explicitly tests the later static, homogeneous, non-checkpointed structure, so the prior outcome is context rather than proof. No HLO or predicted numeric speedup. New official and strict full checks required; candidate 7/8 remain validated alternatives.

Implementation ready. Syntax/whitespace checks passed; exact AST comparison confirms the only executable change is that single JIT decorator keyword. No local simulator or benchmark run. Candidate SHA/run IDs and measurements pending supervisor.

## Candidate 9 evaluation and decision

- SHA `33cc72e1ee0764979d86a965552292159a8f313e`, immediate parent `a4923527a59fb15d2bdf4ac553bf4b3fdd76bfc4`.
- Screen `c6061a436cef4301a26afa6ff55c7002`, request `a848b477fe884c088b042777005cf2cf`: passed; first-run 24.854818612 s, compilation/lowering 10.452970617 s, process wall 25.968431581 s, peak RSS 12548040 KiB.
- Full `7d2ad35f2151448e9bd927af81741b70`, request `38f0d762c414439785ab0c7bb55aecb3`: official and strict passed; first-run 25.189547028 s, compilation/lowering 10.493717391 s, warm median 13.449909711 s, process wall 104.987963028 s, peak RSS 12552356 KiB.

Full first-run phase seconds: imports 0.285923159; initialize 0.002912831; load 0.001481073; build 1.110181293; forward lower 0.686955608; forward compile 7.200912375; forward execute 11.488893779; sensitivity lower 0.201501675; sensitivity compile 0.347781913; sensitivity execute 0.000869479; gradient lower 0.135971799; gradient compile 1.920594020; gradient execute 1.805260187; host transfer 0.000307838.

Supplied saved-array comparison inspected: carrier, signal, noise, sensitivity, powers, parameters and frequencies match exactly; gradient max absolute error 1.5178830414797062e-18, relative L2 2.153189561034463e-23, max normalized tolerance error 2.627152248723926e-11 and zero failures. Loss remains 9.793036291535532e-08; official finite-difference check passed and max reference log-sensitivity error remains 5.374104176780747e-06. Comparison scope is last warm evaluation; full workload unchanged.

Decision: retain inlining for the next isolated experiment, but claim no established speed benefit. Full first-run rose 0.197417 s versus candidate 8, with build time up 0.337357 s; total compilation/lowering fell 0.114045 s and warm median fell 0.106226 s. Screen was slightly faster than candidate 8. These separate observations do not isolate causality. Candidate 7 remains lowest observed validated full first-run (24.902804 s).

## Candidate 10 proposal

Same thread `01a1fedf-f7aa-77b2-885d-75aceeb4c48c`, 808 seconds remaining on resumption. Immediate parent `33cc72e1ee0764979d86a965552292159a8f313e`; no external combination.

Focused change: in the homogeneous path, replace `parameters[function_input_indices][rows]` with `parameters[function_input_indices[rows]]`. The generic fallback retains its original gather and dynamic dispatch. Group iteration, component evaluation, output remapping, scatter ordering, uniqueness hints and physics are unchanged. The empty-group output shape now reads the index-array shape, which equals the former gathered array's leading dimension.

Hypothesis: composing structural indices before gathering differentiable values removes the intermediate full component-input value array from the grouped reverse pass. Constant index composition may also simplify compilation. It may instead increase separate parameter-gradient accumulations; effect on runtime, compiler work and floating-point reduction order remains unmeasured. This is structural indexing, not cached physical data. No additional host preparation or persistent cache is introduced.

Validation: syntax and whitespace checks passed; AST comparison confirms all functions other than `update` are unchanged. A standard-library-only check of 1000 randomized input-index/group-row cases verifies exact value selection and integer-cotangent routing, including repeated parameter indices, negative aliases and empty selections. This is an algebra/structure check, not numerical JAX or performance validation. No local simulator or benchmark execution. Fresh official full and strict gradient/output checks required. SHA/run IDs and timings pending supervisor.
