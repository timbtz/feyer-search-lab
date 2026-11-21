#!/usr/bin/env python3
"""Cross-setup generalization check for Differometor candidates.

run:     python -m lab.gencheck run --tree /path/to/repo --out result.npz [--cases a,b,...]
compare: python -m lab.gencheck compare reference.npz candidate.npz
report:  python -m lab.gencheck report reference.npz candidate.npz --sha SHA --label NAME --output report.json

The final Feyer evaluation uses a different, slightly varied optical setup
(upstream commit 2bb437a), so a candidate must preserve physics and gradients
beyond the development fixture. `run` evaluates every case with the same
three-stage pipeline as benchmark.py (jit(vjp(simulate)) -> jit(vjp(readout))
-> jit(backward)) and stores outputs, sensitivity, powers, loss, gradient and
per-stage timings. Run each tree in its own process: the module name
`differometor` is shared. The script is standalone (no lab imports) so it can be
copied to an evaluator host and run with the fixed environment's Python.
"""
import os
import sys
import json
import math
import time
import argparse

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_ENABLE_X64", "true")

PROPERTIES = ["reflectivity", "tuning", "db", "angle", "power", "mass", "length"]
ALL_CASES = ["dev", "dev_perturbed", "uifo_20_5000", "uifo_rand1", "uifo_rand2", "uifo_rand3", "voyager", "aligo",
             "dev_randparams", "uifo_randparams1", "uifo_randparams2", "uifo_randparams3"]
# Opt-in cases (run with --cases): random UIFOs in the amplitude- and frequency-modulation modes,
# which exercise laser modulation component functions the supplied example never uses.
EXTRA_CASES = ["uifo_amod1", "uifo_fmod1"]
# Uniform ranges from upstream examples/uifo_optimization.py, the simulator's own random-parameter protocol.
# The organizers judge "a random setup with random parameters".
PROPERTY_BOUNDS = {"db": (0, 10), "angle": (-360, 360), "power": (0, 200), "tuning": (-360, 360),
                   "mass": (0.01, 200), "length": (0.1, 4000), "reflectivity": (0, 1)}


def run(args):
    sys.path.insert(0, os.path.abspath(args.tree))
    import numpy as np
    import jax
    import jax.numpy as jnp
    jax.config.update("jax_enable_x64", True)
    jax.config.update("jax_enable_compilation_cache", False)
    import differometor as df
    from differometor import setups as dsetups
    from differometor.setups import constrain_inter_grid_cell_spaces, Setup
    assert os.path.abspath(os.path.dirname(df.__file__)).startswith(os.path.abspath(args.tree)), df.__file__

    data_dir = os.path.join(args.tree, "examples", "data")

    def initial_values(data, pairs):
        values = []
        for pair in pairs:
            members = pair if isinstance(pair[0], list) else [pair]
            name, prop = members[0]
            values.append(float(np.real(data["nodes" if name in data["nodes"] else "edges"][name]["properties"][prop])))
        return values

    def perturbed(data, seed=7):
        rng = np.random.default_rng(seed)
        data = json.loads(json.dumps(data))
        for group in ("nodes", "edges"):
            for name, item in data[group].items():
                props = item.get("properties", {})
                for key, value in list(props.items()):
                    if not isinstance(value, (int, float)) or isinstance(value, bool):
                        continue
                    if key == "reflectivity":
                        props[key] = float(min(max(value * (1 + 0.02 * rng.standard_normal()), 1e-4), 1 - 1e-4))
                    elif key == "tuning":
                        props[key] = float(value + 0.5 * rng.standard_normal())
                    elif key == "length" and value > 0:
                        props[key] = float(value * (1 + 0.01 * rng.standard_normal()))
                    elif key == "power" and value > 0:
                        props[key] = float(value * (1 + 0.05 * rng.standard_normal()))
        return data

    def random_values(pairs, seed):
        rng = np.random.default_rng(seed)
        values = []
        for pair in pairs:
            prop = (pair if isinstance(pair[0], list) else [pair])[0][1]
            low, high = PROPERTY_BOUNDS[prop]
            values.append(float(rng.uniform(low, high)))
        return values

    def case(name):
        if name == "dev_randparams":
            fixture = json.load(open(os.path.join(data_dir, "uifo_800_3000.json")))
            setup = Setup.from_data(fixture)
            pairs = constrain_inter_grid_cell_spaces(setup.parameters, PROPERTIES)
            freqs = np.linspace(800, 3000, 101)
            return setup, pairs, random_values(pairs, 1001), freqs, np.ones_like(freqs)
        if name.startswith(("uifo_amod", "uifo_fmod")):
            seed = int(name[len("uifo_amod"):])
            mode = "amplitude_modulation" if name.startswith("uifo_amod") else "frequency_modulation"
            setup, component_pairs = dsetups.uifo(3, random=True, random_seed=200 + seed, mode=mode)
            pairs = constrain_inter_grid_cell_spaces(component_pairs, PROPERTIES)
            freqs = np.linspace(800, 3000, 101)
            return setup, pairs, random_values(pairs, 3000 + seed), freqs, np.ones_like(freqs)
        if name.startswith("uifo_randparams"):
            seed = int(name[len("uifo_randparams"):])
            setup, component_pairs = dsetups.uifo(3, random=True, random_seed=100 + seed)
            pairs = constrain_inter_grid_cell_spaces(component_pairs, PROPERTIES)
            freqs = np.linspace(800, 3000, 101)
            return setup, pairs, random_values(pairs, 2000 + seed), freqs, np.ones_like(freqs)
        if name in ("dev", "dev_perturbed"):
            fixture = json.load(open(os.path.join(data_dir, "uifo_800_3000.json")))
            reference = json.load(open(os.path.join(data_dir, "uifo_800_3000_test_data.json")))
            if name == "dev_perturbed":
                fixture = perturbed(fixture)
            setup = Setup.from_data(fixture)
            pairs = constrain_inter_grid_cell_spaces(setup.parameters, PROPERTIES)
            freqs = np.asarray(reference["frequencies"], dtype=np.float64)
            ref = np.asarray(reference["sensitivities"]) if name == "dev" else np.ones_like(freqs)
            return setup, pairs, initial_values(fixture, pairs), freqs, ref
        if name == "uifo_20_5000":
            fixture = json.load(open(os.path.join(data_dir, "uifo_20_5000.json")))
            setup = Setup.from_data(fixture)
            pairs = constrain_inter_grid_cell_spaces(setup.parameters, PROPERTIES)
            freqs = np.logspace(np.log10(20), np.log10(5000), 100)
            return setup, pairs, initial_values(fixture, pairs), freqs, np.ones_like(freqs)
        if name.startswith("uifo_rand"):
            seed = int(name[len("uifo_rand"):])
            setup, component_pairs = dsetups.uifo(3, random=True, random_seed=seed)
            pairs = constrain_inter_grid_cell_spaces(component_pairs, PROPERTIES)
            data = setup.to_data()
            freqs = np.linspace(800, 3000, 101)
            return setup, pairs, initial_values(data, pairs), freqs, np.ones_like(freqs)
        if name in ("voyager", "aligo"):
            setup, component_pairs = getattr(dsetups, name)()
            pairs = [list(p) for p in component_pairs if p[1] in PROPERTIES]
            data = setup.to_data()
            freqs = np.logspace(np.log10(20), np.log10(5000), 100)
            return setup, pairs, initial_values(data, pairs), freqs, np.ones_like(freqs)
        raise ValueError(name)

    def readout(outputs, detector_ports, reference):
        carrier, signal, noise = outputs
        signals = df.signal_detector(carrier, signal)[detector_ports]
        detected = signals.squeeze() if detector_ports.shape[0] == 1 else signals[0] - signals[1]
        sensitivity = (noise / jnp.abs(detected)).squeeze()
        loss = jnp.mean(jnp.log10(sensitivity / reference))
        return loss, (sensitivity, df.power_detector(carrier))

    results = {}
    cases = args.cases.split(",") if args.cases else ALL_CASES
    for name in cases:
        timings = {}
        try:
            t = time.perf_counter()
            setup, pairs, init, freqs, ref = case(name)
            arrays, ports, *_ = df.run_build_step(setup, [("f", "frequency")], jnp.asarray(freqs), pairs)
            params = jnp.asarray(init, dtype=jnp.float64)
            arrays["optimized_parameters"] = params
            ports = jnp.asarray(ports)
            ref = jnp.asarray(ref, dtype=jnp.float64)
            jax.block_until_ready(arrays)
            timings["build"] = time.perf_counter() - t

            def fwd(p, a):
                return jax.vjp(lambda q: df.simulate(**dict(a, optimized_parameters=q)), p)

            def sens(o, dp, r):
                return jax.vjp(lambda v: readout(v, dp, r), o, has_aux=True)

            def bwd(sp, rp, c):
                return sp(rp(c)[0])[0]

            def staged(key, fn, *vals):
                t0 = time.perf_counter(); low = jax.jit(fn).lower(*vals); timings[key + "_lower"] = time.perf_counter() - t0
                t0 = time.perf_counter(); comp = low.compile(); timings[key + "_compile"] = time.perf_counter() - t0
                t0 = time.perf_counter(); out = jax.block_until_ready(comp(*vals)); timings[key] = time.perf_counter() - t0
                return out

            outputs, spb = staged("forward", fwd, params, arrays)
            loss, rpb, (sensitivity, powers) = staged("sensitivity", sens, outputs, ports, ref)
            grad = staged("gradient", bwd, spb, rpb, jnp.asarray(1.0, dtype=jnp.float64))
            host = jax.device_get((outputs, sensitivity, powers, loss, grad))
            (carrier, signal, noise), sensitivity, powers, loss, grad = host
            prefix = name + "/"
            for key, value in (("carrier", carrier), ("signal", signal), ("noise", noise), ("sensitivity", sensitivity),
                               ("powers", powers), ("loss", np.asarray(loss)), ("gradient", grad), ("parameters", np.asarray(params)),
                               ("frequencies", freqs)):
                results[prefix + key] = np.asarray(value)
            results[prefix + "timings"] = np.asarray(json.dumps(timings))
            first = sum(timings.values())
            print(f"[{name}] ok n_params={len(init)} n_freq={len(freqs)} ports={np.asarray(ports).tolist()} "
                  f"loss={float(loss):.10g} first_run(no imports)={first:.3f}s "
                  + " ".join(f"{k}={v:.3f}" for k, v in timings.items()), flush=True)
            del spb, rpb, outputs
        except Exception as error:  # record failure per case, keep going
            import traceback
            traceback.print_exc()
            results[name + "/error"] = np.asarray(repr(error))
            print(f"[{name}] ERROR {error!r}", flush=True)
    if getattr(args, "merge", False) and os.path.exists(args.out):
        previous = np.load(args.out, allow_pickle=False)
        replaced = {k.split("/")[0] for k in results}
        results = {**{k: previous[k] for k in previous.files if k.split("/")[0] not in replaced}, **results}
    np.savez_compressed(args.out, **results)
    print("saved", args.out)


# Acceptance thresholds for one case. The sensitivity bound is the official
# benchmark's; the gradient bound is this harness's cross-setup review gate,
# deliberately looser than the team's strict 1e-7 saved-array regression check.
LOG_SENSITIVITY_TOLERANCE = 1e-5
GRADIENT_REL_L2_TOLERANCE = 1e-4
OUTPUT_KEYS = ("carrier", "signal", "noise", "powers")


def finite_or_none(value):
    return value if value is None or math.isfinite(value) else None


def compare_cases(reference_path, candidate_path):
    """Return one structured row per case plus an overall verdict."""
    import numpy as np
    a = np.load(reference_path, allow_pickle=False)
    b = np.load(candidate_path, allow_pickle=False)
    names = sorted({k.split("/")[0] for k in a.files} | {k.split("/")[0] for k in b.files})
    rows, overall = [], True
    for name in names:
        row = dict(case=name, status="ok", issues=[])
        if name + "/error" in b.files:
            row.update(status="candidate_error", issues=[str(b[name + "/error"])]); rows.append(row); overall = False; continue
        if name + "/error" in a.files or name + "/gradient" not in a.files:
            row.update(status="reference_unavailable"); rows.append(row); continue
        if name + "/gradient" not in b.files:
            row.update(status="candidate_missing"); rows.append(row); overall = False; continue
        sa, sb = a[name + "/sensitivity"], b[name + "/sensitivity"]
        finite = all(bool(np.isfinite(b[name + "/" + k]).all()) for k in OUTPUT_KEYS + ("sensitivity", "gradient"))
        positive = bool(np.all(sa > 0) and np.all(sb > 0))
        log_error = float(np.max(np.abs(np.log(sb) - np.log(sa)))) if positive else None
        output_errors = {}
        for key in OUTPUT_KEYS:
            x, y = a[name + "/" + key], b[name + "/" + key]
            if x.shape != y.shape:
                output_errors[key] = None; row["issues"].append(f"{key} shape {x.shape} != {y.shape}"); continue
            output_errors[key] = float(np.abs(x - y).max() / max(np.abs(x).max(), 1e-300))
        ga, gb = a[name + "/gradient"], b[name + "/gradient"]
        if ga.shape != gb.shape:
            rel_l2 = worst = None; worst_index = None; row["issues"].append(f"gradient shape {ga.shape} != {gb.shape}")
        else:
            rel_l2 = float(np.linalg.norm(ga - gb) / max(np.linalg.norm(ga), 1e-300))
            normalized = np.abs(ga - gb) / np.maximum(np.abs(ga), 1e-3 * np.abs(ga).max())
            worst, worst_index = float(normalized.max()), int(normalized.argmax())
        ta = json.loads(str(a[name + "/timings"])); tb = json.loads(str(b[name + "/timings"]))
        ok = (finite and log_error is not None and log_error <= LOG_SENSITIVITY_TOLERANCE
              and rel_l2 is not None and rel_l2 <= GRADIENT_REL_L2_TOLERANCE and not row["issues"])
        if not finite:
            row["issues"].append("non-finite candidate output or gradient")
        if log_error is None:
            row["issues"].append("non-positive sensitivity")
        row.update(
            status="ok" if ok else "needs_review",
            frequencies=int(a[name + "/frequencies"].shape[0]),
            design_variables=int(ga.shape[0]),
            finite=finite,
            max_abs_log_sensitivity_error=finite_or_none(log_error),
            max_relative_output_error={k: finite_or_none(v) for k, v in output_errors.items()},
            gradient_relative_l2=finite_or_none(rel_l2),
            gradient_worst_normalized=finite_or_none(worst),
            gradient_worst_index=worst_index,
            loss_abs_difference=finite_or_none(abs(float(a[name + "/loss"]) - float(b[name + "/loss"]))),
            reference_seconds=sum(ta.values()),
            candidate_seconds=sum(tb.values()),
            reference_timings=ta,
            candidate_timings=tb,
        )
        overall &= ok
        rows.append(row)
    return rows, overall


def compare(args):
    rows, overall = compare_cases(args.reference, args.candidate)
    for r in rows:
        if r["status"] in ("candidate_error", "reference_unavailable", "candidate_missing"):
            print(f"{r['case']:14s} {r['status'].upper()} {' '.join(r['issues'])}"); continue
        out = r["max_relative_output_error"]
        fmt = lambda v: "n/a" if v is None else f"{v:.1e}"
        print("  ".join([
            f"{r['case']:14s}",
            f"logS={fmt(r['max_abs_log_sensitivity_error'])}",
            *(f"{k}={fmt(out[k])}" for k in OUTPUT_KEYS),
            f"grad relL2={fmt(r['gradient_relative_l2'])} worst={fmt(r['gradient_worst_normalized'])}@{r['gradient_worst_index']}",
            f"loss diff={fmt(r['loss_abs_difference'])}",
            "finite" if r["finite"] else "NONFINITE",
            f"time {r['reference_seconds']:.2f}s->{r['candidate_seconds']:.2f}s",
            "OK" if r["status"] == "ok" else "CHECK",
        ]))
    print("OVERALL", "OK" if overall else "NEEDS REVIEW")


def report(args):
    """Add or replace one candidate's comparison in a dashboard collection file."""
    rows, overall = compare_cases(args.reference, args.candidate)
    record = dict(
        schema="feyer-generalization-v1",
        candidate_sha=args.sha,
        label=args.label,
        branch=args.branch,
        reference_sha=args.reference_sha,
        instance=args.instance,
        cpu=args.cpu,
        observed_at=time.time(),
        status="ok" if overall else "needs_review",
        thresholds=dict(max_abs_log_sensitivity_error=LOG_SENSITIVITY_TOLERANCE,
                        gradient_relative_l2=GRADIENT_REL_L2_TOLERANCE),
        timing_scope=("Exploratory development timing on a non-evaluator CPU, excluding imports; "
                      "not a scored queue measurement."),
        cases=rows,
    )
    path = os.path.abspath(args.output)
    try:
        with open(path) as handle:
            collection = json.load(handle)
    except FileNotFoundError:
        collection = dict(schema="feyer-generalization-collection-v1", reports=[])
    reports = [r for r in collection.get("reports", []) if r.get("candidate_sha") != args.sha]
    reports.append(record)
    collection = dict(schema="feyer-generalization-collection-v1", reports=reports)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(collection, handle, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)
    print(f"{args.label}: {record['status']} ({len(rows)} cases) -> {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--tree", required=True); r.add_argument("--out", required=True); r.add_argument("--cases")
    r.add_argument("--merge", action="store_true", help="Keep other cases already stored in --out")
    c = sub.add_parser("compare"); c.add_argument("reference"); c.add_argument("candidate")
    p = sub.add_parser("report", help="Write a dashboard record (.lab/generalization/report.json)")
    p.add_argument("reference"); p.add_argument("candidate")
    p.add_argument("--sha", required=True); p.add_argument("--label", required=True)
    p.add_argument("--branch"); p.add_argument("--reference-sha", default="02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f")
    p.add_argument("--instance", default="amd-hackathon"); p.add_argument("--cpu", type=int)
    p.add_argument("--output", required=True)
    args = parser.parse_args()
    {"run": run, "compare": compare, "report": report}[args.cmd](args)
