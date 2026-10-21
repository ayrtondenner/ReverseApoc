---
status: testing
phase: 04-compiler-identification
source: [04-VERIFICATION.md]
started: 2026-10-21T22:56:05Z
updated: 2026-10-21T22:56:05Z
---

## Current Test

number: 1
name: Goal wording vs delivered result (exact version and default flags "known and proven")
expected: |
  Owner either accepts the result under D-08/D-10 (record the override in 04-VERIFICATION.md, or reword the
  ROADMAP goal to the D-08/D-10 bar), or reopens the phase to separate 10.6 from 11.0 and -4 from -5 before Phase 5.
  Delivered: runtime library 10.6 proven byte for byte (11 rows per EXE match only 10.6); game code 10.6 with
  10.5 byte-identical on the probe and 11.0 tied at -4r; flags: register convention, -s for most code, -fpi
  proven by scan, -4 from 5-dword rep copies (scan evidence); -o*/-zp*/-zm/-fp3/-fp5 candidate, evidence pending;
  config/cflags.txt "*  wcc386@10.6  -4r -s -fpi" (supported by the scans, not proven).
awaiting: user response

## Tests

### 1. Goal wording vs delivered result
expected: Owner accepts under D-08/D-10 (override or reworded goal) or reopens the phase (see 04-VERIFICATION.md "Verdict on the goal wording")
result: [pending]

### 2. Backstop truth (04-01): concurrent cc processes never read a half-written gate stamp
expected: Under concurrent compiles (Phase 5's first ninja -j) no compile fails or trusts a torn stamp; cc.log lines may interleave (unit tests prove the atomic swap and torn-stamp miss; no concurrent-process test exists — insufficient_spec)
result: [pending]

### 3. Judgment-tier prohibitions (31 across plans 04-01..04-12)
expected: Owner confirms the advisory LLM-judge verdicts in 04-VERIFICATION.md "Prohibitions" (all observed as held), in particular T-04-13/A1: no OWPL code or comments copied into tools/reverseapoc/wpack.py (also closes 04-SECURITY.md's one open item)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
