"""Synthetic differential check for homogeneous static link dispatch.

Supervisor: run with this checkout on PYTHONPATH in the fixed JAX environment.
No benchmark, timing, optical fixture, or full simulation is used. The temporary
registry below belongs only to this diagnostic process and is restored on exit.
"""

import importlib
import json

import jax
import jax.numpy as jnp
import numpy as np

from differometor.host_pass import ParameterLayout

sim = importlib.import_module("differometor.simulate")
jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)


@jax.custom_jvp
def custom_tangent(x):
    return x * x


@custom_tangent.defjvp
def custom_tangent_jvp(primals, tangents):
    (x,), (dx,) = primals, tangents
    return x * x, 3 * x * dx


@jax.custom_vjp
def custom_pullback(x):
    return 2 * x


def custom_pullback_fwd(x):
    return 2 * x, ()


def custom_pullback_bwd(residual, cotangent):
    return (7 * cotangent,)


custom_pullback.defvjp(custom_pullback_fwd, custom_pullback_bwd)


def make_arrays(ids, count):
    return dict(
        parameters=np.zeros((1, count), dtype=np.complex128),
        optimized_parameter_indices=np.arange(count),
        optimized_value_indices=np.arange(count),
        linked_indices=np.arange(len(ids)),
        indices_to_link=np.arange(len(ids)),
        qhd_parameter_indices=np.array([], dtype=np.int64),
        qhd_placing_indices=np.empty((0, 3), dtype=np.int64),
        linking_function_indices=np.asarray(ids, dtype=np.int64),
    )


def assert_same(left, right):
    left_leaves, tree = jax.tree_util.tree_flatten(left)
    right_leaves, other_tree = jax.tree_util.tree_flatten(right)
    assert tree == other_tree
    for left, right in zip(left_leaves, right_leaves):
        left, right = np.asarray(left), np.asarray(right)
        assert left.shape == right.shape and left.dtype == right.dtype
        np.testing.assert_array_equal(left, right)
        # Numerical equality alone does not distinguish signed zeros.
        if np.iscomplexobj(left):
            for a, b in ((left.real, right.real), (left.imag, right.imag)):
                np.testing.assert_array_equal(np.signbit(a), np.signbit(b))
        else:
            np.testing.assert_array_equal(np.signbit(left), np.signbit(right))


def check(ids, values, allow_jvp):
    arrays = make_arrays(ids, max(len(ids), 1))
    layout = ParameterLayout.from_arrays(arrays)
    assert layout is not None
    ids = jnp.asarray(ids, dtype=jnp.int64)
    generic = lambda x: jax.vmap(lambda i, v: jax.lax.switch(i, sim.LINKING_FUNCTIONS, v))(ids, x)
    direct = lambda x: sim._link_parameter_values(x, ids, layout)
    weights = jnp.asarray(np.arange(values.size) + 1, dtype=values.dtype)

    def reverse(function, x):
        result, pullback = jax.vjp(function, x)
        return result, pullback(weights)

    for transform in (lambda f: f, jax.jit):
        assert_same(transform(lambda x: reverse(generic, x))(values),
                    transform(lambda x: reverse(direct, x))(values))
        if allow_jvp:
            assert_same(transform(lambda x: jax.jvp(generic, (x,), (weights,)))(values),
                        transform(lambda x: jax.jvp(direct, (x,), (weights,)))(values))
    return {
        "size": values.size,
        "selected": layout.single_linking_function,
        "generic_top_level_eqns": len(jax.make_jaxpr(generic)(values).jaxpr.eqns),
        "candidate_top_level_eqns": len(jax.make_jaxpr(direct)(values).jaxpr.eqns),
    }


def main():
    results = []
    registry = sim.LINKING_FUNCTIONS
    saved = registry[:]
    try:
        basic = [lambda x: x, lambda x: -x,
                 lambda x: jnp.asarray(jnp.abs(x), dtype=x.dtype), custom_tangent]
        for with_custom_vjp in (False, True):
            registry[:] = basic + ([custom_pullback] if with_custom_vjp else [])
            for dtype in (np.float64, np.complex128):
                values = np.array([0.0, -0.0, 0.25, -0.5, 1.0], dtype=dtype)
                if dtype == np.complex128:
                    values[0], values[1] = complex(0.0, -0.0), complex(-0.0, 0.0)
                    values[2], values[3] = 0.25 + 0.5j, -0.5 - 0.25j
                values = jnp.asarray(values)
                # Homogeneous dispatch, mixed fallback, clamped-index fallback,
                # empty input, and an arbitrary nonidentity registry entry zero.
                for index in range(len(registry)):
                    results.append(check([index] * values.size, values, not with_custom_vjp))
                results.append(check([0, 1, 2, 3, 0], values, not with_custom_vjp))
                results.append(check([-1] * values.size, values, not with_custom_vjp))
                results.append(check([len(registry) + 2] * values.size, values, not with_custom_vjp))
                results.append(check([], values[:0], not with_custom_vjp))
            registry[0] = lambda x: x * 5
            results.append(check([0, 0], jnp.asarray([2.0, -1.0]), not with_custom_vjp))

        registry[:] = basic
        # Read all source values before writing linked destinations, including
        # when source/destination indices overlap or sources repeat.
        arrays = make_arrays([1, 1, 1], 4)
        arrays["linked_indices"] = np.array([1, 0, 1])
        arrays["indices_to_link"] = np.array([0, 1, 3])
        layout = ParameterLayout.from_arrays(arrays)
        ids = jnp.array(arrays["linking_function_indices"], copy=True)

        def apply(row, direct):
            inputs = sim._static_take(row, layout.linked_indices)
            outputs = (sim._link_parameter_values(inputs, ids, layout) if direct else
                       jax.vmap(lambda i, x: jax.lax.switch(i, registry, x))(ids, inputs))
            return sim._static_set(row, layout.indices_to_link, outputs)

        row = jnp.asarray([2.0, 3.0, 5.0, 7.0])
        assert_same(jax.jit(lambda x: apply(x, True))(row),
                    jax.jit(lambda x: apply(x, False))(row))
        assert_same(jax.jacrev(lambda x: apply(x, True))(row),
                    jax.jacrev(lambda x: apply(x, False))(row))

        # Metadata owns its function-ID copy and rebuilding changes the plan key.
        original_key = layout._key
        arrays["linking_function_indices"][:] = 2
        assert layout.single_linking_function == 1
        assert np.all(layout.linking_function_indices == 1)
        assert ParameterLayout.from_arrays(arrays)._key != original_key
        arrays["linking_function_indices"] = np.array([1.0, 1.0, 1.0])
        assert ParameterLayout.from_arrays(arrays) is None
        arrays["linking_function_indices"] = np.array([[1, 1, 1]])
        assert ParameterLayout.from_arrays(arrays) is None
        # Growth of the global registry must not change a previously built link.
        registry.extend([lambda x: x + 17] * 12)
        assert_same(apply(row, True), apply(row, False))
        print(json.dumps({"passed": True, "cases": results, "overlap_and_metadata": "passed"}, indent=2))
    finally:
        registry[:] = saved


if __name__ == "__main__":
    main()
