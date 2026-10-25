---
phase: 06-reporting-and-agent-pilot
plan: 03
subsystem: oracle
tags: [configure, d-12, relocs, omf, fixup-frame, ninja, python]

requires:
  - phase: 05-split-and-first-matches
    provides: "configure.py D-12 parser, relocs.check_function, the two matched units and 05-REVIEW items 10/12/15"
provides:
  - "configure.py D-12 parser that splices backslash-newline like translation phase 2 (DI-05)"
  - "relocs refusal of overlapping/duplicate own publics (DI-04 12a) and of fixup frames other than F1 FLAT (10a)"
  - "build.ninja rules that carry a non-default --config tree (DI-06 part c)"
affects: [06-12 hooks.py (reuses the D-12 parser), 06-09 (updates the default-render golden), driver plans, 06-16 container re-run]

actuals:
  tokens: 9024
  tasks: 3
  commits: 6
plan_head_before: 021a58ba7441665b1eb5486caef92c91f23ad9c2
plan_head_after: de94a5b222dea3a22b91ee2dd0bd9b03860ada1b

tech-stack:
  added: []
  patterns:
    - "D-12 parser reads logical lines: a directive and its backslash continuations are one directive, reported at its first physical line"
    - "relocs accepts exactly the observed set of fixup frame methods (FLAT_CODE_FRAMES), named, never a bare number"
    - "configure emits config-tree arguments only for a non-default --config, so the default text is byte-identical"

key-files:
  created: []
  modified:
    - configure.py
    - tools/reverseapoc/relocs.py
    - tests/test_configure.py
    - tests/test_relocs.py
    - tests/relocpair.py
    - tests/test_check.py
    - tests/test_objdiff_real.py

key-decisions:
  - "The allowed fixup frame set is {F1}: every FIXUPP of both real wcc386 10.6 matched units is F1 with the FLAT group as frame datum"
  - "A spliced string or character literal keeps its line breaks between its quotes when blanked, so directive line numbers stay true"
  - "Layout.rule_config is None when --config resolves to ROOT/config, wherever build.ninja is written; only then is the default text emitted"
  - "asm also receives --manifest for a custom config tree (it selects the EXE from the manifest), besides --functions/--symbols"

patterns-established:
  - "Synthetic OMF fixtures frame every fixup F1 FLAT (relocpair.FLAT_FRAME, a FLAT GRPDEF in each builder), as the real objects do"

requirements-completed: [AGT-05, AGT-06]

coverage:
  - id: D1
    description: "A marker or definition on the continuation line of a // comment or #define is dead for configure and check alike; directive line numbers stay true (DI-05)"
    requirement: "AGT-05"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_line_comment_continuation_hides_a_marker, test_define_continuation_hides_a_definition, test_continuation_keeps_directive_line_numbers, test_directive_continuation_is_one_directive, test_check_source_marks_agrees_with_configure"
        status: pass
    human_judgment: false
  - id: D2
    description: "relocs refuses duplicate/overlapping own publics before resolving any fixup; 12b and 12c pinned (DI-04)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_relocs.py#test_duplicate_own_publics_are_refused, test_target_at_own_public_end_is_refused, test_wrong_target_inside_function_fails, test_own_segment_layout_coincidence_is_not_trusted"
        status: pass
    human_judgment: false
  - id: D3
    description: "A fixup framed other than F1 FLAT is refused at the field VA (10a); relocpair names LE kinds (10c); byte-dump regex case-insensitive (10d)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_relocs.py#test_unexpected_frame_is_refused"
        status: pass
      - kind: other
        ref: "scratch: check.checked_functions on build/06-03/u_000a34f0.obj and u_00054f20.obj (real wcc386 10.6) -> func_000A3980 ok, func_00055080 ok"
        status: pass
    human_judgment: false
  - id: D4
    description: "build.ninja's check-orig, rebuild, target, land and asm rules carry a non-default --config; the default render is unchanged (DI-06 part c)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_default_config_render_is_unchanged, test_default_config_dir_adds_no_rule_flags, test_custom_config_rules_name_its_manifest"
        status: pass
    human_judgment: false

duration: 17min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 03: Oracle hardening (D-12 continuation, relocs own publics and frame, config-consistent rules) Summary

**The D-12 parser now splices backslash-newline the way the compiler does, relocs refuses overlapping own publics and any fixup frame other than the F1 FLAT that real wcc386 10.6 objects use, and build.ninja rules pass a non-default `--config` tree to every verb that reads config/.**

Execution context nonce: 8576cea0285a1181

## Performance

- **Duration:** 17 min
- **Started:** 2026-10-25T01:08:59Z
- **Completed:** 2026-10-25T01:25:36Z
- **Tasks:** 3 (each RED test commit, then GREEN fix commit)
- **Files modified:** 7

## Accomplishments

- DI-05: a `//` comment runs on through a backslash-newline, a directive plus its continuation lines is one logical directive (so `#if \` + `0` is `#if 0`, and an `#ifdef` inside a `#define` body is not a directive), and a spliced literal keeps its line breaks. `check.source_marks` agrees with configure on the three probe texts, and check.py is unchanged.
- DI-04: `_check_own_publics` raises RelocError naming both publics when two own publics share a byte (same offset or overlapping spans), before any fixup is resolved. The 12b (target at an own public's end) and 12c (`_TEXT+0x5 resolves to 0x00010005, the original lands on 0x00010006`) behaviours are pinned. `test_own_segment_layout_coincidence_is_not_trusted` still passes, and own-public sizes are not widened.
- 10a: `FRAME_GROUP = 1` and `FLAT_CODE_FRAMES = frozenset({FRAME_GROUP})` in relocs.py. A fixup with any other frame method gives `0xVVVVVVVV: <target>: fixup frame method F<n> is not F1, the frame wcc386 10.6 emits for flat code`.
- 10c/10d: relocpair and test_relocs use `SRC_OFF32` / `SRC_SEL16` from le.py, and `_BYTE_DUMP` is `re.IGNORECASE`.
- DI-06 part c: for a non-default `--config DIR`, `check-orig` and `rebuild` get `--manifest DIR/targets.toml`, `target` and `land` also get `--config DIR`, and `asm` gets `--manifest`, `--functions DIR/$exe/functions.csv` and `--symbols DIR/$exe/symbols.csv`. All escape through `ninja_path` after the same safe-path check as the regeneration command. The default text is unchanged, byte for byte.

## DI rows and their commits

| Row | What | RED | GREEN |
|-----|------|-----|-------|
| DI-05 (05-REVIEW 15) | backslash continuation in the D-12 parser | `dee1491` | `a71dd7a` |
| DI-04 (05-REVIEW 12a) | duplicate/overlapping own publics refused | `5eab11a` | `426e8ff` |
| DI-04 (05-REVIEW 12b, 12c) | end-of-public and wrong-inside targets pinned | `5eab11a` | (already behaved; pinned) |
| DI-19 10a | fixup frame method checked | `5eab11a` | `426e8ff` |
| DI-19 10c | LE kinds named in relocpair (and test_relocs) | `5eab11a` | n/a (test-only) |
| DI-19 10d | byte-dump regex case-insensitive | `5eab11a` | n/a (test-only) |
| DI-06 part c | rules carry a non-default config tree | `19a4f5b` | `de94a5b` |

## Task Commits

1. **Task 1 (tracer): continuation is dead for configure and check.** RED `dee1491` (test), GREEN `a71dd7a` (fix). Tracer gate: interactive, end-of-phase, verify is automated only, so I re-ran `uv run pytest -q tests/test_configure.py tests/test_check.py` (154 passed, 3 skipped) and expanded.
2. **Task 2: relocs own publics, 12b/12c, frame, test helpers.** RED `5eab11a` (test), GREEN `426e8ff` (fix)
3. **Task 3: config-consistent rules.** RED `19a4f5b` (test), GREEN `de94a5b` (fix)

The GREEN commits use `fix(06-03)` because the plan's actions say so. The plan is `type: execute`, not `type: tdd`, so the plan-level feat-commit gate does not apply. Every tdd task has its RED test commit before its GREEN commit.

## RED evidence (semantic assessment)

- Task 1: 7 targets failed on assertions. Two got no problem where one was expected, because the marker or definition was still counted live. `[string]` reported `line 10:` where `line 11:` was expected (the literal blanking dropped a line break). `test_directive_continuation_is_one_directive` got `#if` refused. The three `source_marks` probes returned the wrong marked/defined sets. No import, collection or syntax faults.
- Task 2: 6 failed for the planned reasons. Both `duplicate_own_publics` cases failed with `DID NOT RAISE RelocError`, and all four `unexpected_frame` cases failed because `RelocResult.ok` was True. The 12b and 12c tests passed as the plan expected: they pin behaviour that was already correct.
- Task 3: `test_custom_config_rules_name_its_manifest` failed because `--manifest other/targets.toml` was not in `command = uv run reverseapoc check-orig --orig orig`. Both golden tests passed against the code before the change, as intended.

## F20: the observed frame set

Commands (host, main checkout's Watcom tree):

```
uv run reverseapoc cc src/ufo2p/u_000a34f0.c -o build/06-03/u_000a34f0.obj --watcom-dir "C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/third_party/watcom"
uv run reverseapoc cc src/tacp/u_00054f20.c -o build/06-03/u_00054f20.obj --watcom-dir "C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/third_party/watcom"
uv run python -c "from pathlib import Path; from reverseapoc.omf import read_object; ..."  # frame_method of every FIXUPP
```

Both compiled `OK ... wcc386@10.6 ... Version 10.6`. Every FIXUPP:

| Object | Field | Frame | Target | Kind |
|--------|-------|-------|--------|------|
| u_000a34f0.obj | _TEXT+0x1 | F1 | extern func_000A3990_ | self-relative, loc 9 |
| u_000a34f0.obj | _TEXT+0x8 | F1 | extern _D_0012EFAC | segment-relative, loc 9 |
| u_00054f20.obj | _TEXT+0x1 | F1 | extern func_00011500_ | self-relative, loc 9 |
| u_00054f20.obj | _TEXT+0x6 | F1 | extern _D_0028DF70 | segment-relative, loc 9 |

The raw FIXUPP bytes (`a4 01 16 02 01 ...`) give frame datum 2, and the module's GRPDEFs are DGROUP (1) and FLAT (2), so the frame is F1 FLAT. The allowed set is {F1}. After the change, `check.checked_functions` on both real objects still returns `func_000A3980 ok` and `func_00055080 ok`. The flagged assumption holds: one frame method.

## Files Created/Modified

- `configure.py`: continuation-aware `_NOT_CODE` and `_live_code` (`_logical_lines`), `_blank` keeps a literal's spliced line breaks, `Layout.rule_config` and `_config_arguments` for the config-reading rules, and the `DEFAULT_CONFIG`/`FUNCTIONS_NAME`/`SYMBOLS_NAME` constants.
- `tools/reverseapoc/relocs.py`: the overlap refusal in `_check_own_publics`, `FRAME_GROUP`/`FLAT_CODE_FRAMES` and the frame check in `_fixup`, plus the docstring.
- `tests/test_configure.py`: the DI-05 probes and tests, the F4 golden literal and the DI-06c tests.
- `tests/test_relocs.py`: the 12a-12c and frame tests, the case-insensitive `_BYTE_DUMP`, and named LE kinds.
- `tests/relocpair.py`: `SRC_OFF32`, `FLAT_LNAME`/`FLAT_GROUP`/`FLAT_FRAME` (taking `FRAME_GROUP` from relocs), a FLAT GRPDEF in `our_segment`, and a `frame` keyword on `call`/`absolute`.
- `tests/test_check.py`, `tests/test_objdiff_real.py`: their OMF builders gain the FLAT GRPDEF (see Deviations).

## Decisions Made

See key-decisions in the frontmatter. One addition: with `--config` pointing at the repository's own tree but build.ninja written elsewhere, no flags are emitted (`test_default_config_dir_adds_no_rule_flags`), because every verb already defaults to that tree.

## Deviations from Plan

- **Orchestrator ruling F4: pin the golden on a synthetic tree.** `test_default_config_render_is_unchanged` builds the `_split_tree` config/src tree in tmp_path, collects its units and renders with the default `Layout()`. The result is compared with the literal `DEFAULT_RENDER_GOLDEN`, captured from the code before the change. Interpretation: the ruling asks the default render to contain none of `--config`, `--manifest`, `--functions` or `--symbols`. The regeneration rule always carries `--config config` (it existed before this plan and must stay), so the assertion covers the commands of the config-reading rules (check_orig, rebuild, target, asm, land). The golden literal pins the rest of the text, the configure rule included.
- **Orchestrator ruling F20: observe the real frame method.** I compiled both matched units on the host with the main checkout's Watcom tree and listed `frame_method` for every FIXUPP: the observed set is {F1}, with the FLAT group as frame datum. The allowed set is exactly that, named `FRAME_GROUP` / `FLAT_CODE_FRAMES`. Commands and results are in the section "F20: the observed frame set" above. I used the literal main-checkout path, because the harness refuses `$(...)` in git-bearing commands.

### Auto-fixed Issues

**1. [Rule 1 - Bug] A literal spliced across lines dropped its line breaks**
- **Found during:** Task 1 RED (`test_continuation_keeps_directive_line_numbers[string]`)
- **Issue:** `_blank` turned a string like `"a\<newline>b"` into `""`, which deleted a line break, so every later directive was reported one line early.
- **Fix:** `_blank` now returns the quote, the literal's line breaks, then the quote again, so the physical layout is kept.
- **Files modified:** configure.py
- **Commit:** `a71dd7a`

**2. [Rule 3 - Blocking] Synthetic OMF fixtures used frame F5, which the frame check now refuses**
- **Found during:** Task 2
- **Issue:** omfimage.fixup defaults to frame F5. Every relocpair fixup, and the OMF builders in tests/test_check.py and tests/test_objdiff_real.py that use relocpair's `call`/`absolute`, would have failed the new F1-only check. Their modules also had no GRPDEF for an F1 datum to name.
- **Fix:** relocpair frames every fixup `FLAT_FRAME` (F1, GRPDEF 1 = FLAT) and adds the FLAT GRPDEF to `our_segment`. The three outside builders add `FLAT_LNAME` and `grpdef(4)`. tests/test_check.py and tests/test_objdiff_real.py are outside this plan's `files_modified`. The change is to test fixtures only: no assertion changed, and every existing test passes.
- **Files modified:** tests/relocpair.py, tests/test_check.py, tests/test_objdiff_real.py
- **Commit:** `5eab11a`

**3. [Rule 2 - Missing critical] asm also gets `--manifest` for a custom config**
- **Found during:** Task 3
- **Issue:** the plan names `--functions`/`--symbols` for asm, but asm also picks its EXE from `--manifest`. Without it, a config tree whose EXE is not in the repository manifest would still read the repository's targets.toml.
- **Fix:** asm's arguments start with `--manifest DIR/targets.toml`. The test asserts it.
- **Commit:** `de94a5b`

**4. [Additional test] `test_directive_continuation_is_one_directive` and `test_default_config_dir_adds_no_rule_flags`, and named LE kinds in test_relocs.py too**
- These pin the logical-directive behaviour, the default-tree detection in `Layout.for_base`, and 10c for `fixup_record(2/7, ...)` in test_relocs.py as well as relocpair.

---

**Total deviations:** 2 orchestrator rulings applied (F4, F20). 3 auto-fixed (1 bug, 1 blocking, 1 missing critical) and 1 note on extra tests. **Impact:** no scope creep. check.py, targets.toml, watcom.toml and orig/ are untouched, and configure.py changed only as Tasks 1 and 3 specify.

## Issues Encountered

- objdiff-cli and ninja are not on the host, so `reverseapoc check` and the unskipped real check tests run only in the container (plan 06-16 re-runs every real relocation test). On the host I ran the relocation check on the real objects directly through `check.checked_functions`, in a scratch script outside the repo.
- On Windows, Python `write_text` wrote CRLF into three test files. The index stayed LF, and I normalised the working copies to LF, so no commit carries CR.

## Verification

- `uv run pytest -q tests/test_configure.py tests/test_check.py`: 154 passed, 3 skipped (the skips are pre-existing platform skips).
- `uv run pytest -q tests/test_relocs.py tests/test_land.py tests/test_check.py`: 115 passed.
- `uv run pytest -q tests/test_configure.py`: 104 passed, 3 skipped.
- `uv run pytest -q && uv run ruff check .`: 1437 passed, 215 skipped (real-file skips: the worktree has no orig/, third_party/, objdiff or ninja). Ruff: all checks passed.
- Acceptance: `grep -n "fixup_record(7" tests/relocpair.py` prints nothing. Every named test exists. `test_own_segment_layout_coincidence_is_not_trusted` is still present and passes. Task 1's commits list only configure.py and tests/test_configure.py.

## Next Phase Readiness

- hooks.py (06-12) can reuse the continuation-aware parser (`_NOT_CODE`, `_live_code`).
- 06-09 updates `DEFAULT_RENDER_GOLDEN`: its only diff is the `| ...prov.json` implicit outputs of the cc edges (ruling F4 consumer).
- Open question (not in this plan): `land` reads `--src` too. A non-default `--src` is passed back only to the regeneration rule, not to land.

## Self-Check: PASSED

- FOUND: configure.py, tools/reverseapoc/relocs.py, tests/test_configure.py, tests/test_relocs.py, tests/relocpair.py
- FOUND commits: dee1491, a71dd7a, 5eab11a, 426e8ff, 19a4f5b, de94a5b (`git log 021a58b..HEAD`, 6 commits)

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
