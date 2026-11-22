"""Candidate33 metadata equivalence diagnostic for the supervisor's NumPy environment.

No timing or optical benchmark. Compare the actual pairs_to_arrays implementation
with the old constant-label expressions, including pre-cast host arrays.
"""
import ast
import copy
from collections import defaultdict
from pathlib import Path
import numpy as np

source = Path(__file__).resolve().parents[2] / 'differometor/build.py'
tree = ast.parse(source.read_text())
names = {'pairs_to_arrays', '_group_component_indices', '_matrix_indices_are_unique'}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]


class OriginalLabels(ast.NodeTransformer):
    def __init__(self):
        self.replaced = 0

    def visit_Call(self, node):
        self.generic_visit(node)
        if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'np' and node.func.attr == 'full'):
            assert len(node.args) == 2
            assert len(node.keywords) == 1 and node.keywords[0].arg == 'dtype'
            assert isinstance(node.keywords[0].value, ast.Name) and node.keywords[0].value.id == 'float'
            self.replaced += 1
            return ast.BinOp(left=ast.Call(func=ast.Attribute(value=ast.Name(id='np', ctx=ast.Load()),
                             attr='ones', ctx=ast.Load()), args=[node.args[0]], keywords=[]),
                             op=ast.Mult(), right=node.args[1])
        return node


original = OriginalLabels()
reference_nodes = original.visit(ast.Module(body=copy.deepcopy(nodes), type_ignores=[]))
assert original.replaced == 2, 'Run this diagnostic against candidate33'


def evaluate(module, arguments):
    log = []
    def host_array(values, dtype):
        array = np.asarray(values)
        log.append(array.copy())
        return np.asarray(values, dtype=np.int64 if dtype is int else dtype)
    dummy = object()
    scope = dict(np=np, defaultdict=defaultdict, _host_array=host_array,
                 FUNCTIONS=[object(), object(), object(), dummy], dummy_function=dummy)
    exec(compile(ast.fix_missing_locations(copy.deepcopy(module)), str(source), 'exec'), scope)
    groups = {}
    result = scope['pairs_to_arrays'](**copy.deepcopy(arguments), component_groups=groups,
              matrix_shapes={name: (64, 65) for name in ('carrier', 'signal', 'noise')})
    return result, groups, log


def equal(a, b):
    assert type(a) is type(b), (type(a), type(b))
    if isinstance(a, np.ndarray):
        assert a.dtype == b.dtype and a.shape == b.shape
        np.testing.assert_array_equal(a, b)
        if a.dtype.kind == 'f':
            np.testing.assert_array_equal(np.signbit(a), np.signbit(b))
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a: equal(a[key], b[key])
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b)
        for x, y in zip(a, b): equal(x, y)
    else:
        assert a == b


checked = 0
for count in (0, 1, 4, 9):
    for width in (0, 1, 3):
        for repeats in (False, True):
            for explicit_rows in (False, True):
                def instruction(i):
                    return dict(function_input_indices=np.full((1, 7), i, dtype=np.int64),
                                function_indices=[i % 3], output_column_indices=np.arange(width),
                                system_matrix_row_indices=np.full(width, i),
                                system_matrix_column_indices=np.arange(width))
                parameters = {f'p{i}': instruction(i) for i in range(count)}
                noise = {f'n{i}': instruction(i) for i in range(count)}
                signal = {f's{i}': instruction(i) for i in range(count)}
                if explicit_rows:
                    for item in signal.values(): item['output_row_indices'] = np.zeros(width, dtype=int)
                signal['ignored'] = {}
                optimization = [(name, 'gain') for name in parameters]
                if repeats: optimization = optimization + optimization[::-1]
                changing = [('p0', 'gain'), ('s0', 'phase')] if count else []
                arguments = dict(parameter_instructions=parameters, signal_instructions=signal,
                    noise_instructions=noise, signal_components=[f's{i}' for i in range(count)],
                    parameter_names=[f'p{i}_gain' for i in range(count)] + [f's{i}_phase' for i in range(count)],
                    optimization_pairs=optimization, changing_pairs=changing)
                equal(evaluate(ast.Module(body=nodes, type_ignores=[]), arguments),
                      evaluate(reference_nodes, arguments))
                checked += 1
print(f'PASS: {checked} synthetic instruction collections; outputs, groups and pre-cast arrays equal')

# Offset conversion near the exact-integer limit must match the old float64 multiply.
for offset in (0, 1, 17, 2**53 - 1, 2**53, 2**53 + 1, 2**63 - 1):
    for length in (0, 1, 5):
        equal(np.full(length, offset, dtype=float), np.ones(length) * offset)
print('PASS: 21 scalar-conversion/zero-length cases; no timing claim')
