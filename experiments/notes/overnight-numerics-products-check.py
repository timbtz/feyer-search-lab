"""Small synthetic correctness checks; no official workload or timing claims.

Run with an existing NumPy/SciPy environment. Extracts just the numerical kernel
definitions so this inspection does not need JAX or import the simulator package.
"""

import ast
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu


ROOT = Path(__file__).resolve().parents[2]
PARENT = "ee4fea28c04d482566be16e916b609d7c6a99e5e"


def kernels(source):
    tree = ast.parse(source)
    nodes = [node for node in tree.body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef))
             and node.name in ("_Products", "_solve")]
    namespace = {"np": np, "REFINEMENT_STEPS": 3, "REFINEMENT_TOLERANCE": 1e-14}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "kernels", "exec"), namespace)
    return namespace


class Factor:
    def __init__(self, factor):
        self.factor = factor
        self.calls = 0

    def solve(self, rhs, trans):
        self.calls += 1
        return self.factor.solve(rhs, trans=trans)


def main():
    parent = kernels(subprocess.check_output(
        ["git", "show", f"{PARENT}:differometor/host_pass.py"], cwd=ROOT, text=True))
    candidate = kernels((ROOT / "differometor/host_pass.py").read_text())
    rng = np.random.default_rng(20261122)
    products_checked = solves_checked = 0
    correction_counts = {}
    max_dense_product_error = 0.0
    for size in (5, 13, 37):
        for ill_scaled in (False, True):
            matrix = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
            matrix[rng.random((size, size)) > 0.2] = 0
            matrix[np.diag_indices(size)] = size + 2.0
            if ill_scaled:
                scales = np.geomspace(1e-8, 1e8, size)
                matrix = scales[:, None] * matrix / scales[None, :]
            csc = csc_matrix(matrix)
            pattern = SimpleNamespace(size=size, rows=csc.indices,
                                      cols=np.repeat(np.arange(size), np.diff(csc.indptr)))
            old = parent["_Products"](pattern)
            new = candidate["_Products"](pattern)
            for perturb in (False, True):
                values = csc.data.copy()
                if perturb:
                    values *= 1 + 0.03 * (rng.normal(size=values.size) + 1j * rng.normal(size=values.size))
                    # Zero-valued structural entries remain in both products.
                    values[(pattern.rows != pattern.cols) & (np.arange(values.size) % 3 == 0)] = 0
                dense = csc_matrix((values, csc.indices, csc.indptr), shape=csc.shape).toarray()
                factor = splu(csc_matrix((values, csc.indices, csc.indptr), shape=csc.shape))
                for trans in ("N", "T", "H"):
                    operator = dense if trans == "N" else dense.T if trans == "T" else dense.conj().T
                    for columns in (None, 1, 2, 4):
                        shape = (size,) if columns is None else (size, columns)
                        bound = new.bind(values, trans, shape)
                        rhs = rng.normal(size=shape) + 1j * rng.normal(size=shape)
                        expected = old.apply(values, rhs, trans)
                        actual = bound(rhs)
                        assert actual.tobytes() == expected.tobytes(), (size, ill_scaled, trans, columns)
                        dense_result = operator @ rhs
                        error = np.max(np.abs(actual - dense_result)) / max(1.0, np.max(np.abs(dense_result)))
                        max_dense_product_error = max(max_dense_product_error, error)
                        assert error < 2e-15
                        products_checked += 1
                        # The next residual must use the new input, even though
                        # its scratch and output buffers are reused within a solve.
                        second = rhs * (0.25 - 0.125j)
                        assert bound(second).tobytes() == old.apply(values, second, trans).tobytes()
                        products_checked += 1
                        f_old, f_new = Factor(factor), Factor(factor)
                        expected = parent["_solve"](old, values, f_old, rhs, trans)
                        actual = candidate["_solve"](new, values, f_new, rhs, trans)
                        assert actual.tobytes() == expected.tobytes(), ("solve", size, ill_scaled, trans, columns)
                        assert f_old.calls == f_new.calls
                        steps = f_new.calls - 1
                        correction_counts[steps] = correction_counts.get(steps, 0) + 1
                        solves_checked += 1
    # Nearly singular Hilbert systems exercise the full three-correction path.
    for size in (8, 12):
        index = np.arange(size)
        matrix = (1 / (1 + index[:, None] + index[None, :])).astype(np.complex128)
        csc = csc_matrix(matrix)
        pattern = SimpleNamespace(size=size, rows=csc.indices,
                                  cols=np.repeat(index, np.diff(csc.indptr)))
        old, new = parent["_Products"](pattern), candidate["_Products"](pattern)
        factor = splu(csc)
        for trans in ("N", "T", "H"):
            for columns in (1, 3):
                rhs = rng.normal(size=(size, columns)) + 1j * rng.normal(size=(size, columns))
                f_old, f_new = Factor(factor), Factor(factor)
                expected = parent["_solve"](old, csc.data, f_old, rhs, trans)
                actual = candidate["_solve"](new, csc.data, f_new, rhs, trans)
                assert actual.tobytes() == expected.tobytes()
                assert f_old.calls == f_new.calls
                steps = f_new.calls - 1
                correction_counts[steps] = correction_counts.get(steps, 0) + 1
                solves_checked += 1

    # Sparse products must leave absent rows/columns zero even on repeated calls.
    pattern = SimpleNamespace(size=7, rows=np.array([1, 3, 1, 5]), cols=np.array([0, 0, 4, 6]))
    old, new = parent["_Products"](pattern), candidate["_Products"](pattern)
    values = np.array([0, 2j, -3, 1 + 4j], dtype=np.complex128)
    for trans in ("N", "T", "H"):
        for shape in ((7,), (7, 2)):
            bound = new.bind(values, trans, shape)
            for _ in range(3):
                x = rng.normal(size=shape) + 1j * rng.normal(size=shape)
                assert bound(x).tobytes() == old.apply(values, x, trans).tobytes()
                products_checked += 1
    print({"products_bitwise_equal": products_checked, "solves_bitwise_equal": solves_checked,
           "refinement_step_counts_equal": correction_counts,
           "max_scaled_dense_product_error": max_dense_product_error,
           "scope": "small synthetic kernels; no official validation or performance measurement"})


if __name__ == "__main__":
    main()
