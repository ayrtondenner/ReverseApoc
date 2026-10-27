---
spike: 007
idea: mechanics-first-decompilation
name: locate-997-training
type: standard
validates: "Given UFO2P.EXE and TACP.EXE, their LE fixups and the committed functions.csv, when the BIOS-tick readers, the UI strings through get_text and the data-table and hand-off-file xrefs are followed, then the #997 time-advance code and its rate constants are located in both EXEs, the #263-1 battle-to-agent stat rule (incl. androids) is located, and the same method gives an entry function for most remaining D-01 items"
verdict: VALIDATED
related: [003]
tags: [mechanics, 997, training, get_text, bios-tick, d-01, d-03, d-26]
---

# Spike 007: locate the #997 tick rule and the #263-1 training rule

This is the Phase 7 roadmap spike (D-03, refined by D-26). Part 1 (plan 07-02) holds q1-q3: the
time base, the tick rule and the training rule. Part 2 (plan 07-08) adds the string, table and
call-graph questions (q4-q6), the verdict and the owner report. Verdict: **VALIDATED** by the
D-03 formula, with the caveats in "Verdict".

## What This Validates

- **q1 time base.** What paces game time: the BIOS tick read through `int386_(0x1A)`, not the PIT
  or INT 8 code, which belongs to the sound library.
- **q2 tick rule.** From the tick readers' loops to the time-advance code: the loop, the speed
  variable, the sub-second accumulator and its modulus (OpenApoc PR #1688 says 36 units make one
  game second), and the speed table against the speed labels.
- **q3 training rule.** The `scenario/unitr.dat` hand-off (TACP writes, UFO2P reads), the UFO2P
  stat update reached from the reader, the android branch and the TACP accrual sites.
  EXPERIEN/BRAIN/WEAPEXP.DAT are the Learning AI files of #265, not #263-1 (D-26).
- **q4 strings.** The `get_text` section tables, how often a call site's (section, index) can be
  recovered, the TACP speed labels, and how many of 12 sampled Tier 2-4 items get an entry row
  by string or file name.
- **q5 tables.** Whether the CD build's data, where OpenApoc's extractor offsets point, sits at
  the same linear addresses in the installed build (VA identity).
- **q6 call graph.** Direct edges rebuilt independently against `CallIndex`, and research Q1's
  reachability from `main_` reproduced.

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
uv run python .planning/spikes/007-locate-997-training/q1_timebase.py [--plant] [--mutant] [--plant-chain]
uv run python .planning/spikes/007-locate-997-training/q2_tickrule.py [--plant] [--plant-guards]
uv run python .planning/spikes/007-locate-997-training/q3_training.py [--plant]
uv run python .planning/spikes/007-locate-997-training/q4_strings.py [--plant]
uv run python .planning/spikes/007-locate-997-training/q5_tables.py [--plant] [--headers DIR]
uv run python .planning/spikes/007-locate-997-training/q6_callgraph.py [--plant]
```

Each prints one `PASS/FAIL <file> <claim> <detail>` line per claim and `ALL PASS` or `N FAILED`,
and exits 1 on any FAIL. Output is addresses, counts, booleans, keyword labels and protocol or
rate constants only. q2-q6 import q1's shared reader (`Image`, the constant tracker). q5 also
reads the Steam `cd.iso` in memory and, if present, OpenApoc's extractor headers from the
gitignored `build/openapoc-extractors/` (text only, never committed).

## Results

### #997 lead for the owner

**How to read this lead.** Each statement carries its evidence class:
- **[script]** a spike script checks it (q1/q2/q3 below, each `ALL PASS`, each planted run fails);
- **[hand]** read by hand in the private disassembly; no script asserts it;
- **[assumption]** standard PC/BIOS behaviour or research, not checked in our bytes.

**Answer.** Both EXEs pace game time on the BIOS tick and advance the clock in 36ths of a game
second.
- The frame loop reads the BIOS tick through `int386_(0x1A)` and busy-waits until it has moved at
  least once since the frame began [script: q1 readers, q2 `paces-on-bios-tick`].
- Then it adds the current speed value to a 16-bit sub-second accumulator. At 36 it subtracts 36
  and adds one game second [script: q2 `accumulator-modulus-is-36`, both EXEs]. At most one game
  second per frame [script: q2 `one-second-per-frame`]. Seconds roll over at 60, minutes at 60
  and hours at 24 into the calendar [hand].
- **The BIOS tick stays at 18.2 Hz while the sound timer owns INT 8.** The sound library
  reprograms the PIT for its fastest event (a 30 Hz event, per research) [assumption: research].
  But it keeps the BIOS clock: it saves the old INT 8 vector, and an event callback far-returns
  into it, registered by the timer init [script: q1 `bios-chain-cadence`]. That event's
  increment is 0x123333 (18.2 in 16.16) divided by the PIT rate [script: the dividend; hand: the
  divide by the PIT rate]. A callback the timer init installs adds the increments to the event
  accumulators [script]; that the INT 8 handler calls it on every interrupt, and that the event
  fires when the accumulator passes 1.0, is [hand].
- So the old handler runs about 18.2 times a second whatever the PIT rate: 0x123333 / 0x10000 =
  18.2000 Hz, or 18.2001 Hz with a 30 Hz event once integer rounding is counted. At the library's
  DOS rate (divisor 0xFFFF) it runs on every interrupt: 1,193,182 / 65,535 = 18.2068 Hz [hand].
- That INT 1Ah returns the tick count this old handler keeps is standard BIOS behaviour under
  DOS/4GW [assumption].
- There is no 36 Hz or 144 Hz game timer [derived: the only PIT programming is in the sound
  library (script: q1 `pit-int8-sites`), and the 36-unit clock is called only from the frame
  rows that wait on the BIOS tick (script: q2 `paces-on-bios-tick`, rows calling the clock)].
- **Exception to "every frame waits".** The UFO2P frame skips the BIOS read and the wait while
  the no-wait counter `D_000D4D5C` is nonzero after the frame's own decrement, or while the byte
  `D_00183BAC` is set [script: q2 `wait-skip-guards` finds both tests before the wait; both
  globals pinned since plan 07-08].
  - All six speed setters write the counter, and the only constants any row stores to it are
    0, 1 and 600 [script].
  - A value of 1 is used up by the decrement before the test, so steady play at speeds 1/2/4/6
    waits every frame [hand].
  - The 600 setting stores 600, so frames skip the wait while it counts down [hand]. One more
    row stores a computed value (`func_0004B1B0`) [hand: not resolved].
  - TACP's frame step skips its wait when a flag computed from `D_000E6D64`, `D_001B7BAC` and
    `D_0027A0EB` says so [script: the three globals, pinned since plan 07-08; hand: the
    condition].

**Cityscape (UFO2P) speeds.**
- The speed values are 1, 2, 4 and 6 units per frame [script: q2 `speed-values`]. The labels
  are Slow = 1, Normal = 2, Double = 4 and Quadruple = 6 [script: q2
  `speed-table-one-entry-per-label`]. So Quadruple is 3 times Normal, not 4.
- **Steady-state rates** (every frame waits one tick, and no frame overruns it): the clock runs
  at about 0.506 / 1.011 / 2.022 / 3.033 game seconds per real second for Slow / Normal /
  Double / Quadruple. That is speed x 18.2 / 36 [derived from script facts + the
  18.2 Hz chain above]. A frame that takes longer than one tick runs slower, so these are upper
  bounds for steady state only. While the no-wait counter is above 1, frames are not
  rate-limited by the tick at all.
- At Normal a game second takes 18 frames, about 0.989 real seconds, so Normal is about real
  time.
- 0 is pause [script: the setter stores 0]. The sixth setter writes 600 (0x258) and sets
  `D_000D5064`. With that flag set, each frame takes a separate path, `func_00011520`, which does
  not use the accumulator: it clears the seconds and the accumulator and moves the minutes up to
  the next multiple of 5. So 600 is a 5-minute time skip, not a speed [hand].

**Battlescape (TACP).**
- Same rule in its own functions [script]. Speed values 0, 1, 2 and 4 [script].
- The start value is 4 when the byte `D_000E6D66` is set and 0 otherwise, and 1 when the byte
  `D_0027A805` is set [hand].
- The labels are Pause = 0, Slow = 1, Normal = 2 and Double = 4 [script: q4 `speed-labels`].
  The battlescape has no Quadruple label. So TACP's Double is 2 times Normal, and Slow is half
  of Normal.

**PR #1688.** Our bytes confirm both halves of its claim in both EXEs:
- the main loop busy-waits on the BIOS clock [script], which stays at 18.2 Hz under the sound
  timer [script + hand + assumption, as above];
- the loop adds a speed value into a sub-second accumulator, and 36 units make one game second
  [script].

**Addresses** (installed build, functions.csv names):

| | UFO2P (cityscape) | TACP (battlescape) |
|---|---|---|
| frame loop with the tick wait | `func_00010940`: outer loop `0x000109A0..0x00011392`, busy-wait `0x00011127..0x00011174`. It reads INT 1Ah itself through `int386_`, via a register set once. Reached as `main_` -> `func_000105D0` -> `func_00010940` | frame step `func_000116B0`, busy-wait `0x00011909..0x00011959`. Called from the battle loop `func_00010EE0` (`0x00010F40..0x0001135C`, called by `main_`) and 8 other loop rows |
| clock advance (36-unit accumulator) | `func_0004AB30`, compare with 36 at `0x0004AB59`, called only from `func_00010940` | `func_0003D160`, compare with 36 at `0x0003D184`, called from `func_000116B0` (when the speed is nonzero and the byte `D_0027A0EA` is clear) and `func_000B6E50` |
| speed variable | `D_000D4D58` (dword; the clock reads its low word) | `D_000E6C24` |
| sub-second accumulator (16-bit) | `D_000D4D6E` | `D_000E6C36` |
| second / minute / hour words | `D_000D4D6C` / `D_000D4D6A` / `D_000D4D68` | `D_000E6C34` / `D_000E6C32` / `D_000E6C30` |
| speed setters | `func_00050920` (0), `func_00050970` (1), `func_000509C0` (2), `func_00050A20` (4), `func_00050A80` (6), `func_00050AE0` (600) | stores in `func_00010EE0` and 7 more rows (q2 `speed-values`) |
| speed labels | `get_text` `func_00063800` section 38, indexes 43-46. Call sites `0x000523C1` (Slow), `0x00052439` (Normal), `0x000524B1` (Double), `0x0005252C` (Quadruple), all in `func_00052150`, each under a compare of the speed with 1 / 2 / 4 / 6 | `get_text` `func_0005B360` section 36, indexes 0-3. Call sites `0x000A751A` (Pause), `0x000A758C` (Slow), `0x000A75FE` (Normal), `0x000A7670` (Double), all in `func_000A7490`, each under a compare of the speed with 0 / 1 / 2 / 4 (q4 `speed-labels`) |
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
PASS UFO2P.EXE bios-chain-cadence saved old INT 8 vector [0x0013BD34 0x0013BD38]; chain rows [0x000C9099] via event callback [0x000C3692] registered by [0x000C2F1F]; increment dividend in [0x000C3035 0x000C33BA]: 0x123333/0x10000 = 18.2000 Hz (expected 0x123333); increments [0x0013D80B] added in [0x000C35C8], a callback the same writer installs: True
PASS TACP.EXE raw-image objects 2 bytes-equal True fixups 24438 equal-to-le.py True
PASS TACP.EXE pit-int8-sites pit 8 int8 3 all in 0x000CC151..0x000CC402 True rows [0x000CC1CD 0x000CC213 0x000CC32D]
PASS TACP.EXE unresolved-vectors 6 sites in rows [0x000A5750 0x000A58A0]
PASS TACP.EXE int1a-readers immediate [0x00011500 0x000116B0] expected [0x00011500 0x000116B0]
PASS TACP.EXE int1a-pinned-readers via a register set once [] expected []
PASS TACP.EXE callers-0x00011500 own scan 35 CallIndex 35 expected 35
PASS TACP.EXE callers-0x000116B0 own scan 10 CallIndex 10 expected 10
PASS TACP.EXE no-46c-read absolute [0x46c] reads 0
PASS TACP.EXE bios-chain-cadence saved old INT 8 vector [0x002B4050 0x002B4054]; chain rows [0x000CC3A9] via event callback [0x000C6386] registered by [0x000C5C13]; increment dividend in [0x000C5D29 0x000C60AE]: 0x123333/0x10000 = 18.2000 Hz (expected 0x123333); increments [0x002B5B27] added in [0x000C62BC], a callback the same writer installs: True
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
- `bios-chain-cadence` (fix round 1). The sound library keeps the BIOS clock running while it
  owns INT 8.
  - Its install saves the old vector (UFO2P `D_0013BD34`/`D_0013BD38`).
  - `func_000C9099` far-returns into that saved vector. Only the event callback `func_000C3692`
    calls it, and the timer init `func_000C2F1F` registers that callback.
  - The rate rows `func_000C3035` and `func_000C33BA` compute that event's increment from the
    dividend 0x123333, which is 18.2 in 16.16.
  - The ISR callback `func_000C35C8`, which the same init installs, adds the increments on every
    interrupt.
  - TACP has the same chain at `func_000CC3A9`, `func_000C6386`, `func_000C5C13`,
    `func_000C5D29`/`func_000C60AE` and `func_000C62BC`.
  - The planted run that expects the PIT clock as the dividend (a BIOS tick that would follow the
    PIT rate) fails in both EXEs.

### q2 tick rule

`uv run python .planning/spikes/007-locate-997-training/q2_tickrule.py` (exit 0), kept in the
gitignored `build/spike007-q2.out`:

```
PASS UFO2P.EXE loop-located-ufo2p loop rows 2 [0x000105D0:0x00010603..0x000108CE 0x00010940:0x000109A0..0x00011392] clock [0x0004AB30] accumulator 0x000D4D6E speed 0x000D4D58 expected loop 0x00010940
PASS UFO2P.EXE accumulator-modulus-is-36 modulus 36 at 0x0004AB59 expected 36 (PR #1688)
PASS UFO2P.EXE one-second-per-frame `sub _, 36` count 1 in 0x0004AB30 (one per call: at most one game second per frame)
PASS UFO2P.EXE paces-on-bios-tick rows calling the clock [0x00010940]; busy-wait on int386 0x1A [0x00010940:0x00011127..0x00011174]
PASS UFO2P.EXE wait-skip-guards globals tested right before the busy-wait by a jump past it [0x000D4D5C 0x00183BAC] expected [0x000D4D5C 0x00183BAC]; rows writing both the speed and 0x000D4D5C: 15, the 6 speed setters among them True; constants stored to it [0, 1, 600]
PASS UFO2P.EXE speed-values stored [0, 1, 2, 4, 6, 600] compared [0, 1, 2, 4, 6, 60, 600] at 0x000D4D58
PASS UFO2P.EXE get-text-sections 50 of 50 section pointers at 0x000F3794
PASS UFO2P.EXE speed-table-one-entry-per-label labels 4: slow 38/43 sites [0x000523C1] speed [1]; normal 38/44 sites [0x00052439] speed [2]; double 38/45 sites [0x000524B1] speed [4]; quadruple 38/46 sites [0x0005252C] speed [6]; tables [('0x000108EC', 6, [1, 2, 4, 6]), ('0x00010904', 6, [1, 2, 4, 6]), ('0x0001091C', 6, [1, 2, 4, 6])]
PASS UFO2P.EXE research-candidates-refuted 0x00022EF0 reaches clock False; 0x00026B80 reaches clock False; table 0x001303E0 users [0x000ACDC0 0x000BB500] in loop/clock False
PASS TACP.EXE loop-located-tacp loop rows 9 [0x00010EE0:0x00010F40..0x0001135C 0x000161B0:0x000161CC..0x000167F2 0x00040B40:0x00040B4A..0x00040B5F 0x00042F90:0x00042FB4..0x000433D4 0x00050620:0x0005086E..0x00050CB6 0x000760A0:0x000761D1..0x000763DA 0x00077DF0:0x00077E42..0x00077F33 0x000AE060:0x000AE0C0..0x000AE2F9 0x000B70D0:0x000B7A25..0x000B85BD] clock [0x0003D160] accumulator 0x000E6C36 speed 0x000E6C24 expected loop None (report)
PASS TACP.EXE accumulator-modulus-is-36 modulus 36 at 0x0003D184 expected 36 (PR #1688)
PASS TACP.EXE one-second-per-frame `sub _, 36` count 1 in 0x0003D160 (one per call: at most one game second per frame)
PASS TACP.EXE tacp-paces-on-same-bios-tick rows calling the clock [0x000116B0 0x000B6E50]; busy-wait on int386 0x1A [0x000116B0:0x00011909..0x00011959]
PASS TACP.EXE wait-skip-guards globals tested right before the busy-wait by a jump past it [0x000E6D64 0x001B7BAC 0x0027A0EB] expected [0x000E6D64 0x001B7BAC 0x0027A0EB]
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
- `wait-skip-guards` (fix round 1). Not every frame waits.
  - UFO2P tests the no-wait counter `D_000D4D5C` and the byte `D_00183BAC` right before the
    busy-wait, each with a jump past it.
  - 15 rows write both the speed and the counter, including all six speed setters. The only
    constants stored to the counter are 0, 1 and 600.
  - TACP's skip tests a flag computed from `D_000E6D64`, `D_001B7BAC` and `D_0027A0EB`.
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
  **not located**. The call-graph route of D-03 or reading is needed. q6 (plan 07-08) checks
  the graph itself; it does not locate the accrual, so this gap passes to plan 07-22.
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

### q4 strings through get_text

`uv run python .planning/spikes/007-locate-997-training/q4_strings.py` (exit 1: two findings),
kept in the gitignored `build/spike007-q4.out`:

```
PASS UFO2P.EXE get-text-table table 0x000F3794 slots 52 non-null 52 strings 2112 blob [0x000E7E2A..0x000F3794) dump-loop bound [50] expected slots 52 bound 50; self-consistent True
FAIL UFO2P.EXE get-text-args sites 997 in 180 rows; full 742 = 74.4% (target 80%); section-only 227, index-only 0, neither 28; full pairs past their section 0 []
PASS TACP.EXE get-text-table table 0x00292D18 slots 52 non-null 21 strings 672 blob [0x0028EC22..0x00292D18) dump-loop bound [] expected slots None bound None; self-consistent True
PASS TACP.EXE get-text-args sites 315 in 88 rows; full 255 = 81.0% (target 80%); section-only 47, index-only 1, neither 12; full pairs past their section 3 [0x0003600C 0x000537CA 0x000539E7]
PASS TACP.EXE speed-labels pause 36/0 sites [0x000A751A] rows [0x000A7490] speed [0]; slow speed 36/1 sites [0x000A758C] rows [0x000A7490] speed [1]; normal speed 36/2 sites [0x000A75FE] rows [0x000A7490] speed [2]; double speed 36/3 sites [0x000A7670] rows [0x000A7490] speed [4]; absent ['quadruple speed']; expected {'pause': 0, 'slow speed': 1, 'normal speed': 2, 'double speed': 4}
FAIL q4 item 263-4 'chrysalis' rows found 0; UFO2P: strings 8 S rows 0 [] F rows 0 [] partial 8; TACP: strings 2 S rows 0 [] F rows 0 [] partial 1
PASS q4 item 263-6 'funding assessment' rows found 1; UFO2P: strings 1 S rows 1 [0x00098A70] F rows 0 [] partial 0; TACP: strings 0 S rows 0 [] F rows 0 [] partial 0
PASS q4 item 263-9 'improve relations' rows found 1; UFO2P: strings 1 S rows 1 [0x000977F0] F rows 0 [] partial 7; TACP: strings 0 S rows 0 [] F rows 0 [] partial 0
PASS q4 item 263-13 'combat training' rows found 2; UFO2P: strings 2 S rows 2 [0x0004F100 0x00052150] F rows 0 [] partial 24; TACP: strings 0 S rows 0 [] F rows 0 [] partial 0
PASS q4 item 263-15 'transfer' rows found 8; UFO2P: strings 17 S rows 8 [0x00067930 0x0006B270 0x00091AF0 0x0009DA90 0x0009E0C0 0x000A0170 0x000A0A40 0x000A1990] F rows 1 [0x0009DA90] partial 26; TACP: strings 0 S rows 0 [] F rows 0 [] partial 0
PASS q4 item 263-22 'tactical.map' rows found 3; UFO2P: strings 1 S rows 0 [] F rows 2 [0x000B0F70 0x000B4590] partial 0; TACP: strings 1 S rows 0 [] F rows 1 [0x000141A0] partial 0
PASS q4 item 264-3 'score' rows found 4; UFO2P: strings 3 S rows 3 [0x00060C80 0x00060F50 0x00098240] F rows 0 [] partial 20; TACP: strings 2 S rows 1 [0x000A6D10] F rows 0 [] partial 5
PASS q4 item 264-10 'kills' rows found 2; UFO2P: strings 4 S rows 1 [0x000863F0] F rows 0 [] partial 19; TACP: strings 1 S rows 1 [0x000550C0] F rows 0 [] partial 1
PASS q4 item 264-16 'treaty' rows found 1; UFO2P: strings 1 S rows 1 [0x00092970] F rows 0 [] partial 8; TACP: strings 0 S rows 0 [] F rows 0 [] partial 0
PASS q4 item 264-21 '/music/' rows found 2; UFO2P: strings 33 S rows 0 [] F rows 1 [0x000B63F0] partial 0; TACP: strings 33 S rows 0 [] F rows 1 [0x000B0200] partial 0
PASS q4 item 265-1 'brain.dat' rows found 5; UFO2P: strings 1 S rows 0 [] F rows 3 [0x000A5F40 0x000A6040 0x000A61E0] partial 0; TACP: strings 2 S rows 0 [] F rows 2 [0x00014AF0 0x000B20B0] partial 0
PASS q4 item 265-13 'new recruit' rows found 1; UFO2P: strings 1 S rows 1 [0x0007AFF0] F rows 0 [] partial 9; TACP: strings 0 S rows 0 [] F rows 0 [] partial 0
q4 found 11 of 12
2 FAILED
```

- **The section tables.** Both tables have 52 slots. UFO2P fills all 52. Research's "50
  sections" is the loop bound of the dump routine that follows `get_text` in the same row: it
  dumps only the first 50, but sections 50 and 51 exist and are called (q2's
  `get-text-sections 50 of 50` checked the first 50 only). TACP fills 21 of its 52 slots; the
  others are null, so the battlescape carries only the sections it uses. Every pointer starts a
  string below the table, and no two share a start.
- **Argument recovery rate (D-03 target 80%).**

  | EXE | call sites (rows) | (section, index) recovered | section only | neither |
  |---|---|---|---|---|
  | UFO2P | 997 (180) | 742 = **74.4%** (below target: a finding) | 227 | 28 |
  | TACP | 315 (88) | 255 = **81.0%** | 47 (+1 index only) | 12 |

  - The rows match research's caller counts (180 / 88).
  - Section-only sites take the index from a variable or a loop (base + i): lists, tables and
    per-record names. They are the partial route: they give the section and the rows that use
    it, not the string.
  - "Neither" sites take both from variables or from registers set before an earlier call
    (the tracker forgets eax/edx at every call, which is conservative).
  - Three TACP sites ask for indexes past the end of their TACP section (`0x0003600C` 37/380,
    `0x000537CA` and `0x000539E7` 38/25). Those indexes exist in UFO2P's numbering, so this is
    code shared with the cityscape that never shows those strings in battle [hand: the reading
    of why].
- **TACP speed labels** (`speed-labels`): Pause, Slow, Normal and Double sit in section 36,
  indexes 0-3, all shown by `func_000A7490`, each under a compare of the speed variable
  `D_000E6C24` with 0, 1, 2 and 4. There is no Quadruple label in TACP. This fills the TACP
  gap in the #997 lead.
- **The 12-item sample: 11 of 12 get an entry row.** One keyword per item, matched inside the
  data strings. Route S goes through `get_text` (section, index); route F through an exact
  fixup (file names and hand-off files).

  | Item | Keyword | Route | Rows |
  |---|---|---|---|
  | #263-4 eggs/chrysalis hatch | `chrysalis` | S partial only | **none** (8 UFO2P + 1 TACP section-only rows: the creature names are shown from lists) |
  | #263-6 weekly funding | `funding assessment` | S | U `0x00098A70` (it also loads the funding screen image) |
  | #263-9 bribes | `improve relations` | S | U `0x000977F0` |
  | #263-13 base training | `combat training` | S | U `0x0004F100`, `0x00052150` |
  | #263-15 transfers | `transfer` | S + F | 8 U rows, `0x0009DA90` also by file |
  | #263-22 map spawn | `tactical.map` | F | U `0x000B0F70`, `0x000B4590`; T `0x000141A0` |
  | #264-3 score and finances | `score` | S | U `0x00060C80`, `0x00060F50`, `0x00098240`; T `0x000A6D10` |
  | #264-10 per-battle stats | `kills` | S | U `0x000863F0`; T `0x000550C0` |
  | #264-16 treaties | `treaty` | S | U `0x00092970` |
  | #264-21 dynamic music | `/music/` | F | U `0x000B63F0`; T `0x000B0200` |
  | #265-1 battle AI | `brain.dat` | F | U `0x000A5F40`, `0x000A6040`, `0x000A61E0`; T `0x00014AF0`, `0x000B20B0` |
  | #265-13 name generator | `new recruit` | S | U `0x0007AFF0` |

  - **What "found" means.** The route gives at least one row that shows or loads text tied to
    the item. It does not show that the row holds the rule. The tier drafts (07-25, 07-28,
    07-32) confirm each entry by reading and by the call graph.
  - **How the keywords were chosen.** The plan names the items. The keywords were picked after
    reading the text blob privately, the way a tier drafter would; for example `improve
    relations` is the bribe dialog and `kills` is the agent service record. So 11 of 12 measures
    whether a drafter who reads the text can reach a row, not a blind keyword hit rate.
  - **Weak entries.** `new recruit` is the arrival message, next to the name generator but not
    in it. The names themselves are not in either EXE's text (no name list was found), so
    #265-13 needs the call graph from the recruitment rows.
  - **The miss.** Chrysalis and egg names appear only in lists (section-only sites), so the
    hatch rule needs the data-table or call-graph route (`CREW_ALIEN_BUILDING`, research Q3).

### q5 tables by VA identity

`uv run python .planning/spikes/007-locate-997-training/q5_tables.py` (exit 0), kept in the
gitignored `build/spike007-q5.out`:

```
SKIP q5 headers absent (C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\build\openapoc-extractors)
PASS UFO2P.EXE cd-build XCOM3/UFOEXE/UFO2P.EXE size 1702206 sha1 6be861d611548f5a00b0b3bc49a82ed29d25fd4a expected size 1702206 sha1 6be861d611548f5a00b0b3bc49a82ed29d25fd4a
PASS UFO2P.EXE data-object-identity installed [0x000D0000..0x00251E20) CD [0x000D0000..0x00251E20) same True; identical pages 380 of 386; differing bytes 258; expected 380 of 386, 258
PASS TACP.EXE cd-build XCOM3/TACEXE/TACP.EXE size 3170298 sha1 af32ccc371c153c514fb8e3cc80e765de380aef9 expected size 3170298 sha1 af32ccc371c153c514fb8e3cc80e765de380aef9
PASS TACP.EXE data-object-identity installed [0x000E0000..0x0033F0B0) CD [0x000E0000..0x0033F0B0) same True; identical pages 605 of 608; differing bytes 190; expected 605 of 608, 190
ALL PASS
```

- **The OpenApoc headers were absent in this session** (`build/openapoc-extractors/` does not
  exist; agents have no network). So the per-table claim `tables-va-identity` was skipped, and
  research Q3's "35 UFO2P + 12 TACP tables byte-identical, 23 / 10 with code refs" stays
  research's measurement, not this spike's.
- What q5 does show without the headers: the CD and installed data objects have the same base
  and size, and 380 of 386 UFO2P pages (258 bytes differ) and 605 of 608 TACP pages (190 bytes
  differ) are identical. A table re-located by VA identity therefore lands on identical bytes
  unless it falls in one of those 9 pages, which the per-table check reports.
- The header path was exercised with a synthetic header in the session scratchpad that holds two
  of our own locators (the CD file offsets of the two `get_text` tables), never OpenApoc's.
  Both mapped and were identical; with `--plant` the flipped UFO2P table was reported as
  differing. The count check (47 spans) failed there, as it must for 2 spans. A span may map
  into both EXEs, because the headers do not say which EXE a span belongs to; the claim then
  requires identity in both.
- q5 is not an input of the D-03 verdict formula.

### q6 call graph

`uv run python .planning/spikes/007-locate-997-training/q6_callgraph.py` (exit 0), kept in the
gitignored `build/spike007-q6.out`:

```
PASS UFO2P.EXE direct-edges-equal-callindex own 5288 CallIndex 5288 only-own 0 only-CallIndex 0 expected 5288
PASS UFO2P.EXE reach-direct from main_ 0x00010010: 1128 / 1553 walked rows (72.6%); research 1128 / 1553, off 0.00%; edges 5288
PASS UFO2P.EXE reach-pointer from main_ 0x00010010: 1412 / 1553 walked rows (90.9%); research 1412 / 1553, off 0.00%; edges 5627
PASS UFO2P.EXE reach-table from main_ 0x00010010: 1471 / 1553 walked rows (94.7%); research 1471 / 1553, off 0.00%; edges 6381
INFO UFO2P.EXE pointer edges 343; table slots 66 in 13 runs; referenced from game/thunk code 10 with the 64-byte lead-in (edges 755), 3 without it (edges 18, reach 1429)
PASS TACP.EXE direct-edges-equal-callindex own 4885 CallIndex 4885 only-own 0 only-CallIndex 0 expected 4885
PASS TACP.EXE reach-direct from main_ 0x000102A0: 1224 / 1526 walked rows (80.2%); research 1224 / 1526, off 0.00%; edges 4885
PASS TACP.EXE reach-pointer from main_ 0x000102A0: 1479 / 1526 walked rows (96.9%); research 1479 / 1526, off 0.00%; edges 5215
PASS TACP.EXE reach-table from main_ 0x000102A0: 1479 / 1526 walked rows (96.9%); research 1479 / 1526, off 0.00%; edges 5266
INFO TACP.EXE pointer edges 336; table slots 34 in 12 runs; referenced from game/thunk code 8 with the 64-byte lead-in (edges 52), 2 without it (edges 19, reach 1479)
ALL PASS
```

- **Direct edges.** The own scan equals `CallIndex` edge for edge (5,288 / 4,885), as research
  counted.
- **Reachability from `main_`** reproduces research Q1 exactly in both EXEs: direct 1,128 /
  1,224, + pointers 1,412 / 1,479, + tables 1,471 / 1,479 (of 1,553 / 1,526 game and thunk rows).
- **The table rule needs a record lead-in to match research.** With the strict rule (a code
  fixup into [first slot, last slot + 4)), which `tools/reverseapoc/callgraph.py` uses (plan
  07-05), only 3 UFO2P / 2 TACP runs are referenced from game code and UFO2P's reach is 1,429,
  42 rows (2.9%) short of research. Code often addresses the base of a record whose function
  pointer sits a few bytes in: the bases observed lie 4, 20 (four runs) and 41 bytes before a
  run's first slot. Counting references up to 64 bytes before the first slot wires 10 / 8 runs,
  exactly research's "10 / 8 referenced", and gives 1,471. The 64 was chosen by trying 0-128:
  20-64 give 1,471, 128 gives 1,472. TACP's reach is 1,479 either way.
- The slot count is 66 against research's 67 for UFO2P because q6 drops slots onto
  data-in-code rows (research and `callgraph.py` keep them to shape runs); TACP 34 against 35.

## Verdict

**VALIDATED**, by the D-03 formula from the scripts' own lines:

| Input | Result | Formula |
|---|---|---|
| q2 tick rule | `ALL PASS` (both EXEs; plants fail) | pass |
| q3 training rule | `ALL PASS` (plants fail) | pass |
| q4 sample | `q4 found 11 of 12` | >= 10 |

VALIDATED needs q2 and q3 to pass and q4 to find at least 10 of 12; PARTIAL one of q2/q3 or 6-9
of 12; INVALIDATED otherwise. Research A18 expected PARTIAL to VALIDATED.

What the formula does not see:
- **q3 passes, but the TACP accrual is not located.** q3 locates the hand-off, the UFO2P stat
  copy and the android branch. Where the battle raises the 17 stat fields is only a heuristic
  lead (`accrual-sites`, 2 rows). The improvement rule of #263-1 itself still needs the call
  graph or reading (plan 07-22).
- **The #997 route was the BIOS tick, not the PIT.** D-03 named the PIT / INT 8 setup; that
  leads to the sound library. D-26 moved the start to the BIOS-tick readers, and q2 found the
  rule from there.
- **q4's keywords were chosen by reading the text privately**, and "found" means an entry row
  that shows or loads the item's text, not the rule. One miss (#263-4) and one weak entry
  (#265-13) need other routes.
- **UFO2P's `get_text` argument recovery is 74.4%**, below the 80% research target (TACP 81.0%).
  A quarter of UFO2P's text sites take their index from data (lists, records), so the string
  route finds those rows only by section.

## Consequence for Phase 7

- **The tier drafts (07-25, 07-28, 07-32) can locate entries by strings and xrefs**: the
  `get_text` (section, index) route for UI text and exact fixups for file names and hand-off
  files. q4's method (`decode_table`, `call_sites`, `search`) is the recipe.
- **They still add the call graph where the text route stops**:
  - items whose text is shown only from lists (section-only sites, such as #263-4's creature
    names) and items with no text of their own (#265-13's names);
  - #263-1's TACP accrual (07-22, Tier 1).
- **Data tables re-located by VA identity are safe** for the data object: 380 / 386 and 605 /
  608 pages are identical between the CD and installed builds (q5). Each table still gets its
  own byte check when the headers are present.
- **Table edges: plan 07-22 should decide the record lead-in.** The production call graph
  (`callgraph.py`, 07-05) wires only runs whose first slot is addressed directly. Research's
  numbers, and 42 more UFO2P rows reached from `main_`, come from code that addresses a record's
  base a few bytes before its pointer slots (q6).
- **#997:** nothing changes for Tier 1. q4 adds the TACP speed labels to the lead.

## Planted failures

| Run | What is planted | Result | Exit |
|---|---|---|---|
| `q1 --plant` | UFO2P expected reader `0x00011430` -> `0x00011440` | `FAIL UFO2P.EXE int1a-readers immediate [0x00011430] expected [0x00011440]`, `1 FAILED` | 1 |
| `q1 --mutant` | every `mov reg, 0x1a` immediate in game rows zeroed in an in-memory copy of the flat image | UFO2P `int1a-readers immediate []` and `int1a-pinned-readers []` FAIL; TACP `int1a-readers immediate []` FAIL; `3 FAILED` (the readers are reported missing) | 1 |
| `q1 --plant-chain` | expected BIOS-chain dividend 0x123333 -> 0x1234DC (the PIT clock: a BIOS tick that would follow the PIT rate) | `bios-chain-cadence` FAILs in both EXEs, `2 FAILED` | 1 |
| `q2 --plant` | expected modulus 36 -> 144 (OpenApoc's assumed ticks per second) | `FAIL UFO2P.EXE accumulator-modulus-is-36 modulus 36 at 0x0004AB59 expected 144`, the same for TACP at `0x0003D184`, `2 FAILED` | 1 |
| `q2 --plant-guards` (plan 07-08) | each EXE's expected wait-skip guard set without its last global (UFO2P without `0x00183BAC`, TACP without `0x0027A0EB`) | `wait-skip-guards` FAILs in both EXEs, `2 FAILED` | 1 |
| `q3 --plant` | TACP expected writer `0x000156A0` -> `0x000156B0` | `unitr-writer`, `record-layout`, `handoff-fields-agree`, `accrual-sites` and TACP `learning-ai-files` FAIL; `5 FAILED` | 1 |
| `q4 --plant` | UFO2P expected get_text slot count 52 -> 0x10000 (impossible) | `FAIL UFO2P.EXE get-text-table ... expected slots 65536`, `3 FAILED` (the plant plus the two findings of the default run) | 1 |
| `q5 --plant` | one installed byte flipped in memory at `0x000D0000` (the first identical UFO2P data page; with headers, the first table) | `FAIL UFO2P.EXE data-object-identity ... identical pages 379 of 386; differing bytes 259`, `1 FAILED`; with the synthetic header the flipped table is listed as differing | 1 |
| `q6 --plant` | expected direct edges + 1 in both EXEs (5,289 / 4,886) | `direct-edges-equal-callindex` FAILs in both EXEs, `2 FAILED` | 1 |

## Investigation Trail

- Fix round 1 (review): the lead first gave 18.2065 Hz as if a script had checked it. q1 only
  showed where the PIT and INT 8 code sits, not how fast the BIOS tick runs while the sound timer
  owns INT 8. So the sound library was read by hand. The timer init programs the PIT for its
  fastest event, and slot 15 is a "DOS rate" (0xFF00) event whose callback far-returns into the
  saved old INT 8 vector. Each interrupt adds the slot's increment to a 16.16 accumulator. The
  event fires when bit 16 sets, and the high word is then cleared. The increment is
  0x123333 / (1,193,180 / divisor), or 0x10000 at divisor 0xFFFF. q1 `bios-chain-cadence` now
  checks the wiring and the dividend; the bit-16 fire test and the divide by the PIT rate stay
  hand-read.
- Fix round 1: the lead said every frame waits a tick, but the no-wait counter lets frames skip
  the wait. q2 `wait-skip-guards` now finds the guards and the constants stored to the counter.
  How the decrement uses up a 1 was read by hand.

- Plan 07-08, before the verdict (orchestrator ruling on the 07-02 re-review). Four evidence
  tags in the lead claimed more than the scripts assert; they are corrected here, not in the
  07-02 SUMMARY:
  - "The ISR callback adds the increment on every interrupt [script]": q1 asserts only that a
    callback the timer init installs adds increment-array entries to memory. The per-interrupt
    call is now tagged [hand].
  - q1's `bios-chain-cadence` detail text said the increments are "added per interrupt"; it
    now says "added in" the callback, which is what the claim checks.
  - UFO2P `wait-skip-guards` pinned only `D_000D4D5C`; TACP's passed on any non-empty set. q2
    now requires the guard sets to equal EXPECTED in both EXEs (UFO2P `D_000D4D5C`,
    `D_00183BAC`; TACP `D_000E6D64`, `D_001B7BAC`, `D_0027A0EB`), and `--plant-guards` gives the
    claim its own planted failure.
  - "There is no 36 Hz or 144 Hz game timer" had no tag; it is now [derived] from q1's PIT sites
    and q2's rows calling the clock.

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
- q4 (plan 07-08) first bounded the section table at the next address any code row references.
  For UFO2P that is 3 slots too far: the slots after slot 51 hold nonzero words without fixups.
  The table now also ends at the first nonzero slot without a fixup, which gives 52 in both
  EXEs (TACP's next referenced global is exactly slot 52).
- q6 first wired a table run only from code addressing [first slot, last slot + 4). That
  reproduced research's direct and pointer reach exactly but gave 1,429 instead of 1,471 for
  UFO2P tables, with 3 runs referenced against research's 10. Listing each run's nearest code
  reference showed record bases 4-41 bytes before the first slot; a 64-byte lead-in reproduces
  research (see q6).
- q5's first cross-EXE rule counted a span as identical if it matched in either EXE. A
  synthetic header showed the flaw: a UFO2P span also maps into TACP's data and is identical
  there, so the plant still passed. The claim now requires identity in every EXE a span maps
  into.
- q4 first counted a recovered pair past its section's end as a recovery error. The three TACP
  cases are real constants (37/380 and 38/25, read in the private disassembly): shared code that
  uses UFO2P's numbering. They are now reported, not failed.
