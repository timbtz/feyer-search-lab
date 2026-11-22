"""Check derivative-slot group boundaries in SystemPlan identity; no timings.

Default uses stdlib array stand-ins and extracts only the actual key expression.
--numpy additionally constructs real SystemPlan/HostPlan objects.
--jax adds a synthetic static-plan JIT dispatch check (requires NumPy/JAX).
--parent-ref REF reads earlier source with read-only Git.
"""
import argparse
import ast
import hashlib
from itertools import combinations_with_replacement
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def load_source(ref):
    path = ROOT / 'differometor/host_pass.py'
    source = (subprocess.check_output(['git', 'show', ref + ':differometor/host_pass.py'],
                                     cwd=ROOT, text=True) if ref else path.read_text())
    return path, ast.parse(source)


def partitions(size, groups):
    for cuts in combinations_with_replacement(range(size + 1), groups - 1):
        ends = (0,) + cuts + (size,)
        yield tuple(tuple(range(ends[i], ends[i + 1])) for i in range(groups))


def structural_check(tree, path):
    helpers = runpy.run_path(str(Path(__file__).with_name('overnight-overhead-layout-snapshot-check.py')))
    np = helpers['ArrayModuleStandIn']
    digest = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_digest')
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SystemPlan')
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
    key = next(n.value for n in init.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Attribute) and t.attr == '_key' for t in n.targets))
    ns = dict(np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=[digest], type_ignores=[]), str(path), 'exec'), ns)
    expression = compile(ast.Expression(body=key), str(path), 'eval')
    checked = 0
    for group_count in (2, 3, 4):
        for size in range(5):
            keys = set()
            for slots in partitions(size, group_count):
                groups = tuple((f, np.asarray(range(4), dtype=np.int64).reshape(1, 4), d)
                               for f, d in enumerate(slots))
                plan = SimpleNamespace(groups=groups, flat_selection=np.asarray(range(group_count)))
                env = dict(ns, self=plan, writes=np.asarray(range(group_count)),
                           sparse_system=SimpleNamespace(_key='fixed-system'))
                result = eval(expression, env)
                assert result == eval(expression, env), 'unstable key'
                assert result not in keys, f'derivative-slot partition collision: {slots}'
                keys.add(result)
                checked += 1
    print(f'PASS: {checked} slot partitions using actual key expression; stdlib only')


def numpy_check(tree, path, with_jax):
    import numpy as np
    names = {'_digest', '_layout_indices', 'SystemPlan', 'HostPlan'}
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    ns = dict(np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    SystemPlan, HostPlan = ns['SystemPlan'], ns['HostPlan']
    system = SimpleNamespace(write_positions=np.array([0, 1]), _key='system')
    structure = SimpleNamespace(_key='structure')
    indices = np.array([[0, 1]], dtype=np.int64)

    def make(slots):
        component = SystemPlan(system, [(0, indices, slots[0]), (1, indices, slots[1])],
                               np.array([0, 1]), np.array([0, 0]))
        return HostPlan(structure, component, component, component, [], [], [], False)

    first = make(((0,), (1,)))
    second = make(((0, 1), ()))
    equivalent = make(((0,), (1,)))
    assert first != second and first._key != second._key
    assert first == equivalent and hash(first) == hash(equivalent)
    print('PASS: actual NumPy SystemPlan/HostPlan identity distinguishes group boundaries')
    if with_jax:
        import jax
        import jax.numpy as jnp
        jax.config.update('jax_enable_x64', True)
        traces = []

        def marker(plan, value):
            # A synthetic function whose traced behavior depends on the same
            # per-group metadata as backward. No optical-solver claim.
            traces.append(plan._key)
            scale = sum((f + 1) * len(slots) for f, _, slots in plan.carrier.groups)
            return value * scale

        compiled = jax.jit(marker, static_argnums=0)
        x = jnp.asarray(2.0, dtype=jnp.float64)
        assert float(compiled(first, x)) == 6.0
        assert float(compiled(second, x)) == 4.0
        assert float(compiled(equivalent, x)) == 6.0
        assert len(traces) == 2
        print('PASS: two distinct JIT traces, equivalent plan reuses its correct trace')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-ref')
    parser.add_argument('--numpy', action='store_true')
    parser.add_argument('--jax', action='store_true')
    args = parser.parse_args()
    source_path, source_tree = load_source(args.parent_ref)
    structural_check(source_tree, source_path)
    if args.numpy or args.jax:
        numpy_check(source_tree, source_path, args.jax)
