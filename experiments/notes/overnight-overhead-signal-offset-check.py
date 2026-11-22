"""Signal instruction offsets: stdlib structural checks, optional NumPy/JAX.

No fixtures or timing runs. --jax exercises the real pairs_to_arrays output
selectors and their JIT/VJP on a synthetic stack of distinguishable values.
It does not certify optical propagation or the solver derivatives.
"""
import argparse
import ast
from collections import defaultdict
from pathlib import Path
import random
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'f856aafd5552f433aa08bd3dc923acb31d5adf4e'


class Vector(list):
    def flatten(self):
        return Vector(self)

    def __add__(self, offset):
        return Vector(x + offset for x in self)

    def __mul__(self, value):
        return Vector(x * value for x in self)


def signal_prefix(source):
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'pairs_to_arrays')
    end = next(i for i, n in enumerate(function.body)
               if isinstance(n, ast.FunctionDef) and n.name == 'append_information')
    function.body = function.body[:end] + ast.parse('return signal_arrays').body
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[
        ast.alias(name='annotations')], level=0), function], type_ignores=[])
    ns = dict(defaultdict=defaultdict, np=SimpleNamespace(
        ones=lambda n: Vector([1] * n), unique=lambda v: sorted(set(v))))
    exec(compile(ast.fix_missing_locations(module), '<actual signal planning loop>', 'exec'), ns)
    return ns['pairs_to_arrays']


def instruction(count, selected):
    # All rows exist even when no entry from some rows is read.
    columns = [i % 4 for i in range(len(selected) if selected is not None else 2)]
    result = dict(function_input_indices=[[0] * 7 for _ in range(count)],
                  function_indices=[0] * count, output_column_indices=columns,
                  system_matrix_row_indices=list(range(len(columns))),
                  system_matrix_column_indices=[0] * len(columns))
    if selected is not None:
        result['output_row_indices'] = Vector(selected)
    return result


def expected(specs):
    offset, rows = 0, []
    for count, selected in specs:
        rows.extend(offset + r for r in (selected if selected is not None else [0, 0]))
        offset += count
    return rows


def structural_check():
    source = (ROOT / 'differometor/build.py').read_text()
    old = subprocess.check_output(['git', 'show', PARENT + ':differometor/build.py'],
                                  cwd=ROOT, text=True)
    current, parent = signal_prefix(source), signal_prefix(old)

    def run(fn, specs):
        items = {str(i): instruction(n, rows) for i, (n, rows) in enumerate(specs)}
        result = fn({}, items, {}, [], [])
        return [r for block in result['output_row_indices'] for r in block]

    witness = [(3, [0, 2]), (1, [0])]
    assert run(parent, witness) == [0, 2, 2]
    assert run(current, witness) == [0, 2, 3]
    print('Parent counterexample: next instruction selects row 2, expected row 3')
    cases = [witness, [(3, []), (1, [0])], [(3, None), (2, [0, 1])], []]
    rng = random.Random(5401)
    for _ in range(500):
        specs = []
        for _ in range(rng.randrange(1, 9)):
            count = rng.randrange(1, 8)
            rows = ([rng.randrange(count) for _ in range(rng.randrange(16))]
                    if rng.randrange(4) else None)
            specs.append((count, rows))
        cases.append(specs)
    for specs in cases:
        assert run(current, specs) == expected(specs)
    # Ordinary instructions selecting every row retain exactly the same selectors.
    for _ in range(500):
        specs = []
        for _ in range(rng.randrange(1, 9)):
            count = rng.randrange(1, 8)
            rows = list(range(count)) + [rng.randrange(count) for _ in range(8)]
            rng.shuffle(rows)
            specs.append((count, rows))
        assert run(current, specs) == run(parent, specs) == expected(specs)
    print('PASS: 504 arbitrary-selection cases and 500 full-selection parent comparisons (stdlib)')


def jax_check():
    import sys
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import jax
    import jax.numpy as jnp
    from differometor.build import pairs_to_arrays
    jax.config.update('jax_enable_x64', True)
    for specs in ([(3, [0, 2]), (1, [0])], [(3, []), (2, [0, 1])],
                  [(3, None), (2, [1, 0, 1])], [(2, [1, 0, 1]), (1, [0])]):
        items, columns = {}, []
        for i, (count, selected) in enumerate(specs):
            item = instruction(count, selected)
            columns.extend(item['output_column_indices'])
            items[str(i)] = {k: np.asarray(v, dtype=np.int64) for k, v in item.items()}
        _, _, signal, _ = pairs_to_arrays({}, items, {}, [], [])
        selectors = np.asarray(signal[2])
        rows = np.asarray(expected(specs), dtype=np.int64)
        np.testing.assert_array_equal(selectors, np.stack((rows, columns)))
        total = sum(n for n, _ in specs)
        values = jnp.arange(total * 4, dtype=jnp.float64).reshape(total, 4)
        cotangent = jnp.arange(1, len(rows) + 1, dtype=jnp.float64)
        fn = jax.jit(lambda x: x[selectors[0], selectors[1]])
        output, pullback = jax.vjp(fn, values)
        np.testing.assert_array_equal(output, np.asarray(values)[rows, columns])
        expected_bar = np.zeros((total, 4))
        np.add.at(expected_bar, (rows, columns), np.asarray(cotangent))
        np.testing.assert_array_equal(pullback(cotangent)[0], expected_bar)
    print('PASS: 4 actual-builder NumPy selector and JIT/VJP cases')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jax', action='store_true')
    args = parser.parse_args()
    structural_check()
    if args.jax:
        jax_check()
