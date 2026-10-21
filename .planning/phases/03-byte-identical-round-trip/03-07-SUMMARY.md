---
phase: 03-byte-identical-round-trip
plan: 07
subsystem: build
tags: [configure, ninja, build.ninja, argparse, utf-8, gap-closure]
gap_closure: true
gap_ids: [G-03-6]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "03-06 configure.py: ConfigureError refusals, the _SAFE_ORIG allowlist, the {orig} HEADER template and the sentinel tests"
provides:
  - "configure.py refuses a path it cannot write as UTF-8 (WR-07) with one `configure.py: error:` line and exit 1"
  - "main() encodes the whole build.ninja before opening the output and writes it with write_bytes, so a refusal never truncates an existing build.ninja"
  - "a leading `-` is refused in the orig dir and in every executable path that reaches a parse_le edge (IN-09)"
  - "check_orig description `CHECK-ORIG {orig}` and generic header comments (IN-10)"
  - "the rebuild rule passes `--out build`, the builddir, so `ninja verify` writes next to the build.ninja it runs from (IN-11)"
  - "module docstring and header without the earlier phase's skeleton wording (IN-08)"
affects: [03-10 phase gate, Phase 5 build.ninja compilation rules, Phase 6 driver]

actuals:
  tokens: 5668
  tasks: 2
  commits: 4
plan_head_before: 0269b2ae4057c5a94e96266de82d24e510915def
plan_head_after: bf341b578ae96b04c9dfb4cc046782dfd486c59b

tech-stack:
  added: []
  patterns:
    - "Encode before open: build the output bytes inside the try, write them after it, so no refusal touches the file"
    - "One helper (_refuse_option_like) guards every string that reaches reverseapoc's argparse as a positional or option value"

key-files:
  created: []
  modified:
    - configure.py
    - tests/test_configure.py

key-decisions:
  - "Encode-first with write_bytes and no temporary file: a refusal leaves build.ninja untouched and leaves no stray file; an OSError while writing stays out of scope (adjacent to WR-07)"
  - "`--out build` is written literally, equal to `builddir = build`; test_rebuild_out_is_the_builddir fails if the two drift; `$builddir` would not survive the host test that runs the command text through the CLI"
  - "The option check covers the full executable path only; the bare output name under $builddir/always/parse-le/ is never an argument, and a control assertion keeps orig/-h.exe accepted"

patterns-established:
  - "A configure.py refusal is a ConfigureError raised before any write; main() adds the `configure.py: error:` context in one except clause"

requirements-completed: []

coverage:
  - id: D1
    description: "WR-07: a non-UTF-8 executable name gives a `configure.py: error:` line naming the path by repr, exit 1, and an untouched build.ninja; no traceback"
    requirement: "RT-03"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_render_refuses_names_that_are_not_utf8"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_names_that_are_not_utf8"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_never_truncates_on_an_encoding_failure"
        status: pass
    human_judgment: false
  - id: D2
    description: "WR-07 on a real non-UTF-8 byte name (Linux file system only); skipped on the Windows host, runs in the container at 03-10 step 5"
    requirement: "RT-03"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_real_names_that_are_not_utf8"
        status: unknown
    human_judgment: true
    rationale: "Skipped on the Windows host by design; its RED and GREEN are proven only in the container run of plan 03-10"
  - id: D3
    description: "IN-09: an orig dir or executable path starting with `-` is refused with exit 1 and the sentinel kept"
    requirement: "RT-03"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_render_refuses_an_option_like_orig_dir"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_render_refuses_an_option_like_exe_path"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_an_option_like_orig_dir"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_an_option_like_exe_name"
        status: pass
      - kind: other
        ref: "uv run python configure.py --orig build/configure-smoke/-h --output build/configure-smoke/dash.ninja (exit 1, sentinel kept)"
        status: pass
    human_judgment: false
  - id: D4
    description: "IN-10: check_orig description and header comments name the orig dir, not a fixed orig/"
    requirement: "RT-03"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_render_check_orig_description_names_the_orig_dir"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_header_comments_name_no_fixed_orig_dir"
        status: pass
    human_judgment: false
  - id: D5
    description: "IN-11: the rebuild rule passes `--out build`, and the generated command writes into the builddir next to build.ninja (host end to end through the reverseapoc CLI)"
    requirement: "RT-03"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_rebuild_out_is_the_builddir"
        status: pass
      - kind: integration
        ref: "tests/test_configure.py#test_generated_rebuild_writes_into_builddir"
        status: pass
    human_judgment: false
  - id: D6
    description: "IN-08: no earlier phase label or `skeleton` in the docstring or header; `Phase 5` kept"
    requirement: "RT-03"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_no_stale_phase_wording"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-21
status: complete
---

# Phase 3 Plan 07: configure.py half of G-03-6 Summary

**configure.py refuses non-UTF-8 and leading-dash paths with one error line while leaving build.ninja byte-identical (encode before open), names the --orig dir in the CHECK-ORIG status line, and makes `ninja verify` write into the builddir via `rebuild --orig {orig} --out build`.**

## Performance

- **Duration:** about 8 min of execution (start 2026-10-21T02:27:56Z, last task commit 2026-10-21T02:35Z)
- **Started:** 2026-10-21T02:27:56Z
- **Completed:** 2026-10-21T02:35:22Z
- **Tasks:** 2 (both TDD, each RED then GREEN)
- **Files modified:** 2

## Accomplishments

- WR-07: `ninja_path` encodes each path as UTF-8 and raises ConfigureError (path by repr, "build.ninja is written as UTF-8; rename the file"). `main()` encodes the whole text inside the try. One except clause reports ConfigureError and UnicodeEncodeError as `configure.py: error:` and returns 1. The bytes are then written with `Path.write_bytes`, so an existing build.ninja is never truncated. `write_text` is gone from configure.py.
- IN-09: `_refuse_option_like` refuses a leading `-`. It runs in `_check_orig_dir` after the allowlist, and in `render()` on each full executable path before `ninja_path`. `_SAFE_ORIG`, the `--orig PATH` form and the unquoted `$in` are unchanged, and no `--` separator was added.
- IN-10: `description = CHECK-ORIG {orig}`. The check-orig and parse-le header comments now say "the orig dir".
- IN-11: `command = uv run reverseapoc rebuild --orig {orig} --out build`. The host end-to-end test runs that command through the CLI from `cfg/`. The image lands in `cfg/build/IN11.EXE`, and the monkeypatched DEFAULT_OUT stays empty.
- IN-08: the docstring and HEADER say "Verification targets only (check-orig, parse-le, verify)". The Phase 5 note, `REBUILD build/`, `builddir = build` and the parse_le rule are kept byte for byte.

## Task Commits

1. **Task 1 (tracer): non-UTF-8 and option-like paths (WR-07, IN-09)**
   - RED: `9939f81` test(03-07): add failing tests for non-UTF-8 and option-like paths
   - GREEN: `231ee0d` fix(03-07): refuse non-UTF-8 and option-like paths without truncating build.ninja (WR-07, IN-09)
2. **Task 2: orig-dir description, --out build, stale wording (IN-10, IN-11, IN-08)**
   - RED: `1553453` test(03-07): add failing tests for the orig-dir description, --out build and stale wording
   - GREEN: `bf341b5` fix(03-07): name the orig dir in check-orig, write verify into the builddir, drop stale wording (IN-10, IN-11, IN-08)

GREEN hashes for 03-REVIEW-DISPOSITION.md: WR-07 and IN-09 are `231ee0d`. IN-10, IN-11 and IN-08 are `bf341b5`.

No REFACTOR commit was needed.

## RED Results

### Task 1 (at `0269b2a`, after adding the tests only): 11 failed, 29 passed, 3 skipped

| Test | Failure at HEAD |
|------|-----------------|
| test_render_refuses_names_that_are_not_utf8[low-surrogate] | DID NOT RAISE ConfigureError |
| test_render_refuses_names_that_are_not_utf8[high-surrogate] | DID NOT RAISE ConfigureError |
| test_main_refuses_names_that_are_not_utf8 | uncaught UnicodeEncodeError ('\udcff' at position 1364) from the text-mode writer |
| test_main_never_truncates_on_an_encoding_failure | uncaught UnicodeEncodeError ('\udcff' at position 3) |
| test_render_refuses_an_option_like_orig_dir[-h], [--orig], [-] | DID NOT RAISE ConfigureError (the control assert passed first) |
| test_render_refuses_an_option_like_exe_path[exe-name], [orig-dir] | DID NOT RAISE ConfigureError (the `orig/-h.exe` control passed first) |
| test_main_refuses_an_option_like_orig_dir | main returned 0 (wrote build.ninja) |
| test_main_refuses_an_option_like_exe_name | main returned 0 (wrote build.ninja) |

- test_main_refuses_real_names_that_are_not_utf8 is skipped on the Windows host ("needs a file system that stores non-UTF-8 byte names"). Its RED can only be shown in the container, and plan 03-10 step 5 runs it green there.
- Machine check: `gsd-tools check tdd-red-evidence` on pytest's JUnit XML report returned `RED_EVIDENCE_OK`. The target was `tests.test_configure#test_main_never_truncates_on_an_encoding_failure`, with exit 1 and 11 failing tests.
- Semantic assessment: each target ran and failed on its planned assertion or on the planned uncaught exception. There were no collection, import or fixture errors. The 29 passing tests are the unchanged controls.

### Task 2 (at `231ee0d`, after the test edits only): 18 failed, 27 passed, 3 skipped

| Test | Failure at HEAD |
|------|-----------------|
| test_render_has_verify_edge (pin :80) | `--orig orig --out build` not in the block (`--orig orig` only) |
| test_render_passes_orig_to_check_orig_and_rebuild (pins :115, :118) | `../elsewhere --out build` not in the block |
| test_main_passes_orig_to_check_orig_and_rebuild[same-dir], [sub-dir] (pin :146) | the command does not end with `--orig <orig> --out build` |
| test_render_refuses_an_unsafe_orig_dir (pin :214), all 9 ids | its first assert: `../safe-dir --out build` not in the block |
| test_render_check_orig_description_names_the_orig_dir | `description = CHECK-ORIG orig/` instead of `../elsewhere` |
| test_header_comments_name_no_fixed_orig_dir | 2 comment lines hold `orig/` |
| test_rebuild_out_is_the_builddir | `'' == 'build'` (no `--out`) |
| test_generated_rebuild_writes_into_builddir | FileNotFoundError for cfg/build/IN11.EXE: the rebuild wrote the monkeypatched default-out, never the repo's build/ (checked: no build/IN11.EXE afterwards) |
| test_no_stale_phase_wording | the earlier phase label is in configure.__doc__ |

- Machine check: `check tdd-red-evidence` returned `RED_EVIDENCE_OK`. The target was `tests.test_configure#test_generated_rebuild_writes_into_builddir`, with exit 1 and 18 failing tests.
- Semantic assessment: every failure is the planned assertion or the planned missing output file. None comes from setup.

## Mutants (applied alone after each GREEN commit, run, reverted; none committed)

After every revert, `git diff --exit-code -- configure.py` exited 0.

| # | Mutant | Tests that failed |
|---|--------|-------------------|
| T1-1 | Remove the UTF-8 check from `ninja_path` | test_render_refuses_names_that_are_not_utf8 [low-surrogate], [high-surrogate] |
| T1-2 | Text-mode write of the str before the encode, outside the try | test_main_never_truncates_on_an_encoding_failure |
| T1-3 | `_check_orig_dir` returns `orig` without the option check | test_render_refuses_an_option_like_orig_dir [-h], [--orig], [-]; test_main_refuses_an_option_like_orig_dir |
| T1-4 | `render()` calls `ninja_path(exe)` without the option check | test_render_refuses_an_option_like_exe_path [exe-name], [orig-dir]; test_main_refuses_an_option_like_exe_name |
| T2-1 | check_orig description back to `CHECK-ORIG orig/` | test_render_check_orig_description_names_the_orig_dir |
| T2-2 | Drop `--out build` from the rebuild rule | the five pins (test_render_has_verify_edge; test_render_passes_orig_to_check_orig_and_rebuild; test_main_passes_orig_to_check_orig_and_rebuild x2; test_render_refuses_an_unsafe_orig_dir x9), test_rebuild_out_is_the_builddir, test_generated_rebuild_writes_into_builddir (15 failed) |
| T2-3 | `--out $builddir` instead of the literal | the same 15 as T2-2 |
| T2-4 | Restore the earlier skeleton wording in HEADER | test_no_stale_phase_wording |
| extra | The check-orig header comment back to `verify orig/ against` | test_header_comments_name_no_fixed_orig_dir |

- T1-1: test_main_refuses_names_that_are_not_utf8 kept passing, because main's encode guard still catches the UnicodeEncodeError and prints `\udcff`. The plan expected this.
- T2-1: the plan expected the header-comment test to fail as well. It does not, because the description is a rule line, not a `#` comment. The extra mutant proves the header-comment test on its own.

## Files Created/Modified

- `configure.py`:
  - UTF-8 refusal in `ninja_path`;
  - `_refuse_option_like`, called from `_check_orig_dir` and from `render()`;
  - encode-before-open with `write_bytes` in `main()`;
  - `CHECK-ORIG {orig}`, generic header comments, `--out build` in the rebuild rule, and docstring and header wording without the earlier phase;
  - a render docstring note on the builddir.
- `tests/test_configure.py`:
  - 13 new tests (21 cases with the parametrized ids) and an `import os`;
  - the conftest import, the IN-11 comment and the five rebuild pins in their `--out build` form.
  - `git diff -U0 main` removes exactly five lines, all rebuild-command assertions.

## Decisions Made

- No temporary file plus os.replace. Encoding first already leaves build.ninja untouched on any refusal, and it leaves no stray file behind (the plan's flagged assumption).
- The orig-dir option refusal uses the same helper and message as the exe path ("the reverseapoc command in build.ninja would read it as an option"). The orig-dir message therefore does not repeat the "orig path" prefix of the allowlist message, and the tests check only `'-h'`.

## Deviations from Plan

1. **[Mutant expectation] T2-1 failed only the description test.** The plan predicted that the header-comment test would fail too. The code and tests are as planned; the prediction overlooked that a rule line is not a comment. I ran an extra reverted mutant (restoring `orig/` in a header comment), and it failed test_header_comments_name_no_fixed_orig_dir. Nothing was committed for this.
2. **[Test addition within plan scope] Over-refusal guard.** test_render_refuses_an_option_like_exe_path starts with a control assertion that `render(["orig/-h.exe"])` keeps the edge. That pins the plan's rule that the bare output name needs no check. It passed at HEAD and passes after GREEN.

**Total deviations:** 2 minor (one corrected mutant expectation, one added control assertion). **Impact:** none on the code. Scope stayed at configure.py and tests/test_configure.py.

## Issues Encountered

- The worktree sandbox refuses compound shell commands that mix `git` with other tools. Each git step ran as its own command. This had no effect on results.

## Verification

- `uv run pytest -q -rs tests/test_configure.py`: 45 passed, 3 skipped. The skips are the Windows-only `Windows file names cannot hold | or LF` x2 and the Linux-only `needs a file system that stores non-UTF-8 byte names`.
- `REVERSEAPOC_ORIG=C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig uv run pytest -q -rs`: 359 passed, 12 skipped. No skip names a missing orig/ file. The skips are the 3 configure skipifs above, 3 container-only hygiene tests, and 6 Watcom-media tests (third_party/watcom-media absent).
- `uv run ruff check .`: All checks passed.
- Smoke checks:
  - `-h` orig dir: exit 1 with `configure.py: error: '-h' starts with '-' ...`, and dash.ninja still reads `# sentinel`.
  - `--orig build/configure-smoke/elsewhere`: writes `  command = uv run reverseapoc rebuild --orig elsewhere --out build` and `  description = CHECK-ORIG elsewhere`.
- Acceptance greps:
  - absent: `write_text`, `Phase 2` and `CHECK-ORIG orig/`;
  - present: `write_bytes`, `rebuild --orig {orig} --out build`, `CHECK-ORIG {orig}`, `REBUILD build/`, `Phase 5` and `parse-le $in`;
  - `git diff --exit-code main -- tools/` exits 0.
- Docker and ninja were not run here, as instructed. The phase gate runs in plan 03-10 on main.

## User Setup Required

None.

## Next Phase Readiness

- Ready for 03-10, the phase gate after 03-07, 03-08 and 03-09 merge. 03-10 cites the GREEN hashes `231ee0d` and `bf341b5`. Its container run (step 5) is where test_main_refuses_real_names_that_are_not_utf8 goes green.
- RT-03 is left Pending in REQUIREMENTS.md. Sibling plans that are still running share it, and the orchestrator and 03-10 own that update.

## TDD Gate Compliance

| Task | RED commit | GREEN commit | REFACTOR |
|------|-----------|--------------|----------|
| 1 | 9939f81 test(03-07) | 231ee0d fix(03-07) | not needed |
| 2 | 1553453 test(03-07) | bf341b5 fix(03-07) | not needed |

- The plan names the GREEN commits `fix(03-07)`, not `feat`, because they are review-finding fixes. Each RED commit comes before its GREEN commit.

## Self-Check: PASSED

- FOUND: configure.py, tests/test_configure.py, 03-07-SUMMARY.md
- FOUND on this branch (git log 0269b2a..HEAD): 9939f81, 231ee0d, 1553453, bf341b5 (4 commits, the measured `commits:` value)

---
*Phase: 03-byte-identical-round-trip*
*Completed: 2026-10-21*
