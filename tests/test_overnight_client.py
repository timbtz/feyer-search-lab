import json
import contextlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lab.overnight_client import Client, atomic_bytes, immutable, relative, runner_request_for, sha256, validate_request
from lab.overnight_search import git


class Publisher:
    def __init__(self):
        self.calls = []
        self.fail = False

    def publish(self, path):
        self.calls.append(json.loads(Path(path).read_text()))
        return {'published': not self.fail, 'decision': {'promote': False}, 'commit_sha': 'f' * 40}


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        subprocess.run(['git', 'init', '-q', '-b', 'explore/test', str(self.repo)], check=True)
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        git(self.repo, 'config', 'user.name', 'Test')
        (self.repo / 'differometor').mkdir()
        (self.repo / 'differometor/a.py').write_text('value=1\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'seed')
        self.seed = git(self.repo, 'rev-parse', 'HEAD')
        self.patch = patch('lab.overnight_client.SEED', self.seed)
        self.patch.start()
        (self.repo / 'differometor/a.py').write_text('value=2\n')
        git(self.repo, 'commit', '-qam', 'candidate')
        self.sha = git(self.repo, 'rev-parse', 'HEAD')
        self.config = {'ssh_host': 'amd-hackathon', 'remote_runtime': str(self.root / 'runtime'),
                       'remote_root': str(self.root / 'remote'), 'mirror': str(self.root / 'mirror.git'),
                       'deadline_unix': 2000, 'evidence_root': str(self.root / 'evidence'),
                       'publisher_worktree': str(self.root / 'publisher'), 'campaign_dir': str(self.root / 'campaign')}
        self.request = {'request_id': 'a' * 32, 'sha': self.sha, 'parent_sha': self.seed,
                        'deadline_unix': 2000, 'branch': 'explore/test', 'session': 'lane0', 'lane': 0,
                        'worktree': str(self.repo)}
        self.publisher = Publisher()
        self.client = Client(self.config, publisher=self.publisher, clock=lambda: 1000, sleep=lambda _: None)
        self.uploads, self.launches, self.calls = [], [], []
        self.client.upload = lambda req, directory: self.uploads.append(req) or {'uploaded': True}
        self.client.collect_logs = lambda request, directory: None
        self.client.launch = lambda identity: self.launches.append(identity)
        self.files = {}
        self.receipt_path = 'requests/' + 'a'*32 + '/receipt.json'
        self.receipt = {'schema_version': 'feyer-overnight-evaluation-v1', 'evaluation_id': 'a'*32,
                        'candidate_sha': self.sha, 'benchmarks': {}, 'generalization': {},
                        'admission': {'promotion_ready': False, 'candidate_sha': self.sha}}
        self.files[self.receipt_path] = immutable(self.receipt)
        self.terminal = {'request_id': 'a'*32, 'sha': self.sha, 'status': 'completed',
                         'official_passed': True, 'receipt_path': self.receipt_path,
                         'receipt_sha256': sha256(self.files[self.receipt_path])}
        self.statuses = [{'request_id': 'a'*32, 'sha': self.sha, 'status': 'queued'}, self.terminal]
        def runner(command, identity=None, value=None):
            self.calls.append((command, identity, value))
            return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        self.client.call_runner = runner
        self.client.remote = lambda argv, stdin=None: self.files[argv[-1]]

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_full_flow_filters_payload_and_preserves_raw_receipt(self):
        result = self.client.run(self.request)
        self.assertTrue(result['official_passed'])
        self.assertFalse(result['confirmed_improvement'])
        self.assertEqual(self.launches, ['a'*32])
        registered = self.calls[0][2]
        self.assertEqual(registered['fresh_process_repetitions'], 3)
        self.assertTrue(registered['run_generalization'])
        self.assertEqual(registered['lane'], '0')
        self.assertNotIn('worktree', registered)
        self.assertEqual((Path(self.config['evidence_root']) / self.receipt_path).read_bytes(), self.files[self.receipt_path])
        self.assertTrue(self.publisher.calls[0]['requires_source_review'])
        again = self.client.run(self.request)
        self.assertEqual(again, result)
        self.assertEqual(len(self.uploads), 1)

    def test_lost_registration_response_reuses_same_identity(self):
        original = self.client.call_runner
        failed = [False]
        def runner(command, identity=None, value=None):
            if not failed[0]:
                failed[0] = True
                raise RuntimeError('SSH response lost after registration')
            return original(command, identity, value)
        self.client.call_runner = runner
        with self.assertRaises(RuntimeError):
            self.client.run(self.request)
        self.client.run(self.request)
        self.assertEqual(len(self.uploads), 1)
        self.assertEqual(self.calls[0][2]['request_id'], self.request['request_id'])

    def test_running_orphan_is_probed_and_preserved_as_interrupted(self):
        self.statuses = [{'request_id': 'a'*32, 'sha': self.sha, 'status': 'running'},
                         {'request_id': 'a'*32, 'sha': self.sha, 'status': 'interrupted',
                          'official_passed': None, 'error': 'Lost owner; never reexecuted'}]
        result = self.client.run(self.request)
        self.assertEqual(self.launches, ['a'*32])
        self.assertEqual(result['status'], 'interrupted')
        self.assertFalse(result['official_passed'])

    def test_pending_publication_retries_without_rerun(self):
        self.publisher.fail = True
        with self.assertRaisesRegex(RuntimeError, 'Publication pending'):
            self.client.run(self.request)
        self.publisher.fail = False
        self.client.run(self.request)
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(len(self.uploads), 1)
        self.assertEqual(self.publisher.calls[0], self.publisher.calls[1])

    def test_terminal_receipt_race_retries_instead_of_false_failure(self):
        self.statuses = [{key: value for key, value in self.terminal.items() if not key.startswith('receipt_')}]
        with self.assertRaisesRegex(RuntimeError, 'awaiting'):
            self.client.run(self.request)
        self.assertFalse(self.publisher.calls)

    def test_remote_report_hash_mismatch_blocks_publication(self):
        self.files[self.receipt_path] += b' '
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.client.run(self.request)
        self.assertFalse(self.publisher.calls)

    def test_mismatched_remote_identity_is_rejected(self):
        self.statuses = [{**self.terminal, 'sha': 'f'*40}]
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.client.run(self.request)

    def test_new_request_past_deadline_never_uploads(self):
        self.client.clock = lambda: 2001
        self.assertEqual(self.client.run(self.request)['status'], 'expired')
        self.assertFalse(self.uploads)

    def test_pending_request_immutable_after_network_failure(self):
        self.client.call_runner = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('offline'))
        with self.assertRaises(RuntimeError):
            self.client.run(self.request)
        self.request['session'] = 'other'
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.client.run(self.request)

    def test_failed_early_run_publishes_failure_evidence(self):
        self.statuses = [{'request_id': 'a'*32, 'sha': self.sha, 'status': 'failed', 'official_passed': None,
                          'error': 'Resource failure'}]
        result = self.client.run(self.request)
        self.assertFalse(result['official_passed'])
        self.assertIn('failure', self.publisher.calls[0])

    def test_download_is_atomic_and_partial_temp_is_recoverable(self):
        path = Path(self.config['evidence_root']) / self.receipt_path
        path.parent.mkdir(parents=True)
        path.with_suffix('.json.download').write_bytes(b'partial')
        self.client.fetch_file(self.receipt_path, self.terminal['receipt_sha256'])
        self.assertEqual(path.read_bytes(), self.files[self.receipt_path])
        self.files[self.receipt_path] = b'different'
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.client.fetch_file(self.receipt_path)

    def test_bundle_upload_real_git_preserves_exact_sha(self):
        mirror = Path(self.config['mirror'])
        subprocess.run(['git', 'clone', '-q', '--bare', str(self.repo), str(mirror)], check=True)
        self.client.remote = lambda argv, stdin=None: subprocess.check_output(argv, input=stdin)
        directory = self.root / 'transport'
        directory.mkdir()
        result = Client.upload(self.client, self.request, directory)
        self.assertEqual(len(result['bundle_sha256']), 64)
        self.assertEqual(git(mirror, 'rev-parse', 'refs/candidates/overnight-'+'a'*32), self.sha)
        self.assertFalse((directory / 'candidate.bundle').exists())
        self.assertEqual(git(self.repo, 'for-each-ref', '--format=%(refname)', 'refs/lab/overnight-export'), '')

    def test_request_rejects_nonfinite_deadline_wrong_branch(self):
        for change in ({'deadline_unix': float('nan')}, {'request_id': '../oops'}, {'branch': 'wrong'}):
            with self.assertRaises(ValueError):
                validate_request({**self.request, **change}, self.config)

    def test_relative_evidence_paths_reject_traversal(self):
        for value in ('/etc/passwd', '../outside', 'requests/../../outside'):
            with self.assertRaises(ValueError):
                relative(value)

    def test_real_runner_request_contract_when_integrated(self):
        try:
            from lab.dual_benchmark_worker import normalize_request
        except ImportError:
            self.skipTest('Dual runner is integrated by the coordinating maintainer')
        normalized = normalize_request(runner_request_for(self.request))
        self.assertEqual(normalized['lane'], '0')
        self.assertEqual(normalized['fresh_process_repetitions'], 3)

    def test_review_hook_uses_whole_seed_delta_and_durable_envelope(self):
        directory = Path(self.config['evidence_root']) / 'client' / self.request['request_id']
        directory.mkdir(parents=True)
        receipt = directory / 'receipt.json'
        receipt.write_text(json.dumps({**self.receipt, 'admission': {'promotion_ready': True}}))
        self.config['source_review_command'] = '/fake/reviewer'
        self.client.review_selection = lambda _: {'eligible_except_source_review': True, 'reasons': []}
        original_run = subprocess.run
        calls = []
        def run(args, **kwargs):
            if args[0] != '/fake/reviewer':
                return original_run(args, **kwargs)
            payload = json.loads(kwargs['input'])
            calls.append(payload)
            self.assertEqual(payload['parent_sha'], self.seed)
            data = {'approved': False, 'candidate_sha': payload['candidate_sha'],
                    'parent_sha': payload['parent_sha'], 'diff_sha256': payload['source_diff_sha256'],
                    'scope': 'no-fixture-specialization-and-integrity'}
            root = Path(self.config['evidence_root'])
            artifact = root / 'review.json'
            artifact.write_bytes(immutable(data))
            diff = root / 'source.diff'
            diff.write_bytes(Path(payload['source_diff_path']).read_bytes())
            envelope = {**data, 'artifact_path': 'review.json', 'artifact_sha256': sha256(artifact.read_bytes()),
                        'diff_path': 'source.diff'}
            return subprocess.CompletedProcess(args, 0, immutable({'source_review': envelope}), b'')
        with patch('lab.overnight_client.subprocess.run', side_effect=run):
            first = self.client.review(self.request, self.terminal, directory, receipt)
            second = self.client.review(self.request, self.terminal, directory, receipt)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)
        self.assertFalse(first['approved'])

    def selection_fixture(self, seconds):
        try:
            from lab.overnight_publish import BEST
        except ImportError:
            self.skipTest('Publisher is integrated by the coordinating maintainer')
        control = self.root / 'selection-control'
        current = {'status': 'admitted_campaign_best', 'candidate_sha': self.seed,
                   'cohort_digest': 'f'*64,
                   'metrics': {setup: {'median_seconds': 1.0, 'min_seconds': .99, 'max_seconds': 1.01}
                               for setup in ('grid', 'aligo')}}
        path = control / BEST
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(current))
        self.publisher.worktree = control
        self.publisher.locked = lambda: contextlib.nullcontext()
        receipt = {**self.receipt, 'cohort_digest': 'f'*64,
                   'admission': {'promotion_ready': True, 'candidate_sha': self.sha, 'comparison_cohort_passed': True},
                   'generalization': {'case_count': 14, 'all_finite': True, 'inputs_identical': True,
                                      'seed_comparison_passed': True, 'new_failures': []},
                   'benchmarks': {setup: {'samples': [
                       {'seconds': seconds, 'fresh_process': True, 'official_passed': True,
                        'candidate_sha': self.sha, 'report_sha256': f'{i:064x}'} for i in range(1, 4)]}
                       for setup in ('grid', 'aligo')}}
        return path, receipt

    def test_slower_candidate_skips_external_review_with_durable_reason(self):
        _, receipt = self.selection_fixture(1.1)
        directory = Path(self.config['evidence_root']) / 'client' / self.request['request_id']
        directory.mkdir(parents=True)
        path = directory / 'receipt.json'
        path.write_text(json.dumps(receipt))
        self.config['source_review_command'] = '/must/not/run'
        with patch('lab.overnight_client.subprocess.run', side_effect=AssertionError('Slower candidate must not consume model tokens')):
            result = self.client.review(self.request, self.terminal, directory, path)
        self.assertIsNone(result)
        selection = json.loads((directory / 'source-review-selection.json').read_text())
        self.assertFalse(selection['eligible_except_source_review'])
        self.assertTrue(selection['reasons'])
        self.assertNotIn('requires_source_review', selection['reasons'])

    def test_faster_candidate_is_eligible_for_review_without_invented_approval(self):
        _, receipt = self.selection_fixture(.9)
        selection = self.client.review_selection(receipt)
        self.assertTrue(selection['eligible_except_source_review'], selection)
        self.assertEqual(selection['selection_decision']['reasons'], ['requires_source_review'])
        self.assertNotIn('source_review', receipt)

    def test_missing_current_best_skips_review_fail_closed(self):
        path, receipt = self.selection_fixture(.9)
        path.unlink()
        selection = self.client.review_selection(receipt)
        self.assertFalse(selection['eligible_except_source_review'])
        self.assertIn('current_best_unavailable_or_invalid', selection['reasons'])

    def test_log_collection_skips_source_and_keeps_hashed_small_logs(self):
        remote_root = Path(self.config['remote_root'])
        base = remote_root / 'requests' / self.request['request_id']
        (base / 'grid').mkdir(parents=True)
        (base / 'code').mkdir()
        (base / 'grid/stdout.log').write_text('benchmark output')
        (base / 'code/private.log').write_text('not an evaluator log')
        self.client.remote = lambda argv, stdin=None: subprocess.check_output(argv, input=stdin)
        directory = Path(self.config['evidence_root']) / 'client' / self.request['request_id']
        Client.collect_logs(self.client, self.request, directory)
        manifest = json.loads((directory / 'log-manifest.json').read_text())
        self.assertEqual(len(manifest), 1)
        self.assertTrue(manifest[0]['path'].endswith('grid/stdout.log'))


if __name__ == '__main__':
    unittest.main()
