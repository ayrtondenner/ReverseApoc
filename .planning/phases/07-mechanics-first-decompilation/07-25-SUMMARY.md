---
phase: 07-mechanics-first-decompilation
plan: 25
subsystem: data
tags: [mechanics, tier-2, dec-01, d-01, d-03, d-04, d-31, f36, 263, sign-off]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-22 signed Tier 1 (digest 7f892df5...d39294, 973 must-match) and hub rule; 07-12 `mechanics locate`; 07-10 mechanics write/check/digest/status; spike 007 (verdict PARTIAL)"
provides:
  - "config/mechanics.toml: [[tier]] id = 2 signed by ayrtondenner on 2026-10-30 (members_sha256 d8763a40...78df8ed), 27 #263 items (2-28), 18 entries for 9 `in` items"
  - "config/mechanics-members.csv: regenerated, 2,455 rows (1,154 member, 343 hub, 776 closure, 182 asm)"
  - "Tier 2 must-match: 409 rows (372 UFO2P + 37 TACP), 181 of them not already Tier 1 must-match"
affects: [07-26, 07-28, 07-32, 07-15, 07-39, 07-41]

actuals:
  tokens: 45000
  tasks: 3
  commits: 2
plan_head_before: e7f001eecd247c6493964acaad710fec2e5246ae
plan_head_after: 8599827e0cafd3a186811b5bf79881a5d037b391

tech-stack:
  added: []
  patterns:
    - "Tier N entries are screened for F36 effect 3 first: a candidate whose earlier-tier role is `closure` reopens that tier's digest, so it is held back and shown to the owner with its member gain (in-memory variants script)"
    - "Shared-data-reference route: the data target that only a handful of rows reference (for example 0x000E0D48) identifies a table without the OpenApoc headers"

key-files:
  created: []
  modified:
    - config/mechanics.toml
    - config/mechanics-members.csv

key-decisions:
  - "Owner ruling 2026-10-30: sign-as-drafted by ayrtondenner. Unlocated items 263-3, -4, -8, -25, -26, -27, -28 are out with reason \"not located yet (owner ruling 2026-10-30)\""
  - "UI-chrome items 263-10, -11, -14, -16, -17, -18 out; 263-19, -20, -23, -24 out by D-01; 263-21 a duplicate of 997"
  - "The two held-back entries (UFO2P 0x00089360 for 263-2, TACP 0x000141A0 for 263-22) stay out, so Tier 1 is untouched: digest still 7f892df5...d39294, 973 must-match"
  - "Tier 2 is signed with 9 `in` items and 409 must-match rows; it keeps matching in Milestone 2 (D-05)"

patterns-established:
  - "One `mechanics locate` log per item under build/gate/07-evidence/25-locate-<item>.txt, with the script that wrote it beside it"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "Tier 2 drafted: #263 items 2-28 with scopes, 18 located entries, members regenerated, Tier 1 digest unchanged"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "uv run reverseapoc mechanics check (no problems); 28 #263 items; uv run pytest -q tests/test_mechanics.py tests/test_mechanics_real.py (67 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tier 2 signed off by the owner; members_sha256 equals `mechanics digest --tier 2`; Tier 1 still verifies"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "uv run reverseapoc mechanics check; signed tiers 2; full host suite 3,933 passed, 38 skipped"
        status: pass
    human_judgment: true
    rationale: "D-04: the sign-off is the owner's ruling, quoted verbatim below and in commit 8599827"

duration: 85min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 25: Tier 2 (the rest of #263) located, drafted and signed off Summary

**ayrtondenner signed Tier 2 as drafted. Of the 27 #263 items, 9 are `in`, with 18 entries found by the get_text, file-name, shared-table and call-graph routes. That gives 409 must-match rows (372 UFO2P + 37 TACP), 181 of them new beyond Tier 1. The other 18 items are out: 7 not located yet, 6 UI chrome, 4 under D-01, and 1 a duplicate of #997. Tier 1's signature (7f892df5...d39294, 973 must-match) is untouched.**

Execution context nonce: 9a69c09a0e6dcce3

## Performance

- **Duration:** about 85 min of work (start 2026-10-30T17:52:24Z, end 19:17Z), plus the owner's checkpoint
- **Tasks:** 3 (tracer draft, owner checkpoint, record)
- **Files:** 2 modified

## The owner's ruling (Task 2, verbatim as relayed by the orchestrator)

> Owner answer (relayed by the orchestrator, 2026-10-30): "sign-as-drafted by ayrtondenner", dated 2026-10-30.
> - The 7 unlocated items (3, 4, 8, 25, 26, 27, 28) move OUT with the reason "not located yet (owner ruling 2026-10-30)".
> - The UI-chrome outs (10, 11, 14, 16, 17, 18), the D-01 outs (19, 20, 23, 24) and 21 as a duplicate of #997 stand as proposed.
> - The two held-back entries stay out, so Tier 1 is untouched: its digest must still be 7f892df5...d39294 after your write.

## Accomplishments

- **Signed Tier 2.** `[[tier]] id = 2` ("OpenApoc #263: the rest of the city and agent mechanics") records:
  - `signed_off_by = "ayrtondenner"`;
  - `signed_off_date = 2026-10-30`;
  - `members_sha256 = d8763a40e298fb7367aa776d7da7ef3f6d9898aa22436579726e0e06778df8ed`, equal to `mechanics digest --tier 2`.
- **The in/out line as signed:**

  | Scope | Items (#263-n) |
  |---|---|
  | in (9) | 2, 5, 6, 7, 9, 12, 13, 15, 22 |
  | out, not located yet (7) | 3, 4, 8, 25, 26, 27, 28 |
  | out, UI chrome (6) | 10, 11, 14, 16, 17, 18 |
  | out, D-01 (4) | 19, 20, 23, 24 |
  | duplicate of 997 (1) | 21 |

- **The entries.** Each entry has a locate log under `build/gate/07-evidence/25-locate-263-<n>.txt`. U is UFO2P and T is TACP.

  | Item | Entries | Route | Members / full closure |
  |---|---|---|---|
  | 263-2 infiltration | U 0x0006F3C0, 0x0006FC80 (2 of the 3 readers of the table 0x000E0D48); U 0x0009A0A0 (graph screen, text 22/80) | table (shared data ref), string | U 28 / 979 |
  | 263-5 economy | U 0x000946B0 (building figures, text 37/108-117) | string | U 33 / 979 |
  | 263-6 funding | U 0x00098A70 (text 40/0-10) | string | U 7 / 173 |
  | 263-7 diplomacy | U 0x00099710 (only row referencing 0x0012799C and 0x0016F387) | table | U 1 / 2 |
  | 263-9 bribes | U 0x000977F0 (text 22/122) | string | U 11 / 979 |
  | 263-12 repair | U 0x0006CA40 (called by the clock advance and the time-skip path); U 0x0006CB90 (message, text 24/33) | call-graph, string | U 5 / 979 |
  | 263-13 base training | U 0x0004F100 (text 37/241-243, 37/331; also a 263-1 entry) | string | U 9 / 20 |
  | 263-15 transfers | U 0x00067930, 0x00091AF0, 0x0009E0C0, 0x000A1990 | string | U 249 / 980 |
  | 263-22 map spawn | U 0x000ACDC0 (unresolved-units hand-off file); T 0x00014EA0 (reads the city hand-off files) | file | U 180 / 979; T 37 / 147 |

- **D-03.** Spike 007's verdict was PARTIAL, so the call-graph route was added. It found the shared data references for #263-2 and #263-7 and the clock-side caller for #263-12.
  - The OpenApoc extractor headers are absent from `build/openapoc-extractors/`, so no table could be re-located by name.
  - Items 263-4 and 263-28 depend on that route, because their names appear only in list-driven text.
- **Unlocated leads**, kept in `25-tier2-summary.txt` for Milestone 2:
  - 263-3: 0x0006F9B0, 0x00071460;
  - 263-8: 0x00092970;
  - 263-27: 0x0006DAA0 and 0x00098240.

## Tier 2 counts

`uv run reverseapoc mechanics status --tier 2` reports `tier 2: 409 members, 0 matched, 0 partial, 409 unmatched`.

| | must-match | hub | closure | asm | full closure | new must-match (not Tier 1 must-match) |
|---|---|---|---|---|---|---|
| UFO2P | 372 | 97 | 436 | 76 | 981 | 177 |
| TACP | 37 | 10 | 53 | 47 | 147 | 4 |
| Tier 2 | 409 | 107 | 489 | 123 | 1,128 | 181 |

- The members file has 2,455 rows (was 2,450): 1,154 member (was 973), 343 hub (was 350), 776 closure (was 945) and 182 asm.
- Seven Tier 2 entries are rows the hub rule marks as hubs, and as entries they are members (D-31): 0x0006CA40, 0x0006CB90, 0x00067930, 0x00091AF0, 0x0009E0C0, 0x000A1990 and 0x000ACDC0.
- The re-scope of the 7 unlocated items changed no members row, because out items had no entries.

## Effect on Tier 1 (F36)

- Tier 1's digest after both writes is `7f892df5689c656b1c8d0895326713140d1a2080ce7b7103dc4e9a6e84d39294`, so it is unchanged.
- `mechanics status --tier 1` still reports `973 members, 2 matched, 6 partial, 965 unmatched`.
- The three effects that reopen it:
  1. min_items: the signed rule has 0, so it has no effect;
  2. a hand `[[edge]]` from a Tier 1 row: none was added;
  3. a Tier 2 entry that Tier 1 reaches only through hubs.
- **Effect 3 held back seven candidates** (`25-variants.txt`). Each one alone reopens Tier 1, because its Tier 1 class turns from closure to hub.
  - Only two would add must-match rows: U 0x00089360 (+17) and T 0x000141A0 (+22). The owner kept both out.
  - The other five add nothing: U 0x000A0A40, 0x0009DA90, 0x000B0F70, 0x000B4590 and 0x000ACD70 are already Tier 2 members through the signed entries.

## Sanity criteria

- get_text stays a hub (U 0x00063800, T 0x0005B360).
- The drawing rows stay out of must-match: U 0x00027020 and T 0x0001F080 are hubs, and U 0x00016864 is asm.
- The BIOS-tick readers remain #997-only members.
- Every Tier 2 entry is a member of its own item.

## Task Commits

1. **Task 1: draft Tier 2 (tracer).** Commit `c43b175`: `data(07-25): draft Tier 2 (#263)`. It holds config/mechanics.toml and config/mechanics-members.csv. The tracer verify was re-run before the checkpoint and passed (end-of-phase mode, automated verify only).
2. **Task 2: the owner's ruling.** A checkpoint, so there was nothing to commit.
3. **Task 3: record the sign-off.** Commit `8599827`: `data(07-25): Tier 2 signed off by ayrtondenner (D-04)`. Its body quotes the ruling. It holds config/mechanics.toml only, because the members file did not change.

## Files Created/Modified

- `config/mechanics.toml`: the Tier 2 tier with its sign-off, 27 `[[item]]` tables and 18 `[[entry]]` tables. It holds addresses, text section/index numbers and short details in our own words, and no game strings or OpenApoc text (D-21, T-07-74).
- `config/mechanics-members.csv`: regenerated, 2,455 rows.

## Decisions Made

- The key-decisions above.
- **Titles.** The titles of 263-20, -23 and -24 are placeholders ("Checklist item N: OpenApoc tooling, modding or project work"), because research did not record their subjects. 263-19 uses research's label "Map editor". The owner kept them as proposed.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F36:** Tier 1's digest was checked after every write and never changed, so no re-sign was needed.
  - The effect-3 candidates were held back from the committed draft and put to the owner with their member gain, instead of reopening Tier 1.
- **R-A:** no new tests and no new skip reasons.
- **R-B:** host only; no container step was run.
- **R-C:** ` M .planning/config.json` belongs to the orchestrator and was never staged.
- **R-D:** no subagents.

### Auto-fixed Issues

None. The draft keeps the plan's shape. The only addition is the held-back candidate list, which F36 required.

**Total deviations:** 0 auto-fixed; the F36 ruling was applied as above.
**Impact:** none on scope.

## Issues Encountered

- **Most good Tier 2 entries sit in Tier 1's closure.** #997 reaches 1,197 of 1,553 UFO2P rows. A Tier 2 entry of class "closure" in Tier 1 reopens Tier 1's digest, even though Tier 1's must-match set does not change.
  - Tiers 3 and 4 (07-28, 07-32) will meet the same effect 3, likely more often.
  - A tooling option for the owner: let `_tier_role` class a later-tier non-hub entry as closure for earlier tiers. That would make such reopenings disappear. It was not done here, because it is out of the plan's files.
- **Speed.** Building the call graph per helper run is slow (about 1-2 min per EXE). The helpers were batched (25-xq.py) to load once.

## Verification

- `uv run reverseapoc mechanics check`: `mechanics: no problems`.
- `mechanics digest --tier 1` gives 7f892df5...d39294 (unchanged); `--tier 2` gives d8763a40...78df8ed (recorded).
- Two tiers carry members_sha256.
- `uv run pytest -q tests/test_mechanics.py tests/test_mechanics_real.py`: 67 passed (after Task 1 and after Task 3).
- **Full host suite on main** (`uv run pytest -q -rs`): 3,933 passed and 38 skipped in 13:12.
  - Every skip reason is F2-allowed and none is new: objdiff-cli, Ghidra, clang, ninja, symlink privileges, POSIX-only, Windows file names, non-UTF-8 names and container-only.
- `uv run ruff check .`: All checks passed.
- **Evidence** (gitignored, build/gate/07-evidence/):
  - Tier 2 summary: 25-tier2-summary.txt.
  - Locate logs: 25-locate-263-*.txt and 25-locate-all.sh.
  - Variants: 25-variants.py and 25-variants.txt.
  - Helpers: 25-xq.py, 25-xref.py, 25-textsearch.py and 25-xq-round*.txt.
  - Writes and checks: 25-write.txt, 25-write-signed.txt, 25-check.txt, 25-check-signed.txt.
  - Digests and status: 25-digest-1.txt, 25-digest-2.txt, 25-tier2-status.json, 25-tier2-status-signed.txt.
  - Test runs: 25-t1-pytest.txt, 25-pytest-full.txt, 25-ruff.txt.

## User Setup Required

None.

## Next Phase Readiness

- `signed_tiers` now returns (1, 2). The driver's tier order can read Tier 2's must-match set, but Tier 2 matching belongs to Milestone 2 (D-05).
- Plans 07-28 (Tier 3) and 07-32 (Tier 4) should screen entries for F36 effect 3 the same way. Tier 2's digest is now one more signature that can reopen.
- Unlocated #263 items can return in Milestone 2 with the OpenApoc headers (table route) or a reading pass. The leads are in 25-tier2-summary.txt.

## Self-Check: PASSED

- config/mechanics.toml and config/mechanics-members.csv exist; build/gate/07-evidence/25-tier2-summary.txt exists.
- Commits c43b175 and 8599827 are on HEAD.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
