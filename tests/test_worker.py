import fcntl
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lab.queue import Queue
from lab.worker import (Worker, WorkerBusyError, peak_rss_kib, PHASE_CATEGORIES,
                        THREAD_VARIABLES, FIXTURE_SHA256, REFERENCE_SHA256, resource_snapshot)


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True, stderr=subprocess.PIPE).strip()


def valid_report(profile="screen"):
    phases = [{"key": key, "category": category, "seconds": 1.0}
              for key, category in PHASE_CATEGORIES.items()]
    return {"benchmark": "feyer-lab-screen-v1" if profile == "screen" else "start-munich-2026-public-differometor-uifo-v2",
            "source": {"commit": "a" * 40, "modified": False},
            "starter_sha256": "b" * 64,
            "timing_seconds": {"end_to_end": 14.0, "trace_lower_and_compile": 6.0},
            "phases": phases,
            "inputs": {"frequency_count": 101, "gradient_parameter_count": 193,
                       "setup_sha256": FIXTURE_SHA256, "reference_sha256": REFERENCE_SHA256},
            "environment": {"backend": "cpu", "jax_enable_x64": True,
                            "persistent_compilation_cache": False, "cpu_affinity_ids": [2],
                            "cpu_affinity_count": 1, "requested_logical_cpus": 1,
                            "thread_limits": {key: "1" for key in THREAD_VARIABLES},
                            "omp_num_threads": "1", "xla_flags": None, "python": "3.12.15"},
            "validation": {"passed": True, "all_outputs_and_gradients_finite": True,
                           "upstream_sensitivity_check_passed": True, "gradient_check": {"passed": True},
                           "output_shapes": {"carrier": [286, 1], "signal": [751, 101], "noise": [101]},
                           "gradient_shape": [193], "gradient_norm": 1.0, "loss": 0.0,
                           "max_absolute_log_sensitivity_error": 1e-6,
                           "output_dtypes": {"carrier": "complex128", "signal": "complex128", "noise": "float64"}}}


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
report=make_report()
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
        prefix = "import json,hashlib,subprocess\nfrom pathlib import Path\n"
        prefix += "def make_report():\n"
        prefix += f"    report=json.loads({json.dumps(valid_report())!r})\n"
        prefix += "    report['source']['commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()\n"
        prefix += "    report['starter_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()\n"
        prefix += "    return report\n"
        (self.evaluators / "fake.py").write_text(prefix + source)

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
        self.assertIn("benchmark", result["error"])

    def test_full_requires_all_official_validation_flags(self):
        self.write_evaluator("""
import json,sys
from pathlib import Path
report=make_report()
report['benchmark']='start-munich-2026-public-differometor-uifo-v2'
report['validation']['gradient_check']['passed']=False
(Path(sys.argv[1])/'report.json').write_text(json.dumps(report))
""")
        self.submit(profile="full")
        self.assertEqual(self.worker.run_once()["status"], "failed")

    def test_full_comparison_failure_keeps_official_passed_evidence(self):
        self.write_evaluator("""
import json,sys
from pathlib import Path
run=Path(sys.argv[1])
report=make_report()
report['benchmark']='start-munich-2026-public-differometor-uifo-v2'
(run/'report.json').write_text(json.dumps(report))
""")
        (self.evaluators / "compare_arrays.py").write_text("import sys; from pathlib import Path; Path(sys.argv[sys.argv.index('--output')+1]).write_text('{\"passed\": false}'); raise SystemExit(1)\n")
        reference = self.root / "reference.npz"
        reference.touch()
        self.worker.reference_arrays = reference
        self.worker.compare_full = True
        self.submit(profile="full")
        result = self.worker.run_once()
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["result"]["official_passed"])
        self.assertFalse(result["result"]["regression_passed"])
        self.assertEqual(result["result"]["verdict"], "official_pass_numerical_review_needed")
        self.assertEqual(result["result"]["comparison"]["returncode"], 1)

    def test_rejects_smaller_workloads_and_changed_cpu_or_precision(self):
        report = valid_report()
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

    def test_rejects_wrong_sha_dirty_source_and_evaluator_digest(self):
        for field, value in (("commit", "c" * 40), ("modified", True)):
            report = valid_report()
            report['source'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.worker._validate_report(report, 'screen', expected_sha='a' * 40)
        with self.assertRaisesRegex(ValueError, 'digest'):
            self.worker._validate_report(valid_report(), 'screen', evaluator_sha256='c' * 64)

    def test_rejects_library_thread_drift_and_inconsistent_totals(self):
        report = valid_report()
        report['environment']['thread_limits']['OPENBLAS_NUM_THREADS'] = '16'
        with self.assertRaisesRegex(ValueError, 'thread limits'):
            self.worker._validate_report(report, 'screen')
        for field in ('end_to_end', 'trace_lower_and_compile'):
            report = valid_report()
            report['timing_seconds'][field] = .001
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'phase timings'):
                self.worker._validate_report(report, 'screen')

    def test_rejects_missing_duplicate_negative_and_nan_phases(self):
        for mutation in ('missing', 'duplicate', 'negative', 'nan'):
            report = valid_report()
            if mutation == 'missing': report['phases'].pop()
            elif mutation == 'duplicate': report['phases'][1] = dict(report['phases'][0])
            else: report['phases'][0]['seconds'] = -1 if mutation == 'negative' else float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.worker._validate_report(report, 'screen')

    def test_accepts_only_reviewed_package_xla_flags(self):
        accepted = ["--xla_backend_optimization_level=0 --xla_cpu_use_fusion_emitters=false",
                    "--xla_cpu_use_fusion_emitters=false"]
        for flags in accepted:
            with self.subTest(flags=flags):
                report = valid_report()
                report["environment"]["xla_flags"] = flags
                self.worker._validate_report(report, 'screen')
        rejected = ["", "--xla_force_host_platform_device_count=8",
                    "--xla_backend_optimization_level=0 --xla_cpu_enable_fast_math=true", 3]
        for flags in rejected:
            with self.subTest(flags=flags):
                report = valid_report()
                report["environment"]["xla_flags"] = flags
                with self.assertRaisesRegex(ValueError, "unexpected OpenMP or XLA"):
                    self.worker._validate_report(report, 'screen')

    def test_environment_removes_inherited_jax_and_xla_overrides(self):
        with patch.dict('os.environ', {'JAX_DISABLE_JIT': 'true', 'XLA_FLAGS': '--unexpected',
                                      'JAX_COMPILATION_CACHE_DIR': '/tmp/cache'}):
            env = self.worker._environment(self.repo)
        self.assertNotIn('JAX_DISABLE_JIT', env)
        self.assertNotIn('XLA_FLAGS', env)
        self.assertNotIn('JAX_COMPILATION_CACHE_DIR', env)
        self.assertEqual(env['JAX_ENABLE_COMPILATION_CACHE'], 'false')

    def test_resource_metadata_does_not_claim_a_per_job_memory_cap(self):
        result = resource_snapshot()
        self.assertFalse(result['per_job_memory_limit_enforced'])
        self.assertIn('memory.max', result['container_limits'])

    def test_gnu_time_peak_above_budget_is_rejected(self):
        self.worker.memory_budget_bytes = 100
        self.submit()
        with patch('lab.worker.MemoryMonitor') as monitor:
            monitor.return_value.sample.return_value = False
            monitor.return_value.report.return_value = {'exceeded': False}
            result = self.worker.run_once()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['result']['verdict'], 'resource_budget_exceeded')

    def test_sampled_memory_excess_stops_process_and_records_failure(self):
        self.write_evaluator('import time; time.sleep(60)\n')
        self.submit()
        with patch('lab.worker.MemoryMonitor') as monitor:
            monitor.return_value.sample.return_value = True
            monitor.return_value.report.return_value = {'exceeded': True}
            result = self.worker.run_once()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['result']['verdict'], 'resource_budget_exceeded')
        self.assertTrue(result['result']['memory_monitoring']['exceeded'])

    def test_rejects_invalid_validation_scalars_and_boolean_cpu_counts(self):
        for field, value in (('gradient_norm', 0), ('loss', float('nan')),
                             ('max_absolute_log_sensitivity_error', 2e-5)):
            report = valid_report()
            report['validation'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.worker._validate_report(report, 'screen')
        report = valid_report()
        report['environment']['requested_logical_cpus'] = True
        with self.assertRaises(ValueError):
            self.worker._validate_report(report, 'screen')


if __name__ == "__main__":
    unittest.main()
