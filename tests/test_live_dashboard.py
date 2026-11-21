import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from lab.evolution import Campaign
from lab.live_dashboard import Observatory, ReadOnlyCampaign, public, process_status, job_summary, tail


class ObservatoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.directory = self.root/'.lab/campaigns/test'
        self.directory.mkdir(parents=True)
        self.path = self.directory/'campaign.sqlite3'
        self.campaign = Campaign(self.path)
        self.token = self.campaign.initialize(dict(campaign_id='test', budget=dict(max_proposals=20,
            max_evaluations=20, max_model_calls=0, deadline_unix=time.time()+600)), 'owner')
        self.obs = Observatory(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_cannot_write_or_leak_claim_tokens(self):
        reader = ReadOnlyCampaign(self.path)
        before = self.campaign.events()
        encoded = json.dumps(reader.snapshot())
        self.assertNotIn('token_hash', encoded)
        self.assertNotIn(self.token, encoded)
        with reader._connect() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("INSERT INTO claims VALUES('evil',1,'coordinator','hash','owner',0)")
        self.assertEqual(before, self.campaign.events())

    def test_missing_database_is_not_created(self):
        missing = self.root/'missing.sqlite3'
        with self.assertRaises(sqlite3.OperationalError):
            ReadOnlyCampaign(missing).snapshot()
        self.assertFalse(missing.exists())

    def test_new_committed_events_visible_and_no_model_calls(self):
        first = self.obs.state()['campaigns'][0]
        self.campaign.record_decision('owner', self.token, 'review', {'reason':'no new jobs'})
        second = self.obs.state()['campaigns'][0]
        self.assertEqual(len(second['events']),len(first['events'])+1)
        self.assertEqual(second['usage']['model_calls'],0)
        self.assertEqual(second['status'],'unknown')

    def test_disk_error_log_does_not_invent_running_state(self):
        (self.directory/'controller.log').write_text('OSError: No space left on device\n')
        (self.directory/'STOP').write_text('drain')
        (self.directory/'launch.json').write_text(json.dumps({'pid':123}))
        with patch('lab.live_dashboard.process_status',return_value=False):
            c=self.obs.campaign(self.directory)
        self.assertEqual(c['status'],'stopped')
        self.assertFalse(c['alerts'])  # An old log error does not undo reconciled state.

    def test_spent_evaluation_budget_is_distinct_from_unknown_liveness(self):
        snapshot=self.campaign.snapshot()
        snapshot['usage']['evaluations']=20
        with patch.object(ReadOnlyCampaign,'snapshot',return_value=snapshot):
            self.assertEqual(self.obs.campaign(self.directory)['status'],'budget_exhausted')

    def test_zero_model_budget_does_not_imply_finished(self):
        self.assertEqual(self.obs.campaign(self.directory)['status'],'unknown')

    def test_credentials_redacted_from_structures_and_logs(self):
        secret='rc-'+'a'*48
        value=public({'token_hash':'sensitive','api_key':'secret','message':'Authorization: Bearer '+secret,
                      'nested':{'access_token':'hidden','text':'value '+secret},'usage':{'input_tokens':100}})
        text=json.dumps(value)
        self.assertNotIn(secret,text)
        self.assertNotIn('sensitive',text)
        self.assertNotIn('hidden',text)
        self.assertEqual(value['usage']['input_tokens'],100)

    def test_complete_worker_is_not_revived_by_reused_pid(self):
        path=self.root/'.lab/sessions/old/status.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'pid':123,'status':'complete','agent_provider':'claude'}))
        with patch('lab.live_dashboard.process_status',return_value=True):
            worker=self.obs.workers()[0]
        self.assertEqual(worker['status'],'complete')
        self.assertEqual(worker['provider'],'claude')

    def test_permission_denied_is_unknown_liveness(self):
        with patch('lab.live_dashboard.os.kill',side_effect=PermissionError):
            self.assertIsNone(process_status(123,'lab.agent_loop'))

    def test_pid_reuse_by_another_controller_is_not_running(self):
        from types import SimpleNamespace
        result=SimpleNamespace(returncode=0,stdout='python -m lab.evolution_run --state /other/campaign')
        with patch('lab.live_dashboard.os.kill'), patch('lab.live_dashboard.subprocess.run',return_value=result):
            self.assertFalse(process_status(123,['lab.evolution_run','/my/campaign']))

    def test_tail_redacts_capabilities_and_truncated_pem_body(self):
        path=self.root/'test.log'
        path.write_text('prefix\n'*100+'-----BEGIN PRIVATE KEY-----\n'+'A'*64+'\n'+'B'*64+'\n-----END PRIVATE KEY-----\nclaim_token=sensitive\nactor_token=private\ntoken=hidden\n')
        text=tail(path,200)
        for value in ('A'*64,'B'*64,'sensitive','private','hidden'):
            self.assertNotIn(value,text)

    def test_screen_is_not_official_or_strict_pass(self):
        result=job_summary({'id':'abc','profile':'screen','status':'completed','result':{'passed':True}})
        self.assertEqual(result['official_check'],'not_run')
        self.assertEqual(result['strict_check'],'not_run')
        self.assertEqual(result['metrics'],{})

    def test_corrupt_campaign_is_reported_without_hiding_others(self):
        bad=self.root/'.lab/campaigns/broken/campaign.sqlite3';bad.parent.mkdir()
        bad.write_bytes(b'broken')
        state=self.obs.state()
        self.assertEqual([c['id'] for c in state['campaigns']],['test'])
        self.assertTrue(any('broken' in a for a in state['alerts']))


if __name__=='__main__':
    unittest.main()
