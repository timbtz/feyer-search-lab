"""Focused check for candidate 3 (static parameter layout). Run in the fixed environment:

    PYTHONPATH=<repo> /workspace/venv-feyer/bin/python experiments/notes/overnight-overhead-layout-check.py

Compares STATIC_PARAMETER_LAYOUT True vs False (generic traced indexing) on aLIGO
setups in three modulation modes at the default and at perturbed parameters:
forward outputs and full VJP gradients must be bitwise equal. Also prints jaxpr
equation counts for the forward vjp to inspect the mechanism. Not a benchmark.
"""

import numpy as np
import jax
import jax.numpy as jnp

import differometor as df
from differometor import simulate as sim
from differometor.setups import aligo

jax.config.update("jax_enable_x64", True)


def loss_and_grad(arrays, parameters):
    def loss(p):
        carrier, signal, noise = sim.simulate(**dict(arrays, optimized_parameters=p))
        return (jnp.sum(jnp.abs(signal) ** 2) + jnp.sum(noise) + jnp.sum(jnp.abs(carrier))).real, (carrier, signal, noise)

    (value, outputs), grad = jax.jit(jax.value_and_grad(loss, has_aux=True))(parameters)
    return value, outputs, grad


def count_eqns(arrays, parameters):
    closed = jax.make_jaxpr(lambda p: jax.vjp(lambda q: sim.simulate(**dict(arrays, optimized_parameters=q)), p)[0])(
        parameters
    )
    return len(closed.jaxpr.eqns)


failures = 0
frequencies = jnp.asarray(np.logspace(1, 3.5, 23))
for mode in ("space_modulation", "amplitude_modulation", "frequency_modulation"):
    setup, pairs = aligo(mode)
    arrays, *_ = df.run_build_step(setup, [("f", "frequency")], frequencies, pairs)
    plan = arrays.get("host_plan")
    layout = getattr(plan, "parameter_layout", None)
    print(mode, "host_plan:", plan is not None, "layout:", layout is not None)
    base = np.asarray(arrays["parameters"])[0][np.asarray(arrays["optimized_parameter_indices"])]
    base = np.real(base).astype(np.float64)
    rng = np.random.default_rng(0)
    for label, params in (("default", base), ("perturbed", base * (1 + 1e-3 * rng.standard_normal(base.shape)))):
        params = jnp.asarray(params)
        results = {}
        for flag in (False, True):
            sim.STATIC_PARAMETER_LAYOUT = flag
            results[flag] = loss_and_grad(arrays, params)
        (v0, o0, g0), (v1, o1, g1) = results[False], results[True]
        same = bool(np.array_equal(np.asarray(v0), np.asarray(v1))) and all(
            np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(o0, o1)
        ) and bool(np.array_equal(np.asarray(g0), np.asarray(g1)))
        if not same:
            failures += 1
            print("  MISMATCH", label, "max |dgrad|", float(np.max(np.abs(np.asarray(g0) - np.asarray(g1)))))
        else:
            print("  bitwise equal:", label)
    for flag in (False, True):
        sim.STATIC_PARAMETER_LAYOUT = flag
        print("  forward-vjp jaxpr eqns, static layout =", flag, ":", count_eqns(arrays, jnp.asarray(base)))
sim.STATIC_PARAMETER_LAYOUT = True
print("FAILURES:", failures)
raise SystemExit(1 if failures else 0)
