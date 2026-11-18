"""What a run record says about the night's environment, the checker controls run before it,
and the owner's notifier on its end (todos nightly-gold-null-controls, run-environment-digest,
drive-stop-notification).

The controls go through run_drive with tests/test_drive.py's Rig and an injected runner that
answers the attempt wrapper's check; the notifier through test_driver.py's Night. No test runs
docker, claude or the network; every name and text below is made up, and the unit committed in
the tmp repo is made-up C, not the project's.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from reverseapoc import attempt, driver, hooks
from test_attempts_schema import _run_v3
from test_drive import Rig, Runner, _git
from test_driver import RUN as NIGHT_RUN
from test_driver import Night, Sess, _one, check_line
from test_stats import _json, _log, _repo
from test_stats import _run as _stats_run

CHECK_ARGV = [*hooks.ATTEMPT_PREFIX, "check"]
CONTROL_UNIT_REL = f"src/{driver.CANARY_EXE}/{driver.CANARY_UNIT}.c"
CONTROL_UNIT = f"""#include "common.h"

int func_000A3990(void);

/* func_000A3980(void) {{ is how a comment may mention it; only the definition is changed */
int {driver.CANARY_FUNC}(void)
{{
    return func_000A3990();
}}
"""
CONTROL_ROWS = ("start,end,name,kind,unit,evidence\n"
                f"0x000A3980,0x000A398D,{driver.CANARY_FUNC},game,{driver.CANARY_UNIT},call\n")
SHA_A, SHA_B = "a" * 64, "b" * 64
ENVIRONMENT = {"digest": SHA_A, "head": "c" * 40, "image": f"sha256:{SHA_B}",
               "cli": {"claude": "2.1.302", "codex": None},
               "files": {"uv.lock": SHA_A, "config/driver/quota.toml": None},
               "prompt": SHA_B}  # fmt: skip
CONTROLS = {"exe": "ufo2p", "unit": "u_000a34f0", "function": "func_000A3980", "gold": 0,
            "null": 1, "null_percent": 72.5}


# ---- the record schema ----


def _started_v3() -> dict:
    record = _run_v3()
    record.update(event="STARTED", reason="start", totals=None)
    return record


def test_a_started_record_may_carry_its_environment_and_controls():
    """The two keys are additive: a STARTED record without them (every committed one) and one
    with both validate; one of them alone, or either on an ENDED record, does not."""
    driver.validate_record(_started_v3())
    driver.validate_record({**_started_v3(), "environment": ENVIRONMENT, "controls": CONTROLS})
    driver.validate_record({**_started_v3(), "environment": ENVIRONMENT, "controls": None})
    with pytest.raises(driver.RecordError):
        driver.validate_record({**_started_v3(), "environment": ENVIRONMENT})
    with pytest.raises(driver.RecordError, match="STARTED"):
        driver.validate_record({**_run_v3(), "environment": ENVIRONMENT, "controls": CONTROLS})


@pytest.mark.parametrize("change", [
    lambda e: e.update(digest="short"),
    lambda e: e.update(head="HEAD"),
    lambda e: e.update(image="noise on stdout"),
    lambda e: e["cli"].update(vim="9.1"),
    lambda e: e["files"].update({"uv.lock": "not a hash"}),
    lambda e: e.pop("prompt"),
])  # fmt: skip
def test_a_malformed_environment_is_refused(change):
    environment = json.loads(json.dumps(ENVIRONMENT))
    change(environment)
    with pytest.raises(driver.RecordError):
        driver.validate_record({**_started_v3(), "environment": environment,
                                "controls": CONTROLS})  # fmt: skip


def test_the_night_writes_both_into_started_only(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[1])
    night.run(config={"environment": ENVIRONMENT, "controls": CONTROLS})
    runs = night.kinds("run")
    started, ended = runs[0], runs[-1]
    assert (started["environment"], started["controls"]) == (ENVIRONMENT, CONTROLS)
    assert "environment" not in ended and "controls" not in ended
    for record in runs:
        driver.validate_record(record)


# ---- the controls (todo nightly-gold-null-controls) ----


@dataclass
class CheckRunner(Runner):
    """Rig's runner, but the attempt wrapper's check answers `gold` in the gold control's
    attempt dir (attempt-1) and `null` in the null one's (attempt-2), keeping each env and its
    view unit's text."""

    gold: int = 0
    null: int = 1
    null_percent: float | None = 72.5  # what the null check logs; None: not compiled
    checks: list[dict] = field(default_factory=list)

    def __call__(self, argv, env=None) -> subprocess.CompletedProcess:
        if list(argv) != CHECK_ARGV:
            return super().__call__(argv, env)
        self.calls.append(list(argv))
        attempt_dir = Path(env[attempt.DIR_ENV])
        unit = Path(env[hooks.UNIT_FILE_ENV]).read_text(encoding="utf-8")
        self.checks.append({"env": dict(env), "unit": unit, "dir": attempt_dir})
        gold = attempt_dir.name == "attempt-1"
        code, percent = (self.gold, 100.0) if gold else (self.null, self.null_percent)
        line = attempt.CheckLogLine(1, code, False, percent, True, percent == 100.0, True, None,
                                    "checks/0001.c")  # fmt: skip
        with (attempt_dir / attempt.CHECK_LOG).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line.to_json()) + "\n")
        return subprocess.CompletedProcess(argv, code, "made-up check summary\n", "")


def _control_rig(tmp_path: Path, runner: CheckRunner) -> Rig:
    rig = Rig(tmp_path, runner=runner)
    for rel, text in {CONTROL_UNIT_REL: CONTROL_UNIT,
                      f"config/{driver.CANARY_EXE}/functions.csv": CONTROL_ROWS}.items():
        path = rig.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        _git(rig.repo, rig.env, "add", "--", rel)
    _git(rig.repo, rig.env, "commit", "-q", "-m", "the control's made-up unit")
    return rig


def _drive_with_controls(rig: Rig, capsys, monkeypatch) -> tuple[int, dict, list]:
    seen = []

    def fake_drive(config, deps, *, lock=None):
        seen.append(config)
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    monkeypatch.setattr(driver, "drive", fake_drive)
    code, out, _ = rig.drive(capsys, json=True, seams={"controls": driver.run_controls})
    return code, json.loads(out), seen


def test_a_healthy_checker_passes_and_the_night_gets_the_results(tmp_path, capsys, monkeypatch):
    """Gold exit 0 and null exit 1 through the session's own wrapper argv and claim env: the
    night starts with the results; the gold view unit is HEAD's, the null one's definition has
    the null declaration and its comment is unchanged; each check had its plan and note."""
    runner = CheckRunner()
    rig = _control_rig(tmp_path, runner)
    code, doc, seen = _drive_with_controls(rig, capsys, monkeypatch)
    assert code == 0, doc
    assert _one(seen).controls == CONTROLS
    gold, null = runner.checks
    assert gold["unit"] == CONTROL_UNIT
    assert null["unit"] != CONTROL_UNIT
    assert null["unit"].count(driver.CONTROL_NULL_DECLARATION) == 1
    assert "func_000A3980(void) { is how a comment" in null["unit"]
    for check in (gold, null):
        env = check["env"]
        assert env[attempt.CLAIM_ENV] == f"{driver.CANARY_EXE}/{driver.CANARY_UNIT}"
        assert env[attempt.FUNC_ENV] == driver.CANARY_FUNC
        assert env[hooks.SESSION_KIND_ENV] == driver.MATCHING
        assert check["dir"].is_relative_to(rig.repo / "build" / "driver" / "controls")
        assert (check["dir"] / hooks.PLAN_NAME).is_file()
        assert (check["dir"] / hooks.CHECK_NOTE_NAME).is_file()


@pytest.mark.parametrize(("gold", "null", "percent", "named"), [
    (0, 0, 72.5, "the null control exit 0"),  # the checker calls a wrong function exact
    (1, 1, 72.5, "the gold control exit 1"),  # the checker misses a committed match
    (2, 1, 72.5, "the gold control exit 2"),  # the checker cannot run
    (0, 1, None, "no measured percent"),  # exit 1 only because the null unit did not compile
    (0, 1, 100.0, "measured 100%"),  # exit 1 for another reason than the null function
])  # fmt: skip
def test_a_broken_checker_refuses_the_night(tmp_path, capsys, monkeypatch, gold, null, percent,
                                            named):  # fmt: skip
    rig = _control_rig(tmp_path, CheckRunner(gold=gold, null=null, null_percent=percent))
    code, doc, seen = _drive_with_controls(rig, capsys, monkeypatch)
    assert code == driver.EXIT_TOOL
    assert (doc["event"], doc["reason"]) == ("REFUSED", "controls")
    assert named in doc["detail"]
    assert not seen  # no night, so no run record
    log = rig.repo / "progress" / "attempts.jsonl"
    assert log.read_text(encoding="utf-8") == ""


def test_a_second_start_with_the_same_run_id_runs_fresh_controls(tmp_path, capsys, monkeypatch):
    runner = CheckRunner(null=0)
    rig = _control_rig(tmp_path, runner)
    assert _drive_with_controls(rig, capsys, monkeypatch)[0] == driver.EXIT_TOOL
    runner.null = 1
    assert _drive_with_controls(rig, capsys, monkeypatch)[0] == 0


def test_head_without_the_control_unit_refuses(tmp_path, capsys, monkeypatch):
    rig = Rig(tmp_path, runner=CheckRunner())
    code, doc, seen = _drive_with_controls(rig, capsys, monkeypatch)
    assert (code, doc["reason"], seen) == (driver.EXIT_TOOL, "controls", [])
    assert CONTROL_UNIT_REL in doc["detail"]


def test_the_null_unit_changes_only_the_claimed_definition():
    text = driver.null_control_unit(CONTROL_UNIT, driver.CANARY_FUNC)
    assert text.replace(" " + driver.CONTROL_NULL_DECLARATION, "", 1) == CONTROL_UNIT
    with pytest.raises(ValueError, match="no definition"):
        driver.null_control_unit("int other(void)\n{\n    return 0;\n}\n", driver.CANARY_FUNC)
    twice = CONTROL_UNIT + CONTROL_UNIT.split('#include "common.h"\n', 1)[1]
    with pytest.raises(ValueError, match="2 definitions"):
        driver.null_control_unit(twice, driver.CANARY_FUNC)


# ---- the environment digest (todo run-environment-digest) ----

IMAGE = f"sha256:{'d' * 64}"


def _image_reply(argv):
    return argv[:3] == ["docker", "image", "inspect"]


def _environment(rig: Rig, **options) -> dict:
    arms = driver.refuse_arms(rig.options(**options), rig.seams())
    return driver.environment(rig.options(**options), rig.seams(), arms)


def test_the_environment_names_head_image_cli_files_and_prompt(tmp_path):
    rig = Rig(tmp_path, runner=Runner(replies=[(_image_reply, (0, IMAGE + "\n", ""))]))
    (rig.repo / "uv.lock").write_text("made-up lock\n", encoding="utf-8")
    env = _environment(rig)
    assert env["head"] == _git(rig.repo, rig.env, "rev-parse", "HEAD").strip()
    assert env["image"] == IMAGE
    assert env["cli"] == {"claude": "2.1.302"}
    assert set(env["files"]) == set(driver.ENVIRONMENT_FILES)
    assert env["files"]["uv.lock"] is not None and env["files"][driver.SKILL] is None
    record = {**_started_v3(), "environment": env, "controls": CONTROLS}
    driver.validate_record(record)
    rest = {key: value for key, value in env.items() if key not in ("digest", "head")}
    assert env["digest"] == driver.environment_digest(rest)


def test_a_new_commit_alone_keeps_the_digest(tmp_path):
    """HEAD is named but not digested: a docs commit is the same environment."""
    rig = Rig(tmp_path)
    first = _environment(rig)
    (rig.repo / "notes.md").write_text("made up\n", encoding="utf-8")
    _git(rig.repo, rig.env, "add", "--", "notes.md")
    _git(rig.repo, rig.env, "commit", "-q", "-m", "made-up docs commit")
    second = _environment(rig)
    assert second["head"] != first["head"] and second["digest"] == first["digest"]


def test_an_unknown_image_is_null(tmp_path):
    assert _environment(Rig(tmp_path))["image"] is None  # the fake answers "noise on stdout"


def test_different_skills_give_different_digests(tmp_path):
    rig = Rig(tmp_path)
    skill = rig.repo / driver.SKILL
    skill.parent.mkdir(parents=True)
    skill.write_text("made-up skill, first text\n", encoding="utf-8")
    first = _environment(rig)
    assert _environment(rig)["digest"] == first["digest"]  # the same files: the same digest
    skill.write_text("made-up skill, second text\n", encoding="utf-8")
    second = _environment(rig)
    assert second["files"][driver.SKILL] != first["files"][driver.SKILL]
    assert second["digest"] != first["digest"]


def test_a_land_held_night_asks_no_cli(tmp_path):
    rig = Rig(tmp_path)
    assert _environment(rig, land_held=("spike012-*",))["cli"] == {}
    assert not [c for c in rig.runner.calls if c[1:] == ["--version"]]


def test_run_drive_hands_the_environment_to_the_night(tmp_path, capsys, monkeypatch):
    rig = Rig(tmp_path)
    seen = []

    def fake_drive(config, deps, *, lock=None):
        seen.append(config)
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    monkeypatch.setattr(driver, "drive", fake_drive)
    code, _, _ = rig.drive(capsys, json=True)
    assert code == 0
    config = _one(seen)
    assert config.environment["head"] == _git(rig.repo, rig.env, "rev-parse", "HEAD").strip()
    assert config.controls is not None


def test_a_land_held_night_runs_no_controls(tmp_path, capsys, monkeypatch):
    from test_attempts_schema import _attempt_v3
    from test_driver_records import _lines

    rig = Rig(tmp_path)
    record = {**_attempt_v3(), "run": "spike012-haiku", "hold_run": True, "outcome": "PARTIAL"}
    (rig.repo / "progress/attempts.jsonl").write_text(_lines([record]), encoding="ascii",
                                                      newline="\n")  # fmt: skip
    _git(rig.repo, rig.env, "commit", "-q", "-am", "a made-up hold-run record")
    seen = []

    def fake_drive(config, deps, *, lock=None):
        seen.append(config)
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    def no_controls(*args):
        raise AssertionError("a land-held night ran the controls")

    monkeypatch.setattr(driver, "drive", fake_drive)
    code, _, _ = rig.drive(capsys, json=True, land_held=("spike012-*",),
                           seams={"controls": no_controls})  # fmt: skip
    assert code == 0
    assert _one(seen).controls is None and _one(seen).environment is not None


def test_stats_run_prints_each_started_environment(tmp_path, capsys):
    """`stats --run` names each selected night's environment and controls; an older STARTED
    record without them still prints, as such."""
    repo, _ = _repo(tmp_path)
    new = {**_started_v3(), "run": "new1", "environment": ENVIRONMENT, "controls": CONTROLS}
    old = {**_started_v3(), "run": "old1"}
    log = _log(tmp_path, new, old)
    config = tmp_path / "config"
    assert _stats_run(repo, log, "--run", "*", config=config) == 0
    out = capsys.readouterr().out.splitlines()
    head = out.index("environment per run:")
    assert out[head + 1].startswith(f"  new1: digest {SHA_A[:12]}")
    assert "claude 2.1.302" in out[head + 1]
    assert out[head + 1].endswith("controls gold 0, null 1 (72.5%)")
    assert out[head + 2] == "  old1: no environment recorded"
    doc = _json(capsys, repo, log, "--run", "*", config=config)
    assert doc["environments"] == [
        {"run": "new1", "environment": ENVIRONMENT, "controls": CONTROLS},
        {"run": "old1", "environment": None, "controls": None}]  # fmt: skip
    assert _json(capsys, repo, log, config=config)["environments"] is None


# ---- the notifier (todo drive-stop-notification) ----


def _notified(night: Night, **run) -> list[tuple[str, str, str]]:
    calls: list[tuple[str, str, str]] = []
    night.run(notify=lambda event, run_id, text: calls.append((event, run_id, text)), **run)
    return calls


def test_the_notifier_fires_once_on_an_ended_night(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[1])
    (event, run, text), = _notified(night)
    assert (event, run) == ("ENDED", NIGHT_RUN)
    assert text.startswith(f"reverseapoc drive {NIGHT_RUN}: ENDED ")
    ended = night.kinds("run")[-1]
    assert text == (f"reverseapoc drive {NIGHT_RUN}: ENDED {ended['reason']}: "
                    f"{ended['sessions']} sessions, {ended['matched']} matched")


def test_the_notifier_fires_after_the_log_commit(tmp_path):
    """The owner may commit once told; the driver has nothing left to commit by then."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[1])
    seen: list[list[str]] = []
    night.run(notify=lambda *args: seen.append(night.commits()))
    assert seen == [["chore(driver): attempt log"]]


def test_the_notifier_fires_on_a_stopped_night_with_its_reason(tmp_path):
    sessions = [Sess(checks=(check_line(1, 20.0),)), Sess(write="tools/x.py")]
    night = Night(tmp_path, sessions=sessions)
    (event, _, text), = _notified(night)
    assert event == "STOPPED"
    assert ": STOPPED guardrail: " in text


def test_the_notifier_fires_before_an_interrupt_is_raised(tmp_path):
    night = Night(tmp_path, sessions=[Sess(raises=KeyboardInterrupt())])
    calls = []
    with pytest.raises(KeyboardInterrupt):
        night.run(notify=lambda *args: calls.append(args))
    assert [(event, text.split(": ")[1]) for event, _, text in calls] == [
        ("STOPPED", "STOPPED interrupted")]  # fmt: skip


NOTIFY_SCRIPT = """import os, sys
with open(sys.argv[1], "a", encoding="utf-8") as fh:
    fh.write("|".join(os.environ[k] for k in sys.argv[2:]) + "\\n")
"""


def _script(tmp_path: Path) -> tuple[Path, str]:
    script = tmp_path / "notify.py"
    script.write_text(NOTIFY_SCRIPT, encoding="utf-8")
    out = tmp_path / "notified.txt"
    keys = " ".join((driver.NOTIFY_EVENT_ENV, driver.NOTIFY_RUN_ENV, driver.NOTIFY_TEXT_ENV))
    return out, f'"{sys.executable}" "{script}" "{out}" {keys}'


def test_the_real_notifier_runs_the_owners_command_with_the_end_in_its_env(tmp_path):
    out, command = _script(tmp_path)
    said: list[str] = []
    notify = driver.notifier(command, dict(os.environ), said.append)
    notify("STOPPED", "night1", "reverseapoc drive night1: STOPPED guardrail: a-b c/d.e")
    assert out.read_text(encoding="utf-8") == (
        "STOPPED|night1|reverseapoc drive night1: STOPPED guardrail: a-b c/d.e\n")
    assert said == []


@pytest.mark.parametrize("text", ["a & b | c", "%PATH% !x! ^y", "<in >out", 'q"uote', "$(id) `id`",
                                  "line1\nline2", "semi;colon"])  # fmt: skip
def test_the_notifier_env_text_holds_no_shell_metacharacter(tmp_path, text):
    # security review 2026-11-18: an owner command that expands the variable inline (cmd.exe
    # %VAR%, sh $VAR unquoted) must not be able to run session-derived text
    out, command = _script(tmp_path)
    notify = driver.notifier(command, dict(os.environ), [].append)
    notify("STOPPED", "night1", text)
    got = out.read_text(encoding="utf-8").rstrip("\n").split("|", 2)[2]
    assert set(got) <= set(driver.NOTIFY_SAFE_CHARS)
    assert len(got) == len(text)


def test_a_failing_notifier_is_named_and_never_raises(tmp_path):
    said: list[str] = []
    notify = driver.notifier(f'"{sys.executable}" -c "raise SystemExit(3)"', dict(os.environ),
                             said.append)  # fmt: skip
    notify("ENDED", "night1", "made up")
    assert said == [f"notifier ({driver.NOTIFY_ENV}) exit 3"]


def test_a_hung_notifier_is_killed_after_its_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "NOTIFY_TIMEOUT_S", 1)
    said: list[str] = []
    command = f'"{sys.executable}" -c "import time; time.sleep(60)"'
    started = time.monotonic()
    driver.notifier(command, dict(os.environ), said.append)("ENDED", "night1", "made up")
    assert time.monotonic() - started < 30
    assert said == [f"notifier ({driver.NOTIFY_ENV}) ran longer than 1 s; its process tree "
                    "was killed"]  # fmt: skip


def test_no_notifier_command_runs_nothing(tmp_path):
    said: list[str] = []
    for command in (None, "", "   "):
        driver.notifier(command, {}, said.append)("ENDED", "night1", "made up")
    assert said == []


def test_real_deps_wire_the_notifier_from_the_environment(tmp_path):
    out, command = _script(tmp_path)
    rig = Rig(tmp_path / "rig")
    seams = rig.seams(base_env={**rig.env, driver.NOTIFY_ENV: command})
    from test_drive import Packs, _world

    deps = driver.real_deps(rig.options(), seams, _world(Packs()))
    deps.notify("ENDED", "night1", "made up")
    assert out.read_text(encoding="utf-8") == "ENDED|night1|made up\n"


def test_sessions_never_see_the_notifier_command():
    from reverseapoc import backends

    arms = backends.load_arms()
    env = backends.session_env(arms[driver.MODEL], {driver.NOTIFY_ENV: "x", "KEEP": "1"}, arms)
    assert env == {"KEEP": "1"}
