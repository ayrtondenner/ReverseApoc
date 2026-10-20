---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: deferred
    title: "Objects that share logical pages are accepted, and a patch into the second owner is silently dropped"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "The `masked_fields` count is per (patch, field), not per field, so the report over-counts"
  - id: WR-03
    severity: warning
    disposition: deferred
    title: "The output write is checked by path only, not by file identity, and is not atomic; the input is read twice"
  - id: WR-04
    severity: warning
    disposition: deferred
    title: "With `--json`, an error in any target produces no JSON and discards the results already computed"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "`configure.py --orig` reaches only `parse-le`; the new `verify` edge and `check-orig` still use the default `orig/`"
  - id: WR-06
    severity: warning
    disposition: fixed
    title: "`parse_le` passes `$in` to the shell unquoted (this predates Phase 3)"
  - id: IN-01
    severity: info
    disposition: open
    title: "The mismatch label \"page N of object M\" uses the global logical page number"
  - id: IN-02
    severity: info
    disposition: open
    title: "`_unwritable_reason` gives misleading reasons on unusual layouts"
  - id: IN-03
    severity: info
    disposition: open
    title: "`layout()` says zero-length regions are left out, but zero-length page regions are kept"
  - id: IN-04
    severity: info
    disposition: open
    title: "`docs/toolchain.md` still says the container's `orig/` holds only UFO2P.EXE and TACP.EXE"
  - id: IN-05
    severity: info
    disposition: open
    title: "The real-file test helpers copy the implementation's arithmetic instead of checking it independently"
  - id: IN-06
    severity: info
    disposition: open
    title: "A malformed TOML manifest crashes `rebuild` with a traceback"
  - id: IN-07
    severity: info
    disposition: open
    title: "`_check_bare_name` raises `SpliceError` for a manifest problem and accepts Windows device names"
  - id: IN-08
    severity: info
    disposition: open
    title: "`configure.py` still calls itself a \"Phase 2 skeleton\""
open: 8
total: 14
recorded: 2026-10-20T21:58:54.790Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | deferred | owner 2026-10-20: deferred to Phase 5 - refuse shared logical pages and overlapping objects in layout() before splice() lands real patches |
| WR-02 | warning | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 3); fixed in plan 03-06 (918b4f9, ee1dcaa), gate logs build/gate/03-06/ |
| WR-03 | warning | deferred | owner 2026-10-20: deferred to Phase 5 - samefile guard, atomic write, single read of the input before splice() lands real patches |
| WR-04 | warning | deferred | owner 2026-10-20: deferred to Phase 6 - per-target error status so --json always prints, for the Phase 6 driver |
| WR-05 | warning | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 3); fixed in plan 03-06 (918b4f9, ee1dcaa), gate logs build/gate/03-06/ |
| WR-06 | warning | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 3); fixed in plan 03-06 (918b4f9, ee1dcaa), gate logs build/gate/03-06/ |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
