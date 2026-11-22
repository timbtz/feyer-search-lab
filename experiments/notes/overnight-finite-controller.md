# Bounded conservative solver tuning

`lab.overnight_finite` enumerates a frozen source-bound implementation menu. A six-point menu does not justify fitting a surrogate: complete enumeration is deterministic, covers every legal point, and spends no model tokens. Physical inputs, precision, refinement rules and the public benchmark harness remain fixed.

Admission requires an operator start gate with the exact repaired seed's dual-benchmark/generalization receipt and an independently approved local source review of the complete original-seed-to-repair simulator diff. The previously considered f856 adjoint approximation is not an admitted seed. The manifest must bind every simulator source to the repaired Git revision.

Each request runs both unchanged full official workloads and all 14 generalization cases with one fresh process per workload, in a fresh request checkout. These are preliminary observations, not three-repeat promotion evidence. After the six menu observations, a nondefault choice must improve both times by at least max(3 ms, 0.5%) to receive five alternating AB/BA pairs against the repaired default. Otherwise the outcome is no qualifying improvement. Six observations plus ten confirmation requests is the absolute 16-request ceiling. Failed trials remain visible and are not replaced. The fixed campaign deadline also stops admission.

No model calls, extra evaluator workers, dependency changes or automatic winner promotion occur. The existing client uses the serial dual runner and publishes immutable raw receipts. The controller publishes its frozen manifest, every sample, scientific failures, full job durations and decision on the dedicated control branch under the publisher lock. Grid and aLIGO times remain separate objectives. A single sample or pooled observations from distinct revisions never become a confirmed improvement.

Durable UUIDs are saved before dispatch. Recovery resumes the same request, including a request already admitted before the deadline. Committed source, branch, menu, budget and gate hashes are checked on resume. Publication retry does not resubmit measurements. The optional trusted client `fresh_process_repetitions` configuration defaults to the existing three repetitions; only this controller explicitly selects one.

Run only after the coordinating operator has completed its preceding confirmation and seed admission:

```sh
python -m lab.overnight_finite \
  --repo '/Users/t.betz/Documents/Feyer challenge' \
  --manifest /absolute/path/to/repaired-menu.json \
  --client-config /absolute/path/to/client-config.json \
  --state-dir /absolute/path/to/finite-tuning-state \
  --start-gate /absolute/path/to/start-gate.json \
  --name overnight-finite-v1 --deadline-unix 1795339664 \
  --max-jobs 16 --confirmation-pairs 5
```

For an interrupted controller, add `--resume` with identical arguments. The gate contains `ready: true`, `deadline_unix`, `seed_sha`, `seed_receipt_path` and `source_review_path`. The review is explicitly local collaborating-agent evidence, not a fabricated provider session.
