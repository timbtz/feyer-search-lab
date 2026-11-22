"""Candidate42 optional-JIT construction and API checks, without benchmarks.

--structural-only uses a recording JIT stand-in. Default also checks real JAX
calls, lower/compile, vmap, JVP and VJP on small synthetic functions.
"""
import argparse
import ast
import functools
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(jit):
    tree = ast.parse((ROOT / 'differometor/simulate.py').read_text())
    node = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == '_DeferredJit')
    scope = {'jit': jit, 'update_wrapper': functools.update_wrapper}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<deferred JIT>', 'exec'), scope)
    return scope['_DeferredJit'], tree


def structural():
    calls = []

    def jit(function, **options):
        calls.append((function, options))
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            return function(*args, **kwargs)
        wrapped.lower = lambda *a, **k: ('lower', function(*a, **k))
        wrapped.clear_cache = lambda: 'cleared'
        return wrapped

    deferred, tree = load(jit)
    def example(value, *, scale=2):
        """Example metadata."""
        return scale * value

    checks = 0
    for options in ({}, {'static_argnums': (0,), 'inline': True},
                    {'static_argnums': (0, 1), 'inline': True}):
        for first in ('call', 'lower', 'clear_cache'):
            before = len(calls)
            function = deferred(example, **options)
            assert len(calls) == before
            assert inspect.signature(function) == inspect.signature(example)
            assert function.__name__ == example.__name__
            assert function.__doc__ == example.__doc__
            assert function.__wrapped__ is example
            if first == 'call':
                assert function(3, scale=4) == 12
            elif first == 'lower':
                assert function.lower(3, scale=4) == ('lower', 12)
            else:
                assert function.clear_cache() == 'cleared'
            assert function(4) == 8
            assert function.lower(5) == ('lower', 10)
            assert function.clear_cache() == 'cleared'
            try:
                function.not_a_jax_attribute
            except AttributeError:
                pass
            else:
                raise AssertionError('Missing attributes must raise')
            assert len(calls) == before + 1
            assert calls[-1] == (example, options)
            checks += 1
    names = {'_evaluate_component', '_evaluate_component_group', '_evaluate_component_group_slots'}
    nodes = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in names]
    assert len(nodes) == 3
    scope = {'_DeferredJit': deferred, 'partial': functools.partial}
    before = len(calls)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + nodes,
                        type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<actual helper declarations>', 'exec'), scope)
    assert len(calls) == before
    assert all(isinstance(scope[name], deferred) for name in names)
    print(f'{checks} lazy API cases passed; actual three declarations construct zero JIT wrappers')


def numeric():
    import jax
    import jax.numpy as jnp
    import numpy as np
    jax.config.update('jax_enable_x64', True)
    deferred, _ = load(jax.jit)
    def example(mode, value):
        if mode:
            return value * jnp.conj(value) + value
        return jnp.abs(value)
    checks = 0
    for inline in (False, True):
        options = dict(static_argnums=(0,), inline=inline)
        eager = jax.jit(example, **options)
        lazy = deferred(example, **options)
        for mode in (False, True):
            for value in (jnp.array([0., -0., 2.]), jnp.array([0j, 1+2j, -3j])):
                f = lambda x: lazy(mode, x)
                g = lambda x: eager(mode, x)
                np.testing.assert_array_equal(f(value), g(value))
                np.testing.assert_array_equal(lazy.lower(mode, value).compile()(value), g(value))
                np.testing.assert_array_equal(jax.vmap(f)(jnp.stack([value, value])),
                                              jax.vmap(g)(jnp.stack([value, value])))
                a = jax.jvp(f, (value,), (jnp.ones_like(value),))
                b = jax.jvp(g, (value,), (jnp.ones_like(value),))
                for x, y in zip(a, b):
                    np.testing.assert_array_equal(x, y)
                out, pull = jax.vjp(f, value)
                _, reference = jax.vjp(g, value)
                np.testing.assert_array_equal(pull(jnp.ones_like(out))[0], reference(jnp.ones_like(out))[0])
                lazy.clear_cache()
                checks += 1
    print(f'{checks} real JAX call/lower/vmap/JVP/VJP cases passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structural-only', action='store_true')
    args = parser.parse_args()
    structural()
    if not args.structural_only:
        numeric()
