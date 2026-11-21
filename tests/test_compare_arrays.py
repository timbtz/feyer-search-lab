"""Numerical diagnostics; execute with NumPy in the fixed evaluator environment."""
import json
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from lab.compare_arrays import compare


@unittest.skipIf(np is None, 'NumPy comparison tests require the evaluator environment')
class ArrayComparisonDiagnosticsTests(unittest.TestCase):
    def compare_arrays(self, key, reference, candidate, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'a.npz', Path(directory) / 'b.npz'
            np.savez(first, **{key: reference})
            np.savez(second, **{key: candidate})
            return compare(first, second, **kwargs)

    def test_gradient_diagnostics_keep_all_193_failures_without_changing_tolerance(self):
        reference = np.ones(193)
        result = self.compare_arrays('gradient', reference, reference + 1e-5)
        check = result['checks']['gradient']
        self.assertFalse(result['passed'])
        self.assertEqual(check['failing_count'], 193)
        self.assertEqual(len(check['failures']), 193)
        self.assertFalse(check['failures_truncated'])
        item = check['failures'][33]
        self.assertEqual(item['index'], [33])
        self.assertAlmostEqual(item['tolerance'], 1e-7 + 1e-12)
        self.assertAlmostEqual(item['normalized_error'], item['absolute_error'] / item['tolerance'])

    def test_non_gradient_diagnostics_are_bounded(self):
        result = self.compare_arrays('noise', np.ones(101), np.ones(101) + 1e-5)
        check = result['checks']['noise']
        self.assertEqual(check['failing_count'], 101)
        self.assertEqual(len(check['failures']), 20)
        self.assertTrue(check['failures_truncated'])

    def test_exact_arrays_report_infinite_ratio_as_valid_json(self):
        result = self.compare_arrays('parameters', np.zeros(2), np.ones(2))
        check = result['checks']['parameters']
        self.assertTrue(check['max_normalized_error_is_infinite'])
        self.assertIsNone(check['max_normalized_error'])
        self.assertTrue(check['failures'][0]['normalized_error_is_infinite'])
        json.dumps(result, allow_nan=False)

    def test_complex_failure_has_real_and_imaginary_values(self):
        result = self.compare_arrays('signal', np.array([1+2j]), np.array([1+3j]))
        item = result['checks']['signal']['failures'][0]
        self.assertEqual(item['reference'], {'real': 1.0, 'imag': 2.0})
        self.assertEqual(item['candidate'], {'real': 1.0, 'imag': 3.0})
        json.dumps(result, allow_nan=False)

    def test_pass_records_zero_failures(self):
        result = self.compare_arrays('gradient', np.ones(193), np.ones(193) + 1e-8)
        self.assertTrue(result['passed'])
        self.assertEqual(result['checks']['gradient']['failing_count'], 0)

    def test_nonfinite_values_fail_with_json_safe_diagnostics(self):
        result = self.compare_arrays('gradient', np.ones(2), np.array([np.nan, np.inf]))
        check = result['checks']['gradient']
        self.assertFalse(result['passed'])
        self.assertEqual(check['failing_count'], 2)
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
