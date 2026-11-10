"""The Antigravity CLI harness: Gemini 3.8 Flash and GPT-OSS 120B on the owner's Google AI Plus as
drive arms (07.2-15; D-21, D-24, D-25, D-25a, D-26).

Owner rule: no test runs the real `agy`. Every session here is tests/fakeagy.py replaying a
synthetic fixture under tests/fixtures/agy/; nothing contacts Google. Every environment is built
with made-up values over test_drive's key-free base, so a key the owner has set can never reach
an assertion or a log.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

from reverseapoc import agyjson, backends, driver, session
from reverseapoc.streamjson import Usage
from reverseapoc.targets import REPO_ROOT
from test_drive import Rig, _keyed
from test_driver import EXE, FUNC, LOG, RUN, UNIT, Night, Sess

HERE = Path(__file__).resolve().parent
FAKEAGY = HERE / "fakeagy.py"
FIXTURES = HERE / "fixtures" / "agy"
GEMINI = "gemini-flash"  # RULINGS "Plan 15, Antigravity arms" (D-25a)
GEMINI_MODEL = "gemini-3.8-flash-medium"
GPT_OSS = "gpt-oss"
GPT_OSS_MODEL = "gpt-oss-120b-medium"
AGY_VERSION = "1.5.3"
UNIT_PATH = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/view/src/{EXE}/{UNIT}.c"
REAL_DRIVE = driver.drive


def _events(name: str) -> tuple[dict, ...]:
    lines = (FIXTURES / f"{name}.jsonl").read_bytes().splitlines(keepends=True)
    return agyjson.parse(lines).events


def fake_agy_argv(prompt: str, *, model: str, attempt_dir: Path, settings: Path,
                  timeout_s: float) -> list[str]:  # fmt: skip
    """Deps.agy_argv for the tests: session.build_agy_argv with tests/fakeagy.py in the
    executable's place, so the fake checks the very argv the driver built."""
    real = session.build_agy_argv(prompt, agy="agy", model=model, attempt_dir=attempt_dir,
                                  settings=settings, timeout_s=timeout_s)  # fmt: skip
    return [sys.executable, str(FAKEAGY), *real[1:]]


def write_pass(repo: Path, arm: str = GEMINI, *, version: str = AGY_VERSION,
               result: str = "PASS") -> Path:  # fmt: skip
    """A canary-pass file as the agy canary writes it (RULINGS "Harness")."""
    path = repo / "build" / "driver" / "canary" / f"{arm}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"arm": arm, "harness": "agy", "cli_version": version,
                                "date": "2026-11-10", "result": result}), encoding="utf-8")
    return path


def agy_version_reply(rig: Rig, version: str = AGY_VERSION) -> None:
    """The rig's runner answers `agy --version` as the installed CLI would."""
    rig.runner.replies.append((lambda argv: argv == ["agy", "--version"],
                               (0, f"{version}\n", "")))  # fmt: skip


def agy_night(tmp_path: Path, monkeypatch, *, scenario: str = "gemini_success",
              extra_env: dict | None = None,
              spec: Sess | None = None) -> tuple[Rig, Night, dict]:  # fmt: skip
    """`drive` on a Rig whose night runs in test_driver's night harness with fakeagy sessions
    and a fake gate; the base env names the fixture and holds no key. `spec`: what the "agent"
    leaves besides the stream (Sess files are relative to the session's cwd, which for agy is
    its attempt dir)."""
    rig = Rig(tmp_path / "rig")
    agy_version_reply(rig)
    night = Night(tmp_path / "night", gate_exits=[1])
    night._current = spec or Sess(write=None)
    real = REAL_DRIVE  # never an earlier call's patch

    def drive(config, deps, *, lock=None):
        moved = replace(config, repo_root=night.repo, min_cli_version=(2, 1, 240),
                        attempts_per_function=1)  # fmt: skip
        return real(moved, night.deps(agy_argv=fake_agy_argv))

    monkeypatch.setattr(driver, "drive", drive)
    env = _keyed(rig.env, FAKEAGY_SCENARIO=scenario, **(extra_env or {}))
    return rig, night, env


def _run_agy(capsys, rig: Rig, env: dict, arm: str = GEMINI) -> tuple[int, str, str]:
    write_pass(rig.repo, arm)
    return rig.drive(capsys, seams={"base_env": env}, night_model=arm, allow_egress=(arm,),
                     workers=1)  # fmt: skip


# ---- Task 1: the arms, the argv, the stream and the record ----


def test_build_agy_argv(tmp_path):
    """D-21, D-24: `agy` with stream-json output, the model, the terminal sandbox, the attempt
    dir as the one added workspace, the driver's per-session settings file, no slash commands,
    the session's wall clock as the print timeout, and `-p` with the prompt last; never the
    flag that skips permissions."""
    attempt_dir = tmp_path / "attempt-1"
    settings = tmp_path / "agy" / "s.json"
    argv = session.build_agy_argv("the prompt", agy="agy.exe", model=GEMINI_MODEL,
                                  attempt_dir=attempt_dir, settings=settings,
                                  timeout_s=1800)  # fmt: skip
    assert argv == ["agy.exe", "--output-format", "stream-json", "--model", GEMINI_MODEL,
                    "--sandbox", "--add-dir", str(attempt_dir), "--settings", str(settings),
                    "--disable-slash-commands", "--print-timeout", "1800", "-p",
                    "the prompt"]  # fmt: skip
    assert argv[-2:] == ["-p", "the prompt"]
    assert "--dangerously-skip-permissions" not in argv


def test_agy_arms_load():
    """D-25, D-25a and RULINGS: the two Antigravity arms on the owner's AI Plus sign-in: no
    endpoint, no key variable, their exact init id, free on the subscription, one worker,
    sending the pack to Google (so --allow-egress)."""
    arms = backends.load_arms()
    for name, model, credit in ((GEMINI, GEMINI_MODEL, "Gemini 3.8 Flash <noreply@google.com>"),
                                (GPT_OSS, GPT_OSS_MODEL, "gpt-oss-120b <noreply@openai.com>")):
        arm = arms[name]
        assert (arm.harness, arm.backend, arm.model) == ("agy", "google", model), name
        assert (arm.base_url, arm.key_env, arm.accepted_init) == (None, None, (model,))
        assert arm.prices == (0.0, 0.0, 0.0, 0.0) and arm.coauthor == credit
        assert arm.max_workers == 1 and arm.egress


def test_each_agy_arm_builds_a_valid_argv(tmp_path):
    """RULINGS "Plan 15, Antigravity arms": each entry builds an argv the fake agy accepts, with
    its exact model id."""
    import fakeagy

    arms = backends.load_arms()
    for name, model in ((GEMINI, GEMINI_MODEL), (GPT_OSS, GPT_OSS_MODEL)):
        argv = session.build_agy_argv("p", agy="agy", model=arms[name].model,
                                      attempt_dir=tmp_path, settings=tmp_path / "s.json",
                                      timeout_s=session.TIMEOUT_S)  # fmt: skip
        assert fakeagy._problem(argv[1:]) is None, name
        assert argv[argv.index("--model") + 1] == model


def test_agy_prompt():
    """Built as the Codex prompt is: the matching goal without /goal, the watcom-decomp skill's
    body without its front matter, and the session rules; no orig/ path."""
    goal = session.goal_prompt(FUNC, UNIT, EXE, unit_path=UNIT_PATH)
    skill = (REPO_ROOT / session.SKILL).read_text(encoding="utf-8")
    prompt = session.agy_prompt(goal, skill)
    assert prompt == session.codex_prompt(goal, skill)
    assert goal.removeprefix("/goal ") in prompt and "# Matching one Watcom function" in prompt
    assert "orig/" not in prompt


def test_agyjson_init_problems(tmp_path):
    """An init whose cwd is the attempt dir, whose model is the requested slug and whose
    permission mode is not a bypass is clean; another cwd, another model or a bypass mode each
    name the problem; no init event is a problem."""
    good = {"type": "init", "cwd": str(tmp_path), "model": GEMINI_MODEL, "tools": ["x"],
            "permission_mode": "default"}  # fmt: skip
    assert agyjson.init_problems(good, cwd=tmp_path, model=GEMINI_MODEL) == []
    for change, word in (({"cwd": str(tmp_path / "other")}, "cwd"),
                         ({"model": "gemini-3.8-flash-high"}, "model"),
                         ({"permission_mode": "bypassPermissions"}, "permission"),
                         ({"permission_mode": "dangerously_skip_permissions"}, "permission")):
        problems = agyjson.init_problems({**good, **change}, cwd=tmp_path, model=GEMINI_MODEL)
        assert len(problems) == 1 and word in problems[0], (change, problems)
    assert agyjson.init_problems(None, cwd=tmp_path, model=GEMINI_MODEL) == ["no init event"]
    assert agyjson.init_event(_events("gemini_success"))["permission_mode"] == "default"


def test_agyjson_usage_and_turns():
    """The result's usage: input, output plus thinking, cache_read, no cache creation, no
    cost; `num_turns` gives the turns and `duration_seconds` the duration in ms; the malformed
    line is counted and skipped."""
    lines = (FIXTURES / "usage_malformed.jsonl").read_bytes().splitlines(keepends=True)
    parsed = agyjson.parse(lines)
    assert parsed.malformed == 1
    assert agyjson.turns(parsed.events) == 2
    assert agyjson.usage(parsed.events) == Usage(
        input_tokens=3000, output_tokens=650, cache_read_tokens=2100, cache_creation_tokens=0,
        turns=2, cost_usd=0.0, duration_ms=12250)  # fmt: skip
    assert agyjson.usage(()) == Usage(0, 0, 0, 0, 0, 0.0, 0)


def test_agyjson_commands_writes_denied():
    """Step updates give the commands and written paths in order, each step once; a step the
    result's denied_actions name never ran, so it is in neither list; the denied actions are
    returned as `action(target)`; a result status other than SUCCESS gives a failure text."""
    events = _events("commands_and_writes")
    assert agyjson.commands(events) == ["uv run --frozen reverseapoc attempt context",
                                        "type notes.md"]  # fmt: skip
    assert agyjson.write_targets(events) == ["notes.md", "view/src/ufo2p/u_00010000.c"]
    assert agyjson.read_targets(events) == ["context.md"]
    assert agyjson.denied_actions(events) == ["command(rm made-up.txt)"]
    failure = agyjson.failure(events)
    assert failure is not None and "ERROR" in failure and "made-up failure" in failure
    assert agyjson.failure(_events("gemini_success")) is None
    assert agyjson.denied_actions(_events("gemini_success")) == ["command(type notes.md)"]


def test_drive_agy_arm_records(tmp_path, capsys, monkeypatch):
    """A Gemini night launches tests/fakeagy.py in its attempt dir under a settings file the
    driver wrote outside it, and records harness agy, backend google, the requested slug, the
    init's model, the fixture's tokens, an estimated cost and the denied actions as blocks."""
    rig, night, env = agy_night(tmp_path, monkeypatch)
    code, _, err = _run_agy(capsys, rig, env)
    assert code == 0, err
    launched = night.launched[0]
    assert launched.argv[:3] == [sys.executable, str(FAKEAGY), "--output-format"]
    assert launched.argv[launched.argv.index("--model") + 1] == GEMINI_MODEL
    assert launched.cwd == night.attempt_dir()
    assert "# Matching one Watcom function" in launched.argv[-1]
    settings = Path(launched.argv[launched.argv.index("--settings") + 1])
    name = f"{EXE}__{FUNC}__attempt-1.json"
    assert settings == night.repo / "build" / "driver" / RUN / "agy" / name
    assert settings.is_file() and not settings.is_relative_to(night.attempt_dir())
    record = night.kinds("attempt")[0]
    driver.validate_record(record)
    assert (record["harness"], record["backend"], record["model_requested"]) == (
        "agy", "google", GEMINI_MODEL)  # fmt: skip
    assert record["model"] == GEMINI_MODEL and record["cli_version"] is None
    assert record["tokens"] == {"input": 4000, "output": 700, "cache_read": 1500,
                                "cache_creation": 0}  # fmt: skip
    assert (record["turns"], record["duration_ms"], record["hook_blocks"]) == (3, 42500, 1)
    assert (record["cost_source"], record["cost_usd"]) == ("estimate", 0.0)
    assert (night.repo / LOG).is_file()


def test_agy_init_problem_stops_the_night(tmp_path, capsys, monkeypatch):
    """init_problems is a STOP condition like check_init: an init naming another cwd stops the
    night with reason init."""
    rig, night, env = agy_night(tmp_path, monkeypatch, scenario="gemini_wrong_cwd")
    code, _, _ = _run_agy(capsys, rig, env)
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.INIT and "cwd" in stopped["detail"], stopped


LEAKS = {"OPENAI_API_KEY": "made-up-openai-0001", "OPENAI_BASE_URL": "https://x.invalid",
         "DEEPSEEK_API_KEY": "made-up-0002", "ZAI_API_KEY": "made-up-0003",
         "OPENROUTER_API_KEY": "made-up-0004", "ANTHROPIC_API_KEY": "made-up-0005",
         "ANTHROPIC_AUTH_TOKEN": "made-up-0006", "ANTHROPIC_BASE_URL": "https://y.invalid",
         "ANTHROPIC_MODEL": "made-up", "GOOGLE_API_KEY": "made-up-0007",
         "GEMINI_API_KEY": "made-up-0008"}  # fmt: skip


def test_agy_env_has_no_keys(tmp_path, capsys, monkeypatch):
    """D-12 and RULINGS "Token-leak guard covers every arm": the agy session uses the owner's
    AI Plus sign-in, so its env holds no arm key variable, no GEMINI_API_KEY or GOOGLE_API_KEY,
    no ANTHROPIC_* variable and neither OPENAI_API_KEY nor OPENAI_BASE_URL."""
    record = tmp_path / "fakeagy-record.json"
    rig, night, env = agy_night(tmp_path, monkeypatch,
                                extra_env={"FAKEAGY_RECORD": str(record), **LEAKS})
    code, _, err = _run_agy(capsys, rig, env)
    assert code == 0, err
    names = set(json.loads(record.read_text(encoding="utf-8"))["env"])
    assert names, "the fake agy wrote no env"
    assert sorted(names & set(LEAKS)) == []
    assert [n for n in names if n.upper().startswith("ANTHROPIC_")] == []


def test_agy_session_env_strips_every_other_vendor():
    """The env builder itself (RULINGS: one test on the session env): an agy arm's session loses
    every ANTHROPIC_* variable, OPENAI_API_KEY, OPENAI_BASE_URL, every arm key and the Google
    key variables; nothing else is dropped and no endpoint is added."""
    arms = backends.load_arms()
    base = {"PATH": "made-up-path", "OPENAI_API_KEY": "made-up", "OPENAI_BASE_URL": "made-up",
            "DEEPSEEK_API_KEY": "made-up", "ANTHROPIC_API_KEY": "made-up",
            "ANTHROPIC_SMALL_FAST_MODEL": "made-up", "GOOGLE_API_KEY": "made-up",
            "GEMINI_API_KEY": "made-up", "GOOGLE_GENAI_API_KEY": "made-up"}  # fmt: skip
    for name in (GEMINI, GPT_OSS):
        env = backends.session_env(arms[name], base, arms)
        assert sorted(env) == ["PATH", "REVERSEAPOC_EGRESS"], name


# ---- Task 2: per-session settings under build/ and the agy audit (D-24, D-26) ----

ATTEMPT = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1"
WRAPPER = "uv run --frozen reverseapoc attempt"
SETTINGS_NAME = f"{EXE}__{FUNC}__attempt-1.json"
LEDGER_NAME = f"{EXE}__{FUNC}__attempt-1.jsonl"


def _rule(rules: list[str], action: str) -> list[str]:
    return [r[len(action) + 1:-1] for r in rules if r.startswith(f"{action}(") and r.endswith(")")]


def test_session_settings_allow_only_the_wrapper(tmp_path, capsys, monkeypatch):
    """D-24: the driver writes the session's settings under build/driver/<run>/agy/, outside
    the workspace and never in the repo or the user's settings: allow holds one command regex
    matching exactly the matching wrapper forms and write_file rules for exactly the session's
    files; deny holds a command regex naming orig/ and third_party/, their reads and writes,
    and unsandboxed commands. The session is told its wrapper ledger, which starts empty."""
    import re

    record = tmp_path / "fakeagy-record.json"
    rig, night, env = agy_night(tmp_path, monkeypatch, extra_env={"FAKEAGY_RECORD": str(record)})
    code, _, err = _run_agy(capsys, rig, env)
    assert code == 0, err
    path = night.repo / "build" / "driver" / RUN / "agy" / SETTINGS_NAME
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert set(doc) == {"permissions"} and set(doc["permissions"]) == {"allow", "deny"}
    allow, deny = doc["permissions"]["allow"], doc["permissions"]["deny"]
    commands = _rule(allow, "command")
    assert len(commands) == 1 and commands[0].startswith("regex:")
    wrapper = re.compile(commands[0].removeprefix("regex:"))
    for form in ("context", "check", "check --sweep", "asm", "asm func_00010010", "plan",
                 "giveup"):  # fmt: skip
        assert wrapper.fullmatch(f"{WRAPPER} {form}"), form
    for bad in ("type notes.md", f"{WRAPPER} check --src x", f"{WRAPPER} check; echo x",
                f"{WRAPPER} asm a b", f"{WRAPPER} giveup x", f"x {WRAPPER} check"):
        assert not wrapper.fullmatch(bad), bad
    attempt_dir = night.attempt_dir()
    files = {(attempt_dir / rel).as_posix() for rel in
             ("notes.md", "plan.json", "check-note.json", "giveup.json",
              f"view/src/{EXE}/{UNIT}.c")}  # fmt: skip
    assert set(_rule(allow, "write_file")) == files and len(allow) == 1 + len(files)
    named = re.compile(_rule(deny, "command")[0].removeprefix("regex:"))
    for text in (f"{WRAPPER} asm orig", "type ..\\ORIG\\x", "ls third_party/watcom"):
        assert named.fullmatch(text), text
    assert not named.fullmatch(f"{WRAPPER} check")
    root = night.repo.as_posix()
    for action in ("read_file", "write_file"):
        assert set(_rule(deny, action)) == {f"{root}/orig/**", f"{root}/third_party/**"}
    assert _rule(deny, "unsandboxed") == ["regex:.*"]
    assert not path.is_relative_to(attempt_dir)
    assert not (night.repo / ".gemini").exists() and not (rig.repo / ".gemini").exists()
    ledger = Path(night.launched[0].env[driver.attempt.WRAPPER_LEDGER_ENV])
    assert ledger == night.repo / "build" / "driver" / RUN / "ledger" / LEDGER_NAME
    assert ledger.read_bytes() == b""
    names = json.loads(record.read_text(encoding="utf-8"))["env"]
    assert driver.attempt.WRAPPER_LEDGER_ENV in names


def test_session_settings_path_is_gitignored():
    """The settings file lies in gitignored build/ (the acceptance check's own path)."""
    import subprocess

    done = subprocess.run(["git", "check-ignore", "-q", "build/driver/x/agy/s.json"],
                          cwd=REPO_ROOT, check=False)  # fmt: skip
    assert done.returncode == 0


def _outside(tmp_path: Path) -> Path:
    outside = tmp_path / "outside"
    (outside / "attempt-cache").mkdir(parents=True)
    (outside / "attempt-cache" / "x.json").write_text("{}\n", encoding="utf-8")
    return outside


AUDIT_CASES = {  # name: (scenario, spec, words in the STOPPED detail)
    "non-wrapper command": ("stray_command", None, "type notes.md"),
    "command naming orig": ("orig_command", None, "names orig/"),
    "read naming third_party": ("orig_read", None, "third_party"),
    "write outside the allowlist": ("stray_write", None, "tools/x.py"),
    "stray file": ("gemini_success", Sess(write=None, files=(("x.txt", "made up\n"),)), "x.txt"),
    "session-written agy config": ("gemini_success",
                                   Sess(write=None, files=((".gemini/settings.json", "{}\n"),)),
                                   ".gemini/settings.json"),
    "changed settings file": ("gemini_success",
                              Sess(write=None, append=((f"../../../agy/{SETTINGS_NAME}", "\n"),)),
                              f"agy/{SETTINGS_NAME}"),
    "forged checks.jsonl": ("gemini_success", "checks", "checks.jsonl"),
    "linked view/build": ("gemini_success", "link", "view/build"),
}


def test_agy_audit_flags(tmp_path, capsys, monkeypatch):
    """D-26 and the Codex review's findings: the agy stream's own commands, writes and reads,
    the attempt dir against the launch inventory and the wrapper ledger, and the settings
    file: a non-wrapper command, a command or read naming orig/ or third_party/, a write
    outside the allowlist, a stray file, a session-written .gemini/ config, a changed settings
    file, a checks.jsonl the ledger never saw and a linked view/build each stop the night at
    the guardrail; the linked directory's target keeps its files."""
    from test_driver import check_line

    for name, (scenario, spec, words) in AUDIT_CASES.items():
        here = tmp_path / name.replace(" ", "_").replace("/", "_")
        if spec == "checks":
            spec = Sess(write=None, checks=(check_line(1, 100.0, exit_code=0),))
        elif spec == "link":
            spec = Sess(write=None, link=("view/build", _outside(here)))
        rig, night, env = agy_night(here, monkeypatch, scenario=scenario, spec=spec)
        code, _, _ = _run_agy(capsys, rig, env)
        assert code != 0, name
        stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
        assert stopped["reason"] == driver.GUARDRAIL and words in stopped["detail"], (name, stopped)
        if name == "linked view/build":
            assert (here / "outside" / "attempt-cache" / "x.json").is_file()


def test_agy_audit_clean_session(tmp_path, capsys, monkeypatch):
    """A session that ran only wrapper forms and wrote only its allowlisted files is clean: no
    guardrail stop, the attempt recorded."""
    rig, night, env = agy_night(tmp_path, monkeypatch)
    code, _, err = _run_agy(capsys, rig, env)
    assert code == 0, err
    assert [r for r in night.kinds("run") if r["event"] == "STOPPED"] == []
    assert night.kinds("attempt")[0]["abort_reason"] != driver.GUARDRAIL


def test_agy_denied_actions_are_not_strays(tmp_path, capsys, monkeypatch):
    """Headless agy soft-denies what its settings do not allow: a denied command and a denied
    write never ran, so they count as hook blocks, not strays."""
    rig, night, env = agy_night(tmp_path, monkeypatch, scenario="denied_steps")
    code, _, err = _run_agy(capsys, rig, env)
    assert code == 0, err
    assert [r for r in night.kinds("run") if r["event"] == "STOPPED"] == []
    assert night.kinds("attempt")[0]["hook_blocks"] == 2
