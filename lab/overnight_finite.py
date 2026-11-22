"""Tiny frozen-menu enumeration using the serial dual benchmark runner.

Every request is one fresh checkout, both full official workloads, and the full
14-case generalization check. Results remain provisional: no model calls, no
automatic winner, and no pooling distinct SHAs into a fictional repeated run.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time
import uuid

from .dual_benchmark_worker import CASES
from .overnight_client import Client, immutable
from .overnight_publish import Publisher
from .overnight_search import exclusive_lock, git, write_json
from .topology_tuning import render, sources, validate_manifest, verify_parent


INITIAL_SEED = '53f38d342c3228c052785e8c9d63b6ce9c832dd1'


def hashed(value):
    return hashlib.sha256(immutable(value)).hexdigest()


def scientifically_eligible(feedback):
    evaluation = feedback.get('evaluation', {})
    general = evaluation.get('generalization', {})
    checks = evaluation.get('checks', [])
    # Pristine differences are retained; no NEW seed-relative failures allowed.
    return (feedback.get('status') == 'completed' and feedback.get('official_passed') is True and len(checks) == 2
            and {c.get('setup') for c in checks} == {'grid', 'aligo'}
            and all(c.get('returncode') == 0 and c.get('failure') is None
                    and c.get('official', {}).get('passed') is True
                    and c.get('artifacts', {}).get('passed') is True
                    and c.get('strict_comparisons', {}).get('initial_seed', {}).get('passed') is True for c in checks)
            and general.get('comparisons', {}).get('initial_seed', {}).get('passed') is True
            and [c.get('case') for c in general.get('comparisons', {}).get('initial_seed', {}).get('cases', [])] == list(CASES)
            and all(c.get('passed') is True for c in general.get('comparisons', {}).get('initial_seed', {}).get('cases', []))
            and general.get('artifacts', {}).get('passed') is True
            and general.get('returncode') == 0 and general.get('failure') is None)


def timing(feedback, setup):
    values = feedback.get('evaluation', {}).get('timings', {}).get(setup, {}).get('fresh_process_seconds', [])
    if len(values) != 1 or type(values[0]) not in (float, int) or not math.isfinite(values[0]) or values[0] <= 0:
        raise ValueError('Screen requires exactly one finite fresh-process time per setup')
    return values[0]


def select_finalist(rows, baseline_id):
    baseline = next((row for row in rows if row['choice_id'] == baseline_id), None)
    if baseline is None or not scientifically_eligible(baseline['feedback']):
        return None
    base_grid, base_aligo = (timing(baseline['feedback'], s) for s in ('grid', 'aligo'))
    candidates = [row for row in rows if row['choice_id'] != baseline_id
                  and scientifically_eligible(row['feedback'])
                  and timing(row['feedback'], 'grid') <= base_grid - max(.003, .005 * base_grid)
                  and timing(row['feedback'], 'aligo') <= base_aligo - max(.003, .005 * base_aligo)]
    return min(candidates, key=lambda row: timing(row['feedback'], 'grid'))['choice_id'] if candidates else None


def balanced_plan(baseline, finalist, pairs):
    # Alternating AB/BA prevents every candidate being second in time/order.
    return [{'pair': index + 1, 'order': order, 'choice_id': choice}
            for index in range(pairs)
            for order, choice in enumerate((baseline, finalist) if index % 2 == 0 else (finalist, baseline))]


class Controller:
    def __init__(self, args, client=None, publisher=None, clock=time.time):
        self.args, self.clock = args, clock
        self.repo = Path(args.repo).resolve()
        self.directory = Path(args.state_dir).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'state.json'
        self.manifest = json.loads(Path(args.manifest).read_text())
        self.manifest_digest = validate_manifest(self.manifest)
        self.config = json.loads(Path(args.client_config).read_text())
        self.config.update(fresh_process_repetitions=1, source_review_command=None)
        self.client = client or Client(self.config)
        self.publisher = publisher or Publisher(self.config['publisher_worktree'], self.config['evidence_root'])
        self.state = None

    def save(self):
        self.state['observed_at'] = self.clock()
        write_json(self.path, self.state)

    def initialize(self):
        if self.args.deadline_unix != self.config['deadline_unix']:
            raise ValueError('Campaign deadline must match trusted client configuration')
        if self.args.max_jobs < len(self.manifest['legal']) + 2 * self.args.confirmation_pairs:
            raise ValueError('Job budget must reserve all screens plus declared paired confirmation')
        gate = json.loads(Path(self.args.start_gate).read_text())
        if (gate.get('ready') is not True or gate.get('deadline_unix') != self.args.deadline_unix
                or gate.get('seed_sha') != self.manifest['parent_sha']):
            raise ValueError('Parent confirmation has not supplied an explicit start gate')
        receipt_raw = Path(gate['seed_receipt_path']).read_bytes()
        review_raw = Path(gate['source_review_path']).read_bytes()
        receipt, reviewed = json.loads(receipt_raw), json.loads(review_raw)
        reviewed = reviewed.get('source_review', reviewed)
        general = receipt.get('generalization', {})
        if (receipt.get('candidate_sha') != self.manifest['parent_sha']
                or receipt.get('admission', {}).get('promotion_ready') is not True
                or not all(receipt.get('benchmarks', {}).get(s, {}).get('passed') is True for s in ('grid', 'aligo'))
                or general.get('case_count') != 14 or general.get('seed_comparison_passed') is not True
                or general.get('all_finite') is not True or general.get('inputs_identical') is not True
                or general.get('new_failures') != []):
            raise ValueError('Menu seed lacks complete dual/generalization admission')
        if (reviewed.get('schema_version') != 'feyer-local-source-review-v1'
                or reviewed.get('parent_sha') != INITIAL_SEED
                or reviewed.get('approved') is not True or reviewed.get('candidate_sha') != self.manifest['parent_sha']
                or reviewed.get('scope') != 'no-fixture-specialization-and-integrity'
                or reviewed.get('review_kind') != 'local-independent-source-and-integrity'
                or reviewed.get('reviewer') != 'collaborating-agent:/root/dual_evaluator'):
            raise ValueError('Menu seed lacks exact independent source approval')
        review_diff = git(self.repo, 'diff', reviewed['parent_sha'], self.manifest['parent_sha'], '--', 'differometor')
        if hashlib.sha256(review_diff.encode()).hexdigest() != reviewed.get('diff_sha256'):
            raise ValueError('Local source review does not bind the exact simulator delta')
        verify_parent(self.repo, self.manifest)
        fixed = {'name': self.args.name, 'manifest_digest': self.manifest_digest,
                 'config_digest': hashed(self.config), 'deadline_unix': self.args.deadline_unix,
                 'max_jobs': self.args.max_jobs, 'confirmation_pairs': self.args.confirmation_pairs,
                 'seed_receipt_sha256': hashlib.sha256(receipt_raw).hexdigest(),
                 'seed_review_sha256': hashlib.sha256(review_raw).hexdigest()}
        if self.path.exists():
            state = json.loads(self.path.read_text())
            if not self.args.resume or any(state.get(k) != v for k, v in fixed.items()):
                raise ValueError('Resume requires identical frozen menu, configuration and budget')
            self.state = state
        else:
            if self.args.resume:
                raise ValueError('No controller exists to resume')
            self.state = {**fixed, 'schema_version': 'feyer-overnight-finite-v1', 'status': 'preparing',
                          'started_at': self.clock(), 'choices': [], 'screens': [], 'confirmations': [],
                          'plan': None, 'active_request': None, 'job_count': 0,
                          'policy': {'selector': 'complete enumeration', 'promotion': 'disabled',
                                     'fresh_process_repetitions_per_request': 1,
                                     'full_official_setups': ['grid', 'aligo'], 'generalization_cases': 14,
                                     'finalist_threshold_each_setup': 'at least max(3 ms, 0.5%) below default single sample; still provisional',
                                     'timing_scope': 'provisional cold-checkout single samples; separate setup objectives'}}
            choices = [self.manifest['defaults']] + [x for x in self.manifest['legal'] if x != self.manifest['defaults']]
            for index, parameters in enumerate(choices):
                identity = f'choice-{index:02d}'
                self.state['choices'].append({'id': identity, 'parameters': parameters,
                    'branch': f'explore/{self.args.name}/{identity}',
                    'worktree': str(self.directory / 'worktrees' / identity),
                    'source_hashes': {p: hashlib.sha256(s.encode()).hexdigest() for p, s in render(self.manifest, parameters).items()}})
            write_json(self.directory / 'frozen-manifest.json', self.manifest)
            write_json(self.directory / 'client-config.json', self.config)
        self.save()

    def prepare_choice(self, choice):
        path = Path(choice['worktree'])
        parent = self.manifest['parent_sha']
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-b', choice['branch'], str(path), parent],
                           check=True, timeout=120, stdout=subprocess.PIPE)
        if git(path, 'branch', '--show-current') != choice['branch']:
            raise ValueError('Finite-choice branch changed externally')
        head = git(path, 'rev-parse', 'HEAD')
        subject = f'Finite tuning {self.args.name} {choice["id"]} {self.manifest_digest[:12]}'
        if choice.get('sha'):
            if head != choice['sha'] or git(path, 'status', '--porcelain'):
                raise ValueError('Committed finite choice changed externally')
        elif head == parent:
            current = sources(path, parent)
            target = render(self.manifest, choice['parameters'])
            dirty = set(git(path, 'diff', '--name-only', 'HEAD').splitlines())
            untracked = git(path, 'ls-files', '--others', '--exclude-standard').splitlines()
            if untracked or not dirty <= set(target):
                raise ValueError('Unexpected edits in owned finite-choice worktree')
            for name, text in target.items():
                dest = path / name
                if dest.is_symlink() or not dest.is_file():
                    raise ValueError('Source target must remain a regular file')
                existing = dest.read_text()
                if existing not in (current[name], text):
                    raise ValueError('Interrupted materialization contains unrelated source')
                if existing != text:
                    dest.write_text(text)
            changed = git(path, 'diff', '--name-only', 'HEAD').splitlines()
            if changed:
                git(path, 'add', '--', *changed)
                git(path, 'commit', '-m', subject)
                head = git(path, 'rev-parse', 'HEAD')
        elif git(path, 'rev-parse', 'HEAD^') != parent or git(path, 'log', '-1', '--format=%s') != subject:
            raise ValueError('Unexpected commit while recovering materialization')
        actual = {p: hashlib.sha256(s.encode()).hexdigest() for p, s in sources(path, head).items()}
        if actual != choice['source_hashes'] or git(path, 'status', '--porcelain'):
            raise ValueError('Committed finite choice differs from frozen renderer')
        choice['sha'] = head
        self.save()
        self.push_choice(choice)
        choice['published'] = True
        self.save()

    def push_choice(self, choice):
        subprocess.run(['git', '-C', choice['worktree'], '-c', 'credential.helper=',
                        '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin',
                        'HEAD:refs/heads/' + choice['branch']], check=True, timeout=120)

    def evaluate(self, choice, phase, pairing=None):
        active = self.state.get('active_request')
        if active is None:
            if git(choice['worktree'], 'rev-parse', 'HEAD') != choice['sha'] or git(choice['worktree'], 'status', '--porcelain'):
                raise ValueError('Committed finite choice changed externally before dispatch')
            if self.clock() >= self.args.deadline_unix or self.state['job_count'] >= self.args.max_jobs:
                return False
            request = {'schema_version': 'feyer-overnight-evaluation-v1', 'request_id': uuid.uuid4().hex,
                       'sha': choice['sha'], 'parent_sha': self.manifest['parent_sha'], 'branch': choice['branch'],
                       'worktree': choice['worktree'], 'session': self.args.name, 'lane': 0,
                       'deadline_unix': self.args.deadline_unix, 'requires_source_review': True,
                       'hypothesis': 'Frozen solver implementation tuning; physics and refinement unchanged'}
            active = {'request': request, 'choice_id': choice['id'], 'phase': phase, 'pairing': pairing}
            self.state['active_request'] = active
            self.state['job_count'] += 1
            self.save()  # Durable identity precedes every external submission.
        elif active['choice_id'] != choice['id'] or active['phase'] != phase or active['pairing'] != pairing:
            raise ValueError('Pending request does not match frozen dispatch plan')
        feedback = self.client.run(active['request'])
        if feedback.get('request_id') != active['request']['request_id'] or feedback.get('sha') != choice['sha']:
            raise ValueError('Evaluator feedback identity differs')
        if feedback.get('status') not in ('completed', 'failed', 'blocked', 'expired', 'interrupted'):
            raise RuntimeError('Evaluation remains pending; resume same request')
        evaluation = feedback.get('evaluation', {})
        record = {**active, 'feedback': feedback, 'status': 'provisional', 'promoted': False,
                  'execution_wall_seconds': ((evaluation['finished_at'] - evaluation['started_at'])
                      if evaluation.get('started_at') and evaluation.get('finished_at') else None),
                  'job_total_seconds': ((evaluation['finished_at'] - evaluation['registered_at'])
                      if evaluation.get('registered_at') and evaluation.get('finished_at') else None),
                  'official_first_run_seconds': evaluation.get('timings', {})}
        self.state['screens' if phase == 'screen' else 'confirmations'].append(record)
        self.state['active_request'] = None
        self.save()
        return True

    def publish_summary(self):
        # This is a control-branch report only. Never write CURRENT_BEST or mark admission.
        prefix = 'experiments/campaigns/' + self.args.name
        if self.state.get('summary_publication', {}).get('published') is True:
            return
        if not self.state.get('summary_payload'):
            summary = {**self.state, 'promoted': False, 'note': 'Preliminary finite-menu experiment. Parent must review paired evidence and source.'}
            self.state['summary_payload'] = summary
            self.save()
        summary = self.state['summary_payload']
        with self.publisher.locked():
            pending = self.publisher._recover()
            if pending and pending.get('published') is not True:
                raise RuntimeError('Control publication awaits earlier outbox push')
            transaction = self.state.get('summary_transaction')
            if transaction is None:
                transaction = uuid.uuid4().hex
                self.state['summary_transaction'] = transaction
                self.save()
            result = pending if pending and pending.get('evaluation_id') == transaction else self.publisher._submit(transaction, {
                prefix + '/manifest.json': json.dumps(self.manifest, indent=2, allow_nan=False).encode() + b'\n',
                prefix + '/results.json': json.dumps(summary, indent=2, allow_nan=False).encode() + b'\n'})
        if result.get('published') is not True:
            raise RuntimeError('Control report push remains pending')
        self.state['summary_publication'] = result
        self.save()

    def run(self):
        with exclusive_lock(self.directory / 'controller.lock'):
            self.initialize()
            for choice in self.state['choices']:
                if any(row['choice_id'] == choice['id'] for row in self.state['screens']):
                    continue
                if self.clock() >= self.args.deadline_unix and not self.state.get('active_request'):
                    break
                self.state['status'] = 'screening'
                if not choice.get('published'):
                    self.prepare_choice(choice)
                if not self.evaluate(choice, 'screen'):
                    break
            if len(self.state['screens']) == len(self.state['choices']) and self.state['plan'] is None:
                finalist = select_finalist(self.state['screens'], self.state['choices'][0]['id'])
                self.state['selected_finalist'] = finalist
                self.state['selection_outcome'] = ('provisional_finalist_for_paired_confirmation' if finalist
                    else 'no_screen_candidate_meets_both_setup_thresholds')
                self.state['plan'] = balanced_plan(self.state['choices'][0]['id'], finalist, self.args.confirmation_pairs) if finalist else []
                self.save()
            for pairing in self.state['plan'] or []:
                if any(row['pairing'] == pairing for row in self.state['confirmations']):
                    continue
                if self.clock() >= self.args.deadline_unix and not self.state.get('active_request'):
                    break
                choice = next(c for c in self.state['choices'] if c['id'] == pairing['choice_id'])
                self.state['status'] = 'confirming'
                if not self.evaluate(choice, 'confirmation', pairing):
                    break
            complete = (len(self.state['screens']) == len(self.state['choices']) and self.state['plan'] is not None
                        and len(self.state['confirmations']) == len(self.state['plan']))
            self.state['status'] = 'complete' if complete else 'budget_exhausted'
            self.save()
            self.publish_summary()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'manifest', 'client-config', 'state-dir', 'start-gate', 'name'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--deadline-unix', type=float, required=True)
    p.add_argument('--max-jobs', type=int, default=16)
    p.add_argument('--confirmation-pairs', type=int, choices=(3, 5), default=5)
    p.add_argument('--resume', action='store_true')
    args = p.parse_args(argv)
    if not re.fullmatch('[a-z0-9][a-z0-9_-]{0,60}', args.name):
        p.error('name must be a safe campaign identifier')
    if not math.isfinite(args.deadline_unix) or args.deadline_unix <= 0 or not 1 <= args.max_jobs <= 16:
        p.error('Deadline and job budget must be finite positive values')
    Controller(args).run()


if __name__ == '__main__':
    main()
