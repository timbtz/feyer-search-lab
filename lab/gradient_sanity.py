"""Additional all-coordinate finite-difference sanity checks, not scored timing.

Uses the official sanity-check bounds (rtol=.01, atol=1e-6), with a step ladder
and explicit inconclusive results. This is not a substitute for tight numerical
regression or an independent high-precision proof of every derivative.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def extended_readout_loss(carrier, signal, noise, ports, reference):
    """Same physical readout formula with extended arithmetic for diagnostics."""
    import numpy as np
    c, s, n = np.asarray(carrier, dtype=np.clongdouble), np.asarray(signal, dtype=np.clongdouble), np.asarray(noise, dtype=np.longdouble)
    size = c.shape[0]
    signals = (np.conj(c)*s[:size] + c*s[size:2*size])[ports]
    detected = signals.squeeze() if len(ports) == 1 else signals[0]-signals[1]
    return np.mean(np.log10((n/np.abs(detected)).squeeze()/np.asarray(reference, dtype=np.longdouble)))


def check_coordinate(evaluate, point, index, derivative, step, *, direction=0):
    import numpy as np
    samples = []
    base = float(evaluate(point)) if direction else None
    for scale in (1., .5, .25):
        h = step * scale
        plus, minus = point.copy(), point.copy()
        if direction:
            plus[index] += direction * h
            minus[index] += direction * 2 * h
            estimate = direction * (-3 * base + 4 * float(evaluate(plus)) - float(evaluate(minus))) / (2 * h)
        else:
            plus[index] += h; minus[index] -= h
            estimate = (float(evaluate(plus)) - float(evaluate(minus))) / (2 * h)
        samples.append({'step': h, 'finite_difference': estimate})
    x, y = samples[-2]['finite_difference'], samples[-1]['finite_difference']
    finite = bool(np.isfinite([derivative, x, y]).all())
    stable = finite and bool(np.isclose(x, y, rtol=.01, atol=1e-6))
    agreement = finite and all(bool(np.isclose(derivative, v, rtol=.01, atol=1e-6)) for v in (x, y))
    return {'index': index, 'autodiff': float(derivative), 'samples': samples,
            'difference_scheme': 'central' if direction == 0 else 'second-order one-sided',
            'status': 'passed' if stable and agreement else 'failed' if stable else 'inconclusive',
            'finite': finite, 'step_ladder_stable': stable}


def run(args):
    import numpy as np
    tree = args.tree.resolve()
    sha = subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != args.sha or subprocess.check_output(['git', '-C', str(tree), 'status', '--porcelain', '--untracked-files=no'], text=True).strip():
        raise ValueError('Clean exact candidate required')
    sys.path.insert(0, str(tree))
    import jax
    import jax.numpy as jnp
    import differometor as df
    from differometor.setups import Setup, aligo, constrain_inter_grid_cell_spaces
    assert Path(df.__file__).resolve().parent == tree / 'differometor'
    jax.config.update('jax_enable_x64', True)
    jax.config.update('jax_enable_compilation_cache', False)
    props = ['reflectivity', 'tuning', 'db', 'angle', 'power', 'mass', 'length']
    data = tree / 'examples/data'
    if args.setup == 'grid':
        fixture = json.loads((data / 'uifo_800_3000.json').read_text())
        setup = Setup.from_data(fixture)
        pairs = constrain_inter_grid_cell_spaces(setup.parameters, props)
        reference = json.loads((data / 'uifo_800_3000_test_data.json').read_text())
    else:
        setup, _ = aligo(mode='space_modulation')
        fixture = setup.to_data()
        pairs = [list(pair) for pair in setup.parameters if pair[1] in props]
        reference = json.loads((data / 'aligo_test_data.json').read_text())
    values, labels = [], []
    for pair in pairs:
        name, prop = (pair if isinstance(pair[0], list) else [pair])[0]
        values.append(float(np.real(fixture['nodes' if name in fixture['nodes'] else 'edges'][name]['properties'][prop])))
        labels.append([name, prop])
    point = np.asarray(values, dtype=np.float64)
    frequencies = jnp.asarray(reference['frequencies'], dtype=jnp.float64)
    expected = jnp.asarray(reference['sensitivities'], dtype=jnp.float64)
    arrays, ports, *_ = df.run_build_step(setup, [('f', 'frequency')], frequencies, pairs)
    arrays['optimized_parameters'] = jnp.asarray(point)
    ports = jnp.asarray(ports)

    def loss(p, a, detector_ports, ref):
        carrier, signal, noise = df.simulate(**dict(a, optimized_parameters=p))
        signals = df.signal_detector(carrier, signal)[detector_ports]
        detected = signals.squeeze() if detector_ports.shape[0] == 1 else signals[0] - signals[1]
        sensitivity = (noise / jnp.abs(detected)).squeeze()
        return jnp.mean(jnp.log10(sensitivity / ref))

    compiled = jax.jit(loss)
    objective, grad = jax.jit(jax.value_and_grad(loss))(jnp.asarray(point), arrays, ports, expected)
    objective, grad = float(objective), np.asarray(grad)
    def evaluate(p):
        return float(compiled(jnp.asarray(p), arrays, ports, expected))
    precision_probe = bool(getattr(args, 'extended_residual', False))
    if precision_probe:
        # The target gradient was computed above by the UNMODIFIED candidate.
        # Only the diagnostic primal below gets more accurate residual/readout
        # arithmetic; this must never be reported as ordinary candidate timing.
        if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
            raise RuntimeError('Extended-precision diagnostics unavailable on this platform')
        import differometor.host_pass as hp
        from lab.solver_precision_probe import extended_solve
        original_solve = hp._solve
        def refined_solve(products, values, factor, rhs, trans):
            initial = original_solve(products, values, factor, rhs, trans)
            return extended_solve(products, values, factor, rhs, trans, initial)[0]
        hp._solve = refined_solve
        forward = jax.jit(lambda p: df.simulate(**dict(arrays, optimized_parameters=p)))
        port_ids = np.asarray(ports)
        ref = np.asarray(expected, dtype=np.longdouble)
        def evaluate(p):
            c, s, n = jax.device_get(forward(jnp.asarray(p)))
            return extended_readout_loss(c, s, n, port_ids, ref)
    results = {'schema': 'feyer-all-coordinate-gradient-sanity-v1', 'candidate_sha': sha,
               'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'setup': args.setup, 'frequencies': int(frequencies.size), 'variables': len(point),
               'cpu_affinity': sorted(os.sched_getaffinity(0)), 'objective': objective,
               'rtol': .01, 'atol': 1e-6, 'checks': [], 'started_at': time.time(),
               'scope': 'Additional finite-difference sanity, not scored and not a 1e-7 precision certificate.'}
    if precision_probe:
        results.update(precision_assisted=True, target_gradient='Unmodified exact candidate autodiff',
                       scope='Diagnostic primal uses extended-residual solves and long-double readout; original candidate gradient target. Not a pass of the unmodified black-box finite difference, not timing evidence.',
                       residual_probe_sha256=hashlib.sha256(Path(__file__).with_name('solver_precision_probe.py').read_bytes()).hexdigest())
    floors = {'reflectivity': 1e-3, 'tuning': 1., 'angle': 1., 'db': 1.,
              'power': 1e-6, 'mass': 1e-9, 'length': 1e-3}
    prior = json.loads(args.recheck.read_text()) if getattr(args, 'recheck', None) else None
    if prior and (prior['candidate_sha'] != sha or prior['setup'] != args.setup):
        raise ValueError('Recheck must refer to the same exact candidate and setup')
    if prior:
        results['prior_sha256'] = hashlib.sha256(args.recheck.read_bytes()).hexdigest()
        results['scope'] += ' Predeclared alternative step sizes on previously nonpassing coordinates; original results retained.'
    only = getattr(args, 'only_indices', None)
    if only is not None and (not only or len(set(only)) != len(only) or any(i < 0 or i >= len(labels) for i in only)):
        raise ValueError('Explicit coordinate subset must be unique and in range')
    for index, (name, prop) in enumerate(labels):
        if only is not None and index not in only:
            continue
        if prior and prior['checks'][index]['status'] == 'passed':
            continue
        step = 1e-3 * max(abs(point[index]), floors[prop])
        direction = 0
        if prop == 'reflectivity':
            margin = min(point[index], 1 - point[index])
            if margin > 0:
                step = min(step, .1 * margin)
            else:
                direction = 1 if point[index] <= 0 else -1
        elif prop in ('power', 'mass', 'length'):
            if point[index] > 0:
                step = min(step, .1 * point[index])
            else:
                direction = 1
        if prior:
            attempts = []
            # Smaller steps probe truncation; larger steps probe cancellation.
            # This menu does not depend on whether a derivative agrees.
            for multiplier in ((.1, 1., 10., .01, 100.) if precision_probe else (.01, .0001, 100.)):
                h, side = step * multiplier, direction
                if prop == 'reflectivity' and min(point[index], 1-point[index]) <= h:
                    side = 1 if point[index] < .5 else -1
                    h = min(h, .01)
                elif prop in ('power', 'mass', 'length') and point[index] <= h:
                    side = 1
                attempts.append(check_coordinate(evaluate, point, index, grad[index], h, direction=side))
            check = {'index': index, 'autodiff': float(grad[index]), 'attempts': attempts,
                     'status': 'passed' if any(a['status'] == 'passed' for a in attempts) else 'unresolved'}
        else:
            check = check_coordinate(evaluate, point, index, grad[index], step, direction=direction)
        check['parameter'] = [name, prop]
        results['checks'].append(check)
        if index % 20 == 0 or check['status'] != 'passed':
            print(args.setup, index, name, prop, check['status'], flush=True)
        args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + '\n')
    results['passed'] = all(x['status'] == 'passed' for x in results['checks'])
    results['finished_at'] = time.time()
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + '\n')
    print('COMPLETE', args.setup, {status: sum(x['status'] == status for x in results['checks'])
                                 for status in ('passed', 'failed', 'inconclusive', 'unresolved')}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', required=True, type=Path)
    p.add_argument('--sha', required=True)
    p.add_argument('--setup', choices=['grid', 'aligo'], required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--recheck', type=Path, help='Retain a first pass and probe its nonpassing coordinates with a fixed alternative step menu')
    p.add_argument('--extended-residual', action='store_true', help='Separate precision-assisted primal diagnostic; original candidate AD target')
    p.add_argument('--only-indices', type=int, nargs='+')
    run(p.parse_args())
