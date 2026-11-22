"""Candidate31: supervisor-only synthetic CSC validation equivalence, no timings.

Extracts SparsePattern and substitutes only the parent's order-validation block
for the reference. Requires NumPy; no JAX, optics fixtures, or solver invocation.
"""
import ast
import copy
import hashlib
from pathlib import Path
import numpy as np

source = Path(__file__).resolve().parents[2] / 'differometor/sparse.py'
node = next(n for n in ast.parse(source.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == 'SparsePattern')
reference_node = copy.deepcopy(node)
constructor = next(n for n in reference_node.body
                   if isinstance(n, ast.FunctionDef) and n.name == '__init__')
start = next(i for i, n in enumerate(constructor.body)
             if isinstance(n, ast.If) and 'rows.ndim' in ast.unparse(n.test))
assert ast.unparse(constructor.body[start + 1].test) == 'out_of_order'
constructor.body[start:start + 2] = ast.parse('''
order = np.lexsort((rows, cols))
if np.any(order != np.arange(order.size)):
    raise ValueError("SparsePattern entries must already be in CSC order")
''').body

def load(class_node):
    scope = dict(np=np, hashlib=hashlib)
    tree = ast.fix_missing_locations(ast.Module(body=[class_node], type_ignores=[]))
    exec(compile(tree, str(source), 'exec'), scope)
    return scope['SparsePattern']

candidate, reference = load(node), load(reference_node)
rng = np.random.default_rng(3131)
cases = [([], [], 0), ([0], [0], 1), ([0, 0], [0, 0], 1),
         ([1, 0], [0, 0], 2), ([0, 1], [1, 0], 2),
         ([2, 0], [0, 1], 3),
         ([-2**63, 2**63-1], [0, 0], 2),
         ([2**63-1, -2**63], [0, 0], 2),
         ([0, 0], [-2**63, 2**63-1], 2)]
for _ in range(300):
    size = int(rng.integers(1, 20))
    count = int(rng.integers(0, 40))
    rows, cols = rng.integers(size, size=count), rng.integers(size, size=count)
    order = np.lexsort((rows, cols))
    cases.extend([(rows, cols, size), (rows[order], cols[order], size),
                  (rows[order][::-1], cols[order][::-1], size)])
# Fallback keeps parent handling of malformed dimensions and mismatched shapes.
cases.extend([(np.zeros((2, 2)), np.zeros((2, 2)), 2),
              ([0], [0, 1], 2), (0, 0, 1),
              (np.zeros((0, 2)), np.zeros((0, 2)), 2)])
for rows, cols, size in cases:
    outcomes = []
    for cls in (candidate, reference):
        try:
            outcomes.append(cls(rows, cols, size))
        except Exception as exc:
            outcomes.append((type(exc), str(exc)))
    a, b = outcomes
    if isinstance(a, tuple) or isinstance(b, tuple):
        assert a == b, (rows, cols, a, b)
    else:
        for name in ('rows', 'cols', 'indices', 'indptr'):
            np.testing.assert_array_equal(getattr(a, name), getattr(b, name))
        assert (a.size, a.nnz, a._key, hash(a)) == (b.size, b.nnz, b._key, hash(b))
print(f'PASS: {len(cases)} construction/validation cases; no timing claim')
