"""Synthetic callback-layout differential check; run in the fixed environment.

Loads only the current callback boundary definitions into an isolated namespace
with toy host functions. Compares with the previous boundary, including JIT/VJP
and sequential vmap. Does not patch any simulator, benchmark or validation module.
No timings, fixtures, full simulation or numerical solver are involved.
"""

import ast
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)
jax.config.update("jax_enable_compilation_cache", False)


class Plan:
    def __init__(self, carrier_size, signal_size):
        self.structure = SimpleNamespace(carrier=SimpleNamespace(size=carrier_size),
                                         signal=SimpleNamespace(size=signal_size))


def bases(plan, inputs):
    bc = inputs[1].shape[1]
    bs = inputs[2].shape[1] * bc
    detectors = inputs[6].shape[0]
    cn, sn = plan.structure.carrier.size, plan.structure.signal.size
    return (np.arange(bc * cn).reshape(bc, cn) + 1 + 2j,
            np.arange(bs * sn).reshape(bs, sn) + 2 - 3j,
            np.arange(detectors * bs).reshape(detectors, bs) + 3.)


def forward(plan, *inputs):
    t = sum(np.sum(np.real(x)) for x in inputs)
    carrier, signal, noise = (b * t for b in bases(plan, inputs))
    bs, sn = signal.shape
    detectors = noise.shape[0]
    cov = np.full((bs, detectors, sn), t + 4j, dtype=np.complex128)
    weights = np.full_like(cov, 2 * t - 5j)
    return carrier, signal, noise, cov, weights


def backward(plan, *arguments):
    inputs, residuals, bars = arguments[:7], arguments[7:12], arguments[12:]
    for actual, expected in zip(residuals, forward(plan, *inputs)):
        np.testing.assert_array_equal(actual, expected)
    assert len(bars) == 3
    total = 0.
    for basis, cotangent in zip(bases(plan, inputs), bars):
        assert basis.shape == cotangent.shape
        total += np.sum(np.real(basis * cotangent))
    return tuple(np.full_like(x, total) for x in inputs)


# Execute the implementation's actual boundary functions, with only their host
# math dependencies replaced by toy functions in this independent namespace.
path = Path(__file__).resolve().parents[2] / "differometor" / "host_pass.py"
names = {"_shapes", "_transposed", "host_forward_transposed", "host_backward_transposed",
         "_forward_call", "host_pass", "_host_pass_fwd", "_host_pass_bwd"}
nodes = [node for node in ast.parse(path.read_text()).body
         if isinstance(node, ast.FunctionDef) and node.name in names]
assert {node.name for node in nodes} == names
namespace = dict(jax=jax, jnp=jnp, np=np, partial=partial, host_forward=forward, host_backward=backward)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
candidate = namespace["host_pass"]
candidate.defvjp(namespace["_host_pass_fwd"], namespace["_host_pass_bwd"])


def old_call(plan, *inputs):
    new_shapes = namespace["_shapes"](plan, inputs[1], inputs[2], inputs[6])
    shapes = tuple(new_shapes[i] for i in (3, 4, 2, 5, 6))
    return jax.pure_callback(partial(forward, plan), shapes, *inputs, vmap_method="sequential")


@partial(jax.custom_vjp, nondiff_argnums=(0,))
def previous(plan, *inputs):
    carrier, signal, noise, _, _ = old_call(plan, *inputs)
    return carrier, signal, noise


def old_fwd(plan, *inputs):
    outputs = old_call(plan, *inputs)
    return outputs[:3], (inputs, outputs)


def old_bwd(plan, residuals, bars):
    inputs, outputs = residuals
    shapes = tuple(jax.ShapeDtypeStruct(x.shape, x.dtype) for x in inputs)
    return jax.pure_callback(partial(backward, plan), shapes, *inputs, *outputs, *bars,
                             vmap_method="sequential")


previous.defvjp(old_fwd, old_bwd)


def compare(a, b):
    la, ta = jax.tree_util.tree_flatten(a)
    lb, tb = jax.tree_util.tree_flatten(b)
    assert ta == tb
    for x, y in zip(la, lb):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape and x.dtype == y.dtype
        np.testing.assert_array_equal(x, y)


for bc, bs_per_carrier, detectors, cn, sn in ((1, 1, 1, 3, 4), (1, 3, 2, 4, 5), (2, 2, 1, 5, 3)):
    plan = Plan(cn, sn)
    inputs = tuple(jnp.asarray(x) for x in (
        np.array([[1+2j, 3-4j]]), np.ones((1, bc)), np.ones((1, bs_per_carrier)) * 2,
        np.array([2-1j, 3+1j]), np.array([1+1j, 4-1j, 2+2j]), np.array([1-3j]),
        np.ones((detectors, 1, sn), dtype=np.complex128)))

    def public(function, transpose, *args):
        c, s, n = function(plan, *args)
        return (c.T, s.T, n.squeeze()) if transpose else (c, s, n.squeeze())

    old = partial(public, previous, True)
    new = partial(public, candidate, False)

    def result_and_vjp(function, *args):
        result, pullback = jax.vjp(function, *args)
        bars = tuple(jnp.ones_like(x) * (1 + 2j if jnp.iscomplexobj(x) else 3) for x in result)
        return result, pullback(bars)

    compare(jax.jit(old)(*inputs), jax.jit(new)(*inputs))
    compare(jax.jit(partial(result_and_vjp, old))(*inputs),
            jax.jit(partial(result_and_vjp, new))(*inputs))
    batched = tuple(jnp.stack((x, x * 2)) for x in inputs)
    compare(jax.jit(jax.vmap(partial(result_and_vjp, old)))(*batched),
            jax.jit(jax.vmap(partial(result_and_vjp, new)))(*batched))
    print("passed callback primal/VJP/sequential-vmap", (bc, bs_per_carrier, detectors, cn, sn))
