---
phase: 06-reporting-and-agent-pilot
plan: 13
subsystem: tooling
tags: [python, context-pack, difflib, capstone, AGT-08, D-13, D-14]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-06: asm.file_name, one listing per functions.csv row (<kind>_<start>.s for ambiguous names)"
  - phase: 06-reporting-and-agent-pilot
    provides: "06-03/06-09: configure.code_text, normalize_source, _NOT_CODE, _DEFINITION (the D-12 parser) and fileio.write_atomic"
provides:
  - "contextpack.build_pack: ten sections in the D-13 order, a 24,576-byte UTF-8 cap, cuts in the D-14 order (look-alikes, callers, draft), `pack_bytes` and `truncated`"
  - "contextpack.write_pack: context.md only under a resolved build/driver/ path, written with fileio.write_atomic"
  - "contextpack.CallIndex: callees of every game/thunk row (asm.walk + asm.branch_target) and the reverse caller map"
  - "contextpack.definitions: definition heads and sources sliced from the original unit text through an explicit offset map (ruling R2-3)"
  - "contextpack.externs, mnemonics, lookalikes (SequenceMatcher on mnemonics, floor 0.6, top 3, ties by start) and gather (build_pack's keywords for one row)"
affects: [06-15 context verb and attempt context, 06-14/06-25 driver, attempts.jsonl pack_bytes/truncated]

actuals:
  tokens: 9701  # chars/4 over the realized diff: 38,805 bytes in 2 new files
  tasks: 3
  commits: 6
plan_head_before: 325c6066b67916ec70c794d79ebfabfcea2178c1
plan_head_after: 23045554325e21e6ca61531db345027958b4d1ff

tech-stack:
  added: []
  patterns:
    - "Slice the original text through an explicit offset map (each derived character keeps its original index) when a normalised or blanked copy decides what to find"
    - "A size cap enforced by re-rendering after each single cut, so the recorded `truncated` list and the measured bytes always agree"

key-files:
  created:
    - tools/reverseapoc/contextpack.py
    - tests/test_contextpack.py
  modified: []

key-decisions:
  - "Definition heads: configure.code_text decides which func_ names are defined at file scope; the head is found in a same-length blanked copy (comments, literals, directives and dead #if 0 lines become filler) of normalize_source's text, and sliced from the original through the offset map (R2-3)"
  - "A callee is any other row whose start a direct call or jump of the row lands on, so a tail call counts; an off32 fixup whose target is inside a code row is a code pointer, not an extern"
  - "Cut order inside a section: the last look-alike (least similar) first, then callers from the highest address; a section emptied by cuts says none, and the header line `Truncated:` lists every cut"
  - "Every free-text input (listing, unit, common.h, draft, idioms, notes, look-alike C) sits in a fenced block whose fence is longer than any backtick run inside it, so a heading or fence in the input cannot break the pack's structure"
  - "gather derives look-alike C from unit_texts (matched rows whose definition the unit file holds) instead of a separate matched_sources argument"

patterns-established:
  - "contextpack.definitions is the one way to get a matched function's C text out of a unit file with its original bytes"

requirements-completed: [AGT-08]  # copied from the plan; the `context` verb and the attempt wrapper's `context` are wired in 06-15

coverage:
  - id: D1
    description: "build_pack returns the ten D-13 sections in order; empty inputs say none; write_pack writes context.md only under build/driver/"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_contextpack.py#test_pack_has_every_section_in_order"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_write_pack_stays_under_build_driver"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_empty_inputs_say_none"
        status: pass
    human_judgment: false
  - id: D2
    description: "Callers, callees and externs come from the LE; a matched neighbour carries its prototype sliced from the original unit text (R2-3, tested on the real src/tacp/u_00054f20.c)"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_contextpack.py#test_callers_and_callees_from_the_le"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_matched_callee_carries_its_prototype"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_externs_are_the_d_symbols_the_row_touches"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_callee_prototype_offsets_survive_comments_trigraphs_and_crlf"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_callee_prototype_on_the_real_tacp_unit"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_callee_prototype_unreadable_unit_gives_none"
        status: pass
    human_judgment: false
  - id: D3
    description: "Look-alikes ranked by mnemonic similarity (floor 0.6, top 3, ties by start); the 24,576-byte cap kept at the boundary and cut in the D-14 order one byte over; required sections never cut; deterministic output"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_contextpack.py#test_lookalikes_rank_by_mnemonic_similarity"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_lookalikes_come_from_matched_rows_with_c"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_pack_at_the_cap_is_kept_whole"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_pack_one_byte_over_is_truncated_in_order"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_required_sections_alone_over_the_cap"
        status: pass
      - kind: unit
        ref: "tests/test_contextpack.py#test_pack_is_deterministic"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 13: Per-function context pack library Summary

**`contextpack.py` builds the AGT-08 pack: the listing, the unit, callers and callees from a one-pass call index over the LE (a matched neighbour shows its prototype, sliced from the original unit text through an offset map), the `D_` externs, common.h, the draft, the idioms, the notes and up to 3 look-alikes ranked by SequenceMatcher on mnemonics. It caps the pack at 24,576 UTF-8 bytes by cutting look-alikes, then callers, then the draft, and writes it only under build/driver/.**

Execution context nonce: 10c9d726ea2bb85e

## Performance

- **Duration:** about 11 min
- **Started:** 2026-10-25T04:15:05Z
- **Completed:** 2026-10-25T04:26:05Z
- **Tasks:** 3
- **Files modified:** 2 (both new)

## Accomplishments

- `build_pack` renders `# Context pack: <name>`, a data-not-instructions line, a `Truncated:` line, then ten `## ` sections in the D-13 order: Target listing, Unit file, Callers, Callees, D_ externs, include/common.h, Ghidra draft, Matching idioms, Earlier notes, Look-alikes. A section with no input says `none`. `Pack.to_json()` gives `pack_bytes`, `truncated` and the section titles for attempts.jsonl.
- The cap: after each cut the pack is rendered again and measured as `len(text.encode("utf-8"))`. A pack of exactly 24,576 bytes is kept whole. At 24,577 bytes the last look-alike is cut, then the others, then callers from the last, then the draft. If the pack is still over with all of these cut, ContextPackError names the size.
- `write_pack` refuses any directory whose resolved parts, casefolded, do not contain `build/driver`. It checks before it creates anything, then writes `context.md` with `fileio.write_atomic` (threat T-06-29).
- `CallIndex.build` walks every game and thunk row once. On the real UFO2P.EXE it indexed 1553 rows in 6.3 s. A smoke run built packs for 0x000A3980 and 0x0008A0E0 (2589 and 2109 bytes, nothing truncated). It printed only sizes and counts, wrote no file, and read `orig/` from the main checkout without changing it.
- `definitions(text)` returns each live file-scope `func_` definition's head and source as bytes of the original file (ruling R2-3). On the real `src/tacp/u_00054f20.c`, slicing at code_text's offsets gives `'P match).\n */\nvoid fu'`. `definitions` gives `void func_00055080(void)` and the exact four-line body.

## Task Commits

1. **Task 1 (tracer): sections, writer, empty inputs**
   - RED `9e15bf3` (test), GREEN `140e971` (feat)
2. **Task 2: callers, callees, externs, prototypes (D-13)**
   - RED `1b31b0b` (test), GREEN `d36064e` (feat)
3. **Task 3: look-alikes and the 24 KB cap (D-13, D-14)**
   - RED `d67ac29` (test), GREEN `2304555` (feat)

**Plan metadata:** the SUMMARY commit that follows (docs).

## TDD evidence

pytest's console report is not one of the formats `check tdd-red-evidence` supports, and `workflow.tdd_mode` is off. I judged RED by reading each failure, as 06-02, 06-03 and 06-09 did.

- **Task 1 RED:** collection failed with `ModuleNotFoundError: No module named 'reverseapoc.contextpack'`, because the module did not exist yet (06-02 had the same case). After GREEN, 4 passed. One test-helper bug turned up in GREEN: `_headings` counted a `## ` line inside the fenced idioms input. The helper now skips fenced blocks; it was fixed in the GREEN commit.
- **Task 2 RED:** 6 failed and the 4 Task 1 tests passed. The failures were AttributeErrors on `CallIndex`, `gather` and `definitions`, the planned missing features; nothing failed in setup. After GREEN, 10 passed on the first run. To check that the offset map matters, I swapped in an identity map: the tricky CRLF/trigraph unit then gave the head `'nd a ; */ int func_00010'`.
- **Task 3 RED:** 5 failed. `lookalikes` and `mnemonics` were missing (AttributeError). The one-byte-over test failed on its assertion (`() == ('look-alike func_00013000',)`), and the over-cap required test failed with `DID NOT RAISE`. `test_pack_at_the_cap_is_kept_whole` already passed, because nothing truncated yet; it pins the boundary and is not proof of new behaviour. Before the RED commit I fixed one setup error: the padding helper was not linear at pad 0, because an empty idioms section renders as `none`. After GREEN, 16 passed.

## Verification

- `uv run pytest -q tests/test_contextpack.py`: 16 passed.
- `uv run pytest -q tests/test_contextpack.py -k "callers or callee or externs"`: 6 passed (Task 2 verify).
- `uv run pytest -q`: 1614 passed, 217 skipped. `uv run ruff check .`: all checks passed.
- Acceptance greps: `PACK_CAP = 24576`, `def write_pack(`, `class CallIndex` and `def gather(` are in contextpack.py. `test_pack_at_the_cap_is_kept_whole` and `test_pack_one_byte_over_is_truncated_in_order` are in the tests.

## Files Created/Modified

- `tools/reverseapoc/contextpack.py` (new): `PACK_CAP`, `ORDER`, `ContextPackError`, `Neighbour`, `Lookalike`, `Section`, `Pack`, `build_pack`, `write_pack`, `Definition`, `definitions`, `CallIndex`, `externs`, `mnemonics`, `lookalikes`, `gather`.
- `tests/test_contextpack.py` (new): 16 tests. All inputs are synthetic (conftest `build_le_image` and made-up bytes), plus the committed C file `src/tacp/u_00054f20.c` that R2-3 names.

## Decisions Made

See `key-decisions` in the frontmatter. In short:

- the D-12 parser (code_text) decides what is defined, and the offset map decides where it is;
- tail calls count as callees, and code pointers are not externs;
- cuts are made from the end of each optional list;
- all free text is fenced.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling R2-3: no slicing by blanked offsets.** Prototype heads are not sliced at configure's blanked offsets. `definitions` rebuilds `normalize_source` with an explicit offset map: trigraphs, then CRLF, then blank-splice, in configure's order, and the result is checked equal to `configure.normalize_source`. It blanks comments and literals with same-length filler. It blanks directive and dead `#if 0` lines by comparing each logical line with `code_text`, which keeps the line count. Only names that `code_text` defines at file scope are kept (C is scanned through configure.code_text, as `## 06-12` asks). Tests: `test_callee_prototype_on_the_real_tacp_unit` (the real `src/tacp/u_00054f20.c`), `test_callee_prototype_offsets_survive_comments_trigraphs_and_crlf`, and `test_callee_prototype_unreadable_unit_gives_none` (lone CR and `#if FOO` give no head).
- **R-A (skip reasons):** no new test skips.
- **R-B (build/ evidence):** nothing was written under build/. Tests write only under tmp_path, and the smoke run wrote no file.

### Auto-fixed Issues

**1. [Plan text] gather's keywords**
- **Found during:** Task 2
- **Issue:** The plan's `gather` signature lists `matched_sources` and has no `common_h`, but `build_pack` needs `common_h`. Look-alike C can come from the unit texts that `gather` already receives.
- **Fix:** `gather` takes `common_h`, an optional `calls: CallIndex` (one index reused across functions) and `lookalike_floor` (default 0.6). It drops `matched_sources`: a matched row's C comes from `definitions(unit_texts[row.unit])`.
- **Files modified:** tools/reverseapoc/contextpack.py
- **Verification:** `test_callers_and_callees_from_the_le` passes `gather`'s dict straight to `build_pack`, and `test_lookalikes_come_from_matched_rows_with_c` covers the look-alike path.
- **Committed in:** d36064e, 2304555

**2. [Plan text] GPLv3 header**
- **Issue:** The plan asks for a GPLv3 header, but no file in tools/reverseapoc/ that is not derived from another project carries one.
- **Fix:** `# SPDX-License-Identifier: GPL-3.0-or-later` as line 1 of contextpack.py. docs/legal.md already covers tools/ as GPLv3.
- **Committed in:** 140e971

**3. [Test helper] fenced headings**
- **Found during:** Task 1 GREEN
- **Issue:** The test's `_headings` read `## ` lines inside fenced inputs.
- **Fix:** The helper skips fenced blocks.
- **Committed in:** 140e971

---

**Total deviations:** 3 plan-text or test-helper adjustments, plus ruling R2-3 applied and R-A/R-B followed.
**Impact on plan:** None in scope. Every must-have truth is covered by a test.

## Issues Encountered

- Python's `Path.write_text` on Windows writes CRLF, which surfaced while I edited the test file with a script. The committed blobs have no CR (I checked with `git show`). The working file was normalised to LF.

## Known Stubs

None. The `context` CLI verb and the attempt wrapper's `context` are 06-15's work, as the plan's objective says.

## Threat Flags

None. The only new surface is file writing, which `write_pack` confines to build/driver/ (T-06-29, mitigated and tested).

## User Setup Required

None.

## Next Phase Readiness

- 06-15 can wire `reverseapoc context`. It should build one `CallIndex` per run, call `gather(row, ..., calls=index)`, then `build_pack(**inputs)` and `write_pack(pack, build/driver/<run>/<exe>/<func>/)`. It should record `pack.to_json()`'s `pack_bytes` and `truncated` in attempts.jsonl.
- The idioms text passed to `gather` is the caller's choice. matching.md's "Known idioms" and "Relocation rules" headings are the planned source, and 06-15 picks them by heading.
- The floor of 0.6 is a starting metric (research A10). On the real UFO2P.EXE, the only matched rows today give ratios like 0.364, so most packs will have no look-alikes until more functions match.

## Self-Check: PASSED

- The three files exist: tools/reverseapoc/contextpack.py, tests/test_contextpack.py and this SUMMARY.
- The six task commits (9e15bf3, 140e971, 1b31b0b, d36064e, d67ac29, 2304555) are on this branch. `git diff --name-only 325c606..HEAD` lists only these three files. STATE.md, ROADMAP.md, config/ and orig/ are untouched.

## Fix round 1

Source: review-06-13.md (spec approved; one Important finding, minors). FIX_BASE 1c379f5. RED `4c9320d` (test), GREEN `11fcb13` (fix).

| Finding | Change | Test | RED evidence |
|---|---|---|---|
| I-1: the truncation header grew 22 bytes per cut item, so 600 unmatched callers raised although the required sections (22,581 bytes) fit | The `Truncated:` line counts cuts per section (`3 of 3 look-alikes, 118 of 400 callers, draft`), so it has a small fixed bound. The per-item list stays in `Pack.truncated` and `to_json()`. The error reads "the required sections plus the pack's frame and cut marks are N bytes ..." (fix round 2, N-1) and is raised only when the pack is still over with every optional section cut | `test_many_cut_callers_never_exhaust_the_cap`; `test_pack_one_byte_over_is_truncated_in_order` checks the new header | Raised the spurious `ContextPackError ... 35775 bytes` |
| M-1: the prototype was printed raw | `Neighbour.line` prints `" ".join(head.split())` | `test_prototypes_render_on_one_line` (CRLF, `## injected` in a comment, `#if 0`) | Assertion: `\r` found in the pack |
| M-2: a head could start with a stray backslash | `_declaration_start` skips backslash-newline splices as well as blanks | `test_callee_prototype_head_skips_a_splice_before_it` | Assertion: head `'\\  \t\nint ...'` |
| M-3: cut sections were not marked | A fully cut section says `cut (N items)` (the draft says `cut (1 item)`). A partly cut list ends with `... N more cut`. `none` still means no input | `test_cut_sections_are_marked_in_place` | Assertion: `'none' == 'cut (3 items)'` |
| M-4: the write guard accepted any build/driver pair, casefolded | `write_pack(pack, out_dir, *, root=REPO_ROOT)`: the resolved target must be `<resolved root>/build/driver` or below it, compared part by part as strings (exact case) | `test_write_pack_compares_build_driver_with_exact_case`, `test_write_pack_refuses_paths_outside_the_repo_build_driver` | TypeError: no `root` keyword yet |
| M-5: no `..` or link cases | `..` back out, a foreign `x/build/driver`, outside the repo, `build/drivers`, `build` alone; a junction (Windows, `_winapi.CreateJunction`) or a symlink (POSIX), chosen by `sys.platform` in one test; a separate symlink test that skips only with R-A's `symlink creation needs privileges on this host` (it skips on this host) | the three tests above plus `test_write_pack_refuses_a_link_out_of_build_driver`, `test_write_pack_refuses_a_symlink_out_of_build_driver` | TypeError, as for M-4 |
| M-6: no PARTIAL constant and no validation | `STATUS_MATCHED`, `STATUS_PARTIAL`, `STATUS_UNMATCHED`, `STATUSES`. `gather` refuses any other value and names it. A TODO(06-15) says to switch to 06-11's constants; 06-11's code is not imported | `test_gather_refuses_an_unknown_status` | AttributeError: no `STATUSES` |
| M-7: the real-file test pinned the exact name set | Asserts membership, the exact head, a source that is a substring of the file, and the exact body for TACP. Now covers `src/ufo2p/u_000a34f0.c` too. Both files are read as `read_bytes().decode("utf-8")` | `test_callee_prototype_on_the_real_units[...]` | Test-only change; passed at RED |
| M-9: bare `0x4` object flag | `asm.data_ranges(le)` | `_le_inputs` | Test-only change |
| M-10: no non-ASCII case | 2-byte `é` in idioms: at exactly 24,576 bytes the pack is kept whole with fewer characters than that; one byte over, the first look-alike is cut | `test_cap_counts_utf8_bytes_not_characters` | Passed at RED: the code already measured bytes. This pins it |
| M-8 (note only) | Not changed. `_normalized` repeats normalize_source's three steps and `_file_scope_matches` repeats `_file_scope_definitions`' brace-depth loop, using 8 private configure names (`_TRIGRAPH`, `_TRIGRAPHS`, `_BLANK_SPLICE`, `_SPLICE`, `_NOT_CODE`, `_DEFINITION`, `_ConditionalError`, and `code_text` and `normalize_source` alongside them). Two run-time checks catch drift: the result must equal `configure.normalize_source`, and the line count must equal `code_text`'s. The next change to configure.py could expose a match-yielding variant | n/a | n/a |

Judgment calls:
- "Required sections alone" includes the pack's fixed frame: the title, the preamble, the ten headings, the bounded `Truncated:` line and the short cut marks. These add up to a few hundred bytes and no longer grow with the number of cut items.
- On Windows, a `Build/Driver` spelling of a directory that already exists as `build/driver` resolves to the on-disk case and is accepted. It is the same NTFS directory. A spelling that does not exist keeps its case and is refused, as it is on the container's case-sensitive file system.

Verification after the fix: `uv run pytest -q tests/test_contextpack.py` gave 30 passed and 1 skipped (the R-A symlink reason). `uv run pytest -q` gave 1628 passed and 218 skipped. `uv run ruff check .` reported all checks passed.

## Fix round 2

Source: rereview-06-13-r1.md (fix round 1 approved; one Minor). FIX_BASE 7e185ef. This round changes wording only; behaviour is unchanged.

| Finding | Change | Test |
|---|---|---|
| N-1: the over-cap error said "the required sections alone are N bytes", but N also counts the pack's frame and the cut marks (a 1-character draft gave 421 bytes against 411 for the required sections alone) | The message now reads "the required sections plus the pack's frame and cut marks are N bytes in the context pack of <function> (every optional section cut), over the <cap>-byte cap". `build_pack`'s docstring says the same | `test_required_sections_alone_over_the_cap` matches the new text |

Points for 06-15, from the review's "cannot verify" list:
- (a) Pass every unit text of the EXE in `unit_texts`, not just the claimed unit. Otherwise neighbours and look-alikes in other units get no C.
- (b) Read unit files as `read_bytes().decode("utf-8")`, never `read_text`.
- (c) Use exactly the status vocabulary `STATUSES`; `gather` now enforces it.
- (d) Building the CallIndex took 6.3 s on UFO2P. That is fine once per `context` call.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
