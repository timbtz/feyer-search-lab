"""
JAX-based optical simulation runner.

This module builds linear systems from a `differometor` `Setup` and solves:
- a carrier (steady-state) system,
- a signal (sideband) system,
- and a quantum noise propagation system.

The main public entry points are:
- `run`: build once and simulate once
- `run_setups`: run multiple setups over a shared frequency grid
- `run_with_parameter_sets`: run the same setup over many optimized-parameter sets

Conventions used throughout:
- Arrays are JAX arrays (`jax.numpy`).
- Shapes are documented explicitly for every function.
- All indices are integer arrays that index into parameter vectors and matrix entries.
"""

import jax
import jax.scipy.linalg
from functools import partial
from time import time
import jax.numpy as jnp
import numpy as np
from jax import lax, vmap, jit

from differometor.setups import Setup
from differometor.build import build, pairs_to_arrays, prepare_arrays, LINKING_FUNCTIONS
from differometor.components import FUNCTIONS, UNIT_VACUUM, H_PLANCK, F0
from differometor import components as _components


jax.config.update("jax_enable_x64", True)


def solve(matrix: jnp.ndarray, right_hand_side: jnp.ndarray) -> jnp.ndarray:
    """
    Solve a dense linear system for each batch item.

    Parameters
    ----------
    matrix : jnp.ndarray
        System matrix with shape (..., system_size, system_size).
    right_hand_side : jnp.ndarray
        Right-hand side vector with shape (..., system_size).

    Returns
    -------
    solution : jnp.ndarray
        Solution vector with shape (..., system_size).

    Notes
    -----
    Both inputs are cast to complex128 to reduce numerical issues during solving.

    The function intentionally returns the raw complex solution rather than derived
    quantities (such as phase or amplitude), because some downstream transforms
    (notably `jnp.angle`) can produce invalid gradients in some configurations.
    """
    right_hand_side = right_hand_side.astype(jnp.complex128)
    matrix = matrix.astype(jnp.complex128)
    return jnp.linalg.solve(matrix, right_hand_side)


@jit
def _evaluate_component(function_and_inputs):
    """Keep recomputation within the selected component's reverse branch."""
    function_index, function_inputs = function_and_inputs
    branches = tuple(jax.checkpoint(function, prevent_cse=False) for function in FUNCTIONS)
    return lax.switch(function_index, branches, function_inputs)


@partial(jit, static_argnums=(0,), inline=True)
def _evaluate_component_group(function_index, function_inputs):
    """Vectorize one component type without batching a dynamic branch selector."""
    return vmap(FUNCTIONS[function_index])(function_inputs)


class _ParameterSlots:
    """Integer-indexable stand-in for a component's parameter vector.

    Each slot is a separate scalar, so slots under `lax.stop_gradient` carry
    symbolic-zero tangents and their derivative terms are never formed.
    """

    __slots__ = ("values",)

    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        if isinstance(index, (int, np.integer)):
            return self.values[index]
        return jnp.stack(self.values)[index]


@partial(jit, static_argnums=(0, 1), inline=True)
def _evaluate_component_group_slots(function_index, differentiable, function_inputs):
    """Like `_evaluate_component_group`, with constant input slots gradient-stopped.

    `differentiable` is a static per-slot mask from the builder: a slot is False
    only when no row of the group reads a parameter that depends on the optimized
    values (optimized or linked indices), so its true derivative is exactly zero.
    Forward values are unchanged (stop_gradient is the identity).
    """
    function = FUNCTIONS[function_index]
    columns = tuple(
        function_inputs[:, slot] if keep else lax.stop_gradient(function_inputs[:, slot])
        for slot, keep in enumerate(differentiable)
    )
    base = _LOWER_TO_BASE.get(function)
    if base is not None:
        # Preserve symbolic-zero slot tangents through lower-sideband wrappers.
        # Their array reconstruction otherwise gives the base a dense tangent.
        def evaluate(*values):
            return base(_ParameterSlots((-values[0],) + tuple(values[1:])))
        return vmap(evaluate)(*columns)
    return vmap(lambda *values: function(_ParameterSlots(values)))(*columns)


_LOWER_TO_BASE = {
    _components.space_lower: _components.space,
    _components.space_modulation_lower: _components.space_modulation,
    _components.laser_frequency_modulation_lower: _components.laser_frequency_modulation,
}


def _save_assembly_indices(primitive, *avals, **params):
    """Retain only discrete indexing results; recompute complex arithmetic."""
    # JAX 0.9.0 inserts reduce_precision on saved inexact residuals, which
    # rejects complex128. These operations preserve discrete dtypes (apart
    # from conversion, whose destination dtype is checked separately).
    if primitive.name not in (
        "gather", "lt", "le", "gt", "ge", "eq", "ne", "add", "sub",
        "mul", "select_n", "broadcast_in_dim", "reshape", "concatenate",
        "convert_element_type",
    ):
        return False

    def discrete(dtype):
        return dtype is not None and (
            np.issubdtype(dtype, np.integer) or np.issubdtype(dtype, np.bool_)
        )

    return bool(avals) and all(discrete(getattr(aval, "dtype", None)) for aval in avals) and (
        primitive.name != "convert_element_type" or discrete(params.get("new_dtype"))
    )


@partial(jax.checkpoint, prevent_cse=False, policy=_save_assembly_indices)
def _component_values(
    parameters,
    function_input_indices,
    output_indices,
    function_indices,
    component_groups,
):
    """Recompute component values; carrier coupling and dense assembly stay outside."""
    output_rows = output_indices[0]
    # Keep the function selector scalar so only the selected component branch
    # executes. The outer vmap in simulate still batches frequency samples.
    if component_groups is None:
        function_inputs = parameters[function_input_indices]
        output_matrix = lax.map(
            _evaluate_component,
            (function_indices, function_inputs),
        )
    else:
        # Select directly from grouped outputs using the builder's permutation.
        # The final matrix scatter retains its original update order, including
        # possibly overlapping destinations and parameter-dependent zeros.
        group_values = []
        function_rows = component_groups["function_rows"]
        for function_index in sorted(function_rows):
            rows = function_rows[function_index]
            # New builders compose these structural indices on the host.
            if "parameter_indices" in component_groups:
                input_indices = component_groups["parameter_indices"][function_index]
            else:
                input_indices = function_input_indices[rows]
            group_inputs = parameters[input_indices]
            diff_slots = component_groups.get("diff_slots")
            if (
                diff_slots is not None
                and function_index in diff_slots
                and group_inputs.ndim == 2
            ):
                differentiable = tuple(
                    slot in diff_slots[function_index] for slot in range(group_inputs.shape[1])
                )
                row_split = component_groups.get("row_split", {})
                if function_index in row_split:
                    # Mixed groups are ordered as [dependent rows, constant rows].
                    # Separate evaluation preserves zero tangents for the latter.
                    count = next(iter(row_split[function_index]))
                    group_values.append(
                        _evaluate_component_group_slots(
                            function_index, differentiable, group_inputs[:count]
                        )
                    )
                    group_values.append(
                        _evaluate_component_group_slots(
                            function_index, (False,) * len(differentiable), group_inputs[count:]
                        )
                    )
                else:
                    group_values.append(
                        _evaluate_component_group_slots(function_index, differentiable, group_inputs)
                    )
            else:
                group_values.append(_evaluate_component_group(function_index, group_inputs))
        if group_values:
            output_matrix = jnp.concatenate(group_values, axis=0)
            if "flat_output_indices" not in component_groups:
                output_rows = component_groups["output_rows"][output_rows]
        else:
            output_matrix = jnp.zeros((function_input_indices.shape[0], 4), dtype=jnp.complex128)
    if component_groups is not None and "flat_output_indices" in component_groups:
        outputs = lax.gather(
            output_matrix.reshape(-1),
            component_groups["flat_output_indices"].reshape(-1, 1),
            lax.GatherDimensionNumbers(
                offset_dims=(), collapsed_slice_dims=(0,), start_index_map=(0,),
            ),
            slice_sizes=(1,),
            mode="promise_in_bounds",
        )
    else:
        outputs = output_matrix[output_rows, output_indices[1]]
    return outputs


def update(
    parameters: jnp.ndarray,
    matrix: jnp.ndarray,
    function_input_indices: jnp.ndarray,
    output_indices: tuple[jnp.ndarray, jnp.ndarray],
    matrix_indices: tuple[jnp.ndarray, jnp.ndarray],
    function_indices: jnp.ndarray,
    component_groups: dict | None = None,
    carrier_entries: jnp.ndarray | None = None,
) -> jnp.ndarray:
    """
    Update selected entries of a system matrix by evaluating component functions.

    This function takes a parameter vector, selects the subset that serves as
    inputs to component transfer functions, evaluates those functions, selects
    certain outputs, and writes them into `matrix` at specified indices.

    Parameters
    ----------
    parameters : jnp.ndarray
        Parameter values for one simulation instance, shape (P,).
    matrix : jnp.ndarray
        Base matrix to update, shape (N, N + 1) for augmented systems, or (N, N).
        The function writes entries in-place (functionally) using `.at[...].set(...)`.
    function_input_indices : jnp.ndarray
        Indices into `parameters` selecting inputs to the component functions,
        shape (K,).
    output_indices : tuple[jnp.ndarray, jnp.ndarray]
        Pair of index arrays selecting entries from the evaluated output matrix.
        Each element has shape (M,). Together they define M output positions.
    matrix_indices : tuple[jnp.ndarray, jnp.ndarray]
        Pair of index arrays selecting where to write into `matrix`.
        Each element has shape (M,).
    function_indices : jnp.ndarray
        Indices selecting which function to use for each input, shape (K,).
        Values index into the global `FUNCTIONS` list.
    component_groups : dict | None
        Optional builder-produced structural partition of the function rows.
        `function_rows` has static function-ID keys and original input-row arrays;
        `output_rows` maps original output rows to concatenated group rows.
        `parameter_indices`, when present, supplies prepared input indices per group.
        An optional `unique_matrix_indices` key marks verified distinct destinations.
        `flat_matrix_indices` supplies normalized, in-bounds row-major destinations.
        `flat_output_indices` supplies composed, in-bounds component output offsets.
        `diff_slots` optionally marks inputs dependent on optimized or linked parameters
        for optimized-parameter differentiation; rebuild it when optimization pairs change.
        Omit or rebuild metadata when changing selectors, input/output indices, matrix shape
        or matrix destinations, including carrier coupling destinations.
    carrier_entries : jnp.ndarray | None
        Optional carrier factors, used only with builder-proven
        `carrier_output_positions` to scale component values before matrix assembly.

    Returns
    -------
    updated_matrix : jnp.ndarray
        Matrix with updated entries, same shape as `matrix`.

    Notes
    -----
    `lax.switch` selects functions from the global `FUNCTIONS` list. In JAX, a
    Python list of callables referenced as a global is treated as static during
    tracing, which keeps the function jittable as long as the list is stable.
    """
    outputs = _component_values(
        parameters, function_input_indices, output_indices, function_indices,
        component_groups,
    )
    # Keep the selected component values available to the carrier-product
    # transpose without including that coupling in checkpoint recomputation.
    if carrier_entries is not None:
        positions = component_groups["carrier_output_positions"]
        scaled_outputs = -outputs[positions] * carrier_entries
        outputs = outputs.at[positions].set(scaled_outputs, unique_indices=True)
    if component_groups is not None and "flat_matrix_indices" in component_groups:
        # Builder-proven unique, in-bounds offsets avoid tracing the generic
        # two-coordinate indexing path. Update order and component values stay
        # identical; callers without the proof retain the original scatter.
        flattened = lax.scatter(
            matrix.reshape(-1),
            component_groups["flat_matrix_indices"].reshape(-1, 1),
            outputs,
            lax.ScatterDimensionNumbers(
                update_window_dims=(),
                inserted_window_dims=(0,),
                scatter_dims_to_operand_dims=(0,),
            ),
            unique_indices=True,
            mode="promise_in_bounds",
        )
        return flattened.reshape(matrix.shape)
    unique_indices = component_groups is not None and "unique_matrix_indices" in component_groups
    return matrix.at[matrix_indices[0], matrix_indices[1]].set(outputs, unique_indices=unique_indices)


def expand_parameters(array: jnp.ndarray, indices: jnp.ndarray, values: jnp.ndarray) -> jnp.ndarray:
    """
    Expand a single parameter row into multiple rows by replacing selected entries.

    Parameters
    ----------
    array : jnp.ndarray
        Base parameter array with shape (1, P).
    indices : jnp.ndarray
        Column indices to replace, shape (V,).
    values : jnp.ndarray
        Replacement values stacked row-wise for each index, shape (V, R),
        where R is the number of expanded rows.

        Example:
        - array shape (1, 5)
        - indices shape (2,)
        - values shape (2, 3)
        Output has shape (3, 5), where the two indexed columns are filled from
        `values[:, row]`.

    Returns
    -------
    expanded : jnp.ndarray
        Expanded parameter array with shape (R, P).

    Notes
    -----
    This implementation uses indexed updates that remain compatible with JAX
    transformations and compilation.
    """
    tiled_array = jnp.tile(array, (values.shape[1], 1))
    row_indices = jnp.repeat(jnp.arange(values.shape[1]), len(indices))
    column_indices = jnp.tile(indices, values.shape[1])
    flat_values = values.T.flatten()
    return tiled_array.at[row_indices, column_indices].set(flat_values)


def simulate(
    # prepared arrays
    optimized_parameters: jnp.ndarray,
    optimized_parameter_indices: jnp.ndarray,
    optimized_value_indices: jnp.ndarray,
    carrier_changing_parameter_indices: jnp.ndarray,
    carrier_changing_values: jnp.ndarray,
    signal_changing_parameter_indices: jnp.ndarray,
    signal_changing_values: jnp.ndarray,
    # matrices
    parameters: jnp.ndarray,
    carrier_matrix: jnp.ndarray,
    signal_matrix: jnp.ndarray,
    noise_matrix: jnp.ndarray,
    noise_selection_vectors: jnp.ndarray,
    qhd_parameter_indices: jnp.ndarray,
    qhd_placing_indices: jnp.ndarray,
    linked_indices: jnp.ndarray,
    linking_function_indices: jnp.ndarray,
    indices_to_link: jnp.ndarray,
    # carrier arrays
    carrier_function_input_indices: jnp.ndarray,
    carrier_function_indices: jnp.ndarray,
    carrier_output_indices: tuple[jnp.ndarray, jnp.ndarray],
    carrier_matrix_indices: tuple[jnp.ndarray, jnp.ndarray],
    # signal arrays
    signal_function_input_indices: jnp.ndarray,
    signal_function_indices: jnp.ndarray,
    signal_output_indices: tuple[jnp.ndarray, jnp.ndarray],
    signal_matrix_indices: tuple[jnp.ndarray, jnp.ndarray],
    signal_carrier_indices: jnp.ndarray,
    signal_carrier_placing_indices: tuple[jnp.ndarray, jnp.ndarray],
    # noise arrays
    noise_function_input_indices: jnp.ndarray,
    noise_function_indices: jnp.ndarray,
    noise_output_indices: tuple[jnp.ndarray, jnp.ndarray],
    noise_system_matrix_indices: tuple[jnp.ndarray, jnp.ndarray],
    *,
    component_groups: dict | None = None,
) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """
    Run one full simulation pass: carrier, signal, and quantum noise.

    Parameters
    ----------
    optimized_parameters : jnp.ndarray
        Optimized parameter values provided by an optimizer or sampling routine,
        shape (OPV,) or (num_ranges, OPV) in outer vectorization contexts.
    optimized_parameter_indices : jnp.ndarray
        Indices into `parameters` for parameters that are driven by optimized values,
        shape (OP,).
    optimized_value_indices : jnp.ndarray
        Indices into `optimized_parameters` mapping each optimized parameter to
        its source value, shape (OP,). This supports shared optimized values.
    carrier_changing_parameter_indices : jnp.ndarray
        Indices into `parameters` that change for the carrier sweep, shape (CCP,).
    carrier_changing_values : jnp.ndarray
        Values for those carrier-changing parameters, shape (CCP, CV).
    signal_changing_parameter_indices : jnp.ndarray
        Indices into `parameters` that change for the signal sweep, shape (SCP,).
    signal_changing_values : jnp.ndarray
        Values for those signal-changing parameters, shape (SCP, SV).

    parameters : jnp.ndarray
        Base parameter array, shape (1, P). It is expanded internally.
    carrier_matrix : jnp.ndarray
        Base carrier augmented matrix, shape (CN, CN + 1).
    signal_matrix : jnp.ndarray
        Base signal augmented matrix, shape (SN, SN + 1).
    noise_matrix : jnp.ndarray
        Noise source covariance matrix, shape (NN, NN) or broadcastable for vmap.
    noise_selection_vectors : jnp.ndarray
        Detector selection vectors, shape (D, 1, setup_size).
    qhd_parameter_indices : jnp.ndarray
        Indices of quadrature-homodyne-detector phase parameters in `parameters`,
        shape (Q,).
    qhd_placing_indices : jnp.ndarray
        Indices describing where detector phases are applied into
        `noise_selection_vectors`, shape (Q, 3). Each row contains:
        (detector_index, row_index, column_index).
    linked_indices : jnp.ndarray
        Parameter indices used as inputs to linking functions, shape (L,).
    linking_function_indices : jnp.ndarray
        Function selectors for linking functions, shape (L,).
    indices_to_link : jnp.ndarray
        Parameter indices to receive outputs of linking functions, shape (L,).

    carrier_function_input_indices, carrier_function_indices, carrier_output_indices,
    carrier_matrix_indices :
        Indexing and function-selection arrays used by `update` to fill the carrier matrix.

    signal_function_input_indices, signal_function_indices, signal_output_indices,
    signal_matrix_indices :
        Indexing and function-selection arrays used by `update` to fill the signal matrix.

    signal_carrier_indices : jnp.ndarray
        Indices selecting the carrier solution entries used to scale signal connectors.
    signal_carrier_placing_indices : tuple[jnp.ndarray, jnp.ndarray]
        Matrix indices locating the signal connector entries that must be scaled by carrier.

    noise_function_input_indices, noise_function_indices, noise_output_indices,
    noise_system_matrix_indices :
        Indexing and function-selection arrays used by `update` to fill the noise matrix.

    component_groups : dict | None
        Optional structural dispatch metadata produced by `run_build_step`.
        Contains carrier, signal and noise partitions. Omit it to use dynamic
        function selectors, or rebuild it if selectors or matrix destinations change.

    Returns
    -------
    carrier : jnp.ndarray
        Carrier solution, transposed to shape (CN, CV).
    signal : jnp.ndarray
        Signal solution, transposed to shape (SN, SV).
    noise : jnp.ndarray
        Quantum noise amplitude spectral density, shape (D, SV) after squeeze.

    Notes
    -----
    - Linking functions are applied before parameter expansion so they operate on a single row.
    - The signal path is always executed (even if effectively empty) to avoid conditionals
      that would force compilation of branches with empty shapes.
    - Conjugation and block manipulation follow the conventions used for upper and lower
      sidebands in frequency-domain interferometer models.
    """
    # Insert optimized parameter values into the base parameter row.
    parameters = parameters.at[[0], optimized_parameter_indices].set(
        optimized_parameters[optimized_value_indices]
    )

    # Apply parameter linking (derived parameters).
    inputs_to_link = parameters[0, linked_indices]
    outputs_to_link = vmap(lambda i, x: lax.switch(i, LINKING_FUNCTIONS, x))(
        linking_function_indices, inputs_to_link
    )
    parameters = parameters.at[[0], indices_to_link].set(outputs_to_link)

    # Quadrature-homodyne-detector phase factors (unit magnitude complex phase).
    qhd_phase_values = jnp.exp(1j * jnp.radians(parameters[0, qhd_parameter_indices]))

    # --------------------
    # Carrier solve
    # --------------------
    parameters = expand_parameters(parameters, carrier_changing_parameter_indices, carrier_changing_values)
    carrier_matrix = vmap(update, in_axes=(0, None, None, None, None, None, None))(
        parameters,
        carrier_matrix,
        carrier_function_input_indices,
        carrier_output_indices,
        carrier_matrix_indices,
        carrier_function_indices,
        None if component_groups is None else component_groups["carrier"],
    )
    carrier = vmap(solve)(carrier_matrix[:, :, :-1], carrier_matrix[:, :, -1])

    # --------------------
    # Signal solve
    # --------------------
    parameters = expand_parameters(parameters, signal_changing_parameter_indices, signal_changing_values)

    # Detector selections do not depend on the signal frequency; prepare them once.
    # Apply quadrature-homodyne-detector phases into the selection vectors.
    # `lax.scatter_mul` is used (rather than `.at[...].set`) so empty index arrays
    # remain valid without conditionals.
    noise_selection_vectors = lax.scatter_mul(
        noise_selection_vectors,
        qhd_placing_indices.reshape(-1, 3),
        qhd_phase_values,
        lax.ScatterDimensionNumbers(
            update_window_dims=(),
            inserted_window_dims=(0, 1, 2),
            scatter_dims_to_operand_dims=(0, 1, 2),
        ),
        unique_indices=True,
    )

    # Broadcast selection vectors across the carrier sweep dimension.
    noise_selection_vectors = jnp.tile(noise_selection_vectors, (1, carrier.shape[0], 1))

    # Select necessary carrier entries and build upper and lower sideband selections.
    upper_carrier_selections = noise_selection_vectors[:, :, : carrier.shape[1]] * carrier
    upper_carrier_selections = noise_selection_vectors.at[:, :, : carrier.shape[1]].set(upper_carrier_selections)

    lower_carrier_selections = jnp.conjugate(
        upper_carrier_selections[:, :, carrier.shape[1] : carrier.shape[1] * 2] * carrier
    )
    base_carrier_selections = upper_carrier_selections.at[
        :, :, carrier.shape[1] : carrier.shape[1] * 2
    ].set(lower_carrier_selections)

    # Carrier values that scale signal connector entries, shape (CV, M).
    carrier_entries = carrier[:, signal_carrier_indices.flatten()]

    chunk_size = FREQUENCY_CHUNK_SIZE
    count = parameters.shape[0]
    # Guarded noise reuse: the builder adds the static key "noise_row_reuse" only when
    # no noise-function input index (incl. padding) is a real carrier/signal changing
    # index, so every expanded row yields identical noise inputs. The noise matrix is
    # then built once (same components, same base, same scatter) and broadcast across
    # rows; solves and the noise contraction are unchanged. The in-loop-solve scope
    # always uses the per-row fallback.
    reuse_noise = (
        NOISE_ROW_REUSE
        and component_groups is not None
        and "noise_row_reuse" in component_groups
        and not (chunk_size is not None and count > chunk_size and carrier.shape[0] == 1
                 and FREQUENCY_LOOP_SCOPE == "signal_noise")
    )
    shared_noise_matrix = None
    if reuse_noise:
        shared_noise_matrix = update(
            parameters[0],
            noise_matrix,
            noise_function_input_indices,
            noise_output_indices,
            noise_system_matrix_indices,
            noise_function_indices,
            component_groups["noise"],
        )

    def broadcast_noise(assembled_noise, allow_shared=True):
        if shared_noise_matrix is None:
            return assembled_noise
        if allow_shared and NOISE_REUSE_MODE == "shared":
            # Unbatched (NN, NN): _solve_signal_and_noise contracts it with one einsum.
            return shared_noise_matrix
        return jnp.broadcast_to(shared_noise_matrix, (count, *shared_noise_matrix.shape))

    def assemble(parameters, carrier_entries):
        return _assemble_signal_and_noise(
            parameters,
            carrier_entries,
            carrier.shape[1],
            signal_matrix,
            None if reuse_noise else noise_matrix,
            signal_function_input_indices,
            signal_function_indices,
            signal_output_indices,
            signal_matrix_indices,
            signal_carrier_placing_indices,
            noise_function_input_indices,
            noise_function_indices,
            noise_output_indices,
            noise_system_matrix_indices,
            component_groups,
        )

    if chunk_size is None or carrier.shape[0] != 1 or count <= chunk_size:
        # Full frequency vmap (original layout), also used for carrier sweeps.
        assembled_signal, assembled_noise = assemble(parameters, carrier_entries)
        assembled_noise = broadcast_noise(assembled_noise)
        signal, noise = _solve_signal_and_noise(assembled_signal, assembled_noise, base_carrier_selections)
    else:
        # Bounded frequency blocks. Frequency-shared, parameter-dependent inputs are
        # broadcast outside the loop and fed per row so their cotangents are summed by
        # one broadcast-transpose reduction.
        row_carrier_selections = jnp.moveaxis(
            jnp.broadcast_to(
                base_carrier_selections,
                (base_carrier_selections.shape[0], count, base_carrier_selections.shape[2]),
            ),
            1,
            0,
        )

        if FREQUENCY_LOOP_SCOPE == "solve":
            # Assembly stays full-vmap; only solves and noise contraction loop.
            assembled_signal, assembled_noise = assemble(parameters, carrier_entries)
            # Row-sliced by the loop, so always the broadcast form.
            assembled_noise = broadcast_noise(assembled_noise, allow_shared=False)

            def block_solve(blocks):
                block_signal_matrix, block_noise_matrix, block_selections = blocks
                return _solve_signal_and_noise(
                    block_signal_matrix, block_noise_matrix, jnp.moveaxis(block_selections, 0, 1)
                )

            signal, noise = _map_frequency_chunks(
                block_solve,
                (assembled_signal, assembled_noise, row_carrier_selections),
                chunk_size,
            )
        elif FREQUENCY_LOOP_SCOPE == "signal_noise":
            # Assembly, solves and noise contraction all run inside the loop.
            row_carrier_entries = jnp.broadcast_to(carrier_entries, (count, carrier_entries.shape[1]))

            def block_signal_and_noise(blocks):
                block_parameters, block_entries, block_selections = blocks
                block_signal_matrix, block_noise_matrix = assemble(block_parameters, block_entries)
                return _solve_signal_and_noise(
                    block_signal_matrix, block_noise_matrix, jnp.moveaxis(block_selections, 0, 1)
                )

            signal, noise = _map_frequency_chunks(
                block_signal_and_noise,
                (parameters, row_carrier_entries, row_carrier_selections),
                chunk_size,
            )
        elif FREQUENCY_LOOP_SCOPE == "assemble":
            # Assembly runs in the loop; solves and noise contraction stay full-vmap.
            row_carrier_entries = jnp.broadcast_to(carrier_entries, (count, carrier_entries.shape[1]))

            def block_assemble(blocks):
                block_parameters, block_entries = blocks
                block_signal_matrix, block_noise_matrix = assemble(block_parameters, block_entries)
                # Stack coefficients and RHS separately so the solves do not
                # slice a full frequency batch of augmented matrices. Assembly
                # arithmetic and its component checkpoint remain unchanged.
                split_signal = (block_signal_matrix[:, :, :-1], block_signal_matrix[:, :, -1])
                if reuse_noise:
                    return split_signal
                return (*split_signal, block_noise_matrix)

            # Component values checkpoint internally; dense assembly and solves
            # remain outside recomputation. The official JIT stages are unchanged.
            assembled = _map_row_chunks(
                block_assemble,
                (parameters, row_carrier_entries),
                chunk_size,
            )
            assembled_signal, assembled_rhs = assembled[:2]
            assembled_noise = broadcast_noise(assembled[2] if len(assembled) > 2 else None)
            signal, noise = _solve_signal_and_noise(
                assembled_signal, assembled_noise, base_carrier_selections, assembled_rhs
            )
        else:
            raise ValueError(f"Unknown FREQUENCY_LOOP_SCOPE {FREQUENCY_LOOP_SCOPE!r}")

    return carrier.T, signal.T, noise.squeeze()


# Static frequency-axis execution granularity for the signal and noise solves.
# None evaluates all signal frequencies in one vmapped batch. A positive integer
# evaluates bounded blocks of that many frequencies sequentially with `lax.map`;
# a final partial block is padded by repeating the last frequency row and the
# padded results are discarded. Read at trace time; not a traced argument.
# Measured (AMD CPU2, one full run each): k=1 with scope "signal_noise" gave the
# fastest first run (22.08 s vs 24.66 s) but every loop variant failed the strict
# gradient regression (one coordinate, rel 1.9e-7 > 1e-7) whenever the solves ran in
# the loop. None (full vmap) and k=1 with scope "assemble" (solves kept full-vmap,
# 23.56 s) are strictly validated.
FREQUENCY_CHUNK_SIZE: int | None = 1
# Loop scope when chunking: "signal_noise" (assembly + solves), "solve" (solves only)
# or "assemble" (assembly only; solves stay full-vmap).
FREQUENCY_LOOP_SCOPE: str = "assemble"
# Build the noise source matrix once and broadcast it across signal rows when the
# builder proved (host-side, before dummy filling) that no noise input index is a
# real changing index. False always uses the per-row noise assembly.
NOISE_ROW_REUSE: bool = True
# How the reused noise matrix enters the contraction when NOISE_ROW_REUSE applies:
# "broadcast" (variant A; broadcast to (B, NN, NN), unchanged batched einsum;
# candidate f3139c7 passed official + strict with bitwise forward outputs) or
# "shared" (variant B; unbatched einsum "ij,dbj->dbi", may round differently).
NOISE_REUSE_MODE: str = "broadcast"
# Signal-matrix LU reuse: "off" (three jnp.linalg.solve calls), "direct" (one LU of
# A shared by the signal and covariance solves; separate LU of A^H for noise
# weights) or "all" (A's LU also for A^H; candidate 3 bb9a183, 18.65 s but FAILED
# strict gradient at indices 33/161/180, max normalized error 14.7).
NOISE_FACTOR_REUSE: str = "direct"


def _map_row_chunks(function, row_arrays: tuple, chunk_size: int):
    """Apply `function` to row blocks; every output has a leading block-row axis."""
    count = row_arrays[0].shape[0]
    chunk_count = -(-count // chunk_size)
    padded_count = chunk_count * chunk_size

    def to_chunks(array):
        if padded_count != count:
            padding = jnp.broadcast_to(array[-1:], (padded_count - count, *array.shape[1:]))
            array = jnp.concatenate([array, padding], axis=0)
        return array.reshape(chunk_count, chunk_size, *array.shape[1:])

    outputs = lax.map(function, tuple(to_chunks(array) for array in row_arrays))
    return tuple(output.reshape(padded_count, *output.shape[2:])[:count] for output in outputs)


def _map_frequency_chunks(function, row_arrays: tuple, chunk_size: int):
    """Apply `function` to sequential blocks of `chunk_size` rows of every array."""
    count = row_arrays[0].shape[0]
    chunk_count = -(-count // chunk_size)
    padded_count = chunk_count * chunk_size

    def to_chunks(array):
        if padded_count != count:
            padding = jnp.broadcast_to(array[-1:], (padded_count - count, *array.shape[1:]))
            array = jnp.concatenate([array, padding], axis=0)
        return array.reshape(chunk_count, chunk_size, *array.shape[1:])

    chunks = tuple(to_chunks(array) for array in row_arrays)
    signal, noise = lax.map(function, chunks)
    # signal: (C, k, SN) -> (B, SN); noise: (C, D, k) -> (D, B).
    signal = signal.reshape(padded_count, signal.shape[-1])[:count]
    noise = jnp.moveaxis(noise, 0, 1).reshape(noise.shape[1], padded_count)[:, :count]
    return signal, noise


def _assemble_signal_and_noise(
    parameters,
    carrier_entries,
    carrier_size,
    signal_matrix,
    noise_matrix,
    signal_function_input_indices,
    signal_function_indices,
    signal_output_indices,
    signal_matrix_indices,
    signal_carrier_placing_indices,
    noise_function_input_indices,
    noise_function_indices,
    noise_output_indices,
    noise_system_matrix_indices,
    component_groups,
):
    """Assemble the signal and quantum-noise systems for B signal rows.

    `parameters` has shape (B, P). Returns the conjugation-adjusted augmented signal
    matrices (B, SN, SN + 1) and the noise source matrices (B, NN, NN).
    """
    signal_groups = None if component_groups is None else component_groups["signal"]
    fuse_carrier_scaling = signal_groups is not None and "carrier_output_positions" in signal_groups
    scaling_entries = (
        jnp.broadcast_to(carrier_entries, (parameters.shape[0], carrier_entries.shape[1]))
        if fuse_carrier_scaling else None
    )
    signal_matrix = vmap(update, in_axes=(0, None, None, None, None, None, None, 0 if fuse_carrier_scaling else None))(
        parameters,
        signal_matrix,
        signal_function_input_indices,
        signal_output_indices,
        signal_matrix_indices,
        signal_function_indices,
        signal_groups,
        scaling_entries,
    )

    # Scale signal connector entries by the carrier solution at the respective spaces.
    # The minus sign matches the sign convention used by the referenced modeling tools.
    unique_carrier_placing_indices = (
        component_groups is not None
        and "unique_carrier_placing_indices" in component_groups["signal"]
    )
    if not fuse_carrier_scaling:
        signal_entries = (
            -signal_matrix.at[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]].get(
                unique_indices=unique_carrier_placing_indices
            )
            * carrier_entries
        )
        signal_matrix = signal_matrix.at[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]].set(
            signal_entries,
            unique_indices=unique_carrier_placing_indices,
        )

    # Apply conjugation rules to enforce upper and lower sideband symmetry.
    rows = jnp.arange(signal_matrix.shape[1])[:, None]
    columns = jnp.arange(signal_matrix.shape[2])[None, :]
    # The lower-sideband row blocks are adjacent; include the augmented RHS.
    # Their union and the mechanical-to-upper block are disjoint.
    conjugate_entries = (
        (rows >= carrier_size) & (rows < 2 * carrier_size) & (columns >= carrier_size)
    ) | ((rows >= 2 * carrier_size) & (columns < carrier_size))
    signal_matrix = jnp.where(
        conjugate_entries, jnp.conjugate(signal_matrix), signal_matrix
    )

    # Update noise source matrix (may depend on current parameters).
    # None: the caller builds one shared noise matrix (guarded row reuse).
    if noise_matrix is None:
        return signal_matrix, None
    noise_matrix = vmap(update, in_axes=(0, None, None, None, None, None, None))(
        parameters,
        noise_matrix,
        noise_function_input_indices,
        noise_output_indices,
        noise_system_matrix_indices,
        noise_function_indices,
        None if component_groups is None else component_groups["noise"],
    )
    return signal_matrix, noise_matrix


def _solve_signal_and_noise(signal_matrix, noise_matrix, base_carrier_selections, signal_rhs=None):
    """Solve the signal and quantum-noise systems for B assembled signal rows.

    `signal_matrix` (B, SN, SN + 1), `noise_matrix` (B, NN, NN) and detector
    selections (D, 1 or B, SN). Returns the signal solution (B, SN) and the
    unsqueezed noise amplitude spectral density (D, B). With signal_rhs (B, SN),
    signal_matrix contains only the coefficients (B, SN, SN).
    """
    if signal_rhs is None:
        coefficients = signal_matrix[:, :, :-1]
        signal_rhs = signal_matrix[:, :, -1]
    else:
        coefficients = signal_matrix

    carrier_selections = base_carrier_selections
    carrier_selections = jnp.broadcast_to(
        carrier_selections,
        (carrier_selections.shape[0], signal_matrix.shape[0], carrier_selections.shape[2]),
    )

    if NOISE_FACTOR_REUSE not in ("off", "direct", "all"):
        raise ValueError(f"Unknown NOISE_FACTOR_REUSE {NOISE_FACTOR_REUSE!r}")
    if NOISE_FACTOR_REUSE != "off":
        # One LU per signal row, shared by the signal solve, the adjoint noise-weight
        # solve (A^H y = s via trans=2) and the covariance solve. Each solve is a
        # custom_linear_solve whose matvec depends differentiably on A, mirroring
        # jnp.linalg.solve's structure (factorization of stop_gradient(A)).
        system = coefficients.astype(jnp.complex128)
        lu_matrix, lu_pivots, _ = jax.lax.linalg.lu(lax.stop_gradient(system))
        factors = (lu_matrix, lu_pivots)

        def lu_apply(rhs, trans):
            return jax.scipy.linalg.lu_solve(factors, rhs, trans=trans)

        def direct_solve(rhs):
            return lax.custom_linear_solve(
                lambda x: jnp.einsum("bij,bj->bi", system, x),
                rhs.astype(jnp.complex128),
                solve=lambda _, x: lu_apply(x, 0),
                transpose_solve=lambda _, x: lu_apply(x, 1),
            )

        def adjoint_solve(rhs):
            # Linear transpose of x -> A^H x is x -> conj(A) x: conj(A) z = x
            # <=> A conj(z) = conj(x).
            return lax.custom_linear_solve(
                lambda x: jnp.einsum("bji,bj->bi", jnp.conjugate(system), x),
                rhs.astype(jnp.complex128),
                solve=lambda _, x: lu_apply(x, 2),
                transpose_solve=lambda _, x: jnp.conjugate(lu_apply(jnp.conjugate(x), 0)),
            )

        signal = direct_solve(signal_rhs)
        if NOISE_FACTOR_REUSE == "all":
            # Failed strict gradient (candidate 3, bb9a183): A^H via A's LU drifts.
            noise_weights = vmap(adjoint_solve)(carrier_selections)
        else:
            # Keep a separate LU of the explicit A^H, preserving its pivots.
            # The differentiable matvec captures A, already used by direct_solve,
            # rather than retaining another transposed matrix for reverse mode.
            adjoint_system = jnp.transpose(jnp.conjugate(system), (0, 2, 1))
            adjoint_lu, adjoint_pivots, _ = jax.lax.linalg.lu(lax.stop_gradient(adjoint_system))
            adjoint_factors = (adjoint_lu, adjoint_pivots)

            def explicit_adjoint_solve(rhs):
                return lax.custom_linear_solve(
                    lambda x: jnp.einsum("bji,bj->bi", jnp.conjugate(system), x),
                    rhs.astype(jnp.complex128),
                    solve=lambda _, x: jax.scipy.linalg.lu_solve(adjoint_factors, x, trans=0),
                    transpose_solve=lambda _, x: jax.scipy.linalg.lu_solve(adjoint_factors, x, trans=1),
                )

            noise_weights = vmap(explicit_adjoint_solve)(carrier_selections)
    else:
        signal = vmap(solve)(coefficients, signal_rhs)
        # Back-propagate detector weights by solving the transposed conjugated signal system.
        transposed_conjugated_signal_matrix = jnp.transpose(jnp.conjugate(coefficients), (0, 2, 1))
        noise_weights = vmap(vmap(solve), in_axes=(None, 0))(transposed_conjugated_signal_matrix, carrier_selections)

    def matmul_single_batch(matrix_batch: jnp.ndarray, vector_batch: jnp.ndarray) -> jnp.ndarray:
        """
        Multiply a batch of matrices with a batch of vectors.

        Parameters
        ----------
        matrix_batch : jnp.ndarray
            Shape (B, N, N).
        vector_batch : jnp.ndarray
            Shape (B, N).

        Returns
        -------
        product : jnp.ndarray
            Shape (B, N).
        """
        return jnp.einsum("bij,bj->bi", matrix_batch, vector_batch)

    # Project noise sources into the system and propagate through the signal matrix.
    if noise_matrix.ndim == 2:
        # Guarded shared noise matrix (NN, NN): one contraction over all detectors/rows.
        noise_sources = jnp.einsum("ij,dbj->dbi", noise_matrix, noise_weights)
    else:
        noise_sources = vmap(matmul_single_batch, in_axes=(None, 0))(noise_matrix, noise_weights)
    if NOISE_FACTOR_REUSE != "off":
        covariances = vmap(direct_solve)(noise_sources)
    else:
        covariances = vmap(vmap(solve), in_axes=(None, 0))(coefficients, noise_sources)

    # Convert propagated covariances into amplitude spectral density.
    temporary_sum = jnp.sum(jnp.real(covariances * jnp.conjugate(carrier_selections)), axis=2)
    noise = jnp.sqrt(2 * temporary_sum * UNIT_VACUUM * H_PLANCK * F0 * 0.25)

    return signal, noise


def run_build_step(
    setup: Setup,
    changing_pairs: list | None = None,
    changing_values: jnp.ndarray | None = None,
    optimization_pairs: list | None = None,
    timeit: bool = False,
) -> tuple:
    """
    Build a `Setup` into simulation-ready arrays and matrices.

    Parameters
    ----------
    setup : Setup
        The optical setup to build.
    changing_pairs : list | None
        Each element is a (component_name, parameter_name) tuple describing which
        parameters are swept during simulation. If None, no sweep is applied.
    changing_values : jnp.ndarray | None
        Values for the parameters described by `changing_pairs`.
        Expected shape is (num_changing_parameters, num_values).
    optimization_pairs : list | None
        Each element is a (component_name, parameter_name) tuple describing which
        parameters are treated as optimized inputs (external values injected into
        the parameter vector before solving). If None, no optimized parameters exist.
    timeit : bool
        If True, return an additional timing measurement (seconds) for the build.

    Returns
    -------
    If `timeit` is False
        simulation_arrays : dict[str, jnp.ndarray]
            Mapping from `simulate` argument name to the array value.
        metadata : tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray]
            (detector_indices, mirror_indices, beamsplitter_indices, isolator_indices)

    If `timeit` is True
        build_seconds : float
            Time spent building and preparing arrays.
        (simulation_arrays, metadata) : tuple
            The same outputs as the non-timed case, packed into a tuple.

    Notes
    -----
    The returned dictionary keys are derived from the `simulate` function signature.
    """
    start = time()

    instructions, matrices, metadata = build(setup)
    component_groups = {}
    arrays_to_prepare, carrier_arrays, signal_arrays, noise_arrays = pairs_to_arrays(
        *instructions, optimization_pairs, changing_pairs, component_groups=component_groups,
        matrix_shapes={"carrier": matrices[1].shape, "signal": matrices[2].shape, "noise": matrices[3].shape},
    )
    prepared_arrays = prepare_arrays(*arrays_to_prepare, changing_values, parameters=matrices[0])

    arg_count = simulate.__code__.co_argcount
    arg_names = simulate.__code__.co_varnames[:arg_count]

    all_arrays = (*prepared_arrays, *matrices, *carrier_arrays, *signal_arrays, *noise_arrays)
    if len(arg_names) != len(all_arrays):
        raise ValueError(
            "simulate signature does not match the number of prepared arrays and matrices. "
            f"simulate expects {len(arg_names)} arguments, but build produced {len(all_arrays)} arrays."
        )

    simulation_arrays = {arg_names[i]: array for i, array in enumerate(all_arrays)}
    # Predicate S: real (pre-dummy) carrier/signal changing indices are disjoint from
    # every noise-function input index, including padding and grouped indices. Then all
    # expanded rows share bitwise-identical noise inputs. Key presence is static.
    real_changing = {int(i) for i in np.asarray(arrays_to_prepare[2]).ravel()}
    real_changing |= {int(i) for i in np.asarray(arrays_to_prepare[3]).ravel()}
    noise_inputs = {int(i) for i in np.asarray(noise_arrays[0]).ravel()}
    for indices in component_groups.get("noise", {}).get("parameter_indices", {}).values():
        noise_inputs |= {int(i) for i in np.asarray(indices).ravel()}
    if real_changing.isdisjoint(noise_inputs):
        component_groups["noise_row_reuse"] = ()

    # Static differentiable-slot masks (dict keys only; empty-tuple values add no
    # pytree leaves). A slot is differentiable when any row of the group reads an
    # optimized index or a linking output; other slots read constants only.
    differentiable_indices = {
        int(i) for i in np.asarray(simulation_arrays["optimized_parameter_indices"]).ravel()
    }
    differentiable_indices |= {
        int(i) for i in np.asarray(simulation_arrays["indices_to_link"]).ravel()
    }
    for name in ("carrier", "signal", "noise"):
        group = component_groups.get(name)
        if not isinstance(group, dict) or "parameter_indices" not in group:
            continue
        diff_slots = {}
        for function_index, indices in group["parameter_indices"].items():
            indices = np.asarray(indices)
            if indices.ndim != 2:
                continue
            diff_slots[function_index] = {
                slot: ()
                for slot in range(indices.shape[1])
                if any(int(i) in differentiable_indices for i in indices[:, slot])
            }
        group["diff_slots"] = diff_slots

        if "function_rows" not in group or "output_rows" not in group:
            continue
        # Stable partition each mixed function group by dependency. Keep both
        # selector representations consistent with the new concatenated order.
        output_rows = np.asarray(group["output_rows"])
        new_position = np.arange(output_rows.size, dtype=output_rows.dtype)
        row_split = {}
        offset = 0
        for function_index in sorted(group["function_rows"]):
            rows = np.asarray(group["function_rows"][function_index])
            size = rows.shape[0]
            indices = np.asarray(group["parameter_indices"][function_index])
            if indices.ndim == 2 and indices.shape[0] == size and function_index in diff_slots:
                live = np.array(
                    [any(int(i) in differentiable_indices for i in row) for row in indices],
                    dtype=bool,
                )
                count = int(live.sum())
                if 0 < count < size:
                    order = np.concatenate([np.flatnonzero(live), np.flatnonzero(~live)])
                    new_position[offset + order] = offset + np.arange(size)
                    group["parameter_indices"][function_index] = jnp.asarray(indices[order])
                    group["function_rows"][function_index] = jnp.asarray(rows[order])
                    row_split[function_index] = {count: ()}
            offset += size
        if row_split:
            group["output_rows"] = jnp.asarray(new_position[output_rows])
            if "flat_output_indices" in group:
                flat = np.asarray(group["flat_output_indices"])
                group["flat_output_indices"] = jnp.asarray(
                    (new_position[flat // 4] * 4 + flat % 4).astype(flat.dtype)
                )
            group["row_split"] = row_split

    simulation_arrays["component_groups"] = component_groups

    if timeit:
        for array in simulation_arrays.values():
            jax.block_until_ready(array)
        return time() - start, (simulation_arrays, metadata)

    return simulation_arrays, *metadata


def run_simulation_step(
    simulation_arrays: dict,
    jit_simulation: bool = False,
    timeit: bool = False,
) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray] | tuple[float, tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]]:
    """
    Run `simulate` using a pre-built set of arrays.

    Parameters
    ----------
    simulation_arrays : dict[str, jnp.ndarray]
        Dictionary mapping argument names to arrays. This is the first return value
        of `run_build_step`.
    jit_simulation : bool
        If True, compile `simulate` using `jax.jit` and run one warmup call to
        trigger compilation before measuring runtime.
    timeit : bool
        If True, return the simulation runtime (seconds) alongside the results.

    Returns
    -------
    If `timeit` is False
        carrier : jnp.ndarray
        signal : jnp.ndarray
        noise : jnp.ndarray

    If `timeit` is True
        simulation_seconds : float
            Time spent executing the simulation (excluding warmup compilation).
        results : tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]
            (carrier, signal, noise)

    Notes
    -----
    The warmup run uses the same inputs and forces compilation when `jit_simulation`
    is enabled.
    """
    simulation_function = simulate

    if jit_simulation:
        simulation_function = jit(simulate)
        _ = simulation_function(**simulation_arrays)  # warmup compilation

    start = time()
    results = simulation_function(**simulation_arrays)

    if timeit:
        for result in results:
            jax.block_until_ready(result)
        return time() - start, results

    return results


def run(
    setup: Setup,
    changing_pairs: list | None = None,
    changing_values: jnp.ndarray | None = None,
    optimization_pairs: list | None = None,
) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """
    Convenience wrapper: build a setup and immediately run the simulation.

    Parameters
    ----------
    setup : Setup
        The setup to simulate.
    changing_pairs : list | None
        Sweep definition as (component_name, parameter_name) pairs.
    changing_values : jnp.ndarray | None
        Sweep values, shape (num_changing_parameters, num_values).
    optimization_pairs : list | None
        Optimized parameter definition as (component_name, parameter_name) pairs.

    Returns
    -------
    carrier : jnp.ndarray
        Carrier solution, shape (num_ports_carrier, num_carrier_values).
    signal : jnp.ndarray
        Signal solution, shape (num_ports_signal, num_signal_values).
    noise : jnp.ndarray
        Noise amplitude spectral density, shape (num_detectors, num_signal_values) after squeeze.
    detector_indices : jnp.ndarray
    mirror_indices : jnp.ndarray
    beamsplitter_indices : jnp.ndarray
    isolator_indices : jnp.ndarray
        Port indices in the order defined by the setup.
    """
    simulation_arrays, *metadata = run_build_step(setup, changing_pairs, changing_values, optimization_pairs)
    carrier, signal, noise = run_simulation_step(simulation_arrays)
    return carrier, signal, noise, *metadata


def run_setups(setups: list[Setup], frequencies: jnp.ndarray):
    """
    Run a list of setups over a shared frequency sweep.

    Parameters
    ----------
    setups : list[Setup]
        Setups to simulate.
    frequencies : jnp.ndarray
        Frequency values. This is passed as the sweep values for the pair ("f", "frequency").
        Expected shape is (1, num_frequencies) or broadcastable to the builder expectations.

    Returns
    -------
    results : list
        Each element is the return value of `run(setup, [("f", "frequency")], frequencies)`.
    """
    results = []
    for setup in setups:
        results.append(run(setup, [("f", "frequency")], frequencies))
    return results
