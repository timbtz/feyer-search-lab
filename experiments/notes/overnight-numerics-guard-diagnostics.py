"""Supervisor-only adjoint guard capture; no workload or file writes.

Use a separate serial diagnostic driver, never official timing runs. Pass exact
reference host_pass.py source (e.g. candidate34 against candidate35). Returned
callback results are unchanged. Context captures bounded changed decisions,
coefficient vectors when matching forward state is available, forward weights,
reference reused solutions, and actual signal-adjoint solutions. It does not
compute a reference gradient or certify either solution's accuracy.

    with collect_guard_diagnostics(reference_source, max_records=8) as report:
        ... supervisor runs and synchronizes one requested optical case ...
    ... supervisor saves metadata and NumPy arrays separately ...

Row indices identify flattened signal sweep rows, not assumed frequency values.
All callback arguments remain visible to the original callback; no benchmark
identification or launch policy changes. Synchronize before leaving the context.
Nested/concurrent diagnostic contexts on the same module are unsupported.
"""
import ast
from contextlib import contextmanager
from functools import wraps
import hashlib
import inspect
from threading import Lock, local

import numpy as np


@contextmanager
def collect_guard_diagnostics(reference_source, module=None, max_records=8):
    if module is None:
        from differometor import host_pass as module
    if max_records < 1:
        raise ValueError('max_records must be positive')
    nodes = [n for n in ast.parse(reference_source).body
             if isinstance(n, ast.FunctionDef) and n.name == '_collinear_coefficient']
    if len(nodes) != 1:
        raise ValueError('reference source must contain one collinearity guard')
    namespace = dict(np=np, HERMITIAN_TOLERANCE=8*np.finfo(float).eps)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'reference-guard', 'exec'), namespace)
    reference = namespace['_collinear_coefficient']
    original_guard, original_backward, original_solve = (
        module._collinear_coefficient, module.host_backward, module._solve)
    signature = inspect.signature(original_backward)
    report = dict(scope='diagnostic only; captures and extra guard calls; not timing evidence',
                  reference_source_sha256=hashlib.sha256(reference_source.encode()).hexdigest(),
                  callbacks=[], records=[])
    active, lock = local(), Lock()

    @wraps(original_backward)
    def backward(*args, **kwargs):
        inputs = signature.bind(*args, **kwargs).arguments
        assembly_inputs = tuple(np.asarray(inputs[name]) for name in (
            'parameters', 'carrier_values', 'signal_values', 'carrier_base', 'signal_base', 'noise_base'))
        state = module._ASSEMBLY.get(module._assembly_key(inputs['plan'], *assembly_inputs))
        weights = np.asarray(inputs['weights'])
        counts = dict(guard_calls=0, accepted=0, reference_accepted=0,
                      changed_decisions=0, explicit_signal_rows=0,
                      signal_rows=int(weights.shape[0]), detectors=int(weights.shape[1]),
                      matching_assembly_available=state is not None)
        with lock:
            counts['ordinal'] = len(report['callbacks'])
            report['callbacks'].append(counts)
        previous = getattr(active, 'context', None)
        context = dict(counts=counts, row=0, detector=0, pending=[],
                       weights=weights, state=state, plan=inputs['plan'], awaiting_solve=False)
        active.context = context
        try:
            return original_backward(*args, **kwargs)
        finally:
            active.context = previous

    @wraps(original_guard)
    def guard(vector, direction):
        actual = original_guard(vector, direction)
        ctx = getattr(active, 'context', None)
        if ctx is None:
            return actual
        expected = reference(vector, direction)
        counts, row, detector = ctx['counts'], ctx['row'], ctx['detector']
        counts['guard_calls'] += 1
        counts['accepted'] += actual is not None
        counts['reference_accepted'] += expected is not None
        changed = ((actual is None) != (expected is None)
                   or (actual is not None and expected is not None and actual != expected))
        counts['changed_decisions'] += changed
        if changed:
            with lock:
                if len(report['records']) < max_records:
                    record = dict(callback=counts['ordinal'], signal_row=row, detector=detector,
                                  vector=np.array(vector, copy=True), direction=np.array(direction, copy=True),
                                  actual_alpha=actual, reference_alpha=expected,
                                  weight=np.array(ctx['weights'][row, detector], copy=True),
                                  actual_solution=None, reference_reused_solution=None,
                                  coefficients=None, rows=None, cols=None)
                    if expected is not None:
                        record['reference_reused_solution'] = expected*np.conj(record['weight'])
                    if ctx['state'] is not None:
                        system = ctx['plan'].structure.signal
                        record['coefficients'] = ctx['state']['signal_values'][row, :system.nnz].copy()
                        record['rows'] = system.pattern.rows.copy()
                        record['cols'] = system.pattern.cols.copy()
                    report['records'].append(record)
                    ctx['pending'].append(record)
        if actual is not None:
            solution = actual*np.conj(ctx['weights'][row, detector])
            for record in ctx['pending']:
                record['actual_solution'] = solution.copy()
            ctx['pending'] = []
            ctx['row'], ctx['detector'] = row+1, 0
        elif detector+1 == counts['detectors']:
            counts['explicit_signal_rows'] += 1
            ctx['awaiting_solve'] = True
            ctx['row'], ctx['detector'] = row+1, 0
        else:
            ctx['detector'] += 1
        return actual

    @wraps(original_solve)
    def solve(products, values, factor, rhs, trans):
        actual = original_solve(products, values, factor, rhs, trans)
        ctx = getattr(active, 'context', None)
        if ctx is not None and ctx['awaiting_solve'] and trans == 'T':
            for record in ctx['pending']:
                record['actual_solution'] = np.array(actual, copy=True)
                # Also covers backward without matching cached forward assembly.
                record['coefficients'] = np.array(values, copy=True)
                record['rows'], record['cols'] = products.rows.copy(), products.cols.copy()
            ctx['pending'] = []
            ctx['awaiting_solve'] = False
        return actual

    try:
        module.host_backward, module._collinear_coefficient, module._solve = backward, guard, solve
        yield report
    finally:
        module.host_backward, module._collinear_coefficient, module._solve = (
            original_backward, original_guard, original_solve)
