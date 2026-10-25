---
id: SEED-261025-q3c
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: "Milestone 2: early steps any time, verdict after 100%"
scope: medium
---

# SEED-261025-q3c: Diff other editions against our build (technical wrapper or real behaviour change?)

## Why This Matters

The owner wants to know whether other distributions differ only in wrappers and technical details, or also in fixes, game logic or patches that change behaviour. The Learning AI is reported to work only on some editions.

## What Research Found (2026-10-25)

**No native Windows build is documented.** No source found describes a Win32 PE executable:
- The US box lists DOS 5.0, Windows 95 and Windows 3.1 requirements for one product, so Windows 95 is a compatibility note.
- MobyGames' "2008 Windows" date is the Steam/DOSBox release.
- An OpenApoc Discord recollection says the Win9x version is an installer wrapper.

**What UFOpaedia calls the "Windows 95" build is a second DOS/4GW LE build, and our v1.00 disc already has it.** The disc's `UFO2P.EXE`/`TACP.EXE` (CRC32 `0x4749FFC1`/`0xFEBBE39E`) sit beside the "4" builds that are installed under the plain names (module names `ufo24`/`tac4`); see `docs/toolchain.md`. JonnyH found the two builds differ only by the Watcom `-4` scheduling flag, with identical data I/O. That is still to be proven.

**Editions with a sourced behaviour difference:**
- UK/EU original CD, serial **MP191 207 D01R**.
- Power Plus, **PP191 207D01R**.
- "North American 1.03": no patch file or changelog was found.

The difference reported for these is the Learning AI, which may depend on the disc layout rather than different code. No source reports logic differences for the localized discs (German, Spanish, Brazilian Portuguese) or for X-COM Collection.

**It is not abandonware.** The game is on sale on Steam and GOG (Take-Two), so an ISO from an abandonware site is infringement. A used retail disc bought second-hand (eBay) is a legitimate source.

## Plan

1. **Free first.** Diff the disc's v1.00 builds against the installed "4" builds. This is v2 requirement CD-01 ("CD v1.00 builds as a second matching target"). Once our build is fully matched, most functions should compile from the same C with different flags, and the leftovers are the real differences.
2. **Then, if worth it:** buy a UK original disc (MP191 207 D01R, or Power Plus as second choice). Hash its `UFO2P*.EXE`/`TACP*.EXE` against `config/targets.toml` before assuming the code differs. Diff the data files (`TACDATA/*.DAT`) and their layout too.
3. **Optional:** localized discs, mostly text and data diffs. Hash first.

Rules: no game bytes from any edition are committed. Hashes go into the manifest under the existing rules.

## When to Surface

**Trigger:** Milestone 2 (layout in [[SEED-261025-l4y]]):
- **Any time:** hash a bought disc, and diff functions against the v1.00 builds as they match.
- **After 100%:** the verdict.

## Scope Estimate

**Medium.** Step 1 reuses the matching tooling with new flags. Step 2 depends on getting a disc.

## Breadcrumbs

- `docs/toolchain.md` (the CD v1.00 table) and `config/targets.toml` (the `[[cd_builds]]` entries).
- `.planning/REQUIREMENTS.md`: v2 CD-01, and the Out of Scope row "Win9x release, XCOMAPOC.EXE, SETUP.EXE".
- UFOpaedia "Game versions and builds (Apocalypse)" (rev 115696), "Known Bugs (Apocalypse)" (rev 124000) and "Cut items and features (Apocalypse)" (rev 117358).
- https://elisoftware.org/wiki/X-COM:_Apocalypse_(PC,_CD-ROM)_Microprose_-_1997_USA,_Canada_Release
