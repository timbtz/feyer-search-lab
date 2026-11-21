"""Sparse direct solves for the carrier, signal and quantum-noise systems.

The interferometer systems are large but extremely sparse (the public 3x3 UIFO
signal system has 751 unknowns and about 2.5 thousand structural nonzeros).
Their sparsity pattern is fixed by the optical setup, so it is derived once on
the host while building the setup and carried through JAX transformations as
static pytree metadata. Only the numerical values of the structural nonzeros are
traced.

`sparse_solve` factors each system with SciPy's SuperLU through
`jax.pure_callback` and defines its reverse-mode derivative with a custom VJP:

    x = op(A)^-1 b,  op(A) in {A, A^T}
    b_bar = op(A)^-T x_bar
    A_bar[i, j] = -b_bar[i] x[j]   (op = identity)
    A_bar[i, j] = -b_bar[j] x[i]   (op = transpose)

JAX uses the plain (non-conjugated) transpose of complex-linear maps for its
cotangents; `A^H` systems are expressed as transposed solves of `conj(A)` so JAX
differentiates the conjugation itself.
"""

from __future__ import annotations

import hashlib
from functools import partial

import jax
import jax.numpy as jnp
import numpy as np

_splu = None
_csc_matrix = None


def _scipy():
    """Import SciPy's sparse solver lazily (only the sparse path needs it)."""
    global _splu, _csc_matrix
    if _splu is None:
        from scipy.sparse import csc_matrix
        from scipy.sparse.linalg import splu

        _splu, _csc_matrix = splu, csc_matrix
    return _splu, _csc_matrix


class SparsePattern:
    """Static CSC structure of a square sparse matrix.

    `rows` and `cols` list the structural nonzeros in CSC order (sorted by column,
    then row). Value vectors passed to `sparse_solve` use this order.
    """

    def __init__(self, rows, cols, size):
        rows = np.asarray(rows, dtype=np.int64)
        cols = np.asarray(cols, dtype=np.int64)
        order = np.lexsort((rows, cols))
        if np.any(order != np.arange(order.size)):
            raise ValueError("SparsePattern entries must already be in CSC order")
        self.rows = rows
        self.cols = cols
        self.size = int(size)
        self.indices = rows.astype(np.int32)
        self.indptr = np.searchsorted(cols, np.arange(self.size + 1)).astype(np.int32)
        digest = hashlib.sha256()
        digest.update(np.int64(self.size).tobytes())
        digest.update(rows.tobytes())
        digest.update(cols.tobytes())
        self._key = digest.hexdigest()

    @property
    def nnz(self):
        return int(self.rows.size)

    def __hash__(self):
        return hash(self._key)

    def __eq__(self, other):
        return isinstance(other, SparsePattern) and other._key == self._key

    def __repr__(self):
        return f"SparsePattern(size={self.size}, nnz={self.nnz})"


def _host_solve(pattern: SparsePattern, transpose: bool, values, rhs):
    """Solve op(A_l) X_l = B_l for every leading batch index l on the host."""
    splu, csc_matrix = _scipy()
    values = np.asarray(values)
    rhs = np.asarray(rhs)
    lead = np.broadcast_shapes(values.shape[:-1], rhs.shape[:-2])
    nnz = values.shape[-1]
    count, size = rhs.shape[-2:]
    values = np.broadcast_to(values, lead + (nnz,)).reshape(-1, nnz)
    rhs = np.broadcast_to(rhs, lead + (count, size)).reshape(-1, count, size)
    result = np.empty(rhs.shape, dtype=np.complex128)
    trans = "T" if transpose else "N"
    shape = (size, size)
    for item in range(values.shape[0]):
        matrix = csc_matrix((values[item], pattern.indices, pattern.indptr), shape=shape)
        factor = splu(matrix, permc_spec="COLAMD")
        operator = matrix.T if transpose else matrix
        right = np.ascontiguousarray(rhs[item].T)
        solution = factor.solve(right, trans=trans)
        # Iterative refinement. The systems are badly scaled (cond ~ 1e30), so the
        # sparse pivot order alone can lose accuracy in derived quantities such as
        # quantum noise; refinement restores (and on some setups exceeds) the
        # accuracy of the dense reference. At least one step, at most REFINEMENT_STEPS.
        for _ in range(REFINEMENT_STEPS):
            correction = factor.solve(right - operator @ solution, trans=trans)
            solution = solution + correction
            if np.max(np.abs(correction)) <= REFINEMENT_TOLERANCE * np.max(np.abs(solution)):
                break
        result[item] = solution.T
    return result.reshape(lead + (count, size))


# Maximum refinement steps per solve and the relative correction size that ends it.
REFINEMENT_STEPS = 3
REFINEMENT_TOLERANCE = 1e-14


def _call(pattern, transpose, values, rhs):
    shape = jnp.broadcast_shapes(values.shape[:-1], rhs.shape[:-2]) + rhs.shape[-2:]
    return jax.pure_callback(
        partial(_host_solve, pattern, transpose),
        jax.ShapeDtypeStruct(shape, jnp.complex128),
        values.astype(jnp.complex128),
        rhs.astype(jnp.complex128),
        vmap_method="broadcast_all",
    )


@partial(jax.custom_vjp, nondiff_argnums=(0, 1))
def sparse_solve(pattern: SparsePattern, transpose: bool, values, rhs):
    """Solve op(A) x = b for sparse A with several right-hand sides.

    Parameters
    ----------
    pattern : SparsePattern
        Static structure of A (CSC order).
    transpose : bool
        Solve A^T x = b instead of A x = b.
    values : jnp.ndarray
        Structural nonzero values of A, shape (L, nnz).
    rhs : jnp.ndarray
        Right-hand sides, shape (L, K, N); K systems share each matrix.

    Returns
    -------
    jnp.ndarray
        Solutions with shape (L, K, N), complex128.
    """
    return _call(pattern, transpose, values, rhs)


def _sparse_solve_fwd(pattern, transpose, values, rhs):
    solution = _call(pattern, transpose, values, rhs)
    return solution, (values, solution)


def _sparse_solve_bwd(pattern, transpose, residuals, solution_bar):
    values, solution = residuals
    rhs_bar = _call(pattern, not transpose, values, solution_bar)
    if transpose:
        left, right = pattern.cols, pattern.rows
    else:
        left, right = pattern.rows, pattern.cols
    values_bar = -jnp.einsum("lkn,lkn->ln", rhs_bar[..., left], solution[..., right])
    return values_bar.astype(values.dtype), rhs_bar


sparse_solve.defvjp(_sparse_solve_fwd, _sparse_solve_bwd)


class SparseSystem:
    """Static map from an augmented dense system (N, N + 1) to sparse values.

    The augmented pattern lists coefficient entries first (CSC order of A), then
    right-hand-side entries. `write_positions` maps every update destination of
    the builder's scatter to its pattern position, preserving duplicates and
    their order.
    """

    def __init__(self, base_matrix, write_rows, write_cols, extra_rows=(), extra_cols=()):
        base_matrix = np.asarray(base_matrix)
        size = base_matrix.shape[0]
        augmented = base_matrix.shape[1] == size + 1
        if base_matrix.shape[1] not in (size, size + 1):
            raise ValueError("Expected a square or augmented system matrix")
        write_rows = np.asarray(write_rows, dtype=np.int64).ravel()
        write_cols = np.asarray(write_cols, dtype=np.int64).ravel()
        mask = base_matrix != 0
        mask[write_rows, write_cols] = True
        extra_rows = np.asarray(extra_rows, dtype=np.int64).ravel()
        extra_cols = np.asarray(extra_cols, dtype=np.int64).ravel()
        if extra_rows.size:
            mask[extra_rows, extra_cols] = True
        coefficient_mask = mask[:, :size]
        # Coefficient entries in CSC order, then right-hand-side entries by row.
        cols, rows = np.nonzero(coefficient_mask.T)
        if augmented:
            rhs_rows = np.nonzero(mask[:, size])[0]
        else:
            rhs_rows = np.zeros((0,), dtype=np.int64)
        self.size = int(size)
        self.augmented = bool(augmented)
        self.pattern = SparsePattern(rows, cols, size)
        self.rhs_rows = rhs_rows.astype(np.int64)
        all_rows = np.concatenate([rows, rhs_rows])
        all_cols = np.concatenate([cols, np.full(rhs_rows.shape, size, dtype=np.int64)])
        self.all_rows = all_rows
        self.all_cols = all_cols
        position = np.full(base_matrix.shape, -1, dtype=np.int64)
        position[all_rows, all_cols] = np.arange(all_rows.size)
        self._position = position
        self.write_positions = position[write_rows, write_cols]
        self.unique_writes = bool(np.unique(self.write_positions).size == self.write_positions.size)
        digest = hashlib.sha256()
        for array in (np.int64(size), np.int64(augmented), all_rows, all_cols, self.write_positions):
            digest.update(np.asarray(array).tobytes())
        self._key = digest.hexdigest()

    def positions(self, rows, cols):
        positions = self._position[np.asarray(rows, dtype=np.int64).ravel(), np.asarray(cols, dtype=np.int64).ravel()]
        if np.any(positions < 0):
            raise ValueError("Requested positions outside the sparse pattern")
        return positions

    def mask(self, predicate):
        """Static boolean mask over pattern entries from predicate(rows, cols)."""
        return np.asarray(predicate(self.all_rows, self.all_cols), dtype=bool)

    @property
    def nnz(self):
        return self.pattern.nnz

    def base_values(self, matrix):
        """Gather the base matrix values at all pattern entries (traced)."""
        return matrix[self.all_rows, self.all_cols]

    def split(self, values):
        """Split augmented values (..., nnz_total) into A values and dense RHS."""
        coefficients = values[..., : self.nnz]
        if not self.augmented:
            return coefficients, None
        rhs = jnp.zeros(values.shape[:-1] + (self.size,), dtype=values.dtype)
        rhs = rhs.at[..., self.rhs_rows].set(values[..., self.nnz :], unique_indices=True)
        return coefficients, rhs

    def __hash__(self):
        return hash(self._key)

    def __eq__(self, other):
        return isinstance(other, SparseSystem) and other._key == self._key

    def __repr__(self):
        return f"SparseSystem(size={self.size}, nnz={self.nnz}, rhs={self.rhs_rows.size})"


class SparseStructure:
    """Static sparse metadata for one built setup (no array leaves)."""

    def __init__(self, carrier, signal, noise, carrier_size, signal_placing_positions, unique_placing,
                 group_indices=None):
        # group_indices: {system: {function_index: (rows, slots) int array}} or None.
        self.group_indices = group_indices
        self.carrier = carrier
        self.signal = signal
        self.noise = noise
        self.carrier_size = int(carrier_size)
        self.signal_placing_positions = np.asarray(signal_placing_positions, dtype=np.int64)
        self.unique_placing = bool(unique_placing)
        cs = self.carrier_size
        # Lower-sideband rows [cs, 2cs) for columns >= cs (including the RHS),
        # and mechanical rows >= 2cs for upper-sideband columns < cs.
        self.signal_conjugate = signal.mask(
            lambda r, c: ((r >= cs) & (r < 2 * cs) & (c >= cs)) | ((r >= 2 * cs) & (c < cs))
        )
        digest = hashlib.sha256()
        for part in (carrier._key, signal._key, noise._key):
            digest.update(part.encode())
        digest.update(np.int64(cs).tobytes())
        digest.update(self.signal_placing_positions.tobytes())
        for system in sorted(group_indices or {}):
            digest.update(system.encode())
            for function_index in sorted(group_indices[system]):
                indices = group_indices[system][function_index]
                digest.update(np.int64(function_index).tobytes())
                digest.update(np.int64(indices.ndim).tobytes())
                digest.update(np.asarray(indices.shape, dtype=np.int64).tobytes())
                digest.update(indices.tobytes())
        self._key = digest.hexdigest()

    def __hash__(self):
        return hash(self._key)

    def __eq__(self, other):
        return isinstance(other, SparseStructure) and other._key == self._key

    def __repr__(self):
        return f"SparseStructure(carrier={self.carrier}, signal={self.signal}, noise={self.noise})"


for _static in (SparsePattern, SparseSystem, SparseStructure):
    jax.tree_util.register_static(_static)
