---
phase: 05-split-and-first-matches
plan: 20
subsystem: gate
tags: [phase-gate, ninja, wibo, objdiff, relocs, land, rebuild, skip-audit, hygiene, validation, spl-01, spl-13]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-01..05-19: the split, the ninja graph, check/land, both first matches (build/match/ufo2p.unit u_000a34f0, build/match/tacp.unit u_00054f20)"
provides:
  - "build/gate/05-evidence/ (gitignored): 01..11 evidence logs, each ending exit=0, plus 09-rows.log running every VALIDATION row command in the container"
  - ".planning/phases/05-split-and-first-matches/05-VALIDATION.md signed off: 13/13 rows green with their evidence log, status validated, nyquist_compliant true, wave_0_complete true"
  - ".planning/STATE.md: the [Phase 5] blocker line carries the plan's RESOLVED note"
affects: [gsd-verify-work-5, phase-06]

actuals:
  tokens: 3653
  tasks: 3
  commits: 1
plan_head_before: 540379493cb944b41fe202f51885892858168a2c
plan_head_after: e4a242bfe29c1593b788cba4ae978cb28c5d76c0

tech-stack:
  added: []
  patterns:
    - "Gate evidence comes from a CLEAN graph (`ninja -t clean objects lint` first), so the log shows every unit compiled and linted in this run, not a no-op incremental build"
    - "Each VALIDATION row is proven by its own command in one container run (09-rows.log, one exit line per row), not by a -q suite log that names no files"

key-files:
  created: []
  modified:
    - .planning/phases/05-split-and-first-matches/05-VALIDATION.md
    - .planning/STATE.md

key-decisions:
  - "The ninja gate log is from a clean objects+lint graph: the first run was a no-op (`ninja: no work to do`, no CC line) because 05-19's outputs were current, so it did not show the units compiling under wibo; that run is kept as 01-ninja.incremental.log"
  - "Ruling F6 skip audit: host skips accepted only for GHIDRA_INSTALL_DIR, clang, objdiff-cli, only inside the container, run in the container, POSIX-only, Windows file names cannot hold, non-UTF-8 byte names; container skips only for `Windows-only: msvcrt lock path`; no tests/test_*_real.py skip in the container, and no host skip for a missing orig/ or Watcom tree"
  - "Ruling F4: both check JSONs also asserted to have splice exes exactly {UFO2P.EXE, TACP.EXE}"

patterns-established:
  - "Phase gate evidence directory build/gate/<NN>-evidence/ with numbered logs, each ending exit=STATUS (as 04-12)"

requirements-completed: [SPL-01, SPL-02, SPL-03, SPL-04, SPL-05, SPL-06, SPL-07, SPL-08, SPL-09, SPL-10, SPL-11, SPL-12, SPL-13]

coverage:
  - id: D1
    description: "Container pipeline from a clean graph: configure, ninja (846 edges: 841 target cuts, both units compiled by wcc386@10.6 under wibo), ninja lint (both units ok), ninja verify (all three EXEs rebuilt SHA-1 equal to the manifest; UFO2P landed 1, TACP landed 1)"
    requirement: SPL-13
    verification:
      - kind: integration
        ref: "docker compose run --rm build bash -lc \"uv sync --locked && uv run python configure.py && ninja -t clean objects lint && ninja && ninja lint && ninja verify\" (build/gate/05-evidence/01-ninja.log, exit=0)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Both first matches pass check: func_000A3980 (ufo2p/u_000a34f0) and func_00055080 (tacp/u_00054f20) at objdiff 100.0, reloc ok, splices exactly UFO2P.EXE and TACP.EXE, both ok"
    requirement: SPL-13
    verification:
      - kind: integration
        ref: "docker compose run --rm build ... reverseapoc check ufo2p/u_000a34f0 --json and check tacp/u_00054f20 --json (02-check-ufo2p.exit and 03-check-tacp.exit = 0; JSON parsed by the plan's verify and the F4 exe-set assertion)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Phase 3 gate kept: the host rebuild of UFO2P.EXE, TACP.EXE and SMKP.EXE is SHA-1 identical and cmp against orig/ is silent"
    verification:
      - kind: integration
        ref: "uv run reverseapoc rebuild && cmp build/<EXE> orig/<EXE> x3 (build/gate/05-evidence/04-rebuild.log, exit=0)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Done gate: host suite 1540 passed / 25 platform-only skips and ruff clean; container suite 1563 passed / 2 Windows-only skips and ruff clean; every real-file test runs in the container"
    verification:
      - kind: integration
        ref: "uv run pytest -q -rs && uv run ruff check . (06-host.log exit=0); docker compose run --rm build bash -lc \"uv sync --locked && uv run pytest -q -rs && uv run ruff check .\" (07-container.log exit=0); F6 skip audit commands"
        status: pass
    human_judgment: false
  - id: D5
    description: "Repository hygiene: git ls-files lists nothing under asm/, build/, orig/, third_party/, no objdiff.json, compile_commands.json, build.ninja, .obj/.o, no CMAIN386"
    verification:
      - kind: other
        ref: "the plan's git ls-files check (build/gate/05-evidence/08-hygiene.log, exit=0, 345 tracked files, 0 matches)"
        status: pass
    human_judgment: false
  - id: D6
    description: "05-VALIDATION.md signed off against recorded evidence; spike 005 verdict recorded; STATE.md Phase 5 blocker marked resolved"
    verification:
      - kind: other
        ref: "Task 3 verify: grep nyquist_compliant/wave_0_complete true, no '| ⬜ pending |' row, grep 'RESOLVED .*capstone' STATE.md; 09-rows.log 13/13 row commands exit=0 in the container"
        status: pass
    human_judgment: false
  - id: D7
    description: "The three manual-only checks (owner reads the matched C, accepts image size and capstone, signs the spike verdict)"
    verification: []
    human_judgment: true
    rationale: "05-VALIDATION.md Manual-Only Verifications: owner judgement at /gsd-verify-work 5; this gate only records the spike verdict (VALIDATED)"

duration: 25min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 20: the Phase 5 gate Summary

**The Phase 5 gate passes on the main checkout, with every step's output recorded in build/gate/05-evidence/. In the container, the graph was cleaned and then rebuilt (configure, ninja, lint, verify). Both units compiled under wcc386 10.6 on wibo, both linted clean, and both EXEs landed SHA-1 identical. `check ufo2p/u_000a34f0` and `check tacp/u_00054f20` each report objdiff 100.0, a passing relocation check, and the UFO2P.EXE and TACP.EXE splices ok. The host rebuild of all three EXEs is still byte-identical to orig/. Both suites and ruff are green, with skips only for named platform reasons and no real-file skip in the container. Nothing forbidden is tracked. 05-VALIDATION.md is signed off with 13 of 13 rows green, each citing its log.**

Execution context nonce: dac9fbd616059ab3

## Performance

- **Duration:** about 25 min
- **Started:** 2026-10-24T04:54:32Z
- **Completed:** 2026-10-24T05:19:34Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto)
- **Files modified:** 2 tracked (05-VALIDATION.md, STATE.md); about 17 gitignored evidence files

## Evidence logs (build/gate/05-evidence/, gitignored)

| Log | Command | Result |
|---|---|---|
| 01-ninja.log | container `uv sync --locked && uv run python configure.py && ninja -t clean objects lint && ninja && ninja lint && ninja verify` | exit=0. 847 files cleaned. 846/846 edges. `CC src/ufo2p/u_000a34f0.c` and `CC src/tacp/u_00054f20.c` built by `wcc386@10.6 WATCOM C32 Optimizing Compiler Version 10.6`. 841 target cuts. Both lint stamps report `lint: 1 files, ok`. REBUILD: UFO2P, TACP and SMKP `== manifest`. LAND: UFO2P.EXE e7488bf3… landed 1, TACP.EXE 48ef0096… landed 1 |
| 01-ninja.incremental.log | the plan's command as written, run first | exit=0, but a no-op (`ninja: no work to do`, no CC line); kept, not used as proof (see Deviations) |
| 02-check-ufo2p.json / .exit / .err | container `uv sync --locked && uv run reverseapoc check ufo2p/u_000a34f0 --json` | exit 0. ok true; func_000A3980 100.0, reloc ok; splices UFO2P.EXE ok (landed 1), TACP.EXE ok (landed 1) |
| 03-check-tacp.json / .exit / .err | container `uv sync --locked && uv run reverseapoc check tacp/u_00054f20 --json` | exit 0. ok true; func_00055080 100.0, reloc ok; splices UFO2P.EXE ok (landed 1), TACP.EXE ok (landed 1) |
| 04-rebuild.log | host `uv run reverseapoc rebuild && cmp` x3 against orig/ | exit=0; three `== manifest` lines, cmp silent |
| 05-spike.log | `grep -m1 '^verdict:' .planning/spikes/005-objdiff-omf-elf/README.md` | `verdict: VALIDATED`, exit=0 |
| 06-host.log | host `uv run pytest -q -rs`, then `uv run ruff check .` | 1540 passed, 25 skipped in 293 s, exit=0; `All checks passed!`, ruff_exit=0 |
| 07-container.log | container `uv sync --locked && uv run pytest -q -rs && uv run ruff check .` | 1563 passed, 2 skipped in 446 s; `All checks passed!`; exit=0 |
| 08-hygiene.log | the plan's `git ls-files` forbidden-path check | 345 tracked files, 0 matches, exit=0 |
| 09-rows.log (+ 09-rows.sh) | container: each 05-VALIDATION.md row command with `-rs`, one exit line per row | SPL-01..SPL-13 all exit=0, 0 skipped. Slowest is SPL-01 at 172 s (Ghidra real). Overall exit=0 |
| 10-wave0.log | greps for the Wave 0 items | all present, exit=0 |
| 11-signoff.log | per-plan scan of the 20 plans for `<automated>` verifies and watch flags | every non-checkpoint task has `<automated>`; longest run without one is 0; no watch flags; exit=0 |

The host suite and the container commands ran strictly one after the other, never at the same time.

## Skip audit (ruling F6)

**Host (06-host.log): 25 skipped.** Every reason is on the allowed platform list:

| Count | Where | Reason |
|---|---|---|
| 1 | tests/test_cc_log.py:190 | `POSIX-only: /dev/null and its directory /dev` |
| 4 | tests/conftest.py:68 (requires_objdiff: tests/test_check_real.py, tests/test_objdiff_real.py) | `objdiff-cli is not on PATH (run in the container)` |
| 2 | tests/test_configure.py:202 | `Windows file names cannot hold \| or LF` |
| 1 | tests/test_configure.py:276 | `needs a file system that stores non-UTF-8 byte names` |
| 4 | tests/conftest.py:89 (requires_ghidra: tests/test_ghidra_real.py, tests/test_functions_real.py:116) | `Ghidra: ... analyzeHeadless not found (set GHIDRA_INSTALL_DIR, or run in the container)` |
| 8 | tests/test_ghidra_real.py:126/131/143/148 (2 each) | the same GHIDRA_INSTALL_DIR reason |
| 3 | tests/test_hygiene.py:529 | `only inside the container` |
| 2 | tests/conftest.py:74 (requires_clang: tests/test_lint.py) | `clang-18 / clang is not on PATH (run in the container)` |

No host skip names a missing orig/ or Watcom tree: a grep for `orig` and `watcom` over the SKIPPED lines finds nothing. The real-file tests that skip on the host do so only for Ghidra, objdiff-cli or clang. Those tools are in the container by design (D-04/D-05), and these tests run there unskipped.

**Container (07-container.log): 2 skipped**, both allowed:

| Count | Where | Reason |
|---|---|---|
| 1 | tests/test_cc_log.py:229 | `Windows-only: msvcrt lock path` |
| 1 | tests/test_cc_log.py:250 | `Windows-only: msvcrt lock path` |

No `tests/test_*_real.py` test skipped in the container. Both suites collected the same 1,565 tests (host 1540 + 25, container 1563 + 2).

Task 2 verify as amended by F6:
- host: pytest exit 0, and no SKIPPED line outside the allowed reasons or naming orig/Watcom → `host_verify=0`;
- container: exit 0, no SKIPPED line other than `Windows-only: msvcrt lock path`, and no `_real.py` SKIPPED line → `container_verify=0`;
- hygiene: the plan's command → exit 0.

## Task Commits

1. **Task 1 (tracer): the pipeline in the container, both checks, rebuild, spike verdict.** It made no commit, because its only output is gitignored evidence. Tracer gate: an interactive run, `human_verify_mode` end-of-phase, automated-only verify. I re-ran both plan verifies and the F4 JSON check, and all three passed (verify1=0, verify2=0, verify2_F4=0), so I expanded.
2. **Task 2: both suites with the skip audit, and hygiene.** It made no commit: gitignored evidence only.
3. **Task 3: validation sign-off and the STATE.md blocker:** `e4a242b` (docs)

## Files Created/Modified

- `.planning/phases/05-split-and-first-matches/05-VALIDATION.md`:
  - frontmatter set to `status: validated`, `nyquist_compliant: true`, `wave_0_complete: true`;
  - the 13 map rows: File Exists `✅`, Status `✅ green` with the evidence log(s) that prove each one;
  - Wave 0 list ticked, with a pointer to 10-wave0.log;
  - spike 005 verdict recorded under Manual-Only (the three manual checks stay with the owner);
  - sign-off checklist ticked, with pointers to 11-signoff.log and 09-rows.log;
  - Approval: `2026-10-24, gate plan 05-20`.
- `.planning/STATE.md`: one line, the `[Phase 5]` blocker. The plan's RESOLVED note is appended, plus "re-proven by gate plan 05-20".

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

- **Orchestrator ruling F6: the skip audit checks real-file coverage, not zero skips anywhere.** The Task 2 verify regexes were widened:
  - host: the three OS-limitation reasons were added, and a fail was added for any skip naming orig/ or Watcom;
  - container: only `Windows-only: msvcrt lock path` is accepted, and any `_real.py` skip fails.

  All skips are listed above. None was "fixed".
- **Orchestrator ruling F4: the check JSONs were also asserted to have splice exes exactly {UFO2P.EXE, TACP.EXE}.** Both pass.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical: evidence] The ninja gate log is from a clean graph**
- **Found during:** Task 1, step 1.
- **Issue:** The plan's command exited 0, but every output was current from 05-19. The log had `ninja: no work to do` for lint and no CC line, so it did not show the units compiling under Watcom 10.6 on wibo in this run, which is what the must_have claims.
- **Fix:**
  - I checked `ninja -t targets all`: no output lives under build/gate/ or build/match/.
  - I re-ran the plan's command with `ninja -t clean objects lint` inserted after configure.
  - The no-op run is kept as 01-ninja.incremental.log.
- **Verification:** 01-ninja.log shows both CC lines with the 10.6 banner, 841 TARGET cuts, both lint stamps and `exit=0`.
- **Committed in:** nothing (gitignored evidence).

**2. [Rule 2 - Missing critical: evidence] Per-row proof log for 05-VALIDATION.md**
- **Found during:** Task 3.
- **Issue:** `pytest -q` output names no test files, so 06/07 alone cannot show that each row's command passes. The plan forbids marking a row green without the command output that proves it.
- **Fix:** 09-rows.log runs each row's exact pytest command in the container (where real tests run) with `-rs` and one exit line per row. It also adds 10-wave0.log and 11-signoff.log for the Wave 0 list and the sign-off checklist.
- **Verification:** 13/13 `SPL-xx exit=0`, no SKIPPED line, overall `exit=0`.
- **Committed in:** nothing (gitignored evidence). The rows citing these logs are in `e4a242b`.

**3. [Minor] The STATE.md blocker line was already rewritten as RESOLVED by 05-12.**
- 05-12 replaced the original text. I appended the plan's RESOLVED sentence as written, with a short re-proof note, and changed nothing else (`git diff --numstat`: 1 1).

**4. [Minor] 06-host.log ends with `ruff_exit=0`** after ruff's output, one line past the plan's `exit=` line, so both exit statuses are on record. The plan's `exit=0` sits before ruff's output, as its acceptance criterion requires.

**5. [Minor] Tasks 1 and 2 made no commit.** Their only outputs are gitignored evidence logs (CLAUDE.md: build output is never committed).

---

**Total deviations:** 2 orchestrator rulings applied, 2 auto-fixed (evidence strengthening), 3 minor.
**Impact on plan:** The gate got stricter: a clean graph and per-row proof. No verdict changed, and no check was loosened beyond what F6 names.

## Issues Encountered

None. No gate step failed.

## Known Stubs

None. Tracked changes are planning documents only.

## Threat Flags

None. T-05-45: every green row cites a log produced in this plan, and the verifies parse logs and JSON. T-05-46: 08-hygiene.log shows 0 forbidden tracked paths. No package was installed.

## User Setup Required

None.

## Next Phase Readiness

- Phase complete. Ready for `/gsd-verify-work 5`.
- The owner's manual checks are open:
  - read src/ufo2p/u_000a34f0.c and src/tacp/u_00054f20.c next to 02-check-ufo2p.json and 03-check-tacp.json;
  - accept the image size and the capstone dependency;
  - sign the spike 005 verdict (VALIDATED).
- Deferred minors from the phase's reviews are in the orchestrator's progress ledger for the final review.

## Self-Check: PASSED

- FOUND: .planning/phases/05-split-and-first-matches/05-VALIDATION.md, .planning/STATE.md, and build/gate/05-evidence/01-ninja.log, 02-check-ufo2p.json, 03-check-tacp.json, 04-rebuild.log, 05-spike.log, 06-host.log, 07-container.log, 08-hygiene.log
- FOUND commit e4a242b (ancestor of HEAD). `git rev-list --count 5403794..HEAD` = 1 before this SUMMARY commit.
- Re-ran all acceptance criteria: Task 1 verify1/verify2/F4 = 0; Task 2 host_verify/container_verify/hygiene = 0; Task 3 verify1/verify2 = 0, 13/13 rows cite 05-evidence.

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
