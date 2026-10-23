---
phase: 05-split-and-first-matches
plan: 01
subsystem: tooling
tags: [objdiff, omf, elf, spike, d-01, d-02, d-19]

requires:
  - phase: 04-compiler-identification
    provides: "reverseapoc cc under wibo (wcc386@10.6, `*  wcc386@10.6  -4r -s -fpi`), runtime.csv rows, omf.read_object"
  - phase: 03-le-round-trip
    provides: "le.LE.load_flat(relocate=False) and le.LE.fixups()"
provides:
  - "Spike 005 verdict VALIDATED: objdiff-cli 3.8.2 scores a Watcom OMF object converted to ELF32 at 100.0 against an LE cut (__CMain, both EXEs)"
  - "Pinned writer shape for SPL-07/SPL-08: `_TEXT` section names, REL implicit addends, TH addend rule, PC32 for calls, one name per address"
  - "Recorded objdiff blind spot (wrong 2nd relocation of one instruction scores 100.0), so the SPL-09 relocation check is the gate"
  - "The 8-name address map for cmain386 in both EXEs, and config/<exe>/symbols.csv named as the general mechanism"
affects: [05-02, 05-04, 05-06, 05-08, 05-09, 05-16, 05-18]

actuals:
  tokens: 10840
  tasks: 2
  commits: 2
plan_head_before: 688168c02902006e43f072efe6e0b8f6f45e300b
plan_head_after: d8c73c0df89e50ca290f8439c90373f54fe469d2

tech-stack:
  added: []
  patterns:
    - "Spike-local ELF32 REL writer in stdlib struct, one named constant per ELF field"
    - "Target cut: load_flat(relocate=False) bytes, LE off32 -> R_386_32 (field 0), call rel32 -> R_386_PC32 (field -4)"

key-files:
  created:
    - .planning/spikes/005-objdiff-omf-elf/mkelf.py
    - .planning/spikes/005-objdiff-omf-elf/spike.py
    - .planning/spikes/005-objdiff-omf-elf/README.md
  modified:
    - .planning/spikes/MANIFEST.md

key-decisions:
  - "Spike 005 verdict VALIDATED (D-02, D-19): objdiff-cli 3.8.2 shows 100.0 for __CMain in UFO2P.EXE and TACP.EXE with only the address-to-name map; the hybrid pipeline stays"
  - "objdiff is a score and viewer, not the gate: a wrong symbol on the 2nd relocation of one instruction still scores 100.0 (P3), so the SPL-09 relocation check gates matches"
  - "Code sections are named `_TEXT` on both sides; a `.text` target leaves the function unpaired (P4)"

patterns-established:
  - "objdiff one-shot: `objdiff-cli diff -1 <target.o> -2 <base.o> -o - <symbol>`, match_percent from left.symbols (left = target); absent or no match_percent = unpaired"

requirements-completed: [SPL-07, SPL-08]

coverage:
  - id: D1
    description: "cmain386 pair (CMAIN386.C via reverseapoc cc, converted to ELF32) scores match_percent 100.0 for __CMain against the LE cut in UFO2P.EXE and TACP.EXE"
    requirement: SPL-08
    verification:
      - kind: integration
        ref: "docker compose run --rm build bash -lc \"uv sync --locked && uv run python .planning/spikes/005-objdiff-omf-elf/spike.py --plants\" (build/spike005/all.out, ALL PASS)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Plants P1 (wrong call symbol, 99.80769), P2 (wrong addend, 99.80769), P3 (wrong 2nd relocation, 100.0; control 98.75) and P4 (.text, unpaired) recorded"
    requirement: SPL-07
    verification:
      - kind: integration
        ref: "spike.py --plants in the container (build/spike005/all.out)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Spike record: README with Given/When/Then, name map, objdiff command, D-02/D-19 verdict VALIDATED; MANIFEST idea and 005 row"
    verification:
      - kind: other
        ref: "grep -qE '^verdict: (VALIDATED|PARTIAL)$' README.md && grep -q symbols.csv README.md && grep -q '^| 005 ' MANIFEST.md"
        status: pass
    human_judgment: false
  - id: D4
    description: "CMAIN386.C read in place only; no CMAIN386 file tracked; no game or Watcom bytes in output or record"
    verification:
      - kind: other
        ref: "git ls-files | grep -qi cmain386 (no match)"
        status: pass
    human_judgment: true
    rationale: "The prohibition on printing bytes/source/disassembly is a judgment check over the output and README text; the git check covers only the copy rule"

duration: 10min
completed: 2026-10-23
status: complete
---

# Phase 5 Plan 01: objdiff-on-converted-OMF spike Summary

**objdiff-cli 3.8.2 scores Watcom's own CMAIN386.C, compiled with `reverseapoc cc` and converted OMF->ELF32, at match_percent 100.0 for `__CMain` against a target ELF cut from the LE in both UFO2P.EXE and TACP.EXE. The only addition was an 8-name address map, so spike 005 is VALIDATED and the hybrid pipeline stays.**

Execution context nonce: 135413bf01d849c2

## Performance

- **Duration:** about 10 min
- **Started:** 2026-10-23T23:26:52Z
- **Completed:** 2026-10-23T23:36:48Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Spike-local `mkelf.py`: an ELF32 REL writer, an OMF->ELF converter using the TH addend rule, and an LE target cut built from `load_flat(relocate=False)` and `fixups()` only.
- `spike.py` compiles CMAIN386.C in place under the `*` rule (cflags.txt:37). For each EXE it checks the 79-byte row, 0 differing bytes outside fixup fields, 4 + 5 OMF fixups and 5 LE fixups, resolves the 8 linker names, and runs objdiff-cli. The result is 100.0 for both EXEs.
- Plants record what objdiff catches (wrong call symbol, wrong addend, wrong 1st relocation) and what it misses (wrong 2nd relocation of one instruction scores 100.0). A `.text` target leaves `__CMain` unpaired.
- README verdict: VALIDATED by D-02 and D-19. The MANIFEST has the `split-and-first-matches` idea and the 005 row.

## PASS lines (container, `spike.py --plants`, build/spike005/all.out)

```
PASS CMAIN386.C rule cflags.txt:37 * wcc386@10.6 -4r -s -fpi
PASS CMAIN386.C compile wcc386@10.6 exit 0 normalized 0f4549d1ae2e9b80deb3489d389993cb353df0f9
PASS UFO2P.EXE row cmain386 rows 1
PASS UFO2P.EXE row-start 0x000c5c9c
PASS UFO2P.EXE size _TEXT 79 row 79
PASS UFO2P.EXE bytes 0 differ outside fixup fields
PASS UFO2P.EXE omf-fixups self-relative 4 segment-relative 5
PASS UFO2P.EXE le-fixups 5 in range, all off32 True
PASS UFO2P.EXE call-opcodes 4 self-relative fields follow call rel32, no LE fixup
PASS UFO2P.EXE le-coverage every segment-relative field has its LE fixup and every LE fixup in range is ours
PASS UFO2P.EXE name-map 8 names: __ASTACKPTR 0x0013bba8 __ASTACKSIZ 0x0013bba4 __CommonInit_ 0x000c9360 ____Argc 0x00249968 ____Argv 0x0024996c exit_ 0x000c01e1 main_ 0x00010010 stackavail_ 0x000c9357
PASS UFO2P.EXE objdiff __CMain match_percent 100.0
PASS UFO2P.EXE P1-wrong-call-symbol exit_->main_ match_percent 99.80769 (expect below 100)
PASS UFO2P.EXE P2-wrong-addend R_386_32 at 0x000c5ca2 addend 4 match_percent 99.80769 (expect below 100)
PASS UFO2P.EXE P4-section-.text target section .text, base _TEXT: match_percent None (expect unpaired)
PASS TACP.EXE row cmain386 rows 1
PASS TACP.EXE row-start 0x000c7915
PASS TACP.EXE size _TEXT 79 row 79
PASS TACP.EXE bytes 0 differ outside fixup fields
PASS TACP.EXE omf-fixups self-relative 4 segment-relative 5
PASS TACP.EXE le-fixups 5 in range, all off32 True
PASS TACP.EXE call-opcodes 4 self-relative fields follow call rel32, no LE fixup
PASS TACP.EXE le-coverage every segment-relative field has its LE fixup and every LE fixup in range is ours
PASS TACP.EXE name-map 8 names: __ASTACKPTR 0x002b3e54 __ASTACKSIZ 0x002b3e50 __CommonInit_ 0x000cc54a ____Argc 0x00336bf8 ____Argv 0x00336bfc exit_ 0x000c23a4 main_ 0x000102a0 stackavail_ 0x000ca446
PASS TACP.EXE objdiff __CMain match_percent 100.0
PASS TACP.EXE P1-wrong-call-symbol exit_->main_ match_percent 99.80769 (expect below 100)
PASS TACP.EXE P2-wrong-addend R_386_32 at 0x000c791b addend 4 match_percent 99.80769 (expect below 100)
PASS TACP.EXE P4-section-.text target section .text, base _TEXT: match_percent None (expect unpaired)
PASS synthetic P3-control-1st-reloc symbol at field 12 differs: match_percent 98.75 (expect below 100)
PASS synthetic P3-blind-spot-2nd-reloc symbol at field 16 (imm32, 2nd reloc of one instruction) differs: match_percent 100.0 (expect exactly 100.0)
ALL PASS
```

## Name map (D-19)

| name | UFO2P address | TACP address |
|---|---|---|
| `__ASTACKSIZ` | 0x0013BBA4 | 0x002B3E50 |
| `__ASTACKPTR` | 0x0013BBA8 | 0x002B3E54 |
| `____Argc` | 0x00249968 | 0x00336BF8 |
| `____Argv` | 0x0024996C | 0x00336BFC |
| `stackavail_` | 0x000C9357 | 0x000CA446 |
| `__CommonInit_` | 0x000C9360 | 0x000CC54A |
| `main_` | 0x00010010 | 0x000102A0 |
| `exit_` | 0x000C01E1 | 0x000C23A4 |

Each name is resolved from the pair's own fields:
- A call field F names `F + 4 + rel32 - stored - displacement`.
- A data field names the target_va of the LE fixup at F, minus stored and displacement.

The map holds one name per address. The general mechanism is the optional committed `config/<exe>/symbols.csv` (`address,name,kind`), which comes in plans 05-04 and 05-16.

## objdiff command as run

`objdiff-cli diff --help` (3.8.2) lists these options: `-1, --target`, `-2, --base`, `-o, --output` (`-` = stdout) and `--format` (default json).

```
objdiff-cli diff -1 build/spike005/<exe>/target.o -2 build/spike005/<exe>/base.o -o - __CMain
```

`match_percent` comes from the `__CMain` entry in `left.symbols`, where left is the target. The default `functionRelocDiffs=name_address` was left unchanged.

## Verdict

**VALIDATED** (D-02, D-19). objdiff loads both objects and reports 100.0 for `__CMain` in both EXEs. The target side needed only the address-to-name map, and D-19 counts that as normal relocation mapping, so nothing here is a workaround. `_TEXT` naming and REL addends in the field are writer rules, not workarounds. Plant P3 is why the KKND-style relocation check (SPL-09, plan 05-09) is the gate. No INVALIDATED checkpoint was needed, so wave 2 can proceed.

## Task Commits

1. **Task 1: Tracer, UFO2P cmain386 pair at 100%** - `c2ae8cc` (feat)
2. **Task 2: Both EXEs, plants, name map record, verdict** - `d8c73c0` (docs)

## Files Created/Modified

- `.planning/spikes/005-objdiff-omf-elf/mkelf.py`: `write_elf`, `from_omf`, `cut_target`, `function_parts`, ELF field constants
- `.planning/spikes/005-objdiff-omf-elf/spike.py`: `EXPECTED`, `--exe`, `--plants`, the name map, plants P1-P4
- `.planning/spikes/005-objdiff-omf-elf/README.md`: spike record with Given/When/Then, results, plants and verdict
- `.planning/spikes/MANIFEST.md`: `split-and-first-matches` idea and the 005 row

## Decisions Made

- Verdict VALIDATED, not PARTIAL. Per D-19 the name map is normal mapping. My own writer bug (below) was not an objdiff workaround.
- Added a P3 control: a wrong symbol on the 1st relocation of the same instruction scores 98.75. This shows the P3 100.0 is a real blind spot, not a check that never looks at relocations.
- The compile claim also resolves the cflags rule (`cflags.txt:37 * wcc386@10.6 -4r -s -fpi`), because the cc `OK` line names only `wcc386@10.6`, not the flags.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ELF data encoding constant was wrong**
- **Found during:** Task 1 (first objdiff run)
- **Issue:** `ELFDATA2LSB` was set to 2, which is the MSB value. objdiff read the header big-endian and refused the object: `Invalid ELF section header entry size`.
- **Fix:** `ELFDATA2LSB = 1`.
- **Files modified:** .planning/spikes/005-objdiff-omf-elf/mkelf.py
- **Verification:** both objects load and `__CMain` scores 100.0.
- **Committed in:** c2ae8cc

**2. [Rule 2 - Missing evidence] Compile claim names the cflags rule**
- **Found during:** Task 1
- **Issue:** the `OK` line carries only `wcc386@10.6`, so it did not show that `-4r -s -fpi` applied.
- **Fix:** an added `rule` PASS line from `cflags.select_rule(load_cflags(), SOURCE)`.
- **Files modified:** spike.py
- **Committed in:** c2ae8cc

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing evidence)
**Impact on plan:** none on scope. Both make the spike's claims correct and evidenced.

## Issues Encountered

None beyond the deviations above.

## Verification

- Task 1 verify: container run for UFO2P gave `ALL PASS` and `__CMain match_percent 100.0`. `uv run ruff check .planning/spikes/005-objdiff-omf-elf/` passed.
- Task 2 verify: container run with `--plants` gave `ALL PASS`, with 100.0 PASS lines for both EXEs. The verdict, `symbols.csv` and `| 005 ` greps pass. The spike files are tracked, and no CMAIN386 file is tracked.
- `uv run ruff check .` passed. Host `uv run pytest -q` gave 1038 passed, 7 skipped, run with no container active.

## User Setup Required

None.

## Next Phase Readiness

- The verdict is not INVALIDATED, so wave 2 (production omf2elf 05-02, target writer 05-06/05-08, symbols.csv 05-04) can start on the pinned shape:
  - `_TEXT` sections
  - REL addends in the field
  - the TH addend rule
  - PC32 for calls
  - one name per address
- Plan 05-18 re-proves this pair through the production modules.

## Self-Check: PASSED

- FOUND: .planning/spikes/005-objdiff-omf-elf/mkelf.py, spike.py, README.md; .planning/spikes/MANIFEST.md has the 005 row
- FOUND: c2ae8cc, d8c73c0 (ancestors of HEAD); `git rev-list --count 688168c..HEAD` = 2

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-23*
