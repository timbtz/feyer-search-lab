"""Synthetic retained-input equivalence checks; no optical timings."""
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
                retained = case[:, indices]
                equal((advanced,), (retained,))
                for function in range(len(namespace['HOST_FUNCTIONS'])):
                    for slots in ((), tuple(range(7)), (6, 4, 2, 0), (0, 0, -1)):
                        old = namespace['function_jacobian'](function, slots, advanced)
                        primal = namespace['evaluate_function'](function, retained)
                        new = namespace['function_jacobian'](function, slots, retained)
                        equal((primal,), (old[0],))
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
                    gathered = new.gather_inputs(case)
                    before = tuple(x.tobytes() for x in gathered)
                    equal((old.values(case, base),), (new.values(case, base, gathered),))
                    equal(old.backward(case, bars), new.backward(case, bars, gathered))
                    assert before == tuple(x.tobytes() for x in gathered)
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
                  namespace['function_jacobian'](function, tuple(range(7)), rows[:, indices]))
            component_checks += 1

print(dict(component_and_contraction_checks=component_checks,
           full_system_checks=integration_checks,
            finite='bitwise equal',
           nonfinite='array-equal', scope='synthetic only; no timing claim'))

# Execute real assembly/forward/backward kernels on tiny synthetic matrices.
# SciPy supplies a fresh factor each time; no optical setup or timing workload.
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

names = {'SystemPlan', '_digest', '_Products', '_solve', '_split', '_assembly_key',
         '_noise_amplitude', 'host_forward', 'host_backward', '_sum_to', '_cast_bar',
         '_expand', '_expand_backward', '_assemble', '_selections', '_is_hermitian',
         '_transpose_index', '_collinear_coefficient'}


def load_execution(source):
    ns = dict(namespace, np=np, hashlib=hashlib, _ASSEMBLY={}, _TRANSPOSES={},
              REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14,
              UNIT_VACUUM=1., H_PLANCK=1., F0=1., _NOISE_SCALE=.5)
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'execution-kernels', 'exec'), ns)
    counts = dict(factors=0, gathered_bytes=0, gather_calls=0)
    def factor(pattern, values):
        counts['factors'] += 1
        return splu(csc_matrix((values, pattern.rows, pattern.indptr),
                              shape=(pattern.size, pattern.size)))
    expand = ns['_expand']
    def traced_expand(*args):
        return expand(*args).view(Rows)
    ns.update(_products=ns['_Products'], _factor=factor, _expand=traced_expand)
    return ns, counts


class Rows(np.ndarray):
    """Count the actual advanced-index input copies made by source kernels."""
    counter = None
    def __getitem__(self, index):
        result = super().__getitem__(index)
        if (isinstance(index, tuple) and len(index) == 2
                and isinstance(index[1], np.ndarray) and index[1].ndim == 2):
            self.counter['gather_calls'] += 1
            self.counter['gathered_bytes'] += result.nbytes
        return result


class Pattern(SimpleNamespace):
    __hash__ = object.__hash__
    __eq__ = object.__eq__


def system(size, write, augmented):
    pattern = Pattern(size=size, rows=np.tile(np.arange(size), size),
                              cols=np.repeat(np.arange(size), size),
                              indptr=np.arange(size + 1)*size)
    return SimpleNamespace(pattern=pattern, size=size, nnz=size*size,
                           augmented=augmented, rhs_rows=np.array([0, size-1]) if augmented else np.array([], int),
                           write_positions=np.array([write]), _key='synthetic')


parent_source = subprocess.check_output(['git', 'show', PARENT+':differometor/host_pass.py'], cwd=ROOT, text=True)
executions = [load_execution(parent_source), load_execution((ROOT/'differometor/host_pass.py').read_text())]
callback_checks = 0
for count in (1, 4):
    for reuse in (False, True):
        for mode in ('matched', 'cleared', 'interleaved'):
            results, totals = [], []
            for ns, counters in executions:
                counters.update(factors=0, gathered_bytes=0, gather_calls=0)
                Rows.counter = counters
                ns['_ASSEMBLY'].clear()
                cs, ss, nn = system(2, 4, True), system(4, 16, True), system(4, 0, False)
                functions = {f.__name__: i for i,f in enumerate(ns['HOST_FUNCTIONS'])}
                def plan(sys, name):
                    return ns['SystemPlan'](sys, [(functions[name], np.arange(7)[None,:], (0,1))], [0], [0])
                structure = SimpleNamespace(carrier=cs, signal=ss, noise=nn,
                    signal_placing_positions=np.array([], int), signal_conjugate=np.zeros(18, bool))
                hp = SimpleNamespace(_key='synthetic', structure=structure, noise_row_reuse=reuse,
                    carrier_changing=np.array([1]), signal_changing=np.array([1]),
                    signal_carrier_indices=np.array([], int), carrier=plan(cs,'laser'),
                    signal=plan(ss,'signal_function'), noise=plan(nn,'signal_function'))
                params = np.full((1,7), .4, dtype=complex).view(Rows)
                cv = np.array([[3.]], dtype=complex)
                sv = np.linspace(2., 7., count)[None,:].astype(complex)
                cb = np.r_[(np.eye(2)*3).ravel(), [0., .1]].astype(complex)
                sb = np.r_[(np.eye(4)*4).ravel(), [0., .1]].astype(complex)
                nb = (np.eye(4)*2).ravel().astype(complex)
                selects = np.array([[[.2, .3j, .5, .7j]], [[.3j,.1,.8j,.2]]])
                args = (params, cv, sv, cb, sb, nb, selects)
                forward = ns['host_forward'](hp, *args)
                after_forward = counters.copy()
                retained = sum(x.nbytes for state in ns['_ASSEMBLY'].values()
                               for key in ('carrier_inputs','signal_inputs','noise_inputs')
                               for x in state.get(key, ()))
                if mode == 'cleared':
                    ns['_ASSEMBLY'].clear()
                elif mode == 'interleaved':
                    changed = params.copy(); changed[0,0] += .1
                    ns['host_forward'](hp, changed, *args[1:])
                c,s,n,cov,w = forward
                bars = (np.full(c.shape,.01+0.02j), np.full(s.shape,.02-.03j), np.full(n.shape,.04))
                backward = ns['host_backward'](hp, *args, c,s,n,cov,w, *bars)
                assert not ns['_ASSEMBLY'], 'backward must consume/clear state'
                # Every fresh forward still factors; no reuse across evaluations.
                before = counters['factors']
                again = ns['host_forward'](hp, *args)
                assert counters['factors'] - before == 1+count
                equal(forward, again)
                results.append((*forward, *backward))
                totals.append((counters.copy(), after_forward, retained))
            equal(results[0], results[1])
            assert totals[0][0]['factors'] == totals[1][0]['factors']
            assert totals[1][0]['gather_calls'] == totals[0][0]['gather_calls']-3
            assert totals[0][0]['gathered_bytes']-totals[1][0]['gathered_bytes'] == totals[1][2]
            callback_checks += 1
print(dict(callback_scenarios=callback_checks, gathers_removed_per_reverse=3,
           last_scenario_counts=totals, result='bitwise equal',
           scope='tiny synthetic matrices, no optical workload or timing'))
