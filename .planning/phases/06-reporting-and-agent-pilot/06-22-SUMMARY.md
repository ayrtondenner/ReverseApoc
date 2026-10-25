---
phase: 06-reporting-and-agent-pilot
plan: 22
subsystem: listings
tags: [recomp.fyi, decomphub, readme, progress, listings]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-01 spike 006 verdict INVALIDATED (own agent layer); 06-16 gate-written status.csv for both EXEs"
provides:
  - ".recomp.json with the Pages progress link and notes that match the current pipeline (status stays exploring)"
  - "README Progress section that explains matched/partial/unmatched/library/uncovered and links decomphub.progress.json"
  - "docs/DECOMPHUB_VERIFICATION.md, the two-sentence maintainer statement the owner cites (06-26)"
  - "tests/test_listings.py: recomp.fyi v1 schema pins, README progress needles, verification file shape"
affects: [06-24, 06-26, 06-27, recomp.fyi, decomphub]

actuals:
  tokens: 3290
  tasks: 2
  commits: 4
plan_head_before: 5d391a95fc7e771f05cab9d5985e9a315bc99097
plan_head_after: cf5dec3103dba6fb94cad5eb6a20b230a59c3456

tech-stack:
  added: []
  patterns:
    - "Third-party schema pinned as constants with a dated `# from recomp.fyi/schema/v1.json, 2026-10-24` comment, because CI has no network"
    - "Doc checks are pure helpers (_schema_problems, _non_https, _stale_note_phrases, _sentences) with planted-defect tests that prove each can fail"

key-files:
  created:
    - tests/test_listings.py
    - docs/DECOMPHUB_VERIFICATION.md
  modified:
    - .recomp.json
    - README.md

key-decisions:
  - "tests/test_listings.py checks status against the enum, not against `exploring`: 06-27 moves it to in-progress and runs this test file without editing it"
  - "The notes test reads spike 006's `verdict:` line, so decomp.wtf may return to the notes only if a later spike record says VALIDATED"
  - "README gives no uncovered byte counts: they change as rows are added, and the page shows them"

patterns-established:
  - "Listing metadata (recomp.fyi, DecompHub, README progress) is pinned by offline tests; the live reads stay third-party and are checked in 06-27"

requirements-completed: [RPT-05, RPT-03]

coverage:
  - id: D1
    description: ".recomp.json validates against the pinned recomp.fyi v1 property set and status enum, every link is https, it links the Pages progress page, keeps ai-assisted and its notes name neither retrokit nor decomp.wtf (spike 006 INVALIDATED)"
    requirement: RPT-05
    verification:
      - kind: unit
        ref: "tests/test_listings.py#test_recomp_json_keys_and_enum, #test_recomp_json_links_are_https, #test_recomp_json_lists_the_progress_page, #test_recomp_json_notes_match_the_pipeline"
        status: pass
      - kind: unit
        ref: "tests/test_listings.py#test_recomp_checks_catch_planted_defects, #test_note_check_follows_the_spike_verdict"
        status: pass
    human_judgment: false
  - id: D2
    description: "README Progress section keeps the three Pages URLs, explains the five categories, links [Progress data](decomphub.progress.json) and no longer carries the Phase 6 placeholder"
    requirement: RPT-03
    verification:
      - kind: unit
        ref: "tests/test_listings.py#test_readme_progress_section"
        status: pass
    human_judgment: false
  - id: D3
    description: "README retrokit row and GhidraMCP cell keep their original text and gain an annotation"
    verification:
      - kind: other
        ref: "git diff -U0 5d391a9..cf5dec3 README.md (both rows: original cell text followed by the annotation)"
        status: pass
    human_judgment: false
  - id: D4
    description: "docs/DECOMPHUB_VERIFICATION.md is a two-sentence ownership statement naming ayrtondenner, the repository and decomphub.progress.json"
    requirement: RPT-05
    verification:
      - kind: unit
        ref: "tests/test_listings.py#test_decomphub_verification_file, #test_sentence_count_skips_headings_and_url_dots"
        status: pass
    human_judgment: false
  - id: D5
    description: "The wording of the README Progress section and of the notes reads as accurate and honest to the owner (AI-assisted, no overclaim about Pages before the owner enables it)"
    verification: []
    human_judgment: true
    rationale: "Tests pin needles, not prose quality or the claim's accuracy against the live Pages site, which 06-24 deploys and the owner enables (D-27)"

duration: 12min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 22: Listings metadata Summary

**.recomp.json links the Pages progress page and describes the real pipeline (own oracle, Ghidra headless with the lastonesky loader, own agent layer per spike 006), README's Progress section explains the five categories and links decomphub.progress.json, and a two-sentence DecompHub ownership statement exists, all pinned by offline tests.**

Execution context nonce: c54711309345e4b2

## Performance

- **Duration:** 12 min
- **Started:** 2026-10-25T14:16:20Z
- **Completed:** 2026-10-25T14:28:03Z
- **Tasks:** 2 (Task 1 tracer, Task 2 auto; both tdd)
- **Files modified:** 4

## Accomplishments

- `.recomp.json`: links gain `{"label": "Progress", "url": "https://ayrtondenner.github.io/ReverseApoc/"}`; notes rewritten (no retrokit, no decomp.wtf; the own oracle, Ghidra 12.1.4 headless with the lastonesky loader, the own agent layer after spike 006, the gate-written status table and the `X-COM_Apocalypse_DOS_report` artifact). `status` stays `exploring`, `ai-assisted` stays in tags (D-32, DI-37).
- README Progress section (DI-08): badge and mosaic lines kept; text says the figures come from `config/ufo2p/status.csv` and `config/tacp/status.csv`, written by `reverseapoc gate`, on every push to `main`; defines matched, partial, unmatched, library (outside the percentage) and uncovered (mostly alignment filler; the 3-byte UFO2P tail is not counted); links `[Progress data](decomphub.progress.json)` (D-26, D-29, D-50).
- README retrokit row: `(not used: Phase 5 runs Ghidra headless in the Docker image with the lastonesky loader)` appended; GhidraMCP: `(Later)` appended (DI-21, D-41). Line numbers moved from L62/L139 to L69/L146 because the Progress section grew.
- `docs/DECOMPHUB_VERIFICATION.md`: two sentences, ayrtondenner owns and maintains https://github.com/ayrtondenner/ReverseApoc and publishes decomphub.progress.json from it (D-31, DI-34). Nothing was filed with DecompHub or recomp.fyi.

## Task Commits

1. **Task 1 RED** - `8b8fa37` test(06-22): add failing recomp.fyi schema and notes tests for .recomp.json
2. **Task 1 GREEN** - `a9011c7` feat(06-22): list the progress page and the current pipeline in .recomp.json
3. **Task 2 RED** - `3b250ce` test(06-22): add failing README progress and DecompHub verification tests
4. **Task 2 GREEN** - `cf5dec3` docs(06-22): README progress section, retrokit/GhidraMCP annotations, DecompHub verification

## TDD Gate Compliance

- **RED 1** (`8b8fa37`): `uv run pytest -q tests/test_listings.py --junitxml=build/06-22/red1-junit.xml`, exit 1, 9 passed / 2 failed. Classifier `check tdd-red-evidence` on the JUnit record (target `test_recomp_json_lists_the_progress_page`): `RED_EVIDENCE_OK`, `target_test_failed`. Semantic assessment: both failures are the planned assertions; the progress link was missing (`links` held only the OpenApoc URL) and the notes test reported `['retrokit', 'decomp.wtf']`. No collection, import or fixture fault.
- **GREEN 1** (`a9011c7`): 11 passed. Tracer gate (interactive, `end-of-phase`, automated-only verify): verify re-run green, expanded to Task 2.
- **RED 2** (`3b250ce`): `uv run pytest -q tests/test_listings.py --junitxml=build/06-22/red2-junit.xml`, exit 1, 14 passed / 2 failed. Classifier on both targets (`test_readme_progress_section`, `test_decomphub_verification_file`): `RED_EVIDENCE_OK`, `target_test_failed`. Semantic assessment: README failed on the missing `[Progress data](decomphub.progress.json)` link; the verification test failed on `assert VERIFICATION.is_file()`. A first run failed with FileNotFoundError from `read_text`, which is not an assertion, so I added the `is_file()` assertion before committing RED.
- **GREEN 2** (`cf5dec3`): 16 passed. The plan names this commit `docs(06-22)` rather than `feat(...)`; it is the GREEN for Task 2.
- RED records are in the gitignored `build/06-22/` (red1-record.json, red2-test_*.json). Their `runStartedAt` values are estimates a few seconds before the report mtime; `reportModifiedAt` is the file's real mtime.

## Verification

- `uv run pytest -q tests/test_listings.py tests/test_hygiene.py`: 81 passed, 3 skipped (`only inside the container`, test_hygiene.py:551).
- Full host suite with REVERSEAPOC_ORIG, REVERSEAPOC_WATCOM_DIR and REVERSEAPOC_GHIDRA_EXPORT pointing into the main checkout: **2282 passed, 41 skipped, exit 0** (402 s; log `build/06-22/host-suite.log`). Skip reasons: watcom-media not present (5 lines, REVERSEAPOC_WATCOM_MEDIA not set), Ghidra analyzeHeadless not found (5), symlink privileges (2), POSIX-only, Windows file names, non-UTF-8 byte names, clang, ninja, objdiff-cli, only inside the container (1 each). None comes from tests/test_listings.py.
- `uv run ruff check .`: All checks passed.
- Acceptance: `.recomp.json` parses and `status` is `exploring`; README contains `[Progress data](decomphub.progress.json)` once; the retrokit row and the GhidraMCP cell keep their original text and gain the annotation (`git diff -U0`).
- The container suite was not run: the dispatch forbids docker from a worktree.

## Files Created/Modified

- `tests/test_listings.py` (new): the six planned tests plus `test_recomp_checks_catch_planted_defects`, `test_note_check_follows_the_spike_verdict` and `test_sentence_count_skips_headings_and_url_dots`.
- `.recomp.json`: progress link, current notes.
- `README.md`: Progress section; retrokit and GhidraMCP annotations.
- `docs/DECOMPHUB_VERIFICATION.md` (new).

## Decisions Made

- The status test accepts any value in the v1 enum. 06-27 sets `in-progress` and runs this file unchanged (06-27-PLAN.md L137), so pinning `exploring` would break 06-27.
- The notes check reads spike 006's frontmatter `verdict:` line, the same way test_hygiene.py reads spike 005's.
- The README gives no uncovered byte counts. The figures (UFO2P 25,787, TACP 35,349 after 06-04) change when rows are added, and the Pages site shows the current ones.

## Deviations from Plan

No orchestrator ruling applies to 06-22 (rulings.md has no "## 06-22" section). R-A: no new skips. R-B: build/06-22 evidence was written only by shell redirection and by the programs' own writes.

1. **[Rule 2 - test strength] Planted-defect tests added.** I added three small parametrized tests so that each check can be shown to fail (the project's "a check is only worth something if it can fail" pattern from test_hygiene.py). The six planned tests are unchanged. Files: tests/test_listings.py. Commits: 8b8fa37, 3b250ce.
2. **[Plan detail] tools/progress.py was not on this base.** Task 2's read_first names it, but it is 06-18's output and runs in the same wave. I took the category meanings from 06-CONTEXT D-26/D-50, tools/reverseapoc/status.py (a matched or partial row; a missing row means unmatched) and gate.py `_merge_partial` (partial means objdiff above 0%, not matched).
3. **[Plan detail] README line numbers.** The annotated rows are now at L69 and L146; the plan named L62 and L139 before the Progress section grew. (After fix round 1 the annotations moved again; the tests find the rows by section, not by line number.)
4. **Owner ruling 2026-10-25: no `help` field (removes recomp.fyi's 'wants help' tag).**
   - The `help` array was removed from .recomp.json, and nothing else in the file changed.
   - `test_recomp_json_asks_for_no_help` pins the absence. `help` stays in the pinned v1 property set, because the schema allows it.
   - No test or live doc expected the field. Only the dated research snapshot docs/research/notes-progress-reporting-recompfyi.md lists `help` among the schema fields, and it is left as written.
   - Commits: e6656f0 (RED), e360d32 (GREEN).

**Total deviations:** 1 auto-added (Rule 2), 2 recorded plan details, 1 owner ruling (fix round 2); fix round 1 is in its own section below. **Impact:** none on scope; no file outside files_modified was touched besides this SUMMARY.

## Issues Encountered

- The harness refused several compound shell commands (heredocs, inline `python -c` with multiple statements, `git` mixed with other steps), saying it could not verify they stayed in the worktree. I split them into plain commands or used Edit/Write and a scratchpad script. I did not work around any guardrail-hook deny, and none happened.
- REQUIREMENTS.md was not edited. RPT-03 and RPT-05 are shared with other wave-7 plans (06-18, 06-24, 06-19, 06-26, 06-27), so the orchestrator marks them after merge.

## User Setup Required

None. The owner files the DecompHub maintainer claim citing docs/DECOMPHUB_VERIFICATION.md at the pilot checkpoint (06-26, D-31).

## Next Phase Readiness

- 06-24 (Pages workflow) publishes the URLs the README and `.recomp.json` now point at. 06-27 moves `.recomp.json` to `in-progress` and reruns tests/test_listings.py.
- The game's tick rate (OpenApoc #997) was not touched in this plan.

## Fix round 1

FIX_BASE 32314b5. Source: review-06-22.md, the coordinator's rulings, and an addition with the definitions tools/progress.py (06-18) implements. Each change has a RED test commit before its docs commit.

| Item | Change | Test (tests/test_listings.py) | Commits |
|---|---|---|---|
| I1 | The percentage's denominator is game + thunk bytes plus the uncovered bytes (D-50) | `test_readme_percentage_counts_uncovered_bytes` (`DENOMINATOR`) | df8d641, 0c858b0 |
| I2 | Unmatched now means no gate-written matched or partial row, and the rebuilt EXE keeps that function's original bytes through the in-place splice. The INCLUDE_ASM stub claim is gone. | `test_readme_progress_makes_no_stub_claim` | df8d641, 0c858b0 |
| I3 | The four Approach lines that name decomp.wtf fork mode or an MCP server keep their text and gain a note, as with D-41: spike 006 INVALIDATED (06-01), the agent layer is our own (D-03, D-04), there is no MCP server (D-44), and agents call the Bash-allowlisted attempt wrapper | `test_readme_approach_annotates_the_agent_layer`, `test_agent_line_check_catches_unannotated_lines` | df8d641, 0c858b0 |
| Minor | Category needles are matched as bold `**name**:` items, so "unmatched" no longer satisfies "matched" | `test_readme_progress_section` (`CATEGORIES`) | df8d641 |
| Minor | The Progress section names data-in-code (excluded) and its inputs: status.csv plus functions.csv and units.csv | `test_readme_progress_section` (`PROGRESS_NEEDLES`) | df8d641, 0c858b0 |
| Minor | Toolchain summary uses the DI-25 wording: 10.6 default rule; 10.5, 10.6 and 11.0 tied on game code after the two Phase 5 leaf matches; links docs/toolchain.md | `test_readme_toolchain_summary_is_current` | df8d641, 0c858b0 |
| Minor | The second block of test constants moved to the top of the file | (structure only) | df8d641 |
| Addition | The combined figure comes from summed bytes; thunks count as code; the function ratio is defined | `test_readme_percentage_counts_uncovered_bytes` (`COMBINED`), `test_readme_partial_gets_no_credit` (`RATIO`) | 3e118fc, 364f8ed |
| Addition | Partial counts for nothing in the percentage or the ratio; only report.json's fuzzy percent credits it | `test_readme_partial_gets_no_credit` (`PARTIAL_RULE`) | 3e118fc, 364f8ed |
| Addition | Uncovered means no functions.csv row of any kind covers the bytes; library is outside both sides of the percentage; Pages regenerates progress.json, the shield and report.json on push; decomphub.progress.json changes only when a `gate EXE/UNIT` run passes | (text only, brief) | 364f8ed |

- **RED evidence:** df8d641 failed 5 of 24 tests and 3e118fc failed 2 of 25. Every failure was the planned assertion; there were no collection or import errors. The reports are `build/06-22/fix1-red.out` and `build/06-22/fix1b-red.out`.
- **After the round:** tests/test_listings.py has 25 passed. With hygiene: 90 passed, 3 skipped (`only inside the container`). Host suite: 2291 passed, 41 skipped, exit 0, with the same skip reasons as before and none in tests/test_listings.py. ruff: All checks passed.
- **Unchanged:** the present-tense Pages and report wording, as ruled. The README's goal framing and its honesty: two matched functions, and the EXEs are not rebuilt from C.

## Fix round 2

FIX_BASE 39e27d0. Source: owner ruling 2026-10-25, relayed by the coordinator. Nothing was sent to recomp.fyi and nothing was pushed.

| Item | Change | Test (tests/test_listings.py) | Commits |
|---|---|---|---|
| Owner ruling 2026-10-25 | No `help` field in .recomp.json, which removes recomp.fyi's 'wants help' tag. No other key changed, and the file still validates against the pinned schema. | `test_recomp_json_asks_for_no_help` | e6656f0, e360d32 |

- **RED evidence:** e6656f0 failed 1 of 26 tests, on `assert 'help' not in {...}` (`build/06-22/fix2-red.out`).
- **After the round:** tests/test_listings.py has 26 passed. Host suite: 2292 passed, 41 skipped, exit 0 (`build/06-22/fix2-host-suite.log`), with the same skip reasons as before and none in tests/test_listings.py. ruff: All checks passed.

## Self-Check: PASSED

- All four files in files_modified and this SUMMARY exist; `git diff --name-status 5d391a9 HEAD` shows only them (3 added, 2 modified, no deletions).
- Commits 8b8fa37, a9011c7, 3b250ce and cf5dec3 are on this branch (`git log 5d391a9..HEAD`); the working tree is clean.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
