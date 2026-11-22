"""Supervisor-only import/build attribution for an arbitrary supplied setup.

Put this checkout on PYTHONPATH. This is an instrumented diagnostic, not an official benchmark or a timing sample
for promotion. Run once in a fresh process under the existing resource policy.
No simulation execution, output validation, compilation-cache enablement or file writes.
Optional JSON inputs contain the same pairs and sweep values as the intended
caller; omitting them profiles the builder's public defaults.
--trace-forward also profiles tracing/lowering of the public simulator VJP,
without compiling or executing it. Supply the caller's optimized values when
the builder returns no default values. This retains all built metadata leaves.
"""

import argparse
import cProfile
import importlib
import json
from pathlib import Path
import pstats
import sys
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-json", required=True, type=Path)
    parser.add_argument("--optimization-pairs-json", type=Path)
    parser.add_argument("--changing-pairs-json", type=Path)
    parser.add_argument("--changing-values-json", type=Path)
    parser.add_argument("--optimized-values-json", type=Path)
    parser.add_argument("--trace-forward", action="store_true")
    parser.add_argument("--top", type=int, default=60)
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be positive")
    if bool(args.changing_pairs_json) != bool(args.changing_values_json):
        parser.error("Supply both changing-pairs and changing-values JSON files")
    if any(name in sys.modules for name in ("jax", "numpy", "differometor")):
        raise RuntimeError("Use a fresh process with no scientific-library preloads")

    phases = {}

    def profiled(name, function):
        profile = cProfile.Profile()
        start = perf_counter()
        profile.enable()
        try:
            result = function()
        finally:
            profile.disable()
        elapsed = perf_counter() - start
        records = []
        for (filename, line, function_name), values in pstats.Stats(profile).stats.items():
            primitive_calls, total_calls, self_seconds, cumulative_seconds, _ = values
            records.append({"file": filename, "line": line, "function": function_name,
                            "primitive_calls": primitive_calls, "total_calls": total_calls,
                            "self_seconds": self_seconds, "cumulative_seconds": cumulative_seconds})
        phases[name] = {
            "instrumented_wall_seconds": elapsed,
            "top_cumulative": sorted(records, key=lambda x: x["cumulative_seconds"], reverse=True)[:args.top],
            "top_self": sorted(records, key=lambda x: x["self_seconds"], reverse=True)[:args.top],
            "simulator_functions": [r for r in records if "/differometor/" in r["file"]],
        }
        return result

    def imports():
        return tuple(importlib.import_module(name) for name in ("differometor", "jax", "numpy"))

    df, jax, np = profiled("simulator_imports", imports)
    if Path(df.__file__).resolve().parent != Path(__file__).resolve().parents[2] / "differometor":
        raise RuntimeError("Imported a different checkout; put this checkout on PYTHONPATH")

    def initialize():
        jax.config.update("jax_enable_x64", True)
        jax.config.update("jax_enable_compilation_cache", False)
        return jax.devices("cpu")

    profiled("initialize", initialize)

    def read_inputs():
        def read(path):
            return None if path is None else json.loads(path.read_text())
        return (read(args.setup_json), read(args.optimization_pairs_json),
                read(args.changing_pairs_json), read(args.changing_values_json))

    data, optimization_pairs, changing_pairs, changing_values = profiled("load_inputs", read_inputs)
    setup = profiled("setup_from_data", lambda: df.Setup.from_data(data))
    changing_values = profiled("prepare_sweep", lambda: None if changing_values is None
                               else jax.block_until_ready(jax.device_put(np.asarray(changing_values))))

    def build():
        result = df.run_build_step(setup, changing_pairs=changing_pairs,
                                   changing_values=changing_values,
                                   optimization_pairs=optimization_pairs)
        return jax.block_until_ready(result)

    built = profiled("run_build_step", build)
    arrays = built[0]
    leaf_inventory = {}
    for name, value in arrays.items():
        leaves = jax.tree_util.tree_leaves(value)
        leaf_inventory[name] = {
            "leaf_count": len(leaves),
            "array_bytes": sum(int(leaf.size * leaf.dtype.itemsize) for leaf in leaves
                               if hasattr(leaf, "size") and hasattr(leaf, "dtype")),
        }
    if args.trace_forward:
        def prepare_parameters():
            if args.optimized_values_json is not None:
                values = np.asarray(json.loads(args.optimized_values_json.read_text()))
                if values.ndim != 1:
                    raise ValueError("Optimized values must be a one-dimensional array")
                return jax.block_until_ready(jax.device_put(values))
            values = arrays["optimized_parameters"]
            if values is None:
                raise ValueError("Supply the caller's --optimized-values-json for tracing")
            return values

        parameters = profiled("prepare_optimized_values", prepare_parameters)
        arrays = dict(arrays, optimized_parameters=parameters)

        def forward_with_pullback(parameters, arrays):
            return jax.vjp(lambda p: df.simulate(**dict(arrays, optimized_parameters=p)), parameters)

        # lower() traces the original operations and callback signatures but does
        # not execute the callbacks or factor any matrices. No leaves are removed.
        lowered = profiled("forward_trace_lower", lambda: jax.jit(forward_with_pullback).lower(parameters, arrays))
        del lowered
    storage = {}
    structure = arrays.get("sparse_structure")
    if structure is not None:
        for name in ("carrier", "signal", "noise"):
            system = getattr(structure, name)
            storage[name] = {"size": system.size, "augmented": system.augmented,
                             "coefficient_nnz": system.nnz,
                             "all_entries": int(system.all_rows.size),
                             "dense_lookup_bytes": int(getattr(system, "_position", np.empty(0)).nbytes),
                             "compact_lookup_bytes": int(getattr(system, "_position_keys", np.empty(0)).nbytes)}
    print(json.dumps({"scope": "instrumented diagnostic; not official timing or validation",
                      "simulator_path": df.__file__, "jax_version": jax.__version__,
                      "numpy_version": np.__version__, "phases": phases,
                      "sparse_metadata": storage,
                      "input_leaf_inventory": leaf_inventory}, indent=2))


if __name__ == "__main__":
    main()
