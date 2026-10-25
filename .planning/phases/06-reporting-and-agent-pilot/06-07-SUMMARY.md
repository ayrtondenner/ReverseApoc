---
phase: 06-reporting-and-agent-pilot
plan: 07
subsystem: tooling
tags: [python, compiler, cc-log, watcom, docs, security]

requires:
  - phase: 06-02
    provides: "fileio.write_atomic as the one atomic writer (compiler.py imports it)"
provides:
  - "cc refuses a --log naming an existing directory before the compile (DI-12, IN-08)"
  - "cc opens <log>.lock before the gate and the compile; an OSError there is a CompilerError (DI-13, IN-09 option b)"
  - "docs/toolchain.md cc.log bullet: --log must name a file, both platforms' messages, device branch covers directories (DI-11, backlog 999.1)"
  - "Phase 4 info items IN-10..IN-13 closed (DI-14..DI-17); PROJECT_INCLUDE removed; whole-name marker match (05-REVIEW row 4)"
  - "real codegen and stub assertions print booleans, names, sizes and SHA-1s, never object bytes (T-04-17; the stub half was completed in fix round 1, e23cbcc, and proven by mutation); 10.5 env-injection and cleanup proofs run unskipped on the host (DI-23)"
  - "config/watcom.toml notes on lines 37 and 106 say LX, in one owner-authorized commit 28342e1 (DI-33, D-43, D-47)"
  - "toolchain.md -s and -fpi scratch-check claims labelled (T-04-36)"
affects: [06-12, 06-21, cc, check, gate]

actuals:
  tokens: 6971  # chars/4 over `git diff a9e13ed..fdf0e0a` (27,885 chars)
  tasks: 3
  commits: 6
plan_head_before: a9e13ed54f72aafb7389d1415f1707e516d1581d
plan_head_after: fdf0e0a7048fea98f015608918fe30256590f98a

tech-stack:
  added: []
  patterns:
    - "Pre-compile probes: anything the post-compile log append needs (a file name, a non-directory, an openable lock sidecar) is checked before the gate, so a good compile never ends as a failed edge"
    - "Real-test assertions compare dataclasses of booleans plus SHA-1s, never raw object bytes"

key-files:
  created: []
  modified:
    - tools/reverseapoc/compiler.py
    - tests/test_compiler.py
    - tests/test_cc_log.py
    - tests/test_cli.py
    - tests/test_compiler_real.py
    - tests/test_stub_real.py
    - docs/toolchain.md
    - config/watcom.toml

key-decisions:
  - "The lock probe runs after the path/output checks and before the gate, so a refused log never reaches the banner probe; it creates the log's directory and the empty sidecar that the append would create anyway"
  - "A device log (exists, not a regular file) is not probed, so /dev/null and NUL keep the lock-free branch"
  - "Unlogged -s and -fpi evidence is labelled '(scratch check, not logged)' rather than re-measured"

patterns-established:
  - "A test that asserts something is absent also proves its matcher finds the thing when present (test_marker_extern_pattern_sees_a_referenced_marker)"

requirements-completed: [AGT-05, AGT-06]

coverage:
  - id: D1
    description: "--log naming an existing directory, or with an unopenable <log>.lock, is refused before the runner and the stale-object unlink; a device log keeps the device branch"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_log_naming_a_directory_is_refused_before_the_compile"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_unwritable_lock_is_refused_before_the_compile"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_device_log_still_works"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/toolchain.md cc.log bullet states the refusals and quotes both platforms' messages (backlog 999.1)"
    verification:
      - kind: other
        ref: "grep -q 'Is a directory' docs/toolchain.md && grep -q 'Permission denied' docs/toolchain.md"
        status: pass
    human_judgment: true
    rationale: "The container's [Errno 21] message is standard Linux behaviour and was quoted by the Phase 4 UAT, but it was not re-observed here (no docker from a worktree); a reader should confirm the prose is accurate"
  - id: D3
    description: "IN-10..IN-13 test and docstring fixes; PROJECT_INCLUDE removed; whole-name marker regex"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_cc_log.py tests/test_cli.py tests/test_compiler.py"
        status: pass
      - kind: integration
        ref: "tests/test_stub_real.py#test_marker_extern_pattern_sees_a_referenced_marker"
        status: pass
    human_judgment: false
  - id: D4
    description: "DI-23: 10.5/10.6/11.0 env-injection and cleanup real proofs run unskipped on the host; assertions byte-free"
    requirement: AGT-05
    verification:
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom uv run pytest -v -rs tests/test_compiler_real.py tests/test_stub_real.py (21 passed, 0 SKIPPED)"
        status: pass
    human_judgment: false
  - id: D5
    description: "config/watcom.toml lines 37 and 106 say LX in commit 28342e1 (2 -note / 2 +note lines, message quotes the 2026-10-24 authorization)"
    verification:
      - kind: other
        ref: "git show --format= --numstat 28342e1 -> '2 2 config/watcom.toml'; uv run pytest -q tests/test_watcom.py tests/test_compiler.py"
        status: pass
    human_judgment: true
    rationale: "A protected manifest changed under an owner authorization; the owner should see the commit"
  - id: D6
    description: "toolchain.md -s 'most code' and -fpi same-object claims carry '(scratch check, not logged)'"
    verification: []
    human_judgment: true
    rationale: "Whether the labels are placed on the right sentences is a reading judgment"

duration: 70min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 07: cc --log refusals, Phase 4 review closures and the LX note fix Summary

**`reverseapoc cc` now refuses a directory `--log` and an unopenable `<log>.lock` before the gate and the compile. The Phase 4 IN-10..IN-13 test and docstring items are closed. The real 10.5 proofs run on the host with assertions that print no object bytes. The two config/watcom.toml notes say LX, in the single commit the owner authorized (28342e1).**

Execution context nonce: 8587be25404e1913

## Performance

- **Duration:** about 70 min
- **Started:** 2026-10-25T01:30Z (approximate; first commit 711b829 at 02:32:54Z)
- **Completed:** 2026-10-25T02:40:09Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- `_check_log_name` refuses an existing directory (`--log X is a directory; name a file in it`). The new `_probe_log_lock` opens `<log>.lock` in `"a+b"`, the way `_log_lock` will, before the gate. An OSError there becomes a CompilerError that quotes the OS message. Device logs are not probed. A good compile can no longer end as a failed ninja edge that leaves its object behind (DI-12, DI-13).
- The docs/toolchain.md cc.log bullet now says `--log` must name a file. It lists what is refused before the compile and quotes `[Errno 21] Is a directory` (container) and `[Errno 13] Permission denied` (Windows host, observed here). It also says `_append_log`'s device branch covers directories (DI-11, backlog 999.1).
- IN-10: `cc_root` fails if `rmtree` could not remove the directory, and `_reap`'s docstring says it reaps only the `cc` processes. IN-11: the `/dev/null` sidecar test fails instead of skipping and removes any sidecar it created. IN-12: `_append_log`'s docstring names the Windows host. IN-13: the CLI refusal test writes the object first and checks it survives.
- `PROJECT_INCLUDE` is removed; nothing in tools/, tests/ or configure.py read it. test_stub_real.py now matches the whole marker extern name (`_?INCLUDE_ASM_func_[0-9A-F]{8}_?`, fullmatch) instead of a substring. A new test shows the pattern matches a referenced marker as Watcom 10.6 spells it: `_INCLUDE_ASM_func_00012000`.
- DI-23: the real tests for 10.5, 10.6 and 11.0 ran on the host against the main checkout's Watcom trees: 21 passed, 0 skipped. The codegen checks now compare a `Codegen(and_mask, movzx, sha1)` dataclass. The stub tests assert on a `StubFacts` dataclass (names, `_TEXT` size and SHA-1). A failure therefore prints booleans, names and hashes, never object bytes (T-04-17). Correction from fix round 1: the first version (1b34ae3) still printed bytes in two ways, through `len(_text(module))` and through any assert on an `omf.Module`, whose repr holds the segment data. Commit e23cbcc fixed both, and fifteen scratch mutations showed it (see Fix round 1).
- D-43/D-47: commit 28342e1 changes only the two `note` values (2 lines removed, 2 added, one file). Its message quotes the owner's 2026-10-24 authorization.
- T-04-36: the `-s` "most code" count, the `-fpi` same-object claim and the `-fpi`/`-fpi87` record equality each carry "(scratch check, not logged)".

## Task Commits

1. **Task 1 (tracer, TDD): --log refusals before the compile.** RED `711b829` (test), GREEN `b328679` (fix).
2. **Task 2 (TDD): IN-10..IN-13, dead constant, DI-23.** `1b34ae3` (test), `d24e14d` (fix).
3. **Task 3: the watcom.toml note fix and the evidence labels.** `28342e1` (docs; **the watcom.toml commit**), `fdf0e0a` (docs).

**Plan metadata:** the SUMMARY commit that follows this file.

## RED evidence (semantic assessment)

pytest's console report is not a format that `check tdd-red-evidence` supports, so RED was judged by reading the target assertions.

- Command: `uv run pytest -q tests/test_compiler.py -k "directory_is_refused or unwritable_lock or device_log_still"`. Exit 1: 2 failed, 1 passed.
- `test_log_naming_a_directory_is_refused_before_the_compile` failed with `PermissionError: [Errno 13] Permission denied: '...\logdir'`, raised from `_append_log` after the compile had run. That is exactly IN-08. Intended reason.
- `test_unwritable_lock_is_refused_before_the_compile` failed because the monkeypatched `PermissionError` came from `_log_lock`, after the compile, instead of a CompilerError before it. That is exactly IN-09. Intended reason.
- `test_device_log_still_works` passed at RED. It is a regression guard on existing behaviour: it fails if the new probe, or the lock, touches `_lock_path` for a device.
- Task 2's `test(06-07)` commit hardens existing tests; there is no new production behaviour. Those tests passed at commit time. To show the IN-13 test can fail, I moved `obj.unlink` in front of `_check_log_name` as a temporary change: both `test_cc_log_without_a_name_is_an_error_line` cases failed. I then reverted the change with `git checkout -- tools/reverseapoc/compiler.py`. The marker-pattern test shows `_marker_externs(...) == []` can fail, by finding a real marker extern.

## Files Created/Modified

- `tools/reverseapoc/compiler.py`: `_check_log_name` refuses directories; `_is_device` and `_probe_log_lock` added; the probe is called in `compile_rule` before the gate; docstrings for `compile_rule` and `_append_log` updated; `PROJECT_INCLUDE` removed.
- `tests/test_compiler.py`: the three Task 1 tests.
- `tests/test_cc_log.py`: the IN-11 `/dev/null` test.
- `tests/test_cli.py`: the IN-13 refusal test.
- `tests/test_compiler_real.py`: the IN-10 `cc_root` and `_reap` changes; the `Codegen` dataclass; byte-free codegen assertions.
- `tests/test_stub_real.py`: `MARKER_EXTERN` fullmatch; `StubFacts` and `_facts` (fix round 1, replacing `_text_sha1`); byte-free assertions; the referenced-marker test.
- `docs/toolchain.md`: the cc.log bullet (999.1) and three scratch-check labels.
- `config/watcom.toml`: lines 37 and 106, `LE` -> `LX` (commit 28342e1 only).

## Decisions Made

- The lock probe runs after the path and output checks and before `check_gate`. A refused log therefore never reaches the banner probe, and `runner.calls == []` holds. The probe creates the log's parent directory and the empty sidecar, which the post-compile append would have created anyway, and never deletes the sidecar. That matches the no-delete rule `_log_lock` documents.
- The `-s` and `-fpi` claims are labelled rather than re-measured. The plan allows either, and a re-measurement's log would sit under the gitignored build/, so a reader could not re-run it from the docs anyway.

## Deviations from Plan

### Orchestrator rulings applied

**Orchestrator ruling F18: a skip check that can fail.** Task 2's real verify ran pytest with `-v -rs` and failed on `grep -E "(test_env_injection_has_no_effect|test_compile_error_cleans_up)\[[^]]*\] SKIPPED"`. The run gave exit 0, 21 passed, 0 SKIPPED lines, and the six 10.5/10.6/11.0 cases PASSED. As a check, the grep was fed a synthetic `...test_env_injection_has_no_effect[10.5] SKIPPED` line and matched it, so it can fail.

**Orchestrator ruling F2 / R-A: one device test.** `test_device_log_still_works` is one test with no skip. It picks `NUL` on win32 and `/dev/null` otherwise, by `sys.platform`. It checks the device branch by replacing `compiler._lock_path` with a function that raises, so it fails on either platform if the probe or the lock touches a device's sidecar.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The REVERSEAPOC_WATCOM_DIR spelling in the real verify**
- **Found during:** Task 2 (DI-23 run)
- **Issue:** The worktree harness refused the plan's `$(git rev-parse --path-format=absolute --git-common-dir)` form. It also refused the literal main-checkout path and `$PWD`-based exports, because it reads "Gitprojects" in the path as a git invocation.
- **Fix:** I ran the same command with `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom`. That is the main checkout's tree, reached relative to the worktree root, pytest's cwd. The run read 10.5, 10.6 and 11.0 from it and the gate accepted all three. I also split Task 3's second verify into separate `git show --numstat` and `git show -s --format=%B` calls, with the same checks: `2 2 config/watcom.toml`, and the message contains `2026-10-24` twice.
- **Committed in:** no code change.

**2. [Rule 2 - Missing critical] Byte-free assertions in test_stub_real.py too**
- **Found during:** Task 2
- **Issue:** `assert _text(unit) == _text(control)` and `assert _text(module) == b""` would print object bytes on failure (T-04-17). This is the same defect as the codegen asserts, and the file is in this plan's list.
- **Fix:** I compare SHA-1s and lengths through `_text_sha1`. That was incomplete: `len(_text(module))` and asserts on `omf.Module` still printed bytes. Fix round 1 (e23cbcc) replaced it with `StubFacts`.
- **Committed in:** 1b34ae3

**3. [Rule 2 - Missing critical] Show the marker check can fail**
- **Found during:** Task 2 (05-REVIEW row 4)
- **Issue:** Replacing the substring match with a whole-name regex could make `_marker_externs(...) == []` pass forever if the regex missed Watcom's spelling.
- **Fix:** I added `test_marker_extern_pattern_sees_a_referenced_marker`. The real 10.6 compile emits `_INCLUDE_ASM_func_00012000`, and the regex matches it.
- **Committed in:** 1b34ae3

**4. [Rule 2 - Missing critical] Label the `-fpi`/`-fpi87` record equality too**
- **Found during:** Task 3
- **Issue:** The FPU row's claim that the LEDATA and FIXUPP records are equal comes from a 04-11 review-round comparison. 04-11-SUMMARY:275 says the calibration log shows only the default-library column, so the claim is unlogged in the same way.
- **Fix:** That sentence is labelled as well, which gives three labels in total.
- **Committed in:** fdf0e0a

---

**Total deviations:** 2 orchestrator rulings applied; 4 auto-fixed (1 blocking, 3 missing critical).
**Impact on plan:** None of these widens scope. Every file touched is in the plan's `files_modified`.

## Issues Encountered

- DI-23's premise that the 10.5 cases skip did not hold at this base. With the main checkout's trees, all three versions ran unskipped before any change; the baseline is in `build/06-07-real-before.out`, gitignored. The 04-SECURITY.md L122 observation ("still run for 10.6 and 11.0 only, RUNNABLE") is stale, and 06-21's paperwork can close it.
- `ruff format --check` flags compiler.py at lines this plan did not touch (`runner_prefix` signature, `except OSError, ValueError`). That is pre-existing, not a gate (`ruff check .` is green), and I left it alone.

## Follow-ups for later plans (not done here, outside this plan's files)

- docs/learnings.md L58 still says the watcom.toml notes "stay until the owner edits it". Commit 28342e1 has now made that edit.
- docs/matching.md:28 states the `-fpi`/`-fpi87` LEDATA/FIXUPP equality without the scratch-check label.
- 04-SECURITY.md L122: T-04-15/16 (10.5 now runs), T-04-17 (assertions byte-free since e23cbcc, proven by the build/06-07-mutation-*.out runs) and T-04-36 (labels added) can be closed by 06-21.

## Verification

- Task 1: `uv run pytest -q tests/test_compiler.py tests/test_cc_log.py`: 66 passed, 1 skipped (`POSIX-only: /dev/null and its directory /dev`). The grep for `Is a directory` and `Permission denied` in toolchain.md passed. The tracer gate (end-of-phase mode, `<automated>` only) re-ran the verify, it passed, and I continued.
- Task 2: the real verify per F18 gave 21 passed and 0 skipped. `uv run pytest -q tests/test_cc_log.py tests/test_cli.py tests/test_compiler.py`: 165 passed, 1 skipped. `grep -n PROJECT_INCLUDE tools/reverseapoc/*.py tests/*.py` prints nothing. The `/dev/null` test has no `pytest.skip(`.
- Task 3: exactly 2 `the real LX compiler`, 0 `real LE compiler`, and `tests/test_watcom.py tests/test_compiler.py` 156 passed. Commit 28342e1 numstat is `2 2 config/watcom.toml` and its diff is exactly two `-note` and two `+note` lines. The message contains `2026-10-24`.
- Before the change I ran `git grep -n "watcom.toml"` over tests/, tools/ and configure.py. Readers load its keys, `configure.CC_CONFIG` lists it as an implicit ninja input, and nothing hashes its bytes. config/targets.toml does not mention it and is unchanged (`git diff --stat a9e13ed HEAD` does not list it).
- Whole host suite: `uv run pytest -q` gave 1517 passed and 217 skipped (the real tests skip without orig/ in the worktree). `uv run ruff check .` reported "All checks passed!".

## User Setup Required

None.

## Next Phase Readiness

- 06-12, the always-on hooks, can protect config/watcom.toml from the moment it lands; the only authorized edit (28342e1) is done.
- 06-21 can close the 04-SECURITY.md observations listed above.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/compiler.py, tests/test_compiler.py, tests/test_cc_log.py, tests/test_cli.py, tests/test_compiler_real.py, tests/test_stub_real.py, docs/toolchain.md, config/watcom.toml
- FOUND commits on this branch: 711b829, b328679, 1b34ae3, d24e14d, 28342e1, fdf0e0a (`git rev-list --count a9e13ed..fdf0e0a` = 6)

## Fix round 1 (review-06-07, FIX_BASE 6b9d2b0)

| Finding | Fix | Commit | Proof |
|---------|-----|--------|-------|
| Important: `assert len(_text(module)) == 0` (test_stub_real.py:142) printed `_TEXT` bytes on failure. A grep of the other asserts found the same leak in every assert on an `omf.Module` (`module.publics`, `module.externs`, `_publics(module)`, `_marker_externs(module)`): pytest prints the Module repr, whose segments hold `data: bytes` | `_compile` returns `StubFacts(publics, externs, marker_externs, text_size, text_sha1)` and every stub assert reads it. The empty-segment check is `(text_size, text_sha1) == (0, sha1(b""))`, and the referenced-marker test pins `("_INCLUDE_ASM_func_00012000",)`. test_compiler_real.py's asserts already worked on `Codegen`, `CompileResult` (no bytes field), names and SHA-1s | e23cbcc (test) | 15 scratch mutations, each assertion flipped, over 5 runs: build/06-07-mutation-1.out (8 failed: 4 stub, 3 env_injection, 1 two_sources) and -2..-5 (3, 2, 1, 1 failed). The failures print only tuples of names, ints, SHA-1s, `StubFacts(...)` and `Codegen(...)`. A grep for a `b'` or `b"` literal finds 0 lines in every file. Each mutation was reverted with `git checkout -- <file>`, and `git status` is clean |
| Minor 1: the probe and `_log_lock` each spelled `open(..., "a+b")` | `_open_lock(log)` is the only opener of the sidecar, and both use it | 45d1e94 (refactor) | with the opener's mode changed to `rb`, 40 compiler/log tests fail; after the revert, 68 pass |
| Minor 2: on POSIX, `--log new/..` with no `new` passed `is_dir()`, the probe created `new`, and the append failed after the compile | `_check_log_name` refuses a name of `..` like an empty name ("names no file"), before anything is created. The docs bullet lists it | b8d1f75 (RED), 7a5178a (fix) | RED: `test_log_ending_in_dotdot_names_no_file[parts0]` (`new/..`) and `[parts1]` (`..`) failed on the host, because Windows refused them via `is_dir()` as "is a directory", not by name. GREEN: both pass and `new` is not created |
| Minor 3: build/06-07-real.out was older than the last code commit | re-ran `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom uv run pytest -v -rs tests/test_compiler_real.py tests/test_stub_real.py` after 45d1e94 | none | 21 passed, 0 SKIPPED, 6 env_injection/cleanup cases PASSED. The file was written at 23:53:33, after 45d1e94 at 23:53:19 |
| Minor 4: the mutation proof was prose only | this round's mutation outputs are kept as build/06-07-mutation-1..5.out (gitignored) | none | as above |

After the round: `uv run pytest -q` gives 1519 passed and 217 skipped (the real tests skip in the worktree without the env var). `uv run ruff check .` reports "All checks passed!". The branch has 11 commits from a9e13ed to 45d1e94, 4 of them in this round, plus this SUMMARY update.

Execution context nonce: 8587be25404e1913

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
