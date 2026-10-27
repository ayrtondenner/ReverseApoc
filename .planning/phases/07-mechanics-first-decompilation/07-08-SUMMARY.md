---
phase: 07-mechanics-first-decompilation
plan: 08
subsystem: research-spike
tags: [spike-007, mechanics, 997, get_text, va-identity, callgraph, verdict]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-02: spike 007 q1-q3, the shared reader (q1 Image/tracker) and the #997 lead"
provides:
  - "q4_strings.py: get_text section tables, call-site (section, index) recovery rate, TACP speed labels, 12-item Tier 2-4 sample (11 of 12)"
  - "q5_tables.py: CD-build data objects identical to the installed build by VA (pages and bytes); per-table OpenApoc check (skipped: headers absent)"
  - "q6_callgraph.py: direct edges equal CallIndex; research Q1 reachability reproduced (table runs need a 64-byte record lead-in)"
  - "spike 007 verdict PARTIAL (D-03; the plan's formula alone reads VALIDATED) and the consequence for the tier drafts; MANIFEST idea block and 007 row"
  - "the #997 owner report (delivered at the Task 3 checkpoint) and a draft OpenApoc comment for the owner (chat only)"
affects: [07-22, 07-25, 07-28, 07-32]

actuals:
  tokens: 20900
  tasks: 3
  commits: 5
plan_head_before: d73427f8500018ff3be6d6b8c5f4394ecdd587c5
plan_head_after: 601d42d
# fix round 1: fd7d973 (README, MANIFEST) and this SUMMARY's update
# Measured `git rev-list --count d73427f..HEAD` is 35 (HEAD 8a8f98e): main also took the wave-2
# merges and other plans' commits while this sequential plan ran. This executor's own commits in
# that range are the 5 spike(007) commits listed under Task Commits (F35), plus this SUMMARY.

tech-stack:
  added: []
  patterns:
    - "get_text route: decode the section table, recover (eax, edx) per call site with q1's tracker, map a keyword string to (section, index)"
    - "per-spike synthetic input for an absent third-party file: our own locators in the scratchpad exercise the code path, never committed"

key-files:
  created:
    - .planning/spikes/007-locate-997-training/q4_strings.py
    - .planning/spikes/007-locate-997-training/q5_tables.py
    - .planning/spikes/007-locate-997-training/q6_callgraph.py
  modified:
    - .planning/spikes/007-locate-997-training/README.md
    - .planning/spikes/MANIFEST.md
    - .planning/spikes/007-locate-997-training/q2_tickrule.py
    - .planning/spikes/007-locate-997-training/q1_timebase.py

key-decisions:
  - "Spike 007 verdict PARTIAL (fix round 1, orchestrator ruling): D-03 asks for the tick rate and the training rule; the tick rate is located, the #263-1 TACP accrual is not. The plan's formula (q2 ALL PASS, q3 ALL PASS, q4 11 of 12) alone would read VALIDATED. Other caveats: q4 keywords chosen by reading the text, UFO2P get_text recovery 74.4% < 80%"
  - "TACP speed labels located: Pause 0, Slow 1, Normal 2, Double 4 (no Quadruple), get_text section 36 in func_000A7490"
  - "Both get_text tables have 52 slots; research's '50 sections' is the dump loop's bound"
  - "Research's table reach (UFO2P 1,471) needs code references up to 64 bytes before a pointer run (record bases); the strict rule of callgraph.py gives 1,429. Plan 07-22 decides the rule"
  - "Owner received the #997 report and asked for a draft comment; the draft stays in the chat, the owner posts by hand"

patterns-established:
  - "A wait-skip style claim pins its found set by equality and gets its own planted run"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "q4: get_text tables decoded, recovery rate per EXE, TACP speed labels, 11 of 12 sample items with an entry row; planted run fails"
    requirement: "DEC-01"
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/007-locate-997-training/q4_strings.py (ends '2 FAILED': two findings; 'q4 found 11 of 12'); --plant exit 1"
        status: pass
    human_judgment: false
  - id: D2
    description: "q5: CD and installed data objects identical by VA (380/386, 605/608 pages); per-table OpenApoc check skipped (headers absent)"
    requirement: "DEC-01"
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/007-locate-997-training/q5_tables.py (ALL PASS, SKIP headers); --plant exit 1"
        status: pass
    human_judgment: false
  - id: D3
    description: "q6: direct edges equal CallIndex; research Q1 reachability reproduced in both EXEs; planted run fails"
    requirement: "DEC-01"
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/007-locate-997-training/q6_callgraph.py (ALL PASS); --plant exit 1"
        status: pass
    human_judgment: false
  - id: D4
    description: "Verdict PARTIAL (D-03) with the formula reading and the consequence for Phase 7; MANIFEST idea block and 007 row"
    requirement: "DEC-01"
    verification:
      - kind: other
        ref: "grep '^verdict: PARTIAL$' README.md; grep '^| 007 ' MANIFEST.md"
        status: pass
    human_judgment: true
    rationale: "The verdict applies D-03's definition over the plan's formula (orchestrator ruling); the verifier and owner judge it"
  - id: D5
    description: "#997 report delivered to the owner at the blocking checkpoint; nothing posted"
    verification: []
    human_judgment: true
    rationale: "The owner's receipt is a human act; quoted below"

duration: 73min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 08: Spike 007 part 2 (strings, tables, call graph, verdict) Summary

**Spike 007 closed as PARTIAL (D-03: the tick rate is located, the #263-1 TACP accrual is not;
the plan's formula alone would read VALIDATED). The UI-text route through get_text was measured on both EXEs.
Recovery is 74.4% for UFO2P and 81.0% for TACP, and 11 of 12 sampled Tier 2-4 items get an entry
row. The TACP speed labels are located (Pause 0, Slow 1, Normal 2, Double 4). The CD and
installed data objects are page-identical by VA except for 9 pages. q6 reproduces research's
reachability exactly once table runs count references to record bases. The owner has the #997
report and asked for a draft comment.**

Execution context nonce: bba450d10c530859

## Performance

- **Duration:** about 73 min (incl. the wait at the owner checkpoint)
- **Started:** about 2026-10-27T16:30Z
- **Checkpoint:** 2026-10-27T17:17Z
- **Completed:** 2026-10-27T17:43Z
- **Tasks:** 3 (2 auto + the owner checkpoint)
- **Files modified:** 7

## Accomplishments

- q4: both `get_text` tables decode self-consistently with 52 slots.
  - UFO2P fills all 52; TACP fills 21.
  - The call sites are 997 in 180 rows (UFO2P) and 315 in 88 rows (TACP), matching research's
    caller counts.
  - Fully recovered (section, index): UFO2P 74.4%, below the 80% target (a finding); TACP 81.0%.
  - Three TACP sites name indexes that exist only in UFO2P's numbering (shared code).
- TACP speed labels: `func_000A7490`, get_text section 36, indexes 0-3, each under a compare of
  `D_000E6C24` with 0 / 1 / 2 / 4. This fills the TACP gap in the #997 lead.
- Sample: 11 of 12 items get an entry row. The miss is #263-4 (chrysalis: section-only sites).
  #265-13's entry (the recruit message) is weak.
- q5: the CD builds come from cd.iso in memory, and their size and SHA-1 match `[[cd_builds]]`.
  - The data objects have the same base and size in both builds.
  - Identical pages: 380/386 for UFO2P (258 bytes differ) and 605/608 for TACP (190 bytes).
  - The per-table claim was skipped because `build/openapoc-extractors/` is absent. It was
    exercised with a synthetic header of our own two locators.
- q6: the own direct edges equal CallIndex (5,288 / 4,885).
  - Reach from `main_` matches research exactly: direct 1,128 / 1,224; with pointers 1,412 /
    1,479; with tables 1,471 / 1,479.
  - The table numbers need a 64-byte record lead-in. The strict rule gives 1,429 for UFO2P.
- README: the verdict section with the formula inputs and caveats, and the consequence for
  Phase 7. MANIFEST: the idea block and the 007 row.

## Task Commits

1. **Task 1: Tracer - q4_strings.py**: `97c33f4` (spike)
2. **Ruling (07-02 re-review): pin wait-skip guards, retag the lead**: `6ab9c34` (spike)
3. **Task 2: q5, q6, verdict, MANIFEST**: `7c9a85b` (spike)
4. **Ruling: q1 chain detail text**: `6a750da` (spike)
5. **Ruling: per-interrupt adder call tagged hand-read in q1's text**: `601d42d` (spike)
6. **Task 3: owner checkpoint**: no commit. The report was delivered in the checkpoint return.

The tracer gate for Task 1 ran in interactive end-of-phase mode with an automated-only verify.
The verify was re-run and passed before Task 2.

## Owner checkpoint (Task 3)

The owner's reply, relayed by the orchestrator on 2026-10-27: **"997 report received" + "draft a
comment"**.

The report gave these addresses (installed build):
- UFO2P:
  - frame loop `func_00010940` (busy-wait `0x00011127..0x00011174`);
  - clock `func_0004AB30` (compare with 36 at `0x0004AB59`);
  - speed `D_000D4D58`, accumulator `D_000D4D6E`, s/m/h `D_000D4D6C`/`D_000D4D6A`/`D_000D4D68`;
  - setters `func_00050920`/`00050970`/`000509C0`/`00050A20`/`00050A80`/`00050AE0`;
  - labels in `func_00052150` (get_text 38/43-46);
  - readers `func_00011430` (28 callers) and `func_00010940`;
  - no-wait guards `D_000D4D5C`, `D_00183BAC`;
  - sound-library BIOS chain `func_000C9099`, `func_000C3692`, `func_000C2F1F`,
    `func_000C3035`/`func_000C33BA`, `func_000C35C8`.
- TACP:
  - frame step `func_000116B0` (busy-wait `0x00011909..0x00011959`) and battle loop
    `func_00010EE0`;
  - clock `func_0003D160` (compare with 36 at `0x0003D184`);
  - speed `D_000E6C24`, accumulator `D_000E6C36`, s/m/h `D_000E6C34`/`D_000E6C32`/`D_000E6C30`;
  - labels in `func_000A7490` (get_text 36/0-3);
  - readers `func_00011500` (35 callers) and `func_000116B0` (10 callers);
  - wait-skip globals `D_000E6D64`, `D_001B7BAC`, `D_0027A0EB`;
  - chain `func_000CC3A9`, `func_000C6386`, `func_000C5C13`, `func_000C5D29`/`func_000C60AE`,
    `func_000C62BC`.
- Matched code backs it: no. None of these functions is in either status.csv; re-checked.

The draft comment the owner asked for was written in the executor's return message only. It is
not in any file and was not posted.

**Verification (read-only, F35 wording).**
- `git log d73427f..HEAD` holds other plans' commits and merges as well. This executor's own
  commits are only the five spike(007) commits above, plus this SUMMARY.
- No network command (`git push`, `gh`, curl/wget), no docker and no subagent was run by this
  executor.

## Files Created/Modified

- `.planning/spikes/007-locate-997-training/q4_strings.py`: the get_text route, the recovery
  rate, the TACP speed labels and the 12-item sample (`--plant`).
- `.planning/spikes/007-locate-997-training/q5_tables.py`: the CD builds from cd.iso, data-object
  identity, the header-driven table identity (`--plant`, `--headers`, `--game`).
- `.planning/spikes/007-locate-997-training/q6_callgraph.py`: direct, pointer and table edges,
  the CallIndex check and research reach (`--plant`).
- `.planning/spikes/007-locate-997-training/README.md`: q4-q6 results, the TACP labels in the
  lead, the verdict, the consequence, planted runs, the trail and the retagged lead.
- `.planning/spikes/MANIFEST.md`: `### mechanics-first-decompilation` idea block and the 007 row.
- `.planning/spikes/007-locate-997-training/q2_tickrule.py` (outside files_modified; ruling):
  guard sets pinned and `--plant-guards` added.
- `.planning/spikes/007-locate-997-training/q1_timebase.py` (outside files_modified; ruling):
  the chain detail text and docstring.
- Gitignored outputs: `build/spike007-q1.out`, `-q2.out`, `-q2-plant-guards.out`, `-q3.out`,
  `-q4.out`, `-q4-plant.out`, `-q5.out`, `-q5-plant.out`, `-q6.out`, `-q6-plant.out`.

## Decisions Made

- Keywords for the sample were chosen by reading the text blob privately, the way a tier drafter
  would. The README says so, and "found" is defined as "an entry row", not "the rule".
- q4's table extent runs to the next code-referenced address or the first nonzero slot without a
  fixup.
- A recovered pair past its section's end is reported, not failed: it is TACP shared code.
- The q5 cross-EXE rule requires identity in every EXE a span maps into. The headers do not say
  which EXE a span belongs to.
- q6's table rule uses a 64-byte lead-in, chosen by trying 0-128 (20-64 reproduce research). The
  strict rule's reach is printed beside it.

## Deviations from Plan

### Orchestrator rulings applied

**1. Orchestrator ruling F35: the Task 3 verification wording**
- The check "git log holds only the spike commits of plans 07-02 and 07-08" was read as "this
  executor made no commit besides its spike commits". Main took the wave-2 merges and other
  plans' commits during this plan.
- Checked read-only: five spike(007) commits by this executor; no network command.

**2. Orchestrator ruling 07-08 notes (07-02 re-review tag corrections), applied before the verdict**
- Found during: before Task 2's verdict.
- Fixes:
  - q2 `wait-skip-guards` now pins the guard sets by equality: UFO2P adds `D_00183BAC`; TACP's
    three globals are pinned.
  - New `q2 --plant-guards` fails in both EXEs (2 FAILED).
  - README: the per-interrupt adder call is tagged [hand], in the lead, in the q1 bullet and in
    q1's detail text and docstring.
  - "No 36 Hz or 144 Hz game timer" is tagged [derived].
  - The guard tags say "pinned since plan 07-08", and the trail records all of this.
  - The 07-02 SUMMARY was not edited.
- Files modified outside files_modified: `q2_tickrule.py`, `q1_timebase.py`.
- Commits: `6ab9c34`, `6a750da`, `601d42d`.
- Verification: q1 and q2 ALL PASS; their plants exit 1; q3 ALL PASS.
- The owner relay quoted the current README lead, not the plan's "18.2065 Hz" wording.

### Auto-fixed Issues

**3. [Rule 1 - Bug] Research's "50 sections" corrected to 52 slots**
- Found during: Task 1.
- Issue: the plan said to assert 50 UFO2P sections. The table has 52 pointer slots and sections
  50 and 51 are called. 50 is the dump loop's bound.
- Fix: EXPECTED `slots: 52` ("this spike") plus `dump_bound: 50` (research's number, verified).
- Note: q2's `get-text-sections 50 of 50` checked only the first 50; it is left as is.
- Committed in: `97c33f4`.

**4. [Rule 1 - Bug] q6 table edges: record lead-in**
- Found during: Task 2.
- Issue: the strict [first slot, last slot + 4) rule wired 3 / 2 runs and reached 1,429 UFO2P
  rows, against research's 10 / 8 runs and 1,471.
- Fix: count references up to 64 bytes before a run, because code addresses record bases. This
  reproduces research exactly. The strict-rule numbers are kept as an INFO line.
- Consequence: plan 07-22 decides this rule for `callgraph.py`.
- Committed in: `7c9a85b`.

**5. [Rule 2 - Missing critical] q5 header-independent claims and a synthetic-header self-test**
- Issue: with no headers, q5 as planned would only print SKIP, and its plant could not be
  shown to fail.
- Fix: added the `cd-build` and `data-object-identity` claims, which the no-header plant fails.
  The header path was run with a scratchpad header of our own two locators; this run exposed
  and fixed a "match in either EXE" flaw.
- Committed in: `7c9a85b`.

---

**Total deviations:** 2 orchestrator rulings applied; 3 auto-fixed (2 bug, 1 missing critical).
**Impact:** the guard pins and retags make the #997 evidence classes exact before the owner
relay. The other changes record measured facts that differ from research. There is no scope creep
beyond the q1/q2 edits the ruling required.

## Issues Encountered

- OpenApoc extractor headers were absent (`build/openapoc-extractors/` does not exist), so
  research Q3's per-table counts (35 + 12, 23 / 10 with refs) remain research's measurement.
- q4's default run exits 1 by design, with two findings (UFO2P recovery 74.4%, item #263-4). The
  plan's verify accepts `N FAILED`.

## Done gate

- `uv run pytest -q`: 3058 passed, 38 skipped. No new tests and no new skip reasons.
- `uv run ruff check .`: green.
- No container step in this plan.

## User Setup Required

None.

## Next Phase Readiness

- 07-22 (Tier 1) needs to:
  - close the TACP accrual of #263-1 through the call graph;
  - decide the table-edge record lead-in.
- 07-25 / 07-28 / 07-32 can use q4's recipe (`decode_table`, `call_sites`, `search`) for entries
  and add the call graph for list-only and text-less items.
- The OpenApoc #997 comment is the owner's to post by hand.

## Self-Check: PASSED

- Created files exist: q4_strings.py, q5_tables.py and q6_callgraph.py.
- Commits 97c33f4, 6ab9c34, 7c9a85b, 6a750da and 601d42d are ancestors of HEAD.

## Fix round 1

Orchestrator fix round after the task review. There were two Important findings.

1. **Verdict label.**
   - D-03 (07-CONTEXT.md, the owner's binding decision) defines VALIDATED as strings and xrefs
     locating the tick rate and the training rule. The #263-1 TACP accrual is not located.
   - Ruling: D-03 outranks the plan's formula.
   - Changes: the README frontmatter, the intro, the Verdict section and the MANIFEST 007 row now
     say **PARTIAL**, with the reason. They note that the formula (q2 and q3 ALL PASS, q4 11 of
     12) alone would read VALIDATED. The Consequence section is unchanged: call-graph walking,
     the PARTIAL remedy, is done in 07-22. The verdict text in this SUMMARY is corrected too.
2. **An overclaim in the #997 lead.**
   - The [derived] sentence said the 36-unit clock is called only from frame rows that wait on
     the BIOS tick. That is true for UFO2P only.
   - In TACP, `func_000B6E50` also calls the clock and q2 finds no wait there. q2's pass
     condition is `bool(waits)`: at least one caller waits.
   - The lead now says:
     - The game programs no 36 Hz or 144 Hz timer: the only PIT programming is in the sound
       library [script: q1 `pit-int8-sites`].
     - Who calls the 36-unit clock [script: q2 `paces-on-bios-tick` lists the callers and passes
       when at least one of them busy-waits on the BIOS tick]: in UFO2P, only the frame loop
       `func_00010940`, which waits on the tick. In TACP, the frame step `func_000116B0`, which
       waits, and `func_000B6E50`, in which q2 finds no BIOS-tick wait. How often
       `func_000B6E50` runs, and so whether it advances battle time at another pace, is not
       checked [open].

The q2 lines this relies on (re-run, q2 ALL PASS):

```
PASS UFO2P.EXE paces-on-bios-tick rows calling the clock [0x00010940]; busy-wait on int386 0x1A [0x00010940:0x00011127..0x00011174]
PASS TACP.EXE tacp-paces-on-same-bios-tick rows calling the clock [0x000116B0 0x000B6E50]; busy-wait on int386 0x1A [0x000116B0:0x00011909..0x00011959]
```

The draft OpenApoc comment from the checkpoint resume said there is no 36/144 Hz game timer
because the clock "is called only from the frame code that waits on the BIOS tick". That sentence
carries the same overclaim. The corrected wording goes to the owner through the orchestrator; the
draft was never in a file.

Commits: `fd7d973` (README, MANIFEST) and the docs(07-08) commit of this section.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
