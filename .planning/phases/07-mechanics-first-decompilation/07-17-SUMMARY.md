---
phase: 07-mechanics-first-decompilation
plan: 17
subsystem: tooling
tags: [d-12, d-13, d-16, d-28, d-32, cflags, flags, proposals, regate]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-03: rule by logical path (a build/flags/<id>/src copy compiles each unit under its own rule from REPO_ROOT); 07-04: both cflags files owner-only in the hooks; 07-14: sweep JSON stage2 cells"
provides:
  - "tools/reverseapoc/flags.py: FlagsError, QUEUE, QUEUE_VERSION, STATUSES, OPEN_STATUSES, SOURCES, VARIANTS, NOT_RUN, Proposal, FIELDS, read_queue, write_queue, format_queue, pilot_hits, Hit, find_hits, propose, ProposeReport, cflags_sha256, temp_cflags, regate, RegateReport, Variant, _reduced, _merge, _cells_100"
  - "reverseapoc flags propose --from-attempts [RUN ...] [--repo] [--json]; flags regate ID... [--orig] [--build] [--watcom-dir] [--json]; flags list [--json]"
  - "config/cflags-proposals.toml format: version = 1, [[proposal]] tables in FIELDS order (first written by 07-29 on the main checkout)"
affects: [07-24, 07-29, 07-37, 07-41]

actuals:
  tokens: 20255
  tasks: 3
  commits: 7
plan_head_before: aaa81213cfcc46c1f9028bfa077e5ce67b41d9c3
plan_head_after: 8133e34121c444f0cdb45c326f243801e74e4830

tech-stack:
  added: []
  patterns:
    - "A committed TOML queue written by a fixed-key-order emitter (json.dumps strings, printable ASCII only, write_atomic) and read back with tomllib with exact key sets"
    - "A whole-unit re-proof on build/flags/<id>/src under build/flags/<id>/cflags.txt (committed text plus one exact-path rule), never the shared src/ or config/cflags.txt"
    - "Default collaborators looked up at call time (_check_unit, _cross_check) so CLI tests can monkeypatch check.check_unit"

key-files:
  created:
    - tools/reverseapoc/flags.py
    - tests/test_flags.py
  modified:
    - tools/reverseapoc/cli.py

key-decisions:
  - "Ruling F15: pilot_hits reads attempts.jsonl alone (sweep_hit and no MATCHED record); propose skips status-matched functions separately"
  - "Rules are intersected by spec (compiler@version + flags), not by cell number, so 30-cell, 60-cell (__CHK) and stage-2 numbering cannot collide; ranking is (number of flags, cell number)"
  - "Another hit of a function the proposal already holds only adds evidence (the candidate stays that function's first hitting C); a new function narrows the rules and has its hitting definition spliced into the candidate"
  - "Any merge voids the re-gate fields (status back to proposed); a proposal failed by an empty intersection stays failed"
  - "regate_variant `empty` means no re-gate has run (paired with regate_exit -1)"
  - "Idempotency key is the hit's checks/NNNN.json evidence path"
  - "An approved proposal blocks new hits for its unit (skipped with a note) until it lands"

patterns-established:
  - "flags verbs exit 0 done, 1 a re-gate failed, 2 a tool or usage error"

requirements-completed: [DEC-03, AGT-11]

coverage:
  - id: D1
    description: "Queue model: Proposal with the D-12 fields; write_queue fixed key order, ASCII-only, round-trips through read_queue; malformed queue refused"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_queue_round_trip"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_queue_refuses_non_ascii"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_read_queue_refuses_an_unknown_status"
        status: pass
    human_judgment: false
  - id: D2
    description: "pilot_hits re-derives the six D-16 pilot hits from the committed attempts.jsonl (func_0008A100 out)"
    requirement: AGT-11
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_pilot_hits_from_committed_log"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_pilot_hits_drops_a_later_match_and_ignores_status"
        status: pass
    human_judgment: false
  - id: D3
    description: "flags propose: the hitting checks/NNNN.c (never best/) becomes build/flags/<id>/<unit>.c with its LF sha256; idempotent; status-matched functions skipped; CLI propose and list"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_propose_uses_the_hitting_snapshot"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_propose_is_idempotent"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_propose_skips_a_status_matched_function"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_cli_propose_and_list"
        status: pass
    human_judgment: false
  - id: D4
    description: "Per-unit merge by intersection, DEC-03 tie-break (fewer flags, then lower cell), empty intersection failed, stage-2 source, siblings and keeps (D-32)"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_merge_by_intersection"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_tie_break"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_empty_intersection_fails"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_stage2_hit_source"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_siblings_listed"
        status: pass
    human_judgment: false
  - id: D5
    description: "flags regate on a copy: writes nothing shared, refuses the committed cflags, kept-function drop and cross-check drop fail, reduced variant passes, records the committed cflags sha"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_regate_writes_nothing_shared"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_regate_refuses_the_committed_cflags"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_regate_kept_function_drop"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_regate_cross_check_drop"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_regate_reduced_variant"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_regate_records_cflags_sha"
        status: pass
    human_judgment: false
  - id: D6
    description: "Real container re-gate of the six pilot proposals (objdiff-cli, Watcom under wibo)"
    verification: []
    human_judgment: true
    rationale: "Needs the container and the owner's game files; plan 07-29 runs it on the main checkout. Only fakes of check_unit run here."

duration: 28min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 17: Flag proposals, part 1 (propose, regate, list) Summary

**`reverseapoc flags` turns driver sweep hits into owner-reviewable per-unit cflags proposals in config/cflags-proposals.toml, copying the C that actually hit (checks/NNNN.c, never best/) to build/flags/<id>/, merging hits per unit by intersecting their 100% rules (fewest flags, then lowest cell), and `flags regate` re-proves a proposal over the whole unit and both EXEs on a src/ copy under the committed cflags plus one exact-path rule, falling back to the D-28 reduced variant, without ever writing src/ or config/cflags.txt.**

## Performance

- **Duration:** about 28 min
- **Started:** 2026-10-27T18:56:16Z
- **Completed:** 2026-10-27T19:24Z
- **Tasks:** 3 (all TDD: RED commit, then GREEN commit; one REFACTOR commit)
- **Files modified:** 3

## Accomplishments

- **Queue:** `Proposal` carries exactly the fields of the truth, in this order: id, exe, unit, glob, rule, base, functions, keeps, siblings, alternatives, source, candidate, candidate_sha256, evidence, status, regate_exit, regate_variant, regate_cflags_sha256, regate_log, approved_by, approved_date, reason.
  - `write_queue` emits the header, `version = 1` and one `[[proposal]]` per proposal, its keys in FIELDS order. Strings go through json.dumps after a printable-ASCII check, lists are inline arrays and ints are bare. It writes through write_atomic.
  - `read_queue` (tomllib) checks the exact key sets and every value: the id pattern, `glob == src/<exe>/<unit>.c`, the spec shapes, `candidate == build/flags/<id>/<unit>.c`, evidence under build/, the enums and the sha256 hex. It also checks that ids are unique and that each unit has at most one open proposal.
- **pilot_hits (D-16, ruling F15):** reads attempts.jsonl alone, validating each record with `driver.validate_record`. On the committed log it returns exactly the six pilot functions. func_0008A100 is excluded because it has a later MATCHED record.
- **propose:**
  - Reads checks.jsonl sweep lines and their `checks/NNNN.json` cells, stage 1 and stage 2.
  - Copies `checks/NNNN.c` to `build/flags/<id>/<unit>.c` and records its LF sha256 and the evidence path.
  - Sets base from the committed cflags rule, keeps from the unit's matched rows and siblings from its other partial rows (D-32).
  - Skips status-matched functions. A re-run adds nothing.
- **Merging and ranking:** rules are ranked by (number of flags, cell number).
  - A hit for a new function of an open unit proposal intersects the rule sets and splices that function's hitting definition into the candidate. An empty intersection is `failed`, with a reason naming the functions.
  - Every merge voids the re-gate fields.
- **regate:**
  - Refuses an id that is unknown, duplicated, not open, without a rule, or whose candidate changed.
  - Writes `build/flags/<id>/cflags.txt` (`temp_cflags`: the committed text plus `<glob>  <rule>  # F-nnnn (proposed)`, checked with parse_cflags, refused when the path resolves to the committed file).
  - Copies src/ to `build/flags/<id>/src/` with the candidate in place, runs `check_unit` and then gate's `cross_check`.
  - When only co-defined neighbours miss (every proposal function and keep defined and passing), it retries with them as `INCLUDE_ASM(...)` (`_reduced`).
  - Records regate_exit, regate_variant, regate_cflags_sha256 (lf sha of the committed cflags.txt), regate_log (`build/flags/<id>/regate.json`), status and reason, writing the queue after each proposal.
  - A check that raises is exit 2.
- **CLI:** `flags propose --from-attempts [RUN ...]`, `flags regate ID...` (`--orig`, `--build`, `--watcom-dir`), `flags list [--json]`, each with `--repo` (default REPO_ROOT). FlagsError is in `_ERRORS`. A tool error exits 2.
- **Real-data dry run:** I ran it on a scratchpad copy of config/ and the pilot run directory, not the checkout.
  - `flags propose` produced F-0001..F-0006 for exactly the six D-13 functions, with the rules research Q2 predicts: `-oneatx` for func_0006FBD0, func_00026FD0 and func_0009C3A0, `-ot` for the other three.
  - It listed the siblings func_0004DFF0 33.19, func_00061F50 46.45 and func_00061FA0 67.50.
  - It skipped func_0008A100 as matched in status.csv.

## Task Commits

1. **Task 1 (tracer, TDD): pilot_hits, the queue, propose, the verb.** RED `ddfdd12`, GREEN `5e0db1a`.
2. **Task 2 (TDD): merging, tie-break, failed proposals, siblings.** RED `f9d4597`, GREEN `e63f367`.
3. **Task 3 (TDD): flags regate.** RED `809b271`, GREEN `8943b01`, REFACTOR `8133e34`.

## TDD evidence

Each RED commit carried API stubs only (the 07-10/07-12 precedent), so the new tests fail on assertions and not at import.

- **Task 1 RED:** 13 of 14 tests failed. Target `test_propose_uses_the_hitting_snapshot` failed on `assert report.added == ("F-0001",)` because the stub propose added nothing.
  - JUnit `build/red/07-17-t1.xml` (gitignored). Classifier: `RED_EVIDENCE_OK` / `target_test_failed`.
  - Semantic assessment: the target ran and failed on its planned assertion; no setup fault.
  - `test_read_queue_missing_is_empty` passed by design: the stub returns [], which is also the specified behaviour.
- **Task 2 RED:** 7 failed. Target `test_tie_break` failed with `'wcc386@10.6 -4r -ot -s -fpi' == 'wcc386@10.5 -4r -s -fpi'`: Task 1 ranked by cell number only.
  - Classifier: `RED_EVIDENCE_OK` / `target_test_failed`.
  - `test_stage2_hit_source` failed with a ValueError (no stage-1 cell, so nothing to unpack). That is the missing stage-2 reading, a behavioural failure.
- **Task 3 RED:** 12 failed. Target `test_regate_kept_function_drop` failed on `('proposed', -1, 'empty') == ('failed', 1, 'as-written')`.
  - Classifier: `RED_EVIDENCE_OK` / `target_test_failed`.
- **Tracer feedback gate:** interactive, end-of-phase, automated-only verify. I re-ran `uv run pytest -q tests/test_flags.py` after Task 1 GREEN: 14 passed. Then I expanded to Task 2.

## Verification (done gate)

- `uv run pytest -q tests/test_flags.py`: 33 passed, 0 skipped.
- `uv run pytest -q tests/test_flags.py -k "merge or tie or intersection or stage2 or siblings"`: 7 passed.
- `uv run pytest -q` (worktree, at HEAD `8133e34`): **3140 passed, 246 skipped**. This plan adds no skip; all 246 are pre-existing platform or owner-file skips (no orig/ or third_party/ in the worktree).
- `uv run ruff check .`: All checks passed.
- Acceptance:
  - `QUEUE = Path("config/cflags-proposals.toml")`, `def propose(`, `def regate(`, `def _reduced(` and `def pilot_hits(` are present.
  - `uv run reverseapoc flags --help` lists propose, list and regate.
  - `uv run reverseapoc flags regate --help` exits 0.
  - `test_tie_break` asserts the fewer-flags rule (`wcc386@10.5 -4r -s -fpi`, 3 flags) wins over a lower-numbered 4-flag cell.
  - key_links: `check_unit(` and `cross_check(` are called in flags.py.

## Container steps deferred to the orchestrator

- **Container step deferred to the orchestrator:** `docker compose run --rm test`, the full container suite. tests/test_flags.py needs no container tool; every check is faked.
- The real re-gates of the six pilot proposals (`uv run reverseapoc flags propose --from-attempts 20261026-005209`, then `docker compose run --rm build uv run reverseapoc flags regate F-0001 ... F-0006`) are plan 07-29's, on the main checkout.

## Files Created/Modified

- `tools/reverseapoc/flags.py` (new): the queue model, reader and writer, pilot_hits, find_hits, propose/_merge/_cells_100, temp_cflags/_reduced/regate.
- `tools/reverseapoc/cli.py`: `_add_flags_command` with propose, regate and list, plus FlagsError in `_ERRORS`. It is one self-contained block before `build_parser`, and 07-24 adds its verbs inside or right after it (ruling F7).
- `tests/test_flags.py` (new): 33 tests. Everything is synthetic except the committed attempts.jsonl.

## Decisions Made

See key-decisions in the frontmatter. Three need a word more:

- **Intersection by spec, not by cell number.** Cell numbers mean different flags in a 60-cell `__CHK` sweep, and stage-2 numbers continue from stage 1. The plan's example ({4,5,14} and {5,15} give the cell-5 rule) holds under both readings.
- **What "fewer flags" counts.** It counts the whitespace-separated flag fields of the rule. The plan's two named rules (`-4r -ot -s -fpi`, `-4r -oneatx -s -fpi`) have four each, so between them the lower cell decides. The test also has a 3-flag cell (10.5's `-4r -s -fpi`, cell 11) that beats a lower-numbered 4-flag cell, which proves the first key.
- **The neighbour retry.** The reduced variant runs only when every proposal function and every keep is defined and passing and only other defined functions fail. When a kept function misses, the result is exit 1 with no retry (DEC-03 adjacency).

## Deviations from Plan

**1. Orchestrator ruling F15: pilot_hits uses attempts.jsonl only.**
- `pilot_hits(log)` drops functions with a MATCHED attempt record and never reads status.csv.
- `propose` skips status-matched functions separately: `test_propose_skips_a_status_matched_function`, and in the real dry run func_0008A100.
- The committed-data test pins the six from the log alone, so it keeps passing after 07-29's approvals write matched rows.
- Commits: `ddfdd12`, `5e0db1a`.

**2. [Plan clarification] `landed_commit` is not a field.** The truth's field list ends at `reason` and says the landing commit is found from its `Flags-Approved-By:` trailer. The research draft's `landed_commit` key was therefore left out.

**3. [Plan clarification] regate takes `orig_dir`, `build_dir` and `watcom_dir` keywords.** These are the plan's "usual check roots for the container". The defaults are `<repo>/orig` and `build/flags/<id>/build`, so check's `check-custom` objects stay per proposal. `--repo` was added to all three verbs so the CLI tests run on a tmp checkout.

**4. [Rule 1 - test fixture] Two Task 3 fixture errors fixed in the GREEN commit (`8943b01`).**
- The fixture's functions.csv evidence value `made-up` is not one of the allowed tags. It is now `call`.
- `write_status` did not sort rows by start.
- Both only surfaced once the real regate read those files. At RED the stub never read them, and the target's failure was the planned one.

**5. [Addition] Behaviour the plan implies but does not spell out, each pinned by a test.**
- An approved proposal blocks new hits for its unit.
- Regate refuses an id that is unknown, not open, without a rule or whose candidate changed (`test_regate_refusals`).
- Check errors are exit 2 (`test_regate_check_error_is_exit_2`).
- A merge into a regated proposal resets its re-gate (`test_merge_into_a_regated_proposal_resets_its_regate`).

**Total deviations:** 1 orchestrator ruling applied (F15), 2 plan clarifications, 1 test-fixture fix, 1 group of pinned additions.
**Impact on plan:** every must-have truth holds as written. There is no change to config/cflags.txt, src/, the hooks or any committed data.

## Issues Encountered

- Heredoc edits through the shell twice turned a `\b` regex escape into a backspace character. It was caught by the merge tests and fixed. Both files were then checked for control characters (none).

## Known Stubs

None. The RED stubs were replaced in each GREEN commit.

## Threat Flags

None. The only new surfaces are the queue (T-07-50: ASCII, fixed fields, no game bytes) and `build/flags/<id>/` (gitignored), both in the plan's threat model.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- 07-24 (approve and the `*` default) can rely on these pieces:
  - `read_queue` / `write_queue` / `cflags_sha256`, plus `regate_cflags_sha256` and `candidate_sha256` for its refusals;
  - OPEN_STATUSES and APPROVED/LANDED;
  - `_add_flags_command` for its verbs.
- 07-29 runs `flags propose --from-attempts 20261026-005209` and the container `flags regate F-0001..F-0006` on the main checkout.
- Flagged assumption (research A13) is unchanged: the reduced variant may lose the hit if Watcom used the same-module definition. Only the container re-gate shows it.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/flags.py, tests/test_flags.py, tools/reverseapoc/cli.py (modified)
- FOUND commits: ddfdd12, 5e0db1a, f9d4597, e63f367, 809b271, 8943b01, 8133e34 (7 = `git rev-list --count aaa8121..HEAD`)

## Fix round 1

The orchestrator's task review raised two Important findings. Both rulings were applied test-first: RED `b11bbb2`, GREEN `e4a83e4`.

**1. Siblings left out the never-attempted rows of the unit (D-32).**
- **Before:** `_Context.siblings` listed only status.csv partial rows. u_00060c50 has 16 game rows but listed 2 siblings. u_0006fbd0 listed none, not even its D-28 neighbour func_0006FC00.
- **Ruling:** D-32 outranks the plan's narrower list.
- **Now:** `siblings` lists every game and thunk row of the unit other than the proposal's functions, sorted by start.
  - Rows come from functions.csv, named as symbols.csv names them now.
  - Each is `<name> <status> <percent>` from status.csv (`matched`/`partial`), or `<name> unattempted`.
  - Data-in-code and runtime rows are excluded. Without a functions.csv, the unit's status.csv rows stand in.
  - `flags list` prints one `sibling` line each.
- **Scratchpad dry run on the real pilot data:** F-0005 (u_00060c50) now lists 15 siblings. F-0001 (u_0006fbd0) lists func_0006FC00 and func_0006FC40, both unattempted. u_0009c1a0 lists 10, its 3 data-in-code rows left out.
- **Tests:** `test_siblings_listed` (rewritten: matched, partial, an unattempted thunk, a data-in-code row left out) and `test_siblings_include_the_unattempted_neighbour`.

**2. A regate that passed on the reduced variant left no pinned record.**
- **Before:** neither the reduced text, its sha nor the reverted names were recorded, and `reason` was cleared on a pass.
- **Now:** a pass on the reduced variant writes that C to `build/flags/<id>/<unit>.reduced.c` (`flags.variant_path(p)`, `REDUCED_SUFFIX`).
- **Two new queue fields, appended after `reason`:**
  - `variant_sha256`: the LF sha256 of that C.
  - `reverted`: the function names returned to INCLUDE_ASM.
- **Empty when nothing passed reduced:** both are empty when the full candidate passed, when no variant passed, or after any merge, and a stale variant file is removed.
- **Validation:** `read_queue`/`write_queue` validate them; one without the other is refused.
- **Log:** regate.json records both.
- **Owner-facing:** `flags list` prints `WARNING the re-gate passed only with <names> returned to INCLUDE_ASM: approving lands <variant path>, not the candidate`.
- **Documentation:** the queue format, every field with the two new ones, is documented in the flags.py module docstring. 07-24's approve lands `variant_path` when `reverted` is non-empty.
- **Tests:**
  - `test_regate_reduced_variant`, extended: the file, its sha, `reverted == (F50,)`, the warning.
  - `test_regate_writes_nothing_shared`, extended: both fields empty and no variant file after an as-written pass.
  - `test_regate_failing_reduced_variant_pins_nothing` (new).
  - `test_queue_refuses_inconsistent_fields`, 4 cases.
  - `test_queue_round_trip`, extended: a reduced-pass row, and the field order ends `reason, variant_sha256, reverted`.
  - `test_merge_into_a_regated_proposal_resets_its_regate`, extended: the merge clears both fields.

**RED evidence:**
- 7 failed. Target `test_siblings_listed` failed on its assertion: the old output `func_00061F50 46.45, ...` against the four-row expected list. Classifier: `RED_EVIDENCE_OK` / `target_test_failed` (`build/red/07-17-fr1.xml`).
- `test_regate_reduced_variant` failed with FileNotFoundError: the reduced file was never written.
- At RED, three of the four `test_queue_refuses_inconsistent_fields` cases already passed, but for an unrelated reason: the old sibling regex refused the fixture's new-format siblings. After GREEN they fail only on the field each one targets.
- The RED commit added `variant_sha256`, `reverted` and `variant_path` as API stubs only.

**Verification:**
- `uv run pytest -q tests/test_flags.py`: 39 passed.
- `uv run pytest -q`: **3146 passed, 246 skipped**, no new skip.
- `uv run ruff check .`: all checks passed.

**New queue field names:** `variant_sha256`, `reverted` (after `reason`). The `siblings` entry format is now `<name> <status> <percent>` | `<name> unattempted`.

Execution context nonce: 3bb854a1fc929c42

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
