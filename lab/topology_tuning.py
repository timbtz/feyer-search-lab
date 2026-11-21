"""Reviewed finite tuning menus for an exact topology; no simulator execution.

Manifests are trusted coordinator-authored code transformations, not model output.
The full simulator source map binds observations to a rendered assignment.
"""
import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path, PurePosixPath

from .evolution_evidence import canonical_digest, normalize_job, policy_from_job

VERSION = 'exact-topology-finite-v1'
FAILURE_COST = 1_000_000.0


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def sources(repo, sha):
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Exact committed revision required')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args])
    names = git('ls-tree', '-r', '--name-only', sha, '--', 'differometor').decode().splitlines()
    return {name: git('show', sha + ':' + name).decode() for name in names if name.endswith('.py')}


def validate_manifest(manifest):
    if manifest['version'] != VERSION or not re.fullmatch(r'[0-9a-f]{40}', manifest['parent_sha']):
        raise ValueError('Invalid version or parent revision')
    if not manifest['base_sources'] or 'differometor/simulate.py' not in manifest['base_sources']:
        raise ValueError('Complete base simulator sources required')
    for path, source in manifest['base_sources'].items():
        p = PurePosixPath(path)
        if p.is_absolute() or '..' in p.parts or p.parts[0] != 'differometor' or p.suffix != '.py':
            raise ValueError('Transformation outside simulator Python source')
        if not isinstance(source, str):
            raise ValueError('Source must be text')
    if not 1 <= len(manifest['dimensions']) <= 6:
        raise ValueError('Bounded finite dimensions required')
    for name, values in manifest['dimensions'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', name) or not values or len(values) > 32:
            raise ValueError('Invalid dimension')
        if any(not isinstance(v, (str, int, bool, type(None))) for v in values):
            raise ValueError('Categorical JSON scalars required')
        if len(set(map(canonical, values))) != len(values):
            raise ValueError('Duplicate choices')
    legal = manifest['legal']
    if not legal or len(legal) > 4096 or len({canonical(p) for p in legal}) != len(legal):
        raise ValueError('Unique bounded legal menu required')
    for parameters in legal:
        if set(parameters) != set(manifest['dimensions']):
            raise ValueError('Complete parameter assignment required')
        for key, value in parameters.items():
            if canonical(value) not in list(map(canonical, manifest['dimensions'][key])):
                raise ValueError('Unregistered value')
    if manifest['defaults'] not in legal:
        raise ValueError('Default must be legal')
    seen = set()
    for parameters in legal:
        rendered = render(manifest, parameters)
        identity = canonical_digest({p: digest(s) for p, s in rendered.items()})
        if identity in seen:
            raise ValueError('Two assignments render identical simulator source')
        seen.add(identity)
    if render(manifest, manifest['defaults']) != manifest['base_sources']:
        raise ValueError('Defaults must reproduce exact parent')
    return canonical_digest(manifest)


def render(manifest, parameters):
    if canonical(parameters) not in {canonical(p) for p in manifest['legal']}:
        raise ValueError('Assignment is not in reviewed legal menu')
    result = dict(manifest['base_sources'])
    # Simultaneous replacement avoids order-dependent transformations.
    by_path = {}
    for rule in manifest['replacements']:
        if rule['dimension'] not in parameters or rule['path'] not in result:
            raise ValueError('Unknown replacement dimension or source')
        anchor = rule['anchor']
        if not anchor or result[rule['path']].count(anchor) != 1:
            raise ValueError('Replacement anchor must be unique in exact parent')
        keys = set(map(canonical, manifest['dimensions'][rule['dimension']]))
        if set(rule['values']) != keys:
            raise ValueError('Replacement must cover every registered value')
        replacement = rule['values'][canonical(parameters[rule['dimension']])]
        if not isinstance(replacement, str):
            raise ValueError('Replacement must be source text')
        start = result[rule['path']].index(anchor)
        by_path.setdefault(rule['path'], []).append((start, start + len(anchor), replacement))
    for path, changes in by_path.items():
        ordered = sorted(changes)
        if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Overlapping transformation anchors')
        for start, end, replacement in reversed(ordered):
            result[path] = result[path][:start] + replacement + result[path][end:]
        compile(result[path], path, 'exec')
    return result


def observations(manifest, jobs, seed_job, policy_context=None):
    """Only source-identical, same-cohort full evidence may train this topology."""
    validate_manifest(manifest)
    seed = normalize_job(seed_job, expected_sha=manifest['parent_sha'], policy_context=policy_context)
    if not seed['eligible_full']:
        raise ValueError('Parent requires an eligible exact full official and strict pass')
    policy = policy_from_job(seed_job, policy_context=policy_context)
    seed = normalize_job(seed_job, expected_sha=manifest['parent_sha'], policy_context=policy)
    base_hashes = {p: digest(s) for p, s in manifest['base_sources'].items()}
    if seed_job['report.json']['source']['simulator_files_sha256'] != base_hashes:
        raise ValueError('Parent full source differs from registered topology')
    menu = {canonical_digest({p: digest(s) for p, s in render(manifest, config).items()}): config
            for config in manifest['legal']}
    grouped, seen = {}, set()
    for job in [seed_job] + list(jobs):
        if job['id'] in seen:
            continue
        seen.add(job['id'])
        e = normalize_job(job, policy_context=policy)
        if e['profile'] != 'full' or e['cohort_digest'] != seed['cohort_digest']:
            continue
        if not e['eligible_full'] and e['category'] != 'invalid_candidate':
            continue
        hashes = job.get('report.json', {}).get('source', {}).get('simulator_files_sha256', {})
        key = canonical_digest(hashes)
        if key not in menu:
            continue
        grouped.setdefault(key, []).append((job, e))
    rows = []
    for key, items in grouped.items():
        invalid = any(e['category'] == 'invalid_candidate' for _, e in items)
        rows.append({'parameters': menu[key], 'status': 'invalid' if invalid else 'valid',
            'cost': FAILURE_COST if invalid else statistics.median(e['metrics']['total'] for _, e in items),
            'source_digest': key, 'job_ids': [j['id'] for j, _ in items],
            'commit_shas': [j['sha'] for j, _ in items]})
    return rows, seed['cohort_digest']


def verify_parent(repo, manifest):
    validate_manifest(manifest)
    if sources(repo, manifest['parent_sha']) != manifest['base_sources']:
        raise ValueError('Manifest source differs from exact Git parent')


def materialize(repo, manifest, parameters, branch, expected_head, campaign_id=None):
    """Only an explicitly owned clean branch may receive registered source edits."""
    verify_parent(repo, manifest)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    if git('branch', '--show-current') != branch or git('rev-parse', 'HEAD') != expected_head:
        raise ValueError('Owned branch moved')
    if git('status', '--porcelain'):
        raise ValueError('Owned worktree must be clean')
    changed = git('diff', '--name-only', manifest['parent_sha'], 'HEAD').splitlines()
    if campaign_id is not None and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', campaign_id):
        raise ValueError('Invalid campaign identity')
    prefix = 'experiments/campaigns/' + campaign_id + '/' if campaign_id else None
    if any(not (p in manifest['base_sources'] or p.startswith('experiments/notes/')
                or (prefix and p.startswith(prefix))) for p in changed):
        raise ValueError('Unexpected changes outside topology and notes')
    current = sources(repo, expected_head)
    if current not in [render(manifest, p) for p in manifest['legal']]:
        raise ValueError('Current source is not a registered topology assignment')
    target = render(manifest, parameters)
    for name, content in target.items():
        path = Path(repo) / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Simulator target must be a regular file')
    for name, content in target.items():
        if current[name] != content:
            (Path(repo) / name).write_text(content)
    return {p: digest(s) for p, s in target.items()}
