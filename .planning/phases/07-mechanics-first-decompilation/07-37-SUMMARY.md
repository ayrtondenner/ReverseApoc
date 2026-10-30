---
phase: 07-mechanics-first-decompilation
plan: 37
subsystem: stats
tags: [stats, dec-07, agt-11, git-trailers, attempts-jsonl, r4, d-09, d-18]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-07: validate_record with v1 and v2 schemas, MATCHED_BY; 07-10: config/mechanics-members.csv and read_members; 07-23: v2 attempt records (session, model_requested, hook_blocks, gate.regressions), matched_starts"
provides:
  - "tools/reverseapoc/stats.py: StatsError, CLASSES, SIZE_BUCKETS, read_attempts, MatchEvent, History, is_shallow, history, match_history, classify, read_sizes, read_tiers, size_bucket, money, tenth, build_report, Report, collect"
  - "`reverseapoc stats [--json] [--log PATH] [--repo PATH] [--config DIR] [--min-unattended N]`: exit 0 done, 1 below --min-unattended (AGT-11), 2 for a bad log or a git failure"
  - "AGT-11's count from git: 7 unattended (4 of them flag-approved) and 2 human-written on the base history"
affects: [07-41, G14]

actuals:
  tokens: 12100
  tasks: 3
  commits: 5
plan_head_before: 5f5bbb2f564847cc9863bfa887e76cfa40aa7c6a
plan_head_after: 889fe57de2886311b11984e9aee5bf508d3cef0b

tech-stack:
  added: []
  patterns:
    - "A match is classed only from committed trailers. `git log --reverse --no-merges` over both status.csv paths, with `%(trailers:only,unfold)`. A start is newly matched when it is in the commit's table but not in its parent's (`ls-tree` blob ids, `cat-file blob`, `driver.matched_starts`)"
    - "Every git call is `git -c safe.directory=* ...` through driver.git_runner (GIT_OPTIONAL_LOCKS=0). A failing git call is a StatsError, never an empty history"
    - "Sums are exact Decimals of each number's written form. Display values are quantized ROUND_HALF_EVEN and emitted as strings in the JSON, so 1.10 stays 1.10"

key-files:
  created:
    - tools/reverseapoc/stats.py
    - tests/test_stats.py
  modified:
    - tools/reverseapoc/cli.py

key-decisions:
  - "A function counts once in the class totals, by its latest event, and only while the end of the walked history still has it matched. One matched, reverted and matched again is listed under re_matched. One no longer matched is listed under reverted and is not counted"
  - "flags_approved counts the counted functions whose latest event is unattended and carries Flags-Approved-By. Match-Hints wins over the driver trailer (human-hints) even when Flags-Approved-By is also there"
  - "In a shallow clone the boundary commit (no parent listed) is the baseline: it updates the matched set but gives no events. A root commit of a full clone is compared with empty tables. The report carries `shallow`"
  - "Per-match figures and the size buckets count matching sessions only (v1 lines, and v2 lines with session `matching`). The matched set is the functions git counts, plus those with a MATCHED record that git does not show as reverted. So a flag-approved function counts as matched for its attempts"
  - "Readability sessions stay in totals, hook blocks and the per-kind split. Hook blocks and regressions are summed over every v2 attempt record"
  - "A missing --log file is an error (exit 2), not an empty report, so a mistyped path cannot print zeros. An empty file gives the all-zero report"
  - "A missing functions.csv puts the function in an `unknown` size bucket. A missing members file gives `by_tier: null` ('per tier: no mechanics-members.csv')"

patterns-established:
  - "v2-only figures are {value, v1_records}. value is null when there are no v2 attempt records, and the text then prints 'n/a for v1'"

requirements-completed: [DEC-07, AGT-11]

coverage:
  - id: D1
    description: "Every match classed from git trailers: unattended (Matched-By: reverseapoc drive), human-hints (+ Match-Hints), human-written (no driver trailer), flag-approved subset apart (R4); --min-unattended gates with exit 1"
    requirement: AGT-11
    verification:
      - kind: integration
        ref: "tests/test_stats.py#test_classes_from_trailers, test_match_history_events, test_partial_rows_are_no_match, test_matched_by_must_name_the_driver, test_text_names_the_classes, test_min_unattended, test_min_unattended_with_json"
        status: pass
    human_judgment: false
  - id: D2
    description: "The attempt log read through driver.validate_record (v1 and v2 together); a non-JSON line, a non-object or a schema failure exits 2 naming the line; an empty log and no history give an all-zero report"
    requirement: DEC-07
    verification:
      - kind: unit
        ref: "tests/test_stats.py#test_malformed_lines, test_read_attempts_names_the_line, test_a_missing_log_is_refused, test_v1_and_v2_lines_read_together, test_empty, test_help_lists_the_flags"
        status: pass
    human_judgment: false
  - id: D3
    description: "Metrics: size buckets and their edges, per-match attempts/turns/tokens/cost/seconds, regressions and hook blocks (n/a for v1), per-model, per-kind and per-tier splits, round-half-even precision, re-match counted once, two functions in one commit"
    requirement: DEC-07
    verification:
      - kind: unit
        ref: "tests/test_stats.py#test_size_bucket_edges, test_size_buckets, test_a_function_without_a_size_is_unknown, test_per_match_figures, test_per_match_figures_without_a_match_are_none, test_a_git_match_counts_for_the_attempted_function, test_v1_fields_na, test_v2_fields_summed, test_model_and_kind_splits, test_readability_sessions_are_no_matching_attempts, test_tier_split, test_no_members_file_no_tier_split, test_precision, test_precision_rate_and_text, test_full_precision_sums, test_rematch_counted_once, test_a_reverted_match_is_not_counted, test_one_commit_matching_two_functions"
        status: pass
    human_judgment: false
  - id: D4
    description: "Committed data: the log reads, stats --json exits 0, the full-clone history includes the 3 pilot unattended and 2 Phase 5 human-written matches; shallow clones; determinism"
    requirement: DEC-07
    verification:
      - kind: integration
        ref: "tests/test_stats.py#test_committed_log_reads, test_stats_runs_on_the_committed_data, test_committed_history_classes, test_a_shallow_boundary_is_a_baseline, test_a_shallow_clone_sees_the_matches_after_its_boundary, test_a_failing_git_is_an_error_not_shallow, test_deterministic"
        status: pass
    human_judgment: false
  - id: D5
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3769 passed, 248 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge (the container exercises the safe.directory path of ruling F13)"

duration: 19min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 37: `reverseapoc stats` Summary

**`reverseapoc stats` classes every match from committed git trailers and reports DEC-07's research numbers from progress/attempts.jsonl, so AGT-11 is a number CI can compute.**
- The classes are unattended, human-hints and human-written. The flag-approved subset is shown apart.
- The numbers are match rate by size, per-match cost, regressions, hook blocks, and splits per model, per session kind and per tier.
- On the base history the count is 7 unattended (4 of them flag-approved) and 2 human-written.

## Performance

- **Duration:** about 19 min of work (20:13Z to 20:33Z), plus about 8 min for the full host suite
- **Started:** 2026-10-30T20:13:55Z
- **Completed:** 2026-10-30T20:33Z
- **Tasks:** 3 (two RED/GREEN pairs, then one commit of characterization tests)
- **Files:** 3 (2 created, 1 modified)

## Accomplishments

- **Task 1 (tracer): classes from git and the verb.**
  - `read_attempts` refuses a bad line with exit 2, naming the line number.
  - `match_history` walks the status.csv commits oldest first and classes each new `matched` start by its commit's trailers.
  - `Report.unattended` is AGT-11's count. `--min-unattended N` exits 1 below N.
- **Task 2: the metrics.**
  - `SIZE_BUCKETS`, plus an `unknown` bucket for functions functions.csv does not size.
  - Rate per bucket. Attempts, turns, the four token classes, cost and seconds per matched function.
  - Regressions the gate stopped and hook blocks. Both are "n/a for v1" when there is no v2 line.
  - Per-model (`model_requested`) and per-session splits. A per-tier split by the function's lowest tier in mechanics-members.csv.
  - Exact Decimal sums, displayed with ROUND_HALF_EVEN.
- **Task 3: committed data, shallow clones, determinism.**
  - The real log reads, and `stats --json` exits 0 on it.
  - The full-clone history includes c83cf4e, d288ad6 and 955931f as unattended, and fc7d1cd's two Phase 5 matches as human-written.
  - Two `--json` runs give identical bytes with sorted keys.

Output of `uv run reverseapoc stats` on the base history (main 5f5bbb2 plus this plan):
- Matches: unattended 7 (flag-approved 4), human-hints 0, human-written 2.
- Attempt log: 42 v1 records, 40 sessions, cost $42.93.
- Match rate: [0, 64) 5 of 15 (33.3%).
- Per matched function: 8.0 attempts, $8.59.
- Per tier: tier 1 has 6 unattended. Untiered: 1 unattended and 2 human-written.

## Task Commits

1. **Task 1 (tracer): classes from git trailers, AGT-11, refusals, the verb.** RED `e3778f6`, GREEN `2fbbe98`.
   - Tracer feedback gate: the run is interactive, `end-of-phase`, and the verify is automated only. I re-ran `uv run pytest -q tests/test_stats.py` (15 passed) and `uv run reverseapoc stats --help` (lists `--min-unattended` and `--json`), then expanded.
   - Tracer verified end-to-end.
2. **Task 2: the metrics.** RED `f0bd6d8`, GREEN `bc7dbef`.
3. **Task 3: committed history and determinism.** `889fe57`: characterization tests (ruling F28), proven by mutation as described below.

## TDD Gate Compliance

Each RED run wrote pytest JUnit XML (`build/red/t1.xml`, `build/red/t2.xml`, gitignored) and a record. `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` both times.
- **t1, target `test_match_history_events`: 15 of 15 failed.**
  - The tests reach the module as `reverseapoc.stats`, an attribute set once cli imports it.
  - The failures were `AttributeError: module 'reverseapoc' has no attribute 'stats'`, and `SystemExit: 2` from argparse for the unknown `stats` verb. Both were raised in the test body after collection.
  - This is the missing feature itself, the same kind of evidence 07-21 and 07-23 accepted. Nothing failed in collection, import or a fixture.
- **t2, target `test_size_buckets`: 19 failed, 20 passed.**
  - The target failed on `KeyError: 'by_size'` in its body: the report had no size buckets yet.
  - The 20 that passed are Task 1's 15 tests and five new Task 2 tests that pin behaviour Task 1 already built: `test_precision`, `test_full_precision_sums`, `test_rematch_counted_once`, `test_a_reverted_match_is_not_counted` and `test_one_commit_matching_two_functions`. Task 1's Report already had Decimal totals and the latest-event rule.
- **Task 3 (ruling F28):** its tests are characterization tests and had no genuine RED. Instead, I ran them against a mutated stats.py with three mutations:
  - `sort_keys=False`;
  - no shallow baseline;
  - every commit without the driver trailer classed unattended.
  Four tests failed: `test_deterministic`, both shallow tests and `test_committed_history_classes`. `test_a_failing_git_is_an_error_not_shallow` was not targeted by any mutation. I then restored the file with `git checkout -- tools/reverseapoc/stats.py`.
- Every `feat(07-37)` commit follows its `test(07-37)` commit. There is no REFACTOR commit.

## Files Created/Modified

- `tools/reverseapoc/stats.py` (new): the attempt reader, the git match history, size and tier inputs, and the report (JSON and text).
- `tools/reverseapoc/cli.py`, kept to the verb's own parts:
  - `stats` added to the `from . import` line;
  - `_cmd_stats` and `_add_stats_command`, after `_add_flags_owner_verbs`;
  - `_add_stats_command(sub)`, registered after `_add_flags_command(sub)`;
  - `stats.StatsError` in `_ERRORS`.
- `tests/test_stats.py` (new): 46 tests. Every git test uses a synthetic repository, except `test_committed_history_classes`, `test_committed_log_reads` and `test_stats_runs_on_the_committed_data`.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

**Orchestrator ruling F13: git in the container and shallow CI.**
- Every git call in `match_history` (log, ls-tree, cat-file, rev-parse) passes `-c safe.directory=*`, and so does the shallow probe `is_shallow`.
- A failing probe raises StatsError and is never treated as "shallow" (`test_a_failing_git_is_an_error_not_shallow`).
- `test_deterministic` and every trailer test run on synthetic repos. Two tests read the real history:
  - `test_committed_history_classes` skips with the reason "shallow clone: the committed match history is cut" (R-A's 07-37 `shallow` reason).
  - `test_stats_runs_on_the_committed_data` runs `stats --json` with the default `--repo` and asserts only exit 0 and a non-empty log, so it holds on a shallow clone (the boundary is a baseline) and needs no skip. (Corrected in fix round 1.)
- I added two synthetic shallow-clone tests (`--depth 1` and `--depth 2`). They pin that a shallow boundary is a baseline: its rows are not classed by the boundary commit's own trailers.
- Commits `2fbbe98`, `889fe57`.

**Orchestrator ruling F28: Task 3 has no genuine RED.** Task 3's tests are characterization tests, committed once as `test(07-37): committed history and determinism`. Each was proven to fail against a mutated stats.py (see TDD Gate Compliance).

**Owner answer R4 (rulings "Owner answers"), applied as researched.**
- A `Flags-Approved-By:` match is classed `unattended`.
- `flags_approved` reports the subset apart, in JSON and in text ("unattended: 7 (flag-approved 4)").

**1. [Plan clarification] The verb's error is in `_ERRORS` and `_cmd_stats` returns 2.**
- `main` turns `_ERRORS` into exit 1, but the truth asks exit 2 for a malformed line. `_cmd_stats` therefore catches StatsError itself and returns `EXIT_TOOL` (2).
- StatsError is also in `_ERRORS`, as the plan says.

**2. [Plan clarification] Functions no longer matched are not counted.** The plan's truths cover re-matches (counted once, by the latest event). A function whose match was undone and not redone is listed under `reverted` and is left out of the class totals, so AGT-11 never counts a match that no longer holds (`test_a_reverted_match_is_not_counted`).

**3. [Test fix inside a GREEN commit] `test_precision_rate_and_text`.** The test meant a total cost of 0.125, but its two other records kept the default 0.25 each. They now cost 0, and the behaviour it pins (33.3% and $0.12) is unchanged. Commit `bc7dbef`.

**4. [TDD sequencing] Five Task 2 tests passed at RED.** These are test_precision, test_full_precision_sums and the three match-adjacency tests, because Task 1's Report already held the Decimal totals and the latest-event rule. They are characterization tests within Task 2. The target test and 18 others failed for the missing metrics.

---

**Total deviations:** 2 orchestrator rulings (F13, F28) and the owner's R4, all applied; 2 plan clarifications; 1 test fix inside a GREEN commit; 1 TDD sequencing note.
**Impact on plan:** every must-have truth holds. The gate G14 (`stats --min-unattended 10`) and its flag exist as specified. I changed no gate.

## Issues Encountered

- The harness refused compound shell commands (heredocs, `cd ... &&`, variables in sed). I used the Edit/Write tools, plus scratchpad files named `*_0737.py` (another agent rewrote a shared scratchpad `red_record.py` mid-run).
- A git call costs more on Windows than elsewhere: tests/test_stats.py takes 10-30 s on this host.

## Concerns

- **Siblings matched by a flags approval count as unattended.**
  - 864fb46 also turned `func_0006FC00` matched (a sibling marked "unattempted"), and 6adc5c8 did the same for `func_00026FF0`. Both carry `Matched-By: reverseapoc drive` and `Flags-Approved-By:`.
  - Under the classing rule (a newly matched start takes its commit's class), they are unattended and flag-approved. So 2 of today's 7 unattended functions never had a session of their own.
  - The flag-approved subset (4) makes this visible. The owner may want 07-41's docs to state it, or a fourth subset ("matched as a sibling, no session").
- **The real count today is 7 unattended**, so `stats --min-unattended 10` (G14) exits 1 on this history.
- **Readers of the JSON:** costs and percentages are strings ("0.12", "33.3"), and counts are integers. 07-41 should read them that way.
- **Container step deferred to the orchestrator (R-B):** `docker compose build && docker compose run --rm test`. That run exercises `-c safe.directory=*` on the bind-mounted repository.

## Known Stubs

None.

## Threat Flags

None.
- T-07-109: a match is unattended only with the exact `Matched-By: reverseapoc drive` trailer (`test_matched_by_must_name_the_driver`), and the flag-approved subset is shown.
- T-07-110: every log line goes through `driver.validate_record`, and a bad line exits 2 naming its number.
- `stats` only reads git history, the log and two config files. It writes nothing and prints addresses, names, counts and commit hashes only.

## Verification

- `uv run pytest -q tests/test_stats.py`: 15 passed after Task 1, 39 after Task 2, 46 after Task 3.
- `uv run reverseapoc stats --help`: lists `--min-unattended` and `--json`.
- `uv run reverseapoc stats --json > /dev/null`: exit 0.
- `uv run reverseapoc stats`: prints `unattended: 7 (flag-approved 4)`, which meets "at least 3".
- tools/reverseapoc/stats.py contains `SIZE_BUCKETS`, `ROUND_HALF_EVEN`, `def match_history(`, `validate_record(` and `read_members`. tests/test_stats.py contains `human-written`.
- `uv run pytest -q` (host, worktree): **3769 passed, 248 skipped**. The skip count is unchanged from the base. On this full clone the new `shallow` skip reason does not fire.
- `uv run ruff check .`: All checks passed.
- I ran no `claude -p`, no `drive` and no docker (D-11, R-B).

## User Setup Required

None.

## Next Phase Readiness

- 07-41 and the G14 gate can run `reverseapoc stats --min-unattended 10`. Today it reports 7.
- The JSON keys are sorted and stable: classes, flags_approved, events, re_matched, reverted, shallow, attempts, totals, by_size, per_match, regressions_stopped, hook_blocks, by_model, by_session, by_tier.

Execution context nonce: 9cd63a164b737c3f

## Self-Check: PASSED

- FOUND: tools/reverseapoc/stats.py, tests/test_stats.py, tools/reverseapoc/cli.py (modified)
- FOUND commits on this branch: e3778f6, 2fbbe98, f0bd6d8, bc7dbef, 889fe57. `git rev-list --count 5f5bbb2..HEAD` = 5 before this SUMMARY commit.
- No STATE.md, ROADMAP.md or REQUIREMENTS.md change (the orchestrator owns them after the merge).

## Fix round 1

**Finding (task review, Important 1):**
- `history().matched`, the "matched at the end" set, came from the last commit the walk reached, not from HEAD.
- `git log --reverse --no-merges` orders by date and drops merge commits. So when status.csv changes on two branches that are then merged, the last walked commit lacks the other branch's rows.
- That undercounts AGT-11, and the missing match is wrongly listed as reverted. A date-later side commit could also overcount a match that was reverted on main.
- The real history is linear today, so the count of 7 was right. Phase 7's merged worktrees could change that.

**Fix (`tools/reverseapoc/stats.py`):**
- `history` reads the end state from HEAD's own status tables (`_blobs(repo, "HEAD")`, then `_matched`).
- The walk adds `--topo-order`, so "oldest first" never puts a child before its parent.
- Events are unchanged in kind: each non-merge commit is still compared with its own parent and classed by its own trailers. A merge brings no match of its own.
- The shallow-boundary skip now comes first in the loop, since the walk no longer tracks tables.

**Tests (`tests/test_stats.py`):**
- `test_a_merged_history_ends_with_heads_tables`: base {0x100}. A side branch adds 0x300 (drive). Main adds 0x108 by hand, dated after the side commit. Then a `--no-ff` merge.
  - HEAD holds 3 matched rows, and `history().matched` now equals them. At RED it was 2.
- `test_a_merged_history_classes_every_match`: 0x100 and 0x300 are unattended, 0x108 human-written, and nothing is reverted.
- `test_a_revert_on_one_branch_is_not_counted`: main reverts 0x100, and a side commit dated later still holds the row.
  - After the merge, HEAD lacks 0x100, so it is listed as reverted and not counted.

**RED evidence:**
- All 3 tests failed on their assertions (`build/red/f1.xml`). The target `test_a_merged_history_ends_with_heads_tables` was missing ('ufo2p', 0x300).
- The classifier returned `RED_EVIDENCE_OK` / `target_test_failed`.

**Minor fixed:** the F13 bullet under Deviations now names both tests that read the real history (`test_committed_history_classes` and `test_stats_runs_on_the_committed_data`). The other minors stay as the orchestrator ruled.

**Commits:**
- `4aca414` test(07-37): add failing tests for a merged status.csv history
- `d4f8c6c` fix(07-37): stats reads the end-state matched set from HEAD and walks in topo order
- this SUMMARY commit

**Counts:**
- `uv run pytest -q tests/test_stats.py`: 49 passed.
- `uv run pytest -q` (host, worktree): 3772 passed, 248 skipped. That is the 3 new tests on top of 3769, with no new skip.
- `uv run ruff check .`: All checks passed.
- `uv run reverseapoc stats` still reports unattended 7 (flag-approved 4) and human-written 2.
- Container step still deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
