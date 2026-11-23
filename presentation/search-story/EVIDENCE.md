# Evidence and wording boundaries

This kit was assembled from stored results, source notes and the supplied slide text. The animation compresses the mechanism; it is not a literal reconstruction of every commit or a claim that the lab controller produced every teammate milestone.

## What the records support

| Presentation element | Evidence | Qualification |
|---|---|---|
| 35.8 s baseline; approximately 11.5 s sparse stage; 1.743 s host-engine breakthrough | Teammate `PRESENTATION.md` / `DEVELOPMENT.md` in `.lab/comparisons/akshat-c38eecda/` | Selected team-history milestones, measured under the documented scopes. Intermediate 11.5 s is approximate. |
| 28.094 s early confirmed seed | `.wiki/evolution-search-design.md`; seed8 confirmation records | Early lab lineage. Do not invent an exact parent edge into the teammate host-engine lineage. |
| Approximately 20 s later compiler-oriented exploration | Stored phase ledger; prior `7d1ccc` full run `7e6ce3c3…` at 20.05772 s | Exploratory later phase, not a new cross-cohort speedup certificate. Use an approximate rounded label. |
| “17 s → 8 s” total-time chain | Not established by the records inspected for this kit | Omit. Approximately 8 s in the supplied story is remaining **compilation**, not necessarily total first-run time. |
| Per-session branches/worktrees, exact candidate SHAs, queue, measured feedback | `.wiki/architecture.md`, `.wiki/profiling.md`, `.wiki/dag-search.md` | GitHub versions source and published evidence. Local/server controllers and durable queues execute work; GitHub does not itself run the AMD benchmark. |
| Early model-guided numerical search | `.wiki/smac-search.md`; SMAC campaign records | SMAC3 uses a random-forest surrogate and expected-improvement acquisition over registered implementation choices. Some decisions and handoffs remained human-coordinated. No proof it beat enumeration here. |
| Final finite sweep: six settings, five nondefaults rejected | [Frozen sweep/results](https://github.com/timbtz/feyer-search-lab/tree/control/overnight-20261122/experiments/campaigns/overnight-finite-v1) | Exhaustive enumeration. Every official benchmark passed, but each nondefault failed additional seed-relative checks. No final paired promotion followed. |
| Faster provisional solutions needed source review | [Paired audit](https://github.com/timbtz/feyer-search-lab/tree/control/overnight-20261122/experiments/campaigns/overnight-20261122/final-confirmation) | All four old finalists passed 40 official checks and refreshed seed suites, yet source review found approximate adjoint risks. Do not present all-pass testing as universal proof. |
| Exact teammate code versus our conservative repair | [Head-to-head analysis](https://github.com/timbtz/feyer-search-lab/blob/control/overnight-20261122/experiments/campaigns/overnight-20261122/peer-comparison/analysis.md) | Current peer `7615f59`, byte-identical simulator import `be4949e1`, versus repaired `3b107d69`. Three cold-checkout matched pairs: large 0.703439 vs 0.855262 s; aLIGO 0.542659 vs 0.538566 s. All 12 official checks pass. Not the judges’ hardware. |
| Hidden-topology generality | Organizer message supplied by user | Unknown optical topology similar to the large example; same setup-definition/input/output interface; benchmark unchanged. Finite tests cannot establish universal generality. |

## Final sweep data used by the animation

All entries below are **one** complete first-run measurement per setup from a fresh checkout, not medians. Large runs first; aLIGO follows it. Double precision, one logical CPU, unchanged official harnesses. The 14-case comparison uses the established seed; it is not an independent high-precision oracle.

| SuperLU setting | Large / s | aLIGO / s | Public checks | Additional seed checks |
|---|---:|---:|---|---|
| Default | 0.852731 | 0.530437 | Pass | Pass |
| Default panel, relax 4 | 0.855784 | 0.530816 | Pass | Fail |
| Panel 8 | 0.855807 | 0.531165 | Pass | Fail |
| Panel 8, relax 4 | 0.845224 | 0.522221 | Pass | Fail |
| Panel 16 | 0.860740 | 0.528449 | Pass | Fail |
| Panel 16, relax 4 | 0.844503 | 0.527698 | Pass | Fail |

Correct closing for this animation: **“No admissible improvement. Keep the starting candidate for this sweep.”** The last trial was numerically faster on both observed stopwatch values than the default, but failed additional checks. It is therefore incorrect to say the default was literally the fastest measured configuration.

## What validation added

- Fixed full large workload: 101 frequencies, 193 design variables, float64/complex128, all physical outputs and gradients. aLIGO has its own workload and 29 gradient parameters; do not label it 193.
- Complete first run includes imports, build/setup, tracing/lowering/compilation, simulation, sensitivity, gradients and transfers. Warm runtime is a separate quantity.
- Official sensitivity tolerances: large `abs(log(S)-log(S_ref)) <= 1e-5`; aLIGO uses its published `1e-6` bound. Positive sensitivity, finite outputs/gradients, nonzero gradient, official gradient sanity checks.
- Additional saved-array comparisons and 14 setup/parameter/mode cases; source integrity; same-input checks; explicit review of generic matrix structure and adjoints; targeted regression tests for builder/indexing defects; selected finite-difference and precision diagnostics.
- Counterexample: approximate cotangent collinearity can discard a tiny component that an ill-conditioned inverse amplifies. Explicit adjoint solves repaired that experimental branch. This does not imply the teammate implementation used the same shortcut.
- Both public PASS and seed agreement can coexist with unresolved pristine-reference disagreements. The original dense result is not automatically a precision oracle; high-precision follow-up must be described with its actual coverage.
- `jit` and first-order reverse gradients are the tested host interface. No claim of full GPU/JVP/Hessian/higher-order parity. Unsupported-component fallback is not proof of universal JAX API compatibility.

## Do not overclaim the system

The implemented system records experiments and routes measured feedback. Use “coordinator + explicit search rules,” not “fully autonomous discovery of the global optimum.” Show agent sessions containing candidate commits; evaluation jobs are separate records. Candidate ancestry is a DAG. Feedback goes back to the coordinator as a visibly separate dashed loop.

Use “repeat-confirmed” only for actual repeats in the same comparison regime. Pareto plots help inspect phase/memory tradeoffs; complete first-run time is still the scoring objective. Do not invent a single weighted average of the large and aLIGO scores.

Branch closure means no admissible improvement within that budget or a recorded correctness issue. It does not mean a mathematically exhausted search space or that the experiment produced no knowledge. Combining two branches creates a new candidate requiring new validation; do not merge timings by addition.

The final future-application slide must say **“next application”**: optimizing mirror/laser arrangements is a proposed use of the system, not an accomplished result in this hack. In this challenge, the physical design variables were preserved, not tuned to make the benchmark easier.

## Check the existing closing slide

The supplied deck’s 0.66 s headline needs its exact final-revision report. Our controlled peer check was about 0.70 s under a different checkout/repetition policy; do not quietly replace one with the other or call the variation a code gain.

“30,000 evaluations/hour versus 230” corresponds approximately to **warm** 0.12 s versus 15.46 s. At 0.66 s complete first-run time the arithmetic ceiling is about **5,455/hour**, before orchestration overhead. Do not combine the warm-throughput figure and the cold-run speedup without labelling both.

“Same answers” should mean agreement within stated numerical tolerances on the validated setups, not bit-identical outputs everywhere. Avoid “all constraints passed on every topology.” The judges’ setup has not been observed.
