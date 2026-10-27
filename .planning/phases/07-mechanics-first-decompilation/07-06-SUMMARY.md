---
phase: 07-mechanics-first-decompilation
plan: 06
subsystem: reporting
tags: [progress-page, html, css, accessibility, backlog-999.4]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "tools/progress.py page (render_html, strip, mosaic embed) and 06-UI-REVIEW.md fixes #1-#3"
provides:
  - "Mosaic in a focusable region that scrolls sideways below 40rem (.mosaic svg min-width 48rem)"
  - "HTML legend (<ul class=\"legend\">) right above the mosaic, SVG legend kept"
  - "Per-EXE <details> text list of matched and partial function tooltips, address order"
  - "Non-zero percent bar segment with class nz and a 2px minimum width"
affects: [07-15 coverage section on progress.py, 07-41 ticks backlog 999.4, pages.yml]

actuals:
  tokens: 4761      # chars/4 over the realized diff (19,045 chars, git diff base..HEAD)
  tasks: 2
  commits: 4        # git rev-list --count plan_head_before..HEAD
plan_head_before: 0f9de364337258572e5dcddb10a133cd2c95c821
plan_head_after: 839f71667e25168331c56936d6517bfd096da7cb

tech-stack:
  added: []
  patterns:
    - "Page features that need a mouse get a no-script text equivalent (<details> list) next to them"
    - "Phone legibility through a focusable overflow-x region with a min-width, not by scaling"

key-files:
  created: []
  modified:
    - tools/progress.py
    - tests/test_progress_page.py

key-decisions:
  - "The HTML legend uses inline style backgrounds from TREEMAP_COLORS on a .swatch span (no new class per status), CELL_STATUSES order"
  - "The tooltip list's summary count is a plain integer (no thousands separator) so the pinned markup stays simple"
  - "Focus rings added for the mosaic region and <summary> (same 2px ink outline as links)"
  - "min-width:48rem and .bar .nz{min-width:2px} are literal in the CSS (the plan's acceptance greps), not constants"

patterns-established:
  - "Backlog 999.4 markup is pinned by tests (MOSAIC_REGION, phone_rules, listed, bar_html helpers in test_progress_page.py)"

requirements-completed: [DEC-05]

coverage:
  - id: D1
    description: "Mosaic scrolls sideways on a phone in a focusable, named region (999.4 fix #2)"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress_page.py#test_mosaic_scrolls_sideways_on_a_phone"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_mosaic_region_is_focusable"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_page_embeds_the_mosaic"
        status: pass
    human_judgment: true
    rationale: "The markup is pinned, but whether the mosaic is readable at 390 px is a visual check the plan defers to /gsd-verify-work 7 (human_verify_mode end-of-phase)."
  - id: D2
    description: "HTML legend above the mosaic, one item per cell status with page colour and LEGEND_LABELS text; SVG legend kept"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress_page.py#test_html_legend_above_the_mosaic"
        status: pass
    human_judgment: false
  - id: D3
    description: "Per-EXE <details> list of every matched and partial function's tooltip text in address order, escaped; absent for an EXE with none (999.4 fix #1)"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress_page.py#test_details_lists_matched_and_partial"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_details_on_committed_csvs"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_details_absent_when_none"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_details_escapes_names"
        status: pass
    human_judgment: false
  - id: D4
    description: "Non-zero percent bar draws a span with class nz, CSS .bar .nz{min-width:2px}; zero draws none (999.4 fix #3)"
    requirement: DEC-05
    verification:
      - kind: unit
        ref: "tests/test_progress_page.py#test_nonzero_bar_has_min_width"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_page_shape"
        status: pass
    human_judgment: false
  - id: D5
    description: "Page stays static and deterministic: no script, no new href, equal bytes across renders"
    verification:
      - kind: unit
        ref: "tests/test_progress_page.py#test_page_is_static_and_self_contained"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_page_is_deterministic_and_bounded"
        status: pass
      - kind: unit
        ref: "tests/test_progress_page.py#test_script_writes_the_page_isolated"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 06: Progress page backlog 999.4 fixes Summary

**The progress page's mosaic now scrolls sideways at a 48rem minimum width in a focusable region with an HTML legend above it, every matched and partial tooltip is also a keyboard/touch-reachable `<details>` text list per EXE, and a non-zero percent bar keeps a 2px segment so 0.0091% is visible.**

Execution context nonce: db06144bddddd442

## Performance

- **Duration:** about 11 min
- **Started:** 2026-10-27T14:50:45Z
- **Completed:** 2026-10-27T15:01:21Z
- **Tasks:** 2 (both TDD: RED then GREEN commits)
- **Files modified:** 2

## Accomplishments

- Fix #2 (phone mosaic): `.mosaic{margin-top:.75rem;overflow-x:auto}`, `.mosaic svg{min-width:48rem}` inside the existing
  40rem media block only, the mosaic wrapped in `<div class="mosaic" tabindex="0" role="region" aria-label="Decompilation
  mosaic, scrolls sideways">` with a focus ring, and a `<ul class="legend">` (one item per status in CELL_STATUSES order,
  swatch in the page's status colour, LEGEND_LABELS text) right above it. `render_svg` is embedded unchanged and keeps its
  own legend.
- Fix #1 (tooltips): after each EXE's strip, `<details><summary>Matched and partial functions (N)</summary><ul>` with one
  `<li>` per matched or partial function in address order, text equal to `_function_title`, HTML-escaped. No block for an
  EXE with none. The tick `title` attributes stay. On the committed CSVs: UFO2P 11 items, TACP 8.
- Fix #3 (bar): a percent above zero draws `<span class="nz" style="width:X%">`, and `.bar .nz{min-width:2px}` follows
  the `.bar span` rule; 0% draws no `nz` span. `_figures` text is unchanged.

## Task Commits

1. **Task 1 (tracer): scrollable mosaic region and HTML legend**
   - RED `7973c6f` test(07-06): add failing tests for the scrollable mosaic region and HTML legend
   - GREEN `a64a8ff` feat(07-06): scroll the mosaic sideways on a phone, with an HTML legend
2. **Task 2: tooltip list and visible non-zero bar**
   - RED `3ee9db3` test(07-06): add failing tests for the tooltip list and the visible non-zero bar
   - GREEN `839f716` feat(07-06): list the tooltips as text and keep a non-zero bar visible

No REFACTOR commits (nothing to clean up after GREEN).

## TDD evidence

- **Task 1 RED:** `uv run pytest -q tests/test_progress_page.py --junitxml=...`, exit 1, 4 failed / 20 passed. The
  failures were test_page_embeds_the_mosaic, test_mosaic_scrolls_sideways_on_a_phone, test_mosaic_region_is_focusable
  and test_html_legend_above_the_mosaic. `gsd-tools check tdd-red-evidence` (JUnit format) returned
  **RED_EVIDENCE_OK** for target `test_mosaic_scrolls_sideways_on_a_phone`. Semantic assessment: the target failed on its
  first assertion (the overflow-x rule was absent), not on import or collection, and the siblings failed on their markup
  assertions.
- **Task 2 RED:** same command, exit 1, 6 failed / 23 passed. The failures were test_page_shape (the `nz` bar substring was
  missing), the four details tests and test_nonzero_bar_has_min_width. RED_EVIDENCE_OK for both targets,
  `test_details_lists_matched_and_partial` and `test_nonzero_bar_has_min_width`. Semantic assessment: each target ran and
  failed on its planned assertion (no details list; no `nz` class after the 0.4% precondition passed). Before the RED
  commit, test_details_escapes_names was changed to fail on an assertion instead of a TypeError (unpacking None).
- **GREEN:** after each GREEN commit, 24/24 and then 29/29 page tests passed. The tracer gate (interactive,
  end-of-phase, automated-only verify) re-ran Task 1's verify, which passed, so Task 2 went ahead.
- Gate log: `test(07-06)` precedes `feat(07-06)` for both tasks.

## Verification

- `uv run pytest -q tests/test_progress_page.py tests/test_progress.py tests/test_listings.py`: 80 passed.
- `uv run pytest -q` (host, worktree): **2688 passed, 229 skipped**. Every skip is a pre-existing real-file skip:
  `orig/*.EXE not present`, Watcom 10.6 or watcom-media not installed in the worktree. No new skip reason, and none of the
  new tests skips.
- `uv run ruff check .`: all checks passed.
- `uv run python -I tools/progress.py --help`: exit 0.
- `uv run python -I tools/progress.py --out build/page-check --commit <sha>` on the committed CSVs: exit 0, 2 details
  blocks (11 and 8 items), both bars `class="nz"` (0.0091%, 0.0035%).
- Acceptance greps all pass: `overflow-x:auto`, `min-width:48rem`, `.bar .nz{min-width:2px}` and
  `Matched and partial functions` are each in tools/progress.py.
- **Container step deferred to the orchestrator:** `docker compose run --rm test` (the done gate's container leg). No
  docker was run from the worktree.

## Files Created/Modified

- `tools/progress.py`: MOSAIC_REGION, SWATCH_SIZE and TOOLTIP_LIST_SUMMARY constants; `_legend_html`, `_bar_html` and
  `_tooltip_list_html`; the `.legend`, `.swatch`, `details`, `summary:focus-visible`, `.mosaic:focus-visible` and
  `.bar .nz` rules, the overflow-x `.mosaic` rule and the phone `min-width` rule; updated docstrings.
- `tests/test_progress_page.py`: 9 new tests (test_mosaic_scrolls_sideways_on_a_phone, test_mosaic_region_is_focusable,
  test_html_legend_above_the_mosaic, test_details_lists_matched_and_partial, test_details_on_committed_csvs,
  test_details_absent_when_none, test_details_escapes_names, test_nonzero_bar_has_min_width), with test_page_shape and
  test_page_embeds_the_mosaic updated to the new markup.

## Decisions Made

- Each legend swatch is a `<span class="swatch">` with an inline `background` from TREEMAP_COLORS. The page's status hues
  are the same in both schemes, so no per-status class or dark-scheme rule is needed.
- The summary count is a plain integer, with no thousands separator.
- Focus rings for the new focusable elements (the mosaic region and `<summary>`) use the same 2px ink outline as links.
- `min-width:48rem` and `min-width:2px` are written literally in the CSS so the plan's acceptance greps hold.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Focus ring for the focusable mosaic region and the details summary**
- **Found during:** Task 1 and Task 2
- **Issue:** making the mosaic `tabindex="0"` without a visible focus indicator would leave keyboard users without a
  cue (WCAG 2.4.7). The page already gives links a custom outline.
- **Fix:** added `.mosaic:focus-visible` and `summary:focus-visible` with the link outline. The first is pinned in
  test_mosaic_region_is_focusable.
- **Files modified:** tools/progress.py, tests/test_progress_page.py
- **Committed in:** 7973c6f / a64a8ff (Task 1), 839f716 (Task 2)

**2. [Scope addition] Extra tests beyond the plan's list**
- test_details_on_committed_csvs (the tooltip list matches the committed CSVs) and test_details_escapes_names (threat
  T-07-16 says "tests escape-check the details list"). Both are included in the RED commit.

Orchestrator rulings: none apply to 07-06 (rulings.md has no 07-06 section). Rules for every plan were followed:
R-A (no new skips), R-B (container step deferred), R-D (no subagents).

**Total deviations:** 1 auto-fixed (Rule 2), plus 2 added tests. **Impact:** an accessibility correctness addition with
no scope creep. The page is still static: no script, no new link.

## Issues Encountered

- The worktree harness refuses compound or `source`d git commands, so the guards and the classifier ran as separate plain
  commands. The commit ledger base was recorded from the spawn-time HEAD (0f9de36) instead of a ledger file.

## Threat Flags

None. No new network endpoint, link or asset. Names reach the new list only through the existing `_xml` escape
(T-07-16, tested).

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- Plan 07-15 can add the coverage section on top. The new helpers sit next to `_exe_html`, and `render_html`'s mosaic
  block is now legend, region, then SVG.
- The phone check (390 px, readable labels, sideways scroll) is the `<human-check>` for `/gsd-verify-work 7`.
- Plan 07-41 ticks backlog 999.4 in ROADMAP.md. This plan did not touch ROADMAP.md or STATE.md.

## Self-Check: PASSED

- FOUND: tools/progress.py, tests/test_progress_page.py
- FOUND commits: 7973c6f, a64a8ff, 3ee9db3, 839f716 (ancestors of HEAD)

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
