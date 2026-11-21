"""Read-only, guided-search evidence feed. Never dispatches or promotes candidates."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .evolution_evidence import normalize_job
from .phase_report import GROUPS
from .research_lineage import digest, exact_sha
from .queue import TERMINAL_STATUSES

SCHEMA = 'feyer-search-frontier-v1'
MAX_BYTES = 256 * 1024
OBJECTIVES = ['total', *GROUPS]


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def comparison_context(job, team):
    """Classify recorded execution intervals, never current import time.

    No implicit quiet epoch exists before the first recorded transition. A run
    crossing transitions or missing timestamps remains unranked.
    """
    start, end = job.get('started_at'), job.get('finished_at')
    if not all(number(x) for x in (start, end)) or end < start:
        return {'mode': 'unknown', 'epoch': None}
    transitions = [dict(e['data'], changed_at=e['at'], epoch=e['seq'])
                   for e in team.get('events', []) if e.get('command') == 'comparison-regime']
    transitions.sort(key=lambda r: r['changed_at'])
    active = [r for r in transitions if r['changed_at'] <= start]
    if not active or any(start < r['changed_at'] <= end for r in transitions):
        return {'mode': 'unknown', 'epoch': None}
    r = active[-1]
    return {k: r.get(k) for k in ('mode', 'epoch', 'receipt')}


def published_feedback(root, path, feedback):
    """Require an exact feedback blob in an already-known origin branch.

    Never fetch, read an independent prompt, or inspect uncommitted source code.
    A missing/stale remote-tracking receipt means unavailable until refresh.
    """
    job = feedback.get('full') or {}
    branch = job.get('branch')
    if job.get('status') not in TERMINAL_STATUSES or not isinstance(branch, str):
        return None
    try:
        commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--verify',
            'refs/remotes/origin/' + branch], text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
        relative = path.relative_to(root).as_posix()
        saved = subprocess.check_output(['git', '-C', str(root), 'show', commit + ':' + relative],
            text=True, stderr=subprocess.DEVNULL, timeout=10)
        if exact_sha(commit) and json.loads(saved) == feedback:
            return 'git:' + commit + ':' + relative
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def collect(repo, team, instance, policies):
    """Read allowlisted artifact paths only. Caller explicitly assigns the host.

    Per-CPU policy overrides come from a separate coordinator-owned manifest,
    never from a candidate's request. No credentials or raw prompts are read.
    """
    repo = Path(repo).resolve()
    entries, issues = [], []
    records = team.get('research_records', {}).values()
    excluded = {'astra-independent-v1'} | {r['executor']['id'] for r in records
        if r.get('own_feedback_only') or r.get('feedback_mode') == 'evidence-only'}

    def add(job, source, owner=None, context=None, assigned_instance=None, published_independent=False):
        if not isinstance(job, dict) or job.get('profile') not in ('screen', 'full'):
            return
        labels = [owner, job.get('agent'), job.get('branch')]
        if not published_independent and any(any(x in str(label or '') for x in excluded) for label in labels):
            return
        # Strip logs and unrelated queue fields before hashing or publication.
        raw = {k: job[k] for k in ('id', 'sha', 'profile', 'status', 'started_at',
               'finished_at', 'result', 'report.json', 'comparison.json') if k in job}
        cpu = (raw.get('result') or {}).get('cpu')
        actual_context = comparison_context(raw, team)
        if context and (context.get('mode'), context.get('epoch')) != (actual_context.get('mode'), actual_context.get('epoch')):
            actual_context = {'mode':'unknown', 'epoch':None}
        entries.append(dict(job=raw, instance=assigned_instance or instance,
            executor=owner or job.get('agent') or 'unattributed', source_ref=source,
            comparison_context=actual_context,
            policy_context=policies.get(str(cpu))))

    observations = team.get('observations', [])
    for obs in observations.values() if isinstance(observations, dict) else observations:
        provenance = obs.get('provenance', {})
        source = ('{repository}/blob/{commit}/{path}'.format(**provenance)
                  if all(k in provenance for k in ('repository', 'commit', 'path')) else 'team-ledger')
        add(obs.get('job'), source, context=obs.get('comparison_context'), assigned_instance=obs.get('instance'))
    paths = set(repo.glob('.lab/phase-ledger/*.json'))
    paths.update(repo.glob('.lab/campaigns/*/queue-results/*.json'))
    roots = {repo}
    listing = subprocess.check_output(['git', '-C', str(repo), 'worktree', 'list', '--porcelain'], text=True)
    roots.update(Path(line[9:]) for line in listing.splitlines() if line.startswith('worktree '))
    feedback_roots = {}
    for root in roots:
        for path in root.glob('experiments/runs/*/candidate-*.json'):
            paths.add(path)
            feedback_roots[path] = root
    for path in sorted(paths):
        try:
            if path.is_symlink():
                raise ValueError('Symlink evidence excluded')
            raw = json.loads(path.read_text())
            source = str(path.relative_to(repo)) if path.is_relative_to(repo) else 'worktree/' + str(path.relative_to(path.parents[3]))
            if 'candidate_sha' in raw:
                independent = any(x in path.parts for x in excluded)
                if independent:
                    published = published_feedback(feedback_roots[path], path, raw)
                    if published:
                        add(raw.get('full'), published, path.parent.name, published_independent=True)
                    continue
                for profile in ('screen', 'full'):
                    add(raw.get(profile), source, path.parent.name)
            else:
                owner = path.parents[1].name if 'queue-results' in path.parts else None
                add(raw, source, owner)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            issues.append(f'{path.name}: {type(exc).__name__}')
    return entries, issues


def build_frontier(entries, records=(), generated_at=None, source_provenance=None, limit=8):
    """Observed job-level Pareto points; no averaging, significance or final winner."""
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError('Limit must be between 1 and 16')
    copies, issues, failures, points, conflicts = {}, [], [], [], set()
    for entry in entries:
        job = entry['job']
        if job.get('status') not in TERMINAL_STATUSES or job.get('profile') != 'full':
            continue
        key = (entry.get('instance'), job.get('id'))
        copies.setdefault(key, []).append(entry)
    for key, rows in sorted(copies.items(), key=lambda pair: str(pair[0])):
        row, job = rows[0], rows[0]['job']
        item = dict(instance=key[0], job_id=key[1], candidate_sha=job.get('sha'),
                    sources=sorted({r['source_ref'] for r in rows}),
                    executors=sorted({r.get('executor', 'unattributed') for r in rows}))
        try:
            scientific = {digest({k: r['job'].get(k) for k in
                ('sha', 'profile', 'status', 'started_at', 'finished_at', 'result', 'report.json', 'comparison.json')}) for r in rows}
            if len(scientific) != 1:
                conflicts.update((key[0], r['job'].get('sha')) for r in rows)
                raise ValueError('Conflicting terminal artifacts for exact job identity')
            policies = {digest(r.get('policy_context')) for r in rows}
            if len(policies) != 1:
                conflicts.update((key[0], r['job'].get('sha')) for r in rows)
                raise ValueError('Conflicting authorized policies')
            evidence = normalize_job(job, policy_context=row.get('policy_context'))
            item.update(category=evidence['category'], checks=evidence['checks'],
                cohort_digest=evidence['cohort_digest'], artifact_digest=evidence['artifact_digest'])
            contexts = [r.get('comparison_context') or {} for r in rows]
            known = [c for c in contexts if c.get('mode') in ('serial', 'concurrent') and type(c.get('epoch')) is int]
            identities = {(c['mode'], c['epoch']) for c in known}
            item['comparison_context'] = known[0] if len(identities) == 1 and len(known) == len(contexts) else {'mode':'unknown', 'epoch':None}
            if not evidence['eligible_full']:
                item['issues'] = evidence['issues']
                failures.append(item)
                continue
            item.update(metrics={k:evidence['metrics'][k] for k in OBJECTIVES},
                        phases=evidence['phases'], qualification='single_full_valid_observation')
            points.append(item)
        except (ValueError, TypeError, KeyError) as exc:
            failures.append(dict(item, category='unverified', issues=[str(exc)]))

    # A valid rerun cannot hide a scientific failure for the same source/cohort.
    blocked = {(f['instance'], f.get('cohort_digest'), f['candidate_sha']) for f in failures
               if f.get('category') == 'invalid_candidate'}
    for p in points[:]:
        if ((p['instance'], p['candidate_sha']) in conflicts or
            any(p['instance'] == i and p['candidate_sha'] == s and
                (c is None or p['cohort_digest'] == c) for i, c, s in blocked)):
            points.remove(p)
            failures.append(dict(p, category='numerical_review_required'))

    grouped, unranked = {}, []
    for p in points:
        ctx = p['comparison_context']
        if not p['instance'] or not p['cohort_digest'] or ctx['mode'] == 'unknown':
            unranked.append(p)
            continue
        group = (p['instance'], p['cohort_digest'], ctx['mode'], ctx['epoch'])
        grouped.setdefault(group, []).append(p)
    groups = []
    for key, samples in sorted(grouped.items()):
        def dominates(a, b):
            return (all(a['metrics'][k] <= b['metrics'][k] for k in OBJECTIVES)
                    and any(a['metrics'][k] < b['metrics'][k] for k in OBJECTIVES))
        ordered = sorted(samples, key=lambda p:(p['metrics']['total'], p['candidate_sha'], p['job_id']))
        frontier = [p for p in ordered if not any(dominates(q, p) for q in samples)]
        best = {}
        for p in ordered:
            for owner in p['executors']:
                if owner != 'unattributed':
                    best.setdefault(owner, p)
        groups.append(dict(instance=key[0], cohort_digest=key[1],
            comparison_context=dict(mode=key[2], epoch=key[3]), observation_count=len(samples),
            observed_frontier=frontier[:limit], frontier_count=len(frontier),
            frontier_omitted=max(0, len(frontier)-limit), own_best_observed=best,
            qualification='exploratory_only; quiet serial confirmation required for promotion'))
    combinations = [{k:r.get(k) for k in ('record_id','candidate_sha','parents','hypothesis','source_ref','source_digest')}
                    for r in records if r.get('kind') == 'combine' and exact_sha(r.get('candidate_sha'))]
    result = dict(schema=SCHEMA, generated_at=time.time() if generated_at is None else generated_at,
        source_provenance=source_provenance or {}, objectives=OBJECTIVES, groups=groups,
        unranked=unranked[:limit], unranked_count=len(unranked), unranked_omitted=max(0,len(unranked)-limit),
        failures=failures[:32], failure_count=len(failures), failures_omitted=max(0,len(failures)-32),
        declared_combinations=combinations, issues=issues,
        limits=['Guided sessions only; never deliver this feed to independent/evidence-only sessions.',
            'Observed Pareto membership and own best refer to individual full-valid jobs, not confirmed gains.',
            'Groups are incomparable across instance, cohort or regime epoch. Unknown context remains unranked.',
            'No automatic source merge, scheduling, budget change, stopping decision or promotion.',
            'Phase complementarity motivates an experiment; it does not prove changes compose.',
            'Sources are trusted local/coordinator artifacts, not cryptographic attestations.'])
    if not number(result['generated_at']) or result['generated_at'] <= 0:
        raise ValueError('Invalid generation timestamp')
    result['content_digest'] = digest(result)
    if len(json.dumps(result, separators=(',', ':'), allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError('Frontier exceeds 256 KiB; reduce limit or input scope')
    return result


def temporary_bytes(directory, data):
    """Remove a partial temporary file if disk write or flush fails."""
    path = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            path = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    return path


def write_snapshot(result, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(result, separators=(',', ':'), allow_nan=False).encode()
    if len(data) > MAX_BYTES or digest({k:v for k,v in result.items() if k != 'content_digest'}) != result['content_digest']:
        raise ValueError('Invalid snapshot size or content digest')
    archive = output.parent / 'artifacts' / (result['content_digest'] + '.json')
    archive.parent.mkdir(exist_ok=True)
    if archive.exists() and archive.read_bytes() != data:
        raise ValueError('Immutable snapshot conflict')
    if not archive.exists():
        temporary_archive = temporary_bytes(archive.parent, data)
        try:
            # Atomic exclusive publication: neither partial immutable files nor
            # a second writer can replace a content-addressed artifact.
            try:
                os.link(temporary_archive, archive)
            except FileExistsError:
                if archive.read_bytes() != data:
                    raise ValueError('Immutable snapshot conflict')
        finally:
            temporary_archive.unlink()
    temporary = temporary_bytes(output.parent, data)
    try:
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return archive


def refresh_loop(refresh, interval=None, deadline=None, clock=time.time, sleep=time.sleep):
    """Retry filesystem errors only in bounded watch mode; keep old good output.

    Semantic errors still propagate. A retry is a new collection attempt, never
    a rewritten timestamp on the previous snapshot.
    """
    if interval is None:
        return refresh()
    if not number(interval) or not 5 <= interval <= 60 or not number(deadline):
        raise ValueError('Refresh needs a finite 5..60 second interval and deadline')
    while clock() < deadline:
        try:
            refresh()
        except OSError as exc:
            try:
                print(json.dumps({'event':'frontier_refresh_failed', 'error':str(exc),
                    'publication_status':'unknown', 'deadline_unix':deadline}), file=sys.stderr, flush=True)
            except OSError:
                # The log may be on the same full filesystem. Preserve the
                # bounded retry even when recording the failure is impossible.
                pass
        remaining = deadline - clock()
        if remaining > 0:
            sleep(min(interval, remaining))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--team-state', type=Path, required=True)
    p.add_argument('--instance', required=True, help='Explicit physical host identity for local artifact corpus')
    p.add_argument('--policies', type=Path, help='Coordinator-approved JSON: CPU string -> policy context')
    p.add_argument('--policy-source', help='Immutable source receipt authorizing policy overrides')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--limit', type=int, default=8)
    p.add_argument('--watch-seconds', type=float, help='Optional bounded read-only refresh interval (5..60 seconds)')
    p.add_argument('--until-unix', type=float, help='Required fixed deadline when refreshing repeatedly')
    args = p.parse_args()
    if args.policies and not args.policy_source:
        p.error('--policies requires --policy-source')
    if args.watch_seconds is not None and (not number(args.watch_seconds) or not 5 <= args.watch_seconds <= 60
            or not number(args.until_unix) or args.until_unix <= time.time()):
        p.error('Refresh needs an interval of 5..60 seconds and a future fixed deadline')
    def refresh():
        team = json.loads(args.team_state.read_text())
        policies = json.loads(args.policies.read_text()) if args.policies else {}
        entries, issues = collect(args.repo, team, args.instance, policies)
        provenance = dict(team_digest=digest(team), policy_digest=digest(policies),
            policy_source_ref=args.policy_source, evidence_digest=digest(entries),
            collector='trusted-local-artifacts-v1', instance=args.instance)
        result = build_frontier(entries, team.get('research_records', {}).values(), source_provenance=provenance, limit=args.limit)
        result['issues'].extend(issues)
        result.pop('content_digest')
        result['content_digest'] = digest(result)
        archive = write_snapshot(result, args.output)
        print(json.dumps(dict(path=str(args.output), archive=str(archive), groups=len(result['groups']),
            unranked=result['unranked_count'], failures=result['failure_count'], issues=result['issues'])), flush=True)
    refresh_loop(refresh, args.watch_seconds, args.until_unix)


if __name__ == '__main__':
    main()
