---
phase: 06-reporting-and-agent-pilot
plan: 24
subsystem: reporting
tags: [progress, treemap, svg, github-pages, recomp-fyi, decomphub, workflow]

requires:
  - phase: 06-reporting-and-agent-pilot (06-18)
    provides: tools/progress.py (derive, Progress, report.json, the feed, main creating output dirs)
provides:
  - tools/progress.py squarify, render_svg, write_svg; --out also writes progress.svg
  - ExeProgress.library_rows (the runtime rows, one library cell each)
  - .github/workflows/pages.yml (jobs build, deploy, notify-decomphub)
  - tests/test_treemap.py, tests/test_workflows.py
  - .gitignore lines _site/ and .playwright-mcp/
affects: [06-26 pilot checkpoint (Pages source, DECOMPHUB_REFRESH variable), 06-27 phase gate (live run and URLs)]

actuals:
  tokens: 9054
  tasks: 3
  commits: 6
plan_head_before: 33310b760142b6260b133c0df46715e54be86a82
plan_head_after: f15b981a22604c254bf8bdcd4beb5f8ee68e78ea

tech-stack:
  added: []
  patterns:
    - "Workflow properties pinned by text with a small indentation-block reader (no YAML library)"
    - "Mosaic cells ordered by (-size, start, status rank): a total order, so the SVG is byte-stable"

key-files:
  created:
    - .github/workflows/pages.yml
    - tests/test_treemap.py
    - tests/test_workflows.py
  modified:
    - tools/progress.py
    - .gitignore

key-decisions:
  - "Treemap cells: one per game/thunk function (matched/partial/unmatched), one per runtime row (library), one per unit for its uncovered bytes; data-in-code is not drawn"
  - "Colours matched #008300, partial #eda100, unmatched #898781, library #2a78d6, uncovered #d8d6cf; the three hues pass the dataviz validator's CVD check, the two greys are neutral on purpose"
  - "EXEs keep EXES order (UFO2P, TACP); units and cells go largest first, then by address"
  - "Legend swatches are circles, so every <rect> with a status colour is a cell"
  - "The build job runs the runner's python3 (no uv), passes --commit \"$GITHUB_SHA\", checks out without persisted credentials; notify-decomphub has permissions: {}"

patterns-established:
  - "tests/test_workflows.py block()/job()/top() helpers read a workflow by indentation"

requirements-completed: [RPT-02, RPT-03, RPT-04, RPT-05]

coverage:
  - id: D1
    description: "progress.svg: a deterministic squarified treemap EXE > unit > function, five fixed colours, titles on unit groups and matched cells, 0.1 rounding, 476,714 bytes for today's CSVs"
    requirement: RPT-02
    verification:
      - kind: unit
        ref: "tests/test_treemap.py (11 tests)"
        status: pass
      - kind: other
        ref: "uv run python -I tools/progress.py --out build/progress-check && test -s build/progress-check/progress.svg"
        status: pass
    human_judgment: false
  - id: D2
    description: "pages.yml builds the site from the committed CSVs and deploys it with GitHub's Pages actions"
    requirement: RPT-03
    verification:
      - kind: unit
        ref: "tests/test_workflows.py#test_pages_triggers, test_pages_permissions_and_concurrency, test_pages_build_steps, test_pages_deploy_job"
        status: pass
    human_judgment: true
    rationale: "The live deploy needs the owner's Pages setting (Source: GitHub Actions) and a push to main; plan 06-27 checks the run and the URLs"
  - id: D3
    description: "The report.json artifact X-COM_Apocalypse_DOS_report (90 days, error when missing), one upload only"
    requirement: RPT-04
    verification:
      - kind: unit
        ref: "tests/test_workflows.py#test_pages_build_steps, test_pages_uploads_one_report_artifact"
        status: pass
    human_judgment: true
    rationale: "recomp.fyi's daily read of the artifact can only be observed after a default-branch run"
  - id: D4
    description: "The DecompHub refresh POST, skipped unless the event is a push and vars.DECOMPHUB_REFRESH is 'true'; no secret anywhere"
    requirement: RPT-05
    verification:
      - kind: unit
        ref: "tests/test_workflows.py#test_decomphub_notify_is_gated, test_no_other_outward_url, test_pages_needs_no_secret"
        status: pass
    human_judgment: false
  - id: D5
    description: ".gitignore ignores _site/ and (ruling F14) .playwright-mcp/"
    verification:
      - kind: unit
        ref: "tests/test_workflows.py#test_gitignore_ignores_site, test_gitignore_ignores_playwright_mcp"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 24: progress treemap, Pages workflow and the DecompHub refresh Summary

**tools/progress.py now draws progress.svg, a stdlib squarified treemap (EXE > unit > one cell
per function, plus each unit's uncovered bytes) in five fixed colours; .github/workflows/pages.yml
builds the site and report.json from the committed CSVs with the runner's `python3 -I`, uploads
the single `X-COM_Apocalypse_DOS_report` artifact, deploys Pages, and POSTs to DecompHub only
when the owner sets `DECOMPHUB_REFRESH`.**

Execution context nonce: f09971cb337e83fc

## Performance

- **Duration:** about 10 min of wall clock between the first and last commit (start
  2026-10-25T15:45:55Z, last task commit about 15:55Z)
- **Tasks:** 3 (Task 1 tracer, verified end-to-end before expanding)
- **Files modified:** 5 (tools/progress.py, tests/test_treemap.py, .github/workflows/pages.yml,
  tests/test_workflows.py, .gitignore)

## Accomplishments

- `squarify(sizes, rect)`: Bruls/Huizing/van Wijk rows, grown while the worst aspect ratio
  improves, laid along the shorter side; rectangles in input order; non-positive sizes refused.
- `render_svg(progress)`: title and right-aligned legend (including "uncovered: mostly alignment
  filler"), one captioned group per EXE, unit groups with a `<title>` (matched/total code bytes,
  function count, library and uncovered bytes), cells with a `<title>` only when matched.
  Edges are rounded to 0.1, so neighbouring cells stay flush. Today: 476,714 bytes, 5,025 rects.
- `main --out` writes progress.svg next to progress.json and the shield.
- pages.yml: the triggers, permissions and concurrency of D-27; build, deploy and
  notify-decomphub jobs.

I rendered the committed CSVs with headless Edge and looked at the result. The two EXE maps
sit side by side with their captions. Library cells (blue) cluster where the runtime's small
functions are, and the large uncovered blocks (light grey) stand out. The two matched
functions (13 and 11 bytes) are about 7 px² each, too small to see at 1200x800. Their
`<title>` is there, and the cells will grow as matches land.

## README Progress section vs the treemap

They agree. The README describes one cell per function, grouped by EXE and unit and sized by
bytes, in five categories. The treemap draws exactly that: game and thunk functions as
matched/partial/unmatched, runtime rows as library, and each unit's uncovered bytes as one
uncovered cell (uncovered bytes belong to no function). Data-in-code is not drawn, as the
README says.

## Task Commits

1. Task 1 (tracer): `fc1d4ac` test RED, `eba1125` feat GREEN
2. Task 2: `7144cad` test RED, `2a163d7` feat GREEN
3. Task 3: `90a2315` test RED, `f15b981` feat GREEN

## TDD Gate Compliance

Each RED run went through `gsd-tools check tdd-red-evidence` on pytest JUnit XML (records under
build/06-24/, written by the program, not tracked):

- Task 1: RED_EVIDENCE_OK, target `test_squarify_tiles_its_rectangle`; 11/11 failing on
  `AssertionError: progress.py has no squarify` (a loader assert in each test body). Semantic
  assessment: the target ran and failed because the feature was missing. There was no
  collection, import or fixture fault.
- Task 2: RED_EVIDENCE_OK, target `test_pages_build_steps`; 8/8 failing (6 on "pages.yml does
  not exist", 2 on the missing `_site/` and `.playwright-mcp/` lines).
- Task 3: RED_EVIDENCE_OK, target `test_decomphub_notify_is_gated`; 2 failing (`pages.yml has no
  'notify-decomphub:' block`; the URL set empty), 8 Task 2 tests still passing.

Tracer gate: Task 1's automated verify was re-run after GREEN (treemap + progress tests and the
`python -I` run): pass.

## Decisions Made

See key-decisions. I chose the colours with the dataviz skill's validator (`--mode light
--pairs all` on surface #fcfcfb). Matched/partial/library pass the lightness band, chroma floor,
CVD separation (worst ΔE 16.2) and normal-vision floor. The validator flags the two greys
under "chroma floor" because they are neutral, which is the intent: they mean "nothing yet".
Every category also has a text label in the legend, so no category is told apart by colour
alone.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F17: create output directories.** `main()` already created every
  output's parent (06-18). I added `test_main_creates_output_dirs` in tests/test_treemap.py:
  `--out tmp/a/b --report tmp/c/report.json` with neither directory present gives exit 0,
  all four files, and progress.svg equal to `render_svg`. It was RED because it also requires
  progress.svg. 06-18's `test_main_creates_every_output_parent` in tests/test_progress.py stays,
  with a different name. Commits `fc1d4ac`, `eba1125`.
- **Orchestrator ruling (fix round 1): permissions per job.** This departs from the plan's
  truth of top-level `pages: write` / `id-token: write`. The top level is now `contents: read`
  only; `deploy` alone gets `pages: write` and `id-token: write`; `build` inherits read-only;
  `notify-decomphub` keeps `permissions: {}`. See "Fix round 1" below. Commits `734de40`,
  `56e67bf`.
- **Orchestrator ruling F14: ignore `.playwright-mcp/`** (owner-approved 2026-10-24). The line
  sits under "Generated by analysis/doc tools", and `test_gitignore_ignores_playwright_mcp`
  checks that it is in that section. Commits `7144cad`, `2a163d7`.

### Auto-fixed / added

**1. [Rule 2 - Missing critical] Library cells needed the runtime rows**
- Found during: Task 1. ExeProgress held only library byte and function counts, so the mosaic
  could not draw one cell per library function.
- Fix: `ExeProgress.library_rows: tuple[Row, ...] = ()`, filled by `_derive_exe`. The default
  keeps every other construction working, and no JSON output changes (the drift and report
  tests pass).
- Commit: `eba1125`.

**2. [Rule 2 - Hardening] Least privilege beyond the plan's text** (T-06-57, T-06-59)
- `actions/checkout@v7` with `persist-credentials: false`; `notify-decomphub` has
  `permissions: {}`.
- Extra tests: `test_pages_needs_no_secret` (no `secrets.` anywhere),
  `test_pages_uploads_one_report_artifact` (one upload-artifact step, the name once),
  `test_pages_deploy_job`, and the no-other-tool check in `test_no_other_outward_url` (no wget,
  Invoke-WebRequest, urllib, requests; one curl, inside notify-decomphub).
- Commits: `7144cad`, `2a163d7`, `90a2315`, `f15b981`.

**3. [Rule 2] The Pages run records its commit**
- The build step passes `--commit "$GITHUB_SHA"` after the planned command (06-18's SUMMARY
  expected the Pages job to pass it). It uses the default environment variable, not an
  expression interpolated into the shell. The planned command text is unchanged, and the test
  pins it as a substring.
- Commit: `2a163d7`.

**4. [Rule 1] Cron comment on its own line**
- My Task 2 test parses the cron line's five fields, and a trailing `# weekly` comment broke
  that. I moved the comment above `schedule:`. The workflow's meaning is unchanged.
- Commit: `2a163d7`.

**Total deviations:** 3 rulings applied (one in fix round 1), 4 auto-fixes (3 Rule 2, 1 Rule 1). **Impact:** no
scope change. Every file stayed within files_modified.

## Issues Encountered

- The worktree guard refused compound commands (a `$(git ...)` capture, a long heredoc chain,
  and Edge started by its full path). I split them into plain commands. The plan-start ledger
  file under `.git/worktrees/` was not written; plan_head_before is the dispatch base 33310b7.
- The security-guidance hook warned about `xml.etree` on tests/test_treemap.py. The tests parse
  only SVG that progress.py itself rendered, not outside input, and the plan names
  `xml.etree`. I kept it.
- The IDE reports "Context access might be invalid: DECOMPHUB_REFRESH" because the repository
  variable does not exist yet. That is the intended inert state until the owner creates it
  (06-26).

## Verification (fresh, host)

- `uv run pytest -q tests/test_treemap.py tests/test_progress.py`: 31 passed.
- `uv run python -I tools/progress.py --out build/progress-check && test -s build/progress-check/progress.svg`: exit 0.
- `uv run pytest -q tests/test_workflows.py tests/test_hygiene.py`: 83 passed, 3 skipped. The
  skips are the existing `only inside the container` ones at test_hygiene.py:554. The
  `test_ci_never_fetches_the_compiler` parametrisation now covers pages.yml.
- `uv run pytest -q tests/test_workflows.py`: 10 passed.
- Full host suite `uv run pytest -q -rs`: 2322 passed, 225 skipped. None of the skips is in a
  file this plan touched (tests/test_treemap.py, tests/test_workflows.py and test_progress.py:
  41 passed, 0 skipped). The skips are the existing real-file and container skips (orig/,
  third_party/ and the REVERSEAPOC_* variables are absent in the worktree).
- `uv run ruff check .`: All checks passed.
- Acceptance greps: `def squarify(` and `def render_svg(` in tools/progress.py; pages.yml holds
  `name: X-COM_Apocalypse_DOS_report`, `actions/deploy-pages@v5`,
  `vars.DECOMPHUB_REFRESH == 'true'` and `--max-time 20`.
- No container run (worktree rule). No YAML parser or actionlint is installed, and installing
  one is not allowed here, so the first real run on GitHub is the workflow's syntax check
  (06-27).

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. The one outward call (T-06-59) is gated as planned. The
site and the artifact hold only derived JSON/SVG (T-06-58).

## User Setup Required

As the plan's user_setup lists, at the pilot checkpoint (06-26):
- Settings > Pages > Source: GitHub Actions.
- Optional: repository variable `DECOMPHUB_REFRESH=true` to turn on the refresh POST.

## Next Phase Readiness

- 06-26/06-27 can run the workflow once the Pages source is set. Untested assumption:
  ubuntu-latest's `python3` is 3.12 or newer (the 3.12 parse test guards syntax only).
- REQUIREMENTS.md was not edited (the orchestrator marks requirements after merge). RPT-03's
  live deploy stays unresolved until 06-27.
- This plan did not touch the tick rate (OpenApoc #997).

## Fix round 1 (FIX_BASE 312882a, review-06-24.md: approved, minors only)

| # | Review minor | Change | Test (RED first) | Commits |
|---|---|---|---|---|
| 1 | Build job inherited `pages: write` / `id-token: write` | Orchestrator ruling (fix round 1): permissions per job. Top level `contents: read`; `deploy` has `pages: write`, `id-token: write`; build has no block (read-only); notify `permissions: {}` | `test_pages_permissions_and_concurrency` (each permission appears once, only in deploy) | `734de40` RED, `56e67bf` GREEN |
| 2 | A fork could POST its own URL | notify-decomphub `if:` adds `github.repository == 'ayrtondenner/ReverseApoc'` to push and `vars.DECOMPHUB_REFRESH == 'true'`; no `\|\|`, no negation | `test_decomphub_notify_is_gated` (exact job-level line) | `734de40`, `56e67bf` |
| 3 | No pipefail: a failed jq let curl POST an empty body | `shell: bash`; the script starts `set -euo pipefail`; jq's output goes into `body`; `if [ -z "$body" ]` prints `::error::` and exits 1 before `printf ... \| curl` | `test_decomphub_notify_never_posts_an_empty_body` (line order: set, jq, empty check, exit, fi, then the post) | `734de40`, `56e67bf` |
| 4 | Tests did not pin persist-credentials or a closed trigger set | Workflow already right; tests added | `test_every_checkout_drops_its_credentials`, `test_pages_trigger_set_is_closed` (keys of `on:` exactly push/schedule/workflow_dispatch, no `pull_request` text) | `734de40` |
| 5 | Zero-area cells | Note only, no change: 34 cells in today's render round to width or height 0 at 1200x800 (0.1 rounding). None is a matched cell (both matched cells have area), so no matched tooltip is unreachable today. If a matched function ever rounds to zero, its `<title>` cannot be hovered | none | this commit |

RED evidence: `test_decomphub_notify_never_posts_an_empty_body` gave RED_EVIDENCE_OK (13 tests,
3 failing on assertions: the permissions list, the gate line, the missing `shell: bash`). Minor
4's two tests passed at RED because the workflow already satisfied them. They are coverage
tests, so I proved they bite with planted defects instead (below).

**Planted defects (parse-only).** A scratch script ran the module against mutated copies of
pages.yml in a temporary directory. It parses files only and runs no workflow step. All 11 were
caught:
- persist-credentials dropped, or set to true;
- `pull_request`, `pull_request_target` or `issue_comment` added;
- `pages: write` given to build;
- repository guard dropped;
- pipefail dropped, `shell: bash` dropped, the empty check dropped, `exit 1` replaced.

**Network rule for this round.** No command that could reach the network was run. Nothing ran
curl, wget, gh, git push or fetch, or any HTTP client, and no workflow step was executed. The
notify script was checked only with `bash -n` on an extracted copy. That only parses the
script, and it passed.

**Not applied:** the review notes that the same repository guard on `deploy` is optional. It
was not asked for in this round, and I left it out. CI's own `ci.yml` checkout also lacks
`persist-credentials: false`. That file is outside this plan, so I did not change it.

**Verification (host):** `uv run pytest -q tests/test_workflows.py tests/test_hygiene.py` gives
88 passed, 3 skipped (the container-only skips). The full suite gives 2325 passed, 225
skipped: +3 tests, skip count unchanged. `uv run ruff check .`: All checks passed.

## Self-Check: PASSED

- Files exist: tools/progress.py, tests/test_treemap.py, tests/test_workflows.py,
  .github/workflows/pages.yml, .gitignore.
- Commits fc1d4ac, eba1125, 7144cad, 2a163d7, 90a2315, f15b981 and (fix round 1) 734de40,
  56e67bf are ancestors of HEAD.
