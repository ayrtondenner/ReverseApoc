# Own-pipeline reuse inventory for ReverseApoc (UFO2P.EXE / TACP.EXE, Watcom 10.x, DOS/4GW LE)

All sources were read through the GitHub API (`gh api`) and raw.githubusercontent.com on 2026-10-19. Nothing was cloned, executed or installed. Line counts are `wc -l` of the raw files on the default branch on 2026-10-19. Abbreviations: TH = matteo-pacini/theme-hospital-decomp, KK = Wyrelade/KKND-Decomp, RK = nemo22/retrokit.

Note: plan mode was active, so these notes were saved here and not to the scratchpad research_notes path.

## Q1. Theme Hospital decomp: what tools exist, their license, and what would need to change

### Takeaway
TH has the most complete Watcom/LE/objdiff pipeline of the three: configure.py, ninja, wibo, Watcom 10.6, OMF-to-ELF, objdiff, a full LE re-writer and a source-variant search. It is all GPLv3 and lives inside the game repo, not in a separate package. It builds with Nix, not Docker. Its LE writer rebuilds the whole EXE from scratch and has Theme Hospital constants hardcoded, so it is the hardest part to lift. omf2elf.py, cc.py, configure.py, check.py, verify.py/elfrelocs.py and variants.py are the most reusable parts.

### Cited Findings
- Repo metadata: created 2026-10-02, last push 2026-10-16, 223 commits, 1 star. The GitHub license field reads "Other". [GitHub API](https://api.github.com/repos/matteo-pacini/theme-hospital-decomp) (2026-10-19)
- License split: "The project's own work (the build system and tools in tools/, configure.py, nix/, the configuration in config/ and the documentation) is licensed under the GNU General Public License, version 3 or any later version". `src/` and `include/` are not covered and no rights in them are claimed. [LICENSE](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/LICENSE) (2026-10-19)
- The tools are inside the repo under `tools/`. No separate package exists. [README Layout](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/README.md) (2026-10-19)
- Status claim: "As of 2026-09-30, `ninja report` counts all 2938 functions matched (100% of code bytes)". 53 of these are assembly stand-ins (`*.standin.s`) and 79 come from Watcom's own runtime libraries. [README](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/README.md)
- Two builds: `tools/lewrite.py --strict` writes a byte-identical `build/hospital.exe` ("writes the headers, fixup tables and the DOS/4GW stub of the Watcom 10.5 toolchain itself"). `ninja link` (tools/link.py plus Open Watcom wlink) writes a working but non-identical EXE. [README](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/README.md)
- Toolchain is a Nix flake: Watcom 10.6 and 10.0a (Win32 host binaries), wibo 1.2.0, objdiff-cli 3.8.1, rizin with rz-ghidra, and Open Watcom v2 `wdis`. Compiler flags for the game are `wpp386 -s -ot -d2 -zm`. [README Toolchain](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/README.md)
- The flake pins wibo 1.2.0 because "nixpkgs ships wibo 0.6.14 (i686-only), which cannot run Watcom ('Unhandled function LocalAlloc')". The compilers come from `https://github.com/OmniBlade/decomp.me/releases/download/wcc10.5/wcc10.6.tar.gz` and `https://github.com/decompme/compilers/releases/download/compilers/wcc10.0a.tar.gz`. The runtime libraries come from WinWorld CD images. [nix/flake.nix](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/nix/flake.nix) (2026-10-19)
- No Dockerfile is in the tree. The only build environment is `nix/flake.nix`. [git tree](https://api.github.com/repos/matteo-pacini/theme-hospital-decomp/git/trees/master?recursive=1) (2026-10-19)
- LE/OMF format documentation: there is no standalone format document. The formats are explained in module docstrings (lefile.py, lewrite.py, omf2elf.py). docs/MATCHING.md (58 KB) covers compiler behaviour, idioms, static data layout and COMDAT placement, not file formats. [docs/MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md) (2026-10-19)

**TH tool inventory (all Python 3, GPLv3-or-later):**

| File | Lines | What it does | Platform/game specificity | Change for ReverseApoc |
|---|---:|---|---|---|
| `configure.py` | 177 | Writes build.ninja, objdiff.json (units, categories, `base_path`/`target_path`) and compile_commands.json. Checks EXE SHA-1. | Medium: categories, unit model and EXE path come from project.py | Replace project model, two EXEs (UFO2P/TACP), categories |
| `tools/project.py` | 236 | Reads config/functions.txt, symbols.txt, sections.txt, relocs.txt and demo maps. Scans `// FUNCTION: 0xADDR` markers into units, plus auto units for unclaimed code | High: demo-map logic, `GAME_END`, CODE16 | Rewrite to a simpler model (no demo map) |
| `tools/cc.py` | 131 | Compiles with wpp386/wcc386 under wibo, converts OMF to ELF, applies stand-ins. Per-file flags from glob rules in config/cflags.txt, versions selected with `compiler@version` | Low: generic | Nearly as-is (env var names, Docker paths) |
| `tools/omf2elf.py` | 589 | Converts Watcom OMF to ELF32 (see Q5). Also `write_omf` and `library_module` (extracts a module from a .LIB) | Low: generic Watcom | Nearly as-is |
| `tools/lefile.py` | 130 | LE reader: object table, loaded bytes, internal fixups resolved to linear addresses | Low, but assumes data pages are file-absolute (no bound-stub offset) and raises on fixup source lists | Add bound DOS/4GW Pro stub offset (KK le.py has it) |
| `tools/lewrite.py` | 433 | Rebuilds the full EXE: code and data from units, linker filler table, fixup records in linker processing order packed into 512-byte blocks written newest first, regenerated headers, page map and name tables, WSTUB.EXE 10.5 stub | Very high: hardcoded `CODE_BASE`, `DATA_VSIZE=0x79F30`, `OBJECT4_VSIZE`, `LINKED_AFTER`, module name "MAIN", Watcom 10.5 stub | Not needed for the MVP (use KK in-place splice) |
| `tools/relink.py` | 457 | Places every unit's code at its original address and compares bytes and fixup targets with the EXE. Reports gaps | High | Later phase only |
| `tools/split.py` | 295 | Writes one GNU `as` source per unit from the EXE (each function its own `_TEXT` section, LE fixups become R_386_32 and rel32 branches become R_386_PC32). These are objdiff's *target* objects | Medium | Adapt (unit model, data refs) |
| `tools/x86scan.py` | 129 | Instruction scan that treats fixup sites inside code (switch tables) as data | Low | As-is |
| `tools/discover.py` | 123 | Builds functions.txt from rizin analysis, rel32 call targets, Watcom prologues and demo-identified library functions | Medium-high (rizin, demo) | Replace with Ghidra/retrokit or KK find_functions |
| `tools/check.py` | 94 | Builds one file's unit in a temp dir and prints per-function match. Safe to run alongside ninja | Medium | Adapt |
| `tools/verify.py` / `tools/elfrelocs.py` | 38 / 93 | Catch relocation mismatches objdiff misses ("objdiff compares at most one relocation per x86 instruction") | Low | As-is |
| `tools/variants.py` | 534 | Beam search over source rewrites (operand swaps, declaration order, `op=`, types, blocks, zero tests, if/else, local reuse) scored by objdiff | Low-medium | Adapt (high value for AI loop) |
| `tools/standin.py` / `asm2src.py` | 364 / 334 | Assembly stand-ins for functions that won't match from C | Medium | Optional, later |
| `tools/link.py` | 315 | wlink build that produces a runnable non-identical EXE | High | Out of MVP scope |
| `tools/fn.py`, `setfn.py`, `progress.py`, `format.py`, `libunit.py`, `demangle.py` | 76 / 52 / 27 / 82 / 114 / 14 | Viewer, config editor, progress summary, clang-format with pragmas kept, library-module check, C++ demangle | Low-medium | Optional |
| `tools/variants.py` + `AGENTS.md` (72) | n/a | Agent instructions | n/a | Model for CLAUDE.md |

### Inferences
- Reusing any TH tool file means ReverseApoc's tooling must be distributed under GPLv3 (or later). Mixing TH files with KK (CC0) and RK (Apache-2.0) is allowed one way: Apache-2.0 and CC0 code can go into a GPLv3 work, not the other way. Decide on the tooling license before copying anything from TH.
- TH targets an unbound stub (README says `DOS4GW.EXE` ships separately and lewrite writes `WSTUB.EXE`). ReverseApoc's EXEs are reported as bound DOS/4GW Professional, so TH's LE offset assumptions need KK's bound-stub fix.
- TH is C++ (`wpp386`). If Apocalypse is C (`wcc386`), COMDAT handling is still harmless but less exercised.

### Gaps
- I did not read full bodies of split.py, relink.py, variants.py or the rest of lewrite.py. The line counts and docstrings are verified, but the internal coupling of each function to TH is estimated from docstrings and imports.
- Whether TH's 100% claim was independently reproduced: no third-party confirmation found.

## Q2. KKND-Decomp: what tools exist, their license, and what would need to change

### Takeaway
KK (CC0) is the closest match to ReverseApoc's MVP. It targets a bound DOS/4GW Professional LE built with Watcom 10.x. It does per-function splice-and-verify into a copy of the original EXE with a whole-file SHA-1 check, and its LE reader already handles the bound-stub offset. Its OMF reader is minimal (no COMDAT, no ELF output). It has no ninja, no objdiff objects and no Docker. It uses a patched Open Watcom instead of real Watcom 10.x.

### Cited Findings
- Repo metadata: CC0-1.0, created and last pushed 2026-09-24, 10 commits, 8 stars. [GitHub API](https://api.github.com/repos/Wyrelade/KKND-Decomp) (2026-10-19)
- Target: "MZ stub + DOS/4GW Pro + Linear Executable (LE), 3 objects, 20,192 fixups". Flags `-s -of+ -5r -omiler -zm -zp1`. Progress 492/3713 functions (13.25%). [README](https://github.com/Wyrelade/KKND-Decomp/blob/main/README.md) (2026-10-19)
- The splice works on a copy of the original. build_kknd.py does `out = bytearray(le.data)` and overwrites only page bytes from the patched object images, then compares SHA-1 with `configs/DOS/KKND.EXE.sha1`. Headers, fixup tables and stub are never regenerated. Relocated fields keep the original link-time value after the relocation *target* has been checked. [tools/build_kknd.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/build_kknd.py) (2026-10-19)
- Verification rules in build_kknd.py:
  - every non-relocated byte must be identical and the length must be equal;
  - every `call rel32` must hit the same function;
  - every absolute fixup must match the original LE fixup target;
  - local-segment references (string literals) are rejected ("move data to an extern D_ symbol");
  - switch tables at the start of a `-zm` segment are handled.
  [tools/build_kknd.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/build_kknd.py)
- le.py handles bound DOS/4GW Pro: "Data-page offset is relative to the MZ stub that owns this LE header (the bound DOS/4GW loader sits in front of it). For KKND.EXE that stub is at 0x26654". It parses fixup source lists and raises `NotImplementedError` on non-zero page flags (iterated or zero pages) and on non-internal fixups. [tools/le.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/le.py) (2026-10-19)
- Compiler: "Watcom C/C++32 (runtime banner '1988-1994', i.e. Watcom 10.0/10.0a class)". They match with a patched Open Watcom 2.0 `wcc386` (switch tables through `cs:`, Watcom 10 switch costs, no loop alignment, no jump threading, bottom-test loops, EBX before ECX, multiply costs). The patch is 506 lines against OW commit 91922ea. [COMPILER_ANALYSIS.md](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/COMPILER_ANALYSIS.md), [doc/compiler_patch.md](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/doc/compiler_patch.md) (2026-10-19)
- Toolchain is native Open Watcom found through `$WATCOM` or hardcoded paths such as `D:/programs/re/openwatcom/patched`. There is no wibo, no Docker and no ninja. The only Python dependency is `capstone>=5.0`. [tools/match.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/match.py), [requirements.txt](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/requirements.txt)
- objdiff integration covers progress only: make_report.py writes an objdiff v2 report.json for decomp.dev from committed CSVs. A function "defined in C" is counted as matched because the build gate refuses anything else. No ELF objects are produced for objdiff diffing. [tools/make_report.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/make_report.py), [.github/workflows/progress.yml](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/.github/workflows/progress.yml)

**KK tool inventory (Python 3 plus one bash script, CC0-1.0):**

| File | Lines | What it does | Specificity | Change for ReverseApoc |
|---|---:|---|---|---|
| `tools/le.py` | 201 | LE reader: bound-stub offset, object table, page map, fixups including source lists, `load(relocate=)` | Low | Nearly as-is. Add support for iterated/zero page flags if UFO2P/TACP use them |
| `tools/omf.py` | 224 | OMF reader: LNAMES, SEGDEF, GRPDEF, EXTDEF/LEXTDEF, COMDEF, PUBDEF/LPUBDEF, LEDATA, LIDATA, FIXUPP (threads). `functions()` cuts out each public in CODE segments | Low | Adapt: add COMDAT (0xC2), CEXTDEF and BAKPAT if needed |
| `tools/build_kknd.py` | 203 | Compile, cut, verify bytes and reloc targets, splice in place, rewrite pages, SHA-1 gate | Low-medium (paths, `func_`/`D_` naming, single EXE) | Adapt: loop over two EXEs, config paths |
| `tools/match.py` | 190 | Per-function compile and diff (capstone side-by-side), Watcom env discovery, `compile_c` that works around `/` and spaces in paths | Medium (native OW paths) | Adapt: call wibo plus Watcom 10.x in Docker |
| `tools/find_functions.py` | 193 | Capstone recursive descent seeded from entry, data-to-code fixups and immediates. Reads switch tables through fixups, does gap scanning and padding trimming. Writes functions.csv and code_data.csv | Low | Nearly as-is (Ghidra-independent cross-check) |
| `tools/split.py` | 129 | One Intel-syntax `.s` per function with symbolic operands. A reading aid only: "the build does not assemble it" | Low | As-is |
| `tools/gen_units.py` | 85 | Unit ranges from `__FILE__` strings; `--write-src` writes `src/*.c` with one `INCLUDE_ASM` per function | Medium (relies on `__FILE__` strings) | Adapt the unit heuristic |
| `tools/land.py` | 42 | Replaces `INCLUDE_ASM(...)` with matched C | Low | As-is |
| `tools/score_functions.py` | 71 | Ranks the easiest unmatched functions | Low | As-is |
| `tools/auto_families.py` | 141 | Auto-matches trivial families (return-constant, forwarders) and keeps only verified ones | Low | As-is |
| `tools/lib_match.py` | 115 | Masked-byte matching of OMF library modules (e.g. clib3r.lib) to label runtime functions | Low | As-is |
| `tools/name_evidence.py` | 68 | Function names from `Name(): ...` diagnostic strings | Low | As-is |
| `tools/make_report.py` / `update_readme_progress.py` | 134 / 101 | decomp.dev report and README badge | Low-medium | Adapt |
| `tools/learn.py` | 96 | Ranked section search over DECOMPILATION_LEARNINGS.md | Low | As-is |
| `tools/build-and-verify.sh` | 25 | Gate wrapper | Low | As-is |
| `tools/owpatch/kknd-wcc386.patch` | 506 | Patched OW 2.0 code generator | n/a | Reference only if real 10.x won't match |
| `CLAUDE.md`, `DECOMPILATION_LEARNINGS.md`, `CODEGEN_MODEL.md`, `tools/difficult_functions` | n/a | Agent rules, journal, codegen model, give-up list | n/a | Template |

### Inferences
- KK's in-place approach is byte-identical by construction for unmatched bytes. For a "keep SHA-1 identical" MVP it is far less work than TH's full rewrite.
- KK's Watcom 10.0a diagnosis paired with OW patching suggests the author did not use the real Watcom 10.0a binaries. Those binaries exist as `wcc10.0a` in decomp.me's compiler set, and TH uses them. ReverseApoc should start with the real 10.x binaries under wibo.
- learn.py's docstring describes a "1.3 MB corpus of ~1,275 sections" and MIPS terms ("delay slot lhu"). The file was evidently copied from another (DW2, MIPS) project, so KK's own journal is far smaller.

### Gaps
- KK's PLAN.md, DECOMPILATION_LEARNINGS.md and CODEGEN_MODEL.md were not read in full.
- No evidence of KK running its tools in CI beyond the report job.

## Q3. retrokit, ghidra-lx-loader, decomp.me cromper, and Dockerfiles

### Takeaway
retrokit (Apache-2.0, Python CLI plus Java Ghidra scripts and its own Java LE loader, v0.2.0, 6 days old) is an *analysis* toolkit, not a matching toolkit. It runs headless Ghidra 12 with Watcom cspecs, creates functions from fixups, applies Open Watcom library signatures, exports `functions.csv`/`fixups.txt`/decompiled C, and serves all of it to agents over MCP. It has no INCLUDE_ASM or per-function splitting. Its exported "size" is a Ghidra body-address count, so it needs post-processing into contiguous ranges. None of the projects ships a Dockerfile. decomp.me's cromper is the reference for wibo plus Watcom (MIT).

### Cited Findings
- retrokit metadata: Apache-2.0, Python, created 2026-10-13, last push 2026-10-15, 22 commits, 31 stars. [GitHub API](https://api.github.com/repos/nemo22/retrokit) (2026-10-19). CHANGELOG lists 0.1.0 and 0.2.0, both dated 2026-10-14. [CHANGELOG.md](https://raw.githubusercontent.com/nemo22/retrokit/main/CHANGELOG.md)
- Requirements: "Ghidra 12.x (unpacked), a JDK 21+ (`JAVA_HOME`), Python 3.10+". `retrokit install-loader` compiles the loader with `javac` against the installed Ghidra. [README](https://github.com/nemo22/retrokit/blob/main/README.md) (2026-10-19)
- Workspace output: `decomp/<exe>_decompiled.c`, `functions.csv (addr,name,size,callers,callees,cc,signature)`, `calls.txt`, `strings.txt`, `data_symbols.txt`, `memory_blocks.txt` and `fixups.txt`. Names go back in through `notes/names_*.csv` and `retrokit names`. [README](https://github.com/nemo22/retrokit/blob/main/README.md)
- Size semantics: `long size = f.getBody().getNumAddresses();` (Ghidra body size, not start-to-next-start). [ExportDecompiled.java](https://raw.githubusercontent.com/nemo22/retrokit/main/retrokit/ghidra_scripts/ExportDecompiled.java) (2026-10-19)
- LE pipeline steps:
  - functions at the targets of 32-bit fixups into code, with switch tables kept inside their functions (`CreateFunctionsFromFixups.java`, 204 lines);
  - `CreateFunctionsAtEntries.java` (275 lines) for given addresses, fixups or prologues in gaps;
  - FixTruncatedCallers;
  - library signatures (exact plus fuzzy);
  - stack-convention parameter counts;
  - prototypes recovered bottom-up;
  - export.
  [README](https://github.com/nemo22/retrokit/blob/main/README.md), [docs/WORKFLOW.md](https://raw.githubusercontent.com/nemo22/retrokit/main/docs/WORKFLOW.md)
- Library signatures shipped: Open Watcom 2.0 and 1.9 clib3/math387/plib3, zlib, libjpeg. "on a 1994 Watcom 10.0 program it raised the named run-time from 17 to 73 functions" with the fuzzy tier. [docs/WORKFLOW.md](https://raw.githubusercontent.com/nemo22/retrokit/main/docs/WORKFLOW.md)
- LE loader (Java, `LinearExecutableLoader.java` 496 lines plus `LinearImage.java` 513 lines, own LICENSE). It supports DOS/4GW, DOS/32A, PMODE/W, CauseWay and DOS/4G "BW"-bound files ("its LE offsets are relative to that program's MZ header"). It ships `watcom` (stack) and `watcomreg` (register) cspecs. Not supported: Watcom debug info, PMODE/W compressed, LX EXEPACK2. [le-loader/README.md](https://raw.githubusercontent.com/nemo22/retrokit/main/retrokit/le-loader/README.md) (2026-10-19)
- Python LE model: `retrokit/formats.py` (467 lines, `identify()`, `LinearExecutable` with pages, fixups and iterated-page expansion) and `retrokit/tools/le.py` (122 lines). Both are Apache-2.0. [formats.py](https://raw.githubusercontent.com/nemo22/retrokit/main/retrokit/formats.py)
- MCP server: `retrokit/mcp_server.py` (755 lines, stdio, no extra packages). Tools: workspace_info, libraries, list_functions, get_function, call_graph, xrefs, search_code, strings, pointer_tables, disassemble, read_bytes, propose_names, write_note, reexport. [docs/AGENT_PROMPTS.md](https://raw.githubusercontent.com/nemo22/retrokit/main/docs/AGENT_PROMPTS.md)
- Maturity evidence: the test corpus is small synthetic Open Watcom programs (the baseline shows `own_total: 28`, `own_found: 28`, `lib_total: 130`, `lib_found: 120` per variant). CI runs on Windows and Linux. [tests/baseline.json](https://raw.githubusercontent.com/nemo22/retrokit/main/tests/baseline.json). The README says most of the code was written by Claude through Claude Code. [README](https://github.com/nemo22/retrokit/blob/main/README.md)
- lastonesky/ghidra-lx-loader:
  - Java Ghidra extension, Apache-2.0, a fork of yetmorecode/ghidra-lx-loader (85 stars). Releases v12.1.4 (2026-10-09) and v12.1.4-1 (2026-10-10), asset `ghidra_12.1.4_PUBLIC_20261010_ghidra-lx-loader.zip`.
  - Requires Ghidra 12.1.x. It does full page-map and fixup support, typed headers, overlays for MZ/LX header/loader/fixup/data sections, optional per-fixup and per-page labels, and base-address overrides. It ships `watcom.cspec`.
  - It is a loader only, with no export scripts. Its "export" is the Ghidra program itself.
  - Its README lists "X-Com: Apocalypse (UFO2P.EXE - DOS/16 LE and unbound LE-style)" as tested. This line is inherited from upstream.
  [GitHub API](https://api.github.com/repos/lastonesky/ghidra-lx-loader), [README](https://raw.githubusercontent.com/lastonesky/ghidra-lx-loader/master/README.md) (2026-10-19)
- decomp.me cromper (MIT):
  - `compilers.py` (2023 lines) defines `WatcomCompiler` ids wcc10.0a, wpp10.0a, wcc10.5, wcc10.5a, wcc10.6 and wcc11.0 (plus the C++ variants).
  - The command is `${WIBO} "${COMPILER_DIR}/binnt/wcc386.exe" ... -zq -i="Z:${COMPILER_DIR}/h" ... -fo"Z:${OUTPUT}" "Z:${INPUT}"` with `/` converted to `\` by `sed`. The comment says "Watcom doesn't like '/' in paths".
  - The Dockerfile installs wibo with `COPY --from=ghcr.io/decompals/wibo:1.2.0 /usr/local/bin/wibo /usr/bin/` and pulls OMF tools (jwasm from OmniBlade/binutils-gdb, `omf-nm`/`omf-objdump` from decompals/binutils-omf v0.4).
  - Compilers are downloaded from the `decompme/compilers` registry (`compilers/download.py`).
  [compilers.py](https://github.com/decompme/decomp.me/blob/main/cromper/cromper/compilers.py), [cromper/Dockerfile](https://github.com/decompme/decomp.me/blob/main/cromper/Dockerfile), [compilers.linux.yaml](https://raw.githubusercontent.com/decompme/decomp.me/main/cromper/compilers/compilers.linux.yaml) (2026-10-19)
- Dockerfiles: none in TH (Nix flake only), none in KK, none in retrokit (pipx), none in ghidra-lx-loader (Gradle). Verified from the recursive git trees on 2026-10-19 ([TH](https://api.github.com/repos/matteo-pacini/theme-hospital-decomp/git/trees/master?recursive=1), [KK](https://api.github.com/repos/Wyrelade/KKND-Decomp/git/trees/main?recursive=1), [RK](https://api.github.com/repos/nemo22/retrokit/git/trees/main?recursive=1)).

### Inferences
- For ReverseApoc's Dockerfile, combine:
  - cromper's wibo line (`COPY --from=ghcr.io/decompals/wibo:1.2.0`);
  - TH's compiler tarball URLs (wcc10.6 from OmniBlade/decomp.me, wcc10.0a from decompme/compilers);
  - objdiff-cli from the encounter/objdiff release.
  This is about a 40-60 line Dockerfile written new.
- Ghidra 12 plus JDK 21 for retrokit can run on the host (Windows) or in a separate container. Putting them in the compile image would bloat it.
- The lx-loader README claim that UFO2P.EXE is "DOS/16 LE and unbound" conflicts with the brief ("DOS/4GW Professional bound"). Check the actual MZ/BW chain of the local UFO2P.EXE/TACP.EXE before choosing the LE offset logic. KK le.py and RK formats.py both handle the bound case.

### Gaps
- I did not test whether retrokit's fixup-seeded discovery reaches full coverage on a real Watcom 10.x game. Its published numbers are only on synthetic programs.
- I could not verify the internal license header of `retrokit/le-loader/LICENSE` beyond its size (11357 bytes, the same as the Apache-2.0 LICENSE at the root).

## Q4. Which LE parser/writer is cleanest to lift; in-place patch vs full rebuild

### Takeaway
Lift KK's `tools/le.py` (201 lines, CC0) together with the in-place splice from `build_kknd.py`. Neither KK nor RK regenerates headers. Only TH's `lewrite.py` rebuilds the LE header, page map and fixup records byte-identically, and it needs hardcoded TH constants plus a 457-line `relink.py` to do so. In-place patching of a copy of the original EXE is far less work: about 1-3 days versus about 10-20+ days for a full rebuild. It is sufficient while every unmatched function keeps its original bytes and every matched function has the same size.

### Cited Findings
- KK in place: `out = bytearray(le.data)`, then `out[fo:fo + len(chunk)] = chunk` per page, then the SHA-1 compare. [build_kknd.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/build_kknd.py)
- TH full rebuild: "Each page's fixup records are generated in the order the original linker processed them... packed into 512-byte blocks written newest first... The LE header, object table, page map, name tables, fixup page table and import tables are computed". It uses constants "that came from the original rather than from a unit: CODE_BASE, DATA_VSIZE, OBJECT4_VSIZE and LINKED_AFTER" and a 15-entry linker filler table. [lewrite.py](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/tools/lewrite.py)
- TH lefile.py reads `data_pages = hdr(0x80)` with no stub offset and raises `NotImplementedError("fixup source lists")`. KK le.py adds `_find_stub()` and parses source lists. [lefile.py](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/tools/lefile.py), [le.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/le.py)
- RK formats.py has an Apache-2.0 LE reader with BW-bind handling and iterated-page expansion (`_expand_iterated`), but no writer. [formats.py](https://raw.githubusercontent.com/nemo22/retrokit/main/retrokit/formats.py)

### Inferences
- MVP: KK le.py nearly as-is, with RK's `_expand_iterated` grafted in (license-compatible) if UFO2P/TACP have iterated pages.
- TH-style regeneration only matters once ReverseApoc wants shiftable or relinkable builds. Even then, TH's `link.py` (wlink) route gives a runnable modded EXE without byte-identical regeneration.

### Gaps
- Unknown until tested locally: whether UFO2P/TACP have non-internal fixups, iterated pages or 16-bit objects (the brief says two objects each).

## Q5. Which OMF reader exists, and how complete it is

### Takeaway
TH's `omf2elf.py` (589 lines, GPLv3) is the only complete Watcom OMF reader plus ELF writer found. KK's `omf.py` (224 lines, CC0) is a minimal reader without COMDAT or ELF output. No suitable PyPI package exists: PyPI `omf` is Open Mining Format. Other GitHub Python OMF parsers are small and either unlicensed or AGPL.

### Cited Findings
- TH omf2elf.py handles:
  - THEADR, COMENT (including weak/lazy externs and class), LINNUM/LINSYM/VERNUM/VENDEXT (skipped);
  - LNAMES/LLNAMES, SEGDEF, GRPDEF, EXTDEF/LEXTDEF/CEXTDEF, PUBDEF/LPUBDEF;
  - LEDATA, LIDATA (recursive);
  - COMDAT (weak symbols for pick-any; raises on iterated COMDAT or a frame number);
  - FIXUPP (threads; raises on a fixup to LIDATA or unknown location types);
  - BAKPAT, MODEND.
  It drops debug segments. It writes ELF with FUNC symbols sized to the next symbol, plus `read_elf`, `write_omf` and `library_module`. Its docstring says it covers "the records objconv drops or rejects". [omf2elf.py](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/tools/omf2elf.py) (2026-10-19)
- KK omf.py handles LNAMES, SEGDEF, GRPDEF, EXTDEF/LEXTDEF, COMDEF, PUBDEF/LPUBDEF, LEDATA, LIDATA and FIXUPP (thread plus fixup). It has no COMDAT (0xC2), no CEXTDEF, no BAKPAT and no writer. [omf.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/omf.py)
- PyPI `omf` 1.0.1: "API Library for Open Mining Format" (unrelated). `pyomf`, `omfutils`, `omf-parser` and `python-omf` return 404. [PyPI](https://pypi.org/pypi/omf/json) (2026-10-19)
- GitHub alternatives:
  - JohnVillalovos/omf_parser_py (no license, 2 stars, MS-DOS OMF);
  - HK47196/OMF-Parser (AGPL-3.0);
  - avwohl/pyle (GPL-3.0, a pure-Python OMF linker to MZ+LE with PMODE/W or DOS/32A stub).
  [GitHub search](https://api.github.com/search/repositories?q=OMF+relocatable+object) (2026-10-19)
- objdiff has no OMF support. A code search for "omf" in encounter/objdiff returned 0 results, which is why TH converts to ELF. [GitHub code search](https://api.github.com/search/code?q=omf+repo:encounter/objdiff) (2026-10-19)
- External binary option: decompals/binutils-omf (`omf-nm`, `omf-objdump`, GPL-2.0) as used in cromper. It is for inspection only. [cromper/Dockerfile](https://github.com/decompme/decomp.me/blob/main/cromper/Dockerfile)

### Inferences
- If GPLv3 is acceptable: copy TH omf2elf.py nearly as-is (about 1 day including tests).
- If permissive tooling is required: extend KK omf.py with COMDAT and an ELF32 writer (symbols, `.rel` sections, R_386_32/PC32). That is about 3-5 days written new, and longer if C++ COMDAT and weak semantics matter.

### Gaps
- The GitHub code-search result of 0 for objdiff could be an index artefact. I did not read objdiff's object-format list directly.

## Q6. Watcom-aware function splitting (Ghidra export to INCLUDE_ASM / per-function asm)

### Takeaway
None of the projects goes from a Ghidra export to INCLUDE_ASM stubs. KK has a Ghidra-free chain: capstone discovery (`find_functions.py`), then `gen_units.py --write-src` (INCLUDE_ASM per function), then `split.py` (per-function `.s`, reading aid only). TH's `split.py` emits *assemblable* per-unit GNU `as` with relocations for objdiff targets. retrokit gives a high-quality Ghidra function list but would need a small adapter (about 100-200 lines) to produce contiguous, padding-aware ranges.

### Cited Findings
- KK find_functions.py seeds from the entry point, data-to-code fixups and immediate fixups. It walks with capstone, reads `jmp [reg*4+table]` tables through fixups and scans gaps for prologues. Size is the distance to the next start minus trailing padding. [find_functions.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/find_functions.py)
- KK gen_units.py `--write-src` creates src files "with one INCLUDE_ASM per function". INCLUDE_ASM expands to `extern int INCLUDE_ASM_##name`, and the build keeps the original bytes. [gen_units.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/gen_units.py), [include/common.h](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/include/common.h)
- KK split.py: "The listing is a *reading* aid and the m2c/diff input; the build does not assemble it". [split.py](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/tools/split.py)
- TH split.py: "Each function goes in its own _TEXT section, mirroring wpp386 -zm output... LE fixups become R_386_32 relocations; rel32 branches leaving the section... become R_386_PC32". [split.py](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/tools/split.py)
- TH discover.py combines rizin analysis, rel32 call targets, Watcom prologues and demo identification. [discover.py](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/tools/discover.py)
- retrokit size is a Ghidra body count (see Q3).

### Inferences
- Recommended: run both retrokit (Ghidra) and KK find_functions.py, then diff the two lists. A small new `ghidra2functions.py` normalises Ghidra entries into start/end with padding trimmed, and feeds KK gen_units/split.

### Gaps
- No project here produces m2c-style C stubs. retrokit's decompiled C is the closest.

## Q7. Driver loop / AI integration that could be reused

### Takeaway
There is no autonomous driver loop or hooks in any of the three. What exists:
- agent instruction files (KK `CLAUDE.md`, TH `AGENTS.md`, RK `AGENTS.md` plus `docs/AGENT_PROMPTS.md`);
- a learnings journal and a search tool (KK `DECOMPILATION_LEARNINGS.md` plus `learn.py`);
- a give-up list (`tools/difficult_functions`) and an easiest-first ranker (`score_functions.py`);
- trivial-family auto-matching (`auto_families.py`);
- a variant beam search (TH `variants.py`, 534 lines);
- an MCP server over Ghidra output (RK `mcp_server.py`, 755 lines).

### Cited Findings
- KK CLAUDE.md workflow: pick with score_functions, iterate in scratch with match.py ("okay to give up after ~10 real attempts"), land, gate on `build_kknd.py` OK, record learnings, one function per commit, failures go to `tools/difficult_functions`. [CLAUDE.md](https://raw.githubusercontent.com/Wyrelade/KKND-Decomp/main/CLAUDE.md)
- TH AGENTS.md: matching steps, `variants.py` for near-misses, stand-ins as the last resort, and "Done" defined as report plus `lewrite --strict` plus `cmp`. [AGENTS.md](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/AGENTS.md)
- TH variants.py: beam search over swaps, decls, opassign, types, blocks, zero, adjacent, ifelse and reuse, scored by objdiff. [variants.py](https://raw.githubusercontent.com/matteo-pacini/theme-hospital-decomp/master/tools/variants.py)
- RK MCP plus AGENT_PROMPTS task templates (structure, generator, entities, renderer). Names are proposed as V/G CSVs. [docs/AGENT_PROMPTS.md](https://raw.githubusercontent.com/nemo22/retrokit/main/docs/AGENT_PROMPTS.md)

### Inferences
- A ReverseApoc driver loop (pick, attempt, verify, land or give up) must be written new. It is about 1-3 days on top of the KK scripts, which already provide every primitive. TH variants.py is the strongest single accelerator but is GPLv3.

### Gaps
- None of the repos documents Claude Code hooks or settings files.

## Q8. Effort estimate for the minimum viable own pipeline, and main risks

### Takeaway
Assembling the MVP takes about **13-24 developer-days**, roughly **15-20 days typical**, for one developer with Claude Code, if GPLv3 TH files may be copied. If the tooling must stay permissive (CC0 or Apache only), it takes about **17-28 days**. The main time sinks are:
- OMF-to-ELF plus building objdiff target objects from the EXE;
- validating LE quirks of UFO2P/TACP;
- getting Watcom 10.x running reliably under wibo in Docker on a Windows host.

### Cited Findings
- Component evidence is cited in Q1-Q7. Line counts are from raw files on 2026-10-19.

### Inferences
**Copy nearly as-is**
- KK `le.py` (201), `land.py` (42), `score_functions.py` (71), `auto_families.py` (141), `lib_match.py` (115), `name_evidence.py` (68), `learn.py` (96), `split.py` (129), `build-and-verify.sh` (25). All CC0.
- TH `omf2elf.py` (589), `elfrelocs.py` (93), `verify.py` (38), `x86scan.py` (129). All GPLv3.
- decomp.me cromper Watcom command line and wibo `COPY --from` line (MIT).
- RK as an external tool: pipx install, run as-is (Apache-2.0). Not vendored.
- objdiff-cli release binary.

**Adapt**
- KK `build_kknd.py` (203) to splice-and-verify for 2 EXEs.
- KK `match.py` (190) to call wibo plus Watcom 10.x in Docker.
- KK `omf.py` (224) only if TH omf2elf is not used.
- KK `find_functions.py` (193) and `gen_units.py` (85).
- KK `make_report.py` (134).
- TH `configure.py` (177), `cc.py` (131) and a cut-down `project.py` (236 down to about 100).
- TH `split.py` (295) for objdiff target objects.
- TH `check.py` (94) and `variants.py` (534).
- RK `formats.py` `_expand_iterated` if needed.

**Write new**
- Dockerfile (Ubuntu, wibo 1.2.0, Watcom 10.x tarballs, objdiff-cli, python, ninja, binutils `as`).
- `config/` schema for two EXEs.
- `ghidra2functions.py` adapter (retrokit `functions.csv` to contiguous ranges, cross-checked against KK discovery).
- Two-EXE orchestration and SHA-1 manifests.
- Driver loop and CLAUDE.md rules.
- If permissive-only: an ELF writer and target-object builder in place of TH omf2elf/split.

**Effort table (developer-days, one developer plus Claude Code)**

| # | Component | Copy as-is | Adapt | Write new | Days (GPL path) | Days (permissive-only) |
|---|---|---|---|---|---:|---:|
| 1 | LE parser + byte-identical output (in-place splice) | KK le.py | page-flag/iterated support (RK formats.py idea), bound-stub check for UFO2P/TACP | SHA-1 manifests for 2 EXEs | 1.5-3 | 1.5-3 |
| 2 | OMF reader + OMF-to-ELF + objdiff target objects | TH omf2elf.py, elfrelocs.py, verify.py | TH split.py (target `.s` to ELF) | (permissive: ELF writer + COMDAT on KK omf.py; ELF target writer) | 3-6 | 6-10 |
| 3 | configure.py + ninja + per-file flags + Docker/wibo/Watcom 10.x | cromper wibo line, compiler URLs | TH configure.py, cc.py, project.py (slimmed) | Dockerfile, Windows/Docker Desktop path glue | 2.5-4 | 3-5 |
| 4 | Per-function splice-and-verify, whole-EXE SHA-1 | KK land.py, build-and-verify.sh | KK build_kknd.py, match.py (C/C++ naming, two EXEs, data/string refs policy) | none | 2-3 | 2-3 |
| 5 | Ghidra function discovery + symbol export | retrokit (external), KK find_functions.py | KK gen_units.py, split.py | ghidra2functions.py adapter, list cross-check | 2.5-4 | 2.5-4 |
| 6 | Integration, progress report, CLAUDE.md, driver loop | KK learn.py, score_functions.py, auto_families.py | KK make_report.py, TH check.py (and variants.py, GPL path only) | driver loop, rules | 1.5-4 | 2-3 |
| | **Total** | | | | **13-24** | **17-28** |

**Main risks**
- *Compiler identity.* Real Watcom 10.0a/10.5/10.6 may still not match (KK had to patch OW). Real binaries via decomp.me's wcc10.x reduce this risk. C vs C++ (`wcc386` vs `wpp386`) for Apocalypse is unconfirmed. This is outside the pipeline estimate and could add weeks of matching research.
- *wibo compatibility.* Only wibo 1.2.0 is known to run Watcom (TH, cromper). On Windows 10 the build needs Docker Desktop with WSL2, or native Watcom binnt.
- *LE quirks of UFO2P/TACP.* Possible iterated or zero pages, non-internal fixups or 16:16 fixups would trip both KK and TH readers (both raise `NotImplementedError`). The lx-loader README calls UFO2P "DOS/16 LE and unbound", which contradicts the "bound DOS/4GW Pro" assumption.
- *objdiff limits.* It compares at most one relocation per instruction (TH needs `verify.py`). Without OMF support, conversion to ELF is mandatory.
- *Data and string references.* KK refuses local-segment references, so string literals must stay `extern D_` until data placement is modelled. TH solved this with config/sections.txt, which adds days later.
- *Maturity.* TH is about 2.5 weeks old with a single maintainer. KK has 10 commits. retrokit is 6 days old (v0.2.0) and validated only on synthetic programs. Expect bugs and pin commit SHAs.
- *License.* Any TH file makes ReverseApoc's tooling GPLv3.
- *Function discovery.* A boundary error between Ghidra and capstone breaks the splice size check. Budget time to reconcile the two lists.

### Gaps
- The estimates are judgement based on line counts and docstrings. None of the code was executed against UFO2P/TACP, which was not allowed.
- No public data on how long TH or KK took to build their pipelines, apart from repo ages (TH created 2026-10-02 with 100% claimed for 2026-09-30, implying earlier private work; KK's single-day push on 2026-09-24).
