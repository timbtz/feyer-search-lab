"""One exact-parent CPU34 calibration under a new, immutable numerical budget."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time
from lab.client import Client, TERMINAL
from lab.evolution_evidence import normalize_job
from lab.evolution_run import atomic_json
from lab.topology_tuning import sources, validate_manifest


def publish(root, state):
    repo = root / '.lab/worktrees/astra-numerical-control'
    prefix = 'experiments/control/astra-numerical-v3/receipts'
    destination = repo / prefix
    destination.mkdir(parents=True, exist_ok=True)
    for source in state.glob('*.json'):
        (destination / source.name).write_bytes(source.read_bytes())
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    assert git('branch', '--show-current') == 'control/astra-numerical-v3'
    git('add', '--', prefix)
    staged = git('diff', '--cached', '--name-only').splitlines()
    assert all(p.startswith(prefix + '/') for p in staged)
    if staged:
        git('commit', '-m', 'Record fresh Astra numerical calibration')
    subprocess.run(['git', '-C', str(repo), '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin', 'control/astra-numerical-v3'], check=True)


def execute(root, state):
    plan = json.loads((state / 'plan.json').read_text())
    manifest = json.loads((state / 'manifest.json').read_text())
    assert validate_manifest(manifest) == plan['manifest_digest']
    assert sources(root, plan['seed_sha']) == manifest['base_sources']
    assert (root / '.lab/campaigns/layout-window-confirmations/outcome.json').exists()
    client = Client(plan['host'], plan['root'])
    request = plan['seed_request']
    existing = client.request({'action': 'lookup_request', 'request_id': request['request_id']})
    if existing is None:
        if time.time() >= plan['deadline_unix']:
            return {'status': 'deadline_reached_before_seed'}
        active = [j for j in client.request({'action': 'list', 'limit': 1000}) if j['status'] not in TERMINAL]
        if active:
            return {'status': 'queue_boundary_requires_review', 'active_job_ids': [j['id'] for j in active]}
    job = client.submit(root, plan['seed_branch'], 'astra-numerical-v3', 'fresh-lane-seed',
        'Measure exact validated Astra topology on CPU34 before source-bound compiler-boundary tuning; new cohort evidence only.',
        profile='full', sha=plan['seed_sha'], publish=False, request_id=request['request_id'])
    request['job_id'] = job['id']
    atomic_json(state / 'plan.json', plan)
    print(json.dumps({'job_id': job['id'], 'sha': job['sha']}), flush=True)
    publish(root, state)
    job = client.wait(job['id'], timeout=3600)
    atomic_json(state / 'seed-full.json', job)
    evidence = normalize_job(job, expected_sha=plan['seed_sha'], policy_context=plan['policy'])
    atomic_json(state / 'seed-evidence.json', evidence)
    expected = {p: hashlib.sha256(s.encode()).hexdigest() for p,s in manifest['base_sources'].items()}
    assert job.get('report.json', {}).get('source', {}).get('simulator_files_sha256') == expected
    if not evidence['eligible_full']:
        return {'status': 'seed_needs_review', 'job_id': job['id'], 'category': evidence['category']}
    return {'status': 'blocked_review', 'reason': 'Parameter menu awaits source/ownership review; no further admissions by seed bootstrap.',
            'seed_job_id': job['id'], 'cohort_digest': evidence['cohort_digest'], 'jobs_used': 1,
            'deadline_unix': plan['deadline_unix']}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args();root=args.root.resolve()
    state=root/'.lab/campaigns/astra-numerical-v3-bootstrap'
    with (state/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=execute(root,state)
        atomic_json(state/'outcome.json',dict(result,observed_at=time.time()))
        publish(root,state)
        print(json.dumps(result),flush=True)
