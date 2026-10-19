---
phase: 01-hygiene-and-safety
plan: 02
subsystem: infra
tags: [hygiene, dockerignore, gap-closure]
gap_closure: true
requires:
  - phase: 01-hygiene-and-safety
    provides: "01-01 hygiene rules"
provides:
  - ".dockerignore excludes executables and disc images at any depth"
  - "tests/test_hygiene.py pins the ignore and mount rules"
key-files:
  created: [tests/test_hygiene.py]
  modified: [.dockerignore, .gitignore, docs/coding-style.md, docs/learnings.md, docs/toolchain.md, docs/tools.md]
key-decisions:
  - "Use **/ patterns in .dockerignore; a bare *.exe only matches the context root"
requirements-completed: [HYG-01, HYG-04]
coverage:
  - id: D1
    description: ".dockerignore excludes **/*.exe, *.EXE, *.iso, *.ISO, *.bin, *.BIN"
    requirement: HYG-01
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py::test_dockerignore_excludes_executables_and_disc_images_at_any_depth"
        status: pass
    human_judgment: false
  - id: D2
    description: "No bare TBD marker in live docs (stale ones replaced by known values, unknowns name their requirement/phase)"
    requirement: HYG-04
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py::test_live_docs_carry_no_bare_tbd_markers (fails on the docs before d2bf040, passes after)"
        status: pass
    human_judgment: false
completed: 2026-10-19
status: complete
---

# Phase 1 Plan 02: Hygiene gap closure Summary

**`.dockerignore` now excludes executables and disc images at any depth, pinned by tests; no bare TBD marker left in the live docs (commits fa9c1a0, d2bf040).**

- TDD: `tests/test_hygiene.py` failed 6 dockerignore cases before the fix and passes after (commit `fa9c1a0`).
- `.gitignore` also ignores the `/watcom/` mountpoint Docker creates and `*.img`/`*.cue`/`*.mdf`.
- Host `uv run pytest -q`: 87 passed, 3 skipped (container-only); container: 90 passed.
- Re-verification round 1 found five more TBDs (toolchain.md, tools.md) and four stale ones; all replaced in `d2bf040` and pinned by `test_live_docs_carry_no_bare_tbd_markers`, which fails on the pre-fix docs.
- Host `uv run pytest -q` after `d2bf040`: 88 passed, 3 skipped.
