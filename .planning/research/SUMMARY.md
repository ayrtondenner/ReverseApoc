# Project Research Summary

**Project:** ReverseApoc
**Domain:** Byte-matching decompilation of a 1997 DOS/4GW-bound Watcom 10.x LE game (X-COM: Apocalypse — UFO2P.EXE `ufo24`, TACP.EXE `tac4`) with an unattended AI agent layer
**Researched:** 2026-10-19 (local sources only; no web/MCP lookups)
**Confidence:** MEDIUM (HIGH for repo pins and locally-measured facts; MEDIUM for borrowed tooling never yet run on UFO2P/TACP)

> **Phases:** the phase structure is fixed by the owner in `docs/workflow.md`: 1 Hygiene and safety (done), 2 Container and target ingest (done), 3 Byte-identical round trip, 4 Compiler identification, 5 Split and first matches, 6 Reporting and agent pilot.

## Executive Summary

ReverseApoc is a matching decompilation: C source that, compiled with the original Watcom 10.x, must reproduce the shipped executables byte for byte. Every comparable project converges on the same three-layer shape — an analysis layer that finds functions and drafts C but never judges, a deterministic oracle (compile → compare → splice → hash), and a replaceable agent/driver layer on top. The closest precedents are KKND-Decomp (bound DOS/4GW Pro LE, in-place page splice, SHA-1 gate) and Theme Hospital (real Watcom 10.6 under wibo, configure.py + ninja, OMF→ELF into objdiff). The recommended build is KKND's gate plus Theme Hospital's build/compare path.

The recommended approach is opinionated: in-place page splice into a copy of the original EXE (1-3 days) instead of a full LE rewrite (10-20+ days); the real user-supplied `BINNT\wcc386.exe` (10.6 hypothesis) under wibo 1.2.0 inside the existing Docker image, never Open Watcom `wcc386` for matching; Theme Hospital's `omf2elf.py` (GPLv3) to make objects objdiff-readable — but objdiff is only a viewer, and "matched" means relocation check + equal length + whole-EXE SHA-1 for both EXEs. Progress is published from committed per-function metadata because CI never has the game or compiler. The agent pilot is a driver that picks the function, runs one fresh `claude -p "/goal ..."` session per function, re-verifies itself, and commits or resets; decomp.wtf v0.10.6 fork mode (owner decision) is gated on the Phase 5 objdiff spike.

The key risks are (1) oracles that cannot fail — an identity round trip passes on day one and proves nothing, and objdiff 100% misses a second relocation per instruction; (2) new local facts that contradict the docs — a 27-byte trailer after the last LE page in both EXEs, and 14/11 page-straddling off32 fixups; (3) documented verifier gaming by unattended agents (SHA-1 rewrite, bypassed `make`, Python editing a forbidden file). Mitigations: mutation/negative tests and a region-coverage model of the whole file, flat-address splicing, one four-check verify command, and layered defences (driver re-verification, diff allowlist, read-only mounts, pytest-tested hooks).

## Key Findings

### Recommended Stack

The Phase 1-2 baseline is pinned and stays: Python 3.14, uv 0.12.23, ubuntu:24.04 by digest, ninja 1.11.1, binutils 2.42, wibo 1.2.0, objdiff-cli v3.8.2, OW v2 tools (`wdis`/`wlink`/`wlib` only), zero runtime Python deps. Phase 3 adds nothing but stdlib. Phase 4 adds user-supplied compilers on a read-only mount. Phase 5 adds the first runtime dependency (capstone), the clang 18 driver for the C89 lint gate, and the WSL2 analysis stack. See STACK.md.

**Core technologies:**
- Original Watcom `wcc386.exe` 10.6 (10.5 equivalent; 11.0 probe-only), user-supplied — only compiler that can produce the game's bytes; banner + `and eax,0FFh` vs `movzx` counts (33/61 vs 1/1) point to classic 10.x.
- wibo 1.2.0 (already pinned) — runs BINNT Watcom on Linux; older wibo fails with "Unhandled function LocalAlloc".
- In-place page splice (KKND, CC0, adapted) + whole-EXE SHA-1 vs `config/targets.toml` — the done gate.
- `configure.py` -> `build.ninja` + `objdiff.json` + `compile_commands.json`, per-glob `compiler@version` flags in `config/cflags.txt` (Theme Hospital pattern) — also the contract decomp.wtf fork mode consumes.
- Theme Hospital `omf2elf.py` + `elfrelocs.py`/`verify.py` (GPLv3) — objdiff cannot read OMF (#97) and compares at most one relocation per instruction.
- Ghidra 12.1.4 + one LE loader (lastonesky v12.1.4-1 or retrokit 0.2.0) + GhidraMCP 2.0 headless (Python 3.13) in WSL2, cross-checked with KKND capstone `find_functions.py`.
- Phase 6: own stdlib `progress.py` + Pages deploy + shields endpoint + `<VERSION>_report` artifact for recomp.fyi; Claude Code hooks; `watcom-decomp` skill; driver (Nigel evaluated first, ~200-line Python fallback).

**Image/config gaps surfaced by research:** the `clang` driver package is missing (lint gate needs it; add in Phase 5, pinned `1:18.0-59~exp2`); `.gitignore` lacks `objdiff.json`, `compile_commands.json` and the Docker-created empty `watcom/` mountpoint; `.claude/hooks/` is gitignored (GSD install dir), so project hook scripts must live elsewhere (e.g. `.claude/guard/`).

### Expected Features

FEATURES.md assigns requirement IDs per phase: RT (3), CID (4), SPL (5), RPT/AGT (6).

**Must have (table stakes — the Milestone 1 gates):**
- RT-01..05 — rebuild from decomposed regions (not a file copy), splice API with guards, SHA-1 gate for both EXEs, negative tests, LE edge-case confirmation on real files.
- CID-01..06 — wcc386 under wibo per version, `compiler@version` wrapper + `cflags.txt`, mosura codegen probe, CLIB3R/MATH3R library match, default flags with per-flag evidence, C vs C++ scan.
- SPL-01..13 — Ghidra discovery + capstone cross-check, per-EXE unit config, stub convention, generated `asm/`, configure/ninja compile path, omf2elf, target ELF cut from the LE, relocation check, fixup-site splice, single-unit `check` tool, C89 lint, first hand match per EXE.
- RPT-01..05 — committed gate-written per-function status, `progress.py`, Pages, objdiff-shaped report artifact, `.recomp.json`/decomphub listings.
- AGT-01..09 — re-verifying driver, 3-5 attempt cap + re-queue, tri-state outcome log, usage-limit backoff, guardrail hooks, zero-regression gate, easiest-first scorer, context pack, `watcom-decomp` skill; AGT-10 decomp.wtf fork mode conditional on the Phase 5 spike.

**Should have (differentiators, mostly next milestone):**
- UFO2P <-> TACP twin matching (normalized-asm hashes, then opcode Levenshtein) — the project's structural advantage; build the normalized-asm data in Phase 5.
- Library-match-first clearing of the Watcom runtime (cheap real names) — falls out of CID-04.
- Trivial-family auto-matcher, name evidence from diagnostic strings, OpenApoc-reader comment pass, human-approved retrospective loop, mismatch diagnostics.

**Defer (v2+):** full LE rewrite / relinkable build, data/rodata placement matching, CD v1.00 as a matching target, SMKP.EXE, embeddings, parallel agents, `variants.py` beam search.

**Anti-features:** playable port, modernizing matched C, inline asm / asm stand-ins counted as matches, Open Watcom for matching, compiler baked into the image, permuter / m2c, Ralph Loop as driver, agent-chosen functions, >5 attempts per function per pass, decomp.wtf from-scratch mode, decomp.dev / frogress.

### Architecture Approach

Three layers with arrows pointing only into the oracle; the oracle reads only `src/` + `include/` from the agent side. One Python package / one CLI (`uv run reverseapoc <verb>`) is the only thing `build.ninja` calls, keeping the protected surface small. Every tool is keyed by `<exe>`; per-target tables under `config/<exe>/`; twins shared via `src/common/` with repeatable `// FUNCTION: UFO2P 0x...` markers (recommendation, not yet decided). Target bytes always come from file pages via `le.py` (`relocate=False`), never from Ghidra. See ARCHITECTURE.md (components C1-C21).

**Major components:**
1. C3 byte-region map + C4 splicer + C5 rebuild/SHA-1 gate (Phase 3) — tile the whole file, apply flat-address patches, hash.
2. C6 wibo compiler wrapper + C7 OMF reader + C8 library matcher/probe (Phase 4) — OMF reader pulled forward from Phase 5 because the library match needs it.
3. C9 ELF writer, C10 omf2elf, C11 target splitter, C12 function table, C13 reloc check, C14 landing, C15 full configure.py (Phase 5).
4. C16 progress, C17 scorer, C18 driver, C19 hooks, C20 decomp.wtf fork mode, C21 skill (Phase 6).

### Critical Pitfalls

1. **Tautological round trip** — `bytearray(original)` with no patches always passes. Avoid: rebuild through object images + page map; mutation tests (mid-page, page edge, short last page, across boundaries) and a negative test that must report the offset/VA.
2. **27-byte trailer** (both EXEs, starts `64 00 9B FF`) contradicts the docs' "page data runs exactly to EOF". Avoid: model it as an opaque region; coverage assertion that regions tile the file; record offset/length/hash only, never bytes.
3. **Page-straddling fixups** (14 UFO2P / 11 TACP) — splice and mask in flat address space; the deduplicated `fixups()` list is the single relocation source; address-only regression fixture.
4. **objdiff 100% != match** — one verify command: objdiff + every relocation target + equal length/non-relocated bytes + both whole-EXE SHA-1s; humans, driver and hooks all call it; KKND-style compare stays authoritative regardless of the spike.
5. **Compiler fingerprinting on library code / fake compilers** — library match first; idiom counts in non-library code of both EXEs; record library version and game-code compiler separately; hash every compiler binary (the 10.5 CD `BINW/WCC386.EXE` is a damaged 64 KiB stub), log banners, per-version `h/` only, native-vs-wibo cross-check.
6. **Verifier gaming** — Edit/Write hooks are insufficient; layer driver re-verification, a `git diff --name-only` allowlist (`src/`, `include/`, notes), read-only oracle mounts, pytest-tested Bash-pattern hooks, plus the code-emitting `#pragma aux` rule (decomp.wtf's `_CHEAT` filter does not cover it).
7. **Quota exhaustion counted as failed attempts / cross-unit regressions / inflated progress** — classify session exits; rebuild every matched unit + both EXEs before each commit; only the gate writes the status column.

## Implications for Roadmap

The six-phase structure is fixed; Phases 1-2 are complete. Research maps onto Phases 3-6 as follows.

### Phase 1: Hygiene and safety (done)
**Status:** complete. Carry forward its leak-scan tests: every later phase opens new side channels for game bytes (fixtures, docs, transcripts, artifacts) — Pitfall 13.

### Phase 2: Container and target ingest (done)
**Status:** complete. `le.py`, hash manifest, `configure.py` skeleton and Docker image are the baseline. `tests/test_le_real.py` already demonstrates both EXEs parse with physical pages and internal fixups only, which de-risks most of the Phase 3 spike.

### Phase 3: Byte-identical round trip
**Rationale:** needs no compiler and no OMF, so build and harden it first; Phase 5's "splices back, whole EXE still identical" reuses this path unchanged, and a splice bug found later looks like a codegen problem.
**Delivers:** C3 region map (blob, MZ/LE stub, header, loader/fixup tables, pages, 27-byte trailer, coverage assertion); C4 `splice(exe, {va: bytes})` with guards (no writes outside page data, no length change); C5 rebuild + SHA-1 gate as a CLI verb and `ninja verify` edge for both EXEs.
**Addresses:** RT-01..05.
**Avoids:** Pitfalls 1, 2, 3, 21 (record "in-place only; full rewrite deferred" in CONTEXT.md with reopen trigger "a matched function changes size").
**Docs:** the content update due in `docs/toolchain.md` is the stale "To be confirmed in Phase 2/3" LE-quirks line, which must now state the measured facts (physical pages only, 14/11 straddling fixups, 27-byte trailer instead of "runs exactly to EOF"). Have `parse-le` report bytes-after-last-page.

### Phase 4: Compiler identification
**Rationale:** no match is possible without the version and default flags; the wibo wrapper built here is the Phase 5 compile path.
**Delivers:** C6 wibo wrapper keyed by `compiler@version` (path rewriting, compiler-hash check), `config/cflags.txt`, C7 OMF reader (reader half of `omf2elf.py`), C8 library match + mosura probe, C/C++ scan, default flags and `-zp` recorded per EXE in `docs/toolchain.md`, runtime names into `config/<exe>/symbols.csv`.
**Uses:** user-supplied Watcom 10.5/10.6/11.0 (ro mount), wibo 1.2.0, `wlib`/`wdis`, KKND `lib_match.py`, TH `cc.py`.
**Avoids:** Pitfalls 5, 6, 17, 18, 22. Order: library match first, then probe idioms in non-library code; validate flags on real game functions from both EXEs.
**Bonus:** run objdiff on one converted CLIB3R module as a free preview of the Phase 5 spike; a library function matched here is a known-good pair for testing the bridge.

### Phase 5: Split and first matches
**Rationale:** depends on Phase 3 (splice) and Phase 4 (compiler, flags, OMF reader). Run the objdiff spike first, time-boxed with an explicit INVALIDATED outcome; the gate does not depend on its outcome, but C11/C20/RPT-04 do.
**Delivers:** function table from Ghidra + capstone reconciliation (`ghidra2functions` adapter), `units.csv`, stub convention (no-op `extern int INCLUDE_ASM_##name`, chosen with Phase 6's fork mode in view and exercised on a toy repo), generated gitignored `asm/`, full `configure.py`, omf2elf + ELF writer, target objects with synthesized R_386_PC32, relocation check, landing step, `check` tool, clang C89 lint + compat header, one verified first match per EXE, normalized-asm data for future twins.
**Addresses:** SPL-01..13.
**Avoids:** Pitfalls 4, 7, 8, 9, 11, 15, 16, 19, 20. Filter first-match candidates mechanically: game code, no local-data refs, no jump table, no straddling fixup, ≥1 `call rel32` and ≥1 absolute fixup. Re-locate every OpenApoc address (they describe the CD v1.00 build).
**Also:** provide the single four-check verify command and the read-only mount layout that Phase 6's hooks and driver depend on. Add `clang` to the Dockerfile and `capstone` to `pyproject.toml` (reason recorded in `docs/tools.md`, cp314 wheels checked).

### Phase 6: Reporting and agent pilot
**Rationale:** needs the Phase 5 verify command, function table and stub convention. Internal order: hooks + diff allowlist before the first unattended run; progress reporting is independent and can run in parallel; the fork-mode stub spike precedes choosing decomp.wtf over a minimal own layer.
**Delivers:** RPT-01..05 (gate-written status table, stdlib `progress.py` treemap + shield + `report.json`, Pages workflow, listings) and AGT-01..10 (driver, cap, logs, backoff, hooks with pytest, zero-regression gate, easiest-first scorer, context pack, `watcom-decomp` skill, decomp.wtf fork mode if the spike allows).
**Avoids:** Pitfalls 10, 12, 13, 14, 25, 26, 27. Minimal settings profile for driver sessions (no GSD/superpowers/LLM-review hooks), gitignored transcripts, frozen pilot candidate list excluding library and auto-family functions, repo visibility settled before Pages.

### Phase Ordering Rationale

- The order is fixed and research confirms it: splice before compiler, compiler before split, oracle before agents; each phase's gate primitive is reused unchanged by the next.
- One deliberate pull-forward: the OMF reader (C7) moves from Phase 5 into Phase 4 because the library match needs it.
- One deliberate look-ahead: the Phase 5 stub convention must be exercised against decomp.wtf fork mode before real stubs are written, because retrofitting touches every source file.
- The objdiff and decomp.wtf seams are spikes with fallbacks (KKND compare; minimal own agent layer ~5-9 days), so neither can block the gate.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-plan-phase --research-phase N`):
- **Phase 4:** wibo 1.2.0 x each Watcom version, real 10.5 binary extraction, flag grid, per-module version mixing — untested on these binaries.
- **Phase 5:** highest risk — LE loader choice (lastonesky vs retrokit, neither tried on bound DOS/4GW Pro), objdiff behavior on converted ELF (symbol sizes, sections, FLAT-group fixups), unit-boundary heuristics (only two `__FILE__` strings), stub convention.
- **Phase 6:** decomp.wtf fork-mode fit (archived, where its build runs: WSL2 vs our Docker), Nigel fit and its Go build approval, recomp.fyi acceptance of a hand-built report.

Phases with standard patterns (skip research-phase):
- **Phase 3:** KKND splice is well understood, LE edge cases are already measured, and the work is stdlib + pytest; plan directly from PITFALLS 1-3.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Pins HIGH (in repo); fitness MEDIUM — TH/KKND production use but nothing run on UFO2P/TACP; retrokit and capstone cp314 wheels LOW |
| Features | MEDIUM-HIGH | Gates come from `docs/workflow.md` (owner decisions); effort figures are note estimates |
| Architecture | HIGH (oracle) / MEDIUM (seams) | Copies two working Watcom/LE pipelines; OMF->objdiff and fork-mode seams untested |
| Pitfalls | MEDIUM-HIGH | Local scan facts (trailer, straddling fixups, physical pages) HIGH; incident reports multi-source; inference-flagged items LOW |

**Overall confidence:** MEDIUM

### Gaps to Address

- **27-byte trailer origin** (wlink/binder/DOS4GW artefact): unknown; treat opaque in Milestone 1, record in docs in Phase 3.
- **wibo compatibility for 10.5 and 11.0:** Phase 4 spike with native-vs-wibo cross-check.
- **objdiff on OMF-converted ELF:** Phase 5 spike, time-boxed, with a Phase 4 library function as the known-good pair.
- **Unit-boundary heuristics:** only `source\grafix.c` and `source/pixlpath.c` embedded — Phase 5 open design point.
- **Stub convention vs decomp.wtf fork mode:** toy-repo test in Phase 5, confirmed by the Phase 6 spike.
- **Where decomp.wtf's build runs** (WSL2 pins vs ninja wrapping `docker compose run`): Phase 6 spike.
- **recomp.fyi acceptance of a hand-built report** and artifact-name parsing: unverified; treat as best-effort.
- **Repo visibility:** Pages on a private repo needs a paid plan; listings need public — settle before Phase 6 reporting.
- **capstone cp314 wheels:** check before `uv lock` in Phase 5.
- **Nigel:** Go build step needs owner approval; ~200-line Python fallback.
- **Bind-mount I/O speed on Docker Desktop:** measure one compile->verify cycle in Phase 4; consider a named volume for `build/` or a WSL2-filesystem clone.

## Sources

### Primary (HIGH confidence)
- Repo: `docker/Dockerfile`, `docker/compose.yaml`, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`, `tools/reverseapoc/le.py`, `tests/test_le.py`, `tests/test_le_real.py`, `configure.py`, `config/targets.toml`, `.gitignore`, `.claude/rules/*.md` — pins, existing behavior, gaps.
- `docs/workflow.md`, `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`, `docs/tools.md` — owner decisions, gates, spikes, hook table.
- Local scan facts (2026-10-19) — 27-byte trailer, physical pages only, 14/11 straddling off32 fixups, idiom counts.

### Secondary (MEDIUM confidence)
- `docs/research/2026-10-19-kickoff-research-report.md` — pipeline shape, verdicts, risks.
- `docs/research/notes-own-pipeline-reuse-inventory.md` — KKND/TH/retrokit inventories, splice vs rewrite effort.
- `docs/research/notes-target-binary-and-toolchain.md` — mosura probe, version-pinning methods, damaged 10.5 stub.
- `docs/research/notes-automation-loops.md`, `notes-blogs-and-reference-repos.md` — Lewis/Macabeus/Mizuchi incidents, `/goal`, Nigel.
- `docs/research/notes-decompwtf-rea-ghidra-ida.md`, `notes-progress-reporting-recompfyi.md`, `notes-repo-infra-docker-standards.md`, `notes-vector-retrieval-bsim.md`, `notes-skills-plugins-frameworks.md`.
- `docs/toolchain.md`, `docs/matching.md`, `docs/coding-style.md`, `docs/ceremonies.md`, `docs/learnings.md`.

### Tertiary (LOW confidence)
- retrokit 0.2.0 fitness (6 days old, synthetic validation only), Nigel fit, lx-loader README "unbound" claim (contradicted locally), inference-flagged items in PITFALLS.md (plugin token cost, bind-mount speed, OMF header nondeterminism).

Detailed files: `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md`.

---
*Research completed: 2026-10-19*
*Ready for roadmap: yes*
