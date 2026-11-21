"""Forced-command SSH entrypoint: trusted queue RPC and bounded bundle upload only."""
import os
from pathlib import Path
import re
import shlex
import sys

ROOT = '/workspace/feyer-lab'
REQUEST = ['env', 'PYTHONPATH=' + ROOT + '/control', '/workspace/venv-feyer/bin/python',
           '-m', 'lab.remote', '--root', ROOT, 'request']
UPLOAD = re.compile(r'mkdir -p /workspace/feyer-lab/incoming && cat > /workspace/feyer-lab/incoming/([0-9a-f]{32})\.bundle')


def classify(command):
    if shlex.split(command) == REQUEST:
        return 'request', None
    match = UPLOAD.fullmatch(command)
    if match:
        return 'upload', match.group(1)
    raise ValueError('This key only permits the trusted Feyer evaluation protocol')


def main():
    kind, transfer = classify(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    if kind == 'request':
        os.chdir(ROOT + '/control')
        environment = os.environ.copy()
        environment['PYTHONPATH'] = ROOT + '/control'
        os.execve(REQUEST[2], REQUEST[2:], environment)
    incoming = Path(ROOT) / 'incoming'
    incoming.mkdir(exist_ok=True)
    target = incoming / (transfer + '.bundle')
    total = 0
    try:
        with target.open('xb') as output:
            os.chmod(target, 0o600)
            while True:
                block = sys.stdin.buffer.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > 128 * 1024 * 1024:
                    raise ValueError('Bundle exceeds relay limit')
                output.write(block)
    except FileExistsError:
        raise
    except BaseException:
        target.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    main()
