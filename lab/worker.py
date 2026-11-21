"""Serial evaluator with immutable checkouts, process-group timeouts and durable results."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import math
import os
import platform
import re
import signal
import socket
import subprocess
import time
import uuid
from pathlib import Path

from .queue import Queue
from .resources import MemoryMonitor

BASELINE_SHA = "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f"
PROTECTED_PATHS = ("benchmark.py", "plot_timings.py", "examples/data", "requirements.txt", "pyproject.toml", "setup.py")
PHASE_CATEGORIES = {
    "imports": "setup", "initialize": "setup", "load": "setup", "build": "setup",
    "forward_lower": "compile", "forward_compile": "compile", "forward": "execute",
    "sensitivity_lower": "compile", "sensitivity_compile": "compile", "sensitivity": "execute",
    "gradient_lower": "compile", "gradient_compile": "compile", "gradient": "execute",
    "host_transfer": "output",
}
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
FIXTURE_SHA256 = "ff4ba353a2a03cdce7f3e61bad729c2e00888d842c28ba9cf699f95afb87e138"
REFERENCE_SHA256 = "726f2cfe6986cb991fa48d5a28127b9330c3dc7e69d5bd193c8748acef03adc3"


class WorkerBusyError(RuntimeError):
    pass


class RejectedCandidate(RuntimeError):
    pass


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def peak_rss_kib(path):
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        return None
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", text)
    return int(match.group(1)) if match else None


def resource_snapshot():
    """Read shared container limits; these are not an enforced per-job memory cap."""
    limits = {}
    root = Path("/sys/fs/cgroup")
    for name in ("memory.max", "memory.swap.max", "cpu.max", "cpuset.cpus.effective"):
        try:
            limits[name] = (root / name).read_text().strip()
        except OSError:
            limits[name] = None
    return {"container_limits": limits,
            "worker_cpu_affinity_ids": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "per_job_memory_limit_enforced": False,
            "memory_measurement": "GNU time maximum resident set size; shared cgroup limits are recorded separately"}


class Worker:
    def __init__(self, queue: Queue, runs_dir, evaluator_root,
                 python_path="/workspace/venv-feyer/bin/python", cpu=2,
                 timeout=900, baseline_sha=BASELINE_SHA,
                 reference_arrays="/workspace/feyer-pristine/base1.npz",
                 heartbeat_seconds=5, stale_seconds=120, compare_full=True,
                 memory_budget_bytes=32_000_000_000):
        self.queue = queue
        self.runs_dir = Path(runs_dir).resolve()
        self.evaluator_root = Path(evaluator_root).resolve()
        self.python_path = str(python_path)
        self.cpu = int(cpu)
        self.timeout = float(timeout)
        self.baseline_sha = baseline_sha
        self.reference_arrays = Path(reference_arrays).resolve() if reference_arrays else None
        self.heartbeat_seconds = max(0.05, float(heartbeat_seconds))
        self.stale_seconds = float(stale_seconds)
        self.compare_full = compare_full
        if isinstance(memory_budget_bytes, bool):
            raise ValueError("Memory budget must be a positive byte count")
        self.memory_budget_bytes = int(memory_budget_bytes)
        self.last_memory_report = {}
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        if self.timeout <= 0 or self.cpu < 0 or self.memory_budget_bytes <= 0:
            raise ValueError("Positive timeout/memory budget and nonnegative CPU required")

    @contextlib.contextmanager
    def _lock(self):
        with (self.queue.state_dir / "worker.lock").open("a+") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise WorkerBusyError("Another evaluator holds the worker lock") from exc
            try:
                yield handle.fileno()
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _verify(self, job):
        actual = self.queue._git("rev-parse", f"refs/candidates/{job['id']}")
        if actual != job["sha"]:
            raise RejectedCandidate("Pinned candidate ref no longer matches submitted SHA")
        changed = self.queue._git("diff", "--name-only", self.baseline_sha, job["sha"], "--", *PROTECTED_PATHS)
        if changed:
            raise RejectedCandidate("Protected challenge files changed: " + ", ".join(changed.splitlines()))

    def _build_command(self, job, code, run):
        evaluator = self.evaluator_root / "screen.py" if job["profile"] == "screen" else code / "benchmark.py"
        if not evaluator.is_file():
            raise FileNotFoundError(f"Evaluator missing: {evaluator}")
        command = ["/usr/bin/time", "-v", "-o", str(run / "time.txt"),
                   "taskset", "-c", str(self.cpu), self.python_path, "-u", str(evaluator)]
        if job["profile"] == "screen":
            command += ["--repo", str(code)]
        command += ["--cpus", "1", "--output", str(run / "report.json"),
                    "--save-arrays", str(run / "arrays.npz")]
        if job["profile"] == "full":
            command += ["--repeats", "3"]
        return command, evaluator

    @staticmethod
    def _environment(code):
        env = os.environ.copy()
        for name in tuple(env):
            if name.startswith(("JAX_", "XLA_")):
                env.pop(name)
        for name in ("PYTHONHOME", "PYTHONSTARTUP", "XLA_FLAGS", "JAX_COMPILATION_CACHE_DIR"):
            env.pop(name, None)
        env.update(PYTHONPATH=str(code), PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1",
                   JAX_PLATFORMS="cpu", JAX_ENABLE_X64="true", JAX_ENABLE_COMPILATION_CACHE="false",
                   OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
                   NUMEXPR_NUM_THREADS="1", MPLBACKEND="Agg", LC_ALL="C.UTF-8")
        return env

    @staticmethod
    def _terminate_group(process):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        # Kill descendants even when the direct child exited before them.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

    def _execute(self, command, code, log_path, job, lock_fd):
        start = time.monotonic()
        memory_monitor = MemoryMonitor(self.memory_budget_bytes)
        with Path(log_path).open("w") as log:
            process = subprocess.Popen(command, cwd=code, env=self._environment(code),
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True, pass_fds=(lock_fd,))
            next_heartbeat = start
            try:
                while process.poll() is None:
                    now = time.monotonic()
                    if memory_monitor.sample(process.pid):
                        self._terminate_group(process)
                        return process.returncode, False, time.monotonic() - start
                    if now >= next_heartbeat:
                        self.queue.heartbeat(job["id"], self.worker_id)
                        next_heartbeat = now + self.heartbeat_seconds
                    if now - start >= self.timeout:
                        self._terminate_group(process)
                        return process.returncode, True, time.monotonic() - start
                    time.sleep(min(self.heartbeat_seconds, 0.25))
                return process.returncode, False, time.monotonic() - start
            finally:
                self.last_memory_report = memory_monitor.report()
                # Do not leave child processes consuming resources after success or failure.
                self._terminate_group(process)

    def _validate_report(self, report, profile, expected_sha=None, evaluator_sha256=None):
        benchmark = "feyer-lab-screen-v1" if profile == "screen" else "start-munich-2026-public-differometor-uifo-v2"
        if report.get("benchmark") != benchmark:
            raise ValueError("Report benchmark does not match evaluation profile")
        source = report.get("source", {})
        commit = source.get("commit")
        if not isinstance(commit, str) or re.fullmatch("[0-9a-f]{40}", commit) is None:
            raise ValueError("Report lacks a valid source commit")
        if expected_sha is not None and commit != expected_sha:
            raise ValueError("Report source commit does not match submitted candidate")
        if source.get("modified") is not False:
            raise ValueError("Report source checkout is not clean")
        if evaluator_sha256 is not None and report.get("starter_sha256") != evaluator_sha256:
            raise ValueError("Report evaluator digest does not match executed file")
        total = report.get("timing_seconds", {}).get("end_to_end")
        if not isinstance(total, (int, float)) or isinstance(total, bool) or not math.isfinite(total) or total <= 0:
            raise ValueError("Report does not contain a positive finite first-run timing")
        inputs = report.get("inputs", {})
        if inputs.get("frequency_count") != 101 or inputs.get("gradient_parameter_count") != 193:
            raise ValueError("Report does not cover all 101 frequencies and 193 design variables")
        if inputs.get("setup_sha256") != FIXTURE_SHA256 or inputs.get("reference_sha256") != REFERENCE_SHA256:
            raise ValueError("Report does not identify the canonical workload fixtures")
        environment = report.get("environment", {})
        if not (environment.get("backend") == "cpu" and environment.get("jax_enable_x64") is True
                and environment.get("persistent_compilation_cache") is False
                and environment.get("cpu_affinity_ids") == [self.cpu]):
            raise ValueError("Report does not match fixed CPU affinity, double precision and disabled compilation cache")
        if any(type(environment.get(key)) is not int or environment[key] != 1
               for key in ("cpu_affinity_count", "requested_logical_cpus")):
            raise ValueError("Report does not identify one requested and effective logical CPU")
        if environment.get("thread_limits") != {name: "1" for name in THREAD_VARIABLES}:
            raise ValueError("Report numerical-library thread limits differ from one")
        if environment.get("omp_num_threads") != "1" or environment.get("xla_flags") is not None:
            raise ValueError("Report has unexpected OpenMP or XLA configuration")
        if not str(environment.get("python", "")).startswith("3.12."):
            raise ValueError("Report did not use Python 3.12")
        phases = report.get("phases")
        if not isinstance(phases, list) or len(phases) != len(PHASE_CATEGORIES):
            raise ValueError("Report lacks the complete first-run phase schema")
        seen = set()
        for phase in phases:
            if not isinstance(phase, dict):
                raise ValueError("Report phase entries must be objects")
            key, seconds = phase.get("key"), phase.get("seconds")
            if key not in PHASE_CATEGORIES or key in seen or phase.get("category") != PHASE_CATEGORIES[key]:
                raise ValueError("Report has unknown, repeated or misclassified first-run phases")
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError("Report phase timing must be finite and nonnegative")
            seen.add(key)
        if not math.isclose(sum(p["seconds"] for p in phases), total, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("First-run total does not equal its phase timings")
        compiled = sum(p["seconds"] for p in phases if p["category"] == "compile")
        recorded_compilation = report.get("timing_seconds", {}).get("trace_lower_and_compile")
        if not isinstance(recorded_compilation, (int, float)) or not math.isclose(compiled, recorded_compilation, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("Compilation total does not equal its phase timings")
        validation = report.get("validation", {})
        if validation.get("output_dtypes") != {"carrier": "complex128", "signal": "complex128", "noise": "float64"}:
            raise ValueError("Physical outputs are not double precision")
        if validation.get("output_shapes") != {"carrier": [286, 1], "signal": [751, 101], "noise": [101]} or validation.get("gradient_shape") != [193]:
            raise ValueError("Report physical output or gradient shapes differ from the canonical workload")
        for key in ("gradient_norm", "loss", "max_absolute_log_sensitivity_error"):
            value = validation.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError("Report validation scalars must be finite numbers")
        if validation["gradient_norm"] <= 0 or not 0 <= validation["max_absolute_log_sensitivity_error"] <= 1e-5:
            raise ValueError("Report gradient is zero or sensitivity error exceeds official tolerance")
        if profile == "screen":
            if validation.get("passed") is not True:
                raise ValueError("Screening correctness checks did not pass")
        elif not (validation.get("all_outputs_and_gradients_finite") is True
                  and validation.get("upstream_sensitivity_check_passed") is True
                  and validation.get("gradient_check", {}).get("passed") is True):
            raise ValueError("Official correctness checks did not pass")
        return total

    def _run_claimed(self, job, lock_fd):
        run = self.runs_dir / job["id"]
        run.mkdir(exist_ok=False)
        code = run / "code"
        result = {"run_dir": str(run), "sha": job["sha"], "profile": job["profile"],
                  "cpu": self.cpu, "python": self.python_path, "platform": platform.platform(),
                  "official_passed": None, "regression_passed": None,
                  "resource_provenance": resource_snapshot(),
                  "memory_budget_bytes": self.memory_budget_bytes,
                  "evaluator_release": str(self.evaluator_root),
                  "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "baseline_sha": self.baseline_sha,
                  "artifacts": {name: str(run / name) for name in
                                ("report.json", "arrays.npz", "stdout.log", "time.txt")}}
        atomic_json(run / "job.json", job)
        status, error = "failed", None
        interrupted = None
        try:
            self._verify(job)
            self.queue._git("worktree", "add", "--detach", str(code), job["sha"])
            command, evaluator = self._build_command(job, code, run)
            result.update(command=command, evaluator_sha256=hashlib.sha256(evaluator.read_bytes()).hexdigest())
            execution_env = self._environment(code)
            result["execution_environment"] = {key: execution_env.get(key) for key in
                (*THREAD_VARIABLES, "JAX_PLATFORMS", "JAX_ENABLE_X64", "JAX_ENABLE_COMPILATION_CACHE", "XLA_FLAGS", "PYTHONNOUSERSITE")}
            atomic_json(run / "execution.json", result)
            returncode, timed_out, wall = self._execute(command, code, run / "stdout.log", job, lock_fd)
            result.update(returncode=returncode, wall_seconds=wall, peak_rss_kib=peak_rss_kib(run / "time.txt"))
            result["memory_monitoring"] = self.last_memory_report
            peak = result["peak_rss_kib"]
            memory_exceeded = self.last_memory_report.get("exceeded", False) or (peak is not None and peak * 1024 > self.memory_budget_bytes)
            if memory_exceeded:
                result["verdict"] = "resource_budget_exceeded"
                error = f"Evaluation exceeded the {self.memory_budget_bytes}-byte sampled RSS budget; this is not a kernel memory cap"
            elif timed_out:
                status, error = "timed_out", f"Evaluation exceeded {self.timeout:g} seconds"
            elif returncode:
                error = f"Evaluator exited with code {returncode}; see stdout.log"
            else:
                report = json.loads((run / "report.json").read_text())
                total = self._validate_report(report, job["profile"], expected_sha=job["sha"],
                                              evaluator_sha256=result["evaluator_sha256"])
                result.update(first_run_seconds=total, validation=report["validation"],
                              warm_median_seconds=report.get("timing_seconds", {}).get("runtime_median"),
                              official_passed=True if job["profile"] == "full" else None,
                              reported_environment=report["environment"],
                              validated_output_scope="last_warm_evaluation" if job["profile"] == "full" else "first_evaluation")
                if job["profile"] == "full" and self.compare_full:
                    comparison = self.evaluator_root / "compare_arrays.py"
                    if not comparison.is_file() or self.reference_arrays is None or not self.reference_arrays.is_file():
                        raise FileNotFoundError("Full evaluation requires trusted array comparison and reference arrays")
                    compare_command = [self.python_path, str(comparison), "--reference", str(self.reference_arrays),
                                       "--candidate", str(run / "arrays.npz"), "--output", str(run / "comparison.json")]
                    result["comparison_evaluator_sha256"] = hashlib.sha256(comparison.read_bytes()).hexdigest()
                    result["reference_arrays_sha256"] = hashlib.sha256(self.reference_arrays.read_bytes()).hexdigest()
                    rc, expired, wall = self._execute(compare_command, code, run / "comparison.log", job, lock_fd)
                    result["comparison"] = {"returncode": rc, "timed_out": expired, "wall_seconds": wall,
                                            "report": str(run / "comparison.json"),
                                            "memory_monitoring": self.last_memory_report}
                    comparison_report = None
                    try:
                        comparison_report = json.loads((run / "comparison.json").read_text())
                    except (OSError, ValueError):
                        pass
                    if self.last_memory_report.get("exceeded", False):
                        result["verdict"] = "resource_budget_exceeded"
                        error = f"Regression comparison exceeded the {self.memory_budget_bytes}-byte sampled RSS budget"
                    elif expired:
                        status, error = "timed_out", "Array comparison timed out"
                        result["verdict"] = "official_pass_regression_check_error"
                    elif rc:
                        numerical_failure = isinstance(comparison_report, dict) and comparison_report.get("passed") is False
                        result["regression_passed"] = False if numerical_failure else None
                        result["verdict"] = "official_pass_numerical_review_needed" if numerical_failure else "official_pass_regression_check_error"
                        error = ("Official benchmark passed, but strict baseline array comparison failed" if numerical_failure else
                                 "Official benchmark passed, but the regression checker did not produce a valid comparison")
                    elif not isinstance(comparison_report, dict) or comparison_report.get("passed") is not True:
                        result["verdict"] = "official_pass_regression_check_error"
                        error = "Regression checker exited successfully without an affirmative comparison report"
                    else:
                        result["regression_passed"] = True
                        status = "completed"
                else:
                    status = "completed"
                if status == "completed":
                    result["verdict"] = ("screened" if job["profile"] == "screen" else
                                         "validated" if result["regression_passed"] is True else "official_pass_only")
        except RejectedCandidate as exc:
            status, error = "rejected", str(exc)
        except (KeyboardInterrupt, SystemExit) as exc:
            status, error, interrupted = "interrupted", "Worker stopped during evaluation", exc
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            result.setdefault("peak_rss_kib", peak_rss_kib(run / "time.txt"))
            if code.exists():
                try:
                    self.queue._git("worktree", "remove", "--force", str(code))
                except subprocess.CalledProcessError as exc:
                    result["cleanup_error"] = str(exc)
            result["status"] = status
            if error:
                result["error"] = error
            atomic_json(run / "result.json", result)
            finished = self.queue.finish(job["id"], self.worker_id, status, result=result, error=error)
        if interrupted is not None:
            raise interrupted
        return finished

    def run_once(self):
        with self._lock() as lock_fd:
            self.queue.recover_stale(self.stale_seconds)
            job = self.queue.claim(self.worker_id)
            if job is None:
                return None
            return self._run_claimed(job, lock_fd)

    def run_forever(self, poll_seconds=3):
        # TERM follows the same cleanup path as Ctrl-C; existing results remain durable.
        old_term = signal.getsignal(signal.SIGTERM)
        def stop(_signum, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
        try:
            while True:
                try:
                    job = self.run_once()
                    if job is not None:
                        print(json.dumps({"id": job["id"], "status": job["status"], "error": job["error"]}), flush=True)
                except WorkerBusyError:
                    job = None
                if job is None:
                    time.sleep(poll_seconds)
        except KeyboardInterrupt:
            return
        finally:
            signal.signal(signal.SIGTERM, old_term)
