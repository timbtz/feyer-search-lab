# Bound internal verification evidence

`lab.verification` adds an explicit internal review gate beside official benchmark and strict array comparison results. It never changes either verdict, runs physics, promotes a candidate, or produces scored timings. A caller may require this additional decision before its own promotion action. The existing evaluator and controller are unchanged until explicitly integrated.

The team now requires broad JAX support internally. This is a team requirement, not an additional organizer rule. The `broader-jax-review` template covers the eleven concrete uses in `lab/jaxcompat.py`: jitted first-order value/gradient, three descent steps, batched value/gradient, JVP, forward Jacobian, both Hessian-vector variants, eager first-order value/gradient, public run, checkpoint gradient, and a second setup in the same process. Passing these tests is evidence for those uses and inputs, not proof of all JAX semantics. GPU execution, untested primitives, non-smooth derivative conventions such as `abs(0)`, additional setup families, and future workloads need separate checks. In particular, “11/11 passed” must never be presented as universal JAX compatibility.

`challenge-first-order-review` is a deliberately narrow internal starting template containing only `value_and_grad_jit`. Its name does not make it the official challenge validator. The unchanged official benchmark must still run and pass independently. The eleven-test comparator's default relative output tolerance is `1e-6`; this is separate from the official log-sensitivity requirement.

## Receipt and policy contracts

The receipt is compatible with `research_records[].verification`:

```json
{
  "schema": "feyer-verification-v1",
  "candidate_sha": "<exact 40-character commit SHA>",
  "checks": [{
    "id": "jvp",
    "capability": "jvp",
    "setup": "voyager-40",
    "name": "Forward-mode derivative",
    "method": "Compare actual outputs with the unchanged-source reference",
    "status": "passed",
    "evidence_kind": "independent_measurement",
    "source_ref": "<immutable raw report URI/path>",
    "source_digest": "<64-character SHA-256>",
    "observed_at": 1795220000,
    "binding": {
      "setup_digest": "<SHA-256 of complete setup/input descriptor>",
      "harness_digest": "<SHA-256 of actual test sources and invocation descriptor>",
      "environment_digest": "<SHA-256 of actual environment descriptor>",
      "acceptance_digest": "<SHA-256 of comparator, reference and acceptance descriptor>"
    },
    "thresholds": {"max_relative_difference": 0.000001},
    "outputs": {"max_relative_difference": 0.0}
  }]
}
```

Placeholders above are illustrative, not valid digests. The validator retains additional display fields including `next_action`. Planned or historical checks can omit provenance and still display, but cannot satisfy a gate. Accepted status values are `passed`, `failed`, `needs_review`, `pending`, `blocked`, and `unsupported`.

A policy pins a capability, setup identity, all four binding digests and an optional `minimum_passes` for every requirement. All requirements must be satisfied. Only independently measured or trusted evaluator evidence qualifies; author reports and source inspection are useful context, not measured passes. The same source artifact counts once even if copied under several IDs. Matching adverse evidence remains visible and prevents satisfaction; a later pass cannot erase it. A reviewed change in the acceptance contract needs a new explicit policy and a new acceptance digest. This module does not automatically supersede failures.

The caller must establish provenance. Hashes are integrity identifiers, not signatures or authentication: declaring an arbitrary SHA or labeling a report independent does not prove it was run. Read-only source inspection does not establish that an artifact was generated from that source. Keep raw reports, environment details, complete inputs, exact candidate/reference SHAs, run command, test/harness sources, and observation time together. General labels such as `arrays_pass` or `SETUPS PASS` are not imported as proof of complete outputs or gradients.

## Import the existing JAX suite

The importer requires the hardened `lab.jaxcompat.compare_reports` implementation. It fails explicitly if only the old printing comparator is available. It reuses that comparator rather than implementing a second numerical comparison. The comparator checks complete test inventory, output tree structure, shapes and finite values against the reference. A missing or failed reference cannot create a pass. Global comparator issues invalidate otherwise-passing rows.

Run `python -m lab.verification import-jaxcompat --help` for all arguments. Supply both raw JSON report paths, full candidate and reference SHAs, the source reference, observation timestamp, reviewed evidence kind, and setup/harness/environment digests. Build the descriptors from the actual run, not from guesses. The importer constructs the acceptance digest from the tolerance, required test inventory, reference SHA/report digest, comparator source digest and importer source digest. Changing any of these changes the accepted evidence contract.

```bash
python -m lab.verification import-jaxcompat \
  --reference /path/to/reference.json --candidate /path/to/candidate.json \
  --candidate-sha "$CANDIDATE_SHA" --reference-sha "$REFERENCE_SHA" \
  --source-ref "$RAW_REPORT_REFERENCE" --observed-at "$OBSERVED_UNIX_SECONDS" \
  --setup-digest "$SETUP_DIGEST" --harness-digest "$HARNESS_DIGEST" \
  --environment-digest "$ENVIRONMENT_DIGEST" \
  --evidence-kind independent_measurement --output /path/to/verification.json
```

These variables must already contain reviewed identities. The importer does not infer commits from directory names. Nonfinite JSON artifacts are rejected instead of becoming pass receipts; retain their raw files and record a failed or blocked diagnostic check separately. Imported CPU-suite receipts always include a planned, pending `gpu_execution` row. A CPU pass cannot satisfy an explicitly added GPU requirement.

After reviewing an imported receipt, create a policy pinning its binding. The Python API avoids copying digests manually:

```python
import json
from pathlib import Path
from lab.verification import assess, template

receipt = json.loads(Path('/path/to/verification.json').read_text())
first_check = receipt['checks'][0]
policy = template('broader-jax-review', first_check['setup'], first_check['binding'])
Path('/path/to/policy.json').write_text(json.dumps(policy, indent=2) + '\n')
decision = assess(receipt['candidate_sha'], policy, [receipt])
```

Creating a policy from a receipt is convenient, but the human or trusted orchestrator must approve its setup, harness, environment and acceptance contract first. To cover multiple setups or extra capabilities, append explicit requirements with unique IDs and the correct binding for each. An `abs_zero_derivative` requirement, for example, needs its own observed JAX-reference comparison; the eleven-test suite does not supply it. GPU requirements need an actual GPU-bound receipt. Policies are finite lists, not claims about every possible task.

```bash
python -m lab.verification assess --candidate-sha "$CANDIDATE_SHA" \
  --policy /path/to/policy.json --verification /path/to/verification.json \
  --output /path/to/decision.json
```

Repeat `--verification` for immutable receipts from additional runs. Assessment exits `0` for satisfied, `2` for incomplete, and `3` for needs review. The import command uses the same codes for the eleven CPU-suite rows; its pending GPU row is always retained separately. Invalid inputs are errors. The decision includes excluded evidence and reasons, matched observations, counts, and input/policy digests. It intentionally has no `official_passed` or `eligible_full` field.

## Integration and checks

Store the receipt under the research record's `verification` field for the explorer. Show the gate decision beside official/strict verdicts with its internal policy name and exact setup scope. Planned checks should remain visible as work to do, with next steps; they must not appear as completed measurements. Policy decisions can be retained as separate artifacts referenced from the record. Integration into promotion requires an explicit caller action; this module does not silently alter existing scheduling or eligibility.

The focused unit suite tests exact identity/binding requirements, missing and untrusted provenance, retained adverse evidence, duplicate-source repeat inflation, status validation, nonfinite rejection, importer coverage/overall consistency, GPU unknown, reference binding, and CLI exit codes:

```bash
python -m unittest discover -s tests -p 'test_verification.py'
```

These are infrastructure tests, not new physical measurements or a performance benchmark. Numerical comparator adversarial tests belong to `lab.jaxcompat` and its test module.

Implementation validation: 12 focused verification tests, 13 existing research-lineage tests and 9 existing evolution-evidence tests passed. An adapter integration check loaded the actual hardened comparator from numerical-review commit `92fd7c0` and compared the historical pristine/aac9904 raw reports from `b093f74`. It retained 11 passing CPU checks and the pending GPU check; with author-reported provenance the internal gate correctly remained incomplete. This was a comparator/adapter check against existing artifacts, not a rerun of the simulator and not an independent measurement of aac9904. No qualifying receipt was created using invented run metadata.
