"""Bounded topology tuning through the existing ledger and serial AMD client."""
import argparse
import fcntl
import json
import math
from pathlib import Path
import re
import subprocess
import time
import uuid

from .evolution import BudgetExhausted, Campaign
from .evolution_evidence import canonical_digest, normalize_job, policy_from_job
from .evolution_run import atomic_json, evaluate, git, publish
from .evolution_report import freeze_context
from .topology_tuning import digest, materialize, observations, render, sources, validate_manifest, verify_parent
from .topology_smac import choose, metadata


def initialize(args):
    state = args.state.resolve()
    if (type(args.max_evaluations) is not int or args.max_evaluations <= 0
            or isinstance(args.deadline_unix, bool) or not math.isfinite(args.deadline_unix)
            or args.deadline_unix <= time.time()):
        raise ValueError('Positive integer evaluation budget and finite future deadline required')
    manifest = json.loads(args.manifest.read_text())
    verify_parent(args.repo, manifest)
    seed = json.loads(args.seed_report.read_text())
    context_path = getattr(args, 'policy_context', None)
    policy_context = json.loads(context_path.read_text()) if context_path else None
    rows, cohort = observations(manifest, [], seed, policy_context=policy_context)
    if state.exists() or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', args.name):
        raise ValueError('New state directory and simple campaign name required')
    if git(args.repo, 'status', '--porcelain'):
        raise ValueError('Use a clean committed controller checkout')
    budget = {'max_proposals': len(manifest['legal']) + 1, 'max_evaluations': args.max_evaluations,
              'max_model_calls': 0, 'deadline_unix': args.deadline_unix}
    optimizer = metadata()
    spec = {'campaign_id': args.name, 'budget': budget, 'selector': 'topology-smac',
            'optimizer': optimizer, 'space_version': manifest['version'], 'manifest': manifest,
            'manifest_digest': validate_manifest(manifest), 'cohort_digest': cohort,
            'seed_sha': manifest['parent_sha'], 'seed_confirmed': False,
            'controller_commit': git(args.repo, 'rev-parse', 'HEAD'),
            'objective': {'primary': 'total', 'direction': 'minimize'},
            'evaluation_policy': policy_from_job(seed, policy_context=policy_context),
            'guidance_policy': 'Validated exploratory seed; no paired confirmation or topology transfer implied'}
    state.mkdir(parents=True)
    campaign = Campaign(state / 'campaign.sqlite3')
    token = campaign.initialize(spec, 'coordinator')
    atomic_json(state / 'credentials.json', {'coordinator': token}, private=True)
    branch = 'explore/' + args.name
    repo = state / 'worktree'
    subprocess.run(['git', '-C', str(args.repo), 'worktree', 'add', '-b', branch,
                    str(repo), manifest['parent_sha']], check=True)
    runtime = {'repo': str(repo), 'branch': branch, 'campaign_id': args.name,
               'policy': spec['evaluation_policy'], 'host': args.host, 'root': args.root,
               'publish': args.publish, 'selector': 'topology-smac', 'optimizer': optimizer}
    atomic_json(state / 'runtime.json', runtime)
    campaign.add_round('coordinator', token, {'round_id': 'topology-001',
        'dimensions': manifest['dimensions'], 'recipes': {'tune': {'dimensions': list(manifest['dimensions'])}},
        'lanes': {'tune': {'owner': 'coordinator', 'dimensions': list(manifest['dimensions']),
                          'max_proposals': len(manifest['legal']), 'stall_limit': len(manifest['legal'])}},
        'budget': budget, 'progress': {'relative': .01, 'absolute': .02},
        'seed_parameters': manifest['defaults'], 'materializer_version': manifest['version']})
    campaign.propose('coordinator', token, {'proposal_id': 'topology-seed', 'candidate_id': 'topology-seed',
        'round_id': 'topology-001', 'lane_id': 'tune', 'kind': 'seed', 'parents': [],
        'parameters': manifest['defaults'], 'commit_sha': manifest['parent_sha'],
        'content_sha256': rows[0]['source_digest'],
        'provenance': {'heuristic_id': 'import-exact-claude-topology', 'model_calls': 0}})
    campaign.observe('coordinator', token, 'topology-seed', normalize_job(seed,
                     expected_sha=manifest['parent_sha'], policy_context=runtime['policy']))
    atomic_json(state / 'queue-results' / (seed['id'] + '.json'), seed)
    atomic_json(state / 'seed.json', seed)
    publish(campaign, state, 'topology-initialized')
    return {'status': 'initialized', 'state': str(state), 'deadline_unix': args.deadline_unix}


def finish_pending(state, campaign, runtime, manifest, token):
    path = state / 'pending-topology.json'
    if not path.exists():
        return
    pending = json.loads(path.read_text())
    proposal = pending['proposal']
    if not any(c['candidate_id'] == proposal['candidate_id'] for c in campaign.snapshot()['candidates']):
        repo = Path(runtime['repo'])
        head = git(repo, 'rev-parse', 'HEAD')
        desired = render(manifest, proposal['parameters'])
        if head == pending['expected_head']:
            materialize(repo, manifest, proposal['parameters'], runtime['branch'], head, runtime['campaign_id'])
            git(repo, 'add', '--', *manifest['base_sources'])
            git(repo, 'commit', '-m', 'Tune exact topology ' + json.dumps(proposal['parameters'], sort_keys=True))
            head = git(repo, 'rev-parse', 'HEAD')
        # Recover only the single exact source commit made above. Dirty interrupted
        # writes require operator review; never silently adopt external edits.
        if (git(repo, 'status', '--porcelain') or git(repo, 'rev-parse', 'HEAD^') != pending['expected_head']
                or sources(repo, head) != desired
                or any(p not in manifest['base_sources'] for p in
                       git(repo, 'diff', '--name-only', pending['expected_head'], head).splitlines())):
            raise ValueError('Interrupted topology commit requires ownership review')
        proposal['commit_sha'] = head
        atomic_json(path, dict(pending, proposal=proposal))
        campaign.propose('coordinator', token, proposal)
    publish(campaign, state, 'topology-proposed')
    path.unlink()


def run(args):
    state = args.state.resolve()
    with (state / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        campaign = Campaign(state / 'campaign.sqlite3')
        runtime = json.loads((state / 'runtime.json').read_text())
        spec = campaign.snapshot()['campaign']['spec']
        manifest = spec['manifest']
        if validate_manifest(manifest) != spec['manifest_digest'] or metadata() != spec['optimizer']:
            raise ValueError('Frozen topology or optimizer drift')
        if runtime['policy'] != spec['evaluation_policy'] or runtime['optimizer'] != spec['optimizer']:
            raise ValueError('Frozen runtime policy drift')
        secrets = json.loads((state / 'credentials.json').read_text())
        token = secrets['coordinator']
        seed = json.loads((state / 'seed.json').read_text())
        try:
            while True:
                finish_pending(state, campaign, runtime, manifest, token)
                snapshot = campaign.snapshot()
                ids = {l.get('inflight_candidate') for l in snapshot['lanes']}
                pending = [c for c in snapshot['candidates'] if c['candidate_id'] in ids]
                if pending:
                    evaluate(campaign, state, pending[0], secrets, runtime)
                    if args.once:
                        return {'status': 'evaluated', 'candidate_id': pending[0]['candidate_id']}
                    if any(l.get('inflight_candidate') == pending[0]['candidate_id'] for l in campaign.snapshot()['lanes']):
                        return {'status': 'evaluation_needs_review'}
                    continue
                if (state / 'STOP').exists():
                    return {'status': 'stopped'}
                plan = campaign.plan('coordinator', token)
                if plan['action'] != 'mutate':
                    return {'status': plan['action']}
                jobs = [json.loads(p.read_text()) for p in (state / 'queue-results').glob('*.json')]
                rows, cohort = observations(manifest, jobs, seed, policy_context=runtime['policy'])
                if cohort != spec['cohort_digest']:
                    raise ValueError('Training cohort drift')
                request = {'metadata': spec['optimizer'], 'dimensions': manifest['dimensions'],
                           'legal': manifest['legal'], 'observations': rows}
                selected = choose(request)
                if selected['parameters'] is None:
                    return {'status': 'space_exhausted'}
                parameters = selected['parameters']
                hashes = {p: digest(s) for p, s in render(manifest, parameters).items()}
                identity = canonical_digest(hashes)
                if any(c['content_sha256'] == identity for c in snapshot['candidates']):
                    return {'status': 'previous_candidate_needs_review'}
                parent = min((c for c in snapshot['candidates'] if c['valid']), key=lambda c: c['metrics']['total'])
                identity_id = uuid.uuid4().hex
                context = {'request': request, 'selection': selected, 'manifest_digest': spec['manifest_digest']}
                atomic_json(state / 'decisions' / (identity_id + '.json'), context)
                context_ref = freeze_context(context, Path(runtime['repo']) / 'experiments' / 'campaigns' / runtime['campaign_id'])
                decision = dict(selected['decision'], selection_origin=selected['decision']['origin'], context=context_ref)
                campaign.record_decision('coordinator', token, identity_id, decision)
                publish(campaign, state, 'topology-selected')
                proposal = {'proposal_id': identity_id, 'candidate_id': identity_id,
                    'round_id': 'topology-001', 'lane_id': 'tune', 'kind': 'mutate', 'recipe': 'tune',
                    'parents': [parent['candidate_id']], 'parameters': parameters, 'content_sha256': identity,
                    'provenance': dict(decision, heuristic_id='exact-topology-smac-v1',
                        model='SMAC3 random forest + expected improvement', model_calls=0,
                        hypothesis='Measure registered topology parameters under unchanged full correctness checks',
                        context_sha256=canonical_digest(context))}
                atomic_json(state / 'pending-topology.json', {'proposal': proposal,
                            'expected_head': git(runtime['repo'], 'rev-parse', 'HEAD')})
        except BudgetExhausted as exc:
            publish(campaign, state, 'budget-exhausted')
            return {'status': 'budget_exhausted', 'reason': str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--repo', type=Path, default=Path.cwd())
    init.add_argument('--state', type=Path, required=True)
    init.add_argument('--name', required=True)
    init.add_argument('--manifest', type=Path, required=True)
    init.add_argument('--seed-report', type=Path, required=True)
    init.add_argument('--policy-context', type=Path,
                      help='Coordinator-approved CPU/memory/checker policy for this isolated lane')
    init.add_argument('--deadline-unix', type=float, required=True)
    init.add_argument('--max-evaluations', type=int, default=10)
    init.add_argument('--host', default='amd-hackathon')
    init.add_argument('--root', default='/workspace/feyer-lab')
    init.add_argument('--publish', action='store_true')
    runner = sub.add_parser('run')
    runner.add_argument('--state', type=Path, required=True)
    runner.add_argument('--once', action='store_true')
    args = parser.parse_args()
    print(json.dumps(initialize(args) if args.command == 'init' else run(args), indent=2))


if __name__ == '__main__':
    main()
