"""The GitHub Copilot CLI harness: Claude Haiku 5.5, Claude Sonnet 5.5 and GPT-6 Luna on the
owner's Copilot Pro AI credits as drive arms (owner ruling 2026-11-13, spike 013).

Owner rule: no test runs the real `copilot`. Every session here is tests/fakecopilot.py
replaying a synthetic fixture under tests/fixtures/copilot/ (shapes from the coordinator's
Copilot CLI 1.0.111 capture, every id made up, every path a fake slot); nothing contacts
GitHub. Every environment is built with made-up values over test_drive's key-free base, so a
key the owner has set can never reach an assertion or a log.
"""

from __future__ import annotations

import json
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
        return real(moved, night.deps(copilot_argv=fake_copilot_argv))

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
        assert (arm.max_workers, arm.max_ai_credits) == (4, 30), name
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


def _enoent(path: str) -> str:
    return f"Unhandled error: Error: ENOENT: no such file or directory, open '{path}'"


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
        "extra argument": _call("u2", "view", {"path": "x", "made_up_key": [1, 2]}),
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


def test_copilot_audit_clean_session(tmp_path, capsys, monkeypatch):
    """Wrapper forms only, reads inside the attempt dir and writes to its allowlisted files:
    no stop, the attempt recorded."""
    rig, night, env = copilot_night(tmp_path, monkeypatch)
    code, _, err = _run(capsys, rig, env)
    assert code == 0, err
    assert [r for r in night.kinds("run") if r["event"] == "STOPPED"] == []
    assert night.kinds("attempt")[0]["abort_reason"] != driver.GUARDRAIL


def test_copilot_denied_steps_are_not_strays(tmp_path, capsys, monkeypatch):
    """A command and a write Copilot's rules refused never ran: both are hook blocks; the
    refused write is a denied write, so the one-arm night stops at the guardrail naming it and
    quarantining nothing."""
    rig, night, env = copilot_night(tmp_path, monkeypatch, scenario="denied_steps")
    code, _, _ = _run(capsys, rig, env)
    assert code != 0
    stopped = _stopped(night)
    assert stopped["reason"] == driver.GUARDRAIL and "quarantined: none" in stopped["detail"]
    assert "tools/x.py (transcript)" in stopped["detail"], stopped
    assert night.kinds("attempt")[0]["hook_blocks"] == 2


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
