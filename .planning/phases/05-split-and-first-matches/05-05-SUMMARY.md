---
phase: 05-split-and-first-matches
plan: 05
subsystem: compiler-wrapper
tags: [watcom, wcc386, include-asm, stub-convention, c89, omf]

requires:
  - phase: 04-compiler-identification
    provides: "reverseapoc cc wrapper (compile_rule, guest_path, wrapper-owned -i), config/cflags.txt `*` rule wcc386@10.6"
  - phase: 05-split-and-first-matches
    provides: "05-01 spike: objdiff on converted OMF is validated"
provides:
  - "include/common.h: INCLUDE_ASM(name) marker (expands to an unused extern int) and s8/u8/s16/u16/s32/u32 typedefs"
  - "reverseapoc cc passes one -i= of <compile root>/include;<version H>, so src units can #include \"common.h\""
  - "real Watcom 10.6 proof that markers emit no bytes, no EXTDEF and no public"
affects: [05-12 lint of the header, 05-13 unit scaffold, 05-14 configure.py defined-or-marked check, phase 6 decomp.wtf marker spike]

actuals:
  tokens: 3041
  tasks: 2
  commits: 3
plan_head_before: 6463d471f6040396d790fc8b1d9243901a6200e3
plan_head_after: 18db2609e99139503bfdc7271924ef75b567cdaf

tech-stack:
  added: []
  patterns:
    - "Marker emptiness measured against a control compile of the same function, never against literal bytes"
    - "Include dir is joined to the compile root (INCLUDE_DIR), not to the import-time REPO_ROOT"

key-files:
  created:
    - include/common.h
    - tests/test_stub_real.py
  modified:
    - tools/reverseapoc/compiler.py
    - tests/test_compiler.py

key-decisions:
  - "The -i= value is built from root / INCLUDE_DIR (\"include\"), not from PROJECT_INCLUDE.relative_to(REPO_ROOT): tests and callers that pass another root (or monkeypatch REPO_ROOT) must still get that root's include/"
  - "test_markers_emit_nothing compares _TEXT and externs with a control file holding only the defined function, so no compiled byte is a literal in the test"
  - "Marker externs are matched by substring INCLUDE_ASM (Watcom decorates data names), not by prefix"

patterns-established:
  - "Real compile tests for src-shaped files go through compile_source under config/cflags.txt, writing under build/test-stub/<test>/"

requirements-completed: [SPL-04]

coverage:
  - id: D1
    description: "include/common.h defines INCLUDE_ASM(name) as `extern int INCLUDE_ASM_##name` plus C89 fixed-width typedefs, guard COMMON_H"
    requirement: SPL-04
    verification:
      - kind: other
        ref: "grep -n '#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name' include/common.h"
        status: pass
    human_judgment: false
  - id: D2
    description: "reverseapoc cc passes exactly one -i= of <root>/include;<version H>, backslash entries, ';' separator, native and under wibo; cflags still cannot add -i"
    requirement: SPL-04
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_include_list_puts_the_repo_include_first"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_include_list_on_wibo_and_native"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_cflags_cannot_add_an_include"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_include_is_own_tree_only"
        status: pass
    human_judgment: false
  - id: D3
    description: "Under real Watcom 10.6 (`*` rule) INCLUDE_ASM markers emit no bytes, no EXTDEF and no public: unit file, markers-only file, marker adjacent to a definition"
    requirement: SPL-04
    verification:
      - kind: integration
        ref: "tests/test_stub_real.py#test_markers_emit_nothing"
        status: pass
      - kind: integration
        ref: "tests/test_stub_real.py#test_markers_only_file"
        status: pass
      - kind: integration
        ref: "tests/test_stub_real.py#test_marker_next_to_a_defined_function"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 05: INCLUDE_ASM stub convention and project include path Summary

**include/common.h with a KKND-style `INCLUDE_ASM(name)` marker that Watcom 10.6 compiles to nothing (no bytes, no EXTDEF, no public), and `reverseapoc cc` now passes `-i=include;<version H>` so src units can include project headers.**

Execution context nonce: c896afd8ee27029e

## Performance

- **Duration:** about 7 min
- **Started:** 2026-10-24T00:10:15Z
- **Completed:** 2026-10-24T00:16:50Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `include/common.h` (C89, guard `COMMON_H`): `#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name`, with a comment on why it reserves nothing and how the in-place splice keeps the original bytes (D-12). Typedefs `s8 u8 s16 u16 s32 u32` (`long` for 32-bit).
- `tools/reverseapoc/compiler.py`: `INCLUDE_DIR = "include"`, `PROJECT_INCLUDE = REPO_ROOT / INCLUDE_DIR`, and `_include_list(root, watcom_dir, version)`. compile_rule's single `-i=` value is now `<root>\include;<version>\H`. `-i` stays wrapper-owned (config/cflags.txt still refuses it in every spelling).
- Real Watcom 10.6 compiles: a unit with three markers and one function yields publics `("func_00012345_",)`, no externs, and a `_TEXT` identical to a control file holding only that function (3 bytes). A markers-only file has no publics, no externs and an empty `_TEXT`. A marker right before a definition leaves exactly `func_00012010_`.

## Task Commits

1. **Task 1: Tracer, unit-shaped file includes common.h and markers emit nothing**
   - RED `e2b93c8` (test): new argv test plus the three include-list expectations; real test failed on `E1055: Unable to open 'common.h'`
   - GREEN `3eb40fd` (feat): include/common.h and the include list
2. **Task 2: Edges of the stub convention and the include list** - `18db260` (test): four pinning tests; no code change was needed

**Plan metadata:** see the docs(05-05) commit that adds this file.

## TDD record

- **Task 1 RED:** `uv run pytest -q tests/test_compiler.py -k include_list_puts --junitxml=build/red/t1a.xml` exited 1. Target `test_include_list_puts_the_repo_include_first` failed on `assert ['-i=w\\10.6\\H'] == ['-i=include;w\\10.6\\H']`. Classifier (`gsd-tools check tdd-red-evidence`, format junit): `RED_EVIDENCE_OK`, reason `target_test_failed`. Semantic assessment: the planned assertion on the include list failed; no collection, import or fixture fault.
- **Task 1 RED (real):** `REVERSEAPOC_WATCOM_DIR=<main>/third_party/watcom uv run pytest -q -rs tests/test_stub_real.py --junitxml=build/red/t1b.xml` exited 1. Target `test_markers_emit_nothing` failed on `assert result.ok` with the compiler's `E1055: Unable to open 'common.h'`. Classifier: `RED_EVIDENCE_OK`. Semantic assessment: this is the failure the plan predicted (the header is not on the include list); the compiler ran, so it was not a skip or a runner fault.
- **Task 1 GREEN:** both tests pass; the tracer verify (`test_stub_real.py`, rc 0, no SKIPPED line) was re-run before Task 2 (tracer gate, end-of-phase mode, automated verify only).
- **Task 2:** the plan allowed for these to pass after Task 1. All four did, so they pin behaviour. Each was shown able to fail with a temporary mutation that was reverted before committing (`git checkout -- <file>`):
  - `INCLUDE_ASM` as a definition (`int INCLUDE_ASM_##name`): all three real stub tests failed.
  - forward slashes in `_include_list`: both `test_include_list_on_wibo_and_native` cases failed.
  - `-i` removed from `cflags.WRAPPER_OWNED`: `test_cflags_cannot_add_an_include` failed.
- No `feat(05-05)` commit for Task 2: no defect turned up, so no GREEN step was needed (the plan says to adjust compiler.py only if a test shows a defect).

## Files Created/Modified

- `include/common.h`: the INCLUDE_ASM marker and the fixed-width typedefs
- `tools/reverseapoc/compiler.py`: INCLUDE_DIR, PROJECT_INCLUDE, `_include_list`; module docstring updated (D-12/D-14)
- `tests/test_compiler.py`: `test_include_list_puts_the_repo_include_first`, `test_include_list_on_wibo_and_native` (win32 and linux), `test_cflags_cannot_add_an_include`; the include-list expectations in `test_argv_shape`, `test_include_is_own_tree_only` and `test_include_path_from_a_tree_outside_the_root` now start with `include;`
- `tests/test_stub_real.py`: `test_markers_emit_nothing`, `test_markers_only_file`, `test_marker_next_to_a_defined_function`

## Decisions Made

- The include entry is `root / INCLUDE_DIR`, not `PROJECT_INCLUDE.relative_to(REPO_ROOT)` (see deviation 1).
- Marker emptiness is measured against a control compile, so no compiled byte appears as a literal in the tests.
- Marker externs are matched by substring (`INCLUDE_ASM` anywhere in the name) because Watcom decorates data names.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Include entry derived from the compile root, not from REPO_ROOT**
- **Found during:** Task 1 (GREEN, full suite)
- **Issue:** The first GREEN draft used `root / PROJECT_INCLUDE.relative_to(REPO_ROOT)`. Four `tests/test_cli.py` cc tests monkeypatch `compiler.REPO_ROOT` to a tmp dir, and `relative_to` raised ValueError there. The same failure would hit any caller whose REPO_ROOT differs from the import-time one.
- **Fix:** Added `INCLUDE_DIR = "include"` and built the entry as `root / INCLUDE_DIR`. `PROJECT_INCLUDE = REPO_ROOT / INCLUDE_DIR` stays as the documented constant.
- **Files modified:** tools/reverseapoc/compiler.py
- **Verification:** full suite 881 passed, 166 skipped before Task 2; the real stub test still passes
- **Committed in:** 3eb40fd (the Task 1 GREEN commit; the broken draft was never committed)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Same behaviour the plan specified ("resolved against the compile root"); only the constant's shape changed. No scope creep.

## Issues Encountered

- The worktree's Bash isolation guard refused a few compound commands (`! grep`, `$status`). They were split into plain commands; the checks are the same ones the plan specifies.
- `uv run ruff format --check` reports 20 files that would be reformatted, all pre-existing and outside this plan. The gate is `ruff check`, which is green. Not touched.

## Verification

- `uv run pytest -q tests/test_compiler.py`: 55 passed
- `REVERSEAPOC_WATCOM_DIR=<main checkout>/third_party/watcom uv run pytest -q -rs tests/test_stub_real.py`: 3 passed, no SKIPPED line (Windows host, real Watcom 10.6)
- Task 2 verify (`test_compiler.py test_stub_real.py test_cflags.py` with the owner's tree): 117 passed, rc 0, no SKIPPED for test_stub_real
- `uv run pytest -q tests/test_stub_real.py -k "markers_only or next_to"` with the owner's tree: 2 passed
- `uv run pytest -q`: 884 passed, 168 skipped (without REVERSEAPOC_WATCOM_DIR the real stub tests skip, as designed). `uv run ruff check .`: all checks passed.
- `git status --porcelain`: nothing under build/
- Not run here: `docker compose run --rm test`. Running compose from a worktree would create empty root-owned `orig/` and `third_party/` mounts inside it, and the real stub tests would skip there anyway (no tree in the worktree). It belongs in the post-merge run from the main checkout.

## User Setup Required

None. No external service configuration required.

## Next Phase Readiness

- 05-13 (unit scaffold) can write `#include "common.h"` and `INCLUDE_ASM(func_XXXXXXXX);` in src/<exe>/<unit>.c.
- 05-14 (configure.py defined-or-marked check) can rely on markers leaving no symbol in the object, so a marker can never be counted as a definition.
- 05-12 still has to lint the header under clang (`long` assumed 32-bit for `--target=i386-unknown-none`).

## Self-Check: PASSED

- FOUND: include/common.h, tests/test_stub_real.py, tools/reverseapoc/compiler.py, tests/test_compiler.py
- FOUND commits on HEAD: e2b93c8, 3eb40fd, 18db260

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
