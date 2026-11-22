"""Durable, bounded Claude-first search; evaluator admission remains authoritative.

One process owns one lane. Two processes may share a campaign, provider registry,
and deadline. The evaluator hook must implement idempotence by request_id.
"""
import argparse
import ast
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time
import uuid

from .agent_loop import (changed_paths, codex_turn, exclusive_lock, read_thread_id,
                         terminate_group, validate_changes, validate_response)
from .claude_turn import claude_turn

MODELS = {'claude': 'claude-opus-5-5', 'codex': 'gpt-6-astra'}
TERMINAL = {'completed', 'failed', 'blocked', 'interrupted', 'expired'}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def read_json(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True,
                                   timeout=120).strip()


@contextlib.contextmanager
def registry_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Providers:
    """Short atomic registry updates; never hold the registry lock during a call."""
    def __init__(self, directory, owner, deadline, clock=time.time):
        self.directory, self.owner, self.deadline, self.clock = Path(directory), owner, deadline, clock
        self.path = self.directory / 'providers.json'

    def choose(self):
        now = self.clock()
        with registry_lock(self.directory / 'providers.lock'):
            data = read_json(self.path, {})
            for provider in ('claude', 'codex'):
                item = data.get(provider, {})
                if now < item.get('blocked_until', 0):
                    if provider == 'claude' and item.get('kind') == 'transient':
                        return None  # Retry Claude; quota/auth alone authorizes provider fallback.
                    continue
                if item.get('needs_probe'):
                    if now < item.get('probe_until', 0) and item.get('probe_owner') != self.owner:
                        continue
                    item.update(probe_owner=self.owner, probe_until=min(now + 1800, self.deadline))
                    data[provider] = item
                    write_json(self.path, data)
                return provider
        return None

    def success(self, provider):
        with registry_lock(self.directory / 'providers.lock'):
            data = read_json(self.path, {})
            data[provider] = {'failures': 0, 'observed_at': self.clock()}
            write_json(self.path, data)

    def failure(self, provider, error):
        # Classify structured/error text, not arbitrary assistant prose.
        lower = error.lower()
        auth = any(x in lower for x in ('authentication_error', 'invalid api key', 'not logged in',
                                        'authentication failed', 'login required', 'unauthorized'))
        quota = any(x in lower for x in ('usage limit', 'usage_limit', 'quota exceeded',
                                         'rate_limit_error', 'rate limit', 'rate_limit_exceeded',
                                         'insufficient_quota', 'out of extra usage', 'hit your limit'))
        now = self.clock()
        with registry_lock(self.directory / 'providers.lock'):
            data = read_json(self.path, {})
            count = data.get(provider, {}).get('failures', 0) + 1
            kind = 'auth' if auth else 'quota' if quota else 'transient'
            delay = min(300, 15 * 2 ** min(count - 1, 5))
            if auth:
                until = self.deadline
            elif quota:
                # Honor unambiguous retry-after seconds; prose reset times need operator review.
                retry = re.search(r'retry[_ -]?after["\s:=]+(\d+(?:\.\d+)?)', lower)
                until = now + (max(60, float(retry.group(1))) if retry else 6 * 3600)
                reset = re.search(r'(?:resets?_at|reset_unix)["\s:=]+(\d+(?:\.\d+)?)', lower)
                if reset and math.isfinite(float(reset.group(1))) and float(reset.group(1)) > now:
                    until = float(reset.group(1))
            else:
                until = now + delay
            data[provider] = {'failures': count, 'kind': kind, 'blocked_until': until,
                              'needs_probe': True, 'observed_at': now,
                              'error_digest': digest(error)}
            write_json(self.path, data)
        return kind


def turn_error(directory, iteration, exception):
    """Only diagnostic streams/error events classify quota; exclude model-authored prose."""
    text = str(exception)
    errors = directory / f'turn-{iteration:02d}.stderr.log'
    if errors.exists():
        text += '\n' + errors.read_text(errors='replace')[-16000:]
    events = directory / f'turn-{iteration:02d}.jsonl'
    if events.exists():
        for line in events.read_text(errors='replace').splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('type') in ('error', 'turn.failed') or event.get('is_error'):
                text += '\n' + json.dumps(event)
    return text


def turn_usage(directory, iteration):
    found = []
    path = directory / f'turn-{iteration:02d}.jsonl'
    if path.exists():
        for line in path.read_text(errors='replace').splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('type') in ('result', 'turn.completed'):
                found.append({key: event[key] for key in ('usage', 'total_cost_usd', 'modelUsage') if key in event})
    return found


def validate_evaluation(result, request):
    if not isinstance(result, dict) or any(result.get(k) != request[k] for k in ('request_id', 'sha')):
        raise ValueError('Evaluator response identity mismatch')
    if result.get('status') not in TERMINAL | {'queued', 'running'}:
        raise ValueError('Unknown evaluator state')
    if result['status'] == 'completed' and type(result.get('official_passed')) is not bool:
        raise ValueError('Completed evaluation lacks explicit dual-benchmark verdict')
    return result


class Supervisor:
    def __init__(self, args, model_call=None, evaluate=None, publish=None, clock=time.time):
        self.args, self.clock = args, clock
        self.worktree = Path(args.worktree).resolve()
        self.campaign = Path(args.campaign_dir).resolve()
        self.directory = self.campaign / 'sessions' / args.name
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'status.json'
        self.brief = Path(args.brief).read_text()
        self.model_call = model_call or self._model_call
        self.evaluate = evaluate or self._evaluate
        self.publish = publish or self._publish
        self.providers = Providers(self.campaign, args.name, args.deadline_unix, clock)
        self.lock_fds = ()
        self.state = None

    def save(self):
        self.state['observed_at'] = self.clock()
        self.state['pid'] = os.getpid()
        self.state['process_match'] = 'lab.overnight_search'
        write_json(self.path, self.state)
        if self.args.status_export:
            write_json(self.args.status_export, self.state)

    def initialize(self):
        if git(self.worktree, 'branch', '--show-current') != self.args.branch:
            raise ValueError('Assigned branch does not match worktree')
        fixed = {'deadline_unix': self.args.deadline_unix, 'worktree': str(self.worktree),
                 'branch': self.args.branch, 'lane': self.args.lane, 'brief_sha256': digest(self.brief),
                 'evaluator_command': self.args.evaluator_command,
                 'codex_bin_dir': str(Path(self.args.codex_bin_dir).resolve()),
                 'codex_wrapper_sha256': hashlib.sha256((Path(self.args.codex_bin_dir) / 'codex').read_bytes()).hexdigest()}
        previous = read_json(self.path)
        if previous:
            if not self.args.resume or any(previous.get(k) != v for k, v in fixed.items()):
                raise ValueError('Resume requires identical lane, worktree, brief, evaluator and deadline')
            self.state = previous
        else:
            if self.args.resume:
                raise ValueError('No session exists to resume')
            if changed_paths(self.worktree):
                raise ValueError('New session requires a clean worktree')
            initial = git(self.worktree, 'rev-parse', 'HEAD')
            self.state = {**fixed, 'id': self.args.name, 'name': self.args.name, 'host': 'local',
                          'schema_version': 'feyer-overnight-session-v1', 'started_at': self.clock(),
                          'initial_sha': initial, 'expected_head': initial, 'iteration': 0,
                          'candidate_count': 0, 'nonimproving': 0, 'no_candidate': 0,
                          'threads': {}, 'history': [], 'status': 'starting',
                          'runtime_commit': git(Path(__file__).resolve().parent, 'rev-parse', 'HEAD'),
                          'runtime_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        current_runtime = {'commit': git(Path(__file__).resolve().parent, 'rev-parse', 'HEAD'),
                           'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self.state['current_runtime'] = current_runtime
        self.state.setdefault('runtime_history', []).append({**current_runtime, 'observed_at': self.clock()})
        with registry_lock(self.campaign / 'campaign.lock'):
            manifest = read_json(self.campaign / 'campaign.json', {'deadline_unix': self.args.deadline_unix, 'lanes': {}})
            if manifest['deadline_unix'] != self.args.deadline_unix:
                raise ValueError('Shared campaign deadline differs')
            lane = str(self.args.lane)
            identity = {'name': self.args.name, 'worktree': str(self.worktree), 'branch': self.args.branch}
            if lane in manifest['lanes'] and manifest['lanes'][lane] != identity:
                raise ValueError('Campaign lane already assigned')
            if any(k != lane and (v['worktree'] == str(self.worktree) or v['branch'] == self.args.branch)
                   for k, v in manifest['lanes'].items()):
                raise ValueError('Worktree/branch already belongs to another lane')
            manifest['lanes'][lane] = identity
            write_json(self.campaign / 'campaign.json', manifest)
        self.save()

    def check_head(self):
        if git(self.worktree, 'branch', '--show-current') != self.args.branch:
            raise ValueError('Worktree branch changed externally')
        if git(self.worktree, 'rev-parse', 'HEAD') != self.state['expected_head']:
            raise ValueError('Worktree HEAD changed externally')

    def prompt(self):
        repair = self.state.get('last_feedback')
        guidance = ''
        if self.state['nonimproving'] >= 3:
            guidance += ('\nThree consecutive evaluated proposals were not explicitly confirmed improvements. '
                         'Refine conservative simulator variants, reduce complexity and timing variance, '
                         'or change the hypothesis using measured feedback. Preserve all physical requirements.\n')
        if self.state['no_candidate']:
            guidance += ('\nYour previous turn returned no evaluable simulator change. Use your handoff to choose '
                         'one concrete next experiment or repair; do not repeat the identical handoff. '
                         'Preserved untested edits are available in your branch.\n')
        return (self.brief + '\n\nManaged campaign operating rules:\n'
                'The user authorized this new eight-hour campaign, superseding old one-hour budgets. '
                f'Absolute deadline {self.args.deadline_unix}; remaining seconds {max(0, int(self.args.deadline_unix-self.clock()))}. '
                'Work only in this assigned worktree. Edit differometor/** and experiments/notes/** only. '
                'Do not commit, push, call GitHub/SSH, launch benchmarks, install dependencies or spawn agents. '
                'Preserve both official benchmark files, all fixture/reference data, all 101 frequencies and 193 '
                'design variables in the large setup, double precision, physical outputs and gradients, and '
                'the three official JIT stages. No answer caching or persistent compilation cache. '
                'Never hardcode fixtures, recognize benchmark inputs, alter benchmark/reference data, '
                'monkeypatch validation or hide work outside the timer. Improvements must generalize '
                'to other optical setups. Independent source review is required before promotion. '
                'Package compiler settings are allowed only when correctness and generalization are preserved. '
                'Both unchanged full benchmarks are required; large first-run time is primary and aLIGO tests '
                'transfer. Do not average their totals. Public passes alone are not promotion: retain explicit '
                'generalization/strict review and stable fresh-process confirmations. '
                'Return summary,hypothesis,ready_for_evaluation,stop,notes using the required schema. '
                'A stop handoff ends this hypothesis, not the user-authorized campaign.\n'
                + guidance + '\nYour most recent evaluator feedback (authoritative, may fail):\n'
                + json.dumps(repair, sort_keys=True) + '\nMost recent research handoff:\n'
                + json.dumps(self.state.get('last_handoff'), sort_keys=True)
                + '\nPreserved partial turn (finish or repair permitted edits; never assume evaluated):\n'
                + json.dumps(self.state.get('partial_turn'), sort_keys=True) + '\n')

    def _model_call(self, provider, iteration, prompt, thread, timeout):
        if provider == 'claude':
            return claude_turn(self.worktree, self.directory, iteration, prompt, thread, timeout,
                               self.lock_fds, model=MODELS[provider])
        return codex_turn(self.worktree, self.directory, iteration, prompt, thread, timeout, self.lock_fds)

    def _publish(self):
        subprocess.run(['git', '-C', str(self.worktree), '-c', 'credential.helper=',
                        '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin',
                        'HEAD:refs/heads/' + self.args.branch], check=True, timeout=120)

    def _evaluate(self, request):
        attempts = self.directory / 'evaluations' / request['request_id']
        attempts.mkdir(parents=True, exist_ok=True)
        stamp = str(time.time_ns())
        with (attempts / (stamp + '.stdout')).open('w+') as out, (attempts / (stamp + '.stderr')).open('w') as err:
            process = subprocess.Popen(shlex.split(self.args.evaluator_command), stdin=subprocess.PIPE,
                                       stdout=out, stderr=err, text=True, start_new_session=True,
                                       pass_fds=tuple(self.lock_fds))
            try:
                process.communicate(json.dumps(request), timeout=self.args.hook_timeout)
            except BaseException:
                terminate_group(process)
                raise
            if process.returncode:
                raise RuntimeError(f'Evaluator hook failed {process.returncode}; durable request retained')
            out.seek(0)
            return json.load(out)

    def commit_pending(self):
        pending = self.state['pending_commit']
        head = git(self.worktree, 'rev-parse', 'HEAD')
        if head == pending['before_sha']:
            self.check_head()
            paths = changed_paths(self.worktree)
            if pending['kind'] == 'model':
                validate_changes(self.worktree, paths)
                for name in paths:
                    path = self.worktree / name
                    if name.endswith('.py') and path.is_file():
                        ast.parse(path.read_text(), filename=name)
            elif set(paths) != {pending['artifact_path']}:
                raise ValueError('Unexpected changes while publishing feedback')
            if paths:
                subprocess.run(['git', '-C', str(self.worktree), 'add', '--', *paths], check=True, timeout=60)
                subprocess.run(['git', '-C', str(self.worktree), 'commit', '-m', pending['subject']], check=True, timeout=120)
                head = git(self.worktree, 'rev-parse', 'HEAD')
        elif (git(self.worktree, 'rev-parse', 'HEAD^') != pending['before_sha'] or
              git(self.worktree, 'log', '-1', '--format=%s') != pending['subject']):
            raise ValueError('Unexpected HEAD during commit recovery')
        self.state['expected_head'] = head
        pending['committed_sha'] = head
        self.save()
        self.publish()  # Retry same commit if push succeeds but acknowledgement is lost.
        if pending['kind'] == 'model' and pending['evaluate']:
            if changed_paths(self.worktree):
                raise ValueError('Candidate must be clean before evaluation')
            diff = git(self.worktree, 'diff', pending['before_sha'], head, '--', 'differometor')
            source_path = self.directory / ('candidate-' + head + '.diff')
            source_path.write_text(diff)
            request = {'schema_version': 'feyer-overnight-evaluation-v1', 'request_id': uuid.uuid4().hex,
                       'sha': head, 'branch': self.args.branch, 'worktree': str(self.worktree),
                       'session': self.args.name, 'lane': self.args.lane, 'deadline_unix': self.args.deadline_unix,
                       'requires_source_review': True, 'parent_sha': pending['before_sha'],
                       'hypothesis': pending['response']['hypothesis'], 'source_diff_sha256': digest(diff),
                       'source_diff_path': str(source_path)}
            if self.clock() < self.args.deadline_unix:
                self.state['active_evaluation'] = request
                self.state['candidate_count'] += 1
            else:
                self.state['history'].append({'kind': 'unevaluated_deadline_checkpoint', 'sha': head})
        self.state.pop('pending_commit')
        self.save()

    def evaluate_pending(self):
        request = self.state['active_evaluation']
        self.state['status'] = 'evaluating'
        self.save()  # Request already durable before external invocation.
        result = validate_evaluation(self.evaluate(request), request)
        write_json(self.directory / 'evaluations' / (request['request_id'] + '.json'), result)
        if result['status'] not in TERMINAL:
            return False
        self.state['last_feedback'] = result
        # Only explicit evaluator admission may reset stagnation; no guessed Pareto/winner claim.
        improved = result.get('confirmed_improvement') is True and result.get('official_passed') is True
        self.state['nonimproving'] = 0 if improved else self.state['nonimproving'] + 1
        self.state['history'].append({'kind': 'evaluation', 'request': request, 'result': result})
        rel = f'experiments/runs/{self.campaign.name}/{self.args.name}/{request["request_id"]}.json'
        self.check_head()
        if changed_paths(self.worktree):
            raise ValueError('Unexpected worktree changes during evaluation')
        # Intent precedes artifact mutation, so restart can reconstruct the exact feedback file.
        self.state['pending_commit'] = {'kind': 'feedback', 'before_sha': self.state['expected_head'],
                                        'subject': f'lab: {self.args.name} feedback {request["request_id"]}',
                                        'artifact_path': rel, 'artifact': result, 'evaluate': False}
        self.state.pop('active_evaluation')
        self.save()
        write_json(self.worktree / rel, result)
        return True

    def model_step(self):
        pending = self.state.get('pending_turn')
        if pending:
            output = self.directory / f'turn-{pending["iteration"]:02d}.json'
            if output.exists():
                response = validate_response(read_json(output))
                thread = read_thread_id(self.directory / f'turn-{pending["iteration"]:02d}.jsonl', pending['thread'])
                if not thread:
                    raise ValueError('Recovered model output lacks conversation identity')
                if pending['thread'] and thread != pending['thread']:
                    raise ValueError('Recovered conversation identity changed')
                return self.finish_turn(pending, thread, response)
            self.state['history'].append({'kind': 'interrupted_turn', **pending})
            observed = read_thread_id(self.directory / f'turn-{pending["iteration"]:02d}.jsonl', pending['thread'])
            if observed:
                self.state['threads'][pending['provider']] = observed
            self.state.pop('pending_turn')
            self.save()
        if self.clock() >= self.args.deadline_unix:
            return False
        self.check_head()
        validate_changes(self.worktree, changed_paths(self.worktree))
        provider = self.providers.choose()
        if not provider:
            self.state['status'] = 'waiting_provider'
            self.save()
            return False
        iteration = self.state['iteration'] + 1
        prompt = self.prompt()
        prompt_path = self.directory / f'turn-{iteration:02d}.prompt.txt'
        prompt_path.write_text(prompt)
        rules = (self.worktree / 'AGENTS.md').read_text()
        write_json(self.directory / f'turn-{iteration:02d}.input.json',
                   {'prompt': prompt, 'prompt_sha256': digest(prompt), 'worktree_rules': rules,
                    'worktree_rules_sha256': digest(rules), 'provider': provider,
                    'runtime': self.state['current_runtime'],
                    'claude_combined_prompt_sha256': digest(
                        'Repository rules (the current supervisor instructions override obsolete budgets):\n'
                        + rules + '\n\n' + prompt) if provider == 'claude' else None})
        pending = {'iteration': iteration, 'provider': provider, 'thread': self.state['threads'].get(provider),
                   'before_sha': self.state['expected_head'], 'prompt_sha256': digest(prompt),
                   'prompt_path': str(prompt_path), 'requested_model': MODELS[provider],
                   'reasoning_effort': 'high' if provider == 'codex' else None, 'started_at': self.clock(),
                   'worktree_rules_sha256': digest(rules), 'runtime': self.state['current_runtime']}
        self.state.update(pending_turn=pending, iteration=iteration, provider=provider,
                          requested_model=MODELS[provider], status='coding')
        self.save()
        try:
            thread, response = self.model_call(provider, iteration, prompt, pending['thread'],
                                               min(self.args.max_turn_seconds, self.args.deadline_unix-self.clock()))
        except Exception as exc:
            text = turn_error(self.directory, iteration, exc)
            category = self.providers.failure(provider, text)
            thread = getattr(exc, 'thread_id', None) or read_thread_id(self.directory / f'turn-{iteration:02d}.jsonl', pending['thread'])
            if thread:
                self.state['threads'][provider] = thread
            self.state['history'].append({'kind': 'model_error', **pending, 'category': category,
                                          'error': str(exc), 'usage': turn_usage(self.directory, iteration)})
            validate_changes(self.worktree, changed_paths(self.worktree))
            self.state['partial_turn'] = {'provider': provider, 'thread': thread, 'category': category,
                                           'error': str(exc), 'paths': changed_paths(self.worktree),
                                           'turn': iteration, 'evaluated': False}
            self.state.pop('pending_turn')
            self.save()
            return False
        self.providers.success(provider)
        return self.finish_turn(pending, thread, response)

    def finish_turn(self, pending, thread, response):
        validate_response(response)
        self.check_head()
        paths = changed_paths(self.worktree)
        validate_changes(self.worktree, paths)
        self.state['threads'][pending['provider']] = thread
        self.state['session_id'] = thread
        actual_models = []
        event_path = self.directory / f'turn-{pending["iteration"]:02d}.jsonl'
        if event_path.exists():
            for line in event_path.read_text(errors='replace').splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('type') == 'system' and event.get('subtype') == 'init' and event.get('model'):
                    actual_models.append(event['model'])
        self.state['actual_model'] = actual_models[-1] if actual_models else None
        self.state['history'].append({'kind': 'model_turn', **pending, 'thread': thread,
                                      'response': response, 'observed_models': actual_models,
                                      'usage': turn_usage(self.directory, pending['iteration'])})
        ready = response['ready_for_evaluation'] and any(p.startswith('differometor/') for p in paths)
        syntax_error = None
        if ready:
            try:
                for name in paths:
                    path = self.worktree / name
                    if name.endswith('.py') and path.is_file():
                        ast.parse(path.read_text(), filename=name)
            except (SyntaxError, UnicodeError) as exc:
                syntax_error = str(exc)
                ready = False
        self.state['no_candidate'] = 0 if ready else self.state['no_candidate'] + 1
        self.state['last_handoff'] = response
        if ready:
            self.state['pending_commit'] = {'kind': 'model', 'before_sha': pending['before_sha'],
                                            'subject': f'lab: {self.args.name} turn {pending["iteration"]}',
                                            'evaluate': bool(ready), 'response': response}
            self.state.pop('partial_turn', None)
        elif paths or syntax_error:
            self.state['partial_turn'] = {'provider': pending['provider'], 'thread': thread,
                                           'paths': paths, 'turn': pending['iteration'],
                                           'syntax_error': syntax_error, 'evaluated': False}
        self.state.pop('pending_turn')
        self.save()
        return True

    def run(self):
        with contextlib.ExitStack() as stack:
            keys = [self.directory / 'supervisor.lock', self.campaign / f'lane-{self.args.lane}.lock',
                    self.worktree.parent / ('.writer-' + digest(str(self.worktree)) + '.lock')]
            self.lock_fds = tuple(stack.enter_context(exclusive_lock(path)) for path in keys)
            self.initialize()
            while True:
                now = self.clock()
                if (self.campaign / 'STOP').exists() or (self.directory / 'STOP').exists():
                    self.state['status'] = 'stopped'
                    break
                try:
                    if self.state.get('pending_commit'):
                        pending = self.state['pending_commit']
                        if pending['kind'] == 'feedback' and git(self.worktree, 'rev-parse', 'HEAD') == pending['before_sha']:
                            write_json(self.worktree / pending['artifact_path'], pending['artifact'])
                        self.commit_pending()
                        continue
                    if self.state.get('active_evaluation'):
                        if now > self.args.deadline_unix + self.args.drain_seconds:
                            self.state['status'] = 'deadline_pending_evaluation'
                            break
                        if not self.evaluate_pending():
                            time.sleep(min(15, max(1, self.args.deadline_unix + self.args.drain_seconds-now)))
                        continue
                    if now >= self.args.deadline_unix:
                        self.state['status'] = 'budget_exhausted'
                        break
                    worked = self.model_step()
                    if not worked or (self.state['no_candidate'] >= 3 and not self.state.get('pending_commit')):
                        time.sleep(min(60, max(0, self.args.deadline_unix-self.clock())))
                except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                    self.state['status'] = 'retrying_infrastructure'
                    self.state['last_error'] = str(exc)
                    self.save()
                    if now > self.args.deadline_unix + self.args.drain_seconds:
                        break
                    time.sleep(min(60, max(1, self.args.deadline_unix+self.args.drain_seconds-self.clock())))
                except ValueError as exc:
                    self.state['status'] = 'blocked_integrity'
                    self.state['last_error'] = str(exc)
                    self.save()
                    raise
            self.save()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('campaign-dir', 'name', 'worktree', 'branch', 'brief', 'evaluator-command', 'codex-bin-dir'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--lane', type=int, choices=(0, 1), required=True)
    p.add_argument('--deadline-unix', type=float, required=True)
    p.add_argument('--max-turn-seconds', type=float, default=1800)
    p.add_argument('--hook-timeout', type=float, default=180)
    p.add_argument('--drain-seconds', type=float, default=900)
    p.add_argument('--status-export')
    p.add_argument('--resume', action='store_true')
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.name):
        p.error('name must be an identifier')
    for key in ('deadline_unix', 'max_turn_seconds', 'hook_timeout', 'drain_seconds'):
        value = getattr(args, key)
        if not math.isfinite(value) or value <= 0:
            p.error(key + ' must be finite and positive')
    wrapper = Path(args.codex_bin_dir) / 'codex'
    if not wrapper.is_file() or not os.access(wrapper, os.X_OK):
        p.error('Pinned Codex wrapper is required')
    os.environ['PATH'] = str(Path(args.codex_bin_dir).resolve()) + os.pathsep + os.environ.get('PATH', '')
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    Supervisor(args).run()


if __name__ == '__main__':
    main()
