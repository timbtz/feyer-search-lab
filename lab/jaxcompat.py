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

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_ENABLE_X64", "true")
PROPERTIES = ["reflectivity", "tuning", "db", "angle", "power", "mass", "length"]


def run(args):
    sys.path.insert(0, os.path.abspath(args.tree))
    import numpy as np
    import jax
    import jax.numpy as jnp
    jax.config.update("jax_enable_x64", True)
    jax.config.update("jax_enable_compilation_cache", False)
    import differometor as df
    from differometor import setups as dsetups
    from differometor.setups import Setup, constrain_inter_grid_cell_spaces
    assert os.path.abspath(df.__file__).startswith(os.path.abspath(args.tree)), df.__file__
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

    results = dict(tree=os.path.abspath(args.tree), setup=args.setup, tests={})
    setup, pairs, freqs, arrays, params, loss = problem(args.setup)
    n = params.shape[0]
    rng = np.random.default_rng(0)
    direction = jnp.asarray(rng.standard_normal(n))
    direction = direction / jnp.linalg.norm(direction)
    # Scaled per-parameter steps keep the perturbed points physical for every property.
    scale = jnp.maximum(jnp.abs(params), 1e-3)

    def record(key, fn):
        if args.only and key not in args.only.split(","):
            return
        t = time.perf_counter()
        try:
            value = fn()
            value = jax.tree_util.tree_map(lambda x: np.asarray(x).tolist(), jax.device_get(value))
            results["tests"][key] = dict(status="ok", seconds=time.perf_counter() - t, value=value)
            print(f"[{key}] ok {time.perf_counter() - t:.2f}s", flush=True)
        except Exception as error:
            results["tests"][key] = dict(status="error", seconds=time.perf_counter() - t,
                                         error=f"{type(error).__name__}: {str(error).splitlines()[0][:300] if str(error) else ''}",
                                         trace=traceback.format_exc()[-1500:])
            print(f"[{key}] ERROR {type(error).__name__}: {str(error)[:200]}", flush=True)

    # 1. Optimizer-style reverse mode, the upstream examples' pattern.
    record("value_and_grad_jit", lambda: jax.jit(jax.value_and_grad(loss))(params))
    # 2. Several optimizer steps with changing parameters (detects stale caches).
    def descent():
        step = jax.jit(jax.value_and_grad(loss))
        p, history = params, []
        for _ in range(3):
            value, g = step(p)
            history.append(float(value))
            p = p - 1e-3 * scale * g / (jnp.linalg.norm(g) + 1e-300)
        return dict(losses=history, final=p)
    record("descent_3_steps", descent)
    # 3. Batched parameter sets (population optimizers, run_with_parameter_sets).
    batch = jnp.stack([params, params + 1e-3 * scale * direction, params - 1e-3 * scale * direction])
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
        previous["tests"].update(results["tests"])
        results = previous
    with open(args.out, "w") as handle:
        json.dump(results, handle)
    print("saved", args.out)


def compare(args):
    import numpy as np
    a = json.load(open(args.reference))["tests"]
    b = json.load(open(args.candidate))["tests"]

    def leaves(x):
        if isinstance(x, dict):
            return [v for k in sorted(x) for v in leaves(x[k])]
        if isinstance(x, (list, tuple)):
            try:  # rectangular numeric block
                return [np.asarray(x, dtype=complex).ravel()]
            except (ValueError, TypeError):  # e.g. (loss, gradient)
                return [v for item in x for v in leaves(item)]
        return [np.asarray([x], dtype=complex)]

    overall = True
    for key in a:
        ra, rb = a[key], b.get(key, dict(status="missing"))
        if rb["status"] != "ok":
            overall = False
            print(f"{key:28s} CANDIDATE {rb['status'].upper()}  {rb.get('error', '')[:160]}  (reference: {ra['status']})")
            continue
        if ra["status"] != "ok":
            print(f"{key:28s} reference {ra['status']}; candidate ok"); continue
        la, lb = leaves(ra["value"]), leaves(rb["value"])
        worst = 0.0
        for x, y in zip(la, lb):
            if x.shape != y.shape:
                worst = float("inf"); break
            worst = max(worst, float(np.abs(x - y).max() / max(np.abs(x).max(), 1e-300)))
        ok = worst <= args.tolerance
        overall &= ok
        print(f"{key:28s} {'ok   ' if ok else 'DIFF '} max rel diff {worst:.1e}   time {ra['seconds']:.1f}s -> {rb['seconds']:.1f}s")
    print("OVERALL", "COMPATIBLE" if overall else "INCOMPATIBLE OR DIFFERENT")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--tree", required=True); r.add_argument("--out", required=True)
    r.add_argument("--setup", default="voyager", choices=["voyager", "dev", "uifo_20_5000"])
    r.add_argument("--only", help="Comma-separated test names; merged into an existing --out file")
    c = sub.add_parser("compare"); c.add_argument("reference"); c.add_argument("candidate")
    c.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    run(args) if args.cmd == "run" else compare(args)
