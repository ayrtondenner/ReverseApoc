---
phase: 07-mechanics-first-decompilation
plan: 15
subsystem: reporting
tags: [progress-page, progress-json, mechanics, coverage, asm-list, pages-workflow, DEC-05]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-06 page fixes (bar nz class, legend, details list); 07-10 mechanics.toml / members CSV / asm list formats"
provides:
  - "derive_mechanics(config_dir, progress) -> Mechanics | None: per-item and per-tier must-match and full-closure figures (D-22)"
  - "progress.json \"mechanics\" key (null without mechanics.toml; PROGRESS_VERSION stays 1)"
  - "The Mechanics coverage page section: tiers, one <li> per in item, duplicates once"
  - "exclude_assembler(progress, asm_starts): signed asm rows outside the percentage (D-23), with assembler_bytes/assembler_functions in progress.json"
  - "pages.yml rebuilds on config/mechanics.toml, config/mechanics-members.csv, config/asm-functions.csv"
affects: [07-20, 07-22, 07-41, gsd-verify-work 7]

actuals:
  tokens: 21564     # chars/4 over the realized diff (86,256 chars, git diff 8a8f98e..f6b54c7)
  tasks: 3
  commits: 5        # git rev-list --count plan_head_before..HEAD, before the SUMMARY commit
plan_head_before: 8a8f98e5278614aa181fd6101c5ecb58ef29bead
plan_head_after: f6b54c7bc93547ae0429ccd876b94c23196ff7d6

tech-stack:
  added: []
  patterns:
    - "progress.py keeps its own stdlib copies of reverseapoc formats, pinned to the package's constants by a test (test_mechanics_constants_agree)"
    - "Two Progress views in main: derive() for the gate's DecompHub feed, exclude_assembler(derive()) for every published figure"
    - "Page CSS for an optional section is emitted only when the section is (coverage, assembler tick)"

key-files:
  created: []
  modified:
    - tools/progress.py
    - tests/test_progress.py
    - tests/test_progress_page.py
    - tests/test_treemap.py
    - tests/test_listings.py
    - README.md
    - .github/workflows/pages.yml
    - tests/test_workflows.py

key-decisions:
  - "report.json is built from the asm-excluded view too, so its combined matched_code_percent stays progress.json's (test_report_shape's invariant); only the DecompHub feed keeps the asm rows"
  - "An unsigned, edited or missing asm list moves nothing and raises nothing (07-20 commits an unsigned list first; mechanics check reports it)"
  - "A tier reads matched only when its must-match set is non-empty and every member is matched in status.csv; else located (rows exist) or not located yet"
  - "The SVG/HTML legend's library label is 'library or assembler': the 36-character 'library or assembler, not decompiled' starts the right-aligned SVG legend about 4 px from the bold heading; 'not decompiled' is stated in the assembler key line, MEASURED and the README"
  - "A coverage set with no bytes has percent 0.0, not objdiff's 100.0 for an empty total"
  - "The tier digest (members_sha256) is not recomputed in progress.py: a signed tier shows its sign-off; mechanics check in CI catches a stale digest"

patterns-established:
  - "Coverage figures: {functions: {total, matched, partial, unmatched}, bytes: {total, matched, partial}, percent}"

requirements-completed: [DEC-05]

coverage:
  - id: D1
    description: "derive_mechanics: item must-match and full-closure figures from committed data; null without mechanics.toml; malformed toml or a members row off a game/thunk row exits 2"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress.py#test_item_figures"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_mechanics_absent_gives_null"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_malformed_member_exits_2"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_malformed_mechanics_toml_exits_2"
        status: pass
    human_judgment: false
  - id: D2
    description: "Ruling F2: schema-only toml with an asm list, an absent members file and a toml with every 07-10 table all exit 0"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress.py#test_schema_only_mechanics_and_asm_list_exit_0"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_members_file_absent_gives_no_items"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_every_mechanics_table_is_accepted"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tier unions count a shared function once, zero-member items read 0 of 0, located/signed/matched tier states, duplicates once, ordering and determinism"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress.py#test_tier_union_counts_once"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_zero_member_item"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_located_tier_reads_located"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_tier_reads_matched_only_from_status"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_duplicates_listed_once"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_ordering_and_determinism"
        status: pass
    human_judgment: false
  - id: D4
    description: "Mechanics coverage section markup: text first, aria-hidden three-segment bar with nz minimum, tier states, duplicates, no new link"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress_page.py#test_coverage_section_markup"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_zero_member_item_markup"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_located_tier_text"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_duplicates_listed_once_on_the_page"
        status: pass
    human_judgment: true
    rationale: "The markup is pinned, but whether the section reads well on the published page (desktop and 390 px phone) is the plan's flagged <human-check> for /gsd-verify-work 7."
  - id: D5
    description: "Signed asm rows form an assembler group outside the percentage in progress.json, shields, report.json, strip, mosaic and legend; the DecompHub feed is unchanged"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress.py#test_assembler_group"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_unsigned_or_changed_asm_list_moves_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_progress.py#test_feed_ignores_the_asm_list"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_assembler_group_on_the_page"
        status: pass
      - kind: unit
        ref: "tests/test_drift.py#test_committed_feed_is_derived"
        status: pass
      - kind: unit
        ref: "tests/test_treemap.py#test_treemap_legend_clears_the_heading"
        status: pass
    human_judgment: false
  - id: D6
    description: "Ruling F37: How it is measured, progress.json notes and the README state which artifacts exclude the asm rows"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress_page.py#test_measured_states_the_assembler_group"
        status: pass
      - kind: unit
        ref: "tests/test_listings.py#test_readme_names_the_assembler_group"
        status: pass
      - kind: unit
        ref: "tests/test_listings.py#test_readme_names_the_coverage_section"
        status: pass
    human_judgment: false
  - id: D7
    description: "pages.yml on.push.paths and tests/test_workflows.py PATHS add the three mechanics paths"
    verification:
      - kind: unit
        ref: "tests/test_workflows.py#test_pages_triggers"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 15: Mechanics coverage view on the progress page Summary

**The progress page and progress.json now show each OpenApoc checklist item's must-match and full-closure coverage (D-22). Each tier's figures are taken over the union of its items' rows. The data comes from the committed mechanics.toml and members CSV, joined with the gate-written status.csv. Owner-signed asm rows move out of the percentage into an assembler group counted like the library (D-23). The gate's DecompHub feed stays exactly as it was.**

Execution context nonce: 0db1d6c93f0e5010

## Performance

- **Duration:** about 25 min of execution (reading started earlier)
- **Started:** 2026-10-27T17:45:46Z
- **Completed:** 2026-10-27T18:10:48Z
- **Tasks:** 3. Tasks 1 and 2 are TDD, each with a RED commit and then a GREEN commit.
- **Files modified:** 8

## Accomplishments

- **`derive_mechanics(config_dir, progress)`** reads `config/mechanics.toml` with tomllib. It reads `config/mechanics-members.csv` and `config/asm-functions.csv` with progress.py's own `_records`, so it stays stdlib-only and Python 3.12 syntax under `python3 -I`.
  - It returns `None` without the toml. It returns a `Mechanics` with no items when the toml has no `in` item or the members file is absent (ruling F2).
  - It accepts every 07-10 table and refuses an unknown top-level key, a wrong schema, a table of the wrong shape and bad tier or item fields.
  - A members row (or a signed asm row) that is not a game or thunk row of functions.csv is a `ProgressError`, so `main` exits 2.
- **Figures** (`Coverage`, `ItemCoverage`, `TierCoverage`, `Duplicate`, `Mechanics`). An item has two sets:
  - **must match:** role `member` rows that name the item in member_items.
  - **full closure:** rows that name the item in items, except rows with role `asm`.

  Each set holds functions total, matched, partial and unmatched, bytes total, matched and partial, and a percent. A tier's sets are the union of its `in` items' rows, so a shared function counts once. Tier state is `matched` (every must-match function is matched in status.csv), `located` or `not located yet`, plus its sign-off ("signed off by NAME on DATE" or "not signed off").
- **progress.json** gains `"mechanics"` (null without the toml) with `tiers`, `items` and `duplicates`. Each EXE and the combined block also gain `assembler_bytes` and `assembler_functions`, and a new note explains the group. `PROGRESS_VERSION` stays 1.
- **Page:** a `Mechanics coverage` section sits after the strip's key and before the mosaic. It has a caption and a tier list. Then a `<ul class="items">` holds one `<li>` per `in` item, sorted by (tier, issue, number): the text first, then an aria-hidden `.cov` bar with matched, partial and unmatched segments by function count, each non-zero one carrying `nz` (2 px minimum). Duplicates are listed once, as "a duplicate of #ID". Issue numbers are plain text, so the page has no new link. The section's CSS is emitted only when the section is shown.
- **Assembler group (D-23):** a list counts only when `[asm_list]` has signed_off_by and its list_sha256 equals the SHA-256 of the file with LF line endings.
  - `exclude_assembler` moves those rows to `ExeProgress.assembler_rows`, so they leave the percent and the function ratio.
  - The strip draws them as short library-coloured `l` ticks at their address, with an aria count and a key line. The mosaic draws them as library cells.
  - The EXE figures add "N assembler function(s) (B bytes) outside the percentage". The legend reads "library or assembler".
  - `main` uses this view for progress.json, the shields, progress.svg, index.html and report.json. `--decomphub` and gate keep `build_decomphub(derive(...))`.
- **pages.yml** rebuilds when `config/mechanics.toml`, `config/mechanics-members.csv` or `config/asm-functions.csv` changes. `PATHS` in tests/test_workflows.py matches, in the same order.

## Task Commits

1. **Task 1 (tracer): the coverage line on the page and in progress.json.** RED `80aa237`, GREEN `eb7f9cd`. Tracer gate: the run is interactive in end-of-phase mode and the verify is automated only. The verify was re-run (62 passed), so expansion went ahead.
2. **Task 2: tier unions, duplicates, located tiers, the assembler group.** RED `3cb2e24`, GREEN `021aa49`.
3. **Task 3: Pages trigger paths.** `f6b54c7` (ci).

No REFACTOR commits.

## TDD Gate Compliance

Each RED record was built from pytest JUnit XML. `gsd-tools check tdd-red-evidence` returned **RED_EVIDENCE_OK** (`target_test_failed`) for both.

- **Task 1:**
  - Target `test_item_figures`. 11 failed, 51 passed.
  - Every failure was an assertion. The API-presence asserts (`progress.py has no derive_mechanics`) follow the suite's `hasattr` pattern. `test_mechanics_absent_gives_null` failed on `"mechanics" in doc`.
  - Semantic assessment: the target ran and failed because the planned behaviour was absent. There was no collection, import or fixture error.
- **Task 2:**
  - Target `test_assembler_group`. 10 failed, 140 passed.
  - Before the RED commit, two tests failed with an AttributeError (`ASM_CSV`, `.assembler`). I changed them to fail on a `hasattr` assertion first.
  - These Task 2 tests already passed at RED: tier union, zero-member item, located tier, matched-only tier, duplicates, ordering and determinism, the feed ignoring the asm list, and the three page tests for zero, located and duplicates. Task 1's GREEN already derives tiers and duplicates, so they are characterization tests, like 07-10's Task 2. `test_feed_ignores_the_asm_list` passes by construction (`derive` never reads the list) and pins T-07-44.
- Git log: `test(07-15)` comes before `feat(07-15)` for both tasks.

## Verification

- `uv run pytest -q tests/test_progress.py tests/test_progress_page.py`: 62 passed after Task 1.
- `uv run pytest -q tests/test_progress.py tests/test_progress_page.py tests/test_treemap.py tests/test_drift.py tests/test_listings.py tests/test_report_shape.py`: 160 passed. That run includes `test_committed_feed_is_derived`.
- `uv run pytest -q tests/test_workflows.py`: 13 passed. `grep -q '"config/mechanics-members.csv"' .github/workflows/pages.yml`: ok.
- **Host suite:** `uv run pytest -q` gave **3033 passed, 236 skipped**. The skip count equals 07-10's fix-round count. Every skip is a pre-existing real-file or tool skip: orig/*.EXE not present, Watcom 10.5/10.6/11.0 or watcom-media not installed in the worktree, symlink privileges, non-UTF-8 names, and objdiff-cli, ninja or clang off PATH ("run in the container"). No new skip reason. None of the new tests skips (R-A).
- `uv run ruff check .`: all checks passed.
- `uv run python -I tools/progress.py --help`: exit 0. `uv run python -I tools/progress.py --out build/page-check --commit 3cb2e24` on the committed config (no mechanics.toml yet): exit 0. The page has no coverage section, and progress.json has `"mechanics": null`.
- Acceptance greps: `def derive_mechanics(`, `Mechanics coverage` and `def exclude_assembler(` are each in tools/progress.py.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test` (R-B). No docker was run from the worktree.

## Files Created/Modified

- `tools/progress.py`:
  - mechanics constants (pinned to mechanics.py), `Coverage`, `TierCoverage`, `ItemCoverage`, `Duplicate`, `Mechanics`;
  - the readers (`_read_toml`, `_tier_specs`, `_item_specs`, `_read_members`, `_asm_signed`, `_assembler`), `derive_mechanics` and `exclude_assembler`;
  - `Totals.assembler_*`, `ExeProgress.assembler_rows`, `build_mechanics`, `build_progress(..., mechanics)`, `write_progress_json(..., mechanics)`;
  - the coverage section helpers, `render_html(..., mechanics)` and `write_html(..., mechanics)`;
  - the assembler tick, key and CSS, the legend label, the NOTES and MEASURED text;
  - `main`'s `_Derived` (feed view and published view).
- `tests/test_progress.py`: fixtures (`item_toml`, `write_mechanics` checked by `mechanics.load`, `member`, `tick_members`, `asm_config`) and 19 new tests.
- `tests/test_progress_page.py`: 7 new page tests (section markup, zero, located, duplicates, assembler, no-assembler, MEASURED).
- `tests/test_treemap.py`: the legend names "library or assembler"; new `test_treemap_legend_clears_the_heading`.
- `tests/test_listings.py`: `test_readme_names_the_assembler_group`, `test_readme_names_the_coverage_section`.
- `README.md`: Progress section. A sentence on the coverage section, and the **library** item now covers the assembler group: where the rows are excluded and that the DecompHub feed keeps them.
- `.github/workflows/pages.yml`, `tests/test_workflows.py`: the three trigger paths.

## Decisions Made

See key-decisions above.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F2: `derive_mechanics` no longer breaks on mechanics data that is only partly committed.**
  - It returns a `Mechanics` with no items when the toml has no `in` item or the members file is absent.
  - It accepts all seven 07-10 top-level tables and refuses unknown top-level keys. It validates only what the page reads (tiers, items and the `[asm_list]` sign-off fields); `[hub_rule]`, `[[entry]]` and `[[edge]]` are checked for shape only.
  - Tests: `test_schema_only_mechanics_and_asm_list_exit_0`, `test_members_file_absent_gives_no_items` and `test_every_mechanics_table_is_accepted` (each exits 0), and `test_malformed_mechanics_toml_exits_2` (exits 2).
  - The 07-20 / 07-22 verify additions are those plans' part of the ruling, not this plan's.
- **Orchestrator ruling F37: the published wording now names the asm exclusion.**
  - MEASURED (How it is measured), a new progress.json note and README's Progress **library** item each say which artifacts exclude the signed asm rows: the page, progress.json, the badges and report.json. They also say that decomphub.progress.json still counts them.
  - README.md and tests/test_listings.py were added to the files touched.
  - Tests: `test_measured_states_the_assembler_group`, `test_readme_names_the_assembler_group`, `test_readme_names_the_coverage_section`.
- Rules for every plan:
  - R-A: no new skip.
  - R-B: container step deferred (see Verification).
  - R-C: not applicable (worktree).
  - R-D: no subagents.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] report.json uses the asm-excluded view too**
- **Found during:** Task 2.
- **Issue:** The plan applies `exclude_assembler` to "the page and progress.json path". build_report's docstring and test_report_shape pin report.json's combined matched_code_percent to progress.json's percent. Leaving report.json on `derive()` would break that invariant once a list is signed, and recomp.fyi would publish a different percent from the badges.
- **Fix:** `main` builds report.json, like every `--out` file, from the excluded view. Only `--decomphub`, and gate, use `derive()`. `test_assembler_group` checks that the two percents are equal.
- **Committed in:** `021aa49`.

**2. [Rule 1 - Bug, layout] Legend label shortened to "library or assembler"**
- **Found during:** Task 2, a render of the committed config.
- **Issue:** The plan's wording, "library or assembler, not decompiled" (36 characters), moves the right-aligned SVG legend to x=448. The bold heading "X-COM Apocalypse (DOS): 0.0063% decompiled, 5 of 3,079 functions" ends near x=444, so the labels would touch, and they would overlap once the figures grow.
- **Fix:** The label is now "library or assembler" (20 characters, shorter than the old 24-character "library (not decompiled)"). The legend now starts at x=554. "Not decompiled" is still stated in the assembler key line, in MEASURED and in the README. The new `test_treemap_legend_clears_the_heading` checks the clearance against the worst-case heading ("100% decompiled, 3,079 of 3,079"). The pinned label tests were updated in the GREEN commit.
- **Committed in:** `021aa49`.

**3. [Rule 2 - Correctness] An unsigned or stale asm list is ignored, not an error**
- **Issue:** Plan 07-20 Task 1 commits an unsigned list (F38). Raising an error would make the Pages job exit 2.
- **Fix:** Such a list moves nothing. `mechanics check` remains the place that reports it. A signed list's rows are validated strictly.
- **Test:** `test_unsigned_or_changed_asm_list_moves_nothing`.
- **Committed in:** `021aa49`.

**4. [Scope addition] Extra tests**
- `test_mechanics_constants_agree`: progress.py's format copies match mechanics.py's.
- `test_tier_reads_matched_only_from_status`: the RPT-01 prohibition.
- `test_asm_row_off_a_game_row_exits_2`.
- `test_page_without_assembler_has_no_assembler_markup`.

**Total deviations:** 3 auto-fixed (2 Rule 2, 1 Rule 1), plus the 2 orchestrator rulings and the extra tests. **Impact:** consistency and correctness fixes inside the plan's files, plus README and test_listings (F37). The gate's feed and the page's links are unchanged.

## Issues Encountered

- The worktree harness refuses compound or heredoc commands. Tests were appended with Edit, and the RED evidence records were built by a scratch script (outside the repo) from the JUnit XML under the gitignored build/red/.
- No ledger file was written under `.git/worktrees/`. The commit count is measured against the dispatch base 8a8f98e.

## Threat Flags

None.
- No new link: `_check_static` holds, and the href set is unchanged (tested). Issue numbers are text.
- Titles reach the page only through `_xml` escaping, and progress.json is ASCII JSON.
- No game bytes. Only addresses, ids, titles and counts are used.
- T-07-44 is pinned by `test_feed_ignores_the_asm_list` and `test_committed_feed_is_derived`.

## Known Stubs

None. The committed config has no mechanics.toml yet, so the live page shows no coverage section until plans 07-20 and 07-22 commit the data. That is the intended F2 behaviour, not a stub.

## User Setup Required

None.

## Next Phase Readiness

- Plans 07-20 and 07-22 can commit mechanics.toml, the asm list and the members file. The Pages job will exit 0 at each step (F2) and rebuild on each of those files.
- Visual check of the coverage section on desktop and on a 390 px phone: the plan's flagged `<human-check>` for `/gsd-verify-work 7`.
- STATE.md and ROADMAP.md were not touched.

## Self-Check: PASSED

- FOUND: tools/progress.py, tests/test_progress.py, tests/test_progress_page.py, tests/test_treemap.py, tests/test_listings.py, README.md, .github/workflows/pages.yml, tests/test_workflows.py
- FOUND commits (ancestors of HEAD): 80aa237, eb7f9cd, 3cb2e24, 021aa49, f6b54c7

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
