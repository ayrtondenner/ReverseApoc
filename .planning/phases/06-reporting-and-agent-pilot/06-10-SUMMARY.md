---
phase: 06-reporting-and-agent-pilot
plan: 10
subsystem: oracle
tags: [check, relocs, omf2elf, jump-table, static, wcc386, DI-02, DI-03]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-08 RelocResult start/length/sha1 (land refuses a mismatched verdict); 06-09 provenance stamps and check-custom routing; 06-03 frame-method set F1"
provides:
  - "check.leading_table: a jump table at _TEXT+0 pairs with the data-in-code row before the head function's row; the span (table plus filler) is checked like a function and its problems fail the head"
  - "own_publics: every entry no longer than its row (a table after a public belongs to no row)"
  - "tests/test_check_tables_real.py: the real wcc386 10.6 switch and static probes, with separate objdiff tests (F25)"
  - "docs: matching.md relocation rules for tables and statics; learnings.md 2026-10-25 entry"
affects: [06-16, phase-7, score, pilot]

actuals:
  tokens: 9000
  tasks: 3
  commits: 5
plan_head_before: 325c6066b67916ec70c794d79ebfabfcea2178c1
plan_head_after: 02a6ca1bea1ed6353a83b87d7484fe38276d41b5

tech-stack:
  added: []
  patterns:
    - "Real-compiler probes laid into a synthetic LE built from our own object (rows at made-up VAs, LE fixups synthesised per fixup of ours), so no game byte is needed"

key-files:
  created:
    - tests/test_check_tables_real.py
  modified:
    - tools/reverseapoc/check.py
    - tools/reverseapoc/relocs.py
    - tools/reverseapoc/omf2elf.py
    - tests/test_check.py
    - tests/test_omf2elf.py
    - docs/learnings.md
    - docs/matching.md

key-decisions:
  - "The leading table is checked against [data-in-code row start, head row start), filler included, so the length rule refuses a layout of ours that differs; its problems fail the head function while the verdict's fields, row and sha1 stay the function's (land patches only those)"
  - "Own publics are capped at their row's length: closes the mid-unit-table fail-open where a coinciding layout let a jmp through an unchecked table pass"
  - "DI-03 needed no code change: omf2elf already drops an extern the module defines, so a row-named static and its callers pass; tests pin it"

patterns-established:
  - "A function that owns a leading jump table passes only when the table span also passes"

requirements-completed: [AGT-06, AGT-07]

coverage:
  - id: D1
    description: "A unit whose function opens with a jump table at _TEXT+0 pairs the table with its data-in-code row and passes; a wrong entry fails naming its VA"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_leading_table_pairs_with_its_data_row"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_leading_table_with_a_wrong_entry_fails"
        status: pass
    human_judgment: false
  - id: D2
    description: "A table between two publics still fails closed, also when our layout coincides with the original's"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_mid_unit_table_still_fails_closed"
        status: pass
      - kind: unit
        ref: "tests/test_relocs.py#test_own_segment_layout_coincidence_is_not_trusted"
        status: pass
    human_judgment: false
  - id: D3
    description: "The IN-02 6-case switch compiled by real wcc386 10.6 passes the relocation and byte checks on the host; a planted wrong case target fails"
    requirement: AGT-06
    verification:
      - kind: integration
        ref: "tests/test_check_tables_real.py#test_real_switch_probe_passes (build/06-10-switch.out)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A static named func_X and its caller, compiled by real wcc386 10.6, pass; calls landing one byte off fail the caller; a static named helper keeps the IN-01 message; omf2elf emits one LOCAL symbol for a self-EXTDEF"
    requirement: AGT-07
    verification:
      - kind: integration
        ref: "tests/test_check_tables_real.py#test_real_static_probe_passes (build/06-10-static.out)"
        status: pass
      - kind: unit
        ref: "tests/test_omf2elf.py#test_self_extdef_resolves_to_the_local_public"
        status: pass
    human_judgment: false
  - id: D5
    description: "objdiff layer of both real probes scores 100.0"
    requirement: AGT-06
    verification:
      - kind: integration
        ref: "tests/test_check_tables_real.py#test_real_switch_probe_objdiff, #test_real_static_probe_objdiff"
        status: unknown
    human_judgment: true
    rationale: "Skipped on the host (objdiff-cli not on PATH); runs unskipped only in the container, which plan 06-16 runs"
  - id: D6
    description: "docs/matching.md and docs/learnings.md state the table and static rules, the mid-unit refusal and the scorer's P16 exclusions until Phase 7"
    verification:
      - kind: other
        ref: "grep -qi 'jump table' docs/matching.md && grep -qi static docs/matching.md && uv run pytest -q tests/test_hygiene.py"
        status: pass
    human_judgment: false

duration: ~45min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 10: Jump tables and statics in check Summary

**`check` now proves a switch whose jump table leads its unit (the table span checked entry by entry against the original's data-in-code row) and a `static` named after its row with its callers, both on real wcc386 10.6 output. Mid-unit tables stay refused, now also when the layouts coincide.**

Execution context nonce: cc94622c737ece6f

## Performance

- **Duration:** about 45 min
- **Completed:** 2026-10-25T04:24:05Z
- **Tasks:** 3
- **Files modified:** 8 (1 created)

## Accomplishments

- DI-02: `check.leading_table` pairs `[0, first public)` with the data-in-code row that sits right before the head function's row. The pairing needs all of these: a first public past offset 0, one row named there, and a data-in-code row right before it that ends at or before its start. The span `[row start, head start)`, filler included, is checked like a function (length, bytes, every entry an off32 LE fixup to the original case label). Its problems fail the head function. The span is also an `OwnPublic`, so the head's `jmp cs:[eax*4+_TEXT+0]` resolves to the table row.
- Hardening found by the RED test: `own_publics` sized an entry to the next public, so a table after a public counted as that public's row. With a coinciding layout, the next function's `jmp` passed with its table never checked. Entries are now capped at their row's length, so that case is refused.
- DI-03: the probe showed the research's risk does not occur. omf2elf already emits only the LOCAL symbol for an LPUBDEF `func_X_` that the module also lists as an EXTDEF, so `write_elf` finds no ambiguous symbol. relocs resolves the caller's extern through the row placeholder, so a row-named static and its caller pass with no code change. Tests pin this, and a planted call target fails the caller.
- Docs: matching.md gets the table and static rules next to the relocation rules. learnings.md gets a dated entry, and its 2026-10-24 static entry now names the row-name condition.

## Probe results (real wcc386 10.6, host, `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom`)

- Switch (6 cases, `int func_00010140(int)`): `_TEXT` is 0x4C bytes. Six segment-relative F1 fixups to `_TEXT` sit at 0x0..0x14 (the table, which holds the case-label offsets). The public `func_00010140_` is at 0x18, with no filler between. The `jmp` table-address fixup is at 0x21, stored 0. omf2elf sizes the function at 52 bytes. This is the IN-02 layout exactly.
- Static (`static int func_00010040(int)` plus a caller): `func_00010040_` is an LPUBDEF at 0. The caller is a PUBDEF at 0xB. The two calls are self-relative F1 fixups to EXTDEF `func_00010040_`. `convert` gives one LOCAL STT_FUNC `func_00010040_` (size 11) and one GLOBAL `func_00010060_` (size 24), and no undefined duplicate.
- `build/06-10-switch.out`: `1 passed, 1 skipped` (only the objdiff layer, "objdiff-cli is not on PATH").
- `build/06-10-static.out` (tables_real plus omf2elf_real): `4 passed, 2 skipped` (both objdiff layers only). There were no runner or 10.6 skips.

## Task Commits

1. **Task 1 (tracer, TDD): leading jump table (DI-02)**: RED `930a173` (test), GREEN `a314bb9` (feat). The tracer gate re-ran the automated verify green before expansion (end-of-phase mode, automated only).
2. **Task 2 (TDD): row-named statics (DI-03)**: `55edbe4` (test; GREEN needed no code, see Deviations), plus `2efa21c` (docs: the omf2elf docstring).
3. **Task 3: docs**: `02a6ca1` (docs).

## Files Created/Modified

- `tools/reverseapoc/check.py`: `LeadingTable`, `leading_table`, the row-length cap in `own_publics`, and the table check merged into the head's verdict (`_with_table`) in `with_relocs`.
- `tools/reverseapoc/relocs.py`: the rule-4 docstring names the row cap and the leading-table entry. There is no behaviour change, and `test_own_segment_layout_coincidence_is_not_trusted` is untouched and green.
- `tools/reverseapoc/omf2elf.py`: the docstring says that a self-EXTDEF names the module's own symbol.
- `tests/test_check.py`: three synthetic table tests.
- `tests/test_omf2elf.py`: `test_self_extdef_resolves_to_the_local_public`.
- `tests/test_check_tables_real.py` (new): the switch and static probes, each with its own objdiff test.
- `docs/learnings.md`, `docs/matching.md`: the rules.

## Decisions Made

- The table span includes the filler up to the head row, so the length rule catches a different layout of ours and the filler bytes are compared too.
- The head function's verdict keeps its own `ours`/`theirs`/`start`/`length`/`sha1`. Only `ok` and `problems` absorb the table check, because land patches and verifies the function's bytes and fields alone. The table itself is never landed, so the original table bytes stay.
- Two data-in-code rows before one function (two switches) give a span shorter than our `[0, first public)`. That fails on length (fail closed) and is left for Phase 7.

## Deviations from Plan

**1. Orchestrator ruling F25: a separate objdiff test.** The objdiff layer of each real probe is its own test, `test_real_switch_probe_objdiff` and `test_real_static_probe_objdiff`, each calling `requires_objdiff()` after the compile. The plan and F25 write these names with a `[10.6]` id, but the tests are not parametrized: each compiles with 10.6 through `requires_version("10.6")`, so the real pytest ids carry no `[10.6]` (fix round 1, M5). The host run of `-k switch` shows the relocation and byte test passed and only the objdiff test skipped (`build/06-10-switch.out`).

**2. [Rule 2 - Missing critical] Own publics capped at their row's length**
- **Found during:** Task 1 RED. `test_mid_unit_table_still_fails_closed` passed the switch today when our layout coincided with the original's.
- **Issue:** a mid-unit table was attributed to the preceding public, so the `jmp` resolved and the table entries were never checked (a fail-open the plan's truth "a table between two publics still fails closed" forbids, T-06-19).
- **Fix:** `own_publics` sizes each entry `min(next public - offset, row length)`. This narrows the map, never widens it.
- **Files modified:** tools/reverseapoc/check.py
- **Verification:** the mid-unit test refuses it with `needs the unit's public-to-row map`, and the full suite is green.
- **Committed in:** a314bb9

**3. [TDD - unexpected GREEN] Task 2 needed no implementation**
- **Found during:** the Task 2 probe.
- **Issue:** the plan expected omf2elf to emit a LOCAL plus an undefined GLOBAL of one name. It does not: `omf2elf._symbols` already skips an extern a public or COMDAT of the module defines (since Phase 4), and relocs resolves the call through the row's placeholder.
- **Investigation:** dropping that filter makes `test_self_extdef_resolves_to_the_local_public` fail with `ElfError: ... ambiguous symbol 'func_00010000_'`, so the test bites. The real static test plants calls one byte off, and the caller fails.
- **Result:** a `test(06-10)` commit with no `feat(06-10)` for Task 2, plus a `docs(06-10)` commit that corrects the omf2elf docstring. The IN-01 message is unchanged.

**4. [Rule 3 - Blocking] Watcom tree path in the real verifies.** The harness refuses `$(git rev-parse ...)` in a command, so the real verifies ran with `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom`, the relative path the plan notes allow. The asserted outputs and grep conditions are as written.

**5. Real probes go through `check.check_source`.** They do not call `check_function` directly, so omf2elf, target.py, the unit account (D-12 source checks included) and the byte compare run too. The objdiff runner is a stand-in returning 100.0 in the host tests only. The real objdiff layer is the separate F25 test.

- R-A: no new platform skip was added. The real tests skip only through the existing `requires_runner` / `requires_version` / `requires_objdiff` helpers.
- R-B: not yet in force (it applies from 06-12's merge on). The build/ evidence files were written by shell redirection anyway. The scratch probe sources under `build/06-10-probe/` (gitignored) were written with the Write tool.

**Total deviations:** 1 orchestrator ruling applied, 1 Rule 2, 1 TDD unexpected GREEN, 1 Rule 3 path workaround, 1 test-route choice.
**Impact on plan:** the Rule 2 cap tightens the oracle. Nothing was widened.

## TDD Gate Compliance

- Task 1: RED `930a173` (the synthetic tests failed on the missing pairing, and the mid-unit test failed because the switch passed; the real test failed with `own _TEXT target 0x0 outside func_00010140 needs the unit's public-to-row map`, the IN-02 refusal), then GREEN `a314bb9`.
- Task 2: RED commit `55edbe4` has no failing run. The behaviour already existed (unexpected GREEN, investigated above), so there is no `feat(06-10)` commit for Task 2.

## Issues Encountered

- Python `write_text` on Windows wrote CRLF into two test files during editing. They were normalised to LF before the first commit.

## Threat Flags

None. The change sits inside T-06-19 and T-06-20 (both mitigated: pairing only through the committed data-in-code row, every entry checked, mid-unit tables and coincidences refused; a self-EXTDEF resolves only to the module's own identically named symbol).

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- Plan 06-16 runs the objdiff layers (`test_real_switch_probe_objdiff`, `test_real_static_probe_objdiff`) unskipped in the container. If target.py's relocation for the `jmp` table address does not pair with ours in objdiff, that test shows it there.
- The pilot scorer keeps P16's exclusions (jump tables) until Phase 7.

## Fix round 1

Review: `review-06-10.md` (FIX_BASE db8c803). TDD order: RED `2861c12`, then GREEN `9c16f06`.

| Item | Finding | Fix | Commit | Proof |
|---|---|---|---|---|
| C1 (Critical) | The table's own-public entry was offered to every function, but the table was checked only in the head's verdict. A later function jumping through `_TEXT+0` passed with a wrong table and would have been landed. | `own_publics` no longer carries the table entry. `with_relocs` adds it only to the head's map, so any other function's reference to `[0, first public)` is refused ("needs the unit's public-to-row map"). If the account dropped the head, nothing resolves into the table. | 9c16f06 | `test_leading_table_used_by_another_function_is_refused[same-table]` and `[planted-entry]` (the reviewer's layout): RED in 2861c12, green after 9c16f06 |
| M1 | The `with_relocs` docstring said entries land "inside that function", but entries into any function of the unit were accepted. | Tightened to the claim: the span is checked with the head as its only other own public, so every entry must land inside the head on the original's target. The docstring states exactly that. | 9c16f06 | `test_leading_table_entry_outside_the_head_fails`: RED in 2861c12, green after |
| M2 | `leading_table`'s refusal branches and the span's filler and length comparison had no committed tests. | Pinned (they fail closed today) with `test_no_leading_table_without_its_data_row` (`game-row-before-head`, `data-row-past-head-start`, `no-data-row`) and `test_leading_table_span_compares_filler_and_length` (`filler-differs`, `original-table-longer`). | 2861c12 | pass |
| M3 | `leading_table` ran twice per function, and `own_publics` once per function. | `_SegmentMap` computes both once per code segment in `with_relocs`. | 9c16f06 | suite green |
| M4 | learnings.md cited D-09 for "drafts stay non-static", which D-09 does not say. | Reworded: the scorer has no static filter yet, and adding one is Phase 7 tuning (D-09). Also added the head-only rule to learnings.md and matching.md. | 3287ee8 | `tests/test_hygiene.py` pass |
| M5 | The SUMMARY quoted `[10.6]` ids that do not exist. | Deviation 1 now gives the real names and says why they carry no id. | this SUMMARY commit | n/a |

The 06-08 binding is kept: the head's verdict keeps its own `start`, `length`, `sha1`, `ours` and `theirs`. Only `ok` and `problems` take the span's result (`_with_table`).

Evidence re-run after the fix (`REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom`, shell redirection):
- `build/06-10-switch.out`: `1 passed, 1 skipped, 2 deselected` (the skip is the objdiff layer only).
- `build/06-10-static.out` (tables_real plus omf2elf_real): `4 passed, 2 skipped` (both skips are objdiff layers). There were no runner or 10.6 skips.
- `uv run pytest -q`: 1610 passed, 221 skipped. `uv run ruff check .`: all checks passed.

## Self-Check: PASSED

- Files: tests/test_check_tables_real.py, tools/reverseapoc/check.py, docs/matching.md and docs/learnings.md exist.
- Commits 930a173, a314bb9, 55edbe4, 2efa21c and 02a6ca1 are on this branch (`git rev-list --count 325c606..HEAD` = 5 before this SUMMARY).
- Acceptance: all three synthetic test names are in tests/test_check.py; `test_self_extdef_resolves_to_the_local_public` and `test_real_static_probe_passes` exist; tests/test_check_tables_real.py holds only its C sources and a synthetic LE; learnings.md no longer says a static cannot pass without naming the row-name condition.
- `uv run pytest -q`: 1602 passed, 221 skipped. `uv run ruff check .`: all checks passed.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
