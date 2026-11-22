"""Small SuperLU stopping-rule inspection; no optical fixtures or timings.

Extracts actual host kernels without importing JAX (unavailable locally).
An unrelated, exactly solved large RHS is added to a difficult small system.
Decimal elimination provides a reference for the exact supplied float inputs.
"""
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def decimal_solve(matrix, rhs, precision=80):
    with localcontext() as ctx:
        ctx.prec = precision
        a = [[Decimal.from_float(float(x)) for x in row] for row in matrix]
        b = [Decimal.from_float(float(x)) for x in rhs]
        n = len(b)
        for k in range(n):
            pivot = max(range(k, n), key=lambda i: abs(a[i][k]))
            a[k], a[pivot] = a[pivot], a[k]
            b[k], b[pivot] = b[pivot], b[k]
            for i in range(k + 1, n):
                m = a[i][k] / a[k][k]
                for j in range(k + 1, n):
                    a[i][j] -= m * a[k][j]
                b[i] -= m * b[k]
                a[i][k] = Decimal(0)
        x = [Decimal(0)] * n
        for i in reversed(range(n)):
            x[i] = (b[i] - sum(a[i][j] * x[j] for j in range(i + 1, n))) / a[i][i]
        return np.array([float(v) for v in x])


def kernels():
    path = ROOT / 'experiments/notes/overnight-numerics-pattern-snapshot-check.py'
    spec = importlib.util.spec_from_file_location('snapshot_check', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load((ROOT / 'differometor/sparse.py').read_text())


def steps(products, values, factor, rhs, trans):
    x = factor.solve(np.asarray(rhs, dtype=complex), trans=trans)
    result = []
    for _ in range(3):
        correction = factor.solve(np.ascontiguousarray(rhs - products.apply(values, x, trans)), trans=trans)
        x = x + correction
        scale = np.max(np.abs(x), axis=0)
        change = np.max(np.abs(correction), axis=0)
        result.append((x.copy(), bool(np.max(change) <= 1e-14 * np.max(scale)),
                       bool(np.all(change <= 1e-14 * scale)), (change / np.maximum(scale, 1e-300)).tolist()))
    return result


def main():
    ns = kernels()
    rng = np.random.default_rng(2026112252)
    masked = improved = worsened = unchanged = 0
    example = None
    worst_regression = None
    max_old_error = max_new_error = 0.
    max_old_backward = max_new_backward = 0.
    for sample in range(120):
        block = rng.normal(size=(4, 4))
        # A nearly dependent row, with independent row/column scaling.
        block[3] = block[0] + block[1] + 10. ** (-6 - sample % 5) * block[3]
        block *= np.geomspace(1e-2, 1e2, 4)[:, None]
        block *= np.geomspace(1e2, 1e-2, 4)[None, :]
        a = np.zeros((5, 5))
        a[0, 0], a[1:, 1:] = 1., block
        cols, rows = np.nonzero(a.T)
        pattern = ns['SparsePattern'](rows, cols, 5)
        values = a[rows, cols].astype(complex)
        factor = ns['_factor'](pattern, values)
        products = ns['_Products'](pattern)
        for trans in ('N', 'T', 'H'):
            op = a if trans == 'N' else a.T
            small = op @ rng.normal(size=5)
            small[0] = 0
            rhs = np.column_stack((np.array([1e20, 0, 0, 0, 0]), small)).astype(complex)
            trace = steps(products, values, factor, rhs, trans)
            if not trace[0][1] or trace[0][2]:
                continue
            masked += 1
            ref = decimal_solve(op, small)
            np.testing.assert_array_equal(ref, decimal_solve(op, small, 110))
            old = trace[0][0][:, 1].real
            chosen = next((t for t in trace if t[2]), trace[-1])
            new = chosen[0][:, 1].real
            old_error = float(np.max(np.abs(old - ref)))
            new_error = float(np.max(np.abs(new - ref)))
            max_old_error = max(max_old_error, old_error)
            max_new_error = max(max_new_error, new_error)
            def backward_error(x):
                # Double residual, reported separately from the Decimal error.
                return float(np.max(np.abs(op @ x - small)) /
                             (np.linalg.norm(op, np.inf) * np.max(np.abs(x)) + np.max(np.abs(small))))
            old_backward, new_backward = backward_error(old), backward_error(new)
            max_old_backward = max(max_old_backward, old_backward)
            max_new_backward = max(max_new_backward, new_backward)
            improved += new_error < old_error
            worsened += new_error > old_error
            unchanged += new_error == old_error
            if new_error > old_error and (worst_regression is None or
                                         new_error - old_error > worst_regression['error_increase']):
                worst_regression = dict(sample=sample, trans=trans, matrix=a.tolist(),
                                        small_rhs=small.tolist(), old_max_error=old_error,
                                        new_max_error=new_error, error_increase=new_error - old_error,
                                        old_backward_error=old_backward, new_backward_error=new_backward,
                                        corrections_relative=[t[3] for t in trace])
            if example is None and new_error < old_error / 3 and old_error > 1e-8:
                example = dict(sample=sample, trans=trans, matrix=a.tolist(), small_rhs=small.tolist(),
                               old_max_error=old_error, new_max_error=new_error,
                               corrections_relative=[t[3] for t in trace],
                               old_solution=old.tolist(), new_solution=new.tolist(), reference=ref.tolist())
    result = dict(parent_sha='534570265891b5782b8b55ef10b5b06eb778d1c3',
                  host_pass_sha256=hashlib.sha256((ROOT / 'differometor/host_pass.py').read_bytes()).hexdigest(),
                  numpy_version=np.__version__, systems=120, solves=360, masked=masked,
                  decimal_80_110_float64_reference_agreements=masked,
                  improved=improved, worsened=worsened, unchanged=unchanged, example=example,
                  worst_regression=worst_regression, maximum_old_absolute_error=max_old_error,
                  maximum_new_absolute_error=max_new_error,
                  maximum_old_normwise_double_residual=max_old_backward,
                  maximum_new_normwise_double_residual=max_new_backward,
                  decision='Reject per-column stopping alone; production solver unchanged.',
                  scope='Small synthetic SuperLU inspection; Decimal 80-digit real reference; no timings')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
