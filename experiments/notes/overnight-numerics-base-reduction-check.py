"""Synthetic base-cotangent reduction audit; no optical workloads or timings."""
import ast
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import tracemalloc
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = '7a9480332bad29b5aaeacc5a4628481581507e7a'
helper = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-surface-check.py'))
namespace, _ = helper['load']((ROOT / 'differometor/components.py').read_text())
equal = helper['check_equal']


def load_plan(source):
    nodes = [n for n in ast.parse(source).body if
             isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ('SystemPlan', '_digest')]
    ns = dict(namespace, np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'base-reduction-plan', 'exec'), ns)
    return ns['SystemPlan']


old_class = load_plan(subprocess.check_output(
    ['git', 'show', PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True))
new_class = load_plan((ROOT / 'differometor/host_pass.py').read_text())
rng = np.random.default_rng(2026112240)
checks = primal_checks = fast_path_checks = fallback_checks = 0


def plans(n, writes, groups, selected):
    system = SimpleNamespace(write_positions=np.asarray(writes, dtype=np.int64),
                             all_rows=np.arange(n), _key='synthetic-base-reduction')
    result = [cls(system, groups, selected // 4, selected % 4) for cls in (old_class, new_class)]
    assert result[0]._key == result[1]._key
    return result


def compare(old, new, rows, bars):
    global checks, fast_path_checks, fallback_checks
    fast_path_checks += bool(bars.flags.c_contiguous)
    fallback_checks += not bars.flags.c_contiguous
    before = bars.copy()
    with np.errstate(all='ignore'):
        left = old.backward(rows, bars)
        right = new.backward(rows, bars)
    equal(left, right)
    equal((before,), (bars,))
    checks += 1


# Base-only tests still execute the actual whole SystemPlan.backward method.
# An empty derivative slot list separates reduction from the unchanged Jacobian.
for batch in (0, 1, 2, 7, 16, 33, 97, 128, 257):
    for width in (0, 1, 2, 3, 4, 5, 16, 31, 64):
        for mode in ('none_written', 'all_written', 'alternating', 'random'):
            written = (np.empty(0, dtype=int) if mode == 'none_written' else
                       np.arange(width) if mode == 'all_written' else
                       np.arange(0, width, 2) if mode == 'alternating' else
                       np.flatnonzero(rng.random(width) < .5))
            old, new = plans(width, written, [(0, np.zeros((1, 7), dtype=int), ())],
                             np.arange(written.size) % 4)
            rows = np.zeros((batch, 1), dtype=np.complex128)
            data = (rng.normal(size=(batch, width)) + 1j*rng.normal(size=(batch, width)))
            data *= 10.**rng.integers(-12, 12, data.shape)
            storage = np.empty((batch, 2*width), dtype=np.complex128)
            storage[:, ::2] = data
            for bars in (data, np.asfortranarray(data), data[::-1], storage[:, ::2]):
                compare(old, new, rows, bars)
            if batch and width:
                # Overwritten NaN/Inf/overflow/signed-zero entries must remain
                # masked out of base cotangents; surviving entries stay visible.
                for value in (np.nan, np.inf, -np.inf, 1e308, complex(-0., -0.)):
                    special = np.full(data.shape, value, dtype=np.complex128)
                    compare(old, new, rows, special)

# Full source-derived component pullbacks, all19 functions, repeated destinations,
# repeated/negative parameter indices, zero-point and boundary derivatives.
for batch in (1, 3, 17):
    rows = rng.uniform(.15, .7, (batch, 41)).astype(np.complex128)
    rows += .002j*rng.normal(size=rows.shape)
    groups = [(f, rng.integers(-41, 41, (2+f%3, 7)), tuple(range(7)))
              for f in range(len(namespace['HOST_FUNCTIONS']))]
    size = sum(i.shape[0]*4 for _, i, _ in groups)
    for repeated in (False, True):
        selected = np.arange(size)
        if repeated:
            selected = np.concatenate((selected, selected[::3]))
        writes = np.arange(selected.size) if not repeated else rng.integers(0, size, selected.size)
        old, new = plans(size+7, writes, groups, selected)
        base = rng.normal(size=size+7) + 1j*rng.normal(size=size+7)
        bars = rng.normal(size=(batch, size+7)) + 1j*rng.normal(size=(batch, size+7))
        for parameters in (rows, rows*0, np.ones_like(rows)):
            with np.errstate(all='ignore'):
                equal((old.values(parameters, base),), (new.values(parameters, base),))
            primal_checks += 1
            for cotangent in (bars, np.asfortranarray(bars), bars[::-1]):
                compare(old, new, parameters, cotangent)
        bars[:, 0] = np.nan + 1j*np.inf
        compare(old, new, rows, bars)

# Confirm masked nonfinites are not evaluated by the reduction itself; no
# production warning suppression or relaxed comparison is needed.
old, new = plans(5, np.arange(5), [(0, np.zeros((2, 7), dtype=int), ())], np.arange(5))
with np.errstate(invalid='raise', over='raise'):
    for value in (np.nan, np.inf, 1e308):
        bars = np.full((17, 5), value, dtype=np.complex128)
        left = old.backward(np.zeros((17, 1), dtype=complex), bars)
        right = new.backward(np.zeros((17, 1), dtype=complex), bars)
        equal(left, right)
        assert np.all(right[1] == 0)

# Measure allocation only, with unchanged result and no solver/optical workload.
batch, width = 97, 263
old, new = plans(width, np.arange(0, width, 2), [(0, np.zeros((1, 7), dtype=int), ())],
                 np.arange(0, width, 2) % 4)
rows = np.zeros((batch, 1), dtype=np.complex128)
bars = rng.normal(size=(batch, width)).astype(np.complex128)
peaks = []
for plan in (old, new):
    tracemalloc.start()
    result = plan.backward(rows, bars)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peaks.append(peak)
compare(old, new, rows, bars)
print(json.dumps(dict(pullbacks=checks, primals=primal_checks,
    fast_path_checks=fast_path_checks, fallback_checks=fallback_checks,
    masked_nonfinite_raise_checks=3,
    full_matrix_copy_bytes=bars.nbytes, static_mask_bytes=new.base_unwritten.nbytes,
    traced_peak_bytes_parent=peaks[0], traced_peak_bytes_candidate=peaks[1],
    finite='bitwise equal including signed zeros', nonfinite='array-equal',
    scope='synthetic correctness and allocation; no timing claim'), indent=2))
