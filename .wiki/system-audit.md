# Evaluation system audit and decisions

The user confirmed Feyer allocation on 21 November 2026. Three independent audit agents reviewed numerical acceptance, the evaluator/resource envelope, and the queue/feedback/reporting path. The existing simulator worktrees and canonical benchmark were not edited by this audit.

## Decisions

| Area | Decision | Limit of the claim |
| --- | --- | --- |
| Official validity | Preserve the unchanged official harness and expose its result separately | Passing its spot checks is not a proof of all derivatives or unseen setups |
| Internal promotion | Keep the existing strict saved-array tolerance for automatic promotion | A strict-only failure means numerical review, not official disqualification |
| Expanded derivative validation | Use parameter-scaled, bound-aware step sweeps and independent primitive/directional checks for substantial solver changes | The expanded protocol is documented, not yet an implemented complete test suite |
| CPU budget | One logical CPU, affinity CPU 2, one numerical-library thread | AMD and final Intel processors remain different; compare against matching local baselines |
| Memory budget | 32,000,000,000 bytes per evaluation, screen and full; process-group RSS watchdog plus post-run peak rejection | No kernel cap is possible inside the current read-only cgroup mount; short peaks can evade sampling |
| Instance utilization | Keep the instance's full allocation; GPU VRAM is separate from system RAM | Other GPU workloads still consume some CPU/system RAM and can add timing noise |
| Timing claims | Rank complete first-run time; retain phase timings and repeated fresh-process evidence | Warm repetitions do not establish cold-start repeatability |
| Search feedback | Screen first; promising candidates receive full validation before Codex resumes | The 2% screening promotion threshold is an evaluation-cost heuristic and can miss noisy/borderline ideas; manual full submission remains available |
| Shared reporting | Synchronize completed shared-queue jobs into the local phase ledger | A local-only Git worktree scan alone misses manual agent submissions |
| Pareto display | Show official/strict status, exact observed frontier and phase/noise tradeoff labels separately | Tiny phase timings can put many candidates on the exact frontier; it is not sufficient as a search ranking |

The conservative decimal interpretation of 32 GB is about 29.8 GiB. If the organizers specify 32 GiB, the memory budget can be versioned and changed explicitly. Neither interpretation turns the AMD host into the final Intel hardware.

## Corrections implemented

- Worker validation now checks the submitted SHA, clean checkout, executed evaluator hash, canonical fixture hashes, all phase names/categories, finite phase times and their totals, one CPU, thread settings, double precision and expected output shapes.
- Execution metadata records worker/evaluator provenance, actual shared container limits and the per-job memory watchdog. Screen and full use the same monitored budget; the canonical timing code remains unchanged.
- Official pass, strict regression pass, checker infrastructure failure and resource-budget failure are distinct fields/verdicts. Historical reports retain their original evidence; the viewer derives separate labels for them.
- Strict comparison reports identify failing indices and per-entry actual/reference/error/allowance, preserving the existing acceptance inequality.
- The misleading screening log message about finite-difference testing was corrected. Screening still omits that check and declares it not run.
- The phase ledger now includes manually submitted jobs, calibration runs and independent repetitions by job ID. Reporting compares evaluator/timing schemas as well as workloads and environment settings.
- New supervised submissions persist an idempotency UUID before uploading. Identical retries return the same queued job; conflicting payloads reject. Atomic database migration and recovery cover response loss and duplicate requests without relying on clock synchronization. Older in-flight records without a UUID retain fail-closed recovery.
- CI installs the pinned NumPy version so numerical comparison tests execute rather than being silently omitted. Local environments without NumPy explicitly report those tests as skipped; the fixed remote environment also runs them.

## Important numerical distinctions

Candidate 2 passes the official checks but exceeds the internal gradient tolerance at exactly three coordinates: `mb13.reflectivity`, `boundary01.power`, and `m03.reflectivity`. The largest absolute gradient difference is at a different coordinate that passes. The contraction appears algebraically equivalent in exact arithmetic, but which floating-point derivative is more accurate remains unresolved. We have not loosened the tolerance to accept it.

The strict tolerance uses a global absolute floor across derivatives with different physical units. It is a regression guard, not a calibrated physical error bound. See [the numerical audit](../experiments/audits/numerical.md) for exact values, limitations and the proposed independent derivative protocol.

The official full benchmark validates and saves the last warm repetition's outputs. Screening validates the timed first-run outputs. For pure deterministic code these should agree, but the official full harness does not independently validate both executions. A first-versus-warm consistency diagnostic would be additional evidence, not a change to the official harness.

That diagnostic was performed on existing candidate-2 and candidate-8 artifacts: all eight saved arrays are bitwise identical between screen-first and full-last-warm, and the recorded scalar losses match exactly. This is positive evidence for those two cases, not a general guarantee for future rewrites. See [the first-versus-warm evidence](../experiments/audits/first-warm.md).

## Resource utilization

The instance has 55 GiB of system RAM and approximately 48 GB of GPU VRAM. A CPU evaluation's 32-billion-byte monitored allowance does not allocate or disable the GPU. Keep other work away from CPU 2 and its SMT sibling where practical, and leave system-RAM headroom for the evaluator. For final comparative timing, pause heavy competing CPU/memory/I/O jobs; GPU activity alone does not guarantee absence of CPU interference.

For a true kernel-enforced 32 GB envelope, ask AMD for a delegated cgroup or a suitably constrained evaluation container. Do not use `RLIMIT_AS` as a replacement: virtual address reservations are not resident RAM. Do not change the entire instance's memory limit to constrain one benchmark.

## Open questions

1. Are there organizer tolerances for all 193 gradients beyond the public one-coordinate finite-difference check, especially for custom solvers?
2. Which parameter-family scales and admissible perturbations should define independent derivative diagnostics?
3. Can AMD provide a per-job cgroup for exact memory enforcement, and is the intended unit GB or GiB?
4. Do future finalists retain their speed advantage on the actual Intel judging hardware?

These questions do not prevent screening or conservative local comparison. They do prevent claiming proof of general numerical correctness or identical judging hardware.

## Candidate chosen for confirmation

The paired repeat study freezes candidate 8, `1e552d675c3795265be8af1ac23ffb61f90f30b1`, rather than following a moving branch tip. Its simulator diff is confined to `differometor/simulate.py`: scalar component dispatch through `lax.map`, a JIT helper with branch-local rematerialization, and one equivalent mask replacing three disjoint conjugation updates. The linear solve is unchanged; no precomputed answers, reduced workload or persistent compilation cache was introduced in that diff. Candidate 11 restores the same simulator files, but its distinct commit had only completed screening when the original agent deadline expired.

Automated checks supplement this source review. The root-user evaluation environment is cooperative, not an adversarial sandbox; hash checks and numerical tests alone do not prove that arbitrary submitted Python obeys every challenge rule.

## Repeated measurement result

Three fresh-process pairs under the audited evaluator all passed official and strict validation. Median first-run time fell from **35.720092 s to 28.093522 s**, a **21.35% reduction**, with paired reductions of **19.82–22.00%**. Baseline sampled group RSS was approximately 15.5 GB; candidate peaks were approximately 13.8 GB. All were below the monitored 32-billion-byte budget.

The main gains were compilation (median 19.6300 → 12.7776 s) and gradient execution (2.9563 → 1.8829 s). Forward execution was slightly slower (12.1191 → 12.3995 s). Thus this is a favorable total-time tradeoff, not a strict Pareto improvement in every phase. It is repeated evidence on this AMD instance, not a promise about the final Intel system.

See [the confirmation study](../experiments/audits/confirmation.md) for all pairs, exact commit/job IDs, resource observations and limitations. An additional audited screen of the same implementation passed with first-evaluation validation and the same monitored budget.
