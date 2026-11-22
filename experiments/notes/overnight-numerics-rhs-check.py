"""Small synthetic RHS materialization checks; no optical workloads or timings."""
import ast
import hashlib
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'
NAMES = {'_Products', '_solve', '_split', '_assembly_key', '_noise_amplitude',
         'host_forward', 'host_backward', '_sum_to', '_cast_bar', '_expand_backward',
         '_is_hermitian', '_transpose_index', '_collinear_coefficient'}


def load(source):
    ns = dict(np=np, hashlib=hashlib, _ASSEMBLY={}, _TRANSPOSES={},
              REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14,
              HERMITIAN_TOLERANCE=8*np.finfo(float).eps,
              UNIT_VACUUM=1., H_PLANCK=1., F0=1., _NOISE_SCALE=.5)
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in NAMES]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'rhs-kernels', 'exec'), ns)
    ns['_products'] = ns['_Products']
    records = dict(factors=0, factor_solves=0, solves=[], splits=0, rhs_bytes=0)

    class Factor:
        def __init__(self, pattern, values):
            records['factors'] += 1
            self.factor = splu(csc_matrix((values, pattern.rows, pattern.indptr),
                                          shape=(pattern.size, pattern.size)))
        def solve(self, rhs, trans):
            records['factor_solves'] += 1
            before = rhs.tobytes()
            result = self.factor.solve(rhs, trans=trans)
            assert before == rhs.tobytes(), 'SuperLU mutated its RHS'
            return result

    solve, split = ns['_solve'], ns['_split']
    def traced_solve(products, values, factor, rhs, trans):
        snapshot = np.array(rhs, copy=True)
        result = solve(products, values, factor, rhs, trans)
        equal(snapshot, rhs)
        assert not np.shares_memory(result, rhs)
        records['solves'].append((trans, snapshot, result.copy()))
        return result
    def traced_split(system, values):
        records['splits'] += 1
        result = split(system, values)
        records['rhs_bytes'] += result[1].nbytes
        return result
    ns.update(_factor=Factor, _solve=traced_solve, _split=traced_split)
    return ns, records


class Pattern:
    def __init__(self, matrix):
        self.size = matrix.shape[0]
        self.cols = np.repeat(np.arange(self.size), self.size)
        self.rows = np.tile(np.arange(self.size), self.size)
        self.indptr = np.arange(self.size + 1)*self.size


def equal(a, b):
    np.testing.assert_array_equal(a, b)
    assert a.tobytes() == b.tobytes(), 'finite signed-zero/rounding difference'


def values(matrix, pattern):
    return matrix[pattern.rows, pattern.cols]


parent = subprocess.check_output(['git', 'show', PARENT+':differometor/host_pass.py'],
                                 cwd=ROOT, text=True)
old, old_records = load(parent)
new, new_records = load((ROOT/'differometor/host_pass.py').read_text())
rng = np.random.default_rng(2026112233)
forwards = backwards = 0

# The component pullback stand-in keeps all base cotangents and returns the
# correct parameter-row shape. It isolates RHS/solve orchestration; it is not
# evidence for component differentiation or a complete optical simulation.
def component_backward(rows, bars):
    return np.zeros_like(rows), bars.sum(axis=0)

for count in (1, 3, 9):
    for detectors in (1, 2, 4):
        for augmented in (False, True):
            for ill_scaled in (False, True):
                size, carrier_size = 7, 2
                a = np.eye(size, dtype=complex)*4
                a += .03*(rng.normal(size=a.shape)+1j*rng.normal(size=a.shape))
                if ill_scaled:
                    scale = np.geomspace(1e-5, 1e5, size)
                    a *= scale[:, None]/scale[None, :]
                pat = Pattern(a)
                coeff = np.tile(values(a, pat), (count, 1))
                rhs_rows = np.array([6, 0, 3]) if augmented else np.zeros(0, dtype=int)
                coeff[0, pat.rows != pat.cols] = 0  # Retain explicit structural zeros.
                rhs_values = rng.normal(size=(count, rhs_rows.size)).astype(complex)
                # Alternate zero and nonzero sources: reused buffers must be cleared.
                rhs_values[::2] = 0
                signal_values = np.concatenate((coeff, rhs_values), axis=1)
                n = np.eye(size, dtype=complex)
                npat = Pattern(n)
                cm = np.eye(carrier_size, dtype=complex)*2
                cpat = Pattern(cm)
                cv = values(cm, cpat)[None, :]
                noise_reuse = count != 3
                nc = 1 if noise_reuse else count
                system = SimpleNamespace(pattern=pat, size=size, nnz=coeff.shape[1],
                                         augmented=augmented, rhs_rows=rhs_rows)
                carrier_system = SimpleNamespace(pattern=cpat, size=carrier_size,
                                                 nnz=cv.shape[1], augmented=False)
                structure = SimpleNamespace(signal=system, carrier=carrier_system,
                    noise=SimpleNamespace(pattern=npat), signal_conjugate=np.zeros(signal_values.shape[1], bool),
                    signal_placing_positions=np.zeros(0, dtype=int))
                plan = SimpleNamespace(_key='synthetic', structure=structure, noise_row_reuse=noise_reuse,
                    signal_carrier_indices=np.zeros(0, dtype=int), signal_changing=np.array([0]),
                    carrier_changing=np.array([0]), signal=SimpleNamespace(backward=component_backward),
                    noise=SimpleNamespace(backward=component_backward),
                    carrier=SimpleNamespace(backward=component_backward))
                selections = rng.normal(size=(detectors, 1, size))+1j*rng.normal(size=(detectors, 1, size))
                state = dict(signal_values=signal_values, noise_values=np.tile(values(n, npat), (nc, 1)),
                    carrier=np.ones((1, carrier_size), complex), carrier_coefficients=cv,
                    carrier_values=cv, raw_signal=signal_values.copy(), carrier_rows=np.ones((1, 3), complex),
                    signal_rows=np.ones((count, 3), complex), noise_rows=np.ones((nc, 3), complex))
                assemblies = [0, 0]
                for index, ns in enumerate((old, new)):
                    def assemble(*args, ns=ns, index=index):
                        assemblies[index] += 1
                        result = dict(state)
                        result['carrier_factors'] = [ns['_factor'](cpat, cv[0])]
                        return result
                    ns['_assemble'] = assemble
                    ns['_selections'] = lambda *args: (selections, selections)
                inputs = (np.ones((1, 3), complex), np.ones((1, 1)), np.ones((1, count)),
                          cv[0], signal_values[0], state['noise_values'][0], selections)
                for repeat in range(2):
                    outputs = []
                    for ns in (old, new):
                        outputs.append(ns['host_forward'](plan, *inputs))
                    for a, b in zip(*outputs):
                        equal(a, b)
                    forwards += 1
                    carrier, signal, noise, covariances, weights = outputs[0]
                    bars = (rng.normal(size=carrier.shape).astype(complex),
                            rng.normal(size=signal.shape).astype(complex), rng.normal(size=noise.shape))
                    expected = old['host_backward'](plan, *inputs, *outputs[0], *bars)
                    actual = new['host_backward'](plan, *inputs, *outputs[1], *bars)
                    for a, b in zip(expected, actual):
                        equal(a, b)
                    backwards += 1
                    # New evaluation on the same topology, including formerly zero RHS entries.
                    signal_values[:, system.nnz:] += .01
                    signal_values[:, :system.nnz] *= 1.001
                assert assemblies == [2, 2], assemblies

assert old_records['factors'] == new_records['factors']
assert old_records['factor_solves'] == new_records['factor_solves']
assert len(old_records['solves']) == len(new_records['solves'])
for (ta, ra, xa), (tb, rb, xb) in zip(old_records['solves'], new_records['solves']):
    assert ta == tb
    equal(ra, rb)
    equal(xa, xb)
assert new_records['splits'] == 0
print(dict(forward_pairs=forwards, backward_pairs=backwards,
           identical_refined_solves=len(new_records['solves']),
           fresh_factorizations_each_version=new_records['factors'],
           identical_factor_solve_counts=new_records['factor_solves'],
           parent_discarded_or_repacked_dense_rhs_arrays=old_records['splits'],
           parent_dense_rhs_bytes=old_records['rhs_bytes'],
           candidate_dense_rhs_arrays=new_records['splits'],
           scope='small synthetic equality/operation counts; no optical benchmark or timing'))
