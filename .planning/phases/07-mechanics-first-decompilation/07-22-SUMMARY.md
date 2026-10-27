---
phase: 07-mechanics-first-decompilation
plan: 22
subsystem: data
tags: [mechanics, tier-1, dec-01, d-04, d-22, d-26, d-31, hub-rule, sign-off, 997, 263-1]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-08 spike 007 (q1-q6, verdict PARTIAL); 07-10 mechanics.py (write/check/digest/hubs/status/graph); 07-12 locate.py (`mechanics locate`); 07-20 the signed asm list"
provides:
  - "config/mechanics.toml: Tier 1 (items 997 and 263-1, 27 entries), the signed [hub_rule] and Tier 1's sign-off record"
  - "config/mechanics-members.csv: generated members (2,450 rows: 521 member, 480 hub, 1,267 closure, 182 asm)"
  - "The #263-1 TACP post-battle stat raise located by the call graph (0x000B2510), closing spike 007's PARTIAL gap"
affects: [07-25, 07-26, 07-28, 07-32, 07-15, 07-37, 07-39, 07-41]

actuals:
  tokens: 33000
  tasks: 3
  commits: 1
plan_head_before: f50d69b607c9ef7ead91cc9b1d30cc043341e607
plan_head_after: 4d821482f9a43341b846099b9759097da63db01e

tech-stack:
  added: []
  patterns:
    - "Hub-rule candidates over every criterion computed through the mechanics API on an in-memory copy of mechanics.toml (no config edit until the owner signs)"

key-files:
  created:
    - config/mechanics-members.csv
  modified:
    - config/mechanics.toml

key-decisions:
  - "Owner ruling 2026-10-27: sign-recommended by ayrtondenner; [hub_rule] min_direct_callers = 20, largest_scc = false, max_closure_share = 0.2, min_items = 0"
  - "Owner Q1: hub and SCC figures ignore midrow edges (switch-table artefacts); the closure walk still follows them. No tooling change now (the signed rule does not use largest_scc); later tiers must keep this in mind"
  - "Owner Q2: keep 07-05's strict table rule; the research difference (UFO2P reach 1,429 vs 1,471; Tier 1 moves 0 / 1 rows under the signed rule) is recorded, no backlog item"
  - "Tier 1 must-match: UFO2P 215, TACP 306 (521); full D-02 closure 1,197 / 1,253"

patterns-established:
  - "Entry evidence is re-confirmed by a `mechanics locate` log under build/gate/07-evidence/22-locate-*.txt"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "Mid-row references of both EXEs classified (243 / 220; 0 candidate missed starts)"
    requirement: DEC-01
    verification:
      - kind: other
        ref: "uv run reverseapoc mechanics graph --exe {ufo2p,tacp} --json + scratch classifier -> build/gate/07-evidence/22-midrow.txt"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tier 1 items and entries with evidence kinds, each re-confirmed by a locate log"
    requirement: DEC-01
    verification:
      - kind: other
        ref: "uv run reverseapoc mechanics check (no problems); 22-locate-*.txt cover all 27 entries"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tier 1 and its hub rule signed by the owner; members regenerated; digest recorded and checked"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "uv run reverseapoc mechanics check; uv run pytest -q tests/test_mechanics.py tests/test_mechanics_real.py (63 passed)"
        status: pass
    human_judgment: true
    rationale: "D-04: the sign-off is the owner's ruling, quoted verbatim below and in commit 4d82148"

duration: 60min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 22: Tier 1 located, drafted and signed off Summary

**Tier 1 (#997 tick rate and #263-1 training from battle) is signed off by ayrtondenner with the hub rule "at least 20 direct callers, or an own closure above 20% of the EXE". 27 entries give a must-match set of 215 UFO2P + 306 TACP functions (521) out of a D-02 full closure of 1,197 + 1,253. The call graph located the TACP post-battle stat raise at 0x000B2510.**

Execution context nonce: 96d065acda88d38e

## Performance

- **Duration:** about 60 min including the owner's checkpoint (start 2026-10-27T20:50:33Z, end 21:50:45Z)
- **Tasks:** 3 (tracer, owner checkpoint, record)
- **Files:** 1 created, 1 modified

## The owner's ruling (Task 2, verbatim as relayed)

> sign-recommended by ayrtondenner (2026-10-27): `min_direct_callers = 20`, `largest_scc = false`, `max_closure_share = 0.2`, `min_items = 0`.
> Q1: hub and SCC numbers ignore `midrow` edges (they are switch-table artefacts); closure walking still follows them. Record this ruling in the commit body and SUMMARY (the signed rule does not use largest_scc, so no tooling change is needed now; note it for later tiers).
> Q2: keep 07-05's strict table rule; record the research difference (UFO2P 1,429 vs 1,471; Tier 1 moves 0/1 rows) — no backlog item.

**For later tiers (Q1):** `HubStats.largest_scc` and `graph_report`'s "all" SCC still count midrow edges (136 / 212 against 32 / 159 without them). Before any later tier signs a rule with `largest_scc = true`, the SCC must be computed without midrow edges, as the owner ruled.

## Accomplishments

- **Mid-row references classified** (`22-midrow.txt`).

  | Class | UFO2P | TACP |
  |---|---|---|
  | Total | 243 | 220 |
  | Data references into game rows | 0 | 0 |
  | Code references off an instruction boundary | 20 | 20 |
  | Code references on a boundary | 223 | 200 |
  | Candidate missed starts | 0 | 0 |

  - Every data mid-row reference lands in a runtime row (ruling note b confirmed).
  - Every code mid-row reference is a Watcom switch table placed in front of its function. functions.csv gives the table to the previous row. The off-boundary references are the tables' bases, and the on-boundary ones are their slots, including 15 slots that capstone decodes as `add`.
- **Tier 1 drafted** in config/mechanics.toml: items `997` and `263-1`, both EXEs, titles in our own words and the issue URLs.
  - **#997 entries.**
    - UFO2P: tick reader 0x00011430, frame loop 0x00010940, 36-unit clock 0x0004AB30, 5-minute skip 0x00011520, speed panel 0x00052150, and the six speed setters 0x00050920..0x00050AE0.
    - TACP: tick reader 0x00011500, frame step 0x000116B0, clock 0x0003D160, battle loop 0x00010EE0, second clock caller 0x000B6E50, speed panel 0x000A7490.
  - **#263-1 entries.**
    - UFO2P: hand-off reader 0x000B2A90, 17-field copy 0x000B2E80, android training label 0x0004F100, android word 0x0009B840.
    - TACP: hand-off writer 0x000156A0, post-battle raise 0x000B2510, counter raisers 0x00064B60 and 0x00067B60, and the spike's heuristic leads 0x00060080 and 0x000B26F0.
  - No `[[edge]]`: the spike proved no indirect call.
- **The TACP accrual is located (spike 007's PARTIAL gap).**
  - The program entry calls the battle loop (at 0x00010A02), then 0x000B2510, and last the hand-off writer (at 0x00010ACC) [script].
  - 0x000B2510 is the only row in that window that loads and stores hand-off stat fields (6 of 17) through a register base [script].
  - Read by hand: it walks the unit array 0x00109ED0..0x0011B360 in steps of 0x49C and adds capped gains (caps 100 and 200). Each gain divides a battle counter (+0x6A, +0x6E, +0x42 or +0x8C) by a stat value.
  - During battle, 0x00064B60 raises the +0x6A counter and 0x00067B60 raises +0x6E [script + hand]. No writers were found for +0x42 or +0x8C.
- **Hub-rule candidates** went to the owner with real numbers (`22-tier1-summary.txt`):
  - `mechanics hubs --k 10 20 40 80`: 940-1,078 UFO2P and 1,004-1,138 TACP must-match;
  - every other criterion, varied through the same API;
  - each entry's contribution;
  - the asm boundary effect;
  - the table-rule effects.
- **Signed and recorded.**
  - `[hub_rule]` holds the signed values.
  - `mechanics write` gives 2,450 rows: 521 member, 480 hub, 1,267 closure and 182 asm.
  - `[[tier]] id = 1` carries `signed_off_by = "ayrtondenner"`, `signed_off_date = 2026-10-27` and `members_sha256 = 0c668c5c...b318fc`, the value `mechanics digest --tier 1` prints.

## Tier 1 counts (the start of the done rule's count)

`uv run reverseapoc mechanics status --tier 1 --json` (`build/gate/07-evidence/22-tier1-status.json`) reports `tier 1: 521 members, 0 matched, 1 partial, 520 unmatched`.

| | must-match (member) | hub | closure | asm | full D-02 closure |
|---|---|---|---|---|---|
| UFO2P | 215 | 224 | 665 | 93 | 1,197 of 1,553 game + thunk rows |
| TACP | 306 | 256 | 602 | 89 | 1,253 of 1,526 |

## Graph notes (orchestrator rulings, notes a-e)

- **(a) TACP largest SCC, 159 vs research's 160: explained.**
  - Over direct, pointer and table edges it is 159 under 07-05's strict table rule and 160 under spike q6's 64-byte lead-in rule. UFO2P gives 32 either way.
  - So the table rule is the cause, not runtime pointer edges.
  - With midrow edges the largest SCC is 136 / 212 (213 with the lead-in rule).
- **(b) Data mid-row references:** 0 land in game or thunk rows; all 64 of 64 land in runtime rows.
- **(c) Owner questions:** put at the checkpoint and answered (Q1 and Q2 above).
- **(d) Table rule, measured** (`22-table-rule.txt`).

  | | Reach from main_ | Tier 1 reached | Tier 1 must-match, no hubs | Tier 1 must-match, signed rule |
  |---|---|---|---|---|
  | UFO2P, strict rule (kept) | 1,429 | 1,197 | 1,082 | 215 |
  | UFO2P, 64-byte lead-in | 1,471 | 1,250 | 1,134 | 215 |
  | UFO2P, lead-in + runtime-only runs as roots | 1,479 | 1,250 | 1,134 | 215 |
  | TACP, strict rule (kept) | 1,479 | 1,253 | 1,139 | 306 |
  | TACP, 64-byte lead-in | 1,479 | 1,253 | 1,139 | 305 |
  | TACP, lead-in + runtime-only runs as roots | 1,488 | 1,253 | 1,139 | 305 |

  - 1,471 is research's table step; 1,479 and 1,488 are research's figures with orphan tables.
  - Runs referenced only from runtime code (3 in UFO2P, 4 in TACP, each EXE with 6 game targets) never touch Tier 1.
- **(e) Digest-reopening effects (F36),** named in the checkpoint text. Tier 1's signature reopens when:
  1. a signed rule uses `min_items` and a later tier adds items (the signed rule has `min_items = 0`);
  2. a hand `[[edge]]` starts from a Tier 1 row;
  3. a later non-hub entry is reached by Tier 1 only through hubs. That asks for a re-sign that is not needed; it is loud, never silent.

## Task Commits

1. **Task 1: tracer (classify, draft, members, hub candidates).** Not committed, by dispatch: the commit flag was not set and the precondition needed a fully clean tree. The draft went to the owner uncommitted.
2. **Task 2: the owner's ruling.** A checkpoint; nothing to commit.
3. **Task 3: record the hub rule and the sign-off.** Commit `4d82148`: `data(07-22): Tier 1 signed off by ayrtondenner with hub rule callers>=20, closure share>0.2 (D-04, D-22)`. It holds exactly config/mechanics.toml and config/mechanics-members.csv, and its body quotes the ruling.

## Files Created/Modified

- `config/mechanics.toml`: `[hub_rule]`, `[[tier]] id = 1` with its sign-off, 2 `[[item]]` and 27 `[[entry]]` tables. It holds addresses, evidence kinds and short details in our own words, with no game strings or OpenApoc text (D-21).
- `config/mechanics-members.csv`: generated, 2,450 rows.

## Decisions Made

- The key-decisions above.
- The plan text and the owner's ruling settled the entries. The spike's two heuristic leads (0x00060080, 0x000B26F0) stay, as the plan lists them. 0x00060080 adds 23 TACP must-match rows; 0x000B26F0 adds none.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F2:** Task 3's verify also ran `uv run python -I tools/progress.py --out build/gate/07-evidence/22-site`. It exited 0, and the page rendered with the signed Tier 1 data.
- **Orchestrator ruling F36:** the checkpoint text named the digest-reopening effects (note e above).
- **Notes a-e (07-05 and 07-10 as built):** recorded under "Graph notes". Note (a) is now explained; it is no longer "unexplained".
- **Dispatch: Task 1 was not committed.** The plan's `data(07-22): draft Tier 1 ...` commit was not made, because the commit flag was off. The draft was committed only in Task 3, together with the sign-off, as one commit.
- R-A: no new tests and no new skip reasons. R-B: host only, no container step was run. R-C: ` M .planning/config.json` belongs to the orchestrator and was never staged. R-D: no subagents.

### Auto-fixed Issues

**1. [Rule 2 - Missing evidence] Extra #263-1 entries from the call-graph route**
- **Found during:** Task 1.
- **Issue:** spike 007 left the TACP accrual unlocated, and the plan asks for it to be located with the call graph.
- **Fix:** added 0x000B2510 (call-graph), plus 0x00064B60 and 0x00067B60 (data-field). Each has `22-locate-tacp-unit-array.txt` and the `22-accrual-*.txt` evidence.
- **Verification:** `mechanics check` passes, and the owner signed the draft with these entries.
- **Committed in:** 4d82148.

**Total deviations:** 1 auto-fixed (Rule 2), plus the F2/F36 rulings, notes a-e and the dispatch's no-commit Task 1.
**Impact:** none on scope; the owner saw every entry before signing.

## Issues Encountered

- **Open: the android skip on the battle side.** 0x000B2510 skips units whose field +0x96 equals 2. That may be the android test, but it is not confirmed [hand]. q3's android evidence is cityscape-only (0x0004F100).
- No writers were found for the +0x42 and +0x8C battle counters that 0x000B2510 also reads. They may be raised by register-indirect code that the scan's pattern does not match.
- A heredoc with an apostrophe broke one shell write. The evidence summary was written to the scratchpad and then copied into build/ by redirection.

## Verification

- `uv run reverseapoc mechanics check`: `mechanics: no problems`.
- `grep "^\[hub_rule\]"` and `grep members_sha256` both match in config/mechanics.toml.
- `uv run pytest -q tests/test_mechanics.py tests/test_mechanics_real.py`: 63 passed, including the real members drift test.
- `uv run reverseapoc mechanics status --tier 1 --json > build/gate/07-evidence/22-tier1-status.json`: 521 members.
- F2: `uv run python -I tools/progress.py --out build/gate/07-evidence/22-site` exited 0.
- Full host suite on main (`uv run pytest -q -rs`): 3,834 passed and 38 skipped in 11:47. Every skip reason is F2-allowed and none is new:
  - symlink privileges 5, Ghidra 5, objdiff-cli 2;
  - one each: container-only, ninja, non-UTF-8 names, clang, Windows file names, and the two POSIX-only reasons.
- `uv run ruff check .`: All checks passed.

## User Setup Required

None.

## Next Phase Readiness

- Plan 07-26 and the driver can read Tier 1's must-match set (`signed_tiers` returns (1,)).
- Plans 07-25, 07-28 and 07-32 draft Tiers 2-4 under the signed rule. They stop with a re-sign checkpoint if Tier 1's digest reopens (F36).
- Plans 07-39 and 07-41 count Tier 1 done with `mechanics status --tier 1 --require-matched` (0 of 521 now).

## Self-Check: PASSED

- config/mechanics.toml, config/mechanics-members.csv and build/gate/07-evidence/22-tier1-status.json exist.
- Commit 4d82148 is on HEAD.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
