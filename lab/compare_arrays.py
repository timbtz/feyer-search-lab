"""Conservative numerical regression comparison, additional to official validation."""
import argparse
import json
from pathlib import Path

import numpy as np


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
                'passed': passed, 'finite': finite, 'reference_scale': scale,
                'max_absolute_error': float(np.max(error)) if error.size and finite else None,
                'relative_l2_error': float(np.linalg.norm((a-b).ravel()) / max(np.linalg.norm(a.ravel()), np.finfo(float).tiny)) if finite else None,
                'exact_required': exact,
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
