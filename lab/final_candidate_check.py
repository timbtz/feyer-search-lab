"""One bounded, nonranking final-verification batch; no shared worker changes."""
from pathlib import Path
import hashlib
import json
import time
from .transfer_run import reserve, execute, checked_harness, VENDOR
from .worker import atomic_json


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--harness', required=True, type=Path)
    p.add_argument('--recheck-from', type=Path)
    args = p.parse_args()
    sha = '53f38d342c3228c052785e8c9d63b6ce9c832dd1'
    args.output.mkdir(parents=True, exist_ok=False)
    python = '/workspace/venv-feyer/bin/python'
    runtime = Path(__file__).resolve().parents[1]
    common = ['--tree', str(args.tree), '--sha', sha]
    tasks = []
    for setup in ('grid', 'aligo'):
        tasks.append((f'gradient-{setup}', [python, '-u', '-m', 'lab.gradient_sanity', *common,
                      '--setup', setup, '--output', str(args.output/f'gradient-{setup}.json'),
                      *(['--recheck', str(args.recheck_from/f'gradient-{setup}.json')] if args.recheck_from else [])]))
    tasks.append(('precision', [python, '-u', '-m', 'lab.solver_precision_probe', *common,
                  '--harness', str(args.harness), '--output', str(args.output/'precision-arrays')]))
    cases = 'dev,dev_perturbed,uifo_20_5000,uifo_rand1,uifo_rand2,uifo_rand3,voyager,aligo,dev_randparams,uifo_randparams1,uifo_randparams2,uifo_randparams3,uifo_amod1,uifo_fmod1'
    tasks.append(('generalization', [python, '-u', str(args.harness), 'run', '--tree', str(args.tree),
                  '--out', str(args.output/'generalization.npz'), '--cases', cases]))
    if args.recheck_from:
        tasks = [task for task in tasks if task[0].startswith('gradient-')]
    for repeat in (2, 3):
        for setup in ('grid', 'aligo'):
            entry = 'benchmark.py' if setup == 'grid' else 'benchmark_aligo.py'
            tasks.append((f'official-{setup}-{repeat}', [python, '-u', str(VENDOR/entry), '--repo',
                          str(args.tree), '--cpus', '1', '--repeats', '3', '--output',
                          str(args.output/f'official-{setup}-{repeat}.json')]))
    receipt = {'candidate_sha': sha, 'ranking_eligible': False, 'scope': 'Additional diagnostics and fresh-process official repetitions',
               'started_at': time.time(), 'deadline_unix': time.time()+900,
               'harness_sha256': hashlib.sha256(args.harness.read_bytes()).hexdigest(),
               'official_harness': checked_harness(), 'tasks': [], 'status': 'preparing'}
    atomic_json(args.output/'execution.json', receipt)
    try:
        with reserve(['/workspace/feyer-lab/state', '/workspace/feyer-lab-lane1/state']) as fds:
            deadline = time.monotonic()+900
            for name, command in tasks:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Final-check budget exhausted')
                folder = args.output/name
                folder.mkdir()
                command = ['taskset', '-c', '2', *command]
                # Official benchmark verifies its import comes from --repo.
                cwd = args.tree if name.startswith('official-') else runtime
                result = execute(command, cwd, folder, deadline-time.monotonic(), fds)
                receipt['tasks'].append({'name': name, 'command': command, **result})
                atomic_json(args.output/'execution.json', receipt)
                print(name, result, flush=True)
            receipt['status'] = 'completed' if all(t['returncode'] == 0 and t['failure'] is None for t in receipt['tasks']) else 'completed_with_execution_errors'
    except Exception as error:
        receipt.update(status='blocked', error=repr(error))
        raise
    finally:
        receipt['finished_at'] = time.time()
        atomic_json(args.output/'execution.json', receipt)


if __name__ == '__main__':
    main()
