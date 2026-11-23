"""Read-only submission dossiers: exact source changes plus retained evidence.

Code mechanisms are editorial annotations, never line-level timing measurements.
Only the manifest's allowlisted local artifacts are read; no network or evaluator.
"""
from __future__ import annotations

import ast
import difflib
from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess

REPO_URL = 'https://github.com/timbtz/feyer-search-lab'
SHA = re.compile(r'[0-9a-f]{40}')


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                   stderr=subprocess.PIPE, timeout=15)


@lru_cache(maxsize=16)
def source_changes(repo, baseline, candidate):
    if not SHA.fullmatch(baseline) or not SHA.fullmatch(candidate):
        raise ValueError('Source revisions must be complete immutable SHAs')
    files = git(repo, 'diff', '--name-only', baseline, candidate, '--', 'differometor/').splitlines()
    result = []
    for path in files:
        if not path.startswith('differometor/') or not path.endswith('.py'):
            continue
        def read(sha):
            try:
                return git(repo, 'show', f'{sha}:{path}')
            except subprocess.CalledProcessError:
                # A newly added or deleted file has no blob on one side.
                if path not in git(repo, 'ls-tree', '-r', '--name-only', sha, '--', path).splitlines():
                    return ''
                raise
        before, after = read(baseline), read(candidate)
        old, new = before.splitlines(), after.splitlines()
        hunks = []
        added = removed = 0
        for group in difflib.SequenceMatcher(None, old, new, autojunk=False).get_grouped_opcodes(3):
            lines = []
            for tag, i, j, a, b in group:
                if tag == 'equal':
                    lines.extend(dict(kind='context', old=i+n+1, new=a+n+1, text=line)
                                 for n, line in enumerate(old[i:j]))
                else:
                    lines.extend(dict(kind='removed', old=n+1, new=None, text=old[n]) for n in range(i,j))
                    lines.extend(dict(kind='added', old=None, new=n+1, text=new[n]) for n in range(a,b))
                    removed += j-i
                    added += b-a
            hunks.append(dict(old_start=group[0][1]+1, new_start=group[0][3]+1, lines=lines))
        symbols = {}
        if after:
            for node in ast.parse(after).body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols[node.name] = dict(start=node.lineno, end=node.end_lineno)
        result.append(dict(path=path, added=added, removed=removed, hunks=hunks, symbols=symbols,
                           source_url=f'{REPO_URL}/blob/{candidate}/{path}',
                           baseline_url=f'{REPO_URL}/blob/{baseline}/{path}'))
    return result


def artifact(repo, relative):
    path = repo / relative
    if not path.resolve().is_relative_to((repo/'.lab').resolve()):
        raise ValueError('Evidence must stay within .lab')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink evidence is not read')
    if path.stat().st_size > 2_000_000:
        raise ValueError('Evidence exceeds 2 MB bound')
    if path.suffix == '.log':
        # Use the same redaction as other bounded dashboard logs.
        from .live_dashboard import tail
        data = tail(path, 12000)
    else:
        data = json.loads(path.read_text())
    return dict(path=relative, observed_at=path.stat().st_mtime, data=data,
                size_bytes=path.stat().st_size,
                truncated=path.suffix == '.log' and path.stat().st_size > 12000)


def submission_snapshot(repo):
    repo = Path(repo).resolve()
    manifest = repo/'experiments/submission/candidates.json'
    if not manifest.is_file():
        return dict(schema='feyer-submission-v1', candidates=[], selected_sha=None)
    spec = json.loads(manifest.read_text())
    candidates = []
    for entry in spec['candidates']:
        candidate = dict(entry)
        candidate['issues'] = []
        candidate['files'] = []
        try:
            candidate['files'] = source_changes(str(repo), spec['baseline_sha'], entry['sha'])
        except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as exc:
            candidate['issues'].append('Exact source unavailable: ' + type(exc).__name__)
        candidate['artifacts'] = []
        paths = set(entry.get('artifacts', []))
        for pattern in entry.get('artifact_globs', []):
            if not pattern.startswith('.lab/') or '..' in Path(pattern).parts:
                candidate['issues'].append('Invalid evidence pattern')
                continue
            paths.update(str(path.relative_to(repo)) for path in repo.glob(pattern))
        for relative in sorted(paths):
            try:
                row = artifact(repo, relative)
                data = row['data']
                identity = (data.get('candidate_sha') or data.get('sha') or
                            (data.get('source') or {}).get('commit')) if isinstance(data, dict) else None
                # Reference reports belong in the evidence archive, but are labelled.
                row['identity'] = identity
                row['identity_status'] = ('candidate' if identity == entry['sha'] else
                                          'reference' if identity == spec['baseline_sha'] else
                                          'different_revision' if identity else 'manifest_association')
                candidate['artifacts'].append(row)
            except (OSError, ValueError, TypeError) as exc:
                candidate['issues'].append(f'{relative}: unavailable ({type(exc).__name__})')
        candidates.append(candidate)
    return dict(schema='feyer-submission-v1', baseline_sha=spec['baseline_sha'],
                selected_sha=spec.get('selected_sha'), selection_status=spec.get('selection_status'),
                candidates=candidates)
