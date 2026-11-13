# Matching notes

The project's record of how Watcom turns C into the bytes in UFO2P.EXE and TACP.EXE: flags, idioms and traps that we have **verified on our own binaries**. Each entry says where it was seen (function address, EXE) and when.

Phase 4 recorded the compiler and the default flags per EXE (whole-binary scans, below) and the idioms calibrated on our own probe; Phase 5 and later add per-function entries. Raw observations go to [learnings.md](learnings.md) first and move here once confirmed. The evidence behind each compiler and flag claim lives in [toolchain.md](toolchain.md#compiler).

## Compiler and flags per module

| Module / file glob | EXE | Compiler@version | Flags | Evidence | Date |
|---|---|---|---|---|---|
| * | UFO2P.EXE | wcc386@10.6 | -4r -s -fpi | runtime.csv + probe scan + cppscan (toolchain.md "Result") | 2026-10-21 |
| * | TACP.EXE | wcc386@10.6 | -4r -s -fpi | runtime.csv + probe scan + cppscan (toolchain.md "Result") | 2026-10-21 |
| src/tacp/u_0006fbd0.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0001 approved by ayrtondenner (re-gate log under build/flags/) | 2026-10-30 |
| src/ufo2p/u_00026dd0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0003 approved by ayrtondenner (re-gate log under build/flags/) | 2026-10-30 |
| src/tacp/u_00021a90.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0008 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/tacp/u_000443f0.c | TACP.EXE | wcc386@10.6 | -4r -ot -s -fpi | F-0009 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/tacp/u_00074420.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0012 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/tacp/u_0008e720.c | TACP.EXE | wcc386@10.6 | -4r -ox -s -fpi | F-0015 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_0002e710.c | UFO2P.EXE | wcc386@10.6 | -4r -ox -s -fpi | F-0024 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_00060140.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0031 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_0006ee50.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0032 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_00071740.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0033 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_00089240.c | UFO2P.EXE | wcc386@10.6 | -4r -ot -s -fpi | F-0036 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_000ab080.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0041 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_000b4470.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0043 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/ufo2p/u_000b76d0.c | UFO2P.EXE | wcc386@10.6 | -4r -ox -s -fpi | F-0044 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-01 |
| src/tacp/u_00015f80.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0045 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/tacp/u_000a6100.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0046 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/tacp/u_000a87c0.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0048 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/ufo2p/u_00041ef0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0049 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/ufo2p/u_00051810.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0050 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/ufo2p/u_00092250.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0051 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/ufo2p/u_000b63c0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0052 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/tacp/u_0001df90.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0053 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/tacp/u_00095780.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0054 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/tacp/u_00098010.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0055 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/ufo2p/u_000477b0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0056 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/ufo2p/u_0005f750.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0057 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-03 |
| src/tacp/u_00048350.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0058 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/tacp/u_0004b8b0.c | TACP.EXE | wcc386@10.6 | -4r -ox -s -fpi | F-0059 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/tacp/u_000a9720.c | TACP.EXE | wcc386@10.6 | -4r -ox -s -fpi | F-0060 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/tacp/u_000b1de0.c | TACP.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0061 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_00063480.c | UFO2P.EXE | wcc386@10.6 | -4r -ot -s -fpi | F-0064 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_00073000.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0065 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_000989d0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0066 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_000a74d0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0068 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_000130b0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0062 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_00050c60.c | UFO2P.EXE | wcc386@10.6 | -4r -ot -s -fpi | F-0063 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_000a59f0.c | UFO2P.EXE | wcc386@10.6 | -4r -oneatx -s -fpi | F-0067 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-07 |
| src/ufo2p/u_000502b0.c | UFO2P.EXE | wcc386@10.6 | -4r -ox -s -fpi | F-0071 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-13 |
| src/tacp/u_00063100.c | TACP.EXE | wcc386@10.6 | -4r -ox -s -fpi | F-0069 approved by ayrtondenner (re-gate log under build/flags/) | 2026-11-13 |

Both rows are the `*` default of `config/cflags.txt`, a whole-binary result per EXE (D-09). 10.5 gives the same objects as 10.6 on the probe, and 11.0 ties with 10.6 at `-4r` on the decisive idioms (still tied after the two Phase 5 leaf matches, which separate no candidate; Phase 6 records the evidence of each pilot match). The 40 (UFO2P) and 32 (TACP) functions that call `__CHK` were built without `-s`; they get their own rows once a match reaches one (neither Phase 5 match calls `__CHK`). The first two hand matches (UFO2P func_000A3980 in `src/ufo2p/u_000a34f0.c`, TACP func_00055080 in `src/tacp/u_00054f20.c`) both matched under the `*` default, so no per-glob rule exists yet ([toolchain.md "Phase 5 match evidence"](toolchain.md#phase-5-match-evidence)). The flags table with the evidence for each flag is [toolchain.md "Flags"](toolchain.md#flags).

## Known idioms

C shapes and the code Watcom emits for them (switches, loops, byte compares, struct copies, division by constants, register allocation order).

Calibrated 2026-10-21 on our clean-room probe `probe/cg_basic.c`, compiled with 10.5, 10.6 and 11.0 over ten flag sets (`uv run reverseapoc probe calibrate`; the table is in [probe/README.md](../probe/README.md)). 10.5 and 10.6 give byte-identical objects in all ten flag sets, so "10.x" below means both. Mnemonics and counts only.

| Construct | 10.x | 11.0 | Reads as |
|---|---|---|---|
| `return c == 5;` on an `unsigned char` | `-3r`: `sete al; movzx eax,al`. `-4r`, `-5r`: `sete al; and eax,0FFh`. `-5r -os`: `movzx` again | `-3r`: `movzx`. `-4r`: `and eax,0FFh`. Every `-5` cell: a branch (`jne`, `mov eax,1`), no setcc | `and`-form: not `-3`, not 11.0 at `-5`; a `movzx` alone does not prove `-3` (10.x `-os`) |
| 5-dword struct copy | `-3r`, `-4r`, `-4r -ox`: `mov ecx,5` .. `rep movsd` (register moves between). Every `-5r`/`-5s` cell: five `movsd` unrolled | the same split | only the 5-dword size (20-23 bytes with a movsw/movsb tail) separates `-4` from `-5` (10.6 and 11.0 sizes table, 04-10): 2-4 dwords unroll at both, 6 and more use rep at both, except `-os`, which also unrolls 6 and 7 |
| counted loop `for (i = 0; i < n; i++)` | rotated: `jmp` to the bottom test, `jl` back | top-tested: `cmp; jge` out, `jmp` back | 10.x vs 11.0 on the probe, but not decisive in game code (both shapes occur) and gone under `-oneatx` for both |
| sparse switch `{1, 2, 3, 10}` | one ascending compare chain (none found under `-oneatx`) | the same | switch order does not separate the versions; our counter covers `eax`/`al` compares only |
| `-fpi` vs `-fpi87` | identical code (LEDATA and FIXUPP records equal; scratch check, not logged); the `-fpi` object also requests `emu387` (`-fpi87`: `noemu387`) and declares the extern `__init_387_emulator`, which pulls EMU387 in | the same | the linked EMU387 module says some object asked for `-fpi` |
| without `-s` | one `push imm32; call __CHK` per function (7 in the 7-function probe) | the same | each `__CHK` call in game code is one function built without `-s` |
| `-5s` | default libraries `math387s` and `emu387`; no CLIB library is requested under any flag set | the same | a stack-convention build links 3S libraries |
| a function whose last statement calls the function defined right after it in the same file (07-45, our clean-room `45-calib` cases) | 10.6 under `-4r -s -fpi`, `-4r -ot -s -fpi` and `-4r -oneatx -s -fpi`: the call is dropped, so the caller ends with no `ret` or `jmp` and runs into the callee laid out next. With the callee defined first, or only declared extern: a tail `jmp` | not calibrated | a row with no `ret` that runs into a row which is called, tail-jumped to or has its address taken is most likely C ending in a call to that next function, defined right after it in the same unit (`mechanics splits` lists such pairs). Such a pair matches only together: func_00061F30 hit 100% under `-4r -ot` only while func_00061F50's C followed it (F-0005). A negative calibration would not have refuted this reading |

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
- **Declaration order decides far fewer stack slots than it looks.** Measured on our clean-room [`probe/cg_slots.c`](../probe/cg_slots.c) under `-4r -s -fpi` and `-4r -oneatx -s -fpi`, with the same result in both. Address-taken locals and aggregates sort by size, the largest lowest, each padded to 4 and nothing aligned past that, and a local nothing uses takes no slot. Declaration order only breaks ties, and only when the frame has one size, of 1, 2 or 4 bytes (the first declared sits highest). Three or more multi-element arrays do not follow that even alone in a frame of one size: in both cells three `char[4]` or `short[2]` sit at 4, 8, 0 and three `char[2]` at 0, 8, 4, first declared to last, where two `char[4]` and three `int[1]` or `char[1]` keep the rule, and so do three or four `char[4]` declared first with one or two `int` after them in one block (quick 261112-fdx). Nor does an array of 2 bytes beside plain locals, as a rule: `short a; short b; char c[2];` sits at 4, 8, 0, though one `char[2]` declared first keeps the rule beside up to eleven shorts. Nor two arrays beside a later block: `char a[4]; char b[4];` with `int c;` in a block sits at 8, 4, 0, though with an `int` after the two arrays in the top block they keep the rule. `slots.order_is_known` refuses such a frame, some of which hold because no count draws the line, so the search keeps its plain moves there. Ints keep that order across blocks, an earlier block lower, by its place in the source and not its depth; chars and shorts do not. Any other tie leaves declaration order, and locals outside it change how: adding an `int` to three `int[2]` moves the three. Register-candidate scalars ignore declaration and scope, while assignment order, use order, type and loop weight move them, with one exception: shorts spilled beside a short in memory do move with their declarations. Spills sort by size too, so they sit above ints and below shorts. On a matched function none of this is a reason to reorder anything: its declarations stay as they are ([ceremonies.md](ceremonies.md#the-one-rule-matched-c-keeps-its-shape)).

Leads from other projects, not yet verified here:

- `wcc386` treats `/` as an option switch and splits paths on spaces ([KKND](https://github.com/Wyrelade/KKND-Decomp)).
- `wcc386` and `wpp386` generate different code for the same source ([Theme Hospital MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md)).

## How to read objdiff output

What a diff line means for OMF-converted Watcom objects, which differences are real and which are artefacts of the conversion.

What Phase 5 established (spike 005, plans 05-17 to 05-19; details in [toolchain.md "Result"](toolchain.md#result)): objdiff-cli pairs code sections by name, so our converted `_TEXT` pairs only with a target `_TEXT` (a target `.text` stays unpaired), and it compares a relocation to an undefined symbol by name and addend only, so the target side carries the exact linker names. Both first matches (UFO2P func_000A3980, TACP func_00055080) score 100.0. A 100.0 is a score, not a match: in the spike's plants a wrong symbol on the 2nd relocation of a `mov dword [abs32], imm32` (its imm32) still scores 100.0. That is the one instruction shape observed, and it is why every match also needs the relocation check below and the whole-EXE SHA-1.

## Relocation rules

How relocations in our compiled object must line up with the LE fixups of the original.

Rules from KKND's build gate, confirmed in Phase 5. The relocation check (SPL-09, `tools/reverseapoc/relocs.py`) implements them independently of objdiff, and together with the whole-EXE SHA-1 it is the match gate. Both first matches (05-18 func_000A3980, 05-19 func_00055080) pass it, and a planted wrong call target fails it (`tests/test_check_real.py`):

- every non-relocated byte identical, and the function length equal (one exception, next bullet);
- **Trailing filler (07-48, owner ruling: option A).** Our public may be shorter than its row only by the original's trailing Watcom alignment filler, and only when all five conditions hold, checked in this order (`relocs._trailing_filler`): (1) the shortfall is 1 to 15 bytes; (2) the row ends on a 16-byte boundary; (3) no LE fixup field overlaps the tail `[start + our size, end)`; (4) our bytes decode exactly to our size (an instruction start at one of our fixup fields ends the decode as inline data) and our last instruction is terminal (`ret`, `iret` or an unconditional `jmp`); (5) the original's tail decodes exactly to the row end and every instruction is alignment filler in any register (`x86.is_alignment_filler`: `nop`, `mov r, r`, `lea r, [r]` with no index, displacement 0 and no segment override). Why: each original object held one function, and the linker aligned each object's `_TEXT` to 16, so a row can end in up to 15 bytes of filler that our unit never emits (the next function in a unit is an `INCLUDE_ASM` stub that emits nothing). Spike 011 found 32 of 51 converter matches byte-identical once the filler was cut. The rest of the check (bytes, fixups, reverse coverage) then runs over our bytes; land patches our bytes only, so the tail keeps the original bytes and the whole-EXE SHA-1 still decides. `check` reports `bytes ok, N bytes of trailing filler kept` and cuts that row's objdiff target at our length (objdiff scored the real tacp func_0006BEE0 89.6552% over the full row, 100% after the cut). Every other length difference is refused as `length differs: ours N bytes, original M bytes; <the first failing condition's reason>`. Our own sizes do not move: omf2elf still trims only the eax-only `x86.is_filler`;
- every `call rel32` hits the same function;
- every absolute fixup resolves to the same target as the original LE fixup;
- every LE fixup field inside the row is covered by one of our fixups (reverse coverage), so a constant that happens to equal the raw field cannot pass the byte compare;
- references to local-segment data (string literals) are rejected until data placement is modelled; such data moves to an extern `D_` symbol.

Confirmed rules for jump tables and statics (plan 06-10, D-39; `tools/reverseapoc/check.py` `leading_table` and `own_publics`):

- **A switch with a jump table matches only when the table leads its unit.** wcc386 10.6 puts the table at `_TEXT+0`, before the function's public. `check` pairs it with the unit's data-in-code row (`D_XXXXXXXX` in functions.csv) that sits right before the function's row, and checks the table and the filler up to the function like a function: every entry must land inside that function on the original's case label. When ours has less filler there than the original (07-48b: wcc386 lays the function right after the table, the original object's linker aligned it to 16), the gap passes under 07-48's conditions 1, 2, 3 and 5: at most 15 bytes, the function's row starts on a 16-byte boundary, no LE fixup field in the gap, and the original gap decodes exactly to the function's start and is all alignment filler. A table is data and has no terminal instruction, so condition 4 does not apply (only this span check, `check._head_reloc`, passes `table=True` to `relocs.check_function`), and the table is never landed: land splices the function's row alone, so the table and its gap keep the original bytes. Measured on tacp func_0001E860: a 32-byte table, 8 bytes of original filler, then the function; exact under `-4r -oneatx -s -fpi` once the gap passed. Only that function may jump through the table; another function of the unit that references it is refused. So a switch needs its table row in the same unit, as the unit's first compiled thing (rows marked `INCLUDE_ASM` emit nothing, so they may come before it).
- **A jump table between two publics fails closed.** Each other public of the unit counts only up to its own row's length, so a table after a public belongs to no row and the function that jumps through it is refused. Keep such a function `INCLUDE_ASM` until Phase 7.
- **Name a static after its row: `static <type> func_XXXXXXXX(...)`.** wcc386 emits it as an LPUBDEF `func_XXXXXXXX_`, and its callers call it through an EXTDEF of the same name, which `check` resolves to the row. A static with any other name fails ("a static (LPUBDEF) function, which check cannot pair with a row"); static data fails likewise.
