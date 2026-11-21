"""Trusted instance entrypoint. Requests are JSON over authenticated SSH stdin."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from .queue import Queue
from .worker import Worker


def handle(root, request):
    root = Path(root).resolve()
    queue = Queue(root / 'state', root / 'repo.git')
    action = request['action']
    if action == 'ingest':
        transfer = request['transfer']
        if not re.fullmatch('[0-9a-f]{32}', transfer):
            raise ValueError('Invalid transfer ID')
        bundle = root / 'incoming' / (transfer + '.bundle')
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != request['bundle_sha256']:
            raise ValueError('Bundle digest mismatch')
        ref = f'refs/lab/export/{transfer}'
        destination = f'refs/transfers/{transfer}'
        queue._git('fetch', '--no-tags', str(bundle), f'{ref}:{destination}')
        if queue._git('rev-parse', destination) != request['sha']:
            raise ValueError('Bundle commit does not match submitted SHA')
        job = queue.enqueue(**{k: request[k] for k in ('sha', 'branch', 'agent', 'direction', 'hypothesis', 'profile')})
        queue._git('update-ref', '-d', destination)
        bundle.unlink()
        return job
    if action == 'enqueue':
        return queue.enqueue(**{k: request[k] for k in ('sha', 'branch', 'agent', 'direction', 'hypothesis', 'profile')})
    if action == 'list':
        return queue.list_jobs(limit=request.get('limit', 50))
    if action in ('show', 'artifact'):
        job = queue.get(request['id'])
        run = root / 'runs' / job['id']
        if action == 'artifact':
            files = {}
            for name in ('job.json', 'result.json', 'report.json', 'comparison.json', 'stdout.log', 'time.txt', 'report.png'):
                path = run / name
                if path.is_file() and path.stat().st_size <= 4 * 1024 * 1024:
                    files[name] = base64.b64encode(path.read_bytes()).decode()
            return files
        for name in ('stdout.log', 'comparison.log'):
            path = run / name
            if path.is_file():
                with path.open('rb') as stream:
                    stream.seek(max(0, path.stat().st_size - 16000))
                    job[name] = stream.read().decode(errors='replace')
        for name in ('report.json', 'comparison.json'):
            path = run / name
            if path.is_file():
                try:
                    job[name] = json.loads(path.read_text())
                except json.JSONDecodeError:
                    pass
        return job
    raise ValueError(f'Unknown action: {action}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/workspace/feyer-lab'))
    parser.add_argument('command', choices=('request', 'worker'))
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--cpu', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args()
    if args.command == 'request':
        import sys
        print(json.dumps(handle(args.root, json.load(sys.stdin)), allow_nan=False))
    else:
        queue = Queue(args.root / 'state', args.root / 'repo.git')
        (args.root / 'state' / 'worker.pid').write_text(str(os.getpid()) + '\n')
        worker = Worker(queue, args.root / 'runs', args.root / 'control' / 'lab', cpu=args.cpu, timeout=args.timeout)
        if args.once:
            print(json.dumps(worker.run_once()))
        else:
            worker.run_forever()


if __name__ == '__main__':
    main()
