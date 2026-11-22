"""Small shared-optimization regression; no official fixtures or timing runs.

Default: execute the instruction-planning prefix of pairs_to_arrays with a tiny
stdlib stand-in for np.ones. Check group membership, source indices, deduplication
and ordinary-pair compatibility with the recorded parent. This does not test
NumPy, JAX, or optical propagation.
--jax: also assemble two independent laser sources with the real builder and JAX
update function, checking full matrix values/VJPs against independent inputs tied
outside the builder, and checking analytic laser powers and their gradients.
"""

import argparse
import ast
from collections import defaultdict
from pathlib import Path
import random
import subprocess
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
PARENT = "eb583adb64d1b0ea079c882d60048415783413f3"


class Ones(list):
    def __mul__(self, value):
        return [item * value for item in self]


def planner(source):
    tree = ast.parse(source)
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "pairs_to_arrays")
    end = next(i for i, node in enumerate(function.body)
               if isinstance(node, ast.FunctionDef) and node.name == "combine_arrays")
    function.body = function.body[:end] + ast.parse(
        "return (optimized_parameter_indices, optimization_value_indices, "
        "carrier_components, carrier_arrays, carrier_changing_parameter_indices, "
        "signal_changing_parameter_indices)"
    ).body
    # Delay PEP 604 annotations so the stdlib inspection also runs on Python 3.9.
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[
        ast.alias(name="annotations")], level=0), function], type_ignores=[])
    namespace = {"defaultdict": defaultdict,
                 "np": SimpleNamespace(ones=lambda size: Ones([1.0] * size))}
    exec(compile(ast.fix_missing_locations(module), "<actual planning prefix>", "exec"), namespace)
    return namespace["pairs_to_arrays"]


def structural_checks():
    source = (ROOT / "differometor/build.py").read_text()
    parent_source = subprocess.check_output(
        ["git", "show", PARENT + ":differometor/build.py"], cwd=ROOT, text=True)
    current, parent = planner(source), planner(parent_source)
    instructions = {
        name: dict(function_input_indices=[[i]], function_indices=[i],
                   output_column_indices=[0], system_matrix_row_indices=[i],
                   system_matrix_column_indices=[i])
        for i, name in enumerate(("a", "b", "c"))
    }
    names = ["a_power", "b_power", "c_power", "sig_phase", "a_phase"]
    signal_components = ["sig"]

    def run(function, pairs, changing=()):
        return function(instructions, {}, {}, signal_components, names, pairs, list(changing))

    witness = [[["a", "power"], ["b", "power"]]]
    assert run(parent, witness)[2] == ["b"]
    assert run(current, witness)[2] == ["a", "b"]
    print("Confirmed parent counterexample: shared a/b power schedules only b; repair schedules a and b")

    rng = random.Random(4901)
    choices = [["a", "power"], ["b", "power"], ["c", "power"],
               ["sig", "phase"], ["a", "phase"], ["a", "missing"], ["absent", "power"]]
    cases = [[], witness, [[['a', 'power'], ['sig', 'phase']]],
             [[['sig', 'phase'], ['b', 'power']]],
             [[['a', 'power'], ['a', 'phase'], ['a', 'power']]]]
    for _ in range(400):
        cases.append([rng.choice(choices) if rng.randrange(2) else
                      [rng.choice(choices) for _ in range(rng.randrange(1, 6))]
                      for _ in range(rng.randrange(9))])
    checks = 0
    for pairs in cases:
        expected_indices, expected_sources, expected_components = [], [], []
        for source_index, group in enumerate(pairs):
            members = group if isinstance(group[0], list) else [group]
            for component, property_name in members:
                key = component + "_" + property_name
                if key in names:
                    expected_indices.append(names.index(key))
                    expected_sources.append(source_index)
                if component in instructions and component not in expected_components:
                    expected_components.append(component)
        for changing in ([], [["a", "power"]], [["sig", "phase"]]):
            actual = run(current, pairs, changing)
            components = expected_components.copy()
            if changing == [["a", "power"]] and "a" not in components:
                components.append("a")
            assert actual[:3] == (expected_indices, expected_sources, components)
            expected_functions = [instructions[component]["function_indices"][0] for component in components]
            assert actual[3]["function_indices"] == expected_functions
            checks += 1

    # The complete captured instruction lists must remain identical for ordinary
    # (unshared) inputs, including missing properties, duplicates and sweeps.
    for _ in range(300):
        pairs = [rng.choice(choices) for _ in range(rng.randrange(12))]
        for changing in ([], [["b", "power"]], [["sig", "phase"]]):
            assert run(current, pairs, changing) == run(parent, pairs, changing)
            checks += 1
    print(f"PASS: {checks} stdlib planning cases; no NumPy/JAX execution")


def jax_checks():
    import importlib
    import sys
    sys.path.insert(0, str(ROOT))
    import jax
    import jax.numpy as jnp
    import numpy as np
    import differometor.components as components
    builder = importlib.import_module("differometor.build")
    simulation = importlib.import_module("differometor.simulate")
    jax.config.update("jax_enable_x64", True)

    names = ["", "a_power", "b_power", "a_phase", "b_phase"]
    instructions = {}
    for i, name in enumerate(("a", "b")):
        instructions[name] = dict(
            function_input_indices=np.array([[1 + i, 3 + i, 0, 0, 0, 0, 0]]),
            function_indices=[components.FUNCTIONS.index(components.laser)],
            output_column_indices=np.array([0]), system_matrix_row_indices=np.array([i]),
            system_matrix_column_indices=np.array([2]))
    parameters = jnp.array([0, 1, 4, 5, -12], dtype=jnp.float64)
    base = np.eye(2, 3, dtype=np.complex128)
    base[:, 2] = [components.laser_np(1, 5), components.laser_np(4, -12)]
    base = jnp.asarray(base)

    def prepare(pairs, expand):
        groups = {}
        prepared, carrier, _, _ = builder.pairs_to_arrays(
            instructions, {}, {}, [], names, pairs, component_groups=groups,
            matrix_shapes={"carrier": (2, 3)})
        input_indices, functions, output_indices, matrix_indices = carrier

        def assemble(x):
            values = expand(x)
            row = parameters.at[prepared[0]].set(values[prepared[1]])
            return simulation.update(row, base, input_indices, output_indices,
                                     matrix_indices, functions, groups["carrier"])
        return jax.jit(assemble)

    shared = prepare([[["a", "power"], ["b", "power"]],
                      [["a", "phase"], ["b", "phase"]]], lambda x: x)
    independent = prepare([["a", "power"], ["b", "power"], ["a", "phase"], ["b", "phase"]],
                          lambda x: jnp.stack((x[0], x[0], x[1], x[1])))
    cotangent = jnp.array([[1 + 2j, -3j, 2 - 7j], [5j, -1, 3 + 4j]])
    for power, phase in ((0.25, 0.), (2., -0.), (7., 37.), (15., -113.)):
        x = jnp.array([power, phase], dtype=jnp.float64)
        actual, actual_back = jax.vjp(shared, x)
        expected, expected_back = jax.vjp(independent, x)
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))
        np.testing.assert_allclose(actual_back(cotangent)[0], expected_back(cotangent)[0], rtol=1e-13, atol=1e-13)
        # Identity coefficient block: each RHS is the corresponding laser field.
        np.testing.assert_allclose(components.power_detector(actual[:, 2]), [power, power], rtol=1e-13, atol=1e-13)
        derivative = jax.grad(lambda value: jnp.sum(components.power_detector(shared(value)[:, 2])))(x)
        np.testing.assert_allclose(derivative, [2., 0.], rtol=1e-13, atol=1e-13)
    print("PASS: 4 real JAX assembly value/VJP and analytic laser power/gradient cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jax", action="store_true")
    args = parser.parse_args()
    structural_checks()
    if args.jax:
        jax_checks()
