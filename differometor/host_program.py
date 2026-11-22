"""Static NumPy arithmetic programs for the component dual interpreter.

Only operation graphs are cached; there is no generated source or bytecode. Graph construction uses symbolic columns, never
an evaluation's physical parameters, and every call executes on its supplied
columns. No algebraic simplification or zero-derivative elimination is performed.
"""

from functools import lru_cache
import operator

import numpy as np


class _Expression:
    __array_priority__ = 1000

    def __init__(self, graph, index):
        self.graph, self.index = graph, index

    def __array_ufunc__(self, function, method, *args, **kwargs):
        if method != "__call__" or kwargs:
            return NotImplemented
        return self.graph.operation(function, *args)

    def __neg__(self):
        return self.graph.operation(operator.neg, self)

    def __add__(self, other):
        return self.graph.operation(operator.add, self, other)

    def __radd__(self, other):
        return self.graph.operation(operator.add, other, self)

    def __sub__(self, other):
        return self.graph.operation(operator.sub, self, other)

    def __rsub__(self, other):
        return self.graph.operation(operator.sub, other, self)

    def __mul__(self, other):
        return self.graph.operation(operator.mul, self, other)

    def __rmul__(self, other):
        return self.graph.operation(operator.mul, other, self)

    def __truediv__(self, other):
        return self.graph.operation(operator.truediv, self, other)

    def __rtruediv__(self, other):
        return self.graph.operation(operator.truediv, other, self)

    def __pow__(self, other):
        return self.graph.operation(operator.pow, self, other)


class _Graph:
    def __init__(self, count):
        self.nodes = [("input", slot) for slot in range(count)]
        self.interned = {}
        self.columns = [_Expression(self, slot) for slot in range(count)]

    def constant(self, value):
        if isinstance(value, _Expression):
            if value.graph is not self:
                raise ValueError("Cannot combine separate component graphs")
            return value.index
        if not np.isscalar(value):
            raise TypeError("Component graph constants must be scalars")
        # Preserve scalar types and signed zeros; constants originate in component
        # source and Dual rules, never in a supplied physical parameter array.
        key = ("constant", type(value), repr(value))
        if key not in self.interned:
            self.interned[key] = len(self.nodes)
            self.nodes.append(("constant", value))
        return self.interned[key]

    def operation(self, function, *args):
        # Match ndarray's deferral to Dual's reflected arithmetic. In particular,
        # an unseeded column on the left must not swallow a seeded Dual operand.
        if any(getattr(arg, "__array_ufunc__", False) is None for arg in args):
            return NotImplemented
        indices = tuple(self.constant(arg) for arg in args)
        key = (function, indices)
        if key not in self.interned:
            self.interned[key] = len(self.nodes)
            self.nodes.append(("operation", function, indices))
        return _Expression(self, self.interned[key])

    def program(self, writes):
        destinations = [[] for _ in self.nodes]
        for target, column, position, index in writes:
            destinations[index].append((target, column, position))
        # Retain each array only until its final arithmetic use. Jacobian
        # destinations are independent, so write them as soon as available.
        last_use = list(range(len(self.nodes)))
        for index, node in enumerate(self.nodes):
            if node[0] == "operation":
                for operand in node[2]:
                    last_use[operand] = index
        release = [[] for _ in self.nodes]
        for operand, index in enumerate(last_use):
            release[index].append(operand)
        return _Program(tuple(self.nodes), tuple(map(tuple, destinations)), tuple(map(tuple, release)))


class _Program:
    """Static operation layout; each invocation owns its numerical workspace."""

    def __init__(self, nodes, destinations, release):
        self.nodes, self.destinations, self.release = nodes, destinations, release

    def __call__(self, columns, linear, antilinear):
        values = [None] * len(self.nodes)
        for index, (node, destinations, release) in enumerate(
                zip(self.nodes, self.destinations, self.release)):
            kind = node[0]
            if kind == "input":
                value = columns[node[1]]
            elif kind == "constant":
                value = node[1]
            else:
                function, operands = node[1:]
                # Component arithmetic is predominantly unary/binary. Avoid a
                # generator and argument tuple for every such operation, keeping
                # exactly the same callable, arguments and evaluation order.
                if len(operands) == 1:
                    value = function(values[operands[0]])
                elif len(operands) == 2:
                    value = function(values[operands[0]], values[operands[1]])
                else:
                    value = function(*(values[operand] for operand in operands))
            values[index] = value
            for target, column, position in destinations:
                output = linear if target == "linear" else antilinear
                output[..., column, position] = value
            for operand in release:
                values[operand] = None


@lru_cache(maxsize=128)
def jacobian_program(function, slots, column_count, dual_type, slots_type):
    """Stage the existing Dual operations once for a component/slot layout."""
    graph = _Graph(column_count)
    writes = []
    for position, slot in enumerate(slots):
        seeded = list(graph.columns)
        seeded[slot] = dual_type(graph.columns[slot], 1.0, 0.0)
        stack = function(slots_type(seeded))
        for column, item in enumerate(stack.items):
            if isinstance(item, dual_type):
                writes.append(("linear", column, position, graph.constant(item.a)))
                writes.append(("antilinear", column, position, graph.constant(item.b)))
    return graph.program(writes)
