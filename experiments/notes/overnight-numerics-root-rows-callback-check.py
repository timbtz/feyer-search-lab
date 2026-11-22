"""Actual tiny callbacks with root rows, modulation and zero-coefficient VJPs."""
import ast
import itertools
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = '534570265891b5782b8b55ef10b5b06eb778d1c3'


def main():
    path = ROOT / 'experiments/notes/overnight-numerics-destination-broadcast-callback-check.py'
    nodes = []
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'parent' for t in node.targets):
            break
        nodes.append(node)
    helper = {'__file__': str(path)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), helper)
    helper['names'].update(('_sweep_last_writes', 'HostPlan', '_RootRows', '_RootFactor', '_factor_full'))
    sources = [subprocess.check_output(['git', 'show', PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True),
               (ROOT / 'differometor/host_pass.py').read_text()]
    versions = [helper['load'](s, (ROOT / 'differometor/host.py').read_text()) for s in sources]
    nodes = [n for n in ast.parse((ROOT / 'differometor/sparse.py').read_text()).body
             if isinstance(n, ast.ClassDef) and n.name in ('SparsePattern', 'SparseSystem')]
    for ns, counters in versions:
        ns['_ROOT_ROWS'] = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'sparse-classes', 'exec'), ns)
    cases = coordinates = 0
    maximum_difference = maximum_fd_error = 0.
    for count, reuse, mode, modulation, zero, conjugated in itertools.product(
            (1, 3), (False, True), ('matched', 'cleared', 'interleaved'),
            ('signal_function', 'laser_amplitude_modulation', 'laser_frequency_modulation',
             'laser_frequency_modulation_lower'), (False, True), (False, True)):
        results = []
        for version, (ns, counters) in enumerate(versions):
            cb = np.column_stack((np.eye(2) * 3, [0., .1])).astype(complex)
            cb[1, 0] = .2 + .01j
            sb = np.column_stack((np.eye(4) * 4, [0., 0., 0., .1])).astype(complex)
            sb[1, 0], sb[2, 1], sb[3, 2], sb[1, 3] = .2j, .1, .15j, .03
            nb = (np.eye(4) * 2).astype(complex)
            if not reuse:
                nb[1, 0] = .02j
            cs = ns['SparseSystem'](cb, [0], [2])
            ss = ns['SparseSystem'](sb, [0, 2], [4, 0])
            noise = ns['SparseSystem'](nb, [0], [0])
            functions = {f.__name__: i for i, f in enumerate(ns['HOST_FUNCTIONS'])}
            def component(system, name):
                return ns['SystemPlan'](system, [(functions[name], np.arange(7)[None, :], (0, 1))], [0], [0])
            signal = ns['SystemPlan'](ss, [(functions[modulation], np.arange(7)[None, :], (0, 1)),
                (functions['signal_function'], np.array([[2, 3, 4, 5, 6, 0, 1]]), (0, 1))], [0, 1], [0, 0])
            placing = ss.positions([0, 3], [4, 4])
            conjugate = np.zeros(ss.all_rows.size, bool)
            if conjugated:
                conjugate[ss.positions([2], [0])] = True
            structure = SimpleNamespace(_key='synthetic', carrier=cs, signal=ss, noise=noise,
                                        signal_placing_positions=placing, signal_conjugate=conjugate)
            hp = ns['HostPlan'](structure, component(cs, 'laser'), signal, component(noise, 'signal_function'),
                                np.array([1]), np.array([0]), np.array([0, 1]), reuse)
            params = np.full((1, 7), .4, complex)
            params[0, 2] = 0. if zero else .03
            cv, sv = np.array([[3.]], complex), np.linspace(20., 107., count)[None, :].astype(complex)
            selects = np.array([[[.2, .3j, .5, .7j]], [[.3j, .1, .8j, .2]]])
            args = (params, cv, sv, cb[cs.all_rows, cs.all_cols], sb[ss.all_rows, ss.all_cols],
                    nb[noise.all_rows, noise.all_cols], selects)
            forward = ns['host_forward'](hp, *args)
            if version:
                assert ns['_ROOT_ROWS'][ss.pattern].roots.tolist() == [0]
                assert ns['_ROOT_ROWS'][cs.pattern].roots.tolist() == [0]
            if mode == 'cleared':
                ns['_ASSEMBLY'].clear()
            elif mode == 'interleaved':
                changed = params.copy()
                changed[0, 2] += .1
                ns['host_forward'](hp, changed, *args[1:])
            c, s, n, cov, w = forward
            bars = (np.full(c.shape, .01 + .02j), np.full(s.shape, .02 - .03j), np.full(n.shape, .04))
            backward = ns['host_backward'](hp, *args, *forward, *bars)
            assert not ns['_ASSEMBLY']
            assert abs(backward[0][0, 2]) > 0
            results.append((*forward, *backward))
            before = counters['factors']
            repeated = ns['host_forward'](hp, *args)
            assert counters['factors'] - before == 1 + count
            helper['helper']['check_equal'](repeated, forward)
            if not version:
                continue
            def loss(arguments):
                output = ns['host_forward'](hp, *arguments)
                return float(sum(np.real(np.sum(y * b)) for y, b in zip(output[:3], bars)))
            checks = [(0, (0, 2)), (0, (0, 3)), (1, (0, 0)), (2, (0, 0)),
                      (3, (int(cs.positions([0], [0])[0]),)),
                      (3, (int(cs.positions([1], [0])[0]),)),
                      (4, (int(ss.positions([0], [0])[0]),)), (5, (0,)), (6, (0, 0, 1))]
            for arg, index in checks:
              for direction in (1., 1j):
                plus, minus = [x.copy() for x in args], [x.copy() for x in args]
                step = 1e-4
                plus[arg][index] += step * direction
                minus[arg][index] -= step * direction
                numerical = (loss(plus) - loss(minus)) / (2 * step)
                analytic = float(np.real(backward[arg][index] * direction))
                maximum_fd_error = max(maximum_fd_error, abs(numerical - analytic))
                np.testing.assert_allclose(numerical, analytic, rtol=2e-6, atol=1e-9)
                coordinates += 1
        for old, new in zip(*results):
            assert np.all(np.isfinite(new))
            scale = max(float(np.max(np.abs(old))) if old.size else 0., 1e-300)
            np.testing.assert_allclose(new, old, rtol=1e-11, atol=1e-13 * scale)
            if old.size:
                maximum_difference = max(maximum_difference, float(np.max(np.abs(new - old))) / scale)
        cases += 1
    print(json.dumps(dict(parent=PARENT, callback_cases=cases, arrays_per_case=12,
                         finite_difference_coordinates=coordinates, maximum_fd_absolute_error=maximum_fd_error,
                         maximum_parent_array_scaled_difference=maximum_difference,
                         fresh_factorization_and_zero_derivative_checks=True,
                         scope='Tiny actual source callbacks; no JAX/full builder/official timing'), indent=2))


if __name__ == '__main__':
    main()
