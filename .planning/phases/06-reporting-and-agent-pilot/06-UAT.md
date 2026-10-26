---
status: complete
phase: 06-reporting-and-agent-pilot
source: [06-VERIFICATION.md]
started: 2026-10-26T16:05:00Z
updated: 2026-10-26T18:42:47.281Z
---

## Current Test

[testing complete]

## Tests

### 1. Fresh owner canary under the current guardrails
expected: `CANARY PASS` before any further real night (a live `claude -p` session; owner-only)
result: pass
evidence: owner canary3 (2026-10-26 13:36, after the last guardrail commit 9232499 at 11:52) ended CANARY PASS, every line PASS incl. both wrapper calls allowed under the WR-04 timeout rule (owner report, .superpowers/sdd progress.md L276); its one attempt check scored objdiff 100, bytes and relocs ok (build/driver/canary/canary3/.../checks/0001.json)

### 2. Review the 39 judgment-tier prohibitions
expected: The owner confirms the section "### Prohibitions (judgment tier, 39, all `status: resolved`)" in 06-VERIFICATION.md (39 rows, one per prohibition; the verifier's verdict is 34 held, 5 held with note, 0 not held), or names any prohibition the verdict gets wrong
result: pass
note: owner passed the table including row 5 (the in-plan timing of the 47b633d regeneration)

### 3. Look at the progress page in a browser
expected: https://ayrtondenner.github.io/ReverseApoc/ on a desktop and a phone browser, light and dark scheme, shows the per-EXE bars and function strips, the mosaic with legible labels and the "how it is measured" text; the figures equal progress.json (UFO2P 3/1553, TACP 2/1526 functions)
result: pass
note: owner confirmed light and dark mode and the new partial tooltips; figures checked by fetch of the live progress.json (UFO2P 3/1553, TACP 2/1526)
automated: Playwright on the live page (2026-10-26, commit 6d26a0a) at 1366x900 and 390x844, light and dark. Bars, strips, mosaic, legend and "How it is measured" render in both schemes; no horizontal scroll at 390 px; the figures read "3 of 1,553 functions matched, 8 partial" and "2 of 1,526 functions matched, 6 partial". Tooltips present: 14 partial ticks/cells (e.g. "func_000C6287: 53 bytes, partial, best 61.87%") and unit lines such as "...; 1 partial (best 75.00%)". At 390 px the mosaic shrinks to ~31% and its unit labels and legend are not readable (also UI-REVIEW Visuals 2/4). Only console error: a 404 for /favicon.ico.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

## Deferred Follow-Ups

- test: 3
  idea: "Phone mosaic unreadable at 390 px (labels and legend ~31% scale); owner kept the pass and deferred the fix (06-UI-REVIEW.md fix #2). Promoted to ROADMAP backlog 999.4."
  deferred_at: 2026-10-26
