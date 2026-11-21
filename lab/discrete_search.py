"""Deterministic finite-space search; no simulator execution or model calls.

Local search uses categorical Hamming neighborhoods. It expands the neighborhood
when all nearer configurations are already observed, and returns to radius one
after a noise-qualified improvement. Exhaustion is finite-space coverage, not a
proof of an optimum outside the registered implementation space.
"""
import json

from .evolution_space import SOURCE_PATH, assignments, canonical, content_identity, materialize

SELECTORS = ('enumeration', 'local-search')
VERSION = 'discrete-search-v1'


def prior_observations(paths, seed_report, source, policy, normalize):
    """Admit only exact registered source, unchanged other files and full evidence."""
    baseline_files = seed_report['report.json']['source']['simulator_files_sha256']
    choices = {content_identity(materialize(source, p)): p for p in assignments()}
    rows = []
    for path in paths:
        job = json.loads(path.read_text())
        evidence = normalize(job, expected_sha=job['sha'], policy_context=policy)
        if evidence['profile'] != 'full' or evidence['category'] not in ('valid', 'invalid_candidate'):
            raise ValueError('Prior evidence must have a full scientific verdict')
        files = job['report.json']['source']['simulator_files_sha256']
        digest = files.get(SOURCE_PATH)
        if digest not in choices or set(files) != set(baseline_files):
            raise ValueError('Prior candidate is outside the registered implementation space')
        if any(files[k] != baseline_files[k] for k in files if k != SOURCE_PATH):
            raise ValueError('Prior candidate changes files outside the registered materializer')
        rows.append((choices[digest], digest, job, evidence))
    return rows


def distance(left, right):
    return sum(canonical(left[k]) != canonical(right[k]) for k in left)


def incumbent(candidates, relative=.01, absolute=.02):
    """Replay observations deterministically; screens/invalid nodes cannot win.

    Ranges are empirical noise guards, not confidence intervals. Repeated full
    confirmation remains necessary before claiming a statistically proven gain.
    """
    valid = sorted((c for c in candidates if c.get('valid')),
                   key=lambda c: (c.get('created_at', 0), c['candidate_id']))
    if not valid:
        raise ValueError('Search requires a fully validated parent')
    best = valid[0]
    for candidate in valid[1:]:
        if candidate.get('cohort_digest') != best.get('cohort_digest'):
            raise ValueError('Cannot compare different evaluation cohorts')
        threshold = max(absolute, relative * best['metrics']['total'],
                        best.get('metric_ranges', {}).get('total', 0),
                        candidate.get('metric_ranges', {}).get('total', 0))
        if best['metrics']['total'] - candidate['metrics']['total'] > threshold:
            best = candidate
    return best


def select(selector, candidates, options, relative=.01, absolute=.02):
    if selector not in SELECTORS:
        raise ValueError('Unknown deterministic selector')
    if not options:
        raise ValueError('No untested configurations remain')
    best = incumbent(candidates, relative, absolute)
    order = {canonical(p): i for i, p in enumerate(assignments())}
    for p in options:
        if canonical(p) not in order:
            raise ValueError('Configuration outside registered search space')
    if selector == 'local-search':
        chosen = min(options, key=lambda p: (distance(p, best['parameters']), order[canonical(p)]))
    else:
        chosen = min(options, key=lambda p: order[canonical(p)])
    radius = distance(chosen, best['parameters'])
    return best, chosen, {
        'heuristic_id': VERSION + '-' + selector,
        'neighborhood_radius': radius,
        'remaining_configurations': len(options),
        'incumbent_candidate': best['candidate_id'],
        'acceptance': {'relative': relative, 'absolute_seconds': absolute,
                       'noise_guard': 'maximum observed range of both candidates'},
        'hypothesis': ('Measure registered configuration using ' + selector +
                       ' at categorical distance ' + str(radius) +
                       ' from the noise-qualified incumbent; improvement is unmeasured.'),
    }
