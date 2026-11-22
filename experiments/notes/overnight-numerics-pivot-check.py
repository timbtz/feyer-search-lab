"""Candidate36 second scalar estimate; synthetic correctness, no timings."""
import ast
from decimal import Decimal, localcontext
from pathlib import Path
import subprocess
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
PARENT = '7a9480332bad29b5aaeacc5a4628481581507e7a'


def load(source):
    names = {'_collinear_coefficient', '_Products', '_solve'}
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    ns = dict(np=np, REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'pivot-kernels', 'exec'), ns)
    return ns


class Pattern:
    def __init__(self, size):
        self.size = size
        self.rows = self.cols = np.arange(size)


old = load(subprocess.check_output(['git', 'show', PARENT+':differometor/host_pass.py'],
                                  cwd=ROOT, text=True))
new = load((ROOT/'differometor/host_pass.py').read_text())
rng = np.random.default_rng(36)
retained = recovered = fallback = near_rejected = 0
worst_reused = worst_refined = 0.
for size in (2, 5, 13, 37):
    for trial in range(100):
        direction = rng.normal(size=size)+1j*rng.normal(size=size)
        direction[rng.random(size)<.5] = 0
        if not np.any(direction):
            direction[0] = 1
        for scalar in (1., -2., .5j, .3+.7j, rng.normal()+1j*rng.normal()):
            vector = scalar*direction
            before = old['_collinear_coefficient'](vector, direction)
            after = new['_collinear_coefficient'](vector, direction)
            if before is not None:
                # Preserve the original scalar bits, not just an approximate value.
                assert np.asarray(before).tobytes() == np.asarray(after).tobytes()
                retained += 1
            elif after is None:
                fallback += 1
            else:
                assert np.array_equal(vector, after*direction)
                recovered += 1
                # All recovered paths also exercise the real refined solve and
                # an independent Decimal oracle. Condition numbers up to 1e12.
                diagonal = np.geomspace(1., (1., 1e-4, 1e-12)[trial % 3], size)
                pattern = Pattern(size)
                values = diagonal.astype(complex)
                factor = splu(csc_matrix(np.diag(values)))
                products = new['_Products'](pattern)
                weight = new['_solve'](products, values, factor, np.conj(direction), 'H')
                reused = after*np.conj(weight)
                refined = new['_solve'](products, values, factor, vector, 'T')
                with localcontext() as ctx:
                    ctx.prec = 70
                    expected = np.array([
                        complex(float(Decimal.from_float(float(v.real))/Decimal.from_float(float(d))),
                                float(Decimal.from_float(float(v.imag))/Decimal.from_float(float(d))))
                        for v, d in zip(vector, diagonal)])
                scale = np.max(np.abs(expected))
                worst_reused = max(worst_reused, float(np.max(np.abs(reused-expected))/scale))
                worst_refined = max(worst_refined, float(np.max(np.abs(refined-expected))/scale))
                np.testing.assert_allclose(reused, expected, rtol=2e-15, atol=0)
                np.testing.assert_allclose(refined, expected, rtol=2e-15, atol=0)
            # Add a small component outside the direction's support. This
            # remains rejected even when the scalar estimate can be recovered.
            padded_direction = np.append(direction, 0)
            perturbed = np.append(vector, 4*np.finfo(float).eps*np.max(np.abs(vector)))
            assert new['_collinear_coefficient'](perturbed, padded_direction) is None
            near_rejected += 1
assert recovered > 0
print(dict(retained_identical_scalar=retained, recovered_exact_products=recovered,
           still_refined=fallback, perturbed_vectors_rejected=near_rejected,
           recovered_solve_checks=recovered, worst_scaled_reuse_error=worst_reused,
           worst_scaled_refined_error=worst_refined,
           scope='synthetic diagonal systems only; no optical workload or timing'))
