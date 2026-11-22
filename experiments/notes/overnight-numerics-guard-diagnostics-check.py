"""Small synthetic test of supervisor capture plumbing; no optical workloads."""
import ast
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

root = Path(__file__).resolve().parents[2]
source = (root/'differometor/host_pass.py').read_text()
nodes = [n for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
         and n.name in ('_collinear_coefficient', '_Products', '_solve')]
ns = dict(np=np, REFINEMENT_STEPS=3, REFINEMENT_TOLERANCE=1e-14)
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual-kernels', 'exec'), ns)
module = SimpleNamespace(**ns)
module._ASSEMBLY = {}
module._assembly_key = lambda *args: 'key'
pattern = SimpleNamespace(size=2, rows=np.array([0,1]), cols=np.array([0,1]))
system = SimpleNamespace(nnz=2, pattern=pattern)
plan = SimpleNamespace(structure=SimpleNamespace(signal=system))
values = np.array([1, 1e-12], complex)
products = module._Products(pattern)
factor = splu(csc_matrix(np.diag(values)))
weights = np.tile(np.diag(1/values)[None, :, :], (3,1,1))
directions = np.eye(2, dtype=complex)
epsilon = 4*np.finfo(float).eps
vectors = np.array([[1,epsilon], [1,0], [0,1]], complex)

# Mirrors the production detector-loop/control flow; actual kernels do all
# scalar decisions and refined solves. Tests wrapper row tracking and captures.
def backward(plan, parameters, carrier_values, signal_values, carrier_base, signal_base, noise_base,
             selection_vectors, carrier, signal, noise, covariances, weights,
             carrier_bar, signal_bar, noise_bar):
    result = []
    for row, vector in enumerate(signal_bar):
        solution = None
        for detector, direction in enumerate(selection_vectors):
            alpha = module._collinear_coefficient(vector, direction)
            if alpha is not None:
                solution = alpha*np.conj(weights[row,detector])
                break
        if solution is None:
            solution = module._solve(products, values, factor, vector, 'T')
        result.append(solution)
    return np.asarray(result)

module.host_backward = backward
args = dict(plan=plan, parameters=np.zeros((1,1)), carrier_values=np.zeros(1),
            signal_values=np.zeros(1), carrier_base=np.zeros(1), signal_base=np.zeros(1),
            noise_base=np.zeros(1), selection_vectors=directions, carrier=np.zeros(1),
            signal=np.zeros((3,2)), noise=np.ones(3), covariances=np.zeros((3,2,2)),
            weights=weights, carrier_bar=np.zeros(1), signal_bar=vectors, noise_bar=np.zeros(3))
expected = module.host_backward(**args)
reference = subprocess.check_output(['git','show','86860bdcbf4b02888b5db6ca2aa563234db0721a:differometor/host_pass.py'], cwd=root, text=True)
collect = runpy.run_path(str(root/'experiments/notes/overnight-numerics-guard-diagnostics.py'))['collect_guard_diagnostics']
originals = (module.host_backward,module._collinear_coefficient,module._solve)
with collect(reference, module=module, max_records=1) as report:
    first = module.host_backward(**args)
    module._ASSEMBLY['key'] = dict(signal_values=np.tile(values,(3,1)))
    second = module.host_backward(**args)
assert (module.host_backward,module._collinear_coefficient,module._solve) == originals
assert first.tobytes() == second.tobytes() == expected.tobytes()
assert len(report['callbacks']) == 2 and len(report['records']) == 1
for counts in report['callbacks']:
    assert counts['guard_calls']==5 and counts['accepted']==2
    assert counts['reference_accepted']==3 and counts['changed_decisions']==1
    assert counts['explicit_signal_rows']==1
assert not report['callbacks'][0]['matching_assembly_available']
assert report['callbacks'][1]['matching_assembly_available']
r = report['records'][0]
assert (r['signal_row'],r['detector']) == (0,0)
assert r['actual_solution'].tobytes() == expected[0].tobytes()
np.testing.assert_array_equal(r['reference_reused_solution'], [1,0])
np.testing.assert_array_equal(r['coefficients'],values)
# Check matching-state captures separately, not just the count-cap path.
with collect(reference, module=module) as cached_report:
    module.host_backward(**args)
np.testing.assert_array_equal(cached_report['records'][0]['coefficients'],values)
try:
    with collect(reference,module=module):
        raise RuntimeError('intentional context restoration check')
except RuntimeError:
    pass
assert (module.host_backward,module._collinear_coefficient,module._solve) == originals
print(dict(callbacks_checked=3, changed_decisions_per_callback=1,
           results_byte_identical=True, bounded_captures=True,
           cache_hit_and_miss=True, restored_after_exception=True,
           captured_adjoint_difference=float(abs(r['actual_solution'][1]))))
