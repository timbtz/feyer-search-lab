import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lab import amd_preflight


class AmdPreflightTests(unittest.TestCase):
    def run_check(self, *, dirty=False, version='0.9.0', reference=True, cpu=2):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            pristine = workspace / 'feyer-pristine'
            pristine.mkdir()
            if reference:
                (pristine / 'base1.npz').write_bytes(b'not-numerically-validated')
                (pristine / 'base1.json').write_text('{}')
            def git(repo, *args):
                if args[0] == 'show':
                    return '# official pins\njax==0.9.0\n'
                if args[0] == 'status':
                    return ' M differometor/simulate.py' if dirty else ''
                return amd_preflight.BASELINE_SHA
            # No subprocess or model execution is allowed through this fixture.
            with patch.object(amd_preflight, 'git', side_effect=git), \
                 patch.object(amd_preflight.platform, 'system', return_value='Linux'), \
                 patch.object(amd_preflight.sys, 'version_info', (3, 12, 15)), \
                 patch.object(amd_preflight.sys, 'prefix', str(workspace / 'venv-feyer')), \
                 patch.object(amd_preflight.sys, 'base_prefix', '/base-python'), \
                 patch.object(amd_preflight.os, 'sched_getaffinity', return_value={2, 3}, create=True), \
                 patch.object(amd_preflight.shutil, 'which', return_value='/usr/bin/tool'), \
                 patch.object(amd_preflight.importlib.metadata, 'version', return_value=version):
                result = amd_preflight.check(workspace / 'repo', cpu, workspace)
            return result

    def test_readiness_does_not_claim_numerical_validation(self):
        result = self.run_check()
        self.assertTrue(result['ready_for_calibration_review'])
        self.assertIn('No physics', result['limits'])
        archive = next(c for c in result['checks'] if c['name'] == 'reference_archive')
        self.assertEqual(len(archive['detail']['sha256']), 64)
        json.dumps(result, allow_nan=False)

    def test_dirty_source_dependency_drift_and_missing_reference_fail(self):
        for args, failed_name in [({'dirty': True}, 'pristine_source'),
                                  ({'version': 'other'}, 'package_jax'),
                                  ({'reference': False}, 'reference_archive')]:
            with self.subTest(args=args):
                result = self.run_check(**args)
                self.assertFalse(result['ready_for_calibration_review'])
                self.assertFalse(next(c for c in result['checks'] if c['name'] == failed_name)['passed'])

    def test_unavailable_or_boolean_cpu_fails(self):
        for cpu in (0, True):
            self.assertFalse(self.run_check(cpu=cpu)['ready_for_calibration_review'])


if __name__ == '__main__':
    unittest.main()
