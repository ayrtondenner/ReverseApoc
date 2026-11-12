---
name: watcom-decomp
description: Use when working in a ReverseApoc matching attempt - writing or fixing the C of a claimed Watcom C 10.6 function in your private view unit (REVERSEAPOC_UNIT_FILE), declaring a struct or extern it needs, reading attempt check or sweep output, or deciding whether to stop and leave notes.
---

# Matching one Watcom function

You make one claimed function byte-identical to the original, proven by `attempt check`, or you stop and leave notes. This page holds every rule and fact the attempt needs: read the docs it links only for depth, and never read `tools/` to find a rule.

**Quick reference**

| Question | Answer |
|---|---|
| Your file | the private view unit at `$REVERSEAPOC_UNIT_FILE`. The goal you were given names its path, `build/driver/<run>/<exe>/<func>/attempt-<n>/view/src/<exe>/<unit>.c`. It is the only C you edit. |
| What you may write | that view unit, and in this attempt's directory notes.md (its full path follows `notes:` in `attempt check` output, and `attempt context` prints it on stderr) and, beside it, `plan.json`, `check-note.json` and `giveup.json` (under "The attempt wrapper" and "When to give up"). No header anywhere. The hooks also allow `proposals.jsonl` (`REVERSEAPOC_PROPOSALS`), but a matching session writes none: nothing applies a matching session's proposals (the driver's rename step runs after readability sessions only). A name or header idea goes in notes.md, even when a denial message suggests proposals.jsonl. Nothing else. |
| Types you need | declared in the view unit, at file scope (see "Replacing INCLUDE_ASM"). |
| Names | placeholders stay: `func_XXXXXXXX`, `D_XXXXXXXX` and your own function's name. A name idea goes in notes.md. |
| The only commands | the seven wrapper commands under "The attempt wrapper". Anything else (`ls`, `cat`, `sed`, a host `reverseapoc check`, `docker`, `objdiff-cli`) is denied and costs a turn. Read and search files with your harness's own file tools wherever it lets them read, never with a command; anywhere else, or with no file tools, read through the wrapper: `attempt context`, `attempt asm`, `attempt asm <NAME>` and `attempt check` print what you need. |
| Check exit codes | under "The attempt wrapper" below. |
| Check budget | 25 runs per attempt. Every run counts: exit `0`, `1` or `2`, and each `--sweep`. A call the wrapper refuses before running counts nothing, such as a check without a valid `plan.json` and `check-note.json`. |
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
- send a check to the background yourself (`run_in_background` or any other way), or start a second check while one runs: checks run one at a time, in the foreground, each waited on until it exits.

A write or command the hooks deny costs a turn and counts as a hook block: never try one "just to see". A changed path or a command that got past the hooks is worse: the driver's audit after the session finds it, the night stops on a guardrail and nothing is committed.

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
- Flags are never your choice. A sweep hit (under "The attempt wrapper") is evidence: the driver records it in the attempt record, and an executor later turns it into a proposal with `reverseapoc flags propose`, which reads every sweep's saved `checks/NNNN.c`. Only the owner lands a rule, with `reverseapoc flags approve`. So once a sweep with a hit has run, the hit is safe: write it in notes.md and stop (see "When to give up").
- Depth: `docs/toolchain.md#flags` and `docs/toolchain.md#phase-7-flag-rules`.

## C89 and the lint

- Declare every local at the start of its block, before any statement. No `for (int i...)`, no mixed declarations and code.
- `/* */` comments only, never `//`. No `inline`, `bool`, VLAs, designated initializers or compound literals.
- In a function you are matching, address-taken locals, aggregates and volatiles live in memory. They sort by size, the largest lowest, each padded to 4.
- Among those, declaration order breaks ties only when the frame has one size, of 1, 2 or 4 bytes. Inside a block the first declared sits highest, so swapping two declarations swaps their slots. Across blocks, ints sit by the block's place in the source, an earlier block lower, and chars and shorts do not follow their blocks. In any other tie the order is not known: it is not the declaration order, and only a check can say whether a swap moves it. The same goes in a frame of one size for three or more multi-element arrays such as `char[4]` or `short[2]`, for a `char[2]` beside shorts, and for two multi-element arrays beside a later block.
- Register-candidate scalars, integers and pointers of 4 bytes, ignore declaration order and scope. Assignment order, use order, type and loop weight move them, so change those. Under 4 bytes this need not hold: shorts spilled beside a short in memory do move with their declarations.
- Floats and doubles are not covered: a float with no address taken in a tie still moves with its declarations, and a double moves the ints beside it by its use alone.
- A function that already matches is never reordered.
- C89 is required: the driver lints the unit before it commits a match (`reverseapoc lint`, clang `-std=gnu89 -Werror=declaration-after-statement`). A C89 slip fails the attempt even when check passes.
- Depth: `docs/coding-style.md`; `docs/matching.md` for the slot rules, which win where the two differ.

## Pragmas

- Agents write no `#pragma` of any kind during the pilot: not `#pragma aux` (a calling convention, registers, forcing a match), and not `#pragma on/off (check_stack)`, which changes code the way a flag does. Flags are owner-only.
- Calling-convention pragmas come only in human-reviewed commits.
- Default `__watcall` needs no pragma. A register difference is a C-shape or flags question; record it in notes.md.

## Relocation rules

check passes a function only when all of these hold (`docs/matching.md#relocation-rules`):
- objdiff 100%, every non-relocated byte identical, and the same length;
- every `call rel32` hits the same function;
- every absolute fixup resolves to the same target as the original's LE fixup;
- no reference to data of the unit's own segments, such as a string literal. The one exception is a leading jump table (see "Strings, statics and jump tables").

## Strings, statics and jump tables

- A string or any other constant data the target addresses becomes its extern `D_` symbol (`extern char D_0012F3A0[];`). Never write the literal: it emits new data in our object and fails the relocation check.
- A `switch` that compiles to a jump table (`jmp cs:[eax*4+...]`) matches only when its table leads the unit. wcc386 puts the table at the start of the object, so three things must hold: the table's `D_XXXXXXXX` data-in-code row sits right before your function's row in `config/<exe>/functions.csv`, with the same `unit`; your definition is the first in the file that compiles (rows still `INCLUDE_ASM` emit nothing, so they may stand before it); and only your function jumps through the table. Write the `switch` in C: the compiler emits the table.
- A table between two publics fails closed: a table compiled after another function belongs to no row, and check refuses the function that jumps through it. So put your definition above any compiled function of the unit: that moves yours and leaves its text alone.
- Stop and say so in notes.md when the table's row is in another unit, or when a compiled function of the unit has its own leading table. A unit leads with one table only: if a row still `INCLUDE_ASM` has a table too, go on and note that it can no longer lead.
- A static function keeps its row's name: `static <type> func_XXXXXXXX(...)`, or its symbols.csv name. Any other name fails check, and so does static data.

## Replacing INCLUDE_ASM

Work in your view unit, `$REVERSEAPOC_UNIT_FILE`. The view is the driver's private copy of HEAD's `src/`, `include/` and `config/` for this attempt. The repo-root unit is HEAD's copy, and you never write `src/<exe>/<unit>.c`: after the session the driver copies your view unit's bytes there, then lints and gates it, and puts it back if that fails.

- Delete the claimed function's `INCLUDE_ASM(func_XXXXXXXX);` line. Leave every other marker as it is.
- Put the types, prototypes and externs it needs, then its definition, after the marker block, as in `src/ufo2p/u_000a34f0.c`. All of them at file scope, each before its first use.
- File order does not change check's verdict (calls resolve through fixups), except for a jump-table function, whose table must come first in the unit (`docs/matching.md#relocation-rules`).
- The definition keeps the row's name (`func_XXXXXXXX`, or its symbols.csv name).
- Use `D_XXXXXXXX` and `func_XXXXXXXX` placeholders for data and callees. Never invent names, and never rename one: a rename in a matching session is not applied anywhere. Naming is the readability pass's work (D-19), through its proposals, which the driver applies after readability sessions only; a name idea, with its evidence, goes in notes.md.

A struct the function needs is declared in the unit, never in a header: a header would not land (only the unit's bytes do), and the gate never compiles from a view's `include/`. Shared types and headers come later, through readability proposals, which the driver writes as headers after readability sessions (D-19). Use `struct unk_XXXX` (its size in hex), the `s8`/`u8`/`s16`/`u16`/`s32`/`u32` typedefs of `include/common.h`, an offset comment per field, a size comment, and explicit padding where an offset must be pinned (the packing is not known yet, `docs/coding-style.md#watcom-specifics`):

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
| `uv run --frozen reverseapoc attempt asm` | prints the claimed function's original listing, with the converter's notes (no check run) |
| `uv run --frozen reverseapoc attempt asm <NAME>` | the listing of another function of the same EXE, e.g. a callee, with its notes |
| `uv run --frozen reverseapoc attempt context` | rebuilds and prints the context pack (callers, callees, externs, draft, look-alikes, earlier notes); it is printed, so you need not open context.md |
| `uv run --frozen reverseapoc attempt plan` | checks your `plan.json` against the function's size and prints its regions (no check used) |
| `uv run --frozen reverseapoc attempt giveup` | checks your `giveup.json` (no check used); see "When to give up" |

The pack's "Earlier give-ups" and "Earlier best C" sections say where earlier attempts on this function stopped and hold the best earlier definition: read them before you plan.

**The plan and the note.** A check needs two files beside notes.md. Without them `attempt check`, plain or `--sweep`, is refused with exit `2` and uses none of the 25 checks. The refusal names what is missing or wrong, e.g. `write plan.json beside notes.md first`: write that file, then run the check again.

1. Before the first check, write `plan.json` from the listing and run `attempt plan` until it accepts it. One JSON object with exactly:
   - `frame`: the prologue and the frame size, in words;
   - `slots`: one text per stack slot (an empty list when there is none);
   - `calls`: one text per call, with its convention (or an empty list);
   - `regions`: objects with `start`, `end` and `intent`, byte offsets from the function's start, `end` one past the region's last byte. They are sorted and contiguous from 0 to the function's size. One region is enough under 64 B; from 64 B write two or more. At 256 B and up every inner boundary is a multiple of 0x100, the region board's grid (a function of exactly 0x100 bytes takes one region).
   Every check reads the plan again: when a check proves it wrong, write the corrected plan.
2. Before every check, write `check-note.json`: one JSON object with exactly `change` (what this run changes), `why` (the evidence for it) and `expect` (what it should show), each at most 400 characters.
3. The check moves the note to `checks/NNNN.note.json` and adds `observed`: the exit, objdiff, bytes differing, the first difference, the window's first row and the regions. Never add `observed` yourself: a note that holds it is refused. Each check needs a new note.

At 256 B and up each check's summary shows the region board after the claimed function's window, one line per 0x100 bytes from the function's start: `exact in NNNN` names the plain check of this attempt whose bytes match there, `closest NNNN (k differ)` the nearest one. A region exact in an earlier check is solved: carry that check's C (`checks/NNNN.c`) for it, and work on the regions that still differ.

- Run every `attempt check`, plain or `--sweep`, in the foreground and wait until it exits. If your command tool takes a timeout, set it to 600000 (milliseconds, its longest); if it hands the command back still running, poll it until it exits and never end your turn while it runs. The wrapper stops a run at 580 s and logs it as exit `2`.
- "another check is running in this attempt" means a check is still running, or one was killed. Do not retry. Work from the last result, then stop.
- The arguments are fixed: the wrapper takes the unit, function and flags from the driver, and refuses anything else with exit `2`.

`attempt asm` prints a note after some lines, past a `  ; `. Notes reach this command's output only, so `attempt context` and the listing files do not show them. The exception is a `<kind> -> <name>` note, such as `off32 -> D_00091000`: that is the listing's own, a fact from an LE fixup, and the listing files show it too.

- `cases: 0: .L00034590, 1: .L000345A0` on a table jump is read from the original's fixups, so it is exact. Each number is the entry's place in the table, always from 0, not your `case` value: read the `sub`, `dec` or `add` on the index above the jump and add that bias back (after `sub eax, 5`, entry 0 is `case 5`), and entries that share the default's target take no `case`. `.L00034590` names address 0x00034590: most targets have no label line, so find the line that starts with that address. A target written any other way (a row's name, `func_X+0x1` or a bare address) lands outside your function: check refuses the table, so stop and say so in notes.md. A table jump with no note has a table the tool could not read.
- `eax=<expr> edx=<expr>` on a call comes from the converter's symbolic state: a hint to check against the listing, with `attempt check` as the proof. It shows what those registers hold when something still reads them, the call or code after it, and it leaves out what the converter does not know. A shown register is no proof of an argument, and a missing one is no proof of none: take the argument count from the callee's listing.
- `r_<reg>` in a note is the value that register held at the last point the converter named it, not the register now: `eax=5 edx=r_eax` says `edx` holds what `eax` held before the 5. That point can be the start of a block, so it need not be the function's entry value either: read back up the listing before you write the argument.
- `h_<address>` is a hole: the converter could not read the instruction at that hex address, so the value is unknown.
- `al=<expr>` is a byte or word write at that width: the rest of the register is not in the text.
- `s_<hex>` is a stack slot. `r_p<n>` is the n-th argument, passed on the stack: `r_p5` is the first.

`attempt check` exits:
- `0`: the claimed function matches (objdiff 100, reloc and bytes ok) and check passes its whole unit. Only this is a match.
- `1`: a mismatch, or the claimed function was not compiled (the summary says "was not compiled (still INCLUDE_ASM?)").
- `2`: refused or tool error, a compile error included. Exit 2 never measures anything. A refusal before the run, such as a missing plan or note, uses no check.

`attempt check --sweep` exits `0` when it ran and `2` when it did not, never `1`: a sweep is a diagnostic, never a match.

The sweep's two stages:
- Stage 1: 30 cells (10.6, 10.5 and 11.0, `-4r`/`-5r`, no `-o` set or `-ox`, `-os`, `-ot`, `-oneatx`), or 60 when `-s` is toggled for a function that calls `__CHK`.
- Stage 2 runs only after a near miss: no stage-1 cell is perfect, and the best one is at or above 90% with its relocation check ok. It varies that best cell, always under 10.6, in up to 24 cells numbered on from 31 or 61: each single `-o` letter (`-od`, `-of+`, `-or`, `-oi`, `-om`, `-ol`, `-on`, `-op`) or KKND's `-of+ -omiler` in place of its `-o` set; each letter added to its `-o` set, when it has one; and `-zp1`/`-zp2`/`-zp4`/`-zp8`, `-zm`, `-fp3`/`-fp5` appended. Spec forms: `wcc386@10.6 -4r -oi -s -fpi`, `wcc386@10.6 -4r -s -fpi -zp4`.
- Either stage's hit comes through the same `sweep_hit` and the same `sweep hit: needs flags` line. Read the stage from the output, never from the flags.

A sweep after a near miss, as it prints (stage 2 cell 42 hit):

```
attempt check --sweep 16/25, 388 s (9 left) ufo2p/u_00089980 func_0008AAF0: exit 0 SWEEP RAN (a diagnostic: never a match)
  a sweep is a diagnostic: it never lands and never edits config/cflags.txt
  best cell 01  wcc386@10.6 -4r -s -fpi  objdiff 98.9%  reloc ok  differing 6  first_va 0x0008AB14  size 180
  stage 2 best cell 42  wcc386@10.6 -4r -s -fpi -zp4  objdiff 100%  reloc ok  differing 0  first_va none  size 180
  sweep hit: needs flags wcc386@10.6 -4r -s -fpi -zp4 (the owner decides; cflags.txt is owner-only)
saved <attempt dir>/checks/0016.json (full JSON) and <attempt dir>/checks/0016.c (the C checked)
notes: <attempt dir>/notes.md
```

check's JSON, in `checks/NNNN.json`:
- `ok`;
- per function in `functions[]`: `name`, `va`, `objdiff_percent`, `reloc.ok`, `reloc.problems` (one sentence per wrong field), `bytes.ok`, `bytes.differing` and `bytes.first_va`; and `window[]`, the rows the summary prints when the bytes differ (empty when they match): each row has `first`, `ours` and `original` (null where that side has no instruction), and each of those has `va`, `mnemonic`, `operands` and `relocated`;
- `problems[]`: the unit's account, e.g. a row that is neither defined nor marked;
- `splice[]`: per EXE, `ok` and `first_difference`.

A sweep's JSON has `cells[]`, and `stage2` (null unless stage 2 ran: `from`, the stage-1 cell it varied, its own `cells`, and its `best` cell numbers). Each cell reports, for the claimed function under its `compiler` and `flags`, `objdiff_percent`, `reloc_ok` and `differing` (bytes outside relocated fields that differ), `first_va` (its first differing byte, null when none) and `size` (your function's bytes under that cell). A cell at 100% with `reloc_ok` and `differing` 0 under other flags than the unit's rule is logged as `sweep_hit`: stage 1's first hit, else stage 2's. A sweep hit is never a match until a plain `attempt check` under the new rule passes, and only the owner adds that rule.

### From a mismatch to the instruction

1. Read the window the summary prints under the claimed function, after `first difference at`: your instructions on the left, the original's on the right, one per row. The row marked `>` is the first differing instruction; `-` means that side has no instruction there.
2. An instruction that ends in `(relocated)` covers a relocated field: the byte compare ignores that operand, and yours shows the unlinked placeholder. A wrong target there shows in `reloc.problems`, never in the window.
3. For the rest of the original, take `bytes.first_va` and each address named in `reloc.problems` and find them in the `attempt asm` listing. Each line is `  0xADDRESS  instruction`, some with a note after it.
4. Change the C shape behind that instruction, one change per check, using the idioms in `docs/matching.md`.

The window is all you see of your own object: at most 8 rows around the first difference, never the whole function. If that blocks you, write it in notes.md as a tooling request.

## When to give up

Stop only when one of these holds:
- `attempt check` exited `0`: stop editing, because the driver gates the view unit as you leave it;
- a sweep printed `sweep hit: needs flags`: write the hit in notes.md and stop, because the driver starts no new session on the function for the rest of the night;
- three different C shapes leave objdiff below 100;
- all 25 check runs are used;
- about 25 of 30 minutes or 35 of 40 turns are gone;
- needs flags (no -s), a jump table that cannot lead the unit or has a target outside the function, or another check running in this attempt, each as its section above says.

When the /goal blocks a stop: if a rule above holds, name it in one message with the printed line that shows it; if none holds, the attempt is not done, so make the next C shape.

On stopping:
1. Write notes.md first, then `giveup.json` (below) unless `attempt check` exited `0`, before any optional last step.
2. If the remaining difference is register allocation or instruction choice and time remains, you may run one `attempt check --sweep`, then add its result to notes.md.
3. Leave the view unit as it is. Do not restore `INCLUDE_ASM` and do not re-check to confirm. The driver keeps every `checks/NNNN.c`, scores the best run, and abandons the view; the repo-root unit is never yours to reset.
4. End with one last message that names the rule that holds, in its words above, and its evidence (check numbers or the printed line): the /goal's judge reads only the conversation.

`giveup.json`, beside notes.md, is how a stop without a match is recorded. Write it, then run `attempt giveup`: it checks the file and prints what the driver will record (no check used); on exit `2` fix what it names and run it again. The driver records it with your best check's C, and later attempts read it in their pack. One JSON object with exactly:
- `category`: one of `flags`, `block_layout`, `stack_layout`, `register_allocation`, `instruction_idiom`, `types_or_struct`, `call_convention`, `compile_error`, `other`;
- `tried`: the C shapes tried, in one line;
- `still_differs`: what still differs, such as the first differing address and its instruction;
- `suspected_cause`: why it differs, as far as the evidence goes.

A sweep hit or "needs flags (no -s)" is category flags. The three texts are plain prose, each at most 200 characters, with no C in them: no braces or semicolons, and no hex run of 65 characters or more. The C stays in `checks/NNNN.c`.

notes.md holds, in this order:
1. The outcome: matched, or the best objdiff with its check number (`checks/NNNN.c` is that C).
2. Each shape tried: one line each, with its best percent and check number.
3. The remaining difference: `first_va`, the original instruction there, and any `reloc.problems`. The summary shows at most 8 rows around the first difference and a count, never the rest of your object, so if `first_va` falls on a stack operand write `slots only?`, with that instruction and `differing`. The owner runs the search outside sessions, and a session never does.
4. The sweep result, if one ran: the best cell, and any hit as "needs flags <spec>" with its cell number and stage (as printed).
5. Name ideas for callees, globals or the function, each with its evidence.
6. What to try next, most promising first.

Every fact in notes.md is read, never guessed: siblings from `config/<exe>/functions.csv` or the check JSON, instructions from the listing, numbers from `checks/NNNN.json`. Write "not read" for anything you did not read.

A match is never your claim. The driver re-checks it, and only exit `0` counts.
