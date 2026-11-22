import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import numpy as np

from lab.transfer_validation import (INPUTS, OUTPUTS, PHASES, THREADS, WORKLOADS,
                                     audit_archive, audit_arrays, validate_official_report)
from lab.transfer_run import checked_harness, reserve


def arrays():
    return {k: np.ones(3, dtype='complex128' if k in ('carrier', 'signal') else 'float64')
            for k in OUTPUTS + INPUTS}


def report(setup='aligo'):
    spec = WORKLOADS[setup]
    return {'benchmark': spec['benchmark'], 'source': {'commit': 'a' * 40, 'modified': False},
            'starter_sha256': 'entry', 'benchmark_harness_sha256': 'harness',
            'inputs': {'frequency_count': 101, 'gradient_parameter_count': spec['variables'],
                       'setup_sha256': spec['setup'], 'reference_sha256': spec['reference']},
            'environment': {'cpu_affinity_ids': [2], 'cpu_affinity_count': 1, 'requested_logical_cpus': 1,
                            'thread_limits': dict.fromkeys(THREADS, '1'), 'backend': 'cpu',
                            'jax_enable_x64': True, 'persistent_compilation_cache': False},
            'phases': [{'key': k, 'seconds': 1.0} for k in PHASES],
            'timing_seconds': {'end_to_end': 14., 'trace_lower_and_compile': 6.},
            'validation': {'all_outputs_and_gradients_finite': True, 'upstream_sensitivity_check_passed': True,
                           'gradient_check': {'passed': True}, 'gradient_shape': [spec['variables']],
                           'gradient_norm': 1., 'loss': -0.1, 'sensitivity_log_atol': spec['tolerance'],
                           'max_absolute_log_sensitivity_error': 0.,
                           'output_dtypes': {'carrier': 'complex128', 'signal': 'complex128', 'noise': 'float64'}}}


def validate(r):
    return validate_official_report(r, setup='aligo', cpu=2, candidate_sha='a' * 40,
                                   harness_hashes={'benchmark.py': 'harness', 'benchmark_aligo.py': 'entry'})


class ArrayAuditTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(audit_arrays(arrays(), arrays())['passed'])

    def test_physical_output_changes_fail_even_if_sensitivity_gradient_match(self):
        for key in ('carrier', 'signal', 'noise', 'powers', 'loss'):
            with self.subTest(key=key):
                b = arrays(); b[key][0] *= 2
                self.assertFalse(audit_arrays(arrays(), b)['passed'])

    def test_nan_loss_fails(self):
        b = arrays(); b['loss'][0] = np.nan
        self.assertFalse(audit_arrays(arrays(), b)['passed'])

    def test_shape_broadcast_is_not_accepted(self):
        b = arrays(); b['sensitivity'] = b['sensitivity'][:, None]
        self.assertFalse(audit_arrays(arrays(), b)['passed'])

    def test_float32_fails(self):
        b = arrays(); b['gradient'] = b['gradient'].astype('float32')
        self.assertFalse(audit_arrays(arrays(), b)['passed'])

    def test_zero_gradient_fails_even_if_reference_zero(self):
        a = arrays(); a['gradient'][:] = 0
        self.assertFalse(audit_arrays(a, a)['passed'])

    def test_small_gradient_component_not_hidden_by_norm(self):
        a = arrays(); a['gradient'] = np.array([1e6, 1., 1.])
        b = copy.deepcopy(a); b['gradient'][1] += .01
        self.assertLess(np.linalg.norm(a['gradient'] - b['gradient']) / np.linalg.norm(a['gradient']), 1e-4)
        self.assertFalse(audit_arrays(a, b)['passed'])

    def test_inputs_must_match_exactly(self):
        for key in INPUTS:
            b = arrays(); b[key][0] += 1e-10
            self.assertFalse(audit_arrays(arrays(), b)['passed'])

    def test_missing_and_nonfinite_reference_fail(self):
        self.assertFalse(audit_arrays({}, arrays())['passed'])
        a = arrays(); a['signal'][0] = np.inf
        self.assertFalse(audit_arrays(a, arrays())['passed'])

    def test_negative_sensitivity_fails(self):
        a = arrays(); a['sensitivity'][:] = -1
        self.assertFalse(audit_arrays(a, a)['passed'])

    def test_empty_archive_and_expected_missing_case_do_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / 'a.npz', Path(d) / 'b.npz'
            np.savez(a); np.savez(b)
            self.assertFalse(audit_archive(a, b, ['aligo'])['passed'])
            with self.assertRaises(ValueError):
                audit_archive(a, b, [])

    def test_error_case_and_partial_suite_fail(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / 'a.npz', Path(d) / 'b.npz'
            values = {'dev/' + k: v for k, v in arrays().items()}
            np.savez(a, **values); np.savez(b, **values)
            self.assertFalse(audit_archive(a, b, ['dev', 'aligo'])['passed'])
            np.savez(a, **values, **{'dev/error': 'error'})
            self.assertFalse(audit_archive(a, b, ['dev'])['passed'])


class OfficialReportTests(unittest.TestCase):
    def test_valid_aligo_and_allowed_package_flags(self):
        r = report(); r['environment']['xla_flags'] = '--xla_cpu_use_fusion_emitters=false'
        self.assertTrue(validate(r)['passed'])

    def test_aligo_requires_stricter_tolerance(self):
        r = report(); r['validation']['max_absolute_log_sensitivity_error'] = 2e-6
        self.assertFalse(validate(r)['passed'])
        r['validation']['sensitivity_log_atol'] = 1e-5
        self.assertFalse(validate(r)['passed'])

    def test_custom_100_frequency_probe_is_not_official_aligo(self):
        r = report(); r['inputs']['frequency_count'] = 100
        self.assertFalse(validate(r)['passed'])

    def test_wrong_source_and_hashes_fail(self):
        for key in ('starter_sha256', 'benchmark_harness_sha256'):
            r = report(); r[key] = 'wrong'
            self.assertFalse(validate(r)['passed'])
        r = report(); r['source']['modified'] = True
        self.assertFalse(validate(r)['passed'])

    def test_multiple_cpus_threads_cache_and_float32_fail(self):
        for key, value in [('cpu_affinity_ids', [2, 34]), ('cpu_affinity_count', 2),
                           ('requested_logical_cpus', 2), ('cpu_affinity_count', True),
                           ('requested_logical_cpus', True), ('persistent_compilation_cache', True),
                           ('jax_enable_x64', False), ('thread_limits', {})]:
            r = report(); r['environment'][key] = value
            self.assertFalse(validate(r)['passed'])

    def test_missing_compile_or_import_time_cannot_be_score(self):
        for key in ('imports', 'forward_compile', 'gradient_compile', 'host_transfer'):
            r = report(); r['phases'] = [x for x in r['phases'] if x['key'] != key]
            r['timing_seconds']['end_to_end'] = 13.
            self.assertFalse(validate(r)['passed'])

    def test_warm_time_cannot_replace_first_run(self):
        r = report(); r['timing_seconds']['end_to_end'] = 3.
        self.assertFalse(validate(r)['passed'])

    def test_nan_or_forged_compile_sum_fails(self):
        r = report(); r['timing_seconds']['trace_lower_and_compile'] = 0.
        self.assertFalse(validate(r)['passed'])
        r = report(); r['phases'][0]['seconds'] = float('nan')
        self.assertFalse(validate(r)['passed'])

    def test_missing_gradient_sanity_check_fails(self):
        r = report(); r['validation']['gradient_check']['passed'] = None
        self.assertFalse(validate(r)['passed'])


class OperationalTests(unittest.TestCase):
    def test_vendored_harness_hashes_match(self):
        self.assertEqual(len(checked_harness()['files']), 3)

    def test_modified_harness_rejected(self):
        import shutil
        from lab.transfer_run import VENDOR
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'vendor'; shutil.copytree(VENDOR, target)
            (target / 'benchmark.py').write_text('changed')
            with self.assertRaises(ValueError):
                checked_harness(target)

    def test_pending_queue_not_bypassed_and_lock_released(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with sqlite3.connect(root / 'queue.sqlite3') as db:
                db.execute('CREATE TABLE jobs (status TEXT)'); db.execute("INSERT INTO jobs VALUES ('queued')")
            with self.assertRaises(RuntimeError):
                with reserve([root]):
                    self.fail('Pending job must retain priority')
            with sqlite3.connect(root / 'queue.sqlite3') as db:
                db.execute('DELETE FROM jobs')
            with reserve([root]) as fds:
                self.assertEqual(len(fds), 1)

    def test_live_worker_lock_not_bypassed(self):
        import fcntl
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with sqlite3.connect(root / 'queue.sqlite3') as db:
                db.execute('CREATE TABLE jobs (status TEXT)')
            with (root / 'worker.lock').open('a+') as h:
                fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    with reserve([root]):
                        self.fail('Running job must retain lock')


if __name__ == '__main__':
    unittest.main()
