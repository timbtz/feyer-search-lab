"""
Sparse, structure-specialized simulation engine.

`simulate.simulate` evaluates exactly the same physics as the original dense
implementation (kept as `simulate.simulate_reference`), but exploits three facts
about the systems it solves:

1. **Static structure.** Which component function fills which matrix entry, and
   where the non-zeros are, is fixed by the setup. `make_simulation_arrays`
   turns the build step's index arrays into a `SimulationPlan`, a static
   (hashable, leaf-less) pytree node. Under `jax.jit` the plan becomes compile-time
   constants, so each component function is traced once for exactly the entries
   that use it, instead of `lax.switch`-ing over all 19 functions for every entry.

2. **Sparsity.** The signal system (751 x 751 for the public setup) has about
   3 non-zeros per row (0.45 % dense), with the same pattern at every frequency.
   It is stored as values on a fixed pattern and factorized with SuperLU
   (`scipy.sparse.linalg.splu`), once per frequency.

3. **One factorization, two solves.** The signal solve `A x = b` and the
   quantum-noise weights `A^H w = s` share the same LU factors. The noise
   covariance `s^H A^-1 M A^-H s` equals `w^H M w`, so the third (covariance)
   solve of the dense implementation is not needed.

The sparse solves run on the host through `jax.pure_callback`, wrapped in a
`jax.custom_vjp` whose reverse pass reuses the forward pass's LU factors
(adjoint method: one `A^T` solve and one `A` solve per frequency).
"""

from __future__ import annotations

import itertools
from collections import OrderedDict
from functools import partial

import numpy as np
import jax
import jax.numpy as jnp
from jax import vmap

from differometor.components import FUNCTIONS, UNIT_VACUUM, H_PLANCK, F0


# ---------------------------------------------------------------------------
# Static plan
# ---------------------------------------------------------------------------

HOST_ENGINE = True
"""Use the host (NumPy) engine when possible. Set to False to force the traced JAX path."""


class SimulationPlan:
    """
    Compile-time structure of one built setup (index arrays, sparsity patterns).

    Registered as a static pytree node: it has no array leaves, so passing it to
    a jitted function makes its contents Python/NumPy constants during tracing.
    Hashing and equality are by identity, which is what the jit cache needs.
    """

    def __init__(self, **fields):
        self.__dict__.update(fields)

    def __repr__(self) -> str:
        return (f"SimulationPlan(signal_size={self.signal_size}, signal_nnz={len(self.a_rows)}, "
                f"noise_nnz={len(self.noise_rows)}, frequencies={self.num_signal_rows})")


jax.tree_util.register_static(SimulationPlan)


def _as_np(array) -> np.ndarray:
    return np.asarray(array)


def _stage_plan(function_input_indices, function_indices, output_indices, matrix_indices, num_columns):
    """
    Group a stage's function evaluations by component function.

    Returns
    -------
    groups : list of (function_index, input_indices (K_t, I))
        One entry per distinct component function, in a fixed order.
    source : (E,) int
        For each matrix update, its position in the concatenated group outputs
        (group outputs are flattened as K_t * 4 complex values).
    target_rows, target_columns : (E,) int
        Matrix position written by each update. Duplicates are resolved the way
        a sequential scatter would (last write wins).
    """
    inputs = _as_np(function_input_indices)
    functions = _as_np(function_indices).astype(int)
    outputs = _as_np(output_indices).astype(int)
    targets = _as_np(matrix_indices).astype(int)

    used = np.zeros(len(functions), dtype=bool)
    used[outputs[0]] = True

    flat_position = np.full(len(functions), -1)
    groups, offset = [], 0
    for function_index in np.unique(functions[used]):
        members = np.nonzero((functions == function_index) & used)[0]
        groups.append((int(function_index), inputs[members]))
        flat_position[members] = offset + 4 * np.arange(len(members))
        offset += 4 * len(members)

    source = flat_position[outputs[0]] + outputs[1]
    rows = targets[0]
    columns = np.mod(targets[1], num_columns)

    # Last write wins for duplicated targets.
    keys = rows * num_columns + columns
    _, last = np.unique(keys[::-1], return_index=True)
    keep = np.sort(len(keys) - 1 - last)
    return groups, source[keep], rows[keep], columns[keep]


def _positions(pattern_keys: np.ndarray, rows: np.ndarray, columns: np.ndarray, num_columns: int):
    """Map (row, column) pairs to indices into a sorted pattern; -1 where absent."""
    keys = rows * num_columns + columns
    index = np.searchsorted(pattern_keys, keys)
    index = np.minimum(index, len(pattern_keys) - 1)
    return np.where(pattern_keys[index] == keys, index, -1)


def make_simulation_arrays(prepared, matrices, carrier_arrays, signal_arrays, noise_arrays) -> dict:
    """
    Build the `simulate` keyword arguments: a static `SimulationPlan` plus numeric arrays.

    Parameters
    ----------
    prepared, matrices, carrier_arrays, signal_arrays, noise_arrays :
        Outputs of `prepare_arrays`, `build` and `pairs_to_arrays`, exactly as
        consumed by the dense reference implementation.
    """
    (optimized_parameters, optimized_parameter_indices, optimized_value_indices,
     carrier_changing_parameter_indices, carrier_changing_values,
     signal_changing_parameter_indices, signal_changing_values) = prepared
    (parameters, carrier_matrix, signal_matrix, noise_matrix, noise_selection_vectors,
     qhd_parameter_indices, qhd_placing_indices, linked_indices, linking_function_indices,
     indices_to_link) = matrices

    carrier_matrix = _as_np(carrier_matrix)
    signal_matrix = _as_np(signal_matrix)
    noise_matrix = _as_np(noise_matrix)
    carrier_size = carrier_matrix.shape[0]
    signal_size, augmented_columns = signal_matrix.shape
    num_signal_rows = _as_np(carrier_changing_values).shape[1] * _as_np(signal_changing_values).shape[1]

    # Carrier stage: dense (small system), solved exactly as in the reference implementation.
    carrier_groups, carrier_source, carrier_rows, carrier_columns = _stage_plan(
        *carrier_arrays, num_columns=carrier_matrix.shape[1])

    # Signal stage: augmented matrix [A | b] on a fixed sparsity pattern.
    (signal_fii, signal_fi, signal_oi, signal_mi, carrier_solution_indices,
     carrier_placing_indices) = signal_arrays
    signal_groups, signal_source, signal_rows, signal_columns = _stage_plan(
        signal_fii, signal_fi, signal_oi, signal_mi, num_columns=augmented_columns)

    base_rows, base_columns = np.nonzero(signal_matrix)
    pattern_keys = np.union1d(base_rows * augmented_columns + base_columns,
                              signal_rows * augmented_columns + signal_columns)
    pattern_rows, pattern_columns = np.divmod(pattern_keys, augmented_columns)
    signal_values = signal_matrix[pattern_rows, pattern_columns]
    signal_update_positions = _positions(pattern_keys, signal_rows, signal_columns, augmented_columns)

    # Entries scaled by the carrier solution (signal connectors). Entries outside the
    # pattern are structurally zero and stay zero after scaling, so they are dropped.
    placing = _as_np(carrier_placing_indices).astype(int)
    placing_rows, placing_columns = placing[0], np.mod(placing[1], augmented_columns)
    placing_sources = _as_np(carrier_solution_indices).astype(int).reshape(-1)
    keys = placing_rows * augmented_columns + placing_columns
    _, last = np.unique(keys[::-1], return_index=True)
    keep = np.sort(len(keys) - 1 - last)
    placing_positions = _positions(pattern_keys, placing_rows[keep], placing_columns[keep], augmented_columns)
    present = placing_positions >= 0
    placing_positions, placing_sources = placing_positions[present], placing_sources[keep][present]

    # Upper/lower sideband conjugation blocks (same regions as the reference implementation).
    c = carrier_size
    conjugate = (
        ((pattern_rows >= c) & (pattern_rows < 2 * c) & (pattern_columns >= c) & (pattern_columns < 2 * c))
        | ((pattern_rows >= 2 * c) & (pattern_columns < c))
        | ((pattern_rows >= c) & (pattern_rows < 2 * c) & (pattern_columns >= 2 * c))
    )
    conjugate_positions = np.nonzero(conjugate)[0]

    # Split [A | b]: A entries in CSC order (column-major) for SuperLU, b entries separately.
    is_rhs = pattern_columns == signal_size
    a_positions = np.nonzero(~is_rhs)[0]
    order = np.lexsort((pattern_rows[a_positions], pattern_columns[a_positions]))
    a_positions = a_positions[order]
    a_rows, a_columns = pattern_rows[a_positions], pattern_columns[a_positions]
    a_indptr = np.concatenate([[0], np.cumsum(np.bincount(a_columns, minlength=signal_size))])
    rhs_positions = np.nonzero(is_rhs)[0]
    rhs_rows = pattern_rows[rhs_positions]

    # Noise stage: quantum noise source matrix on its own sparse pattern.
    noise_groups, noise_source, noise_rows_upd, noise_columns_upd = _stage_plan(
        *noise_arrays, num_columns=noise_matrix.shape[1])
    noise_base_rows, noise_base_columns = np.nonzero(noise_matrix)
    noise_keys = np.union1d(noise_base_rows * signal_size + noise_base_columns,
                            noise_rows_upd * signal_size + noise_columns_upd)
    noise_rows, noise_columns = np.divmod(noise_keys, signal_size)
    noise_values = noise_matrix[noise_rows, noise_columns]
    noise_update_positions = _positions(noise_keys, noise_rows_upd, noise_columns_upd, signal_size)

    qhd_placing = _as_np(qhd_placing_indices).astype(int).reshape(-1, 3)

    plan = SimulationPlan(
        carrier_size=carrier_size,
        signal_size=signal_size,
        num_signal_rows=num_signal_rows,
        optimized_parameter_indices=_as_np(optimized_parameter_indices).astype(int),
        optimized_value_indices=_as_np(optimized_value_indices).astype(int),
        linked_indices=_as_np(linked_indices).astype(int),
        linking_function_indices=_as_np(linking_function_indices).astype(int),
        indices_to_link=_as_np(indices_to_link).astype(int),
        qhd_parameter_indices=_as_np(qhd_parameter_indices).astype(int),
        qhd_placing=qhd_placing,
        carrier_changing_parameter_indices=_as_np(carrier_changing_parameter_indices).astype(int),
        signal_changing_parameter_indices=_as_np(signal_changing_parameter_indices).astype(int),
        carrier_groups=carrier_groups,
        carrier_source=carrier_source,
        carrier_rows=carrier_rows,
        carrier_columns=carrier_columns,
        signal_groups=signal_groups,
        signal_source=signal_source,
        signal_update_positions=signal_update_positions,
        placing_positions=placing_positions,
        placing_sources=placing_sources,
        conjugate_positions=conjugate_positions,
        a_positions=a_positions,
        a_rows=a_rows,
        a_columns=a_columns,
        a_indptr=a_indptr,
        rhs_positions=rhs_positions,
        rhs_rows=rhs_rows,
        noise_groups=noise_groups,
        noise_source=noise_source,
        noise_update_positions=noise_update_positions,
        noise_rows=noise_rows,
        noise_columns=noise_columns,
    )
    plan.noise_output_shape = tuple(
        size for size in (_as_np(noise_selection_vectors).shape[0], num_signal_rows) if size != 1)
    plan.linear_block = make_linear_block(plan)

    # Physical setups have real parameters (stored as complex). Then the whole simulation
    # can run on the host (see `differometor.host`); otherwise use the traced JAX path.
    real_inputs = all(
        not np.iscomplexobj(a) or not np.any(np.imag(a))
        for a in (_as_np(parameters), _as_np(carrier_changing_values), _as_np(signal_changing_values)))
    plan.host_simulate = None
    if real_inputs and HOST_ENGINE:
        from differometor.host import make_host_simulate
        try:
            plan.host_simulate = make_host_simulate(plan)
        except NotImplementedError as error:  # e.g. a custom component outside the interpreter's coverage
            import warnings
            warnings.warn(f"differometor: host engine unavailable ({error}); using the traced JAX path.")

    return {
        "optimized_parameters": None if optimized_parameters is None else jnp.asarray(optimized_parameters),
        "plan": plan,
        "parameters": jnp.asarray(parameters),
        "carrier_changing_values": jnp.asarray(carrier_changing_values),
        "signal_changing_values": jnp.asarray(signal_changing_values),
        "carrier_matrix": jnp.asarray(carrier_matrix),
        "signal_values": jnp.asarray(signal_values),
        "noise_values": jnp.asarray(noise_values),
        "noise_selection_vectors": jnp.asarray(noise_selection_vectors),
    }


# ---------------------------------------------------------------------------
# Host-side sparse LU (SuperLU) with factor reuse between forward and reverse pass
# ---------------------------------------------------------------------------

_FACTOR_CACHE: "OrderedDict[int, list]" = OrderedDict()
_FACTOR_CACHE_SIZE = 4
_TOKENS = itertools.count(1)


def _forward_host(values, rhs, selections, *, plan, remember):
    """Solve A x = b and A^H w = s per frequency with one (refined) sparse LU each."""
    from differometor.host import SparseSystem

    system = SparseSystem(plan, np.asarray(values))
    x = system.solve(np.asarray(rhs), "N")
    w = system.solve(np.asarray(selections), "H")
    token = 0
    if remember:
        token = next(_TOKENS)
        _FACTOR_CACHE[token] = system
        while len(_FACTOR_CACHE) > _FACTOR_CACHE_SIZE:
            _FACTOR_CACHE.popitem(last=False)
    return x, w, np.asarray(token, dtype=np.int64)


def _backward_host(values, token, x_bar, w_bar, *, plan):
    """Adjoint solves: lambda = A^-T x_bar,  mu = conj(A^-1 conj(w_bar))."""
    from differometor.host import SparseSystem

    system = _FACTOR_CACHE.get(int(token))
    if system is None:  # e.g. pullback used after its factors were evicted
        system = SparseSystem(plan, np.asarray(values))
    lam = system.solve(np.asarray(x_bar), "T")
    mu = np.conj(system.solve(np.conj(np.asarray(w_bar)), "N"))
    return lam, mu


def make_linear_block(plan: SimulationPlan):
    """
    Differentiable `(values, b, s) -> (A^-1 b, A^-H s)` for the plan's sparse pattern.

    values : (F, nnz) complex, entries of A in the plan's CSC order
    b      : (F, N) complex
    s      : (D, F, N) complex
    """
    rows, columns = plan.a_rows, plan.a_columns

    def shapes(values, rhs, selections):
        return (jax.ShapeDtypeStruct(rhs.shape, jnp.complex128),
                jax.ShapeDtypeStruct(selections.shape, jnp.complex128),
                jax.ShapeDtypeStruct((), jnp.int64))

    def host_call(values, rhs, selections, remember):
        return jax.pure_callback(
            partial(_forward_host, plan=plan, remember=remember),
            shapes(values, rhs, selections), values, rhs, selections,
            vmap_method="sequential",
        )

    @jax.custom_vjp
    def linear_block(values, rhs, selections):
        x, w, _ = host_call(values, rhs, selections, remember=False)
        return x, w

    def forward(values, rhs, selections):
        x, w, token = host_call(values, rhs, selections, remember=True)
        return (x, w), (values, x, w, token)

    def backward(residuals, cotangents):
        values, x, w, token = residuals
        x_bar, w_bar = cotangents
        lam, mu = jax.pure_callback(
            partial(_backward_host, plan=plan),
            (jax.ShapeDtypeStruct(x_bar.shape, jnp.complex128),
             jax.ShapeDtypeStruct(w_bar.shape, jnp.complex128)),
            values, token, x_bar, w_bar,
            vmap_method="sequential",
        )
        # x = A^-1 b:   dA_ij += -lam_i x_j
        # w = A^-H s:   dA_ij += -conj(w_i mu_j)
        values_bar = -lam[:, rows] * x[:, columns] - jnp.sum(jnp.conj(w[:, :, rows] * mu[:, :, columns]), axis=0)
        return values_bar, lam, mu

    linear_block.defvjp(forward, backward)
    return linear_block


# ---------------------------------------------------------------------------
# Traced simulation
# ---------------------------------------------------------------------------

def _evaluate_groups(groups, parameters: jnp.ndarray) -> jnp.ndarray:
    """Evaluate each component function on exactly its own inputs; (R, sum_t 4 K_t)."""
    outputs = []
    for function_index, input_indices in groups:
        inputs = parameters[:, input_indices]  # (R, K_t, I)
        values = vmap(vmap(FUNCTIONS[function_index]))(inputs)  # (R, K_t, 4)
        outputs.append(values.reshape(parameters.shape[0], -1))
    return jnp.concatenate(outputs, axis=1)


def _expand(parameters: jnp.ndarray, indices: np.ndarray, values: jnp.ndarray) -> jnp.ndarray:
    """Tile parameter rows per sweep value and write the swept columns (as `expand_parameters`)."""
    count = values.shape[1]
    tiled = jnp.tile(parameters, (count, 1))
    return tiled.at[np.arange(count)[:, None], indices[None, :]].set(values.T.astype(tiled.dtype))


def simulate_sparse(
    optimized_parameters,
    plan: SimulationPlan,
    parameters,
    carrier_changing_values,
    signal_changing_values,
    carrier_matrix,
    signal_values,
    noise_values,
    noise_selection_vectors,
):
    """Carrier, signal and quantum noise for one setup; see `simulate.simulate`."""
    if plan.host_simulate is not None:
        return plan.host_simulate(
            jnp.asarray(optimized_parameters, dtype=jnp.float64), parameters, carrier_changing_values,
            signal_changing_values, carrier_matrix, signal_values, noise_values, noise_selection_vectors)

    from differometor.build import LINKING_FUNCTIONS
    from differometor.simulate import solve

    # Optimized values and linked parameters (single parameter row).
    parameters = parameters.at[0, plan.optimized_parameter_indices].set(
        optimized_parameters[plan.optimized_value_indices].astype(parameters.dtype))
    linked_inputs = parameters[0, plan.linked_indices]
    linked_outputs = jnp.stack([
        jnp.asarray(LINKING_FUNCTIONS[function_index](linked_inputs[position]), dtype=parameters.dtype)
        for position, function_index in enumerate(plan.linking_function_indices)
    ])
    parameters = parameters.at[0, plan.indices_to_link].set(linked_outputs)
    qhd_phases = jnp.exp(1j * jnp.radians(parameters[0, plan.qhd_parameter_indices]))

    # Carrier (dense, small): identical algorithm to the reference implementation.
    parameters = _expand(parameters, plan.carrier_changing_parameter_indices, carrier_changing_values)
    carrier_outputs = _evaluate_groups(plan.carrier_groups, parameters)
    carrier_system = jnp.broadcast_to(carrier_matrix, (parameters.shape[0],) + carrier_matrix.shape)
    carrier_system = carrier_system.at[:, plan.carrier_rows, plan.carrier_columns].set(
        carrier_outputs[:, plan.carrier_source])
    carrier = vmap(solve)(carrier_system[:, :, :-1], carrier_system[:, :, -1])

    # Signal system values on the sparse pattern, one row per signal frequency.
    parameters = _expand(parameters, plan.signal_changing_parameter_indices, signal_changing_values)
    rows = parameters.shape[0]
    signal_outputs = _evaluate_groups(plan.signal_groups, parameters)
    values = jnp.broadcast_to(signal_values, (rows, signal_values.shape[0]))
    values = values.at[:, plan.signal_update_positions].set(signal_outputs[:, plan.signal_source])
    values = values.at[:, plan.placing_positions].set(
        -values[:, plan.placing_positions] * carrier[:, plan.placing_sources])
    values = values.at[:, plan.conjugate_positions].set(jnp.conjugate(values[:, plan.conjugate_positions]))
    matrix_values = values[:, plan.a_positions]
    rhs = jnp.zeros((rows, plan.signal_size), dtype=jnp.complex128).at[:, plan.rhs_rows].set(
        values[:, plan.rhs_positions])

    # Detector selection vectors (with homodyne phases), as in the reference implementation.
    c = plan.carrier_size
    selections = noise_selection_vectors.at[
        plan.qhd_placing[:, 0], plan.qhd_placing[:, 1], plan.qhd_placing[:, 2]].multiply(qhd_phases)
    selections = jnp.tile(selections, (1, carrier.shape[0], 1))
    upper = selections.at[:, :, :c].set(selections[:, :, :c] * carrier)
    lower = jnp.conjugate(upper[:, :, c:2 * c] * carrier)
    selections = upper.at[:, :, c:2 * c].set(lower)
    selections = jnp.broadcast_to(selections, (selections.shape[0], rows, selections.shape[2]))

    signal, weights = plan.linear_block(matrix_values, rhs, selections)

    # Quantum noise: s^H A^-1 M A^-H s = w^H M w with w = A^-H s.
    noise_outputs = _evaluate_groups(plan.noise_groups, parameters)
    noise_matrix = jnp.broadcast_to(noise_values, (rows, noise_values.shape[0]))
    noise_matrix = noise_matrix.at[:, plan.noise_update_positions].set(noise_outputs[:, plan.noise_source])
    sources = jnp.zeros_like(weights).at[:, :, plan.noise_rows].add(noise_matrix * weights[:, :, plan.noise_columns])
    quadratic = jnp.sum(jnp.real(jnp.conjugate(weights) * sources), axis=2)
    noise = jnp.sqrt(2 * quadratic * UNIT_VACUUM * H_PLANCK * F0 * 0.25)

    return carrier.T, signal.T, noise.squeeze()
