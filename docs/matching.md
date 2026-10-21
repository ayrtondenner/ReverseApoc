# Matching notes

The project's record of how Watcom turns C into the bytes in UFO2P.EXE and TACP.EXE: flags, idioms and traps that we have **verified on our own binaries**. Each entry says where it was seen (function address, EXE) and when.

**Nothing recorded yet.** Phase 4 fills in compilers and flags; Phase 5 and later fill in the rest. Raw observations go to [learnings.md](learnings.md) first and move here once confirmed. Hypotheses and evidence from the research live in [toolchain.md](toolchain.md).

## Compiler and flags per module

| Module / file glob | EXE | Compiler@version | Flags | Evidence | Date |
|---|---|---|---|---|---|
| * | UFO2P.EXE | wcc386@10.6 | -4r -s -fpi | runtime.csv + probe scan + cppscan (toolchain.md "Result") | 2026-10-21 |
| * | TACP.EXE | wcc386@10.6 | -4r -s -fpi | runtime.csv + probe scan + cppscan (toolchain.md "Result") | 2026-10-21 |

Both rows are the `*` default of `config/cflags.txt`, a whole-binary result per EXE (D-09). 10.5 gives the same objects as 10.6 on the probe, and 11.0 ties with 10.6 at `-4r` on the decisive idioms (a candidate until a Phase 5 match separates them). The 40 (UFO2P) and 32 (TACP) functions that call `__CHK` were built without `-s`; they get their own rows once Phase 5 maps them to files. The flags table with the evidence for each flag is [toolchain.md "Flags"](toolchain.md#flags).

## Known idioms

C shapes and the code Watcom emits for them (switches, loops, byte compares, struct copies, division by constants, register allocation order).

Nothing recorded yet.

## Pitfalls

Things that look equivalent in C but compile differently, and tooling traps.

Nothing recorded yet.

Leads from other projects, not yet verified here:

- Declaration order decides stack slots; never reorder declarations ([Theme Hospital AGENTS.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/AGENTS.md)).
- `wcc386` treats `/` as an option switch and splits paths on spaces ([KKND](https://github.com/Wyrelade/KKND-Decomp)).
- `wcc386` and `wpp386` generate different code for the same source ([Theme Hospital MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md)).

## How to read objdiff output

What a diff line means for OMF-converted Watcom objects, which differences are real and which are artefacts of the conversion.

Nothing recorded yet. Known limit: objdiff compares at most one relocation per x86 instruction, so a 100% objdiff score still needs the relocation check below.

## Relocation rules

How relocations in our compiled object must line up with the LE fixups of the original.

Nothing recorded yet. Starting rules from KKND's build gate, to be confirmed in Phase 5:

- every non-relocated byte identical, and the function length equal;
- every `call rel32` hits the same function;
- every absolute fixup resolves to the same target as the original LE fixup;
- references to local-segment data (string literals) are rejected until data placement is modelled; such data moves to an extern `D_` symbol.
