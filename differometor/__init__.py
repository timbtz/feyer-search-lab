from differometor.setups import Setup
from differometor.simulate import run, run_build_step, run_simulation_step, simulate
from differometor.components import power_detector, signal_detector

__all__ = [
    "Setup", "run", "run_build_step", "run_simulation_step", "simulate",
    "visualize_setup", "power_detector", "signal_detector",
]


def __getattr__(name):
    if name == "visualize_setup":
        from differometor.plot import visualize_setup

        globals()[name] = visualize_setup
        return visualize_setup
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | {"visualize_setup"})
