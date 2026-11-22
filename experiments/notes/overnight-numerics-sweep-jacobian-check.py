"""Static sweep-independent Jacobians: small component checks, no benchmarks or timings."""
from pathlib import Path
import runpy
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-assembly-check.py'))
old_class, old_ns = helpers['old_class'], helpers['old_ns']
new_class, new_ns = helpers['new_class'], helpers['new_ns']
equal = helpers['loader']['check_equal']
rng = np.random.default_rng(2026112220)
checks = 0
for original_count in (1, 2):
    for repeats in (1, 3, 7):
        for sweep in ([], [0], [-21], [0, 7], list(range(21))):
            for aliases in (False, True):
                groups = []
                for f in range(19):
                    indices = np.arange(21).reshape(3, 7)
                    if aliases:
                        indices = indices.copy()
                        indices[:, ::2] -= 21
                    groups.append((f, indices, tuple(range(7))))
                total = 19 * 3 * 4
                # Duplicate output reads and writes preserve last-write semantics.
                selection = rng.integers(0, total, total + 17)
                writes = rng.integers(0, total, selection.size)
                system = SimpleNamespace(write_positions=writes, _key='synthetic-sweep')
                old = old_class(system, groups, selection // 4, selection % 4)
                new = new_class(system, groups, selection // 4, selection % 4,
                                sweep_indices=sweep, parameter_count=21)
                base = rng.normal(size=total + 11) + 1j * rng.normal(size=total + 11)
                for mode in ('random', 'zero_sweep', 'zero_all', 'nonfinite'):
                    original = rng.uniform(.1, .8, (original_count, 21)).astype(np.complex128)
                    original += .001j * rng.normal(size=original.shape)
                    if mode == 'zero_all':
                        original[:] = 0
                    elif mode == 'nonfinite':
                        original[:, 7] = np.inf
                        original[:, 14] = np.nan
                    rows = np.tile(original, (repeats, 1))
                    if sweep:
                        rows[:, sweep] = (0 if mode.startswith('zero') else
                                          rng.uniform(.1, .8, (rows.shape[0], len(sweep))))
                    bars = rng.normal(size=(rows.shape[0], base.size)) + 1j * rng.normal(size=(rows.shape[0], base.size))
                    with np.errstate(all='ignore'):
                        equal((old.values(rows, base),),
                              (new.values(rows, base),))
                        equal(old.backward(rows, bars), new.backward(rows, bars, repeated_rows=original_count))
                    checks += 1

# Measure work multiplicity, not elapsed time, on an arbitrary synthetic sweep.
counts = dict(parent=0, candidate=0)
for label, ns in (('parent', old_ns), ('candidate', new_ns)):
    original_evaluate = ns['function_jacobian']
    def counted(f, slots, inputs, with_outputs=True, label=label, original_evaluate=original_evaluate):
        counts[label] += int(np.prod(inputs.shape[:-1]))
        return original_evaluate(f, slots, inputs, with_outputs=with_outputs)
    ns['function_jacobian'] = counted
groups = [(f, np.arange(21).reshape(3, 7), tuple(range(7))) for f in range(19)]
selection = np.arange(19 * 3 * 4)
system = SimpleNamespace(write_positions=selection, _key='multiplicity')
old = old_class(system, groups, selection // 4, selection % 4)
new = new_class(system, groups, selection // 4, selection % 4, sweep_indices=[0], parameter_count=21)
rows = np.tile(rng.uniform(.1, .8, (2, 21)).astype(np.complex128), (7, 1))
rows[:, 0] = rng.uniform(.1, .8, rows.shape[0])
base = np.zeros(selection.size, dtype=np.complex128)
bars = rng.normal(size=(rows.shape[0], base.size)) + 1j * rng.normal(size=(rows.shape[0], base.size))
equal(old.backward(rows, bars), new.backward(rows, bars, repeated_rows=2))
assert counts == dict(parent=798, candidate=342), counts
print(dict(sweep_forward_and_backward_checks=checks, jacobian_row_evaluations=counts,
           scope='synthetic structural evidence only; official performance unmeasured'))
