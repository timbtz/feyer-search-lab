"""Small coordinate-ownership checks using actual source kernels; no timings.

JAX is unavailable locally. AST extraction omits imports/decorators, not solver
code. This checks SparsePattern and the host refined solves, not JAX tracing.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
PARENT = "253a1362a6890685b10602608a5f39f58c9292b1"


def load(sparse_source):
    ns = dict(np=np, hashlib=hashlib, REFINEMENT_STEPS=3,
              REFINEMENT_TOLERANCE=1e-14, _GSTRF=None,
              _scipy=lambda: (splu, csc_matrix))
    host_source = (ROOT / "differometor/host_pass.py").read_text()
    wanted = {"_Products", "_solve", "_factor", "_superlu_gstrf", "_construct_csc"}
    for source, names in ((sparse_source, {"SparsePattern"}), (host_source, wanted)):
        nodes = [n for n in ast.parse(source).body
                 if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names
                 or isinstance(n, ast.Assign) and any(
                     isinstance(t, ast.Name) and t.id == "_SUPERLU_OPTIONS" for t in n.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "source-kernels", "exec"), ns)
    return ns


def exact(left, right):
    assert np.all(np.isfinite(left)) and np.all(np.isfinite(right))
    assert left.shape == right.shape and left.dtype == right.dtype
    assert left.tobytes() == right.tobytes()


def buffers(data, strided, dtype):
    result = np.empty(data.size * (2 if strided else 1), dtype=dtype)
    view = result[::2] if strided else result
    view[:] = data
    return view


def dense(pattern, values):
    result = np.zeros((pattern.size, pattern.size), complex)
    result[pattern.rows, pattern.cols] = values
    return result


def main():
    old_source = subprocess.check_output(
        ["git", "show", PARENT + ":differometor/sparse.py"], cwd=ROOT, text=True)
    source = (ROOT / "differometor/sparse.py").read_text()
    old, new = load(old_source), load(source)
    reproduction = []
    for ns in (old, new):
        rows, cols = np.array([0, 1, 1, 2, 2]), np.array([0, 0, 1, 1, 2])
        values = np.array([2, .25, 3, .5, 4], complex)
        pattern = ns["SparsePattern"](rows, cols, 3)
        matrix = dense(pattern, values)
        factor = ns["_factor"](pattern, values)
        rhs = np.ones(3, complex)
        before = ns["_solve"](ns["_Products"](pattern), values, factor, rhs, "N")
        key = pattern._key
        rows[1] = 2
        after = ns["_solve"](ns["_Products"](pattern), values, factor, rhs, "N")
        reproduction.append(dict(key_unchanged=key == pattern._key,
                                 residual=float(np.max(np.abs(matrix @ after - rhs))),
                                 solution_change=float(np.max(np.abs(after - before)))))
    assert reproduction[0]["residual"] == .125
    assert reproduction[1]["solution_change"] == 0

    rng = np.random.default_rng(2026112249)
    cases = solves = 0
    max_backward_error = 0.
    copied_bytes = 0
    for size in (3, 5, 9):
      # Lower and upper triangular coordinates have the same number of entries,
      # but changing between them changes both row and column index buffers.
      cols, rows = np.nonzero(np.triu(np.ones((size, size), bool)))
      other_cols, other_rows = np.nonzero(np.tril(np.ones((size, size), bool)))
      for dtype in (np.int32, np.int64):
       for strided in (False, True):
        for scaled in (False, True):
         source_rows, source_cols = buffers(rows, strided, dtype), buffers(cols, strided, dtype)
         parent = old["SparsePattern"](source_rows.copy(), source_cols.copy(), size)
         pattern = new["SparsePattern"](source_rows, source_cols, size)
         assert parent._key == pattern._key
         assert not np.shares_memory(source_rows, pattern.rows)
         assert not np.shares_memory(source_cols, pattern.cols)
         assert not pattern.rows.flags.writeable and not pattern.cols.flags.writeable
         assert source_rows.flags.writeable and source_cols.flags.writeable
         values = (.01 * (rng.normal(size=rows.size) + 1j * rng.normal(size=rows.size)))
         values[rows == cols] = 2. + .1j
         # Row scaling preserves triangular nonsingularity; dynamic range 1e16.
         if scaled:
             values *= np.geomspace(1e-8, 1e8, size)[rows]
         matrix = dense(parent, values)
         parent_factor = old["_factor"](parent, values)
         factor = new["_factor"](pattern, values)
         cached_products = new["_Products"](pattern)
         source_rows[:] = other_rows
         source_cols[:] = other_cols
         exact(pattern.rows, parent.rows)
         exact(pattern.cols, parent.cols)
         assert pattern._key == parent._key
         rebuilt = new["SparsePattern"](source_rows, source_cols, size)
         rebuilt_parent = old["SparsePattern"](source_rows.copy(), source_cols.copy(), size)
         assert rebuilt._key == rebuilt_parent._key and rebuilt._key != pattern._key
         exact(rebuilt.indices, rebuilt_parent.indices)
         exact(rebuilt.indptr, rebuilt_parent.indptr)
         for trans in ("N", "T", "H"):
          operator = matrix if trans == "N" else matrix.T if trans == "T" else matrix.conj().T
          for columns in (None, 1, 3):
           shape = (size,) if columns is None else (size, columns)
           rhs = rng.normal(size=shape) + 1j * rng.normal(size=shape)
           baseline = old["_solve"](old["_Products"](parent), values, parent_factor, rhs, trans)
           for products in (cached_products, new["_Products"](pattern)):
               actual = new["_solve"](products, values, factor, rhs, trans)
               exact(baseline, actual)
               residual = np.max(np.abs(operator @ actual - rhs))
               denominator = np.linalg.norm(operator, np.inf) * np.max(np.abs(actual)) + np.max(np.abs(rhs))
               backward_error = float(residual / denominator)
               max_backward_error = max(max_backward_error, backward_error)
               assert backward_error < 1e-14
               # Dense solves are only an extra check on the regular systems.
               if not scaled:
                   np.testing.assert_allclose(actual, np.linalg.solve(operator, rhs), rtol=1e-13, atol=1e-14)
               solves += 1
         copied_bytes += pattern.rows.nbytes + pattern.cols.nbytes
         cases += 1

    for rows, cols, size in (([], [], 0), ([], [], 3), ([0], [0], 1)):
        pattern = new["SparsePattern"](rows, cols, size)
        parent = old["SparsePattern"](rows, cols, size)
        assert pattern._key == parent._key
        exact(pattern.rows, parent.rows)
        exact(pattern.cols, parent.cols)
    # A caller's read-only input remains usable and independent too.
    indices = np.arange(3)
    indices.flags.writeable = False
    pattern = new["SparsePattern"](indices, indices, 3)
    assert not np.shares_memory(indices, pattern.rows)
    for ns in (old, new):
        try:
            ns["SparsePattern"]([1, 0], [0, 0], 2)
        except ValueError:
            pass
        else:
            raise AssertionError("unsorted coordinates were accepted")
    result = dict(parent=PARENT, sparse_sha256=hashlib.sha256(source.encode()).hexdigest(),
                  reproduction=dict(parent=reproduction[0], candidate=reproduction[1]),
                  mutation_cases=cases, refined_solve_comparisons=solves,
                  maximum_normwise_backward_error=max_backward_error,
                  total_coordinate_copy_bytes_across_cases=copied_bytes,
                  scope="Synthetic source-derived kernels; no JAX or official workload; no timing claim")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
