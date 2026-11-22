"""Supervisor-only diagnostic context; this module does not run a workload.

Use around an existing synchronized diagnostic driver, under the evaluator's
fixed CPU/thread policy. Each host callback gets its own cProfile instance in
its calling thread, so JAX worker-thread execution is included. Keep the first
forward/backward records separate from later callbacks. Do not use instrumented
results as official timing or promotion evidence: profiler overhead is included,
and importing the simulator before a driver changes its import-time accounting.

Example integration in a diagnostic driver (not the public benchmark):
    with collect_host_profiles() as records:
        ... execute and synchronize the driver's requested evaluations ...
    ... serialize records as JSON to the coordinator's diagnostic artifact ...

No physical values, factors, outputs or validation functions are modified.
The context restores entry points even if the diagnostic raises an exception.
"""
from contextlib import contextmanager
import cProfile
from functools import wraps
import pstats
from threading import Lock


@contextmanager
def collect_host_profiles(module=None):
    if module is None:
        from differometor import host_pass as module
    names = ("host_forward", "host_backward")
    originals = {name: getattr(module, name) for name in names}
    records = []
    lock = Lock()
    ordinals = {name: 0 for name in names}

    def instrument(name, function):
        @wraps(function)
        def call(*args, **kwargs):
            with lock:
                ordinals[name] += 1
                ordinal = ordinals[name]
            profiler = cProfile.Profile()
            succeeded = False
            try:
                result = profiler.runcall(function, *args, **kwargs)
                succeeded = True
                return result
            finally:
                stats = pstats.Stats(profiler)
                functions = []
                for (filename, line, function_name), entry in stats.stats.items():
                    primitive_calls, total_calls, self_seconds, cumulative_seconds, _ = entry
                    functions.append(dict(file=filename, line=line, function=function_name,
                                          primitive_calls=primitive_calls, total_calls=total_calls,
                                          self_seconds=self_seconds, cumulative_seconds=cumulative_seconds))
                functions.sort(key=lambda item: item["cumulative_seconds"], reverse=True)
                record = dict(callback=name, ordinal=ordinal, succeeded=succeeded,
                              scope="instrumented callback diagnostic; not official timing",
                              profiled_seconds=stats.total_tt, functions=functions)
                with lock:
                    records.append(record)
        return call

    try:
        for name, function in originals.items():
            setattr(module, name, instrument(name, function))
        yield records
    finally:
        for name, function in originals.items():
            setattr(module, name, function)
