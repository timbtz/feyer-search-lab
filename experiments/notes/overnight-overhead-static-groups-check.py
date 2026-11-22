"""Supervisor synthetic checks for static integer metadata; no fixtures or timings.

Run with this checkout on PYTHONPATH in the fixed evaluator environment.
Checks public JAX tree/JIT behavior, fresh-build invalidation, metadata round trips,
and real component primal/VJP equivalence with ordinary dynamic dictionaries.
"""
import importlib

import jax
import jax.numpy as jnp
import numpy as np

from differometor.build import _group_component_indices
from differometor.components import FUNCTIONS, space, space_lower
from differometor.host_pass import StaticComponentGroups, build_host_plan
from differometor.setups import Setup

jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)
sim = importlib.import_module("differometor.simulate")


def equal_tree(left, right):
    assert jax.tree.structure(left) == jax.tree.structure(right)
    for actual, expected in zip(jax.tree.leaves(left), jax.tree.leaves(right)):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))


comparisons = 0
for count in (0, 1, 4, 7):
    functions = [FUNCTIONS.index(space if row % 2 else space_lower) for row in range(count)]
    indices = np.arange(count * 3, dtype=np.int64).reshape(count, 3) % 5
    group = _group_component_indices(functions, indices)
    group["diff_slots"] = {index: {slot: () for slot in range(3)} for index in functions}
    groups = {"signal": group, "noise_row_reuse": ()}
    static = StaticComponentGroups(groups)
    assert not jax.tree.leaves(static)
    assert jax.tree.leaves(groups)
    equal_tree(static.to_dict(), groups)
    equal_tree(static.copy(), groups)
    assert static["signal"]["parameter_indices"].keys() == group["parameter_indices"].keys()
    outputs = jnp.asarray(np.stack((np.arange(count), np.arange(count) % 4)))
    indices, functions = jnp.asarray(indices), jnp.asarray(functions, dtype=jnp.int64)

    def evaluate(parameters, metadata, cotangent):
        if isinstance(metadata, StaticComponentGroups):
            metadata = metadata.to_dict()  # same fallback conversion as simulate
        value, pullback = jax.vjp(lambda p: sim._component_outputs(
            p, indices, outputs, functions, metadata["signal"]), parameters)
        return value, pullback(cotangent)

    checked = jax.jit(evaluate)
    for parameters in (jnp.array([0., -0., 1., 3., 7.]),
                       jnp.array([0j, 1 + .01j, 1.2, 3., 7.])):
        cotangent = jnp.full((count,), 1 + .2j, dtype=jnp.complex128)
        equal_tree(checked(parameters, static, cotangent), checked(parameters, groups, cotangent))
        comparisons += 1

# The snapshot cannot be changed by mutating its source or a returned dictionary.
source = {"group": {"index": jnp.array([0], dtype=jnp.int64)}}
first = StaticComponentGroups(source)
source["group"]["index"] = jnp.array([1], dtype=jnp.int64)
second = StaticComponentGroups(source)
assert first != second
copy = first.to_dict()
copy["group"]["index"] = jnp.array([2], dtype=jnp.int64)
traces = []


@jax.jit
def select(values, metadata):
    traces.append(None)
    return values[metadata["group"]["index"]]


values = jnp.array([2., 4., 9.])
np.testing.assert_array_equal(select(values, first), [2.])
np.testing.assert_array_equal(select(values, first), [2.])
assert len(traces) == 1
np.testing.assert_array_equal(select(values, second), [4.])
assert len(traces) == 2
for mutation in (lambda: setattr(first, "_groups", {}),
                 lambda: first["group"].__setitem__("index", jnp.array([2]))):
    try:
        mutation()
    except (TypeError, AttributeError):
        pass
    else:
        raise AssertionError("Static metadata mutation succeeded")
for invalid in (np.array([1]), jnp.array([1.]), jnp.array([1j]), [1]):
    try:
        StaticComponentGroups({"invalid": invalid})
    except TypeError:
        pass
    else:
        raise AssertionError("Mutable or physical-valued metadata accepted")

# Exercise actual builder integration on a small supplied optical graph, without
# executing a simulation. Re-deriving each plan must preserve its complete key.
setup = Setup()
setup.add("laser", "l", power=1., phase=0.)
setup.add("mirror", "m", transmissivity=.2, loss=.01, tuning=0.)
setup.space("l", "m", length=2.)
setup.add("frequency", "f")
arrays, *_ = sim.run_build_step(setup, [("f", "frequency")], jnp.array([13., 81., 307.]),
                               [("l", "power"), ("m", "tuning")])
metadata = arrays["component_groups"]
assert isinstance(metadata, StaticComponentGroups)
structure = sim._build_sparse_structure(arrays)
assert structure == arrays["sparse_structure"]
assert build_host_plan(arrays, structure, metadata) == arrays["host_plan"]
assert build_host_plan(arrays, structure, metadata.to_dict()) == arrays["host_plan"]

print(f"PASS: {comparisons} component JIT primal/VJP comparisons, four metadata round trips, "
      "zero-leaf registration, two-build invalidation, mutation guards and builder plan round trips")
