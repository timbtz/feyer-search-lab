"""Candidate37 diagnostic; no timing and no optical benchmark.

Default: NumPy comparisons of the actual set_instructions against its original
padding block. --structural-only: stdlib execution of the extracted padding
blocks with a tiny array model; this does not validate NumPy dtype behavior.
"""
import ast
import copy
from pathlib import Path
import sys
from types import SimpleNamespace

source = Path(__file__).resolve().parents[2] / 'differometor/build.py'
function = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'set_instructions')
padding = next(n for n in function.body if isinstance(n, ast.If))
assert isinstance(padding.body[0], ast.If), 'Run against candidate37'
original_padding = copy.deepcopy(padding)
original_padding.body = copy.deepcopy(padding.body[0].orelse)


def padding_function(node, np):
    module = ast.parse('def pad(function_input_indices):\n function_input_indices_shape = 7\n return function_input_indices')
    module.body[0].body.insert(1, copy.deepcopy(node))
    scope = dict(np=np)
    exec(compile(ast.fix_missing_locations(module), str(source), 'exec'), scope)
    return scope['pad']


if '--structural-only' in sys.argv:
    class Array:
        def __init__(self, rows, width, kind='i'):
            self.rows = rows
            self.shape = (len(rows), width)
            self.dtype = SimpleNamespace(kind=kind)

        def __setitem__(self, indices, values):
            a, b = indices
            assert a == slice(None)
            for row, update in zip(self.rows, values.rows):
                row[b] = update

    class NP:
        ndarray = Array
        float64 = 'f'

        def zeros(self, shape, dtype=None):
            return Array([[0.0] * shape[1] for _ in range(shape[0])], shape[1], 'f')

        def result_type(self, dtype, other):
            return 'f'

        def concatenate(self, arrays, axis):
            assert axis == 1
            left, right = arrays
            return Array([a + b for a, b in zip(left.rows, right.rows)],
                         left.shape[1] + right.shape[1], 'f')

    candidate, reference = (padding_function(node, NP()) for node in (padding, original_padding))
    checked = 0
    for count in range(17):
        for width in range(9):
            for kind in ('b', 'u', 'i', 'f', 'c', 'O'):
                data = Array([[i * 13 + j for j in range(width)] for i in range(count)], width, kind)
                before = copy.deepcopy(data.rows)
                a, b = candidate(data), reference(data)
                assert a.shape == b.shape and a.rows == b.rows
                assert data.rows == before
                assert (a is data) == (b is data) == (width >= 7)
                checked += 1
    print(f'PASS: {checked} structural padding cases; no NumPy/dtype or timing claim')
    sys.exit(0)

import numpy as np


def load_function(original=False):
    node = copy.deepcopy(function)
    if original:
        node.body[node.body.index(next(n for n in node.body if isinstance(n, ast.If)))] = copy.deepcopy(original_padding)
    module = ast.parse('from __future__ import annotations')
    module.body.append(node)
    scope = dict(np=np)
    exec(compile(ast.fix_missing_locations(module), str(source), 'exec'), scope)
    return scope['set_instructions']


def equal(a, b):
    if isinstance(a, np.ndarray):
        assert a.dtype == b.dtype and a.shape == b.shape
        np.testing.assert_array_equal(a, b)
        if a.dtype.kind in 'fc':
            np.testing.assert_array_equal(np.signbit(a.real), np.signbit(b.real))
            if a.dtype.kind == 'c':
                np.testing.assert_array_equal(np.signbit(a.imag), np.signbit(b.imag))
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a:
            equal(a[key], b[key])
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            equal(x, y)
    else:
        assert a == b


candidate, reference = load_function(), load_function(True)
checked = 0
for dtype in (np.bool_, np.int8, np.int64, np.uint64, np.float32, np.float64,
              np.complex64, np.complex128, object, 'U8'):
    for count in (0, 1, 4):
        for width in range(8):
            for strided in (False, True):
                values = np.arange(count * width * 2).reshape(count, width * 2).astype(dtype)
                values = values[:, ::2] if strided else values[:, :width].copy()
                if values.dtype.kind in 'fc' and values.size:
                    values.flat[0] = -0.0
                    if values.size > 1:
                        values.flat[1] = np.nan
                before = values.copy()
                for sidebands in (None, 3):
                    args = dict(node='synthetic', function_input_indices=values,
                                output_column_indices=np.array([0, 1, 2, 3]),
                                output_row_indices=np.zeros(4, dtype=int),
                                system_matrix_row_indices=np.array([0, 4, 0, 4]),
                                system_matrix_column_indices=np.array([0, 0, 4, 4]),
                                function_indices=[0] * count,
                                system_size_for_sidebands=sidebands)
                    outputs = []
                    for f in (candidate, reference):
                        result = {}
                        f(instructions=result, **copy.deepcopy(args))
                        outputs.append(result)
                    equal(*outputs)
                    equal(values, before)
                    checked += 1
print(f'PASS: {checked} NumPy instruction comparisons, including dtype, sign bits and sidebands')

class SubArray(np.ndarray):
    pass

candidate_pad, reference_pad = (padding_function(node, np) for node in (padding, original_padding))
for width in range(8):
    for make in (lambda x: x.view(SubArray), lambda x: np.ma.array(x, mask=x % 2 == 0)):
        values = make(np.arange(3 * width).reshape(3, width))
        a, b = candidate_pad(values), reference_pad(values)
        assert type(a) is type(b)
        equal(a, b)
        if np.ma.isMaskedArray(a):
            np.testing.assert_array_equal(np.ma.getmaskarray(a), np.ma.getmaskarray(b))
print('PASS: 16 subclass/fallback comparisons')
