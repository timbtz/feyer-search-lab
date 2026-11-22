"""Durable, serial two-benchmark support runner. Never changes existing workers.

CLI (trusted operator configuration is identical for register and run):
  python -m lab.dual_benchmark_worker --root ROOT register < request.json
  python -m lab.dual_benchmark_worker --root ROOT run --request-id UUID
  python -m lab.dual_benchmark_worker --root ROOT status --request-id UUID

Request: {request_id, sha, deadline_unix, timeout_seconds?:900,
          fresh_process_repetitions?:1|3|5, run_generalization?:false,
          branch?:str, session?:str, lane?:str}.
Repeated registration/run never re-executes a started request. After a controller
crash, a started request becomes interrupted once its inherited execution lock
is released. A new request ID is needed for an intentional new measurement.

Official PASS, strict array comparisons, generalization and timing confirmation
remain separate. No result is automatically promoted to a shared winner.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import re
import signal
import statistics
import subprocess
import time
import uuid

from .transfer_run import BASELINE, PROTECTED, VENDOR, checked_harness, execute, git, reserve
from .transfer_validation import WORKLOADS, audit_arrays, audit_archive, file_digest, validate_official_report
from .worker import resource_snapshot

SCHEMA = 'feyer-dual-benchmark-request-v1'
RESULT_SCHEMA = 'feyer-dual-benchmark-result-v1'
TERMINAL = {'completed', 'failed', 'interrupted', 'expired'}
CASES = ('dev', 'dev_perturbed', 'uifo_20_5000', 'uifo_rand1', 'uifo_rand2',
         'uifo_rand3', 'voyager', 'aligo', 'dev_randparams', 'uifo_randparams1',
         'uifo_randparams2', 'uifo_randparams3', 'uifo_amod1', 'uifo_fmod1')
PYTHON = '/workspace/venv-feyer/bin/python'
LOCK_STATES = ('/workspace/feyer-lab/state', '/workspace/feyer-lab-lane1/state')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def environment_cohort(environment):
    """Package compiler options are evaluated changes; hardware/dependencies stay fixed."""
    return {key: environment.get(key) for key in ('cpu_model', 'cpu_affinity_ids', 'platform',
        'python', 'packages', 'backend', 'jax_enable_x64', 'persistent_compilation_cache', 'thread_limits')}


def durable_json(path, value):
    """Atomic replace plus file/directory fsync; never expose a partial state."""
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def lock(path, *, nonblocking=False):
    with Path(path).open('a+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield stream.fileno()


def request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
        raise ValueError('request_id must be a lowercase UUID, not a path')
    return uuid.UUID(value).hex


def normalize_request(payload):
    if not isinstance(payload, dict): raise ValueError('Request must be an object')
    allowed = {'schema_version', 'request_id', 'sha', 'deadline_unix', 'timeout_seconds',
               'fresh_process_repetitions', 'run_generalization', 'branch', 'session', 'lane'}
    if set(payload)-allowed: raise ValueError('Unknown request fields: ' + str(sorted(set(payload)-allowed)))
    out = dict(payload)
    if out.get('schema_version', SCHEMA) != SCHEMA: raise ValueError('Unknown request schema')
    out['schema_version'] = SCHEMA
    out['request_id'] = request_id(out.get('request_id'))
    if not isinstance(out.get('sha'), str) or not re.fullmatch('[0-9a-f]{40}', out['sha']):
        raise ValueError('Exact full candidate SHA required')
    for name, default in [('deadline_unix', None), ('timeout_seconds', 900)]:
        value = out.get(name, default)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(name + ' must be finite and positive')
        out[name] = float(value)
    if out['timeout_seconds'] > 900: raise ValueError('Support job cannot exceed 900 seconds')
    reps = out.get('fresh_process_repetitions', 1)
    if type(reps) is not int or reps not in (1, 3, 5): raise ValueError('Fresh-process repetitions must be 1, 3 or 5')
    out['fresh_process_repetitions'] = reps
    generalization = out.get('run_generalization', False)
    if type(generalization) is not bool: raise ValueError('run_generalization must be boolean')
    out['run_generalization'] = generalization
    for name in ('branch', 'session', 'lane'):
        value = out.get(name, '')
        if not isinstance(value, str) or len(value) > 256 or any(ord(c) < 32 for c in value):
            raise ValueError('Invalid metadata ' + name)
        out[name] = value
    return out


class Runner:
    def __init__(self, root, *, mirror='/workspace/feyer-lab/repo.git', lock_states=LOCK_STATES,
                 reference_root=None, seed_reference_root=None, generalization_harness=None,
                 generalization_reference=None, generalization_seed=None):
        self.root = Path(root).resolve()
        self.mirror = Path(mirror).resolve()
        self.lock_states = tuple(Path(p).resolve() for p in lock_states)
        if len(set(self.lock_states)) != 2: raise ValueError('Both existing queue states are required')
        self.reference_roots = {key: Path(value).resolve() for key, value in
                                [('pristine', reference_root), ('initial_seed', seed_reference_root)] if value}
        self.generalization_harness = Path(generalization_harness).resolve() if generalization_harness else None
        self.generalization_refs = {key: Path(value).resolve() for key, value in
                                   [('pristine', generalization_reference), ('initial_seed', generalization_seed)] if value}
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root/'requests').mkdir(exist_ok=True)

    def _directory(self, identity):
        return self.root/'requests'/request_id(identity)

    def _policy(self):
        manifest = checked_harness()
        refs = {}
        for label, root in self.reference_roots.items():
            refs[label] = {'root': str(root), 'files': {}}
            for setup in ('grid', 'aligo'):
                # A reference directory has grid/{report.json,arrays.npz} and aligo/...
                report_path, arrays_path = root/setup/'report.json', root/setup/'arrays.npz'
                report = json.loads(report_path.read_text())
                sha = report.get('source', {}).get('commit')
                if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{40}', sha): raise ValueError('Reference needs exact source SHA')
                if label == 'pristine' and sha != BASELINE: raise ValueError('Pristine reference has wrong SHA')
                verdict = validate_official_report(report, setup=setup, cpu=2, candidate_sha=sha,
                                                   harness_hashes=manifest['files'])
                if not verdict['passed']: raise ValueError('Unvalidated reference report: '+label+'/'+setup)
                refs[label]['files'][setup] = {'report_sha256': file_digest(report_path), 'arrays_sha256': file_digest(arrays_path),
                    'sha': sha, 'environment_cohort': environment_cohort(report['environment'])}
            if len({v['sha'] for v in refs[label]['files'].values()}) != 1:
                raise ValueError('Reference setups must identify the same exact source')
        policy = {'cpu': 2, 'python': PYTHON, 'memory_budget_bytes': 16_000_000_000,
                  'memory_reserve_bytes': 8_000_000_000, 'mirror': str(self.mirror),
                  'lock_states': list(map(str, self.lock_states)), 'protected_baseline': BASELINE,
                  'harness': manifest, 'references': refs,
                  'package_compiler_policy': 'organizer-configurable-recorded-v1',
                  'runtime_files': {name: file_digest(Path(__file__).with_name(name)) for name in
                      ('dual_benchmark_worker.py', 'transfer_run.py', 'transfer_validation.py', 'worker.py', 'resources.py')}}
        if self.generalization_harness:
            policy['generalization'] = {'harness': str(self.generalization_harness),
                'harness_sha256': file_digest(self.generalization_harness), 'cases': list(CASES),
                'references': {k: {'path': str(v), 'sha256': file_digest(v)} for k,v in self.generalization_refs.items()}}
        return policy

    def register(self, payload):
        request = normalize_request(payload)
        directory = self._directory(request['request_id'])
        policy = self._policy()
        if request['run_generalization'] and (not self.generalization_harness or set(self.generalization_refs) != {'pristine', 'initial_seed'}):
            raise ValueError('Generalization requires a pinned harness and both pristine/initial-seed references')
        envelope = {'request': request, 'request_digest': digest(request), 'policy': policy, 'policy_digest': digest(policy)}
        with lock(self.root/'registry.lock'):
            directory.mkdir(exist_ok=True)
            path = directory/'request.json'
            if path.exists():
                old = json.loads(path.read_text())
                if old != envelope: raise ValueError('Request identity reused with different payload or execution policy')
            else:
                durable_json(path, envelope)
            state_path = directory/'state.json'
            if not state_path.exists():
                # Registration can recover a crash between request and initial-state writes.
                # It must never recover missing state over any execution artifacts.
                extra = set(p.name for p in directory.iterdir())-{'request.json'}
                if extra: raise ValueError('Missing state with existing artifacts; manual investigation required')
                durable_json(state_path, {'schema_version': RESULT_SCHEMA, 'request_id': request['request_id'],
                    'sha': request['sha'], 'request_digest': envelope['request_digest'], 'policy_digest': envelope['policy_digest'],
                    'status': 'queued', 'registered_at': time.time(), 'checks': [], 'official_passed': None,
                    'promotion_ready': False, 'ranking_eligible': False})
        return self.status(request['request_id'])

    def status(self, identity):
        directory = self._directory(identity)
        state = json.loads((directory/'state.json').read_text())
        if state['request_id'] != request_id(identity): raise ValueError('State identity mismatch')
        return state

    def _save(self, directory, state, **updates):
        state.update(updates, observed_at=time.time())
        durable_json(directory/'state.json', state)

    def _check_resources(self):
        if not hasattr(os, 'sched_getaffinity') or 2 not in os.sched_getaffinity(0):
            raise RuntimeError('Linux CPU2 affinity unavailable')
        if not Path(PYTHON).is_file() or not Path('/usr/bin/timeout').is_file():
            raise RuntimeError('Fixed Python or independent GNU timeout unavailable')
        cgroup = Path('/sys/fs/cgroup')
        limit, current = (cgroup/'memory.max').read_text().strip(), int((cgroup/'memory.current').read_text())
        if limit != 'max' and int(limit)-current < 24_000_000_000:
            raise RuntimeError('Insufficient cgroup headroom for 16GB sampled RSS plus 8GB reserve')
        available = re.search(r'^MemAvailable:\s+(\d+)\s+kB$', Path('/proc/meminfo').read_text(), re.MULTILINE)
        if not available or int(available.group(1))*1024 < 24_000_000_000:
            raise RuntimeError('Insufficient host memory headroom for 16GB sampled RSS plus 8GB reserve')

    def _verify_candidate(self, sha):
        for value in (BASELINE, sha):
            if git(self.mirror, 'rev-parse', value+'^{commit}') != value:
                raise ValueError('Missing exact commit in staged mirror')
        if git(self.mirror, 'diff', '--name-only', BASELINE, sha, '--', *PROTECTED):
            raise ValueError('Candidate changed protected benchmark/data/dependency files')

    def _checkout(self, directory, sha, deadline):
        code = directory/'code'
        for command in (['git', 'clone', '--shared', '--no-checkout', str(self.mirror), str(code)],
                        ['git', '-C', str(code), 'checkout', '--detach', sha]):
            remaining = deadline-time.monotonic()
            if remaining <= 0: raise TimeoutError('Evaluation budget exhausted during checkout')
            subprocess.run(command, check=True, capture_output=True, timeout=min(60, remaining))
        return code

    def _execute(self, command, code, output, remaining, fds):
        # Independent timeout survives a killed SSH/controller process. Inherited
        # locks prevent another request from overlapping any surviving child.
        guarded = ['/usr/bin/timeout', '--signal=TERM', '--kill-after=5s', f'{max(.001, remaining):.3f}', *command]
        return execute(guarded, code, output, remaining, fds), guarded

    def _check_report(self, output, setup, sha, manifest):
        import numpy as np
        report_path, arrays_path = output/'report.json', output/'arrays.npz'
        report = json.loads(report_path.read_text())
        official = validate_official_report(report, setup=setup, cpu=2, candidate_sha=sha, harness_hashes=manifest['files'])
        with np.load(arrays_path, allow_pickle=False) as archive:
            arrays = dict(archive)
        arrays['loss'] = np.asarray(report['validation']['loss'], dtype=np.float64)
        artifacts = audit_arrays(arrays, arrays, sensitivity_tolerance=WORKLOADS[setup]['tolerance'])
        comparisons = {}
        for label, root in self.reference_roots.items():
            reference_report = json.loads((root/setup/'report.json').read_text())
            with np.load(root/setup/'arrays.npz', allow_pickle=False) as archive: reference = dict(archive)
            reference['loss'] = np.asarray(reference_report['validation']['loss'], dtype=np.float64)
            comparison = audit_arrays(reference, arrays, sensitivity_tolerance=WORKLOADS[setup]['tolerance'])
            ga, gb = reference.get('gradient'), arrays.get('gradient')
            if ga is not None and gb is not None and ga.shape == gb.shape:
                comparison['gradient_relative_l2'] = float(np.linalg.norm(ga-gb)/max(float(np.linalg.norm(ga)), 1e-300))
                comparison['gradient_max_abs_difference'] = float(np.max(np.abs(ga-gb)))
            comparisons[label] = comparison
        return {'official': official, 'artifacts': artifacts, 'strict_comparisons': comparisons,
                'report_sha256': file_digest(report_path), 'arrays_sha256': file_digest(arrays_path),
                'first_run_seconds': report['timing_seconds']['end_to_end'], 'phases': report['phases'],
                'effective_environment': report['environment'], 'source': report['source']}

    def run(self, identity):
        directory = self._directory(identity)
        try:
            with lock(self.root/'execution.lock', nonblocking=True) as global_fd:
                state = self.status(identity)
                if state['status'] in TERMINAL: return state
                if state['status'] == 'running':
                    self._save(directory, state, status='interrupted', finished_at=time.time(),
                               error='Previous started execution lost its owner; no automatic re-execution or inferred verdict', official_passed=None)
                    return state
                envelope = json.loads((directory/'request.json').read_text())
                request = envelope['request']
                if digest(request) != envelope['request_digest'] or state['request_digest'] != envelope['request_digest']:
                    raise ValueError('Durable request digest mismatch')
                if digest(self._policy()) != envelope['policy_digest']:
                    raise ValueError('Execution policy changed since registration')
                if time.time() >= request['deadline_unix']:
                    self._save(directory, state, status='expired', finished_at=time.time(), error='No new evaluation admitted after request deadline')
                    return state
                self._verify_candidate(request['sha'])
                try:
                    with reserve(self.lock_states) as legacy_fds:
                        self._check_resources()
                        self._save(directory, state, status='running', started_at=time.time(), owner_pid=os.getpid(),
                                   resource_snapshot=resource_snapshot(), policy=envelope['policy'])
                        deadline = time.monotonic()+min(request['timeout_seconds'], request['deadline_unix']-time.time())
                        return self._run_started(directory, state, request, envelope['policy'], deadline, (global_fd, *legacy_fds))
                except (BlockingIOError, RuntimeError) as error:
                    if state['status'] != 'queued': raise
                    self._save(directory, state, blocked_reason=str(error), last_attempt_at=time.time())
                    return state
        except BlockingIOError:
            return self.status(identity)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            # A preflight identity/provenance failure cannot become an indefinite retry.
            state = self.status(identity)
            if state['status'] == 'queued':
                self._save(directory, state, status='failed', finished_at=time.time(),
                           error=f'Preflight {type(error).__name__}: {error}', official_passed=None,
                           promotion_ready=False)
                return state
            raise

    def _run_started(self, directory, state, request, policy, deadline, fds):
        try:
            code = self._checkout(directory, request['sha'], deadline)
            for repetition in range(1, request['fresh_process_repetitions']+1):
                for setup in ('grid', 'aligo'):
                    remaining = deadline-time.monotonic()
                    if remaining <= 0: raise TimeoutError('Total evaluation budget exhausted')
                    output = directory/f'{setup}-{repetition}'
                    output.mkdir()
                    entry = 'benchmark.py' if setup == 'grid' else 'benchmark_aligo.py'
                    command = ['taskset', '-c', '2', PYTHON, '-u', str(VENDOR/entry), '--repo', str(code),
                               '--cpus', '1', '--repeats', '3', '--output', str(output/'report.json'), '--save-arrays', str(output/'arrays.npz')]
                    execution, command = self._execute(command, code, output, remaining, fds)
                    check = {'setup': setup, 'repetition': repetition, 'command': command, 'output': str(output), **execution}
                    if (output/'report.json').exists() and (output/'arrays.npz').exists():
                        try: check.update(self._check_report(output, setup, request['sha'], policy['harness']))
                        except (ValueError, KeyError, OSError, TypeError) as error: check['report_error'] = str(error)
                    state['checks'].append(check)
                    self._save(directory, state)
            if request['run_generalization']:
                self._generalization(directory, state, request, code, deadline, fds)
            else:
                state['generalization'] = {'status': 'not_requested', 'passed': None, 'comparisons': {}}
            # Recheck source/harness/reference digests after arbitrary candidate code.
            if git(code, 'rev-parse', 'HEAD') != request['sha'] or git(code, 'status', '--porcelain', '--untracked-files=no'):
                raise ValueError('Candidate checkout changed during execution')
            if digest(self._policy()) != digest(policy): raise ValueError('Trusted harness/reference changed during execution')
            expected = 2*request['fresh_process_repetitions']
            complete = len(state['checks']) == expected
            passed = complete and all(c.get('returncode') == 0 and c.get('failure') is None
                and c.get('official', {}).get('passed') is True and c.get('artifacts', {}).get('passed') is True for c in state['checks'])
            timings = {}
            for setup in ('grid', 'aligo'):
                values = [c['first_run_seconds'] for c in state['checks'] if c['setup']==setup and 'first_run_seconds' in c]
                if values: timings[setup] = {'fresh_process_seconds': values, 'median_seconds': statistics.median(values),
                                            'minimum_seconds': min(values), 'maximum_seconds': max(values), 'count':len(values)}
            strict = [v['passed'] for c in state['checks'] for v in c.get('strict_comparisons', {}).values()]
            self._save(directory, state, status='completed' if passed else 'failed', finished_at=time.time(),
                       official_passed=passed, strict_passed=all(strict) if strict else None, timings=timings,
                       timing_scope='Separate fresh-process setup medians, not a combined score or judges median claim; external contention not excluded',
                       numerical_review_required=any(not x for x in strict) or state['generalization'].get('passed') is False,
                       promotion_ready=False)
            publication = self._publication(directory, state, request, policy)
            durable_json(directory/'receipt.json', publication)
            self._save(directory, state, promotion_ready=publication['admission']['promotion_ready'],
                       receipt_path=str((directory/'receipt.json').relative_to(self.root)),
                       receipt_sha256=file_digest(directory/'receipt.json'))
        except BaseException as error:
            self._save(directory, state, status='interrupted' if isinstance(error, (KeyboardInterrupt, InterruptedError)) else 'failed',
                       finished_at=time.time(), error=f'{type(error).__name__}: {error}', official_passed=None, promotion_ready=False)
            if isinstance(error, (KeyboardInterrupt, SystemExit)): raise
        return state

    def _generalization(self, directory, state, request, code, deadline, fds):
        remaining = deadline-time.monotonic()
        if remaining <= 0: raise TimeoutError('No time remaining for required generalization')
        output = directory/'generalization'; output.mkdir()
        archive = output/'arrays.npz'
        command = ['taskset','-c','2',PYTHON,'-u',str(self.generalization_harness),'run','--tree',str(code),
                   '--out',str(archive),'--cases',','.join(CASES)]
        execution, command = self._execute(command, code, output, remaining, fds)
        result = {'command':command, 'cases':list(CASES), **execution, 'comparisons':{}}
        if archive.exists():
            result['archive_sha256'] = file_digest(archive)
            result['artifacts'] = audit_archive(archive, archive, list(CASES))
            for label, reference in self.generalization_refs.items():
                result['comparisons'][label] = audit_archive(reference, archive, list(CASES))
        result['passed'] = (execution['returncode']==0 and execution['failure'] is None
                            and set(result['comparisons'])=={'pristine','initial_seed'}
                            and all(c['passed'] for c in result['comparisons'].values()))
        durable_json(output/'comparison.json', result)
        self._save(directory, state, generalization=result)

    def _publication(self, directory, state, request, policy):
        """Small fail-closed publication contract; inherited pristine discrepancies stay visible."""
        benchmarks, environments, new_failures, inherited = {}, [], [], []
        for setup in ('grid', 'aligo'):
            checks = [c for c in state['checks'] if c['setup'] == setup]
            samples = []
            for check in checks:
                if 'first_run_seconds' not in check: continue
                env = check['effective_environment']
                environments.append(environment_cohort(env))
                samples.append({'seconds': check['first_run_seconds'],
                    'candidate_sha': request['sha'], 'fresh_process': True,
                    'official_passed': (check.get('returncode') == 0 and check.get('failure') is None
                        and check.get('official', {}).get('passed') is True and check.get('artifacts', {}).get('passed') is True),
                    'report_path': str((Path(check['output'])/'report.json').relative_to(self.root)),
                    'report_sha256': check['report_sha256'], 'arrays_sha256': check['arrays_sha256'],
                    'effective_environment': env})
                comparisons = check.get('strict_comparisons', {})
                if comparisons.get('initial_seed', {}).get('passed') is not True:
                    new_failures.append(f'{setup}/{check["repetition"]}: missing or failed initial-seed comparison')
                if comparisons.get('pristine', {}).get('passed') is not True:
                    inherited.append({'setup': setup, 'repetition': check['repetition'],
                                      'pristine_comparison': comparisons.get('pristine')})
            values = [x['seconds'] for x in samples]
            benchmarks[setup] = {'passed': len(checks) == request['fresh_process_repetitions'] and all(
                c.get('returncode') == 0 and c.get('failure') is None and c.get('official', {}).get('passed') is True
                and c.get('artifacts', {}).get('passed') is True for c in checks), 'fresh_process': True,
                'samples': samples, 'median_seconds': statistics.median(values) if values else None,
                'minimum_seconds': min(values) if values else None, 'maximum_seconds': max(values) if values else None}
        gen = state.get('generalization', {})
        seed = gen.get('comparisons', {}).get('initial_seed', {})
        pristine = gen.get('comparisons', {}).get('pristine', {})
        cases = seed.get('cases', [])
        all_finite = gen.get('artifacts', {}).get('passed') is True
        inputs_identical = len(cases) == len(CASES) and all(not any(
            'input values differ' in issue or ('parameters:' in issue or 'frequencies:' in issue)
            or 'missing arrays' in issue for issue in c.get('issues', [])) for c in cases)
        gen_ok = (gen.get('returncode') == 0 and gen.get('failure') is None and seed.get('passed') is True
                  and all_finite and inputs_identical and [c.get('case') for c in cases] == list(CASES))
        if not gen_ok: new_failures.append('generalization: full 14-case initial-seed regression check missing or failed')
        if pristine.get('passed') is not True:
            inherited.append({'generalization_pristine_comparison': pristine or None})
        # Same-host/runtime/harness comparisons permit recorded package compiler options.
        # The compiler settings are code changes, not silently removed from raw evidence.
        environment_digests = {digest(env) for env in environments}
        reference_environments = {digest(item['environment_cohort']) for reference in policy['references'].values()
                                  for item in reference['files'].values()}
        cohort_passed = (len(environment_digests) == 1 and reference_environments == environment_digests
                         and set(policy['references']) == {'pristine', 'initial_seed'})
        cohort = {'host': platform.node(), 'policy': {key: policy[key] for key in (
            'cpu', 'python', 'memory_budget_bytes', 'memory_reserve_bytes', 'lock_states', 'harness', 'runtime_files')},
            'container_limits': state.get('resource_snapshot', {}).get('container_limits'),
            'environment': environments[0] if environments else None,
            'timing_regime': 'both-existing-queues-reserved; external-contention-not-excluded'}
        if len(environment_digests) != 1: new_failures.append('Inconsistent or missing execution environments')
        if not cohort_passed: new_failures.append('Missing or mismatched reference hardware/environment cohort')
        eligible = (state.get('official_passed') is True and request['fresh_process_repetitions'] >= 3
                    and all(len(b['samples']) >= 3 and b['passed'] for b in benchmarks.values())
                    and not new_failures and set(policy['references']) == {'pristine', 'initial_seed'}
                    and bool(pristine))
        return {'schema_version': 'feyer-overnight-evaluation-v1', 'evaluation_id': request['request_id'],
            'candidate_sha': request['sha'], 'cohort_digest': digest(cohort), 'cohort': cohort,
            'benchmarks': benchmarks, 'generalization': {'case_count': len(cases), 'all_finite': all_finite,
                'inputs_identical': inputs_identical, 'seed_comparison_passed': gen_ok, 'new_failures': new_failures,
                'seed_case_checks': cases, 'artifact_checks': gen.get('artifacts'),
                'candidate_archive_sha256': gen.get('archive_sha256'),
                'pristine_comparison': pristine or None,
                'comparison_path': str((directory/'generalization/comparison.json').relative_to(self.root)) if gen.get('cases') else None,
                'comparison_sha256': file_digest(directory/'generalization/comparison.json') if gen.get('cases') else None},
            'admission': {'promotion_ready': eligible, 'source_sha': request['sha'], 'candidate_sha': request['sha'],
                'comparison_cohort_passed': cohort_passed,
                'scope': 'public-benchmarks-and-no-new-regressions', 'universal_physics_claim': False},
            'inherited_caveats': inherited,
            'note': 'Pristine mismatches remain review caveats, never erased; initial seed comparison is the no-new-regression gate.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/workspace/feyer-final-validation'))
    parser.add_argument('--mirror', type=Path, default=Path('/workspace/feyer-lab/repo.git'))
    parser.add_argument('--lock-state', action='append')
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--seed-reference-root', type=Path)
    parser.add_argument('--generalization-harness', type=Path)
    parser.add_argument('--generalization-reference', type=Path)
    parser.add_argument('--generalization-seed', type=Path)
    parser.add_argument('command', choices=('register','run','status'))
    parser.add_argument('--request-id')
    args = parser.parse_args()
    runner = Runner(args.root, mirror=args.mirror, lock_states=args.lock_state or LOCK_STATES,
                    reference_root=args.reference_root, seed_reference_root=args.seed_reference_root,
                    generalization_harness=args.generalization_harness,
                    generalization_reference=args.generalization_reference, generalization_seed=args.generalization_seed)
    import sys
    if args.command == 'register': result = runner.register(json.load(sys.stdin))
    else:
        if not args.request_id: parser.error('--request-id required')
        if args.command == 'run':
            def interrupted(signum, frame): raise InterruptedError('Termination signal '+str(signum))
            signal.signal(signal.SIGTERM, interrupted)
            result = runner.run(args.request_id)
        else: result = runner.status(args.request_id)
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__': main()
