import argparse
import contextlib
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lab.dual_benchmark_worker import CASES
from lab.overnight_client import runner_request_for
from lab.overnight_finite import Controller, balanced_plan, scientifically_eligible, select_finalist
from lab.overnight_search import git, write_json


def feedback(request, grid=1.0, aligo=.5, valid=True):
    return {'request_id': request['request_id'], 'sha': request['sha'], 'status': 'completed',
            'official_passed': True, 'evaluation': {
                'registered_at': 1, 'started_at': 2, 'finished_at': 12,
                'checks': [{'setup': s, 'returncode': 0, 'failure': None, 'official': {'passed': True}, 'artifacts': {'passed': True}, 'strict_comparisons': {'initial_seed': {'passed': True}}}
                           for s in ('grid', 'aligo')],
                'generalization': {'comparisons': {'initial_seed': {'passed': valid, 'cases': [{'case': c, 'passed': True} for c in CASES]}},
                                   'artifacts': {'passed': True}, 'returncode': 0, 'failure': None},
                'timings': {s: {'fresh_process_seconds': [v]} for s, v in [('grid', grid), ('aligo', aligo)]}}}


class FakePublisher:
    def __init__(self):
        self.files = []

    def locked(self):
        return contextlib.nullcontext()

    def _recover(self):
        return None

    def _submit(self, identity, files):
        self.files.append(files)
        return {'published': True, 'evaluation_id': identity, 'commit_sha': 'f'*40}


class FakeClient:
    def __init__(self):
        self.requests = []

    def run(self, request):
        self.requests.append(request.copy())
        return feedback(request, .9 if request['branch'].endswith('01') else 1.0,
                        .45 if request['branch'].endswith('01') else .5)


class FiniteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.repo)], check=True)
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        git(self.repo, 'config', 'user.name', 'Test')
        (self.repo / 'differometor').mkdir()
        source = 'LAYOUT = 0\n'
        (self.repo / 'differometor/simulate.py').write_text(source)
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'seed')
        sha = git(self.repo, 'rev-parse', 'HEAD')
        patcher = patch('lab.overnight_finite.INITIAL_SEED', sha)
        patcher.start(); self.addCleanup(patcher.stop)
        self.manifest = {'version': 'exact-topology-finite-v1', 'parent_sha': sha,
            'base_sources': {'differometor/simulate.py': source}, 'dimensions': {'layout': [0, 1]},
            'defaults': {'layout': 0}, 'legal': [{'layout': 0}, {'layout': 1}],
            'replacements': [{'path': 'differometor/simulate.py', 'dimension': 'layout',
                              'anchor': 'LAYOUT = 0', 'values': {'0': 'LAYOUT = 0', '1': 'LAYOUT = 1'}}]}
        write_json(self.root / 'manifest.json', self.manifest)
        self.config = {'deadline_unix': 2000, 'publisher_worktree': str(self.root / 'control'),
                       'evidence_root': str(self.root / 'evidence')}
        write_json(self.root / 'client.json', self.config)
        receipt = {'candidate_sha': sha, 'admission': {'promotion_ready': True},
                   'benchmarks': {s: {'passed': True} for s in ('grid', 'aligo')},
                   'generalization': {'case_count': 14, 'seed_comparison_passed': True, 'all_finite': True,
                                      'inputs_identical': True, 'new_failures': []}}
        review = {'schema_version': 'feyer-local-source-review-v1', 'candidate_sha': sha, 'parent_sha': sha,
                  'approved': True, 'scope': 'no-fixture-specialization-and-integrity', 'review_kind': 'local-independent-source-and-integrity',
                  'reviewer': 'collaborating-agent:/root/dual_evaluator',
                  'diff_sha256': hashlib.sha256(b'').hexdigest()}
        write_json(self.root / 'seed.json', receipt)
        write_json(self.root / 'review.json', review)
        write_json(self.root / 'gate.json', {'ready': True, 'deadline_unix': 2000, 'seed_sha': sha,
            'seed_receipt_path': str(self.root / 'seed.json'), 'source_review_path': str(self.root / 'review.json')})
        self.args = argparse.Namespace(repo=str(self.repo), state_dir=str(self.root / 'state'),
            manifest=str(self.root / 'manifest.json'), client_config=str(self.root / 'client.json'),
            start_gate=str(self.root / 'gate.json'), deadline_unix=2000, max_jobs=8, confirmation_pairs=3,
            name='finite-test', resume=False)
        self.client, self.publisher = FakeClient(), FakePublisher()
        self.controller = Controller(self.args, self.client, self.publisher, clock=lambda: 1000)
        self.controller.push_choice = lambda choice: None

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_menu_and_balanced_same_sha_confirmations(self):
        self.controller.run()
        state = self.controller.state
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(len(state['screens']), 2)
        self.assertEqual(len(state['confirmations']), 6)
        self.assertEqual(state['job_count'], 8)
        self.assertEqual(len({r['request_id'] for r in self.client.requests}), 8)
        candidate = state['choices'][1]['sha']
        self.assertNotEqual(candidate, self.manifest['parent_sha'])
        self.assertEqual([r['sha'] for r in self.client.requests[2:]],
                         [self.manifest['parent_sha'], candidate, candidate, self.manifest['parent_sha'], self.manifest['parent_sha'], candidate])
        self.assertTrue(all(row['promoted'] is False for row in state['confirmations']))
        self.assertEqual(state['screens'][0]['execution_wall_seconds'], 10)
        self.assertEqual(state['screens'][0]['job_total_seconds'], 11)
        self.assertTrue(self.publisher.files)
        self.assertTrue(all('CURRENT_BEST' not in p for p in self.publisher.files[0]))
        self.assertEqual(self.controller.config['fresh_process_repetitions'], 1)
        self.assertIsNone(self.controller.config['source_review_command'])

    def test_pending_transport_failure_reuses_uuid(self):
        self.controller.initialize()
        choice = self.controller.state['choices'][0]
        self.controller.prepare_choice(choice)
        saved_run = self.client.run
        self.client.run = lambda request: (_ for _ in ()).throw(RuntimeError('transport lost'))
        with self.assertRaises(RuntimeError):
            self.controller.evaluate(choice, 'screen')
        identity = self.controller.state['active_request']['request']['request_id']
        self.client.run = saved_run
        self.controller.evaluate(choice, 'screen')
        self.assertEqual(self.client.requests[0]['request_id'], identity)
        self.assertEqual(self.controller.state['job_count'], 1)

    def test_no_forced_finalist_if_no_gain(self):
        self.client.run = lambda request: feedback(request)
        self.controller.run()
        self.assertEqual(self.controller.state['job_count'], 2)
        self.assertEqual(self.controller.state['plan'], [])
        self.assertEqual(self.controller.state['selection_outcome'], 'no_screen_candidate_meets_both_setup_thresholds')

    def test_failed_generalization_never_selects_fastest(self):
        rows = [{'choice_id': 'a', 'feedback': feedback({'request_id': 'a', 'sha': 'a'})},
                {'choice_id': 'b', 'feedback': feedback({'request_id': 'b', 'sha': 'b'}, .1, .1, False)}]
        self.assertIsNone(select_finalist(rows, 'a'))
        self.assertFalse(scientifically_eligible(rows[1]['feedback']))

    def test_missing_source_approval_blocks_every_job(self):
        p = self.root / 'review.json'
        review = json.loads(p.read_text()); review['approved'] = False; write_json(p, review)
        with self.assertRaisesRegex(ValueError, 'source approval'):
            self.controller.run()
        self.assertFalse(self.client.requests)

    def test_wrong_seed_evidence_blocks_materialization(self):
        p = self.root / 'seed.json'
        receipt = json.loads(p.read_text()); receipt['candidate_sha'] = 'f'*40; write_json(p, receipt)
        with self.assertRaisesRegex(ValueError, 'admission'):
            self.controller.run()
        self.assertFalse(self.client.requests)

    def test_deadline_stops_new_requests(self):
        self.controller.clock = lambda: 2001
        self.controller.run()
        self.assertEqual(self.controller.state['status'], 'budget_exhausted')
        self.assertFalse(self.client.requests)

    def test_resume_budget_and_manifest_immutable(self):
        self.controller.initialize()
        self.args.resume = True
        self.args.max_jobs = 9
        with self.assertRaisesRegex(ValueError, 'identical frozen'):
            Controller(self.args, self.client, self.publisher).initialize()


    def test_durable_identity_exists_before_client_call(self):
        original = self.client.run
        def inspect(request):
            durable = json.loads((self.root / 'state/state.json').read_text())
            self.assertEqual(durable['active_request']['request'], request)
            self.assertGreater(durable['job_count'], 0)
            return original(request)
        self.client.run = inspect
        self.controller.run()

    def test_publish_failure_resume_does_not_repeat_jobs(self):
        submit = self.publisher._submit
        self.publisher._submit = lambda *args: {'published': False}
        with self.assertRaisesRegex(RuntimeError, 'push remains pending'):
            self.controller.run()
        previous = [r['request_id'] for r in self.client.requests]
        frozen = self.controller.state['summary_payload']
        self.publisher._submit = submit
        self.args.resume = True
        resumed = Controller(self.args, self.client, self.publisher, clock=lambda: 1001)
        resumed.push_choice = lambda choice: None
        resumed.run()
        self.assertEqual(previous, [r['request_id'] for r in self.client.requests])
        self.assertEqual(resumed.state['summary_payload'], frozen)

    def test_frozen_sha_change_blocks_pending_retry(self):
        self.controller.initialize()
        choice = self.controller.state['choices'][0]
        self.controller.prepare_choice(choice)
        git(choice['worktree'], 'commit', '--allow-empty', '-m', 'external mutation')
        with self.assertRaisesRegex(ValueError, 'changed externally'):
            self.controller.prepare_choice(choice)
        self.assertFalse(self.client.requests)

    def test_every_per_request_scientific_guard_fails_closed(self):
        baseline = feedback({'request_id': 'x', 'sha': 'y'})
        mutations = [lambda v: v.update(official_passed=False),
            lambda v: v.update(status='failed'),
            lambda v: v['evaluation']['generalization']['comparisons']['initial_seed']['cases'][0].update(passed=False),
            lambda v: v['evaluation']['generalization']['comparisons']['initial_seed']['cases'][1].pop('passed'),
            lambda v: v['evaluation']['checks'][0]['official'].update(passed=False),
            lambda v: v['evaluation']['checks'][1]['artifacts'].update(passed=False),
            lambda v: v['evaluation']['checks'][0]['strict_comparisons']['initial_seed'].update(passed=False),
            lambda v: v['evaluation']['generalization']['comparisons']['initial_seed'].update(passed=False),
            lambda v: v['evaluation']['generalization']['comparisons']['initial_seed']['cases'].pop(),
            lambda v: v['evaluation']['generalization']['comparisons']['initial_seed']['cases'][0].update(case='wrong')]
        for mutation in mutations:
            value = copy.deepcopy(baseline); mutation(value)
            self.assertFalse(scientifically_eligible(value))

    def test_request_repetitions_override_is_trusted_config_only(self):
        request = {'request_id': 'a'*32, 'sha': 'b'*40, 'deadline_unix': 2000,
                   'branch': 'x', 'session': 's', 'lane': 0, 'fresh_process_repetitions': 5}
        self.assertEqual(runner_request_for(request)['fresh_process_repetitions'], 3)
        single = runner_request_for(request, {'fresh_process_repetitions': 1})
        self.assertEqual(single['fresh_process_repetitions'], 1)
        self.assertTrue(single['run_generalization'])
        for invalid in (True, 2, 0, '1'):
            with self.assertRaises(ValueError):
                runner_request_for(request, {'fresh_process_repetitions': invalid})


if __name__ == '__main__':
    unittest.main()
