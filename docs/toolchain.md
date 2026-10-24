# Toolchain

What the targets are, what built them, and what each part of our toolchain does. Facts marked "local scan" come from read-only Python scans of the Steam install on 2026-10-19. Everything else cites the research notes in [research/](research/). Items marked **to be confirmed in Phase N** are hypotheses, not facts.

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

SMKP.EXE and XCOMAPOC.EXE are identical in both places. The Steam ISO and the GOG disc image contain byte-identical files. The disc's README.TXT says "Version 1.00, 11th June 1997". The installed executables are not a patch added by the store installers: both builds are pressed on the 1997 disc. The disc also carries `XCOM3/UFOEXE/UFO2P4.EXE` and `XCOM3/TACEXE/TACP4.EXE`, which are byte-identical to the installed UFO2P.EXE and TACP.EXE (trailer spike, [`.planning/spikes/003-trailer/`](../.planning/spikes/003-trailer/README.md), Investigation Trail step 4), and their module names are `ufo24` and `tac4`. So the installer copies the "4" build under the plain names; its copy rule was not traced (probably inside a compressed archive). Which of the two builds is newer, and what changed between them, is unknown; a build-to-build diff after Phase 5 may tell. Consequences:

- OpenApoc's table offsets and the `FUN_` addresses in its PRs describe the **CD build**. They are not valid for the installed build without re-deriving them.
- The project's primary target stays the **installed build** (what players run, what `uv run reverseapoc ingest` collects). The CD build is recorded in `config/targets.toml` under `[[cd_builds]]` for cross-reference and as a second, smaller matching target once the pipeline exists. Which build becomes primary is an owner decision to revisit after Phase 5.
- A build-to-build diff (same compiler, small source delta) is a cheap source of matching evidence in later phases.

## LE layout

All three 32-bit EXEs are LE executables bound with DOS/4GW Professional (local scan). The facts below were confirmed on 2026-10-20 with an independent raw reader by the LE edge-case spike ([`.planning/spikes/001-le-pages-and-fixups/`](../.planning/spikes/001-le-pages-and-fixups/README.md) and [`.planning/spikes/002-le-region-tiling/`](../.planning/spikes/002-le-region-tiling/README.md)) and the trailer spike ([`.planning/spikes/003-trailer/`](../.planning/spikes/003-trailer/README.md)). `tests/test_splice_real.py` pins them as real-file tests.

| Fact | UFO2P.EXE | TACP.EXE | SMKP.EXE |
|---|---|---|---|
| Bound DOS/4GW Pro kernel | first 217,764 bytes (LE program's MZ stub at 0x352A4): an MZ loader followed by two BW modules | same | first 157,268 bytes (stub at 0x26654): an MZ loader followed by one BW module |
| LE header offset | 0x37F34 | 0x37F34 | 0x292E4 |
| Objects | 2 | 2 | 2 |
| obj1 (code) | base 0x10000, vsize 0xBFADD, flags 0x2045 | base 0x10000, vsize 0xC254F | base 0x10000, vsize 0x11380 |
| obj2 (data, includes BSS) | base 0xD0000, vsize 0x181E20, flags 0x2043 | base 0xE0000, vsize 0x25F0B0 | base 0x30000, vsize 0xFA70 |
| Page size | 4096 | 4096 | 4096 |
| Pages | 303, all physical, identity page map | 666, all physical, identity page map | 21, all physical, identity page map |
| Fixups (off32 / sel16 / ptr16:32 / rel32) | 28,183 / 10 / 4 / 0, all internal | 24,424 / 10 / 4 / 0, all internal | 2,297 / 0 / 0 / 0, all internal |
| Page-straddling fields | 14 off32, all in obj1 | 11 off32, all in obj1 | 2 off32, all in obj1 |
| Field cut by the end of page data | off32 at 0x13E27C in obj2: 3 bytes backed, 1 in BSS | off32 at 0x2B6538 in obj2: 3 backed, 1 in BSS | off32 at 0x32FF6 in obj2: 2 backed, 2 in BSS |
| obj1 page bytes past vsize | 0x523, all zero | 0xAB1, all zero | 0xC80, all zero |
| Debug info | none (offset and length 0) | none | none |
| Non-resident name table | empty | empty | empty |
| Bytes after the last page | 27 bytes at 0x1A0723, starts `64 00 9B FF`, sha1 `33a69cacf0a929fa9a104844a933273b4d0e4ee0` | 27 bytes at 0x303DDF, starts `64 00 9B FF`, sha1 `28ad5c4593a0080fd58cd8a627a996472e68fa34` | none (the pages run to the end of the file) |

- SMKP.EXE's DOS/4GW blob has a different size (one BW module instead of two), so it was bound separately.
- No symbol names come for free. Naming relies on RE, OpenApoc knowledge and string references.
- Mapping objects at their preferred bases keeps community Ghidra addresses (`FUN_000xxxxx`, `0x0016xxxx`) usable, once the build question above is settled.
- Edge cases (LE edge-case spike): every page is physical and the page map is the identity (303 / 666 / 21 pages), so the iterated and zero pages that KKND's and Theme Hospital's readers raise on do not occur. Every fixup is internal: off32 / sel16 / ptr16:32 counts are 28,183 / 10 / 4, 24,424 / 10 / 4 and 2,297 / 0 / 0, with no rel32, no other kind (no byte, off16 or 16:16 fixups) and no import, additive or chained records. 14 / 11 / 2 off32 fields straddle a 4 KiB page boundary and are listed on both pages. One off32 field per file is cut by the short last page of obj2, with 3 / 3 / 2 bytes backed by the page and the rest in BSS. The declared loader section includes the fixup section (both end at the same offset). 362 / 403 / 223 bytes of zero padding sit between the fixup section and the pages. obj1's page bytes past its vsize (0x523 / 0xAB1 / 0xC80) are all zero, and the rebuild carries them anyway.
- The 27 bytes after the last page (trailer spike, verdict partial): they are a structured record, with u16 value/complement pairs at trailer offsets 0, 4 and 8, and the 1997 CD builds carry one too. They are not any tested checksum or CRC of the file, pages or objects, not a DOS/4GW bind record (SMKP.EXE is bound the same way and has none) and not an install-time stamp. What they mean is unknown. The table gives their offset, length, first 4 bytes and SHA-1 only. The rebuild carries them unchanged as their own region, and nothing regenerates them.

Byte-region map. Every byte of each file lies in exactly one region; the boundaries come from the file's own LE header (half-open file offsets):

| Region | UFO2P.EXE (1,705,790 bytes) | TACP.EXE (3,161,594 bytes) | SMKP.EXE (271,436 bytes) |
|---|---|---|---|
| extender (MZ loader + BW modules) | [0x0, 0x352A4) | [0x0, 0x352A4) | [0x0, 0x26654) |
| MZ stub | [0x352A4, 0x37F34), 11,408 bytes | [0x352A4, 0x37F34), 11,408 bytes | [0x26654, 0x292E4), 11,408 bytes |
| LE header | [0x37F34, 0x37FF8), 196 bytes | [0x37F34, 0x37FF8), 196 bytes | [0x292E4, 0x293A8), 196 bytes |
| loader tables | [0x37FF8, 0x384EE), 1,270 bytes | [0x37FF8, 0x38A99), 2,721 bytes | [0x293A8, 0x29435), 141 bytes |
| fixup section | [0x384EE, 0x7233A), 237,132 bytes | [0x38A99, 0x6A711), 203,896 bytes | [0x29435, 0x2D375), 16,192 bytes |
| padding (all zero) | [0x7233A, 0x724A4), 362 bytes | [0x6A711, 0x6A8A4), 403 bytes | [0x2D375, 0x2D454), 223 bytes |
| pages 1..N | [0x724A4, 0x1A0723) | [0x6A8A4, 0x303DDF) | [0x2D454, 0x4244C) |
| trailer | [0x1A0723, 0x1A073E), 27 bytes | [0x303DDF, 0x303DFA), 27 bytes | none |

`uv run reverseapoc rebuild` (or `ninja verify` in the container) rebuilds `build/<NAME>` from exactly these regions, with each page placed through the page map, and checks the whole-file SHA-1 against `config/targets.toml`.
- The lx-loader README lists "X-Com: Apocalypse (UFO2P.EXE - DOS/16 LE and unbound LE-style)" as tested (a line inherited from upstream). That conflicts with the local scan, which shows a bound DOS/4GW Pro file. **To be checked in Phase 5.**

## Compiler

### Evidence

- Each 32-bit EXE carries two Watcom banners: `WATCOM C/C++16 Run-Time system ... 1988-1994` (in the 16-bit DOS/4GW part) and `WATCOM C/C++32 Run-Time system ... 1988-1995` (in the 32-bit program), plus Rational Systems copyrights (local scan).
- Banner dating ([mosura watcom-detection](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-detection.md)): 10.5, 10.6 and 11.0/11.0A/11.0B all ship the same `1988-1995` banner. The banner excludes only 10.0/10.0a.
- Codegen fingerprint, the published reference ([mosura codegen fingerprint](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-codegen-fingerprint.md)). Our own clean-room probe (`probe/cg_basic.c`, plan 04-08) reproduced the byte-compare row but not the register row: on our counted loop 10.6 kept the bound in `ecx` and 11.0 in `ebx`, so register choice depends on the construct and is not used as evidence. Switch compare order did not separate 10.6 from 11.0 on our probe either (one ascending chain in both). Every idiom we use is calibrated from our own probe objects instead (`uv run reverseapoc probe calibrate`, see [probe/README.md](../probe/README.md)).

| Construct | 10.5 / 10.6 | 11.0 | Open Watcom 2.0 |
|---|---|---|---|
| `return c == 5;` on a byte | `cmp al,5; sete al; and eax,0FFh` | `cmp al,5; jne ...; mov eax,1` (branch, no setcc) | `cmp al,5; sete al; movzx eax,al` |
| Counted loop bound register | `ebx` | `ecx` | `ecx` |
| Switch compare order | ascending | ascending | descending |

- Idiom counts in **non-library** code (every runtime row of `config/<exe>/runtime.csv` excluded, every LE fixup byte masked; `uv run reverseapoc probe scan <EXE>`, plan 04-10). The 2026-10-19 whole-file counts (33 / 61 `and`-form hits) included the runtime library.

| Idiom | UFO2P | TACP |
|---|---:|---:|
| non-library / runtime-row code bytes | 741,159 / 43,958 | 749,928 / 46,055 |
| `setcc al; and eax,0FFh` (setcc_and) | 30 | 58 |
| `setcc al; movzx eax,al` (setcc_movzx) | 0 | 0 |
| unrolled `movsd` runs (movsd_unrolled) | 75 | 35 |
| `mov ecx,1..16` .. `rep movsd`, register moves between (rep_movsd_small) | 4 | 2 |
| rotated / top-tested loops (byte level, not decisive) | 357 / 194 | 262 / 223 |
| ascending / descending switch chains (eax/al compares only, not decisive) | 10 / 7 | 12 / 10 |
| `push imm32; call __CHK` | 40 | 32 |

- Theme Hospital (1997) settled on 10.6, found 10.5/10.5a/10.6 identical on what it tested, and saw 11.0 match only 2 of 10 demo functions ([MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md)).
- Open Watcom does not match classic 10.x: it "threads jumps on conditions it can prove on loop entry, and it lays out loops differently. No flag tested fixes this" ([KKND COMPILER_ANALYSIS.md](https://github.com/Wyrelade/KKND-Decomp/blob/main/COMPILER_ANALYSIS.md)). KKND now patches OW's `wcc386` to work around it.

### Result

Phase 4 measured each EXE separately (D-09). The game-code compiler comes from the codegen probe and the linked runtime library from the library match; they are reported separately (D-07), and ties are written as ties (D-10). Measured 2026-10-21 on the owner's trees (10.5 with the decoded compiler, 10.6, 11.0).

| | UFO2P (`ufo24`) | TACP (`tac4`) | Evidence |
|---|---|---|---|
| Game-code compiler | **Watcom C 10.6** (10.5 byte-identical on the probe), with **11.0 tied at `-4r`** on the decisive idioms | same as UFO2P | `probe calibrate`: 10.5 and 10.6 give the same object in all 10 flag sets (`tie:` lines). `probe scan`: 18 of 30 calibration cells consistent, the same 18 in both EXEs: eight 10.5 and the same eight 10.6 cells, plus 11.0 `-4r -s` and 11.0 `-4r -s -ox`. No `-3r` cell (no `movzx` form) and no 11.0 `-5` cell (11.0 branches at `-5`) is consistent. |
| Linked runtime library | **10.6**, no mix | **10.6**, no mix | `libmatch` summary (and `config/<exe>/runtime.csv`): 11 rows match only 10.6 in each EXE, every other row lists 10.6 too (UFO2P: 58 in all three versions, 51 in 10.5+10.6, 1 in 10.6+11.0; TACP: 62, 57, 2), and no row matches only 10.5 or only 11.0. The 10.6-only modules: chk8087, cinit, close, efgfmt, ftell, ftos, grownear, initargv, memalloc, prtf, sprintf. |
| Runtime libraries | DOS/CLIB3R.LIB (106 rows), MATH387R.LIB (15), MATH3R.LIB (1), DOS/EMU387.LIB (1), DOS/GRAPH.LIB (1) | DOS/CLIB3R.LIB (113), MATH387R.LIB (19), MATH3R.LIB (1), DOS/EMU387.LIB (1), DOS/GRAPH.LIB (1) | `libmatch` summary. A row lists every library holding the same body, so the NT/, OS2/, WIN/ and NETWARE/ copies of a CLIB module are not separate evidence. The 3S rows (CLIB3S 16, MATH387S 3, MATH3S 1) all list a 3R library too: `probe scan` "calling convention" counts 3S-only rows as 0. |
| Library-match coverage | 121 ranges, 43,958 of 785,117 code bytes (5.60%); 14 ambiguous | 132 ranges, 46,055 of 795,983 code bytes (5.79%); 12 ambiguous | `libmatch` summary; committed as `config/ufo2p/runtime.csv` and `config/tacp/runtime.csv`. An ambiguous row names its alternative module, and its publics may include the alternative's names, so Phase 5 treats them as candidates. |
| C or C++ | `C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 5 vtable-shaped candidate runs` | `C (wcc386): ...` the same, with 3 vtable-shaped candidate runs | `cppscan` verdict line; see [C, not C++](#c-not-c) |

Reading the result:

- **10.5 vs 10.6.** Byte-identical on every probe cell, so the probe cannot separate them and no time is spent on it (D-10). The default rule names 10.6 because it is the version consistent with both the probe and the linked runtime library.
- **10.6 vs 11.0.** At `-4r` both emit the `and`-form byte compare and the `rep movsd` struct copy, so the decisive idioms tie. The probe's counted loop separates them (10.x rotates it, 11.0 tests at the top), but the game has both loop shapes (rotated / top-tested 357 / 194 in UFO2P, 262 / 223 in TACP; byte-level counts, and `-oneatx` removes both shapes on the probe), so loop shape is not decisive. 11.0 stays a **candidate, evidence pending: the first Phase 5 matches**. What separates them: a game function that compiles byte-identical under `wcc386@10.6` and not under `wcc386@11.0` with the same flags (or the reverse). **11.0a and 11.0b were not swept** (D-02 admits them only if 11.0 turns out to be a candidate): 11.0 is only a codegen tie at `-4r`, while the linked runtime is 10.6 with zero 11.0-only rows, so sweeping its point releases would not change the result now. They are swept if the first Phase 5 matches favour 11.0 over 10.6; their trees (`third_party/watcom/11.0a`, `11.0b`) and `config/watcom.toml` entries already exist. The 10.6-only runtime modules say the game was linked against the 10.6 library; that is library evidence, not game-code evidence (D-07).
- The consistent-cell list reads only the decisive idiom families (byte compare and struct copy). The other evidence lines contradict two of its cells: `-5s -s` (no 3S-only runtime row) and `-5r -s -fpi87` (an EMU387 row, see Flags). The `-5r` cells stay in the list only because both EXEs show both struct-copy shapes; the sized struct-copy count below speaks against `-5`.

How to reproduce (the logs live in `build/gate/04-evidence/`, gitignored; they hold counts, addresses, names and hashes only):

1. `uv run reverseapoc check-watcom 10.5 10.6 11.0` (every key file OK; older installs first run `uv run reverseapoc install-watcom 10.5 --force`)
2. `uv run reverseapoc libmatch UFO2P.EXE` and `uv run reverseapoc libmatch TACP.EXE` (summary at the end; `--write` regenerates `config/<exe>/runtime.csv`, and refuses unless every swept version loads an OMF library, since the map does not record which versions were swept)
3. `uv run reverseapoc probe calibrate --output build/probe/calibration.json`
4. `uv run reverseapoc probe scan UFO2P.EXE --calibration build/probe/calibration.json`, then `TACP.EXE`
5. `uv run reverseapoc cppscan UFO2P.EXE`, then `TACP.EXE`

Modules may still mix versions (Theme Hospital used 10.0a for some CRT modules), so the build keeps `compiler@version` per file and Phase 5 overrides the default per glob where a match says so.

### Flags

Per-flag evidence for each EXE (D-08, D-09). "Proven (scan)" means a whole-binary scan of non-library code shows it; the `-o*`, `-zp*`, `-zm` and `-fp3`/`-fp5` candidates need matched functions.

| Flag | UFO2P | TACP | Evidence | Status |
|---|---|---|---|---|
| Calling convention: `-3r`/`-4r`/`-5r` (register) vs `-3s`/`-5s` (stack) | register (`r`) | register (`r`) | `probe scan` "calling convention": rows only in 3R libraries 102 / 113, only in 3S libraries 0 / 0, in both 18 / 18 (shared asm modules) | proven (scan) |
| Stack checks: `-s` | `-s` for most code; 40 functions without it, `__CHK` calls in block 0x00010000 (37) and 0x000b0000 (3) | `-s` for most code; 32 functions without it, block 0x00010000 (26) and 0x000b0000 (6) | `probe scan` "stack checks": each `push imm32; call __CHK` is one function built without `-s` (the probe emits one per function without `-s` and none with it); 40 / 32 calls in 741,159 / 749,928 non-library bytes | proven for most code (scan); the `__CHK` functions get a per-glob rule without `-s` once Phase 5 maps them to source files |
| FPU: `-fpi` vs `-fpi87` vs `-fpc` | `-fpi` | `-fpi` | `probe scan` "fpu": EMU387 1 row, NOEMU387 0; MATH387 15 / 19 rows and MATH3 1 row (shared, 0 only in MATH3), so inline x87 code, not `-fpc` calls | proven (scan), with one caveat: one `-fpi` object anywhere links the emulator, so `-fpi87` modules beside it would not show (research A3). The code is identical (the LEDATA and FIXUPP records of the probe's `5r_s` and `5r_s_fpi87` objects are equal in 10.5, 10.6 and 11.0), but the `-fpi` object also requests `emu387` and declares the extern `__init_387_emulator`, which is what pulls EMU387 in; the calibration log shows only the default-library column |
| CPU target: `-4` vs `-5` (and `-3`) | `-4` | `-4` | `probe scan` "cpu": setcc_and 30 / 58, setcc_movzx 0 / 0, so not `-3`. "struct-copy sizes": 5-dword rep copies UFO2P 2 (`5+2`), TACP 6 (`5` x5, `5+1` x1), and no unrolled run of 5 or more `movsd` in either EXE. On the probe only a 5-dword copy (20-23 bytes) separates `-4` (rep) from `-5` (unrolled under every `-5r` option tried) | scan evidence: no `-5` evidence in either EXE. A module built at `-5` that copies no 5-dword struct would not show; the first Phase 5 matches will confirm |
| Memory model: `-mf` | flat 32-bit | flat 32-bit | `probe scan` "memory model": 2 objects, both with the 32-bit flag | consistent with `-mf`, wcc386's 386 default; this is what the data shows, not a flag proof, so the rule does not write it |
| Target: `-bt=dos` | DOS | DOS | DOS CLIB modules linked (`runtime.csv`); the NT-hosted compilers define `__NT__` without it | wrapper-owned: `uv run reverseapoc cc` always passes `-bt=dos` |
| Optimization: `-o*` | not known yet | not known yet | the decisive idioms tie between `-4r -s` and `-4r -s -ox`; loop shapes are mixed (see Result) | candidate, evidence pending: a Phase 5 function that matches under one `-o` set and not under the other |
| Structure packing: `-zp*` | not known yet | not known yet | field offsets of structs used by matched code | candidate, evidence pending (Phase 5 matches) |
| One segment per function: `-zm` | not known yet | not known yet | padding and order between functions in the code object | candidate, evidence pending (Phase 5 matches) |
| FP scheduling: `-fp3`/`-fp5` | not known yet | not known yet | `fxch` placement in x87 code | candidate, evidence pending (Phase 5 matches) |

Notes:

- The `-4` reading rests on few sites: UFO2P's two recognised 5-dword copies plus two likely ones the recogniser skips (an unaccepted instruction between `mov ecx,5` and `rep movsd`), in two code regions; TACP's six plus two likely ones ([04-10-SUMMARY.md](../.planning/phases/04-compiler-identification/04-10-SUMMARY.md), fix rounds 1 and 2). The size table behind it was measured on 10.6 and 11.0; 10.5 gives the same object as 10.6 on the probe's 5-dword copy in every cell.
- Switch compare forms are counted for `eax`/`al` only; the switch and loop counts are shapes, never evidence for a flag.
- Both EXEs give the same answer for every flag: a measured finding, not an assumption (D-09).
- **What the first UFO2P match says (05-18, func_000A3980, see [Phase 5 match evidence](#phase-5-match-evidence)).** It matches under the default rule, so the rule holds for it, but it separates no candidate: no sweep ran (D-17 sweeps only after a miss), so 10.6, 10.5 and 11.0 stay tied; it has no 5-dword struct copy, so `-4` vs `-5` stays tied; it has no loop, branch or stack frame for an `-o` set to change, so `-o*` stays a candidate; and it loads a byte declared `signed char`, which reads the same with or without `-j`. One match changes nothing in the `*` default: D-18 needs 3 functions from different regions of both EXEs that agree.

The default rule in `config/cflags.txt` is `*  wcc386@10.6  -4r -s -fpi`, written explicitly. It is consistent with the scans above and supported by them; it is not proven by them. The version is 10.6 because that is the one consistent with the probe (10.5 byte-identical, 11.0 tied with it at `-4r`, see Result) and with the linked runtime library (10.6, D-07). `-4r` carries the register convention (no 3S-only runtime row) and the CPU target `-4` (no `-5` evidence: the 5-dword struct copies use `rep`). `-s` is the stack-check default, and `-fpi` is wcc386's default made explicit (the probe gives the same object with and without it; research A3 caveat in the FPU row). The candidates stay out of the rule until Phase 5 matches prove them, and the first Phase 5 matches also confirm or change the rule itself.

References from other Watcom games, not evidence for ours:

| Project | Compiler | Flags |
|---|---|---|
| KKND | patched OW `wcc386` (10.0/10.0a target) | `-s -of+ -5r -omiler -zm -zp1` |
| Theme Hospital | `wpp386` 10.6 | `-s -ot -d2 -zm` |
| NHL95PC | 10.0 GA | `-5r -fpi -zp1` |

For scratches, start from the default rule above and work through [Fallbacks and candidates](#fallbacks-and-candidates) below.

### Phase 5 match evidence

Every hand match, with the cell that proved it. A row is written only from `reverseapoc check EXE/UNIT --json` exiting 0: objdiff 100.0, the relocation check, the byte compare and both EXEs landed SHA-1 identical to `config/targets.toml` (D-16). "default" is the `*` rule of `config/cflags.txt`; a sweep cell names its number and its log under `build/logs/` (gitignored).

| EXE | Function | Unit | Compiler | Flags | Evidence cell | objdiff | Reloc check | SHA-1 |
|---|---|---|---|---|---|---|---|---|
| UFO2P.EXE | func_000A3980 (13 bytes: one call, one `signed char` load) | u_000a34f0 (`src/ufo2p/u_000a34f0.c`, 2 INCLUDE_ASM stubs) | wcc386@10.6 | `-4r -s -fpi` | default | 100.0 | ok | UFO2P.EXE and TACP.EXE identical |

Before any game C, plan 05-18 re-proved spike 005 through the production writers (`tests/test_check_real.py`): `check_source` on Watcom's own CMAIN386.C against the `__CMain` runtime row gives objdiff 100.0, a passing relocation check and equal bytes in both EXEs, landing it alone keeps both SHA-1s, and a planted wrong call target fails the relocation check. `tests/test_objdiff_real.py` repeats the objdiff blind spot (a wrong 2nd relocation of one instruction scores 100.0) through omf2elf, the target writer and objdiff-cli.

### Fallbacks and candidates

The owner accepted Phase 4 under D-08/D-10 on 2026-10-22 (override in `04-VERIFICATION.md`): the version and flags below are a preference order and a candidate list, not a proof. The first Phase 5 matches prove or drop each entry; record what a match proves in the Flags table above.

Game-code compiler versions, in the order to try:

1. **10.6, preferred.** The linked runtime library is 10.6 (11 modules per EXE match only 10.6, see Result), and a team building one game most likely used one toolchain for runtime and game code. The probe cannot separate 10.6 from 10.5, or from 11.0 at `-4r`, so this is a choice backed by the runtime evidence, not a codegen proof.
2. **10.5, first fallback.** Byte-identical to 10.6 on every probe cell, so it only matters if a real function compiles differently under the two. Try it when a 10.6 build misses and no flag change explains the miss.
3. **11.0, candidate.** Tied with 10.6 at `-4r` on the decisive idioms, with no 11.0-only runtime row. If Phase 5 matches favour it, sweep 11.0a and 11.0b too (see Result).

Candidate flags. Each axis lists the default-rule value first; the alternatives stay candidates until a match proves one. When a function misses, change one axis at a time first, then combine axes (the version above is one more axis):

| Axis | Default rule | Alternatives to try | What proves it |
|---|---|---|---|
| CPU target | `-4` | `-5` | a 5-dword struct copy unrolled (`-5`) or `rep` (`-4`) in a matched function; a module with no such copy does not show it |
| Stack checks | `-s` | no `-s` (per function: the 40 UFO2P / 32 TACP `__CHK` functions) | a `push imm32; call __CHK` prologue in the original function |
| FPU | `-fpi` | `-fpi87` (per module) | the object's default-library request (`emu387` vs `noemu387`); the code bytes are equal on the probe, and one `-fpi` object anywhere hides `-fpi87` neighbours (research A3) |
| FP scheduling | none | `-fp3`, `-fp5` | `fxch` placement in matched x87 code |
| Optimization | none | `-ox`; subsets `-ot`, `-os`, `-oneatx`; single letters `-od -of+ -or -oi -om -ol -on -op` (decomp.me's set); KKND used `-of+ -omiler`, Theme Hospital `-ot` | a function that matches under one `-o` set and not another. On the probe, `-ox` ties with no `-o` at `-4r`; `-os` at `-5r` emitted the `movzx` byte compare the game lacks (not probed at `-4r`); `-oneatx` removes both loop shapes |
| Structure packing | none (compiler default) | `-zp1`, `-zp2`, `-zp4`, `-zp8` (KKND and NHL95PC used `-zp1`) | field offsets of structs used by matched code |
| One segment per function | off | `-zm` (KKND and Theme Hospital used it) | padding and order between functions in the code object |
| Char signedness | none (unsigned `char`) | `-j` | sign- vs zero-extension of `char` loads in matched code |
| Debug info | none | `-d1`, `-d2` (Theme Hospital used `-d2`) | untested whether either changes our code bytes |

Ruled out by the Phase 4 scans, so not permuted unless new evidence appears: `-3` (no `movzx` byte compare), the stack calling convention `-3s`/`-4s`/`-5s` (0 3S-only runtime rows), `-fpc` (inline x87 via MATH387), and any memory model other than flat `-mf`.

### C, not C++

Both EXEs are C compiled with `wcc386` (CID-06). `uv run reverseapoc cppscan <EXE>` (plan 04-09) prints, per EXE:

- UFO2P: `C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 5 vtable-shaped candidate runs (C dispatch tables look the same)`
- TACP: `C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 3 vtable-shaped candidate runs (C dispatch tables look the same)`

| Signal | UFO2P | TACP |
|---|---|---|
| XI init table (found through the matched `inirt386` module) | 0x0013E11C..0x0013E158, 10 entries: priority 1 (thread) x1, 2 (fpu) x1, 3 x1, 32 (library) x7; 8 routines in the runtime map | 0x002B63D6..0x002B6412, the same 10-entry profile; 8 in the runtime map |
| YI exit table | 0x0013E158..0x0013E164, 2 entries: priority 1 x1, 32 x1; 1 in the runtime map | 0x002B6412..0x002B641E, the same profile; 1 in the runtime map |
| XI priority 64 (C++ static constructors) / YI priority 40 (module destructors) | 0 / 0 | 0 / 0 |
| Runtime rows only in C++ libraries | none | none |
| `__wcpp_` / `W?` strings | 0 / 0 | 0 / 0 |
| Vtable-shaped candidate runs (weak: C function-pointer tables look the same) | 5 | 3 |

What the scan does not cover:

- The C++-only module signal reads CODE segments only, like `libmatch`; code that sits only in COMDATs is not matched (in the 10.5/10.6 PLIB3R about 13% of the C++ code bytes, measured in plan 04-09).
- An ambiguous runtime row whose candidates are all C++ libraries would not be counted; there is none in either EXE.
- Only a verdict starting `C (wcc386): ` is a full C verdict. `C (wcc386) on partial evidence:` means the C++ library sweep had a gap.

Older local-scan facts that agree: UFO2P embeds `source\grafix.c` (next to PCX-loading error strings) and `source/pixlpath.c` (next to `rawdata/pixlpath.pcx`), and TACP contains neither; neither binary holds "pure virtual" or RTTI strings; the `assertion "%s" failed` string lives in the DOS/4GW extender region, not the game. Keep `wpp386` available per file anyway, because Theme Hospital found that `wcc386` "generates different code for the same source" when the original was C++.

## What the Docker image contains, and what you supply

The image is built locally and never pushed with proprietary bytes in it.

| In the image | Supplied by you (gitignored, mounted read-only) | Outside the container |
|---|---|---|
| Python 3.14 + uv (image tag pinned) | `third_party/watcom/`: Watcom 10.5, 10.6, 11.0, 11.0a and 11.0b trees, mounted at `/work/watcom:ro` (see [Getting the Watcom compilers](#getting-the-watcom-compilers)) | decomp.wtf v0.10.6 in WSL2, its own venv (Python 3.12+) |
| ninja | `orig/`: UFO2P.EXE, TACP.EXE and SMKP.EXE from your install, mounted at `/work/orig:ro` | |
| clang-format, clangd | `.env`: install paths and API keys | |
| binutils (`as`) | | |
| `objdiff-cli` (pinned release binary) | | |
| wibo 1.2.0 (`COPY --from=ghcr.io/decompals/wibo:1.2.0`, as decomp.me's cromper does) | | |
| Open Watcom v2 Linux build (`wdis`, `wlink`, `wlib` only) | | |
| OpenJDK 21 (`openjdk-21-jdk-headless`, 21.0.12.1, apt-pinned; Phase 5) | | |
| Ghidra 12.1.4 with the lastonesky LE loader v12.1.4-1, headless, in its own cached `ghidra` stage at `/opt/ghidra` (`GHIDRA_INSTALL_DIR`); run it with `uv run reverseapoc ghidra-export` (Phase 5) | | |
| clang 18 (18.1.3, apt-pinned), the C89 lint gate `uv run reverseapoc lint` (D-14; Phase 5) | | |

capstone 5.0.9 is not an image package: it is a Python dependency (`[project].dependencies`) and comes with `uv sync`. Ghidra, the JDK and clang took the image from 300,640,359 to 898,389,257 bytes, after the D-20 strip of Ghidra's `docs/` and its uninstalled top-level `Extensions/` zips (plan 05-12; the unstripped image was 1,067,599,391 bytes). GhidraMCP is not installed: it is Later (see [tools.md](tools.md)).

Watcom 10.x/11.0 is proprietary and its current IP owner was not verified, so it is never baked into an image layer. Open Watcom's licence permits redistribution, but it cannot match.

## Getting the Watcom compilers

The original compilers are not distributed here. Three opt-in commands fetch, install and check them on your machine. They are never run by the Dockerfile or CI.

### Sources

- **Internet Archive (preferred).** Uploader cdroms@textfiles.com, 2018: [Watcom_C_10.5](https://archive.org/details/Watcom_C_10.5), [Watcom_C_10.6](https://archive.org/details/Watcom_C_10.6), [Watcom_C_11.0](https://archive.org/details/Watcom_C_11.0).
- **Collection item.** [watcom-c-cpp-compilers-collection](https://archive.org/details/watcom-c-cpp-compilers-collection) holds 11.0a (`watcom-11.0a/WatcomC11a.iso`) and 11.0b (`watcom-11.0b/WATCOM_C11B.iso`). It publishes SHA256SUMS and cross-verification notes. It also holds files Phase 4 may need: the 10.5a patch (`watcom-10.5/patches/c105_a.zip`), the 11.0c update, 10.6a and the QNX 10.6b patches. Its 10.5, 10.6 and 11.0 ISOs are byte-identical to the three items above.
- **WinWorld (mirror).** [10.5](https://winworldpc.com/product/watcom-c-c/105), [10.6](https://winworldpc.com/product/watcom-c-c/106), [11.0, 11.0a, 11.0b](https://winworldpc.com/product/watcom-c-c/110b). The same ISO bytes inside `.7z` archives, but WinWorld caps downloads at 25 a day. To use them, extract the ISO from the `.7z`, rename it to the file name in the table below (WinWorld's 10.6 archive, for example, calls it `watcom10.6.iso`) and put it in `third_party/watcom-media/`; `fetch-watcom` then verifies it and skips the download.

### ISOs

| Version | File | Size (bytes) | SHA-1 |
|---|---|---:|---|
| 10.5 | `Watcom_C++_10.5.iso` | 515,213,312 | `0722e7494647cd5e9a66bd106aa80a620f7ee999` |
| 10.6 | `Watcom_C++_10.6.iso` | 664,373,248 | `211f4e7acecf89cf8af26e12099e1aec5a255f65` |
| 11.0 | `Watcom_C++_11.0.iso` | 669,603,840 | `1708a29f7209b9d29aff18aba8923a0ddd5d97cc` |
| 11.0a | `WatcomC11a.iso` | 670,785,536 | `8361779a2c7fb395eedff82d4f6207a819292f87` |
| 11.0b | `WATCOM_C11B.iso` | 649,111,552 | `da67b5b249357b120e20d8580043ead319f2a91b` |

`config/watcom.toml` is the source of truth: md5, CRC32 and key-file hashes live there.

### Commands

`VERSION` is one or more of the versions above; with none given, a command acts on all five.

- `uv run reverseapoc fetch-watcom [VERSION ...]` downloads the ISOs into `third_party/watcom-media/` and verifies them. An already-verified file is skipped, so copying your own ISOs there first works too.
- `uv run reverseapoc install-watcom [VERSION ...] [--force]` extracts each verified ISO verbatim (original upper-case names) into `third_party/watcom/<version>/`, using the repo's stdlib ISO9660 reader. `--force` replaces an existing installation.
- `uv run reverseapoc check-watcom [VERSION ...]` verifies the key files (compiler, linker, CLIB3R/CLIB3S, MATH3R/MATH387R, STDIO.H) against the manifest.

### Layout

- `third_party/watcom-media/`: the ISOs. Outside the container's compiler mount.
- `third_party/watcom/<version>/BINNT, BINW, H, LIB386, ...`: the extracted trees, mounted read-only at `/work/watcom`.

Both are gitignored.

### What is on the discs

- **10.5 and 10.6:** `BINNT/WCC386.EXE` is a 9,216-byte Win32 loader stub ("32-bit DOS programs require the BINW directory to be in your path before BINNT"). The real compiler is `BINW/WCC386.EXE`: an LX image of 567,558 bytes in 10.5 (decoded, see below) and of 567,698 bytes in 10.6. The 11.0 `BINW/WCC386.EXE` (653,342 bytes) is an LX image too: in all three swept versions `e_lfanew` is 0xE38 and the two bytes there are `LX`, so `reverseapoc parse-le` rejects them ("no LE header found"). Only the game EXEs are LE. The loader finds it by itself: it reads its own path and opens `..\BINW\WCC386.EXE` next to it (confirmed under wibo with `WIBO_DEBUG=1`, spike [004](../.planning/spikes/004-wibo-watcom/README.md)), so a tree needs `BINW` next to `BINNT`, and PATH, `WATCOM` and DOS4GW are not needed.
- **11.0, 11.0a, 11.0b:** `BINNT` is native Win32 (`WCC386.EXE` driver plus `WCCD386.DLL`).
- **10.5:** `BINW/WCC386.EXE` on the CD is a damaged 65,536-byte stub. The real 567,558-byte binary is packed in `DISKIMGS/DISK02/PCK00017.1` and `DISKIMGS/DISK03/PCK00017.2` (wpack). `install-watcom 10.5` decodes it from those two parts with the repo's own decoder (D-01; format in [research/wpack-format.md](research/wpack-format.md)) and `config/watcom.toml` pins the decoded file. An install made before that still holds the stub, and `check-watcom 10.5` reports `MISMATCH` for it: run `uv run reverseapoc install-watcom 10.5 --force` once to replace the tree.
- **11.0b:** the only public dump has one damaged directory sector (353) for the 3-file sample folder `SAMPLES/WIN/DATACTL/WIN16`. 7-Zip cannot open the image. `install-watcom` skips that folder (manifest `skip_dirs`). The compiler, headers and libraries are unaffected.

## Tools in detail

### decomp.me

decomp.me's `msdos` platform offers `wcc10.0a`, `wcc10.5`, `wcc10.5a`, `wcc10.6` and `wcc11.0`, plus the `wpp` C++ equivalents ([compilers.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/compilers.py)). It runs `binnt/wcc386.exe` under wibo. Try `wcc10.6` and `wcc10.5` first, then `wcc11.0`. Whether `-zm` and `-d2` can be typed as custom flags is unverified.

### Ghidra and loaders

- **Ghidra 12.1.4** (2026-09-21). Stock Ghidra has no LE loader and no `__watcall` ([ghidra#532](https://github.com/NationalSecurityAgency/ghidra/issues/532), [ghidra#156](https://github.com/NationalSecurityAgency/ghidra/issues/156)).
- **lastonesky ghidra-lx-loader v12.1.4-1** (2026-10-10): supports 12.1.x and ships a Watcom cspec with `__watcall` ([release](https://github.com/lastonesky/ghidra-lx-loader/releases/tag/v12.1.4-1)). Upstream yetmorecode v12.0.1 targets 12.0 and breaks on the 12.1 loader API.
- **retrokit** (Apache-2.0): its own LE loader, `watcom`/`watcomreg` cspec auto-detection, Open Watcom library signatures, function export and an MCP server ([nemo22/retrokit](https://github.com/nemo22/retrokit)). Exported sizes are Ghidra body counts and need post-processing into contiguous ranges.
- **Outcome (D-03, Phase 5): lastonesky v12.1.4-1, retrokit not used.** The loader zip and the Ghidra zip are SHA-256-pinned in `docker/Dockerfile`. The loader imports both bound EXEs through its BW-header walk: its `checkFormat` takes `e_lfanew` only when the first MZ has `e_lfarlc == 0x40`, and otherwise walks "DOS/16 BW" headers from `(e_cp-1)*512 + e_cblp`; both EXEs have a `BW` header at 0xF474, so the README's "DOS/16 LE" is its name for that binding, not an unbound file ([05-RESEARCH.md](../.planning/phases/05-split-and-first-matches/05-RESEARCH.md), "Pattern 2: Ghidra headless export"). It places `.object1` at 0x10000 and `.object2` at 0xD0000 (UFO2P) / 0xE0000 (TACP) with the le.py sizes.
- **Bytes and fixups always come from `le.py`** (P3, P4). With every relocation site zeroed on both sides, Ghidra's blocks and `load_flat(relocate=False)` have equal SHA-1s for both objects of both EXEs, so Ghidra's bytes differ only at relocation sites. Its relocation table lists each page-straddling off32 field twice (type 7: 28,197 = 28,183 + 14 in UFO2P, 24,435 = 24,424 + 11 in TACP). Ghidra supplies boundaries, names and drafts only.
- **Headless export.** `uv run reverseapoc ghidra-export EXE` runs `analyzeHeadless -loader LeLoader` with the committed Java GhidraScripts (Jython is an uninstalled extension in 12.1.4 and PyGhidra's bundled JPype wheels stop at cp313, while the project is on 3.14). It finds 1408 functions in UFO2P and 1498 in TACP, about one minute per EXE, and `--drafts ADDR ...` writes decompile drafts. Each export has exactly one one-address "function" in the data object (UFO2P 0x0013BD40, TACP 0x002B405C), which reconcile drops (plan 05-12). The raw exports are cached, gitignored, in `build/ghidra/<exe>/functions.raw.csv`.

### GhidraMCP

**Later** (Phase 6 context pack or later; deferred in Phase 5, see [tools.md](tools.md)). LaurieWired GhidraMCP 2.0 (2026-10-10) supports Ghidra 12.1.4 and has a GUI-less `--headless` PyGhidra mode, which needs Python 3.10-3.13 ([GhidraMCP](https://github.com/LaurieWired/GhidraMCP)). It is not installed in the image.

### objdiff and the OMF bridge

- objdiff cannot read OMF. Issue [#97](https://github.com/encounter/objdiff/issues/97) has been open since 2024-08-19; a WIP `omf` branch dates from 2025-09-25; v3.8.2 (2026-09-29) reads ELF and COFF only.
- Bridge: Theme Hospital's `omf2elf.py` (GPLv3, about 590 lines) converts Watcom OMF to ELF32, including COMDAT, LIDATA, FIXUPP threads and BAKPAT. Theme Hospital runs objdiff-cli 3.8.1 through it.
- objdiff compares at most one relocation per x86 instruction, so Theme Hospital's `elfrelocs.py`/`verify.py` check the rest.
- Target objects for objdiff are cut from the LE, with relocations built from LE fixups (Phase 5).
- Fallback: KKND-style compare (cut each function from its OMF object, mask relocations, check their targets), which avoids objdiff entirely. Not needed: spike 005 kept the hybrid pipeline (D-02).

Result (spike [005](../.planning/spikes/005-objdiff-omf-elf/README.md), verdict VALIDATED):

- **The pair.** The `cmain386` runtime row (public `__CMain`, 79 bytes) of UFO2P.EXE and TACP.EXE, against Watcom's own `SRC/STARTUP/386/CMAIN386.C` read in place from the read-only 10.6 tree (never copied, D-19) and compiled by `reverseapoc cc` under the default rule. objdiff-cli 3.8.2 loads both the converted object and the LE cut and reports `match_percent` 100.0 for `__CMain` in both EXEs.
- **The shape objdiff pairs.** Code sections are named `_TEXT` on both sides: a target `.text` against our `_TEXT` is left unpaired. Relocations are REL, with the addend in the field: on our side the Theme Hospital addend rule (`R_386_PC32` field = stored + displacement - 4, `R_386_32` = stored + displacement), on the target side every LE off32 field rewritten to its addend (the raw field holds `target_off`) and every call field to -4. objdiff compares a relocation to an undefined symbol by name and addend only, so the target side uses the exact linker names (`func_X_`, `_D_X`, Watcom publics such as `exit_` and `__CommonInit_`), one name per address; the optional committed `config/<exe>/symbols.csv` (`address,name,kind`, no bytes) supplies names the CSVs cannot derive.
- **The blind spot.** objdiff checks one relocation per instruction: in the spike's plants a wrong symbol on the 2nd relocation of one instruction (the imm32 of a `mov dword [abs32], imm32`) still scores 100.0, while a wrong call symbol or addend drops the score below 100. objdiff is a score and a viewer, not the gate: the relocation check (SPL-09, `tools/reverseapoc/relocs.py`) plus the whole-EXE SHA-1 is the gate.

### wibo

wibo 1.2.0 runs the Win32-hosted `BINNT\wcc386.exe` on Linux ([decompals/wibo](https://github.com/decompals/wibo)). Older wibo (nixpkgs 0.6.14) cannot run Watcom ("Unhandled function LocalAlloc"). Watcom treats `/` as an option switch and splits paths on spaces: decomp.me rewrites `/` to `\`, and KKND compiles from relative paths under `build/tmp`. The BINNT binaries also run natively on the Windows host, which helps debugging.

Result (spike [004](../.planning/spikes/004-wibo-watcom/README.md), verdict VALIDATED): 10.5 (with the decoded BINW compiler), 10.6 and 11.0 all run under wibo 1.2.0 in `docker compose run` from the read-only `third_party/watcom` tree. D-03 compiled `probe/cg_basic.c` natively and under wibo for each version: the raw SHA-1s differ (THEADR holds the absolute source path, COMENT class 0xE9 absolute header paths and timestamps), and the normalized SHA-1s, over every other record, are equal for all three versions (`build/gate/04-native-vs-wibo.txt`: `D-03: normalized equal for 10.5, 10.6, 11.0`).

`uv run reverseapoc cc SRC -o OBJ` encodes the invocation rules, the same on the host and in the container:

- always `-zq -zld -bt=dos` (quiet; no file-dependency entries: `-zld` drops the source and header entries, but each object still ends its dependency list with one empty COMENT 0xE9 record, measured on 10.5, 10.6 and 11.0; DOS target instead of the NT host's `__NT__` default) and `-fr=` naming an error file beside the object, so no stray `.err` file lands in the cwd (10.5 writes no error file at all);
- `-i=<tree>\H` from the selected version's own tree only (`WATCOM=<tree>` alone does not find the headers);
- relative paths with backslashes, refusing any path with a space or a leading `-` (Watcom reads `/` as an option switch);
- an environment built from scratch (PATH, plus SYSTEMROOT, TEMP and TMP on Windows), so `WCC386`, `INCLUDE` or `WATCOM` set in the caller's environment never reach the compiler (`WCC386=-3r` in the environment changes codegen);
- the size and SHA-1 of the compiler binaries checked against `config/watcom.toml` first, and the compiler's banner written to the log; the OK line gives the raw and the normalized SHA-1 of the object;
- one line per call appended to `build/logs/cc.log` (or to the file `--log` names) under an OS lock on the sidecar `cc.log.lock` beside it (`<log>.lock` for another `--log`): `fcntl.flock` in Linux, a non-blocking `msvcrt.locking` loop on Windows. The lock is held from before the log is opened until after it is closed, so parallel `cc` processes in one environment (one `ninja -j`, or several containers at once) leave one intact line per call, in any order, and a killed `cc` frees the lock when it exits. The log's directory must be writable, because `<log>.lock` is created there; a log that is a device (such as `/dev/null`) is appended to without the lock and gets no sidecar. Every writer of one log must name it by the same path, because the sidecar is derived from the `--log` spelling, not from the file it reaches: a symlink, junction, hard link or `subst` drive to the same file gets a different sidecar, so a different lock, and lines can be lost again (a relative and an absolute spelling of the same path are fine, they open the same sidecar). The Windows host and a container writing the same log at the same time is not supported, because the two OS locks do not see each other: give each its own `--log`. Lines written on the Windows host end in CRLF, those written in the container in LF.

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
| Watcom C | game code: 10.6 preferred (10.5 byte-identical on the probe, first fallback; 11.0 tied at `-4r`, candidate pending Phase 5 matches; see [Fallbacks and candidates](#fallbacks-and-candidates)); linked runtime library: 10.6 (see [Result](#result)) | Phase 4 |
| Ghidra | 12.1.4 (sha256-pinned in `docker/Dockerfile`) + OpenJDK 21.0.12.1 | Phase 5 |
| ghidra-lx-loader | lastonesky v12.1.4-1 (sha256-pinned in `docker/Dockerfile`) | Phase 5 |
| clang | 18.1.3 (`clang-18=1:18.1.3-1ubuntu1`, lint gate) | Phase 5 |
| capstone | 5.0.9 (`[project].dependencies`) | Phase 5 |
| GhidraMCP | 2.0, headless, Python 3.13 | Later |
| decomp.wtf | v0.10.6 (archived) | Phase 6 |
