"""Candidate41 dependency classification checks; no optical workloads or timings.

--structural-only uses a stdlib array shim to execute the actual helper.
Default also requires NumPy and checks its indexing/reductions and strided arrays.
"""
import argparse
import ast
import itertools
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def candidate(np):
    tree = ast.parse((ROOT / 'differometor/simulate.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == '_differentiable_slots')
    scope = {'np': np}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<slot helper>', 'exec'), scope)
    return scope[node.name]


def reference(indices, selected):
    return {slot: () for slot in range(indices.shape[1])
            if any(int(i) in selected for i in indices[:, slot])}


class Matrix:
    def __init__(self, values, rows, cols, kind='i'):
        self.values = list(values)
        self.shape = rows, cols
        self.size = rows * cols
        self.dtype = SimpleNamespace(kind=kind)

    def min(self):
        return min(self.values)

    def max(self):
        return max(self.values)

    def __getitem__(self, key):
        rows, col = key
        assert rows == slice(None)
        return self.values[col::self.shape[1]]


class Table:
    def __init__(self, count, selected):
        self.size = count
        self.values = [i in selected for i in range(count)]

    def __getitem__(self, indices):
        assert all(0 <= x < self.size for x in indices.values)
        return Matrix([self.values[x] for x in indices.values], *indices.shape)


def structural():
    def reduce_any(matrix, axis):
        assert axis == 0
        return [any(matrix[:, col]) for col in range(matrix.shape[1])]
    function = candidate(SimpleNamespace(any=reduce_any))
    checks = 0
    # Exhaust all pairs of rows, including repeated reads and inactive columns.
    for count in range(4):
        for bits in itertools.product((False, True), repeat=count):
            selected = {i for i, bit in enumerate(bits) if bit}
            table = Table(count, selected)
            for values in itertools.product(range(-1, count + 1), repeat=4):
                indices = Matrix(values, 2, 2)
                assert function(indices, selected, table) == reference(indices, selected)
                checks += 1
            for rows, cols in ((0, 0), (0, 7), (4, 0)):
                indices = Matrix([], rows, cols)
                assert function(indices, selected, table) == {}
                checks += 1
    for kind in ('f', 'b', 'O'):
        indices = Matrix([-0.0, 0.7, -1.2, 3.4], 2, 2, kind)
        for selected in ({0}, {-1, 3}, set()):
            for table in (None, Table(4, selected)):
                assert function(indices, selected, table) == reference(indices, selected)
                checks += 1
    print(f'{checks} actual-helper stdlib-shim comparisons passed (not NumPy validation)')


def numeric():
    import numpy as np
    function = candidate(np)
    checks = 0
    for count in (0, 1, 8):
        for selected in (set(), set(range(count)), set(range(1, count, 2)), {-1, count}):
            table = None
            if all(0 <= x < count for x in selected):
                table = np.array([i in selected for i in range(count)], dtype=bool)
            for dtype in ('i1', 'i4', 'i8', 'u8', 'f8', 'bool', 'object'):
                values = np.arange(28).reshape(4, 7) % max(count, 1)
                if dtype not in ('u8', 'bool'):
                    values = values - 1
                values = values.astype(dtype)
                if dtype == 'f8':
                    values += 0.25
                    values[0, 0] = -0.0
                for indices in (values, values.T, values[::-1, ::2], values[:0], values[:, :0]):
                    before = indices.copy()
                    actual = function(indices, selected, table)
                    assert actual == reference(indices, selected)
                    assert all(type(key) is int for key in actual)
                    np.testing.assert_array_equal(indices, before)
                    checks += 1
    print(f'{checks} NumPy comparisons passed; no inputs mutated')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structural-only', action='store_true')
    args = parser.parse_args()
    structural()
    if not args.structural_only:
        numeric()
