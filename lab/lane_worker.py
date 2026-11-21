"""Start an additional serial evaluator with explicit, coordinator-owned limits.

The original worker remains untouched. Sampled RSS guards are not kernel caps.
Each lane has its own queue/root/lock; a shared host reserve protects admission.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

from .queue import Queue
from .worker import Worker, atomic_json


def validate_config(value):
    required = {'schema', 'root', 'primary_root', 'cpu', 'primary_cpu',
                'memory_budget_bytes', 'primary_memory_budget_bytes', 'host_reserve_bytes'}
    if not isinstance(value, dict) or not required <= value.keys() or value['schema'] != 'feyer-lane-v1':
        raise ValueError('Complete feyer-lane-v1 configuration required')
    c = dict(value)
    for key in ('cpu', 'primary_cpu', 'memory_budget_bytes', 'primary_memory_budget_bytes', 'host_reserve_bytes'):
        if type(c[key]) is not int or c[key] < (0 if key.endswith('cpu') else 1):
            raise ValueError('Invalid integer policy: ' + key)
    if c['host_reserve_bytes'] < 8_000_000_000:
        raise ValueError('At least 8 GB host reserve required for this two-lane policy')
    root, primary = Path(c['root']), Path(c['primary_root'])
    if not root.is_absolute() or not primary.is_absolute():
        raise ValueError('Queue roots must be absolute')
    root, primary = root.resolve(), primary.resolve()
    if root == primary or root in primary.parents or primary in root.parents:
        raise ValueError('Lane needs a separate non-overlapping queue root')
    if c['cpu'] == c['primary_cpu']:
        raise ValueError('Lane CPUs must differ')
    c.update(root=str(root), primary_root=str(primary))
    return c


def cpu_set(text):
    result = set()
    for group in text.strip().split(','):
        bounds = group.split('-')
        if len(bounds) == 1:
            result.add(int(bounds[0]))
        elif len(bounds) == 2 and int(bounds[0]) <= int(bounds[1]):
            result.update(range(int(bounds[0]), int(bounds[1]) + 1))
        else:
            raise ValueError('Malformed CPU list')
    return result


def inspect_limits(config, cgroup=Path('/sys/fs/cgroup'), topology=Path('/sys/devices/system/cpu')):
    c = validate_config(config)
    cgroup, topology = Path(cgroup), Path(topology)
    limit = int((cgroup / 'memory.max').read_text().strip())
    current = int((cgroup / 'memory.current').read_text().strip())
    siblings = cpu_set((topology / f"cpu{c['cpu']}" / 'topology/thread_siblings_list').read_text())
    if c['primary_cpu'] in siblings:
        raise ValueError('New lane shares a physical core with the original lane')
    allowed = os.sched_getaffinity(0) if hasattr(os, 'sched_getaffinity') else {c['cpu']}
    if c['cpu'] not in allowed:
        raise ValueError('New lane CPU is outside process affinity')
    aggregate = c['memory_budget_bytes'] + c['primary_memory_budget_bytes']
    if aggregate + c['host_reserve_bytes'] > limit:
        raise ValueError('Aggregate sampled budgets plus host reserve exceed cgroup memory')
    return {'at': time.time(), 'memory_limit_bytes': limit, 'memory_current_bytes': current,
            'cpu': c['cpu'], 'thread_siblings': sorted(siblings),
            'aggregate_sampled_budget_bytes': aggregate, 'host_reserve_bytes': c['host_reserve_bytes'],
            'can_admit': current + c['memory_budget_bytes'] + c['host_reserve_bytes'] <= limit,
            'kernel_per_job_cap': False}


@contextlib.contextmanager
def secondary_slot(config):
    """Allow only one extra lane; an unclean death requires manual reconciliation."""
    primary = Path(config['primary_root']) / 'state'
    primary.mkdir(parents=True, exist_ok=True)
    receipt = primary / 'additional-lane-state.json'
    with (primary / 'additional-lane.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('An additional evaluator lane already owns the host slot') from exc
        if receipt.exists() and json.loads(receipt.read_text()).get('status') == 'running':
            raise ValueError('Previous extra lane stopped uncleanly; reconcile child jobs before restart')
        record = {'status': 'running', 'pid': os.getpid(), 'root': config['root'], 'at': time.time()}
        atomic_json(receipt, record)
        try:
            yield
        finally:
            # Worker.run_forever has already stopped/cleaned its current child.
            atomic_json(receipt, dict(record, status='stopped', stopped_at=time.time()))


class LaneWorker(Worker):
    def __init__(self, config):
        self.lane_config = validate_config(config)
        c = self.lane_config
        self.lane_root = Path(c['root'])
        inspect_limits(c)
        queue = Queue(self.lane_root / 'state', self.lane_root / 'repo.git')
        super().__init__(queue, self.lane_root / 'runs', self.lane_root / 'control/lab',
                         cpu=c['cpu'], memory_budget_bytes=c['memory_budget_bytes'])

    def run_once(self):
        if (self.lane_root / 'state/STOP').exists():
            raise KeyboardInterrupt('Coordinator requested drain and stop')
        limits = inspect_limits(self.lane_config)
        atomic_json(self.lane_root / 'state/lane-health.json',
                    {'status': 'ready' if limits['can_admit'] else 'waiting_for_headroom',
                     'pid': os.getpid(), 'limits': limits})
        if not limits['can_admit']:
            return None  # Do not claim a job while admission is blocked.
        return super().run_once()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = validate_config(json.loads(args.config.read_text()))
    root = Path(config['root'])
    if (root / 'state/STOP').exists():
        raise ValueError('STOP marker present; explicit coordinator action required before restart')
    with secondary_slot(config):
        run_lane(config, root)


def run_lane(config, root):
    worker = LaneWorker(config)
    record = {'schema': 'feyer-lane-startup-v1', 'started_at': time.time(), 'pid': os.getpid(),
              'config': config, 'limits': inspect_limits(config),
              'worker_sha256': hashlib.sha256((root / 'control/lab/worker.py').read_bytes()).hexdigest(),
              'launcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'evaluator_release': str((root / 'control').resolve()),
              'stop_policy': 'Create state/STOP to finish current job and stop before next claim'}
    atomic_json(root / 'state/lane-startup.json', record)
    (root / 'state/worker.pid').write_text(str(os.getpid()) + '\n')
    try:
        worker.run_forever()
    finally:
        atomic_json(root / 'state/lane-stopped.json', {'at': time.time(), 'pid': os.getpid()})


if __name__ == '__main__':
    main()
