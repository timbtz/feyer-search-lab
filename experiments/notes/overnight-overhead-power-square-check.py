"""Candidate19 synthetic checks; supervisor runs in the fixed JAX environment.

No fixtures or timing. Compares the actual power_detector with its predecessor,
including JIT and reverse derivatives at signed zero and varied finite scales.
"""
import ast
from pathlib import Path
import jax
import jax.numpy as jnp
import numpy as np

jax.config.update('jax_enable_x64', True)
jax.config.update('jax_enable_compilation_cache', False)
source = ast.parse((Path(__file__).resolve().parents[2] / 'differometor/components.py').read_text())
function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'power_detector')
namespace = {'jnp': jnp, 'EPSILON_0C': 1}
exec(compile(ast.Module(body=[function], type_ignores=[]), 'actual_power_detector', 'exec'), namespace)
candidate = namespace['power_detector']
reference = lambda x: 0.5 * jnp.abs(x) ** 2
rng = np.random.default_rng(1901)
count = 0
for dtype in (np.float64, np.complex128, np.float32, np.complex64):
    is_complex = np.issubdtype(dtype, np.complexfloating)
    wide = np.dtype(dtype).itemsize > (8 if is_complex else 4)
    tol = 3e-15 if wide else 2e-6
    scales = (1e-150, 1., 1e150) if wide else (1e-15, 1., 1e15)
    for shape in ((), (0,), (7,), (3, 4)):
        for scale in scales:
            real = np.asarray(rng.normal(size=shape), dtype=np.float64)
            imag = np.asarray(rng.normal(size=shape), dtype=np.float64)
            values = (real + 1j * imag if is_complex else real) * scale
            values = np.asarray(values, dtype=dtype)
            if values.size:
                values.reshape(-1)[0] = complex(-0., -0.) if is_complex else -0.
            x = jnp.asarray(values)
            cot = jnp.asarray(rng.normal(size=shape), dtype=jnp.real(x).dtype)
            def evaluate(fn):
                def apply(values, cotangent):
                    result, pullback = jax.vjp(fn, values)
                    return result, pullback(cotangent)[0]
                return jax.jit(apply)(x, cot)
            got, want = evaluate(candidate), evaluate(reference)
            for a, b in zip(got, want):
                a, b = np.asarray(a), np.asarray(b)
                assert np.all(np.isfinite(a)) and np.all(np.isfinite(b))
                np.testing.assert_allclose(a, b, rtol=tol, atol=0)
                if a.size:
                    assert a.reshape(-1)[0] == b.reshape(-1)[0] == 0
            count += 1
# Pure imaginary and equal-component fields exercise different magnitude paths.
x = jnp.asarray([0j, complex(-0., 0.), 2j, -3j, 2+2j, -2-2j], dtype=jnp.complex128)
for fn in (candidate, reference):
    out, back = jax.vjp(fn, x)
    np.testing.assert_allclose(np.asarray(out), [0, 0, 2, 4.5, 4, 4], rtol=3e-15, atol=0)
    np.testing.assert_allclose(np.asarray(back(jnp.ones(6))[0]), np.conj(np.asarray(x)), rtol=3e-15, atol=0)
print(f'PASS: {count} JIT primal/VJP cases plus zero/axis/diagonal checks; no optical or timing claim')
