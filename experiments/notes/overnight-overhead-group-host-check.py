"""Synthetic metadata/JIT/VJP check; run through the fixed evaluator environment.

No optical fixtures or timings. Compares the current helper to the same helper
with the parent's eager device conversion restored at its three conversion sites.
"""
import ast
import copy
from collections import defaultdict
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)
source = Path(__file__).resolve().parents[2] / "differometor" / "build.py"
node = next(n for n in ast.parse(source.read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == "_group_component_indices")


class RestoreDeviceConversion(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        if (isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "np" and node.func.attr == "asarray"):
            node.func = ast.Name(id="device_array", ctx=ast.Load())
        return node


def load(function):
    scope = dict(np=np, defaultdict=defaultdict,
                 device_array=lambda values, dtype: jnp.asarray(np.asarray(values, dtype=dtype)))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 str(source), "exec"), scope)
    return scope[function.name]


host_groups = load(copy.deepcopy(node))
device_groups = load(RestoreDeviceConversion().visit(copy.deepcopy(node)))
cases = [[], [0], [2, 0, 2, 1], [3, 3, 3], [1, 0, 1, 0, 2]]
for functions in cases:
    indices = np.arange(len(functions) * 3).reshape(-1, 3) % 7
    for inputs in (None, indices):
        host = host_groups(functions, inputs)
        device = device_groups(functions, inputs)
        assert jax.tree.structure(host) == jax.tree.structure(device)
        for left, right in zip(jax.tree.leaves(host), jax.tree.leaves(device)):
            assert isinstance(left, np.ndarray)
            assert left.dtype == right.dtype == np.dtype("int64")
            np.testing.assert_array_equal(left, np.asarray(right))
        if inputs is None:
            continue

        def readout(parameters, metadata):
            rows = [jnp.sum(parameters[metadata["parameter_indices"][key]], axis=1)
                    for key in sorted(metadata["function_rows"])]
            grouped = jnp.concatenate(rows) if rows else jnp.empty((0,), dtype=parameters.dtype)
            return grouped[metadata["output_rows"]]

        primal = jax.jit(readout)
        gradient = jax.jit(jax.grad(lambda parameters, metadata:
                                   jnp.sum(jnp.abs(readout(parameters, metadata)) ** 2)))
        for parameters in (jnp.array([0., -0., 2., -3., .5, 1., -1.]),
                           jnp.array([0j, 1+2j, -3j, 2., -.5j, 1j, -2.])):
            np.testing.assert_array_equal(primal(parameters, host), primal(parameters, device))
            np.testing.assert_array_equal(gradient(parameters, host), gradient(parameters, device))

print("PASS: 10 metadata comparisons and 10 synthetic JIT primal/gradient comparisons.")
