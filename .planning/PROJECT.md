# ReverseApoc

## What This Is

ReverseApoc is a byte-matching decompilation of X-COM: Apocalypse (DOS, 1997): readable C89 that, compiled with the original Watcom 10.x toolchain, rebuilds the DOS/4GW LE executables UFO2P.EXE (cityscape, module `ufo24`) and TACP.EXE (tactical, module `tac4`) byte for byte. It exists to document how the original engine really works (logic, mechanics, bugs, above all the enemy AI) for the OpenApoc reimplementation, and as a proof of concept for AI-assisted reverse engineering with Claude Code. It is not a port.

Source of truth for every decision: `docs/superpowers/specs/2026-10-19-reverseapoc-design.md` (design spec), `docs/workflow.md` (Milestone 1 roadmap and gates), `docs/toolchain.md` (targets, LE layout, compiler evidence), `CLAUDE.md` (hard rules). The research behind them is in `docs/research/`.

## Core Value

Every match is proven by a deterministic oracle (rebuilt EXE SHA-1 identical to the original, objdiff 100% for the function), never by an agent's own judgement.

## Requirements

### Validated

- ✓ Repo hygiene: game files, disassembly, build output and secrets never tracked; plugins at project scope; lean CLAUDE.md; docs skeleton, README, `.recomp.json`, design spec — Phase 1 (built before GSD was set up, commits `d7d4d65`…`e50784f`)
- ✓ Container and target ingest: Docker image (uv, ninja, objdiff-cli, wibo, Open Watcom v2 tools), hash manifest `config/targets.toml`, `reverseapoc ingest | check-orig | parse-le`, LE parser with 75 pytest tests green on host, in the container and in CI — Phase 2 (built before GSD was set up, commits `29f9327` and `8418027`)

### Active

- [ ] Byte-identical round trip: KKND-style in-place page splice rebuilds UFO2P.EXE and TACP.EXE with `cmp`/SHA-1 identical to `orig/` (Phase 3)
- [ ] Compiler identification: exact Watcom version and default flags proven by the mosura codegen probe and a CLIB3R/MATH3R library match (Phase 4)
- [ ] Split and first matches: Ghidra + LE loader, `omf2elf.py`, function split, `configure.py` -> ninja + `objdiff.json`; one function per EXE matched, relocation-checked, spliced, whole EXE identical (Phase 5)
- [ ] Reporting and agent pilot: self-hosted progress (mosaic, badge, JSON on Pages), guardrail hooks, decomp.wtf fork mode, per-function driver; 10 easy functions matched unattended with zero regressions; recomp.fyi and decomphub listings (Phase 6)

### Out of Scope

- Making the game run on modern systems / a playable port (no platform layer, no SDL) — anti-goal [Owner]
- A modern C++ rewrite — C89 for Watcom 10.x; modern idioms break matching [Default]
- Committing any game bytes (executables, assets, disassembly, compiler binaries) in git, image layers or issues — anti-goal [Owner]
- Agents judging their own matches; agents editing `orig/`, hash manifests or build scripts — anti-goal [Default]
- The Win9x release, SMKP.EXE (Smacker player, deferred), XCOMAPOC.EXE (16-bit launcher), SETUP.EXE (Borland) in Milestone 1 — non-goal
- Competing with or replacing OpenApoc — ReverseApoc serves it
- Claiming to be the first Watcom or X-COM decomp — it is the closest found
- IDA — cloud decompiler and no LE loader [Owner]/[Default]

## Context

- **Targets (installed build, primary):** UFO2P.EXE 1,705,790 bytes, sha1 `e7488bf3…7c56`; TACP.EXE 3,161,594 bytes, sha1 `48ef0096…7393`. Both bound with DOS/4GW Professional: 217,764-byte extender, Watcom MZ stub at 0x352A4, LE header at 0x37F34, 2 objects (code at 0x10000, data at 0xD0000 / 0xE0000), 4 KiB pages. A second build (CD v1.00, inside the disc image both stores ship) is the one OpenApoc's offsets describe; it is recorded under `[[cd_builds]]` for cross-reference.
- **Compiler hypothesis:** Watcom C 10.6 (10.5 equivalent), C not C++ (`wcc386`); 11.0 not excluded by the banner. Open Watcom does not match classic 10.x and is used only for `wdis`/`wlink`/`wlib`.
- **Reuse:** KKND-Decomp (CC0) for LE reading, in-place splice, discovery; Theme Hospital decomp (GPLv3) for `omf2elf.py` and the configure/ninja pattern; retrokit (Apache-2.0) as an external analysis tool. `tools/` is GPLv3.
- **Prior art for the oracle-first design:** every successful AI decomp in the research stood on a deterministic verifier; every documented failure (rewritten hashes, false match claims, permuter overfitting) came from an agent judging itself.

## Constraints

- **Host**: Windows 10 + WSL2 Ubuntu + Docker Desktop; no cmake/make/ninja/clang/Ghidra on the host, so builds run in Docker and Ghidra/decomp.wtf in WSL2 — [Owner] (Docker, WSL2), [Default] (split)
- **Python**: 3.14 pinned (`.python-version`), managed with uv; move to 3.15 is a one-line change — [Owner]
- **License**: GPLv3 for `tools/`; decomp.wtf (MIT) stays a subprocess, never imported — [Owner]
- **Bring your own files**: Watcom compiler under gitignored `third_party/watcom/`, game under gitignored `orig/`, both mounted read-only, never in an image — [Owner]/[Default]
- **Sources**: Steam preferred, GOG fallback (byte-identical executables), DOS release only — [Owner]
- **Tracker**: GitHub issues — [Owner]
- **Agent runtime**: Claude Code only; skills and GSD installed for the Claude runtime only, at project scope — [Owner]
- **Matching discipline**: a matched function is byte-identical and stays that way; no restructuring, no inline assembly to force a match — CLAUDE.md
- **Done gate**: tooling = tests and ruff green, in the container too; decompiled code = rebuilt EXE SHA-1 identical and objdiff 100% for the function — CLAUDE.md

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid pipeline: own matching oracle (Watcom 10.x under wibo in Docker, configure.py + ninja, LE splitter, in-place splice, whole-EXE SHA-1, OMF-to-ELF for objdiff) + decomp.wtf v0.10.6 fork mode as agent layer [Owner] | decomp.wtf has no LE/Watcom path but fork mode accepts any configure.py + ninja + objdiff.json repo; ~3-7 extra days vs 12-24 to build an agent layer | — Pending |
| Fallback if objdiff cannot diff OMF-converted ELF: own pipeline + minimal agent layer [Default] | Decided by the Phase 5 spike | — Pending |
| Reuse KKND-Decomp (CC0), Theme Hospital (GPLv3), retrokit (Apache-2.0) [Default] | Closest existing Watcom/DOS/4GW pipelines; ~13-24 developer-days for the oracle | ✓ Good (KKND le.py lifted in Phase 2) |
| GSD for milestones and phases; Milestone 1 = Phases 1-6, each with a verification gate [Owner] | Durable phase state, VERIFICATION.md gates, /gsd-spike | — Pending |
| superpowers inside phases; GSD's files are the record when both prescribe a step [Owner] | Avoids two systems giving competing instructions | — Pending |
| Plugins installed at project scope rather than trimming the list [Owner] | Settings enabled seven plugins but only one was installed | ✓ Good |
| Phases with gates, byte-identical rebuild before any decompiling [Owner] (structure), [Default] (gate wording) | Abahbob; Theme Hospital's final cmp | — Pending |
| Watcom 10.6 (10.5 equivalent) hypothesis; Open Watcom only for wdis/wlink/wlib [Default] | Banner and codegen evidence; settled in Phase 4 | — Pending |
| C89 with wcc386 by default; wpp386 per file if a module proves C++ [Default] | Source-file strings, no C++ runtime traces | — Pending |
| In-place page splice for the MVP instead of a full LE rewrite [Default] | Byte-identical by construction for unmatched bytes; 1-3 days vs 10-20+ | — Pending |
| Progress self-hosted on GitHub Pages (treemap SVG, shields JSON, progress.json) [Default] | decomp.dev closed to new projects; recomp.fyi renders no badge | — Pending |
| recomp.fyi listing via .recomp.json and decomphub.com submission once public [Owner] | Visibility in directories still open | — Pending |
| Per-function driver: one `claude -p "/goal ..."` per function, 3-5 attempt cap with re-queue, driver re-verifies bytes; evaluate Nigel first [Default] | Lewis's results, Macabeus's benchmark; /goal's evaluator cannot run tools | — Pending |
| Similarity retrieval without ML first (opcode Levenshtein, UFO2P-TACP twins) [Default] | Corpus is a few thousand functions | — Pending |
| Ghidra 12.1.4 + lastonesky ghidra-lx-loader or retrokit, GhidraMCP 2.0 headless under Python 3.13 [Default] | Only maintained LE loaders for Ghidra 12.1 | — Pending |
| Primary target is the installed build; CD v1.00 build recorded for cross-reference [Default] | What players run; OpenApoc offsets describe the CD build; revisit after Phase 5 | — Pending |
| Milestone 1 phases numbered 1-6 [Owner, 2026-10-19] | GSD phase ids start at 1 | ✓ Good |

## Left to the builder (decided in the phase that needs it)

- Exact LE writer strategy and header/page-map/fixup verification; whether a full rewrite is ever needed (Phase 3)
- OMF-to-ELF details: per-unit target ELF objects from LE fixups, section/symbol naming, COMDAT, FLAT-group fixups, inline switch tables, extra-relocation check (Phase 5)
- Scorer design (Phase 6); hook implementation (Phase 6)
- Stub convention for unmatched functions in Watcom units; compat header path and `__WATCOMC__` value; progress file names; Nigel vs Python driver

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-19 after initialization (GSD set up after Phases 1-2 were built; both verified retroactively)*
