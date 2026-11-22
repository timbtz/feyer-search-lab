"""Small surface equivalence and operation-count checks; no benchmark or timings.

Execute source-derived NumPy/dual component functions without importing JAX.
Compare against the admitted parent, including all seven differentiated slots.
"""
import ast
from collections import Counter
from pathlib import Path
import subprocess
import types

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = "ee4fea28c04d482566be16e916b609d7c6a99e5e"


def load(source):
    host = ast.parse((ROOT / "differometor/host.py").read_text())
    names = {"Dual", "Stack", "_Slots", "_holomorphic", "_conjugate", "_radians",
             "_value_only", "_columns", "evaluate_function", "function_jacobian"}
    nodes = [node for node in host.body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
             or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_SHIM"
                                                     for t in node.targets)]
    ns = {"np": np, "types": types}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "host-kernels", "exec"), ns)
    counts = Counter()

    def counted(name, function):
        def call(*args, **kwargs):
            counts[name] += 1
            return function(*args, **kwargs)
        return call

    shim = ns["_SHIM"]
    for name in ("sqrt", "cos", "sin", "arcsin", "exp", "radians"):
        setattr(shim, name, counted(name, getattr(shim, name)))
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))
                 or isinstance(node, ast.ImportFrom) and node.module == "__future__"]
    components = {"np": np, "jnp": shim}
    exec(compile(tree, "components", "exec"), components)
    components["phase_shift"] = counted("phase_shift", components["phase_shift"])
    ns["HOST_FUNCTIONS"] = components["FUNCTIONS"]
    ns["index"] = next(i for i, f in enumerate(components["FUNCTIONS"]) if f.__name__ == "surface")
    return ns, counts


def check_equal(old, new):
    for expected, actual in zip(old, new):
        np.testing.assert_array_equal(actual, expected)
        # Bitwise compare finite entries too, including the signs of zero.
        finite = np.isfinite(expected)
        assert actual[finite].tobytes() == expected[finite].tobytes()


def main():
    parent_source = subprocess.check_output(
        ["git", "show", f"{PARENT}:differometor/components.py"], cwd=ROOT, text=True)
    parent, old_counts = load(parent_source)
    candidate, new_counts = load((ROOT / "differometor/components.py").read_text())
    rng = np.random.default_rng(2026112203)
    inputs = np.empty((3, 11, 7), dtype=np.complex128)
    for slot, (low, high) in enumerate(((0, .2), (.01, .99), (-90, 90), (-9000, 9000),
                                       (.9, 1.2), (1.3, 1.6), (-25, 25))):
        inputs[..., slot] = rng.uniform(low, high, inputs.shape[:-1])
    cases = [inputs, inputs + 1e-3j * rng.normal(size=inputs.shape)]
    for slot, value in ((0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (3, 0), (4, 0), (5, 0), (6, 90)):
        case = inputs.copy()
        case[..., slot] = value
        cases.append(case)
    total_internal_reflection = inputs.copy()
    total_internal_reflection[..., 4:7] = [1.0, 1.7, 65.0]
    cases.append(total_internal_reflection)
    count = 0
    with np.errstate(all="ignore"):
        for case in cases:
            for slots in ((), (0, 1, 2), tuple(range(7)), (6, 4, 2, 0)):
                expected = parent["function_jacobian"](parent["index"], slots, case)
                actual = candidate["function_jacobian"](candidate["index"], slots, case)
                check_equal(expected, actual)
                count += 1
    # Check actual derivative directions independently with central differences
    # in both real and imaginary coordinates at a nonsingular random point.
    point = inputs[0, 0].copy()
    _, linear, antilinear = candidate["function_jacobian"](candidate["index"], range(7), point)
    max_scaled_error = 0.0
    for slot in range(7):
        step = 1e-5 * max(1.0, abs(point[slot]))
        for direction in (1, 1j):
            plus, minus = point.copy(), point.copy()
            plus[slot] += direction * step
            minus[slot] -= direction * step
            finite_difference = (candidate["evaluate_function"](candidate["index"], plus)
                                 - candidate["evaluate_function"](candidate["index"], minus)) / (2 * step)
            expected = linear[:, slot] * direction + antilinear[:, slot] * np.conj(direction)
            error = np.max(np.abs(finite_difference - expected)) / max(1.0, np.max(np.abs(expected)))
            max_scaled_error = max(max_scaled_error, float(error))
            assert error < 2e-7, (slot, direction, error)
    old_counts.clear()
    new_counts.clear()
    for ns in (parent, candidate):
        ns["function_jacobian"](ns["index"], range(7), inputs, with_outputs=False)
    print({"array_cases": len(cases), "output_jacobian_checks": count,
           "finite_difference_directions": 14, "max_scaled_fd_error": max_scaled_error,
           "parent_calls_per_seven_slot_jacobian": dict(old_counts),
           "candidate_calls_per_seven_slot_jacobian": dict(new_counts)})


if __name__ == "__main__":
    main()
