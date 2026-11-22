# Proposed generic three-step refinement

Exact parent: d785b5bb2451b10ff259458303e36bda790393f9 (peer solver plus three general builder fixes). This revision changes only SparseSystem.solve and explanatory comments in differometor/host.py.

The existing initial solve is followed by one to three actual residual corrections. Each correction is added before the relative-correction stopping check (max absolute correction <= 1e-14 times max absolute updated solution). The same method covers N, T and H solves. No residual, cotangent component or operator asymmetry is discarded; no physical input or fixture is inspected. Factorization options, dtype, derivative formulas and compiler settings remain unchanged.

Three local tests execute the actual method with a controlled inexact dense solve on an ill-scaled complex 2x2 system for all three operators, and check minimum one correction, the three-step cap, unchanged input and zero RHS behavior. These tests establish iteration semantics, not SuperLU or optical accuracy. Existing solver comments containing historical accuracy numbers are explicitly labelled as observations of the older one-step implementation.

No numerical benchmark has been run by this author. Both official benchmarks and all14 generalization comparisons are required on this exact revision. Parent d785 had official passes but seed-comparison failures; extra refinement is a hypothesis, not an established repair. Closer agreement to our seed is not automatically closer agreement to physical truth. Preserve all failed comparisons and investigate discrepancies without loosening tolerances. This candidate is not promoted.
