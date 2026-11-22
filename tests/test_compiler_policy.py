import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from lab.compiler_policy import LEGACY, REVIEWED, flags_allowed, policy_digest
from lab.evolution_evidence import normalize_job, policy_from_job
from lab.worker import Worker
from tests.test_worker import valid_report
from tests.test_evolution_evidence import full_job


FLAGS = '--xla_backend_optimization_level=0 --xla_cpu_use_fusion_emitters=false'


def reviewed_job(flags=FLAGS):
    job = full_job()
    job['report.json']['environment']['xla_flags'] = flags
    job['result']['reported_environment'] = copy.deepcopy(job['report.json']['environment'])
    job['result'].update(compiler_policy=REVIEWED, compiler_policy_sha256=policy_digest(REVIEWED))
    return job


class CompilerPolicyTests(unittest.TestCase):
    def test_deploy_pins_explicit_policy_and_retains_running_worker_guard(self):
        from lab.deploy import deploy
        with tempfile.TemporaryDirectory() as tmp, patch('lab.deploy.git', return_value='a'*40), \
             patch('lab.deploy.subprocess.check_output', return_value=b'archive'), \
             patch('lab.deploy.subprocess.run') as run:
            record = deploy(Path(tmp), compiler_policy=REVIEWED)
            command = run.call_args_list[-1].args[0][-1]
            self.assertIn('--compiler-policy '+REVIEWED, command)
            self.assertIn('Worker already exists; release uploaded without switching it.', command)
            self.assertLess(command.index('exit 3'), command.index('ln -sfn'))
            self.assertEqual(record['compiler_policy_sha256'], policy_digest(REVIEWED))
            with self.assertRaises(ValueError): deploy(Path(tmp), compiler_policy='unknown')
            self.assertEqual(run.call_count, 3)

    def test_allowlist_does_not_accept_other_flags_or_duplicate_assignments(self):
        self.assertTrue(flags_allowed(FLAGS, REVIEWED))
        self.assertTrue(flags_allowed(None, REVIEWED))
        for value in ('', ' ', False, 3, '--xla_cpu_enable_fast_math=true',
                      FLAGS+' --xla_cpu_use_fusion_emitters=false',
                      FLAGS+' --xla_force_host_platform_device_count=8'):
            with self.subTest(value=value):
                self.assertFalse(flags_allowed(value, REVIEWED))
        self.assertFalse(flags_allowed(FLAGS, LEGACY))
        with self.assertRaises(ValueError): flags_allowed(None, 'unknown')

    def test_worker_policy_must_be_explicit_and_other_guards_remain(self):
        worker = Worker.__new__(Worker); worker.cpu = 2
        report = valid_report(); report['environment']['xla_flags'] = FLAGS
        with self.assertRaisesRegex(ValueError, 'XLA'): worker._validate_report(report, 'screen')
        worker.compiler_policy = REVIEWED
        worker._validate_report(report, 'screen')
        report['environment']['thread_limits']['OMP_NUM_THREADS'] = '2'
        with self.assertRaisesRegex(ValueError, 'thread'): worker._validate_report(report, 'screen')

    def test_worker_claim_cannot_self_authorize_consumption(self):
        job = reviewed_job()
        out = normalize_job(job)
        self.assertEqual(out['category'], 'infrastructure_error')
        self.assertFalse(out['eligible_full'])
        self.assertFalse(out['scientific_strike'])
        with self.assertRaises(ValueError): policy_from_job(job)

    def test_explicit_reviewed_policy_accepts_and_bootstraps_same_policy(self):
        job = reviewed_job()
        policy = {'compiler_policy': REVIEWED}
        out = normalize_job(job, policy_context=policy)
        self.assertTrue(out['eligible_full'], out['issues'])
        pinned = policy_from_job(job, policy_context=policy)
        self.assertEqual(pinned['compiler_policy'], REVIEWED)
        self.assertEqual(pinned['compiler_policy_sha256'], policy_digest(REVIEWED))
        self.assertTrue(normalize_job(job, policy_context=pinned)['eligible_full'])

    def test_missing_mismatched_and_forged_policy_receipts_fail_closed(self):
        for mutation in ('missing', 'digest', 'id', 'unknown_flag', 'launch_override'):
            job = reviewed_job()
            if mutation == 'missing': job['result'].pop('compiler_policy_sha256')
            if mutation == 'digest': job['result']['compiler_policy_sha256'] = 'f'*64
            if mutation == 'id': job['result']['compiler_policy'] = LEGACY
            if mutation == 'unknown_flag':
                job['report.json']['environment']['xla_flags'] += ' --xla_cpu_enable_fast_math=true'
                job['result']['reported_environment'] = copy.deepcopy(job['report.json']['environment'])
            if mutation == 'launch_override': job['result']['execution_environment']['XLA_FLAGS'] = FLAGS
            with self.subTest(mutation=mutation):
                out = normalize_job(job, policy_context={'compiler_policy': REVIEWED})
                self.assertFalse(out['eligible_full'])
                self.assertFalse(out['scientific_strike'])
                self.assertEqual(out['category'], 'infrastructure_error')

    def test_legacy_cohorts_stay_stable_and_reviewed_policy_is_distinct_without_flags(self):
        old = full_job(); explicit = copy.deepcopy(old)
        explicit['result'].update(compiler_policy=LEGACY, compiler_policy_sha256=policy_digest(LEGACY))
        self.assertEqual(normalize_job(old)['cohort_digest'], normalize_job(explicit)['cohort_digest'])
        new = normalize_job(reviewed_job(None), policy_context={'compiler_policy': REVIEWED})
        self.assertTrue(new['eligible_full'])
        self.assertNotEqual(new['cohort_digest'], normalize_job(old)['cohort_digest'])

    def test_compiler_policy_does_not_waive_strict_comparison(self):
        job = reviewed_job()
        job['status'] = job['result']['status'] = 'failed'
        job['result']['regression_passed'] = False
        job['result']['comparison']['returncode'] = 1
        job['comparison.json']['passed'] = False
        job['comparison.json']['checks']['gradient']['passed'] = False
        out = normalize_job(job, policy_context={'compiler_policy': REVIEWED})
        self.assertEqual(out['checks']['official'], 'passed')
        self.assertEqual(out['checks']['strict'], 'failed')
        self.assertFalse(out['eligible_full'])


if __name__ == '__main__':
    unittest.main()
