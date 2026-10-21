---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "The `masked_fields` count is per (patch, field), not per field, so the report over-counts"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "`configure.py --orig` reaches only `parse-le`; the new `verify` edge and `check-orig` still use the default `orig/`"
  - id: WR-06
    severity: warning
    disposition: fixed
    title: "`parse_le` passes `$in` to the shell unquoted (this predates Phase 3)"
  - id: WR-07
    severity: warning
    disposition: fixed
    title: "A file name that cannot be encoded as UTF-8 truncates `build.ninja` and escapes as a traceback"
  - id: IN-09
    severity: info
    disposition: fixed
    title: "The `--orig` allowlist accepts a leading `-`, which argparse reads as an option"
  - id: IN-10
    severity: info
    disposition: fixed
    title: "Rule descriptions and header comments still say `orig/` after `--orig` points elsewhere"
  - id: IN-11
    severity: info
    disposition: fixed
    title: "`--output` does not reach the rebuild output directory, so `verify` writes `<repo>/build` whatever `builddir` says"
  - id: IN-01
    severity: info
    disposition: fixed
    title: "The mismatch label \"page N of object M\" uses the global logical page number"
  - id: IN-02
    severity: info
    disposition: fixed
    title: "`_unwritable_reason` gives misleading reasons on unusual layouts"
  - id: IN-03
    severity: info
    disposition: fixed
    title: "`layout()` says zero-length regions are left out, but zero-length page regions are kept"
  - id: IN-04
    severity: info
    disposition: fixed
    title: "`docs/toolchain.md` still says the container's `orig/` holds only UFO2P.EXE and TACP.EXE"
  - id: IN-05
    severity: info
    disposition: fixed
    title: "The real-file test helpers copy the implementation's arithmetic instead of checking it independently"
  - id: IN-06
    severity: info
    disposition: fixed
    title: "A malformed TOML manifest crashes `rebuild` with a traceback"
  - id: IN-07
    severity: info
    disposition: fixed
    title: "`_check_bare_name` raises `SpliceError` for a manifest problem and accepts Windows device names"
  - id: IN-08
    severity: info
    disposition: fixed
    title: "`configure.py` still calls itself a \"Phase 2 skeleton\""
  - id: WR-08
    severity: warning
    disposition: fixed
    title: "`_unwritable_reason` raises `TypeError` when `last_page_size` exceeds `page_size`, and the same header makes the round trip produce wrong bytes"
  - id: IN-12
    severity: info
    disposition: fixed
    title: "REFUSED and MISSING hints tell the user to run `check-orig` and `ingest` without the `--orig` and `--manifest` that produced the line"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Objects that share logical pages are accepted, and a patch into the second owner is silently dropped"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "The output write is checked by path only, not by file identity, and is not atomic; the input is read twice"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "With `--json`, an error in any target produces no JSON and discards the results already computed"
  - id: IN-13
    severity: info
    disposition: fixed
    title: "REFUSED and MISSING lines always name orig/<NAME> and config/targets.toml, whatever --orig and --manifest say"
open: 0
total: 21
recorded: 2026-10-21T03:16:11.038Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-02 | warning | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 3); fixed in plan 03-06 (918b4f9, ee1dcaa), gate logs build/gate/03-06/ |
| WR-05 | warning | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 3); fixed in plan 03-06 (918b4f9, ee1dcaa), gate logs build/gate/03-06/ |
| WR-06 | warning | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 3); fixed in plan 03-06 (918b4f9, ee1dcaa), gate logs build/gate/03-06/ |
| WR-07 | warning | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-07 (231ee0d), gate logs build/gate/03-10/ |
| IN-09 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-07 (231ee0d), gate logs build/gate/03-10/ |
| IN-10 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-07 (bf341b5), gate logs build/gate/03-10/ |
| IN-11 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-07 (bf341b5), gate logs build/gate/03-10/ |
| IN-01 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-08 (09781cf), gate logs build/gate/03-10/ |
| IN-02 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-08 (09781cf), gate logs build/gate/03-10/ |
| IN-03 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-08 (09781cf), gate logs build/gate/03-10/; proof: docstring-only change, grep for the old sentence fails at HEAD |
| IN-04 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-09 (154a73c), gate logs build/gate/03-10/; proof: docs-only change, grep fails at HEAD |
| IN-05 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-09 (e3abcc6), gate logs build/gate/03-10/; proof: test refactor, reverted mutants (no RED test) |
| IN-06 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-08 (51a6efc), gate logs build/gate/03-10/ |
| IN-07 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-08 (51a6efc), gate logs build/gate/03-10/ |
| IN-08 | info | fixed | owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-07 (bf341b5), gate logs build/gate/03-10/ |
| WR-08 | warning | fixed | owner 2026-10-21: deferred to Phase 5 - refuse last_page_size > page_size when the LE is read and handle the no-page case, so every splice refusal is a SpliceError before patches flow (regression from 03-08); owner 2026-10-21: fix now, before Phase 4; fixed in ee5cdb6, TDD, gate logs build/gate/03-leftovers/ |
| IN-12 | info | fixed | owner 2026-10-21: deferred to Phase 5 - carry --orig/--manifest into the REFUSED/MISSING check-orig and ingest hints; owner 2026-10-21: fix now, before Phase 4; fixed in 0a51a92, TDD, gate logs build/gate/03-leftovers/ |
| WR-01 | warning | fixed | owner 2026-10-20: deferred to Phase 5 - refuse shared logical pages and overlapping objects in layout() before splice() lands real patches; owner 2026-10-21: fix now, before Phase 4; fixed in 88c6a94, TDD, gate logs build/gate/03-leftovers/ |
| WR-03 | warning | fixed | owner 2026-10-20: deferred to Phase 5 - samefile guard, atomic write, single read of the input before splice() lands real patches; owner 2026-10-21: fix now, before Phase 4; fixed in d4de0d8 (+2493b95 shared hash helpers), TDD, gate logs build/gate/03-leftovers/ |
| WR-04 | warning | fixed | owner 2026-10-20: deferred to Phase 6 - per-target error status so --json always prints, for the Phase 6 driver; owner 2026-10-21: fix now, before Phase 4; fixed in 2eea90f (+2493b95 name once in ERROR lines), TDD, gate logs build/gate/03-leftovers/ |
| IN-13 | info | fixed | renamed from VN-01 (owner 2026-10-21); verifier note, 03-VERIFICATION.md (tools/reverseapoc/splice.py:527, :531); owner 2026-10-20: fix now (Phase 3 gap closure, UAT test 6); fixed in plan 03-08 (09781cf), gate logs build/gate/03-10/ (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
