"""Run only the actual builder scheduling/registry blocks, without JAX imports."""
import ast
from pathlib import Path
import textwrap
import unittest

SOURCE = (Path(__file__).resolve().parents[2] / 'differometor/build.py').read_text()


def schedule(pairs, changing, instructions, names, signal_components=()):
    start = SOURCE.index('    # Compile optimized parameter indices and include')
    end = SOURCE.index('    def combine_arrays(', start)
    env = dict(optimization_pairs=pairs, changing_pairs=changing,
               parameter_instructions=instructions, parameter_names=names,
               signal_components=signal_components, optimized_parameter_indices=[],
               optimization_value_indices=[], carrier_components=[], carrier_arrays={},
               carrier_changing_parameter_indices=[], signal_changing_parameter_indices=[])
    def append_information(ins, arrays, component, components):
        if component not in components:
            components.append(component)
    env['append_information'] = append_information
    exec(compile(textwrap.dedent(SOURCE[start:end]), '<actual-builder-scheduling>', 'exec'), env)
    return env


class GeneralBuilderRegression(unittest.TestCase):
    def test_grouped_members_all_scheduled_and_share_value(self):
        ins = {'a': {'function_input_indices': [[0]]}, 'b': {'function_input_indices': [[1]]}}
        e = schedule([[['a', 'x'], ['b', 'x']]], [], ins, ['a_x', 'b_x'])
        self.assertEqual(e['carrier_components'], ['a', 'b'])
        self.assertEqual(e['optimized_parameter_indices'], [0, 1])
        self.assertEqual(e['optimization_value_indices'], [0, 0])

    def test_foreign_parameter_reader_scheduled_without_value_test(self):
        ins = {'owner': {'function_input_indices': [[0]]},
               'surface': {'function_input_indices': [[0, 1]]},
               'unrelated': {'function_input_indices': [[1]]}}
        e = schedule([['owner', 'n']], [], ins, ['owner_n', 'other_x'])
        self.assertEqual(e['carrier_components'], ['owner', 'surface'])

    def test_carrier_sweep_readers_but_not_signal_only_sweep(self):
        ins = {'owner': {'function_input_indices': [[0]]}, 'reader': {'function_input_indices': [[0]]}}
        e = schedule([], [['owner', 'x']], ins, ['owner_x'])
        self.assertEqual(e['carrier_components'], ['owner', 'reader'])
        signal = schedule([], [['owner', 'x']], ins, ['owner_x'], ['owner'])
        self.assertEqual(signal['carrier_components'], [])

    def test_identity_registry_after_nonidentity_and_repeated_build(self):
        tree = ast.parse(SOURCE)
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {'identity_link', '_identity_link_index'}]
        registry = [lambda x: x + 7]
        env = {'LINKING_FUNCTIONS': registry}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<actual-identity>', 'exec'), env)
        first = env['_identity_link_index']()
        self.assertEqual(first, 1)
        self.assertEqual(registry[first](3), 3)
        self.assertEqual(env['_identity_link_index'](), first)
        self.assertEqual(len(registry), 2)
        self.assertIn('linking_function_indices = [_identity_link_index()]', SOURCE)


if __name__ == '__main__':
    unittest.main()
