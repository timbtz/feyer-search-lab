import copy
import unittest
from lab.phase_report import GROUPS, analyze_feedback, baseline, deltas, dominates, metrics


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
        self.assertFalse(analyze_feedback({'full':job},baseline([r]))['validated'])

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


if __name__=='__main__':unittest.main()
