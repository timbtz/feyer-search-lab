"""Small synthetic checks of CSC index reuse; no optical workloads or timings.

Run using an existing NumPy/SciPy environment. Extract numerical code by AST so
the local check does not need JAX. Official evaluation remains supervisor-owned.
"""
import ast
import hashlib
from pathlib import Path
import subprocess

import numpy as np
from scipy.sparse import csc_array, csc_matrix
from scipy.sparse.linalg import splu
from scipy.sparse.linalg._dsolve import _superlu


ROOT = Path(__file__).resolve().parents[2]
PARENT = "ee4fea28c04d482566be16e916b609d7c6a99e5e"


def load(source, names, namespace):
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
             and node.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<numerical AST>", "exec"), namespace)
    return namespace


def factor_namespace(source, use_extension=True):
    calls = []

    def checked_gstrf(n, nnz, data, indices, indptr, **kwargs):
        before = (data.tobytes(), indices.tobytes(), indptr.tobytes())
        result = _superlu.gstrf(n, nnz, data, indices, indptr, **kwargs)
        assert before == (data.tobytes(), indices.tobytes(), indptr.tobytes())
        calls.append((indices, indptr))
        return result

    namespace = dict(np=np, _superlu_gstrf=lambda: checked_gstrf if use_extension else False,
                     _construct_csc=csc_array, _scipy=lambda: (splu, csc_matrix),
                     _SUPERLU_OPTIONS=dict(DiagPivotThresh=None, ColPerm="COLAMD", PanelSize=None, Relax=None))
    return load(source, {"_factor"}, namespace)["_factor"], calls


def equal(a, b):
    np.testing.assert_array_equal(a, b)
    assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def main():
    parent_source = subprocess.check_output(
        ["git", "show", f"{PARENT}:differometor/host_pass.py"], cwd=ROOT, text=True)
    candidate_source = (ROOT / "differometor/host_pass.py").read_text()
    pattern_type = load((ROOT / "differometor/sparse.py").read_text(), {"SparsePattern"},
                        dict(np=np, hashlib=hashlib))["SparsePattern"]
    rng = np.random.default_rng(8129)
    factorizations = solves = shared_calls = converted_calls = avoided_bytes = 0
    for use_extension in (True, False):
        old_factor, old_calls = factor_namespace(parent_source, use_extension)
        new_factor, new_calls = factor_namespace(candidate_source, use_extension)
        for n in (7, 19, 43):
            mask = rng.random((n, n)) < 0.17
            np.fill_diagonal(mask, True)
            cols, rows = np.nonzero(mask.T)
            for index_type in (np.int32, np.int64):
                for readonly in (False, True):
                    pattern = pattern_type(rows, cols, n)
                    pattern.indices = pattern.indices.astype(index_type)
                    pattern.indptr = pattern.indptr.astype(index_type)
                    pattern.indices.flags.writeable = not readonly
                    pattern.indptr.flags.writeable = not readonly
                    structure_bytes = (pattern.indices.tobytes(), pattern.indptr.tobytes())
                    # Reuse structure across fresh factorizations of different values.
                    for variant in (0, 1, 2):
                        matrix = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
                        matrix *= mask
                        matrix += (2 * n) * np.eye(n)
                        if variant == 0:
                            matrix[rows[rows != cols], cols[rows != cols]] = 0
                        if variant == 2:
                            # A wide dynamic range exercises pivots and scaling.
                            matrix = np.logspace(-7, 7, n)[:, None] * matrix
                        values = matrix[rows, cols]
                        old = old_factor(pattern, values)
                        new = new_factor(pattern, values)
                        factorizations += 1
                        assert structure_bytes == (pattern.indices.tobytes(), pattern.indptr.tobytes())
                        equal(old.perm_r, new.perm_r)
                        equal(old.perm_c, new.perm_c)
                        for left, right in ((old.L, new.L), (old.U, new.U)):
                            for attr in ("data", "indices", "indptr"):
                                equal(getattr(left, attr), getattr(right, attr))
                        for trans in ("N", "T", "H"):
                            for width in (None, 1, 3):
                                shape = (n,) if width is None else (n, width)
                                rhs = rng.normal(size=shape) + 1j * rng.normal(size=shape)
                                equal(old.solve(rhs, trans=trans), new.solve(rhs, trans=trans))
                                solves += 1
                        if use_extension:
                            assert old_calls[-1][0] is not pattern.indices
                            assert old_calls[-1][1] is not pattern.indptr
                            if np.dtype(index_type) == np.dtype(np.intc):
                                assert new_calls[-1][0] is pattern.indices
                                assert new_calls[-1][1] is pattern.indptr
                                shared_calls += 1
                                avoided_bytes += pattern.indices.nbytes + pattern.indptr.nbytes
                            else:
                                assert new_calls[-1][0] is not pattern.indices
                                assert new_calls[-1][1] is not pattern.indptr
                                converted_calls += 1
    print(dict(factor_pairs=factorizations, bitwise_equal_solves=solves,
               shared_index_calls=shared_calls, converted_index_calls=converted_calls,
               synthetic_index_copy_bytes_avoided=avoided_bytes,
               structure_and_values_unchanged=True, readonly_indices_passed=True,
               scope="Small synthetic correctness and copy-count check; no timing claim"))


if __name__ == "__main__":
    main()
