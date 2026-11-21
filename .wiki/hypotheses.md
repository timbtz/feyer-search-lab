# Optimization hypotheses

These ideas are starting points for experiments. Their expected benefits have not been established. Inspect the current implementation, preserve the challenge invariants, and measure each change against the fixed baseline.

## First experiments

### Import plotting only when requested

`differometor/__init__.py` imports `visualize_setup` from `plot.py`, which imports Plotly. Test whether deferring the plotting import until visualization is requested reduces the measured import phase. Preserve the public `visualize_setup` behavior and signature as far as practical.

This change should leave the numerical implementation untouched, but it still needs the screening and full benchmark checks. Measure the import phase and complete first-run time separately. Do not claim a gain from the import graph alone.

### Inspect repeated noise solves

Inspect the shapes, batching axes, and lowered computation around the noise solve. Determine whether multiple right-hand sides share a coefficient matrix and whether JAX already reuses a factorization. The nested `vmap` structure alone does not prove repeated factorization.

If duplication is established, test a matrix of right-hand sides or explicit factorization reuse. Preserve complex128 arithmetic and all outputs and derivatives. Record runtime, compilation time, peak RAM and full-array differences. A faster solve can still produce unacceptable sensitivity or gradient errors on a poorly conditioned system.

Keep the import change and solve change in separate commits and evaluate them separately before testing their combination.

## Later investigations

| Direction | Question to answer first | Evidence to collect |
| --- | --- | --- |
| Redundant copies and augmented matrices | Which slices, transposes, conjugations and intermediate arrays survive lowering? | Lowered representation, phase timings, peak memory and array comparison |
| Component grouping around `lax.switch` | Does batching cause avoidable computation for the actual component distribution? | Current JAX lowering, compile time, runtime and unchanged component results |
| Custom reverse derivative | Can the derivative reuse forward factors without increasing setup or compilation cost? | Derived convention for this complex-valued calculation, focused derivative tests and full-gradient comparison |
| SciPy solves through callbacks | Are sufficiently sparse, stable systems available to offset callback and derivative overhead? | Actual nonzero counts, sparsity patterns, conversion cost, callbacks under JIT and differentiation, full first-run timing |

For a custom VJP, derive and test JAX's complex differentiation convention for the exact loss and solve. Do not assume that replacing a conjugate transpose with an ordinary transpose is correct in every formulation.

For sparse methods, measure the populated carrier and signal matrices at representative inputs before choosing a sparse solver. Include matrix construction, conversion, factorization, callback, compilation and derivative costs in the decision. A sparse forward solve without a correct efficient gradient is not a complete candidate.

## Constraints and open questions

Persistent compilation caching is disabled by the benchmark and is outside the experiment scope. The official staged JIT structure remains unchanged. Ask the organizers about uncertain rule interpretations before relying on package-level XLA flags or other changes to the evaluation environment.

The user's suggested phase times and expected wins were estimates from code inspection and another timing breakdown. Use the measured AMD baseline in [Machine and baseline](baseline.md) and each run's detailed report for this machine.
