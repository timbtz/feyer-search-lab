"""Optional internal verification gates; independent of scored benchmark eligibility.

This module reads evidence only. It does not run tests, change the official
benchmark, submit jobs, authenticate reports, or certify general correctness.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import importlib
from pathlib import Path
import re

SCHEMA = 'feyer-verification-v1'
POLICY_SCHEMA = 'feyer-verification-policy-v1'
DECISION_SCHEMA = 'feyer-verification-decision-v1'
STATUSES = {'passed', 'failed', 'needs_review', 'pending', 'blocked', 'unsupported'}
ADVERSE = {'failed', 'needs_review', 'unsupported'}
BINDINGS = ('setup_digest', 'harness_digest', 'environment_digest', 'acceptance_digest')
JAXCOMPAT_TESTS = ('value_and_grad_jit', 'descent_3_steps', 'vmap_value_and_grad',
                   'jvp', 'jacfwd_2', 'hvp_fwd_over_rev', 'hvp_rev_over_rev',
                   'eager_value_and_grad', 'public_run', 'checkpoint_grad',
                   'second_setup_same_process')
PROFILE_CAPABILITIES = {
    'challenge-first-order-review': ['value_and_grad_jit'],
    'broader-jax-review': list(JAXCOMPAT_TESTS),
}



def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _copy(value):
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError('Verification artifacts must be finite JSON') from exc


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hex(value, length):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def _sha(value):
    if not _hex(value, 40):
        raise ValueError('An exact 40-character candidate SHA is required')


def validate_verification(value, expected_sha=None):
    """Validate display-compatible envelopes without inventing missing provenance.

    Unbound historical/pending checks may be displayed but cannot satisfy a gate.
    Extra fields (outputs, thresholds, reproduction commands) are retained.
    """
    r = _copy(value)
    if not isinstance(r, dict) or r.get('schema', SCHEMA) != SCHEMA:
        raise ValueError('Unsupported verification schema')
    _sha(r.get('candidate_sha'))
    if expected_sha is not None and r['candidate_sha'] != expected_sha:
        raise ValueError('Verification candidate differs from the research record')
    checks = r.get('checks')
    if not isinstance(checks, list) or len(checks) > 500:
        raise ValueError('Verification checks must be a list of at most 500 entries')
    seen = set()
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError('Verification check must be an object')
        for key in ('id', 'setup', 'method'):
            if not _text(check.get(key)):
                raise ValueError('Verification check needs ' + key)
        if check['id'] in seen:
            raise ValueError('Duplicate verification check ID within one receipt')
        seen.add(check['id'])
        if check.get('status') not in STATUSES:
            raise ValueError('Unknown verification status')
        if check.get('candidate_sha', r['candidate_sha']) != r['candidate_sha']:
            raise ValueError('Check belongs to a different candidate')
        binding = check.get('binding', {})
        if not isinstance(binding, dict):
            raise ValueError('Check binding must be an object')
        for key in BINDINGS:
            if key in binding and not _hex(binding[key], 64):
                raise ValueError('Invalid binding: ' + key)
        for key in ('source_digest',):
            if key in check and not _hex(check[key], 64):
                raise ValueError('Invalid ' + key)
        at = check.get('observed_at')
        if at is not None and (isinstance(at, bool) or not isinstance(at, (int, float)) or at <= 0):
            raise ValueError('observed_at must be a positive timestamp')
    return r


def validate_policy(value):
    p = _copy(value)
    if (not isinstance(p, dict) or p.get('schema') != POLICY_SCHEMA
            or p.get('scope') != 'internal_opt_in' or not _text(p.get('policy_id'))
            or not _text(p.get('purpose'))):
        raise ValueError('An explicitly identified internal opt-in policy is required')
    rows = p.get('requirements')
    if not isinstance(rows, list) or not rows or len(rows) > 500:
        raise ValueError('Policy needs 1 to 500 explicit requirements')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Requirement must be an object')
        for key in ('id', 'capability', 'setup'):
            if not _text(row.get(key)):
                raise ValueError('Requirement needs ' + key)
        if row['id'] in seen:
            raise ValueError('Duplicate requirement ID')
        seen.add(row['id'])
        if not isinstance(row.get('binding'), dict) or any(not _hex(row['binding'].get(k), 64) for k in BINDINGS):
            raise ValueError('Every requirement must pin setup, harness, environment and acceptance digests')
        if type(row.get('minimum_passes', 1)) is not int or not 1 <= row.get('minimum_passes', 1) <= 100:
            raise ValueError('minimum_passes must be an integer from 1 to 100')
    return p


def template(profile, setup, binding):
    """Create an explicit starting policy, not an organizer rule or universal test suite."""
    if profile not in PROFILE_CAPABILITIES:
        raise ValueError('Unknown internal review profile')
    return validate_policy(dict(schema=POLICY_SCHEMA, policy_id=profile,
        scope='internal_opt_in', purpose='Optional internal review; official benchmark remains separate.',
        requirements=[dict(id=capability + ':' + setup, capability=capability, setup=setup,
                           binding=copy.deepcopy(binding), minimum_passes=1)
                      for capability in PROFILE_CAPABILITIES[profile]]))


def assess(candidate_sha, policy, verifications):
    """Require exact bound observations; never erase matching adverse results.

    The caller must obtain receipts from trusted sources. Hashes are integrity
    identifiers, not authentication. Duplicate artifacts cannot increase repeats.
    """
    _sha(candidate_sha)
    p = validate_policy(policy)
    if not isinstance(verifications, list) or len(verifications) > 500:
        raise ValueError('Provide at most 500 verification envelopes')
    checks, issues, input_digests = [], [], []
    for value in verifications:
        r = validate_verification(value)
        input_digests.append(digest(r))
        if r['candidate_sha'] != candidate_sha:
            issues.append('Ignored verification for different candidate: ' + r['candidate_sha'])
            continue
        checks.extend(r['checks'])
    decisions = []
    for required in p['requirements']:
        matches, excluded = {}, []
        for check in checks:
            if check.get('capability', check['id']) != required['capability'] or check['setup'] != required['setup']:
                continue
            why = []
            if check.get('binding') != required['binding']:
                why.append('setup/harness/environment/acceptance binding differs or is missing')
            if check.get('evidence_kind') not in ('independent_measurement', 'trusted_evaluator'):
                why.append('not independently measured evidence')
            if not (_text(check.get('source_ref')) and _hex(check.get('source_digest'), 64)
                    and check.get('observed_at') is not None):
                why.append('source artifact or observation timestamp is missing')
            if why:
                excluded.append(dict(check_id=check['id'], status=check['status'], reasons=why))
                continue
            # A copied source artifact is one observation, irrespective of record/check IDs.
            identity = check['source_digest']
            matches.setdefault(identity, []).append(check)
        adverse = [c for group in matches.values() for c in group if c['status'] in ADVERSE]
        passed = [identity for identity, group in matches.items()
                  if all(c['status'] == 'passed' for c in group)]
        if adverse:
            status, reason = 'needs_review', 'A matching adverse observation is retained; passes cannot hide it.'
        elif len(passed) >= required.get('minimum_passes', 1):
            status, reason = 'satisfied', 'Required exact bound observations passed.'
        else:
            status, reason = 'incomplete', 'Missing, pending, blocked or unbound evidence cannot satisfy this requirement.'
        decisions.append(dict(requirement_id=required['id'], capability=required['capability'],
            setup=required['setup'], binding=required['binding'], status=status, reason=reason,
            pass_count=len(passed), minimum_passes=required.get('minimum_passes', 1),
            observations=[dict(check_id=c['id'], status=c['status'], source_ref=c['source_ref'],
                               source_digest=c['source_digest']) for group in matches.values() for c in group],
            excluded=excluded))
    status = ('needs_review' if any(r['status'] == 'needs_review' for r in decisions) else
              'incomplete' if any(r['status'] == 'incomplete' for r in decisions) else 'satisfied')
    return dict(schema=DECISION_SCHEMA, candidate_sha=candidate_sha, policy_id=p['policy_id'],
        policy_digest=digest(p), scope='internal_opt_in', status=status,
        requirements_satisfied=status == 'satisfied', requirements=decisions,
        verification_digests=sorted(set(input_digests)), issues=issues,
        official_benchmark='unchanged; not evaluated or overridden by this module',
        limits=['This gate is additional internal policy, not an organizer requirement or a scored timing.',
                'A pass covers only the recorded setups/capabilities; it is not universal correctness.',
                'Caller must trust receipt provenance; content digests are not authentication.',
                'Historical matching failures require review; no automatic supersession or promotion.'])


def _jaxcompat_comparator():
    # Added by the independently reviewed suite-hardening change. Lazy loading
    # lets policy/receipt assessment remain useful without the optional suite.
    try:
        module = importlib.import_module('lab.jaxcompat')
        comparator = module.compare_reports
    except (ImportError, AttributeError) as exc:
        raise ValueError('import-jaxcompat requires the hardened lab.jaxcompat.compare_reports; '
                         'install the suite-hardening change first') from exc
    return comparator, hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()


def import_jaxcompat(reference, candidate, *, candidate_sha, reference_sha,
                     source_ref, setup_digest, harness_digest, environment_digest,
                     observed_at, evidence_kind, tolerance=1e-6):
    """Bind explicit caller-reviewed provenance; do not infer SHAs from tree names."""
    _sha(candidate_sha)
    _sha(reference_sha)
    if not _text(source_ref) or evidence_kind not in ('independent_measurement', 'trusted_evaluator', 'author_reported'):
        raise ValueError('Explicit source reference and evidence kind are required')
    comparator, comparator_digest = _jaxcompat_comparator()
    result = _copy(comparator(reference, candidate, tolerance=tolerance))
    rows = result.get('checks', [])
    if (not isinstance(rows, list) or len(rows) != len(JAXCOMPAT_TESTS)
            or {r.get('test') for r in rows} != set(JAXCOMPAT_TESTS)
            or result.get('required_tests') != list(JAXCOMPAT_TESTS)
            or any(r.get('status') not in ('passed', 'failed', 'unavailable') for r in rows)):
        raise ValueError('Comparator did not return the complete eleven-test contract')
    if not _text(result.get('setup')):
        raise ValueError('Comparator did not identify the setup')
    if bool(result.get('passed')) != (all(r['status'] == 'passed' for r in rows) and not result.get('issues')):
        raise ValueError('Comparator overall verdict conflicts with its checks/issues')
    source_digest = digest(dict(reference=reference, candidate=candidate))
    acceptance = dict(comparator='feyer-jaxcompat-comparison-v1', tolerance=tolerance,
                      required_tests=list(JAXCOMPAT_TESTS), reference_sha=reference_sha,
                      reference_report_digest=digest(reference),
                      comparator_source_digest=comparator_digest,
                      importer_source_digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    binding = dict(setup_digest=setup_digest, harness_digest=harness_digest,
                   environment_digest=environment_digest, acceptance_digest=digest(acceptance))
    checks = []
    for row in rows:
        status = {'passed': 'passed', 'failed': 'failed', 'unavailable': 'blocked'}[row['status']]
        # Global report errors invalidate per-test passes as gate evidence.
        if result.get('issues') and status == 'passed':
            status = 'needs_review'
        checks.append(dict(id=row['test'], capability=row['test'], setup=result['setup'],
                           name=row['test'], status=status,
                           method='Hardened lab.jaxcompat.compare_reports output comparison',
                           summary='; '.join(result.get('issues', []) + row.get('issues', [])) or
                                   'Recorded outputs matched the reference within the comparison threshold.',
                           thresholds=dict(max_relative_difference=tolerance),
                           outputs=dict(max_relative_difference=row.get('max_relative_difference')),
                           binding=binding, evidence_kind=evidence_kind,
                           source_ref=source_ref, source_digest=source_digest, observed_at=observed_at,
                           reference_sha=reference_sha, acceptance=acceptance))
    checks.append(dict(id='gpu_execution', capability='gpu_execution', setup=result['setup'],
                       method='Run the actual simulator and transformations using a JAX GPU environment.',
                       status='pending', evidence_kind='planned',
                       summary='CPU-only evidence does not establish GPU compatibility or device execution.',
                       next_action='Obtain a GPU environment and a separately bound GPU verification receipt.'))
    return validate_verification(dict(schema=SCHEMA, candidate_sha=candidate_sha, checks=checks,
                                      source_report_digest=source_digest, limits=[
        'Covers only the eleven recorded transformations on this setup; not universal JAX compatibility.',
        'Raw reports do not attest exact source/environment identity; provenance is caller-reviewed.',
        'GPU execution and untested transformations remain unknown.']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    t = sub.add_parser('template', help='Create an explicit internal review policy')
    t.add_argument('--profile', required=True, choices=sorted(PROFILE_CAPABILITIES))
    t.add_argument('--setup', required=True)
    for key in BINDINGS:
        t.add_argument('--' + key.replace('_', '-'), required=True)
    a = sub.add_parser('assess', help='Assess receipts without running tests or changing benchmark verdicts')
    a.add_argument('--candidate-sha', required=True)
    a.add_argument('--policy', type=Path, required=True)
    a.add_argument('--verification', type=Path, action='append', required=True,
                   help='Envelope or JSON list of envelopes; repeat to combine immutable receipts')
    i = sub.add_parser('import-jaxcompat', help='Strictly compare and bind the existing eleven-test suite')
    i.add_argument('--reference', type=Path, required=True)
    i.add_argument('--candidate', type=Path, required=True)
    for key in ('candidate_sha', 'reference_sha', 'source_ref', 'setup_digest', 'harness_digest', 'environment_digest'):
        i.add_argument('--' + key.replace('_', '-'), required=True)
    i.add_argument('--observed-at', type=float, required=True)
    i.add_argument('--evidence-kind', choices=['independent_measurement', 'trusted_evaluator', 'author_reported'], required=True)
    i.add_argument('--tolerance', type=float, default=1e-6)
    for command in (t, a, i):
        command.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'template':
        result = template(args.profile, args.setup, {k: getattr(args, k) for k in BINDINGS})
        code = 0
    elif args.command == 'import-jaxcompat':
        result = import_jaxcompat(json.loads(args.reference.read_text()), json.loads(args.candidate.read_text()),
            **{key: getattr(args, key) for key in ('candidate_sha', 'reference_sha', 'source_ref', 'setup_digest',
                'harness_digest', 'environment_digest', 'observed_at', 'evidence_kind', 'tolerance')})
        statuses = [r['status'] for r in result['checks'] if r['id'] != 'gpu_execution']
        code = 0 if all(s == 'passed' for s in statuses) else 3 if any(s in ADVERSE for s in statuses) else 2
    else:
        receipts = []
        for path in args.verification:
            value = json.loads(path.read_text())
            receipts.extend(value if isinstance(value, list) else [value])
        result = assess(args.candidate_sha, json.loads(args.policy.read_text()), receipts)
        code = {'satisfied': 0, 'incomplete': 2, 'needs_review': 3}[result['status']]
    payload = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end='')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
