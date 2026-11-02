---
phase: 07-mechanics-first-decompilation
plan: "48c"
subsystem: tooling
tags: [flags, d-12, d-32, batch, oneatx, queue, approve, agt-11]
bundle_nonce: c9a7f0592875

requires:
  - phase: 07-48
    provides: "the trailing-filler rule, so a filler row's batch record is exact and its regate can pass"
  - phase: 07-48b
    provides: "the leading-table gap rule; tacp 0x0001E860 routed to Task 2b"
provides:
  - "`flags propose --from-batch FILE --cell FLAGS --author WHO` (flags.propose_batch): one D-12 proposal per (exe, unit) from a batch cell's exact records"
  - "`reverseapoc batch` records carry `source` and `source_sha256` (batch.with_source)"
  - "the queue's optional `author` field (AUTHORS closed), omitted when empty, so the 44 committed entries round-trip byte for byte"
  - "`flags approve` of a batch proposal: trailer `Matched-By: <author>`, no attempt co-authors, gate --attempts 0"
affects: ["Task 2b (the 18 -oneatx rows plus tacp 0x0001E860)", "flags approve", "stats (AGT-11 classes)"]

actuals:
  tokens: 16236  # chars/4 over `git diff d1a8e19 fccbc67` (64945 chars)
  tasks: 3
  commits: 5  # MEASURED: git rev-list --count d1a8e19..HEAD at SUMMARY write; the SUMMARY commit follows
plan_head_before: d1a8e19e30b80703fd172362266329558f01c060
plan_head_after: fccbc67abfa9490ae785b87ffa76e62ff7a14b53

tech-stack:
  added: []
  patterns:
    - "optional queue keys: FIELDS stays the required keys; OPTIONAL_FIELDS are written after them only when they differ from their default"
    - "batch-sourced proposal: every refusal (FlagsError) before any write; candidates and queue written only after the whole queue validates"

key-files:
  created: []
  modified:
    - tools/reverseapoc/flags.py
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/batch.py
    - tests/test_flags.py
    - tests/test_batch.py
    - tests/test_cli_batch.py
    - docs/workflow.md
    - docs/toolchain.md

key-decisions:
  - "07-48c: a batch proposal's inserted row C is LF-normalized (CRLF read as LF) and otherwise verbatim; the source sha256 check is on the LF form, as lf_sha256 is everywhere"
  - "07-48c: a skipped (exe, unit) group is skipped whole: the committed rule, a matched function, a duplicate (exe, unit, rule) held in any status but rejected/superseded, an open or approved proposal, a missing marker, or a row file defining another row's placeholder"
  - "07-48c: approve reads attempts.jsonl lazily, only when a sweep proposal is named; a batch proposal never consults it"

patterns-established:
  - "Batch landing trailer: `Matched-By: <author>` from MATCHED_BY_KEY (derived from driver.MATCHED_BY), so stats classes it human-written, never unattended"

requirements-completed: [DEC-03]

coverage:
  - id: D1
    description: "flags propose --from-batch turns a cell's exact batch records into one proposal per unit, with the unit candidate, the author and the results file as evidence; config/cflags.txt untouched"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_propose_batch_adds_one_proposal_per_unit"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_propose_batch_is_idempotent"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_cli_propose_from_batch"
        status: pass
    human_judgment: false
  - id: D2
    description: "the design's negatives (not exact, flags differ, outside build/, unknown author, duplicate) and the plan's extra ones are refused or skipped with nothing written"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_propose_batch_skips_a_record_that_is_not_exact (and the 9 other negative tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "batch records name their source C and its LF sha256"
    verification:
      - kind: unit
        ref: "tests/test_batch.py#test_with_source_names_the_path_and_lf_sha256"
        status: pass
      - kind: unit
        ref: "tests/test_cli_batch.py#test_batch_records_name_their_source"
        status: pass
    human_judgment: false
  - id: D4
    description: "the committed queue's 44 entries parse and round-trip byte for byte under the new optional author key"
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_committed_queue_round_trips_byte_identical"
        status: pass
      - kind: other
        ref: "cmp config/cflags-proposals.toml build/gate/07-evidence/48c-queue-before.toml"
        status: pass
    human_judgment: false
  - id: D5
    description: "a batch proposal's approval commit carries Matched-By: <author>, no driver Matched-By, no attempt co-authors, gate --attempts 0; sweep approvals unchanged"
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_approve_a_batch_proposal_writes_matched_by_author"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_approve_a_batch_proposal_has_no_driver_trailer"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_approve_a_batch_proposal_gates_with_attempts_0"
        status: pass
    human_judgment: false
  - id: D6
    description: "regate byte-identical; both suites, ruff and the container gate --all green with both SHA-1s OK"
    verification:
      - kind: other
        ref: "cmp build/gate/07-evidence/48c-regate-before.txt 48c-regate-after.txt"
        status: pass
      - kind: integration
        ref: "docker compose run --rm build bash -lc \"uv sync --locked && uv run reverseapoc gate --all\" (48c-gate-all-after.log)"
        status: pass
    human_judgment: false
  - id: D7
    description: "code review of the plan's diff"
    verification: []
    human_judgment: true
    rationale: "/code-review was not run by the executor (orchestrator ruling); deferred to the orchestrator"

duration: 53min
completed: 2026-11-02
status: complete
---

# Phase 7 Plan 48c: Batch-sourced flag proposals Summary

**`flags propose --from-batch <results.jsonl> --cell <flags> --author <who>` turns a `reverseapoc batch` cell's exact records into one D-12 proposal per unit (the whole unit with each row's C at its INCLUDE_ASM marker), batch records now name their C and its LF sha256, and `flags approve` lands such a proposal with `Matched-By: <author>`, no attempt co-authors and gate attempts 0.**

Bundle nonce: c9a7f0592875

## Performance

- **Duration:** 53 min
- **Started:** 2026-11-02T04:41:56Z
- **Completed:** 2026-11-02T05:35:02Z
- **Tasks:** 3 (Task 1 tracer, Task 2, Task 3)
- **Files modified:** 8

## Accomplishments

- **The verb, as built.** `flags propose` takes a required mutually exclusive `--from-attempts [RUN ...]` | `--from-batch FILE`. `--cell FLAGS` and `--author WHO` (argparse choices: `reverseapoc lift`, `claude subagent (spike 011)`) go with `--from-batch` only; either misuse is exit 2. `flags.propose_batch(results, cell, author, *, repo, queue=None)`:
  - refuses (FlagsError, nothing written): an author outside AUTHORS; a results file outside `build/` of the repo; a cell with no record; an unknown exe, a bad address or a row functions.csv does not hold; a record whose `flags` are not the proposed rule's; a record with no `source`/`source_sha256` ("re-run reverseapoc batch"); a source not under `build/`, unreadable, or whose LF sha256 differs ("changed since the batch judged it");
  - skips, with a reason: a record that is not exact; per (exe, unit) group, the cell equal to the unit's committed rule, a function matched in status.csv, a queue entry with the same (exe, unit, rule) not rejected/superseded ("duplicate of F-NNNN"), an open or approved proposal for the unit ("is open (proposed)"), a row with no marker, or a row file defining another of the unit's placeholders;
  - otherwise one proposal per (exe, unit): `source = "batch"`, `author`, evidence `(results path,)`, rule = the unit's committed spec plus the cell's flags (batch.cell_rule), base = the committed rule, functions in start order, keeps, siblings (D-32), alternatives empty. The candidate is the committed `src/<exe>/<unit>.c`, or `units.scaffold_unit` over units.csv when there is none, with each row's C replacing `INCLUDE_ASM(<name>);` (no declaration rewrite), written to `build/flags/<id>/<unit>.c` with its LF sha256. Candidates and the queue are written only after the whole queue validates. A re-run is idempotent.
- **Record keys.** `reverseapoc batch` records gain `source` (the input C, repo-relative POSIX inside the repo, absolute otherwise) and `source_sha256` (LF sha256, "" when not ASCII), refused records too (`batch.with_source`, applied in cli `_file_records`; the file is read once). `batch.cell_record` is unchanged.
- **Queue schema.** `Proposal.author: str = ""` is the last field; `OPTIONAL_FIELDS = {"author": ""}`; `FIELDS` stays the 24 required keys. `_proposal` accepts the required keys plus any optional one; `format_queue` writes an optional key only when it differs from its default; `_field_problem` requires `author in ("", *AUTHORS)` and `(source == "batch") == (author != "")`.
- **Queue compatibility evidence.** `read_queue(config/cflags-proposals.toml)` gives 44 entries, every author "", and `format_queue` reproduces the file byte for byte (test_committed_queue_round_trips_byte_identical, and the acceptance one-liner). `cmp config/cflags-proposals.toml build/gate/07-evidence/48c-queue-before.toml` passes.
- **Approve.** For `source == "batch"`, `_approvable` builds `_Landing(p, _landing_source(...), (), BY_HAND_ATTEMPTS)` without `_hitting_attempts`/`_coauthors` (attempts.jsonl is read only for sweep proposals); every other refusal (regated exit 0, today's cflags sha, one per unit, the candidate's sha, drive lock, claim env, owner name, lint, container gate) holds for both. `_approve_message` writes `f"{MATCHED_BY_KEY} {p.author}"` then Flags-Approved-By; `MATCHED_BY_KEY` is derived from `driver.MATCHED_BY` (`grep -c '"Matched-By' flags.py` is 0). `Proposal.line()` shows `  author <author>`; `_confirmation` names it. stats then classes such a landing human-written.
- **regate** is byte-identical: the `# ---- regate` .. `CFLAGS = ` section (320 lines) cmp-equal to d1a8e19's.

## Task Commits

1. **Task 1 (tracer): flags propose --from-batch** - `bd43eed` (test, RED), `ff5e82c` (feat, GREEN)
2. **Task 2: the batch landing trailer** - `78a4156` (test, RED), `27bc9f5` (feat, GREEN)
3. **Task 3: docs** - `fccbc67` (docs)

**Plan metadata:** the SUMMARY commit `docs(07-48c): complete the batch-sourced flag proposals plan`, then STATE/ROADMAP.

## TDD Gate Compliance

- **Task 1 RED** (`48c-red.xml`, `48c-red-record.json`, `RED_EVIDENCE_OK`): target `test_propose_batch_adds_one_proposal_per_unit` failed with `AttributeError: module 'reverseapoc.flags' has no attribute 'propose_batch'` (16 failed, 167 passed, the files collected). Semantic assessment: the target ran and failed on the absent API, no collection or fixture fault. Each negative's HEAD failure is in 48c-notes.txt: propose_batch missing (8 tests), `Proposal(author=...)` a TypeError (2), the CLI usage message lacking `--from-batch` (1), `SystemExit: 2` for the unknown option (1), `with_source` missing (1), a record without `source` (KeyError, 1). `test_committed_queue_round_trips_byte_identical` passed on HEAD by design (a guard).
- **Task 1 GREEN**: the three files 183 passed; tracer verify re-run green (end-of-phase mode, automated-only verify), then expansion.
- **Task 2 RED** (`48c-red2.xml`, `48c-red2-record.json`, `RED_EVIDENCE_OK`): target `test_approve_a_batch_proposal_writes_matched_by_author` failed inside `flags.approve`: `FlagsError: F-0001: evidence build/batch/48c.jsonl is not a driver attempt's checks/NNNN.json` (4 failed, 105 passed). The planned behavior was absent, not a setup fault.
- **Task 2 GREEN**: flags, batch, CLI batch and stats tests 236 passed; the existing sweep approve tests unchanged and green.
- RED and GREEN commits present for both TDD tasks; no REFACTOR commit (none needed).

## Suites and gate

| Run | Result |
|---|---|
| host `uv run pytest -q -rs` (48c-host.log, head fccbc67) | 4412 passed, 41 skipped, exit=0; every skip an R-A reason (Ghidra, run in the container, only inside the container, POSIX-only, Windows file names, non-UTF-8 names, symlink privileges) |
| host `uv run ruff check .` (48c-ruff.log) | exit=0 |
| `docker compose build` (48c-container-build.log) | exit=0 |
| container suite + ruff (48c-container.log, head fccbc67) | 4451 passed, 2 skipped (`Windows-only: msvcrt lock path`), ruff green, exit=0 |
| container `gate --all` before (48c-gate-all-before.log, d1a8e19) | exit=0; `OK UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 landed 57`; `OK TACP.EXE sha1 48ef00969d8880a0a152de1b652853fa7ac27393 landed 38` |
| container `gate --all` after (48c-gate-all-after.log, fccbc67) | exit=0; the same two lines: UFO2P sha1 e7488bf3...c56 landed 57, TACP sha1 48ef0096...393 landed 38 |

**48c-gate-all.diff**: three hunks, all run noise. Lines 1-2: the compose run container name (`reverseapoc-build-run-aff0ad9b2a10` before, `-104a60b319c4` after) on its Creating and Created lines. Line 4: uv's `Checked 8 packages in 4ms` before, `3ms` after. No function line differs; newly passing functions: none (none expected). config/, src/, the feed and configure.py are unchanged since d1a8e19; `check-orig` OK.

## Review

Code review deferred to the orchestrator (orchestrator ruling: the executor runs no `/code-review`). Command: `/code-review` at the default level over `git diff d1a8e19...HEAD` (tools/reverseapoc/flags.py, cli.py, batch.py and the three test files).

## Files Created/Modified

- `tools/reverseapoc/flags.py` - BATCH, AUTHORS, OPTIONAL_FIELDS, Proposal.author, optional-key reader/writer, propose_batch and its helpers (_batch_results, _record_row, _cell_rule_text, _source_text, _batch_row, _batch_groups, _group_skip, _unit_text, _batch_candidate, _batch_proposal), MATCHED_BY_KEY, BY_HAND_ATTEMPTS, the batch landing trailer
- `tools/reverseapoc/cli.py` - `flags propose --from-attempts | --from-batch` with `--cell`/`--author`; the batch verb's records through batch.with_source
- `tools/reverseapoc/batch.py` - with_source; docstring
- `tests/test_flags.py` - 15 batch-proposal tests and 4 approve/list tests
- `tests/test_batch.py`, `tests/test_cli_batch.py` - with_source and the record keys
- `docs/workflow.md` (Flag rules), `docs/toolchain.md` (Batch judge)

## Decisions Made

- The inserted row C is LF-normalized, otherwise verbatim (lf_sha256 already reads CRLF as LF, so the checked sha is the same).
- A skipped group is skipped whole (one proposal per unit and run), as the plan orders.
- approve reads attempts.jsonl lazily, only for a sweep proposal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixture: two open proposals on one unit**
- **Found during:** Task 1 GREEN
- **Issue:** test_queue_round_trips_a_batch_proposal put the batch proposal on the sweep proposal's unit, which `_check_queue` correctly refuses.
- **Fix:** the batch proposal moved to u_00010000. Committed in `ff5e82c`.

**2. [Rule 1 - Bug] Test helper: git's trailing newline**
- **Found during:** Task 2 GREEN
- **Issue:** `git log --format=%B` ends in a blank line, so the trailer-block slice was empty.
- **Fix:** the helper strips trailing newlines before splitting. Committed in `27bc9f5`.

No fix-forward commit after the done gate.

**Total deviations:** 2 auto-fixed (test bugs). **Impact:** none on the tool's behavior.

## Issues Encountered

None.

## Known Stubs

None.

## Task 2b hand-off (for the orchestrator; nothing here was run by the executor)

All from the main checkout's root after this plan is on main. One author per batch run, so converter rows and agent rows are separate runs. The queue's last id is F-0044, so the first new ids are F-0045 onward; use the ids `flags propose` prints.

1. **Converter rows** (spike 011 inferred arm, author `reverseapoc lift`). Judge the whole arm under both cells, keep the rows exact under `-oneatx` and not under the committed rule (expect 13; report another count), re-judge those alone, then propose:
   ```
   uv run reverseapoc batch build/spike-011/all/inferred --cell "-4r -oneatx -s -fpi" --out build/48c-2b/inferred-all.jsonl
   uv run python -c "import json, shutil, pathlib as P; R=[json.loads(l) for l in open('build/48c-2b/inferred-all.jsonl')]; x={(r['exe'], r['address']) for r in R if r['cell']=='-4r -oneatx -s -fpi' and r['exact']}; c={(r['exe'], r['address']) for r in R if r['cell']=='committed' and r['exact']}; k=sorted(x-c); [(P.Path('build/48c-2b/converter')/e).mkdir(parents=True, exist_ok=True) or shutil.copy(f'build/spike-011/all/inferred/{e}/f_{int(a, 16):08x}.c', f'build/48c-2b/converter/{e}/') for e, a in k]; print(len(k), k)"
   uv run reverseapoc batch build/48c-2b/converter --cell "-4r -oneatx -s -fpi" --out build/48c-2b/converter.jsonl
   uv run reverseapoc flags propose --from-batch build/48c-2b/converter.jsonl --cell "-4r -oneatx -s -fpi" --author "reverseapoc lift"
   ```
2. **Agent rows** (author `claude subagent (spike 011)`): ufo2p 0x00034FE0, 0x000483A0, 0x0005FBD0; tacp 0x00095800, 0x00098300, 0x0001E860 (07-48b routed it here; its file is build/spike-011/agents/b064/f_0001e860.c). `batch` needs the `<dir>/<exe>/f_<addr>.c` layout, so copy them first:
   ```
   mkdir -p build/48c-2b/agents/ufo2p build/48c-2b/agents/tacp
   cp build/spike-011/agents/b064/f_00034fe0.c build/spike-011/agents/b256/f_000483a0.c build/spike-011/agents/b256/f_0005fbd0.c build/48c-2b/agents/ufo2p/
   cp build/spike-011/agents/b064/f_00095800.c build/spike-011/agents/b064/f_00098300.c build/spike-011/agents/b064/f_0001e860.c build/48c-2b/agents/tacp/
   uv run reverseapoc batch build/48c-2b/agents --cell "-4r -oneatx -s -fpi" --out build/48c-2b/agents.jsonl
   uv run reverseapoc flags propose --from-batch build/48c-2b/agents.jsonl --cell "-4r -oneatx -s -fpi" --author "claude subagent (spike 011)"
   ```
3. **Re-gate** the new ids in the container: `docker compose run --rm build bash -lc "uv sync --locked && uv run reverseapoc flags regate F-0045 F-0046 ..."`. A proposal whose regate fails (a broken matched sibling, or a declaration clash between a row's C and its unit, which fails the compile and records `failed` with the reason) is reported, not pushed.
4. **Commit** only config/cflags-proposals.toml, as b006bf3 did (`chore(flags): D-12 proposals ..., re-gated`). Never `flags approve`; the owner approves, and each row lands through approve's gated commit with `Matched-By: <author>`.

Watch for: a unit that holds both a converter row and an agent row gets its proposal from the first run only; the second run reports it `is open` (the queue allows one open proposal per unit). A row whose file defines another row's placeholder is skipped with that name.

## Next Phase Readiness

Task 2b can start once this branch is on main. The stats classes are unchanged: a batch landing classes human-written until the owner rules a converter class.

## Self-Check: PASSED

- All 8 modified files exist; commits bd43eed, ff5e82c, 78a4156, 27bc9f5, fccbc67 are ancestors of HEAD.
- Task 1 and Task 2 acceptance criteria and automated verifies re-run green; the regate section cmp-equal; the committed queue cmp-equal to its baseline.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-11-02*
