# Future operator: bounded scalar component scan unrolling

Recommend `component_scan_unroll ∈ {1, 2, 4}` for a coordinator-frozen **future** round, after reviewing round-001 results. Anchor the experiment to seed8 with `checkpoint=true`, `prevent_cse=false`, `map_batch_size=null`. This is a source-derived hypothesis, not an evaluated candidate. The current fifteen configurations remain frozen; neither an additional round nor additional budget is authorized by this note.

Task `076fb719980748409ecf0c5ab4d1d53b`; actor `hetzner-codex-1`; assigned branch `explore/hetzner/guidance-001`; campaign `dag-pilot-v1`. Parent SHA: `1e552d675c3795265be8af1ac23ffb61f90f30b1`. The inspected `differometor/simulate.py` SHA-256 is `8225fedb4580e39fcc3f3611e73e4e356c7c0b55e4a3353486fcad9260d77c01`, matching the supplied seed content digest. Context digest: `83ad5453fe05d5804bde25d432a241d9f3e651b04c8ab90986ebe0e58b82670c`; round digest: `340b0328994b565ff10f277a62029154eed8346995b6ccec5a616e87bf465efe`. The context and brief files are absent locally; their immutable prompt contents supplied the campaign evidence. No Git inspection was performed.

The frozen context confirms three full seed runs, with these aggregate metrics:

| Metric | Supplied value | Supplied range |
| --- | ---: | ---: |
| Compilation | 12.777620 s | 0.414144 s |
| Execution (`runtime`) | 14.283548 s | 0.044317 s |
| Complete first-run total | 28.093522 s | 0.534216 s |
| Peak RSS | 13,758,509,056 bytes | 12,640,256 bytes |

Evidence run IDs: `e6e5badb945c47ae927e511a3ff15fd7`, `415bab6b82ef42baa0e0a5277df7aeb9`, `882be0c143db470c9686cd2ba9e44c77`. The snapshot reports zero new campaign evaluations. Its runtime aggregate is not a separately reported warm median; individual import time, warm timings and total job duration are not supplied. The 0.534216 s total range is about 1.9% of the aggregate total, exceeding the round's 1% relative progress margin (about 0.281 s). A range is not a confidence interval, but it warrants repeated full runs for small apparent improvements. Existing round evidence should be assessed before spending future evaluations on this operator.

Source evidence supports a distinct mechanism from map batching:

- In [simulate.py](../../differometor/simulate.py), lines 62–67 dispatch a scalar selector through 19 branch-local checkpointed component functions; lines 116–124 gather inputs, map that helper, then gather/scatter outputs. The registry at [components.py](../../differometor/components.py), lines 1362–1382, contains 19 functions. `update` has no dependence between component evaluations before its final scatter.
- Carrier, signal and noise call `vmap(update, in_axes=(0, None, None, None, None, None))` at simulator lines 303, 317 and 392. Thus selectors remain shared across frequency samples. [JAX's map documentation](https://docs.jax.dev/en/latest/_autosummary/jax.lax.map.html) says specifying `batch_size` uses `vmap`; [switch documentation](https://docs.jax.dev/en/latest/_autosummary/jax.lax.switch.html) explains the selection transformation when predicates are batched. Consequently, registered batching choices can change dispatch behavior, not merely loop overhead. Actual AMD optimized lowering has not been inspected here.
- [JAX's scan API](https://docs.jax.dev/en/latest/_autosummary/jax.lax.scan.html) exposes an integer `unroll` controlling iterations within each rolled loop iteration. An empty-carry scan can express the same ordered component map while keeping each selector scalar. Small unroll factors may reduce loop bookkeeping or expose scheduling opportunities without introducing component-selector vectorization. This is an inference, not proof of less executed work.

The future materializer would replace **only** the `output_matrix = lax.map(...)` expression in `update` with this sketch; `U` is a static integer literal chosen from the finite domain:

```python
_, output_matrix = lax.scan(
    lambda carry, item: (carry, _evaluate_component(item)),
    (),
    (function_indices, function_inputs),
    unroll=U,
)
```

Keep the helper/JIT/checkpoints, frequency batching, output order, final scatter and all physical arithmetic unchanged. Let scan handle the exact input length, including remainders; do not pad with extra physical evaluations or truncate components. `U=1` is a representation control against unchanged seed8; it is not assumed to produce identical compiled code. Use the same U for all three matrix updates, with no other tuning axis in this experiment. This preserves the simulator signature and the benchmark's separate forward-with-pullback, sensitivity-with-pullback and backward compilations ([benchmark.py](../../benchmark.py), lines 112–133 and 211–216).

Compatibility is at the public-API level: `requirements.txt` pins JAX/JAXLIB 0.9.0, while the linked live documentation is not version-pinned. `/workspace/venv-feyer` is unavailable in this worktree. The coordinator must confirm the sketch's trace/lowering in that fixed environment; no dependency upgrade, private scan transpose option or custom derivative is proposed. The fixed-shape component outputs and statically known input length fit scan's documented requirements.

The expected tradeoff is fewer loop iterations versus larger compiled bodies and potentially different AD residual lifetimes. Forward and backward execution could improve, but lowering/compilation and RSS could increase; retaining branch-local checkpoints does not guarantee unchanged memory. Dense solves are untouched, and no profile establishes how much runtime belongs to component dispatch. The benchmark's forward stage also constructs AD residuals, so a primal-only microbenchmark would not settle this hypothesis. Historical candidate 7 already illustrates opposing forward/backward compilation changes ([initial-agent.md](initial-agent.md), candidate 7 full run `da015d91ac4c448b9b487d196ee057e0`); that older measurement is not a same-cohort comparison to seed8.

Before accepting any future exact committed revision, the coordinator should:

1. Check ordered outputs and VJPs for U=1 and unrolled variants, including singleton/dummy updates and component counts not divisible by U. Inspect forward/backward lowering for scalar dispatch, remainder handling, code growth and residual changes. These diagnostics supplement full validation.
2. Run the unchanged official full workload on AMD, serially on CPU 2 in the fixed environment: all 101 frequencies, 193 physical variables, complete optical setup, float64/complex128 and all three JIT stages. Require the official sensitivity and finite-difference gradient checks; sensitivities must be positive with absolute log-reference error at most `1e-5`, and outputs/gradients finite with a nonzero full gradient.
3. Inspect saved carrier, signal, noise, sensitivity, powers, loss and all gradient coordinates against the frozen reference using the existing comparator. Retain maximum absolute and relative errors with near-zero handling and exact parameter/frequency equality. Scheduling can alter floating-point gradient accumulation; unchanged equations do not establish numerical equivalence.
4. Compare fresh-process full repetitions against the unchanged parent in the same cohort, recording imports/setup, each lowering/compilation stage, first execution, warm runtime, complete first-run total, job duration and peak RSS (32,000,000,000-byte budget). Screens remain provisional. Reject a runtime improvement outweighed by compilation in the primary total objective; retain any separately useful Pareto tradeoff without calling it a total-time win. Combinations with a round-001 winner require fresh validation, not additive speedup estimates.

Handoff: only this research note was written. No simulator candidate, new evaluation/run ID or measured speedup exists. No benchmarks, installs, Git/SSH/GitHub calls or agents were used. Static inspection used Python 3 after the `python` alias was unavailable. Deadline: `2026-11-21T17:32:51.977746Z`; this single proposer turn ends without extending it. Supervisor owns publication; coordinator decides whether to register the operator after the current round. `ready_for_evaluation=false`; `stop=true`; structured before/after parameter objects are both `{}` because this guidance makes no registered assignment.
