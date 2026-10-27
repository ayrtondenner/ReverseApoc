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
- ✓ Byte-identical round trip: `uv run reverseapoc rebuild` / `ninja verify` reassemble UFO2P.EXE, TACP.EXE and SMKP.EXE from a byte-region map and page-mapped object images, `cmp`/SHA-1 identical to `orig/` on the host and in the container. The `splice(le, {va: bytes})` API refuses unwritable or overlapping patches and masks fixup fields, and negative tests prove the gate fails on a one-byte change. RT-01..RT-05 — Phase 3 (plans 03-01..03-10, VERIFICATION passed 87/87, UAT 2026-10-21)
- ✓ Compiler identification: the 10.6 runtime library (CLIB3R/MATH3R) matches byte for byte (masked) in UFO2P.EXE and TACP.EXE; the codegen probe finds its idioms in both EXEs' own code; `wcc386` (C, not C++) confirmed; `reverseapoc cc` runs 10.5/10.6/11.0 under wibo with a per-file flags table; version and flags recorded per EXE with evidence in `docs/toolchain.md`. Game code: 10.6 preferred, 10.5 first fallback, 11.0 candidate; `-4r -s -fpi` baseline, other flags carried as candidates for Phase 5 (accepted by override, D-08/D-10). CID-01..CID-06 — Phase 4 (plans 04-01..04-13, VERIFICATION passed 26/26, UAT 2026-10-23)
- ✓ Split and first matches: Ghidra 12.1.4 with the lastonesky LE loader runs headless in the image; a capstone pass cross-checks its function list, with hand verdicts for the 7 boundaries the LE evidence does not decide; `functions.csv` and `units.csv` per EXE (841 units); `INCLUDE_ASM` stubs; `omf2elf.py`; target ELFs cut from LE fixups; an independent relocation check; `configure.py` -> ninja + `objdiff.json`; clang C89 lint; `check` and land. func_000A3980 (UFO2P) and func_00055080 (TACP) match under `wcc386@10.6 -4r -s -fpi`: objdiff 100%, relocation check passed, both EXEs SHA-1 identical. SPL-01..SPL-13 — Phase 5 (plans 05-01..05-20, VERIFICATION passed with 1 owner override, UAT 2026-10-24)
- ✓ Reporting and agent pilot: self-hosted progress on GitHub Pages (per-EXE bars, function strips with partial scores, labelled mosaic, per-EXE shields, progress.json, CI-built report.json); two-layer guardrail hooks; our own stdlib per-function driver (`reverseapoc drive`, attempt wrapper, context packs, `watcom-decomp` skill) after spike 006 invalidated decomp.wtf fork mode; recomp.fyi listed and claimed, DecompHub submitted. The pilot matched 3 functions in 40 sessions with zero regressions (owner-accepted partial; AGT-11 stays open and the 10-match target carries to Phase 7). RPT-01..05, AGT-01..10 — Phase 6 (plans 06-01..06-27, VERIFICATION passed, UAT 3/3 2026-10-26)

### Active

- [ ] Pilot target: 10 functions matched unattended with zero regressions (AGT-11, 3/10 at Phase 6 close; carried into Phase 7)
- [ ] Mechanics-first decompilation: every function behind the OpenApoc checklist items the decomp can answer matched, named and commented by the driver at scale; readability lint (Phase 7)
- [ ] Clean-room specs for OpenApoc: OpenSpec-format spec per mechanic with template, `speclint`, `wikifetch`, `apoc-spec` skill, claim inventory and owner review, under CC0-1.0 (Phase 8)

### Out of Scope

- Making the game run on modern systems / a playable port (no platform layer, no SDL) — anti-goal [Owner]
- A modern C++ rewrite — C89 for Watcom 10.x; modern idioms break matching [Default]
- Committing any game bytes (executables, assets, disassembly, compiler binaries) in git, image layers or issues — anti-goal [Owner]
- Agents judging their own matches; agents editing `orig/`, hash manifests or build scripts — anti-goal [Default]
- The Win9x release, SMKP.EXE (Smacker player, deferred), XCOMAPOC.EXE (16-bit launcher), SETUP.EXE (Borland) in Milestone 1 — non-goal
- Competing with or replacing OpenApoc — ReverseApoc serves it
- Claiming to be the first Watcom or X-COM decomp — it is the closest found
- IDA — cloud decompiler and no LE loader [Owner]/[Default]
- Contacting OpenApoc about the specs or sending them specs or PRs in Milestone 1 — [Owner, 2026-10-21]

## Context

- **Targets (installed build, primary):** UFO2P.EXE 1,705,790 bytes, sha1 `e7488bf3…7c56`; TACP.EXE 3,161,594 bytes, sha1 `48ef0096…7393`. Both bound with DOS/4GW Professional: 217,764-byte extender, Watcom MZ stub at 0x352A4, LE header at 0x37F34, 2 objects (code at 0x10000, data at 0xD0000 / 0xE0000), 4 KiB pages. A second build (CD v1.00, inside the disc image both stores ship) is the one OpenApoc's offsets describe; it is recorded under `[[cd_builds]]` for cross-reference. Phase 3 spike 003 found that the installed executables are byte-identical to the disc's `XCOM3/UFOEXE/UFO2P4.EXE` and `XCOM3/TACEXE/TACP4.EXE`, and that every one of these builds ends in an opaque 27-byte record after the last LE page, which the rebuild carries unchanged.
- **Compiler (Phase 4):** Watcom C 10.6 runtime proven byte for byte in both EXEs; game code built with `wcc386` (C, not C++), 10.6 preferred, 10.5 byte-identical on the probe (first fallback), 11.0 tied at `-4r` (candidate). Baseline flags `-4r -s -fpi`; the `__CHK` functions (40 in UFO2P, 32 in TACP) were built without `-s`. The first Phase 5 matches settle 10.6 vs 10.5/11.0, `-4` vs `-5` and `-o*` (see `docs/toolchain.md` "Fallbacks and candidates"). Open Watcom does not match classic 10.x and is used only for `wdis`/`wlink`/`wlib`.
- **Reuse:** KKND-Decomp (CC0) for LE reading, in-place splice, discovery; Theme Hospital decomp (GPLv3) for `omf2elf.py` and the configure/ninja pattern; retrokit (Apache-2.0) as an external analysis tool. `tools/` is GPLv3.
- **Prior art for the oracle-first design:** every successful AI decomp in the research stood on a deterministic verifier; every documented failure (rewritten hashes, false match claims, permuter overfitting) came from an agent judging itself.

## Constraints

- **Host**: Windows 10 + WSL2 Ubuntu + Docker Desktop; no cmake/make/ninja/clang/Ghidra on the host, so builds and the headless Ghidra export run in Docker and decomp.wtf in WSL2 — [Owner] (Docker, WSL2; Ghidra in the image, 2026-10-23), [Default] (split)
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
| Hybrid pipeline: own matching oracle (Watcom 10.x under wibo in Docker, configure.py + ninja, LE splitter, in-place splice, whole-EXE SHA-1, OMF-to-ELF for objdiff) + decomp.wtf v0.10.6 fork mode as agent layer [Owner] | decomp.wtf has no LE/Watcom path but fork mode accepts any configure.py + ninja + objdiff.json repo; ~3-7 extra days vs 12-24 to build an agent layer | ✗ Revised (spike 006 INVALIDATED, 06-01, b3b4636): unpatched fork mode stops at its own setup with no build in WSL2, and even with a build it would keep the `INCLUDE_ASM` stub next to the new C, which our D-12 check refuses, so Phase 6 builds its own agent layer (D-03, D-04); decomp.wtf is not looked at again in Phase 7: spike 006 stands (D-06, 2026-10-26); Phase 7 runs N sessions in one checkout on private views (D-24). The own matching oracle half stands |
| Fallback if objdiff cannot diff OMF-converted ELF: own pipeline + minimal agent layer [Default] | Decided by the Phase 5 spike | ✓ Not needed (spike 005 VALIDATED: objdiff pairs omf2elf output with the LE-cut target; its 2nd-relocation blind spot is covered by our own relocation check) |
| Reuse KKND-Decomp (CC0), Theme Hospital (GPLv3), retrokit (Apache-2.0) [Default] | Closest existing Watcom/DOS/4GW pipelines; ~13-24 developer-days for the oracle | ✓ Good (KKND le.py lifted in Phase 2) |
| GSD for milestones and phases; Milestone 1 = Phases 1-6, each with a verification gate [Owner]; extended to Phases 1-8 [Owner, 2026-10-21] | Durable phase state, VERIFICATION.md gates, /gsd-spike | — Pending |
| superpowers inside phases; GSD's files are the record when both prescribe a step [Owner] | Avoids two systems giving competing instructions | — Pending |
| Plugins installed at project scope rather than trimming the list [Owner] | Settings enabled seven plugins but only one was installed | ✓ Good |
| Phases with gates, byte-identical rebuild before any decompiling [Owner] (structure), [Default] (gate wording) | Abahbob; Theme Hospital's final cmp | — Pending |
| Watcom 10.6 (10.5 equivalent) hypothesis; Open Watcom only for wdis/wlink/wlib [Default] | Banner and codegen evidence; settled in Phase 4 | ✓ Good (Phase 4: 10.6 runtime byte-identical; game code 10.6 preferred with 10.5/11.0 kept as fallbacks until the first Phase 5 matches, owner override 2026-10-22) |
| C89 with wcc386 by default; wpp386 per file if a module proves C++ [Default] | Source-file strings, no C++ runtime traces | ✓ Good (Phase 4 C vs C++ scan: `wcc386` for both EXEs) |
| In-place page splice for the MVP instead of a full LE rewrite [Default] | Byte-identical by construction for unmatched bytes; 1-3 days vs 10-20+ | ✓ Good (Phase 3: three EXEs rebuild SHA-1 identical; full rewrite reopens only if a matched function changes size, LE-01) |
| The 27 bytes after the last LE page stay opaque and are carried unchanged (D-10) [Owner] | Spike 003: a structured record (u16 value/complement pairs) also on the 1997 CD builds, not a checksum, bind record or install stamp | ✓ Good (Phase 3) |
| Phase 3 review findings deferred: WR-01, WR-03, WR-08, IN-12 to Phase 5; WR-04 to Phase 6 [Owner, 2026-10-20/21]; brought forward and fixed before Phase 4 [Owner, 2026-10-21] | They matter once real patches flow through `splice()` (Phase 5) or the driver reads `--json` (Phase 6) | ✓ Good (fixed 2026-10-21 with TDD; 03-REVIEW-DISPOSITION.md open: 0, all 21 findings fixed) |
| Progress self-hosted on GitHub Pages (treemap SVG, shields JSON, progress.json) [Default] | decomp.dev closed to new projects; recomp.fyi renders no badge | ✓ Good (Phase 6: Pages live from CI on every push; owner UAT 2026-10-26 desktop/phone, light/dark; phone mosaic legibility deferred to backlog 999.4) |
| recomp.fyi listing via .recomp.json and decomphub.com submission once public [Owner] | Visibility in directories still open | ✓ Done (recomp.fyi listed and claimed 2026-10-25; DecompHub submitted 2026-10-24, pending review) |
| Per-function driver: one `claude -p "/goal ..."` per function, 3-5 attempt cap with re-queue, driver re-verifies bytes; evaluate Nigel first [Default] | Lewis's results, Macabeus's benchmark; /goal's evaluator cannot run tools | ✓ Good, revised (Phase 6: own stdlib driver, Nigel rejected (D-05); only the driver's container gate decides a match; pilot 3 matches in 40 sessions, about USD 14 per match, zero regressions; partial accepted by the owner 2026-10-26) |
| Similarity retrieval without ML first (opcode Levenshtein, UFO2P-TACP twins) [Default] | Corpus is a few thousand functions | — Pending |
| Ghidra 12.1.4 + lastonesky ghidra-lx-loader or retrokit, GhidraMCP 2.0 headless under Python 3.13 [Default]; lastonesky v12.1.4-1 chosen, Ghidra + openjdk-21-jdk-headless baked into the Docker image, SHA-pinned [Owner, 2026-10-23] | Only maintained LE loaders for Ghidra 12.1; lastonesky has no 12.2 build; in the image no developer installs Ghidra or a JDK by hand (Apache-2.0 / GPLv2+CE, unlike the user-supplied Watcom and game) | ✓ Good (Phase 5: exports UFO2P 1408 / TACP 1498 functions; image 898,389,257 bytes after the D-20 strip, accepted by the owner 2026-10-24; GhidraMCP not needed yet) |
| Target cuts leave a branch or off32 field into no `functions.csv` row raw (listed in `raw_fields`) instead of refusing the unit as 05-08 planned [Owner override, 2026-10-24] | The refusal left 18 of 842 units uncuttable on the first real ninja run; the relocation check still fails such a field, so no false match is possible | ✓ Good (all 841 units cut with raw fields none at HEAD) |
| capstone 5.0.9 as the first runtime dependency, installed by `uv sync --locked` into the venv volume, not baked into the image [Owner, 2026-10-24] | A second boundary list independent of Ghidra (SPL-02) | ✓ Good |
| Phase 5 UAT follow-ups: fix the `asm` listing collision on ambiguous runtime names (`_Alphabet`) in Phase 6; readlint must also reject our own `func_`/`D_` placeholders in Phase 7 [Owner, 2026-10-24] | Agents rely on `asm/` from Phase 6; Phase 7 criterion 4 names only Ghidra's `FUN_`/`sub_`/`DAT_` | ◐ Partly done: 999.3 closed by 06-06 (a56080d, 6d535c1); 999.2's SC4 wording added by 06-21 (80e9c17), and readlint itself is Phase 7 (999.2 stays open) |
| Primary target is the installed build; CD v1.00 build recorded for cross-reference [Default] | What players run; OpenApoc offsets describe the CD build; revisit after Phase 5 | ✓ Decided (D-42, owner 2026-10-24, DI-32): the installed build (`UFO2P4.EXE`/`TACP4.EXE`) stays primary; CD v1.00 is for cross-reference only; OpenApoc offsets are re-located by signature when Phase 7 needs them; twin matching of CD v1.00 is revisited after Phase 7 |
| Milestone 1 phases numbered 1-6 [Owner, 2026-10-19] | GSD phase ids start at 1 | ✓ Good |
| Add Phase 7 (mechanics-first decomp) and Phase 8 (clean-room specs) to Milestone 1; Phase 6 keeps its 10-function pilot gate; specs use the OpenSpec format, not the tool; specs are CC0-1.0; no OpenApoc contact during Milestone 1 [Owner, 2026-10-21] | Only about 12 leaf functions are matched by the end of Phase 6, so mechanics must be decompiled before they can be specced; CC0 lets OpenApoc (GPL-3.0) use spec text without attribution; clean room needs the author/implementer split (see `docs/clean-room.md`) | — Pending |
| Phase 5 context deferrals (DI-09): no Ghidra GUI guide in Phase 6; the `-zp`/`-zm`/`-fp` and 11.0a/b flag sweeps run only if a pilot miss needs them; GhidraMCP stays "Later (Phase 7 or later)" [Owner, 2026-10-24, D-41] | The pilot needs neither a GUI guide nor extra sweeps unless a function fails to match under the default rule; the context pack is built by our own `context` command (D-13) | — Pending (Phase 6 pilot) |

## Left to the builder (decided in the phase that needs it)

- ~~Exact LE writer strategy and header/page-map/fixup verification; whether a full rewrite is ever needed (Phase 3)~~ Settled in Phase 3: in-place splice through `splice(le, {va: bytes})` with fixup masking; a full rewrite reopens only if a matched function changes size (LE-01)
- ~~OMF-to-ELF details: per-unit target ELF objects from LE fixups, section/symbol naming, COMDAT, FLAT-group fixups, inline switch tables, extra-relocation check (Phase 5)~~ Settled in Phase 5: `omf2elf.py`, `target.py` and `relocs.py`; `check` refuses jump-table functions until Phase 7 (IN-02)
- ~~Scorer design (Phase 6); hook implementation (Phase 6)~~ Settled in Phase 6 (D-05..D-29): the scorer reuses `score.assess` with status awareness (D-09); the hooks are stdlib Python in `tools/reverseapoc/hooks.py`, in two layers (D-15..D-18)
- ~~Stub convention for unmatched functions in Watcom units; compat header path and `__WATCOMC__` value~~ Settled in Phase 5: `INCLUDE_ASM(func_XXXXXXXX)` in `include/common.h`, `include/watcom_compat.h`, and the lint defines `__WATCOMC__` to the build version
- ~~Progress file names; Nigel vs Python driver (Phase 6)~~ Settled in Phase 6 (D-05..D-29): `config/<exe>/status.csv`, `progress/attempts.jsonl`, CI-built report.json and the committed `decomphub.progress.json` (D-20, D-23, D-28, D-29); our own stdlib Python driver `tools/reverseapoc/driver.py` with a `reverseapoc drive` verb; Nigel is rejected (D-05)

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
*Last updated: 2026-10-26 after Phase 6 (verification passed, UAT passed 3/3; pilot 3/10 accepted as partial)*
