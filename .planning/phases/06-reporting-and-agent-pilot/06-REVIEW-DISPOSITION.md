---
phase: 06
review: 06-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "A gate pass is recorded and committed as a match for the claimed function even when that function was never matched"
  - id: CR-02
    severity: critical
    disposition: fixed
    title: "The no-`#pragma` / no-inline-asm guardrail is bypassed by `#include` of an agent-writable, unscanned file"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "ci.yml checkout keeps the job token in `.git/config` while repository and PR code runs (known item from 06-24)"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "The always-layer hook has no timeout/onFailure, so a slow or hung hook does not fail closed"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "`gate --partial` keeps an older partial row's date (and reports it as written), so a function attempted today stays eligible today"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "A Bash-tool timeout kills the attempt wrapper mid-run and leaves `check.lock` behind, ending every later check of the attempt"
  - id: IN-01
    severity: info
    disposition: fixed
    title: "A sweep with no measured cell logs `best_percent` 0.0, not null"
  - id: IN-02
    severity: info
    disposition: fixed
    title: "A failed lint is recorded as PARTIAL even when no check scored above 0%"
  - id: IN-03
    severity: info
    disposition: fixed
    title: "Tests that assert on docstring wording"
  - id: IN-04
    severity: info
    disposition: deferred
    title: "Workflow actions are pinned by tag, not by commit SHA"
open: 0
total: 10
recorded: 2026-10-26
---

# Phase 06: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | 0b96364, plus the refused-restore test 67ec06f |
| CR-02 | critical | fixed | 3457f72, completed by de724a8 (check, gate and land refuse a path include before compiling), e7ae703, 3a00807, 27f30d6 |
| WR-01 | warning | fixed | 23ce78f |
| WR-02 | warning | fixed | 15a9398 |
| WR-03 | warning | fixed | 3fc9c68 |
| WR-04 | warning | fixed | 8da5c2c, plus the canary fixtures 48bdb3b |
| IN-01 | info | fixed | 8bd7ed4 |
| IN-02 | info | fixed | 31fe0a9 |
| IN-03 | info | fixed | f8e6577 |
| IN-04 | info | deferred | SHA pinning needs network lookups and is an owner supply-chain decision; kept as a residual in 06-SECURITY.md |

Fix verification: a fresh SDD re-reviewer, r1, found 8 of 9 fixes closed, with a gap in the CR-02 gate. Round 2 closed it and r2 APPROVED. Round 3 minors were diff-checked by the orchestrator. Host suite after round 3: 2862 passed, 35 skipped; ruff clean.

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
