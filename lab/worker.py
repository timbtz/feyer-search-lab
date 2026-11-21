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

BASELINE_SHA = "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f"
PROTECTED_PATHS = ("benchmark.py", "plot_timings.py", "examples/data", "requirements.txt", "pyproject.toml", "setup.py")


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


class Worker:
    def __init__(self, queue: Queue, runs_dir, evaluator_root,
                 python_path="/workspace/venv-feyer/bin/python", cpu=2,
                 timeout=900, baseline_sha=BASELINE_SHA,
                 reference_arrays="/workspace/feyer-pristine/base1.npz",
                 heartbeat_seconds=5, stale_seconds=120, compare_full=True):
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
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        if self.timeout <= 0 or self.cpu < 0:
            raise ValueError("Positive timeout and nonnegative CPU required")

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
        with Path(log_path).open("w") as log:
            process = subprocess.Popen(command, cwd=code, env=self._environment(code),
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True, pass_fds=(lock_fd,))
            next_heartbeat = start
            try:
                while process.poll() is None:
                    now = time.monotonic()
                    if now >= next_heartbeat:
                        self.queue.heartbeat(job["id"], self.worker_id)
                        next_heartbeat = now + self.heartbeat_seconds
                    if now - start >= self.timeout:
                        self._terminate_group(process)
                        return process.returncode, True, time.monotonic() - start
                    time.sleep(min(self.heartbeat_seconds, 0.25))
                return process.returncode, False, time.monotonic() - start
            finally:
                # Do not leave child processes consuming resources after success or failure.
                self._terminate_group(process)

    def _validate_report(self, report, profile):
        total = report.get("timing_seconds", {}).get("end_to_end")
        if not isinstance(total, (int, float)) or isinstance(total, bool) or not math.isfinite(total) or total <= 0:
            raise ValueError("Report does not contain a positive finite first-run timing")
        inputs = report.get("inputs", {})
        if inputs.get("frequency_count") != 101 or inputs.get("gradient_parameter_count") != 193:
            raise ValueError("Report does not cover all 101 frequencies and 193 design variables")
        environment = report.get("environment", {})
        if not (environment.get("backend") == "cpu" and environment.get("jax_enable_x64") is True
                and environment.get("persistent_compilation_cache") is False
                and environment.get("cpu_affinity_ids") == [self.cpu]):
            raise ValueError("Report does not match fixed CPU affinity, double precision and disabled compilation cache")
        validation = report.get("validation", {})
        if validation.get("output_dtypes") != {"carrier": "complex128", "signal": "complex128", "noise": "float64"}:
            raise ValueError("Physical outputs are not double precision")
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
            atomic_json(run / "execution.json", result)
            returncode, timed_out, wall = self._execute(command, code, run / "stdout.log", job, lock_fd)
            result.update(returncode=returncode, wall_seconds=wall, peak_rss_kib=peak_rss_kib(run / "time.txt"))
            if timed_out:
                status, error = "timed_out", f"Evaluation exceeded {self.timeout:g} seconds"
            elif returncode:
                error = f"Evaluator exited with code {returncode}; see stdout.log"
            else:
                report = json.loads((run / "report.json").read_text())
                total = self._validate_report(report, job["profile"])
                result.update(first_run_seconds=total, validation=report["validation"],
                              warm_median_seconds=report.get("timing_seconds", {}).get("runtime_median"),
                              official_passed=job["profile"] == "full")
                if job["profile"] == "full" and self.compare_full:
                    comparison = self.evaluator_root / "compare_arrays.py"
                    if not comparison.is_file() or self.reference_arrays is None or not self.reference_arrays.is_file():
                        raise FileNotFoundError("Full evaluation requires trusted array comparison and reference arrays")
                    compare_command = [self.python_path, str(comparison), "--reference", str(self.reference_arrays),
                                       "--candidate", str(run / "arrays.npz"), "--output", str(run / "comparison.json")]
                    rc, expired, wall = self._execute(compare_command, code, run / "comparison.log", job, lock_fd)
                    result["comparison"] = {"returncode": rc, "timed_out": expired, "wall_seconds": wall,
                                            "report": str(run / "comparison.json")}
                    if expired:
                        status, error = "timed_out", "Array comparison timed out"
                    elif rc:
                        error = "Official benchmark passed, but strict baseline array comparison failed"
                    else:
                        status = "completed"
                else:
                    status = "completed"
                if status == "completed":
                    result["verdict"] = "screened" if job["profile"] == "screen" else "validated"
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
