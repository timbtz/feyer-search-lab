"""Read-only checks for a separate AMD evaluator; never installs or runs physics."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .worker import BASELINE_SHA


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                   stderr=subprocess.PIPE, timeout=30).strip()


def check(repo, cpu=2, workspace=Path('/workspace')):
    """Check the existing fixed-path worker contract without changing the host."""
    repo, workspace = Path(repo).resolve(), Path(workspace)
    checks = []
    def record(name, passed, detail):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    record('linux', platform.system() == 'Linux', platform.system())
    record('python_3_12', sys.version_info[:2] == (3, 12), platform.python_version())
    expected_python = workspace / 'venv-feyer/bin/python'
    # sys.prefix distinguishes virtual environments sharing the same base binary.
    record('isolated_venv', Path(sys.prefix).resolve() == (workspace / 'venv-feyer').resolve()
           and sys.prefix != sys.base_prefix, str(sys.prefix))
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else []
    record('evaluation_cpu', type(cpu) is int and cpu >= 0 and cpu in affinity,
           {'requested': cpu, 'available': affinity})
    for name in ('git', 'tmux', 'taskset'):
        record('command_' + name, shutil.which(name) is not None, shutil.which(name))
    record('gnu_time_path', Path('/usr/bin/time').is_file(), '/usr/bin/time')
    try:
        # Read pins from the immutable official commit, not a mutable working file.
        pins = git(repo, 'show', BASELINE_SHA + ':requirements.txt')
        for line in pins.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, version = line.split('==')
            try:
                actual = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                actual = None
            record('package_' + name, actual == version, {'expected': version, 'installed': actual})
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        record('official_dependency_pins', False, type(exc).__name__)
    pristine = workspace / 'feyer-pristine'
    try:
        head = git(pristine, 'rev-parse', 'HEAD')
        tracked = git(pristine, 'status', '--porcelain', '--untracked-files=no')
        record('pristine_source', head == BASELINE_SHA and not tracked,
               {'commit': head, 'expected': BASELINE_SHA, 'tracked_changes': bool(tracked)})
    except (subprocess.SubprocessError, OSError) as exc:
        record('pristine_source', False, type(exc).__name__)
    reference = pristine / 'base1.npz'
    # Presence/digest are readiness evidence only, not numerical validation.
    if reference.is_file() and reference.stat().st_size > 0:
        digest = hashlib.sha256()
        with reference.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        record('reference_archive', True, {'path': str(reference), 'sha256': digest.hexdigest()})
    else:
        record('reference_archive', False, str(reference))
    record('reference_report', (pristine / 'base1.json').is_file(), str(pristine / 'base1.json'))
    try:
        release = git(repo, 'rev-parse', 'HEAD')
        clean = not git(repo, 'status', '--porcelain', '--untracked-files=no')
        record('controller_checkout', clean, {'commit': release, 'tracked_clean': clean})
    except (subprocess.SubprocessError, OSError) as exc:
        record('controller_checkout', False, type(exc).__name__)
    return {'schema': 'amd-preflight-v1', 'ready_for_calibration_review': all(c['passed'] for c in checks),
            'cpu': cpu, 'python': str(expected_python), 'checks': checks,
            'limits': 'Readiness only. No physics, calibration, deployment or timing comparison performed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--cpu', type=int, default=2)
    args = parser.parse_args()
    result = check(args.repo, args.cpu)
    print(json.dumps(result, indent=2))
    return 0 if result['ready_for_calibration_review'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
