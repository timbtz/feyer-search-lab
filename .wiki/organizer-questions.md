# Questions for the Feyer organizers

These questions are drafted from the written brief, the [judging criteria](../judging-criteria.pdf), upstream commit [`2bb437a`](https://github.com/feyerlabs/start-hack-munich-2026/commit/2bb437a223) and the challenge talk. Ask them in Discord `#feyer` or room 0602. Record each answer with its date and source. A ★ marks a question whose answer changes what we optimize.

## What we already know

- Score: complete first-run total of the benchmark, on the same CPU for everyone (Intel Xeon Platinum 8468, 1 logical CPU, 32 GB). Validation is excluded.
- Final setup: "a slight variation of the supplied example" (README). In the talk: "a random setup with random parameters."
- Correct: results match Differometor's accuracy. The written checks are |Δ log S| ≤ 1e-5 at every frequency, finite outputs, a nonzero gradient and the gradient sanity check.
- Allowed (talk): rewriting internals, bringing prior work, pre-computation and pre-compilation, "as long as a random setup with random parameters is simulated faster." Development on AMD GPUs is fine. Evaluation is "for now" CPU.

## Questions (ready to paste)

**Final setup**

1. ★ How is the final "random setup with random parameters" generated? Is it `setups.uifo(size=3, random=True, random_seed=…)` with parameters drawn uniformly from `property_bounds` in `examples/uifo_optimization.py`, or a hand-modified variant of `uifo_800_3000.json`?
2. ★ Can it include component types or modes the example lacks? Examples: amplitude or frequency modulation mode, isolators, another grid size, more detectors or balanced homodyne readout.
3. Do the frequency grid (101 points, 800–3000 Hz) and the optimized properties (`reflectivity, tuning, db, angle, power, mass, length` with `constrain_inter_grid_cell_spaces`) stay the same?

**How it is run**

4. ★ Is the final run our unchanged `benchmark.py`, with only the fixture and reference files swapped? It hard-codes the fixture hashes and the `mb11.tuning` gradient spot check.
5. Is the score one fresh-process first run, or a median over several runs? Is the OS file cache warm or cold?
6. Which environment exactly: the pinned `requirements.txt` (jax 0.9.0) plus `pip install -e .` from our repository? May we add a dependency or a compiled extension built at install time?

**Correctness**

7. ★ Is the final setup's reference computed with the original dense Differometor? Is the criterion still |Δ log S| ≤ 1e-5 at every frequency?
8. Are all gradient components compared with reference gradients, and with what tolerance? Or only the finite-difference spot check?
9. ★ On some random setups the original dense solve is itself inaccurate. Against an extended-precision solution we measured detected-signal errors up to about 3e-4, larger than the 1e-5 bound. If a submission is closer to the exact solution but differs from the reference there, how is it judged?
10. Does "double precision" require every internal operation to be float64/complex128? Or is a lower-precision step acceptable if outputs reach double-precision accuracy, for example through iterative refinement?

**Pre-compilation and interface**

11. ★ The talk allowed pre-computation and pre-compilation. Does that include JAX's persistent compilation cache (`benchmark.py` disables it explicitly), AOT-compiled native code in the repository, or kernels compiled at install time?
12. ★ Must `differometor.simulate` remain a fully transformable JAX function: jit, vjp, jvp/forward mode, vmap and Hessians? Or is the benchmark's jit plus reverse-mode pipeline enough? Host-side code inside JAX callbacks keeps reverse mode but can drop forward mode.

**Hardware and submission**

13. Is the final evaluation CPU-only on the Xeon 8468, or will the AMD GPUs mentioned in the talk be used?
14. Is the 32 GB memory limit enforced, and is it GB or GiB?
15. What is the submission deadline and format: repository, branch or commit, required reports and plots? May the repository contain extra tooling outside `differometor/`?

## What each answer changes

| Question | Decision it unblocks |
| --- | --- |
| 1, 2, 3 | How much setup structure we may specialize; which component functions need fast paths; which cross-setup cases [the generalization check](generalization.md) must cover |
| 4, 5 | Whether a hard-coded-fixture benchmark is the scored harness; how much import/build overhead matters |
| 6, 11 | Whether native or precompiled kernels and an install-time build step are legitimate levers on the ~6 s compile |
| 7, 8, 9, 10 | Whether the sparse SuperLU line (more accurate than the dense reference on badly conditioned setups) is safe, or must reproduce dense rounding |
| 12 | Whether `custom_vjp` host callbacks are acceptable or [full transformation support](jax-compatibility.md) is required |
| 13, 14 | Hardware targeting and the memory budget |

Supersedes open questions 1 and 3 in the [system audit](system-audit.md).

## Answers

None recorded yet.
