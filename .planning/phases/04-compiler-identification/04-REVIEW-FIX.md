---
phase: 04-compiler-identification
fixed_at: 2026-10-23T16:22:01Z
review_path: .planning/phases/04-compiler-identification/04-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-10-23T16:22:01Z
**Source review:** .planning/phases/04-compiler-identification/04-REVIEW.md (incremental review of plan 04-13 / G-04-2)
**Iteration:** 1

This report replaces the earlier one for this review, which covered WR-01..03 under the
`critical_warning` scope. That report is still in git history (9b78244, 0c2a9b2). This run used
scope `all`. WR-01..03 were not re-applied: they were checked on HEAD (44b2a3e) and are carried
forward below with their original commits. IN-01..03 were fixed in this run.

**Summary:**
- Findings in scope: 6 (WR-01..03, IN-01..03)
- Fixed: 6 (3 carried forward, 3 in this run)
- Skipped: 0

## Fixed Issues

### WR-01: A `--log` without a final name component (`.`, `C:/`, `/`) now crashes with an uncaught ValueError, after the compile has run

**Files modified:** `tools/reverseapoc/compiler.py`, `tests/test_cli.py`
**Commit:** 37b104f (previous fix run; carried forward)
**Applied fix:** Added `_check_log_name(log)`, which raises
`CompilerError("--log <log> names no file; the lock sidecar is <log>.lock")` when `log.name` is
empty. `compile_rule` calls it right after `_check_object_name(obj)`, before the gate and the
runner, so a bad `--log` never compiles and never writes an object. Tests
`test_cc_log_without_a_name_is_an_error_line[.]` and `[/]` in `tests/test_cli.py` pin it (RED
2 failed with the reviewer's `ValueError`, GREEN 2 passed).
**Still fixed on HEAD:** `_check_log_name` is defined in `compiler.py` and called from
`compile_rule`; the tests pass in this run.

### WR-02: `--log /dev/null` (and any log in a directory the user cannot create files in) now fails a successful compile

**Files modified:** `tools/reverseapoc/compiler.py`, `tests/test_cc_log.py`, `docs/toolchain.md`
**Commit:** 83053f9 (previous fix run; carried forward)
**Applied fix:** The owner's option (a). `_append_log` writes a log that exists and is not a
regular file (`/dev/null`, a FIFO, a console) without the lock and without a sidecar. Every
other log keeps the lock as before. The toolchain bullet says the log's directory must be
writable and that a device log is appended to without the lock. Tests
`test_a_device_log_is_appended_without_the_lock` (portable) and
`test_dev_null_log_works_and_leaves_no_sidecar` (POSIX-only) pin it.
**Still fixed on HEAD:** the `log.exists() and not log.is_file()` branch is in `_append_log`, and
both bullet additions are still in `docs/toolchain.md` after this run's edits.

### WR-03: The new concurrency tests wait on child processes with no timeout, and the real parallel test leaks processes on its first failure

**Files modified:** `tests/test_cc_log.py`, `tests/test_compiler_real.py`
**Commit:** c01df4c (previous fix run; carried forward)
**Applied fix:** `WAIT_SECONDS = 120` and a `_reap` helper in `tests/test_cc_log.py`, and
`CC_WAIT_SECONDS = 300` and a `_reap` helper in `tests/test_compiler_real.py`. Every wait on a
child is bounded and every child still running is killed and reaped in `finally`. The return
codes are asserted only after that.
**Still fixed on HEAD:** `p.wait(timeout=WAIT_SECONDS)` with `_reap(writers)` in `finally`
(test_cc_log.py), and `communicate(timeout=CC_WAIT_SECONDS)` with `_reap(procs)` in `finally`
(test_compiler_real.py).

### IN-01: `_try_lock` retries on EACCES, but the UCRT maps more than lock contention to EACCES, and the spin has no deadline or diagnostic

**Files modified:** `tools/reverseapoc/compiler.py`
**Commit:** 1ad7417
**Applied fix:** Docstring only, by owner decision. The `_try_lock` docstring no longer says
"False only on contention (EACCES)". It now says:
- the call returns False on EACCES and raises any other error;
- EACCES is lock contention, but the Windows C runtime also sets it for access-denied,
  sharing-violation and network-denied errors, and `_acquire` retries those too;
- the wait has no deadline by design (plan 04-13), so a failure that persists, or a holder that
  never exits, makes it spin.

No timeout was added and the control flow is unchanged. No other comment or doc in `tools/`,
`tests/` or `docs/` said "only on contention". The learning (learnings.md:17) says the Windows
path "treats only EACCES as busy", which is accurate, so it was left alone.

### IN-02: The sidecar comes from the `--log` spelling, not the file it names

**Files modified:** `docs/toolchain.md`
**Commit:** 9f4f5bc
**Applied fix:** Documentation only, by owner decision; `_lock_path` is unchanged. The cc.log
bullet in the "wibo" section now says that every writer of one log must name it by the same
path, because the sidecar is derived from the `--log` spelling, not from the file it reaches. A
symlink, junction, hard link or `subst` drive to the same file gets a different sidecar, so a
different lock, and lines can be lost again. It also says that a relative and an absolute
spelling of the same path are fine, because they open the same sidecar. The sentence sits after
the WR-02 sentence about the writable directory and device logs.

### IN-03: The toolchain bullet states Windows-host facts as general ones

**Files modified:** `docs/toolchain.md`
**Commit:** 862159b
**Applied fix:** The bullet now says "The Windows host and a container writing the same log at
the same time is not supported ..." and "Lines written on the Windows host end in CRLF ...".
Nothing else in the bullet changed in this commit.

**Commit split for IN-02 and IN-03:** both touch the same bullet, but they are separate
sentences, so they went in as two atomic commits: IN-03 first (862159b), then IN-02 (9f4f5bc).

## Verification

The edits and gates ran inside the isolated worktree
`.claude/worktrees/rf-04-18022-1792772439`, on branch `gsd-reviewfix/04-18022` created from
`main` at 44b2a3e. After the gates passed, `main` was fast-forwarded to 9f4f5bc, the worktree was
removed, the temp branch was deleted and the recovery sentinel was removed. The worktree had no
`third_party/`, so the real-compiler tests skipped there.

| Check | Where | Result |
|---|---|---|
| `uv run python -c "import ast; ..."` on `compiler.py` and `uv run ruff check tools/reverseapoc/compiler.py`, after IN-01 | Windows host, worktree | parses; All checks passed |
| `grep -q 'cc.log.lock'`, `grep -q 'same log at the same time is not supported'` (after IN-03 and IN-02) and `grep -q 'directory must be writable'` (after IN-02) on `docs/toolchain.md` | worktree | all found |
| `uv run pytest -q tests/test_hygiene.py tests/test_cc_log.py tests/test_compiler.py tests/test_cli.py` | Windows host, worktree, after all three commits | 202 passed, 4 skipped |
| `uv run ruff check .` | Windows host, worktree, after all three commits | All checks passed |

The container was not run for this iteration: the changes are a docstring and two sentences in
a Markdown file. The orchestrator re-verifies on the main checkout, on the host and in the
container.

None of these were touched: `_lock_path`, `_try_lock`'s code, `_acquire`, `_log_line`,
`DEFAULT_LOG`, the `--log` option, any test, `pyproject.toml`, `uv.lock`, `orig/`,
`third_party/`, `config/*.toml` and the Docker files. The total diff from 44b2a3e is
`docs/toolchain.md` (1 line) and `tools/reverseapoc/compiler.py` (docstring, +6 -2).

---

_Fixed: 2026-10-23T16:22:01Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
