import json
import tempfile
import unittest
from pathlib import Path
from lab.claude_turn import command_for, parse_result
from lab.agent_loop import read_thread_id


class ClaudeTurnTests(unittest.TestCase):
    def test_restricted_tools_and_explicit_resume(self):
        cmd = command_for('saved-session', 'claude-opus-5-5')
        self.assertEqual(cmd[cmd.index('--model') + 1], 'claude-opus-5-5')
        self.assertIn('--restricted', cmd)
        self.assertIn('--safe-mode', cmd)
        self.assertIn('--strict-mcp-config', cmd)
        self.assertEqual(cmd[cmd.index('--permission-mode') + 1], 'dontAsk')
        self.assertNotIn('Bash', cmd[cmd.index('--tools') + 1])
        self.assertNotIn('Agent', cmd[cmd.index('--tools') + 1])
        self.assertEqual(cmd[-2:], ['--resume', 'saved-session'])
        self.assertNotIn('--resume', command_for())
        self.assertNotIn('--dangerously-skip-permissions', cmd)

    def test_structured_result_and_interrupted_session_identity(self):
        response = dict(summary='Checked', hypothesis='Sparse solve', notes='Unmeasured',
                        ready_for_evaluation=False, stop=True)
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / 'events.jsonl'
            events.write_text(json.dumps(dict(type='system', subtype='init', session_id='abc')) + '\n')
            self.assertEqual(read_thread_id(events), 'abc')
            with self.assertRaises(ValueError):
                parse_result(events)
            with events.open('a') as stream:
                stream.write(json.dumps(dict(type='result', subtype='success', session_id='abc',
                                             is_error=False, structured_output=response)) + '\n')
            self.assertEqual(parse_result(events), ('abc', response))

    def test_errors_and_invalid_schema_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / 'events.jsonl'
            for result in [dict(type='result', subtype='error_max_turns', is_error=True),
                           dict(type='result', subtype='success', structured_output={'stop': 'false'})]:
                events.write_text(json.dumps(result))
                with self.assertRaises(ValueError):
                    parse_result(events)
