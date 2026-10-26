---
phase: 06-reporting-and-agent-pilot
plan: 27
subsystem: gate
tags: [phase-gate, pilot, d-37, agt-06, regate, sweep, validation, skip-audit, pages, recomp, ledger]
status: complete

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-26 owner pilot run 20261026-005209 (3 MATCHED: c83cf4e, d288ad6, 955931f; chore 398515d); 06-11..06-25 gate, drift, progress, report, Pages, hooks, wrapper, pack, picker, driver, skill; 06-DEFERRED-LEDGER.md"
provides:
  - "Independent proof of the pilot: each of the 3 match commits re-gated in the container in order (gate --all exit 0, both EXEs SHA-1 identical), final tree from clean (ninja verify + gate --all exit 0), drift and attempt-log schema green, no guardrail record"
  - "docs/toolchain.md `### Phase 6 match evidence`: one row per pilot match with the 30-cell sweep result; versions and -4r/-5r stay tied, -os drops for both UFO2P functions; `*` default unchanged"
  - ".recomp.json status in-progress (D-32); owner's spike 005 line in 05-VALIDATION.md (DI-29); every DI ledger row closed or ruled"
  - "06-VALIDATION.md signed off (status validated, nyquist_compliant, wave_0_complete), every row citing a build/gate/06-evidence/ log; AGT-11 partial, owner-accepted 2026-10-26 (3/10), carried to Phase 7"
affects: [/gsd-verify-work 6, Phase 7 (the 10-match target carries over), recomp.fyi listing (status in-progress)]

actuals:
  tokens: 9500    # chars/4 over git diff f4056f1..1722b1a (37,903 chars), before this SUMMARY
  tasks: 3
  commits: 2      # MEASURED: git rev-list --count f4056f1..HEAD before this SUMMARY commit (03b63e2, 1722b1a)
plan_head_before: f4056f1e8cf4f14c2957a3d047348d4f4a84b431
plan_head_after: 1722b1a537abd3669c5c0a7bdce3decc971f0d4b

tech-stack:
  added: []
  patterns:
    - "Phase gate re-checks the driver's claims with the oracle, commit by commit (git checkout --detach <hash>; container gate --all), never from the driver's own log"

key-files:
  created:
    - .planning/phases/06-reporting-and-agent-pilot/06-27-SUMMARY.md
  modified:
    - docs/toolchain.md
    - .recomp.json
    - .planning/phases/05-split-and-first-matches/05-VALIDATION.md
    - .planning/phases/06-reporting-and-agent-pilot/06-DEFERRED-LEDGER.md
    - .planning/phases/06-reporting-and-agent-pilot/06-VALIDATION.md
    - .planning/STATE.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Pilot result (D-37): run 20261026-005209, 3 MATCHED in 40 sessions (2 UFO2P + 1 TACP, about USD 14 per match). The re-gate after each commit, the final tree from clean, the drift test and the guardrail check all pass"
  - "Owner ruling 2026-10-26: PARTIAL pilot accepted; AGT-11 = partial, owner-accepted 2026-10-26 (3/10), carried to Phase 7; AGT-11 not marked complete (F39)"
  - "Compiler evidence: all three pilot matches hold under `*  wcc386@10.6  -4r -s -fpi`; 10.5/10.6/11.0 and -4r/-5r stay tied; config/cflags.txt unchanged"
  - "Owner ruling 2026-10-26 (F40): RPT-05 complete. .recomp.json is updated (status in-progress, listed and claimed on recomp.fyi 2026-10-25) and the owner submitted the DecompHub form on 2026-10-24 (pending DecompHub review); the requirement asks for the submission, not the approval"

patterns-established:
  - "Phase-gate evidence under build/gate/<phase>-evidence/ is written only by shell redirection, each log ending exit=STATUS"

requirements-completed: [AGT-06, AGT-03, RPT-01, RPT-02, RPT-03, RPT-04, RPT-05, AGT-01, AGT-02, AGT-04, AGT-05, AGT-07, AGT-08, AGT-09, AGT-10]
# plan frontmatter requirements (verbatim): [AGT-11, AGT-06, AGT-03, RPT-01, RPT-02, RPT-03, RPT-04, RPT-05, AGT-01, AGT-02, AGT-04, AGT-05, AGT-07, AGT-08, AGT-09, AGT-10]
# not completed here: AGT-11 (partial, owner-accepted, F39). RPT-05 completed by owner ruling F40 (review fix round 1)

coverage:
  - id: D1
    description: "Pilot checked against D-37 independently: 3 match commits found (F30 form), each changes one src unit plus allowlisted paths, each re-gated in the container, final tree from clean, drift/schema green, no guardrail record"
    requirement: AGT-06
    verification:
      - kind: integration
        ref: "build/gate/06-evidence/10-commits.txt, 11-regate-1..3.log, 12-final-ninja.log, 13-final-gate.log, 14-drift.log (each ends exit=0); Task 1 verify with the count checks against the actual count (3; 2 ufo2p, 1 tacp)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Phase 6 match evidence table in docs/toolchain.md from the three container sweeps; cflags default unchanged"
    verification:
      - kind: other
        ref: "build/gate/06-evidence/20-sweep-func_0008A0E0.json (24/30), 20-sweep-func_0006EE30.json (30/30), 20-sweep-func_0008A100.json (18/30); grep '^### Phase 6 match evidence' docs/toolchain.md; grep -n '^\\*' config/cflags.txt"
        status: pass
    human_judgment: false
  - id: D3
    description: ".recomp.json status in-progress, spike 005 owner line, ledger fully closed or ruled"
    requirement: RPT-05
    verification:
      - kind: unit
        ref: "Task 2 verify: uv run pytest -q tests/test_listings.py tests/test_hygiene.py (104 passed, 3 skipped) and no planned/pending ledger row"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both suites green with the F2 skip audit, ruff clean, hygiene clean"
    verification:
      - kind: unit
        ref: "build/gate/06-evidence/30-host.log (2780 passed, 35 skipped, exit=0, ruff clean), 31-container.log (2813 passed, 2 skipped, exit=0, ruff clean), 32-hygiene.log (exit=0)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live publishing: Pages deploy, live site files, raw feed and report artifact"
    requirement: RPT-03
    verification:
      - kind: other
        ref: "build/gate/06-evidence/33-live.log (written by the orchestrator, ruling F37)"
        status: pass
    human_judgment: false
  - id: D6
    description: "AGT-11 pilot target (10 MATCHED) is partial, owner-accepted"
    requirement: AGT-11
    verification: []
    human_judgment: true
    rationale: "3 of 10 matched; the owner accepted the PARTIAL pilot on 2026-10-26 and the target carries to Phase 7. Owner ruling, not a test result"

duration: "about 35 min (Phase A about 3 min plus Phase B about 30 min; the container suite alone took 11 min 14 s)"
completed: 2026-10-26
---

# Phase 6 Plan 27: Phase 6 gate Summary

**The phase gate re-checked the owner's pilot with the oracle rather than taking the driver's word. Each of the 3 match commits passes the container `gate --all`, both EXEs stay SHA-1 identical after every commit, and the final tree passes from clean. The three sweeps leave the compiler versions and -4r/-5r tied (-os is ruled out for both UFO2P functions), so the `*` default stays. Both suites are green with F2-allowed skips only (platform and tool). 06-VALIDATION.md is signed off, and AGT-11 is recorded as partial, owner-accepted (3/10).**

Execution context nonce: e92135e16b8ef800

## Performance

- **Duration:** about 35 min
- **Started:** 2026-10-26T12:56Z (Phase A, Task 1)
- **Completed:** 2026-10-26T13:30Z
- **Tasks:** 3 of 3
- **Files modified:** 6 tracked files plus this SUMMARY; gitignored evidence in build/gate/06-evidence/

## Evidence (build/gate/06-evidence/, gitignored, written by shell redirection)

| Log | What | Result |
|-----|------|--------|
| 10-commits.txt | F30 form: `git log --reverse --format=%H%x09%s --grep="^Matched-By: reverseapoc drive$"` | 3 commits, oldest first: c83cf4e feat(ufo2p) func_0008A0E0, d288ad6 feat(tacp) func_0006EE30, 955931f feat(ufo2p) func_0008A100. Each changes exactly one src/<exe>/<unit>.c plus only status.csv, decomphub.progress.json and progress/attempts.jsonl |
| 11-regate-1.log | c83cf4e, container `gate --all` | UFO2P landed 2, TACP landed 1, both SHA-1 OK, `exit=0` |
| 11-regate-2.log | d288ad6 | UFO2P landed 2, TACP landed 2, `exit=0` |
| 11-regate-3.log | 955931f | UFO2P landed 3, TACP landed 2, `exit=0` |
| 12-final-ninja.log | main: configure.py, `ninja -t clean` (16 files), `ninja verify` | UFO2P, TACP and SMKP sha1 == manifest, `exit=0` |
| 13-final-gate.log | main: container `gate --all` | 5 matched functions at objdiff 100%, reloc ok, bytes ok; both SHA-1 OK, `exit=0` |
| 14-drift.log | host `pytest -q tests/test_drift.py tests/test_attempts_schema.py` | 42 passed, `exit=0` |
| 20-sweep-func_0008A0E0.json | container `check ufo2p/u_00089980 --sweep func_0008A0E0 --json` | exit 0; 24 of 30 cells at 100.0 (every `-os` cell 80.0) |
| 20-sweep-func_0006EE30.json | `check tacp/u_0006ee30 --sweep func_0006EE30 --json` | exit 0; 30 of 30 |
| 20-sweep-func_0008A100.json | `check ufo2p/u_00089980 --sweep func_0008A100 --json` | exit 0; 18 of 30 (`-os` 80.0; `-4r -ot`/`-4r -oneatx` 75.0) |
| 30-host.log | host `uv run pytest -q -rs` + `uv run ruff check .` | 2780 passed, 35 skipped, `exit=0`; ruff "All checks passed!" (`ruff_exit=0`); F2 host audit passes |
| 31-container.log | `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."` (after the host run finished) | 2813 passed, 2 skipped, ruff clean, `exit=0`; F2 container audit passes |
| 32-hygiene.log | `git ls-files` check from the Task 3 verify | 504 tracked files, no offender, `exit=0` |
| 33-live.log | written by the orchestrator (ruling F37), main at f4056f1; not run by this executor | latest pages.yml run on main `success`; `/`, `/index.html`, progress.json, progress-shield.json, progress-shield-ufo2p.json, progress-shield-tacp.json, progress.svg and raw decomphub.progress.json 200; `/progress.html` 404 (expected, removed in f4056f1); artifact `X-COM_Apocalypse_DOS_report` for f4056f1, `expired: false` |

Other Task 1 checks: progress/attempts.jsonl has exactly one STARTED record (line 1, run 20261026-005209), and each match has a MATCHED attempt record. `grep '"reason": *"guardrail"'` finds nothing. After the re-gates, git was back on main with an empty `git status --porcelain` and an empty stash list.

## Skip lists (F2 audit, 06-16 forms)

Host (30-host.log, 35 skips, every reason on the allow-list):
- `SKIPPED [1] tests\test_cc_log.py:190: POSIX-only: /dev/null and its directory /dev`
- `SKIPPED [8] tests\conftest.py:68: objdiff-cli is not on PATH (run in the container)`
- `SKIPPED [1] tests\test_check_real.py:147: ninja is not on PATH (run in the container)`
- `SKIPPED [2] tests\test_configure.py:203: Windows file names cannot hold | or LF`
- `SKIPPED [1] tests\test_configure.py:277: needs a file system that stores non-UTF-8 byte names`
- `SKIPPED [1] tests\test_contextpack.py:157: symlink creation needs privileges on this host`
- `SKIPPED [1] tests\test_driver.py:949: symlink creation needs privileges on this host`
- `SKIPPED [1] tests\test_driver.py:1305: symlink creation needs privileges on this host`
- `SKIPPED [1] tests\test_fileio.py:58: symlink creation needs privileges on this host`
- `SKIPPED [4] tests\conftest.py:89: Ghidra: \opt\ghidra/support/analyzeHeadless not found (set GHIDRA_INSTALL_DIR, or run in the container)`
- `SKIPPED [2] \work\tests\test_ghidra_real.py:126: Ghidra: ... (set GHIDRA_INSTALL_DIR, or run in the container)`, and the same at :131, :143 and :148 (2 each, 8 in total)
- `SKIPPED [3] tests\test_hygiene.py:554: only inside the container`
- `SKIPPED [2] tests\conftest.py:74: clang-18 / clang is not on PATH (run in the container)`
- `SKIPPED [1] tests\test_session.py:430: POSIX-only: taskkill /T cannot find children after the parent exits`

No `_real.py` skip comes from a missing orig/ or Watcom tree. The test_ghidra_real.py and test_check_real.py skips are tool skips (GHIDRA_INSTALL_DIR, ninja "run in the container"), which F2 allows.

Container (31-container.log, 2 skips):
- `SKIPPED [1] ...tests\test_cc_log.py:234: Windows-only: msvcrt lock path`
- `SKIPPED [1] ...tests\test_cc_log.py:255: Windows-only: msvcrt lock path`

No `_real.py` line is skipped in the container.

## Accomplishments

- The driver's three matches are proven by the oracle commit by commit, and the final tree is proven from clean.
- The per-match compiler evidence is recorded. The three pilot matches, with the two Phase 5 ones, agree with the `*` default, which stays as it is.
- The listing status is `in-progress`, the spike 005 sign-off is quoted with its date, and every DI-01..DI-37 row is closed or ruled.
- Both suites and ruff are green on the host and in the container, hygiene is clean, Pages is live (33-live.log), and the validation map is signed off.

## Task Commits

1. **Task 1: tracer, pilot vs D-37 with re-gates**: no commit (gitignored evidence only, ruling F38, Phase A)
2. **Task 2: match evidence, recomp status, spike 005 line, ledger**: `03b63e2` (docs)
3. **Task 3: suites, hygiene, live check citation, validation sign-off, STATE decisions**: `1722b1a` (docs)

**Plan metadata:** this docs(06-27) commit (SUMMARY, ROADMAP, REQUIREMENTS)

Tracer gate: `end-of-phase` mode with an automated-only verify. The Task 1 verify (count checks adjusted per the owner ruling) was re-run after Task 1 and exited 0, so the plan expanded to Tasks 2 and 3. The pause between Phase A and Phase B was ruling F38's commit-flag checkpoint, not a tracer checkpoint.

## Files Created/Modified

- `docs/toolchain.md`: the `### Phase 6 match evidence` table and the separation notes
- `.recomp.json`: `status` changed from exploring to in-progress
- `.planning/phases/05-split-and-first-matches/05-VALIDATION.md`: the owner's spike 005 line, with dates
- `.planning/phases/06-reporting-and-agent-pilot/06-DEFERRED-LEDGER.md`: 17 rows filled (recounted from `git diff f4056f1..d070e72`), with every hash checked by `git cat-file -e`; the rows this plan closes cite 03b63e2
- `.planning/phases/06-reporting-and-agent-pilot/06-VALIDATION.md`: every row green with its evidence log, an AGT-11 partial row, the Wave 0 F31 note, the manual-only results, the sign-off and the approval
- `.planning/STATE.md`: two Phase 06 Decisions lines (the pilot result and the PARTIAL ruling); the Deferred Items status; the repo-visibility blocker marked RESOLVED (review fix round 1)

## Decisions Made

See key-decisions in the frontmatter. RPT-05 is settled by owner ruling F40 (2026-10-26): it is complete. Its automated row (the .recomp.json schema and the DecompHub feed) is green; .recomp.json is updated (a9011c7/e360d32, 03b63e2 status in-progress; listed and claimed on recomp.fyi 2026-10-25); and the owner submitted the DecompHub form on 2026-10-24 (pending DecompHub review, 06-CONTEXT.md). The requirement asks for the submission, not the approval, so REQUIREMENTS.md marks RPT-05 Complete (review fix round 1). These stay open owner items, outside RPT-05's text: the D-31 DecompHub maintainer claim, the awesome-list PRs and the decomp.me preset issue.

## Deviations from Plan

**Orchestrator and owner rulings applied:**

1. **Owner ruling 2026-10-26: PARTIAL pilot accepted (D-37).** The run reached 3 MATCHED, not 10. Task 1 did not stop at its checkpoint:decision for the count, but every re-gate, final and drift check still ran and could have stopped it. None failed.
2. **Owner ruling 2026-10-26: count checks replaced.** Task 1's `>= 10` and `>= 3 per EXE` verify checks became the same checks against the actual count: `test "$n" -eq 3`, feat(ufo2p) = 2, feat(tacp) = 1. They pass, and so do the per-log `exit=0` checks and the check that there is one log per commit.
3. **Orchestrator ruling F37: 33-live.log written by the orchestrator.** This executor made no network call. It cites the orchestrator's 33-live.log, whose URL list (site root, index.html, progress.json, the three shield files, progress.svg and the raw feed) replaces the plan's "three Pages URLs". `/progress.html` 404 is expected after the owner's f4056f1.
4. **Orchestrator ruling F2: skip audit forms.** The plan's container verify (`! grep -q "SKIPPED"`) would fail on the 2 `Windows-only: msvcrt lock path` skips. The 06-16 F2 form allows exactly those and passes. The host form uses the full F2 allow-list.
5. **Orchestrator ruling F30:** 10-commits.txt uses `git log --reverse` (oldest first), and the guardrail grep uses the pinned key `"reason": *"guardrail"`.
6. **Orchestrator ruling F31:** in 06-VALIDATION.md the Wave 0 conftest helpers are recorded as not needed rather than ticked, and the RPT-05 feed row points at tests/test_progress.py.
7. **Orchestrator ruling F38:** Task 1 ran on a clean tree with no commit flag and returned a checkpoint. Tasks 2 and 3 ran after the orchestrator set its flag. That file was never staged.
8. **Orchestrator ruling F39:** AGT-11 is not marked complete. Its 06-VALIDATION row reads "partial, owner-accepted 2026-10-26 (3/10), carried to Phase 7".
9. **Owner ruling F40 (2026-10-26, applied in review fix round 1):** RPT-05 is complete (submission done, DecompHub approval pending). REQUIREMENTS.md ticks it and its 06-VALIDATION row cites the owner submission and the ruling.

**Minor execution choices (no rule change):**
- The sweep commands ran as `uv sync --locked >/dev/null 2>&1 && uv run reverseapoc check ... --sweep ... --json`, so the JSON on stdout stays clean. stderr went to `20-sweep-<func>.stderr.log`. config/cflags.txt has the same md5 before and after.
- 30-host.log appends `ruff_exit=STATUS` after the ruff output. The pytest `exit=STATUS` line comes before it, as in the plan's command.

**Total deviations:** 9 ruling applications, 0 auto-fixes. **Impact:** no code, cflags, manifest or matched C changed. The gate's checks are as strict as planned, apart from the owner-accepted count.

## Issues Encountered

- Skip lines show cross-environment file paths. The host log names `\work\tests\test_ghidra_real.py`, and the container log names `C:\Users\...\tests\test_cc_log.py`. This most likely comes from pytest's assertion-rewrite cache in `tests/__pycache__`, which the bind mount shares between host and container. The reasons and line numbers are right, and the audit matches on reasons (06-16 note). I changed nothing here and record it as an observation.
- STATE.md listed the Phase 6 blocker "Repo visibility must be settled before Pages and listings". 33-live.log shows Pages live (root 200), so review fix round 1 marks it RESOLVED 2026-10-26.

## Next Phase Readiness

- Phase 6 is ready for `/gsd-verify-work 6`. The validation map is signed off against evidence. AGT-11 is partial, owner-accepted. RPT-05 is complete (F40). Open owner items outside RPT-05's text: the D-31 DecompHub maintainer claim, the awesome-list PRs and the decomp.me preset issue.
- Phase 7 inherits the 10-match target. Measured rate from the pilot: 3 matches in 40 sessions, about USD 14 per match.
- No tick-rate finding (OpenApoc #997) came up in this plan, its evidence or the pilot's logs.

## Self-Check: PASSED

- All 14 evidence files listed above exist in build/gate/06-evidence/, along with docs/toolchain.md, .recomp.json and this SUMMARY.
- Commits 03b63e2 and 1722b1a (this plan) and c83cf4e, d288ad6 and 955931f (the pilot) are ancestors of HEAD. `check evaluation-scope --plan 06-27 --commits-only` resolves both 06-27 commits.
- `git diff f4056f1..HEAD` touches nothing under src/, orig/ or config/. `grep -n '^\*' config/cflags.txt` prints `37:*  wcc386@10.6  -4r -s -fpi`.
- Acceptance re-run: the Task 1 verify (adjusted per the ruling), the Task 2 verify and acceptance checks, and the Task 3 verifies (F2 host and container forms, hygiene, validation flags) all exit 0.
