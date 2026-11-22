import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import analyze


class AnalysisTests(unittest.TestCase):
    def test_summary_keeps_every_sample(self):
        values=[.9,.8,.81,.82,.83]
        result=analyze.summary(values)
        self.assertEqual(result['samples_seconds'],values)
        self.assertEqual(result['count'],5)
        self.assertEqual(result['maximum_seconds'],.9)
        self.assertAlmostEqual(result['median_seconds'],.82)
        self.assertGreater(result['standard_deviation_seconds'],0)

    def test_constant_paired_effect_has_exact_interval(self):
        result=analyze.paired([.9,1.8,2.7,3.6,4.5],[1,2,3,4,5])
        self.assertAlmostEqual(result['estimated_ratio'],.9)
        self.assertTrue(all(abs(x-.9)<1e-12 for x in result['ratio_percentile_interval_95']))
        self.assertEqual(result['improving_blocks'],5)

    def test_bootstrap_deterministic_and_preserves_bad_block(self):
        candidate=[.8,.9,1.2,.9,.95];baseline=[1]*5
        a=analyze.paired(candidate,baseline);b=analyze.paired(candidate,baseline)
        self.assertEqual(a,b)
        self.assertEqual(a['paired_ratios_by_block'],candidate)
        self.assertEqual(a['improving_blocks'],4)
        self.assertGreater(a['ratio_percentile_interval_95'][1],1.)

    def test_no_partial_bootstrap(self):
        with self.assertRaises(ValueError): analyze.paired([1]*4,[1]*4)

    def test_incomplete_plan_refuses_final_and_preserves_partial_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'plan.json').write_bytes((Path(__file__).parent/'plan.json').read_bytes())
            result=analyze.analyze(root,root/'evidence')
            self.assertEqual(result['status'],'partial_not_final');self.assertEqual(result['complete_requests'],0)
            self.assertFalse(any('paired_vs_incumbent' in c for c in result['candidates'].values()))
            process=subprocess.run([sys.executable,str(Path(__file__).parent/'analyze.py'),'--directory',str(root),
                '--evidence-root',str(root/'evidence')],capture_output=True,text=True)
            self.assertEqual(process.returncode,2)
            self.assertFalse((root/'analysis.json').exists())
            self.assertFalse((root/'partial-analysis.json').exists())

    def test_changed_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'plan.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'altered'):analyze.analyze(root,root)


if __name__=='__main__':unittest.main()
