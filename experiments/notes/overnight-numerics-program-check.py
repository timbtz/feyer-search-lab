"""Static Jacobian-program inspection. Small synthetic cases; no benchmarks/timing."""
import ast
from collections import Counter
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import runpy
import sys
import tracemalloc
import types

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('differometor.host_program', ROOT / 'differometor/host_program.py')
programs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = programs
spec.loader.exec_module(programs)
# Reuse the preserved comprehensive Dual tests. Its old shim-level work counter
# does not observe program execution, so deliberately omit that metric here.
output = io.StringIO()
with redirect_stdout(output):
    checked = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-directions-check.py'))
results = [ast.literal_eval(line) for line in output.getvalue().splitlines()]
results[0].pop('surface_transcendental_work')
for result in results:
    print(result)
load = checked['load']
parent_source = checked['parent_host']
new_source = (ROOT / 'differometor/host.py').read_text()
old, new = load(parent_source), load(new_source)
equal = checked['loader']['check_equal']
rng = np.random.default_rng(2026112230)

# Explicitly test empty batches, changing numbers of input columns, repeated and
# negative seed slots, strided inputs and with_outputs=False after cache hits.
extra_checks = 0
with np.errstate(all='ignore'):
    for shape in ((0, 7), (3, 0, 7), (2, 9), (5, 3, 7)):
        inputs = rng.uniform(.1, .8, shape).astype(np.complex128)
        for f in range(19):
            for slots in ((), (0,), (-1, 0, 0), tuple(range(shape[-1]))):
                for case in (inputs, inputs[..., ::-1], inputs + .03j):
                    a = old['function_jacobian'](f, slots, case, with_outputs=False)
                    b = new['function_jacobian'](f, slots, case, with_outputs=False)
                    assert a[0] is None and b[0] is None
                    equal(a[1:], b[1:])
                    extra_checks += 1

# Count actual NumPy transcendental ufunc invocations, including derivative slopes
# (the older shim-level counter excludes the slopes). No elapsed time is measured.
transcendentals = {'exp', 'sqrt', 'sin', 'cos', 'arcsin', 'cosh', 'sinh'}
counts = {'parent': Counter(), 'candidate': Counter()}
class CountedNumpy:
    def __getattr__(self, name):
        value = getattr(np, name)
        if name not in transcendentals:
            return value
        def call(*args, **kwargs):
            counts['parent'][name] += 1
            return value(*args, **kwargs)
        return call
# Recreate the host loader with an isolated proxy namespace; NumPy itself and all
# production modules stay unchanged.
counted_load = types.FunctionType(load.__code__, {**load.__globals__, 'np': CountedNumpy()})
counted_parent = counted_load(parent_source)
f = next(i for i, function in enumerate(new['HOST_FUNCTIONS']) if function.__name__ == 'surface')
slots = tuple(range(7))
program = programs.jacobian_program(new['HOST_FUNCTIONS'][f], slots, 7, new['Dual'], new['_Slots'])
original_nodes = program.nodes
nodes = list(original_nodes)
for index, node in enumerate(nodes):
    if node[0] != 'operation':
        continue
    function = node[1]
    if isinstance(function, np.ufunc) and function.__name__ in transcendentals:
        def call(*args, function=function):
            counts['candidate'][function.__name__] += 1
            return function(*args)
        nodes[index] = ('operation', call, node[2])
program.nodes = tuple(nodes)
inputs = rng.uniform(.1, .8, (3, 11, 7)).astype(np.complex128)
counts['parent'].clear()
try:
    with np.errstate(all='ignore'):
        a = counted_parent['function_jacobian'](f, slots, inputs, with_outputs=False)
        b = new['function_jacobian'](f, slots, inputs, with_outputs=False)
        equal(a[1:], b[1:])
finally:
    program.nodes = original_nodes
assert 0 < sum(counts['candidate'].values()) < sum(counts['parent'].values())
assert all(node[0] != 'constant' or np.isscalar(node[1]) for node in program.nodes)

# Include first graph construction and plan construction in the cold allocation
# probe; warm probe shows retained-temporary cost independently. Neither is an
# official workload or a speed measurement.
def peak(function):
    tracemalloc.start()
    try:
        with np.errstate(all='ignore'):
            function()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
probe = rng.uniform(.1, .8, (17, 23, 7)).astype(np.complex128)
old_peak = peak(lambda: old['function_jacobian'](f, slots, probe, with_outputs=False))
programs.jacobian_program.cache_clear()
cold_peak = peak(lambda: new['function_jacobian'](f, slots, probe, with_outputs=False))
warm_peak = peak(lambda: new['function_jacobian'](f, slots, probe, with_outputs=False))
print(dict(extra_checks=extra_checks, actual_transcendental_calls={k: dict(v) for k,v in counts.items()},
           parent_peak_bytes=old_peak, candidate_cold_peak_bytes=cold_peak,
           candidate_warm_peak_bytes=warm_peak, cache_bound=programs.jacobian_program.cache_info().maxsize))
