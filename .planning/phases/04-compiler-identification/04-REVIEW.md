---
phase: 04-compiler-identification
reviewed: 2026-10-23T19:19:02Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - docs/toolchain.md
  - tests/test_cc_log.py
  - tests/test_cli.py
  - tests/test_compiler_real.py
  - tools/reverseapoc/compiler.py
findings:
  critical: 0
  warning: 0
  info: 6
  total: 6
status: issues_found
---

# Phase 4: Code Review Report (incremental re-review of the 04-13 review fixes)

**Reviewed:** 2026-10-23T19:19:02Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found (Info only)

## Summary

This is the incremental re-review of the fixes for the 04-13 review (cc.log sidecar lock,
G-04-2). It covers `git diff 8a77590..HEAD` over the five files: commits 37b104f (WR-01), 83053f9
(WR-02), c01df4c (WR-03), 1ad7417 (IN-01), 862159b (IN-03) and 9f4f5bc (IN-02). Code that did not
change was dispositioned in earlier rounds and is not reported again.

Finding IDs continue from the highest ID in 04-REVIEW-DISPOSITION.md (IN-07). The disposition
gate drops a recorded row when its ID is reused by a different finding, so restarting at
WR-01/IN-01 would erase the recorded `fixed` decisions.

Verdict on each earlier finding:

- **WR-01 (fixed, correct).** `_check_log_name` (compiler.py:306-310) runs in `compile_rule`
  (:521) before the gate, the unlink and the runner. Path inputs with an empty name are refused
  with a `CompilerError`, which `cli._ERRORS` turns into one error line. Checked inputs: `.`,
  `/`, `C:` and `""` (argparse `""` becomes `Path(".")`). `test_cc_log_without_a_name_is_an_error_line`
  pins `.` and `/`, including `runner.calls == []`.
- **WR-02 (fixed for devices; the rest is documented, not fixed).** `log.exists() and not
  log.is_file()` (:487) sends `/dev/null`, `nul`, `CON`, FIFOs and directories past the
  sidecar. On this Windows 10 host `Path("nul")`, `Path("NUL")`, `Path("CON")` and
  `Path("nul.txt")` all report `exists() True` and `is_file() False`, so `os.devnull` takes the
  lock-free branch. `_log_lock` is looked up as a module global at call time, so the
  monkeypatched `_no_lock` test is valid. A regular log in a directory the user cannot create
  files in still fails after the compile; see IN-09.
- **WR-03 (fixed).** Every wait is bounded (`wait(timeout=WAIT_SECONDS)`,
  `communicate(timeout=CC_WAIT_SECONDS)`) and reaped in `finally`. `list.extend` over a
  generator keeps the items yielded before an exception, so a `Popen` failure in the middle of
  the spawn loop still reaps the earlier children. `errs` is only read after the `try` has
  completed normally. Two smaller gaps remain; see IN-10.
- **IN-01 (fixed).** The `_try_lock` docstring now says that EACCES covers access-denied,
  sharing-violation and network-denied errors as well as contention, and that the wait has no
  deadline.
- **IN-02 (fixed as documentation).** The toolchain bullet says every writer must name the log
  by the same path, and why.
- **IN-03 (fixed in the docs, not in the code docstring).** See IN-12.

Verification: `uv run pytest -q tests/test_cc_log.py tests/test_cli.py` gave 107 passed and 1
skipped (the POSIX-only `/dev/null` test) on the Windows host. `uv run ruff check tools tests`
is clean. The UAT observation about `--log <existing directory>` was reproduced on the host
through `_append_log` and is classified below (IN-08). No Critical or Warning issues were found.

## Info

### IN-08: `--log <existing directory>` compiles, then fails at the append and leaves the object behind (pre-existing, accepted at UAT)

**File:** `tools/reverseapoc/compiler.py:306-310`, `:487-490`, `:548`
**Issue:** The UAT observation is confirmed. It is not a regression of the 04-13 fixes.
1. `_check_log_name` only refuses a path with an empty name. `build/x/` and `..` have a name, so
   they pass.
2. The compile then runs. `_append_log` sees `exists() and not is_file()` and takes the device
   branch, so `log.open("a")` raises an `OSError` after the object is written.
3. `cli.main` maps that `OSError` to one error line and exit 1, and the object stays on disk.

Before 04-13, `_append_log` also opened the log only after the compile, so the behaviour is
pre-existing. The owner accepted it and moved a docs note to the backlog (ROADMAP Phase 999.1,
Test 5).

Reproduced on the Windows host:

```
_append_log(<scratch>/dirlog, r) -> PermissionError [Errno 13] Permission denied: '...\dirlog'
_append_log(Path(".."), r)       -> PermissionError [Errno 13] Permission denied: '..'
```

No `dirlog.lock` sidecar was left. Two details matter for the deferred docs note:
- On the Windows host the message is `[Errno 13] Permission denied`. `[Errno 21] Is a directory`
  is what the container prints. The backlog item quotes only the container's text.
- The `_append_log` docstring (:482-484) calls every existing non-regular file "a device",
  but a directory also takes that branch.

**Fix (optional, when the backlog item is done):** Refuse an existing directory before the
compile, next to the empty-name check:

```python
def _check_log_name(log: Path) -> None:
    if not log.name:
        raise CompilerError(f"--log {log} names no file; the lock sidecar is <log>{LOCK_SUFFIX}")
    if log.is_dir():
        raise CompilerError(f"--log {log} is a directory; name a file in it")
```

Otherwise, word the docs note so it covers both platforms' messages.

### IN-09: The WR-02 fix covers devices only; an unwritable log directory still fails a successful compile

**File:** `tools/reverseapoc/compiler.py:469`, `docs/toolchain.md:321`
**Issue:** WR-02 offered two options: (a) skip the lock for devices, or (b) open the sidecar
before the compile. Only (a) was implemented. A regular, writable log in a directory where the
user cannot create `<log>.lock` still goes like this:
1. the compile runs;
2. `open(_lock_path(log), "a+b")` raises `PermissionError`;
3. `cc` exits 1 with a valid object left on disk, which is a failed ninja edge.

Examples are a read-only directory, or a sticky directory owned by someone else. The bullet
now states the requirement ("The log's directory must be writable"). That is a reasonable
disposition, but the failure still happens after the compile, not before it.
**Fix:** Either leave it as documented, or add a pre-compile probe in `compile_rule`. The probe
would open and close `_lock_path(log)` in `"a+b"` mode when `log` is not an existing non-regular
file, and turn an `OSError` into a `CompilerError`. It opens the same sidecar the lock later
opens and never deletes it, so it adds no new race.

### IN-10: `_reap` in the real parallel test kills only the Python `cc`, not the compiler it spawned; `cc_root` still fails on a leftover directory

**File:** `tests/test_compiler_real.py:252-258`, `:48-54`
**Issue:** `proc.kill()` is `TerminateProcess` on Windows and `SIGKILL` on POSIX. Either one ends
only the `python -c CC_MAIN` process. The `wcc386.exe` (native) or `wibo` child that
`compile_rule` started through `subprocess.run` is orphaned and keeps its object and `.err`
open under `build/test-cc/` until it finishes. So the docstring's claim ("leaves none writing
into build/test-cc/") does not hold for a `cc` killed in the middle of a compile.

The case WR-03 targeted (a lock that never comes free) is not affected, because the lock is
taken only after the compile has finished. So this is Info. The follow-on effect WR-03 named
is also unchanged. `cc_root` still calls `path.mkdir(parents=True)` without `exist_ok` after
`shutil.rmtree(..., ignore_errors=True)`. If the rmtree leaves the directory behind, the next
run errors in the fixture instead of reporting the real failure.
**Fix:** Change the `_reap` docstring to say it reaps the `cc` processes only. In `cc_root`,
check that the rmtree worked instead of hiding it:

```python
shutil.rmtree(path, ignore_errors=True)
if path.exists():
    pytest.fail(f"{path} survived rmtree; a process from an earlier run still holds it")
path.mkdir(parents=True)
```

### IN-11: `test_dev_null_log_works_and_leaves_no_sidecar` hides its own regression when run as root

**File:** `tests/test_cc_log.py:190-196`
**Issue:** If the device branch regresses and the test runs as root (a CI image without the `dev`
user, or `docker compose run -u 0`), `/dev/null.lock` is created. The assertion fails once,
and every later run hits `pytest.skip("... already exists, left by something else")`. The
regression then reads as a skip. As user `dev`, which the project's container uses, the
regression fails with `PermissionError` instead, so the gate is not affected today.
**Fix:** Fail instead of skipping, or delete the sidecar the test created:

```python
existed = sidecar.exists()
try:
    compiler._append_log(Path("/dev/null"), _result("w0-0"))
    assert existed or not sidecar.exists()
finally:
    if not existed:
        sidecar.unlink(missing_ok=True)
```

### IN-12: The IN-03 qualification reached the toolchain bullet but not the `_append_log` docstring

**File:** `tools/reverseapoc/compiler.py:481-482`
**Issue:** The bullet now says "The Windows host and a container ... is not supported". The
docstring still says "the host and a container writing the same log at once are not covered,
because their OS locks do not see each other". On a Linux host with native Docker, the host and
the container share one kernel's `flock`, so the statement is only true for the Windows host.
**Fix:** Change it to "the Windows host and a container writing the same log at once are not
covered ...".

### IN-13: The new CLI test's `assert not obj.exists()` cannot fail

**File:** `tests/test_cli.py:733-743`
**Issue:** The object never exists before the call, so `assert not obj.exists()` passes even if
a refused `--log` reached `obj.unlink` (compiler.py:539). `runner.calls == []` covers the runner
but not the unlink, which comes before it. The property the docstring promises ("a refused path
or binary never reaches the runner and nothing is deleted") is therefore only half pinned.
**Fix:** Create the object first and check that it survives:

```python
obj.parent.mkdir(parents=True)
obj.write_bytes(b"keep")
...
assert obj.read_bytes() == b"keep"
```

---

_Reviewed: 2026-10-23T19:19:02Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
