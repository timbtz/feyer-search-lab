"""Diagnostic-only long-double host primal, using the candidate component source.

This is a precision investigation, not a new simulator candidate or independent
physics implementation. No package files or global NumPy objects are changed.
"""
from contextlib import ExitStack
import types
from unittest.mock import patch


class ExtendedNumpy:
    def __init__(self):
        import numpy as np
        self.np = np
        self.complex128 = np.clongdouble
        self.float64 = np.longdouble

    def __getattr__(self, name):
        return getattr(self.np, name)


def make_evaluator(arrays, ports, reference):
    import numpy as np
    import differometor.host as host
    import differometor.host_pass as hp
    from differometor.build import LINKING_FUNCTIONS
    from scipy.sparse import csc_matrix
    from scipy.sparse.linalg import splu
    from .gradient_sanity import extended_readout_loss
    from .solver_precision_probe import extended_solve

    if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
        raise RuntimeError('No extended precision on this platform')
    plan = arrays['host_plan']
    data = {name: np.asarray(value) for name, value in arrays.items()
            if name not in ('host_plan', 'component_groups', 'sparse_structure')}
    ext = ExtendedNumpy()
    links = []
    for fn in LINKING_FUNCTIONS:
        if not isinstance(fn, types.FunctionType):
            raise ValueError('Unsupported linking callable for diagnostic')
        namespace = dict(fn.__globals__)
        namespace.update(jnp=np)
        links.append(types.FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__))
    structure = plan.structure
    bases = [np.asarray(getattr(structure, name).base_values(arrays[name+'_matrix']), dtype=np.clongdouble)
             for name in ('carrier', 'signal', 'noise')]

    def factor(pattern, values):
        return splu(csc_matrix((np.asarray(values, dtype=np.complex128), pattern.indices, pattern.indptr),
                              shape=(pattern.size, pattern.size)), permc_spec='COLAMD')

    def solve(products, values, lu, rhs, trans):
        initial = lu.solve(np.asarray(rhs, dtype=np.complex128), trans=trans)
        return extended_solve(products, values, lu, rhs, trans, initial, return_extended=True)[0]

    def evaluate(point):
        parameters = np.array(data['parameters'], dtype=np.clongdouble, copy=True)
        parameters[0, data['optimized_parameter_indices']] = np.asarray(point, dtype=np.longdouble)[data['optimized_value_indices']]
        # Simultaneous linking, matching the original gather then scatter order.
        inputs = parameters[0, data['linked_indices']]
        outputs = [links[int(i)](x) for i, x in zip(data['linking_function_indices'], inputs)]
        parameters[0, data['indices_to_link']] = np.asarray(outputs, dtype=np.clongdouble)
        phases = np.exp(1j * parameters[0, data['qhd_parameter_indices']] * (np.pi/180))
        selection = np.array(data['noise_selection_vectors'], dtype=np.clongdouble, copy=True)
        for index, phase in zip(data['qhd_placing_indices'].reshape(-1,3), phases):
            selection[tuple(index)] *= phase
        with ExitStack() as stack:
            stack.enter_context(patch.object(host, 'np', ext))
            stack.enter_context(patch.object(hp, 'np', ext))
            stack.enter_context(patch.object(hp, '_factor', factor))
            stack.enter_context(patch.object(hp, '_solve', solve))
            carrier, signal, noise, _, _ = hp.host_forward(
                plan, parameters, np.asarray(data['carrier_changing_values'], dtype=np.clongdouble),
                np.asarray(data['signal_changing_values'], dtype=np.clongdouble), *bases, selection)
        if carrier.dtype != np.clongdouble or signal.dtype != np.clongdouble:
            raise RuntimeError('Diagnostic unexpectedly lost extended precision')
        return extended_readout_loss(carrier.T, signal.T, noise.squeeze(), np.asarray(ports), reference)
    return evaluate
