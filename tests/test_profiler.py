import copy
import json
from pathlib import Path
import tempfile
import unittest

from lab.profiler import collect_profiles, feedback_profile, profile_job
from tests.test_evolution_evidence import full_job


class ProfilerTests(unittest.TestCase):
    def test_ranking_accounts_for_all_first_run_work_and_keeps_clocks_separate(self):
        job = full_job()
        result = profile_job(job, source='test receipt', instance='amd-test')
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['eligible_full'])
        self.assertEqual(len(result['phases']), 14)
        self.assertEqual(result['phases'][0]['key'], 'forward_compile')
        self.assertAlmostEqual(sum(p['share'] for p in result['phases']), 1)
        self.assertAlmostEqual(sum(p['seconds'] for p in result['groups']), result['first_run_seconds'])
        self.assertAlmostEqual(result['unattributed_seconds'], 0)
        self.assertEqual(result['job_wall_seconds'], 120)
        self.assertEqual(result['warm_timing']['runtime_median'], job['report.json']['timing_seconds']['runtime_median'])
        self.assertEqual(result['instance'], 'amd-test')
        self.assertEqual(result['source'], 'test receipt')
        self.assertIsNone(result['observed_at'])

    def test_hypothetical_halving_uses_total_objective(self):
        result = profile_job(full_job())
        phase = result['phases'][0]
        scenario = phase['halving']
        self.assertTrue(scenario['hypothetical'])
        self.assertAlmostEqual(scenario['saved_seconds'], phase['seconds'] / 2)
        self.assertAlmostEqual(scenario['predicted_total_seconds'], result['first_run_seconds'] - phase['seconds'] / 2)
        self.assertLess(scenario['speedup'], 2)

    def test_unmeasured_screen_warm_medians_are_null_not_errors(self):
        job = full_job()
        job['profile'] = job['result']['profile'] = 'screen'
        job['report.json']['timing_seconds'].update(runtime_median=None, runtime_min=None,
                                                    runtime_max=None, runtime_samples=[])
        result = profile_job(job)
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(result['warm_timing']['runtime_median'])
        self.assertFalse(result['eligible_full'])

    def test_profile_never_changes_input(self):
        job = full_job()
        original = copy.deepcopy(job)
        profile_job(job)
        self.assertEqual(job, original)

    def test_incomplete_provenance_can_explain_time_without_claiming_validation(self):
        job = full_job()
        del job['result']['worker_sha256']
        result = profile_job(job)
        self.assertEqual(result['status'], 'ok')
        self.assertFalse(result['eligible_full'])
        self.assertIsNone(result['cohort_digest'])
        self.assertTrue(result['validation']['issues'])

    def test_failure_and_screen_never_get_full_eligibility(self):
        for kind in ('strict', 'screen'):
            job = full_job()
            if kind == 'strict':
                job['status'] = job['result']['status'] = 'failed'
                job['comparison.json']['passed'] = False
                job['comparison.json']['checks']['gradient']['passed'] = False
                job['result']['regression_passed'] = False
                job['result']['comparison']['returncode'] = 1
            else:
                job['profile'] = job['result']['profile'] = 'screen'
            with self.subTest(kind=kind):
                result = profile_job(job)
                self.assertFalse(result['eligible_full'])
                self.assertEqual(result['status'], 'ok')

    def test_malformed_phases_fail_visibly_without_rankings(self):
        for kind in ('missing', 'duplicate', 'negative', 'nan', 'infinity', 'boolean', 'unknown', 'category', 'not_list', 'entry'):
            job = full_job()
            phases = job['report.json']['phases']
            if kind == 'missing': phases.pop()
            elif kind == 'duplicate': phases.append(copy.deepcopy(phases[0]))
            elif kind in ('negative', 'nan', 'infinity', 'boolean'):
                phases[0]['seconds'] = {'negative':-1, 'nan':float('nan'), 'infinity':float('inf'), 'boolean':True}[kind]
            elif kind == 'unknown': phases[0]['key'] = 'made_up'
            elif kind == 'category': phases[0]['category'] = 'execute'
            elif kind == 'not_list': job['report.json']['phases'] = {}
            elif kind == 'entry': phases[0] = None
            with self.subTest(kind=kind):
                result = profile_job(job)
                self.assertEqual(result['status'], 'invalid_report')
                self.assertTrue(result['issues'])
                self.assertEqual(result['phases'], [])
                self.assertFalse(result['eligible_full'])
                json.dumps(result, allow_nan=False)

    def test_total_and_accounting_reject_bad_values_and_expose_unattributed_time(self):
        for total in (0, -1, float('nan'), True, 1):
            job = full_job()
            job['report.json']['timing_seconds']['end_to_end'] = total
            with self.subTest(total=total):
                self.assertEqual(profile_job(job)['status'], 'invalid_report')
        job = full_job()
        job['report.json']['timing_seconds']['end_to_end'] += 2
        result = profile_job(job)
        self.assertEqual(result['status'], 'ok')
        self.assertAlmostEqual(result['unattributed_seconds'], 2)
        self.assertLess(result['phases'][-1]['cumulative_share'], 1)
        self.assertFalse(result['eligible_full'])

    def test_exact_sha_mismatch_is_not_attributed_to_candidate(self):
        job = full_job()
        job['report.json']['source']['commit'] = 'f' * 40
        result = profile_job(job)
        self.assertEqual(result['status'], 'invalid_report')
        self.assertFalse(result['eligible_full'])

    def test_cohorts_remain_distinct(self):
        first, second = full_job(), full_job()
        second['result']['worker_sha256'] = 'f' * 64
        self.assertNotEqual(profile_job(first)['cohort_digest'], profile_job(second)['cohort_digest'])

    def test_feedback_preserves_failed_full_and_separate_screen(self):
        screen, full = full_job(), full_job()
        screen['id'], screen['profile'] = 'screen-one', 'screen'
        full['status'] = 'failed'
        result = feedback_profile(dict(candidate_sha=full['sha'], screen=screen, full=full))
        self.assertEqual([x['profile'] for x in result['jobs']], ['screen', 'full'])
        self.assertFalse(any(x['eligible_full'] for x in result['jobs']))
        self.assertEqual(result['jobs'][1]['execution_status'], 'failed')
        mismatch = feedback_profile(dict(candidate_sha='f' * 40, full=full))
        self.assertEqual(mismatch['jobs'][0]['status'], 'invalid_report')

    def test_observation_time_comes_from_artifact(self):
        job = full_job()
        job.update(created_at=1, updated_at=2, finished_at=3)
        self.assertEqual(profile_job(job)['observed_at'], 3)

    def test_collection_deduplicates_and_reports_conflicting_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = root / '.lab/phase-ledger/a.json'
            b = root / 'experiments/runs/agent/candidate-01.json'
            a.parent.mkdir(parents=True)
            b.parent.mkdir(parents=True)
            job = full_job()
            a.write_text(json.dumps(job))
            b.write_text(json.dumps({'candidate_sha':job['sha'], 'full':job}))
            result = collect_profiles(root, worktrees=False)
            self.assertEqual(len(result['profiler_reports']), 1)
            self.assertEqual(result['profiler_reports'][0]['status'], 'ok')
            self.assertEqual(len(result['profiler_reports'][0]['sources']), 2)
            job['result']['wall_seconds'] = 122
            a.write_text(json.dumps(job))
            result = collect_profiles(root, worktrees=False)
            self.assertEqual(result['profiler_reports'][0]['status'], 'conflicting_artifacts')
            self.assertFalse(result['profiler_reports'][0]['eligible_full'])

    def test_archived_session_receipt_recovers_final_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.lab/sessions/agent/results/job-one'
            path.mkdir(parents=True)
            job = full_job()
            for key, name in (('result', 'result.json'), ('report.json', 'report.json'), ('comparison.json', 'comparison.json')):
                (path / name).write_text(json.dumps(job.pop(key)))
            job.update(status='running', result=None)
            (path / 'job.json').write_text(json.dumps(job))
            result = collect_profiles(root, worktrees=False)
            profile = result['profiler_reports'][0]
            self.assertTrue(profile['eligible_full'])
            self.assertEqual(profile['execution_status'], 'completed')

    def test_corrupt_source_is_reported_in_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.lab/phase-ledger/a.json'
            path.parent.mkdir(parents=True)
            path.write_text('{bad')
            result = collect_profiles(root, worktrees=False)
            self.assertEqual(result['profiler_reports'], [])
            self.assertEqual(len(result['issues']), 1)


if __name__ == '__main__':
    unittest.main()
