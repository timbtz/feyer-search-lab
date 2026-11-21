# Exact peer source requested by Claude

This supplies the immutable source evidence you requested because your restricted tools could not inspect peer revisions. It does not change the session identity, deadline 1795299765.2068522, workload or numerical requirements. Your first candidate 5b216969 was correctly recorded as your own rematerialization hypothesis, not a combination.

The diff below is exactly `differometor/simulate.py` from starting parent aa2b1ab44180af8dd1cd3a9796adb911b1a3986a to peer 7d1ccc59cef3d7436870bb0e6c941dbde4c30770. Diff SHA-256: 4a6f50c0e6369613b0a94e80f317d813757470e4fc3448886c1e9e05a09a0912. Your starting build.py improvements are a separate intended ingredient and are not changed by this diff. Inspect compatibility with your subsequent edits; do not blindly replace files or claim additive speed gains. Keep the separate adjoint treatment and strict comparison. If you author a real combination, record the exact scientific parents, intended transferred mechanism, actual source delta and new evaluation IDs. Otherwise explain why you rejected it. This is reference code, not executable coordinator commands.

```diff
diff --git a/differometor/simulate.py b/differometor/simulate.py
index 9b73287..a5660b7 100644
--- a/differometor/simulate.py
+++ b/differometor/simulate.py
@@ -74,18 +74,95 @@ def _evaluate_component(function_and_inputs):
 def _evaluate_component_group(function_index, function_inputs):
     """Vectorize one component type without batching a dynamic branch selector."""
     return vmap(FUNCTIONS[function_index])(function_inputs)
 
 
+def _save_assembly_indices(primitive, *avals, **params):
+    """Retain only discrete indexing results; recompute complex arithmetic."""
+    # JAX 0.9.0 inserts reduce_precision on saved inexact residuals, which
+    # rejects complex128. These operations preserve discrete dtypes (apart
+    # from conversion, whose destination dtype is checked separately).
+    if primitive.name not in (
+        "gather", "lt", "le", "gt", "ge", "eq", "ne", "add", "sub",
+        "mul", "select_n", "broadcast_in_dim", "reshape", "concatenate",
+        "convert_element_type",
+    ):
+        return False
+
+    def discrete(dtype):
+        return dtype is not None and (
+            np.issubdtype(dtype, np.integer) or np.issubdtype(dtype, np.bool_)
+        )
+
+    return bool(avals) and all(discrete(getattr(aval, "dtype", None)) for aval in avals) and (
+        primitive.name != "convert_element_type" or discrete(params.get("new_dtype"))
+    )
+
+
+@partial(jax.checkpoint, prevent_cse=False, policy=_save_assembly_indices)
+def _component_values(
+    parameters,
+    function_input_indices,
+    output_indices,
+    function_indices,
+    component_groups,
+):
+    """Recompute component values; carrier coupling and dense assembly stay outside."""
+    output_rows = output_indices[0]
+    # Keep the function selector scalar so only the selected component branch
+    # executes. The outer vmap in simulate still batches frequency samples.
+    if component_groups is None:
+        function_inputs = parameters[function_input_indices]
+        output_matrix = lax.map(
+            _evaluate_component,
+            (function_indices, function_inputs),
+        )
+    else:
+        # Select directly from grouped outputs using the builder's permutation.
+        # The final matrix scatter retains its original update order, including
+        # possibly overlapping destinations and parameter-dependent zeros.
+        group_values = []
+        function_rows = component_groups["function_rows"]
+        for function_index in sorted(function_rows):
+            rows = function_rows[function_index]
+            # New builders compose these structural indices on the host.
+            if "parameter_indices" in component_groups:
+                input_indices = component_groups["parameter_indices"][function_index]
+            else:
+                input_indices = function_input_indices[rows]
+            group_inputs = parameters[input_indices]
+            group_values.append(_evaluate_component_group(function_index, group_inputs))
+        if group_values:
+            output_matrix = jnp.concatenate(group_values, axis=0)
+            if "flat_output_indices" not in component_groups:
+                output_rows = component_groups["output_rows"][output_rows]
+        else:
+            output_matrix = jnp.zeros((function_input_indices.shape[0], 4), dtype=jnp.complex128)
+    if component_groups is not None and "flat_output_indices" in component_groups:
+        outputs = lax.gather(
+            output_matrix.reshape(-1),
+            component_groups["flat_output_indices"].reshape(-1, 1),
+            lax.GatherDimensionNumbers(
+                offset_dims=(), collapsed_slice_dims=(0,), start_index_map=(0,),
+            ),
+            slice_sizes=(1,),
+            mode="promise_in_bounds",
+        )
+    else:
+        outputs = output_matrix[output_rows, output_indices[1]]
+    return outputs
+
+
 def update(
     parameters: jnp.ndarray,
     matrix: jnp.ndarray,
     function_input_indices: jnp.ndarray,
     output_indices: tuple[jnp.ndarray, jnp.ndarray],
     matrix_indices: tuple[jnp.ndarray, jnp.ndarray],
     function_indices: jnp.ndarray,
     component_groups: dict | None = None,
+    carrier_entries: jnp.ndarray | None = None,
 ) -> jnp.ndarray:
     """
     Update selected entries of a system matrix by evaluating component functions.
 
     This function takes a parameter vector, selects the subset that serves as
@@ -115,11 +192,17 @@ def update(
         Optional builder-produced structural partition of the function rows.
         `function_rows` has static function-ID keys and original input-row arrays;
         `output_rows` maps original output rows to concatenated group rows.
         `parameter_indices`, when present, supplies prepared input indices per group.
         An optional `unique_matrix_indices` key marks verified distinct destinations.
-        Omit or rebuild metadata when changing selectors, input indices or matrix destinations.
+        `flat_matrix_indices` supplies normalized, in-bounds row-major destinations.
+        `flat_output_indices` supplies composed, in-bounds component output offsets.
+        Omit or rebuild metadata when changing selectors, input/output indices, matrix shape
+        or matrix destinations, including carrier coupling destinations.
+    carrier_entries : jnp.ndarray | None
+        Optional carrier factors, used only with builder-proven
+        `carrier_output_positions` to scale component values before matrix assembly.
 
     Returns
     -------
     updated_matrix : jnp.ndarray
         Matrix with updated entries, same shape as `matrix`.
@@ -128,40 +211,37 @@ def update(
     -----
     `lax.switch` selects functions from the global `FUNCTIONS` list. In JAX, a
     Python list of callables referenced as a global is treated as static during
     tracing, which keeps the function jittable as long as the list is stable.
     """
-    output_rows = output_indices[0]
-    # Keep the function selector scalar so only the selected component branch
-    # executes. The outer vmap in simulate still batches frequency samples.
-    if component_groups is None:
-        function_inputs = parameters[function_input_indices]
-        output_matrix = lax.map(
-            _evaluate_component,
-            (function_indices, function_inputs),
+    outputs = _component_values(
+        parameters, function_input_indices, output_indices, function_indices,
+        component_groups,
+    )
+    # Keep the selected component values available to the carrier-product
+    # transpose without including that coupling in checkpoint recomputation.
+    if carrier_entries is not None:
+        positions = component_groups["carrier_output_positions"]
+        scaled_outputs = -outputs[positions] * carrier_entries
+        outputs = outputs.at[positions].set(scaled_outputs, unique_indices=True)
+    if component_groups is not None and "flat_matrix_indices" in component_groups:
+        # Builder-proven unique, in-bounds offsets avoid tracing the generic
+        # two-coordinate indexing path. Update order and component values stay
+        # identical; callers without the proof retain the original scatter.
+        flattened = lax.scatter(
+            matrix.reshape(-1),
+            component_groups["flat_matrix_indices"].reshape(-1, 1),
+            outputs,
+            lax.ScatterDimensionNumbers(
+                update_window_dims=(),
+                inserted_window_dims=(0,),
+                scatter_dims_to_operand_dims=(0,),
+            ),
+            unique_indices=True,
+            mode="promise_in_bounds",
         )
-    else:
-        # Select directly from grouped outputs using the builder's permutation.
-        # The final matrix scatter retains its original update order, including
-        # possibly overlapping destinations and parameter-dependent zeros.
-        group_values = []
-        function_rows = component_groups["function_rows"]
-        for function_index in sorted(function_rows):
-            rows = function_rows[function_index]
-            # New builders compose these structural indices on the host.
-            if "parameter_indices" in component_groups:
-                input_indices = component_groups["parameter_indices"][function_index]
-            else:
-                input_indices = function_input_indices[rows]
-            group_inputs = parameters[input_indices]
-            group_values.append(_evaluate_component_group(function_index, group_inputs))
-        if group_values:
-            output_matrix = jnp.concatenate(group_values, axis=0)
-            output_rows = component_groups["output_rows"][output_rows]
-        else:
-            output_matrix = jnp.zeros((function_input_indices.shape[0], 4), dtype=jnp.complex128)
-    outputs = output_matrix[output_rows, output_indices[1]]
+        return flattened.reshape(matrix.shape)
     unique_indices = component_groups is not None and "unique_matrix_indices" in component_groups
     return matrix.at[matrix_indices[0], matrix_indices[1]].set(outputs, unique_indices=unique_indices)
 
 
 def expand_parameters(array: jnp.ndarray, indices: jnp.ndarray, values: jnp.ndarray) -> jnp.ndarray:
@@ -424,13 +504,12 @@ def simulate(
         )
 
     def broadcast_noise(assembled_noise, allow_shared=True):
         if shared_noise_matrix is None:
             return assembled_noise
-        if allow_shared and NOISE_REUSE_MODE in ("shared", "rowmap"):
-            # Unbatched (NN, NN): _solve_signal_and_noise contracts it without a
-            # (B, NN, NN) broadcast ("shared": one GEMM; "rowmap": per-row matvecs).
+        if allow_shared and NOISE_REUSE_MODE == "shared":
+            # Unbatched (NN, NN): _solve_signal_and_noise contracts it with one einsum.
             return shared_noise_matrix
         return jnp.broadcast_to(shared_noise_matrix, (count, *shared_noise_matrix.shape))
 
     def assemble(parameters, carrier_entries):
         return _assemble_signal_and_noise(
@@ -511,11 +590,17 @@ def simulate(
                 block_signal_matrix, block_noise_matrix = assemble(block_parameters, block_entries)
                 if reuse_noise:
                     return (block_signal_matrix,)
                 return block_signal_matrix, block_noise_matrix
 
-            assembled = _map_row_chunks(block_assemble, (parameters, row_carrier_entries), chunk_size)
+            # Component values checkpoint internally; dense assembly and solves
+            # remain outside recomputation. The official JIT stages are unchanged.
+            assembled = _map_row_chunks(
+                block_assemble,
+                (parameters, row_carrier_entries),
+                chunk_size,
+            )
             assembled_signal = assembled[0]
             assembled_noise = broadcast_noise(assembled[1] if len(assembled) > 1 else None)
             signal, noise = _solve_signal_and_noise(assembled_signal, assembled_noise, base_carrier_selections)
         else:
             raise ValueError(f"Unknown FREQUENCY_LOOP_SCOPE {FREQUENCY_LOOP_SCOPE!r}")
@@ -542,24 +627,17 @@ FREQUENCY_LOOP_SCOPE: str = "assemble"
 # real changing index. False always uses the per-row noise assembly.
 NOISE_ROW_REUSE: bool = True
 # How the reused noise matrix enters the contraction when NOISE_ROW_REUSE applies:
 # "broadcast" (variant A; broadcast to (B, NN, NN), unchanged batched einsum;
 # candidate f3139c7 passed official + strict with bitwise forward outputs) or
-# "shared" (variant B; unbatched einsum "ij,dbj->dbi", may round differently;
-# e525ee5 strict gradient margin 0.949) or "rowmap" (lax.map of per-row
-# (NN,NN)x(NN,D) products against the single noise matrix; no (B,NN,NN) broadcast,
-# intended to keep the per-row product of "broadcast"; profile-guided candidate 1
-# b879706 FAILED strict: noise normalized 1.2e-5, gradient index 161 normalized 6.85).
+# "shared" (variant B; unbatched einsum "ij,dbj->dbi", may round differently).
 NOISE_REUSE_MODE: str = "broadcast"
 # Signal-matrix LU reuse: "off" (three jnp.linalg.solve calls), "direct" (one LU of
 # A shared by the signal and covariance solves; separate LU of A^H for noise
 # weights) or "all" (A's LU also for A^H; candidate 3 bb9a183, 18.65 s but FAILED
 # strict gradient at indices 33/161/180, max normalized error 14.7).
-# "direct_implicit" is "direct" with the A^H solve as its own custom_linear_solve:
-# the LU of the explicit A^H (identical LAPACK input) but a matvec that reads A
-# itself (x -> conj(A)^T x), so the transposed copy is not kept as an AD residual.
-NOISE_FACTOR_REUSE: str = "direct_implicit"
+NOISE_FACTOR_REUSE: str = "direct"
 
 
 def _map_row_chunks(function, row_arrays: tuple, chunk_size: int):
     """Apply `function` to row blocks; every output has a leading block-row axis."""
     count = row_arrays[0].shape[0]
@@ -616,36 +694,44 @@ def _assemble_signal_and_noise(
     """Assemble the signal and quantum-noise systems for B signal rows.
 
     `parameters` has shape (B, P). Returns the conjugation-adjusted augmented signal
     matrices (B, SN, SN + 1) and the noise source matrices (B, NN, NN).
     """
-    signal_matrix = vmap(update, in_axes=(0, None, None, None, None, None, None))(
+    signal_groups = None if component_groups is None else component_groups["signal"]
+    fuse_carrier_scaling = signal_groups is not None and "carrier_output_positions" in signal_groups
+    scaling_entries = (
+        jnp.broadcast_to(carrier_entries, (parameters.shape[0], carrier_entries.shape[1]))
+        if fuse_carrier_scaling else None
+    )
+    signal_matrix = vmap(update, in_axes=(0, None, None, None, None, None, None, 0 if fuse_carrier_scaling else None))(
         parameters,
         signal_matrix,
         signal_function_input_indices,
         signal_output_indices,
         signal_matrix_indices,
         signal_function_indices,
-        None if component_groups is None else component_groups["signal"],
+        signal_groups,
+        scaling_entries,
     )
 
     # Scale signal connector entries by the carrier solution at the respective spaces.
     # The minus sign matches the sign convention used by the referenced modeling tools.
     unique_carrier_placing_indices = (
         component_groups is not None
         and "unique_carrier_placing_indices" in component_groups["signal"]
     )
-    signal_entries = (
-        -signal_matrix.at[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]].get(
-            unique_indices=unique_carrier_placing_indices
+    if not fuse_carrier_scaling:
+        signal_entries = (
+            -signal_matrix.at[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]].get(
+                unique_indices=unique_carrier_placing_indices
+            )
+            * carrier_entries
+        )
+        signal_matrix = signal_matrix.at[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]].set(
+            signal_entries,
+            unique_indices=unique_carrier_placing_indices,
         )
-        * carrier_entries
-    )
-    signal_matrix = signal_matrix.at[:, signal_carrier_placing_indices[0], signal_carrier_placing_indices[1]].set(
-        signal_entries,
-        unique_indices=unique_carrier_placing_indices,
-    )
 
     # Apply conjugation rules to enforce upper and lower sideband symmetry.
     rows = jnp.arange(signal_matrix.shape[1])[:, None]
     columns = jnp.arange(signal_matrix.shape[2])[None, :]
     # The lower-sideband row blocks are adjacent; include the augmented RHS.
@@ -684,11 +770,11 @@ def _solve_signal_and_noise(signal_matrix, noise_matrix, base_carrier_selections
     carrier_selections = jnp.broadcast_to(
         carrier_selections,
         (carrier_selections.shape[0], signal_matrix.shape[0], carrier_selections.shape[2]),
     )
 
-    if NOISE_FACTOR_REUSE not in ("off", "direct", "direct_implicit", "all"):
+    if NOISE_FACTOR_REUSE not in ("off", "direct", "all"):
         raise ValueError(f"Unknown NOISE_FACTOR_REUSE {NOISE_FACTOR_REUSE!r}")
     if NOISE_FACTOR_REUSE != "off":
         # One LU per signal row, shared by the signal solve, the adjoint noise-weight
         # solve (A^H y = s via trans=2) and the covariance solve. Each solve is a
         # custom_linear_solve whose matvec depends differentiably on A, mirroring
@@ -720,28 +806,10 @@ def _solve_signal_and_noise(signal_matrix, noise_matrix, base_carrier_selections
 
         signal = direct_solve(signal_matrix[:, :, -1])
         if NOISE_FACTOR_REUSE == "all":
             # Failed strict gradient (candidate 3, bb9a183): A^H via A's LU drifts.
             noise_weights = vmap(adjoint_solve)(carrier_selections)
-        elif NOISE_FACTOR_REUSE == "direct_implicit":
-            # Separate LU of the explicit A^H exactly as jnp.linalg.solve factors it
-            # (same input, same pivots), solved with lu_solve(trans=0) as in
-            # jnp.linalg.solve. The differentiable matvec reads A (already a residual
-            # of the direct solves) instead of capturing the transposed copy.
-            adjoint_system = jnp.transpose(jnp.conjugate(system), (0, 2, 1))
-            adjoint_lu, adjoint_pivots, _ = jax.lax.linalg.lu(lax.stop_gradient(adjoint_system))
-            adjoint_factors = (adjoint_lu, adjoint_pivots)
-
-            def explicit_adjoint_solve(rhs):
-                return lax.custom_linear_solve(
-                    lambda x: jnp.einsum("bji,bj->bi", jnp.conjugate(system), x),
-                    rhs.astype(jnp.complex128),
-                    solve=lambda _, x: jax.scipy.linalg.lu_solve(adjoint_factors, x, trans=0),
-                    transpose_solve=lambda _, x: jax.scipy.linalg.lu_solve(adjoint_factors, x, trans=1),
-                )
-
-            noise_weights = vmap(explicit_adjoint_solve)(carrier_selections)
         else:
             # "direct": keep the original separate LU of A^H for the noise weights.
             transposed_conjugated_signal_matrix = jnp.transpose(jnp.conjugate(signal_matrix[:, :, :-1]), (0, 2, 1))
             noise_weights = vmap(vmap(solve), in_axes=(None, 0))(
                 transposed_conjugated_signal_matrix, carrier_selections
@@ -769,20 +837,11 @@ def _solve_signal_and_noise(signal_matrix, noise_matrix, base_carrier_selections
             Shape (B, N).
         """
         return jnp.einsum("bij,bj->bi", matrix_batch, vector_batch)
 
     # Project noise sources into the system and propagate through the signal matrix.
-    if noise_matrix.ndim == 2 and NOISE_REUSE_MODE == "rowmap":
-        # Guarded shared noise matrix (NN, NN), contracted row by row in a sequential
-        # loop: each row is the same (NN, NN) x (NN, D) product the broadcast batched
-        # einsum performs per batch element, but the (B, NN, NN) broadcast operand and
-        # its AD residual are never materialized.
-        def row_sources(row_weights):
-            return jnp.einsum("ij,dj->di", noise_matrix, row_weights)
-
-        noise_sources = jnp.moveaxis(lax.map(row_sources, jnp.moveaxis(noise_weights, 1, 0)), 0, 1)
-    elif noise_matrix.ndim == 2:
+    if noise_matrix.ndim == 2:
         # Guarded shared noise matrix (NN, NN): one contraction over all detectors/rows.
         noise_sources = jnp.einsum("ij,dbj->dbi", noise_matrix, noise_weights)
     else:
         noise_sources = vmap(matmul_single_batch, in_axes=(None, 0))(noise_matrix, noise_weights)
     if NOISE_FACTOR_REUSE != "off":
```
