"""Publish exact commits and submit reproducible evaluations through an SSH relay."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
import uuid

BASELINE_SHA = '02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f'
TERMINAL = {'completed', 'failed', 'timed_out', 'interrupted', 'rejected'}


def sync_ledger(client, directory):
    """Read completed queue jobs into a local ledger, without submitting any work."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    jobs = client.request({'action': 'list', 'limit': 10000})
    saved = 0
    for item in jobs:
        if item['status'] not in TERMINAL:
            continue
        if not re.fullmatch(r'[0-9a-f]{32}', item['id']):
            raise ValueError('Invalid queue job ID')
        path = directory / (item['id'] + '.json')
        if path.exists():
            cached = json.loads(path.read_text())
            if cached.get('updated_at') == item.get('updated_at') and cached.get('status') == item['status']:
                continue
        job = client.request({'action': 'show', 'id': item['id']})
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(job, indent=2, allow_nan=False) + '\n')
        temporary.replace(path)
        saved += 1
    return {'saved': saved, 'listed': len(jobs), 'truncated': len(jobs) == 10000}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def publish_candidate(repo, sha, branch):
    """Publish branch history without rewinding it when evaluating an older commit."""
    try:
        tip = git(repo, 'rev-parse', '--verify', f'refs/heads/{branch}^{{commit}}')
    except subprocess.CalledProcessError:
        tip = sha
    if subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', sha, tip]).returncode:
        raise ValueError('Candidate is not an ancestor of the assigned branch')
    subprocess.run(['git', '-C', str(repo), '-c', 'credential.helper=!gh auth git-credential',
                    'push', 'origin', f'{tip}:refs/heads/{branch}'], check=True)


class Client:
    def __init__(self, host='amd-hackathon', root='/workspace/feyer-lab'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', host):
            raise ValueError('Use an SSH configuration alias as host')
        if not root.startswith('/') or '..' in Path(root).parts:
            raise ValueError('Remote root must be an absolute path without parent traversal')
        self.host, self.root = host, root.rstrip('/')
        self.ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20',
                    '-o', 'ControlMaster=auto', '-o', 'ControlPersist=120',
                    '-o', f'ControlPath={Path.home()}/.ssh/feyer-%C', host]

    def request(self, data):
        command = ['env', f'PYTHONPATH={self.root}/control', '/workspace/venv-feyer/bin/python',
                   '-m', 'lab.remote', '--root', self.root, 'request']
        try:
            reply = subprocess.check_output(self.ssh + [shlex.join(command)], input=json.dumps(data),
                                            text=True, timeout=120, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr or ''
            if isinstance(detail, bytes):
                detail = detail.decode(errors='replace')
            if data.get('action') == 'lookup_request' and 'Unknown action: lookup_request' in detail:
                raise RuntimeError('AMD evaluator does not support idempotent request lookup. Deploy the updated '
                                   'lab/queue.py and lab/remote.py before using request IDs; no submission or '
                                   'automatic fallback was attempted.') from exc
            raise
        return json.loads(reply)

    def submit(self, repo, branch, agent, direction, hypothesis, profile='screen', sha=None, publish=True, request_id=None):
        if request_id is not None:
            from .queue import normalize_request_id
            request_id = normalize_request_id(request_id)
        repo = Path(repo).resolve()
        sha = git(repo, 'rev-parse', '--verify', f'{sha or "HEAD"}^{{commit}}')
        git(repo, 'check-ref-format', '--branch', branch)
        if branch.startswith('-') or len(sha) != 40:
            raise ValueError('Invalid branch or SHA')
        if request_id is not None:
            # Capability check precedes publication/upload; old servers must not
            # silently ignore the new field and create non-idempotent jobs.
            existing = self.request({'action': 'lookup_request', 'request_id': request_id})
            if existing is not None:
                expected = dict(sha=sha, branch=branch, agent=agent, direction=direction,
                                hypothesis=hypothesis, profile=profile, request_id=request_id)
                if not isinstance(existing, dict) or any(existing.get(k) != v for k, v in expected.items()):
                    raise ValueError('request_id already identifies a different submission payload')
                return existing
        if publish:
            publish_candidate(repo, sha, branch)
        transfer = uuid.uuid4().hex
        ref = f'refs/lab/export/{transfer}'
        git(repo, 'update-ref', ref, sha)
        try:
            with tempfile.TemporaryDirectory(prefix='feyer-bundle-') as directory:
                bundle = Path(directory) / 'candidate.bundle'
                # Include no upstream data: the instance already has the baseline commit.
                subprocess.run(['git', '-C', str(repo), 'bundle', 'create', str(bundle), ref, f'^{BASELINE_SHA}'], check=True)
                payload = bundle.read_bytes()
                destination = f'{self.root}/incoming/{transfer}.bundle'
                command = f'mkdir -p {shlex.quote(self.root + "/incoming")} && cat > {shlex.quote(destination)}'
                subprocess.run(self.ssh + [command], input=payload, check=True, timeout=180)
                return self.request(dict(action='ingest', transfer=transfer,
                    bundle_sha256=hashlib.sha256(payload).hexdigest(), sha=sha, branch=branch,
                    agent=agent, direction=direction, hypothesis=hypothesis, profile=profile,
                    request_id=request_id))
        finally:
            git(repo, 'update-ref', '-d', ref)

    def wait(self, job_id, timeout=1800, poll=5):
        started = time.monotonic()
        while True:
            job = self.request({'action': 'show', 'id': job_id})
            if job['status'] in TERMINAL:
                return job
            if time.monotonic() - started > timeout:
                raise TimeoutError(f'Job {job_id} remains {job["status"]}; evaluation continues remotely')
            time.sleep(poll)

    def fetch(self, job_id, destination):
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        files = self.request({'action': 'artifact', 'id': job_id})
        for name, encoded in files.items():
            if Path(name).name != name:
                raise ValueError('Invalid artifact name')
            (destination / name).write_bytes(base64.b64decode(encoded, validate=True))
        return str(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='amd-hackathon')
    parser.add_argument('--root', default='/workspace/feyer-lab')
    sub = parser.add_subparsers(dest='command', required=True)
    submit = sub.add_parser('submit')
    submit.add_argument('--repo', type=Path, default=Path.cwd())
    for name in ('branch', 'agent', 'direction', 'hypothesis'):
        submit.add_argument('--' + name, required=True)
    submit.add_argument('--sha')
    submit.add_argument('--request-id', help='Optional UUID; reuse only to retry the identical submission')
    submit.add_argument('--profile', choices=('screen', 'full'), default='screen')
    for name in ('status', 'wait', 'fetch'):
        cmd = sub.add_parser(name)
        cmd.add_argument('id')
        if name == 'wait': cmd.add_argument('--timeout', type=float, default=1800)
        if name == 'fetch': cmd.add_argument('--output', type=Path)
    sub.add_parser('list')
    args = parser.parse_args()
    client = Client(args.host, args.root)
    if args.command == 'submit':
        result = client.submit(args.repo, args.branch, args.agent, args.direction, args.hypothesis, args.profile, args.sha,
                               request_id=args.request_id)
    elif args.command == 'status': result = client.request({'action':'show','id':args.id})
    elif args.command == 'wait': result = client.wait(args.id, timeout=args.timeout)
    elif args.command == 'fetch': result = client.fetch(args.id, args.output or Path('.lab/results') / args.id)
    else: result = client.request({'action':'list'})
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
