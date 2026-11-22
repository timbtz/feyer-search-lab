"""Small arithmetic-dispatch comparison against31; no workload or timing runs."""
from collections import Counter
from contextlib import redirect_stdout
import io
from pathlib import Path
import runpy
import subprocess
import sys
import types

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
with redirect_stdout(io.StringIO()):
    checked = runpy.run_path(str(ROOT / 'experiments/notes/overnight-numerics-program-check.py'))
new = checked['programs']
host = checked['new']
equal = checked['equal']
parent = types.ModuleType('parent31_program')
parent_filename = '<candidate31-host-program>'
source = subprocess.check_output(['git', 'show',
    '316df3dd0e65d2d6edac263e24cf14ea9b80972b:differometor/host_program.py'], text=True)
exec(compile(source, parent_filename, 'exec'), parent.__dict__)
rng = np.random.default_rng(2026112232)
counts = Counter()

def profile(frame, event, arg):
    if event == 'call' and frame.f_code.co_name == '<genexpr>':
        if frame.f_code.co_filename == parent_filename:
            counts['parent_generator_resumes'] += 1
        elif frame.f_code.co_filename == new.__file__:
            counts['candidate_generator_resumes'] += 1

checks = 0
operations = 0
expected_resumes = 0
arity = Counter()
with np.errstate(all='ignore'):
    for function in host['HOST_FUNCTIONS']:
        program = new.jacobian_program(function, tuple(range(7)), 7, host['Dual'], host['_Slots'])
        previous = parent._Program(program.nodes, program.destinations, program.release)
        columns = list(rng.uniform(.1, .8, (7, 3, 5)).astype(np.complex128))
        a = [np.zeros((3, 5, 4, 7), dtype=np.complex128) for _ in range(2)]
        b = [np.zeros_like(x) for x in a]
        for node in program.nodes:
            if node[0] == 'operation':
                arity[len(node[2])] += 1
                operations += 1
                expected_resumes += len(node[2]) + 1
        prior_profile = sys.getprofile()
        sys.setprofile(profile)
        try:
            previous(columns, *a)
            program(columns, *b)
        finally:
            sys.setprofile(prior_profile)
        equal(a, b)
        checks += 1
assert counts['parent_generator_resumes'] == expected_resumes
assert counts['candidate_generator_resumes'] == 0

# Generic zero- and three-argument callables retain ordered argument dispatch.
for operands, function, expected in (((), lambda: 7., 7.),
                                    ((0, 1, 2), lambda a, b, c: a - b / c, 1.)):
    nodes = (('input', 0), ('input', 1), ('input', 2), ('operation', function, operands))
    destinations = ((), (), (), (('linear', 0, 0),))
    release = ((), (), (), (0, 1, 2, 3))
    a = [np.zeros((1, 1), dtype=np.complex128) for _ in range(2)]
    b = [np.zeros_like(x) for x in a]
    parent._Program(nodes, destinations, release)([3., 8., 4.], *a)
    new._Program(nodes, destinations, release)([3., 8., 4.], *b)
    equal(a, b)
    assert b[0][0, 0] == expected
    checks += 1
print(dict(program_checks=checks, operations=operations, arities=dict(arity),
           **counts, candidate_generator_resumes=counts['candidate_generator_resumes'],
           eliminated_generators=operations, scope='synthetic operation counts, no elapsed timing'))
