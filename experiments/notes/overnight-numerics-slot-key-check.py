"""Synthetic static-plan identity repair; no benchmark or timing workload.

Default: source-derived NumPy kernels, for the local environment without JAX.
--jax: additionally check the real registered HostPlan with two JIT callbacks in
the evaluator environment. This optional check is separate from official runs.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = "e5cbeba07943b6c797932263ff9deb721bf3ca89"


def load(source):
    helper = runpy.run_path(str(ROOT / "experiments/notes/overnight-numerics-destination-broadcast-check.py"))
    ns, _ = helper["load"]((ROOT / "differometor/host.py").read_text())
    ns["hashlib"] = hashlib
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef))
             and n.name in {"SystemPlan", "HostPlan", "_digest"}]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "plan-kernels", "exec"), ns)
    return ns


def system(ns, slots, functions=("laser", "signal_function")):
    lookup = {f.__name__: i for i, f in enumerate(ns["HOST_FUNCTIONS"])}
    sparse = SimpleNamespace(write_positions=np.arange(len(slots)), _key="tiny-system")
    indices = np.arange(7)[None, :]
    groups = [(lookup[name], indices.copy(), d) for name, d in zip(functions, slots)]
    return ns["SystemPlan"](sparse, groups, np.arange(len(slots)), np.zeros(len(slots), int))


def host(ns, carrier, unchanged):
    return ns["HostPlan"](SimpleNamespace(_key="tiny-structure"), carrier,
                          unchanged, unchanged, [], [], [], False)


def same(expected, actual):
    np.testing.assert_array_equal(actual, expected)
    finite = np.isfinite(expected)
    assert actual[finite].tobytes() == expected[finite].tobytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jax", action="store_true")
    args = parser.parse_args()
    old_source = subprocess.check_output(
        ["git", "show", PARENT + ":differometor/host_pass.py"], cwd=ROOT, text=True)
    source = (ROOT / "differometor/host_pass.py").read_text()
    old, new = load(old_source), load(source)
    rows = np.array([[2., 0., .2, .3, 1., 1.4, 2.]], complex)
    bar = np.array([[1., 0.]], complex)
    pairs = []
    for ns in (old, new):
        a = system(ns, ((), (0,)))
        b = system(ns, ((0,), ()))
        ga, gb = a.backward(rows, bar)[0], b.backward(rows, bar)[0]
        assert ga[0, 0] == 0 and gb[0, 0] == .5
        pairs.append((host(ns, a, a), host(ns, b, a)))
    assert pairs[0][0] == pairs[0][1]
    assert len(dict(zip(pairs[0], ("a", "b")))) == 1
    assert pairs[1][0] != pairs[1][1]
    assert len(dict(zip(pairs[1], ("a", "b")))) == 2

    # Every partition has the same flat [0,...,6] but different group boundaries.
    # Include empty groups' derivative lists and confirm equal plans still share
    # keys. Compare all primal values and pullbacks to their corresponding parent.
    old_keys, new_keys = set(), set()
    count = 0
    unchanged = system(new, ((), ()))
    regular = np.array([[.2, .7, .2, .3, 1., 1.4, 2.]], complex)
    for first in range(8):
        for second in range(first, 8):
            slots = (tuple(range(first)), tuple(range(first, second)), tuple(range(second, 7)))
            funcs = ("laser", "surface", "signal_function")
            a, b = system(old, slots, funcs), system(new, slots, funcs)
            old_keys.add(a._key)
            new_keys.add(b._key)
            clone = system(new, slots, funcs)
            assert b._key == clone._key
            hb, hc = host(new, b, unchanged), host(new, clone, unchanged)
            assert hb == hc and hash(hb) == hash(hc)
            for point in (regular, np.concatenate([regular, regular + .001j], axis=0)):
                bars = np.broadcast_to(np.array([1., .2j, -.7]), (point.shape[0], 3))
                same(a.values(point, np.zeros(3)), b.values(point, np.zeros(3)))
                for expected, actual in zip(a.backward(point, bars), b.backward(point, bars)):
                    assert np.all(np.isfinite(expected)) and np.all(np.isfinite(actual))
                    same(expected, actual)
                count += 1
    assert len(old_keys) == 1 and len(new_keys) == 36

    jax_result = "not run (optional evaluator check)"
    if args.jax:
        sys.path.insert(0, str(ROOT))
        import jax
        from differometor import host_pass
        from differometor.host import HOST_FUNCTIONS
        assert Path(host_pass.__file__).resolve() == ROOT / "differometor/host_pass.py"
        jax.config.update("jax_enable_x64", True)
        ns = dict(vars(host_pass), HOST_FUNCTIONS=HOST_FUNCTIONS)
        a, b = system(ns, ((), (0,))), system(ns, ((0,), ()))
        ha, hb = host(ns, a, a), host(ns, b, a)

        @jax.jit
        def pullback(plan, r, v):
            return jax.pure_callback(lambda x, y: plan.carrier.backward(x, y)[0],
                                     jax.ShapeDtypeStruct(r.shape, np.complex128), r, v)

        same(a.backward(rows, bar)[0], np.asarray(pullback(ha, rows, bar)))
        same(b.backward(rows, bar)[0], np.asarray(pullback(hb, rows, bar)))
        same(a.backward(rows, bar)[0], np.asarray(pullback(ha, rows, bar)))
        jax_result = "three callbacks return each plan's intended gradient"
    print(json.dumps(dict(parent_sha=PARENT,
        candidate_host_pass_sha256=hashlib.sha256(source.encode()).hexdigest(),
        parent_collision_reproduced=True, parent_gradient_pair=[0., .5],
        candidate_distinguishes_pair=True, slot_partitions=36,
        parent_unique_keys=len(old_keys), candidate_unique_keys=len(new_keys),
        primal_and_pullback_cases=count, finite_results_bitwise_equal=True,
        equal_plan_hashes_preserved=True, jax_check=jax_result,
        scope="Synthetic correctness only; no timing or official workload"), indent=2))


if __name__ == "__main__":
    main()
