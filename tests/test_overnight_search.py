import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lab.agent_loop import CodexTurnError, SessionBusyError, exclusive_lock
from lab.overnight_search import (Providers, SHARED_BEST, SHARED_PREFIX, Supervisor, digest, git,
                                 shared_best_snapshot, turn_error, validate_evaluation, write_json)


def response(ready=True):
    return dict(summary='measured experiment', hypothesis='generic simplification',
                ready_for_evaluation=ready, stop=False, notes='preserve physics')


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'explore/test', str(self.repo)], check=True)
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        git(self.repo, 'config', 'user.name', 'Test')
        (self.repo / 'differometor').mkdir()
        (self.repo / 'differometor' / 'simulate.py').write_text('value = 1\n')
        (self.repo / 'AGENTS.md').write_text('No changing physics.\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'initial')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'codex').write_text('#!/bin/sh\nexit 0\n')
        self.now = [1000.0]
        self.args = argparse.Namespace(worktree=str(self.repo), campaign_dir=str(self.root / 'campaign'),
                                       name='lane0', lane=0, branch='explore/test', brief=str(self.repo / 'AGENTS.md'),
                                       deadline_unix=2000.0, evaluator_command='/fake/evaluator',
                                       codex_bin_dir=str(self.bin), status_export=None, resume=False,
                                       max_turn_seconds=1800, hook_timeout=10, drain_seconds=900)
        self.s = Supervisor(self.args, clock=lambda: self.now[0], publish=lambda: None)
        self.s.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def candidate(self):
        def call(provider, iteration, prompt, thread, timeout):
            (self.repo / 'differometor' / 'simulate.py').write_text('value = 2\n')
            return 'claude-thread', response()
        self.s.model_call = call
        self.s.model_step()
        self.s.commit_pending()
        return self.s.state['active_evaluation']

    def test_dual_evaluation_same_identity_persisted_before_call(self):
        request = self.candidate()
        seen = []
        def evaluate(value):
            persisted = json.loads(self.s.path.read_text())['active_evaluation']
            self.assertEqual(persisted, value)
            seen.append(value['request_id'])
            if len(seen) == 1:
                raise RuntimeError('connection lost')
            return {**value, 'status': 'completed', 'official_passed': False,
                    'generalization': {'status': 'review_required'}}
        self.s.evaluate = evaluate
        with self.assertRaises(RuntimeError):
            self.s.evaluate_pending()
        self.s.evaluate_pending()
        self.assertEqual(seen, [request['request_id']] * 2)
        self.s.commit_pending()
        self.assertEqual(self.s.state['nonimproving'], 1)
        self.assertIn('review_required', self.s.prompt())
        self.assertEqual(self.s.state['threads']['claude'], 'claude-thread')
        self.assertNotIn('active_evaluation', self.s.state)

    def test_public_pass_does_not_imply_promotion_or_improvement(self):
        request = self.candidate()
        self.s.evaluate = lambda _: {**request, 'status': 'completed', 'official_passed': True}
        self.s.evaluate_pending()
        self.assertEqual(self.s.state['nonimproving'], 1)
        self.assertNotIn('best', self.s.state)

    def test_commit_push_failure_reuses_commit_and_request(self):
        self.s.model_call = lambda *args: ('thread', response())
        (self.repo / 'differometor' / 'simulate.py').write_text('value = 3\n')
        self.s.model_step()
        self.s.publish = lambda: (_ for _ in ()).throw(RuntimeError('push offline'))
        with self.assertRaises(RuntimeError):
            self.s.commit_pending()
        committed = git(self.repo, 'rev-parse', 'HEAD')
        self.assertNotIn('active_evaluation', self.s.state)
        self.s.publish = lambda: None
        self.s.commit_pending()
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), committed)
        self.assertEqual(self.s.state['candidate_count'], 1)

    def test_feedback_crash_before_artifact_reconstructs_exact_result(self):
        request = self.candidate()
        self.s.evaluate = lambda _: {**request, 'status': 'failed', 'reason': 'physical output mismatch'}
        self.s.evaluate_pending()
        pending = self.s.state['pending_commit']
        (self.repo / pending['artifact_path']).unlink()
        write_json(self.repo / pending['artifact_path'], pending['artifact'])
        self.s.commit_pending()
        self.assertEqual(json.loads((self.repo / pending['artifact_path']).read_text())['request_id'], request['request_id'])

    def test_quota_preserves_partial_edits_for_codex(self):
        def fail(*args):
            (self.repo / 'differometor' / 'simulate.py').write_text('value = 5\n')
            (self.s.directory / 'turn-01.stderr.log').write_text('usage limit reached')
            raise CodexTurnError('exited 1', thread_id='claude-thread')
        self.s.model_call = fail
        self.assertFalse(self.s.model_step())
        self.assertEqual(self.s.providers.choose(), 'codex')
        self.assertIn('value = 5', (self.repo / 'differometor' / 'simulate.py').read_text())
        self.assertNotIn('pending_commit', self.s.state)
        def recover(provider, iteration, prompt, thread, timeout):
            self.assertEqual(provider, 'codex')
            self.assertIsNone(thread)
            self.assertIn('Preserved partial turn', prompt)
            self.assertIn('quota', prompt)
            return 'codex-thread', response()
        self.s.model_call = recover
        self.s.model_step()
        self.assertEqual(self.s.state['threads'], {'claude': 'claude-thread', 'codex': 'codex-thread'})

    def test_syntax_failure_keeps_edits_for_same_session_repair(self):
        def call(*args):
            (self.repo / 'differometor' / 'simulate.py').write_text('value = (\n')
            return 'thread', response()
        self.s.model_call = call
        self.s.model_step()
        self.assertNotIn('pending_commit', self.s.state)
        self.assertTrue(self.s.state['partial_turn']['syntax_error'])
        self.assertEqual(self.s.state['threads']['claude'], 'thread')

    def test_no_candidate_preserves_handoff_and_does_not_commit_partial(self):
        self.s.model_call = lambda *args: ('same-thread', response(False))
        for _ in range(3):
            self.s.model_step()
        self.assertEqual(self.s.state['no_candidate'], 3)
        self.assertEqual(self.s.state['threads']['claude'], 'same-thread')
        self.assertIn('one concrete next experiment', self.s.prompt())
        self.assertNotIn('pending_commit', self.s.state)

    def test_stagnation_does_not_reset_conversation(self):
        self.s.state['nonimproving'] = 3
        self.s.state['threads']['claude'] = 'keep-me'
        self.assertIn('reduce complexity and timing variance', self.s.prompt())
        self.assertEqual(self.s.state['threads']['claude'], 'keep-me')

    def test_completed_turn_recovery_never_calls_model_twice(self):
        (self.repo / 'differometor' / 'simulate.py').write_text('value = 42\n')
        self.s.state['iteration'] = 1
        self.s.state['pending_turn'] = {'iteration': 1, 'provider': 'claude', 'thread': None,
                                         'before_sha': self.s.state['expected_head']}
        self.s.save()
        write_json(self.s.directory / 'turn-01.json', response())
        (self.s.directory / 'turn-01.jsonl').write_text(json.dumps(
            {'type': 'system', 'subtype': 'init', 'session_id': 'recovered', 'model': 'claude-opus-5-5'}) + '\n')
        self.s.model_call = lambda *args: self.fail('repeated completed model call')
        with patch('lab.overnight_search.shared_best_snapshot', side_effect=AssertionError('must not refresh dispatched input')):
            self.s.model_step()
        self.assertEqual(self.s.state['threads']['claude'], 'recovered')
        self.assertEqual(self.s.state['actual_model'], 'claude-opus-5-5')
        self.assertIn('pending_commit', self.s.state)

    def test_source_review_packet_is_bound_to_exact_commit(self):
        request = self.candidate()
        self.assertTrue(request['requires_source_review'])
        self.assertEqual(request['sha'], git(self.repo, 'rev-parse', 'HEAD'))
        self.assertEqual(request['parent_sha'], self.s.state['initial_sha'])
        self.assertIn('+value = 2', Path(request['source_diff_path']).read_text())
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')

    def test_no_new_model_or_evaluation_after_deadline(self):
        self.now[0] = 2001
        self.s.model_call = lambda *args: self.fail('must not dispatch')
        self.assertFalse(self.s.model_step())
        self.now[0] = 1000
        self.s.model_call = lambda *args: ('thread', response())
        (self.repo / 'differometor' / 'simulate.py').write_text('value = 9\n')
        self.s.model_step()
        self.now[0] = 2001
        self.s.commit_pending()
        self.assertNotIn('active_evaluation', self.s.state)
        self.assertEqual(self.s.state['history'][-1]['kind'], 'unevaluated_deadline_checkpoint')

    def test_resume_requires_immutable_deadline_and_wrapper(self):
        self.args.resume = True
        self.args.deadline_unix += 1
        with self.assertRaisesRegex(ValueError, 'identical'):
            Supervisor(self.args).initialize()
        self.args.deadline_unix -= 1
        (self.bin / 'codex').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'identical'):
            Supervisor(self.args).initialize()

    def test_protected_change_rejected_before_commit(self):
        def call(*args):
            (self.repo / 'benchmark.py').write_text('tampered')
            return 'thread', response()
        self.s.model_call = call
        with self.assertRaises(ValueError):
            self.s.model_step()
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.s.state['initial_sha'])

    def test_external_commit_rejected(self):
        git(self.repo, 'commit', '--allow-empty', '-qm', 'outsider')
        with self.assertRaisesRegex(ValueError, 'externally'):
            self.s.model_step()

    def test_lane_duplicate_worktree_rejected(self):
        self.args.name, self.args.lane = 'other', 1
        with self.assertRaisesRegex(ValueError, 'another lane'):
            Supervisor(self.args).initialize()

    def test_lock_keeps_one_writer(self):
        path = self.root / 'writer.lock'
        with exclusive_lock(path):
            with self.assertRaises(SessionBusyError):
                with exclusive_lock(path):
                    self.fail('duplicate writer')

    def shared_fixture(self, large=False):
        control = self.root / 'control'
        subprocess.run(['git', 'clone', '-q', str(self.repo), str(control)], check=True)
        git(control, 'config', 'user.email', 'test@example.invalid')
        git(control, 'config', 'user.name', 'Test')
        seed = git(control, 'rev-parse', 'HEAD')
        content = 'value = 2\n' if not large else 'value = 2\n#' + 'x'*200_001 + '\n'
        (control / 'differometor/simulate.py').write_text(content)
        git(control, 'commit', '-qam', 'source improvement')
        selected = git(control, 'rev-parse', 'HEAD')
        diff = git(control, 'diff', seed, selected, '--', 'differometor')
        evaluation = 'b'*32
        directory = SHARED_PREFIX + '/candidates/' + evaluation
        review = {'approved': True, 'candidate_sha': selected, 'parent_sha': seed,
                  'diff_sha256': digest(diff), 'scope': 'no-fixture-specialization-and-integrity',
                  'reviewer': 'independent', 'provider': 'codex', 'model': 'gpt-6-astra', 'session_id': 'review-session'}
        review_path = control / directory / 'source-review.json'
        write_json(review_path, review)
        import hashlib
        envelope = {**review, 'artifact_sha256': hashlib.sha256(review_path.read_bytes()).hexdigest()}
        (control / directory / 'reviewed-source.diff').write_text(diff)
        metrics = {setup: {'median_seconds': 1.1, 'min_seconds': 1.0, 'max_seconds': 1.2} for setup in ('grid', 'aligo')}
        record = {'candidate_sha': selected, 'evaluation_id': evaluation,
                  'decision': {'promote': True, 'metrics': metrics},
                  'evaluator_receipt': {'candidate_sha': selected, 'source_review': envelope,
                                        'admission': {'promotion_ready': True}}}
        write_json(control / directory / 'record.json', record)
        best = {'status': 'admitted_campaign_best', 'candidate_sha': selected, 'seed_sha': seed,
                'evaluation_id': evaluation, 'record_path': directory + '/record.json', 'metrics': metrics}
        write_json(control / SHARED_BEST, best)
        git(control, 'add', '.')
        git(control, 'commit', '-qm', 'publish reviewed candidate')
        return control, seed, best

    def test_shared_best_verified_snapshot_is_captured_and_refreshes_next_turn(self):
        control, seed, best = self.shared_fixture()
        self.s.state['shared_best_worktree'] = str(control)
        seen = []
        self.s.model_call = lambda provider, iteration, prompt, thread, timeout: (seen.append(prompt) or 'same-thread', response(False))
        with patch('lab.overnight_search.SHARED_SEED', seed):
            self.s.model_step()
            first = json.loads((self.s.directory / 'turn-01.input.json').read_text())['shared_best_snapshot']
            self.assertEqual(first['status'], 'available')
            self.assertEqual(first['selected_sha'], best['candidate_sha'])
            self.assertIn('+value = 2', first['source_diff'])
            best['metrics']['grid']['median_seconds'] = 1.05
            write_json(control / SHARED_BEST, best)
            record_path = control / best['record_path']
            record = json.loads(record_path.read_text())
            record['decision']['metrics'] = best['metrics']
            write_json(record_path, record)
            git(control, 'commit', '-qam', 'publish fresh repeated timings')
            self.s.model_step()
            second = json.loads((self.s.directory / 'turn-02.input.json').read_text())['shared_best_snapshot']
        self.assertNotEqual(first['artifact_sha256'], second['artifact_sha256'])
        self.assertEqual(self.s.state['threads']['claude'], 'same-thread')
        self.assertIn('do not automatically accept, merge or reset', seen[0])
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.s.state['initial_sha'])

    def test_shared_best_uncommitted_or_provisional_is_omitted(self):
        control, seed, best = self.shared_fixture()
        best['status'] = 'seed_pending_fresh_calibration'
        write_json(control / SHARED_BEST, best)
        with patch('lab.overnight_search.SHARED_SEED', seed):
            self.assertIn('exact committed', shared_best_snapshot(control)['reason'])
            git(control, 'commit', '-qam', 'provisional state')
            rejected = shared_best_snapshot(control)
        self.assertEqual(rejected['status'], 'omitted')
        self.assertIn('not admitted', rejected['reason'])
        self.assertNotIn('source_diff', rejected)

    def test_shared_best_rejects_unreviewed_or_oversized_source(self):
        control, seed, best = self.shared_fixture(large=True)
        with patch('lab.overnight_search.SHARED_SEED', seed):
            self.assertIn('200 KB', shared_best_snapshot(control)['reason'])
        record_path = control / best['record_path']
        record = json.loads(record_path.read_text())
        record['evaluator_receipt']['admission']['promotion_ready'] = False
        write_json(record_path, record)
        git(control, 'commit', '-qam', 'reject evidence')
        with patch('lab.overnight_search.SHARED_SEED', seed):
            self.assertIn('admission', shared_best_snapshot(control)['reason'])

    def test_shared_best_review_artifact_tamper_is_not_injected(self):
        control, seed, best = self.shared_fixture()
        review_path = control / Path(best['record_path']).parent / 'source-review.json'
        review_path.write_text('{}')
        git(control, 'commit', '-qam', 'invalid review')
        with patch('lab.overnight_search.SHARED_SEED', seed):
            snapshot = shared_best_snapshot(control)
        self.assertEqual(snapshot['status'], 'omitted')
        self.assertIn('review artifact digest', snapshot['reason'])

    def test_shared_best_one_explicit_resume_activation_only(self):
        self.s.state.pop('shared_best_worktree')  # Legacy snapshot predates optional field.
        self.s.save()
        self.args.resume = True
        self.args.shared_best_worktree = str(self.root / 'control')
        resumed = Supervisor(self.args)
        resumed.initialize()
        self.assertEqual(len(resumed.state['shared_best_activation_history']), 1)
        self.assertEqual(resumed.state['deadline_unix'], 2000)
        resumed = Supervisor(self.args)
        resumed.initialize()
        self.assertEqual(len(resumed.state['shared_best_activation_history']), 1)
        self.args.shared_best_worktree = str(self.root / 'other')
        with self.assertRaisesRegex(ValueError, 'cannot change'):
            Supervisor(self.args).initialize()
        self.args.shared_best_worktree = None
        with self.assertRaisesRegex(ValueError, 'cannot change'):
            Supervisor(self.args).initialize()

    def test_default_disabled_or_missing_shared_artifact_keeps_original_prompt(self):
        self.assertEqual(shared_best_snapshot(None)['status'], 'disabled')
        self.assertEqual(self.s.prompt(), self.s.prompt(shared_best_snapshot(None)))
        missing = shared_best_snapshot(self.root / 'missing')
        self.assertEqual(missing['status'], 'omitted')
        self.assertEqual(self.s.prompt(), self.s.prompt(missing))


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = [100.0]
        self.p = Providers(self.tmp.name, 'one', 50000, lambda: self.now[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_quota_cooldown_and_single_reset_probe(self):
        self.assertEqual(self.p.choose(), 'claude')
        self.assertEqual(self.p.failure('claude', 'usage limit exceeded'), 'quota')
        self.assertEqual(self.p.choose(), 'codex')
        self.now[0] += 21601
        other = Providers(self.tmp.name, 'two', 50000, lambda: self.now[0])
        self.assertEqual(self.p.choose(), 'claude')
        self.assertEqual(other.choose(), 'codex')
        self.p.success('claude')
        self.assertEqual(other.choose(), 'claude')

    def test_explicit_retry_after_and_auth(self):
        self.p.failure('claude', 'rate_limit_error retry_after: 120')
        self.assertEqual(json.loads(self.p.path.read_text())['claude']['blocked_until'], 220)
        self.assertEqual(self.p.failure('codex', 'authentication failed'), 'auth')
        self.assertIsNone(self.p.choose())

    def test_rejected_rate_limit_metadata_honors_reset_but_allowed_event_does_not(self):
        directory = Path(self.tmp.name)
        events = directory / 'turn-01.jsonl'
        events.write_text(json.dumps({'type': 'rate_limit_event', 'rate_limit_info': {'status': 'allowed', 'resetsAt': 999}}))
        self.assertNotIn('rate_limit_error', turn_error(directory, 1, RuntimeError('transport failed')))
        events.write_text(json.dumps({'type': 'rate_limit_event', 'rate_limit_info': {'status': 'rejected', 'resetsAt': 999}}))
        self.p.failure('claude', turn_error(directory, 1, RuntimeError('exited 1')))
        self.assertEqual(json.loads(self.p.path.read_text())['claude']['blocked_until'], 999)

    def test_bad_response_is_transient_not_quota(self):
        self.assertEqual(self.p.failure('claude', 'invalid structured output'), 'transient')
        self.assertEqual(json.loads(self.p.path.read_text())['claude']['blocked_until'], 115)
        self.assertIsNone(self.p.choose())

    def test_older_success_does_not_erase_newer_shared_quota(self):
        self.p.failure('claude', 'usage limit exceeded')
        self.p.success('claude', started_at=99)
        self.assertEqual(self.p.choose(), 'codex')

    def test_another_lane_transient_probe_does_not_authorize_codex_fallback(self):
        self.p.failure('claude', 'temporary bad structured response')
        self.now[0] = 116
        other = Providers(self.tmp.name, 'two', 50000, lambda: self.now[0])
        self.assertEqual(self.p.choose(), 'claude')
        self.assertIsNone(other.choose())

    def test_evaluation_identity_and_missing_verdict(self):
        request = {'request_id': 'a'*32, 'sha': 'b'*40}
        for result in ({**request, 'request_id': 'c'*32, 'status': 'failed'},
                       {**request, 'status': 'completed'}, {**request, 'status': 'unknown'}):
            with self.assertRaises(ValueError):
                validate_evaluation(result, request)
        self.assertEqual(validate_evaluation({**request, 'status': 'interrupted'}, request)['status'], 'interrupted')


if __name__ == '__main__':
    unittest.main()
