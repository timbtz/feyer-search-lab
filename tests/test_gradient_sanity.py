import unittest
import numpy as np
from lab.gradient_sanity import check_coordinate


class GradientSanityTests(unittest.TestCase):
    def test_correct_quadratic(self):
        point = np.array([2., 3.])
        r = check_coordinate(lambda p: p @ p, point, 0, 4., .01)
        self.assertEqual(r['status'], 'passed')

    def test_wrong_gradient_fails_stable_difference(self):
        r = check_coordinate(lambda p: p @ p, np.array([2.]), 0, 1., .01)
        self.assertEqual(r['status'], 'failed')

    def test_unstable_difference_is_inconclusive(self):
        r = check_coordinate(lambda p: np.sin(100 * p[0]), np.array([0.]), 0, 100., .1)
        self.assertEqual(r['status'], 'inconclusive')

    def test_boundary_one_sided_is_second_order(self):
        for direction in (-1, 1):
            r = check_coordinate(lambda p: p[0] ** 2 + 3 * p[0], np.array([0.]), 0, 3., .01, direction=direction)
            self.assertEqual(r['status'], 'passed')

    def test_nonfinite_cannot_pass(self):
        r = check_coordinate(lambda p: float('nan'), np.array([1.]), 0, 1., .01)
        self.assertNotEqual(r['status'], 'passed')


if __name__ == '__main__':
    unittest.main()
