"""Check private Jacobian buffer reuse through SystemPlan.backward; no timings."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import tracemalloc
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
h = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-assembly-check.py'))
check_equal = h['loader']['check_equal']
rng = np.random.default_rng(2026112224)

def plans(function, components, slots):
    indices = rng.integers(-31, 31, (components, 7))
    selected = np.arange(components * 4)
    system = SimpleNamespace(write_positions=selected, _key='inplace-synthetic')
    args = (system, [(function, indices, slots)], selected // 4, selected % 4)
    return h['old_class'](*args), h['new_class'](*args)

checks = 0
for batches in (0, 1, 7, 37):
    for components in (1, 5, 43):
        for function in range(19):
            for slots in ((), (0,), (6, 0, 2, 6), (-1, 0, 1, 2, 3, 4, 5, 6)):
                old, new = plans(function, components, slots)
                rows = rng.uniform(.1, .6, (batches, 31)).astype(np.complex128)
                rows += 1e-3j * rng.normal(size=rows.shape)
                bars = rng.normal(size=(batches, components * 4)).astype(np.complex128)
                bars += 1j * rng.normal(size=bars.shape)
                for mode in ('regular', 'zero', 'nonfinite'):
                    inputs, cotangents = rows.copy(), bars.copy()
                    if mode == 'zero':
                        inputs *= 0
                        cotangents[:, ::2] = complex(-0., -0.)
                    elif mode == 'nonfinite':
                        inputs[:, ::5] = np.nan
                        cotangents[:, ::7] = np.inf + 1j
                    saved_inputs, saved_bars = inputs.copy(), cotangents.copy()
                    with np.errstate(all='ignore'):
                        expected = old.backward(inputs, cotangents)
                        actual = new.backward(inputs, cotangents)
                    check_equal(expected, actual)
                    check_equal((saved_inputs, saved_bars), (inputs, cotangents))
                    checks += 1

# Count Jacobian calls and inspect private storage ownership. Measure complete
# synthetic backward allocations, including its row gathers and scatters.
old, new = plans(h['namespace']['index'], 43, tuple(range(7)))
inputs = rng.uniform(.1, .6, (37, 31)).astype(np.complex128)
bars = rng.normal(size=(37, 43 * 4)).astype(np.complex128)
counts = []
for ns in (h['old_ns'], h['new_ns']):
    jacobian = ns['function_jacobian']
    calls = []
    def counted(function, slots, rows, with_outputs=True, original=jacobian, calls=calls):
        result = original(function, slots, rows, with_outputs=with_outputs)
        linear, antilinear = result[1:]
        assert linear.flags.owndata and antilinear.flags.owndata
        assert not np.shares_memory(linear, antilinear)
        assert not np.shares_memory(linear, rows)
        assert not np.shares_memory(antilinear, rows)
        calls.append(linear.nbytes + antilinear.nbytes)
        return result
    ns['function_jacobian'] = counted
    counts.append(calls)

def peak(plan):
    tracemalloc.start()
    try:
        result = plan.backward(inputs, bars)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak_bytes

expected, old_peak = peak(old)
actual, new_peak = peak(new)
check_equal(expected, actual)
assert counts[0] == counts[1] == [2 * 37 * 43 * 4 * 7 * 16], counts
assert new_peak < old_peak
print(dict(backward_checks=checks, inherited_checks=h['checks'],
           jacobian_pairs_bytes=counts, parent_peak_bytes=old_peak,
           candidate_peak_bytes=new_peak,
           scope='synthetic correctness/allocation only; no official workload/timing'))
