"""Synthetic gather-layout equivalence and stride checks; no optical timings."""
import ast
import hashlib
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = '7a9480332bad29b5aaeacc5a4628481581507e7a'
helper = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
namespace, _ = helper['load']((ROOT / 'differometor/components.py').read_text())
equal = helper['check_equal']


def load_plan(source):
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ('SystemPlan', '_digest')]
    ns = dict(namespace, np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'system-plan', 'exec'), ns)
    return ns['SystemPlan']


old_class = load_plan(subprocess.check_output(
    ['git', 'show', PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True))
new_class = load_plan((ROOT / 'differometor/host_pass.py').read_text())
rng = np.random.default_rng(2026112237)
component_checks = integration_checks = 0
with np.errstate(all='ignore'):
    for batch in (1, 3, 17):
        storage = rng.uniform(.15, .7, (batch, 82)).astype(np.complex128)
        storage += .002j * rng.normal(size=storage.shape)
        # C, F, sliced and reversed sources; repeated/negative input indices.
        for rows in (storage[:, :41].copy(), np.asfortranarray(storage[:, :41]),
                     storage[:, ::2], storage[:, -1::-2]):
            indices = rng.integers(-41, 41, (5, 7))
            indices[2] = indices[0]
            for case in (rows, rows * 0, np.ones_like(rows)):
                advanced = case[:, indices]
                taken = np.take(case, indices, axis=1)
                equal((advanced,), (taken,))
                assert taken.flags.c_contiguous
                for function in range(len(namespace['HOST_FUNCTIONS'])):
                    for slots in ((), tuple(range(7)), (6, 4, 2, 0), (0, 0, -1)):
                        old = namespace['function_jacobian'](function, slots, advanced)
                        new = namespace['function_jacobian'](function, slots, taken)
                        equal(old, new)
                        bar = rng.normal(size=old[1].shape[:-1] + (1,))
                        def contract(result):
                            _, j, k = result
                            return np.sum(j * bar, axis=2) + np.conj(np.sum(k * bar, axis=2))
                        equal((contract(old),), (contract(new),))
                        component_checks += 1
            for duplicates in (False, True):
                groups = [(f, rng.integers(-41, 41, (2 + f % 3, 7)), tuple(range(7)))
                          for f in range(len(namespace['HOST_FUNCTIONS']))]
                size = sum(i.shape[0] * 4 for _, i, _ in groups)
                selected = np.arange(size)
                if duplicates:
                    selected = np.concatenate((selected, selected[::3]))
                writes = np.arange(selected.size) if not duplicates else rng.integers(0, size, selected.size)
                system = SimpleNamespace(write_positions=writes, _key='synthetic-gather-layout')
                old, new = [cls(system, groups, selected // 4, selected % 4)
                            for cls in (old_class, new_class)]
                assert old._key == new._key
                base = rng.normal(size=size + 7) + 1j * rng.normal(size=size + 7)
                bars = rng.normal(size=(batch, size + 7)) + 1j * rng.normal(size=(batch, size + 7))
                for case in (rows, rows * 0, np.ones_like(rows)):
                    equal((old.values(case, base),), (new.values(case, base),))
                    equal(old.backward(case, bars), new.backward(case, bars))
                    integration_checks += 1
                bars[:, 0] = np.nan + 1j * np.inf
                equal(old.backward(rows, bars), new.backward(rows, bars))
                integration_checks += 1
    # Boundary and nonfinite inputs, including signed zero, stay visible to all
    # component derivatives; the layout change does not select by numeric value.
    for value in (complex(-0.0, -0.0), 1e-12, 1e12, np.inf, np.nan):
        rows = np.full((3, 41), value, dtype=np.complex128)
        indices = rng.integers(0, 41, (5, 7))
        for function in range(len(namespace['HOST_FUNCTIONS'])):
            equal(namespace['function_jacobian'](function, tuple(range(7)), rows[:, indices]),
                  namespace['function_jacobian'](function, tuple(range(7)), np.take(rows, indices, axis=1)))
            component_checks += 1

probe = np.empty((17, 41), dtype=np.complex128)
indices = np.zeros((5, 7), dtype=np.int64)
a, b = probe[:, indices], np.take(probe, indices, axis=1)
print(dict(component_and_contraction_checks=component_checks,
           full_system_checks=integration_checks,
           advanced_strides=a.strides, take_strides=b.strides,
           gathered_bytes_each=b.nbytes, finite='bitwise equal',
           nonfinite='array-equal', scope='synthetic only; no timing claim'))
