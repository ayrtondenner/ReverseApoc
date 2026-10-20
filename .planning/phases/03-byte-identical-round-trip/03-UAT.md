---
status: testing
phase: 03-byte-identical-round-trip
source: [03-VERIFICATION.md]
started: 2026-10-20T22:06:30Z
updated: 2026-10-20T22:06:30Z
---

## Current Test

number: 1
name: Pinned real-file facts come only from the spike READMEs (03-05 judgment-tier prohibition)
expected: |
  Every FACTS value in tests/test_splice_real.py (pages, extender end, data-pages start, padding,
  obj1 tail past vsize, trailer offset/length, straddler VAs, cut fields, fixup-kind counts) appears
  in .planning/spikes/001, 002 or 003 README.md with the same value.
awaiting: user response

## Tests

### 1. Pinned real-file facts come only from the spike READMEs (03-05 judgment-tier prohibition)
expected: Every FACTS value in tests/test_splice_real.py appears in .planning/spikes/001, 002 or 003 README.md with the same value (verifier's non-authoritative check: holds)
result: [pending]

### 2. Concurrent rebuilds can only show MISMATCH, never a false OK (03-01 backstop truth)
expected: Owner accepts the single-user-CLI argument (each run hashes the file it just wrote, so OK needs the full manifest bytes on disk), or asks for an atomic write (03-REVIEW WR-03)
result: [pending]

### 3. Triage of the six open code-review warnings (03-REVIEW-DISPOSITION.md)
expected: Each of WR-01..WR-06 is set to fixed, deferred (with reason) or skipped; verifier judgment: none breaks a Phase 3 must-have, WR-01 and WR-03 should be closed before Phase 5 feeds real patches through splice()
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
