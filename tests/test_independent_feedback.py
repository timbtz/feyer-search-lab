import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from lab.agent_loop import _run_locked, evidence_only_feedback, run


def response():
    return dict(summary='Own change', hypothesis='Own hypothesis', notes='Own evidence',
                ready_for_evaluation=True, stop=False)


def own_feedback():
    return {'candidate_sha': 'a' * 40, 'agent_response': response(),
            'profiler': {'recommendation': 'INHERITED_STRATEGY'},
            'agent_context': {'continuation_guidance': 'INHERITED_STRATEGY'},
            'input_receipt': {'prior_context': 'INHERITED_STRATEGY'},
            'full': dict(id='own-job', sha='a' * 40, agent='independent', branch='explore/independent',
                         direction='independent', profile='full', status='completed',
                         result={'official_passed': True, 'first_run_seconds': 35.},
                         **{'report.json': {'phases': [{'key': 'forward_compile', 'seconds': 10.}]},
                            'comparison.json': {'passed': False, 'max_error': 0.3},
                            'profiler': {'recommendation': 'INHERITED_STRATEGY'}})}


class IndependentFeedbackTests(unittest.TestCase):
    def select(self, feedback):
        return evidence_only_feedback(feedback, name='independent', branch='explore/independent',
                                      direction='independent', candidate_sha='a' * 40)

    def test_raw_own_results_and_response_survive_without_context_or_recommendations(self):
        feedback = own_feedback()
        selected = self.select(feedback)
        self.assertNotIn('INHERITED_STRATEGY', json.dumps(selected))
        self.assertEqual(selected['agent_response'], feedback['agent_response'])
        for key in ('report.json', 'comparison.json', 'result'):
            self.assertEqual(selected['full'][key], feedback['full'][key])
        selected['full']['comparison.json']['max_error'] = 0
        self.assertEqual(feedback['full']['comparison.json']['max_error'], .3)

    def test_foreign_results_or_sha_are_rejected(self):
        for key, value in [('agent', 'someone-else'), ('branch', 'explore/other'),
                           ('direction', 'other'), ('sha', 'b' * 40), ('profile', 'screen')]:
            feedback = own_feedback()
            feedback['full'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.select(feedback)
        feedback = own_feedback()
        feedback['candidate_sha'] = 'b' * 40
        with self.assertRaises(ValueError):
            self.select(feedback)

    def test_mode_is_immutable_and_legacy_sessions_are_guided(self):
        for saved, requested in [({'feedback_mode': 'guided'}, 'evidence-only'),
                                 ({'feedback_mode': 'evidence-only'}, 'guided'),
                                 ({'thread_id': 'legacy'}, 'evidence-only')]:
            with self.subTest(saved=saved), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                status = root / 'status.json'
                status.write_text(json.dumps(saved))
                args = SimpleNamespace(resume=True, feedback_mode=requested)
                with self.assertRaisesRegex(ValueError, 'Cannot change feedback mode'):
                    _run_locked(args, root, root, root, status, ())

    def test_seeds_and_guidance_are_rejected_before_reading_or_starting_work(self):
        for field in ('profile_seed', 'continuation_guidance'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                args = SimpleNamespace(resume=False, feedback_mode='evidence-only', **{field: '/not/read'})
                with self.assertRaisesRegex(ValueError, 'reject continuation guidance and profile seeds'):
                    _run_locked(args, root, root, root, root/'status.json', ())
                status = root / 'status.json'
                status.write_text(json.dumps({'feedback_mode': 'evidence-only', field: {'text': 'inherited'}}))
                args = SimpleNamespace(resume=True, feedback_mode='evidence-only')
                with self.assertRaisesRegex(ValueError, 'reject continuation guidance and profile seeds'):
                    _run_locked(args, root, root, root, status, ())

    def test_two_turns_capture_only_own_raw_feedback_and_default_guided_is_unchanged(self):
        for mode in ('evidence-only', 'guided'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, worktree = root / 'repo', root / 'worktree'
                repo.mkdir()
                def git(*args):
                    return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                                   stderr=subprocess.PIPE).strip()
                git('init', '-b', 'main')
                git('config', 'user.name', 'Test')
                git('config', 'user.email', 'test@example.invalid')
                (repo/'differometor').mkdir()
                (repo/'differometor/simulate.py').write_text('# original\n')
                (repo/'experiments').mkdir()
                (repo/'experiments/initial-agent.md').write_text('LEGACY_GUIDED_BRIEF')
                git('add', '.')
                git('commit', '-m', 'fixture')
                args = SimpleNamespace(repo=repo, worktree=worktree, name='independent',
                    branch='explore/independent', direction='independent', resume=False,
                    host='unused', github_repo='', max_minutes=1, max_candidates=None,
                    baseline_seconds=36., feedback_mode=mode)
                client, calls, jobs = Mock(), [], {}
                def turn(folder, session, number, prompt, thread, timeout, lock_fds=()):
                    calls.append(prompt)
                    if number == 1:
                        (folder/'differometor/simulate.py').write_text('# own candidate\n')
                        return 'own-conversation', response()
                    return 'own-conversation', dict(response(), ready_for_evaluation=False, stop=True)
                def submit(folder, branch, agent, direction, hypothesis, profile, sha, request_id=None):
                    job = copy.deepcopy(own_feedback()['full'])
                    job.update(id='own-'+profile, sha=sha, profile=profile, branch=branch,
                               agent=agent, direction=direction)
                    job.pop('profiler')
                    jobs[job['id']] = job
                    return job
                client.submit.side_effect = submit
                client.wait.side_effect = lambda job_id, timeout: jobs[job_id]
                with patch('lab.agent_loop.Client', return_value=client), \
                     patch('lab.agent_loop.codex_turn', side_effect=turn), \
                     patch('lab.agent_loop._push'), patch('lab.agent_loop.github_status'), \
                     patch('lab.profiler_feedback.prompt_guidance', return_value='GUIDED_RECOMMENDATIONS') as guidance:
                    run(args)
                self.assertEqual(len(calls), 2)
                self.assertIn('own-full', calls[1])
                self.assertIn('forward_compile', calls[1])
                self.assertIn('max_error', calls[1])
                self.assertIn('Own hypothesis', calls[1])
                session = repo/'.lab/sessions/independent'
                state = json.loads((session/'status.json').read_text())
                self.assertEqual(state['feedback_mode'], mode)
                receipts = list(session.glob('turn-02-prompt-*.json'))
                receipt = json.loads(receipts[0].read_text())
                self.assertEqual(receipt['feedback_mode'], mode)
                self.assertEqual(receipt['prompt'], calls[1])
                self.assertEqual(receipt['sha256'], hashlib.sha256(calls[1].encode()).hexdigest())
                saved = json.loads((worktree/'experiments/runs/independent/candidate-01.json').read_text())
                self.assertEqual(saved['provenance']['feedback_mode'], mode)
                self.assertEqual(saved['agent_context']['feedback_mode'], mode)
                if mode == 'evidence-only':
                    delivered = json.loads(Path(receipt['consumed_feedback_ref']).read_text())
                    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                    self.assertEqual(receipt['consumed_feedback_digest'], digest(delivered))
                    self.assertEqual(receipt['source_feedback_digest'], digest(saved))
                    self.assertEqual(receipt['consumed_feedback_projection'], 'evidence-only-v1')
                    guidance.assert_not_called()
                    self.assertNotIn('GUIDED_RECOMMENDATIONS', ''.join(calls))
                    self.assertNotIn('LEGACY_GUIDED_BRIEF', ''.join(calls))
                    self.assertNotIn('hypothetical halving', ''.join(calls))
                    self.assertNotIn('profiler', saved)
                    self.assertIn('fresh independent investigation', calls[0])
                    self.assertIsNotNone(state['fixed_deadline_unix'])
                else:
                    self.assertEqual(guidance.call_count, 2)
                    self.assertIn('GUIDED_RECOMMENDATIONS', calls[0])
                    self.assertIn('LEGACY_GUIDED_BRIEF', calls[0])
                    self.assertIn('profiler', saved)


if __name__ == '__main__':
    unittest.main()
