# Roadmap: ReverseApoc

> **Done rule:** a phase is complete only when its `VERIFICATION.md` passes. The checkboxes and the
> progress table below are annotations, not proof.
>
> **Source:** the phase structure, goals, gates and spikes are fixed by the owner in
> `docs/workflow.md` ("Milestone 1 roadmap"). This file restates them with requirement IDs and
> command-checkable success criteria; it does not change them.

## Milestones

- 🚧 **v1.0 Milestone 1** - Phases 1-8 (in progress)

## Overview

Milestone 1 builds the deterministic oracle before any decompiling, then puts agents on top of it.
Phases 1-2 (built before GSD existed) make the repo safe and give every contributor a container, a
verified copy of their own executables and an LE parser. Phase 3 proves the in-place page splice
rebuilds UFO2P.EXE and TACP.EXE byte for byte with a gate that can fail. Phase 4 pins the exact
Watcom compiler and flags. Phase 5 connects split, compile, objdiff, relocation check and splice into
one pipeline and lands the first hand match per EXE. Phase 6 publishes progress from gate-written
data and runs an unattended agent pilot under guardrails, where the build, never the agent, decides
every match. Phase 7 (added by the owner on 2026-10-21) scales that driver to the functions behind
the OpenApoc checklist items the decomp can answer, matched and made readable. Phase 8 writes
clean-room specs for those mechanics in OpenSpec format, checked by a linter, under CC0-1.0, so
OpenApoc can re-implement from the specs without ever seeing the decompiled code.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Hygiene and safety** - No game bytes or secrets tracked, plugins and GSD at project scope, lean CLAUDE.md, docs skeleton (built before GSD was set up; retroactive verification) (completed 2026-10-20)
- [x] **Phase 2: Container and target ingest** - Docker image, hash manifest, ingest/check-orig, LE parser with pytest (built before GSD was set up; retroactive verification) (completed 2026-10-20)
- [x] **Phase 3: Byte-identical round trip** - KKND-style in-place page splice rebuilds both EXEs SHA-1 identical, with a gate proven able to fail (completed 2026-10-21)
- [x] **Phase 4: Compiler identification** - Exact Watcom version and default flags proven by codegen probe and CLIB3R/MATH3R library match (completed 2026-10-23)
- [x] **Phase 5: Split and first matches** - Ghidra split, omf2elf, configure.py + ninja + objdiff, relocation check; one verified match per EXE (completed 2026-10-24)
- [x] **Phase 6: Reporting and agent pilot** - Self-hosted progress, guardrail hooks, per-function driver; 10 easy functions matched unattended with zero regressions (completed 2026-10-26; pilot 3/10, partial accepted by the owner, the target carries to Phase 7)
- [ ] **Phase 7: Mechanics-first decompilation** - Functions behind the OpenApoc checklist items matched byte for byte, named and commented by the driver at scale; readability lint
- [ ] **Phase 8: Clean-room specs for OpenApoc** - OpenSpec-format specs per mechanic with template, `speclint`, `wikifetch`, `apoc-spec` skill, claim inventory and owner review; CC0-1.0; findings docs (bugs, cut content, cheats and easter eggs, Learning AI)

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
**Plans:** 10/10 plans complete

Plans:
**Wave 1**
- [x] 03-01-PLAN.md — Wave 1: `reverseapoc rebuild` tracer, byte-region map with D-19 refusals, "rebuilt, not copied" mutant proofs (RT-01, RT-03, RT-05)
- [x] 03-02-PLAN.md — Wave 1: ninja `verify` edge and the D-15 manifest-hash guard (RT-03)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-03-PLAN.md — Wave 2: linear-address splice API, refusals, overlap, fixup masking, D-13 negative suite (RT-02, RT-04)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-04-PLAN.md — Wave 3: `rebuild --json`/`--exe`, CLI mismatch path, parse-le trailer (RT-03, RT-05)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 03-05-PLAN.md — Wave 4: real-file round trip and control, post-spike facts, docs/toolchain.md correction, phase gate (RT-01..RT-05)

**Gap closure (G-03-3, UAT test 3)**
- [x] 03-06-PLAN.md — Wave 1: fix review warnings WR-05/WR-06 (`configure.py --orig` reaches check-orig and verify; refuse paths ninja or the shell would misread) and WR-02 (masked_fields counts distinct fields); re-run the phase gate on the main checkout (RT-02, RT-03)

**Gap closure (G-03-6, UAT test 6)**
- [x] 03-07-PLAN.md — Wave 1: configure.py refuses non-UTF-8 names without truncating build.ninja (WR-07) and paths starting with `-` (IN-09); `CHECK-ORIG` names the orig dir (IN-10); the rebuild rule passes `--out build` (IN-11); stale skeleton wording removed (IN-08) (RT-03)
- [x] 03-08-PLAN.md — Wave 1: load_manifest raises ManifestError for malformed manifests and non-bare or Windows-reserved names (IN-06, IN-07); labels and refusal reasons count pages within the object (IN-01, IN-02); layout() docstring (IN-03); REFUSED/MISSING name the real input and manifest (VN-01) (RT-02, RT-03, RT-04)
- [x] 03-09-PLAN.md — Wave 1: real-file test helpers derived from le.py's reader instead of splice.py's arithmetic, FACTS unchanged (IN-05); docs/toolchain.md lists SMKP.EXE in the container's orig/ row (IN-04) (RT-03, RT-05)
- [x] 03-10-PLAN.md — Wave 2 *(blocked on 03-07, 03-08, 03-09)*: phase gate re-run on the main checkout, eight steps including `ninja verify` through `--orig` and from a sub-directory build.ninja; all 13 findings marked fixed in 03-REVIEW-DISPOSITION.md (RT-01, RT-03)

### Phase 4: Compiler identification

**Goal**: The exact Watcom version and default flags that built each EXE are known and proven: runtime library modules match byte for byte, and the codegen probe locates its idioms in the game's own code.
**Depends on**: Phase 3
**Requirements**: CID-01, CID-02, CID-03, CID-04, CID-05, CID-06
**Prerequisite**: Met 2026-10-19: Watcom 10.5, 10.6 and 11.0 media are in the gitignored `third_party/watcom-media/` (hash-verified); extracted trees go to `third_party/watcom/<ver>/`, mounted read-only and never baked into the image.
**Success Criteria** (what must be TRUE):
  1. For each owner-supplied version (10.5, 10.6, 11.0), the original compiler runs under wibo 1.2.0 (11.0: native `BINNT\wcc386.exe`; 10.5/10.6: `BINNT\wcc386.exe` is a loader for the LX `BINW\WCC386.EXE`, so both directories are installed) inside `docker compose run`, mounted read-only from `third_party/watcom/`, and compiles a test source to an object file; each compiler binary's hash and banner are logged (CID-01)
  2. A compiler wrapper keyed by `compiler@version` reads `config/cflags.txt`, and a test shows two source files compiled with the version and flags the table assigns to each (CID-02)
  3. Linked CLIB3R/MATH3R runtime modules from one version's `LIB386` match the code objects byte for byte with fixups masked, and the mosura codegen probe compiled with each version locates its idioms in non-library code of both EXEs' code objects (CID-03, CID-04)
  4. `docs/toolchain.md` records the compiler version and default flags per EXE with per-flag evidence, replacing its "To be confirmed in Phase 4" line (CID-05)
  5. A C vs C++ scan (vtables, `__wcpp_` routines, XI/YI segments) reports its result per EXE and confirms `wcc386`, or names the modules that need `wpp386` (CID-06)

**Spike**: wibo 1.2.0 runs `wcc386.exe` for each version (10.5, 10.6, 11.0) in Docker.
**Plans:** 13/13 plans complete

Plans:
**Wave 1**
- [x] 04-01-PLAN.md — `reverseapoc cc` wrapper: config/cflags.txt rules, compiler hash gate and banner log, scrubbed env, Watcom-safe paths (CID-01, CID-02)
- [x] 04-02-PLAN.md — stdlib OMF/LIB reader (fixups, LIDATA, Easy OMF, COMDAT32, normalized object hash) proven on every LIB386 library; real-file skip helpers (CID-04)
- [x] 04-03-PLAN.md — wpack format description, then the independent 10.5 decoder; D-01 time box with recorded verdict or fallback (CID-01)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 04-04-PLAN.md — real compiles per version with banner, compiler and object hashes; env-scrub, -bt=dos, two-source cflags and error-path proofs (CID-01, CID-02)
- [x] 04-05-PLAN.md — masked library matcher, runtime.csv format, config_dir (D-16), disambiguation rules, `libmatch` verb (CID-04)
- [x] 04-06-PLAN.md — `install-watcom 10.5` decodes BINW/WCC386.EXE; decoded compiler pinned in config/watcom.toml (CID-01)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 04-07-PLAN.md — committed config/ufo2p|tacp/runtime.csv with drift test and the D-05/D-07 summary (CID-04)
- [x] 04-08-PLAN.md — clean-room C89 probe, idiom counters and the per-version, per-flag calibration with ties (CID-03)
- [x] 04-09-PLAN.md — C vs C++ scan (XI/YI via inirt386, C++-only runtime rows, mangled strings, vtable candidates), `cppscan` verb (CID-06)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 04-10-PLAN.md — `probe calibrate|scan`: non-library idiom counts, per-flag evidence lines and consistent calibration cells per EXE (CID-03, CID-05)

**Wave 5** *(blocked on Wave 4 completion; main checkout)*
- [x] 04-11-PLAN.md — 10.5 data migration, D-03 native vs wibo log, spike 004 record, toolchain.md/matching.md/learnings.md results and the final cflags default (CID-05, CID-01)

**Wave 6** *(blocked on Wave 5 completion; main checkout)*
- [x] 04-12-PLAN.md — phase gate on host and container: no real-file skips, rebuild still SHA-1 identical, check-watcom OK, drift and D-03 confirmed (CID-01..CID-06)

**Gap closure (G-04-2, UAT test 2)**
- [x] 04-13-PLAN.md — Wave 1 *(main checkout)*: cc.log keeps one intact line per parallel `cc`: stdlib OS lock on the sidecar `<log>.lock` held across open/write/close, concurrent-append regression test red first on host and container, five reverted mutants, toolchain.md/learnings.md, done gate on host and container (CID-01, CID-02)

### Phase 5: Split and first matches

**Goal**: The matching pipeline works end to end: functions are found and grouped into units, C compiles with the identified compiler, objdiff and an independent relocation check compare it to the target cut from the LE, and one hand-matched function per EXE splices back with both EXEs still SHA-1 identical.
**Depends on**: Phase 3, Phase 4
**Requirements**: SPL-01, SPL-02, SPL-03, SPL-04, SPL-05, SPL-06, SPL-07, SPL-08, SPL-09, SPL-10, SPL-11, SPL-12, SPL-13
**Success Criteria** (what must be TRUE):
  1. `config/<exe>/functions.csv` exists for both EXEs, exported by Ghidra 12.1.4 (headless, JDK 21) with one LE loader in the Docker image and cross-checked by an independent capstone discovery pass with every boundary disagreement reconciled, and functions are grouped into translation units under `config/<exe>/` (SPL-01, SPL-02, SPL-03)
  2. `configure.py` writes `build.ninja`, `objdiff.json` and `compile_commands.json`; `ninja` compiles units with the Phase 4 compiler under wibo, every unmatched function keeps its original bytes through the stub convention, per-function asm is generated into gitignored `asm/` by script, and the C89 lint gate (`clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with the Watcom compat header) passes on `src/` (SPL-04, SPL-05, SPL-06, SPL-12)
  3. `omf2elf.py` converts Watcom OMF (COMDAT, LIDATA, FIXUPP threads, BAKPAT, CEXTDEF) to ELF32 with its pytest suite green, and target ELF objects cut from the LE carry relocations rebuilt from the LE fixups (SPL-07, SPL-08)
  4. For one function per EXE, the single-unit `check` tool prints objdiff 100%, a passing relocation check (every non-relocated byte, equal length, every `call rel32` target, every absolute fixup target) and, after splicing with the original link-time value kept at each fixup site, both rebuilt EXEs SHA-1 identical to `config/targets.toml`; a negative test with a wrong call or fixup target makes the relocation check fail even where objdiff reports 100% (SPL-09, SPL-10, SPL-11, SPL-13)

**Spike**: objdiff diffs OMF-converted ELF cleanly (decides hybrid vs fallback: if INVALIDATED, the KKND-style compare stays the oracle and Phase 6 uses a minimal own agent layer).
**Plans:** 20/20 plans complete

Plans:
**Wave 1** *(main checkout)*
- [x] 05-01-PLAN.md — objdiff spike on the cmain386 pair (spike 005): spike-local converter and target cut, plants, D-19 name map, D-02 verdict (SPL-07, SPL-08)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 05-02-PLAN.md — ELF32 writer, omf2elf core and the `omf2elf` verb; real 10.6 object converts (SPL-07)
- [x] 05-03-PLAN.md — capstone 5.0.9 (docs/tools.md first, blocking legitimacy checkpoint, uv add), x86.py decode helpers, Wave 0 skip helpers and Ghidra-loadable LE (SPL-02, SPL-01)
- [x] 05-04-PLAN.md — functions/boundaries/units/symbols CSV schemas, runtime public offsets from LIB386, symbols.py naming (SPL-01, SPL-03)
- [x] 05-05-PLAN.md — INCLUDE_ASM stub in include/common.h and `-i=include;H` in the cc wrapper, proven inert under 10.6 (SPL-04)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 05-06-PLAN.md — omf2elf complete: COMDAT 0xC2, NBKPAT, LIDATA, BAKPAT, CEXTDEF, LPUBDEF, filler sizing, refusals (SPL-07)
- [x] 05-07-PLAN.md — capstone recursive-descent discovery with LE evidence, jump tables, D-07 ends (SPL-02)
- [x] 05-08-PLAN.md — per-unit target ELF cut from the LE with rebuilt relocations and PC32 (SPL-08)
- [x] 05-09-PLAN.md — relocation check and the land step (keep-original fields, splice, SHA-1) with the negative suite (SPL-09, SPL-10, SPL-13)
- [x] 05-10-PLAN.md — Ghidra headless driver, Java export and drafts scripts, export adapter (SPL-01)
- [x] 05-11-PLAN.md — asm listings into gitignored asm/ and the P16 easiest-first scorer, `asm`/`score` verbs (SPL-05)

**Wave 4** *(blocked on Wave 3 completion; main checkout)*
- [x] 05-12-PLAN.md — Ghidra 12.1.4 + JDK 21 + clang 18 in the image, smoke and real export, `ghidra-export` and `lint` verbs, compat header (SPL-01, SPL-12)

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 05-13-PLAN.md — D-07/D-08 reconcile with automatic verdicts, units draft, INCLUDE_ASM scaffold, `discover`/`functions`/`units` verbs (SPL-02, SPL-03, SPL-04)
- [x] 05-14-PLAN.md — configure.py: build.ninja compile/convert/cut/lint/asm/land edges, objdiff.json, compile_commands.json, D-12 check (SPL-06, SPL-04)
- [x] 05-15-PLAN.md — docs: Ghidra in the image (not WSL2), D-03 outcome, spike 005 result, Phase 5 learnings (SPL-01, SPL-12)

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 05-16-PLAN.md — commit functions.csv, boundaries.csv (every disagreement reconciled), units.csv and symbols.csv for both EXEs with drift tests (SPL-01, SPL-02, SPL-03)
- [x] 05-17-PLAN.md — `check` (objdiff %, reloc check, both splice SHA-1s), `target` and `land` verbs, logged D-17 sweep (SPL-11, SPL-10)

**Wave 7** *(blocked on Wave 6 completion; main checkout)*
- [x] 05-18-PLAN.md — cmain386 production re-proof and real negatives, then the first UFO2P match (SPL-13, SPL-09, SPL-10, SPL-06)

**Wave 8** *(blocked on Wave 7 completion; main checkout)*
- [x] 05-19-PLAN.md — the first TACP match, UFO2P match kept, D-18 evidence recorded (SPL-13)

**Wave 9** *(blocked on Wave 8 completion; main checkout)*
- [x] 05-20-PLAN.md — phase gate: container ninja graph and both checks, rebuild/cmp, both suites with skip audit, hygiene, validation sign-off (SPL-01..SPL-13)

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
**Plans:** 27/27 plans complete
**UI hint**: yes

Plans:
**Wave 1** *(D-38 Wave 1: spike and deferred-item hardening)*
- [x] 06-01-PLAN.md — spike 006: decomp.wtf v0.10.6 fork mode vs the stub convention, D-02 verdict, D-03 consequence (AGT-10)
- [x] 06-02-PLAN.md — DI-18 fileio.write_atomic and the importer flip; symbols/functions minors (RPT-01, AGT-06)
- [x] 06-03-PLAN.md — DI-05 continuation-aware D-12 parser, DI-04 relocs refusals and frame check, DI-06c config-consistent rules (AGT-05, AGT-06)
- [x] 06-04-PLAN.md — 05 minors: discover end rule (measured), lint and drafts-script refusals, CSV tiling without orig/ (AGT-06, AGT-08)
- [x] 06-05-PLAN.md — 05 minors: comment-only void note in matched TACP C, spike 005 wording, test hygiene, Dockerfile comment (AGT-06)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 06-06-PLAN.md — DI-01 one asm listing per row (999.3); scorer and listing minors (AGT-07, AGT-08)
- [x] 06-07-PLAN.md — DI-11..DI-17 cc/log fixes (999.1), DI-23 proofs, the owner-authorized watcom.toml LE->LX note fix (AGT-05, AGT-06)
- [x] 06-08-PLAN.md — relocation verdicts tied to their row and bytes; raw-field reasoning corrected and tested (AGT-06)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 06-09-PLAN.md — DI-06a/b provenance stamps and stale-object refusal, check --src/--config isolation; check minors (AGT-06)

**Wave 4** *(D-38 Wave 2; blocked on Wave 3 completion)*
- [x] 06-10-PLAN.md — DI-02 leading jump tables and DI-03 row-named statics pass check, with real wcc386 probes (AGT-06, AGT-07)
- [x] 06-11-PLAN.md — status.csv (D-20) and the `gate` verb with cross-check, --all and --partial (RPT-01, AGT-06)
- [x] 06-12-PLAN.md — guardrail hooks: always-on and matching layers, attempt-wrapper Bash allowlist, settings files (AGT-05)
- [x] 06-13-PLAN.md — context pack library: sections, callers/callees, look-alikes, 24 KB cap (AGT-08)
- [x] 06-14-PLAN.md — status-aware easiest-first picker with the variety rule and re-queue (AGT-07, AGT-02)

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 06-15-PLAN.md — attempt wrapper and `context` verb; watcom-decomp skill (writing-skills); D-18 pragma policy (AGT-08, AGT-09, AGT-05)

**Wave 6** *(blocked on Wave 5 completion; main checkout)*
- [x] 06-16-PLAN.md — seed status.csv with the container gate, CI drift test, real container proofs, both suites (RPT-01, AGT-06)

**Wave 7** *(D-38 Wave 3; blocked on Wave 6 completion)*
- [x] 06-17-PLAN.md — session argv, /goal prompt, stream-json classifier, init assertions, stand-in claude (AGT-01, AGT-03, AGT-04)
- [x] 06-18-PLAN.md — progress.py: progress.json, shield, report.json, DecompHub feed; gate rewrites the feed (RPT-02, RPT-04, RPT-05)
- [x] 06-19-PLAN.md — listing drafts: three awesome-list PRs and the decomp.me preset request (RPT-05)
- [x] 06-20-PLAN.md — docs carry-overs: .dockerignore, SMKP entry, stale text, tool verdicts, AI-use record (AGT-10, RPT-04, AGT-06)
- [x] 06-21-PLAN.md — planning paperwork and the DI-01..DI-37 ledger (AGT-10, AGT-11)
- [x] 06-22-PLAN.md — README progress section, .recomp.json, DecompHub verification file (RPT-05, RPT-03)

**Wave 8** *(blocked on Wave 7 completion)*
- [x] 06-23-PLAN.md — the driver loop: caps, backoff, audit, gate before commit, reset, attempts.jsonl (AGT-01..AGT-04, AGT-06)
- [x] 06-24-PLAN.md — treemap SVG, Pages workflow with the report artifact, gated DecompHub POST (RPT-02..RPT-05)

**Wave 9** *(blocked on Wave 8 completion)*
- [x] 06-25-PLAN.md — `drive` verb: preflight with CLI pin, dry run, owner-run canary, end-of-run verify, docs (AGT-01, AGT-04, AGT-06, AGT-07, AGT-11)

**Wave 10** *(D-38 Wave 4; blocked on Wave 9 completion; main checkout)*
- [x] 06-26-PLAN.md — pilot checkpoint: session-free preflight, then the owner upgrades the CLI, sets Pages, sends drafts, runs the canary and the pilot (AGT-11, RPT-03, RPT-05)

**Wave 11** *(blocked on Wave 10 completion; main checkout)*
- [x] 06-27-PLAN.md — phase gate: pilot vs D-37 with every match re-gated, evidence and paperwork, both suites, validation sign-off (all Phase 6 requirements)

### Phase 7: Mechanics-first decompilation

**Goal**: Every function behind the OpenApoc checklist items the decomp can answer is located, matched byte for byte and made readable (meaningful names, header comments, named types and constants) by the Phase 6 driver at scale, with both EXEs SHA-1 identical after every commit.
**Depends on**: Phase 6
**Requirements**: DEC-01, DEC-02, DEC-03, DEC-04, DEC-05, DEC-06, DEC-07, AGT-11
**Carry-in**: AGT-11 (carried in from Phase 6, 3/10): its 10 unattended matches with zero regressions are reached during this phase (owner ruling D-05, 2026-10-26)
**Success Criteria** (what must be TRUE):
  1. `config/mechanics.toml` maps each answerable item of OpenApoc #263, #264, #265 and #997 to its EXE and the functions behind it, located from UI strings and data-table cross-references, and the owner has signed the list off (DEC-01)
  2. The driver works through the list callees first, with claims so parallel agents never take the same function and a single owner of the shared naming state (DEC-02, DEC-06)
  3. For every function in Tier 1's must-match set, `check` prints objdiff 100% and a passing relocation check, and after the last commit `rebuild` plus `cmp` against `orig/` are silent for both EXEs with zero regressions; every tier 1-4 is signed off in `config/mechanics.toml` (owner ruling D-05, 2026-10-26; D-22 hub rule, D-23 asm rows excluded, D-31 entries always must match) (DEC-03)
  4. `uv run reverseapoc readlint src/` exits 0, and negative tests show it fails on a `FUN_`/`sub_`/`DAT_` placeholder name and on our own `func_XXXXXXXX` / `D_XXXXXXXX` placeholders (backlog 999.2), a function without a header comment, and an unnamed struct field or magic constant in a matched unit; pytest and ruff pass on the host and in the container (DEC-04)
  5. The progress page shows coverage per checklist item, Tier 1's must-match set reads matched, and Tiers 2-4 show their located and signed-off state with both the must-match and full-closure figures (owner ruling D-05, 2026-10-26) (DEC-05)
  6. `uv run reverseapoc stats` prints match rate by function size, attempts per match, turns, tokens, cost and time per matched function, regressions stopped, hook blocks and the `unattended` / `human-hints` / `human-written` split over the whole Phase 6-7 history, and tests show it refuses a malformed `attempts.jsonl` line and classes a hand-landed match without the `Matched-By` trailer as `human-written` (DEC-07)

**Spike**: Locate the #997 tick-rate and training code from the timer setup and strings within a time box; decides whether "find via strings and data xrefs" scales to the whole list.
**Plans:** 7/42 plans executed

Plans:
**Wave 1**
- [x] 07-01-PLAN.md — D-05/D-06 paperwork: done-rule rewording (DEC-03, DEC-05, SC3, SC5, roadmap row), decomp.wtf not re-evaluated (DEC-03, DEC-05, DEC-06)
- [x] 07-02-PLAN.md — spike 007 part 1 *(main checkout)*: q1 time base, q2 tick rule, q3 training rule with planted failures (DEC-01)
- [x] 07-03-PLAN.md — D-27 P1/P2: cflags rule by logical unit path, gate refuses uncommitted flags, real view-compile test (DEC-03, DEC-02)
- [x] 07-04-PLAN.md — hooks: owner-only cflags files, view-mode allowlist, view-unit scan, D-19 denies, readability kind (DEC-02, DEC-03)
- [x] 07-05-PLAN.md — callgraph.py: typed edges, mid-row/indirect/orphan reports, closure, SCCs (DEC-01)
- [x] 07-06-PLAN.md — progress page backlog 999.4: phone mosaic, keyboard/touch tooltips, visible bar (DEC-05)
- [x] 07-07-PLAN.md — attempts.jsonl v2 schema: per-attempt fields, limit/rename kinds, nightly totals (DEC-07, DEC-06)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 07-08-PLAN.md — spike 007 part 2 *(main checkout, owner checkpoint)*: get_text, tables, call graph, verdict, #997 report to the owner (DEC-01)
- [ ] 07-09-PLAN.md — D-29 part 1: shared renamed-aware unit finder, configure D-12, source_marks, drift test by start (DEC-02, DEC-04)
- [ ] 07-10-PLAN.md — mechanics.py: TOML schema, members generator with member/hub/closure/asm roles, tier digests, `mechanics` verb (DEC-01)
- [ ] 07-11-PLAN.md — attempt wrapper: checks rooted in the private view, env validation (DEC-02)

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 07-12-PLAN.md — locate.py and the asm detector, `mechanics locate` and `mechanics asm` (DEC-01)
- [ ] 07-13-PLAN.md — driver private views: HEAD snapshot, landing section, ledger and view-hash audit, no header writes (DEC-02)
- [ ] 07-14-PLAN.md — D-15 second-stage sweep and the -zm spike (DEC-03)
- [ ] 07-15-PLAN.md — progress coverage view per checklist item, asm group, Pages paths (DEC-05)
- [ ] 07-16-PLAN.md — D-29 part 2: SymbolTable.c_name, gate._reverted by start, linker-name path pinned (DEC-02, DEC-04)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 07-17-PLAN.md — flags propose/regate/list, the review queue, D-16 re-derivation (DEC-03, AGT-11)
- [ ] 07-18-PLAN.md — claims, drive.lock, gate and git locks, concurrency-safe writes (DEC-02)
- [ ] 07-19-PLAN.md — D-19 naming-proposal format and validators (DEC-02, DEC-04)
- [ ] 07-20-PLAN.md — asm list generated and signed off by the owner *(main checkout, owner checkpoint)* (DEC-01, DEC-03)

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 07-21-PLAN.md — N worker threads, shared usage-limit pause, stop-all, shared night cap, new defaults (DEC-02, DEC-06)
- [ ] 07-22-PLAN.md — Tier 1 drafted, mid-row refs classified, hub-rule numbers, owner sign-off *(main checkout, owner checkpoint)* (DEC-01)

**Wave 6** *(blocked on Wave 5 completion)*
- [ ] 07-23-PLAN.md — v2 records written: hook blocks, gate verdicts, passes, nightly totals, limit records (DEC-06, DEC-07)
- [ ] 07-24-PLAN.md — flags approve and default (owner-run), D-33 evidence bar, per-rule docs check (DEC-03)
- [ ] 07-25-PLAN.md — Tier 2 (#263) drafted and signed off *(main checkout, owner checkpoint)* (DEC-01)
- [ ] 07-42-PLAN.md — model table: Opus passes 1-2 then Fable, per-model budget defaults, `build_argv` per-session values, requested-model init check (DEC-06, AGT-11)

**Wave 7** *(blocked on Wave 6 completion)*
- [ ] 07-26-PLAN.md — tier picker: callees first by SCC level, hubs after members, unlimited passes (DEC-02, DEC-03)
- [ ] 07-27-PLAN.md — readlint RL01-RL06 with allowlist, waivers and scoped modes (DEC-04)
- [ ] 07-28-PLAN.md — Tier 3 (#264) drafted and signed off *(main checkout, owner checkpoint)* (DEC-01)
- [ ] 07-29-PLAN.md — D-13 pilot sweep hits: propose, container re-gate, owner approves the batch *(main checkout, owner checkpoint)* (DEC-03, AGT-11)

**Wave 8** *(blocked on Wave 7 completion)*
- [ ] 07-30-PLAN.md — Opus-then-Fable escalation wired into the driver, per-model budgets, init check and co-author by requested model, cap flags, canary `--model` (AGT-11, DEC-06, DEC-02)
- [ ] 07-31-PLAN.md — readability sessions' `attempt check` adds readlint on the view unit (DEC-04)
- [ ] 07-32-PLAN.md — Tier 4 (#265) drafted and signed off *(main checkout, owner checkpoint)* (DEC-01)
- [ ] 07-33-PLAN.md — optional `*` default ruling on D-33 evidence *(main checkout, owner checkpoint)* (DEC-03)

**Wave 9** *(blocked on Wave 8 completion)*
- [ ] 07-34-PLAN.md — driver applies rename and header proposals as gated commits (DEC-02, DEC-04)
- [ ] 07-35-PLAN.md — watcom-decomp for private views (writing-skills) and Phase 7 driver docs (DEC-02, DEC-06)
- [ ] 07-36-PLAN.md — new watcom-readability skill (writing-skills) and the readability pass in ceremonies (DEC-04)
- [ ] 07-37-PLAN.md — `reverseapoc stats` over the Phase 6-7 history, match classes from git (DEC-07, AGT-11)

**Wave 10** *(blocked on Wave 9 completion)*
- [ ] 07-38-PLAN.md — readability session kind in the driver, one unit per commit (DEC-04, DEC-02)

**Wave 11** *(blocked on Wave 10 completion; main checkout)*
- [ ] 07-39-PLAN.md — owner canaries (Opus, Fable) and matching nights until Tier 1 is matched, with a two-flat-nights stall decision (DEC-03, DEC-06, AGT-11)

**Wave 12** *(blocked on Wave 11 completion; main checkout)*
- [ ] 07-40-PLAN.md — owner readability nights, D-30 allowlist, `readlint src/` clean (DEC-04)

**Wave 13** *(blocked on Wave 12 completion; main checkout)*
- [ ] 07-41-PLAN.md — phase gate: done rule, sampled re-gates, rebuild + cmp, both suites, validation sign-off (all Phase 7 requirements)

### Phase 8: Clean-room specs for OpenApoc

**Goal**: Every mechanic decompiled in Phase 7 has a clean-room spec in OpenSpec format, written in our own words, citing function addresses and dated community sources, checked by a linter that can fail, reviewed by the owner and licensed CC0-1.0 so OpenApoc can use it without conditions.
**Depends on**: Phase 7
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05, SPEC-06, SPEC-07, SPEC-08, SPEC-09, SPEC-10
**Success Criteria** (what must be TRUE):
  1. `specs/_template/spec.md` has the OpenSpec shape (`## Purpose`, `## Requirements`, `### Requirement:` with SHALL/MUST, `#### Scenario:` with WHEN/THEN) plus OpenApoc issue, constants and formulas, functions (EXE + address), evidence, sources and status on the ladder `drafted -> cited -> backed-by-matched-code -> dosbox-verified -> reviewed-by-openapoc` (SPEC-01)
  2. `uv run reverseapoc speclint specs/` exits 0, and negative tests show it fails on a missing section, a requirement without SHALL/MUST or scenario, an address not in `config/<exe>/functions.csv`, a `backed-by-matched-code` claim the gate-written status table does not support, a `dosbox-verified` claim without a test, a fenced C block or text copied from `src/`, and a source without URL, access date and wiki revid (SPEC-02)
  3. `uv run reverseapoc wikifetch` fetches single pages through the MediaWiki API with a descriptive User-Agent, at least 10 s between requests per host and the revid recorded, caches into a gitignored directory, and its tests run offline (SPEC-03)
  4. The `apoc-spec` skill exists in `.claude/skills/apoc-spec/`; `docs/clean-room.md` states the author/implementer split and the human review rule and links both OpenApoc Discord messages; `specs/LICENSE` is CC0-1.0 and `docs/legal.md` and `README.md` name it (SPEC-04, SPEC-05, SPEC-06)
  5. `specs/claims.md` lists the mechanics claims from UFOpaedia, Wikibooks, StrategyWiki and the OpenApoc Discord, paraphrased and linked, each tied to a checklist item with a verdict (confirmed, refuted, refined) or marked "none found" (SPEC-07)
  6. Every target in `config/mechanics.toml` has a spec that passes `speclint`, reaches at least `backed-by-matched-code`, and carries an owner review line with date; pytest and ruff pass on the host and in the container (SPEC-08, SPEC-09)
  7. `docs/findings/` holds `bugs.md`, `cut-content.md`, `cheats-and-easter-eggs.md` and `learning-ai.md`, filled with the community reports and the Phase 7 findings known at the time; every entry has an EXE, a build, an address where known and a status (`reported`, `confirmed`, `refuted`, `not seen in the code matched so far`), and no entry reads `confirmed` unless its function is matched per the gate-written status table (SPEC-10)

**Spike**: `wikifetch` fetches one UFOpaedia table page with the revid recorded and the table numbers intact (decides fetcher vs MCP extract for citations).
**Plans**: TBD
**Note**: Write the `apoc-spec` skill (SPEC-04) with superpowers' `writing-skills` skill (owner, 2026-10-24). That is the rule for every project skill, in `.claude/rules/workflow.md`.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Hygiene and safety | 2/2 | Complete    | 2026-10-20 |
| 2. Container and target ingest | 2/2 | Complete    | 2026-10-20 |
| 3. Byte-identical round trip | 10/10 | Complete    | 2026-10-21 |
| 4. Compiler identification | 13/13 | Complete    | 2026-10-23 |
| 5. Split and first matches | 20/20 | Complete    | 2026-10-24 |
| 6. Reporting and agent pilot | 27/27 | Complete    | 2026-10-26 |
| 7. Mechanics-first decompilation | 7/42 | In Progress | - |
| 8. Clean-room specs for OpenApoc | 0/TBD | Not started | - |

## Backlog

### Phase 999.1: Follow-up — Phase 04 deferred UAT follow-up: Test 5 (BACKLOG)

**Goal:** Resolve the UAT checkpoint deferred during Phase 04 verification
**Source phase:** 04
**Deferred at:** 2026-10-23 during /gsd-verify-work 04 session completion
**Follow-ups:**
- [x] Test 5 (closed by plan 06-07, b328679): Update docs/toolchain.md (the cc.log bullet) to say --log must name a file: `--log .` or `--log /` is refused before the compile, and an existing folder compiles first and then fails ('Is a directory' in the container, 'Permission denied' on the Windows host); also say the `_append_log` device branch covers directories (deferred 2026-10-23)

### Phase 999.2: Follow-up — Phase 05 deferred UAT follow-up: Test 1 (BACKLOG)

**Goal:** Resolve the UAT checkpoint deferred during Phase 05 verification
**Source phase:** 05
**Target phase:** 7 (success criterion 4, DEC-04)
**Deferred at:** 2026-10-24 during /gsd-verify-work 05 session completion
**Follow-ups:**
- [ ] Test 1: readlint must also reject our own placeholders `func_XXXXXXXX` / `D_XXXXXXXX` in a matched unit, not only Ghidra's `FUN_`/`sub_`/`DAT_`; Phase 7 success criterion 4 as worded would let src/ufo2p/u_000a34f0.c and src/tacp/u_00054f20.c through unnamed (deferred 2026-10-24)

### Phase 999.3: Follow-up — Phase 05 deferred UAT follow-up: Test 5 (BACKLOG)

**Goal:** Resolve the UAT checkpoint deferred during Phase 05 verification
**Source phase:** 05
**Target phase:** 6 (agents start relying on asm/ listings)
**Deferred at:** 2026-10-24 during /gsd-verify-work 05 session completion
**Follow-ups:**
- [x] Test 5 (closed by plan 06-06, a56080d, 6d535c1): `reverseapoc asm` writes a name that SymbolTable.ambiguous lists (`_Alphabet`: UFO2P 0x000C06FA / 0x000C92CD, TACP 0x000C2826 / 0x000CD0AF) as `<kind>_<start>.s`, so no listing overwrites another (one file per functions.csv row), with a test (deferred 2026-10-24)

### Phase 999.4: Follow-up — Phase 06 deferred UAT follow-up: Test 3 (BACKLOG)

**Goal:** Resolve the UAT checkpoint deferred during Phase 06 verification
**Source phase:** 06
**Deferred at:** 2026-10-26 during /gsd-verify-work 06 session completion
**Follow-ups:**
- [ ] Test 3: on a 390 px phone the progress-page mosaic shrinks to ~31% and its unit labels and legend are unreadable; let `.mosaic` scroll sideways with a minimum SVG width (~48rem) or move the legend into HTML (06-UI-REVIEW.md fix #2). Also there: tooltips are `title`-only, so mouse-only (fix #1), and the percent bar draws nothing at current values (fix #3) (deferred 2026-10-26)
