"""The Codex CLI harness: GPT-6 Luna and GPT-6.1 Sol as drive arms (07.2-13; D-12, D-13, D-26;
RESEARCH Q8).

Owner rule: no test runs the real `codex`. Every session here is tests/fakecodex.py replaying a
synthetic fixture under tests/fixtures/codex/; nothing contacts OpenAI. Every environment is
built with made-up values over test_drive's key-free base, so a key the owner has set can never
reach an assertion or a log.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

from reverseapoc import backends, codexjson, driver, session
from reverseapoc.streamjson import Usage
from reverseapoc.targets import REPO_ROOT
from test_drive import Rig, _keyed
from test_driver import EXE, FUNC, LOG, RUN, UNIT, Night

HERE = Path(__file__).resolve().parent
FAKECODEX = HERE / "fakecodex.py"
FIXTURES = HERE / "fixtures" / "codex"
LUNA = "gpt-6-luna"
SOL = "gpt-6.1-sol"
CODEX_VERSION = "0.167.0"
UNIT_PATH = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/view/src/{EXE}/{UNIT}.c"


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
                extra_env: dict | None = None) -> tuple[Rig, Night, dict]:  # fmt: skip
    """`drive` on a Rig whose night (run_drive's own DriveConfig and arm table) runs in
    test_driver's night harness with fakecodex sessions and a fake gate; the base env names
    the fixture and holds no key."""
    rig = Rig(tmp_path / "rig")
    codex_version_reply(rig)
    night = Night(tmp_path / "night", gate_exits=[1])
    real = driver.drive

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
    approval never, no user config, the attempt dir trusted so its per-session rules load
    (RESEARCH A4, A5: the canary proves both), the prompt last."""
    attempt_dir = tmp_path / "attempt-1"
    argv = session.build_codex_argv("the prompt", codex="codex.exe", model=LUNA,
                                    attempt_dir=attempt_dir)  # fmt: skip
    trust = f"projects.{json.dumps(str(attempt_dir))}.trust_level=\"trusted\""
    assert argv == ["codex.exe", "exec", "--json", "--model", LUNA, "--sandbox",
                    "workspace-write", "--cd", str(attempt_dir), "--skip-git-repo-check",
                    "--ephemeral", "--ignore-user-config", "-c", 'approval_policy="never"', "-c",
                    "sandbox_workspace_write.network_access=false", "-c", trust,
                    "the prompt"]  # fmt: skip
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
