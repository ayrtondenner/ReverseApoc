---
phase: 06-reporting-and-agent-pilot
plan: 19
subsystem: docs
tags: [listings, awesome-rea, awesome-decomp-games, awesome-game-decompilations, decomp.me, ai-disclosure]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-16 status.csv and the gate (the acceptance test the drafts describe)"
provides:
  - "docs/listings.md: four ready-to-send drafts (awesome-rea, awesome-decomp-games, awesome-game-decompilations, decomp.me preset request), each in its target's own format, each sent by the owner by hand"
affects: [06-27, pilot-checkpoint, RPT-05]

actuals:
  tokens: 3017
  tasks: 2
  commits: 2
plan_head_before: 5d391a95fc7e771f05cab9d5985e9a315bc99097
plan_head_after: 74afbf895018a1e1e2a607c679dc2fc0a5d6ddd3

tech-stack:
  added: []
  patterns:
    - "Upstream list formats read only with read-only `gh api repos/<owner>/<repo>/contents/<path>` into the session scratchpad; nothing forked, written or filed upstream"
    - "Every listing draft carries the same four statements: AI-assisted (Claude Code), byte-comparison acceptance test, no game files distributed, repo + progress page links"

key-files:
  created:
    - docs/listings.md
  modified: []

key-decisions:
  - "awesome-decomp-games entry sets `\"ai_flag\": true` and `\"needs_assets\": \"byo\"` itself (both keys exist in upstream additions.json), so the project discloses its AI use instead of waiting to be flagged"
  - "awesome-game-decompilations line uses the list's own AI marker, a leading ⚠️ in the link text, placed alphabetically between Touhou (PC-98) and Zuma Deluxe"
  - "decomp.me preset request asks for a preset only (msdos platform already offers wcc10.6 per docs/toolchain.md); neither decomp.me nor its GitHub repository was accessed by any tool"
  - "Drafts carry no match counts, so they do not go stale between now and the pilot checkpoint; the progress page carries the numbers"

patterns-established:
  - "Listing drafts open with who sends each one (the owner) and a before-sending checklist (Pages live, re-read upstream layout, send by hand)"

requirements-completed: [RPT-05]

coverage:
  - id: D1
    description: "awesome-rea draft: a categories/game-decompilation.md line in the CONTRIBUTING shape `- [Name](link) - Decompilation: ...` naming byte comparison as the acceptance test, with placement, PR title and body"
    requirement: RPT-05
    verification:
      - kind: other
        ref: "grep -q '^## awesome-rea' docs/listings.md && grep -q 'categories/game-decompilation.md' docs/listings.md && grep -q 'AI-assisted' docs/listings.md && uv run pytest -q tests/test_hygiene.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "awesome-decomp-games draft: one valid JSON object for data/additions.json with platform DOS and type decomp"
    requirement: RPT-05
    verification:
      - kind: other
        ref: "uv run python -c parse of the single ```json block in the ## awesome-decomp-games section (json.loads OK; platform == DOS, type == decomp, ai_flag is True)"
        status: pass
    human_judgment: false
  - id: D3
    description: "awesome-game-decompilations draft (PC / Computer line marked with ⚠️) and decomp.me preset issue (msdos, wcc10.6, -4r -s -fpi)"
    requirement: RPT-05
    verification:
      - kind: other
        ref: "grep -q '^## awesome-game-decompilations' && grep -q '^## decomp.me preset request' && grep -q 'wcc10.6' && grep -q -- '-4r -s -fpi' docs/listings.md && uv run pytest -q tests/test_hygiene.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Each of the four sections states the owner sends it, says AI-assisted, names byte comparison, says no game files are distributed and links the repo and the progress page"
    requirement: RPT-05
    verification:
      - kind: other
        ref: "uv run python -c per-section check of 'Who sends it: the owner', 'AI-assisted', 'byte comparison', 'No game files are distributed', repo URL and Pages URL: all four sections True"
        status: pass
    human_judgment: false
  - id: D5
    description: "The drafts read well and are fit to send under the owner's name (tone, honesty, accuracy of the claims about the project)"
    verification: []
    human_judgment: true
    rationale: "Public statements under the owner's name; the owner reviews and sends each draft by hand at the pilot checkpoint (D-33)"

duration: 5min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 19: Listing drafts Summary

**docs/listings.md with four owner-sent drafts in each target's own format: an awesome-rea `Decompilation:` line naming byte comparison, an awesome-decomp-games `data/additions.json` object (DOS, decomp, ai_flag true), a ⚠️-marked awesome-game-decompilations PC line, and a decomp.me preset issue for msdos / wcc10.6 / `-4r -s -fpi`**

Execution context nonce: 4313982a6d6a4591

## Performance

- **Duration:** about 5 min
- **Started:** 2026-10-25T14:15:47Z
- **Completed:** 2026-10-25T14:20:18Z
- **Tasks:** 2
- **Files modified:** 1 (docs/listings.md, created)

## Accomplishments

- A header that says who sends what (the owner opens each PR and files the issue; Claude drafts only; decomp.me is never accessed by automation), the shared facts every draft uses, and a before-sending checklist.
- awesome-rea: read upstream `categories/game-decompilation.md` and `CONTRIBUTING.md` (one line, one sentence, mandatory verification clause naming the mechanism; README is generated by `scripts/build-readme.py`). The drafted line follows the `- [Name](link) - Decompilation: ...` shape of the existing entries and says a function counts "only by byte comparison".
- awesome-decomp-games: read upstream `CONTRIBUTING.md`, `data/additions.json` and `data/games.json` (DOS is an existing platform value with 126 entries; titles follow `Game (repo)`). The drafted object is valid JSON with platform DOS and type decomp.
- awesome-game-decompilations: read the upstream README; the PC / Computer section is bare alphabetical links, and AI projects get a leading ⚠️ (its "AI disclosure" section). The drafted line is `- [⚠️ X-COM: Apocalypse (DOS)](...)` with its exact neighbours.
- decomp.me: a preset issue (msdos, wcc10.6, `-4r -s -fpi`) citing the docs/toolchain.md evidence (10.6-only runtime modules, register convention, `rep movsd` struct copies, `__CHK` functions without `-s`, EMU387), written for the owner to file by hand.

## Task Commits

1. **Task 1 (tracer): awesome-rea draft read from upstream** - `90e4d0e` (docs)
2. **Task 2: awesome-decomp-games, awesome-game-decompilations and decomp.me drafts** - `74afbf8` (docs)

Tracer gate: interactive run, `human_verify_mode` end-of-phase, `<verify>` automated only, so the verify was re-run after the Task 1 commit (exit 0) and the plan expanded without a checkpoint.

## Verification run

- Task 1 `<automated>`: exit 0 (hygiene 65 passed, 3 skipped), before and after the commit.
- Task 2 `<automated>`: exit 0 (hygiene 65 passed, 3 skipped).
- JSON acceptance check: `uv run python -c` extracted the single fenced `json` block of the `## awesome-decomp-games` section and `json.loads` parsed it: keys ai_flag, description, needs_assets, platform, title, type, url; platform DOS, type decomp, ai_flag true.
- Per-section check (`uv run python -c`): each of the four sections contains "Who sends it: the owner", "AI-assisted", "byte comparison", "No game files are distributed", the repo URL and the progress page URL: all True.
- `uv run ruff check .`: all checks passed. Stub scan (TODO, FIXME, placeholder, coming soon, TBD) over docs/listings.md: no hits.
- Content check: the drafts carry no game bytes, disassembly, Watcom source text or object bytes; the instruction names they mention (`rep movsd`, `__CHK`) are the ones docs/toolchain.md already publishes as evidence.

## Files Created/Modified

- `docs/listings.md` - the four listing drafts, the sender rule and the before-sending checklist.

## Decisions Made

- The awesome-decomp-games object adds `ai_flag: true` and `needs_assets: "byo"` beyond the CONTRIBUTING template; both keys are used by other entries in upstream `data/additions.json` (22 and 7 of 81 entries). The `source` key that existing entries carry was left out: CONTRIBUTING's template omits it and its values name where a maintainer found the project.
- No match counts or percentages are written into any draft; the progress page link carries them, so the drafts stay true until the owner sends them.
- The decomp.me draft names the issue tracker from the compilers.py link in docs/toolchain.md and tells the owner to confirm the request channel by hand; no tool opened decomp.me or `decompme/decomp.me`.

## Deviations from Plan

None - plan executed exactly as written. There is no "## 06-19" section in rulings.md, so no orchestrator ruling applied. R-A (skip reasons) and R-B (build/ evidence) did not come into play: no test was added and nothing was written under build/.

Flagged assumption check: all three upstream files exist at the paths D-33 names (`categories/game-decompilation.md`, `data/additions.json`, README PC section, which is headed `## PC / Computer`); no layout change to record.

## Issues Encountered

- The harness refused two compound Bash commands that embedded `git` in `$(...)` or in a chain ("names git in a form too complex to verify that it stays inside the worktree"). Split into plain commands; the plan ledger was written with the literal worktree git-dir path. No guardrail deny was worked around.

## Known Stubs

None.

## Threat Flags

None. T-06-46 (every draft states AI-assisted and byte-comparison proof) and T-06-47 (drafts only, upstream read with read-only `gh api`, decomp.me never accessed, the owner sends each one) are mitigated as planned.

## User Setup Required

None. At the pilot checkpoint the owner sends each draft by hand after the before-sending checklist in docs/listings.md.

## Next Phase Readiness

- DI-35 and DI-36 drafts are ready for the pilot checkpoint. The progress page link only resolves once the owner sets the Pages source.
- RPT-05 is shared with 06-18, 06-22, 06-24, 06-26 and 06-27; REQUIREMENTS.md was not touched here (shared-ID gate), the orchestrator marks it when the last declaring plan finishes.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*

## Self-Check: PASSED

- FOUND: docs/listings.md
- FOUND: 90e4d0e (ancestor of HEAD)
- FOUND: 74afbf8 (ancestor of HEAD)
