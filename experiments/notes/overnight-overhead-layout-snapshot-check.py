"""Check ParameterLayout ownership and key stability (no optical runs or timing).

Default uses real NumPy and the actual extracted class/digest. --structural-only
uses a small aliasing array stand-in to exercise ownership without dependencies;
its results do not substitute for the NumPy check in the fixed environment.
--parent-ref REF reads an older source using read-only Git for a regression check.
"""

import argparse
import array
import ast
import hashlib
from pathlib import Path
import subprocess
from types import SimpleNamespace


class ArrayStandIn:
    def __init__(self, values, shape=None):
        self.data = list(values)
        self.shape = (len(self.data),) if shape is None else shape
        self.dtype = "int64"
        self.flags = SimpleNamespace(writeable=True)

    def reshape(self, *shape):
        shape = shape[0] if len(shape) == 1 and isinstance(shape[0], tuple) else shape
        known = 1
        for value in shape:
            if value != -1:
                known *= value
        view = ArrayStandIn([], tuple(len(self.data) // known if value == -1 else value for value in shape))
        view.data = self.data
        view.flags.writeable = self.flags.writeable
        return view

    def ravel(self):
        return self.reshape(-1)

    def setflags(self, write):
        self.flags.writeable = write

    def tobytes(self):
        return array.array('q', self.data).tobytes()

    def __setitem__(self, index, value):
        if not self.flags.writeable:
            raise ValueError("read-only snapshot")
        self.data[index] = value


class ArrayModuleStandIn:
    int64 = int

    @staticmethod
    def asarray(values, dtype=None):
        if isinstance(values, ArrayStandIn):
            return values
        return ArrayStandIn([values] if isinstance(values, int) else values)

    @classmethod
    def array(cls, values, dtype=None, copy=True):
        source = cls.asarray(values, dtype)
        return ArrayStandIn(source.data, source.shape) if copy else source

    ascontiguousarray = asarray


def run(np, parent_ref=None):
    source_path = Path(__file__).resolve().parents[2] / 'differometor/host_pass.py'
    source = (subprocess.check_output(['git', 'show', parent_ref + ':differometor/host_pass.py'],
                                      text=True) if parent_ref else source_path.read_text())
    tree = ast.parse(source)
    selected = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                and node.name in ('_digest', '_layout_indices', 'ParameterLayout')]
    namespace = dict(np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source_path), 'exec'), namespace)
    cls = namespace['ParameterLayout']
    names = ['optimized_parameter_indices', 'optimized_value_indices', 'linked_indices',
             'indices_to_link', 'qhd_parameter_indices', 'qhd_placing_indices', 'linking_function_indices']
    checks = 0
    for count in (1, 0, 3):
        for optional in (False, True):
            inputs = [np.asarray(list(range(count)), dtype=np.int64) for _ in names]
            inputs[5] = np.asarray(list(range(count * 3)), dtype=np.int64).reshape(-1, 3)
            if optional:
                inputs[6] = None
            plan = cls(16, *inputs)
            key = plan._key
            before = [None if x is None else x.tobytes() for x in inputs]
            for name, source, original in zip(names, inputs, before):
                target = getattr(plan, name)
                if source is None:
                    assert target is None
                    continue
                if count:
                    source.ravel()[0] = 15
                    assert target.tobytes() == original, name + ' aliases caller storage'
                assert not target.flags.writeable, name + ' remains writable'
                if count:
                    try:
                        target.ravel()[0] = 9
                    except ValueError:
                        pass
                    else:
                        raise AssertionError(name + ' allows mutation')
                checks += 1
            assert plan._key == key
            rebuilt = cls(16, *inputs)
            assert (rebuilt._key != key) == bool(count)
    # Real NumPy-only extra case: a non-contiguous caller-owned view.
    if np is not ArrayModuleStandIn:
        backing = np.arange(12, dtype=np.int64)
        view = backing[::2]
        plan = cls(16, view, view, view, view, view, view.reshape(-1, 3), view)
        before = plan.optimized_parameter_indices.copy()
        backing[:] = 14
        for name in names:
            assert not np.shares_memory(getattr(plan, name), backing)
        assert np.array_equal(plan.optimized_parameter_indices, before)
        checks += 1
    print(f'PASS: {checks} snapshot cases; backend={np.__name__}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structural-only', action='store_true')
    parser.add_argument('--parent-ref')
    args = parser.parse_args()
    if args.structural_only:
        run(ArrayModuleStandIn, args.parent_ref)
    else:
        import numpy
        run(numpy, args.parent_ref)
