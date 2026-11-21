import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from lab.client import sync_ledger
from lab.phase_report import GROUPS, analyze_feedback, baseline, collect_rows, deltas, dominates, metrics


def report():
    phases=[{'key':k,'seconds':1.0} for keys in GROUPS.values() for k in keys]
    return {'phases':phases,'timing_seconds':{'end_to_end':14},
            'environment':{'cpu_model':'same','backend':'cpu'},'inputs':{}}


class PhaseReportTests(unittest.TestCase):
    def test_phase_aggregation_does_not_mix_warm_timings(self):
        r=report();r['timing_seconds']['phase_runtime_medians']={'forward':999}
        m,_=metrics(r)
        self.assertEqual(m['compilation'],6)
        self.assertEqual(m['setup'],4)
        self.assertEqual(m['forward'],1)

    def test_pareto_dominance_rejects_tradeoffs_and_ties(self):
        a={k:1 for k in GROUPS};b=dict(a,compilation=2)
        self.assertTrue(dominates(a,b))
        self.assertFalse(dominates(a,a))
        self.assertFalse(dominates(dict(a,forward=3),b))

    def test_noise_threshold_uses_baseline_phase_range(self):
        d=deltas({'forward':9.5},{'forward':{'median':10,'range':1}})
        self.assertEqual(d['forward']['classification'],'within_noise_band')

    def test_official_pass_but_strict_failure_is_not_validated(self):
        r=report();job={'profile':'full','status':'failed','report.json':r,
            'result':{'official_passed':True},'comparison.json':{'passed':False}}
        analysis=analyze_feedback({'full':job},baseline([r]))
        self.assertFalse(analysis['validated'])
        self.assertEqual(analysis['official_check'],'passed')
        self.assertEqual(analysis['strict_check'],'failed')

    def test_screen_pass_is_not_full_validation(self):
        r=report();job={'profile':'screen','status':'completed','report.json':r}
        self.assertFalse(analyze_feedback({'screen':job},baseline([r]))['validated'])

    def test_mismatched_hardware_is_not_classified(self):
        r=report();other=copy.deepcopy(r);other['environment']['cpu_model']='different'
        analysis=analyze_feedback({'full':{'report.json':other}},baseline([r]))
        self.assertFalse(analysis['comparable'])
        self.assertNotIn('delta',analysis)

    def test_missing_phases_are_not_silently_zero(self):
        r=report();r['phases'].pop()
        with self.assertRaises(ValueError):metrics(r)

    def test_changed_evaluator_is_not_comparable(self):
        r=report();r['benchmark']='official';r['starter_sha256']='a'*64
        other=copy.deepcopy(r);other['starter_sha256']='b'*64
        analysis=analyze_feedback({'full':{'report.json':other}},baseline([r]))
        self.assertFalse(analysis['comparable'])

    def test_reported_hash_must_match_worker_execution_hash(self):
        r=report();r['starter_sha256']='a'*64
        job={'report.json':r,'result':{'evaluator_sha256':'b'*64}}
        self.assertFalse(analyze_feedback({'full':job},baseline([r]))['comparable'])

    def test_reviewed_screen_schema_matches_official_timing_schema(self):
        r=report();r['benchmark']='start-munich-2026-public-differometor-uifo-v2'
        r['starter_sha256']='d5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e'
        screen=copy.deepcopy(r);screen['benchmark']='feyer-lab-screen-v1'
        screen['starter_sha256']='5cb1e5b8013dde1249845e3d6ce24b1f85240a0fb14b5cb966340188559c390a'
        job={'profile':'screen','status':'completed','report.json':screen}
        analysis=analyze_feedback({'screen':job},baseline([r]))
        self.assertTrue(analysis['comparable'])
        self.assertEqual(analysis['official_check'],'not_run')

    def test_manual_runs_are_collected_without_supervisor_records_and_repeats_stay_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ledger=root/'ledger';ledger.mkdir()
            common={'sha':'a'*40,'branch':'explore/manual','agent':'manual','direction':'solver',
                    'status':'completed','report.json':report(),'hypothesis':'Try a solve'}
            for n,profile in enumerate(('screen','full','full'),1):
                job=common|{'id':str(n)*32,'profile':profile,'created_at':n,
                    'result':{'official_passed':profile=='full'},'comparison.json':{'passed':profile=='full'}}
                (ledger/f'{n}.json').write_text(json.dumps(job))
            with patch('lab.phase_report.subprocess.check_output',return_value=''):
                rows=collect_rows(root,baseline([report()]),ledger)
            self.assertEqual(len(rows),2)
            self.assertEqual({r['job_id'] for r in rows},{'2'*32,'3'*32})
            self.assertTrue(all(r['validated'] for r in rows))
            self.assertTrue(all(r['screen_job_ids']==['1'*32] for r in rows))

    def test_ledger_sync_only_reads_terminal_jobs_and_reuses_cache(self):
        terminal={'id':'a'*32,'status':'completed','updated_at':1}
        queued={'id':'b'*32,'status':'queued','updated_at':2}
        client=Mock();client.request.side_effect=[[terminal,queued],terminal,[terminal,queued]]
        with tempfile.TemporaryDirectory() as directory:
            first=sync_ledger(client,directory);second=sync_ledger(client,directory)
            self.assertEqual(first['saved'],1)
            self.assertEqual(second['saved'],0)
            self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
        self.assertEqual([c.args[0]['action'] for c in client.request.call_args_list],['list','show','list'])

    def test_missing_historical_resource_metadata_stays_unknown(self):
        analysis=analyze_feedback({'full':{'report.json':report()}},baseline([report()]))
        resource=analysis['resource_evidence']
        self.assertEqual(resource['enforcement'],'unknown_historical')
        self.assertIsNone(resource['kernel_memory_limit_enforced'])
        self.assertIsNone(resource['budget_bytes'])

    def test_monitored_budget_is_not_mislabeled_as_kernel_cap(self):
        job={'report.json':report(),'result':{'memory_budget_bytes':32000000000,
            'memory_monitoring':{'enforcement':'sampled_process_group_rss','kernel_memory_limit_enforced':False}}}
        resource=analyze_feedback({'full':job},baseline([report()]))['resource_evidence']
        self.assertEqual(resource['budget_bytes'],32000000000)
        self.assertFalse(resource['kernel_memory_limit_enforced'])


if __name__=='__main__':unittest.main()
