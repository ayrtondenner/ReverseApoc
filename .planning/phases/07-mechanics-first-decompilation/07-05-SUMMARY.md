---
phase: 07-mechanics-first-decompilation
plan: 05
subsystem: tooling
tags: [callgraph, le, fixups, capstone, tarjan, dec-01, d-02]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "contextpack.CallIndex (direct/tail edges), asm.walk/FixupIndex, le.Fixup, check.ExeInputs"
provides:
  - "tools/reverseapoc/callgraph.py: DIRECT/POINTER/TABLE/MIDROW/HAND, EDGE_KINDS, TABLE_SLOT_GAP, Edge, MidRowRef, CallGraph (build, callees, callers), build_for, closure, sccs, reach"
  - "tests/test_callgraph.py: 27 synthetic-LE tests (every edge kind, every report, SCC order, reach via)"
affects: [07-10, 07-12, 07-22, 07-26]

actuals:
  tokens: 8669
  tasks: 3
  commits: 8
plan_head_before: 0f9de364337258572e5dcddb10a133cd2c95c821
plan_head_after: 1d640d5715addfae899b4c8c1d89dac737767b91

tech-stack:
  added: []
  patterns:
    - "Typed edge graph over the LE: CallIndex for direct edges, fixups for pointer/table/midrow"
    - "Iterative Tarjan plus a heap-ordered leaves-first condensation for a canonical SCC order"
    - "BFS-level reach with the strongest weakest edge kind among shortest paths"

key-files:
  created:
    - tools/reverseapoc/callgraph.py
    - tests/test_callgraph.py
  modified: []

key-decisions:
  - "Table slots are every data off32/ptr16:32 fixup onto any functions.csv row start (research Q1's count, reproduced exactly: 67 slots in 13 runs UFO2P, 35 in 12 TACP); only game/thunk targets become table edges"
  - "Orphan tables are unreferenced runs (no game/thunk referrer) that point at a game/thunk row; a run of runtime-only slots is not a root"
  - "A MidRowRef from data has src_row None; mid-row targets are game/thunk rows only (all 64/64 data mid-row refs research counted land in runtime rows, so the real reports carry 0 data entries)"
  - "Direct edges drop runtime targets (D-02), so they are CallIndex's callees minus edges into runtime rows"

patterns-established:
  - "Synthetic LE call-graph images: made-up rel32/off32/ptr16:32 encodings on the conftest objects"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "CallGraph.build gives exact direct (= CallIndex) and pointer edges; runtime rows are leaves, thunks walked, a planted edge fails"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_callgraph.py#test_exact_edge_set, test_direct_and_tail_edges, test_pointer_edge, test_runtime_row_is_a_leaf, test_planted_edge_fails"
        status: pass
    human_judgment: false
  - id: D2
    description: "Table runs (16-byte gap rule), mid-row references with boundary flag, indirect-call counts, orphan tables; jump tables add nothing"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_callgraph.py -k \"table or jump or midrow or indirect or orphan\""
        status: pass
    human_judgment: false
  - id: D3
    description: "closure with stop nodes, sccs in a stable leaves-first order without recursion, reach with the via rule"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_callgraph.py#test_closure_follows_edges_and_stops, test_sccs_cycle_and_order, test_sccs_deep_chain_no_recursion_limit, test_shortest_weakest_path, test_reach_is_deterministic"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 05: Typed call graph Summary

**Stdlib-plus-capstone call graph of one EXE from its LE bytes and fixups: direct (CallIndex), pointer, table, mid-row and hand edge kinds, mid-row/indirect/orphan reports, closure with stop nodes, iterative-Tarjan SCCs in a canonical leaves-first order, and `reach` with the shortest-then-strongest `via` rule.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-10-27T14:52:30Z
- **Completed:** 2026-10-27T15:13:46Z
- **Tasks:** 3 (plus one RED/GREEN fix pair)
- **Files modified:** 2 (both new)

## Accomplishments

- `CallGraph.build(rows, flat, fixups, *, code, data)` and `build_for(exe)`. Direct edges come from `contextpack.CallIndex.build`, with edges into runtime rows dropped. Pointer edges come from off32/ptr16:32 fixups in game/thunk rows that land on another such row's start. Table edges link code rows to slot runs. Mid-row edges link a code row to another row it references in the middle. Every tuple and mapping is sorted, so two builds compare equal.
- Reports: a `MidRowRef` (source, source row, target, target row, `code`/`data`, instruction-boundary flag from `asm.walk`) for every mid-row reference. Unresolvable `call reg` / `call [mem]` (no fixup) are counted per row and never turned into edges. Orphan pointer runs are listed by their first slot.
- `closure`, `sccs` (iterative Tarjan restricted to a node set, condensation ordered leaves first with heap ties by smallest address) and `reach` (hops plus the weakest edge kind on the chosen shortest path, roots `entry`).
- Real-file sanity run, read-only from the main checkout's `orig/` (scratch script, counts only, not committed). Numbers for plan 07-22:

| | UFO2P | TACP | Research Q1 |
|---|---|---|---|
| CallIndex callees (all targets) | 5,288 | 4,885 | 5,288 / 4,885 (equal) |
| direct edges (runtime targets dropped, D-02) | 4,730 | 4,429 | |
| pointer edges | 339 | 332 | 343 / 336 (research included runtime-row targets) |
| table slots / runs | 67 / 13 | 35 / 12 | 67 / 13, 35 / 12 (equal) |
| runs referenced from game/thunk rows | 3 | 2 | 10 / 8 (research counted references from any code; "any code" gives 9 / 8) |
| table edges | 18 | 19 | |
| mid-row code refs (boundary true) | 243 (223) | 220 (200) | 243 / 220 (equal) |
| mid-row data refs into game/thunk rows | 0 | 0 | 64 / 64, all into runtime rows |
| midrow edges | 32 | 32 | |
| unresolvable indirect calls (rows) | 24 (16) | 36 (25) | |
| orphan runs | 9 | 9 | "6 targets / 6 targets" (a different unit) |
| largest SCC: direct only | 9 | 120 | 9 / 120 (equal) |
| largest SCC: direct+pointer+table | 32 | 159 | 32 / 160 |
| largest SCC: all kinds incl. midrow | 136 | 212 | |
| build time, deterministic | 13 s, yes | 15 s, yes | |

## Task Commits

1. **Task 1 (tracer): direct and pointer edges, closure.** RED `8b42043` (test), GREEN `ec1b368` (feat). Tracer gate: interactive run, `end-of-phase` mode, verify is automated-only. The verify was re-run and passed (11/11), so expansion went ahead.
2. **Task 2: table runs, mid-row refs, indirect counts, orphans.** RED `a71f595` (test), GREEN `b5ae488` (feat).
3. **Task 3: SCCs and `reach`.** RED `95635d7` (test), GREEN `25e9731` (feat).
4. **Slot-rule fix (Rule 1).** RED `6a93e98` (test), fix `1d640d5` (fix).

## TDD Gate Compliance

Each RED commit was checked with `gsd-tools check tdd-red-evidence` on pytest JUnit XML. All four returned `RED_EVIDENCE_OK` (`target_test_failed`):
- Task 1: `test_exact_edge_set` failed on its assertion (the stub returns an empty edge set). Six tests failed, all with AssertionError. Five passed on the stub because they are invariants: the edge-kind constants, the planted-edge helper raising on an empty graph, the runtime-leaf check, determinism and `build_for` equality.
- Task 2: `test_table_run_edges` failed on its assertion (no table edges). Seven failed. `test_jump_table_gives_no_edge` passes on the stub by design, since it is a "no edge" invariant.
- Task 3: `test_sccs_cycle_and_order` failed on its assertion (the stub returns an empty tuple). Six failed, all with AssertionError: `test_reach_is_deterministic` uses `.get` so it fails on the assertion, not on a KeyError.
- Fix pair: `test_table_runs_count_every_row_start_slot` failed on its assertion (runtime and ptr16:32 slots split the run, so no edges came out).

Each RED commit includes the API-surface stub (empty results, or the `MidRowRef` type) so the tests fail on assertions, not on import. Phase 6 RED commits did the same.

## Files Created/Modified

- `tools/reverseapoc/callgraph.py`: the typed call graph, reports, closure, SCCs, reach.
- `tests/test_callgraph.py`: synthetic-LE images (made-up encodings) for every edge kind and report, plus hand-made graphs for SCC/reach.

## Decisions Made

See key-decisions above. Also:
- `Edge` is ordered, and a row's callees are sorted by (target, kind rank). One `Edge` exists per (src, dst, kind), so A->B can be both `direct` and `pointer`, and `reach` picks the stronger one.
- `CallGraph.edges` has an entry for every game/thunk row, possibly empty, so `sccs(graph, graph.edges)` covers every node.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The table-slot rule did not reproduce the measurement the plan relies on**
- **Found during:** the real-file sanity run after Task 3 (read-only, main checkout `orig/`).
- **Issue:** the plan's wording ("data-object off32 fixups whose target is a code-row start", implemented as off32 onto game/thunk starts) gave 51 slots in 10 runs (UFO2P) and 19 in 8 (TACP). Research Q1 measured 67/13 and 35/12, and the plan's flagged assumption says 07-22 compares against those counts. Leaving out runtime-row and ptr16:32 slots also splits real runs at the gaps they leave.
- **Fix:** a slot is any off32 or ptr16:32 data fixup onto any row start. Runtime and data-in-code slots shape the runs but add no edge. A run's span ends at its last slot's own size (6 bytes for ptr16:32; the plan's "+4" for off32). Orphan roots must point at a game/thunk row.
- **Files modified:** tools/reverseapoc/callgraph.py, tests/test_callgraph.py.
- **Verification:** new `test_table_runs_count_every_row_start_slot` (RED then green). The real-file counts now equal research: 67/13 and 35/12.
- **Committed in:** `6a93e98` (test), `1d640d5` (fix).

**2. [Rule 3 - Blocking] Plan commit ledger not written to the git dir**
- **Issue:** the worktree sandbox refuses writes under `.git/worktrees/...`, so the gsd-executor ledger file could not be created.
- **Fix:** the commit count was measured against the dispatch base: `git rev-list --count 0f9de36..1d640d5` = 8. Both heads are recorded in the frontmatter.

### Orchestrator rulings applied

- R-A: no new test skips (test_callgraph has no skip). R-B: no container step in this plan. R-C: not applicable (worktree). R-D: no subagents dispatched. This plan has no plan-specific section in rulings.md.

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking). **Impact:** the slot fix keeps the 16-byte rule and makes 07-22's run-count comparison line up with research. Table edges are unchanged on the real files (18 / 19). No scope creep.

## Issues Encountered

- Research's "runs referenced from code" (10 / 8) counts references from any code-object fixup, runtime included. Table edges only come from game/thunk rows (3 / 2 runs), because runtime rows are leaves (D-02). A run that only runtime code references (for example an init-routine table) therefore shows up as an orphan root, which is what review needs. Plan 07-22 should record this difference.
- Largest SCC over direct+pointer+table is 159 in TACP against research's 160. The extra function probably comes from research counting pointer edges into runtime rows. Midrow edges grow the largest SCC to 136 / 212. Plan 07-22 / 07-26 should decide whether hub and SCC numbers include `midrow`.

## User Setup Required

None.

## Next Phase Readiness

- 07-10 (mechanics generator), 07-12 (locator) and 07-26 (picker) can import `callgraph.build_for`, `closure`, `sccs` and `reach`.
- `hand` edges are a constant only. 07-10 adds them from `config/mechanics.toml`, for example by building a new `CallGraph` with the extra `Edge(src, dst, HAND)` entries merged into `edges`.
- Container step deferred to the orchestrator: `docker compose run --rm test` (CLAUDE.md container done gate). The host suite passed: 2707 passed, 229 skipped, all skips pre-existing (orig/, Watcom, Ghidra, clang, objdiff, container-only, POSIX-only). `uv run ruff check .` is clean.

Execution context nonce: c489e306bef405d4

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*

## Self-Check: PASSED

- tools/reverseapoc/callgraph.py, tests/test_callgraph.py exist; contain `class CallGraph`, `def closure(`, `TABLE_SLOT_GAP = 16`, `class MidRowRef`, `def sccs(`, `def reach(`.
- Commits 8b42043, ec1b368, a71f595, b5ae488, 95635d7, 25e9731, 6a93e98, 1d640d5 are on HEAD.
