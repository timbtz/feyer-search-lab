import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lab.agent_loop import (_run_locked, SHARED_EVIDENCE_MAX_BYTES, SHARED_EVIDENCE_SCHEMA,
                            snapshot_shared_evidence)


def frontier(number=1):
    value = dict(schema=SHARED_EVIDENCE_SCHEMA, generated_at=1000. + number,
                source_provenance={'team_digest': 'a'*64, 'policy_digest': 'b'*64,
                                   'evidence_digest': 'c'*64, 'collector': 'trusted-local-artifacts-v1',
                                   'instance': 'amd'},
                groups=[{'instance': 'amd', 'cohort_digest': 'c' * 64,
                         'points': [{'sha': 'a' * 40, 'source': 'raw-job-' + str(number)}]}],
                failures=[], unranked=[], declared_combinations=[])
    value['content_digest'] = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                                       allow_nan=False).encode()).hexdigest()
    return value


def response():
    return dict(summary='change', hypothesis='own hypothesis', notes='', ready_for_evaluation=True, stop=False)


class SharedEvidenceTests(unittest.TestCase):
    def test_snapshot_retains_exact_original_bytes_timestamp_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'frontier.json'
            raw = (json.dumps(frontier(), indent=3) + '\n').encode()
            path.write_bytes(raw)
            text, receipt = snapshot_shared_evidence(path, root/'session')
            self.assertEqual(text.encode(), raw)
            self.assertEqual(receipt['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt['generated_at'], 1001.)
            self.assertEqual(receipt['content_digest'], frontier()['content_digest'])
            self.assertEqual(receipt['source_provenance'], frontier()['source_provenance'])
            self.assertEqual(receipt['source_path'], str(path))
            self.assertEqual(Path(receipt['snapshot_ref']).read_bytes(), raw)
            self.assertIn('raw-job-1', text)

    def test_bad_json_schema_nonfinite_duplicate_and_oversize_fail_closed(self):
        malformed = [b'{', b'[]', b'{"schema":NaN}', b'{"x":1,"x":2}',
                     b' ' * (SHARED_EVIDENCE_MAX_BYTES + 1)]
        for mutate in (lambda x: x.update(schema='other'),
                       lambda x: x.update(generated_at=float('inf')),
                       lambda x: x.update(content_digest='bad'),
                       lambda x: x.update(content_digest='0'*64),
                       lambda x: x.pop('source_provenance'),
                       lambda x: x.update(groups={}),
                       lambda x: x.update(groups=['not-an-object']),
                       lambda x: x.pop('failures')):
            value = frontier()
            mutate(value)
            malformed.append(json.dumps(value).encode())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for raw in malformed:
                with self.subTest(raw=raw[:60]):
                    path = root/'bad.json'
                    path.write_bytes(raw)
                    with self.assertRaises(ValueError):
                        snapshot_shared_evidence(path, root/'session')
            self.assertFalse((root/'session/shared-evidence').exists())

    def test_independent_rejects_flag_and_saved_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root/'status.json'
            args = SimpleNamespace(resume=False, feedback_mode='evidence-only', shared_evidence=root/'missing')
            with self.assertRaisesRegex(ValueError, 'reject shared evidence'):
                _run_locked(args, root, root, root, status, ())
            args = SimpleNamespace(resume=True, feedback_mode='evidence-only')
            for extra in ({'shared_evidence_path': '/old/path'},
                          {'pending_turn': {'agent_context': {'shared_evidence': {'sha256': 'a'*64}}}}):
                status.write_text(json.dumps(dict(feedback_mode='evidence-only', **extra)))
                with self.assertRaisesRegex(ValueError, 'reject shared evidence'):
                    _run_locked(args, root, root, root, status, ())

    def test_new_turn_refreshes_snapshot_and_pending_recovery_keeps_old_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = root/'frontier.json'
            shared.write_text(json.dumps(frontier(1)))
            brief = root/'brief.md'
            brief.write_text('Research with measured evidence.')
            session = root/'session'
            session.mkdir()
            status = session/'status.json'
            args = SimpleNamespace(resume=False, feedback_mode='guided', shared_evidence=shared,
                branch='explore/test', direction='test', name='test', max_minutes=1,
                max_candidates=2, host='unused', brief=brief)
            pending_receipts, prompts = [], []
            def git(_root, *command):
                return args.branch if command == ('branch', '--show-current') else 'a' * 40
            def turn(_worktree, _session, number, prompt, thread, timeout, lock_fds=()):
                prompts.append(prompt)
                return 'same-thread', response()
            def commit(pending, _args, _worktree, state, _status):
                pending_receipts.append(copy.deepcopy(pending))
                state.update(candidates=pending['iteration'], pending_turn=None)
                shared.write_text(json.dumps(frontier(2)))
                return {'saved': True}
            with patch('lab.agent_loop.git', side_effect=git), patch('lab.agent_loop.changed_paths', return_value=[]), \
                 patch('lab.agent_loop.Client'), patch('lab.agent_loop.codex_turn', side_effect=turn), \
                 patch('lab.agent_loop._commit_candidate', side_effect=commit):
                _run_locked(args, root, root, session, status, ())
            self.assertEqual(len(prompts), 2)
            self.assertIn('raw-job-1', prompts[0])
            self.assertNotIn('raw-job-2', prompts[0])
            self.assertIn('raw-job-2', prompts[1])
            first, second = [p['input_receipt']['shared_evidence'] for p in pending_receipts]
            self.assertNotEqual(first['sha256'], second['sha256'])
            for pending in pending_receipts:
                receipt = pending['input_receipt']
                self.assertEqual(receipt['shared_evidence'], pending['agent_context']['shared_evidence'])
                self.assertEqual(hashlib.sha256(Path(receipt['shared_evidence']['snapshot_ref']).read_bytes()).hexdigest(),
                                 receipt['shared_evidence']['sha256'])
                self.assertEqual(json.loads(Path(receipt['path']).read_text())['shared_evidence'], receipt['shared_evidence'])
            # A parsed prior turn must be committed with its original frozen
            # context even when the live file is now malformed or unavailable.
            state = json.loads(status.read_text())
            state.update(pending_turn=pending_receipts[0], candidates=0)
            status.write_text(json.dumps(state))
            shared.write_text('invalid now')
            args.resume = True
            with patch('lab.agent_loop.git', side_effect=git), patch('lab.agent_loop.Client'), \
                 patch('lab.agent_loop.snapshot_shared_evidence') as read, \
                 patch('lab.agent_loop.codex_turn') as provider, \
                 patch('lab.agent_loop._commit_candidate', return_value=None) as recover:
                _run_locked(args, root, root, session, status, ())
            read.assert_not_called()
            provider.assert_not_called()
            self.assertEqual(recover.call_args.args[0]['input_receipt'], pending_receipts[0]['input_receipt'])
            self.assertEqual(recover.call_args.args[0]['agent_context'], pending_receipts[0]['agent_context'])


if __name__ == '__main__':
    unittest.main()
