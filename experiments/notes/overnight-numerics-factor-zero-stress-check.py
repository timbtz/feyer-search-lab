"""Exact-zero compaction on the preserved panel-stress cases; no optical timings.

Run with an existing NumPy/SciPy environment. Extract the actual factor and
refinement kernels without importing JAX. Parent is the exact guard repair35.
"""
import ast
from decimal import Decimal, localcontext
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
PARENT = '7a9480332bad29b5aaeacc5a4628481581507e7a'
NAMES = {'_construct_csc', '_superlu_gstrf', '_factor', '_Products', '_solve'}


def load(source, fallback=False):
    nodes = []
    for node in ast.parse(source).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in NAMES:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == '_SUPERLU_OPTIONS' for t in node.targets
        ):
            nodes.append(node)
    ns = dict(np=np, _GSTRF=False if fallback else None,
              _scipy=lambda: (splu, csc_matrix),
              REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'panel-kernels', 'exec'), ns)
    return ns


class CountingFactor:
    def __init__(self, factor):
        self.factor, self.calls = factor, 0

    def solve(self, rhs, trans):
        self.calls += 1
        return self.factor.solve(rhs, trans=trans)


def bits(a, b):
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def decimal_solve(matrix, rhs, precision):
    """Independent real-block Gaussian elimination with partial pivoting.

    Decimal inputs are exact conversions of the supplied binary64 coefficients
    and RHS. This solves the rounded linear system, not the pre-rounding known x.
    """
    n = matrix.shape[0]
    block = np.block([[matrix.real, -matrix.imag], [matrix.imag, matrix.real]])
    rhs = rhs.reshape(n)
    target = np.concatenate([rhs.real, rhs.imag])
    with localcontext() as ctx:
        ctx.prec = precision
        rows = [[Decimal.from_float(float(x)) for x in row] +
                [Decimal.from_float(float(b))] for row, b in zip(block, target)]
        m = len(rows)
        for col in range(m):
            pivot = max(range(col, m), key=lambda r: abs(rows[r][col]))
            rows[col], rows[pivot] = rows[pivot], rows[col]
            assert rows[col][col] != 0
            for r in range(col + 1, m):
                if not rows[r][col]:
                    continue
                scale = rows[r][col] / rows[col][col]
                for c in range(col + 1, m + 1):
                    rows[r][c] -= scale * rows[col][c]
                rows[r][col] = Decimal(0)
        result = [Decimal(0)] * m
        for r in range(m - 1, -1, -1):
            result[r] = (rows[r][m] - sum(rows[r][c]*result[c]
                         for c in range(r + 1, m))) / rows[r][r]
        return np.array([complex(float(result[r]), float(result[n+r])) for r in range(n)])


def run():
    parent = subprocess.check_output(
        ['git', 'show', PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True)
    source = (ROOT / 'differometor/host_pass.py').read_text()
    old, new, fallback = load(parent), load(source), load(source, fallback=True)
    assert old['_SUPERLU_OPTIONS']['PanelSize'] is None
    assert new['_SUPERLU_OPTIONS']['PanelSize'] is None
    rng = np.random.default_rng(2026112239)
    report = dict(matrices=0, solves=0, factor_bit_differences=0,
                  permutation_differences=0, refined_bit_differences=0,
                  correction_count_differences=0, fallback_bit_differences=0,
                  max_scaled_solution_difference=0., max_backward_error=0.,
                  max_known_solution_error=0., agreement_failures=[], worst_case=None,
                  decimal_diagnostics=[], parent_max_backward_error=0.)
    for n in (2, 3, 7, 8, 9, 17, 31, 65):
        for kind in ('sparse', 'scaled', 'triangular', 'explicit_zero'):
            for trial in range(3):
                raw = rng.normal(size=(n, n)) + 1j*rng.normal(size=(n, n))
                mask = rng.random((n, n)) < .12
                raw *= mask
                a = raw + np.diag(2 + np.sum(np.abs(raw), axis=1))
                if kind == 'scaled':
                    scale = np.geomspace(1e-6, 1e6, n)
                    a *= scale[:, None] / scale[None, :]
                elif kind == 'triangular':
                    a = np.triu(raw) * .05
                    a[np.diag_indices(n)] = np.geomspace(1., 1e-12, n) * (1 + .3j)
                    # Deliberately extreme triangular stress: tiny diagonal
                    # entries and off-diagonal chains may cause large inverse growth.
                    a *= np.geomspace(1., 1e-12, n)[None, :]
                if kind == 'explicit_zero':
                    # Keep the supplied structural zeros in the CSC pattern.
                    coords = mask | np.eye(n, dtype=bool)
                    rr, cc = np.nonzero(coords)
                    data = a[rr, cc].copy()
                    data[(rr != cc) & (np.arange(data.size) % 3 == 0)] = 0
                    matrix = csc_matrix((data, (rr, cc)), shape=(n, n))
                    a = matrix.toarray()
                else:
                    matrix = csc_matrix(a)
                pattern = SimpleNamespace(size=n, rows=matrix.indices,
                    indices=matrix.indices, indptr=matrix.indptr,
                    cols=np.repeat(np.arange(n), np.diff(matrix.indptr)))
                data = matrix.data.copy()
                factors = [ns['_factor'](pattern, data) for ns in (old, new, fallback)]
                assert bits(data, matrix.data), 'factorization mutated coefficients'
                report['matrices'] += 1
                for attr in ('perm_r', 'perm_c'):
                    report['permutation_differences'] += not bits(
                        getattr(factors[0], attr), getattr(factors[1], attr))
                for attr in ('L', 'U'):
                    left, right = getattr(factors[0], attr), getattr(factors[1], attr)
                    report['factor_bit_differences'] += not all(bits(getattr(left, k), getattr(right, k))
                        for k in ('data', 'indices', 'indptr'))
                products = old['_Products'](pattern)
                for trans in ('N', 'T', 'H'):
                    op = a if trans == 'N' else a.T if trans == 'T' else a.conj().T
                    for width in (0, 1, 3):
                        shape = (n,) if width == 0 else (n, width)
                        known = rng.normal(size=shape) + 1j*rng.normal(size=shape)
                        rhs = op @ known
                        saved = rhs.copy()
                        wrappers = [CountingFactor(f) for f in factors]
                        results = [ns['_solve'](products, data, f, rhs, trans)
                            for ns, f in zip((old, new, fallback), wrappers)]
                        assert bits(rhs, saved), 'solve mutated right-hand side'
                        assert all(np.all(np.isfinite(x)) for x in results)
                        report['solves'] += 1
                        report['refined_bit_differences'] += not bits(results[0], results[1])
                        report['fallback_bit_differences'] += not bits(results[1], results[2])
                        report['correction_count_differences'] += wrappers[0].calls != wrappers[1].calls
                        scale = max(np.max(np.abs(results[0])), np.finfo(float).tiny)
                        difference = float(np.max(np.abs(results[0] - results[1])) / scale)
                        if difference > report['max_scaled_solution_difference']:
                            report['max_scaled_solution_difference'] = difference
                            report['worst_case'] = [n, kind, trial, trans, width]
                        denominator = np.abs(op) @ np.abs(results[1]) + np.abs(rhs)
                        residual = np.abs(rhs - op @ results[1])
                        backward = np.max(residual / np.maximum(denominator, np.finfo(float).tiny))
                        report['max_backward_error'] = max(report['max_backward_error'], float(backward))
                        parent_denominator = np.abs(op) @ np.abs(results[0]) + np.abs(rhs)
                        parent_error = np.max(np.abs(rhs - op @ results[0]) /
                            np.maximum(parent_denominator, np.finfo(float).tiny))
                        report['parent_max_backward_error'] = max(report['parent_max_backward_error'], float(parent_error))
                        if ((kind == 'scaled' and n in (31, 65) and width == 0) or
                            (n, kind, trial, trans, width) == (65, 'triangular', 1, 'T', 1)):
                            ref = decimal_solve(op, rhs, 100)
                            ref_more = decimal_solve(op, rhs, 160)
                            assert bits(ref, ref_more), 'Decimal precision did not stabilize'
                            ref_scale = np.max(np.abs(ref))
                            report['decimal_diagnostics'].append(dict(
                                case=[n, kind, trial, trans, width],
                                parent_relative_max_error=float(np.max(np.abs(results[0].reshape(n)-ref))/ref_scale),
                                candidate_relative_max_error=float(np.max(np.abs(results[1].reshape(n)-ref))/ref_scale),
                                reference_max_abs=float(ref_scale),
                                precision_agrees=[100, 160]))
                        report['max_known_solution_error'] = max(report['max_known_solution_error'],
                            float(np.max(np.abs(results[1] - known)) / np.max(np.abs(known))))
                        if not np.allclose(results[1], results[0], rtol=1e-12, atol=1e-14*scale):
                            report['agreement_failures'].append([n, kind, trial, trans, width, difference])
                        assert bits(results[1], results[2]), 'direct/fallback disagreement'
    report['agreement_passed'] = not report['agreement_failures']
    report['agreement_criterion'] = dict(rtol=1e-12, atol_parent_max_scale=1e-14)
    path = ROOT / 'experiments/notes/overnight-numerics-factor-zero-stress-result.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    summary = dict(report)
    summary['agreement_failures'] = len(report['agreement_failures'])
    cases = [r for r in report['decimal_diagnostics'] if r['case'][1] == 'scaled']
    summary['decimal_diagnostics'] = dict(
        scaled_cases=len(cases),
        candidate_closer=sum(r['candidate_relative_max_error'] < r['parent_relative_max_error'] for r in cases),
        candidate_farther=sum(r['candidate_relative_max_error'] > r['parent_relative_max_error'] for r in cases),
        parent_worst=max(r['parent_relative_max_error'] for r in cases),
        candidate_worst=max(r['candidate_relative_max_error'] for r in cases),
        triangular=report['decimal_diagnostics'][-1])
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    run()
