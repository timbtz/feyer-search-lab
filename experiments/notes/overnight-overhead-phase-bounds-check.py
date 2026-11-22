"""Candidate20: synthetic JIT/VJP scatter checks for supervisor execution.
No optical fixtures or timings; uses the actual helper and scatter expression.
"""
import ast
import copy
from pathlib import Path
import jax
import jax.numpy as jnp
from jax import lax
import numpy as np

jax.config.update('jax_enable_x64', True)
jax.config.update('jax_enable_compilation_cache', False)
source = ast.parse((Path(__file__).resolve().parents[2] / 'differometor/simulate.py').read_text())
functions = {n.name: n for n in source.body if isinstance(n, ast.FunctionDef)}
namespace = dict(np=np, jnp=jnp, lax=lax)
exec(compile(ast.Module(body=[functions['_phase_scatter_mode']], type_ignores=[]), 'actual_mode', 'exec'), namespace)
scatter = next(n for n in functions['_simulate_host_pass'].body if isinstance(n, ast.Assign)
               and ast.unparse(n.targets[0]) == 'noise_selection_vectors')

def make_function(original):
    body = copy.deepcopy(scatter)
    if original:
        body.value.keywords = [k for k in body.value.keywords if k.arg != 'mode']
    fn = ast.parse('def apply(noise_selection_vectors, qhd_phase_values, qhd_placing_indices):\n    return noise_selection_vectors').body[0]
    fn.body.insert(0, body)
    scope = dict(namespace)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), 'actual_scatter', 'exec'), scope)
    return scope['apply']

candidate, reference = make_function(False), make_function(True)
shape = (2, 3, 4)
rng = np.random.default_rng(2001)
cases = [([], True), ([[0, 0, 0]], True), ([[0, 1, 3], [1, 2, 0]], True),
         ([[-1, 1, 2]], False), ([[2, 0, 0]], False), ([[0, 3, 0], [1, 1, 4]], False)]
count = 0
for raw, in_bounds in cases:
    indices = np.asarray(raw, dtype=np.int64).reshape(-1, 3)
    expected = lax.GatherScatterMode.PROMISE_IN_BOUNDS if in_bounds else None
    assert namespace['_phase_scatter_mode'](indices, shape) == expected
    for dynamic in (False, True):
        values = jnp.asarray(rng.normal(size=shape) + 1j*rng.normal(size=shape))
        values = values.at[0, 0, 0].set(0j)
        phases = jnp.asarray(np.exp(1j*rng.normal(size=len(indices))))
        if len(indices):
            phases = phases.at[0].set(0j)  # a current zero retains derivatives
        cot = jnp.asarray(rng.normal(size=shape) + 1j*rng.normal(size=shape))
        def evaluate(fn):
            def apply(x, p, c, i):
                placement = i if dynamic else indices
                y, pullback = jax.vjp(lambda a, b: fn(a, b, placement), x, p)
                return y, pullback(c)
            return jax.jit(apply)(values, phases, cot, jnp.asarray(indices))
        for got, want in zip(jax.tree.leaves(evaluate(candidate)), jax.tree.leaves(evaluate(reference))):
            np.testing.assert_array_equal(np.asarray(got), np.asarray(want))
        count += 1
assert namespace['_phase_scatter_mode'](np.zeros((1, 3), dtype=float), shape) is None
assert namespace['_phase_scatter_mode'](np.zeros((3,), dtype=int), shape) is None
assert namespace['_phase_scatter_mode'](np.zeros((1, 3), dtype=int), (2, 3)) is None
assert namespace['_phase_scatter_mode'](jnp.zeros((1, 3), dtype=int), shape) is None
print(f'PASS: {count} static/dynamic JIT primal/VJP cases and fallback checks; no timing claim')
