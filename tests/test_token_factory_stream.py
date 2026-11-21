import io
import json
from http.client import IncompleteRead
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from lab.token_factory import TokenFactory


class Stream(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'text/event-stream'}


def events(*items, done=True):
    data = b''.join(b'data: ' + json.dumps(item).encode() + b'\n\n' for item in items)
    return Stream(data + (b'data: [DONE]\n\n' if done else b''))


def chunk(content=None, reasoning=None, finish=None):
    return {'choices': [{'index': 0, 'delta': {'content': content, 'reasoning': reasoning},
                         'finish_reason': finish}]}


class StreamingTests(unittest.TestCase):
    def test_complete_json_and_trailing_usage(self):
        stream = events(chunk(reasoning='private reasoning'), chunk('{"ok":'),
                        chunk('true}', finish='stop'), {'choices': [], 'usage': {'completion_tokens': 50}})
        with patch('lab.token_factory.urlopen', return_value=stream) as call:
            r = TokenFactory('secret').chat_stream([], response_format={'type': 'json_object'})
        self.assertTrue(r['usable_completion'])
        self.assertEqual(json.loads(r['data']['choices'][0]['message']['content']), {'ok': True})
        self.assertEqual(r['data']['usage']['completion_tokens'], 50)
        self.assertNotIn('private reasoning', json.dumps(r))
        self.assertEqual(r['reasoning_characters'], 17)
        body = json.loads(call.call_args.args[0].data)
        self.assertEqual(body['max_tokens'], 4096)
        self.assertEqual(body['reasoning_effort'], 'low')
        self.assertTrue(body['stream'])
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertTrue(stream.closed)

    def test_exhausted_reasoning_is_not_success(self):
        with patch('lab.token_factory.urlopen', return_value=events(chunk(reasoning='private', finish='length'))):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertEqual(r['data']['choices'][0]['finish_reason'], 'length')

    def test_truncated_connection_keeps_partial_answer_but_fails(self):
        with patch('lab.token_factory.urlopen', return_value=events(chunk('partial'), done=False)):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertIn('[DONE]', r['error'])
        self.assertEqual(r['data']['choices'][0]['message']['content'], 'partial')

    def test_http_throttle_no_retry_and_secret_redaction(self):
        error = HTTPError('https://example.invalid', 429, 'busy', {'Retry-After': '5'}, io.BytesIO(b'secret'))
        with patch('lab.token_factory.urlopen', side_effect=error) as call:
            r = TokenFactory('secret').chat_stream([])
        self.assertEqual(call.call_count, 1)
        self.assertFalse(r['usable_completion'])
        self.assertEqual(r['headers']['retry-after'], '5')
        self.assertNotIn('secret', json.dumps(r))

    def test_provider_error_after_http200(self):
        with patch('lab.token_factory.urlopen', return_value=events({'error': {'message': 'secret backend'}})):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertNotIn('secret', json.dumps(r))

    def test_multiline_data_and_comments(self):
        stream = Stream(b': heartbeat\n\nevent: message\ndata: {"choices":\ndata: [{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        with patch('lab.token_factory.urlopen', return_value=stream):
            r = TokenFactory('secret').chat_stream([])
        self.assertTrue(r['usable_completion'])

    def test_malformed_json_is_not_silently_ignored(self):
        with patch('lab.token_factory.urlopen', return_value=Stream(b'data: broken\n\ndata: [DONE]\n\n')):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertIn('error', r)

    def test_non_sse_http200_is_not_success(self):
        stream = Stream(b'not streaming');stream.headers = {'Content-Type': 'application/json'}
        with patch('lab.token_factory.urlopen', return_value=stream):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertIn('text/event-stream', r['error'])

    def test_oversize_line_is_bounded(self):
        with patch('lab.token_factory.urlopen', return_value=Stream(b'data: ' + b'x' * 65537)):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertIn('byte limit', r['error'])

    def test_duration_budget_stops_before_read(self):
        with patch('lab.token_factory.urlopen', return_value=events(chunk('ok', finish='stop'))), \
             patch('lab.token_factory.time.monotonic', side_effect=[0, 2, 3]):
            r = TokenFactory('secret').chat_stream([], max_seconds=1)
        self.assertFalse(r['usable_completion'])
        self.assertIn('duration', r['error'])

    def test_empty_stop_is_not_success(self):
        with patch('lab.token_factory.urlopen', return_value=events(chunk('', finish='stop'))):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])

    def test_bad_content_shape_returns_failure(self):
        with patch('lab.token_factory.urlopen', return_value=events(chunk(['not text'], finish='stop'))):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertIn('not text', r['error'])

    def test_incomplete_chunked_transport_keeps_partial_and_closes(self):
        class BrokenStream(Stream):
            reads = 0
            def readline(self, size=-1):
                self.reads += 1
                if self.reads == 3:
                    raise IncompleteRead(b'broken frame', 30)
                return super().readline(size)
        stream = BrokenStream(b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n')
        with patch('lab.token_factory.urlopen', return_value=stream):
            r = TokenFactory('secret').chat_stream([])
        self.assertFalse(r['usable_completion'])
        self.assertFalse(r['stream_done'])
        self.assertEqual(r['data']['choices'][0]['message']['content'], 'partial')
        self.assertIn('IncompleteRead', r['error'])
        self.assertTrue(stream.closed)

    def test_invalid_limits_rejected_before_network(self):
        with patch('lab.token_factory.urlopen') as call:
            for tokens in (True, False, 0, -1, 1.5, float('nan'), float('inf'), '4096'):
                with self.subTest(max_tokens=tokens), self.assertRaises(ValueError):
                    TokenFactory('secret').chat_stream([], max_tokens=tokens)
            for duration in (True, False, 0, -1, float('nan'), float('inf'), -float('inf'), '30'):
                with self.subTest(max_seconds=duration), self.assertRaises(ValueError):
                    TokenFactory('secret').chat_stream([], max_seconds=duration)
            call.assert_not_called()

if __name__ == '__main__':
    unittest.main()
