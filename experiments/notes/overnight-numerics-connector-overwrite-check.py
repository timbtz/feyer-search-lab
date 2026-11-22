"""Small duplicate-connector callback finite differences; no benchmark/timing."""
import ast
import itertools
import json
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'a5d5a10c9e63ef00a532407a2ed3220905d6e34b'


def main():
    path = ROOT / 'experiments/notes/overnight-numerics-destination-broadcast-callback-check.py'
    nodes = []
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'parent' for t in node.targets):
            break
        nodes.append(node)
    helper = {'__file__': str(path)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), helper)
    helper['names'].update(('_sweep_last_writes', 'HostPlan'))
    component_source = (ROOT / 'differometor/host.py').read_text()
    sources = [subprocess.check_output(['git', 'show', PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True),
               (ROOT / 'differometor/host_pass.py').read_text()]
    versions = [helper['load'](source, component_source)[0] for source in sources]
    cases = coordinates = failed_parent = 0
    maximum_error = 0.
    for placement, mode, modulation, count, conjugated, hermitian, zero_carrier in itertools.product(
            ('unique', 'duplicate', 'alias'), ('matched', 'cleared'),
            ('signal_function', 'laser_amplitude_modulation', 'laser_frequency_modulation',
             'laser_frequency_modulation_lower'), (1, 3), (False, True), (False, True), (False, True)):
        duplicate = placement != 'unique'
        results = []
        for version, ns in enumerate(versions):
            cs, ss, noise = helper['system'](2, [4], True), helper['system'](4, [16], True), helper['system'](4, [0], False)
            functions = {f.__name__: i for i, f in enumerate(ns['HOST_FUNCTIONS'])}
            def plan(system, name):
                return ns['SystemPlan'](system, [(functions[name], np.arange(7)[None, :], (0, 1))], [0], [0])
            placing = np.array({'unique': [16, 17], 'duplicate': [16, 16], 'alias': [16, -2]}[placement])
            conjugate = np.zeros(18, bool)
            conjugate[16] = conjugated
            structure = helper['SimpleNamespace'](_key='synthetic', carrier=cs, signal=ss, noise=noise,
                signal_placing_positions=placing, signal_conjugate=conjugate)
            hp = ns['HostPlan'](structure, plan(cs, 'laser'), plan(ss, modulation), plan(noise, 'signal_function'),
                                np.array([1]), np.array([0]), np.array([0, 1]), False)
            params = np.full((1, 7), .4, complex)
            cv, sv = np.array([[3.]], complex), np.linspace(20., 70., count)[None, :].astype(complex)
            cb = np.r_[(np.eye(2) * 3).ravel(), [0., 0. if zero_carrier else .1 + .03j]].astype(complex)
            sb = np.r_[(np.eye(4) * 4).ravel(), [0., .1]].astype(complex)
            nb = (np.eye(4) * 2).ravel().astype(complex)
            if not hermitian:
                nb[4] = .02j
            selects = np.array([[[.2, .3j, .5, .7j]], [[.3j, .1, .8j, .2]]])
            args = (params, cv, sv, cb, sb, nb, selects)
            forward = ns['host_forward'](hp, *args)
            c, s, n, cov, w = forward
            bars = (np.full(c.shape, .01 + .02j), np.full(s.shape, .02 - .03j), np.full(n.shape, .04))
            if mode == 'cleared':
                ns['_ASSEMBLY'].clear()
            backward = ns['host_backward'](hp, *args, *forward, *bars)
            results.append((forward, backward))
            def loss(arguments):
                result = ns['host_forward'](hp, *arguments)
                return float(sum(np.real(np.sum(y * bar)) for y, bar in zip(result[:3], bars)))
            # Carrier RHS last entry and carrier diagonal feed the surviving and
            # overwritten scales. Both complex directional derivatives matter.
            checks = [(3, (5,)), (3, (0,)), (3, (3,)), (0, (0, 0)), (1, (0, 0)), (2, (0, 0))]
            parent_failed = False
            for arg, index in checks:
                for direction in (1., 1j):
                    plus, minus = [x.copy() for x in args], [x.copy() for x in args]
                    step = 1e-4
                    plus[arg][index] += step * direction
                    minus[arg][index] -= step * direction
                    numerical = (loss(plus) - loss(minus)) / (2 * step)
                    expected = float(np.real(backward[arg][index] * direction))
                    good = np.isclose(numerical, expected, rtol=2e-6, atol=1e-9)
                    if version:
                        maximum_error = max(maximum_error, abs(numerical - expected))
                        np.testing.assert_allclose(numerical, expected, rtol=2e-6, atol=1e-9, err_msg=str((placement, mode, modulation, count, conjugated, hermitian, zero_carrier, arg, index, direction)))
                        coordinates += 1
                    elif not good:
                        parent_failed = True
            if not version and parent_failed:
                failed_parent += 1
        helper['helper']['check_equal'](results[0][0], results[1][0])
        if not duplicate:
            helper['helper']['check_equal'](results[0][1], results[1][1])
        for item in (*results[1][0], *results[1][1]):
            assert np.all(np.isfinite(item))
        cases += 1
    print(json.dumps(dict(parent=PARENT, cases=cases, finite_difference_coordinates=coordinates,
                         parent_failing_cases=failed_parent, maximum_absolute_error=maximum_error,
                         scope='Actual tiny host callbacks; finite differences, no JAX/builder/official timing'), indent=2))


if __name__ == '__main__':
    main()
