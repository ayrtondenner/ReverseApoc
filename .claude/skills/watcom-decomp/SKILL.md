---
name: watcom-decomp
description: Use when working in a ReverseApoc matching attempt - writing or fixing the C of a claimed Watcom C 10.6 function in src/<exe>/<unit>.c, reading attempt check output, choosing extern types or prototypes, or deciding whether to stop and leave notes.
---

# Matching one Watcom function

You make one claimed function byte-identical to the original, proven by `attempt check`, or you stop and leave notes. This page holds every rule and fact the attempt needs: read the docs it links only for depth, and never read `tools/` to find a rule.

**Quick reference**

| Question | Answer |
|---|---|
| The only Bash | the five wrapper commands under "The attempt wrapper". Anything else (`ls`, `cat`, `sed`, a host `reverseapoc check`, `docker`, `objdiff-cli`) is denied and costs a turn. Look around with Read, Grep and Glob. |
| What you may write | the claimed unit file, a new header under `include/`, and this attempt's notes.md. Its full path is printed after `notes:` by `attempt check` and (on stderr) `attempt context`. Nothing else. |
| Check exit codes | `0` matched; `1` mismatch (compiled and compared, something differs); `2` refused or tool error, which includes a compile error. Exit 2 never measures anything. |
| Check budget | 25 runs per attempt. Every run counts: exit `0`, `1` or `2`, and each `--sweep`. A call the wrapper refuses before running counts nothing. |
| Real time budget | 30 minutes, about 90 s per check: plan on about 15 checks. A sweep takes minutes. |
| Full evidence | `<attempt dir>/checks/NNNN.json` (check's JSON) and `checks/NNNN.c` (the exact C that run checked), one pair per run, plus a line in `checks.jsonl`. Each check prints both full paths. |
| Default flags | `wcc386@10.6 -4r -s -fpi` (the `*` rule of `config/cflags.txt`). |
| Linker names | function `func_000A3980` links as `func_000A3980_`; data `D_0012EFAC` as `_D_0012EFAC`. A symbols.csv name is used verbatim. |
| Marker | `INCLUDE_ASM(func_XXXXXXXX);` (one argument). |

Never:
- write `#pragma aux` of any kind, `_asm`, `__asm` or `_Pragma` (the hook blocks them);
- edit `config/cflags.txt`, anything else in `config/`, `include/common.h`, `include/watcom_compat.h`, tools, tests or build files;
- run a check with `run_in_background`, or start a second check while one runs: checks run one at a time, in the foreground.

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

- Every unit builds with the `*` default above unless `config/cflags.txt` has a rule for it.
- A function whose target starts with `push imm32; call __CHK` was built without `-s`. It needs a per-file rule only the owner can add. Note it as "needs flags (no -s)" and stop.
- `config/cflags.txt` is owner-only. A sweep hit is evidence for the owner, never a change you make.
- Depth: `docs/toolchain.md#flags`.

## C89 and the lint

- Declare every local at the start of its block, before any statement. No `for (int i...)`, no mixed declarations and code.
- `/* */` comments only, never `//`. No `inline`, `bool`, VLAs, designated initializers or compound literals.
- Never reorder declarations: their order decides the stack slots.
- The owner's lint (`reverseapoc lint`, clang `-std=gnu89 -Werror=declaration-after-statement`) runs before a match is committed. A C89 slip fails it even when check passes.
- Depth: `docs/coding-style.md`.

## Pragmas

- Agents write no `#pragma aux` of any kind during the pilot: not for a calling convention, not for registers, not to force a match.
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

- Delete the claimed function's `INCLUDE_ASM(func_XXXXXXXX);` line. Leave every other marker as it is.
- Put the prototypes and externs it needs, then its definition, after the marker block, as in `src/ufo2p/u_000a34f0.c`. File order does not change the object.
- The definition keeps the row's name (`func_XXXXXXXX`, or its symbols.csv name).
- Use `D_XXXXXXXX` and `func_XXXXXXXX` placeholders for data and callees. Never invent names.

## The attempt wrapper

| Command | What it does |
|---|---|
| `uv run --frozen reverseapoc attempt check` | compiles the claimed unit in the container and runs the full check; prints a summary |
| `uv run --frozen reverseapoc attempt check --sweep` | the flag matrix (30 or 60 cells) for the claimed function; a diagnostic, never a match |
| `uv run --frozen reverseapoc attempt asm` | prints the claimed function's original listing (no check run) |
| `uv run --frozen reverseapoc attempt asm <NAME>` | the listing of another function of the same EXE, e.g. a callee |
| `uv run --frozen reverseapoc attempt context` | rebuilds and prints the context pack (callers, callees, externs, draft, look-alikes, earlier notes) |

- Run `attempt check --sweep` with the Bash tool's `timeout` set to 600000. The wrapper stops a run at 580 s and logs it as exit `2`.
- "another check is running in this attempt" means a check is still running, or one was killed. Do not retry. Work from the last result, then stop.
- The arguments are fixed: the wrapper takes the unit, function and flags from the driver, and refuses anything else with exit `2`.

check's JSON, in `checks/NNNN.json`:
- `ok`;
- per function in `functions[]`: `name`, `va`, `objdiff_percent`, `reloc.ok`, `reloc.problems` (one sentence per wrong field), `bytes.ok`, `bytes.differing` and `bytes.first_va`;
- `problems[]`: the unit's account, e.g. a row that is neither defined nor marked;
- `splice[]`: per EXE, `ok` and `first_difference`.

A sweep's JSON has `cells[]` (`compiler`, `flags`, `objdiff_percent`, `reloc_ok`, `differing`). A 100% cell under other flags is logged as `sweep_hit`.

### From a mismatch to the instruction

1. Read the newest `checks/NNNN.json` and find the claimed function in `functions[]`.
2. Take `bytes.first_va`, and each address named in `reloc.problems`.
3. Find those addresses in the `attempt asm` listing. Each line is `  0xADDRESS  instruction`. The line at `first_va` is the first original instruction your object gets wrong.
4. Change the C shape behind that instruction, one change per check, using the idioms in `docs/matching.md`.

You get no disassembly of your own object. If that blocks you, write it in notes.md as a tooling request.

## When to give up

Stop when any of these holds:
- three different C shapes leave objdiff below 100;
- the check budget is used;
- about 25 of 30 minutes or 35 of 40 turns are gone.

On stopping:
1. Write notes.md first, before any optional last step.
2. If the remaining difference is register allocation or instruction choice and time remains, you may run one `attempt check --sweep`, then add its result to notes.md.
3. Leave the unit file as it is. Do not restore `INCLUDE_ASM` and do not re-check to confirm. The driver keeps every `checks/NNNN.c`, scores the best run and resets the unit itself.

notes.md holds, in this order:
1. The outcome: matched, or the best objdiff with its check number (`checks/NNNN.c` is that C).
2. Each shape tried: one line each, with its best percent and check number.
3. The remaining difference: `first_va`, the original instruction there, and any `reloc.problems`.
4. The sweep result, if one ran: the best cell, and any hit as "needs flags X".
5. What to try next, most promising first.

A match is never your claim. The driver re-checks it, and only exit `0` counts.
