---
phase: 05-split-and-first-matches
plan: 12
subsystem: tooling
tags: [docker, ghidra, lxloader, openjdk, clang, lint, c89, watcom, analyzeHeadless]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-03 requires_ghidra/requires_clang and build_le_image(ghidra_loadable=True); 05-05 include/common.h and the -i= include path; 05-10 reverseapoc.ghidra driver and the two Java GhidraScripts"
provides:
  - "docker/Dockerfile: cached `ghidra` stage (Ghidra 12.1.4 + lastonesky LxLoader v12.1.4-1, both sha256sum -c checked), openjdk-21-jdk-headless, clang-18, clang, COPY --from=ghidra /opt/ghidra, ENV GHIDRA_INSTALL_DIR=/opt/ghidra, D-20 strip of docs/ and top-level Extensions/"
  - "reverseapoc ghidra-export EXE [--orig] [--manifest] [--out] [--drafts ADDR ...] [--asm] [--json]"
  - "cached raw exports build/ghidra/ufo2p/functions.raw.csv (1408) and build/ghidra/tacp/functions.raw.csv (1498) in the main checkout, for 05-16"
  - "include/watcom_compat.h (clang-only)"
  - "tools/reverseapoc/lint.py: LintError, WATCOMC_VALUE, LINT_FLAGS, CLANGD_FLAGS, find_clang, lint_argv, run_lint, LintResult, collect_sources"
  - "reverseapoc lint [PATHS ...] [--stamp FILE] [--json]"
affects: [05-14 compile_commands/ninja lint edge, 05-16 reconcile, 05-13 units, 05-15 docs]

actuals:
  tokens: 8809
  tasks: 3
  commits: 7
plan_head_before: 39c20feca0ed6815d53718dc335b1c0c67125050
plan_head_after: 17017869190cd63520272c5a0e89138797da66c1

tech-stack:
  added: ["Ghidra 12.1.4 PUBLIC (image)", "lastonesky ghidra-lx-loader v12.1.4-1 (image)", "openjdk-21-jdk-headless 21.0.12.1 (image)", "clang 18.1.3 (image)"]
  patterns:
    - "Every image download is curl + `sha256sum -c` against an ARG pin; hygiene tests pin the hashes and forbid COPY without --from and ADD"
    - "Container-first verbs (ghidra-export, lint) fail early on the host with the exact `docker compose run --rm build uv run reverseapoc ...` command"
    - "Lint runs one clang per file from the repo root, so -Iinclude and -include include/watcom_compat.h are root-relative"

key-files:
  created:
    - tests/test_ghidra_real.py
    - include/watcom_compat.h
    - tools/reverseapoc/lint.py
    - tests/test_lint.py
  modified:
    - docker/Dockerfile
    - tests/test_hygiene.py
    - tools/reverseapoc/cli.py

key-decisions:
  - "D-20 strip kept: removing /opt/ghidra/docs and the top-level /opt/ghidra/Extensions shrinks the image from 1,067,599,391 to 898,389,257 bytes, and the smoke, both real exports and the drafts test pass on the stripped image"
  - "Ghidra makes exactly one one-address function in each EXE's data object (UFO2P 0x0013BD40, TACP 0x002B405C); the code-object test allows at most one such entry, and reconcile (05-16) must drop entries outside the code object"
  - "ghidra-export --drafts writes only the drafts (one analysis run) and exits 1 when any address got no draft"
  - "lint with no sources passes without needing clang; a missing default src/ (before 05-13) is 0 files, an explicit missing path is an error"
  - "Drifted apt pins ca-certificates and xz-utils refreshed to the archive's current versions (the Dockerfile's documented procedure); the Ghidra and loader SHA-256 pins are unchanged and matched"

patterns-established:
  - "Real Ghidra tests use a module-scoped fixture so each EXE is analysed once per test module"

requirements-completed: [SPL-01, SPL-12]

coverage:
  - id: D1
    description: "Dockerfile pins: Ghidra and loader SHA-256, ghidra stage, JDK and clang apt pins, GHIDRA_INSTALL_DIR; a sha256sum -c per curl; only COPY --from=, no ADD"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_dockerfile_pins_ghidra[7], test_dockerfile_checks_every_download, test_dockerfile_copies_nothing_from_the_context"
        status: pass
    human_judgment: false
  - id: D2
    description: "In the container Ghidra 12.1.4 and LxLoader 12.1.4 are installed and a synthetic LE imports headless with -loader LeLoader; ExportDrafts resolves an LE object address"
    requirement: SPL-01
    verification:
      - kind: integration
        ref: "docker compose run --rm build uv run pytest tests/test_ghidra_real.py -k 'install or synthetic' (3 passed, no skip)"
        status: pass
    human_judgment: false
  - id: D3
    description: "ghidra-export verb; real export of both EXEs (>=1300 functions, entries in the code object bar one data-object artifact, LE entry, >=70 runtime starts); drafts for the UFO2P entry and the cmain386 row"
    requirement: SPL-01
    verification:
      - kind: integration
        ref: "docker compose run --rm build ... ghidra-export ufo2p && ... tacp && pytest tests/test_ghidra_real.py (14 passed, no skip)"
        status: pass
      - kind: unit
        ref: "tests/test_ghidra_real.py#test_ghidra_export_verb_host_message, test_ghidra_export_verb_refuses_an_unknown_exe"
        status: pass
    human_judgment: false
  - id: D4
    description: "C89 lint gate: compat header, LINT_FLAGS, lint verb; Watcom constructs pass and a mixed declaration fails with 'mixing declarations and code' in the container; header inert for wcc386 10.6"
    requirement: SPL-12
    verification:
      - kind: integration
        ref: "docker compose run --rm build uv run pytest tests/test_lint.py (12 passed, no skip)"
        status: pass
      - kind: unit
        ref: "tests/test_lint.py (host: 10 passed, 2 clang skips; test_compat_header_is_inert_for_watcom passed on the Windows host)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Image size with Ghidra + JDK + clang (898,389,257 bytes after the strip, from 300,640,359 before this plan)"
    verification: []
    human_judgment: true
    rationale: "D-20 accepts about +1.17 GB; the owner sees the recorded size at UAT and decides whether it is acceptable"

duration: 42min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 12: Ghidra 12.1.4 in the image, ghidra-export, and the C89 lint gate Summary

**The Docker image now carries a SHA-256-pinned Ghidra 12.1.4 with the lastonesky LE loader (own cached `ghidra` stage), OpenJDK 21 and clang 18. `reverseapoc ghidra-export` exports UFO2P (1408 functions) and TACP (1498) headless in about a minute each, and writes decompile drafts that resolve LE object addresses. `reverseapoc lint` runs `clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with the new clang-only `include/watcom_compat.h`. The 05-10 Java scripts compiled and ran unchanged.**

Execution context nonce: d8367eef6ceffb36

## Performance

- **Duration:** 42 min
- **Started:** 2026-10-24T01:25:59Z
- **Completed:** 2026-10-24T02:08:00Z
- **Tasks:** 3
- **Files modified:** 7 (4 new)

## Accomplishments
- **Image (D-03, D-04, D-06, D-20):** a `FROM ${UBUNTU_IMAGE} AS ghidra` stage downloads `ghidra_12.1.4_PUBLIC_20260921.zip` and `ghidra_12.1.4_PUBLIC_20261010_ghidra-lx-loader.zip`. The build log shows `ghidra.zip: OK` and `lx.zip: OK` against the plan's pins. The stage unpacks Ghidra to /opt/ghidra and the loader into `Ghidra/Extensions/ghidra-lx-loader`. The final stage installs `openjdk-21-jdk-headless=21.0.12.1+1-1~24.04.4`, `clang-18=1:18.1.3-1ubuntu1` and `clang=1:18.0-59~exp2`, then copies /opt/ghidra in. In the container: `openjdk version "21.0.12.1"`, `Ubuntu clang version 18.1.3 (1ubuntu1)`, LxLoader `version=12.1.4`. A clean `docker compose build` took 154 s.
- **Image size** (`docker image inspect reverseapoc-build:local --format "{{.Size}}"`, recorded in build/gate/05-image-size.txt):

  | State | Bytes |
  |---|---|
  | Before this plan | 300,640,359 |
  | With Ghidra, JDK and clang (Task 1) | 1,067,599,391 |
  | After the D-20 strip (kept) | 898,389,257 |

- **Smoke test (D-06):** in the container `test_ghidra_install`, `test_headless_imports_a_synthetic_le` and `test_headless_drafts_a_synthetic_le` pass unskipped (3 passed in 14.6 s). The synthetic import finds the entry at 0x00010123, and ExportDrafts' `toAddr(long)` resolves that LE object address to a function. This settles the 05-10 review note.
- **Real export (D-05):** results through the verb, counts and timings only:

  | EXE | Functions | Export (script-reported) | Wall time |
  |---|---|---|---|
  | UFO2P.EXE | 1408 | 57.8 s, then 55.8 s on the stripped image | 61.6 s |
  | TACP.EXE | 1498 | 52.5 s, then 50.4 s on the stripped image | 55.7 s |

  Both counts equal the research's measurement. `tests/test_ghidra_real.py` has 14 tests, all passing unskipped in the container (174.7 s on the stripped image). They check at least 1,300 functions per EXE, the LE entry point among the entries, at least 70 runtime.csv starts among the entries, and drafts for the UFO2P entry and the cmain386 row (0x000C5C9C).
- **Lint gate (SPL-12, D-14):** `include/watcom_compat.h` (clang-only, `-Wunknown-pragmas` silenced, 15 keywords empty), `tools/reverseapoc/lint.py` and the `lint` verb. In the container, tests/test_lint.py has 12 tests, all passing unskipped. The Watcom constructs pass, and the mixed declaration fails with `mixing declarations and code`. On the Windows host, `test_compat_header_is_inert_for_watcom` compiled with and without the header under wcc386 10.6 and got the same normalized object SHA-1. This resolves the STATE.md blocker "clang is missing from the Docker image".

## Task Commits

1. **Task 1 (tracer): the Ghidra stage, pinned; synthetic LE imports headless**: `5cafd4b` (test, RED), `e2b86e1` (feat, GREEN). Tracer gate (interactive, end-of-phase, automated-only verify): I re-ran the hygiene tests (58 passed) and the container smoke test (3 passed, no skip), then expanded.
2. **Task 2: ghidra-export verb, real exports, drafts, D-20 strip**: `5aa890c` (test, RED), `ab42674` (feat, GREEN), `fefd7f9` (perf, D-20 strip kept).
3. **Task 3: C89 lint gate**: `cd08f43` (test, RED), `1701786` (feat, GREEN).

## TDD notes (RED evidence, semantic assessment)
- Task 1 RED `5cafd4b`: 7 failed, all `test_dockerfile_pins_ghidra[...]` asserting a missing pin. That is the planned behaviour. `test_dockerfile_checks_every_download` and `test_dockerfile_copies_nothing_from_the_context` already passed at RED: they guard properties today's Dockerfile already had (2 curls and 2 checks, only COPY --from). They pin those properties against the new stage. The Ghidra tests skipped on the host, as planned.
- Task 2 RED `5aa890c`: 2 failed (`ghidra-export` was an invalid argparse choice, SystemExit 2, so no verb existed), 12 skipped on the host. That is an assertion-level absence of the verb.
- Task 3 RED `cd08f43`: collection ImportError, because `reverseapoc.lint` did not exist. That is load-level, not an assertion. The plan is `type: execute` and `workflow.tdd_mode` is unset, so the plan-level gate does not apply. Recorded for the end-of-phase TDD review, as in 05-03 and 05-10.

## Files Created/Modified
- `docker/Dockerfile`: ghidra stage, Ghidra/loader ARG pins, JDK and clang apt pins, COPY --from=ghidra, GHIDRA_INSTALL_DIR, D-20 strip, updated header comment.
- `tests/test_hygiene.py`: `test_dockerfile_pins_ghidra`, `test_dockerfile_checks_every_download`, `test_dockerfile_copies_nothing_from_the_context`.
- `tests/test_ghidra_real.py` (new): smoke, synthetic drafts, verb host message, unknown EXE, real export (4 tests per EXE), real drafts.
- `tools/reverseapoc/cli.py`: `ghidra-export` and `lint` verbs; GhidraError and LintError registered.
- `include/watcom_compat.h` (new), `tools/reverseapoc/lint.py` (new), `tests/test_lint.py` (new).
- Gitignored, in the main checkout: `build/ghidra/{ufo2p,tacp}/functions.raw.csv` (`git check-ignore` exits 0), `build/gate/05-image-size.txt`, `build/gate/05-docker-build*.log`, `build/gate/05-ghidra-smoke.out`, `build/gate/05-ghidra-real.out`, `build/gate/05-lint.out`, `build/gate/05-container-suite.out`.

## Decisions Made
See `key-decisions` in the frontmatter.

## Deviations from Plan

No orchestrator ruling amends 05-12. I followed the "For 05-12 (notes)" items: no Java fix was needed. Both 05-10 GhidraScripts compiled under Ghidra 12.1.4 on the first container run. The LE object-address check is done on the synthetic entry (0x00010123) and on the UFO2P entry plus the cmain386 row (0x000C5C9C), and both resolve to functions. The Ghidra and loader SHA-256 pins matched and were not touched.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Drifted apt pins in the existing Dockerfile**
- **Found during:** Task 1 (first `docker compose build`)
- **Issue:** The build failed with `Version '20260601~24.04.1' for 'ca-certificates' was not found` and `Version '5.6.1+really5.4.5-1ubuntu0.3' for 'xz-utils' was not found`. Ubuntu had published security updates since the pins were set, so the image could not be built from scratch at all, Ghidra or not.
- **Fix:** I followed the Dockerfile's own documented procedure: `apt-cache policy` in a fresh pinned ubuntu:24.04. Then I moved both pins to the current candidates, `ca-certificates=20260816ubuntu0.24.04.1` and `xz-utils=5.6.1+really5.4.5-1ubuntu0.4`, and added a dated comment. The other pins (curl, unzip, git, binutils, ninja, clang-format, clangd) and the plan's new JDK and clang pins were still the archive candidates. The base digest and every SHA-256 are unchanged.
- **Files modified:** docker/Dockerfile
- **Verification:** a clean `docker compose build` succeeds, and the hygiene tests pass.
- **Committed in:** `e2b86e1`

**2. [Rule 1 - Test oracle vs measured fact] One Ghidra function in each EXE's data object**
- **Found during:** Task 2 (first real run)
- **Issue:** The plan's check "every entry inside the code object" failed on both EXEs, each with exactly one entry outside it: UFO2P `0x0013BD40` and TACP `0x002B405C`. Both sit in the data object and have a one-address body. That is Ghidra analysis noise, not code.
- **Fix:** `test_export_real_entries_in_code_object` now allows at most `DATA_OBJECT_NOISE = 1` entry outside the code object per EXE, and only one inside the data object with a one-address body. Every other entry must be in the code object. The raw export is unchanged. It is raw, and the adapter does not drop rows silently. Reconcile (05-16) must drop entries outside the code object.
- **Files modified:** tests/test_ghidra_real.py
- **Verification:** 14 passed in the container. A second data-object entry, or a longer body, would fail the test.
- **Committed in:** `ab42674`

**3. [Rule 2 - Missing critical] Extra tests beyond the plan's list**
- **Found during:** Tasks 1-3
- **Issue:** The plan listed one synthetic import test, one host verb test and six lint tests. The review note on `toAddr(long)`, the unknown-EXE path, the `--stamp` contract and `collect_sources` were untested.
- **Fix:** I added these tests: `test_headless_drafts_a_synthetic_le`, `test_ghidra_export_verb_refuses_an_unknown_exe`, the cmain386 address in `test_drafts_real`, `test_lint_flags_are_the_d14_command`, `test_lint_reports_a_failing_file`, `test_collect_sources`, `test_collect_sources_refuses_a_missing_path`, `test_lint_verb_writes_the_stamp_only_when_ok` and `test_lint_verb_without_clang_names_the_container`.
- **Committed in:** `5cafd4b`, `5aa890c`, `cd08f43`

---

**Total deviations:** 3 auto-fixed (1 blocking, 1 test-oracle correction, 1 missing coverage)
**Impact on plan:** No scope change. Deviation 1 was needed for any image build. Deviation 2 records a real Ghidra fact that 05-16 needs.

## Issues Encountered
- The first build attempt failed on the drifted apt pins (deviation 1); the second built cleanly.
- `ruff format` on cli.py rewrote two unrelated lines (an `except (A, B, C):` into the unparenthesised 3.14 form). The repo is not ruff-formatted as a whole, so I reverted both hunks and committed only the verb's own lines.

## Verification
- Host: `uv run pytest -q`: 1401 passed, 21 skipped (Ghidra, clang, container-only and POSIX-only skips). `uv run ruff check .`: clean.
- Container, run after the host suite finished: `docker compose run --rm test`: 1420 passed, 2 skipped. Both skips are `Windows-only: msvcrt lock path` in tests/test_cc_log.py, the allowed container skip.
- The plan-level verify commands all pass. Smoke: no SKIPPED. Real export: both CSVs non-empty, no SKIPPED. Lint: no SKIPPED.

## Next Phase Readiness
- 05-16 can read the cached raw exports in the main checkout's build/ghidra/<exe>/functions.raw.csv. It should drop the one data-object entry per EXE.
- 05-14 can use `lint.CLANGD_FLAGS` for compile_commands.json and `reverseapoc lint --stamp FILE` for its ninja lint edge.
- docs/toolchain.md "what is in the container" does not mention Ghidra, the JDK or clang yet. The plan did not list docs; this is left to the phase's docs plan (05-15).

## Self-Check: PASSED
- FOUND: docker/Dockerfile, tests/test_hygiene.py, tests/test_ghidra_real.py, tools/reverseapoc/cli.py, include/watcom_compat.h, tools/reverseapoc/lint.py, tests/test_lint.py, build/gate/05-image-size.txt, build/ghidra/ufo2p/functions.raw.csv, build/ghidra/tacp/functions.raw.csv
- FOUND commits: 5cafd4b, e2b86e1, 5aa890c, ab42674, fefd7f9, cd08f43, 1701786 (7 = `git rev-list --count 39c20fe..HEAD` before this SUMMARY commit)
- Acceptance: `grep -n "__clang__" include/watcom_compat.h` gives lines 21 and 41. `grep -n "1060" tools/reverseapoc/lint.py` shows `WATCOMC_VALUE = "1060"` on line 24. `git check-ignore -q build/ghidra/ufo2p/functions.raw.csv` exits 0.

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
