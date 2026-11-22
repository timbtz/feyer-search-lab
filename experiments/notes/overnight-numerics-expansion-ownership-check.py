"""Synthetic expansion pullback checks and allocation inspection; no timings."""
import ast
import json
from pathlib import Path
import subprocess
import tracemalloc

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'


def load(source):
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, ast.FunctionDef) and n.name == '_expand_backward']
    namespace = dict(np=np)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual-pullback', 'exec'), namespace)
    return namespace['_expand_backward']


def main():
    source = (ROOT/'differometor/host_pass.py').read_text()
    old = load(subprocess.check_output(['git','show',f'{PARENT}:differometor/host_pass.py'], cwd=ROOT, text=True))
    new = load(source)
    # Both production call sites explicitly transfer ownership. The first input
    # is the fresh SystemPlan.backward row result, the second a fresh addition.
    calls = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == '_expand_backward']
    assert len(calls) == 2
    assert all(any(k.arg == 'consume' and isinstance(k.value, ast.Constant) and k.value.value is True
                   for k in call.keywords) for call in calls)
    rng = np.random.default_rng(202611220443)
    checked = 0
    for rows in (1,2,5):
        for count in (0,1,3,17):
            for columns in (9,31):
                selections = ([], [0], [0,columns-1], [2,2,-1], list(range(columns)))
                for selection in selections:
                    indices = np.asarray(selection,dtype=np.int64)
                    values = rng.normal(size=(len(indices),count))
                    base = rng.normal(size=(count*rows,columns))+1j*rng.normal(size=(count*rows,columns))
                    for exceptional in (False,True):
                        test = base.copy()
                        if exceptional and test.size:
                            flat = test.reshape(-1)
                            flat[::3] = complex(-0.0,0.0)
                            flat[1::7] = complex(np.nan,-0.0)
                            flat[2::11] = complex(np.inf,-np.inf)
                        for layout in ('C','F','slice','readonly'):
                            if layout == 'slice':
                                padded = np.zeros((count*rows,columns*2),dtype=complex)
                                padded[:,::2] = test
                                array = padded[:,::2]
                            else:
                                array = np.array(test, order='C' if layout == 'readonly' else layout, copy=True)
                                if layout == 'readonly':
                                    array.flags.writeable = False
                            before = array.tobytes()
                            with np.errstate(invalid='ignore'):
                                expected = old(rows,indices,values,array)
                                preserved = new(rows,indices,values,array)
                            assert array.tobytes() == before
                            assert all(a.tobytes()==b.tobytes() for a,b in zip(expected,preserved))
                            expected_mutated = array.copy()
                            rr,cc = np.repeat(np.arange(count),len(indices)), np.tile(indices,count)
                            if array.flags.c_contiguous and array.flags.writeable:
                                expected_mutated[rr,cc] = 0
                            with np.errstate(invalid='ignore'):
                                consumed = new(rows,indices,values,array,consume=True)
                            assert all(a.tobytes()==b.tobytes() for a,b in zip(expected,consumed)), (rows,count,columns,selection,layout)
                            assert array.tobytes() == expected_mutated.tobytes()
                            assert not np.shares_memory(consumed[1],array)
                            checked += 1
    # A fresh caller-owned cotangent is created before measuring each kernel.
    # Count only the pullback's allocations; full official timing must count all
    # surrounding operations, initialization, compilation and host transfer.
    count,columns = 37,1024
    indices = np.arange(7,dtype=np.int64)
    values = np.zeros((len(indices),count))
    peaks = []
    for function, kwargs in ((old,{}),(new,{'consume':True})):
        array = rng.normal(size=(count,columns)).astype(complex)
        tracemalloc.start()
        result = function(1,indices,values,array,**kwargs)
        _,peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
    print(json.dumps(dict(bitwise_cases=checked, allocations_parent_candidate_bytes=peaks,
                          removed_row_copy_bytes=count*columns*np.dtype(complex).itemsize),indent=2))


if __name__ == '__main__':
    main()
