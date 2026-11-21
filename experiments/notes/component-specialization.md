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
