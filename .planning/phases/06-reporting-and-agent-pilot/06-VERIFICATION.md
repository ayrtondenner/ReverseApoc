---
phase: 06-reporting-and-agent-pilot
verified: 2026-10-26T15:56:03Z
status: human_needed
score: 9/10 must-haves verified (1 of the 9 is an owner override, SC5b, the pilot count, partial 3/10; 1 present, behavior-unverified)
covered_files: [".claude/settings.json",".claude/skills/watcom-decomp/SKILL.md",".dockerignore",".github/workflows/ci.yml",".github/workflows/pages.yml",".gitignore",".planning/phases/06-reporting-and-agent-pilot/06-01-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-01-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-02-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-02-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-03-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-03-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-04-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-04-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-05-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-05-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-06-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-06-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-07-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-07-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-08-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-08-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-09-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-09-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-10-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-10-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-11-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-11-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-12-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-12-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-13-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-13-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-14-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-14-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-15-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-15-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-16-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-16-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-17-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-17-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-18-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-18-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-19-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-19-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-20-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-20-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-21-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-21-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-22-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-22-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-23-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-23-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-24-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-24-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-25-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-25-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-26-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-26-SUMMARY.md",".planning/phases/06-reporting-and-agent-pilot/06-27-PLAN.md",".planning/phases/06-reporting-and-agent-pilot/06-27-SUMMARY.md",".recomp.json","README.md","config/driver/claude-settings.json","config/tacp/functions.csv","config/tacp/status.csv","config/ufo2p/functions.csv","config/ufo2p/status.csv","config/watcom.toml","configure.py","decomphub.progress.json","docker/Dockerfile","docs/DECOMPHUB_VERIFICATION.md","docs/coding-style.md","docs/learnings.md","docs/legal.md","docs/listings.md","docs/matching.md","docs/superpowers/specs/2026-10-19-reverseapoc-design.md","docs/toolchain.md","docs/tools.md","docs/workflow.md","progress/attempts.jsonl","src/tacp/u_00054f20.c","src/tacp/u_0006ee30.c","src/ufo2p/u_00089980.c","tests/fakeclaude.py","tests/fixtures/stream/auth.jsonl","tests/fixtures/stream/bad_init_extra_tool.jsonl","tests/fixtures/stream/bad_init_mcp.jsonl","tests/fixtures/stream/bad_init_model.jsonl","tests/fixtures/stream/bad_init_no_bash.jsonl","tests/fixtures/stream/bad_init_old.jsonl","tests/fixtures/stream/bad_init_plugin.jsonl","tests/fixtures/stream/bad_init_v1.jsonl","tests/fixtures/stream/bad_init_v3.jsonl","tests/fixtures/stream/billing.jsonl","tests/fixtures/stream/canary_fail.jsonl","tests/fixtures/stream/canary_pass.jsonl","tests/fixtures/stream/canary_unknown_error.jsonl","tests/fixtures/stream/canary_wrapper_denied.jsonl","tests/fixtures/stream/cloud_credential.jsonl","tests/fixtures/stream/credits.jsonl","tests/fixtures/stream/during_execution.jsonl","tests/fixtures/stream/hold.jsonl","tests/fixtures/stream/http429.jsonl","tests/fixtures/stream/limit_text.jsonl","tests/fixtures/stream/low_credit_text.jsonl","tests/fixtures/stream/malformed.jsonl","tests/fixtures/stream/max_budget.jsonl","tests/fixtures/stream/max_turns.jsonl","tests/fixtures/stream/no_result.jsonl","tests/fixtures/stream/not_logged_in.jsonl","tests/fixtures/stream/oauth.jsonl","tests/fixtures/stream/overloaded.jsonl","tests/fixtures/stream/overloaded_result.jsonl","tests/fixtures/stream/rate_limit.jsonl","tests/fixtures/stream/rejected.jsonl","tests/fixtures/stream/server_error.jsonl","tests/fixtures/stream/success.jsonl","tests/relocpair.py","tests/test_asm.py","tests/test_attempt_wrapper.py","tests/test_attempts_schema.py","tests/test_cc_log.py","tests/test_check.py","tests/test_check_tables_real.py","tests/test_cli.py","tests/test_compiler.py","tests/test_compiler_real.py","tests/test_configure.py","tests/test_contextpack.py","tests/test_discover.py","tests/test_drift.py","tests/test_drive.py","tests/test_drive_real.py","tests/test_driver.py","tests/test_driver_pick.py","tests/test_fileio.py","tests/test_functions.py","tests/test_functions_real.py","tests/test_gate.py","tests/test_gate_real.py","tests/test_ghidra.py","tests/test_hooks.py","tests/test_hygiene.py","tests/test_land.py","tests/test_le.py","tests/test_lint.py","tests/test_listings.py","tests/test_objdiff_real.py","tests/test_omf2elf.py","tests/test_progress.py","tests/test_progress_page.py","tests/test_relocs.py","tests/test_report_shape.py","tests/test_score.py","tests/test_session.py","tests/test_skill.py","tests/test_status.py","tests/test_streamjson.py","tests/test_stub_real.py","tests/test_symbols.py","tests/test_target.py","tests/test_treemap.py","tests/test_units.py","tests/test_workflows.py","tests/test_x86.py","tools/progress.py","tools/reverseapoc/asm.py","tools/reverseapoc/attempt.py","tools/reverseapoc/check.py","tools/reverseapoc/cli.py","tools/reverseapoc/compiler.py","tools/reverseapoc/contextpack.py","tools/reverseapoc/discover.py","tools/reverseapoc/driver.py","tools/reverseapoc/fileio.py","tools/reverseapoc/functions.py","tools/reverseapoc/gate.py","tools/reverseapoc/ghidra_scripts/ExportDrafts.java","tools/reverseapoc/hooks.py","tools/reverseapoc/land.py","tools/reverseapoc/libmatch.py","tools/reverseapoc/lint.py","tools/reverseapoc/omf2elf.py","tools/reverseapoc/picker.py","tools/reverseapoc/relocs.py","tools/reverseapoc/score.py","tools/reverseapoc/session.py","tools/reverseapoc/splice.py","tools/reverseapoc/status.py","tools/reverseapoc/streamjson.py","tools/reverseapoc/symbols.py","tools/reverseapoc/target.py","tools/reverseapoc/x86.py"]
covered_digest: "v3:sha256:f038c33e1a9d162a623799901a9d539d9245d996e6c67cdbea3e5d937f142898"
behavior_unverified: 1
overrides_applied: 1
overrides:
  - must_have: "An unattended pilot run matches 10 easy functions (D-37: at least 3 per EXE)"
    reason: "PARTIAL pilot accepted by the owner. Run 20261026-005209 reached 3 MATCHED (ufo2p func_0008A0E0, tacp func_0006EE30, ufo2p func_0008A100; 2 UFO2P + 1 TACP) at D-37's 40-session ceiling, about USD 14 per match. Every other D-37 condition held: one commit per match, the D-24 gate after every commit, no guardrail breach, a complete attempt log. The 10-match target carries to Phase 7. AGT-11 stays Pending in REQUIREMENTS.md (F39). This is a recorded deviation, not a pass."
    accepted_by: "ayrtondenner (owner ruling, rulings.md '06-27 owner ruling'; STATE.md Decisions; 06-VALIDATION.md AGT-11 row)"
    accepted_at: "2026-10-26T00:00:00Z"
behavior_unverified_items:
  - truth: "The guardrails as they stand at 060a001 hold in a real `claude -p` matching session. CR-02 (include rule), WR-02 (always-hook timeout/onFailure) and WR-04 (an `attempt check` is denied unless the Bash tool's timeout is 600000) changed hook behaviour after the pilot and after canary2"
    test: "Owner: `uv run reverseapoc drive --canary --run <fresh id>` before the next real night (docs/workflow.md 'Before you start')"
    expected: "Last line `CANARY PASS`. The protected writes and `ls` are denied, and `attempt context` and `attempt check` (sent with timeout 600000) are allowed and run"
    why_human: "tests/test_hooks.py exercises decide() on synthetic payloads, and the canary fixtures (a446a3c) are synthetic too. Whether the real CLI's Bash tool_input carries `timeout` as the skill instructs, so that WR-04 does not deny every check, shows only in a live session, and execution never runs a real claude"
human_verification:
  - test: "Fresh owner canary under the current guardrails (see behavior_unverified_items)"
    expected: "CANARY PASS before any further real night"
    why_human: "Live claude -p session; owner-only (subscription, HARD rule against real claude in execution)"
  - test: "Review the 32 judgment-tier prohibitions in the 06-01..06-27 PLAN frontmatter (all `status: resolved`, `verification: judgment`). The table 'Prohibitions (judgment tier)' below gives the verifier's verdict on each group"
    expected: "Owner confirms, or names any prohibition the verdict gets wrong"
    why_human: "ADR-550 D4: a judgment-tier prohibition is never a silent pass, and the verifier's LLM verdict is not authoritative"
  - test: "Open https://ayrtondenner.github.io/ReverseApoc/ in a desktop and a phone browser, light and dark scheme"
    expected: "Per-EXE bars and function strips, the mosaic with legible labels, the 'how it is measured' text; figures equal progress.json (UFO2P 3/1553, TACP 2/1526 functions)"
    why_human: "Visual layout and contrast (ROADMAP UI hint: yes). 33-live.log proves only HTTP 200s"
---

# Phase 6: Reporting and agent pilot Verification Report

**Phase Goal:** Progress is published from gate-written data, and an unattended per-function driver matches easy functions under guardrails, with the build, never the agent, deciding each match.
**Verified:** 2026-10-26T15:56:03Z, at HEAD 43c7fd9 (code at 060a001)
**Status:** human_needed
**Re-verification:** No, initial verification. No earlier 06-VERIFICATION.md exists.

## Verdict in one paragraph

The reporting half and the driver half are in the code, wired, and pass their tests. Both post-pilot blockers are closed in the code, with named tests that I ran green. CR-01: the driver now counts a match only when the container gate wrote a matched row for the claimed function. CR-02: an `#include` must name a bare header, in the hook and in configure's D-12 check. The real pilot ran unattended, made one commit per match, and broke nothing: every match commit re-gated with both SHA-1s identical, and the final tree passes from clean. **The pilot fell short of its count: 3 of 10, and 1 TACP against D-37's 3 per EXE.** The owner accepted this as PARTIAL on 2026-10-26. I record it as an override (a deviation), not as VERIFIED, and AGT-11 stays Pending. I judge the ruling sufficient for this phase. The shortfall is the agent's match yield at the 40-session ceiling, not a missing or broken part. The goal sentence ("matches easy functions ... the build deciding each match") is shown by 3 genuine gate-decided matches. The ruling is written in four places (rulings.md, STATE.md, 06-VALIDATION.md, REQUIREMENTS.md Pending), so nothing is hidden. The status is `human_needed`, not `passed`, for three reasons. The guardrails changed after the pilot and have not run in a live session (a fresh canary is due). 32 judgment-tier prohibitions need human confirmation. The Pages page needs a visual check.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 (RPT-01..04): on push to main, Pages publishes progress.svg, the shield and progress.json. All come from stdlib progress.py and a committed status table that only the local gate writes. The `<VERSION>_report` artifact with an objdiff-shaped report.json is uploaded | ✓ VERIFIED | `.github/workflows/pages.yml`: push on main, with paths filtering status/functions/units CSVs and progress.py; weekly cron; `python3 -I tools/progress.py`; `actions/upload-artifact@v7` named `X-COM_Apocalypse_DOS_report`; deploy-pages. progress.py imports only stdlib (L41-56). `write_status` is called only from gate.py L536/L814 (gate EXE/UNIT on exit 0, gate --partial). Both status.csv files carry the header `written by: uv run reverseapoc gate`. The hooks protect status.csv in matching sessions. test_drift (matched rows equal the defined C, the sha256 matches the file, the feed is derived), test_progress, test_report_shape, test_workflows, test_status and test_treemap are green (451 passed, my run). Live: 33-live.log has pages.yml success at f4056f1, `/` and progress.json/svg/shields at 200, and the report artifact unexpired |
| 2 | SC2 (RPT-05): `.recomp.json` is updated, and the recomp.fyi listing and DecompHub submission are done | ✓ VERIFIED (external parts owner-attested) | `.recomp.json`: status `in-progress`, Progress link to Pages, `ai-assisted` tag, no "retrokit", notes name the own layer. `decomphub.progress.json` (progress-v1, 4 tracks, matching status.csv: UFO2P 3/1553, TACP 2/1526). `docs/DECOMPHUB_VERIFICATION.md` exists. The DecompHub form submission (2026-10-24, pending review) and the recomp.fyi listing and claim (2026-10-25) are owner-attested. Ruling F40: the requirement asks for the submission, not the approval. test_listings green |
| 3 | SC3 (AGT-05): guardrail hooks, tested with pytest, block edits to orig/, the hash manifests and the build/verify scripts during matching sessions, inline asm and code-emitting `#pragma aux` in src/, and builds that bypass the verify script | ✓ VERIFIED | `tools/reverseapoc/hooks.py`. The always layer (`.claude/settings.json`) protects orig/, asm/, build/ (except the D-46 notes path), targets.toml, watcom.toml and `*.sha1`, and blocks inline asm and pragmas in src/ and include/. The matching layer (`config/driver/claude-settings.json`, matcher `*`) denies by default, allows writes only to the claimed unit, a new header and notes.md, and allows Bash only as an exact attempt-wrapper argv with no metacharacters (`bash_allowed`), so no direct ninja or compiler build is possible. Both handlers have `timeout: 120` and `onFailure: block`. There is no allow decision, only deny or no opinion (L801). tests/test_hooks.py is green, including 55 `include` tests (CR-02) |
| 4 | SC4 (AGT-01..04, 07..09): the driver runs one fresh `claude -p "/goal ..."` per function from the easiest-first scorer, supplies the context pack and skill, re-verifies itself, caps attempts and re-queues, logs MATCHED/PARTIAL/GAVE_UP with turns, tokens, time and verifier output, and backs off with a night cap | ✓ VERIFIED | `session.build_argv` is the D-06 argv (`-p`, stream-json, `--max-turns`, `--model claude-opus-5-5`, dontAsk, `--tools`, `--allowedTools ...Bash(wrapper *)`, `--strict-mcp-config`, `--setting-sources project`, `--settings`, `--append-system-prompt-file SKILL.md`, `--max-budget-usd`). `goal_prompt` starts `/goal`. The driver judges with its own container gate (`_judge`), caps 3 per function (difficult.json, then `picker.requeue`), applies BACKOFF_S (60, 120, 240) then polls, stops on the STOP classes in streamjson.py, and ends at max_sessions or target_matched. The context pack is capped at PACK_CAP 24576. The skill is 147 lines with the required sections. Live: progress/attempts.jsonl has 40 attempt records plus STARTED/ENDED `max sessions`; no function has more than 3 attempts; records carry turns, tokens, cost, seconds, model, cli_version 2.1.308 and a check summary. Tests test_driver, test_driver_pick, test_gate, test_attempt_wrapper, test_contextpack, test_session, test_streamjson and test_drive are green (562 passed, 4 platform skips, my run) |
| 5 | SC5a (AGT-06): the pilot ran unattended, one function per commit, with zero regressions: every earlier match still matches and both EXEs stay SHA-1 identical after every commit | ✓ VERIFIED | `git show --stat` of c83cf4e, d288ad6 and 955931f: each touches one src unit plus status.csv, the feed and attempts.jsonl, and carries `Matched-By: reverseapoc drive`. 11-regate-1..3.log: `gate --all` exit=0 after each commit, with both SHA-1s equal to the manifest (UFO2P e7488bf3..., TACP 48ef0096...) and the Phase 5 matches (func_000A3980, func_00055080) still OK. 12-final-ninja.log (from clean) and 13-final-gate.log are exit=0, with all 5 matched functions at objdiff 100% and reloc ok. The run record shows ENDED `max sessions` with no STOPPED and no guardrail record |
| 6 | SC5b (AGT-11, D-37): the unattended pilot matches 10 easy functions, at least 3 per EXE | PASSED (override): partial, 3/10 | The count is not met: 3 MATCHED (2 UFO2P, 1 TACP) in 40 sessions. Override: PARTIAL pilot accepted by ayrtondenner on 2026-10-26; the 10-match target carries to Phase 7; AGT-11 stays Pending. See "Owner-accepted deviation" below |
| 7 | SC5c (AGT-10): agent work runs through decomp.wtf fork mode if the spike passes, otherwise through a minimal own agent layer | ✓ VERIFIED | `.planning/spikes/006-decompwtf-fork-stub/README.md` gives `verdict: INVALIDATED` (D-02, no build in WSL2). The own layer is present and was used live: driver, hooks, skill, pack and attempt wrapper, with no MCP server (D-44). No decomp.wtf file is tracked (`git ls-files` grep is empty) |
| 8 | The build, never the agent, decides each match: MATCHED is logged and committed only when the container gate passed AND wrote a matched row for the claimed function (CR-01) | ✓ VERIFIED | `driver._gate_matched` calls `claimed_matched(gate.doc, pick)`, which needs a `written` row with that start, unit and `matched`. Otherwise it restores the pre-gate tables (a refused restore stops the night). Both `_counted` and `_salvage` use it. Named tests run green: `pytest tests/test_driver.py -k "claimed or unclaimed"` gave 6 passed (test_gate_pass_without_the_claimed_row_is_no_match, ..._keeps_a_partial, test_limit_salvage_without_the_claimed_row_is_no_match, test_unclaimed_pass_with_a_refused_restore_stops_the_night, test_gate_pass_with_the_claimed_row_beside_a_sibling_commits) |
| 9 | The no-pragma and no-inline-asm guardrail cannot be bypassed by `#include` of an unscanned file (CR-02) | ✓ VERIFIED | hooks.py `include_problem` and `INCLUDE_RULE`. configure.py `include_problems` is called from `check_unit_source`, so check, gate and land refuse a path include before compiling (9232499). The tests (test_hooks include tests, test_check L1189+, test_configure L578) are green. I also ran `include_problems` on every tracked src/*.c and include/*.h: none are refused, so the post-evidence configure.py change does not break the committed units |
| 10 | The guardrails at 060a001 (CR-02, WR-02, WR-04 changes) hold in a real matching session | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Present, wired and unit-tested (decide() payload tests; canary fixtures updated in a446a3c; SKILL.md L100 tells the agent to send timeout 600000). No live session has run since these changes; the pilot and canary2 ran under the old hooks. A fresh owner canary is needed (see Human Verification) |

**Score:** 9/10 truths verified, 1 of them an owner override (SC5b). 1 truth is present but behavior-unverified (#10).

### Owner-accepted deviation: AGT-11 (stated explicitly)

- **What was required:** D-37 and ROADMAP SC5 call for 10 MATCHED in one owner-started run, with at least 3 per EXE, under a 40-session ceiling.
- **What happened:** run 20261026-005209 made 3 MATCHED: ufo2p func_0008A0E0 (attempt 1), tacp func_0006EE30 (attempt 1) and ufo2p func_0008A100 (attempt 2). The other 37 sessions were PARTIAL across 12 functions, each capped at 3. The night ended at `max sessions` (40).
- **What held:** one commit per match, the D-24 gate after every commit, no guardrail record (`"reason": *"guardrail"` count 0), and a complete attempt log (42 records, schema test green).
- **Ruling:** owner, 2026-10-26: PARTIAL accepted, and the 10-match target carries to Phase 7. AGT-11 stays `[ ]` and Pending in REQUIREMENTS.md, as it should.
- **Verifier judgment:** the ruling is sufficient for the phase verdict. This is a yield shortfall, not missing or broken code.
- **Not a Step 9b deferral:** the Phase 7 ROADMAP section does not yet name the 10-match target. Its SC3 asks for matching at scale, but not this pilot count.
- **WARNING:** the owner should write the carry-over into Phase 7's success criteria, or remap AGT-11 in the REQUIREMENTS traceability, when Phase 7 is planned. Today it lives only in STATE.md and 06-VALIDATION.md.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| Plan must_haves.artifacts, 06-01..06-27 | per plan | ✓ VERIFIED (53/54 by gsd-tools) | The one miss is 06-26's `build/gate/06-evidence/`, reported "path is a directory". That is a tool false negative: the directory exists and holds the evidence logs listed below |
| `tools/reverseapoc/driver.py` | driver loop, caps, backoff, gate, commit | ✓ VERIFIED | 2614 lines, wired to `reverseapoc drive` (cli.py) |
| `tools/reverseapoc/hooks.py` | two-layer PreToolUse hooks | ✓ VERIFIED | wired from both settings files |
| `tools/reverseapoc/gate.py`, `status.py` | sole status.csv writer, cross-check | ✓ VERIFIED | test_gate crosscheck tests green |
| `tools/progress.py` | stdlib progress, svg, shields, report, feed | ✓ VERIFIED | run by pages.yml, loaded by gate for the feed |
| `.github/workflows/pages.yml` | Pages deploy plus report artifact | ✓ VERIFIED | live run success (33-live.log) |
| `.claude/skills/watcom-decomp/SKILL.md` | AGT-09 skill, ≤300 lines | ✓ VERIFIED | 147 lines; test_skill green |
| `config/{ufo2p,tacp}/status.csv`, `decomphub.progress.json`, `progress/attempts.jsonl` | gate- and driver-written data | ✓ VERIFIED | drift and schema tests green |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Plan key_links, 06-01..06-27 | | | ✓ WIRED (all but 06-26) | 06-26's single link starts from a directory (EISDIR): a tool limitation, not a wiring gap |
| driver `_counted`/`_salvage` | container gate | `deps.gate`, then `claimed_matched` | ✓ WIRED | CR-01 tests |
| `config/driver/claude-settings.json` | hooks.py matching layer | `--settings` in `build_argv` | ✓ WIRED | session.py L46/L78 |
| pages.yml | progress.py | `python3 -I tools/progress.py --out _site --report build/report.json` | ✓ WIRED | live deploy |
| gate | decomphub.progress.json | progress.py loaded by path | ✓ WIRED | test_drift `test_committed_feed_is_derived` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Pages site / progress.json | matched bytes and functions | config/*/status.csv + functions.csv + units.csv | yes (UFO2P 3/1553, TACP 2/1526, matching status.csv) | ✓ FLOWING |
| decomphub.progress.json | 4 tracks | the same CSVs, via gate | yes (drift test proves it is derived) | ✓ FLOWING |
| commit message | objdiff, reloc, SHA-1s | gate JSON (`gate_sha1s`) | yes (SHA-1s in the commits equal the manifest) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01: unclaimed gate pass is no match | `uv run pytest -q tests/test_driver.py -k "claimed or unclaimed"` | 6 passed | ✓ PASS |
| CR-02: include rule in the hooks | `uv run pytest -q tests/test_hooks.py -k include` | 55 passed | ✓ PASS |
| Reporting, hooks, drift, schema, skill | `uv run pytest -q tests/test_hooks.py tests/test_progress.py tests/test_report_shape.py tests/test_workflows.py tests/test_listings.py tests/test_skill.py tests/test_drift.py tests/test_attempts_schema.py tests/test_status.py tests/test_treemap.py` | 451 passed | ✓ PASS |
| Driver, picker, gate, wrapper, pack, session, stream, drive | `uv run pytest -q -rs tests/test_driver.py tests/test_driver_pick.py tests/test_gate.py tests/test_attempt_wrapper.py tests/test_contextpack.py tests/test_session.py tests/test_streamjson.py tests/test_drive.py` | 562 passed, 4 skipped (3 symlink-privilege, 1 POSIX-only) | ✓ PASS |
| Committed units pass the new include rule | `configure.include_problems` over src/ and include/ | all `[]` | ✓ PASS |
| Attempt log facts | Python read of progress/attempts.jsonl | 40 attempts (3 MATCHED, 37 PARTIAL), max 3 per function, ENDED max sessions, 0 guardrail | ✓ PASS |

The full suites were not run (HARD rule). The orchestrator re-runs every gate after this report. Stated suites at 060a001: container 2895 passed / 2 skipped; host 2862 passed / 35 skipped.

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `.planning/spikes/006-decompwtf-fork-stub/stub_regex.py`, `linker_name.py` | `uv run python ... SRC` | Not runnable: its input (the extracted tarball in gitignored build/spike006/) no longer exists | ? SKIP. The scripts exist. The verdict they support is INVALIDATED, so AGT-10 rests on the fallback branch, which the live pilot evidences. There are no conventional `scripts/*/tests/probe-*.sh` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RPT-01 | 06-02, 06-11, 06-16 | status table written only by the gate | ✓ SATISFIED | Truth 1 |
| RPT-02 | 06-18, 06-24 | progress.json, treemap svg, shield | ✓ SATISFIED | Truth 1 |
| RPT-03 | 06-22, 06-24, 06-26, 06-27 | Pages workflow on push to main | ✓ SATISFIED | Truth 1, 33-live.log |
| RPT-04 | 06-18, 06-20, 06-24, 06-27 | report.json as the `<VERSION>_report` artifact | ✓ SATISFIED | Truth 1, artifact unexpired |
| RPT-05 | 06-18, 06-19, 06-22, 06-24, 06-26, 06-27 | .recomp.json and DecompHub submission | ✓ SATISFIED (owner ruling F40) | Truth 2 |
| AGT-01 | 06-17, 06-23, 06-25, 06-27 | fresh session per function, self re-verify, one per commit or reset | ✓ SATISFIED | Truths 4, 5, 8 |
| AGT-02 | 06-14, 06-23, 06-27 | 3-5 cap, difficult list, re-queue | ✓ SATISFIED | Truth 4 |
| AGT-03 | 06-17, 06-23, 06-27 | tri-state outcome with turns, tokens, time, verifier output | ✓ SATISFIED | Truth 4, attempts.jsonl |
| AGT-04 | 06-17, 06-23, 06-25, 06-27 | backoff and night cap | ✓ SATISFIED | Truth 4 (fake-clock tests) |
| AGT-05 | 06-03, 06-07, 06-12, 06-15, 06-27 | guardrail hooks, pytest-tested | ✓ SATISFIED | Truths 3, 9 (live behaviour after review: truth 10) |
| AGT-06 | 14 plans | zero-regression gate | ✓ SATISFIED | Truth 5 |
| AGT-07 | 06-06, 06-10, 06-14, 06-25, 06-27 | easiest-first scorer | ✓ SATISFIED | Truth 4 |
| AGT-08 | 06-04, 06-06, 06-13, 06-15, 06-27 | context pack | ✓ SATISFIED | Truth 4 |
| AGT-09 | 06-15, 06-27 | watcom-decomp skill | ✓ SATISFIED | Truth 4 |
| AGT-10 | 06-01, 06-20, 06-21, 06-27 | decomp.wtf if the spike passes, else own layer | ✓ SATISFIED | Truth 7 |
| AGT-11 | 06-21, 06-25, 06-26, 06-27 | pilot matches 10 easy functions | ⚠️ PARTIAL, owner-accepted 2026-10-26 (3/10), carried to Phase 7 | Truth 6. REQUIREMENTS.md keeps it Pending (consistent) |

All 16 IDs appear in plan frontmatter. REQUIREMENTS.md maps no other ID to Phase 6, so there are no orphans.

### Decision Coverage

`check.decision-coverage-verify`: 49/49 trackable CONTEXT.md decisions honored; not_honored: []. Non-blocking.

### Prohibitions (judgment tier, 32, all `status: resolved`)

These verdicts are non-authoritative LLM judgments and are flagged for human review (see human_verification).

| Group | Prohibitions | Verdict | Evidence checked |
|-------|--------------|---------|------------------|
| Match decided only by the container gate | 06-11 "MUST NOT count a match on anything but check's own verdict"; 06-23 "MUST NOT commit, count or log MATCHED on the transcript..." | held (after CR-01) | `_gate_matched` / `claimed_matched`; CR-01 tests green. Before 02f513e this was violated in a latent path; the pilot's 3 matches are confirmed genuine by 13-final-gate.log |
| status.csv only from gate | 06-11, 06-16 | held | the only callers of `write_status` are in gate.py; hooks deny matching-session writes |
| Hook semantics | 06-12: never deny outside the D-16 list in the always layer; matching-session write and Bash limits; never emit allow | held | hooks.py `_PROTECTED_*`, `matching_write_allowed`, `bash_allowed`; only `deny` is emitted (L801) |
| Attempt wrapper | 06-15: no agent-chosen unit, function, flags, Watcom tree or src root; no listing text outside stdout and build/driver | held | test_attempt_wrapper green |
| Game data stays local | 06-13, 06-18, 06-23: no packs or listings in tracked files; no game bytes in outputs | held | `git ls-files` has nothing under orig/, asm/, build/, third_party/; the attempts schema test refuses long hex blobs |
| decomp.wtf | 06-01: not vendored or patched | held | no tracked decomp.wtf file |
| Manifests and matched C | 06-05, 06-07: matched C tokens; watcom.toml only the two words; targets.toml untouched | held per the plan SUMMARYs; byte identity confirmed by the gate logs | |
| Oracle refusals | 06-03, 06-04, 06-09, 06-10: no widening of own-public sizes; no refusal bypass flag; no CSV changes | held per test suites (not re-derived here) | |
| Third parties | 06-19, 06-22: nothing filed or submitted by Claude; decomp.me not accessed; AI-assisted wording kept | held | `ai-assisted` tag present; the submissions are the owner's |
| Process | 06-16 (no concurrent suites), 06-17 (no real claude in tests), 06-18 (no AnyPS5 code copied), 06-21 (no DI closed without a hash or ruling), 06-23 (no staging outside the allowlist, stop after a breach) | held per the record | tests/fakeclaude.py used; progress.py header cites the design only |

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|-----------|-----------|--------|---------|----------|-----------------|---------|
| tests/test_driver.py | AGT-01..04, CR-01 | yes | 2 conditional (symlink privilege; they run in the container) | no | behavioral (tmp git repo, fake claude, fake gate) | OK |
| tests/test_hooks.py | AGT-05, CR-02 | yes | 0 | no | value (deny/no-opinion per payload) | OK |
| tests/test_drift.py | RPT-01 | yes | 0 | no: compares committed tables to src/ and the file hashes | value | OK |
| tests/test_report_shape.py | RPT-04 | yes | 0 | partial: the field names are pinned to report.proto names (external), the values to progress.py | value | OK |
| tests/test_gate.py | AGT-06 | yes | 0 | no | behavioral (crosscheck refusals) | OK |

Disabled tests on requirements: 0. Circular patterns: 0 blocking.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (131 phase-touched files) | | TBD / FIXME / XXX / TODO / HACK (placeholder `func_XXXXXXXX` excluded) | none | Only hit: tests/test_hygiene.py:77, a comment that bans "TBD" |
| config/ufo2p/status.csv | rows 0x0004DFF0, 0x00061F50 | partial rows with `attempts 3` for siblings the driver never claimed | ℹ️ Info | `gate --partial` writes a row for every function in the best C that scored above 0% and stamps it with the claim's attempt count (gate.py `gate_partial`). This misstates `attempts` for those siblings and keeps them out of the pick pool for that pass. Not a goal blocker; Phase 7 scorer tuning may want it |
| .claude/skills/watcom-decomp/SKILL.md | | does not mention the CR-02 include rule | ℹ️ Info | the hook denial names the rule; the skill can only change through writing-skills |
| build/gate/06-evidence/11..14 | | evidence predates the review fixes (taken at 03b63e2) | ⚠️ Warning (covered) | review changes to configure.py, check, gate and the driver came after; the orchestrator re-runs every gate after this report, and the committed units pass the new include rule (spot-check) |

### Human Verification Required

#### 1. Fresh canary under the current guardrails

**Test:** `uv run reverseapoc drive --canary --run <fresh id>` (owner), before the next real night.
**Expected:** `CANARY PASS`. In particular, `attempt check` sent with Bash timeout 600000 is allowed (WR-04) and the protected writes are denied.
**Why human:** a live `claude -p` session. The hook changes since canary2 (CR-02, WR-02, WR-04) have only synthetic-payload tests.

#### 2. Judgment-tier prohibitions

**Test:** read the "Prohibitions (judgment tier)" table above.
**Expected:** the owner confirms the verdicts, or names any that are wrong.
**Why human:** ADR-550 D4: an LLM verdict on a must-NOT is not authoritative.

#### 3. Progress page visual check

**Test:** open https://ayrtondenner.github.io/ReverseApoc/ on desktop and phone, light and dark.
**Expected:** bars, strips and mosaic render legibly, and the figures equal progress.json.
**Why human:** visual layout; 33-live.log proves only HTTP 200s.

### Open owner items (not phase gaps)

- IN-04: pinning actions by commit SHA (deferred; residual in 06-SECURITY.md).
- The D-31 DecompHub maintainer claim, the three awesome-list PRs and the decomp.me preset issue. These are third-party submissions the owner sends from docs/listings.md. They sit outside RPT-05's text per F40.
- Writing the AGT-11 10-match carry-over into Phase 7's ROADMAP success criteria or the REQUIREMENTS traceability (WARNING above).

### Gaps Summary

No blocking gaps. Every roadmap success criterion is met in the code, except SC5's count of 10. That count is an explicit owner-accepted deviation: 3/10, 2 UFO2P + 1 TACP, recorded as an override, with AGT-11 kept Pending. Both critical review findings are fixed and pinned by named tests that pass. The security audit is SECURED (94/94, threats_open 0, at 060a001). The status is `human_needed` for three reasons: the post-pilot guardrail changes need a live canary, the judgment-tier prohibitions need human confirmation, and the page needs a visual check.

---

_Verified: 2026-10-26T15:56:03Z_
_Verifier: Claude (gsd-verifier)_
