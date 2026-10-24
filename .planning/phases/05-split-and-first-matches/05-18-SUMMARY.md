---
phase: 05-split-and-first-matches
plan: 18
subsystem: matching
tags: [first-match, check, objdiff, relocs, land, ninja, cmain386, target, spl-13, d-16, d-17]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-17 check_source/check_unit/land_all and the target/land verbs; 05-16 committed functions/units/symbols CSVs; 05-14 the ninja graph; 05-11 score (P16); 05-13 units --write-src"
provides:
  - "tests/test_check_real.py: the cmain386 production re-proof for UFO2P and TACP and the real-pair planted wrong call target"
  - "tests/test_objdiff_real.py: the objdiff 2nd-relocation blind spot through omf2elf, build_target and objdiff-cli"
  - "src/ufo2p/u_000a34f0.c: func_000A3980 matched in C89 (first UFO2P hand match), two INCLUDE_ASM stubs"
  - "target.py: references into no functions.csv row and branches out of the code object stay raw and are named in raw_fields, so every real unit cuts and the default ninja graph builds"
  - "docs/toolchain.md ### Phase 5 match evidence; docs/learnings.md 2026-10-24 entry"
affects: [05-19, 05-20, phase-06]

actuals:
  tokens: 6860
  tasks: 3
  commits: 5
plan_head_before: 705c4b687bcbe5a2ae15e06966dd4fe509f4ef0c
plan_head_after: 28aaf039c636d5ff866fb4b4eec68468520251f2

tech-stack:
  added: []
  patterns:
    - "Real compile tests write their objects under build/test-check/<test> (reverseapoc cc refuses an output outside the repository)"
    - "A match claim is backed by a mutation probe: a one-token change to the matched C must make check exit 1"

key-files:
  created:
    - tests/test_check_real.py
    - tests/test_objdiff_real.py
    - src/ufo2p/u_000a34f0.c
  modified:
    - tools/reverseapoc/target.py
    - tests/test_target.py
    - docs/toolchain.md
    - docs/learnings.md

key-decisions:
  - "First UFO2P match: func_000A3980 (score candidate 1, 13 bytes) in unit u_000a34f0, matched under the default `*  wcc386@10.6  -4r -s -fpi` rule on the first try; no units.csv re-cut, no sweep, no cflags rule"
  - "The global the function loads is `extern signed char D_0012EFAC;` (the original sign-extends); a probe with `unsigned char` failed check (objdiff 46.7%, reloc FAILED, 3 bytes differ, splice refused)"
  - "target.py leaves raw, and names in raw_fields, an off32 fixup or rel32 branch into code no functions.csv row covers and a decoded branch out of the code object (kinds `off32 to no row`, `branch to no row`, `branch outside the code object`), the F11 principle; 18 of 842 real target cuts failed before"
  - "One match separates no compiler version or flag candidate; the `*` default is unchanged (D-18)"

patterns-established:
  - "Phase 5 match evidence table in docs/toolchain.md: one row per hand match, written only from check --json exit 0"

requirements-completed: [SPL-13, SPL-09, SPL-10, SPL-06]

coverage:
  - id: D1
    description: "The production pipeline re-proves spike 005: check_source on CMAIN386.C against __CMain gives objdiff 100.0, reloc ok, bytes ok in UFO2P and TACP, and landing it alone keeps the manifest SHA-1; a planted exit_ -> main_ call target fails the relocation check at the field VA"
    requirement: SPL-09
    verification:
      - kind: integration
        ref: "tests/test_check_real.py#test_cmain386_pair_matches[UFO2P.EXE], [TACP.EXE], #test_cmain386_wrong_call_target_fails (container, unskipped: build/gate/05-cmain-real.out)"
        status: pass
    human_judgment: false
  - id: D2
    description: "objdiff-blind negative: a wrong 2nd relocation of mov dword [abs32], imm32 scores 100.0 in objdiff-cli through omf2elf and build_target while relocs.check_function fails it (roadmap criterion 4)"
    requirement: SPL-13
    verification:
      - kind: integration
        ref: "tests/test_objdiff_real.py#test_second_relocation_blind_spot (container, unskipped)"
        status: pass
    human_judgment: false
  - id: D3
    description: "func_000A3980 of UFO2P.EXE matches by check's verdict: objdiff 100.0, reloc ok, bytes ok, UFO2P.EXE and TACP.EXE splices SHA-1 identical"
    requirement: SPL-13
    verification:
      - kind: integration
        ref: "docker compose run --rm build uv run reverseapoc check ufo2p/u_000a34f0 --json (exit 0; build/gate/05-match-ufo2p.json parsed by the plan's verify)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The matched C is plain C89 a person could maintain (D-16)"
    verification: []
    human_judgment: true
    rationale: "The plan's human-check: the owner reads src/ufo2p/u_000a34f0.c next to build/gate/05-match-ufo2p.json at /gsd-verify-work 5"
  - id: D5
    description: "Container graph: configure, ninja, ninja lint and ninja verify succeed, compiling the unit under wibo, linting it and landing it with both EXEs SHA-1 identical; every real unit's target cuts"
    requirement: SPL-06
    verification:
      - kind: integration
        ref: "docker compose run --rm build bash -lc \"uv sync --locked && uv run python configure.py && ninja && ninja lint && ninja verify\" (exit 0, build/gate/05-ninja-ufo2p.out: UFO2P landed 1)"
        status: pass
      - kind: unit
        ref: "tests/test_target.py#test_a_branch_out_of_the_code_object_stays_raw, #test_a_call_to_no_row_stays_raw, #test_an_off32_target_in_no_row_stays_raw"
        status: pass
    human_judgment: false
  - id: D6
    description: "Evidence recorded: docs/toolchain.md ### Phase 5 match evidence row and Flags note, docs/learnings.md dated entry"
    verification:
      - kind: other
        ref: "grep -q '^### Phase 5 match evidence' docs/toolchain.md && grep -qE '^\\| UFO2P' docs/toolchain.md"
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 18: the first UFO2P hand match Summary

**func_000A3980 of UFO2P.EXE is matched in C89 in src/ufo2p/u_000a34f0.c, under the default `*  wcc386@10.6  -4r -s -fpi` rule on the first try. `reverseapoc check ufo2p/u_000a34f0 --json` reports objdiff 100.0, a passing relocation check, a clean byte compare, and both UFO2P.EXE and TACP.EXE landed SHA-1 identical. Before any game C, the production omf2elf, target writer, relocation check and land step reproduced spike 005 on Watcom's own CMAIN386.C in both EXEs and caught the planted wrong targets. The first real `ninja` run exposed 18 units the target writer could not cut; that is fixed.**

Execution context nonce: 591970bbd9a4375e

## Performance

- **Duration:** about 32 min
- **Started:** 2026-10-24T03:43:27Z
- **Completed:** 2026-10-24T04:15Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto)
- **Files:** 3 created, 4 modified

## Candidate list (`uv run reverseapoc score ufo2p --top 10 --json`)

UFO2P.EXE: 1,892 functions, 612 pass the P16 filter. Top 10:

| # | Address | Name | Size | Score | Reasons |
|---|---|---|---|---|---|
| 1 | 0x000A3980 | func_000A3980 | 13 | 155 | 1 call, 1 D_ reference, no push ebp frame |
| 2 | 0x0008A0E0 | func_0008A0E0 | 27 | 169 | same |
| 3-9 | 0x0008A100 .. 0x0008A1C0 (every 0x20) | func_0008A100 .. func_0008A1C0 | 27 | 169 | same |
| 10 | 0x00026FD0 | func_00026FD0 | 32 | 174 | same |

Only candidate 1 was tried. Before trying it I checked it against the 05-16 notes:
- It is not one of the poor candidates (func_0007BDB0, func_000B7070).
- Its target cut reports no `raw_fields` and no `undecoded` sites (check JSON `target`).

## The match

| | |
|---|---|
| EXE | UFO2P.EXE |
| Function | func_000A3980, 0x000A3980..0x000A398D, 13 bytes |
| Unit | u_000a34f0 (0x000A34F0..0x000A3990, draft reason alignment-gap). Kept as drafted, no re-cut: the matched function's object holds only that function, and check and land compare and splice per function. The unit's other rows are func_000A34F0 and func_000A3970, both kept as INCLUDE_ASM. |
| C | `int func_000A3980(void)`: it calls `func_000A3990()` and returns `extern signed char D_0012EFAC`. One prototype and one extern per address, no inline assembly, no pragma. |
| Evidence cell | default (`*  wcc386@10.6  -4r -s -fpi`). No sweep was run (D-17 sweeps only after a miss), so `config/cflags.txt` is unchanged. |
| Candidates tried | 1 of the cap of 3 |

### check JSON summary (build/gate/05-match-ufo2p.json)

- `ok: true`; compiler `wcc386@10.6`, flags `-4r -s -fpi`.
- functions: func_000A3980, va 0x000A3980, size 13, objdiff_percent 100.0, reloc ok (no problems), bytes ok (0 differing).
- problems: none. stubs: func_000A34F0 and func_000A3970, both `stub, not checked`.
- splice: UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 equals the expected value, ok, landed 1. TACP.EXE sha1 48ef00969d8880a0a152de1b652853fa7ac27393 equals the expected value, ok, landed 0. Exactly these two EXEs.
- target: raw_fields none, undecoded none.

**Mutation probe:** declaring the global `unsigned char` makes check exit 1:
- objdiff 46.6667%;
- relocation check FAILED, 3 bytes differ from 0x000A3985;
- the UFO2P splice refuses the function.

The original C was restored from a scratchpad copy, and the committed file is the matching one.

## Task Commits

1. **Task 1 (tracer): cmain386 re-proof and the objdiff blind spot.**
   - `77e6709` (test): the two real-test modules.
   - `c891b3e` (test, RED) and `e5120a9` (fix, GREEN): the target writer fix the baseline graph needed (see Deviations).
   - Tracer gate: an interactive run, `human_verify_mode` end-of-phase, automated-only verify. After the fix I re-ran the Task 1 verify in the container: 24 passed with tests/test_target.py, no SKIPPED. Then I expanded.
2. **Task 2: the first UFO2P game function:** `5ab2e79` (feat)
3. **Task 3: evidence in the docs:** `28aaf03` (docs)

## TDD notes

- **Task 1, first container run:**
  - The three cmain386 cases failed with `CompilerError: ... is outside /work`. `reverseapoc cc` writes objects only inside the repository, and the tests used pytest's `tmp_path`. This was a test defect, not a production writer defect. The tests now write under `build/test-check/<test>`, following tests/test_compiler_real.py's `build/test-cc/`.
  - `test_second_relocation_blind_spot` passed at once. It pins behaviour that the production writers from 05-02/05-06/05-08/05-09 already had.
  - After the fix: 4 passed, no SKIPPED (build/gate/05-cmain-real.out).
- **target.py fix:**
  - RED `c891b3e`: the three rewritten tests failed with the old `TargetError` (`... in no functions.csv row`, `... outside the code object`).
  - GREEN `e5120a9`: 20 of 20 passed.
- The plan is `type: execute` and `workflow.tdd_mode` is off, so the tdd-red-evidence classifier does not apply.

## Verification

| Command | Result |
|---|---|
| Task 1 verify (container `pytest -q -rs tests/test_check_real.py tests/test_objdiff_real.py`) | 4 passed, no SKIPPED |
| Task 1 baseline (container `configure.py && ninja && ninja verify`, before any C) | exit 0; both EXEs `landed 0`, SHA-1 equal to the manifest |
| Task 2 verify (container `check ufo2p/u_000a34f0 --json` plus the plan's JSON assertion, with the splice exes asserted to be exactly {UFO2P.EXE, TACP.EXE} per ruling F4) | exit 0, VERIFY PASS |
| `uv run pytest -q tests/test_cflags.py tests/test_hygiene.py -k cflags` | 60 passed |
| `git grep -n -e "_asm" -e "#pragma aux" -- src/` | nothing |
| `grep -n '^\*' config/cflags.txt` | exactly `37:*  wcc386@10.6  -4r -s -fpi` |
| `git ls-files -- '*CMAIN386*' '*cmain386*'` | nothing |
| Task 3 graph (container `configure.py && ninja && ninja lint && ninja verify`) | exit 0; `CC src/ufo2p/u_000a34f0.c` under wcc386@10.6, `lint: 1 files, ok`, UFO2P `landed 1` and TACP `landed 0`, both SHA-1 identical |
| Host `uv run pytest -q` | 1540 passed, 25 skipped |
| Host `uv run ruff check .` | All checks passed! |
| Container `docker compose run --rm test` | 1563 passed, 2 skipped |

## Files Created/Modified

- `tests/test_check_real.py` (new): `test_cmain386_pair_matches[UFO2P.EXE|TACP.EXE]` and `test_cmain386_wrong_call_target_fails`. CMAIN386.C is read in place from `WATCOM_DIR/10.6`, and the test asserts names, VAs, percentages and SHA-1s only.
- `tests/test_objdiff_real.py` (new): `test_second_relocation_blind_spot` covers the good pair at 100.0 with the check passing, then a first-relocation control below 100, then the blind spot at 100.0 with the check failing at the second field.
- `src/ufo2p/u_000a34f0.c` (new): the matched func_000A3980 and two INCLUDE_ASM markers.
- `tools/reverseapoc/target.py`: the RAW_* kinds. `_target_symbol` returns None for a code address in no row. `_branch_relocs` returns `_Branches(fields, raw, undecoded)`. raw_fields are sorted by VA. The docstring is updated.
- `tests/test_target.py`: the three refusal tests became raw-site tests. The row-outside-the-code-object and split-field refusals are unchanged.
- `docs/toolchain.md`: `### Phase 5 match evidence` (table and the cmain386 re-proof), and a note under Flags on what this match confirms or leaves tied.
- `docs/learnings.md`: the 2026-10-24 entry.
- Gitignored, not committed: `build/match/ufo2p.unit` (`u_000a34f0`), `build/match/ufo2p-candidates.json`, and under `build/gate/`: `05-cmain-real.out`, `05-ninja-baseline.out`, `05-ninja-k0.out`, `05-match-ufo2p.json`, `05-match-ufo2p.try1.json`, `05-match-ufo2p.mutant.out`, `05-ninja-ufo2p.out`, `05-18-host-suite.out`, `05-18-container-suite.out`. Also `asm/ufo2p/func_000A3980.s`, read locally only.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

No orchestrator ruling amends 05-18. I applied the notes addressed to 05-18 as interface facts:
- check is the only verdict.
- The candidate has no `undecoded` sites or raw fields.
- The 05-16 poor candidates were avoided.
- The cmain386 object exports only `__CMain`: `result.problems == ()` is asserted.
- No runtime aliases were needed. Every cmain386 extern resolves through functions.csv and symbols.csv, so check.load_exe is unchanged.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The target writer refused references into code with no functions.csv row**
- **Found during:** Task 1, the baseline `ninja && ninja verify`. This was the first run of the 05-14 graph on the 05-16 split.
- **Issue:** 18 of 842 target edges failed, so ninja stopped before any C existed:
  - 13 rel32 branches into code that no functions.csv row covers. Examples: UFO2P grafix_3, u_0007bdb0, and u_000cfab6 into the 3-byte uncovered tail; TACP u_00029340 into its uncovered stretch.
  - 3 off32 fixups into such code (UFO2P u_000658e0, TACP u_00074530 and u_000ad340).
  - 2 decoded branches out of the code object in rt_i64tos (data read as code), one in each EXE.

  These are split gaps D-11 leaves for later, and D-13 needs every unit cuttable.
- **Fix:** such a field keeps its raw bytes, gets no relocation, and is named in `raw_fields`, exactly as ruling F11 does for non-off32 fixups. A function holding one is no first-match candidate: score already rejects calls to non-row starts, and 05-18/05-19 skip any target with raw fields. It cannot pass falsely, because our side relocates the field, so objdiff and the relocation check both disagree with the raw target. The refusals for a row outside the code object and for a field split by a row boundary stay.
- **Files modified:** tools/reverseapoc/target.py, tests/test_target.py
- **Verification:** 3 rewritten unit tests; the baseline graph exits 0; the full host and container suites pass.
- **Committed in:** c891b3e (RED), e5120a9 (GREEN)

**2. [Rule 3 - Blocking] The real compile tests write under build/test-check/, not tmp_path**
- **Found during:** Task 1 RED run.
- **Issue:** `reverseapoc cc` refuses an object outside the repository root.
- **Fix:** a `build_dir` fixture creating `build/test-check/<test name>`.
- **Committed in:** 77e6709

**3. [Minor] No Ghidra draft read for the candidate**
- The plan's step 3 reads both `asm --only` and the container `ghidra-export --drafts`. The listing of the 13-byte function was unambiguous (a call, a sign-extending byte load, a return), so I skipped the Ghidra draft. Only check's output decides a match (D-16), so this changes no verdict.

---

**Total deviations:** 2 auto-fixed (both blocking), 1 minor step skipped.
**Impact on plan:** The target.py change widens what the target writer accepts to the F11 shape. It never widens what check passes.

## Issues Encountered

None beyond the deviations.

## Known Stubs

None that block the plan's goal. The two `INCLUDE_ASM` markers in src/ufo2p/u_000a34f0.c (func_000A34F0, func_000A3970) are the D-12 design: unmatched functions of a unit stay markers until matched.

## Threat Flags

None. T-05-39: the verify parses check's JSON, and ninja verify re-lands. T-05-40: the `_asm` / `#pragma aux` grep over src/ is empty, and lint runs in ninja. T-05-41: the `*` line is unchanged and no per-glob rule was added. T-05-42: no listing or draft text appears in a commit or this SUMMARY. The C states only what the function does.

## User Setup Required

None.

## Next Phase Readiness

- 05-19 (TACP first match) can use the same loop. TACP's target cuts now all build, including the units around its uncovered stretches. Candidates with `raw_fields` must still be skipped.
- At /gsd-verify-work 5 the owner reads src/ufo2p/u_000a34f0.c next to build/gate/05-match-ufo2p.json (D-16 human-check).
- Requirements SPL-13, SPL-09, SPL-10 and SPL-06 are handed to the shared-ID gate (`requirements.ready-ids`). 05-19/05-20 also declare some of them.

## Self-Check: PASSED

- FOUND: tests/test_check_real.py, tests/test_objdiff_real.py, src/ufo2p/u_000a34f0.c, tools/reverseapoc/target.py, docs/toolchain.md, docs/learnings.md
- FOUND commits (ancestors of HEAD): 77e6709, c891b3e, e5120a9, 5ab2e79, 28aaf03. `git rev-list --count 705c4b6..HEAD` = 5 before this SUMMARY commit.

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
