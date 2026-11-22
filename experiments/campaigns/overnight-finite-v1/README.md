# Bounded SuperLU implementation tuning

Six frozen configurations vary `panel_size` in {default, 8, 16} and `relax` in {default, 4}. Physics, topology, double precision, COLAMD ordering, pivot defaults and iterative-refinement settings remain fixed. This is exhaustive enumeration, not an LLM or a fitted SMAC model.

Parent: `3b107d69d9d083f7aaa5f11b952f0098ed0ba528`, which restores explicit signal/noise adjoint solves after a source review found unsafe approximate substitutions in older candidates. Its preflight `fbe23beea6e049ccbb5e971232a00955` passed all six official processes and 14 seed-relative cases. Three-process medians: 0.827086 s large, 0.529997 s aLIGO. Inherited pristine-reference caveats remain; this is not universal correctness proof.

Controller runs locally; all numerical work runs serially on AMD logical CPU 2 through the existing immutable dual evaluator. Each request includes both complete official benchmarks and all 14 additional cases. Every grid timing starts in a fresh checkout; aLIGO follows grid. This differs from the earlier three-process-per-checkout median scope.

Budget: six menu trials plus, if both single-sample setup thresholds improve, five balanced seed/finalist pairs. Maximum 16 requests; original deadline 2026-11-22 09:27:44 UTC. No automatic promotion, retries retain request IDs, failures remain visible. Exact source branches and individual evidence are published as each request completes. `results.json` will appear here when the bounded controller finishes.

Runtime: `d0df691534e8df0066225b5fd4bc1068706274df` on `infra/overnight-finite-tuning`. Frozen menu: `9b0c63155dfa112f19e156c9ef4b86ce573662d1` on `explore/overnight-superlu-exact-menu-v1`. Candidate branches: `explore/overnight-finite-v1/choice-00` through `choice-05`.

The organizers evaluate an unknown topology similar to the large example. Both public benchmarks and these extra cases are evidence of transfer, not a substitute for generic simulator semantics. Benchmark scripts and physical setup definitions are unchanged.
