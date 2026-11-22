"""Candidate38 checks: selection composition, then optional NumPy execution.

--structural-only needs only stdlib; it does not validate NumPy execution.
Default runs the actual candidate values method against the original method,
without importing the simulator, running optical workloads, or timing anything.
"""
import argparse
import ast
import itertools
from pathlib import Path
import random
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = '''
def values(self, rows, base):
    blocks = [evaluate_function(f, rows[:, indices]) for f, indices, _ in self.groups]
    outputs = np.concatenate(blocks, axis=1).reshape(rows.shape[0], -1)[:, self.flat_selection]
    values = np.repeat(np.asarray(base, dtype=np.complex128)[None, :], rows.shape[0], axis=0)
    values[:, self.writes[self.last]] = outputs[:, self.last]
    return values
'''


def structural():
    checks = 0
    # Exhaustive repeated destinations and repeated component selections.
    for count in range(5):
        for writes in itertools.product(range(3), repeat=count):
            last = [i for i, dest in enumerate(writes) if dest not in writes[i + 1:]]
            for selection in itertools.product(range(3), repeat=count):
                output = ['a', 'b', 'c']
                selected = [output[i] for i in selection]
                old = ['base'] * 3
                new = old.copy()
                for i in last:
                    old[writes[i]] = selected[i]
                for dest, index in zip([writes[i] for i in last], [selection[i] for i in last]):
                    new[dest] = output[index]
                assert old == new
                checks += 1
    print(f'{checks} exhaustive selection-composition checks passed (stdlib only)')


def numeric():
    import numpy as np
    tree = ast.parse((ROOT / 'differometor/host_pass.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SystemPlan')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'values')
    assert 'self.last_selection' in ast.unparse(method), 'Run against candidate38 source'
    scope = {'np': np}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<candidate values>', 'exec'), scope)
    candidate = scope['values']
    exec(REFERENCE, scope)
    reference = scope['values']
    rng = random.Random(3838)
    checks = 0
    for batch in (1, 2, 7):
        for widths in ((1,), (2, 3), (0, 1, 2)):
            for count in (0, 1, 5, 17):
                for special in (False, True):
                    blocks = [np.empty((batch, width, 4), dtype=np.complex128) for width in widths]
                    for block in blocks:
                        raw = block.view(np.float64).reshape(-1)
                        options = (0.0, -0.0, float('nan'), float('inf'), -float('inf'), 1.25, -2.5)
                        raw[:] = [options[i % len(options)] if special else rng.uniform(-9, 9)
                                  for i in range(raw.size)]
                    writes = np.array([rng.randrange(13) for _ in range(count)], dtype=np.int64)
                    selection = np.array([rng.randrange(4 * sum(widths)) for _ in range(count)], dtype=np.int64)
                    last = np.array([i not in writes[j + 1:] for j, i in enumerate(writes)], dtype=bool)
                    plan = SimpleNamespace(
                        groups=tuple((i, np.zeros((width, 7), dtype=np.int64), ())
                                     for i, width in enumerate(widths)),
                        writes=writes, flat_selection=selection, last=last,
                        last_positions=writes[last], last_selection=selection[last])
                    rows = np.zeros((batch, 2), dtype=np.complex128)
                    base = np.arange(13).astype(np.complex128)
                    before = base.tobytes(), rows.tobytes()
                    calls = []
                    def evaluate(index, inputs):
                        calls.append((index, inputs.shape))
                        return blocks[index]
                    scope['evaluate_function'] = evaluate
                    expected = reference(plan, rows, base)
                    expected_calls = calls.copy()
                    calls.clear()
                    actual = candidate(plan, rows, base)
                    assert expected.shape == actual.shape and expected.dtype == actual.dtype
                    assert expected.tobytes() == actual.tobytes()
                    assert calls == expected_calls
                    assert before == (base.tobytes(), rows.tobytes())
                    checks += 1
    print(f'{checks} NumPy actual-method comparisons passed, including signed zeros and nonfinite values')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structural-only', action='store_true')
    args = parser.parse_args()
    structural()
    if not args.structural_only:
        numeric()
