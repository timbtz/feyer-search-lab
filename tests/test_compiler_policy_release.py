import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lab.compiler_policy import LEGACY, REVIEWED, flags_allowed, policy_digest
from lab.worker import Worker
from lab.deploy import deploy
from tests.test_worker import valid_report
from tests import test_worker as fixture_module

FLAGS = '--xla_backend_optimization_level=0 --xla_cpu_use_fusion_emitters=false'


class CompilerReleaseTests(unittest.TestCase):
    def test_only_reviewed_flags_under_explicit_policy(self):
        worker = Worker.__new__(Worker); worker.cpu = 2
        report = valid_report(); report['environment']['xla_flags'] = FLAGS
        with self.assertRaisesRegex(ValueError, 'XLA'): worker._validate_report(report, 'screen')
        worker.compiler_policy = REVIEWED
        worker._validate_report(report, 'screen')
        for value in ('', False, FLAGS+' --xla_cpu_enable_fast_math=true', FLAGS+' --xla_cpu_use_fusion_emitters=false'):
            self.assertFalse(flags_allowed(value, REVIEWED))
        self.assertFalse(flags_allowed(FLAGS, LEGACY))
        report['environment']['thread_limits']['OMP_NUM_THREADS'] = '2'
        with self.assertRaisesRegex(ValueError, 'thread'): worker._validate_report(report, 'screen')

    def test_actual_worker_receipt_and_sanitized_launch(self):
        fixture = fixture_module.WorkerTests()
        fixture.setUp()
        try:
            fixture.worker.compiler_policy = REVIEWED
            fixture.write_evaluator("""
import json, sys
from pathlib import Path
run=Path(sys.argv[1])
report=make_report()
report['environment']['xla_flags']='--xla_backend_optimization_level=0 --xla_cpu_use_fusion_emitters=false'
(run/'report.json').write_text(json.dumps(report))
(run/'time.txt').write_text('Maximum resident set size (kbytes): 12345\\n')
""")
            fixture.submit()
            result = fixture.worker.run_once()
            self.assertEqual(result['status'], 'completed')
            result = result['result']
            self.assertEqual(result['compiler_policy'], REVIEWED)
            self.assertEqual(result['compiler_policy_sha256'], policy_digest(REVIEWED))
            self.assertIsNone(result['execution_environment']['XLA_FLAGS'])
            self.assertEqual(result['reported_environment']['xla_flags'], FLAGS)
        finally:
            fixture.tearDown()

    def test_deploy_retains_live_worker_guard_and_records_policy(self):
        with tempfile.TemporaryDirectory() as tmp, patch('lab.deploy.git',return_value='a'*40), \
             patch('lab.deploy.subprocess.check_output',return_value=b'archive'), \
             patch('lab.deploy.subprocess.run') as run:
            receipt = deploy(Path(tmp),compiler_policy=REVIEWED)
            command = run.call_args_list[-1].args[0][-1]
            self.assertIn('--compiler-policy '+REVIEWED, command)
            self.assertLess(command.index('exit 3'),command.index('ln -sfn'))
            self.assertEqual(receipt['compiler_policy_sha256'],policy_digest(REVIEWED))
            with self.assertRaises(ValueError): deploy(Path(tmp),compiler_policy='unknown')
            self.assertEqual(run.call_count,3)


if __name__ == '__main__':
    unittest.main()
