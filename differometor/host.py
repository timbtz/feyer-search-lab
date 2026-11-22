"""Host (NumPy) evaluation of component transfer functions with a JAX-linear JVP.

The sparse path evaluates 19 component functions (complex sqrt, asin, exp, ...)
for every matrix entry. As XLA programs, their tracing, linearization and
compilation dominate the complete first-run time, while executing them takes
milliseconds. `component_outputs` evaluates one component group on the host and
remains an ordinary differentiable JAX function:

* primal: `jax.pure_callback` into NumPy;
* tangent (`jax.custom_jvp`): dY = J dX + K conj(dX), where the per-row Jacobian
  blocks J and K are computed on the host and contracted with the input tangents
  by JAX. The tangent is JAX-linear in dX, so JAX transposes it for reverse mode.
  jit, grad/vjp, jvp/jacfwd and vmap all work.
* second order: J and K come from a callback that has no derivative rule, so a
  second derivative (Hessian, HVP, jvp of grad) through these functions raises
  JAX's explicit "Pure callbacks do not support JVP" error. It is never silently
  wrong. Set `simulate.HOST_COMPONENTS = False` for second-order work.

The component functions are not re-implemented. The originals in
`differometor.components` are re-bound to a NumPy namespace (`_SHIM`) whose
operations accept plain arrays or first-order duals. A dual carries the
derivative of a value with respect to one complex input in Wirtinger form,
dy = a dz + b conj(dz): holomorphic operations keep b = 0 and conjugation swaps
a and b. Non-holomorphic outputs (squeezer lower terms, corrected right
optomechanical phase) are therefore exact, and the same source code defines the
values on both paths.
"""

from __future__ import annotations

import types
from functools import partial

import jax
import jax.numpy as jnp
import numpy as np

from differometor import components as _components
from differometor.components import FUNCTIONS


class Dual:
    """Value v with Wirtinger derivatives dv = a dz + b conj(dz) for one seed z."""

    __slots__ = ("v", "a", "b")
    __array_ufunc__ = None  # NumPy defers to the reflected operators below

    def __init__(self, v, a, b):
        self.v, self.a, self.b = v, a, b

    def __neg__(self):
        return Dual(-self.v, -self.a, -self.b)

    def __add__(self, other):
        if isinstance(other, Dual):
            return Dual(self.v + other.v, self.a + other.a, self.b + other.b)
        return Dual(self.v + other, self.a, self.b)

    def __radd__(self, other):
        return Dual(other + self.v, self.a, self.b)

    def __sub__(self, other):
        if isinstance(other, Dual):
            return Dual(self.v - other.v, self.a - other.a, self.b - other.b)
        return Dual(self.v - other, self.a, self.b)

    def __rsub__(self, other):
        return Dual(other - self.v, -self.a, -self.b)

    def __mul__(self, other):
        if isinstance(other, Dual):
            return Dual(self.v * other.v, self.a * other.v + self.v * other.a, self.b * other.v + self.v * other.b)
        return Dual(self.v * other, self.a * other, self.b * other)

    def __rmul__(self, other):
        return Dual(other * self.v, other * self.a, other * self.b)

    def __truediv__(self, other):
        if isinstance(other, Dual):
            value = self.v / other.v
            return Dual(value, (self.a - value * other.a) / other.v, (self.b - value * other.b) / other.v)
        return Dual(self.v / other, self.a / other, self.b / other)

    def __rtruediv__(self, other):
        value = other / self.v
        slope = -value / self.v
        return Dual(value, slope * self.a, slope * self.b)

    def __pow__(self, exponent):
        if isinstance(exponent, Dual):
            raise TypeError("Dual exponents are not supported")
        slope = exponent * self.v ** (exponent - 1)
        return Dual(self.v ** exponent, slope * self.a, slope * self.b)


def _holomorphic(function, derivative):
    def apply(x):
        if isinstance(x, Dual):
            value = function(x.v)
            slope = derivative(x.v, value)
            return Dual(value, slope * x.a, slope * x.b)
        return function(x)
    return apply


def _conjugate(x):
    if isinstance(x, Dual):
        return Dual(np.conj(x.v), np.conj(x.b), np.conj(x.a))
    return np.conj(x)


def _radians(x):
    # jnp.radians multiplies by the constant pi / 180; np.radians rejects complex.
    return x * (np.pi / 180)


def _value_only(function):
    def apply(x):
        if isinstance(x, Dual):
            raise TypeError(f"{function.__name__} has no dual rule")
        return function(x)
    return apply


class Stack:
    """List-backed stand-in for `jnp.array([...])` of per-row columns."""

    __slots__ = ("items",)
    __array_ufunc__ = None

    def __init__(self, items):
        self.items = list(items)

    def __getitem__(self, index):
        return self.items[index]

    def __neg__(self):
        return Stack([-item for item in self.items])

    def __len__(self):
        return len(self.items)


_SHIM = types.SimpleNamespace(
    pi=np.pi,
    e=np.e,
    complex128=np.complex128,
    ndarray=np.ndarray,
    exp=_holomorphic(np.exp, lambda x, value: value),
    sqrt=_holomorphic(np.sqrt, lambda x, value: 0.5 / value),
    sin=_holomorphic(np.sin, lambda x, value: np.cos(x)),
    cos=_holomorphic(np.cos, lambda x, value: -np.sin(x)),
    arcsin=_holomorphic(np.arcsin, lambda x, value: 1 / np.sqrt(1 - x * x)),
    cosh=_holomorphic(np.cosh, lambda x, value: np.sinh(x)),
    sinh=_holomorphic(np.sinh, lambda x, value: np.cosh(x)),
    log10=_value_only(np.log10),
    abs=_value_only(np.abs),
    radians=_radians,
    conj=_conjugate,
    conjugate=_conjugate,
    array=lambda items, dtype=None: Stack(items),
)


def _rebind_components():
    """Copies of every component function whose `jnp` is the NumPy shim."""
    namespace = dict(vars(_components))
    namespace["jnp"] = _SHIM
    for name, value in list(namespace.items()):
        if isinstance(value, types.FunctionType) and value.__module__ == _components.__name__:
            namespace[name] = types.FunctionType(
                value.__code__, namespace, value.__name__, value.__defaults__, value.__closure__
            )
    return namespace


_NAMESPACE = _rebind_components()
HOST_FUNCTIONS = [_NAMESPACE[function.__name__] for function in FUNCTIONS]


class _Slots:
    __slots__ = ("columns",)

    def __init__(self, columns):
        self.columns = columns

    def __getitem__(self, index):
        if isinstance(index, (int, np.integer)):
            return self.columns[index]
        raise TypeError("Component inputs must be indexed with integers")


def _columns(inputs):
    inputs = np.asarray(inputs, dtype=np.complex128)
    return inputs, [inputs[..., slot] for slot in range(inputs.shape[-1])]


def evaluate_function(function_index, inputs):
    """Component outputs (..., 4) for inputs (..., slots), on the host."""
    inputs, columns = _columns(inputs)
    stack = HOST_FUNCTIONS[function_index](_Slots(columns))
    shape = inputs.shape[:-1]
    return np.stack([np.broadcast_to(np.asarray(item, dtype=np.complex128), shape) for item in stack.items], axis=-1)


def function_jacobian(function_index, slots, inputs, with_outputs=True):
    """Outputs (..., 4) and Wirtinger blocks J, K (..., 4, len(slots)) on the host.

    `with_outputs=False` skips the (unused) primal evaluation and returns None
    for the outputs; the Jacobian blocks are computed identically.
    """
    inputs, columns = _columns(inputs)
    shape = inputs.shape[:-1]
    outputs = evaluate_function(function_index, inputs) if with_outputs else None
    # Each derivative plane is filled as one contiguous array. Expose the same
    # (..., 4, slots) API using views; contraction and scatter order are unchanged.
    linear_planes = np.zeros((len(slots), 4) + shape, dtype=np.complex128)
    antilinear_planes = np.zeros_like(linear_planes)
    linear = np.moveaxis(linear_planes, (0, 1), (-1, -2))
    antilinear = np.moveaxis(antilinear_planes, (0, 1), (-1, -2))
    for position, slot in enumerate(slots):
        seeded = list(columns)
        seeded[slot] = Dual(columns[slot], 1.0, 0.0)
        stack = HOST_FUNCTIONS[function_index](_Slots(seeded))
        for column, item in enumerate(stack.items):
            if isinstance(item, Dual):
                linear[..., column, position] = np.broadcast_to(item.a, shape)
                antilinear[..., column, position] = np.broadcast_to(item.b, shape)
    return outputs, linear, antilinear


_ANTILINEAR = {}


def has_antilinear_part(function_index):
    """Whether the function's outputs depend on conj(input) (probed once on the host)."""
    if function_index not in _ANTILINEAR:
        probe = np.array([[0.3 + 0.1j, 0.7 + 0.05j, 0.2 + 0.02j, 1.1 + 0.03j, 1.3 + 0.01j, 1.2 + 0.02j, 0.4 + 0.01j]])
        _, _, antilinear = function_jacobian(function_index, tuple(range(probe.shape[-1])), probe)
        _ANTILINEAR[function_index] = bool(np.any(antilinear != 0))
    return _ANTILINEAR[function_index]


def _value_call(function_index, inputs):
    return jax.pure_callback(
        partial(evaluate_function, function_index),
        jax.ShapeDtypeStruct(inputs.shape[:-1] + (4,), jnp.complex128),
        inputs,
        vmap_method="broadcast_all",
    )


@partial(jax.custom_jvp, nondiff_argnums=(0, 1))
def component_outputs(function_index, slots, inputs):
    """Outputs (..., 4) of FUNCTIONS[function_index] for inputs (..., S).

    Only input slots listed in `slots` carry tangents. The others are treated as
    constants, matching the gradient-stopped slots of the JAX path (they read no
    optimized or linked parameter).
    """
    return _value_call(function_index, inputs.astype(jnp.complex128))


@component_outputs.defjvp
def _component_outputs_jvp(function_index, slots, primals, tangents):
    (inputs,), (inputs_dot,) = primals, tangents
    inputs = inputs.astype(jnp.complex128)
    if not slots:
        outputs = _value_call(function_index, inputs)
        return outputs, jnp.zeros_like(outputs)
    antilinear = has_antilinear_part(function_index)
    count = len(slots)
    shape = inputs.shape[:-1]
    result_shapes = [
        jax.ShapeDtypeStruct(shape + (4,), jnp.complex128),
        jax.ShapeDtypeStruct(shape + (4, count), jnp.complex128),
        jax.ShapeDtypeStruct(shape + (4, count), jnp.complex128),
    ]
    outputs, linear, conjugate_linear = jax.pure_callback(
        partial(function_jacobian, function_index, slots), result_shapes, inputs, vmap_method="broadcast_all"
    )
    selected = inputs_dot.astype(jnp.complex128)[..., np.asarray(slots)]
    tangent = jnp.einsum("...cs,...s->...c", linear, selected)
    if antilinear:
        tangent = tangent + jnp.einsum("...cs,...s->...c", conjugate_linear, jnp.conjugate(selected))
    return outputs, tangent
