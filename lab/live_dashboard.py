"""Read-only, loopback-only search observatory. No model calls or queue mutations.

python -m lab.live_dashboard --repo /path/to/main --port 8765 --sync-remote
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
    from .phase_report import metrics
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
    out['log_tail'] = public('\n'.join(str(job.get(k, ''))[-4000:] for k in ('stdout.log', 'stderr.log', 'run.log') if job.get(k)))
    return public(out)


class Observatory:
    def __init__(self, repo, remote=False, host='amd-hackathon', root='/workspace/feyer-lab'):
        self.repo = Path(repo).resolve()
        self.lab = self.repo / '.lab'
        self.lock = threading.Lock()
        self.remote = dict(enabled=remote, observed_at=None, error=None, jobs=[])
        self.remote_details = {}
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
        status = ('stop_requested' if alive and stopped else 'running' if alive else
                  'interrupted' if alive is False and inflight else 'stopped' if stopped else
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

    def state(self):
        now = time.time()
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
        return public(dict(generated_at=now, repo_url=REPO_URL, storage={'free_bytes':free.free,'total_bytes':free.total},
            campaigns=campaigns, workers=workers, infrastructure=infrastructure, jobs=list(jobs.values()),
            queue=queue, historical=historical, alerts=alerts,
            read_only=True, refresh_seconds=5,
            stage_policy={'screen':'Complete physical workload, provisional checks; omits finite-difference gradient sanity check and strict saved-array comparison.',
                'full':'Official full benchmark plus separate strict saved-array / all-gradient comparison.',
                'objective':'Minimize complete first-run time, including imports/setup, compilation, execution and transfer.',
                'pareto':'Same-cohort valid full results only. Exact observed Pareto membership is separate from noise-qualified progress.',
                'expansion':'Coordinator freezes a new round after reviewed guidance; frozen per-lane stall_limit applies (default 3). No automatic budget extensions.'}))


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
            elif path in ('/', '/index.html', '/app.js', '/style.css'):
                name = 'index.html' if path == '/' else path[1:]
                try:
                    body = (assets/name).read_bytes()
                except OSError:
                    self.send_error(404)
                    return
                mime = {'html':'text/html', 'js':'text/javascript', 'css':'text/css'}[name.rsplit('.',1)[1]]+'; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True, help='Main repository containing .lab state')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--sync-remote', action='store_true', help='Poll AMD via existing SSH; list/show only, no submissions')
    parser.add_argument('--host', default='amd-hackathon')
    parser.add_argument('--root', default='/workspace/feyer-lab')
    args = parser.parse_args()
    obs = Observatory(args.repo, args.sync_remote, args.host, args.root)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(obs))
    server.daemon_threads = True
    if args.sync_remote:
        threading.Thread(target=obs.poll_remote, daemon=True).start()
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
