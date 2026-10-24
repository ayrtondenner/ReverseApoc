---
phase: 05-split-and-first-matches
plan: 15
subsystem: docs
tags: [docs, hygiene, ghidra, lxloader, docker, objdiff, spike-005, learnings]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-01 spike 005 verdict VALIDATED (objdiff pairing shape, 2nd-relocation blind spot); 05-12 Ghidra 12.1.4 + LxLoader v12.1.4-1, OpenJDK 21.0.12.1 and clang 18.1.3 in the image (898,389,257 bytes), ghidra-export (UFO2P 1408, TACP 1498), include/watcom_compat.h and the lint verb"
provides:
  - "tests/test_hygiene.py: test_docs_place_ghidra_in_the_image (8 stale phrases absent from live docs; coding-style.md names include/watcom_compat.h; toolchain.md names ghidra-export) and test_toolchain_records_spike_005 (spike link + verdict read from the spike README)"
  - "Live docs place Ghidra 12.1.4 + lastonesky loader headless in the Docker image: docs/workflow.md Phase 5 row, docs/toolchain.md image table and version pins, docs/tools.md Ghidra/GhidraMCP/clang/retrokit rows, docs/coding-style.md compat-header bullet, design spec host line and diagram, README Analysis line"
  - "docs/toolchain.md records the D-03 outcome, the bytes-and-fixups-from-le.py rule (P3, P4), the headless export facts and the spike 005 result"
  - "docs/learnings.md: two dated 2026-10-23 Phase 5 entries (8 learnings) with pointers to the rules"
affects: [05-16, 05-20, phase-06]

actuals:
  tokens: 7660
  tasks: 2
  commits: 3
plan_head_before: a6cbc0f0426b24b68ab6aa07e9067bc7bbdd87ee
plan_head_after: 2d60e8aabc4a528accc57bce59beb2ea370b64ee

tech-stack:
  added: []
  patterns:
    - "Stale-phrase hygiene test: a tuple of phrases that were in a live doc, scanned over _live_docs(), plus needles the correction must leave"
    - "A doc's spike verdict is checked against the spike README's own `verdict:` line, not a copied string"

key-files:
  created: []
  modified:
    - tests/test_hygiene.py
    - docs/workflow.md
    - docs/toolchain.md
    - docs/tools.md
    - docs/coding-style.md
    - docs/superpowers/specs/2026-10-19-reverseapoc-design.md
    - README.md
    - docs/learnings.md

key-decisions:
  - "docs/tools.md retrokit row moved from Use (alternative loader) to Skip (not used, D-03), so no live doc leaves the loader choice open"
  - "docs/toolchain.md version pins: GhidraMCP status Later; clang 18.1.3 and capstone 5.0.9 rows added; the '(or retrokit)' loader cell dropped"
  - "The spike-005 assertion lives in its own test (test_toolchain_records_spike_005) in Task 2, per ruling F7, and reads the verdict from the spike README"

patterns-established:
  - "Each corrected doc statement cites its source (D-xx, 05-RESEARCH.md section, plan SUMMARY or spike README)"

requirements-completed: [SPL-01, SPL-12]

coverage:
  - id: D1
    description: "No live doc places Ghidra in WSL2 or leaves the loader choice or the compat-header path open; coding-style.md names include/watcom_compat.h; toolchain.md names ghidra-export"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_docs_place_ghidra_in_the_image (failed at RED c396653 with 8 hits, passes at e78e7ea)"
        status: pass
    human_judgment: false
  - id: D2
    description: "toolchain.md links spike 005 and states its verdict exactly as the README's verdict: line; the 'Phase 5 spike decides' sentence is gone"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_toolchain_records_spike_005"
        status: pass
      - kind: other
        ref: "grep -q 005-objdiff-omf-elf docs/toolchain.md && grep -qE '^## 2026-1[0-2]-[0-9]{2}: .*(capstone|objdiff|Ghidra|splice)' docs/learnings.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "The prose of the new toolchain.md, tools.md, coding-style.md and learnings.md text states only what the spike record, 05-RESEARCH VERIFIED facts, the SUMMARYs and the code show"
    verification: []
    human_judgment: true
    rationale: "Fidelity of doc prose to its sources is a reading judgement; the tests only pin the stale phrases, the needles and the verdict"

duration: 5min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 15: Ghidra in the image, the D-03 outcome and spike 005 in the docs Summary

**Every live doc now places Ghidra 12.1.4 with the lastonesky LE loader headless in the Docker image (own cached stage, OpenJDK 21), with decomp.wtf still in WSL2. docs/toolchain.md records the image contents (898,389,257 bytes after the D-20 strip), the D-03 outcome (BW-header walk, retrokit not used, bytes and fixups always from le.py), the export counts (UFO2P 1408, TACP 1498) and spike 005 (verdict VALIDATED, the `_TEXT`/REL/name shape objdiff pairs, the 2nd-relocation blind spot). docs/learnings.md has 8 dated Phase 5 learnings. Two hygiene tests keep the stale wording out.**

Execution context nonce: e4c43a1b18a20923

## Performance

- **Duration:** 5 min
- **Started:** 2026-10-24T02:19:11Z
- **Completed:** 2026-10-24T02:24:07Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- `test_docs_place_ghidra_in_the_image`: none of the 8 stale phrases (`Ghidra 12.1.4 + JDK 21 in WSL2`, `WSL2 (with JDK 21)`, `Ghidra and decomp.wtf run in WSL2`, `WSL2: Ghidra`, `(or retrokit), in WSL2`, `(lastonesky or retrokit) in WSL2`, `**Decided in Phase 5.**`, `Its path is decided in Phase 5`) appears in a live doc. All 8 were present at the base, and RED failed with exactly 8 hits.
- docs/workflow.md Phase 5 row (build column only), README Analysis line, design spec Constraints host line (the owner decision of 2026-10-23, D-04, is quoted) and the diagram label `Docker: Ghidra + LE loader (headless)`, at the same arrow column (48) as the decomp.wtf line.
- docs/toolchain.md:
  - Image table: the header is `In the image`. New rows for OpenJDK 21, Ghidra 12.1.4 + LxLoader (headless, `uv run reverseapoc ghidra-export`) and clang 18 (lint gate). A note says capstone 5.0.9 comes with `uv sync` and gives the image sizes from 05-12. Ghidra/JDK, GhidraMCP and retrokit are gone from "Outside the container".
  - "Ghidra and loaders": the D-03 outcome, the P3/P4 bytes-and-fixups rule with the double-listed straddler counts, and the headless export facts.
  - GhidraMCP is Later.
  - Version pins: Ghidra and the loader are sha256-pinned, with rows for clang 18.1.3 and capstone 5.0.9. GhidraMCP is Later.
  - "objdiff and the OMF bridge": the spike 005 result.
- docs/tools.md: the Ghidra row says Docker, installed (Phase 5) and that retrokit is not used. GhidraMCP is Later. There is a new clang 18 **Use** row (D-14, apt pin `clang-18=1:18.1.3-1ubuntu1`), and the retrokit row is Skip.
- docs/coding-style.md: the compat header is `include/watcom_compat.h`, active only under clang. `uv run reverseapoc lint` runs it with `-D__WATCOMC__=1060` (checked against `tools/reverseapoc/lint.py`).
- docs/learnings.md: two entries dated 2026-10-23, newest first.
  - Ghidra headless: LeLoader's `e_lfarlc == 0x40`/BW rule, analyzeHeadless needing an existing project dir, Java because Jython and PyGhidra are unavailable on 3.14, straddlers listed twice.
  - capstone/off32/splice/objdiff: capstone's `__version__`, raw off32 fields holding `target_off`, splice masking LE fields only, objdiff's 2nd-relocation blind spot.

## Task Commits

1. **Task 1 (tracer): stale-phrase test, then the corrections**: `c396653` (test, RED), `e78e7ea` (docs, GREEN). Tracer gate (interactive, `end-of-phase`, automated-only verify): `uv run pytest -q tests/test_hygiene.py` re-run, 59 passed and 3 skipped, then expanded to Task 2.
2. **Task 2: spike 005 in toolchain.md and the learnings journal**: `2d60e8a` (docs, with `test_toolchain_records_spike_005`).

## TDD notes (RED evidence, semantic assessment)
- Task 1 RED `c396653`: `uv run pytest -q tests/test_hygiene.py -k ghidra_in_the_image` gave 1 failed, `AssertionError: assert [...8 items...] == []` on the stale-phrase assertion, with the first hit `docs\coding-style.md: Its path is decided in Phase 5`. The target test ran and failed on its planned assertion for the intended reason, with no collection, import or fixture fault. GREEN `e78e7ea`: 59 passed.
- `test_toolchain_records_spike_005` (Task 2, a `type="auto"` task) was committed with the doc change. To prove it can fail, I ran it against the base toolchain.md (`git show HEAD:docs/toolchain.md` before the Task 2 edit): that text still holds `The Phase 5 spike decides` (1 hit) and no `005-objdiff-omf-elf` (0 hits), so both assertions would fail.

## Files Created/Modified
- `tests/test_hygiene.py`: `_STALE_GHIDRA_PHRASES`, `test_docs_place_ghidra_in_the_image`, `_SPIKE_005`, `test_toolchain_records_spike_005`. These were added after `test_toolchain_records_the_compiler_result`; the 05-03 and 05-12 tests are unchanged.
- `docs/workflow.md`, `docs/toolchain.md`, `docs/tools.md`, `docs/coding-style.md`, `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`, `README.md`, `docs/learnings.md`.

## Decisions Made
See `key-decisions` in the frontmatter. Sources for every new statement:
- spike 005 README: verdict, pair, plants, objdiff shape.
- 05-12 SUMMARY: image contents and sizes, apt pins, counts, the data-object entry, the scripts compiling unchanged.
- 05-RESEARCH.md "Pattern 2: Ghidra headless export" `[VERIFIED]` facts: BW walk, 0xF474, object bases, the P4 SHA-1 cross-check, the double-listed straddler counts, Jython/PyGhidra, Pitfalls 1, 2 and 6.
- 05-03 SUMMARY: capstone version quirk, `ghidra_loadable`.
- 05-07, 05-08 SUMMARYs: raw fields are never read as addresses and are rewritten to their addend.
- Code: `tools/reverseapoc/land.py` docstring, `lint.py` flags, `x86.check_capstone`, `ghidra.py` TemporaryDirectory and `-deleteProject`.
- docs/toolchain.md LE table: UFO2P obj2 0xD0000, TACP 0xE0000.

## Deviations from Plan

**Orchestrator ruling F7:** the hygiene assertion that docs/toolchain.md contains `005-objdiff-omf-elf` moved from Task 1 to Task 2, the task that adds the link, as a separate `test_toolchain_records_spike_005`. It checks the exact phrase `spike [005](../.planning/spikes/005-objdiff-omf-elf/README.md), verdict <README verdict>`, with the verdict read from the README's `verdict:` line. A bare `verdict VALIDATED` would also match spike 004's existing line. Task 2's commit therefore also touches tests/test_hygiene.py. Every task ended green.

I also followed the "For 05-16 and 05-15 (notes from 05-12)" items:
- Ghidra 12.1.4 + LxLoader v12.1.4-1, OpenJDK 21.0.12.1, clang 18.1.3 and 898,389,257 bytes are recorded in docs/toolchain.md.
- So are the export counts UFO2P 1408 / TACP 1498 and the spike 005 verdict VALIDATED.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Two more stale "open loader choice" cells**
- **Found during:** Task 1
- **Issue:** Two more cells kept the loader choice open, which the must-have truth forbids:
  - docs/toolchain.md version pins said `lastonesky v12.1.4-1 (or retrokit)` and GhidraMCP `Phase 5`.
  - docs/tools.md's retrokit row was `**Use** (alternative LE loader and export)`, status Phase 5.
- **Fix:** the pins table now names the loader alone (sha256-pinned), adds clang 18.1.3 and capstone 5.0.9 rows, and marks GhidraMCP Later. The retrokit row is Skip (not used, D-03).
- **Files modified:** docs/toolchain.md, docs/tools.md
- **Committed in:** `e78e7ea`

**2. [Rule 1 - Accuracy] Learnings wording narrowed to what was measured**
- **Found during:** Task 2
- **Issue:** a first draft said the loader "refused" the old synthetic fixture. The research says this was read from LeLoader.java and not run against Ghidra.
- **Fix:** the entry says the loader would refuse it, "read from LeLoader.java's source, not run".
- **Committed in:** `2d60e8a`

---

**Total deviations:** 1 orchestrator ruling (F7) + 2 auto-fixed (1 missing critical, 1 accuracy)
**Impact on plan:** No scope change. All edits stay in the plan's 8 `files_modified`.

## Issues Encountered
None.

## Left for the owner (not changed, per the plan's flagged assumptions)
- docs/tools.md ast-grep row: install method "Docker or pipx, decided in Phase 5". No Phase 5 decision covers ast-grep, so the row is unchanged.
- Design spec line 76, the decisions table: it still says `Ghidra 12.1.4 + lastonesky ghidra-lx-loader or retrokit, GhidraMCP 2.0 headless under Python 3.13`. Spec edits were limited to lines 49 and 88.
- README line 62 (retrokit in the reused-projects table) and line 139 (GhidraMCP in the Analysis tools table): credit and kickoff tables, not Ghidra-location claims. Left as written.
- docs/tools.md REA row ("WSL2 (Node MCP server, Ghidra backend)", Later): a separate optional tool's own install, not where our Ghidra runs. Left as written.
- docs/legal.md line 26 (decomp.wtf in WSL2) is correct and unchanged.

## Verification
- `uv run pytest -q tests/test_hygiene.py`: 60 passed, 3 skipped.
- `grep -q "005-objdiff-omf-elf" docs/toolchain.md && grep -qE "^## 2026-1[0-2]-[0-9]{2}: .*(capstone|objdiff|Ghidra|splice)" docs/learnings.md`: exit 0.
- `uv run pytest -q && uv run ruff check .` in the worktree: 1224 passed, 200 skipped, ruff clean.
  - The skips are the real-file, Ghidra, clang and container-only tests: the worktree has no orig/ or Watcom tree, and this plan changes no code they exercise.
- `git diff --name-only a6cbc0f..HEAD -- docs/research .planning/research`: empty.

## Next Phase Readiness
- 05-16 can cite docs/toolchain.md "Ghidra and loaders" for the drop-the-data-object-entry rule.
- 05-20's docs audit has two more hygiene tests pinning the Phase 5 corrections.

## Self-Check: PASSED
- FOUND: tests/test_hygiene.py, docs/workflow.md, docs/toolchain.md, docs/tools.md, docs/coding-style.md, docs/superpowers/specs/2026-10-19-reverseapoc-design.md, README.md, docs/learnings.md
- FOUND commits: c396653, e78e7ea, 2d60e8a (`git rev-list --count a6cbc0f..HEAD` = 3 before this SUMMARY commit)

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
