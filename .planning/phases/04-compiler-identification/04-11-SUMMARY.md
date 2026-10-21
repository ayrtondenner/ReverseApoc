---
phase: 04-compiler-identification
plan: 11
subsystem: docs
tags: [watcom, wibo, d-03, compiler-identification, flags, cflags, toolchain, cid-05]

requires:
  - phase: 04-compiler-identification (plan 04-06)
    provides: install-watcom 10.5 decodes and pins the 567,558-byte BINW compiler
  - phase: 04-compiler-identification (plan 04-07)
    provides: committed config/ufo2p|tacp/runtime.csv and the libmatch summary block
  - phase: 04-compiler-identification (plan 04-09)
    provides: cppscan verdict lines (full `C (wcc386): ` form)
  - phase: 04-compiler-identification (plan 04-10)
    provides: probe calibrate / probe scan, the seven evidence lines, the sized struct-copy reading (-4r)
provides:
  - "10.5 data migration on the main checkout (install-watcom 10.5 --force) and 10.5 calibration cells"
  - "build/gate/04-native-vs-wibo.txt: D-03 normalized equal for 10.5, 10.6, 11.0"
  - "build/gate/04-evidence/01..05 logs (check-watcom, libmatch, probe calibrate, probe scan, cppscan)"
  - "spike 004 wibo-watcom (VALIDATED) and its MANIFEST row"
  - "docs/toolchain.md Result, per-EXE Flags table, C verdict, confirmed disc/wibo facts, version pin"
  - "config/cflags.txt default `*  wcc386@10.6  -4r -s -fpi`, pinned to the docs by two hygiene tests"
  - "docs/matching.md per-EXE rows, Known idioms, Pitfalls; docs/learnings.md Phase 4 entries"
affects: [04-12, phase-05 cflags per-glob rules, phase-05 first matches]

actuals:
  tokens: 12366
  tasks: 3
  commits: 4
plan_head_before: 1cfbaed9cec8860b9391fac8825b679466c51865
plan_head_after: 48df72042c129ce6e5eb640f77ea603d448bf1b6

tech-stack:
  added: []
  patterns:
    - "A doc claim about the build default is pinned by a test that parses config/cflags.txt and requires its spec and flags in the docs"
    - "Every Result/Flags cell cites the reverseapoc command whose output (logged under build/gate/04-evidence/) reproduces it"

key-files:
  created:
    - .planning/spikes/004-wibo-watcom/README.md
  modified:
    - .planning/spikes/MANIFEST.md
    - docs/toolchain.md
    - docs/matching.md
    - docs/learnings.md
    - config/cflags.txt
    - tests/test_hygiene.py
    - probe/README.md

key-decisions:
  - "Game-code compiler written as a tie: 10.6 (10.5 byte-identical on the probe in all 10 flag sets) with 11.0 tied at -4r on the decisive idioms; 11.0 is 'candidate, evidence pending: first Phase 5 matches'. Linked runtime library 10.6, no mix, reported separately (D-07, D-10)"
  - "config/cflags.txt default is `*  wcc386@10.6  -4r -s -fpi`: 10.6 is the version consistent with both the probe and the linked runtime; -4r from the register-convention and 5-dword struct-copy evidence; -s because only 40/32 functions call __CHK; -fpi explicit (EMU387 row; the probe object is identical with and without it)"
  - "-s kept in the default despite the ruling's example 'not -s if __CHK calls are present': the measured evidence (40/32 __CHK sites against at least 714/801 multiply-called functions in non-library code) says stack checks are off for most code, so the __CHK functions become per-glob exceptions in Phase 5"
  - "Memory model -mf recorded as 'consistent (wcc386 default), not a flag proof' and left out of the rule; -bt=dos stays wrapper-owned"

patterns-established:
  - "Docs pin: test_cflags_default_rule_is_documented ties the `*` rule to toolchain.md and matching.md"

requirements-completed: [CID-05, CID-01]  # copied from the plan; REQUIREMENTS.md not marked: requirements.ready-ids blocks both until 04-12 (which also declares them) has a SUMMARY

coverage:
  - id: D1
    description: "10.5 reinstalled from the owner's ISO with the decoded compiler; check-watcom 10.5 10.6 11.0 all OK"
    requirement: CID-01
    verification:
      - kind: manual_procedural
        ref: "uv run reverseapoc install-watcom 10.5 --force; uv run reverseapoc check-watcom 10.5 10.6 11.0 (build/gate/04-evidence/01-check-watcom.log: 8/8/10 ok, exit=0)"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-03: probe/cg_basic.c native vs wibo, normalized SHA-1 equal for 10.5, 10.6 and 11.0"
    requirement: CID-01
    verification:
      - kind: integration
        ref: "grep -qE '^D-03: normalized equal for ' build/gate/04-native-vs-wibo.txt && ! grep -q DIFFERENT build/gate/04-native-vs-wibo.txt (plus the per-version check, Task 1 verify)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Spike 004 recorded (VALIDATED) and listed in MANIFEST.md"
    requirement: CID-01
    verification:
      - kind: other
        ref: "git ls-files --error-unmatch .planning/spikes/004-wibo-watcom/README.md && grep -q '^| 004 ' .planning/spikes/MANIFEST.md"
        status: pass
    human_judgment: false
  - id: D4
    description: "toolchain.md records the compiler, runtime library, per-EXE flags and C verdict with the reproducing commands; stale Phase 4 markers gone"
    requirement: CID-05
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_toolchain_records_the_compiler_result"
        status: pass
    human_judgment: true
    rationale: "Whether each cell says no more than its log shows is a reading judgment (checked by hand below); the test pins structure and the absence of stale markers only"
  - id: D5
    description: "config/cflags.txt default rule names the identified compiler@version and the proven flags, documented in toolchain.md and matching.md"
    requirement: CID-05
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_cflags_default_rule_is_documented"
        status: pass
    human_judgment: true
    rationale: "Choosing 10.6 over the tied 11.0 and keeping -s are evidence-weighing decisions (recorded in Decisions Made) that the owner should confirm"
  - id: D6
    description: "matching.md per-EXE rows, Known idioms and Pitfalls; learnings.md Phase 4 entries"
    requirement: CID-05
    verification:
      - kind: other
        ref: "grep -cE '^\\| \\* \\| (UFO2P|TACP)\\.EXE \\| wcc386@' docs/matching.md (prints 2)"
        status: pass
    human_judgment: true
    rationale: "Prose content and wording of the idiom and pitfall entries need a reader's review"

duration: 24min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 11: Main-checkout evidence and the compiler record Summary

**10.5 reinstalled with its decoded compiler, D-03 native vs wibo normalized-equal for 10.5/10.6/11.0 (spike 004 VALIDATED), and docs/toolchain.md now states per EXE: game code Watcom C 10.6 (10.5 byte-identical on the probe, 11.0 tied at `-4r`), linked runtime 10.6, flags `-4r -s -fpi` with per-flag evidence, C (wcc386), all pinned to `config/cflags.txt` by hygiene tests.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-10-21T20:22:24Z
- **Completed:** 2026-10-21T20:46:35Z (SUMMARY written right after)
- **Tasks:** 3 (Task 1 tracer, Task 2 TDD, Task 3 auto)
- **Files modified:** 8 tracked (1 created) plus 6 gitignored logs

## Accomplishments

- `uv run reverseapoc install-watcom 10.5 --force` on the main checkout: `BINW/WCC386.EXE` went from the 65,536-byte stub to the decoded 567,558-byte compiler; check-watcom 10.5 / 10.6 / 11.0: 8 / 8 / 10 ok.
- D-03 logged: raw SHA-1s differ host vs container, normalized SHA-1s equal for every version. 10.5 and 10.6 even give the same raw object on each backend at `-5r -s`.
- The 10.5 calibration cells now exist: 10.5 and 10.6 are byte-identical on the probe in all ten flag sets (`tie:` lines). The scan's consistent set grows from 10 of 20 to 18 of 30 cells (the eight 10.6 cells plus the same eight for 10.5, and 11.0 `-4r -s`, `-4r -s -ox`), in both EXEs.
- docs/toolchain.md: "### Result" table per EXE, "How to reproduce" list, the Flags table (`| Flag | UFO2P | TACP | Evidence | Status |`), the C verdict with signal table and coverage limits, confirmed BINNT-loader and 10.5 decode facts with the `--force` migration, the wibo/D-03 result and wrapper rules, the Watcom C version pin.
- config/cflags.txt: `*  wcc386@10.6  -4r -s -fpi`, with the reasoning in its comment.
- docs/matching.md: two per-EXE rows, Known idioms (calibrated), Pitfalls (wrapper traps and identical library stubs). docs/learnings.md: two dated Phase 4 entries.

## The D-03 log (`build/gate/04-native-vs-wibo.txt`, reproduced)

```
10.5  native sha1 a8959f459c510fe3214c3704bd0cb5b13af582e9 normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  wibo sha1 1c3ad3b57a332f31dd1d488357fd354e5f12571b normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  normalized equal
  native banner: WATCOM C32 Optimizing Compiler  Version 10.5
  wibo banner:   WATCOM C32 Optimizing Compiler  Version 10.5
10.6  native sha1 a8959f459c510fe3214c3704bd0cb5b13af582e9 normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  wibo sha1 1c3ad3b57a332f31dd1d488357fd354e5f12571b normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  normalized equal
  native banner: WATCOM C32 Optimizing Compiler  Version 10.6
  wibo banner:   WATCOM C32 Optimizing Compiler  Version 10.6
11.0  native sha1 538da4b77b57e90c772bb0dd01c80db04e31bc7e normalized 419decf88073e026a0ebfff588ccc3ff1bd5f03c  wibo sha1 7f2f562574abdb9695b6aa687711af0f863cba84 normalized 419decf88073e026a0ebfff588ccc3ff1bd5f03c  normalized equal
  native banner: Watcom C32 Optimizing Compiler  Version 11.0
  wibo banner:   Watcom C32 Optimizing Compiler  Version 11.0
D-03: normalized equal for 10.5, 10.6, 11.0
```

The header lines (not reproduced) name D-03, the two commands, the comparison cflags (`*  wcc386@<v>  -5r -s`, not the game's flags) and the normalization (THEADR and COMENT class 0xE9 dropped).

## Evidence logs (all end `exit=0`)

| Log | Command | Key lines |
|---|---|---|
| 01-check-watcom.log | `uv run reverseapoc check-watcom 10.5 10.6 11.0` | 8 ok / 8 ok / 10 ok, 0 mismatched, 0 known bad |
| 02-libmatch.log | `uv run reverseapoc libmatch UFO2P.EXE`, `... TACP.EXE` | unchanged from 04-07: 121 / 132 ranges, 43,958 / 46,055 bytes (5.60% / 5.79%), 10.6-only 11 / 11, ambiguous 14 / 12 |
| 03-probe-calibrate.log | `uv run reverseapoc probe calibrate --output build/probe/calibration.json` | 30 cells; `tie: <flags>: 10.5 10.6` for all ten flag sets; 11.0 never ties |
| 04-probe-scan.log | `uv run reverseapoc probe scan <EXE> --calibration build/probe/calibration.json` | counts as in 04-10 (unchanged); `consistent: 18 of 30`; eight `ties:` lines (10.5 = 10.6) |
| 05-cppscan.log | `uv run reverseapoc cppscan <EXE>` | both `C (wcc386): ...` (full form), 5 / 3 vtable-shaped runs |

## Docs cells and the log behind each (hand check)

Result table (toolchain.md):

| Cell | Log |
|---|---|
| Game-code compiler: 10.6, 10.5 byte-identical, 11.0 tied at `-4r`; 18 of 30 consistent; no `-3r`, no 11.0 `-5` | 03 (`tie:` lines, 11.0 `-5` rows setcc 0/0), 04 (`consistent:` list, `ties:`) |
| Linked runtime 10.6: 11 rows 10.6 only, 58/51/1 and 62/57/2, no 10.5-only or 11.0-only row, the 11 module names | 02 (`versions ...` lines) |
| Runtime libraries: CLIB3R 106/113, MATH387R 15/19, MATH3R 1, EMU387 1, GRAPH 1; CLIB3S 16, MATH387S 3, MATH3S 1; 3S-only 0 | 02 (`library ...` lines), 04 (`calling convention:`) |
| Coverage: 121 / 132 ranges, 43,958 of 785,117 (5.60%) / 46,055 of 795,983 (5.79%), ambiguous 14 / 12 | 02 (`summary`, `ambiguous`) |
| C or C++ verdict lines, 5 / 3 runs | 05 |

Flags table:

| Row | Log |
|---|---|
| Calling convention: 102 / 113, 0 / 0, 18 / 18 | 04 `calling convention:` |
| `-s`: 40 / 32 calls; blocks 0x00010000 37 / 26, 0x000b0000 3 / 6; 741,159 / 749,928 bytes; probe one `__CHK` per function without `-s` (chk 7 at `-5r`) | 04 `stack checks:` and header line; 03 chk column |
| FPU: EMU387 1, NOEMU387 0, MATH387 15 / 19, MATH3 1 | 04 `fpu:` |
| CPU: setcc_and 30 / 58, movzx 0 / 0; 5-dword rep copies `5+2` x2 / `5` x5 + `5+1` x1; no run of 5+; the 20-23-byte split | 04 `cpu:` and `struct-copy sizes` |
| Memory model: 2 objects, both 32-bit | 04 `memory model:` |
| Evidence table above the Result (non-library counts, loop/switch shapes, `__CHK`) | 04 counts block |

Cells not from a log, each cited where it appears: the "about two more" skipped 5-dword copies per EXE (04-10-SUMMARY fix rounds 1-2, linked in the Flags notes), "13% of PLIB3R C++ code in COMDATs" (04-09), and the `-fpi` object identity (a throwaway compile in `build/d03/fpi/`, normalized `bc730313...` both ways, equal to the calibration's 10.6 `-4r -s` cell).

## Task Commits

1. **Task 1 (tracer): main-checkout evidence and spike record** - `d7573a2` (docs). The logs are gitignored by design and stay under `build/gate/`.
2. **Task 2 (TDD): toolchain.md result and hygiene tests**
   - RED `94cb90c` test(04-11): two failing hygiene tests
   - GREEN `d9b874d` feat(04-11): toolchain.md (and the two matching.md rows, see Deviations)
3. **Task 3: cflags default, matching.md idioms and pitfalls, learnings** - `48df720` (docs; amended once before the SUMMARY to put the entry naming wpack/env/NT/normalized hash first)

**Plan metadata:** the docs(04-11) commit holding this SUMMARY.

## TDD record (Task 2)

- **RED:** `uv run pytest -q tests/test_hygiene.py -k "toolchain_records_the_compiler_result or cflags_default_rule" --junitxml=build/red/04-11-t2.xml` exited 1, 2 failed. `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` (reason `target_test_failed`) for both targets. Semantic assessment: both failed on their planned assertions inside the test body. `test_toolchain_records_the_compiler_result` found all six stale markers in toolchain.md (the plan expected five; the sixth, `To be confirmed in Phase 5:** scan obj2`, was present too). `test_cflags_default_rule_is_documented` failed on `'wcc386@10.6' in <toolchain.md>`. No collection, import or fixture fault.
- **GREEN:** both pass after the toolchain.md rewrite plus the matching.md rows; the whole hygiene file 30 passed, 3 skipped (container-only).
- **REFACTOR:** none.
- **Tracer gate (Task 1):** interactive run, `end-of-phase`, automated-only verify. All four verify commands re-ran green after the Task 1 commit, then Task 2 started.

## Decisions Made

- **Version (ruling applied).** The probe leaves 10.5 = 10.6 (all cells) and 10.6 vs 11.0 tied at `-4r`; the runtime map is 10.6 with no mix. So the docs state the tie, the default names 10.6, and 11.0 is "candidate, evidence pending: the first Phase 5 matches", with what separates them (a function that matches under one version and not the other; loop shape is not decisive in game code). 10.5 is not separated (D-10).
- **`-4r`.** UFO2P and TACP both have 5-dword rep copies and no unrolled 5-dword run; only that size separates `-4` from `-5` on the probe. 10.5 equals 10.6 on the probe's 5-dword copy in every cell, so the reinstall does not change this. Written as "no `-5` evidence", with the caveat.
- **`-s`, and why it departs from the ruling's example.** The ruling said "not -s if __CHK calls are present — follow the measured evidence". The measured evidence: 40 / 32 `__CHK` calls in 741,159 / 749,928 non-library bytes, and a throwaway count (`calltargets.py` in the session scratchpad, not committed; counts only) found 1,330 / 1,377 distinct near-call targets in non-library code, 714 / 801 of them reached from two or more call sites. Stack checks are therefore off for most functions, so the default carries `-s` and the 40 / 32 `__CHK` functions get per-glob rules without `-s` in Phase 5. If the owner reads the ruling literally, the alternative is to drop `-s` from the `*` rule; that would compile hundreds of functions with a `__CHK` prologue they do not have.
- **`-fpi` explicit.** Proven by the EMU387 row (caveat A3) and identical in the object, so writing it costs nothing and documents the FPU mode.
- **Not in the rule:** `-mf` (default, not a flag proof), `-bt=dos` (wrapper-owned), and the candidates `-o*`, `-zp*`, `-zm`, `-fp3`/`-fp5`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] matching.md rows pulled forward into Task 2**
- **Found during:** Task 2 GREEN
- **Issue:** Task 2's own test `test_cflags_default_rule_is_documented` requires the spec in docs/matching.md, but matching.md is a Task 3 file; Task 2's verify (whole hygiene file green) could not pass otherwise.
- **Fix:** the two `| * | <EXE> | wcc386@10.6 | -4r -s -fpi | ...` rows and their note went into the Task 2 GREEN commit; Task 3 wrote the rest of matching.md.
- **Commit:** d9b874d

**2. [Minor] probe/README.md corrected (not in the plan's file list)**
- The "Running the calibration" paragraph said the verb "arrives with plan 04-10"; it now names the verb and says 10.5 is calibrated and byte-identical to 10.6. The controller's notes allowed this.
- **Commit:** 48df720

**3. [Minor] Plan text vs current tools**
- `probe scan` prints seven evidence lines, not five (plan line 113); the docs use all seven.
- `docker compose run` was invoked with `-T` and `MSYS_NO_PATHCONV=1` (Git Bash, no TTY); the command inside is the plan's.

---

**Total deviations:** 1 auto-fixed (blocking), 2 minor. **Impact:** none on scope; every planned artifact exists.

## Issues Encountered

- A stray `python -` in one of my shell lines waited on stdin and timed out; I killed that one process (my own) and re-ran the edit through `uv run python -c`. No file was affected beyond the intended edit.
- `config/watcom.toml`'s 10.5 and 10.6 BINNT notes say "runs BINW/WCC386.EXE (the real LE compiler)". That is stale for 10.5 (the decoded compiler is LX). The manifest is protected, so it was not edited; docs/learnings.md records it for the owner.

## Known Stubs

None. The "not known yet" cells in the Flags table are the D-08 candidates, labelled "candidate, evidence pending" with what would prove each.

## User Setup Required

None. Contributors with a pre-Phase-4 10.5 install run `uv run reverseapoc install-watcom 10.5 --force` once (documented in toolchain.md).

## Next Phase Readiness

- Plan 04-12 can read the D-03 log, the evidence logs and the spike record; CID-01 and CID-05 stay unmarked in REQUIREMENTS.md until 04-12's SUMMARY exists (shared-ID gate).
- Phase 5: the first matches decide 10.6 vs 11.0 at `-4r`, the `-o*`/`-zp*`/`-zm`/`-fp*` candidates, and the per-glob rules without `-s` for the `__CHK` functions.

## Verification

- Task 1 verify (four commands): all exit 0, re-run after the commit (tracer gate).
- Task 2: `uv run pytest -q tests/test_hygiene.py` 30 passed, 3 skipped; the stale-marker grep finds nothing; the flags header appears once.
- Task 3: matching.md row grep prints 2; `grep -v '^#' config/cflags.txt | grep -c 'wcc386@'` prints 1; learnings' newest entry is dated 2026-10-21 and names the wpack tie order, env injection, the NT default target and the normalized hash.
- Host: `uv run pytest -q` 960 passed, 6 skipped (10.5 real tests now run instead of skipping); `uv run ruff check .` clean.
- Container: `docker compose run --rm test` 966 passed; `uv run ruff check .` in the build container clean.

## Self-Check: PASSED

- Files found: .planning/spikes/004-wibo-watcom/README.md, .planning/spikes/MANIFEST.md, docs/toolchain.md, docs/matching.md, docs/learnings.md, config/cflags.txt, tests/test_hygiene.py, probe/README.md, build/gate/04-native-vs-wibo.txt, build/gate/04-evidence/01..05 logs.
- Commits d7573a2, 94cb90c, d9b874d, 48df720 are ancestors of HEAD; `git rev-list --count 1cfbaed..HEAD` = 4 before this SUMMARY; no commit deletes a file.

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
