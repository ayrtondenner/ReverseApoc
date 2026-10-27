---
phase: 07-mechanics-first-decompilation
plan: 24
subsystem: tooling
tags: [d-12, d-13, d-14, d-32, d-33, cflags, flags, approve, default, owner-only]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-17: the proposal queue (Proposal, read_queue/write_queue, cflags_sha256, variant_path, siblings, variant_sha256/reverted); 07-18: locks.ProcessLock and DRIVE_LOCK (drive.lock taken at the top of run_drive)"
provides:
  - "tools/reverseapoc/flags.py: approve, ApproveReport, doc_row, CFLAGS, MATCHING_DOC, KNOWN_MODEL, APPROVED_TRAILER; default, default_evidence, Evidence, Agreeing, DefaultReport, has_branch_or_loop, D33_MIN_FUNCTIONS, D33_MIN_BYTES, REGION_SIZE, TOOLCHAIN_DOC"
  - "reverseapoc flags approve ID... --by NAME [--repo]; flags default --rule SPEC --by NAME [--evidence] [--repo]"
  - "tests/test_hygiene.py: test_every_rule_documented (every non-* rule glob of config/cflags.txt has a matching.md rules-table row)"
affects: [07-29, 07-30, 07-33, 07-37]

actuals:
  tokens: 18800
  tasks: 3
  commits: 6
plan_head_before: 0fd68778633ad39c153ad7d3e7093c3e340240fa
plan_head_after: c41c7edbbbeb8a9cd8e67b576aac5517d68f5f26

tech-stack:
  added: []
  patterns:
    - "Owner verbs refuse everything before the first write, hold drive.lock for the whole call, snapshot every file they touch and restore it byte for byte on any failure"
    - "The container gate runs through an injected runner (driver.command_runner by default) and git through an injected git (driver.git_runner), both looked up at call time so CLI tests stand fakes in"
    - "Commits name explicit literal paths (git --literal-pathspecs add/commit -- paths), never -A"

key-files:
  created: []
  modified:
    - tools/reverseapoc/flags.py
    - tools/reverseapoc/cli.py
    - tests/test_flags.py
    - tests/test_hygiene.py

key-decisions:
  - "A batch's refusals are all checked first against the cflags.txt sha at batch start, so a later ID's re-gate stays valid after the earlier IDs' own appends (each rule names one exact unit; research R3). A proposal re-gated on any other cflags.txt is refused."
  - "A failed gate stops the batch: the failing proposal is restored and failed, and later IDs are reported 'not attempted' (exit 1)"
  - "gate records --attempts N, where N is the highest attempt number among the proposal's hitting attempts"
  - "Ruling F33: the co-author is driver.COAUTHOR only when every hitting attempt's attempts.jsonl record has model claude-opus-5-5. Any other model, a null model or a missing record is refused."
  - "approve also refuses when the paths it commits (cflags.txt, the unit, status.csv, the feed, matching.md) hold uncommitted changes. The queue is exempt: it carries the re-gate results into the landing commit."
  - "flags default: D-33 counts the functions matched under per-unit rules with the same compiler@version and flag set as SPEC. The bar needs 3 such functions with a branch or loop or 64+ bytes, coming from both EXEs and from at least 3 distinct (EXE, 0x10000 region) pairs."
  - "flags default also writes a matching.md row for every pin, so the new hygiene check holds after a flip"

patterns-established:
  - "Owner-only verbs: approve and default are never run by an executor or a matching session; tests run them on tmp git repos with fake gates"

requirements-completed: [DEC-03]

coverage:
  - id: D1
    description: "flags approve lands rule, C (or the reduced variant), docs row, status.csv, feed and queue in one commit with COAUTHOR, Matched-By and Flags-Approved-By; siblings shown"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_approve_lands_one_commit"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_approve_lands_the_reduced_variant"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_cli_approve"
        status: pass
    human_judgment: false
  - id: D2
    description: "A failed gate restores every file byte for byte, fails the proposal with the reason, commits nothing; a batch lands in the given order, one commit each"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_approve_restores_on_gate_failure"
        status: pass
      - kind: unit
        ref: "tests/test_flags.py#test_approve_order"
        status: pass
    human_judgment: false
  - id: D3
    description: "approve refusals before any write: not regated / exit 1, changed candidate, stale cflags sha, REVERSEAPOC_CLAIM, an ID twice, two on one unit, dirty unit, reduced-variant sha, unknown or other model, drive.lock held; CLI exit 2"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_approve_refusals (11 cases), test_approve_refuses_while_a_drive_holds_the_lock, test_approve_refuses_two_proposals_on_one_unit, test_cli_approve_refusal_exits_2"
        status: pass
    human_judgment: false
  - id: D4
    description: "Hygiene: every non-* rule in config/cflags.txt has a matching.md 'Compiler and flags per module' row"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_every_rule_documented, test_every_rule_documented_fails_when_missing"
        status: pass
    human_judgment: false
  - id: D5
    description: "flags default: D-33 bar, --evidence (writes nothing), pins, the three gate --all runs, matching.md and toolchain.md updates (ruling F16), restore on a failed gate, one commit with the default trailer"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_flags.py#test_has_branch_or_loop, test_default_bar_refusals, test_default_bar_counts_size_without_a_branch, test_default_evidence_mode, test_default_pins_and_gates, test_default_refuses_unfound_doc_text, test_default_failed_gate_writes_nothing, test_default_unpinned_dry_run_is_evidence_only, test_default_refusals, test_cli_default_evidence"
        status: pass
    human_judgment: false
  - id: D6
    description: "Real owner runs (container gate, real cflags.txt): the D-13 batch and any default ruling"
    verification: []
    human_judgment: true
    rationale: "Owner-only by D-12/D-14; plans 07-29 (approvals) and 07-33 (default) run them at blocking checkpoints on the main checkout. Only fakes run here."

duration: 23min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 24: Flag approvals and the `*` default (owner verbs) Summary

**`reverseapoc flags approve ID... --by NAME` lands each regated proposal, in the given order, as one gated match commit. The commit holds the rule line in config/cflags.txt, the C (the reduced variant when the re-gate reverted functions), a docs/matching.md row, status.csv, the feed and the queue, under the subject `feat(<exe>): match <function> in <unit> under approved flags F-nnnn (C89)` and the trailers `Matched-By:` and `Flags-Approved-By:`. A failed gate puts every file back byte for byte. `flags default --rule SPEC --by NAME [--evidence]` changes the `*` default only when D-33's bar is met (3 functions with a branch or loop or 64+ bytes, from both EXEs, in different 0x10000 regions). It pins every matched unit that has no rule, proves the change with `gate --all` before and after the write, and commits once. A new hygiene test requires a matching.md row for every per-unit rule.**

## Performance

- **Duration:** about 23 min
- **Started:** 2026-10-27T20:26:49Z
- **Completed:** 2026-10-27T20:49:30Z
- **Tasks:** 3, all TDD: a RED commit, then a GREEN commit
- **Files modified:** 4

## Accomplishments

**`approve(ids, by, *, repo, today, runner, git, queue, env)` (D-12, D-13, D-32).**
- Every refusal is checked before the first write. The refusals are listed under Task 2 below.
- drive.lock is held for the whole call.
- For each ID, in the given order:
  - append `<glob>  <rule>  # F-nnnn approved NAME DATE` to cflags.txt (write_atomic, validated with parse_cflags);
  - copy `flags.variant_path(p)` when `reverted` is non-empty, else the candidate, to `src/<exe>/<unit>.c`;
  - append `| src/<exe>/<unit>.c | <EXE.EXE> | <compiler@version> | <flags> | F-nnnn approved by NAME (re-gate log under build/flags/) | DATE |` under the rules table;
  - run `[*CONTAINER_CLI, "gate", "<exe>/<unit>", "--attempts", N, "--json"]`;
  - check that each of the proposal's functions now has a matched row;
  - mark the proposal `landed` with approved_by and approved_date;
  - commit exactly the six paths with `git --literal-pathspecs add/commit -- paths`.
- **The commit message** has the subject, the rule and its base, the re-gate result, the keeps, every sibling (D-32) and the evidence paths, then the trailers `driver.COAUTHOR`, `Matched-By: reverseapoc drive` and `Flags-Approved-By: NAME (F-nnnn, DATE)`.
- **The printed report** shows each proposal's rule and every sibling it binds before its landing line (the 07-17 note).
- **On a failed gate:** every file is restored byte for byte, the proposal is marked `failed` with the gate's output as the reason, the batch stops and the exit is 1.
- **On any other error:** the files are restored, the index is reset for what was staged, the proposal is marked failed, and the error is re-raised (exit 2).

**`default(rule, by, *, repo, today, runner, git, evidence_only, env, exe_loader)` (D-14, D-33).**
- **`default_evidence`** finds every status.csv-matched function whose unit's committed rule is a per-unit rule equal to SPEC. For each it gives the size from functions.csv and `has_branch_or_loop`: any jcc, jecxz or loop*, or any backward jump inside the row, decoded with reverseapoc.x86. It also names the first unmet part of the bar.
- **`--evidence`** prints the bar's inputs and the verdict, and writes nothing, whether or not the bar is met.
- **Otherwise the change is refused** when:
  - REVERSEAPOC_CLAIM is set;
  - drive.lock is held;
  - SPEC is the same as the committed `*` rule;
  - the bar is not met;
  - toolchain.md's canonical sentence is not there exactly once (ruling F16);
  - matching.md does not have exactly one `*` row per EXE;
  - the three doc and config paths are dirty.
- **The steps that follow:**
  1. Write `build/flags/default-<DATE>/cflags.txt`: the new `*` line, the existing per-unit rules, then one pin per matched unit without a rule, `src/<exe>/<unit>.c  <old spec>  <old flags>  # pinned by D-14 (...)`.
  2. Write `cflags-unpinned.txt` next to it.
  3. Run `gate --all --cflags <pinned> --json`; it must exit 0.
  4. Run `gate --all --cflags <unpinned> --json` as a dry run; its exit is evidence only.
  5. Write cflags.txt, then matching.md (the `*` rows say the new rule, plus one row per pin), then the toolchain.md sentence.
  6. Run `gate --all --json`. If it fails, every file is restored.
  7. Commit the three files once, with `Flags-Approved-By: NAME (default, DATE)`.
- **CLI:** `flags approve` exits 0 when every ID landed, 1 on a failed gate and 2 on a refusal. `flags default` exits 0 when it is done and 2 on a refusal. Both verbs are added through `_add_flags_owner_verbs`, which sits right after `_add_flags_command` (ruling F7).

**Hygiene (Task 2).** `_matching_rule_globs` reads the glob cell of the rows of the "Compiler and flags per module" table only. `_undocumented_rules` lists the non-`*` globs of a cflags text that have no row there. `test_every_rule_documented` passes on today's tree, which has no per-unit rule yet.

## Task Commits

1. **Task 1 (tracer, TDD): `flags approve` lands one gated commit.** RED `53d6b68`, GREEN `3bcb623`.
   - Tracer feedback gate: the run is interactive, in end-of-phase mode, with an automated-only verify.
   - I re-ran `uv run pytest -q tests/test_flags.py -k approve`: 5 passed. Then I expanded.
2. **Task 2 (TDD): approve refusals and the per-rule hygiene check.** RED `c1fe6ee`, GREEN `13e8775`.
3. **Task 3 (TDD): `flags default` with D-33's bar, pins, dry runs and the docs update.** RED `6dbc8a9`, GREEN `c41c7ed`.

## TDD evidence (RED)

Each RED run wrote pytest JUnit XML to `build/red/07-24-t{1,2,3}.xml` (gitignored). `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` each time.

- **t1, target `test_approve_lands_one_commit`: 5 of 5 failed.**
  - All five failures are assertion failures against the no-op stub `approve`, starting with `report.landed == ()`.
  - The stubs were API only (ApproveReport, approve, the verb wiring), the 07-17 precedent.
  - Semantic assessment: the target ran and failed on its planned assertion; no setup fault.
- **t2, target `test_every_rule_documented_fails_when_missing`: 1 failed, 1 passed.**
  - The target failed on `[] == [glob]` against a stub helper.
  - `test_every_rule_documented` passed vacuously: the tree has no per-unit rule.
  - The 24 approve refusal tests passed at RED (see Deviation 1).
- **t3, target `test_default_pins_and_gates`: 17 failed, 4 passed.**
  - The target failed on the expected three `gate --all` calls: the stub ran none.
  - The other 16 failures are assertions or `pytest.raises` against the stubs.
  - The 4 passes are the `has_branch_or_loop` cases that expect False, which the stub's constant False satisfies by design.
  - Before recording, I replaced a `next()` in `test_default_evidence_mode` with a list and an assertion, so it fails on an assertion and not with StopIteration.

## Verification (done gate)

- `uv run pytest -q tests/test_flags.py -k approve`: 5 passed (Task 1 verify).
- `uv run pytest -q tests/test_flags.py -k refus`: 24 passed. `uv run pytest -q tests/test_hygiene.py`: 77 passed, 3 skipped (Task 2 verify). The 3 skips are pre-existing: "only inside the container".
- `uv run pytest -q tests/test_flags.py`: 78 passed, 0 skipped.
- `uv run pytest -q` (host, worktree, at `c41c7ed`): **3456 passed, 247 skipped**.
  - That is the same skip count 07-18 reported.
  - This plan adds no skipping test and no new skip reason.
- `uv run ruff check .`: All checks passed.
- Acceptance:
  - flags.py has `def approve(`, `Flags-Approved-By:`, `D33_MIN_BYTES = 64` and `def default(`.
  - tests/test_hygiene.py has `test_every_rule_documented`.
  - `uv run reverseapoc flags default --help` lists `--evidence`.
- **Read-only run** on the worktree's committed data: `uv run reverseapoc flags default --rule "wcc386@10.6 -4r -oneatx -s -fpi" --by "Read Only" --evidence` printed "D-33 bar not met: only 0 function(s) matched under per-unit rules equal to it; D-33 needs 3" and exited 0. Nothing was written.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`. The new tests need no container tool: the gate, git repos and EXEs are all fakes or tmp repos.

## Files Created/Modified

- `tools/reverseapoc/flags.py`:
  - the approve section: `ApproveReport`, the refusals, `_Approver`, `approve`, `doc_row`;
  - the default section: `Agreeing`, `Evidence`, `DefaultReport`, `has_branch_or_loop`, `default_evidence`, `_Flip`, `default`;
  - the constants listed in `provides`.
- `tools/reverseapoc/cli.py`: `_flags_approve`, `_flags_default` and `_add_flags_owner_verbs`, placed right after `_add_flags_command` and called from inside it (ruling F7). No other line of cli.py moved.
- `tests/test_flags.py`: 34 new tests and parametrized cases, all on tmp git repos with an isolated git env, a fake container gate and synthetic EXE bytes.
- `tests/test_hygiene.py`: `_matching_rule_globs`, `_undocumented_rules`, `test_every_rule_documented` and `test_every_rule_documented_fails_when_missing`.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

**Orchestrator ruling F7: cli.py placement.**
- The new functions sit right after `_add_flags_command`, and `_add_flags_command` registers them (`for verb in (pr, ls, rg, *_add_flags_owner_verbs(verbs))`).
- `build_parser`, `_ERRORS` and the docstring are untouched; FlagsError was already in `_ERRORS`.
- Commits: `53d6b68`, `6dbc8a9`.

**Orchestrator ruling F16: only the canonical toolchain.md sentence is rewritten.**
- `default` rewrites only "The default rule in `config/cflags.txt` is `<rule>`" (`_TOOLCHAIN_SENTENCE`). It refuses unless that sentence is there exactly once and quotes the committed `*`. The historical quotes stay.
- Tests: `test_default_pins_and_gates` (the historical quote is kept) and `test_default_refuses_unfound_doc_text` (missing, or twice, on a tmp doc).
- Commits: `6dbc8a9`, `c41c7ed`.

**Orchestrator ruling F33: the co-author line.**
- The co-author line is `driver.COAUTHOR` when every hitting attempt (from the proposal's evidence paths) has model `claude-opus-5-5` in attempts.jsonl.
- Any other model, a null model or a missing record is refused.
- Tests: the refusal cases "unknown model", "other model" and "no attempt record".

**07-17 notes (rulings.md "## 07-24"):**
- When `reverted` is non-empty, approve lands `flags.variant_path(p)` and refuses if its LF sha256 differs from `variant_sha256`. Tests: `test_approve_lands_the_reduced_variant` and the "variant sha" refusal case.
- The siblings (`<name> <status> <percent>` | `<name> unattempted`) appear in the approve report before each landing, and in the commit body.

**Owner answer R4 (confirmed):** a flag-approved match carries `Matched-By: reverseapoc drive` plus `Flags-Approved-By:`, so stats (07-37) can class it `unattended` and report the subset separately. Nothing else is needed here.

**07-18 note:** drive.lock refuses approve (and default) while a drive holds it. Tests: `test_approve_refuses_while_a_drive_holds_the_lock` and `test_default_refusals`.

**1. [TDD] Task 2's approve refusals were built in Task 1's GREEN.**
- **What happened:** the refusal tests (24, including the parametrized cases) passed at Task 2's RED commit, so for them that commit is not a genuine RED. This is the F28 class of finding.
- **How each refusal was proven anyway:** I removed each refusal check from flags.py, one at a time, and ran `-k refus`. All nine mutations were caught by 1 to 3 failing tests each:
  - status/exit, cflags sha, one unit, source sha, claim, drive lock, dirty paths, model, ids once.
- After each run the file was restored to its committed bytes. The script is `mutate_0724.py` in the scratchpad.
- The genuine RED of Task 2 is the hygiene check.

**2. [Rule 1 - Bug] capstone 5 does not put `loop`/`loope`/`loopne` in its jump group.**
- **Effect:** `x86.Insn.is_jump` and `is_conditional` are False for them, though x86.py's own comment lists loop.
- **Fix:** `has_branch_or_loop` names those mnemonics (`_LOOPS`).
- **Test:** `test_has_branch_or_loop[\xe2\xfe\xc3-True]`.
- The shared decoder is not changed (see Deferred Issues).
- Commit `c41c7ed`.

**3. [Rule 2 - Missing critical] approve and default refuse when the paths they commit hold uncommitted changes.**
- **Why:** a landing or flip commits those paths whole, so it would otherwise sweep someone's edit into an approval commit.
- The queue is exempt for approve, because the regate results ride into the landing commit.
- **Test:** the "dirty unit" refusal case.

**4. [Rule 2 - Missing critical] `flags default` writes a matching.md row per pin.**
- **Why:** the hygiene check this plan adds requires a row for every non-`*` rule, so a flip without pin rows would break the suite.
- **Test:** `test_default_pins_and_gates`.

**5. [Plan clarification] driver.commit_paths no longer exists (07-18 removed it).**
- approve and default commit through their own `_git_ok`, with `git --literal-pathspecs add -- paths` then `commit -q -F <file> -- paths`.
- The message file is `build/flags/<id>/commit-msg.txt`, or `build/flags/default-<date>/commit-msg.txt` for a flip.

**6. [Plan clarification] Batch semantics.**
- All refusals are checked against the sha of cflags.txt at batch start, so the plan's `test_approve_order` (two IDs, two commits) holds while a proposal re-gated on an older file is still refused.
- A failed gate stops the batch: the rest are "not attempted" and the exit is 1.

**7. [Plan clarification] There is no interactive confirmation prompt.**
- The owner reads `flags list` (siblings included) before approving.
- approve prints each proposal's rule and siblings before its landing line, and the commit body repeats them.

---

**Total deviations:** the rulings F7, F16 and F33 applied, plus the 07-17 and 07-18 notes and R4. Beyond those: 1 TDD note (refusals proven by mutation), 1 Rule 1 fix, 2 Rule 2 additions and 3 plan clarifications.
**Impact on plan:** every must-have truth holds as written. config/cflags.txt, the docs and src/ in the repo are unchanged: only tmp repos in tests were written.

## Deferred Issues

- **`reverseapoc.x86`:** `Insn.is_jump`'s comment says "any jump: jmp, jcc, loop, jecxz", but capstone 5.0.9 leaves `loop`/`loope`/`loopne` out of CS_GRP_JUMP, so those decode with `is_jump=False`.
  - It is out of scope here, because other modules (discover, asm, callgraph, score) rely on that decoder.
  - It is worth a look by whoever owns x86.py: a loop instruction's target is not a `branch_target` either.

## Issues Encountered

- The worktree harness refused compound shell commands that touch git, as well as heredoc appends. I used the Edit tool and plain one-step commands instead.
- I could not write the GSD plan ledger file under `.git/worktrees/`, because it is outside the worktree. The base `0fd6877` is recorded in `plan_head_before`.
- The scratchpad's `red_record.py` was rewritten during the run by another session (a parallel executor, by its content). I used `red_record_0724.py` for the later records.

## Known Stubs

None. Every RED stub was replaced in its GREEN commit.

## Threat Flags

None beyond the plan's threat model:
- T-07-70: the refusals and the byte-for-byte restore.
- T-07-71: the D-33 bar, the pins and `gate --all` before and after.
- T-07-72: the trailers, the docs row and the landed status.

The new surfaces are owner-run verbs that write config/cflags.txt, src/, the two docs and build/flags/. All of them are named in the plan.

## User Setup Required

None.

## Next Phase Readiness

- **07-29 (the D-13 batch, owner at a checkpoint):**
  1. `uv run reverseapoc flags list`.
  2. `uv run reverseapoc flags approve F-.... --by NAME` on the host, with no drive running; the gate runs through `docker compose run --rm -T build`.
  3. Each landing is one commit with the `Flags-Approved-By:` trailer.
- **07-30** swaps `KNOWN_MODEL`/`driver.COAUTHOR` for `coauthor(model)` (ruling F33).
- **07-33 (the optional default ruling):**
  1. `uv run reverseapoc flags default --rule "<spec>" --by NAME --evidence` first; it reads orig/ for the sizes and branches only when agreeing functions exist.
  2. Then the same command without `--evidence`.
  3. In that commit, review `_DRIFTED_RULES` in tests/test_hygiene.py (research Q4).
- **07-37 (stats):** finds flag-approved matches by the `Flags-Approved-By:` trailer next to `Matched-By:` (R4).

Execution context nonce: a87993ade6db394c

## Self-Check: PASSED

- FOUND: tools/reverseapoc/flags.py, tools/reverseapoc/cli.py, tests/test_flags.py, tests/test_hygiene.py (all modified).
- FOUND commits: 53d6b68, 3bcb623, c1fe6ee, 13e8775, 6dbc8a9, c41c7ed. `git rev-list --count 0fd6877..HEAD` was 6 before the SUMMARY commit.
- No STATE.md or ROADMAP.md change.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
