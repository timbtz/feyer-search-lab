"""Guards used before an autonomous edit becomes a committed candidate."""
import subprocess
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lab.agent_loop import (CodexTurnError, SessionBusyError, _advance_candidate,
                            _finish_record, _recover_submission, changed_paths, codex_turn,
                            exclusive_lock, run, validate_changes, validate_response)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE).strip()


class AgentChangeGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "differometor").mkdir()
        (self.repo / "differometor/simulate.py").write_text("# original\n")
        (self.repo / "benchmark.py").write_text("# fixed harness\n")
        (self.repo / "experiments/notes").mkdir(parents=True)
        (self.repo / "experiments/initial-agent.md").write_text("Fixed instructions\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "baseline")

    def tearDown(self):
        self.temp.cleanup()

    def test_detects_staged_unstaged_untracked_and_deleted_files(self):
        (self.repo / "differometor/simulate.py").write_text("# changed\n")
        git(self.repo, "add", "differometor/simulate.py")
        (self.repo / "benchmark.py").unlink()
        (self.repo / "experiments/initial-agent.md").write_text("Changed instructions\n")
        (self.repo / "experiments/notes/idea.md").write_text("A hypothesis\n")
        self.assertEqual(changed_paths(self.repo), [
            "benchmark.py", "differometor/simulate.py", "experiments/initial-agent.md",
            "experiments/notes/idea.md"])

    def test_accepts_simulator_and_notes_edits(self):
        note = self.repo / "experiments/notes/idea.md"
        note.write_text("Hypothesis\n")
        validate_changes(self.repo, ["differometor/simulate.py", "experiments/notes/idea.md"])
        (self.repo / "differometor/simulate.py").unlink()
        validate_changes(self.repo, ["differometor/simulate.py"])

    def test_rejects_harness_instructions_feedback_and_other_paths(self):
        for name in ("benchmark.py", "lab/worker.py", "requirements.txt", "AGENTS.md",
                     "experiments/initial-agent.md", "experiments/runs/agent/candidate-01.json",
                     "differometor_else/file.py", "examples/data/reference.json"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_changes(self.repo, [name])

    def test_rejects_symlinks_and_oversized_files(self):
        link = self.repo / "differometor/link.py"
        link.symlink_to(self.repo / "benchmark.py")
        with self.assertRaises(ValueError):
            validate_changes(self.repo, ["differometor/link.py"])
        huge = self.repo / "experiments/notes/huge.bin"
        with huge.open("wb") as f:
            f.truncate(2 * 1024 * 1024 + 1)
        with self.assertRaises(ValueError):
            validate_changes(self.repo, ["experiments/notes/huge.bin"])

    def test_session_lock_rejects_a_second_supervisor(self):
        lock = self.repo / 'session.lock'
        with exclusive_lock(lock):
            with self.assertRaises(SessionBusyError):
                with exclusive_lock(lock):
                    pass

    def test_response_requires_real_booleans(self):
        response = {'summary': 'change', 'hypothesis': 'faster', 'notes': '',
                    'ready_for_evaluation': True, 'stop': False}
        self.assertEqual(validate_response(response), response)
        for key in ('ready_for_evaluation', 'stop'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_response(response | {key: 'false'})


class AgentResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.status_file = self.directory / 'status.json'
        self.args = SimpleNamespace(name='agent-a', direction='imports', branch='explore/imports',
                                    github_repo='test/repo', baseline_seconds=35.7)
        self.response = {'summary': 'change', 'hypothesis': 'faster', 'notes': '',
                         'ready_for_evaluation': True, 'stop': False}
        self.active = {'iteration': 1, 'sha': 'a' * 40, 'response': self.response,
                       'jobs': {}, 'feedback': {'candidate_sha': 'a' * 40, 'agent_response': self.response}}
        self.state = {'active_candidate': self.active}
        self.client = Mock()

    def tearDown(self):
        self.temp.cleanup()

    def advance(self, deadline):
        return _advance_candidate(self.active, self.args, self.client, self.directory,
                                  self.directory, self.state, self.status_file, deadline)

    def test_resume_waits_existing_failed_screen_and_does_not_resubmit(self):
        self.active['jobs']['screen'] = 'existing-job'
        job = {'id': 'existing-job', 'sha': 'a' * 40, 'profile': 'screen',
               'status': 'failed', 'error': 'incorrect result'}
        self.client.wait.return_value = job
        with patch('lab.agent_loop.github_status'), patch('lab.agent_loop._finish_record') as finish:
            self.assertTrue(self.advance(time.monotonic() + 60))
        self.client.submit.assert_not_called()
        self.client.wait.assert_called_once_with('existing-job', timeout=1800)
        self.assertEqual(self.active['feedback']['screen'], job)
        finish.assert_called_once()

    def test_operator_continuation_overrides_old_final_candidate_stop(self):
        self.active['response']['stop'] = True
        self.active['continue_after_evaluation'] = True
        with patch('lab.agent_loop.subprocess.run', return_value=Mock(returncode=0)), \
             patch('lab.agent_loop._push'), patch('lab.agent_loop.git', return_value='b' * 40):
            stopped = _finish_record(self.active, self.args, self.directory,
                                     self.directory, self.state, self.status_file)
        self.assertFalse(stopped)
        self.assertFalse(self.state['stop_requested'])
        self.assertTrue(self.active['response']['stop'])

    def test_no_new_job_is_submitted_after_deadline(self):
        self.assertFalse(self.advance(time.monotonic() - 1))
        self.client.submit.assert_not_called()
        self.assertEqual(self.state['status'], 'budget_exhausted')
        self.assertIs(self.state['active_candidate'], self.active)

    def test_existing_evaluation_may_finish_after_deadline_but_full_is_not_started(self):
        self.active['jobs']['screen'] = 'already-queued'
        self.client.wait.return_value = {'id': 'already-queued', 'sha': 'a' * 40,
                                         'profile': 'screen', 'status': 'completed',
                                         'result': {'first_run_seconds': 30}}
        with patch('lab.agent_loop.github_status'):
            self.assertFalse(self.advance(time.monotonic() - 1))
        self.client.wait.assert_called_once()
        self.client.submit.assert_not_called()
        self.assertEqual(self.active['feedback']['screen']['status'], 'completed')
        self.assertEqual(self.state['status'], 'budget_exhausted')

    def test_wait_timeout_keeps_job_id_for_later_resume(self):
        self.active['jobs']['screen'] = 'pending'
        self.client.wait.side_effect = TimeoutError('still pending')
        self.assertFalse(self.advance(time.monotonic() + 60))
        self.assertEqual(self.state['status'], 'waiting_for_evaluation')
        self.assertEqual(self.state['active_candidate']['jobs']['screen'], 'pending')
        self.client.submit.assert_not_called()

    def test_lost_submission_response_recovers_unique_matching_job(self):
        self.active.update(submitting_profile='screen', submission_started_at=100)
        self.client.request.return_value = [{'id': 'recovered', 'sha': 'a' * 40,
            'profile': 'screen', 'agent': 'agent-a', 'direction': 'imports', 'created_at': 101}]
        _recover_submission(self.active, self.args, self.client, self.state, self.status_file)
        self.assertEqual(self.active['jobs']['screen'], 'recovered')
        self.assertNotIn('submitting_profile', self.active)

    def test_uncertain_submission_never_blindly_requeues(self):
        self.active.update(submitting_profile='screen', submission_started_at=100)
        self.client.request.return_value = []
        with self.assertRaisesRegex(RuntimeError, 'uncertain'):
            _recover_submission(self.active, self.args, self.client, self.state, self.status_file)
        self.client.submit.assert_not_called()
        self.assertEqual(self.active['submitting_profile'], 'screen')

    def test_durable_request_recovery_ignores_clock_skew(self):
        request_id='1'*32
        self.active.update(submitting_profile='screen',submission_started_at=999999,
                           request_ids={'screen':request_id})
        self.client.request.return_value={'id':'recovered','sha':'a'*40,'branch':self.args.branch,
            'agent':self.args.name,'direction':self.args.direction,'hypothesis':'faster','profile':'screen',
            'created_at':-999999,'request_id':request_id}
        _recover_submission(self.active,self.args,self.client,self.state,self.status_file)
        self.assertEqual(self.active['jobs']['screen'],'recovered')
        self.client.request.assert_called_once_with({'action':'lookup_request','request_id':request_id})

    def test_pre_enqueue_crash_resubmits_same_persisted_request_id(self):
        request_id='2'*32
        self.active.update(submitting_profile='screen',submission_started_at=100,
                           request_ids={'screen':request_id})
        self.client.request.return_value=None
        def submit(*args,**kwargs):
            saved=json.loads(self.status_file.read_text())['active_candidate']
            self.assertEqual(saved['request_ids']['screen'],request_id)
            self.assertEqual(saved['submitting_profile'],'screen')
            self.assertEqual(kwargs['request_id'],request_id)
            return {'id':'retried','status':'queued','profile':'screen','sha':'a'*40}
        self.client.submit.side_effect=submit
        self.client.wait.return_value={'id':'retried','status':'failed','profile':'screen','sha':'a'*40}
        with patch('lab.agent_loop.github_status'),patch('lab.agent_loop._finish_record'):
            self.assertTrue(self.advance(time.monotonic()+60))
        self.client.submit.assert_called_once()

    def test_recovered_request_rejects_payload_mismatch(self):
        self.active.update(submitting_profile='screen',request_ids={'screen':'3'*32})
        self.client.request.return_value={'id':'wrong','sha':'b'*40}
        with self.assertRaisesRegex(RuntimeError,'different submission payload'):
            _recover_submission(self.active,self.args,self.client,self.state,self.status_file)
        self.client.submit.assert_not_called()

    def test_codex_failure_preserves_thread_identifier(self):
        process = Mock(returncode=1)
        def communicate(_prompt, timeout):
            (self.directory / 'turn-01.jsonl').write_text('{"type":"thread.started","thread_id":"saved-thread"}\n')
        process.communicate.side_effect = communicate
        with patch('lab.agent_loop.subprocess.Popen', return_value=process):
            with self.assertRaises(CodexTurnError) as raised:
                codex_turn(self.directory, self.directory, 1, 'prompt', None, 10)
        self.assertEqual(raised.exception.thread_id, 'saved-thread')

    def test_codex_timeout_preserves_thread_and_stops_process_group(self):
        process = Mock(returncode=-15)
        def communicate(_prompt, timeout):
            (self.directory / 'turn-02.jsonl').write_text('{"type":"thread.started","thread_id":"timeout-thread"}\n')
            raise subprocess.TimeoutExpired('codex', timeout)
        process.communicate.side_effect = communicate
        with patch('lab.agent_loop.subprocess.Popen', return_value=process), \
             patch('lab.agent_loop.terminate_group') as terminate:
            with self.assertRaises(CodexTurnError) as raised:
                codex_turn(self.directory, self.directory, 2, 'prompt', None, 0.1)
        self.assertTrue(raised.exception.timed_out)
        self.assertEqual(raised.exception.thread_id, 'timeout-thread')
        terminate.assert_called_once_with(process)


class AgentLoopIntegrationTests(unittest.TestCase):
    def test_two_candidates_keep_one_conversation_and_versioned_feedback(self):
        self.exercise_loop(2, 2)

    def test_no_count_limit_continues_past_four_candidates(self):
        self.exercise_loop(None, 5)

    def test_claude_uses_shared_queue_and_resumes_with_feedback(self):
        self.exercise_loop(2, 2, provider='claude')

    def exercise_loop(self, candidate_limit, expected_candidates, provider='codex'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, worktree, origin = root / 'repo', root / 'worktree', root / 'origin.git'
            repo.mkdir()
            git(repo, 'init', '-b', 'main')
            git(repo, 'config', 'user.name', 'Test')
            git(repo, 'config', 'user.email', 'test@example.invalid')
            (repo / 'differometor').mkdir()
            (repo / 'differometor/simulate.py').write_text('# baseline\n')
            (repo / 'experiments').mkdir()
            (repo / 'experiments/initial-agent.md').write_text('Try safe optimizations.\n')
            git(repo, 'add', '.')
            git(repo, 'commit', '-m', 'baseline')
            subprocess.run(['git', 'clone', '--bare', str(repo), str(origin)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            git(repo, 'remote', 'add', 'origin', str(origin))
            args = SimpleNamespace(repo=repo, worktree=worktree, name='trial', branch='explore/trial',
                direction='imports', resume=False, host='unused', github_repo='test/repo',
                max_minutes=1, max_candidates=candidate_limit, baseline_seconds=36.177949,
                agent_provider=provider, agent_model='claude-opus-5-5' if provider == 'claude' else None)
            calls = []
            submitted = {}
            client = Mock()
            def turn(folder, session, number, prompt, thread, timeout, lock_fds=(), model=None):
                self.assertEqual(model, args.agent_model)
                calls.append((thread, prompt))
                (folder / 'differometor/simulate.py').write_text(f'# candidate {number}\n')
                return 'same-thread', {'summary': f'Change {number}', 'hypothesis': 'faster',
                    'ready_for_evaluation': True, 'stop': number == expected_candidates, 'notes': ''}
            def submit(folder, branch, agent, direction, hypothesis, profile, sha, request_id=None):
                self.assertIsNotNone(request_id)
                job_id = f'job-{len(submitted) + 1}'
                job = {'id': job_id, 'sha': sha, 'profile': profile, 'status': 'queued'}
                submitted[job_id] = job
                return job
            def wait(job_id, timeout):
                job = submitted[job_id]
                return job | {'status': 'completed', 'result': {'first_run_seconds': 30,
                    'verdict': 'screened' if job['profile'] == 'screen' else 'validated'}}
            client.submit.side_effect = submit
            client.wait.side_effect = wait
            with patch('lab.agent_loop.Client', return_value=client), \
                 patch('lab.claude_turn.claude_turn' if provider == 'claude' else 'lab.agent_loop.codex_turn', side_effect=turn), \
                 patch('lab.agent_loop.github_status'):
                run(args)
            self.assertEqual(len(calls), expected_candidates)
            if candidate_limit is None:
                self.assertIn('There is no candidate-count limit', calls[4][1])
            self.assertIsNone(calls[0][0])
            self.assertEqual(calls[1][0], 'same-thread')
            self.assertIn('job-1', calls[1][1])
            self.assertEqual(len(submitted), expected_candidates * 2)
            reports = worktree / 'experiments/runs/trial'
            first = json.loads((reports / 'candidate-01.json').read_text())
            second = json.loads((reports / 'candidate-02.json').read_text())
            self.assertEqual(first['candidate_sha'], submitted['job-1']['sha'])
            self.assertEqual(second['candidate_sha'], submitted['job-3']['sha'])
            parent = git(worktree, 'rev-parse', second['candidate_sha'] + '^')
            self.assertEqual(git(worktree, 'show', '-s', '--format=%s', parent),
                             'Record evaluator feedback for ' + first['candidate_sha'][:12])
            state = json.loads((repo / '.lab/sessions/trial/status.json').read_text())
            self.assertEqual(state['status'], 'complete')
            self.assertEqual(state['thread_id'], 'same-thread')
            self.assertEqual(state['candidates'], expected_candidates)
            self.assertIsNone(state['active_candidate'])
            self.assertEqual(state['agent_provider'], provider)
            args.resume = True
            args.agent_provider = 'claude' if provider == 'codex' else 'codex'
            with self.assertRaisesRegex(ValueError, 'different agent provider'):
                run(args)
            args.agent_provider = provider
            args.resume = False
            with self.assertRaisesRegex(ValueError, 'already exists'):
                run(args)


if __name__ == "__main__":
    unittest.main()
