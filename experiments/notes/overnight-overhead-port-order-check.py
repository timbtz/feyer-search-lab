"""Check unused-port instruction determinism across synthetic process hash seeds.

Runs only the AST-extracted unused-port loop with captured instructions; no
simulation or timing. Default uses list stand-ins for array construction.
--numpy additionally checks the captured instructions with actual NumPy arrays.
The hash seed varies only for these tiny inspection subprocesses, never for an
official evaluation or shared launch environment.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'dbb5b6e70ad66af83f2fa3f6c7f1ff2ca016ca8f'


def capture(parent=False, with_numpy=False, empty=False):
    source = (subprocess.check_output(['git', 'show', PARENT + ':differometor/build.py'],
                                     cwd=ROOT, text=True) if parent else
              (ROOT / 'differometor/build.py').read_text())
    tree = ast.parse(source)
    build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
    loop = next(n for n in build.body if isinstance(n, ast.For)
                and isinstance(n.target, ast.Name) and n.target.id == 'node_port')
    ports = next(n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'PORT_DICTS' for t in n.targets))
    nodes = {'m1': {'component': 'mirror'}, 'm2': {'component': 'mirror'},
             'b1': {'component': 'beamsplitter'}, 'b2': {'component': 'beamsplitter'}}
    positions = {'m1': 0, 'm2': 4, 'b1': 8, 'b2': 16}
    all_ports = {name + '.' + port for name, data in nodes.items()
                 for port in (('left', 'right') if data['component'] == 'mirror'
                              else ('left', 'right', 'top', 'bottom'))}
    used = set(all_ports) if empty else {'m1.right', 'b1.top', 'b2.bottom'}
    result = {}

    def record(instructions, key, **kwargs):
        instructions[key] = kwargs

    np = SimpleNamespace(array=lambda x: x)
    if with_numpy:
        import numpy as np
    vacuum = object()
    ns = dict(all_ports=all_ports, used_ports=used, setup=SimpleNamespace(nodes=nodes),
              matrix_positions=positions, noise_instructions=result,
              np=np, FUNCTIONS=[vacuum], vacuum_quantum_noise=vacuum,
              set_instructions=record, system_size=24)
    exec(compile(ast.Module(body=[ports, loop], type_ignores=[]), '<unused-port loop>', 'exec'), ns)
    # Independent expected coordinates from the supplied graph, including columns.
    expected = {'m1.left': 0, 'm2.left': 4, 'm2.right': 6, 'b1.left': 8,
                'b1.right': 12, 'b1.bottom': 14, 'b2.left': 16, 'b2.right': 20,
                'b2.top': 18}
    if empty:
        expected = {}
    assert set(result) == set(expected)
    for key, info in result.items():
        assert list(info['system_matrix_row_indices']) == [expected[key]]
        assert list(info['system_matrix_column_indices']) == [expected[key]]
        assert list(info['output_column_indices']) == [0]
        assert list(info['function_indices']) == [0]
        assert info['system_size_for_sidebands'] == 24
    if not parent:
        assert list(result) == sorted(expected)
    # Compare all arguments passed to the unchanged instruction constructor.
    def plain(v):
        return v.tolist() if hasattr(v, 'tolist') else v
    return {key: {field: plain(value) for field, value in info.items()}
            for key, info in result.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--numpy', action='store_true')
    args = parser.parse_args()
    if args.child:
        parent, candidate = capture(True, args.numpy), capture(False, args.numpy)
        assert parent == candidate  # dict equality ignores insertion order
        assert capture(False, args.numpy, empty=True) == {}
        print(json.dumps({'parent_order': list(parent), 'candidate_order': list(candidate),
                          'instructions': candidate}, sort_keys=True))
        return
    outputs = []
    for seed in range(8):
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        cmd = [sys.executable, str(Path(__file__).resolve()), '--child']
        if args.numpy:
            cmd.append('--numpy')
        outputs.append(json.loads(subprocess.check_output(cmd, cwd=ROOT, env=env, text=True)))
    parent_orders = {tuple(x['parent_order']) for x in outputs}
    candidate_orders = {tuple(x['candidate_order']) for x in outputs}
    assert len(parent_orders) > 1, 'Counterexample did not vary across inspected seeds'
    assert len(candidate_orders) == 1
    assert all(x['instructions'] == outputs[0]['instructions'] for x in outputs)
    print(f'PASS: {len(outputs)} synthetic hash seeds; {len(parent_orders)} parent orders, '
          f'{len(candidate_orders)} candidate order; all instruction arguments unchanged')
    print('Actual NumPy checked' if args.numpy else 'Stdlib only; no NumPy/JAX or optical check')


if __name__ == '__main__':
    main()
