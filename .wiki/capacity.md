# Expanded CPU capacity and comparison policy

The user explicitly authorized more CPU capacity and a fresh numerical-search
budget on 2026-11-21. This supersedes the initial one-worker-per-host restriction
for the broker-managed capacity expansion. It does not extend an expired campaign
or the deadlines of the existing Claude and Astra sessions. One writer owns each
branch, and one supervisor owns each submission stream.

## Current ownership and admission

- The broker owns additional worker lanes, topology/affinity checks, queue roots,
  resource monitoring, launch receipts and concurrency-epoch records. A second
  lane is an initial target, not evidence that it is running. Additional lanes
  require measured resource headroom and their own receipt.
- The numerical owner owns `layout-numerical-v2` and branch
  `explore/layout-round-seed`. Its actual launch receipt starts at Unix
  `1795292429.2574458` and ends at `1795296029.2574458` (21:20:29 UTC), with
  **40 total jobs**, including two seed checks. The profiler owner instructed the
  fresh one-hour clock to start at actual launch; the earlier 20:14:57 UTC plan
  had not launched. The campaign ceiling after seed checks is 38 jobs. Do not
  restart this actual clock on a lane handoff.
- The layout combination is assigned to the numerical owner; the earlier planned
  Astra layout assignment was withdrawn before injection. Astra and Claude retain
  their original profiler-guided work and fixed deadlines. No duplicate layout
  task or third model session is implied.
- The launched seed `e0a1dc69f4951c100fefbc9fc08a23c3c12058dc` combines `28566a64` with the layout-only transformation from
  `3e94580e` to `423bcc4a`. It must obtain its own exact full/strict evidence. The
  proposed four-option menu varies noise contraction (`broadcast`, `shared`) and
  factorization (`off`, `direct`), with assembly chunk 1 and a separate adjoint
  factorization. A proposed menu or source change is not a passing seed.

The local bootstrap launch receipt records PID 39262, controller commit
`2ae00b7b0efac2b85e7928118128db92c3f75a8b`, and first screen job
`4c29fe65a1b54b5192b51ad5775db353`. These are launch facts, not a claim that the
process is still running or that the seed passed. Live status belongs in the
campaign receipt and queue.

CPU-2 exploratory jobs may start within this new budget while the additional lane
is prepared. Record the actual seed SHA, menu digest, campaign ID, queue/root,
start/deadline and request IDs in the campaign receipt. Preserve failed trials.
Never silently resume the exhausted earlier SMAC campaign.

## Lane setup and measured capacity

Each lane needs a distinct physical core (check SMT siblings), queue/root, worker
lock and service identity. Do not restart an existing worker or interrupt an
in-flight job to create capacity. Retain the fixed Python environment, official
benchmark, precision, physical workload and strict checks.

Use aggregate memory evidence, not CPU utilization alone. The broker's initial
proposal is the existing 32 GB sampled process-group budget plus a new 16 GB
budget, subject to measured host/container headroom. These are sampled limits,
not reservations or kernel-enforced caps. Record observed simultaneous RSS,
container limits, affinity, load and resource failures before increasing capacity.

A non-CPU-2 or differently budgeted lane requires an explicit reviewed evidence
policy. `normalize_job` accepts `policy_context`, but default-policy callers and
seed bootstraps must also be updated; a new worker alone does not make its reports
eligible. Keep original evaluator jobs and hashes intact. Establish the new lane's
own baseline/reference and cohort before comparisons or campaign handoff.

## Concurrent timing is exploratory

Different cores still share memory bandwidth, caches and container resources.
Even CPU-2 jobs with unchanged evaluator hashes have a different timing context
when another lane runs. Record the concurrency start/end, active lanes and every
overlapping job ID in a broker-owned sidecar receipt, including jobs already
running when capacity starts. Official/strict passes remain correctness facts;
concurrent timings do not establish quiet-run speedups.

The team coordinator records this admission before importing expanded-capacity
results, using the updated team CLI:

```bash
team comparison-regime --mode concurrent --receipt RECEIPT_URL \
  --reason 'Expanded CPU capacity admitted; imported timings remain exploratory.'
```

New imports receive `comparison_context`. Concurrent records remain in the ledger
but are excluded from `assess` comparison samples; incomplete confirmation returns
`needs_serial_confirmation`. Scientific failures are still retained and checked.
Full-and-strict passing concurrent candidates can still be admitted as research
or confirmation parents; correctness admission does not certify a timing gain.
Retries preserve the original context instead of relabeling a job. The regime is
conservative across all hosts: import historical records before the transition,
or keep them exploratory and collect fresh confirmation. The context is separate
from the immutable numerical cohort and does not rewrite evaluator evidence.

Use the updated CLI for all team writes and assessments. This is a cooperative
protocol; old clients do not enforce the new timing-context rule. The dashboard
must show the context and must not infer a winner from raw timings or task status.

## Return to serial confirmation

Stop admissions to extra lanes, allow every admitted job to drain, and preserve
the terminal reports and resource receipts. Import those results while the
concurrent regime is still active. Only then record a drained receipt:

```bash
team comparison-regime --mode serial --receipt DRAINED_RECEIPT_URL \
  --reason 'All overlapping jobs drained; begin new quiet confirmation runs.'
```

Only freshly started jobs whose trusted `started_at` is at or after this transition
and whose `finished_at` is at or after their start can enter serial comparison
samples. Missing/reversed timestamps and late arrivals from
the previous epoch are `unverified_timing` and remain excluded. Preserve queue
`started_at`/`finished_at` in exported job JSON. A new context label cannot turn an
old concurrent measurement into quiet evidence.

Re-evaluate the exact finalists and both scientific parents on one quiet host,
same core, environment and numerical cohort, with the existing repeat/noise policy.
A combination must beat its better parent. The exact final merged SHA requires
its own confirmation. More exploratory throughput does not relax this gate.
