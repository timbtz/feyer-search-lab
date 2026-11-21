import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from lab.evolution import Campaign, PHASES, digest


def sha(value, size=64):
    return hashlib.sha256(value.encode()).hexdigest()[:size]


def measurements(total=30, **changes):
    values = dict(total=total, setup=1., compilation=12., forward=10., sensitivity=.2,
                  gradient=5., transfer=.001, runtime=15.201, peak_rss_bytes=1000000.)
    values.update(changes)
    return values


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'campaign.sqlite3'
        self.c = Campaign(self.path)
        self.spec = dict(campaign_id='test', budget=dict(max_proposals=100, max_evaluations=100,
                         max_model_calls=20, deadline_unix=time.time()+600), cohort_digest=sha('cohort'))
        self.owner = self.c.initialize(self.spec, 'owner')
        self.worker = self.c.grant('owner', self.owner, 'worker', 'qwen')
        self.strong = self.c.grant('owner', self.owner, 'strong', 'strong')
        self.round = dict(round_id='r1', dimensions={'x':list(range(10)), 'y':[0,1]},
                          recipes={'x':{'dimensions':['x']}},
                          lanes={'x':{'owner':'worker', 'dimensions':['x'], 'max_proposals':20}},
                          progress={'relative':.03, 'absolute':.02},
                          budget={'max_proposals':50, 'max_evaluations':60})
        self.c.add_round('owner', self.owner, self.round)
        self.c.propose('owner', self.owner, self.proposal('seed', 0, kind='seed', parents=[]))
        self.c.observe('owner', self.owner, 'seed', self.evidence('seed', 'seed-job', category='valid'))

    def tearDown(self):
        self.temp.cleanup()

    def proposal(self, name, x, kind='mutate', parents=None, **changes):
        item=dict(proposal_id=name, candidate_id=name, round_id='r1', lane_id='x', kind=kind,
                  parents=['seed'] if parents is None else parents, parameters={'x':x,'y':0}, recipe='x',
                  content_sha256=sha(name), commit_sha=sha(name,40), provenance={'hypothesis':'measure'})
        item.update(changes)
        return item

    def evidence(self, cid, job, category='screen', **changes):
        result=dict(evidence_id=job, job_id=job, candidate_sha=sha(cid,40),
                    profile='screen' if category=='screen' else 'full', category=category,
                    eligible_full=category=='valid', screen_passed=category=='screen',
                    evidence_digest=sha(job), cohort_digest=sha('cohort'), metrics=measurements())
        result.update(changes)
        return result

    def propose(self, name, x, **changes):
        return self.c.propose('worker', self.worker, self.proposal(name,x,**changes))

    def screen(self, cid):
        request=self.c.reserve_evaluation('owner',self.owner,cid,'screen')
        self.c.bind_evaluation('owner',self.owner,request['request_id'],cid+'-screen')
        self.c.observe('owner',self.owner,cid,self.evidence(cid,cid+'-screen'))
        return request

    def finish(self, cid, **changes):
        self.screen(cid)
        request=self.c.reserve_evaluation('owner',self.owner,cid,'full')
        self.c.bind_evaluation('owner',self.owner,request['request_id'],cid+'-full')
        return self.c.observe('owner',self.owner,cid,self.evidence(cid,cid+'-full',category='valid',**changes))

    def lane(self):
        return next(l for l in self.c.snapshot()['lanes'] if l['round_id']=='r1')

    def test_seed_confirmation_aggregation_and_no_strikes_or_dispatch_budget(self):
        self.c.observe('owner',self.owner,'seed',self.evidence('seed','seed-2',category='valid',metrics=measurements(32)))
        result=self.c.observe('owner',self.owner,'seed',self.evidence('seed','seed-3',category='valid',metrics=measurements(28)))
        self.assertEqual(result['metrics']['total'],30)
        self.assertEqual(result['metric_ranges']['total'],4)
        self.assertEqual(result['full_run_count'],3)
        self.assertEqual(self.lane()['strikes'],0)
        self.assertEqual(self.c.snapshot()['usage']['evaluations'],0)

    def test_log_hash_chain_and_token_redaction(self):
        self.assertTrue(self.c.verify_log())
        exported=json.dumps(self.c.snapshot())
        self.assertNotIn(self.owner,exported)
        self.assertNotIn(self.worker,exported)
        self.assertNotIn('token_hash',exported)
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM events')

    def test_round_replay_is_idempotent_and_changed_spec_rejected(self):
        before=len(self.c.events())
        self.c.add_round('owner',self.owner,self.round)
        self.assertEqual(len(self.c.events()),before)
        changed=copy.deepcopy(self.round);changed['dimensions']['x'].append(10)
        with self.assertRaisesRegex(ValueError,'immutable'):self.c.add_round('owner',self.owner,changed)

    def test_owner_tokens_rotate_and_qwen_cannot_change_round(self):
        with self.assertRaises(PermissionError):self.c.add_round('worker',self.worker,dict(self.round,round_id='r2'))
        new=self.c.grant('owner',self.owner,'worker','qwen')
        with self.assertRaises(PermissionError):self.propose('p',1)
        p=self.c.propose('worker',new,self.proposal('p',1))
        self.assertEqual(p['owner_version'],2)

    def test_one_inflight_and_proposal_replay(self):
        first=self.propose('p',1)
        before=len(self.c.events())
        self.assertEqual(self.propose('p',1)['candidate_id'],first['candidate_id'])
        self.assertEqual(len(self.c.events()),before)
        with self.assertRaises(RuntimeError):self.propose('q',2)
        with self.assertRaisesRegex(ValueError,'conflicts'):self.propose('p',2)

    def test_finite_space_recipe_and_parent_guards(self):
        for change in ({'parameters':{'x':20,'y':0}}, {'parameters':{'x':1,'y':1}},
                       {'recipe':'unknown'}, {'parents':['missing']}, {'parents':['p']},
                       {'parameters':{'x':True,'y':0}}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.propose('p',1,**change)

    def test_screen_provisional_and_bound_job_required(self):
        self.propose('p',1)
        with self.assertRaises(ValueError):self.c.observe('owner',self.owner,'p',self.evidence('p','unbound'))
        with self.assertRaises(RuntimeError):self.c.reserve_evaluation('owner',self.owner,'p','full')
        self.screen('p')
        candidate=next(c for c in self.c.snapshot()['candidates'] if c['candidate_id']=='p')
        self.assertFalse(candidate['valid'])
        self.assertEqual(candidate['status'],'screened')
        self.assertEqual(self.lane()['strikes'],0)

    def test_reservation_replay_reopen_and_binding_conflicts(self):
        self.propose('p',1)
        first=self.c.reserve_evaluation('owner',self.owner,'p','screen')
        reopened=Campaign(self.path)
        again=reopened.reserve_evaluation('owner',self.owner,'p','screen')
        self.assertEqual(first['request_id'],again['request_id'])
        self.assertEqual(reopened.snapshot()['usage']['evaluations'],1)
        reopened.bind_evaluation('owner',self.owner,first['request_id'],'job')
        with self.assertRaises(ValueError):reopened.bind_evaluation('owner',self.owner,first['request_id'],'other')

    def test_three_distinct_nonimprovements_stall_and_replay_does_not_count(self):
        for n in range(1,4):
            name='p'+str(n);self.propose(name,n);self.finish(name)
            self.c.observe('owner',self.owner,name,self.evidence(name,name+'-full',category='valid'))
            self.assertEqual(self.lane()['strikes'],n)
        self.assertEqual(self.lane()['status'],'stalled')
        self.assertEqual(self.c.plan('owner',self.owner)['action'],'combine')
        with self.assertRaises(RuntimeError):self.propose('p4',4)

    def test_real_total_improvement_resets_strikes_but_tiny_noise_does_not(self):
        self.propose('p1',1);self.finish('p1',metrics=measurements(29.99))
        self.assertEqual(self.lane()['strikes'],1)
        self.propose('p2',2);result=self.finish('p2',metrics=measurements(25))
        self.assertTrue(result['progress']['meaningful_total'])
        self.assertEqual(self.lane()['strikes'],0)

    def test_infrastructure_failure_and_retry_never_counts_a_strike(self):
        self.propose('p',1)
        first=self.c.reserve_evaluation('owner',self.owner,'p','screen')
        self.c.bind_evaluation('owner',self.owner,first['request_id'],'bad')
        self.c.observe('owner',self.owner,'p',self.evidence('p','bad',category='infrastructure_error',profile='screen'))
        self.assertEqual(self.lane()['strikes'],0)
        self.assertEqual(self.c.reserve_evaluation('owner',self.owner,'p','screen')['request_id'],first['request_id'])
        retry=self.c.reserve_evaluation('owner',self.owner,'p','screen',retry=True)
        self.assertNotEqual(retry['request_id'],first['request_id'])
        self.assertEqual(self.c.reserve_evaluation('owner',self.owner,'p','screen',retry=True)['request_id'],retry['request_id'])

    def test_duplicate_content_and_exhaustion_do_not_add_strikes(self):
        duplicate=self.propose('same',1,content_sha256=sha('seed'))
        self.assertEqual(duplicate['status'],'duplicate')
        self.assertIsNone(self.lane()['inflight_candidate'])
        self.assertEqual(self.lane()['strikes'],0)
        self.c.lane_exhausted('owner',self.owner,'r1','x')
        self.assertEqual(self.c.plan('owner',self.owner)['action'],'meta_guidance')

    def test_combination_requires_two_valid_parents_and_fresh_validation(self):
        self.propose('p',1);self.finish('p',metrics=measurements(25))
        second=copy.deepcopy(self.round);second['round_id']='r2';second['combination_parents']=['seed','p']
        self.c.add_round('owner',self.owner,second)
        proposal=self.proposal('joint',2,round_id='r2',kind='combine',parents=['seed','p'])
        joint=self.c.propose('worker',self.worker,proposal)
        self.assertFalse(joint['valid'])
        self.assertEqual(joint['status'],'proposed')
        with self.assertRaises(RuntimeError):self.c.add_round('owner',self.owner,dict(second,round_id='r3'))

    def test_model_reservation_failure_outcome_and_guidance_are_durable(self):
        self.c.record_model_call('worker',self.worker,'call',{'model':'fixed'})
        self.c.record_model_call('worker',self.worker,'call',{'model':'fixed'})
        self.c.record_model_outcome('worker',self.worker,'call',{'ok':False,'status':429})
        self.c.record_model_outcome('worker',self.worker,'call',{'ok':False,'status':429})
        self.assertEqual(self.c.snapshot()['usage']['model_calls'],1)
        with self.assertRaises(ValueError):self.c.record_model_outcome('worker',self.worker,'call',{'ok':True})
        with self.assertRaises(PermissionError):self.c.record_guidance('worker',self.worker,'g',{})
        self.c.record_guidance('strong',self.strong,'g',{'parents':['seed'],'context_sha256':sha('context')})
        self.assertEqual(len(self.c.snapshot()['guidance']),1)

    def test_different_evidence_cohort_rejected(self):
        with self.assertRaisesRegex(ValueError,'cohort'):
            self.c.observe('owner',self.owner,'seed',self.evidence('seed','wrong',category='valid',cohort_digest=sha('other')))

    def test_decision_is_coordinator_only_idempotent_and_budget_free(self):
        payload={'plan':self.c.plan('owner',self.owner),'context_sha256':digest(self.c.context())}
        usage=self.c.snapshot()['usage']
        with self.assertRaises(PermissionError):
            self.c.record_decision('strong',self.strong,'decision',payload)
        self.c.record_decision('owner',self.owner,'decision',payload)
        self.c.record_decision('owner',self.owner,'decision',payload)
        self.assertEqual(len(self.c.snapshot()['decisions']),1)
        self.assertEqual(self.c.context()['decisions'][0]['payload'],payload)
        self.assertEqual(self.c.snapshot()['usage'],usage)
        with self.assertRaises(ValueError):
            self.c.record_decision('owner',self.owner,'decision',{'plan':'changed'})

    def test_adapter_digest_detects_mutated_envelope(self):
        evidence=self.evidence('seed','digest',category='valid')
        evidence['schema_version']='feyer-evolution-evidence-v1'
        evidence['evidence_digest']=digest({k:v for k,v in evidence.items() if k!='evidence_digest'})
        mutated=copy.deepcopy(evidence);mutated['metrics']['total']=1
        with self.assertRaisesRegex(ValueError,'digest'):
            self.c.observe('owner',self.owner,'seed',mutated)
        self.c.observe('owner',self.owner,'seed',evidence)

    def test_invalid_observation_cannot_be_repaired_by_one_later_pass(self):
        self.c.observe('owner',self.owner,'seed',self.evidence('seed','invalid',category='invalid_candidate'))
        result=self.c.observe('owner',self.owner,'seed',self.evidence('seed','later',category='valid'))
        self.assertFalse(result['valid'])
        with self.assertRaises(ValueError):self.propose('p',1)

    def test_custom_pareto_axes_use_runtime_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            c=Campaign(Path(directory)/'other.sqlite3')
            spec=copy.deepcopy(self.spec);spec['objective']={'pareto_axes':['runtime','peak_rss_bytes']}
            owner=c.initialize(spec,'owner');worker=c.grant('owner',owner,'worker','qwen')
            c.add_round('owner',owner,self.round)
            for name,x,runtime,memory in [('seed',0,5,1000),('other',1,6,1100)]:
                c.propose('owner',owner,self.proposal(name,x,kind='seed',parents=[]))
                c.observe('owner',owner,name,self.evidence(name,name+'-e',category='valid',metrics=measurements(runtime=runtime,peak_rss_bytes=memory)))
            rows={r['candidate_id']:r for r in c.snapshot()['candidates']}
            self.assertTrue(rows['seed']['exact_pareto']);self.assertFalse(rows['other']['exact_pareto'])
            self.assertEqual(rows['seed']['metrics']['peak_rss_bytes'],1000)


if __name__=='__main__':unittest.main()
