"""Synthetic Jacobian storage checks; no optical workloads or timings."""
import ast
import hashlib
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
loader = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
namespace, _ = loader['load']((ROOT / 'differometor/components.py').read_text())
parent_host = subprocess.check_output(
    ['git', 'show', loader['PARENT'] + ':differometor/host.py'], cwd=ROOT, text=True)
old_ns = dict(namespace)
node = next(n for n in ast.parse(parent_host).body
            if isinstance(n, ast.FunctionDef) and n.name == 'function_jacobian')
exec(compile(ast.Module(body=[node], type_ignores=[]), 'parent-jacobian', 'exec'), old_ns)
old_jac, new_jac = old_ns['function_jacobian'], namespace['function_jacobian']
rng = np.random.default_rng(2026112216)
checks = 0


def contract(j, k, bar):
    return np.sum(j * bar[..., None], axis=-2) + np.conj(np.sum(k * bar[..., None], axis=-2))


for shape in ((7,), (13, 7), (3, 11, 7)):
    inputs = rng.uniform(.1, .8, shape).astype(np.complex128)
    inputs[..., 4:6] += 1
    cases = [inputs, inputs + .01j * rng.normal(size=shape)]
    for slot in range(7):
        zeros = inputs.copy()
        zeros[..., slot] = 0
        cases.append(zeros)
    for f in range(len(namespace['HOST_FUNCTIONS'])):
        for case in cases:
            bar = (rng.normal(size=shape[:-1] + (4,))
                   + 1j * rng.normal(size=shape[:-1] + (4,)))[..., ::-1]
            for slots in ((), (0,), (0, 1), (0, 1, 2), tuple(range(7)), (6, 4, 2, 0)):
                with np.errstate(all='ignore'):
                    old = old_jac(f, slots, case)
                    new = new_jac(f, slots, case)
                    loader['check_equal'](old, new)
                    loader['check_equal']((contract(*old[1:], bar),), (contract(*new[1:], bar),))
                checks += 1


def system_plan(jacobian):
    source = (ROOT / 'differometor/host_pass.py').read_text()
    nodes = [n for n in ast.parse(source).body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
             and n.name in ('SystemPlan', '_digest')]
    ns = dict(namespace, np=np, hashlib=hashlib, function_jacobian=jacobian)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'system-plan', 'exec'), ns)
    return ns['SystemPlan']


old_plan, new_plan = system_plan(old_jac), system_plan(new_jac)
integration_checks = 0
for batch_size in (1, 5):
    for duplicates in (False, True):
        groups = [(f, rng.integers(0, 37, (2 + f % 3, 7)), tuple(range(7))) for f in range(19)]
        total = sum(indices.shape[0] * 4 for _, indices, _ in groups)
        selection = np.arange(total) if not duplicates else rng.integers(0, total, total + 13)
        writes = np.arange(selection.size) if not duplicates else rng.integers(0, 150, selection.size)
        system = SimpleNamespace(write_positions=writes, _key='synthetic')
        old, new = [cls(system, groups, selection // 4, selection % 4) for cls in (old_plan, new_plan)]
        rows = rng.uniform(.1, .8, (batch_size, 37)).astype(np.complex128)
        bars = rng.normal(size=(batch_size, total + 20)) + 1j * rng.normal(size=(batch_size, total + 20))
        loader['check_equal'](old.backward(rows, bars), new.backward(rows, bars))
        bars[:, 0] = np.nan + 1j * np.inf
        with np.errstate(all='ignore'):
            loader['check_equal'](old.backward(rows, bars), new.backward(rows, bars))
        integration_checks += 2

probe = rng.uniform(.1, .8, (7, 31, 7)).astype(np.complex128)
old = old_jac(2, tuple(range(7)), probe, with_outputs=False)[1]
new = new_jac(2, tuple(range(7)), probe, with_outputs=False)[1]
assert new[..., 0, 0].flags.c_contiguous
assert not old[..., 0, 0].flags.c_contiguous
assert old.nbytes == new.nbytes
print(dict(component_and_contraction_checks=checks, integration_checks=integration_checks,
           parent_strides=old.strides, candidate_strides=new.strides,
           derivative_plane_contiguous=True, jacobian_bytes_each=new.nbytes,
           finite='bitwise equal', nonfinite='array-equal', scope='synthetic, no timing claim'))
