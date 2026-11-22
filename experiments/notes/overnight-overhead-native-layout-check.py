"""Check restored callback plumbing; --jax adds a small synthetic JIT/VJP test.

Default uses stdlib shape/data stand-ins, not real JAX or numerical optics.
"""
import argparse
import ast
from functools import partial
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(Path(__file__).with_name('overnight-overhead-shared-residual-check.py')))
Array, Plan, extract = (helpers[name] for name in ('Array', 'Plan', 'extract'))
ADMITTED = 'ee4fea28c04d482566be16e916b609d7c6a99e5e'


def structural_checks():
    source = (ROOT / 'differometor/host_pass.py').read_text()
    admitted = subprocess.check_output(['git', 'show', ADMITTED + ':differometor/host_pass.py'], cwd=ROOT, text=True)
    marker = 'def _shapes(plan, carrier_values, signal_values, selection_vectors):'
    assert source[source.index(marker):] == admitted[admitted.index(marker):]
    assert all(name not in source for name in ('def _transposed(', 'def host_forward_transposed(',
                                              'def host_backward_transposed('))
    sim = ast.parse((ROOT / 'differometor/simulate.py').read_text())
    function = next(n for n in sim.body if isinstance(n, ast.FunctionDef) and n.name == '_simulate_host_pass')
    expected = ast.parse('return carrier.T, signal.T, noise.squeeze()').body[0]
    assert ast.dump(function.body[-1]) == ast.dump(expected)

    def callback(fn, shapes, *inputs, **kwargs):
        assert kwargs == {'vmap_method': 'sequential'}
        outputs = fn(*inputs)
        assert len(outputs) == len(shapes)
        assert all(x.shape == s.shape and x.dtype == s.dtype for x, s in zip(outputs, shapes))
        return outputs

    ns = dict(partial=partial, jnp=SimpleNamespace(complex128='complex128', float64='float64'),
              jax=SimpleNamespace(pure_callback=callback,
                                  ShapeDtypeStruct=lambda s, d: SimpleNamespace(shape=s, dtype=d)))
    extract(ns)
    for bc, sweeps, cn, n, d in [(1, 1, 2, 3, 1), (2, 3, 4, 7, 2), (3, 2, 1, 5, 3), (1, 4, 3, 2, 0)]:
        bs = bc * sweeps
        plan = Plan(cn, n)
        inputs = tuple(Array(s, 'complex128') for s in
                       [(bc, cn), (1, bc), (1, sweeps), (bs, n), (1,), (d, bs), (d, bc, n)])
        outputs = (Array((bc, cn), 'complex128'), Array((bs, n), 'complex128'),
                   Array((d, bs), 'float64'), Array((bs, d, n), 'complex128'), Array((bs, d, n), 'complex128'))
        ns['host_forward'] = lambda plan, *args: outputs
        received = []
        def backward(plan, *args):
            received.append(args)
            return inputs
        ns['host_backward'] = backward
        primal, residual = ns['_host_pass_fwd'](plan, *inputs)
        assert all(a is b for a, b in zip(primal, outputs))
        assert all(a is b for a, b in zip(residual[1], outputs))
        assert ns['host_pass'](plan, *inputs) == primal
        bars = tuple(Array(x.shape, x.dtype) for x in primal)
        assert ns['_host_pass_bwd'](plan, residual, bars) is inputs
        assert all(a is b for a, b in zip(received[-1], (*inputs, *outputs, *bars)))
    print('PASS: exact admitted callback source, public transpose, 4 structural plumbing cases')


def jax_checks():
    # Reuse the earlier independent linear reference and checks, changing only
    # the candidate wrapper to apply the public transpose now done by simulate.
    tree = ast.parse(Path(__file__).with_name('overnight-overhead-shared-residual-check.py').read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'jax_checks')
    candidate = next(n for n in ast.walk(function) if isinstance(n, ast.FunctionDef) and n.name == 'candidate')
    candidate.body = ast.parse("carrier, signal, noise = ns['host_pass'](plan, *xs)\nreturn carrier.T, signal.T, noise").body
    namespace = dict(np=None, partial=partial, extract=extract, Plan=Plan)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 '<linear JAX callback check>', 'exec'), namespace)
    namespace['jax_checks']()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jax', action='store_true')
    args = parser.parse_args()
    structural_checks()
    if args.jax:
        jax_checks()
