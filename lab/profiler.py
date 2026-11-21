"""Rank existing evaluator timings without executing physics or changing evidence.

Shares refer to one measured first run. Halving estimates are Amdahl scenarios,
not predictions or measured improvements. No cross-run averaging is performed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import time

from .evolution_evidence import normalize_job
from .phase_report import GROUPS
from .worker import PHASE_CATEGORIES

SCHEMA = 'feyer-profiler-v1'
LIMITS = [
    'Phase timings do not attribute native operators or simulator source functions.',
    'Halving scenarios assume only that phase changes and all other work stays fixed; they are hypothetical.',
    'One report is one observation, not repeat-confirmed improvement.',
    'Warm runtime and worker wall time are separate from the first-run objective.',
    'Local artifact provenance is checked for consistency, not authenticated.',
]


def _number(value, positive=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0))


def _rank(values, total):
    rows, cumulative = [], 0.0
    for key, seconds in sorted(values.items(), key=lambda row: (-row[1], row[0])):
        share = seconds / total
        cumulative += share
        predicted = total - seconds / 2
        rows.append(dict(key=key, name=key, seconds=seconds, share=share,
                         cumulative_share=cumulative,
                         halving=dict(hypothetical=True, saved_seconds=seconds / 2,
                                      predicted_total_seconds=predicted,
                                      speedup=total / predicted)))
    return rows


def profile_job(job, source=None, instance=None):
    """Return visible invalid_report on malformed timings; never infer eligibility.

    Historical incomplete provenance may still yield useful phase rankings, with
    eligible_full=False and validation.issues explaining the missing evidence.
    """
    job = job if isinstance(job, dict) else {}
    def label(key):
        return job.get(key) if isinstance(job.get(key), str) else None
    out = dict(schema=SCHEMA, status='invalid_report', job_id=label('id'),
               candidate_sha=label('sha'), profile=label('profile'),
               execution_status=label('status'), instance=str(instance) if instance is not None else None,
               observed_at=next((job.get(k) for k in ('finished_at', 'updated_at', 'created_at')
                                 if _number(job.get(k))), None), source=str(source) if source is not None else None,
               eligible_full=False, cohort_digest=None,
               validation=dict(category='unverified', checks={}, issues=[]),
               first_run_seconds=None, phase_sum_seconds=None, unattributed_seconds=None,
               warm_timing={}, job_wall_seconds=None, phases=[], groups=[],
               issues=[], limits=list(LIMITS))
    if not isinstance(job.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', job['id']):
        out['issues'].append('Missing or malformed exact job ID')
    if not isinstance(job.get('sha'), str) or not re.fullmatch(r'[0-9a-f]{40}', job['sha']):
        out['issues'].append('Missing or malformed exact candidate SHA')
    if job.get('profile') not in ('screen', 'full'):
        out['issues'].append('Unknown evaluation profile')
    report = job.get('report.json')
    if not isinstance(report, dict):
        out['issues'].append('Missing timing report')
        return out
    reported_source = report.get('source')
    if not isinstance(reported_source, dict) or reported_source.get('commit') != job.get('sha'):
        out['issues'].append('Report source does not match the exact candidate SHA')
    timing = report.get('timing_seconds')
    if not isinstance(timing, dict):
        out['issues'].append('Missing timing_seconds object')
        return out
    total = timing.get('end_to_end')
    if not _number(total, positive=True):
        out['issues'].append('First-run total must be positive and finite')
    phases = report.get('phases')
    values = {}
    if not isinstance(phases, list):
        out['issues'].append('Missing phase list')
    else:
        for phase in phases:
            if not isinstance(phase, dict):
                out['issues'].append('Phase entry must be an object')
                continue
            key, seconds = phase.get('key'), phase.get('seconds')
            if not isinstance(key, str) or key not in PHASE_CATEGORIES:
                out['issues'].append('Unknown phase key')
                continue
            if key in values:
                out['issues'].append('Duplicate phase: ' + key)
            if not _number(seconds):
                out['issues'].append('Phase must have finite nonnegative seconds: ' + key)
            if phase.get('category') != PHASE_CATEGORIES[key]:
                out['issues'].append('Incorrect phase category: ' + key)
            values[key] = seconds
        missing = set(PHASE_CATEGORIES) - set(values)
        if missing:
            out['issues'].append('Missing phases: ' + ', '.join(sorted(missing)))
    warm = {}
    for key in ('runtime_median', 'runtime_min', 'runtime_max', 'runtime_samples', 'phase_runtime_medians'):
        if key not in timing:
            continue
        value = timing[key]
        if value is None:
            # Screen reports explicitly use null for unmeasured warm medians.
            warm[key] = None
            continue
        valid = (_number(value) if key in ('runtime_median', 'runtime_min', 'runtime_max') else
                 isinstance(value, list) and all(_number(v) for v in value) if key == 'runtime_samples' else
                 isinstance(value, dict) and all(isinstance(k, str) and _number(v) for k, v in value.items()))
        if not valid:
            out['issues'].append('Malformed warm timing: ' + key)
        else:
            warm[key] = json.loads(json.dumps(value))
    result = job.get('result')
    result = result if isinstance(result, dict) else {}
    wall = result.get('wall_seconds')
    if wall is not None and not _number(wall):
        out['issues'].append('Malformed worker wall timing')
    if out['issues']:
        return out
    phase_sum = math.fsum(values.values())
    residual = total - phase_sum
    # Float summation noise is not overlapping work; genuine overlap is invalid.
    if residual < -max(1e-9, total * 1e-10):
        out['issues'].append('Phase sum exceeds first-run total')
        return out
    out.update(status='ok', first_run_seconds=total, phase_sum_seconds=phase_sum,
               unattributed_seconds=max(0.0, residual), warm_timing=warm,
               job_wall_seconds=wall, phases=_rank(values, total),
               groups=_rank({name: math.fsum(values[key] for key in keys)
                             for name, keys in GROUPS.items()}, total))
    try:
        evidence = normalize_job(job)
        out.update(eligible_full=evidence['eligible_full'], cohort_digest=evidence['cohort_digest'],
                   validation={key: evidence[key] for key in ('category', 'checks', 'issues')})
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        out['validation']['issues'].append(str(exc))
    return out


def feedback_profile(feedback):
    """Profile both screen and full separately, retaining failed full evidence."""
    if not isinstance(feedback, dict):
        return dict(schema='feyer-profiler-feedback-v1', candidate_sha=None, jobs=[],
                    issues=['Feedback must be an object'])
    profiles = []
    for key in ('screen', 'full'):
        if key in feedback:
            item = profile_job(feedback[key], source='feedback.' + key)
            if feedback.get('candidate_sha') and item['candidate_sha'] != feedback['candidate_sha']:
                item.update(status='invalid_report', eligible_full=False, phases=[], groups=[])
                item['issues'].append('Feedback candidate SHA differs from job SHA')
            profiles.append(item)
    return dict(schema='feyer-profiler-feedback-v1', candidate_sha=feedback.get('candidate_sha'),
                jobs=profiles, issues=[] if profiles else ['No screen or full jobs in feedback'])


def _read(path):
    with path.open() as stream:
        return json.load(stream)


def _artifact_job(path):
    job = _read(path)
    if not isinstance(job, dict):
        raise ValueError('Job must be an object')
    for filename, key in (('result.json', 'result'), ('report.json', 'report.json'),
                          ('comparison.json', 'comparison.json')):
        artifact = path.with_name(filename)
        if artifact.is_file():
            job[key] = _read(artifact)
    result = job.get('result')
    # job.json is captured when execution begins; result.json is its terminal receipt.
    if isinstance(result, dict):
        if result.get('sha') != job.get('sha') or result.get('profile') != job.get('profile'):
            raise ValueError('Result receipt identity differs from archived job')
        job['status'] = result.get('status')
    return job


def collect_profiles(repo, worktrees=True):
    """Read local trusted-artifact locations; no SSH, queue or Git writes.

    Conflicting copies of a terminal job are reported, never arbitrarily averaged.
    """
    repo = Path(repo).resolve()
    roots, issues, copies = {repo}, [], {}
    if worktrees:
        try:
            listing = subprocess.check_output(['git', '-C', str(repo), 'worktree', 'list', '--porcelain'],
                                              text=True, stderr=subprocess.PIPE, timeout=10)
            roots.update(Path(line[9:]) for line in listing.splitlines() if line.startswith('worktree '))
        except (OSError, subprocess.SubprocessError) as exc:
            issues.append('Worktree discovery unavailable: ' + type(exc).__name__)
    paths = set()
    for pattern in ('.lab/phase-ledger/*.json', '.lab/campaigns/*/queue-results/*.json',
                    '.lab/sessions/*/results/*/job.json'):
        paths.update(repo.glob(pattern))
    for root in roots:
        paths.update(root.glob('experiments/runs/*/candidate-*.json'))
    for path in sorted(paths):
        try:
            if path.is_symlink():
                raise ValueError('Symlink evidence file is not read')
            data = _artifact_job(path) if path.name == 'job.json' else _read(path)
            if not isinstance(data, dict):
                raise ValueError('Evidence file must be an object')
            jobs = [data] if 'id' in data else [data[key] for key in ('screen', 'full') if key in data]
            if not jobs:
                raise ValueError('No job records found')
            for job in jobs:
                report = profile_job(job, source=str(path))
                identity = report['job_id']
                if not isinstance(identity, str):
                    issues.append(str(path) + ': missing job identity')
                    continue
                # Compare the scientific receipt, not differing log tails or timestamps.
                receipt = {k: job.get(k) for k in ('sha', 'profile', 'status', 'result', 'report.json', 'comparison.json')}
                signature = json.dumps(receipt, sort_keys=True, allow_nan=True)
                has_report = isinstance(job.get('report.json'), dict)
                copies.setdefault(identity, []).append((report, signature, has_report))
        except (OSError, ValueError, TypeError) as exc:
            issues.append(str(path) + ': ' + str(exc))
    reports = []
    for identity, observations in sorted(copies.items()):
        # Incomplete earlier queue snapshots may coexist with a terminal receipt.
        complete = [x for x in observations if x[0]['status'] == 'ok']
        choices = complete or observations
        report = choices[0][0]
        scientific_copies = [x for x in observations if x[2]] or observations
        identities = {(x[0]['candidate_sha'], x[0]['profile']) for x in observations}
        if len({x[1] for x in scientific_copies}) > 1 or len(identities) > 1:
            report.update(status='conflicting_artifacts', eligible_full=False)
            report['issues'].append('Conflicting artifacts share this job ID; manual review required')
        report['sources'] = sorted({x[0]['source'] for x in observations})
        for invalid, _, _ in observations:
            if invalid is not report and invalid['status'] == 'invalid_report':
                issues.append(invalid['source'] + ': ' + '; '.join(invalid['issues']))
        reports.append(report)
    return dict(schema='feyer-profiler-collection-v1', generated_at=time.time(), profiler_reports=reports, issues=issues,
                limits=['Runs are not pooled across candidates, instances or cohorts.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--repo', type=Path, default=Path.cwd())
    source.add_argument('--job', type=Path, help='One raw queue job JSON or archived job.json')
    source.add_argument('--feedback', type=Path, help='One supervisor candidate feedback JSON')
    parser.add_argument('--no-worktrees', action='store_true')
    parser.add_argument('--output', type=Path, help='Write JSON here instead of stdout')
    parser.add_argument('--watch', type=float, help='Refresh a local collection every N seconds (at least 5)')
    args = parser.parse_args()
    if args.watch is not None and (not math.isfinite(args.watch) or args.watch < 5
                                   or not args.output or args.job or args.feedback):
        parser.error('--watch needs --output, repository collection, and a finite interval >= 5 seconds')
    while True:
        if args.job:
            job = _artifact_job(args.job) if args.job.name == 'job.json' else _read(args.job)
            value = profile_job(job, source=str(args.job))
        elif args.feedback:
            value = feedback_profile(_read(args.feedback))
        else:
            value = collect_profiles(args.repo, worktrees=not args.no_worktrees)
        payload = json.dumps(value, indent=2, allow_nan=False) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=args.output.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            try:
                temporary.replace(args.output)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            print(payload, end='')
        if args.watch is None:
            break
        time.sleep(args.watch)


if __name__ == '__main__':
    main()
