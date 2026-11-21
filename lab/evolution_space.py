"""Versioned finite implementation space, authored from the validated seed8.

This materializer never changes physical inputs or evaluator configuration. Every
non-seed assignment remains an experiment requiring fresh full validation.
"""
import hashlib
import itertools
import json
from pathlib import Path
import subprocess

SEED_SHA = '1e552d675c3795265be8af1ac23ffb61f90f30b1'
SOURCE_PATH = 'differometor/simulate.py'
SOURCE_SHA256 = '8225fedb4580e39fcc3f3611e73e4e356c7c0b55e4a3353486fcad9260d77c01'
SPACE_VERSION = 'seed8-component-execution-v1'
DIMENSIONS = {'checkpoint': [True, False], 'prevent_cse': [False, True],
              'map_batch_size': [None, 1, 2, 4, 8]}
DEFAULTS = {'checkpoint': True, 'prevent_cse': False, 'map_batch_size': None}
CHECKPOINT = '    branches = tuple(jax.checkpoint(function, prevent_cse=False) for function in FUNCTIONS)'
MAP = '        (function_indices, function_inputs),\n    )'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def validate(parameters):
    if not isinstance(parameters, dict) or set(parameters) != set(DIMENSIONS):
        raise ValueError('A complete registered parameter assignment is required')
    for name, choices in DIMENSIONS.items():
        if not any(type(parameters[name]) is type(x) and parameters[name] == x for x in choices):
            raise ValueError('Unregistered value for ' + name)
    if not parameters['checkpoint'] and parameters['prevent_cse']:
        raise ValueError('prevent_cse must remain false when checkpointing is disabled')
    return dict(parameters)


def materialize(source, parameters):
    parameters = validate(parameters)
    if hashlib.sha256(source.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Materializer requires the exact reviewed seed8 source')
    if source.count(CHECKPOINT) != 1 or source.count(MAP) != 1:
        raise ValueError('Registered transformation anchors are not unique')
    replacement = CHECKPOINT
    if not parameters['checkpoint']:
        replacement = '    branches = FUNCTIONS'
    elif parameters['prevent_cse']:
        replacement = CHECKPOINT.replace('prevent_cse=False', 'prevent_cse=True')
    result = source.replace(CHECKPOINT, replacement)
    if parameters['map_batch_size'] is not None:
        result = result.replace(MAP, '        (function_indices, function_inputs),\n'
            + '        batch_size=' + str(parameters['map_batch_size']) + ',\n    )')
    compile(result, SOURCE_PATH, 'exec')  # syntax only, never import candidate code here
    return result


def assignments(base=None, dimensions=None):
    base = validate(base or DEFAULTS)
    names = list(dimensions or DIMENSIONS)
    if set(names) - set(DIMENSIONS):
        raise ValueError('Unknown search dimensions')
    rows = []
    for values in itertools.product(*(DIMENSIONS[n] for n in names)):
        candidate = dict(base, **dict(zip(names, values)))
        try:
            rows.append(validate(candidate))
        except ValueError:
            pass
    return rows


def source_from_git(repo):
    return subprocess.check_output(['git', '-C', str(repo), 'show',
                                    SEED_SHA + ':' + SOURCE_PATH]).decode()


def content_identity(source):
    return hashlib.sha256(source.encode()).hexdigest()


def materialize_commit(repo, parameters, branch, expected_head, campaign_id=None):
    """Write to one owned clean worktree; fail if another writer moved its head."""
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    if git('branch', '--show-current') != branch or git('rev-parse', 'HEAD') != expected_head:
        raise ValueError('Owned branch/head changed before materialization')
    if git('status', '--porcelain'):
        raise ValueError('Materialization requires a clean worktree')
    # All non-target tracked files must still equal the reviewed seed. This is a
    # finite-space renderer, not a patch applicator for arbitrary parent code.
    import re
    if campaign_id is not None and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', campaign_id):
        raise ValueError('Invalid campaign identity')
    prefix = 'experiments/campaigns/' + campaign_id + '/' if campaign_id else None
    changed = set(git('diff', '--name-only', SEED_SHA, 'HEAD').splitlines())
    if any(name != SOURCE_PATH and not (prefix and name.startswith(prefix)) for name in changed):
        raise ValueError('Parent has tracked changes outside the source and owned campaign records')
    source = materialize(source_from_git(repo), parameters)
    path = Path(repo) / SOURCE_PATH
    if path.is_symlink() or not path.is_file():
        raise ValueError('Registered source must be a regular file, never a symlink')
    if path.read_text() == source:
        return {'sha': expected_head, 'content_sha256': content_identity(source), 'changed': False}
    path.write_text(source)
    git('add', '--', SOURCE_PATH)
    git('commit', '-m', 'Explore ' + SPACE_VERSION + ' ' + canonical(parameters))
    return {'sha': git('rev-parse', 'HEAD'), 'content_sha256': content_identity(source), 'changed': True}


def parse_recipe(content, allowed):
    """Allow one JSON fence, then require an exact menu choice; never run text."""
    import re
    if not isinstance(content, str) or len(content) > 16000:
        raise ValueError('Invalid recipe response')
    match = re.fullmatch(r'\s*```(?:json)?\s*\n(.*?)\n```\s*', content, re.S)
    recipe = json.loads(match.group(1) if match else content)
    if not isinstance(recipe, dict) or set(recipe) != {'choice', 'rationale'}:
        raise ValueError('Recipe must contain only choice and rationale')
    if type(recipe['choice']) is not int or not 0 <= recipe['choice'] < len(allowed):
        raise ValueError('Recipe choice is outside the supplied menu')
    if not isinstance(recipe['rationale'], str) or not 1 <= len(recipe['rationale']) <= 1200:
        raise ValueError('Recipe rationale is missing or too long')
    return validate(allowed[recipe['choice']]), recipe['rationale']
