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
