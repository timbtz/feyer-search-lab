#!/usr/bin/env python3
"""Plot five phases from either optical-setup benchmark (no simulation needed)."""

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


INK = "#22272B"
MUTED = "#626A71"
RED = "#C73135"
GROUPS = (
    ("Setup", ("imports", "initialize", "load", "build")),
    ("Compilation", (
        "forward_lower", "forward_compile", "sensitivity_lower",
        "sensitivity_compile", "gradient_lower", "gradient_compile",
    )),
    ("Forward simulation", ("forward",)),
    ("Sensitivity", ("sensitivity", "host_transfer")),
    ("Gradient", ("gradient",)),
)


def seconds_label(value):
    """Use milliseconds for tiny phases so a measured value never reads as zero."""
    return f"{value:.2f} s" if value >= 0.01 else f"{value * 1000:.2f} ms"


def phase_summary(report):
    """Group all fourteen measured stages exactly once into five readable phases."""
    phases = report["phases"]
    values = {}
    for phase in phases:
        key = phase["key"]
        if key in values:
            raise ValueError(f"Duplicate phase: {key}")
        seconds = float(phase["seconds"])
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Phase times must be finite and non-negative")
        values[key] = seconds
    expected = {key for _, keys in GROUPS for key in keys}
    if set(values) != expected:
        raise ValueError(
            f"Unexpected phase set: missing={sorted(expected - set(values))}, "
            f"unknown={sorted(set(values) - expected)}"
        )
    total = float(report["timing_seconds"]["end_to_end"])
    if not math.isfinite(total) or total <= 0 or not math.isclose(
        math.fsum(values.values()), total, rel_tol=1e-9, abs_tol=1e-9
    ):
        raise ValueError("Phase times must sum to the reported end-to-end time")
    grouped = [(label, math.fsum(values[key] for key in keys)) for label, keys in GROUPS]
    if not math.isclose(math.fsum(value for _, value in grouped), total, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("Grouped phases must preserve the complete measured total")
    return grouped, total


def render(report, output):
    """Save a compact first-run phase chart to PNG, SVG or PDF."""
    grouped, total = phase_summary(report)
    labels, values = zip(*grouped)
    environment = report.get("environment", {})
    cpu = environment.get("cpu_model", "CPU not recorded").replace("(R)", "").strip()
    affinity = environment.get("cpu_affinity_count")
    details = cpu
    if affinity is not None:
        details += f" · {affinity} logical CPU" + ("s" if affinity != 1 else "")

    with plt.rc_context({
        "font.family": "DejaVu Sans", "font.size": 11,
        "text.color": INK, "axes.labelcolor": MUTED,
        "xtick.color": MUTED, "ytick.color": INK,
        "svg.fonttype": "none", "pdf.fonttype": 42,
    }):
        fig = plt.figure(figsize=(9, 5.6), facecolor="white")
        fig.text(0.06, 0.92, "Time per phase", fontsize=21, weight="bold")
        fig.text(0.95, 0.92, seconds_label(total), ha="right", fontsize=21, weight="bold")
        fig.text(0.95, 0.875, "TOTAL", ha="right", fontsize=9, color=MUTED)
        fig.text(0.06, 0.855, details, fontsize=10, color=MUTED)
        setup_label = report.get("inputs", {}).get("label", "Complete optical setup")
        fig.text(0.06, 0.80, f"{setup_label} simulation + gradient · first run", fontsize=11)

        ax = fig.add_axes([0.26, 0.24, 0.69, 0.49])
        ax.barh(range(len(values)), values, height=0.54, color=RED, zorder=3)
        ax.set_yticks(range(len(labels)), labels)
        ax.invert_yaxis()
        maximum = max(values)
        ax.set_xlim(0, maximum * 1.25)
        ax.set_xlabel("Seconds", labelpad=9)
        ax.xaxis.grid(True, color="#ECEDEC", linewidth=0.8, zorder=0)
        ax.tick_params(axis="both", length=0)
        ax.tick_params(axis="y", pad=12)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for index, value in enumerate(values):
            ax.text(value + maximum * 0.02, index, seconds_label(value), va="center", fontsize=11)

        fig.text(
            0.06, 0.075,
            "Setup includes imports and input preparation. Sensitivity includes host transfer.\n"
            "Total includes compilation. Validation and repeat runs are excluded.",
            fontsize=8.5, color=MUTED, linespacing=1.5,
        )
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=200, facecolor="white")
        plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="JSON report from benchmark.py or benchmark_aligo.py")
    parser.add_argument("--output", type=Path, required=True, help="Output PNG, SVG or PDF")
    args = parser.parse_args()
    output = render(json.loads(args.report.read_text()), args.output)
    print(f"Plot: {output}")


if __name__ == "__main__":
    main()
