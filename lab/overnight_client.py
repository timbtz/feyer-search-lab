"""Trusted SSH hook for durable dual-benchmark requests and evidence publication.

Configuration is operator-owned. Input comes from the local supervisor; only the
small validated runner schema crosses into the AMD runner. No legacy queue calls.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import time

from .overnight_search import TERMINAL, git, registry_lock, write_json

SEED = '53f38d342c3228c052785e8c9d63b6ce9c832dd1'


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def immutable(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def atomic_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.download')
    with temp.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)
    fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Unsafe remote evidence path')
    return str(path)


def validate_request(request, config):
    if not isinstance(request, dict):
        raise ValueError('Request must be an object')
    if not re.fullmatch(r'[0-9a-f]{32}', str(request.get('request_id', ''))):
        raise ValueError('request_id must be UUID hex')
    if not re.fullmatch(r'[0-9a-f]{40}', str(request.get('sha', ''))):
        raise ValueError('sha must be exact lowercase commit')
    deadline = request.get('deadline_unix')
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline != config['deadline_unix']:
        raise ValueError('Request does not match campaign deadline')
    for key in ('branch', 'session'):
        if not isinstance(request.get(key), str) or not request[key] or '\x00' in request[key]:
            raise ValueError('Missing identity ' + key)
    if type(request.get('lane')) is not int or request['lane'] not in (0, 1):
        raise ValueError('Invalid lane')
    worktree = Path(request.get('worktree', '')).resolve()
    if not worktree.is_dir():
        raise ValueError('Worktree does not exist')
    if git(worktree, 'branch', '--show-current') != request['branch']:
        raise ValueError('Candidate branch mismatch')
    if git(worktree, 'rev-parse', request['sha'] + '^{commit}') != request['sha']:
        raise ValueError('Candidate missing locally')
    subprocess.run(['git', '-C', str(worktree), 'merge-base', '--is-ancestor', SEED, request['sha']],
                   check=True, timeout=30)
    return request


def runner_request_for(request):
    result = {key: request[key] for key in ('request_id', 'sha', 'deadline_unix', 'branch', 'session')}
    result.update(lane=str(request['lane']), schema_version='feyer-dual-benchmark-request-v1',
                  timeout_seconds=900, fresh_process_repetitions=3, run_generalization=True)
    return result


class Client:
    def __init__(self, config, remote=None, publisher=None, clock=time.time, sleep=time.sleep):
        self.config, self.clock, self.sleep = config, clock, sleep
        for key in ('remote_runtime', 'remote_root', 'mirror'):
            if not PurePosixPath(config[key]).is_absolute() or '\x00' in config[key]:
                raise ValueError('Trusted remote paths must be absolute')
        if not re.fullmatch(r'[A-Za-z0-9_.@-]+', config['ssh_host']):
            raise ValueError('Invalid SSH host')
        self.evidence = Path(config['evidence_root']).resolve()
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.remote = remote or self._remote
        self.publisher = publisher

    def _remote(self, argv, stdin=None):
        return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                                        self.config['ssh_host'], shlex.join(argv)], input=stdin,
                                       timeout=self.config.get('command_timeout', 120), stderr=subprocess.PIPE)

    def runner_argv(self, command, identity=None):
        args = [self.config.get('remote_python', '/workspace/venv-feyer/bin/python'), '-m',
                'lab.dual_benchmark_worker', '--root', self.config['remote_root'], '--mirror', self.config['mirror']]
        for name in ('reference_root', 'seed_reference_root', 'generalization_harness',
                     'generalization_reference', 'generalization_seed'):
            if self.config.get(name):
                args += ['--' + name.replace('_', '-'), self.config[name]]
        for path in self.config.get('lock_states', []):
            args += ['--lock-state', path]
        args += [command]
        if identity:
            args += ['--request-id', identity]
        return args

    def call_runner(self, command, identity=None, value=None):
        args = self.runner_argv(command, identity)
        script = 'import os,sys; os.chdir(sys.argv[1]); os.execv(sys.argv[2],sys.argv[2:])'
        raw = self.remote(['python3', '-c', script, self.config['remote_runtime'], *args],
                          immutable(value) if value is not None else None)
        return json.loads(raw)

    def launch(self, identity):
        # Runner has its own nonblocking global lock and terminal-state replay guard.
        script = ('import os,sys,subprocess,pathlib; os.chdir(sys.argv[1]); '
                  'p=pathlib.Path(sys.argv[2]); p.parent.mkdir(parents=True,exist_ok=True); '
                  'f=p.open("ab"); subprocess.Popen(["nohup",*sys.argv[3:]],stdin=subprocess.DEVNULL,'
                  'stdout=f,stderr=f,start_new_session=True,close_fds=True); print("launched")')
        log = str(PurePosixPath(self.config['remote_root']) / 'incoming' / (identity + '.runner.log'))
        self.remote(['python3', '-c', script, self.config['remote_runtime'], log, *self.runner_argv('run', identity)])

    def upload(self, request, directory):
        identity, source = request['request_id'], request['sha']
        if source == SEED:
            script = ('import subprocess,sys; m,s,r=sys.argv[1:]; '
                      'v=subprocess.check_output(["git","--git-dir",m,"rev-parse",s+"^{commit}"],text=True).strip(); '
                      'assert v==s; subprocess.run(["git","--git-dir",m,"update-ref",r,s],check=True)')
            self.remote(['python3', '-c', script, self.config['mirror'], source, 'refs/candidates/overnight-' + identity])
            return {'seed_already_staged': True}
        bundle = directory / 'candidate.bundle'
        ref = 'refs/lab/overnight-export/' + identity
        git(request['worktree'], 'update-ref', ref, source)
        try:
            if bundle.exists():
                bundle.unlink()  # Reproducible transport only; scientific artifacts remain immutable.
            git(request['worktree'], 'bundle', 'create', str(bundle), ref, '^' + SEED)
        finally:
            git(request['worktree'], 'update-ref', '-d', ref, source)
        raw = bundle.read_bytes()
        hashed = sha256(raw)
        script = '''import sys,pathlib,hashlib,subprocess,os
root,mirror,identity,expected,source,ref=sys.argv[1:]
incoming=pathlib.Path(root)/'incoming'; incoming.mkdir(parents=True,exist_ok=True)
path=incoming/(identity+'.bundle'); temporary=incoming/(identity+'.upload')
data=sys.stdin.buffer.read()
if hashlib.sha256(data).hexdigest()!=expected: raise ValueError('Bundle upload digest mismatch')
temporary.write_bytes(data); os.replace(temporary,path)
subprocess.run(['git','--git-dir',mirror,'bundle','verify',str(path)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
subprocess.run(['git','--git-dir',mirror,'fetch',str(path),ref+':refs/candidates/overnight-'+identity],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
actual=subprocess.check_output(['git','--git-dir',mirror,'rev-parse','refs/candidates/overnight-'+identity],text=True).strip()
if actual!=source: raise ValueError('Fetched commit mismatch')
print(expected)
'''
        received = self.remote(['python3', '-c', script, self.config['remote_root'], self.config['mirror'],
                                identity, hashed, source, ref], raw).decode().strip()
        if received != hashed:
            raise ValueError('Remote upload acknowledgement mismatch')
        bundle.unlink()
        return {'bundle_sha256': hashed, 'bytes': len(raw)}

    def fetch_file(self, path, expected=None):
        rel = relative(path)
        script = '''import pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve(); path=(root/sys.argv[2]).resolve()
if root not in path.parents or not path.is_file() or path.stat().st_size>16000000: raise ValueError('Unsafe or oversized evidence')
sys.stdout.buffer.write(path.read_bytes())
'''
        raw = self.remote(['python3', '-c', script, self.config['remote_root'], rel])
        if expected is not None and sha256(raw) != expected:
            raise ValueError('Remote evidence digest mismatch: ' + rel)
        target = self.evidence / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('Immutable evidence collision: ' + rel)
        atomic_bytes(target, raw)
        return target

    def collect(self, state, request, directory):
        self.collect_logs(request, directory)
        if state.get('receipt_path'):
            receipt_path = self.fetch_file(state['receipt_path'], state.get('receipt_sha256'))
            receipt = json.loads(receipt_path.read_bytes())
            if receipt.get('evaluation_id') != request['request_id'] or receipt.get('candidate_sha') != request['sha']:
                raise ValueError('Receipt identity mismatch')
            for benchmark in receipt.get('benchmarks', {}).values():
                for sample in benchmark.get('samples', []):
                    self.fetch_file(sample['report_path'], sample['report_sha256'])
            gen = receipt.get('generalization', {})
            if gen.get('comparison_path'):
                self.fetch_file(gen['comparison_path'], gen['comparison_sha256'])
        else:
            # An infrastructure failure may precede reports; still publish an explicit failure receipt.
            receipt = {'schema_version': 'feyer-overnight-evaluation-v1', 'evaluation_id': request['request_id'],
                       'candidate_sha': request['sha'], 'benchmarks': {}, 'generalization': {},
                       'admission': {'promotion_ready': False, 'candidate_sha': request['sha']},
                       'failure': state, 'caveats': ['Evaluation failed before publication receipt was created.']}
            receipt_path = directory / 'failure-receipt.json'
            write_json(receipt_path, receipt)
        raw_sha = sha256(receipt_path.read_bytes())
        # The raw receipt is retained byte-for-byte; local review decorates a distinct derived receipt.
        derived = dict(receipt)
        derived.update(raw_runner_receipt_sha256=raw_sha, original_evaluation_id=request['request_id'])
        review = self.review(request, state, directory, receipt_path)
        if review is not None:
            derived['source_review'] = review
        else:
            derived['requires_source_review'] = request['sha'] != SEED
        path = directory / 'admission-receipt.json'
        if path.exists() and json.loads(path.read_text()) != derived:
            raise ValueError('Admission receipt changed after first publication attempt')
        write_json(path, derived)
        return path

    def collect_logs(self, request, directory):
        script = '''import pathlib,sys,hashlib,json,os
root=pathlib.Path(sys.argv[1]).resolve(); base=root/'requests'/sys.argv[2]; result=[]; total=0
for folder,dirs,files in os.walk(base):
 dirs[:]=[d for d in dirs if d not in ('code','.git')]
 for name in files:
  path=pathlib.Path(folder)/name
  if not name.endswith('.log') or path.is_symlink(): continue
  size=path.stat().st_size
  if size>16000000 or total+size>32000000: continue
  data=path.read_bytes(); total+=len(data)
  result.append({'path':str(path.relative_to(root)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
print(json.dumps(result))
'''
        manifest = json.loads(self.remote(['python3', '-c', script, self.config['remote_root'], request['request_id']]))
        for item in manifest:
            path = relative(item['path'])
            if not path.startswith('requests/' + request['request_id'] + '/') or not path.endswith('.log'):
                raise ValueError('Unexpected log manifest path')
            self.fetch_file(path, item['sha256'])
        write_json(directory / 'log-manifest.json', manifest)

    def review(self, request, state, directory, receipt_path):
        saved = directory / 'source-review.json'
        if saved.exists():
            return json.loads(saved.read_text())
        command = self.config.get('source_review_command')
        receipt = json.loads(receipt_path.read_text())
        if (not command or request['sha'] == SEED
                or receipt.get('admission', {}).get('promotion_ready') is not True):
            return None
        proposal_parent = request.get('parent_sha')
        if not re.fullmatch(r'[0-9a-f]{40}', str(proposal_parent)):
            raise ValueError('Source review requires exact parent')
        parent = SEED  # Review the complete simulator delta, including inherited candidate edits.
        # Hash the exact stored packet, matching the supervisor's canonical stripped diff.
        raw = subprocess.check_output(['git', '-C', request['worktree'], 'diff', parent, request['sha'], '--', 'differometor'], timeout=60).strip()
        diff_path = directory / 'source.diff'
        atomic_bytes(diff_path, raw)
        payload = {'candidate_sha': request['sha'], 'parent_sha': parent,
                   'proposal_parent_sha': proposal_parent,
                   'source_diff_sha256': sha256(raw), 'source_diff_path': str(diff_path),
                   'evaluation_receipt_path': str(receipt_path), 'worktree': request['worktree'],
                   'evidence_root': str(self.evidence), 'campaign_dir': self.config['campaign_dir'],
                   'deadline_unix': request['deadline_unix']}
        # The reviewed hook owns bounded model dispatch and durable failure receipts.
        process = subprocess.run(shlex.split(command), input=immutable(payload), capture_output=True,
                                 timeout=self.config.get('source_review_timeout', 600))
        (directory / 'source-review.stderr.log').write_bytes(process.stderr)
        if process.returncode:
            raise RuntimeError('Source review hook failed; same identity retained for recovery')
        result = json.loads(process.stdout)
        review = result['source_review']
        for key, expected in (('candidate_sha', request['sha']), ('parent_sha', parent),
                              ('diff_sha256', sha256(raw))):
            if review.get(key) != expected:
                raise ValueError('Review identity mismatch: ' + key)
        for key in ('artifact_path', 'diff_path'):
            path = (self.evidence / relative(review[key])).resolve()
            if self.evidence not in path.parents or not path.is_file():
                raise ValueError('Review artifact is outside trusted evidence root')
        if sha256((self.evidence / review['artifact_path']).read_bytes()) != review['artifact_sha256']:
            raise ValueError('Review artifact hash mismatch')
        write_json(saved, review)
        return review

    def publish(self, path):
        if self.publisher is None:
            from .overnight_publish import Publisher
            self.publisher = Publisher(self.config['publisher_worktree'], self.evidence)
        result = self.publisher.publish(path)
        if result.get('published') is not True:
            raise RuntimeError('Publication pending; retry same evaluation identity')
        return result

    def run(self, request):
        validate_request(request, self.config)
        identity = request['request_id']
        directory = self.evidence / 'client' / identity
        directory.mkdir(parents=True, exist_ok=True)
        with registry_lock(directory / 'client.lock'):
            path = directory / 'client-state.json'
            config_digest = sha256(immutable(self.config))
            if path.exists():
                state = json.loads(path.read_text())
                if state['request'] != request or state['config_digest'] != config_digest:
                    raise ValueError('Durable request or trusted configuration changed')
                if state.get('feedback'):
                    return state['feedback']
            else:
                if self.clock() >= request['deadline_unix']:
                    return {**request, 'status': 'expired', 'official_passed': False, 'reason': 'No new admission after deadline'}
                state = {'request': request, 'config_digest': config_digest, 'phase': 'created'}
                write_json(path, state)
            if state['phase'] == 'created':
                state['upload'] = self.upload(request, directory)
                state['phase'] = 'uploaded'
                write_json(path, state)
            runner_request = runner_request_for(request)
            if state['phase'] == 'uploaded':
                # Registration itself is idempotent; this can safely replay after a lost SSH response.
                remote = self.call_runner('register', value=runner_request)
                state.update(phase='registered', runner_request=runner_request)
                write_json(path, state)
            else:
                remote = self.call_runner('status', identity)
            while True:
                if remote.get('request_id') != identity or remote.get('sha') != request['sha']:
                    raise ValueError('Runner status identity mismatch')
                write_json(directory / 'latest-status.json', remote)
                if remote.get('status') in TERMINAL:
                    if type(remote.get('official_passed')) is bool and not remote.get('receipt_path'):
                        raise RuntimeError('Terminal benchmark state is awaiting its durable publication receipt')
                    break
                if remote.get('status') not in ('queued', 'running'):
                    raise ValueError('Unknown runner status')
                if remote['status'] == 'queued' or self.clock() - state.get('last_owner_probe', 0) >= 60:
                    # run() is a no-op while inherited execution locks are held. Once an
                    # orphan releases them, run() marks its old running state interrupted;
                    # it never re-executes that request. status() alone cannot recover it.
                    self.launch(identity)
                    state['last_owner_probe'] = self.clock()
                    write_json(path, state)
                if self.clock() > request['deadline_unix'] + 900:
                    return {'request_id': identity, 'sha': request['sha'], 'status': remote['status'],
                            'reason': 'Admitted request still pending; identity preserved for operator recovery'}
                self.sleep(self.config.get('poll_seconds', 10))
                remote = self.call_runner('status', identity)
            state['terminal_state'] = remote
            write_json(path, state)
            receipt_path = self.collect(remote, request, directory)
            publication = self.publish(receipt_path)
            feedback = {'request_id': identity, 'sha': request['sha'], 'status': remote['status'],
                        'official_passed': remote.get('official_passed') is True,
                        'evaluation': remote, 'publication': publication,
                        'admission_receipt': str(receipt_path),
                        'source_review': json.loads(receipt_path.read_text()).get('source_review'),
                        'confirmed_improvement': (publication.get('decision') or {}).get('promote') is True,
                        'universal_physics_claim': False}
            state.update(phase='published', feedback=feedback)
            write_json(path, state)
            return feedback


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args(argv)
    result = Client(json.loads(args.config.read_text())).run(json.load(sys.stdin))
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
