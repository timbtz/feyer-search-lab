"""Candidate35 identity-gather primal and VJP check for the supervisor environment.

Tiny synthetic arrays only. No timing, optical fixtures or benchmark execution.
"""
import ast
from pathlib import Path
import jax
import jax.numpy as jnp
from jax import lax
import numpy as np

jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)
source = Path(__file__).resolve().parents[2] / "differometor/simulate.py"
node = next(n for n in ast.parse(source.read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == "_static_take")
scope = dict(np=np, jnp=jnp, lax=lax)
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
candidate = scope["_static_take"]


def reference(values, indices):
    return lax.gather(
        values, np.asarray(indices, dtype=np.int64)[:, None],
        lax.GatherDimensionNumbers(offset_dims=(), collapsed_slice_dims=(0,), start_index_map=(0,)),
        slice_sizes=(1,), mode=lax.GatherScatterMode.PROMISE_IN_BOUNDS,
    )


rng = np.random.default_rng(3535)
checked = 0
for size in (1, 4, 9):
    cases = [[], [0], [size - 1], list(range(size)), list(range(1, size)),
             list(range(size - 1, -1, -1)), [0, 0], [size - 1, 0, size - 1],
             rng.integers(size, size=7).tolist()]
    for indices in cases:
        indices = np.asarray(indices, dtype=np.int64)
        for complex_values in (False, True):
            values = rng.normal(size=size)
            bars = rng.normal(size=indices.size)
            if complex_values:
                values = values + 1j * rng.normal(size=size)
                bars = bars + 1j * rng.normal(size=indices.size)
            values[0] = 0
            if size > 1:
                values[1] = -0.0
            values, bars = jnp.asarray(values), jnp.asarray(bars)

            def evaluate(function):
                def run(x, cotangent):
                    output, pullback = jax.vjp(lambda v: function(v, indices), x)
                    return output, pullback(cotangent)[0]
                return jax.jit(run)(values, bars)

            got, want = evaluate(candidate), evaluate(reference)
            for a, b in zip(got, want):
                np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
            # Selection itself must also preserve the sign bit of stored zeros.
            for part in (np.real, np.imag):
                np.testing.assert_array_equal(np.signbit(part(np.asarray(got[0]))),
                                              np.signbit(part(np.asarray(want[0]))))
            checked += 1
print(f"PASS: {checked} primal/VJP cases, including duplicate-index accumulation; no timing claim")

# Structural trace inspection, not a compilation timing or optical benchmark.
traces = 0
for size in (1, 4, 9):
    indices = np.arange(size, dtype=np.int64)
    for dtype in (jnp.float64, jnp.complex128):
        values = jnp.zeros(size, dtype=dtype)
        bars = jnp.ones(size, dtype=dtype)
        def transpose(function):
            return lambda x, g: jax.vjp(lambda v: function(v, indices), x)[1](g)[0]
        forward_got = jax.make_jaxpr(lambda x: candidate(x, indices))(values)
        forward_want = jax.make_jaxpr(lambda x: reference(x, indices))(values)
        reverse_got = jax.make_jaxpr(transpose(candidate))(values, bars)
        reverse_want = jax.make_jaxpr(transpose(reference))(values, bars)
        names = lambda graph: [eqn.primitive.name for eqn in graph.jaxpr.eqns]
        assert 'gather' not in names(forward_got), names(forward_got)
        assert 'gather' in names(forward_want), names(forward_want)
        assert 'scatter-add' not in names(reverse_got), names(reverse_got)
        assert 'scatter-add' in names(reverse_want), names(reverse_want)
        traces += 1
print(f"PASS: {traces} identity forward/transpose trace checks; no timing claim")

# Eager NumPy callers must still receive JAX arrays, as with lax.gather.
eager = 0
for size in (1, 4, 9):
    for dtype in (np.float64, np.complex128):
        values = np.arange(size, dtype=np.float64).astype(dtype)
        indices = np.arange(size, dtype=np.int64)
        got, want = candidate(values, indices), reference(values, indices)
        assert isinstance(got, jax.Array)
        assert got.dtype == want.dtype
        np.testing.assert_array_equal(np.asarray(got), np.asarray(want))
        eager += 1
print(f"PASS: {eager} eager NumPy input compatibility cases")
