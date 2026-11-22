"""Small component equivalence and call counts; no benchmark or timings.

Loads actual parent/candidate NumPy component kernels through AST extraction,
because the local inspection environment has NumPy but no JAX. All 19 source
functions are exercised, including scalar outputs and zero-valued parameters.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import types

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = "e5cbeba07943b6c797932263ff9deb721bf3ca89"


class CountedNumpy:
    def __init__(self):
        self.counts = Counter()

    def __getattr__(self, name):
        function = getattr(np, name)
        if name not in ("broadcast_to", "stack", "empty", "zeros"):
            return function

        def call(*args, **kwargs):
            self.counts[name] += 1
            return function(*args, **kwargs)
        return call


def load(source):
    proxy = CountedNumpy()
    names = {"Dual", "Stack", "_Slots", "_holomorphic", "_conjugate",
             "_radians", "_value_only", "_columns", "evaluate_function",
             "function_jacobian"}
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
             or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_SHIM"
                                                     for t in node.targets)]
    ns = dict(np=proxy, types=types)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "host-kernels", "exec"), ns)
    tree = ast.parse((ROOT / "differometor/components.py").read_text())
    tree.body = [node for node in tree.body
                 if not isinstance(node, (ast.Import, ast.ImportFrom))
                 or isinstance(node, ast.ImportFrom) and node.module == "__future__"]
    components = dict(np=np, jnp=ns["_SHIM"])
    exec(compile(tree, "components", "exec"), components)
    ns["HOST_FUNCTIONS"] = components["FUNCTIONS"]
    return ns, proxy.counts


def equal(expected, actual):
    assert expected.shape == actual.shape and expected.dtype == actual.dtype
    np.testing.assert_array_equal(actual, expected)
    # Check finite signed zero bits as well as values and nonfinite positions.
    finite = np.isfinite(expected)
    assert expected[finite].tobytes() == actual[finite].tobytes()


def main():
    source = (ROOT / "differometor/host.py").read_text()
    old_source = subprocess.check_output(
        ["git", "show", PARENT + ":differometor/host.py"], cwd=ROOT, text=True)
    old, old_counts = load(old_source)
    new, new_counts = load(source)
    rng = np.random.default_rng(2026112246)
    base = np.array([.2, .7, .3, 120., 1., 1.4, 2.], dtype=np.complex128)
    cases = [base, base.real, base.astype(np.complex64), base.tolist()]
    storage = np.broadcast_to(base, (4, 6, 7)).copy()
    storage += rng.uniform(-.01, .01, storage.shape)
    cases += [storage, storage + .001j, storage[::2, ::-2],
              np.asfortranarray(storage), np.broadcast_to(base, (2, 1, 3, 7)),
              np.empty((0, 7), complex), np.empty((2, 0, 7), complex)]
    for slot in range(7):
        for value in (0., -0., 1., -1., np.inf, np.nan):
            point = base.copy()
            point[slot] = value
            cases.append(point)
    total = jacobians = 0
    with np.errstate(all="ignore"):
        for index in range(len(new["HOST_FUNCTIONS"])):
            for inputs in cases:
                equal(old["evaluate_function"](index, inputs),
                      new["evaluate_function"](index, inputs))
                total += 1
                for slots in ((), tuple(range(7)), (6, 4, 2, 0), (0, 0, 1)):
                    for with_outputs in (False, True):
                        expected = old["function_jacobian"](index, slots, inputs, with_outputs)
                        actual = new["function_jacobian"](index, slots, inputs, with_outputs)
                        if with_outputs:
                            equal(expected[0], actual[0])
                        else:
                            assert expected[0] is actual[0] is None
                        equal(expected[1], actual[1])
                        equal(expected[2], actual[2])
                        jacobians += 1
    # An input zero at the evaluation point must retain its nonzero derivative.
    signal = next(i for i, f in enumerate(new["HOST_FUNCTIONS"])
                  if f.__name__ == "signal_function")
    point = base.copy()
    point[0] = 0
    output, linear, antilinear = new["function_jacobian"](signal, (0, 1), point)
    assert output[0] == 0 and abs(linear[0, 0]) > .99
    assert antilinear[0, 0] == 0
    # Count explicit production calls on a small synthetic group per function.
    # This is operation evidence, not a runtime/official performance measurement.
    old_counts.clear()
    new_counts.clear()
    for ns in (old, new):
        for index in range(len(ns["HOST_FUNCTIONS"])):
            ns["evaluate_function"](index, storage)
            ns["function_jacobian"](index, tuple(range(7)), storage, False)
    print(json.dumps(dict(parent_sha=PARENT,
        candidate_host_sha256=hashlib.sha256(source.encode()).hexdigest(),
        functions=len(new["HOST_FUNCTIONS"]), input_cases=len(cases),
        primal_comparisons=total, jacobian_comparisons=jacobians,
        finite_entries_bitwise_equal=True, nonfinite_positions_and_values_equal=True,
        zero_amplitude_derivative_preserved=True,
        parent_explicit_calls=dict(old_counts), candidate_explicit_calls=dict(new_counts),
        scope="Local synthetic correctness and explicit call counts only; no timings."), indent=2))


if __name__ == "__main__":
    main()
