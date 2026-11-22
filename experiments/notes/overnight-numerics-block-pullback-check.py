"""Synthetic bounded-Jacobian checks and allocation inspection; no timings."""
from pathlib import Path
import runpy
import tracemalloc
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
h = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-assembly-check.py'))
new_class, ns = h['new_class'], h['new_ns']
check_equal = h['loader']['check_equal']
jacobian = ns['function_jacobian']
rng = np.random.default_rng(2026112223)

def original(function, slots, inputs, cotangent):
    _, linear, antilinear = jacobian(function, slots, inputs, with_outputs=False)
    return np.sum(linear * cotangent, axis=2) + np.conj(np.sum(antilinear * cotangent, axis=2))

checks = 0
for batches in (0, 1, 7, 37):
    for components in (1, 5, 43):
        for function in range(19):
            inputs = rng.uniform(.1, .6, (batches, components, 7)).astype(np.complex128)
            inputs += 1e-3j * rng.normal(size=inputs.shape)
            bar = rng.normal(size=(batches, components, 4, 1)).astype(np.complex128)
            bar += 1j * rng.normal(size=bar.shape)
            for slots in ((), (0,), (6, 0, 2, 6), (-1, 0, 1, 2, 3, 4, 5, 6)):
                for mode in ('regular', 'zero', 'nonfinite'):
                    values = inputs.copy()
                    cotangent = bar.copy()
                    if mode == 'zero':
                        values *= 0
                        cotangent[:, ::2] = complex(-0., -0.)
                    elif mode == 'nonfinite':
                        values[:, ::5, 0] = np.nan
                        cotangent[:, ::7, 1] = np.inf + 1j
                    with np.errstate(all='ignore'):
                        expected = original(function, slots, values, cotangent)
                        actual = new_class._group_pullback(function, slots, values, cotangent)
                    check_equal((expected,), (actual,))
                    checks += 1

# Original per-slot scatter order is also tested with actual blocking and
# duplicate/negative parameter aliases. Both paths share original component code.
from types import SimpleNamespace
integration_checks = 0
for function in range(19):
    indices = rng.integers(-31, 31, (43, 7))
    slots = (6, 0, 2, 6)
    groups = [(function, indices, slots)]
    selected = np.arange(43 * 4)
    system = SimpleNamespace(write_positions=selected, _key='blocked-integration')
    old = h['old_class'](system, groups, selected // 4, selected % 4)
    new = new_class(system, groups, selected // 4, selected % 4)
    rows = rng.uniform(.1, .6, (37, 31)).astype(np.complex128)
    bar = rng.normal(size=(37, selected.size)) + 1j * rng.normal(size=(37, selected.size))
    with np.errstate(all='ignore'):
        check_equal(old.backward(rows, bar), new.backward(rows, bar))
    integration_checks += 1

# Count actual Jacobian array sizes and compare peak traced NumPy allocations.
inputs = rng.uniform(.1, .6, (37, 43, 7)).astype(np.complex128)
bar = np.ones((37, 43, 4, 1), dtype=np.complex128)
slots = tuple(range(7))
function = h['namespace']['index']
block_bytes = []
def counted(*args, **kwargs):
    result = jacobian(*args, **kwargs)
    block_bytes.append(result[1].nbytes + result[2].nbytes)
    return result
ns['function_jacobian'] = counted

def peak(call):
    tracemalloc.start()
    try:
        value = call()
        _, size = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return value, size
try:
    expected, old_peak = peak(lambda: original(function, slots, inputs, bar))
    actual, new_peak = peak(lambda: new_class._group_pullback(function, slots, inputs, bar))
finally:
    ns['function_jacobian'] = jacobian
check_equal((expected,), (actual,))
assert max(block_bytes) <= new_class.JACOBIAN_BLOCK_BYTES
assert sum(block_bytes) == 2 * 37 * 43 * 4 * 7 * 16
assert new_peak < old_peak
print(dict(component_checks=checks, blocked_integration_checks=integration_checks,
           parent_jacobian_pair_bytes=sum(block_bytes), candidate_pair_bytes=block_bytes,
           parent_peak_bytes=old_peak, candidate_peak_bytes=new_peak,
           scope='synthetic correctness and allocation only; no official workload/timing'))
