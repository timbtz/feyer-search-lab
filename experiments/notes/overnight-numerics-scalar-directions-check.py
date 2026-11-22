"""Candidate 19 scalar rules and allocation counts; no workloads or timings."""
from pathlib import Path
import runpy
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
checks = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-directions-check.py'))
PARENT = '457d0eaa2b4ab4fe1005ad0cd0cbd47999864575'
parent_source = subprocess.check_output(
    ['git', 'show', PARENT + ':differometor/host.py'], cwd=ROOT, text=True)
parent = checks['load'](parent_source)
candidate = checks['load']((ROOT / 'differometor/host.py').read_text())
equal = checks['loader']['check_equal']

operators = ('__add__', '__sub__', '__mul__', '__truediv__',
             '__radd__', '__rsub__', '__rmul__', '__rtruediv__')
arithmetic_checks = 0
for value in (0., -0., 1., -1., 1e-12, 1e12, np.inf, np.nan):
    for scalar in (0., -0., 2., -3., 1j, np.inf, np.nan):
        for directions in ({}, {0: (0., 0.)}, {0: (1., 0.), 3: (0., 1j)}):
            for operator in operators:
                results = []
                exceptions = []
                for ns in (parent, candidate):
                    operand = ns['_Directions'](np.asarray(value, dtype=np.complex128), directions.copy())
                    try:
                        with np.errstate(all='ignore'):
                            result = getattr(operand, operator)(scalar)
                    except ZeroDivisionError as error:
                        exceptions.append(type(error))
                        continue
                    exceptions.append(None)
                    assert result.directions.keys() == directions.keys()
                    assert result.directions is not operand.directions
                    results.append((result.v,) + tuple(x for key in sorted(directions)
                                                     for x in result.directions[key]))
                assert exceptions[0] == exceptions[1], (value, scalar, directions, operator, exceptions)
                if exceptions[0] is None:
                    equal(*(tuple(np.asarray(item) for item in result) for result in results))
                arithmetic_checks += 1

counts = {}
for label, ns in (('parent', parent), ('candidate', candidate)):
    counts[label] = 0
    cls = ns['_Directions']
    original = cls.__init__
    def counted(self, value, directions, original=original, label=label):
        counts[label] += 1
        original(self, value, directions)
    cls.__init__ = counted

rng = np.random.default_rng(2026112219)
inputs = rng.uniform(.1, .8, (3, 11, 7)).astype(np.complex128)
inputs[..., 4:6] += 1
inputs += .01j * rng.normal(size=inputs.shape)
component_checks = 0
for function in range(len(candidate['HOST_FUNCTIONS'])):
    for slots in ((0,), (0, 2, 6), tuple(range(7)), (-1, 6, 0, 0)):
        with np.errstate(all='ignore'):
            equal(parent['function_jacobian'](function, slots, inputs, with_outputs=False)[1:],
                  candidate['function_jacobian'](function, slots, inputs, with_outputs=False)[1:])
        component_checks += 1
assert counts['candidate'] < counts['parent']
print(dict(parent_sha=PARENT, scalar_arithmetic_checks=arithmetic_checks,
           component_checks_against_parent=component_checks, direction_object_constructions=counts,
           scope='synthetic operation counts only; no performance claim'))
