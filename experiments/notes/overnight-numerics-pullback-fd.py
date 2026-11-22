"""Small component pullback finite differences; no optical workload or timing.

The oracle evaluates primal component formulas only. It does not use Dual
derivatives or function_jacobian. This checks first derivatives of the real
linear objective Re(sum(output * cotangent)), including imaginary directions.
It does not resolve the full-system finite-difference questions.
"""
from pathlib import Path
import runpy

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
loader = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
ns, _ = loader['load']((ROOT / 'differometor/components.py').read_text())
rng = np.random.default_rng(2026112205)
records = []
for function_index, function in enumerate(ns['HOST_FUNCTIONS']):
    errors = []
    for sample in range(3):
        # Interior points avoid singular zero-frequency/mass and square-root
        # endpoints. Complex perturbations also exercise conjugate derivatives.
        point = rng.uniform(.2, .7, 7).astype(np.complex128)
        point[4:6] += 1
        if sample:
            point += .01j * rng.normal(size=7)
        primal = ns['evaluate_function'](function_index, point)
        cotangent = rng.normal(size=4) + 1j * rng.normal(size=4)
        cotangent /= max(1e-30, float(np.max(np.abs(primal))))
        pullback = ns['function_pullback'](function_index, tuple(range(7)), point, cotangent)
        for slot in range(7):
            for direction in (1.0, 1.0j):
                expected = float(np.real(pullback[slot] * direction))
                # Require both step sizes to pass; do not select the best step.
                for step in (1e-5, 5e-6):
                    plus, minus = point.copy(), point.copy()
                    plus[slot] += step * direction
                    minus[slot] -= step * direction
                    delta = (ns['evaluate_function'](function_index, plus)
                             - ns['evaluate_function'](function_index, minus)) / (2 * step)
                    observed = float(np.real(np.sum(delta * cotangent)))
                    error = abs(observed - expected) / max(1.0, abs(expected))
                    assert np.isfinite(error) and error < 2e-7, (
                        function.__name__, sample, slot, direction, step, expected, observed, error)
                    errors.append(error)
    records.append((function.__name__, len(errors), max(errors)))
print({'functions': len(records), 'direction_step_checks': sum(r[1] for r in records),
       'max_scaled_error': max(r[2] for r in records), 'per_function': records,
       'scope': 'synthetic component finite differences, not full-system validation'})
