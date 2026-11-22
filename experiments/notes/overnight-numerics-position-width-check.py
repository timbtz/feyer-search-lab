"""Small compact-dense structural-index checks; no optical workloads or elapsed timings.

Extract the real classes without importing JAX, which is not installed in the
local inspection environment. Compare with parent35 and an independent dense
coordinate oracle. Run with Python -B in the existing topology inspection venv.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PARENT = "7a9480332bad29b5aaeacc5a4628481581507e7a"


def load(source):
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.ClassDef)
             and node.name in ("SparsePattern", "SparseSystem")]
    ns = dict(np=np, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "sparse-index", "exec"), ns)
    return ns["SparseSystem"]


parent_source = subprocess.check_output(
    ["git", "show", PARENT + ":differometor/sparse.py"], cwd=ROOT, text=True)
source = (ROOT / "differometor/sparse.py").read_text()
old_class, new_class = load(parent_source), load(source)
rng = np.random.default_rng(4211)
counts = dict(structures=0, query_pairs=0, zero_structure_entries=0,
              matched_exceptions=0, gathered_value_vectors=0)


def same(a, b):
    assert a.dtype == b.dtype and a.shape == b.shape
    assert a.tobytes() == b.tobytes()


def query_pair(old, new, rows, cols):
    outputs, errors = [], []
    for obj in (old, new):
        try:
            outputs.append(obj.positions(rows, cols))
            errors.append(None)
        except (ValueError, IndexError) as exc:
            outputs.append(None)
            errors.append(type(exc).__name__)
    assert errors[0] == errors[1], (rows, cols, errors)
    if errors[0] is None:
        same(*outputs)
    else:
        counts["matched_exceptions"] += 1
    counts["query_pairs"] += 1


for size in (0, 1, 2, 3, 8, 17, 33):
    for augmented in (False, True):
        width = size + augmented
        for mode in ("empty", "diagonal", "random", "dense"):
            for draw in range(4):
                base = np.zeros((size, width), dtype=np.complex128)
                if mode == "diagonal":
                    np.fill_diagonal(base, 2.)
                elif mode in ("random", "dense"):
                    occupied = (rng.random(base.shape) < .15 if mode == "random"
                                else np.ones(base.shape, dtype=bool))
                    base[occupied] = (rng.normal(size=occupied.sum())
                                      + 1j * rng.normal(size=occupied.sum()))
                count = min(2 * size + draw, size * width) if mode != "empty" else 0
                wr = rng.integers(0, size, count) if count else np.array([], dtype=int)
                wc = rng.integers(0, width, count) if count else np.array([], dtype=int)
                er, ec = wr[::3].copy(), wc[::3].copy()
                # Repeated writes, negative coordinates and explicit zero entries.
                if count:
                    wr = np.r_[wr, wr[:2]]
                    wc = np.r_[wc, wc[:2]]
                    wr[::2] -= size
                    wc[1::2] -= width
                    base[er, ec] = 0.
                args = (base, wr, wc, er, ec)
                old, new = old_class(*args), new_class(*args)
                assert old._key == new._key and old.pattern._key == new.pattern._key
                assert old.unique_writes == new.unique_writes
                for name in ("all_rows", "all_cols", "rhs_rows", "write_positions", "base_coordinates"):
                    same(getattr(old, name), getattr(new, name))
                for name in ("rows", "cols", "indices", "indptr"):
                    same(getattr(old.pattern, name), getattr(new.pattern, name))

                # Independent dense marker table using the public sparse coordinates.
                oracle = np.full(base.shape, -1, dtype=np.int64)
                oracle[new.all_rows, new.all_cols] = np.arange(new.all_rows.size)
                same(new.write_positions, oracle[wr, wc])
                for row in range(size):
                    for col in range(width):
                        if oracle[row, col] >= 0:
                            same(new.positions([row], [col]), oracle[row:row+1, col])
                        else:
                            try:
                                new.positions([row], [col])
                            except ValueError:
                                pass
                            else:
                                raise AssertionError("Absent structural position accepted")
                for rows, cols in ((wr, wc), (er, ec), ([], []), ([], [0]),
                                   ([0], []), ([size], [0]), ([-size-1], [0]),
                                   ([0], [width]), ([0], [-width-1]),
                                   ([0, 0], [0, 0, 0])):
                    query_pair(old, new, rows, cols)
                if size:
                    query_pair(old, new, [-1], [-1])
                    query_pair(old, new, np.arange(size), [0])
                    query_pair(old, new, [0], np.arange(width))
                counts["zero_structure_entries"] += int(np.sum(base[new.all_rows, new.all_cols] == 0))
                for variation in range(3):
                    changed = base.copy()
                    if count:
                        changed[wr, wc] = (variation + 1.) * (1. + .2j)
                    same(changed[old.all_rows, old.all_cols], changed[new.all_rows, new.all_cols])
                    counts["gathered_value_vectors"] += 1
                counts["structures"] += 1

# Legal but nonfinite base entries still belong to the structural index.
base = np.array([[np.nan, 0., np.inf], [0., -0., -np.inf]], dtype=complex)
old, new = old_class(base, [1, 1], [0, 0]), new_class(base, [1, 1], [0, 0])
same(old.base_coordinates, new.base_coordinates)
same(old.write_positions, new.write_positions)
assert old._key == new._key

storage = []
for size in (67, 257):
    base = np.eye(size, size + 1, dtype=complex)
    rows = np.arange(size)
    cols = (rows + 1) % size
    old, new = old_class(base, rows, cols), new_class(base, rows, cols)
    storage.append(dict(size=size, structural_entries=int(new.all_rows.size),
                        parent_lookup_bytes=old._position.nbytes,
                        candidate_lookup_bytes=new._position.nbytes))

# Exercise the actual selection expression at integer limits without allocating
# enormous matrices. Verify that the sentinel and highest offset are representable.
selection = next(node.value for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "position_dtype"
                         for target in node.targets))
selection = compile(ast.Expression(body=selection), "position-dtype", "eval")
boundary_checks = []
limit = np.iinfo(np.int32).max
for count in (0, 1, limit - 1, limit, limit + 1, np.iinfo(np.int64).max):
    dtype = eval(selection, dict(np=np, all_rows=SimpleNamespace(size=count)))
    endpoints = np.array([-1, count - 1], dtype=dtype)
    assert endpoints.tolist() == [-1, count - 1]
    assert dtype is (np.int32 if count <= limit else np.int64)
    boundary_checks.append(dict(entry_count=int(count), dtype=np.dtype(dtype).name))

result = dict(parent=PARENT, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
              counts=counts, storage=storage,
              boundary_checks=boundary_checks,
              result="all coordinate, digest, exception and value comparisons passed",
              scope="synthetic structural inspection; no JAX, optical workload or timings")
print(json.dumps(result, indent=2))
(ROOT / "experiments/notes/overnight-numerics-position-width-result.json").write_text(
    json.dumps(result, indent=2) + "\n")
