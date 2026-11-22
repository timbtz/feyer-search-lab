# Proposed peer solver plus general builder fixes

Scientific source parent: be4949e104da90968b426e4cbdd5c9c725eb2c12, the exact upstream7615f59 simulator import. Builder logic donor:3b107d69d9d083f7aaa5f11b952f0098ed0ba528. This is an explicitly proposed combination, not an accepted winner.

Only differometor/build.py changes: schedule every member of grouped optimized pairs; select the actual registered identity link rather than assuming index0; schedule additional carrier instructions that read optimized or carrier-swept parameter indices, including initially zero contributions. The dependency scan is the reviewed direct input-reader scheduling logic, not a new transitive linking algorithm. Signal-only sweeps retain their existing placement after the carrier solve.

The peer host interpreter, sparse factorization options, refinement, callbacks, gradient rules and compiler settings are untouched. No host_pass implementation or donor solver is imported. Benchmark, dependency and fixture files remain unchanged.

Four lightweight regressions execute the actual scheduling and identity function source blocks without importing JAX. They check grouped members/shared value indices, foreign parameter readers, carrier versus signal-only sweeps, and identity registration after a nonidentity function across repeated builds. Source compilation and diff checks pass. These tests do not establish optical numerical correctness or speed.

Before acceptance this exact revision requires both unchanged official benchmarks, all14 generalization cases, independent source review and fair repeated timings. The original peer and repaired-source head-to-head remains frozen and unaffected. No new evaluation is launched by this branch author.
