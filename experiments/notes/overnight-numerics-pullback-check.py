"""Synthetic streamed pullback equivalence checks, without JAX or timed workloads."""
from pathlib import Path
import runpy

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
loader = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
namespace, _ = loader['load']((ROOT / 'differometor/components.py').read_text())
rng = np.random.default_rng(2026112204)
checks = 0
for shape in ((7,), (13, 7), (3, 11, 7)):
    inputs = rng.uniform(.1, .8, shape).astype(np.complex128)
    inputs[..., 4:6] += 1
    cases = [inputs, inputs + .01j * rng.normal(size=shape)]
    for slot in range(7):
        zeros = inputs.copy()
        zeros[..., slot] = 0
        cases.append(zeros)
    for f, function in enumerate(namespace['HOST_FUNCTIONS']):
        for case in cases:
            # Reversed strides exercise noncontiguous cotangent inputs.
            cotangent = (rng.normal(size=shape[:-1] + (4,))
                         + 1j * rng.normal(size=shape[:-1] + (4,)))[..., ::-1]
            for slots in ((), (0,), (0, 1), (0, 1, 2), tuple(range(7)), (6, 4, 2, 0)):
                with np.errstate(all='ignore'):
                    _, linear, antilinear = namespace['function_jacobian'](f, slots, case, with_outputs=False)
                    expected = np.sum(linear * cotangent[..., None], axis=-2) + np.conj(
                        np.sum(antilinear * cotangent[..., None], axis=-2))
                    actual = namespace['function_pullback'](f, slots, case, cotangent)
                np.testing.assert_array_equal(actual, expected, err_msg=(function.__name__, shape, slots))
                finite = np.isfinite(expected)
                assert actual[finite].tobytes() == expected[finite].tobytes(), (function.__name__, shape, slots)
                checks += 1
print({'component_functions': len(namespace['HOST_FUNCTIONS']), 'pullback_checks': checks,
       'finite_entries': 'bitwise equal', 'nonfinite_entries': 'array-equal'})

# Integration: preserve last-write semantics and repeated parameter-index sums.
import ast
import hashlib
import subprocess
from types import SimpleNamespace
import tracemalloc


def system_plan(source):
    tree = ast.parse(source)
    nodes = [node for node in tree.body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in ('SystemPlan', '_digest')]
    ns = dict(namespace, np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'system-plan', 'exec'), ns)
    return ns['SystemPlan']


parent_source = subprocess.check_output(
    ['git', 'show', loader['PARENT'] + ':differometor/host_pass.py'], cwd=ROOT, text=True)
old_plan = system_plan(parent_source)
new_plan = system_plan((ROOT / 'differometor/host_pass.py').read_text())
integration_checks = 0
for batch_size in (1, 5):
    for duplicates in (False, True):
        groups = [(2, rng.integers(0, 17, (3, 7)), tuple(range(7))),
                  (17, rng.integers(0, 17, (2, 7)), (0, 1)),
                  (14, rng.integers(0, 17, (2, 7)), (0, 1, 2, 3, 4, 5)),
                  (15, rng.integers(0, 17, (2, 7)), tuple(range(7)))]
        selection = np.arange(36) if not duplicates else rng.integers(0, 36, 43)
        writes = np.arange(selection.size) if not duplicates else rng.integers(0, 24, selection.size)
        system = SimpleNamespace(write_positions=writes, _key='synthetic')
        old = old_plan(system, groups, selection // 4, selection % 4)
        new = new_plan(system, groups, selection // 4, selection % 4)
        rows = rng.uniform(.1, .8, (batch_size, 17)).astype(np.complex128)
        base = rng.normal(size=48).astype(np.complex128)
        bars = rng.normal(size=(batch_size, 48)) + 1j * rng.normal(size=(batch_size, 48))
        loader['check_equal']((old.values(rows, base),), (new.values(rows, base),))
        loader['check_equal'](old.backward(rows, bars), new.backward(rows, bars))
        # Include nonfinite cotangents without silently dropping 0 * NaN terms.
        bars[:, 0] = np.nan + 1j * np.inf
        with np.errstate(all='ignore'):
            loader['check_equal'](old.backward(rows, bars), new.backward(rows, bars))
        integration_checks += 1


# Peak traced allocation on one small synthetic surface group; no elapsed timing.
# Both paths produce the same fully materialized input cotangent result.
inputs = rng.uniform(.1, .8, (7, 31, 7)).astype(np.complex128)
cotangent = rng.normal(size=(7, 31, 4)) + 1j * rng.normal(size=(7, 31, 4))

def old_contract():
    _, linear, antilinear = namespace['function_jacobian'](2, tuple(range(7)), inputs, with_outputs=False)
    return np.sum(linear * cotangent[..., None], axis=-2) + np.conj(
        np.sum(antilinear * cotangent[..., None], axis=-2))


def peak(function):
    tracemalloc.start()
    try:
        result = function()
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak_bytes


expected, old_peak = peak(old_contract)
actual, new_peak = peak(lambda: namespace['function_pullback'](2, tuple(range(7)), inputs, cotangent))
loader['check_equal']((expected,), (actual,))
print({'system_plan_checks': integration_checks, 'synthetic_rows': 7 * 31,
       'parent_tracemalloc_peak_bytes': old_peak, 'candidate_tracemalloc_peak_bytes': new_peak,
       'scope': 'local small synthetic allocation inspection, not official RSS or timing'})
