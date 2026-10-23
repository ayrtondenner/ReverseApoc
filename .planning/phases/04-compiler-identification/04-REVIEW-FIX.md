---
phase: 04-compiler-identification
fixed_at: 2026-10-23T14:52:45Z
review_path: .planning/phases/04-compiler-identification/04-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-10-23T14:52:45Z
**Source review:** .planning/phases/04-compiler-identification/04-REVIEW.md (incremental review of plan 04-13 / G-04-2)
**Iteration:** 1

This report replaces the one from the previous review round. That report is still in git history.

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03; IN-01..03 are out of scope under `critical_warning`)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: A `--log` without a final name component (`.`, `C:/`, `/`) now crashes with an uncaught ValueError, after the compile has run

**Files modified:** `tools/reverseapoc/compiler.py`, `tests/test_cli.py`
**Commit:** 37b104f
**Applied fix:** Added `_check_log_name(log)`, which raises
`CompilerError("--log <log> names no file; the lock sidecar is <log>.lock")` when `log.name` is
empty. `compile_rule` calls it right after `_check_object_name(obj)`. That is before the gate and
the runner, so a bad `--log` never compiles and never writes an object. `_lock_path`, `_log_line`,
`DEFAULT_LOG` and the `--log` option are unchanged.

**Test-first evidence:**
- New test `test_cc_log_without_a_name_is_an_error_line[.]` and `[/]` in `tests/test_cli.py`. It
  uses the existing `cc_workspace` fake-compiler fixture, so no real Watcom is needed. It asserts:
  - `main` returns 1;
  - stderr is a single line that starts `reverseapoc cc: error:`, names `--log`, and has no
    `Traceback`;
  - the runner was never called (`ws.runner.calls == []`);
  - no object exists.
- RED (before the fix): `2 failed`. Both failed with
  `ValueError: WindowsPath('/') has an empty name` (and the same for `.`), raised from
  `_lock_path` <- `_log_lock` <- `_append_log`, after the compile. That is the reviewer's
  failure.
- GREEN (after the fix): `2 passed`.

### WR-02: `--log /dev/null` (and any log in a directory the user cannot create files in) now fails a successful compile

**Files modified:** `tools/reverseapoc/compiler.py`, `tests/test_cc_log.py`, `docs/toolchain.md`
**Commit:** 83053f9
**Applied fix:** This is the owner's option (a). In `_append_log`, a log that exists and is not a
regular file (`log.exists() and not log.is_file()`) is written without the lock: /dev/null,
a FIFO, a console. It is opened in append mode, written and closed, and no `<log>.lock` is
created. Every other log keeps `with _log_lock(log):` exactly as before: the log is opened,
written and closed inside the lock. The docstring now says this too.

The cc.log bullet in `docs/toolchain.md` ("wibo" section) now says two more things:
- the log's directory must be writable, because `<log>.lock` is created there;
- a log that is a device (such as `/dev/null`) is appended to without the lock and gets no
  sidecar.

The exact phrases `cc.log.lock` and `same log at the same time is not supported` are still
there. The 04-13 plan's grep for them passes.

**Test-first evidence:**
- `test_a_device_log_is_appended_without_the_lock` is portable. It appends to
  `Path(os.devnull)`, which is `nul` on Windows and `/dev/null` on POSIX; on both, the path
  exists and is not a regular file. `compiler._log_lock` is replaced by a stub that raises, so
  the test fails if the lock is taken.
- `test_dev_null_log_works_and_leaves_no_sidecar` is POSIX-only. It is skipped on win32 with
  the reason "POSIX-only: /dev/null and its directory /dev". It appends to the real `/dev/null`
  and asserts that `/dev/null.lock` does not exist afterwards. If that file already exists, the
  test skips instead.
- RED (before the fix):
  - Windows host: `1 failed, 1 skipped`, with `AssertionError: took the sidecar lock for nul`.
  - Container (`reverseapoc-build:local`, user `dev`): `2 failed`. Both raised
    `PermissionError: [Errno 13] Permission denied: '/dev/null.lock'`, which is the failure the
    reviewer reproduced.
- GREEN (after the fix):
  - Windows host: `1 passed, 1 skipped`.
  - Container: all of `tests/test_cc_log.py` gives `7 passed, 2 skipped` (the two skips are the
    Windows-only msvcrt tests), and `ls /dev/null.lock` reports no such file.

### WR-03: The new concurrency tests wait on child processes with no timeout, and the real parallel test leaks processes on its first failure

**Files modified:** `tests/test_cc_log.py`, `tests/test_compiler_real.py`
**Commit:** c01df4c
**Applied fix:**
- `tests/test_cc_log.py`:
  - New constant `WAIT_SECONDS = 120`. Its comment says it is far above the measured 2.7 s for
    1600 appends.
  - New helper `_reap(procs)`: it kills and waits for every process that is still running.
  - `test_concurrent_appends_keep_every_line` now starts its writers inside `try`, waits on each
    with `p.wait(timeout=WAIT_SECONDS)`, and calls `_reap(writers)` in `finally`.
  - The killed-holder test's `finally` loop did the same thing inline. It now calls `_reap(procs)`
    instead, with no change in behaviour.
- `tests/test_compiler_real.py`:
  - New constant `CC_WAIT_SECONDS = 300`.
  - New helper `_start_cc(obj, options)`, the existing Popen call moved out unchanged.
  - New helper `_reap(procs)`: it kills, then calls `communicate()` so the stderr pipes are
    drained.
  - `test_parallel_cc_keeps_one_log_line_per_compile` now does four steps:
    1. starts its `cc` processes inside `try`;
    2. collects stderr with `communicate(timeout=CC_WAIT_SECONDS)`;
    3. reaps in `finally`;
    4. only then asserts each return code.
  - So the first failing return code can no longer leave up to 15 `cc` processes running.

**Evidence:**
- Scratch harness (not committed): one process held the log lock for good, and
  `test_concurrent_appends_keep_every_line` ran with `WAIT_SECONDS` patched to 2. Result:
  `TimeoutExpired after 2 s; writers started: 16; still running: []`. The test fails instead of
  hanging, and no writer is left behind.
- The real parallel test passed in the worktree when pointed at the main checkout's Watcom trees,
  read-only, through `REVERSEAPOC_WATCOM_DIR`: `1 passed`.

This finding was not test-first: the change is to test code only, and the owner's TDD
instruction covered WR-01 and WR-02.

## Verification

Every gate ran inside the isolated worktree
`.claude/worktrees/rf-04-<pid>-<epoch>`, on branch `gsd-reviewfix/04-<pid>`. That worktree is
gone now: it was removed after the fast-forward to `main`. The worktree had no `third_party/`, so
the real-compiler tests skipped there, except the one parallel run listed under WR-03.

| Check | Where | Result |
|---|---|---|
| `uv run pytest -q tests/test_cc_log.py tests/test_compiler.py tests/test_cli.py` | Windows host, worktree | 158 passed, 1 skipped |
| same three files | container (`docker run` with the worktree mounted at /work and `reverseapoc_uv-venv` mounted read-only, `uv run --no-sync`) | 157 passed, 2 skipped |
| `uv run pytest -q tests/test_hygiene.py` (together with the three files above, after WR-02) | Windows host, worktree | passed (202 passed, 4 skipped in total) |
| `uv run ruff check .` | Windows host, worktree, after each commit | All checks passed |
| `grep -q 'cc.log.lock' docs/toolchain.md && grep -q 'same log at the same time is not supported' docs/toolchain.md` | worktree | both found |

`docker compose` was not run from the worktree on purpose. It would have created a new compose
project with new named volumes, and root-owned `orig/` and `third_party/` directories in the
worktree. The orchestrator re-verifies on the main checkout, on the host and in the container.

`ruff format --check tools/reverseapoc/compiler.py` reports two existing differences, at the
`runner_prefix` signature and at `except (OSError, ValueError)`. Neither was touched by these
fixes, and the project gate is `ruff check`, which passes.

None of these were touched: `_log_line`, `DEFAULT_LOG`, the `--log` option, the existing
assertions in `tests/test_compiler.py` and `tests/test_cli.py`, `pyproject.toml`, `uv.lock`,
`orig/`, `third_party/`, `config/*.toml` and the Docker files. No dependency was added.

---

_Fixed: 2026-10-23T14:52:45Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
