---
name: watcom-decomp
description: Use when working in a ReverseApoc matching attempt - writing or fixing the C of a claimed Watcom C 10.6 function in your private view unit (REVERSEAPOC_UNIT_FILE), declaring a struct or extern it needs, reading attempt check or sweep output, or deciding whether to stop and leave notes.
---

# Matching one Watcom function

You make one claimed function byte-identical to the original, proven by `attempt check`, or you stop and leave notes. This page holds every rule and fact the attempt needs: read the docs it links only for depth, and never read `tools/` to find a rule.

**Quick reference**

| Question | Answer |
|---|---|
| Your file | the private view unit at `$REVERSEAPOC_UNIT_FILE`. The /goal names its path, `build/driver/<run>/<exe>/<func>/attempt-<n>/view/src/<exe>/<unit>.c`. It is the only C you edit. |
| What you may write | that view unit and this attempt's notes.md (its full path follows `notes:` in `attempt check` output, and `attempt context` prints it on stderr). No header anywhere. The hooks also allow `proposals.jsonl` (`REVERSEAPOC_PROPOSALS`), but a matching session writes none: nothing applies a matching session's proposals (the driver's rename step is planned, for readability sessions only). A name or header idea goes in notes.md, even when a denial message suggests proposals.jsonl. Nothing else. |
| Types you need | declared in the view unit, at file scope (see "Replacing INCLUDE_ASM"). |
| Names | placeholders stay: `func_XXXXXXXX`, `D_XXXXXXXX` and your own function's name. A name idea goes in notes.md. |
| The only Bash | the five wrapper commands under "The attempt wrapper". Anything else (`ls`, `cat`, `sed`, a host `reverseapoc check`, `docker`, `objdiff-cli`) is denied and costs a turn. Look around with Read, Grep and Glob. |
| Check exit codes | under "The attempt wrapper" below. |
| Check budget | 25 runs per attempt. Every run counts: exit `0`, `1` or `2`, and each `--sweep`. A call the wrapper refuses before running counts nothing. |
| Real time budget | 30 minutes. Each check prints its elapsed seconds and the checks left (`check 7/25, 41 s`); budget by those against the clock. A sweep takes longer than a check. |
| Full evidence | `<attempt dir>/checks/NNNN.json` (check's JSON) and `checks/NNNN.c` (the exact C that run checked), one pair per run, plus a line in `checks.jsonl`. Each check prints both full paths. |
| Flags of your check | the unit's rule in the view's `config/cflags.txt` (HEAD's copy): its own line if it has one, else the `*` default `wcc386@10.6 -4r -s -fpi`. |
| Linker names | function `func_000A3980` links as `func_000A3980_`; data `D_0012EFAC` as `_D_0012EFAC`. A symbols.csv name is used verbatim. |
| Marker | `INCLUDE_ASM(func_XXXXXXXX);` (one argument). |

Never:
- write a `#pragma` of any kind (`#pragma aux`, `#pragma on/off (check_stack)`, any other), `_asm`, `__asm` or `_Pragma` (the hook blocks them);
- write a header, in `include/` or in the view's `view/include/`;
- edit `config/cflags.txt` or anything else in `config/`, the view's copies under `view/config/` included, or `include/common.h`, `include/watcom_compat.h`, tools, tests or build files;
- rename a `func_`/`D_` placeholder or your own function, in the unit or anywhere else;
- run a check with `run_in_background`, or start a second check while one runs: checks run one at a time, in the foreground.

A write or Bash call the hooks deny costs a turn and counts as a hook block: never try one "just to see". A changed path that got past the hooks is worse: the driver's audit after the session finds it, the night stops on a guardrail and nothing is committed.

## Calling convention and linker names

- Default `__watcall`: arguments in `eax`, `edx`, `ebx`, `ecx`, then the stack; the result in `eax`. It needs no pragma and no keyword.
- Linker names are in the table above. You write C names (`func_XXXXXXXX`, `D_XXXXXXXX`); the compiler adds the `_`.
- Give every function you call a prototype at file scope, with the argument count the target passes in registers. A function you call may still be `INCLUDE_ASM` in its unit: the call still resolves.
- `void` or `int`: if the bytes cannot tell (EAX is unused or just holds a callee's result at `ret`), write `void` and say so in a comment; the callers decide (`docs/learnings.md`).

Extern types, from how the target listing touches the data:

| Target access | Declaration |
|---|---|
| 32-bit `mov` / `cmp dword ptr` | `extern int D_X;` |
| `movsx` from a byte | `extern signed char D_X;` (plain `char` is unsigned under Watcom) |
| `movzx` from a byte | `extern unsigned char D_X;` |
| 16-bit (`66` prefix, `movsx`/`movzx` word) | `extern short D_X;` / `extern unsigned short D_X;` |
| `mov reg, offset D_X` (an address, e.g. a string) | `extern char D_X[];` (an array, not a pointer) |
| indexed `[reg*4+D_X]` | an array of the element type |
| x87 `fld dword` / `qword` | `extern float D_X;` / `extern double D_X;` |

## Flags

- Your check compiles with the unit's rule in the view's `config/cflags.txt`, which is HEAD's copy: the unit's own line if it has one (a few units have per-unit `-oneatx` rules), else the `*` default above.
- That file is the check's oracle. Editing it, or its view copy, would make a check pass that the gate refuses; both hook layers deny it, and the driver's audit would stop the night.
- A function whose target starts with `push imm32; call __CHK` was built without `-s`. It needs a per-file rule only the owner can add. Note it as "needs flags (no -s)" and stop.
- Flags are never your choice. A sweep hit (under "The attempt wrapper") is evidence: the driver records it in the attempt record, and an executor later turns it into a proposal with `reverseapoc flags propose`, which reads every sweep's saved `checks/NNNN.c`. Only the owner lands a rule, with `reverseapoc flags approve`. So once a sweep with a hit has run, the hit is safe: editing on loses nothing.
- Depth: `docs/toolchain.md#flags` and `docs/toolchain.md#phase-7-flag-rules`.

## C89 and the lint

- Declare every local at the start of its block, before any statement. No `for (int i...)`, no mixed declarations and code.
- `/* */` comments only, never `//`. No `inline`, `bool`, VLAs, designated initializers or compound literals.
- Never reorder declarations: their order decides the stack slots.
- C89 is required: the driver lints the unit before it commits a match (`reverseapoc lint`, clang `-std=gnu89 -Werror=declaration-after-statement`). A C89 slip fails the attempt even when check passes.
- Depth: `docs/coding-style.md`.

## Pragmas

- Agents write no `#pragma` of any kind during the pilot: not `#pragma aux` (a calling convention, registers, forcing a match), and not `#pragma on/off (check_stack)`, which changes code the way a flag does. Flags are owner-only.
- Calling-convention pragmas come only in human-reviewed commits.
- Default `__watcall` needs no pragma. A register difference is a C-shape or flags question; record it in notes.md.

## Relocation rules

check passes a function only when all of these hold (`docs/matching.md#relocation-rules`):
- objdiff 100%, every non-relocated byte identical, and the same length;
- every `call rel32` hits the same function;
- every absolute fixup resolves to the same target as the original's LE fixup;
- no reference to data of the unit's own segments, such as a string literal.

## Strings, statics and jump tables

- A string or any other constant data the target addresses becomes its extern `D_` symbol (`extern char D_0012F3A0[];`). Never write the literal: it emits new data in our object and fails the relocation check.
- No `static`, and no `switch` that compiles to a jump table, during the pilot. If the target jumps through a table (`jmp cs:[eax*4+...]`), stop: the function is outside the pilot pool.

## Replacing INCLUDE_ASM

Work in your view unit, `$REVERSEAPOC_UNIT_FILE`. The view is the driver's private copy of HEAD's `src/`, `include/` and `config/` for this attempt. The repo-root unit is HEAD's copy, and you never write `src/<exe>/<unit>.c`: after the session the driver copies your view unit's bytes there, then lints and gates it, and puts it back if that fails.

- Delete the claimed function's `INCLUDE_ASM(func_XXXXXXXX);` line. Leave every other marker as it is.
- Put the types, prototypes and externs it needs, then its definition, after the marker block, as in `src/ufo2p/u_000a34f0.c`. All of them at file scope, each before its first use.
- File order does not change check's verdict (calls resolve through fixups), except for a jump-table function, whose table must come first in the unit (`docs/matching.md#relocation-rules`). The pilot has none.
- The definition keeps the row's name (`func_XXXXXXXX`, or its symbols.csv name).
- Use `D_XXXXXXXX` and `func_XXXXXXXX` placeholders for data and callees. Never invent names, and never rename one: a rename in a matching session is not applied anywhere. Naming is the readability pass's work (D-19), through its proposals (planned: the driver's rename step is not built yet); a name idea, with its evidence, goes in notes.md.

A struct the function needs is declared in the unit, never in a header: a header would not land (only the unit's bytes do), and the gate never compiles from a view's `include/`. Shared types and headers come later, through readability proposals (planned: the driver writes no header yet, D-19). Use `struct unk_XXXX` (its size in hex), the `s8`/`u8`/`s16`/`u16`/`s32`/`u32` typedefs of `include/common.h`, an offset comment per field, a size comment, and explicit padding where an offset must be pinned (the packing is not known yet, `docs/coding-style.md#watcom-specifics`):

```c
struct unk_002C {
    /* 0x00 */ s32 flags;
    /* 0x04 */ s16 x;
    /* 0x06 */ s16 pad_06;
    /* 0x08 */ u8 data[0x24];
}; /* size: 0x2C */
```

## The attempt wrapper

| Command | What it does |
|---|---|
| `uv run --frozen reverseapoc attempt check` | compiles your view unit (`$REVERSEAPOC_UNIT_FILE`) in the container under the view's rule and runs the full check; prints a summary |
| `uv run --frozen reverseapoc attempt check --sweep` | the flag matrix for the claimed function (stage 1, and stage 2 after a near miss); a diagnostic, never a match |
| `uv run --frozen reverseapoc attempt asm` | prints the claimed function's original listing (no check run) |
| `uv run --frozen reverseapoc attempt asm <NAME>` | the listing of another function of the same EXE, e.g. a callee |
| `uv run --frozen reverseapoc attempt context` | rebuilds and prints the context pack (callers, callees, externs, draft, look-alikes, earlier notes); it is printed, so no Read of context.md is needed |

- Run every `attempt check`, plain or `--sweep`, with the Bash tool's `timeout` set to 600000. The wrapper stops a run at 580 s and logs it as exit `2`.
- "another check is running in this attempt" means a check is still running, or one was killed. Do not retry. Work from the last result, then stop.
- The arguments are fixed: the wrapper takes the unit, function and flags from the driver, and refuses anything else with exit `2`.

`attempt check` exits:
- `0`: the claimed function matches (objdiff 100, reloc and bytes ok) and check passes its whole unit. Only this is a match.
- `1`: a mismatch, or the claimed function was not compiled (the summary says "was not compiled (still INCLUDE_ASM?)").
- `2`: refused or tool error, a compile error included. Exit 2 never measures anything.

`attempt check --sweep` exits `0` when it ran and `2` when it did not, never `1`: a sweep is a diagnostic, never a match.

The sweep's two stages:
- Stage 1: 30 cells (10.6, 10.5 and 11.0, `-4r`/`-5r`, no `-o` set or `-ox`, `-os`, `-ot`, `-oneatx`), or 60 when `-s` is toggled for a function that calls `__CHK`.
- Stage 2 runs only after a near miss: no stage-1 cell is perfect, and the best one is at or above 90% with its relocation check ok. It varies that best cell, always under 10.6, in up to 24 cells numbered on from 31 or 61: each single `-o` letter (`-od`, `-of+`, `-or`, `-oi`, `-om`, `-ol`, `-on`, `-op`) or KKND's `-of+ -omiler` in place of its `-o` set; each letter added to its `-o` set, when it has one; and `-zp1`/`-zp2`/`-zp4`/`-zp8`, `-zm`, `-fp3`/`-fp5` appended. Spec forms: `wcc386@10.6 -4r -oi -s -fpi`, `wcc386@10.6 -4r -s -fpi -zp4`.
- Either stage's hit comes through the same `sweep_hit` and the same `sweep hit: needs flags` line. Read the stage from the output, never from the flags.

A sweep after a near miss, as it prints (stage 2 cell 42 hit):

```
attempt check --sweep 16/25, 388 s (9 left) ufo2p/u_00089980 func_0008AAF0: exit 0 SWEEP RAN (a diagnostic: never a match)
  a sweep is a diagnostic: it never lands and never edits config/cflags.txt
  best cell 01  wcc386@10.6 -4r -s -fpi  objdiff 98.9%  reloc ok  differing 6
  stage 2 best cell 42  wcc386@10.6 -4r -s -fpi -zp4  objdiff 100%  reloc ok  differing 0
  sweep hit: needs flags wcc386@10.6 -4r -s -fpi -zp4 (the owner decides; cflags.txt is owner-only)
saved <attempt dir>/checks/0016.json (full JSON) and <attempt dir>/checks/0016.c (the C checked)
notes: <attempt dir>/notes.md
```

check's JSON, in `checks/NNNN.json`:
- `ok`;
- per function in `functions[]`: `name`, `va`, `objdiff_percent`, `reloc.ok`, `reloc.problems` (one sentence per wrong field), `bytes.ok`, `bytes.differing` and `bytes.first_va`;
- `problems[]`: the unit's account, e.g. a row that is neither defined nor marked;
- `splice[]`: per EXE, `ok` and `first_difference`.

A sweep's JSON has `cells[]`, and `stage2` (null unless stage 2 ran: `from`, the stage-1 cell it varied, its own `cells`, and its `best` cell numbers). Each cell reports, for the claimed function under its `compiler` and `flags`, `objdiff_percent`, `reloc_ok` and `differing` (bytes outside relocated fields that differ). A cell at 100% with `reloc_ok` and `differing` 0 under other flags than the unit's rule is logged as `sweep_hit`: stage 1's first hit, else stage 2's. A sweep hit is never a match until a plain `attempt check` under the new rule passes, and only the owner adds that rule.

### From a mismatch to the instruction

1. Read the newest `checks/NNNN.json` and find the claimed function in `functions[]`.
2. Take `bytes.first_va`, and each address named in `reloc.problems`.
3. Find those addresses in the `attempt asm` listing. Each line is `  0xADDRESS  instruction`. The line at `first_va` is the first original instruction your object gets wrong.
4. Change the C shape behind that instruction, one change per check, using the idioms in `docs/matching.md`.

You get no disassembly of your own object. If that blocks you, write it in notes.md as a tooling request.

## When to give up

Stop when any of these holds:
- `attempt check` exited `0`: stop editing, because the driver gates the view unit as you leave it;
- three different C shapes leave objdiff below 100;
- the check budget is used;
- about 25 of 30 minutes or 35 of 40 turns are gone.

On stopping:
1. Write notes.md first, before any optional last step.
2. If the remaining difference is register allocation or instruction choice and time remains, you may run one `attempt check --sweep`, then add its result to notes.md.
3. Leave the view unit as it is. Do not restore `INCLUDE_ASM` and do not re-check to confirm. The driver keeps every `checks/NNNN.c`, scores the best run, and abandons the view; the repo-root unit is never yours to reset.

After a sweep hit, record it in notes.md first. Then stop, or try C shapes under the unit's rule within the budget; either way, end with notes.md written.

notes.md holds, in this order:
1. The outcome: matched, or the best objdiff with its check number (`checks/NNNN.c` is that C).
2. Each shape tried: one line each, with its best percent and check number.
3. The remaining difference: `first_va`, the original instruction there, and any `reloc.problems`.
4. The sweep result, if one ran: the best cell, and any hit as "needs flags <spec>" with its cell number and stage (as printed).
5. Name ideas for callees, globals or the function, each with its evidence.
6. What to try next, most promising first.

Every fact in notes.md is read, never guessed: siblings from `config/<exe>/functions.csv` or the check JSON, instructions from the listing, numbers from `checks/NNNN.json`. Write "not read" for anything you did not read.

A match is never your claim. The driver re-checks it, and only exit `0` counts.
