"""Normalize trusted queue artifacts into versioned, fail-closed search evidence.

This adapter does not authenticate a caller: the campaign controller must fetch
jobs from the trusted worker and authorize the actor submitting this envelope.
Digests bind the supplied JSON; they are integrity identifiers, not signatures.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from .phase_report import metrics as phase_metrics, signature
from .worker import BASELINE_SHA, THREAD_VARIABLES, Worker
from .compiler_policy import LEGACY, policy_descriptor, policy_digest

SCHEMA_VERSION = 'feyer-evolution-evidence-v1'
FULL_EVALUATOR_SHA256 = 'd5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e'
ARRAY_KEYS = {'carrier', 'signal', 'noise', 'sensitivity', 'powers', 'gradient', 'parameters', 'frequencies'}
TERMINAL = {'completed', 'failed', 'timed_out', 'interrupted', 'rejected'}
HEX40 = re.compile(r'[0-9a-f]{40}')
HEX64 = re.compile(r'[0-9a-f]{64}')


def canonical_digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _hash(value):
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _number(value, positive=False):
    return (isinstance(value, (float, int)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0))


def _integer(value, positive=False):
    return type(value) is int and (value > 0 if positive else value >= 0)


def _monitor(monitor, budget):
    """Return (structurally complete, within recorded sampled budget, policy)."""
    if not isinstance(monitor, dict) or not _integer(budget, positive=True):
        return False, False, None
    policy = {key: monitor.get(key) for key in
              ('budget_bytes', 'enforcement', 'kernel_memory_limit_enforced')}
    complete = (monitor.get('budget_bytes') == budget
                and monitor.get('enforcement') == 'sampled_process_group_rss'
                and monitor.get('kernel_memory_limit_enforced') is False
                and _integer(monitor.get('samples'), positive=True)
                and _integer(monitor.get('sampled_process_group_peak_rss_bytes'))
                and type(monitor.get('exceeded')) is bool)
    within = (complete and monitor['exceeded'] is False
              and monitor['sampled_process_group_peak_rss_bytes'] <= budget)
    return complete, within, policy


def policy_from_job(job, policy_context=None):
    """Pin identities from a full seed under explicit coordinator-owned lane policy.

    Defaults stay CPU 2 / 32 GB. Non-default lane CPU/memory policy must be
    supplied independently of the candidate job; never bootstrap trust from its claims.
    """
    evidence = normalize_job(job, policy_context=policy_context)
    if not evidence['eligible_full']:
        raise ValueError('Cannot derive policy from an unvalidated or incomplete full seed job')
    result = job['result']
    policy = {key: result[key] for key in ('worker_sha256', 'evaluator_sha256',
            'comparison_evaluator_sha256', 'reference_arrays_sha256', 'memory_budget_bytes', 'cpu')}
    if result.get('compiler_policy', LEGACY) != LEGACY:
        policy.update(compiler_policy=result['compiler_policy'],
                      compiler_policy_sha256=result['compiler_policy_sha256'])
    return policy


def normalize_job(job, expected_sha=None, policy_context=None):
    """Return compact evidence; incomplete evidence never counts as a science failure.

    Outer identity errors and nonterminal observations raise ValueError. Missing,
    malformed or inconsistent artifacts return infrastructure_error with issues.
    A full strict-numerical mismatch with otherwise verified evidence is an
    invalid_candidate; it remains explicitly distinct from official rejection.
    """
    if not isinstance(job, dict):
        raise ValueError('Queue job must be an object')
    identity, sha, profile = job.get('id'), job.get('sha'), job.get('profile')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', identity):
        raise ValueError('Malformed queue job identifier')
    if not isinstance(sha, str) or HEX40.fullmatch(sha) is None:
        raise ValueError('Malformed exact candidate SHA')
    if expected_sha is not None and sha != expected_sha:
        raise ValueError('Queue job SHA does not match the proposed candidate')
    if profile not in ('screen', 'full'):
        raise ValueError('Unknown evaluation profile')
    if job.get('status') not in TERMINAL:
        raise ValueError('Evidence requires a terminal queue observation')
    # Copy with the strict JSON encoder: no NaNs, arbitrary Python objects, or
    # mutation of the caller's historical artifacts is permitted.
    try:
        artifact_digest = canonical_digest(job)
        job = json.loads(json.dumps(job, allow_nan=False))
    except (ValueError, TypeError) as exc:
        raise ValueError('Queue job is not finite canonical JSON') from exc
    policy = dict(policy_context or {})
    out = {'schema_version': SCHEMA_VERSION,
           'evidence_id': identity + ':' + artifact_digest,
           'job_id': identity, 'candidate_sha': sha, 'profile': profile,
           'execution_status': job['status'], 'category': 'infrastructure_error',
           'eligible_full': False, 'screen_passed': False, 'scientific_strike': False,
           'cohort_digest': None, 'metrics': {}, 'phases': {}, 'warm_metrics': {},
           'checks': {k: 'unknown' for k in ('official', 'strict', 'resource', 'source', 'workload', 'precision')},
           'cost': {}, 'source_digests': {}, 'artifact_digest': artifact_digest,
           'artifact_digests': {key: canonical_digest(job[key]) for key in
               ('report.json', 'comparison.json', 'result') if key in job},
           'issues': [], 'worker_error': job.get('error')}

    def issue(message):
        out['issues'].append(message)

    def finish():
        out['evidence_digest'] = canonical_digest(out)
        return out

    result, report = job.get('result'), job.get('report.json')
    if not isinstance(result, dict) or not isinstance(report, dict):
        issue('Missing result or timing report: no scientific rejection inferred')
        return finish()
    compiler_policy = policy.get('compiler_policy', LEGACY)
    try:
        compiler_descriptor = policy_descriptor(compiler_policy)
        expected_compiler_digest = policy_digest(compiler_policy)
    except ValueError:
        issue('Unknown coordinator compiler policy')
        return finish()
    if result.get('compiler_policy', LEGACY) != compiler_policy:
        issue('Recorded compiler policy differs from coordinator policy')
    # Preserve old artifacts only under their original legacy policy. Approved
    # flags need an independently supplied policy AND an explicit worker receipt.
    if compiler_policy != LEGACY or 'compiler_policy_sha256' in result:
        if result.get('compiler_policy_sha256') != expected_compiler_digest:
            issue('Missing or invalid compiler policy digest')
    if 'compiler_policy_sha256' in policy and policy['compiler_policy_sha256'] != expected_compiler_digest:
        issue('Coordinator compiler policy digest mismatch')
    out['validated_output_scope'] = result.get('validated_output_scope')
    if result.get('sha') != sha or result.get('profile') != profile or result.get('status') != job['status']:
        issue('Job/result identity or terminal status mismatch')
    if result.get('baseline_sha') != BASELINE_SHA:
        issue('Protected-file baseline is not the fixed public baseline')
    expected_env = {name: '1' for name in THREAD_VARIABLES}
    expected_env.update(JAX_PLATFORMS='cpu', JAX_ENABLE_X64='true',
                        JAX_ENABLE_COMPILATION_CACHE='false', XLA_FLAGS=None, PYTHONNOUSERSITE='1')
    if result.get('execution_environment') != expected_env:
        issue('Trusted execution environment does not establish fixed CPU/x64/cache/thread limits')
    source = report.get('source')
    if not isinstance(source, dict):
        issue('Missing source provenance')
        return finish()
    file_hashes = source.get('simulator_files_sha256')
    source_ok = (source.get('commit') == sha and source.get('modified') is False
                 and source.get('diff_sha256') == hashlib.sha256(b'').hexdigest()
                 and isinstance(file_hashes, dict) and 'differometor/simulate.py' in file_hashes
                 and all(isinstance(path, str) and _hash(value) for path, value in file_hashes.items()))
    out['checks']['source'] = 'passed' if source_ok else 'unknown'
    if not source_ok:
        issue('Source is not the clean exact candidate with complete simulator digests')

    digest_keys = ['worker_sha256', 'evaluator_sha256']
    if profile == 'full':
        digest_keys += ['comparison_evaluator_sha256', 'reference_arrays_sha256']
    for key in digest_keys:
        value = result.get(key)
        if not _hash(value):
            issue('Missing/invalid ' + key)
        elif key in policy and value != policy[key]:
            # A screen evaluator is a separate first-run implementation, never
            # the official full evaluator pinned in the full policy context.
            if not (profile == 'screen' and key == 'evaluator_sha256'):
                issue('Execution identity differs from policy: ' + key)
    if report.get('starter_sha256') != result.get('evaluator_sha256'):
        issue('Reported and executed evaluator digests differ')
    if profile == 'full' and result.get('evaluator_sha256') != FULL_EVALUATOR_SHA256:
        issue('Full evaluator is not the fixed official benchmark version')
    cpu = policy.get('cpu', 2)
    if not _integer(cpu) or result.get('cpu') != cpu:
        issue('Execution CPU differs from policy')
    try:
        validator = Worker.__new__(Worker)
        validator.cpu = cpu
        validator.compiler_policy = compiler_policy
        validator._validate_report(report, profile, expected_sha=sha,
                                   evaluator_sha256=result.get('evaluator_sha256'))
        values, phases = phase_metrics(report)
        values['runtime'] = sum(values[k] for k in ('forward', 'sensitivity', 'gradient', 'transfer'))
        out.update(metrics=values, phases=phases,
                   warm_metrics=report['timing_seconds'].get('phase_runtime_medians', {}))
        out['checks']['workload'] = 'passed'
        out['checks']['precision'] = 'passed'
        if result.get('first_run_seconds') != values['total']:
            issue('Result and report first-run totals disagree')
        if result.get('reported_environment') != report.get('environment'):
            issue('Result and report environments disagree')
        if result.get('validation') != report.get('validation'):
            issue('Result and report validation outcomes disagree')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        issue('Malformed or unverified benchmark report: ' + str(exc))

    budget = result.get('memory_budget_bytes')
    expected_budget = policy.get('memory_budget_bytes', 32_000_000_000)
    if not _integer(budget, positive=True) or budget != expected_budget:
        issue('Memory budget is missing or differs from policy')
    complete, within, memory_policy = _monitor(result.get('memory_monitoring'), budget)
    if not complete:
        issue('Missing or malformed sampled process-group resource evidence')
    peak_kib, wall = result.get('peak_rss_kib'), result.get('wall_seconds')
    if not _integer(peak_kib, positive=True) or not _number(wall, positive=True):
        issue('Missing/invalid RSS or benchmark wall cost')
    else:
        within = within and peak_kib * 1024 <= budget if _integer(budget, positive=True) else False
        out['cost'].update(wall_seconds=wall, peak_rss_kib=peak_kib, peak_rss_bytes=peak_kib * 1024)
        out['metrics']['peak_rss_bytes'] = peak_kib * 1024
    provenance = result.get('resource_provenance')
    limits = provenance.get('container_limits') if isinstance(provenance, dict) else None
    if not isinstance(limits, dict) or any(limits.get(key) is None for key in
            ('memory.max', 'memory.swap.max', 'cpu.max', 'cpuset.cpus.effective')):
        issue('Missing shared-container resource provenance')
    out['resource_evidence'] = {'budget_bytes': budget, 'memory_monitoring': result.get('memory_monitoring'),
                               'container_limits': limits,
                               'limitation': 'Sampled process-group RSS is not a kernel-enforced memory cap.'}

    official = result.get('official_passed')
    out['checks']['official'] = ('passed' if official is True else 'failed' if official is False
                                 else 'not_run' if profile == 'screen' else 'unknown')
    strict = None
    comparison_policy = None
    if profile == 'full':
        comparison, comparison_run = job.get('comparison.json'), result.get('comparison')
        if not isinstance(comparison, dict) or not isinstance(comparison_run, dict):
            issue('Missing strict comparison artifact or execution evidence')
        else:
            checks = comparison.get('checks')
            coherent = (isinstance(checks, dict) and set(checks) == ARRAY_KEYS
                        and all(isinstance(v, dict) and type(v.get('passed')) is bool for v in checks.values())
                        and type(comparison.get('passed')) is bool
                        and comparison['passed'] == all(v['passed'] for v in checks.values()))
            if not coherent or comparison.get('rtol') != 1e-7 or comparison.get('scale_atol') != 1e-12:
                issue('Malformed, contradictory or unreviewed strict comparison policy')
            else:
                strict = comparison['passed']
                if result.get('regression_passed') is not strict:
                    issue('Worker strict outcome disagrees with comparison artifact')
                if strict and any(v.get('finite') is not True for v in checks.values()):
                    issue('Passing comparison does not establish finite saved arrays')
                if comparison_run.get('returncode') != (0 if strict else 1):
                    issue('Comparison return code contradicts its numerical outcome')
            if comparison_run.get('timed_out') is not False:
                issue('Strict comparison did not finish normally')
            cmp_complete, cmp_within, cmp_policy = _monitor(comparison_run.get('memory_monitoring'), budget)
            if not cmp_complete or cmp_policy != memory_policy:
                issue('Missing or incompatible strict-check resource evidence')
            within = within and cmp_within
            cmp_wall = comparison_run.get('wall_seconds')
            if not _number(cmp_wall):
                issue('Missing comparison wall cost')
            else:
                out['cost']['comparison_wall_seconds'] = cmp_wall
                if _number(wall):
                    out['cost']['total_worker_wall_seconds'] = wall + cmp_wall
            comparison_policy = {'evaluator_sha256': result.get('comparison_evaluator_sha256'),
                                 'reference_arrays_sha256': result.get('reference_arrays_sha256'),
                                 'rtol': comparison.get('rtol'), 'scale_atol': comparison.get('scale_atol')}
        out['checks']['strict'] = 'passed' if strict is True else 'failed' if strict is False else 'unknown'
    else:
        out['checks']['strict'] = 'not_run'
        if official is not None or result.get('regression_passed') is not None:
            issue('Screening must not claim official or strict validation')
        out['cost']['total_worker_wall_seconds'] = wall if _number(wall) else None
    out['checks']['resource'] = 'passed' if complete and within else 'failed' if complete else 'unknown'
    out['source_digests'] = {key: result.get(key) for key in digest_keys}
    out['source_digests'].update(simulator_files_sha256=file_hashes,
                                 clean_diff_sha256=source.get('diff_sha256'))
    if out['issues']:
        return finish()

    cohort = {'adapter_schema': SCHEMA_VERSION, 'profile': profile, 'signature': signature(report),
              'worker_sha256': result['worker_sha256'], 'memory_policy': memory_policy,
              'container_limits': limits, 'strict_policy': comparison_policy,
              'protected_baseline_sha': result['baseline_sha']}
    # Keep historical legacy cohort digests stable; never mix reviewed-policy
    # runs into them, including reviewed runs whose candidate sets no flags.
    if compiler_policy != LEGACY:
        cohort['compiler_policy'] = compiler_descriptor
        cohort['compiler_policy_sha256'] = expected_compiler_digest
    out['cohort_digest'] = canonical_digest(cohort)
    out['cohort'] = cohort
    if policy.get('cohort_digest') and out['cohort_digest'] != policy['cohort_digest']:
        issue('Evidence cohort differs from the campaign reference cohort')
        return finish()
    if result.get('returncode') != 0 or job['status'] in ('timed_out', 'interrupted', 'rejected'):
        issue('Benchmark execution did not finish normally')
    elif not within:
        out.update(category='invalid_candidate', scientific_strike=True)
    elif profile == 'screen' and job['status'] == 'completed':
        out.update(category='screen', screen_passed=True)
    elif profile == 'full' and official is True and strict is False and job['status'] == 'failed':
        out.update(category='invalid_candidate', scientific_strike=True)
    elif profile == 'full' and official is True and strict is True and job['status'] == 'completed':
        out.update(category='valid', eligible_full=True)
    else:
        issue('Terminal outcome does not establish either validation or scientific rejection')
    return finish()
