# Frozen conservative SuperLU menu

Parent: `3b107d69d9d083f7aaa5f11b952f0098ed0ba528`. Manifest: `overnight-superlu-exact-menu.json`. The parent removes approximate collinearity and Hermitian solve substitutions. Parent validation and independent source review are mandatory before admission.

Six generic choices vary SuperLU panel size (default, 8, 16) and relaxation grouping (default, 4). COLAMD ordering, pivot threshold, equilibration, precision, iterative refinement, compiler flags and physical workload are fixed. Native factorization and public SciPy fallback use identical selected settings. All choices retain explicit refined signal/noise adjoints and the exact covariance-column identity.

The source-bound exact-topology-finite-v1 manifest uses the existing lab.topology_tuning renderer. Its default reproduces every simulator source byte at the parent SHA. No source parameterization commit or bootstrap-default change is necessary. All six renderings compile and static option/guard checks pass. These are not numerical validation results.

Every choice requires both published benchmarks and all14 generalization cases. Single fresh-process samples are provisional; finalists require balanced repeated exact-SHA comparisons against the repaired parent. Preserve failed trials and compare only matching cohorts. The campaign deadline remains1795339664; no evaluator concurrency increase is requested.

These options preserve mathematical equations, not necessarily floating-point results. No answer caching, fixture-specific dispatch, physical parameter changes, or relaxed correctness thresholds are allowed. Earlier f856/ee4 review findings remain recorded; this menu does not rehabilitate those revisions.

Option documentation: https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.splu.html
