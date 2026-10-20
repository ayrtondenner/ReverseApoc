---
status: testing
phase: 03-byte-identical-round-trip
source: [03-VERIFICATION.md]
started: 2026-10-20T22:06:30Z
updated: 2026-10-20T23:19:34Z
---

## Current Test

number: 4
name: 03-06 changed nothing outside WR-02, WR-05 and WR-06 (judgment-tier prohibition)
expected: |
  `git diff 9158a03 HEAD -- tools/reverseapoc/splice.py tools/reverseapoc/cli.py` shows only the
  masked-count line (splice.py:635) and two comments; cli.py is unchanged; configure.py's HEADER
  comments and descriptions are byte-identical apart from the two `--orig {orig}` command lines.
awaiting: user response

## Tests

### 1. Pinned real-file facts come only from the spike READMEs (03-05 judgment-tier prohibition)
expected: Every FACTS value in tests/test_splice_real.py appears in .planning/spikes/001, 002 or 003 README.md with the same value (verifier's non-authoritative check: holds)
result: pass

### 2. Concurrent rebuilds can only show MISMATCH, never a false OK (03-01 backstop truth)
expected: Owner accepts the single-user-CLI argument (each run hashes the file it just wrote, so OK needs the full manifest bytes on disk), or asks for an atomic write (03-REVIEW WR-03)
result: pass

### 3. Triage of the six open code-review warnings (03-REVIEW-DISPOSITION.md)
expected: Each of WR-01..WR-06 is set to fixed, deferred (with reason) or skipped; verifier judgment: none breaks a Phase 3 must-have, WR-01 and WR-03 should be closed before Phase 5 feeds real patches through splice()
result: issue
reported: "Can we do the following: Fix now: 02, 05, 06 / 01 and 03: fix during Phase 5 / 04: fix during phase 6"
severity: major

### 4. 03-06 changed nothing outside WR-02, WR-05 and WR-06 (judgment-tier prohibition)
expected: `git diff 9158a03 HEAD -- tools/reverseapoc/splice.py tools/reverseapoc/cli.py` shows only the masked-count line (splice.py:635) and two comments; cli.py unchanged; configure.py HEADER comments/descriptions byte-identical apart from the two `--orig {orig}` command lines (verifier's non-authoritative check: holds)
result: [pending]

### 5. 03-06 did not edit orig/, config/ or the Docker files, nor configure.py during the gate (judgment-tier prohibition)
expected: no commit after 918b4f9 touches configure.py; gate logs stamped after it; `git diff 9158a03 HEAD -- config docker compose.yaml` empty; orig/ SHA-1s equal the manifest (verifier's non-authoritative check: holds)
result: [pending]

### 6. Triage of the open review findings after the re-review (03-REVIEW-DISPOSITION.md)
expected: WR-07, IN-09, IN-10, IN-11 (and the still-open IN-01..IN-08) each set to fix now, deferred (with phase/reason) or skipped; verifier judgment: none breaks a Phase 3 must-have; WR-07 is a real hole next to the WR-06 contract but cannot occur with the three ASCII-named targets
result: [pending]

## Summary

total: 6
passed: 2
issues: 1
pending: 3
skipped: 0
blocked: 0

## Gaps

- gap_id: G-03-3
  truth: "Code-review warnings WR-02, WR-05 and WR-06 are fixed in Phase 3 (owner triage, UAT test 3)"
  status: resolved
  reason: "User reported: Can we do the following: Fix now: 02, 05, 06 / 01 and 03: fix during Phase 5 / 04: fix during phase 6"
  severity: major
  test: 3
  resolved_by: 03-06-PLAN.md
  resolved_at: 2026-10-20
  root_cause: "WR-02: splice.py:634 counts len(result.masked), one MaskedField per (patch, fixup), so a field split by k touching patches counts k in the text line and JSON masked_fields. WR-05: configure.py render() has no orig parameter and the check_orig/rebuild rule commands are constant text without --orig, so --orig reaches only parse-le. WR-06 (mechanism corrected by diagnosis): not shell injection, ninja shell-quotes $in; configure.py ninja_path escapes only $, space and colon and find_executables accepts any *.exe name, so a name with |, LF or CR (unrepresentable in ninja 1.11) corrupts build.ninja; WR-05 fix adds a literal --orig dir that ninja does not quote."
  artifacts:
    - path: "tools/reverseapoc/splice.py"
      issue: "rebuild_target masked count (line 634) counts (patch, field) entries, not distinct fields"
    - path: "configure.py"
      issue: "render() lacks the orig dir; HEADER rule commands omit --orig; ninja_path/find_executables accept names ninja cannot represent"
    - path: "tests/test_splice.py"
      issue: "no case where one fixup field is touched by several patches"
    - path: "tests/test_configure.py"
      issue: "line 73 pins the WR-05 bug (exact unqualified rebuild command); no test for --orig reaching the rules or for unrepresentable names"
  missing:
    - "Count distinct fixups for masked_fields (key name and SpliceResult.masked shape unchanged) with touching-patch, three-patch, straddling and two-field control tests"
    - "Pass the orig dir into render() and emit --orig <dir> in check_orig and rebuild commands; update test_configure.py:73 deliberately"
    - "Refuse exe names containing |, LF or CR and an --orig dir with characters unsafe on host and container, with a clear configure error; keep parse-le $in unquoted and names with spaces working"
  debug_session: ".planning/debug/phase3-wr02-wr05-wr06.md"

## Deferred Follow-Ups

- test: 3
  idea: "WR-01 (layout() must refuse shared logical pages and overlapping objects) and WR-03 (samefile guard, atomic write, single input read): fix during Phase 5, before splice() lands real patches"
  deferred_at: 2026-10-20
- test: 3
  idea: "WR-04 (per-target error status so rebuild --json always prints): fix during Phase 6, for the driver"
  deferred_at: 2026-10-20
