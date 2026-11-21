"""Bounded, serial official transfer checks in a reserved existing evaluator slot.

Never modifies a deployed worker or its queue. Both existing lane locks must be
available and their queues drained. These support results are nonranking.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

from .resources import MemoryMonitor
from .transfer_validation import UPSTREAM, WORKLOADS, audit_arrays, file_digest, validate_official_report
from .worker import Worker, atomic_json, resource_snapshot

BASELINE = '02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f'
VENDOR = Path(__file__).resolve().parents[1] / 'experiments/vendor/official-transfer'
PROTECTED = ('benchmark.py', 'plot_timings.py', 'examples/data', 'requirements.txt', 'pyproject.toml', 'setup.py')


def git(mirror, *args):
    return subprocess.check_output(['git', '-C', str(mirror), *args], text=True).strip()


def checked_harness(root=VENDOR):
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['upstream_commit'] != UPSTREAM:
        raise ValueError('Wrong upstream benchmark release')
    for name, sha in manifest['files'].items():
        if file_digest(root / name) != sha:
            raise ValueError('Modified official harness: ' + name)
    return manifest


@contextlib.contextmanager
def reserve(states):
    """Cooperate with existing worker locks; never cancel another job."""
    with contextlib.ExitStack() as stack:
        descriptors = []
        for state in sorted(set(Path(s).resolve() for s in states)):
            if not (state / 'queue.sqlite3').is_file():
                raise ValueError('Existing queue state required: ' + str(state))
            h = stack.enter_context((state / 'worker.lock').open('a+'))
            fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
            descriptors.append(h.fileno())
            with contextlib.closing(sqlite3.connect((state / 'queue.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
                pending = db.execute("SELECT count(*) FROM jobs WHERE status NOT IN ('completed','failed','timed_out','interrupted','rejected')").fetchone()[0]
            if pending:
                raise RuntimeError('Queue not drained; support check must wait')
        yield tuple(descriptors)


def execute(command, code, output, timeout, lock_fds):
    monitor = MemoryMonitor(16_000_000_000)
    started = time.monotonic()
    with (output / 'stdout.log').open('w') as log:
        process = subprocess.Popen(command, cwd=code, env=Worker._environment(code),
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, pass_fds=lock_fds)
        reason = None
        try:
            while process.poll() is None:
                if monitor.sample(process.pid):
                    reason = 'sampled_memory_budget_exceeded'
                    break
                if time.monotonic() - started > timeout:
                    reason = 'timeout'
                    break
                time.sleep(.25)
        finally:
            Worker._terminate_group(process)
    return {'returncode': process.returncode, 'failure': reason, 'wall_seconds': time.monotonic() - started,
            'memory': monitor.report()}


def run(args):
    import numpy as np
    if not math.isfinite(args.timeout) or args.timeout <= 0 or args.timeout > 1200:
        raise ValueError('Total support budget must be finite, positive and at most 1200 seconds')
    if args.cpu != 2 or len(set(args.lock_state)) != 2:
        raise ValueError('This reviewed support policy requires CPU2 and both existing evaluator lane states')
    if not hasattr(os, 'sched_getaffinity') or args.cpu not in os.sched_getaffinity(0):
        raise ValueError('Linux CPU affinity required')
    for sha in (BASELINE, args.candidate):
        if not re.fullmatch('[0-9a-f]{40}', sha) or git(args.mirror, 'rev-parse', sha + '^{commit}') != sha:
            raise ValueError('Exact available commit SHA required')
    if git(args.mirror, 'diff', '--name-only', BASELINE, args.candidate, '--', *PROTECTED):
        raise ValueError('Candidate changed protected source/data/dependencies')
    manifest = checked_harness()
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {'schema': 'feyer-official-transfer-run-v1', 'upstream': UPSTREAM, 'harness': manifest,
               'reference_sha': BASELINE, 'candidate_sha': args.candidate, 'cpu': args.cpu,
               'started_at': time.time(), 'status': 'preparing', 'ranking_eligible': False,
               'timing_scope': 'Matched one-CPU fresh processes; support evidence, not queue promotion. External contention not excluded.',
               'resource_snapshot': resource_snapshot(), 'checks': [], 'comparisons': []}
    atomic_json(args.output / 'receipt.json', receipt)
    try:
        with reserve(args.lock_state) as fds:
            # 16GB sampled budget plus headroom; do not assume host free(1) equals cgroup availability.
            cgroup = Path('/sys/fs/cgroup')
            limit = (cgroup / 'memory.max').read_text().strip()
            current = int((cgroup / 'memory.current').read_text())
            if limit != 'max' and int(limit) - current < 24_000_000_000:
                raise RuntimeError('Insufficient cgroup headroom for a 16GB support check plus 8GB reserve')
            receipt['status'] = 'running'
            atomic_json(args.output / 'receipt.json', receipt)
            deadline = time.monotonic() + args.timeout
            codes = {}
            for name, sha in [('reference', BASELINE), ('candidate', args.candidate)]:
                code = args.output / (name + '-code')
                subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(args.mirror), str(code)], check=True, capture_output=True)
                subprocess.run(['git', '-C', str(code), 'checkout', '--detach', sha], check=True, capture_output=True)
                codes[name] = code
            for setup in ('grid', 'aligo'):
                for name, sha in [('reference', BASELINE), ('candidate', args.candidate)]:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Total support budget exhausted; no further tests started')
                    out = args.output / f'{name}-{setup}'
                    out.mkdir()
                    entry = 'benchmark_aligo.py' if setup == 'aligo' else 'benchmark.py'
                    command = [args.python, '-u', str(VENDOR / entry), '--repo', str(codes[name]), '--cpus', '1',
                               '--repeats', '3', '--output', str(out / 'report.json'), '--save-arrays', str(out / 'arrays.npz')]
                    command = ['taskset', '-c', str(args.cpu)] + command
                    execution = execute(command, codes[name], out, remaining, fds)
                    check = {'name': name, 'setup': setup, 'sha': sha, 'command': command, **execution,
                             'official': {'passed': False, 'issues': ['No successful full report']}}
                    if execution['returncode'] == 0 and execution['failure'] is None:
                        report = json.loads((out / 'report.json').read_text())
                        check['official'] = validate_official_report(report, setup=setup, cpu=args.cpu,
                                                                     candidate_sha=sha, harness_hashes=manifest['files'])
                        check['total_seconds'] = report['timing_seconds']['end_to_end']
                        check['report_sha256'] = file_digest(out / 'report.json')
                        check['arrays_sha256'] = file_digest(out / 'arrays.npz')
                    receipt['checks'].append(check)
                    atomic_json(args.output / 'receipt.json', receipt)
                paths = [args.output / f'{name}-{setup}/arrays.npz' for name in ('reference', 'candidate')]
                if all(p.is_file() for p in paths):
                    with np.load(paths[0], allow_pickle=False) as a, np.load(paths[1], allow_pickle=False) as b:
                        comparison = audit_arrays(a, b, sensitivity_tolerance=WORKLOADS[setup]['tolerance'], include_loss=False)
                    comparison['setup'] = setup
                    receipt['comparisons'].append(comparison)
            receipt['passed'] = (len(receipt['checks']) == 4 and len(receipt['comparisons']) == 2
                                 and all(c['official']['passed'] for c in receipt['checks'])
                                 and all(c['passed'] for c in receipt['comparisons']))
            receipt['status'] = 'passed' if receipt['passed'] else 'needs_review'
    except (Exception, KeyboardInterrupt) as error:
        receipt.update(status='blocked_or_interrupted', passed=False, error=f'{type(error).__name__}: {error}')
    finally:
        receipt['finished_at'] = time.time()
        atomic_json(args.output / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'output': str(args.output)}))
    return 0 if receipt.get('passed') else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mirror', required=True, type=Path)
    p.add_argument('--candidate', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--lock-state', action='append', required=True)
    p.add_argument('--cpu', type=int, default=2)
    p.add_argument('--python', default='/workspace/venv-feyer/bin/python')
    p.add_argument('--timeout', type=float, default=900)
    args = p.parse_args()
    args.output = args.output.resolve()
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
