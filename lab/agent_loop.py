"""Run a bounded, resumable Codex conversation with measured evaluator feedback."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .client import Client, git

SCHEMA = {
    'type':'object', 'additionalProperties':False,
    'properties':{
        'summary':{'type':'string'}, 'hypothesis':{'type':'string'},
        'ready_for_evaluation':{'type':'boolean'}, 'stop':{'type':'boolean'},
        'notes':{'type':'string'},
    }, 'required':['summary','hypothesis','ready_for_evaluation','stop','notes'],
}


def write_json(path, value):
    path=Path(path)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def changed_paths(repo):
    tracked=subprocess.check_output(['git','-C',str(repo),'diff','--name-only','-z','HEAD']).decode().split('\0')
    new=subprocess.check_output(['git','-C',str(repo),'ls-files','--others','--exclude-standard','-z']).decode().split('\0')
    return sorted(set(p for p in tracked+new if p))


def validate_changes(repo, paths):
    for name in paths:
        if not name.startswith(('differometor/','experiments/notes/')):
            raise ValueError(f'Agent changed a protected path: {name}')
        path=Path(repo)/name
        if path.is_symlink():
            raise ValueError(f'Agent may not add symlinks: {name}')
        if path.exists() and path.stat().st_size>2*1024*1024:
            raise ValueError(f'Candidate file exceeds 2 MiB: {name}')


def github_status(slug, job, target=None):
    result=job.get('result') or {}
    if job['status'] in ('queued','running'):
        state,description='pending',f'{job["profile"]} queued on AMD CPU 2'
    elif job['status']=='completed':
        state='success'
        description=f'{result.get("verdict")}: {result.get("first_run_seconds",0):.3f}s; peak RAM {(result.get("peak_rss_kib") or 0)/1024**2:.2f} GiB'
    else:
        state,description='failure',(job.get('error') or job['status'])[:130]
    command=['gh','api','--method','POST',f'repos/{slug}/statuses/{job["sha"]}',
             '-f',f'state={state}','-f',f'context=feyer/{job["profile"]}',
             '-f',f'description={description[:140]}']
    if target:command+=['-f',f'target_url={target}']
    result=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    if result.returncode:
        print('GitHub status publication failed: '+result.stderr.strip(),flush=True)


class SessionBusyError(RuntimeError):
    pass


class CodexTurnError(RuntimeError):
    def __init__(self, message, thread_id=None, timed_out=False, interrupted=False):
        super().__init__(message)
        self.thread_id = thread_id
        self.timed_out = timed_out
        self.interrupted = interrupted


@contextlib.contextmanager
def exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SessionBusyError(f'Another supervisor owns {path}') from exc
        try:
            yield handle.fileno()
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_thread_id(events, previous=None):
    events = Path(events)
    if events.exists():
        for line in events.read_text(errors='replace').splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('type') == 'thread.started':
                previous = event['thread_id']
            elif event.get('type') == 'system' and event.get('subtype') == 'init':
                previous = event.get('session_id') or previous
    return previous


def validate_response(response):
    if not isinstance(response, dict) or set(response) != set(SCHEMA['required']):
        raise ValueError('Agent response must match the required schema')
    for key in ('summary', 'hypothesis', 'notes'):
        if not isinstance(response[key], str):
            raise ValueError(f'Agent response {key} must be text')
    for key in ('ready_for_evaluation', 'stop'):
        if not isinstance(response[key], bool):
            raise ValueError(f'Agent response {key} must be a boolean')
    return response


def terminate_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def codex_turn(worktree, session_dir, iteration, prompt, thread_id, timeout, lock_fds=()):
    output = session_dir / f'turn-{iteration:02d}.json'
    events = session_dir / f'turn-{iteration:02d}.jsonl'
    errors = session_dir / f'turn-{iteration:02d}.stderr.log'
    schema = session_dir / 'response-schema.json'
    write_json(schema, SCHEMA)
    command = ['codex', 'exec', '-C', str(worktree), '--approve-for-me']
    if thread_id:
        command += ['resume', '--json', '--output-schema', str(schema), '-o', str(output), thread_id, '-']
    else:
        command += ['--json', '--output-schema', str(schema), '-o', str(output), '-']
    failure = None
    with events.open('w') as stdout, errors.open('w') as stderr:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                   text=True, start_new_session=True, pass_fds=tuple(lock_fds))
        try:
            process.communicate(prompt, timeout=timeout)
        except BaseException as exc:
            failure = exc
        finally:
            if failure is not None:
                terminate_group(process)
    thread_id = read_thread_id(events, thread_id)
    if failure is not None:
        timed_out = isinstance(failure, subprocess.TimeoutExpired)
        raise CodexTurnError('Agent turn exceeded its time budget' if timed_out else f'{type(failure).__name__}: {failure}',
                             thread_id, timed_out, isinstance(failure, (KeyboardInterrupt, SystemExit))) from failure
    if process.returncode:
        raise CodexTurnError(f'Codex exited {process.returncode}; inspect {errors}', thread_id)
    if not thread_id:
        raise CodexTurnError('Codex did not report a resumable conversation ID')
    try:
        response = validate_response(json.loads(output.read_text()))
    except (OSError, ValueError) as exc:
        raise CodexTurnError(f'Invalid agent response: {exc}', thread_id) from exc
    return thread_id, response


def _save(state, status_file, **changes):
    state.update(changes)
    write_json(status_file, state)


def _push(worktree, branch):
    subprocess.run(['git', '-C', str(worktree), '-c', 'credential.helper=!gh auth git-credential',
                    'push', 'origin', branch], check=True)


def _recover_submission(active, args, client, state, status_file):
    """A lost SSH response must not cause a duplicate evaluation on resume."""
    profile = active.get('submitting_profile')
    if not profile:
        return
    candidates = client.request({'action': 'list', 'limit': 10000})
    matches = [job for job in candidates if job['sha'] == active['sha']
               and job['profile'] == profile and job['agent'] == args.name
               and job['direction'] == args.direction
               and job['created_at'] >= active['submission_started_at'] - 1]
    if len(matches) != 1:
        raise RuntimeError('Previous submission outcome is uncertain; inspect the queue before retrying. '
                           f'Expected one matching {profile} job, found {len(matches)}.')
    active['jobs'][profile] = matches[0]['id']
    active.pop('submitting_profile', None)
    _save(state, status_file, active_candidate=active)


def _finish_record(active, args, worktree, directory, state, status_file):
    feedback = active['feedback']
    records = worktree / 'experiments' / 'runs' / args.name
    records.mkdir(parents=True, exist_ok=True)
    record = records / f'candidate-{active["iteration"]:02d}.json'
    write_json(record, feedback)
    relative = record.relative_to(worktree).as_posix()
    subprocess.run(['git', '-C', str(worktree), 'add', '--', relative], check=True)
    changed = subprocess.run(['git', '-C', str(worktree), 'diff', '--cached', '--quiet', '--', relative])
    if changed.returncode == 1:
        subprocess.run(['git', '-C', str(worktree), 'commit', '-m',
                        f'Record evaluator feedback for {active["sha"][:12]}', '--', relative], check=True)
    elif changed.returncode:
        raise RuntimeError('Unable to inspect feedback commit')
    _push(worktree, args.branch)
    record_sha = git(worktree, 'rev-parse', 'HEAD')
    target = f'https://github.com/{args.github_repo}/blob/{record_sha}/{relative}'
    for profile in ('screen', 'full'):
        if profile in feedback:
            github_status(args.github_repo, feedback[profile], target)
    stop = active['response']['stop'] and not active.get('continue_after_evaluation', False)
    _save(state, status_file, feedback=feedback, candidates=active['iteration'],
          active_candidate=None, status='feedback_ready', stop_requested=stop)
    return stop


def _advance_candidate(active, args, client, worktree, directory, state, status_file, deadline):
    """Return False when budget/wait expiry leaves durable work for --resume."""
    _recover_submission(active, args, client, state, status_file)
    for profile in ('screen', 'full'):
        if profile in active['feedback']:
            continue
        if profile == 'full':
            screen = active['feedback'].get('screen', {})
            total = (screen.get('result') or {}).get('first_run_seconds', float('inf'))
            if screen.get('status') != 'completed' or (active['iteration'] > 1 and total > args.baseline_seconds * 1.02):
                active['feedback']['full_skipped'] = 'Screen failed or did not pass the promotion threshold'
                break
        if profile not in active['jobs']:
            if time.monotonic() >= deadline:
                _save(state, status_file, status='budget_exhausted', active_candidate=active,
                      reason=f'No new {profile} job started after the deadline; resume to continue')
                return False
            active['submitting_profile'] = profile
            active['submission_started_at'] = time.time()
            _save(state, status_file, status=f'submitting_{profile}', active_candidate=active)
            job = client.submit(worktree, args.branch, args.name, args.direction,
                                active['response']['hypothesis'], profile, active['sha'])
            active['jobs'][profile] = job['id']
            active.pop('submitting_profile', None)
            _save(state, status_file, active_candidate=active, job_id=job['id'])
            github_status(args.github_repo, job)
        job_id = active['jobs'][profile]
        _save(state, status_file, status=f'evaluating_{profile}', job_id=job_id)
        try:
            # Previously submitted work may finish after the coding/submission deadline.
            job = client.wait(job_id, timeout=1800)
        except TimeoutError:
            _save(state, status_file, status='waiting_for_evaluation', active_candidate=active,
                  reason=f'Job {job_id} is still pending; --resume reconnects without resubmitting')
            return False
        active['feedback'][profile] = job
        _save(state, status_file, active_candidate=active)
        try:
            client.fetch(job_id, directory / 'results' / job_id)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            active['feedback'][profile]['artifact_fetch_error'] = str(exc)
            _save(state, status_file, active_candidate=active)
        github_status(args.github_repo, job)
    _finish_record(active, args, worktree, directory, state, status_file)
    return True


def _commit_candidate(pending, args, worktree, state, status_file):
    response = pending['response']
    before, current = pending['before_sha'], git(worktree, 'rev-parse', 'HEAD')
    subject = f'Experiment {args.name} {pending["iteration"]}: {response["summary"][:120]}'
    if current != before:
        # Recover the narrow crash window after our commit but before state was saved.
        if not (pending.get('committing') and git(worktree, 'rev-parse', 'HEAD^') == before
                and git(worktree, 'show', '-s', '--format=%s', 'HEAD') == subject):
            raise ValueError('Agent changed Git history; manual review required')
    else:
        paths = changed_paths(worktree)
        validate_changes(worktree, paths)
        if not response['ready_for_evaluation'] or not paths:
            _save(state, status_file, pending_turn=None, status='complete', reason='Agent returned no candidate',
                  last_response=response)
            return None
        pending['committing'] = True
        _save(state, status_file, pending_turn=pending)
        subprocess.run(['git', '-C', str(worktree), 'add', '--', *paths], check=True)
        subprocess.run(['git', '-C', str(worktree), 'commit', '-m', subject], check=True)
        current = git(worktree, 'rev-parse', 'HEAD')
    active = {'iteration': pending['iteration'], 'sha': current, 'response': response, 'jobs': {},
              'feedback': {'candidate_sha': current, 'agent_response': response}}
    _save(state, status_file, active_candidate=active, pending_turn=None,
          candidates=pending['iteration'], candidate_sha=current, status='candidate_ready')
    return active


def _run_locked(args, repo, worktree, directory, status_file, lock_fds):
    if status_file.exists() and not args.resume:
        raise ValueError('Session already exists; use --resume or choose a new session name')
    if args.resume and not status_file.exists():
        raise ValueError('No saved session exists to resume')
    state = json.loads(status_file.read_text()) if status_file.exists() else {}
    provider = getattr(args, 'agent_provider', 'codex')
    model = getattr(args, 'agent_model', None)
    if state and state.get('agent_model') != model:
        raise ValueError('Cannot change the model while resuming a session')
    if state and state.get('agent_provider', 'codex') != provider:
        raise ValueError('Cannot resume a session with a different agent provider')
    for key, expected in (('branch', args.branch), ('worktree', str(worktree)), ('direction', args.direction)):
        if key in state and state[key] != expected:
            raise ValueError(f'Resume {key} does not match the saved session')
    invocation_started = time.time()
    deadline = time.monotonic() + args.max_minutes * 60
    _save(state, status_file, pid=os.getpid(), branch=args.branch, worktree=str(worktree), direction=args.direction,
          status='starting', agent_provider=provider, agent_model=model, candidate_limit=args.max_candidates, invocation_started_at=invocation_started,
          invocation_deadline_at=invocation_started + args.max_minutes * 60)
    try:
        if not worktree.exists():
            subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '-b', args.branch, str(worktree), 'main'], check=True)
        if git(worktree, 'branch', '--show-current') != args.branch:
            raise ValueError('Worktree branch does not match assigned direction')
        if changed_paths(worktree) and not args.resume:
            raise ValueError('Initial agent worktree must be clean')
        client = Client(args.host)
        brief_path = getattr(args, 'brief', None) or (repo / 'experiments' / 'initial-agent.md')
        brief = Path(brief_path).read_text()
        if provider == 'claude':
            from .claude_turn import claude_turn
            turn = claude_turn
            turn_options = {'model': model}
        else:
            turn = codex_turn
            turn_options = {}
        while True:
            active = state.get('active_candidate')
            if active:
                if not _advance_candidate(active, args, client, worktree, directory, state, status_file, deadline):
                    return
                if state.get('stop_requested'):
                    _save(state, status_file, status='complete', reason='Agent requested stop after evaluated candidate')
                    return
            pending = state.get('pending_turn')
            if pending:
                number = pending['number']
                state['thread_id'] = read_thread_id(directory / f'turn-{number:02d}.jsonl', state.get('thread_id'))
                output = directory / f'turn-{number:02d}.json'
                if 'response' not in pending and output.exists():
                    try:
                        pending['response'] = validate_response(json.loads(output.read_text()))
                    except (OSError, ValueError):
                        pass
                _save(state, status_file, pending_turn=pending)
                if 'response' in pending:
                    if _commit_candidate(pending, args, worktree, state, status_file) is None:
                        return
                    continue
                if git(worktree, 'rev-parse', 'HEAD') != pending['before_sha']:
                    raise ValueError('Git history changed during the interrupted agent turn')
            if args.max_candidates is not None and int(state.get('candidates', 0)) >= args.max_candidates:
                _save(state, status_file, status='complete', reason='Candidate limit reached')
                return
            if time.monotonic() >= deadline:
                _save(state, status_file, status='budget_exhausted', reason='No new agent turn started after the deadline')
                return
            iteration = int(state.get('candidates', 0)) + 1
            turn_number = int(state.get('turn_count', 0)) + 1
            pending = {'number': turn_number, 'iteration': iteration,
                       'before_sha': git(worktree, 'rev-parse', 'HEAD')}
            _save(state, status_file, status='coding', iteration=iteration, turn_count=turn_number, pending_turn=pending)
            thread = state.get('thread_id')
            prompt = brief if not thread else 'Continue the same investigation using the evaluator feedback below.'
            prompt += ('\n\nManaged session: edit only differometor/** and experiments/notes/**. Do NOT commit, push, invoke SSH, '
                       'or run the full benchmark locally. The supervisor handles Git and evaluation. Keep the official benchmark '
                       'and harness unchanged. Make one focused candidate, then return the requested JSON. Returning does not discard '
                       'this conversation: you will be resumed with measured feedback. Do not spawn agents. If a previous turn was '
                       'interrupted, inspect and continue its uncommitted edits.\n')
            if args.max_candidates is None:
                prompt += (f'Candidate {iteration}. There is no candidate-count limit. The user removed the former '
                           'four-candidate cap; this supersedes older brief, worktree rules and conversation instructions '
                           'about that cap. Continue exploring after candidate four while time remains.\n')
            else:
                prompt += f'Candidate {iteration}/{args.max_candidates}.\n'
            prompt += f'Remaining session seconds: {max(0, int(deadline-time.monotonic()))}.\n'
            if state.get('feedback'):
                prompt += 'Evaluator feedback:\n' + json.dumps(state['feedback'], indent=2) + '\n'
            try:
                thread, response = turn(worktree, directory, turn_number, prompt, thread,
                                              max(0.01, deadline-time.monotonic()), lock_fds, **turn_options)
            except CodexTurnError as exc:
                _save(state, status_file, thread_id=exc.thread_id or state.get('thread_id'),
                      status='budget_exhausted' if exc.timed_out else 'failed', error=str(exc))
                if exc.timed_out:
                    return
                raise
            pending['response'] = response
            _save(state, status_file, thread_id=thread, last_response=response, pending_turn=pending)
            if _commit_candidate(pending, args, worktree, state, status_file) is None:
                return
    except BaseException as exc:
        interrupted = isinstance(exc, (KeyboardInterrupt, SystemExit)) or (
            isinstance(exc, CodexTurnError) and exc.interrupted)
        _save(state, status_file, status='interrupted' if interrupted else 'failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        write_json(status_file, state)


def run(args):
    repo = args.repo.resolve()
    worktree = args.worktree.resolve()
    directory = repo / '.lab' / 'sessions' / args.name
    directory.mkdir(parents=True, exist_ok=True)
    status_file = directory / 'status.json'
    worktree_lock = repo / '.lab' / 'locks' / (hashlib.sha256(str(worktree).encode()).hexdigest() + '.lock')
    old_term = signal.getsignal(signal.SIGTERM)
    def stop(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        with exclusive_lock(directory / 'supervisor.lock') as session_fd, exclusive_lock(worktree_lock) as worktree_fd:
            _run_locked(args, repo, worktree, directory, status_file, (session_fd, worktree_fd))
    finally:
        signal.signal(signal.SIGTERM, old_term)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-provider', choices=('codex', 'claude'), default='codex')
    parser.add_argument('--agent-model', help='Explicit Claude model; omit to use the account default')
    parser.add_argument('--brief', type=Path, help='Direction-specific agent instructions')
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--worktree',type=Path,required=True)
    parser.add_argument('--branch',default='explore/seed-agent')
    parser.add_argument('--name',default='seed-agent')
    parser.add_argument('--direction',default='first-pass')
    parser.add_argument('--host',default='amd-hackathon')
    parser.add_argument('--github-repo',default='timbtz/feyer-search-lab')
    parser.add_argument('--max-candidates',type=int,default=None,
                        help='Optional candidate-count limit; omitted means no count limit')
    parser.add_argument('--max-minutes',type=float,default=60)
    parser.add_argument('--baseline-seconds',type=float,default=35.737065)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if (args.max_candidates is not None and args.max_candidates<1) or args.max_minutes<=0 or '/' in args.name or args.name in ('','.','..'):
        parser.error('Invalid session name or budget')
    if args.agent_model and args.agent_provider != 'claude':
        parser.error('--agent-model currently applies only to Claude')
    run(args)


if __name__=='__main__':
    main()
