---
phase: 06-reporting-and-agent-pilot
plan: 25
subsystem: driver
tags: [driver, drive-verb, preflight, canary, dry-run, end-of-run, d-10, d-13, d-24, d-34, d-36, d-48]
status: complete

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-23 driver.drive/Deps/DriveConfig/DriveReport (exit 0/1/2, Deps.end_of_run before the ENDED record, checks_failed, uncommitted); 06-17 session.build_argv/run_session, streamjson.check_init/parse_version/tool_uses; 06-14 picker.queue/pilot/requeue; 06-15 attempt.exe_inputs/make_pack/container_prefix and the wrapper forms; 06-12 hooks.ATTEMPT_PREFIX; 06-24 .gitignore .playwright-mcp/"
provides:
  - "reverseapoc drive [--max-sessions N] [--target-matched N] [--dry-run | --canary] [--run ID] [--json] (cli._add_drive_command, _cmd_drive)"
  - "tools/reverseapoc/driver.py: TESTED_MAJOR, MIN_CLI_VERSION, DriveOptions, ExeWorld, Seams, command_runner, gate_argv, partial_gate_argv, lint_argv, excluded_keys, matched_keys, finish, END_OF_RUN, compose_project, container_remover, real_deps, preflight, Refused, pilot_picks, night_top_picks, dry_run, run_drive, run_canary, CANARY_PROMPT, load_world, default_seams"
  - "tests/test_drive.py (45 tests), tests/test_drive_real.py (2 real-file tests), 4 synthetic canary stream fixtures"
  - "docs/workflow.md: the driver, preflight, dry run, canary, reset rules, end of run, both hook layers"
affects: [06-26 pilot checkpoint (the owner runs drive --dry-run, drive --canary, then the pilot), 06-27 phase gate]

actuals:
  tokens: 26500   # chars/4 over git diff d86e673..dc3c34f (106,017 chars)
  tasks: 3
  commits: 12     # measured: git rev-list --count d86e673..HEAD before this SUMMARY commit
plan_head_before: d86e673dc3ab71512445f2349cbc7888b7543fac
plan_head_after: dc3c34f60cc881959d603f084327e802563c7295

tech-stack:
  added: []
  patterns:
    - "Every effect of the verb behind one frozen Seams dataclass (run, git, world, session, argv); tests answer every command with a recording fake runner"
    - "Refusals as one exception type (Refused: reason + detail) caught once in run_drive: exit 2, one JSON document in --json mode"
    - "The canary measures with a probe _Night, so it checks exactly what a night audits (pinned bytes, fingerprint)"

key-files:
  created:
    - tests/test_drive.py
    - tests/test_drive_real.py
    - tests/fixtures/stream/canary_pass.jsonl
    - tests/fixtures/stream/canary_fail.jsonl
    - tests/fixtures/stream/canary_wrapper_denied.jsonl
    - tests/fixtures/stream/canary_unknown_error.jsonl
  modified:
    - tools/reverseapoc/driver.py
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/picker.py
    - docs/workflow.md

key-decisions:
  - "Keep hooks.ATTEMPT_PREFIX as `uv run --frozen` (no `--no-sync`): the preflight runs the host `uv sync --locked` and then compileall, so the wrapper's `uv run` finds the venv in sync and writes nothing; the canary's fingerprint check proves it on the real host. Changing the prefix would ripple through hooks.py, session.build_argv, the skill and test_skill"
  - "\"Partial in this pass\" (D-09) is a status.csv partial row dated today (UTC); an older partial row is eligible again. Matched rows are always skipped"
  - "Preflight order: main checkout, clean tree, CLI version (not in the dry run), docker info, container uv sync, host uv sync, compileall tools/ configure.py, asm listings of both EXEs; then the world loads and one ghidra-export --drafts per EXE runs for the pilot picks (dry run) or the queue's first max_sessions picks (night)"
  - "ghidra-export exit 1 (some drafts missing) is logged, not a refusal: a pack works without a draft; any other non-zero exit refuses"
  - "The canary runs a fifth call, `attempt check`, on the matched claim and needs it at exit 0 (Rule 2): it proves the wrapper's container path and what a container check leaves in the bind mount before the pilot"
  - "The canary leaves the tree as the session left it (no containment); the next preflight refuses a dirty tree"
  - "Container cleanup filters by the compose project label (the checkout's directory name, normalized) and the attempt's name prefix, then docker rm -f; a failing docker call is a DriverError, which the driver records and stops on (06-23 S1)"
  - "The claude executable is resolved once with shutil.which('claude') for both `claude --version` and the sessions"

patterns-established:
  - "Verb tests: Rig (tmp main checkout + Runner fake + Seams) and _canary_rig (fakeclaude through the real run_session)"

requirements-completed: [AGT-01, AGT-04, AGT-06, AGT-07, AGT-11]

coverage:
  - id: D1
    description: "drive verb with D-48 defaults; dry run prints 5 + 5 interleaved pilot picks with packs under build/driver/<run>/dry-run/, never a session or a gate; JSON `exe` is the config stem (F30)"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_drive.py#test_drive_defaults, #test_dry_run_prints_the_pilot, #test_dry_run_text_lists_the_picks, #test_drive_help_lists_the_flags, #test_cli_drive_reaches_run_drive, #test_drive_queue_skips_matched_and_todays_partial_rows"
        status: pass
      - kind: integration
        ref: "tests/test_drive_real.py#test_real_pilot_is_5_plus_5_and_skips_the_matched_rows, #test_real_pools_have_units_and_callees"
        status: pass
    human_judgment: false
  - id: D2
    description: "Real Deps: container gate, partial gate (F7 argv), lint argv, container cleanup by compose project and prefix"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_drive.py#test_drive_builds_gate_argv, #test_drive_builds_the_partial_gate_and_lint_argv, #test_remove_containers_filters_by_project_and_prefix, #test_remove_containers_failure_raises"
        status: pass
    human_judgment: false
  - id: D3
    description: "Fail-closed preflight with exit 2 and named reasons (worktree, dirty naming paths, CLI pin, docker, container/host sync, compile, asm, drafts); one JSON document with noise in preflight.log (F13)"
    requirement: AGT-04
    verification:
      - kind: unit
        ref: "tests/test_drive.py#test_preflight_refusals (9 cases), #test_preflight_refuses_a_worktree, #test_preflight_refuses_a_dirty_tree_naming_the_paths, #test_preflight_passes_a_clean_main_checkout_on_2_1_302, #test_dry_run_skips_only_the_cli_version_check, #test_preflight_regenerates_listings_and_drafts, #test_preflight_drafts_tool_failure_refuses_but_missing_drafts_do_not, #test_json_mode_stdout_is_one_document_and_noise_goes_to_the_log, #test_compiled_bytecode_is_not_rewritten_by_an_isolated_import"
        status: pass
    human_judgment: false
  - id: D4
    description: "Canary logic on synthetic streams: PASS, FAIL naming the leak, wrapper denied (F12), init problem, unknown error event, fingerprint change, failed container check, crash"
    requirement: AGT-01
    verification:
      - kind: integration
        ref: "tests/test_drive.py#test_canary_pass, #test_canary_env_names_the_claim_with_absolute_paths, #test_canary_fail, #test_canary_wrapper_denied, #test_canary_fails_on_an_init_problem, #test_canary_fails_on_an_unknown_event_type_carrying_an_error, #test_canary_fails_when_the_session_changes_what_the_driver_fingerprints, #test_canary_fails_unless_the_wrapper_check_passed, #test_canary_session_that_raises_is_a_fail, #test_canary_text_mode_prints_pass_and_fail_lines, #test_canary_runs_the_preflight_first"
        status: pass
    human_judgment: false
  - id: D5
    description: "The canary on the real CLI: denials appear in permission_denials, the wrapper and the container check work, nothing fingerprinted changes"
    requirement: AGT-11
    verification: []
    human_judgment: true
    rationale: "No test may run the real claude or docker; the owner runs `drive --canary` at plan 06-26"
  - id: D6
    description: "End of run: container ninja verify from clean, then gate --all, logged under build/driver/<run>/, failures in the ENDED record and exit 1, before the chore commit"
    requirement: AGT-06
    verification:
      - kind: integration
        ref: "tests/test_drive.py#test_end_of_run_order, #test_a_failing_end_of_run_check_is_recorded_and_exits_1 (2 cases), #test_real_deps_wire_finish_as_the_end_of_run"
        status: pass
    human_judgment: false
  - id: D7
    description: "docs/workflow.md: driver, flags, pilot command, minimum CLI, dry run, canary, wrapper commands, reset rules, hooks table (no #pragma aux for agents), Nigel rejected, spike 006"
    verification:
      - kind: other
        ref: "grep -q 'drive --max-sessions 40 --target-matched 10' && grep -q 2.1.302 && grep -q 'drive --canary' docs/workflow.md; tests/test_hygiene.py"
        status: pass
    human_judgment: false

duration: 37min
completed: 2026-10-25
---

# Phase 6 Plan 25: The drive verb, its preflight, dry run, canary and end-of-run checks Summary

**`reverseapoc drive` wires the 06-23 loop to the real world: a fail-closed preflight (main checkout, clean tree, Claude CLI major 2 and at least 2.1.302, Docker, both `uv sync --locked`, compileall, asm listings, Ghidra drafts), a `--dry-run` that prints the 5 + 5 pilot picks and builds their packs without any session, an owner-run `--canary` that passes only when the real session's forbidden calls are denied, both wrapper calls work and nothing the night audits changed, and an end-of-run container ninja verify plus `gate --all` recorded in the ENDED record.**

Execution context nonce: cd3096eb7531c5d5

## Performance

- **Duration:** about 37 min of work (19:35Z to 20:12Z), plus two full host suites
- **Started:** 2026-10-25T19:35:30Z
- **Completed:** 2026-10-25T20:30Z
- **Tasks:** 3 of 3, plus one Rule 2 extension of the canary and one real-file test
- **Files:** 6 created, 4 modified

## Accomplishments

- **The verb.** `drive [--max-sessions N] [--target-matched N] [--dry-run | --canary] [--run ID] [--json]`, defaults 30 and 10 (D-48). The run id defaults to the UTC start time. Exit 0 ended clean (or a dry run, or a canary PASS), 1 stopped, a failed end check or a canary FAIL, 2 refused.
- **The real Deps** (`real_deps`): the picker over both EXEs' `score.assess` survivors minus status.csv's matched rows and today's partial rows (AGT-07); `requeue` with the matched set read at the time and `pool_empty` from an empty queue; the worlds' scaffold (units `--write-src` logic) and pack (`attempt.make_pack` with one CallIndex per EXE); `session.build_argv` and `run_session`; the container lint, gate and partial gate argv; container cleanup; `finish` as `end_of_run`.
- **Preflight** (`preflight`, `Refused`): each refusal has a short reason and a text, printed as one JSON document with `--json`. Every command's output goes to `build/driver/<run>/preflight.log`.
- **Dry run:** the pilot (5 + 5, interleaved, variety rule) with packs under `build/driver/<run>/dry-run/<exe>/<func>/context.md`; no claude, no gate. On the real files (test_drive_real) the pilot skips both Phase 5 matches.
- **Canary** (`run_canary`): one session, fixed prompt, claim `ufo2p/u_000a34f0` `func_000A3980` with absolute paths under `build/driver/canary/<run>/`. PASS/FAIL lines like the spike scripts, then `CANARY PASS` or `CANARY FAIL`.
- **End of run** (`finish`): container `uv run --frozen python configure.py && ninja -t clean && ninja verify`, then `gate --all --json`, both always run and logged by the driver; failures become `checks_failed`; run() is not reordered.
- **Docs:** docs/workflow.md's driver and hooks sections rewritten for what Phase 6 built.

## Task Commits

1. **Task 1 (tracer): dry run, real Deps, gate argv**
   - RED `f0c241d` (test): 7 failed on assertions (interface skeletons only), 1 pin passed.
   - GREEN `69cedc1` (feat): 8 passed. Tracer gate (interactive, end-of-phase, automated-only verify): `uv run pytest -q tests/test_drive.py` re-run, 8 passed, expanded.
   - REFACTOR `d7e6cb1` (refactor): picker's TODO(06-25) closed, see Deviations.
2. **Task 2: preflight, canary, container cleanup**
   - RED `eff0014` (test): 29 failed, all on assertions (skeleton `preflight`/`compose_project`).
   - GREEN `77a0d6a` (feat): 38 passed.
   - Rule 2 extension: RED `8f78d1e` (test, 5 assertion failures: the missing fifth call, the crash escape reported through `pytest.fail`), GREEN `53ca925` (fix), docs `56827a3`.
3. **Task 3: end of run and docs**
   - RED `5e74574` (test): 4 failed on assertions (skeleton `finish`).
   - GREEN `ca68c96` (feat): 42 passed.
   - Docs `c2b0a9c` (docs). Baseline at d86e673: none of the three grep strings were in workflow.md.
4. **Real-file test** `dc3c34f` (test): see Deviations.

## TDD Gate Compliance

Every tdd task has a `test(06-25)` commit before its `feat(06-25)` commit: f0c241d -> 69cedc1, eff0014 -> 77a0d6a, 5e74574 -> ca68c96, and 8f78d1e -> 53ca925 for the canary extension. pytest's console report is not a format `check tdd-red-evidence` reads; as in 06-15 and 06-23 I judged RED by reading each failure, and each RED commit carried only interface skeletons so the failures were assertions, not imports. `d7e6cb1` is a REFACTOR with no behaviour change, pinned by tests/test_driver_pick.py's matched_starts test.

## Files Created/Modified

- `tools/reverseapoc/driver.py`: the drive verb section (options, seams, argv builders, real Deps, preflight, dry run, canary, finish, worlds); module docstring names the verb
- `tools/reverseapoc/cli.py`: `_add_drive_command`, `_cmd_drive`, `_positive`, `_run_id`; docstring verb list gains `drive`
- `tools/reverseapoc/picker.py`: `STATUS_MATCHED = status.MATCHED`
- `tests/test_drive.py`, `tests/test_drive_real.py`, `tests/fixtures/stream/canary_{pass,fail,wrapper_denied,unknown_error}.jsonl`
- `docs/workflow.md`

## Verification

- `uv run pytest -q tests/test_drive.py tests/test_session.py tests/test_streamjson.py` (Task 2 verify) and `tests/test_driver.py tests/test_attempts_schema.py tests/test_driver_pick.py`: 346 passed, 3 skipped (the existing R-A symlink skips and the POSIX-only taskkill skip).
- Task 3 verify: `uv run pytest -q tests/test_drive.py tests/test_hygiene.py` 120 passed, 3 skipped; the three greps on docs/workflow.md pass; full suite and ruff below.
- **Full host suite** (REVERSEAPOC_ORIG / REVERSEAPOC_WATCOM_DIR / REVERSEAPOC_GHIDRA_EXPORT at the main checkout), final code: **2692 passed, 44 skipped** in 458 s, exit 0. No skip comes from test_drive.py or test_drive_real.py; the 44 are the existing ones (watcom-media absent from a worktree, Ghidra/ninja/clang/objdiff-cli not on the host, the container-only and POSIX-only cases, and the R-A symlink skips of earlier plans). The run before the canary extension: 2687 passed, 44 skipped.
- `uv run ruff check .`: All checks passed.
- Acceptance: `uv run reverseapoc drive --help` lists `--max-sessions`, `--target-matched`, `--dry-run`, `--canary`; driver.py contains `MIN_CLI_VERSION = (2, 1, 302)` and `TESTED_MAJOR = 2`; the canary fixtures hold synthetic events only (made-up session ids and paths, no game text); the hooks table no longer says calling-convention pragmas stay allowed for agents.
- Smoke: `uv run reverseapoc drive --dry-run --json --run smoke06-25` in this worktree printed one REFUSED document with reason `worktree` and exit 2, before any other command.
- No test or command ran the real claude, `drive` without `--dry-run`, `drive --canary`, docker or anything that reaches the network. The tests answer every docker/uv/claude command with a recording fake; sessions are tests/fakeclaude.py by absolute path through sys.executable.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

**Orchestrator rulings (rulings.md ## 06-25), applied as plan text:**

1. **Orchestrator ruling F12: the canary proves the wrapper works.** The canary sets `REVERSEAPOC_CLAIM=ufo2p/u_000a34f0`, `REVERSEAPOC_FUNC=func_000A3980` and absolute `REVERSEAPOC_ATTEMPT_DIR`/`REVERSEAPOC_ATTEMPT_NOTES` under `build/driver/canary/<run>/`. PASS needs the `uv run --frozen reverseapoc attempt context` call to be made, absent from `permission_denials`, and `<attempt dir>/context.md` to exist. Fixture `canary_wrapper_denied.jsonl` FAILs naming the wrapper. Tests: `test_canary_env_names_the_claim_with_absolute_paths`, `test_canary_wrapper_denied`.
2. **Orchestrator ruling F13: one JSON document on stdout.** Every preflight command's argv, exit, stdout and stderr go to `build/driver/<run>/preflight.log`; text-mode progress goes to stderr; refusals, the dry run, the canary and the night each print one document. Test: `test_json_mode_stdout_is_one_document_and_noise_goes_to_the_log` (fake runners print noise on both streams).
3. **Orchestrator ruling F14: what "dirty" means.** `git status --porcelain=v1 -z --untracked-files=all` not empty; the refusal names the paths. Test: `test_preflight_refuses_a_dirty_tree_naming_the_paths`.
4. **Orchestrator ruling F7 (consumer): the partial-gate argv** is `docker compose run --rm -T build uv run --frozen reverseapoc gate EXE/UNIT --partial --src <repo-relative POSIX path> --attempts N --json`. Test: `test_drive_builds_the_partial_gate_and_lint_argv`.
5. **Orchestrator ruling F30: `exe` is the config stem** in the dry-run JSON (`ufo2p` / `tacp`). Test: `test_dry_run_prints_the_pilot`.
6. **Orchestrator ruling F32 (docs): both hook layers fail closed.** docs/workflow.md names the command `uv run --frozen --project "$CLAUDE_PROJECT_DIR" python -I -m reverseapoc.hooks ... || exit 2`, says a missing uv, a missing module or an unset/foreign `CLAUDE_PROJECT_DIR` blocks every Edit and Write, and lists the three known limits (Bash not covered by the always layer, Bash-made hard links, other checkouts over-denied).
7. **06-12 re-review canary items:** (a) per-tool hook timing cannot be observed by the canary and is an open assumption (below); (b) `CLAUDE_PROJECT_DIR` is checked indirectly: the matching hook gates every tool (matcher `*`, `--project "$CLAUDE_PROJECT_DIR"`, fails closed), so an allowed wrapper call plus the hook denials prove the hooks ran in a project that holds `reverseapoc.hooks`; that it is this very checkout stays partly open (below).
8. **06-23 security notes: preflight compiles tools/ and configure.py** (`uv run --frozen python -m compileall -q tools configure.py`), after the host `uv sync --locked`. Tests: `test_preflight_regenerates_listings_and_drafts` (order), `test_compiled_bytecode_is_not_rewritten_by_an_isolated_import` (a `python -I` import writes no .pyc after compileall; the uncompiled control does).
9. **06-23 notes: the `.venv`/`.claude` fingerprint stays stable; PYTHONDONTWRITEBYTECODE; `--no-sync` decided with hooks.ATTEMPT_PREFIX.** The session env already sets PYTHONDONTWRITEBYTECODE=1 (06-23; the canary env carries it, tested). `--no-sync` is not added (key decision): the preflight syncs and compiles first, and the canary's fingerprint check is the real-host test that a session's wrapper calls change nothing fingerprinted (`test_canary_fails_when_the_session_changes_what_the_driver_fingerprints`).
10. **06-23 fix round 4 consumer contract:** exit codes 0 / 1 / 2 come from `DriveReport.exit_code` unchanged; the real end-of-run checks go through `Deps.end_of_run` (`finish`), which `_Night.run` calls before the ENDED record; run() is not reordered; failures land in `checks_failed`; `uncommitted` is untouched 06-23 behaviour, and docs/workflow.md says the next drive refuses until the owner commits or restores it. Tests: `test_end_of_run_order`, `test_a_failing_end_of_run_check_is_recorded_and_exits_1`.
11. **06-23 notes: unknown event types are a canary check.** An event whose type is outside system/assistant/user/result/rate_limit_event and which carries any key containing "error" is a FAIL; one without is listed as ignored. Fixture `canary_unknown_error.jsonl`, test `test_canary_fails_on_an_unknown_event_type_carrying_an_error`.
12. **06-23 notes: the canary must not touch pinned paths.** The canary measures, through a probe `_Night`, the same pinned bytes and fingerprint a night does, before and after the session; any change is a FAIL naming the paths.
13. **Notes for 06-06, 06-15 and 06-25:** `ghidra-export EXE --drafts ADDR ...` is used as it is (hex addresses, one call per EXE); `units --write-src` logic is reused in-process through `units.scaffold_unit`/`write_unit_source` with the committed CSVs.
14. **Security findings 06-23 (containment):** the canary writes only its attempt dir under build/driver/ and the preflight log; it never restores or quarantines (the driver's containment is untouched), and it leaves the tree for the owner to inspect, with the next preflight refusing a dirty tree.

**Auto-fixed / added:**

15. **[Rule 2 - Missing critical] The canary also runs `attempt check`.** Found after Task 2: a container check during a session writes Python bytecode into the bind-mounted tools/ if the container's interpreter rejects the host's .pyc, which would stop the pilot's first night on the fingerprint; 06-15 also left the first real `docker compose run -T --name` check unproven. The prompt gains a fifth call on the matched claim; PASS needs it allowed and its checks.jsonl line at exit 0. A raising session is now a FAIL line with the tree still measured, never an escape. `CANARY_TIMEOUT_S` 1200. Commits 8f78d1e, 53ca925, 56827a3.
16. **[Rule 2 - Missing critical] A real-file test of the verb's world** (`tests/test_drive_real.py`, a file outside files_modified): `load_world` on both real EXEs and the real pilot over the committed config/. A probe with the exclusion removed puts both Phase 5 matches into the pilot, so the test can fail. It skips only with the existing `orig/<name> not present` reason (no new skip reason, R-A). Commit dc3c34f.
17. **[Plan reading] picker.py joins the files.** rulings ## 06-15 left the picker's TODO(06-25) for this plan: `STATUS_MATCHED` now imports `status.MATCHED` (refactor d7e6cb1).
18. **[Plan reading] Two more synthetic fixtures** than the plan lists: `canary_wrapper_denied.jsonl` (ruling F12) and `canary_unknown_error.jsonl` (06-23 notes).
19. **[Rule 2 - Fail closed] Extra refusals, each tested:** `host sync`, `compile` and `asm` failures refuse; a world-load failure refuses (`world`); a pilot that cannot be filled refuses (`picks`); a run id outside `[A-Za-z0-9_.-]+` refuses; `ghidra-export` exit other than 0/1 refuses (`drafts`).

**Total deviations:** 14 rulings and notes applied, 5 auto-fixed or plan-reading deviations. **Impact:** the canary does a little more than the plan's four calls (one container check) and a real-file test was added outside files_modified; everything else stays inside the plan's truths.

## Open canary assumptions for the owner (06-26)

- **permission_denials shape.** The canary reads the last result event's `permission_denials` as `{tool_name, tool_use_id, tool_input}` (Agent SDK SDKPermissionDenial), with paths judged against the checkout and the init `cwd`. If hook denials do not show up there on the real CLI, the canary FAILs (fail closed) and the shape must be checked in the transcript at `build/driver/canary/<run>/ufo2p/func_000A3980/attempt-1/transcript.jsonl`.
- **(a) Hook timing per tool (06-12 re-review).** Not observable by the canary. If Claude Code ran all PreToolUse hooks of one turn before any tool, two Edits that are each placeable on the original file could compose `_asm`. Behind it: the always layer denies any src/ Edit whose old text is not in the file verbatim, and the gate decides every match, but no commit-time inline-asm scan exists. A manual probe would need two Edits in one assistant message on a scratch unit.
- **(b) CLAUDE_PROJECT_DIR.** The canary shows the hooks ran in a project holding reverseapoc.hooks (denials plus an allowed wrapper call), not that it is this checkout rather than another one with hooks.py. The preflight's main-checkout check and the session's cwd at the checkout root make a foreign value unlikely.
- **`uv run --frozen` without `--no-sync`.** Assumed to write nothing to `.venv` once the preflight's host `uv sync --locked` ran; the canary's fingerprint check proves or refutes it.
- **Container bytecode.** Assumed: the container's Python 3.14 accepts the host-compiled .pyc in the bind mount and writes none during `attempt check`; the canary's fifth call and fingerprint check prove or refute it.
- **Known event types.** system, assistant, user, result, rate_limit_event; any other type that carries an error key fails the canary.
- **The claude executable** is `shutil.which("claude")`; assumed to be the native `claude.exe` from `claude install`. A `.cmd` shim may not start under an argv-list Popen.
- **Compose project name** is the checkout directory name normalized (`reverseapoc`). If the owner sets `COMPOSE_PROJECT_NAME`, the cleanup filter finds no container (no error).
- **A leaky canary leaves its files** (for example tools/x.py) for inspection; restore them before the pilot.

## Known Stubs

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: process-spawn | tools/reverseapoc/driver.py | The verb runs docker, uv, `claude --version` and the session as argv lists (no shell); the end-of-run ninja step runs one fixed script through the container's `bash -lc` |
| threat_flag: container-removal | tools/reverseapoc/driver.py | `docker rm -f` on containers matching the compose project label and the attempt's name prefix |

## Issues Encountered

- The harness refused compound shell commands that mention git or worktrees (heredocs, python fed through stdin naming git); file splices ran as small scripts in the scratchpad and git steps as plain commands.

## User Setup Required

None beyond 06-26's checkpoint (CLI upgrade to major 2, at least 2.1.302).

## Next Phase Readiness

- 06-26: the owner runs `uv run reverseapoc drive --dry-run`, then `uv run reverseapoc drive --canary`, then `uv run reverseapoc drive --max-sessions 40 --target-matched 10`, in the main checkout on a clean tree.
- No tick-rate finding (OpenApoc #997) in this plan.

## Self-Check: PASSED

- Files exist: tools/reverseapoc/driver.py, tools/reverseapoc/cli.py, tools/reverseapoc/picker.py, docs/workflow.md, tests/test_drive.py, tests/test_drive_real.py and the four canary fixtures.
- Commits f0c241d, 69cedc1, d7e6cb1, eff0014, 77a0d6a, 5e74574, ca68c96, c2b0a9c, 8f78d1e, 53ca925, 56827a3, dc3c34f are on this branch (`git rev-list --count d86e673..HEAD` = 12 before this SUMMARY).
- No modification to STATE.md, ROADMAP.md, orig/, config/, status.csv, hooks.py or the build scripts.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
