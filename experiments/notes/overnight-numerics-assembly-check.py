"""Synthetic direct-group assembly checks and allocation counts; no timings."""
import ast
import hashlib
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace
import tracemalloc

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
loader = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
namespace, _ = loader['load']((ROOT / 'differometor/components.py').read_text())


def load_plan(source):
    tree = ast.parse(source)
    nodes = [node for node in tree.body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in ('SystemPlan', '_digest')]
    ns = dict(namespace, np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'system-plan', 'exec'), ns)
    return ns['SystemPlan'], ns


parent_source = subprocess.check_output(
    ['git', 'show', loader['PARENT'] + ':differometor/host_pass.py'], cwd=ROOT, text=True)
old_class, old_ns = load_plan(parent_source)
new_class, new_ns = load_plan((ROOT / 'differometor/host_pass.py').read_text())
rng = np.random.default_rng(2026112206)
checks = 0
for count in (1, 3, 7):
    for duplicate_writes in (False, True):
        for negative_selections in (False, True):
            # All 19 component functions, variable group sizes, repeated input
            # parameter indices, and output reads shared by multiple writes.
            groups = [(f, rng.integers(0, 41, (1 + f % 4, 7)), tuple(range(7)))
                      for f in range(len(namespace['HOST_FUNCTIONS']))]
            total_outputs = sum(i.shape[0] * 4 for _, i, _ in groups)
            selection = rng.integers(0, total_outputs, 191)
            if negative_selections:
                selection[::3] -= total_outputs
            writes = rng.integers(0, 79, selection.size) if duplicate_writes else np.arange(selection.size)
            system = SimpleNamespace(write_positions=writes, _key='synthetic')
            old = old_class(system, groups, selection // 4, selection % 4)
            new = new_class(system, groups, selection // 4, selection % 4)
            base = rng.normal(size=211) + 1j * rng.normal(size=211)
            rows = rng.uniform(.1, .6, (count, 41)).astype(np.complex128)
            bars = rng.normal(size=(count, 211)) + 1j * rng.normal(size=(count, 211))
            for case in (rows, rows + .001j * rng.normal(size=rows.shape), rows * 0):
                with np.errstate(all='ignore'):
                    loader['check_equal']((old.values(case, base),), (new.values(case, base),))
                    loader['check_equal'](old.backward(case, bars), new.backward(case, bars))
                checks += 1

# A group with no surviving write is still evaluated. One output also feeds
# multiple destinations; later writes from other groups win independently.
groups = [(2, np.arange(7)[None, :], tuple(range(7))),
          (1, np.arange(7)[None, :], (0, 1)),
          (17, np.arange(7)[None, :], (0, 1))]
selection = np.array([0, 1, 4, 4, 8, 9])
system = SimpleNamespace(write_positions=np.array([0, 1, 0, 2, 1, 3]), _key='overwritten')
old = old_class(system, groups, selection // 4, selection % 4)
new = new_class(system, groups, selection // 4, selection % 4)
rows = np.full((3, 7), .3, dtype=np.complex128)
base = np.arange(8, dtype=np.complex128)
calls = []
original = new_ns['evaluate_function']
def counted(function_index, inputs):
    calls.append(function_index)
    return original(function_index, inputs)
new_ns['evaluate_function'] = counted
loader['check_equal']((old.values(rows, base),), (new.values(rows, base),))
assert calls == [2, 1, 17], calls
new_ns['evaluate_function'] = original
checks += 1

# Small synthetic groups with a fully materialized result in both paths.
groups = [(f, rng.integers(0, 41, (17, 7)), tuple(range(7))) for f in range(19)]
selection = rng.integers(0, 19 * 17 * 4, 800)
system = SimpleNamespace(write_positions=rng.integers(0, 400, 800), _key='allocation')
old = old_class(system, groups, selection // 4, selection % 4)
new = new_class(system, groups, selection // 4, selection % 4)
rows = rng.uniform(.1, .6, (7, 41)).astype(np.complex128)
base = np.zeros(1000, dtype=np.complex128)
def peak(plan):
    tracemalloc.start()
    try:
        result = plan.values(rows, base)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak_bytes
expected, old_peak = peak(old)
actual, new_peak = peak(new)
loader['check_equal']((expected,), (actual,))
print({'assembly_and_backward_checks': checks, 'all_groups_evaluated': calls,
       'parent_peak_bytes': old_peak, 'candidate_peak_bytes': new_peak,
       'scope': 'synthetic allocation, no official workload or timing'})
