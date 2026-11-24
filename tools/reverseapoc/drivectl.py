# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc drive-stop` and `drive-status` (todo drive-stop-helpers-in-repo): stop and inspect
a running drive, a detached one included, with repo commands instead of the PowerShell scripts
that were copied from one session's scratchpad to the next (docs/model-routing.md "Stopping and
inspecting a detached night").

A drive is found by its command line: `reverseapoc drive` (uv's, the console script's or its
Python's spelling) with `--run RUN`. The stop is the documented console Ctrl-C: a short-lived
helper process attaches to the drive's console, ignores Ctrl-C itself and raises it there, so the
caller's own console is never detached. Both commands are read-only: they write nothing under the
checkout, so the hook can allow them while a drive holds the lock.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .attempt import ATTEMPT_LOG

EXITED, STILL_RUNNING, NOT_RUNNING = 0, 1, 2  # drive-stop's exit codes
RUNNING = 0  # drive-status: a drive process for the run exists (else NOT_RUNNING)
POLL_S = 10.0  # how often drive-stop looks for the drive again
TAIL_LINES = 5  # drive-status: the last lines of --log
DRIVE = re.compile(r'reverseapoc(\.exe"?)?\s+drive(\s|$)')  # not drive-stop or drive-status
# uv, the console script and its Python; never a launcher or watcher shell that names the drive
DRIVE_NAME = re.compile(r"(uv|reverseapoc|python[\d.]*)(\.exe)?", re.IGNORECASE)
SESSION_LINE = re.compile(r": (MATCHED|PARTIAL|GAVE_UP) after ")  # driver._announced's outcome
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_LIST = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-CimInstance Win32_Process | "
         "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
# Run as `python -I -c _CTRL_C PID CALLER` (driver.take_console_ctrl_c turned Ctrl-C back on in a
# drive). It refuses when CALLER is on PID's console: the Ctrl-C would reach the caller too.
_CTRL_C = """\
import ctypes, sys
k = ctypes.WinDLL("kernel32", use_last_error=True)
pid, caller = int(sys.argv[1]), int(sys.argv[2])
k.FreeConsole()
if not k.AttachConsole(pid):
    sys.exit(f"AttachConsole({pid}) failed: error {ctypes.get_last_error()}")
on_console = (ctypes.c_uint32 * 4096)()
if caller in on_console[: k.GetConsoleProcessList(on_console, 4096)]:
    sys.exit(f"pid {pid} shares this command's console; press Ctrl-C in that console instead")
k.SetConsoleCtrlHandler(None, True)
if not k.GenerateConsoleCtrlEvent(0, 0):
    sys.exit(f"GenerateConsoleCtrlEvent(CTRL_C_EVENT) failed: error {ctypes.get_last_error()}")
"""


class DriveCtlError(Exception):
    """The attempt log or the process listing could not be read."""


@dataclass(frozen=True)
class Proc:
    pid: int
    parent: int
    name: str
    command: str


def parse_processes(text: str) -> list[Proc]:
    """Get-CimInstance Win32_Process as ConvertTo-Json writes it: a list, or one object when
    there is a single process; a CommandLine Windows hides is null."""
    try:
        rows = json.loads(text)
        rows = [rows] if isinstance(rows, dict) else rows
        return [Proc(pid=r["ProcessId"], parent=r["ParentProcessId"], name=r["Name"] or "",
                     command=r["CommandLine"] or "") for r in rows]  # fmt: skip
    except (ValueError, KeyError, TypeError) as exc:
        raise DriveCtlError(f"the Win32_Process listing is not Get-CimInstance JSON: "
                            f"{exc!r}") from exc  # fmt: skip


def list_processes() -> list[Proc]:
    done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _LIST],
                          capture_output=True, stdin=subprocess.DEVNULL)  # fmt: skip
    if done.returncode:
        raise DriveCtlError(f"Get-CimInstance Win32_Process failed: "
                            f"{done.stderr.decode('utf-8', 'replace').strip()}")  # fmt: skip
    return parse_processes(done.stdout.decode("utf-8-sig"))


def process_in_job(pid: int) -> bool | None:
    """IsProcessInJob(pid, any job); None when the process cannot be opened or asked."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    result = ctypes.c_int()
    try:
        asked = kernel32.IsProcessInJob(ctypes.c_void_p(handle), None, ctypes.byref(result))
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
    return bool(result.value) if asked else None


def send_ctrl_c(pid: int) -> str:
    """Raise the console Ctrl-C in `pid`'s console from a helper child; "" when sent, else why."""
    argv = [sys.executable, "-I", "-c", _CTRL_C, str(pid), str(os.getpid())]
    done = subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return (done.stderr.strip() or f"exit {done.returncode}") if done.returncode else ""


@dataclass(frozen=True)
class Seams:
    """What the commands touch outside the attempt log and --log: the process table, the job
    check, the Ctrl-C send, the sleep and the clock."""

    processes: Callable[[], Sequence[Proc]] = list_processes
    in_job: Callable[[int], bool | None] = process_in_job
    ctrl_c: Callable[[int], str] = send_ctrl_c
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic


def default_seams() -> Seams:
    return Seams()


def drive_processes(procs: Sequence[Proc], run: str) -> list[Proc]:
    """The `reverseapoc drive --run RUN` processes (uv, the console script, its Python), by pid."""
    names_run = re.compile(rf'(^|\s)--run(=|\s+)"?{re.escape(run)}"?(\s|$)')
    return sorted((p for p in procs if DRIVE_NAME.fullmatch(p.name) and DRIVE.search(p.command)
                   and names_run.search(p.command)), key=lambda p: p.pid)  # fmt: skip


def last_run_record(log: Path, run: str) -> str | None:
    """RUN's last kind=run line of the attempt log, as written; None when it has none."""
    last = None
    with log.open(encoding="utf-8") as lines:
        for number, line in enumerate(lines, 1):
            if '"run"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DriveCtlError(f"{log}:{number}: {exc}") from exc
            if record.get("kind") == "run" and record.get("run") == run:
                last = line.strip()
    return last


def _say_record(repo: Path, run: str) -> None:
    log = repo / ATTEMPT_LOG
    record = last_run_record(log, run) if log.exists() else None
    print(record or f"no kind=run record for {run} in {log}")


def stop(run: str, wait_minutes: int, repo: Path, seams: Seams) -> int:
    """Send the console Ctrl-C to RUN's drive, wait up to `wait_minutes` for every drive process
    of RUN to exit, then print RUN's last kind=run record from the repo's attempt log."""
    procs = drive_processes(seams.processes(), run)
    if not procs:
        print(f"no drive process for {run}")
        return NOT_RUNNING
    target = next((p for p in procs if p.name.lower().startswith("python")), procs[0])
    failed = seams.ctrl_c(target.pid)
    if failed:
        print(f"the console Ctrl-C to pid {target.pid} ({run}) was not sent: {failed}")
        return STILL_RUNNING
    print(f"sent the console Ctrl-C to pid {target.pid} ({run}); waiting up to "
          f"{wait_minutes} min for the driver to exit")  # fmt: skip
    deadline = seams.clock() + wait_minutes * 60
    while procs := drive_processes(seams.processes(), run):
        if seams.clock() >= deadline:
            pids = ", ".join(str(p.pid) for p in procs)
            print(f"drive {run} still running after {wait_minutes} min: pids {pids}")
            return STILL_RUNNING
        seams.sleep(POLL_S)
    print(f"drive {run} exited")
    try:
        _say_record(repo, run)
    except DriveCtlError as exc:  # the driver is gone all the same: the exit code says so
        print(f"its kind=run record could not be read: {exc}")
    return EXITED


def _say_log(log: Path) -> None:
    if not log.exists():
        print(f"no log at {log}")
        return
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    sessions = sum(1 for line in lines if SESSION_LINE.search(line))
    print(f"sessions so far: {sessions} ({log})")
    for line in lines[-TAIL_LINES:]:
        print(f"  {line}")


def status(run: str, log: Path | None, seams: Seams) -> int:
    """Print RUN's drive processes (pid, parent, name, whether each is in a job) and, with a log,
    its finished sessions and last lines."""
    procs = drive_processes(seams.processes(), run)
    for p in procs:
        in_job = {True: "yes", False: "no", None: "unknown"}[seams.in_job(p.pid)]
        print(f"pid {p.pid} parent {p.parent} {p.name} in_job={in_job}")
    if not procs:
        print(f"no drive process for {run}")
    if log is not None:
        _say_log(log)
    return RUNNING if procs else NOT_RUNNING
