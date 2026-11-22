"""Supervisor-only diagnostic context; no workload, benchmark or file writes.

Run on candidate28 in a separate diagnostic driver, never in official timings.
Pass the exact admitted parent's host_pass.py text as reference_source. This
compares products and refined solves at the SAME supplied coefficients and RHS,
using the same SuperLU factor. Actual callback results are returned unchanged.
Extra solves, copies and comparisons are substantial diagnostic overhead.

    with collect_product_diagnostics(reference_source, max_records=8) as report:
        ... run and synchronize one requested optical case ...
    ... coordinator saves report metadata and its NumPy arrays ...

The report retains the largest discrepancies, including coefficient coordinates,
RHS, both solutions and every factor-solve RHS/result (initial and corrections).
Each solve has an ordinal; products record the enclosing ordinal, or None for
products outside _solve. Captures contain no fixture-specific logic. Use a fresh
context for each case so small-case failures cannot be displaced by another case.
Run serially under fixed resource policy; simultaneous contexts are unsupported.
"""
import ast
from contextlib import contextmanager
from functools import wraps
from threading import Lock, local
from types import SimpleNamespace

import numpy as np


def _reference_kernels(source, module):
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef))
             and n.name in ('_Products', '_solve')]
    namespace = dict(np=np, REFINEMENT_STEPS=module.REFINEMENT_STEPS,
                     REFINEMENT_TOLERANCE=module.REFINEMENT_TOLERANCE)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'reference-kernels', 'exec'), namespace)
    return namespace['_Products'], namespace['_solve']


def _difference(actual, reference):
    if np.array_equal(actual, reference, equal_nan=True):
        return 0.0
    if not (np.all(np.isfinite(actual)) and np.all(np.isfinite(reference))):
        return float('inf')
    return float(np.max(np.abs(actual-reference), initial=0)
                 / max(float(np.max(np.abs(reference), initial=0)), np.finfo(float).tiny))


class _FactorTrace:
    def __init__(self, factor):
        self.factor = factor
        self.calls = []

    def solve(self, rhs, trans):
        result = self.factor.solve(rhs, trans=trans)
        self.calls.append(dict(rhs=np.array(rhs, copy=True), result=np.array(result, copy=True)))
        return result


@contextmanager
def collect_product_diagnostics(reference_source, module=None, max_records=8):
    if module is None:
        from differometor import host_pass as module
    if max_records < 1:
        raise ValueError('max_records must be positive')
    reference_products, reference_solve = _reference_kernels(reference_source, module)
    original_apply, original_solve = module._Products.apply, module._solve
    report = dict(scope='diagnostic only; extra computations; not timing evidence',
                  products=0, solves=0, unequal_products=0, unequal_solves=0,
                  changed_refinement_counts=0, products_top=[], solves_top=[])
    cache, lock, active = {}, Lock(), local()

    def get_reference(products):
        key = (products.size, products.rows.tobytes(), products.cols.tobytes())
        with lock:
            if key not in cache:
                pattern = SimpleNamespace(size=products.size, rows=products.rows, cols=products.cols)
                cache[key] = reference_products(pattern)
            return cache[key]

    def retain(kind, score, make_record):
        with lock:
            top = report[kind + '_top']
            if score > 0 and (len(top) < max_records or score > top[-1]['relative_difference']):
                record = make_record()
                record['relative_difference'] = score
                top.append(record)
                top.sort(key=lambda r: r['relative_difference'], reverse=True)
                del top[max_records:]

    def coordinates(products, values, trans):
        return dict(size=products.size, rows=products.rows.copy(), cols=products.cols.copy(),
                    values=np.array(values, copy=True), trans=trans)

    @wraps(original_apply)
    def apply(products, values, x, trans='N'):
        actual = original_apply(products, values, x, trans)
        reference = get_reference(products).apply(values, x, trans)
        score = _difference(actual, reference)
        with lock:
            report['products'] += 1
            ordinal = report['products']
            report['unequal_products'] += score > 0
        retain('products', score, lambda: dict(coordinates(products, values, trans),
               ordinal=ordinal, solve_ordinal=getattr(active, 'solve', None),
               x=np.array(x, copy=True), candidate=np.array(actual, copy=True), reference=reference.copy()))
        return actual

    @wraps(original_solve)
    def solve(products, values, factor, rhs, trans):
        with lock:
            report['solves'] += 1
            ordinal = report['solves']
        previous = getattr(active, 'solve', None)
        candidate_factor, reference_factor = _FactorTrace(factor), _FactorTrace(factor)
        active.solve = ordinal
        try:
            actual = original_solve(products, values, candidate_factor, rhs, trans)
        finally:
            active.solve = previous
        reference = reference_solve(get_reference(products), values, reference_factor, rhs, trans)
        score = _difference(actual, reference)
        with lock:
            report['unequal_solves'] += score > 0
            report['changed_refinement_counts'] += len(candidate_factor.calls) != len(reference_factor.calls)
        retain('solves', score, lambda: dict(coordinates(products, values, trans), ordinal=ordinal,
               rhs=np.array(rhs, copy=True), candidate=np.array(actual, copy=True), reference=reference.copy(),
               candidate_factor_calls=candidate_factor.calls, reference_factor_calls=reference_factor.calls))
        return actual

    try:
        module._Products.apply, module._solve = apply, solve
        yield report
    finally:
        module._Products.apply, module._solve = original_apply, original_solve
