"""Algebraic counterexamples and source guards; no optical benchmark is executed."""
import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def counterexamples():
    eps = 8 * sys.float_info.epsilon
    # A=diag(1,1e-20), direction=(1,0), cotangent=(1,1e-16).
    cotangent, direction = (1., 1e-16), (1., 0.)
    alpha = sum(a*b for a,b in zip(direction,cotangent)) / sum(a*a for a in direction)
    residual = max(abs(a-alpha*b) for a,b in zip(cotangent,direction))
    signal = (1., 1e-16 / 1e-20)
    # N=[[1,0],[delta,1]], w=(0,1), A=diag(1e-20,1).
    # A^-1 N^T w differs materially from A^-1 N w.
    delta = 1e-16
    return {'scope':'Algebraic guard counterexamples, not an observed optical Setup failure.',
            'old_tolerance':eps,
            'collinearity':{'old_guard_accepts':residual <= eps, 'discarded_cotangent':residual,
                           'explicit_solution':signal,'approximate_reuse':(1.,0.),'max_error':signal[1]},
            'hermitian':{'old_guard_accepts':delta <= eps,'operator_asymmetry':delta,
                         'explicit_solution':(delta/1e-20,1.),'approximate_reuse':(0.,1.),'max_error':delta/1e-20}}


class ExactAdjointRegression(unittest.TestCase):
    def test_small_cotangent_residual_is_amplified(self):
        x=counterexamples()['collinearity'];self.assertTrue(x['old_guard_accepts']);self.assertGreater(x['max_error'],9999.)

    def test_small_operator_asymmetry_is_amplified(self):
        x=counterexamples()['hermitian'];self.assertTrue(x['old_guard_accepts']);self.assertGreater(x['max_error'],9999.)

    def test_no_approximate_reuse_predicates_remain(self):
        text=(ROOT/'differometor/host_pass.py').read_text();tree=ast.parse(text)
        names={n.name for n in tree.body if isinstance(n,ast.FunctionDef)}
        self.assertNotIn('_collinear_coefficient',names);self.assertNotIn('_is_hermitian',names)
        self.assertNotIn('HERMITIAN_TOLERANCE',text)

    def test_both_refined_solves_are_unconditional(self):
        tree=ast.parse((ROOT/'differometor/host_pass.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='host_backward')
        loop=next(n for n in fn.body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='row')
        assignments={n.targets[0].id:n.value for n in loop.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
        call=assignments['signal_rhs_bar'];self.assertIsInstance(call,ast.Call);self.assertEqual(call.func.id,'_solve');self.assertEqual(ast.literal_eval(call.args[-1]),'T')
        calls=[n for n in ast.walk(assignments['adjoint']) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_solve']
        self.assertEqual(len(calls),1);self.assertEqual(ast.literal_eval(calls[0].args[-1]),'N')
        self.assertIn('covariance_rhs_bar',assignments)


if __name__=='__main__':
    if '--json' in sys.argv:print(json.dumps(counterexamples(),indent=2))
    else:unittest.main()
