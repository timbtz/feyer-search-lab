"""Duplicate sweeps through tiny real host callbacks; no benchmark or timing."""
import ast
import itertools
import json
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = "86f26be624002fcb33c22f9a64259af16e73356c"


def main():
    # Reuse only the prior diagnostic's loader/fixture definitions, without
    # running its top-level 96-case inspection or changing production globals.
    helper_path = ROOT / "experiments/notes/overnight-numerics-destination-broadcast-callback-check.py"
    nodes = []
    for node in ast.parse(helper_path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "parent" for t in node.targets):
            break
        nodes.append(node)
    helper = {"__file__": str(helper_path)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(helper_path), "exec"), helper)
    helper["names"].add("_sweep_last_writes")
    components = (ROOT / "differometor/host.py").read_text()
    current = (ROOT / "differometor/host_pass.py").read_text()
    parent = subprocess.check_output(
        ["git", "show", PARENT + ":differometor/host_pass.py"], cwd=ROOT, text=True)
    versions = [helper["load"](source, components)[0] for source in (parent, current)]
    cases = coordinates = 0
    parent_overwritten_nonzero = 0
    maximum_relative_error = 0.
    for mode, modulation, stage in itertools.product(
            ("matched", "cleared"),
            ("signal_function", "laser_amplitude_modulation",
             "laser_frequency_modulation", "laser_frequency_modulation_lower"),
            ("carrier", "signal")):
        outputs = []
        for version, ns in enumerate(versions):
            cs, ss, noise = helper["system"](2, [4], True), helper["system"](4, [16], True), helper["system"](4, [0], False)
            functions = {f.__name__: i for i, f in enumerate(ns["HOST_FUNCTIONS"])}
            def plan(system, name):
                return ns["SystemPlan"](system, [(functions[name], np.arange(7)[None, :], (0, 1))], [0], [0])
            structure = helper["SimpleNamespace"](
                carrier=cs, signal=ss, noise=noise,
                signal_placing_positions=np.array([], int), signal_conjugate=np.zeros(18, bool))
            hp = helper["SimpleNamespace"](
                _key="duplicate-sweep-synthetic", structure=structure, noise_row_reuse=False,
                carrier_changing=np.array([1, 1] if stage == "carrier" else [1]),
                signal_changing=np.array([0, 0] if stage == "signal" else [0]),
                signal_carrier_indices=np.array([], int), carrier=plan(cs, "laser"),
                signal=plan(ss, modulation), noise=plan(noise, "signal_function"))
            params = np.full((1, 7), .4, dtype=complex)
            cv = np.array([[3., 4.], [5., 6.]] if stage == "carrier" else [[.4]], complex)
            sv = np.array([[0., 23.], [35., 60.]] if stage == "signal" else [[.4]], complex)
            cb = np.r_[(np.eye(2) * 3).ravel(), [0., .1]].astype(complex)
            sb = np.r_[(np.eye(4) * 4).ravel(), [0., .1]].astype(complex)
            nb = (np.eye(4) * 2).ravel().astype(complex)
            nb[4] = .02j
            selects = np.array([[[.2, .3j, .5, .7j]], [[.3j, .1, .8j, .2]]])
            args = (params, cv, sv, cb, sb, nb, selects)
            forward = ns["host_forward"](hp, *args)
            c, s, n, cov, w = forward
            bars = (np.full(c.shape, .01 + .02j), np.full(s.shape, .02 - .03j), np.full(n.shape, .04))
            if mode == "cleared":
                ns["_ASSEMBLY"].clear()
            backward = ns["host_backward"](hp, *args, c, s, n, cov, w, *bars)
            outputs.append((forward, backward))
            duplicate_arg = 1 if stage == "carrier" else 2
            for values_bar in (backward[duplicate_arg],):
                assert np.all(np.isfinite(values_bar))
                if version:
                    assert np.all(values_bar[0] == 0)
                elif np.any(values_bar[0] != 0):
                    parent_overwritten_nonzero += 1
            if not version:
                continue
            def loss(arguments):
                result = ns["host_forward"](hp, *arguments)
                return float(sum(np.real(np.sum(y * bar)) for y, bar in zip(result[:3], bars)))
            for arg in (1, 2):
             for index in np.ndindex(args[arg].shape):
                plus, minus = [x.copy() for x in args], [x.copy() for x in args]
                step = 1e-4
                plus[arg][index] += step
                minus[arg][index] -= step
                numerical = (loss(plus) - loss(minus)) / (2 * step)
                expected = float(np.real(backward[arg][index]))
                scale = max(abs(expected), 1e-8)
                maximum_relative_error = max(maximum_relative_error, abs(numerical - expected) / scale)
                np.testing.assert_allclose(numerical, expected, rtol=2e-6, atol=1e-9)
                coordinates += 1
        # Only overwritten sweep cotangents may differ from the parent.
        helper["helper"]["check_equal"](outputs[0][0], outputs[1][0])
        for arg, (old_bar, new_bar) in enumerate(zip(outputs[0][1], outputs[1][1])):
            if arg == duplicate_arg:
                helper["helper"]["check_equal"]((old_bar[1:],), (new_bar[1:],))
            else:
                helper["helper"]["check_equal"]((old_bar,), (new_bar,))
        cases += 1
    assert parent_overwritten_nonzero > 0
    print(json.dumps(dict(parent=PARENT, callback_cases=cases,
                         finite_difference_coordinates=coordinates,
                         parent_overwritten_nonzero_blocks=parent_overwritten_nonzero,
                         maximum_scaled_finite_difference_error=maximum_relative_error,
                         scope="Small actual NumPy/SuperLU callbacks, separate carrier/signal sweeps, four modulation functions, matched/cleared state; no JAX or official workload"), indent=2))


if __name__ == "__main__":
    main()
