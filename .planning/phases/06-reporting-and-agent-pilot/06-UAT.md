---
status: testing
phase: 06-reporting-and-agent-pilot
source: [06-VERIFICATION.md]
started: 2026-10-26T16:05:00Z
updated: 2026-10-26T16:05:00Z
---

## Current Test

number: 1
name: Fresh owner canary under the current guardrails
expected: |
  `uv run reverseapoc drive --canary --run <fresh id>` ends with `CANARY PASS` before any further real night. The
  guardrails changed after canary2 and the pilot: frontend-design is switched off in driver sessions (fe7149c); a match
  needs the claimed row (CR-01, 02f513e); a path `#include` is refused by the hook, configure, check, gate and land
  (CR-02); the always hook fails closed on a timeout (WR-02); the matching hook denies an `attempt check` sent without
  a Bash timeout of 600000 (WR-04).
awaiting: user response

## Tests

### 1. Fresh owner canary under the current guardrails
expected: `CANARY PASS` before any further real night (a live `claude -p` session; owner-only)
result: [pending]

### 2. Review the 39 judgment-tier prohibitions
expected: The owner confirms the section "### Prohibitions (judgment tier, 39, all `status: resolved`)" in 06-VERIFICATION.md (39 rows, one per prohibition; the verifier's verdict is 34 held, 5 held with note, 0 not held), or names any prohibition the verdict gets wrong
result: [pending]

### 3. Look at the progress page in a browser
expected: https://ayrtondenner.github.io/ReverseApoc/ on a desktop and a phone browser, light and dark scheme, shows the per-EXE bars and function strips, the mosaic with legible labels and the "how it is measured" text; the figures equal progress.json (UFO2P 3/1553, TACP 2/1526 functions)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
