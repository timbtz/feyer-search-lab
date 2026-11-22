"""Small sparse solve/layout inspection for trial26; no optical benchmark/timing."""
import ast
from pathlib import Path
import subprocess
import numpy as np

# Reuse only the loader/helpers of the retained trial25 inspection, not its loop.
path = Path(__file__).with_name('overnight-numerics-column-order-check.py')
tree = ast.parse(path.read_text())
tree.body = tree.body[:next(i for i, node in enumerate(tree.body)
                          if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'rng'
                                  for target in node.targets))]
ns = {'__file__': str(path.resolve())}
exec(compile(tree, str(path), 'exec'), ns)
old, _ = ns['load'](ns['parent_source'])
trial25_source = subprocess.check_output(
    ['git', 'show', '8aa393502844782c85bb84f381cad67b4d83296c:differometor/host_pass.py'],
    cwd=ns['ROOT'], text=True)
trial25, _ = ns['load'](trial25_source)
new, _ = ns['load'](ns['source'])
rng = np.random.default_rng(10427)
layout_changes = refined_layout_changes = checks = 0

def layout(array):
    return array.flags.c_contiguous, array.flags.f_contiguous

for case in range(400):
    size = int(rng.integers(6, 75))
    matrix = rng.normal(size=(size, size)) + 1j*rng.normal(size=(size, size))
    matrix[rng.random((size, size)) > .08] = 0
    matrix += np.eye(size) * (.1 if case % 2 else size)
    pattern, values = ns['pattern'](matrix)
    first = old['_factor'](pattern, values)
    order25 = trial25['_ColumnOrdering'](pattern, first)
    order26 = new['_ColumnOrdering'](pattern, first)
    scales = 10**rng.uniform(-12, 12, size)
    values *= scales[pattern.rows] / scales[pattern.cols]
    values *= 1 + .3j*rng.normal(size=values.size)
    reference = old['_factor'](pattern, values)
    factors = reference, order25.factor(values), order26.factor(values)
    assert np.array_equal(first.perm_c, reference.perm_c)
    for trans in ('N', 'T', 'H'):
        for width in (1, 2, 5):
            rhs = rng.normal(size=(size, width)) + 1j*rng.normal(size=(size, width))
            saved = rhs.copy()
            direct = [factor.solve(rhs, trans=trans) for factor in factors]
            for result in direct[1:]:
                ns['equal'](direct[0], result)
            assert layout(direct[0]) == layout(direct[2])
            layout_changes += layout(direct[0]) != layout(direct[1])
            counted = [ns['CountSolve'](factor) for factor in factors]
            refined = [module['_solve'](module['_Products'](pattern), values,
                                        factor, rhs, trans)
                       for module, factor in zip((old, trial25, new), counted)]
            for result in refined[1:]:
                ns['equal'](refined[0], result)
            assert layout(refined[0]) == layout(refined[2])
            refined_layout_changes += layout(refined[0]) != layout(refined[1])
            assert len({factor.calls for factor in counted}) == 1
            ns['equal'](rhs, saved)
            checks += 1

assert layout_changes == refined_layout_changes == 800
print(dict(factor_triples=400, direct_and_refined_solve_triples=checks,
           trial25_direct_layout_changes=layout_changes,
           trial25_refined_layout_changes=refined_layout_changes,
           trial26_layout_changes=0, all_values_bitwise_equal=True,
           refinement_counts_equal=True,
           scope='synthetic inspection; does not explain remote rand3 discrepancy'))
