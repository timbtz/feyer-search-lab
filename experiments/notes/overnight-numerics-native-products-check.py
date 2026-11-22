"""Small synthetic native-product inspection; no optical benchmark or timings.

Execute with an existing NumPy/SciPy environment. JAX is not required: extract
only the product, loader and unchanged refinement kernel from actual source.
"""
import ast
from decimal import Decimal, localcontext
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import tracemalloc

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'


def kernels(source):
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef))
             and n.name in ('_csr_matvecs', '_Products', '_solve')]
    namespace = dict(np=np, _CSR_MATVECS=None, REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual-kernels', 'exec'), namespace)
    return namespace


class Factor:
    def __init__(self, factor):
        self.factor = factor
        self.calls = 0

    def solve(self, rhs, trans):
        self.calls += 1
        return self.factor.solve(rhs, trans=trans)


def decimal_reference(real_matrix, rhs, precision=70):
    """Independent 70-digit elimination on the exact supplied binary64 inputs."""
    assert np.all(np.imag(real_matrix) == 0)
    rhs = np.asarray(rhs).reshape(len(real_matrix), -1)
    width = rhs.shape[1]
    with localcontext() as ctx:
        ctx.prec = precision
        rows = [[Decimal.from_float(float(v)) for v in row.real]
                + [Decimal.from_float(float(v)) for v in b.real]
                + [Decimal.from_float(float(v)) for v in b.imag]
                for row, b in zip(real_matrix, rhs)]
        size = len(rows)
        for col in range(size):
            pivot = max(range(col, size), key=lambda i: abs(rows[i][col]))
            rows[col], rows[pivot] = rows[pivot], rows[col]
            for i in range(col+1, size):
                scale = rows[i][col]/rows[col][col]
                for j in range(col+1, size+2*width):
                    rows[i][j] -= scale * rows[col][j]
                rows[i][col] = Decimal(0)
        solution = [[Decimal(0)]*(2*width) for _ in range(size)]
        for i in range(size-1, -1, -1):
            for j in range(2*width):
                solution[i][j] = (rows[i][size+j] - sum(
                    rows[i][k]*solution[k][j] for k in range(i+1,size)))/rows[i][i]
        return np.array([[complex(float(row[j]),float(row[j+width])) for j in range(width)]
                         for row in solution])


def main():
    parent = kernels(subprocess.check_output(['git', 'show', f'{PARENT}:differometor/host_pass.py'], cwd=ROOT, text=True))
    source = (ROOT / 'differometor/host_pass.py').read_text()
    candidate = kernels(source)
    # Exercise the cold direct loader before any scipy imports.
    assert not any(k == 'scipy' or k.startswith('scipy.') for k in sys.modules)
    native = candidate['_csr_matvecs']()
    assert native
    assert not any(k == 'scipy.sparse' or k.startswith('scipy.sparse.linalg') for k in sys.modules)
    from scipy.sparse import csc_matrix, _sparsetools
    from scipy.sparse.linalg import splu
    loaded = kernels(source)
    assert loaded['_csr_matvecs']() is _sparsetools.csr_matvecs
    fallback = kernels(source)
    fallback['_CSR_MATVECS'] = False
    rng = np.random.default_rng(202611220428)
    report = dict(products=0, solves=0, fallback_products=0, bitwise_different_products=0,
                  bitwise_different_solutions=0, changed_correction_counts=0,
                  max_product_scaled_error=0.0, max_solution_relative_difference=0.0,
                  max_backward_error_parent=0.0, max_backward_error_candidate=0.0,
                  correction_counts_parent={}, correction_counts_candidate={})
    matrices = []
    for size in (5, 13, 37):
        for density in (.1, .4):
            a = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
            a[rng.random(a.shape) > density] = 0
            a[np.diag_indices(size)] += size
            matrices.append(('ordinary', a))
            s = np.geomspace(1e-8, 1e8, size)
            matrices.append(('scaled', a * s[:, None] / s[None, :]))
    for size in (6, 9, 12):
        ix = np.arange(size)
        matrices.append(('hilbert', (1 / (1 + ix[:, None] + ix[None, :])).astype(complex)))
    categories = {}
    worst = None
    independent_cases = []
    for category, dense in matrices:
        csc = csc_matrix(dense)
        pattern = SimpleNamespace(size=len(dense), rows=csc.indices.copy(),
                                  cols=np.repeat(np.arange(len(dense)), np.diff(csc.indptr)))
        old = parent['_Products'](pattern)
        new = candidate['_Products'](pattern)
        generic = fallback['_Products'](pattern)
        for changed in (False, True):
            values = csc.data.copy()
            if changed:
                values *= 1 + .03 * (rng.normal(size=len(values)) + 1j*rng.normal(size=len(values)))
                values[(pattern.rows != pattern.cols) & (np.arange(len(values)) % 3 == 0)] = 0
            a = csc_matrix((values, csc.indices, csc.indptr), shape=csc.shape).toarray()
            lu = splu(csc_matrix(a))
            values_before = values.tobytes()
            for trans in ('N', 'T', 'H'):
                op = a if trans == 'N' else a.T if trans == 'T' else a.conj().T
                extended = op.astype(np.clongdouble)
                for width in (None, 1, 2, 5):
                    shape = (len(a),) if width is None else (len(a), width)
                    rhs = rng.normal(size=shape) + 1j*rng.normal(size=shape)
                    # Include noncontiguous multi-RHS inputs.
                    if width is not None:
                        rhs = np.asfortranarray(rhs)
                    before = rhs.tobytes()
                    expected, actual = old.apply(values, rhs, trans), new.apply(values, rhs, trans)
                    generic_result = generic.apply(values, rhs, trans)
                    assert generic_result.tobytes() == expected.tobytes()
                    exact_product = extended @ rhs.astype(np.clongdouble)
                    magnitude = np.abs(extended) @ np.abs(rhs.astype(np.clongdouble))
                    scaled_error = float(np.max(np.abs(actual - exact_product) / np.maximum(magnitude, 1e-300)))
                    assert scaled_error < 64*np.finfo(float).eps, (category, trans, width, scaled_error)
                    report['max_product_scaled_error'] = max(report['max_product_scaled_error'], scaled_error)
                    report['products'] += 1
                    report['fallback_products'] += 1
                    report['bitwise_different_products'] += expected.tobytes() != actual.tobytes()
                    f_old, f_new = Factor(lu), Factor(lu)
                    x_old = parent['_solve'](old, values, f_old, rhs, trans)
                    x_new = candidate['_solve'](new, values, f_new, rhs, trans)
                    assert np.all(np.isfinite(x_new))
                    difference = float(np.max(np.abs(x_new-x_old))/max(np.max(np.abs(x_old)), 1e-300))
                    if category == 'hilbert' and not changed and (worst is None or difference > worst[0]):
                        worst = difference, op.copy(), rhs.copy(), x_old.copy(), x_new.copy(), trans
                    report['max_solution_relative_difference'] = max(report['max_solution_relative_difference'], difference)
                    if category == 'hilbert' and not changed:
                        exact = decimal_reference(op, rhs)
                        stable = decimal_reference(op, rhs, precision=90)
                        assert exact.tobytes() == stable.tobytes()
                        independent_cases.append(dict(size=len(op), rhs_shape=list(rhs.shape), trans=trans,
                            parent_error=float(np.max(np.abs(x_old.reshape(exact.shape)-exact))/np.max(np.abs(exact))),
                            candidate_error=float(np.max(np.abs(x_new.reshape(exact.shape)-exact))/np.max(np.abs(exact)))))
                    report['bitwise_different_solutions'] += x_new.tobytes() != x_old.tobytes()
                    report['changed_correction_counts'] += f_new.calls != f_old.calls
                    report['solves'] += 1
                    stats = categories.setdefault(category, dict(max_solution_relative_difference=0.0,
                                                                 max_parent_error=0.0, max_candidate_error=0.0))
                    stats['max_solution_relative_difference'] = max(stats['max_solution_relative_difference'], difference)
                    for label, x, f in (('parent', x_old, f_old), ('candidate', x_new, f_new)):
                        x_ext, b_ext = x.astype(np.clongdouble), rhs.astype(np.clongdouble)
                        residual = b_ext - extended @ x_ext
                        scale = np.abs(extended) @ np.abs(x_ext) + np.abs(b_ext)
                        error = float(np.max(np.abs(residual)/np.maximum(scale, 1e-300)))
                        report[f'max_backward_error_{label}'] = max(report[f'max_backward_error_{label}'], error)
                        stats[f'max_{label}_error'] = max(stats[f'max_{label}_error'], error)
                        counts = report[f'correction_counts_{label}']
                        counts[f.calls-1] = counts.get(f.calls-1, 0)+1
                        assert error < 64*np.finfo(float).eps, (category, trans, width, label, error)
                    assert values.tobytes() == values_before and rhs.tobytes() == before
    # Empty rows/columns, completely empty patterns, structural zero entries and
    # non-finite inputs must stay present in both native and fallback operations.
    for rows, cols in (([1,3,1,5], [0,0,4,6]), ([], [])):
        pattern = SimpleNamespace(size=7, rows=np.array(rows, dtype=int), cols=np.array(cols, dtype=int))
        old, new = parent['_Products'](pattern), candidate['_Products'](pattern)
        for trans in ('N','T','H'):
            for width in (1,3):
                for nonfinite in (False, True):
                    values = np.array([0, 2j, -3, 1+4j][:len(rows)], dtype=complex)
                    x = np.ones((7,width), dtype=complex)
                    if nonfinite:
                        x[1] = np.nan
                        x[4] = np.inf
                    with np.errstate(invalid='ignore'):
                        a, b = old.apply(values,x,trans), new.apply(values,x,trans)
                    assert np.array_equal(a,b,equal_nan=True)
    # Inspect allocation only, not timing. The CSR layout and import overhead are
    # deliberately outside this per-product peak measurement and still count in
    # a future complete official run.
    size, degree, width = 127, 9, 3
    csc = csc_matrix((rng.normal(size=size*degree).astype(complex),
                      (np.tile(np.arange(degree),size), np.repeat(np.arange(size),degree))), shape=(size,size))
    pattern = SimpleNamespace(size=size, rows=csc.indices, cols=np.repeat(np.arange(size),np.diff(csc.indptr)))
    x = rng.normal(size=(size,width)).astype(complex)
    peaks = []
    for k in (parent, candidate):
        p = k['_Products'](pattern)
        tracemalloc.start()
        p.apply(csc.data,x)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
    difference, op, rhs, x_old, x_new, trans = worst
    exact = decimal_reference(op, rhs)
    report['worst_unperturbed_hilbert'] = dict(size=len(op), rhs_shape=list(rhs.shape), trans=trans,
        parent_candidate_relative_difference=difference,
        parent_relative_forward_error=float(np.max(np.abs(x_old.reshape(exact.shape)-exact))/np.max(np.abs(exact))),
        candidate_relative_forward_error=float(np.max(np.abs(x_new.reshape(exact.shape)-exact))/np.max(np.abs(exact))),
        reference='70-digit Decimal elimination on the exact binary64 A and rhs')
    report['independent_hilbert_summary'] = dict(count=len(independent_cases),
        reference='70-digit Decimal; binary64 result unchanged at 90 digits for every case',
        parent_worst_error=max(c['parent_error'] for c in independent_cases),
        candidate_worst_error=max(c['candidate_error'] for c in independent_cases),
        candidate_more_accurate=sum(c['candidate_error'] < c['parent_error'] for c in independent_cases),
        candidate_less_accurate=sum(c['candidate_error'] > c['parent_error'] for c in independent_cases))
    report['independent_hilbert_cases'] = independent_cases
    report['categories'] = categories
    report['allocation_peak_bytes_parent_candidate'] = peaks
    report['extended_precision_bits'] = np.finfo(np.longdouble).nmant
    report['residual_check_scope'] = ('Local dense residual and product checks have no extra precision '
        'when extended_precision_bits is 52; only the separate Decimal checks are independent high precision.')
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
