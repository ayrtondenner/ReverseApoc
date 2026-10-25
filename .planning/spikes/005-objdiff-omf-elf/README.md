---
spike: 005
idea: split-and-first-matches
name: objdiff-omf-elf
type: standard
validates: "Given the cmain386 rows of UFO2P.EXE and TACP.EXE, Watcom's own SRC/STARTUP/386/CMAIN386.C read from the owner's 10.6 tree and objdiff-cli 3.8.2 in reverseapoc-build, when the object compiled with reverseapoc cc is converted to ELF32 and diffed against a target ELF cut from le.py bytes with relocations rebuilt from the LE fixups, PC32 synthesized for the calls and an address-to-name map for the linker names, then objdiff loads both objects and reports match_percent 100.0 for __CMain"
verdict: VALIDATED
related: [004]
tags: [objdiff, omf, elf, d-01, d-02, d-19]
---

# Spike 005: objdiff-cli 3.8.2 scores a converted Watcom object at 100% against an LE cut

This is the spike named in the Phase 5 roadmap entry and in D-01: before any Ghidra or splitter
work, does objdiff-cli diff a Watcom OMF object, converted to ELF32, cleanly against a target ELF
cut from the LE? The verdict decides between the hybrid pipeline and the fallback (D-02).

## What This Validates

Given the `cmain386` runtime row of both EXEs (`config/<exe>/runtime.csv`, public `__CMain`) and
Watcom's own `SRC/STARTUP/386/CMAIN386.C`, read in place from the owner's read-only
`third_party/watcom/10.6/` tree and never copied (D-19), we check that:

- `reverseapoc cc` compiles it under the default `*  wcc386@10.6  -4r -s -fpi` rule to a
  `_TEXT` segment as long as the row, with no differing byte outside the fixup fields;
- a spike-local omf2elf (`mkelf.from_omf`) and target cut (`mkelf.cut_target`) produce two
  ELF32 REL objects that objdiff-cli 3.8.2 loads;
- objdiff reports `match_percent` 100.0 for `__CMain` in both EXEs once the target side names its
  relocation targets through an address-to-name map;
- plants show what objdiff catches and what it misses.

## Research

Restated from 05-RESEARCH.md "Pattern 1" (measured natively on the host, 2026-10-23):

| | UFO2P | TACP |
|---|---|---|
| runtime.csv row | `cmain386`, 0x000C5C9C..0x000C5CEB, `__CMain`, unique | `cmain386` at 0x000C7915 |
| Object | `_TEXT` 79 bytes = row length, 0 unmasked differing bytes | same object, 79 = 79 |
| OMF fixups | 4 self-relative (calls) + 5 segment-relative (data) | same |
| LE fixups in range | 5 | 5 |
| Linker names | `__ASTACKSIZ`, `stackavail_`, `__ASTACKPTR`, `__CommonInit_`, `____Argv`, `____Argc`, `main_`, `exit_` | same |

The research also probed objdiff with made-up bytes: identical 100.0, a wrong call symbol
98.75, a wrong addend 98.75, a wrong symbol on the 2nd relocation of one instruction 100.0,
and a `.text` section on one side unpaired. This spike repeats those on the real pair where it
can and on the same made-up bytes where it cannot (P3).

## How It Works

`spike.py` (stdlib + `reverseapoc` for shared inputs only):

1. Resolves the cflags rule for the source (`config/cflags.txt:37`, `*  wcc386@10.6  -4r -s -fpi`)
   and runs `uv run reverseapoc cc third_party/watcom/10.6/SRC/STARTUP/386/CMAIN386.C -o
   build/spike005/cmain386.obj`; the `OK` line must name `wcc386@10.6`.
2. Parses the object with `omf.read_object` and finds `__CMain` and its segment.
3. Reads each EXE through `libmatch.read_target` (manifest-checked), takes the row from
   `read_runtime_csv`, and compares the row's bytes from `le.load_flat(relocate=False)` with the
   segment, masking our OMF fixup fields and the row's LE fixup fields.
4. Builds the name map (below), writes `build/spike005/<exe>/target.o` (`cut_target`) and
   `base.o` (`from_omf`), and runs objdiff-cli.

`mkelf.py` is the spike-local ELF side; the production modules come in plans 05-02, 05-06 and
05-08, and plan 05-18 re-proves this pair through them:

- `write_elf`: ELF32 LSB `ET_REL` `EM_386`, sections `null, _TEXT, .rel_TEXT, .symtab, .strtab,
  .shstrtab`; each `.rel` section has `sh_link` = symtab and `sh_info` = the section it
  relocates; the symtab's `sh_info` is the first global. Relocations are REL: the addend lives in
  the field bytes.
- `from_omf`: the segment holding the public becomes one section named like the segment
  (`_TEXT`); the public is a GLOBAL `STT_FUNC` sized to the segment; a self-relative fixup becomes
  `R_386_PC32` with the field rewritten to `stored + displacement - 4`, a segment-relative one
  `R_386_32` with `stored + displacement` (Theme Hospital `omf2elf.convert` addend rule); an
  extern target is an undefined GLOBAL `STT_NOTYPE` symbol of its OMF name.
- `cut_target`: bytes from `load_flat(relocate=False)[start:end]` (P4: never Ghidra, never
  `relocate=True`); every LE off32 fixup in range becomes `R_386_32` against the name of its
  `target_va`, field rewritten to 0 (the raw field holds `target_off`); every call field becomes
  `R_386_PC32` against the name of `field + 4 + rel32`, field rewritten to -4.

## How the name map works (D-19)

objdiff compares a relocation to an undefined symbol by name and addend only, so the target's
relocations must carry the same linker names as our object. Each of the 8 names is resolved from
the pair's own fields:

- a self-relative (call) field at VA `F` names the extern at `F + 4 + rel32(original[F]) -
  stored - displacement`; the spike also checks the byte before `F` is the `call rel32` opcode and
  that no LE fixup sits on `F` (calls inside object 1 are resolved at link time);
- a segment-relative field at VA `F` names the extern at `target_va - stored - displacement` of
  the LE fixup at `F`; the spike checks every such field has its LE fixup and every LE fixup in
  the row is one of ours.

Each name resolves to exactly one address and each address to one name (one name per address).
Under D-19 this map is normal relocation mapping, not a workaround.

In the pipeline the general mechanism is the optional committed `config/<exe>/symbols.csv` with
columns `address,name,kind` (code or data), holding addresses and names only, never bytes (plans
05-04 and 05-16). Runtime publics that are not module starts, such as `exit_` (the `exit` module
start + 1) and `stackavail_` (inside a module), come from the LIB386 public offsets that the
functions.csv generator derives (`seed_runtime_rows`, plan 05-04), not from `runtime.csv`, which
lists module starts only.

## Results

Run 2026-10-23 on the main checkout, in the `reverseapoc-build` container
(`docker compose run --rm build bash -lc "uv sync --locked && uv run python
.planning/spikes/005-objdiff-omf-elf/spike.py --plants"`; output kept in the gitignored
`build/spike005/all.out`):

```
PASS CMAIN386.C rule cflags.txt:37 * wcc386@10.6 -4r -s -fpi
PASS CMAIN386.C compile wcc386@10.6 exit 0 normalized 0f4549d1ae2e9b80deb3489d389993cb353df0f9
PASS UFO2P.EXE row cmain386 rows 1
PASS UFO2P.EXE row-start 0x000c5c9c
PASS UFO2P.EXE size _TEXT 79 row 79
PASS UFO2P.EXE bytes 0 differ outside fixup fields
PASS UFO2P.EXE omf-fixups self-relative 4 segment-relative 5
PASS UFO2P.EXE le-fixups 5 in range, all off32 True
PASS UFO2P.EXE call-opcodes 4 self-relative fields follow call rel32, no LE fixup
PASS UFO2P.EXE le-coverage every segment-relative field has its LE fixup and every LE fixup in range is ours
PASS UFO2P.EXE name-map 8 names: __ASTACKPTR 0x0013bba8 __ASTACKSIZ 0x0013bba4 __CommonInit_ 0x000c9360 ____Argc 0x00249968 ____Argv 0x0024996c exit_ 0x000c01e1 main_ 0x00010010 stackavail_ 0x000c9357
PASS UFO2P.EXE objdiff __CMain match_percent 100.0
PASS UFO2P.EXE P1-wrong-call-symbol exit_->main_ match_percent 99.80769 (expect below 100)
PASS UFO2P.EXE P2-wrong-addend R_386_32 at 0x000c5ca2 addend 4 match_percent 99.80769 (expect below 100)
PASS UFO2P.EXE P4-section-.text target section .text, base _TEXT: match_percent None (expect unpaired)
PASS TACP.EXE row cmain386 rows 1
PASS TACP.EXE row-start 0x000c7915
PASS TACP.EXE size _TEXT 79 row 79
PASS TACP.EXE bytes 0 differ outside fixup fields
PASS TACP.EXE omf-fixups self-relative 4 segment-relative 5
PASS TACP.EXE le-fixups 5 in range, all off32 True
PASS TACP.EXE call-opcodes 4 self-relative fields follow call rel32, no LE fixup
PASS TACP.EXE le-coverage every segment-relative field has its LE fixup and every LE fixup in range is ours
PASS TACP.EXE name-map 8 names: __ASTACKPTR 0x002b3e54 __ASTACKSIZ 0x002b3e50 __CommonInit_ 0x000cc54a ____Argc 0x00336bf8 ____Argv 0x00336bfc exit_ 0x000c23a4 main_ 0x000102a0 stackavail_ 0x000ca446
PASS TACP.EXE objdiff __CMain match_percent 100.0
PASS TACP.EXE P1-wrong-call-symbol exit_->main_ match_percent 99.80769 (expect below 100)
PASS TACP.EXE P2-wrong-addend R_386_32 at 0x000c791b addend 4 match_percent 99.80769 (expect below 100)
PASS TACP.EXE P4-section-.text target section .text, base _TEXT: match_percent None (expect unpaired)
PASS synthetic P3-control-1st-reloc symbol at field 12 differs: match_percent 98.75 (expect below 100)
PASS synthetic P3-blind-spot-2nd-reloc symbol at field 16 (imm32, 2nd reloc of one instruction) differs: match_percent 100.0 (expect exactly 100.0)
ALL PASS
```

The container compile gives the same object for both EXEs (one compile, normalized SHA-1 above),
and the research's host-measured facts all hold under wibo: 79 bytes, 0 differing bytes, 4 + 5
OMF fixups, 5 LE fixups.

The name map, as resolved from each EXE's own fields:

| name | UFO2P address | TACP address |
|---|---|---|
| `__ASTACKSIZ` | 0x0013BBA4 | 0x002B3E50 |
| `__ASTACKPTR` | 0x0013BBA8 | 0x002B3E54 |
| `____Argc` | 0x00249968 | 0x00336BF8 |
| `____Argv` | 0x0024996C | 0x00336BFC |
| `stackavail_` | 0x000C9357 | 0x000CA446 |
| `__CommonInit_` | 0x000C9360 | 0x000CC54A |
| `main_` | 0x00010010 | 0x000102A0 |
| `exit_` | 0x000C01E1 | 0x000C23A4 |

The first four are data (object 2, reached through LE off32 fixups); the last four are code
(call targets in object 1, reached through `call rel32` with no LE fixup). The UFO2P addresses
equal the ones the research listed.

## Plants

| Plant | What changes | objdiff result | Expected |
|---|---|---|---|
| P1 wrong call symbol | our converted object's `R_386_PC32` to `exit_` names `main_` | 99.80769 (both EXEs) | below 100: caught |
| P2 wrong addend | the target's first `R_386_32` field holds addend 4 instead of 0 | 99.80769 (both EXEs) | below 100: caught |
| P3 control | made-up `mov eax,[abs32]; call rel32; mov dword [abs32], imm32; ret`, symbol of the 1st relocation of the `mov dword` (field 12) differs | 98.75 | below 100: caught |
| P3 blind spot | same made-up bytes, only the symbol of the 2nd relocation of the `mov dword` (the imm32, field 16) differs | 100.0 | exactly 100.0: missed |
| P4 naming | the target's section is `.text`, ours `_TEXT` | no `match_percent` (unpaired) | unpaired |

P3 shows a blind spot of the observed shape: in the plants, a wrong symbol on the 2nd relocation
of `mov dword [abs32], imm32` still scored 100.0, while a wrong symbol on its 1st relocation was
caught. The spike tested only this instruction, so it makes no claim about other instructions
with two relocations. objdiff is therefore a score and a viewer, not
the gate: the KKND-style relocation check (SPL-09, plan 05-09) is the gate, and the whole-EXE
SHA-1 stays the final authority. P4 pins the naming rule for the production writers (plans 05-02
and 05-08): both sides name code sections `_TEXT`.

## objdiff command

`objdiff-cli diff --help` (3.8.2) spells the one-shot options as `-1, --target`, `-2, --base`,
`-o, --output` (`-` for stdout) and `--format` (default `json`), with the symbol as the last
argument. The spike runs, from the repo root in the container:

```
objdiff-cli diff -1 build/spike005/<exe>/target.o -2 build/spike005/<exe>/base.o -o - __CMain
```

and takes `match_percent` of the `__CMain` entry in `left.symbols` of the JSON (left = target).
A symbol absent from `left.symbols`, or one with no `match_percent`, counts as unpaired. The
default `functionRelocDiffs=name_address` was not changed.

## Verdict

**VALIDATED** (D-02, D-19). objdiff-cli 3.8.2 loads both the converted object and the LE cut, and
reports `match_percent` 100.0 for `__CMain` in UFO2P.EXE and in TACP.EXE. The only thing the
target side needed beyond the LE's own bytes and fixups is the address-to-name map, which D-19
counts as normal relocation mapping, so no workaround was needed and the verdict is not PARTIAL.
Two writer rules are design, not workarounds: code sections are named `_TEXT` on both sides
(P4), and relocations are REL with the addend in the field (the TH addend rule on our side,
field rewritten to the addend on the target side).

During the tracer the first target.o failed to load (`Invalid ELF section header entry size`)
because `mkelf.py` set `EI_DATA` to 2 (big-endian); with `ELFDATA2LSB = 1` both objects load.
That was a bug in the spike's writer, not an objdiff limitation.

The hybrid pipeline stays. The KKND-style relocation check is built regardless (D-02), and P3
is why it, not objdiff, is the gate.

## Not covered here

- The relocation-check half of the research Given/When/Then (the check passes on the good pair
  and fails on planted wrong targets) is proven by `tests/test_check_real.py` in plan 05-18.
- Production omf2elf and target writers, and `symbols.csv`, are plans 05-02, 05-04, 05-06 and
  05-08 (05-16 commits the `symbols.csv` files).
- Functions with jump tables, several publics per segment, and data sections: `__CMain` has none
  of these, and `from_omf` refuses a fixup to a segment it does not emit.
