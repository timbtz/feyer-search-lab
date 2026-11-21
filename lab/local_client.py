"""Server-local transport to the deployed evaluator's existing queue protocol.

This client never imports an evaluator from the candidate checkout and never
starts a benchmark. It sends the same requests/bundles as the SSH client to a
separate process rooted in the trusted deployed control directory.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

from .client import BASELINE_SHA, Client, git, publish_candidate
from .queue import normalize_request_id


class LocalClient(Client):
    def __init__(self, root='/workspace/feyer-lab', python_path='/workspace/venv-feyer/bin/python'):
        root = Path(root)
        if not root.is_absolute() or '..' in root.parts:
            raise ValueError('Evaluator root must be an absolute path without parent traversal')
        if not Path(python_path).is_absolute():
            raise ValueError('Evaluator Python must be an absolute path')
        self.root = str(root.resolve())
        self.python_path = str(python_path)

    def request(self, data):
        control = (Path(self.root) / 'control').resolve(strict=True)
        if not (control / 'lab' / 'remote.py').is_file():
            raise FileNotFoundError('Trusted deployed lab.remote is missing')
        env = os.environ.copy()
        env.pop('PYTHONHOME', None)
        env.pop('PYTHONSTARTUP', None)
        env.update(PYTHONPATH=str(control), PYTHONNOUSERSITE='1')
        command = [self.python_path, '-s', '-m', 'lab.remote', '--root', self.root, 'request']
        try:
            reply = subprocess.check_output(command, input=json.dumps(data), text=True,
                                            cwd=control, env=env, timeout=120, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr or ''
            if isinstance(detail, bytes):
                detail = detail.decode(errors='replace')
            if data.get('action') == 'lookup_request' and 'Unknown action: lookup_request' in detail:
                raise RuntimeError('Deployed evaluator lacks idempotent request lookup; update the trusted '
                                   'queue/remote release before submitting. No fallback was attempted.') from exc
            raise
        return json.loads(reply)

    def submit(self, repo, branch, agent, direction, hypothesis, profile='screen', sha=None,
               publish=True, request_id=None):
        if request_id is not None:
            request_id = normalize_request_id(request_id)
        repo = Path(repo).resolve()
        sha = git(repo, 'rev-parse', '--verify', f'{sha or "HEAD"}^{{commit}}')
        git(repo, 'check-ref-format', '--branch', branch)
        if branch.startswith('-') or len(sha) != 40:
            raise ValueError('Invalid branch or SHA')
        payload = dict(sha=sha, branch=branch, agent=agent, direction=direction,
                       hypothesis=hypothesis, profile=profile, request_id=request_id)
        if request_id is not None:
            existing = self.request({'action': 'lookup_request', 'request_id': request_id})
            if existing is not None:
                if not isinstance(existing, dict) or any(existing.get(k) != v for k, v in payload.items()):
                    raise ValueError('request_id already identifies a different submission payload')
                return existing
        if publish:
            publish_candidate(repo, sha, branch)
        transfer = uuid.uuid4().hex
        ref = f'refs/lab/export/{transfer}'
        git(repo, 'update-ref', ref, sha)
        incoming = Path(self.root) / 'incoming'
        try:
            incoming.mkdir(parents=True, exist_ok=True)
            # Stage on the destination filesystem, then atomically expose the
            # complete bundle to the trusted ingress process.
            with tempfile.TemporaryDirectory(prefix='local-transfer-', dir=incoming) as directory:
                bundle = Path(directory) / 'candidate.bundle'
                subprocess.run(['git', '-C', str(repo), 'bundle', 'create', str(bundle), ref,
                                f'^{BASELINE_SHA}'], check=True, stdout=subprocess.DEVNULL)
                digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
                destination = incoming / (transfer + '.bundle')
                bundle.replace(destination)
                # A lost response deliberately leaves reconciliation to the same
                # durable request ID, just as in the network transport.
                return self.request(dict(action='ingest', transfer=transfer,
                                         bundle_sha256=digest, **payload))
        finally:
            git(repo, 'update-ref', '-d', ref, sha)

    # wait() and fetch() are inherited from Client and dispatch through request().
