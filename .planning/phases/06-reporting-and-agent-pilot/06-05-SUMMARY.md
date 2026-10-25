---
phase: 06-reporting-and-agent-pilot
plan: 05
subsystem: review-minors
tags: [di-19, matched-c, spike-005, tests, docker]

requires: []
provides:
  - "func_00055080 (TACP) carries a comment explaining its void return, comment-only"
  - "spike 005 README states the observed objdiff blind-spot shape, spike.py annotated"
  - "tests/test_le.py uses conftest's MZ constants; tests/test_hygiene.py exact pin regex"
  - "docker/Dockerfile lists everything the image does not contain in one list"
affects: [06-16, 06-20]

actuals:
  tokens: 19175  # chars/4 over the full text of the six changed files (76699 chars)
  tasks: 2
  commits: 6
plan_head_before: 021a58ba7441665b1eb5486caef92c91f23ad9c2
plan_head_after: d8be60c

tech-stack:
  added: []
  patterns:
    - "Comment-only proof for matched C: blank comments with configure._NOT_CODE/_blank, collapse whitespace, compare with the parent commit"

key-files:
  created: []
  modified:
    - src/tacp/u_00054f20.c
    - .planning/spikes/005-objdiff-omf-elf/README.md
    - .planning/spikes/005-objdiff-omf-elf/spike.py
    - tests/test_le.py
    - tests/test_hygiene.py
    - docker/Dockerfile

key-decisions:
  - "The exact pin regex is _EXACT_PIN (PEP 508 name, ==, a version of letters, digits and .+!_- starting with a letter or digit), matched with fullmatch"
  - "MZ constants come from tests/conftest.py, not le.py (ruling F21)"

patterns-established:
  - "Dependency pins are checked by one fullmatch regex; anything that is not a bare name==version is a problem"

requirements-completed: [AGT-06]

coverage:
  - id: D1
    description: "Comment on func_00055080's void return, with no change outside comments and whitespace (row 19b)"
    requirement: AGT-06
    verification:
      - kind: other
        ref: "uv run python -c '... configure._NOT_CODE blank + whitespace collapse, compare with 43daac3~1 ...' (plan Task 1 verify)"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_configure.py tests/test_check.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Spike 005 README states the observed blind-spot shape; spike.py Pair.module/segment and build_name_map annotated (rows 1, 2)"
    requirement: AGT-06
    verification:
      - kind: other
        ref: "uv run ruff check .planning/spikes/005-objdiff-omf-elf; typing.get_type_hints(spike.build_name_map) resolves"
        status: pass
    human_judgment: true
    rationale: "Whether the README wording is accurate and clear is a reading judgment; no test asserts prose"
  - id: D3
    description: "tests/test_le.py imports MZ_E_LFARLC, MZ_E_LFANEW, NEW_FORMAT_LFARLC from conftest; tests/test_hygiene.py exact name==version regex (row 5)"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_dependency_doc_check_refuses_anything_but_name_eq_version"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_le.py tests/test_hygiene.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "docker/Dockerfile DOES NOT CONTAIN comment is one list; no instruction changed (row 13a)"
    requirement: AGT-06
    verification:
      - kind: other
        ref: "non-comment lines of d8be60c~1:docker/Dockerfile equal those of docker/Dockerfile, file differs"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 05: Phase 5 review style and wording minors Summary

**A comment-only void-return note on matched TACP func_00055080 (proven token-identical outside comments), spike 005's blind spot restated as the observed `mov dword [abs32], imm32` shape, typed spike.py, conftest MZ constants in test_le, an exact `name==version` pin regex, and a single "does not contain" list in the Dockerfile.**

Execution context nonce: 787955882886fbc5

## Performance

- **Duration:** about 5 min
- **Started:** 2026-10-25T01:09:38Z
- **Completed:** 2026-10-25T01:14:04Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Row 19b: `src/tacp/u_00054f20.c` explains why `func_00055080` is `void` (store-only body; the bytes cannot tell
  `void` from `int ... return D = g();`) and points to docs/learnings.md, 2026-10-24. Comments blanked with
  configure's own `_NOT_CODE`/`_blank` and whitespace collapsed, the file equals its parent commit's text.
- Row 1: spike 005 README:175 now says that in the plants a wrong symbol on the 2nd relocation of
  `mov dword [abs32], imm32` still scored 100.0, and makes no claim about other instructions.
- Row 2: `Pair.module: Module`, `Pair.segment: Segment`, and `build_name_map(report: Report, exe: str, seg: Segment,
  base_va: int, flat: bytearray, le_fx: list[Fixup]) -> tuple[dict[int, str], list[int]]`. Behaviour unchanged.
- Row 5a: tests/test_le.py imports `MZ_E_LFARLC`, `MZ_E_LFANEW`, `NEW_FORMAT_LFARLC` from tests/conftest.py; the bare
  0x40 is now `NEW_FORMAT_LFARLC`.
- Row 5b: tests/test_hygiene.py uses `_EXACT_PIN.fullmatch` instead of `partition("==")`; a marker, an extra, a
  second `==`, a space or an empty name is refused (new parametrized test).
- Row 13a: the Open Watcom v2 compiler item moved into the "DOES NOT CONTAIN" list; the redundant "Watcom and the
  game are still never in the image" sentence went with it. Comments only.

## Task Commits

1. **Task 1: comment-only edit of matched TACP C** - `43daac3` (docs)
2. **Task 2: spike wording/annotations, test hygiene, Dockerfile comment**
   - `9d817e4` (test) test_le MZ constants from conftest
   - `02031f8` (test) RED: exact pin test
   - `d7e4601` (test) GREEN: exact pin regex
   - `191d094` (docs) spike 005 README and spike.py
   - `d8be60c` (docs) Dockerfile comment

## Files Created/Modified

- `src/tacp/u_00054f20.c` - void-choice comment (comment only)
- `.planning/spikes/005-objdiff-omf-elf/README.md` - observed blind-spot shape
- `.planning/spikes/005-objdiff-omf-elf/spike.py` - type annotations
- `tests/test_le.py` - constants from conftest
- `tests/test_hygiene.py` - `_EXACT_PIN` regex and its test
- `docker/Dockerfile` - CONTAIN comment as one list

## Decisions Made

- The pin regex accepts a PEP 508 name and a version of letters, digits and `.+!_-` (starting with a letter or
  digit), an allow-list, so it refuses markers and extras that `partition` let through. The one real pin (`capstone==5.0.9`) still passes.

## Deviations from Plan

**1. Orchestrator ruling F21: where the MZ constants live.** le.py defines no MZ constants, so tests/test_le.py
imports `MZ_E_LFARLC`, `MZ_E_LFANEW` and `NEW_FORMAT_LFARLC` from tests/conftest.py instead of le.py; le.py is not
edited. Commit `9d817e4`.

**2. [Rule 2 - test for a behaviour change] Exact-pin regex test.** The rulings ask for a test per behaviour change,
and the regex is stricter than `partition`. Added `test_dependency_doc_check_refuses_anything_but_name_eq_version`
(5 cases), committed RED (`02031f8`, all 5 failing against `partition`) before GREEN (`d7e4601`).

**3. [Rule 3 - blocking] Dockerfile verify run in an equivalent form.** The harness refused the plan's one-line
Dockerfile verify (git inside `$(...)` with `&&` chains) as unverifiable for a worktree agent. Ran the same check
in separate steps: `git show d8be60c~1:docker/Dockerfile` into the scratchpad, then a Python comparison of
non-comment, non-blank lines (equal) and of the whole file (differs). Result: pass.

**4. Task 2 split into five commits** by file group (the plan allows `chore`/`test`/`docs` per file group), with the
pin change as RED then GREEN.

---

**Total deviations:** 1 ruling applied, 3 minor execution adjustments. **Impact:** none on scope; no code token of
matched C changed.

## Issues Encountered

None. The host suite skips (215 in the full run, 3 in test_hygiene "only inside the container") are pre-existing
real-file and container-only skips; this plan adds no skip.

## Verification

- Task 1 verify (comment-only proof): exit 0. `uv run pytest -q tests/test_configure.py tests/test_check.py`: 145
  passed, 3 skipped. `git show --stat 43daac3` lists only src/tacp/u_00054f20.c; no `//` in the file.
- Task 1 is a tracer: verify re-run after commit passed, then expanded to Task 2.
- Task 2: `uv run pytest -q tests/test_le.py tests/test_hygiene.py` 103 passed, 3 skipped; `ruff check .` clean;
  `partition("==")` absent; Dockerfile instructions unchanged.
- Plan level: `uv run pytest -q` 1421 passed, 215 skipped; `uv run ruff check .` all checks passed.
- The byte identity of u_00054f20 is re-proven by the container gate after merge (plan 06-16), not in this worktree.

## User Setup Required

None.

## Next Phase Readiness

- The u_00054f20.c edit lands before 06-16 seeds status.csv, so the seeded `source_sha256` covers it.
- Spike 005's toolchain.md:340 wording (row 1, docs part) is left to plan 06-20.

## Self-Check: PASSED

- All six modified files exist; commits 43daac3, 9d817e4, 02031f8, d7e4601, 191d094, d8be60c are ancestors of HEAD.

## Fix round 1

The review approved the plan with no Critical or Important findings and asked for three cosmetic minors
(FIX_BASE 4b4c4c9).

1. **The pin regex comment matches the regex.** tests/test_hygiene.py's comment on `_EXACT_PIN` now says the
   version is letters, digits and `.+!_-` starting with a letter or digit (an allow-list), instead of "no `=`,
   `;`, `[` or space". The same wording is fixed in this SUMMARY's key-decisions and "Decisions Made".
   Code comment: `6b7531b`; SUMMARY lines: this fix-round SUMMARY commit.
2. **`actuals.tokens` re-measured.** 2214 was chars/4 over the diff text only. It is now 19175, chars/4 over the
   full text of the six changed files (76699 chars), the scale the plan estimate uses. `commits: 6` and
   `plan_head_after: d8be60c` still describe the plan's task commits; the fix-round commits are listed here.
   Commit: this fix-round SUMMARY commit.
3. **Spike 005 P3 paragraph rewrapped and reworded.** README.md:175-181 no longer has the ragged short line, and
   "a blind spot of the observed shape" is now "where objdiff missed a wrong symbol". The claim is the same.
   Commit: `a3adc21`.

Re-run after the fixes: `uv run pytest -q tests/test_hygiene.py` 65 passed, 3 skipped (container-only, pre-existing);
`uv run ruff check .` all checks passed.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
