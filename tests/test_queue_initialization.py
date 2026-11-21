import fcntl
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lab.queue import Queue, initialization_lock


class QueueInitializationTests(unittest.TestCase):
    def test_lock_precedes_sqlite_open_and_releases_after_constructor_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = Queue._connect
            def connect(queue):
                with (root / 'queue-init.lock').open('a+') as probe:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return original(queue)
            with patch.object(Queue, '_connect', connect):
                Queue(root, root / 'repo.git')
            with patch.object(Queue, '_connect', side_effect=RuntimeError('connection failed')):
                with self.assertRaisesRegex(RuntimeError, 'connection failed'):
                    Queue(root, root / 'repo.git')
            with initialization_lock(root, timeout=0):
                pass
            self.assertEqual(Queue(root, root / 'repo.git').list_jobs(), [])

    def test_lock_contention_is_bounded_and_does_not_release_the_other_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with initialization_lock(root):
                for _ in range(2):
                    with self.assertRaisesRegex(TimeoutError, 'initialization is busy'):
                        with initialization_lock(root, timeout=0):
                            self.fail('A second initializer acquired the lock')
            with initialization_lock(root, timeout=0):
                pass

    def test_independent_processes_migrate_legacy_database_without_losing_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'queue.sqlite3'
            with sqlite3.connect(database) as db:
                db.execute('''CREATE TABLE jobs (
                    id TEXT PRIMARY KEY, sha TEXT NOT NULL, branch TEXT NOT NULL,
                    agent TEXT NOT NULL, direction TEXT NOT NULL, hypothesis TEXT NOT NULL,
                    profile TEXT NOT NULL, status TEXT NOT NULL,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    started_at REAL, finished_at REAL, worker_id TEXT,
                    result_json TEXT, error TEXT)''')
                db.execute('INSERT INTO jobs (id,sha,branch,agent,direction,hypothesis,profile,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           ('legacy', 'a' * 40, 'main', 'test', 'test', '', 'screen', 'queued', 1, 1))
            command = [sys.executable, '-c',
                       'import sys; from lab.queue import Queue; Queue(sys.argv[1], sys.argv[2])',
                       str(root), str(root / 'repo.git')]
            processes = [subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                         for _ in range(12)]
            try:
                for process in processes:
                    _, error = process.communicate(timeout=35)
                    self.assertEqual(process.returncode, 0, error.decode())
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            queue = Queue(root, root / 'repo.git')
            self.assertEqual(len(queue.list_jobs()), 1)
            self.assertIsNone(queue.get('legacy')['request_id'])
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
                self.assertIn('jobs_request_id', {r[1] for r in db.execute('PRAGMA index_list(jobs)')})


if __name__ == '__main__':
    unittest.main()
