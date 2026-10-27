---
spike: 007
idea: mechanics-first-decompilation
name: locate-997-training
type: standard
validates: "Given UFO2P.EXE and TACP.EXE, their LE fixups and the committed functions.csv, when the BIOS-tick readers, the UI strings through get_text and the data-table and hand-off-file xrefs are followed, then the #997 time-advance code and its rate constants are located in both EXEs, the #263-1 battle-to-agent stat rule (incl. androids) is located, and the same method gives an entry function for most remaining D-01 items"
verdict: pending
related: [003]
tags: [mechanics, 997, training, get_text, bios-tick, d-01, d-03, d-26]
---

# Spike 007: locate the #997 tick rule and the #263-1 training rule

This is the Phase 7 roadmap spike (D-03, refined by D-26). Part 1 (plan 07-02) holds q1-q3: the
time base, the tick rule and the training rule. Part 2 (plan 07-08) adds the string, table and
call-graph questions (q4-q6), the verdict and the owner report. The verdict stays `pending` until
then.

## What This Validates

- **q1 time base.** What paces game time: the BIOS tick read through `int386_(0x1A)`, not the PIT
  or INT 8 code, which belongs to the sound library.
- **q2 tick rule.** From the tick readers' loops to the time-advance code: the loop, the speed
  variable, the sub-second accumulator and its modulus (OpenApoc PR #1688 says 36 units make one
  game second), and the speed table against the speed labels.
- **q3 training rule.** The `scenario/unitr.dat` hand-off (TACP writes, UFO2P reads), the UFO2P
  stat update reached from the reader, the android branch and the TACP accrual sites.
  EXPERIEN/BRAIN/WEAPEXP.DAT are the Learning AI files of #265, not #263-1 (D-26).

Stated deviation (spike CONVENTIONS allow shared inputs): instructions are decoded through
`reverseapoc.x86`, the pinned capstone, because a raw opcode scan cannot find instruction
boundaries. The bytes and fixups come from the independent `001-le-pages-and-fixups/rawle.py`
(cross-checked against `le.py` by q1's `raw-image` claim); the function rows come from the
committed `functions.csv` through `reverseapoc.check.load_exe`. Caller counts are rebuilt by the
scripts and only cross-checked against `reverseapoc.contextpack.CallIndex`.

OpenApoc sources (PR #1688's description, the extractor headers) are used as locators only. Nothing
from them is committed, and no finding is posted anywhere: findings go to the owner (D-03).

## How to Run

From the main checkout (orig/ is gitignored and absent from worktrees), host only:

```
uv run python .planning/spikes/007-locate-997-training/q1_timebase.py [--plant] [--mutant]
uv run python .planning/spikes/007-locate-997-training/q2_tickrule.py [--plant]
uv run python .planning/spikes/007-locate-997-training/q3_training.py [--plant]
```

Each prints one `PASS/FAIL <file> <claim> <detail>` line per claim and `ALL PASS` or `N FAILED`,
and exits 1 on any FAIL. Output is addresses, counts, booleans, keyword labels and protocol or
rate constants only. q2 and q3 import q1's shared reader (`Image`, the constant tracker).

## Results

### q1 time base

`uv run python .planning/spikes/007-locate-997-training/q1_timebase.py` (exit 0), kept in the
gitignored `build/spike007-q1.out`:

```
PASS UFO2P.EXE raw-image objects 2 bytes-equal True fixups 28197 equal-to-le.py True
PASS UFO2P.EXE pit-int8-sites pit 8 int8 3 all in 0x000C8E41..0x000C90F3 True rows [0x000C8EBD 0x000C8F03 0x000C901D]
PASS UFO2P.EXE unresolved-vectors 6 sites in rows [0x000B7280 0x000B73D0]
PASS UFO2P.EXE int1a-readers immediate [0x00011430] expected [0x00011430]
PASS UFO2P.EXE int1a-pinned-readers via a register set once [0x00010940] expected [0x00010940]
PASS UFO2P.EXE callers-0x00011430 own scan 28 CallIndex 28 expected 28
PASS UFO2P.EXE no-46c-read absolute [0x46c] reads 0
PASS TACP.EXE raw-image objects 2 bytes-equal True fixups 24438 equal-to-le.py True
PASS TACP.EXE pit-int8-sites pit 8 int8 3 all in 0x000CC151..0x000CC402 True rows [0x000CC1CD 0x000CC213 0x000CC32D]
PASS TACP.EXE unresolved-vectors 6 sites in rows [0x000A5750 0x000A58A0]
PASS TACP.EXE int1a-readers immediate [0x00011500 0x000116B0] expected [0x00011500 0x000116B0]
PASS TACP.EXE int1a-pinned-readers via a register set once [] expected []
PASS TACP.EXE callers-0x00011500 own scan 35 CallIndex 35 expected 35
PASS TACP.EXE callers-0x000116B0 own scan 10 CallIndex 10 expected 10
PASS TACP.EXE no-46c-read absolute [0x46c] reads 0
ALL PASS
```

- The PIT writes (ports 0x43/0x40) and the INT 8 vector get/set sites with a constant vector
  (DPMI 0204h/0205h with BL=8, DOS 3508h/2508h) are only in the sound-library rows, as research
  found: UFO2P `0x000C8EBD`, `0x000C8F03`, `0x000C901D`; TACP `0x000CC1CD`, `0x000CC213`,
  `0x000CC32D`.
- Vector get/set sites whose vector is not a constant (6 per EXE) are only in the keyboard-handler
  installers (UFO2P `0x000B7280`, `0x000B73D0`; TACP `0x000A5750`, `0x000A58A0`), whose vector is
  computed from the DPMI PIC base at run time.
- The BIOS-tick readers match research, with **one addition**: UFO2P `func_00010940` also calls
  `int386_` with 0x1A, passed through a register the row sets once (not an immediate in the call's
  block). It is the cityscape frame loop (q2). Research's caller count of 28 is for
  `func_00011430` only.
- No game or thunk row reads the BIOS tick word at linear 0x46C directly.

### q2 tick rule

Pending (plan 07-02 Task 2).

### q3 training rule

Pending (plan 07-02 Task 3).

## Planted failures

| Run | What is planted | Result | Exit |
|---|---|---|---|
| `q1 --plant` | UFO2P expected reader `0x00011430` -> `0x00011440` | `FAIL UFO2P.EXE int1a-readers immediate [0x00011430] expected [0x00011440]`, `1 FAILED` | 1 |
| `q1 --mutant` | every `mov reg, 0x1a` immediate in game rows zeroed in an in-memory copy of the flat image | UFO2P `int1a-readers immediate []` and `int1a-pinned-readers []` FAIL; TACP `int1a-readers immediate []` FAIL; `3 FAILED` (the readers are reported missing) | 1 |

## Investigation Trail

- q1 started from research's capstone scan. A first run missed the pinned reader: the tracker
  treated `movsx`/`movzx` as string instructions (prefix match on `movs`), so every register
  looked rewritten. Matching the string mnemonics exactly found UFO2P `func_00010940`.
- The constant tracker is spike-grade: it follows `mov`/`xor`/`lea` constants along one row,
  forgets them at jump targets, esp changes and calls (eax/edx), and keeps a register the row
  writes once by an immediate (besides prologue/epilogue push/pop). Vector numbers passed in
  `union REGS` are read from the esp slots the block stores before `int386_`.
