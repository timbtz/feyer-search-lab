"""Read-only, loopback-only search observatory. No model calls or queue mutations.

python -m lab.live_dashboard --repo /path/to/main --port 8765 --sync-remote --sync-team
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .evolution import Campaign
from .evolution_report import _private_key

SECRET = re.compile(r'\b(?:rc-[\da-fA-F]{24,}|gh[pousr]_[\w]{20,}|github_pat_[\w]{20,}|sk-[\w-]{20,})\b|(?i:Bearer\s+\S+)')
PRIVATE = re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)', re.S)
TERMINAL = {'completed', 'failed', 'timed_out', 'interrupted', 'rejected'}
WORKER_TERMINAL = {'complete', 'completed', 'failed', 'budget_exhausted', 'stopped', 'blocked', 'no_candidate'}
REPO_URL = 'https://github.com/timbtz/feyer-search-lab'
TEAM_ENDPOINT = 'repos/timbtz/feyer-search-lab/contents/state.json?ref=control/team-search'
TEAM_LIMIT = 16_000_000
TEAM_STALE_SECONDS = 90
PROFILER_STALE_SECONDS = 90


def public(value):
    """Remove credentials even from a malformed log; never read credential files."""
    if isinstance(value, dict):
        return {str(k): public(v) for k, v in value.items() if not _private_key(k)}
    if isinstance(value, list):
        return [public(v) for v in value]
    if isinstance(value, str):
        value = PRIVATE.sub('[private key redacted]', value)
        value = SECRET.sub('[credential redacted]', value)
        return re.sub(r'(?im)^.*\b(?:api[_-]?key|authorization|password|access_token|refresh_token|claim_token|actor_token|role_token|token|capability|secret)\s*[:=].*$', '[credential line redacted]', value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def read_json(path, limit=16_000_000):
    if path.is_symlink() or path.stat().st_size > limit:
        raise ValueError('Refusing symlink or oversized data file')
    return json.loads(path.read_text())


def team_state(value):
    """Validate the presentation envelope without inferring scientific eligibility."""
    if not isinstance(value, dict) or value.get('schema') != 'feyer-team-search-v1':
        raise ValueError('Unsupported team search snapshot')
    if not isinstance(value.get('coordinator'), str) or not value['coordinator']:
        raise ValueError('Team coordinator is missing')
    for name in ('tasks', 'observations'):
        rows = value.get(name)
        if not isinstance(rows, dict) or any(not isinstance(k, str) or not isinstance(v, dict)
                                             for k, v in rows.items()):
            raise ValueError('Invalid team ' + name)
    for identity, task in value['tasks'].items():
        if task.get('id') != identity:
            raise ValueError('Task identity does not match its key')
        for name in ('parents', 'candidates', 'depends_on'):
            rows = task.get(name, [])
            if not isinstance(rows, list) or any(not isinstance(v, str) for v in rows):
                raise ValueError('Invalid task ' + name)
        if not isinstance(task.get('candidate_branches', {}), dict):
            raise ValueError('Invalid candidate branch map')
    for observation in value['observations'].values():
        if not isinstance(observation.get('evidence'), dict):
            raise ValueError('Invalid observation evidence')
        if 'job' in observation and not isinstance(observation['job'], dict):
            raise ValueError('Invalid observation job')
    if not isinstance(value.get('events'), list) or any(not isinstance(e, dict) for e in value['events']):
        raise ValueError('Invalid team event history')
    return public(value)


def team_updated_at(value):
    """Latest recorded source event, distinct from successful fetch/copy time."""
    stamps = [e.get('at') for e in value['events']]
    stamps += [t.get(key) for t in value['tasks'].values()
               for key in ('created_at', 'claimed_at', 'updated_at')]
    return max((s for s in stamps if type(s) in (int, float) and math.isfinite(s) and s > 0), default=None)


def profiler_state(value):
    """Read profiler presentation records without deriving a validation verdict."""
    if not isinstance(value, dict) or not isinstance(value.get('profiler_reports'), list):
        raise ValueError('Invalid profiler collection')
    if 'schema' in value and value['schema'] != 'feyer-profiler-collection-v1':
        raise ValueError('Unsupported profiler collection schema')
    for report in value['profiler_reports']:
        if not isinstance(report, dict) or report.get('schema') != 'feyer-profiler-v1':
            raise ValueError('Unsupported profiler record schema')
        if report.get('status') not in ('ok', 'invalid_report', 'conflicting_artifacts'):
            raise ValueError('Unknown profiler record status')
        for name in ('phases', 'groups'):
            rows = report.get(name, [])
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError('Invalid profiler ' + name)
        for name in ('issues', 'limits'):
            rows = report.get(name, [])
            if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
                raise ValueError('Invalid profiler ' + name)
        if not isinstance(report.get('warm_timing', {}), dict):
            raise ValueError('Invalid profiler warm timing')
    return public(value['profiler_reports'])


GENERALIZATION_CASE_STATUSES = ('ok', 'needs_review', 'candidate_error', 'reference_unavailable', 'candidate_missing')


def generalization_state(value):
    """Read cross-setup comparison records written by `lab.gencheck report`.

    These are development comparisons against the unchanged simulator on other
    optical setups. They are not queue measurements and do not change a
    candidate's official, strict or Pareto status.
    """
    if not isinstance(value, dict) or value.get('schema') != 'feyer-generalization-collection-v1':
        raise ValueError('Unsupported generalization collection schema')
    reports = value.get('reports')
    if not isinstance(reports, list):
        raise ValueError('Invalid generalization collection')
    for report in reports:
        if not isinstance(report, dict) or report.get('schema') != 'feyer-generalization-v1':
            raise ValueError('Unsupported generalization record schema')
        if report.get('status') not in ('ok', 'needs_review'):
            raise ValueError('Unknown generalization record status')
        if not isinstance(report.get('candidate_sha'), str) or not isinstance(report.get('cases'), list):
            raise ValueError('Invalid generalization record identity')
        for case in report['cases']:
            if not isinstance(case, dict) or not isinstance(case.get('case'), str):
                raise ValueError('Invalid generalization case')
            if case.get('status') not in GENERALIZATION_CASE_STATUSES:
                raise ValueError('Unknown generalization case status')
            if not isinstance(case.get('issues', []), list):
                raise ValueError('Invalid generalization case issues')
    return public(reports)


JAXCOMPAT_TEST_STATUSES = ('ok', 'different', 'unsupported', 'missing', 'reference_unavailable')


def jaxcompat_state(value):
    """Read JAX transformation compatibility records written by `lab.jaxcompat report`.

    They describe which JAX transformations a candidate supports relative to the
    unchanged simulator. They do not change official, strict or Pareto status.
    """
    if not isinstance(value, dict) or value.get('schema') != 'feyer-jaxcompat-collection-v1':
        raise ValueError('Unsupported JAX compatibility collection schema')
    reports = value.get('reports')
    if not isinstance(reports, list):
        raise ValueError('Invalid JAX compatibility collection')
    for report in reports:
        if not isinstance(report, dict) or report.get('schema') != 'feyer-jaxcompat-v1':
            raise ValueError('Unsupported JAX compatibility record schema')
        if report.get('status') not in ('compatible', 'incompatible'):
            raise ValueError('Unknown JAX compatibility record status')
        if not isinstance(report.get('candidate_sha'), str) or not isinstance(report.get('tests'), list):
            raise ValueError('Invalid JAX compatibility record identity')
        for test in report['tests']:
            if not isinstance(test, dict) or not isinstance(test.get('test'), str):
                raise ValueError('Invalid JAX compatibility test')
            if test.get('status') not in JAXCOMPAT_TEST_STATUSES:
                raise ValueError('Unknown JAX compatibility test status')
    return public(reports)


def tail(path, size=10000):
    if not path.is_file() or path.is_symlink():
        return ''
    with path.open('rb') as stream:
        offset = max(0, path.stat().st_size - size)
        stream.seek(offset)
        value = stream.read(size).decode('utf-8', errors='replace')
        if offset:
            value = value.partition('\n')[2]
        # A tail can start inside a PEM block, after its BEGIN delimiter.
        value = re.sub(r'(?m)^[A-Za-z0-9+/=]{48,}\s*$', '[opaque credential-like line redacted]', value)
        return public(value)


class ReadOnlyCampaign(Campaign):
    """Reuse canonical calculations without invoking Campaign's schema initializer."""
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError('Refusing symlink database')

    @contextlib.contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.3)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA query_only=ON')
            yield db
        finally:
            db.close()


def process_status(pid, expected=None):
    if type(pid) is not int or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    if expected and (isinstance(expected, str) or isinstance(expected, list) and all(isinstance(term, str) for term in expected)):
        try:
            result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True, timeout=2)
            if result.returncode:
                return None
            terms = [expected] if isinstance(expected, str) else expected
            return all(term in result.stdout for term in terms)
        except (OSError, subprocess.TimeoutExpired):
            return None
    # A PID may be reused: presence without an identity match is not proof.
    return None


def job_summary(job, source='local artifact'):
    from .phase_report import metrics, signature
    from .evolution_evidence import normalize_job
    report = job.get('report.json') or {}
    execution = job.get('result') or {}
    comparison = job.get('comparison.json') or {}
    out = {k: job.get(k) for k in ('id', 'sha', 'request_id', 'profile', 'status', 'agent', 'branch',
                                   'direction', 'hypothesis', 'created_at', 'updated_at', 'error')}
    out.update(source=source, official_check=('passed' if execution.get('official_passed') is True else
        'failed' if execution.get('official_passed') is False else 'not_run' if job.get('profile') == 'screen' else 'unknown'),
        strict_check='passed' if comparison.get('passed') is True else 'failed' if comparison.get('passed') is False else 'not_run' if job.get('profile')=='screen' else 'unknown',
        peak_rss_bytes=(execution.get('memory_monitoring') or {}).get('sampled_process_group_peak_rss_bytes'))
    try:
        out['metrics'], out['phases'] = metrics(report)
    except (KeyError, ValueError, TypeError):
        out['metrics'], out['phases'] = {}, {}
    out['warm_timing'] = report.get('timing_seconds', {}).get('phase_runtime_medians', {})
    out['resource_evidence'] = execution.get('memory_monitoring', {})
    out['comparison'] = comparison
    # Timing identity is separate from scientific eligibility. A signature alone
    # neither identifies a physical instance nor proves an uncontended run.
    try:
        out['timing_signature'] = signature(report) if out['metrics'] else None
    except (KeyError, ValueError, TypeError, AttributeError):
        out['timing_signature'] = None
    try:
        evidence = normalize_job(job)
        out['evidence'] = {key: evidence.get(key) for key in (
            'schema_version', 'job_id', 'candidate_sha', 'profile', 'execution_status',
            'category', 'eligible_full', 'cohort_digest', 'checks', 'issues', 'artifact_digest')}
    except (KeyError, ValueError, TypeError, AttributeError):
        out['evidence'] = None
    out['instance'] = job.get('instance') if isinstance(job.get('instance'), str) else None
    for key in ('comparison_context', 'provenance'):
        out[key] = job.get(key) if isinstance(job.get(key), dict) else None
    reported_source = report.get('source')
    reported_source = reported_source if isinstance(reported_source, dict) else {}
    out['evaluation_provenance'] = dict(
        reported_candidate_sha=reported_source.get('commit'),
        protected_baseline_sha=execution.get('baseline_sha'),
        evaluator_sha256=execution.get('evaluator_sha256'),
        reported_evaluator_sha256=report.get('starter_sha256'),
        worker_sha256=execution.get('worker_sha256'),
        comparison_evaluator_sha256=execution.get('comparison_evaluator_sha256'),
        reference_arrays_sha256=execution.get('reference_arrays_sha256'),
        measured_at=report.get('measured_at_utc'),
        started_at=job.get('started_at'), finished_at=job.get('finished_at'))
    out['log_tail'] = public('\n'.join(str(job.get(k, ''))[-4000:] for k in ('stdout.log', 'stderr.log', 'run.log') if job.get(k)))
    return public(out)


class Observatory:
    def __init__(self, repo, remote=False, host='amd-hackathon', root='/workspace/feyer-lab', team=False):
        self.repo = Path(repo).resolve()
        self.lab = self.repo / '.lab'
        self.lock = threading.Lock()
        self.remote = dict(enabled=remote, observed_at=None, error=None, jobs=[])
        self.remote_details = {}
        self.team = dict(sync_enabled=team, mode='github' if team else 'local_snapshot',
                         source=REPO_URL + '/blob/control/team-search/state.json' if team else '.lab/team/state.json',
                         observed_at=None, source_updated_at=None, error=None)
        self.team_data = None
        self.profiler = dict(source='.lab/profiler/report.json', observed_at=None, error=None)
        self.profiler_data = None
        self.generalization = dict(source='.lab/generalization/report.json', observed_at=None, error=None)
        self.generalization_data = None
        self.jaxcompat = dict(source='.lab/jaxcompat/report.json', observed_at=None, error=None)
        self.jaxcompat_data = None
        self.cached_files = {}
        self.host, self.root = host, root
        self.stop = threading.Event()

    def cached_json(self, path):
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        old = self.cached_files.get(str(path))
        if old and old[0] == stamp:
            return old[1]
        data = read_json(path)
        self.cached_files[str(path)] = (stamp, data)
        return data

    def refresh_team(self):
        """One read-only GitHub observation; credentials stay in the gh process."""
        if not self.team['sync_enabled']:
            return
        try:
            response = subprocess.run(['gh', 'api', '--hostname', 'github.com', '--method', 'GET', TEAM_ENDPOINT,
                                       '--header', 'Accept: application/vnd.github.raw+json'],
                                      capture_output=True, text=True, check=True, timeout=20)
            if len(response.stdout.encode('utf-8')) > TEAM_LIMIT:
                raise ValueError('Oversized team snapshot')
            data = team_state(json.loads(response.stdout))
            with self.lock:
                self.team_data = data
                self.team.update(observed_at=time.time(), source_updated_at=team_updated_at(data), error=None)
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            with self.lock:
                self.team['error'] = (f'{type(exc).__name__}: GitHub team search unavailable; '
                                      'last successful observation retained if available')

    def poll_team(self):
        while not self.stop.is_set():
            self.refresh_team()
            self.stop.wait(30)

    def team_snapshot(self, now):
        if not self.team['sync_enabled']:
            path = self.lab / 'team' / 'state.json'
            try:
                if path.is_symlink() or path.parent.is_symlink():
                    raise ValueError('Refusing symlink team snapshot')
                data = team_state(self.cached_json(path))
                # Reading an unchanged local export must not make it appear live.
                observed_at = path.stat().st_mtime
                with self.lock:
                    self.team_data = data
                    self.team.update(observed_at=observed_at,
                                     source_updated_at=team_updated_at(data), error=None)
            except (OSError, ValueError, TypeError) as exc:
                with self.lock:
                    self.team['error'] = (f'{type(exc).__name__}: local team search snapshot unavailable; '
                                          'last successful observation retained if available')
        with self.lock:
            data, source = self.team_data, dict(self.team)
        source['available'] = data is not None
        source['stale'] = bool(source['error']) or source['observed_at'] is None or now - source['observed_at'] > TEAM_STALE_SECONDS
        return data, source

    def profiler_snapshot(self, now):
        path = self.lab / 'profiler' / 'report.json'
        try:
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError('Refusing symlink profiler snapshot')
            reports = profiler_state(self.cached_json(path))
            observed_at = path.stat().st_mtime
            with self.lock:
                self.profiler_data = reports
                self.profiler.update(observed_at=observed_at, error=None)
        except (OSError, ValueError, TypeError) as exc:
            with self.lock:
                self.profiler['error'] = (f'{type(exc).__name__}: local profiler snapshot unavailable; '
                                          'last successful observation retained if available')
        with self.lock:
            reports, source = self.profiler_data, dict(self.profiler)
        source['available'] = reports is not None
        source['stale'] = bool(source['error']) or source['observed_at'] is None or now - source['observed_at'] > PROFILER_STALE_SECONDS
        return reports if reports is not None else [], source

    def collection_snapshot(self, name, relative, validator, label):
        """Read one optional local evidence collection; keep the last good copy on error."""
        path = self.lab / relative
        source_attr, data_attr = name, name + '_data'
        try:
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError(f'Refusing symlink {label} snapshot')
            reports = validator(self.cached_json(path))
            observed_at = path.stat().st_mtime
            with self.lock:
                setattr(self, data_attr, reports)
                getattr(self, source_attr).update(observed_at=observed_at, error=None)
        except FileNotFoundError:
            with self.lock:
                getattr(self, source_attr)['error'] = None if getattr(self, data_attr) is None else (
                    f'FileNotFoundError: {label} snapshot removed; last successful observation retained')
        except (OSError, ValueError, TypeError) as exc:
            with self.lock:
                getattr(self, source_attr)['error'] = (f'{type(exc).__name__}: local {label} snapshot unavailable; '
                                                       'last successful observation retained if available')
        with self.lock:
            reports, source = getattr(self, data_attr), dict(getattr(self, source_attr))
        source['available'] = reports is not None
        return reports if reports is not None else [], source

    def generalization_snapshot(self, now):
        return self.collection_snapshot('generalization', Path('generalization') / 'report.json',
                                        generalization_state, 'generalization')

    def jaxcompat_snapshot(self, now):
        return self.collection_snapshot('jaxcompat', Path('jaxcompat') / 'report.json',
                                        jaxcompat_state, 'JAX compatibility')

    def poll_remote(self):
        from .client import Client
        client = Client(self.host, self.root)
        while not self.stop.is_set():
            try:
                jobs = client.request({'action': 'list', 'limit': 250})
                if not isinstance(jobs, list):
                    raise ValueError('Unexpected queue response')
                # Refresh queue state promptly, then fetch only a few changed reports.
                with self.lock:
                    self.remote.update(jobs=public(jobs), observed_at=time.time(), error=None)
                for item in sorted(jobs, key=lambda j: j.get('updated_at') or 0, reverse=True)[:12]:
                    job_id = item.get('id', '')
                    if not re.fullmatch('[0-9a-f]{32}', job_id):
                        continue
                    with self.lock:
                        cached = self.remote_details.get(job_id)
                    if cached and cached.get('updated_at') == item.get('updated_at') and cached.get('status') == item.get('status'):
                        continue
                    detail = job_summary(client.request({'action': 'show', 'id': job_id}), 'AMD queue (read-only SSH)')
                    with self.lock:
                        self.remote_details[job_id] = detail
            except Exception as exc:
                with self.lock:
                    self.remote['error'] = f'{type(exc).__name__}: remote queue refresh failed; last successful observation retained'
            self.stop.wait(15)

    def campaign(self, directory):
        data = ReadOnlyCampaign(directory / 'campaign.sqlite3').snapshot()
        spec = data['campaign']['spec']
        runtime = self.cached_json(directory / 'runtime.json') if (directory / 'runtime.json').exists() else {}
        launch = self.cached_json(directory / 'launch.json') if (directory / 'launch.json').exists() else {}
        log = tail(directory / 'controller.log')
        pid = launch.get('pid')
        alive = process_status(pid, ['lab.evolution_run', str(directory)])
        last = max([data['campaign']['created_at']] + [e['at'] for e in data['events']])
        stopped = (directory / 'STOP').exists()
        inflight = any(l.get('inflight_candidate') for l in data['lanes'])
        expired = time.time() >= spec['budget']['deadline_unix']
        spent = any(data['usage'].get(k, 0) >= spec['budget']['max_' + k]
                    for k in ('proposals', 'evaluations', 'model_calls')
                    if spec['budget'].get('max_' + k, 0) > 0)
        status = ('stop_requested' if alive and stopped else 'running' if alive else
                  'interrupted' if alive is False and inflight else 'stopped' if stopped else
                  'budget_exhausted' if spent and not inflight else
                  'deadline_reached' if expired else 'unknown')
        alerts = []
        if 'No space left on device' in log and inflight:
            alerts.append('Controller log records a disk-full failure. Queue results may be newer than this ledger; recovery requires coordinator reconciliation.')
        if inflight and alive is not True:
            alerts.append('Ledger has pending work; controller liveness is not verified. Check live queue status.')
        data.update(id=spec['campaign_id'], selector=spec.get('selector', runtime.get('selector', 'qwen')),
                    status=status, source_updated_at=last, stale=time.time()-last > 120,
                    budget=spec['budget'], objective=spec['objective'], branch=runtime.get('branch'),
                    controller={'pid': pid, 'process_alive': alive, 'status': status, 'log_tail': log,
                                'log_updated_at': (directory/'controller.log').stat().st_mtime if (directory/'controller.log').exists() else None},
                    stop_requested=stopped, alerts=alerts)
        # Core reserves model invocations; a CLI invocation can contain many requests.
        data['model_budget_unit'] = 'reserved proposer invocations, not underlying provider requests'
        return public(data)

    def workers(self):
        rows = []
        paths = sorted((self.lab/'sessions').glob('*/status.json')) + sorted((self.lab/'agent-status').glob('*.json'))
        for path in paths:
            try:
                d = self.cached_json(path)
                manifest = d.get('manifest') or {}
                provider = d.get('provider', d.get('agent_provider', manifest.get('provider', 'unknown')))
                if isinstance(provider, dict):
                    provider = provider.get('name', 'unknown')
                observed = d.get('observed_at', d.get('updated_at', path.stat().st_mtime))
                reported = d.get('status', 'unknown')
                expected = d.get('process_match')
                if not expected and path.parent.parent.name == 'sessions' and d.get('worktree'):
                    expected = ['lab.agent_loop', d['worktree']]
                host = d.get('host', d.get('execution_host', manifest.get('execution_host', 'local Mac')))
                alive = process_status(d.get('pid'), expected) if 'local' in host.lower() or 'mac' in host.lower() else None
                status = reported if reported in WORKER_TERMINAL else 'running' if alive is True else 'not_running' if alive is False else reported if reported in ('idle', 'blocked', 'available', 'ready') else 'service_active_observed' if reported=='active' and 'hetzner' in host.lower() else 'unverified'
                worker_id = d.get('id', path.parent.name if path.name == 'status.json' else path.stem)
                rows = [row for row in rows if row['id'] != worker_id]
                rows.append(dict(id=worker_id,
                    name=d.get('name', path.parent.name if path.name == 'status.json' else path.stem),
                    provider=provider, model=d.get('actual_model', d.get('model', d.get('agent_model'))) or 'inherited / not recorded',
                    status=status, reported_status=reported, process_alive=alive, pid=d.get('pid'),
                    observed_at=observed, stale=time.time()-observed > 120, host=host,
                    branch=d.get('branch'), session_id=d.get('session_id', d.get('thread_id')),
                    deadline_unix=d.get('deadline_unix', d.get('invocation_deadline_at')),
                    started_at=d.get('started_at', d.get('invocation_started_at')), runtime_commit=d.get('runtime_commit'),
                    candidates=d.get('candidates'), direction=d.get('direction'), reason=d.get('reason'), description=d.get('description'),
                    source=str(path.relative_to(self.repo)), log_tail=tail(path.parent/'supervisor.log') if path.name=='status.json' else '',
                    usage=d.get('usage')))
            except (OSError, ValueError, TypeError):
                rows.append(dict(id=path.parent.name if path.name=='status.json' else path.stem, status='unreadable', source=str(path.relative_to(self.repo))))
        return public(rows)

    def recorded_feedback(self, jobs):
        """Join agent statements by exact evaluated identity, never code ancestry."""
        paths = list((self.repo/'experiments/runs').glob('*/candidate-*.json'))
        paths += list((self.lab/'worktrees').glob('*/experiments/runs/*/candidate-*.json'))
        paths += list((self.lab/'campaigns').glob('*/worktree/experiments/runs/*/candidate-*.json'))
        matches = {}
        for path in sorted(paths):
            # A worktree directory symlink must not turn this into an arbitrary
            # filesystem reader; cached_json also caps each artifact's size.
            if any(parent.is_symlink() for parent in (path, *path.parents) if parent != self.repo):
                continue
            try:
                feedback = self.cached_json(path)
                if not isinstance(feedback, dict):
                    continue
                response, provenance = feedback.get('agent_response'), feedback.get('provenance')
                response = response if isinstance(response, dict) else {}
                provenance = provenance if isinstance(provenance, dict) else {}
                parents = provenance.get('parent_candidates')
                if not isinstance(parents, list) or not all(isinstance(p, str) and re.fullmatch(r'[0-9a-f]{40}', p) for p in parents):
                    parents = None
                record = dict(summary=response.get('summary') if isinstance(response.get('summary'), str) else None,
                    hypothesis=response.get('hypothesis') if isinstance(response.get('hypothesis'), str) else None,
                    parent_candidates=parents)
                for profile in ('screen', 'full'):
                    job = feedback.get(profile)
                    if not isinstance(job, dict) or not isinstance(job.get('id'), str):
                        continue
                    target = jobs.get(job['id'])
                    if (not target or job.get('sha') != target.get('sha')
                            or feedback.get('candidate_sha') != target.get('sha')
                            or job.get('profile') != profile or target.get('profile') != profile):
                        continue
                    matches.setdefault(job['id'], []).append((record, str(path.relative_to(self.repo))))
            except (OSError, ValueError, TypeError):
                continue
        for job_id, entries in matches.items():
            record = entries[0][0]
            conflict = any(other != record for other, _ in entries)
            if conflict:
                record = dict(summary=None, hypothesis=None, parent_candidates=None)
            jobs[job_id] = dict(jobs[job_id], recorded_feedback=public(dict(record,
                status='conflicting_records' if conflict else 'recorded', sources=[source for _, source in entries])))

    def state(self):
        now = time.time()
        team, team_source = self.team_snapshot(now)
        profiles, profiler_source = self.profiler_snapshot(now)
        generalization, generalization_source = self.generalization_snapshot(now)
        jaxcompat, jaxcompat_source = self.jaxcompat_snapshot(now)
        alerts, campaigns, jobs = [], [], {}
        for path in sorted((self.lab/'campaigns').glob('*/campaign.sqlite3')):
            try:
                campaigns.append(self.campaign(path.parent))
            except (OSError, ValueError, sqlite3.Error, KeyError) as exc:
                alerts.append(f'{path.parent.name}: ledger unavailable ({type(exc).__name__}); no successful state inferred')
        files = list((self.lab/'phase-ledger').glob('*.json')) + list((self.lab/'campaigns').glob('*/queue-results/*.json'))
        for path in files:
            try:
                j = job_summary(self.cached_json(path), str(path.relative_to(self.repo)))
                if j['id']:
                    jobs[j['id']] = j
            except (OSError, ValueError, KeyError, TypeError):
                alerts.append(f'Unreadable result artifact: {path.name}')
        with self.lock:
            queue = dict(self.remote)
            jobs.update(self.remote_details)
        self.recorded_feedback(jobs)
        queue['stale'] = queue['observed_at'] is None or now-queue['observed_at'] > 45
        historical = {}
        try:
            historical = self.cached_json(self.lab/'phase-dashboard/phases.json')
        except (OSError, ValueError):
            pass
        free = shutil.disk_usage(self.repo)
        if free.free < 1_000_000_000:
            alerts.append('Local disk has less than 1 GB free. Agent logs and durable result writes may fail; remote results are retained on AMD.')
        if queue['error']:
            alerts.append(queue['error'])
        workers = self.workers()
        infrastructure = [
            dict(id='mac', name='Local controller & dashboard', host='Mac', status='serving', observed_at=now,
                 description='Read-only dashboard, campaign coordinator and local CLI workers. Local storage is monitored.'),
            dict(id='github', name='GitHub provenance', host='timbtz/feyer-search-lab', status='not_probed',
                 description='Immutable source SHAs, owned branches, context, receipts and published evidence. Connectivity not inferred from local Git history.'),
            dict(id='hetzner', name='Native agent broker / SMAC helper', host='Hetzner', status='see_worker_evidence',
                 description='Single-slot Codex broker. SMAC helper readiness is shown by its own status evidence; Claude adapter not yet implemented in broker.'),
            dict(id='amd', name='Serial CPU evaluator', host='AMD cloud', status='observed' if not queue['stale'] else 'unverified', observed_at=queue['observed_at'],
                 description='CPU 2, one logical CPU. Screen and full use 101 frequencies / 193 variables. 32,000,000,000-byte sampled RSS watchdog; not a kernel memory limit. Radeon VRAM is separate and not used by these CPU benchmarks.'),
            dict(id='qwen', name='Optional narrow proposer', host='AMD Token Factory', status='optional',
                 description='Used by the initial pilot; not required for deterministic or SMAC selection. Main research uses Codex / Claude.')]
        snapshot = public(dict(generated_at=now, repo_url=REPO_URL, storage={'free_bytes':free.free,'total_bytes':free.total},
            campaigns=campaigns, workers=workers, infrastructure=infrastructure, jobs=list(jobs.values()),
            queue=queue, historical=historical, alerts=alerts,
            team_search=team, team_search_source=team_source,
            profiler_reports=profiles, profiler_source=profiler_source,
            generalization_reports=generalization, generalization_source=generalization_source,
            jaxcompat_reports=jaxcompat, jaxcompat_source=jaxcompat_source,
            read_only=True, refresh_seconds=5,
            stage_policy={'screen':'Complete physical workload, provisional checks; omits finite-difference gradient sanity check and strict saved-array comparison.',
                'full':'Official full benchmark plus separate strict saved-array / all-gradient comparison.',
                'objective':'Minimize complete first-run time, including imports/setup, compilation, execution and transfer.',
                'pareto':'Same-cohort valid full results only. Exact observed Pareto membership is separate from noise-qualified progress.',
                'expansion':'Coordinator freezes a new round after reviewed guidance; frozen per-lane stall_limit applies (default 3). No automatic budget extensions.'}))
        from .research_lineage import build_lineage
        snapshot['search_lineage'] = public(build_lineage(snapshot))
        return snapshot


def handler_for(observatory):
    assets = Path(__file__).parent/'dashboard'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            # Loopback binding alone does not prevent DNS rebinding.
            if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                self.send_error(403, 'Loopback host required')
                return
            path = urlsplit(self.path).path
            if path == '/api/state':
                try:
                    body = json.dumps(observatory.state(), allow_nan=False).encode()
                except Exception:
                    self.send_error(503, 'Evidence snapshot temporarily unavailable')
                    return
                mime = 'application/json; charset=utf-8'
            elif path in ('/', '/index.html', '/app.js', '/style.css', '/pds-loader.js', '/pds-variables.css', '/pds-normalize.css', '/pds-font-face.css', '/search-architecture.svg'):
                name = 'index.html' if path == '/' else path[1:]
                try:
                    body = (assets/name).read_bytes()
                except OSError:
                    self.send_error(404)
                    return
                mime = {'html':'text/html', 'js':'text/javascript', 'css':'text/css', 'svg':'image/svg+xml'}[name.rsplit('.',1)[1]]+'; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self' https://cdn.ui.porsche.com; script-src 'self' https://cdn.ui.porsche.com; style-src 'self' 'unsafe-inline'; font-src 'self' https://cdn.ui.porsche.com; img-src 'self' data: https://cdn.ui.porsche.com; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True, help='Main repository containing .lab state')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--sync-remote', action='store_true', help='Poll AMD via existing SSH; list/show only, no submissions')
    parser.add_argument('--sync-team', action='store_true', help='Read GitHub control/team-search every 30 seconds via gh; no ledger mutations')
    parser.add_argument('--host', default='amd-hackathon')
    parser.add_argument('--root', default='/workspace/feyer-lab')
    args = parser.parse_args()
    obs = Observatory(args.repo, args.sync_remote, args.host, args.root, team=args.sync_team)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(obs))
    server.daemon_threads = True
    if args.sync_remote:
        threading.Thread(target=obs.poll_remote, daemon=True).start()
    if args.sync_team:
        threading.Thread(target=obs.poll_team, daemon=True).start()
    print(f'Feyer Search Observatory: http://localhost:{server.server_port} (read-only)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        obs.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
