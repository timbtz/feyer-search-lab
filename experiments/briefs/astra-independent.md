# Independent Differometor optimization

This is a fresh independent investigation from the original public baseline
`02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f`. Determine your own approach from the
challenge code and the measurements returned for your own candidates.

Minimize the complete first-run evaluation time: imports, CPU initialization,
input loading, optical setup construction, all three JIT lowering/compilation
stages, forward simulation with its AD residuals, sensitivity and power readout,
the full reverse gradient, and transfer to host. Warm runtime and total evaluator
job duration are separate observations, not replacements for that objective.

Preserve the complete optical setup, all 101 frequencies, all 193 physical design
variables, double precision, physical outputs and gradients. Do not optimize or
alter the physical inputs. Preserve the benchmark's three JIT stages. Do not
modify `benchmark.py`, `plot_timings.py`, fixtures, dependencies or the evaluator.
Do not cache answers or enable persistent compilation caching.

Sensitivities must be positive and satisfy the supplied logarithmic reference
comparison within `1e-5`. Physical outputs and the complete gradient must be
finite; the gradient must be nonzero. Preserve the supplied benchmark's gradient
sanity check. The lab additionally reports a strict comparison of all saved
outputs and gradients against reference arrays. Its result and numerical error
magnitudes are separate from the official challenge checks; neither should be
silently substituted for the other.

The supervisor owns commits, Git publication, exact-SHA submission, the assigned
evaluation queue and delivery of results. Edit only `differometor/**` and your own
notes under `experiments/notes/**`. Read-only Git status, diff and log inspection
of your own working copy and branch is permitted. Do not make commits, push,
invoke GitHub or SSH, run a local benchmark, use other evaluation queues, install
dependencies or change the environment. Do not
spawn agents or start services. Keep your failed attempts and measurements in
your own notes and conversation.

Use only this conversation, the original challenge material, your assigned
working copy and the raw results from your own session. Do not read other agents'
notes, prior experiment reports, other branches, the team wiki, research guidance
or profiler recommendations. This independent-session brief replaces prior
exploration briefs and their proposed optimization directions. The supervisor
will return your own phase measurements and numerical checks without suggested
strategies or hypothetical speedups.

The session lasts one hour from its recorded actual start, with no candidate-count
limit. The supervisor's fixed deadline governs new turns and submissions; do not
extend it. Previously submitted work may finish and be recorded afterward.

When a candidate is ready, return exactly the supervisor's structured response:
`summary`, `hypothesis`, `ready_for_evaluation`, `stop`, and `notes`. Readiness and
stop are booleans. Both may be true for a final candidate that should be evaluated
before stopping. Preserve the session identifier, your own evidence and an honest
handoff when the time budget ends.
