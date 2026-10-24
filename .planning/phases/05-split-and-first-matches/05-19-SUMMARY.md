---
phase: 05-split-and-first-matches
plan: 19
subsystem: matching
tags: [first-match, tacp, check, objdiff, relocs, land, ninja, spl-13, d-16, d-17, d-18]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-18 the UFO2P match and the procedure (score, units --write-src, lint, check --json); 05-17 check/land; 05-16 committed TACP CSVs; 05-14 the ninja graph"
provides:
  - "src/tacp/u_00054f20.c: func_00055080 of TACP.EXE matched in C89 (first TACP hand match), 10 INCLUDE_ASM stubs"
  - "docs/toolchain.md: TACP row in ### Phase 5 match evidence and the per-candidate state after two matches"
  - "docs/matching.md: both matches use the * default; docs/learnings.md 2026-10-24 TACP entry"
affects: [05-20, phase-06]

actuals:
  tokens: 2491
  tasks: 3
  commits: 2
plan_head_before: 2abb069410f761ebd3ed18899093c3eb0be2142e
plan_head_after: 6a5dc521a56406be464f736f19582135bf9c46ac

tech-stack:
  added: []
  patterns:
    - "A match claim is backed by a mutation probe: a one-token change to the matched C must make check exit 1 (as in 05-18)"

key-files:
  created:
    - src/tacp/u_00054f20.c
  modified:
    - docs/toolchain.md
    - docs/matching.md
    - docs/learnings.md

key-decisions:
  - "First TACP match: func_00055080 (score candidate 1, 11 bytes) in unit u_00054f20, matched under the default `*  wcc386@10.6  -4r -s -fpi` rule on the first draft; no units.csv re-cut, no sweep, no cflags rule"
  - "func_00055080 is written `void` with `extern int D_0028DF70`: the bytes cannot tell void from returning the stored value, because wcc386 does not save EAX in a void function; a `short` global probe failed check"
  - "Two leaf-sized matches separate no Phase 4 candidate (10.5/10.6/11.0, -4/-5, -o* tied; -s consistent); the * default and __WATCOMC__ 1060 stay (D-18, D-14)"

patterns-established:
  - "The Phase 5 match evidence table has one row per EXE; the Flags note lists, per candidate, the cell that would settle its tie"

requirements-completed: [SPL-13]

coverage:
  - id: D1
    description: "func_00055080 of TACP.EXE matches by check's verdict: objdiff 100.0, reloc ok, bytes ok, UFO2P.EXE and TACP.EXE splices SHA-1 identical"
    requirement: SPL-13
    verification:
      - kind: integration
        ref: "docker compose run --rm build uv run reverseapoc check tacp/u_00054f20 --json (exit 0; build/gate/05-match-tacp.json parsed by the plan's verify plus the F4 splice-exe assertion)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The UFO2P match from 05-18 still holds after the TACP unit lands"
    requirement: SPL-13
    verification:
      - kind: integration
        ref: "docker compose run --rm build uv run reverseapoc check ufo2p/u_000a34f0 --json (exit 0; build/gate/05-match-ufo2p-recheck.json: func_000A3980 100.0, both splices ok, landed 1 each)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Container graph: configure, ninja, ninja lint and ninja verify land both units with all EXEs SHA-1 identical"
    verification:
      - kind: integration
        ref: "docker compose run --rm build bash -lc \"uv sync --locked && uv run python configure.py && ninja && ninja lint && ninja verify\" (exit 0, build/gate/05-ninja-both.out: UFO2P landed 1, TACP landed 1)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Evidence recorded: TACP row in docs/toolchain.md, the per-candidate Flags note, the docs/matching.md default statement, the docs/learnings.md entry"
    verification:
      - kind: other
        ref: "grep -qE '^\\| TACP' docs/toolchain.md && grep -qE '^\\| UFO2P' docs/toolchain.md"
        status: pass
    human_judgment: false
  - id: D5
    description: "The matched C is plain C89 a person could maintain (D-16)"
    verification: []
    human_judgment: true
    rationale: "The plan's human-check: the owner reads src/tacp/u_00054f20.c next to build/gate/05-match-tacp.json at /gsd-verify-work 5"

duration: 17min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 19: the first TACP hand match Summary

**func_00055080 of TACP.EXE is matched in C89 in src/tacp/u_00054f20.c, under the default `*  wcc386@10.6  -4r -s -fpi` rule on the first draft. `reverseapoc check tacp/u_00054f20 --json` reports objdiff 100.0, a passing relocation check, a clean byte compare, and UFO2P.EXE and TACP.EXE both landed SHA-1 identical. The UFO2P match from 05-18 still passes, and `ninja verify` lands both units. Together the two matches separate no compiler version or flag candidate, so the `*` default and `__WATCOMC__` 1060 stay.**

Execution context nonce: 95861203abf50cab

## Performance

- **Duration:** about 17 min
- **Started:** 2026-10-24T04:27:07Z
- **Completed:** 2026-10-24T04:44:28Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto)
- **Files:** 1 created, 3 modified

## Candidate list (`uv run reverseapoc score tacp --top 10 --json`)

TACP.EXE: 1,874 functions, 696 pass the P16 filter. Top 10:

| # | Address | Name | Size | Score | Reasons |
|---|---|---|---|---|---|
| 1 | 0x00055080 | func_00055080 | 11 | 153 | 1 call, 1 D_ reference, no push ebp frame |
| 2 | 0x0006EE30 | func_0006EE30 | 15 | 157 | same |
| 3 | 0x00032B80 | func_00032B80 | 32 | 174 | same |
| 4 | 0x000779C0 | func_000779C0 | 32 | 174 | same |
| 5-7 | 0x0006FBD0, 0x00071CE0, 0x00095850 | | 48 | 190 | same |
| 8 | 0x000C6287 | func_000C6287 | 53 | 195 | same |
| 9-10 | 0x000A7440, 0x000BA320 | | 32 | 198 | 3 calls, 1 D_ reference |

Only candidate 1 was tried. Before trying it I checked it against the rulings notes:
- It is well away from TACP's uncovered stretch at 0x00029D4D..0x00031040.
- Its target cut reports no `raw_fields` and no `undecoded` sites (check JSON `target`).

## The match

| | |
|---|---|
| EXE | TACP.EXE |
| Function | func_00055080, 0x00055080..0x0005508B, 11 bytes |
| Unit | u_00054f20 (0x00054F20..0x00056D70, draft reason alignment-gap). Kept as drafted, no re-cut: check and land compare and splice per function, so the other ten rows stay INCLUDE_ASM. |
| C | `void func_00055080(void)` stores `func_00011500()` in `extern int D_0028DF70`. One prototype, one extern per address, no inline assembly, no pragma. |
| Evidence cell | default (`*  wcc386@10.6  -4r -s -fpi`). No sweep ran (D-17 sweeps only after a miss), so `config/cflags.txt` is unchanged. |
| Candidates tried | 1 of the cap of 3 |
| First check (Task 1, build/match/tacp-first.json) | objdiff 100.0, relocation verdict ok, exit 0 |

### check JSON summary (build/gate/05-match-tacp.json)

- `ok: true`; compiler `wcc386@10.6`, flags `-4r -s -fpi`.
- functions: func_00055080, va 0x00055080, size 11, objdiff_percent 100.0, reloc ok (no problems), bytes ok (0 differing).
- problems: none. stubs: the other ten rows of the unit (func_00054F20, func_000550C0, func_00056070, func_000560E0, func_000562B0, func_00056590, func_00056940, func_00056A10, func_00056BB0, func_00056D20), all `stub, not checked`.
- splice: UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 equals the expected value, ok, landed 1. TACP.EXE sha1 48ef00969d8880a0a152de1b652853fa7ac27393 equals the expected value, ok, landed 1. Exactly these two EXEs.
- target: raw_fields none, undecoded none.

### UFO2P re-check (build/gate/05-match-ufo2p-recheck.json)

`check ufo2p/u_000a34f0 --json` exits 0: func_000A3980 objdiff 100.0, reloc ok, bytes ok; UFO2P.EXE ok (landed 1) and TACP.EXE ok (landed 1). No regression.

**Mutation probe:** declaring the global `short` makes check exit 1 (build/gate/05-match-tacp.mutant.out):
- the function becomes 12 bytes; objdiff 98.3333%;
- relocation check FAILED, 2 bytes differ from 0x00055085;
- the TACP splice refuses the function.

I restored the original C from a scratchpad copy (checked with `cmp`), and the committed file is the matching one.

## Task Commits

1. **Task 1 (tracer): candidate scored, unit scaffolded, drafted, linted and checked.** It needed no units.csv/functions.csv re-cut, so it made no commit. The plan has Task 2 commit the C once check says it matches. Tracer gate: an interactive run, `human_verify_mode` end-of-phase, automated-only verify. The verify passed (lint ok, check exit 0), so I expanded.
2. **Task 2: the TACP match:** `a463163` (feat)
3. **Task 3: evidence in the docs, graph and both suites:** `6a5dc52` (docs)

## Verification

| Command | Result |
|---|---|
| Task 1 lint (container `reverseapoc lint src/tacp/u_00054f20.c`) | `lint: 1 files, ok` |
| Task 1 check (container `check tacp/u_00054f20 --json` > build/match/tacp-first.json) | exit 0, one function entry, 100.0 |
| Task 2 verify (container check plus the plan's JSON assertion, with the splice exes asserted to be exactly {UFO2P.EXE, TACP.EXE} per ruling F4) | exit 0, VERIFY PASS |
| Task 2 UFO2P re-check (container `check ufo2p/u_000a34f0 --json`) | exit 0 |
| `git grep -n -e "_asm" -e "#pragma aux" -- src/` | nothing |
| `grep -n '^\*' config/cflags.txt` | exactly `37:*  wcc386@10.6  -4r -s -fpi` |
| Task 3 graph (container `configure.py && ninja && ninja lint && ninja verify`) | exit 0. `src/tacp/u_00054f20.c` compiled under wcc386@10.6 and lint ok; the UFO2P lint stamp was already current from 05-18. Both lint stamps sit under the `lint` phony. UFO2P `landed 1`, TACP `landed 1`, all three EXEs SHA-1 equal to the manifest. |
| `grep -qE "^\| TACP" docs/toolchain.md && grep -qE "^\| UFO2P" docs/toolchain.md` | pass |
| Host `uv run pytest -q` | 1540 passed, 25 skipped |
| Host `uv run ruff check .` | All checks passed! |
| Container `docker compose run --rm test` | 1563 passed, 2 skipped |

I ran the host suite and the container commands one at a time, never together.

## Files Created/Modified

- `src/tacp/u_00054f20.c` (new): the matched func_00055080 and ten INCLUDE_ASM markers.
- `docs/toolchain.md`: the TACP row in `### Phase 5 match evidence`. A Flags note gives each Phase 4 candidate's state after the two matches, the cell that would settle each tie, and why the `*` default and `__WATCOMC__` 1060 stay.
- `docs/matching.md`: "Compiler and flags per module" now says both matches used the `*` default, so no per-glob row exists.
- `docs/learnings.md`: the 2026-10-24 TACP entry.
- Gitignored, not committed:
  - `build/match/tacp.unit` (`u_00054f20`), `build/match/tacp-candidates.json`, `build/match/tacp-first.json`.
  - Under `build/gate/`: `05-match-tacp.json`, `05-match-tacp.mutant.out`, `05-match-ufo2p-recheck.json`, `05-ninja-both.out`, `05-19-host-suite.out`, `05-19-container-suite.out`.
  - `asm/tacp/func_00055080.s`, which I read locally only.

## What the two matches say (D-18)

| Candidate | State after 05-18 + 05-19 | What would settle it |
|---|---|---|
| 10.6 vs 10.5 | tied | a matched function whose 10.5 and 10.6 sweep cells differ (none known; the probe gives identical objects) |
| 10.6 vs 11.0 | tied | a match with 10.6 cells at 100.0 and 11.0 below it (or the reverse); likely a counted loop or a `-5` branch |
| `-4` vs `-5` | tied | a matched function with a 5-dword struct copy |
| `-o*` | candidate | a function with a loop or branch matching under `-4r -s` and not `-4r -s -ox` (or the reverse) |
| `-s` | consistent | (both match with `-s`; the `__CHK` functions still need their own rules) |
| `-zp*`, `-zm`, `-fp3`/`-fp5` | not touched | struct field access, function order/padding, x87 code |

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

No orchestrator ruling amends 05-19. I applied the notes addressed to 05-18/05-19 as interface facts:
- check is the only verdict.
- Every game/thunk row of the unit is exported or INCLUDE_ASM: check's problems[] is empty.
- The object exports no other public, data included: `D_0028DF70` is `extern`, so it defines nothing.
- The candidate has no `undecoded` sites or raw fields and does not touch the TACP uncovered stretch.
- No runtime aliases were needed (the callee is a functions.csv row), so check.load_exe is unchanged.

**1. [Minor] No Ghidra draft read for the candidate.** As in 05-18, the 11-byte listing was unambiguous (a call, a 32-bit store, a return), so I skipped the container `ghidra-export --drafts` step. Only check's output decides a match (D-16), so this changes no verdict.

**2. [Minor] Task 1 made no commit.** No re-cut was needed. Task 2's commit carries the C, as the plan prescribes.

---

**Total deviations:** 0 auto-fixed, 2 minor (one step skipped, one empty commit not made).
**Impact on plan:** none on any verdict.

## Issues Encountered

None.

## Known Stubs

None that block the plan's goal. The ten `INCLUDE_ASM` markers in src/tacp/u_00054f20.c are the D-12 design: a unit's unmatched functions stay markers until someone matches them.

## Threat Flags

None. T-05-43: the verify parses check's JSON, and `ninja verify` re-lands both units. T-05-44: the explicit UFO2P re-check exits 0, and `ninja verify` lands both EXEs SHA-1 identical. No package was installed.

## User Setup Required

None.

## Next Phase Readiness

- Roadmap criterion 4 now has one verified match per EXE. 05-20 can run its phase gate over both units.
- At /gsd-verify-work 5 the owner reads src/tacp/u_00054f20.c next to build/gate/05-match-tacp.json (D-16 human-check).
- The next matches should be chosen to carry a loop, a branch or a 5-dword struct copy, so they can separate the tied candidates.

## Self-Check: PASSED

- FOUND: src/tacp/u_00054f20.c, docs/toolchain.md, docs/matching.md, docs/learnings.md
- FOUND commits (ancestors of HEAD): a463163, 6a5dc52. `git rev-list --count 2abb069..HEAD` = 2 before this SUMMARY commit.

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
