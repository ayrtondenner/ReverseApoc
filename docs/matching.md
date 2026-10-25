# Matching notes

The project's record of how Watcom turns C into the bytes in UFO2P.EXE and TACP.EXE: flags, idioms and traps that we have **verified on our own binaries**. Each entry says where it was seen (function address, EXE) and when.

Phase 4 recorded the compiler and the default flags per EXE (whole-binary scans, below) and the idioms calibrated on our own probe; Phase 5 and later add per-function entries. Raw observations go to [learnings.md](learnings.md) first and move here once confirmed. The evidence behind each compiler and flag claim lives in [toolchain.md](toolchain.md#compiler).

## Compiler and flags per module

| Module / file glob | EXE | Compiler@version | Flags | Evidence | Date |
|---|---|---|---|---|---|
| * | UFO2P.EXE | wcc386@10.6 | -4r -s -fpi | runtime.csv + probe scan + cppscan (toolchain.md "Result") | 2026-10-21 |
| * | TACP.EXE | wcc386@10.6 | -4r -s -fpi | runtime.csv + probe scan + cppscan (toolchain.md "Result") | 2026-10-21 |

Both rows are the `*` default of `config/cflags.txt`, a whole-binary result per EXE (D-09). 10.5 gives the same objects as 10.6 on the probe, and 11.0 ties with 10.6 at `-4r` on the decisive idioms (a candidate until a Phase 5 match separates them). The 40 (UFO2P) and 32 (TACP) functions that call `__CHK` were built without `-s`; they get their own rows once Phase 5 maps them to files. The first two hand matches (UFO2P func_000A3980 in `src/ufo2p/u_000a34f0.c`, TACP func_00055080 in `src/tacp/u_00054f20.c`) both matched under the `*` default, so no per-glob rule exists yet ([toolchain.md "Phase 5 match evidence"](toolchain.md#phase-5-match-evidence)). The flags table with the evidence for each flag is [toolchain.md "Flags"](toolchain.md#flags).

## Known idioms

C shapes and the code Watcom emits for them (switches, loops, byte compares, struct copies, division by constants, register allocation order).

Calibrated 2026-10-21 on our clean-room probe `probe/cg_basic.c`, compiled with 10.5, 10.6 and 11.0 over ten flag sets (`uv run reverseapoc probe calibrate`; the table is in [probe/README.md](../probe/README.md)). 10.5 and 10.6 give byte-identical objects in all ten flag sets, so "10.x" below means both. Mnemonics and counts only.

| Construct | 10.x | 11.0 | Reads as |
|---|---|---|---|
| `return c == 5;` on an `unsigned char` | `-3r`: `sete al; movzx eax,al`. `-4r`, `-5r`: `sete al; and eax,0FFh`. `-5r -os`: `movzx` again | `-3r`: `movzx`. `-4r`: `and eax,0FFh`. Every `-5` cell: a branch (`jne`, `mov eax,1`), no setcc | `and`-form: not `-3`, not 11.0 at `-5`; a `movzx` alone does not prove `-3` (10.x `-os`) |
| 5-dword struct copy | `-3r`, `-4r`, `-4r -ox`: `mov ecx,5` .. `rep movsd` (register moves between). Every `-5r`/`-5s` cell: five `movsd` unrolled | the same split | only the 5-dword size (20-23 bytes with a movsw/movsb tail) separates `-4` from `-5` (10.6 and 11.0 sizes table, 04-10): 2-4 dwords unroll at both, 6 and more use rep at both, except `-os`, which also unrolls 6 and 7 |
| counted loop `for (i = 0; i < n; i++)` | rotated: `jmp` to the bottom test, `jl` back | top-tested: `cmp; jge` out, `jmp` back | 10.x vs 11.0 on the probe, but not decisive in game code (both shapes occur) and gone under `-oneatx` for both |
| sparse switch `{1, 2, 3, 10}` | one ascending compare chain (none found under `-oneatx`) | the same | switch order does not separate the versions; our counter covers `eax`/`al` compares only |
| `-fpi` vs `-fpi87` | identical code (LEDATA and FIXUPP records equal); the `-fpi` object also requests `emu387` (`-fpi87`: `noemu387`) and declares the extern `__init_387_emulator`, which pulls EMU387 in | the same | the linked EMU387 module says some object asked for `-fpi` |
| without `-s` | one `push imm32; call __CHK` per function (7 in the 7-function probe) | the same | each `__CHK` call in game code is one function built without `-s` |
| `-5s` | default libraries `math387s` and `emu387`; no CLIB library is requested under any flag set | the same | a stack-convention build links 3S libraries |

Measured in the game's non-library code with these idioms: [toolchain.md "Evidence"](toolchain.md#evidence) (counts) and ["Flags"](toolchain.md#flags) (what they prove).

## Pitfalls

Things that look equivalent in C but compile differently, and tooling traps.

Compiler wrapper traps, each verified in Phase 4 and handled by `uv run reverseapoc cc` (details in [toolchain.md "wibo"](toolchain.md#wibo)):

- **Environment variables change codegen.** `wcc386` reads its own name as an options variable: `WCC386=-3r` turned the `and`-form byte compare into `movzx` on 10.6 and 11.0. `INCLUDE` changes the header search. docker compose loads `../.env` into the container, so the wrapper builds the child environment from scratch.
- **The NT-hosted compilers target NT by default.** Without `-bt=dos`, `__NT__` is defined and the headers and default libraries take the NT branches. The wrapper always passes `-bt=dos`, and cflags.txt may not override it.
- **A failed compile writes `<stem>.err` into the cwd** (the repo root). The wrapper passes `-fr=` with a path beside the object.
- **`/` starts an option and a space splits the command line.** A forward-slash path became `Invalid option`. The wrapper writes relative backslash paths and refuses paths with a space or a leading `-`. In Git Bash, MSYS also rewrites `-i=` arguments and eats `\\`; run manual compiles with `MSYS_NO_PATHCONV=1`, or through the wrapper.
- **Objects hold absolute paths.** THEADR holds the absolute source path and COMENT class 0xE9 absolute header paths and DOS timestamps, even when the command line was relative, so raw object hashes never agree across host and container. Compare the normalized SHA-1 (all records except THEADR and COMENT 0xE9), which the wrapper prints next to the raw one; it was equal native vs wibo for 10.5, 10.6 and 11.0 (D-03).
- **Identical library bodies.** Equal-length library stubs match each other after masking: CLIB's 18-byte `noefgfmt`/`nomem` stubs look like the C++ `__wcpp_` undefined-member stubs, and C++ `fatalerr` equals the head of CLIB's `__fatal_runtime_error_`. A naive library match "finds" the C++ runtime in both EXEs. `libmatch` keeps such rows `ambiguous` (or resolves them by data, call graph or C-before-C++), and an ambiguous row's publics are candidates, not placements.

Leads from other projects, not yet verified here:

- Declaration order decides stack slots; never reorder declarations ([Theme Hospital AGENTS.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/AGENTS.md)).
- `wcc386` treats `/` as an option switch and splits paths on spaces ([KKND](https://github.com/Wyrelade/KKND-Decomp)).
- `wcc386` and `wpp386` generate different code for the same source ([Theme Hospital MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md)).

## How to read objdiff output

What a diff line means for OMF-converted Watcom objects, which differences are real and which are artefacts of the conversion.

Nothing recorded yet. Known limit: objdiff compares at most one relocation per x86 instruction, so a 100% objdiff score still needs the relocation check below.

## Relocation rules

How relocations in our compiled object must line up with the LE fixups of the original.

Starting rules from KKND's build gate, to be confirmed in Phase 5:

- every non-relocated byte identical, and the function length equal;
- every `call rel32` hits the same function;
- every absolute fixup resolves to the same target as the original LE fixup;
- references to local-segment data (string literals) are rejected until data placement is modelled; such data moves to an extern `D_` symbol.

Confirmed rules for jump tables and statics (plan 06-10, D-39; `tools/reverseapoc/check.py` `leading_table` and `own_publics`):

- **A switch with a jump table matches only when the table leads its unit.** wcc386 10.6 puts the table at `_TEXT+0`, before the function's public. `check` pairs it with the unit's data-in-code row (`D_XXXXXXXX` in functions.csv) that sits right before the function's row, and checks the table and the filler up to the function like a function: every entry must land on the original's case label. So a switch needs its table row in the same unit, as the unit's first compiled thing (rows marked `INCLUDE_ASM` emit nothing, so they may come before it).
- **A jump table between two publics fails closed.** Each other public of the unit counts only up to its own row's length, so a table after a public belongs to no row and the function that jumps through it is refused. Keep such a function `INCLUDE_ASM` until Phase 7.
- **Name a static after its row: `static <type> func_XXXXXXXX(...)`.** wcc386 emits it as an LPUBDEF `func_XXXXXXXX_`, and its callers call it through an EXTDEF of the same name, which `check` resolves to the row. A static with any other name fails ("a static (LPUBDEF) function, which check cannot pair with a row"); static data fails likewise.
