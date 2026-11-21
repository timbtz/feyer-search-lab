import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lab.evolution import Campaign
from lab.live_dashboard import Observatory, ReadOnlyCampaign, public, process_status, job_summary, tail, TEAM_ENDPOINT


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

    def test_job_comparison_provenance_requires_recorded_context(self):
        from tests.test_evolution_evidence import full_job
        from lab.phase_report import signature
        job = full_job()
        result = job_summary(job, 'AMD queue (read-only SSH)')
        self.assertEqual(result['timing_signature'], signature(job['report.json']))
        self.assertTrue(result['evidence']['eligible_full'])
        self.assertTrue(result['evidence']['cohort_digest'])
        self.assertIsNone(result['instance'])
        self.assertIsNone(result['comparison_context'])
        self.assertIsNone(result['provenance'])
        self.assertEqual(result['evaluation_provenance']['reported_candidate_sha'], job['sha'])
        self.assertEqual(result['evaluation_provenance']['protected_baseline_sha'], job['result']['baseline_sha'])
        self.assertNotIn('parent_run_key', result)
        self.assertNotIn('delta', result)

    def test_recorded_job_context_is_preserved_and_sanitized(self):
        from tests.test_evolution_evidence import full_job
        job = full_job()
        secret = 'ghp_' + 'a' * 30
        job.update(instance='amd-a', comparison_context=dict(mode='serial', epoch=4,
            receipt='recorded receipt', access_token=secret),
            provenance=dict(parent_candidates=['b' * 40], summary='Recorded change ' + secret),
            started_at=100, finished_at=200)
        result = job_summary(job)
        self.assertEqual(result['instance'], 'amd-a')
        self.assertEqual(result['comparison_context'], dict(mode='serial', epoch=4, receipt='recorded receipt'))
        self.assertEqual(result['provenance']['parent_candidates'], ['b' * 40])
        self.assertEqual(result['evaluation_provenance']['finished_at'], 200)
        self.assertNotIn(secret, json.dumps(result))

    def test_timing_report_does_not_imply_eligibility_or_valid_context(self):
        from tests.test_evolution_evidence import full_job
        job = full_job()
        job['result'].pop('worker_sha256')
        job.update(instance=['amd-a'], comparison_context='serial', provenance=['parent'])
        result = job_summary(job)
        self.assertTrue(result['timing_signature'])
        self.assertFalse(result['evidence']['eligible_full'])
        self.assertIsNone(result['evidence']['cohort_digest'])
        self.assertTrue(result['evidence']['issues'])
        for key in ('instance', 'comparison_context', 'provenance'):
            self.assertIsNone(result[key])
        job['status'] = 'running'
        self.assertIsNone(job_summary(job)['evidence'])

    def test_job_cohort_changes_with_worker_even_when_signature_matches(self):
        from tests.test_evolution_evidence import full_job
        job = full_job()
        before = job_summary(job)
        job['result']['worker_sha256'] = 'e' * 64
        after = job_summary(job)
        self.assertEqual(before['timing_signature'], after['timing_signature'])
        self.assertNotEqual(before['evidence']['cohort_digest'], after['evidence']['cohort_digest'])

    def test_feedback_join_uses_exact_job_sha_and_profile_without_mutating_source(self):
        from tests.test_evolution_evidence import full_job
        job = full_job()
        path = self.root/'.lab/worktrees/agent/experiments/runs/agent/candidate-01.json'
        path.parent.mkdir(parents=True)
        secret = 'ghp_' + 'a' * 30
        feedback = dict(candidate_sha=job['sha'], full=job,
            agent_response=dict(summary='Changed solver ' + secret, hypothesis='Expected faster solve'),
            provenance=dict(parent_candidates=['b' * 40]))
        path.write_text(json.dumps(feedback))
        original = job_summary(job)
        jobs = {job['id']: original}
        self.obs.recorded_feedback(jobs)
        record = jobs[job['id']]['recorded_feedback']
        self.assertEqual(record['parent_candidates'], ['b' * 40])
        self.assertEqual(record['status'], 'recorded')
        self.assertNotIn(secret, json.dumps(record))
        self.assertNotIn('recorded_feedback', original)
        for key, value in [('sha', 'c' * 40), ('profile', 'screen'), ('id', 'another-job')]:
            changed = dict(original, **{key: value})
            jobs = {changed['id']: changed}
            self.obs.recorded_feedback(jobs)
            self.assertNotIn('recorded_feedback', jobs[changed['id']])

    def test_conflicting_feedback_does_not_choose_a_scientific_parent(self):
        from tests.test_evolution_evidence import full_job
        job = full_job()
        root = self.root/'experiments/runs/agent'
        root.mkdir(parents=True)
        for number, parent in enumerate(['b' * 40, 'c' * 40]):
            (root/f'candidate-{number}.json').write_text(json.dumps(dict(candidate_sha=job['sha'], full=job,
                agent_response=dict(summary='Recorded change'), provenance=dict(parent_candidates=[parent]))))
        jobs = {job['id']: job_summary(job)}
        self.obs.recorded_feedback(jobs)
        record = jobs[job['id']]['recorded_feedback']
        self.assertEqual(record['status'], 'conflicting_records')
        self.assertIsNone(record['parent_candidates'])
        self.assertIsNone(record['summary'])
        self.assertEqual(len(record['sources']), 2)

    def test_feedback_symlinked_worktree_is_not_read(self):
        external = self.root/'outside'
        path = external/'experiments/runs/agent/candidate-01.json'
        path.parent.mkdir(parents=True)
        path.write_text('{}')
        root = self.root/'.lab/worktrees'
        root.mkdir(parents=True)
        (root/'agent').symlink_to(external, target_is_directory=True)
        with patch.object(self.obs, 'cached_json', side_effect=AssertionError('must not read')):
            self.obs.recorded_feedback({})

    def test_corrupt_campaign_is_reported_without_hiding_others(self):
        bad=self.root/'.lab/campaigns/broken/campaign.sqlite3';bad.parent.mkdir()
        bad.write_bytes(b'broken')
        state=self.obs.state()
        self.assertEqual([c['id'] for c in state['campaigns']],['test'])
        self.assertTrue(any('broken' in a for a in state['alerts']))

    def team_fixture(self):
        return dict(schema='feyer-team-search-v1', coordinator='owner', tasks={}, observations={}, events=[])

    def write_team(self, value):
        path = self.root / '.lab/team/state.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def test_unavailable_team_source_is_distinct_from_empty_ledger(self):
        missing = self.obs.state()
        self.assertIsNone(missing['team_search'])
        self.assertFalse(missing['team_search_source']['available'])
        self.assertTrue(missing['team_search_source']['stale'])
        self.assertIsNone(missing['team_search_source']['observed_at'])
        self.assertTrue(missing['team_search_source']['error'])
        self.assertEqual(len(missing['campaigns']), 1)
        self.write_team(self.team_fixture())
        empty = self.obs.state()
        self.assertEqual(empty['team_search']['tasks'], {})
        self.assertTrue(empty['team_search_source']['available'])
        self.assertFalse(empty['team_search_source']['stale'])
        self.assertIsNone(empty['team_search_source']['error'])
        self.assertIsNone(empty['team_search_source']['source_updated_at'])

    def test_comparison_context_survives_team_snapshot_without_changing_eligibility(self):
        data = self.team_fixture()
        context = dict(mode='concurrent', epoch=14, receipt='https://github.com/example/repo/issues/6')
        data['comparison_regime'] = dict(context, changed_at=100)
        data['observations']['host:job'] = dict(instance='host', comparison_context=context,
                                               evidence=dict(job_id='job', candidate_sha='a'*40, eligible_full=True))
        self.write_team(data)
        value, _ = self.obs.team_snapshot(time.time())
        self.assertEqual(value['comparison_regime'], data['comparison_regime'])
        self.assertEqual(value['observations']['host:job']['comparison_context'], context)
        self.assertTrue(value['observations']['host:job']['evidence']['eligible_full'])

    def test_local_copy_age_is_not_reset_by_browser_reads(self):
        data = self.team_fixture()
        data['events'] = [dict(at=25, command='add')]
        path = self.write_team(data)
        os.utime(path, (100, 100))
        _, source = self.obs.team_snapshot(150)
        self.assertEqual(source['observed_at'], 100)
        self.assertEqual(source['source_updated_at'], 25)
        self.assertFalse(source['stale'])
        _, later = self.obs.team_snapshot(200)
        self.assertEqual(later['observed_at'], 100)
        self.assertTrue(later['stale'])
        self.assertEqual(later['mode'], 'local_snapshot')

    def test_corrupt_or_removed_snapshot_preserves_last_good_evidence(self):
        original = self.team_fixture()
        path = self.write_team(original)
        good = self.obs.state()
        path.write_text('corrupt JSON')
        corrupt = self.obs.state()
        self.assertEqual(corrupt['team_search'], original)
        self.assertEqual(corrupt['team_search_source']['observed_at'], good['team_search_source']['observed_at'])
        self.assertTrue(corrupt['team_search_source']['error'])
        self.assertTrue(corrupt['team_search_source']['stale'])
        self.assertEqual(len(corrupt['campaigns']), 1)
        path.unlink()
        self.assertEqual(self.obs.state()['team_search'], original)

    def test_malformed_team_shapes_are_unavailable(self):
        values = [[], {**self.team_fixture(), 'schema':'wrong'},
                  {**self.team_fixture(), 'tasks':[]},
                  {**self.team_fixture(), 'observations':{'bad':{'evidence':[]}}},
                  {**self.team_fixture(), 'events':{}},
                  {**self.team_fixture(), 'tasks':{'a':{'id':'b'}}},
                  {**self.team_fixture(), 'tasks':{'a':{'id':'a','parents':{}}}}]
        for value in values:
            with self.subTest(value=value):
                self.write_team(value)
                fresh = Observatory(self.root).state()
                self.assertIsNone(fresh['team_search'])
                self.assertTrue(fresh['team_search_source']['error'])

    def test_team_credentials_redacted_without_reclassifying_results(self):
        data = self.team_fixture()
        data['tasks'] = {'a':dict(id='a', status='done', parents=[], candidates=[],
                                 api_key='credential-value', hypothesis='Bearer private-credential')}
        data['observations'] = {'amd-a:job':dict(instance='amd-a', evidence=dict(
            eligible_full=False, category='infrastructure_error', access_token='hidden-access'))}
        data['events'] = [dict(at=100, payload={'claim_token':'private-claim'})]
        path = self.write_team(data)
        before = path.read_bytes()
        snapshot = self.obs.state()
        encoded = json.dumps(snapshot)
        for secret in ('credential-value', 'private-credential', 'hidden-access', 'private-claim'):
            self.assertNotIn(secret, encoded)
        self.assertFalse(snapshot['team_search']['observations']['amd-a:job']['evidence']['eligible_full'])
        self.assertEqual(snapshot['team_search']['tasks']['a']['status'], 'done')
        self.assertEqual(path.read_bytes(), before)

    def test_symlink_snapshot_is_not_read(self):
        outside = self.root / 'private.json'
        outside.write_text(json.dumps(self.team_fixture()))
        path = self.root / '.lab/team/state.json'
        path.parent.mkdir(parents=True)
        path.symlink_to(outside)
        self.assertIsNone(self.obs.state()['team_search'])

    def test_github_poll_is_explicit_read_only_and_reports_source_freshness(self):
        obs = Observatory(self.root, team=True)
        data = self.team_fixture()
        data['events'] = [dict(at=20, command='init'), dict(at=50, command='add')]
        reply = SimpleNamespace(stdout=json.dumps(data))
        with patch('lab.live_dashboard.subprocess.run', return_value=reply) as request, \
             patch('lab.live_dashboard.time.time', return_value=100):
            obs.refresh_team()
        request.assert_called_once_with(
            ['gh','api','--hostname','github.com','--method','GET',TEAM_ENDPOINT,'--header','Accept: application/vnd.github.raw+json'],
            capture_output=True,text=True,check=True,timeout=20)
        value, source = obs.team_snapshot(150)
        self.assertEqual(value, data)
        self.assertEqual(source['mode'], 'github')
        self.assertEqual(source['observed_at'], 100)
        self.assertEqual(source['source_updated_at'], 50)
        self.assertFalse(source['stale'])
        self.assertTrue(obs.team_snapshot(191)[1]['stale'])
        self.assertFalse((self.root / '.lab/team/state.json').exists())

    def test_failed_github_poll_retains_evidence_without_leaking_stderr(self):
        obs = Observatory(self.root, team=True)
        data = self.team_fixture()
        with patch('lab.live_dashboard.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(data))), \
             patch('lab.live_dashboard.time.time', return_value=100):
            obs.refresh_team()
        failure = subprocess.CalledProcessError(1, ['gh'], stderr='private-unredacted-credential')
        with patch('lab.live_dashboard.subprocess.run', side_effect=failure):
            obs.refresh_team()
        value, source = obs.team_snapshot(101)
        self.assertEqual(value, data)
        self.assertEqual(source['observed_at'], 100)
        self.assertTrue(source['stale'])
        self.assertNotIn('private-unredacted-credential', source['error'])
        with patch('lab.live_dashboard.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(data))):
            obs.refresh_team()
        self.assertIsNone(obs.team_snapshot(time.time())[1]['error'])

    def test_disabled_github_poll_does_not_invoke_a_command(self):
        with patch('lab.live_dashboard.subprocess.run') as command:
            self.obs.refresh_team()
        command.assert_not_called()

    def profiler_fixture(self):
        return dict(profiler_reports=[dict(schema='feyer-profiler-v1', status='ok',
            job_id='job-one', candidate_sha='a' * 40, instance='amd-a', cohort_digest='cohort-one',
            first_run_seconds=10, phases=[dict(key='forward', seconds=5, share=.5)],
            groups=[dict(key='execution', seconds=5, share=.5)], warm_timing={},
            job_wall_seconds=15, limits=['Phase summary only'], issues=[], eligible_full=False)])

    def write_profiler(self, value):
        path = self.root / '.lab/profiler/report.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def test_profiler_unavailable_is_distinct_from_empty_collection(self):
        missing = self.obs.state()
        self.assertEqual(missing['profiler_reports'], [])
        self.assertFalse(missing['profiler_source']['available'])
        self.assertTrue(missing['profiler_source']['stale'])
        self.assertTrue(missing['profiler_source']['error'])
        self.write_profiler(dict(profiler_reports=[]))
        empty = self.obs.state()
        self.assertEqual(empty['profiler_reports'], [])
        self.assertTrue(empty['profiler_source']['available'])
        self.assertFalse(empty['profiler_source']['stale'])
        self.assertIsNone(empty['profiler_source']['error'])

    def test_profiler_records_preserved_without_validation_inference(self):
        data = self.profiler_fixture()
        invalid = dict(schema='feyer-profiler-v1', status='invalid_report', job_id='bad-job',
                       candidate_sha=None, phases=[], groups=[], first_run_seconds=None,
                       issues=['Missing timing report'], limits=[], warm_timing={})
        data['profiler_reports'].append(invalid)
        data['schema'] = 'feyer-profiler-collection-v1'
        path = self.write_profiler(data)
        before = path.read_bytes()
        with patch('lab.live_dashboard.subprocess.run') as command:
            reports, source = self.obs.profiler_snapshot(time.time())
        command.assert_not_called()
        self.assertEqual(reports, data['profiler_reports'])
        self.assertFalse(reports[0]['eligible_full'])
        self.assertEqual(reports[1]['status'], 'invalid_report')
        self.assertNotIn('eligible_full', reports[1])
        self.assertTrue(source['available'])
        self.assertEqual(path.read_bytes(), before)

    def test_conflicting_profiler_artifacts_remain_visible_without_discarding_other_reports(self):
        data = self.profiler_fixture()
        conflict = dict(schema='feyer-profiler-v1', status='conflicting_artifacts',
                        job_id='same-job', candidate_sha='b'*40, phases=[], groups=[],
                        eligible_full=False, issues=['Two records disagree'])
        data['profiler_reports'].append(conflict)
        self.write_profiler(data)
        state = self.obs.state()
        self.assertEqual(len(state['profiler_reports']), 2)
        self.assertEqual(state['profiler_reports'][1]['status'], 'conflicting_artifacts')
        self.assertFalse(state['profiler_reports'][1]['eligible_full'])
        self.assertIsNone(state['profiler_source']['error'])

    def test_profiler_schema_error_retains_last_good_collection(self):
        data = self.profiler_fixture()
        self.write_profiler(data)
        first = self.obs.state()
        malformed = [[], {'profiler_reports':{}}, {'profiler_reports':[[]]},
                     {'schema':'unexpected','profiler_reports':[]},
                     {'profiler_reports':[{'schema':'other','status':'ok'}]},
                     {'profiler_reports':[{'schema':'feyer-profiler-v1','status':'passed'}]},
                     {'profiler_reports':[{'schema':'feyer-profiler-v1','status':'ok','phases':{}}]}]
        for value in malformed:
            with self.subTest(value=value):
                self.write_profiler(value)
                current = self.obs.state()
                self.assertEqual(current['profiler_reports'], first['profiler_reports'])
                self.assertEqual(current['profiler_source']['observed_at'], first['profiler_source']['observed_at'])
                self.assertTrue(current['profiler_source']['stale'])
                self.assertTrue(current['profiler_source']['error'])
                self.assertEqual(len(current['campaigns']), 1)
        self.write_profiler(data)
        self.assertIsNone(self.obs.state()['profiler_source']['error'])

    def test_profiler_corrupt_and_removed_source_retains_last_good(self):
        data = self.profiler_fixture()
        path = self.write_profiler(data)
        self.obs.state()
        path.write_text('invalid JSON')
        self.assertEqual(self.obs.state()['profiler_reports'], data['profiler_reports'])
        path.unlink()
        state = self.obs.state()
        self.assertEqual(state['profiler_reports'], data['profiler_reports'])
        self.assertTrue(state['profiler_source']['stale'])

    def test_profiler_snapshot_age_tracks_file_not_browser_refresh(self):
        path = self.write_profiler(self.profiler_fixture())
        os.utime(path, (100, 100))
        _, first = self.obs.profiler_snapshot(150)
        _, later = self.obs.profiler_snapshot(191)
        self.assertEqual(first['observed_at'], 100)
        self.assertEqual(later['observed_at'], 100)
        self.assertFalse(first['stale'])
        self.assertTrue(later['stale'])
        self.assertEqual(later['source'], '.lab/profiler/report.json')

    def test_profiler_secrets_redacted_and_symlink_or_oversize_rejected(self):
        data = self.profiler_fixture()
        data['profiler_reports'][0].update(api_key='private-key-value', issues=['Bearer private-credential'])
        path = self.write_profiler(data)
        encoded = json.dumps(self.obs.state()['profiler_reports'])
        self.assertNotIn('private-key-value', encoded)
        self.assertNotIn('private-credential', encoded)
        path.unlink()
        target = self.root / 'external-profile.json'
        target.write_text(json.dumps(data))
        path.symlink_to(target)
        self.assertFalse(Observatory(self.root).state()['profiler_source']['available'])
        path.unlink()
        with path.open('wb') as stream:
            stream.truncate(16_000_001)
        self.assertFalse(Observatory(self.root).state()['profiler_source']['available'])


if __name__=='__main__':
    unittest.main()
