"""Source-backed research records and a read-only projection of executor evidence.

No scheduling, source parsing, winner selection or timing aggregation occurs here.
"""
import copy
import hashlib
import json
import re

from .phase_report import GROUPS
from .queue import TERMINAL_STATUSES
from .worker import PHASE_CATEGORIES

SCHEMA = 'feyer-research-record-v1'
PHASES = set(PHASE_CATEGORIES) | set(GROUPS)
STOPPED = {'stalled', 'budget_exhausted', 'deadline_reached', 'menu_exhausted', 'failed'}
STATUSES = STOPPED | {'proposed', 'current', 'checkpoint', 'evaluating', 'evaluated', 'completed', 'unknown'}
SHA = re.compile(r'[0-9a-f]{40}')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def exact_sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def validate_record(value):
    r = copy.deepcopy(value)
    if not isinstance(r, dict) or r.get('schema') != SCHEMA:
        raise ValueError('Unsupported research record schema')
    if not isinstance(r.get('record_id'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', r['record_id']):
        raise ValueError('Research record needs a stable simple ID')
    if r.get('kind') not in ('explore', 'refine', 'combine', 'diagnose') or r.get('status') not in STATUSES:
        raise ValueError('Unknown research kind or status; no local-optimum verdict exists')
    for key in ('hypothesis', 'change_summary', 'source_ref'):
        if not isinstance(r.get(key), str) or not r[key].strip():
            raise ValueError('Research record needs ' + key)
    if not isinstance(r.get('source_digest'), str) or not re.fullmatch('[0-9a-f]{64}', r['source_digest']):
        raise ValueError('Source digest must identify the reviewed artifact')
    executor = r.get('executor')
    if not isinstance(executor, dict) or executor.get('kind') not in ('supervisor', 'campaign', 'manual') or not isinstance(executor.get('id'), str) or not executor['id']:
        raise ValueError('An explicit executor identity is required')
    phases = r.get('target_phases', [])
    if not isinstance(phases, list) or any(not isinstance(p, str) or p not in PHASES for p in phases) or len(phases) != len(set(phases)):
        raise ValueError('Target phases must use canonical measured phase/group keys')
    r['target_phases'] = phases
    parents = r.get('parents', [])
    if not isinstance(parents, list) or any(not exact_sha(p) for p in parents) or len(parents) != len(set(parents)):
        raise ValueError('Scientific parents must be distinct exact SHAs')
    r['parents'] = parents
    child = r.get('candidate_sha')
    if child is not None and (not exact_sha(child) or child in parents):
        raise ValueError('Candidate must be an exact SHA distinct from its scientific parents')
    if r['kind'] == 'combine' and len(parents) < 2:
        raise ValueError('Combination needs two explicitly declared scientific parents')
    reason = r.get('stopping_reason')
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError('Stopping reason must be nonempty text or null')
    if r['status'] in STOPPED and reason is None:
        raise ValueError('Stopped research needs its recorded stopping reason')
    if r['status'] == 'menu_exhausted':
        menu = r.get('menu', {})
        if (not isinstance(menu, dict) or not isinstance(menu.get('manifest_digest'), str)
                or not re.fullmatch('[0-9a-f]{64}', menu['manifest_digest'])
                or type(menu.get('legal_count')) is not int or menu['legal_count'] < 1
                or type(menu.get('covered_count')) is not int or menu['covered_count'] != menu['legal_count']):
            raise ValueError('Menu exhaustion needs a frozen manifest and complete finite coverage')
    for key in ('feedback_ref', 'checkpoint', 'next_input'):
        artifact = r.get(key)
        if artifact is not None and (not isinstance(artifact, dict)
                or not isinstance(artifact.get('artifact_ref'), str) or not artifact['artifact_ref']
                or not isinstance(artifact.get('artifact_digest'), str)
                or not re.fullmatch('[0-9a-f]{64}', artifact['artifact_digest'])):
            raise ValueError('Artifact references require a location and SHA-256 digest')
    if r.get('iteration') is not None and (type(r['iteration']) is not int or r['iteration'] < 1):
        raise ValueError('Iteration must be a positive integer when recorded')
    receipt = r.get('input_receipt')
    if receipt is not None and (not isinstance(receipt, dict) or not isinstance(receipt.get('path'), str)
            or not isinstance(receipt.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', receipt['sha256'])):
        raise ValueError('Dispatched input receipt needs a local path and exact digest')
    for key in ('evaluations', 'target_evidence'):
        rows = r.setdefault(key, [])
        if not isinstance(rows, list):
            raise ValueError('Evidence references must be lists')
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get('job_id'), str) or not row['job_id']
                    or not exact_sha(row.get('candidate_sha')) or row.get('profile') not in ('screen', 'full')):
                raise ValueError('Each evaluation reference needs an exact job, candidate and profile')
            if key == 'evaluations' and row['candidate_sha'] != child:
                raise ValueError('Evaluation does not belong to the recorded candidate')
            if key == 'target_evidence' and child is not None and row['candidate_sha'] == child:
                raise ValueError('A candidate cannot be motivated by its own later evaluation')
    return r


def from_feedback(feedback, executor_id, source_ref):
    """Convert explicit supervisor fields; old missing phase declarations stay empty."""
    response = feedback.get('agent_response') or {}
    provenance = feedback.get('provenance') or {}
    source_digest = digest(feedback)
    record = dict(schema=SCHEMA, record_id='feedback-' + source_digest,
                  executor={'kind': 'supervisor', 'id': executor_id}, kind='explore',
                  status='completed', candidate_sha=feedback.get('candidate_sha'),
                  parents=provenance.get('parent_candidates') or [],
                  target_phases=feedback.get('target_phases') or [],
                  hypothesis=response.get('hypothesis') or 'Hypothesis not recorded',
                  change_summary=response.get('summary') or 'Change summary not recorded',
                  stopping_reason=None, source_ref=source_ref, source_digest=source_digest,
                  source_digest_kind='canonical_json_sha256',
                  feedback_ref=dict(artifact_ref=source_ref, artifact_digest=source_digest,
                                    digest_kind='canonical_json_sha256'),
                  session_id=(feedback.get('agent_context') or {}).get('thread_id'),
                  iteration=feedback.get('iteration'), checkpoint=feedback.get('checkpoint'),
                  next_input=feedback.get('next_input'),
                  input_receipt=feedback.get('input_receipt'),
                  evaluations=[], target_evidence=feedback.get('target_evidence') or [])
    combined = provenance.get('combined_candidates')
    if combined is not None and not isinstance(combined, list):
        raise ValueError('Declared combination inputs must be a list')
    if combined:
        if not isinstance(combined, list) or set(combined) != set(record['parents']) or len(combined) < 2:
            raise ValueError('Declared combination inputs do not match scientific parents')
        record['kind'] = 'combine'
    # Neither a boolean stop request nor a failed candidate proves branch exhaustion.
    for profile in ('screen', 'full'):
        job = feedback.get(profile)
        if job is None:
            continue
        if not isinstance(job, dict) or job.get('sha') != record['candidate_sha'] or job.get('profile') != profile:
            raise ValueError('Feedback job identity does not match the exact candidate/profile')
        record['evaluations'].append(dict(job_id=job.get('id'), candidate_sha=job['sha'], profile=profile))
        if job.get('status') not in TERMINAL_STATUSES:
            record['status'] = 'evaluating' if job.get('status') in ('queued', 'running') else 'unknown'
    if not record['evaluations']:
        record['status'] = 'unknown'
    return validate_record(record)


def build_lineage(snapshot):
    """Project declared ancestry and exact job references; retain explicit unknowns."""
    nodes, edges, control_edges, records, issues = {}, {}, {}, {}, []
    ancestry = {}
    known = {}
    team = snapshot.get('team_search') or {}
    for obs in (team.get('observations') or {}).values():
        e = obs.get('evidence') or {}
        key = (e.get('job_id'), e.get('candidate_sha'), e.get('profile'))
        known.setdefault(key, []).append(obs)

    def node(identity, kind, **fields):
        if identity not in nodes:
            nodes[identity] = dict(id=identity, kind=kind, **fields)
        return identity

    def edge(source, target, kind, reference, control=False):
        if source == target:
            issues.append('Self-edge rejected: ' + source)
            return
        key = (source, target, kind)
        destination = control_edges if control else edges
        item = destination.setdefault(key, dict(source=source, target=target, kind=kind, sources=[]))
        if reference not in item['sources']:
            item['sources'].append(reference)

    def candidate(sha):
        if not exact_sha(sha):
            raise ValueError('Missing exact candidate SHA')
        return node('candidate:' + sha, 'candidate', candidate_sha=sha)

    def parents(parent_shas, child, source, combination=False):
        for parent in parent_shas:
            if not exact_sha(parent):
                issues.append('Invalid parent in ' + source)
                continue
            pending, seen = [child], set()
            while pending:
                item = pending.pop()
                if item in seen:
                    continue
                seen.add(item)
                pending.extend(ancestry.get(item, ()))
            if parent in seen:
                issues.append('Scientific cycle rejected in ' + source)
                continue
            ancestry.setdefault(parent, set()).add(child)
            edge(candidate(parent), candidate(child),
                 'hypothesis_combination' if combination else 'scientific_parent', source)

    def evaluation(ref, instance=None, cohort=None, context=None, evidence=None, checks=None):
        sha, job_id, profile = ref.get('candidate_sha'), ref.get('job_id'), ref.get('profile')
        if not exact_sha(sha) or not isinstance(job_id, str) or not job_id or profile not in ('screen', 'full'):
            raise ValueError('Evaluation reference is missing an exact identity')
        matches = known.get((job_id, sha, profile), [])
        if instance is None and len(matches) == 1:
            obs = matches[0]
            instance, evidence = obs.get('instance'), obs['evidence']
            cohort, context = evidence.get('cohort_digest'), obs.get('comparison_context')
        # Composite identity prevents a conflicting job/SHA/profile join.
        identity = 'evaluation:' + digest([instance, job_id, sha, profile])
        node(identity, 'evaluation', job_id=job_id, candidate_sha=sha, profile=profile,
             instance=instance, cohort_digest=cohort, comparison_context=context,
             evidence=evidence, checks=checks or (evidence or {}).get('checks', {}),
             outcome=(evidence or {}).get('category', 'unknown'))
        edge(candidate(sha), identity, 'evaluation', 'exact job/SHA/profile')
        return identity

    for key, record in sorted((team.get('research_records') or {}).items()):
        try:
            r = validate_record(record)
            if key != r['record_id']:
                raise ValueError('Research record ID differs from its key')
            records[key] = r
            identity = node('research:' + key, 'research', **{k: r.get(k) for k in
                ('candidate_sha', 'target_phases', 'hypothesis', 'change_summary', 'executor',
                 'status', 'stopping_reason', 'source_ref', 'source_digest', 'menu',
                 'feedback_ref', 'checkpoint', 'next_input', 'session_id', 'iteration', 'input_receipt')})
            nodes[identity]['research_kind'] = r['kind']
            receipt = r.get('input_receipt')
            if receipt:
                iid = node('input:' + receipt['sha256'], 'dispatched_input',
                           receipt=receipt, available_in_export=False)
                edge(iid, identity, 'dispatched_input', r['source_ref'], control=True)
            feedback_artifact = r.get('feedback_ref')
            if feedback_artifact:
                fid = node('artifact:' + digest(feedback_artifact), 'feedback_artifact', **feedback_artifact)
                edge(identity, fid, 'recorded_feedback', r['source_ref'], control=True)
                next_input = r.get('next_input')
                if next_input and next_input.get('feedback_digest') == feedback_artifact['artifact_digest']:
                    nid = node('artifact:' + digest(next_input), 'next_input_artifact', **next_input)
                    edge(fid, nid, 'control_feedback', r['source_ref'], control=True)
            for phase in r['target_phases']:
                phase_id = node('phase:' + phase, 'phase', phase_key=phase)
                edge(phase_id, identity, 'targets_phase', r['source_ref'])
            child = r.get('candidate_sha')
            if child is None:
                for parent in r['parents']:
                    edge(candidate(parent), identity, 'research_input', r['source_ref'])
            if child:
                edge(identity, candidate(child), 'membership', r['source_ref'])
                parents(r['parents'], child, r['source_ref'], r['kind'] == 'combine')
            for ref in r['evaluations']:
                evaluation(ref)  # references are not a validation verdict
            for ref in r['target_evidence']:
                edge(evaluation(ref), identity, 'target_evidence', r['source_ref'], control=True)
        except (ValueError, TypeError, KeyError) as exc:
            issues.append('Research ' + str(key) + ': ' + str(exc))

    for key, task in sorted((team.get('tasks') or {}).items()):
        identity = node('task:' + key, 'task', task_id=key, hypothesis=task.get('hypothesis'),
                        target_phases=task.get('target_phases') or [], status=task.get('status'),
                        stopping_reason=task.get('resolution'))
        for phase in task.get('target_phases') or []:
            if phase in PHASES:
                edge(node('phase:' + phase, 'phase', phase_key=phase), identity,
                     'targets_phase', 'team task ' + key)
            else:
                issues.append('Unknown declared phase in task ' + key)
        for child in task.get('candidates', []):
            try:
                edge(identity, candidate(child), 'membership', 'team task ' + key)
                parents(task.get('parents', []), child, 'team task ' + key, task.get('kind') == 'combine')
            except ValueError as exc:
                issues.append(str(exc))

    # Input receipts identify the prior feedback consumed by a later turn. These
    # operational links never become backwards scientific-parent edges.
    for r in records.values():
        receipt = r.get('input_receipt') or {}
        consumed = receipt.get('consumed_feedback_digest')
        prior_sha = receipt.get('consumed_candidate_sha')
        if not consumed:
            continue
        matches = [prior for prior in records.values()
                   if (prior.get('feedback_ref') or {}).get('artifact_digest') == consumed
                   and prior.get('candidate_sha') == prior_sha]
        if len(matches) == 1:
            artifact = matches[0]['feedback_ref']
            edge('artifact:' + digest(artifact), 'input:' + receipt['sha256'],
                 'control_feedback', r['source_ref'], control=True)
        else:
            issues.append('Consumed feedback artifact unavailable or ambiguous for ' + r['record_id'])

    for key, obs in sorted((team.get('observations') or {}).items()):
        e = obs.get('evidence') or {}
        try:
            evaluation(e, obs.get('instance'), e.get('cohort_digest'), obs.get('comparison_context'), e)
        except ValueError as exc:
            issues.append('Observation ' + key + ': ' + str(exc))

    for job in snapshot.get('jobs') or []:
        try:
            sha = job.get('sha')
            ref = dict(candidate_sha=sha, job_id=job.get('id'), profile=job.get('profile'))
            evidence = job.get('evidence') or {}
            if evidence and (evidence.get('candidate_sha') != sha or evidence.get('job_id') != ref['job_id']
                             or evidence.get('profile') != ref['profile']):
                raise ValueError('Job evidence identity mismatch')
            evaluation(ref, job.get('instance'), evidence.get('cohort_digest'), job.get('comparison_context'), evidence,
                       {'official':job.get('official_check', 'unknown'), 'strict':job.get('strict_check', 'unknown')})
            feedback = job.get('recorded_feedback') or {}
            if feedback.get('status') == 'recorded':
                identity = node('feedback:' + digest([sha, feedback]), 'research', candidate_sha=sha,
                                target_phases=feedback.get('target_phases') or [],
                                hypothesis=feedback.get('hypothesis'), change_summary=feedback.get('summary'),
                                sources=feedback.get('sources'), status='recorded', stopping_reason=None)
                edge(identity, candidate(sha), 'membership', 'exact recorded feedback')
                parents(feedback.get('parent_candidates') or [], sha, 'exact recorded feedback')
            elif feedback:
                issues.append('Conflicting or unverified feedback for ' + str(ref['job_id']))
        except (ValueError, TypeError) as exc:
            issues.append(str(exc))

    for campaign in snapshot.get('campaigns') or []:
        cid = campaign.get('id') or (campaign.get('campaign') or {}).get('spec', {}).get('campaign_id')
        if not isinstance(cid, str):
            issues.append('Campaign missing identity')
            continue
        identity = node('campaign:' + cid, 'campaign', executor_id=cid, status=campaign.get('status', 'unknown'))
        spec = (campaign.get('campaign') or {}).get('spec', {})
        manifest = spec.get('manifest') or {}
        legal = manifest.get('legal')
        nodes[identity]['menu'] = dict(manifest_digest=spec.get('manifest_digest'),
                                      legal_count=len(legal) if isinstance(legal, list) else None,
                                      covered_count=None)
        nodes[identity]['selector'] = campaign.get('selector', spec.get('selector'))
        nodes[identity]['budget'] = campaign.get('budget', spec.get('budget'))
        for lane in campaign.get('lanes', []):
            lid = str(lane.get('round_id')) + ':' + str(lane.get('lane_id'))
            reasons = [(event.get('payload') or {}).get('reason') for event in campaign.get('events', [])
                       if event.get('type') == 'lane_exhausted'
                       and (event.get('payload') or {}).get('round_id') == lane.get('round_id')
                       and (event.get('payload') or {}).get('lane_id') == lane.get('lane_id')]
            lane_node = node('lane:' + cid + ':' + lid, 'lane', status=lane.get('status', 'unknown'),
                             stopping_reason=reasons[-1] if reasons else None,
                             strikes=lane.get('strikes'), round_id=lane.get('round_id'), lane_id=lane.get('lane_id'))
            edge(identity, lane_node, 'membership', 'campaign ' + cid)
        candidates = {}
        for c in campaign.get('candidates') or []:
            if isinstance(c, dict) and isinstance(c.get('candidate_id'), str):
                candidates[c['candidate_id']] = c
            else:
                issues.append('Malformed campaign candidate in ' + cid)
        for c in candidates.values():
            try:
                child = c.get('commit_sha')
                if not exact_sha(child):
                    raise ValueError('Missing exact campaign candidate SHA')
                parent_ids = c.get('parents', [])
                if not isinstance(parent_ids, list) or any(not isinstance(p, str) for p in parent_ids):
                    raise ValueError('Malformed campaign parent IDs')
                edge(identity, candidate(child), 'membership', 'campaign ' + cid)
                refs = [candidates.get(p, {}).get('commit_sha') for p in parent_ids]
                if any(p is None for p in refs):
                    issues.append('Unresolved campaign parent in ' + cid)
                parents([p for p in refs if p is not None], child, 'campaign ' + cid, c.get('kind') == 'combine')
            except (ValueError, TypeError) as exc:
                issues.append('Campaign ' + cid + ': ' + str(exc))

    return dict(schema='feyer-search-lineage-v1', nodes=sorted(nodes.values(), key=lambda n: n['id']),
                edges=sorted(edges.values(), key=lambda e: (e['source'], e['target'], e['kind'])),
                control_edges=sorted(control_edges.values(), key=lambda e: (e['source'], e['target'], e['kind'])),
                records=records, issues=issues,
                limits=['Declared scientific ancestry is separate from Git history.',
                        'Missing phase targets and stopping reasons remain unknown.',
                        'Completed, finite-menu exhausted and stalled do not prove a local optimum.',
                        'Evaluation links preserve evidence context; no winner or cross-cohort aggregation is inferred.'])
