"""Turn measured phase attribution into bounded experiment guidance."""
import json
from pathlib import Path

from .profiler import feedback_profile, profile_job


def load_seed(path, expected_sha):
    """Pin initial guidance to a trusted, fully checked exact starting revision."""
    value = json.loads(Path(path).read_text())
    job = value.get('full') if 'full' in value else value
    if not isinstance(job, dict) or job.get('sha') != expected_sha:
        raise ValueError('Profiler seed must match the exact initial worktree HEAD')
    profile = profile_job(job)
    if profile['status'] != 'ok' or not profile['eligible_full']:
        raise ValueError('Profiler seed requires complete eligible full evidence')
    return {'candidate_sha': expected_sha, 'full': job}


def prompt_guidance(feedback):
    policy = (
        '\n\nProfiler-guided experiment policy:\n'
        'First identify which measured phases consume most time for this exact candidate. '
        'In hypothesis and notes cite the job ID and phase, explain the mechanism, and predict '
        'which phase changes. A hypothetical halving estimate is an opportunity calculation, '
        'not a measured or promised speedup. Make one attributable implementation change. '
        'Unknown native-operation costs remain unknown; do not infer solve or kernel time from source counts. '
        'Optimize complete first-run time with all three JIT stages and unchanged physical workload. '
        'Warm execution, compilation, job wall time and profiling diagnostics are separate evidence. '
        'Screening is provisional; inspect official full and all saved-output/gradient checks. '
        'Compare with the retained exact parent and preserve failures; a phase improvement cannot '
        'excuse a slower total or a numerical failure. Profiling does not grant more time, '
        'parallel evaluations, local benchmark runs, or changes to frozen search spaces.\n'
    )
    if not feedback:
        return policy + 'No measured profiler seed is available; do not invent hotspot evidence.\n'
    # Recompute from raw results; never trust stale derived feedback on resume.
    evidence = feedback_profile(feedback)
    return policy + 'Measured phase attribution:\n' + json.dumps(evidence, indent=2, allow_nan=False) + '\n'
