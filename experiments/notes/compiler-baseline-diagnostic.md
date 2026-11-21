# Compiler diagnostic: confirmed baseline

One nonranking diagnostic of exact `96474bdd4d83bb02c163640f63fae1c4bd7a21d4` completed as job `a8e9a3cdb3554e298a385c0551370fb6`. It retained all 101 frequencies, 193 design variables, double precision and the official three stage functions. This capture is not an official/full correctness test or a ranked first-run measurement.

The instrumented forward stage lowered in 0.860 s, compiled in 7.816 s and executed in 8.922 s. Gradient lowering/compilation/execution were 0.195/2.029/1.549 s; sensitivity compilation was 0.282 s. Job wall time was 24.537 s with GNU-time peak RSS 8,107,964 KiB. No first-run total, official pass or strict pass is assigned.

Forward pre-optimization HLO was 476,516 bytes with 6,060 counted instructions. Optimized text was 2,840,748 bytes and exceeded the 2 MiB export cap: its 12,638 counted instructions describe only the retained prefix. Do not compare that partial count as a whole-program total, or interpret instruction counts as time attribution. The retained largest computation includes a dense frequency-by-matrix loop state; sparse update assembly is a hypothesis worth examining, not a measured improvement from this diagnostic.

The numerical repeat controller was paused before new admissions. Its already-admitted full job drained normally. CPU 34 was borrowed through the existing exclusive secondary-lane lock, with a 16 GB sampled RSS guard and 600 s total runner bound. The diagnostic had its own root and release and used one separately authorized profiler-support job. Afterward, the runner restored the exact bea601a numerical release, original root, CPU, memory policy and queue; the new worker PID was 237151. The numerical owner independently verified restoration and resumed its controller. CPU 2 was not restarted. Concurrent timings remain exploratory.

Raw report, bounded compressed IR, resource result, launch, durable request and restoration receipts are in `experiments/diagnostics/compiler-baseline-v1/`; the manifest hashes every artifact. The executable wrapper is `experiments/launchers/diagnostic-borrow-v1.py`. No further diagnostics were submitted.
