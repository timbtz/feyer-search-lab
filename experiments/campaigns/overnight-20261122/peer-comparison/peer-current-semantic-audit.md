# Current peer simulator semantic audit

Exact imported candidate `be4949e104da90968b426e4cbdd5c9c725eb2c12`, upstream `7615f59ced23a5988e66eddc8408ff823dcd3651`. Local read-only review; no provider call or numerical test.

No deliberate fixture specialization identified. Concrete inherited builder generalization defects and portability/edge concerns prevent universal correctness claim. Current benchmark feasibility belongs to parent evaluator; these source findings do not predict its outcome.

## grouped-carrier-updates

concrete source-level generalization defect; inherited, not evidence of cheating. Source: `differometor/build.py:1588-1605`.

The grouped-pair loop collects every parameter but append_information runs after that loop using only its last optimized_component. Earlier group members with carrier update instructions can remain at base values unless separately scheduled. 3b107d69 schedules each member inside the loop. No optical failure was reproduced by this audit.

## identity-link-registry

concrete source-level state/history defect; inherited. Source: `differometor/build.py:1413-1419`.

No-link setup appends identity to global LINKING_FUNCTIONS but selects index0, not the appended identity index. If a prior setup registered a nonidentity function first, a later no-link setup can apply that function to parameter0. 3b107d69 obtains the actual identity function registry index. No optical failure was reproduced by this audit.

## carrier-dependency-scheduling

source-level generalization risk. Source: `differometor/build.py:1587-1613`.

Carrier update scheduling follows named optimization/changing components, with no scan for other instructions consuming those changed parameter indices. Hidden setups with dependent/link-driven carrier components need explicit coverage. 3b107d69 additionally schedules unscheduled carrier instructions reading updated parameter indices. No optical failure was reproduced by this audit.

## solver-options-portability

environment-dependent path difference, not automatic numerical failure. Source: `differometor/host.py:666,729-737`.

Private SuperLU path sets PanelSize=1,Relax=1; public splu fallback leaves these at defaults. Numeric equations unchanged, but timing and floating-point behavior may differ by SciPy/private-extension availability. 3b107d69 default paths match; frozen tuning menu updates both private and public paths together. No optical failure was reproduced by this audit.

## one-refinement-step

numerical robustness validation requirement, not automatic incorrectness. Source: `differometor/host.py:713-717`.

All sparse solves always apply one correction, without adaptive residual criterion. This may be entirely sufficient for tested setups; fixed one-step count alone does not demonstrate a bug. New ill-conditioned topologies require the actual official and gradient checks. Our repaired implementation retains its existing up-to-three-step refinement and residual threshold. No optical failure was reproduced by this audit.

## interpreter-zero-abs

unverified edge-case concern. Source: `differometor/host.py:219`.

Complex abs tangent divides by out=abs(x). At x=0 with an active tangent this expression produces 0/0. Whether a supported optical component exercises this path was not established in this read-only audit. Not asserted as a differentiator versus our implementation; shared interpreter ancestry requires separate scrutiny. No optical failure was reproduced by this audit.

## Checks supporting generality

- `differometor/sparse.py:160-165,201-205`: Signal/noise sparse patterns union initial nonzero coordinates with ALL update coordinates, preserving initially zero entries that may change.
- `differometor/host.py:510-513`: Gradient uses explicit A^-T signal and conjugated A^-1 noise adjoint solves; no approximate collinearity/Hermitian reuse predicate found.
- `differometor/host.py:590-597,794-799`: Two-entry forward-state cache keyed by evaluation token supports backward factor reuse; evicted state recomputes forward from supplied inputs. Not a disk answer cache or fixture result lookup.
- `differometor/host.py:334-339; sparse.py:250-261`: Kernel cache stores traced function/shape programs; real-input and supported-primitives guards choose host versus JAX fallback. Not benchmark-name dispatch. Unsupported primitives are checked for both value and tangent support at construction.
- `differometor/** executable-code search`: No benchmark-name or101/193/751 fixture dispatch, fixture file reading, precomputed answer table, or persistent compilation cache found in reviewed nine files. This is a bounded source audit, not proof of universal correctness.

Package-level compiler flags are allowed by the supplied organizer clarification; they are not flagged as a violation. First-order custom VJP/callback use is also allowed. No claim is made about higher-order differentiation, unknown hidden setups, or judging outcomes. Preserve the peer import unchanged for fair measured comparison; apply any fixes only on a separately owned candidate branch with new exact-SHA evidence.
