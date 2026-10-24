# ReverseApoc design

- **Date:** 2026-10-19
- **Status:** approved plan for Milestone 1; Phases 1-2 detailed, Phases 3-6 planned later with GSD.
- **Amendment 2026-10-21 [Owner]:** Milestone 1 extended with Phase 7 (mechanics-first decompilation) and Phase 8 (clean-room specs for OpenApoc, OpenSpec format, CC0-1.0). See [workflow.md](../../workflow.md#milestone-1-roadmap) and [clean-room.md](../../clean-room.md). The text below is the plan as approved on 2026-10-19.
- **Sources:** the [kickoff research report](../../research/2026-10-19-kickoff-research-report.md), the eight research notes in [docs/research/](../../research/), the owner's kickoff brief and the approved plan.

Every decision below is tagged:

- **[Owner]**: decided by the project owner.
- **[Default]**: chosen by Claude during research and planning, accepted with the plan, and open to change without a new decision from the owner.

## Intent and why

ReverseApoc produces a 100% byte-matching decompilation of X-COM: Apocalypse (1997, DOS): readable C that, compiled with the original Watcom toolchain, rebuilds UFO2P.EXE and TACP.EXE byte for byte. **[Owner]**

Why:

- The OpenApoc reimplementation needs to know how the original really works: its logic, mechanics and bugs, the enemy AI above all. A matching decomp is the most trustworthy source for that, because the compiler proves every function. **[Owner]**
- It is a proof of concept for AI-assisted reverse engineering with Claude Code. **[Owner]**
- The research showed why the oracle matters more than the agent: every successful AI decomp stood on a deterministic verifier, and every documented failure came from an agent judging itself. So the design puts the trustworthy oracle first and treats the agent layer as replaceable. **[Default]**

## Goals

1. A reproducible, containerized build that rebuilds both executables byte-identically from the user's own files (Phases 2-3).
2. The exact compiler version and flags, proven by library and codegen matching (Phase 4).
3. Matched C functions, each verified by objdiff, relocation checks and a whole-EXE SHA-1, readable and commented for OpenApoc readers (Phase 5 onward).
4. A per-function agent loop that matches easy functions unattended with zero regressions (Phase 6 pilot: 10 functions).
5. Public, self-hosted progress (mosaic, badge, raw JSON) and directory listings (recomp.fyi, decomphub.com).

## Non-goals

- Making the game run on modern systems.
- Supporting the Win9x release, SMKP.EXE (Smacker player, deferred), XCOMAPOC.EXE (16-bit launcher) or SETUP.EXE in Milestone 1.
- Competing with or replacing OpenApoc. ReverseApoc serves it.
- Claiming to be the first Watcom or X-COM decomp; it is the closest found.

## Anti-goals

Things the project must actively avoid:

- **A playable port.** No platform layer, no SDL, no "just fix this while we are here". **[Owner]**
- **A modern C++ rewrite.** The source is C89 for Watcom 10.x; modern C++ idioms break matching. **[Default]**
- **Committing any game bytes.** No executables, assets, disassembly or compiler binaries in git, in Docker image layers or in issues. **[Owner]**
- **Agents judging their own matches.** The driver and the build decide; agents cannot edit `orig/`, hash manifests or build scripts. **[Default]**

## Constraints

- **Host:** Windows 10 with WSL2 Ubuntu and Docker Desktop. No cmake, make, ninja, clang or Ghidra on the host, so everything build-related runs in Docker; Ghidra runs headless in the Docker image (owner decision 2026-10-23, D-04) and decomp.wtf runs in WSL2. **[Owner]** (Docker and WSL2), **[Default]** (the split)
- **Python 3.14 pin**, moving to 3.15 with a one-line change once dependencies have wheels. **[Owner]**
- **GPLv3 for `tools/`**, so Theme Hospital's modules can be copied with their headers. decomp.wtf (MIT) stays a separate tool run as a subprocess, never imported. **[Owner]**
- **User-supplied Watcom compiler** under gitignored `third_party/watcom/`, mounted read-only, never in an image. Same for the game under `orig/`. **[Owner]** (bring your own files), **[Default]** (mount layout)
- **No IDA.** Its decompiler is cloud-based and the owner wants analysis to stay local **[Owner]**; it also cannot load LE files, so it is dropped entirely rather than kept as a last resort **[Default]**.
- **Steam preferred, GOG fallback**; they are byte-identical for the executables. DOS release only. **[Owner]**
- **GitHub issues** as the tracker. **[Owner]**
- **Claude Code only** as the agent runtime for now; skills and GSD are installed for the Claude runtime only. **[Owner]**

## Decisions made

| Decision | Tag | Rationale |
|---|---|---|
| **Hybrid pipeline:** our own matching oracle (Watcom 10.x under wibo in Docker, `configure.py` + ninja, LE splitter, in-place page splice, whole-EXE SHA-1, OMF-to-ELF for objdiff) plus decomp.wtf v0.10.6 fork mode as the agent layer | [Owner] | decomp.wtf has no LE/Watcom path, but its fork mode accepts any `configure.py` + ninja + `objdiff.json` repo; the hybrid buys its agent layer for about 3-7 extra days instead of 12-24 to build one |
| Fallback if objdiff cannot diff OMF-converted ELF cleanly: own pipeline plus a minimal agent layer (MCP, claims, guardrails, Claude Code only) | [Default] | Decided by the Phase 5 spike |
| Reuse KKND-Decomp (CC0) for LE reading, splice and discovery; Theme Hospital (GPLv3) for `omf2elf.py` and the build pattern; retrokit (Apache-2.0) as an external analysis tool | [Default] | Closest existing Watcom/DOS/4GW pipelines; about 13-24 developer-days for the oracle |
| **GSD for milestones and phases**, Milestone 1 = Phases 1-6 below, each with a verification gate | [Owner] | Durable phase state, `VERIFICATION.md` gates, `/gsd-spike` |
| **superpowers inside phases** (brainstorming, TDD on tooling, verification before completion); GSD's files are the record when both prescribe a step | [Owner] | Avoids two systems giving competing instructions |
| Install the enabled plugins at project scope rather than trimming the list | [Owner] | Settings enabled seven plugins but only one was installed |
| **Phases 1-6 with gates** (hygiene, container and ingest, round trip, compiler ID, split and first matches, reporting and pilot) | [Owner] (structure), [Default] (gate wording) | Byte-identical rebuild before any decompiling (Abahbob; Theme Hospital's final `cmp`) |
| Watcom 10.6 (10.5 equivalent) as the compiler hypothesis; Open Watcom only for `wdis`/`wlink`/`wlib` | [Default] | Banner and codegen evidence; settled in Phase 4 |
| C89 with `wcc386` by default; `wpp386` per file if a module proves to be C++ | [Default] | Source-file strings and no C++ runtime traces |
| In-place page splice for the MVP instead of a full LE rewrite | [Default] | Byte-identical by construction for unmatched bytes; 1-3 days instead of 10-20+ |
| **Progress self-hosted**: treemap SVG, shields endpoint JSON and `progress.json` on GitHub Pages, built by Actions on push to `main` | [Default] | decomp.dev closed to new projects; recomp.fyi renders no badge |
| **recomp.fyi listing** via `.recomp.json` and **decomphub.com** submission via its reviewed form once the repo is public | [Owner] | Visibility in the directories that are still open |
| Per-function driver running one `claude -p "/goal ..."` per function, 3-5 attempt cap with re-queue, driver re-verifies bytes; evaluate Nigel first | [Default] | Lewis's results and Macabeus's benchmark; `/goal`'s evaluator cannot run tools |
| Similarity retrieval without ML first (opcode Levenshtein, twin matching UFO2P to TACP); embeddings later | [Default] | Corpus is a few thousand functions; Lewis dropped embeddings for coddog-style matching |
| Ghidra 12.1.4 + lastonesky ghidra-lx-loader or retrokit, GhidraMCP 2.0 headless under Python 3.13 | [Default] | The only maintained LE loaders for Ghidra 12.1 |

## Architecture overview

```
your Steam/GOG install --ingest--> orig/ (ro) --+
your Watcom 10.x -------------> third_party/ (ro)+--> Docker build image
                                                 |     wibo + wcc386 -> OMF -> omf2elf -> ELF
                                                 |     LE splitter -> target ELF objects
                                                 |     objdiff + relocation check
                                                 |     in-place splice -> whole-EXE SHA-1
                                                 |
Docker: Ghidra + LE loader (headless) ----------+--> function list, drafts, names
WSL2: decomp.wtf fork mode (subprocess) --------+--> claims, agents, dashboard
driver (claude -p "/goal ...") ------------------+--> re-verify, commit one function
GitHub Actions --> progress.svg / progress.json / shield JSON on Pages, report artifact for recomp.fyi
```

## What is left to the builder

These were deliberately not decided; the phase that needs each one decides it, using GSD's discuss and plan steps.

- **Exact LE writer strategy (Phase 3).** In-place splice is the default, but how to verify headers, page map and fixup tables, and whether a full Theme Hospital style rewrite is ever needed (for shiftable or relinkable builds), is open. Unknowns: iterated or zero pages and non-internal fixups in UFO2P/TACP, both of which the borrowed readers reject today.
- **OMF-to-ELF details (Phase 5).** How to cut per-unit target ELF objects from the LE with relocations built from LE fixups; section and symbol naming that objdiff and decomp.wtf fork mode accept; handling of COMDAT, FLAT-group fixups and Watcom inline switch tables; how the extra-relocation check is wired in.
- **Scorer design (Phase 6).** Features and weights for easiest-first, when to switch to similarity-first, how twin functions between the two EXEs and library-matched runtime functions are prioritised, and how the difficult list is re-queued.
- **Hook implementation (Phase 6).** Which Claude Code hook events, the exact path and pattern lists (hash manifests, build scripts, `orig/`, inline asm and code-emitting pragmas), how decomp.wtf's own guardrails and ours coexist, and how the driver detects usage limits and backs off.
- **Also open:** the stub convention for unmatched functions in Watcom units (decomp.wtf expects GNU-asm `INCLUDE_ASM`); the compat header path and `__WATCOMC__` value; the progress file names on Pages; whether Nigel or a Python driver wins.

## Risks to watch

From the report's risk table: the UFO2P CRC mismatch with OpenApoc's reference build; Watcom version mixing across modules; objdiff and OMF; legal sourcing of the compiler; community reception of AI decomps; reward hacking and subscription budget; C vs C++ not fully proven; toolchain version drift (GhidraMCP needs Python <= 3.13, Ghidra 12.1 broke loader APIs). Mitigations are in the [report](../../research/2026-10-19-kickoff-research-report.md#risks-and-open-questions) and in [workflow.md](../../workflow.md).
