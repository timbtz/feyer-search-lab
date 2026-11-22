"""Small carrier dependency checks; no official fixtures or timing runs.

Default executes the actual planning prefix with the stdlib adapter from the
shared-parameter diagnostic. --jax additionally builds a two-mirror setup and
compares matrix values and VJPs with an explicit all-instruction assembly.
"""

import argparse
from pathlib import Path
import random
import runpy
import subprocess


ROOT = Path(__file__).resolve().parents[2]
PARENT = "0b47280143b3f2839641b4ae51dd4c7b33fac549"
planner = runpy.run_path(str(Path(__file__).with_name(
    "overnight-overhead-shared-parameters-check.py")))["planner"]


def structural_checks():
    current = planner((ROOT / "differometor/build.py").read_text())
    parent = planner(subprocess.check_output(
        ["git", "show", PARENT + ":differometor/build.py"], cwd=ROOT, text=True))

    def instruction(inputs, position):
        return dict(function_input_indices=[inputs], function_indices=[position],
                    output_column_indices=[0], system_matrix_row_indices=[position],
                    system_matrix_column_indices=[position])

    # The builder's surface instructions read neighboring space indices. The
    # names here are arbitrary; only the index dependency establishes relevance.
    instructions = {"a_b": instruction([0, 1, 2], 0),
                    "a": instruction([3, 4, 5, 0, 6, 2, 0], 1),
                    "b": instruction([7, 8, 9, 0, 2, 6, 0], 2)}
    names = ["", "a_b_length", "a_b_refractive_index", "a_loss", "a_reflectivity",
             "a_tuning", "constant", "b_loss", "b_reflectivity", "b_tuning"]
    pairs = [["a_b", "refractive_index"]]
    for optimized, changing in ((pairs, []), ([], pairs)):
        args = (instructions, {}, {}, [], names, optimized, changing)
        assert parent(*args)[2] == ["a_b"]
        assert current(*args)[2] == ["a_b", "a", "b"]
    print("Confirmed parent omission: optimized or swept space index schedules no adjacent surface")

    rng = random.Random(5001)
    checks = 2
    for _ in range(600):
        names = [f"c{i}_value" for i in range(8)] + ["sig_value"]
        instructions = {f"c{i}": instruction([i] + [rng.randrange(9) for _ in range(4)], i)
                        for i in range(8)}
        optimized = [[f"c{i}", "value"] for i in rng.sample(range(8), rng.randrange(9))]
        if len(optimized) > 1 and rng.randrange(2):
            optimized = [optimized[:2]] + optimized[2:]
        for changing in ([], [["c3", "value"]], [["sig", "value"]]):
            args = (instructions, {}, {}, ["sig"], names, optimized, changing)
            before, actual = parent(*args), current(*args)
            active = set(before[0]) | set(before[4])
            expected = before[2] + [name for name, item in instructions.items()
                                    if name not in before[2] and any(
                                        index in active for row in item["function_input_indices"]
                                        for index in row)]
            assert actual[2] == expected
            assert actual[:2] == before[:2] and actual[4:] == before[4:]
            assert len(actual[2]) == len(set(actual[2]))
            assert actual[3].get("function_indices", []) == [int(name[1:]) for name in expected]
            if expected == before[2]:
                assert actual == before
            checks += 1
    print(f"PASS: {checks} structural checks; no numerical propagation or JAX execution")


def jax_checks():
    import importlib
    import sys
    sys.path.insert(0, str(ROOT))
    import jax
    import jax.numpy as jnp
    import numpy as np
    from differometor import Setup
    from differometor.components import FUNCTIONS
    builder = importlib.import_module("differometor.build")
    simulation = importlib.import_module("differometor.simulate")
    jax.config.update("jax_enable_x64", True)

    setup = Setup()
    setup.add("mirror", "a", reflectivity=0.7, tuning=17.)
    setup.add("mirror", "b", reflectivity=0.4, tuning=-23.)
    setup.space("a", "b", length=0.125, refractive_index=1.2)
    instructions, matrices, _ = builder.build(setup)
    index = instructions[-1].index("a_b_refractive_index")
    groups = {}
    _, carrier, _, _ = builder.pairs_to_arrays(
        *instructions, [["a_b", "refractive_index"]], component_groups=groups,
        matrix_shapes={"carrier": matrices[1].shape})
    inputs, functions, outputs, destinations = carrier

    def candidate(x):
        row = matrices[0][0].at[index].set(x)
        return simulation.update(row, matrices[1], inputs, outputs, destinations,
                                 functions, groups["carrier"])

    def reference(x):
        row = matrices[0][0].at[index].set(x)
        matrix = matrices[1]
        for item in instructions[0].values():
            values = jnp.stack([FUNCTIONS[int(function)](row[indices])
                                for function, indices in zip(item["function_indices"],
                                                              item["function_input_indices"])])
            rows = item.get("output_row_indices", np.zeros(len(item["output_column_indices"]), dtype=int))
            matrix = matrix.at[item["system_matrix_row_indices"], item["system_matrix_column_indices"]].set(
                values[rows, item["output_column_indices"]])
        return matrix

    candidate, reference = jax.jit(candidate), jax.jit(reference)
    rng = np.random.default_rng(5001)
    cotangent = jnp.asarray(rng.normal(size=matrices[1].shape) + 1j * rng.normal(size=matrices[1].shape))
    for index_value in (1., 1.2, 1.5, 2.):
        actual, back = jax.vjp(candidate, jnp.asarray(index_value))
        expected, expected_back = jax.vjp(reference, jnp.asarray(index_value))
        np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13)
        np.testing.assert_allclose(back(cotangent)[0], expected_back(cotangent)[0], rtol=1e-13, atol=1e-13)
    print("PASS: 4 real JAX two-mirror assembly value/VJP checks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jax", action="store_true")
    args = parser.parse_args()
    structural_checks()
    if args.jax:
        jax_checks()
