"""Small synthetic validation for the static base-value gather (no benchmark).

Run in the evaluator environment with the candidate repository on PYTHONPATH.
Checks the old indexing expression against SparseSystem.base_values, including
matrix tangents: structural zeros must retain their derivative contributions.
"""

import json

import jax
import jax.numpy as jnp
import numpy as np

from differometor.sparse import SparseSystem

jax.config.update("jax_enable_x64", True)
rng = np.random.default_rng(748)


def check(size, augmented, empty=False):
    shape = (size, size + int(augmented))
    base = np.zeros(shape, dtype=np.complex128)
    if empty:
        system = SparseSystem(base, [], [])
    else:
        base[0, 0] = 2 + 3j
        # Repeated writes and negative input coordinates become unique,
        # normalized pattern entries, including entries that start at zero.
        system = SparseSystem(base, [0, -1, -1], [-1, 0, 0], [size - 1], [-1])
    old = lambda x: x[system.all_rows, system.all_cols]
    new = system.base_values
    for values in (base, rng.normal(size=shape) + 1j * rng.normal(size=shape)):
        x = jnp.asarray(values)
        tangent = jnp.asarray(rng.normal(size=shape) + 1j * rng.normal(size=shape))
        np.testing.assert_array_equal(new(x), old(x))
        np.testing.assert_array_equal(jax.jit(new)(x), jax.jit(old)(x))
        for left, right in zip(jax.jvp(new, (x,), (tangent,)), jax.jvp(old, (x,), (tangent,))):
            np.testing.assert_array_equal(left, right)
        new_y, new_pull = jax.vjp(new, x)
        _, old_pull = jax.vjp(old, x)
        cotangent = jnp.asarray(rng.normal(size=new_y.shape) + 1j * rng.normal(size=new_y.shape))
        np.testing.assert_array_equal(new_pull(cotangent)[0], old_pull(cotangent)[0])
        np.testing.assert_array_equal(
            jax.jit(jax.vmap(new))(jnp.stack((x, tangent))),
            jax.jit(jax.vmap(old))(jnp.stack((x, tangent))),
        )
    counts = {}
    for name, fn in (("old", old), ("new", new)):
        equations = jax.make_jaxpr(fn)(jnp.asarray(base)).jaxpr.eqns
        counts[name] = [equation.primitive.name for equation in equations]
    print(json.dumps({"shape": shape, "empty": empty, "primitives": counts, "passed": True}))


for size, augmented in ((1, False), (1, True), (3, False), (4, True), (7, True)):
    check(size, augmented)
check(3, False, empty=True)
