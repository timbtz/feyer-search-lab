"""Small callback-layout checks, not optical benchmarks.

Default: real NumPy adapter checks. --structural-only: stdlib shape/plumbing
stand-in only. --jax: additionally execute the actual custom VJP with a linear
synthetic host function. No solver or fixture is loaded.
"""
import argparse
import ast
from functools import partial
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
NAMES = {'_shapes', '_transposed', 'host_forward_transposed',
         'host_backward_transposed', '_forward_call', 'host_pass',
         '_host_pass_fwd', '_host_pass_bwd'}


class Array:
    def __init__(self, shape, dtype, data=None):
        self.shape, self.dtype = tuple(shape), dtype
        count = 1
        for n in shape:
            count *= n
        self.data = list(range(count)) if data is None else list(data)

    @property
    def T(self):
        rows, cols = self.shape
        return Array((cols, rows), self.dtype,
                     [self.data[r * cols + c] for c in range(cols) for r in range(rows)])


def extract(namespace, decorators=False):
    tree = ast.parse((ROOT / 'differometor/host_pass.py').read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
    if not decorators:
        for node in nodes:
            node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<actual callback adapters>', 'exec'), namespace)
    if decorators:
        namespace['host_pass'].defvjp(namespace['_host_pass_fwd'], namespace['_host_pass_bwd'])


class Plan:
    def __init__(self, cn, n):
        self.structure = SimpleNamespace(carrier=SimpleNamespace(size=cn), signal=SimpleNamespace(size=n))


def adapter_checks(structural):
    if structural:
        np = SimpleNamespace(asarray=lambda a: a,
                             ascontiguousarray=lambda a: Array(a.shape, a.dtype, a.data))
        def make(shape, real=False):
            return Array(shape, 'float64' if real else 'complex128')
        def equal(a, b):
            return a.shape == b.shape and a.dtype == b.dtype and a.data == b.data
    else:
        import numpy as np
        def make(shape, real=False):
            count = 1
            for n in shape:
                count *= n
            out = np.arange(count, dtype=np.float64).reshape(shape)
            if not real:
                out = out.astype(np.complex128) * (1 + 2j)
                # Include signed zero and nonfinite payloads: adapters must copy,
                # never perform arithmetic on these values.
                flat = out.ravel()
                for i, value in enumerate([complex(-0.0, -0.0), complex(float('nan'), 2), complex(3, float('inf'))]):
                    if i < flat.size:
                        flat[i] = value
            return out
        def equal(a, b):
            return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()
    def callback(fn, shapes, *inputs, **kwargs):
        assert kwargs == {'vmap_method': 'sequential'}
        outputs = fn(*inputs)
        assert len(outputs) == len(shapes)
        for value, shape in zip(outputs, shapes):
            assert value.shape == shape.shape
        return outputs
    ns = dict(np=np, jnp=SimpleNamespace(complex128='complex128', float64='float64'),
              jax=SimpleNamespace(ShapeDtypeStruct=lambda s, d: SimpleNamespace(shape=s, dtype=d),
                                  pure_callback=callback), partial=partial)
    extract(ns)
    count = 0
    for bc, sweeps, cn, size, detectors in [(1, 1, 2, 3, 1), (2, 3, 4, 7, 2), (3, 2, 1, 5, 3), (1, 4, 3, 2, 0)]:
        bs = bc * sweeps
        plan = Plan(cn, size)
        inputs = tuple(make(s) for s in [(bc, cn), (1, bc), (1, sweeps), (bs, size), (1,), (detectors, bs), (detectors, bc, size)])
        original = (make((bc, cn)), make((bs, size)), make((detectors, bs), True),
                    make((bs, detectors, size)), make((bs, detectors, size)))
        calls = []
        ns['host_forward'] = lambda plan, *args: original
        def backward(plan, *args):
            calls.append(args)
            return inputs
        ns['host_backward'] = backward
        direct = ns['host_pass'](plan, *inputs)
        outputs, residual = ns['_host_pass_fwd'](plan, *inputs)
        assert len(residual[1]) == 5
        assert all(outputs[i] is residual[1][i] for i in range(3))
        assert all(equal(a, b) for a, b in zip(direct, outputs))
        bars = tuple(make(v.shape, i == 2) for i, v in enumerate(outputs))
        result = ns['_host_pass_bwd'](plan, residual, bars)
        assert result is inputs
        args = calls[-1]
        assert all(a is b for a, b in zip(args[:7], inputs))
        assert all(equal(a, b) for a, b in zip(args[7:12], original))
        for index in (0, 1):
            assert equal(args[12 + index], np.ascontiguousarray(bars[index].T))
            if not structural:
                assert args[7 + index].flags.c_contiguous
                assert args[12 + index].flags.c_contiguous
        assert args[-1] is bars[-1]
        count += 1
    print('PASS', count, 'adapter cases;', 'stdlib stand-in only' if structural else 'real NumPy, byte-exact primal restoration')


def jax_checks():
    import numpy as np
    import jax
    import jax.numpy as jnp
    jax.config.update('jax_enable_x64', True)
    ns = dict(np=np, jnp=jnp, jax=jax, partial=partial)
    extract(ns, decorators=True)
    for bc, sweeps, cn, n, d in [(1, 2, 3, 4, 1), (2, 3, 2, 5, 2)]:
        bs = bc * sweeps
        plan = Plan(cn, n)
        shapes = [(bc, cn), (1, bc), (1, sweeps), (bs, n), (1,), (d, bs), (d, bc, n)]
        inputs = tuple(jnp.asarray(np.arange(np.prod(s)).reshape(s) * (0.25 + 0.5j), dtype=jnp.complex128) for s in shapes)
        def forward(plan, p, cv, sv, cb, sb, nb, sel):
            aux = np.zeros((bs, d, n), dtype=np.complex128)
            return np.asarray(p), np.asarray(cb), np.real(nb), aux, aux.copy()
        def backward(plan, *args):
            primal, outputs, bars = args[:7], args[7:12], args[12:]
            assert np.array_equal(outputs[0], primal[0])
            assert np.array_equal(outputs[1], primal[3])
            grad = [np.zeros_like(a) for a in primal]
            grad[0], grad[3], grad[5] = bars[0], bars[1], bars[2].astype(primal[5].dtype)
            return tuple(grad)
        ns['host_forward'], ns['host_backward'] = forward, backward
        def candidate(*xs):
            return ns['host_pass'](plan, *xs)
        def reference(*xs):
            return xs[0].T, xs[3].T, jnp.real(xs[5])
        expected, ref_pull = jax.vjp(reference, *inputs)
        actual, pull = jax.jit(lambda *xs: jax.vjp(candidate, *xs))(*inputs)
        bars = tuple(jnp.ones_like(x) * (1 + 2j if jnp.iscomplexobj(x) else 3) for x in actual)
        actual_grad = jax.jit(pull)(bars)
        for a, b in zip(actual, expected):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
        for a, b in zip(actual_grad, ref_pull(bars)):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    print('PASS 2 JIT/VJP cases with linear synthetic host functions (no optical solve)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structural-only', action='store_true')
    parser.add_argument('--jax', action='store_true')
    args = parser.parse_args()
    adapter_checks(args.structural_only)
    if args.jax:
        jax_checks()
