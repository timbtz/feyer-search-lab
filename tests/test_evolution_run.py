"""Controller dispatch must recover with the same request ID and frozen model."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from lab.evolution_run import evaluate, finish_pending_recipe, run
from lab.evolution_space import DEFAULTS, content_identity


class RunnerRecoveryTests(unittest.TestCase):
    def test_recovered_nonpassing_screen_does_not_reserve_or_dispatch_full(self):
        campaign=Mock()
        campaign.reserve_evaluation.return_value={'status':'completed','evidence_id':'screen-evidence',
                                                  'job_id':'screen-job','request_id':'same-screen-request'}
        client=Mock();client.request.return_value={'id':'screen-job'}
        normalize=Mock(return_value={'screen_passed':False,'category':'infrastructure_error'})
        runtime={'host':'amd-hackathon','root':'/workspace/feyer-lab','policy':{}}
        candidate={'candidate_id':'candidate','commit_sha':'a'*40}
        with tempfile.TemporaryDirectory() as directory, \
             patch('lab.evolution_run.components',return_value=(None,normalize,None,None,None)), \
             patch('lab.evolution_run.Client',return_value=client):
            evaluate(campaign,Path(directory),candidate,{'coordinator':'token'},runtime)
        campaign.reserve_evaluation.assert_called_once_with('coordinator','token','candidate','screen')
        client.submit.assert_not_called()
        client.wait.assert_not_called()

    def test_commit_written_before_pending_sha_is_recovered_without_rendering_again(self):
        campaign=Mock();campaign.snapshot.return_value={'candidates':[]}
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory);repo=state/'worktree';(repo/'differometor').mkdir(parents=True)
            source='reviewed-render\n';(repo/'differometor/simulate.py').write_text(source)
            proposal={'candidate_id':'candidate','content_sha256':content_identity(source),'parameters':DEFAULTS}
            pending={'proposal':proposal,'expected_head':'parent','owner':'qwen-mapping'}
            path=state/'pending-recipe.json';path.write_text(json.dumps(pending))
            def git(_repo,*args):
                if args==('rev-parse','HEAD'):return 'rendered-child'
                if args==('rev-parse','HEAD^'):return 'parent'
                if args==('status','--porcelain'):return ''
                if args[:2]==('diff','--name-only'):return 'differometor/simulate.py'
                raise AssertionError(args)
            with patch('lab.evolution_run.git',side_effect=git), \
                 patch('lab.evolution_run.materialize_commit') as materialize, \
                 patch('lab.evolution_run.publish'):
                finish_pending_recipe(campaign,state,{'qwen-mapping':'token'},
                    {'repo':str(repo),'branch':'explore/test','campaign_id':'test'})
            materialize.assert_not_called()
            self.assertEqual(campaign.propose.call_args.args[2]['commit_sha'],'rendered-child')
            self.assertFalse(path.exists())

    def test_lost_submission_response_reuses_the_same_reservation(self):
        class Campaign:
            def __init__(self):self.reservations={};self.evidence=[]
            def reserve_evaluation(self,actor,token,cid,profile):
                return self.reservations.setdefault(profile,{'status':'reserved','request_id':'request-'+profile})
            def bind_evaluation(self,actor,token,request,job):pass
            def observe(self,actor,token,cid,evidence):
                self.evidence.append(evidence)
                self.reservations[evidence['profile']].update(status='completed',evidence_id=evidence['job_id'])

        class Client:
            def __init__(self):self.jobs={};self.requests=[];self.lose_response=True
            def submit(self,*args,**kwargs):
                request=kwargs['request_id'];self.requests.append(request)
                job=self.jobs.setdefault(request,{'id':'job-'+kwargs['profile'],'profile':kwargs['profile']})
                if self.lose_response:
                    self.lose_response=False
                    raise TimeoutError('Submission reached worker but SSH response was lost')
                return job
            def wait(self,job_id,timeout):
                return next(j for j in self.jobs.values() if j['id']==job_id)

        def normalize(job,**kwargs):
            return dict(job,job_id=job['id'],screen_passed=job['profile']=='screen',
                        category='screen' if job['profile']=='screen' else 'valid')

        campaign,client=Campaign(),Client()
        candidate={'candidate_id':'candidate','commit_sha':'a'*40,'owner':'qwen-mapping',
                   'lane_id':'mapping','provenance':{'hypothesis':'Same exact candidate'}}
        runtime={'host':'amd-hackathon','root':'/workspace/feyer-lab','repo':'unused',
                 'branch':'explore/test','publish':False,'policy':{}}
        with tempfile.TemporaryDirectory() as directory, \
             patch('lab.evolution_run.components',return_value=(None,normalize,None,None,None)), \
             patch('lab.evolution_run.Client',return_value=client), \
             patch('lab.evolution_run.publish'):
            state=Path(directory)
            with self.assertRaises(TimeoutError):
                evaluate(campaign,state,candidate,{'coordinator':'token'},runtime)
            evaluate(campaign,state,candidate,{'coordinator':'token'},runtime)
        self.assertEqual(client.requests,['request-screen','request-screen','request-full'])
        self.assertEqual(len(client.jobs),2)
        self.assertEqual(len(campaign.reservations),2)
        self.assertEqual(len(campaign.evidence),2)

    def test_changed_configured_model_never_calls_provider(self):
        campaign=Mock()
        campaign.plan.return_value={'action':'mutate','parent_candidates':['seed8'],
            'dimensions':['map_batch_size'],'lane_id':'mapping','owner':'qwen-mapping','round_id':'round-001'}
        campaign.snapshot.return_value={'campaign':{'spec':{'model_manifest':{'qwen':{'model':'frozen-model'}}}},'lanes':[],
            'rounds':[{'round_id':'round-001','spec':{}}],
            'candidates':[{'candidate_id':'seed8','valid':True,'parameters':DEFAULTS,
                           'metrics':{'total':28},'content_sha256':content_identity('seed'),'status':'valid'}]}
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory);repo=state/'worktree';repo.mkdir()
            (state/'runtime.json').write_text(json.dumps({'repo':str(repo),'campaign_id':'test',
                'env_file':str(state/'not-read.env'),'branch':'explore/test'}))
            (state/'credentials.json').write_text(json.dumps({'coordinator':'token'}))
            store=Mock(return_value={'sha256':'a'*64,'path':'prompts/a.txt'})
            with patch('lab.evolution_run.components',return_value=(lambda path:campaign,None,None,None,store)), \
                 patch('lab.evolution_run.source_from_git',return_value='seed'), \
                 patch('lab.evolution_run.materialize',side_effect=lambda source,p:source+json.dumps(p)), \
                 patch('lab.evolution_run.publish',return_value={'context_sha256':'b'*64}), \
                 patch('lab.evolution_run.settings',return_value=('test-secret','changed-model')), \
                 patch('lab.evolution_run.TokenFactory') as provider:
                with self.assertRaisesRegex(ValueError,'Model identity changed'):
                    run(SimpleNamespace(state=state,once=True))
                provider.assert_not_called()
                campaign.record_model_call.assert_not_called()


if __name__=='__main__':unittest.main()
