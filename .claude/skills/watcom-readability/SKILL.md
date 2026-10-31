---
name: watcom-readability
description: Use when working in a ReverseApoc readability session - naming, commenting or documenting an already-matched Watcom C unit in its view, answering readlint findings (RL01 to RL06, placeholder names, header comments, magic literals), writing proposals.jsonl renames or header proposals, or deciding whether to stop and leave notes.
---

# Making one matched unit readable

The unit already matches: its C compiles to the original bytes. You make it readable without moving one byte. `attempt check` proves the bytes and runs readlint, and readlint decides what is readable. This page holds every format the session needs: never read `tools/` to learn one.

**Quick reference**

| Question | Answer |
|---|---|
| What you may write | your view unit (`REVERSEAPOC_UNIT_FILE`), this session's notes.md, and `proposals.jsonl` (`REVERSEAPOC_PROPOSALS`) beside it in `<attempt dir>/proposals.jsonl`. `attempt check` prints the notes.md path after `notes:`. The hooks deny every other write. |
| The only Bash | the five wrapper commands under "The attempt wrapper". Look around with Read, Grep and Glob. |
| Budgets | 40 turns (`--max-turns`), 25 checks per attempt, 30 minutes. Each check prints its elapsed seconds and the checks left (`check 3/25, 88 s (22 left)`); budget by those against the clock. |
| The verdict | `attempt check` exits `0` only when every function still matches and readlint is clean. A pending rename does not fail it. |
| What lands | the final text of your view unit, not your best check (see "When to stop"). |
| Evidence of each run | `<attempt dir>/checks/NNNN.c` (the exact C checked) and `checks/NNNN.json`. |

Never:
- edit `config/<exe>/symbols.csv`, anything under `include/` or `config/` (`config/readlint-allow.csv` too), tools, tests or build files. Names and shared headers change only through proposals (D-19);
- rename a linked name inside the unit (the defined function, a callee, a `D_` global): its linker name would change and the check would lose it. Propose it instead;
- copy a name, a comment or any text from OpenApoc code or comments, or from a wiki (D-21);
- keep an edit the check says moved a byte, or end the session on such text;
- change which functions the unit defines in C or marks `INCLUDE_ASM`;
- write a `#pragma` of any kind, `_asm` or `__asm`;
- run a check with `run_in_background`, or start a second check while one runs.

## What you may change

In the view unit:
- comments, above all the header comment of every function (next section);
- names of locals and parameters (they have no linker name);
- whitespace and line breaks;
- a `#define` that names a literal (see "Constants without changing bytes");
- types the unit introduces: a new `typedef`, `struct` or `enum` in the unit. An alias of the type already declared (`typedef s32 clock_units_t;`) keeps the bytes. Anything else, the check must prove.

Not, because the bytes depend on it:
- the declared type of an existing local, parameter or extern. Signedness turns `jl`/`jge` into `jb`/`jae`, and width changes the loads (`movsx`, `movzx`, `mov`). `s32` stays `s32` even when the value is never negative;
- the order of declarations (it decides the stack slots), statements or operands, or any "simpler" shape;
- the names of functions and `D_` globals: they change through `proposals.jsonl` only.

## Header comments

Every function the unit defines needs a header comment (RL02) in this form (RL03):
- the first line is `<name>: <purpose>`. The name is the one the unit defines now (`func_00012340` until its rename lands), and the purpose has 3 words or more;
- exactly one line `Address: <UFO2P.EXE|TACP.EXE> 0x%08X`: the unit's EXE file name (with `.EXE`) and the function's start, 8 upper-case hex digits;
- one or more lines `Evidence: <string|table|call|vocab>: <text>`, each on one line (the kinds are in the next section);
- any other lines you like.

readlint takes the last comment between the previous `;`, `}` or directive and the definition. So put the header directly above the definition, after the `#define`s, externs and prototypes. A prototype or another comment between them takes its place.

A whole view unit after a readability edit (made-up addresses; the output example below reads this unit):

```c
#include "common.h"

#define CLOCK_FRAME_WRAP 0x24

extern s32 D_000D1230;
void func_00012400(void);

/* func_00012340: advance the game clock one frame
 * Adds the speed to the frame fraction; each wrap is one game step.
 * Address: UFO2P.EXE 0x00012340
 * Evidence: call: the only caller, the frame loop at 0x00011000, calls it once per frame
 * Evidence: call: calls 0x00012400 each time the fraction reaches 0x24 units
 */
void func_00012340(s32 speed) {
    s32 fraction;
    fraction = D_000D1230 + speed * 3; /* lit: speed scale; no string or table names it */
    if (fraction >= CLOCK_FRAME_WRAP) {
        fraction -= CLOCK_FRAME_WRAP;
        func_00012400();
    }
    D_000D1230 = fraction;
}
```

Write the current placeholder name on the header's first line. The driver's rename step rewrites every whole-word use of the old name in the unit, comments included, so the header follows the rename.

## Names, evidence and proposals

Where a name comes from (D-21):
1. game evidence: a string the code uses, the role of a data table, the call context (callers, callees, what it reads and writes);
2. OpenApoc's domain vocabulary as plain words (Organisation, Agent, Vehicle, Building).

Never an OpenApoc identifier, comment or code, and nothing from a wiki. Project records such as `config/mechanics.toml` are not an evidence kind: cite the game fact they record, by its address. A placeholder is better than a guess.

Style: lower `snake_case` with a module prefix (`clock_advance_frame`), `ALL_CAPS` macros, `is_`/`has_` for booleans (`docs/coding-style.md#naming`).

The evidence kinds, in header lines and in proposals:

| Kind | Means | The text names |
|---|---|---|
| `string:` | a string the code uses | its address in the EXE, and the words |
| `table:` | the role of a game data table | the table's address in the EXE |
| `call:` | call context | the caller and callee addresses |
| `vocab:` | an OpenApoc domain word | the word only |

Evidence is `<kind>: <text>`, the text 1 to 200 printable ASCII characters on one line.

Locals and parameters you rename in the unit. Each function or global name is one line in `proposals.jsonl`:

```
{"op": "rename", "exe": "ufo2p", "kind": "func", "address": "0x00012340", "name": "clock_advance_frame", "evidence": "call: the only caller, the frame loop at 0x00011000, calls it once per frame"}
{"op": "rename", "exe": "ufo2p", "kind": "data", "address": "0x000D1230", "name": "clock_frame_fraction", "evidence": "call: 0x00012340 adds the speed to it every frame and wraps it at 0x24"}
```

- Exactly the keys `op`, `exe`, `kind`, `address`, `name`, `evidence`, all strings. `exe` is `ufo2p` or `tacp`; `kind` is `func` or `data`; `address` is the row's start as `0x%08X`, upper case.
- The name: ASCII letters, digits and `_`, no leading digit, at most 63 characters; not a C89 or Watcom keyword (`near`, `far`, `inline`, `cdecl`...); not `_` plus a capital or `__`; not placeholder-shaped (`func_` or `D_` plus 8 hex digits, `FUN_`, `sub_`, `DAT_`, `LAB_`, `PTR_`, `UNK_`).
- Refused: a `func` address that starts no game or thunk row; a `data` address inside code; the row's current name; a name another symbols.csv row, a runtime public or a function defined in `src/` already uses.

A struct, enum or constant several units share is a header proposal: the whole text of one bare `include/<name>.h` (lower case, never common.h or watcom_compat.h). It may hold include guards, typedefs, struct, union and enum declarations and object-like `#define NAME <constant>`; no function-like macro, no `#` or `##` operator, no pragma:

```
{"op": "header", "path": "include/clock.h", "text": "#ifndef CLOCK_H\n#define CLOCK_H\n\n#define CLOCK_STEP_UNITS 0x24\n\n#endif\n", "evidence": "call: 0x00012340 and 0x00012400 both wrap the clock fraction at 0x24"}
```

Every name the header declares must be new: one that no symbols.csv row, runtime public or other committed file declares. So a header cannot newly declare a prototype of an existing function (units keep their own externs), and promoting a unit-local `#define` or struct into a header under the same name is refused while the unit still declares it: give the shared one a new name, as above. A rewrite of a header may keep the names it already declares. The driver writes the header after the session, in its own commit; units start to include it in a later session. A constant only this unit uses stays a `#define` in the unit.

Write `proposals.jsonl` with the Write tool, one object per line. To change a proposal, edit its line or add a later line for the same row: the last line for a row wins.

Write the proposals before you run `attempt check`. The check counts an RL01 hit as a `pending rename` only when your own valid proposal covers it, and prints `rename proposal refused: <why>` for one it refuses. That in-session check is narrower than the driver's. Every name is re-checked at landing, after the driver applies the proposals, and can still be refused there.

A callee or global nothing evidences stays a placeholder. List it in notes.md for the owner's allowlist (`config/readlint-allow.csv`, D-30). A reference to a name already on it counts as an allowlisted reference, not a violation.

## Constants without changing bytes

Name a literal with a `#define` that copies its exact spelling and suffix:

```c
#define CLOCK_FRAME_WRAP 0x24
```

In C89 the spelling and the suffix choose the constant's type, and the type picks the compare and extend instructions. Under wcc386 `int` and `long` are both 32 bits, so a literal above INT_MAX is unsigned either way, but not the same type: `0x80000000` is `unsigned int`, `2147483648` is `unsigned long`, and a `u` or `l` suffix changes the type again. A copied token keeps the type by construction, so `0x24` stays `0x24`, never `36`.

Not:
- `static const s32 X = 36;`: RL06 still flags the initializer, and it adds a data object or a load the original does not have;
- `enum { X = 0x24 };`: an enumerator is always `int`, so it re-types every literal that is not a plain `int`.

When nothing evidences a name, waive the literal with `/* lit: <reason> */` on the literal's own line: one whole comment, text after `lit:`. readlint counts the waivers.

Put the `#define`s above the externs, so the header stays the last comment before the definition.

## Readlint

readlint (`reverseapoc readlint`) is the judge: `attempt check` runs it on your view unit, and the driver runs it strictly at landing, on the unit and the headers it includes.

| Rule | Fails on | Reach |
|---|---|---|
| RL01 | a placeholder identifier: `func_`/`D_` plus 8 upper-case hex digits, `FUN_`, `sub_`, `DAT_`, `LAB_`, `PTR_`, `UNK_` | code and directives, not comments, strings or `INCLUDE_ASM` stubs. Every hit counts: an extern, a prototype and each use |
| RL02 | a function definition with no header comment | the last comment after the previous `;`, `}` or directive |
| RL03 | a header comment not in the form above | the same comment |
| RL04 | a struct or union field named like `unk`, `field_0x`, `pad`, `gap`, `filler` or `undefined` | bodies at any depth, and the project headers the unit includes |
| RL05 | a pointer cast over an offset expression, such as `*(s32 *)(p + 0x10)` | a fix needs a struct type and usually a type change: if the check cannot prove it, note it |
| RL06 | an integer literal other than 0 and 1 | exempt: `#define` and enum bodies, masks in bitwise context, shift counts 1 to 31, 2, 4 or 8 in arithmetic or `[ ]`, a line with a waiver. Floating literals are no violation |

A name on `config/readlint-allow.csv` is exempt from RL01 where the unit only references it (a use, an `extern`, a prototype), never where the unit defines it.

## The attempt wrapper

| Command | In a readability session |
|---|---|
| `uv run --frozen reverseapoc attempt check` | the container check of the whole view unit, then readlint on the host: the verdict |
| `uv run --frozen reverseapoc attempt check --sweep` | no use here: a flag diagnostic that never runs readlint, and it costs a check |
| `uv run --frozen reverseapoc attempt asm` | the claimed function's original listing, for evidence |
| `uv run --frozen reverseapoc attempt asm <NAME>` | another function's listing of the same EXE, such as a callee you want to name |
| `uv run --frozen reverseapoc attempt context` | callers, callees, externs and earlier notes: call-context evidence |

Run every `attempt check` with the Bash tool's `timeout` set to 600000, in the foreground, one at a time.

`attempt check` exits `0` when every compiled function is still at objdiff 100% with relocations and bytes ok, every splice is identical and readlint is clean; `1` when either half fails; `2` on a tool error. The output for the unit above, with both proposals written:

```
attempt check 3/25, 88 s (22 left) ufo2p/u_00012340 func_00012340: exit 1 FAILED: see the check and readlint lines (both must pass)
  check: OK (every compiled function objdiff 100% with relocations and bytes ok, every splice identical)
  func_00012340  0x00012340  objdiff 100%  reloc ok  bytes ok
  splice UFO2P.EXE ok
  readlint: 2 violations, 1 waiver, 0 allowlisted references, 4 pending renames
    src/ufo2p/u_00012340.c:6: RL01 func_00012400 is a placeholder name: name it (a D-19 rename)
    src/ufo2p/u_00012340.c:19: RL01 func_00012400 is a placeholder name: name it (a D-19 rename)
    pending rename: src/ufo2p/u_00012340.c:5: D_000D1230 -> clock_frame_fraction (your proposal; the driver applies it after the session and lints again at landing)
    pending rename: src/ufo2p/u_00012340.c:14: func_00012340 -> clock_advance_frame (your proposal; the driver applies it after the session and lints again at landing)
    pending rename: src/ufo2p/u_00012340.c:16: D_000D1230 -> clock_frame_fraction (your proposal; the driver applies it after the session and lints again at landing)
    pending rename: src/ufo2p/u_00012340.c:21: D_000D1230 -> clock_frame_fraction (your proposal; the driver applies it after the session and lints again at landing)
saved <attempt dir>/checks/0003.json (full JSON) and <attempt dir>/checks/0003.c (the C checked)
notes: <notes path>
```

Reading it:
- pending renames are counted per hit, not per name: the extern and two uses of `D_000D1230` are three;
- line numbers come only from this output: quote no line number you have not read here;
- `rename proposal refused: <why>`: fix that proposal line and check again;
- `check: FAILED`: a byte moved. Undo your last edit that was not a comment or a local rename, and check again;
- here the only failures left are `func_00012400`, which nothing evidences: it goes to notes.md for the allowlist.

## When to stop

The session, in order:
1. Read the unit. Run `attempt context`, or `attempt asm <NAME>` for a callee, only when you need evidence.
2. Edit local names, header comments, `#define`s and waivers.
3. Write `proposals.jsonl` for every function and global you can evidence.
4. Run one `attempt check`.
5. Read it as above. Fix a refused proposal or a moved byte, then check again.
6. Write notes.md.
7. Stop.

Stop when the check exits `0`; when the only failures left are placeholders nothing evidences; when the check budget is used; or at about 25 of 30 minutes or 35 of 40 turns.

What lands. The driver applies your proposals first (each rename and header is its own commit), then takes the final text of the view unit, not your best check, and decides in this order:
- GAVE_UP: the unit is unchanged against HEAD. Nothing runs;
- REFUSED: the set of defined or `INCLUDE_ASM` functions changed (checked before anything runs), the C89 lint fails, or the gate finds a changed byte. The unit is restored and the session's work is lost;
- PARTIAL: bytes identical, strict readlint still failing. The view unit is kept under `best/` for a later session;
- LANDED: bytes identical and readlint clean. One commit for the unit.

So end on byte-identical text. If the last run said `check: FAILED` and you cannot fix it, restore the C of the last run that said `check: OK`: Read `<attempt dir>/checks/NNNN.c` and Write it over the view unit. That text was already checked, so it needs no re-check.

notes.md holds, in this order:
1. The outcome: the last check number and its verdict.
2. Each name proposed (row, name, evidence) and any refusal.
3. The placeholders left and why: candidates for `config/readlint-allow.csv`. The owner adds the rows; you never edit it.
4. The literals waived, and why.
5. What the next session should try.

Write notes.md before any optional last step. A clean check is never your claim: the driver checks everything again at landing.
