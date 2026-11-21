"""Focused regression tests for the interpreter compatibility candidate.

Local NumPy-only rule checks:
  PYTHON experiments/notes/host_compatibility_probe.py --numpy-only
Pinned-environment JAX comparisons and fallback check:
  /workspace/venv-feyer/bin/python experiments/notes/host_compatibility_probe.py

No official benchmark, shared environment, or evaluator state is modified.
"""
import argparse
import ast
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument('--numpy-only', action='store_true')
args, remaining = parser.parse_known_args()

# Evaluate the actual checked-in NumPy rule without importing unavailable JAX on
# the coordinator. The pinned test below exercises the full interpreter instead.
tree = ast.parse((ROOT / 'differometor/host.py').read_text())
names = {'_LINEAR', '_NON_DIFFERENTIABLE'}
nodes = [node for node in tree.body if
         isinstance(node, ast.FunctionDef) and node.name == '_tangent' or
         isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)]
namespace = {'np': np}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / 'differometor/host.py'), 'exec'), namespace)
tangent = namespace['_tangent']


class NumpyAbsRules(unittest.TestCase):
    def test_real_signed_zero_and_nonzero_tangents(self):
        x = np.array([-2., -0., 0., 3.])
        t = np.array([4., 5., -6., 7.])
        actual = tangent('abs', {}, [x], [t], [np.abs(x)], 0)[0]
        np.testing.assert_array_equal(actual, [-4., 5., -6., 7.])

    def test_complex_zero_and_directions(self):
        x = np.array([0j, 3 + 4j, -3 + 4j], dtype=np.complex128)
        t = np.array([2 + 3j, 2 - 1j, 2 - 1j], dtype=np.complex128)
        actual = tangent('abs', {}, [x], [t], [np.abs(x)], 0)[0]
        self.assertTrue(np.isfinite(actual).all())
        np.testing.assert_allclose(actual, [0., .4, -2.], rtol=1e-15, atol=1e-15)


if not args.numpy_only:
    import jax
    import jax.numpy as jnp
    jax.config.update('jax_enable_x64', True)
    jax.config.update('jax_enable_compilation_cache', False)
    from differometor.host import kernel, unsupported_primitives

    class PinnedJaxInterpreter(unittest.TestCase):
        def test_real_abs_values_and_jacobian(self):
            fn = lambda v: jnp.abs(v[0])
            points = np.array([[-2.], [-0.], [0.], [3.]])
            value, jac = kernel(fn, (1,))(points)
            expected_value = np.asarray(jax.vmap(fn)(jnp.asarray(points)))
            expected_jac = np.asarray(jax.vmap(jax.jacfwd(fn))(jnp.asarray(points)))
            np.testing.assert_array_equal(value, expected_value)
            np.testing.assert_array_equal(np.moveaxis(jac, 0, -1), expected_jac)

        def test_complex_abs_of_two_real_inputs(self):
            fn = lambda v: jnp.abs(jax.lax.complex(v[0], v[1]))
            points = np.array([[0., 0.], [3., 4.], [-3., 4.], [2., 0.]])
            value, jac = kernel(fn, (2,))(points)
            expected_value = np.asarray(jax.vmap(fn)(jnp.asarray(points)))
            expected_jac = np.asarray(jax.vmap(jax.jacfwd(fn))(jnp.asarray(points)))
            self.assertTrue(np.isfinite(jac).all())
            np.testing.assert_allclose(value, expected_value, rtol=1e-15, atol=1e-15)
            np.testing.assert_allclose(np.moveaxis(jac, 0, -1), expected_jac, rtol=1e-15, atol=1e-15)

        def test_custom_jvp_is_rejected_not_silently_rederived(self):
            @jax.custom_jvp
            def clipped(x):
                return jnp.maximum(x, 0.)

            @clipped.defjvp
            def clipped_jvp(primals, tangents):
                (x,), (xdot,) = primals, tangents
                return clipped(x), jnp.where(x > 0, xdot, 0.)

            fn = jax.jit(lambda v: clipped(v[0]))
            self.assertEqual(float(jax.grad(lambda x: clipped(x))(0.)), 0.)
            self.assertEqual(float(jax.grad(lambda x: jnp.maximum(x, 0.))(0.)), .5)
            with self.assertRaisesRegex(NotImplementedError, 'custom_jvp_call'):
                kernel(fn, (1,))

        def test_custom_vjp_is_rejected(self):
            @jax.custom_vjp
            def special(x):
                return x * x
            def forward(x):
                return special(x), x
            def backward(x, cotangent):
                return (3 * x * cotangent,)
            special.defvjp(forward, backward)
            fn = lambda v: special(v[0])
            self.assertEqual(float(jax.grad(special)(2.)), 6.)
            with self.assertRaisesRegex(NotImplementedError, 'custom_vjp_call'):
                kernel(fn, (1,))

        def test_component_custom_jvp_selects_traced_fallback(self):
            # Override only the interpreter registry with an equivalent wrapper.
            # Build instructions look functions up by identity in the shared
            # registry, so mutating that list would invalidate the fixture.
            import json
            import warnings
            from unittest.mock import patch
            import differometor as df
            import differometor.host as host
            from differometor.setups import constrain_inter_grid_cell_spaces
            fixture = json.loads((ROOT / 'examples/data/uifo_800_3000.json').read_text())
            setup = df.Setup.from_data(fixture)
            pairs = constrain_inter_grid_cell_spaces(setup.parameters,
                        ['reflectivity', 'tuning', 'db', 'angle', 'power', 'mass', 'length'])
            freqs = jnp.array([800., 1300., 3000.])
            ordinary, *_ = df.run_build_step(setup, [('f', 'frequency')], freqs, pairs)
            self.assertIsNotNone(ordinary['plan'].host_simulate)
            index = ordinary['plan'].carrier_groups[0][0]
            original = host.FUNCTIONS[index]
            @jax.custom_jvp
            def wrapped(x):
                return original(x)
            @wrapped.defjvp
            def wrapped_jvp(primals, tangents):
                return jax.jvp(original, primals, tangents)
            interpreter_functions = list(host.FUNCTIONS)
            interpreter_functions[index] = wrapped
            with patch.object(host, 'FUNCTIONS', interpreter_functions):
                with warnings.catch_warnings(record=True) as messages:
                    warnings.simplefilter('always')
                    fallback, *_ = df.run_build_step(setup, [('f', 'frequency')], freqs, pairs)
                self.assertIsNone(fallback['plan'].host_simulate)
                self.assertTrue(any('custom_jvp_call' in str(m.message) for m in messages))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *remaining])
