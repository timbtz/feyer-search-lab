"""Run the registered finite DAG pilot through the existing trusted evaluator.

Controller credentials remain local. Candidate code, hypotheses, context,
responses and evaluation summaries are published on the campaign branch.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from .client import Client, TERMINAL
from .evolution_space import (DEFAULTS, DIMENSIONS, SEED_SHA, SPACE_VERSION,
    assignments, canonical, content_identity, materialize, materialize_commit,
    parse_recipe, source_from_git)
from .token_factory import TokenFactory, settings, summarize_response


def atomic_json(path, value, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if private else 0o644)
    with os.fdopen(fd, 'w') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def components():
    from .evolution import Campaign
    from .evolution_evidence import normalize_job, policy_from_job
    from .evolution_report import export_campaign, store_text_artifact
    return Campaign, normalize_job, policy_from_job, export_campaign, store_text_artifact


def initialize(args):
    Campaign, normalize_job, policy_from_job, _, _ = components()
    state = args.state.resolve()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', args.name):
        raise ValueError('Campaign name must be a simple identifier')
    if state.exists():
        raise ValueError('Use a new state directory; resume with run, not init')
    jobs = [json.loads(p.read_text()) for p in args.seed_report]
    if len(jobs) < 3 or len({j['id'] for j in jobs}) < 3:
        raise ValueError('Supply three distinct confirmed seed8 full jobs')
    policy = policy_from_job(jobs[0])
    evidence = [normalize_job(j, expected_sha=SEED_SHA, policy_context=policy) for j in jobs]
    if not all(e['eligible_full'] for e in evidence):
        raise ValueError('Every seed observation must pass full evidence validation')
    if len({e['cohort_digest'] for e in evidence}) != 1:
        raise ValueError('Seed observations must share the same complete evaluation cohort')
    selector = getattr(args, 'selector', 'qwen')
    deterministic = selector != 'qwen'
    from .search_policy import STRATEGIES, resolve
    if selector not in STRATEGIES:
        raise ValueError('Unknown search selector')
    model = None if deterministic else settings(args.env_file)[1]
    source = source_from_git(args.repo)
    materialize(source, DEFAULTS)
    prior = []
    if getattr(args, 'prior_full', None):
        if not deterministic:
            raise ValueError('Prior finite-space imports currently require a deterministic selector')
        from .discrete_search import prior_observations
        prior = prior_observations(args.prior_full, jobs[0], source, policy, normalize_job)
        if any(e['cohort_digest'] != evidence[0]['cohort_digest'] for _, _, _, e in prior):
            raise ValueError('Prior evidence does not match the frozen full cohort')
    observed = {content_identity(source)} | {digest for _, digest, _, _ in prior}
    selection_policy = resolve(selector, len(assignments()) - len(observed), args.max_evaluations)
    selector = selection_policy['effective']
    optimizer = None
    if selector == 'smac':
        from .smac_transport import invoke, verify_metadata
        host = getattr(args, 'smac_host', None)
        endpoint = None
        if host:
            endpoint = {'host': host, 'python': args.smac_python, 'root': args.smac_root}
        elif getattr(args, 'smac_python', None) or getattr(args, 'smac_root', None):
            raise ValueError('Remote SMAC paths require --smac-host')
        seed = getattr(args, 'search_seed', 0)
        if type(seed) is not int or not 0 <= seed < 2**31:
            raise ValueError('Search seed must be an integer between 0 and 2**31-1')
        optimizer = {'metadata': verify_metadata(invoke({'action': 'metadata'}, endpoint)),
                     'endpoint': endpoint, 'seed': seed}
    deadline = time.time() + args.minutes * 60
    if getattr(args, 'deadline_unix', None) is not None:
        deadline = min(deadline, args.deadline_unix)
    if not time.time() < deadline < float('inf'):
        raise ValueError('Campaign requires a finite future deadline')
    if git(args.repo, 'status', '--porcelain'):
        raise ValueError('Initialize from a clean controller checkout')
    branch = 'explore/' + args.name
    worktree = state / 'worktree'
    state.mkdir(parents=True)
    subprocess.run(['git', '-C', str(args.repo), 'worktree', 'add', '-b', branch,
                    str(worktree), SEED_SHA], check=True)
    atomic_json(state / 'runtime.json', {'repo': str(worktree), 'branch': branch,
        'campaign_id': args.name, 'policy': policy, 'env_file': str(args.env_file.resolve()),
        'host': args.host, 'root': args.root, 'publish': args.publish,
        'selector': selector, 'optimizer': optimizer})
    campaign = Campaign(state / 'campaign.sqlite3')
    spec = {'campaign_id': args.name, 'space_version': SPACE_VERSION,
            'controller_commit': git(Path(__file__).resolve().parents[1], 'rev-parse', 'HEAD'),
            'budget': {'max_proposals': 1000, 'max_evaluations': args.max_evaluations,
                       'max_model_calls': 0 if deterministic else args.max_model_calls,
                       'deadline_unix': deadline},
            'objective': {'primary': 'total', 'direction': 'minimize',
                          'pareto_axes': ['compilation', 'runtime', 'peak_rss_bytes'],
                          'full_workload': {'frequencies': 101, 'variables': 193,
                                            'precision': 'float64/complex128'}},
            'selector': selector,
            'selection_policy': selection_policy, 'optimizer': optimizer,
            'model_manifest': {'qwen': {'provider': 'amd-token-factory', 'model': model},
                'strong': {'codex': 'inherit designated Codex configuration',
                           'claude': 'claude-opus-5-5', 'automatic_launch': False}},
            'evaluation_policy': policy, 'cohort_digest': evidence[0]['cohort_digest'], 'seed_sha': SEED_SHA,
            'initial_seed_author': 'validated Codex seed8, three fresh full measurements',
            'guidance_policy': 'New operators require a strong-agent proposal and coordinator-frozen new round; no automatic budget extension'}
    if deterministic:
        spec['model_manifest'] = {'selection': {'implementation': 'lab.smac_search' if selector == 'smac' else 'lab.discrete_search',
                                               'selector': selector, 'model_calls': 0}}
    token = campaign.initialize(spec, 'coordinator')
    secrets = {'coordinator': token}
    atomic_json(state / 'credentials.json', secrets, private=True)
    for owner in (() if deterministic else ('qwen-checkpoint', 'qwen-mapping', 'qwen-joint')):
        secrets[owner] = campaign.grant('coordinator', token, owner, 'qwen')
        atomic_json(state / 'credentials.json', secrets, private=True)
    round_spec = {'round_id': 'round-001', 'dimensions': DIMENSIONS,
        'recipes': {'checkpoint': {'dimensions': ['checkpoint', 'prevent_cse']},
                    'mapping': {'dimensions': ['map_batch_size']}},
        'lanes': {'checkpoint': {'owner': 'qwen-checkpoint', 'dimensions': ['checkpoint', 'prevent_cse'], 'max_proposals': 1000},
                  'mapping': {'owner': 'qwen-mapping', 'dimensions': ['map_batch_size'], 'max_proposals': 1000}},
        'progress': {'relative': 0.01, 'absolute': 0.02},
        'budget': {'max_proposals': 1000, 'max_evaluations': args.max_evaluations},
        'materializer_version': SPACE_VERSION, 'constraints': ['not checkpoint implies not prevent_cse'],
        'seed_parameters': DEFAULTS}
    if deterministic:
        round_spec['recipes'] = {'discrete': {'dimensions': list(DIMENSIONS)}}
        round_spec['lanes'] = {'discrete': {'owner': 'coordinator', 'dimensions': list(DIMENSIONS),
            'max_proposals': len(assignments()), 'stall_limit': len(assignments())}}
        round_spec['selector'] = selector
    campaign.add_round('coordinator', token, round_spec)
    campaign.propose('coordinator', token, {'proposal_id': 'seed8', 'candidate_id': 'seed8',
        'round_id': 'round-001', 'lane_id': 'discrete' if deterministic else 'checkpoint', 'kind': 'seed', 'parents': [],
        'parameters': DEFAULTS, 'content_sha256': content_identity(source), 'commit_sha': SEED_SHA,
        'provenance': {'heuristic_id': 'import-confirmed-strong-agent-seed', 'model': spec['initial_seed_author']}})
    for item in evidence:
        campaign.observe('coordinator', token, 'seed8', item)
    for parameters, digest, job, item in prior:
        existing = next((c for c in campaign.snapshot()['candidates'] if c['content_sha256'] == digest), None)
        if existing:
            if existing['commit_sha'] != job['sha']:
                raise ValueError('Equal content at a different commit cannot overwrite imported provenance')
            candidate_id = existing['candidate_id']
        else:
            candidate_id = 'import-' + job['sha']
            campaign.propose('coordinator', token, {'proposal_id': candidate_id,
                'candidate_id': candidate_id, 'round_id': 'round-001', 'lane_id': 'discrete',
                'kind': 'seed', 'parents': [], 'parameters': parameters,
                'content_sha256': digest, 'commit_sha': job['sha'],
                'provenance': {'heuristic_id': 'import-exact-full-evidence', 'source_job': job['id'],
                               'source_branch': job.get('branch'), 'model_calls': 0}})
        campaign.observe('coordinator', token, candidate_id, item)
        atomic_json(state / 'queue-results' / (job['id'] + '.json'), job)
    atomic_json(state / 'credentials.json', secrets, private=True)
    publish(campaign, state, checkpoint='initialized')
    return {'campaign': args.name, 'state': str(state), 'branch': branch,
            'deadline_unix': spec['budget']['deadline_unix'], 'status': 'initialized'}


def publish(campaign, state, checkpoint):
    _, _, _, export_campaign, _ = components()
    runtime = json.loads((state / 'runtime.json').read_text())
    repo = Path(runtime['repo'])
    snapshot = campaign.snapshot()
    exported = export_campaign(snapshot, campaign.events(), repo / 'experiments' / 'campaigns',
                               context=campaign.context())
    relative = 'experiments/campaigns/' + runtime['campaign_id']
    git(repo, 'add', '--', relative)
    staged = git(repo, 'diff', '--cached', '--name-only').splitlines()
    if any(not name.startswith(relative + '/') for name in staged):
        raise ValueError('Refusing to commit staged changes outside owned campaign records')
    if subprocess.run(['git', '-C', str(repo), 'diff', '--cached', '--quiet']).returncode:
        git(repo, 'commit', '-m', 'Record DAG campaign ' + checkpoint)
    if runtime['publish']:
        subprocess.run(['git', '-C', str(repo), '-c', 'credential.helper=!gh auth git-credential',
                        'push', '-u', 'origin', runtime['branch']], check=True)
    return exported


def evaluate(campaign, state, candidate, secrets, runtime):
    _, normalize_job, _, _, _ = components()
    client = Client(runtime['host'], runtime['root'])
    cid, sha = candidate['candidate_id'], candidate['commit_sha']
    for profile in ('screen', 'full'):
        reservation = campaign.reserve_evaluation('coordinator', secrets['coordinator'], cid, profile)
        if reservation.get('evidence_id'):
            if profile == 'screen':
                old_job = client.request({'action': 'show', 'id': reservation['job_id']})
                old_evidence = normalize_job(old_job, expected_sha=sha, policy_context=runtime['policy'])
                if not old_evidence.get('screen_passed'):
                    return
            continue
        job = client.submit(runtime['repo'], runtime['branch'], candidate['owner'],
            candidate['lane_id'], candidate.get('provenance', {}).get('hypothesis', 'Registered finite-space experiment'),
            profile=profile, sha=sha, publish=runtime['publish'], request_id=reservation['request_id'])
        campaign.bind_evaluation('coordinator', secrets['coordinator'], reservation['request_id'], job['id'])
        # Admission was budgeted before dispatch. Drain this exact job even if the
        # deadline passes; never launch a second worker or resubmit with a new ID.
        job = client.wait(job['id'], timeout=1800)
        evidence = normalize_job(job, expected_sha=sha, policy_context=runtime['policy'])
        artifact = state / 'queue-results' / (job['id'] + '.json')
        atomic_json(artifact, job)
        campaign.observe('coordinator', secrets['coordinator'], cid, evidence)
        publish(campaign, state, checkpoint=cid + '-' + profile)
        if profile == 'screen' and not evidence.get('screen_passed'):
            return


def finish_pending_recipe(campaign, state, secrets, runtime):
    """Recover the recorded choice before another model call can be admitted."""
    path = state / 'pending-recipe.json'
    if not path.exists():
        return
    pending = json.loads(path.read_text())
    proposal = pending['proposal']
    existing = next((c for c in campaign.snapshot()['candidates']
                     if c['candidate_id'] == proposal['candidate_id']), None)
    if existing is None:
        repo = Path(runtime['repo'])
        head = git(repo, 'rev-parse', 'HEAD')
        if 'commit_sha' not in proposal:
            if head == pending['expected_head']:
                rendered = materialize_commit(repo, proposal['parameters'], runtime['branch'], head,
                                              campaign_id=runtime['campaign_id'])
                proposal['commit_sha'] = rendered['sha']
            else:
                # Exactly one clean source-only child commit may have landed
                # before the coordinator persisted its returned SHA.
                changed = git(repo, 'diff', '--name-only', pending['expected_head'], head).splitlines()
                if (git(repo, 'status', '--porcelain') or
                        git(repo, 'rev-parse', 'HEAD^') != pending['expected_head'] or
                        changed != ['differometor/simulate.py'] or
                        content_identity((repo / 'differometor/simulate.py').read_text()) != proposal['content_sha256']):
                    raise ValueError('Interrupted materialization needs ownership review; no new model call dispatched')
                proposal['commit_sha'] = head
            atomic_json(path, pending)
        campaign.propose(pending['owner'], secrets[pending['owner']], proposal)
    publish(campaign, state, checkpoint='candidate-proposed')
    path.unlink()


def run(args):
    from .evolution import BudgetExhausted
    with (args.state.resolve() / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return _run_owned(args)
        except BudgetExhausted as exc:
            # A screen may finish at the deadline. Keep its exact evidence and
            # pending full stage; do not launch a new job or reset the budget.
            Campaign, *_ = components()
            publish(Campaign(args.state / 'campaign.sqlite3'), args.state, checkpoint='budget-exhausted')
            return {'status': 'budget_exhausted', 'reason': str(exc)}


def _run_owned(args):
    Campaign, _, _, _, store_text_artifact = components()
    state = args.state.resolve()
    runtime = json.loads((state / 'runtime.json').read_text())
    secrets = json.loads((state / 'credentials.json').read_text())
    campaign = Campaign(state / 'campaign.sqlite3')
    repo = Path(runtime['repo'])
    selector = runtime.get('selector', 'qwen')
    if selector != campaign.snapshot()['campaign']['spec'].get('selector', 'qwen'):
        raise ValueError('Selector differs from frozen campaign specification')
    if runtime.get('optimizer') != campaign.snapshot()['campaign']['spec'].get('optimizer'):
        raise ValueError('Optimizer runtime differs from frozen campaign specification')
    while True:
        finish_pending_recipe(campaign, state, secrets, runtime)
        current = campaign.snapshot()
        inflight = {lane.get('inflight_candidate') for lane in current['lanes'] if lane.get('inflight_candidate')}
        pending = [c for c in current['candidates'] if c['candidate_id'] in inflight]
        if pending:
            evaluate(campaign, state, pending[0], secrets, runtime)
            if args.once:
                return {'status': 'evaluated', 'candidate_id': pending[0]['candidate_id']}
            after = campaign.snapshot()
            if any(lane.get('inflight_candidate') == pending[0]['candidate_id'] for lane in after['lanes']):
                return {'status': 'evaluation_needs_review', 'candidate_id': pending[0]['candidate_id']}
            continue
        if (state / 'STOP').exists():
            publish(campaign, state, checkpoint='operator-stop')
            return {'status': 'stopped', 'reason': 'Operator STOP file; pending work drained'}
        plan = campaign.plan('coordinator', secrets['coordinator'])
        campaign.record_decision('coordinator', secrets['coordinator'], uuid.uuid4().hex,
                                 {'policy': 'frozen-lane-three-strike-v1' if selector == 'qwen'
                                  else 'finite-space-' + selector + '-v1', 'plan': plan})
        atomic_json(state / 'latest-plan.json', plan)
        snapshot = campaign.snapshot()
        if plan['action'] == 'wait':
            pending = [c for c in snapshot['candidates'] if c['status'] in ('proposed', 'screened', 'evaluating')]
            if not pending:
                return {'status': 'needs_review', 'plan': plan}
            evaluate(campaign, state, pending[0], secrets, runtime)
            if args.once:
                return {'status': 'evaluated', 'candidate_id': pending[0]['candidate_id']}
            continue
        if plan['action'] == 'combine':
            if selector != 'qwen':
                publish(campaign, state, checkpoint='space-exhausted')
                return {'status': 'space_exhausted', 'selector': selector}
            # Joint optimization is a new frozen round over the same registered
            # dimensions. No arbitrary source merge and no budget extension.
            if any(r['round_id'] == 'round-002-joint' for r in snapshot['rounds']):
                publish(campaign, state, checkpoint='guidance-required')
                return {'status': 'guidance_required', 'plan': plan}
            joint = {'round_id': 'round-002-joint', 'dimensions': DIMENSIONS,
                'recipes': {'joint': {'dimensions': list(DIMENSIONS)}},
                'lanes': {'joint': {'owner': 'qwen-joint', 'dimensions': list(DIMENSIONS), 'max_proposals': 1000}},
                'progress': {'relative': 0.01, 'absolute': 0.02},
                'budget': {'max_proposals': 1000, 'max_evaluations': snapshot['campaign']['spec']['budget']['max_evaluations']},
                'materializer_version': SPACE_VERSION, 'combination_parents': plan['parent_candidates'],
                'reason': 'Prior lanes stalled or exhausted; jointly optimize registered choices'}
            campaign.add_round('coordinator', secrets['coordinator'], joint)
            publish(campaign, state, checkpoint='joint-round-frozen')
            continue
        if plan['action'] != 'mutate':
            publish(campaign, state, checkpoint=plan['action'])
            return {'status': plan['action'], 'plan': plan}
        active_round = next(r['spec'] for r in snapshot['rounds'] if r['round_id'] == plan['round_id'])
        if active_round.get('materializer_version', SPACE_VERSION) != SPACE_VERSION:
            raise ValueError('This runner cannot execute a different materializer version')
        parents = [c for c in snapshot['candidates'] if c['candidate_id'] in plan['parent_candidates'] and c['valid']]
        base_id = plan.get('base_candidate') or 'seed8'
        base = next((c for c in snapshot['candidates'] if c['candidate_id'] == base_id), None)
        if base is not None:
            parents = [c for c in parents if all(c['parameters'][k] == base['parameters'][k]
                        for k in DIMENSIONS if k not in plan['dimensions'])]
        if not parents:
            raise ValueError('No validated parent for planned mutation')
        parent = min(parents, key=lambda c: c['metrics']['total'])
        options = assignments(parent['parameters'], plan['dimensions'])
        source = source_from_git(repo)
        seen = {c['content_sha256'] for c in snapshot['candidates']}
        options = [p for p in options if content_identity(materialize(source, p)) not in seen]
        if not options:
            campaign.lane_exhausted('coordinator', secrets['coordinator'], plan['round_id'], plan['lane_id'])
            publish(campaign, state, checkpoint=plan['lane_id'] + '-exhausted')
            if selector != 'qwen':
                return {'status': 'space_exhausted', 'selector': selector}
            continue
        if selector != 'qwen':
            from .discrete_search import select, incumbent
            thresholds = active_round['progress']
            optimizer_request = None
            if selector == 'smac':
                from .smac_search import training_observations
                from .smac_transport import invoke
                optimizer = runtime['optimizer']
                optimizer_request = {'metadata': optimizer['metadata'], 'seed': optimizer['seed'],
                    'options': options, 'observations': training_observations(snapshot)}
                selected = invoke(optimizer_request, optimizer['endpoint'])
                parameters, decision = selected['parameters'], selected['decision']
                if canonical(parameters) not in {canonical(p) for p in options}:
                    raise ValueError('SMAC returned an already-seen or unregistered configuration')
                if decision.get('metadata') != optimizer['metadata']:
                    raise ValueError('SMAC response differs from frozen runtime metadata')
                parent = incumbent(parents, relative=thresholds['relative'], absolute=thresholds['absolute'])
            else:
                parent, parameters, decision = select(selector, parents, options,
                    relative=thresholds['relative'], absolute=thresholds['absolute'])
            from .evolution_report import freeze_context
            directory = repo / 'experiments' / 'campaigns' / runtime['campaign_id']
            context = {'selector': selector, 'parent': parent['candidate_id'],
                       'parameters': parameters, 'options': options, 'decision': decision,
                       'optimizer_request': optimizer_request,
                       'observations': [{'candidate_id': c['candidate_id'],
                            'parameters': c['parameters'], 'valid': c['valid'],
                            'metrics': c.get('metrics')} for c in snapshot['candidates']]}
            context_ref = freeze_context(context, directory)
            proposal_id = uuid.uuid4().hex
            campaign.record_decision('coordinator', secrets['coordinator'], proposal_id,
                                     dict(decision, context=context_ref))
            publish(campaign, state, checkpoint=selector + '-selection')
            expected_head = git(repo, 'rev-parse', 'HEAD')
            proposal = {'proposal_id': proposal_id, 'candidate_id': proposal_id,
                'round_id': plan['round_id'], 'lane_id': plan['lane_id'], 'kind': 'mutate',
                'parents': [parent['candidate_id']], 'recipe': 'discrete', 'parameters': parameters,
                'content_sha256': content_identity(materialize(source, parameters)),
                'provenance': dict(decision, operator_version=SPACE_VERSION,
                    parameters_before=parent['parameters'], context=context_ref,
                    context_sha256=context_ref['sha256'], git_parent_sha=expected_head,
                    controller_commit=git(Path(__file__).resolve().parents[1], 'rev-parse', 'HEAD'),
                    model_calls=0, target_symbols=['simulate._evaluate_component', 'simulate.update'])}
            atomic_json(state / 'pending-recipe.json', {'owner': plan['owner'], 'proposal': proposal,
                                                       'expected_head': expected_head})
            finish_pending_recipe(campaign, state, secrets, runtime)
            candidate = next(c for c in campaign.snapshot()['candidates'] if c['candidate_id'] == proposal_id)
            evaluate(campaign, state, candidate, secrets, runtime)
            if args.once:
                return {'status': 'evaluated', 'candidate_id': proposal_id, 'selector': selector}
            continue
        exported = publish(campaign, state, checkpoint='proposal-context')
        source_context_sha = exported['context_sha256']
        directory = repo / 'experiments' / 'campaigns' / runtime['campaign_id']
        from .evolution_report import freeze_context
        supplied_context = {'lane': plan['lane_id'], 'parent': parent['candidate_id'],
            'parent_metrics': parent['metrics'], 'parent_parameters': parent['parameters'],
            'choices': options, 'source_context_sha256': source_context_sha,
            'recent_outcomes': [{'parameters': c['parameters'], 'status': c['status'],
                                 'metrics': c.get('metrics')} for c in snapshot['candidates'][-6:]]}
        context_ref = freeze_context(supplied_context, directory)
        context_sha = context_ref['sha256']
        prompt = ('Pick one experiment from choices. Return exactly {"choice":0,"rationale":"at most twelve words"}, '
            'using your selected integer. No Markdown or additional text. Keep the rationale under twelve words. '
            'These are untested alternatives; do not assert correctness or speed. Objective: lower complete first-run time '
            'while passing our fixed checks.\n'
            + canonical(supplied_context))
        call_id = uuid.uuid4().hex
        prompt_ref = store_text_artifact(prompt, directory, kind='prompts')
        key, model = settings(runtime['env_file'])
        if model != snapshot['campaign']['spec']['model_manifest']['qwen']['model']:
            raise ValueError('Model identity changed after campaign freeze')
        campaign.record_model_call('coordinator', secrets['coordinator'], call_id,
            {'actor': plan['owner'], 'model': snapshot['campaign']['spec']['model_manifest']['qwen'],
             'context_sha256': context_sha, 'prompt': prompt_ref, 'max_tokens': 1024,
             'controller_commit': git(Path(__file__).resolve().parents[1], 'rev-parse', 'HEAD'),
             'reasoning_effort': 'low', 'temperature': 0})
        publish(campaign, state, checkpoint='model-call-reserved')
        response = TokenFactory(key, model, timeout=50).chat([{'role': 'user', 'content': prompt}], max_tokens=1024)
        choices = response.get('data', {}).get('choices') or []
        content = (choices[0].get('message', {}).get('content') or '') if choices else ''
        response_ref = store_text_artifact(json.dumps({'call_id': call_id, 'prompt': prompt_ref,
                                                      'context_sha256': context_sha,
                                                      'summary': summarize_response(response),
                                                      'content': content}, allow_nan=False), directory, kind='responses')
        atomic_json(state / 'model-calls' / (call_id + '.json'),
                    {'prompt': prompt_ref, 'response': response_ref, 'summary': summarize_response(response)})
        try:
            if response['status'] != 200:
                raise ValueError('Provider request did not succeed')
            parameters, reason = parse_recipe(content, options)
        except ValueError as exc:
            # Model failures consume their reservation but never a scientific strike.
            campaign.record_model_outcome('coordinator', secrets['coordinator'], call_id,
                {'response': response_ref, 'summary': summarize_response(response),
                 'recipe_valid': False, 'error': str(exc)})
            publish(campaign, state, checkpoint='model-call-failed')
            return {'status': 'model_error', 'call_id': call_id, 'error': str(exc)}
        campaign.record_model_outcome('coordinator', secrets['coordinator'], call_id,
            {'response': response_ref, 'summary': summarize_response(response), 'recipe_valid': True})
        # Publish prompt/response files before rendering so the worktree is clean.
        publish(campaign, state, checkpoint='recipe-received')
        expected_head = git(repo, 'rev-parse', 'HEAD')
        round_spec = next(r['spec'] for r in snapshot['rounds'] if r['round_id'] == plan['round_id'])
        # First joint proposal combines the frozen sources. Subsequent trials
        # refine a validated joint child, keeping that improvement in lineage.
        joint_children = [c for c in parents if c['round_id'] == plan['round_id'] and c['kind'] != 'seed']
        if round_spec.get('combination_parents') and not joint_children:
            parent_ids = round_spec['combination_parents']
            before = next(c['parameters'] for c in snapshot['candidates'] if c['candidate_id'] == parent_ids[0])
        else:
            parent_ids, before = [parent['candidate_id']], parent['parameters']
        proposal = {'proposal_id': call_id, 'candidate_id': call_id, 'round_id': plan['round_id'],
            'lane_id': plan['lane_id'], 'kind': 'combine' if len(parent_ids) > 1 else 'mutate',
            'parents': parent_ids, 'recipe': plan['lane_id'], 'parameters': parameters,
            'content_sha256': content_identity(materialize(source, parameters)),
            'provenance': {'heuristic_id': 'finite-menu-guided-selection-v1',
                'operator_version': SPACE_VERSION, 'hypothesis': reason,
                'parameters_before': before, 'model': model,
                'context_sha256': context_sha, 'prompt': prompt_ref, 'response': response_ref,
                'source_context_sha256': source_context_sha, 'context': context_ref,
                'model_call_id': call_id, 'usage': summarize_response(response).get('usage'),
                'git_parent_sha': expected_head, 'target_symbols': ['simulate._evaluate_component', 'simulate.update']}}
        atomic_json(state / 'pending-recipe.json', {'owner': plan['owner'], 'proposal': proposal,
                                                   'expected_head': expected_head})
        finish_pending_recipe(campaign, state, secrets, runtime)
        candidate = next(c for c in campaign.snapshot()['candidates'] if c['candidate_id'] == call_id)
        evaluate(campaign, state, candidate, secrets, runtime)
        if args.once:
            return {'status': 'evaluated', 'candidate_id': call_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--state', required=True, type=Path)
    init.add_argument('--repo', type=Path, default=Path.cwd())
    init.add_argument('--name', required=True)
    init.add_argument('--seed-report', type=Path, action='append', required=True)
    init.add_argument('--env-file', type=Path, default=Path('.env'))
    init.add_argument('--minutes', type=float, default=15)
    init.add_argument('--max-evaluations', type=int, default=12)
    init.add_argument('--max-model-calls', type=int, default=8)
    from .search_policy import STRATEGIES
    init.add_argument('--selector', choices=STRATEGIES, default='auto')
    init.add_argument('--search-seed', type=int, default=0)
    init.add_argument('--smac-host', help='Optional SSH alias for the isolated SMAC environment')
    init.add_argument('--smac-python', help='Absolute remote controller Python path')
    init.add_argument('--smac-root', help='Absolute remote directory containing this version of lab/')
    init.add_argument('--deadline-unix', type=float, help='Optional earlier absolute deadline, e.g. a campaign handoff')
    init.add_argument('--prior-full', type=Path, action='append', default=[],
                      help='Import a full result for an exact registered implementation, preserving its SHA')
    init.add_argument('--host', default='amd-hackathon')
    init.add_argument('--root', default='/workspace/feyer-lab')
    init.add_argument('--publish', action='store_true')
    execute = sub.add_parser('run')
    execute.add_argument('--state', type=Path, required=True)
    execute.add_argument('--once', action='store_true')
    status = sub.add_parser('status')
    status.add_argument('--state', type=Path, required=True)
    export = sub.add_parser('export')
    export.add_argument('--state', type=Path, required=True)
    freeze = sub.add_parser('freeze-round')
    freeze.add_argument('--state', type=Path, required=True)
    freeze.add_argument('--spec', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'init':
        if args.minutes <= 0 or args.max_evaluations < 1 or args.max_model_calls < 0 or (args.selector == 'qwen' and args.max_model_calls < 1):
            raise ValueError('Positive bounded campaign budgets required')
        result = initialize(args)
    elif args.command == 'run':
        result = run(args)
    elif args.command == 'status':
        Campaign, *_ = components()
        result = Campaign(args.state / 'campaign.sqlite3').snapshot()
    else:
        Campaign, *_ = components()
        campaign = Campaign(args.state / 'campaign.sqlite3')
        if args.command == 'freeze-round':
            secrets = json.loads((args.state / 'credentials.json').read_text())
            campaign.add_round('coordinator', secrets['coordinator'], json.loads(args.spec.read_text()))
        result = publish(campaign, args.state, checkpoint=args.command)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
