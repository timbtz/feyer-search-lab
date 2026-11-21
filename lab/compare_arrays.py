"""Conservative numerical regression comparison, additional to official validation."""
import argparse
import json
from pathlib import Path

import numpy as np


def json_scalar(value):
    """Represent complex/non-finite diagnostics without invalid JSON numbers."""
    value = np.asarray(value).item()
    if isinstance(value, complex):
        return {'real': json_scalar(value.real), 'imag': json_scalar(value.imag)}
    return value if np.isfinite(value) else None


def failure_details(reference, candidate, error, tolerance, key):
    failed = (~np.isfinite(reference) | ~np.isfinite(candidate)
              | ~np.isfinite(error) | ~np.isfinite(tolerance) | (error > tolerance))
    flat_indices = np.flatnonzero(failed)
    limit = reference.size if key == 'gradient' else 20
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where(tolerance > 0, error / tolerance,
                         np.where(error == 0, 0.0, np.inf))
    details = []
    for flat_index in flat_indices[:limit]:
        index = np.unravel_index(flat_index, reference.shape)
        details.append({
            'index': [int(i) for i in index],
            'flat_index': int(flat_index),
            'reference': json_scalar(reference[index]),
            'candidate': json_scalar(candidate[index]),
            'absolute_error': json_scalar(error[index]),
            'tolerance': json_scalar(tolerance[index]),
            'normalized_error': json_scalar(ratio[index]),
            'normalized_error_is_infinite': bool(np.isinf(ratio[index])),
        })
    maximum = float(np.max(ratio)) if ratio.size else 0.0
    return {
        'failing_count': int(flat_indices.size),
        'failing_indices': [item['index'] for item in details],
        'failures': details,
        'failures_truncated': len(details) < flat_indices.size,
        'max_normalized_error': json_scalar(maximum),
        'max_normalized_error_is_infinite': bool(np.isinf(maximum)),
    }


def compare(reference, candidate, rtol=1e-7, scale_atol=1e-12):
    checks = {}
    with np.load(reference, allow_pickle=False) as expected, np.load(candidate, allow_pickle=False) as actual:
        if set(expected.files) != set(actual.files):
            raise ValueError('Saved array keys differ')
        for key in expected.files:
            a, b = expected[key], actual[key]
            if a.shape != b.shape or a.dtype != b.dtype:
                checks[key] = {'passed': False, 'reason': 'shape or dtype differs'}
                continue
            finite = bool(np.isfinite(a).all() and np.isfinite(b).all())
            scale = float(np.max(np.abs(a))) if a.size else 0.0
            error = np.abs(a - b)
            exact = key in ('parameters', 'frequencies')
            tolerance = np.zeros_like(error) if exact else scale_atol * scale + rtol * np.abs(a)
            passed = finite and bool(np.all(error <= tolerance))
            checks[key] = {
                'passed': passed, 'finite': finite, 'reference_scale': json_scalar(scale),
                'max_absolute_error': json_scalar(np.max(error)) if error.size and finite else None,
                'relative_l2_error': json_scalar(np.linalg.norm((a-b).ravel()) / max(np.linalg.norm(a.ravel()), np.finfo(float).tiny)) if finite else None,
                'exact_required': exact,
                **failure_details(a, b, error, tolerance, key),
            }
    return {'passed': all(c['passed'] for c in checks.values()), 'rtol': rtol,
            'scale_atol': scale_atol, 'checks': checks,
            'scope': 'Additional regression check; stricter than official challenge checks.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.reference, args.candidate)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
