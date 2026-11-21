"""Restricted, resumable Claude CLI turns for the existing evaluation supervisor."""
import json
import subprocess
from pathlib import Path

from .agent_loop import (SCHEMA, CodexTurnError, read_thread_id, terminate_group,
                         validate_response, write_json)


def command_for(thread_id=None, model=None):
    # No Bash, background agents, MCP servers or project hooks. Restricted file
    # tools stay within the worktree. The supervisor alone owns Git/SSH/evaluation.
    command = [
        'claude', '-p', '--output-format', 'stream-json', '--verbose',
        '--json-schema', json.dumps(SCHEMA), '--safe-mode', '--restricted',
        '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
        '--permission-mode', 'dontAsk', '--permission-prompts', 'none',
        '--tools', 'Read,Glob,Grep,Edit,Write',
        '--allowedTools', 'Read,Glob,Grep,Edit(./differometor/**),Write(./differometor/**),'
                          'Edit(./experiments/notes/**),Write(./experiments/notes/**)',
    ]
    if model:
        command += ['--model', model]
    if thread_id:
        command += ['--resume', thread_id]
    return command


def parse_result(events):
    result = None
    for line in Path(events).read_text(errors='replace').splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get('type') == 'result':
            result = event
    if result is None:
        raise ValueError('Claude did not return a final result')
    if result.get('is_error') or result.get('subtype') != 'success':
        raise ValueError('Claude turn failed: ' + str(result.get('subtype')))
    response = validate_response(result.get('structured_output'))
    return result.get('session_id'), response


def claude_turn(worktree, session_dir, iteration, prompt, thread_id, timeout, lock_fds=(), model=None):
    directory = Path(session_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f'turn-{iteration:02d}.json'
    events = directory / f'turn-{iteration:02d}.jsonl'
    errors = directory / f'turn-{iteration:02d}.stderr.log'
    rules = (Path(worktree) / 'AGENTS.md').read_text()
    prompt = ('Repository rules (the current supervisor instructions override obsolete budgets):\n'
              + rules + '\n\n' + prompt)
    failure = None
    with events.open('w') as stdout, errors.open('w') as stderr:
        process = subprocess.Popen(command_for(thread_id, model), cwd=worktree,
                                   stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
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
        raise CodexTurnError('Claude turn exceeded its time budget' if timed_out else str(failure),
                             thread_id, timed_out, isinstance(failure, (KeyboardInterrupt, SystemExit))) from failure
    if process.returncode:
        raise CodexTurnError(f'Claude exited {process.returncode}; inspect {errors}', thread_id)
    try:
        returned_id, response = parse_result(events)
        if not returned_id or (thread_id and returned_id != thread_id):
            raise ValueError('Claude session identity is missing or inconsistent')
        write_json(output, response)
    except (OSError, ValueError) as exc:
        raise CodexTurnError(f'Invalid Claude response: {exc}', thread_id) from exc
    return returned_id, response
