"""Sweep column-index allocation checks; no official workload or timing."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = "534570265891b5782b8b55ef10b5b06eb778d1c3"


def load(source):
    ns = dict(np=np)
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
             and n.name in {"_sweep_last_writes", "_expand", "_expand_backward"}]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "sweep-kernels", "exec"), ns)
    return ns


def sequential(array, indices, values):
    result = np.tile(array, (values.shape[1], 1))
    for row in range(values.shape[1]):
        for slot, column in enumerate(indices):
            result[row, column] = values[slot, row]
    return result


def exact(left, right):
    assert left.shape == right.shape and left.dtype == right.dtype
    assert np.all(np.isfinite(left)) and np.all(np.isfinite(right))
    assert left.tobytes() == right.tobytes()


def main():
    source = (ROOT / "differometor/host_pass.py").read_text()
    parent_source = subprocess.check_output(
        ["git", "show", PARENT + ":differometor/host_pass.py"], cwd=ROOT, text=True)
    old, new = load(parent_source), load(source)
    indices = np.array([1, 1])
    values = np.array([[4., 5.], [6., 7.]])
    bar = np.array([[0., 2., 0.], [0., 3., 0.]])
    reproduction = {name: ns["_expand_backward"](1, indices, values, bar)[1].tolist()
                    for name, ns in (("parent", old), ("candidate", new))}
    assert reproduction["parent"] == [[0., 0.], [2., 3.]]
    assert reproduction["candidate"] == [[0., 0.], [2., 3.]]
    rng = np.random.default_rng(2026112250)
    cases = coordinates = unique_cases = 0
    maximum_error = 0.
    # One or several base rows exercise the existing tiling transpose convention;
    # this does not assert support for simultaneous carrier and signal sweeps.
    for base_rows in (1, 3):
     for count in (0, 1, 4, 17):
      for complex_values in (False, True):
       for columns in ([], [0], [0, 2], [2, 2], [0, 2, 0], [1, -3], [-1, 1, 3, -3]):
        indices = np.array(columns, dtype=np.int64)
        array = rng.normal(size=(base_rows, 4))
        values = rng.normal(size=(indices.size, count))
        cotangent = rng.normal(size=(base_rows * count, 4))
        if complex_values:
            array = array + 1j * rng.normal(size=array.shape)
            values = values + 1j * rng.normal(size=values.shape)
            cotangent = cotangent + 1j * rng.normal(size=cotangent.shape)
        if indices.size and count:
            values[0, 0] = 0  # A zero-valued write can still be the final write.
        before = (array.copy(), values.copy(), cotangent.copy(), indices.copy())
        result = new["_expand"](array, indices, values)
        exact(result, sequential(array, indices, values))
        exact(result, old["_expand"](array, indices, values))
        base_bar, values_bar = new["_expand_backward"](base_rows, indices, values, cotangent)
        if True:
            old_bars = old["_expand_backward"](base_rows, indices, values, cotangent)
            exact(base_bar, old_bars[0])
            exact(values_bar, old_bars[1])
            unique_cases += 1
        for actual, expected in zip((array, values, cotangent, indices), before):
            exact(actual, expected)
        # Real scalar loss uses the JAX complex-cotangent convention Re(bar*dx).
        for arg, derivative in ((0, base_bar), (1, values_bar)):
         arguments = [array, values]
         for index in np.ndindex(arguments[arg].shape):
          for direction in ((1., 1j) if complex_values else (1.,)):
            plus = [x.copy() for x in arguments]
            minus = [x.copy() for x in arguments]
            step = 1e-5
            plus[arg][index] += step * direction
            minus[arg][index] -= step * direction
            fp = np.real(np.sum(sequential(plus[0], indices, plus[1]) * cotangent))
            fm = np.real(np.sum(sequential(minus[0], indices, minus[1]) * cotangent))
            numerical = (fp - fm) / (2 * step)
            expected = np.real(derivative[index] * direction)
            error = float(abs(numerical - expected))
            maximum_error = max(maximum_error, error)
            np.testing.assert_allclose(numerical, expected, rtol=1e-8, atol=1e-8)
            coordinates += 1
        cases += 1
    # Invalid destinations still raise through ordinary NumPy indexing.
    for columns in ([4, 4], [-5, -5], [0, 4], [-5, 3]):
        for ns in (old, new):
            try:
                ns["_expand"](np.ones((1, 4)), np.array(columns), np.ones((2, 1)))
            except IndexError:
                pass
            else:
                raise AssertionError("out-of-bounds sweep was accepted")
    layout_cases = 0
    for base_rows in (1, 3):
     for count in (0, 1, 4, 17):
      for layout in ('C', 'F', 'strided', 'readonly'):
       for columns in ([], [0], [0, 2], [2, 2], [0, 2, 0], [1, -3], [-1, 1, 3, -3]):
        idx = np.array(columns, dtype=np.int64)
        for special in (False, True):
            def storage(shape):
                a = rng.normal(size=shape) + 1j * rng.normal(size=shape)
                if special and a.size:
                    a.flat[0] = complex(-0., 0.)
                    if a.size > 1: a.flat[1] = complex(np.nan, np.inf)
                    if a.size > 2: a.flat[2] = complex(-np.inf, np.nan)
                if layout == 'F': a = np.asfortranarray(a)
                if layout == 'strided':
                    b = np.empty((shape[0], shape[1] * 2), complex)
                    b[:, ::2] = a
                    a = b[:, ::2]
                if layout == 'readonly': a.flags.writeable = False
                return a
            array, values, bar = storage((base_rows, 4)), storage((idx.size, count)), storage((base_rows * count, 4))
            before = [a.tobytes() for a in (array, values, bar)]
            with np.errstate(invalid='ignore'):
                lhs = (old['_expand'](array, idx, values), *old['_expand_backward'](base_rows, idx, values, bar))
                rhs = (new['_expand'](array, idx, values), *new['_expand_backward'](base_rows, idx, values, bar))
            for x, y in zip(lhs, rhs):
                assert x.shape == y.shape and x.dtype == y.dtype and x.tobytes() == y.tobytes()
            assert before == [a.tobytes() for a in (array, values, bar)]
            assert not np.shares_memory(rhs[2], bar)
            layout_cases += 1
    class CountIndices:
        def __init__(self): self.outputs = []
        def __getattr__(self, name):
            f = getattr(np, name)
            if name not in ('arange', 'repeat', 'tile'): return f
            def call(*args, **kwargs):
                result = f(*args, **kwargs)
                if np.issubdtype(result.dtype, np.integer):
                    self.outputs.append(dict(operation=name, elements=result.size, bytes=result.nbytes))
                return result
            return call
    allocations = {}
    for name, ns in (('parent', old), ('candidate', new)):
        proxy = CountIndices()
        ns['np'] = proxy
        idx = np.array([0, 2, 3])
        ns['_expand'](np.ones((1, 4)), idx, np.ones((3, 17)))
        ns['_expand_backward'](1, idx, np.ones((3, 17)), np.ones((17, 4)))
        ns['np'] = np
        allocations[name] = dict(integer_index_outputs=proxy.outputs,
                                 cumulative_allocated_bytes=sum(x['bytes'] for x in proxy.outputs))
    assert allocations['parent']['cumulative_allocated_bytes'] == 1904
    assert allocations['candidate']['cumulative_allocated_bytes'] == 0
    print(json.dumps(dict(parent=PARENT,
                         host_pass_sha256=hashlib.sha256(source.encode()).hexdigest(),
                         reproduction=reproduction, expansion_cases=cases,
                         all_destination_bitwise_cases=unique_cases,
                         finite_difference_coordinates=coordinates,
                         maximum_finite_difference_absolute_error=maximum_error,
                         layout_and_special_value_cases=layout_cases, index_allocation_inspection=allocations,
                         scope="Source-derived NumPy checks; no JAX tracing or benchmark"), indent=2))


if __name__ == "__main__":
    main()
