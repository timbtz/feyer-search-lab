# SuperLU panel size 1 / relaxation 1

Parent: `3b107d69d9d083f7aaa5f11b952f0098ed0ba528`, the explicit-adjoint conservative repair.

Hypothesis: small SuperLU panels and relaxed-supernode size may reduce factorization overhead for this class of sparse optical systems. Peer evidence suggested this option; no measured gain is claimed here. This is separate from the previously frozen six-point menu.

Only `differometor/host_pass.py` changes: native `_superlu.gstrf` options use `PanelSize=1, Relax=1`, and the public `splu` fallback uses matching `panel_size=1, relax=1`. COLAMD, pivot defaults, equilibration, precision, iterative-refinement limits/tolerance and the explicit full adjoint solves are unchanged. No optical topology, frequencies, variables, fixtures, benchmark or dependency changes.

Validation before evaluation: complete parent source matched the frozen menu; default rendering reproduced every simulator file byte-for-byte; both option locations were rendered together; all ten Python simulator sources passed AST parsing; only the intended source file differed. Required next: exact-SHA two-official-benchmark plus14-case validation, then matched fresh-checkout timings if valid. No evaluation was launched by the candidate author.
