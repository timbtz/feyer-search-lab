# Independent follow-up review

Candidate `cb502e8a5a15689e6f41971bd4a611cf6612283f`; unchanged reference `02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f` (remote checkout clean for simulator and example data). Diagnostic source `18b8e51`; simulator source digests are retained in raw receipts. Runs use the fixed Linux Python3.12.15/JAX0.9.0/NumPy2.5.5 environment, float64, one pinned logicalCPU101, disabled persistent compilation caching. These tests are unscored and not comparable with complete first-run totals.

## Findings

- Bounded Voyager optimization (three steps) and four-design batching passed against unchanged code: maximum relative output differences5.2483943e-10 and1.6487997e-13, under1e-6. Raw receipts preserve all evaluated/final vectors,45parameters and40frequencies. Reflection restrictions are checked independently from saved points. This is a restricted domain check, not proof of every physical constraint.
- Historical unbounded trajectory/batching exceeded reflectivity1. Preserve those failures as API stress; do not call them valid-design failures. The bounded tests use separate IDs and do not replace the eleven-test inventory.
- Hardened comparison of cachedb093f74 reports retains denseaac9904=11/11 and sparseac49ee4=7/11. This is reanalysis of historical artifacts, not a new simulation or independent timing.
- The cb502 historical suite is5passed,1nonfinite batch,5unavailable; originalstatus=ok did not establish finite results. Four transformation failures (forward/second-order) remain genuine compatibility limits.
- Synthetic30x30 complex custom_linear_solve probe passed8/8, including Hessian, JVP and batching; worst relative comparison6.3600201e-16. It validates this mechanism for that toy, not the whole optical simulator, GPU support, a migrated candidate or its speed.
- Exact-source bounded evidence satisfies its two-capability internal gate. It does not satisfy a broader JAX policy. Gates are explicit opt-in callers, not yet automatic promotion enforcement; official and strict evaluator verdicts are unchanged.

## Prior numerical arbitration: evidence and limits

Another session's2e91916 cites sparse-worker notes at3d98686: extended-precision residual refinement reportedly gives detected-magnitude errors rand1=9.1e-11 (dense2.6e-4), rand3=2.5e-8 (dense3.8e-5). This supports dense-roundoff as an explanation. The inspected source contains notes but no corresponding arbitration script, captured systems, residual/precision convergence receipts. Independent reproduction, certified error bounds and gradient33/161/180 arbitration remain open. This worker study is distinct from the teammate's inspectable eight-step roundoff_study.py; limitations specific to that script must not be attributed to the unavailable worker implementation. The strongest justified label is worker-reported extended-precision proxy evidence, not certified exact truth. Matching organizer reference remains a separate requirement.

## Reproduction and infrastructure

`execution.json` contains exact commands, timestamps, return codes and source hashes; run-0..3.log retain outputs. Raw bounded reference/candidate and comparison files are included. `build_bounded_receipt.py` rebuilds the separately scoped policy and decision from those artifacts when run from repository root with PYTHONPATH=.; policy descriptors preserve setup, harness, environment and acceptance identities. Content hashes establish integrity, not independent authentication.

59 infrastructure acceptance/lineage tests,36 frontend JS tests and6 server tests passed. Browser smoke verified exact candidate selection, expandable failures, pending GPU and all193-coordinate evidence, plus desktop/mobile rendering. See infrastructure-validation.json for commands and failed attempts. The combined frontend on review/external-evidence7f39810 is previewed atlocalhost:8770 against the live read-only8765API. Another session owns8765; its running server was preserved.

No full-simulator proof or universal JAX claim is made. Pending work: full migrated custom_linear_solve candidate, all relevant setup/gradient gates, independently reproducible numerical arbitration, GPU if required, fresh matching-hardware timing confirmation.
