"""Candidate39 key-equivalence diagnostic, with no timings or optical workloads.

--structural-only executes actual candidate _digest with stdlib buffer objects.
Default additionally checks actual NumPy buffers; requires supervisor environment.
"""
import argparse
import array
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = '''
def reference(*arrays):
    digest = hashlib.sha256()
    for array in arrays:
        array = np.ascontiguousarray(array)
        digest.update(str(array.dtype).encode())
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()
'''


def functions(np):
    tree = ast.parse((ROOT / 'differometor/host_pass.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_digest')
    assert 'tobytes' not in ast.unparse(node), 'Run against candidate39 source'
    scope = {'np': np, 'hashlib': hashlib}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<candidate digest>', 'exec'), scope)
    exec(REFERENCE, scope)
    return scope['_digest'], scope['reference']


class Buffer(array.array):
    copies = 0

    @property
    def shape(self):
        return (len(self),)

    @property
    def dtype(self):
        return self.typecode

    def tobytes(self):
        Buffer.copies += 1
        return super().tobytes()


def structural():
    shim = SimpleNamespace(ascontiguousarray=lambda a: a,
                           asarray=lambda a, dtype: Buffer('q', a), int64='q')
    candidate, reference = functions(shim)
    checks = 0
    for code in ('b', 'B', 'h', 'H', 'i', 'I', 'q', 'Q', 'f', 'd'):
        for count in (0, 1, 2, 7, 64, 1024):
            buf = Buffer(code, (i % 100 for i in range(count)))
            for inputs in ((buf,), (buf, buf), ()):
                expected = reference(*inputs)
                Buffer.copies = 0
                assert candidate(*inputs) == expected
                assert Buffer.copies == 0
                checks += 1
    print(f'{checks} actual-function stdlib buffer checks passed; zero tobytes calls')


def numeric():
    import numpy as np
    candidate, reference = functions(np)
    checks = 0
    for dtype in ('bool', 'int8', '<i4', '>i4', '<i8', '>i8', '<f8', '>f8', '<c16', '>c16'):
        a = np.arange(24).astype(dtype).reshape(4, 6)
        variants = (a, a.T, a[:, ::2], a[::-1], a[:0], a[:, :0],
                    np.asarray(3, dtype=dtype), np.asfortranarray(a))
        for value in variants:
            for readonly in (False, True):
                view = value.view()
                if readonly:
                    view.setflags(write=False)
                for inputs in ((view,), (view, a.T), ()):
                    before = [x.tobytes() for x in inputs]
                    assert candidate(*inputs) == reference(*inputs)
                    assert before == [x.tobytes() for x in inputs]
                    checks += 1
    special = np.array([0.0, -0.0, np.nan, np.inf, -np.inf])
    assert candidate(special) == reference(special)
    assert candidate(np.array([0.0])) != candidate(np.array([-0.0]))
    assert candidate(np.arange(6)) != candidate(np.arange(6).reshape(2, 3))
    assert candidate(np.array([1], dtype='i8')) != candidate(np.array([1], dtype='u8'))
    print(f'{checks} NumPy comparisons and four encoding checks passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structural-only', action='store_true')
    args = parser.parse_args()
    structural()
    if not args.structural_only:
        numeric()
