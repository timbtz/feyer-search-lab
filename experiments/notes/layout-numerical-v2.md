# Fresh layout/numerical round

New user authorization: up to 60 minutes and 40 new evaluator jobs, including
the seed screen/full pair. This is independent of the expired first window.
The absolute start/deadline will be recorded with the first admitted seed job.

Scientific parents:
- `28566a64a9efbdddc104762ac1f8212eb1d8370c`: guarded broadcast noise construction
  plus merged signal/noise-covariance RHS, separate adjoint factorization.
- `423bcc4ad6e99b85cd651980bee541612ed2ee20`: split coefficient/RHS layout inside
  the frequency assembly loop. Its single full pass was 22.360747559 seconds.

This candidate ports only the split layout. It retains the guarded shared noise
construction and supports both the existing multi-RHS solve and direct LU reuse.
All signal-system slices use the supplied coefficient/RHS arrays. The optional
RHS argument defaults to None, retaining the original augmented input path for
other loop scopes and callers. The assembly tuple includes noise only when the
dependency guard requires per-row construction; its index follows the layout.

Proposed frozen numerical menu after this exact seed passes full validation:
noise contraction {broadcast, shared} x factor reuse {off, direct}, four choices.
Split layout is enabled, chunk size remains 1, scope remains assemble, and the
adjoint solve retains its separate factorization in every admitted choice.
The known strict-failing `all` factor mode is excluded. The small menu calls for
local/enumeration selection, not a claim of learned SMAC acquisition.

Hypothesis: coefficient/RHS separation changes buffer layout and may reduce
stacked augmented-array copies in combination with noise reuse. No speed or
correctness claim is made before exact screen/full validation. The matrix,
frequency/variable counts, precision and official three-stage benchmark remain
unchanged. Alternate shape/guard fallbacks still need numerical evidence beyond
the official workload; syntax/source inspection alone does not establish them.

Existing CPU-2 queue owns evaluation initially. Any later second-lane migration
requires a clean boundary, a new policy/cohort and lane-local calibration; timing
under concurrent load is exploratory and cannot silently replace serial results.
