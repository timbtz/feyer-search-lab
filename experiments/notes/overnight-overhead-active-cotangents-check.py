"""Supervisor-only synthetic check of active-input callback results.

No benchmark, fixture, solver or simulator module is patched. Actual boundary
AST is executed in an isolated namespace with analytic toy host functions.
Run using the fixed evaluator environment; local runtime checks are unexecuted.
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



path = Path(__file__).resolve().parents[2] / "differometor" / "host_pass.py"
names = {"_shapes", "_forward_call", "host_pass", "_ActiveInputs", "_host_pass_fwd",
         "_backward_active", "_host_pass_bwd"}
nodes = [node for node in ast.parse(path.read_text()).body
         if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
assert {node.name for node in nodes} == names
namespace = dict(jax=jax, jnp=jnp, np=np, partial=partial, host_forward=forward, host_backward=backward)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
candidate = namespace["host_pass"]
candidate.defvjp(namespace["_host_pass_fwd"], namespace["_host_pass_bwd"], symbolic_zeros=True)


@partial(jax.custom_vjp, nondiff_argnums=(0,))
def previous(plan, *inputs):
    return namespace["_forward_call"](plan, *inputs)[:3]


def old_fwd(plan, *inputs):
    outputs = namespace["_forward_call"](plan, *inputs)
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


plan = Plan(3, 4)
inputs = tuple(jnp.asarray(x) for x in (
    np.array([[0.+0.j, -0.+0.j]]), np.zeros((1, 1)), np.zeros((1, 2)),
    np.zeros(2, dtype=np.complex128), np.zeros(3, dtype=np.complex128),
    np.zeros(1, dtype=np.complex128), np.zeros((2, 1, 4), dtype=np.complex128)))
# Zero physical values are still differentiated. All toy derivatives are nonzero.
active_sets = [(i,) for i in range(7)] + [tuple(range(7)), (0, 3, 6), (1, 2, 4, 5)]
output_sets = [(0,), (1,), (2,), (0, 1, 2)]
checks = 0
for active in active_sets:
    for selected_outputs in output_sets:
        def loss(function, *all_inputs):
            outputs = function(plan, *all_inputs)
            return sum(jnp.sum(jnp.real(outputs[i])) for i in selected_outputs)

        old_grad = jax.grad(partial(loss, previous), argnums=active)
        new_grad = jax.grad(partial(loss, candidate), argnums=active)
        # Inspect untimed toy JAXPR: forward has five outputs, backward only K.
        graph = jax.make_jaxpr(new_grad)(*inputs).jaxpr
        arities = [len(eq.outvars) for eq in graph.eqns if eq.primitive.name == "pure_callback"]
        assert arities == [5, len(active)], arities
        compare(jax.jit(old_grad)(*inputs), jax.jit(new_grad)(*inputs))
        checks += 1

# A stop_gradient argument must remain inactive even when it was requested
# at the enclosing API; all other requested gradients must be preserved.
def stopped(function, *args):
    values = list(args)
    values[3] = jax.lax.stop_gradient(values[3])
    return sum(jnp.sum(jnp.real(x)) for x in function(plan, *values))
compare(jax.jit(jax.grad(partial(stopped, previous), argnums=tuple(range(7))))(*inputs),
        jax.jit(jax.grad(partial(stopped, candidate), argnums=tuple(range(7))))(*inputs))
checks += 1

# Explicit VJP with all inputs active and zero/nonzero array cotangents.
def value_and_pullback(function, *args):
    output, pullback = jax.vjp(partial(function, plan), *args)
    bars = (jnp.ones_like(output[0]) * (1 + 2j), jnp.zeros_like(output[1]),
            jnp.ones_like(output[2]) * 3)
    return output, pullback(bars)
old_vjp = partial(value_and_pullback, previous)
new_vjp = partial(value_and_pullback, candidate)
compare(jax.jit(old_vjp)(*inputs), jax.jit(new_vjp)(*inputs))
checks += 1
batched = tuple(jnp.stack((x, x + 1)) for x in inputs)
compare(jax.jit(jax.vmap(old_vjp))(*batched), jax.jit(jax.vmap(new_vjp))(*batched))
checks += 1
compare(jax.jit(partial(previous, plan))(*inputs), jax.jit(partial(candidate, plan))(*inputs))
checks += 1
print(f"passed {checks} synthetic boundary comparisons, including 40 callback-arity checks")
