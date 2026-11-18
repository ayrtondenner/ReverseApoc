"""The GitHub Copilot CLI harness: Claude Haiku 5.5, Claude Sonnet 5.5 and GPT-6 Luna on the
owner's Copilot Pro AI credits as drive arms (owner ruling 2026-11-13, spike 013).

Owner rule: no test runs the real `copilot`. Every session here is tests/fakecopilot.py
replaying a synthetic fixture under tests/fixtures/copilot/ (shapes from the coordinator's
Copilot CLI 1.0.111 capture, every id made up, every path a fake slot); nothing contacts
GitHub. Every environment is built with made-up values over test_drive's key-free base, so a
key the owner has set can never reach an assertion or a log.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from reverseapoc import backends, copilotjson, driver, session, streamjson
from reverseapoc.streamjson import Disposition
from reverseapoc.targets import REPO_ROOT
from test_drive import Rig, _keyed
from test_driver import EXE, FUNC, RUN, UNIT, Night, Sess

HERE = Path(__file__).resolve().parent
FAKECOPILOT = HERE / "fakecopilot.py"
FIXTURES = HERE / "fixtures" / "copilot"
HAIKU = "copilot-haiku-5-5"
HAIKU_MODEL = "claude-haiku-5.5"
SONNET = "copilot-sonnet-5-5"
LUNA = "copilot-gpt-6-luna"
COPILOT_VERSION = "1.0.111"
WRAPPER = "uv run --frozen reverseapoc attempt"
NO_APPROVAL = ("Permission denied because no interactive user response was available. Retry in an "
               "interactive session so the user can approve it, or try an alternative that does "
               "not require this permission.")  # fmt: skip
REAL_DRIVE = driver.drive
PER_SESSION = f"{EXE}__{FUNC}__attempt-1"


def fake_copilot_argv(prompt: str, **values) -> list[str]:
    """Deps.copilot_argv for the tests: session.build_copilot_argv with tests/fakecopilot.py in
    the executable's place, so the fake checks the very argv the driver built."""
    real = session.build_copilot_argv(prompt, copilot="copilot", **values)
    return [sys.executable, str(FAKECOPILOT), *real[1:]]


def write_pass(repo: Path, arm: str = HAIKU, *, version: str = COPILOT_VERSION,
               result: str = "PASS") -> Path:  # fmt: skip
    """A canary-pass file as the Copilot canary writes it."""
    path = repo / "build" / "driver" / "canary" / f"{arm}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"arm": arm, "harness": "copilot", "cli_version": version,
                                "date": "2026-11-13", "result": result}), encoding="utf-8")
    return path


def copilot_version_reply(rig: Rig, version: str = COPILOT_VERSION) -> None:
    """The rig's runner answers `copilot --version` as the installed CLI 1.0.111 does."""
    rig.runner.replies.append((lambda argv: argv == ["copilot", "--version"],
                               (0, f"GitHub Copilot CLI {version}.\nRun 'copilot update' to "
                                   "check for updates.\n", "")))  # fmt: skip


def copilot_night(tmp_path: Path, monkeypatch, *, scenario: str = "night_success",
                  extra_env: dict | None = None,
                  spec: Sess | None = None) -> tuple[Rig, Night, dict]:  # fmt: skip
    """`drive` on a Rig whose night runs in test_driver's night harness with fakecopilot
    sessions and a fake gate; the base env names the fixture and holds no key."""
    rig = Rig(tmp_path / "rig")
    copilot_version_reply(rig)
    night = Night(tmp_path / "night", gate_exits=[1])
    night._current = spec or Sess(write=None)
    real = REAL_DRIVE

    def drive(config, deps, *, lock=None):
        moved = replace(config, repo_root=night.repo, min_cli_version=(2, 1, 240),
                        attempts_per_function=1)  # fmt: skip
        return real(moved, night.deps(copilot_argv=fake_copilot_argv, say=deps.say))

    monkeypatch.setattr(driver, "drive", drive)
    env = _keyed(rig.env, FAKECOPILOT_SCENARIO=scenario, **(extra_env or {}))
    return rig, night, env


def _run(capsys, rig: Rig, env: dict, arm: str = HAIKU) -> tuple[int, str, str]:
    write_pass(rig.repo, arm)
    return rig.drive(capsys, seams={"base_env": env}, night_model=arm, allow_egress=(arm,),
                     workers=1)  # fmt: skip


def _stopped(night: Night) -> dict:
    (stopped,) = [r for r in night.kinds("run") if r["event"] == "STOPPED"]
    return stopped


# ---- the runtime exception, the arms, the argv, the prompt and the env ----


def test_exception_names_copilot():
    """Owner ruling 2026-11-13: CLAUDE.md and .claude/rules/workflow.md name GitHub Copilot CLI
    in the one scoped exception (drive sessions only, config under build/) and commit no
    Copilot config tree."""
    for rel in ("CLAUDE.md", ".claude/rules/workflow.md"):
        text = " ".join((REPO_ROOT / rel).read_text(encoding="utf-8").split())
        for needle in ("only agent runtime", "GitHub Copilot CLI", "Copilot Pro",
                       "reverseapoc drive", "build/", ".github/copilot/", ".copilot/"):
            assert needle in text, (rel, needle)
    assert not (REPO_ROOT / ".github" / "copilot").exists()
    assert not (REPO_ROOT / ".copilot").exists()


def test_build_copilot_argv(tmp_path):
    """The argv of one Copilot session: the prompt right after -p, the model, JSONL output
    streamed, no auto-update, no custom instructions, no built-in MCP server, no ask_user, no
    temp dir, the five tools the audit knows and nothing else visible, one shell rule, a write
    rule per session file, read and write denied under each forbidden root, URLs and memory
    denied, the session's AI-credit cap and its usage file. Never an allow-everything flag, an
    added directory or a trusted folder."""
    unit = tmp_path / "a" / "view" / "src" / "ufo2p" / "u_1.c"
    notes = tmp_path / "a" / "notes.md"
    usage = tmp_path / "copilot" / "x.usage.json"
    argv = session.build_copilot_argv("PROMPT", copilot="copilot", model=HAIKU_MODEL,
                                      writes=[unit, notes],
                                      forbidden=[tmp_path / "orig", tmp_path / "third_party"],
                                      usage_file=usage, max_ai_credits=30)  # fmt: skip
    assert argv == [
        "copilot", "-p", "PROMPT", "--model", HAIKU_MODEL, "--output-format", "json",
        "--stream", "on", "--no-auto-update", "--no-custom-instructions",
        "--disable-builtin-mcps", "--no-ask-user", "--disallow-temp-dir",
        "--available-tools", "view", "create", "edit", "powershell", "read_powershell",
        "--allow-tool", session.COPILOT_SHELL_RULE,
        "--allow-tool", f"write({unit.as_posix()})", "--allow-tool", f"write({notes.as_posix()})",
        "--deny-tool", f"read({(tmp_path / 'orig').as_posix()}/**)",
        "--deny-tool", f"write({(tmp_path / 'orig').as_posix()}/**)",
        "--deny-tool", f"read({(tmp_path / 'third_party').as_posix()}/**)",
        "--deny-tool", f"write({(tmp_path / 'third_party').as_posix()}/**)",
        "--deny-tool", "url", "--deny-tool", "memory",
        "--max-ai-credits", "30", "--usage-output-file", str(usage)]  # fmt: skip
    for banned in ("--allow-all", "--yolo", "--allow-all-tools", "--allow-all-paths",
                   "--allow-all-urls", "--add-dir", "--trust-folder", "--autopilot"):
        assert banned not in argv, banned
    assert list(copilotjson.AVAILABLE_TOOLS) == argv[15:20]
    # security review (coordinator, 2026-11-13): the one shell rule names the dedicated wrapper
    # executable only, never uv (uv:* would pre-approve `uv run python -c ...`)
    assert session.COPILOT_SHELL_RULE == "shell(reverseapoc-attempt)"
    shell = [arg for arg in argv if arg.startswith("shell(")]
    assert shell == [session.COPILOT_SHELL_RULE]


def test_the_wrapper_executable_is_the_attempt_wrapper(monkeypatch):
    """`reverseapoc-attempt <form>` (a console script of the package, so Windows starts it as
    an .exe with no cmd.exe parsing) is `reverseapoc attempt <form>`, whose own first step
    refuses anything but an exact form of the session's kind."""
    import tomllib

    from reverseapoc import cli

    scripts = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert scripts["project"]["scripts"][session.COPILOT_WRAPPER] == "reverseapoc.cli:attempt_main"
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv=None: seen.append(argv) or 0)
    assert cli.attempt_main(["check", "--sweep"]) == 0
    assert seen == [["attempt", "check", "--sweep"]]


def test_the_wrapper_executable_refuses_a_non_form(monkeypatch, capsys):
    """A form outside the session kind's list exits 2 before anything runs: refused by the
    parser (extra arguments) or by the wrapper's own form check (a matching-only verb in a
    readability session)."""
    from reverseapoc import attempt, cli

    ran = []
    for name in ("cmd_check", "cmd_plan", "cmd_context", "cmd_asm"):
        monkeypatch.setattr(attempt, name, lambda *a, **kw: ran.append(a) or 0)
    for bad in (["context", "extra"], ["asm", "a", "b"], ["check", "--src", "x"]):
        with pytest.raises(SystemExit) as stop:
            cli.attempt_main(bad)
        assert stop.value.code == 2, bad
    monkeypatch.setenv(attempt.SESSION_KIND_ENV, "readability")
    assert cli.attempt_main(["plan"]) == 2
    assert ran == []
    assert "accepts only" in capsys.readouterr().err


def test_copilot_arms_load():
    """The three Copilot arms: harness copilot, backend github, the pack leaves the machine
    (--allow-egress), the init must name the requested model, a vendor co-author, four
    workers, a 30-credit session cap, the subscription billing, and GitHub's AI-credit rates as
    USD per million tokens (1 credit = $0.01; Haiku and Luna at the default context tier)."""
    arms = backends.load_arms()
    expected = {HAIKU: ("claude-haiku-5.5", "Claude Haiku 5.5 <noreply@anthropic.com>",
                        (0.10, 0.50, 0.01, 0.125)),
                SONNET: ("claude-sonnet-5.5", "Claude Sonnet 5.5 <noreply@anthropic.com>",
                         (2.00, 10.00, 0.10, 2.50)),
                LUNA: ("gpt-6-luna", "GPT-6 Luna <noreply@openai.com>",
                       (0.10, 0.50, 0.01, 0.125))}  # fmt: skip
    for name, (model, coauthor, prices) in expected.items():
        arm = arms[name]
        assert (arm.harness, arm.backend, arm.model) == ("copilot", "github", model), name
        assert arm.sends_disassembly and arm.egress and arm.billing == backends.SUBSCRIPTION
        assert arm.accepted_init == (model,) and arm.coauthor == coauthor, name
        # owner, 2026-11-16: spend the month's credits in 5 hours. Haiku 16 workers (~700 s and
        # 2.7 credits a session); Sonnet a 60-credit cap, since a Haiku-length session at its
        # rates is about 35 credits and 30 would cut it short; Luna keeps 4 and 30
        caps = {HAIKU: (16, 30), SONNET: (4, 60)}.get(name, (4, 30))
        assert (arm.max_workers, arm.max_ai_credits) == caps, name
        assert (arm.base_url, arm.key_env) == (None, None), name
        got = (arm.prices.input, arm.prices.output, arm.prices.cache_read,
               arm.prices.cache_creation)  # fmt: skip
        assert got == pytest.approx(prices), name


def _table(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "backends.toml"
    path.write_text(body, encoding="utf-8")
    return path


COPILOT_ARM = """[arms."c"]
harness = "copilot"
backend = "github"
model = "claude-haiku-5.5"
sends_disassembly = true
accepted_init = ["claude-haiku-5.5"]
coauthor = "Claude Haiku 5.5 <noreply@anthropic.com>"
max_workers = 4
{extra}
[arms."c".prices]
input = 0.1
output = 0.5
cache_read = 0.01
cache_creation = 0.125
"""


def test_max_ai_credits_is_a_copilot_cap_of_at_least_30(tmp_path):
    """`max_ai_credits` (Copilot's --max-ai-credits, minimum 30): 30 when absent, refused
    below 30 or not a whole number, and refused on any other harness."""
    assert backends.load_arms(_table(tmp_path, COPILOT_ARM.format(extra="")))["c"].max_ai_credits \
        == 30
    assert backends.load_arms(_table(tmp_path, COPILOT_ARM.format(
        extra="max_ai_credits = 45")))["c"].max_ai_credits == 45
    for bad in ("max_ai_credits = 29", "max_ai_credits = 30.5", "max_ai_credits = true"):
        with pytest.raises(backends.ArmError, match="max_ai_credits"):
            backends.load_arms(_table(tmp_path, COPILOT_ARM.format(extra=bad)))
    other = COPILOT_ARM.format(extra="max_ai_credits = 30").replace('"copilot"', '"agy"')
    with pytest.raises(backends.ArmError, match="max_ai_credits"):
        backends.load_arms(_table(tmp_path, other))
    assert backends.load_arms()["gemini-flash"].max_ai_credits is None


def test_copilot_prompt():
    """A Copilot session loads no skill of ours and runs no hook of ours, so its prompt is
    the signed-in harnesses' (goal, skill body, harness note with the wait instruction, session
    rules) plus the one read its view tool may make: inside the attempt directory."""
    goal = session.goal_prompt(FUNC, UNIT, EXE, unit_path=(
        f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/view/src/{EXE}/{UNIT}.c"))
    skill = "---\nname: watcom-decomp\ndescription: x\n---\n# Matching one Watcom function\n"
    text = session.copilot_prompt(goal, skill)
    assert not text.startswith("/goal") and "# Matching one Watcom function" in text
    assert "name: watcom-decomp" not in text
    assert session.WAIT_NOTE in text and "Harness note" in text
    assert "view tool may also read files inside this attempt's directory" in text
    # the session's wrapper is the dedicated executable, in the goal, the skill and the rules
    assert "Session rules" in text and f"`{session.COPILOT_WRAPPER} check`" in text
    assert WRAPPER not in text


def test_copilot_prompt_forbids_scratch_copies_of_the_session_files():
    """Runs 20261116-copilot2 to -fable-ab: Sonnet 5.5 tried plan2.json, plan.json.tmp,
    giveup.json.tmp, giveup2.json and giveup.json2; Copilot refused each, and each such session
    was spent. The Copilot prompt says to write each session file in place (create it once,
    then edit it), never a temporary or numbered copy and no other file. The other signed-in
    harnesses' prompts are unchanged."""
    goal = session.goal_prompt(FUNC, UNIT, EXE, unit_path=(
        f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/view/src/{EXE}/{UNIT}.c"))
    skill = "---\nname: watcom-decomp\ndescription: x\n---\n# Matching one Watcom function\n"
    text = session.copilot_prompt(goal, skill)
    assert "in place" in text and "then change it with your edit tool" in text
    # the unit exists before the session (the driver's view): it is edited, never created
    assert "edit your unit" in text
    for copy in ("plan.json.tmp", "plan2.json", "giveup.json2"):
        assert copy in text, copy
    assert "Copilot refuses every other write" in text
    rules = text.rindex("Session rules")
    assert text.index("in place") > rules  # it follows the list of files it means
    assert "plan.json.tmp" not in session.codex_prompt(goal, skill)
    assert "plan.json.tmp" not in session.agy_prompt(goal, skill)


def test_copilot_session_path_leads_with_the_wrapper_executable(tmp_path, capsys, monkeypatch):
    """The session's PATH starts with the directory of the driver's own interpreter (the
    package's console scripts, reverseapoc-attempt among them), so the bare name the shell
    rule allows resolves to the checkout's wrapper."""
    import os

    rig, night, env = copilot_night(tmp_path, monkeypatch)
    code, _, err = _run(capsys, rig, env)
    assert code == 0, err
    launched = night.launched[0].env
    (key,) = [name for name in launched if name.upper() == "PATH"]
    first = launched[key].split(os.pathsep)[0]
    assert Path(first) == Path(sys.executable).parent
    assert driver.copilot_wrapper_exe() is not None


LEAKS = {"OPENAI_API_KEY": "made-up-openai-0001", "OPENROUTER_API_KEY": "made-up-0004",
         "ANTHROPIC_API_KEY": "made-up-0005", "GOOGLE_API_KEY": "made-up-0007",
         "GH_TOKEN": "made-up-0009", "GITHUB_TOKEN": "made-up-0010",
         "COPILOT_GITHUB_TOKEN": "made-up-0011", "COPILOT_ALLOW_ALL": "true",
         "COPILOT_PROVIDER_BASE_URL": "https://z.invalid", "COPILOT_HOME": "made-up-home",
         "COPILOT_OTEL_FILE_EXPORTER_PATH": "made-up-path"}  # fmt: skip


def test_copilot_session_env_strips_every_other_vendor_and_copilot_setting():
    """The env builder: a Copilot session loses every vendor's routing and credential variable,
    the GitHub tokens (Copilot would take them over its sign-in) and every inherited COPILOT_*
    variable (COPILOT_ALLOW_ALL approves every tool, COPILOT_PROVIDER_* reroutes the model, an
    inherited COPILOT_HOME would load the owner's config); the driver then sets its own. A
    Claude session loses the GitHub tokens and COPILOT_* too: no harness sees another vendor's
    credential."""
    arms = backends.load_arms()
    base = {"PATH": "made-up-path", **LEAKS}
    for name in (HAIKU, SONNET, LUNA):
        assert sorted(backends.session_env(arms[name], base, arms)) == ["PATH",
                                                                        "REVERSEAPOC_EGRESS"]
    assert sorted(backends.session_env(arms["claude-opus-5-5"], base, arms)) == ["PATH"]


# ---- the stream: copilotjson ----

WS = "C:\\made-up\\ws"


def _start(**data) -> dict:
    payload = {"copilotVersion": COPILOT_VERSION, "selectedModel": HAIKU_MODEL,
               "sessionLimits": {"maxAiCredits": 30}, "context": {"cwd": WS}, **data}
    return {"type": "session.start", "data": payload, "id": "e0", "parentId": None}


def _call(ident: str, tool: str, arguments: dict, *, ok: bool = True, error: str | None = None,
          code: str = "denied", edits: tuple = (), content: str = "made up",
          start: dict | None = None, event: dict | None = None) -> list[dict]:  # fmt: skip
    began = {"type": "tool.execution_start", "data": {
        "toolCallId": ident, "toolName": tool, "arguments": arguments, "turnId": "0",
        "model": HAIKU_MODEL, **(start or {})}, **(event or {})}
    done = {"toolCallId": ident, "model": HAIKU_MODEL, "turnId": "0", "success": ok}
    if error is not None:
        done["error"] = {"message": error, "code": code}
    if ok:
        done["result"] = {"content": content}
    if edits:
        done["fileEdits"] = [{"path": p, "kind": k} for p, k in edits]
    return [began, {"type": "tool.execution_complete", "data": done, **(event or {})}]


def _result(code: int = 0, modified: tuple = ()) -> dict:
    return {"type": "result", "exitCode": code, "usage": {
        "premiumRequests": 1, "sessionDurationMs": 10608,
        "codeChanges": {"filesModified": list(modified)}}}


RULE = ("Permission to run this tool was denied due to the following rules: "
        "`read(C:/made-up/ws/secret.txt)`")  # fmt: skip


def _with_guidance(text: str) -> list[dict]:
    """A view whose result carries `text` after Copilot's postToolUse guidance header."""
    content = ("alpha\n\nTool \"view\" succeeded. Additional guidance from postToolUse "
               f"hooks:\n{text}")
    return [_start(), *_call("t1", "view", {"path": f"{WS}\\x.txt"}, content=content)]


def test_copilotjson_a_view_with_a_line_range_is_known():
    """Night 20261114-nearmiss: Haiku viewed its unit with `view_range` [start, end]; that read
    stopped the night as an unknown shape. Two integers are known; anything else is not."""
    for good in ([1, 40], [10, -1]):
        events = [_start(), *_call("t1", "view", {"path": f"{WS}\\x.txt", "view_range": good})]
        assert copilotjson.unknown_steps(events) == [], good
        assert copilotjson.read_targets(events) == [f"{WS}\\x.txt"]
    for bad in ([1], [1, 2, 3], ["1", "2"], [True, 2], "1-40"):
        events = [_start(), *_call("t1", "view", {"path": f"{WS}\\x.txt", "view_range": bad})]
        assert copilotjson.unknown_steps(events), bad


def test_copilotjson_a_view_forcing_a_large_read_is_known():
    """Run 20261114-opus-sonnet: a view with `forceReadLargeFiles` stopped the night. 1.0.111's
    own view schema is {path, view_range?, forceReadLargeFiles?: boolean} (runtime.node, read
    2026-11-16): the flag lifts only the size check, and the path is judged as any view. Its
    flattened `view_range[0]`/`[1]` form and powershell's `detach` stay unknown."""
    path = f"{WS}\\x.txt"
    for flag in (True, False):
        events = [_start(), *_call("t1", "view", {"path": path, "forceReadLargeFiles": flag})]
        assert copilotjson.unknown_steps(events) == [], flag
        assert copilotjson.read_targets(events) == [path]
    both = {"path": path, "view_range": [1, 40], "forceReadLargeFiles": True}
    assert copilotjson.unknown_steps([_start(), *_call("t1", "view", both)]) == []
    for bad in ({"path": path, "forceReadLargeFiles": "true"},
                {"path": path, "forceReadLargeFiles": 1},
                {"path": path, "view_range[0]": 1, "view_range[1]": 40}):
        assert copilotjson.unknown_steps([_start(), *_call("t1", "view", bad)]), bad
    detached = {"command": "reverseapoc-attempt context", "detach": True}
    assert copilotjson.unknown_steps([_start(), *_call("t1", "powershell", detached)])


def _cache_break(tools=copilotjson.AVAILABLE_TOOLS, model: str = HAIKU_MODEL,
                 after: bool = True) -> dict:  # fmt: skip
    """1.0.111's `prompt_cache_break` (run 20261116-copilot, its shape cut to what is judged)."""
    request = {"model": model, "tool_count": len(tools), "tools_truncated": 0,
               "tools": [{"name": t, "schema_hash": "0", "safe": True} for t in tools]}
    data = {"primaryReason": "history_rewritten", "contributingReasons": ["history_rewritten"],
            "beforeRequest": request, **({"afterRequest": request} if after else {})}
    return {"type": "prompt_cache_break", "data": data}


def test_copilotjson_a_prompt_cache_break_of_the_sessions_tools_is_known(tmp_path):
    """Run 20261116-copilot stopped on `prompt_cache_break`: the CLI's event schema calls it "a
    detected loss of a previously cached prompt prefix"; it runs nothing. It is known only when
    both its requests list no tool but the five the session was given; the models they name
    join the init check, so another model still fails closed."""
    assert copilotjson.unknown_steps([_start(), _cache_break()]) == []
    for bad in (_cache_break(tools=(*copilotjson.AVAILABLE_TOOLS, "web_fetch")),
                _cache_break(after=False),
                {"type": "prompt_cache_break", "data": {"beforeRequest": "x", "afterRequest": {}}}):
        assert copilotjson.unknown_steps([_start(), bad]), bad
    cwd = tmp_path / "ws"
    cwd.mkdir()
    events = [_start(context={"cwd": str(cwd)}), _cache_break(model="gpt-6-luna")]
    problems = copilotjson.init_problems(events, cwd=cwd, accepted=(HAIKU_MODEL,),
                                         max_ai_credits=30)  # fmt: skip
    assert any("gpt-6-luna" in p for p in problems)
    events[1] = _cache_break()
    assert copilotjson.init_problems(events, cwd=cwd, accepted=(HAIKU_MODEL,),
                                     max_ai_credits=30) == []  # fmt: skip


def _notification(kind: dict) -> dict:
    """1.0.111's `system.notification` (run 20261116-fable-ab, cut to what is judged)."""
    content = ("<system_notification>\nShell command \"Print context pack\" (shellId: 1) has "
               "completed successfully.\n</system_notification>")
    return {"type": "system.notification", "data": {"content": content, "kind": kind}}


def test_copilotjson_only_a_shell_completed_notification_is_known():
    """Run 20261116-fable-ab stopped on `system.notification` ("runtime events like background
    task completion", 1.0.111's event schema): kind `shell_completed` reports a powershell
    command the audit already judged by its own call. Only that kind, with a string shellId
    and an integer exit code, is known; another kind (`instruction_discovered`, an agent's
    completion) or a malformed one stays unknown."""
    done = {"type": "shell_completed", "shellId": "1", "exitCode": 0,
            "description": "Print context pack"}
    assert copilotjson.unknown_steps([_start(), _notification(done)]) == []
    for bad in ({"type": "instruction_discovered", "path": "AGENTS.md"},
                {**done, "shellId": 1}, {**done, "exitCode": "0"}, {**done, "exitCode": True},
                {"type": "agent_completed"}):
        assert copilotjson.unknown_steps([_start(), _notification(bad)]), bad
    assert copilotjson.unknown_steps([_start(), {"type": "system.notification", "data": {}}])


# The event review of 2026-11-18 read Copilot CLI 1.0.111's own event schema, which is only on a
# machine with the CLI installed (CI and the container skip). A new CLI version gets the same
# review, then this path moves to it.
_LOCAL = os.environ.get("LOCALAPPDATA")
REVIEWED_SCHEMA = (Path(_LOCAL) / "copilot" / "pkg" / "win32-x64" / COPILOT_VERSION / "schemas"
                   / "session-events.schema.json") if _LOCAL else None  # fmt: skip


def _schema_constants(definitions: dict, union: str) -> set[str]:
    """The `type` constant of every member of the schema's `union` definition."""
    refs = (ref["$ref"].rsplit("/", 1)[-1] for ref in definitions[union]["anyOf"])
    return {definitions[name]["properties"]["type"]["const"] for name in refs}


def test_copilotjson_every_event_type_of_the_reviewed_schema_is_judged():
    """Six Copilot audit stops on 2026-11-16 were event types no review had read. Every event
    type 1.0.111's schema documents (and every system.notification kind) is now known, known
    only in an exact shape, or kept unknown on purpose with a reason; `result` is the one
    stdout line the schema does not list."""
    if REVIEWED_SCHEMA is None or not REVIEWED_SCHEMA.is_file():
        pytest.skip("Copilot CLI 1.0.111's event schema is not installed here")
    definitions = json.loads(REVIEWED_SCHEMA.read_text(encoding="utf-8"))["definitions"]
    known, shaped = copilotjson.KNOWN_EVENTS, copilotjson.SHAPED_EVENTS
    kept = set(copilotjson.KEPT_UNKNOWN)
    assert _schema_constants(definitions, "SessionEvent") == (known | shaped | kept) - {"result"}
    kinds = _schema_constants(definitions, "SystemNotification")
    assert kinds == {"shell_completed", *copilotjson.KEPT_UNKNOWN_NOTIFICATIONS}


def test_copilotjson_the_installed_cli_is_the_reviewed_one():
    """A new CLI version can document event types the review never read: every Copilot CLI
    package installed here must be the reviewed version until its schema gets the same review
    (then COPILOT_VERSION and the classes move with it)."""
    packages = Path(_LOCAL) / "copilot" / "pkg" / "win32-x64" if _LOCAL else None
    if packages is None or not packages.is_dir():
        pytest.skip("no Copilot CLI package installed here")
    # a version folder's name starts with its major number (beside it: .session-operation-locks)
    installed = sorted(p.name for p in packages.iterdir() if p.is_dir() and p.name[:1].isdigit())
    assert installed == [COPILOT_VERSION], f"review the event schema of {installed}"


def test_copilotjson_event_classes_are_disjoint():
    """An event type is in exactly one of the review's three classes, and under one reason."""
    known, shaped = copilotjson.KNOWN_EVENTS, copilotjson.SHAPED_EVENTS
    kept = set(copilotjson.KEPT_UNKNOWN)
    assert not known & shaped and not known & kept and not shaped & kept
    assert "shell_completed" not in copilotjson.KEPT_UNKNOWN_NOTIFICATIONS
    assert len(kept) == sum(len(kinds) for kinds in copilotjson._KEPT.values())


def test_copilotjson_an_event_of_a_subagent_is_unknown():
    """The CLI's schema puts `agentId` on the envelope of a subagent's events; none of the
    436 recorded sessions has one. Any event carrying it is unknown, known type or not."""
    for event in ({"type": "assistant.intent", "data": {"intent": "x"}},
                  {"type": "assistant.usage", "data": _usage()},
                  {"type": "assistant.message", "data": {"content": "x"}}):
        assert copilotjson.unknown_steps([_start(), event]) == [], event
        (step,) = copilotjson.unknown_steps([_start(), {**event, "agentId": "a1"}])
        assert "subagent" in step, event


# one made-up payload in 1.0.111's schema shape for each type the review made known as is
REVIEW_KNOWN = {
    "assistant.intent": {"intent": "Reading the context pack"},
    "assistant.streaming_delta": {"totalResponseSizeBytes": 512},
    "session.title_changed": {"title": "Match func_00012340"},
    "session.todos_changed": {},
    "session.quota_observation": {"observation": {"quotaId": "q", "unit": "ai_credits"}},
    "session.completion_receipt": {"schemaVersion": 1, "attempt": 1, "sourceEventId": "e1",
                                   "eventRange": {}, "stopReason": "end_turn",
                                   "successfulToolCount": 3, "failedToolCount": 0},
    "pending_messages.modified": {},
    "capabilities.changed": {"ui": {}},
    "commands.changed": {"commands": []},
    "session.binary_asset": {"assetId": "a1", "type": "image", "mimeType": "image/png",
                             "byteLength": 4, "data": "AAAA"},
    "session.request_body_compression_disabled": {"encoding": "zstd"},
    "session.indexed_search": {},
    "session.journal_link": {"version": 1, "sessionId": "s1", "previousFile": "events.1.jsonl"},
    "instruction.update_delivery": {"deliveryId": "d1", "firstUpdateEventId": "e1",
                                    "latestUpdateEventId": "e1", "updateCount": 1,
                                    "requestGeneration": 1, "outcome": "delivered",
                                    "capability": "x", "reason": "x"},
    "session_limits_exhausted.requested": {"requestId": "r1", "usedAiCredits": 30.4,
                                           "maxAiCredits": 30},
}


def test_copilotjson_the_reviews_plain_events_run_nothing():
    """The review's known-as-is types (2026-11-18): each runs nothing and names no tool, path,
    model, agent, hook, permission or instruction text the audit would have to judge."""
    assert set(REVIEW_KNOWN) <= copilotjson.KNOWN_EVENTS
    for kind, data in REVIEW_KNOWN.items():
        assert copilotjson.unknown_steps([_start(), {"type": kind, "data": data}]) == [], kind


def _usage(**extra) -> dict:
    """A model call's usage as 1.0.111 persists it (cut to what is judged): `initiator` is
    `user` on the first call and `agent` on the rest, `interactionType` conversation-agent."""
    return {"model": HAIKU_MODEL, "initiator": "agent", "interactionType": "conversation-agent",
            "inputTokens": 4, "outputTokens": 345, **extra}


def _usage_events(usage: dict) -> list[dict]:
    """The two events that carry a usage: the live one and its durable record."""
    return [{"type": "assistant.usage", "data": usage},
            {"type": "session.usage_record", "data": {"usage": usage}}]


def test_copilotjson_a_usage_of_the_main_agent_is_known(tmp_path):
    """`session.usage_record`, "internal durable accounting receipt; the live usage event
    shares its accounting identity" (assistant.usage). 1.0.111 persists one per model call
    (7,405 in 436 sessions, every one `user` or `agent` and conversation-agent) but streams
    none. A usage is known only in that shape: a sub-agent's, an MCP sampling's or a
    background call's is not, and its model joins the model check."""
    for usage in (_usage(), _usage(initiator="user")):
        for event in _usage_events(usage):
            assert copilotjson.unknown_steps([_start(), event]) == [], event
    no_initiator = {k: v for k, v in _usage().items() if k != "initiator"}
    for bad in (_usage(initiator="sub-agent"), _usage(initiator="mcp-sampling"),
                _usage(interactionType="conversation-subagent"),
                _usage(interactionType="conversation-background"),
                _usage(parentToolCallId="t0"), no_initiator):
        for event in _usage_events(bad):
            assert copilotjson.unknown_steps([_start(), event]), event
    assert copilotjson.unknown_steps([_start(), {"type": "session.usage_record", "data": {}}])
    cwd = tmp_path / "ws"
    cwd.mkdir()
    for event in _usage_events(_usage(model="gpt-6-luna")):
        problems = copilotjson.init_problems([_start(context={"cwd": str(cwd)}), event], cwd=cwd,
                                             accepted=(HAIKU_MODEL,), max_ai_credits=30)
        assert any("gpt-6-luna" in p for p in problems), event


def test_copilotjson_tool_progress_is_known_only_for_a_started_call():
    """`tool.execution_progress`, "tool execution progress notification with status message":
    it runs nothing, and is known only while it names a call this session already started
    (the call itself is judged as any call)."""
    progress = {"type": "tool.execution_progress",
                "data": {"toolCallId": "t1", "progressMessage": "Running"}}
    began, done = _call("t1", "powershell", {"command": "reverseapoc-attempt check"})
    assert copilotjson.unknown_steps([_start(), began, progress, done]) == []
    assert copilotjson.unknown_steps([_start(), progress, began, done])
    other = {**progress, "data": {"toolCallId": 1, "progressMessage": "Running"}}
    assert copilotjson.unknown_steps([_start(), began, other, done])


def test_copilotjson_an_exhausted_credit_cap_is_known_only_when_left_as_set():
    """`session_limits_exhausted.completed` closes the prompt the driver's --max-ai-credits cap
    raised. Only action `cancel` ("leave the limit unchanged") is known; `add`, `set` and
    `unset` would lift the cap the driver set."""
    def done(response: object) -> dict:
        return {"type": "session_limits_exhausted.completed",
                "data": {"requestId": "r1", "response": response}}

    assert copilotjson.unknown_steps([_start(), done({"action": "cancel"})]) == []
    for bad in ({"action": "add", "additionalAiCredits": 30}, {"action": "set",
                                                               "maxAiCredits": 90},
                {"action": "unset"}, {}, "cancel"):
        assert copilotjson.unknown_steps([_start(), done(bad)]), bad


def test_copilotjson_events_kept_unknown_name_their_reason():
    """The review keeps unknown on purpose anything that names instructions, agents, hooks,
    permissions, a model or mode switch, a cwd change or a write no call names: each stops the
    night with its reason. A type the review never read stops it too."""
    for kind in ("abort", "session.model_change", "system.message", "permission.requested",
                 "session.context_changed", "session.workspace_file_changed",
                 "assistant.server_tool_progress", "session.tool_outcomes_recorded"):
        (step,) = copilotjson.unknown_steps([_start(), {"type": kind, "data": {}}])
        assert "on purpose" in step and copilotjson.KEPT_UNKNOWN[kind] in step, kind
    (step,) = copilotjson.unknown_steps([_start(), _notification({"type": "agent_completed"})])
    assert copilotjson.KEPT_UNKNOWN_NOTIFICATIONS["agent_completed"] in step
    (step,) = copilotjson.unknown_steps([_start(), {"type": "made.up", "data": {}}])
    assert "not one the Copilot audit knows" in step


SPILL = str(copilotjson.SPILL_DIR / ("1794634688790-copilot-tool-output-63812-"
                                     "1ab393a8-15b8-44fc-a7e1-ddd8ce48b339.txt"))


def _spilled(path: str = SPILL) -> list[dict]:
    """A shell call whose result Copilot spilled to `path` (night 20261114-nearmiss2)."""
    content = f"Output too large to read at once (22.9 KB). Saved to: {path}\n\n```asm\n# f"
    return _call("t1", "powershell", {"command": "reverseapoc-attempt asm"}, content=content)


def test_copilotjson_a_view_of_the_sessions_own_spill_is_no_read():
    """Night 20261114-nearmiss2: a result too large to show was saved by Copilot to
    `<temp>/<n>-copilot-tool-output-<pid>-<uuid>.txt` and the model viewed it, a read outside
    the checkout that stopped the night. A view of exactly a path an earlier result of this
    session announced, in that form, directly in the temp dir, is the session's own output;
    any other path, an unannounced spill, one announced only later, or one outside the temp
    dir is still a read (fail closed)."""
    view = _call("t2", "view", {"path": SPILL})
    assert copilotjson.read_targets([_start(), *_spilled(), *view]) == []
    assert copilotjson.read_targets([_start(), *view]) == [SPILL]  # never announced
    assert copilotjson.read_targets([_start(), *view, *_spilled()]) == [SPILL]  # announced later
    other = SPILL.replace("63812", "99999")
    assert copilotjson.read_targets([_start(), *_spilled(), *_call("t2", "view", {"path": other})]
                                    ) == [other]  # fmt: skip
    elsewhere = "C:\\made-up\\" + SPILL.rsplit("\\", 1)[-1]
    assert copilotjson.read_targets([_start(), *_spilled(elsewhere),
                                     *_call("t2", "view", {"path": elsewhere})]) == [elsewhere]


def test_copilot_audit_passes_wrapper_forms_chained_with_semicolons_only():
    """Night 20261114-lanesC4: Copilot ran `reverseapoc-attempt context; reverseapoc-attempt
    asm` in one powershell call (its shell rule allowed each part). A chain whose every part,
    split on `;`, is an exact wrapper form is those forms; an empty part, another separator, or
    any part that is not an exact form is still a stray."""
    wrapper = session.COPILOT_WRAPPER
    ok = (f"{wrapper} context; {wrapper} asm", f"{wrapper} context;{wrapper} plan")
    for command in ok:
        assert driver.copilot_command_strays([command]) == [], command
    bad = (f"{wrapper} context; whoami", f"{wrapper} context && {wrapper} asm",
           f"{wrapper} context;", f"; {wrapper} context", f"{wrapper} context | {wrapper} asm",
           f"{wrapper} context; uv run --frozen reverseapoc attempt asm")
    for command in bad:
        assert driver.copilot_command_strays([command]), command


def test_copilot_audit_passes_the_wrappers_help_forms_only():
    """Run 20261116-copilot2: Haiku ran `reverseapoc-attempt check --help` (Copilot's shell rule
    allows the wrapper with any arguments). The attempt parser's argparse prints usage and
    exits before any command runs, so exactly `<wrapper> [<verb>] --help|-h` is known, alone or
    in a `;` chain; a help flag beside any other argument (where it may be an option's value,
    as in `--note=-h`) or after an unknown verb is still a stray."""
    wrapper = session.COPILOT_WRAPPER
    ok = (f"{wrapper} check --help", f"{wrapper} check -h", f"{wrapper} --help",
          f"{wrapper} asm --help", f"{wrapper} plan -h",
          f"{wrapper} context; {wrapper} check --help")
    for command in ok:
        assert driver.copilot_command_strays([command]) == [], command
    bad = (f"{wrapper} check --sweep --help", f"{wrapper} check --note=-h",
           f"{wrapper} shell --help", f"{wrapper} check  --help", f"{wrapper} check --help x",
           f"{wrapper} --help check", f"{wrapper} check --HELP")
    for command in bad:
        assert driver.copilot_command_strays([command]), command


def test_copilotjson_a_file_tool_ignores_keys_no_cli_schema_has():
    """Nights 20261114-nearmiss7 and -lanesC3: create carried `file_path: "x"` and
    `description: "Create check-note.json"`, which the CLI drops; it wrote through `path`.
    Security review of 469cab57 (an allowlist, not a denylist): only those two observed keys,
    only on create and edit, and only when the completion's fileEdits name exactly the call's
    own path, are excused. Any other extra key, any extra key on view or powershell, and a
    completion with no fileEdits or with another path stay unknown (fail closed)."""
    note = f"{WS}\\check-note.json"
    for extra in ({"description": "Create check-note.json"}, {"file_path": "x"}):
        call = _call("t1", "create", {"path": note, "file_text": "{}", **extra},
                     edits=((note, "create"),))
        assert copilotjson.unknown_steps([_start(), *call]) == [], extra
        assert copilotjson.write_targets([_start(), *call]) == [note]
        for edits in ((), ((f"{WS}\\other.json", "create"),)):
            call = _call("t1", "create", {"path": note, "file_text": "{}", **extra}, edits=edits)
            assert copilotjson.unknown_steps([_start(), *call]), (extra, edits)
    for extra in ({"label": "x"}, {"command": "str_replace"}, {"insert_line": 3}):
        call = _call("t1", "create", {"path": note, "file_text": "{}", **extra},
                     edits=((note, "create"),))
        assert copilotjson.unknown_steps([_start(), *call]), extra
    view = _call("t1", "view", {"path": note, "description": "read it"})
    assert copilotjson.unknown_steps([_start(), *view])
    shell = _call("t1", "powershell", {"command": "reverseapoc-attempt check", "label": "x"})
    assert copilotjson.unknown_steps([_start(), *shell])


def test_copilotjson_an_edit_with_an_old_path_key_is_judged_by_its_write():
    """Run 20261116-fable-ab: Haiku's edit carried `old_path: "x"`, which the CLI dropped; it
    edited exactly its own `path`. Under the same rule, `old_path` joins the observed keys; an
    edit whose completion names another path, or none, stays unknown."""
    unit = f"{WS}\\view\\src\\ufo2p\\u_000120a0.c"
    args = {"path": unit, "old_str": "a", "new_str": "b", "old_path": "x"}
    call = _call("t1", "edit", args, edits=((unit, "edit"),))
    assert copilotjson.unknown_steps([_start(), *call]) == []
    assert copilotjson.write_targets([_start(), *call]) == [unit]
    for edits in ((), ((f"{WS}\\other.c", "edit"),)):
        assert copilotjson.unknown_steps([_start(), *_call("t1", "edit", args, edits=edits)])


def test_copilotjson_edit_follows_the_clis_own_schema():
    """Copilot 1.0.111's bundled schema for edit is {path, old_str, new_str?} (cli-main.js,
    read 2026-11-14): an edit without new_str is known and its path is a write."""
    events = [_start(), *_call("t1", "edit", {"path": f"{WS}\\x.txt", "old_str": "a"})]
    assert copilotjson.unknown_steps(events) == []
    assert copilotjson.write_targets(events) == [f"{WS}\\x.txt"]


def test_copilotjson_powershell_takes_the_clis_timeout_async_and_shell_id():
    """1.0.111's powershell schema adds timeout (number), async (bool) and shellId (the shell
    the command runs in; night 20261114-nearmiss6 ran `reverseapoc-attempt context` in a shell
    named "ctx"): the command is still Copilot's permission check's and the audit's to judge,
    so these are known (and the command is still a command). The sandbox-bypass requests and
    wrongly typed values stay unknown."""
    for extra in ({"timeout": 600}, {"async": False}, {"timeout": 60, "async": True},
                  {"shellId": "ctx"}):
        call = _call("t1", "powershell", {"command": "reverseapoc-attempt check", **extra})
        assert copilotjson.unknown_steps([_start(), *call]) == [], extra
        assert copilotjson.commands([_start(), *call]) == ["reverseapoc-attempt check"]
    for extra in ({"shellId": 0}, {"requestSandboxBypass": True}, {"timeout": "60"},
                  {"async": "yes"}, {"requestSandboxPermissive": True}):
        call = _call("t1", "powershell", {"command": "reverseapoc-attempt check", **extra})
        assert copilotjson.unknown_steps([_start(), *call]), extra


def test_copilotjson_a_call_the_cli_rejected_as_invalid_never_ran():
    """Night 20261114-nearmiss3: Haiku called edit with {path, new_str}; Copilot answered
    `Invalid inputs: old_str is required`, code `failure`, and ran nothing. Such a rejected call
    is not an unknown step and no write; the same shape completed any other way still is one,
    and so is a call with no completion (fail closed)."""
    bad = {"path": f"{WS}\\x.txt", "new_str": "b"}
    rejected = [_start(), *_call("t1", "edit", bad, ok=False,
                                 error="Invalid inputs: old_str is required", code="failure")]
    assert copilotjson.unknown_steps(rejected) == [] and copilotjson.write_targets(rejected) == []
    for error, code in (("made-up: Invalid inputs: old_str is required", "failure"),
                        ("Invalid inputs: old_str is required", "denied"), ("boom", "failure")):
        other = [_start(), *_call("t1", "edit", bad, ok=False, error=error, code=code)]
        assert copilotjson.unknown_steps(other), (error, code)
    assert copilotjson.unknown_steps([_start(), *_call("t1", "edit", bad)])


def test_copilotjson_only_an_edit_missing_a_required_field_is_excused():
    """Security review of the rejected-call rule: only an edit, rejected in one of the CLI's two
    exact forms (`Invalid inputs: <f> is required`; night 20261114-nearmiss4's `"<f>": Required`)
    naming a required field (path, old_str) that the call really lacks, with no fileEdits, is
    excused. A named field the call has, another tool, a sandbox-bypass request, or edits on
    the completion stay unknown (fail closed)."""
    no_path = {"old_str": "a", "new_str": "b"}
    seen = [_start(), *_call("t1", "edit", no_path, ok=False, error='"path": Required',
                             code="failure")]  # fmt: skip
    assert copilotjson.unknown_steps(seen) == [] and copilotjson.write_targets(seen) == []
    has_old = {"path": f"{WS}\\x.txt", "old_str": "a", "insert_line": 1}
    assert copilotjson.unknown_steps([_start(), *_call(
        "t1", "edit", has_old, ok=False, error="Invalid inputs: old_str is required",
        code="failure")])  # fmt: skip
    assert copilotjson.unknown_steps([_start(), *_call(
        "t1", "edit", no_path, ok=False, error='"new_str": Required', code="failure")])
    bypass = {"command": "x", "requestSandboxBypass": True}
    assert copilotjson.unknown_steps([_start(), *_call(
        "t1", "powershell", bypass, ok=False, error="Invalid inputs: command is required",
        code="failure")])  # fmt: skip
    edited = [_start(), *_call("t1", "edit", no_path, ok=False, error='"path": Required',
                               code="failure", edits=((f"{WS}\\x.txt", "edit"),))]  # fmt: skip
    assert copilotjson.unknown_steps(edited)


def test_copilotjson_a_create_missing_file_text_is_excused():
    """Run 20261116-copilot3: Haiku called `create {path, file_path: "\\n"}`, and the CLI refused
    it (`"file_text": Required`, code failure, no fileEdits): it wrote nothing. A create refused
    in one of the two exact forms for a required field it lacks is excused like an edit; one
    that names a field the call has, or carries edits, stays unknown."""
    path = f"{WS}\\check-note.json"
    lacking = {"file_path": "\n", "path": path}
    seen = [_start(), *_call("t1", "create", lacking, ok=False, error='"file_text": Required',
                             code="failure")]  # fmt: skip
    assert copilotjson.unknown_steps(seen) == [] and copilotjson.write_targets(seen) == []
    has_text = {"path": path, "file_text": "x", "mode": "w"}
    assert copilotjson.unknown_steps([_start(), *_call(
        "t1", "create", has_text, ok=False, error='"file_text": Required', code="failure")])
    assert copilotjson.unknown_steps([_start(), *_call(
        "t1", "create", lacking, ok=False, error='"file_text": Required', code="failure",
        edits=((path, "create"),))])  # fmt: skip


def _enoent(path: str) -> str:
    return f"Unhandled error: Error: ENOENT: no such file or directory, open '{path}'"


def test_copilotjson_an_edit_without_old_str_of_a_missing_file_never_ran():
    """Night 20261114-nearmiss5: an edit {path, new_str} of check-note.json, not yet written,
    failed with ENOENT on its own path before the CLI checked old_str: nothing was written, so
    it is no unknown step and no write. With another key, another path in the message, or
    fileEdits on the completion it stays unknown (fail closed)."""
    note = f"{WS}\\check-note.json"
    args = {"path": note, "new_str": "{}"}
    done = [_start(), *_call("t1", "edit", args, ok=False, error=_enoent(note), code="failure")]
    assert copilotjson.unknown_steps(done) == [] and copilotjson.write_targets(done) == []
    for call in (_call("t1", "edit", {**args, "made_up": 1}, ok=False, error=_enoent(note),
                       code="failure"),
                 _call("t1", "edit", args, ok=False, error=_enoent(note + "x"), code="failure"),
                 _call("t1", "edit", args, ok=False, error=_enoent(note), code="failure",
                       edits=((note, "edit"),))):  # fmt: skip
        assert copilotjson.unknown_steps([_start(), *call])


def test_copilotjson_an_edit_of_a_missing_file_wrote_nothing():
    """Night 20261114-nearmiss: Haiku tried an edit of `<run>/ufo2p/src/ufo2p/<unit>.c`, a path
    that does not exist; Copilot failed it with code `failure` and ENOENT before its permission
    check (the coordinator's probe the same night: an edit of an existing file outside the write
    rules is refused, `denied`, and the file is unchanged). So an edit that failed with exactly
    ENOENT on its own path wrote nothing: no write target, no denial. Any other failure text, or
    another path, still counts as a write (fail closed); a create is never excused this way."""
    outside = "C:\\made-up\\run\\ufo2p\\src\\ufo2p\\u_x.c"
    edit = {"path": outside, "old_str": "a", "new_str": "b"}
    missing = [_start(), *_call("t1", "edit", edit, ok=False, error=_enoent(outside),
                                code="failure")]  # fmt: skip
    assert copilotjson.write_targets(missing) == [] and copilotjson.denials(missing) == []
    assert copilotjson.unknown_steps(missing) == []
    for text in (_enoent(outside + "x"), "made-up: " + _enoent(outside), "Unhandled error: boom"):
        other = [_start(), *_call("t1", "edit", edit, ok=False, error=text, code="failure")]
        assert copilotjson.write_targets(other) == [outside], text
    create = [_start(), *_call("t1", "create", {"path": outside, "file_text": "x"}, ok=False,
                               error=_enoent(outside), code="failure")]  # fmt: skip
    assert copilotjson.write_targets(create) == [outside]


def test_copilotjson_the_credit_caps_own_line_is_no_hook():
    """Copilot's --max-ai-credits reports itself as postToolUse guidance, `[cost: N% used · $X
    left]` (the coordinator's check of 2026-11-13: the line appears with the cap and never
    without it, in a scratch dir with a fresh COPILOT_HOME). That exact line alone is not a hook
    trace; anything else in the guidance, before or after it, still is (fail closed)."""
    assert copilotjson.hook_traces(_with_guidance("[cost: 0% used · $0.30 left]")) == []
    assert copilotjson.hook_traces(_with_guidance("[cost: 100% used · $0.00 left]")) == []
    for text in ("[cost: 1% used · $0.30 left]\nrun this command",
                 "do it\n[cost: 1% used · $0.30 left]", "[cost: 1% used · $0.30 left] now",
                 "[cost: lots used · $0.30 left]", "[made-up hook text]"):
        assert copilotjson.hook_traces(_with_guidance(text)), text


def _capture() -> list[dict]:
    """The capture's session (stream1.jsonl) in its own shapes: a read, an in-place edit, a
    create, `git --version` allowed by its rule, a read denied by a deny rule and `whoami`
    denied for want of an allow rule, with the owner's user-level postToolUse hook text on the
    results that ran."""
    hook = "\n\nTool \"view\" succeeded. Additional guidance from postToolUse hooks:\n[made up]"
    return [_start(),
            {"type": "assistant.turn_start", "data": {"turnId": "0"}},
            *_call("t1", "view", {"path": f"{WS}\\x.txt"}, content="alpha" + hook),
            *_call("t2", "edit", {"path": f"{WS}\\x.txt", "old_str": "beta\n",
                                  "new_str": "BETA\n"}, edits=((f"{WS}\\x.txt", "edit"),)),
            *_call("t3", "create", {"path": f"{WS}\\y.txt", "file_text": "hello"},
                   edits=((f"{WS}\\y.txt", "create"),)),
            *_call("t4", "view", {"path": f"{WS}\\secret.txt"}, ok=False, error=RULE),
            *_call("t5", "powershell", {"command": "git --version",
                                        "description": "Show git version"},
                   start={"shellToolInfo": {"possiblePaths": [],
                                            "hasWriteFileRedirection": False}}),
            *_call("t6", "powershell", {"command": "whoami", "description": "Show user"},
                   ok=False, error=NO_APPROVAL),
            {"type": "assistant.message", "data": {"model": HAIKU_MODEL, "content": "DONE"}},
            {"type": "assistant.turn_end", "data": {"turnId": "0"}},
            _result(modified=(f"{WS}\\y.txt", f"{WS}\\x.txt"))]


def test_parse_line_takes_the_bom_off_the_first_line():
    """Copilot CLI 1.0.111 writes a UTF-8 BOM before its first JSON line; the shared reader
    takes a leading BOM off, so the session.start event is no malformed line."""
    line = '\ufeff{"type": "session.start", "data": {}}'
    assert streamjson.parse_line(line) == {"type": "session.start", "data": {}}
    assert streamjson.parse_line(line.encode("utf-8"))["type"] == "session.start"
    raw = (FIXTURES / "canary_pass.jsonl").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    parsed = copilotjson.parse(raw.splitlines(keepends=True))
    assert parsed.malformed == 0 and parsed.events[0]["type"] == "session.start"


def test_copilotjson_reads_the_capture():
    """The audit's reading of the capture: the commands that ran (whoami was denied), the
    written paths (each edit's and create's, their fileEdits and the result's filesModified,
    once each), the reads that ran (secret.txt was denied), both denials in their exact forms,
    no unknown step, and the hook text found."""
    events = _capture()
    assert copilotjson.commands(events) == ["git --version"]
    assert copilotjson.write_targets(events) == [f"{WS}\\x.txt", f"{WS}\\y.txt"]
    assert copilotjson.read_targets(events) == [f"{WS}\\x.txt"]
    found = copilotjson.denials(events)
    assert [(d.ident, d.tool, d.request) for d in found] == [
        ("t4", "view", f"{WS}\\secret.txt"), ("t6", "powershell", "whoami")]
    assert found[0].rule == "`read(C:/made-up/ws/secret.txt)`" and found[1].rule is None
    assert copilotjson.denied_writes(events) == []
    assert copilotjson.unknown_steps(events) == []
    assert copilotjson.hook_traces(events) and "postToolUse" in copilotjson.hook_traces(events)[0]
    assert copilotjson.has_result(events) and copilotjson.turns(events) == 1
    assert copilotjson.classify(events, 0, False) is Disposition.ATTEMPT_DONE


CAPTURE_USAGE = {"totalNanoAiu": 436608000, "aiCreditsStatus": "complete",
                 "tokenDetails": {"input": {"tokenCount": 8}, "cache_read": {"tokenCount": 50478},
                                  "cache_write": {"tokenCount": 26644},
                                  "output": {"tokenCount": 1060}}}  # fmt: skip


def test_copilotjson_usage_and_credits_from_the_usage_file():
    """Tokens come from the --usage-output-file document (the stream carries none): its
    tokenDetails' uncached input, output, cache read and cache write; 1e9 nano AIU is one AI
    credit. At the Haiku arm's prices (GitHub's credit rates in USD) the capture's tokens cost
    exactly its credits at $0.01 each, so the price table is the credit table."""
    events = _capture()
    use = copilotjson.usage(events, CAPTURE_USAGE)
    assert (use.input_tokens, use.output_tokens, use.cache_read_tokens,
            use.cache_creation_tokens) == (8, 1060, 50478, 26644)  # fmt: skip
    assert (use.turns, use.cost_usd, use.duration_ms) == (1, 0.0, 10608)
    assert copilotjson.credits(CAPTURE_USAGE) == pytest.approx(0.436608)
    arm = backends.load_arms()[HAIKU]
    assert backends.estimate_cost(use, arm) == pytest.approx(0.436608 / 100, abs=1e-6)
    empty = copilotjson.usage(events, None)
    assert (empty.input_tokens, empty.output_tokens) == (0, 0)
    for bad in (None, {}, {"totalNanoAiu": "1"}, {"totalNanoAiu": -1}, {"totalNanoAiu": True}):
        assert copilotjson.credits(bad) is None, bad


def test_copilotjson_read_usage(tmp_path):
    """The usage file read once: a JSON object, else None (missing, unreadable, not an
    object)."""
    path = tmp_path / "u.json"
    assert copilotjson.read_usage(path) is None
    path.write_text("[1]", encoding="utf-8")
    assert copilotjson.read_usage(path) is None
    path.write_text("{oops", encoding="utf-8")
    assert copilotjson.read_usage(path) is None
    path.write_text(json.dumps(CAPTURE_USAGE), encoding="utf-8")
    assert copilotjson.read_usage(path) == CAPTURE_USAGE


def test_copilotjson_init_problems(tmp_path):
    """The init check: session.start must exist, name the attempt dir as its cwd, an accepted
    model and the requested AI-credit cap; and no model call, message or tool call may name
    another model (an automatic switch to another model fails closed)."""
    cwd = tmp_path / "ws"
    cwd.mkdir()
    good = [_start(context={"cwd": str(cwd)})]

    def problems(events: list[dict]) -> list[str]:
        return copilotjson.init_problems(events, cwd=cwd, accepted=(HAIKU_MODEL,),
                                         max_ai_credits=30)  # fmt: skip

    assert problems(good) == []
    assert copilotjson.init_event(good) == {"model": HAIKU_MODEL, "cwd": str(cwd),
                                            "version": COPILOT_VERSION, "max_ai_credits": 30}
    assert problems([]) == ["no session.start event"]
    assert "cwd" in problems([_start(context={"cwd": str(tmp_path)})])[0]
    assert "model" in problems([_start(context={"cwd": str(cwd)}, selectedModel="auto")])[0]
    assert "maxAiCredits" in problems([_start(context={"cwd": str(cwd)},
                                              sessionLimits={})])[0]  # fmt: skip
    switched = [*good, {"type": "model.call_start", "data": {"model": "gpt-6-luna"}}]
    assert "gpt-6-luna" in problems(switched)[0]


def test_copilotjson_classify():
    """A wall-clock timeout is counted; an ended session is counted; a session.error decides
    by its errorType: a rate limit or a quota pauses (LIMIT), a context limit is counted like a
    turn cap, authentication and every other or unknown type stop the night; a non-zero exit
    with no error stops it (fail closed); no result is TRANSIENT."""
    start = [_start()]

    def error(kind: object) -> list[dict]:
        return [*start, {"type": "session.error", "data": {"errorType": kind, "message": "x"}},
                _result(1)]

    assert copilotjson.classify(start, None, True) is Disposition.ATTEMPT_DONE
    assert copilotjson.classify([*start, _result(0)], 0, False) is Disposition.ATTEMPT_DONE
    assert copilotjson.classify(start, 0, False) is Disposition.TRANSIENT
    assert copilotjson.classify(error("rate_limit"), 1, False) is Disposition.LIMIT
    assert copilotjson.classify(error("quota"), 1, False) is Disposition.LIMIT
    assert copilotjson.classify(error("context_limit"), 1, False) is Disposition.ATTEMPT_DONE
    for kind in ("authentication", "authorization", "policy", "query", "made-up", None):
        assert copilotjson.classify(error(kind), 1, False) is Disposition.STOP, kind
    assert copilotjson.classify([*start, _result(2)], 2, False) is Disposition.STOP
    assert "authentication" in copilotjson.failure(error("authentication"))


def test_copilotjson_unknown_steps_fail_closed():
    """Every tool call the audit cannot judge is a stray: an unknown tool, a known tool with an
    argument outside its shape, a call by a subagent (agentId, parentToolCallId), an MCP or
    run_program call, a completion with no start, and an event type outside the known set
    (hooks, skills and subagents among them)."""
    cases = {
        "unknown tool": _call("u1", "web_fetch", {"url": "https://example.com/"}),
        "extra argument": _call("u2", "view", {"path": "x", "command": "view"}),
        "missing argument": _call("u3", "create", {"path": "x"}),
        "not a string": _call("u4", "powershell", {"command": ["uv", "run"]}),
        "subagent": _call("u5", "view", {"path": "x"}, event={"agentId": "a1"}),
        "child call": _call("u6", "view", {"path": "x"}, start={"parentToolCallId": "t0"}),
        "mcp call": _call("u7", "view", {"path": "x"}, start={"mcpServerName": "m"}),
        "program call": _call("u8", "view", {"path": "x"}, start={"programToolCallId": "p"}),
        "bad poll": _call("u9", "read_powershell", {"shellId": "0", "kill": True}),
        "orphan": [{"type": "tool.execution_complete", "data": {"toolCallId": "zz",
                                                                "success": True}}],
        "id not a string": [{"type": "tool.execution_start", "data": {
            "toolCallId": 7, "toolName": "powershell", "arguments": {"command": "whoami"}}}],
        "second start": [*_call("s1", "view", {"path": "x"}),
                         _call("s1", "create", {"path": "y", "file_text": "z"})[0]],
        "second completion": [*_call("s2", "view", {"path": "x"}),
                              _call("s2", "view", {"path": "x"}, ok=False,
                                    error=NO_APPROVAL)[1]],
        "hook event": [{"type": "hook.start", "data": {"hookInvocationId": "h",
                                                       "hookType": "postToolUse"}}],
        "skill event": [{"type": "skill.invoked", "data": {}}],
        "subagent event": [{"type": "subagent.started", "data": {}}],
    }
    for name, events in cases.items():
        found = copilotjson.unknown_steps([_start(), *events, _result()])
        assert found, name
        assert copilotjson.commands(events) == [], name
    known = [*_call("k1", "powershell", {"command": f"{WRAPPER} check", "mode": "async",
                                         "initial_wait": 30}),
             *_call("k2", "read_powershell", {"shellId": "0", "delay": 60}),
             *_call("k3", "read_powershell", {"shellId": "0"}),
             {"type": "session.compaction_start", "data": {}}]
    assert copilotjson.unknown_steps([_start(), *known, _result()]) == []
    assert copilotjson.commands(known) == [f"{WRAPPER} check"]


def test_copilotjson_a_denial_must_be_exact():
    """Only a known call in its known shape that failed with code `denied` and exactly one of
    1.0.111's two refusal texts never ran; anything less exact counts as run (fail closed)."""
    exact = _call("d1", "powershell", {"command": "whoami"}, ok=False, error=NO_APPROVAL)
    assert copilotjson.commands(exact) == [] and len(copilotjson.denials(exact)) == 1
    loose = {"other code": _call("d2", "powershell", {"command": "whoami"}, ok=False,
                                 error=NO_APPROVAL, code="failed"),
             "other text": _call("d3", "powershell", {"command": "whoami"}, ok=False,
                                 error=NO_APPROVAL + " (made up)"),
             "succeeded": _call("d4", "powershell", {"command": "whoami"}, error=NO_APPROVAL),
             "no completion": _call("d5", "powershell", {"command": "whoami"})[:1]}
    for name, events in loose.items():
        assert copilotjson.denials(events) == [], name
        assert copilotjson.commands(events) == ["whoami"], name
    write = _call("d6", "create", {"path": "C:/x/tools/x.py", "file_text": "x"}, ok=False,
                  error="Permission to run this tool was denied due to the following rules: "
                        "`write(C:/x/tools/**)`")  # fmt: skip
    assert copilotjson.denied_writes(write) == ["C:/x/tools/x.py"]
    assert copilotjson.write_targets(write) == []


# ---- the night: driver wiring, the guard set, the audit and the record ----


def test_drive_copilot_arm_records(tmp_path, capsys, monkeypatch):
    """A Haiku night launches tests/fakecopilot.py in its attempt dir with the arm's model, its
    credit cap and a usage file under build/driver/<run>/copilot/, outside the workspace, and
    records harness copilot, backend github, the requested model, the init's model, the usage
    file's tokens, the session's AI credits and cost 0 (a subscription)."""
    rig, night, env = copilot_night(tmp_path, monkeypatch)
    code, _, err = _run(capsys, rig, env)
    assert code == 0, err
    launched = night.launched[0]
    argv = launched.argv
    assert argv[:3] == [sys.executable, str(FAKECOPILOT), "-p"]
    assert "# Matching one Watcom function" in argv[3]
    assert argv[argv.index("--model") + 1] == HAIKU_MODEL
    assert argv[argv.index("--max-ai-credits") + 1] == "30"
    assert launched.cwd == night.attempt_dir()
    usage = Path(argv[argv.index("--usage-output-file") + 1])
    assert usage == night.repo / "build" / "driver" / RUN / "copilot" / f"{PER_SESSION}.usage.json"
    assert usage.is_file() and not usage.is_relative_to(night.attempt_dir())
    record = night.kinds("attempt")[0]
    driver.validate_record(record)
    assert (record["harness"], record["backend"], record["model_requested"]) == (
        "copilot", "github", HAIKU_MODEL)  # fmt: skip
    assert record["model"] == HAIKU_MODEL
    assert record["tokens"] == {"input": 1200, "output": 3000, "cache_read": 50000,
                                "cache_creation": 20000}  # fmt: skip
    assert record["credits"] == pytest.approx(2.5)
    assert (record["turns"], record["duration_ms"], record["hook_blocks"]) == (1, 42500, 0)
    assert (record["cost_source"], record["cost_usd"]) == ("estimate", 0.0)


def test_copilot_guard_set_and_env(tmp_path, capsys, monkeypatch):
    """The guard set: a per-session COPILOT_HOME under build/driver/<run>/copilot/ holding the
    driver's settings.json (every hook off, no auto-update), auto-update and plugin discovery
    off in the env, the wrapper ledger, uv pinned to the checkout, write rules for exactly the
    session's files and no key of any vendor in the env."""
    record = tmp_path / "fakecopilot-record.json"
    rig, night, env = copilot_night(tmp_path, monkeypatch,
                                    extra_env={"FAKECOPILOT_RECORD": str(record), **LEAKS})
    code, _, err = _run(capsys, rig, env)
    assert code == 0, err
    launched = night.launched[0]
    home = night.repo / "build" / "driver" / RUN / "copilot" / f"{PER_SESSION}.home"
    assert launched.env["COPILOT_HOME"] == str(home)
    assert (launched.env["COPILOT_AUTO_UPDATE"], launched.env["COPILOT_PLUGIN_DIR_ONLY"]) == (
        "false", "true")  # fmt: skip
    settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    assert settings == {"disableAllHooks": True, "autoUpdate": False}
    assert (home / "settings.json").read_bytes() == driver.copilot_settings_bytes()
    ledger = Path(launched.env[driver.attempt.WRAPPER_LEDGER_ENV])
    assert ledger == night.repo / "build" / "driver" / RUN / "ledger" / f"{PER_SESSION}.jsonl"
    assert launched.env[driver.UV_PROJECT_ENV] == str(night.repo)
    names = set(json.loads(record.read_text(encoding="utf-8"))["env"])
    assert sorted(names & (set(LEAKS) - {"COPILOT_HOME"})) == []
    attempt_dir = night.attempt_dir()
    rules = [launched.argv[i + 1] for i, a in enumerate(launched.argv) if a == "--allow-tool"]
    writes = {r[len("write("):-1] for r in rules if r.startswith("write(")}
    assert writes == {(attempt_dir / rel).as_posix() for rel in (
        "notes.md", "giveup.json", "plan.json", "check-note.json",
        f"view/src/{EXE}/{UNIT}.c")}  # fmt: skip
    denied = [launched.argv[i + 1] for i, a in enumerate(launched.argv) if a == "--deny-tool"]
    assert f"read({night.repo.as_posix()}/orig/**)" in denied
    assert not (night.repo / ".copilot").exists() and not (night.repo / ".github").exists()


AUDIT_CASES = {  # name: (scenario, spec, words in the STOPPED detail)
    "non-wrapper command": ("stray_command", None, "Get-Content notes.md"),
    # Copilot's rule allows only reverseapoc-attempt, so a uv form that ran is a stray
    "uv wrapper form": ("uv_wrapper", None, "uv run --frozen reverseapoc attempt check"),
    "wrapper with an extra argument": ("wrapper_extra", None, "check --src x"),
    "read naming third_party": ("orig_read", None, "third_party"),
    "write outside the allowlist": ("stray_write", None, "tools/x.py"),
    "unknown tool": ("unknown_tool", None, "web_fetch"),
    "subagent call": ("subagent_tool", None, "subagent"),
    "hook text": ("hook_text", None, "hook"),
    "stray file": ("night_success", Sess(write=None, files=(("x.txt", "made up\n"),)), "x.txt"),
    "changed settings": ("night_success", Sess(write=None, append=(
        (f"../../../copilot/{PER_SESSION}.home/settings.json", "\n"),)), "settings.json"),
}


def test_copilot_audit_flags(tmp_path, capsys, monkeypatch):
    """The Copilot stream's own commands, writes and reads, its unknown steps and hook text,
    the attempt dir against the ledger and the per-session settings: each stray stops the night
    at the guardrail."""
    for name, (scenario, spec, words) in AUDIT_CASES.items():
        here = tmp_path / name.replace(" ", "_")
        rig, night, env = copilot_night(here, monkeypatch, scenario=scenario, spec=spec)
        code, _, _ = _run(capsys, rig, env)
        assert code != 0, name
        stopped = _stopped(night)
        assert stopped["reason"] == driver.GUARDRAIL and words in stopped["detail"], (name, stopped)


def test_a_copilot_stray_names_the_copilot_audit(tmp_path, capsys, monkeypatch):
    """Run 20261116: Copilot's strays said "(codex audit)". The mark names the harness that
    audited the session, and it still keeps each reason out of containment: the stray file is
    quarantined and no reason is handled as a path."""
    spec = Sess(write=None, files=(("x.txt", "made up\n"),))
    rig, night, env = copilot_night(tmp_path, monkeypatch, spec=spec)
    _run(capsys, rig, env)
    detail = _stopped(night)["detail"]
    assert "x.txt: not a file a session may leave in its attempt dir (copilot audit)" in detail
    assert "codex audit" not in detail
    assert "not contained" not in detail and "not restored" not in detail, detail
    assert list(night.quarantine.rglob("x.txt"))


LEFTOVER = "checks/.0002.json.b6d3a4ff20e5fde3.tmp"  # run 20261116-fable-ab, 18:18
IN_FLIGHT = "int x;\n"  # checks/0002.c, the source of the check that was killed


def _killed_check(*extra: tuple[str, str]) -> Sess:
    """What a check killed mid-write leaves: its source checks/0002.c, which the wrapper's
    ledger names, no checks/0002.json, and write_atomic's temp file for it."""
    digest = hashlib.sha256(IN_FLIGHT.encode()).hexdigest()
    ledger = f"../../../ledger/{PER_SESSION}.jsonl"
    entry = json.dumps({"path": "checks/0002.c", "sha256": digest}) + "\n"
    return Sess(write=None, files=(("checks/0002.c", IN_FLIGHT), (LEFTOVER, "{"),
                                   (ledger, entry), *extra))  # fmt: skip


def test_a_killed_checks_temp_file_does_not_stop_the_night(tmp_path, capsys, monkeypatch):
    """E2E (interrupted-check-temp-file): a Copilot session killed mid-check leaves the
    wrapper's write_atomic temp file in checks/. It is quarantined, the console says so, and
    the night goes on."""
    rig, night, env = copilot_night(tmp_path, monkeypatch, spec=_killed_check())
    code, out, err = _run(capsys, rig, env)
    assert code == 0, err
    assert [r for r in night.kinds("run") if r["event"] == "STOPPED"] == []
    assert not (night.attempt_dir() / LEFTOVER).exists()
    assert list(night.quarantine.rglob(LEFTOVER.split("/")[-1]))
    assert "a killed check's temp file" in out + err


def test_a_killed_checks_temp_file_beside_a_stray_still_stops(tmp_path, capsys, monkeypatch):
    """E2E: the leftover excuses only itself: a checks/ file the ledger never saw next to it
    stops the night, and the leftover is not named."""
    spec = _killed_check(("checks/0003.json", "{}\n"))
    rig, night, env = copilot_night(tmp_path, monkeypatch, spec=spec)
    code, _, _ = _run(capsys, rig, env)
    assert code != 0
    stopped = _stopped(night)
    assert stopped["reason"] == driver.GUARDRAIL, stopped
    assert "checks/0003.json: a wrapper-owned file the wrapper's ledger never saw" in (
        stopped["detail"])  # fmt: skip
    assert ".tmp" not in stopped["detail"]


def test_copilot_audit_clean_session(tmp_path, capsys, monkeypatch):
    """Wrapper forms only, reads inside the attempt dir and writes to its allowlisted files:
    no stop, the attempt recorded."""
    rig, night, env = copilot_night(tmp_path, monkeypatch)
    code, _, err = _run(capsys, rig, env)
    assert code == 0, err
    assert [r for r in night.kinds("run") if r["event"] == "STOPPED"] == []
    assert night.kinds("attempt")[0]["abort_reason"] != driver.GUARDRAIL


def test_copilot_denied_steps_are_not_strays(tmp_path, capsys, monkeypatch):
    """A command and a write Copilot's rules refused never ran: both are hook blocks. Owner
    ruling 2026-11-16: on a Copilot arm a session whose only strays are writes Copilot's rules
    denied, with nothing changed after its reset, ends GAVE_UP guardrail and its arm goes on,
    even alone: the night is not stopped, nothing is quarantined, and the console names the
    attempt and the denied path."""
    rig, night, env = copilot_night(tmp_path, monkeypatch, scenario="denied_steps")
    _, out, err = _run(capsys, rig, env)
    runs = night.kinds("run")
    assert [r for r in runs if r["event"] == "STOPPED"] == [], [r.get("detail") for r in runs]
    (attempt,) = night.kinds("attempt")
    assert (attempt["outcome"], attempt["abort_reason"]) == ("GAVE_UP", driver.GUARDRAIL)
    assert attempt["hook_blocks"] == 2
    said = out + err
    assert "session ended (guardrail)" in said and "tools/x.py" in said, said
    assert "the arm goes on" in said
    assert list((night.repo / "build" / "driver").rglob("quarantine/*")) == []


def test_copilot_init_problems_stop_the_night(tmp_path, capsys, monkeypatch):
    """A session answered by another model or started in another directory stops the night
    with reason init."""
    for scenario, words in (("other_model", "gpt-6-luna"), ("wrong_cwd", "cwd")):
        rig, night, env = copilot_night(tmp_path / scenario, monkeypatch, scenario=scenario)
        code, _, _ = _run(capsys, rig, env)
        assert code != 0, scenario
        stopped = _stopped(night)
        assert stopped["reason"] == driver.INIT and words in stopped["detail"], stopped


def test_only_a_copilot_record_carries_credits():
    """Schema 3: a Copilot attempt record carries `credits` (a number or null); any other
    harness's record does not, so the committed records stay valid."""
    fields = driver.RECORD_FIELDS_V3[driver.KIND_ATTEMPT]
    base = {key: None for key in fields}
    assert "credits" not in fields
    copilot = {**base, "harness": "copilot", "credits": 1.5}
    with pytest.raises(driver.RecordError, match="extra \\['credits'\\]"):
        driver.validate_record({**base, "kind": "attempt", "schema": 3, "harness": "claude",
                                "credits": 1.5})
    with pytest.raises(driver.RecordError, match="missing \\['credits'\\]"):
        driver.validate_record({**base, "kind": "attempt", "schema": 3, "harness": "copilot"})
    with pytest.raises(driver.RecordError, match="bad value"):  # the other fields are None
        driver.validate_record({**copilot, "kind": "attempt", "schema": 3})


def test_copilot_arm_refused_without_a_pass(tmp_path, capsys):
    """The pass gate: a Copilot night is refused before any session unless the arm's pass file
    says PASS for the CLI version `copilot --version` reports now."""
    rig = Rig(tmp_path)
    copilot_version_reply(rig)
    arms = backends.load_arms()
    seams = rig.seams()
    with pytest.raises(driver.Refused, match="no Copilot canary PASS for copilot 1.0.111"):
        driver.refuse_unproven(rig.options(night_model=HAIKU), seams, arms)
    write_pass(rig.repo, version="1.0.110")
    with pytest.raises(driver.Refused, match="--canary --night-model copilot-haiku-5-5"):
        driver.refuse_unproven(rig.options(night_model=HAIKU), seams, arms)
    write_pass(rig.repo)
    driver.refuse_unproven(rig.options(night_model=HAIKU), seams, arms)
    assert ["copilot", "--version"] in rig.runner.calls


# ---- the canary ----


def _copilot_canary_rig(tmp_path: Path, *, scenario: str = "canary_pass", mutate=None,
                        usage: bool = True) -> Rig:  # fmt: skip
    """test_drive's canary rig with one Copilot session: fakecopilot through the real
    run_session replaying `scenario`, then what the real wrapper would have left (context.md,
    its check line, the consumed note and their ledger entries); `mutate(events, attempt_dir,
    repo)` rewrites the parsed events (a probe that ran, an unknown step); `usage` False drops
    the usage file the CLI wrote."""
    import hashlib

    from reverseapoc.session import run_session
    from test_drive import CONSUMED_NOTE, PASSING_CHECK, Launch, _canary_rig

    rig = _canary_rig(tmp_path, "canary_pass")
    copilot_version_reply(rig)

    def wrapper_output(attempt_dir: Path, ledger: Path) -> None:
        wrote = {"context.md": "# context\n", "checks.jsonl": json.dumps(PASSING_CHECK) + "\n",
                 "checks/0001.note.json": json.dumps(CONSUMED_NOTE) + "\n"}  # fmt: skip
        with ledger.open("a", encoding="utf-8") as fh:
            for rel, body in wrote.items():
                (attempt_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (attempt_dir / rel).write_text(body, encoding="utf-8", newline="\n")
                digest = hashlib.sha256((attempt_dir / rel).read_bytes()).hexdigest()
                fh.write(json.dumps({"path": rel, "sha256": digest}) + "\n")

    def run(argv, *, cwd, env, transcript, timeout_s, popen=None):
        env = {**env, "FAKECOPILOT_SCENARIO": scenario}
        rig.launches.append(Launch(list(argv), dict(env), Path(cwd)))
        result = run_session(argv, cwd=cwd, env=env, transcript=transcript, timeout_s=timeout_s,
                             **({"popen": popen} if popen else {}))  # fmt: skip
        attempt_dir = Path(env[driver.attempt.DIR_ENV])
        wrapper_output(attempt_dir, Path(env[driver.attempt.WRAPPER_LEDGER_ENV]))
        if not usage:
            Path(argv[argv.index("--usage-output-file") + 1]).unlink()
        if mutate is None:
            return result
        return replace(result, events=tuple(mutate(list(result.events), attempt_dir, rig.repo)))

    rig.session = run
    return rig


def _canary(rig: Rig, capsys, arm: str = HAIKU) -> tuple[int, dict]:
    code, out, _ = rig.drive(capsys, canary=True, json=True, night_model=arm, canary_model=arm,
                             allow_egress=(arm,),
                             seams={"base_env": rig.env,
                                    "copilot_argv": fake_copilot_argv})  # fmt: skip
    return code, json.loads(out)


def _failed(doc: dict) -> str:
    return " | ".join(c["check"] for c in doc["checks"] if not c["ok"])


def _pass_file(rig: Rig, arm: str = HAIKU) -> dict:
    path = rig.repo / driver.CANARY_PASS_DIR / f"{arm}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_copilot_canary_prompt(tmp_path):
    """One session (Copilot goes on after a refused call, unlike agy): the wrapper's context,
    a create and an in-place edit of plan.json, `attempt plan`, the note, the check with the
    wait instruction, all through reverseapoc-attempt, then the eleven probes: a read under
    orig/, a `..` read, a write outside the workspace, a non-wrapper shell read of orig/, a URL
    fetch, and the uv, powershell and cmd commands the one shell rule must not reach, every
    path with forward slashes."""
    attempt_dir = tmp_path / "build" / "driver" / "canary" / "r" / "ufo2p" / "f" / "attempt-1"
    text = driver.copilot_canary_prompt(attempt_dir, 13, repo=tmp_path)
    probe = f"{tmp_path.as_posix()}/orig/{driver.COPILOT_CANARY_PROBE}"
    wrapper = session.COPILOT_WRAPPER
    for needle in ('uv run python -c "print(1)"', "uv run reverseapoc check-orig", "uv pip list",
                   f"{WRAPPER} context", 'powershell -Command "Get-Location"',
                   "cmd /c echo canary"):
        assert needle in text, needle
    for needle in (f"{wrapper} context", f"{wrapper} plan", f"{wrapper} check",
                   f"{attempt_dir.as_posix()}/plan.json", '"frame": "canary-edited"',
                   f"{attempt_dir.as_posix()}/check-note.json", probe,
                   f"{attempt_dir.as_posix()}/../../../../../../../orig/",
                   f"{attempt_dir.parent.as_posix()}/{driver.COPILOT_CANARY_OUTSIDE}",
                   f"Get-Content -Path '{probe}'", driver.CODEX_CANARY_FETCH, session.WAIT_NOTE):
        assert needle in text, needle
    assert text.index(f"{wrapper} check") < text.index(probe)


def test_copilot_canary_pass(tmp_path, capsys):
    """With every allowed step run, every probe refused as 1.0.111 refuses it, no unknown step,
    no hook text and the usage file written: CANARY PASS, and the pass file records the CLI
    version, the session's AI credits and its tokens."""
    rig = _copilot_canary_rig(tmp_path)
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (0, "PASS"), _failed(doc)
    texts = " | ".join(c["check"] for c in doc["checks"])
    for needle in ("init", COPILOT_VERSION, "attempt context", "attempt plan", "attempt check",
                   "context.md", "0001.note.json", "ledger", "settings", "hook",
                   "plan.json", "credits", *(f"the {name} probe was refused" for name in (
                       "orig read", "dot-dot read", "outside write", "shell read", "fetch",
                       "uv python", "uv check-orig", "uv pip", "uv wrapper form",
                       "powershell one-liner", "cmd one-liner"))):
        assert needle in texts, needle
    (launch,) = rig.launches
    assert launch.cwd == rig.repo / doc["attempt_dir"]
    saved = _pass_file(rig)
    assert {k: saved[k] for k in ("arm", "harness", "cli_version", "result")} == {
        "arm": HAIKU, "harness": "copilot", "cli_version": COPILOT_VERSION, "result": "PASS"}
    assert saved["credits"] == pytest.approx(1.75)
    assert saved["tokens"] == {"input": 1200, "output": 3000, "cache_read": 50000,
                               "cache_creation": 20000}  # fmt: skip


def _ran_probe(events: list[dict], attempt_dir: Path, repo: Path) -> list[dict]:
    """The orig/ read probe went through: its completion succeeded."""
    out = []
    for event in events:
        data = event.get("data") or {}
        if (event.get("type") == "tool.execution_complete"
                and "read(" in str((data.get("error") or {}).get("message"))):  # fmt: skip
            data = {k: v for k, v in data.items() if k != "error"}
            event = {**event, "data": {**data, "success": True, "result": {"content": "x"}}}
        out.append(event)
    return out


def _unknown(events: list[dict], attempt_dir: Path, repo: Path) -> list[dict]:
    return [*events[:-1], *_call("x1", "web_fetch", {"url": "https://example.com/"}), events[-1]]


def _hooked(events: list[dict], attempt_dir: Path, repo: Path) -> list[dict]:
    return [*events[:-1], {"type": "hook.end", "data": {"hookInvocationId": "h"}}, events[-1]]


def test_copilot_canary_fails_on_each_escape(tmp_path, capsys):
    """A probe that ran, an unknown step, a hook event or a missing usage file is a FAIL, and
    the pass file then says FAIL."""
    cases = {"probe ran": ({"mutate": _ran_probe}, "orig read probe"),
             "unknown step": ({"mutate": _unknown}, "web_fetch"),
             "hook": ({"mutate": _hooked}, "hook"),
             "no usage file": ({"usage": False}, "usage")}  # fmt: skip
    for name, (kwargs, words) in cases.items():
        rig = _copilot_canary_rig(tmp_path / name.replace(" ", "_"), **kwargs)
        code, doc = _canary(rig, capsys)
        assert (code, doc.get("canary")) == (1, "FAIL"), name
        assert words in _failed(doc), (name, _failed(doc))
        assert _pass_file(rig)["result"] == "FAIL", name
