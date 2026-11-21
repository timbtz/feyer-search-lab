import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lab.agent_loop import _run_locked
from lab.profiler_feedback import load_seed, prompt_guidance
from tests.test_evolution_evidence import full_job


class ProfilerFeedbackTests(unittest.TestCase):
    def test_seed_requires_exact_fully_validated_revision(self):
        job = full_job()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'seed.json'
            path.write_text(json.dumps(job))
            self.assertEqual(load_seed(path, job['sha'])['full']['id'], job['id'])
            with self.assertRaisesRegex(ValueError, 'exact initial'):
                load_seed(path, 'b' * 40)
            job['comparison.json']['passed'] = False
            path.write_text(json.dumps(job))
            with self.assertRaisesRegex(ValueError, 'eligible full'):
                load_seed(path, job['sha'])

    def test_prompt_recomputes_raw_evidence_and_preserves_objective(self):
        job = full_job()
        prompt = prompt_guidance({'candidate_sha': job['sha'], 'full': job,
                                  'profiler': {'invented_hotspot': 'fake'}})
        self.assertIn(job['id'], prompt)
        self.assertIn('forward_compile', prompt)
        self.assertIn('complete first-run time', prompt)
        self.assertIn('Unknown native-operation costs remain unknown', prompt)
        self.assertNotIn('invented_hotspot', prompt)
        self.assertIn('No measured profiler seed', prompt_guidance(None))

    def test_resume_cannot_change_model_or_fixed_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / 'status.json'
            deadline = time.time() + 100
            state = {'agent_provider': 'claude', 'agent_model': 'claude-fable-5-2',
                     'fixed_deadline_unix': deadline}
            status.write_text(json.dumps(state))
            args = SimpleNamespace(resume=True, agent_provider='claude',
                agent_model='other', branch='explore/test', direction='profile', max_minutes=60)
            with self.assertRaisesRegex(ValueError, 'provider or model'):
                _run_locked(args, root, root, root, status, ())
            args.agent_model = 'claude-fable-5-2'
            args.deadline_unix = deadline + 100
            with self.assertRaisesRegex(ValueError, 'fixed session deadline'):
                _run_locked(args, root, root, root, status, ())

    def test_expired_fixed_deadline_survives_resume_without_new_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / 'status.json'
            deadline = time.time() - 1
            status.write_text(json.dumps({'fixed_deadline_unix': deadline}))
            brief = root / 'brief.txt'
            brief.write_text('Do work only within budget.')
            args = SimpleNamespace(resume=True, branch='explore/test', direction='profile',
                max_minutes=60, max_candidates=None, host='unused', brief=brief)
            def git(_path, *command):
                return 'explore/test' if command == ('branch', '--show-current') else 'a' * 40
            with patch('lab.agent_loop.git', side_effect=git), \
                 patch('lab.agent_loop.Client') as client, \
                 patch('lab.agent_loop.codex_turn') as turn:
                _run_locked(args, root, root, root, status, ())
            turn.assert_not_called()
            client.return_value.submit.assert_not_called()
            saved = json.loads(status.read_text())
            self.assertEqual(saved['fixed_deadline_unix'], deadline)
            self.assertEqual(saved['invocation_deadline_at'], deadline)
            self.assertEqual(saved['status'], 'budget_exhausted')


if __name__ == '__main__':
    unittest.main()
