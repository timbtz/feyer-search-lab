"""Candidate40: synthetic conversion checks, no timing or optical benchmark.

--structural-only uses stdlib stubs on the actual three return expressions.
Default additionally compares complete built inputs on a small synthetic cavity
with the former conversion order, including sparse and host-plan fallback paths.
"""
import ast
import copy
from pathlib import Path
import sys
from types import SimpleNamespace

root = Path(__file__).resolve().parents[2]
build_tree = ast.parse((root / 'differometor/build.py').read_text())
node = next(n for n in build_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
expressions = node.body[-1].value.elts[1].elts[1:4]
assert all(isinstance(n, ast.IfExp) for n in expressions)
expressions = [compile(ast.Expression(n), '<matrix-return>', 'eval') for n in expressions]
sim_tree = ast.parse((root / 'differometor/simulate.py').read_text())
run_node = next(n for n in sim_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_build_step')
sparse_branch = next(n for n in run_node.body if isinstance(n, ast.If)
                     and isinstance(n.test, ast.Name) and n.test.id == 'SPARSE_SOLVES')
transfer = sparse_branch.body[-1]
assert isinstance(transfer, ast.For)
assert ast.literal_eval(transfer.iter) == ('carrier_matrix', 'signal_matrix', 'noise_matrix')
assert transfer.lineno > max(n.lineno for n in ast.walk(sparse_branch)
                            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                            and n.func.attr == 'build_host_plan')

if '--structural-only' in sys.argv:
    events = []
    def host(value, dtype=None):
        events.append(('host', dtype))
        return value
    def device(value):
        events.append(('device', None))
        return value
    scope = dict(np=SimpleNamespace(asarray=host, complex128=complex),
                 jnp=SimpleNamespace(asarray=device),
                 _host_array=lambda v, dtype: device(host(v, dtype)))
    count = 0
    for rows in range(12):
        for columns in range(13):
            value = [[complex(i, -j) for j in range(columns)] for i in range(rows)]
            scope.update(carrier_matrix=value, signal_matrix=value, noise_matrix=value)
            for expression in expressions:
                events.clear()
                eager = eval(expression, dict(scope, _host_matrices=False))
                assert sum(e[0] == 'device' for e in events) == 1
                events.clear()
                deferred = eval(expression, dict(scope, _host_matrices=True))
                assert not any(e[0] == 'device' for e in events)
                assert device(deferred) == eager
                count += 1
    print(f'PASS: {count} actual-expression conversion-order checks; fallback placement checked by AST')
    sys.exit(0)

import importlib
sys.path.insert(0, str(root))
import numpy as np
import jax
import jax.numpy as jnp
from differometor import Setup
builder = importlib.import_module('differometor.build')
simulator = importlib.import_module('differometor.simulate')
jax.config.update('jax_enable_x64', True)

# Reconstruct only the original conversion order; simulator computations unchanged.
reference = copy.deepcopy(run_node)
for n in ast.walk(reference):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'build':
        n.keywords = []
branch = next(n for n in reference.body if isinstance(n, ast.If)
              and isinstance(n.test, ast.Name) and n.test.id == 'SPARSE_SOLVES')
branch.body.pop()
module = ast.parse('from __future__ import annotations')
module.body.append(reference)
reference_scope = dict(vars(simulator))
exec(compile(ast.fix_missing_locations(module), '<original-conversion-order>', 'exec'), reference_scope)


def setup(tuning, modulation):
    s = Setup()
    s.add('laser', 'source', power=2.3, phase=17.)
    s.add('mirror', 'input', transmissivity=.2, loss=1e-5, tuning=tuning)
    s.add('mirror', 'end', transmissivity=.03, loss=2e-5, tuning=-3.)
    s.space('source', 'input', length=.7)
    s.space('input', 'end', length=8.4)
    s.add('detector', 'readout', target='input', port='left', direction='out')
    s.add('qnoised', 'noise', target='input', port='left', direction='out')
    s.add('frequency', 'sweep', frequency=71.)
    target = {'space_modulation': 'input_end',
              'amplitude_modulation': 'source_amplitude',
              'frequency_modulation': 'source_frequency'}[modulation]
    s.add('signal', 'drive', target=target)
    return s


def equal(a, b):
    if hasattr(a, '_key'):
        assert type(a) is type(b) and a._key == b._key
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a:
            equal(a[key], b[key])
    elif isinstance(a, (list, tuple)):
        assert type(a) is type(b) and len(a) == len(b)
        for x, y in zip(a, b):
            equal(x, y)
    elif isinstance(a, jax.Array):
        assert isinstance(b, jax.Array)
        x, y = np.asarray(a), np.asarray(b)
        assert x.shape == y.shape and x.dtype == y.dtype
        assert x.tobytes() == y.tobytes()
    else:
        assert a == b

count = 0
saved_sparse = simulator.SPARSE_SOLVES
saved_structure = simulator._build_sparse_structure
saved_host_builder = simulator._host_pass.build_host_plan
try:
    for path in ('host', 'sparse_only', 'unsupported', 'dense'):
        simulator.SPARSE_SOLVES = path != 'dense'
        simulator._build_sparse_structure = (lambda arrays: None) if path == 'unsupported' else saved_structure
        simulator._host_pass.build_host_plan = (lambda *args: None) if path == 'sparse_only' else saved_host_builder
        reference_scope.update(SPARSE_SOLVES=simulator.SPARSE_SOLVES,
                               _build_sparse_structure=simulator._build_sparse_structure)
        for tuning in (0., -0., 23.7):
            for mode in ('space_modulation', 'amplitude_modulation', 'frequency_modulation'):
                results = []
                for run in (simulator.run_build_step, reference_scope['run_build_step']):
                    s = setup(tuning, mode)
                    result = run(s, changing_pairs=[('sweep', 'frequency')],
                                 changing_values=jnp.array([13., 71., 333.]),
                                 optimization_pairs=s.parameters)
                    results.append(result)
                equal(*results)
                count += 1
finally:
    simulator.SPARSE_SOLVES = saved_sparse
    simulator._build_sparse_structure = saved_structure
    simulator._host_pass.build_host_plan = saved_host_builder
print(f'PASS: {count} synthetic built-input byte/plan-key comparisons; no timing claim')
