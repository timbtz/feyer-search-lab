"""Independent Decimal comparison on small ill-conditioned block systems."""
import importlib.util
import json
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    path = ROOT / 'experiments/notes' / ('overnight-numerics-' + name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    check = module('root-rows-check')
    decimal = module('rhs-refinement-inspect').decimal_solve
    source = (ROOT / 'differometor/host_pass.py').read_text()
    parent = subprocess.check_output(['git', 'show', check.PARENT + ':differometor/host_pass.py'], cwd=ROOT, text=True)
    old, new = check.load(parent), check.load(source)
    rng = np.random.default_rng(20261122531)
    records = []
    for sample in range(24):
        a = np.zeros((5, 5), complex)
        a[0, 0] = 2. + (.1j if sample % 2 else 0)
        block = rng.normal(size=(4, 4)).astype(complex)
        if sample % 2:
            block += .1j * rng.normal(size=(4, 4))
        block[3] = block[0] + block[1] + 10. ** (-5 - sample % 6) * block[3]
        a[1:, 1:] = block
        a[1:, 0] = rng.normal(size=4) + (.1j if sample % 2 else 0)
        a *= np.geomspace(1e-3, 1e3, 5)[:, None]
        a *= np.geomspace(1e3, 1e-3, 5)[None, :]
        cols, rows = np.nonzero(a.T)
        pattern = new['SparsePattern'](rows, cols, 5)
        values = a[rows, cols]
        factors = [ns['_factor'](pattern, values) for ns in (old, new)]
        for trans in ('N', 'T', 'H'):
            op = a if trans == 'N' else a.T if trans == 'T' else a.conj().T
            rhs = op @ (rng.normal(size=5) + .1j * rng.normal(size=5))
            real_block = np.block([[op.real, -op.imag], [op.imag, op.real]])
            right = np.r_[rhs.real, rhs.imag]
            ref80 = decimal(real_block, right)
            ref110 = decimal(real_block, right, 110)
            np.testing.assert_array_equal(ref80, ref110)
            ref = ref80[:5] + 1j * ref80[5:]
            scale = max(float(np.max(np.abs(ref))), 1e-300)
            solutions = [ns['_solve'](ns['_Products'](pattern), values, factor, rhs, trans)
                         for ns, factor in zip((old, new), factors)]
            assert all(np.all(np.isfinite(x)) for x in solutions)
            errors = [float(np.max(np.abs(x - ref))) / scale for x in solutions]
            residuals = [float(np.max(np.abs(op @ x - rhs)) /
                               (np.linalg.norm(op, np.inf) * np.max(np.abs(x)) + np.max(np.abs(rhs))))
                         for x in solutions]
            records.append(dict(sample=sample, trans=trans, parent_scaled_error=errors[0],
                                candidate_scaled_error=errors[1], double_residuals=residuals,
                                parent_candidate_scaled_difference=float(np.max(np.abs(solutions[0]-solutions[1]))) / scale))
    print(json.dumps(dict(parent=check.PARENT, systems=24, solves=len(records),
                         improved=sum(r['candidate_scaled_error'] < r['parent_scaled_error'] for r in records),
                         worsened=sum(r['candidate_scaled_error'] > r['parent_scaled_error'] for r in records),
                         unchanged=sum(r['candidate_scaled_error'] == r['parent_scaled_error'] for r in records),
                         worst_parent=max(records, key=lambda r: r['parent_scaled_error']),
                         worst_candidate=max(records, key=lambda r: r['candidate_scaled_error']), records=records,
                         scope='Small real/complex ill-conditioned systems; independent real-block Decimal80/110 reference, no timing'), indent=2))


if __name__ == '__main__':
    main()
