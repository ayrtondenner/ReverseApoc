| IN-05 |  | fixed | 2d74826 (05-REVIEW-FIX.md; scoped re-review: addressed) || IN-04 |  | fixed | aaa08e6 (05-REVIEW-FIX.md; scoped re-review: addressed) || IN-03 |  | fixed | 300ee86 (05-REVIEW-FIX.md; scoped re-review: addressed) || IN-01 |  | fixed | 1fecd6b (05-REVIEW-FIX.md; scoped re-review: addressed) || WR-01 |  | fixed | bcf46d7 (05-REVIEW-FIX.md; scoped re-review: addressed) |---
phase: 05
review: 05-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "`check` overwrites ninja's unit objects with objects built under its own `--cflags`/`--watcom-dir`, and `land`/`ninja verify` reuse any object on disk without checking where it came from"
  - id: IN-01
    severity: info
    disposition: open
    title: "A `static` function always fails `check`, and the messages do not say why"
  - id: IN-02
    severity: info
    disposition: deferred
    title: "Every jump-table function is refused: wcc386 puts the table before the public, outside every own public"
  - id: IN-03
    severity: info
    disposition: open
    title: "`check` skips the D-12 source checks for a unit with no game or thunk rows"
  - id: IN-04
    severity: info
    disposition: open
    title: "`configure.py --config DIR` swaps the CSVs but not the manifest"
  - id: IN-05
    severity: info
    disposition: open
    title: "The committed-CSV address parser accepts more than `0x%08X`"
open: 0
total: 6
recorded: 2026-10-24T05:48:26.387Z
---

# Phase 05: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | deferred | fails closed (jump-table functions refused, never passed); pairing the leading table with its row is Phase 6/7 work |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
