"""Build and source-check the exact Astra compiler-boundary menu; no physics runs."""
import ast
import json
from pathlib import Path
from lab.topology_tuning import VERSION, sources, render, validate_manifest

PARENT = 'd947905c9b73e310257235cf00cb065c31572ecd'
PATH = 'differometor/simulate.py'
GROUP = '@partial(jit, static_argnums=(0,), inline=True)'
CHECKPOINT = '@partial(jax.checkpoint, static_argnums=(0,), prevent_cse=False, policy=_save_assembly_indices)'


def manifest(repo):
    source = sources(repo, PARENT)
    result = {'version': VERSION, 'parent_sha': PARENT, 'base_sources': source,
        'dimensions': {'group_inline': [True, False], 'group_checkpoint': ['existing', 'cse_barrier', 'disabled']},
        'defaults': {'group_inline': True, 'group_checkpoint': 'existing'},
        'legal': [{'group_inline': inline, 'group_checkpoint': checkpoint}
                  for inline in [True, False] for checkpoint in ['existing', 'cse_barrier', 'disabled']],
        'replacements': [
            {'path': PATH, 'dimension': 'group_inline', 'anchor': GROUP,
             'values': {'true': GROUP, 'false': GROUP.replace('inline=True', 'inline=False')}},
            {'path': PATH, 'dimension': 'group_checkpoint', 'anchor': CHECKPOINT,
             'values': {'"existing"': CHECKPOINT, '"cse_barrier"': CHECKPOINT.replace('prevent_cse=False', 'prevent_cse=True'), '"disabled"': ''}}],
        'scientific_parents': [PARENT],
        'target_phases': ['gradient_compile', 'forward_compile', 'gradient', 'forward'],
        'scope': 'Only two decorators change; all function bodies, solver order, assembly topology and physical workload fixed.',
        'comparison_context': 'CPU34 own seed and cohort, exploratory concurrent epoch; no CPU2 timing import.'}
    validate_manifest(result)
    original = ast.parse(source[PATH])
    def without_target_decorators(tree):
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in ('_evaluate_component_group', '_component_values'):
                node.decorator_list = []
        return ast.dump(tree, include_attributes=False)
    expected = without_target_decorators(original)
    for parameters in result['legal']:
        rendered = render(result, parameters)
        assert all(rendered[p] == source[p] for p in source if p != PATH)
        assert without_target_decorators(ast.parse(rendered[PATH])) == expected
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = manifest(args.repo)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'parent': PARENT, 'legal': len(result['legal']), 'manifest_digest': validate_manifest(result), 'ast_body_equivalence': True}))
