"""Freeze a strategy at initialization; never switch an active campaign."""
STRATEGIES = ('auto', 'qwen', 'enumeration', 'local-search', 'smac')


def resolve(requested, remaining, max_evaluations):
    if requested not in STRATEGIES:
        raise ValueError('Unknown search selector')
    if type(remaining) is not int or remaining < 0 or type(max_evaluations) is not int or max_evaluations < 1:
        raise ValueError('Finite remaining space and positive evaluation budget required')
    effective, reason = requested, 'Explicit operator choice'
    if requested == 'auto':
        if remaining <= 32 and 2 * remaining <= max_evaluations:
            effective = 'enumeration'
            reason = 'Small finite space fits the screen/full evaluation-count budget'
        else:
            effective = 'smac'
            reason = 'Space exceeds 32 remaining choices or cannot all fit the evaluation-count budget'
    return {'version': 'search-policy-v1', 'requested': requested, 'effective': effective,
            'remaining_at_start': remaining, 'enumeration_threshold': 32,
            'max_evaluations': max_evaluations, 'reason': reason,
            'limitations': 'Count-based heuristic; wall time can still prevent exhaustion.'}
