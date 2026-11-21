import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lab.host_broker import Broker, checked_path, load_artifact, validate_response, validate_task
from lab.evaluator_ssh_relay import classify, REQUEST
import shlex


def assignment():
    return {
        'schema_version': 'feyer-dag-task-v1', 'task_id': '1' * 32,
        'campaign_id': 'test-campaign', 'round_id': 'round:1', 'round_spec_sha256': 'a' * 64,
        'parent_candidates': [{'candidate_id': 'seed8', 'commit_sha': 'b' * 40}],
        'context': {'path': 'context.json', 'sha256': 'c' * 64, 'commit_sha': 'd' * 40},
        'brief': {'path': 'brief.md', 'sha256': 'e' * 64, 'commit_sha': 'f' * 40},
        'ownership': {'actor': 'hetzner-codex-1', 'claim_version': 1, 'branch': 'explore/hetzner/test'},
        'provider': {'name': 'codex', 'model_policy': 'specified', 'model': 'gpt-6-astra', 'reasoning': 'high'},
        'budget': {'deadline_unix': 2000, 'max_turns': 1}, 'kind': 'guidance',
        'allowed_paths': ['experiments/notes/**'], 'output_schema': 'feyer-dag-proposal-v1',
    }


class ContractTests(unittest.TestCase):
    def test_pinned_assignment_and_explicit_inheritance(self):
        task = assignment()
        validate_task(task, 'hetzner-codex-1', now=1000)
        task['provider'].update(model_policy='inherit-designated-config', model=None, reasoning=None)
        validate_task(task, 'hetzner-codex-1', now=1000)

    def test_reject_scope_budget_owner_and_traversal(self):
        changes = [
            ('task_id', '../outside'), ('allowed_paths', ['lab/**']),
            ('budget', {'deadline_unix': 900, 'max_turns': 1}),
            ('budget', {'deadline_unix': 2000, 'max_turns': 2}),
            ('ownership', {'actor': 'other', 'claim_version': 1, 'branch': 'explore/hetzner/test'}),
            ('ownership', {'actor': 'hetzner-codex-1', 'claim_version': 1, 'branch': 'main'}),
            ('context', {'path': '../secret', 'sha256': 'c' * 64, 'commit_sha': 'd' * 40}),
            ('allowed_paths', ['differometor/**', 'experiments/notes/**']),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises((ValueError, KeyError)):
                task = assignment(); task[key] = value
                validate_task(task, 'hetzner-codex-1', now=1000)

    def test_artifact_uses_immutable_commit_and_verifies_bytes(self):
        raw = b'context'
        spec = {'path': 'context.json', 'sha256': hashlib.sha256(raw).hexdigest(), 'commit_sha': 'a' * 40}
        with patch('lab.host_broker.git', side_effect=[b'', raw]) as mocked:
            self.assertEqual(load_artifact('/repo', 'b' * 40, spec), 'context')
            self.assertEqual(mocked.call_args.args[2], 'a' * 40 + ':context.json')
        with patch('lab.host_broker.git', side_effect=[b'', b'changed']), self.assertRaises(ValueError):
            load_artifact('/repo', 'b' * 40, spec)

    def test_output_has_typed_parameters_and_readiness(self):
        response = dict(summary='ok', hypothesis='test', heuristic_id='audit',
                        parameters_before_json='{}', parameters_after_json='{}',
                        notes='not measured', ready_for_evaluation=False)
        validate_response(response)
        response['parameters_after_json'] = '[]'
        with self.assertRaises(ValueError): validate_response(response)
        response['parameters_after_json'] = '{}'; response['ready_for_evaluation'] = 'true'
        with self.assertRaises(ValueError): validate_response(response)

    def test_failed_or_interrupted_task_never_restarts_agent(self):
        task = assignment(); raw = json.dumps(task).encode()
        with tempfile.TemporaryDirectory() as tmp:
            broker = Broker.__new__(Broker); broker.root = Path(tmp)
            broker.config = {}; broker.actor = 'hetzner-codex-1'
            directory = Path(tmp) / 'tasks' / task['task_id']; directory.mkdir(parents=True)
            state = {'status': 'running', 'task_sha256': hashlib.sha256(raw).hexdigest()}
            (directory / 'state.json').write_text(json.dumps(state))
            with patch.object(broker, 'turn') as turn, patch.object(broker, 'failure_outbox'):
                broker.execute(task, raw, 'c' * 40, 1)
                turn.assert_not_called()
            self.assertEqual(json.loads((directory / 'state.json').read_text())['status'], 'interrupted')

    def test_publish_retry_reuses_commit_and_does_not_rerun(self):
        task = assignment(); raw = json.dumps(task).encode()
        with tempfile.TemporaryDirectory() as tmp:
            broker = Broker.__new__(Broker); broker.root = Path(tmp)
            directory = Path(tmp) / 'tasks' / task['task_id']; directory.mkdir(parents=True)
            state = {'status': 'publishing', 'task_sha256': hashlib.sha256(raw).hexdigest(), 'receipt_sha': 'a' * 40}
            (directory / 'state.json').write_text(json.dumps(state))
            with patch.object(broker, 'publish') as publish, patch.object(broker, 'turn') as turn:
                broker.execute(task, raw, 'c' * 40, 1)
                publish.assert_called_once(); turn.assert_not_called()

    def test_mutated_assignment_cannot_reuse_task_id(self):
        task = assignment(); raw = json.dumps(task).encode()
        with tempfile.TemporaryDirectory() as tmp:
            broker = Broker.__new__(Broker); broker.root = Path(tmp)
            directory = Path(tmp) / 'tasks' / task['task_id']; directory.mkdir(parents=True)
            (directory / 'state.json').write_text(json.dumps({'status': 'complete', 'task_sha256': '0' * 64}))
            with self.assertRaises(ValueError): broker.execute(task, raw, 'c' * 40, 1)


class RelayTests(unittest.TestCase):
    def test_trusted_rpc_and_upload(self):
        self.assertEqual(classify(shlex.join(REQUEST)), ('request', None))
        self.assertEqual(classify('mkdir -p /workspace/feyer-lab/incoming && cat > /workspace/feyer-lab/incoming/' + 'a' * 32 + '.bundle'), ('upload', 'a' * 32))

    def test_reject_shell_and_modified_evaluator(self):
        for command in ['bash', 'id', shlex.join(REQUEST) + '; id',
                        shlex.join(REQUEST).replace('/control', '/untrusted'),
                        'mkdir -p /workspace/feyer-lab/incoming && cat > /root/.ssh/authorized_keys']:
            with self.subTest(command=command), self.assertRaises(ValueError): classify(command)


if __name__ == '__main__':
    unittest.main()
