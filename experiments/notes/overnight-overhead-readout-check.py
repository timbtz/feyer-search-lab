"""Synthetic signal-detector equivalence; run through the supervisor environment.

No fixtures, official timings, or simulator configuration changes. Compare the
joint split with the original slices, including JAX's own derivative conventions.
"""

import json
from collections import Counter

import jax
import jax.numpy as jnp
import numpy as np

from differometor.components import signal_detector

jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)


def original(carrier, signal):
    upper = jnp.conj(carrier) * signal[: carrier.shape[0]]
    lower = carrier * signal[carrier.shape[0] : 2 * carrier.shape[0]]
    return upper + lower


zero_sign_differences = 0
comparisons = 0


def same(actual, expected):
    global zero_sign_differences, comparisons
    aa, ta = jax.tree_util.tree_flatten(actual)
    bb, tb = jax.tree_util.tree_flatten(expected)
    assert ta == tb
    for a, b in zip(aa, bb):
        a, b = np.asarray(a), np.asarray(b)
        assert a.dtype == b.dtype
        # Exact numerical equality including NaN locations and infinity signs.
        # Track signed zeros separately: pad-plus-add can canonicalize -0.
        np.testing.assert_array_equal(a, b)
        parts = ((a.real, b.real), (a.imag, b.imag)) if np.iscomplexobj(a) else ((a, b),)
        for x, y in parts:
            zero_sign_differences += int(np.count_nonzero(
                (x == 0) & (y == 0) & (np.signbit(x) != np.signbit(y))))
        comparisons += 1


rng = np.random.default_rng(91823)


def values(shape, complex_input):
    x = rng.normal(size=shape)
    if complex_input:
        x = x + 1j * rng.normal(size=shape)
    return jnp.asarray(x)


def check(carrier, signal):
    dc = values(carrier.shape, jnp.iscomplexobj(carrier))
    ds = values(signal.shape, jnp.iscomplexobj(signal))
    output = original(carrier, signal)
    cotangent = values(output.shape, jnp.iscomplexobj(output))
    for compiled in (False, True):
        def wrap(f):
            return jax.jit(f) if compiled else f

        same(wrap(signal_detector)(carrier, signal), wrap(original)(carrier, signal))

        def jvp(f):
            return wrap(lambda c, s, c_dot, s_dot: jax.jvp(f, (c, s), (c_dot, s_dot)))(
                carrier, signal, dc, ds)

        same(jvp(signal_detector), jvp(original))

        def vjp(f):
            return wrap(lambda c, s, g: jax.vjp(f, c, s)[1](g))(
                carrier, signal, cotangent)

        same(vjp(signal_detector), vjp(original))


# Broadcasted sweeps, mechanical tails, vectors, mixed ranks, empty outputs,
# and a short lower sideband that the original broadcasts to the carrier shape.
shapes = [((4, 1), (11, 5)), ((3,), (6,)), ((3,), (8, 3)),
          ((3, 1, 2), (8, 4, 2)), ((0,), (3,)), ((3,), (4,)),
          ((1,), (0,))]
for cshape, sshape in shapes:
    for complex_c, complex_s in ((False, False), (True, False), (False, True), (True, True)):
        check(values(cshape, complex_c), values(sshape, complex_s))

# Both signed real zeros and complex zeros with independently signed components.
real_edge = np.array([0.0, -0.0, 1.0, -1.0])
complex_edge = real_edge.astype(np.complex128)
complex_edge.imag = real_edge[::-1]
for edge in (real_edge, complex_edge):
    check(jnp.asarray(edge), jnp.asarray(np.concatenate([edge[::-1], edge, edge[:1]])))

# Non-finite behavior remains evidence about compatibility, not physical validity.
for edge in (np.array([np.inf, -np.inf, np.nan, 0.0]),
             np.array([complex(np.inf, 1), complex(1, np.inf), complex(np.nan, 0), 0j])):
    check(jnp.asarray(edge), jnp.asarray(np.concatenate([edge[::-1], edge])))

c, s = values((2, 3, 1), True), values((2, 8, 7), True)
same(jax.jit(jax.vmap(signal_detector))(c, s), jax.jit(jax.vmap(original))(c, s))

# The rewrite uses built-in JAX transformations, including second derivatives
# for this standalone readout. This says nothing about the host simulator's VJP.
def scalar(f, x):
    y = f(x[:3], x[3:])
    return jnp.sum(y * y)

x = values((11,), False)
same(jax.jit(jax.hessian(lambda x: scalar(signal_detector, x)))(x),
     jax.jit(jax.hessian(lambda x: scalar(original, x)))(x))


def primitive_counts(value):
    counts = Counter()
    def visit(v):
        if hasattr(v, "jaxpr"):
            visit(v.jaxpr)
        elif hasattr(v, "eqns"):
            for eq in v.eqns:
                counts[eq.primitive.name] += 1
                visit(eq.params)
        elif isinstance(v, dict):
            for child in v.values():
                visit(child)
        elif isinstance(v, (tuple, list)):
            for child in v:
                visit(child)
    visit(value)
    return dict(sorted(counts.items()))


c, s = values((4, 1), True), values((11, 5), True)
g = values((4, 5), True)
ir = {}
for name, f in (("original", original), ("joint_split", signal_detector)):
    ir[name] = primitive_counts(jax.make_jaxpr(
        lambda c, s, g: jax.vjp(f, c, s)[1](g))(c, s, g))
print(json.dumps({"passed": True, "array_comparisons": comparisons,
                  "zero_sign_differences": zero_sign_differences,
                  "vjp_primitive_counts": ir}, indent=2))
