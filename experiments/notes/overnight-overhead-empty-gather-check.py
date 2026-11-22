"""Candidate32 empty-gather primal and VJP check for the supervisor environment.

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
scope = dict(np=np, lax=lax)
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
candidate = scope["_static_take"]


def reference(values, indices):
    return lax.gather(
        values, np.asarray(indices, dtype=np.int64)[:, None],
        lax.GatherDimensionNumbers(offset_dims=(), collapsed_slice_dims=(0,), start_index_map=(0,)),
        slice_sizes=(1,), mode=lax.GatherScatterMode.PROMISE_IN_BOUNDS,
    )


rng = np.random.default_rng(3232)
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

# The empty optimization must retain the parent gather's validation for invalid
# operand shapes, including an empty operand with slice_sizes=(1,).
invalid_checked = 0
for shape, indices in [
    ((0,), []), ((), []), ((2, 3), []),
    ((3,), 0),
]:
    failures = []
    for function in (candidate, reference):
        try:
            jax.jit(lambda x: function(x, indices))(jnp.zeros(shape, dtype=jnp.float64))
        except Exception as error:
            failures.append(type(error))
        else:
            failures.append(None)
    assert failures[0] is not None and failures[0] is failures[1], (shape, indices, failures)
    invalid_checked += 1
print(f"PASS: {invalid_checked} invalid-shape exception comparisons")
