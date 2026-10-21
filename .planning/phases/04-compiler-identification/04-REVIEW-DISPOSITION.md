---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "Bad input files and `-o .` still crash with a traceback instead of `reverseapoc <verb>: error:`"
  - id: WR-02
    severity: warning
    disposition: open
    title: "`probe calibrate --output` can overwrite files in orig/; `libmatch` protects only the `--orig` it was given"
  - id: WR-03
    severity: warning
    disposition: open
    title: "`probe calibrate` turns a refusal by the D-13 hash gate into a \"skipped\" version, exits 0 and writes the calibration"
  - id: WR-04
    severity: warning
    disposition: open
    title: "`libmatch --write` commits a runtime map built from a partial sweep, and downstream cannot tell"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Stale test gating keeps 10.5 out of the wrapper invariant tests, and the 10.5 calibration test fails instead of skipping"
  - id: IN-01
    severity: info
    disposition: open
    title: "The docs say `-zld` suppresses the file-dependency record, but the wrapper's own objects carry COMENT 0xE9"
  - id: IN-02
    severity: info
    disposition: open
    title: "cflags accepts `wpp386`, but the compiler wrapper always runs WCC386.EXE"
  - id: IN-03
    severity: info
    disposition: open
    title: "Flags are checked against a deny list, while guest paths use an allow list"
  - id: IN-04
    severity: info
    disposition: skipped
    title: "The private `splice._write_atomic` is imported by three other modules"
  - id: IN-05
    severity: info
    disposition: open
    title: "The OMF reader decides inconsistently when a Base Frame follows"
  - id: IN-06
    severity: info
    disposition: open
    title: "`cppscan._check_table` refuses an empty table at the very end of an object and mislabels `end < start`"
  - id: IN-07
    severity: info
    disposition: fixed
    title: "Dead code: `Candidate` and `_Hit.candidate()`"
open: 10
total: 12
recorded: 2026-10-21T22:34:13.928Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | skipped | 04-REVIEW-FIX.md |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | fixed | 04-REVIEW-FIX.md |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
