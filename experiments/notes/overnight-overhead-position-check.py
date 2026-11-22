"""Compare sparse coordinate lookup with the previous dense table, without solves.

Run in the supervisor's fixed environment. Uses synthetic structures only;
reports metadata storage, not a benchmark time or physical correctness claim.
"""

import hashlib
import json

import numpy as np

from differometor.sparse import SparseSystem

rng = np.random.default_rng(41763)
checks = 0


def reference(base, wr, wc, er, ec):
    size = base.shape[0]
    mask = base != 0
    mask[wr, wc] = True
    if er.size:
        mask[er, ec] = True
    cc, rr = np.nonzero(mask[:, :size].T)
    rhs = np.nonzero(mask[:, size])[0] if base.shape[1] == size + 1 else np.zeros(0, dtype=np.int64)
    rr = np.concatenate([rr, rhs])
    cc = np.concatenate([cc, np.full(rhs.shape, size, dtype=np.int64)])
    table = np.full(base.shape, -1, dtype=np.int64)
    table[rr, cc] = np.arange(rr.size)
    return table, rr, cc


def compare_query(system, table, rows, cols):
    global checks
    def old():
        result = table[np.asarray(rows, dtype=np.int64).ravel(), np.asarray(cols, dtype=np.int64).ravel()]
        if np.any(result < 0):
            raise ValueError("Requested positions outside the sparse pattern")
        return result
    try:
        expected = old()
    except (IndexError, ValueError) as exc:
        try:
            system.positions(rows, cols)
        except type(exc):
            pass
        else:
            raise AssertionError("Candidate did not raise the reference exception type")
    else:
        result = system.positions(rows, cols)
        assert result.dtype == expected.dtype
        np.testing.assert_array_equal(result, expected)
    checks += 1


storage = []
for n in (0, 1, 2, 5, 17):
    for augmented in (False, True):
        shape = (n, n + int(augmented))
        for density in (0.0, 0.2, 1.0):
            base = rng.normal(size=shape) + 1j * rng.normal(size=shape)
            base[rng.random(shape) >= density] = 0
            if n:
                wr = rng.integers(-n, n, size=12, dtype=np.int64)
                wc = rng.integers(-shape[1], shape[1], size=12, dtype=np.int64)
                # Include duplicate destinations and an explicit structural zero.
                wr[:3], wc[:3] = 0, -1
                base[0, -1] = 0
                er = np.array([-1, 0], dtype=np.int64)
                ec = np.array([0, -1], dtype=np.int64)
            else:
                wr = wc = er = ec = np.zeros(0, dtype=np.int64)
            table, rr, cc = reference(base, wr, wc, er, ec)
            system = SparseSystem(base, wr, wc, er, ec)
            np.testing.assert_array_equal(system.all_rows, rr)
            np.testing.assert_array_equal(system.all_cols, cc)
            np.testing.assert_array_equal(system.write_positions, table[wr, wc])
            assert system.unique_writes == (np.unique(table[wr, wc]).size == wr.size)
            digest = hashlib.sha256()
            for a in (np.int64(n), np.int64(augmented), rr, cc, table[wr, wc]):
                digest.update(np.asarray(a).tobytes())
            assert system._key == digest.hexdigest()
            assert not hasattr(system, "_position")
            compare_query(system, table, wr, wc)
            compare_query(system, table, rr, cc)
            compare_query(system, table, [], [])
            if n:
                for row in range(-n - 1, n + 1):
                    for col in range(-shape[1] - 1, shape[1] + 1):
                        compare_query(system, table, [row], [col])
                compare_query(system, table, [0], [0, -1, 0])
                compare_query(system, table, [0, -1, 0], [-1])
                compare_query(system, table, [[0, -1]], [[0], [-1]])
                compare_query(system, table, [0, 0], [0, 0, 0])
                # Rebuilding after changing a previously absent base entry must
                # update structural metadata; no lookup survives across builds.
                absent = np.argwhere(table < 0)
                if absent.size:
                    row, col = absent[0]
                    base[row, col] = 2 + 3j
                    rebuilt = SparseSystem(base, wr, wc, er, ec)
                    changed_table, _, _ = reference(base, wr, wc, er, ec)
                    compare_query(rebuilt, changed_table, [row], [col])
            storage.append({"shape": shape, "density": density,
                            "old_table_bytes": table.nbytes,
                            "new_keys_bytes": system._position_keys.nbytes})

# Empty sparse patterns without any write/extra destinations.
for shape in ((1, 1), (3, 4), (4, 4)):
    base = np.zeros(shape, dtype=np.complex128)
    empty = np.zeros(0, dtype=np.int64)
    table, _, _ = reference(base, empty, empty, empty, empty)
    system = SparseSystem(base, empty, empty)
    compare_query(system, table, [], [])
    compare_query(system, table, [0], [0])

print(json.dumps({"passed": True, "query_checks": checks, "storage": storage}, indent=2))
