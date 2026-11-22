"""Small component/scatter equivalence inspections; no workload or timing runs."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-assembly-check.py'))
old_class, new_class = helpers['old_class'], helpers['new_class']
old_ns, new_ns = helpers['old_ns'], helpers['new_ns']
check_equal = helpers['loader']['check_equal']
rng = np.random.default_rng(2026112222)
checks = 0
for count in (1, 4, 9):
    for function in range(19):
        for slots in ((), (0,), (6, 2, 0, 6), (-1, 0, 1, 2, 3, 4, 5, 6)):
            # Both negative parameter aliases and repeated slot aliases.
            indices = rng.integers(0, 23, size=(5, 7))
            indices[::2] -= 23
            groups = [(function, indices, slots)]
            selection = np.arange(20)
            system = SimpleNamespace(write_positions=selection, _key='group-scatter')
            old = old_class(system, groups, selection // 4, selection % 4)
            new = new_class(system, groups, selection // 4, selection % 4)
            rows = rng.uniform(.1, .5, size=(count, 23)).astype(np.complex128)
            bars = rng.normal(size=(count, 29)) + 1j * rng.normal(size=(count, 29))
            for mode in ('complex', 'zero', 'nonfinite'):
                values = rows.copy()
                cotangents = bars.copy()
                if mode == 'complex':
                    values += 1e-3j * rng.normal(size=rows.shape)
                elif mode == 'zero':
                    values *= 0
                    cotangents[:, ::2] = complex(-0.0, -0.0)
                else:
                    cotangents[:, ::7] = np.inf + 1j
                    cotangents[:, ::11] = np.nan
                with np.errstate(all='ignore'):
                    check_equal(old.backward(values, cotangents), new.backward(values, cotangents))
                checks += 1

# Isolate the accumulation with adversarial cancellation and duplicate groups.
# Jacobians are prescribed for this synthetic test only; production functions
# remain unchanged. Both paths consume the same arrays.
originals = [ns['function_jacobian'] for ns in (old_ns, new_ns)]
scatter_checks = 0
try:
    for count in (0, 1, 3, 8):
        for trial in range(40):
            groups = [(0, rng.integers(-13, 13, (7, 7)), (6, 0, 2, 6)),
                      (0, rng.integers(-13, 13, (7, 7)), (6, 0, 2, 6))]
            selection = np.arange(56)
            system = SimpleNamespace(write_positions=selection, _key='cancellation')
            old = old_class(system, groups, selection // 4, selection % 4)
            new = new_class(system, groups, selection // 4, selection % 4)
            choices = np.array([0., -0., 1., -1., 1e30, -1e30, 1e-30, -1e-30])
            linear = rng.choice(choices, (count, 7, 4, 4)).astype(np.complex128)
            linear.imag = rng.choice(choices, linear.shape)
            antilinear = linear[..., ::-1].copy()
            def jacobian(*args, **kwargs):
                return None, linear, antilinear
            for ns in (old_ns, new_ns):
                ns['function_jacobian'] = jacobian
            rows = np.zeros((count, 13), dtype=np.complex128)
            bars = rng.choice(choices, (count, 56)).astype(np.complex128)
            check_equal(old.backward(rows, bars), new.backward(rows, bars))
            scatter_checks += 1
finally:
    for ns, original in zip((old_ns, new_ns), originals):
        ns['function_jacobian'] = original

# Count calls on an illustrative 19-group synthetic topology. No elapsed timings.
class NumpyCounter:
    def __init__(self):
        self.calls = 0
        self.add = SimpleNamespace(at=self.add_at)
    def add_at(self, *args, **kwargs):
        self.calls += 1
        return np.add.at(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(np, name)

groups = [(f, rng.integers(0, 23, (5, 7)), tuple(range(7))) for f in range(19)]
selection = np.arange(19 * 5 * 4)
system = SimpleNamespace(write_positions=selection, _key='call-count')
plans = [cls(system, groups, selection // 4, selection % 4) for cls in (old_class, new_class)]
rows = np.full((7, 23), .3, dtype=np.complex128)
bars = np.ones((7, selection.size), dtype=np.complex128)
counts = []
results = []
for plan, ns in zip(plans, (old_ns, new_ns)):
    counter = NumpyCounter()
    ns['np'] = counter
    try:
        results.append(plan.backward(rows, bars))
        counts.append(counter.calls)
    finally:
        ns['np'] = np
check_equal(*results)
assert counts == [133, 19], counts
print(dict(component_checks=checks, cancellation_checks=scatter_checks,
           parent_scatter_calls=counts[0], candidate_scatter_calls=counts[1],
           scope='synthetic correctness and call counts; no official timing'))
