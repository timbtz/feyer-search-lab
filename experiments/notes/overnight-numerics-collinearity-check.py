"""Candidate35 collinearity repair: small synthetic checks, no benchmark timings.

Extracts actual production guard and refined solver without requiring JAX.
The parent is candidate34, so this isolates the second guard repair.
"""
import ast
from decimal import Decimal, localcontext
from pathlib import Path
import subprocess

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
PARENT = '86860bdcbf4b02888b5db6ca2aa563234db0721a'


def load(source):
    names = {'_collinear_coefficient', '_Products', '_solve'}
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    namespace = dict(np=np, HERMITIAN_TOLERANCE=8*np.finfo(float).eps,
                     REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'collinear-kernels', 'exec'), namespace)
    return namespace


class Pattern:
    def __init__(self, size):
        self.size = size
        self.cols, self.rows = np.nonzero(np.ones((size, size), bool))


old = load(subprocess.check_output(['git', 'show', PARENT+':differometor/host_pass.py'],
                                  cwd=ROOT, text=True))
new = load((ROOT/'differometor/host_pass.py').read_text())
rng = np.random.default_rng(2026112235)
accepted = rejected = 0
for size in (2, 5, 13):
    for trial in range(20):
        storage = rng.normal(size=2*size)+1j*rng.normal(size=2*size)
        direction = storage[::2]  # Also exercise noncontiguous inputs.
        direction[-1] = 0
        for scalar in (1., -2., .5j, .3+.7j):
            vector = scalar*direction
            for perturbed in (False, True):
                candidate = vector.copy()
                if perturbed:
                    candidate[-1] = np.finfo(float).eps*np.max(np.abs(vector))
                alpha = new['_collinear_coefficient'](candidate, direction)
                if alpha is not None:
                    assert np.array_equal(candidate, alpha*direction)
                    accepted += 1
                else:
                    rejected += 1
                if perturbed:
                    assert alpha is None

# Exact and zero cases, real/complex directions, nonfinite inputs and changing
# numeric values on the same arrays. No static/current-zero derivative pruning.
special_checks = 0
for dtype in (float, complex):
    for direction in (np.array([1., 0.], dtype=dtype), np.zeros(2, dtype=dtype)):
        zero = np.array([0., -0.], dtype=dtype)
        assert new['_collinear_coefficient'](zero, direction) == 0
        special_checks += 1
    direction = np.array([1., 0.], dtype=dtype)
    for scalar in (1., -2., .5):
        assert new['_collinear_coefficient'](scalar*direction, direction) == scalar
        special_checks += 1
    for invalid in (np.nan, np.inf, -np.inf):
        bad = np.array([invalid, 0.], dtype=dtype)
        assert new['_collinear_coefficient'](bad, direction) is None
        assert new['_collinear_coefficient'](np.zeros(2, dtype=dtype), bad) is None
        special_checks += 2
assert new['_collinear_coefficient'](np.ones(2), np.zeros(2)) is None
special_checks += 1

# The host backward branch solves A^T r = vector unless the guard permits
# alpha*conj(weight), where A^H weight = selection. Reproduce that branch using
# the actual refined solver. A diagonal system gives an independent Decimal
# derivative oracle for loss(b) = vector^T A^-1 b.
repair_checks = 0
max_parent_error = max_candidate_error = 0.
for tau in (1., 1e-8, 1e-12):
    a = np.diag([1., tau]).astype(complex)
    pattern = Pattern(2)
    values = a[pattern.rows, pattern.cols]
    products = new['_Products'](pattern)
    factor = splu(csc_matrix(a))
    for scale in (2.**-20, 1., 2.**20):
        direction = np.array([scale, 0.], complex)
        weight = new['_solve'](products, values, factor, np.conj(direction), 'H')
        for phase in (1., 1j):
            epsilon = scale*4*np.finfo(float).eps
            vector = np.array([scale, phase*epsilon], complex)
            alpha_old = old['_collinear_coefficient'](vector, direction)
            alpha_new = new['_collinear_coefficient'](vector, direction)
            assert alpha_old == 1 and alpha_new is None
            old_result = alpha_old*np.conj(weight)
            new_result = new['_solve'](products, values, factor, vector, 'T')
            with localcontext() as ctx:
                ctx.prec = 70
                e = Decimal.from_float(float(epsilon))
                t = Decimal.from_float(tau)
                step = Decimal('1e-20')
                # For phase=i this is the imaginary part of the same loss.
                def loss(b):
                    return e*b/t
                fd = (loss(step)-loss(-step))/(2*step)
                expected = np.array([scale, phase*float(fd)], complex)
            np.testing.assert_allclose(new_result, expected, rtol=1e-15, atol=0)
            max_parent_error = max(max_parent_error, float(np.max(np.abs(old_result-expected))))
            max_candidate_error = max(max_candidate_error, float(np.max(np.abs(new_result-expected))))
            # A subsequent exactly collinear vector retains reuse.
            vector[1] = 0
            assert new['_collinear_coefficient'](vector, direction) == 1
            repair_checks += 1

print(dict(random_guard_checks=accepted+rejected, accepted=accepted, rejected=rejected,
           special_checks=special_checks, amplified_residual_repairs=repair_checks,
           max_parent_absolute_error=max_parent_error,
           max_candidate_absolute_error=max_candidate_error,
           oracle='70-digit Decimal central differences of diagonal linear loss',
           scope='synthetic correctness only; no optical workload or timing'))
