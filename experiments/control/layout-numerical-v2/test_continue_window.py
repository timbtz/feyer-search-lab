import importlib.util
from pathlib import Path
import unittest
import copy
from tests.test_evolution_evidence import full_job
from lab.evolution_evidence import normalize_job, policy_from_job

spec = importlib.util.spec_from_file_location('continue_window', Path(__file__).with_name('continue_window.py'))
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


class WindowTests(unittest.TestCase):
    def test_imports_do_not_consume_jobs_but_reservations_do(self):
        snapshot = {'evaluations': [{'imported': True}, {'imported': False}, {'imported': False, 'job_id': None}]}
        self.assertEqual(window.new_evaluations(snapshot), 2)

    def test_global_repeat_ceiling_and_exact_deadline_are_independent(self):
        self.assertTrue(window.can_reserve(26, 13, 99, 100))
        self.assertFalse(window.can_reserve(26, 14, 99, 100))
        self.assertFalse(window.can_reserve(39, 1, 99, 100))
        self.assertFalse(window.can_reserve(26, 0, 100, 100))

    def test_repeat_requires_same_commit_source_and_cohort(self):
        job = full_job()
        policy = policy_from_job(job)
        cohort = normalize_job(job)['cohort_digest']
        target = {'sha': job['sha'], 'source_hashes': job['report.json']['source']['simulator_files_sha256']}
        self.assertTrue(window.inspect_result(job, target, policy, cohort)['eligible_full'])
        with self.assertRaisesRegex(ValueError, 'cohort'):
            window.inspect_result(job, target, policy, 'different')
        changed = copy.deepcopy(job)
        changed['report.json']['source']['simulator_files_sha256']['differometor/simulate.py'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'source map'):
            window.inspect_result(changed, target, policy, cohort)
        changed['sha'] = 'b' * 40
        with self.assertRaises(ValueError):
            window.inspect_result(changed, target, policy, cohort)


if __name__ == '__main__':
    unittest.main()
