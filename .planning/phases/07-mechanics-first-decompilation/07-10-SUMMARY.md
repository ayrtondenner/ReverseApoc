---
phase: 07-mechanics-first-decompilation
plan: 10
subsystem: tooling
tags: [mechanics, dec-01, d-02, d-22, d-23, d-31, tomllib, callgraph, digest]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-05 callgraph.py: CallGraph, build_for, closure(stop), sccs, reach, EDGE_KINDS"
provides:
  - "tools/reverseapoc/mechanics.py: strict mechanics.toml loader (schema, [asm_list], [hub_rule], [[tier]], [[item]], [[entry]], [[edge]]), members generator with member/hub/closure/asm roles, tier_digest/signed_tiers, asm list read/format/sha, check_committed, tier_status, hub_candidates, graph_report, load_graphs"
  - "reverseapoc mechanics write|check|digest|hubs|status|graph (exit 0/1/2)"
  - "callgraph.with_edges: merges hand edges keeping callee order (07-05 ruling note)"
  - "tests/test_mechanics.py (synthetic), tests/test_mechanics_real.py (reach pins, CallIndex equality, members drift)"
affects: [07-12, 07-15, 07-20, 07-22, 07-25, 07-26, 07-27, 07-28, 07-32, 07-37, 07-39, 07-41]

actuals:
  tokens: 24258
  tasks: 3
  commits: 6
plan_head_before: 2815ddb72530220a0d7d474ae1abe1284dda210f
plan_head_after: 45e16a34122d5aff27a08baaa3c1d0a4f5a4b22d

tech-stack:
  added: []
  patterns:
    - "Hand-edited TOML + generated, byte-checked CSV (the functions.csv / units.csv split)"
    - "Per-tier digest over a tier-N projection of the members rows plus the hub-rule line"
    - "Generator seam `mechanics.load_graphs` monkeypatched in tests, so no game files are needed"

key-files:
  created:
    - tools/reverseapoc/mechanics.py
    - tests/test_mechanics.py
    - tests/test_mechanics_real.py
  modified:
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/callgraph.py
    - tests/test_callgraph.py

key-decisions:
  - "Members CSV columns exe,address,items,tiers,member_items,via,role; role precedence member > asm > hub > closure; ids sorted by (issue, number); rows by (ufo2p, tacp; address)"
  - "A hub is any reached row meeting an enabled criterion (direct callers >= K, largest SCC with a cycle, own closure share > X, reached by >= M in items); the per-item member walk stops at hubs and asm rows minus that item's entries (D-31)"
  - "tier_digest's tier-N role for a row that is a member only of another tier: hub when via is entry, else closure (the file carries no hub flag for such rows)"
  - "An asm list that exists but is unsigned or changed since sign-off makes `mechanics write` refuse (D-23); an asm-listed entry is refused by write and reported by check"
  - "check_committed returns [] with no mechanics.toml, and asks for `mechanics write` only when entries exist without a members file (07-20 commits a schema-only TOML first)"
  - "tier_status takes the Mechanics (it needs the item -> tier map); unmatched_starts lists every member not yet matched, partial included"

patterns-established:
  - "Mechanics verbs catch their own errors and return 2 (cli.main maps _ERRORS to 1)"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "Strict mechanics.toml loader refusing unknown keys, wrong types, bad enums, non-ASCII/overlong text, long hex runs, partial sign-offs, bad cross-references"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_mechanics.py#test_load_minimal, test_load_refusals (16 cases), test_load_refuses_bad_toml_and_schema"
        status: pass
    human_judgment: false
  - id: D2
    description: "Members generator: full closure items/tiers, hub-stopped members, entries always members, asm/hub/closure roles, hand edges, shared rows, empty inputs, deterministic LF write"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_mechanics.py#test_members_from_one_entry, test_hub_stops_the_member_walk, test_entry_that_is_a_hub_stays_a_member, test_other_hub_criteria, test_asm_row_is_a_boundary, test_shared_function_one_row, test_empty_item_and_empty_file, test_members_written_atomically_and_deterministically"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tier digests and the committed-data check (signed tier drift, entry-less items, asm sign-off, runtime rows, via entry)"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_mechanics.py#test_tier_digest_changes_on_change, test_signed_tiers, test_check_clean, test_check_refuses (6 cases), test_check_without_members_file, test_committed_mechanics_check"
        status: pass
    human_judgment: false
  - id: D4
    description: "mechanics verb: write, check, digest, hubs (--k nargs +), status (--require-matched), graph"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_mechanics.py#test_cli_write_with_injected_graphs, test_digest_verb, test_cli_hubs_takes_several_k, test_status_counts_and_require_matched, test_graph_report, test_hub_candidates_report"
        status: pass
    human_judgment: false
  - id: D5
    description: "Real-file pins: reach from main_ per edge set, direct edges = CallIndex, members drift (vacuous until 07-22)"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest -q tests/test_mechanics_real.py (5 passed)"
        status: pass
    human_judgment: false

duration: 29min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 10: Mechanics map, members generator and sign-off digests Summary

**A strict `config/mechanics.toml` loader and a generator for `config/mechanics-members.csv`. Roles are member, hub, closure and asm: the walk stops at hubs and at rows on the signed asm list, and an item's entries are always its members. Per-tier SHA-256 digests make a sign-off checkable without game files. The new `mechanics` verb has six subcommands: write, check, digest, hubs, status and graph.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-10-27T16:09:10Z
- **Completed:** 2026-10-27T16:38:05Z
- **Tasks:** 3 (each a RED and a GREEN commit)
- **Files modified:** 6 (3 new)

## Accomplishments

- `mechanics.load` reads the hand-edited TOML with tomllib and refuses bad input with a `MechanicsError` that names the table and key. It checks:
  - exact key sets, types and enums (scope, evidence kind, EXE);
  - text fields: printable ASCII, at most 120 characters, no hex run longer than 64;
  - `0x%08X` addresses;
  - sign-offs: who, date and digest come together or not at all;
  - cross-references: an item's tier exists; `duplicate_of` points at an `in` item; an entry belongs to an `in` item and to one of its EXEs; no repeats.
- `compute_members` works on the call graph per EXE:
  - Each `in` item's full closure (D-02) gives `items` and `tiers`.
  - A second walk that does not expand hubs (D-22) or asm rows (D-23) gives `member_items`. The item's entries are always members and always expanded (D-31).
  - `via` comes from `callgraph.reach` over all entries.
  - `[[edge]]` hand edges join the graph through the new `callgraph.with_edges`.
  - Runtime rows never appear.
- The members CSV is written through `write_atomic`, LF only, and is deterministic. `read_members` refuses any file that `mechanics write` would not have written byte for byte.
- `tier_digest` hashes the hub-rule line plus one line per row a tier-N item reaches: `exe,address,<tier-N items>,<tier-N member items>,<tier-N role>`. `signed_tiers` lists the tiers whose sign-off is present and whose digest still matches.
- `check_committed` runs in CI without game files. It reports:
  - member rows that are not game or thunk rows;
  - items that are not `in`, and tiers that disagree with their items;
  - roles that disagree with the asm list;
  - entries missing from the file with via entry, and asm-listed entries;
  - signed tiers that changed since sign-off, or that hold an entry-less `in` item;
  - an asm list that is unsigned, changed since its sign-off or missing.
- Other verbs:
  - `mechanics hubs --tier N --k 10 20 40 80` prints the candidate hub-rule numbers per K: must-match with all edges and with direct edges only, the hubs with their direct caller counts, members per via kind, and asm rows removed.
  - `mechanics status [--tier N] [--require-matched]` checks the D-05 done rule from status.csv.
  - `mechanics graph --exe EXE` prints the call-graph reports that plan 07-22 needs.

Real-file numbers (main checkout `orig/`, read-only, counts only), for plan 07-22:

| | UFO2P | TACP |
|---|---|---|
| reach from `main_`, direct | 1,128 (research 1,128) | 1,224 (research 1,224) |
| + pointer | 1,412 (research 1,412) | 1,479 (research 1,479) |
| + table | **1,429** (research 1,471) | 1,479 (research 1,479) |
| all kinds incl. midrow (F14: recorded, not pinned) | 1,429 | 1,479 |
| CallIndex edges | 5,288 | 4,885 |
| graph edges direct / pointer / table / midrow | 4,730 / 339 / 18 / 32 | 4,429 / 332 / 19 / 32 |
| midrow refs (instruction start; from data) | 243 (223; 0) | 220 (200; 0) |
| indirect calls (rows), orphan tables | 24 (16), 9 | 36 (25), 9 |
| largest SCC: direct / d+p+t / all kinds | 9 / 32 / 136 | 120 / 159 / 212 |

## Task Commits

1. **Task 1 (tracer): loader, members from entries, `mechanics write`.** RED `e31baa6`, GREEN `d632877`. Tracer gate: the run is interactive, in `end-of-phase` mode, and the verify is automated only. The verify was re-run (21 passed), so expansion went ahead.
2. **Task 2: hub roles, asm boundary, digests, `check`/`digest`.** RED `b24f3ee`, GREEN `628123a`.
3. **Task 3: `hubs`, `status`, `graph`, real-file tests.** RED `ed627c6`, GREEN `45e16a3`.

## TDD Gate Compliance

Each RED commit was checked with `gsd-tools check tdd-red-evidence` on pytest JUnit XML, and each returned `RED_EVIDENCE_OK` (`target_test_failed`). Every RED commit carries an API-surface stub, so the tests fail on assertions rather than on imports.

- **Task 1.** Target `test_members_from_one_entry`. 21 of 21 tests failed, all on assertions or "DID NOT RAISE".
- **Task 2.** Target `test_hub_stops_the_member_walk`. 20 failed and 51 passed.
  - The 51 passes are the Task 1 tests, the existing callgraph tests and three Task 2 cases: the shared row, the empty item and file, and the hub rule turned off. Task 1 code already gives those three, so they are characterization tests.
  - Two failures first came from stub artefacts (a KeyError, and an invalid stub digest). The tests were changed to fail on assertions before the RED commit.
- **Task 3.** Target `test_hub_candidates_report`. 4 failed and 45 passed.
  - `test_committed_mechanics_check` and the three real-file tests are characterization tests: they pin the existing graph and the committed data (F28 style). Run against the main `orig/`, the real tests failed on the UFO2P table pin first (see deviation 1) and then passed.

## Files Created/Modified

- `tools/reverseapoc/mechanics.py`: the data model, loader, generator, digests, asm list, check, status, hub candidates and graph report.
- `tools/reverseapoc/cli.py`: `_add_mechanics_command` and its six subcommands; `MechanicsError` added to `_ERRORS`; docstring verb list updated.
- `tools/reverseapoc/callgraph.py`: `with_edges`.
- `tests/test_mechanics.py`: 48 synthetic tests (no game files).
- `tests/test_mechanics_real.py`: reach pins, CallIndex equality, members drift.
- `tests/test_callgraph.py`: `test_with_edges_merges_hand_edges_in_callee_order`.

## Decisions Made

The key-decisions above, plus:
- The hub list in `hubs` comes from the tier-N role: a row counts as a hub when that tier sees it as one. `callers` is the row's direct caller count.
- "Direct only" in `hubs` keeps the TOML's hand edges, because they come from mechanics.toml and not from the graph.
- `graph_report` adds the largest SCC per edge set (direct, direct+pointer+table, all kinds). Plan 07-22 needs these numbers.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F14:** `test_reachability_from_main_within_one_percent` pins direct, direct+pointer and direct+pointer+table reach only, never `midrow` or `hand`. The all-kinds count is recorded above without a pin (UFO2P 1,429, TACP 1,479). See deviation 1 for the UFO2P table value.
- **Orchestrator ruling F24:** `mechanics hubs --k` uses `nargs="+"`. `test_cli_hubs_takes_several_k` calls `--k 10 20 40 80`.
- **Orchestrator ruling F32:** `test_committed_mechanics_check` and `test_members_csv_has_no_drift` pass when there is nothing to check yet (no mechanics.toml, no members file); they do not skip. `check_committed` returns `[]` when there is no mechanics.toml.
- **Note on 07-05:** hand edges go through a new public `callgraph.with_edges`. It keeps callee order inside callgraph.py and does not use the private `_edge_key` from mechanics.py. It has its own test.
- R-A: no new skip reasons. The real-file tests skip with the same "orig/<EXE> not present" form as the existing `*_real.py` tests (4 skips in this worktree), and run wherever `orig/` exists. R-B: see the container step below. R-C: not applicable (worktree). R-D: no subagents dispatched.

### Auto-fixed Issues

**1. [Rule 1 - Bug in a planned pin] UFO2P's direct+pointer+table reach is 1,429, not research's 1,471 (2.9% off)**
- **Found during:** Task 3, the real-file run against the main `orig/`.
- **Issue:** The other research steps match exactly: direct is 1,128 / 1,224 and direct+pointer is 1,412 / 1,479. Only UFO2P's table step differs. callgraph.py (07-05, as built) wires a pointer run only from the game/thunk rows that reference it. 31 UFO2P game targets sit in runs that only runtime code references, so they are not reached. A scratch measurement that treats those runs as reached gives 1,480 / 1,489, which brackets research's 1,471. This matches 07-05's "Issues Encountered" note (runs referenced from game/thunk rows: 3 vs research's 10).
- **Fix:** The pin follows the built rule: UFO2P table step 1,429, with the reason in a comment. I also added a direct+pointer pin that matches research exactly. 07-05's table rule is not changed, because that is outside this plan's scope.
- **For plan 07-22 / the orchestrator:** the Tier 1 checkpoint should state that 42 UFO2P functions are reachable from `main_` only through pointer runs that runtime code references (for example tables registered by init code). The owner should decide whether those runs count as roots.
- **Files modified:** tests/test_mechanics_real.py. **Committed in:** `ed627c6`.

**2. [Rule 1 - Test bug] Two Task 2 tests were wrong; fixed in the GREEN commit `628123a`**
- The asm-list CRLF test wrote its file with `write_text`, which writes CRLF on Windows. It now writes bytes, so the file is LF on every host.
- The min_items case expected the row below a shared hub to be `closure`. Every row below a row that two items reach is also reached by both items, so it is a hub too. The test now checks a row that only one item reaches.

**3. [Rule 3 - Blocking] Plan commit ledger**
- The `.git/worktrees/...` ledger file was not written. The commit count is measured against the dispatch base instead: `git rev-list --count 2815ddb..45e16a3` = 6.

---

**Total deviations:** 3 auto-fixed (2 Rule 1, 1 Rule 3), plus the F14/F24/F32 rulings and the 07-05 note applied. **Impact:** the UFO2P table-step pin documents a real difference between 07-05's table rule and research, which needs a decision at 07-22. No scope creep.

## Issues Encountered

- **The tier digest cannot be exact in one corner.** The members file has no hub flag for a row that is a member only of another tier's item. In that case `tier_digest` counts the row as hub when it is an entry (via entry) and as closure otherwise. The rule is wrong for one row type: a later-tier entry that is not a hub and that tier N reaches only through a hub. Adding such an entry makes `mechanics check` ask for tier N to be re-signed. The failure is loud, never silent. The `min_items` criterion and hand edges can also reopen an earlier tier's digest (F36). This is documented in `tier_digest`'s docstring.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`. The host suite gave 2914 passed and 236 skipped. The only new skips are the 4 orig-absent `test_mechanics_real.py` skips in this worktree. `uv run ruff check .` is clean.

## Known Stubs

None. The data files (`config/mechanics.toml`, `config/mechanics-members.csv`, `config/asm-functions.csv`) are created by plans 07-12, 07-20 and 07-22, as the plan states.

## Threat Flags

None. No network, auth or new trust boundary: the verbs read committed config and the user's own `orig/` only. T-07-28, T-07-29 and T-07-30 are mitigated as planned (digests, strict loader caps, all-or-nothing sign-offs).

## User Setup Required

None.

## Next Phase Readiness

- 07-12 can write `config/asm-functions.csv` with `format_asm_csv` / `ASM_COMMENT` / `AsmRow`, and add a `mechanics asm` subcommand to `_add_mechanics_command`.
- 07-15 can read the members columns `exe,address,items,tiers,member_items,via,role`.
- 07-20 can use `asm_list_sha256` for the `[asm_list]` sign-off. 07-22 can use `mechanics graph`, `hubs`, `write` and `digest`. 07-26 can use `signed_tiers` and `read_members`. 07-39 and 07-41 can run `mechanics status --tier 1 --require-matched` and `mechanics check`.

Execution context nonce: 1ca40221f8453928

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
