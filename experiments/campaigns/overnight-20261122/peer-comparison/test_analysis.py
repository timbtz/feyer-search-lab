import importlib.util,pathlib,unittest,tempfile,json
P=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('peer_analysis',P/'analyze.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_metrics_keep_all_samples(self):
  v=[1.,2.,3.];x=m.metrics(v);self.assertEqual(x['count'],3);self.assertEqual(x['samples_seconds'],v);self.assertEqual(x['median_seconds'],2.)
 def test_known_paired_ratio(self):
  r=m.paired([1.,2.,3.],[2.,4.,6.],11);self.assertEqual(r['estimated_ratio'],.5);self.assertEqual(r['ratio_percentile_interval_95'],[.5,.5]);self.assertEqual(r['repaired_faster_blocks'],3)
 def test_deterministic_and_no_bad_sample_dropped(self):
  a=m.paired([1.,1.,10.],[2.,2.,2.],12);self.assertEqual(a,m.paired([1.,1.,10.],[2.,2.,2.],12));self.assertEqual(a['repaired_over_peer_ratios_by_block'],[.5,.5,5.]);self.assertAlmostEqual(a['ratio_percentile_interval_95'][1],5.)
 def test_no_results_partial(self):
  with tempfile.TemporaryDirectory() as t:
   r=m.analyze(P,pathlib.Path(t),[]);self.assertEqual(r['status'],'partial_not_final');self.assertFalse(r['promotion_ready']);self.assertEqual(r['complete_requests'],0)
if __name__=='__main__':unittest.main()
