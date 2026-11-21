import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

from lab.queue import Queue
from lab.remote import handle


def git(path,*args):
    return subprocess.check_output(['git','-C',str(path),*args],text=True,stderr=subprocess.PIPE).strip()


class RemoteIdempotenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir()
        git(self.source,'init','-b','main');git(self.source,'config','user.name','Test')
        git(self.source,'config','user.email','test@example.invalid')
        (self.source/'source.py').write_text('initial\n');git(self.source,'add','.');git(self.source,'commit','-m','baseline')
        self.sha=git(self.source,'rev-parse','HEAD')
        git(self.root,'clone','--bare',str(self.source),str(self.root/'repo.git'))
        (self.root/'incoming').mkdir()
        self.request_id=uuid.uuid4().hex

    def tearDown(self):self.temp.cleanup()

    def request(self):
        transfer=uuid.uuid4().hex;ref=f'refs/lab/export/{transfer}'
        git(self.source,'update-ref',ref,self.sha)
        bundle=self.root/'incoming'/f'{transfer}.bundle'
        git(self.source,'bundle','create',str(bundle),ref)
        return {'action':'ingest','transfer':transfer,'bundle_sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),
                'sha':self.sha,'branch':'main','agent':'test','direction':'imports','hypothesis':'faster',
                'profile':'screen','request_id':self.request_id}

    def test_retry_after_enqueue_and_cleanup_returns_existing_job_without_bundle(self):
        request=self.request()
        first=handle(self.root,request)
        self.assertFalse((self.root/'incoming'/f"{request['transfer']}.bundle").exists())
        # Simulate losing the first response after enqueue and bundle cleanup.
        second=handle(self.root,request)
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(handle(self.root,{'action':'lookup_request','request_id':self.request_id})['id'],first['id'])
        self.assertEqual(len(Queue(self.root/'state',self.root/'repo.git').list_jobs()),1)

    def test_new_upload_for_same_request_is_cleaned_and_not_requeued(self):
        first=handle(self.root,self.request());retry=self.request()
        second=handle(self.root,retry)
        self.assertEqual(first['id'],second['id'])
        self.assertFalse((self.root/'incoming'/f"{retry['transfer']}.bundle").exists())
        self.assertEqual(git(self.root/'repo.git','for-each-ref','--format=%(refname)','refs/transfers'),'')

    def test_conflicting_retry_is_rejected_and_upload_cleaned(self):
        handle(self.root,self.request());conflict=self.request();conflict['hypothesis']='different'
        with self.assertRaisesRegex(ValueError,'different submission payload'):handle(self.root,conflict)
        self.assertFalse((self.root/'incoming'/f"{conflict['transfer']}.bundle").exists())
        self.assertEqual(len(Queue(self.root/'state',self.root/'repo.git').list_jobs()),1)

    def test_lookup_before_enqueue_returns_none(self):
        self.assertIsNone(handle(self.root,{'action':'lookup_request','request_id':self.request_id}))
        job=handle(self.root,self.request())
        self.assertEqual(job['request_id'],self.request_id)


if __name__=='__main__':unittest.main()
