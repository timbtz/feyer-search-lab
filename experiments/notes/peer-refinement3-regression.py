"""Exercise the actual solve method with a controlled inexact linear solver.

This validates iteration/control semantics, not the full optical benchmark or
SuperLU's accuracy on any particular matrix.
"""
import ast
from pathlib import Path
import unittest
import numpy as np

SOURCE = (Path(__file__).resolve().parents[2] / 'differometor/host.py').read_text()
TREE = ast.parse(SOURCE)
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'SparseSystem')
METHOD = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name == 'solve')
NS = {'np': np}
exec(compile(ast.fix_missing_locations(ast.Module(body=[METHOD], type_ignores=[])), '<actual-peer-solve>', 'exec'), NS)


class Toy:
    solve = NS['solve']
    def __init__(self, matrix, error=0):
        self.matrix, self.error, self.calls = matrix, error, []
    def op(self, trans):
        return {'N': self.matrix, 'T': self.matrix.T, 'H': self.matrix.conj().T}[trans]
    def _solve_once(self, rhs, trans):
        self.calls.append(trans)
        return np.linalg.solve(self.op(trans), rhs) * (1 + self.error)
    def matvec(self, x, trans):
        return self.op(trans) @ x


class RefinementRegression(unittest.TestCase):
    def test_ill_scaled_all_three_operators_improve(self):
        matrix = np.array([[1, 0.1j], [0, 1e-12]], dtype=np.complex128)
        expected = np.array([1+2j, 3-1j])
        for trans in ('N', 'T', 'H'):
            with self.subTest(trans=trans):
                engine = Toy(matrix, error=1e-3)
                rhs = engine.op(trans) @ expected
                before = rhs.copy()
                one = np.linalg.solve(engine.op(trans), rhs) * 1.001
                one += np.linalg.solve(engine.op(trans), rhs-engine.op(trans)@one)*1.001
                actual = engine.solve(rhs, trans)
                self.assertLess(np.linalg.norm(actual-expected), np.linalg.norm(one-expected))
                self.assertLess(np.linalg.norm(rhs-engine.op(trans)@actual), np.linalg.norm(rhs-engine.op(trans)@one))
                self.assertEqual(engine.calls, [trans]*4)
                np.testing.assert_array_equal(rhs, before)
    def test_at_least_one_correction_even_exact_initial_solve(self):
        engine = Toy(np.diag([1., 1e-12]).astype(np.complex128))
        expected = np.array([1., 2.])
        np.testing.assert_allclose(engine.solve(engine.matrix @ expected), expected)
        self.assertEqual(engine.calls, ['N', 'N'])
    def test_zero_rhs_still_one_correction(self):
        engine = Toy(np.eye(2, dtype=np.complex128))
        np.testing.assert_array_equal(engine.solve(np.zeros(2)), np.zeros(2))
        self.assertEqual(len(engine.calls), 2)

if __name__ == '__main__':
    unittest.main()
