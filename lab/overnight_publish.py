"""Publish overnight search evidence on one dedicated control branch.

This module is a local operator, never an optimization-agent tool. The trusted
runner's publication receipt must live under the explicitly supplied evidence
root. Candidate code cannot nominate an alternative evidence root. Search
selection heuristics are not organizer judging rules.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
import uuid

CAMPAIGN = 'overnight-20261122'
BRANCH = 'control/' + CAMPAIGN
PREFIX = 'experiments/campaigns/' + CAMPAIGN
BEST = PREFIX + '/current-best.json'
POLICY = {'version': 'overnight-selection-v2', 'minimum_repetitions': 3,
          'large_minimum_absolute_gain_seconds': .003,
          'large_minimum_relative_gain': .005, 'aligo_maximum_ratio': 1.02,
          'maximum_relative_range': .10,
          'large_candidate_maximum_must_be_below_incumbent_minimum': True,
          'scope': 'Team search-selection heuristic, not organizer judging policy.'}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def git(worktree, *args):
    return subprocess.check_output(['git', '-C', str(worktree), *args], text=True,
                                   stderr=subprocess.STDOUT,
                                   timeout=120 if args and args[0] == 'push' else 30).strip()


def identifier(value):
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('evaluation_id must be a UUID') from exc
    return parsed.hex


def sha(value, length=40):
    if not isinstance(value, str) or len(value) != length or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Expected a lowercase immutable SHA')
    return value


def safe_read(root, path):
    root = Path(root).resolve(); path = Path(path)
    target = path if path.is_absolute() else root / path
    resolved = target.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError('Evidence must be a regular file under the trusted evidence root')
    return resolved.read_bytes()


def read_receipt(path, evidence_root):
    raw = safe_read(evidence_root, path)
    value = json.loads(raw)
    if value.get('schema_version') != 'feyer-overnight-evaluation-v1':
        raise ValueError('Unsupported trusted-runner publication schema')
    identifier(value.get('evaluation_id')); sha(value.get('candidate_sha'))
    return value, raw


def assess(receipt, current):
    """Fail closed; a false admission is evidence, not a publisher exception."""
    reasons = []; metrics = {}; timing_comparison = {}
    admission = receipt.get('admission', {})
    if admission.get('promotion_ready') is not True: reasons.append('runner_not_promotion_ready')
    if admission.get('candidate_sha') != receipt['candidate_sha']: reasons.append('admission_source_mismatch')
    if admission.get('comparison_cohort_passed') is not True: reasons.append('runner_comparison_cohort_rejected')
    general = receipt.get('generalization', {})
    if (general.get('case_count') != 14 or general.get('all_finite') is not True
            or general.get('inputs_identical') is not True
            or general.get('seed_comparison_passed') is not True):
        reasons.append('incomplete_generalization')
    if general.get('new_failures') != []: reasons.append('unresolved_new_failures')
    cohort = receipt.get('cohort_digest')
    try: sha(cohort, 64)
    except ValueError: reasons.append('missing_cohort')
    for setup in ('grid', 'aligo'):
        benchmark = receipt.get('benchmarks', {}).get(setup, {})
        samples = benchmark.get('samples', [])
        valid = isinstance(samples, list) and len(samples) >= 3
        values = []; hashes = set()
        for sample in samples if isinstance(samples, list) else []:
            seconds = sample.get('seconds')
            valid = valid and type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0
            valid = valid and sample.get('fresh_process') is True and sample.get('official_passed') is True
            valid = valid and sample.get('candidate_sha') == receipt['candidate_sha']
            try: hashes.add(sha(sample.get('report_sha256'), 64))
            except ValueError: valid = False
            if type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0: values.append(seconds)
        if not valid or len(hashes) != len(samples):
            reasons.append(setup + '_needs_three_distinct_fresh_official_runs'); continue
        median = statistics.median(values)
        metrics[setup] = {'samples_seconds': values, 'median_seconds': median,
                          'min_seconds': min(values), 'max_seconds': max(values),
                          'relative_range': (max(values) - min(values)) / median}
        if metrics[setup]['relative_range'] > POLICY['maximum_relative_range']:
            reasons.append(setup + '_unstable_timing')
    if current['status'] == 'seed_pending_fresh_calibration':
        if receipt['candidate_sha'] != current['candidate_sha']:
            reasons.append('seed_fresh_calibration_required')
    elif cohort != current.get('cohort_digest'):
        reasons.append('comparison_cohort_mismatch')
    seed_calibration = (current['status'] == 'seed_pending_fresh_calibration'
                        and receipt['candidate_sha'] == current['candidate_sha'])
    review = receipt.get('source_review', {})
    if not seed_calibration:
        valid_review = (review.get('approved') is True
                        and review.get('candidate_sha') == receipt['candidate_sha']
                        and review.get('scope') == 'no-fixture-specialization-and-integrity'
                        and all(isinstance(review.get(k), str) and review[k].strip() for k in
                                ('reviewer', 'provider', 'model', 'session_id', 'artifact_path', 'diff_path')))
        for key, length in [('parent_sha', 40), ('diff_sha256', 64), ('artifact_sha256', 64)]:
            try: sha(review.get(key), length)
            except ValueError: valid_review = False
        if not valid_review: reasons.append('requires_source_review')
    # Report independent timing objections even when source review is still
    # missing, so callers need not spend a model review on a clearly slower trial.
    if (current['status'] != 'seed_pending_fresh_calibration'
            and cohort == current.get('cohort_digest') and 'missing_cohort' not in reasons
            and set(metrics) == {'grid', 'aligo'}):
        old = current['metrics']; new = metrics
        threshold = max(.003, old['grid']['median_seconds'] * .005)
        if old['grid']['median_seconds'] - new['grid']['median_seconds'] < threshold:
            reasons.append('large_gain_below_selection_threshold')
        if new['aligo']['median_seconds'] > old['aligo']['median_seconds'] * 1.02:
            reasons.append('aligo_regression_over_two_percent')
        # Three samples and a small median shift are not a confidence interval.
        # This conservative observed-range heuristic prevents automatic promotion
        # when the apparent gain still falls within incumbent timing variation.
        incumbent_min = old['grid'].get('min_seconds')
        if type(incumbent_min) not in (int, float) or not math.isfinite(incumbent_min) or incumbent_min <= 0:
            reasons.append('incumbent_timing_range_unavailable')
        else:
            timing_comparison = {'incumbent_grid_min_seconds': incumbent_min,
                                 'candidate_grid_max_seconds': new['grid']['max_seconds'],
                                 'observed_ranges_nonoverlapping': new['grid']['max_seconds'] < incumbent_min}
            if not timing_comparison['observed_ranges_nonoverlapping']:
                reasons.append('large_first_run_ranges_overlap_requires_paired_evidence')
    return {'promote': not reasons, 'reasons': reasons, 'metrics': metrics,
            'policy': POLICY, 'timing_comparison': timing_comparison}


def caveat_summaries(previous, receipt):
    values = [c for c in previous if isinstance(c, str) and 'fresh dual calibration is pending' not in c]
    for value in receipt.get('inherited_caveats', []) + receipt.get('caveats', []):
        if isinstance(value, str): values.append(value)
        elif isinstance(value, dict):
            if 'generalization_pristine_comparison' in value:
                values.append('Generalization pristine-reference disagreements remain; see complete candidate receipt.')
            else:
                values.append(str(value.get('setup', 'Additional')) +
                              ' pristine-reference disagreements remain; see complete candidate receipt.')
    return list(dict.fromkeys(values))


def markdown(best):
    lines = ['# Current best submission', '',
             '**Status:** ' + best['status'], '',
             '**Exact simulator revision:** [' + best['candidate_sha'] + ']('
             + best['repository_url'] + '/tree/' + best['candidate_sha'] + ')', '',
             'The larger official benchmark is the primary objective. aLIGO is reported separately.',
             'This is the best admitted candidate in this campaign; it is not an official judging verdict.', '']
    for setup, metric in best.get('metrics', {}).items():
        lines.append(f"- {setup}: median {metric['median_seconds']:.9f} s; range "
                     f"{metric['min_seconds']:.9f}–{metric['max_seconds']:.9f} s.")
    lines += ['', '## Evidence and limitations', '',
              '- [Machine-readable current best](' + BEST + ')',
              '- [All candidate receipts](' + PREFIX + '/candidates)',
              '- Only exact-source, matching-cohort results with both official benchmarks and generalization admission can replace this record.']
    for caveat in best.get('caveats', []): lines.append('- ' + str(caveat))
    if best.get('record_path'): lines.append('- [Selected candidate evidence](' + best['record_path'] + ')')
    lines += ['', 'Search selection requires at least three fresh runs of each official benchmark, a large-case gain '
              'of at least max(3 ms, 0.5%), no more than 2% aLIGO regression, and relative timing range at most 10%. '
              'Under selection-v2, the candidate large-case maximum must also be strictly below the incumbent minimum. '
              'Overlapping candidates remain provisional for further paired investigation. Observed nonoverlap is not statistical proof. '
              'These are team heuristics, not organizer scoring rules. Failed and provisional trials remain in the candidate receipts.', '']
    return '\n'.join(lines).encode()


class Publisher:
    def __init__(self, worktree, evidence_root, repository_url='https://github.com/timbtz/feyer-search-lab', remote='origin'):
        self.worktree = Path(worktree).resolve(); self.evidence_root = Path(evidence_root).resolve()
        self.repository_url = repository_url.rstrip('/'); self.remote = remote
        if git(self.worktree, 'branch', '--show-current') != BRANCH:
            raise ValueError('Publisher requires dedicated branch ' + BRANCH)
        self.state = Path(git(self.worktree, 'rev-parse', '--absolute-git-dir')) / 'overnight-publisher'
        self.state.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def locked(self):
        with (self.state / 'publish.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def _push(self, transaction):
        if git(self.worktree, 'rev-parse', 'HEAD') != transaction['commit_sha']:
            raise ValueError('Publication branch moved while an outbox commit was pending')
        # Push exactly the current commit on our dedicated branch. A rejected push
        # remains a local outbox; never force or claim remote success.
        try:
            git(self.worktree, 'push', self.remote, 'HEAD:refs/heads/' + BRANCH)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            transaction['publication_status'] = 'pending_push'
            transaction['last_error'] = str(exc.output)[-2000:]
            atomic(self.state / 'pending.json', encoded(transaction))
            return {'published': False, 'publication_status': 'pending_push',
                    'commit_sha': transaction['commit_sha'], 'evaluation_id': transaction['evaluation_id']}
        receipt = {'published': True, 'publication_status': 'pushed',
                   'commit_sha': transaction['commit_sha'], 'evaluation_id': transaction['evaluation_id'],
                   'published_at': time.time(), 'decision': transaction.get('decision')}
        atomic(self.state / ('published-' + transaction['evaluation_id'] + '.json'), encoded(receipt))
        (self.state / 'pending.json').unlink(missing_ok=True)
        return receipt

    def _recover(self):
        pending = self.state / 'pending.json'
        if not pending.exists(): return None
        transaction = json.loads(pending.read_bytes())
        if not transaction.get('commit_sha'):
            head = git(self.worktree, 'rev-parse', 'HEAD')
            if head != transaction['base_commit']:
                if (git(self.worktree, 'rev-parse', 'HEAD^') != transaction['base_commit']
                        or git(self.worktree, 'log', '-1', '--format=%s') != 'Publish overnight evidence ' + transaction['evaluation_id']):
                    raise ValueError('Publication branch moved during transaction recovery')
            dirty = set()
            for args in [('diff', '--name-only'), ('diff', '--cached', '--name-only'),
                         ('ls-files', '--others', '--exclude-standard')]:
                dirty.update(git(self.worktree, *args).splitlines())
            if dirty - set(transaction['files']):
                raise ValueError('Unrelated edits prevent publication transaction recovery')
            for rel, value in transaction['files'].items():
                target = self.worktree / rel
                if '/candidates/' in rel and target.exists() and target.read_bytes() != value.encode():
                    raise ValueError('Immutable candidate artifact collision')
                atomic(target, value.encode())
            git(self.worktree, 'add', '--', *transaction['files'])
            if git(self.worktree, 'diff', '--cached', '--name-only'):
                git(self.worktree, 'commit', '-m', 'Publish overnight evidence ' + transaction['evaluation_id'])
            transaction['commit_sha'] = git(self.worktree, 'rev-parse', 'HEAD')
            transaction['publication_status'] = 'pending_push'
            atomic(pending, encoded(transaction))
        return self._push(transaction)

    def retry(self):
        with self.locked():
            return self._recover() or {'published': False, 'publication_status': 'nothing_pending'}

    def _submit(self, evaluation_id, files, decision=None):
        if git(self.worktree, 'status', '--porcelain'):
            raise ValueError('Dedicated publication worktree must be clean before starting a transaction')
        transaction = {'evaluation_id': evaluation_id, 'files': {k: v.decode() for k, v in files.items()},
                       'decision': decision, 'created_at': time.time(), 'commit_sha': None,
                       'base_commit': git(self.worktree, 'rev-parse', 'HEAD')}
        atomic(self.state / 'pending.json', encoded(transaction))
        return self._recover()

    def initialize(self, manifest_path):
        manifest_raw = Path(manifest_path).read_bytes(); manifest = json.loads(manifest_raw)
        with self.locked():
            pending = self._recover()
            if pending and not pending['published']: return pending
            target = self.worktree / BEST
            if target.exists():
                current = json.loads(target.read_bytes())
                if current['seed_sha'] != manifest['recommended_seed_sha']:
                    raise ValueError('Campaign already initialized with another seed')
                return {'published': True, 'publication_status': 'already_initialized',
                        'candidate_sha': current['candidate_sha']}
            metrics = {k: {x: v[x] for x in ('median_seconds', 'min_seconds', 'max_seconds')}
                       for k, v in manifest['official_evidence'].items()}
            best = {'schema_version': 'feyer-current-best-v1', 'candidate_sha': sha(manifest['recommended_seed_sha']),
                    'seed_sha': manifest['recommended_seed_sha'], 'status': 'seed_pending_fresh_calibration',
                    'repository_url': self.repository_url, 'metrics': metrics,
                    'caveats': manifest['extra_validation_notes'] + [manifest['timing_caveat'],
                              'Historical seed evidence is retained; current-cohort fresh dual calibration is pending.'],
                    'seed_manifest_sha256': digest(manifest_raw), 'policy': POLICY}
            return self._submit('seed-initialization', {BEST: encoded(best), 'CURRENT_BEST.md': markdown(best),
                         PREFIX + '/initial-seed-manifest.json': manifest_raw})

    def publish(self, receipt_path):
        receipt, raw = read_receipt(receipt_path, self.evidence_root)
        evaluation_id = identifier(receipt['evaluation_id'])
        with self.locked():
            pending = self._recover()
            if pending and not pending['published']: return pending
            record_path = PREFIX + '/candidates/' + evaluation_id + '/record.json'
            existing = self.worktree / record_path
            if existing.exists():
                recorded = json.loads(existing.read_bytes())
                if recorded['receipt_sha256'] != digest(raw):
                    raise ValueError('evaluation_id already exists with different evidence')
                if git(self.worktree, 'status', '--porcelain'):
                    raise ValueError('Existing publication record is not in a clean worktree')
                published = self.state / ('published-' + evaluation_id + '.json')
                prior = json.loads(published.read_bytes()) if published.exists() else {}
                if not prior.get('published'):
                    raise ValueError('Existing local record lacks a verified publication receipt')
                return {**prior, 'publication_status': 'already_published',
                        'evaluation_id': evaluation_id, 'decision': recorded['decision']}
            current = json.loads((self.worktree / BEST).read_bytes())
            decision = assess(receipt, current)
            files = {}; archived = []
            review = receipt.get('source_review', {})
            if review.get('artifact_path'):
                review_raw = safe_read(self.evidence_root, review['artifact_path'])
                if digest(review_raw) != review.get('artifact_sha256'):
                    raise ValueError('Source review artifact digest mismatch')
                reviewed = json.loads(review_raw)
                for key in ('approved', 'candidate_sha', 'parent_sha', 'diff_sha256',
                            'reviewer', 'provider', 'model', 'session_id', 'scope'):
                    if reviewed.get(key) != review.get(key):
                        raise ValueError('Source review artifact contradicts receipt')
                diff_raw = safe_read(self.evidence_root, review['diff_path'])
                if digest(diff_raw) != review.get('diff_sha256'):
                    raise ValueError('Source review diff digest mismatch')
                files[PREFIX + '/candidates/' + evaluation_id + '/source-review.json'] = review_raw
                files[PREFIX + '/candidates/' + evaluation_id + '/reviewed-source.diff'] = diff_raw
            for setup in ('grid', 'aligo'):
                for index, sample in enumerate(receipt.get('benchmarks', {}).get(setup, {}).get('samples', [])):
                    data = safe_read(self.evidence_root, sample['report_path'])
                    if digest(data) != sample['report_sha256']:
                        raise ValueError('Official report digest mismatch')
                    report = json.loads(data)
                    if (report.get('source', {}).get('commit') != receipt['candidate_sha']
                            or report.get('source', {}).get('modified') is not False):
                        raise ValueError('Official report source mismatch')
                    validation = report.get('validation', {})
                    if (validation.get('all_outputs_and_gradients_finite') is not True
                            or validation.get('upstream_sensitivity_check_passed') is not True
                            or validation.get('gradient_check', {}).get('passed') is not True):
                        if sample.get('official_passed') is True:
                            raise ValueError('Official PASS assertion contradicts archived report')
                    inputs = report.get('inputs', {})
                    if (inputs.get('frequency_count') != 101
                            or inputs.get('gradient_parameter_count') != (193 if setup == 'grid' else 29)):
                        raise ValueError('Official report workload mismatch')
                    if report.get('timing_seconds', {}).get('end_to_end') != sample['seconds']:
                        raise ValueError('Official report timing mismatch')
                    dest = PREFIX + '/candidates/' + evaluation_id + f'/{setup}-{index + 1}.json'
                    files[dest] = data; archived.append({'path': dest, 'sha256': digest(data),
                         'url': self.repository_url + '/blob/' + BRANCH + '/' + dest})
            record = {'schema_version': 'feyer-overnight-candidate-v1', 'evaluation_id': evaluation_id,
                      'candidate_sha': receipt['candidate_sha'], 'receipt_sha256': digest(raw),
                      'evaluator_receipt': receipt, 'decision': decision, 'official_reports': archived,
                      'code_url': self.repository_url + '/tree/' + receipt['candidate_sha'],
                      'previous_best_sha': current['candidate_sha'], 'recorded_at': time.time()}
            files[record_path] = encoded(record)
            files[PREFIX + '/candidates/' + evaluation_id + '/runner-receipt.json'] = raw
            if decision['promote']:
                best = {'schema_version': 'feyer-current-best-v1', 'candidate_sha': receipt['candidate_sha'],
                        'seed_sha': current['seed_sha'], 'status': 'admitted_campaign_best',
                        'repository_url': self.repository_url, 'metrics': decision['metrics'],
                        'cohort_digest': receipt['cohort_digest'], 'record_path': record_path,
                        'evaluation_id': evaluation_id, 'policy': POLICY,
                        'caveats': caveat_summaries(current['caveats'], receipt)}
                files[BEST] = encoded(best); files['CURRENT_BEST.md'] = markdown(best)
            return self._submit(evaluation_id, files, decision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'publish', 'retry'])
    parser.add_argument('--worktree', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    publisher = Publisher(args.worktree, args.evidence_root)
    if args.command == 'init':
        if not args.manifest: parser.error('init requires --manifest')
        result = publisher.initialize(args.manifest)
    elif args.command == 'publish':
        if not args.receipt: parser.error('publish requires --receipt')
        result = publisher.publish(args.receipt)
    else: result = publisher.retry()
    print(json.dumps(result, allow_nan=False))
    return 0 if result.get('published') or result['publication_status'] == 'nothing_pending' else 2


if __name__ == '__main__':
    raise SystemExit(main())
