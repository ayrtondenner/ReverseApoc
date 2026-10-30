---
phase: 07-mechanics-first-decompilation
plan: 28
subsystem: data
tags: [mechanics, tier-3, dec-01, d-01, d-03, d-04, f26, f36, 264, sign-off, re-sign]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-25 signed Tier 2 (d8763a40...78df8ed, 409 must-match) and the F36 effect-3 screen; 07-22 signed Tier 1 (7f892df5...d39294, 973 must-match); 07-12 `mechanics locate`; 07-10 write/check/digest/status"
provides:
  - "config/mechanics.toml: [[tier]] id = 3 signed by ayrtondenner on 2026-10-30 (members_sha256 a37cad55...c052c6), 33 #264 items, 23 entries for 11 `in` items"
  - "Tier 2 re-signed by ayrtondenner on 2026-10-30 for the UI-chrome wording only (members_sha256 ab88dd39...10f6b7)"
  - "config/mechanics-members.csv: regenerated, 2,526 rows (1,271 member, 335 hub, 687 closure, 233 asm)"
  - "Tier 3 must-match: 428 rows (328 UFO2P + 100 TACP), 117 of them not already Tier 1 or Tier 2 must-match"
affects: [07-32, 07-15, 07-39, 07-41, "the gap plan for must-match-only digests"]

actuals:
  tokens: 101000
  tasks: 3
  commits: 3
plan_head_before: 5f5bbb2f564847cc9863bfa887e76cfa40aa7c6a
plan_head_after: 7d07bd493b1230dbfe5a7a17ecb6c15146393f0d

tech-stack:
  added: []
  patterns:
    - "Prefer a hub or not-yet-reached caller as the entry when the specific row is closure in an earlier tier: the row still joins the tier's members, and no earlier digest moves (F36 effect 3)"
    - "Wording-only re-sign guard: byte-compare the members file and `mechanics status --tier N` (text and JSON) before and after, and diff the TOML down to the changed reason lines, before writing the new digest"

key-files:
  created: []
  modified:
    - config/mechanics.toml
    - config/mechanics-members.csv

key-decisions:
  - "Owner ruling 2026-10-30: Tier 3 sign-as-drafted by ayrtondenner. The 9 unlocated items (264-7, -8, -11, -12, -13, -15, -19, -20, -25) are out as \"not located yet (owner ruling 2026-10-30)\"; 264-14 stays out with its neutral title until the owner gives its text; the D-01 outs (1, 22, 23, 29-33), the UI-chrome outs (24, 26, 27) and 264-2 as a duplicate of 997 stand; the 8 held-back candidates stay out"
  - "Owner ruling 2026-10-30, \"Fix both now\": the UI-chrome reasons of Tier 3 (3) and Tier 2 (6) read \"(owner ruling 2026-10-30)\"; Tier 2 is re-signed by ayrtondenner, and only those six reason strings changed"
  - "Owner ruling 2026-10-30 on the design question, \"Fix it in Phase 7\": the orchestrator adds a gap plan after wave 7 (the digest covers must-match membership only, with a hub column in the members CSV). Nothing for it was built in this plan"
  - "Tier 1 is untouched: 7f892df5...d39294, 973 must-match"

patterns-established:
  - "One `mechanics locate` log per item under build/gate/07-evidence/28-locate-<item>.txt, with 28-locate-all.sh beside them; the call-graph facts are in 28-xq-round*.txt (25-xq.py)"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "Tier 3 drafted: #264 items 1-33 with scopes, 23 located entries, members regenerated, Tier 1 and Tier 2 digests unchanged"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "uv run reverseapoc mechanics check (no problems); 33 #264 items; uv run pytest -q tests/test_mechanics.py tests/test_mechanics_real.py (67 passed); 28-sanity.txt ALL PASS"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tier 2 re-signed for the wording only: members file and Tier 2 status identical before and after"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "cmp config/mechanics-members.csv build/gate/07-evidence/28-members-before.csv; cmp 28-t2-status-before/after (.txt and .json); 28-t2-diff.txt shows 6 reason lines"
        status: pass
    human_judgment: true
    rationale: "D-04: the re-sign is the owner's ruling, quoted verbatim below and in commit bb5f1e5"
  - id: D3
    description: "Tier 3 signed off by the owner; members_sha256 equals `mechanics digest --tier 3`; Tiers 1 and 2 still verify"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "uv run reverseapoc mechanics check; three signed tiers; full host suite 3,933 passed, 38 skipped; ruff clean"
        status: pass
    human_judgment: true
    rationale: "D-04: the sign-off is the owner's ruling, quoted verbatim below and in commit 7d07bd4"

duration: 74min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 28: Tier 3 (#264) located, drafted and signed off Summary

**ayrtondenner signed Tier 3 as drafted. Of the 33 #264 items, 11 are `in`, with 23 entries found through get_text, hand-off files, file names, the organisation data table and the call graph. That gives 428 must-match rows (328 UFO2P + 100 TACP), 117 of them new beyond Tiers 1 and 2. The other 22 items are out or duplicate: 9 not located yet, 8 under D-01, 3 UI chrome, 264-14 pending the owner's text, and 264-2 a duplicate of #997. On the owner's "Fix both now", Tier 2 was also re-signed, and the only change in it is the wording of its six UI-chrome reasons. Tier 1 is untouched.**

Execution context nonce: 4d3c3a4a2b9eb226

## Performance

- **Duration:** about 74 min of work: from 20:53:37Z to the checkpoint at about 21:25Z, then 21:40Z to 22:08Z after the ruling, which includes the 13-minute full suite.
- **Tasks:** 3 (tracer draft, owner checkpoint, record)
- **Files:** 2 modified

## The owner's ruling (Task 2, verbatim as relayed by the orchestrator)

> Owner answers for Task 2 (relayed by the orchestrator, 2026-10-30):
>
> 1. **Tier 3:** "sign-as-drafted by ayrtondenner", dated 2026-10-30.
>    - The 9 unlocated items (7, 8, 11, 12, 13, 15, 19, 20, 25) move OUT as "not located yet (owner ruling 2026-10-30)".
>    - 264-14 stays OUT with its neutral title, pending the owner's text.
>    - The D-01 outs and the UI-chrome outs (24, 26, 27) stand, and 264-2 is a duplicate of 997.
>    - The 8 held-back candidates stay out.
> 2. **Wording:** "Fix both now".
>    - Before writing Tier 3's sign-off, remove "(proposal, owner rules at sign-off)" from Tier 3's three UI-chrome reasons and say they are owner-ruled out on 2026-10-30.
>    - Fix Tier 2's six UI-chrome reasons the same way, then RE-SIGN Tier 2 as ayrtondenner, 2026-10-30, with the new digest. The owner chose that option knowing it means a Tier 2 re-sign whose only change is the wording.
>    - Guard: before writing the Tier 2 sign-off, verify that the ONLY difference in Tier 2 is those six reason strings. Its members, roles, entries and every member row must be unchanged; compare `mechanics status --tier 2` and the CSV rows before and after.
>    - If anything else changed, STOP with a CHECKPOINT and do not sign.
>    - Tier 1 must stay untouched (digest 7f892df5...d39294).
> 3. **Design question:** "Fix it in Phase 7". The orchestrator adds a gap plan after wave 7: the digest covers must-match membership only, with a hub column in the members CSV. Record the answer in your SUMMARY; implement nothing for it in this plan.

## Accomplishments

- **Signed Tier 3.** `[[tier]] id = 3` ("OpenApoc #264: city-wide rules, score, endgame and vehicles") records:
  - `signed_off_by = "ayrtondenner"`;
  - `signed_off_date = 2026-10-30`;
  - `members_sha256 = a37cad5530791f9ec49d4038ea034ebb6309b641521a688736836320fcc052c6`, equal to `mechanics digest --tier 3`.
- **Re-signed Tier 2 for the wording.** Its digest moved from d8763a40...78df8ed to `ab88dd39001cd17c755b3af18b54df95bbe1852ac65fa1bc018a49319210f6b7`.
  - The guard passed before the sign-off was written:
    - the members CSV is byte-identical;
    - `mechanics status --tier 2` (text and JSON) is identical: 409 members, 0 matched, 0 partial, 409 unmatched;
    - the TOML diff is exactly six reason lines, on items 263-10, -11, -14, -16, -17 and -18.
- **The in/out line as signed:**

  | Scope | Items (#264-n) |
  |---|---|
  | in (11) | 3, 4, 5, 6, 9, 10, 16, 17, 18, 21, 28 |
  | out, not located yet (9) | 7, 8, 11, 12, 13, 15, 19, 20, 25 |
  | out, D-01 (8) | 1, 22, 23, 29, 30, 31, 32, 33 |
  | out, UI chrome (3) | 24, 26, 27 |
  | out, not described; owner to rule (1) | 14 |
  | duplicate of 997 (1) | 2 |

- **The entries.** U is UFO2P and T is TACP. Each item has a locate log at `build/gate/07-evidence/28-locate-264-<n>.txt`.

  | Item | Entries | Route | Members / full closure |
  |---|---|---|---|
  | 264-3 nightly score and finances | U 0x0004AAF0 (time-skip branch, calls the row that opens the score and finance screens); U 0x00098240 (score screen, text 37/144-156); U 0x00099050 (finance screen, text 44/0-9) | call-graph, string | U 14 / 980 |
  | 264-4 weekly funding | U 0x00098A70 (text 40/0-10; also the 263-6 entry) | string | U 7 / 173 |
  | 264-5 victory and defeat | U 0x00060C80 (defeat screen, text 44/17, 44/19); U 0x000B4A50 (battle-result path, calls the victory-screen row); T 0x000127F0 (abort dialog, text 35/81-82) | string, call-graph | U 16 / 985; T 71 / 1120 |
  | 264-6 alien takeover | U 0x0004A9D0 (periodic city update, the only caller of the takeover row) | call-graph | U 16 / 979 |
  | 264-9 graphs and stats | U 0x0009A5D0 (graph screen, text 44/26, 38/129) | string | U 9 / 162 |
  | 264-10 medals, per-battle stats | U 0x000B2A90 and T 0x000156A0 (the battle-result hand-off, both Tier 1 entries); T 0x000774C0 (calls the service-record row) | file, call-graph | U 102 / 995; T 35 / 1124 |
  | 264-16 treaties, raids, storming | U 0x00092970 (event messages, text 24/16, 24/18, 24/22); U 0x00072AA0 (raid order, text 38/118); U 0x000B2A90 and T 0x000156A0 (the relations-result hand-off) | string, file | U 249 / 995; T 2 / 1122 |
  | 264-17 illegal flyers | U 0x00092970 (text 24/21, 37/91) | string | U 19 / 979 |
  | 264-18 craft retreat | U 0x000586C0 (returning-damaged message, text 24/34) | string | U 35 / 991 |
  | 264-21 dynamic music | U 0x000B5950, T 0x000AF770 (music file names); U 0x000B5FD0, T 0x000AFDF0 (music switches) | file, call-graph | U 12 / 96; T 13 / 96 |
  | 264-28 starting agents | U 0x000BA360 (new-game setup, references the organisation data, research Q3) | table | U 72 / 992 |

- **D-03.** The call-graph route was used again (spike 007 verdict PARTIAL), for 264-3, -5, -6, -10 and -21. The OpenApoc extractor headers are still absent, so no table could be re-located by name.
- **Unlocated leads**, kept in `28-tier3-summary.txt` for Milestone 2:
  - 264-7 and 264-8 (portals): the gate texts are reached only through computed indexes (section 37 rows);
  - 264-15: texts 24/31-32 are reached only through computed indexes, with 0x00092970 as the lead;
  - 264-19 and 264-20: need the vehicle-movement call graph;
  - 264-11, -12, -13 and -25: no text or file name was found.

## Tier 3 counts

`uv run reverseapoc mechanics status --tier 3` reports `tier 3: 428 members, 1 matched, 2 partial, 425 unmatched`.

| | must-match | hub | closure | asm | full closure | new must-match (not Tier 1/2 must-match) |
|---|---|---|---|---|---|---|
| UFO2P | 328 | 110 | 511 | 102 | 1,051 | 55 |
| TACP | 100 | 179 | 761 | 114 | 1,154 | 62 |
| Tier 3 | 428 | 289 | 1,272 | 216 | 2,205 | 117 |

- The members file has 2,526 rows (was 2,455): 1,271 member, 335 hub, 687 closure and 233 asm.
- Moving the 9 unlocated items out changed no members row, because they had no entries.

## Effect on Tiers 1 and 2 (F36)

- **Tier 1:** the digest is 7f892df5...d39294 after every write, so it is unchanged. `mechanics status --tier 1` still reports 973 members.
- **Tier 2:** the draft left its digest unchanged (d8763a40...78df8ed). The only later change is the owner-ruled wording re-sign above.
- **Effects 1 and 2 do not apply:** min_items is 0 and no `[[edge]]` was added.
- **Effect 3 held back 8 candidates** (`28-variants.txt`). Each one alone reopens an earlier tier:

  | Candidate | Reopens | Adds Tier 3 must-match rows |
  |---|---|---|
  | U 0x00098180 (264-3) | Tier 2 | 0 |
  | U 0x00060F50 (264-5) | Tier 1 | 0 |
  | U 0x0006FE10 (264-6) | Tiers 1 and 2 | 0 |
  | U 0x000863F0 (264-10) | Tier 1 | 0 |
  | T 0x000550C0 (264-10) | Tier 1 | 0 |
  | U 0x000ACD70 (264-16) | Tier 1 | 1 |
  | U 0x000B63F0 (264-21) | Tiers 1 and 2 | 0 |
  | T 0x000B0200 (264-21) | Tiers 1 and 2 | 0 |

  The drafted entries reach seven of these rows already, so holding them back costs one row (U 0x000ACD70's gain). The owner kept them out.
- **The reverse case** (`28-reverse.txt`): rows that are entries of other tiers and that a tier's projection counts as hubs.
  - Tier 2's projection counts 13 of them: 8 Tier 1 entries and 5 Tier 3 entries. The 5 Tier 3 entries were already hub rows, so no digest moved.
  - Tier 3's projection counts 28 Tier 1/2 entries.

## Sanity criteria (28-sanity.txt and 28-sanity-signed.txt: ALL PASS)

- get_text stays a hub (U 0x00063800, T 0x0005B360).
- The drawing rows stay out of must-match: U 0x00027020 and T 0x0001F080 are hubs, and U 0x00016864 is asm.
- The BIOS-tick readers (U 0x00011430, T 0x00011500, 0x000116B0) remain #997-only members.
- Every Tier 3 entry is a member of its own item.

## Task Commits

1. **Task 1: draft Tier 3 (tracer).** Commit `eae7599`: `data(07-28): draft Tier 3 (#264)`. It holds config/mechanics.toml and config/mechanics-members.csv. The tracer verify was re-run before the checkpoint and passed (end-of-phase mode, automated verify only).
2. **Task 2: the owner's ruling.** A checkpoint, so there was nothing to commit.
3. **Task 3: record the sign-offs.**
   - Commit `bb5f1e5`: `data(07-28): Tier 2 re-signed by ayrtondenner for the UI-chrome wording (D-04)`. Its body quotes ruling item 2 and the guard results.
   - Commit `7d07bd4`: `data(07-28): Tier 3 signed off by ayrtondenner (D-04)`. Its body quotes ruling items 1-3.
   - Both commits touch config/mechanics.toml only, because the members file did not change.

## Files Created/Modified

- `config/mechanics.toml`:
  - the Tier 3 tier with its sign-off, 33 `[[item]]` tables and 23 `[[entry]]` tables;
  - Tier 2's six reasons and its new members_sha256.
  - Only addresses, text section/index numbers and short details in our own words: no game strings and no OpenApoc text (D-21, T-07-83).
- `config/mechanics-members.csv`: regenerated, 2,526 rows.

## Decisions Made

- The key-decisions above.
- **Titles.** Items 264-1, -22, -23 and -29..-33 have placeholder titles ("Checklist item N: OpenApoc tooling, modding or project work"), because the research did not record their subjects. 264-14 has the neutral title "Not described in the research; owner to rule" (F26). The other titles paraphrase the research's labels. None was copied from the issue.
- **Entry choice under F36.** Where the specific row was closure in an earlier tier, the entry is its hub or not-yet-reached caller, and the row itself joins Tier 3's members through it:
  - U 0x000B4A50 for the victory screen;
  - U 0x0004A9D0 for the takeover row;
  - U 0x000B5FD0 and T 0x000AFDF0 for the music rows;
  - T 0x000774C0 for the service record.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F36:** the Tier 1 and Tier 2 digests were checked after every write.
  - The draft never moved them.
  - The effect-3 candidates were held back and put to the owner, instead of reopening a tier.
  - The only later digest change is the Tier 2 re-sign, which the owner chose.
- **Orchestrator ruling F26:** 264-14 has the neutral title "Not described in the research; owner to rule", is scoped out and gives the stated reason.
- **R-A:** no new tests and no new skip reasons.
- **R-B:** host only; no container step was run.
- **R-C:** ` M .planning/config.json` belongs to the orchestrator and was never staged.
- **R-D:** no subagents.

### Owner-directed additions (beyond the plan's text)

- **The Tier 2 wording re-sign** (commit bb5f1e5), with the before/after guard. It was done on the owner's "Fix both now". The plan itself only signs Tier 3.

### Auto-fixed Issues

**1. [Rule 1 - Bug] CRLF line endings in the appended Tier 3 items**
- **Found during:** Task 1.
- **Issue:** the item tables were generated by a Python print on Windows, which wrote CRLF. The repo uses `eol=lf`.
- **Fix:** normalised config/mechanics.toml to LF before the commit. The digest was unchanged, because the parsed content is the same.
- **Files modified:** config/mechanics.toml.
- **Committed in:** eae7599.

**Total deviations:** 1 auto-fixed (Rule 1), 2 rulings (F36, F26) and 1 owner-directed re-sign.
**Impact:** none on scope.

## Issues Encountered

- **The F36 effect-3 pressure is as expected.** Many good Tier 3 rows sit in the Tier 1/2 closure. Choosing hub callers as entries kept every earlier digest, at a cost of one must-match row.
  - The owner's design ruling ("Fix it in Phase 7") moves this into a gap plan: the digest will cover must-match membership only, with a hub column in the members CSV.
- **Two of my evidence edits were not shell redirections.** The summary text file was corrected once with a Python in-place write, and the TOML was normalised the same way. All evidence files were otherwise written by shell redirection.

## Verification

- `uv run reverseapoc mechanics check`: `mechanics: no problems`.
- Digests: `--tier 1` gives 7f892df5...d39294 (unchanged), `--tier 2` gives ab88dd39...10f6b7 (re-signed) and `--tier 3` gives a37cad55...c052c6 (recorded). Three tiers carry members_sha256.
- `uv run pytest -q tests/test_mechanics.py tests/test_mechanics_real.py`: 67 passed (after Task 1 and after Task 3).
- **Full host suite on main** (`uv run pytest -q -rs`): 3,933 passed and 38 skipped in 13:07.
  - Every skip reason is F2-allowed and none is new: symlink privileges, Ghidra, objdiff-cli, container-only, ninja, non-UTF-8 names, clang, Windows file names and POSIX-only.
- `uv run ruff check .`: All checks passed.
- **Evidence** (gitignored, build/gate/07-evidence/):
  - Tier 3 summary: 28-tier3-summary.txt.
  - Locate logs: 28-locate-264-*.txt and 28-locate-all.sh.
  - Call-graph rounds: 28-xq-round*.in/.txt.
  - Variants and checks: 28-variants.py/.txt, 28-sanity.py/.txt, 28-sanity-signed.txt, 28-reverse.py/.txt.
  - Writes: 28-write.txt, 28-write-t2.txt, 28-write-signed.txt.
  - Checks: 28-check.txt, 28-check-t2-resign.txt, 28-check-signed.txt.
  - Digests: 28-digest-{1,2,3}.txt, 28-digests-signed.txt.
  - Tier 2 guard: 28-members-before.csv, 28-t2-status-before/after.{txt,json}, 28-t2-digest-before.txt, 28-t2-diff.txt.
  - Status: 28-tier3-status.{json,txt}, 28-tier3-status-signed.txt.
  - Test runs: 28-t1-verify.txt, 28-t3-verify.txt, 28-pytest-full.txt, 28-ruff.txt.

## User Setup Required

None.

## Next Phase Readiness

- `signed_tiers` now returns (1, 2, 3). Tier 3 matching belongs to Milestone 2 (D-05).
- 07-32 (Tier 4) meets the same effect 3, with three signatures that can reopen, unless the must-match-only digest gap plan lands first.
- 264-14 still needs the owner's title and scope. Adding them later re-signs Tier 3.

## Self-Check: PASSED

- config/mechanics.toml and config/mechanics-members.csv exist; build/gate/07-evidence/28-tier3-summary.txt exists.
- Commits eae7599, bb5f1e5 and 7d07bd4 are on HEAD.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
