"""Trusted evidence requires complete provenance, not just a PASS label."""
import copy
import json
from pathlib import Path
import unittest

from lab.evolution_evidence import (ARRAY_KEYS, FULL_EVALUATOR_SHA256, canonical_digest,
                                    normalize_job, policy_from_job)
from lab.worker import BASELINE_SHA, THREAD_VARIABLES


def full_job():
    report = json.loads((Path(__file__).resolve().parents[1] /
                        'experiments/baselines/base1.json').read_text())
    sha = 'a' * 40
    report['source']['commit'] = sha
    report['source']['modified'] = False
    report['source']['diff_sha256'] = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    monitor = {'budget_bytes':32_000_000_000, 'enforcement':'sampled_process_group_rss',
               'kernel_memory_limit_enforced':False, 'samples':20,
               'sampled_process_group_peak_rss_bytes':14_000_000_000, 'exceeded':False}
    env = {name:'1' for name in THREAD_VARIABLES}
    env.update(JAX_PLATFORMS='cpu', JAX_ENABLE_X64='true', JAX_ENABLE_COMPILATION_CACHE='false',
               XLA_FLAGS=None, PYTHONNOUSERSITE='1')
    comparison = {'passed':True,'rtol':1e-7,'scale_atol':1e-12,
                  'checks':{key:{'passed':True,'finite':True} for key in ARRAY_KEYS}}
    result = {'sha':sha,'profile':'full','status':'completed','cpu':2,
              'baseline_sha':BASELINE_SHA,'evaluator_sha256':FULL_EVALUATOR_SHA256,
              'worker_sha256':'b'*64,'comparison_evaluator_sha256':'c'*64,
              'reference_arrays_sha256':'d'*64,'official_passed':True,'regression_passed':True,
              'execution_environment':env, 'reported_environment':copy.deepcopy(report['environment']),
              'validation':copy.deepcopy(report['validation']),
              'first_run_seconds':report['timing_seconds']['end_to_end'],
              'memory_budget_bytes':32_000_000_000,'memory_monitoring':monitor,
              'resource_provenance':{'container_limits':{'memory.max':'59055800320',
                  'memory.swap.max':'0','cpu.max':'1600000 100000','cpuset.cpus.effective':'0-127'}},
              'peak_rss_kib':14_000_000,'wall_seconds':120.0,'returncode':0,
              'comparison':{'returncode':0,'timed_out':False,'wall_seconds':0.3,
                            'memory_monitoring':copy.deepcopy(monitor)}}
    return {'id':'job-one','sha':sha,'profile':'full','status':'completed',
            'result':result,'report.json':report,'comparison.json':comparison}


class EvolutionEvidenceTests(unittest.TestCase):
    def test_complete_full_is_eligible_and_digests_bind_every_artifact(self):
        job=full_job(); evidence=normalize_job(job,expected_sha=job['sha'])
        self.assertEqual(evidence['category'],'valid')
        self.assertTrue(evidence['eligible_full'])
        self.assertEqual(evidence['checks']['strict'],'passed')
        self.assertEqual(evidence['metrics']['runtime'],sum(evidence['metrics'][k]
            for k in ('forward','sensitivity','gradient','transfer')))
        unsigned=dict(evidence);digest=unsigned.pop('evidence_digest')
        self.assertEqual(digest,canonical_digest(unsigned))
        altered=copy.deepcopy(job);altered['stdout.log']='different retained output'
        self.assertNotEqual(evidence['artifact_digest'],normalize_job(altered)['artifact_digest'])

    def test_independent_runs_same_cohort_but_distinct_evidence(self):
        first=full_job();second=copy.deepcopy(first);second['id']='job-two'
        second['result']['wall_seconds']=121.0
        second['result']['memory_monitoring']['samples']=21
        a,b=normalize_job(first),normalize_job(second)
        self.assertEqual(a['cohort_digest'],b['cohort_digest'])
        self.assertNotEqual(a['evidence_id'],b['evidence_id'])

    def test_normalized_envelope_does_not_alias_mutable_job_artifacts(self):
        job=full_job();out=normalize_job(job)
        original=copy.deepcopy(out)
        job['result']['memory_monitoring']['samples']=999
        job['report.json']['source']['simulator_files_sha256']['differometor/simulate.py']='f'*64
        self.assertEqual(out,original)

    def test_changed_worker_reference_or_comparator_is_incomparable(self):
        original=full_job(); policy=policy_from_job(original)
        for key in ('worker_sha256','comparison_evaluator_sha256','reference_arrays_sha256'):
            with self.subTest(key=key):
                altered=copy.deepcopy(original);altered['result'][key]='e'*64
                raw=normalize_job(altered)
                self.assertNotEqual(raw['cohort_digest'],normalize_job(original)['cohort_digest'])
                constrained=normalize_job(altered,policy_context=policy)
                self.assertEqual(constrained['category'],'infrastructure_error')
                self.assertFalse(constrained['scientific_strike'])

    def test_missing_or_contradictory_metadata_never_becomes_scientific_strike(self):
        for mutation in ('hash','report','memory','nanphase','sha','strict','env','total'):
            with self.subTest(mutation=mutation):
                job=full_job()
                if mutation=='hash':job['result'].pop('worker_sha256')
                if mutation=='report':job.pop('report.json')
                if mutation=='memory':job['result']['memory_monitoring']['samples']=0
                if mutation=='nanphase':job['report.json']['phases'][0]['seconds']='not a number'
                if mutation=='sha':job['report.json']['source']['commit']='f'*40
                if mutation=='strict':job['comparison.json']['checks']['gradient']['passed']=False
                if mutation=='env':job['result']['execution_environment']['OMP_NUM_THREADS']='8'
                if mutation=='total':job['result']['first_run_seconds']+=1
                out=normalize_job(job)
                self.assertEqual(out['category'],'infrastructure_error')
                self.assertFalse(out['scientific_strike'])
                self.assertFalse(out['eligible_full'])

    def test_strict_only_failure_keeps_official_pass_and_counts_scientific_rejection(self):
        job=full_job();job['status']=job['result']['status']='failed'
        job['result']['regression_passed']=False
        job['result']['comparison']['returncode']=1
        job['comparison.json']['passed']=False
        job['comparison.json']['checks']['gradient']['passed']=False
        out=normalize_job(job)
        self.assertEqual(out['category'],'invalid_candidate')
        self.assertTrue(out['scientific_strike'])
        self.assertEqual(out['checks']['official'],'passed')
        self.assertEqual(out['checks']['strict'],'failed')

    def test_screen_never_enters_full_cohort_or_promotion(self):
        full=full_job();job=copy.deepcopy(full)
        job['profile']=job['result']['profile']='screen';job.pop('comparison.json')
        r=job['report.json'];r['benchmark']='feyer-lab-screen-v1'
        r['starter_sha256']=job['result']['evaluator_sha256']='5cb1e5b8013dde1249845e3d6ce24b1f85240a0fb14b5cb966340188559c390a'
        r['validation']['passed']=True;r['validation']['gradient_check']={'passed':None,'status':'not_run'}
        job['result']['validation']=copy.deepcopy(r['validation'])
        job['result']['official_passed']=job['result']['regression_passed']=None
        for key in ('comparison','comparison_evaluator_sha256','reference_arrays_sha256'):
            job['result'].pop(key)
        out=normalize_job(job,policy_context=policy_from_job(full))
        self.assertEqual(out['category'],'screen')
        self.assertTrue(out['screen_passed'])
        self.assertFalse(out['eligible_full'])
        self.assertNotEqual(out['cohort_digest'],normalize_job(full)['cohort_digest'])

    def test_wrong_candidate_and_running_job_are_rejected_before_adapter(self):
        job=full_job()
        with self.assertRaises(ValueError):normalize_job(job,expected_sha='f'*40)
        job['status']='running'
        with self.assertRaises(ValueError):normalize_job(job)

    def test_unknown_memory_budget_is_infrastructure_error(self):
        job=full_job();job['result']['memory_budget_bytes']=None
        out=normalize_job(job)
        self.assertEqual(out['category'],'infrastructure_error')
        self.assertFalse(out['scientific_strike'])


if __name__=='__main__':unittest.main()
