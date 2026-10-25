---
phase: 06-reporting-and-agent-pilot
plan: 20
subsystem: docs
tags: [dockerignore, hygiene, toolchain, matching, learnings, tools, legal, design-spec]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-16 (wave dependency); 06-07's LX edit of config/watcom.toml (commit 28342e1), which the learnings entry now records"
provides:
  - ".dockerignore excludes **/*.IMG, **/*.CUE, **/*.mdf, **/*.MDF; tests/test_hygiene.py covers all twelve exe/iso/bin/img/cue/mdf cases"
  - "docs/toolchain.md: SMKP.EXE entry point obj1:0x6CB0 confirmed with parse-le --json on the main checkout's orig/"
  - "docs/toolchain.md, docs/matching.md, docs/learnings.md: after fix round 1, no live text describes Phase 5 as pending (dated learnings entries keep their words with an 'Update, 2026-10-25' note); candidates tied, -s tied, blind spot limited to the observed shape"
  - "docs/tools.md verdicts (ast-grep Later, GhidraMCP Later (Phase 7 or later), Nigel Skip per D-05, recomp.fyi D-49 risk); design-spec L76 annotation; legal.md AI-use record (progress/attempts.jsonl) and decomp.wtf line"
affects: [06-22, 06-27, README, listings, phase-7]

actuals:
  tokens: 8600
  tasks: 3
  commits: 4
plan_head_before: 5d391a95fc7e771f05cab9d5985e9a315bc99097
plan_head_after: 6e0c397442710d3818577f4b3232494feee882c9

tech-stack:
  added: []
  patterns:
    - "Stale design-spec rows are annotated below the table with a dated bullet; the row text stays as approved (D-41)"
    - "A changed tool verdict keeps the kickoff verdict in parentheses next to the new one"

key-files:
  created:
    - .planning/phases/06-reporting-and-agent-pilot/06-20-SUMMARY.md
  modified:
    - .dockerignore
    - tests/test_hygiene.py
    - docs/toolchain.md
    - docs/matching.md
    - docs/learnings.md
    - docs/tools.md
    - docs/superpowers/specs/2026-10-19-reverseapoc-design.md
    - docs/legal.md

key-decisions:
  - "SMKP.EXE entry point confirmed, not corrected: parse-le --json prints entry object 1, offset 27824 (0x6CB0), linear 93360 (0x16CB0)"
  - "The -s axis reads 'tied, not separated': both leaf matches compile with -s, but no cell without -s was compared"
  - "tools.md's Nigel row names the `reverseapoc drive` verb, not the driver.py path, because driver.py is not on this plan's base"

patterns-established:
  - "Doc claims about objdiff's relocation blind spot name the one observed instruction shape (mov dword [abs32], imm32) and say other shapes were not tested"

requirements-completed: [AGT-10, RPT-04, AGT-06]

coverage:
  - id: D1
    description: ".dockerignore excludes IMG, CUE, mdf and MDF at any depth, with the hygiene parametrize covering both cases of every image extension (DI-22, T-06-48)"
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_hygiene.py -k dockerignore (14 passed; RED at 82acd9c: IMG, CUE, mdf, MDF failed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "SMKP.EXE entry point obj1:0x6CB0 marked confirmed in toolchain.md with the parse-le command cited (DI-22)"
    verification:
      - kind: other
        ref: "grep -n \"UFOEXE/SMKP.EXE\" docs/toolchain.md | head -n 1 | grep -qi confirmed; uv run reverseapoc parse-le <main>/orig/SMKP.EXE --json -> entry {object 1, offset 27824, linear 93360}"
        status: pass
    human_judgment: false
  - id: D3
    description: "Stale toolchain/matching/learnings text fixed (DI-20, DI-25 wording, 05 rows 1 and 19a, the 06-20 rulings notes)"
    verification:
      - kind: other
        ref: "! grep -q 'candidate pending Phase 5 matches' docs/toolchain.md && ! grep -q 'Nothing recorded yet' docs/matching.md && ! grep -qE '`-s`:\\*\\* consistent' docs/toolchain.md && uv run pytest -q tests/test_hygiene.py"
        status: pass
    human_judgment: true
    rationale: "The greps prove the stale phrases are gone; whether the new wording is accurate and readable is a reviewer judgement"
  - id: D4
    description: "tools.md verdicts, recomp.fyi D-49 risk, design-spec annotation and legal.md AI-use record (DI-21, 05 row 14, D-03, D-05, D-23, D-41, D-49)"
    verification:
      - kind: other
        ref: "Task 3 <automated> verify (GhidraMCP 'Phase 7 or later', ast-grep Later, Nigel D-05, Report::split, progress/attempts.jsonl, hygiene green); git diff of the design spec is additions only"
        status: pass
    human_judgment: true
    rationale: "Public claims in docs; the wording of the verdicts and the AI-use statement is for the owner to accept"

duration: 15min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 20: .dockerignore disc images, SMKP entry check, and the Phase 5/6 doc carry-overs Summary

**.dockerignore now keeps IMG, CUE, mdf and MDF disc images out of the Docker context at any depth, and a hygiene test covers both cases. SMKP.EXE's entry point obj1:0x6CB0 is confirmed by `parse-le --json` on the real file. The toolchain, matching and learnings docs say what Phase 5 actually showed: the compiler candidates and `-s` are tied, the relocation check is the match gate, and the objdiff blind spot is stated for the one instruction shape that was tested. tools.md, legal.md and the design spec now carry Phase 6's decisions: ast-grep and GhidraMCP Later, Nigel Skip, the D-49 report risk, and `progress/attempts.jsonl` as the public AI-use record.**

Execution context nonce: dc9d133e246719e5

## Performance

- **Duration:** about 15 min
- **Started:** about 2026-10-25T14:08Z
- **Completed:** 2026-10-25T14:23Z
- **Tasks:** 3 of 3
- **Files modified:** 8 (35 insertions, 18 deletions)

## Accomplishments

- DI-22 closed: four disc-image patterns added to `.dockerignore`, pinned by six new parametrized cases in `tests/test_hygiene.py` (TDD: RED 82acd9c, GREEN 9277149).
- DI-22 closed: `uv run reverseapoc parse-le "<main checkout>/orig/SMKP.EXE" --json` (read-only) prints `"entry": {"object": 1, "offset": 27824, "linear": 93360}`. 27824 = 0x6CB0, so the doc value was right. The row is marked confirmed and the command is cited under the table.
- DI-20, DI-25 wording, 05 rows 1 and 19a. The first pass (0a2cf9b) left about eight "Phase 5 ... pending / will / once" lines in toolchain.md, plus one in matching.md. The review caught them, and fix round 1 rewrote them. After that round, no live text in toolchain.md, matching.md or learnings.md describes Phase 5 as pending. Dated learnings entries keep their original words and gain an "Update, 2026-10-25" note.
- DI-21 (docs part), 05 row 14, D-03, D-05, D-23, D-41, D-49: tools.md verdicts, the design-spec annotation and the legal.md AI-use record.

## Task Commits

1. **Task 1 (tracer, tdd): disc images and SMKP entry point**: `82acd9c` (test, RED), `9277149` (fix, GREEN + SMKP check)
2. **Task 2: stale toolchain, matching and learnings text**: `0a2cf9b` (docs)
3. **Task 3: tools.md verdicts, design-spec annotation, legal.md AI-use record**: `6e0c397` (docs)

Tracer gate: interactive run, `human_verify_mode` end-of-phase, and the tracer `<verify>` is automated only. I re-ran both verify commands after the GREEN commit and both passed, so the plan went on to Tasks 2 and 3 without a checkpoint.

### RED evidence (Task 1)

- Command: `uv run pytest -q tests/test_hygiene.py -k dockerignore`, exit 1.
- Target: `test_dockerignore_excludes_executables_and_disc_images_at_any_depth[IMG|CUE|mdf|MDF]`. 4 failed and 10 passed. Each failure is the planned assertion: `assert '**/*.MDF' in {...}` (and likewise for the other three).
- Semantic assessment: the target test ran and failed on the planned assertion, for the reason the plan predicted. The lowercase `img` and `cue` patterns already existed, so those cases passed. The run had no collection, import or fixture fault. Valid RED.
- GREEN: the same command gives 14 passed.

## Files Created/Modified

- `.dockerignore`: `**/*.IMG`, `**/*.CUE`, `**/*.mdf`, `**/*.MDF` next to the existing image lines.
- `tests/test_hygiene.py`: `ext` parametrize extended with img/IMG/cue/CUE/mdf/MDF.
- `docs/toolchain.md`:
  - SMKP row marked confirmed, with the cited parse-le command;
  - `-s` is "tied, not separated";
  - a Fallbacks-and-candidates paragraph on the tie and Phase 6's per-match evidence;
  - 11.0 "still tied after the two Phase 5 leaf matches";
  - the summary row says "tied after the two Phase 5 leaf matches; Phase 6 records per-match evidence";
  - the blind spot is limited to `mov dword [abs32], imm32`;
  - the GhidraMCP section says Later (Phase 7 or later).
- `docs/matching.md`:
  - the "How to read objdiff output" placeholder now holds what Phase 5 established;
  - "Relocation rules" now reads "confirmed in Phase 5", names relocs.py as the gate, and adds the reverse-coverage rule;
  - the `-fpi`/`-fpi87` record equality is labelled as a scratch check;
  - the `*` default paragraph says the candidates are still tied.
- `docs/learnings.md`:
  - the watcom.toml note entry records 06-07's edit (commit `28342e1`);
  - the 2026-10-19 BINNT stub entry no longer says "to be confirmed in Phase 4".
- `docs/tools.md`: the ast-grep, GhidraMCP, Nigel and recomp.fyi rows.
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`: a dated annotation bullet after the decisions table. The L76 row is unchanged.
- `docs/legal.md`: the decomp.wtf licence line, and an AI-use paragraph naming `progress/attempts.jsonl`.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

### Orchestrator rulings applied

**1. Orchestrator ruling (06-20 notes on what 06-07 built; no F number): docs/learnings.md watcom.toml note entry updated**
- The rulings cite "learnings.md L58". At this base the entry is on line 66 (the 2026-10-21 "BINW compilers ... are all LX images" bullet). It said the stale notes "stay until the owner edits it". It now says the owner authorized one edit (2026-10-24, D-43) and that plan 06-07 changed lines 37 and 106 to "the real LX compiler" in commit `28342e1`. I checked this against `git log -1 28342e1` and `config/watcom.toml` lines 37 and 106.
- Committed in `0a2cf9b`.

**2. Orchestrator ruling (06-20 notes): docs/matching.md:28's `-fpi`/`-fpi87` record-equality sentence labelled as a scratch check**
- "(LEDATA and FIXUPP records equal)" now reads "(LEDATA and FIXUPP records equal; scratch check, not logged)", the same label 06-07 used in toolchain.md.
- Committed in `0a2cf9b`.

### Auto-fixed issues

**3. [Rule 1 - Accuracy] matching.md's objdiff placeholder repeated the over-generalized blind-spot claim (05 row 1)**
- **Found during:** Task 2
- **Issue:** L57 said "objdiff compares at most one relocation per x86 instruction". That is the same over-generalization 05 row 1 flags in toolchain.md.
- **Fix:** the replacement text names the one observed shape and says it is why the relocation check and SHA-1 are needed.
- **Files modified:** docs/matching.md
- **Committed in:** `0a2cf9b`

**4. [Rule 1 - Consistency] matching.md:14 still said 11.0 was "a candidate until a Phase 5 match separates them"**
- **Found during:** Task 2
- **Fix:** it now says the candidates are still tied after the two Phase 5 leaf matches, and that Phase 6 records the evidence of each pilot match. This is the DI-25 wording.
- **Committed in:** `0a2cf9b`

**5. [Rule 1 - Consistency] toolchain.md's GhidraMCP section said "Later (Phase 6 context pack or later)"**
- **Found during:** Task 3
- **Issue:** after the tools.md change, the two docs disagreed.
- **Fix:** the section now reads "Later (Phase 7 or later)", citing D-41 and D-44. toolchain.md is in the plan's files_modified.
- **Committed in:** `6e0c397`

**6. [Rule 1 - Accuracy] Nigel row does not name `tools/reverseapoc/driver.py`**
- **Found during:** Task 3
- **Issue:** driver.py does not exist on this plan's base, because a sibling plan builds it.
- **Fix:** the row says "Phase 6 builds our own stdlib driver instead (a `reverseapoc drive` verb, D-05)". That keeps the plan's "own stdlib driver (Phase 6)" without pointing at a missing file.
- **Committed in:** `6e0c397`

### Process notes (no content change)

- **Line numbers.** The plan's line numbers had drifted:
  - Task 1 added 3 lines to toolchain.md's targets section, so its `-s` line is 169, not 166;
  - learnings.md's entries were at 66 and 94, not 58 and 86.
  I matched each target by its text, not by line number.
- **Task 1's GREEN commit uses `fix(06-20)`, as the plan prescribes,** not `feat`. The plan is `type: execute`, so the `type: tdd` gate check does not apply. The RED commit still comes before GREEN.
- **The commit ledger and the cwd sentinel were not written.** The harness refused the command that writes `gsd-plan-head-before-06-20` and `gsd-spawn-toplevel` into the worktree's git dir ("names git in a form too complex to verify"). I used the dispatch's verified base `5d391a9` as the ledger. Before each commit I ran `git rev-parse --show-toplevel` and `git symbolic-ref HEAD` as plain commands. `commits: 4` is measured with `git rev-list --count 5d391a9..HEAD`.

---

**Total deviations:** 2 orchestrator rulings applied, 4 auto-fixed (all Rule 1 doc accuracy or consistency).
**Impact on plan:** every edit stays inside the plan's 8 files_modified. No scope creep.

## Issues Encountered

- First pass: I listed only toolchain.md:148 and matching.md:14 here as stale. The review found the toolchain.md lines described above as well. Fix round 1 fixed all of them, and these two as well.
- Left alone after fix round 1: learnings.md:104 ("decomp.wtf's fork mode as the agent layer"). It sits in the dated 2026-10-19 entry and is not a "Phase 5 pending" claim. legal.md and tools.md already state D-03.

## Fix round 1 (FIX_BASE a479c1f, review-06-20.md)

| Item | Where | What changed |
|---|---|---|
| I1 | toolchain.md:128 | 11.0 is "a candidate, tied after the two Phase 5 leaf matches" (10.5/10.6/11.0 tied on game code); Phase 6 records the evidence of each pilot match. 11.0a/b are swept "if a later match favours 11.0 (the two Phase 5 leaf matches did not)" |
| I1 | toolchain.md:148 | the `__CHK` per-glob rule comes "once a match reaches one (neither Phase 5 match calls `__CHK`)" |
| I1 | toolchain.md:150 | `-4` vs `-5`: tied after the two Phase 5 leaf matches (no 5-dword copy); Phase 6 records per-match evidence |
| I1 | toolchain.md:153-156 | the four `-o*`/`-zp*`/`-zm`/`-fp3`/`-fp5` status cells each say why the two leaf matches do not touch the flag, plus the Phase 6 per-match evidence |
| I1 | toolchain.md:174 | "until a match proves them"; the two leaf matches separate no candidate; D-18's three-function rule; Phase 6 records per-match evidence |
| I1 | toolchain.md:199 | "A match proves or drops an entry" (this no longer contradicts the :201 paragraph) |
| I1 (grep) | toolchain.md:34, :37, :81, :139 | :34 and :37: build-to-build diff and primary build follow D-42 (twin matching revisited after Phase 7). :81: the loader README claim "checked in Phase 5", linking to Ghidra and loaders. :139: a per-glob rule overrides the default where a match says so, and none exists yet |
| I1 | matching.md:14 | `__CHK` rows "once a match reaches one (neither Phase 5 match calls `__CHK`)" |
| I1 (grep) | learnings.md:77, :103, :110 | dated entries kept as written, each followed by an "Update, 2026-10-25" sentence (tie stands; spike 005 kept the hybrid path; D-42) |
| I1 | SUMMARY frontmatter `provides` and Accomplishments | the completion claim corrected to what is now true |
| M1 | toolchain.md:169 | the two matches do not separate the flag set; neither original has a `__CHK` call, which is consistent with `-s` for those two functions |
| M2 | legal.md:44 | future tense from the Phase 6 driver (plan 06-23) on, and D-23's attempt-number field added |
| M3 | learnings.md:67 | "This confirms the 2026-10-19 BINNT entry below, which now says so" (it no longer quotes the removed phrase) |
| M4 | toolchain.md:379 | "11.0 tied at `-4r`, still tied after the two Phase 5 leaf matches" |
| Notes | test design, ledger | no change, per the ruling |

Verification after fix round 1:
- `uv run pytest -q -rs tests/test_hygiene.py`: 71 passed, 3 skipped. The skips are the existing `only inside the container` ones.
- `uv run ruff check .`: All checks passed.
- Re-grep: every "Phase 5" line in the three docs was reviewed. The remaining "pending", "will", "once" and "first Phase 5 matches" hits are either the corrected wording or dated text followed by its update.

## Threat Flags

None. No new network, auth, file-access or schema surface. T-06-48 (disc images in the build context) and T-06-49 (stale claims) are mitigated as the threat register says.

## Known Stubs

None.

## Verification

- `uv run pytest -q tests/test_hygiene.py -k dockerignore`: 14 passed.
- `grep -n "UFOEXE/SMKP.EXE" docs/toolchain.md | head -n 1 | grep -qi confirmed`: exit 0.
- Task 2 verify (three negative greps, then hygiene): 71 passed, 3 skipped. The 3 skips are `tests/test_hygiene.py:554: only inside the container`. They already existed and none is new.
- Task 3 verify (five greps, then hygiene): 71 passed, 3 skipped (same reason).
- Acceptance:
  - `.dockerignore` has the 4 patterns (`grep -c` = 4);
  - toolchain.md says the candidates are tied and that Phase 6 records per-match evidence (2 lines);
  - the design spec diff is additions only, with the L76 row unchanged.
- Host suite in this worktree, `uv run pytest -q -rs`: **2089 passed, 224 skipped, 0 failed**.
  - The skips are the existing real-file and tool-presence skips: the worktree has no `orig/`, no `third_party/` and no objdiff-cli on PATH.
  - This plan adds no skip.
- `uv run ruff check .`: All checks passed.
- No docker was run (worktree rule). The container suite is for the orchestrator's post-merge run.
- STATE.md, ROADMAP.md and REQUIREMENTS.md were not modified. The orchestrator updates tracking after the merge (parallel wave).

## User Setup Required

None.

## Next Phase Readiness

- 06-22 (README) can point at tools.md's new verdicts and legal.md's AI-use record.
- The pilot's per-match evidence has a documented place to land: toolchain.md "Fallbacks and candidates" and the Flags notes.
- Tick rate (OpenApoc #997): not found. This plan touched no game logic.

## Self-Check: PASSED

- FOUND: .dockerignore, tests/test_hygiene.py, docs/toolchain.md, docs/matching.md, docs/learnings.md, docs/tools.md, docs/superpowers/specs/2026-10-19-reverseapoc-design.md, docs/legal.md
- FOUND commits: 82acd9c, 9277149, 0a2cf9b, 6e0c397 (all ancestors of HEAD)

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
