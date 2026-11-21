"""One authorized numerical window; seed gate and existing campaign controller."""
import fcntl
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
import uuid

from lab.client import Client
from lab.evolution_evidence import normalize_job
from lab.evolution_run import atomic_json
from lab.topology_tuning import VERSION, sources, validate_manifest
from lab.topology_run import initialize, run

ROOT = Path('/Users/t.betz/Documents/Feyer challenge')
BOOT = ROOT / '.lab/campaigns/layout-numerical-v2-bootstrap'
STATE = ROOT / '.lab/campaigns/layout-numerical-v2'
CONTROLLER = ROOT / '.lab/worktrees/topology-tuning'
SEED_REPO = ROOT / '.lab/worktrees/layout-round-seed'


def main():
    with (BOOT / 'bootstrap.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = json.loads((BOOT / 'plan.json').read_text())
        client = Client(plan['host'], plan['root'])
        for profile in ('screen', 'full'):
            request = plan['seed_requests'][profile]
            existing = client.request({'action': 'lookup_request', 'request_id': request['request_id']})
            if existing is None and time.time() >= plan['deadline_unix']:
                return {'status': 'budget_exhausted_before_seed_' + profile}
            job = client.submit(SEED_REPO, plan['seed_branch'], 'layout-numerical-v2',
                'split-rhs-layout-combination', plan['hypothesis'], profile=profile,
                sha=plan['seed_sha'], publish=True, request_id=request['request_id'])
            request['job_id'] = job['id']
            atomic_json(BOOT / 'plan.json', plan)
            print(json.dumps({'stage': profile, 'job_id': job['id'], 'sha': plan['seed_sha']}), flush=True)
            job = client.wait(job['id'], timeout=3600)
            atomic_json(BOOT / (job['id'] + '.json'), job)
            evidence = normalize_job(job, expected_sha=plan['seed_sha'])
            if not evidence['screen_passed' if profile == 'screen' else 'eligible_full']:
                return {'status': 'seed_needs_review', 'profile': profile,
                        'category': evidence['category'], 'issues': evidence['issues']}
        if time.time() >= plan['deadline_unix']:
            return {'status': 'seed_validated_after_deadline', 'job_id': job['id']}
        manifest = {'version': VERSION, 'parent_sha': plan['seed_sha'],
            'base_sources': sources(ROOT, plan['seed_sha']),
            'dimensions': {'noise_mode': ['broadcast', 'shared'], 'factor_mode': ['off', 'direct']},
            'defaults': {'noise_mode': 'broadcast', 'factor_mode': 'off'},
            'legal': [{'noise_mode': n, 'factor_mode': f} for n in ['broadcast', 'shared'] for f in ['off', 'direct']],
            'replacements': [
                {'path': 'differometor/simulate.py', 'dimension': 'noise_mode',
                 'anchor': 'NOISE_REUSE_MODE: str = "broadcast"',
                 'values': {json.dumps(v): 'NOISE_REUSE_MODE: str = ' + json.dumps(v)
                            for v in ['broadcast', 'shared']}},
                {'path': 'differometor/simulate.py', 'dimension': 'factor_mode',
                 'anchor': 'NOISE_FACTOR_REUSE: str = "off"',
                 'values': {json.dumps(v): 'NOISE_FACTOR_REUSE: str = ' + json.dumps(v)
                            for v in ['off', 'direct']}}]}
        validate_manifest(manifest)
        atomic_json(BOOT / 'manifest.json', manifest)
        if not STATE.exists():
            print(json.dumps(initialize(SimpleNamespace(
                state=STATE, repo=CONTROLLER, manifest=BOOT / 'manifest.json',
                seed_report=BOOT / (job['id'] + '.json'), name='layout-numerical-v2',
                deadline_unix=plan['deadline_unix'], max_evaluations=38,
                host=plan['host'], root=plan['root'], publish=True))), flush=True)
        launch = json.loads((BOOT / 'launch.json').read_text())
        launch['seed_bootstrap'] = str(BOOT)
        atomic_json(STATE / 'launch.json', launch)
        return run(SimpleNamespace(state=STATE, once=False))


if __name__ == '__main__':
    result = main()
    atomic_json(BOOT / 'outcome.json', dict(result, observed_at=time.time()))
    print(json.dumps(result, indent=2), flush=True)
