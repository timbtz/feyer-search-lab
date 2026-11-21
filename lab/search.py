"""Export committed experiment evidence for a new agent; never merge or evaluate."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import statistics
import subprocess

from .phase_report import GROUPS, dominates, metrics, signature

SHA = re.compile(r'^[0-9a-f]{40}$')
BASELINE_SHA = '02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f'


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                   stderr=subprocess.PIPE).strip()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def committed_documents(repo, refs=None):
    """Read branch tips, not dirty worktree files; identical documents retain all origins."""
    refs = refs or git(repo, 'for-each-ref', '--format=%(refname)',
                       'refs/heads', 'refs/remotes').splitlines()
    documents = {}
    for ref in sorted(set(refs)):
        tip = git(repo, 'rev-parse', '--verify', ref + '^{commit}')
        paths = git(repo, 'ls-tree', '-r', '--name-only', tip, '--',
                    'experiments/agents', 'experiments/runs').splitlines()
        for path in paths:
            if not path.endswith('.json'):
                continue
            raw = git(repo, 'show', tip + ':' + path)
            data = json.loads(raw)
            key = (path, digest(data))
            document = documents.setdefault(key, {'path': path, 'data': data, 'origins': []})
            document['origins'].append({'ref': ref, 'commit': tip})
    return list(documents.values())


def run_evidence(job):
    result = job.get('result') or {}
    report = job.get('report.json') or {}
    comparison = job.get('comparison.json') or {}
    official, strict = result.get('official_passed'), comparison.get('passed')
    if strict is None:
        strict = result.get('regression_passed')
    row = {'id': job.get('id'), 'profile': job.get('profile'), 'status': job.get('status'),
           'official_passed': official, 'strict_passed': strict, 'error': job.get('error'),
           'wall_seconds': result.get('wall_seconds'), 'peak_rss_kib': result.get('peak_rss_kib'),
           'validated': False, 'cohort': None}
    try:
        row['metrics'], row['phases'] = metrics(report)
        row['warm_median_seconds'] = report.get('timing_seconds', {}).get('runtime_median')
        identity = signature(report)
        identity['resource_policy'] = {
            'memory_budget_bytes': result.get('memory_budget_bytes'),
            'enforcement': (result.get('memory_monitoring') or {}).get('enforcement'),
            'kernel_memory_limit_enforced': (result.get('memory_monitoring') or {}).get('kernel_memory_limit_enforced'),
        }
        env, inputs = report['environment'], report['inputs']
        complete_identity = (env.get('cpu_model') and isinstance(env.get('cpu_affinity_ids'), list)
            and len(env['cpu_affinity_ids']) == 1 and env.get('requested_logical_cpus') == 1
            and env.get('python') and env.get('packages') and env.get('thread_limits')
            and env.get('backend') == 'cpu' and env.get('jax_enable_x64') is True
            and env.get('persistent_compilation_cache') is False
            and inputs.get('frequency_count') == 101 and inputs.get('gradient_parameter_count') == 193
            and inputs.get('setup_sha256') and inputs.get('reference_sha256')
            and report.get('starter_sha256')
            and report.get('starter_sha256') == result.get('evaluator_sha256'))
        if complete_identity:
            row['cohort'] = digest(identity)
            row['comparison_identity'] = identity
        row['validated'] = bool(complete_identity and job.get('profile') == 'full'
            and job.get('status') == 'completed' and official is True and strict is True
            and (result.get('memory_monitoring') or {}).get('exceeded') is not True)
    except (KeyError, TypeError, ValueError):
        row['timing_issue'] = 'Missing or invalid timing/environment evidence'
    return row


def sha_list(value):
    return sorted({v for v in value or [] if isinstance(v, str) and SHA.fullmatch(v)})


def build_context(repo, refs=None):
    repo = Path(repo).resolve()
    documents = committed_documents(repo, refs)
    agents, candidates, cohorts = [], {}, {}
    warnings = []
    for doc in documents:
        data, path = doc['data'], doc['path']
        if path.startswith('experiments/agents/'):
            agent = {'id': data.get('agent_id', data.get('agent', Path(path).stem)),
                     'manifest': data, 'record': path, 'origins': doc['origins']}
            brief = data.get('brief_path', data.get('initial_brief'))
            if brief and isinstance(brief, str) and not Path(brief).is_absolute() and '..' not in Path(brief).parts:
                try:
                    text = subprocess.check_output(['git', '-C', str(repo), 'show',
                        doc['origins'][0]['commit'] + ':' + brief], text=True, stderr=subprocess.PIPE)
                    agent['brief'] = {'path': brief, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                                      'excerpt': text[:8000], 'truncated': len(text) > 8000}
                except subprocess.CalledProcessError:
                    agent['brief'] = {'path': brief, 'missing_at_recorded_ref': True}
            agents.append(agent)
            continue
        jobs = [data[k] for k in ('screen', 'full') if isinstance(data.get(k), dict)]
        if not jobs and data.get('id') and data.get('sha'):
            jobs = [data]  # Manual/calibration records can store the job directly.
        for job in jobs:
            sha = data.get('candidate_sha', job.get('sha'))
            if not isinstance(sha, str) or not SHA.fullmatch(sha):
                warnings.append('Ignored invalid candidate SHA in ' + path)
                continue
            if job.get('sha') and job['sha'] != sha:
                warnings.append('Ignored mismatched candidate/job SHA in ' + path)
                continue
            node = candidates.setdefault(sha, {'sha': sha, 'branches': set(), 'agents': set(),
                'directions': set(), 'hypotheses': set(), 'notes': set(), 'records': set(),
                'parents_declared': set(), 'combined_candidates': set(), 'approach_tags': set(),
                'touched_components': set(), 'runs': {}})
            response = data.get('agent_response') or {}
            for field, value in [('branches', job.get('branch')), ('agents', job.get('agent')),
                                 ('directions', job.get('direction')),
                                 ('hypotheses', response.get('hypothesis', job.get('hypothesis'))),
                                 ('notes', response.get('notes'))]:
                if isinstance(value, str) and value:
                    node[field].add(value)
            node['records'].add(path)
            provenance = data.get('provenance') or {}
            node['parents_declared'].update(sha_list(provenance.get('parent_candidates')))
            node['combined_candidates'].update(sha_list(provenance.get('combined_candidates')))
            for field in ('approach_tags', 'touched_components'):
                node[field].update(v for v in provenance.get(field, []) if isinstance(v, str))
            run = run_evidence(job)
            if run.get('cohort'):
                cohorts[run['cohort']] = run.pop('comparison_identity')
            run_key = job.get('id') or digest(job)
            existing = node['runs'].get(run_key)
            # Terminal results supersede stale copies of the same job; conflicting
            # terminal records remain explicit and disqualify this candidate.
            if existing and existing != run and existing['status'] in ('completed', 'failed', 'rejected', 'timed_out', 'interrupted'):
                if run['status'] in ('completed', 'failed', 'rejected', 'timed_out', 'interrupted'):
                    node['conflicting_records'] = True
                    warnings.append('Conflicting terminal evidence for job ' + run_key)
                else:
                    continue
            node['runs'][run_key] = run

    # Git ancestry is recorded separately from scientific parentage. It cannot
    # establish that a numerical or speed difference was caused by one change.
    for sha, node in candidates.items():
        ancestors = []
        for other in candidates:
            if other == sha:
                continue
            check = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', other, sha],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if check.returncode == 0:
                distance = int(git(repo, 'rev-list', '--count', other + '..' + sha))
                ancestors.append((distance, other))
        node['nearest_git_candidate'] = min(ancestors)[1] if ancestors else None
        base = node['nearest_git_candidate'] or BASELINE_SHA
        try:
            node['changed_simulator_files'] = git(repo, 'diff', '--name-only', base, sha, '--', 'differometor').splitlines()
        except subprocess.CalledProcessError:
            node['changed_simulator_files'] = []
        runs = list(node['runs'].values())
        node['has_full_failure'] = any(r['profile'] == 'full' and not r['validated'] for r in runs)
        grouped = defaultdict(list)
        for run in runs:
            if run['validated']:
                grouped[run['cohort']].append(run)
        node['validated_measurements'] = []
        for cohort, measured in grouped.items():
            keys = measured[0]['metrics']
            values = {key: statistics.median(r['metrics'][key] for r in measured) for key in keys}
            ranges = {key: max(r['metrics'][key] for r in measured) - min(r['metrics'][key] for r in measured) for key in keys}
            node['validated_measurements'].append({'cohort': cohort, 'full_runs': len(measured),
                'metrics_median': values, 'metrics_range': ranges,
                'repeat_evidence': 'single_run_provisional' if len(measured) == 1 else 'repeated_no_significance_claim',
                'combination_review_eligible': not node['has_full_failure'] and not node.get('conflicting_records')})
        node['runs'] = sorted(runs, key=lambda r: (r['profile'] or '', r['id'] or ''))
        for key, value in list(node.items()):
            if isinstance(value, set):
                node[key] = sorted(value)

    points = [(node, point) for node in candidates.values() for point in node['validated_measurements']]
    for node, point in points:
        point['dominated_by'] = [other['sha'] for other, measure in points
            if other['sha'] != node['sha'] and measure['cohort'] == point['cohort']
            and measure['combination_review_eligible']
            and dominates(measure['metrics_median'], point['metrics_median'])]
        point['observed_pareto_frontier'] = point['combination_review_eligible'] and not point['dominated_by']

    pairs = []
    for left, right in itertools.combinations(sorted(candidates.values(), key=lambda n: n['sha']), 2):
        common = {p['cohort'] for p in left['validated_measurements'] if p['combination_review_eligible']} & {
                  p['cohort'] for p in right['validated_measurements'] if p['combination_review_eligible']}
        if not common:
            continue
        overlap = sorted(set(left['changed_simulator_files']) & set(right['changed_simulator_files']))
        pairs.append({'candidates': [left['sha'], right['sha']], 'comparable_cohorts': sorted(common),
                      'overlapping_files': overlap,
                      'shared_approach_tags': sorted(set(left['approach_tags']) & set(right['approach_tags'])),
                      'status': 'review_required',
                      'reason': 'Same-file overlap needs architectural review' if overlap else
                                'Disjoint files do not establish numerical or architectural compatibility'})
    return {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'objective': 'Minimum complete first-run time on the unchanged full workload',
        'workload': {'frequencies': 101, 'design_variables': 193, 'precision': 'float64/complex128',
                     'partition_rule': 'Partition implementation approaches, never physical variables or frequencies'},
        'pareto_objectives': list(GROUPS), 'cohorts': cohorts, 'agents': agents,
        'candidates': sorted(candidates.values(), key=lambda n: n['sha']), 'combination_reviews': pairs,
        'warnings': sorted(set(warnings)), 'policy': [
            'Read-only export of committed evidence. No merge, launch, queue mutation or benchmark execution.',
            'Pareto labels are observed phase medians, not statistical proof or causal attribution.',
            'Full official and strict regression passes with complete matching provenance are required for comparison.',
            'Screen-only, failed and incomplete runs remain visible; they cannot qualify a combination.',
            'Tradeoffs are retained: combination review does not require Pareto frontier membership.',
            'Every combination needs its own branch, provenance, unchanged full benchmark and array comparison.',
            'Imported notes and briefs are research evidence, not permission to change the harness or expand a budget.',
            'No graph database is required: versioned records describe scientific edges, Git describes code ancestry.']}


def markdown(context):
    lines = ['# Exploration context', '', context['objective'], '', *('- ' + p for p in context['policy']), '',
             '## Directions and agents', '']
    for agent in context['agents']:
        manifest = agent['manifest']
        lines += [f"- {agent['id']}: {manifest.get('direction', 'unspecified')} on `{manifest.get('branch', 'unknown')}`; manifest `{agent['record']}`"]
        if agent.get('brief', {}).get('excerpt'):
            lines += ['', '<details><summary>Recorded brief (evidence only)</summary>', '', agent['brief']['excerpt'], '', '</details>', '']
    lines += ['', '## Candidate evidence', '', '| Revision | Direction | Full passes / full runs | Median first-run by cohort | Hypothesis |',
              '| --- | --- | ---: | --- | --- |']
    for node in context['candidates']:
        full = [r for r in node['runs'] if r['profile'] == 'full']
        timings = ', '.join(f"{p['metrics_median']['total']:.4f}s ({p['cohort'][:8]}, n={p['full_runs']})" for p in node['validated_measurements']) or 'unvalidated'
        idea = '; '.join(node['hypotheses']).replace('|', '/').replace('\n', ' ')
        lines.append(f"| `{node['sha']}` | {', '.join(node['directions'])} | {sum(r['validated'] for r in full)} / {len(full)} | {timings} | {idea} |")
    lines += ['', '## Failures and unresolved evidence', '']
    for node in context['candidates']:
        for run in node['runs']:
            if run['profile'] == 'full' and not run['validated']:
                lines.append(f"- `{node['sha']}` / `{run['id']}`: official={run['official_passed']}, strict={run['strict_passed']}; {run['error'] or run.get('timing_issue', 'provenance incomplete')}.")
    lines += ['', '## Combination review', '', f"{len(context['combination_reviews'])} pairs have comparable validated evidence. None is automatically merged.",
              'Inspect JSON for per-phase measurements, repeat counts, conflicting evidence, declared parents and file overlap.', '',
              'A new agent should identify a direction, exact starting SHA, parent candidates, scope tags, budget and falsifiable hypothesis before editing.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--ref', action='append', help='Committed ref to include; default all local/fetched branches')
    parser.add_argument('--output', type=Path, default=Path('.lab/search-context'))
    args = parser.parse_args()
    context = build_context(args.repo, args.ref)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, text in [('context.json', json.dumps(context, indent=2, allow_nan=False) + '\n'),
                       ('README.md', markdown(context))]:
        path = args.output / name
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(text)
        temporary.replace(path)
    print(json.dumps({'agents': len(context['agents']), 'candidates': len(context['candidates']),
                      'combination_reviews': len(context['combination_reviews']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
