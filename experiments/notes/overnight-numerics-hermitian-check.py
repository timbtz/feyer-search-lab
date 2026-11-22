"""Exact Hermitian guard diagnostics; small synthetic arrays, no timings."""
import ast
from decimal import Decimal, localcontext
from pathlib import Path
import runpy
import subprocess

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'


def load(source):
    names = {'_is_hermitian', '_transpose_index', '_collinear_coefficient', '_Products', '_solve'}
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    ns = dict(np=np, _TRANSPOSES={}, HERMITIAN_TOLERANCE=8*np.finfo(float).eps,
              REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'guard-kernels', 'exec'), ns)
    return ns


class Pattern:
    def __init__(self, mask):
        self.size = mask.shape[0]
        self.cols, self.rows = np.nonzero(mask.T)


old = load(subprocess.check_output(['git', 'show', PARENT+':differometor/host_pass.py'],
                                  cwd=ROOT, text=True))
new = load((ROOT/'differometor/host_pass.py').read_text())
rng = np.random.default_rng(2026112234)
checks = 0
for size in (1, 2, 5, 11):
    for trial in range(15):
        z = rng.normal(size=(size, size))+1j*rng.normal(size=(size, size))
        h = z+z.conj().T
        mask = rng.random(h.shape) < .5
        mask = mask | mask.T
        h = np.where(mask, h, 0)
        for mode in ('exact', 'zero', 'small_asymmetry', 'unpaired', 'nonfinite', 'imaginary_diagonal'):
            n = h.copy()
            layout = mask.copy()
            if mode == 'zero':
                n[:] = 0
            elif mode == 'small_asymmetry':
                n[0, 0] += 1j*np.finfo(float).eps
                layout[0, 0] = True
            elif mode == 'unpaired' and size > 1:
                n[0, 1] = np.finfo(float).tiny
                n[1, 0] = 0
                layout[0, 1], layout[1, 0] = True, False
            elif mode == 'nonfinite':
                n[0, 0] = np.inf
                layout[0, 0] = True
            elif mode == 'imaginary_diagonal':
                n[0, 0] += .5j
                layout[0, 0] = True
            pat = Pattern(layout)
            coeff = n[pat.rows, pat.cols]
            expected = bool(np.all(np.isfinite(n)) and np.array_equal(n, n.conj().T))
            assert new['_is_hermitian'](pat, coeff) == expected, (size, trial, mode)
            # Changed numeric inputs on the identical structural plan.
            assert new['_is_hermitian'](pat, np.zeros_like(coeff))
            checks += 1

# Real source component outputs for physical real loss/squeeze parameters.
helper = runpy.run_path(str(ROOT/'experiments/notes/overnight-numerics-surface-check.py'))
host, _ = helper['load']((ROOT/'differometor/components.py').read_text())
functions = {f.__name__: i for i, f in enumerate(host['HOST_FUNCTIONS'])}
physical_checks = 0
for db in (0., 1., 10., 30.):
    for angle in (-180., -37., 0., 89., 180.):
        inputs = np.array([db, angle, 0., 0., 0., 0., 0.], complex)
        out = host['evaluate_function'](functions['squeezer'], inputs)
        # Component output order is upper diagonal, upper off-diagonal,
        # lower diagonal, lower off-diagonal (not flattened matrix order).
        n = out[[0, 1, 3, 2]].reshape(2, 2)
        pat = Pattern(np.ones((2, 2), bool))
        coeff = n[pat.rows, pat.cols]
        assert old['_is_hermitian'](pat, coeff)
        assert new['_is_hermitian'](pat, coeff)
        physical_checks += 1
for name in ('vacuum_quantum_noise', 'loss_quantum_noise'):
    for loss in (0., 1e-12, .3, 1.):
        inputs = np.array([loss, 0., 0., 0., 0., 0., 0.], complex)
        out = host['evaluate_function'](functions[name], inputs)
        pat = Pattern(np.eye(2, dtype=bool))
        coeff = np.full(2, out[0])
        assert old['_is_hermitian'](pat, coeff)
        assert new['_is_hermitian'](pat, coeff)
        physical_checks += 1

# Analytically solvable example: A=diag(1,tau), N=[[1,epsilon],[0,1]], s=e0.
# cov=A^-1 N A^-H s=e0, but A^-1 N^H A^-H s=(1,epsilon/tau).
# The selection derivative of Re(s^H A^-1 N A^-H s) is (2,epsilon/tau).
tau = 1e-12
epsilon = 4*np.finfo(float).eps
a = np.diag([1., tau]).astype(complex)
n = np.array([[1., epsilon], [0., 1.]], complex)
pat = Pattern(np.ones((2, 2), bool))
av, nv = a[pat.rows, pat.cols], n[pat.rows, pat.cols]
factor = splu(csc_matrix(a))
products = new['_Products'](pat)
source = np.array([1., 0.], complex)
weight = new['_solve'](products, av, factor, source, 'H')
cov = new['_solve'](products, av, factor, products.apply(nv, weight), 'N')
weight_bar = products.apply(nv, np.conj(weight), 'T')
explicit = np.conj(new['_solve'](products, av, factor, np.conj(weight_bar), 'N'))
assert old['_is_hermitian'](pat, nv)
assert not new['_is_hermitian'](pat, nv)
old_gradient = np.real(np.conj(cov)+np.conj(cov))
new_gradient = np.real(np.conj(cov)+explicit)
with localcontext() as ctx:
    ctx.prec = 70
    t, e = Decimal.from_float(tau), Decimal.from_float(float(epsilon))
    step = Decimal('1e-8')
    def energy(y):
        return Decimal(1)+e*y/t+y*y/(t*t)
    independent_fd = (energy(step)-energy(-step))/(2*step)
    np.testing.assert_allclose(new_gradient, [2., float(independent_fd)], rtol=1e-15, atol=0)
assert old_gradient[1] == 0 and new_gradient[1] > 8e-4

# Separate unresolved guard: record the same amplification for collinearity.
vector = np.array([1., epsilon], complex)
assert old['_collinear_coefficient'](vector, source) == 1
assert new['_collinear_coefficient'](vector, source) == 1
print(dict(dense_oracle_guard_checks=checks, physical_noise_component_checks=physical_checks,
           asymmetry=float(epsilon), diagonal_condition_number=1/tau,
           parent_selection_gradient=old_gradient.tolist(),
           candidate_selection_gradient=new_gradient.tolist(),
           independent_70_digit_fd=float(independent_fd),
           deferred_collinearity_error=float(epsilon/tau),
           scope='synthetic numerical evidence only; no optical benchmark or timing'))
