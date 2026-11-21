import os as _os

# Package-level XLA compiler settings (allowed by the Feyer organizers). The heavy
# numerical work runs on the host (SuperLU and NumPy callbacks), so the XLA programs
# are small gathers, scatters and readouts whose compile time far exceeds their run
# time. Optimization level 0 without the CPU fusion emitters compiles them ~3x faster
# with unchanged outputs (rounding-level differences only, no fast-math). XLA reads
# XLA_FLAGS when JAX creates its CPU backend, so this has an effect only if
# differometor is imported before the first JAX computation. Flags a user already
# set in XLA_FLAGS are never overridden; DIFFEROMETOR_XLA_DEFAULTS=0 disables this.
# These settings apply to every XLA program in the process.
_XLA_DEFAULTS = ("--xla_backend_optimization_level=0", "--xla_cpu_use_fusion_emitters=false")


def _apply_xla_defaults():
    if _os.environ.get("DIFFEROMETOR_XLA_DEFAULTS", "1") == "0":
        return
    existing = _os.environ.get("XLA_FLAGS", "")
    present = {flag.split("=", 1)[0] for flag in existing.split()}
    added = [flag for flag in _XLA_DEFAULTS if flag.split("=", 1)[0] not in present]
    if added:
        _os.environ["XLA_FLAGS"] = " ".join(part for part in (existing, *added) if part)


_apply_xla_defaults()

from differometor.setups import Setup
from differometor.simulate import run, run_build_step, run_simulation_step, simulate
from differometor.plot import visualize_setup
from differometor.components import power_detector, signal_detector
