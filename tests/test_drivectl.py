"""`reverseapoc drive-stop` and `drive-status` (todo drive-stop-helpers-in-repo): stop and inspect
a detached drive with repo commands instead of the session scratchpad's PowerShell scripts.

Every unit test fakes the process listing, the job check, the console Ctrl-C and the clock
(drivectl.Seams) and writes its attempt log and drive log under tmp_path. The one end-to-end test
starts a real sleeper in its own hidden console (Windows only, marked slow)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from reverseapoc import cli, drivectl

RUN = "20261124-codex"
UV = r"C:\Users\x\.local\bin\uv.exe"
PY = r"C:\repo\.venv\Scripts\python.exe"
TRAMPOLINE = r"C:\repo\.venv\Scripts\reverseapoc.exe"


def _proc(pid, command, *, name="python.exe", parent=1):
    return drivectl.Proc(pid=pid, parent=parent, name=name, command=command)


def _drive(run=RUN, *, pid=200, name="python.exe", parent=100):
    return _proc(pid, f'"{PY}" "{TRAMPOLINE}" drive --run {run} --arm codex=8', name=name,
                 parent=parent)  # fmt: skip


def _uv(run=RUN, pid=100):
    return _proc(pid, f"{UV} run reverseapoc drive --run {run} --arm codex=8", name="uv.exe")


# ---- the run match ----


@pytest.mark.parametrize("command", [
    f"uv run reverseapoc drive --run {RUN}",
    f'"{TRAMPOLINE}" drive --workers 8 --run {RUN}',
    f'"{PY}" "{TRAMPOLINE}" drive --run={RUN} --max-sessions 40',
    f'"{PY}" "{TRAMPOLINE}" drive --run "{RUN}"',
    f"python sleeper.py marker reverseapoc drive --run {RUN}",
])  # fmt: skip
def test_a_drive_of_the_run_matches(command):
    assert drivectl.drive_processes([_proc(7, command)], RUN) == [_proc(7, command)]


@pytest.mark.parametrize("command", [
    f"uv run reverseapoc drive --run {RUN}2",  # another run that starts with this one's id
    f"uv run reverseapoc drive --run x{RUN}",
    f"uv run reverseapoc drive-stop {RUN}",  # this very command
    f"uv run reverseapoc drive-status {RUN} --log C:/logs/{RUN}.log",
    f"uv run reverseapoc gate --all --run {RUN}",  # not a drive
    f"uv run reverseapoc drive --land-held {RUN}",  # names the run but is not its drive
    "",
])  # fmt: skip
def test_other_processes_do_not_match(command):
    assert drivectl.drive_processes([_proc(7, command)], RUN) == []


@pytest.mark.parametrize("name", ["powershell.exe", "pwsh.exe", "cmd.exe", "bash.exe"])
def test_a_launcher_or_watcher_shell_that_names_the_drive_is_not_the_drive(name):
    command = f"{name} -Command uv run reverseapoc drive --run {RUN}"
    assert drivectl.drive_processes([_proc(7, command, name=name)], RUN) == []


@pytest.mark.parametrize("name", ["uv.exe", "reverseapoc.exe", "python.exe", "python3.14.exe",
                                  "Python.EXE"])  # fmt: skip
def test_uv_the_console_script_and_python_are_drive_processes(name):
    procs = [_proc(7, f"x reverseapoc drive --run {RUN}", name=name)]
    assert drivectl.drive_processes(procs, RUN) == procs


def test_a_dot_in_the_run_id_is_literal():
    assert drivectl.drive_processes([_proc(7, "reverseapoc drive --run 1x2")], "1.2") == []


def test_the_listing_is_parsed_from_get_ciminstance_json():
    text = json.dumps([
        {"ProcessId": 4, "ParentProcessId": 0, "Name": "System", "CommandLine": None},
        {"ProcessId": 200, "ParentProcessId": 100, "Name": "python.exe",
         "CommandLine": f"reverseapoc drive --run {RUN}"},
    ])  # fmt: skip
    assert drivectl.parse_processes(text) == [
        _proc(4, "", name="System", parent=0),
        _proc(200, f"reverseapoc drive --run {RUN}", parent=100),
    ]


@pytest.mark.parametrize("text", ["not json", '[{"ProcessId": 1}]'])
def test_a_listing_that_is_not_get_ciminstance_json_is_named(text):
    with pytest.raises(drivectl.DriveCtlError, match="Win32_Process"):
        drivectl.parse_processes(text)


def test_a_listing_of_one_process_is_a_json_object_not_a_list():
    text = json.dumps({"ProcessId": 9, "ParentProcessId": 1, "Name": "a.exe", "CommandLine": "a"})
    assert drivectl.parse_processes(text) == [_proc(9, "a", name="a.exe")]


# ---- fakes ----


class FakeWorld:
    """The process table over time: `alive` lists drive processes per poll until it runs out
    (then none), the job check answers from `jobs`, Ctrl-C sends are recorded."""

    def __init__(self, polls, *, jobs=None, ctrl_c_error=""):
        self.polls = list(polls)
        self.jobs = jobs or {}
        self.ctrl_c_error = ctrl_c_error
        self.sent: list[int] = []
        self.now = 0.0
        self.sleeps: list[float] = []

    def processes(self):
        return self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]

    def seams(self) -> drivectl.Seams:
        return drivectl.Seams(processes=self.processes, in_job=lambda pid: self.jobs.get(pid),
                              ctrl_c=self._ctrl_c, sleep=self._sleep,
                              clock=lambda: self.now)  # fmt: skip

    def _ctrl_c(self, pid):
        self.sent.append(pid)
        return self.ctrl_c_error

    def _sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _attempts(repo: Path, *records: dict) -> None:
    log = repo / "progress" / "attempts.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records),
                   encoding="utf-8")  # fmt: skip


STOPPED = {"kind": "run", "run": RUN, "event": "STOPPED", "reason": "interrupted",
           "sessions": 41, "matched": 0}  # fmt: skip


# ---- drive-stop ----


def test_stop_sends_ctrl_c_to_the_drive_python_waits_and_prints_the_stop_record(tmp_path, capsys):
    _attempts(tmp_path,
              {"kind": "run", "run": RUN, "event": "STARTED", "sessions": 0},
              {"kind": "attempt", "run": RUN, "function": "x"},
              {"kind": "run", "run": f"{RUN}2", "event": "STARTED"},
              STOPPED,
              {"kind": "run", "run": "later", "event": "STARTED"})  # fmt: skip
    world = FakeWorld([[_uv(), _drive()], [_uv(), _drive()], [_uv()], []])
    assert drivectl.stop(RUN, 15, tmp_path, world.seams()) == drivectl.EXITED
    assert world.sent == [200]  # the python, not uv
    out = capsys.readouterr().out
    assert f"sent the console Ctrl-C to pid 200 ({RUN})" in out
    assert f"drive {RUN} exited" in out
    assert json.loads(out.strip().splitlines()[-1]) == STOPPED


def test_stop_falls_back_to_any_drive_process_when_no_python_is_left(tmp_path):
    world = FakeWorld([[_uv(pid=100)], []])
    assert drivectl.stop(RUN, 15, tmp_path, world.seams()) == drivectl.EXITED
    assert world.sent == [100]


def test_stop_without_a_drive_process_sends_nothing(tmp_path, capsys):
    world = FakeWorld([[_drive(f"{RUN}2"), _proc(5, "explorer.exe", name="explorer.exe")]])
    assert drivectl.stop(RUN, 15, tmp_path, world.seams()) == drivectl.NOT_RUNNING == 2
    assert world.sent == []
    assert capsys.readouterr().out.strip() == f"no drive process for {RUN}"


def test_stop_gives_up_after_the_wait_and_says_the_drive_still_runs(tmp_path, capsys):
    world = FakeWorld([[_uv(), _drive()]])
    assert drivectl.stop(RUN, 1, tmp_path, world.seams()) == drivectl.STILL_RUNNING == 1
    assert world.now >= 60 and all(s == drivectl.POLL_S for s in world.sleeps)
    assert world.now < 60 + drivectl.POLL_S
    assert f"drive {RUN} still running after 1 min: pids 100, 200" in capsys.readouterr().out


def test_stop_reports_a_failed_ctrl_c_and_does_not_wait(tmp_path, capsys):
    world = FakeWorld([[_drive()]], ctrl_c_error="AttachConsole(200) failed: error 5")
    assert drivectl.stop(RUN, 15, tmp_path, world.seams()) == drivectl.STILL_RUNNING
    assert world.sleeps == []
    assert "AttachConsole(200) failed: error 5" in capsys.readouterr().out


def test_stop_says_so_when_the_log_has_no_run_record(tmp_path, capsys):
    _attempts(tmp_path, {"kind": "run", "run": "other", "event": "STOPPED"})
    world = FakeWorld([[_drive()], []])
    assert drivectl.stop(RUN, 15, tmp_path, world.seams()) == drivectl.EXITED
    assert f"no kind=run record for {RUN} in " in capsys.readouterr().out


def test_stop_still_exits_0_when_the_record_line_is_broken(tmp_path, capsys):
    """The driver is gone, so the exit says so; the broken line is named, not swallowed."""
    log = tmp_path / "progress" / "attempts.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(f'{{"kind":"run","run":"{RUN}"\n', encoding="utf-8")
    world = FakeWorld([[_drive()], []])
    assert drivectl.stop(RUN, 15, tmp_path, world.seams()) == drivectl.EXITED
    assert "attempts.jsonl:1:" in capsys.readouterr().out


def test_the_ctrl_c_helper_gets_the_drive_pid_and_the_caller_pid(monkeypatch):
    """The helper refuses when the caller is on the drive's console (a drive started in the
    caller's own terminal), so drive-stop never interrupts itself or its shell."""
    seen = []

    def run(argv, **kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "the caller shares the console\n")

    monkeypatch.setattr(drivectl.subprocess, "run", run)
    assert drivectl.send_ctrl_c(200) == "the caller shares the console"
    assert seen == [[sys.executable, "-I", "-c", drivectl._CTRL_C, "200", str(os.getpid())]]
    assert "GetConsoleProcessList" in drivectl._CTRL_C


def test_stop_names_a_broken_attempt_log_line(tmp_path):
    log = tmp_path / "progress" / "attempts.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(f'{{"kind":"run","run":"{RUN}"\n', encoding="utf-8")
    with pytest.raises(drivectl.DriveCtlError, match=r"attempts\.jsonl:1"):
        drivectl.last_run_record(log, RUN)


# ---- drive-status ----


def _night_log(path: Path) -> Path:
    lines = [
        "drive 20261124-codex: 8 workers",
        "UFO2P.EXE func_00047FB0 attempt 1/3 (codex): started",
        "UFO2P.EXE func_00047FB0 attempt 1/3 (codex): PARTIAL after 812.3 s",
        "TACP.EXE func_0001C250 attempt 1/3 (codex): started",
        "TACP.EXE func_0001C250 attempt 1/3 (codex): GAVE_UP after 1500.0 s (1600.0 s wall, "
        "100.0 s limit waits)",
        "TACP.EXE func_00049E10 attempt 2/3 (codex): MATCHED after 90.1 s",
        "TACP.EXE func_00053CF0 attempt 1/3 (codex): ABORTED (transient) after 3.0 s",
        "codex arm: usage limit, pausing until 15:32",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_status_lists_each_drive_process_with_its_job_and_the_log(tmp_path, capsys):
    world = FakeWorld([[_uv(), _drive(), _drive("other", pid=300)]], jobs={100: False, 200: True})
    log = _night_log(tmp_path / "night.log")
    assert drivectl.status(RUN, log, world.seams()) == drivectl.RUNNING == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "pid 100 parent 1 uv.exe in_job=no"
    assert out[1] == "pid 200 parent 100 python.exe in_job=yes"
    assert out[2] == f"sessions so far: 3 ({log})"  # MATCHED, PARTIAL, GAVE_UP; not ABORTED
    assert len(out) == 3 + drivectl.TAIL_LINES
    assert world.processes() and "pid 300" not in "\n".join(out)


def test_status_tail_is_the_last_five_lines(tmp_path, capsys):
    world = FakeWorld([[_drive()]], jobs={200: False})
    log = _night_log(tmp_path / "night.log")
    drivectl.status(RUN, log, world.seams())
    out = capsys.readouterr().out.splitlines()
    tail = log.read_text(encoding="utf-8").splitlines()[-5:]
    assert out[-5:] == [f"  {line}" for line in tail]


def test_status_says_unknown_when_the_job_check_cannot_open_the_process(tmp_path, capsys):
    world = FakeWorld([[_drive()]])
    assert drivectl.status(RUN, None, world.seams()) == drivectl.RUNNING
    assert capsys.readouterr().out.strip() == "pid 200 parent 100 python.exe in_job=unknown"


def test_status_without_a_drive_exits_2_and_still_reads_the_log(tmp_path, capsys):
    world = FakeWorld([[]])
    log = _night_log(tmp_path / "night.log")
    assert drivectl.status(RUN, log, world.seams()) == drivectl.NOT_RUNNING
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"no drive process for {RUN}"
    assert out[1] == f"sessions so far: 3 ({log})"


def test_status_names_a_missing_log(tmp_path, capsys):
    world = FakeWorld([[_drive()]])
    missing = tmp_path / "nope.log"
    assert drivectl.status(RUN, missing, world.seams()) == drivectl.RUNNING
    assert f"no log at {missing}" in capsys.readouterr().out


# ---- the command line ----


def _fake(monkeypatch, world):
    monkeypatch.setattr(drivectl, "default_seams", world.seams)
    monkeypatch.setattr(sys, "platform", "win32")


def test_cli_drive_stop_argv(monkeypatch, tmp_path):
    world = FakeWorld([[_drive()], []])
    _fake(monkeypatch, world)
    calls = []
    real = drivectl.stop
    monkeypatch.setattr(drivectl, "stop", lambda *a: calls.append(a) or real(*a))
    assert cli.main(["drive-stop", RUN, "--wait-minutes", "3"]) == 0
    assert calls[0][:3] == (RUN, 3, cli.REPO_ROOT)
    assert cli.main(["drive-stop", RUN]) == 2  # the drive already exited
    assert calls[1][:2] == (RUN, 15)


def test_cli_drive_status_argv(monkeypatch, tmp_path):
    world = FakeWorld([[_drive()]], jobs={200: False})
    _fake(monkeypatch, world)
    log = _night_log(tmp_path / "n.log")
    assert cli.main(["drive-status", RUN, "--log", str(log)]) == 0
    assert cli.main(["drive-status", "other"]) == 2


@pytest.mark.parametrize("argv", [["drive-stop", RUN], ["drive-status", RUN]])
def test_cli_refuses_off_windows(monkeypatch, capsys, argv):
    monkeypatch.setattr(drivectl, "default_seams", lambda: pytest.fail("no seams off Windows"))
    monkeypatch.setattr(sys, "platform", "linux")
    assert cli.main(argv) == 2
    assert "Windows only" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    ["drive-stop", "bad id"], ["drive-stop", RUN, "--wait-minutes", "0"], ["drive-status"],
])  # fmt: skip
def test_cli_rejects_a_bad_run_id_or_wait(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)


# ---- end to end: a real sleeper in its own hidden console ----

_SLEEPER = """\
import ctypes, sys, time
ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)  # as driver.take_console_ctrl_c
marker = sys.argv[1]
open(marker, "w").write("started\\n")
try:
    for _ in range(300):
        time.sleep(1)
except KeyboardInterrupt:
    open(marker, "a").write("KeyboardInterrupt caught\\n")
"""


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "win32", reason="the console Ctrl-C is Windows only")
def test_e2e_stop_interrupts_a_detached_sleeper(tmp_path, monkeypatch, capsys):
    run = f"e2e-{uuid.uuid4().hex[:8]}"
    script, marker = tmp_path / "sleeper.py", tmp_path / "marker.txt"
    script.write_text(_SLEEPER, encoding="utf-8")
    startup = subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)
    child = subprocess.Popen(
        [sys.executable, "-I", str(script), str(marker), "reverseapoc", "drive", "--run", run],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_BREAKAWAY_FROM_JOB,
        startupinfo=startup, close_fds=True)  # fmt: skip
    try:
        for _ in range(100):
            if marker.exists():
                break
            time.sleep(0.1)
        assert cli.main(["drive-status", run]) == 0
        status = capsys.readouterr().out
        assert f"pid {child.pid} " in status and "in_job=no" in status
        monkeypatch.setattr(drivectl, "POLL_S", 1.0)
        assert cli.main(["drive-stop", run, "--wait-minutes", "1"]) == 0
        assert "KeyboardInterrupt caught" in marker.read_text(encoding="utf-8")
        assert cli.main(["drive-status", run]) == 2
    finally:
        child.kill()
