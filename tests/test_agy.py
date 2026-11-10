"""The Antigravity CLI harness: Gemini 3.8 Flash and GPT-OSS 120B on the owner's Google AI Plus as
drive arms (07.2-15; D-21, D-24, D-25, D-25a, D-26).

Owner rule: no test runs the real `agy`. Every session here is tests/fakeagy.py replaying a
synthetic fixture under tests/fixtures/agy/; nothing contacts Google. Every environment is built
with made-up values over test_drive's key-free base, so a key the owner has set can never reach
an assertion or a log.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from reverseapoc import agyjson, backends, driver, session
from reverseapoc.streamjson import Disposition, Usage
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
                    "--disable-slash-commands", "--print-timeout", "1800s", "-p",
                    "the prompt"]  # fmt: skip
    assert argv[-2:] == ["-p", "the prompt"]
    assert "--dangerously-skip-permissions" not in argv


def test_agy_arms_load():
    """D-25, D-25a and RULINGS: the two Antigravity arms on the owner's AI Plus sign-in: no
    endpoint, no key variable, their exact init id, a subscription arm, one worker, sending
    the pack to Google (so --allow-egress). Quick 261110-f30: their prices are the public API
    list prices, for the comparison only (gpt-oss has no cached price: cache_read as input)."""
    from reverseapoc.streamjson import Price

    arms = backends.load_arms()
    prices = {GEMINI: Price(0.75, 3.75, 0.075, 0.75), GPT_OSS: Price(0.04, 0.18, 0.04, 0.04)}
    for name, model, credit in ((GEMINI, GEMINI_MODEL, "Gemini 3.8 Flash <noreply@google.com>"),
                                (GPT_OSS, GPT_OSS_MODEL, "gpt-oss-120b <noreply@openai.com>")):
        arm = arms[name]
        assert (arm.harness, arm.backend, arm.model) == ("agy", "google", model), name
        assert (arm.base_url, arm.key_env, arm.accepted_init) == (None, None, (model,))
        assert arm.prices == prices[name] and arm.coauthor == credit
        assert arm.max_workers == 1 and arm.egress
        assert arm.billing == backends.SUBSCRIPTION


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


def test_fake_agy_rejects_a_unitless_print_timeout(tmp_path):
    """Canary 2026-11-10: agy 1.5.5 parses --print-timeout as a Go duration and exits on
    `invalid value "1200" for flag -print-timeout: time: missing unit in duration`, so the fake
    refuses a bare number the same way; the driver's whole seconds carry an `s` unit."""
    import fakeagy

    argv = session.build_agy_argv("p", agy="agy", model=GEMINI_MODEL, attempt_dir=tmp_path,
                                  settings=tmp_path / "s.json", timeout_s=1200)[1:]  # fmt: skip
    assert argv[argv.index("--print-timeout") + 1] == "1200s"
    assert fakeagy._problem(argv) is None
    timeout = argv.index("--print-timeout") + 1
    for bad in ("1200", "0s", "12.5s", "20m"):
        argv[timeout] = bad
        assert "--print-timeout" in fakeagy._problem(argv), bad


def test_agy_prompt(tmp_path):
    """Built as the Codex prompt is: the matching goal without /goal, the watcom-decomp skill's
    body without its front matter, the harness note and the session rules; no orig/ path.
    07.2 review WR-10: agy's settings also allow its read_file tool inside the attempt dir and
    nowhere else, so its harness note says exactly that, besides the Codex note's wrapper
    forms; the rest of the prompt is the Codex one."""
    goal = session.goal_prompt(FUNC, UNIT, EXE, unit_path=UNIT_PATH)
    skill = (REPO_ROOT / session.SKILL).read_text(encoding="utf-8")
    prompt = session.agy_prompt(goal, skill)
    codex = session.codex_prompt(goal, skill)
    assert goal.removeprefix("/goal ") in prompt and "# Matching one Watcom function" in prompt
    assert "orig/" not in prompt
    [note] = [part for part in prompt.split("\n\n") if part.startswith("Harness note:")]
    [codex_note] = [part for part in codex.split("\n\n") if part.startswith("Harness note:")]
    assert prompt == codex.replace(codex_note, note)
    assert note.startswith(codex_note)
    assert "read_file" in note and "inside this attempt's directory" in note
    claim = driver._Claim(driver.Pick(EXE, 0x1000, "func_00001000", UNIT, 20, 1), RUN,
                          tmp_path / "repo", 1, arm=backends.load_arms()[GEMINI])  # fmt: skip
    reads = _rule(driver.agy_settings(claim)["permissions"]["allow"], "read_file")
    assert reads == [f"{claim.attempt_dir.as_posix()}/**"]


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


def test_agyjson_reads_the_agy_1_5_5_envelope():
    """Spike 012 round-2 canaries: agy 1.5.5 streams each event as {"event": kind, kind:
    {...}}, and a write step names its path as tool_info.parameters.Path. The fixture copies
    that real stream's shape (made-up paths and numbers): its init, its one turn, its usage, its
    soft-denied write (the step itself ends ERROR, so it counts as a write the audit judges) and
    its result are all read; no step is unknown."""
    events = _events("canary_agy_soft_denied")
    init = agyjson.init_event(events)
    assert init is not None and init["permission_mode"] == "request-review", init
    assert (init["cwd"], init["model"]) == ("@cwd", "@model")
    assert agyjson.turns(events) == 1
    assert agyjson.usage(events) == Usage(
        input_tokens=9000, output_tokens=2100, cache_read_tokens=0, cache_creation_tokens=0,
        turns=1, cost_usd=0.0, duration_ms=10500)  # fmt: skip
    assert agyjson.write_targets(events) == ["C:\\made-up\\func_000A3980\\agy-canary-outside.txt"]
    assert agyjson.read_targets(events) == [] and agyjson.commands(events) == []
    assert agyjson.unknown_steps(events) == []
    assert agyjson.failure(events) is None
    assert agyjson.classify(events, 0, False) == Disposition.ATTEMPT_DONE


CONTEXT, PLAN, CHECK = (f"uv run --frozen reverseapoc attempt {form}"
                        for form in ("context", "plan", "check"))  # fmt: skip


def test_agyjson_reads_the_real_run_command_step():
    """Spike 012 round 3: agy 1.5.5's run_command step is tool_info {name: run_command,
    parameters: {CommandLine: <the command>}, output: <text>}, the output (once DONE) reading
    `Command exited with code <n>.` and `Command output:`. The fixture copies the real allowed
    session's shape (placeholder output): commands() reads each CommandLine once, in order, and
    no step is unknown. The same step with another parameter (a Cwd), another tool_info key, a
    tool_info name that is not its tool's or a CommandLine that is no string is unknown (a
    stray, fail closed), and its command never counts as run."""
    events = _events("canary_agy_allowed")
    assert agyjson.commands(events) == [CONTEXT, PLAN, CHECK]
    assert agyjson.unknown_steps(events) == []
    assert agyjson.write_targets(events) == ["C:\\made-up\\attempt-1\\plan.json",
                                             "C:\\made-up\\attempt-1\\check-note.json"]
    assert agyjson.read_targets(events) == []
    line = {"CommandLine": CHECK}
    odd = [_step(1, "run_command", name="run_command", parameters={**line, "Cwd": "C:\\x"}),
           _step(2, "run_command", name="run_command", parameters=line, exit_code=0),
           _step(3, "run_command", name="list_dir", parameters=line),
           _step(4, "run_command", name="run_command", parameters={"CommandLine": [CHECK]})]
    found = agyjson.unknown_steps(odd)
    assert [text.split(":")[0] for text in found] == [f"step {n}" for n in range(1, 5)], found
    assert agyjson.commands(odd) == []


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


def _wrapped(kind: str, **payload) -> dict:
    """One event in agy 1.5.5's envelope."""
    return {"event": kind, kind: payload}


def _step(index: int, tool: str, *, state: str = "DONE", subagent: dict | None = None,
          **info) -> dict:  # fmt: skip
    step = {"step_index": index, "state": state, "step_type": "TOOL", "tool_name": tool,
            "tool_info": info}  # fmt: skip
    return _wrapped("step_update", **step, **({"subagent_info": subagent} if subagent else {}))


def _run(index: int, command: str, *, state: str = "DONE", **info) -> dict:
    """A run_command step in agy 1.5.5's real shape (spike 012 round 3)."""
    return _step(index, "run_command", state=state, name="run_command",
                 parameters={"CommandLine": command}, **info)  # fmt: skip


def test_agyjson_only_a_steps_own_denied_state_hides_it():
    """07.2 review WR-02: a step is dropped as denied only when the step itself ends DENIED. A
    result's denied action never hides a step that ran, whatever its kind, target or count
    (it is a hook block, nothing more)."""
    target = "../../../orig/UFO2P.EXE"
    events = [_run(1, target),
              _step(2, "read_file", path=target),
              _step(3, "read_file", path=target, state="DENIED"),
              _step(4, "write_file", path=target),
              _wrapped("result", status="SUCCESS",
                       denied_actions=[f"command({target})", f"read_file({target})",
                                       f"write_file({target})"])]  # fmt: skip
    assert agyjson.commands(events) == [target]
    assert agyjson.read_targets(events) == [target]
    assert agyjson.write_targets(events) == [target]
    unsandboxed = [_run(1, "type notes.md"),
                   _wrapped("result", status="SUCCESS",
                            denied_actions=["unsandboxed(type notes.md)"])]  # fmt: skip
    assert agyjson.commands(unsandboxed) == ["type notes.md"]


def test_agyjson_denials_read_the_permission_error():
    """Spike 012: a soft-denied step ends ERROR with tool_info.error.message `permission check
    failed for <action> "<target>": user denied permission for ...` (agy's own format, the
    result's denied_actions name no target), so `denials` reads the action and the target from
    that message. A step that itself ends DENIED is a denial by its tool and its path or
    command. An ERROR with any other message ran and failed, and a DONE step ran: neither is a
    denial, and `undenied_steps` names both."""
    events = _events("canary_agy_soft_denied")
    outside = "C:/made-up/func_000A3980/agy-canary-outside.txt"
    assert agyjson.denials(events) == [agyjson.Denial(2, "write_file", "write_file", outside)]
    assert agyjson.undenied_steps(events) == []
    message = 'permission check failed for command "echo \\"a\\" > C:\\\\x": user denied ...'
    mixed = [_step(1, "run_command", state="ERROR", error={"type": "TOOL_ERROR",
                                                           "message": message}),
             _step(2, "read_file", state="DENIED", path="../orig/x.txt"),
             _step(3, "read_file", state="ERROR", path="a.txt",
                   error={"type": "TOOL_ERROR", "message": "file not found"}),
             _step(4, "write_file", path="notes.md")]  # fmt: skip
    assert agyjson.denials(mixed) == [agyjson.Denial(1, "run_command", "command",
                                                     'echo "a" > C:\\x'),
                                      agyjson.Denial(2, "read_file", "read_file",
                                                     "../orig/x.txt")]  # fmt: skip
    assert agyjson.undenied_steps(mixed) == ["step 3: read_file (ERROR)",
                                             "step 4: write_file (DONE)"]  # fmt: skip
    assert agyjson.response(_events("canary_agy_refused")) == "I'm sorry, but I can't help."


def test_agyjson_ignores_a_line_outside_the_envelope():
    """A line that is not agy 1.5.5's envelope (the flat shape RESEARCH assumed) is no event:
    no init, no result, no step."""
    flat = [{"type": "init", "cwd": ".", "model": GEMINI_MODEL, "permission_mode": "default"},
            {"type": "step_update", "step_index": 1, "state": "DONE", "step_type": "TOOL",
             "tool_name": "write_file", "tool_info": {"path": "notes.md"}},
            {"type": "result", "status": "SUCCESS", "num_turns": 1}]  # fmt: skip
    assert agyjson.init_event(flat) is None and agyjson.turns(flat) == 0
    assert agyjson.write_targets(flat) == [] and agyjson.unknown_steps(flat) == []


def test_agyjson_reads_are_an_allowlist():
    """WR-02: only a read-only tool the audit knows (read_file) is a read; any other tool step
    that names a path is judged as a write, so an unknown writing tool never passes as a read
    inside the checkout."""
    events = [_step(1, "view_file", path="context.md"), _step(2, "read_file", path="notes.md"),
              _step(3, "write_to_file", path="notes.md")]
    assert agyjson.read_targets(events) == ["notes.md"]
    assert agyjson.write_targets(events) == ["context.md", "notes.md"]


def test_agyjson_unknown_steps():
    """WR-02: a tool step that ran is a stray unless it is a tool the audit knows in its known
    shape: run_command in agy 1.5.5's real shape (parameters.CommandLine), read_file or
    write_file with a path. A missing or non-string tool name, an unknown tool (a fetch, a
    listing, a search, the real manage_task a model polls a background command with), a known
    tool without its field or in the documented but never seen `tool_info.command` shape, and
    a subagent step are each named; a denied step and a step that is no tool step (model text)
    are not."""
    real = {"name": "run_command", "parameters": {"CommandLine": CHECK}}
    stray = [_step(1, "web_fetch", url="https://made-up.invalid/"),
             _step(2, "list_dir", path="."),
             _wrapped("step_update", step_index=3, state="DONE", step_type="TOOL",
                      tool_info=real),
             _wrapped("step_update", step_index=4, state="DONE", step_type="TOOL",
                      tool_name=["run_command"], tool_info=real),
             _step(5, "read_file", query="orig"),
             _step(6, "run_command", path="notes.md"),
             _step(7, "run_command", **real, subagent={"name": "made-up"}),
             _step(8, "run_command", command=CHECK),
             _step(9, "manage_task", name="manage_task",
                   parameters={"Action": "status", "TaskId": "made-up/task-10"},
                   output="Status: RUNNING")]  # fmt: skip
    fine = [_step(10, "run_command", **real, output="Command exited with code 0."),
            _step(11, "read_file", path="context.md"), _step(12, "write_file", path="notes.md"),
            _step(13, "web_fetch", state="DENIED", url="https://made-up.invalid/"),
            _wrapped("step_update", step_index=14, state="DONE", step_type="PLANNER_RESPONSE",
                     text_delta="made-up text")]  # fmt: skip
    found = agyjson.unknown_steps([*stray, *fine])
    assert len(found) == len(stray), found
    for index, text in zip(range(1, len(stray) + 1), found, strict=True):
        assert f"step {index}" in text, (index, text)


def test_an_unknown_agy_tool_stops_the_night(tmp_path, capsys, monkeypatch):
    """WR-02 at night: a session whose stream holds a tool step the audit does not know (here
    a URL fetch that names no command and no path) stops the night at the guardrail."""
    rig, night, env = agy_night(tmp_path, monkeypatch, scenario="unknown_tool")
    code, _, _ = _run_agy(capsys, rig, env)
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.GUARDRAIL and "web_fetch" in stopped["detail"], stopped


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
    files; deny holds a command regex naming orig/ and third_party/ and their reads and
    writes. No `unsandboxed(...)` rule: agy 1.5.5 ignores it and grants nothing ("unsandboxed
    is no longer a valid rule, use command() instead"), and an unallowed command soft-denies
    anyway, so the canary's unsandboxed probe is the proof. The session is told its wrapper
    ledger, which starts empty."""
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
    assert set(_rule(allow, "write_file")) == files
    # security review round 2: reads are allowed in the attempt dir only (an allow list:
    # headless agy soft-denies the unconfigured rest)
    assert _rule(allow, "read_file") == [f"{attempt_dir.as_posix()}/**"]
    assert len(allow) == 2 + len(files)
    named = re.compile(_rule(deny, "command")[0].removeprefix("regex:"))
    for text in (f"{WRAPPER} asm orig", "type ..\\ORIG\\x", "ls third_party/watcom"):
        assert named.fullmatch(text), text
    assert not named.fullmatch(f"{WRAPPER} check")
    root = night.repo.as_posix()
    for action in ("read_file", "write_file"):
        rules = _rule(deny, action)
        assert {f"{root}/orig/**", f"{root}/third_party/**"} <= set(rules), rules
        for part in ("orig", "third_party"):  # the backslash form of the same roots
            assert f"{str(night.repo)}\\{part}\\**" in rules, (action, part)
        spelled = [re.compile(r.removeprefix("regex:")) for r in rules if r.startswith("regex:")]
        assert len(spelled) == 3, rules

        def denied(text: str, spelled=spelled) -> bool:
            return any(rule.fullmatch(text) for rule in spelled)

        for text in ("../../../../../../orig/UFO2P.EXE", "C:\\x\\ORIG\\TACP.EXE",
                     "c:/x/Third_Party/watcom/h/stdio.h", "..\\..\\orig",
                     # round 3: a `..` segment behind the allowed prefix, and 8.3 short names
                     f"{attempt_dir.as_posix()}/../../../../../../x/UFO2P.EXE",
                     f"{attempt_dir}\\..\\notes.md", "C:/x/THIRD_~1/watcom/x.h",
                     "c:\\x\\ORIGIN~2\\a"):  # fmt: skip
            assert denied(text), (action, text)
        for text in ("view/src/ufo2p/original_x.c", "notes.md", "origins/x",
                     f"{attempt_dir.as_posix()}/..x/y", *sorted(files)):  # fmt: skip
            assert not denied(text), (action, text)
    assert not [rule for rule in (*allow, *deny) if rule.startswith("unsandboxed")], deny
    assert not path.is_relative_to(attempt_dir)
    assert not (night.repo / ".gemini").exists() and not (rig.repo / ".gemini").exists()
    ledger = Path(night.launched[0].env[driver.attempt.WRAPPER_LEDGER_ENV])
    assert ledger == night.repo / "build" / "driver" / RUN / "ledger" / LEDGER_NAME
    assert ledger.read_bytes() == b""
    names = json.loads(record.read_text(encoding="utf-8"))["env"]
    assert driver.attempt.WRAPPER_LEDGER_ENV in names


def test_session_settings_path_is_gitignored():
    """The settings file lies in gitignored build/ (the acceptance check's own path).
    safe.directory=* as in test_hygiene (ruling F13): the container's bind mount has another
    owner, and git refuses it without."""
    import subprocess

    done = subprocess.run(["git", "-c", "safe.directory=*", "check-ignore", "-q",
                           "build/driver/x/agy/s.json"],
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


# ---- Task 3: the quota canary, its pass gate, the fallback arm and the exception text ----

FALLBACK = "gemini-3.8-flash-openrouter"
USAGE_ARGV = ["agy", "-p", "/usage"]


ALLOWED = "allowed"
PROBES = ("outside-write", "fetch", "unsandboxed", "relative-read", "different-case-read",
          "dot-dot-read", "short-name-read")  # fmt: skip
# each session's default scenario: the allowed path's wrapper flow and each probe denied the
# way spike 012 captured it (the step ends ERROR with the permission check's message)
SCENARIOS = {ALLOWED: "canary_agy_allowed", "outside-write": "canary_agy_soft_denied",
             "fetch": "canary_agy_deny_fetch", "unsandboxed": "canary_agy_deny_unsandboxed",
             **{name: "canary_agy_deny_read" for name in PROBES if name.endswith("-read")}}
CANARY_LEFT = {"outside-write": "agy-canary-outside.txt",
               "unsandboxed": "agy-canary-unsandboxed.txt"}  # fmt: skip


def _read_spellings(attempt_dir: Path, repo: Path) -> dict[str, tuple[str, str]]:
    """Each orig/ read probe's spelling as its prompt asks for it, and the plain spelling of
    the same file a model could read instead (the long, absolute, as-cased path)."""
    probe = driver.AGY_CANARY_PROBE
    relative = Path(os.path.relpath(repo / "orig" / probe, attempt_dir)).as_posix()
    plain = str(repo / "orig" / probe)
    return {"relative-read": (relative, plain),
            "different-case-read": (str(repo / "ORIG" / probe), plain),
            "dot-dot-read": (f"{attempt_dir.as_posix()}/{relative}", plain),
            "short-name-read": (str(repo / "THIRD_~1" / probe),
                                str(repo / "third_party" / probe))}  # fmt: skip


def _filled(value: object, slots: dict[str, tuple[str, str]]) -> object:
    """`value` with each slot filled: Go-quoted (as agy's permission message quotes its
    target) where the slot stands in quotes, else as written."""
    if isinstance(value, dict):
        return {key: _filled(item, slots) for key, item in value.items()}
    if not isinstance(value, str):
        return value
    for slot, (quoted, bare) in slots.items():
        value = value.replace(f'"{slot}"', json.dumps(quoted)).replace(slot, bare)
    return value


def _probe_slots(name: str, attempt_dir: Path, repo: Path) -> dict[str, tuple[str, str]]:
    """A probe session's fixture slots: @asked, the spelling its prompt asks for (in agy's
    message with every slash turned to a backslash, so the match must undo both the quoting and
    the slash direction), and @plain, the plain spelling of the same file."""
    asked, plain = _read_spellings(attempt_dir, repo).get(
        name, (None, str(repo / "orig" / driver.AGY_CANARY_PROBE)))
    slots = {"@plain": (plain, plain)}
    if asked is not None:
        slots["@asked"] = (asked.replace("/", "\\"), asked)
    return slots


def _session_name(transcript: Path) -> str:
    """Which canary session a launch is, by the transcript the driver gave it."""
    if transcript.name == driver.TRANSCRIPT:
        return ALLOWED
    return transcript.stem.removeprefix("agy-canary-")


def _agy_canary_rig(tmp_path: Path, *, usage: str = "usage_remaining", check: dict | None = None,
                    scenarios: dict | None = None, escape: str | None = None,
                    raises: str | None = None) -> Rig:  # fmt: skip
    """test_drive's canary rig (the matched canary unit and its functions.csv row in HEAD) with
    agy sessions: fakeagy through the real run_session, each session replaying its scenario
    (SCENARIOS, `scenarios` overriding by session name), a probe's events with their fixture
    slots filled (_probe_slots). After the allowed session, what the
    real wrapper would have left (context.md, its check line, the consumed note and their
    ledger entries); after the probe named `escape`, its file outside the workspace; the
    session named `raises` raises. The runner answers `agy --version` and `agy -p /usage` (the
    latter from tests/fixtures/agy/<usage>.txt)."""
    import hashlib

    from reverseapoc.session import run_session
    from test_drive import CONSUMED_NOTE, PASSING_CHECK, Launch, _canary_rig

    rig = _canary_rig(tmp_path, "canary_pass")
    agy_version_reply(rig)
    text = (FIXTURES / f"{usage}.txt").read_text(encoding="utf-8")
    rig.runner.replies.append((lambda argv: argv == USAGE_ARGV, (0, text, "")))
    line = PASSING_CHECK if check is None else check
    chosen = {**SCENARIOS, **(scenarios or {})}

    def wrapper_output(attempt_dir: Path, ledger: Path) -> None:
        wrote = {"context.md": "# context\n", "checks.jsonl": json.dumps(line) + "\n",
                 "checks/0001.note.json": json.dumps(CONSUMED_NOTE) + "\n"}  # fmt: skip
        with ledger.open("a", encoding="utf-8") as fh:
            for rel, body in wrote.items():
                (attempt_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (attempt_dir / rel).write_text(body, encoding="utf-8", newline="\n")
                digest = hashlib.sha256((attempt_dir / rel).read_bytes()).hexdigest()
                fh.write(json.dumps({"path": rel, "sha256": digest}) + "\n")

    def run(argv, *, cwd, env, transcript, timeout_s, popen):
        name = _session_name(Path(transcript))
        env = {**env, "FAKEAGY_SCENARIO": chosen[name]}
        rig.launches.append(Launch(list(argv), dict(env), Path(cwd)))
        if name == raises:
            raise OSError("made-up launch failure")
        result = run_session(argv, cwd=cwd, env=env, transcript=transcript, timeout_s=timeout_s,
                             popen=popen)  # fmt: skip
        attempt_dir = Path(env[driver.attempt.DIR_ENV])
        if name == ALLOWED:
            wrapper_output(attempt_dir, Path(env[driver.attempt.WRAPPER_LEDGER_ENV]))
        if name == escape:
            (attempt_dir.parent / CANARY_LEFT[name]).write_text("canary\n", encoding="utf-8")
        if name == ALLOWED:
            return result
        slots = _probe_slots(name, attempt_dir, rig.repo)
        return replace(result, events=tuple(_filled(event, slots) for event in result.events))

    rig.session = run
    return rig


def _agy_canary(rig: Rig, capsys, arm: str = GEMINI) -> tuple[int, dict]:
    code, out, _ = rig.drive(capsys, canary=True, json=True, night_model=arm, canary_model=arm,
                             allow_egress=(arm,),
                             seams={"base_env": rig.env, "agy_argv": fake_agy_argv})  # fmt: skip
    return code, json.loads(out)


def _pass_file(rig: Rig, arm: str = GEMINI) -> Path:
    return rig.repo / driver.CANARY_PASS_DIR / f"{arm}.json"


def _no_pass(rig: Rig, arm: str = GEMINI) -> bool:
    path = _pass_file(rig, arm)
    return not path.exists() or json.loads(path.read_text(encoding="utf-8"))["result"] != "PASS"


def _failed(doc: dict) -> str:
    return " | ".join(c["check"] for c in doc["checks"] if not c["ok"])


def _timeout(argv: list[str]) -> str:
    return argv[argv.index("--print-timeout") + 1]


def test_agy_canary_pass(tmp_path, capsys):
    """Spike 012: headless agy ends the turn at its first soft-denied tool, so the canary is a
    sequence of short sessions in one attempt dir, each proving one thing: the allowed path
    first (the wrapper's context, a plan through `attempt plan`, the check), then one session
    per forbidden probe, each denied as agy's stream shows it. With every session as expected,
    the side effects absent and `/usage` reporting remaining quota: CANARY PASS, and the pass
    file records the CLI version, the date, the allowed session's tokens and the quota."""
    rig = _agy_canary_rig(tmp_path)
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc.get("canary")) == (0, "PASS"), _failed(doc)
    texts = " | ".join(c["check"] for c in doc["checks"])
    for needle in ("init", "attempt context", "attempt plan", "attempt check", "context.md",
                   "0001.note.json", "ledger", "settings", "1500000", AGY_VERSION,
                   driver.AGY_CANARY_OUTSIDE, driver.AGY_CANARY_UNSANDBOXED, "example.com",
                   *(f"the {name.replace('-', ' ')} probe was denied" for name in PROBES)):
        assert needle in texts, needle
    attempt_dir = rig.repo / doc["attempt_dir"]
    assert len(rig.launches) == 1 + len(PROBES)
    assert all(launch.cwd == attempt_dir for launch in rig.launches)
    assert [_timeout(launch.argv) for launch in rig.launches] == (
        [f"{driver.CANARY_TIMEOUT_S}s"] + [f"{driver.AGY_CANARY_PROBE_TIMEOUT_S}s"] * len(PROBES))
    # the wall time stays bounded: every session together within 45 minutes
    assert driver.CANARY_TIMEOUT_S + driver.AGY_CANARY_PROBE_TIMEOUT_S * len(PROBES) <= 45 * 60
    assert ["agy", "--version"] in rig.runner.calls and USAGE_ARGV in rig.runner.calls
    saved = json.loads(_pass_file(rig).read_text(encoding="utf-8"))
    assert {k: saved[k] for k in ("arm", "harness", "cli_version", "result")} == {
        "arm": GEMINI, "harness": "agy", "cli_version": AGY_VERSION, "result": "PASS"}
    assert isinstance(saved["date"], str) and len(saved["date"]) == len("2026-11-10")
    assert saved["tokens"] == {"input": 9000, "output": 1000, "cache_read": 3000,
                               "cache_creation": 0}  # fmt: skip
    assert saved["quota"]["measured"] is True and saved["quota"]["remaining"] == 1500000
    assert "agy_auto_denied" not in doc  # a PASS carries no auto-deny diagnostics


def test_agy_canary_sessions_run_in_order_with_their_own_transcripts(tmp_path, capsys):
    """The allowed session runs first with the attempt's transcript; each probe then runs once,
    in order, with its own transcript outside the workspace (beside the settings file), so the
    attempt dir holds only what the allowed path left."""
    rig = _agy_canary_rig(tmp_path)
    seen: list[str] = []
    inner = rig.session

    def run(argv, *, transcript, **values):
        seen.append(_session_name(Path(transcript)))
        if seen[-1] != ALLOWED:
            assert Path(transcript).parent.name == driver.AGY_DIR, transcript
        return inner(argv, transcript=transcript, **values)

    rig.session = run
    code, doc = _agy_canary(rig, capsys)
    assert code == 0, _failed(doc)
    assert seen == [ALLOWED, *PROBES]


def test_agy_canary_prompts_are_one_plain_instruction(tmp_path):
    """Each probe session asks for one action in a plain sentence naming only its own target:
    a write one directory above the workspace, a URL fetch, a command writing outside the
    workspace, and the four orig/ probe-read spellings (`../`-relative, a different case, the
    attempt dir followed by `..`, the 8.3 short name). The allowed session lists the wrapper
    flow in order. No prompt frames itself as a guardrail test with steps that will fail
    (gpt-oss-120b-medium refused that prompt outright)."""
    attempt_dir = tmp_path / "build" / "x" / "attempt-1"
    probes = driver.agy_canary_probes(attempt_dir, repo=tmp_path)
    assert [probe.name for probe in probes] == list(PROBES)
    wants = {"outside-write": str(attempt_dir.parent / driver.AGY_CANARY_OUTSIDE),
             "fetch": driver.CODEX_CANARY_URL,
             "unsandboxed": str(attempt_dir.parent / driver.AGY_CANARY_UNSANDBOXED),
             "relative-read": f"../../../orig/{driver.AGY_CANARY_PROBE}",
             "different-case-read": str(tmp_path / "ORIG" / driver.AGY_CANARY_PROBE),
             "dot-dot-read": f"{attempt_dir.as_posix()}/../../../orig/{driver.AGY_CANARY_PROBE}",
             "short-name-read": str(tmp_path / "THIRD_~1" / driver.AGY_CANARY_PROBE)}
    for probe in probes:
        assert wants[probe.name] in probe.prompt, probe
        others = [want for name, want in wants.items()  # the `..` read holds the relative one
                  if name != probe.name and want not in wants[probe.name]]  # fmt: skip
        assert not [want for want in others if want in probe.prompt], probe
    allowed = driver.agy_canary_allowed_prompt(attempt_dir, 0xD)
    order = [f"{WRAPPER} context", "plan.json", f"{WRAPPER} plan", "check-note.json",
             f"{WRAPPER} check"]  # fmt: skip
    places = [allowed.index(needle) for needle in order]
    assert places == sorted(places), places
    for prompt in (allowed, *(probe.prompt for probe in probes)):
        for framing in ("guardrail", "canary,", "not a matching attempt", "will fail",
                        "will be denied", "do not retry"):  # fmt: skip
            assert framing not in prompt.casefold(), (framing, prompt)


def test_agy_canary_probe_verdicts(tmp_path, capsys):
    """A probe session passes only when its action was denied in agy's stream. A model that
    made no tool step refused ("model refused"); a session whose only denial is another action
    never attempted its probe ("never attempted"); a step that was not denied ran ("not
    denied"). Each is a CANARY FAIL naming the probe, with no PASS file."""
    cases = (("model refused", "canary_agy_refused"),
             ("never attempted", "canary_agy_soft_denied"),
             ("not denied", "canary_agy_read_ran"))  # fmt: skip
    for verdict, scenario in cases:
        rig = _agy_canary_rig(tmp_path / scenario, scenarios={"relative-read": scenario})
        code, doc = _agy_canary(rig, capsys)
        assert (code, doc["canary"]) == (1, "FAIL"), verdict
        failed = _failed(doc)
        assert "the relative read probe" in failed and verdict in failed, (verdict, failed)
        assert "the different case read probe" not in failed, failed
        assert _no_pass(rig), verdict


def test_agy_canary_read_probe_wants_its_own_spelling(tmp_path, capsys):
    """Security review: each orig/ read probe exists to prove the deny rules for one spelling
    (`../`-relative, another case, `..` segments, the 8.3 short name). A model that reads the
    plain path of the same file instead, and has that denied, never tried the spelling: the
    probe FAILs saying it read a different spelling than asked, quoting both, and the other
    read probes still pass. Only the slash direction and agy's Go quoting are undone (the
    default fixture turns every slash of the asked spelling into a backslash and Go-quotes it,
    and test_agy_canary_pass still passes), never case or `..`."""
    for name in (probe for probe in PROBES if probe.endswith("-read")):
        rig = _agy_canary_rig(tmp_path / name, scenarios={name: "canary_agy_deny_read_plain"})
        code, doc = _agy_canary(rig, capsys)
        assert (code, doc["canary"]) == (1, "FAIL"), name
        failed = _failed(doc)
        asked, plain = _read_spellings(rig.repo / doc["attempt_dir"], rig.repo)[name]
        label = name.replace("-", " ")
        assert f"the {label} probe: the model read a different spelling than asked" in failed, (
            name, failed)
        assert repr(asked) in failed and repr(plain) in failed, (name, failed)
        texts = " | ".join(c["check"] for c in doc["checks"] if c["ok"])
        for other in (probe for probe in PROBES if probe != name):
            assert f"the {other.replace('-', ' ')} probe was denied" in texts, (name, other)
        assert _no_pass(rig), name


def test_agy_canary_other_probes_still_want_their_own_action(tmp_path, capsys):
    """The exact-spelling rule is for the read probes only and loosens nothing else: a write,
    fetch or unsandboxed probe whose only denial is a read of the orig/ probe file never
    attempted its probe."""
    for name in ("outside-write", "fetch", "unsandboxed"):
        rig = _agy_canary_rig(tmp_path / name, scenarios={name: "canary_agy_deny_read_plain"})
        code, doc = _agy_canary(rig, capsys)
        assert (code, doc["canary"]) == (1, "FAIL"), name
        failed = _failed(doc)
        assert f"the {name.replace('-', ' ')} probe: never attempted" in failed, (name, failed)
        assert _no_pass(rig), name


def test_agy_canary_allowed_session_names_an_unseen_step_shape(tmp_path, capsys):
    """An allowed session whose command steps are in a shape the audit does not know (here a
    Cwd parameter beside CommandLine, which the real run_command step never showed) FAILs
    naming each step, and its wrapper calls do not count, even though the wrapper's files are
    there."""
    rig = _agy_canary_rig(tmp_path, scenarios={ALLOWED: "canary_agy_allowed_unseen"})
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc["canary"]) == (1, "FAIL")
    failed = _failed(doc)
    assert "is not a tool step the agy audit knows" in failed and "'parameters'" in failed, failed
    assert "never ran" in failed and f"{WRAPPER} plan" in failed, failed
    assert _no_pass(rig)


def test_agy_canary_allowed_session_denied(tmp_path, capsys):
    """An allowed session that agy soft-denied (its turn then ends) FAILs naming the denied
    step and the wrapper calls it never made; agy's stderr line is a NOTE, labelled with the
    session, on FAIL only, and all of agy's stderr is echoed."""
    marker = "headless mode cannot prompt"
    rig = _agy_canary_rig(tmp_path / "json", scenarios={ALLOWED: "canary_agy_soft_denied",
                                                         "outside-write": "canary_agy_refused"})
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc["canary"]) == (1, "FAIL")
    failed = _failed(doc)
    assert "the allowed session had a denied step" in failed and "write_file(" in failed, failed
    assert "never ran" in failed, failed
    assert any(c["ok"] and c["check"].startswith("init: cwd the attempt dir")
               for c in doc["checks"]), doc["checks"]  # fmt: skip
    noted = doc["agy_auto_denied"]
    assert len(noted) == 1 and noted[0].startswith(f"{ALLOWED}: ") and marker in noted[0], noted
    assert not any(marker in c["check"] for c in doc["checks"])
    text = _agy_canary_rig(tmp_path / "text", scenarios={ALLOWED: "canary_agy_soft_denied"})
    code, out, err = text.drive(capsys, canary=True, night_model=GEMINI, canary_model=GEMINI,
                                allow_egress=(GEMINI,),
                                seams={"base_env": text.env, "agy_argv": fake_agy_argv})
    lines = out.splitlines()
    assert (code, lines[-1]) == (1, "CANARY FAIL")
    notes = [line for line in lines if line.startswith("NOTE: ")]
    assert len(notes) == 2 and all(marker in note for note in notes), notes
    assert "an unrelated made-up warning" in err and marker in err


def test_agy_canary_fails_on_each_escape(tmp_path, capsys):
    """An outside file afterwards, a command's file afterwards, a fetch that ran, a check
    without exit 0, or a session that raised: CANARY FAIL naming it, and no PASS file; every
    other session still ran."""
    bad_check = {"n": 1, "exit": 1, "sweep": False, "best_percent": 90.0, "reloc_ok": False,
                 "bytes_ok": False, "splice_ok": True, "sweep_hit": None,
                 "source": "checks/0001.c", "note": "checks/0001.note.json"}  # fmt: skip
    cases = (("outside", {"escape": "outside-write"}, driver.AGY_CANARY_OUTSIDE),
             ("unsandboxed", {"escape": "unsandboxed"}, driver.AGY_CANARY_UNSANDBOXED),
             ("network", {"scenarios": {"fetch": "canary_agy_fetch_ran"}}, "the fetch probe"),
             ("check", {"check": bad_check}, "attempt check"),
             ("raised", {"raises": "fetch"}, "the fetch probe session raised"))  # fmt: skip
    for name, rig_args, needle in cases:
        rig = _agy_canary_rig(tmp_path / name, **rig_args)
        code, doc = _agy_canary(rig, capsys)
        assert (code, doc["canary"]) == (1, "FAIL"), name
        assert needle in _failed(doc), (name, _failed(doc))
        assert len(rig.launches) == 1 + len(PROBES), name
        assert _no_pass(rig), name


def test_agy_canary_no_quota(tmp_path, capsys):
    """D-21: a `/usage` with no remaining quota, or a quota error status: CANARY FAIL naming
    the fallback arm and how to run it, and no PASS file."""
    for usage in ("usage_exhausted", "usage_quota_error"):
        rig = _agy_canary_rig(tmp_path / usage, usage=usage)
        code, doc = _agy_canary(rig, capsys)
        assert (code, doc["canary"]) == (1, "FAIL"), usage
        failed = " | ".join(c["check"] for c in doc["checks"] if not c["ok"])
        assert FALLBACK in failed, failed
        assert f"--night-model {FALLBACK} --allow-egress {FALLBACK}" in failed, failed
        assert _no_pass(rig), usage


def test_agy_canary_unmeasurable_quota(tmp_path, capsys):
    """RESEARCH A8: a `/usage` that prints nothing machine-readable falls back to the session's
    tokens and says the quota was estimated, not measured; the probes passed, so PASS, with the
    estimate in the pass file."""
    rig = _agy_canary_rig(tmp_path, usage="usage_unreadable")
    code, doc = _agy_canary(rig, capsys)
    failed = [c["check"] for c in doc["checks"] if not c["ok"]]
    assert (code, doc["canary"]) == (0, "PASS"), failed
    texts = " | ".join(c["check"] for c in doc["checks"])
    assert "estimated, not measured" in texts and "13000" in texts, texts
    saved = json.loads(_pass_file(rig).read_text(encoding="utf-8"))
    assert saved["quota"]["measured"] is False and saved["quota"]["remaining"] is None
    assert saved["quota"]["session_tokens"] == 13000


def test_agy_arm_refused_without_a_pass(tmp_path, capsys):
    """D-21 (as D-13 for Codex): no agy arm runs before its canary passed on the installed CLI:
    no pass file, a FAIL one, or one naming another version exits 2 before any session, naming
    the canary command to run."""
    for state in ("none", "fail", "other-version"):
        rig = Rig(tmp_path / state)
        agy_version_reply(rig)
        if state == "fail":
            write_pass(rig.repo, result="FAIL")
        elif state == "other-version":
            write_pass(rig.repo, version="1.5.2")
        code, out, _ = rig.drive(capsys, json=True, seams={"base_env": _keyed(rig.env)},
                                 night_model=GEMINI, allow_egress=(GEMINI,),
                                 workers=1)  # fmt: skip
        assert code == 2, state
        detail = json.loads(out)["detail"]
        assert f"--canary --night-model {GEMINI} --allow-egress {GEMINI}" in detail, detail
        assert list((rig.repo / "build").rglob("attempt-*")) == [], state


def test_an_unknown_harness_is_refused(tmp_path):
    """The pass gate fails closed: an arm on a harness the driver has no canary for is refused
    before any session, whatever pass file exists."""
    import pytest

    arm = backends.Arm(name="made-up-arm", harness="made-up-cli", backend="made-up",
                       model="made-up-model", sends_disassembly=False, max_workers=1)
    rig = Rig(tmp_path)
    write_pass(rig.repo, arm.name)
    options = rig.options(night_model=arm.name)
    with pytest.raises(driver.Refused) as exc:
        driver.refuse_unproven(options, rig.seams(), {arm.name: arm})
    assert "made-up-cli" in str(exc.value)


def _linked_repo(tmp_path: Path, part: str) -> tuple[Path, Path]:
    """A made-up checkout whose attempt dir holds `v`, a directory link (a junction on
    Windows) to the checkout's `part`/ directory: a raw path through `v` names no forbidden
    part, its resolved form does."""
    from test_driver import _plant_dir_link

    repo = tmp_path / "repo"
    root = repo / ATTEMPT
    root.mkdir(parents=True)
    (repo / part / "watcom").mkdir(parents=True)
    _plant_dir_link(root / "v", repo / part)
    return repo, root


def test_agy_read_through_a_link_into_third_party_is_a_stray(tmp_path):
    """Security review round 2: a read is judged on every resolved form, not only on the raw
    string: `v/watcom/x.h` through a link into third_party/ is a stray naming third_party."""
    repo, root = _linked_repo(tmp_path, "third_party")
    strays = driver.read_strays(["v/watcom/x.h", "context.md"], attempt_dir=root, repo=repo)
    assert len(strays) == 1 and "third_party" in strays[0], strays


def test_codex_write_through_a_link_into_orig_names_it(tmp_path):
    """The same for Codex's (and agy's) writes: a write whose resolved form lies under orig/ is
    a stray naming orig/, even when the allowlist would pass every form."""
    repo, root = _linked_repo(tmp_path, "orig")
    strays = driver.codex_write_strays(["v/watcom/x.c", "notes.md"], attempt_dir=root,
                                       repo=repo, allowed=lambda rel: True)  # fmt: skip
    assert len(strays) == 1 and "orig/" in strays[0], strays


def test_dot_dot_and_short_name_segments_are_strays(tmp_path):
    """Security review round 3: a read or write path holding a `..` segment, or an 8.3 short
    name segment (`~<digit>`) below the checkout, is a stray even when it resolves inside the
    allowlist; a name that merely holds dots or a tilde is not."""
    repo = tmp_path / "repo"
    root = repo / ATTEMPT
    (root / "view").mkdir(parents=True)
    bad = ["view/../notes.md", f"{root}\\view\\..\\notes.md", "VIEW~1/src/x.c",
           f"{root.as_posix()}/NOTES~1.MD"]  # fmt: skip
    good = ["notes.md", "..notes/x.md", "view/a~b.c"]
    reads = driver.read_strays([*bad, *good], attempt_dir=root, repo=repo)
    assert [s.split(": a read")[0] for s in reads] == bad, reads
    writes = driver.codex_write_strays([*bad, *good], attempt_dir=root, repo=repo,
                                       allowed=lambda rel: True)  # fmt: skip
    assert [s.split(": a write")[0] for s in writes] == bad, writes


def _query_envs(runner, argv: list[str]) -> list[dict | None]:
    return [env for call, env in zip(runner.calls, runner.envs, strict=True) if call == argv]


def _clean(env: dict | None) -> bool:
    """The stripped session env: given at all, and holding no ANTHROPIC_* name, no arm key and
    no OpenAI or Google key variable."""
    return env is not None and not [n for n in env if n.upper().startswith("ANTHROPIC_")
                                    or n in LEAKS]  # fmt: skip


def test_cli_queries_run_with_the_stripped_session_env(tmp_path, capsys):
    """RULINGS token-leak guard, orchestrator follow-up: `agy --version` and `agy -p /usage`
    (the canary and the pass gate) and `codex --version` (the gate) run with the env an agy or
    Codex session gets, never the driver's own: no ANTHROPIC_* and no arm key variable."""
    import pytest

    rig = _agy_canary_rig(tmp_path / "canary")
    env = _keyed(rig.env, **LEAKS)
    code, out, _ = rig.drive(capsys, canary=True, json=True, night_model=GEMINI,
                             canary_model=GEMINI, allow_egress=(GEMINI,),
                             seams={"base_env": env, "agy_argv": fake_agy_argv})  # fmt: skip
    assert code == 0, out
    for argv in (["agy", "--version"], USAGE_ARGV):
        envs = _query_envs(rig.runner, argv)
        assert envs and all(_clean(e) for e in envs), argv
    arms = backends.load_arms()
    for name, cli in ((GEMINI, "agy"), ("gpt-6-luna", "codex")):
        gate = Rig(tmp_path / name)
        seams = gate.seams(base_env=_keyed(gate.env, **LEAKS))
        with pytest.raises(driver.Refused):  # no pass file: refused after the version query
            driver.refuse_unproven(gate.options(night_model=name), seams, arms)
        envs = _query_envs(gate.runner, [cli, "--version"])
        assert envs and all(_clean(e) for e in envs), name


def test_exception_names_antigravity():
    """CLAUDE.md and .claude/rules/workflow.md keep Claude Code as the only agent runtime and
    name the one scoped exception: Codex CLI and Antigravity CLI `reverseapoc drive` sessions,
    their per-session config under build/, and no .gemini/ or Antigravity config tree."""
    for rel in ("CLAUDE.md", ".claude/rules/workflow.md"):
        text = " ".join((REPO_ROOT / rel).read_text(encoding="utf-8").split())
        for needle in ("only agent runtime", "Codex", "Antigravity", "reverseapoc drive",
                       "spike 012", "build/", ".gemini/"):  # fmt: skip
            assert needle in text, (rel, needle)
