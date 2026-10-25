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
  - "tools/reverseapoc/attempt.py: Claim (from REVERSEAPOC_CLAIM/FUNC/ATTEMPT_DIR only), CHECK_BUDGET = 25, container_check_argv, run_check (check.lock, reserved checks/NNNN.c slots), CheckLogLine, load_exe, resolve_row, make_pack, cmd_check/cmd_asm/cmd_context"
  - "reverseapoc attempt check [--sweep] | asm [NAME] | context, argv after `attempt` equal to hooks.ATTEMPT_FORMS"
  - "reverseapoc context EXE FUNC [--out DIR] [--json]"
  - ".claude/skills/watcom-decomp/SKILL.md (139 lines) and tests/test_skill.py"
  - "D-18 pragma policy in .claude/rules/src.md and docs/coding-style.md"
affects: [06-17 session goal prompt, 06-23 driver (checks.jsonl, checks/NNNN.c, context --json, notes layout), 06-25 canary, 06-26 preflight (first real attempt check)]

actuals:
  tokens: 18000   # chars/4 over the realized diff (~72 KB)
  tasks: 3
  commits: 11
plan_head_before: ca93eb245503a8aa89ef88959f255403313f4e3c
plan_head_after: f47261b97e2b3fb991e91c37b502ab41cb4452a2

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
    - .claude/rules/src.md
    - docs/coding-style.md

key-decisions:
  - "The budget counts reserved checks/NNNN.c slots (created with O_EXCL under check.lock), so exit-2, killed and sweep runs all count; a refused call (budget, lock, argument, environment) counts nothing"
  - "A stale check.lock is never cleared: every session gets a fresh attempt dir, so it ends that attempt's checks (fail closed)"
  - "A sweep hit is a 100.0 cell with reloc_ok and differing 0 whose `compiler flags` differ from the unit's own cflags.txt rule; logged as sweep_hit `wcc386@V flags...`"
  - "check exit is passed through only when it agrees with the JSON's ok (0 with ok true, 1 with ok false); anything else, or no JSON, is exit 2"
  - "The wrapper prints the absolute POSIX paths of checks/NNNN.json, checks/NNNN.c and <attempt dir>/notes.md, because the goal prompt does not name the attempt dir"
  - "Earlier notes are capped at the newest 6144 bytes: notes are a required pack section, and an unbounded notes file would make every later pack fail the 24 KB cap"

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
        ref: "tests/test_skill.py (5 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The skill makes fresh agents answer S1-S4 correctly with fewer tool uses (writing-skills GREEN run)"
    requirement: AGT-09
    verification: []
    human_judgment: true
    rationale: "The with-skill pressure-scenario run is the orchestrator's (subagents cannot be spawned here); pending"
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
3. **[Rule 2 - Missing critical] Earlier notes are bounded to the newest 6144 bytes (`NOTES_CAP`).**
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

## Next Phase Readiness

- **06-17 (session):** the goal prompt can name `uv run --frozen reverseapoc attempt check`. The skill file for `--append-system-prompt-file` is `.claude/skills/watcom-decomp/SKILL.md`.
- **06-23 (driver):** what it can read and run:
  - `checks.jsonl` lines carry `n, exit, sweep, best_percent, reloc_ok, bytes_ok, splice_ok, sweep_hit, source`;
  - the best C is `<attempt dir>/<source>`;
  - `reverseapoc context EXE FUNC --out <attempt dir> --json` gives `pack_bytes` and `truncated`;
  - set `REVERSEAPOC_CLAIM`, `REVERSEAPOC_FUNC` and `REVERSEAPOC_ATTEMPT_DIR` (an existing dir below build/driver/), and give each session a fresh attempt dir.
- **06-26 (preflight):** the first real `attempt check` (docker compose `-T`) is still unproven, as the plan's flagged assumption says.
- **Skill GREEN verification:** pending, the orchestrator's.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/attempt.py, tests/test_attempt_wrapper.py, tests/test_skill.py, .claude/skills/watcom-decomp/SKILL.md.
- FOUND on this branch (`git log ca93eb2..HEAD`): ccedbaa, cce58ca, 100bca9, 474c9d2, 457e83a, 7f8552a, cc25102, 1cf25c1, b8e8517, 511619c, f47261b (11 commits).
- Acceptance:
  - `CHECK_BUDGET = 25` is in attempt.py, and `REVERSEAPOC_CLAIM` is read from the environment only (via `hooks.CLAIM_ENV`);
  - `uv run reverseapoc attempt check --cflags x` exits 2;
  - `context --help` and `attempt --help` exit 0;
  - SKILL.md has nine `## ` headings in D-19's order and 139 lines (≤ 300);
  - `human-reviewed` appears in both policy files.
- Plan verification:
  - `uv run pytest -q tests/test_skill.py tests/test_hygiene.py`: 70 passed, 3 skipped (pre-existing hygiene skips);
  - full host suite: 2015 passed, 222 skipped (real-file skips; orig/ and the Watcom tree are not in the worktree);
  - `uv run ruff check .`: all checks passed.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
