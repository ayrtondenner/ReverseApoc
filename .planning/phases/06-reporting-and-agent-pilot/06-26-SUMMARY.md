---
phase: 06-reporting-and-agent-pilot
plan: 26
subsystem: driver
tags: [pilot, checkpoint, drive, canary, cli-pin, pages, spike-005, d-27, d-36, d-37, d-41, d-48]
status: complete

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-25 drive verb (preflight, dry run, canary, end-of-run ninja verify + gate --all); 06-24 Pages workflow and gated DecompHub POST; 06-19..06-22 hooks, skill, pack, listing drafts"
provides:
  - "Session-free preflight evidence on the main checkout (gitignored build/gate/06-evidence/): container uv sync, dry run 20261025-213752 (10 picks, 5 + 5), a real wrapper `attempt check`, a baseline `gate --all`"
  - "The owner-run pilot, run 20261026-005209: 40 sessions, 3 MATCHED (2 UFO2P + 1 TACP), each its own commit with the `Matched-By: reverseapoc drive` trailer, end-of-run ninja verify and gate --all ok, quarantine empty"
  - "Fix b221245: the driver's session settings switch off the three built-in plugins that CLI 2.1.308 loads by default"
affects: [06-27 phase gate (judges run 20261026-005209 against D-37 and re-gates every match commit)]

actuals:
  tokens: 9700    # chars/4 over git diff b457bbb..398515d (38,792 chars), which includes the owner's run commits; the executor's own diff is b221245 (12,276 chars, ~3,100) plus this SUMMARY
  tasks: 2
  commits: 5      # measured: git rev-list --count b457bbb..HEAD before this SUMMARY commit = b221245 (fix) + c83cf4e, d288ad6, 955931f, 398515d (the owner's drive run)
plan_head_before: b457bbb9e86c5acc2e80a2fa01a2c5b8620503b0
plan_head_after: 398515d9af340170595e6d92a919584397f0d61c

tech-stack:
  added: []
  patterns:
    - "CLI built-in plugins are switched off per key in the session settings (`\"<alias>@builtin\": false`, short alias); the init check stays strict (plugins == [])"

key-files:
  created: []
  modified:
    - config/driver/claude-settings.json
    - tools/reverseapoc/driver.py
    - tests/test_drive.py
    - tests/test_hooks.py
    - docs/workflow.md

key-decisions:
  - "Keep the strict init check (plugins == []) and switch off the CLI's built-in plugins in config/driver/claude-settings.json instead of relaxing the check; two owner one-turn probes proved the short `<alias>@builtin` key form (probe 2: plugins [], mcp [])"
  - "The canary prints PASS lines for the containers-removed and unknown-event checks too, so a passing canary shows every check (workflow.md said it did; before b221245 those two printed only on failure)"
  - "`gh api .../pages` reaches the network, so no agent runs it: the Pages source is owner-confirmed and the deploy check (G14) stays with the owner"
  - "requirements-completed stays empty: AGT-11 (10 matched) is judged by 06-27 against D-37 and the run reached 3; RPT-03 waits on the owner's Pages deploy check; RPT-05 waits on the listings, which the owner has not sent yet. REQUIREMENTS.md is not edited"

patterns-established:
  - "An owner-run session step is verified afterwards from the attempt log and git only, never by running claude, drive or gh from the executor"

requirements-completed: []  # plan frontmatter: [AGT-11, RPT-03, RPT-05]; none verifiably complete here (see key-decisions); 06-27 also declares all three

coverage:
  - id: D1
    description: "Session-free preflight on the main checkout: uv sync, dry run with 5 + 5 picks, real wrapper attempt check, gate --all, tree clean"
    verification:
      - kind: other
        ref: "Task 1 <automated> verify over build/gate/06-evidence/01..04 (exit=0 each, 02-dryrun.exit 0, 10 picks 5+5, max 2 per unit, porcelain empty)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The owner upgraded the CLI to 2.1.308, set Pages to GitHub Actions, signed off spike 005, passed the canary (canary2) and ran the pilot (run 20261026-005209, 3 matched), then pushed main"
    requirement: AGT-11
    verification:
      - kind: other
        ref: "progress/attempts.jsonl last record (run ENDED, max sessions, 40 sessions, 3 matched, checks_failed [], uncommitted []); cli_version 2.1.308 on all 40 attempt records; git log --grep='^Matched-By: reverseapoc drive$'"
        status: pass
    human_judgment: true
    rationale: "Whether 3 matched out of a target of 10 meets D-37 is judged in 06-27; the canary, the CLI upgrade, the Pages setting and the push are owner-side facts taken from the owner's report"
  - id: D3
    description: "Pages deploy after the push, and the listings and DecompHub claim"
    requirement: RPT-03
    verification: []
    human_judgment: true
    rationale: "Network and third-party state: no agent runs gh api or opens the listings; the owner checks the Pages deploy (G14) and sends the listings"

duration: "Task 1 ~1h (2026-10-25); continuation 10 min (2026-10-26)"
completed: 2026-10-26
---

# Phase 6 Plan 26: Pilot checkpoint Summary

**The owner-run pilot on CLI 2.1.308 (run 20261026-005209) matched 3 functions in 40 sessions (2 UFO2P, 1 TACP), each its own drive commit. The run ended on max sessions with no failed check, both EXEs SHA-1 identical and quarantine empty. Before the run, fix b221245 switched off the CLI's three default-on built-in plugins, which had failed canary1.**

## Performance

- **Duration:** Task 1 on 2026-10-25 (previous executor, no commit); continuation (verification + SUMMARY) about 10 min on 2026-10-26
- **Started:** 2026-10-25 (Task 1 preflight, base b457bbb)
- **Completed:** 2026-10-26T09:10Z
- **Tasks:** 2 of 2 (Task 1 executor; Task 2 owner checkpoint, now verified)
- **Files modified:** 5 by fix b221245; 3 by the owner's run (config/ufo2p/status.csv, config/tacp/status.csv, progress/attempts.jsonl) plus the matched source units; this SUMMARY

## Owner's report (verbatim)

> pilot done: run 20261026-005209, 3 matched; claude 2.1.308; canary PASS (canary2); Spike 005 VALIDATED, confirmed by the owner on 2026-10-25 -> PUSHED

Push output: `e938fff..398515d  main -> main`.

Owner steps:

| Step | What | Result |
|------|------|--------|
| 1 | `claude install stable` | 2.1.308, native `C:\Users\Ayrton\.local\bin\claude.exe` (major 2, at least 2.1.302: D-36 met) |
| 2 | Pages Source = GitHub Actions | done, owner-confirmed. `DECOMPHUB_REFRESH` (optional) not set, or not reported |
| 3 | Spike 005 sign-off | "Spike 005 VALIDATED, confirmed by the owner on 2026-10-25" |
| 4 | Listings: three PRs, decomp.me issue, DecompHub claim | not reported: open, non-blocking (the owner sends them once the Pages page loads) |
| 5 | Canary | canary1 FAIL (built-in plugins, see Deviations); canary2 at b221245: `CANARY PASS` |
| 6 | Pilot | run 20261026-005209, `ENDED max sessions: 40 sessions, 3 matched` |
| 7 | Push | `e938fff..398515d  main -> main` |

## Task 1 evidence (session-free preflight, build/gate/06-evidence/, gitignored)

- `01-uvsync.log`: `Checked 8 packages in 4ms`, `exit=0`.
- `02-dryrun.json` / `02-dryrun.exit` = `0`: dry run 20261025-213752, 10 picks, 5 ufo2p + 5 tacp, at most 2 per unit (ufo2p u_00089980 x2, u_00026dd0, u_0004dfd0, u_00060c50; tacp u_0006ee30, u_00032980, u_000778d0, u_0006fbd0, u_00071bd0).
- `03-attempt-check.log`: `attempt check 1/25, 4 s (24 left) ufo2p/u_000a34f0 func_000A3980: exit 0 OK: the claimed function matches and its unit passes check`, `func_000A3980  0x000A3980  objdiff 100%  reloc ok  bytes ok`, `splice UFO2P.EXE ok`, `splice TACP.EXE ok`, `exit=0`.
- `04-gate-all.log`: gate --all ok (both SHA-1s), `exit=0`.
- Task 1 `<automated>` verify exited 0 and the tree was clean at b457bbb (recorded by the previous executor and re-checked by the orchestrator).

## Task 2 verification (read-only, 2026-10-26)

| Check | Result | Evidence |
|-------|--------|----------|
| CLI version (claude not run, by ruling) | 2.1.308, major 2, at least 2.1.302 | Owner's line; `cli_version` = "2.1.308" on all 40 attempt records of run 20261026-005209 (model claude-opus-5-5 on all 40) |
| Match commits | 3 | `git log --format='%h %s' --grep="^Matched-By: reverseapoc drive$"`: `955931f feat(ufo2p): match func_0008A100 in u_00089980 (C89)`, `d288ad6 feat(tacp): match func_0006EE30 in u_0006ee30 (C89)`, `c83cf4e feat(ufo2p): match func_0008A0E0 in u_00089980 (C89)`. HEAD `398515d chore(driver): attempt log` (status.csv x2 + attempts.jsonl, +51 lines) is the run's closing commit; it has no Matched-By trailer, so the grep does not list it |
| Last attempt-log record | run ENDED | `{"kind":"run","run":"20261026-005209","event":"ENDED","reason":"max sessions","detail":null,"sessions":40,"matched":3,"checks_failed":[],"uncommitted":[],"date":"2026-10-26"}` |
| Pages (`gh api` not run: network) | owner-confirmed | Source = GitHub Actions set by the owner (step 2); the deploy check after the push (G14) is the owner's |
| End-of-run ninja verify | ok | `build/driver/20261026-005209/end-ninja-verify.log`: `exit 0`; `OK UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest`, `OK TACP.EXE sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest`, `OK SMKP.EXE sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest`; landed 3 (UFO2P) and 2 (TACP) |
| End-of-run gate --all | ok | `end-gate-all.log`: `exit 0`, `"ok": true`, `"exit_code": 0`, both EXE entries `"ok": true`, `"refused": []` |
| Quarantine | empty | `build/driver/20261026-005209/quarantine/` holds 0 entries |
| Attempt counts | 40 = 3 MATCHED + 37 PARTIAL | 3 PARTIAL had `abort_reason` "lint"; ufo2p 2 MATCHED / 19 PARTIAL over 8 functions, tacp 1 MATCHED / 18 PARTIAL over 7 functions (15 functions); 12 functions used all 3 attempts |
| Cost and time | USD 42.93, 19,565.5 s | sum of `cost_usd` = 42.9258; sum of `seconds` = 19565.5 (about 5.4 h of session time) |
| Best partials | facts only | tacp func_00071CE0 87.5%, tacp func_00095850 87.2%, ufo2p func_00026FD0 80.4% |
| Working tree | clean apart from the orchestrator's flag | `git status --porcelain` = ` M .planning/config.json` (the orchestrator's temporary setting), HEAD 398515d |

Against the plan's numbers, as facts: the target was 10 MATCHED and the run reached 3 (2 UFO2P, 1 TACP), ending on the 40-session ceiling. Plan 06-27 judges this against D-37; this SUMMARY does not.

## Accomplishments

- The preflight ran without any agent session: uv sync, dry run, a real wrapper check and gate --all, all exit 0.
- The owner pinned the CLI at 2.1.308, set the Pages source, signed off spike 005, passed the canary on the second try and ran the pilot: 3 functions matched unattended, each its own commit, with no failed check, nothing uncommitted and both EXEs identical at the end.
- The canary caught the CLI's new built-in plugins before any night. The fix keeps the strict init gate.

## Task Commits

1. **Task 1: session-free preflight**: no commit (gitignored evidence under build/gate/06-evidence/)
2. **Task 2: owner checkpoint**: the owner's run made `c83cf4e`, `d288ad6`, `955931f` (feat, Matched-By trailer) and `398515d` (chore, attempt log)

Deviation fix: `b221245` (fix(06-26): switch off CLI built-in plugins in driver sessions)

**Plan metadata:** this docs(06-26) commit

## Files Created/Modified

- `config/driver/claude-settings.json`: three `"<alias>@builtin": false` keys (b221245)
- `tools/reverseapoc/driver.py`: canary PASS lines for the containers-removed and unknown-event checks (b221245)
- `tests/test_drive.py`, `tests/test_hooks.py`: RED then GREEN tests for both (b221245)
- `docs/workflow.md`: init bullet and open assumption 7, future built-ins (b221245)
- `.planning/phases/06-reporting-and-agent-pilot/06-26-SUMMARY.md`: this file

## Decisions Made

See key-decisions in the frontmatter. In short: keep the init gate strict, switch off the built-ins in the session settings, show every canary check as a PASS line, and leave network checks to the owner.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The driver session loaded the CLI's built-in plugins, so canary1 failed**
- **Found during:** Task 2 (owner checkpoint, step 5)
- **Issue:** canary1 failed on one check only: `init: plugins loaded: cc-plugin-agents-md, cc-plugin-telemetry, cc-plugin-plugin-authoring`. Every guardrail check passed. CLI 2.1.308 ships built-in plugins that are on by default (`path: builtin`, source `<name>@builtin`). `--setting-sources project`, `--strict-mcp-config` and the driver's enabledPlugins do not cover them, and the init check requires plugins == [], so a night would have stopped as well. Separately, the containers-removed and unknown-event checks printed only on failure, which contradicted workflow.md.
- **Fix:** two owner one-turn probes. Probe 1: the `@builtin` false keys remove the cc-plugin-* entries. Probe 2: the driver's enabledPlugins plus the short-form keys only give `plugins: []`, `mcp: []`. Then three short-form `@builtin` false keys in config/driver/claude-settings.json, PASS lines for the two silent canary checks, and workflow.md notes plus open assumption 7.
- **Files modified:** config/driver/claude-settings.json, tools/reverseapoc/driver.py, tests/test_drive.py, tests/test_hooks.py, docs/workflow.md
- **Verification:** the fix executor's host suite gave 2727 passed / 35 skipped, ruff clean; the orchestrator reran test_drive + test_hooks (282 passed); canary2 at b221245 printed every PASS line, including init "no plugin" and the two new lines, then `CANARY PASS`. The container suite was not run for this commit; the 06-27 phase gate covers it.
- **Committed in:** b221245

---

**Total deviations:** 1 auto-fixed (1 bug, Rule 1)
**Impact on plan:** needed before any unattended session; the init gate was not weakened. No scope creep.

## Issues Encountered

- The owner's canary2 paste had no "attempt check was called" line. This is most likely a copy glitch: CANARY PASS requires every check, and checks.jsonl logged exit 0. Recorded here; nothing changed.
- The owner did not report the drive exit code. The ENDED record with `checks_failed []` and `uncommitted []` implies exit 0 (orchestrator ruling).

## Open items (non-blocking)

- **Listings (step 4):** the three PRs, the decomp.me preset issue and the DecompHub maintainer claim are not sent yet. The owner sends them once the Pages page loads.
- **`DECOMPHUB_REFRESH`:** the optional repository variable (D-30) was not set, or not reported.
- **G14 Pages deploy:** the owner checks that the push `e938fff..398515d` deployed the Pages site. No agent runs `gh api`.
- **Owner's idea, queued:** timestamp every `drive` console line (TDD; a candidate for a 06-27 deviation or a quick task).

## User Setup Required

The plan's user_setup items were done by the owner (CLI, Pages), except the optional `DECOMPHUB_REFRESH` and the DecompHub claim (open, above). No USER-SETUP.md generated: the checkpoint was the setup.

## STATE / ROADMAP / requirements

- ROADMAP.md: plan progress updated from disk (06-26 has its SUMMARY).
- REQUIREMENTS.md: not edited. The ready-ids gate blocks AGT-11, RPT-03 and RPT-05 because 06-27 declares them too and has no SUMMARY; none is verifiably complete here.
- STATE.md: not edited. In this phase the orchestrator owns STATE centrally: its counter still reads "Plan 1 of 27", so `state.advance-plan` would write a wrong position.

## Next Phase Readiness

- Ready for 06-27: the phase gate judges run 20261026-005209 (3 MATCHED of a target of 10, ended on max sessions) against D-37, re-gates c83cf4e, d288ad6 and 955931f, and runs both suites, including the container run for b221245.
- No tick-rate finding (OpenApoc #997) in this plan or in the run's logs.

## Self-Check: PASSED

- Commits b221245, c83cf4e, d288ad6, 955931f and 398515d are ancestors of HEAD (`git rev-list --count b457bbb..HEAD` = 5 before this SUMMARY).
- Evidence files exist: build/gate/06-evidence/01-uvsync.log, 02-dryrun.json, 02-dryrun.exit, 03-attempt-check.log, 04-gate-all.log; build/driver/20261026-005209/end-ninja-verify.log, end-gate-all.log; quarantine/ is empty.
- No modification to orig/, config/targets.toml, the hash manifests or the build scripts. claude, drive, docker, gh and the network were not used by this executor.

Execution context nonce: 41abe89ceb1e17a0

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-26*
