import concurrent.futures
import sqlite3
import subprocess
import tempfile
import time
import uuid
import unittest
from pathlib import Path

from lab.queue import Queue


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True, stderr=subprocess.PIPE).strip()


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "source.py").write_text("original\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "baseline")
        self.sha = git(self.repo, "rev-parse", "HEAD")
        self.queue = Queue(self.root / "state", self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def enqueue(self, **kwargs):
        return self.queue.enqueue(self.sha, "main", "agent-a", "imports", **kwargs)

    def test_pins_sha_when_branch_moves_and_preserves_metadata(self):
        job = self.enqueue(hypothesis="Lazy import", profile="screen")
        (self.repo / "source.py").write_text("later\n")
        git(self.repo, "commit", "-am", "later")
        self.assertNotEqual(git(self.repo, "rev-parse", "main"), self.sha)
        self.assertEqual(git(self.repo, "rev-parse", f"refs/candidates/{job['id']}"), self.sha)
        reread = Queue(self.root / "state", self.repo).get(job["id"])
        self.assertEqual(reread["hypothesis"], "Lazy import")
        self.assertEqual(reread["sha"], self.sha)

    def test_concurrent_claims_are_unique(self):
        expected = {self.enqueue()["id"] for _ in range(12)}
        def claim(index):
            return Queue(self.root / "state", self.repo).claim(f"worker-{index}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            claimed = list(pool.map(claim, range(12)))
        self.assertEqual({job["id"] for job in claimed}, expected)
        self.assertIsNone(self.queue.claim("extra"))

    def test_worker_ownership_and_finished_result_survive_reopen(self):
        job = self.enqueue()
        self.queue.claim("owner")
        with self.assertRaises(RuntimeError):
            self.queue.heartbeat(job["id"], "other")
        with self.assertRaises(RuntimeError):
            self.queue.finish(job["id"], "other", "completed")
        self.queue.finish(job["id"], "owner", "completed", result={"verdict": "screened"})
        self.assertEqual(Queue(self.root / "state", self.repo).get(job["id"])["result"]["verdict"], "screened")
        with self.assertRaises(RuntimeError):
            self.queue.finish(job["id"], "owner", "failed")

    def test_stale_claim_is_interrupted_not_requeued(self):
        job = self.enqueue()
        self.queue.claim("gone")
        with sqlite3.connect(self.queue.db_path) as db:
            db.execute("UPDATE jobs SET updated_at=? WHERE id=?", (time.time() - 1000, job["id"]))
        self.assertEqual(self.queue.recover_stale(120), [job["id"]])
        self.assertEqual(self.queue.get(job["id"])["status"], "interrupted")
        self.assertIsNone(self.queue.claim("replacement"))

    def test_rejects_bad_inputs_and_noncommit_objects(self):
        for sha in ("HEAD", "abc", "-" + "a" * 39, "a" * 40 + ";echo bad"):
            with self.assertRaises(ValueError):
                self.queue.enqueue(sha, "main", "a", "d")
        for branch in ("--help", "@{-1}", "bad name"):
            with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                self.queue.enqueue(self.sha, branch, "a", "d")
        tree = git(self.repo, "rev-parse", "HEAD^{tree}")
        with self.assertRaises(ValueError):
            self.queue.enqueue(tree, "main", "a", "d")
        with self.assertRaises(ValueError):
            self.enqueue(profile="shell")

    def test_independent_reruns_remain_separate(self):
        first, second = self.enqueue(), self.enqueue()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(self.queue.list_jobs()), 2)

    def test_same_request_id_returns_original_job_after_reopen(self):
        request_id=str(uuid.uuid4())
        first=self.enqueue(request_id=request_id,hypothesis='one')
        reopened=Queue(self.root/'state',self.repo)
        second=reopened.enqueue(self.sha,'main','agent-a','imports',hypothesis='one',request_id=request_id)
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(second['request_id'],uuid.UUID(request_id).hex)
        self.assertEqual(len(reopened.list_jobs()),1)
        self.assertEqual(len(reopened.events(first['id'])),1)

    def test_request_id_payload_conflict_is_rejected(self):
        request_id=uuid.uuid4().hex
        self.enqueue(request_id=request_id,hypothesis='original')
        for changes in ({'hypothesis':'changed'},{'profile':'full'}):
            with self.assertRaisesRegex(ValueError,'different submission payload'):
                self.enqueue(request_id=request_id,**changes)
        self.assertEqual(len(self.queue.list_jobs()),1)

    def test_concurrent_duplicate_submissions_create_one_job_and_ref(self):
        request_id=uuid.uuid4().hex
        def submit(_):
            return Queue(self.root/'state',self.repo).enqueue(self.sha,'main','agent-a','imports',request_id=request_id)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(submit,range(12)))
        self.assertEqual(len({job['id'] for job in results}),1)
        self.assertEqual(len(self.queue.list_jobs()),1)
        refs=git(self.repo,'for-each-ref','--format=%(refname)','refs/candidates').splitlines()
        self.assertEqual(len(refs),1)

    def test_legacy_database_migration_preserves_jobs_and_allows_null_ids(self):
        legacy=self.root/'legacy';legacy.mkdir()
        with sqlite3.connect(legacy/'queue.sqlite3') as db:
            db.execute('''CREATE TABLE jobs (id TEXT PRIMARY KEY, sha TEXT NOT NULL, branch TEXT NOT NULL,
                agent TEXT NOT NULL, direction TEXT NOT NULL, hypothesis TEXT NOT NULL, profile TEXT NOT NULL,
                status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                started_at REAL, finished_at REAL, worker_id TEXT, result_json TEXT, error TEXT)''')
            db.execute('INSERT INTO jobs (id,sha,branch,agent,direction,hypothesis,profile,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       ('old',self.sha,'main','agent-a','imports','','screen','queued',1,1))
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            instances=list(pool.map(lambda _:Queue(legacy,self.repo),range(12)))
        migrated=instances[0]
        self.assertIsNone(migrated.get('old')['request_id'])
        one=migrated.enqueue(self.sha,'main','agent-a','imports')
        two=migrated.enqueue(self.sha,'main','agent-a','imports')
        self.assertNotEqual(one['id'],two['id'])
        self.assertEqual(len(Queue(legacy,self.repo).list_jobs()),3)

    def test_request_lookup_and_validation(self):
        self.assertIsNone(self.queue.get_by_request_id(uuid.uuid4().hex))
        for value in ('not-a-uuid','a'*40,42):
            with self.assertRaises(ValueError):self.enqueue(request_id=value)


if __name__ == "__main__":
    unittest.main()
