# Roadmap: ReverseApoc

> **Done rule:** a phase is complete only when its `VERIFICATION.md` passes. The checkboxes and the
> progress table below are annotations, not proof.
>
> **Source:** the phase structure, goals, gates and spikes are fixed by the owner in
> `docs/workflow.md` ("Milestone 1 roadmap"). This file restates them with requirement IDs and
> command-checkable success criteria; it does not change them.

## Milestones

- 🚧 **v1.0 Milestone 1** - Phases 1-6 (in progress)

## Overview

Milestone 1 builds the deterministic oracle before any decompiling, then puts agents on top of it.
Phases 1-2 (built before GSD existed) make the repo safe and give every contributor a container, a
verified copy of their own executables and an LE parser. Phase 3 proves the in-place page splice
rebuilds UFO2P.EXE and TACP.EXE byte for byte with a gate that can fail. Phase 4 pins the exact
Watcom compiler and flags. Phase 5 connects split, compile, objdiff, relocation check and splice into
one pipeline and lands the first hand match per EXE. Phase 6 publishes progress from gate-written
data and runs an unattended agent pilot under guardrails, where the build, never the agent, decides
every match.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Hygiene and safety** - No game bytes or secrets tracked, plugins and GSD at project scope, lean CLAUDE.md, docs skeleton (built before GSD was set up; retroactive verification) (completed 2026-10-20)
- [x] **Phase 2: Container and target ingest** - Docker image, hash manifest, ingest/check-orig, LE parser with pytest (built before GSD was set up; retroactive verification) (completed 2026-10-20)
- [ ] **Phase 3: Byte-identical round trip** - KKND-style in-place page splice rebuilds both EXEs SHA-1 identical, with a gate proven able to fail
- [ ] **Phase 4: Compiler identification** - Exact Watcom version and default flags proven by codegen probe and CLIB3R/MATH3R library match
- [ ] **Phase 5: Split and first matches** - Ghidra split, omf2elf, configure.py + ninja + objdiff, relocation check; one verified match per EXE
- [ ] **Phase 6: Reporting and agent pilot** - Self-hosted progress, guardrail hooks, per-function driver; 10 easy functions matched unattended with zero regressions

## Phase Details

### Phase 1: Hygiene and safety

**Goal**: The repository is safe to publish and to run agents in: no game file, disassembly, build output or secret is tracked, every enabled plugin and GSD are installed at project scope for Claude Code only, CLAUDE.md is lean and states the hard rules, and the docs skeleton exists.
**Depends on**: Nothing (first phase)
**Requirements**: HYG-01, HYG-02, HYG-03, HYG-04
**Success Criteria** (what must be TRUE):
  1. `git ls-files` lists no game file, disassembly, build output, compiler binary, `.env` or API key, and `git check-ignore` confirms `orig/`, `third_party/`, `asm/`, `build/` and `.env` are excluded by `.gitignore`, with `.dockerignore` excluding the same paths and executable/image types (HYG-01)
  2. `claude plugin list` shows every plugin enabled in `.claude/settings.json` installed at project scope, and `/gsd-health` is clean for a project-local GSD install that targets Claude Code only (HYG-02)
  3. `wc -l CLAUDE.md` reports fewer than 150 lines, the file states the hard rules, the commands and the done gate, and per-path rules live in `.claude/rules/` (HYG-03)
  4. `docs/toolchain.md`, `coding-style.md`, `matching.md`, `learnings.md`, `tools.md`, `legal.md`, `workflow.md` and `ceremonies.md` exist, together with `README.md`, `.recomp.json` and the approved design spec under `docs/superpowers/specs/` (HYG-04)

**Spike**: none
**Plans**: TBD
**Note**: Built before GSD was set up (commits `d7d4d65`…`e50784f`). Verified retroactively; marked complete separately once its `VERIFICATION.md` passes.

### Phase 2: Container and target ingest

**Goal**: A contributor with their own game files can build the container, ingest and verify both executables against the hash manifest, and reproduce their scanned LE layout, with tests and ruff green on the host, in the container and in CI.
**Depends on**: Phase 1
**Requirements**: ING-01, ING-02, ING-03, ING-04, ING-05
**Success Criteria** (what must be TRUE):
  1. `docker compose build` succeeds and the image provides Python 3.14 + uv, ninja, objdiff-cli, wibo 1.2.0 and the Open Watcom v2 tools, with `orig/` and `third_party/watcom/` mounted read-only at run time and absent from every image layer (ING-01)
  2. `uv run reverseapoc ingest` copies the EXEs into `orig/`, `uv run reverseapoc check-orig` exits 0 against `config/targets.toml` (size, CRC32, md5, sha1), and a test shows it exits non-zero for a wrong or altered file (ING-02)
  3. `uv run reverseapoc parse-le orig/UFO2P.EXE` and `uv run reverseapoc parse-le orig/TACP.EXE` report the MZ stub at 0x352A4, the LE header at 0x37F34, two objects at their scanned bases, and internal fixups only (ING-03)
  4. `uv run pytest -q` and `uv run ruff check .` pass on the host and `docker compose run --rm test` passes in the container; real-file tests are skipped unless `orig/` exists (ING-04)
  5. The CI workflow (`.github/workflows/ci.yml`) runs tests and ruff on push and passes with no game file present (ING-05)

**Spike**: none
**Plans**: TBD
**Note**: Built before GSD was set up (commits `29f9327` and `8418027`). Verified retroactively; marked complete separately once its `VERIFICATION.md` passes.

### Phase 3: Byte-identical round trip

**Goal**: UFO2P.EXE and TACP.EXE (plus SMKP.EXE, as a second layout without a trailer) are rebuilt from decomposed parts through a KKND-style in-place page splice and proven SHA-1 identical to the originals, by a gate that demonstrably fails on any one-byte change.
**Depends on**: Phase 2
**Requirements**: RT-01, RT-02, RT-03, RT-04, RT-05
**Success Criteria** (what must be TRUE):
  1. After `uv run reverseapoc rebuild` writes `build/UFO2P.EXE`, `build/TACP.EXE` and `build/SMKP.EXE`, `cmp` of each against `orig/` is silent and each whole-file SHA-1 equals its `sha1` in `config/targets.toml`; the output is reassembled from untouched prefix regions plus per-object images re-paged through the LE page map, not copied from the original (RT-01, RT-03)
  2. A pytest proves the round trip for both EXEs, is skipped unless `orig/` exists, and passes on the host and in `docker compose run --rm test` (RT-03)
  3. Negative tests show the gate can fail: a one-byte mutation mid-page, at a page edge, in the short last page and across a page boundary each changes the SHA-1, and the failure names the file offset; the splice API refuses writes outside page data and any change of file length, and writes page-straddling fields correctly in flat address space (RT-02, RT-04)
  4. A byte-region map tiles every byte of each file (extender, MZ stub, LE header/loader section, fixup section, padding, pages, 27-byte trailer), and a coverage test fails if any byte is unassigned or assigned twice (RT-05)
  5. `docs/toolchain.md` records the LE edge cases confirmed on the real files (page types, the 14 UFO2P / 11 TACP page-straddling fixups, the 27-byte trailer) as offsets, lengths and hashes only, replacing the "page data runs exactly to EOF" and "To be confirmed in Phase 2/3" lines (RT-05)

**Spike**: Iterated pages / fixup edge cases on the real files, plus the 27 trailing bytes after the last LE page (starting `64 00 9B FF`) that a byte-identical rebuild must preserve.
**Plans:** 4/5 plans executed

Plans:
**Wave 1**
- [x] 03-01-PLAN.md — Wave 1: `reverseapoc rebuild` tracer, byte-region map with D-19 refusals, "rebuilt, not copied" mutant proofs (RT-01, RT-03, RT-05)
- [x] 03-02-PLAN.md — Wave 1: ninja `verify` edge and the D-15 manifest-hash guard (RT-03)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-03-PLAN.md — Wave 2: linear-address splice API, refusals, overlap, fixup masking, D-13 negative suite (RT-02, RT-04)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-04-PLAN.md — Wave 3: `rebuild --json`/`--exe`, CLI mismatch path, parse-le trailer (RT-03, RT-05)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 03-05-PLAN.md — Wave 4: real-file round trip and control, post-spike facts, docs/toolchain.md correction, phase gate (RT-01..RT-05)

### Phase 4: Compiler identification

**Goal**: The exact Watcom version and default flags that built each EXE are known and proven: runtime library modules match byte for byte, and the codegen probe locates its idioms in the game's own code.
**Depends on**: Phase 3
**Requirements**: CID-01, CID-02, CID-03, CID-04, CID-05, CID-06
**Prerequisite**: Met 2026-10-19: Watcom 10.5, 10.6 and 11.0 media are in the gitignored `third_party/watcom-media/` (hash-verified); extracted trees go to `third_party/watcom/<ver>/`, mounted read-only and never baked into the image.
**Success Criteria** (what must be TRUE):
  1. For each owner-supplied version (10.5, 10.6, 11.0), the original compiler runs under wibo 1.2.0 (11.0: native `BINNT\wcc386.exe`; 10.5/10.6: `BINNT\wcc386.exe` is a loader for the LE `BINW\WCC386.EXE`, so both directories are installed) inside `docker compose run`, mounted read-only from `third_party/watcom/`, and compiles a test source to an object file; each compiler binary's hash and banner are logged (CID-01)
  2. A compiler wrapper keyed by `compiler@version` reads `config/cflags.txt`, and a test shows two source files compiled with the version and flags the table assigns to each (CID-02)
  3. Linked CLIB3R/MATH3R runtime modules from one version's `LIB386` match the code objects byte for byte with fixups masked, and the mosura codegen probe compiled with each version locates its idioms in non-library code of both EXEs' code objects (CID-03, CID-04)
  4. `docs/toolchain.md` records the compiler version and default flags per EXE with per-flag evidence, replacing its "To be confirmed in Phase 4" line (CID-05)
  5. A C vs C++ scan (vtables, `__wcpp_` routines, XI/YI segments) reports its result per EXE and confirms `wcc386`, or names the modules that need `wpp386` (CID-06)

**Spike**: wibo 1.2.0 runs `wcc386.exe` for each version (10.5, 10.6, 11.0) in Docker.
**Plans**: TBD

### Phase 5: Split and first matches

**Goal**: The matching pipeline works end to end: functions are found and grouped into units, C compiles with the identified compiler, objdiff and an independent relocation check compare it to the target cut from the LE, and one hand-matched function per EXE splices back with both EXEs still SHA-1 identical.
**Depends on**: Phase 3, Phase 4
**Requirements**: SPL-01, SPL-02, SPL-03, SPL-04, SPL-05, SPL-06, SPL-07, SPL-08, SPL-09, SPL-10, SPL-11, SPL-12, SPL-13
**Success Criteria** (what must be TRUE):
  1. `config/<exe>/functions.csv` exists for both EXEs, exported by Ghidra 12.1.4 with one LE loader in WSL2 and cross-checked by an independent capstone discovery pass with every boundary disagreement reconciled, and functions are grouped into translation units under `config/<exe>/` (SPL-01, SPL-02, SPL-03)
  2. `configure.py` writes `build.ninja`, `objdiff.json` and `compile_commands.json`; `ninja` compiles units with the Phase 4 compiler under wibo, every unmatched function keeps its original bytes through the stub convention, per-function asm is generated into gitignored `asm/` by script, and the C89 lint gate (`clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with the Watcom compat header) passes on `src/` (SPL-04, SPL-05, SPL-06, SPL-12)
  3. `omf2elf.py` converts Watcom OMF (COMDAT, LIDATA, FIXUPP threads, BAKPAT, CEXTDEF) to ELF32 with its pytest suite green, and target ELF objects cut from the LE carry relocations rebuilt from the LE fixups (SPL-07, SPL-08)
  4. For one function per EXE, the single-unit `check` tool prints objdiff 100%, a passing relocation check (every non-relocated byte, equal length, every `call rel32` target, every absolute fixup target) and, after splicing with the original link-time value kept at each fixup site, both rebuilt EXEs SHA-1 identical to `config/targets.toml`; a negative test with a wrong call or fixup target makes the relocation check fail even where objdiff reports 100% (SPL-09, SPL-10, SPL-11, SPL-13)

**Spike**: objdiff diffs OMF-converted ELF cleanly (decides hybrid vs fallback: if INVALIDATED, the KKND-style compare stays the oracle and Phase 6 uses a minimal own agent layer).
**Plans**: TBD

### Phase 6: Reporting and agent pilot

**Goal**: Progress is published from gate-written data, and an unattended per-function driver matches easy functions under guardrails, with the build, never the agent, deciding each match.
**Depends on**: Phase 5
**Requirements**: RPT-01, RPT-02, RPT-03, RPT-04, RPT-05, AGT-01, AGT-02, AGT-03, AGT-04, AGT-05, AGT-06, AGT-07, AGT-08, AGT-09, AGT-10, AGT-11
**Success Criteria** (what must be TRUE):
  1. On push to `main`, the GitHub Pages workflow publishes the treemap mosaic (`progress.svg`), the shields badge and raw `progress.json`, all written by stdlib `progress.py` from a committed per-function status table that only the local gate writes, and a `<VERSION>_report` artifact with an objdiff-shaped `report.json` is uploaded for recomp.fyi (RPT-01, RPT-02, RPT-03, RPT-04)
  2. `.recomp.json` is updated and the recomp.fyi listing and decomphub.com submission are done once the repo is public (RPT-05)
  3. Guardrail hooks, tested with pytest, block edits to `orig/`, hash manifests and build/verify scripts during matching sessions, inline asm and code-emitting `#pragma aux` in `src/`, and builds that bypass the verify script (AGT-05)
  4. The driver runs one fresh `claude -p "/goal ..."` session per function chosen by the easiest-first scorer, supplies the context pack and the `watcom-decomp` skill, re-verifies compile/compare/splice/SHA-1 itself, caps attempts at 3-5 with re-queue of capped functions, logs a MATCHED / PARTIAL / GAVE_UP outcome with turns, tokens, time and verifier output, and backs off on usage limits and auth/credit errors with a per-night cap (AGT-01, AGT-02, AGT-03, AGT-04, AGT-07, AGT-08, AGT-09)
  5. An unattended pilot run matches 10 easy functions, one function per commit, with zero regressions: every previously matched function still matches and both EXEs stay SHA-1 identical after every commit; agent work runs through decomp.wtf v0.10.6 fork mode pinned in WSL2 as a subprocess if the spike passes, otherwise through a minimal own agent layer (AGT-06, AGT-10, AGT-11)

**Spike**: decomp.wtf fork mode accepts the repo's stub convention.
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Hygiene and safety | 2/2 | Complete    | 2026-10-20 |
| 2. Container and target ingest | 2/2 | Complete    | 2026-10-20 |
| 3. Byte-identical round trip | 4/5 | In Progress | - |
| 4. Compiler identification | 0/TBD | Not started | - |
| 5. Split and first matches | 0/TBD | Not started | - |
| 6. Reporting and agent pilot | 0/TBD | Not started | - |
