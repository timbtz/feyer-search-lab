"""Fail-closed transfer evidence, separate from official and historical queue verdicts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

UPSTREAM = '83f8d2f40fc75218a1d8ec7908cc0bf1c8f99a75'
OUTPUTS = ('carrier', 'signal', 'noise', 'sensitivity', 'powers', 'loss', 'gradient')
INPUTS = ('parameters', 'frequencies')
PHASES = ('imports', 'initialize', 'load', 'build', 'forward_lower', 'forward_compile',
          'forward', 'sensitivity_lower', 'sensitivity_compile', 'sensitivity',
          'gradient_lower', 'gradient_compile', 'gradient', 'host_transfer')
THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')
WORKLOADS = {
    'grid': {'benchmark': 'start-munich-2026-public-differometor-uifo-v2', 'variables': 193,
             'tolerance': 1e-5, 'setup': 'ff4ba353a2a03cdce7f3e61bad729c2e00888d842c28ba9cf699f95afb87e138',
             'reference': '726f2cfe6986cb991fa48d5a28127b9330c3dc7e69d5bd193c8748acef03adc3'},
    'aligo': {'benchmark': 'start-munich-2026-public-differometor-aligo-v1', 'variables': 29,
              'tolerance': 1e-6, 'setup': 'f77fa86eeae1771a9aa3a9305c490a7ef406df6a542c3e93de303d3070536390',
              'reference': 'e3419da07888d0260800be08ba873dc22518de0b103582740cc447e0014c5cb4'},
}


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_number(value, positive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def audit_arrays(reference, candidate, *, sensitivity_tolerance=1e-5, include_loss=True):
    """Same inputs, precision and elementwise outputs; no norm-only gradient acceptance.

    These regression thresholds match the existing saved-array policy. They are
    additional review checks, not organizer-prescribed tolerances on every output.
    """
    required = set(OUTPUTS + INPUTS) - (set() if include_loss else {'loss'})
    issues, metrics = [], {}
    for side, values in [('reference', reference), ('candidate', candidate)]:
        missing = required - set(values)
        if missing:
            issues.append(f'{side}: missing arrays {sorted(missing)}')
    if issues:
        return {'passed': False, 'issues': issues, 'arrays': metrics}
    for key in sorted(required):
        a, b = np.asarray(reference[key]), np.asarray(candidate[key])
        dtype = np.dtype('complex128' if key in ('carrier', 'signal') else 'float64')
        if a.shape != b.shape or a.dtype != dtype or b.dtype != dtype or a.size == 0:
            issues.append(f'{key}: shape, double-precision dtype or nonempty requirement failed')
            continue
        if not (np.isfinite(a).all() and np.isfinite(b).all()):
            issues.append(f'{key}: non-finite reference or candidate')
            continue
        if key in INPUTS:
            if not np.array_equal(a, b):
                issues.append(f'{key}: input values differ')
            continue
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            error = np.abs(a - b)
            tolerance = 1e-12 * np.max(np.abs(a)) + 1e-7 * np.abs(a)
            failed = (~np.isfinite(error)) | (error > tolerance)
        metrics[key] = {'passed': not bool(failed.any()), 'failing_count': int(failed.sum())}
        if failed.any():
            issues.append(f'{key}: elementwise regression mismatch')
    for side, values in [('reference', reference), ('candidate', candidate)]:
        if not np.any(np.asarray(values['gradient']) != 0):
            issues.append(f'{side}: identically zero gradient')
        if not np.all(np.asarray(values['sensitivity']) > 0):
            issues.append(f'{side}: non-positive sensitivity')
    a, b = np.asarray(reference['sensitivity']), np.asarray(candidate['sensitivity'])
    if a.shape == b.shape and a.size and np.all(a > 0) and np.all(b > 0):
        with np.errstate(invalid='ignore'):
            log_error = float(np.max(np.abs(np.log(a) - np.log(b))))
        if not math.isfinite(log_error) or log_error > sensitivity_tolerance:
            issues.append('sensitivity: logarithmic tolerance exceeded')
        metrics['log_sensitivity_error'] = log_error if math.isfinite(log_error) else None
    return {'passed': not issues, 'issues': issues, 'arrays': metrics,
            'regression_policy': {'rtol': 1e-7, 'scale_atol': 1e-12,
                                  'sensitivity_log_tolerance': sensitivity_tolerance}}


def audit_archive(reference_path, candidate_path, expected_cases):
    """Re-audit gencheck archives without changing or overwriting historical results."""
    if not expected_cases or len(set(expected_cases)) != len(expected_cases):
        raise ValueError('An explicit nonempty unique case list is required')
    checks = []
    with np.load(reference_path, allow_pickle=False) as ref, np.load(candidate_path, allow_pickle=False) as cand:
        for case in expected_cases:
            prefix = case + '/'
            a = {k[len(prefix):]: ref[k] for k in ref.files if k.startswith(prefix)}
            b = {k[len(prefix):]: cand[k] for k in cand.files if k.startswith(prefix)}
            result = audit_arrays(a, b)
            result['case'] = case
            if 'error' in a or 'error' in b:
                result['passed'] = False
                result['issues'].append('Recorded execution error; incomplete case cannot pass')
            checks.append(result)
    return {'schema': 'feyer-transfer-array-audit-v1', 'passed': all(x['passed'] for x in checks),
            'cases': checks, 'reference_archive_sha256': file_digest(reference_path),
            'candidate_archive_sha256': file_digest(candidate_path),
            'scope': 'Additional strict review; not official PASS, no ranking or timing promotion.'}


def validate_official_report(report, *, setup, cpu, candidate_sha, harness_hashes):
    """Check the pinned upstream full report, including first-run accounting."""
    spec = WORKLOADS[setup]
    issues = []
    def require(ok, reason):
        if not ok:
            issues.append(reason)
    require(report.get('benchmark') == spec['benchmark'], 'Wrong benchmark identity')
    source = report.get('source', {})
    require(source.get('commit') == candidate_sha and source.get('modified') is False,
            'Wrong or dirty exact candidate source')
    entry = 'benchmark_aligo.py' if setup == 'aligo' else 'benchmark.py'
    require(report.get('starter_sha256') == harness_hashes[entry], 'Wrong benchmark entrypoint hash')
    require(report.get('benchmark_harness_sha256') == harness_hashes['benchmark.py'], 'Wrong shared harness hash')
    inputs = report.get('inputs', {})
    require(inputs.get('frequency_count') == 101 and inputs.get('gradient_parameter_count') == spec['variables'],
            'Incomplete official workload')
    require(inputs.get('setup_sha256') == spec['setup'] and inputs.get('reference_sha256') == spec['reference'],
            'Wrong optical setup or public reference')
    env = report.get('environment', {})
    require(env.get('cpu_affinity_ids') == [cpu] and type(env.get('cpu_affinity_count')) is int
            and env.get('cpu_affinity_count') == 1 and type(env.get('requested_logical_cpus')) is int
            and env.get('requested_logical_cpus') == 1, 'Not exactly one logical CPU')
    require(env.get('thread_limits') == dict.fromkeys(THREADS, '1'), 'Numerical library thread limits differ')
    require(env.get('backend') == 'cpu' and env.get('jax_enable_x64') is True
            and env.get('persistent_compilation_cache') is False, 'Wrong backend, precision or cache policy')
    phases = report.get('phases', [])
    require(isinstance(phases, list) and [p.get('key') for p in phases] == list(PHASES), 'Missing/reordered/duplicate first-run phases')
    total = report.get('timing_seconds', {}).get('end_to_end')
    valid_phases = isinstance(phases, list) and all(finite_number(p.get('seconds')) for p in phases)
    require(valid_phases and finite_number(total, True), 'Invalid timing values')
    if valid_phases and finite_number(total, True):
        require(math.isclose(sum(p['seconds'] for p in phases), total, rel_tol=1e-9, abs_tol=1e-9),
                'First-run total excludes or miscounts a phase')
        compile_total = sum(p['seconds'] for p in phases if p['key'].endswith(('_lower', '_compile')))
        recorded = report.get('timing_seconds', {}).get('trace_lower_and_compile')
        require(finite_number(recorded) and math.isclose(compile_total, recorded, rel_tol=1e-9, abs_tol=1e-9),
                'Compilation total mismatch')
    v = report.get('validation', {})
    require(v.get('all_outputs_and_gradients_finite') is True and v.get('upstream_sensitivity_check_passed') is True
            and v.get('gradient_check', {}).get('passed') is True, 'Official correctness checks did not pass')
    require(v.get('gradient_shape') == [spec['variables']] and finite_number(v.get('gradient_norm'), True),
            'Incomplete or zero gradient')
    require(type(v.get('loss')) in (float, int) and math.isfinite(v['loss']), 'Non-finite loss')
    error = v.get('max_absolute_log_sensitivity_error')
    require(v.get('sensitivity_log_atol') == spec['tolerance'] and finite_number(error)
            and error <= spec['tolerance'], 'Wrong official sensitivity tolerance or failure')
    require(v.get('output_dtypes') == {'carrier': 'complex128', 'signal': 'complex128', 'noise': 'float64'},
            'Physical outputs are not double precision')
    return {'passed': not issues, 'issues': issues, 'package_xla_flags': env.get('xla_flags'),
            'scope': 'Pinned official transfer benchmark; package compiler settings recorded, not blanket-rejected.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', required=True, type=Path)
    p.add_argument('--candidate', required=True, type=Path)
    p.add_argument('--cases', required=True, help='Explicit comma-separated gencheck case names')
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    result = audit_archive(a.reference, a.candidate, a.cases.split(','))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': result['passed'], 'output': str(a.output)}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
