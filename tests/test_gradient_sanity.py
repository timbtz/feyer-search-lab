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

    def test_extended_solver_transpose_conventions(self):
        from types import SimpleNamespace
        from lab.solver_precision_probe import extended_solve
        rng = np.random.default_rng(7)
        matrix = rng.normal(size=(5, 5)) + 1j * rng.normal(size=(5, 5)) + 8 * np.eye(5)
        rows, cols = np.indices(matrix.shape)
        products = SimpleNamespace(rows=rows.ravel(), cols=cols.ravel())
        class Factor:
            def solve(self, rhs, trans):
                a = matrix if trans == 'N' else matrix.T if trans == 'T' else matrix.conj().T
                return np.linalg.solve(a, rhs)
        for shape in [(5,), (5, 2)]:
            rhs = rng.normal(size=shape) + 1j * rng.normal(size=shape)
            for trans in ('N', 'T', 'H'):
                expected = Factor().solve(rhs, trans)
                actual, info = extended_solve(products, matrix.ravel(), Factor(), rhs, trans, expected)
                np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13)
                self.assertLessEqual(info['extended_componentwise_residual'], info['before_componentwise_residual'])


if __name__ == '__main__':
    unittest.main()
