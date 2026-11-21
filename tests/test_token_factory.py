import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from lab.token_factory import TokenFactory, probe, settings, summarize_response


class TokenFactoryTests(unittest.TestCase):
    def test_environment_overrides_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('RADEON_API_KEY="file-secret"\nRADEON_MODEL=file-model\n')
            with patch.dict('os.environ', {'RADEON_API_KEY': 'env-secret'}, clear=True):
                self.assertEqual(settings(path), ('env-secret', 'file-model'))

    def test_http_error_preserves_throttle_and_redacts_key(self):
        error = HTTPError('https://example.invalid', 429, 'Too many requests',
                          {'Retry-After': '10'}, io.BytesIO(b'{"error":"secret-key"}'))
        with patch('lab.token_factory.urlopen', side_effect=error):
            result = TokenFactory('secret-key').chat([{'role': 'user', 'content': 'OK'}])
        self.assertEqual(result['status'], 429)
        self.assertEqual(result['headers']['retry-after'], '10')
        self.assertNotIn('secret-key', json.dumps(result))

    def test_summary_omits_hidden_reasoning(self):
        result = summarize_response({'status': 200, 'data': {'choices': [
            {'message': {'content': 'OK', 'reasoning_content': 'private'}, 'finish_reason': 'stop'}]}})
        self.assertEqual(result['content_characters'], 2)
        self.assertNotIn('private', json.dumps(result))

    def test_probe_stops_on_throttle(self):
        class Client:
            model = 'fake'
            def chat(self, messages):
                return {'status': 429, 'latency_seconds': .1,
                        'headers': {'retry-after': '10'}, 'data': {'error': 'limit'}}
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            result = probe(Client(), [1, 2, 4], Path(directory) / 'result.json')
        self.assertEqual(len(result['batches']), 1)
        self.assertEqual(result['highest_all_200_concurrency'], 0)
        self.assertEqual(result['batches'][0]['http_429'], 1)

    def test_probe_rejects_excessive_concurrency(self):
        with self.assertRaises(ValueError):
            probe(None, [64], 'unused.json')


if __name__ == '__main__':
    unittest.main()
