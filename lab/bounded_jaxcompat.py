#!/usr/bin/env python3
"""Separate physical Voyager descent/batch diagnostic; does not replace the historical 11 tests."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback

os.environ.setdefault('JAX_PLATFORMS', 'cpu')
os.environ.setdefault('JAX_ENABLE_X64', 'true')
try:
    from .jaxcompat import PROPERTIES, compare_values, numeric_blocks, source_digest
except ImportError:
    from jaxcompat import PROPERTIES, compare_values, numeric_blocks, source_digest

TESTS = ('bounded_descent_3_steps', 'bounded_vmap_value_and_grad')


def validate_points(pairs, points):
    """Independently inspect saved points instead of trusting a success flag."""
    if not isinstance(points, list) or not points:
        return False
    try:
        numeric_blocks(points)
        for point in points:
            if len(point) != len(pairs):
                return False
            for (_, prop), value in zip(pairs, point):
                if prop in ('reflectivity', 'transmissivity', 'loss') and not 1e-6 <= value <= 1-1e-6:
                    return False
                if prop in ('power', 'mass', 'length') and value < 1e-12:
                    return False
        return True
    except (ValueError, TypeError):
        return False


def run(args):
    sys.path.insert(0, str(Path(args.tree).resolve()))
    import numpy as np
    import jax
    import jax.numpy as jnp
    import differometor as df
    from differometor import setups
    jax.config.update('jax_enable_x64', True)
    jax.config.update('jax_enable_compilation_cache', False)
    if os.path.commonpath([os.path.realpath(df.__file__), os.path.realpath(args.tree)]) != os.path.realpath(args.tree):
        raise RuntimeError(f'Unexpected simulator import: {df.__file__}')
    setup, all_pairs = setups.voyager()
    pairs = [list(pair) for pair in all_pairs if pair[1] in PROPERTIES]
    data = setup.to_data()
    initial = np.asarray([float(np.real(data['nodes' if name in data['nodes'] else 'edges'][name]['properties'][prop]))
                          for name, prop in pairs], dtype=np.float64)
    freqs = np.logspace(np.log10(20), np.log10(5000), 40)
    arrays, ports, *_ = df.run_build_step(setup, [('f', 'frequency')], jnp.asarray(freqs), pairs)
    params = jnp.asarray(initial)
    ports = jnp.asarray(ports)

    def loss(p):
        carrier, signal, noise = df.simulate(**dict(arrays, optimized_parameters=p))
        signals = df.signal_detector(carrier, signal)[ports]
        detected = signals.squeeze() if ports.shape[0] == 1 else signals[0] - signals[1]
        return jnp.mean(jnp.log10((noise / jnp.abs(detected)).squeeze()))

    # Strictly interior physical restrictions, not optimizer sampling ranges.
    # In particular, negative tuning is allowed (built-in Voyager fm2 has -0.014).
    lower = np.full(initial.shape, -np.inf)
    upper = np.full(initial.shape, np.inf)
    for index, (_, prop) in enumerate(pairs):
        if prop in ('reflectivity', 'transmissivity', 'loss'):
            lower[index], upper[index] = 1e-6, 1-1e-6
        elif prop in ('power', 'mass', 'length'):
            lower[index] = 1e-12
    if not np.all((initial >= lower) & (initial <= upper)):
        raise ValueError('initial Voyager parameters outside diagnostic interior bounds')
    low, high = jnp.asarray(lower), jnp.asarray(upper)
    project = lambda p: jnp.clip(p, low, high)
    scale = jnp.maximum(jnp.abs(params), 1e-3)
    direction = np.random.default_rng(0).standard_normal(len(initial))
    direction = jnp.asarray(direction / np.linalg.norm(direction))
    report = dict(schema_version=1, setup='voyager', scope='bounded trajectories only; not full JAX compatibility',
                  identity=dict(source_sha256=source_digest(args.tree),
                                harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                comparison_sha256=hashlib.sha256(Path(sys.modules[compare_values.__module__].__file__).read_bytes()).hexdigest(),
                                python=platform.python_version(), jax=jax.__version__, numpy=np.__version__,
                                platform=platform.platform(), x64=bool(jax.config.jax_enable_x64)),
                  pairs=pairs, initial=initial.tolist(), frequencies=freqs.tolist(),
                  projection=dict(unit_interval_margin=1e-6, positive_floor=1e-12), tests={})

    def valid(points):
        p = np.asarray(jax.device_get(points))
        return bool(np.all(np.isfinite(p)) and np.all(p >= lower) and np.all(p <= upper))

    def record(name, function):
        started = time.perf_counter()
        try:
            value, points = function()
            value = jax.tree_util.tree_map(lambda x: np.asarray(x).tolist(), jax.device_get(value))
            numeric_blocks(value)
            if not valid(points):
                raise ValueError('trajectory left declared physical bounds')
            report['tests'][name] = dict(status='ok', seconds=time.perf_counter()-started,
                                         value=value, physical_domain_valid=True,
                                         parameter_points=np.asarray(jax.device_get(points)).tolist())
        except Exception as error:
            report['tests'][name] = dict(status='error', seconds=time.perf_counter()-started,
                                         error=f'{type(error).__name__}: {error}', trace=traceback.format_exc()[-1500:])
        print(name, report['tests'][name]['status'], flush=True)

    def descent():
        step = jax.jit(jax.value_and_grad(loss))
        p, history, gradients, points = params, [], [], [params]
        for _ in range(3):
            value, gradient = step(p)
            history.append(value)
            gradients.append(gradient)
            p = project(p - 1e-3 * scale * gradient / (jnp.linalg.norm(gradient) + 1e-300))
            points.append(p)
        return dict(losses=jnp.stack(history), gradients=jnp.stack(gradients), final=p), jnp.stack(points)

    record(TESTS[0], descent)
    batch = jnp.stack([params, project(params + 1e-3*scale*direction), project(params - 1e-3*scale*direction)])
    record(TESTS[1], lambda: (jax.jit(jax.vmap(jax.value_and_grad(loss)))(batch), batch))
    report['passed'] = all(record['status'] == 'ok' for record in report['tests'].values())
    with open(args.out, 'w') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    return 0 if report['passed'] else 1


def compare(args):
    reference, candidate = [json.loads(Path(path).read_text()) for path in (args.reference,args.candidate)]
    checks = []
    metadata_keys = ('setup', 'pairs', 'initial', 'frequencies', 'projection')
    issues = [f'{key} missing or different' for key in metadata_keys
              if key not in reference or reference[key] != candidate.get(key)]
    for label, receipt in [('reference', reference), ('candidate', candidate)]:
        if set(receipt.get('tests', {})) != set(TESTS):
            issues.append(f'{label}: incorrect bounded test inventory')
    for key in TESTS:
        a,b = reference.get('tests', {}).get(key,{}), candidate.get('tests', {}).get(key,{})
        row = dict(test=key,status='unavailable',passed=False,issues=[])
        if a.get('status') != 'ok' or b.get('status') != 'ok':
            row['issues'].append('reference or candidate unavailable')
        elif a.get('physical_domain_valid') is not True or b.get('physical_domain_valid') is not True:
            row['issues'].append('physical-domain check missing or failed')
        elif not all(validate_points(receipt.get('pairs', []), record.get('parameter_points'))
                     for receipt, record in ((reference,a),(candidate,b))):
            row['issues'].append('saved parameter points missing or outside declared bounds')
        else:
            row.update(compare_values(a.get('value'), b.get('value'), args.tolerance))
        checks.append(row)
    report = dict(passed=not issues and all(row['passed'] for row in checks), checks=checks, issues=issues,
                  tolerance=args.tolerance, scope='bounded Voyager trajectory agreement only')
    print(json.dumps(report,indent=2,allow_nan=False))
    if args.out:
        Path(args.out).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='cmd', required=True)
    r=sub.add_parser('run');r.add_argument('--tree',required=True);r.add_argument('--out',required=True)
    c=sub.add_parser('compare');c.add_argument('reference');c.add_argument('candidate');c.add_argument('--out')
    c.add_argument('--tolerance',type=float,default=1e-6)
    args=parser.parse_args()
    if args.cmd == 'compare' and (not math.isfinite(args.tolerance) or args.tolerance < 0):
        parser.error('tolerance must be finite and nonnegative')
    sys.exit(run(args) if args.cmd == 'run' else compare(args))
