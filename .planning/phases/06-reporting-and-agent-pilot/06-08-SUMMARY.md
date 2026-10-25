---
phase: 06-reporting-and-agent-pilot
plan: 08
subsystem: oracle
tags: [relocs, land, target, raw-fields, sha1, python]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-02 fileio.write_atomic (land's writer); 06-03 relocs hardening (own publics, F1 frames) that check_function keeps"
provides:
  - "RelocResult.start / .length / .sha1: the row start and the length and SHA-1 (hex) of the bytes a verdict judged, set by check_function (defaults None, ruling F24)"
  - "land/build_patch refusal, with a LandError naming the row, of an ok verdict that lacks those fields or names another row or other bytes (05-REVIEW 10b)"
  - "relocs.bytes_sha1, the one SHA-1 helper both sides use"
  - "the raw-field guarantee stated as relocation rule 4 plus rule 5 in target.py and docs/learnings.md (18a), pinned end to end (18c)"
affects: [06-09 (check.py may surface the new fields per function; check.py:300 keeps its positional RelocResult), 06-16 container re-run]

actuals:
  tokens: 5773  # chars/4 over git diff a9e13ed..b10cdbc (23,092 chars, code, tests and docs; SUMMARY not included)
  tasks: 2
  commits: 4  # git rev-list --count a9e13ed..b10cdbc, measured before the SUMMARY commit (5 with it)
plan_head_before: a9e13ed54f72aafb7389d1415f1707e516d1581d
plan_head_after: b10cdbcb79187261484fb8e4ea8d547ec543ec14

tech-stack:
  added: []
  patterns:
    - "A pass verdict carries what it judged (row start, byte length, SHA-1); the consumer that acts on it checks the pairing before acting"
    - "End-to-end raw-field tests cut with target.build_target and check with relocs.check_function on one relocpair image, with a passing control of the same shape"

key-files:
  created: []
  modified:
    - tools/reverseapoc/relocs.py
    - tools/reverseapoc/land.py
    - tools/reverseapoc/target.py
    - docs/learnings.md
    - tests/test_land.py
    - tests/test_target.py

key-decisions:
  - "The verdict-binding check lives in build_patch (which land calls for every function before any splice), after the ok check and before the row-length check, so a mismatched verdict is named as such"
  - "RelocResult.to_json is unchanged: the new fields are not emitted (plan's flagged assumption; 06-09 may surface them)"
  - "The SHA-1 is hashlib.sha1 hex via relocs.bytes_sha1, not targets.hash_bytes, so a verdict costs one hash"

patterns-established:
  - "LandError messages for a misfiled verdict name addresses (0x%08X), lengths and SHA-1s only, never a bytes repr"

requirements-completed: [AGT-06]

coverage:
  - id: D1
    description: "RelocResult names the row start, length and SHA-1 of the bytes it checked; land refuses a verdict for another row, other bytes, or one missing those fields, with a LandError naming the row; the check.py producer shape still lands (05-REVIEW 10b)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_land.py#test_check_function_names_the_row_and_bytes_it_judged, test_land_refuses_a_verdict_for_another_row, test_land_refuses_a_verdict_for_other_bytes[sha1|length], test_land_refuses_a_verdict_without_its_row_and_bytes, test_land_accepts_the_producer_shape"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_land.py tests/test_relocs.py tests/test_check.py (122 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "target.py's docstring and docs/learnings.md state the raw-field guarantee as rule 4 plus rule 5, not 'our side relocates the field' (05-REVIEW 18a)"
    requirement: "AGT-06"
    verification:
      - kind: other
        ref: "grep -q 'rule 4' tools/reverseapoc/target.py; grep 'rule 4.*rule 5' docs/learnings.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "An end-to-end test cuts a unit with a raw field (branch or off32 into no row), compiles nothing, and shows check_function failing at the field VA under rule 4 or rule 5; a control of the same shapes aimed at a row passes (05-REVIEW 18c)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_target.py#test_raw_field_reference_fails_check_function (5 cases), test_the_same_reference_to_a_named_row_passes (2 cases)"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 08: Relocation verdicts tied to their row and bytes, and the raw-field guarantee corrected Summary

**`check_function` now records the row start and the length and SHA-1 of the bytes it judged in its `RelocResult`, and `land` refuses, with a LandError naming the row, any ok verdict that lacks them or belongs to another row or other bytes. The raw-field reasoning in target.py and docs/learnings.md now names the real guarantee, relocation rule 4 plus rule 5, and an end-to-end test proves it.**

Execution context nonce: 56ce7980c36493d9

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-25T02:33:37Z
- **Completed:** 2026-10-25T02:40:51Z
- **Tasks:** 2 (Task 1 tracer: RED then GREEN; Task 2: test pin then docs)
- **Files modified:** 6

## Accomplishments

- 10b: `RelocResult` gains `start`, `length` and `sha1`, each defaulting to None (F24). `check_function` sets them on both of its returns, through one `_verdict` helper. `build_patch` (which `land` runs for every function before any splice) refuses an ok verdict whose fields are missing (`the relocation verdict names no row start, length or SHA-1 ...`), whose start is another row's (`... is for the row at 0x00010100, not this row at 0x00010110`), or whose length or SHA-1 differ from our bytes (`... is for 11 bytes with SHA-1 <a>, not these 12 bytes with SHA-1 <b>`). Every message starts with the row name and holds addresses, lengths and SHA-1s only.
- The check.py producer, `LandedFunction(d.row, d.ours, reloc)` from one `Defined`, is unchanged and still lands (`test_land_accepts_the_producer_shape`, and the full test_check.py suite). check.py:300 still builds its RelocError verdict positionally; that verdict is never ok, so it is refused as before.
- 18a: target.py's docstring (the raw-field paragraph) and the 05-18 entry in docs/learnings.md now say that wcc386 emits a fixup for every call, even to a static, so compiled C relocates the field, but that this is not the guarantee. The guarantee is rule 4 (each of our fixups must land on a nameable start equal to the original target, and a raw target lies in no row) plus rule 5 (every LE fixup field in the row is one of ours). The same wrong reason in a test_target.py comment was fixed too.
- 18c: `test_raw_field_reference_fails_check_function` cuts a one-row unit with `build_target` and checks it with `check_function` on the same synthetic image, with nothing compiled. It runs five cases, each asserting the cut's `raw_fields == (RawField(0x00010001, kind),)` and exactly one problem at 0x00010001:
  - branch to no row, extern at the gap: rule 4, `func_00010400_: no game or thunk row starts at 0x00010400`
  - branch to no row, another nameable start: rule 4, `resolves to 0x00010010, the original lands on 0x00010400`
  - off32 to no row, extern at the gap: rule 4, the SymbolError above
  - off32 to no row, another nameable start: rule 4, `resolves to 0x00010010, the original targets 0x00010400`
  - off32 to no row, our constant equal to the raw field: rule 5, `the original has an off32 LE fixup here and ours has none`

## Task Commits

1. **Task 1 (tracer): land refuses a verdict for another row or other bytes.** RED `80c5789` (test), GREEN `884e810` (fix).
2. **Task 2: raw-field reasoning corrected and proven end to end.** Test `c6f004e` (test), docs `b10cdbc` (docs).

**Plan metadata:** this SUMMARY commit (docs).

Task 1 is a tracer. After GREEN, the tracer gate ran in interactive `end-of-phase` mode with an automated-only verify. It re-ran `uv run pytest -q tests/test_land.py tests/test_relocs.py tests/test_check.py` (122 passed), then went on to Task 2.

## RED evidence (semantic assessment)

pytest's console report is not one of the formats `check tdd-red-evidence` supports, so RED was judged by inspecting each target assertion, as 06-03 and 06-04 did.

- Task 1 (`80c5789`): 5 targets failed on their planned assertions, with no import, collection or fixture faults:
  - `test_check_function_names_the_row_and_bytes_it_judged`: `assert None == 65536` (the verdict had no `start`).
  - `test_land_refuses_a_verdict_for_another_row`: `DID NOT RAISE LandError`.
  - `test_land_refuses_a_verdict_for_other_bytes[sha1]`: `DID NOT RAISE LandError`.
  - `test_land_refuses_a_verdict_for_other_bytes[length]`: the regex did not match. The old row-length LandError (`12 bytes of ours for a row of 11 bytes`) fired instead of the verdict refusal.
  - `test_land_refuses_a_verdict_without_its_row_and_bytes`: `DID NOT RAISE LandError`.
  - `test_land_accepts_the_producer_shape` passed, as planned: it pins the producer path.
- Task 2 (`c6f004e`): the plan expected the test to pass on the code as it stood, and all 7 cases did. To show it can fail, relocs.py was mutated temporarily: `_fixup` returned before resolving the target (rule 4 off) and `_reverse_coverage` returned at once (rule 5 off). All 5 raw cases then failed and both controls still passed. The file was restored with `git checkout -- tools/reverseapoc/relocs.py`, and the suite ran green again before the commit.

## Files Created/Modified

- `tools/reverseapoc/relocs.py`: `RelocResult.start/.length/.sha1` (default None) with a docstring, `bytes_sha1`, `_verdict`, and a line in the module docstring.
- `tools/reverseapoc/land.py`: `_check_verdict_is_for`, called from `build_patch` after the ok check. The module docstring now says that a pass verdict authorizes only its own row and bytes.
- `tools/reverseapoc/target.py`: the raw-field paragraph of the docstring now names rule 4 plus rule 5.
- `docs/learnings.md`: the 05-18 raw-field entry corrected (names rule 4 and rule 5).
- `tests/test_land.py`: five new tests plus a `verdict_for` helper. `forged` builds complete verdicts (F24), and the SHA-1-gate test forges a verdict for its changed bytes.
- `tests/test_target.py`: the end-to-end raw-field tests and their control. The 05-18 comment's reason was corrected.

## Decisions Made

- The binding check sits in `build_patch` rather than in `LandedFunction.__post_init__`. A misfiled verdict can still be built, and is refused at the one place that turns a verdict into bytes, before any splice. The existing `test_refuses_a_failed_check` builds a LandedFunction with an incomplete failed verdict, and that keeps working.
- The order in `build_patch` is: ok, then verdict pairing, then the row length. A length mismatch with a matching verdict still reports the old `bytes of ours for a row of` message (`test_refuses_bytes_of_the_wrong_length`).
- `to_json` is unchanged, so `check --json` stays byte-for-byte the same (the plan's flagged assumption).

## Deviations from Plan

- **Orchestrator ruling F24: defaults for the new fields.** `RelocResult` gains `start: int | None = None`, `length: int | None = None` and `sha1: str | None = None`, so check.py:300's positional construction is untouched. `land` refuses, with a LandError naming the row, any ok verdict whose start, length or sha1 is missing or differs from the LandedFunction (`test_land_refuses_a_verdict_without_its_row_and_bytes` is the added test for the missing case). The helper at tests/test_land.py:68 (`forged`) now builds complete verdicts through `verdict_for`. Commits `80c5789`, `884e810`.

### Auto-fixed Issues

**1. [Rule 1 - Test kept meaningful] The SHA-1-gate test forged a verdict of other bytes**
- **Found during:** Task 1 GREEN
- **Issue:** `test_mutated_byte_changes_the_sha1` paired the good verdict with changed bytes. GREEN now correctly refuses that pairing before the SHA-1 gate is reached, so the test no longer exercised what it is named for.
- **Fix:** it now forges a complete verdict for the changed bytes (`verdict_for`, with the good check's fields), so it still proves that the SHA-1 compare is independent of the check.
- **Files modified:** tests/test_land.py
- **Commit:** `884e810`

**2. [Rule 2 - Missing test] The `RelocResult` fields are pinned at the producer**
- **Found during:** Task 1 RED
- **Issue:** the plan's behaviour list tests land's refusal but not that `check_function` sets the fields.
- **Fix:** added `test_check_function_names_the_row_and_bytes_it_judged` (in tests/test_land.py, which is inside the plan's files, rather than test_relocs.py).
- **Commit:** `80c5789`

**3. [Plan text interpretation] Task 2's "deliberately wrong expectation as a second case"**
- The test asserts, inside each raw case, that the passing expectation (`_assert_passes`: no raw field and an ok verdict) raises AssertionError. A separate control test (`test_the_same_reference_to_a_named_row_passes`) shows the same shapes aimed at a row start do pass. The temporary rule-4/5 mutation above is the proof that the test can fail on broken code.
- The expected rule-4 text for an extern at the gap is the real SymbolError, `no game or thunk row starts at 0x00010400`. It is not `unknown symbol`, which the first draft of the test expected.

**4. [Scope] Stale reason in a test comment**
- tests/test_target.py's 05-18 comment ("our side relocates that field, so objdiff and the relocation check both disagree") repeated the 18a reason. It was reworded in `b10cdbc`. The file is in the plan's list.

---

**Total deviations:** 1 orchestrator ruling applied, 4 auto-handled (1 test kept meaningful, 1 missing test, 1 plan-text interpretation, 1 stale comment)
**Impact on plan:** no scope creep. check.py was not edited, as the plan required.

## Issues Encountered

- The worktree harness refuses compound shell commands that mix `cd` and git (for example a heredoc append). Edits went through the Edit tool, and git commands ran as single `git -C <worktree>` calls.
- `ruff format --check` reports drift in tests/test_land.py and relocs.py lines this plan did not touch (implicit string concatenation, older wrapped yields). The gate is `ruff check`, which is green. Left alone as out of scope.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- 06-09 (wave 3) owns check.py and can surface `start`/`length`/`sha1` per function in `check --json` if it wants. Today `to_json` does not emit them.
- Verification: `uv run pytest -q` 1527 passed, 216 skipped. `uv run ruff check .` all checks passed (host).

## Self-Check: PASSED

- FOUND: tools/reverseapoc/relocs.py, tools/reverseapoc/land.py, tools/reverseapoc/target.py, docs/learnings.md, tests/test_land.py, tests/test_target.py
- FOUND commits on HEAD: 80c5789, 884e810, c6f004e, b10cdbc
- tests/test_land.py has `test_land_refuses_a_verdict_for_another_row` and `test_land_refuses_a_verdict_for_other_bytes`. tests/test_target.py has `test_raw_field_reference_fails_check_function`. docs/learnings.md names rule 4 and rule 5. target.py contains `rule 4`.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
