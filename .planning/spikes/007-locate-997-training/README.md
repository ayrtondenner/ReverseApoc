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

### #997 lead for the owner

**Answer.** Both EXEs pace game time on the BIOS tick and advance the clock in 36ths of a game
second. There is no 36 Hz or 144 Hz timer. Each frame waits until the BIOS tick (INT 1Ah, read
through `int386_`, 1,193,182 / 65,536 = 18.2065 Hz) has moved at least once since the frame
began. It then adds the current speed value to a 16-bit sub-second accumulator. When the
accumulator reaches 36, it subtracts 36 and adds one game second. Seconds roll over at 60 into
minutes, minutes at 60 into hours, hours at 24 into the calendar. One call advances at most one
game second, so a frame never adds more than one second.

- **Cityscape (UFO2P) speeds** are 1, 2, 4 and 6 units per frame. The speed labels map to them as
  Slow = 1, Normal = 2, Double = 4 and Quadruple = 6. Quadruple is therefore 3 times Normal, not
  4 times.
- At most 18.2065 frames per real second, the clock runs at most at 0.506 / 1.011 / 2.023 / 3.034
  game seconds per real second for Slow / Normal / Double / Quadruple. These are upper bounds: a
  frame that takes longer than one tick runs slower.
- At Normal speed a game second takes 18 frames, about 0.989 real seconds, so Normal is about real
  time.
- 0 is pause. A sixth setter writes 600 (0x258), which has no label among the four, and sets the
  flag `D_000D5064`. While that flag is set, each frame takes a separate path, `func_00011520`.
  That path does not use the 36-unit accumulator: it clears the seconds and the accumulator and
  moves the minutes up to the next multiple of 5. So this mode advances in 5-minute steps, a
  time skip rather than a speed. This was read by hand (see Investigation Trail), not checked by
  a script.
- **Battlescape (TACP)** uses the same rule in its own copies. The speed values seen there are 0,
  1, 2 and 4. The start value is 4 when the byte `D_000E6D66` is set and 0 otherwise, and 1
  when the byte `D_0027A805` is set. TACP's labels are not located yet (q4, plan 07-08).
- **PR #1688.** Both halves of its claim are confirmed by our bytes in both EXEs:
  - the main loop busy-waits on the BIOS clock (18.2065 Hz);
  - the loop adds a speed value into a sub-second accumulator, and 36 units make one game second.
  - Its "nothing runs at 36 Hz" also holds: the only PIT programming is in the sound library (q1).

**Addresses** (installed build, functions.csv names):

| | UFO2P (cityscape) | TACP (battlescape) |
|---|---|---|
| frame loop with the tick wait | `func_00010940`: outer loop `0x000109A0..0x00011392`, busy-wait `0x00011127..0x00011174`. It reads INT 1Ah itself through `int386_`, via a register set once. Reached as `main_` -> `func_000105D0` -> `func_00010940` | frame step `func_000116B0`, busy-wait `0x00011909..0x00011959`. Called from the battle loop `func_00010EE0` (`0x00010F40..0x0001135C`, called by `main_`) and 8 other loop rows |
| clock advance (36-unit accumulator) | `func_0004AB30`, compare with 36 at `0x0004AB59`, called only from `func_00010940` | `func_0003D160`, compare with 36 at `0x0003D184`, called from `func_000116B0` (when the speed is nonzero and the byte `D_0027A0EA` is clear) and `func_000B6E50` |
| speed variable | `D_000D4D58` (dword; the clock reads its low word) | `D_000E6C24` |
| sub-second accumulator (16-bit) | `D_000D4D6E` | `D_000E6C36` |
| second / minute / hour words | `D_000D4D6C` / `D_000D4D6A` / `D_000D4D68` | `D_000E6C34` / `D_000E6C32` / `D_000E6C30` |
| speed setters | `func_00050920` (0), `func_00050970` (1), `func_000509C0` (2), `func_00050A20` (4), `func_00050A80` (6), `func_00050AE0` (600) | stores in `func_00010EE0` and 7 more rows (q2 `speed-values`) |
| speed labels | `get_text` `func_00063800` section 38, indexes 43-46. Call sites `0x000523C1` (Slow), `0x00052439` (Normal), `0x000524B1` (Double), `0x0005252C` (Quadruple), all in `func_00052150`, each under a compare of the speed with 1 / 2 / 4 / 6 | not located (q4) |
| speed-indexed tables | three 6-slot jump tables in `func_00010940` (`D_000108EC`, `D_00010904`, `D_0001091C`) indexed by speed - 1. Active slots: speeds 1, 2, 4, 6; slots 3 and 5 fall to the default | - |
| BIOS-tick readers (q1) | `func_00011430` (28 callers), `func_00010940` | `func_00011500` (35 callers), `func_000116B0` (10 callers) |

**Evidence.** q1 (`ALL PASS`) and q2 (`ALL PASS`) below. Every claim is re-derived from the raw LE
bytes and fixups (rawle.py), with the instructions decoded by the pinned capstone. q2's planted
run (expected modulus 144) fails in both EXEs.

Research's candidates are refuted (07-R1 A2), and q2 checks this:
- `func_00022EF0` and the wait in `func_00026B80` do not reach the clock; `func_00026B80` is a
  dialog that waits one tick per frame;
- the table at `0x001303E0` is used by `func_000ACDC0` and `func_000BB500`, not by the loop or
  the clock.

**Status: matched code backs it: no.** None of these functions is in `config/ufo2p/status.csv` or
`config/tacp/status.csv`. The rule is read from the bytes by the scripts here, not from
byte-matched C. Nothing has been posted anywhere: the owner carries it to OpenApoc.

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

`uv run python .planning/spikes/007-locate-997-training/q2_tickrule.py` (exit 0), kept in the
gitignored `build/spike007-q2.out`:

```
PASS UFO2P.EXE loop-located-ufo2p loop rows 2 [0x000105D0:0x00010603..0x000108CE 0x00010940:0x000109A0..0x00011392] clock [0x0004AB30] accumulator 0x000D4D6E speed 0x000D4D58 expected loop 0x00010940
PASS UFO2P.EXE accumulator-modulus-is-36 modulus 36 at 0x0004AB59 expected 36 (PR #1688)
PASS UFO2P.EXE one-second-per-frame `sub _, 36` count 1 in 0x0004AB30 (one per call: at most one game second per frame)
PASS UFO2P.EXE paces-on-bios-tick rows calling the clock [0x00010940]; busy-wait on int386 0x1A [0x00010940:0x00011127..0x00011174]
PASS UFO2P.EXE speed-values stored [0, 1, 2, 4, 6, 600] compared [0, 1, 2, 4, 6, 60, 600] at 0x000D4D58
PASS UFO2P.EXE get-text-sections 50 of 50 section pointers at 0x000F3794
PASS UFO2P.EXE speed-table-one-entry-per-label labels 4: slow 38/43 sites [0x000523C1] speed [1]; normal 38/44 sites [0x00052439] speed [2]; double 38/45 sites [0x000524B1] speed [4]; quadruple 38/46 sites [0x0005252C] speed [6]; tables [('0x000108EC', 6, [1, 2, 4, 6]), ('0x00010904', 6, [1, 2, 4, 6]), ('0x0001091C', 6, [1, 2, 4, 6])]
PASS UFO2P.EXE research-candidates-refuted 0x00022EF0 reaches clock False; 0x00026B80 reaches clock False; table 0x001303E0 users [0x000ACDC0 0x000BB500] in loop/clock False
PASS TACP.EXE loop-located-tacp loop rows 9 [0x00010EE0:0x00010F40..0x0001135C 0x000161B0:0x000161CC..0x000167F2 0x00040B40:0x00040B4A..0x00040B5F 0x00042F90:0x00042FB4..0x000433D4 0x00050620:0x0005086E..0x00050CB6 0x000760A0:0x000761D1..0x000763DA 0x00077DF0:0x00077E42..0x00077F33 0x000AE060:0x000AE0C0..0x000AE2F9 0x000B70D0:0x000B7A25..0x000B85BD] clock [0x0003D160] accumulator 0x000E6C36 speed 0x000E6C24 expected loop None (report)
PASS TACP.EXE accumulator-modulus-is-36 modulus 36 at 0x0003D184 expected 36 (PR #1688)
PASS TACP.EXE one-second-per-frame `sub _, 36` count 1 in 0x0003D160 (one per call: at most one game second per frame)
PASS TACP.EXE tacp-paces-on-same-bios-tick rows calling the clock [0x000116B0 0x000B6E50]; busy-wait on int386 0x1A [0x000116B0:0x00011909..0x00011959]
PASS TACP.EXE speed-values stored [0, 1, 2, 4] compared [0, 1, 2, 4] at 0x000E6C24
ALL PASS
```

- **Which half of PR #1688 our bytes confirm:** both.
  - The BIOS-tick busy-wait: `paces-on-bios-tick` in both EXEs, with q1's readers.
  - The 36-unit sub-second accumulator fed by the speed value: `accumulator-modulus-is-36` in both
    EXEs.
- The located addresses are pinned in q2's `EXPECTED` as "located by this spike". For TACP the
  plan kept `EXPECTED` at `None` (the battle loop was unknown), so the claim reports what it
  finds.
- The UFO2P loop rows include `func_000105D0`, whose loop calls `func_00010940`.
- In TACP, 9 loop rows reach the clock through the frame step `func_000116B0`. The battle loop
  called by `main_` is `func_00010EE0`; the other 8 are modal loops that keep the clock running.
- The extra compare with 60 on the UFO2P speed is not a speed setting, because no setter stores
  60. It is in `func_00011520`, the 5-minute time-skip path of the 600 setting.
- The speed values are rate constants, like the modulus. They are the #997 answer itself, so q2
  prints them.

### q3 training rule

`uv run python .planning/spikes/007-locate-997-training/q3_training.py` (exit 0), kept in the
gitignored `build/spike007-q3.out`:

```
PASS UFO2P.EXE unitr-reader keyword unitr.dat strings 1 at [0x000D4170] refs from [0x000B2A90] expected 0x000B2A90; call 0x00013E30 buffer 0x00241D98
PASS UFO2P.EXE stat-update rows copying >= 8 fields from 0x00241D98 [0x000B2E80] (17 buffer fields) into [0x00144918]; reached 96 rows
PASS UFO2P.EXE android-label label 0x000F12B6 keywords android+training True get_text 37/404 sites [0x0004F41A] guard compares [0x0004F3F5]
PASS UFO2P.EXE android-string keyword android exact strings [0x000D2C50] refs from [0x0009B840]
PASS UFO2P.EXE learning-ai-files keyword strings 3 refs from [0x000A5F40 0x000A6040 0x000A61E0]; reached from 0x000B2A90 [0x000A6040] (none without 0x000A49D0: True)
PASS TACP.EXE unitr-writer keyword unitr.dat strings 1 at [0x000E0CFC] refs from [0x000156A0] expected 0x000156A0; call 0x00013FF0 buffer 0x002B9310 bytes 0x2238
PASS TACP.EXE record-layout unit array 0x00109ED0 step 0x49c, buffer step 0x92, bytes 0x2238 = 60 x 0x92
PASS TACP.EXE handoff-fields-agree writer fills 30 buffer fields from the unit array; the UFO2P stat update (UFO2P.EXE) copies 17, all filled True; 17 unit fields reach agents
PASS TACP.EXE accrual-sites 2 rows [0x00060080 0x000B26F0] (serialised unit fields 30, applied 17; heuristic, data-field)
PASS TACP.EXE learning-ai-files keyword strings 5 refs from [0x00014AF0 0x00078FE0 0x00079050 0x000B20B0]; reached from 0x000156A0 []
ALL PASS
```

What the bytes show about #263-1:

- **The hand-off is a record copy.** TACP's `func_000156A0` fills a buffer of 60 records of
  0x92 bytes, one per battle unit (unit array `D_00109ED0`, 0x49C bytes per unit), and writes it
  to `scenario/unitr.dat`. UFO2P's `func_000B2A90` loads the file into `D_00241D98`, and its
  callee `func_000B2E80` copies 17 of those fields into the agent records at `D_00144918`.
- **UFO2P applies the stats; it does not compute them.** Each of the 17 fields UFO2P copies is
  one the TACP writer filled from a unit field. So the stats an agent brings back are battle-unit
  fields TACP holds at the end of the battle.
- **The improvement rule is on the TACP side**, where those 17 unit fields change during the
  battle. q3 finds only two candidate rows for that accrual: `func_00060080` writes two of the
  fields through the unit-array base, and `func_000B26F0` adds to one through a register base. A
  unit pointer passed in from a caller is invisible to this heuristic, so the TACP accrual is
  **not located**. The call-graph route of D-03 (q6, plan 07-08) or reading is needed.
- **Androids.** The cityscape training screen `func_0004F100` shows the label at `0x000F12B6`
  (get_text 37/404, keywords `android` + `training`) only on the branch guarded by a compare of
  an agent-record field at `0x0004F3F5`. That is the android test of base training (#263-13).
  q3 does not show whether the battle side skips androids. The plain `android` string is
  referenced only by `func_0009B840`.
- **The Learning AI files stay out of #263-1** (D-26). Their rows are research's rows. The TACP
  writer reaches none of them. The UFO2P reader reaches `func_000A6040` only because it first
  reloads the savegame through `func_000A49D0`; without that loader it reaches none.

**#263-1 entry candidates** (plan 07-22 copies these into `config/mechanics.toml`):

| EXE | Address | Evidence kind | Why |
|---|---|---|---|
| tacp | `0x000156A0` | file | writes `scenario/unitr.dat` from the unit array (q3 `unitr-writer`, `record-layout`) |
| tacp | `0x00060080` | data-field | writes serialised unit fields through the unit-array base (heuristic; q3 `accrual-sites`) |
| tacp | `0x000B26F0` | data-field | adds to a unit field the agents receive (heuristic; q3 `accrual-sites`) |
| ufo2p | `0x000B2A90` | file | reads `scenario/unitr.dat` into `D_00241D98` (q3 `unitr-reader`) |
| ufo2p | `0x000B2E80` | data-field | copies 17 result fields into the agent records `D_00144918`; reached from the reader (q3 `stat-update`) |
| ufo2p | `0x0004F100` | string | android branch of base training: get_text 37/404 site `0x0004F41A`, guard `0x0004F3F5` (q3 `android-label`) |
| ufo2p | `0x0009B840` | string | the only reference to the plain `android` string (q3 `android-string`) |

The TACP accrual is a known gap: the call-graph closure from `0x000156A0`'s callers into the
battle code is the route to close it.

## Planted failures

| Run | What is planted | Result | Exit |
|---|---|---|---|
| `q1 --plant` | UFO2P expected reader `0x00011430` -> `0x00011440` | `FAIL UFO2P.EXE int1a-readers immediate [0x00011430] expected [0x00011440]`, `1 FAILED` | 1 |
| `q1 --mutant` | every `mov reg, 0x1a` immediate in game rows zeroed in an in-memory copy of the flat image | UFO2P `int1a-readers immediate []` and `int1a-pinned-readers []` FAIL; TACP `int1a-readers immediate []` FAIL; `3 FAILED` (the readers are reported missing) | 1 |
| `q2 --plant` | expected modulus 36 -> 144 (OpenApoc's assumed ticks per second) | `FAIL UFO2P.EXE accumulator-modulus-is-36 modulus 36 at 0x0004AB59 expected 144`, the same for TACP at `0x0003D184`, `2 FAILED` | 1 |
| `q3 --plant` | TACP expected writer `0x000156A0` -> `0x000156B0` | `unitr-writer`, `record-layout`, `handoff-fields-agree`, `accrual-sites` and TACP `learning-ai-files` FAIL; `5 FAILED` | 1 |

## Investigation Trail

- q1 started from research's capstone scan. A first run missed the pinned reader: the tracker
  treated `movsx`/`movzx` as string instructions (prefix match on `movs`), so every register
  looked rewritten. Matching the string mnemonics exactly found UFO2P `func_00010940`.
- The constant tracker is spike-grade: it follows `mov`/`xor`/`lea` constants along one row,
  forgets them at jump targets, esp changes and calls (eax/edx), and keeps a register the row
  writes once by an immediate (besides prologue/epilogue push/pop). Vector numbers passed in
  `union REGS` are read from the esp slots the block stores before `int386_`.
- q2 first followed research's candidate, `func_00022EF0` -> `func_00026B80`. `func_00026B80`
  waits one BIOS tick per frame, but it is a dialog: it never reaches a clock. Searching instead
  for a function holding the 36 / 60 / 60 / 24 roll-over chain found `func_0004AB30` (UFO2P) and
  `func_0003D160` (TACP). Their only callers are the frame loop `func_00010940` and the frame step
  `func_000116B0`, the pinned UFO2P reader and a TACP reader. q2 then had to derive this from the
  readers without knowing the answer. It goes reader -> loops over the reader call -> functions
  called in the loop, two deep -> an `add`/`cmp`/`sub` accumulator on two globals.
- Read by hand in the private disassembly, not asserted by a script:
  - The six UFO2P speed setters store their constant and set the no-wait frame counter
    `D_000D4D5C` (600 for the 600 setter). The frame loop decrements that counter and skips the
    tick read and the wait while it is nonzero.
  - The 600 setter (`func_00050AE0`) also sets `D_000D5064`. With that flag set, the frame loop
    calls `func_00011520` instead of its normal update. That function rounds the minutes up to
    the next multiple of 5, clears the seconds and the accumulator, and rolls over hours and days
    itself. It clears the flag again once the speed is below 60, which is the compare with 60 in
    q2's `speed-values`.
  - In the three jump tables, speed 1 runs its subsystem on frames where the accumulator is even.
    Speeds 2, 4 and 6 run it 1, 2 and 3 times per frame (`func_0007FA60`, `func_00080030`,
    `func_00032DD0`), so subsystem steps scale as speed / 2.
  - TACP's start value comes from the bytes `D_000E6D66` (4, else 0) and `D_0027A805` (then 1).
  - TACP's `get_text` (`func_0005B360`, table `0x00292D18`) has fixups on only 19 of its first 50
    slots, so its labels are left to q4.
- q3 first used an accrual heuristic that also counted read-modify-writes on `[esp + k]` stack
  locals. That gave 10 TACP rows; excluding esp-based operands leaves 2. Two more details were
  read by hand: the agent records are 0xCE bytes apart, and `func_000B3360` maps a result record
  to its agent.
- The android label is index 404 of section 37, so a walk capped at 400 strings per section
  misses it. q3 walks the section until it reaches the address.
