"""Extended-residual diagnostic for the final host solver; never a scored candidate.

Refines the same complex128 assembled systems using platform long-double residuals.
This probes solver rounding, not assembly accuracy or the judges' reference policy.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def extended_solve(products, values, factor, rhs, trans, initial, *, return_extended=False):
    import numpy as np
    rhs = np.asarray(rhs, dtype=np.clongdouble)
    vector = rhs.ndim == 1
    rhs = rhs[:, None] if vector else rhs
    x = np.asarray(initial, dtype=np.clongdouble)
    x = x[:, None] if vector else x
    values = np.asarray(values, dtype=np.clongdouble)
    row, column = (products.rows, products.cols) if trans == 'N' else (products.cols, products.rows)
    weights = np.conj(values) if trans == 'H' else values
    def residual(solution):
        contributions = weights[:, None] * solution[column]
        applied = np.zeros_like(rhs)
        denominator = np.abs(rhs).copy()
        np.add.at(applied, row, contributions)
        np.add.at(denominator, row, np.abs(contributions))
        r = rhs - applied
        ratio = float(np.max(np.abs(r) / np.maximum(denominator, np.finfo(np.longdouble).tiny)))
        return r, ratio
    r, before = residual(x)
    best, best_error = x.copy(), before
    iterations = 0
    for _ in range(6):
        correction = factor.solve(np.asarray(r[:, 0] if vector else r, dtype=np.complex128), trans=trans)
        correction = correction[:, None] if vector else correction
        x = x + np.asarray(correction, dtype=np.clongdouble)
        r, error = residual(x)
        iterations += 1
        if error < best_error:
            best, best_error = x.copy(), error
        if np.max(np.abs(correction)) <= 1e-19 * max(float(np.max(np.abs(x))), 1e-300):
            break
    result = np.asarray(best[:, 0] if vector else best, dtype=np.clongdouble if return_extended else np.complex128)
    return result, {'before_componentwise_residual': before, 'extended_componentwise_residual': best_error,
                    'iterations': iterations, 'transpose': trans}


def main(args):
    import numpy as np
    tree = args.tree.resolve()
    actual = subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != args.sha or subprocess.check_output(['git', '-C', str(tree), 'status', '--porcelain', '--untracked-files=no'], text=True).strip():
        raise ValueError('Exact clean candidate required')
    if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
        raise RuntimeError('Platform has no extra long-double precision')
    sys.path.insert(0, str(tree))
    import differometor.host_pass as hp
    spec = importlib.util.spec_from_file_location('trusted_gencheck', args.harness)
    gencheck = importlib.util.module_from_spec(spec); spec.loader.exec_module(gencheck)
    args.output.mkdir(exist_ok=False)
    records = []
    original = hp._solve
    def diagnostic_solve(products, values, factor, rhs, trans):
        initial = original(products, values, factor, rhs, trans)
        solution, record = extended_solve(products, values, factor, rhs, trans, initial)
        records.append(record)
        return solution
    try:
        hp._solve = diagnostic_solve
        gencheck.run(argparse.Namespace(tree=str(tree), out=str(args.output/'extended.npz'),
                                       cases='dev,uifo_rand1,uifo_rand3,aligo', merge=False))
    finally:
        hp._solve = original
    summary = {'schema': 'feyer-extended-residual-probe-v1', 'sha': actual,
               'scope': 'Same candidate assembly; extended-precision residual refinement of linear solves only. Not an independent exact physics oracle.',
               'double_mantissa_bits': np.finfo(np.float64).nmant,
               'extended_mantissa_bits': np.finfo(np.longdouble).nmant,
               'solve_count': len(records), 'solves': records}
    (args.output/'residuals.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print('Completed', len(records), 'extended residual probes', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', required=True, type=Path)
    p.add_argument('--sha', required=True)
    p.add_argument('--harness', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    main(p.parse_args())
