"""Whole-pass host evaluation with an explicit reverse-mode derivative (opt-in).

`simulate.HOST_PASS = True` evaluates everything after parameter insertion,
linking and detector-phase scattering on the host:

    F(parameters, sweep values, base matrix values, detector selections)
        -> (carrier, signal, noise)

Forward and backward are `jax.pure_callback`s inside one `jax.custom_vjp`, so
the three benchmark JIT stages compile only a few gathers and scatters.

LIMITATION (deliberate, measured trade-off): a `custom_vjp` function supports
jit, vmap, grad/vjp/value_and_grad (first-order reverse mode) only. jvp, jacfwd,
jax.hessian and any second order raise JAX's explicit errors ("can't apply
forward-mode autodiff (jvp) to a custom_vjp function"). The default
(`HOST_PASS = False`) keeps component evaluation on the host through a
JAX-linear custom JVP (`differometor.host`) and remains forward-mode capable.

Component functions use the re-bound original source from `differometor.host`
(values and exact Wirtinger Jacobian blocks). Linear algebra follows
`differometor.sparse` (SuperLU + COLAMD, iterative refinement); one
factorization per signal row serves the N, T and H solves.
"""

from __future__ import annotations

import hashlib
from functools import partial

import jax
import jax.numpy as jnp
import numpy as np

from differometor.components import UNIT_VACUUM, H_PLANCK, F0
from differometor.host import evaluate_function, function_jacobian
from differometor.sparse import _scipy, REFINEMENT_STEPS, REFINEMENT_TOLERANCE

_NOISE_SCALE = 2 * UNIT_VACUUM * H_PLANCK * F0 * 0.25


def _noise_amplitude(temporary_sum):
    # Same operation order as the reference implementation.
    return np.sqrt(2 * temporary_sum * UNIT_VACUUM * H_PLANCK * F0 * 0.25)


def _digest(*arrays):
    digest = hashlib.sha256()
    for array in arrays:
        array = np.ascontiguousarray(array)
        digest.update(str(array.dtype).encode())
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


class SystemPlan:
    """Static component groups, output selection and ordered writes for one system."""

    def __init__(self, sparse_system, groups, selected_rows, selected_columns):
        self.system = sparse_system
        # (function_index, (R, S) parameter indices, slots that carry derivatives)
        self.groups = tuple((int(f), np.asarray(i, dtype=np.int64), tuple(int(s) for s in d)) for f, i, d in groups)
        self.offsets = np.cumsum([0] + [indices.shape[0] for _, indices, _ in self.groups])
        self.total_rows = int(self.offsets[-1])
        self.flat_selection = (np.asarray(selected_rows, dtype=np.int64) * 4
                               + np.asarray(selected_columns, dtype=np.int64))
        writes = np.asarray(sparse_system.write_positions, dtype=np.int64)
        # The reference scatter applies writes in order: the last write to a position wins.
        _, first_in_reverse = np.unique(writes[::-1], return_index=True)
        last = np.zeros(writes.shape, dtype=bool)
        last[writes.size - 1 - first_in_reverse] = True
        self.writes, self.last = writes, last
        self.written = np.unique(writes)
        self._key = _digest(
            np.asarray([f for f, _, _ in self.groups], dtype=np.int64),
            *[indices for _, indices, _ in self.groups],
            np.asarray([s for _, _, d in self.groups for s in d] + [-1], dtype=np.int64),
            self.flat_selection, writes,
        ) + sparse_system._key

    def values(self, rows, base):
        """Structural values (B, nnz_total) after the ordered update writes."""
        blocks = [evaluate_function(f, rows[:, indices]) for f, indices, _ in self.groups]
        outputs = np.concatenate(blocks, axis=1).reshape(rows.shape[0], -1)[:, self.flat_selection]
        values = np.repeat(np.asarray(base, dtype=np.complex128)[None, :], rows.shape[0], axis=0)
        values[:, self.writes[self.last]] = outputs[:, self.last]
        return values

    def backward(self, rows, values_bar):
        """Cotangents of the parameter rows (B, P) and the base values (nnz_total,)."""
        count = rows.shape[0]
        batch = np.arange(count)[:, None]
        outputs_bar = np.zeros((count, self.writes.size), dtype=np.complex128)
        outputs_bar[:, self.last] = values_bar[:, self.writes[self.last]]
        base_bar = values_bar.copy()
        base_bar[:, self.written] = 0
        flat = np.zeros((count, self.total_rows * 4), dtype=np.complex128)
        np.add.at(flat, (batch, self.flat_selection[None, :]), outputs_bar)
        flat = flat.reshape(count, self.total_rows, 4)
        rows_bar = np.zeros(rows.shape, dtype=np.complex128)
        for (function_index, indices, slots), start, stop in zip(self.groups, self.offsets[:-1], self.offsets[1:]):
            if not slots:
                continue
            _, linear, antilinear = function_jacobian(function_index, slots, rows[:, indices])
            output_bar = flat[:, start:stop, :, None]                       # (B, R, 4, 1)
            inputs_bar = np.sum(linear * output_bar, axis=2) + np.conj(np.sum(antilinear * output_bar, axis=2))
            for position, slot in enumerate(slots):
                np.add.at(rows_bar, (batch, indices[None, :, slot]), inputs_bar[:, :, position])
        return rows_bar, base_bar.sum(axis=0)


class HostPlan:
    """Static host plan for one built setup (no array leaves)."""

    def __init__(self, structure, carrier, signal, noise, carrier_changing, signal_changing,
                 signal_carrier_indices, noise_row_reuse):
        self.structure = structure
        self.carrier, self.signal, self.noise = carrier, signal, noise
        self.carrier_changing = np.asarray(carrier_changing, dtype=np.int64).ravel()
        self.signal_changing = np.asarray(signal_changing, dtype=np.int64).ravel()
        self.signal_carrier_indices = np.asarray(signal_carrier_indices, dtype=np.int64).ravel()
        self.noise_row_reuse = bool(noise_row_reuse)
        self._key = (_digest(self.carrier_changing, self.signal_changing, self.signal_carrier_indices,
                             np.int64(self.noise_row_reuse))
                     + carrier._key + signal._key + noise._key + structure._key)

    def __hash__(self):
        return hash(self._key)

    def __eq__(self, other):
        return isinstance(other, HostPlan) and other._key == self._key

    def __repr__(self):
        return f"HostPlan({self.structure})"


jax.tree_util.register_static(HostPlan)


def build_host_plan(simulation_arrays, structure, component_groups):
    """Static plan from concrete built arrays, or None when the layout is unsupported."""
    if structure is None or not isinstance(component_groups, dict) or not structure.unique_placing:
        return None
    plans = {}
    for name, output_key in (("carrier", "carrier_output_indices"), ("signal", "signal_output_indices"),
                             ("noise", "noise_output_indices")):
        group = component_groups.get(name)
        if not isinstance(group, dict) or not {"function_rows", "parameter_indices", "output_rows"} <= set(group):
            return None
        diff_slots = group.get("diff_slots", {})
        groups = []
        for function_index in sorted(group["function_rows"]):
            indices = np.asarray(group["parameter_indices"][function_index])
            if indices.ndim != 2:
                return None
            groups.append((function_index, indices, sorted(diff_slots.get(function_index, range(indices.shape[1])))))
        output_rows = np.asarray(group["output_rows"])
        output_indices = np.asarray(simulation_arrays[output_key])
        plans[name] = SystemPlan(getattr(structure, name), groups, output_rows[output_indices[0]], output_indices[1])
    return HostPlan(structure, plans["carrier"], plans["signal"], plans["noise"],
                    np.asarray(simulation_arrays["carrier_changing_parameter_indices"]),
                    np.asarray(simulation_arrays["signal_changing_parameter_indices"]),
                    np.asarray(simulation_arrays["signal_carrier_indices"]),
                    "noise_row_reuse" in component_groups)


def _expand(array, indices, values):
    """NumPy replica of `simulate.expand_parameters`."""
    count = values.shape[1]
    tiled = np.tile(array, (count, 1))
    tiled[np.repeat(np.arange(count), indices.size), np.tile(indices, count)] = values.T.reshape(-1)
    return tiled


def _expand_backward(array_rows, indices, values, tiled_bar):
    count = values.shape[1]
    rows, columns = np.repeat(np.arange(count), indices.size), np.tile(indices, count)
    values_bar = tiled_bar[rows, columns].reshape(count, indices.size).T
    tiled_bar = tiled_bar.copy()
    tiled_bar[rows, columns] = 0
    return tiled_bar.reshape(count, array_rows, tiled_bar.shape[1]).sum(axis=0), values_bar


def _split(system, values):
    coefficients = values[:, : system.nnz]
    rhs = np.zeros((values.shape[0], system.size), dtype=np.complex128)
    if system.augmented:
        rhs[:, system.rhs_rows] = values[:, system.nnz :]
    return coefficients, rhs


def _factor(pattern, values):
    splu, csc_matrix = _scipy()
    matrix = csc_matrix((values, pattern.indices, pattern.indptr), shape=(pattern.size, pattern.size))
    return matrix, splu(matrix, permc_spec="COLAMD")


def _solve(matrix, factor, rhs, trans):
    operator = matrix if trans == "N" else matrix.T if trans == "T" else matrix.conj().T
    rhs = np.ascontiguousarray(rhs, dtype=np.complex128)
    solution = factor.solve(rhs, trans=trans)
    for _ in range(REFINEMENT_STEPS):
        correction = factor.solve(np.ascontiguousarray(rhs - operator @ solution), trans=trans)
        solution = solution + correction
        if np.max(np.abs(correction)) <= REFINEMENT_TOLERANCE * np.max(np.abs(solution)):
            break
    return solution


def _selections(plan, carrier, selection_vectors):
    """Tiled detector selections (D, Bc, N) and carrier-weighted selections (D, Bc, N)."""
    size = plan.structure.carrier.size
    tiled = np.tile(selection_vectors, (1, carrier.shape[0], 1))
    upper = tiled.copy()
    upper[:, :, :size] = tiled[:, :, :size] * carrier
    selected = upper.copy()
    selected[:, :, size : 2 * size] = np.conj(upper[:, :, size : 2 * size] * carrier)
    return tiled, selected


def _assemble(plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base):
    structure = plan.structure
    carrier_rows = _expand(parameters, plan.carrier_changing, carrier_values)
    carrier_vals = plan.carrier.values(carrier_rows, carrier_base)
    carrier_coefficients, carrier_rhs = _split(structure.carrier, carrier_vals)
    carrier = np.empty((carrier_rows.shape[0], structure.carrier.size), dtype=np.complex128)
    for row in range(carrier_rows.shape[0]):
        matrix, factor = _factor(structure.carrier.pattern, carrier_coefficients[row])
        carrier[row] = _solve(matrix, factor, carrier_rhs[row], "N")
    signal_rows = _expand(carrier_rows, plan.signal_changing, signal_values)
    raw_signal = plan.signal.values(signal_rows, signal_base)
    placing = structure.signal_placing_positions
    placed = raw_signal.copy()
    placed[:, placing] = -raw_signal[:, placing] * carrier[:, plan.signal_carrier_indices]
    final = np.where(structure.signal_conjugate, np.conj(placed), placed)
    noise_rows = signal_rows[:1] if plan.noise_row_reuse else signal_rows
    return dict(carrier_rows=carrier_rows, carrier_values=carrier_vals, carrier_coefficients=carrier_coefficients,
                carrier=carrier, signal_rows=signal_rows, raw_signal=raw_signal, signal_values=final,
                noise_rows=noise_rows, noise_values=plan.noise.values(noise_rows, noise_base))


def host_forward(plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base,
                 selection_vectors):
    _, csc_matrix = _scipy()
    state = _assemble(plan, np.asarray(parameters), np.asarray(carrier_values), np.asarray(signal_values),
                      np.asarray(carrier_base), np.asarray(signal_base), np.asarray(noise_base))
    structure = plan.structure
    system = structure.signal
    coefficients, rhs = _split(system, state["signal_values"])
    _, selected = _selections(plan, state["carrier"], np.asarray(selection_vectors))
    count, detectors = coefficients.shape[0], selected.shape[0]
    selections = np.moveaxis(np.broadcast_to(selected, (detectors, count, system.size)), 0, 1)
    noise_pattern = structure.noise.pattern
    signal = np.empty((count, system.size), dtype=np.complex128)
    covariances = np.empty((count, detectors, system.size), dtype=np.complex128)
    weights = np.empty((count, detectors, system.size), dtype=np.complex128)
    for row in range(count):
        matrix, factor = _factor(system.pattern, coefficients[row])
        weight = _solve(matrix, factor, selections[row].T, "H")                    # A^H w = s
        noise_matrix = csc_matrix((state["noise_values"][0 if plan.noise_row_reuse else row],
                                   noise_pattern.indices, noise_pattern.indptr),
                                  shape=(noise_pattern.size, noise_pattern.size))
        solution = _solve(matrix, factor, np.concatenate([rhs[row][:, None], noise_matrix @ weight], axis=1), "N")
        signal[row], covariances[row], weights[row] = solution[:, 0], solution[:, 1:].T, weight.T
    noise = _noise_amplitude(np.sum(np.real(covariances * np.conj(selections)), axis=2)).T     # (D, Bs)
    return state["carrier"], signal, noise, covariances, weights


def _sum_to(value, shape):
    """Reverse of NumPy broadcasting from `shape` to `value.shape`."""
    while value.ndim > len(shape):
        value = value.sum(axis=0)
    for axis, want in enumerate(shape):
        if want == 1 and value.shape[axis] != 1:
            value = value.sum(axis=axis, keepdims=True)
    return value


def _cast_bar(value, dtype):
    return (value if np.issubdtype(dtype, np.complexfloating) else np.real(value)).astype(dtype)


def host_backward(plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base,
                  selection_vectors, carrier, signal, noise, covariances, weights,
                  carrier_bar, signal_bar, noise_bar):
    _, csc_matrix = _scipy()
    parameters, carrier_values = np.asarray(parameters), np.asarray(carrier_values)
    signal_values, selection_vectors = np.asarray(signal_values), np.asarray(selection_vectors)
    carrier, signal, noise = np.asarray(carrier), np.asarray(signal), np.asarray(noise)
    covariances, weights = np.asarray(covariances), np.asarray(weights)
    state = _assemble(plan, parameters, carrier_values, signal_values, np.asarray(carrier_base),
                      np.asarray(signal_base), np.asarray(noise_base))
    structure = plan.structure
    system, noise_system, carrier_system = structure.signal, structure.noise, structure.carrier
    coefficients, _ = _split(system, state["signal_values"])
    tiled, selected = _selections(plan, carrier, selection_vectors)
    count, detectors, size = coefficients.shape[0], selected.shape[0], system.size
    selections = np.moveaxis(np.broadcast_to(selected, (detectors, count, size)), 0, 1)

    # noise = sqrt(c t), t = sum Re(cov conj(s)): t_bar = noise_bar c / (2 noise).
    temporary_bar = np.asarray(noise_bar, dtype=np.float64) * _NOISE_SCALE / (2 * noise)      # (D, Bs)
    covariance_bar = temporary_bar.T[:, :, None] * np.conj(selections)                         # (Bs, D, N)
    selection_bar = temporary_bar.T[:, :, None] * np.conj(covariances)
    signal_values_bar = np.zeros(state["signal_values"].shape, dtype=np.complex128)
    noise_values_bar = np.zeros(state["noise_values"].shape, dtype=np.complex128)
    pattern, noise_pattern = system.pattern, noise_system.pattern
    signal_bar = np.asarray(signal_bar)
    for row in range(count):
        matrix, factor = _factor(pattern, coefficients[row])
        solution = np.concatenate([signal[row][:, None], covariances[row].T], axis=1)           # (N, 1 + D)
        solution_bar = np.concatenate([signal_bar[row][:, None], covariance_bar[row].T], axis=1)
        rhs_bar = _solve(matrix, factor, solution_bar, "T")                                    # A^T r = x_bar
        coefficient_bar = -np.sum(rhs_bar[pattern.rows] * solution[pattern.cols], axis=1)
        sources_bar, weight = rhs_bar[:, 1:], weights[row].T                                    # (N, D)
        noise_row = 0 if plan.noise_row_reuse else row
        noise_values_bar[noise_row] += np.sum(sources_bar[noise_pattern.rows] * weight[noise_pattern.cols], axis=1)
        noise_matrix = csc_matrix((state["noise_values"][noise_row], noise_pattern.indices, noise_pattern.indptr),
                                  shape=(noise_pattern.size, noise_pattern.size))
        weight_bar = noise_matrix.T @ sources_bar
        # w = conj(A)^-T s: s_bar = conj(A)^-1 w_bar = g; conj(A)_bar[r, c] = -g[c] w[r].
        adjoint = np.conj(_solve(matrix, factor, np.conj(weight_bar), "N"))
        selection_bar[row] += adjoint.T
        coefficient_bar += np.conj(-np.sum(adjoint[pattern.cols] * weight[pattern.rows], axis=1))
        signal_values_bar[row, : system.nnz] = coefficient_bar
        if system.augmented:
            signal_values_bar[row, system.nnz :] = rhs_bar[system.rhs_rows, 0]

    # Sideband conjugation, then carrier scaling of signal connectors.
    placed_bar = np.where(structure.signal_conjugate, np.conj(signal_values_bar), signal_values_bar)
    placing = structure.signal_placing_positions
    scale = carrier[:, plan.signal_carrier_indices]
    raw_bar = placed_bar.copy()
    raw_bar[:, placing] = -placed_bar[:, placing] * scale
    carrier_total_bar = np.array(np.asarray(carrier_bar), dtype=np.complex128, copy=True)       # (Bc, CN)
    scale_bar = _sum_to(-placed_bar[:, placing] * state["raw_signal"][:, placing], scale.shape)
    np.add.at(carrier_total_bar, (np.arange(carrier.shape[0])[:, None], plan.signal_carrier_indices[None, :]),
              scale_bar)

    # Detector selections (s = tiled with carrier-weighted upper and conjugated lower blocks).
    carrier_size = carrier_system.size
    selected_bar = _sum_to(np.moveaxis(selection_bar, 1, 0), tiled.shape)                     # (D, Bc, N)
    middle_bar = np.conj(selected_bar[:, :, carrier_size : 2 * carrier_size])
    upper_bar = selected_bar.copy()
    upper_bar[:, :, carrier_size : 2 * carrier_size] = middle_bar * carrier
    carrier_total_bar += np.sum(middle_bar * tiled[:, :, carrier_size : 2 * carrier_size], axis=0)
    tiled_bar = upper_bar.copy()
    tiled_bar[:, :, :carrier_size] = upper_bar[:, :, :carrier_size] * carrier
    carrier_total_bar += np.sum(upper_bar[:, :, :carrier_size] * tiled[:, :, :carrier_size], axis=0)
    selection_vectors_bar = tiled_bar.sum(axis=1, keepdims=True)

    # Carrier solve.
    carrier_values_bar = np.zeros(state["carrier_values"].shape, dtype=np.complex128)
    carrier_pattern = carrier_system.pattern
    for row in range(carrier.shape[0]):
        matrix, factor = _factor(carrier_pattern, state["carrier_coefficients"][row])
        rhs_bar = _solve(matrix, factor, carrier_total_bar[row], "T")
        carrier_values_bar[row, : carrier_system.nnz] = -rhs_bar[carrier_pattern.rows] * carrier[row][carrier_pattern.cols]
        if carrier_system.augmented:
            carrier_values_bar[row, carrier_system.nnz :] = rhs_bar[carrier_system.rhs_rows]

    # Component functions and parameter expansion.
    signal_rows_bar, signal_base_bar = plan.signal.backward(state["signal_rows"], raw_bar)
    noise_rows_bar, noise_base_bar = plan.noise.backward(state["noise_rows"], noise_values_bar)
    signal_rows_bar[: noise_rows_bar.shape[0]] += noise_rows_bar
    carrier_rows_bar, signal_values_bar_in = _expand_backward(
        state["carrier_rows"].shape[0], plan.signal_changing, signal_values, signal_rows_bar)
    component_bar, carrier_base_bar = plan.carrier.backward(state["carrier_rows"], carrier_values_bar)
    parameters_bar, carrier_values_bar_in = _expand_backward(
        parameters.shape[0], plan.carrier_changing, carrier_values, carrier_rows_bar + component_bar)
    return (parameters_bar.astype(parameters.dtype), _cast_bar(carrier_values_bar_in, carrier_values.dtype),
            _cast_bar(signal_values_bar_in, signal_values.dtype), carrier_base_bar, signal_base_bar,
            noise_base_bar, selection_vectors_bar.astype(np.complex128))


def _shapes(plan, carrier_values, signal_values, selection_vectors):
    carrier_count = carrier_values.shape[1]
    signal_count = signal_values.shape[1] * carrier_count
    detectors, size = selection_vectors.shape[0], plan.structure.signal.size
    return (jax.ShapeDtypeStruct((carrier_count, plan.structure.carrier.size), jnp.complex128),
            jax.ShapeDtypeStruct((signal_count, size), jnp.complex128),
            jax.ShapeDtypeStruct((detectors, signal_count), jnp.float64),
            jax.ShapeDtypeStruct((signal_count, detectors, size), jnp.complex128),
            jax.ShapeDtypeStruct((signal_count, detectors, size), jnp.complex128))


def _forward_call(plan, *inputs):
    return jax.pure_callback(partial(host_forward, plan), _shapes(plan, inputs[1], inputs[2], inputs[6]),
                             *inputs, vmap_method="sequential")


@partial(jax.custom_vjp, nondiff_argnums=(0,))
def host_pass(plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base,
              selection_vectors):
    """Carrier (Bc, CN), signal (Bs, N) and noise (D, Bs) evaluated on the host."""
    carrier, signal, noise, _, _ = _forward_call(
        plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base, selection_vectors)
    return carrier, signal, noise


def _host_pass_fwd(plan, *inputs):
    carrier, signal, noise, covariances, weights = _forward_call(plan, *inputs)
    return (carrier, signal, noise), (inputs, (carrier, signal, noise, covariances, weights))


def _host_pass_bwd(plan, residuals, cotangents):
    inputs, outputs = residuals
    shapes = tuple(jax.ShapeDtypeStruct(value.shape, value.dtype) for value in inputs)
    return jax.pure_callback(partial(host_backward, plan), shapes, *inputs, *outputs, *cotangents,
                             vmap_method="sequential")


host_pass.defvjp(_host_pass_fwd, _host_pass_bwd)
