"""Read-only host/lane observation for a concurrent timing epoch."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def sample(epoch):
    memory = Path('/sys/fs/cgroup')
    usage = dict(line.split() for line in (memory / 'cpu.stat').read_text().splitlines())
    rows = []
    for line in subprocess.check_output(['ps', '-eo', 'pid=,ppid=,rss='], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3:
            rows.append(tuple(map(int, fields)))
    lanes = []
    for lane in epoch['lanes']:
        root = Path(lane['root'])
        entry = {'root': str(root), 'cpu': lane['cpu'], 'memory_budget_bytes': lane['memory_budget_bytes']}
        try:
            pid = int((root / 'state/worker.pid').read_text())
            owned = {pid}
            while True:
                expanded = owned | {p for p, parent, _ in rows if parent in owned}
                if expanded == owned:
                    break
                owned = expanded
            entry.update(worker_pid=pid, process_count=len(owned),
                         rss_sum_bytes=sum(rss * 1024 for p, _, rss in rows if p in owned))
            with sqlite3.connect('file:' + str(root / 'state/queue.sqlite3') + '?mode=ro', uri=True) as db:
                db.row_factory = sqlite3.Row
                entry['active_jobs'] = [dict(r) for r in db.execute(
                    "select id,sha,status,started_at,agent,profile from jobs where status in ('queued','running')")]
        except (OSError, ValueError, sqlite3.Error) as exc:
            entry['observation_error'] = str(exc)
        lanes.append(entry)
    return {'epoch_id': epoch['epoch_id'], 'at': time.time(),
            'memory_current_bytes': int((memory / 'memory.current').read_text()),
            'memory_limit_bytes': int((memory / 'memory.max').read_text()),
            'cpu_usage_usec': int(usage['usage_usec']), 'lanes': lanes,
            'notes': 'RSS sums can double-count shared pages. Concurrent timings are exploratory.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epoch', required=True, type=Path)
    parser.add_argument('--max-seconds', type=float, default=7200)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    epoch = json.loads(args.epoch.read_text())
    if args.once:
        print(json.dumps(sample(epoch)))
        return
    root = args.epoch.parent
    write_json(root / 'monitor.json', {'pid': os.getpid(), 'started_at': time.time(), 'status': 'running'})
    end = time.monotonic() + args.max_seconds
    previous = None
    with (root / 'samples.jsonl').open('a') as output:
        while time.monotonic() < end and not (root / 'STOP_MONITOR').exists():
            current = sample(epoch)
            if previous is not None:
                elapsed = current['at'] - previous['at']
                current['measured_cpu_cores'] = (current['cpu_usage_usec'] - previous['cpu_usage_usec']) / (elapsed * 1e6) if elapsed > 0 else None
            output.write(json.dumps(current, allow_nan=False) + '\n'); output.flush()
            write_json(root / 'latest.json', current)
            previous = current
            if all((Path(lane['root']) / 'state/lane-stopped.json').exists() for lane in epoch['lanes'][1:]):
                break
            time.sleep(2)
    write_json(root / 'monitor.json', {'pid': os.getpid(), 'stopped_at': time.time(), 'status': 'complete'})


if __name__ == '__main__':
    main()
