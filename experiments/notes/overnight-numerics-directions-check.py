"""Shared-primal directional AD checks; no optical workloads or timings."""
import ast
import hashlib
from pathlib import Path
import runpy
import subprocess
import types
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
loader = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
def load(host_source):
    names = {'Dual', '_Directions', 'Stack', '_Slots', '_holomorphic', '_conjugate',
             '_radians', '_value_only', '_columns', 'evaluate_function', 'function_jacobian'}
    nodes = [node for node in ast.parse(host_source).body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
             or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_SHIM'
                                                     for t in node.targets)]
    ns = dict(np=np, types=types)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'host-kernels', 'exec'), ns)
    tree = ast.parse((ROOT / 'differometor/components.py').read_text())
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))
                 or isinstance(n, ast.ImportFrom) and n.module == '__future__']
    components = dict(np=np, jnp=ns['_SHIM'])
    exec(compile(tree, 'components', 'exec'), components)
    ns['HOST_FUNCTIONS'] = components['FUNCTIONS']
    return ns


parent_host = subprocess.check_output(
    ['git', 'show', loader['PARENT'] + ':differometor/host.py'], cwd=ROOT, text=True)
old_ns = load(parent_host)
namespace = load((ROOT / 'differometor/host.py').read_text())
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
            for slots in ((), (0,), (0, 1), (0, 1, 2), tuple(range(7)), (6, 4, 2, 0), (-1, 6, 0, 0), np.array([0, 2, 6])):
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

# Count elementwise transcendental work as well as interpreter invocations.
counts = {}
for label, ns in (('parent', old_ns), ('candidate', namespace)):
    counts[label] = dict(calls=0, elements=0)
    shim = ns['_SHIM']
    for name in ('sqrt', 'sin', 'cos', 'arcsin', 'exp', 'cosh', 'sinh'):
        original = getattr(shim, name)
        def counted(x, original=original, label=label):
            counts[label]['calls'] += 1
            value = getattr(x, 'v', x)
            counts[label]['elements'] += np.asarray(value).size
            return original(x)
        setattr(shim, name, counted)
probe = rng.uniform(.1, .8, (3, 11, 7)).astype(np.complex128)
with np.errstate(all='ignore'):
    loader['check_equal'](old_jac(2, tuple(range(7)), probe, with_outputs=False)[1:],
                          new_jac(2, tuple(range(7)), probe, with_outputs=False)[1:])
assert counts['candidate']['calls'] < counts['parent']['calls']
print(dict(component_and_contraction_checks=checks, integration_checks=integration_checks,
           surface_transcendental_work=counts, finite='bitwise equal',
           nonfinite='array-equal', scope='synthetic, no timing claim'))

# Independent central differences of primal outputs at nonsingular complex and
# real points. Both step sizes must pass, not just the better of the two.
fd_checks, worst = 0, 0.0
for f, function in enumerate(namespace['HOST_FUNCTIONS']):
    for sample in range(3):
        point = rng.uniform(.2, .7, 7).astype(np.complex128)
        point[4:6] += 1
        if sample:
            point += .01j * rng.normal(size=7)
        primal = namespace['evaluate_function'](f, point)
        bar = rng.normal(size=4) + 1j * rng.normal(size=4)
        bar /= max(1e-30, float(np.max(np.abs(primal))))
        _, j, k = new_jac(f, tuple(range(7)), point)
        pullback = contract(j, k, bar)
        for slot in range(7):
            for direction in (1.0, 1.0j):
                expected = float(np.real(pullback[slot] * direction))
                for step in (1e-5, 5e-6):
                    plus, minus = point.copy(), point.copy()
                    plus[slot] += step * direction
                    minus[slot] -= step * direction
                    delta = (namespace['evaluate_function'](f, plus)
                             - namespace['evaluate_function'](f, minus)) / (2 * step)
                    observed = float(np.real(np.sum(delta * bar)))
                    error = abs(observed - expected) / max(1.0, abs(expected))
                    assert np.isfinite(error) and error < 2e-7, (f, slot, direction, step, error)
                    worst = max(worst, error)
                    fd_checks += 1

edge_checks = 0
for f in range(19):
    for value in (0, 1, -1, 1e-12, 1e12, np.inf, np.nan):
        point = np.full((3, 7), value, dtype=np.complex128)
        with np.errstate(all='ignore'):
            loader['check_equal'](old_jac(f, tuple(range(7)), point),
                                  new_jac(f, tuple(range(7)), point))
        edge_checks += 1
print(dict(finite_difference_checks=fd_checks, maximum_scaled_error=worst,
           extreme_and_nonfinite_input_checks=edge_checks))
