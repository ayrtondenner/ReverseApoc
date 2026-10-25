---
phase: 06-reporting-and-agent-pilot
plan: 16
subsystem: testing
tags: [status-csv, gate, drift-test, container, ninja, provenance, skip-audit]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-11 gate (the only status.csv writer, gate --all), 06-04 regenerated functions.csv, 06-09 provenance stamps, 06-10 real table/static probes, 06-12 hooks"
provides:
  - "config/ufo2p/status.csv and config/tacp/status.csv, written by one container gate run (UFO2P func_000A3980, TACP func_00055080)"
  - "tests/test_drift.py: the D-22 CI drift test (no game files)"
  - "tests/test_gate_real.py: gate --all on the real files passes and refuses a reverted match"
  - "container proofs: real tests unskipped, ninja graph with stamps, both EXEs SHA-1 identical, both suites green"
affects: [06-17, 06-18, 06-25, 06-27, progress, driver]

actuals:
  tokens: 3178
  tasks: 3
  commits: 5
plan_head_before: 28e211dc5ac054634f7f9bed431cacb27928c0d7
plan_head_after: f9222adf9971b72dbd0b524c77ddcb43f2fa8e5c

tech-stack:
  added: []
  patterns:
    - "Drift test: matched names == union of source_marks(...).defined over src/<exe>/*.c; matched source_sha256 == lf_sha256(unit)"
    - "Real gate tests stand a src copy under build/ in for check.DEFAULT_SRC (gate compiles only the committed tree)"
    - "Tests that run real git against the checkout pass safe.directory=* through GIT_CONFIG_COUNT/KEY_0/VALUE_0"

key-files:
  created:
    - config/ufo2p/status.csv
    - config/tacp/status.csv
    - tests/test_drift.py
    - tests/test_gate_real.py
    - .planning/phases/06-reporting-and-agent-pilot/deferred-items.md
  modified:
    - tests/test_hooks.py

key-decisions:
  - "status.csv seeded by ONE container run of `gate ufo2p/u_000a34f0 tacp/u_00054f20 --json` (ruling F1), never by hand"
  - "functions.csv not regenerated (ruling Row 11); tiling and D-50 figures re-measured instead"
  - "06-12's 5 container failures were test-environment defects, fixed in tests/test_hooks.py only (ruling F2b); hooks.py stays fail-closed"

patterns-established:
  - "Container evidence runs use `docker compose run --rm -T` (the build service has tty: true)"

requirements-completed: [RPT-01, AGT-06]

coverage:
  - id: D1
    description: "Both status.csv files hold exactly one gate-written matched row each (D-20 shape, 100.00, attempts 0, lf_sha256)"
    requirement: RPT-01
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_drift.py && grep -q '^0x000A3980,func_000A3980,u_000a34f0,matched,100.00,0,' config/ufo2p/status.csv && grep -q '^0x00055080,func_00055080,u_00054f20,matched,100.00,0,' config/tacp/status.csv"
        status: pass
      - kind: integration
        ref: "build/gate/06-seed/01-gate-seed.exit == 0 and 01-gate-seed.json ok == true"
        status: pass
    human_judgment: false
  - id: D2
    description: "CI drift test fails on a hand-added row, a removed definition and a one-character comment edit"
    requirement: RPT-01
    verification:
      - kind: unit
        ref: "tests/test_drift.py#test_drift_catches_planted_changes"
        status: pass
    human_judgment: false
  - id: D3
    description: "gate --all passes on the committed tree and refuses a src copy with func_000A3980 reverted to INCLUDE_ASM"
    requirement: AGT-06
    verification:
      - kind: integration
        ref: "build/gate/06-seed/03-real.log (container, 42 passed, no SKIPPED, exit=0)"
        status: pass
    human_judgment: false
  - id: D4
    description: "configure + ninja + ninja lint + ninja verify in the container, with provenance stamps written by the cc edges"
    verification:
      - kind: integration
        ref: "build/gate/06-seed/04-ninja.log exit=0; 04b-ninja-rebuild.log exit=0; 05-stamps.log"
        status: pass
    human_judgment: false
  - id: D5
    description: "Host suite and ruff, with platform-only skips"
    verification:
      - kind: integration
        ref: "build/gate/06-seed/06-host.log (2275 passed, 32 skipped, exit=0, ruff clean); uv run pytest -q tests/test_hooks.py after f9222ad (211 passed)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Container suite and ruff with no skips except the msvcrt pair"
    verification:
      - kind: integration
        ref: "build/gate/06-seed/07b-container.log (2305 passed, 2 skipped, ruff clean, exit=0); F2 container verify passed"
        status: pass
    human_judgment: false

duration: 41min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 16: Seed status.csv via gate, CI drift test, container proofs Summary

**One container gate run wrote the status table for the two Phase 5 matches. A CI drift test now ties status.csv to the matched C, and `gate --all` is proven on the real files: it passes on the committed tree and refuses a reverted match. The real tests and the ninja graph with stamps pass in the container. After ruling F2b fixed two test-environment defects in 06-12's tests/test_hooks.py, both suites and ruff are green: 2275 passed on the host and 2305 in the container, with only the allowed skips.**

Execution context nonce: 9c70041144e97752

## Performance

- **Duration:** about 41 min. That is 28 min to the halt, plus about 13 min for the F2b resume.
- **Started:** 2026-10-25T13:17:45Z
- **Completed:** 2026-10-25T13:59Z
- **Tasks:** 3 of 3
- **Files:** 5 created (2 tables, 2 tests, deferred-items.md) and 1 modified (tests/test_hooks.py), plus gitignored evidence

## Accomplishments

- **status.csv seeded (RPT-01, D-20, D-21).** One container run of `gate ufo2p/u_000a34f0 tacp/u_00054f20 --json` exited 0 with `ok: true` and no problems. Its checks report:
  - func_000A3980 (13 bytes) and func_00055080 (11 bytes) at objdiff 100.0;
  - both splices landing 1 function each;
  - UFO2P sha1 `e7488bf3…7c56` and TACP sha1 `48ef0096…7393`, each equal to the manifest.

  The rows it wrote:
  - `0x000A3980,func_000A3980,u_000a34f0,matched,100.00,0,7edd9a60…8665,2026-10-25`
  - `0x00055080,func_00055080,u_00054f20,matched,100.00,0,7029c415…1f56,2026-10-25`

  Both hashes equal the host's `lf_sha256` of the unit files. Each table holds the comment line, the D-20 header and one row, LF in the index and in the working tree.
- **tests/test_drift.py (D-22 points 1 and 2):**
  - `test_matched_rows_equal_defined_functions[ufo2p|tacp]`
  - `test_matched_units_hash[ufo2p|tacp]`
  - `test_drift_catches_planted_changes`: on tmp copies, a hand-added matched row for INCLUDE_ASM'd `func_000A3970`, the definition reverted to its marker, and `Neither` -> `neither` in a comment each fail with a readable problem. Restoring the copy passes again.
  - It needs no game files, so CI runs it from now on.
- **tests/test_gate_real.py (AGT-06):**
  - `test_gate_all_passes_on_the_committed_tree`: exit 0, no problems, both splices ok with the manifest SHA-1s.
  - `test_gate_all_refuses_a_reverted_match`: a src/ copy under build/test-gate-real/ with func_000A3980 back to `INCLUDE_ASM` and the real status.csv. The result is exit 1, exactly one UFO2P cross-check problem `func_000A3980 at 0x000A3980 ... not landed`, and no TACP problem.
- **Container proofs:**
  - 03-real.log: gate_real, check_tables_real (with its objdiff layer), ghidra_real, functions_real and check_real gave 42 passed, no SKIPPED, exit=0.
  - test_functions_real's drift tests pass, so the boundary checkpoint did not fire.
  - 04-ninja.log: configure, ninja, lint and verify exit 0, and both EXEs are SHA-1 identical.
- **Both suites green (Task 3, after F2b):**
  - Host: 2275 passed, 32 platform skips.
  - Container: 2305 passed, 2 msvcrt skips.
  - Ruff is clean on both.
- **Ruling Row 11 re-check** (scratch script in the session scratchpad; numbers only):

  | EXE | rows | units | unit span | row bytes | uncovered | unit gaps | rows outside their unit |
  |-----|------|-------|-----------|-----------|-----------|-----------|-------------------------|
  | UFO2P now | 1892 | 408 | 785,114 | 759,327 | 25,787 | 0 | 0 |
  | UFO2P before 06-04 (47b633d^) | 1892 | 408 | 785,114 | 759,423 | 25,691 | 0 | 0 |
  | TACP now | 1874 | 433 | 795,983 | 760,634 | 35,349 | 0 | 0 |
  | TACP before 06-04 | 1874 | 433 | 795,983 | 760,742 | 35,241 | 0 | 0 |

  - The before figures equal the ledger's D-50 figures exactly.
  - The 26 shorter rows add 96 uncovered bytes in UFO2P and 108 in TACP, the same totals as 06-04's measurement. **06-18 must pin the "now" figures.**
  - The tiling still holds. `tests/test_units.py -k tile` gave 6 passed.

## Task Commits

1. **Task 1 (tracer, TDD): drift test, then gate seeds both tables**
   - RED `004f89d` (test): all 5 failed on their assertions (`config/<exe>/status.csv has no matched row` x4; the planted test's copy reported `func_000A3980 is defined in C but has no matched row`). There was no collection, import or fixture error.
   - GREEN `fc7d1cd` (feat): the two gate-written tables only; the test is unchanged. 5 passed.
   - Tracer gate: interactive, `end-of-phase`, verify automated only. I re-ran it after the commit (5 passed, 1 row per table), then expanded.
2. **Task 2 (TDD): real gate cross-check**: `9ac110a` (test).
   - No GREEN code was needed: gate_all (06-11) already behaves as pinned. This is the same precedent as 06-10 Task 2.
   - The two tests require opposite verdicts (exit 0 and exit 1) from the same gate_all path, so neither passes vacuously.
   - On the host both skip only for objdiff-cli. In the container both pass (5.3 s).
3. **Task 3: both suites with the skip audit**
   - First run: the host passed. The container failed: 5 tests in tests/test_hooks.py (07-container.log). That halt is `c33ec7a` (docs).
   - Ruling F2b: RED is 07-container.log. GREEN is `f9222ad` (fix), tests/test_hooks.py only.
   - Then test_hooks on the host (211 passed), the container suite and ruff (07b-container.log, exit=0), and the F2 container verify, which passed.

**Plan metadata:** `c33ec7a` (the halted SUMMARY), then this SUMMARY commit (docs).

## Evidence logs (gitignored, build/gate/06-seed/)

- `01-gate-seed.json`: the gate JSON only (stdout). `01-gate-seed.exit`: `0`. `01-gate-seed.err`: compose/uv stderr.
- `03-real.log`: 42 passed, `exit=0`, no SKIPPED.
- `04-ninja.log`: `exit=0`. It shows CHECK-ORIG, OMF2ELF x2, REBUILD and LAND. The cc and lint edges were already up to date: gate's default-option compile writes ninja's build/<exe>/obj, and the lint stamps were from an earlier run.
- `04b-ninja-rebuild.log` (supplementary, see Deviations): `ninja -t clean -r cc` and `-r lint`, then the same chain. It shows CC x2 (wcc386@10.6), OMF2ELF x2, LINT x2 (`lint: 1 files, ok`), REBUILD, and LAND `landed 1` with the manifest SHA-1s, `exit=0`.
- `05-stamps.log`: both `*.obj.prov.json`, then the post-rebuild listing (2026-10-25T10:28:54-0300, written by ninja's cc edges).
- `06-host.log`: 2275 passed, 32 skipped, `exit=0`, then `All checks passed!` (ruff).
- `07-container.log`: the RED for F2b. 5 failed (tests/test_hooks.py), 2300 passed, 2 skipped, `exit=1`.
- `07b-container.log`: 2305 passed, 2 skipped, `All checks passed!` (ruff), `exit=0`.

## Skip audit (ruling F2): every skip line

Host (06-host.log). Every reason is in F2's allowed list. No `_real.py` line skips for a missing orig/ or Watcom tree:

```
SKIPPED [1] tests\test_cc_log.py:190: POSIX-only: /dev/null and its directory /dev
SKIPPED [8] tests\conftest.py:68: objdiff-cli is not on PATH (run in the container)
SKIPPED [1] tests\test_check_real.py:147: ninja is not on PATH (run in the container)
SKIPPED [2] tests\test_configure.py:203: Windows file names cannot hold | or LF
SKIPPED [1] tests\test_configure.py:277: needs a file system that stores non-UTF-8 byte names
SKIPPED [1] tests\test_contextpack.py:157: symlink creation needs privileges on this host
SKIPPED [1] tests\test_fileio.py:58: symlink creation needs privileges on this host
SKIPPED [4] tests\conftest.py:89: Ghidra: \opt\ghidra/support/analyzeHeadless not found (set GHIDRA_INSTALL_DIR, or run in the container)
SKIPPED [2] \work\tests\test_ghidra_real.py:126: Ghidra: \opt\ghidra/support/analyzeHeadless not found (set GHIDRA_INSTALL_DIR, or run in the container)
SKIPPED [2] \work\tests\test_ghidra_real.py:131: Ghidra: \opt\ghidra/support/analyzeHeadless not found (set GHIDRA_INSTALL_DIR, or run in the container)
SKIPPED [2] \work\tests\test_ghidra_real.py:143: Ghidra: \opt\ghidra/support/analyzeHeadless not found (set GHIDRA_INSTALL_DIR, or run in the container)
SKIPPED [2] \work\tests\test_ghidra_real.py:148: Ghidra: \opt\ghidra/support/analyzeHeadless not found (set GHIDRA_INSTALL_DIR, or run in the container)
SKIPPED [3] tests\test_hygiene.py:551: only inside the container
SKIPPED [2] tests\conftest.py:74: clang-18 / clang is not on PATH (run in the container)
```

The F2b change touches only tests/test_hooks.py, which has no skip. Its host run after the change was 211 passed, 0 skipped.

Container (07b-container.log). These are only F2's one allowed reason, with no `_real.py` skip. The lines moved from :226 to :234/:255, and the reason is unchanged:

```
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:234: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:255: Windows-only: msvcrt lock path
```

Ruff: `All checks passed!` on the host (06-host.log, and again after f9222ad) and in the container (07b-container.log).

## Files Created/Modified

- `config/ufo2p/status.csv`, `config/tacp/status.csv`: written by `gate` in the container, never by hand.
- `tests/test_drift.py`: the D-22 drift test.
- `tests/test_gate_real.py`: the real gate --all cross-check.
- `tests/test_hooks.py` (F2b):
  - `SAFE_GIT_ENV` (git `safe.directory=*` through GIT_CONFIG_COUNT/KEY_0/VALUE_0) is passed by test_main_tracks_headers_with_git (monkeypatch.setenv) and by test_matching_entry_point_end_to_end (the subprocess env).
  - `_session_env` keeps UV_PROJECT_ENVIRONMENT.
- `.planning/phases/06-reporting-and-agent-pilot/deferred-items.md`: the 06-12 container entry, now resolved.

## Decisions Made

- Seeded with one gate run (F1). config/*/functions.csv and the other CSVs were not regenerated (Row 11).
- The drift test takes "defined" from check.source_marks over every src/<exe>/*.c. Each file is read as strict UTF-8 bytes with its own unit's functions.csv rows, so it agrees with configure and check.
- test_gate_real.py stands its reverted src copy in for `check.DEFAULT_SRC` with monkeypatch, because gate compiles only the committed tree (`_committed_src`). The copy lives under build/ because the compiler compiles only inside the repository.
- F2b: hooks.py is unchanged, so a hook whose git refuses the checkout still blocks (exit 2). The tests give their own git the exception.

## Deviations from Plan

**Orchestrator ruling F1: seed in one gate run.** Task 1's GREEN was one container run of
`gate ufo2p/u_000a34f0 tacp/u_00054f20 --json` into `01-gate-seed.json`, with its status in `01-gate-seed.exit`.
The second verify was F1's form (`test "$(cat 01-gate-seed.exit)" = "0"` plus the JSON's top-level `ok`). It passed.

**Orchestrator ruling Row 11: no CSV regeneration.** Nothing was regenerated. The tiling and the D-50 progress figures were re-checked; see the table above.

**Orchestrator ruling F2: the skip audit.** I used F2's host and container regexes and listed every skip line above. I "fixed" no skip.

**Orchestrator ruling F2b: 06-12's container failures fixed in tests/test_hooks.py (`f9222ad`).**
- **Found during:** Task 3. 07-container.log had 5 failed. I reproduced both causes in the container:
  1. git "dubious ownership" on the uid-0 bind mount;
  2. `_session_env` stripping the image's `UV_PROJECT_ENVIRONMENT`, after which uv tried to replace the host's /work/.venv and failed with an I/O error.
- **Fix:** the two real-git tests pass `safe.directory=*` through GIT_CONFIG_COUNT/KEY_0/VALUE_0, following the precedents at test_hygiene.py:531 and test_githooks.py. `_session_env` keeps UV_PROJECT_ENVIRONMENT when it is set and still drops every other UV_* variable, so the "no project" and "no uv on PATH" cases still exit 2.
- **Unchanged:** hooks.py, the image, compose, the Dockerfile and the build scripts.
- **Verification:** RED is 07-container.log. After the fix:
  - host test_hooks: 211 passed, ruff clean;
  - container suite and ruff (07b-container.log): 2305 passed, 2 skipped, exit=0;
  - the F2 container verify passed.
- **Files modified:** tests/test_hooks.py.

**1. [Rule 3 - Blocking] `-T` on every captured `docker compose run`**
- **Found during:** Task 1.
- **Issue:** The compose `build` service has `tty: true` (ledger note "For 06-15, 06-23 and 06-26"). Without `-T` the redirected JSON and logs can carry TTY artefacts.
- **Fix:** Each plan or ruling command ran as written, plus `-T`. The gate's stderr went to a sibling `01-gate-seed.err`, so the `.json` holds JSON only, as the plan requires.

**2. [Rule 2 - Missing critical proof] supplementary `04b-ninja-rebuild.log`**
- **Found during:** Task 2.
- **Issue:** In 04-ninja.log every cc and lint edge was already up to date, so it did not show that ninja's own cc edges write the stamps and that lint runs.
- **Fix:** In the container, `ninja -t clean -r cc && ninja -t clean -r lint` removed only the two objects with their stamps and the lint stamps (ninja's own writes). Then the plan's chain ran again with exit 0. 04-ninja.log is kept unchanged as the plan's evidence.

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing proof), plus 4 orchestrator rulings applied (F1, Row 11, F2, F2b). **Impact:** F2b adds tests/test_hooks.py to the plan's files, as the ruling directs. There is no other scope change.

## Issues Encountered

- The first container suite failed on 5 tests/test_hooks.py tests. Both causes were in the test environment, and ruling F2b resolved them (see Deviations, and deferred-items.md, now `status: resolved`).
- **Cosmetic:** the host and container share `tests/__pycache__` through the bind mount. So pytest shows the other side's paths in some lines (`\work\tests\...` on the host, `C:\Users\...` in the container) and `???` for source lines. Results are not affected.
- No tick-rate finding (OpenApoc #997).

## User Setup Required

None.

## Next Phase Readiness

- status.csv exists and is gate-written. 06-18's progress, 06-25's driver and the picker's `matched_starts` can read it. CI's drift test guards it from now on.
- 06-18 must pin the re-measured coverage figures (UFO2P 25,787 / TACP 35,349 uncovered), not the older ones.
- The CLAUDE.md done gate holds for Waves 1-2: tests and ruff green on the host and in the container.

## Self-Check: PASSED

- FOUND: config/ufo2p/status.csv, config/tacp/status.csv, tests/test_drift.py, tests/test_gate_real.py, tests/test_hooks.py
- FOUND: build/gate/06-seed/01-gate-seed.{json,exit}, 03-real.log, 04-ninja.log, 04b-ninja-rebuild.log, 05-stamps.log, 06-host.log, 07-container.log, 07b-container.log
- FOUND commits: 004f89d, fc7d1cd, 9ac110a, c33ec7a, f9222ad. `git rev-list --count 28e211d..f9222ad` = 5, with no file deletions.
- Every task's acceptance criteria re-run: PASS. 06-host.log `exit=0`; 07b-container.log `exit=0`; the F2 container verify passed.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
