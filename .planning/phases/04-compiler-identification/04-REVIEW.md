---
phase: 04-compiler-identification
reviewed: 2026-10-23T01:41:29Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - docs/learnings.md
  - docs/toolchain.md
  - tests/test_cc_log.py
  - tests/test_compiler_real.py
  - tools/reverseapoc/compiler.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 4: Code Review Report (incremental, gap-closure plan 04-13 / G-04-2)

**Reviewed:** 2026-10-23T01:41:29Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

This is an incremental re-review of the 04-13 changes since `56ef81b`: the sidecar OS lock in
`tools/reverseapoc/compiler.py` (`_lock_path`, the platform `_try_lock`/`_acquire`/`_release`,
`_log_lock`, `_append_log`), the new `tests/test_cc_log.py`, the new
`test_parallel_cc_keeps_one_log_line_per_compile`, the toolchain bullet and the 2026-10-22
learning. Older code in these files was dispositioned in the previous review round
(04-REVIEW-FIX.md, 04-REVIEW-DISPOSITION.md) and is not re-reported here.

The core mechanism is sound. The lock is taken before the log opens and released after it
closes. The win32 path uses only `LK_NBLCK` and seeks to byte 0 before both the lock and the
unlock. Locks are per handle (win32) and per open file description (flock), so threads in one
process exclude each other too. The child compile runs before the lock fd exists, so no lock fd
leaks into the child. The tests reach the helpers through module attributes as the plan says.

The defects are in the edges the lock adds. The sidecar path is derived and created *after*
the compile has run. That turns two `--log` values into failures that did not exist before:
- `--log .` now ends in an uncaught `ValueError` traceback. This is the same class as the
  `-o .` bug fixed under the previous WR-01.
- `--log /dev/null` in the container used to work and now exits 1 after a successful compile.

Both were reproduced. The new concurrency tests also wait on child processes with no timeout.
The lock deliberately has no deadline, so a lock regression would hang the gate instead of
failing it.

## Warnings

### WR-01: A `--log` without a final name component (`.`, `C:/`, `/`) now crashes with an uncaught ValueError, after the compile has run

**File:** `tools/reverseapoc/compiler.py:417-418` (`_lock_path`), reached from `:458` and `:530`
**Issue:** `_lock_path` returns `log.with_name(log.name + LOCK_SUFFIX)`. `PurePath.with_name`
raises `ValueError` when `log.name` is empty, and `ValueError` is not in `cli._ERRORS`
(cli.py:473-486). Before 04-13, `log.open("a")` on `.` raised an `OSError`
(PermissionError/IsADirectoryError), which `main` turned into a one-line
`reverseapoc cc: error: ...`. Now it is a traceback. It also only surfaces at
`_append_log(log, result)` (:530), after the compiler ran and the object was written.
Reproduced on the host:

```
compiler._append_log(Path('.'), r)   -> ValueError WindowsPath('.') has an empty name
compiler._append_log(Path('C:/'), r) -> ValueError WindowsPath('C:/') has an empty name
```

This is the same failure class as the `-o .` ValueError fixed under the previous WR-01
(`_check_object_name`), now reintroduced through the log path.
**Fix:** Refuse the log path up front, next to `_check_object_name`, so a bad `--log` never
reaches the runner and always maps to a `CompilerError`:

```python
def _check_log_name(log: Path) -> None:
    """The log's lock sidecar is `<log>.lock`, so the log needs a file name."""
    if not log.name:
        raise CompilerError(f"--log {log} names no file; the lock sidecar is <log>{LOCK_SUFFIX}")

# compile_rule, right after `log = Path(log) ...` / beside _check_object_name(obj):
_check_log_name(log)
```

Add a test that `main(["cc", ..., "--log", "."])` returns 1 with an `error:` line and no
traceback.

### WR-02: `--log /dev/null` (and any log in a directory the user cannot create files in) now fails a successful compile

**File:** `tools/reverseapoc/compiler.py:458` (`open(_lock_path(log), "a+b")`)
**Issue:** The lock creates `<log>.lock` beside the log, which needs create permission in the
log's directory, not just write permission on the log. The container runs as the non-root user
`dev` (docker/Dockerfile:139). `/dev/null.lock` cannot be created there. Verified:

```
$ docker compose run --rm --no-deps build bash -lc 'id -un; python3 -c "open(\"/dev/null.lock\",\"a+b\")"'
dev
PermissionError: [Errno 13] Permission denied: '/dev/null.lock'
```

So `reverseapoc cc ... --log /dev/null` worked before 04-13 and now does this:
1. the compile runs and writes the object;
2. the sidecar open raises `PermissionError`;
3. `main` prints an error and exits 1.

For a `ninja` build that means a failed edge with a valid object left on disk. The plan's
truth says "the --log option ... unchanged", and this is a behaviour change of that option.
The same applies to a pre-created, writable log in a read-only or sticky directory. (`--log NUL`
on Windows still works: `NUL.lock` maps to the device and locking it succeeds. That was checked.)
**Fix:** Pick one of these and pin it with a test:
- (a) take the lock only for regular files, since a device needs no append serialisation:
  ```python
  def _append_log(log: Path, result: CompileResult) -> None:
      log.parent.mkdir(parents=True, exist_ok=True)
      line = _log_line(result)
      if log.exists() and not log.is_file():   # /dev/null, a FIFO, a console
          with log.open("a", encoding="utf-8") as fh:
              fh.write(line)
          return
      with _log_lock(log):
          ...
  ```
- (b) check before the compile that the sidecar can be opened, raising `CompilerError`, so
  the failure happens before any object is written.

Also state the requirement in the toolchain bullet: "the directory of `--log` must be writable".

### WR-03: The new concurrency tests wait on child processes with no timeout, and the real parallel test leaks processes on its first failure

**File:** `tests/test_cc_log.py:130`, `tests/test_compiler_real.py:256-268`
**Issue:** The lock has no deadline, which the plan chose deliberately ("No timeout on the lock
wait"). That leaves these tests as the only guard against a lock that never comes free. Two
waits are unbounded:
- `[p.wait() for p in writers]` (test_cc_log.py:130);
- `proc.communicate()` (test_compiler_real.py:267).

pyproject.toml has no pytest-timeout. A regression would hang `uv run pytest` and the
`docker compose run` gate step forever instead of failing them. Examples: a re-entrant
`_log_lock` on the same log (the second handle spins or blocks against the first in the same
process), a lock that is never released, or a permanent EACCES (see IN-01). Only the
killed-holder test bounds its wait (`FREED_TIMEOUT_SECONDS`).

The real-compile test also asserts inside its loop:
`for proc in procs: _, err = proc.communicate(); assert proc.returncode == 0, err`. The first
non-zero exit aborts the test with up to 15 `cc` processes still running and unreaped. They
keep writing into `build/test-cc/<name>/`. On Windows, files they hold open make the next run's
`shutil.rmtree(..., ignore_errors=True)` leave the directory behind. `cc_root` then calls
`path.mkdir(parents=True)` without `exist_ok` (test_compiler_real.py:53), so the next run
errors in the fixture instead of reporting the real failure.
**Fix:** Bound every wait and reap in `finally`:

```python
WAIT_SECONDS = 120  # far above the measured 2.7 s for 1600 locked appends

# test_cc_log.py
try:
    assert [p.wait(timeout=WAIT_SECONDS) for p in writers] == [0] * WRITERS
finally:
    for p in writers:
        if p.poll() is None:
            p.kill(); p.wait()

# test_compiler_real.py
try:
    results = [(proc, proc.communicate(timeout=WAIT_SECONDS)[1]) for proc in procs]
finally:
    for proc in procs:
        if proc.poll() is None:
            proc.kill(); proc.communicate()
for proc, err in results:
    assert proc.returncode == 0, err
```

## Info

### IN-01: `_try_lock` retries on EACCES, but the UCRT maps more than lock contention to EACCES, and the spin has no deadline or diagnostic

**File:** `tools/reverseapoc/compiler.py:423-432`
**Issue:** The docstring (and threat T-04-43) says the call returns False "only on contention
(EACCES)". For `_LK_NBLCK`, the UCRT's `_locking` maps `GetLastError()` through
`__acrt_errno_map_os_error`. That table sends these to `EACCES`, not just
`ERROR_LOCK_VIOLATION` (33):
- `ERROR_ACCESS_DENIED` (5);
- `ERROR_SHARING_VIOLATION` (32);
- `ERROR_NETWORK_ACCESS_DENIED` (65);
- the whole 19-36 range.

A persistent non-contention failure in that set therefore spins forever, silently, at 1 ms. A
live but stuck holder does the same to every later `cc`: a `cc` paused in a debugger, or
suspended with Ctrl-Z in the container where `flock` blocks the same way. The plan accepted "no
timeout" on purpose, so this is recorded as information, not a defect.
**Fix:** Correct the docstring to "EACCES, which includes contention", or add a generous
deadline, e.g. `_LOCK_WAIT_SECONDS = 120`. On expiry, raise
`CompilerError(f"{sidecar} is still locked after {n} s; is another cc stuck?")` so the wait
fails with a message instead of hanging silently.

### IN-02: The sidecar comes from the `--log` spelling, not the file it names

**File:** `tools/reverseapoc/compiler.py:417-418`
**Issue:** Two `--log` values that reach the same file through a symlink, junction, hard link
or `subst` drive get different sidecars (`link.log.lock` vs `cc.log.lock`). Each then holds its
own lock, and the G-04-2 loss comes back with nothing to show it. A relative and an absolute
spelling of the same directory are fine, because they open the same sidecar file.
**Fix:** Derive the sidecar from the resolved log, `_lock_path(log.resolve())`, or document that
every writer must name the log by the same path.

### IN-03: The toolchain bullet states Windows-host facts as general ones

**File:** `docs/toolchain.md:321`
**Issue:** Two statements in the bullet hold only for a Windows host with Docker Desktop, and
the bullet says "the host" without qualifying it:
- "The host and a container writing the same log at the same time is not supported, because the
  two OS locks do not see each other". The two locks are `msvcrt` on NTFS and `flock` inside the
  Docker Desktop VM. On a Linux host with native Docker, host and container share one kernel,
  and `flock` excludes across them.
- "Lines written on the host end in CRLF". That comes from Windows text mode.

The learning (learnings.md:16) names the Windows host explicitly, but the bullet does not.
**Fix:** Say "the Windows host" in both sentences, e.g. "The Windows host and a container
writing the same log at the same time is not supported ...; lines written on the Windows host
end in CRLF".

---

_Reviewed: 2026-10-23T01:41:29Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
