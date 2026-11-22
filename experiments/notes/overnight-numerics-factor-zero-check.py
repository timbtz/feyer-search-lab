"""Exact-zero factor-input compaction: small synthetic audit, no timings."""
from pathlib import Path
from types import SimpleNamespace
import json
import ast
import inspect
from decimal import Decimal, localcontext
import runpy
import subprocess
import numpy as np
from scipy.sparse import csc_matrix

ROOT = Path(__file__).resolve().parents[2]
helper = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-panel-check.py'))
load, bits, decimal_solve = (helper[k] for k in ('load', 'bits', 'decimal_solve'))
parent = subprocess.check_output(['git', 'show', helper['PARENT'] + ':differometor/host_pass.py'], cwd=ROOT, text=True)
source = (ROOT / 'differometor/host_pass.py').read_text()
old, new, fallback = load(parent), load(source), load(source, fallback=True)
rng = np.random.default_rng(2026112241)
report = dict(matrices=0, solves=0, original_entries=0, factored_entries=0,
              original_lu_entries=0, compact_lu_entries=0, permutations_changed=0,
              bit_differences=0, fallback_differences=0, correction_counts_changed=0,
              agreement_failures=[], max_relative_difference=0., decimal=[], zero_gradients=[])


def pattern_for(a, structural):
    r, c = np.nonzero(structural)
    m = csc_matrix((a[r, c], (r, c)), shape=a.shape)
    p = SimpleNamespace(size=a.shape[0], rows=m.indices, indices=m.indices,
        cols=np.repeat(np.arange(a.shape[0]), np.diff(m.indptr)), indptr=m.indptr)
    return p, m.data.copy()


def decimal_loss(matrix, rhs, cot):
    # Use the independent real-block elimination helper, but retain its Decimal
    # solution until after the scalar loss and finite difference are evaluated.
    # Converting x to binary64 before differencing loses small changes when
    # similarity scaling gives the solution a large dynamic range.
    tree = ast.parse(inspect.getsource(decimal_solve))
    function = tree.body[0]
    block = function.body[-1]
    assert isinstance(block, ast.With) and isinstance(block.body[-1], ast.Return)
    block.body[-1].value = ast.Name(id='result', ctx=ast.Load())
    ast.fix_missing_locations(tree)
    ns = dict(np=np, Decimal=Decimal, localcontext=localcontext)
    exec(compile(tree, 'decimal-unrounded-solution', 'exec'), ns)
    solution = ns['decimal_solve'](matrix, rhs, 100)
    n = len(rhs)
    with localcontext() as ctx:
        ctx.prec = 100
        return sum(Decimal.from_float(float(cot[k].real))*solution[k]
                   - Decimal.from_float(float(cot[k].imag))*solution[n+k]
                   for k in range(n))


for n in (2, 3, 7, 13, 23):
    for kind in ('ordinary', 'scaled', 'triangular', 'no_zeros'):
        for draw in range(3):
            a = (rng.normal(size=(n,n)) + 1j*rng.normal(size=(n,n))) * (rng.random((n,n)) < .12)
            if kind == 'triangular':
                a = np.triu(a) * .02
            a += np.diag(2 + np.sum(np.abs(a), axis=1))
            if kind == 'scaled':
                scale = np.geomspace(1e-5, 1e5, n)
                a *= scale[:, None] / scale[None, :]
            structural = a != 0 if kind == 'no_zeros' else (rng.random((n,n)) < .6) | (a != 0)
            p, data = pattern_for(a, structural)
            before = (data.tobytes(), p.indices.tobytes(), p.indptr.tobytes())
            factors = [ns['_factor'](p, data) for ns in (old, new, fallback)]
            assert before == (data.tobytes(), p.indices.tobytes(), p.indptr.tobytes())
            report['matrices'] += 1
            report['original_entries'] += data.size
            report['factored_entries'] += int(np.count_nonzero(data))
            report['original_lu_entries'] += factors[0].L.nnz + factors[0].U.nnz
            report['compact_lu_entries'] += factors[1].L.nnz + factors[1].U.nnz
            report['permutations_changed'] += not bits(factors[0].perm_c, factors[1].perm_c)
            products = old['_Products'](p)
            for trans in ('N', 'T', 'H'):
                op = a if trans == 'N' else a.T if trans == 'T' else a.conj().T
                for width in (0, 1, 3):
                    shape = (n,) if width == 0 else (n,width)
                    rhs = rng.normal(size=shape) + 1j*rng.normal(size=shape)
                    before_rhs = rhs.tobytes()
                    counted = [helper['CountingFactor'](f) for f in factors]
                    out = [ns['_solve'](products, data, f, rhs, trans) for ns,f in zip((old,new,fallback),counted)]
                    assert rhs.tobytes() == before_rhs
                    assert all(np.all(np.isfinite(x)) for x in out)
                    report['solves'] += 1
                    report['bit_differences'] += not bits(out[0], out[1])
                    report['fallback_differences'] += not bits(out[1], out[2])
                    report['correction_counts_changed'] += counted[0].calls != counted[1].calls
                    scale = np.max(np.abs(out[0]))
                    relative = float(np.max(np.abs(out[0]-out[1]))/scale)
                    report['max_relative_difference'] = max(report['max_relative_difference'], relative)
                    if not np.allclose(out[0], out[1], rtol=1e-12, atol=1e-14*scale):
                        report['agreement_failures'].append([n,kind,draw,trans,width,relative])
                    assert bits(out[1], out[2]), 'direct and public fallback disagree'
                    if kind == 'no_zeros':
                        assert bits(out[0], out[1]), 'zero-free path changed arithmetic'
                    if n in (7,13) and kind == 'scaled' and width == 0:
                        ref = decimal_solve(op, rhs, 80)
                        assert bits(ref, decimal_solve(op, rhs, 120))
                        rs = np.max(np.abs(ref))
                        report['decimal'].append(dict(case=[n,kind,draw,trans],
                            parent_relative_error=float(np.max(np.abs(out[0]-ref))/rs),
                            candidate_relative_error=float(np.max(np.abs(out[1]-ref))/rs)))
            # Zero-coefficient derivatives must remain: compare the same original
            # full-pattern -r_i*x_j contraction with an independent Decimal solve.
            zeros = np.flatnonzero(data == 0)
            if zeros.size and n <= 13:
                rhs = rng.normal(size=n) + 1j*rng.normal(size=n)
                cot = rng.normal(size=n) + 1j*rng.normal(size=n)
                x = new['_solve'](products, data, factors[1], rhs, 'N')
                adj = new['_solve'](products, data, factors[1], cot, 'T')
                x_ref, adj_ref = decimal_solve(a,rhs,100), decimal_solve(a.T,cot,100)
                bars = -adj[p.rows] * x[p.cols]
                reference_bars = -adj_ref[p.rows] * x_ref[p.cols]
                selected = zeros[:3]
                for k in selected:
                    row,col = int(p.rows[k]), int(p.cols[k])
                    # Real coefficient perturbation: d Re(cot dot x)/dt = Re(bar).
                    # High-precision solves isolate finite differences from SuperLU.
                    h = 1e-5 * max(1.,abs(a[row,row]))
                    plus, minus = a.copy(), a.copy()
                    plus[row,col] += h
                    minus[row,col] -= h
                    fd = np.real(cot @ (decimal_solve(plus,rhs,100)-decimal_solve(minus,rhs,100))) / (2*h)
                    denom = max(abs(reference_bars[k]), np.finfo(float).tiny)
                    precise_fd = []
                    for power in (50, 70):
                        step = 2.**-power
                        plus, minus = a.copy(), a.copy()
                        plus[row,col] += step
                        minus[row,col] -= step
                        with localcontext() as ctx:
                            ctx.prec = 100
                            precise_fd.append(float((decimal_loss(plus,rhs,cot)-decimal_loss(minus,rhs,cot))
                                                    / Decimal.from_float(2*step)))
                    np.testing.assert_allclose(precise_fd[-1],reference_bars[k].real,
                                               rtol=1e-12,atol=1e-14*denom)
                    report['zero_gradients'].append(dict(case=[n,kind,draw,row,col],
                        candidate=[float(bars[k].real),float(bars[k].imag)],
                        reference=[float(reference_bars[k].real),float(reference_bars[k].imag)],
                        relative_error=float(abs(bars[k]-reference_bars[k])/denom),
                        rounded_solution_finite_difference=float(fd),
                        decimal_loss_finite_differences=precise_fd))
                # The next evaluation has a newly nonzero coefficient in the same
                # supplied pattern; ensure its fresh factor solves the changed matrix.
                changed = data.copy(); changed[zeros[0]] = .012 + .004j
                f = new['_factor'](p, changed)
                xx = new['_solve'](products, changed, f, rhs, 'N')
                aa = csc_matrix((changed,p.indices,p.indptr),shape=a.shape).toarray()
                ref = decimal_solve(aa,rhs,100)
                np.testing.assert_allclose(xx,ref,rtol=1e-10,atol=1e-12*np.max(np.abs(ref)))

# Inspect actual gstrf arguments without asking SuperLU to factor NaN/Inf.
# Tiny nonzeros and nonfinites must survive; signed zero may be omitted.
captures=[]
ns=load(source)
ns['_GSTRF']=lambda *args, **kwargs: captures.append(args)
p=SimpleNamespace(size=3,indices=np.array([0,1,2,0,1,2,0,1,2]),indptr=np.array([0,3,6,9]))
v=np.array([1,0,complex(-0.,-0.),1e-300,np.nan,0,np.inf,2,3],complex)
ns['_factor'](p,v)
a=captures[0]
assert a[1]==6
np.testing.assert_array_equal(a[2], v[v!=0])
np.testing.assert_array_equal(a[4], [0,1,3,6])
assert v[3] != 0 and np.isnan(a[2][2])
report['nonfinite_tiny_entries_preserved']=True
# Empty column and all-zero matrices remain singular on both paths.
for v in (np.zeros(9,complex),np.array([1,0,0,0,0,0,0,0,1],complex)):
    for ns in (old,new,fallback):
        try:
            ns['_factor'](p,v)
        except RuntimeError:
            pass
        else:
            raise AssertionError('singular matrix unexpectedly factored')
report['singular_checks']=6
report['agreement_criterion']=dict(rtol=1e-12,atol_parent_max_scale=1e-14)
report['agreement_passed']=not report['agreement_failures']
(ROOT/'experiments/notes/overnight-numerics-factor-zero-result.json').write_text(json.dumps(report,indent=2)+'\n')
summary=dict(report)
summary['decimal']=dict(cases=len(report['decimal']),
    parent_worst=max(r['parent_relative_error'] for r in report['decimal']),
    candidate_worst=max(r['candidate_relative_error'] for r in report['decimal']))
summary['zero_gradients']=dict(cases=len(report['zero_gradients']),
    worst_relative_error=max(r['relative_error'] for r in report['zero_gradients']),
    worst_decimal_fd_relative_error=max(abs(r['decimal_loss_finite_differences'][-1]-r['reference'][0]) / max(abs(complex(*r['reference'])),1e-300) for r in report['zero_gradients']))
print(json.dumps(summary,indent=2))
