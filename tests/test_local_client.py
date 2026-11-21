import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

from lab.client import git
from lab.local_client import LocalClient
from lab.queue import Queue


class LocalClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'candidate'
        self.lab = self.root / 'evaluation'
        self.lab.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'explore/test', str(self.repo)], check=True)
        git(self.repo, 'config', 'user.name', 'Test')
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        (self.repo / 'file').write_text('baseline')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'baseline')
        self.baseline = git(self.repo, 'rev-parse', 'HEAD')
        subprocess.run(['git', 'clone', '-q', '--bare', str(self.repo), str(self.lab / 'repo.git')], check=True)
        (self.repo / 'file').write_text('candidate')
        git(self.repo, 'commit', '-qam', 'candidate')
        self.sha = git(self.repo, 'rev-parse', 'HEAD')
        trusted = self.lab / 'control' / 'lab'
        trusted.mkdir(parents=True)
        source = Path(__file__).resolve().parents[1] / 'lab'
        for name in ('__init__.py', 'remote.py', 'queue.py', 'worker.py', 'resources.py'):
            shutil.copy2(source / name, trusted / name)
        self.client = LocalClient(self.lab, sys.executable)
        self.patch_baseline = patch('lab.local_client.BASELINE_SHA', self.baseline)
        self.patch_baseline.start()

    def tearDown(self):
        self.patch_baseline.stop()
        self.temp.cleanup()

    def submit(self, **kwargs):
        return self.client.submit(self.repo, 'explore/test', 'test-agent', 'direction',
                                  'hypothesis', publish=False, **kwargs)

    def test_exact_candidate_and_idempotent_retry_share_existing_queue(self):
        request_id = str(uuid.uuid4())
        first = self.submit(request_id=request_id)
        second = self.submit(request_id=request_id)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['sha'], self.sha)
        self.assertEqual(first['request_id'], uuid.UUID(request_id).hex)
        jobs = self.client.request({'action': 'list'})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(git(self.lab / 'repo.git', 'rev-parse', 'refs/candidates/' + first['id']), self.sha)
        self.assertEqual(git(self.repo, 'for-each-ref', '--format=%(refname)', 'refs/lab/export/'), '')
        self.assertEqual(list((self.lab / 'incoming').iterdir()), [])

    def test_same_request_with_changed_payload_is_rejected(self):
        request_id = uuid.uuid4().hex
        self.submit(request_id=request_id)
        with self.assertRaisesRegex(ValueError, 'different submission payload'):
            self.client.submit(self.repo, 'explore/test', 'test-agent', 'direction',
                               'different hypothesis', publish=False, request_id=request_id)
        self.assertEqual(len(self.client.request({'action': 'list'})), 1)

    def test_lost_ingest_response_is_recovered_without_duplicate_job(self):
        request_id = uuid.uuid4().hex
        real_request = self.client.request

        def lose_ingest_reply(data):
            result = real_request(data)
            if data['action'] == 'ingest':
                raise subprocess.TimeoutExpired(['trusted-remote'], 120)
            return result

        self.client.request = lose_ingest_reply
        with self.assertRaises(subprocess.TimeoutExpired):
            self.submit(request_id=request_id)
        self.client.request = real_request
        recovered = self.submit(request_id=request_id)
        jobs = real_request({'action': 'list'})
        self.assertEqual([job['id'] for job in jobs], [recovered['id']])
        self.assertEqual(git(self.repo, 'for-each-ref', '--format=%(refname)', 'refs/lab/export/'), '')

    def test_missing_trusted_deployment_is_not_replaced_with_candidate_code(self):
        shutil.rmtree(self.lab / 'control')
        with self.assertRaises(FileNotFoundError):
            self.client.request({'action': 'list'})

    def test_only_deployed_remote_is_executed_even_with_candidate_pythonpath(self):
        fake = self.repo / 'lab'
        fake.mkdir()
        (fake / '__init__.py').write_text('')
        marker = self.root / 'UNTRUSTED_EXECUTED'
        (fake / 'remote.py').write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
        with patch.dict(os.environ, {'PYTHONPATH': str(self.repo)}):
            self.assertEqual(self.client.request({'action': 'list'}), [])
        self.assertFalse(marker.exists())

    def test_wait_and_fetch_use_existing_protocol_without_worker_or_ssh(self):
        job = self.submit(request_id=uuid.uuid4().hex)
        queue = Queue(self.lab / 'state', self.lab / 'repo.git')
        self.assertEqual(queue.claim('test-worker')['id'], job['id'])
        queue.finish(job['id'], 'test-worker', 'completed', result={'test': True})
        artifacts = self.lab / 'runs' / job['id']
        artifacts.mkdir(parents=True)
        (artifacts / 'report.json').write_text(json.dumps({'test': True}))
        self.assertEqual(self.client.wait(job['id'], timeout=1)['status'], 'completed')
        target = self.root / 'download'
        self.client.fetch(job['id'], target)
        self.assertEqual(json.loads((target / 'report.json').read_text()), {'test': True})

    def test_request_failure_does_not_publish_or_bundle(self):
        self.client.request = Mock(side_effect=RuntimeError('unsupported trusted release'))
        with patch('lab.local_client.publish_candidate') as publish:
            with self.assertRaisesRegex(RuntimeError, 'unsupported'):
                self.client.submit(self.repo, 'explore/test', 'a', 'd', 'h', request_id=uuid.uuid4().hex)
        publish.assert_not_called()
        self.assertEqual(git(self.repo, 'for-each-ref', '--format=%(refname)', 'refs/lab/export/'), '')

    def test_validation_happens_before_side_effects(self):
        for root in ('relative', '/workspace/../root'):
            with self.assertRaises(ValueError):
                LocalClient(root)
        with self.assertRaises(ValueError):
            LocalClient('/workspace/feyer-lab', python_path='python')
        with patch('lab.local_client.git') as command:
            with self.assertRaises(ValueError):
                self.submit(request_id='not-an-id')
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
