import fcntl
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lab.queue import Queue
from lab.worker import Worker, WorkerBusyError, peak_rss_kib


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True, stderr=subprocess.PIPE).strip()


class FakeWorker(Worker):
    """Exercise the real lifecycle without Linux-only taskset or JAX."""
    def _build_command(self, job, code, run):
        evaluator = self.evaluator_root / "fake.py"
        return [sys.executable, str(evaluator), str(run)], evaluator


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "benchmark.py").write_text("# protected\n")
        (self.repo / "differometor").mkdir()
        (self.repo / "differometor/simulate.py").write_text("# original\n")
        (self.repo / "examples/data").mkdir(parents=True)
        (self.repo / "examples/data/reference.json").write_text("{}\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "baseline")
        self.baseline = git(self.repo, "rev-parse", "HEAD")
        self.queue = Queue(self.root / "state", self.repo)
        self.evaluators = self.root / "evaluators"
        self.evaluators.mkdir()
        self.write_evaluator("""
import json, sys
from pathlib import Path
run=Path(sys.argv[1])
report={'timing_seconds':{'end_to_end':1.25},'inputs':{'frequency_count':101,'gradient_parameter_count':193},'environment':{'backend':'cpu','jax_enable_x64':True,'persistent_compilation_cache':False,'cpu_affinity_ids':[2]},'validation':{'passed':True,'output_dtypes':{'carrier':'complex128','signal':'complex128','noise':'float64'}}}
(run/'report.json').write_text(json.dumps(report))
(run/'time.txt').write_text('Maximum resident set size (kbytes): 12345\\n')
print('evaluation completed')
""")
        self.worker = FakeWorker(self.queue, self.root / "runs", self.evaluators,
                                 python_path=sys.executable, baseline_sha=self.baseline,
                                 timeout=5, heartbeat_seconds=0.05, compare_full=False)

    def tearDown(self):
        self.temp.cleanup()

    def write_evaluator(self, source):
        (self.evaluators / "fake.py").write_text(source)

    def submit(self, profile="screen"):
        return self.queue.enqueue(git(self.repo, "rev-parse", "HEAD"), "main", "a", "direction", profile=profile)

    def test_success_retains_reports_cleans_checkout_and_records_verdict(self):
        job = self.submit()
        result = self.worker.run_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"]["verdict"], "screened")
        self.assertEqual(result["result"]["peak_rss_kib"], 12345)
        run = self.root / "runs" / job["id"]
        self.assertTrue((run / "report.json").is_file())
        self.assertTrue((run / "result.json").is_file())
        self.assertFalse((run / "code").exists())
        self.assertEqual(len(git(self.repo, "worktree", "list", "--porcelain").split("worktree ")) - 1, 1)

    def test_rejects_protected_file_tampering_before_execution(self):
        (self.repo / "benchmark.py").write_text("# changed\n")
        git(self.repo, "commit", "-am", "tamper")
        job = self.submit()
        result = self.worker.run_once()
        self.assertEqual(result["status"], "rejected")
        self.assertIn("benchmark.py", result["error"])
        self.assertFalse((self.root / "runs" / job["id"] / "stdout.log").exists())

    def test_rejects_moved_candidate_ref(self):
        job = self.submit()
        (self.repo / "differometor/simulate.py").write_text("# next\n")
        git(self.repo, "commit", "-am", "next")
        git(self.repo, "update-ref", f"refs/candidates/{job['id']}", "HEAD")
        self.assertEqual(self.worker.run_once()["status"], "rejected")

    def test_exclusive_worker_lock_does_not_claim_job(self):
        job = self.submit()
        with (self.queue.state_dir / "worker.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(WorkerBusyError):
                self.worker.run_once()
            self.assertEqual(self.queue.get(job["id"])["status"], "queued")

    def test_timeout_terminates_process_group_and_records_failure(self):
        self.write_evaluator("""
import signal, subprocess, sys, time
from pathlib import Path
run=Path(sys.argv[1])
child='import signal,time,sys; from pathlib import Path; signal.signal(signal.SIGTERM,lambda *args:(Path(sys.argv[1]).write_text("terminated"),sys.exit(0))); Path(sys.argv[2]).write_text("ready"); time.sleep(60)'
p=subprocess.Popen([sys.executable,'-c',child,str(run/'child-stopped'),str(run/'child-ready')])
def stop(*args):
    p.wait(timeout=1)
    sys.exit(0)
signal.signal(signal.SIGTERM,stop)
time.sleep(60)
""")
        self.worker.timeout = 1
        job = self.submit()
        result = self.worker.run_once()
        self.assertEqual(result["status"], "timed_out")
        run = self.root / "runs" / job["id"]
        self.assertTrue((run / "child-ready").is_file())
        self.assertTrue((run / "child-stopped").is_file())
        self.assertFalse((run / "code").exists())

    def test_nonzero_exit_and_bad_report_are_failures(self):
        self.write_evaluator("raise RuntimeError('broken candidate')\n")
        self.submit()
        self.assertEqual(self.worker.run_once()["status"], "failed")
        self.write_evaluator("import sys; from pathlib import Path; (Path(sys.argv[1])/'report.json').write_text('{}')\n")
        self.submit()
        result = self.worker.run_once()
        self.assertEqual(result["status"], "failed")
        self.assertIn("timing", result["error"])

    def test_full_requires_all_official_validation_flags(self):
        self.submit(profile="full")
        self.assertEqual(self.worker.run_once()["status"], "failed")

    def test_full_comparison_failure_keeps_official_passed_evidence(self):
        self.write_evaluator("""
import json,sys
from pathlib import Path
run=Path(sys.argv[1])
report={'timing_seconds':{'end_to_end':1.0},'inputs':{'frequency_count':101,'gradient_parameter_count':193},'environment':{'backend':'cpu','jax_enable_x64':True,'persistent_compilation_cache':False,'cpu_affinity_ids':[2]},'validation':{'all_outputs_and_gradients_finite':True,'upstream_sensitivity_check_passed':True,'gradient_check':{'passed':True},'output_dtypes':{'carrier':'complex128','signal':'complex128','noise':'float64'}}}
(run/'report.json').write_text(json.dumps(report))
""")
        (self.evaluators / "compare_arrays.py").write_text("raise SystemExit(1)\n")
        reference = self.root / "reference.npz"
        reference.touch()
        self.worker.reference_arrays = reference
        self.worker.compare_full = True
        self.submit(profile="full")
        result = self.worker.run_once()
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["result"]["official_passed"])
        self.assertEqual(result["result"]["comparison"]["returncode"], 1)

    def test_rejects_smaller_workloads_and_changed_cpu_or_precision(self):
        report = {'timing_seconds': {'end_to_end': 1},
                  'inputs': {'frequency_count': 101, 'gradient_parameter_count': 193},
                  'environment': {'backend': 'cpu', 'jax_enable_x64': True,
                                  'persistent_compilation_cache': False, 'cpu_affinity_ids': [2]},
                  'validation': {'passed': True, 'output_dtypes': {
                      'carrier': 'complex128', 'signal': 'complex128', 'noise': 'float64'}}}
        for section, field, invalid in [('inputs', 'frequency_count', 3),
                                         ('inputs', 'gradient_parameter_count', 1),
                                         ('environment', 'cpu_affinity_ids', [2, 3]),
                                         ('environment', 'jax_enable_x64', False),
                                         ('environment', 'persistent_compilation_cache', True),
                                         ('validation', 'output_dtypes', {'noise': 'float32'})]:
            modified = json.loads(json.dumps(report))
            modified[section][field] = invalid
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.worker._validate_report(modified, 'screen')


if __name__ == "__main__":
    unittest.main()
