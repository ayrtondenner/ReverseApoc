# Toolchain

What the targets are, what built them, and what each part of our toolchain does. Facts marked "local scan" come from read-only Python scans of the Steam install on 2026-10-19. Everything else cites the research notes in [research/](research/). Items marked **to be confirmed in Phase 4** (or another phase) are hypotheses, not facts.

## Targets

Steam and GOG installs are byte-identical for the game executables (local scan).

| File | Size (bytes) | md5 | Module name | CRC32 | Entry point | Scope |
|---|---:|---|---|---|---|---|
| `UFOEXE/UFO2P.EXE` | 1,705,790 | `d2e874a76344cb9c48afce57357aab31` | `ufo24` | `0xDBD3B41D` | obj1:0xB0784 | Target |
| `TACEXE/TACP.EXE` | 3,161,594 | `644382a6caa787cff613c50a170b5152` | `tac4` | `0x3EC9C268` | obj1:0xB28B0 | Target |
| `UFOEXE/SMKP.EXE` | 271,436 | `2d7933f255348a60536d811391b461ba` | `SMKP` | `0x93A0E620` | obj1:0x6CB0 | Deferred (Smacker player, v2 requirement SMKP-01) |
| `XCOMAPOC.EXE` | 18,171 | `867f7997fae1714313b873f15359c4fb` | n/a | n/a (not ingested) | n/a | Out of scope (16-bit launcher) |

- SHA-1 values are recorded in `config/targets.toml` (Phase 2).
- `SETUP.EXE` is Borland C++ 1991 and out of scope.
- The two targets have separate module names, which suggests separate link scripts. Expect two decomp targets with largely shared engine code, possibly compiled with slightly different flags.

### OpenApoc CRC mismatch (resolved 2026-10-19)

OpenApoc's extractor expects UFO2P.EXE CRC32 `0x4749ffc1` ("the crc32 of the ufo2p.exe found on my steam version", [ufo2p.cpp](https://github.com/OpenApoc/OpenApoc/blob/master/tools/extractors/common/ufo2p.cpp), added 2016-11-05). OpenApoc reads game files from the CD image (`data/cd.iso`, see its [README](https://github.com/OpenApoc/OpenApoc/blob/master/README.md)), not from the installed folder. Hashing the executables inside the Steam `cd.iso` and the GOG `CD/XCOM.BIN` (MODE1/2352, converted to 2048-byte sectors) shows two builds of each program, both available to every Steam and GOG owner:

| Build | File | Size (bytes) | CRC32 | md5 | sha1 |
|---|---|---:|---|---|---|
| CD v1.00 (inside the disc image, `XCOM3/UFOEXE/`) | UFO2P.EXE | 1,702,206 | `0x4749FFC1` | `2345cd4d39807fadaff36792f622466d` | `6be861d611548f5a00b0b3bc49a82ed29d25fd4a` |
| CD v1.00 (`XCOM3/TACEXE/`) | TACP.EXE | 3,170,298 | `0xFEBBE39E` | `cf329277d52968ec26b408caa2856600` | `af32ccc371c153c514fb8e3cc80e765de380aef9` |
| Installed (`XCOMA/` on Steam, root on GOG) | UFO2P.EXE | 1,705,790 | `0xDBD3B41D` | `d2e874a76344cb9c48afce57357aab31` | `e7488bf3de2efeaa3c1c72d3763eeeb35f727c56` |
| Installed | TACP.EXE | 3,161,594 | `0x3EC9C268` | `644382a6caa787cff613c50a170b5152` | `48ef00969d8880a0a152de1b652853fa7ac27393` |

SMKP.EXE and XCOMAPOC.EXE are identical in both places. The Steam ISO and the GOG disc image contain byte-identical files. The disc's README.TXT says "Version 1.00, 11th June 1997"; the installed executables are a later build applied by the store installers (the exact patch level is unknown; a build-to-build diff after Phase 5 may date it). Consequences:

- OpenApoc's table offsets and the `FUN_` addresses in its PRs describe the **CD build**. They are not valid for the installed build without re-deriving them.
- The project's primary target stays the **installed build** (what players run, what `uv run reverseapoc ingest` collects). The CD build is recorded in `config/targets.toml` under `[[cd_builds]]` for cross-reference and as a second, smaller matching target once the pipeline exists. Which build becomes primary is an owner decision to revisit after Phase 5.
- A build-to-build diff (same compiler, small source delta) is a cheap source of matching evidence in later phases.

## LE layout

All three 32-bit EXEs are LE executables bound with DOS/4GW Professional (local scan).

| Fact | UFO2P.EXE | TACP.EXE |
|---|---|---|
| Bound DOS/4GW Pro kernel | first 217,764 bytes (LE program's MZ stub at 0x352A4) | same |
| LE header offset | 0x37F34 | 0x37F34 |
| Objects | 2 | 2 |
| obj1 (code) | base 0x10000, vsize 0xBFADD, flags 0x2045 | base 0x10000, vsize 0xC254F |
| obj2 (data, includes BSS) | base 0xD0000, vsize 0x181E20, flags 0x2043 | base 0xE0000, vsize 0x25F0B0 |
| Page size | 4096 | 4096 |
| Debug info | none (offset and length 0) | none |
| Non-resident name table | empty | empty |
| Overlays | none; page data runs exactly to EOF | same |

- SMKP.EXE differs: stub at 0x26654 (157,268 bytes of extender), LE header at 0x292E4, obj1 base 0x10000 (vsize 0x11380), obj2 base 0x30000 (vsize 0xFA70). Its DOS/4GW blob has a different size, so it was bound separately.
- No symbol names come for free. Naming relies on RE, OpenApoc knowledge and string references.
- Mapping objects at their preferred bases keeps community Ghidra addresses (`FUN_000xxxxx`, `0x0016xxxx`) usable, once the build question above is settled.
- Not yet checked: iterated or zero pages, non-internal fixups, 16:16 fixups. KKND's and Theme Hospital's readers both raise on these. **To be confirmed in Phase 2/3.**
- The lx-loader README lists "X-Com: Apocalypse (UFO2P.EXE - DOS/16 LE and unbound LE-style)" as tested (a line inherited from upstream). That conflicts with the local scan, which shows a bound DOS/4GW Pro file. **To be checked in Phase 5.**

## Compiler

### Evidence

- Each 32-bit EXE carries two Watcom banners: `WATCOM C/C++16 Run-Time system ... 1988-1994` (in the 16-bit DOS/4GW part) and `WATCOM C/C++32 Run-Time system ... 1988-1995` (in the 32-bit program), plus Rational Systems copyrights (local scan).
- Banner dating ([mosura watcom-detection](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-detection.md)): 10.5, 10.6 and 11.0/11.0A/11.0B all ship the same `1988-1995` banner. The banner excludes only 10.0/10.0a.
- Codegen fingerprint ([mosura codegen fingerprint](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-codegen-fingerprint.md)):

| Construct | 10.5 / 10.6 | 11.0 | Open Watcom 2.0 |
|---|---|---|---|
| `return c == 5;` on a byte | `cmp al,5; sete al; and eax,0FFh` | `cmp al,5; jne ...; mov eax,1` (branch, no setcc) | `cmp al,5; sete al; movzx eax,al` |
| Counted loop bound register | `ebx` | `ecx` | `ecx` |
| Switch compare order | ascending | ascending | descending |

- Whole-file idiom counts (local scan, runtime library included): `setcc al; and eax,0FFh` appears 33 times in UFO2P and 61 times in TACP; `setcc al; movzx eax,al` once in each; the 10.0a-only "promote then `cmp eax,imm`" idiom 0 times.
- Theme Hospital (1997) settled on 10.6, found 10.5/10.5a/10.6 identical on what it tested, and saw 11.0 match only 2 of 10 demo functions ([MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md)).
- Open Watcom does not match classic 10.x: it "threads jumps on conditions it can prove on loop entry, and it lays out loops differently. No flag tested fixes this" ([KKND COMPILER_ANALYSIS.md](https://github.com/Wyrelade/KKND-Decomp/blob/main/COMPILER_ANALYSIS.md)). KKND now patches OW's `wcc386` to work around it.

### Hypothesis

**Watcom C 10.6, with 10.5 as an equivalent.** 11.0 is less likely but not excluded by the banner. Open Watcom will not match and is used only for auxiliary tools. **To be confirmed in Phase 4** by:

1. compiling the mosura probe with owner-supplied 10.5, 10.6 and 11.0 and looking for its idioms in UFO2P's code object;
2. matching the linked CLIB3R/MATH3R runtime modules byte for byte against each version's `LIB386`, NHL95PC-style ([NHL95PC](https://github.com/abdulahmad/NHL95PC)).

Modules may mix versions (Theme Hospital used 10.0a for some CRT modules), so the build keeps `compiler@version` per file.

### Flags

Not known yet; CID-05 (Phase 4) records them here. References from other Watcom games, not evidence for ours:

| Project | Compiler | Flags |
|---|---|---|
| KKND | patched OW `wcc386` (10.0/10.0a target) | `-s -of+ -5r -omiler -zm -zp1` |
| Theme Hospital | `wpp386` 10.6 | `-s -ot -d2 -zm` |
| NHL95PC | 10.0 GA | `-5r -fpi -zp1` |

Starting candidates for our scratches: `-5r` or `-4r`, `-s`, an `-o*` subset, `-zp1` or `-zp4`.

### C, not C++

All evidence points to C compiled with `wcc386` (local scan):

- UFO2P embeds `source\grafix.c` (next to PCX-loading error strings) and `source/pixlpath.c` (next to `rawdata/pixlpath.pcx`). TACP contains neither.
- Neither binary contains Watcom C++ mangling (`W?...`), `__wcpp_` runtime symbols, "pure virtual" strings or RTTI strings.
- The `assertion "%s" failed` string lives in the DOS/4GW extender region, not the game.

The binaries are stripped, so missing symbols alone are weak evidence. **To be confirmed in Phase 5:** scan obj2 for vtables, obj1 for `__wcpp_` routines and for XI/YI static-init segments. Keep `wpp386` available per file, because Theme Hospital found that `wcc386` "generates different code for the same source" when the original was C++.

## What the Docker image contains, and what you supply

The image is built locally and never pushed with proprietary bytes in it.

| In the image (Phase 2) | Supplied by you (gitignored, mounted read-only) | Outside the container |
|---|---|---|
| Python 3.14 + uv (image tag pinned) | `third_party/watcom/`: Watcom 10.5/10.6 (and 11.0 for the probe), mounted at `/work/watcom:ro` | Ghidra 12.1.4 + JDK 21 in WSL2 Ubuntu |
| ninja | `orig/`: UFO2P.EXE and TACP.EXE from your install, mounted at `/work/orig:ro` | decomp.wtf v0.10.6 in WSL2, its own venv (Python 3.12+) |
| clang-format, clangd | `.env`: install paths and API keys | GhidraMCP under `uvx --python 3.13` |
| binutils (`as`) | | retrokit via pipx (if chosen over lastonesky's loader) |
| `objdiff-cli` (pinned release binary) | | |
| wibo 1.2.0 (`COPY --from=ghcr.io/decompals/wibo:1.2.0`, as decomp.me's cromper does) | | |
| Open Watcom v2 Linux build (`wdis`, `wlink`, `wlib` only) | | |

Watcom 10.x/11.0 is proprietary and its current IP owner was not verified, so it is never baked into an image layer. Open Watcom's licence permits redistribution, but it cannot match.

## Tools in detail

### decomp.me

decomp.me's `msdos` platform offers `wcc10.0a`, `wcc10.5`, `wcc10.5a`, `wcc10.6` and `wcc11.0`, plus the `wpp` C++ equivalents ([compilers.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/compilers.py)). It runs `binnt/wcc386.exe` under wibo. Try `wcc10.6` and `wcc10.5` first, then `wcc11.0`. Whether `-zm` and `-d2` can be typed as custom flags is unverified.

### Ghidra and loaders

- **Ghidra 12.1.4** (2026-09-21). Stock Ghidra has no LE loader and no `__watcall` ([ghidra#532](https://github.com/NationalSecurityAgency/ghidra/issues/532), [ghidra#156](https://github.com/NationalSecurityAgency/ghidra/issues/156)).
- **lastonesky ghidra-lx-loader v12.1.4-1** (2026-10-10): supports 12.1.x and ships a Watcom cspec with `__watcall` ([release](https://github.com/lastonesky/ghidra-lx-loader/releases/tag/v12.1.4-1)). Upstream yetmorecode v12.0.1 targets 12.0 and breaks on the 12.1 loader API.
- **retrokit** (Apache-2.0): its own LE loader, `watcom`/`watcomreg` cspec auto-detection, Open Watcom library signatures, function export and an MCP server ([nemo22/retrokit](https://github.com/nemo22/retrokit)). Exported sizes are Ghidra body counts and need post-processing into contiguous ranges.
- Pick one loader per Ghidra install. Neither has been tested on UFO2P or TACP. **Decided in Phase 5.**

### GhidraMCP

LaurieWired GhidraMCP 2.0 (2026-10-10) supports Ghidra 12.1.4 and has a GUI-less `--headless` PyGhidra mode. That mode needs Python 3.10-3.13, so run it with `uvx --python 3.13` while the project stays on 3.14 ([GhidraMCP](https://github.com/LaurieWired/GhidraMCP)).

### objdiff and the OMF bridge

- objdiff cannot read OMF. Issue [#97](https://github.com/encounter/objdiff/issues/97) has been open since 2024-08-19; a WIP `omf` branch dates from 2025-09-25; v3.8.2 (2026-09-29) reads ELF and COFF only.
- Bridge: Theme Hospital's `omf2elf.py` (GPLv3, about 590 lines) converts Watcom OMF to ELF32, including COMDAT, LIDATA, FIXUPP threads and BAKPAT. Theme Hospital runs objdiff-cli 3.8.1 through it.
- objdiff compares at most one relocation per x86 instruction, so Theme Hospital's `elfrelocs.py`/`verify.py` check the rest.
- Target objects for objdiff are cut from the LE, with relocations built from LE fixups (Phase 5).
- Fallback: KKND-style compare (cut each function from its OMF object, mask relocations, check their targets), which avoids objdiff entirely. **The Phase 5 spike decides.**

### wibo

wibo 1.2.0 runs the Win32-hosted `BINNT\wcc386.exe` on Linux ([decompals/wibo](https://github.com/decompals/wibo)). Older wibo (nixpkgs 0.6.14) cannot run Watcom ("Unhandled function LocalAlloc"). Watcom treats `/` as an option switch and splits paths on spaces: decomp.me rewrites `/` to `\`, and KKND compiles from relative paths under `build/tmp`. The BINNT binaries also run natively on the Windows host, which helps debugging. **Running every 10.x version under wibo in Docker is a Phase 4 spike.**

### Open Watcom v2

Used for `wdis`, `wlink` and `wlib` only, as Theme Hospital does. Never for matching.

### Python

Pinned to 3.14 for host and container parity. Python 3.15.0 shipped on 2026-10-09; the move is a one-line change once dependencies have wheels. 3.15 makes UTF-8 the default encoding, so tools always pass `encoding=` explicitly when reading DOS-era files (latin-1 or CP437).

## Version pins

| Component | Version | Status |
|---|---|---|
| Python | 3.14 (`.python-version`) | Phase 2 |
| uv | 0.12.23 on the host and in the image (`ghcr.io/astral-sh/uv:0.12.23`) | Phase 2 |
| wibo | 1.2.0 | Phase 2 |
| objdiff-cli | v3.8.2 (sha256-pinned in `docker/Dockerfile`) | Phase 2 |
| Open Watcom v2 | `2026-10-01-Build` (sha256-pinned in `docker/Dockerfile`) | Phase 2 |
| Watcom C | 10.6 / 10.5 hypothesis | Phase 4 |
| Ghidra | 12.1.4 + JDK 21 | Phase 5 |
| ghidra-lx-loader | lastonesky v12.1.4-1 (or retrokit) | Phase 5 |
| GhidraMCP | 2.0, headless, Python 3.13 | Phase 5 |
| decomp.wtf | v0.10.6 (archived) | Phase 6 |
