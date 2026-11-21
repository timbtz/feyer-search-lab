# Teammate host engine review candidate

Simulator files copied byte for byte from https://github.com/akshat-bhat/Feyer/tree/de67f012553d00621fc25404ddecde33e2318493/differometor.
This is an isolated review candidate, not a promoted or merged winner. The official benchmark, fixtures, dependencies and evaluator are unchanged.

The source ledger reports 0.743449828 s complete first-run median for 8d39af7 (three fresh processes, one AMD EPYC 9334 CPU). Its array comparator uses rtol=1e-6, scale_atol=1e-9; our additional comparator uses 1e-7 and 1e-12. An independent comparison of the source's final.npz against baseline.npz fails our stricter bounds at 131 signal entries and gradient indices 33, 161 and 180. Official sensitivity acceptance and this additional regression policy are separate.

Hypothesis: sparse factorization plus an interpreted NumPy component/adjoint engine removes most dense-solve work and XLA compilation while retaining full first-order evaluation. Test through the unchanged full evaluator; preserve any strict failure.
