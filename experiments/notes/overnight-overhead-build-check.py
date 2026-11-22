"""Candidate 4 equivalence check: vectorized build helpers vs the former loop versions.

    PYTHONPATH=<repo> /workspace/venv-feyer/bin/python experiments/notes/overnight-overhead-build-check.py

Randomized inputs (negative indices, out-of-bounds, duplicates, empty, float-valued
indices) compare `_matrix_indices_are_unique` and `_group_component_indices` with
verbatim copies of the seed implementations (keys, key order, shapes, dtypes and
values). Whole-build equality is covered by the evaluator's saved-array and
generalization comparisons. Not a benchmark.
"""

from collections import defaultdict

import numpy as np

from differometor import build as B


def old_unique(matrix_indices, matrix_shape):
    rows, columns = matrix_indices
    height, width = matrix_shape
    if len(rows) != len(columns):
        return False
    seen = set()
    for row, column in zip(rows, columns):
        row, column = int(row), int(column)
        row = row + height if row < 0 else row
        column = column + width if column < 0 else column
        if not (0 <= row < height and 0 <= column < width):
            return False
        destination = (row, column)
        if destination in seen:
            return False
        seen.add(destination)
    return True


def old_group(function_indices, function_input_indices=None):
    groups = defaultdict(list)
    for row, function_index in enumerate(function_indices):
        groups[int(function_index)].append(row)
    grouped_rows = [row for index in sorted(groups) for row in groups[index]]
    output_rows = [0] * len(function_indices)
    for grouped_row, original_row in enumerate(grouped_rows):
        output_rows[original_row] = grouped_row
    result = {
        "function_rows": {index: B._host_array(groups[index], int) for index in sorted(groups)},
        "output_rows": B._host_array(output_rows, int),
    }
    if function_input_indices is not None:
        result["parameter_indices"] = {
            index: B._host_array([function_input_indices[row] for row in groups[index]], int)
            for index in sorted(groups)
        }
    return result


def same_tree(a, b, path="root"):
    if isinstance(a, dict):
        assert isinstance(b, dict) and list(a) == list(b), (path, list(a), list(b))
        for key in a:
            same_tree(a[key], b[key], f"{path}.{key}")
        return
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape and a.dtype == b.dtype and np.array_equal(a, b), path


rng = np.random.default_rng(1)
failures = 0
for trial in range(3000):
    height, width = int(rng.integers(1, 9)), int(rng.integers(1, 9))
    count = int(rng.integers(0, 40))
    rows = rng.integers(-height - 2, height + 2, size=count)
    cols = rng.integers(-width - 2, width + 2, size=count)
    if trial % 3 == 0:  # mostly in bounds
        rows, cols = rng.integers(-height, height, size=count), rng.integers(-width, width, size=count)
    if trial % 7 == 0:
        rows = rows.astype(np.float64) + 0.25
    indices = np.stack((rows, cols))
    if old_unique(indices, (height, width)) != B._matrix_indices_are_unique(indices, (height, width)):
        failures += 1
        print("unique mismatch", trial)
    selectors = list(rng.integers(0, 6, size=count))
    inputs = rng.integers(0, 50, size=(count, 3))
    try:
        same_tree(old_group(selectors, inputs), B._group_component_indices(selectors, inputs))
        same_tree(old_group(selectors), B._group_component_indices(selectors))
    except AssertionError as error:
        failures += 1
        print("group mismatch", trial, error)
same_tree(old_group([0], [[0, 0, 0]]), B._group_component_indices([0], [[0, 0, 0]]))
print("FAILURES:", failures)
raise SystemExit(1 if failures else 0)
