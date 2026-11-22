import unittest
import numpy as np
from lab.gradient_sanity import check_coordinate, extended_readout_loss


class GradientSanityTests(unittest.TestCase):
    def test_extended_namespace_does_not_modify_numpy(self):
        from lab.extended_host_primal import ExtendedNumpy
        original = np.complex128
        ext = ExtendedNumpy()
        self.assertIs(ext.complex128, np.clongdouble)
        self.assertIs(np.complex128, original)
        self.assertIs(ext.asarray, np.asarray)
    def test_extended_readout_single_and_differential_detectors(self):
        carrier = np.array([[1j], [2+1j]])
        signal = np.array([[1+2j, 3-1j], [4+1j, 2-3j], [2-1j, 3j], [1+1j, 2]])
        fields = np.conj(carrier)*signal[:2]+carrier*signal[2:]
        for ports in ([0], [0, 1]):
            detected = fields[0] if len(ports) == 1 else fields[0]-fields[1]
            noise = 10*np.abs(detected)
            self.assertAlmostEqual(float(extended_readout_loss(carrier, signal, noise, ports, np.ones(2))), 1., places=14)

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
                high, _ = extended_solve(products, matrix.ravel(), Factor(), rhs, trans, expected, return_extended=True)
                self.assertEqual(high.dtype, np.dtype(np.clongdouble))
                np.testing.assert_allclose(high, expected, rtol=1e-13, atol=1e-13)


if __name__ == '__main__':
    unittest.main()
