"""After both reserved searches drain, interleave exact-SHA lane-local repeats.

No topology edits or budget extension. Existing queue request IDs survive restart.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from lab.client import Client
from lab.evolution import Campaign
from lab.evolution_evidence import normalize_job
from lab.evolution_run import atomic_json
from lab.topology_tuning import sources


def new_evaluations(snapshot):
    return sum(not e.get('imported', False) for e in snapshot['evaluations'])


def can_reserve(used, repeat_reservations, now, deadline):
    return used + repeat_reservations < 40 and repeat_reservations < 14 and now < deadline


def inspect_result(job, target, policy, cohort):
    evidence = normalize_job(job, expected_sha=target['sha'], policy_context=policy)
    if evidence['category'] in ('valid', 'invalid_candidate'):
        if evidence['cohort_digest'] != cohort:
            raise ValueError('Repeat changed the frozen cohort')
        if job['report.json']['source']['simulator_files_sha256'] != target['source_hashes']:
            raise ValueError('Repeat changed the exact source map')
    return evidence


def publish(root, directory):
    repo = root / '.lab/worktrees/layout-numerical-control'
    relative = 'experiments/control/layout-numerical-v2/confirmation-results'
    destination = repo / relative
    destination.mkdir(parents=True, exist_ok=True)
    for path in directory.glob('*.json'):
        if path.name != 'launch.json':
            (destination / path.name).write_bytes(path.read_bytes())
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    if git('branch', '--show-current') != 'control/layout-numerical-v2':
        raise ValueError('Confirmation publication branch moved')
    git('add', '--', relative)
    staged = git('diff', '--cached', '--name-only').splitlines()
    if any(not p.startswith(relative + '/') for p in staged):
        raise ValueError('Unexpected staged file during confirmation publication')
    if staged:
        git('commit', '-m', 'Record lane-local numerical window confirmation')
    subprocess.run(['git', '-C', str(repo), '-c', 'credential.helper=!gh auth git-credential',
                    'push', 'origin', 'control/layout-numerical-v2'], check=True)


def execute(root):
    data = root / '.lab/campaigns/layout-window-confirmations'
    data.mkdir(parents=True, exist_ok=True)
    budget = json.loads((root / '.lab/campaigns/layout-numerical-v2-bootstrap/global-budget.json').read_text())
    deadline = budget['deadline_unix']
    first = root / '.lab/campaigns/layout-numerical-v2'
    second = root / '.lab/campaigns/layout-numerical-lane1'
    done_paths = [root / '.lab/campaigns/layout-numerical-v2-bootstrap/outcome.json', second / 'outcome.json']
    while not all(p.exists() for p in done_paths):
        if time.time() >= deadline:
            return {'status': 'deadline_before_searches_drained'}
        time.sleep(5)
    snapshots = [Campaign(p / 'campaign.sqlite3').snapshot() for p in (first, second)]
    if any(l.get('inflight_candidate') for s in snapshots for l in s['lanes']):
        return {'status': 'pending_search_requires_review'}
    # Two initial CPU-2 seed jobs and two separately owned capacity calibration
    # jobs are conservatively included in this same global ceiling.
    used = 4 + sum(new_evaluations(s) for s in snapshots)
    if used > 26:
        return {'status': 'unexpected_search_usage', 'used': used}
    runtime = json.loads((second / 'runtime.json').read_text())
    policy = runtime['policy']
    cohort = snapshots[1]['campaign']['spec']['cohort_digest']
    client = Client(runtime['host'], runtime['root'])
    plan_path = data / 'plan.json'
    if not plan_path.exists():
        jobs = [json.loads(p.read_text()) for p in (second / 'queue-results').glob('*.json')]
        jobs.append(json.loads((root / '.lab/deployments/lane1/calibration-full.json').read_text()))
        eligible = {}
        for job in jobs:
            evidence = normalize_job(job, policy_context=policy)
            if evidence['eligible_full'] and evidence['cohort_digest'] == cohort:
                eligible.setdefault(job['sha'], {})[job['id']] = job
        candidates = sorted((c for c in snapshots[1]['candidates'] if c['valid']),
                            key=lambda c: c['metrics']['total'])[:3]
        wanted = [(c['commit_sha'], runtime['branch'], 'lane34-finalist') for c in candidates]
        wanted += [('96474bdd4d83bb02c163640f63fae1c4bd7a21d4', 'explore/claude-noise-reuse', 'reference'),
                   (snapshots[1]['campaign']['spec']['seed_sha'], 'explore/layout-round-seed', 'layout-reference')]
        cpu2_valid = [c for c in snapshots[0]['candidates'] if c['valid']]
        if cpu2_valid:
            cpu2_best = min(cpu2_valid, key=lambda c: c['metrics']['total'])
            wanted.append((cpu2_best['commit_sha'], 'explore/layout-numerical-v2', 'cpu2-finalist-new-lane-measurement'))
        targets = {}
        for sha, branch, role in wanted:
            target = targets.setdefault(sha, {'sha': sha, 'branch': branch, 'roles': [],
                'source_hashes': {p: hashlib.sha256(s.encode()).hexdigest() for p, s in sources(root, sha).items()},
                'existing_job_ids': list(eligible.get(sha, {}))})
            target['roles'].append(role)
            for job in eligible.get(sha, {}).values():
                inspect_result(job, target, policy, cohort)
                atomic_json(data / (job['id'] + '.json'), job)
        # Round-robin ordering interleaves references with candidate measurements.
        ordered = sorted(targets, key=lambda s: (not any('reference' in r for r in targets[s]['roles']), s))
        requests = []
        for repetition in range(3):
            for sha in ordered:
                if repetition < max(0, 3 - len(targets[sha]['existing_job_ids'])):
                    requests.append({'sha': sha, 'request_id': None, 'job_id': None, 'status': 'planned'})
        if len(requests) > 14:
            raise ValueError('Confirmation plan exceeds its reserved allocation')
        coverage = []
        for snapshot, done in zip(snapshots, done_paths):
            spec = snapshot['campaign']['spec']
            tried = {json.dumps(c['parameters'], sort_keys=True) for c in snapshot['candidates']}
            unseen = [p for p in spec['manifest']['legal'] if json.dumps(p, sort_keys=True) not in tried]
            coverage.append({'campaign': spec['campaign_id'], 'manifest_digest': spec['manifest_digest'],
                'tried': len(tried), 'legal': len(spec['manifest']['legal']), 'unseen': unseen,
                'eligible_full_configurations': sum(c['valid'] for c in snapshot['candidates']),
                'stop': json.loads(done.read_text()),
                'interpretation': 'Frozen menu coverage only; neither budget nor menu exhaustion proves a local optimum.'})
        plan = {'deadline_unix': deadline, 'search_and_calibration_jobs': used, 'max_total_jobs': 40,
                'max_repeat_jobs': 14, 'policy': policy, 'cohort_digest': cohort,
                'host': runtime['host'], 'root': runtime['root'], 'targets': targets, 'requests': requests,
                'search_coverage': coverage,
                'comparison_context': 'Same CPU34 capacity-expansion regime; no cross-lane timing ranking or final quiet promotion.'}
        atomic_json(plan_path, plan)
        publish(root, data)
    plan = json.loads(plan_path.read_text())
    if plan['policy'] != policy or plan['cohort_digest'] != cohort or plan['deadline_unix'] != deadline:
        raise ValueError('Frozen confirmation policy changed')
    failed = set(plan.get('scientific_failures', []))
    for request in plan['requests']:
        if request['status'] in ('valid', 'invalid_candidate', 'skipped'):
            continue
        if request['sha'] in failed:
            request['status'] = 'skipped'
            atomic_json(plan_path, plan)
            continue
        if request['request_id'] is None:
            reserved = sum(r['request_id'] is not None for r in plan['requests'])
            if not can_reserve(used, reserved, time.time(), deadline):
                return {'status': 'budget_exhausted', 'search_and_calibration_jobs': used, 'repeat_reservations': reserved}
            request['request_id'] = uuid.uuid4().hex
            request['reserved_at'] = time.time()
            atomic_json(plan_path, plan)
        existing = client.request({'action': 'lookup_request', 'request_id': request['request_id']})
        if existing is None and time.time() >= deadline:
            return {'status': 'budget_exhausted_before_dispatch'}
        target = plan['targets'][request['sha']]
        job = client.submit(root, target['branch'], 'layout-window-repeat', 'same-cohort-confirmation',
            'Repeat exact committed finalist/reference on CPU34; exploratory concurrent epoch, no cross-lane speed claim.',
            profile='full', sha=target['sha'], publish=False, request_id=request['request_id'])
        request['job_id'] = job['id']; request['status'] = 'waiting'
        atomic_json(plan_path, plan)
        print(json.dumps({'sha': target['sha'], 'job_id': job['id']}), flush=True)
        job = client.wait(job['id'], timeout=3600)
        atomic_json(data / (job['id'] + '.json'), job)
        evidence = inspect_result(job, target, policy, cohort)
        request['status'] = evidence['category']
        if evidence['category'] == 'invalid_candidate':
            failed.add(target['sha']); plan['scientific_failures'] = sorted(failed)
        atomic_json(plan_path, plan)
        publish(root, data)
        if evidence['category'] not in ('valid', 'invalid_candidate'):
            return {'status': 'infrastructure_needs_review', 'job_id': job['id']}
    return {'status': 'complete', 'search_and_calibration_jobs': used,
            'repeat_jobs': sum(r['job_id'] is not None for r in plan['requests'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / '.lab/campaigns/layout-window-confirmations'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = execute(root)
        atomic_json(directory / 'outcome.json', dict(result, observed_at=time.time()))
        publish(root, directory)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
