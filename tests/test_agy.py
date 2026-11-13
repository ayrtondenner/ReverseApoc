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
import posixpath
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


AGY_CLAUDE = {  # spike 012 (owner, 2026-11-11): Claude 4.6 through agy's own weekly group
    "agy-sonnet-4-6": ("claude-sonnet-4-6", "Claude Sonnet 4.6 <noreply@anthropic.com>",
                       (3.00, 15.00, 0.30, 3.00)),
    "agy-opus-4-6": ("claude-opus-4-6-thinking", "Claude Opus 4.6 <noreply@anthropic.com>",
                     (5.00, 25.00, 0.50, 5.00)),
}  # fmt: skip


def test_agy_claude_arms_load():
    """Spike 012 (owner, 2026-11-11): Claude Sonnet 4.6 and Opus 4.6 (Thinking) through agy on
    the owner's AI Plus sign-in, in agy's "Claude and GPT models" weekly group (separate from
    Gemini's and from the owner's Claude subscription): the exact slugs `agy models` lists, a
    subscription arm, one worker, at most 7 sessions (the 7 picks under 64 B), sending the pack
    to Google, priced at Anthropic's list prices for the comparison only."""
    from reverseapoc.streamjson import Price

    arms = backends.load_arms()
    for name, (model, credit, price) in AGY_CLAUDE.items():
        arm = arms[name]
        assert (arm.harness, arm.backend, arm.model) == ("agy", "google", model), name
        assert (arm.base_url, arm.key_env, arm.accepted_init) == (None, None, (model,))
        assert arm.prices == Price(*price) and arm.coauthor == credit
        assert arm.max_workers == 1 and arm.max_sessions == 7 and arm.egress
        assert arm.billing == backends.SUBSCRIPTION


def test_each_agy_arm_builds_a_valid_argv(tmp_path):
    """RULINGS "Plan 15, Antigravity arms": each entry builds an argv the fake agy accepts, with
    its exact model id."""
    import fakeagy

    arms = backends.load_arms()
    pairs = ((GEMINI, GEMINI_MODEL), (GPT_OSS, GPT_OSS_MODEL),
             *((name, spec[0]) for name, spec in AGY_CLAUDE.items()))  # fmt: skip
    for name, model in pairs:
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
    # agy 1.5.8's edit_file step is a write the audit knows and judges (allowed by the same
    # write_file rules), so the file-edit rule holds for agy as it does for Codex
    assert "Create and edit files only with your file-edit tool" in note
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
    soft-denied write (the step ends ERROR with the permission check's message: it never ran,
    so it is a denial, not a write) and its result are all read; no step is unknown."""
    events = _events("canary_agy_soft_denied")
    init = agyjson.init_event(events)
    assert init is not None and init["permission_mode"] == "request-review", init
    assert (init["cwd"], init["model"]) == ("@cwd", "@model")
    assert agyjson.turns(events) == 1
    assert agyjson.usage(events) == Usage(
        input_tokens=9000, output_tokens=2100, cache_read_tokens=0, cache_creation_tokens=0,
        turns=1, cost_usd=0.0, duration_ms=10500)  # fmt: skip
    assert agyjson.write_targets(events) == []
    assert agyjson.read_targets(events) == [] and agyjson.commands(events) == []
    assert agyjson.unknown_steps(events) == []
    assert [d.step for d in agyjson.denials(events)] == [2]
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
                                             "C:\\made-up\\attempt-1\\plan.json",
                                             "C:\\made-up\\attempt-1\\check-note.json"]
    assert agyjson.edits(events) == ["C:\\made-up\\attempt-1\\plan.json"]
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


# spike 012 round 4 (gemini-flash's allowed session, step 12): a status poll's output, once DONE
TASK_OUTPUT = ("Created At: 2026-11-10T22:02:14-03:00\nCompleted At: 2026-11-10T22:02:14-03:00\n"
               "Task: made-up/task-10\nStatus: RUNNING\n"
               "Log: file:///C:/made-up/tasks/task-10.log\n")  # fmt: skip


def _task(index: int, action: str = "status", *, state: str = "DONE", **info) -> dict:
    """A manage_task step in agy 1.5.5's real shape (spike 012 round 4): tool_info {name,
    parameters: {Action, TaskId}, output}; `info` replaces or adds tool_info keys."""
    shape = {"name": "manage_task", "parameters": {"Action": action, "TaskId": "made-up/task-10"},
             "output": TASK_OUTPUT}  # fmt: skip
    return _step(index, "manage_task", state=state, **{**shape, **info})


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
    that message, and the step's own request (its path or command as the model asked for it)
    from its parameters: round 3 showed the message's target canonicalized. A step that itself
    ends DENIED is a denial by its tool and its path or command. An ERROR with any other
    message ran and failed, and a DONE step ran: neither is a denial, and `undenied_steps`
    names both, an ERROR with its message."""
    events = _events("canary_agy_soft_denied")
    outside = "C:/made-up/func_000A3980/agy-canary-outside.txt"
    assert agyjson.denials(events) == [agyjson.Denial(2, "write_file", "write_file", outside,
                                                      outside.replace("/", "\\"))]
    assert agyjson.undenied_steps(events) == []
    echo = 'echo "a" > C:\\x'  # Go-quoted in the message: its quotes and backslash escaped
    mixed = [_soft_denied(1, "run_command", "command", echo, command=echo),
             _step(2, "read_file", state="DENIED", path="../orig/x.txt"),
             _step(3, "read_file", state="ERROR", path="a.txt",
                   error={"type": "TOOL_ERROR", "message": "file not found"}),
             _step(4, "write_file", path="notes.md")]  # fmt: skip
    assert agyjson.denials(mixed) == [agyjson.Denial(1, "run_command", "command", echo, echo),
                                      agyjson.Denial(2, "read_file", "read_file",
                                                     "../orig/x.txt", "../orig/x.txt")]  # fmt: skip
    assert agyjson.undenied_steps(mixed) == ["step 3: read_file (ERROR: file not found)",
                                             "step 4: write_file (DONE)"]  # fmt: skip
    canonical = _soft_denied(5, "read_file", "read_file", "C:/x/orig/x.txt",
                             parameters={"Path": "C:/x/a/../orig/x.txt"})
    assert agyjson.denials([canonical]) == [agyjson.Denial(5, "read_file", "read_file",
                                                           "C:/x/orig/x.txt",
                                                           "C:/x/a/../orig/x.txt")]
    assert agyjson.response(_events("canary_agy_refused")) == "I'm sorry, but I can't help."


# round 3: the last line of every real permission denial's message, byte for byte
DENY_TAIL = ("\nDo not attempt to circumvent this denial by rephrasing the command, using "
             "alternative tools/scripts (e.g. python, sh, curl), or accessing the same target "
             "resource. Proceed without performing this action.")


def _deny_message(action: str, target: str) -> str:
    """agy 1.5.5's whole message for a denial, as round 3's transcripts show it: a path
    action's `user denied permission for <action>(<target>)`, a command's `user denied
    permission to run command:` and the command on its own line, then DENY_TAIL."""
    why = ("to run command:\n" + target if action in ("unsandboxed", "command")
           else f"for {action}({target})")  # fmt: skip
    return (f"permission check failed for {action} {json.dumps(target)}: user denied "
            f"permission {why}{DENY_TAIL}")


def _soft_denied(index: int, tool: str, action: str, target: str, *,
                 message: str | None = None, **info) -> dict:  # fmt: skip
    """A step agy 1.5.5's permission check refused, as round 3's probes show it: ERROR,
    TOOL_ERROR, with the check's whole message (`message`, else _deny_message) naming the
    action and the (canonical) target."""
    error = {"type": "TOOL_ERROR", "message": message or _deny_message(action, target)}
    if tool == "run_command":
        return _run(index, info.pop("command"), state="ERROR", error=error, **info)
    return _step(index, tool, state="ERROR", name=tool, error=error, **info)


def test_agyjson_a_soft_denied_step_never_ran():
    """Spike 012: a step agy's permission check refused ends ERROR with that check's message
    and never ran, as a step ending DENIED: it is in no list the audit judges as run (commands,
    writes, reads, unknown steps) and only in `denials`. agy names the target canonicalized
    (round 3: absolute, forward slashes, `..` folded), so a path step's target is its request
    in that form. An ERROR with any other message (round 3: gemini's relative read, `declaring
    permissions: failed to parse path: ... must be an absolute path`) may have run: it stays a
    read the audit judges (fail closed)."""
    relative = "../../../orig/x.txt"
    events = [_soft_denied(1, "run_command", "unsandboxed", "curl.exe -sS https://x.invalid/",
                           command="curl.exe -sS https://x.invalid/"),
              _soft_denied(2, "write_file", "write_file", "C:/x/tools/x.py",
                           parameters={"Path": "C:\\x\\tools\\x.py"}),
              _soft_denied(3, "read_file", "read_file", "C:/x/orig/x.txt",
                           parameters={"Path": "C:/x/a/../orig/x.txt"}),
              _step(4, "read_file", state="ERROR", name="read_file",
                    parameters={"Path": relative},
                    error={"type": "TOOL_ERROR", "message": "declaring permissions: failed to "
                           f"parse path: {relative} must be an absolute path: path is not "
                           "absolute"})]  # fmt: skip
    assert agyjson.commands(events) == [] and agyjson.write_targets(events) == []
    assert agyjson.read_targets(events) == [relative]
    assert agyjson.unknown_steps(events) == []
    assert [d.step for d in agyjson.denials(events)] == [1, 2, 3]
    assert agyjson.denied_writes(events) == ["C:\\x\\tools\\x.py"]  # writes only, as requested


def test_agyjson_a_denial_must_be_exact():
    """Security review: a step counted as denied leaves the audit, so only agy's exact denial
    is one: a known tool in its known shape (tool_info but its error), no subagent, state
    ERROR, error type TOOL_ERROR, the whole message in round 3's format (fullmatch, its last
    line included), the message's action one that fits the step's tool (read_file, write_file;
    unsandboxed or command for run_command), its quoted and bare targets the same, and that
    target the step's own request (a command as written; a path with its slashes turned
    forward and `..` folded, agy's canonical form). Anything else counts as run (fail closed):
    a message embedding the permission text after other text, a denial naming another target,
    an action that does not fit the tool, another error type, a missing tail; and a subagent's
    or an unknown tool's step with an exact message stays an unknown step."""
    command = "uv run --frozen reverseapoc attempt check"
    path = {"Path": "C:\\x\\notes.md"}
    ran = [_soft_denied(1, "run_command", "unsandboxed", command, command=command,
                        message="made-up output: " + _deny_message("unsandboxed", command)),
           _soft_denied(2, "write_file", "write_file", "C:/x/other.md", parameters=path),
           _soft_denied(3, "write_file", "read_file", "C:/x/notes.md", parameters=path),
           _soft_denied(4, "run_command", "write_file", command, command=command),
           _soft_denied(5, "write_file", "write_file", "C:/x/notes.md", parameters=path,
                        message=_deny_message("write_file", "C:/x/notes.md").removesuffix(
                            DENY_TAIL)),
           _soft_denied(6, "run_command", "unsandboxed", "type notes.md", command=command)]
    other_type = _soft_denied(7, "write_file", "write_file", "C:/x/notes.md", parameters=path)
    other_type["step_update"]["tool_info"]["error"]["type"] = "MADE_UP_ERROR"
    ran.append(other_type)
    assert agyjson.denials(ran) == []
    assert [text.split(":")[0] for text in agyjson.undenied_steps(ran)] == [
        f"step {n}" for n in range(1, 8)]
    assert agyjson.write_targets(ran) == ["C:\\x\\notes.md"] * 4
    unknown = [_soft_denied(8, "write_file", "write_file", "C:/x/notes.md", parameters=path,
                            subagent={"name": "made-up"}),
               _soft_denied(9, "web_fetch", "read_url", "https://x.invalid/",
                            parameters={"Url": "https://x.invalid/"}),
               _soft_denied(10, "run_command", "unsandboxed", command, command=command,
                            Cwd="C:\\x")]  # fmt: skip
    assert agyjson.denials(unknown) == []
    assert [text.split(":")[0] for text in agyjson.unknown_steps(unknown)] == [
        "step 8", "step 9", "step 10"]


def _not_absolute(path: str) -> str:
    """agy 1.5.5's whole message for a relative path it rejects before its permission check
    (round 3, gemini's relative read: the path as the model requested it, unquoted)."""
    return (f"declaring permissions: failed to parse path: {path} must be an absolute path: "
            "path is not absolute")


def _rejected(index: int, tool: str, path: str, *, message: str | None = None,
              **over) -> dict:  # fmt: skip
    """A path step agy 1.5.5 rejected for its relative path, as round 3 shows it: ERROR,
    TOOL_ERROR, `_not_absolute(path)` (`message`, else)."""
    error = {"type": "TOOL_ERROR", "message": message or _not_absolute(path)}
    return _step(index, tool, state=over.pop("state", "ERROR"), name=tool,
                 parameters={"Path": path}, error=error, **over)  # fmt: skip


def test_agyjson_a_relative_path_rejection_must_be_exact():
    """Owner ruling 2026-11-10 ("count the rejection"), round 3: agy 1.5.5 rejects a relative
    path before its permission check, ending the step ERROR with `declaring permissions:
    failed to parse path: <path> must be an absolute path: path is not absolute`.
    `rejections` names each such step by its index, tool and request, and only agy's exact
    rejection: a known path tool in its known shape (its error aside), no subagent, ERROR,
    TOOL_ERROR, the whole message in that format with the step's own request as written. A
    rejection is no denial: it stays in the reads and writes the night audit judges (fail
    closed) and in `undenied_steps`, unless the caller names it as one it counts (`rejected`).
    Anything less exact is no rejection: another path in the message (even one differing only
    in slash direction), text before it, its tail cut, another error type, a step that ended
    DONE, a subagent's step, a command step."""
    relative = "../../../orig/x.txt"
    events = [_rejected(1, "read_file", relative), _rejected(2, "write_file", relative)]
    assert agyjson.rejections(events) == [agyjson.Rejection(1, "read_file", relative),
                                          agyjson.Rejection(2, "write_file", relative)]
    assert agyjson.denials(events) == []
    assert agyjson.read_targets(events) == [relative]
    assert agyjson.write_targets(events) == [relative]
    assert agyjson.undenied_steps(events) == [
        f"step 1: read_file (ERROR: {_not_absolute(relative)})",
        f"step 2: write_file (ERROR: {_not_absolute(relative)})"]
    counted = agyjson.rejections(events)[:1]
    assert agyjson.undenied_steps(events, rejected=counted) == [
        f"step 2: write_file (ERROR: {_not_absolute(relative)})"]
    command = "type ..\\x.txt"
    inexact = [_rejected(3, "read_file", relative, message=_not_absolute("../orig/x.txt")),
               _rejected(4, "read_file", relative,
                         message=_not_absolute(relative.replace("/", "\\"))),
               _rejected(5, "read_file", relative, message="made-up: " + _not_absolute(relative)),
               _rejected(6, "read_file", relative,
                         message=_not_absolute(relative).removesuffix(": path is not absolute")),
               _rejected(7, "read_file", relative, state="DONE"),
               _rejected(8, "read_file", relative, subagent={"name": "made-up"}),
               _run(9, command, state="ERROR",
                    error={"type": "TOOL_ERROR", "message": _not_absolute(command)})]
    other_type = _rejected(10, "read_file", relative)
    other_type["step_update"]["tool_info"]["error"]["type"] = "MADE_UP_ERROR"
    inexact.append(other_type)
    assert agyjson.rejections(inexact) == []
    assert len(agyjson.undenied_steps(inexact)) == len(inexact)


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
    write_file with a path, manage_task's status poll. A missing or non-string tool name, an
    unknown tool (a fetch, a listing, a search, a manage_task that kills a task), a known tool
    without its field or in the documented but never seen `tool_info.command` shape, and a
    subagent step are each named, an unknown tool's even when it ends DENIED (only a known
    step can be a denial); a known tool's denied step, the real manage_task status poll and a
    step that is no tool step (model text) are not."""
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
             _task(9, "kill"),
             _step(10, "web_fetch", state="DENIED", url="https://made-up.invalid/")]  # fmt: skip
    fine = [_step(20, "run_command", **real, output="Command exited with code 0."),
            _step(21, "read_file", path="context.md"), _step(22, "write_file", path="notes.md"),
            _step(23, "write_file", state="DENIED", path="tools/x.py"),
            _wrapped("step_update", step_index=24, state="DONE", step_type="PLANNER_RESPONSE",
                     text_delta="made-up text"),
            _task(25)]  # fmt: skip
    found = agyjson.unknown_steps([*stray, *fine])
    assert len(found) == len(stray), found
    for index, text in zip(range(1, len(stray) + 1), found, strict=True):
        assert f"step {index}" in text, (index, text)


def test_agyjson_knows_the_real_manage_task_status_poll():
    """Spike 012 round 4 (gemini-flash's allowed session): agy 1.5.5 backgrounds a command that
    outlives its time limit (the model's log: "Task exceeded the time limit, triggering
    backgrounding"), and the model then polls that task with manage_task, tool_info {name,
    parameters: {Action: "status", TaskId}, output} (once DONE, the task's status and its
    log's path). A status poll reads agy's own task list: it writes no file, runs no command
    and stops nothing, so that exact shape is a known step that ran (no stray) and is in no
    command, read or write list, and never a denial (agy has no permission kind for it) nor a
    rejection: a poll ending DENIED ran, and one ending ERROR carries an `error` key, which is
    no longer its shape, so it is unknown (as an errored run_command is), even with a
    permission-check message. Anything else is unknown too (fail closed): another action
    (agy's own skills use `kill`, which stops a task, and `list`), a parameter added or
    missing (a CommandLine or a Path among them), a non-string Action or TaskId, a tool_info
    name that is not its tool's, another tool_info key, a subagent's step."""
    path = "C:/x/orig/x.txt"
    polls = [_task(1, state="ACTIVE"), _task(2)]
    polls[0]["step_update"]["tool_info"].pop("output")  # its first update holds no output yet
    assert agyjson.unknown_steps(polls) == []
    assert agyjson.commands(polls) == [] and agyjson.denials(polls) == []
    assert agyjson.read_targets(polls) == [] and agyjson.write_targets(polls) == []
    assert agyjson.undenied_steps(polls) == ["step 1: manage_task (ACTIVE)",
                                             "step 2: manage_task (DONE)"]  # fmt: skip
    error = {"type": "TOOL_ERROR", "message": _deny_message("read_file", path)}
    refused = [_task(3, state="ERROR", error=error), _task(4, state="DENIED"),
               _task(5, state="ERROR",
                     error={"type": "TOOL_ERROR", "message": _not_absolute("x.txt")})]
    assert agyjson.denials(refused) == [] and agyjson.rejections(refused) == []
    assert [text.split(":")[0] for text in agyjson.unknown_steps(refused)] == ["step 3", "step 5"]
    assert len(agyjson.undenied_steps(refused)) == 3
    task = "made-up/task-10"
    unknown = [_task(10, "kill"), _task(11, "list"),
               _task(12, parameters={"Action": "status"}),
               _task(13, parameters={"Action": "status", "TaskId": task, "CommandLine": "x"}),
               _task(14, parameters={"Action": "status", "TaskId": task, "Path": path}),
               _task(15, parameters={"Action": ["status"], "TaskId": task}),
               _task(16, parameters={"Action": "status", "TaskId": 10}),
               _task(17, name="run_command"), _task(18, Cwd="C:\\x"),
               _task(19, subagent={"name": "made-up"})]  # fmt: skip
    found = agyjson.unknown_steps(unknown)
    assert len(found) == len(unknown), found
    for index, text in zip(range(10, 10 + len(unknown)), found, strict=True):
        assert f"step {index}: tool 'manage_task'" in text, (index, text)
    assert agyjson.commands(unknown) == [] and agyjson.denials(unknown) == []


TIMER_OUTPUT = ("Timer cancelled early: its early-termination condition (made-up/task-10) was "
                "met by a message from made-up/task-10.")  # fmt: skip


def _timer(index: int, *, state: str = "DONE", **info) -> dict:
    """A schedule step in agy 1.5.6's real shape (spike 012 round 6, the Claude 4.6 arms'
    canaries): tool_info {name, parameters: {DurationSeconds, Prompt}} and, once the timer
    ends, output; `info` replaces or adds tool_info keys."""
    shape = {"name": "schedule",
             "parameters": {"DurationSeconds": 15, "Prompt": "Check if attempt check finished"}}
    return _step(index, "schedule", state=state, **{**shape, **info})  # fmt: skip


def test_agyjson_knows_the_real_schedule_timer():
    """Spike 012 round 6: Claude Sonnet 4.6 and Opus 4.6 through agy wait on a backgrounded
    `attempt check` with `schedule`, a timer that hands the model its own Prompt back after
    DurationSeconds (or early, when the task it waits on reports). It writes no file, runs no
    command and stops nothing, so that exact shape, with or without its output, is a known
    step that ran, in no command, read or write list and never a denial. Anything else stays
    unknown (fail closed): a parameter added or missing, a non-integer, boolean or out-of-range
    DurationSeconds (1 to 3600 seconds), a non-string Prompt, another tool_info key, a
    tool_info name that is not its tool's, a subagent's step, an `error`."""
    timers = [_timer(1, state="ACTIVE"), _timer(2), _timer(3, output=TIMER_OUTPUT)]
    assert agyjson.unknown_steps(timers) == []
    assert agyjson.commands(timers) == [] and agyjson.denials(timers) == []
    assert agyjson.read_targets(timers) == [] and agyjson.write_targets(timers) == []
    prompt = "x"
    unknown = [_timer(10, parameters={"DurationSeconds": 15}),
               _timer(11, parameters={"DurationSeconds": 15, "Prompt": prompt, "Path": "C:/x"}),
               _timer(12, parameters={"DurationSeconds": "15", "Prompt": prompt}),
               _timer(13, parameters={"DurationSeconds": True, "Prompt": prompt}),
               _timer(14, parameters={"DurationSeconds": 0, "Prompt": prompt}),
               _timer(15, parameters={"DurationSeconds": 3601, "Prompt": prompt}),
               _timer(16, parameters={"DurationSeconds": 15, "Prompt": ["x"]}),
               _timer(17, name="run_command"), _timer(18, Cwd="C:\\x"),
               _timer(19, subagent={"name": "made-up"}),
               _timer(20, state="ERROR", error={"type": "TOOL_ERROR", "message": "x"})]  # fmt: skip
    found = agyjson.unknown_steps(unknown)
    assert len(found) == len(unknown), found
    for index, text in zip(range(10, 10 + len(unknown)), found, strict=True):
        assert f"step {index}: tool 'schedule'" in text, (index, text)
    assert agyjson.commands(unknown) == [] and agyjson.denials(unknown) == []


EDITED = "C:/made-up/ws/x.txt"  # the agy 1.5.8 captures' file, its scratch dir made up


def _edit(index: int, *, state: str = "DONE", **info) -> dict:
    """An edit_file step in agy 1.5.8's real shape (the 2026-11-13 captures): tool_info {name,
    parameters: {Path}}; `info` replaces or adds tool_info keys."""
    return _step(index, "edit_file", state=state,
                 **{"name": "edit_file", "parameters": {"Path": EDITED}, **info})  # fmt: skip


def _deny_rule_message(target: str) -> str:
    """agy 1.5.8's whole message for an edit_file step a write_file deny rule refused (the
    2026-11-13 deny capture): the write_file permission names the target, no warning line."""
    return (f"permission check failed for write_file {json.dumps(target)}: Permission denied "
            f"for write_file({target}). Matches user-configured deny rule.")


def test_agyjson_knows_the_real_edit_file_step():
    """agy 1.5.7 began streaming an in-place edit as tool `edit_file`, which stopped the
    20261113-cascade night as an unknown step. The real 1.5.8 allowed capture (a read_file of
    x.txt, then an edit_file of it, settings allowing write_file(x.txt)) is clean: no unknown
    step, no denial, the read in the reads, the edit's Path in the writes the night judges
    against its allowlist (agy governs edit_file with the write_file rules) and in `edits`."""
    events = _events("agy158_edit_allowed")
    assert agyjson.unknown_steps(events) == []
    assert agyjson.denials(events) == [] and agyjson.commands(events) == []
    assert agyjson.read_targets(events) == [EDITED]
    assert agyjson.write_targets(events) == [EDITED]
    assert agyjson.edits(events) == [EDITED]
    assert agyjson.undenied_steps(events) == ["step 2: read_file (DONE)",
                                              "step 4: edit_file (DONE)"]  # fmt: skip


def test_agyjson_a_denied_edit_file_never_ran():
    """The real 1.5.8 deny capture: an edit_file of x.txt under a write_file(x.txt) deny rule
    ends ERROR, TOOL_ERROR, `permission check failed for write_file "<path>": Permission denied
    for write_file(<path>). Matches user-configured deny rule.`: a denial with the write_file
    action, so the edit never ran (in no write, edit or unknown list) and is a denied write the
    night audit names; the read before it ran."""
    events = _events("agy158_edit_denied")
    assert agyjson.denials(events) == [agyjson.Denial(4, "edit_file", "write_file", EDITED,
                                                      EDITED)]
    assert agyjson.write_targets(events) == [] and agyjson.edits(events) == []
    assert agyjson.unknown_steps(events) == []
    assert agyjson.denied_writes(events) == [EDITED]
    assert agyjson.undenied_steps(events) == ["step 2: read_file (DONE)"]
    assert agyjson.read_targets(events) == [EDITED]


def test_agyjson_an_edit_file_step_of_another_shape_is_unknown():
    """Fail closed: only the captured shape is a known edit, tool_info {name: edit_file,
    parameters: {Path: <string>}} with an `error` once it fails. Another tool_info key, another
    or a missing parameter, a Path that is no string, a tool_info name that is not its tool's,
    a subagent's step and a made-up tool are each unknown, never an edit, and a path they name
    is still judged as a write. Only the exact deny-rule message is a denial: text before it,
    another action, another target, the round-3 `user denied permission` form (never seen for
    edit_file) and another error type all count as run."""
    unknown = [_edit(1, output="made-up"), _edit(2, parameters={"Path": EDITED, "Content": "x"}),
               _edit(3, parameters={}), _edit(4, parameters={"Path": [EDITED]}),
               _edit(5, name="write_file"), _edit(6, subagent={"name": "made-up"}),
               _step(7, "patch_file", name="patch_file", parameters={"Path": EDITED})]
    found = agyjson.unknown_steps(unknown)
    assert [text.split(":")[0] for text in found] == [f"step {n}" for n in range(1, 8)], found
    assert agyjson.edits(unknown) == [] and agyjson.denials(unknown) == []
    assert agyjson.write_targets(unknown).count(EDITED) == 5  # step 4's Path is no string
    message = _deny_rule_message(EDITED)
    inexact = [_edit(10, state="ERROR", error={"type": "TOOL_ERROR", "message": m})
               for m in ("made-up: " + message, message.replace("write_file", "read_file"),
                         _deny_rule_message("C:/made-up/ws/y.txt"),
                         _deny_message("write_file", EDITED))]
    inexact.append(_edit(11, state="ERROR", error={"type": "MADE_UP_ERROR", "message": message}))
    assert agyjson.denials(inexact) == [] and agyjson.unknown_steps(inexact) == []
    assert agyjson.write_targets(inexact) == [EDITED] * 5
    exact = _edit(12, state="ERROR", error={"type": "TOOL_ERROR", "message": message})
    assert agyjson.denials([exact]) == [agyjson.Denial(12, "edit_file", "write_file", EDITED,
                                                       EDITED)]


def test_an_agy_edit_is_judged_as_a_write(tmp_path, capsys, monkeypatch):
    """At night an edit_file step in 1.5.8's shape is a write the audit judges: an edit of the
    session's own notes.md stops nothing, and an edit a deny rule refused is a denied write
    (`_denied_write_stop`), as a refused write_file is."""
    rig, night, env = agy_night(tmp_path / "edit", monkeypatch, scenario="gemini_edit")
    code, _, err = _run_agy(capsys, rig, env)
    assert code == 0, err
    assert [r for r in night.kinds("run") if r["event"] == "STOPPED"] == []
    rig, night, env = agy_night(tmp_path / "denied", monkeypatch, scenario="denied_edit")
    code, _, err = _run_agy(capsys, rig, env)
    assert code != 0, err
    _denied_write_stop(night, "C:/made-up/tools/x.py")


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


def _denied_write_stop(night: Night, path: str) -> None:
    """The one-arm night stopped at the guardrail on a write agy refused (owner ruling
    2026-11-10, "extend it": a denied write, as a Claude hook-denied one; with one arm,
    stopping its arm is stopping the night), naming the write, quarantining nothing."""
    (stopped,) = [r for r in night.kinds("run") if r["event"] == "STOPPED"]
    assert stopped["reason"] == driver.GUARDRAIL, stopped
    assert f"{path} (transcript)" in stopped["detail"], stopped
    assert "quarantined: none" in stopped["detail"], stopped


def test_agy_denied_actions_are_not_strays(tmp_path, capsys, monkeypatch):
    """Headless agy soft-denies what its settings do not allow: a denied command and a denied
    write never ran, so they count as hook blocks, never as steps that ran. A denied command
    stops nothing; a denied write is a denied write (`_denied_write_stop`)."""
    rig, night, env = agy_night(tmp_path, monkeypatch, scenario="denied_steps")
    code, _, err = _run_agy(capsys, rig, env)
    assert code != 0, err
    _denied_write_stop(night, "tools/x.py")
    assert night.kinds("attempt")[0]["hook_blocks"] == 2


def test_agy_soft_denied_steps_are_not_strays(tmp_path, capsys, monkeypatch):
    """Spike 012: agy 1.5.5 ends a soft-denied step ERROR with its permission check's message,
    never DENIED; such a step never ran, so at night it is a hook block like a DENIED step, not
    a stray that ran: a soft-denied command naming orig/ (the session's last step, as headless
    agy then ends the turn) stops nothing, and a soft-denied write outside the checkout is a
    denied write (`_denied_write_stop`)."""
    for scenario in ("soft_denied_command", "soft_denied_write"):
        rig, night, env = agy_night(tmp_path / scenario, monkeypatch, scenario=scenario)
        code, _, err = _run_agy(capsys, rig, env)
        assert night.kinds("attempt")[0]["hook_blocks"] == 1, scenario
        if scenario == "soft_denied_write":
            assert code != 0, scenario
            _denied_write_stop(night, "C:\\made-up\\tools\\x.py")
            continue
        assert code == 0, (scenario, err)
        assert [r for r in night.kinds("run") if r["event"] == "STOPPED"] == [], scenario


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
# each probe's file and whether it sits in the workspace itself (the attempt dir; else one
# directory above it)
CANARY_LEFT = {"outside-write": ("agy-canary-outside.txt", False),
               "unsandboxed": ("agy-canary-unsandboxed.txt", True)}  # fmt: skip


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
    """A probe session's fixture slots: @asked, the spelling its prompt asks for, as the step's
    request with every slash turned to a backslash (the match must undo the slash direction
    only); @canonical, the same request as agy's permission message names it (round 3:
    forward slashes, `..` folded, case as asked); and @plain, the plain spelling of the same
    file."""
    asked, plain = _read_spellings(attempt_dir, repo).get(
        name, (None, str(repo / "orig" / driver.AGY_CANARY_PROBE)))
    slots = {"@plain": (plain, plain)}
    if asked is not None:
        backslashed = asked.replace("/", "\\")
        canonical = posixpath.normpath(asked.replace("\\", "/"))
        slots |= {"@asked": (backslashed, backslashed), "@canonical": (canonical, canonical)}
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
    ledger entries); after the probe named `escape`, its file where CANARY_LEFT puts it; the
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
            left, inside = CANARY_LEFT[name]
            (attempt_dir if inside else attempt_dir.parent).joinpath(left).write_text(
                "canary\n", encoding="utf-8")
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
                   "edited C:\\made-up\\attempt-1\\plan.json in place with edit_file",
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
    a write one directory above the workspace, a URL fetch, a command writing a file in the
    workspace (round 4: gemini-flash refused a command writing one directory above it as out
    of its workspace's scope, before agy's permission check was ever reached, so the target
    is the attempt dir itself and agy's soft-deny of the unallowed command is what refuses
    it), and the four orig/ probe-read spellings (`../`-relative, a different case, the
    attempt dir followed by `..`, the 8.3 short name). Each read probe tells the model to pass
    the path string exactly as written, character for character, without resolving or
    normalizing it (round 4: gpt-oss turned the `..` spellings into the canonical absolute
    path, which proves nothing for the asked spelling); no other probe carries that
    instruction. The allowed session lists the wrapper flow in order. No prompt frames itself
    as a guardrail test with steps that will fail (gpt-oss-120b-medium refused that prompt
    outright), and no probe speaks of a sandbox, bypassing or going outside anything (round
    3: gemini and gpt-oss refused "outside the terminal sandbox" as unsafe): each probe is one
    plain line."""
    attempt_dir = tmp_path / "build" / "x" / "attempt-1"
    probes = driver.agy_canary_probes(attempt_dir, repo=tmp_path)
    assert [probe.name for probe in probes] == list(PROBES)
    left = {probe.name: probe.left for probe in probes}
    assert left["unsandboxed"] == attempt_dir / driver.AGY_CANARY_UNSANDBOXED, left
    assert left["outside-write"] == attempt_dir.parent / driver.AGY_CANARY_OUTSIDE, left
    exact = ("exactly as written", "character for character", "do not resolve or normalize",
             "the tool itself decides whether a path is allowed",
             "report what the tool returns, even an error")  # round 6: Claude 4.6 refused itself
    for probe in probes:
        carries = [phrase for phrase in exact if phrase in probe.prompt]
        assert carries == (list(exact) if probe.name.endswith("-read") else []), probe
    wants = {"outside-write": str(attempt_dir.parent / driver.AGY_CANARY_OUTSIDE),
             "fetch": driver.CODEX_CANARY_URL,
             "unsandboxed": str(attempt_dir / driver.AGY_CANARY_UNSANDBOXED),
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
    order = [f"{WRAPPER} context", "plan.json", "With your file-edit tool, edit the file",
             f"{WRAPPER} plan", "check-note.json", f"{WRAPPER} check"]  # fmt: skip
    places = [allowed.index(needle) for needle in order]
    assert places == sorted(places), places
    # the plan is written with an empty frame and edited in place to the plan `attempt plan`
    # accepts, so the session makes one in-place edit (agy's edit_file step) on its own file
    plan = driver._canary_plan_text(0xD)
    draft = plan.replace(driver.AGY_CANARY_FRAME, driver.AGY_CANARY_DRAFT)
    assert draft != plan and draft in allowed and plan not in allowed, allowed
    edit = f"replace `{driver.AGY_CANARY_DRAFT}` with `{driver.AGY_CANARY_FRAME}`"
    assert edit in allowed and str(attempt_dir / "plan.json") in allowed, allowed
    for prompt in (allowed, *(probe.prompt for probe in probes)):
        for framing in ("guardrail", "canary,", "not a matching attempt", "will fail",
                        "will be denied", "do not retry"):  # fmt: skip
            assert framing not in prompt.casefold(), (framing, prompt)
    for probe in probes:
        assert "\n" not in probe.prompt, probe
        for framing in ("terminal sandbox", "the sandbox", "bypass", "outside the", "external",
                        "network"):  # fmt: skip (the probe file's own name holds "unsandboxed")
            assert framing not in probe.prompt.casefold(), (framing, probe.prompt)


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
    (`../`-relative, another case, `..` segments, the 8.3 short name). agy's permission
    message names the target canonicalized (round 3: `..` resolved, absolute), so the spelling
    tried is the step's own request (parameters.Path). A model that requests the plain path of
    the same file instead, and has that denied, never tried the spelling: the probe FAILs
    saying it read a different spelling than asked, quoting both, and the other read probes
    still pass. Only the request's slash direction is undone (the default fixture turns every
    slash of the asked spelling into a backslash and its message names the canonical path, and
    test_agy_canary_pass still passes), never case or `..`."""
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


def test_agy_canary_read_probe_proof_is_its_request_and_its_denial(tmp_path, capsys):
    """A read probe passes on two facts of one step: its request is the asked spelling, and
    agy's permission check denied it naming the probe file (in agy's canonical spelling,
    test_agy_canary_pass). The asked spelling "denied" naming some other file is no denial of
    that step (agyjson: the target must be the step's own request), so it counts as run."""
    scenario = "canary_agy_deny_read_elsewhere"
    rig = _agy_canary_rig(tmp_path / scenario, scenarios={"relative-read": scenario})
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc["canary"]) == (1, "FAIL"), scenario
    failed = _failed(doc)
    assert ("the relative read probe: " in failed
            and "not denied by agy's permission check" in failed), failed
    assert _no_pass(rig), scenario


def test_agy_canary_relative_read_counts_the_rejection(tmp_path, capsys):
    """Owner ruling 2026-11-10 ("count the rejection"): agy 1.5.5 rejects a relative path
    before its permission check (round 3, gemini's relative read: `declaring permissions:
    failed to parse path: <path> must be an absolute path: path is not absolute`), so the
    relative read probe also passes when the step's request is exactly the asked relative
    spelling (slash direction aside) and that very step ended with agy's exact rejection; the
    model's later read of the plain path, denied, changes nothing. Any other outcome FAILs as
    a step that ran: a rejection of a rewritten path, another error, and the same rejection in
    any other read probe (only the relative one counts it; the rest need a real denial)."""
    scenario = "canary_agy_read_not_absolute"
    rig = _agy_canary_rig(tmp_path / scenario, scenarios={"relative-read": scenario})
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc["canary"]) == (0, "PASS"), _failed(doc)
    texts = " | ".join(c["check"] for c in doc["checks"] if c["ok"])
    asked, _ = _read_spellings(rig.repo / doc["attempt_dir"], rig.repo)["relative-read"]
    assert ("the relative read probe was rejected" in texts and "at step 2" in texts
            and repr(asked.replace("/", "\\")) in texts), texts  # fmt: skip
    fails = (("relative-read", "canary_agy_read_not_absolute_rewritten"),
             ("relative-read", "canary_agy_read_not_absolute_other"),
             ("dot-dot-read", "canary_agy_read_not_absolute"),
             ("different-case-read", "canary_agy_read_not_absolute"))  # fmt: skip
    for name, scenario in fails:
        here = tmp_path / f"{name}-{scenario}"
        rig = _agy_canary_rig(here, scenarios={name: scenario})
        code, doc = _agy_canary(rig, capsys)
        assert (code, doc["canary"]) == (1, "FAIL"), (name, scenario)
        failed = _failed(doc)
        assert (f"the {name.replace('-', ' ')} probe: " in failed
                and "not denied by agy's permission check" in failed), (name, scenario, failed)
        assert _no_pass(rig), (name, scenario)


def test_agy_canary_command_probes_count_either_command_kind(tmp_path, capsys):
    """Round 3: gemini's fetch was denied as `unsandboxed "curl.exe -sS https://example.com/"`
    (the default fetch fixture, its real shape) and the canary did not count that kind. A
    denial of kind unsandboxed or command naming the probe's marker is the attempt for both the
    fetch and the unsandboxed probe."""
    cases = (("fetch", "canary_agy_deny_fetch_command", "command(curl -sS"),
             ("unsandboxed", "canary_agy_deny_unsandboxed_kind", "unsandboxed(echo"))
    for name, scenario, shown in cases:
        rig = _agy_canary_rig(tmp_path / name, scenarios={name: scenario})
        code, doc = _agy_canary(rig, capsys)
        assert (code, doc["canary"]) == (0, "PASS"), (name, _failed(doc))
        texts = " | ".join(c["check"] for c in doc["checks"] if c["ok"])
        assert f"the {name} probe was denied: {shown}" in texts, (name, texts)


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


def test_agy_canary_allowed_session_must_edit_in_place(tmp_path, capsys):
    """agy 1.5.7's edit_file step stopped a night the canary had passed, because the canary
    never edited a file. The allowed session must make a known edit_file step that ran: one
    with no edit (the plan written whole) FAILs saying so, and one whose edit step has another
    shape (a Content parameter beside Path) FAILs as an unknown step and as no edit, so a
    version that renames or reshapes the edit step fails the canary, not the night."""
    rig = _agy_canary_rig(tmp_path / "none", scenarios={ALLOWED: "canary_agy_allowed_no_edit"})
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc["canary"]) == (1, "FAIL")
    failed = _failed(doc)
    assert "the allowed session made no in-place edit_file step" in failed, failed
    assert "agy audit knows" not in failed, failed
    assert _no_pass(rig)
    rig = _agy_canary_rig(tmp_path / "reshaped",
                          scenarios={ALLOWED: "canary_agy_allowed_edit_reshaped"})
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc["canary"]) == (1, "FAIL")
    failed = _failed(doc)
    assert "tool 'edit_file'" in failed and "is not a tool step the agy audit knows" in failed
    assert "the allowed session made no in-place edit_file step" in failed, failed
    assert _no_pass(rig)


def test_agy_canary_allowed_session_may_poll_its_backgrounded_check(tmp_path, capsys):
    """Spike 012 round 4: gemini-flash's allowed session polled its backgrounded `attempt
    check` with manage_task's status action, and the canary FAILed it as a step the audit did
    not know. That exact status poll is a known step, so the session passes; every tool step of
    it is one the audit knows."""
    rig = _agy_canary_rig(tmp_path, scenarios={ALLOWED: "canary_agy_allowed_background"})
    code, doc = _agy_canary(rig, capsys)
    assert (code, doc["canary"]) == (0, "PASS"), _failed(doc)
    texts = " | ".join(c["check"] for c in doc["checks"] if c["ok"])
    assert "every tool step of the allowed session is one the agy audit knows" in texts, texts


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
             ("unsandboxed", {"escape": "unsandboxed"}, "the unsandboxed probe went through"),
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


_CONVERSATION = "061fc4c3-3096-4cbd-808a-510b72fee051"


def test_agy_conversation_id_comes_from_the_init_event():
    """Spike 012 round 5: the session's own conversation id, from its first init event only,
    and only in UUID form (anything else is None, so no output folder is accepted)."""
    init = {"event": "init", "conversation_id": _CONVERSATION, "init": {}}
    assert agyjson.conversation_id([init]) == _CONVERSATION
    for odd in ("../x", "", None, 7, _CONVERSATION + "/x", _CONVERSATION.upper() + "\\"):
        assert agyjson.conversation_id([{**init, "conversation_id": odd}]) is None, odd
    assert agyjson.conversation_id([]) is None
    later = {"event": "step_update", "conversation_id": _CONVERSATION}
    assert agyjson.conversation_id([later]) is None


def test_agy_reads_of_the_sessions_own_outputs_are_not_strays(tmp_path):
    """Spike 012 round 5 (owner ruling 2026-11-11): agy hands a long command back and logs its
    output under ~/.gemini/antigravity-cli/brain/<conversation>/.system_generated/, and lets the
    model read that folder without asking the settings; Gemini read its own backgrounded
    `attempt check` logs (tasks/task-20.log) and the paged `attempt context` output
    (steps/8/output.txt). Those two file forms in the session's own folder are not strays;
    another conversation's, another name, a `..` spelling, a link, or no folder at all are."""
    repo = tmp_path / "repo"
    root = repo / ATTEMPT
    root.mkdir(parents=True)
    brain = tmp_path / "home" / ".gemini" / "antigravity-cli" / "brain"
    own = brain / _CONVERSATION / ".system_generated"
    for rel in ("tasks/task-20.log", "steps/8/output.txt", "steps/8/other.txt", "tasks/x.log"):
        (own / rel).parent.mkdir(parents=True, exist_ok=True)
        (own / rel).write_text("x", encoding="utf-8")
    other = brain / "11111111-2222-4333-8444-555555555555" / ".system_generated" / "tasks"
    other.mkdir(parents=True)
    good = [str(own / "tasks" / "task-20.log"), str(own / "steps" / "8" / "output.txt"),
            (own / "tasks" / "task-66.log").as_posix()]  # fmt: skip
    bad = [str(own / "steps" / "8" / "other.txt"), str(own / "tasks" / "x.log"),
           str(other / "task-20.log"), f"{own}\\tasks\\..\\tasks\\task-20.log",
           str(own.parent / "task-20.log")]  # fmt: skip
    reads = driver.read_strays([*good, *bad], attempt_dir=root, repo=repo, own_outputs=own)
    assert [s.split(": a read")[0] for s in reads] == bad, reads
    assert len(driver.read_strays(good, attempt_dir=root, repo=repo)) == len(good)


def test_agy_own_output_read_through_a_link_is_a_stray(tmp_path):
    """A link inside the session's own folder that resolves elsewhere is no own output."""
    from test_driver import _plant_dir_link

    repo = tmp_path / "repo"
    root = repo / ATTEMPT
    root.mkdir(parents=True)
    own = tmp_path / "brain" / _CONVERSATION / ".system_generated"
    (own / "steps").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "output.txt").write_text("x", encoding="utf-8")
    _plant_dir_link(own / "steps" / "9", elsewhere)
    reads = driver.read_strays([str(own / "steps" / "9" / "output.txt")], attempt_dir=root,
                               repo=repo, own_outputs=own)  # fmt: skip
    assert len(reads) == 1 and "outside the checkout" in reads[0], reads


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
