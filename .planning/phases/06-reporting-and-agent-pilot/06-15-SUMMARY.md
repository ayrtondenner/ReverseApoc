---
phase: 06-reporting-and-agent-pilot
plan: 15
subsystem: agent-tooling
tags: [attempt-wrapper, context-pack, skill, watcom, D-44, D-07, D-13, D-18, D-19]
status: complete

requires:
  - phase: 06-11
    provides: status.py (read_status, status_path, MATCHED/PARTIAL)
  - phase: 06-12
    provides: hooks.ATTEMPT_PREFIX, ATTEMPT_FORMS, ATTEMPT_NAME_SLOT, attempt_form_matches, CLAIM_ENV
  - phase: 06-13
    provides: contextpack.gather, build_pack, write_pack, CallIndex, Pack.to_json
provides:
  - "tools/reverseapoc/attempt.py: Claim (from REVERSEAPOC_CLAIM/FUNC/ATTEMPT_DIR/ATTEMPT_NOTES only), claimed_row, CHECK_BUDGET = 25, container_name, container_check_argv, run_check (check.lock, reserved checks/NNNN.c slots, docker rm -f after a timeout), CheckLogLine, exe_inputs (check.load_exe), resolve_row, make_pack, cmd_check/cmd_asm/cmd_context"
  - "reverseapoc attempt check [--sweep] | asm [NAME] | context, argv after `attempt` equal to hooks.ATTEMPT_FORMS"
  - "reverseapoc context EXE FUNC [--out DIR] [--json]"
  - "contextpack.Notes: earlier notes cut as D-14's fourth step (fix round 1 M11)"
  - "hooks matching layer: no run_in_background Bash, no #pragma of any kind (fix round 1 M14)"
  - ".claude/skills/watcom-decomp/SKILL.md (147 lines after fix round 1) and tests/test_skill.py"
  - "D-18 pragma policy in .claude/rules/src.md and docs/coding-style.md (every #pragma since fix round 1)"
affects: [06-17 session goal prompt, 06-23 driver (checks.jsonl, checks/NNNN.c, context --json, notes layout), 06-25 canary, 06-26 preflight (first real attempt check)]

actuals:
  tokens: 18000   # chars/4 over the realized diff (~72 KB)
  tasks: 3
  commits: 11
plan_head_before: ca93eb245503a8aa89ef88959f255403313f4e3c
plan_head_after: f47261b97e2b3fb991e91c37b502ab41cb4452a2
fix_round_1:
  base: 53d6127ce961b02296ad5bd516415bcfe09a0957
  head: d09bebc5cf0e491d65c440485a79357ced6fb22c
  commits: 15  # git rev-list --count 53d6127..d09bebc: 14 code/test/docs commits through ebb6fa0 + the SUMMARY commit d09bebc
fix_round_2:
  base: d09bebc5cf0e491d65c440485a79357ced6fb22c
  head_before_summary: 577952a
  commits: 9  # git rev-list --count d09bebc..577952a; the round's SUMMARY commit is one more

tech-stack:
  added: []
  patterns:
    - "Wrapper argv checked against the hook's own forms (hooks.attempt_form_matches on the raw argv after `attempt`), so the hook and the wrapper cannot drift"
    - "Per-attempt O_EXCL lock plus O_EXCL slot files: the budget counts reserved slots, not log lines"
    - "Module-level ROOTS and RUNNER read at call time; tests replace them, the CLI never takes a root from the agent"

key-files:
  created:
    - tools/reverseapoc/attempt.py
    - tests/test_attempt_wrapper.py
    - tests/test_skill.py
    - .claude/skills/watcom-decomp/SKILL.md
  modified:
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/contextpack.py
    - tools/reverseapoc/hooks.py  # fix round 1 M14
    - tests/test_hooks.py  # fix round 1 M14
    - tests/test_contextpack.py  # fix round 1 M11
    - .claude/rules/src.md
    - docs/coding-style.md

key-decisions:
  - "The budget counts reserved checks/NNNN.c slots (created with O_EXCL under check.lock), so exit-2, killed and sweep runs all count; a refused call (budget, lock, argument, environment) counts nothing"
  - "A stale check.lock is never cleared: every session gets a fresh attempt dir, so it ends that attempt's checks (fail closed)"
  - "A sweep hit is a 100.0 cell with reloc_ok and differing 0 whose `compiler flags` differ from the unit's own cflags.txt rule; logged as sweep_hit `wcc386@V flags...`"
  - "check exit is passed through only when it agrees with the JSON's ok (0 with ok true, 1 with ok false); anything else, or no JSON, is exit 2"
  - "Fix round 1 I1: attempt check exits 0 only when check exits 0 and the claimed function itself passes (objdiff 100, reloc and bytes ok); a claimed function that is a stub or absent from functions[] is exit 1 'was not compiled (still INCLUDE_ASM?)' with no measurement; a FUNC that is no game/thunk row of the claimed unit is refused with exit 2 before a slot is reserved"
  - "A sweep exits 0 when it ran and 2 when it did not, never 1; its 0 reads 'SWEEP RAN (a diagnostic: never a match)'"
  - "The wrapper prints the absolute POSIX paths of checks/NNNN.json and checks/NNNN.c, and REVERSEAPOC_ATTEMPT_NOTES, which must be <attempt dir>/notes.md (fix round 1 M8)"
  - "Fix round 1 M11 (extension of D-14): no fixed notes cap; earlier notes are cut only when the pack is over 24 KB after look-alikes, callers and the draft: attempts.jsonl records first (oldest first), then notes.md texts (oldest first), so records never crowd out notes and the newest note is the last thing cut"
  - "Fix round 1 M7: the check container is named reverseapoc-attempt-<8 hex of sha256(attempt dir)>-<NNNN>; after a runner timeout the wrapper runs docker rm -f <name> through the same runner, and keeps check.lock if that fails"

patterns-established:
  - "Skill commands test: every backticked `uv run` span in SKILL.md must be ATTEMPT_PREFIX plus one of ATTEMPT_FORMS (asm <NAME> quoted literally), and all five forms must appear"

requirements-completed: [AGT-08, AGT-09, AGT-05]

coverage:
  - id: D1
    description: "attempt check runs `docker compose run --rm -T build uv run --frozen reverseapoc check <claim> --json` (+ --sweep <func>) through an injectable runner, logs checks/NNNN.json, NNNN.c and checks.jsonl, passes 0/1/2"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_attempt_check_builds_the_container_argv, test_attempt_check_passes_exit_codes_and_logs, test_attempt_check_snapshots_the_source, test_attempt_check_sweep_logs_a_hit"
        status: pass
    human_judgment: false
  - id: D2
    description: "The wrapper refuses agent arguments and a bad environment with exit 2, accepts exactly hooks.ATTEMPT_FORMS, and enforces the 25-run budget even under concurrent runs"
    requirement: AGT-05
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_attempt_refuses_agent_arguments, test_attempt_refuses_a_bad_environment, test_attempt_forms_match_the_hook, test_attempt_check_budget, test_attempt_check_refuses_a_concurrent_run, test_a_reserved_slot_counts_even_when_its_run_failed, test_attempt_check_releases_the_lock_after_a_runner_exception, test_a_stale_lock_is_never_cleared"
        status: pass
    human_judgment: false
  - id: D3
    description: "reverseapoc context EXE FUNC writes the D-13 pack under build/driver/ (earlier notes per F9); attempt asm and attempt context work for the claimed EXE only"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_context_verb_writes_the_pack, test_context_verb_collects_earlier_notes, test_context_verb_json_reports_size_and_cuts, test_context_verb_refuses_an_out_outside_build_driver, test_attempt_asm_prints_the_claimed_listing, test_attempt_context_rebuilds_into_the_attempt_dir"
        status: pass
    human_judgment: false
  - id: D4
    description: "watcom-decomp SKILL.md: shape, paths, verbs and commands checked by tests/test_skill.py"
    requirement: AGT-09
    verification:
      - kind: unit
        ref: "tests/test_skill.py (13 tests after fix round 1)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The skill makes fresh agents answer S1-S4 correctly with fewer tool uses (writing-skills GREEN run)"
    requirement: AGT-09
    verification: []
    human_judgment: true
    rationale: "The with-skill pressure-scenario runs are the orchestrator's (subagents cannot be spawned here). GREEN passed before fix round 1; the orchestrator re-runs the affected scenarios after this REFACTOR"
  - id: D6
    description: "D-18 pragma policy text in .claude/rules/src.md and docs/coding-style.md"
    requirement: AGT-09
    verification:
      - kind: other
        ref: "grep -q human-reviewed .claude/rules/src.md && grep -q human-reviewed docs/coding-style.md"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-10-25
---

# Phase 6 Plan 15: Attempt wrapper, context verb and watcom-decomp skill Summary

**`reverseapoc attempt check|asm|context` is now the only Bash a matching session runs. The target comes from the driver's environment only. Runs are serialized by a lock, with a 25-slot budget, and logged as checks/NNNN.{c,json} + checks.jsonl. A `reverseapoc context` verb writes the D-13 pack. A 139-line watcom-decomp skill, written from the RED baseline, gives agents the rules, the recipes and the end-of-attempt contract.**

Execution context nonce: e4dfac9bbd917dd4

## Performance

- **Duration:** about 18 min of wall clock between the first and last commit stamps. Started 2026-10-25T05:29:56Z, completed 2026-10-25T05:48:01Z.
- **Tasks:** 3 of 3. Two orchestrator-requested fix cycles ran inside them: the security finding, and the attempt-dir output.
- **Files:** 4 created, 4 modified.

## Accomplishments

- **`attempt check [--sweep]`** (D-44, D-07):
  - The claim is validated from `REVERSEAPOC_CLAIM` (`(ufo2p|tacp)/[a-z0-9_]+`), `REVERSEAPOC_FUNC` (`func_[0-9A-F]{8}`) and `REVERSEAPOC_ATTEMPT_DIR`. The attempt dir must be an existing directory strictly below `<repo>/build/driver/`, compared part by part with exact case.
  - The run is argv-only (no shell), with `-T`, through `attempt.RUNNER`. A missing docker or the 580 s timeout becomes a logged exit-2 run.
  - Each run leaves `checks/NNNN.c` (F10), `checks/NNNN.json`, and a `checks.jsonl` line with `n, exit, sweep, best_percent, reloc_ok, bytes_ok, splice_ok, sweep_hit, source`.
- **The argument check.** `cli.main` keeps the raw argv. `_cmd_attempt` requires `hooks.attempt_form_matches(argv after "attempt")` (F27). On top of that, argparse runs with `allow_abbrev=False`, so `--swe`, `asm 9x`, `asm -- NAME` and `context x` all exit 2 and the runner is never called.
- **`reverseapoc context EXE FUNC [--out DIR] [--json]`** (D-13, D-14):
  - inputs: `status.csv`, every unit text of the EXE (strict UTF-8 bytes), `asm/<exe>/` listings and `ghidra/` drafts, `include/common.h`, matching.md's "Known idioms" and "Relocation rules" (by heading), and earlier notes;
  - output: written only under `build/driver/`, by default `build/driver/manual/<exe>/<func>/`;
  - `--json` prints `path`, `pack_bytes`, `truncated` and `sections` for the driver's attempts.jsonl.
- **`attempt asm [NAME]`** prints a listing of the claimed EXE. **`attempt context`** rebuilds the pack into `<attempt dir>/context.md`, prints it, and names the notes path on stderr.
- **`.claude/skills/watcom-decomp/SKILL.md`** (139 lines, about 1,600 words). Its parts:
  - a quick-reference table;
  - a three-line prohibition list;
  - D-19's nine sections in order;
  - the check-JSON-to-instruction recipe;
  - the give-up rule, with the notes.md contract.
- **D-18 text** in `.claude/rules/src.md` and `docs/coding-style.md`.

## Task Commits

1. **Task 1 (tracer): attempt check**
   - RED `ccedbaa` (test), GREEN `cce58ca` (feat).
   - Tracer gate: interactive, `end-of-phase`, verify automated only. The verify re-ran green (32 passed), then expansion continued.
2. **Task 2: context verb, attempt asm/context**
   - RED `100bca9` (test), GREEN `7f8552a` (feat).
3. **Security finding 1 (orchestrator ruling, in Task 1's code)**
   - RED `474c9d2` (test), GREEN `457e83a` (fix).
4. **Rule 2: the attempt dir in the wrapper output (for Task 3's recipe)**
   - RED `1cf25c1` (test), GREEN `b8e8517` (fix). `b8e8517` was committed with two tests still red; `511619c` (fix) repairs it, see Deviations.
5. **Task 3: watcom-decomp skill + D-18**
   - RED `cc25102` (test), GREEN `f47261b` (docs).

## TDD and RED evidence

pytest's console report is not one of the formats `check tdd-red-evidence` supports, and `workflow.tdd_mode` is off. As in 06-02, 06-03 and 06-13, I judged RED by reading each failure:

- **Task 1:** collection failed with `ImportError: cannot import name 'attempt'`. The module did not exist yet; this is the new-module precedent of 06-02 and 06-13. After GREEN, 31 passed.
- **Task 2:** 6 failed, the Task 1 tests passed. The failures were `invalid choice: 'context'` and `attempt asm/context is not available yet` (exit 2 where 0 was expected), which is the planned missing behaviour. Setup was clean.
- **Security:** 4 failed on assertions:
  - the count came from the log (`assert 1 == 25`);
  - the second concurrent run reached the runner and blocked (`release.wait` timed out);
  - no slot was kept after the exception (`assert 1 == 2`);
  - a stale lock did not refuse (`assert 0 == 2`).
- **Attempt dir output:** 2 failed on assertions (the path was missing from stdout and stderr).
- **Task 3:** 5 failed with `FileNotFoundError` on SKILL.md, the failure the plan names ("they fail: no SKILL.md").

## The skill: superpowers:writing-skills

- **Skill used:** `superpowers:writing-skills` was invoked for Task 3's GREEN step, as `.claude/rules/workflow.md` and D-19 require.
- **RED** was run by the orchestrator: four pressure scenarios, each in a fresh agent, with no skill. The files are in `.superpowers/sdd/let-s-work-on-phase-effervescent-nebula/skill-baseline/`:
  - `SCENARIOS.md`;
  - `S1-red.md`, `S2-red.md`, `S3-red.md`, `S4-red.md`;
  - `RED-FINDINGS.md`.
  I read all six before writing the skill.
- **Form chosen** ("Match the Form to the Failure"): no rule broke at baseline. The failures were cost (21-37 tool uses per answer) and guessed facts. So the body is a reference plus recipes and a contract. The prohibitions are a short plain list, with no rationalization table and no red-flags list, because the baseline shows no rationalization to counter.
- **What addresses which baseline failure:**

| Baseline failure (RED-FINDINGS) | Skill part |
|---|---|
| 21-37 tool uses to find the rules in CLAUDE.md, rules, docs, check.py, hooks.py, configure.py | Quick-reference table: Bash forms, writable paths, exit codes, budget, time, evidence paths, flags, linker names, marker; plus an extern-type table by access width. The intro says "never read `tools/` to find a rule". |
| S2's Bash slip | Table row "The only Bash": anything else (`ls`, `cat`, `sed`, host check, docker, objdiff-cli) is denied and costs a turn; look around with Read, Grep and Glob. |
| No JSON-to-instruction recipe (S2) | "From a mismatch to the instruction": four steps from `bytes.first_va` and `reloc.problems` to the `attempt asm` line. The section also states that there is no disassembly of our object. |
| Guessed: do exit-2 runs and sweeps count? | "Every run counts: exit `0`, `1` or `2`, and each `--sweep`. A call the wrapper refuses before running counts nothing." This is settled from the reserved-slot counter. |
| Guessed: the real time budget | "30 minutes, about 90 s per check: plan on about 15 checks. A sweep takes minutes", plus the 600000 ms Bash timeout (F33). |
| S3 vs S4 disagreed on what to leave in the unit | "Leave the unit file as it is. Do not restore `INCLUDE_ASM` and do not re-check to confirm." The driver keeps every `checks/NNNN.c`, scores the best and resets the unit. This is settled from 06-23 and F10. |
| Guessed: where the definition goes | "Delete the claimed function's marker line, put prototypes, externs, then the definition after the marker block. File order does not change the object." This is settled from configure.py ("The order of the file does not matter") and the two matched units. |
| `void` vs `int` | The learnings.md rule, in one line. |
| S4's sweep after three shapes | Give-up step 2: one sweep is allowed when the residue is register allocation or instruction choice and time remains, and only after notes.md is written. |
| Where notes.md and the JSON are (S2 globbed `build/driver/*`) | The wrapper now prints both absolute paths, and the skill says where (Rule 2 deviation below). |
| Security finding 1 (orchestrator) | Prohibition: never `run_in_background`; checks run one at a time, in the foreground. The lock message is explained. |

- **GREEN verification:** pending. The orchestrator re-runs S1-S4 with the skill, and runs any REFACTOR rounds, after I return. Corrections come back as fix rounds.

## Files Created/Modified

- `tools/reverseapoc/attempt.py` (new, GPLv3 header): the wrapper, the lock and slots, the check log, the EXE loader, the pack builder and the three `cmd_*` entries.
- `tools/reverseapoc/cli.py`:
  - the `attempt` and `context` verbs;
  - `AttemptError` and `ContextPackError` in `_ERRORS`;
  - `main` keeps `args.raw_argv`;
  - the docstring verb list gains `context` and `attempt`.
- `tools/reverseapoc/contextpack.py`: `STATUS_MATCHED` and `STATUS_PARTIAL` are imported from `status.py`. `STATUS_UNMATCHED` stays local, with a comment. The TODO(06-15) is closed.
- `tests/test_attempt_wrapper.py` (new, 44 tests) and `tests/test_skill.py` (new, 5 tests).
- `.claude/skills/watcom-decomp/SKILL.md` (new).
- `.claude/rules/src.md` and `docs/coding-style.md`: the D-18 text.

## Decisions Made

See `key-decisions` in the frontmatter. In addition:
- Every refusal from the attempt wrapper exits 2: `_cmd_attempt` catches `_ERRORS`.
- The `context` verb follows `main`'s usual exit 1 on errors.

## Deviations from Plan

**Orchestrator rulings applied:**
- **Orchestrator ruling F9: where earlier notes are found.** `earlier_notes` collects `build/driver/*/<exe>/<func>/attempt-*/notes.md` and `build/driver/*/<exe>/<func>/notes.md`, sorted by path relative to build/driver. Tested with the driver's layout (`test_context_verb_collects_earlier_notes`), including exclusion of another function and of the other EXE.
- **Orchestrator ruling F10: a source snapshot per check.** Each run writes `checks/NNNN.c` next to `NNNN.json`, and `CheckLogLine.source` holds its path relative to the attempt dir (`test_attempt_check_snapshots_the_source`). Since the security fix, the snapshot is also the run's reserved slot.
- **Orchestrator ruling F27 (consumer): the forms come from the hook.**
  - The wrapper's argument check is `hooks.attempt_form_matches` on the raw argv after `attempt`.
  - test_skill's command check accepts a span only if it is an `ATTEMPT_FORMS` entry or matches `attempt_form_matches`.
  - The skill quotes `uv run --frozen reverseapoc attempt asm <NAME>` literally.
- **Orchestrator ruling F33: the sweep path.**
  - `test_attempt_check_sweep_logs_a_hit`: a 100.0 cell under `wcc386@10.5 -4r -ox -s -fpi` gives `sweep_hit` naming it. A 100.0 cell under the unit's own rule, or one with a failed relocation, gives none.
  - The skill tells the agent to use the Bash tool's `timeout` 600000.
- **Orchestrator notes on what 06-13 built:**
  - every unit text of the EXE goes to `gather`;
  - unit files are read as `read_bytes().decode("utf-8")`;
  - status strings are exactly `matched` and `partial` (from status.py), or absent;
  - `make_pack(calls=...)` reuses one CallIndex;
  - `pack_bytes` and `truncated` come out of `context --json` for the driver to record.
- **Orchestrator note (wave 4): close the contextpack TODO.** `tools/reverseapoc/contextpack.py` is added to the plan's files. `STATUS_MATCHED` and `STATUS_PARTIAL` now import `status.MATCHED` and `status.PARTIAL`. `STATUS_UNMATCHED` stays local, commented. `STATUSES` keeps its three values. The picker's TODO(06-25) is untouched.
- **Orchestrator ruling (security finding 1, VALID): check budget TOCTOU.**
  - **Threat:** concurrent `attempt check` runs started with Bash `run_in_background` all read the same count before a ~580 s container run, so they bypassed D-07's 25 runs and collided in build/.
  - **Fix** (`474c9d2` RED, `457e83a` GREEN):
    - `<attempt dir>/check.lock` is created with O_CREAT|O_EXCL and held for the whole run. A held lock exits 2 at once with "another check is running in this attempt".
    - Under the lock, the run number is reserved by creating `checks/NNNN.c` with O_EXCL. The budget is the highest reserved number.
    - The lock is released in a `finally`.
  - **Stale locks:** the wrapper never clears one. Every session gets a fresh attempt dir, so a stale lock ends that attempt's checks (fail closed); `test_a_stale_lock_is_never_cleared` pins this.
  - **Skill:** "never `run_in_background`, one check at a time, in the foreground".
  - **Tests changed:** `test_attempt_check_budget` now pre-creates reserved slots (`_reserve`), because the count moved from log lines to slots.

**Auto-fixed issues:**

1. **[Rule 2 - Missing critical] The wrapper names the attempt directory and notes.md.**
   - Found during: Task 3.
   - Issue: the goal prompt (06-17) names notes.md but not the attempt directory. The skill's recipe reads `checks/NNNN.json` and writes notes.md there, and the S2 baseline agent had to glob `build/driver/*`.
   - Fix: `attempt check` prints the absolute POSIX paths of `NNNN.json`, `NNNN.c` and `<attempt dir>/notes.md`. `attempt context` names the pack and notes paths on stderr; stdout stays the pack.
   - Files: tools/reverseapoc/attempt.py, tests/test_attempt_wrapper.py.
   - Verification: `test_attempt_check_names_the_attempt_dir`, and an extra assertion in `test_attempt_context_rebuilds_into_the_attempt_dir`.
   - Commits: `1cf25c1`, `b8e8517`, `511619c`.
2. **[Rule 1 - Bug] `b8e8517` was committed with two tests red.**
   - Issue: my verify command piped pytest into `tail`, so its exit code was lost. On Windows the new paths printed with backslashes, so `checks/0001.json` was not found. The context test also read stderr after an earlier `readouterr()` had consumed it.
   - Fix: `511619c` prints paths with `as_posix()` (the Read tool takes forward slashes on every host) and captures once in the test.
   - Verification: the wrapper and skill tests re-ran with a real exit code (49 passed, rc=0). Every later verify kept pytest's own exit code.
3. **[Rule 2 - Missing critical] Earlier notes are bounded to the newest 6144 bytes (`NOTES_CAP`).** Superseded by fix round 1 M11 (see "Fix round 1" below): the fixed cap is gone.
   - Issue: notes are a required pack section, which build_pack never cuts. An attempt that wrote long notes would make every later pack of that function fail the 24 KB cap.
   - Fix: the newest 6144 bytes are kept, with a marker for what was cut.
   - Commit: `7f8552a`.
4. **[Rule 3 - Blocking, test-only] The `Build/driver/...` environment case was dropped from `test_attempt_refuses_a_bad_environment`.**
   - Issue: on Windows, `Build/` is the same directory as `build/`, so that case cannot fail there.
   - Fix: it is replaced by the pure-path `test_attempt_dir_is_compared_with_exact_case`, which holds on every host. R-A: no platform skip was added.
   - Commit: `cce58ca`.

**Assumptions recorded for 06-23 (not deviations, no code depends on them beyond a filter):**
- `progress/attempts.jsonl` records join the notes when `kind == "attempt"`, `exe == <stem>` and `function == func_XXXXXXXX`. The schema is 06-23's. If 06-23 names these keys differently, `_attempt_records` needs one line changed.
- The attempt dir must exist when the session starts. The driver creates it, and the wrapper never creates it.

**Total deviations:**
- 7 orchestrator rulings or notes applied (F9, F10, F27, F33, the 06-13 notes, the contextpack TODO, security finding 1).
- 4 auto-fixed: 2 Rule 2, 1 Rule 1, 1 Rule 3.

**Impact:** the rulings and the security fix tighten D-07 and D-44. The Rule 2 output change is additive, and the driver reads the same files. There is no scope creep beyond what the skill's recipe needs.

## Threat model update

| Threat ID | Category | Component | Disposition | Mitigation as built |
|---|---|---|---|---|
| T-06-33 | Elevation of privilege | attempt check | mitigate | The target comes only from the validated env. The argv is a list (no shell). The raw argv must equal a `hooks.ATTEMPT_FORMS` entry; `allow_abbrev=False`. |
| T-06-34 | Tampering | check flags | mitigate | No `--cflags`, `--watcom-dir` or `--src` reaches check. A sweep hit is only logged. |
| T-06-35 | Denial of service | check loops | mitigate | 25 slots per attempt, enforced by O_EXCL slot files under `check.lock`. |
| T-06-35b (new) | Denial of service / tampering | Bash `run_in_background` | mitigate | Concurrent runs would bypass the count and collide in build/. The per-attempt O_EXCL lock refuses a second run at once (exit 2). A stale lock fails closed. The skill forbids background checks. |
| T-06-36 | Information disclosure | listings and packs | mitigate | Printed to the session's stdout only. Saved only under `build/driver/` (`write_pack`'s exact-case anchor; the attempt dir is validated the same way). |

## Threat Flags

None beyond the table above. The only new process launch is the planned `docker compose run`, and the only new files are under the validated attempt dir.

## Issues Encountered

- `ruff format --check` would reformat cli.py, which was already unformatted at base. The repo enforces only `ruff check`, and that is green.
- The harness refuses compound `git` shell commands in this worktree, so the plan ledger and the self-check ran as plain separate commands.

## Known Stubs

None.

## User Setup Required

None.

## Fix round 1

Rulings: `.superpowers/sdd/let-s-work-on-phase-effervescent-nebula/fixround-06-15-r1.md` (answering review-06-15.md). Base `53d6127`. Every behaviour change had a RED test commit that failed on its assertion (or on the missing name the test wished for) before its GREEN commit.

| Item | Change | Tests (RED commit -> GREEN commit) |
|---|---|---|
| I1(a) | `claimed_row`: FUNC must be a game or thunk row of the claimed unit in functions.csv (the rows check accounts for), read once per call; else exit 2 before the lock and before any slot. asm/context reuse it on check's loaded rows. | `test_attempt_refuses_a_func_that_is_no_game_row_of_the_claimed_unit` x3 (another unit, a runtime row, no row; plain and `--sweep`) (`be64d46` -> `31c1470`) |
| I1(b) | `_verdict`: exit 0 only when check exits 0 agreeing with `ok` and the claimed function has objdiff 100, reloc ok and bytes ok. A stub or absent claimed function is exit 1, prints "func_X was not compiled (still INCLUDE_ASM?)" and logs `best_percent`/`reloc_ok`/`bytes_ok` as null. check's own 2 passes through. | `test_attempt_check_a_stub_claim_is_not_a_match`, `..._missing_from_the_json_is_not_a_match`, `..._must_pass_and_check_exit_0` (same commits) |
| I1(c) | A sweep's 0 reads "SWEEP RAN (a diagnostic: never a match)"; exit rule 0 ran / 2 did not / never 1, stated in the skill and tested. | `test_attempt_sweep_exit_is_never_a_match`; skill: `test_skill_states_the_exit_codes_in_the_wrapper_section` |
| I1(d) | cli.py `attempt` description and `_cmd_attempt` docstring; SKILL.md quick-reference row. | `test_attempt_help_states_the_claimed_function_rule`; `test_skill_states_the_exit_codes_in_the_wrapper_section` |
| M1 | Skill: timeout 600000 on every `attempt check`, plain or `--sweep`; the wrapper's 580 s stays below it. | `test_skill_states_the_timing_rules` (`2a92322` -> `ebb6fa0`) |
| M2 | "90 s / 15 checks" removed. The summary head is `attempt check 7/25, 41 s (18 left) ...`, timed by `attempt.CLOCK` around the runner; the skill says to budget by it. | `test_attempt_check_prints_elapsed_seconds_and_checks_left` (`a53a670` -> `f817490`); `test_skill_states_the_timing_rules` |
| M3 | Skill: "C89 is required: the driver lints the unit before it commits a match" (06-23 makes it true). | `test_skill_states_the_lint_and_file_order_rules` |
| M4 / R2 | Skill: the ruling's file-order wording, with `docs/matching.md#relocation-rules`. | same test |
| M5 | test_skill: `anchors_problems` (every `path#anchor` is a `##`/`###` heading slug of the file), `attempt_form_problems` (every backticked span with an `attempt` token, short or full, is an ATTEMPT_FORMS entry), `json_field_problems` (every dotted JSON path in the skill and every bare key in its JSON block is a key path of a real `to_json` of a made-up CheckResult and SweepReport, or a checks.jsonl key). | `test_skill_anchors_resolve`, `test_skill_short_attempt_forms_are_wrapper_forms`, `test_skill_json_fields_exist`. Mutation probe on in-memory copies (scratch script, the file never written): `#flags`->`#flagz` CAUGHT; `#relocation-rules`->`#relocation-rule` CAUGHT; `` `attempt asm` ``->`` `attempt disasm` `` CAUGHT; `` `attempt check --sweep` ``->`` `attempt sweep` `` CAUGHT; `` `reverseapoc attempt chek` `` CAUGHT; `bytes.first_va`->`bytes.first_addr` CAUGHT; `reloc.problems`->`reloc.problem` CAUGHT; `splice[]`->`splices[]` CAUGHT; `differing`->`different` CAUGHT (9/9). |
| M6 | checks.jsonl sweep lines carry `sweep: true` (plain lines `false`); 06-23 must skip them when picking the best C (rulings ## 06-23). | `test_attempt_sweep_exit_is_never_a_match` asserts every sweep line's `sweep` is true; `test_attempt_check_sweep_logs_a_hit` already did |
| M7 | `docker compose run --rm -T --name reverseapoc-attempt-<8 hex of sha256(attempt dir)>-<NNNN> build ...`. `Ran.timed_out` (the default runner sets it on TimeoutExpired) triggers `docker rm -f <name>` through the same runner before the lock is released; a failed removal (non-zero or an exception) keeps `check.lock`. | `test_attempt_check_builds_the_container_argv`, `test_container_names_differ_per_attempt_dir`, `test_a_timed_out_run_removes_its_container`, `test_a_container_that_cannot_be_removed_keeps_the_lock`, `test_the_default_runner_reports_a_timeout` (`2219bdf` -> `9c6288e`) |
| M8 | `Claim.notes` from `REVERSEAPOC_ATTEMPT_NOTES`; it must resolve to `<attempt dir>/notes.md` (part by part, exact case), else exit 2; that value is the path printed by `attempt check` and `attempt context`. | `test_attempt_refuses_a_notes_path_that_is_not_the_attempt_dirs` x3 (unset, other.md, ../notes.md), `test_attempt_check_prints_the_notes_env_path` (`a53a670` -> `f817490`) |
| M9 | `_cmd_attempt` catches any `Exception` after `_ERRORS`: one stderr line `reverseapoc attempt: error: <Type>: <msg>`, exit 2, no traceback. | `test_an_unexpected_exception_is_a_tool_error`, `test_attempt_asm_an_undecodable_listing_is_a_tool_error`; `test_attempt_check_releases_the_lock_after_a_runner_exception` now expects exit 2 (same commits) |
| M10 | Exit codes moved into "## The attempt wrapper" (D-19 section 8); the quick-reference row points there. | `test_skill_states_the_exit_codes_in_the_wrapper_section` |
| M11 | `attempt.NOTES_CAP` and `_bounded` removed. `earlier_notes` returns `contextpack.Notes(texts, records, records_label)`; `build_pack` cuts notes as a fourth step after look-alikes, callers and the draft: records oldest first, then texts oldest first. Texts render before records; the header counts both; the section starts `... N older notes and M attempt records cut`. | `test_notes_render_texts_before_records`, `test_notes_are_cut_only_after_the_d14_cuts_records_first`, `test_notes_cut_the_oldest_first_and_keep_the_newest`, `test_notes_as_text_stay_one_uncut_block`, `test_context_verb_keeps_long_notes_whole_when_the_pack_fits` (`5598c15` -> `81efed9`) |
| M12 | `attempt.load_exe`/`ExeData` removed; `attempt.exe_inputs` wraps `check.select_exe` + `check.load_exe` (ExeInputs has the same `stem/rows/symbols/flat/fixups`). | `test_attempt_reads_the_exe_with_checks_loader`, `test_context_verb_reads_config_like_check` (`15d29f9` -> `f6de682`) |
| M13 | No change (recorded). | - |
| M14(a) | Matching layer: a Bash call whose `tool_input.run_in_background` is anything but absent or false is denied, "checks run in the foreground, one at a time". | `test_matching_denies_a_background_bash` x3 (True, "true", 1), `test_matching_allows_a_foreground_bash`, `test_always_ignores_background_bash` (`e8ec804` -> `73a2426`) |
| M14(b) | Matching layer: src/ and include/ writes with any `#pragma` directive are denied (`_PRAGMA` on configure's blanked, spliced logical lines; `any_pragma=True` only from `_matching_write`). The always layer is unchanged (`any_pragma` defaults to False). Skill, `.claude/rules/src.md` and `docs/coding-style.md` say "no `#pragma` of any kind". | `test_matching_denies_every_pragma` x8 (`#pragma on/off (check_stack)`, `pack(1)`, `warning`, spaced `once`, continued, comment-split, trigraph `??=pragma`), each also asserting the always layer does not deny; `test_matching_allows_pragma_words_outside_code`; `test_pragma_policy_is_every_pragma` |
| R1 | Skill: each sweep cell reports `objdiff_percent`, `reloc_ok` and `differing` (bytes outside relocated fields) under its `compiler` and `flags` (SweepCell.to_json); "A sweep hit is never a match until a plain `attempt check` under the new rule passes". | `test_skill_states_what_a_sweep_cell_reports` |
| R2 | Covered by M4. | - |

The skill change is the REFACTOR step of superpowers:writing-skills (invoked): only the items above were changed; SKILL.md is 147 lines. The orchestrator re-runs the affected scenarios.

### Fix round 1 deviations

- **M11 is an extension of D-14.** D-14 lists three cuts (look-alikes, callers, the draft); notes are now a fourth, applied only while the pack is still over 24 KB. Reading of the ruling: "records never crowd out notes" means the attempts.jsonl records are cut before any notes.md text, and "the oldest notes first, the newest kept" means texts are cut oldest first. Files: `tools/reverseapoc/contextpack.py` (already in scope by rulings ## 06-15), `tests/test_contextpack.py`.
- **M14 scope addition.** `tools/reverseapoc/hooks.py` and `tests/test_hooks.py` join this plan's files. Matching layer only; the always layer's behaviour is byte-for-byte the same (its call passes no `any_pragma`), and no tooling write outside a matching session is newly denied.
- **M12 is not a pure move**, so it is recorded here: check's loader requires `config/<exe>/units.csv` (the old loader did not) and treats symbols.csv as optional (the old one required it); the `context` verb now reads every CSV from `--config` as check does and no longer takes `--functions`/`--symbols` (it used `_add_split_inputs` before). The test fixture gained a units.csv. No cli loader was reused: `cli._split_inputs` takes an argparse namespace and ignores `--config`.
- **I1(a) reads functions.csv only** for `attempt check`, not units.csv or the LE, so a check needs no orig/ read on the host; asm/context validate on check's already-loaded rows. A unit missing from units.csv still fails in the container (check's exit 2 passes through).
- **Test edits inside GREEN commits** (lint only): `81efed9` turned a `%` format in the RED helper into an f-string (ruff UP031).
- **06-23 consumers (notes, not code):** a not-compiled check line has `exit` 1 and null `best_percent`; skip null percents when picking the best C. `REVERSEAPOC_ATTEMPT_NOTES` is now required by every `attempt` subcommand. The container-name prefix is `attempt.CONTAINER_PREFIX` + 8 hex of sha256 of the RESOLVED attempt dir's POSIX path; since fix round 2 (N3) the driver gets it only from `attempt.container_prefix(attempt_dir)`.

## Fix round 2

Rulings: `fixround-06-15-r2.md` (answering `rereview-06-15-r1-report.md`, approved with no Critical or Important findings), plus N7 from the security finding at the end of `security-findings-06-15.md`. Base `d09bebc`. Each behaviour change has a RED commit that failed on its assertions before its GREEN commit. The RED `test_the_default_runner_takes_a_timeout` turns the missing keyword's TypeError into an explicit `pytest.fail`.

| Item | Change | Tests (RED -> GREEN) |
|---|---|---|
| N1 | `_cmd_attempt` prints every tool error (both the `_ERRORS` and the `Exception` branch) through `_one_line`: each CR/LF run becomes a space, so it is exactly one stderr line. | `test_a_multi_line_error_is_printed_as_one_line` x2 (RuntimeError, OSError) (`c2fae6c` -> `d647046`) |
| N2 | After a timeout, the run's `NNNN.json` and its checks.jsonl line (exit 2) are written BEFORE `docker rm -f`. The removal has its own `RM_TIMEOUT = 15` s (580 + 15 < 600). `default_runner(argv, *, timeout=CHECK_TIMEOUT)` passes the timeout on. A failed, slow (timed-out) or raising removal keeps the lock. | `test_the_evidence_is_written_before_the_removal`, `test_the_removal_has_its_own_short_timeout`, `test_the_default_runner_takes_a_timeout`; `TimeoutRunner` now records kwargs and the on-disk evidence at the removal (`6eda63f` -> `cee76e7`) |
| N3 | `attempt.container_prefix(attempt_dir)` resolves the directory and is the single source of container names; `container_name` is `container_prefix(...) + NNNN`. The 06-23 note above says the driver reuses it. | `test_container_prefix_is_the_names_single_source` (the argv name equals `prefix(repo) + "0001"`; `prefix(repo/sub/..) == prefix(repo)`) (same commits) |
| N4 | `CheckLogLine` docstring: null measurements for a no-JSON run (exit 2) and for a not-compiled claimed function (exit 1); `sweep` lines are never the best C. | docstring only (`8610669`) |
| N5 | Frontmatter commit counts corrected: fix round 1 has 15 commits (14 through `ebb6fa0`, plus the SUMMARY `d09bebc`); fix round 2's count is recorded the same way. | - |
| N6 | Matching layer `_PRAGMA` also matches the `%:` digraph (`\s*(#\|%:)\s*pragma`), with or without spaces after `%:`. The always layer is unchanged. SKILL.md is left alone: "no `#pragma` of any kind" already covers the spelling. | `test_matching_denies_every_pragma` gains `%:pragma off (check_stack)`, `%:  pragma pack(1)`, `  %: pragma once` (each also asserting the always layer allows it); `test_matching_allows_pragma_words_outside_code` gains a comment and a string holding `%:pragma` (`2acc61a` -> `5284a29`) |
| N7 | Security finding (MEDIUM fail-open): a raising evidence write skipped the removal and released the lock with the orphan running. Now `held.keep = True` the moment `ran.timed_out` is seen, before any evidence write. Only a removal that succeeded clears it. The removal runs in a `finally`, so a failed write still removes the container, and the write error then surfaces as exit 2. The evidence writing moved unchanged into `_record`. | `test_a_failed_evidence_write_still_removes_the_container` x4 (`write_atomic` or `_append` raises; removal ok: lock released; removal fails: lock kept), `test_a_failed_evidence_write_and_a_raising_removal_keep_the_lock` x2 (`3c70fa3` -> `577952a`) |

Verification after fix round 2 (measured, pytest's own exit code kept):
- **focused** (test_attempt_wrapper, test_hooks, test_skill, test_contextpack): 336 passed, 1 skipped (the R-A symlink reason), rc 0;
- **full host suite** `uv run --frozen pytest -q`: 2078 passed, 222 skipped, rc 0;
- **ruff:** `uv run --frozen ruff check .` passes all checks;
- **SKILL.md:** 147 lines, unchanged this round. No new skips. Docker was not run.

## Next Phase Readiness

- **06-17 (session):** the goal prompt can name `uv run --frozen reverseapoc attempt check`. The skill file for `--append-system-prompt-file` is `.claude/skills/watcom-decomp/SKILL.md`.
- **06-23 (driver):** what it can read and run:
  - `checks.jsonl` lines carry `n, exit, sweep, best_percent, reloc_ok, bytes_ok, splice_ok, sweep_hit, source`; sweep lines have `sweep: true` and must never be the best C; a not-compiled line has `best_percent: null`;
  - the best C is `<attempt dir>/<source>`;
  - `reverseapoc context EXE FUNC --out <attempt dir> --json` gives `pack_bytes` and `truncated` (notes cuts appear as `attempt record N` / `earlier note N`);
  - set `REVERSEAPOC_CLAIM`, `REVERSEAPOC_FUNC`, `REVERSEAPOC_ATTEMPT_DIR` (an existing dir below build/driver/) and `REVERSEAPOC_ATTEMPT_NOTES` = `<attempt dir>/notes.md`, and give each session a fresh attempt dir;
  - after each session, remove the containers whose name starts with `attempt.container_prefix(<attempt dir>)` (the wrapper's own name builder, which resolves the directory; fix round 2 N3; rulings ## 06-23). Never rebuild the hash in the driver.
- **06-26 (preflight):** the first real `attempt check` (docker compose `-T --name`) is still unproven, as the plan's flagged assumption says.
- **Skill GREEN verification:** passed before fix round 1; the orchestrator re-runs the affected scenarios after this REFACTOR.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/attempt.py, tests/test_attempt_wrapper.py, tests/test_skill.py, .claude/skills/watcom-decomp/SKILL.md.
- FOUND on this branch (`git log ca93eb2..HEAD`): ccedbaa, cce58ca, 100bca9, 474c9d2, 457e83a, 7f8552a, cc25102, 1cf25c1, b8e8517, 511619c, f47261b (11 plan commits), 53d6127 (plan SUMMARY), and the 14 fix-round-1 commits be64d46, 31c1470, a53a670, f817490, 2219bdf, 9c6288e, 5598c15, 81efed9, 15d29f9, f6de682, e8ec804, 73a2426, 2a92322, ebb6fa0.
- Acceptance:
  - `CHECK_BUDGET = 25` is in attempt.py, and `REVERSEAPOC_CLAIM` is read from the environment only (via `hooks.CLAIM_ENV`);
  - `uv run reverseapoc attempt check --cflags x` exits 2;
  - `context --help` and `attempt --help` exit 0;
  - SKILL.md has nine `## ` headings in D-19's order and 147 lines (≤ 300);
  - `human-reviewed` appears in both policy files, and so does "no `#pragma` of any kind".
- Verification after fix round 1 (measured, pytest's own exit code kept):
  - focused: `uv run --frozen pytest -q tests/test_attempt_wrapper.py tests/test_skill.py tests/test_contextpack.py tests/test_hooks.py`: 321 passed, 1 skipped (`symlink creation needs privileges on this host`, the R-A reason), rc 0; the same with REVERSEAPOC_ORIG / REVERSEAPOC_WATCOM_DIR / REVERSEAPOC_GHIDRA_EXPORT pointed at the main checkout: 321 passed, 1 skipped;
  - `uv run --frozen pytest -q tests/test_skill.py tests/test_hygiene.py`: 78 passed, 3 skipped (pre-existing hygiene skips);
  - full host suite `uv run --frozen pytest -q`: 2063 passed, 222 skipped, rc 0 (real-file skips; orig/ and the Watcom tree are not in the worktree); with the three env vars pointed at the main checkout: 2246 passed, 39 skipped, rc 0;
  - `uv run --frozen ruff check .`: all checks passed.
  - No new skips were added. Docker was not run (worktree); container-only tests skip on the host.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
