"""The Codex CLI harness: GPT-6 Luna and GPT-6.1 Sol as drive arms (07.2-13; D-12, D-13, D-26;
RESEARCH Q8).

Owner rule: no test runs the real `codex`. Every session here is tests/fakecodex.py replaying a
synthetic fixture under tests/fixtures/codex/; nothing contacts OpenAI. Every environment is
built with made-up values over test_drive's key-free base, so a key the owner has set can never
reach an assertion or a log.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from reverseapoc import backends, codexjson, driver, session
from reverseapoc.session import run_session
from reverseapoc.streamjson import Usage
from reverseapoc.targets import REPO_ROOT
from test_drive import Rig, _keyed
from test_driver import EXE, FUNC, LOG, RUN, UNIT, Night, Sess

HERE = Path(__file__).resolve().parent
FAKECODEX = HERE / "fakecodex.py"
FIXTURES = HERE / "fixtures" / "codex"
LUNA = "gpt-6-luna"
SOL = "gpt-6.1-sol"
CODEX_VERSION = "0.167.0"
UNIT_PATH = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/view/src/{EXE}/{UNIT}.c"
REAL_DRIVE = driver.drive


def _events(name: str) -> tuple[dict, ...]:
    lines = (FIXTURES / f"{name}.jsonl").read_bytes().splitlines(keepends=True)
    return codexjson.parse(lines).events


def fake_codex_argv(prompt: str, *, model: str, attempt_dir: Path) -> list[str]:
    """Deps.codex_argv for the tests: session.build_codex_argv with tests/fakecodex.py in the
    executable's place, so the fake checks the very argv the driver built."""
    real = session.build_codex_argv(prompt, codex="codex", model=model, attempt_dir=attempt_dir)
    return [sys.executable, str(FAKECODEX), *real[1:]]


def write_pass(repo: Path, arm: str = LUNA, *, version: str = CODEX_VERSION,
               result: str = "PASS") -> Path:  # fmt: skip
    """A canary-pass file as the Codex canary writes it (RULINGS "Harness")."""
    path = repo / "build" / "driver" / "canary" / f"{arm}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"arm": arm, "harness": "codex", "cli_version": version,
                                "date": "2026-11-10", "result": result}), encoding="utf-8")
    return path


def codex_version_reply(rig: Rig, version: str = CODEX_VERSION) -> None:
    """The rig's runner answers `codex --version` as the installed CLI would."""
    rig.runner.replies.append((lambda argv: argv == ["codex", "--version"],
                               (0, f"codex-cli {version}\n", "")))  # fmt: skip


def codex_night(tmp_path: Path, monkeypatch, *, scenario: str = "luna_success",
                extra_env: dict | None = None,
                spec: Sess | None = None) -> tuple[Rig, Night, dict]:  # fmt: skip
    """`drive` on a Rig whose night (run_drive's own DriveConfig and arm table) runs in
    test_driver's night harness with fakecodex sessions and a fake gate; the base env names
    the fixture and holds no key. `spec`: what the "agent" leaves besides the stream (the
    night harness's Sess files, written after the session)."""
    rig = Rig(tmp_path / "rig")
    codex_version_reply(rig)
    night = Night(tmp_path / "night", gate_exits=[1])
    night._current = spec or Sess(write=None)
    real = REAL_DRIVE  # never an earlier call's patch

    def drive(config, deps, *, lock=None):
        moved = replace(config, repo_root=night.repo, min_cli_version=(2, 1, 240),
                        attempts_per_function=1)  # fmt: skip
        return real(moved, night.deps(codex_argv=fake_codex_argv))

    monkeypatch.setattr(driver, "drive", drive)
    env = _keyed(rig.env, FAKECODEX_SCENARIO=scenario, **(extra_env or {}))
    return rig, night, env


# ---- Task 1: the argv, the stream and the record ----


def test_build_codex_argv(tmp_path):
    """D-13: `codex exec --json`, workspace-write limited to the attempt dir, network off,
    approval never, no user config, the Windows sandbox set to unelevated by the argv itself
    (the user config that enabled it is ignored, and without it Codex ran no sandbox and
    rejected every command; owner's ruling 2026-11-10: unelevated, the mode the owner's own
    Codex runs, as elevated needs an admin setup), the attempt dir trusted so its per-session rules load (RESEARCH
    A4, A5: the canary proves both), the prompt last."""
    attempt_dir = tmp_path / "attempt-1"
    argv = session.build_codex_argv("the prompt", codex="codex.exe", model=LUNA,
                                    attempt_dir=attempt_dir)  # fmt: skip
    trust = f"projects.{json.dumps(str(attempt_dir))}.trust_level=\"trusted\""
    assert argv == ["codex.exe", "exec", "--json", "--model", LUNA, "--sandbox",
                    "workspace-write", "--cd", str(attempt_dir), "--skip-git-repo-check",
                    "--ephemeral", "--ignore-user-config", "-c", 'approval_policy="never"', "-c",
                    "sandbox_workspace_write.network_access=false", "-c",
                    'windows.sandbox="unelevated"', "-c", trust, "the prompt"]  # fmt: skip
    for banned in ("--full-auto", "danger-full-access", "--ignore-rules"):
        assert banned not in argv


def test_codexjson_usage():
    """Two turn.completed events: input and cached input summed (cached as cache_read, no
    cache_creation), reasoning tokens added to output, two turns, no cost, the wall clock's
    duration; the malformed line is counted and skipped."""
    lines = (FIXTURES / "usage_two_turns.jsonl").read_bytes().splitlines(keepends=True)
    parsed = codexjson.parse(lines)
    assert parsed.malformed == 1
    assert codexjson.turns(parsed.events) == 2
    assert codexjson.usage(parsed.events, seconds=12.5) == Usage(
        input_tokens=3000, output_tokens=650, cache_read_tokens=2100, cache_creation_tokens=0,
        turns=2, cost_usd=0.0, duration_ms=12500)  # fmt: skip


def test_codexjson_commands_and_writes():
    """Every command_execution item once, in order, a list command joined as the shell got
    it, a started-only one included; every file_change path; failure texts."""
    events = _events("commands_and_writes")
    assert codexjson.commands(events) == ["uv run --frozen reverseapoc attempt context",
                                          "uv run --frozen reverseapoc attempt asm",
                                          "type notes.md"]  # fmt: skip
    assert codexjson.write_targets(events) == ["notes.md", "view/src/ufo2p/u_00010000.c"]
    assert codexjson.failure(events) is None
    assert codexjson.failure(_events("turn_failed")) == "made-up turn failure"
    assert codexjson.failure(_events("top_error")) == "made-up stream error"


def test_codex_prompt():
    """The matching goal, the watcom-decomp skill's body without its front matter, and a
    closing block naming the session's files and the wrapper; no orig/ path."""
    goal = session.goal_prompt(FUNC, UNIT, EXE, unit_path=UNIT_PATH)
    skill = (REPO_ROOT / session.SKILL).read_text(encoding="utf-8")
    prompt = session.codex_prompt(goal, skill)
    assert goal.removeprefix("/goal ") in prompt
    assert "# Matching one Watcom function" in prompt
    assert "name: watcom-decomp" not in prompt and not prompt.startswith("---")
    for name in ("plan.json", "check-note.json", "giveup.json", "notes.md"):
        assert name in prompt, name
    assert "uv run --frozen reverseapoc attempt" in prompt
    assert "orig/" not in prompt and "orig\\" not in prompt


def _note(prompt: str) -> str:
    [note] = [part for part in prompt.split("\n\n") if part.startswith("Harness note:")]
    return note


def test_codex_prompt_harness_note():
    """07.2 review WR-10: the skill says to look around with Read, Grep and Glob, which a Codex
    session does not have. One harness note after the skill body, before the session rules,
    says so and names where files are read instead: the wrapper forms that print (context,
    asm, asm <NAME>, check), each of them a form the rules allow. The session rules forbid any
    other command, reads, listings and searches included; nothing names a read tool."""
    from reverseapoc import hooks

    goal = session.goal_prompt(FUNC, UNIT, EXE, unit_path=UNIT_PATH)
    skill = (REPO_ROOT / session.SKILL).read_text(encoding="utf-8")
    prompt = session.codex_prompt(goal, skill)
    note = _note(prompt)
    assert "no Read, Grep or Glob tool" in note
    assert prompt.index("# Matching one Watcom function") < prompt.index(note)
    assert prompt.index(note) < prompt.index("Session rules:")
    forms = re.findall(r"`(attempt [^`]+)`", note)
    assert sorted(forms) == ["attempt asm", "attempt asm <NAME>", "attempt check",
                             "attempt context"]  # fmt: skip
    for form in forms:
        command = f"uv run --frozen reverseapoc {form.replace('<NAME>', 'func_00010020')}"
        assert hooks.bash_allowed(command, kind="matching"), command
    closing = prompt[prompt.index("Session rules:"):]
    assert "not even to read, list or search a file" in closing
    assert "read_file" not in prompt


def test_drive_codex_arm_records(tmp_path, capsys, monkeypatch):
    """A Luna night launches tests/fakecodex.py through codex exec --json and records the
    attempt with harness codex, backend openai, the requested model, no init model, the
    fixture's tokens and an estimated cost."""
    rig, night, env = codex_night(tmp_path, monkeypatch)
    write_pass(rig.repo)
    code, _, err = rig.drive(capsys, seams={"base_env": env}, night_model=LUNA,
                             allow_egress=(LUNA,), workers=1)  # fmt: skip
    assert code == 0, err
    launched = night.launched[0]
    assert launched.argv[:3] == [sys.executable, str(FAKECODEX), "exec"]
    assert launched.argv[launched.argv.index("--model") + 1] == LUNA
    assert "# Matching one Watcom function" in launched.argv[-1]
    record = night.kinds("attempt")[0]
    driver.validate_record(record)
    assert (record["harness"], record["backend"], record["model_requested"]) == (
        "codex", "openai", LUNA)  # fmt: skip
    assert record["model"] is None and record["cli_version"] is None
    assert record["tokens"] == {"input": 3000, "output": 650, "cache_read": 2100,
                                "cache_creation": 0}  # fmt: skip
    assert record["turns"] == 2
    assert (record["cost_source"], record["cost_usd"]) == ("estimate", 0.0)
    assert (night.attempt_dir() / driver.TRANSCRIPT).read_bytes() == (
        FIXTURES / "luna_success.jsonl").read_bytes()  # fmt: skip
    assert (night.repo / LOG).is_file()


def test_codex_env_has_no_openai_key(tmp_path, capsys, monkeypatch):
    """D-12 and RULINGS "Token-leak guard covers every arm": the Codex session uses the
    owner's ChatGPT login, so its env holds no OPENAI_API_KEY or OPENAI_BASE_URL, no arm's
    key variable, no ANTHROPIC_* variable and no Google API key variable."""
    record = tmp_path / "fakecodex-record.json"
    leaks = {"OPENAI_API_KEY": "made-up-openai-0001", "OPENAI_BASE_URL": "https://x.invalid",
             "DEEPSEEK_API_KEY": "made-up-0002", "ZAI_API_KEY": "made-up-0003",
             "OPENROUTER_API_KEY": "made-up-0004", "ANTHROPIC_API_KEY": "made-up-0005",
             "ANTHROPIC_AUTH_TOKEN": "made-up-0006", "ANTHROPIC_BASE_URL": "https://y.invalid",
             "ANTHROPIC_MODEL": "made-up", "GOOGLE_API_KEY": "made-up-0007",
             "GEMINI_API_KEY": "made-up-0008"}  # fmt: skip
    rig, night, env = codex_night(tmp_path, monkeypatch,
                                  extra_env={"FAKECODEX_RECORD": str(record), **leaks})
    write_pass(rig.repo)
    code, _, err = rig.drive(capsys, seams={"base_env": env}, night_model=LUNA,
                             allow_egress=(LUNA,), workers=1)  # fmt: skip
    assert code == 0, err
    names = set(json.loads(record.read_text(encoding="utf-8"))["env"])
    assert names, "the fake codex wrote no env"
    assert sorted(names & set(leaks)) == []
    assert [n for n in names if n.upper().startswith("ANTHROPIC_")] == []


def test_codex_session_env_strips_every_other_vendor():
    """The env builder itself (RULINGS: one test on the session env): a Codex arm's session
    loses OPENAI_API_KEY, OPENAI_BASE_URL, every arm key, every ANTHROPIC_* variable and the
    Google key variables; nothing else is dropped and no endpoint is added."""
    arms = backends.load_arms()
    base = {"PATH": "made-up-path", "OPENAI_API_KEY": "made-up", "OPENAI_BASE_URL": "made-up",
            "DEEPSEEK_API_KEY": "made-up", "ANTHROPIC_API_KEY": "made-up",
            "ANTHROPIC_SMALL_FAST_MODEL": "made-up", "GOOGLE_API_KEY": "made-up",
            "GEMINI_API_KEY": "made-up", "GOOGLE_GENAI_API_KEY": "made-up"}  # fmt: skip
    for name in (LUNA, SOL):
        env = backends.session_env(arms[name], base, arms)
        assert sorted(env) == ["PATH", "REVERSEAPOC_EGRESS"], name


# ---- Task 2: the guard set (D-13, D-26; RESEARCH Q8 "Command restriction", Pitfall 6) ----

ATTEMPT = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1"
WRAPPER = "uv run --frozen reverseapoc attempt"
RULES_TEXT = ('prefix_rule(pattern=["uv", "run", "--frozen", "reverseapoc", "attempt"], '
              'decision="allow")\n')  # fmt: skip


def _run_codex(capsys, rig: Rig, env: dict) -> tuple[int, str, str]:
    write_pass(rig.repo)
    return rig.drive(capsys, seams={"base_env": env}, night_model=LUNA, allow_egress=(LUNA,),
                     workers=1)  # fmt: skip


def test_rules_file_allows_only_the_wrapper(tmp_path, capsys, monkeypatch):
    """D-13 (RESEARCH Q8 option a): the per-session rules file holds one prefix rule, the
    wrapper's, allowed; it is generated under the attempt dir in gitignored build/, never at
    the checkout's root; the session is told where its wrapper ledger is, outside its
    workspace, and the ledger starts empty."""
    record = tmp_path / "fakecodex-record.json"
    rig, night, env = codex_night(tmp_path, monkeypatch,
                                  extra_env={"FAKECODEX_RECORD": str(record)})  # fmt: skip
    code, _, err = _run_codex(capsys, rig, env)
    assert code == 0, err
    assert driver.CODEX_RULES == ".codex/rules/attempt.rules"
    rules = night.attempt_dir() / driver.CODEX_RULES
    assert rules.read_text(encoding="utf-8") == RULES_TEXT
    assert not (night.repo / ".codex").exists() and not (rig.repo / ".codex").exists()
    ledger_env = driver.attempt.WRAPPER_LEDGER_ENV
    ledger = Path(night.launched[0].env[ledger_env])
    name = f"{EXE}__{FUNC}__attempt-1.jsonl"
    assert ledger == night.repo / "build" / "driver" / RUN / "ledger" / name
    assert not ledger.is_relative_to(night.attempt_dir())
    assert ledger.read_bytes() == b""
    assert ledger_env in json.loads(record.read_text(encoding="utf-8"))["env"]


def test_audit_flags_a_non_wrapper_command():
    """Every command must be an exact wrapper form (hooks.bash_allowed, matching kind); the
    reasons name each command that is not."""
    clean = [f"{WRAPPER} context", f"{WRAPPER} check", f"{WRAPPER} asm func_00010010",
             f"{WRAPPER} plan", f"{WRAPPER} giveup"]  # fmt: skip
    assert driver.codex_command_strays(clean) == []
    strays = driver.codex_command_strays(["type notes.md", f"{WRAPPER} check --src x", *clean])
    assert len(strays) == 2
    assert "type notes.md" in strays[0] and f"{WRAPPER} check --src x" in strays[1]


# the shell as the Windows CLI quotes it (spike 012's rejected-command lines)
POWERSHELL = r'"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"'


def _ran(*commands: object) -> list[dict]:
    """One completed command_execution event per command, in order."""
    return [{"type": "item.completed",
             "item": {"id": f"item_{n}", "type": "command_execution", "command": command,
                      "aggregated_output": "", "exit_code": 0, "status": "completed"}}
            for n, command in enumerate(commands)]  # fmt: skip


def _audited_as(inner: str) -> re.Pattern:
    """A stray finding's `(audited as: <inner>)`, the inner text in backticks or not."""
    return re.compile(r"\(audited as: `?" + re.escape(inner) + r"`?\)")


def test_codexjson_unwraps_the_windows_shell():
    """The Windows CLI reports each command wrapped in its shell, `"<...>\\powershell.exe"
    -Command <cmd>` (spike 012's rejected-command lines): commands() gives <cmd>, one layer."""
    assert codexjson.commands(_events("canary_codex_pass_wrapped")) == [
        "whoami", "Set-Content -LiteralPath '..\\codex-canary-outside.txt' -Value canary",
        "Invoke-WebRequest -Uri 'https://example.com/'",
        f"{WRAPPER} context; echo canary > ..\\codex-canary-compound.txt",
        f"{WRAPPER} check"]  # fmt: skip


@pytest.mark.parametrize("command", [
    f"{POWERSHELL} -Command '{WRAPPER} check'",
    f'{POWERSHELL} -Command "{WRAPPER} check"',
    f"{POWERSHELL} -NoProfile -Command '{WRAPPER} asm func_00010010'",
    r'"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Command "' + WRAPPER
    + ' context"',
    r"c:\WINDOWS\system32\windowspowershell\V1.0\PowerShell.EXE -noprofile -command '"
    + WRAPPER + " giveup'",
    f"C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command '{WRAPPER} plan'",
    r'"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -Command "' + WRAPPER + ' check"',
    ["C:\\Program Files\\PowerShell\\7\\pwsh.exe", "-Command", f"{WRAPPER} check"],
])  # fmt: skip
def test_audit_passes_a_shell_wrapped_wrapper_call(command):
    """One layer of the real Windows shell (its absolute path, any case, either slash, quoted
    or not) around an exact wrapper form is audited as the wrapper form."""
    assert driver.codex_command_strays(codexjson.commands(_ran(command))) == []


@pytest.mark.parametrize("command", [
    f"{POWERSHELL} -Command '{WRAPPER} check; echo x > f'",
    f"{POWERSHELL} -Command whoami",
    f"{POWERSHELL} -Command \"{POWERSHELL} -Command '{WRAPPER} check'\"",
    f"{POWERSHELL} -Command {WRAPPER} check",
    f"{POWERSHELL} -EncodedCommand '{WRAPPER} check'",
    f"{POWERSHELL} -NoProfile -NoProfile -Command '{WRAPPER} check'",
    f"{POWERSHELL} -Command '{WRAPPER} check",
    f'.\\powershell.exe -Command "{WRAPPER} check"',
    f'".\\powershell.exe" -Command "{WRAPPER} check"',
    f"powershell.exe -Command '{WRAPPER} check'",
    f"pwsh -Command '{WRAPPER} check'",
    f"pwsh.exe -NoProfile -Command '{WRAPPER} check'",
    f'C:\\Users\\x\\powershell.exe -Command "{WRAPPER} check"',
    f'"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\x\\..\\powershell.exe" -Command '
    f'"{WRAPPER} check"',
    f'"D:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "{WRAPPER} check"',
    f"cmd.exe /c '{WRAPPER} check'",
    f"bash -lc '{WRAPPER} check'",
])  # fmt: skip
def test_audit_flags_a_shell_wrapped_stray(command):
    """A wrapped compound or non-wrapper command, a doubly wrapped one (one layer comes off, the
    shell left is a stray), a -Command with more than one argument, another flag or an
    unbalanced quote; and a shell that is not the real one at its absolute path (a planted
    `.\\powershell.exe`, a bare name the current directory could resolve, another directory or
    drive, a `..` path, cmd or bash): each still a stray, judged as the whole text."""
    assert len(driver.codex_command_strays(codexjson.commands(_ran(command)))) == 1


def test_audit_flags_orig_and_third_party():
    """Finding 2 (D-10): a command naming orig or third_party as a path part, in any form, is a
    stray even inside an allowed shape; a name merely holding the word is not."""
    named = [f"{WRAPPER} asm orig", f"{WRAPPER} asm third_party", "type orig\\UFO2P.EXE",
             "ls third_party/watcom", "type ..\\..\\ORIG\\TACP.EXE", 'cat "C:/x/orig/a"']
    strays = driver.codex_command_strays(named)
    assert len(strays) == len(named)
    assert all("orig" in s.casefold() or "third_party" in s for s in strays)
    assert driver.codex_command_strays([f"{WRAPPER} asm original_x"]) == []


def _attempt_tree(root: Path) -> dict[str, str]:
    """A made-up attempt dir as the driver leaves it at launch; its launch inventory."""
    for rel, text in (("view-head.txt", "made-up\n"), ("context.md", "made-up pack\n"),
                      ("view/src/ufo2p/u_00010000.c", "int x;\n"),
                      (driver.CODEX_RULES, RULES_TEXT)):  # fmt: skip
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return driver.attempt_inventory(root)


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_flags_a_stray_file(tmp_path):
    """The attempt dir after the session may hold only the session files, the driver's own
    files as they were at launch (the rules file with its recorded hash) and wrapper output the
    ledger names; a new x.txt, a changed rules file and a session-written .codex/config.toml are
    strays (finding 3), the view is the view hashes' business."""
    root = tmp_path / "attempt-1"
    launch = _attempt_tree(root)
    for rel in ("plan.json", "check-note.json", "giveup.json", "notes.md", "proposals.jsonl",
                driver.TRANSCRIPT, "x.txt", ".codex/config.toml"):  # fmt: skip
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("made up\n", encoding="utf-8")
    (root / "view/src/ufo2p/u_00010000.c").write_text("int y;\n", encoding="utf-8")
    (root / driver.CODEX_RULES).write_text(RULES_TEXT + 'prefix_rule(pattern=["cmd"], '
                                           'decision="allow")\n', encoding="utf-8")
    strays = driver.codex_inventory_strays(driver.attempt_inventory(root), launch=launch,
                                           ledger={})  # fmt: skip
    assert sorted(rel for rel, _ in strays) == [".codex/config.toml", driver.CODEX_RULES, "x.txt"]
    (root / driver.CODEX_RULES).unlink()
    gone = driver.codex_inventory_strays(driver.attempt_inventory(root), launch=launch, ledger={})
    assert (driver.CODEX_RULES, "removed during the session") in gone


def test_audit_catches_a_forged_checks_log(tmp_path):
    """D-26: wrapper output must hold the sha256 of the ledger's last entry for it: a changed
    checks.jsonl and a checks/0002.json the ledger never saw are strays; a ledgered
    checks/0001.c, a rewritten context.md the wrapper ledgered and its cache entry are not."""
    root = tmp_path / "attempt-1"
    launch = _attempt_tree(root)
    files = {"checks.jsonl": '{"n": 1, "exit": 1}\n', "checks/0001.c": "int x;\n",
             "checks/0002.json": "{}\n", "context.md": "rebuilt pack\n",
             "view/build/attempt-cache/asm.json": "{}\n"}  # fmt: skip
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    ledger_path = tmp_path / "ledger.jsonl"
    lines = [{"path": rel, "sha256": _sha(root / rel)} for rel in
             ("checks.jsonl", "checks/0001.c", "context.md", "view/build/attempt-cache/asm.json")]
    ledger_path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    ledger = driver.read_wrapper_ledger(ledger_path)
    assert driver.codex_inventory_strays(driver.attempt_inventory(root), launch=launch,
                                         ledger=ledger) == [("checks/0002.json",
                                                             "a wrapper-owned file the wrapper's "
                                                             "ledger never saw")]  # fmt: skip
    (root / "checks.jsonl").write_text('{"n": 1, "exit": 0}\n', encoding="utf-8")
    (root / "view/build/attempt-cache/asm.json").write_text('{"x": 1}\n', encoding="utf-8")
    strays = dict(driver.codex_inventory_strays(driver.attempt_inventory(root), launch=launch,
                                                ledger=ledger))  # fmt: skip
    assert set(strays) == {"checks.jsonl", "checks/0002.json", "view/build/attempt-cache/asm.json"}
    assert "ledger" in strays["checks.jsonl"]


def test_audit_flags_a_write_outside_the_allowlist(tmp_path):
    """Every file_change path, relative to the attempt dir (Codex's --cd) or absolute, must pass
    the session's write allowlist; a path outside the checkout, a wrapper-owned file and any
    path naming orig/ are strays."""
    repo = tmp_path / "repo"
    root = repo / ATTEMPT
    ok = {f"{ATTEMPT}/notes.md", f"{ATTEMPT}/view/src/{EXE}/{UNIT}.c"}
    targets = ["notes.md", f"view/src/{EXE}/{UNIT}.c", str(root / "notes.md"), "x.txt",
               "checks.jsonl", "../../../../../../../outside.txt", "../../../../../../orig/X"]
    strays = driver.codex_write_strays(targets, attempt_dir=root, repo=repo,
                                       allowed=lambda rel: rel in ok)  # fmt: skip
    assert [s.split(":")[0] for s in strays] == targets[3:]


def test_codex_stray_quarantines(tmp_path, capsys, monkeypatch):
    """A file the session left outside the allowlist stops the night and is quarantined, and
    the attempt is recorded as a guardrail give-up, as a Claude session's stray is."""
    spec = Sess(write=None, files=((f"{ATTEMPT}/x.txt", "made up\n"),))
    rig, night, env = codex_night(tmp_path, monkeypatch, spec=spec)
    code, _, _ = _run_codex(capsys, rig, env)
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.GUARDRAIL and "x.txt" in stopped["detail"]
    assert list(night.quarantine.rglob("x.txt"))
    assert not (night.attempt_dir() / "x.txt").exists()
    record = night.kinds("attempt")[0]
    assert (record["outcome"], record["abort_reason"]) == ("GAVE_UP", driver.GUARDRAIL)


def test_audit_stops_the_night_on_a_stray_command_or_write(tmp_path, capsys, monkeypatch):
    """Finding 1: the Codex stream's commands and file_change paths reach the night's audit
    (never through the Claude-only transcript reader)."""
    for name, words in (("stray_command", "type notes.md"), ("stray_write", "tools/x.py")):
        rig, night, env = codex_night(tmp_path / name, monkeypatch, scenario=name)
        code, _, _ = _run_codex(capsys, rig, env)
        assert code != 0, name
        stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
        assert stopped["reason"] == driver.GUARDRAIL and words in stopped["detail"], stopped


def test_a_stray_names_the_command_as_the_session_ran_it(tmp_path, capsys, monkeypatch):
    """A stray command is named as the session ran it, the Windows shell's path included, and,
    with that one layer taken off, by what the audit judged: `<original> (audited as:
    <inner>)` in the night's STOPPED detail (the quarantine reason), never the inner text
    alone."""
    rig, night, env = codex_night(tmp_path, monkeypatch, scenario="stray_command_wrapped")
    code, _, _ = _run_codex(capsys, rig, env)
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    detail = stopped["detail"]
    assert stopped["reason"] == driver.GUARDRAIL, stopped
    assert f"{POWERSHELL} -Command 'whoami'" in detail, detail
    assert _audited_as("whoami").search(detail), detail


def test_audit_quarantines_a_session_written_codex_config(tmp_path, capsys, monkeypatch):
    """Finding 3: a .codex/config.toml the session writes into its trusted workspace is a
    stray: quarantined, the night stops, and no later launch ever sees it (each launch also
    starts from a fresh attempt dir with the driver's rules file only)."""
    config = (f"{ATTEMPT}/.codex/config.toml", "approval_policy = 'on-request'\n")
    spec = Sess(write=None, files=(config,))
    rig, night, env = codex_night(tmp_path, monkeypatch, scenario="transient_no_turn", spec=spec)
    code, _, _ = _run_codex(capsys, rig, env)
    assert code != 0
    assert len(night.launched) == 1
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.GUARDRAIL and ".codex/config.toml" in stopped["detail"]
    assert not (night.attempt_dir() / ".codex" / "config.toml").exists()
    assert list(night.quarantine.rglob("config.toml"))


# ---- Task 3: the Codex canary, its pass gate and the exception text (D-13; Pitfall 11) ----

OWNER = "made-up-owner"  # the owner's USERNAME in these tests; never the real one


def _codex_canary_rig(tmp_path: Path, *, check: dict | None = None, outside: bool = False,
                      compound: bool = False) -> Rig:  # fmt: skip
    """test_drive's canary rig (the matched canary unit and its functions.csv row in HEAD) with
    a Codex session: fakecodex through the real run_session, then what the real wrapper would
    have left (its check line, the consumed note and their ledger entries) and, when asked, a
    probe's escape outside the workspace."""
    import hashlib

    from test_drive import CONSUMED_NOTE, PASSING_CHECK, Launch, _canary_rig

    rig = _canary_rig(tmp_path, "canary_pass")
    codex_version_reply(rig)
    line = PASSING_CHECK if check is None else check

    def session(argv, *, cwd, env, transcript, timeout_s, popen=subprocess.Popen):
        rig.launches.append(Launch(list(argv), dict(env), Path(cwd)))
        result = run_session(argv, cwd=cwd, env=env, transcript=transcript, timeout_s=timeout_s,
                             popen=popen)  # fmt: skip
        attempt_dir = Path(env[driver.attempt.DIR_ENV])
        wrote = {"checks.jsonl": json.dumps(line) + "\n",
                 "checks/0001.note.json": json.dumps(CONSUMED_NOTE) + "\n"}  # fmt: skip
        with Path(env[driver.attempt.WRAPPER_LEDGER_ENV]).open("a", encoding="utf-8") as fh:
            for rel, text in wrote.items():
                (attempt_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (attempt_dir / rel).write_text(text, encoding="utf-8", newline="\n")
                digest = hashlib.sha256((attempt_dir / rel).read_bytes()).hexdigest()
                fh.write(json.dumps({"path": rel, "sha256": digest}) + "\n")
        for wanted, name in ((outside, driver.CODEX_CANARY_OUTSIDE),
                             (compound, driver.CODEX_CANARY_COMPOUND)):  # fmt: skip
            if wanted:
                (attempt_dir.parent / name).write_text("canary\n", encoding="utf-8")
        return result

    rig.session = session
    return rig


def _codex_canary(rig: Rig, capsys, scenario: str = "canary_codex_pass") -> tuple[int, dict]:
    env = _keyed(rig.env, FAKECODEX_SCENARIO=scenario, USERNAME=OWNER)
    code, out, _ = rig.drive(capsys, canary=True, json=True, night_model=LUNA, canary_model=LUNA,
                             allow_egress=(LUNA,),
                             seams={"base_env": env, "codex_argv": fake_codex_argv})  # fmt: skip
    return code, json.loads(out)


def _pass_file(rig: Rig) -> Path:
    return rig.repo / driver.CANARY_PASS_DIR / f"{LUNA}.json"


@pytest.mark.parametrize("scenario", ["canary_codex_pass", "canary_codex_pass_wrapped"])
def test_codex_canary_pass(tmp_path, capsys, scenario):
    """A sandbox identity that is not the owner, a refused outside write, a refused network
    call, a compound command whose second half did nothing, and a wrapper check that logged
    exit 0 with its consumed note and that the audit passed: CANARY PASS, and the pass file
    names the arm, the harness, the installed CLI version (from `codex --version`, never `codex
    exec`), the date and PASS. The same with every command wrapped in the Windows shell, as the
    real CLI reports it."""
    rig = _codex_canary_rig(tmp_path)
    code, doc = _codex_canary(rig, capsys, scenario)
    failed = [c["check"] for c in doc.get("checks", []) if not c["ok"]]
    assert (code, doc.get("canary")) == (0, "PASS"), failed
    texts = " | ".join(c["check"] for c in doc["checks"])
    for needle in ("whoami", "codexsandbox", driver.CODEX_CANARY_OUTSIDE, "example.com",
                   driver.CODEX_CANARY_COMPOUND, "attempt check", "0001.note.json", "ledger",
                   CODEX_VERSION, "the audit passed every attempt wrapper call"):  # fmt: skip
        assert needle in texts, needle
    assert len(rig.launches) == 1 and rig.launches[0].argv[2] == "exec"
    assert ["codex", "--version"] in rig.runner.calls
    saved = json.loads(_pass_file(rig).read_text(encoding="utf-8"))
    assert {k: saved[k] for k in ("arm", "harness", "cli_version", "result")} == {
        "arm": LUNA, "harness": "codex", "cli_version": CODEX_VERSION, "result": "PASS"}
    assert isinstance(saved["date"], str) and len(saved["date"]) == len("2026-11-10")


def test_codex_canary_prompt_asks_for_every_probe(tmp_path):
    """The prompt asks, in order: whoami, a write one directory above the workspace, a URL
    fetch, the compound command riding the wrapper prefix, the plan and the note, then the
    wrapper check."""
    attempt_dir = tmp_path / "attempt-1"
    prompt = driver.codex_canary_prompt(attempt_dir, 0xD)
    order = ["whoami", str(attempt_dir.parent / driver.CODEX_CANARY_OUTSIDE),
             driver.CODEX_CANARY_URL, f"{WRAPPER} context; ", "plan.json", "check-note.json",
             f"{WRAPPER} check"]  # fmt: skip
    places = [prompt.index(needle) for needle in order]
    assert places == sorted(places), places


@pytest.mark.parametrize(("scenario", "rig_args", "needle"), [
    ("canary_codex_owner", {}, "whoami"),
    ("canary_codex_pass", {"outside": True}, "codex-canary-outside.txt"),
    ("canary_codex_network_ok", {}, "example.com"),
    ("canary_codex_pass", {"compound": True}, "codex-canary-compound.txt"),
    ("canary_codex_pass", {"check": {"n": 1, "exit": 1, "sweep": False, "best_percent": 90.0,
                                     "reloc_ok": False, "bytes_ok": False, "splice_ok": True,
                                     "sweep_hit": None, "source": "checks/0001.c",
                                     "note": "checks/0001.note.json"}}, "attempt check"),
])  # fmt: skip
def test_codex_canary_fails_on_each_escape(tmp_path, capsys, scenario, rig_args, needle):
    """Pitfall 11: the owner's identity, an outside file afterwards, a network call that
    succeeded, the compound command's file, or a check without exit 0: CANARY FAIL naming it,
    and no PASS file."""
    rig = _codex_canary_rig(tmp_path, **rig_args)
    code, doc = _codex_canary(rig, capsys, scenario)
    assert (code, doc["canary"]) == (1, "FAIL")
    failed = " | ".join(c["check"] for c in doc["checks"] if not c["ok"])
    assert needle in failed, failed
    path = _pass_file(rig)
    assert not path.exists() or json.loads(path.read_text(encoding="utf-8"))["result"] != "PASS"


@pytest.mark.parametrize(("scenario", "needles"), [
    ("canary_codex_wrapper_stray", ("the audit flagged an attempt wrapper call",
                                    f"powershell.exe -Command '{WRAPPER} check'")),
    ("canary_codex_no_wrapper", ("no attempt wrapper call ran",)),
])  # fmt: skip
def test_codex_canary_proves_the_audit_passes_its_wrapper_call(tmp_path, capsys, scenario,
                                                                needles):  # fmt: skip
    """The positive control. Every probe is flagged, and the canary's own attempt wrapper calls
    (each command naming the wrapper, the compound probe aside) must pass the audit a night
    runs. A wrapper call the audit flags (here a bare `powershell.exe`, which the unwrap
    refuses: every night session would be quarantined) is a CANARY FAIL naming the command
    text it saw; a stream with no wrapper call (rejected or never made, whatever the wrapper's
    files say) proves nothing and fails too. That is the only failing line; the pass file says
    FAIL."""
    rig = _codex_canary_rig(tmp_path)
    code, doc = _codex_canary(rig, capsys, scenario)
    failed = [c["check"] for c in doc["checks"] if not c["ok"]]
    assert (code, doc["canary"], len(failed)) == (1, "FAIL", 1), failed
    for needle in needles:
        assert needle in failed[0], (needle, failed)
    assert json.loads(_pass_file(rig).read_text(encoding="utf-8"))["result"] == "FAIL"


def test_codex_canary_names_each_flagged_probe_as_it_ran(tmp_path, capsys):
    """A canary line for a flagged probe carries its stray finding: the command as the session
    ran it, the Windows shell's path included, and what the audit judged once that one layer
    came off (`<original> (audited as: <inner>)`)."""
    events = _events("canary_codex_pass_wrapped")
    originals = [e["item"]["command"] for e in events
                 if e["type"] == "item.completed" and e["item"]["type"] == "command_execution"]
    audited = codexjson.commands(events)
    _, doc = _codex_canary(_codex_canary_rig(tmp_path), capsys, "canary_codex_pass_wrapped")
    for label, index in (("whoami", 0), ("fetch", 2), ("compound command", 3)):
        [line] = [c["check"] for c in doc["checks"] if f"flagged the {label} probe" in c["check"]]
        assert originals[index] in line, (label, line)
        assert _audited_as(audited[index]).search(line), (label, line)


def test_codex_canary_fail_names_what_the_policy_rejected(tmp_path, capsys):
    """Spike 012: Codex rejected every command, so none ran and the probes are FAILs (a
    rejection is never a pass: each probe must run and be flagged), and the FAIL output adds,
    as diagnostics only, the CLI's stderr lines saying `rejected: blocked by policy` (Codex
    names them nowhere else); the stderr still reaches the console."""
    rig = _codex_canary_rig(tmp_path / "json")
    code, doc = _codex_canary(rig, capsys, "canary_codex_rejected")
    assert (code, doc["canary"]) == (1, "FAIL")
    failed = " | ".join(c["check"] for c in doc["checks"] if not c["ok"])
    for needle in ("whoami was never run", "fetch of https://example.com/ was never run",
                   "did not flag the whoami probe", "did not flag the fetch probe",
                   "did not flag the compound command probe"):  # fmt: skip
        assert needle in failed, failed
    rejected = doc["codex_rejected"]
    assert len(rejected) == 2, rejected
    assert all("rejected: blocked by policy" in line for line in rejected)
    assert "-Command whoami" in rejected[0] and "attempt check" in rejected[1]
    assert not any("rejected: blocked by policy" in c["check"] for c in doc["checks"])
    assert json.loads(_pass_file(rig).read_text(encoding="utf-8"))["result"] == "FAIL"
    text = _codex_canary_rig(tmp_path / "text")
    env = _keyed(text.env, FAKECODEX_SCENARIO="canary_codex_rejected", USERNAME=OWNER)
    code, out, err = text.drive(capsys, canary=True, night_model=LUNA, canary_model=LUNA,
                                allow_egress=(LUNA,),
                                seams={"base_env": env, "codex_argv": fake_codex_argv})  # fmt: skip
    lines = out.splitlines()
    assert (code, lines[-1]) == (1, "CANARY FAIL")
    notes = [line for line in lines if line.startswith("NOTE: ")]
    assert len(notes) == 2 and all("rejected: blocked by policy" in n for n in notes), notes
    assert "an unrelated warning" in err and "-Command whoami" in err


def test_codex_canary_pass_adds_no_rejections(tmp_path, capsys):
    """A PASS carries no rejected-command diagnostics."""
    code, doc = _codex_canary(_codex_canary_rig(tmp_path), capsys)
    assert (code, "codex_rejected" in doc) == (0, False)


@pytest.mark.parametrize("state", ["none", "fail", "other-version"])
def test_codex_arm_refused_without_a_pass(tmp_path, capsys, state):
    """D-13: no Codex arm runs before its canary passed on the installed CLI: no pass file, a
    FAIL one, or one naming another version exits 2 before any session, naming the canary
    command to run."""
    rig = Rig(tmp_path)
    codex_version_reply(rig)
    if state == "fail":
        write_pass(rig.repo, result="FAIL")
    elif state == "other-version":
        write_pass(rig.repo, version="0.166.0")
    env = _keyed(rig.env)
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": env}, night_model=LUNA,
                             allow_egress=(LUNA,), workers=1)  # fmt: skip
    assert code == 2
    detail = json.loads(out)["detail"]
    assert f"--canary --night-model {LUNA} --allow-egress {LUNA}" in detail, detail
    assert list((rig.repo / "build").rglob("attempt-*")) == []


def test_claude_md_states_the_exception():
    """CLAUDE.md and .claude/rules/workflow.md keep Claude Code as the only agent runtime and
    name the one scoped exception: Codex as `reverseapoc drive` arms for spike 012, its
    per-session config generated under build/."""
    for rel in ("CLAUDE.md", ".claude/rules/workflow.md"):
        text = " ".join((REPO_ROOT / rel).read_text(encoding="utf-8").split())
        for needle in ("only agent runtime", "Codex", "reverseapoc drive", "spike 012", "build/"):
            assert needle in text, (rel, needle)


# ---- security review finding 4: a linked ancestor of the wrapper's cache ----


@pytest.mark.parametrize("linked", ["view/build", "view"])
def test_inventory_never_follows_a_linked_cache_ancestor(tmp_path, linked):
    """A session that turns view/ or view/build/ into a link (a junction on Windows) must not
    steer the cache walk outside the attempt dir or hide files from it: the link itself is in
    the inventory as a stray, nothing behind it is read, and the target is left untouched."""
    from test_driver import _plant_dir_link

    root = tmp_path / "attempt-1"
    launch = _attempt_tree(root)
    outside = tmp_path / "outside"
    behind = outside / "build" / "attempt-cache" if linked == "view" else outside / "attempt-cache"
    behind.mkdir(parents=True)
    (behind / "x.json").write_text("{}\n", encoding="utf-8")
    (outside / "keep.c").write_text("int keep;\n", encoding="utf-8")
    _plant_dir_link(root / linked, outside)
    now = driver.attempt_inventory(root)
    assert not [rel for rel in now if rel.endswith("x.json")], now
    assert now[linked].startswith("link:")
    strays = dict(driver.codex_inventory_strays(now, launch=launch, ledger={}))
    assert linked in strays
    assert (behind / "x.json").is_file() and (outside / "keep.c").is_file()


def test_a_linked_view_build_stops_the_night(tmp_path, capsys, monkeypatch):
    """The same at night: the linked view/build is a stray, the night stops at the guardrail,
    and the directory it pointed at keeps every file."""
    outside = tmp_path / "outside"
    (outside / "attempt-cache").mkdir(parents=True)
    (outside / "attempt-cache" / "x.json").write_text("{}\n", encoding="utf-8")
    spec = Sess(write=None, link=(f"{ATTEMPT}/view/build", outside))
    rig, night, env = codex_night(tmp_path, monkeypatch, spec=spec)
    code, _, _ = _run_codex(capsys, rig, env)
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.GUARDRAIL and "view/build" in stopped["detail"], stopped
    assert (outside / "attempt-cache" / "x.json").is_file()


# ---- 07.2 review WR-05: the rules file is the driver's bytes at every launch and after ----


def test_codex_rules_problem(tmp_path):
    """WR-05: the rules file is judged against the driver's own bytes (never against what the
    launch inventory happened to see): written by the driver it is fine; changed, extended,
    removed or reached through a linked .codex/ it is not."""
    root = tmp_path / "attempt-1"
    root.mkdir()
    driver.write_codex_rules(root)
    assert driver.codex_rules_problem(root) is None
    rules = root / driver.CODEX_RULES
    rules.write_text(RULES_TEXT + 'prefix_rule(pattern=["cmd"], decision="allow")\n',
                     encoding="utf-8")  # fmt: skip
    assert "attempt.rules" in driver.codex_rules_problem(root)
    rules.unlink()
    assert "attempt.rules" in driver.codex_rules_problem(root)
    from test_driver import _plant_dir_link

    elsewhere = tmp_path / "elsewhere"
    driver.write_codex_rules(elsewhere)
    linked = tmp_path / "attempt-2"
    linked.mkdir()
    _plant_dir_link(linked / ".codex", elsewhere / ".codex")
    assert driver.codex_rules_problem(linked) is not None


def test_no_session_launches_on_a_rules_file_that_is_not_the_drivers(tmp_path, capsys,
                                                                       monkeypatch):  # fmt: skip
    """WR-05: right after writing the rules file, before the session, the driver checks it
    holds its own bytes; when it does not, no Codex session launches and the night stops."""

    def tampered(attempt_dir: Path) -> None:
        path = attempt_dir / driver.CODEX_RULES
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(RULES_TEXT + 'prefix_rule(pattern=["cmd"], decision="allow")\n',
                        encoding="utf-8")  # fmt: skip

    monkeypatch.setattr(driver, "write_codex_rules", tampered)
    rig, night, env = codex_night(tmp_path, monkeypatch)
    code, _, _ = _run_codex(capsys, rig, env)
    assert code != 0
    assert night.launched == []
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert "attempt.rules" in stopped["detail"], stopped


def test_a_session_edit_of_the_rules_file_stops_the_night(tmp_path, capsys, monkeypatch):
    """WR-05: any session write to the rules file (an added allow rule) is a stray: the night
    stops at the guardrail and the detail names the file."""
    edit = (f"{ATTEMPT}/{driver.CODEX_RULES}", 'prefix_rule(pattern=["cmd"], decision="allow")\n')
    rig, night, env = codex_night(tmp_path, monkeypatch, spec=Sess(write=None, append=(edit,)))
    code, _, _ = _run_codex(capsys, rig, env)
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.GUARDRAIL and "attempt.rules" in stopped["detail"], stopped


# ---- 07.2 review WR-04: a session file or the transcript passes only as a regular file ----


@pytest.mark.parametrize("name", ["notes.md", "plan.json", "check-note.json", "giveup.json",
                                  "proposals.jsonl", "transcript.jsonl"])  # fmt: skip
@pytest.mark.parametrize("digest", ["link:C:/made-up/orig/UFO2P.EXE", "outside:C:/made-up"])
def test_a_linked_session_file_is_a_stray(name, digest):
    """WR-04: attempt_inventory records a link by its target, never followed. A session file
    or the transcript recorded as a link (or as resolving outside the attempt dir) is a stray,
    whatever its name: the driver and the wrapper would read through it."""
    strays = dict(driver.codex_inventory_strays({name: digest}, launch={}, ledger={}))
    assert name in strays, strays


# ---- 07.2 review WR-03: the Codex audit fails closed on item types it does not know ----


def _item(ident: str, kind: object, **fields) -> dict:
    return {"type": "item.completed", "item": {"id": ident, "type": kind, **fields}}


def test_codexjson_unknown_items():
    """WR-03: every item outside the known harmless set (agent_message, reasoning, todo_list,
    command_execution, file_change) is named once by its type: an MCP tool call, a web search,
    an item with no type or a non-mapping item; the known ones are not."""
    events = [_item("a", "agent_message", text="made-up"), _item("b", "reasoning", text="x"),
              _item("c", "todo_list", items=[]),
              _item("d", "command_execution", command="uv run --frozen reverseapoc attempt asm"),
              _item("e", "file_change", changes=[{"path": "notes.md", "kind": "add"}]),
              {"type": "item.started", "item": {"id": "f", "type": "mcp_tool_call"}},
              _item("f", "mcp_tool_call", server="made-up", tool="fetch"),
              _item("g", "web_search", query="made-up"), _item("h", None),
              {"type": "item.completed", "item": "made-up"}]  # fmt: skip
    found = codexjson.unknown_items(events)
    assert len(found) == 4, found
    for words in ("mcp_tool_call", "web_search", "None", "made-up"):
        assert any(words in text for text in found), (words, found)


def test_an_unknown_codex_item_stops_the_night(tmp_path, capsys, monkeypatch):
    """WR-03 at night: an MCP tool call in a Codex session's stream stops the night at the
    guardrail, named in the detail."""
    rig, night, env = codex_night(tmp_path, monkeypatch, scenario="mcp_tool_call")
    code, _, _ = _run_codex(capsys, rig, env)
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.GUARDRAIL and "mcp_tool_call" in stopped["detail"], stopped


# ---- 07.2 review CR-01: uv never finds its project in the session's workspace ----

PLANTED = (("pyproject.toml", '[project]\nname = "reverseapoc"\nversion = "9.9.9"\n'),
           ("uv.lock", "version = 1\n"), ("uv.toml", 'index-url = "https://x.invalid"\n'))


def _pick() -> driver.Pick:
    return driver.Pick(EXE, 0x1000, "func_00001000", UNIT, 20, 1)


@pytest.mark.parametrize("arm", [LUNA, SOL, "gemini-flash", "gpt-oss"])
def test_signed_in_sessions_pin_uv_to_the_checkout(tmp_path, arm):
    """CR-01: a Codex or agy session's commands run in its attempt dir, which it may write. The
    one allowed command, `uv run --frozen reverseapoc attempt ...`, would find a project the
    session planted there (pyproject.toml, uv.lock, uv.toml) and run its code outside the
    sandbox. The driver pins uv to the checkout in the session env (UV_PROJECT, never the
    attempt dir or an inherited value) and turns off uv's config discovery (UV_NO_CONFIG)."""
    arms = backends.load_arms()
    repo = tmp_path / "repo"
    claim = driver._Claim(_pick(), RUN, repo, 1, arm=arms[arm])
    claim.attempt_dir.mkdir(parents=True)
    for name, text in PLANTED:
        (claim.attempt_dir / name).write_text(text, encoding="utf-8")
    base = {"PATH": "made-up-path", "UV_PROJECT": str(claim.attempt_dir), "UV_NO_CONFIG": "0"}
    env = claim.env(base, arms)
    assert env["UV_PROJECT"] == str(repo)
    assert env["UV_NO_CONFIG"] == "1"


def test_the_audit_still_flags_a_planted_project():
    """CR-01: the pin prevents; the after-the-fact audit still names each planted file."""
    now = {name: "made-up-digest" for name, _ in PLANTED}
    strays = dict(driver.codex_inventory_strays(now, launch={}, ledger={}))
    assert sorted(strays) == sorted(name for name, _ in PLANTED)


def test_a_claude_session_gets_no_uv_pin(tmp_path):
    """CR-01 scope: a Claude Code session runs in the checkout, its hooks allow only exact
    wrapper forms (no `cd`) and writes only to its own files, so uv already finds the
    checkout's project; the pin is the signed-in harnesses' alone."""
    claim = driver._Claim(_pick(), RUN, tmp_path / "repo", 1)
    env = claim.env({"PATH": "made-up-path"}, backends.load_arms())
    assert "UV_PROJECT" not in env and "UV_NO_CONFIG" not in env


def test_the_installed_uv_knows_the_pin_variables():
    """CR-01: the two variables the pin sets are the ones the installed uv reads (`uv run
    --help` names each beside its flag), so a renamed variable cannot silently undo it."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    shown = subprocess.run([uv, "run", "--help"], capture_output=True, text=True, check=True,
                           timeout=60).stdout  # fmt: skip
    assert "[env: UV_PROJECT=]" in shown
    assert "[env: UV_NO_CONFIG=]" in shown
