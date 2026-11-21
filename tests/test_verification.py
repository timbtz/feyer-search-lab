import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lab.verification import (BINDINGS, JAXCOMPAT_TESTS, SCHEMA, assess, digest,
                              template, validate_policy, validate_verification)

SHA = 'a' * 40
OTHER = 'b' * 40
BOUND = {key: str(i) * 64 for i, key in enumerate(BINDINGS, 1)}


def check(status='passed', **overrides):
    result = dict(id='value_and_grad_jit', capability='value_and_grad_jit', setup='voyager-40',
                method='Reference output comparison', status=status,
                binding=copy.deepcopy(BOUND), evidence_kind='independent_measurement',
                source_ref='https://example.org/immutable/results.json', source_digest='e' * 64,
                observed_at=1000)
    result.update(overrides)
    return result


def receipt(*checks, sha=SHA):
    return dict(schema=SCHEMA, candidate_sha=sha, checks=list(checks or [check()]))


def policy():
    return template('challenge-first-order-review', 'voyager-40', BOUND)


class VerificationTests(unittest.TestCase):
    def test_exact_provenance_and_no_benchmark_override(self):
        p, r = policy(), receipt()
        original = copy.deepcopy((p, r))
        result = assess(SHA, p, [r])
        self.assertEqual(result['status'], 'satisfied')
        self.assertTrue(result['requirements_satisfied'])
        self.assertEqual((p, r), original)
        self.assertNotIn('eligible_full', result)
        self.assertNotIn('official_passed', result)
        self.assertIn('not evaluated or overridden', result['official_benchmark'])
        self.assertEqual(result['policy_digest'], digest(p))
        self.assertEqual(assess(OTHER, p, [r])['status'], 'incomplete')

    def test_each_binding_and_candidate_identity_are_required(self):
        for key in BINDINGS:
            r = receipt()
            del r['checks'][0]['binding'][key]
            result = assess(SHA, policy(), [r])
            self.assertEqual(result['status'], 'incomplete', key)
            self.assertTrue(result['requirements'][0]['excluded'])
            r['checks'][0]['binding'][key] = 'f' * 64
            self.assertEqual(assess(SHA, policy(), [r])['status'], 'incomplete', key)
        with self.assertRaises(ValueError):
            validate_verification(receipt(), expected_sha=OTHER)
        r = receipt()
        r['checks'][0]['candidate_sha'] = OTHER
        with self.assertRaises(ValueError):
            validate_verification(r)

    def test_pass_label_without_bound_observation_never_qualifies(self):
        for key in ['binding', 'source_ref', 'source_digest', 'observed_at', 'evidence_kind']:
            r = receipt()
            del r['checks'][0][key]
            self.assertEqual(assess(SHA, policy(), [r])['status'], 'incomplete', key)
        for kind in ['author_reported', 'source_review', 'planned']:
            r = receipt()
            r['checks'][0]['evidence_kind'] = kind
            self.assertEqual(assess(SHA, policy(), [r])['status'], 'incomplete')
        r = receipt()
        r['checks'][0].update(arrays_pass=True, overall='SETUPS PASS')
        del r['checks'][0]['binding']
        self.assertEqual(assess(SHA, policy(), [r])['status'], 'incomplete')

    def test_pending_blocked_unsupported_and_retained_failures(self):
        for status in ['pending', 'blocked']:
            self.assertEqual(assess(SHA, policy(), [receipt(check(status))])['status'], 'incomplete')
        for status in ['failed', 'needs_review', 'unsupported']:
            adverse = check(status)
            adverse['source_digest'] = 'f' * 64
            result = assess(SHA, policy(), [receipt(), receipt(adverse)])
            self.assertEqual(result['status'], 'needs_review')
            self.assertFalse(result['requirements_satisfied'])
            self.assertEqual(result['requirements'][0]['pass_count'], 1)

    def test_copies_cannot_increase_repeats_or_hide_conflicting_artifact(self):
        p = policy()
        p['requirements'][0]['minimum_passes'] = 2
        self.assertEqual(assess(SHA, p, [receipt(), receipt()])['status'], 'incomplete')
        second = check()
        second['source_digest'] = 'f' * 64
        self.assertEqual(assess(SHA, p, [receipt(), receipt(second)])['status'], 'satisfied')
        conflict = check('failed')
        self.assertEqual(assess(SHA, policy(), [receipt(), receipt(conflict)])['status'], 'needs_review')

    def test_policy_is_explicit_internal_and_broader_profile_has_eleven_uses(self):
        p = template('broader-jax-review', 'voyager-40', BOUND)
        self.assertEqual([r['capability'] for r in p['requirements']], list(JAXCOMPAT_TESTS))
        self.assertNotIn('gpu_execution', [r['capability'] for r in p['requirements']])
        self.assertEqual(assess(SHA, p, [receipt()])['status'], 'incomplete')
        for field, value in [('scope', 'official'), ('requirements', []), ('policy_id', '')]:
            broken = {**p, field: value}
            with self.assertRaises(ValueError):
                validate_policy(broken)

    def test_invalid_duplicate_and_nonfinite_receipts_rejected(self):
        for r in [receipt(check(), check()), receipt(check('done')), receipt(check(observed_at=float('nan')))]:
            with self.assertRaises(ValueError):
                validate_verification(r)
        r = receipt()
        r['checks'][0]['outputs'] = {'error': float('inf')}
        with self.assertRaises(ValueError):
            validate_verification(r)
        with self.assertRaises(ValueError):
            assess('short', policy(), [receipt()])

    def test_cli_exit_codes_and_persisted_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'policy.json').write_text(json.dumps(policy()))
            command = [sys.executable, '-m', 'lab.verification', 'assess', '--candidate-sha', SHA,
                       '--policy', str(root/'policy.json'), '--verification', str(root/'receipt.json'),
                       '--output', str(root/'decision.json')]
            for status, code in [('passed', 0), ('pending', 2), ('failed', 3)]:
                (root/'receipt.json').write_text(json.dumps(receipt(check(status))))
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads((root/'decision.json').read_text())['candidate_sha'], SHA)


class JaxcompatImportTests(unittest.TestCase):
    def comparison(self):
        return dict(setup='voyager-40', status='passed', passed=True,
                    required_tests=list(JAXCOMPAT_TESTS), issues=[],
                    checks=[dict(test=key, status='passed', max_relative_difference=0.0, issues=[])
                            for key in JAXCOMPAT_TESTS])

    def imported(self, result=None, kind='independent_measurement', reference=None):
        from unittest.mock import patch
        from lab.verification import import_jaxcompat
        comparison = self.comparison() if result is None else result
        with patch('lab.verification._jaxcompat_comparator', return_value=(lambda *a, **k: comparison, 'f'*64)):
            return import_jaxcompat(reference or {'tests': {}}, {'tests': {}}, candidate_sha=SHA,
                reference_sha=OTHER, source_ref='artifact://complete-raw-reports',
                setup_digest=BOUND['setup_digest'], harness_digest=BOUND['harness_digest'],
                environment_digest=BOUND['environment_digest'], observed_at=1000, evidence_kind=kind)

    def test_adapter_preserves_eleven_checks_gpu_unknown_and_explicit_provenance(self):
        r = self.imported()
        self.assertEqual(len(r['checks']), 12)
        p = template('broader-jax-review', 'voyager-40', r['checks'][0]['binding'])
        self.assertEqual(assess(SHA, p, [r])['status'], 'satisfied')
        self.assertEqual(r['checks'][-1]['status'], 'pending')
        self.assertEqual(r['checks'][-1]['evidence_kind'], 'planned')
        self.assertNotIn('binding', r['checks'][-1])
        self.assertEqual(assess(SHA, p, [self.imported(kind='author_reported')])['status'], 'incomplete')
        gpu = copy.deepcopy(p['requirements'][0])
        gpu.update(id='gpu', capability='gpu_execution')
        p['requirements'].append(gpu)
        self.assertEqual(assess(SHA, p, [r])['status'], 'incomplete')

    def test_comparator_missing_checks_or_inconsistent_summary_cannot_create_pass(self):
        r = self.comparison()
        r['checks'].pop()
        with self.assertRaises(ValueError):
            self.imported(r)
        r = self.comparison()
        r['checks'][0]['status'] = 'failed'
        with self.assertRaises(ValueError):
            self.imported(r)
        r['passed'] = False
        r['status'] = 'failed'
        self.assertEqual(self.imported(r)['checks'][0]['status'], 'failed')

    def test_reference_unavailable_and_global_issues_never_satisfy(self):
        r = self.comparison()
        r['checks'][0]['status'] = 'unavailable'
        r['passed'], r['status'] = False, 'failed'
        imported = self.imported(r)
        self.assertEqual(imported['checks'][0]['status'], 'blocked')
        p = template('broader-jax-review', 'voyager-40', imported['checks'][0]['binding'])
        self.assertEqual(assess(SHA, p, [imported])['status'], 'incomplete')
        r = self.comparison()
        r.update(issues=['setup mismatch'], passed=False, status='failed')
        imported = self.imported(r)
        self.assertTrue(all(c['status'] == 'needs_review' for c in imported['checks'][:-1]))
        self.assertEqual(assess(SHA, p, [imported])['status'], 'needs_review')

    def test_nonfinite_raw_report_rejected_and_reference_is_bound(self):
        with self.assertRaises(ValueError):
            self.imported(reference={'value': float('nan')})
        a = self.imported(reference={'value': [1]})
        b = self.imported(reference={'value': [2]})
        self.assertNotEqual(a['checks'][0]['binding']['acceptance_digest'],
                            b['checks'][0]['binding']['acceptance_digest'])
