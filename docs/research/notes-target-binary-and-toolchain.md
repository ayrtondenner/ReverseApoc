# Target binary and toolchain: X-COM Apocalypse (1997) matching-decomp feasibility

Research date: 2026-10-19. All web sources were accessed on 2026-10-19. "Local scan" means read-only Python scans (`python -I -c`) of the Steam install at `C:\Program Files (x86)\Steam\steamapps\common\XCom Apocalypse\XCOMA`. No files were written there.

NOTE: plan mode was active in this session, so these notes could only be written to this plan file. The requested scratchpad path (`...\scratchpad\research_notes\ReverseApoc kickoff research\target_binary_and_toolchain.md`) was NOT written. Copy this file there.

## Q1. Which Watcom version, how do projects identify it, and must the original compiler be used?

### Takeaway
The "1988-1995" C/C++32 runtime banner rules out Watcom 10.0 and 10.0a. It is consistent with 10.5, 10.6 and 11.0/11.0A/11.0B, which all ship identical banners. 10.5/10.6 is the most plausible family; 10.5 and 10.6 emit identical code on the published probe, while 11.0 differs measurably. Byte-matching needs the original proprietary wcc386/wpp386: Open Watcom (descended from 11.0c) has documented codegen differences from 10.x that no flag fixes. Existing projects get the old compilers from WinWorld CD images and run the Win32-hosted binaries under wibo, Wine or dosemu2.

### Cited Findings
**Local scan of the binaries**
- UFO2P.EXE, TACP.EXE and SMKP.EXE each contain two Watcom banners [local scan]:
  - `WATCOM C/C++16 Run-Time system. ... 1988-1994` (in the 16-bit DOS/4GW part).
  - `WATCOM C/C++32 Run-Time system. ... 1988-1995` (in the 32-bit program).
- They also contain `Copyright (C) Rational Systems, Inc. 1987 - 1993` and `1990-1994` [local scan].
- LE layout [local scan]:
  - In UFO2P and TACP, the LE program's own MZ stub is at file offset 0x352A4, so the bound DOS/4GW Pro kernel takes the first 217,764 bytes. The LE header is at 0x37F34.
  - In SMKP, the stub is at 0x26654 (157,268 bytes of extender) and the LE header at 0x292E4. SMKP therefore carries a different-size DOS/4GW blob.
  - LE page data runs exactly to EOF. There are no overlays and no appended Watcom debug info: the LE debug-info offset and length are 0, and the non-resident name table is empty.
- LE objects (page size 4096, cpu=386, os=OS/2-style LE flag 1) [local scan]:
  - UFO2P.EXE:
    - obj1 (code, flags 0x2045): base 0x10000, vsize 0xBFADD (785,117 bytes).
    - obj2 (data, flags 0x2043): base 0xD0000, vsize 0x181E20 (1,580,576 bytes, includes BSS).
    - Entry point: obj1:0xB0784.
    - Resident module name: `ufo24`.
  - TACP.EXE:
    - obj1: base 0x10000, vsize 0xC254F (796,495 bytes).
    - obj2: base 0xE0000, vsize 0x25F0B0 (2,486,448 bytes).
    - Entry point: obj1:0xB28B0.
    - Module name: `tac4`.
  - SMKP.EXE:
    - obj1: base 0x10000, vsize 0x11380.
    - obj2: base 0x30000, vsize 0xFA70.
    - Module name: `SMKP`.
- Codegen idiom counts (whole file) [local scan]:
  - `setcc al; and eax,0FFh` appears 33 times in UFO2P and 61 times in TACP.
  - `setcc al; movzx eax,al` appears once in each.
  - The 10.0a-only "promote then `cmp eax,imm`" idiom appears 0 times.
- The idiom split matters for dating. Per mosura's table, classic 10.x/11.0 use `and eax,0FFh`, while Open Watcom 2.0 (and 9.01) use `movzx` — [mosura codegen doc](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-codegen-fingerprint.md).

**What the banner can and cannot tell you** — measured from install ISOs in [mosura watcom-detection.md](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-detection.md):

| Toolchain | C/C++32 runtime banners shipped |
| --- | --- |
| 10.0 / 10.0a | `1988-1993` and `1988-1994` |
| 10.5 | `1988-1994` and `1988-1995` |
| 10.6 | `1988-1994` and `1988-1995` |
| 11.0 / 11.0A / 11.0B | `1988-1994` and `1988-1995` |

- "No runtime banner in the whole 10.0–11.0 lineage exceeds `1988-1995`."
- "10.5 through 11.0B are indistinguishable by runtime banner."
- The exact release appears only in the compiler tool banner ("Version 10.6"), never in the linked binary.

**Codegen fingerprinting** — [mosura codegen fingerprint](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-codegen-fingerprint.md):
- A 5-construct probe (`cmpbyte`, a counted loop, a small switch, `x/7`, `x/10u`) separates the revisions. Probe code sizes: 10.0a 162 bytes, 10.5 = 10.6 156 bytes (byte-identical), 11.0 158 bytes, 9.01 150 bytes.
- `cmpbyte(unsigned char c){return c==5;}` compiles as:
  - 10.6: `cmp al,5; sete al; and eax,0ffH`
  - 11.0: `cmp al,5; jne L$1; mov eax,1` (a branch, no setcc)
  - Open Watcom 2.0: `cmp al,5; sete al; movzx eax,al`
- Loop-bound register: `ebx` in 10.x, `ecx` in 11.0 and Open Watcom.
- Switch compare order: ascending in classic Watcom, descending in Open Watcom.
- Recipes:
  - 10.0a, 10.6 and 11.0 run under dosemu2 (DOS host in `BINB`/`BINW`; needs `W32RUN.EXE` on PATH).
  - On the 10.5 CD, `BINW/WCC386.EXE` is a damaged 65,536-byte stub. The real 567,558-byte binary has to be unpacked from `DISKIMGS/DISK02+03/PCK00017.{1,2}` with their wpack decoder. It then runs under Wine through the `BINNT\WCC386.EXE` PE launcher.

**How comparable projects pinned their version**
- NHL95PC ([abdulahmad/NHL95PC](https://github.com/abdulahmad/NHL95PC)) pinned "Watcom C/C++32 10.0 GA (mid-1994)" as follows:
  - Banner 1988-1994.
  - `tools/libmatch.py` matched linked runtime modules against 10.0a CLIB3R, except modules changed by the 10.0a patch.
  - Codegen test: 10.0 LA reproduced 8/8 test functions byte-exact; 10.0a got 6/8 because it widens 16-bit short compares.
  - Flags (`-5r -fpi -zp1`) were inferred from instruction statistics, e.g. 2,527 `mov r32,[x-2]; sar r32,10h` loads point to `-5r`.
- Theme Hospital (1997, Bullfrog) ([matteo-pacini/theme-hospital-decomp](https://github.com/matteo-pacini/theme-hospital-decomp)):
  - Uses Watcom C/C++ 10.6 Win32-host binaries, plus 10.0a for some CRT printf/stdio modules, plus the 10.5/10.6 runtime libraries.
  - Flags: `wpp386 -s -ot -d2 -zm`, with per-file compiler/version/flags in `config/cflags.txt`.
  - The final link stage writes "the headers, fixup tables and the DOS/4GW stub of the Watcom 10.5 toolchain."
- KKND (Feb 1997) ([Wyrelade/KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp), [COMPILER_ANALYSIS.md](https://github.com/Wyrelade/KKND-Decomp/blob/main/COMPILER_ANALYSIS.md)):
  - The 1988-1994 banner implies 10.0/10.0a, even for a 1997 game ("the team likely kept an older compiler").
  - Flags were found by probe grids: `-s -of+ -5r -omiler -zm -zp1`.
  - The evidence behind each flag:
    - `-s`: no stack-check calls in prologues.
    - `-zm`: 16-byte zero fill between functions.
    - `-5r`: `and eax,0xff` instead of `movzx`.

**Open Watcom vs. the original compiler**
- KKND's findings ([COMPILER_ANALYSIS.md](https://github.com/Wyrelade/KKND-Decomp/blob/main/COMPILER_ANALYSIS.md)):
  - OW 1.9 and OW 2.0 produce identical output to each other, but some functions still do not match retail 10.x code.
  - OW "threads jumps on conditions it can prove on loop entry, and it lays out loops differently. No flag tested fixes this."
  - OW `-ob` moves `if` bodies after the epilogue.
  - The team is *patching* wcc386 (`doc/compiler_patch.md`) to restore Watcom-10 jump tables through `cs:`, switch costs, no loop padding, no entry threading and bottom-test loop entry.
  - Open Watcom descends from Watcom 11.0c.
  - Their stated fix is that "a real Watcom 10.0a wcc386 would resolve the loop-layout problem."
- How projects run and obtain the compiler:
  - Theme Hospital runs the period Win32-host compiler with wibo 1.2.0 on Linux, inside Nix flakes. The Watcom 10.5 and 10.6 CD images (~600 MB) are downloaded from WinWorld on first `nix develop`. It uses OW v2's `wlink` and `wdis` only as auxiliary tools — [theme-hospital-decomp](https://github.com/matteo-pacini/theme-hospital-decomp).
  - decomp.me runs `binnt/wcc386.exe` under wibo — [decomp.me compilers.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/compilers.py).
  - Blood-RE says "Watcom 10.6 and TASM 3.1 are required to build" and uses `wmake` and `.bat` files. It gives no source for the tools — [NBlood/Blood-RE](https://github.com/NBlood/Blood-RE).
- Release dates:
  - Watcom 10.6: 1996 per [Wikipedia](https://en.wikipedia.org/wiki/Watcom_C/C%2B%2B) and [WinWorld](https://winworldpc.com/product/watcom-c-c/106). mosura's table labels 10.6 as "(1995)", which is a minor conflict.
  - Watcom 11.0: 1997 (Sybase) — [mosura](https://github.com/jdmichaud/mosura/blob/main/docs/watcom-codegen-fingerprint.md).

### Inferences
- Version shortlist and how to settle it:
  - 10.0 and 10.0a are excluded, because a 1988-1995 lib was linked.
  - 11.0 is less likely, because X-COM Apocalypse shipped in mid-1997 when 11.0 had only just appeared, but it cannot be excluded from the banner alone.
  - To decide, compile mosura's probe (`cmpbyte`, counted-loop register, switch order) with 10.5/10.6 and 11.0 and look for those idioms in UFO2P's code object. A counted loop with its bound in `ebx` means 10.x; one with `ecx` and no setcc on byte compares means 11.0.
  - Then confirm the linked CLIB3R/MATH3R modules byte-for-byte against the 10.5, 10.6 and 11.0 `LIB386` libraries, the way NHL95PC's libmatch does.
- The absence of `movzx` after setcc (1 vs 33/61) argues against Open Watcom being enough. A recompile with OW would visibly diverge.
- Two Mythos binaries have their own module names, `ufo24` and `tac4` (the internal exe names at link time). This suggests separate link scripts per program. Expect two separate decomp "targets" with largely shared engine code, which may have been compiled with slightly different flags.
- No debug info is present (unlike the Theme Hospital 1997 demo, which shipped Watcom debug info). Naming will rely entirely on RE, OpenApoc knowledge and string references.
- SMKP.EXE's different DOS/4GW blob size suggests a different DOS/4GW Pro revision or bind. It may have been built or bound separately, possibly by RAD/Smacker tooling. This is unverified.

### Gaps
- No public source documents which Watcom version Mythos/MicroProse used for X-COM Apocalypse. I found no interviews or postmortems.
- No codegen probe has yet been run against the actual UFO2P/TACP code. The idiom counts above are whole-file and include runtime library code.
- The legal status of redistributing Watcom 10.x/11.0 binaries is not addressed by any project I read. Theme Hospital simply downloads from WinWorld, and Blood-RE gives no source. Current IP ownership (Sybase/SAP) was not verified.
- I did not verify whether Watcom 10.5a exists as a distinct public release. decomp.me lists a `wcc10.5a`.

## Q2. Is the game C or C++? Practical implications

### Takeaway
All evidence points to C (Watcom `wcc386`), though none of it is conclusive:
- There is no Watcom C++ runtime or name-mangling trace.
- UFO2P embeds source paths `source\grafix.c` and `source/pixlpath.c`.

The decomp should default to C89 compiled by wcc386. It should keep wpp386 available as a per-file fallback, because Theme Hospital's matching required wpp386 even for plain-looking code.

### Cited Findings
- Local scan of UFO2P/TACP [local scan]:
  - No `W?` Watcom C++ mangled symbols, no `__wcpp_*` runtime symbols, and no "pure virtual" strings. No `typeid`, `bad_alloc`, `xmsg` or `operator new` strings.
  - The only "terminate"/"unexpected" hits are unrelated ("TerminateConnection failed", "Unexpected Interrupt").
  - The binaries are stripped (no debug info), so missing symbols alone is weak evidence.
- UFO2P contains `source\grafix.c` at file offset 0x13315F, next to PCX-loading error strings ("is not a PCX file", "Out of memory loading"). It also contains `source/pixlpath.c` at 0x133503, next to `rawdata/pixlpath.pcx`, "cannot open pixlpath" and "error writing pixlpath". This looks like in-game data-generation code that writes or reads a `.c` file under a `source/` directory [local scan].
- TACP contains neither string [local scan].
- The `assertion "%s" failed (%s: %d)` string sits at 0x1DB5A, inside the DOS/4GW extender region before the LE. It is the extender's, not the game's [local scan].
- decomp.me's Watcom entries come as C/C++ pairs: `wcc10.x` (C) and `wpp10.x` (C++, `language=CXX`) — [decomp.me compilers.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/compilers.py).
- Theme Hospital was compiled with `wpp386` and its source is "decompiled C++". KKND (1997, also Watcom + HMI SOS) is pure C, with 48 modules named from their own `__FILE__` strings (`main.c`, `units.c`, ...) — [theme-hospital-decomp](https://github.com/matteo-pacini/theme-hospital-decomp); [KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp).
- The NHL95PC project is C only — [NHL95PC](https://github.com/abdulahmad/NHL95PC).

### Inferences
- **C vs C++, for the project owner:**
  - Watcom C (`wcc386`) is C89/ANSI C:
    - All local variable declarations must come at the start of a block, before any statement.
    - There are no `//` comments in strict mode; Watcom accepts them as an extension.
    - There is no `bool`, no references, no classes and no inline member functions.
  - Watcom C++ (`wpp386`, 1995–97) is pre-standard C++: no standard namespaces/STL, Watcom-specific name mangling (`W?name$n(...)`), and its own runtime (`__wcpp_*`).
  - Even for C-style code, wpp386 can generate different code, e.g. for stricter typing and implicit conversions. The compiler choice must match the original, not the author's preference.
  - Readability trade-off: C is close to what Ghidra emits and is easy to match. C++ would allow nicer structs/methods, but the source must then reproduce the original's class layout, vtables and calling conventions exactly. For matching, use the original's language.
- **Mid-block declarations:** Ghidra and LLM-produced decompilations often declare variables mid-block (C99 style). `wcc386` 10.x rejects these in C mode.
  - Either hoist declarations to the top of the block by hand, or use a tool that auto-hoists. The caller states that Macabeus's Kappa does this; I could not verify it in Kappa's README.
  - Hoisting can change register allocation and stack-slot order, so do it consistently and re-diff.
- **How to settle C vs C++ definitively:**
  - Look in obj1 for `__wcpp_` runtime routines, which are identifiable via library matching.
  - Look in obj2 for vtables: arrays of code pointers referenced from constructors.
  - Look for compiler-generated static-init (XI/YI) segments with C++ ctor calls.
  - Absence of all three, plus the `.c` source paths, gives strong evidence for C.

### Gaps
- No vtable/RTTI scan of the data object was done; it needs a disassembler pass.
- I could not verify Kappa's mid-block-declaration auto-fix from its README ([Macabeus/kappa](https://github.com/Macabeus/kappa) — "Your decompiler buddy who lives on VS Code", last pushed 2026-02-20). The README mentions decomp.me, m2c, decomp-permuter and objdiff integration, but not declaration hoisting.

## Q3. How existing DOS/4GW + Watcom matching decomps are organized

### Takeaway
The mature pattern (Theme Hospital, KKND, NHL95PC) is:
1. A Python LE reader/splitter.
2. Per-function or per-unit OMF compile with the period wcc386/wpp386, run under wibo/Wine/dosemu2.
3. Extract and compare functions (objdiff via an OMF→ELF converter, or custom scripts).
4. A custom LE writer that reproduces the original wlink's header, fixup ordering and DOS/4GW stub, with a final whole-EXE `cmp`/SHA-1 check.

Ninja via `configure.py` (Theme Hospital) and plain Python scripts (KKND) are the common build drivers. Non-matching ports (swars, TRX, fallout-ce, OpenDUNE) are relevant only for RE methodology.

### Cited Findings
**Theme Hospital** ([matteo-pacini/theme-hospital-decomp](https://github.com/matteo-pacini/theme-hospital-decomp))
- Build: `python3 configure.py` writes `build.ninja`, `objdiff.json` and `compile_commands.json`.
- Splitting and rebuilding:
  - `tools/split.py` splits `orig/HOSPITAL.EXE`.
  - `tools/` contains an LE reader and an OMF→ELF converter, so objdiff can read the objects.
  - `tools/relink.py` places units, and `tools/lewrite.py --strict` "fills the gaps as the original linker did."
- Verification:
  - `tools/check.py src/FILE.cpp` reports per-function matches.
  - `objdiff-cli diff` gives interactive diffs, and `ninja report` writes `build/report.json`.
  - Final gate: `cmp build/hospital.exe orig/HOSPITAL.EXE`.
- Compiler: Watcom 10.6 via wibo 1.2.0, on Nix. Flags `-s -ot -d2 -zm` (one segment per function).
- Other tools: rizin + rz-ghidra for pseudo-C, OW v2 `wdis`/`wlink`, and `wdump` on the demo's debug info.
- Progress as of 2026-09-30: 2938/2938 functions matched (100% of code bytes), of which:
  - 1381 are game functions, 813 are Bullfrog library functions, and 744 are runtime functions (Watcom CLIB, Miles, Smacker).
  - 53 are asm stand-ins.
  - 79 runtime functions are taken from Watcom's own 10.5/10.6 libs.
- Licensing: the tools are GPLv3, the reconstructed code is "not ours to license," and users must supply the GOG installer.

**KKND** ([Wyrelade/KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp))
- Pipeline (Python venv):
  - `tools/find_functions.py` → `configs/DOS/functions.csv`
  - `tools/split.py` → `asm/DOS/nonmatchings/*.s`
  - `tools/build_kknd.py` compiles `src/**/*.c` with wcc386, extracts each function from its OMF object, splices it into the LE image and checks SHA-1.
- Per-function workflow:
  - `tools/match.py scratch.c` loops until `OK`.
  - `INCLUDE_ASM` placeholders are used for unmatched functions.
  - `score_functions.py` ranks the easiest unmatched functions.
  - "A scratch match alone is never enough": relocations must resolve to their original targets.
- Progress: 492/3713 functions (13.25%); game code 489/2006 (24.38%). `update_readme_progress.py` syncs the numbers, with one function per commit.
- Target: LE with 3 objects and 20,192 fixups, bound DOS/4GW Pro.
- Libraries identified: Watcom CRT, MemCheck 3.5, UniVBE/VBE-AF and the HMI SOS loader.
- Code is CC0. The workflow is modelled on the Digimon World 2 decomp.

**NHL95PC** ([abdulahmad/NHL95PC](https://github.com/abdulahmad/NHL95PC))
- `tools/rebuild_exe.py extract` dumps:
  - the MZ stubs, LE header and tables (JSON)
  - 26,790 fixups (`le_fixups.tsv`)
  - per-segment code/data slices
- The whole EXE rebuilds byte-exact from 304 NASM files (one per segment), with symbolic fixup labels. `verify` prints MATCH.
- Only the three third-party stubs (DOS/16M loader, DOS/4GW kernel, wstub) remain opaque blobs.
- C matching is converted to OMF and spliced into the asm build. Matched C builds need DOSBox.
- Build: `make -j8`. Status: 709 of 1084 functions matched.

**Blood-RE** ([NBlood/Blood-RE](https://github.com/NBlood/Blood-RE))
- Matching decompilation of 17 Blood versions plus 9 MAPEDIT versions.
- Watcom 10.6 + TASM 3.1, built with `wmake`/`dobuild` batch scripts.
- The README does not describe its verification or progress method.

**Syndicate Wars port** ([mefistotelis/swars](https://github.com/mefistotelis/swars), pushed 2026-10-18)
- Not a matching decomp. It disassembles the DOS executable and progressively replaces parts with C (SDL/OpenAL), linking the remaining asm with GNU tools.
- Requires `-m32 -fno-PIC -fno-PIE`, because the asm calls back into remade C.
- Original 2010 write-up: Perl scripts translated asm, and the Open Watcom libc source ("~95% accurate") sped up function identification — [gynvael.coldwind.pl](https://gynvael.coldwind.pl/?id=279).

**Non-matching ports**
- TRX / LostArtefacts: an "open source re-implementation of Tomb Raider I–III … through decompilation" — [LostArtefacts/TRX](https://github.com/LostArtefacts/TRX).
- fallout1-ce: based on "Reference Edition", C++, a re-implementation — [alexbatalov/fallout1-ce](https://github.com/alexbatalov/fallout1-ce).
- OpenDUNE: a C reimplementation — [OpenDUNE/OpenDUNE](https://github.com/OpenDUNE/OpenDUNE).
- None of these are byte-matching projects.

**Tools**
- wcdatool: a Watcom-specific disassembler for LE executables that "works best when used on executables that contain debug symbols" — [fonic/wcdatool](https://github.com/fonic/wcdatool).
- ghidra-lx-loader: an "Ultimate Ghidra loader for the LX/LE executable file format (OS/2, DOS4GW, VxD)", pushed 2026-08-29 — [yetmorecode/ghidra-lx-loader](https://github.com/yetmorecode/ghidra-lx-loader).
- rebrew: a compiler-in-the-loop permutation/flag search for binary matching — [maci0/rebrew](https://github.com/maci0/rebrew).
- mosura: a Rust Ghidra port that ships a Watcom `watcall` cspec and Watcom version detection — [jdmichaud/mosura](https://github.com/jdmichaud/mosura).

### Inferences
- Recommended structure for ReverseApoc, modelled on Theme Hospital and KKND:
  - `configure.py` → ninja, with two targets (`ufo24` = UFO2P, `tac4` = TACP).
  - A Python LE splitter that emits `asm/` per function and `config/symbols`.
  - wcc386 10.5/10.6 run under wibo (Linux) or natively (Win32 host binaries on Windows).
  - An OMF→ELF converter so objdiff works, with `objdiff.json` and a progress report.
  - An LE writer reproducing wlink fixup order plus the opaque DOS/4GW Pro blob copied from the original.
- On Windows, the Win32-host (`BINNT`) Watcom 10.x binaries can run directly with no emulator, which is simpler than wibo/dosemu.
- The DOS/4GW Pro kernel (first 217,764 bytes) should be kept as an opaque, user-supplied blob, never committed, like NHL95PC's stubs.

### Gaps
- I did not find a dedicated "dos4gw unbind" tool in these projects. Each one writes its own LE extract/rewrite. DOS/32A's `SB` unbinder is known from general knowledge but was not verified here.
- recomp.fyi and decomp.wiki were not checked for further Watcom projects.
- I did not check whether decomp.dev tracks any Watcom/LE project.

## Q4. Prior RE knowledge of X-COM Apocalypse binaries

### Takeaway
Active Ghidra-based RE of UFO2P.EXE is happening right now in OpenApoc PRs (andremmfaria, Sept 2026), citing function and data addresses. OpenApoc's extractors already document many static data tables inside UFO2P/TACP, with byte offsets. UFOpaedia and the StrategyCore-era tools (Apoc'd, Apatcher, hidden Cityscape editor patch) cover data and behavior but not code. I found no public Ghidra/IDA database.

### Cited Findings
- **OpenApoc PR #1685** (2026-09-12, andremmfaria) — [OpenApoc#1685](https://github.com/OpenApoc/OpenApoc/pull/1685)
  - Data: "UFO2P.EXE holds two 28x28 signed-byte matrices, current relations at `0x0016ec28` and a long-term value at `0x0016f078`."
  - Functions named:
    - `FUN_00014854` (bulk copy at load)
    - `FUN_0009379c` and `FUN_00093a30` (UI text builders)
    - `FUN_0005faf0` ("the original's real adjuster … ally ripple")
  - Scale: "~90 sites in ~25 functions."
- Related andremmfaria PRs:
  - #1679 (STANDART typo), 2026-09-10
  - #1681 (end attack missions), 2026-09-12
  - #1688 (tick-rate constants, part of #997), 2026-09-13
  - Source: [OpenApoc issues search](https://github.com/OpenApoc/OpenApoc/issues?q=UFO2P.EXE)
- The OpenApoc repo has 598 stars, the wiki enabled, and was last pushed 2026-09-16 — [OpenApoc/OpenApoc](https://github.com/OpenApoc/OpenApoc).
- **OpenApoc extractors** read data tables directly out of the executables — [ufo2p.h](https://github.com/OpenApoc/OpenApoc/blob/master/tools/extractors/common/ufo2p.h), [tacp.h](https://github.com/OpenApoc/OpenApoc/blob/master/tools/extractors/common/tacp.h):
  - From UFO2P: research, vehicles, organisations, raid loot, starting relationships, base layouts, agent types, vehicle equipment, facilities, economy and UFOpaedia string tables.
  - From TACP: damage types/modifiers, agent equipment/armor/weapons, equipment-set scores and bullet sprites.
  - The offsets are `*_OFFSET_START/END` constants. `tools/extractors/docs/` holds `ai.txt`, `algo.txt`, `hexa.txt` (e.g. "research data … UFO2P.EXE (13EE80) [28]"), `psionics.txt`, `strafe.txt`, `tactical.txt`, `tb.txt` and `wongFaq.txt`.
- **CRC mismatch:** OpenApoc expects UFO2P CRC32 `0x4749ffc1` ("the crc32 of the ufo2p.exe found on my steam version") — [ufo2p.cpp](https://github.com/OpenApoc/OpenApoc/blob/master/tools/extractors/common/ufo2p.cpp). The local Steam/GOG UFO2P.EXE has CRC32 `0xDBD3B41D`, and TACP.EXE `0x3EC9C268` [local scan].
- **UFOpaedia:**
  - Technical pages: Audio Formats, Image Formats, Cityscape Files, Data Tables, Unit Stats, Damage Modifiers, Learning AI (EXPERIEN.DAT, BRAIN.DAT, WEAPEXP.DAT) and Known Bugs — [UFOpaedia Apocalypse](https://www.ufopaedia.org/index.php/Apocalypse).
  - Utilities page — [Utilities (Apocalypse)](https://www.ufopaedia.org/index.php/Utilities_(Apocalypse)):
    - Apoc'D 3.06c (J'ordos; savegame and mechanics editor)
    - Apatcher 1.5 (J'ordos; UFO timers, hire pool, unlocks the hidden Cityscape Editor)
    - RoadWar Utility 1.12
    - ApocUtil 1.0 (Scott T Jones)
    - PCK Manipulator 1.3
    - XME 0.8
    - Midnight Editor (Marcin Wichary; mexcomap.zip)
- **Cut features** — [Cut mechanics (Apocalypse)](https://www.ufopaedia.org/index.php/Cut_mechanics_and_features_(Apocalypse)):
  - The hidden map editor is enabled by hex-editing UFO2P.EXE and adding CITydemo to UFODATA (found by j'ordos).
  - A debug build existed in late 1996 (Al Giovetti).
  - Cut or stripped features: diplomacy, spies, swimming/climbing, multiplayer and a scenario generator.
- **Cheat codes** from "Keys.doc" (beta/debug builds) "have been fully stripped off the UFO2p.exe and TACP.exe" — [Cheat Codes (Apocalypse)](https://www.ufopaedia.org/Cheat_Codes_(Apocalypse)).
- **Two builds in the wild:** UFOpaedia warns about DOS vs Pentium ("P") versions of the executables in TACEXE/UFOEXE — [Known Bugs (Apocalypse)](https://www.ufopaedia.org/Known_Bugs_(Apocalypse)).
- **Debug strings** in the shipped EXEs [local scan]:
  - Both: "Debug Autosave", "Debug Text String (list31)>-".
  - TACP only: "DEBUG - turns off the frame count thing.", "debug) Validating Map".

### Inferences
- The CRC difference means at least two UFO2P.EXE builds exist: OpenApoc's reference and the current Steam/GOG one.
  - Before reusing OpenApoc offsets or andremmfaria's `FUN_` addresses, ReverseApoc must check which build they refer to.
  - The current Steam and GOG builds are byte-identical, so they are the natural target.
  - The "P" (Pentium) suffix in UFO2P/TACP/SMKP implies a non-P (486/DOS) build also existed. It may be another candidate, or the source of the CRC difference.
- Ghidra `FUN_000xxxxx`/`0x0016xxxx` addresses fall within the object bases (code 0x10000+, data 0xD0000+). This is consistent with an LE loader that maps objects at their preferred bases. The ReverseApoc symbol map should use the same base so community addresses transfer directly.
- OpenApoc's data-table offsets give ready-made struct definitions and data-object labels, which speeds up splitting the data object.

### Gaps
- I found no publicly shared Ghidra/IDA database for UFO2P/TACP.
- The OpenApoc wiki contents and Discord were not reviewed (Discord is not web-accessible).
- I did not determine which build OpenApoc's CRC `0x4749ffc1` is (original CD, patch, or older Steam). It is also unknown which build andremmfaria's addresses use.
- I found no authoritative primary source (developer interview) for "the AI being unfinished." OpenApoc's `ai.txt` documents behavior, but I did not verify claims about it being unfinished.

## Q5. decomp.me and objdiff support for Watcom/OMF

### Takeaway
decomp.me supports Watcom on its `msdos` platform with wcc/wpp 10.0a, 10.5, 10.5a, 10.6 and 11.0. objdiff does NOT natively read OMF: the issue has been open since 2024-08-19. Projects convert OMF→ELF (Theme Hospital) or use custom diff scripts (KKND, NHL95PC).

### Cited Findings
- **decomp.me** — [compilers.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/compilers.py) (last commit 2026-10-14), [platforms.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/platforms.py), [flags.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/flags.py):
  - Compiler IDs on `platform=MSDOS`:
    - `wcc10.0a`, `wpp10.0a`
    - `wcc10.5`, `wpp10.5`
    - `wcc10.5a`, `wpp10.5a`
    - `wcc10.6`, `wpp10.6`
    - `wcc11.0`, `wpp11.0`
    - plus `bcc2.0`, `bcc3.1` and `msc5.1`
  - Invocation: `${WIBO} "${COMPILER_DIR}/binnt/wcc386.exe" -zq -i=".../h" -i=".../h/nt" ${COMPILER_FLAGS} -fo...`, with `/`→`\` path rewriting.
  - The MSDOS platform uses `jwasm` as its assembler, `omf-objdump --no-objects` and `omf-nm`, with a `--reloc` diff flag.
  - Watcom flag UI:
    - codegen `-0/-1/-2/-3r/-3s/-4r/-4s/-5r/-5s/-6r/-6s`
    - packing `-zp1/2/4/8`
    - platform `-bt=nt/-bt=dos`
    - checkboxes `-od -os -ot -of+ -or -oi -om -ol -on -op -s -j -fpi87`
- **objdiff:**
  - Latest release v3.8.2 (2026-09-29). Supported arches include "x86, x86_64 (PC)". No OMF in its supported formats — [encounter/objdiff](https://github.com/encounter/objdiff).
  - Issue #97 "Support OMF object format" is open (since 2024-08-19); it notes OMF would enable "Borland, really old MSVC, and Watcom targets."
  - Workarounds referenced in the issue: OmniBlade's OMF binutils fork (used for decomp.me's objdump), sillyc0n's binutils 2.42 OMF port, and tomsons26's objconv fork. An upstream request was filed at gimli-rs/object#736 — [objdiff#97](https://github.com/encounter/objdiff/issues/97).
  - Theme Hospital uses objdiff-cli 3.8.1 through its own OMF→ELF converter — [theme-hospital-decomp](https://github.com/matteo-pacini/theme-hospital-decomp).

### Inferences
- decomp.me scratches for UFO2P functions can be made today. Try `wcc10.6` and `wcc10.5` first, then `wcc11.0`.
  - Starting flags are `-5r` or `-4r`, `-s`, an `-o*` subset, and `-zp1`/`-zp4` to be determined.
  - The 10.5 vs 10.6 split on decomp.me may yield identical code, per mosura.
- For local work, an OMF→ELF converter (like Theme Hospital's) is the shortest path to objdiff and decomp.dev-style progress reporting.

### Gaps
- I did not determine whether decomp.me's `msdos` platform has a preset for any Watcom game (presets were not checked).
- I did not verify how decomp.me handles `-zm` or `-d2` (they are not in the flag UI, but can presumably be typed as custom flags).
