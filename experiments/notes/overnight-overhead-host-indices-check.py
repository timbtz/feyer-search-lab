"""Check HostPlan's sweep/selection index ownership; no timings or optical solves.

Default requires NumPy. --structural-only uses an aliasing stand-in and does not
validate NumPy/JAX numerics. --parent-ref reads earlier source via read-only Git.
"""
import argparse
import ast
import hashlib
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(Path(__file__).with_name('overnight-overhead-layout-snapshot-check.py')))
StandIn = helpers['ArrayModuleStandIn']
NAMES = ('carrier_changing', 'signal_changing', 'signal_carrier_indices')


def check(np, parent_ref=None):
    path = ROOT / 'differometor/host_pass.py'
    source = (subprocess.check_output(['git', 'show', parent_ref + ':differometor/host_pass.py'],
                                     cwd=ROOT, text=True) if parent_ref else path.read_text())
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
             and n.name in ('_digest', '_layout_indices', 'HostPlan')]
    ns = dict(np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    cls = ns['HostPlan']
    metadata = [SimpleNamespace(_key=k) for k in ('structure', 'carrier', 'signal', 'noise')]
    checks = 0
    for count in (1, 0, 4):
        for reuse in (False, True):
            for layout in (None, SimpleNamespace(_key='layout')):
                inputs = [np.asarray(list(range(count)), dtype=np.int64) for _ in NAMES]
                plan = cls(*metadata, *inputs, reuse, layout)
                original = [a.tobytes() for a in inputs]
                key, hashed = plan._key, hash(plan)
                equivalent = cls(*metadata, *inputs, reuse, layout)
                assert plan == equivalent and hash(equivalent) == hashed
                for name, source_array, before in zip(NAMES, inputs, original):
                    if count:
                        source_array.ravel()[0] = 31
                        assert getattr(plan, name).tobytes() == before, name + ' aliases caller storage'
                    assert not getattr(plan, name).flags.writeable, name + ' remains writable'
                    if count:
                        try:
                            getattr(plan, name).ravel()[0] = 17
                        except ValueError:
                            pass
                        else:
                            raise AssertionError(name + ' allows direct mutation')
                    checks += 1
                assert plan._key == key and hash(plan) == hashed and plan == equivalent
                rebuilt = cls(*metadata, *inputs, reuse, layout)
                assert (rebuilt != plan) == bool(count)
    if np is not StandIn:
        # Native NumPy additionally checks arbitrary strides and actual index use.
        backing = np.arange(12, dtype=np.int64)
        view = backing[::3]
        plan = cls(*metadata, view, view[::-1], view.reshape(2, 2), False)
        row = np.arange(32, dtype=np.float64)
        selected = [row[getattr(plan, name)].copy() for name in NAMES]
        backing[:] = 20
        for name, expected in zip(NAMES, selected):
            target = getattr(plan, name)
            assert not np.shares_memory(target, backing)
            np.testing.assert_array_equal(row[target], expected)
            checks += 1
    print(f'PASS: {checks} HostPlan index ownership cases; backend={np.__name__}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structural-only', action='store_true')
    parser.add_argument('--parent-ref')
    args = parser.parse_args()
    if args.structural_only:
        check(StandIn, args.parent_ref)
    else:
        import numpy
        check(numpy, args.parent_ref)
