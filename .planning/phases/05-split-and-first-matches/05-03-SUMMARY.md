---
phase: 05-split-and-first-matches
plan: 03
subsystem: tooling
tags: [capstone, x86, decoding, pytest, conftest, ghidra, le, uv]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-01 spike 005 (objdiff on converted OMF validated); the phase research package audit of capstone"
provides:
  - "capstone==5.0.9 as the first runtime dependency (pyproject.toml, uv.lock with hashes for 11 py3-none wheels)"
  - "docs/tools.md capstone Use row with reason and pin, plus a hygiene check that every runtime pin has such a row"
  - "tools/reverseapoc/x86.py: CAPSTONE_VERSION, X86Error, check_capstone, Insn, decode, decode_one, is_filler"
  - "tests/conftest.py: requires_capstone/objdiff/clang/ghidra, GHIDRA_DIR, ghidra_dir(), build_le_image(ghidra_loadable=True)"
affects: [05-07, 05-08, 05-09, 05-10, 05-11, 05-12, discovery, asm-listings, scorer, target-objects, ghidra-smoke-test]

actuals:
  tokens: 7400
  tasks: 3
  commits: 5
plan_head_before: 6463d471f6040396d790fc8b1d9243901a6200e3
plan_head_after: 8a523e77153bb3535008e26ca3dc2fa9b1bb9e8d

tech-stack:
  added: ["capstone 5.0.9 (py3-none wheels, C library via ctypes)"]
  patterns:
    - "Every x86 decoding module goes through reverseapoc.x86.decode/decode_one; branch facts come from capstone operand detail, never hand-decoded opcodes"
    - "Runtime dependencies are exact pins, each with a docs/tools.md **Use** row holding the pin as a code span (hygiene-tested)"
    - "Tool-dependent tests call a requires_<tool>() skip helper that names the missing tool"

key-files:
  created:
    - tools/reverseapoc/x86.py
    - tests/test_x86.py
  modified:
    - docs/tools.md
    - tests/test_hygiene.py
    - tests/conftest.py
    - tests/test_le.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "capstone 5.0.9 approved by the owner at the blocking-human legitimacy checkpoint (Task 2) on 2026-10-23, before install"
  - "build_le_image(ghidra_loadable=True) also rebases the LE data-pages field to the first MZ, so le.py and Ghidra read the same page bytes as the default image"
  - "GHIDRA_DIR is the default install path (/opt/ghidra); ghidra_dir() reads GHIDRA_INSTALL_DIR at call time"
  - "Insn carries raw bytes so is_filler matches the four Watcom filler encodings exactly"
  - "rel32_field is set for every rel32 call or jump (not only call), since a jmp/jcc rel32 to another function is also a PC32 site"

patterns-established:
  - "Dependency policy check: _dependency_doc_problems(pyproject_text, tools_text) in tests/test_hygiene.py"
  - "Ghidra-loadable synthetic LE: e_lfarlc 0x40 and e_lfanew -> LE in the first MZ"

requirements-completed: [SPL-02, SPL-01]

coverage:
  - id: D1
    description: "docs/tools.md capstone 5.0.9 Use row exists before the install commit, and a hygiene test fails on any runtime pin without a Use row"
    requirement: SPL-02
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_every_runtime_dependency_is_documented"
        status: pass
      - kind: unit
        ref: "tests/test_hygiene.py#test_dependency_doc_check_catches_an_undocumented_pin"
        status: pass
      - kind: unit
        ref: "tests/test_hygiene.py#test_dependency_doc_check_wants_an_exact_pin"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner approved capstone 5.0.9 at the blocking-human checkpoint before `uv add` ran"
    requirement: SPL-02
    verification: []
    human_judgment: true
    rationale: "A package-legitimacy approval is a human decision; recorded from the orchestrator session of 2026-10-23, not provable by a test"
  - id: D3
    description: "capstone==5.0.9 pinned in pyproject.toml and uv.lock; importlib.metadata reports 5.0.9 on Python 3.14"
    requirement: SPL-02
    verification:
      - kind: unit
        ref: "tests/test_x86.py#test_capstone_pin"
        status: pass
      - kind: other
        ref: "uv sync --locked && uv run python -c \"import importlib.metadata as m; print(m.version('capstone'))\" -> 5.0.9"
        status: pass
    human_judgment: false
  - id: D4
    description: "x86.py decodes call/jmp/jcc targets and rel32 field VAs, terminal and filler instructions, and stops at data sites and undecodable bytes"
    requirement: SPL-02
    verification:
      - kind: unit
        ref: "tests/test_x86.py (17 tests, made-up bytes)"
        status: pass
    human_judgment: false
  - id: D5
    description: "requires_capstone/objdiff/clang/ghidra skip helpers and the Ghidra-loadable synthetic LE that le.py still parses identically"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_requires_helpers_skip_cleanly"
        status: pass
      - kind: unit
        ref: "tests/test_hygiene.py#test_requires_ghidra_returns_the_install_dir"
        status: pass
      - kind: unit
        ref: "tests/test_le.py#test_ghidra_loadable_image"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-23
status: complete
---

# Phase 5 Plan 03: capstone 5.0.9 and shared x86 decode helpers Summary

**capstone 5.0.9 is now the first runtime dependency, added in the order D-09 requires: the docs/tools.md reason first, then the owner's approval, then `uv add`. It comes with a hygiene check that ties each runtime pin to a docs/tools.md Use row. `reverseapoc.x86` gives every later decoder the same capstone-backed call/jump targets, rel32 field addresses, terminal/filler recognition and inline-data stop. The Wave 0 skip helpers and a synthetic LE that Ghidra can load are also in place.**

Execution context nonce: 54502af6a74b8b7f

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-24T00:09:35Z
- **Completed:** 2026-10-24T00:17:28Z
- **Tasks:** 3 (Task 2 was the owner checkpoint, already approved)
- **Files modified:** 8

## Accomplishments
- docs/tools.md has a capstone 5.0.9 **Use** row (reason, py3-none/ctypes note for Python 3.14, the importlib.metadata vs `__version__` quirk, pin). It was committed before the install.
- `_dependency_doc_problems` fails on an undocumented pin, a different or longer version, a non-Use row, or a loose (non-`==`) pin. The real repo passes with capstone listed.
- `capstone==5.0.9` is in `[project].dependencies`. uv.lock pins the sdist and 11 py3-none wheels with hashes. `importlib.metadata.version("capstone")` is 5.0.9 on the host (Python 3.14), while the package's own attribute reports 5.0.7. This resolves the STATE.md blocker "capstone cp314 wheels are unverified".
- `tools/reverseapoc/x86.py` provides one lazily built `Cs(CS_ARCH_X86, CS_MODE_32)` with detail on, created after a version check. Targets and rel32 field VAs come from `imm`/`imm_offset`/`imm_size`. Terminal means ret, iret, or any unconditional jmp. Decoding stops at a data site at an instruction start, at an undecodable byte, or at the end of the bytes.
- `tests/conftest.py` gains `requires_capstone()`, `requires_objdiff()`, `requires_clang()`, `requires_ghidra() -> Path` and `build_le_image(ghidra_loadable=True)`.

## Task Commits

1. **Task 1 (tracer): dependency policy and Wave 0 test helpers**: `00aaf43` (test, RED), `6a662fd` (feat, GREEN). The tracer gate re-ran the verify end to end: 7 passed, full suite 887 passed / 165 skipped, ruff clean.
2. **Task 2: Owner approves capstone 5.0.9 before install**: no commit. Approved by the owner on 2026-10-23, before install (details below).
3. **Task 3: capstone 5.0.9 and shared x86 decode helpers**: `b398159` (chore, `uv add`), `ac76ad5` (test, RED), `8a523e7` (feat, GREEN).

**Plan metadata:** this SUMMARY commit (docs).

## Task 2: owner approval (blocking-human checkpoint)

The orchestrator showed the owner the following, and the owner answered "Approve now" (resume signal: "approved") on 2026-10-23. That was before any install and after Task 1's plan was known:
- PyPI release capstone 5.0.9 exists with 11 py3-none wheels, including `py3-none-win_amd64` and `py3-none-manylinux_2_17_x86_64`, uploaded 2026-05-28.
- 37 releases, going back to 2.0 on 2014-01-21. This is the long-standing Capstone project, not a look-alike name.
- https://github.com/capstone-engine/capstone/releases/tag/5.0.9 resolves (HTTP 200).
- One discrepancy was shown to the owner: PyPI `project_urls` lists only capstone-engine.org, not the GitHub repository.

Order on disk: the docs row (`6a662fd`) comes before the install (`b398159`). The uv.lock entry matches the facts above: sdist and wheels uploaded 2026-05-28, the same 11 py3-none wheel filenames.

## Files Created/Modified
- `docs/tools.md`: capstone 5.0.9 Use row.
- `tests/test_hygiene.py`: `_dependency_doc_problems` and five tests (two dependency-check tests, the exact-pin test, two skip-helper tests).
- `tests/conftest.py`: skip helpers, `GHIDRA_DIR`/`ghidra_dir()`, named MZ/LE field constants, `ghidra_loadable` option, docstring.
- `tests/test_le.py`: `test_ghidra_loadable_image` (bound and unbound).
- `pyproject.toml`, `uv.lock`: `capstone==5.0.9`.
- `tools/reverseapoc/x86.py` (new): decode helpers, Theme Hospital derivation header on line 1.
- `tests/test_x86.py` (new): 17 tests on made-up bytes.

## TDD notes (RED evidence, semantic assessment)
- Task 1 RED (`00aaf43`): 6 failed, 1 passed. The two doc-check tests failed on their assertions against a stub helper returning `[]`. The skip-helper tests failed with AttributeError and the image tests with TypeError (unexpected kwarg), because that API did not exist yet. `test_every_runtime_dependency_is_documented` passed at HEAD by design, since there were no dependencies yet.
- Task 3 RED (`ac76ad5`): collection ImportError (`reverseapoc.x86` did not exist). This is a load-level failure, not an assertion-level RED. The plan is `type: execute`, so the plan-level TDD gate does not apply, but this is noted for the end-of-phase TDD review.
- Mutation check on the ghidra_loadable fix: undoing the data-pages rebase makes `LE.load_flat()` differ from the default image, so the test pins it.

## Decisions Made
- See key-decisions in the frontmatter. The two that shape later plans: `Insn.raw` exists so filler matching is exact, and `rel32_field` is set for rel32 jumps as well as calls.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ghidra-loadable bound image would have put the pages in the wrong place**
- **Found during:** Task 1
- **Issue:** When the first MZ's e_lfanew points at the LE header, le.py (and the LE format) treat that MZ as the owner, so the data-pages field is read relative to the start of the file. The default bound image writes it relative to the inner stub (0x180 later). Only setting e_lfarlc/e_lfanew would have shifted every page by 0x180, for le.py and for Ghidra.
- **Fix:** with `ghidra_loadable=True` the data-pages field is written relative to the first MZ, so the pages stay put. The test checks objects, entry, `data_pages_offset`, `load_flat()` and `fixups()` against the default image, for both bound and unbound.
- **Files modified:** tests/conftest.py, tests/test_le.py
- **Committed in:** 6a662fd

**2. [Rule 3 - Blocking] GHIDRA_DIR "read at call time" cannot be a module constant**
- **Fix:** `GHIDRA_DIR = Path("/opt/ghidra")` is the default, and `ghidra_dir()` reads GHIDRA_INSTALL_DIR at call time. `requires_ghidra()` uses it and returns the dir.
- **Committed in:** 6a662fd

**3. [Rule 2 - Missing] `Insn.raw` field and a loose-pin check**
- `is_filler` must match exact encodings (`8d 40 00` vs `8d 00` disassemble the same), so `Insn` carries its bytes (`8a523e7`). `_dependency_doc_problems` also rejects a non-`==` pin, and the pin must appear as a code span so `foo==1.0` is not satisfied by `foo==1.0.1` (`6a662fd`).

**4. [Process] Install committed separately from the RED tests**
- `uv add` was committed alone (`b398159`) so the install is its own auditable commit after the approval and the docs row.

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 missing critical) plus 1 process note.
**Impact on plan:** No scope creep. Without fix 1, the D-06 Ghidra smoke test would have imported shifted page bytes.

## Issues Encountered
- A Python edit of conftest.py briefly wrote CRLF line endings (Windows text mode). They were converted back to LF before the commit, and all touched files were checked to be CRLF-free.
- The plan's commit ledger file lives in the shared git dir, outside the worktree, so it was not written. The base 6463d47 was taken from the dispatch prompt and used for the measured commit count.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plans 05-07..05-12 can import `reverseapoc.x86` and the conftest skip helpers.
- The container picks up capstone on its next `uv run` / `uv sync --locked` (plan 05-12 rebuilds and runs the container suite). The container run was not done in this plan.
- STATE.md blocker "capstone cp314 wheels are unverified" can be closed by the orchestrator: 5.0.9 py3-none wheels work on Python 3.14 on the Windows host.

## Self-Check: PASSED
- FOUND: tools/reverseapoc/x86.py, tests/test_x86.py, docs/tools.md row, conftest helpers (4 defs)
- FOUND commits: 00aaf43, 6a662fd, b398159, ac76ad5, 8a523e7 (5 = `git rev-list --count 6463d47..HEAD` before this SUMMARY commit)
- Verify: `uv sync --locked && uv run pytest -q` 905 passed / 165 skipped; `uv run ruff check .` clean; capstone metadata 5.0.9

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-23*
