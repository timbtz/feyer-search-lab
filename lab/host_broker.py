"""Native single-slot proposer. GitHub assignments in; committed receipts out.

This is an execution adapter, not a search coordinator or evaluator. Assignment
and receipt refs are operator-configured; grants and round membership are checked
by the DAG coordinator when it ingests receipts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import time
import uuid

from .agent_loop import (changed_paths, exclusive_lock, read_thread_id,
                         terminate_group, validate_changes, write_json)

SAFE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$')
SHA = re.compile(r'^[0-9a-f]{40}$')
HASH = re.compile(r'^[0-9a-f]{64}$')
RESPONSE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {k: {'type': 'string'} for k in
                   ('summary', 'hypothesis', 'heuristic_id', 'parameters_before_json',
                    'parameters_after_json', 'notes')},
}
RESPONSE_SCHEMA['properties']['ready_for_evaluation'] = {'type': 'boolean'}
RESPONSE_SCHEMA['required'] = list(RESPONSE_SCHEMA['properties'])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(args, cwd=None, data=None, timeout=90):
    return subprocess.check_output(args, cwd=cwd, input=data, stderr=subprocess.PIPE,
                                   timeout=timeout)


def git(repo, *args, data=None):
    return run(['git', '-C', str(repo), '-c', 'credential.helper=!gh auth git-credential', *args], data=data)


def textgit(repo, *args):
    return git(repo, *args).decode().strip()


def checked_path(path):
    if not isinstance(path, str):
        raise ValueError('Artifact path must be text')
    p = PurePosixPath(path)
    if not isinstance(path, str) or p.is_absolute() or '..' in p.parts or str(p) != path:
        raise ValueError('Expected a normalized repository-relative artifact path')
    return path


def validate_task(task, actor, branch_prefix='explore/hetzner/', now=None):
    now = time.time() if now is None else now
    if task.get('schema_version') != 'feyer-dag-task-v1' or task.get('output_schema') != 'feyer-dag-proposal-v1':
        raise ValueError('Unsupported assignment schema')
    if not re.fullmatch(r'[0-9a-f]{32}', task['task_id']):
        raise ValueError('Task ID must be a UUID hex string')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', task['campaign_id']):
        raise ValueError('Unsafe campaign ID')
    if not isinstance(task['round_id'], str) or not 1 <= len(task['round_id']) <= 160:
        raise ValueError('Invalid round ID')
    if not HASH.fullmatch(task['round_spec_sha256']):
        raise ValueError('Missing immutable round identity')
    ownership = task['ownership']
    if ownership['actor'] != actor or not SAFE.fullmatch(actor):
        raise ValueError('Assignment belongs to another actor')
    if type(ownership['claim_version']) is not int or ownership['claim_version'] < 1:
        raise ValueError('Invalid claim version')
    branch = ownership['branch']
    if not branch.startswith(branch_prefix) or not re.fullmatch(r'[A-Za-z0-9_./-]+', branch):
        raise ValueError('Branch outside worker namespace')
    subprocess.run(['git', 'check-ref-format', '--branch', branch], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if task['kind'] not in ('guidance', 'candidate'):
        raise ValueError('Unknown proposer kind')
    if not task['parent_candidates']:
        raise ValueError('An explicit checkout parent is required')
    for parent in task['parent_candidates']:
        if not SHA.fullmatch(parent['commit_sha']) or not isinstance(parent['candidate_id'], str):
            raise ValueError('Invalid parent identity')
    for field in ('context', 'brief'):
        checked_path(task[field]['path'])
        if not HASH.fullmatch(task[field]['sha256']) or not SHA.fullmatch(task[field]['commit_sha']):
            raise ValueError('Missing ' + field + ' hash')
    provider = task['provider']
    if provider['name'] != 'codex' or provider.get('model_policy') not in ('specified', 'inherit-designated-config'):
        raise ValueError('This adapter requires a designated Codex model policy')
    if provider['model_policy'] == 'specified' and (not isinstance(provider['model'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', provider['model'])):
        raise ValueError('Specified model is invalid')
    if provider.get('reasoning') not in (None, 'low', 'medium', 'high', 'xhigh'):
        raise ValueError('Unsupported reasoning effort')
    budget = task['budget']
    if budget.get('max_turns') != 1 or isinstance(budget['deadline_unix'], bool):
        raise ValueError('One bounded turn is required')
    if not isinstance(budget['deadline_unix'], (int, float)) or not now < budget['deadline_unix'] <= now + 86400:
        raise ValueError('Expired or excessively distant deadline')
    allowed = task['allowed_paths']
    if not allowed or any(p not in ('differometor/**', 'experiments/notes/**') for p in allowed):
        raise ValueError('Assignment may not expand protected paths')
    if task['kind'] == 'guidance' and allowed != ['experiments/notes/**']:
        raise ValueError('Guidance tasks may only write notes')
    return task


def load_artifact(repo, commit, spec):
    path = checked_path(spec['path'])
    immutable = spec['commit_sha']
    try:
        git(repo, 'cat-file', '-e', immutable + '^{commit}')
    except subprocess.CalledProcessError:
        git(repo, 'fetch', 'origin', immutable)
    raw = git(repo, 'show', immutable + ':' + path)
    if len(raw) > 256 * 1024 or digest(raw) != spec['sha256']:
        raise ValueError('Artifact size or SHA256 mismatch: ' + path)
    return raw.decode()


def validate_response(value):
    if not isinstance(value, dict) or set(value) != set(RESPONSE_SCHEMA['required']):
        raise ValueError('Unexpected agent response fields')
    for key in RESPONSE_SCHEMA['required']:
        expected = bool if key == 'ready_for_evaluation' else str
        if type(value[key]) is not expected:
            raise ValueError('Invalid response type: ' + key)
    for key in ('parameters_before_json', 'parameters_after_json'):
        if not isinstance(json.loads(value[key]), dict):
            raise ValueError('Parameters must encode a JSON object')
    return value


def memory_available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('Cannot establish memory headroom')


def recorded_model(session_id):
    if not session_id:
        return None
    sessions = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'sessions'
    for path in sessions.glob('*/*/*/*' + session_id + '*.jsonl'):
        with path.open() as lines:
            for line in lines:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('type') == 'turn_context':
                    return event.get('payload', {}).get('model')
    return None


class Broker:
    def __init__(self, config):
        self.config = config
        self.repo = Path(config['repo']).resolve()
        self.root = Path(config['state_root']).resolve()
        self.actor = config['actor']
        if not SAFE.fullmatch(self.actor):
            raise ValueError('Unsafe actor')
        self.root.mkdir(parents=True, exist_ok=True)
        self.worktrees = self.root / 'worktrees'
        self.worktrees.mkdir(exist_ok=True)
        self.runtime = textgit(self.repo, 'rev-parse', 'HEAD')

    def fetch(self):
        ref = self.config['assignment_ref']
        subprocess.run(['git', 'check-ref-format', ref], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        git(self.repo, '-c', 'credential.helper=!gh auth git-credential', 'fetch', 'origin', ref)
        return textgit(self.repo, 'rev-parse', 'FETCH_HEAD')

    def claim(self, task, source, task_hash):
        """Create a permanent GitHub task claim atomically; never steal a claim."""
        ref = 'refs/heads/worker-claims/' + self.actor + '/' + task['task_id']
        marker = json.dumps({'task_sha256': task_hash, 'task_id': task['task_id'],
                             'actor': self.actor, 'assignment_commit': source}, sort_keys=True)
        existing = textgit(self.repo, 'ls-remote', 'origin', ref)
        if existing:
            raise RuntimeError('Task already claimed; local recovery state is required')
        tree = textgit(self.repo, 'rev-parse', source + '^{tree}')
        claim = git(self.repo, 'commit-tree', tree, '-p', source,
                    data=('Feyer task claim\n\n' + marker + '\n').encode()).decode().strip()
        # refs API rejects an existing ref, even if its target happens to match.
        payload = json.dumps({'ref': ref, 'sha': claim}).encode()
        # Upload the object on an isolated temporary branch before atomic claim.
        upload = 'refs/heads/worker-claim-objects/' + uuid.uuid4().hex
        git(self.repo, '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin', claim + ':' + upload)
        try:
            run(['gh', 'api', '--method', 'POST', 'repos/' + self.config['github_repo'] + '/git/refs',
                 '--input', '-'], data=payload)
        finally:
            git(self.repo, '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin', ':' + upload)
        return ref, claim

    def prepare(self, task, directory, brief, context):
        branch = task['ownership']['branch']
        if textgit(self.repo, 'ls-remote', 'origin', 'refs/heads/' + branch):
            raise RuntimeError('Assigned candidate branch already exists')
        parent = task['parent_candidates'][0]['commit_sha']
        git(self.repo, '-c', 'credential.helper=!gh auth git-credential', 'fetch', 'origin', parent)
        worktree = self.worktrees / task['task_id']
        git(self.repo, 'worktree', 'add', '-b', branch, str(worktree), parent)
        # The trusted current rules override obsolete budgets in old candidate trees.
        (worktree / 'AGENTS.md').write_bytes((self.repo / 'AGENTS.md').read_bytes())
        manifest_dir = worktree / 'experiments/agents/assignments'
        manifest_dir.mkdir(parents=True, exist_ok=True)
        write_json(manifest_dir / (task['task_id'] + '.json'), task)
        for name, data in [('brief', brief), ('context', context)]:
            (manifest_dir / (task['task_id'] + '.' + name + '.md')).write_text(data)
        git(worktree, 'add', '--', 'AGENTS.md', 'experiments/agents/assignments')
        git(worktree, 'commit', '--allow-empty', '-m', 'Prepare assigned Feyer task ' + task['task_id'])
        return worktree, textgit(worktree, 'rev-parse', 'HEAD')

    def turn(self, task, state, directory, brief, context, lock_fd):
        worktree = Path(state['worktree'])
        schema = directory / 'schema.json'
        write_json(schema, RESPONSE_SCHEMA)
        timeout = min(self.config.get('max_turn_seconds', 3600), state['deadline_unix'] - time.time())
        if timeout <= 0:
            raise TimeoutError('Assigned deadline expired')
        prompt = ((self.repo / 'AGENTS.md').read_text() + '\n\n'
                  'This is exactly one assigned proposer turn. The supervisor owns commits and publishing. '
                  'Do not run benchmarks, Git/SSH commands, install dependencies, spawn agents or change protected files. '
                  'Only the assignment allowed_paths may change. Return the requested structured response; '
                  'parameters_before_json and parameters_after_json must each encode a JSON object. '
                  'A guidance task produces research notes, never simulator changes. '
                  'A candidate task must stay inside the assigned frozen recipe. '
                  'Do not claim unmeasured speedups. Evaluation is performed later on AMD by the coordinator.\n'
                  + json.dumps(task) + '\n\nBrief:\n' + brief + '\n\nFrozen context:\n' + context)
        model = (task['provider']['model'] if task['provider']['model_policy'] == 'specified'
                 else self.config['designated_model'])
        reasoning = task['provider'].get('reasoning') or self.config['designated_reasoning']
        state.update(resolved_model=model, resolved_reasoning=reasoning)
        write_json(directory / 'state.json', state)
        cmd = [self.config['codex'], 'exec', '--ignore-user-config', '-C', str(worktree), '--approve-for-me',
               '-m', model, '-c', 'model_reasoning_effort=' + json.dumps(reasoning),
               '--json', '--output-schema', str(schema), '-o', str(directory / 'response.json'), '-']
        with (directory / 'events.jsonl').open('w') as out, (directory / 'stderr.log').open('w') as err:
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=out, stderr=err, text=True,
                                       start_new_session=True, pass_fds=(lock_fd,))
            try:
                process.communicate(prompt, timeout=timeout)
            except BaseException:
                terminate_group(process)
                raise
        if process.returncode:
            raise RuntimeError('Codex exited ' + str(process.returncode) + '; inspect task stderr.log')
        return validate_response(json.loads((directory / 'response.json').read_text()))

    def finish(self, task, state, directory):
        worktree = Path(state['worktree'])
        response = validate_response(json.loads((directory / 'response.json').read_text()))
        if textgit(worktree, 'rev-parse', 'HEAD') != state['prepared_sha']:
            raise RuntimeError('Agent moved Git HEAD; refusing publication')
        paths = changed_paths(worktree)
        validate_changes(worktree, paths)
        prefixes = [p[:-2] for p in task['allowed_paths']]
        if any(not any(p.startswith(prefix) for prefix in prefixes) for p in paths):
            raise ValueError('Agent edited outside the assignment allowlist')
        if paths:
            git(worktree, 'add', '--', *paths)
            git(worktree, 'commit', '-m', 'Feyer proposer candidate ' + task['task_id'])
        candidate = textgit(worktree, 'rev-parse', 'HEAD')
        changes = git(worktree, 'diff', task['parent_candidates'][0]['commit_sha'], candidate, '--', 'differometor')
        usage = None
        for line in (directory / 'events.jsonl').read_text().splitlines():
            event = json.loads(line)
            if event.get('type') == 'turn.completed':
                usage = event.get('usage')
        receipt = {
            'schema_version': 'feyer-dag-proposal-v1', 'task_id': task['task_id'],
            'actor': self.actor, 'claim_version': task['ownership']['claim_version'],
            'campaign_id': task['campaign_id'], 'round_id': task['round_id'],
            'round_spec_sha256': task['round_spec_sha256'], 'kind': task['kind'],
            'parent_candidates': task['parent_candidates'], 'commit_sha': candidate,
            'content_sha256': digest(changes), 'assignment_commit': state['assignment_commit'],
            'task_sha256': state['task_sha256'], 'brief_sha256': task['brief']['sha256'],
            'context_sha256': task['context']['sha256'], 'runtime_commit': self.runtime,
            'brief_commit_sha': task['brief']['commit_sha'], 'context_commit_sha': task['context']['commit_sha'],
            'session_id': read_thread_id(directory / 'events.jsonl', None),
            'provider': task['provider'], 'actual_model': None,
            'resolved_model': state.get('resolved_model'), 'resolved_reasoning': state.get('resolved_reasoning'),
            'actual_model_note': 'CLI model explicitly selected; JSON event stream did not report resolved model',
            'usage': usage, 'response': response, 'hypothesis': response['hypothesis'],
            'heuristic_id': response['heuristic_id'],
            'parameters_before': json.loads(response['parameters_before_json']),
            'parameters_after': json.loads(response['parameters_after_json']),
            'ready_for_evaluation': task['kind'] == 'candidate' and response['ready_for_evaluation'],
            'validation': 'not_evaluated', 'elapsed_seconds': time.time() - state['started_at'],
            'deadline_unix': state['deadline_unix'], 'changed_paths': paths,
            'artifacts': {},
        }
        receipt['actual_model'] = recorded_model(receipt['session_id'])
        if receipt['actual_model']:
            receipt['actual_model_note'] = 'Recorded in this Codex session turn_context metadata'
        dest = worktree / 'experiments/worker-results' / task['task_id']
        dest.mkdir(parents=True, exist_ok=True)
        # Keep raw event streams private; version the structured response and brief hashes.
        raw = (directory / 'response.json').read_bytes()
        (dest / 'response.json').write_bytes(raw)
        receipt['artifacts']['response'] = {'path': str((dest / 'response.json').relative_to(worktree)), 'sha256': digest(raw)}
        write_json(dest / 'receipt.json', receipt)
        git(worktree, 'add', '--', str(dest.relative_to(worktree)))
        git(worktree, 'commit', '-m', 'Record Feyer proposer receipt ' + task['task_id'])
        state.update(status='publishing', candidate_sha=candidate,
                     receipt_sha=textgit(worktree, 'rev-parse', 'HEAD'))
        write_json(directory / 'state.json', state)

    def outbox(self, task, state, receipt):
        """Publish a small immutable-revision receipt branch for coordinator ingest."""
        ref = 'refs/heads/worker-results/' + self.actor + '/' + task['task_id']
        existing = textgit(self.repo, 'ls-remote', 'origin', ref)
        parent = state.get('claim_sha', state['assignment_commit'])
        if existing:
            parent = existing.split()[0]
            git(self.repo, 'fetch', 'origin', ref)
            prior = json.loads(git(self.repo, 'show', parent + ':receipt.json'))
            if prior.get('task_sha256') != state['task_sha256']:
                raise ValueError('Outbox already belongs to a different assignment')
            if prior == receipt:
                return parent
        raw = (json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        blob = git(self.repo, 'hash-object', '-w', '--stdin', data=raw).decode().strip()
        tree = git(self.repo, 'mktree', data=('100644 blob ' + blob + '\treceipt.json\n').encode()).decode().strip()
        commit = git(self.repo, 'commit-tree', tree, '-p', parent,
                     data=('Feyer worker receipt ' + task['task_id'] + '\n').encode()).decode().strip()
        git(self.repo, 'push', 'origin', commit + ':' + ref)
        return commit

    def failure_outbox(self, task, state, directory):
        if not state.get('claim_sha') or state.get('failure_published'):
            return
        receipt = {'schema_version': 'feyer-worker-failure-v1', 'task_id': task['task_id'],
                   'task_sha256': state['task_sha256'], 'assignment_commit': state['assignment_commit'],
                   'actor': self.actor, 'claim_version': task['ownership']['claim_version'],
                   'runtime_commit': self.runtime, 'status': state['status'], 'error': state.get('error'),
                   'deadline_unix': state['deadline_unix'], 'parent_candidates': task['parent_candidates']}
        state['outbox_sha'] = self.outbox(task, state, receipt)
        state['failure_published'] = True
        write_json(directory / 'state.json', state)

    def publish(self, task, state, directory):
        branch = task['ownership']['branch']
        git(Path(state['worktree']), '-c', 'credential.helper=!gh auth git-credential',
            'push', 'origin', state['receipt_sha'] + ':refs/heads/' + branch)
        relative = 'experiments/worker-results/' + task['task_id'] + '/receipt.json'
        receipt = json.loads(git(Path(state['worktree']), 'show', state['receipt_sha'] + ':' + relative))
        receipt['publication'] = {'branch': branch, 'commit_sha': state['receipt_sha'], 'path': relative}
        receipt['status'] = 'complete'
        state['outbox_sha'] = self.outbox(task, state, receipt)
        state.update(status='complete', completed_at=time.time())
        write_json(directory / 'state.json', state)

    def execute(self, task, raw, source, lock_fd):
        directory = self.root / 'tasks' / task['task_id']
        directory.mkdir(parents=True, exist_ok=True)
        state_path = directory / 'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        if state:
            if state['task_sha256'] != digest(raw):
                raise ValueError('An existing task ID was mutated')
            if state['status'] == 'publishing':
                self.publish(task, state, directory)
            elif state['status'] in ('running', 'responded', 'preparing', 'claiming'):
                state.update(status='interrupted', error='Uncertain prior execution; operator review required, no automatic rerun')
                write_json(state_path, state)
                self.failure_outbox(task, state, directory)
            elif state['status'] in ('failed', 'interrupted'):
                self.failure_outbox(task, state, directory)
            return
        validate_task(task, self.actor, self.config.get('branch_prefix', 'explore/hetzner/'))
        brief = load_artifact(self.repo, source, task['brief'])
        context = load_artifact(self.repo, source, task['context'])
        if memory_available() < self.config.get('min_available_bytes', 2 * 1024**3):
            return  # Wait without claiming or spending the assigned budget.
        state = {'status': 'claiming', 'task_sha256': digest(raw), 'assignment_commit': source,
                 'started_at': time.time(), 'deadline_unix': task['budget']['deadline_unix'],
                 'task_id': task['task_id'], 'runtime_commit': self.runtime}
        write_json(state_path, state)
        write_json(directory / 'assignment.json', task)
        try:
            claim_ref, claim_sha = self.claim(task, source, digest(raw))
            state.update(status='preparing', claim_ref=claim_ref, claim_sha=claim_sha)
            write_json(state_path, state)
            worktree, prepared = self.prepare(task, directory, brief, context)
            state.update(status='running', worktree=str(worktree), prepared_sha=prepared)
            write_json(state_path, state)
            self.turn(task, state, directory, brief, context, lock_fd)
            state['status'] = 'responded'
            write_json(state_path, state)
            self.finish(task, state, directory)
        except BaseException as exc:
            state.update(status='failed', error=type(exc).__name__ + ': ' + str(exc)[:500], finished_at=time.time())
            write_json(state_path, state)
            try:
                self.failure_outbox(task, state, directory)
            except Exception as publication_error:
                print(json.dumps({'task_id': task['task_id'], 'failure_publication_error': str(publication_error)[:300]}), flush=True)
            raise
        self.publish(task, state, directory)

    def poll(self, lock_fd):
        source = self.fetch()
        prefix = self.config.get('assignment_directory', 'assignments/' + self.actor)
        checked_path(prefix)
        for path in textgit(self.repo, 'ls-tree', '-r', '--name-only', source, '--', prefix).splitlines():
            if not path.endswith('.json'):
                continue
            raw = git(self.repo, 'show', source + ':' + path)
            if len(raw) > 64 * 1024:
                continue
            task = json.loads(raw)
            if task.get('ownership', {}).get('actor') != self.actor:
                continue
            try:
                # Validate identifiers before using them as local paths, even on recovery.
                if not re.fullmatch(r'[0-9a-f]{32}', task['task_id']):
                    raise ValueError('Unsafe task ID')
                self.execute(task, raw, source, lock_fd)
            except Exception as exc:
                print(json.dumps({'task_id': task.get('task_id'), 'error': str(exc)[:500]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    broker = Broker(json.loads(args.config.read_text()))
    with exclusive_lock(broker.root / 'broker.lock') as lock_fd:
        while True:
            try:
                broker.poll(lock_fd)
                write_json(broker.root / 'heartbeat.json', {'pid': os.getpid(), 'checked_at': time.time(),
                    'runtime_commit': broker.runtime, 'actor': broker.actor, 'status': 'poll_complete'})
            except Exception as exc:
                print(json.dumps({'broker_error': str(exc)[:500]}), flush=True)
                if args.once:
                    raise
            if args.once:
                return
            time.sleep(broker.config.get('poll_seconds', 30))


if __name__ == '__main__':
    main()
