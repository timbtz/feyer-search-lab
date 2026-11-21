# JAX transformation compatibility

`benchmark.py` exercises only `jax.jit` and first-order reverse mode (`jax.vjp`). Neither the written [judging criteria](../judging-criteria.pdf) nor the challenge talk requires other transformations or forbids NumPy or SciPy. In the talk, the organizers said that rewriting the system underneath is fine and that pre-computation and pre-compilation are allowed. They judge total runtime on "a random setup with random parameters" with Differometor's accuracy. Their "JAX looks like NumPy but is functional" remark was about the effort of speeding up JAX code, not a ban on NumPy. Differentiability is central to their use, though: the upstream workloads are `jax.jit(jax.value_and_grad(...))` optimizer loops with optax and GPU execution (`README.upstream.md`).

Full transformation support is therefore **preferred, not a stated requirement**. Keep it when it is cheap. When it costs real speed, keep both variants and decide explicitly. [Organizer question 12](organizer-questions.md) asks this directly.

## What breaks, and why

| Mechanism | Reverse mode (`grad`, `vjp`) | Forward mode (`jvp`, `jacfwd`) | Second order | `vmap` | GPU |
| --- | --- | --- | --- | --- | --- |
| Pure JAX (`jnp.linalg.solve`) | yes | yes | yes | yes | on device |
| `jax.custom_vjp` around a `pure_callback` | yes | **no**: "can't apply forward-mode autodiff (jvp) to a custom_vjp function" | **no** | with `vmap_method` | host round trip |
| `lax.custom_linear_solve` with callback `solve` / `transpose_solve` | yes | yes | yes | with `vmap_method` | host round trip |
| `jax.custom_jvp` with callback primal and a JAX-linear tangent from host Jacobian blocks | yes (JAX transposes the tangent) | yes | **no**: explicit error, since the callback has no JVP | with `vmap_method` | host round trip |

The JAX documentation states the `custom_vjp` and `custom_jvp` rules ([custom derivative rules](https://docs.jax.dev/en/latest/notebooks/Custom_derivative_rules_for_Python_code.html), [`pure_callback`](https://docs.jax.dev/en/latest/_autosummary/jax.pure_callback.html), [`custom_linear_solve`](https://docs.jax.dev/en/latest/_autosummary/jax.lax.custom_linear_solve.html)). The `custom_linear_solve` row was verified on AMD with [`lab/custom_linear_solve_probe.py`](../lab/custom_linear_solve_probe.py). A SuperLU `pure_callback` as `solve`/`transpose_solve` and a JAX sparse `matvec` match dense `jnp.linalg.solve` to ~1e-16 for value, grad, jvp, jacfwd, Hessian, reverse-over-reverse HVP, `vmap(grad)` and `jit(grad)`. Derivatives with respect to the matrix values flow through the differentiable JAX `matvec`. The callback only applies the linear solve to tangents and cotangents.

A host callback always runs on CPU. On a GPU run the sparse line pays device-to-host transfers, while the dense path stays on device. This cannot be measured here: the evaluator environment has no JAX GPU build. It does not affect the CPU-only judged benchmark.

## Suite

`lab/jaxcompat.py` runs 11 transformations on one setup with the candidate's `differometor`. It then compares the values with the unchanged simulator:

| Test | Downstream use |
| --- | --- |
| `value_and_grad_jit` | upstream optimizer examples |
| `descent_3_steps` | repeated evaluations with changing parameters (catches stale caches) |
| `vmap_value_and_grad` | population or batched parameter sets |
| `jvp`, `jacfwd_2` | forward-mode sensitivities |
| `hvp_fwd_over_rev`, `hvp_rev_over_rev` | Newton / curvature methods |
| `eager_value_and_grad` | interactive use without `jit` |
| `public_run` | `df.run` as in the upstream examples |
| `checkpoint_grad` | rematerialization wrappers |
| `second_setup_same_process` | building another setup in the same process, then re-evaluating the first |

```bash
PY=/workspace/venv-feyer/bin/python
OMP_NUM_THREADS=1 taskset -c 101 $PY -u lab/jaxcompat.py run --tree /workspace/feyer-pristine --setup voyager --out compat-pristine.json
OMP_NUM_THREADS=1 taskset -c 101 $PY -u lab/jaxcompat.py run --tree /path/to/candidate --setup voyager --out compat-candidate.json
$PY lab/jaxcompat.py compare compat-pristine.json compat-candidate.json   # default tolerance 1e-6
```

Use `--only test_a,test_b` to rerun selected tests and merge them into an existing output file.

Record a candidate for the dashboard's **Robustness** tab with `jaxcompat.py report compat-pristine.json compat-candidate.json --sha FULL_SHA --label '...' --branch ... --cpu N --output report.json`. Copy the file to `.lab/jaxcompat/report.json`. All runs execute on the AMD instance with `/workspace/venv-feyer`, never on a laptop.

## Results, 21 November 2026

Voyager, 40 frequencies, AMD EPYC 9334, CPU 101. Raw results: [`experiments/jax-compatibility/`](../experiments/jax-compatibility/).

| Candidate | Passing | Failing | Max rel. difference where both run |
| --- | ---: | --- | --- |
| `aac9904` dense row-split pruning (team best, 17.85 s) | **11/11** | none | 2.0e-14 |
| `ac49ee4` sparse SuperLU `custom_vjp` (7.738 s) | 7/11 | `jvp`, `jacfwd_2`, `hvp_fwd_over_rev`, `hvp_rev_over_rev` | 1.4e-8 (3-step descent); 4.0e-10 otherwise |

The sparse line keeps reverse mode, `vmap`, eager execution, the public API, checkpointing and multi-setup use. It loses all forward-mode and second-order differentiation. The workers' current guidance:

- The sparse solver should move to `lax.custom_linear_solve`. This is expected to be nearly free, but measure it.
- Host-side component evaluation should prefer a `custom_jvp` with a JAX-linear tangent.
- If full semantics cost substantial speed, keep the faster `custom_vjp` variant as its own candidate and report both.

Every candidate reports this suite alongside the cross-setup [generalization check](generalization.md).
