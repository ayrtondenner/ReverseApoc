---
phase: 07-mechanics-first-decompilation
plan: 02
subsystem: research-spike
tags: [spike-007, mechanics, 997, training, bios-tick, get_text, capstone, rawle]

requires:
  - phase: 03-le-round-trip
    provides: "spike 001 rawle.py (independent raw LE reader), le.py"
  - phase: 06-agent-pilot
    provides: "contextpack.CallIndex, check.load_exe, committed functions.csv"
provides:
  - "spike 007 README (verdict pending) with the #997 lead for the owner and #263-1 entry candidates"
  - "q1_timebase.py: BIOS-tick readers, PIT/INT 8 confinement, caller counts (shared reader for q2/q3)"
  - "q2_tickrule.py: time-advance loops, 36-unit accumulator, speed values, speed labels vs speed tables"
  - "q3_training.py: unitr.dat hand-off, UFO2P stat update, android branch, TACP accrual lead, Learning AI split"
affects: [07-08, 07-22, 07-25, 07-28, 07-32]

actuals:
  tokens: 22049
  tasks: 3
  commits: 3
plan_head_before: 0f9de364337258572e5dcddb10a133cd2c95c821
plan_head_after: f8744612c9e2ed312cabd49c00af318ad02cd323

tech-stack:
  added: []
  patterns:
    - "spike scripts share one reader: q2/q3 import q1_timebase (Image, tracked, Regs, Report)"
    - "spike-grade constant tracker: per-row linear walk, reset at jump targets, pinned single-write registers"
    - "values found by a spike run are pinned in EXPECTED with a 'this spike' comment; research values stay labelled"

key-files:
  created:
    - .planning/spikes/007-locate-997-training/README.md
    - .planning/spikes/007-locate-997-training/q1_timebase.py
    - .planning/spikes/007-locate-997-training/q2_tickrule.py
    - .planning/spikes/007-locate-997-training/q3_training.py
  modified: []

key-decisions:
  - "#997: both EXEs pace on the BIOS tick (>= 1 tick per frame outside the no-wait exception; the tick stays at 18.2 Hz under the sound timer via its INT 8 chain, q1 bios-chain-cadence) and advance game time in 36ths of a second (16-bit accumulator, speed added per frame, one second at most per frame); PR #1688 confirmed in both halves"
  - "UFO2P speeds 1/2/4/6 carry the labels Slow/Normal/Double/Quadruple (Quadruple = 3x Normal); 600 is a 5-minute time-skip path, not a speed"
  - "#263-1: UFO2P copies 17 stat fields from scenario/unitr.dat into agent records; the improvement rule is on the TACP side and its accrual is not located (gap for 07-08 call-graph route)"
  - "Located addresses are pinned in EXPECTED as 'this spike'; research candidates are checked by a separate refuted claim"

patterns-established:
  - "Spike PASS/FAIL scripts reuse q1_timebase's Image (rawle bytes + fixups, functions.csv rows) instead of re-reading the LE"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "q1 time base: BIOS-tick readers, PIT/INT 8 only in the sound library, caller counts, no 0x46C read; plant and mutant runs fail"
    requirement: "DEC-01"
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/007-locate-997-training/q1_timebase.py (ALL PASS, exit 0); --plant exit 1; --mutant exit 1"
        status: pass
    human_judgment: false
  - id: D2
    description: "q2 tick rule: time-advance loops, 36-unit accumulator in both EXEs, BIOS-tick busy-wait, speed values, UFO2P labels vs speed tables; plant fails"
    requirement: "DEC-01"
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/007-locate-997-training/q2_tickrule.py (ALL PASS, exit 0); --plant exit 1"
        status: pass
    human_judgment: false
  - id: D3
    description: "q3 training rule: unitr.dat hand-off, UFO2P stat update, android branch, Learning AI split, TACP accrual heuristic; plant fails"
    requirement: "DEC-01"
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/007-locate-997-training/q3_training.py (ALL PASS, exit 0); --plant exit 1"
        status: pass
    human_judgment: false
  - id: D4
    description: "#997 lead for the owner in the README (answer, addresses, evidence, matched code backs it: no), relayed by the orchestrator (ruling F22)"
    verification: []
    human_judgment: true
    rationale: "The owner decides what to tell OpenApoc; the lead's prose interpretation (rates, labels, the 600 time-skip read by hand) needs a human read"
  - id: D5
    description: "#263-1 entry candidates per EXE with evidence kinds for plan 07-22"
    verification:
      - kind: other
        ref: "q3_training.py claims unitr-reader, unitr-writer, stat-update, android-label, accrual-sites"
        status: pass
    human_judgment: true
    rationale: "The TACP accrual (the actual improvement rule) is only a heuristic lead; the verdict and whether this suffices is plan 07-08's call"

duration: 53min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 02: Spike 007 part 1 (time base, tick rule, training rule) Summary

**#997 located in both EXEs: frames wait at least one BIOS tick (INT 1Ah via int386_). The tick stays at 18.2 Hz while the sound library owns INT 8, because it chains the old vector (fix round 1). The exception is UFO2P's no-wait counter. Each frame adds the speed (UFO2P 1/2/4/6 = Slow/Normal/Double/Quadruple) to a 16-bit accumulator, and 36 units make one game second (UFO2P func_0004AB30, TACP func_0003D160). #263-1 is located as the scenario/unitr.dat record copy (TACP func_000156A0 -> UFO2P func_000B2A90 -> func_000B2E80, 17 stat fields). The TACP accrual is still a gap.**

Execution context nonce: 6330e2b3de9a849e

## Performance

- **Duration:** 53 min
- **Started:** 2026-10-27T14:50:48Z
- **Completed:** 2026-10-27T15:43:53Z
- **Tasks:** 3
- **Files modified:** 4 (all created)

## Accomplishments

- **q1:** confirms research's time base in both EXEs.
  - rawle.py reads the same bytes and fixups as le.py.
  - The PIT and INT 8 sites are only in the sound-library rows.
  - The non-constant vector sites are only in the keyboard installers.
  - Caller counts: 28 / 35 / 10, equal to CallIndex.
  - No direct 0x46C read.
  - New: UFO2P `func_00010940` also reads INT 1Ah, through a register it sets once. It is the
    cityscape frame loop.
- **q2:** answers #997 and confirms both halves of PR #1688 in both EXEs.
  - The BIOS-tick busy-wait: UFO2P `0x00011127..0x00011174`, TACP `0x00011909..0x00011959`.
  - The 36-unit accumulator: UFO2P `D_000D4D6E` fed by speed `D_000D4D58`; TACP `D_000E6C36`
    fed by `D_000E6C24`.
  - At most one game second per frame.
  - UFO2P labels (get_text section 38, indexes 43-46) map to speeds 1/2/4/6. The three 6-slot
    speed jump tables have the same four active slots.
  - Research candidate A2 (`func_00022EF0`, `func_00026B80`, table `0x1303E0`) is refuted.
- **q3:** locates #263-1 as a record hand-off.
  - TACP writes 60 x 0x92 result records from the unit array (`D_00109ED0`, 0x49C stride).
  - UFO2P loads them into `D_00241D98`. `func_000B2E80` copies 17 fields into the agent records
    at `D_00144918`, and the writer fills every one of them.
  - The android branch of base training: get_text 37/404 site `0x0004F41A`, guard `0x0004F3F5`.
  - The Learning AI rows stay out of #263-1. The UFO2P reader reaches one of them only through
    the savegame loader `func_000A49D0`.
- **README:** a self-contained "#997 lead for the owner" (answer, addresses, evidence, "matched
  code backs it: no"), the #263-1 entry-candidate table, the planted-failure table and the
  investigation trail.

## #997 lead (for the orchestrator to relay; ruling F22)

The full lead is in `.planning/spikes/007-locate-997-training/README.md` § "#997 lead for the
owner".
This was superseded by fix round 1; the corrected lead is in the README and under "Fix round 1"
below, with each statement marked script / hand / assumption.
- **Answer.** Both EXEs pace on the BIOS tick: a frame waits until the tick moves [script].
  Each frame adds the speed value to a 16-bit sub-second accumulator, and 36 units make one game
  second [script]. A frame never adds more than one second [script].
- **The BIOS tick stays at about 18.2 Hz while the sound timer runs.** The sound library chains
  the old INT 8 handler with a 0x123333 (18.2 in 16.16) increment [script: wiring and dividend;
  hand: the fire test; assumption: INT 1Ah returns that handler's count].
- **No-wait exception (UFO2P).** Frames skip the wait while the no-wait counter `D_000D4D5C` is
  still nonzero after its per-frame decrement, or while `D_00183BAC` is set [script: guards and
  the stored constants 0/1/600]. Steady play at 1/2/4/6 still waits every frame [hand]; the 600
  setting does not [hand].
- **UFO2P speeds:** Slow = 1, Normal = 2, Double = 4, "Quadruple" = 6 (3 times Normal)
  [script]. Steady-state upper bounds: about 0.506 / 1.011 / 2.022 / 3.033 game seconds per real
  second; Normal is about real time. Pause is 0. 600 is a 5-minute time skip [hand].
- **TACP** uses the same rule with speeds 0/1/2/4.
- **Matched code backs it: no.**

## Task Commits

1. **Task 1: Tracer - README skeleton and q1_timebase.py** - `510b6cf` (spike)
2. **Task 2: q2_tickrule.py** - `2b3c193` (spike)
3. **Task 3: q3_training.py** - `f874461` (spike)

Tracer gate (Task 1): interactive end-of-phase mode, automated-only verify. The verify was re-run
and passed before Task 2 started (q1 ALL PASS exit 0, plant and mutant exit 1, ruff clean).

## Files Created/Modified

- `.planning/spikes/007-locate-997-training/README.md`: the spike record. Frontmatter
  `spike: 007`, `verdict: pending`, `related: [003]`. Results for q1-q3, the #997 lead, the
  #263-1 candidates, planted failures and the investigation trail.
- `.planning/spikes/007-locate-997-training/q1_timebase.py`: the time-base claims, plus the
  shared reader (Image, the constant tracker, Report) that q2 and q3 import.
- `.planning/spikes/007-locate-997-training/q2_tickrule.py`: the tick-rule claims, with `--plant`
  (expected modulus 144).
- `.planning/spikes/007-locate-997-training/q3_training.py`: the training-rule claims, with
  `--plant` (wrong writer address).
- Gitignored outputs: `build/spike007-q1.out`, `-q1-plant.out`, `-q1-mutant.out`, `-q2.out`,
  `-q2-plant.out`, `-q3.out` and `-q3-plant.out`.

## Decisions Made

- **Located addresses are pinned in `EXPECTED`.** They carry a "this spike" comment, so the
  scripts stay regression pins that pass, as q1's research values do. Research's wrong
  candidates are tested by a separate `research-candidates-refuted` claim.
- **The scripts print rate constants.** That means the speed values (UFO2P 0/1/2/4/6/600, TACP
  0/1/2/4) and the record sizes. They are the #997 answer and are constants like the modulus.
  Strings are never printed: only keyword labels (`speed`/`slow`/..., `unitr.dat`, `android`,
  `training`).
- **Behaviour read by hand is marked as such in the README**, not asserted by a script: the 600
  time skip, the per-speed subsystem step counts, the TACP start-speed flags and the agent
  record stride.

## Deviations from Plan

- **Orchestrator ruling F22:** the README's "#997 lead for the owner" is self-contained (answer,
  addresses, evidence, "matched code backs it: no"). It is repeated in this SUMMARY and in the
  return message so the orchestrator can relay it to the owner at once. 07-08 still reports the
  verdict and q4-q6.

### Auto-fixed Issues

**1. [Rule 1 - Bug] The research reader list was incomplete**
- **Found during:** Task 1
- **Issue:** UFO2P `func_00010940` also calls `int386_` with 0x1A, through a register it sets
  once. The plan's claim (b) would have been false as written.
- **Fix:** q1 reports immediate readers (research's list) and register-passed readers
  (`int1a-pinned-readers`) separately. `EXPECTED["pinned_readers"]` = {0x00010940} is marked as
  this spike's finding.
- **Files modified:** q1_timebase.py, README.md
- **Commit:** 510b6cf

**2. [Rule 1 - Bug] The tracker treated movsx/movzx as string instructions**
- **Found during:** Task 1
- **Fix:** string mnemonics are matched exactly (a regex on the last word of the mnemonic).
- **Commit:** 510b6cf

**3. [Rule 1 - Bug] Research's loop and speed-table candidates were wrong (A2)**
- **Found during:** Task 2
- **Issue:** the plan's `EXPECTED` was to hold `func_00022EF0` and table `0x1303E0`.
  `func_00022EF0` and `func_00026B80` never reach a clock, and `0x1303E0` is not a speed table.
- **Fix:** `EXPECTED` pins the located loop, clock, accumulator and speed variable. The research
  candidates go to a `research-candidates-refuted` claim. TACP `EXPECTED` stays `None` as
  planned, and the claim reports what it finds.
- **Commit:** 2b3c193

**4. [Rule 2 - Missing critical] q2 has more claims than the plan names**
- **Found during:** Task 2
- **Added:** `one-second-per-frame`, `speed-values` and `get-text-sections`. The #997 answer
  needs them: they show that a frame cannot add several seconds, and which values the speed
  takes.
- **Commit:** 2b3c193

**5. [Rule 1 - Bug] The plan's Learning AI claim is false as written**
- **Found during:** Task 3
- **Issue:** the plan claims none of the Learning AI rows is reached from `func_000B2A90`. In
  fact UFO2P `func_000A6040` is reached, through the savegame loader `func_000A49D0` that the
  reader calls first.
- **Fix:** the claim pins the reached set ({0x000A6040}) and checks that the reader reaches
  none of them without `func_000A49D0`.
- **Commit:** f874461

**6. [Rule 1 - Bug] The accrual heuristic counted stack locals**
- **Found during:** Task 3
- **Fix:** esp-based operands are excluded, which takes the candidates from 10 rows to 2. The
  remaining 2 rows are pinned as a heuristic. The TACP accrual is recorded as not located.
- **Commit:** f874461

---

**Total deviations:** 6 auto-fixed (5 Rule 1, 1 Rule 2), plus orchestrator ruling F22 applied.
**Impact on plan:** no scope creep. The files are exactly the plan's four. q2 and q3 import q1
instead of a new shared module, so `files_modified` is unchanged.

## Issues Encountered

- **The TACP training accrual is not located.** The UFO2P side only copies the values back. The
  rule that raises the stats changes 17 TACP unit fields during battle, through unit pointers
  this script cannot follow. For 07-08's verdict: q3 locates the hand-off and the application
  but not the improvement rule, so D-03's call-graph route (q6) is the natural next step.
- **TACP speed labels are not located.** TACP's get_text table has fixups on only 19 of its
  first 50 slots. Left to q4.

## Done gate

- `uv run ruff check .`: All checks passed.
- `uv run pytest -q` (host): 2874 passed, 35 skipped. Every skip reason is pre-existing and
  F2-allowed (objdiff-cli, ninja / run in the container, Ghidra, clang, only inside the
  container, POSIX-only, Windows file names, non-UTF-8 byte names, symlink privileges). No test
  was added or changed.
- The plan's `<verify>` commands for Tasks 1-3: all exit 0. q1 ALL PASS. q2 and q3 ALL PASS.
  Every planted or mutant run exits 1.
- No docker, no network, nothing posted. STATE.md, ROADMAP.md and `.planning/config.json` are
  untouched.

## User Setup Required

None.

## Next Phase Readiness

- Plan 07-08 (spike part 2) can run q4-q6, fill in the verdict and the MANIFEST row, and report
  to the owner. Expected verdict input from part 1:
  - #997 is fully located;
  - #263-1 is located up to the hand-off, with the TACP accrual missing.
- Plan 07-22 can copy the #263-1 and #997 entry candidates from the README tables into
  `config/mechanics.toml`. The #997 entries are UFO2P `0x00011430`, `0x00010940`, `0x0004AB30`
  and TACP `0x00011500`, `0x000116B0`, `0x0003D160`.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: .planning/spikes/007-locate-997-training/README.md, q1_timebase.py, q2_tickrule.py, q3_training.py
- FOUND commits: 510b6cf, 2b3c193, f874461 (ancestors of HEAD)

## Fix round 1

Orchestrator fix round after the task review. Findings and what changed:

1. **18.2065 Hz read as script-proven, and "nothing runs at 36 Hz" too.** The ruling's first
   option was taken: the bytes decide the cadence.
   - q1 has a new claim, `bios-chain-cadence`, in both EXEs. It checks that the sound library
     saves the old INT 8 vector and that a chain routine far-returns into it. That routine is
     called only by an event callback the timer init registers.
   - The event's increment dividend is 0x123333 (18.2 in 16.16), set in the rate rows. The ISR
     callback the same init installs adds the increments on every interrupt.
   - So the BIOS tick stays at about 18.2 Hz whatever rate the PIT runs at: 18.2000 nominal,
     18.2001 with a 30 Hz event, 18.2068 at the DOS-rate divisor 0xFFFF.
   - Hand-read: the bit-16 fire test and the divide by the PIT rate.
   - Assumption: that INT 1Ah returns the count of the chained BIOS handler (standard BIOS under
     DOS/4GW).
   - Planted proof: `q1 --plant-chain` expects the PIT clock 0x1234DC as the dividend and fails in
     both EXEs.
   - The lead now labels every statement script / hand / assumption, and quotes the rates as
     speed x 18.2 / 36.
2. **"Every frame waits" versus the no-wait counter.**
   - q2 has a new claim, `wait-skip-guards`. In UFO2P it finds the tests right before the
     busy-wait that jump past it: the no-wait counter `D_000D4D5C` and the byte `D_00183BAC`.
     It also checks that all six speed setters write the counter and that the only constants
     ever stored to it are 0, 1 and 600.
   - In TACP it reports the globals behind the computed skip flag.
   - The lead now states the exception and limits "upper bounds" to steady state. That a counter
     value of 1 is used up before the test, so steady play waits every frame, is hand-read.

Commits:
- `e3ca02b` spike(007): prove the BIOS-tick cadence and the no-wait guard
- `adb0ec2` spike(007): pin the no-wait counter's stored constants
- the README and SUMMARY commit (docs(07-02))

Re-runs (host):
- q1 ALL PASS; `--plant`, `--mutant` and `--plant-chain` exit 1.
- q2 ALL PASS; `--plant` exits 1.
- q3 ALL PASS (unchanged; it imports q1 and q2); `--plant` exits 1.
- `uv run ruff check .` is clean.

