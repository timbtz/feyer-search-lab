"""Small structural diagonal-row solve checks; no fixtures or timing runs."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
PARENT = '534570265891b5782b8b55ef10b5b06eb778d1c3'


def load(source):
    ns = dict(np=np, hashlib=hashlib, _GSTRF=None, _ISOLATED_DIAGONALS={}, _ROOT_ROWS={},
              REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14,
              _scipy=lambda: (splu, csc_matrix))
    for text, wanted in (((ROOT / 'differometor/sparse.py').read_text(), {'SparsePattern'}),
                         (source, {'_IsolatedDiagonalPlan', '_IsolatedDiagonalFactor', '_RootRows', '_RootFactor', '_factor_full', '_factor',
                                   '_Products', '_solve', '_superlu_gstrf', '_construct_csc'})):
        nodes = [n for n in ast.parse(text).body
                 if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in wanted
                 or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_SUPERLU_OPTIONS'
                                                     for t in n.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'source-kernels', 'exec'), ns)
    return ns


def main():
    source = (ROOT / 'differometor/host_pass.py').read_text()
    parent = subprocess.check_output(['git', 'show', PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True)
    old, new = load(parent), load(source)
    row_only_variant = '_RootRows' in source  # Reproduce the preserved rejected patch too.
    rng = np.random.default_rng(2026112253)
    checks = matrices = unchanged_pattern = 0
    max_parent_difference = max_dense_error = max_backward_error = 0.
    factor_sizes = []
    for size in (1, 4, 9):
      for root_count in sorted({0, 1, size // 2, size}):
       for complex_values in (False, True):
        for scaling in ('none', 'rows', 'columns'):
         for zeros in (False, True):
          roots = rng.choice(size, root_count, replace=False)
          mask = np.ones((size, size), bool)
          mask[roots] = False
          if zeros and not row_only_variant:
              mask[:, roots] = False
          mask[roots, roots] = True
          cols, rows = np.nonzero(mask.T)
          p = new['SparsePattern'](rows, cols, size)
          a = .1 * rng.normal(size=(size, size))
          if complex_values:
              a = a + .1j * rng.normal(size=(size, size))
          a[~mask] = 0
          a[np.diag_indices(size)] += 3
          offdiag = rows != cols
          if zeros and offdiag.any():
              a[rows[offdiag][0], cols[offdiag][0]] = 0
          scales = np.geomspace(1e-6, 1e6, size)
          if scaling == 'rows':
              a = a * scales[:, None]
          elif scaling == 'columns':
              a = a * scales[None, :]
          values = a[rows, cols].astype(complex)
          before_values, before_rows = values.copy(), p.rows.copy()
          f_old, f_new = old['_factor'](p, values), new['_factor'](p, values)
          again = new['_factor'](p, values)
          assert again is not f_new
          plan = new['_ROOT_ROWS' if row_only_variant else '_ISOLATED_DIAGONALS'][p]
          if plan.roots.size:
              factor_sizes.append([size, int(plan.core.size)])
              if plan.core.size:
                  assert again.core_factor is not f_new.core_factor
                  assert f_new.core_factor.shape == (plan.core.size, plan.core.size)
          for trans in ('N', 'T', 'H'):
           operator = a if trans == 'N' else a.T if trans == 'T' else a.conj().T
           for columns in (None, 1, 3):
            shape = (size,) if columns is None else (size, columns)
            rhs = rng.normal(size=shape) + .1j * rng.normal(size=shape)
            expected = old['_solve'](old['_Products'](p), values, f_old, rhs, trans)
            actual = new['_solve'](new['_Products'](p), values, f_new, rhs, trans)
            assert np.all(np.isfinite(actual))
            scale = max(float(np.max(np.abs(expected))), 1e-300)
            error = float(np.max(np.abs(actual - expected))) / scale
            max_parent_difference = max(max_parent_difference, error)
            np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12 * scale)
            reference = np.linalg.solve(operator, rhs)
            dense_scale = max(float(np.max(np.abs(reference))), 1e-300)
            max_dense_error = max(max_dense_error, float(np.max(np.abs(actual-reference))) / dense_scale)
            np.testing.assert_allclose(actual, reference, rtol=1e-10, atol=1e-12 * dense_scale)
            residual = np.max(np.abs(operator @ actual - rhs))
            denom = np.linalg.norm(operator, np.inf) * np.max(np.abs(actual)) + np.max(np.abs(rhs))
            max_backward_error = max(max_backward_error, float(residual / denom))
            if not plan.roots.size:
                assert actual.tobytes() == expected.tobytes()
                unchanged_pattern += 1
            checks += 1
          np.testing.assert_array_equal(values, before_values)
          np.testing.assert_array_equal(p.rows, before_rows)
          matrices += 1
    fallback_checks = 0
    if not row_only_variant:
        p = new['SparsePattern']([0, 1, 1, 2], [0, 0, 1, 2], 3)
        values = np.array([2., 0., 3., 4.], complex)
        factor = new['_factor'](p, values)
        # The zero-valued off-diagonal still prevents coordinate0 elimination.
        assert factor.plan.roots.tolist() == [2]
        baseline = factor.solve(np.ones(3, complex))
        values[-1] = 5.
        np.testing.assert_array_equal(factor.solve(np.ones(3, complex)), baseline)
        assert new['_factor'](p, values).solve(np.ones(3, complex))[-1] == .2
        for invalid in (0., np.nan, np.inf):
            values[-1] = invalid
            called = []
            full = new['_factor_full']
            def recorded(pattern, data):
                called.append(pattern is p)
                return full(pattern, data)
            new['_factor_full'] = recorded
            try:
                new['_factor'](p, values)
            except RuntimeError:
                pass  # Full SuperLU owns singular/nonfinite failure handling.
            finally:
                new['_factor_full'] = full
            assert called == [True]
            fallback_checks += 1
    print(json.dumps(dict(parent=PARENT, host_pass_sha256=hashlib.sha256(source.encode()).hexdigest(),
                         matrices=matrices, refined_solve_checks=checks,
                         no_root_bitwise_checks=unchanged_pattern,
                         invalid_diagonal_full_factor_fallbacks=fallback_checks,
                         maximum_parent_scaled_difference=max_parent_difference,
                         maximum_dense_scaled_difference=max_dense_error,
                         maximum_normwise_double_residual=max_backward_error,
                         distinct_factor_size_reductions=sorted(set(map(tuple, factor_sizes))),
                         scope='Small synthetic source kernels, no JAX/optical workload/timings'), indent=2))


if __name__ == '__main__':
    main()
