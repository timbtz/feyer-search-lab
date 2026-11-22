"""Supervisor-only synthetic JAX check for candidate 14; no timings or fixtures.

Extracts the actual _static_set helper without importing the optical simulator.
Run in the fixed environment against the candidate checkout. This does not replace
both official benchmarks, full-array generalization checks, or source review.
"""
import ast
from pathlib import Path

import jax
from jax import lax
import jax.numpy as jnp
import numpy as np

jax.config.update('jax_enable_x64', True)
jax.config.update('jax_enable_compilation_cache', False)
source = Path(__file__).resolve().parents[2] / 'differometor' / 'simulate.py'
node = next(n for n in ast.parse(source.read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == '_static_set')
namespace = dict(np=np, jnp=jnp, lax=lax)
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
candidate = namespace['_static_set']


def reference(values, indices, updates):
    return lax.scatter(
        values, np.asarray(indices, dtype=np.int64)[:, None],
        jnp.asarray(updates).astype(values.dtype),
        lax.ScatterDimensionNumbers(update_window_dims=(), inserted_window_dims=(0,),
                                    scatter_dims_to_operand_dims=(0,)),
        unique_indices=True, mode=lax.GatherScatterMode.PROMISE_IN_BOUNDS)


def compare(left, right):
    for a, b in zip(jax.tree_util.tree_leaves(left), jax.tree_util.tree_leaves(right)):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))


rng = np.random.default_rng(4627)
cases = 0
for n in (1, 2, 5, 9):
    selections = [[], [0], [n-1], list(range(n)), list(range(1, n)),
                  list(range(0, n, 2)), list(reversed(range(n)))]
    for selection in selections:
        indices = np.asarray(selection, dtype=np.int64)
        for complex_updates in (False, True):
            values = rng.normal(size=n) + 1j * rng.normal(size=n)
            # Equal-valued updates still need full derivatives. Include signed zeros.
            values[0] = complex(-0.0, 0.0)
            updates = values[indices] if complex_updates else values[indices].real
            dv = rng.normal(size=n) + 1j * rng.normal(size=n)
            du = rng.normal(size=len(indices))
            if complex_updates:
                du = du + 1j * rng.normal(size=len(indices))
            bar = rng.normal(size=n) + 1j * rng.normal(size=n)
            args = tuple(jnp.asarray(x) for x in (values, updates))
            tangents = tuple(jnp.asarray(x) for x in (dv, du))
            functions = [lambda v, u, f=f: f(v, indices, u) for f in (reference, candidate)]
            compare(jax.jit(functions[0])(*args), jax.jit(functions[1])(*args))
            compare(jax.jit(lambda v, u, a, b: jax.jvp(functions[0], (v, u), (a, b)))(*args, *tangents),
                    jax.jit(lambda v, u, a, b: jax.jvp(functions[1], (v, u), (a, b)))(*args, *tangents))
            compare(jax.jit(lambda v, u, c: jax.vjp(functions[0], v, u)[1](c))(*args, jnp.asarray(bar)),
                    jax.jit(lambda v, u, c: jax.vjp(functions[1], v, u)[1](c))(*args, jnp.asarray(bar)))
            primitives = [str(eq.primitive) for eq in jax.make_jaxpr(functions[1])(*args).jaxpr.eqns]
            contiguous = indices.size > 0 and (indices.size == 1 or np.all(np.diff(indices) == 1))
            assert ('dynamic_update_slice' if contiguous else 'scatter') in primitives
            cases += 1
print(f'{cases} synthetic primal/JVP/VJP cases passed; both structural paths exercised.')
