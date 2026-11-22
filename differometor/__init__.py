import os as _os

# XLA only compiles small programs here: the physics runs in NumPy (differometor.host), and
# what XLA still compiles is the caller's readout code and two callbacks. For such programs
# LLVM's backend optimizations cost more compile time than they save at run time, so they
# are switched off. Outputs are unchanged (checked entry by entry, scripts/compare.py).
# The flag must be set before JAX initializes its backend. Opt out with
# DIFFEROMETOR_XLA_DEFAULTS=1, or by setting --xla_backend_optimization_level in XLA_FLAGS.
if (_os.environ.get("DIFFEROMETOR_XLA_DEFAULTS") != "1"
        and "xla_backend_optimization_level" not in _os.environ.get("XLA_FLAGS", "")):
    _os.environ["XLA_FLAGS"] = (_os.environ.get("XLA_FLAGS", "") + " --xla_backend_optimization_level=0").strip()

from differometor.setups import Setup
from differometor.simulate import run, run_build_step, run_simulation_step, simulate
from differometor.plot import visualize_setup
from differometor.components import power_detector, signal_detector