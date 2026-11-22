"""Candidate16 synthetic check; supervisor fixed-environment execution only.

Extract actual helpers without importing the optical simulator. Compare JIT
primals and reverse derivatives against the unconditional linking path. No timing.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
from jax import lax, vmap
import numpy as np

jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)
root = Path(__file__).resolve().parents[2]
nodes = []
for name, wanted in (("build.py", {"_identity_link"}),
                     ("simulate.py", {"_static_link", "_static_take", "_static_set"})):
    nodes.extend(n for n in ast.parse((root / "differometor" / name).read_text()).body
                 if isinstance(n, ast.FunctionDef) and n.name in wanted)
scope = dict(np=np, jnp=jnp, lax=lax, vmap=vmap)
exec(compile(ast.Module(body=nodes, type_ignores=[]), "actual_helpers", "exec"), scope)
identity = scope["_identity_link"]
candidate = scope["_static_link"]

cases = [
    ([identity], [0], [0], [0], True),
    ([identity, identity], [3, 0], [3, 0], [-3, 8], True),
    ([identity], [3, 0], [0, 3], [0, 0], False),
    ([identity, lambda x: 2*x], [1, 2], [1, 2], [0, 1], False),
    ([lambda x: x], [0], [0], [0], False),
    ([identity, lambda x: 2*x], [0], [0], [0], False),
]
for case, (functions, sources, destinations, indices, shortcut) in enumerate(cases):
    scope["LINKING_FUNCTIONS"] = functions
    layout = SimpleNamespace(linked_indices=np.asarray(sources, dtype=np.int64),
                             indices_to_link=np.asarray(destinations, dtype=np.int64))
    indices = jnp.asarray(indices, dtype=jnp.int64)

    def reference(row, function_indices):
        inputs = scope["_static_take"](row, layout.linked_indices)
        outputs = vmap(lambda i, x: lax.switch(i, functions, x))(function_indices, inputs)
        return scope["_static_set"](row, layout.indices_to_link, outputs)

    for complex_values in (False, True):
        row = np.array([0., -0., 2., -3.])
        if complex_values:
            row = row.astype(np.complex128) + np.array([0j, 0j, 1j, -2j])
        row = jnp.asarray(row)
        cot = jnp.asarray([1, -2, 3, -4], dtype=row.dtype)

        def check(function):
            def differentiated(x, i, c):
                y, backward = jax.vjp(lambda v: function(v, i), x)
                return y, backward(c)[0]
            return jax.jit(differentiated)(row, indices, cot)

        wrapped = lambda x, i: candidate(x, layout, i)
        actual, expected = check(wrapped), check(reference)
        for got, want in zip(actual, expected):
            np.testing.assert_array_equal(np.asarray(got), np.asarray(want))
        primitives = [eq.primitive.name for eq in jax.make_jaxpr(wrapped)(row, indices).jaxpr.eqns]
        assert bool(primitives) != shortcut, primitives
        print(f"case={case} complex={complex_values} shortcut={shortcut}: primal/VJP agree")
print("PASS: twelve cases; dynamic indices, custom branches, permutations and zero values")
