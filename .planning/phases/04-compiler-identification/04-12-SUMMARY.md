---
phase: 04-compiler-identification
plan: 12
subsystem: testing
tags: [phase-gate, watcom, wibo, docker, pytest, ruff, rebuild, cmp]

requires:
  - phase: 04-compiler-identification
    provides: "plans 04-01..04-11: wpack decoder and 10.5 install (D-01 LANDED), cflags wrapper, OMF reader, libmatch runtime map, probe, cppscan, toolchain.md record, D-03 log"
  - phase: 03-byte-identical-round-trip
    provides: "rebuild + cmp gate form and the build/gate/ logging convention (03-10)"
provides:
  - "Phase 4 gate run on the main checkout, host and container, every step exit=0, logged under build/gate/04-12/"
  - "Container proof of CID-01: test_compiler_real.py and test_probe_real.py pass under wibo (/usr/local/bin/wibo) for 10.5, 10.6 and 11.0 from the read-only tree"
  - "04-VALIDATION.md: wave_0_complete true, every map row and the D-03 row green with log citations, Wave 0 boxes ticked"
affects: [gsd-verify-work 4, gsd-validate-phase 4, phase-05]

actuals:
  tokens: 7500
  tasks: 2
  commits: 1
plan_head_before: b347206c8563a6e5119f531fc1c94e5cfefc2fdb
plan_head_after: 4bb80f6e79d043bc7300074fb2dfb940b79356b0

tech-stack:
  added: []
  patterns:
    - "Phase gate = one log per step under build/gate/<plan>/, each ending exit=STATUS; Docker steps redirect on the host side"

key-files:
  created:
    - .planning/phases/04-compiler-identification/04-12-SUMMARY.md
  modified:
    - .planning/phases/04-compiler-identification/04-VALIDATION.md

key-decisions:
  - "Phase 4 gate green on host and container: 974 passed / 6 platform-only skips (host), 980 passed / 0 skipped (container), ruff clean on both; no real-file test skipped anywhere"
  - "Added a supplementary verbose container log (08-container-real-verbose.log) so the record names test_compiler_real.py and test_probe_real.py passing under wibo; the seven planned logs are unchanged"

patterns-established:
  - "Gate verify reads the logs, not the narrative: file count, exit lines, OK lines, silent cmp, no SKIPPED real-file line"

requirements-completed: [CID-01, CID-02, CID-03, CID-04, CID-05, CID-06]

coverage:
  - id: D1
    description: "Host suite and ruff green with every real-file test executed natively (no test_*_real.py skip)"
    requirement: CID-01
    verification:
      - kind: integration
        ref: "uv run pytest -q -rs && uv run ruff check . (build/gate/04-12/01-host-suite.log: 974 passed, 6 skipped [platform-only], All checks passed!, exit=0)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Phase 3 does not regress: rebuild prints three OK lines and cmp against orig/ is silent"
    verification:
      - kind: integration
        ref: "uv run reverseapoc rebuild; cmp build/{UFO2P,TACP,SMKP}.EXE orig/ (build/gate/04-12/02-rebuild.log, 03-cmp.log: exit=0 only)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Watcom 10.5, 10.6 and 11.0 trees verified, every key file OK, none KNOWN BAD"
    requirement: CID-01
    verification:
      - kind: integration
        ref: "uv run reverseapoc check-watcom 10.5 10.6 11.0 (build/gate/04-12/04-check-watcom.log: 8/8/10 ok, 0 known bad, exit=0)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Container done gate: docker compose run --rm test and the build-service suite with -rs pass with no skip; compiler and probe real tests run under wibo"
    requirement: CID-01
    verification:
      - kind: integration
        ref: "(cd docker && docker compose run --rm test) (build/gate/04-12/05-container-test.log: 980 passed, exit=0)"
        status: pass
      - kind: integration
        ref: "(cd docker && docker compose run --rm build bash -lc \"uv sync --locked && uv run pytest -q -rs && uv run ruff check .\") (build/gate/04-12/06-container-suite.log: 980 passed, All checks passed!, exit=0)"
        status: pass
      - kind: integration
        ref: "container pytest -v tests/test_compiler_real.py tests/test_probe_real.py (build/gate/04-12/08-container-real-verbose.log: 66 passed under /usr/local/bin/wibo, exit=0)"
        status: pass
    human_judgment: false
  - id: D5
    description: "runtime.csv drift test passes for both EXEs; D-03 log normalized equal for 10.5, 10.6, 11.0 with no DIFFERENT line"
    requirement: CID-04
    verification:
      - kind: integration
        ref: "uv run pytest -q -rs tests/test_libmatch_real.py (build/gate/04-12/07-drift.log: 10 passed, exit=0)"
        status: pass
      - kind: other
        ref: "grep -qE '^D-03: normalized equal for ' build/gate/04-native-vs-wibo.txt && ! grep -q DIFFERENT build/gate/04-native-vs-wibo.txt"
        status: pass
    human_judgment: false
  - id: D6
    description: "04-VALIDATION.md records the gate: wave_0_complete true, no pending row, Wave 0 boxes ticked"
    verification:
      - kind: other
        ref: "grep -q '^wave_0_complete: true' 04-VALIDATION.md && ! grep -qE '^\\|.*⬜ pending' 04-VALIDATION.md"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 12: Phase 4 gate Summary

**Phase 4 gate green on the main checkout: host 974 passed (6 platform-only skips) and container 980 passed / 0 skipped with ruff clean, the three EXEs still rebuild SHA-1 identical with silent cmp, check-watcom OK for 10.5/10.6/11.0, runtime.csv drift-free, and the compiler and probe real tests passing under wibo inside docker compose run.**

## Performance

- **Duration:** 9 min (gate run and record; reading not counted)
- **Started:** 2026-10-21T21:32:01Z
- **Completed:** 2026-10-21T21:41:00Z
- **Tasks:** 2
- **Files modified:** 1 tracked (04-VALIDATION.md) plus this SUMMARY; 8 gitignored logs under build/gate/04-12/

## Accomplishments

- Ran the seven planned gate steps on the main checkout, each into build/gate/04-12/0N-NAME.log with a final `exit=STATUS` line. All seven end `exit=0`.
- Host: `uv run pytest -q -rs` gives 974 passed and 6 skipped. The 6 are platform-only (2: Windows file names cannot hold `|` or LF; 1: non-UTF-8 byte names; 3: only inside the container). No test_*_real.py was skipped. `ruff check .` passes.
- Container: `docker compose run --rm test` gives 980 passed. The build-service run with `-rs` gives 980 passed and 0 skipped, and ruff passes. A verbose supplementary run shows wibo at /usr/local/bin/wibo and all 66 tests in test_compiler_real.py and test_probe_real.py passing, including `test_compile_real[10.5]`, `[10.6]` and `[11.0]`. That is CID-01 inside `docker compose run`.
- Phase 3 holds: rebuild prints three OK lines (UFO2P, TACP, SMKP == manifest) and cmp against orig/ prints nothing.
- check-watcom: 10.5 8 ok, 10.6 8 ok, 11.0 10 ok, with 0 mismatched, 0 missing and 0 known bad. 10.5 BINW/WCC386.EXE is OK, not KNOWN BAD, because D-01 LANDED.
- Drift: test_libmatch_real.py 10 passed. The D-03 log ends `D-03: normalized equal for 10.5, 10.6, 11.0` and has no DIFFERENT line.
- 04-VALIDATION.md: `wave_0_complete: true`, all 15 map rows and the D-03 manual row "✅ green" with their log citations, and the five Wave 0 boxes ticked. `status` and `nyquist_compliant` are left for /gsd-validate-phase.

## Task Commits

1. **Task 1 (tracer): the Phase 4 gate on host and container** — no commit. Its only outputs are the gitignored logs under build/gate/04-12/, which are reproduced below. This follows the Phase 3 gate plan 03-10, which also committed no logs.
2. **Task 2: record the gate in 04-VALIDATION.md** — `4bb80f6` (docs)

**Plan metadata:** the commit that adds this SUMMARY together with STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Files Created/Modified

- `.planning/phases/04-compiler-identification/04-VALIDATION.md`: `wave_0_complete: true`, Status column filled, a Status column added to the manual-only table for the D-03 row, Wave 0 boxes ticked.
- `build/gate/04-12/01-host-suite.log` .. `07-drift.log` and `08-container-real-verbose.log`: gitignored, reproduced below.

## Decisions Made

- Tracer gate (Task 1): interactive run, `human_verify_mode: end-of-phase`, verify is automated only. All five verify commands ran after the gate and exited 0 before Task 2 started.
- In the map, unit rows cite 04-12/01 (host) and 04-12/06 (container), since both full suites ran them. Real compiler and probe rows also cite 04-12/08 (under wibo). The runtime.csv row also cites 04-12/07.

## Deviations from Plan

**1. [Rule 2 - Missing evidence] Supplementary verbose container log**
- **Found during:** Task 1
- **Issue:** The plan's key_link and acceptance criterion expect 06-container-suite.log to show test_compiler_real.py and test_probe_real.py passing under wibo. A `-q` run prints only dots and a count, so the log never names those files.
- **Fix:** Ran an extra container step, `(cd docker && docker compose run --rm build bash -lc "command -v wibo && uv run pytest -v -rs tests/test_compiler_real.py tests/test_probe_real.py")`, into build/gate/04-12/08-container-real-verbose.log, which ends `exit=0`. The seven planned logs are unchanged, and the plan's `0[1-7]` verify glob does not see the extra log.
- **Files modified:** none tracked
- **Verification:** 66 passed, wibo found at /usr/local/bin/wibo, exit=0
- **Committed in:** n/a (gitignored log)

**Total deviations:** 1 (Rule 2: evidence only). **Impact on plan:** no source, test, config or Docker file was touched. The extra log only makes the container CID-01 proof visible.

Left as planned: the "File Exists" column of the map still reads "❌ W0"/"extend". The plan asked only for the Status column, and the Wave 0 boxes now record that the files exist.

## Issues Encountered

None. Every gate step passed on the first run.

## User Setup Required

None. No external service configuration is required.

## Phase gate output

All logs are reproduced verbatim (CR stripped) in step order, each under the command line it ran. Steps 1-4 and 7 ran on the Windows host. Steps 5, 6 and the supplementary step 8 ran in the container, with output redirected on the host side.

### 1. `uv run pytest -q -rs && uv run ruff check .` (build/gate/04-12/01-host-suite.log)

```
........................................................................ [  7%]
........................................................................ [ 14%]
....................................................................ss.. [ 22%]
.............s.......................................................... [ 29%]
.........................................................sss............ [ 36%]
........................................................................ [ 44%]
........................................................................ [ 51%]
........................................................................ [ 58%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 80%]
........................................................................ [ 88%]
........................................................................ [ 95%]
............................................                             [100%]
=========================== short test summary info ===========================
SKIPPED [2] tests\test_configure.py:199: Windows file names cannot hold | or LF
SKIPPED [1] tests\test_configure.py:273: needs a file system that stores non-UTF-8 byte names
SKIPPED [3] tests\test_hygiene.py:355: only inside the container
974 passed, 6 skipped in 118.94s (0:01:58)
All checks passed!
exit=0
```

### 2. `uv run reverseapoc rebuild` (build/gate/04-12/02-rebuild.log)

```
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

### 3. `cmp build/UFO2P.EXE orig/UFO2P.EXE && cmp build/TACP.EXE orig/TACP.EXE && cmp build/SMKP.EXE orig/SMKP.EXE` (build/gate/04-12/03-cmp.log)

```
exit=0
```

### 4. `uv run reverseapoc check-watcom 10.5 10.6 11.0` (build/gate/04-12/04-check-watcom.log)

```
Watcom 10.5: C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\third_party\watcom\10.5
  OK        BINNT/WCC386.EXE
  OK        BINW/WCC386.EXE
  OK        BINNT/WLINK.EXE
  OK        LIB386/DOS/CLIB3R.LIB
  OK        LIB386/DOS/CLIB3S.LIB
  OK        LIB386/MATH3R.LIB
  OK        LIB386/MATH387R.LIB
  OK        H/STDIO.H
8 ok, 0 mismatched, 0 missing, 0 known bad
Watcom 10.6: C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\third_party\watcom\10.6
  OK        BINNT/WCC386.EXE
  OK        BINW/WCC386.EXE
  OK        BINNT/WLINK.EXE
  OK        LIB386/DOS/CLIB3R.LIB
  OK        LIB386/DOS/CLIB3S.LIB
  OK        LIB386/MATH3R.LIB
  OK        LIB386/MATH387R.LIB
  OK        H/STDIO.H
8 ok, 0 mismatched, 0 missing, 0 known bad
Watcom 11.0: C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\third_party\watcom\11.0
  OK        BINNT/WCC386.EXE
  OK        BINW/WCC386.EXE
  OK        BINNT/WLINK.EXE
  OK        LIB386/DOS/CLIB3R.LIB
  OK        LIB386/DOS/CLIB3S.LIB
  OK        LIB386/MATH3R.LIB
  OK        LIB386/MATH387R.LIB
  OK        H/STDIO.H
  OK        BINNT/WCCD386.DLL
  OK        BINNT/WLINK.DLL
10 ok, 0 mismatched, 0 missing, 0 known bad
exit=0
```

### 5. `(cd docker && docker compose run --rm test)` (build/gate/04-12/05-container-test.log)

```
 Container docker-test-run-7e74749cb891 Creating 
 Container docker-test-run-7e74749cb891 Created 
Resolved 8 packages in 7ms
Checked 7 packages in 7ms
........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 22%]
........................................................................ [ 29%]
........................................................................ [ 36%]
........................................................................ [ 44%]
........................................................................ [ 51%]
........................................................................ [ 58%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 80%]
........................................................................ [ 88%]
........................................................................ [ 95%]
............................................                             [100%]
980 passed in 117.46s (0:01:57)
exit=0
```

### 6. `(cd docker && docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check .")` (build/gate/04-12/06-container-suite.log)

```
 Container docker-build-run-e63520143b39 Creating 
 Container docker-build-run-e63520143b39 Created 
Resolved 8 packages in 2ms
Checked 7 packages in 3ms
........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 22%]
........................................................................ [ 29%]
........................................................................ [ 36%]
........................................................................ [ 44%]
........................................................................ [ 51%]
........................................................................ [ 58%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 80%]
........................................................................ [ 88%]
........................................................................ [ 95%]
............................................                             [100%]
980 passed in 120.76s (0:02:00)
All checks passed!
exit=0
```

### 7. `uv run pytest -q -rs tests/test_libmatch_real.py` (build/gate/04-12/07-drift.log)

```
..........                                                               [100%]
10 passed in 36.77s
exit=0
```

### 8 (supplementary). `(cd docker && docker compose run --rm build bash -lc "command -v wibo && uv run pytest -v -rs tests/test_compiler_real.py tests/test_probe_real.py")` (build/gate/04-12/08-container-real-verbose.log)

```
 Container docker-build-run-d1f541518f61 Creating 
 Container docker-build-run-d1f541518f61 Created 
/usr/local/bin/wibo
============================= test session starts ==============================
platform linux -- Python 3.14.5, pytest-9.1.1, pluggy-1.7.0 -- /opt/venv/bin/python
cachedir: .pytest_cache
rootdir: /work
configfile: pyproject.toml
collecting ... collected 66 items

tests/test_compiler_real.py::test_compile_real[10.5] PASSED              [  1%]
tests/test_compiler_real.py::test_compile_real[10.6] PASSED              [  3%]
tests/test_compiler_real.py::test_compile_real[11.0] PASSED              [  4%]
tests/test_compiler_real.py::test_normalized_hash_is_stable[10.6] PASSED [  6%]
tests/test_compiler_real.py::test_normalized_hash_is_stable[11.0] PASSED [  7%]
tests/test_compiler_real.py::test_env_injection_has_no_effect[10.6] PASSED [  9%]
tests/test_compiler_real.py::test_env_injection_has_no_effect[11.0] PASSED [ 10%]
tests/test_compiler_real.py::test_target_is_dos[10.6] PASSED             [ 12%]
tests/test_compiler_real.py::test_target_is_dos[11.0] PASSED             [ 13%]
tests/test_compiler_real.py::test_cflags_two_sources_real PASSED         [ 15%]
tests/test_compiler_real.py::test_compile_error_cleans_up[10.6] PASSED   [ 16%]
tests/test_compiler_real.py::test_compile_error_cleans_up[11.0] PASSED   [ 18%]
tests/test_probe_real.py::test_byte_compare_calibration PASSED           [ 19%]
tests/test_probe_real.py::test_calibration_rows[10.6-3r-movzx] PASSED    [ 21%]
tests/test_probe_real.py::test_calibration_rows[10.6-5r-and-unrolled] PASSED [ 22%]
tests/test_probe_real.py::test_calibration_rows[10.6-5r-no-small-rep] PASSED [ 24%]
tests/test_probe_real.py::test_calibration_rows[10.6-3r-small-rep] PASSED [ 25%]
tests/test_probe_real.py::test_calibration_rows[10.6-4r-small-rep] PASSED [ 27%]
tests/test_probe_real.py::test_calibration_rows[11.0-3r-small-rep] PASSED [ 28%]
tests/test_probe_real.py::test_calibration_rows[11.0-4r-small-rep] PASSED [ 30%]
tests/test_probe_real.py::test_calibration_rows[11.0-5r-no-small-rep] PASSED [ 31%]
tests/test_probe_real.py::test_calibration_rows[10.6-3r_s-switch-up] PASSED [ 33%]
tests/test_probe_real.py::test_calibration_rows[10.6-4r_s-switch-up] PASSED [ 34%]
tests/test_probe_real.py::test_calibration_rows[10.6-5r_s-switch-up] PASSED [ 36%]
tests/test_probe_real.py::test_calibration_rows[10.6-5r-switch-up] PASSED [ 37%]
tests/test_probe_real.py::test_calibration_rows[10.6-4r_s_ox-switch-up] PASSED [ 39%]
tests/test_probe_real.py::test_calibration_rows[10.6-5r_s_ox-switch-up] PASSED [ 40%]
tests/test_probe_real.py::test_calibration_rows[10.6-5r_s_os-switch-up] PASSED [ 42%]
tests/test_probe_real.py::test_calibration_rows[10.6-5r_s_fpi87-switch-up] PASSED [ 43%]
tests/test_probe_real.py::test_calibration_rows[10.6-5s_s-switch-up] PASSED [ 45%]
tests/test_probe_real.py::test_calibration_rows[11.0-3r_s-switch-up] PASSED [ 46%]
tests/test_probe_real.py::test_calibration_rows[11.0-4r_s-switch-up] PASSED [ 48%]
tests/test_probe_real.py::test_calibration_rows[11.0-5r_s-switch-up] PASSED [ 50%]
tests/test_probe_real.py::test_calibration_rows[11.0-5r-switch-up] PASSED [ 51%]
tests/test_probe_real.py::test_calibration_rows[11.0-4r_s_ox-switch-up] PASSED [ 53%]
tests/test_probe_real.py::test_calibration_rows[11.0-5r_s_ox-switch-up] PASSED [ 54%]
tests/test_probe_real.py::test_calibration_rows[11.0-5r_s_os-switch-up] PASSED [ 56%]
tests/test_probe_real.py::test_calibration_rows[11.0-5r_s_fpi87-switch-up] PASSED [ 57%]
tests/test_probe_real.py::test_calibration_rows[11.0-5s_s-switch-up] PASSED [ 59%]
tests/test_probe_real.py::test_calibration_rows[11.0-4r-and] PASSED      [ 60%]
tests/test_probe_real.py::test_calibration_rows[11.0-5r-branch] PASSED   [ 62%]
tests/test_probe_real.py::test_calibration_rows[10.6-rotated] PASSED     [ 63%]
tests/test_probe_real.py::test_calibration_rows[11.0-top-tested] PASSED  [ 65%]
tests/test_probe_real.py::test_calibration_rows[10.6-no-s-chk] PASSED    [ 66%]
tests/test_probe_real.py::test_calibration_rows[11.0-no-s-chk] PASSED    [ 68%]
tests/test_probe_real.py::test_calibration_rows[10.6-s-no-chk] PASSED    [ 69%]
tests/test_probe_real.py::test_calibration_rows[11.0-s-no-chk] PASSED    [ 71%]
tests/test_probe_real.py::test_calibration_libraries[10.6-fpi-emu387] PASSED [ 72%]
tests/test_probe_real.py::test_calibration_libraries[10.6-fpi87-noemu387] PASSED [ 74%]
tests/test_probe_real.py::test_calibration_libraries[10.6-5s-math387s] PASSED [ 75%]
tests/test_probe_real.py::test_calibration_libraries[10.6-5s-clib3s-measured-absent] PASSED [ 77%]
tests/test_probe_real.py::test_calibration_libraries[11.0-fpi-emu387] PASSED [ 78%]
tests/test_probe_real.py::test_calibration_libraries[11.0-fpi87-noemu387] PASSED [ 80%]
tests/test_probe_real.py::test_calibration_libraries[11.0-5s-math387s] PASSED [ 81%]
tests/test_probe_real.py::test_calibration_libraries[11.0-5s-clib3s-measured-absent] PASSED [ 83%]
tests/test_probe_real.py::test_calibration_covers_every_flag_set PASSED  [ 84%]
tests/test_probe_real.py::test_calibration_with_10_5 PASSED              [ 86%]
tests/test_probe_real.py::test_exe_nonlibrary_idioms[UFO2P.EXE] PASSED   [ 87%]
tests/test_probe_real.py::test_exe_chk_calls[UFO2P.EXE] PASSED           [ 89%]
tests/test_probe_real.py::test_exe_struct_copy_sizes[UFO2P.EXE] PASSED   [ 90%]
tests/test_probe_real.py::test_exe_consistent_cells[UFO2P.EXE] PASSED    [ 92%]
tests/test_probe_real.py::test_exe_nonlibrary_idioms[TACP.EXE] PASSED    [ 93%]
tests/test_probe_real.py::test_exe_chk_calls[TACP.EXE] PASSED            [ 95%]
tests/test_probe_real.py::test_exe_struct_copy_sizes[TACP.EXE] PASSED    [ 96%]
tests/test_probe_real.py::test_exe_consistent_cells[TACP.EXE] PASSED     [ 98%]
tests/test_probe_real.py::test_calibration_copy_sizes PASSED             [100%]

============================= 66 passed in 17.18s ==============================
exit=0
```

### D-03 log (build/gate/04-native-vs-wibo.txt, written by plan 04-11, unchanged)

```
# D-03 (04-CONTEXT.md): probe/cg_basic.c compiled natively on the Windows host and under wibo 1.2.0 in
# docker compose run (service build), once per Watcom version, with build/d03/cflags-<v>.txt = '*  wcc386@<v>  -5r -s'
# (the comparison flag set, not the game's flags).
# native:    uv run reverseapoc cc probe/cg_basic.c -o build/d03/native-<v>.obj --cflags build/d03/cflags-<v>.txt
# container: (cd docker && docker compose run --rm build bash -lc "uv sync --locked && uv run reverseapoc cc probe/cg_basic.c -o build/d03/wibo-<v>.obj --cflags build/d03/cflags-<v>.txt")
# normalized = SHA-1 over every OMF record except THEADR (0x80) and COMENT class 0xE9 (absolute paths, timestamps).
# date: 2026-10-21
10.5  native sha1 a8959f459c510fe3214c3704bd0cb5b13af582e9 normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  wibo sha1 1c3ad3b57a332f31dd1d488357fd354e5f12571b normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  normalized equal
  native banner: WATCOM C32 Optimizing Compiler  Version 10.5
  wibo banner:   WATCOM C32 Optimizing Compiler  Version 10.5
10.6  native sha1 a8959f459c510fe3214c3704bd0cb5b13af582e9 normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  wibo sha1 1c3ad3b57a332f31dd1d488357fd354e5f12571b normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  normalized equal
  native banner: WATCOM C32 Optimizing Compiler  Version 10.6
  wibo banner:   WATCOM C32 Optimizing Compiler  Version 10.6
11.0  native sha1 538da4b77b57e90c772bb0dd01c80db04e31bc7e normalized 419decf88073e026a0ebfff588ccc3ff1bd5f03c  wibo sha1 7f2f562574abdb9695b6aa687711af0f863cba84 normalized 419decf88073e026a0ebfff588ccc3ff1bd5f03c  normalized equal
  native banner: Watcom C32 Optimizing Compiler  Version 11.0
  wibo banner:   Watcom C32 Optimizing Compiler  Version 11.0
D-03: normalized equal for 10.5, 10.6, 11.0
```

## Verification

Task 1 verify, all exit 0 (run after the gate, before Task 2):
1. Seven logs exist and `tail -qn 1 ... | sort -u` is exactly `exit=0`.
2. Three `OK <EXE> sha1 ... == manifest` lines are present, and 03-cmp.log is exactly `exit=0`.
3. Both suite logs show a passed count, and there is no SKIPPED real-file line.
4. 04-03 says LANDED, not DEFERRED, so the check that no real-file line was skipped applies, and it holds.
5. The D-03 result line is present, with no DIFFERENT line.

Task 2 verify: `wave_0_complete: true` is set and no table row is pending. Exit 0.

## Next Phase Readiness

- Every Phase 4 plan (12/12) now has a SUMMARY, so the phase is ready for `/gsd-verify-work 4` (and `/gsd-validate-phase 4` for `status`/`nyquist_compliant`).
- Open owner item, not changed here: the 10.5/10.6 BINNT notes in config/watcom.toml still say "the real LE compiler", but the BINW compilers are LX.
- CID-04/05/06 edge rows: per the plan's flagged assumptions, they stay as surfaced in plans 04-05, 04-10/04-11 and 04-09.

## Self-Check: PASSED

- Files found: .planning/phases/04-compiler-identification/04-VALIDATION.md, build/gate/04-12/01..08 logs, build/gate/04-native-vs-wibo.txt.
- Commit found on HEAD's history: 4bb80f6 (`git merge-base --is-ancestor`).
- No source, test, config, tools or Docker file changed (`git diff --stat b347206..HEAD` touches only 04-VALIDATION.md).

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
