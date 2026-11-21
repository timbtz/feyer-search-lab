"""Shared human-driven search queue, serialized by ordinary Git fast-forward pushes.

This is cooperative team coordination, not an authorization boundary. It never
starts models, runs benchmarks, expires a live claim, or merges simulator code.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import tempfile
import time
import uuid


KINDS = ('explore', 'refine', 'combine', 'confirm', 'diagnose')
SHA = re.compile(r'[0-9a-f]{40}')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}')


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError('Names use 1–80 letters, digits, dots, hyphens or underscores')
    return value


def finite_positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def initial_state(coordinator):
    return dict(schema='feyer-team-search-v1', coordinator=name(coordinator),
                tasks={}, observations={}, events=[])


def eligible(state, sha, instance=None, cohort=None, serial_only=False):
    return [o for o in state['observations'].values()
            if o['evidence']['candidate_sha'] == sha and o['evidence']['eligible_full']
            and (not serial_only or o.get('comparison_context', {}).get('mode', 'serial') == 'serial')
            and (instance is None or o['instance'] == instance)
            and (cohort is None or o['evidence']['cohort_digest'] == cohort)]


def check_lineage(state, parents, child):
    edges = {}
    for task in state['tasks'].values():
        for parent in task['parents']:
            edges.setdefault(parent, set()).update(task['candidates'])
    pending, seen = [child], set()
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        if node in parents:
            raise ValueError('Reusing ancestor content would create a scientific cycle; record a new hypothesis from that reference instead')
        seen.add(node)
        pending.extend(edges.get(node, ()))


def assess(state, task_id, sha, instance, cohort):
    """Observed medians, with repeated full evidence on one instance/cohort only."""
    task = state['tasks'][task_id]
    if sha not in task['candidates'] and sha not in task['parents']:
        raise ValueError('Candidate is not reserved in this task or one of its references')
    minimum = task['minimum_full_runs']
    targets = [sha] + task['parents']
    samples = {s: eligible(state, s, instance, cohort, serial_only=True) for s in targets}
    result = dict(candidate_sha=sha, instance=instance, cohort=cohort,
                  counts={s: len(rows) for s, rows in samples.items()},
                  minimum_full_runs=minimum, classification='needs_confirmation')
    excluded = [o['evidence']['job_id'] for o in state['observations'].values()
                if o['instance'] == instance and o['evidence']['candidate_sha'] in targets
                and o['evidence']['cohort_digest'] == cohort
                and o.get('comparison_context', {}).get('mode', 'serial') != 'serial']
    result['exploratory_jobs_excluded'] = excluded
    failures = [o['evidence']['job_id'] for o in state['observations'].values()
                if o['instance'] == instance and o['evidence']['candidate_sha'] in targets
                and o['evidence']['cohort_digest'] == cohort
                and o['evidence']['category'] == 'invalid_candidate']
    if failures:
        result.update(classification='numerical_review_required', invalid_jobs=failures)
        return result
    if any(len(rows) < minimum for rows in samples.values()):
        if excluded:
            result['classification'] = 'needs_serial_confirmation'
        return result
    totals = {s: statistics.median(o['evidence']['metrics']['total'] for o in rows)
              for s, rows in samples.items()}
    result['median_first_run_seconds'] = totals
    result['ranges_seconds'] = {s: [min(o['evidence']['metrics']['total'] for o in rows),
                                    max(o['evidence']['metrics']['total'] for o in rows)]
                               for s, rows in samples.items()}
    if not task['parents'] or sha in task['parents']:
        result['classification'] = 'validated_reference'
        return result
    reference = min(task['parents'], key=totals.get)
    ranges = result['ranges_seconds']
    threshold = max(task['minimum_gain_seconds'], totals[reference] * task['minimum_gain_fraction'],
                    ranges[reference][1] - ranges[reference][0], ranges[sha][1] - ranges[sha][0])
    gain = totals[reference] - totals[sha]
    result.update(reference_sha=reference, gain_seconds=gain, required_gain_seconds=threshold,
                  classification='improved' if gain > threshold else 'not_improved')
    # Descriptors are for retaining complementary ideas, never override total.
    axes = ('compilation', 'runtime', 'peak_rss_bytes')
    medians = {s: {a: statistics.median(o['evidence']['metrics'][a] for o in rows)
                   for a in axes} for s, rows in samples.items()}
    result['pareto_metrics'] = medians
    result['parent_dominates'] = any(
        all(medians[p][a] <= medians[sha][a] for a in axes)
        and any(medians[p][a] < medians[sha][a] for a in axes) for p in task['parents'])
    result['uncertainty'] = 'Repeated observed medians, not a statistical significance test; inspect alternating run order and ranges.'
    return result


def apply(state, command, actor, data, now=None):
    """Pure transaction; rejected changes cannot partly mutate the shared state."""
    state = copy.deepcopy(state)
    actor = name(actor)
    now = time.time() if now is None else now
    if command == 'comparison-regime':
        if actor != state['coordinator']:
            raise ValueError('Only the coordinator changes the comparison regime')
        if data.get('mode') not in ('serial', 'concurrent'):
            raise ValueError('Unknown comparison regime')
        if any(not isinstance(data.get(k), str) or not data[k].strip() for k in ('reason', 'receipt')):
            raise ValueError('A resource receipt and concrete transition reason are required')
        state['comparison_regime'] = dict(data, changed_at=now, epoch=len(state['events']) + 1)
        output = state['comparison_regime']
    elif command == 'add':
        if actor != state['coordinator']:
            raise ValueError('Only the coordinator admits work')
        task = copy.deepcopy(data)
        task_id = name(task['id'])
        if task_id in state['tasks']:
            raise ValueError('Task already exists')
        if task['kind'] not in KINDS:
            raise ValueError('Unknown task kind')
        if not isinstance(task.get('hypothesis'), str) or not task['hypothesis'].strip():
            raise ValueError('A concrete hypothesis is required')
        parents = task.get('parents', [])
        if not isinstance(parents, list) or len(parents) != len(set(parents)) or any(
                not isinstance(s, str) or not SHA.fullmatch(s) for s in parents):
            raise ValueError('Parents must be distinct exact commit SHAs')
        required = 2 if task['kind'] == 'combine' else 1
        if len(parents) < required:
            raise ValueError('Task needs exact scientific parents (combine needs two)')
        if task['kind'] in ('refine', 'combine', 'confirm') and any(not eligible(state, s) for s in parents):
            raise ValueError('Refine/combine/confirm parents need eligible full evidence')
        if type(task.get('max_candidates')) is not int or task['max_candidates'] < 1:
            raise ValueError('An explicit positive candidate budget is required')
        if task['kind'] == 'refine' and task['max_candidates'] != 1:
            raise ValueError('Each refinement task admits one successor; freeze the previous best as its parent')
        if not finite_positive(task.get('deadline_unix')) or task['deadline_unix'] <= now:
            raise ValueError('An explicit future task deadline is required')
        task.setdefault('minimum_full_runs', 3)
        task.setdefault('minimum_gain_fraction', .03)
        task.setdefault('minimum_gain_seconds', .02)
        if type(task['minimum_full_runs']) is not int or task['minimum_full_runs'] < 3:
            raise ValueError('At least three full runs per candidate/reference are required')
        for key in ('minimum_gain_fraction', 'minimum_gain_seconds'):
            value = task[key]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Gain thresholds must be finite and nonnegative')
        task.setdefault('priority', 100)
        if type(task['priority']) is not int:
            raise ValueError('Priority must be an integer; lower is earlier')
        task.setdefault('depends_on', [])
        dependencies = task['depends_on']
        if not isinstance(dependencies, list) or any(not isinstance(d, str) or d not in state['tasks'] for d in dependencies):
            raise ValueError('Dependencies must name already admitted tasks')
        # Reserved fields are generated here, never taken from a spec.
        task.update(parents=parents, status='ready', owner=None, instance=None,
                    claim_id=None, candidates=[], candidate_branches={}, created_at=now)
        state['tasks'][task_id] = task
        output = task
    elif command == 'candidate':
        task = state['tasks'][data['task']]
        if task['status'] != 'claimed' or task['owner'] != actor or task['claim_id'] != data['claim_id']:
            raise ValueError('Candidate reservation requires the current owner and claim')
        sha = data['sha']
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError('Candidate must be an exact commit SHA')
        branch = data['code_branch']
        if not isinstance(branch, str) or not re.fullmatch(r'(explore|combine|submission)/[A-Za-z0-9_./-]+', branch) or '..' in branch:
            raise ValueError('Use an owned explore/, combine/ or submission/ code branch')
        if any(other['id'] != task['id'] and other['status'] == 'claimed'
               and branch in other['candidate_branches'].values() for other in state['tasks'].values()):
            raise ValueError('Another claimed task already owns this writable code branch')
        if sha in task['candidate_branches']:
            if task['candidate_branches'][sha] != branch:
                raise ValueError('Candidate is already reserved on a different branch')
            return state, task
        if now >= task['deadline_unix']:
            raise ValueError('Task deadline exhausted; only bookkeeping is allowed')
        if sha not in task['parents']:
            if len(task['candidates']) >= task['max_candidates']:
                raise ValueError('Task candidate budget exhausted')
            check_lineage(state, task['parents'], sha)
            task['candidates'].append(sha)
        task['candidate_branches'][sha] = branch
        output = task
    elif command in ('claim', 'release', 'resolve'):
        task = state['tasks'][data['task']]
        if command == 'claim':
            if task['status'] != 'ready':
                raise ValueError('Task is not ready; another owner may already hold it')
            if now >= task['deadline_unix']:
                raise ValueError('Task deadline exhausted; coordinator must admit new work')
            if any(state['tasks'][d]['status'] not in ('done', 'stalled') for d in task['depends_on']):
                raise ValueError('Prerequisite tasks have not finished')
            retained_branches = set(task['candidate_branches'].values())
            if any(other['id'] != task['id'] and other['status'] == 'claimed'
                   and retained_branches.intersection(other['candidate_branches'].values())
                   for other in state['tasks'].values()):
                raise ValueError('Another claimed task already owns a retained writable code branch')
            task.update(status='claimed', owner=actor, instance=name(data['instance']),
                        claim_id=data['claim_id'], claimed_at=now)
        else:
            if task['status'] != 'claimed' or (actor != task['owner'] and actor != state['coordinator']):
                raise ValueError('Only the current owner/coordinator can close or release a claim')
            if data.get('claim_id') != task['claim_id']:
                raise ValueError('Stale claim ID')
            if not data.get('reason', '').strip():
                raise ValueError('Record a concrete reason and handoff')
            if command == 'release':
                task.update(status='ready', owner=None, instance=None, claim_id=None)
            else:
                if data['outcome'] not in ('done', 'stalled', 'blocked'):
                    raise ValueError('Unknown resolution')
                task.update(status=data['outcome'], resolution=data['reason'])
        output = task
    elif command == 'record':
        observation = copy.deepcopy(data['observation'])
        # The coordinator's execution regime, not an importer-supplied label,
        # determines whether new timing evidence can enter a comparison.
        observation.pop('comparison_context', None)
        from .evolution_evidence import normalize_job
        if observation['evidence'] != normalize_job(observation['job']):
            raise ValueError('Evidence must match the trusted job normalization')
        evidence = observation['evidence']
        key = observation['instance'] + ':' + evidence['job_id']
        name(observation['instance'])
        previous = state['observations'].get(key)
        if previous:
            original = {k: v for k, v in previous.items() if k != 'comparison_context'}
            if original != observation:
                raise ValueError('Job identity already has different evidence')
            return state, previous
        regime = state.get('comparison_regime')
        if regime:
            mode = regime['mode']
            started = observation['job'].get('started_at')
            finished = observation['job'].get('finished_at')
            # Switching back to serial must not admit late arrivals from the
            # overlapping epoch. Only a new, timestamped job can confirm timing.
            if mode == 'serial' and (not finite_positive(started) or not finite_positive(finished)
                                     or finished < started or started < regime['changed_at']):
                mode = 'unverified_timing'
            observation['comparison_context'] = dict(mode=mode, epoch=regime['epoch'],
                                                     receipt=regime['receipt'])
        task_id = observation.get('task')
        if task_id:
            task = state['tasks'][task_id]
            if task['status'] != 'claimed' or task['owner'] != actor or task['instance'] != observation['instance']:
                raise ValueError('Record against the task owned by this actor on this instance')
            if data.get('claim_id') != task['claim_id']:
                raise ValueError('Stale claim ID')
            sha = evidence['candidate_sha']
            if sha not in task['candidate_branches']:
                raise ValueError('Reserve the exact candidate before evaluation (candidate command)')
            # Late completed results are accepted for safe bookkeeping, not permission to continue.
        elif actor != state['coordinator']:
            raise ValueError('Only coordinator imports reference evidence without a claim')
        state['observations'][key] = observation
        output = observation
    else:
        raise ValueError('Unknown mutation')
    state['events'].append(dict(seq=len(state['events']) + 1, at=now, actor=actor,
                                command=command, data=data))
    return state, output


def ready(state, now=None):
    now = time.time() if now is None else now
    return sorted((t for t in state['tasks'].values() if t['status'] == 'ready'
                   and now < t['deadline_unix']
                   and all(state['tasks'][d]['status'] in ('done', 'stalled') for d in t['depends_on'])),
                  key=lambda t: (t['priority'], t['id']))


def render(state):
    lines = ['# Team search queue', '',
             'Human-driven search; Qwen and SMAC are optional. See `.wiki/team-search.md` on main.', '',
             'Claims and decisions live in this branch. Timing comparisons require the same instance and cohort.', '',
             '| Task | Kind | State | Owner / instance | Parents |', '| --- | --- | --- | --- | --- |']
    for t in state['tasks'].values():
        lines.append(f"| {t['id']} | {t['kind']} | {t['status']} | {t['owner'] or '—'} / {t['instance'] or '—'} | "
                     + ', '.join(s[:12] for s in t['parents']) + ' |')
    regime = state.get('comparison_regime')
    if regime:
        lines += ['', '## Comparison regime', '',
                  f"Current mode: **{regime['mode']}**, epoch {regime['epoch']}.", '',
                  'Concurrent and unverified timing imports are exploratory and excluded from winner assessment.',
                  '', f"Receipt: {regime['receipt']}", '', regime['reason']]
    lines += ['', '## Scientific lineage', '', '```mermaid', 'graph TD']
    shas = sorted({s for t in state['tasks'].values() for s in t['parents'] + t['candidates']})
    ids = {s: f'c{i}' for i, s in enumerate(shas)}
    for sha, node in ids.items():
        lines.append(f'  {node}["{sha[:12]}"]')
    edges = set()
    for task in state['tasks'].values():
        for child in task['candidates']:
            for parent in task['parents']:
                if child != parent:
                    edges.add((parent, child, task['kind']))
    for parent, child, kind in sorted(edges):
        lines.append(f'  {ids[parent]} -->|{kind}| {ids[child]}')
    lines += ['```', '', 'Every edge records intended inputs, not proof of speedup.', '',
              f"Recorded jobs: {len(state['observations'])}. Decisions/events: {len(state['events'])}.", '']
    return '\n'.join(lines)


class GitLedger:
    """Fresh temporary checkout per transaction; never touches the user's worktree."""
    def __init__(self, remote, branch='control/team-search'):
        if not remote or remote.startswith('-'):
            raise ValueError('Provide an explicit Git remote URL or local test repository')
        subprocess.run(['git', 'check-ref-format', 'refs/heads/' + branch], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.remote, self.branch = remote, branch

    @staticmethod
    def git(path, *args, check=True):
        return subprocess.run(['git', '-C', str(path), *args], check=check,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)

    def _checkout(self, path):
        self.git(path, 'init', '-q')
        refs = self.git(path, 'ls-remote', '--exit-code', self.remote, 'refs/heads/' + self.branch, check=False)
        if refs.returncode == 2:
            self.git(path, 'checkout', '--orphan', 'ledger')
            return None
        if refs.returncode:
            raise RuntimeError('Cannot read shared ledger: ' + refs.stderr.strip())
        self.git(path, 'fetch', '-q', self.remote, 'refs/heads/' + self.branch)
        self.git(path, 'checkout', '-q', '-B', 'ledger', 'FETCH_HEAD')
        state = json.loads((path / 'state.json').read_text())
        if state.get('schema') != 'feyer-team-search-v1':
            raise ValueError('Unsupported team ledger schema')
        return state

    def read(self):
        with tempfile.TemporaryDirectory(prefix='feyer-team-') as directory:
            state = self._checkout(Path(directory))
            if state is None:
                raise ValueError('Shared ledger does not exist; coordinator must init it')
            return state

    def transact(self, command, actor, data):
        # Ordinary non-force pushes are a compare-and-swap: a concurrent writer
        # makes our old-parent commit non-fast-forward. Reload before retrying.
        for attempt in range(5):
            with tempfile.TemporaryDirectory(prefix='feyer-team-') as directory:
                path = Path(directory)
                state = self._checkout(path)
                if command == 'init':
                    if state is not None:
                        raise ValueError('Ledger already initialized')
                    updated = initial_state(actor)
                    output = updated
                else:
                    if state is None:
                        raise ValueError('Shared ledger is not initialized')
                    updated, output = apply(state, command, actor, data)
                    if updated == state:
                        return output
                (path / 'state.json').write_text(json.dumps(updated, indent=2, allow_nan=False) + '\n')
                (path / 'README.md').write_text(render(updated))
                self.git(path, 'add', 'state.json', 'README.md')
                self.git(path, '-c', 'user.name=Feyer search ledger', '-c',
                         'user.email=feyer-search@users.noreply.github.com', 'commit', '-qm',
                         f'{command}: {actor}')
                commit = self.git(path, 'rev-parse', 'HEAD').stdout.strip()
                try:
                    pushed = self.git(path, 'push', self.remote, f'HEAD:refs/heads/{self.branch}', check=False)
                except subprocess.TimeoutExpired:
                    # Unknown outcome, not rejection. Try read-only recovery;
                    # if that fails, the caller must inspect list before retry.
                    pushed = subprocess.CompletedProcess([], 1, '', 'push timed out; outcome unknown, inspect shared state')
                if pushed.returncode == 0:
                    return output
                # A lost push response may still mean success. Refresh and check
                # ancestry before replaying a mutation (especially a claim).
                fetched = self.git(path, 'fetch', '-q', self.remote, 'refs/heads/' + self.branch, check=False)
                if fetched.returncode == 0 and self.git(path, 'merge-base', '--is-ancestor', commit, 'FETCH_HEAD', check=False).returncode == 0:
                    if command in ('claim', 'candidate'):
                        latest = json.loads(self.git(path, 'show', 'FETCH_HEAD:state.json').stdout)
                        current = latest['tasks'][data['task']]
                        if any(current[key] != output[key] for key in ('status', 'owner', 'claim_id', 'instance')):
                            raise RuntimeError('Transaction landed but ownership changed; inspect shared state before continuing')
                    return output
                if not any(s in pushed.stderr for s in ('non-fast-forward', 'fetch first', 'cannot lock ref', 'failed to update ref', 'already exists')):
                    raise RuntimeError('Ledger publication failed: ' + pushed.stderr.strip())
        raise RuntimeError('Ledger remained busy; retry after reading current state')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', required=True, help='Explicit team repository URL; never inferred from gh upstream')
    parser.add_argument('--branch', default='control/team-search')
    parser.add_argument('--actor', required=True, help='Stable cooperative owner ID, usually your GitHub username')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('list')
    sub.add_parser('next')
    regime = sub.add_parser('comparison-regime')
    regime.add_argument('--mode', choices=('serial', 'concurrent'), required=True)
    regime.add_argument('--reason', required=True)
    regime.add_argument('--receipt', required=True)
    add = sub.add_parser('add'); add.add_argument('--spec', type=Path, required=True)
    claim = sub.add_parser('claim'); claim.add_argument('task'); claim.add_argument('--instance', required=True)
    candidate = sub.add_parser('candidate'); candidate.add_argument('task')
    candidate.add_argument('--sha', required=True); candidate.add_argument('--claim-id', required=True)
    candidate.add_argument('--code-branch', required=True)
    for command in ('release', 'resolve'):
        cmd = sub.add_parser(command); cmd.add_argument('task'); cmd.add_argument('--claim-id', required=True)
        cmd.add_argument('--reason', required=True)
        if command == 'resolve': cmd.add_argument('--outcome', choices=('done', 'stalled', 'blocked'), required=True)
    record = sub.add_parser('record')
    record.add_argument('--job', required=True, type=Path, help='Full JSON from lab.client status, not the timing report alone')
    record.add_argument('--instance', required=True); record.add_argument('--task'); record.add_argument('--claim-id')
    assessment = sub.add_parser('assess'); assessment.add_argument('task'); assessment.add_argument('--sha', required=True)
    assessment.add_argument('--instance', required=True); assessment.add_argument('--cohort', required=True)
    args = parser.parse_args(argv)
    name(args.actor)
    ledger = GitLedger(args.remote, args.branch)
    if args.command in ('list', 'next', 'assess'):
        state = ledger.read()
        if args.command == 'list': output = state
        elif args.command == 'next': output = ready(state)
        else: output = assess(state, args.task, args.sha, args.instance, args.cohort)
    else:
        data = {}
        if args.command == 'add': data = json.loads(args.spec.read_text())
        elif args.command == 'comparison-regime':
            data = dict(mode=args.mode, reason=args.reason, receipt=args.receipt)
        elif args.command == 'claim': data = dict(task=args.task, instance=args.instance, claim_id=uuid.uuid4().hex)
        elif args.command == 'candidate':
            data = dict(task=args.task, sha=args.sha, claim_id=args.claim_id, code_branch=args.code_branch)
        elif args.command in ('release', 'resolve'):
            data = dict(task=args.task, claim_id=args.claim_id, reason=args.reason)
            if args.command == 'resolve': data['outcome'] = args.outcome
        elif args.command == 'record':
            from .evolution_evidence import normalize_job
            job = json.loads(args.job.read_text())
            # Logs may contain unrelated private content; publish numerical/source
            # evidence only. Never dump local environment or provider transcripts.
            job = {key: job[key] for key in ('id', 'sha', 'profile', 'status', 'started_at', 'finished_at',
                                           'result', 'report.json', 'comparison.json') if key in job}
            evidence = normalize_job(job)
            data = dict(claim_id=args.claim_id, observation=dict(instance=name(args.instance),
                        task=args.task, evidence=evidence, job=job))
        output = ledger.transact(args.command, args.actor, data)
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
