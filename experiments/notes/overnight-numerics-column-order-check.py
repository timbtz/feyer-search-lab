"""Synthetic within-forward column-order reuse checks; no benchmarks or timings."""
import ast
import hashlib
from pathlib import Path
import subprocess
from types import SimpleNamespace
import numpy as np
from scipy.sparse import csc_array, csc_matrix
from scipy.sparse.linalg import splu
from scipy.sparse.linalg._dsolve import _superlu

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'
names = {'_factor', '_ColumnOrdering', '_PermutedFactor', '_Products', '_solve',
         'host_forward', '_split', '_assembly_key', '_noise_amplitude'}

def load(source, extension=True):
    calls = []
    def factor(*args, **kwargs):
        saved = [array.tobytes() for array in args[2:5]]
        result = _superlu.gstrf(*args, **kwargs)
        assert saved == [array.tobytes() for array in args[2:5]]
        calls.append(kwargs['options']['ColPerm'])
        return result
    ns = dict(np=np, hashlib=hashlib, _ASSEMBLY={},
              REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14,
              _superlu_gstrf=lambda: factor if extension else False,
              _construct_csc=csc_array, _scipy=lambda: (splu, csc_matrix),
              _SUPERLU_OPTIONS=dict(DiagPivotThresh=None, ColPerm='COLAMD',
                                    PanelSize=None, Relax=None),
              UNIT_VACUUM=1., H_PLANCK=1., F0=1.)
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<factor kernels>', 'exec'), ns)
    ns['_products'] = ns['_Products']
    return ns, calls

def pattern(matrix, dense=False):
    if dense:
        cols, rows = np.nonzero(np.ones(matrix.shape, bool))
        # np.nonzero's first coordinate is used as the column to obtain CSC order.
        data = matrix[rows, cols]
        csc = csc_matrix((data, (rows, cols)), shape=matrix.shape)
    else:
        csc = csc_matrix(matrix)
    return SimpleNamespace(size=matrix.shape[0], rows=csc.indices,
                           cols=np.repeat(np.arange(matrix.shape[0]), np.diff(csc.indptr)),
                           indices=csc.indices, indptr=csc.indptr), csc.data.copy()

def equal(a, b):
    np.testing.assert_array_equal(a, b)
    assert a.tobytes() == b.tobytes()

class CountSolve:
    def __init__(self, factor):
        self.factor, self.calls = factor, 0
    def solve(self, rhs, trans):
        self.calls += 1
        return self.factor.solve(rhs, trans=trans)

parent_source = subprocess.check_output(['git', 'show', PARENT + ':differometor/host_pass.py'],
                                        cwd=ROOT, text=True)
source = (ROOT / 'differometor/host_pass.py').read_text()
rng = np.random.default_rng(2026112225)
solves = factors = forwards = 0
steps = {}
for extension in (True, False):
    old, _ = load(parent_source, extension)
    new, calls = load(source, extension)
    for size in (7, 19, 43):
        for topology in range(8):
            matrix = rng.normal(size=(size, size)) + 1j*rng.normal(size=(size, size))
            matrix[rng.random((size, size)) > .2] = 0
            matrix += size * np.eye(size)
            pat, initial = pattern(matrix)
            ordering = new['_ColumnOrdering'](pat, new['_factor'](pat, initial))
            for mode in ('zero_offdiagonal', 'complex', 'ill_scaled', 'pivoting'):
                values = initial.copy()
                if mode == 'zero_offdiagonal':
                    values[pat.rows != pat.cols] = 0
                elif mode == 'complex':
                    values *= 1 + .1j * rng.normal(size=values.size)
                elif mode == 'ill_scaled':
                    scales = np.geomspace(1e-9, 1e9, size)
                    values *= scales[pat.rows] / scales[pat.cols]
                else:
                    values[pat.rows == pat.cols] /= size * 3
                f, g = old['_factor'](pat, values), ordering.factor(values)
                factors += 1
                for trans in ('N', 'T', 'H'):
                    for width in (None, 1, 3):
                        shape = (size,) if width is None else (size, width)
                        rhs = rng.normal(size=shape) + 1j*rng.normal(size=shape)
                        saved = rhs.copy()
                        a, b = CountSolve(f), CountSolve(g)
                        expected = old['_solve'](old['_Products'](pat), values, a, rhs, trans)
                        actual = new['_solve'](new['_Products'](pat), values, b, rhs, trans)
                        equal(expected, actual)
                        equal(rhs, saved)
                        assert a.calls == b.calls
                        steps[b.calls - 1] = steps.get(b.calls - 1, 0) + 1
                        solves += 1

    # Nearly singular systems retain all refinement steps and original coordinates.
    for size in (8, 12):
        index = np.arange(size)
        matrix = (1 / (1 + index[:, None] + index[None, :])).astype(np.complex128)
        pat, values = pattern(matrix)
        f = old['_factor'](pat, values)
        ordering = new['_ColumnOrdering'](pat, new['_factor'](pat, values))
        g = ordering.factor(values)
        factors += 1
        for trans in ('N', 'T', 'H'):
            for width in (1, 3):
                rhs = rng.normal(size=(size, width)) + 1j*rng.normal(size=(size, width))
                a, b = CountSolve(f), CountSolve(g)
                equal(old['_solve'](old['_Products'](pat), values, a, rhs, trans),
                      new['_solve'](new['_Products'](pat), values, b, rhs, trans))
                assert a.calls == b.calls
                steps[b.calls-1] = steps.get(b.calls-1, 0) + 1
                solves += 1

    # Exercise the actual forward loop, fresh assembly and factor creation twice.
    # No optical fixture: arbitrary small complex signal/noise systems and selectors.
    for count in (1, 5, 11):
        for detectors in (1, 3):
            for reuse_noise in (False, True):
                size = 13
                matrix = np.eye(size, dtype=np.complex128)*size
                matrix += .1*(rng.normal(size=(size,size))+1j*rng.normal(size=(size,size)))
                pat, base = pattern(matrix, dense=True)
                coeff = np.broadcast_to(base, (count, base.size)).copy()
                coeff *= 1 + .001j*rng.normal(size=coeff.shape)
                coeff[0, pat.rows != pat.cols] = 0
                rhs = rng.normal(size=(count,size))+1j*rng.normal(size=(count,size))
                noise = np.eye(size, dtype=np.complex128)
                noise[1,2], noise[2,1] = .1j,-.1j
                npat, noise_values = pattern(noise)
                ns_count = 1 if reuse_noise else count
                state = dict(signal_values=np.concatenate((coeff,rhs),axis=1),
                             noise_values=np.broadcast_to(noise_values,(ns_count,noise_values.size)).copy(),
                             carrier=np.ones((1,3), dtype=np.complex128))
                selections = rng.normal(size=(detectors,1,size))+1j*rng.normal(size=(detectors,1,size))
                system = SimpleNamespace(pattern=pat, size=size, nnz=base.size,
                                         augmented=True, rhs_rows=np.arange(size))
                plan = SimpleNamespace(_key='synthetic-loop', noise_row_reuse=reuse_noise,
                                       structure=SimpleNamespace(signal=system, noise=SimpleNamespace(pattern=npat)))
                assembled = [0,0]
                for j, ns in enumerate((old,new)):
                    def assemble(*args, j=j):
                        assembled[j] += 1
                        return dict(state)
                    ns['_assemble'] = assemble
                    ns['_selections'] = lambda *args: (None, selections)
                inputs = [np.zeros(1)]*7
                for repeat in range(2):
                    start = len(calls)
                    expected = old['host_forward'](plan,*inputs)
                    actual = new['host_forward'](plan,*inputs)
                    for a,b in zip(expected,actual):
                        equal(a,b)
                    if extension:
                        assert calls[start:] == ['COLAMD']+['NATURAL']*(count-1)
                    # Retained factors used by reverse solve in original coordinates.
                    saved_factors = next(iter(new['_ASSEMBLY'].values()))['signal_factors']
                    for row, factor in enumerate(saved_factors):
                        reference = old['_factor'](pat, coeff[row])
                        for trans in ('N','T','H'):
                            equal(factor.solve(rhs[row],trans=trans), reference.solve(rhs[row],trans=trans))
                    coeff += 1e-4 * base[None, :]
                    state['signal_values'] = np.concatenate((coeff,rhs),axis=1)
                    forwards += 1
                assert assembled == [2,2]

print(dict(factor_pairs=factors, refined_solves_bitwise_equal=solves,
           refinement_steps=steps, forward_calls_bitwise_equal=forwards,
           illustrative_ordering_calls='11 COLAMD -> 1 COLAMD + 10 NATURAL per forward',
           scope='small synthetic correctness and call counts; no optical benchmark/timing'))
