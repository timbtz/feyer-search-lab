"""Small structural ownership inspection; no benchmark inputs or timings."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'ed2c9d27ac4a106959f6cfab7d61ae7ba51a0058'
helper = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-slot-key-check.py'))
source = (ROOT / 'differometor/host_pass.py').read_text()
old = helper['load'](subprocess.check_output(
    ['git', 'show', PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True))
new = helper['load'](source)


def make(ns, indices, writes):
    function = next(i for i, f in enumerate(ns['HOST_FUNCTIONS']) if f.__name__ == 'signal_function')
    system = SimpleNamespace(write_positions=writes, _key='small-system')
    return ns['SystemPlan'](system, [(function, indices, (0, 1))],
                            np.arange(indices.shape[0]), np.zeros(indices.shape[0], int))


def evaluate(plan, rows, base, bar):
    return (plan.values(rows, base), *plan.backward(rows, bar))


def equal(a, b):
    for expected, actual in zip(a, b):
        assert np.all(np.isfinite(expected)) and np.all(np.isfinite(actual))
        assert expected.dtype == actual.dtype and expected.shape == actual.shape
        assert expected.tobytes() == actual.tobytes()


rows = np.array([[2, 0, .2, 5, 1, 1.4, 2]], complex)
reproduction = []
for ns in (old, new):
    indices, writes = np.arange(7)[None, :], np.array([0])
    plan = make(ns, indices, writes)
    initial_key = plan._key
    before = evaluate(plan, rows, np.zeros(2, complex), np.ones((1, 2), complex))
    indices[0, 0] = 3
    writes[0] = 1
    after = evaluate(plan, rows, np.zeros(2, complex), np.ones((1, 2), complex))
    assert initial_key == plan._key
    rebuilt = make(ns, indices, writes)
    assert rebuilt._key != initial_key
    assert rebuilt.values(rows, np.zeros(2))[0, 1] == 5
    reproduction.append((before, after))
assert reproduction[0][0][0].tolist() == [[2, 0]]
assert reproduction[0][1][0].tolist() == [[0, 5]]
# Parent's retained base derivative is [0,1], despite now writing destination1.
assert reproduction[0][1][2].tolist() == [0, 1]
equal(*reproduction[1])

rng = np.random.default_rng(2026112248)
cases = copied_bytes = 0
for batch in (1, 3):
    for components in (1, 2, 4):
        for view in (False, True):
            for duplicate_writes in (False, True):
                for zero in (False, True):
                    indices = rng.integers(0, 9, (components, 7), dtype=np.int64)
                    writes = np.arange(components, dtype=np.int64)
                    if duplicate_writes:
                        writes[:] = 0
                    if view:
                        index_storage = np.zeros((components, 14), dtype=np.int64)
                        index_storage[:, ::2] = indices
                        indices = index_storage[:, ::2]
                        write_storage = np.zeros(components * 2, dtype=np.int64)
                        write_storage[::2] = writes
                        writes = write_storage[::2]
                    points = rng.normal(size=(batch, 9)).astype(complex)
                    if zero:
                        points[:, indices[0, 0]] = 0
                    base = rng.normal(size=components + 1).astype(complex)
                    bar = rng.normal(size=(batch, components + 1)).astype(complex)
                    a, b = make(old, indices, writes), make(new, indices, writes)
                    assert a._key == b._key
                    before = evaluate(a, points, base, bar)
                    equal(before, evaluate(b, points, base, bar))
                    assert not np.shares_memory(indices, b.groups[0][1])
                    assert not np.shares_memory(writes, b.writes)
                    assert indices.flags.writeable and writes.flags.writeable
                    assert not b.groups[0][1].flags.writeable and not b.writes.flags.writeable
                    copied_bytes += indices.nbytes + writes.nbytes
                    indices[:] = (indices + 1) % 9
                    writes[:] = (writes + 1) % (components + 1)
                    equal(before, evaluate(b, points, base, bar))
                    # Rebuilding consumes the edited structure, including duplicates.
                    rebuilt = make(new, indices, writes)
                    fresh_parent = make(old, indices, writes)
                    equal(evaluate(fresh_parent, points, base, bar),
                          evaluate(rebuilt, points, base, bar))
                    assert rebuilt._key == fresh_parent._key and rebuilt._key != b._key
                    # Independent real-direction finite differences of the retained
                    # plan's base pullback check its last-write behavior after edits.
                    for column in range(base.size):
                        delta = np.zeros(base.size, complex)
                        delta[column] = 1e-5
                        derivative = np.real(np.sum(bar * (
                            b.values(points, base + delta) - b.values(points, base - delta)))) / 2e-5
                        np.testing.assert_allclose(derivative, np.real(before[2][column]),
                                                   rtol=1e-8, atol=1e-9)
                    cases += 1

print(json.dumps(dict(parent_sha=PARENT,
    candidate_host_pass_sha256=hashlib.sha256(source.encode()).hexdigest(),
    parent_key_unchanged_after_semantic_mutation=True,
    parent_base_pullback_inconsistency_reproduced=True,
    candidate_snapshot_retained=True, equivalence_and_mutation_cases=cases,
    finite_results_bitwise_equal=True, finite_difference_base_pullbacks_passed=True,
    copied_index_bytes_across_synthetic_plans=copied_bytes,
    scope='SystemPlan input-index and write-position ownership only; no whole-plan immutability or performance claim'), indent=2))
