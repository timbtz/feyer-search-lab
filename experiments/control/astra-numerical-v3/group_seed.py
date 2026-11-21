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
    prefix = 'experiments/control/astra-numerical-v3/group-receipts'
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
    job = client.submit(root, plan['seed_branch'], 'astra-group-numerical-v3', 'fresh-lane-seed',
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
    if time.time() >= plan['deadline_unix']:
        return {'status': 'deadline_reached_after_seed', 'jobs_used': 1}
    from types import SimpleNamespace
    from lab.topology_run import initialize, run
    from lab.evolution import Campaign
    campaign_state = root / '.lab/campaigns/astra-group-numerical-v3'
    if not campaign_state.exists():
        initialize(SimpleNamespace(state=campaign_state, repo=root / '.lab/worktrees/topology-lane-policy',
            manifest=state/'manifest.json', seed_report=state/'seed-full.json', policy_context=state/'policy.json',
            name='astra-group-numerical-v3', deadline_unix=plan['deadline_unix'], max_evaluations=10,
            host=plan['host'], root=plan['root'], publish=True))
    atomic_json(campaign_state/'launch.json', json.loads((state/'launch.json').read_text()))
    result=run(SimpleNamespace(state=campaign_state, once=False))
    snapshot=Campaign(campaign_state/'campaign.sqlite3').snapshot()
    tried={json.dumps(c['parameters'],sort_keys=True) for c in snapshot['candidates']}
    unseen=[x for x in manifest['legal'] if json.dumps(x,sort_keys=True) not in tried]
    jobs=sum(not e.get('imported',False) for e in snapshot['evaluations'])
    coverage={'manifest_digest':plan['manifest_digest'],'legal':len(manifest['legal']), 'tried':len(tried),
        'unseen':unseen,'full_valid':sum(c['valid'] for c in snapshot['candidates']),
        'controller_status':result['status'], 'transition_reason':'menu_exhausted' if not unseen else result['status'],
        'evaluation_cap_reached':jobs>=10,'deadline_reached':time.time()>=plan['deadline_unix'],
        'support_jobs_used_or_reserved':1+jobs, 'global_jobs_used_or_reserved':2+jobs,
        'local_optimum_claimed':False,'deadline_unix':plan['deadline_unix']}
    atomic_json(state/'coverage.json',coverage)
    atomic_json(campaign_state/'outcome.json',dict(result,transition_reason=coverage['transition_reason'],observed_at=time.time()))
    return dict(result, transition_reason=coverage['transition_reason'], global_jobs_used_or_reserved=2+jobs)



if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args();root=args.root.resolve()
    state=root/'.lab/campaigns/astra-group-numerical-v3-bootstrap'
    with (state/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=execute(root,state)
        atomic_json(state/'outcome.json',dict(result,observed_at=time.time()))
        publish(root,state)
        print(json.dumps(result),flush=True)
