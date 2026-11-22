"""Compare the host-first build with the original per-array conversion path.

Run in the fixed evaluator environment with this repository on PYTHONPATH.
Builds only: no solves, benchmark execution, timing claims, or fixture reads.
"""

import importlib

import jax
import numpy as np

from differometor.setups import aligo

B = importlib.import_module("differometor.build")
S = importlib.import_module("differometor.simulate")


def equal_trees(old, new):
    def same_order(a, b):
        if isinstance(a, dict):
            assert isinstance(b, dict) and list(a) == list(b)
            for key in a:
                same_order(a[key], b[key])
        elif isinstance(a, (tuple, list)):
            assert type(a) is type(b) and len(a) == len(b)
            for x, y in zip(a, b):
                same_order(x, y)

    same_order(old, new)
    left, left_tree = jax.tree_util.tree_flatten(old)
    right, right_tree = jax.tree_util.tree_flatten(new)
    # Static HostPlan/SparseStructure equality includes their structural keys.
    assert left_tree == right_tree
    for a, b in zip(left, right):
        if isinstance(a, jax.Array):
            assert isinstance(b, jax.Array), (type(a), type(b))
            assert a.dtype == b.dtype and a.shape == b.shape
            assert a.weak_type == b.weak_type
            # Preserve signed zeros and exact real/complex values, not just tolerances.
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
        else:
            assert type(a) is type(b) and a == b
    return sum(isinstance(a, jax.Array) for a in left)


saved_registry = list(B.LINKING_FUNCTIONS)
saved_flags = S.HOST_BUILD_ARRAYS, S.SPARSE_SOLVES
try:
    for mode in ("space_modulation", "amplitude_modulation", "frequency_modulation"):
        for sparse in (False, True):
            for variant in ("optimized_sweep", "defaults", "grouped_sweep"):
                results = []
                for host_first in (False, True):
                    # The builder registers links globally. Restore the same starting
                    # registry so both builds assign the same function indices.
                    B.LINKING_FUNCTIONS[:] = saved_registry
                    S.HOST_BUILD_ARRAYS, S.SPARSE_SOLVES = host_first, sparse
                    setup, pairs = aligo(mode)
                    if variant == "grouped_sweep":
                        # Two arbitrary physical lengths supplied as one shared input.
                        members = [("itmx_etmx", "length"), ("itmy_etmy", "length")]
                        pairs = [p for p in pairs if p not in members] + [[list(p) for p in members]]
                    if variant == "defaults":
                        result = S.run_build_step(setup)
                    else:
                        result = S.run_build_step(
                            setup, [("f", "frequency")], np.array([13.0, 47.0, 891.0]), pairs
                        )
                    jax.block_until_ready(result)
                    results.append(result)
                count = equal_trees(*results)
                print(mode, sparse, variant, "PASS; array leaves:", count)

    # The batched transfer must not turn port-map ints into scalar JAX arrays.
    metadata = {"ports": {"a.out": 3}, "none": None, "marker": (), "empty": np.empty((0, 3), dtype=np.int64)}
    converted = S._put_built_arrays(metadata)
    assert type(converted["ports"]["a.out"]) is int
    assert converted["none"] is None and converted["marker"] == ()
    assert isinstance(converted["empty"], jax.Array) and converted["empty"].shape == (0, 3)
    assert S._put_built_arrays({"only_metadata": 5}) == {"only_metadata": 5}
    print("Metadata preservation PASS")
finally:
    B.LINKING_FUNCTIONS[:] = saved_registry
    S.HOST_BUILD_ARRAYS, S.SPARSE_SOLVES = saved_flags
