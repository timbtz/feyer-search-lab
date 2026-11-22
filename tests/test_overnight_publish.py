import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid

from lab import overnight_publish as mod

SEED = 'a' * 40
COHORT = 'b' * 64


def receipt(candidate=SEED, large=1., aligo=.6):
    result = {'schema_version': 'feyer-overnight-evaluation-v1',
              'evaluation_id': uuid.uuid4().hex, 'candidate_sha': candidate, 'cohort_digest': COHORT,
              'admission': {'promotion_ready': True, 'candidate_sha': candidate,
                            'comparison_cohort_passed': True},
              'source_review': {'approved': True, 'candidate_sha': candidate, 'parent_sha': SEED,
                                'diff_sha256': 'f' * 64, 'reviewer': 'independent-reviewer',
                                'provider': 'test', 'model': 'test', 'session_id': 'review-session',
                                'scope': 'no-fixture-specialization-and-integrity',
                                'artifact_path': 'review.json', 'artifact_sha256': 'e' * 64,
                                'diff_path': 'source.diff'},
              'generalization': {'case_count': 14, 'all_finite': True, 'inputs_identical': True,
                                 'seed_comparison_passed': True, 'new_failures': []}, 'benchmarks': {}}
    for setup, value in [('grid', large), ('aligo', aligo)]:
        result['benchmarks'][setup] = {'samples': [
            {'seconds': value + i * .0001, 'candidate_sha': candidate,
             'fresh_process': True, 'official_passed': True, 'report_sha256': str(i + 1) * 64,
             'report_path': setup + str(i) + '.json'} for i in range(3)]}
    return result


def best():
    return {'status': 'admitted_campaign_best', 'candidate_sha': SEED, 'cohort_digest': COHORT,
            'metrics': {'grid': {'median_seconds': 1., 'min_seconds': .985, 'max_seconds': 1.015},
                        'aligo': {'median_seconds': .6, 'min_seconds': .599, 'max_seconds': .601}}}


class AssessmentTests(unittest.TestCase):
    def test_good_gain_and_separate_aligo(self):
        decision = mod.assess(receipt('c' * 40, .98, .6), best())
        self.assertTrue(decision['promote'])
        self.assertAlmostEqual(decision['metrics']['grid']['median_seconds'], .9801)

    def test_official_pass_alone_not_sufficient(self):
        r = receipt('c' * 40, .8)
        r['generalization']['seed_comparison_passed'] = False
        self.assertIn('incomplete_generalization', mod.assess(r, best())['reasons'])
        r['generalization']['seed_comparison_passed'] = True
        r['generalization']['new_failures'] = ['gradient regression']
        self.assertIn('unresolved_new_failures', mod.assess(r, best())['reasons'])

    def test_bad_admission_and_cohort(self):
        for key, value in [('promotion_ready', False), ('candidate_sha', SEED), ('comparison_cohort_passed', False)]:
            r = receipt('c' * 40, .8); r['admission'][key] = value
            self.assertFalse(mod.assess(r, best())['promote'])
        r = receipt('c' * 40, .8); r['cohort_digest'] = 'd' * 64
        self.assertIn('comparison_cohort_mismatch', mod.assess(r, best())['reasons'])

    def test_source_review_required_for_new_winners_but_not_seed_calibration(self):
        for field, value in [('approved', False), ('candidate_sha', SEED), ('scope', 'tests-only'),
                             ('parent_sha', 'unknown'), ('session_id', ''), ('artifact_sha256', '')]:
            r = receipt('c' * 40, .8); r['source_review'][field] = value
            with self.subTest(field=field): self.assertIn('requires_source_review', mod.assess(r, best())['reasons'])
        r = receipt(); r.pop('source_review')
        self.assertTrue(mod.assess(r, {'status': 'seed_pending_fresh_calibration', 'candidate_sha': SEED})['promote'])

    def test_missing_review_does_not_hide_independent_timing_objections(self):
        r = receipt('c' * 40, 1.1, .65); r.pop('source_review')
        reasons = mod.assess(r, best())['reasons']
        self.assertIn('requires_source_review', reasons)
        self.assertIn('large_gain_below_selection_threshold', reasons)
        self.assertIn('aligo_regression_over_two_percent', reasons)
        self.assertIn('large_first_run_ranges_overlap_requires_paired_evidence', reasons)

    def test_missing_repetitions_duplicates_and_warm_samples(self):
        for mutation in ('missing', 'duplicate', 'warm', 'wrong_source', 'nan', 'bool'):
            r = receipt('c' * 40, .8); samples = r['benchmarks']['grid']['samples']
            if mutation == 'missing': samples.pop()
            if mutation == 'duplicate': samples[1]['report_sha256'] = samples[0]['report_sha256']
            if mutation == 'warm': samples[1]['fresh_process'] = False
            if mutation == 'wrong_source': samples[1]['candidate_sha'] = SEED
            if mutation == 'nan': samples[1]['seconds'] = float('nan')
            if mutation == 'bool': samples[1]['seconds'] = True
            with self.subTest(mutation=mutation): self.assertFalse(mod.assess(r, best())['promote'])

    def test_selection_heuristics(self):
        for large, aligo, expected in [(.999, .59, 'large_gain_below_selection_threshold'),
                                       (.8, .62, 'aligo_regression_over_two_percent')]:
            self.assertIn(expected, mod.assess(receipt('c' * 40, large, aligo), best())['reasons'])
        r = receipt('c' * 40, .8); r['benchmarks']['grid']['samples'][0]['seconds'] = .5
        self.assertIn('grid_unstable_timing', mod.assess(r, best())['reasons'])

    def test_faster_median_with_overlapping_ranges_stays_provisional(self):
        r = receipt('c' * 40, .989)
        decision = mod.assess(r, best())
        self.assertIn('large_first_run_ranges_overlap_requires_paired_evidence', decision['reasons'])
        self.assertFalse(decision['timing_comparison']['observed_ranges_nonoverlapping'])
        self.assertEqual(decision['policy']['version'], 'overnight-selection-v2')

    def test_range_boundary_is_strict_and_missing_incumbent_range_fails_closed(self):
        r = receipt('c' * 40, .98)
        r['benchmarks']['grid']['samples'][-1]['seconds'] = .985
        self.assertIn('large_first_run_ranges_overlap_requires_paired_evidence', mod.assess(r, best())['reasons'])
        current = best(); del current['metrics']['grid']['min_seconds']
        self.assertIn('incumbent_timing_range_unavailable', mod.assess(receipt('c' * 40, .98), current)['reasons'])

    def test_existing_v1_best_can_be_compared_without_rewriting_its_admission(self):
        current = best(); current['policy'] = {'version': 'overnight-selection-v1'}
        before = copy.deepcopy(current)
        self.assertTrue(mod.assess(receipt('c' * 40, .98), current)['promote'])
        self.assertEqual(current, before)

    def test_pending_seed_only_admits_calibration_of_that_seed(self):
        current = {'status': 'seed_pending_fresh_calibration', 'candidate_sha': SEED}
        self.assertTrue(mod.assess(receipt(), current)['promote'])
        self.assertIn('seed_fresh_calibration_required', mod.assess(receipt('c' * 40, .8), current)['reasons'])


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.repo = self.root / 'control'; self.remote = self.root / 'remote.git'
        self.evidence = self.root / 'evidence'; self.evidence.mkdir()
        subprocess.run(['git', 'init', '--bare', str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git', 'init', '-b', mod.BRANCH, str(self.repo)], check=True, capture_output=True)
        mod.git(self.repo, 'config', 'user.name', 'Test'); mod.git(self.repo, 'config', 'user.email', 'test@example.invalid')
        (self.repo / 'README.md').write_text('control')
        mod.git(self.repo, 'add', 'README.md'); mod.git(self.repo, 'commit', '-m', 'initial')
        mod.git(self.repo, 'remote', 'add', 'origin', str(self.remote))
        self.publisher = mod.Publisher(self.repo, self.evidence)
        self.manifest = self.root / 'seed.json'
        self.manifest.write_bytes(mod.encoded({'recommended_seed_sha': SEED, 'extra_validation_notes': ['Inherited strict discrepancy'],
            'timing_caveat': 'Historical support audit, not current cohort.', 'official_evidence': {
                k: {'median_seconds': value, 'min_seconds': value, 'max_seconds': value} for k, value in [('grid', 1.), ('aligo', .6)]}}))
        self.assertTrue(self.publisher.initialize(self.manifest)['published'])

    def write_receipt(self, value=None):
        value = value or receipt(); folder = self.evidence / value['evaluation_id']; folder.mkdir()
        for setup, bench in value['benchmarks'].items():
            for i, sample in enumerate(bench['samples']):
                report = {'source': {'commit': value['candidate_sha'], 'modified': False},
                          'timing_seconds': {'end_to_end': sample['seconds']}, 'run_id': i,
                          'inputs': {'frequency_count': 101, 'gradient_parameter_count': 193 if setup == 'grid' else 29},
                          'validation': {'all_outputs_and_gradients_finite': True,
                                         'upstream_sensitivity_check_passed': True,
                                         'gradient_check': {'passed': True}}}
                path = folder / f'{setup}-{i}.json'; data = mod.encoded(report); path.write_bytes(data)
                sample['report_path'] = str(path.relative_to(self.evidence)); sample['report_sha256'] = mod.digest(data)
        if value.get('source_review'):
            review = value['source_review']; diff = b'Example independently reviewed source diff\n'
            diff_path = folder / 'source.diff'; diff_path.write_bytes(diff)
            review['diff_sha256'] = mod.digest(diff); review['diff_path'] = str(diff_path.relative_to(self.evidence))
            artifact = {k: v for k, v in review.items() if k not in ('artifact_path', 'artifact_sha256', 'diff_path')}
            review_path = folder / 'source-review.json'; review_data = mod.encoded(artifact); review_path.write_bytes(review_data)
            review['artifact_path'] = str(review_path.relative_to(self.evidence)); review['artifact_sha256'] = mod.digest(review_data)
        path = folder / 'receipt.json'; path.write_bytes(mod.encoded(value)); return path

    def calibrate(self):
        return self.publisher.publish(self.write_receipt())

    def current(self):
        return json.loads((self.repo / mod.BEST).read_bytes())

    def test_seed_pending_then_calibrated_and_improvement_pushed(self):
        self.assertEqual(self.current()['status'], 'seed_pending_fresh_calibration')
        self.assertTrue(self.calibrate()['published'])
        self.assertEqual(self.current()['status'], 'admitted_campaign_best')
        self.assertFalse(any('calibration is pending' in v for v in self.current()['caveats']))
        result = self.publisher.publish(self.write_receipt(receipt('c' * 40, .97)))
        self.assertTrue(result['published']); self.assertEqual(self.current()['candidate_sha'], 'c' * 40)
        self.assertEqual(mod.git(self.remote, 'rev-parse', mod.BRANCH), result['commit_sha'])
        self.assertIn('Inherited strict discrepancy', (self.repo / 'CURRENT_BEST.md').read_text())

    def test_provisional_saved_without_moving_best(self):
        self.calibrate(); value = receipt('c' * 40, .5); value['generalization']['new_failures'] = ['bad']
        result = self.publisher.publish(self.write_receipt(value))
        self.assertTrue(result['published']); self.assertFalse(result['decision']['promote'])
        self.assertEqual(self.current()['candidate_sha'], SEED)
        self.assertTrue((self.repo / mod.PREFIX / 'candidates' / value['evaluation_id'] / 'record.json').exists())

    def test_overlapping_faster_trial_is_published_without_replacing_best(self):
        self.calibrate(); value = receipt('c' * 40, .98)
        for sample, seconds in zip(value['benchmarks']['grid']['samples'], [.98, .99, 1.001]):
            sample['seconds'] = seconds
        result = self.publisher.publish(self.write_receipt(value))
        self.assertTrue(result['published'])
        self.assertIn('large_first_run_ranges_overlap_requires_paired_evidence', result['decision']['reasons'])
        self.assertEqual(self.current()['candidate_sha'], SEED)
        self.assertTrue((self.repo / mod.PREFIX / 'candidates' / value['evaluation_id'] / 'record.json').exists())

    def test_retry_idempotent_and_collision_rejected(self):
        path = self.write_receipt(); first = self.publisher.publish(path); head = mod.git(self.repo, 'rev-parse', 'HEAD')
        second = self.publisher.publish(path)
        self.assertEqual(second['publication_status'], 'already_published')
        self.assertEqual(second['decision'], first['decision'])
        self.assertEqual(second['commit_sha'], first['commit_sha'])
        self.assertEqual(head, mod.git(self.repo, 'rev-parse', 'HEAD'))
        value = json.loads(path.read_bytes()); value['caveats'] = ['changed']; path.write_bytes(mod.encoded(value))
        with self.assertRaisesRegex(ValueError, 'different evidence'): self.publisher.publish(path)

    def test_already_published_does_not_trust_an_unpushed_or_dirty_local_record(self):
        path = self.write_receipt(); result = self.publisher.publish(path)
        marker = self.publisher.state / ('published-' + result['evaluation_id'] + '.json')
        marker.unlink()
        with self.assertRaisesRegex(ValueError, 'verified publication'): self.publisher.publish(path)

    def test_push_failure_keeps_outbox_and_retry_commits_only_once(self):
        mod.git(self.repo, 'remote', 'set-url', 'origin', str(self.root / 'missing'))
        result = self.calibrate(); self.assertFalse(result['published'])
        self.assertTrue((self.publisher.state / 'pending.json').exists())
        head = mod.git(self.repo, 'rev-parse', 'HEAD')
        mod.git(self.repo, 'remote', 'set-url', 'origin', str(self.remote))
        self.assertTrue(self.publisher.retry()['published'])
        self.assertFalse((self.publisher.state / 'pending.json').exists())
        self.assertEqual(head, mod.git(self.repo, 'rev-parse', 'HEAD'))

    def test_crash_after_commit_recovers_without_duplicate_commit(self):
        original = mod.git
        def crash(worktree, *args):
            output = original(worktree, *args)
            if args[0] == 'commit': raise RuntimeError('simulated process death after commit')
            return output
        with patch.object(mod, 'git', side_effect=crash):
            with self.assertRaises(RuntimeError): self.calibrate()
        head = mod.git(self.repo, 'rev-parse', 'HEAD')
        self.assertTrue(self.publisher.retry()['published'])
        self.assertEqual(head, mod.git(self.repo, 'rev-parse', 'HEAD'))

    def test_two_publishers_serialize_without_lost_best_or_receipts(self):
        self.calibrate(); paths = [self.write_receipt(receipt('c' * 40, .98)), self.write_receipt(receipt('d' * 40, .95))]
        def run(path): return mod.Publisher(self.repo, self.evidence).publish(path)
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, paths))
        self.assertTrue(all(r['published'] for r in results)); self.assertEqual(self.current()['candidate_sha'], 'd' * 40)
        for path in paths:
            evaluation_id = json.loads(path.read_bytes())['evaluation_id']
            self.assertTrue((self.repo / mod.PREFIX / 'candidates' / evaluation_id / 'record.json').exists())

    def test_report_digest_source_and_timing_checked(self):
        for kind in ('hash', 'source', 'time', 'modified', 'official_fail', 'workload'):
            with self.subTest(kind=kind):
                path = self.write_receipt(); value = json.loads(path.read_bytes()); sample = value['benchmarks']['grid']['samples'][0]
                reportpath = self.evidence / sample['report_path']; report = json.loads(reportpath.read_bytes())
                if kind == 'source': report['source']['commit'] = 'e' * 40
                elif kind == 'modified': report['source']['modified'] = True
                elif kind == 'official_fail': report['validation']['gradient_check']['passed'] = False
                elif kind == 'workload': report['inputs']['frequency_count'] = 100
                else: report['timing_seconds']['end_to_end'] = 99.
                data = mod.encoded(report); reportpath.write_bytes(data)
                if kind != 'hash': sample['report_sha256'] = mod.digest(data); path.write_bytes(mod.encoded(value))
                with self.assertRaises(ValueError): self.publisher.publish(path)

    def test_untrusted_path_and_dirty_worktree_rejected(self):
        path = self.write_receipt()
        outside = self.root / 'outside.json'; outside.write_bytes(path.read_bytes())
        with self.assertRaises(ValueError): self.publisher.publish(outside)
        (self.repo / 'unrelated.txt').write_text('owned elsewhere')
        with self.assertRaisesRegex(ValueError, 'clean'): self.publisher.publish(path)

    def test_missing_review_keeps_candidate_provisional_and_tampering_rejected(self):
        self.calibrate(); value = receipt('c' * 40, .8); value.pop('source_review')
        result = self.publisher.publish(self.write_receipt(value))
        self.assertIn('requires_source_review', result['decision']['reasons'])
        self.assertEqual(self.current()['candidate_sha'], SEED)
        for field in ('artifact_path', 'diff_path'):
            path = self.write_receipt(receipt('c' * 40, .8)); data = json.loads(path.read_bytes())
            (self.evidence / data['source_review'][field]).write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'digest'): self.publisher.publish(path)

    def test_other_branch_rejected(self):
        mod.git(self.repo, 'checkout', '-b', 'main')
        with self.assertRaisesRegex(ValueError, 'dedicated'): mod.Publisher(self.repo, self.evidence)


if __name__ == '__main__': unittest.main()
