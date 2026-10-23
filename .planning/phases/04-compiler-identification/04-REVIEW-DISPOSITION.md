---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: IN-08
    severity: info
    disposition: open
    title: "`--log <existing directory>` compiles, then fails at the append and leaves the object behind (pre-existing, accepted at UAT)"
  - id: IN-09
    severity: info
    disposition: open
    title: "The WR-02 fix covers devices only; an unwritable log directory still fails a successful compile"
  - id: IN-10
    severity: info
    disposition: open
    title: "`_reap` in the real parallel test kills only the Python `cc`, not the compiler it spawned; `cc_root` still fails on a leftover directory"
  - id: IN-11
    severity: info
    disposition: open
    title: "`test_dev_null_log_works_and_leaves_no_sidecar` hides its own regression when run as root"
  - id: IN-12
    severity: info
    disposition: open
    title: "The IN-03 qualification reached the toolchain bullet but not the `_append_log` docstring"
  - id: IN-13
    severity: info
    disposition: open
    title: "The new CLI test's `assert not obj.exists()` cannot fail"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "A `--log` without a final name component (`.`, `C:/`, `/`) now crashes with an uncaught ValueError, after the compile has run"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "`--log /dev/null` (and any log in a directory the user cannot create files in) now fails a successful compile"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "The new concurrency tests wait on child processes with no timeout, and the real parallel test leaks processes on its first failure"
  - id: IN-01
    severity: info
    disposition: fixed
    title: "`_try_lock` retries on EACCES, but the UCRT maps more than lock contention to EACCES, and the spin has no deadline or diagnostic"
  - id: IN-02
    severity: info
    disposition: fixed
    title: "The sidecar comes from the `--log` spelling, not the file it names"
  - id: IN-03
    severity: info
    disposition: fixed
    title: "The toolchain bullet states Windows-host facts as general ones"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "`libmatch --write` could commit a runtime map from a partial sweep"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "Stale gating kept 10.5 out of the wrapper and calibration tests"
  - id: IN-04
    severity: info
    disposition: skipped
    title: "The private `splice._write_atomic` is imported by three other modules"
  - id: IN-05
    severity: info
    disposition: fixed
    title: "The OMF reader disagreed on when a Base Frame follows"
  - id: IN-06
    severity: info
    disposition: fixed
    title: "`_check_table` refused an empty table at the very end of an object"
  - id: IN-07
    severity: info
    disposition: fixed
    title: "Dead code: `Candidate` and `_Hit.candidate()`"
open: 6
total: 18
recorded: 2026-10-23T19:20:36.639Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| IN-08 | info | open | - |
| IN-09 | info | open | - |
| IN-10 | info | open | - |
| IN-11 | info | open | - |
| IN-12 | info | open | - |
| IN-13 | info | open | - |
| WR-01 | warning | fixed | 04-REVIEW-FIX.md (not in the current review) |
| WR-02 | warning | fixed | 04-REVIEW-FIX.md (not in the current review) |
| WR-03 | warning | fixed | 04-REVIEW-FIX.md (not in the current review) |
| IN-01 | info | fixed | 04-REVIEW-FIX.md (not in the current review) |
| IN-02 | info | fixed | 04-REVIEW-FIX.md (not in the current review) |
| IN-03 | info | fixed | 04-REVIEW-FIX.md (not in the current review) |
| WR-04 | warning | fixed | 04-REVIEW-FIX.md (not in the current review) |
| WR-05 | warning | fixed | 04-REVIEW-FIX.md (not in the current review) |
| IN-04 | info | skipped | 04-REVIEW-FIX.md (not in the current review) |
| IN-05 | info | fixed | 04-REVIEW-FIX.md (not in the current review) |
| IN-06 | info | fixed | 04-REVIEW-FIX.md (not in the current review) |
| IN-07 | info | fixed | 04-REVIEW-FIX.md (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
