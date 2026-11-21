# claude-profile-guided-v1

- Branch: `explore/claude-profile-guided-v1`. Seed (exact parent): `96474bdd4d83bb02c163640f63fae1c4bd7a21d4`, which is claude-noise-reuse candidate 4: `NOISE_FACTOR_REUSE="direct"`, `NOISE_REUSE_MODE="broadcast"`.
- Model: `claude-opus-5-5`. Managed session: no shell and no local runs; the supervisor commits and evaluates.
- Session identifier: as recorded in the supervisor launch record, which was not shown in the prompt.
- Budget: 3599 s remaining at candidate 1. There is no candidate cap.

## Parent evidence: full job `ab12c14c29354bad9aa6dc024c91f8e6`

- Verdict: official PASS, strict PASS.

| Measure | Value |
| --- | --- |
| Complete first run | 22.366 s |
| Imports | 0.297 s |
| Build | 0.821 s |
| Forward lower | 0.824 s |
| Forward compile | 7.634 s (34.1%) |
| Forward execute | 8.609 s (38.5%) |
| Sensitivity lower + compile | 0.551 s |
| Gradient lower | 0.187 s |
| Gradient compile | 1.962 s (8.8%) |
| Gradient execute | 1.475 s (6.6%) |
| Warm median | 10.609 s (forward 8.936 s, gradient 1.505 s) |
| Job wall time | 88.1 s |
| Peak RSS | 8.13 GB |

- Strict comparison: carrier, signal, noise, sensitivity and powers are bitwise identical (error 0).
- Gradient: max normalized error 6.0e-7, max absolute error 5.1e-10, relative L2 error 7.6e-15.

## Ranked bottleneck (from source run comparisons; these are not operator profiles)

1. **Forward execute (8.61 s).** Candidate 3 (`bb9a183`, full `f62c5c80`) dropped the separate LU of `A^H` and measured 5.17 s forward, but failed strict on the gradient (indices 33, 161 and 180). So the `A^H` LU plus its transpose costs about 3.4 s, measured across two different revisions.
   - Both LUs are locked numerically. Any other factorization of the `A^H` system shifts noise by about 2e-8 relative, and the ill-conditioned gradient coordinates amplify that past the strict limit.
   - Everything else in forward is not attributed: assembly loop, triangular solves, broadcast/residual traffic.
2. **Forward compile (7.63 s).** No operator or HLO attribution is available. A coordinator diagnostic is needed: an HLO size/pass breakdown of the forward vjp.
3. **Gradient compile (1.96 s) and gradient execute (1.47 s).**

## Candidate 1: `NOISE_REUSE_MODE="rowmap"`

### Hypothesis
- **Target:** the forward execute phase (8.61 s, job `ab12c14c`), plus secondarily the gradient phase.
- **Mechanism:** in the parent's `"broadcast"` mode, the single noise matrix N (751×751) is broadcast to (101,751,751) for the batched `bij,bdj` einsum.
  - Candidate 1 → candidate 2 of claude-noise-reuse (`f3139c7` → `e525ee5`) removed that broadcast via a GEMM. It measured −0.9 GB RSS, forward −0.35 s, gradient −0.22 s, compiles −0.2 s and total −0.76 s. Those are single runs, not paired.
  - Candidate 2's GEMM changed rounding: gradient margin 0.949.
- **Change:** `"rowmap"` contracts each row in `lax.map` as `einsum("ij,dj->di", N, W_b)`. Per row, that is the same (751×751)·(751×D) product the batched dot performs per batch element, without the broadcast operand and its residual.
  - The reverse pass accumulates N's cotangent in a scan carry instead of reducing a (101,751,751) outer-product array.
- **Expected:**
  - Lower peak RSS, by up to about 0.9 GB.
  - Forward and gradient execute a few tenths of a second lower.
  - Ceiling: about the 0.76 s measured between noise-reuse candidates 1 and 2. That is an opportunity bound, not a promise.
  - Possible costs: loop overhead, and forward/gradient compile could rise slightly.
- **Numerics:**
  - Forward noise is intended to be bitwise identical, assuming XLA CPU emits the same Eigen matmul per row. This is unverified: if XLA picks a different dot kernel, the noise may round differently.
  - The noise-parameter gradient coordinates change summation order (rows are accumulated sequentially), as in candidate 1 of noise-reuse (passed at 1.6e-8).
- **Fallback:** `NOISE_REUSE_MODE="broadcast"`, which is the parent.

### Results
- Candidate SHA: pending (supervisor).
- Screen and full: pending.
