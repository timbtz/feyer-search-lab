"""Compare first-run phases and observed Pareto tradeoffs without rerunning physics."""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

GROUPS = {
    'setup': ('imports', 'initialize', 'load', 'build'),
    'compilation': ('forward_lower', 'forward_compile', 'sensitivity_lower',
                    'sensitivity_compile', 'gradient_lower', 'gradient_compile'),
    'forward': ('forward',), 'sensitivity': ('sensitivity',),
    'gradient': ('gradient',), 'transfer': ('host_transfer',),
}

# Reviewed screen-v1 evaluates the same first-run workload as the official v2
# benchmark. A changed screen hash requires another equivalence review.
SCREEN_EQUIVALENCE = {
    ('feyer-lab-screen-v1', '5cb1e5b8013dde1249845e3d6ce24b1f85240a0fb14b5cb966340188559c390a'):
    ('start-munich-2026-public-differometor-uifo-v2', 'd5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e'),
    ('feyer-lab-screen-v1', '2bf4249e453271d1f665c35356485739ad66a9b0327153d678a5b34d81192458'):
    ('start-munich-2026-public-differometor-uifo-v2', 'd5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e'),
}


def metrics(report):
    phases = {p['key']: p['seconds'] for p in report['phases']}
    required = {key for keys in GROUPS.values() for key in keys}
    if not required.issubset(phases):
        raise ValueError('Missing required first-run phases')
    values = {name: sum(phases[key] for key in keys) for name, keys in GROUPS.items()}
    values['total'] = report['timing_seconds']['end_to_end']
    if not all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0
               for x in list(values.values()) + list(phases.values())):
        raise ValueError('Invalid phase timings')
    return values, phases


def signature(report):
    env = report['environment']
    names = ('cpu_model', 'cpu_affinity_ids', 'requested_logical_cpus', 'backend',
             'jax_enable_x64', 'persistent_compilation_cache', 'python', 'packages',
             'thread_limits', 'xla_flags')
    inputs = report['inputs']
    timing = (report.get('benchmark'), report.get('starter_sha256'))
    timing = SCREEN_EQUIVALENCE.get(timing, timing)
    workload = report.get('workload', {})
    return {'environment': {k: env.get(k) for k in names},
            'timing': {'benchmark': timing[0], 'evaluator_sha256': timing[1],
                       'phase_keys': sorted(p['key'] for p in report['phases']),
                       'scope': {k: workload.get(k) for k in ('objective', 'gradient_coordinates',
                                'optimizer_steps', 'forward_residuals', 'total_scope', 'excluded')}},
            'inputs': {k: inputs.get(k) for k in ('setup_sha256', 'reference_sha256',
                                                'frequency_count', 'gradient_parameter_count')}}


def baseline(reports):
    if not reports or any(signature(r) != signature(reports[0]) for r in reports):
        raise ValueError('Baseline reports must have matching environments and workloads')
    rows = [metrics(r) for r in reports]
    def summarize(index):
        return {k: {'median': statistics.median(row[index][k] for row in rows),
                    'range': max(row[index][k] for row in rows) - min(row[index][k] for row in rows)}
                for k in rows[0][index]}
    return {'runs': len(reports), 'signature': signature(reports[0]),
            'metrics': summarize(0), 'phases': summarize(1)}


def deltas(values, reference):
    result = {}
    for key, value in values.items():
        ref = reference[key]['median']
        saved = ref - value
        threshold = max(.02, .03 * ref, reference[key]['range'])
        result[key] = {'seconds': value, 'baseline_seconds': ref, 'saved_seconds': saved,
                       'saved_percent': 100 * saved / ref if ref else None,
                       'threshold_seconds': threshold,
                       'classification': 'improved' if saved > threshold else
                           'regressed' if saved < -threshold else 'within_noise_band'}
    return result


def analyze_feedback(feedback, ref):
    # Never substitute screening success for a failed or absent full validation.
    job = feedback.get('full') or feedback.get('screen') or {}
    report = job.get('report.json')
    result = {'sha': feedback.get('candidate_sha'), 'profile': job.get('profile'),
              'job_id': job.get('id'), 'error': job.get('error'),
              'idea': feedback.get('agent_response', {}).get('summary', ''),
              'hypothesis': feedback.get('agent_response', {}).get('hypothesis', ''),
              'branch': job.get('branch'), 'agent': job.get('agent'),
              'direction': job.get('direction'),
              'created_at': job.get('created_at', 0), 'validated': False,
              'execution_status': job.get('status', 'unknown')}
    official = (job.get('result') or {}).get('official_passed')
    comparison = job.get('comparison.json', {}).get('passed')
    result['official_check'] = ('passed' if official is True else
        'not_run' if job.get('profile') != 'full' else 'failed' if official is False else 'unknown')
    result['strict_check'] = 'passed' if comparison is True else 'failed' if comparison is False else 'not_run'
    execution = job.get('result') or {}
    memory = execution.get('memory_monitoring') or {}
    provenance = execution.get('resource_provenance') or {}
    peak_kib = execution.get('peak_rss_kib')
    result['resource_evidence'] = {
        'budget_bytes': execution.get('memory_budget_bytes'),
        'enforcement': memory.get('enforcement', 'unknown_historical'),
        'kernel_memory_limit_enforced': memory.get('kernel_memory_limit_enforced'),
        'sampled_process_group_peak_rss_bytes': memory.get('sampled_process_group_peak_rss_bytes'),
        'budget_exceeded': memory.get('exceeded'),
        'gnu_time_peak_rss_bytes': peak_kib * 1024 if peak_kib is not None else None,
        'container_memory_max': provenance.get('container_limits', {}).get('memory.max'),
        'comparison_memory_monitoring': (execution.get('comparison') or {}).get('memory_monitoring'),
    }
    if report is None:
        result['classification'] = 'no_timing_report'
        return result
    values, phases = metrics(report)
    actual_hash = (job.get('result') or {}).get('evaluator_sha256')
    reported_hash = report.get('starter_sha256')
    hash_matches = actual_hash == reported_hash if actual_hash and reported_hash else None
    same = signature(report) == ref['signature'] and hash_matches is not False
    validated = (job.get('profile') == 'full' and job.get('status') == 'completed'
                 and job.get('result', {}).get('official_passed') is True
                 and job.get('comparison.json', {}).get('passed') is True)
    result.update(metrics=values, phases=phases, validated=validated, comparable=same,
                  evaluator_hash_matches_report=hash_matches,
                  warm_timing=report.get('timing_seconds', {}).get('phase_runtime_medians', {}),
                  source_report=report.get('source', {}),
                  peak_rss_kib=job.get('result', {}).get('peak_rss_kib'))
    if not same:
        result['classification'] = 'different_environment_workload_or_evaluator'
        return result
    result['delta'] = deltas(values, ref['metrics'])
    result['phase_delta'] = deltas(phases, ref['phases'])
    result['improved_subphases'] = [k for k, v in result['phase_delta'].items() if v['classification'] == 'improved']
    result['regressed_subphases'] = [k for k, v in result['phase_delta'].items() if v['classification'] == 'regressed']
    improved = [k for k in GROUPS if result['delta'][k]['classification'] == 'improved']
    regressed = [k for k in GROUPS if result['delta'][k]['classification'] == 'regressed']
    result.update(improved=improved, regressed=regressed,
                  observed_dominates_baseline=dominates(values, {k:v['median'] for k,v in ref['metrics'].items()}))
    result['classification'] = ('improvement_without_detected_regression' if improved and not regressed else
                                'tradeoff' if improved and regressed else
                                'regression' if regressed else 'within_noise_band')
    return result


def dominates(left, right):
    """Exact observed dominance, not a statistical significance claim."""
    return all(left[k] <= right[k] for k in GROUPS) and any(left[k] < right[k] for k in GROUPS)


def collect_rows(repo, ref, ledger):
    """Keep independent full jobs separate; do not average away validation failures."""
    jobs = {}
    for path in sorted(ledger.glob('*.json')):
        job = json.loads(path.read_text())
        jobs[job['id']] = (job, {'summary': job.get('hypothesis', ''),
                                'hypothesis': job.get('hypothesis', '')}, None)
    roots = {repo}
    listing = subprocess.check_output(['git', '-C', str(repo), 'worktree', 'list', '--porcelain'], text=True)
    roots.update(Path(line[9:]) for line in listing.splitlines() if line.startswith('worktree '))
    for root in sorted(roots):
        for path in sorted((root / 'experiments/runs').glob('*/candidate-*.json')):
            feedback = json.loads(path.read_text())
            for profile in ('screen', 'full'):
                job = feedback.get(profile)
                if job:
                    jobs[job['id']] = (job, feedback.get('agent_response', {}),
                                      (path.relative_to(root).as_posix(), path.parent.name + '/' + path.stem))
    grouped = {}
    for job, response, record in jobs.values():
        key = (job['sha'], job.get('agent'), job.get('branch'), job.get('direction'))
        grouped.setdefault(key, []).append((job, response, record))
    rows = []
    for entries in grouped.values():
        full = [e for e in entries if e[0]['profile'] == 'full']
        screens = [e for e in entries if e[0]['profile'] == 'screen']
        for job, response, record in full or screens:
            item = analyze_feedback({'candidate_sha': job['sha'], 'agent_response': response,
                                     job['profile']: job}, ref)
            item['record'] = record[0] if record else None
            item['name'] = record[1] if record else f"{job.get('agent', 'manual')}/{job['sha'][:8]}-{job['profile']}-{job['id'][:8]}"
            item['run_key'] = job['id']
            item['screen_job_ids'] = [e[0]['id'] for e in screens]
            item['screen_pairing'] = 'Same SHA, agent, branch and direction; no one-to-one rerun pairing inferred'
            rows.append(item)
    return sorted(rows, key=lambda r: (r['created_at'], r['name'], r['job_id']))


def build_report(repo, ledger=None):
    reports = [json.loads(p.read_text()) for p in sorted((repo / 'experiments/baselines').glob('base*.json'))]
    ref = baseline(reports)
    rows = collect_rows(repo, ref, ledger or repo / '.lab/phase-ledger')
    reference_values = {k: v['median'] for k, v in ref['metrics'].items()}
    eligible = [r for r in rows if r['validated'] and r.get('comparable')]
    for row in rows:
        if row in eligible:
            row['dominated_by'] = [other['name'] for other in eligible
                                   if other is not row and dominates(other['metrics'], row['metrics'])]
            if dominates(reference_values, row['metrics']):
                row['dominated_by'].append('baseline phase medians')
            row['observed_pareto_frontier'] = not row['dominated_by']
        else:
            row['observed_pareto_frontier'] = False
        # Record real code ancestry, not just the chronological order of evaluations.
        row['parent_candidate'] = None
        row['parent_run_key'] = None
        ancestors = []
        for previous in rows:
            if previous['sha'] == row['sha']:
                continue
            check = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor',
                                    previous['sha'], row['sha']], capture_output=True)
            if check.returncode == 0:
                distance = int(subprocess.check_output(['git', '-C', str(repo), 'rev-list', '--count',
                                                       f"{previous['sha']}..{row['sha']}"], text=True))
                ancestors.append((distance, -previous['created_at'], previous['job_id'], previous))
        if ancestors:
            previous = min(ancestors, key=lambda item: item[:3])[3]
            row['parent_candidate'] = previous['sha']
            row['parent_run_key'] = previous['run_key']
            if row.get('comparable') and previous.get('comparable'):
                row['saved_vs_parent_seconds'] = {k: previous['metrics'][k] - row['metrics'][k]
                                                  for k in row['metrics']}
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'baseline': ref, 'candidates': rows,
            'pareto_objectives': list(GROUPS), 'primary_objective': 'total',
            'meaningful_change_rule': 'Magnitude exceeds max(0.02 seconds, 3% of baseline phase median, baseline phase range). Heuristic, not statistical significance.',
            'pareto_rule': 'Exact observed dominance on six first-run phase groups; only full official + strict-array passes with matching environment. Baseline point uses phase medians from three runs.',
            'limitations': 'Single candidate runs are provisional. Baseline medians are calculated independently per phase and need not sum to the median total. First-run and warm timings remain separate. Memory is recorded but not a Pareto objective. Causal attribution requires controlled/repeated runs.'}


def markdown(data):
    lines = ['# Candidate phase comparison', '', f"Snapshot: {data['generated_at']}", '',
             data['meaningful_change_rule'], '', data['pareto_rule'], '', data['limitations'], '',
             'All times below are first-run seconds. Positive savings mean faster.', '',
             '| Candidate evaluation | Official / strict | Total | Setup | Compilation | Forward | Sensitivity | Gradient | Transfer | Improved / regressed vs baseline |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    ref = data['baseline']['metrics']
    keys = ['total', *GROUPS]
    lines.append('| Baseline medians | passed | ' + ' | '.join(f"{ref[k]['median']:.4f}" for k in keys) + ' | reference |')
    for row in data['candidates']:
        values = row.get('metrics', {})
        parts = ', '.join(row.get('improved', [])) or 'none'
        regressions = ', '.join(row.get('regressed', [])) or 'none'
        lines.append(f"| {row['name']} ({row['sha'][:8]}) | {row['official_check']} / {row['strict_check']} | " +
                     ' | '.join(f'{values[k]:.4f}' if k in values else '—' for k in keys) +
                     f' | improved: {parts}; regressed: {regressions} |')
    lines += ['', '## Exploration ancestry', '', 'Edges represent commit ancestry, not proof of causal attribution.', '', '```mermaid', 'graph LR']
    ids = {row['run_key']: f'c{i}' for i, row in enumerate(data['candidates'])}
    for row in data['candidates']:
        label = row['name'].replace('"', '').replace('[', '').replace(']', '')
        lines.append(f'  {ids[row["run_key"]]}["{label}"]')
        if row['parent_run_key']:
            lines.append(f'  {ids[row["parent_run_key"]]} --> {ids[row["run_key"]]}')
    lines += ['```', '', '## Candidate details', '']
    for row in data['candidates']:
        lines += [f"### {row['name']}", '', row['idea'], '',
                  f"Classification: {row.get('classification')}. Observed Pareto frontier: {row['observed_pareto_frontier']}.", '',
                  f"Memory enforcement evidence: {row['resource_evidence']['enforcement']}; kernel cap: {row['resource_evidence']['kernel_memory_limit_enforced']}; budget bytes: {row['resource_evidence']['budget_bytes']}.", '',
                  f"[Code](https://github.com/timbtz/feyer-search-lab/commit/{row['sha']})", '']
        if row.get('error'): lines += [f"Validation: {row['error']}", '']
    return '\n'.join(lines).rstrip() + '\n'


def render_html(data):
    template = Path(__file__).with_name('phase_report.html').read_text()
    return template.replace('__DATA__', json.dumps(data).replace('<', '\\u003c'))


def write_report(repo, output, ledger=None):
    data = build_report(repo, ledger)
    output.mkdir(parents=True, exist_ok=True)
    for name, content in [('phases.json', json.dumps(data, indent=2) + '\n'),
                          ('README.md', markdown(data)), ('index.html', render_html(data))]:
        temporary = output / (name + '.tmp')
        temporary.write_text(content)
        temporary.replace(output / name)
    with (output / 'phases.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['candidate', 'sha', 'validated', 'profile', 'phase', 'seconds', 'saved_seconds', 'classification'])
        for row in data['candidates']:
            for phase, seconds in row.get('phases', {}).items():
                delta = row.get('phase_delta', {}).get(phase, {})
                writer.writerow([row['name'], row['sha'], row['validated'], row['profile'], phase,
                                 seconds, delta.get('saved_seconds'), delta.get('classification')])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, default=Path('.lab/phase-dashboard'))
    parser.add_argument('--watch-session', type=Path, help='Refresh while this supervisor status file is active')
    parser.add_argument('--sync', action='store_true', help='Read terminal jobs from the shared queue into the local ledger')
    parser.add_argument('--host', default='amd-hackathon')
    parser.add_argument('--ledger', type=Path, help='Job-envelope ledger; defaults to REPO/.lab/phase-ledger')
    args = parser.parse_args()
    ledger = args.ledger or args.repo.resolve() / '.lab/phase-ledger'
    while True:
        if args.sync:
            from .client import Client, sync_ledger
            synced = sync_ledger(Client(args.host), ledger)
            print(json.dumps({'ledger_sync': synced}), flush=True)
        data = write_report(args.repo.resolve(), args.output.resolve(), ledger)
        print(f"Recorded {len(data['candidates'])} candidates in {args.output}", flush=True)
        if not args.watch_session:
            break
        state = json.loads(args.watch_session.read_text())
        if state['status'] in ('complete', 'failed', 'budget_exhausted', 'interrupted'):
            break
        time.sleep(10)


if __name__ == '__main__':
    main()
