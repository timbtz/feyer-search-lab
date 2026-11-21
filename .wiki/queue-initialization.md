# Queue initialization lock

Repeated CI failures exposed a constructor race at `PRAGMA journal_mode=WAL`
when several queue clients opened a legacy SQLite database together. The existing
`BEGIN IMMEDIATE` protected the request-ID migration, but ran after journal and
table setup. SQLite's busy handler did not consistently wait during this journal
mode transition.

`lab.queue.initialization_lock` now serializes the whole constructor using a
POSIX file lock at `<state>/queue-init.lock`, before opening SQLite. WAL setup,
table/index creation and the existing transactional migration all stay inside
the lock. The connection is closed before the lock is released, including on
exceptions. The file remains as a harmless rendezvous point; the kernel lock,
not file existence, determines ownership. Never unlink it while clients run.

Lock acquisition waits at most 30 seconds and then reports a retryable
initialization timeout. This bounds acquisition only: SQLite's existing busy
timeouts still govern database operations. No enqueue/claim mutation is retried
by this change, and evaluator concurrency, worker locks and numerical checks
are unchanged. Different queue roots have independent initialization locks.

This coordinates constructors running the new code on Linux/macOS. Old clients
that ignore the lock and external SQLite tools are not covered. Merging this
change does not upgrade deployed evaluator releases or restart workers; any
future deployment remains a separately coordinated operation.

Regression checks cover lock ownership before database opening, exception
cleanup, bounded contention, and twelve independent processes migrating one
legacy database while preserving its jobs and nullable request IDs. Existing
threaded migration and idempotent submission tests remain in place.
