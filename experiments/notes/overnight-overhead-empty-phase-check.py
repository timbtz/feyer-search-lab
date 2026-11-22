"""Small synthetic check for candidate15; run by the supervisor in the fixed environment.

No optical fixtures or timings. Extracts the actual phase code from simulate.py,
compares JIT primals and reverse derivatives with its unconditional predecessor,
and checks that only the structurally empty case removes the phase primitives.
"""

import ast
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
from jax import lax
import numpy as np

jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)

source = ast.parse((Path(__file__).resolve().parents[2] / "differometor/simulate.py").read_text())
functions = {node.name: node for node in source.body if isinstance(node, ast.FunctionDef)}
phase_if = next(
    node for node in ast.walk(functions["simulate"])
    if isinstance(node, ast.If)
    and isinstance(node.test, ast.BoolOp)
    and "layout.qhd_parameter_indices.size" in ast.unparse(node.test)
)
scatter_if = next(
    node for node in functions["_simulate_host_pass"].body
    if isinstance(node, ast.If) and ast.unparse(node.test) == "qhd_phase_values is not None"
)
namespace = {"np": np, "jnp": jnp, "lax": lax}
exec(compile(ast.Module(body=[functions["_static_take"]], type_ignores=[]), "actual_take", "exec"), namespace)


def make_function(conditional):
    template = ast.parse(
        "def phase(row, noise_selection_vectors, layout):\n"
        "    qhd_placing_indices = layout.qhd_placing_indices\n"
        "    return noise_selection_vectors\n"
    ).body[0]
    phase_code = [phase_if] if conditional else phase_if.orelse
    scatter_code = [scatter_if] if conditional else scatter_if.body
    template.body[1:1] = phase_code + scatter_code
    module = ast.fix_missing_locations(ast.Module(body=[template], type_ignores=[]))
    scope = dict(namespace)
    exec(compile(module, "actual_phase", "exec"), scope)
    return scope["phase"]


candidate, reference = make_function(True), make_function(False)
rng = np.random.default_rng(1521)
cases = [
    ([], []),
    ([0], [[0, 0, 0]]),
    ([2, 2], [[0, 1, 0], [1, 0, 3]]),
    ([3, 0, 1], [[1, 2, 3], [0, 0, 1], [1, 1, 2]]),
]
for case, (parameter_indices, placements) in enumerate(cases):
    layout = SimpleNamespace(
        qhd_parameter_indices=np.asarray(parameter_indices, dtype=np.int64),
        qhd_placing_indices=np.asarray(placements, dtype=np.int64).reshape(-1, 3),
    )
    for zero_phases in (False, True):
        row = jnp.asarray(np.zeros(4) if zero_phases else [0., -27., 90., 173.])
        selection = rng.normal(size=(2, 3, 4)) + 1j * rng.normal(size=(2, 3, 4))
        selection[0, 0, 0] = 0  # a current zero must retain its selection derivative
        selection = jnp.asarray(selection)
        cotangent = jnp.asarray(rng.normal(size=(2, 3, 4)) + 1j * rng.normal(size=(2, 3, 4)))

        def evaluate(function):
            def differentiated(values, selectors, cot):
                output, pullback = jax.vjp(lambda x, y: function(x, y, layout), values, selectors)
                return output, pullback(cot)
            return jax.jit(differentiated)(row, selection, cotangent)

        actual, expected = evaluate(candidate), evaluate(reference)
        for got, want in zip(jax.tree.leaves(actual), jax.tree.leaves(expected)):
            np.testing.assert_array_equal(np.asarray(got), np.asarray(want))
        primitives = [eq.primitive.name for eq in jax.make_jaxpr(
            lambda x, y: candidate(x, y, layout))(row, selection).jaxpr.eqns]
        if case == 0:
            assert not primitives, primitives
            np.testing.assert_array_equal(np.asarray(actual[1][0]), np.zeros(4))
        else:
            assert "exp" in primitives and "scatter-mul" in primitives, primitives
        print(f"case={case} zero_phases={zero_phases}: primal and both VJPs identical; {primitives}")

print("PASS: eight synthetic cases; no timing or optical correctness claim")
