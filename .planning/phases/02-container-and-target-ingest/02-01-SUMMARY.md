---
phase: 02-container-and-target-ingest
plan: 01
subsystem: infra
tags: [docker, uv, wibo, objdiff, le-parser, hash-manifest, pytest, ci]
retroactive: true

requires:
  - phase: 01-hygiene-and-safety
    provides: "gitignore rules, bring-your-own-files policy"
provides:
  - "Docker image + compose build/test services with read-only orig/ and third_party/watcom/ mounts"
  - "config/targets.toml hash manifest (installed build targets + CD v1.00 reference builds)"
  - "reverseapoc CLI: ingest, check-orig, parse-le"
  - "tools/reverseapoc/le.py LE reader (KKND-derived, bound DOS/4GW aware)"
  - "pytest suite (75 tests) and CI"
affects: [byte-identical-round-trip, compiler-identification]

tech-stack:
  added: [Python 3.14, uv 0.12.23, ninja, binutils, objdiff-cli v3.8.2, wibo 1.2.0, Open Watcom v2 tools, pytest, ruff]
  patterns: ["Real-file tests skip unless orig/ exists", "Synthetic LE fixtures, never game bytes", "Fail loudly on unsupported LE features"]

key-files:
  created: [docker/Dockerfile, docker/compose.yaml, docker/README.md, compose.yaml, .github/workflows/ci.yml, pyproject.toml, uv.lock, config/targets.toml, configure.py, tools/reverseapoc/cli.py, tools/reverseapoc/ingest.py, tools/reverseapoc/le.py, tools/reverseapoc/targets.py, tests/conftest.py, tests/test_le.py, tests/test_le_real.py, tests/test_targets.py, tests/test_ingest.py, tests/test_cli.py, tests/test_configure.py]
  modified: []

key-decisions:
  - "LE reader lifted from KKND-Decomp (CC0) with the bound-stub offset; data pages are relative to the owning MZ stub"
  - "Primary target is the installed build; CD v1.00 builds recorded under [[cd_builds]] for cross-reference"

requirements-completed: [ING-01, ING-02, ING-03, ING-04, ING-05]

coverage:
  - id: D1
    description: "Container builds and runs the test suite with read-only orig/ and third_party/watcom/ mounts"
    requirement: ING-01
    verification:
      - kind: integration
        ref: "docker compose run --rm test -> '75 passed', exit 0, run 2026-10-19"
        status: pass
    human_judgment: false
  - id: D2
    description: "check-orig verifies the user's executables against config/targets.toml"
    requirement: ING-02
    verification:
      - kind: integration
        ref: "uv run reverseapoc check-orig -> '3 ok, 0 mismatched, 0 missing', exit 0"
        status: pass
      - kind: unit
        ref: "tests/test_targets.py, tests/test_ingest.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "parse-le reproduces the scanned layout of both EXEs"
    requirement: ING-03
    verification:
      - kind: integration
        ref: "uv run reverseapoc parse-le orig/UFO2P.EXE and orig/TACP.EXE -> stub 0x000352a4, LE header 0x00037f34, objects 0x10000 + 0xd0000 (UFO2P) / 0xe0000 (TACP)"
        status: pass
      - kind: unit
        ref: "tests/test_le_real.py (real files), tests/test_le.py (synthetic)"
        status: pass
    human_judgment: false
  - id: D4
    description: "pytest and ruff green on the host"
    requirement: ING-04
    verification:
      - kind: unit
        ref: "uv run pytest -q -> '75 passed'; uv run ruff check . -> 'All checks passed!'"
        status: pass
    human_judgment: false
  - id: D5
    description: "CI runs tests and ruff on push without game files"
    requirement: ING-05
    verification:
      - kind: other
        ref: "gh run list -> CI success on main for 29f9327 through e50784f"
        status: pass
    human_judgment: false

duration: n/a (retroactive)
completed: 2026-10-19
status: complete
---

# Phase 2: Container and target ingest Summary

**Docker image, hash manifest, `reverseapoc ingest | check-orig | parse-le` and a KKND-derived LE parser proven on both real EXEs: 75 tests green on the host, in the container and in CI.**

## Retroactive note

Built before GSD had project state: commit `29f9327` (container, hash manifest, LE parser and
CI, 22 files) and `8418027` (CD v1.00 builds
added to the manifest). This SUMMARY was written on 2026-10-19 when GSD was bootstrapped, from
fresh command output on that day.

## Evidence (2026-10-19)

- `uv run pytest -q`: `75 passed in 0.77s`; `uv run ruff check .`: `All checks passed!`
- `docker compose run --rm test`: `75 passed in 0.98s`, exit 0
- `uv run reverseapoc check-orig`: UFO2P.EXE, TACP.EXE, SMKP.EXE OK; `3 ok, 0 mismatched, 0 missing`
- `parse-le orig/UFO2P.EXE`: stub 0x000352a4, LE header 0x00037f34, 303 pages, objects 0x00010000 (vsize 0xbfadd) and 0x000d0000 (vsize 0x181e20), 28197 fixups (sel16 10, ptr16:32 4, off32 28183)
- `parse-le orig/TACP.EXE`: stub 0x000352a4, LE header 0x00037f34, 666 pages, objects 0x00010000 (vsize 0xc254f) and 0x000e0000 (vsize 0x25f0b0), 24438 fixups (sel16 10, ptr16:32 4, off32 24424)
- `gh run list`: CI `success` on main for every push from `29f9327` to `e50784f`

## Findings carried into Phase 3

- Both EXEs contain only physical pages (303/303, 666/666) and only internal fixups; there are no rel32 fixups at all.
- 14 (UFO2P) / 11 (TACP) off32 fixups straddle a page boundary; the parser lists each once.
- 27 bytes follow the last LE page in both files (start `64 00 9B FF`); `docs/toolchain.md`'s "page data runs exactly to EOF" is wrong and is corrected in Phase 3.

## Next Phase Readiness

Phase 3 (byte-identical round trip) reuses `le.py` and `config/targets.toml` directly.
