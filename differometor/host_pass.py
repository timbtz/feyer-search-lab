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
        # Only the last write to a position receives a cotangent (the others are
        # exactly zero). When those last writes read distinct component outputs,
        # the cotangent scatter is a plain assignment instead of `np.add.at`.
        self.last_positions = writes[last]
        self.last_selection = self.flat_selection[last]
        self.last_selection_unique = bool(np.unique(self.last_selection).size == self.last_selection.size)
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
        last_bar = values_bar[:, self.last_positions]
        base_bar = values_bar.copy()
        base_bar[:, self.written] = 0
        flat = np.zeros((count, self.total_rows * 4), dtype=np.complex128)
        if self.last_selection_unique:
            flat[:, self.last_selection] = last_bar
        else:
            np.add.at(flat, (batch, self.last_selection[None, :]), last_bar)
        flat = flat.reshape(count, self.total_rows, 4)
        rows_bar = np.zeros(rows.shape, dtype=np.complex128)
        for (function_index, indices, slots), start, stop in zip(self.groups, self.offsets[:-1], self.offsets[1:]):
            if not slots:
                continue
            _, linear, antilinear = function_jacobian(function_index, slots, rows[:, indices], with_outputs=False)
            output_bar = flat[:, start:stop, :, None]                       # (B, R, 4, 1)
            inputs_bar = np.sum(linear * output_bar, axis=2) + np.conj(np.sum(antilinear * output_bar, axis=2))
            for position, slot in enumerate(slots):
                np.add.at(rows_bar, (batch, indices[None, :, slot]), inputs_bar[:, :, position])
        return rows_bar, base_bar.sum(axis=0)


class ParameterLayout:
    """Static parameter-row index layout of one built setup (host NumPy copies).

    Holds the concrete optimized-parameter insertion, linking and detector-phase
    indices that `run_build_step` produced, so `simulate` can index the parameter
    row with explicit, unique, in-bounds gathers/scatters instead of generic traced
    indexing. Like the rest of the host plan it describes the built arrays; rebuild
    it (re-run `run_build_step`) whenever those index arrays change.
    """

    def __init__(self, parameter_count, optimized_parameter_indices, optimized_value_indices,
                 linked_indices, indices_to_link, qhd_parameter_indices, qhd_placing_indices):
        self.parameter_count = int(parameter_count)
        self.optimized_parameter_indices = np.asarray(optimized_parameter_indices, dtype=np.int64).ravel()
        self.optimized_value_indices = np.asarray(optimized_value_indices, dtype=np.int64).ravel()
        self.linked_indices = np.asarray(linked_indices, dtype=np.int64).ravel()
        self.indices_to_link = np.asarray(indices_to_link, dtype=np.int64).ravel()
        self.qhd_parameter_indices = np.asarray(qhd_parameter_indices, dtype=np.int64).ravel()
        self.qhd_placing_indices = np.asarray(qhd_placing_indices, dtype=np.int64).reshape(-1, 3)
        self._key = _digest(np.int64(self.parameter_count), self.optimized_parameter_indices,
                            self.optimized_value_indices, self.linked_indices, self.indices_to_link,
                            self.qhd_parameter_indices, self.qhd_placing_indices)

    @classmethod
    def from_arrays(cls, simulation_arrays):
        """Layout from concrete built arrays, or None if not representable exactly.

        Requires nonnegative in-bounds parameter-row indices and unique write
        destinations (so the scatters may declare unique indices); otherwise the
        caller keeps the generic indexing path.
        """
        try:
            parameters = np.asarray(simulation_arrays["parameters"])
            layout = cls(
                parameters.shape[1] if parameters.ndim == 2 else -1,
                np.asarray(simulation_arrays["optimized_parameter_indices"]),
                np.asarray(simulation_arrays["optimized_value_indices"]),
                np.asarray(simulation_arrays["linked_indices"]),
                np.asarray(simulation_arrays["indices_to_link"]),
                np.asarray(simulation_arrays["qhd_parameter_indices"]),
                np.asarray(simulation_arrays["qhd_placing_indices"]),
            )
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        if parameters.ndim != 2 or parameters.shape[0] != 1:
            return None
        count = layout.parameter_count
        for indices in (layout.optimized_parameter_indices, layout.linked_indices, layout.indices_to_link,
                        layout.qhd_parameter_indices):
            if indices.size and (indices.min() < 0 or indices.max() >= count):
                return None
        if layout.optimized_value_indices.size and layout.optimized_value_indices.min() < 0:
            return None
        for indices in (layout.optimized_parameter_indices, layout.indices_to_link):
            if np.unique(indices).size != indices.size:
                return None
        return layout

    def applies(self, parameters, optimized_parameters):
        """Trace-time shape check that the static indices are in bounds for these inputs."""
        if parameters.ndim != 2 or parameters.shape[0] != 1 or parameters.shape[1] != self.parameter_count:
            return False
        if optimized_parameters.ndim != 1:
            return False
        values = self.optimized_value_indices
        return not values.size or int(values.max()) < optimized_parameters.shape[0]


class HostPlan:
    """Static host plan for one built setup (no array leaves)."""

    def __init__(self, structure, carrier, signal, noise, carrier_changing, signal_changing,
                 signal_carrier_indices, noise_row_reuse, parameter_layout=None):
        self.structure = structure
        self.carrier, self.signal, self.noise = carrier, signal, noise
        self.carrier_changing = np.asarray(carrier_changing, dtype=np.int64).ravel()
        self.signal_changing = np.asarray(signal_changing, dtype=np.int64).ravel()
        self.signal_carrier_indices = np.asarray(signal_carrier_indices, dtype=np.int64).ravel()
        self.noise_row_reuse = bool(noise_row_reuse)
        self.parameter_layout = parameter_layout
        self._key = (_digest(self.carrier_changing, self.signal_changing, self.signal_carrier_indices,
                             np.int64(self.noise_row_reuse))
                     + carrier._key + signal._key + noise._key + structure._key
                     + ("" if parameter_layout is None else parameter_layout._key))

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
                    "noise_row_reuse" in component_groups,
                    ParameterLayout.from_arrays(simulation_arrays))


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


_GSTRF = None
# The options `scipy.sparse.linalg.splu(A, permc_spec="COLAMD")` passes to SuperLU.
_SUPERLU_OPTIONS = dict(DiagPivotThresh=None, ColPerm="COLAMD", PanelSize=None, Relax=None)


def _construct_csc(*args, **kwargs):
    # Only used if a caller inspects factor.L / factor.U.
    from scipy.sparse import csc_array
    return csc_array(*args, **kwargs)


def _superlu_gstrf():
    """SciPy's SuperLU factorization entry point, without importing scipy.sparse.

    `splu` lives in `scipy.sparse.linalg`, whose package import (iterative
    solvers, array-API compatibility layer, `scipy.sparse`) costs ~0.1-0.16 s of
    the first evaluation. The factorization itself is the `_superlu` extension,
    which is loaded directly here and called with the same arguments as `splu`.
    Any failure falls back to the public `splu` path.
    """
    global _GSTRF
    if _GSTRF is None:
        import sys
        name = "scipy.sparse.linalg._dsolve._superlu"
        try:
            module = sys.modules.get(name)
            if module is None:
                import importlib.machinery
                import importlib.util
                import os
                scipy_spec = importlib.util.find_spec("scipy")
                directory = os.path.join(os.path.dirname(scipy_spec.origin), "sparse", "linalg", "_dsolve")
                suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
                filename = next(f for f in sorted(os.listdir(directory)) if f.startswith("_superlu.") and f.endswith(suffixes))
                path = os.path.join(directory, filename)
                loader = importlib.machinery.ExtensionFileLoader(name, path)
                module = importlib.util.module_from_spec(importlib.util.spec_from_file_location(name, path, loader=loader))
                loader.exec_module(module)
            _GSTRF = module.gstrf
        except Exception:
            _GSTRF = False
    return _GSTRF


def _factor(pattern, values):
    data = np.ascontiguousarray(values, dtype=np.complex128)
    gstrf = _superlu_gstrf()
    if gstrf:
        return gstrf(pattern.size, data.size, data, pattern.indices.astype(np.intc), pattern.indptr.astype(np.intc),
                     csc_construct_func=_construct_csc, ilu=False, options=dict(_SUPERLU_OPTIONS))
    splu, csc_matrix = _scipy()
    return splu(csc_matrix((data, pattern.indices, pattern.indptr), shape=(pattern.size, pattern.size)),
                permc_spec="COLAMD")


class _Products:
    """NumPy sparse products for one static pattern (no scipy.sparse)."""

    def __init__(self, pattern):
        self.size = pattern.size
        self.rows, self.cols = pattern.rows, pattern.cols
        self.row_order = np.argsort(pattern.rows, kind="stable")
        self.row_ids, self.row_starts = np.unique(pattern.rows[self.row_order], return_index=True)
        self.col_ids, self.col_starts = np.unique(pattern.cols, return_index=True)  # CSC order

    def apply(self, values, x, trans="N"):
        """op(A) x for x (N,) or (N, K); op in {A, A^T, A^H}."""
        x = np.asarray(x)
        vector = x.ndim == 1
        x = x[:, None] if vector else x
        result = np.zeros((self.size, x.shape[1]), dtype=np.complex128)
        if trans == "N":
            contributions = (values[:, None] * x[self.cols])[self.row_order]
            result[self.row_ids] = np.add.reduceat(contributions, self.row_starts, axis=0)
        else:
            weights = values if trans == "T" else np.conj(values)
            result[self.col_ids] = np.add.reduceat(weights[:, None] * x[self.rows], self.col_starts, axis=0)
        return result[:, 0] if vector else result


_PRODUCTS = {}


def _products(pattern):
    if pattern not in _PRODUCTS:
        _PRODUCTS[pattern] = _Products(pattern)
    return _PRODUCTS[pattern]


# Relative tolerance for treating a noise-source matrix as Hermitian. Replacing N^H
# by N within this bound perturbs the noise adjoint source by at most a few units
# of double-precision roundoff relative to max|N|, i.e. the same order as the
# rounding already present when N is assembled. Any larger asymmetry (or a
# structurally unpaired nonzero) keeps the explicit adjoint solve.
HERMITIAN_TOLERANCE = 8 * np.finfo(np.float64).eps

_TRANSPOSES = {}


def _transpose_index(pattern):
    """For each structural entry (r, c): position of (c, r) and whether it exists (static)."""
    if pattern not in _TRANSPOSES:
        size = pattern.size
        keys = pattern.rows.astype(np.int64) * size + pattern.cols
        order = np.argsort(keys, kind="stable")
        ordered = keys[order]
        wanted = pattern.cols.astype(np.int64) * size + pattern.rows
        position = np.clip(np.searchsorted(ordered, wanted), 0, max(ordered.size - 1, 0))
        found = ordered[position] == wanted if ordered.size else np.zeros(0, dtype=bool)
        _TRANSPOSES[pattern] = (order[position] if ordered.size else position, found)
    return _TRANSPOSES[pattern]


def _collinear_coefficient(vector, direction):
    """alpha with vector == alpha * direction (to roundoff), else None.

    Least-squares alpha, accepted only if the residual is within
    HERMITIAN_TOLERANCE * max|vector| (a few units of double roundoff). A zero
    vector gives alpha = 0; a zero direction never matches a nonzero vector.
    """
    scale = np.max(np.abs(vector)) if vector.size else 0.0
    if scale == 0:
        return 0.0
    if not np.isfinite(scale):
        return None
    norm = np.real(np.vdot(direction, direction))
    if norm == 0 or not np.isfinite(norm):
        return None
    alpha = np.vdot(direction, vector) / norm
    if np.max(np.abs(vector - alpha * direction)) <= HERMITIAN_TOLERANCE * scale:
        return alpha
    return None


def _is_hermitian(pattern, values):
    """Whether the sparse matrix with these values equals its conjugate transpose (to roundoff)."""
    values = np.asarray(values)
    if values.shape[-1] != pattern.rows.size:
        return False                       # not a plain coefficient vector: keep the solve
    if values.size == 0:
        return True
    scale = np.max(np.abs(values))
    if scale == 0:
        return True
    if not np.isfinite(scale):
        return False
    index, found = _transpose_index(pattern)
    difference = np.where(found, values - np.conj(values[index]), values)
    return bool(np.max(np.abs(difference)) <= HERMITIAN_TOLERANCE * scale)


def _solve(products, values, factor, rhs, trans):
    """Solve op(A) x = rhs with SuperLU and the iterative refinement of `differometor.sparse`."""
    rhs = np.ascontiguousarray(rhs, dtype=np.complex128)
    solution = factor.solve(rhs, trans=trans)
    for _ in range(REFINEMENT_STEPS):
        correction = factor.solve(np.ascontiguousarray(rhs - products.apply(values, solution, trans)), trans=trans)
        solution = solution + correction
        if np.max(np.abs(correction)) <= REFINEMENT_TOLERANCE * np.max(np.abs(solution)):
            break
    return solution


# Assembly state of the latest forward evaluation (component values, carrier
# factorizations and solution, signal-system factorizations), consumed once by
# its backward evaluation when the backward receives byte-identical assembly
# inputs (verified by digest of the small input arrays; all assembled values and
# factored coefficients are deterministic functions of them), then dropped. A
# mismatch, or a backward without a preceding forward, reassembles and refactors.
# Each forward assembles and factors afresh; nothing is reused across evaluations.
_ASSEMBLY = {}


def _assembly_key(plan, *inputs):
    digest = hashlib.blake2b(digest_size=20)
    for array in inputs:
        array = np.ascontiguousarray(array)
        digest.update(str(array.dtype).encode())
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return plan._key, digest.digest()


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
    carrier_products = _products(structure.carrier.pattern)
    carrier_factors = []
    for row in range(carrier_rows.shape[0]):
        factor = _factor(structure.carrier.pattern, carrier_coefficients[row])
        carrier_factors.append(factor)
        carrier[row] = _solve(carrier_products, carrier_coefficients[row], factor, carrier_rhs[row], "N")
    signal_rows = _expand(carrier_rows, plan.signal_changing, signal_values)
    raw_signal = plan.signal.values(signal_rows, signal_base)
    placing = structure.signal_placing_positions
    placed = raw_signal.copy()
    placed[:, placing] = -raw_signal[:, placing] * carrier[:, plan.signal_carrier_indices]
    final = np.where(structure.signal_conjugate, np.conj(placed), placed)
    noise_rows = signal_rows[:1] if plan.noise_row_reuse else signal_rows
    return dict(carrier_rows=carrier_rows, carrier_values=carrier_vals, carrier_coefficients=carrier_coefficients,
                carrier_factors=carrier_factors, carrier=carrier, signal_rows=signal_rows, raw_signal=raw_signal, signal_values=final,
                noise_rows=noise_rows, noise_values=plan.noise.values(noise_rows, noise_base))


def host_forward(plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base,
                 selection_vectors):
    assembly_inputs = (np.asarray(parameters), np.asarray(carrier_values), np.asarray(signal_values),
                       np.asarray(carrier_base), np.asarray(signal_base), np.asarray(noise_base))
    state = _assemble(plan, *assembly_inputs)
    _ASSEMBLY.clear()
    _ASSEMBLY[_assembly_key(plan, *assembly_inputs)] = state
    structure = plan.structure
    system = structure.signal
    coefficients, rhs = _split(system, state["signal_values"])
    _, selected = _selections(plan, state["carrier"], np.asarray(selection_vectors))
    count, detectors = coefficients.shape[0], selected.shape[0]
    selections = np.moveaxis(np.broadcast_to(selected, (detectors, count, system.size)), 0, 1)
    products, noise_products = _products(system.pattern), _products(structure.noise.pattern)
    signal = np.empty((count, system.size), dtype=np.complex128)
    covariances = np.empty((count, detectors, system.size), dtype=np.complex128)
    weights = np.empty((count, detectors, system.size), dtype=np.complex128)
    factors = []
    for row in range(count):
        factor = _factor(system.pattern, coefficients[row])
        factors.append(factor)
        weight = _solve(products, coefficients[row], factor, selections[row].T, "H")      # A^H w = s
        sources = noise_products.apply(state["noise_values"][0 if plan.noise_row_reuse else row], weight)
        solution = _solve(products, coefficients[row], factor, np.concatenate([rhs[row][:, None], sources], axis=1), "N")
        signal[row], covariances[row], weights[row] = solution[:, 0], solution[:, 1:].T, weight.T
    # Consumed by the matching backward together with the rest of the state:
    # these coefficients are a deterministic function of the digested inputs.
    state["signal_factors"] = factors
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
    parameters, carrier_values = np.asarray(parameters), np.asarray(carrier_values)
    signal_values, selection_vectors = np.asarray(signal_values), np.asarray(selection_vectors)
    carrier, signal, noise = np.asarray(carrier), np.asarray(signal), np.asarray(noise)
    covariances, weights = np.asarray(covariances), np.asarray(weights)
    assembly_inputs = (parameters, carrier_values, signal_values, np.asarray(carrier_base),
                       np.asarray(signal_base), np.asarray(noise_base))
    state = _ASSEMBLY.pop(_assembly_key(plan, *assembly_inputs), None)
    _ASSEMBLY.clear()
    if state is None:
        state = _assemble(plan, *assembly_inputs)
    structure = plan.structure
    system, noise_system, carrier_system = structure.signal, structure.noise, structure.carrier
    coefficients, _ = _split(system, state["signal_values"])
    tiled, selected = _selections(plan, carrier, selection_vectors)
    count, detectors, size = coefficients.shape[0], selected.shape[0], system.size
    selections = np.moveaxis(np.broadcast_to(selected, (detectors, count, size)), 0, 1)

    # noise = sqrt(c t), t = sum Re(cov conj(s)): t_bar = noise_bar c / (2 noise).
    temporary_bar = np.asarray(noise_bar, dtype=np.float64) * _NOISE_SCALE / (2 * noise)      # (D, Bs)
    # The covariance cotangent t_bar conj(s) enters only through the A^T solve below,
    # where it is replaced by its exact solution t_bar conj(w).
    selection_bar = temporary_bar.T[:, :, None] * np.conj(covariances)
    signal_values_bar = np.zeros(state["signal_values"].shape, dtype=np.complex128)
    noise_values_bar = np.zeros(state["noise_values"].shape, dtype=np.complex128)
    pattern, noise_pattern = system.pattern, noise_system.pattern
    products, noise_products = _products(pattern), _products(noise_pattern)
    factors = state.get("signal_factors")
    signal_bar = np.asarray(signal_bar)
    noise_hermitian = [_is_hermitian(noise_pattern, values) for values in state["noise_values"]]
    for row in range(count):
        factor = factors[row] if factors is not None else _factor(pattern, coefficients[row])
        solution = np.concatenate([signal[row][:, None], covariances[row].T], axis=1)           # (N, 1 + D)
        # A^T r = x_bar for x = [signal, covariances]. The covariance columns have
        # x_bar = t_bar conj(s) with real t_bar, and the forward solved A^H w = s;
        # conjugating gives A^T conj(w) = conj(s), so r_cov = t_bar conj(w) exactly.
        # Only the signal column needs a refined solve.
        # The same identity applies to the signal column when its cotangent is a
        # multiple of some conj(s_d): A^T (alpha conj(w_d)) = alpha conj(s_d).
        signal_rhs_bar = None
        for detector in range(detectors):
            alpha = _collinear_coefficient(signal_bar[row], np.conj(selections[row, detector]))
            if alpha is not None:
                signal_rhs_bar = alpha * np.conj(weights[row, detector])
                break
        if signal_rhs_bar is None:
            signal_rhs_bar = _solve(products, coefficients[row], factor, signal_bar[row], "T")
        covariance_rhs_bar = np.conj(weights[row].T) * temporary_bar[:, row][None, :]           # (N, D)
        rhs_bar = np.concatenate([signal_rhs_bar[:, None], covariance_rhs_bar], axis=1)
        coefficient_bar = -np.sum(rhs_bar[pattern.rows] * solution[pattern.cols], axis=1)
        sources_bar, weight = rhs_bar[:, 1:], weights[row].T                                    # (N, D)
        noise_row = 0 if plan.noise_row_reuse else row
        noise_values_bar[noise_row] += np.sum(sources_bar[noise_pattern.rows] * weight[noise_pattern.cols], axis=1)
        # w = conj(A)^-T s: s_bar = conj(A)^-1 w_bar = g; conj(A)_bar[r, c] = -g[c] w[r].
        if noise_hermitian[noise_row]:
            # w_bar = N^T sources_bar = t_bar N^T conj(w), so conj(w_bar) = t_bar N^H w.
            # For Hermitian N this is t_bar N w = t_bar * (forward sources), whose
            # A-solve is t_bar * (forward covariance): g = t_bar cov, adjoint = conj(g).
            adjoint = np.conj(covariances[row].T) * temporary_bar[:, row][None, :]             # (N, D)
        else:
            weight_bar = noise_products.apply(state["noise_values"][noise_row], sources_bar, "T")
            adjoint = np.conj(_solve(products, coefficients[row], factor, np.conj(weight_bar), "N"))
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
    carrier_products = _products(carrier_pattern)
    for row in range(carrier.shape[0]):
        factor = state["carrier_factors"][row]
        rhs_bar = _solve(carrier_products, state["carrier_coefficients"][row], factor, carrier_total_bar[row], "T")
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
    carrier_size = plan.structure.carrier.size
    # Primal carrier and signal are returned transposed, (CN, Bc) and (N, Bs): the
    # layout `simulate` returns, so the XLA programs need no transpose of either
    # array. The (Bc, CN) / (Bs, N) copies are separate outputs used only as
    # backward residuals, so no buffer is both a primal output and a residual.
    return (jax.ShapeDtypeStruct((carrier_size, carrier_count), jnp.complex128),
            jax.ShapeDtypeStruct((size, signal_count), jnp.complex128),
            jax.ShapeDtypeStruct((detectors, signal_count), jnp.float64),
            jax.ShapeDtypeStruct((carrier_count, carrier_size), jnp.complex128),
            jax.ShapeDtypeStruct((signal_count, size), jnp.complex128),
            jax.ShapeDtypeStruct((signal_count, detectors, size), jnp.complex128),
            jax.ShapeDtypeStruct((signal_count, detectors, size), jnp.complex128))


def _transposed(array):
    """C-contiguous transpose (exact copy of the values)."""
    return np.ascontiguousarray(np.asarray(array).T)


def host_forward_transposed(plan, *inputs):
    """`host_forward` plus transposed carrier (CN, Bc) and signal (N, Bs) copies."""
    carrier, signal, noise, covariances, weights = host_forward(plan, *inputs)
    return _transposed(carrier), _transposed(signal), noise, carrier, signal, covariances, weights


def host_backward_transposed(plan, *arguments):
    """`host_backward` for cotangents of the transposed carrier/signal outputs.

    The cotangents arrive as (CN, Bc) and (N, Bs); they are restored to (Bc, CN)
    and (Bs, N) as C-contiguous copies, so `host_backward` receives arrays
    identical in values and memory layout to the untransposed convention.
    """
    (*inputs, carrier, signal, noise, covariances, weights, carrier_bar, signal_bar, noise_bar) = arguments
    return host_backward(plan, *inputs, carrier, signal, noise, covariances, weights,
                         _transposed(carrier_bar), _transposed(signal_bar), noise_bar)


def _forward_call(plan, *inputs):
    return jax.pure_callback(partial(host_forward_transposed, plan),
                             _shapes(plan, inputs[1], inputs[2], inputs[6]),
                             *inputs, vmap_method="sequential")


@partial(jax.custom_vjp, nondiff_argnums=(0,))
def host_pass(plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base,
              selection_vectors):
    """Carrier (CN, Bc), signal (N, Bs) and noise (D, Bs) evaluated on the host."""
    carrier_t, signal_t, noise, _, _, _, _ = _forward_call(
        plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base, selection_vectors)
    return carrier_t, signal_t, noise


def _host_pass_fwd(plan, *inputs):
    carrier_t, signal_t, noise, carrier, signal, covariances, weights = _forward_call(plan, *inputs)
    return (carrier_t, signal_t, noise), (inputs, (carrier, signal, noise, covariances, weights))


def _host_pass_bwd(plan, residuals, cotangents):
    inputs, outputs = residuals
    shapes = tuple(jax.ShapeDtypeStruct(value.shape, value.dtype) for value in inputs)
    return jax.pure_callback(partial(host_backward_transposed, plan), shapes, *inputs, *outputs, *cotangents,
                             vmap_method="sequential")


host_pass.defvjp(_host_pass_fwd, _host_pass_bwd)
