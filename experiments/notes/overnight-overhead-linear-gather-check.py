"""Supervisor-only small JAX gather/VJP comparisons; no benchmarks or fixtures.

Compares actual SparseSystem.base_values with the reviewed two-coordinate gather.
Run in the fixed environment; not executed locally (NumPy/JAX unavailable).
"""
from functools import partial

import differometor
import jax
import jax.numpy as jnp
import numpy as np
from differometor.sparse import SparseSystem

jax.config.update('jax_enable_x64', True)
jax.config.update('jax_enable_compilation_cache', False)


def previous(system, matrix):
    return jax.lax.gather(
        matrix, system.base_coordinates,
        jax.lax.GatherDimensionNumbers(offset_dims=(), collapsed_slice_dims=(0, 1),
                                      start_index_map=(0, 1)),
        slice_sizes=(1, 1), unique_indices=True, mode='promise_in_bounds')


def values_and_vjp(function, matrix):
    result, pullback = jax.vjp(function, matrix)
    cotangent = jnp.arange(result.size, dtype=jnp.float64) + 1
    cotangent = cotangent.astype(result.dtype)
    if jnp.iscomplexobj(result):
        cotangent = cotangent * (1 + 2j)
    return result, pullback(cotangent)[0]


def compare(a, b):
    for x, y in zip(a, b):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape and x.dtype == y.dtype
        np.testing.assert_array_equal(x, y)


rng = np.random.default_rng(741829)
count = 0
for size in (1, 2, 5):
    for augmented in (False, True):
        width = size + int(augmented)
        base = rng.normal(size=(size, width)) + 1j * rng.normal(size=(size, width))
        base[rng.random(base.shape) < .7] = 0
        base[0, 0] = 0  # Structural write must retain derivative at a current zero.
        # Duplicate and negative destinations are normalized by the existing plan.
        system = SparseSystem(base, [0, 0, -1], [0, 0, -1], [0], [-1])
        for dtype in (np.float64, np.complex128):
            for extra_width in (0, 2):
                values = np.zeros((size, width + extra_width), dtype=dtype, order='F')
                values[:, :width] = np.real(base) if dtype == np.float64 else base
                values = jnp.asarray(values)
                new = system.base_values
                old = partial(previous, system)
                expected = jax.jit(partial(values_and_vjp, old))(values)
                actual = jax.jit(partial(values_and_vjp, new))(values)
                compare(expected, actual)
                assert np.asarray(actual[1])[0, 0] != 0
                count += 1
                if size == 2 and augmented and extra_width == 0:
                    batched = jnp.stack((values, values + 1))
                    compare(jax.jit(jax.vmap(partial(values_and_vjp, old)))(batched),
                            jax.jit(jax.vmap(partial(values_and_vjp, new)))(batched))
                    count += 1

# Empty selected pattern, with a nonempty matrix operand.
for dtype in (np.float64, np.complex128):
    system = SparseSystem(np.zeros((3, 4)), [], [])
    for width in (4, 6):
        matrix = jnp.asarray(np.zeros((3, width), dtype=dtype))
        compare(jax.jit(partial(values_and_vjp, partial(previous, system)))(matrix),
                jax.jit(partial(values_and_vjp, system.base_values))(matrix))
        count += 1
print(f'passed {count} exact gather/VJP comparisons, including two batched cases')
