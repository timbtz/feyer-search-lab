#!/usr/bin/env python3
"""JAX transformation compatibility check for Differometor candidates.

The benchmark only exercises jit + reverse-mode vjp. Downstream users of the
simulator (upstream examples, optimizers, other tasks) also rely on
value_and_grad loops, vmap over parameter sets, forward mode, second order,
eager execution and several setups in one process. A candidate that replaces
JAX internals (e.g. host callbacks with custom rules) can pass the benchmark
and still break these.

run:     python jaxcompat.py run --tree /path/to/repo --out result.json [--setup voyager]
compare: python jaxcompat.py compare reference.json candidate.json

Standalone (no lab imports) so it can run with the evaluator's fixed Python.
"""
import os
import sys
import json
import time
import argparse
import traceback
import math
import hashlib
import platform
from importlib import metadata
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_ENABLE_X64", "true")
PROPERTIES = ["reflectivity", "tuning", "db", "angle", "power", "mass", "length"]


REQUIRED_TESTS = (
    "value_and_grad_jit", "descent_3_steps", "vmap_value_and_grad", "jvp",
    "jacfwd_2", "hvp_fwd_over_rev", "hvp_rev_over_rev", "eager_value_and_grad",
    "public_run", "checkpoint_grad", "second_setup_same_process",
)
SCHEMA_VERSION = 2


def numeric_blocks(value, path="value"):
    """Keep dictionary keys and rectangular array shapes; reject empty/nonfinite data."""
    def array(node):
        if isinstance(node, (list, tuple)):
            if not node:
                raise ValueError(f"{path}: empty numeric container")
            children = [array(item) for item in node]
            if any(item is None for item in children):
                return None
            if any(item[0] != children[0][0] for item in children):
                return None
            return (len(node),) + children[0][0], [x for _, xs in children for x in xs]
        if isinstance(node, (int, float, complex)) and not isinstance(node, bool):
            number = complex(node)
            if not (math.isfinite(number.real) and math.isfinite(number.imag)):
                raise ValueError(f"{path}: nonfinite numeric value")
            return (), [number]
        return None

    if isinstance(value, dict):
        if not value or any(not isinstance(k, str) for k in value):
            raise ValueError(f"{path}: empty dictionary or non-string key")
        result = {}
        for key in sorted(value):
            result.update(numeric_blocks(value[key], f"{path}[{key!r}]"))
        return result
    block = array(value)
    if block is not None:
        return {path: block}
    if isinstance(value, (list, tuple)):
        result = {}
        for index, item in enumerate(value):
            result.update(numeric_blocks(item, f"{path}[{index}]"))
        return result
    raise ValueError(f"{path}: expected numeric data")


def compare_values(reference, candidate, tolerance=1e-6):
    """Compare complete JSON numeric trees with a relative infinity norm per block."""
    issues, worst = [], 0.0
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    try:
        a, b = numeric_blocks(reference), numeric_blocks(candidate)
        if a.keys() != b.keys():
            issues.append("numeric tree keys or leaf counts differ")
        else:
            for path, (shape, values) in a.items():
                other_shape, other = b[path]
                if shape != other_shape:
                    issues.append(f"{path}: shape differs ({shape} != {other_shape})")
                    continue
                denominator = max(max(abs(x) for x in values), 1e-300)
                error = max(abs(x - y) for x, y in zip(values, other)) / denominator
                if not math.isfinite(error):
                    issues.append(f"{path}: nonfinite difference")
                else:
                    worst = max(worst, error)
                    if error > tolerance:
                        issues.append(f"{path}: relative difference {error:.9g} exceeds {tolerance:.9g}")
    except (ValueError, TypeError, OverflowError) as error:
        issues.append(str(error))
    return dict(status="failed" if issues else "passed", passed=not issues,
                max_relative_difference=worst if not issues or worst else None, issues=issues)


def compare_reports(reference, candidate, tolerance=1e-6):
    """Numerical coverage gate only; callers must separately verify provenance and domain."""
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    issues, checks = [], []
    if not reference.get("setup") or reference.get("setup") != candidate.get("setup"):
        issues.append("setup missing or different")
    a, b = reference.get("tests", {}), candidate.get("tests", {})
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise ValueError("tests must be a dictionary")
    for label, tests in (("reference", a), ("candidate", b)):
        if set(tests) != set(REQUIRED_TESTS):
            issues.append(f"{label}: test inventory differs from required eleven tests")
    for key in REQUIRED_TESTS:
        ra, rb = a.get(key, {}), b.get(key, {})
        row = dict(test=key, status="unavailable", max_relative_difference=None, issues=[])
        for label, record in (("reference", ra), ("candidate", rb)):
            if not isinstance(record, dict) or record.get("status") != "ok" or "value" not in record:
                row["issues"].append(f"{label}: missing, failed, or missing value")
        if not row["issues"]:
            row.update(compare_values(ra["value"], rb["value"], tolerance))
        checks.append(row)
    passed = not issues and all(row["status"] == "passed" for row in checks)
    return dict(status="passed" if passed else "failed", passed=passed,
                setup=candidate.get("setup"), required_tests=list(REQUIRED_TESTS),
                tolerance=tolerance, checks=checks, issues=issues)


def source_digest(tree):
    root = Path(tree).resolve()
    files = sorted((root / "differometor").rglob("*.py"))
    files += sorted((root / "examples" / "data").glob("*.json"))
    if not files:
        raise ValueError("no simulator source files found")
    digest = hashlib.sha256()
    for file in files:
        digest.update(str(file.relative_to(root)).encode() + b"\0" + file.read_bytes() + b"\0")
    return digest.hexdigest()


def merge_receipts(previous, current):
    """A partial rerun must never inherit results from another code/environment/setup."""
    if previous.get("schema_version") != SCHEMA_VERSION or not current.get("identity"):
        raise ValueError("cannot merge legacy or unidentified receipt; use a fresh output file")
    if previous.get("identity") != current["identity"]:
        raise ValueError("partial rerun identity differs; use a fresh output file")
    merged = dict(current)
    merged["tests"] = {**previous.get("tests", {}), **current["tests"]}
    merged["domain_observations"] = {**previous.get("domain_observations", {}),
                                     **current.get("domain_observations", {})}
    return merged


def run(args):
    selected = set(args.only.split(",")) if args.only else set(REQUIRED_TESTS)
    if not selected or not selected <= set(REQUIRED_TESTS):
        raise ValueError("--only contains an unknown or empty test name")
    sys.path.insert(0, os.path.abspath(args.tree))
    import numpy as np
    import jax
    import jax.numpy as jnp
    jax.config.update("jax_enable_x64", True)
    jax.config.update("jax_enable_compilation_cache", False)
    import differometor as df
    from differometor import setups as dsetups
    from differometor.setups import Setup, constrain_inter_grid_cell_spaces
    if os.path.commonpath([os.path.realpath(df.__file__), os.path.realpath(args.tree)]) != os.path.realpath(args.tree):
        raise RuntimeError(f"simulator imported from unexpected location: {df.__file__}")
    data_dir = os.path.join(args.tree, "examples", "data")

    def values_for(data, pairs):
        out = []
        for pair in pairs:
            name, prop = (pair if isinstance(pair[0], list) else [pair])[0]
            out.append(float(np.real(data["nodes" if name in data["nodes"] else "edges"][name]["properties"][prop])))
        return out

    def make(name):
        if name == "voyager":
            setup, component_pairs = dsetups.voyager()
            pairs = [list(p) for p in component_pairs if p[1] in PROPERTIES]
            freqs = np.logspace(np.log10(20), np.log10(5000), 40)
            return setup, pairs, values_for(setup.to_data(), pairs), freqs
        if name == "dev":
            fixture = json.load(open(os.path.join(data_dir, "uifo_800_3000.json")))
            reference = json.load(open(os.path.join(data_dir, "uifo_800_3000_test_data.json")))
            setup = Setup.from_data(fixture)
            pairs = constrain_inter_grid_cell_spaces(setup.parameters, PROPERTIES)
            return setup, pairs, values_for(fixture, pairs), np.asarray(reference["frequencies"])
        if name == "uifo_20_5000":
            fixture = json.load(open(os.path.join(data_dir, "uifo_20_5000.json")))
            setup = Setup.from_data(fixture)
            pairs = constrain_inter_grid_cell_spaces(setup.parameters, PROPERTIES)
            return setup, pairs, values_for(fixture, pairs), np.logspace(np.log10(20), np.log10(5000), 40)
        raise ValueError(name)

    def problem(name):
        setup, pairs, init, freqs = make(name)
        arrays, ports, *_ = df.run_build_step(setup, [("f", "frequency")], jnp.asarray(freqs), pairs)
        params = jnp.asarray(init, dtype=jnp.float64)
        arrays["optimized_parameters"] = params
        ports = jnp.asarray(ports)

        def loss(p):
            carrier, signal, noise = df.simulate(**dict(arrays, optimized_parameters=p))
            signals = df.signal_detector(carrier, signal)[ports]
            detected = signals.squeeze() if ports.shape[0] == 1 else signals[0] - signals[1]
            return jnp.mean(jnp.log10((noise / jnp.abs(detected)).squeeze()))
        return setup, pairs, freqs, arrays, params, loss

    identity = dict(source_sha256=source_digest(args.tree), setup=args.setup,
                    harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    python=platform.python_version(), platform=platform.platform(),
                    machine=platform.machine(), jax=jax.__version__, numpy=np.__version__,
                    x64=bool(jax.config.jax_enable_x64), devices=[str(x) for x in jax.devices()],
                    cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                    thread_environment={key: os.environ.get(key) for key in
                                        ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                         "XLA_FLAGS", "JAX_PLATFORMS", "JAX_ENABLE_X64")})
    for dependency in ("jaxlib", "scipy"):
        try:
            identity[dependency] = metadata.version(dependency)
        except metadata.PackageNotFoundError:
            identity[dependency] = None
    results = dict(schema_version=SCHEMA_VERSION, identity=identity,
                   tree=os.path.abspath(args.tree), setup=args.setup, tests={}, domain_observations={})
    setup, pairs, freqs, arrays, params, loss = problem(args.setup)
    n = params.shape[0]
    rng = np.random.default_rng(0)
    direction = jnp.asarray(rng.standard_normal(n))
    direction = direction / jnp.linalg.norm(direction)
    # Historical unconstrained trajectory: scaling does NOT ensure physical bounds.
    # Keep its values for reproducibility; report domain separately from API agreement.
    scale = jnp.maximum(jnp.abs(params), 1e-3)

    def record(key, fn):
        if key not in selected:
            return
        t = time.perf_counter()
        try:
            value = fn()
            value = jax.tree_util.tree_map(lambda x: np.asarray(x).tolist(), jax.device_get(value))
            numeric_blocks(value)  # Reject NaN/Inf/empty outputs before status=ok.
            results["tests"][key] = dict(status="ok", seconds=time.perf_counter() - t, value=value)
            print(f"[{key}] ok {time.perf_counter() - t:.2f}s", flush=True)
        except Exception as error:
            results["tests"][key] = dict(status="error", seconds=time.perf_counter() - t,
                                         error=f"{type(error).__name__}: {str(error).splitlines()[0][:300] if str(error) else ''}",
                                         trace=traceback.format_exc()[-1500:])
            print(f"[{key}] ERROR {type(error).__name__}: {str(error)[:200]}", flush=True)

    def domain_violations(p):
        # Physical restrictions; optimizer sampling ranges (e.g. tuning[0,90])
        # are not universal physical bounds and exclude the built-in Voyager itself.
        physical_bounds = {"reflectivity": (0., 1.), "loss": (0., 1.),
                           "transmissivity": (0., 1.), "power": (0., None),
                           "mass": (0., None), "length": (0., None)}
        values = np.asarray(jax.device_get(p))
        failures = []
        for index, (pair, value) in enumerate(zip(pairs, values)):
            group = pair if isinstance(pair[0], list) else [pair]
            for name, prop in group:
                if prop in physical_bounds:
                    low, high = physical_bounds[prop]
                    if not np.isfinite(value) or value < low or (high is not None and value > high) or (prop == "mass" and value == 0):
                        failures.append(dict(index=index, component=name, property=prop,
                                             value=float(value), lower=float(low), upper=high))
        return failures

    results["domain_observations"]["initial"] = domain_violations(params)
    # 1. Optimizer-style reverse mode, the upstream examples' pattern.
    record("value_and_grad_jit", lambda: jax.jit(jax.value_and_grad(loss))(params))
    # 2. Several optimizer steps with changing parameters (detects stale caches).
    def descent():
        step = jax.jit(jax.value_and_grad(loss))
        p, history = params, []
        violations = []
        for iteration in range(3):
            violations.append(dict(iteration=iteration, violations=domain_violations(p)))
            results["domain_observations"]["descent_3_steps"] = violations
            value, g = step(p)
            history.append(float(value))
            p = p - 1e-3 * scale * g / (jnp.linalg.norm(g) + 1e-300)
        violations.append(dict(iteration=3, violations=domain_violations(p)))
        return dict(losses=history, final=p)
    record("descent_3_steps", descent)
    # 3. Batched parameter sets (population optimizers, run_with_parameter_sets).
    batch = jnp.stack([params, params + 1e-3 * scale * direction, params - 1e-3 * scale * direction])
    results["domain_observations"]["vmap_value_and_grad"] = [domain_violations(p) for p in batch]
    record("vmap_value_and_grad", lambda: jax.jit(jax.vmap(jax.value_and_grad(loss)))(batch))
    # 4. Forward mode.
    record("jvp", lambda: jax.jit(lambda p, v: jax.jvp(loss, (p,), (v,)))(params, direction))
    record("jacfwd_2", lambda: jax.jit(jax.jacfwd(lambda q: loss(params.at[:2].set(q))))(params[:2]))
    # 5. Second order (Newton / curvature methods).
    record("hvp_fwd_over_rev", lambda: jax.jit(lambda p, v: jax.jvp(jax.grad(loss), (p,), (v,))[1])(params, direction))
    record("hvp_rev_over_rev", lambda: jax.jit(jax.grad(lambda p: jnp.vdot(jax.grad(loss)(p), direction)))(params))
    # 6. Eager execution and the public run API.
    record("eager_value_and_grad", lambda: jax.value_and_grad(loss)(params))
    def public_run():
        # Upstream examples call run() without optimization pairs (values then come from the setup).
        carrier, signal, noise, *_ = df.run(setup, [("f", "frequency")], jnp.asarray(freqs))
        return dict(noise=noise, carrier_norm=jnp.linalg.norm(carrier), signal_norm=jnp.linalg.norm(signal))
    record("public_run", public_run)
    # 7. Rematerialization wrapper.
    record("checkpoint_grad", lambda: jax.jit(jax.grad(jax.checkpoint(loss)))(params))
    # 8. Another setup built in the same process, then the first one again.
    other_name = "uifo_20_5000" if args.setup != "uifo_20_5000" else "voyager"
    def interleaved():
        _, _, _, _, other_params, other_loss = problem(other_name)
        first = jax.jit(jax.value_and_grad(other_loss))(other_params)
        again = jax.jit(jax.value_and_grad(loss))(params)
        return dict(other=first, first_again=again)
    record("second_setup_same_process", interleaved)

    if args.only and os.path.exists(args.out):
        previous = json.load(open(args.out))
        results = merge_receipts(previous, results)
    with open(args.out, "w") as handle:
        json.dump(results, handle, allow_nan=False)
    print("saved", args.out)
    return 0 if all(results["tests"][key]["status"] == "ok" for key in selected) else 1


def compare(args):
    with open(args.reference) as handle:
        reference = json.load(handle)
    with open(args.candidate) as handle:
        candidate = json.load(handle)
    report = compare_reports(reference, candidate, args.tolerance)
    for row in report["checks"]:
        print(f"{row['test']:28s} {row['status']}: {'; '.join(row['issues'])}")
    for issue in report["issues"]:
        print(issue)
    print("NUMERIC COVERAGE", "PASS" if report["passed"] else "FAIL")
    print("Provenance, physical-domain coverage and universal JAX compatibility are separate checks.")
    if args.out:
        with open(args.out, "w") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--tree", required=True); r.add_argument("--out", required=True)
    r.add_argument("--setup", default="voyager", choices=["voyager", "dev", "uifo_20_5000"])
    r.add_argument("--only", help="Comma-separated test names; merged into an existing --out file")
    c = sub.add_parser("compare"); c.add_argument("reference"); c.add_argument("candidate")
    c.add_argument("--out", help="Write structured comparison report")
    c.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    sys.exit(run(args) if args.cmd == "run" else compare(args))
