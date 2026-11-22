# Current peer simulator comparison

Imported the exact complete `differometor` tree from akshat-bhat/Feyer main at `7615f59ced23a5988e66eddc8408ff823dcd3651` onto trusted seed `53f38d342c3228c052785e8c9d63b6ce9c832dd1`. No compatibility patch or simulator adaptation was applied. Upstream tree identity and every file hash are recorded in the adjacent JSON manifest. Benchmark and dependency files remain from the trusted seed; the evaluator supplies its unchanged official grid and aLIGO harnesses.

The previous local comparison checkout was c38eecda; current upstream differs from that simulator only by package-level compiler settings in __init__.py. The previous imported e2fd659 actually identifies upstream de67f012, not 8d39af7; the manifest records exact changed paths against that available import, avoiding an unsupported source attribution.

No measured speed or feasibility is claimed. Evaluate this exact import with both official benchmarks and the same additional 14 cases. Any failure must remain visible. Compare complete fresh-process timings on matching one-logical-CPU hardware/environment, including compilation. This branch changes neither the peer repository nor the lab evaluator.
