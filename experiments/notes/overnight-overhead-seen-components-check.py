"""Candidate36 structural comparison; stdlib only, no timings or optical fixtures.

Extracts the actual nested append_information helper and its reviewed parent.
NumPy's unchanged ones-vector expression is represented by a tiny list stub.
This verifies ordering/deduplication, not NumPy/JAX execution or physical accuracy.
"""
import ast
from collections import defaultdict
from pathlib import Path
import random
import subprocess
from types import SimpleNamespace

PARENT = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'
ROOT = Path(__file__).resolve().parents[2]


class Ones:
    def __init__(self, count):
        self.count = count

    def __mul__(self, value):
        return [1.0 * value for _ in range(self.count)]


def extract(source):
    outer = next(n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name == 'pairs_to_arrays')
    helper = next(n for n in outer.body
                  if isinstance(n, ast.FunctionDef) and n.name == 'append_information')
    scope = {'np': SimpleNamespace(ones=Ones)}
    future = ast.parse('from __future__ import annotations').body[0]
    exec(compile(ast.Module(body=[future, helper], type_ignores=[]), '<actual helper>', 'exec'), scope)
    return scope['append_information']


parent_source = subprocess.check_output(
    ['git', 'show', PARENT + ':differometor/build.py'], cwd=ROOT, text=True)
reference = extract(parent_source)
candidate = extract((ROOT / 'differometor/build.py').read_text())


class Key:
    comparisons = 0

    def __init__(self, value, collide=False):
        self.value, self.collide = value, collide

    def __hash__(self):
        return 0 if self.collide else self.value

    def __eq__(self, other):
        Key.comparisons += 1
        return isinstance(other, Key) and self.value == other.value


def instructions_for(keys, rng):
    result = {}
    for row, key in enumerate(keys):
        count = rng.randrange(5)
        result[key] = {
            'function_input_indices': [row, 0, row + 1],
            'function_indices': [row % 3],
            'output_column_indices': [i % 4 for i in range(count)],
            'system_matrix_row_indices': [row for _ in range(count)],
            'system_matrix_column_indices': list(range(count)),
        }
    return result


def execute(function, seen, instructions, sequence):
    arrays = defaultdict(list)
    for key in sequence:
        function(instructions, arrays, key, seen)
    return dict(arrays), len(seen)


rng = random.Random(3636)
checks = 0
for count in range(17):
    for key_kind in ('str', 'tuple', 'collision'):
        keys = ([f'component-{i}' for i in range(count)] if key_kind == 'str'
                else [(i, 'component') for i in range(count)] if key_kind == 'tuple'
                else [Key(i, collide=True) for i in range(count)])
        instructions = instructions_for(keys, rng)
        sequences = [[], keys, keys[::-1], keys + keys]
        sequences += [[rng.choice(keys) for _ in range(rng.randrange(50))] if keys else []
                      for _ in range(8)]
        for sequence in sequences:
            assert execute(candidate, set(), instructions, sequence) == execute(
                reference, [], instructions, sequence)
            checks += 1

# Count equality work only: these are operation counts, never elapsed-time claims.
keys = [Key(i) for i in range(128)]
instructions = instructions_for(keys, rng)
sequence = keys + keys[:64]
Key.comparisons = 0
expected = execute(reference, [], instructions, sequence)
old_comparisons = Key.comparisons
Key.comparisons = 0
got = execute(candidate, set(), instructions, sequence)
new_comparisons = Key.comparisons
assert got == expected
assert new_comparisons < old_comparisons
print(f'PASS: {checks} structural cases; equality comparisons {old_comparisons} -> {new_comparisons}')
print('NumPy expression stubbed; no runtime or physical correctness claim')
