#!/usr/bin/env python3
"""Time a complete public optical setup evaluation and gradient, then plot every phase."""
from time import perf_counter

IMPORT_START = perf_counter()
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess

os.environ["JAX_PLATFORMS"] = "cpu"
os.environ["JAX_ENABLE_X64"] = "true"
os.environ.setdefault("MPLBACKEND", "Agg")

# Set Linux CPU affinity before numerical libraries initialize their workers.
# Affinity, rather than JAX's device count, limits execution to N logical CPUs.
cpu_parser = argparse.ArgumentParser(add_help=False)
cpu_parser.add_argument("--cpus", type=int)
cpu_options, _ = cpu_parser.parse_known_args()
if cpu_options.cpus is not None:
    if not hasattr(os, "sched_getaffinity"):
        cpu_parser.error("--cpus requires Linux CPU affinity (Linux or WSL).")
    allowed_cpus = sorted(os.sched_getaffinity(0))
    if not 1 <= cpu_options.cpus <= len(allowed_cpus):
        cpu_parser.error(f"--cpus must be between 1 and {len(allowed_cpus)}.")
    os.sched_setaffinity(0, allowed_cpus[:cpu_options.cpus])
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = str(cpu_options.cpus)

import jax
import jax.numpy as jnp
import numpy as np
import differometor as df
from differometor.setups import aligo, constrain_inter_grid_cell_spaces

IMPORT_SECONDS = perf_counter() - IMPORT_START
PUBLIC_REPO = "https://github.com/artificial-scientist-lab/Differometor"
BASELINE_COMMIT = "b0dc7c79e7c72a1b010174f6bdcad01efa51d6ff"
FIXTURE_SHA256 = "ff4ba353a2a03cdce7f3e61bad729c2e00888d842c28ba9cf699f95afb87e138"
REFERENCE_SHA256 = "726f2cfe6986cb991fa48d5a28127b9330c3dc7e69d5bd193c8748acef03adc3"
ALIGO_REFERENCE_SHA256 = "e3419da07888d0260800be08ba873dc22518de0b103582740cc447e0014c5cb4"
ALIGO_SETUP_SHA256 = "f77fa86eeae1771a9aa3a9305c490a7ef406df6a542c3e93de303d3070536390"
PROPERTIES = ["reflectivity", "tuning", "db", "angle", "power", "mass", "length"]


def cpu_model():
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    if platform.system() == "Darwin":
        return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
    return platform.processor() or platform.machine()


def git_state(repo):
    """Identify simulator files even in a ZIP, without reading a parent repo."""
    repo = repo.resolve()
    state = {
        "commit": None,
        "modified": None,
        "diff_sha256": None,
        "simulator_files_sha256": {
            path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((repo / "differometor").rglob("*.py"))
            if path.is_file()
        },
    }

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL,
        ).strip()

    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
            return state
        state.update(
            commit=git("rev-parse", "HEAD"),
            modified=bool(git("status", "--porcelain", "--untracked-files=no")),
            diff_sha256=hashlib.sha256(git("diff", "HEAD").encode()).hexdigest(),
        )
    except (OSError, subprocess.SubprocessError):
        # Downloaded archives and machines without Git remain runnable.
        pass
    return state


def output_paths(args, parser):
    """Reject invalid or overlapping output destinations before simulation."""
    if args.output.suffix != ".json":
        parser.error("--output must use a .json filename.")
    plot_path = args.plot or args.output.with_suffix(".png")
    if plot_path.suffix.lower() not in {".png", ".svg", ".pdf"}:
        parser.error("--plot must use a .png, .svg or .pdf filename.")
    if args.save_arrays and args.save_arrays.suffix != ".npz":
        parser.error("--save-arrays must use a .npz filename.")
    paths = [args.output, plot_path]
    if args.save_arrays:
        paths.append(args.save_arrays)
    if len({path.resolve() for path in paths}) != len(paths):
        parser.error("The JSON report, plot and saved arrays need different paths.")
    if any(path.is_dir() for path in paths):
        parser.error("Output destinations must be filenames, not directories.")
    return plot_path


def forward_with_pullback(parameters, arrays):
    # A pullback contains the residual arrays needed by reverse-mode AD.
    # Returning it lets us time the forward and reverse passes separately.
    return jax.vjp(lambda p: df.simulate(**dict(arrays, optimized_parameters=p)), parameters)


def readout(outputs, detector_ports, reference):
    carrier, signal, noise = outputs
    signals = df.signal_detector(carrier, signal)[detector_ports]
    detected = signals.squeeze() if detector_ports.shape[0] == 1 else signals[0] - signals[1]
    sensitivity = (noise / jnp.abs(detected)).squeeze()
    loss = jnp.mean(jnp.log10(sensitivity / reference))
    return loss, (sensitivity, df.power_detector(carrier))


def sensitivity_with_pullback(outputs, detector_ports, reference):
    return jax.vjp(lambda values: readout(values, detector_ports, reference), outputs, has_aux=True)


def backward(simulation_pullback, readout_pullback, cotangent):
    output_cotangents = readout_pullback(cotangent)[0]
    return simulation_pullback(output_cotangents)[0]


def main(setup_name="grid", import_seconds=IMPORT_SECONDS):
    if setup_name not in {"grid", "aligo"}:
        raise ValueError("Unknown benchmark setup")
    is_aligo = setup_name == "aligo"
    parser = argparse.ArgumentParser(description=(
        "Time the complete public aLIGO optical setup and all 29 design gradients."
        if is_aligo else __doc__
    ))
    here = Path(__file__).resolve().parent
    entrypoint = here / ("benchmark_aligo.py" if is_aligo else "benchmark.py")
    parser.add_argument("--repo", type=Path, default=here if (here / "differometor").is_dir() else here / "Differometor")
    parser.add_argument("--cpus", type=int, help="Pin this process to N allocated logical CPUs before imports (Linux/WSL)")
    parser.add_argument("--repeats", type=int, default=10, help="Repeated forward + sensitivity + gradient evaluations")
    parser.add_argument("--output", type=Path, default=Path("benchmark-aligo.json" if is_aligo else "benchmark.json"), help="JSON report (.json)")
    parser.add_argument("--plot", type=Path, help="Timing plot (.png, .svg or .pdf); defaults to the JSON filename with .png suffix")
    parser.add_argument("--save-arrays", type=Path, help="Save physical outputs, sensitivity, powers, parameters and gradient (.npz)")
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error("Use at least three timed repetitions.")
    plot_path = output_paths(args, parser)
    repo = args.repo.resolve()
    if Path(df.__file__).resolve().parent != repo / "differometor":
        parser.error("Install the requested public checkout with: python -m pip install -e /path/to/Differometor")

    phases = [{"key": "imports", "label": "Python / library imports", "category": "setup", "seconds": import_seconds}]

    def timed(key, label, category, function):
        start = perf_counter()
        result = function()
        jax.block_until_ready(result)
        seconds = perf_counter() - start
        phases.append({"key": key, "label": label, "category": category, "seconds": seconds})
        print(f"{label}: {seconds:.6f} s", flush=True)
        return result

    def compile_phase(key, label, function, *values):
        lowered = timed(key + "_lower", label + ": trace / lower", "compile", lambda: jax.jit(function).lower(*values))
        return timed(key + "_compile", label + ": compile", "compile", lowered.compile)

    def initialize():
        jax.config.update("jax_enable_x64", True)
        jax.config.update("jax_enable_compilation_cache", False)
        return jax.devices("cpu")

    devices = timed("initialize", "Initialize CPU backend", "setup", initialize)
    print(f"CPU: {cpu_model()}; affinity: {len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else 'unknown'}; devices: {devices}", flush=True)

    data_dir = repo / "examples" / "data"
    fixture_path = None if is_aligo else data_dir / "uifo_800_3000.json"
    reference_path = data_dir / ("aligo_test_data.json" if is_aligo else "uifo_800_3000_test_data.json")
    reference_sha256 = ALIGO_REFERENCE_SHA256 if is_aligo else REFERENCE_SHA256
    sensitivity_tolerance = 1e-6 if is_aligo else 1e-5
    check_pair = ["sq1", "db"] if is_aligo else ["mb11", "tuning"]

    def load_inputs():
        fixture_bytes = fixture_path.read_bytes() if fixture_path else None
        reference_bytes = reference_path.read_bytes()
        return fixture_bytes, reference_bytes, json.loads(fixture_bytes) if fixture_bytes else None, json.loads(reference_bytes)

    fixture_bytes, reference_bytes, fixture, reference = timed("load", "Read and parse public inputs", "setup", load_inputs)
    # Integrity checks are validation, so they are outside measured phases.
    if hashlib.sha256(reference_bytes).hexdigest() != reference_sha256 or (
        fixture_bytes is not None and hashlib.sha256(fixture_bytes).hexdigest() != FIXTURE_SHA256
    ):
        parser.error("Restore the unchanged public fixtures from the baseline commit.")
    source = git_state(repo)

    def build_inputs():
        nonlocal fixture
        if is_aligo:
            # Use the unchanged public constructor, including squeezing and mechanics.
            setup, _ = aligo(mode="space_modulation")
            # Building adds metadata to the setup; keep the original input intact.
            fixture = deepcopy(setup.to_data())
            # aLIGO has independent physical lengths, not the grid's tied lengths.
            pairs = [list(pair) for pair in setup.parameters if pair[1] in PROPERTIES]
        else:
            setup = df.Setup.from_data(fixture)
            pairs = constrain_inter_grid_cell_spaces(setup.parameters, PROPERTIES)
        initial = []
        for pair in pairs:
            members = pair if isinstance(pair[0], list) else [pair]
            values = [fixture["nodes" if name in fixture["nodes"] else "edges"][name]["properties"][prop] for name, prop in members]
            if any(value != values[0] for value in values):
                raise ValueError("Grouped length parameters must agree in the public fixture")
            initial.append(values[0])
        parameters = jnp.asarray(initial, dtype=jnp.float64)
        frequencies = jnp.asarray(reference["frequencies"], dtype=jnp.float64)
        expected = jnp.asarray(reference["sensitivities"], dtype=jnp.float64)
        arrays, ports, *_ = df.run_build_step(setup, [("f", "frequency")], frequencies, pairs)
        arrays["optimized_parameters"] = parameters
        return arrays, jnp.asarray(ports), parameters, frequencies, expected, pairs, jnp.asarray(1.0, dtype=jnp.float64)

    arrays, ports, parameters, frequencies, expected, pairs, one = timed("build", "Build optical setup and prepare inputs", "setup", build_inputs)
    setup_sha256 = FIXTURE_SHA256
    if is_aligo:
        # Validation only: pin the constructed optical input, not simulator code.
        setup_sha256 = hashlib.sha256(json.dumps(fixture, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if setup_sha256 != ALIGO_SETUP_SHA256:
            parser.error("Restore the public aLIGO optical setup; its physical input has changed.")
    print(f"Workload: {len(frequencies)} frequencies; {len(parameters)} physical design variables; no optimizer", flush=True)

    forward = compile_phase("forward", "Forward", forward_with_pullback, parameters, arrays)
    outputs, simulation_pullback = timed("forward", "Forward simulation + AD residuals", "execute", lambda: forward(parameters, arrays))
    sensitivity_fn = compile_phase("sensitivity", "Sensitivity", sensitivity_with_pullback, outputs, ports, expected)
    loss, readout_pullback, (sensitivity, powers) = timed("sensitivity", "Sensitivity, powers and scalar loss", "execute", lambda: sensitivity_fn(outputs, ports, expected))
    gradient_fn = compile_phase("gradient", "Gradient", backward, simulation_pullback, readout_pullback, one)
    gradient = timed("gradient", "Reverse-mode gradient", "execute", lambda: gradient_fn(simulation_pullback, readout_pullback, one))
    host = timed("host_transfer", "Transfer results to host", "output", lambda: jax.device_get((outputs, sensitivity, powers, loss, gradient)))
    first_phases = list(phases)
    total = sum(phase["seconds"] for phase in first_phases)
    print(f"Complete first-run total (excluding validation): {total:.6f} s", flush=True)

    # Reuse compiled programs, but recompute both passes and all readouts each time.
    repeat_samples = []
    for index in range(args.repeats):
        # Do not keep the previous multi-GB AD tape alive during the next solve.
        del simulation_pullback, readout_pullback
        phases.clear()
        outputs, simulation_pullback = timed("forward", "Forward", "execute", lambda: forward(parameters, arrays))
        loss, readout_pullback, (sensitivity, powers) = timed("sensitivity", "Sensitivity", "execute", lambda: sensitivity_fn(outputs, ports, expected))
        gradient = timed("gradient", "Gradient", "execute", lambda: gradient_fn(simulation_pullback, readout_pullback, one))
        host = timed("host_transfer", "Host transfer", "output", lambda: jax.device_get((outputs, sensitivity, powers, loss, gradient)))
        sample = {phase["key"]: phase["seconds"] for phase in phases}
        repeat_samples.append(sample)
        print(f"Repeat {index + 1:02d}/{args.repeats}: {sum(sample.values()):.6f} s", flush=True)

    # Validation only: no timers below contribute to the benchmark total.
    del simulation_pullback, readout_pullback
    print("Validating outputs, reference sensitivity and finite-difference gradient...", flush=True)
    host_outputs, host_sensitivity, host_powers, host_loss, host_gradient = host
    for value in jax.tree_util.tree_leaves(host):
        if not np.isfinite(value).all():
            raise ValueError("Non-finite physical output, sensitivity, loss or gradient")
    if host_sensitivity.shape != expected.shape or np.any(host_sensitivity <= 0):
        raise ValueError("Expected one positive sensitivity per frequency")
    log_error = np.abs(np.log(host_sensitivity) - np.log(np.asarray(expected)))
    np.testing.assert_allclose(np.log(host_sensitivity), np.log(np.asarray(expected)), atol=sensitivity_tolerance, rtol=0)
    if host_gradient.shape != parameters.shape or not np.any(host_gradient != 0):
        raise ValueError("Expected a finite, nonzero full parameter gradient")

    # Independent central-difference spot check, away from near-bound reflectivities.
    check_index = pairs.index(check_pair)
    def loss_only(p, a, detector_ports, target):
        return readout(df.simulate(**dict(a, optimized_parameters=p)), detector_ports, target)[0]
    evaluate_loss = jax.jit(loss_only)
    autodiff = float(host_gradient[check_index])
    finite_differences = []
    # Two step sizes check convergence; smaller 1e-5 perturbations are noisy
    # for the saved grid setup in float64 arithmetic. For aLIGO, check squeezing.
    for check_step in (1e-3, 5e-4):
        upper = float(evaluate_loss(parameters.at[check_index].add(check_step), arrays, ports, expected))
        lower = float(evaluate_loss(parameters.at[check_index].add(-check_step), arrays, ports, expected))
        estimate = (upper - lower) / (2 * check_step)
        np.testing.assert_allclose(autodiff, estimate, rtol=0.01, atol=1e-6)
        finite_differences.append({"step": check_step, "central_difference": estimate, "absolute_error": abs(autodiff - estimate)})
    np.testing.assert_allclose(finite_differences[0]["central_difference"], finite_differences[1]["central_difference"], rtol=0.01, atol=1e-6)

    totals = [sum(sample.values()) for sample in repeat_samples]
    report = {
        "benchmark": "start-munich-2026-public-differometor-aligo-v1" if is_aligo else "start-munich-2026-public-differometor-uifo-v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "starter_sha256": hashlib.sha256(entrypoint.read_bytes()).hexdigest(),
        "benchmark_harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source": {"public_repository": PUBLIC_REPO, "baseline_commit": BASELINE_COMMIT, **source},
        "inputs": {"setup": "differometor.setups.aligo(mode='space_modulation')" if is_aligo else fixture_path.name, "label": "aLIGO optical setup" if is_aligo else "Complete optical setup", "setup_sha256": setup_sha256, "reference": reference_path.name, "reference_sha256": reference_sha256, "frequency_count": len(frequencies), "frequency_min_hz": float(frequencies.min()), "frequency_max_hz": float(frequencies.max()), "gradient_parameter_count": len(parameters), "optimization_pairs": pairs},
        "workload": {"objective": "mean(log10(sensitivity / public_reference))", "gradient_coordinates": "physical parameter values; independent lengths" if is_aligo else "physical parameter values; public grid-length tying", "optimizer_steps": 0, "forward_residuals": "saved for separately compiled reverse pass", "total_scope": "imports, CPU initialization, input I/O, setup, all lowering/compilation, forward, sensitivity/powers/loss, reverse-mode gradient and host transfer", "excluded": "validation and benchmark harness bookkeeping, repeated profiling, plot/report generation; interpreter launch before the first timer"},
        "environment": {
            "cpu_model": cpu_model(), "cpu_affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "cpu_affinity_ids": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "requested_logical_cpus": args.cpus,
            "logical_cpus_on_host": os.cpu_count(), "platform": platform.platform(), "python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in ("differometor", "jax", "jaxlib", "numpy", "optax")},
            "backend": jax.default_backend(), "jax_enable_x64": jax.config.jax_enable_x64, "persistent_compilation_cache": False,
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS"), "xla_flags": os.environ.get("XLA_FLAGS"),
            "thread_limits": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        },
        "phases": first_phases,
        "repeat_samples": repeat_samples,
        "timing_seconds": {"end_to_end": total, "trace_lower_and_compile": sum(p["seconds"] for p in first_phases if p["category"] == "compile"), "runtime_samples": totals, "runtime_median": statistics.median(totals), "runtime_min": min(totals), "runtime_max": max(totals), "phase_runtime_medians": {key: statistics.median(sample[key] for sample in repeat_samples) for key in repeat_samples[0]}},
        "validation": {
            "all_outputs_and_gradients_finite": True, "upstream_sensitivity_check_passed": True, "sensitivity_log_atol": sensitivity_tolerance, "max_absolute_log_sensitivity_error": float(log_error.max()),
            "gradient_check": {"parameter": ".".join(check_pair), "autodiff": autodiff, "finite_differences": finite_differences, "rtol": 0.01, "atol": 1e-6, "passed": True},
            "gradient_shape": list(host_gradient.shape), "gradient_norm": float(np.linalg.norm(host_gradient)), "loss": float(host_loss),
            "output_shapes": {name: list(value.shape) for name, value in zip(("carrier", "signal", "noise"), host_outputs)},
            "output_dtypes": {name: str(value.dtype) for name, value in zip(("carrier", "signal", "noise"), host_outputs)},
        },
    }
    if args.save_arrays:
        args.save_arrays.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.save_arrays, carrier=host_outputs[0], signal=host_outputs[1], noise=host_outputs[2], sensitivity=host_sensitivity, powers=host_powers, gradient=host_gradient, parameters=np.asarray(parameters), frequencies=np.asarray(frequencies))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from plot_timings import render
    render(report, plot_path)
    print(f"PASS: reference sensitivity and gradient spot check; full runtime median {statistics.median(totals):.6f} s")
    print(f"JSON: {args.output}\nPlot: {plot_path}")


if __name__ == "__main__":
    main()
