"""Exact-index component-row reuse: synthetic correctness/counts, no timings."""
import ast
import hashlib
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
helper = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
namespace, _ = helper['load']((ROOT / 'differometor/components.py').read_text())


def load_plan(source):
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ('SystemPlan', '_digest')]
    ns = dict(namespace, np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'system-plan', 'exec'), ns)
    return ns['SystemPlan'], ns


old_class, old_ns = load_plan(subprocess.check_output(
    ['git', 'show', helper['PARENT'] + ':differometor/host_pass.py'], cwd=ROOT, text=True))
new_class, new_ns = load_plan((ROOT / 'differometor/host_pass.py').read_text())
rng = np.random.default_rng(2026112217)
checks = 0
for batch in (1, 3, 9):
    for repeated in (False, True):
        for slots in ((), (0, 1, 2), tuple(range(7)), (6, 4, 2, 0)):
            groups = []
            for function in range(len(namespace['HOST_FUNCTIONS'])):
                indices = rng.integers(0, 37, (3, 7))
                if repeated:
                    indices = indices[[2, 0, 2, 1, 0, 1, 2, 0, 1]]
                groups.append((function, indices, slots))
            total_rows = sum(i.shape[0] for _, i, _ in groups)
            # Select every output, plus repeated reads. Repeated writes and
            # negative selections exercise original ordering/last-write rules.
            selected = np.concatenate((np.arange(total_rows * 4), np.arange(31)))
            selected[::5] -= total_rows * 4
            writes = rng.integers(0, 271, selected.size)
            system = SimpleNamespace(write_positions=writes, _key='row-reuse-synthetic')
            old = old_class(system, groups, selected // 4, selected % 4)
            new = new_class(system, groups, selected // 4, selected % 4)
            assert old._key == new._key
            if not repeated:
                assert all(inverse is None for _, inverse in new.evaluation_groups)
            base = rng.normal(size=281) + 1j * rng.normal(size=281)
            bars = rng.normal(size=(batch, 281)) + 1j * rng.normal(size=(batch, 281))
            rows = rng.uniform(.1, .6, (batch, 37)).astype(np.complex128)
            # Reuse the same plan with new values, zero-valued differentiable
            # inputs, and nonfinite component intermediates at boundaries.
            cases = [rows, rows + .001j * rng.normal(size=rows.shape), rows * 0,
                     np.ones_like(rows), rng.uniform(.2, .7, rows.shape).astype(np.complex128)]
            for case in cases:
                with np.errstate(all='ignore'):
                    helper['check_equal']((old.values(case, base),), (new.values(case, base),))
                    helper['check_equal'](old.backward(case, bars), new.backward(case, bars))
                checks += 1

# Count evaluated component rows and differentiated component rows, rather than
# assuming that fewer evaluations imply lower complete first-run time.
counts = {'parent': [0, 0], 'candidate': [0, 0]}
for label, ns in (('parent', old_ns), ('candidate', new_ns)):
    primal, jacobian = ns['evaluate_function'], ns['function_jacobian']
    def evaluate(f, inputs, original=primal, label=label):
        counts[label][0] += inputs.shape[1]
        return original(f, inputs)
    def differentiate(f, slots, inputs, original=jacobian, label=label, **kwargs):
        counts[label][1] += inputs.shape[1] * len(slots)
        return original(f, slots, inputs, **kwargs)
    ns['evaluate_function'], ns['function_jacobian'] = evaluate, differentiate
with np.errstate(all='ignore'):
    helper['check_equal']((old.values(rows, base),), (new.values(rows, base),))
    helper['check_equal'](old.backward(rows, bars), new.backward(rows, bars))
assert counts == {'parent': [171, 684], 'candidate': [57, 228]}, counts
print({'assembly_and_backward_checks': checks, 'evaluated_rows_and_derivative_rows': counts,
       'finite_results_bitwise_equal': True,
       'scope': 'synthetic only; no official workload or timing'})
