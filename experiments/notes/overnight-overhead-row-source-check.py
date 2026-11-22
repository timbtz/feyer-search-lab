"""Candidate34 parameter-row gather check; supervisor environment only.

Small synthetic metadata, primals and VJPs. No benchmark or timing code.
"""
import ast
import copy
from pathlib import Path
import numpy as np
import jax
import jax.numpy as jnp
from jax import lax

jax.config.update('jax_enable_x64', True)
jax.config.update('jax_enable_compilation_cache', False)
root = Path(__file__).resolve().parents[2]
plan_tree = ast.parse((root / 'differometor/host_pass.py').read_text())
layout_node = next(n for n in plan_tree.body if isinstance(n, ast.ClassDef) and n.name == 'ParameterLayout')
# Digest content is irrelevant to this focused row-index test.
scope = dict(np=np, jnp=jnp, lax=lax, _digest=lambda *args: '')
exec(compile(ast.Module(body=[layout_node], type_ignores=[]), '<layout>', 'exec'), scope)
Layout = scope['ParameterLayout']
tree = ast.parse((root / 'differometor/simulate.py').read_text())
helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('_static_take', '_static_set')]
exec(compile(ast.Module(body=helpers, type_ignores=[]), '<helpers>', 'exec'), scope)
simulate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'simulate')
branch = next(n for n in simulate.body if isinstance(n, ast.If) and 'layout.applies' in ast.unparse(n.test))
start = next(i for i, n in enumerate(branch.body) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'row')
stop = next(i for i, n in enumerate(branch.body) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'inputs_to_link')
wrapper = ast.parse('def candidate(layout, parameters, optimized_parameters):\n    pass').body[0]
wrapper.body = copy.deepcopy(branch.body[start:stop]) + [ast.Return(value=ast.Name(id='row', ctx=ast.Load()))]
exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])), '<actual insertion>', 'exec'), scope)
candidate = scope['candidate']


def reference(layout, parameters, optimized_parameters):
    row = parameters.reshape(parameters.shape[1:])
    return scope['_static_set'](row, layout.optimized_parameter_indices,
                                scope['_static_take'](optimized_parameters, layout.optimized_value_indices))


def arrays(size, destinations, value_indices):
    return dict(parameters=np.zeros((1, size)),
                optimized_parameter_indices=np.asarray(destinations, dtype=np.int64),
                optimized_value_indices=np.asarray(value_indices, dtype=np.int64),
                linked_indices=np.array([], dtype=np.int64),
                indices_to_link=np.array([], dtype=np.int64),
                qhd_parameter_indices=np.array([], dtype=np.int64),
                qhd_placing_indices=np.empty((0, 3), dtype=np.int64))


rng = np.random.default_rng(3434)
checked = 0
for size in (1, 3, 7, 12):
    for destinations in ([], [0], [size - 1], list(range(size)),
                         list(range(size - 1, -1, -1)), list(range(0, size, 2))):
        # Share a physical input between multiple row destinations when possible.
        value_indices = [i % 2 for i in range(len(destinations))]
        layout = Layout.from_arrays(arrays(size, destinations, value_indices))
        assert layout is not None and layout.optimized_row_sources is not None
        for base_complex in (False, True):
            for optimized_complex in (False, True):
                base = rng.normal(size=(1, size))
                optimized = rng.normal(size=3)
                if base_complex:
                    base = base + 1j * rng.normal(size=base.shape)
                if optimized_complex:
                    optimized = optimized + 1j * rng.normal(size=optimized.shape)
                base[0, 0] = -0.0
                optimized[0] = 0.0
                bars = rng.normal(size=size)
                if base_complex:
                    bars = bars + 1j * rng.normal(size=size)
                base, optimized, bars = map(jnp.asarray, (base, optimized, bars))
                assert layout.applies(base, optimized)

                def evaluate(function):
                    def run(p, x, cotangent):
                        result, pullback = jax.vjp(lambda a, b: function(layout, a, b), p, x)
                        return result, pullback(cotangent)
                    return jax.jit(run)(base, optimized, bars)

                got, want = evaluate(candidate), evaluate(reference)
                np.testing.assert_array_equal(np.asarray(got[0]), np.asarray(want[0]))
                for part in (np.real, np.imag):
                    np.testing.assert_array_equal(np.signbit(part(np.asarray(got[0]))),
                                                  np.signbit(part(np.asarray(want[0]))))
                for a, b in zip(got[1], want[1]):
                    np.testing.assert_allclose(np.asarray(a), np.asarray(b), rtol=1e-14, atol=1e-14)
                checked += 1

for destinations, values in (([-1], [0]), ([4], [0]), ([0, 0], [0, 1]), ([0], [-1])):
    assert Layout.from_arrays(arrays(4, destinations, values)) is None
layout = Layout.from_arrays(arrays(4, [0], [7]))
assert layout is not None and not layout.applies(jnp.zeros((1, 4)), jnp.zeros(3))
# Directly constructed layouts keep the existing insertion path.
layout = Layout(4, [1], [0], [], [], [], np.empty((0, 3), dtype=np.int64))
assert layout.optimized_row_sources is None
np.testing.assert_array_equal(candidate(layout, jnp.zeros((1, 4)), jnp.ones(1)),
                              reference(layout, jnp.zeros((1, 4)), jnp.ones(1)))
print(f'PASS: {checked} primal/VJP cases and six layout guard/fallback checks; no timing claim')
