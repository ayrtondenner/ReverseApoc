"""The `drive` verb (plan 06-25; AGT-01, AGT-04, AGT-06, AGT-07, AGT-11; D-10, D-13, D-24, D-34,
D-36, D-48).

Owner rule: no test runs the real `claude`, docker or anything that reaches the network. Every
command the verb runs goes through an injected runner that records its argv and answers with
made-up output; sessions are tests/fakeclaude.py replaying synthetic streams through the real
session.run_session, or a function that fails the test if it is ever called. The repository is a
tmp git repo. Every name, address and version below is made up.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from reverseapoc import cli, driver, hooks
from reverseapoc.driver import DriveOptions, ExeWorld, PackInfo, Seams
from reverseapoc.functions import FunctionRow, write_functions_csv
from reverseapoc.picker import Pick
from reverseapoc.score import Candidate
from reverseapoc.session import run_session
from test_driver import FAKE, Night, _git, _git_env, _write
from test_driver import RUN as NIGHT_RUN

EXES = ("ufo2p", "tacp")
BASE = {"ufo2p": 0x00010000, "tacp": 0x00110000}  # made-up starts, one 64 KiB region apart each
RUN = "night1"
COMPOSE = ["docker", "compose", "run", "--rm", "-T", "build"]
CONTAINER_UV = [*COMPOSE, "uv", "run", "--frozen", "reverseapoc"]


# ---- the harness ----


def _make_repo(tmp_path: Path, env: dict) -> Path:
    """A clean tmp checkout with the two config directories and no status tables (nothing
    matched yet)."""
    repo = tmp_path / "repo"
    files = {
        ".gitignore": "build/\nasm/\n.venv/\n__pycache__/\n",
        "config/ufo2p/README": "made up\n",
        "config/tacp/README": "made up\n",
        "progress/attempts.jsonl": "",
    }
    for rel, text in files.items():
        _write(repo / rel, text)
    _git(repo, env, "init", "-q")
    _git(repo, env, "add", "--", *files)
    _git(repo, env, "commit", "-q", "-m", "base")
    return repo


def _candidates(exe: str, count: int = 7) -> list[Candidate]:
    """`count` made-up survivors, each in its own unit and its own 64 KiB region, scored so the
    easiest is the first."""
    return [Candidate(BASE[exe] + i * 0x10000, f"{exe}_f{i}", 20 + i, 10 + i, ())
            for i in range(count)]  # fmt: skip


def _unit(exe: str, start: int) -> str:
    return f"u_{start:08x}"


@dataclass
class Packs:
    """The fake pack builder: writes a context.md where the real one would and records it."""

    built: list[tuple[str, int, Path]] = field(default_factory=list)

    def for_exe(self, exe: str):
        def pack(pick: Pick, directory: Path) -> PackInfo:
            _write(directory / "context.md", f"made-up pack of {pick.name}\n")
            self.built.append((pick.exe, pick.start, directory))
            return PackInfo(1000 + len(self.built), ())

        return pack


def _scaffold_fails(pick: Pick) -> None:
    raise AssertionError(f"a dry run scaffolded {pick.unit}")


def _world(packs: Packs) -> dict[str, ExeWorld]:
    out = {}
    for exe in EXES:
        pool = _candidates(exe)
        out[exe] = ExeWorld(pool=pool, units={c.address: _unit(exe, c.address) for c in pool},
                            callees={}, pack=packs.for_exe(exe),
                            scaffold=_scaffold_fails)  # fmt: skip
    return out


@dataclass
class Runner:
    """Every non-git command: records the argv and answers. `replies` maps a predicate over the
    argv to (exit, stdout, stderr); the default is exit 0 with some noise on both streams (F13:
    none of it may reach stdout in --json mode)."""

    replies: list[tuple] = field(default_factory=list)
    calls: list[list[str]] = field(default_factory=list)
    envs: list[dict | None] = field(default_factory=list)  # 07.2-15: the env of each call
    version: str = "2.1.302 (Claude Code)"

    def __call__(self, argv, env=None) -> subprocess.CompletedProcess:
        argv = list(argv)
        self.calls.append(argv)
        self.envs.append(None if env is None else dict(env))
        for match, reply in self.replies:
            if match(argv):
                code, out, err = reply
                return subprocess.CompletedProcess(argv, code, out, err)
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, self.version + "\n", "")
        return subprocess.CompletedProcess(argv, 0, "noise on stdout\n", "noise on stderr\n")


def _never_session(*args, **kwargs):
    raise AssertionError("a session was launched")


def _never_argv(prompt: str, **values):
    raise AssertionError("a claude argv was built")


@dataclass
class Rig:
    """A tmp checkout plus the seams of one `drive` invocation."""

    tmp_path: Path
    runner: Runner = field(default_factory=Runner)
    packs: Packs = field(default_factory=Packs)

    def __post_init__(self) -> None:
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        self.env = _git_env(self.tmp_path)
        self.repo = _make_repo(self.tmp_path, self.env)
        self.git_calls: list[list[str]] = []
        self._git = driver.git_runner(self.repo, env=self.env)
        self.session = _never_session
        self.argv = _never_argv

    def git(self, args, input=None):
        self.git_calls.append(list(args))
        return self._git(args) if input is None else self._git(args, input=input)

    def seams(self, **over) -> Seams:
        fields = dict(run=self.runner, git=self.git, world=lambda: _world(self.packs),
                      session=self.session, argv=self.argv, claude="claude",
                      base_env=self.env)  # fmt: skip
        fields.update(over)
        return Seams(**fields)

    def options(self, **over) -> DriveOptions:
        fields = dict(repo=self.repo, run_id=RUN)
        fields.update(over)
        return DriveOptions(**fields)

    def drive(self, capsys, *, seams: dict | None = None, **options) -> tuple[int, str, str]:
        code = driver.run_drive(self.options(**options), self.seams(**(seams or {})))
        out, err = capsys.readouterr()
        return code, out, err

    def commands(self, word: str) -> list[list[str]]:
        return [call for call in self.runner.calls if word in call]


# ---- Task 1: the tracer ----


def test_drive_defaults():
    args = cli.build_parser().parse_args(["drive"])
    assert (args.max_sessions, args.target_matched, args.workers) == (60, 0, 3)  # D-07 (07-21)
    assert (args.dry_run, args.canary, args.json, args.run) == (False, False, False, None)


def test_the_night_gets_the_verbs_caps_and_workers(tmp_path, capsys, monkeypatch):
    """07-21: run_drive hands --workers, --max-sessions and --target-matched to the night."""
    rig = Rig(tmp_path)
    seen = {}

    def fake_drive(config, deps, *, lock=None):
        seen["config"] = config
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    monkeypatch.setattr(driver, "drive", fake_drive)
    code, _, _ = rig.drive(capsys, json=True, workers=2, max_sessions=7, target_matched=0)
    assert code == 0
    config = seen["config"]
    assert (config.workers, config.max_sessions, config.target_matched) == (2, 7, 0)


def test_dry_run_prints_the_pilot(tmp_path, capsys):
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 0
    assert out.count("\n") == 1 and out.startswith("{"), "stdout is not one JSON line"
    picks = json.loads(out)["picks"]
    assert [p["exe"] for p in picks] == ["ufo2p", "tacp"] * 5  # D-10: 5 + 5, interleaved
    expected = [(exe, BASE[exe] + i * 0x10000) for i in range(5) for exe in EXES]
    assert [(p["exe"], int(p["start"], 16)) for p in picks] == expected  # easiest first
    first = picks[0]
    assert set(first) == {"exe", "start", "name", "unit", "size", "score", "pack", "pack_bytes"}
    assert (first["start"], first["name"]) == ("0x00010000", "ufo2p_f0")
    assert first["unit"] == "u_00010000"
    assert (first["size"], first["score"]) == (20, 10)
    assert len(rig.packs.built) == 10
    for pick in picks:
        pack = rig.repo / pick["pack"]
        assert pack.is_file() and pack.name == "context.md"
        assert pack.resolve().is_relative_to((rig.repo / "build" / "driver" / RUN).resolve())
    assert not rig.commands("gate")  # no gate in a dry run
    assert not [c for c in rig.runner.calls if c[:1] == ["claude"]]  # no claude at all


def test_dry_run_text_lists_the_picks(tmp_path, capsys):
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True)
    assert code == 0
    lines = [line for line in out.splitlines() if line.startswith(("ufo2p", "tacp"))]
    assert len(lines) == 10
    assert lines[0].split()[:3] == ["ufo2p", "0x00010000", "ufo2p_f0"]


def test_drive_builds_gate_argv(tmp_path):
    rig = Rig(tmp_path, runner=Runner(replies=[(lambda a: "gate" in a, (1, '{"ok": false}', ""))]))
    deps = driver.real_deps(rig.options(), rig.seams(), _world(rig.packs))
    pick = Pick("ufo2p", 0x00010010, "func_00010010", "u_x", 20, 10)
    run = deps.gate(pick, 2)
    assert rig.runner.calls == [[*CONTAINER_UV, "gate", "ufo2p/u_x", "--attempts", "2", "--json"]]
    assert (run.exit_code, run.doc) == (1, {"ok": False})


def test_drive_builds_the_partial_gate_and_lint_argv(tmp_path):
    """F7 (consumer): the partial gate takes the repo-relative POSIX path of the best C."""
    rig = Rig(tmp_path)
    deps = driver.real_deps(rig.options(), rig.seams(), _world(rig.packs))
    pick = Pick("tacp", 0x00110000, "func_00110000", "u_y", 20, 10)
    best = "build/driver/night1/tacp/func_00110000/attempt-2/best/u_y.c"
    assert deps.partial_gate(pick, best, 2) == 0
    assert deps.lint(pick) == 0
    assert rig.runner.calls == [
        [*CONTAINER_UV, "gate", "tacp/u_y", "--partial", "--src", best, "--attempts", "2",
         "--json"],
        [*CONTAINER_UV, "lint", "src/tacp/u_y.c", "--json"],
    ]


def test_drive_queue_skips_matched_and_todays_partial_rows(tmp_path):
    """D-09/AGT-07: status.csv's matched rows and the rows made partial in this pass (dated
    today) are never picked; an older partial row is eligible again."""
    rig = Rig(tmp_path)
    comment = "# written by: uv run reverseapoc gate EXE/UNIT; do not edit"
    head = "start,name,unit,status,best_percent,attempts,source_sha256,date"
    sha = "a" * 64
    rows = [
        f"0x00010000,ufo2p_f0,u_00010000,matched,100.00,0,{sha},2026-10-01",
        f"0x00020000,ufo2p_f1,u_00020000,partial,40.00,3,{sha},2026-10-25",
        f"0x00030000,ufo2p_f2,u_00030000,partial,40.00,3,{sha},2026-10-24",
    ]
    _write(rig.repo / "config/ufo2p/status.csv", "\n".join([comment, head, *rows]) + "\n")
    deps = driver.real_deps(rig.options(), rig.seams(), _world(rig.packs), today="2026-10-25")
    starts = [p.start for p in deps.queue(frozenset()) if p.exe == "ufo2p"]
    assert starts[:1] == [0x00030000]
    assert 0x00010000 not in starts and 0x00020000 not in starts


def test_drive_help_lists_the_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["drive", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--max-sessions", "--target-matched", "--dry-run", "--canary", "--run", "--json"):
        assert flag in out, flag


def test_cli_drive_reaches_run_drive(tmp_path, monkeypatch, capsys):
    """`_cmd_drive` builds DriveOptions from the flags and the real seams, then runs drive."""
    seen = {}

    def fake_run(options, seams):
        seen["options"] = options
        return 0

    monkeypatch.setattr(driver, "run_drive", fake_run)
    monkeypatch.setattr(driver, "default_seams", lambda repo: "seams")
    code = cli.main(["drive", "--max-sessions", "40", "--target-matched", "10", "--dry-run",
                     "--run", "pilot1", "--json"])  # fmt: skip
    assert code == 0
    options = seen.get("options")
    assert options is not None, "_cmd_drive never called driver.run_drive"
    assert (options.max_sessions, options.target_matched, options.dry_run) == (40, 10, True)
    assert (options.run_id, options.json, options.canary) == ("pilot1", True, False)


# ---- Task 2: the preflight (D-34, D-36, D-13) and the canary (Pitfalls 2-3) ----

HOST_CLI = ["uv", "run", "--frozen", "reverseapoc"]
DOCKER_INFO = ["docker", "info"]
CONTAINER_SYNC = [*COMPOSE, "uv", "sync", "--locked"]
HOST_SYNC = ["uv", "sync", "--locked"]
COMPILE = ["uv", "run", "--frozen", "python", "-m", "compileall", "-q", "tools", "configure.py"]


def _refusal(out: str) -> dict:
    assert out.count("\n") == 1 and out.startswith("{"), "stdout is not one JSON line"
    doc = json.loads(out)
    assert doc["event"] == "REFUSED", doc
    return doc


def _fails(argv_prefix: list[str], code: int = 1):
    return (lambda argv: argv[: len(argv_prefix)] == argv_prefix, (code, "", "made-up failure\n"))


@pytest.mark.parametrize(
    ("case", "reason", "words"),
    [
        ("cli 2.1.240", "cli version", "2.1.240"),
        ("cli 3.0.0", "cli version", "major"),
        ("cli unreadable", "cli version", "not a Claude Code version"),
        ("cli fails", "cli version", "exit 1"),
        ("docker info fails", "docker", "Docker"),
        ("container sync fails", "container sync", "uv sync --locked"),
        ("host sync fails", "host sync", "uv sync --locked"),
        ("compile fails", "compile", "compileall"),
        ("asm fails", "asm", "asm"),
    ],
)
def test_preflight_refusals(tmp_path, capsys, case, reason, words):
    runner = Runner()
    versions = {"cli 2.1.240": "2.1.240 (Claude Code)", "cli 3.0.0": "3.0.0 (Claude Code)",
                "cli unreadable": "garbage"}  # fmt: skip
    runner.version = versions.get(case, runner.version)
    if case == "cli fails":
        runner.replies.append(_fails(["claude", "--version"]))
    prefixes = {"docker info fails": DOCKER_INFO, "container sync fails": CONTAINER_SYNC,
                "host sync fails": HOST_SYNC, "compile fails": COMPILE,
                "asm fails": [*HOST_CLI, "asm"]}  # fmt: skip
    if case in prefixes:
        runner.replies.append(_fails(prefixes[case]))
    rig = Rig(tmp_path, runner=runner)
    code, out, _ = rig.drive(capsys, json=True)
    assert code == 2
    doc = _refusal(out)
    assert doc["reason"] == reason
    assert words in doc["detail"]


def test_preflight_refuses_a_worktree(tmp_path, capsys):
    """D-34: git-dir != git-common-dir means a linked worktree, never the main checkout."""
    rig = Rig(tmp_path)
    linked = tmp_path / "linked"
    _git(rig.repo, rig.env, "worktree", "add", "-q", str(linked))
    rig._git = driver.git_runner(linked, env=rig.env)
    code, out, _ = rig.drive(capsys, json=True, repo=linked)
    assert code == 2
    doc = _refusal(out)
    assert doc["reason"] == "worktree" and "main checkout" in doc["detail"]
    assert not rig.runner.calls  # refused before any command


def test_preflight_refuses_a_dirty_tree_naming_the_paths(tmp_path, capsys):
    """F14: dirty means `git status --porcelain` is not empty; the refusal names the paths."""
    rig = Rig(tmp_path)
    _write(rig.repo / "stray.txt", "made up\n")
    _write(rig.repo / "config/ufo2p/README", "changed\n")
    code, out, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 2
    doc = _refusal(out)
    assert doc["reason"] == "dirty"
    assert "stray.txt" in doc["detail"] and "config/ufo2p/README" in doc["detail"]
    assert not rig.runner.calls


def test_preflight_passes_a_clean_main_checkout_on_2_1_302(tmp_path):
    rig = Rig(tmp_path)
    driver.preflight(rig.options(), rig.seams(), check_cli=True)  # raises Refused otherwise
    assert ["claude", "--version"] in rig.runner.calls


def test_dry_run_skips_only_the_cli_version_check(tmp_path, capsys):
    rig = Rig(tmp_path, runner=Runner(version="1.0.0 (Claude Code)"))
    code, _, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 0
    assert not [c for c in rig.runner.calls if c[1:] == ["--version"]]
    for argv in (DOCKER_INFO, CONTAINER_SYNC, HOST_SYNC, COMPILE):
        assert argv in rig.runner.calls, argv


def test_preflight_regenerates_listings_and_drafts(tmp_path, capsys):
    """D-13: the asm listings of both EXEs on the host, then one container ghidra-export
    --drafts call per EXE covering the queue's top picks, all before the first pack."""
    rig = Rig(tmp_path)
    built_at: list[int] = []
    original = rig.packs.for_exe

    def counting(exe):
        pack = original(exe)

        def wrapped(pick, directory):
            built_at.append(len(rig.runner.calls))
            return pack(pick, directory)

        return wrapped

    rig.packs.for_exe = counting
    code, out, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 0
    for exe in EXES:
        assert [*HOST_CLI, "asm", exe, "--json"] in rig.runner.calls
    drafts = rig.commands("ghidra-export")
    assert [call[: len(CONTAINER_UV) + 4] for call in drafts] == [
        [*CONTAINER_UV, "ghidra-export", exe, "--json", "--drafts"] for exe in EXES]  # fmt: skip
    picked = {(p["exe"], p["start"]) for p in json.loads(out)["picks"]}
    asked = {(call[len(CONTAINER_UV) + 1], a) for call in drafts
             for a in call[len(CONTAINER_UV) + 4 :]}  # fmt: skip
    assert picked <= asked
    last_draft = max(i for i, call in enumerate(rig.runner.calls) if "ghidra-export" in call)
    assert built_at and min(built_at) > last_draft
    order = [rig.runner.calls.index(argv) for argv in (HOST_SYNC, COMPILE)]
    assert order == sorted(order)  # the venv is synced before it is compiled


def _ghidra_reply(code: int, out: str, err: str = ""):
    prefix = [*CONTAINER_UV, "ghidra-export"]
    return (lambda argv: argv[: len(prefix)] == prefix, (code, out, err))


MISSING_ONE = '{"path": "asm/x/ghidra", "written": [], "missing": ["0x00010000"], "seconds": 1.0}'


def test_preflight_accepts_exit_1_only_with_missing_drafts_named(tmp_path, capsys):
    """Fix round 1 I1: ghidra-export --json exits 1 when some drafts could not be made; the
    pack works without a draft, so a parseable document with a non-empty `missing` list is
    logged and the run goes on."""
    rig = Rig(tmp_path, runner=Runner(replies=[_ghidra_reply(1, MISSING_ONE)]))
    code, _, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 0


@pytest.mark.parametrize(
    ("code", "out", "err"),
    [
        (1, "", "Traceback (most recent call last):\nreverseapoc.ghidra.GhidraError: made up\n"),
        (1, '{"path": "x", "written": ["0x00010000"], "missing": [], "seconds": 1.0}', ""),
        (1, "not json at all", ""),
        (1, '{"written": [], "missing": "0x00010000"}', ""),
        (2, "", "made-up failure"),
        (125, "", "made-up docker failure"),
    ],
)
def test_preflight_refuses_any_other_drafts_failure(tmp_path, capsys, code, out, err):
    """Fix round 1 I1: exit 1 is also every ghidra-export tool error (a traceback, a missing
    analyzeHeadless) and many docker failures: without a non-empty `missing` list it refuses,
    and so does any other non-zero exit."""
    rig = Rig(tmp_path, runner=Runner(replies=[_ghidra_reply(code, out, err)]))
    exit_code, stdout, _ = rig.drive(capsys, dry_run=True, json=True)
    assert exit_code == 2
    doc = _refusal(stdout)
    assert doc["reason"] == "drafts"
    assert f"exit {code}" in doc["detail"]


def test_json_mode_stdout_is_one_document_and_noise_goes_to_the_log(tmp_path, capsys):
    """F13: every preflight command's stdout and stderr go to build/driver/<run>/preflight.log;
    stdout carries exactly one JSON document."""
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 0
    assert out.count("\n") == 1
    json.loads(out)
    path = rig.repo / "build" / "driver" / RUN / "preflight.log"
    assert path.is_file(), "no preflight.log"
    log = path.read_text(encoding="utf-8")
    assert "noise on stdout" in log and "noise on stderr" in log
    assert "docker info" in log and "compileall" in log


def test_compiled_bytecode_is_not_rewritten_by_an_isolated_import(tmp_path):
    """Why preflight compiles tools/ and configure.py (06-23 security notes): the hooks import
    the package with `python -I`, which ignores PYTHONDONTWRITEBYTECODE. After compileall the
    import writes nothing, so the driver's __pycache__ fingerprint stays still; without it the
    import writes a .pyc (the night would stop)."""
    pkg = tmp_path / "pkg"
    _write(pkg / "mod.py", "VALUE = 1\n")

    def prints() -> dict[str, tuple[int, int]]:
        return {p.relative_to(pkg).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
                for p in pkg.rglob("*") if "__pycache__" in p.parts and p.is_file()}  # fmt: skip

    def isolated_import() -> None:
        code = f"import sys; sys.path.insert(0, {str(pkg)!r}); import mod"
        subprocess.run([sys.executable, "-I", "-c", code], check=True)

    isolated_import()
    assert prints(), "the control: an uncompiled import writes a .pyc"
    for path in pkg.rglob("*.pyc"):
        path.unlink()
    subprocess.run([sys.executable, "-m", "compileall", "-q", str(pkg)], check=True)
    before = prints()
    isolated_import()
    assert prints() == before


def test_remove_containers_filters_by_project_and_prefix(tmp_path):
    prefix = "reverseapoc-attempt-0123abcd-"
    names = f"{prefix}0001\nother-{prefix}0002\n{prefix}0003\n"
    runner = Runner(replies=[(lambda a: a[:2] == ["docker", "ps"], (0, names, ""))])
    rig = Rig(tmp_path, runner=runner)
    deps = driver.real_deps(rig.options(), rig.seams(), _world(rig.packs))
    deps.remove_containers(prefix)
    project = driver.compose_project(rig.repo)
    assert runner.calls == [
        ["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project}",
         "--filter", f"name={prefix}", "--format", "{{.Names}}"],
        ["docker", "rm", "-f", f"{prefix}0001", f"{prefix}0003"],
    ]  # fmt: skip


def test_remove_containers_failure_raises(tmp_path):
    runner = Runner(replies=[(lambda a: a[:2] == ["docker", "ps"], (1, "", "made up\n"))])
    rig = Rig(tmp_path, runner=runner)
    deps = driver.real_deps(rig.options(), rig.seams(), _world(rig.packs))
    with pytest.raises(driver.DriverError):
        deps.remove_containers("reverseapoc-attempt-0123abcd-")


def test_compose_project_is_the_normalized_directory_name():
    assert driver.compose_project(Path("C:/x/ReverseApoc")) == "reverseapoc"
    assert driver.compose_project(Path("/x/My Repo.2")) == "myrepo2"


# --- fix round 1 I2: every preflight-phase error is REFUSED, exit 2, one JSON document ---


def _drive_refused(rig: Rig, capsys, **options) -> dict:
    try:
        code, out, _ = rig.drive(capsys, json=True, **options)
    except Exception as exc:  # noqa: BLE001 - an escape is the defect under test
        pytest.fail(f"run_drive let {type(exc).__name__}: {exc} escape")
    assert code == 2, out
    return _refusal(out)


def test_a_corrupt_difficult_list_is_refused(tmp_path, capsys):
    rig = Rig(tmp_path)
    _write(rig.repo / "build/driver/difficult.json", "not a difficult list\n")
    doc = _drive_refused(rig, capsys, dry_run=True)
    assert "difficult.json" in doc["detail"]


def test_a_malformed_committed_status_table_is_refused(tmp_path, capsys):
    rig = Rig(tmp_path)
    _write(rig.repo / "config/ufo2p/status.csv", "made-up garbage\n")
    _git(rig.repo, rig.env, "add", "--", "config/ufo2p/status.csv")
    _git(rig.repo, rig.env, "commit", "-q", "-m", "a malformed table")
    doc = _drive_refused(rig, capsys, dry_run=True)
    assert "status.csv" in doc["detail"]


def test_a_runner_that_raises_is_refused(tmp_path, capsys):
    rig = Rig(tmp_path)

    def run(argv):
        if list(argv) == DOCKER_INFO:
            raise PermissionError("made-up: access denied")
        return rig.runner(argv)

    doc = _drive_refused(rig, capsys, dry_run=True, seams=dict(run=run))
    assert "PermissionError" in doc["detail"]


def test_a_missing_git_is_refused(tmp_path, capsys):
    rig = Rig(tmp_path)

    def git(args):
        raise FileNotFoundError("made-up: git not found")

    doc = _drive_refused(rig, capsys, dry_run=True, seams=dict(git=git))
    assert "git" in doc["detail"]
    assert not rig.runner.calls


def test_a_failing_pack_in_the_dry_run_is_refused(tmp_path, capsys):
    rig = Rig(tmp_path)

    def broken(exe):
        def pack(pick, directory):
            raise OSError("made-up: disk full")

        return pack

    rig.packs.for_exe = broken
    doc = _drive_refused(rig, capsys, dry_run=True)
    assert "disk full" in doc["detail"]


@pytest.mark.parametrize(("error", "code"),
                         [(PermissionError("made up"), 126), (FileNotFoundError("made up"), 127),
                          (OSError("made up"), 126)])  # fmt: skip
def test_command_runner_maps_every_os_error(tmp_path, monkeypatch, error, code):
    def raising(*args, **kwargs):
        raise error

    monkeypatch.setattr(driver.subprocess, "run", raising)
    try:
        done = driver.command_runner(tmp_path)(["docker", "info"])
    except OSError as exc:
        pytest.fail(f"command_runner let {exc!r} escape")
    assert done.returncode == code
    assert "made up" in done.stderr


def test_git_runner_maps_an_os_error(tmp_path, monkeypatch):
    def raising(*args, **kwargs):
        raise FileNotFoundError("made up: no git")

    monkeypatch.setattr(driver.subprocess, "run", raising)
    try:
        done = driver.git_runner(tmp_path)(["status"])
    except OSError as exc:
        pytest.fail(f"git_runner let {exc!r} escape")
    assert done.returncode == 127
    assert b"no git" in done.stderr


# --- the canary ---

CANARY_DIR = f"build/driver/canary/{RUN}/ufo2p/func_000A3980/attempt-1"
CANARY_UNIT = "src/ufo2p/u_000a34f0.c"
CANARY_TEXT = "/* made-up matched canary unit */\nint canary;\n"


@dataclass
class Launch:
    argv: list[str]
    env: dict
    cwd: Path


PASSING_CHECK = {"n": 1, "exit": 0, "sweep": False, "best_percent": 100.0, "reloc_ok": True,
                 "bytes_ok": True, "splice_ok": True, "sweep_hit": None,
                 "source": "checks/0001.c", "note": "checks/0001.note.json"}  # fmt: skip
CANARY_FUNCTIONS = "config/ufo2p/functions.csv"
CANARY_SIZE = 0xD  # the made-up canary row below, as long as the real one (func_000A3980)
CANARY_ROW = FunctionRow(0x000A3980, 0x000A3980 + CANARY_SIZE, "func_000A3980", "game",
                         "u_000a34f0", "call")  # fmt: skip
CONSUMED_NOTE = {"change": "canary", "why": "canary", "expect": "canary",
                 "observed": {"exit": 0, "objdiff_percent": 100.0, "bytes_differing": 0,
                              "first_va": None, "window_first_row": None,
                              "regions": "regions 0:0"}}  # fmt: skip


def _canary_rig(tmp_path, scenario: str, *, write: str | None = None, after=None,
                check: dict | None = PASSING_CHECK, raises: BaseException | None = None,
                unit: bool = True, note: bool = True) -> Rig:  # fmt: skip
    """A rig whose session is fakeclaude replaying `scenario` through the real run_session,
    writing `write` (repo-relative) like a tool call that went through; `check` is the
    checks.jsonl line the wrapper's `attempt check` would have logged (None: no log) and `note`
    whether it also left the consumed note checks/0001.note.json (07.2-03);
    `after(repo)` runs once the stream ended (a stray the session left); `raises` is raised by
    the session instead. `unit`: HEAD holds the canary's matched unit, include/common.h and its
    functions.csv row, so its view (07-13) has them and its plan has a size (07.2-03)."""
    rig = Rig(tmp_path)
    rig.launches = []
    rig.views = []  # (view unit exists, its bytes, include/ exists) at session time
    if unit:
        _write(rig.repo / CANARY_UNIT, CANARY_TEXT)
        _write(rig.repo / "include" / "common.h", "/* made up */\n")
        write_functions_csv(rig.repo / CANARY_FUNCTIONS, [CANARY_ROW], "UFO2P.EXE")
        _git(rig.repo, rig.env, "add", "--", CANARY_UNIT, "include/common.h", CANARY_FUNCTIONS)
        _git(rig.repo, rig.env, "commit", "-q", "-m", "the canary's matched unit")

    def argv(prompt: str, *, model: str, max_budget_usd: float, max_turns: int):
        rig.prompt = prompt
        rig.asked = (model, max_budget_usd, max_turns)  # 07-30: the canary's session values
        cmd = [sys.executable, str(FAKE), "--scenario", scenario]
        return cmd + (["--write", write] if write else [])

    def session(argv, *, cwd, env, transcript, timeout_s):
        rig.launches.append(Launch(list(argv), dict(env), Path(cwd)))
        view_unit = Path(env.get("REVERSEAPOC_UNIT_FILE", cwd))
        view = Path(env["REVERSEAPOC_ATTEMPT_DIR"]) / "view"
        rig.views.append((view_unit.is_file(), view_unit.read_bytes() if view_unit.is_file()
                          else None, (view / "include").is_dir()))  # fmt: skip
        if raises is not None:
            raise raises
        result = run_session(argv, cwd=cwd, env=env, transcript=transcript, timeout_s=timeout_s)
        attempt_dir = Path(env["REVERSEAPOC_ATTEMPT_DIR"])
        if check is not None:
            _write(attempt_dir / "checks.jsonl", json.dumps(check) + "\n")
        if check is not None and note:
            _write(attempt_dir / "checks" / "0001.note.json", json.dumps(CONSUMED_NOTE) + "\n")
        if after is not None:
            after(Path(cwd))
        return result

    rig.argv, rig.session = argv, session
    return rig


def _canary(rig: Rig, capsys) -> tuple[int, dict]:
    code, out, _ = rig.drive(capsys, canary=True, json=True)
    assert out.count("\n") == 1, "stdout is not one JSON line"
    return code, json.loads(out)


def _failed(doc: dict) -> list[str]:
    return [c["check"] for c in doc.get("checks", []) if not c["ok"]]


def test_canary_pass(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (0, "PASS"), _failed(doc)
    texts = " | ".join(c["check"] for c in doc["checks"])
    for needle in ("config/targets.toml", "tools/x.py", "`ls`", "attempt context",
                   "attempt check", "git status", driver.CANARY_FOREIGN_GIVEUP,
                   "0001.note.json"):  # fmt: skip
        assert needle in texts, needle
    assert len(rig.launches) == 1
    assert not rig.commands("gate")


def test_canary_prompt_asks_for_the_check_timeout_the_hook_requires():
    """Review WR-04: the matching hook denies an attempt check without the Bash tool's timeout
    at hooks.CHECK_TIMEOUT_MS, so the canary's fifth call must ask for exactly that."""
    from reverseapoc import hooks

    step = (f"8. Run the Bash command `{driver.CANARY_CHECK}` with the Bash tool's timeout set "
            f"to {hooks.CHECK_TIMEOUT_MS}.")  # fmt: skip
    assert step in driver.CANARY_PROMPT


def _content(prompt: str, step: str) -> str:
    """The backquoted content the prompt's `step` asks to write."""
    assert step in prompt, step
    return prompt.split(step, 1)[1].split("`", 1)[0]


def test_canary_prompt_writes_plan_and_note(tmp_path):
    """07.2-03 (D-26): in order, the context wrapper, a forbidden session-file Write, a Write of
    plan.json valid for the canary row, a Write of check-note.json, then the check; both files
    named by their absolute attempt-dir paths."""
    from reverseapoc import attempt

    attempt_dir = tmp_path / "attempt-1"
    attempt_dir.mkdir()
    prompt = driver.canary_prompt(attempt_dir, CANARY_SIZE)
    steps = [f"4. Run the Bash command `{driver.CANARY_WRAPPER}`.",
             f"5. Write the file {driver.CANARY_FOREIGN_GIVEUP} with the content `canary`.",
             f"6. Write the file {attempt_dir / 'plan.json'} with the content `",
             f"7. Write the file {attempt_dir / 'check-note.json'} with the content `",
             f"8. Run the Bash command `{driver.CANARY_CHECK}`"]  # fmt: skip
    places = [prompt.index(step) for step in steps]
    assert places == sorted(places)
    assert "exactly these eight tool calls" in prompt
    plan = attempt_dir / "plan.json"
    plan.write_text(_content(prompt, steps[2]), encoding="utf-8")
    regions = attempt.read_plan(plan, CANARY_SIZE)["regions"]
    assert [(r["start"], r["end"]) for r in regions] == [(0, CANARY_SIZE)]
    note = attempt_dir / "check-note.json"
    note.write_text(_content(prompt, steps[3]), encoding="utf-8")
    assert set(attempt.read_check_note(note)) == {"change", "why", "expect"}


@pytest.mark.parametrize("size", [1, 0x3F, 0x40, 0xFF, 0x100, 0x101, 0x180, 0x300])
def test_canary_plan_is_valid_at_every_size(tmp_path, size):
    from reverseapoc import attempt

    plan = tmp_path / "plan.json"
    plan.write_text(driver._canary_plan_text(size), encoding="utf-8")
    assert attempt.read_plan(plan, size)["regions"][-1]["end"] == size


def test_canary_needs_the_consumed_note(tmp_path, capsys):
    """07.2-03 (D-02): a check line without its consumed note checks/0001.note.json is FAIL."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md", note=False)
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any("no consumed note" in text and "0001.note.json" in text
               for text in _failed(doc)), _failed(doc)  # fmt: skip


def test_canary_probes_a_forbidden_session_file(tmp_path, capsys):
    """07.2-03 (T-07.2-09): the canary writes a giveup.json in another run's attempt directory,
    which the hooks deny, and FAILs when that Write went through."""
    from reverseapoc import hooks

    target = driver.CANARY_FOREIGN_GIVEUP
    assert ("Write", target) in driver.CANARY_DENIED
    assert target.startswith("build/driver/") and target.endswith("/giveup.json")
    assert not target.startswith("build/driver/canary/")
    base = f"{CANARY_DIR}"
    assert not hooks.matching_write_allowed(
        target, claim="ufo2p/u_000a34f0", notes=f"{base}/notes.md", tracked=lambda _: False,
        unit_file=f"{base}/view/{CANARY_UNIT}", proposals=f"{base}/proposals.jsonl")
    rig = _canary_rig(tmp_path, "canary_session_file_allowed",
                      write=f"{CANARY_DIR}/context.md")  # fmt: skip
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any(target in text and "NOT denied" in text for text in _failed(doc)), _failed(doc)


@pytest.mark.parametrize("check", [dict(PASSING_CHECK, exit=2, best_percent=None), None])
def test_canary_fails_unless_the_wrapper_check_passed(tmp_path, capsys, check):
    """Rule 2: the canary also runs `attempt check` on the matched claim, so the container
    path of the wrapper (docker compose run -T --name, 06-15's unproven item) is proven and
    the fingerprint check covers it; a check that did not exit 0, or no check log, is FAIL."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md", check=check)
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any("uv run --frozen reverseapoc attempt check" in text for text in _failed(doc))


def test_canary_session_that_raises_is_a_fail(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", raises=RuntimeError("made-up crash"))
    try:
        code, doc = _canary(rig, capsys)
    except RuntimeError as exc:
        pytest.fail(f"run_drive let {exc!r} escape")
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any("made-up crash" in text for text in _failed(doc))


def test_canary_env_names_the_claim_with_absolute_paths(tmp_path, capsys):
    """F12: REVERSEAPOC_CLAIM ufo2p/u_000a34f0, REVERSEAPOC_FUNC func_000A3980, and absolute
    attempt dir and notes under build/driver/canary/; the session runs in the checkout."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    _canary(rig, capsys)
    assert len(rig.launches) == 1
    env, cwd = rig.launches[0].env, rig.launches[0].cwd
    assert env["REVERSEAPOC_CLAIM"] == "ufo2p/u_000a34f0"
    assert env["REVERSEAPOC_FUNC"] == "func_000A3980"
    attempt_dir = Path(env["REVERSEAPOC_ATTEMPT_DIR"])
    assert attempt_dir.is_absolute() and attempt_dir == rig.repo / CANARY_DIR
    assert Path(env["REVERSEAPOC_ATTEMPT_NOTES"]) == attempt_dir / "notes.md"
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert cwd == rig.repo
    for words in ("config/targets.toml", "tools/x.py", "`ls`",
                  "uv run --frozen reverseapoc attempt context",
                  "uv run --frozen reverseapoc attempt check",
                  str(attempt_dir / "plan.json"),
                  str(attempt_dir / "check-note.json")):  # fmt: skip
        assert words in rig.prompt, words


def test_canary_runs_in_view_mode(tmp_path, capsys):
    """07-13 (D-24): the canary's session gets a view of HEAD like any session (the view
    unit, proposals.jsonl, kind matching, under build/driver/canary/), and its PASS rule is
    unchanged: the forbidden writes must still be denied."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (0, "PASS"), _failed(doc)
    env = rig.launches[0].env
    attempt_dir = rig.repo / CANARY_DIR
    view_unit = attempt_dir / "view" / CANARY_UNIT
    assert env["REVERSEAPOC_UNIT_FILE"] == str(view_unit)
    assert env["REVERSEAPOC_PROPOSALS"] == str(attempt_dir / "proposals.jsonl")
    assert env["REVERSEAPOC_SESSION_KIND"] == "matching"
    assert rig.views == [(True, CANARY_TEXT.encode(), True)]
    assert (attempt_dir / driver.VIEW_HEAD).is_file()


def test_canary_pass_rule_still_needs_the_denials(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_fail", write="tools/x.py")
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert rig.views and rig.views[0][0]


def test_canary_refuses_without_its_matched_unit(tmp_path, capsys):
    """The canary's view needs HEAD's matched unit: without it the canary is refused before any
    session (exit 2), never scaffolded."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md", unit=False)
    code, out, _ = rig.drive(capsys, canary=True, json=True)
    assert code == 2
    assert rig.launches == []
    assert CANARY_UNIT in out


def test_canary_fail(tmp_path, capsys):
    """The tools/x.py Write was not denied (and it landed): FAIL naming it, exit 1."""
    rig = _canary_rig(tmp_path, "canary_fail", write="tools/x.py")
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    failed = _failed(doc)
    assert any("tools/x.py" in text and "denied" in text for text in failed), failed
    assert any("git status" in text and "tools/x.py" in text for text in failed), failed


def test_canary_wrapper_denied(tmp_path, capsys):
    """F12: the attempt wrapper call denied (and no context.md): FAIL naming the wrapper."""
    rig = _canary_rig(tmp_path, "canary_wrapper_denied")
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    failed = " | ".join(_failed(doc))
    assert "uv run --frozen reverseapoc attempt context" in failed
    assert "context.md" in failed


def _check_refused_stream(reason: str, *, retry_denied: bool = False) -> list[dict]:
    """canary_pass's synthetic stream with one more `attempt check` before its own: a call
    with no Bash timeout, denied with `reason` (a permission_denials entry and an is_error
    tool_result, as the real CLI reports a hook denial). `retry_denied`: the later call, the
    one with the timeout, is denied with the same reason too."""
    lines = (FAKE.parent / "fixtures" / "stream" / "canary_pass.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in lines.splitlines()]
    call = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_canary_09", "name": "Bash",
         "input": {"command": driver.CANARY_CHECK}}]}}  # fmt: skip
    events[-3:-3] = [call, _hook_denied("toolu_canary_09", reason)]
    denied = ["toolu_canary_09", "toolu_canary_05"] if retry_denied else ["toolu_canary_09"]
    if retry_denied:
        events[-2] = _hook_denied("toolu_canary_05", reason)
    events[-1]["permission_denials"] += [{"tool_name": "Bash", "tool_use_id": use,
                                          "tool_input": {"command": driver.CANARY_CHECK}}
                                         for use in denied]  # fmt: skip
    return events


def _hook_denied(use: str, reason: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": use, "content": reason, "is_error": True}]}}


def _check_lines(tmp_path, events: list[dict]) -> list[tuple[bool, str]]:
    """The canary's PASS/FAIL lines about the `attempt check` wrapper for `events`."""
    checks = driver._Checks()
    options = DriveOptions(repo=tmp_path, run_id=RUN, canary=True)
    driver._canary_checks(options, events, tmp_path / "attempt-1", checks,
                          model="claude-opus-5-5")  # fmt: skip
    shown = f"the attempt wrapper `{driver.CANARY_CHECK}`"
    return [(ok, text) for ok, text in checks.lines if text.startswith(shown)]


def test_canary_check_refused_for_its_timeout_then_allowed_passes(tmp_path):
    """Canary 2026-11-10 (muse-spark-open): `attempt check` without the Bash timeout, refused
    by the hook's timeout rule, then rerun with it and allowed, is the hook working: an
    informational PASS line, never `was denied`."""
    events = _check_refused_stream(hooks.CHECK_TIMEOUT_DENIAL.reason)
    lines = _check_lines(tmp_path, events)
    assert all(ok for ok, text in lines if "allowed" in text or "denied" in text), lines
    assert any(ok and "first refused for its missing timeout, then allowed" in text
               for ok, text in lines), lines  # fmt: skip
    assert not any("was denied" in text for _, text in lines), lines


def test_canary_check_denied_for_another_reason_fails(tmp_path):
    """Any denial of the wrapper but the hook's timeout rule still FAILs, even when a later
    call of it was allowed."""
    events = _check_refused_stream("reverseapoc hooks: a made-up rule")
    lines = _check_lines(tmp_path, events)
    assert any(not ok and "was denied" in text for ok, text in lines), lines


def test_canary_check_only_ever_refused_for_its_timeout_fails(tmp_path):
    """A wrapper that was only ever denied FAILs, even when every denial is the timeout rule."""
    events = _check_refused_stream(hooks.CHECK_TIMEOUT_DENIAL.reason, retry_denied=True)
    lines = _check_lines(tmp_path, events)
    assert any(not ok and "was denied" in text for ok, text in lines), lines


def test_canary_fails_on_an_init_problem(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(driver, "MIN_CLI_VERSION", (2, 1, 400))
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    rig.runner.version = "2.1.400 (Claude Code)"
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any("below the minimum 2.1.400" in text for text in _failed(doc))


def test_canary_fails_on_an_unknown_event_type_carrying_an_error(tmp_path, capsys):
    """06-23 notes: unknown event types stay ignored by the driver, so the canary proves none
    of them carries an error on the real CLI."""
    rig = _canary_rig(tmp_path, "canary_unknown_error", write=f"{CANARY_DIR}/context.md")
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any("made_up_event" in text for text in _failed(doc))


@pytest.mark.parametrize("stray", [".venv/Lib/site-packages/x.pth", "tools/__pycache__/x.pyc"])
def test_canary_fails_when_the_session_changes_what_the_driver_fingerprints(
    tmp_path, capsys, stray
):
    """06-23 notes: the night stops on any change to the venv, a pinned file or a repo
    __pycache__ during a session, so the canary proves a real session (its hooks and its
    wrapper call) changes none of them."""

    def leave(repo: Path) -> None:
        _write(repo / stray, "made up\n")

    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md", after=leave)
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any(stray in text for text in _failed(doc)), _failed(doc)


def test_canary_text_mode_prints_pass_and_fail_lines(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_fail", write="tools/x.py")
    code, out, _ = rig.drive(capsys, canary=True)
    assert code == 1
    lines = out.splitlines()
    assert lines[-1:] == ["CANARY FAIL"]
    assert any(line.startswith("PASS: ") for line in lines)
    assert any(line.startswith("FAIL: ") and "tools/x.py" in line for line in lines)


def test_canary_runs_the_preflight_first(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    rig.runner.version = "2.1.240 (Claude Code)"
    code, out, _ = rig.drive(capsys, canary=True, json=True)
    assert code == 2 and _refusal(out)["reason"] == "cli version"
    assert not rig.launches


# --- fix round 1: canary minors ---


def test_canary_fails_when_head_moves(tmp_path, capsys):
    """A commit leaves `git status` clean: the canary also compares HEAD before and after."""
    holder = {}

    def commit(repo: Path) -> None:
        _git(repo, holder["env"], "commit", "-q", "--allow-empty", "-m", "a made-up commit")

    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md", after=commit)
    holder["env"] = rig.env
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any("HEAD" in text for text in _failed(doc)), _failed(doc)


def test_canary_removes_its_containers_by_the_attempt_prefix(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    _canary(rig, capsys)
    prefix = driver.attempt.container_prefix(rig.repo / CANARY_DIR)
    assert [c for c in rig.runner.calls if c[:2] == ["docker", "ps"]] == [
        ["docker", "ps", "-a", "--filter",
         f"label=com.docker.compose.project={driver.compose_project(rig.repo)}",
         "--filter", f"name={prefix}", "--format", "{{.Names}}"]]  # fmt: skip


def test_canary_names_a_failed_container_removal(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    rig.runner.replies.append((lambda a: a[:2] == ["docker", "ps"], (1, "", "made up\n")))
    code, doc = _canary(rig, capsys)
    assert (code, doc.get("canary")) == (1, "FAIL")
    assert any("containers" in text for text in _failed(doc)), _failed(doc)


# --- 06-26 canary1: every check prints a line (docs/workflow.md, Canary) ---

CONTAINERS_PASS = "the attempt's containers were removed"
UNKNOWN_PASS = "no unknown stream event carries an error"


def _passed(doc: dict) -> list[str]:
    return [c["check"] for c in doc.get("checks", []) if c["ok"]]


def test_canary_pass_prints_the_containers_and_unknown_event_lines(tmp_path, capsys):
    """canary1: the containers check and the unknown-event check printed nothing on success,
    against "each check prints one PASS: or FAIL: line"."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    code, out, _ = rig.drive(capsys, canary=True)
    assert code == 0
    lines = out.splitlines()
    assert f"PASS: {CONTAINERS_PASS}" in lines
    assert f"PASS: {UNKNOWN_PASS}" in lines


def test_canary_failed_container_removal_has_no_containers_pass_line(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    rig.runner.replies.append((lambda a: a[:2] == ["docker", "ps"], (1, "", "made up\n")))
    _, doc = _canary(rig, capsys)
    assert CONTAINERS_PASS not in _passed(doc)
    assert UNKNOWN_PASS in _passed(doc)


def test_canary_unknown_event_error_has_no_unknown_event_pass_line(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_unknown_error", write=f"{CANARY_DIR}/context.md")
    _, doc = _canary(rig, capsys)
    assert UNKNOWN_PASS not in _passed(doc)
    assert CONTAINERS_PASS in _passed(doc)


def test_canary_refuses_a_reused_run_id(tmp_path, capsys):
    """A reused --run ID would let an earlier canary's context.md or checks.jsonl pass."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    (rig.repo / CANARY_DIR).mkdir(parents=True)
    code, out, _ = rig.drive(capsys, canary=True, json=True)
    assert code == 2 and _refusal(out)["reason"] == "run id"
    assert not rig.launches


@pytest.mark.parametrize("verb", ["status", "for-each-ref"])
def test_a_canary_error_after_the_session_is_a_fail_not_a_refusal(tmp_path, capsys, verb):
    """Fix round 2: once the session ran, exit 2 ("never started") would be wrong. An error
    while the canary measures the tree is a FAIL line after the lines gathered so far, exit 1."""
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    real_git = rig.git

    def git(args):
        if rig.launches and verb in args:
            return subprocess.CompletedProcess(list(args), 128, b"", b"fatal: made up\n")
        return real_git(args)

    code, out, _ = rig.drive(capsys, canary=True, json=True, seams=dict(git=git))
    assert out.count("\n") == 1, "stdout is not one JSON line"
    doc = json.loads(out)
    assert (code, doc.get("event"), doc.get("canary")) == (1, None, "FAIL")
    texts = [c["check"] for c in doc["checks"]]
    assert any(c["ok"] and c["check"].startswith("init:") for c in doc["checks"]), texts
    assert any("made up" in text for text in _failed(doc)), texts


def test_a_canary_error_after_the_session_ends_the_text_with_canary_fail(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    real_git = rig.git

    def git(args):
        if rig.launches and "for-each-ref" in args:
            raise RuntimeError("made-up git crash")
        return real_git(args)

    code, out, _ = rig.drive(capsys, canary=True, seams=dict(git=git))
    assert code == 1
    lines = out.splitlines()
    assert lines[-1:] == ["CANARY FAIL"]
    assert any(line.startswith("FAIL: ") and "made-up git crash" in line for line in lines)


# ---- Task 3: the end-of-run checks (D-24, D-23) ----

NINJA_SCRIPT = "uv run --frozen python configure.py && ninja -t clean && ninja verify"
NINJA_VERIFY = [*COMPOSE, "bash", "-lc", NINJA_SCRIPT]
GATE_ALL = [*CONTAINER_UV, "gate", "--all", "--json"]


def _ordered_night(tmp_path, runner: Runner):
    """A night (06-23's harness) with nothing to do, whose end-of-run checks run through
    driver.finish and `runner`; `events` interleaves the runner's and git's calls."""
    night = Night(tmp_path / "night", picks=())
    events: list[tuple[str, list[str]]] = []
    night.on_git = lambda argv: events.append(("git", argv))

    def run(argv):
        events.append(("run", list(argv)))
        return runner(argv)

    run_dir = night.repo / "build" / "driver" / NIGHT_RUN
    report = night.run(end_of_run=lambda: driver.finish(run, run_dir=run_dir))
    return night, report, events, run_dir


def test_end_of_run_order(tmp_path):
    night, report, events, run_dir = _ordered_night(tmp_path, Runner())
    runs = [argv for kind, argv in events if kind == "run"]
    assert runs == [NINJA_VERIFY, GATE_ALL]
    gate_at = next(i for i, (kind, argv) in enumerate(events) if argv == GATE_ALL)
    commit_at = next(i for i, (kind, argv) in enumerate(events)
                     if kind == "git" and "commit" in argv)  # fmt: skip
    assert gate_at < commit_at
    assert night.commits() == ["chore(driver): attempt log"]
    ended = night.kinds("run")[-1]
    assert (ended["event"], ended["checks_failed"]) == ("ENDED", [])
    assert report.exit_code == 0
    for name in ("end-ninja-verify.log", "end-gate-all.log"):
        log = (run_dir / name).read_text(encoding="utf-8")
        assert "noise on stdout" in log and "noise on stderr" in log, name


@pytest.mark.parametrize(
    ("failing", "expected"),
    [(NINJA_VERIFY, ["ninja verify exit 1"]), (GATE_ALL, ["gate --all exit 1"])],
)
def test_a_failing_end_of_run_check_is_recorded_and_exits_1(tmp_path, failing, expected):
    runner = Runner(replies=[(lambda a: a == failing, (1, "", "made-up failure\n"))])
    night, report, events, _ = _ordered_night(tmp_path, runner)
    assert [argv for kind, argv in events if kind == "run"] == [NINJA_VERIFY, GATE_ALL]
    ended = night.kinds("run")[-1]
    assert (ended["event"], ended["checks_failed"]) == ("ENDED", expected)
    assert report.exit_code == 1
    assert night.commits() == ["chore(driver): attempt log"]


def test_real_deps_wire_finish_as_the_end_of_run(tmp_path):
    rig = Rig(tmp_path)
    deps = driver.real_deps(rig.options(), rig.seams(), _world(rig.packs))
    assert list(deps.end_of_run()) == []
    assert rig.runner.calls == [NINJA_VERIFY, GATE_ALL]
    assert (rig.repo / "build" / "driver" / RUN / "end-gate-all.log").is_file()


# ---- quick 261026-9ue: drive timestamps (every console line stamped [HH:MM:SS]) ----

CONSOLE_START = datetime(2026, 10, 26, 21, 4, 5)  # made up


def _fixed_now() -> datetime:
    return CONSOLE_START


@dataclass
class _Ticks:
    """A clock one second later on each reading, from CONSOLE_START."""

    k: int = 0

    def __call__(self) -> datetime:
        now = CONSOLE_START + timedelta(seconds=self.k)
        self.k += 1
        return now


@dataclass
class _Peek:
    """A runner that records, for each command, what stderr received since the previous
    command started, then answers through `inner`."""

    capsys: object
    inner: Runner
    seen: list = field(default_factory=list)

    def __call__(self, argv) -> subprocess.CompletedProcess:
        self.seen.append((list(argv), self.capsys.readouterr().err))
        return self.inner(argv)


DRAFT_NOTE = "drive: ufo2p: no Ghidra draft for 0x00010000; their packs have none"


def test_console_stamps_each_preflight_line_when_it_prints(tmp_path, capsys):
    rig = Rig(tmp_path, runner=Runner(replies=[_ghidra_reply(1, MISSING_ONE)]))
    code, out, err = rig.drive(capsys, dry_run=True, seams=dict(now=_Ticks()))
    assert code == 0
    lines = err.splitlines()
    assert lines[0] == "[21:04:05] drive: $ docker info"
    for i, line in enumerate(lines):
        assert line.startswith((CONSOLE_START + timedelta(seconds=i)).strftime("[%H:%M:%S] ")
                               + "drive: "), line  # fmt: skip
    assert any(line.endswith(DRAFT_NOTE) for line in lines)
    assert not [line for line in out.splitlines() if line.startswith("[")]


def test_console_preflight_line_prints_when_the_command_starts(tmp_path, capsys):
    rig = Rig(tmp_path, runner=Runner(replies=[_ghidra_reply(1, MISSING_ONE)]))
    peek = _Peek(capsys, rig.runner)
    code, out, err = rig.drive(capsys, dry_run=True, seams=dict(run=peek, now=_fixed_now))
    assert code == 0
    assert peek.seen[0][0] == ["docker", "info"]
    for argv, held in peek.seen:
        assert held.endswith(f"[21:04:05] drive: $ {' '.join(argv)}\n"), (argv, held)
        assert held.count("drive: $ ") == 1, (argv, held)
    assert any(DRAFT_NOTE in held for _, held in peek.seen)
    assert "drive: $ " not in err


def test_console_stamp_stays_out_of_json_and_preflight_log(tmp_path, capsys):
    rig = Rig(tmp_path / "text")
    code, _, _ = rig.drive(capsys, dry_run=True, seams=dict(now=_fixed_now))
    assert code == 0
    log = (rig.repo / "build" / "driver" / RUN / "preflight.log").read_text(encoding="utf-8")
    assert "[21:04:05]" not in log
    assert log.count("$ docker info\n") == 1
    assert ("$ docker info\nexit 0\n--- stdout\nnoise on stdout\n\n--- stderr\n"
            "noise on stderr\n") in log  # fmt: skip
    rig = Rig(tmp_path / "json")
    code, out, err = rig.drive(capsys, dry_run=True, json=True, seams=dict(now=_fixed_now))
    assert code == 0
    assert out.count("\n") == 1
    json.loads(out)
    assert "[21:04:05]" not in out
    assert err == ""


def test_console_clock_is_local_time_by_default(tmp_path):
    assert driver.stamp(datetime(2026, 10, 26, 3, 7, 9)) == "[03:07:09] "
    assert driver.stamp(datetime(2026, 10, 26, 23, 59, 59)) == "[23:59:59] "
    assert driver.default_seams(tmp_path).now == datetime.now
    assert driver.STAMP_FORMAT == "[%H:%M:%S] "


def test_console_real_deps_say_is_stamped_on_stderr_in_text_mode_only(tmp_path, capsys):
    rig = Rig(tmp_path)
    deps = driver.real_deps(rig.options(), rig.seams(now=_fixed_now), _world(rig.packs))
    deps.say("ufo2p func_00010010 attempt 1/3: started")
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "[21:04:05] drive: ufo2p func_00010010 attempt 1/3: started\n"
    deps = driver.real_deps(rig.options(json=True), rig.seams(now=_fixed_now), _world(rig.packs))
    deps.say("ufo2p func_00010010 attempt 1/3: started")
    assert capsys.readouterr() == ("", "")


def test_console_end_of_run_names_each_check_before_it_runs(tmp_path, capsys):
    rig = Rig(tmp_path / "text")
    peek = _Peek(capsys, rig.runner)
    deps = driver.real_deps(rig.options(), rig.seams(run=peek, now=_fixed_now), _world(rig.packs))
    capsys.readouterr()
    assert list(deps.end_of_run()) == []
    assert peek.seen == [(NINJA_VERIFY, "[21:04:05] drive: end of run: ninja verify: started\n"),
                         (GATE_ALL, "[21:04:05] drive: end of run: gate --all: started\n")]
    assert capsys.readouterr().err == ""
    rig = Rig(tmp_path / "json")
    peek = _Peek(capsys, rig.runner)
    deps = driver.real_deps(rig.options(json=True), rig.seams(run=peek, now=_fixed_now),
                            _world(rig.packs))  # fmt: skip
    capsys.readouterr()
    assert list(deps.end_of_run()) == []
    assert [argv for argv, _ in peek.seen] == [NINJA_VERIFY, GATE_ALL]
    assert all(held == "" for _, held in peek.seen)
    assert capsys.readouterr() == ("", "")


def test_console_night_summary_is_stamped(tmp_path, capsys):
    rig = Rig(tmp_path)
    code, out, err = rig.drive(capsys, max_sessions=0, seams=dict(now=_fixed_now))
    assert code == 0
    assert out == "[21:04:05] ENDED max sessions: 0 sessions, 0 matched\n"
    lines = err.splitlines()
    assert all(line.startswith("[21:04:05] drive: ") for line in lines), lines
    assert lines[-2:] == ["[21:04:05] drive: end of run: ninja verify: started",
                          "[21:04:05] drive: end of run: gate --all: started"]


def test_console_night_json_is_one_unstamped_document(tmp_path, capsys):
    rig = Rig(tmp_path)
    code, out, err = rig.drive(capsys, max_sessions=0, json=True, seams=dict(now=_fixed_now))
    assert code == 0
    assert out.count("\n") == 1
    doc = json.loads(out)
    assert (doc["event"], doc["reason"], doc["exit_code"]) == ("ENDED", "max sessions", 0)
    assert "[21:04:05]" not in out
    assert err == ""


@pytest.mark.parametrize("as_json", [False, True])
def test_the_night_summary_reports_what_it_parked(tmp_path, capsys, monkeypatch, as_json):
    """Quick 261109-gzu: a night that parked 2 functions ends its summary line with
    `, 2 parked`, and the --json document carries `parked`."""
    rig = Rig(tmp_path)

    def fake_drive(config, deps, *, lock=None):
        return driver.DriveReport(driver.ENDED, driver.MAX_SESSIONS, 5, 1, parked=2)

    monkeypatch.setattr(driver, "drive", fake_drive)
    code, out, _ = rig.drive(capsys, json=as_json, seams=dict(now=_fixed_now))
    assert code == 0
    if as_json:
        assert json.loads(out)["parked"] == 2
    else:
        assert out == "[21:04:05] ENDED max sessions: 5 sessions, 1 matched, 2 parked\n"


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("dirty", "[21:04:05] reverseapoc drive: refused (dirty): the working tree is dirty"),
        ("run id", "[21:04:05] reverseapoc drive: refused (run id): "),
    ],
)
def test_console_text_refusal_is_stamped(tmp_path, capsys, case, expected):
    rig = Rig(tmp_path)
    if case == "dirty":
        _write(rig.repo / "stray.txt", "made up\n")
        code, out, err = rig.drive(capsys, dry_run=True, seams=dict(now=_fixed_now))
    else:
        code, out, err = rig.drive(capsys, run_id="bad id", seams=dict(now=_fixed_now))
    assert (code, out) == (2, "")
    lines = err.splitlines()
    assert len(lines) == 1, lines
    assert lines[0].startswith(expected), lines[0]


def test_console_canary_check_lines_and_verdict_stay_unstamped(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    code, out, err = rig.drive(capsys, canary=True, seams=dict(now=_fixed_now))
    assert code == 0, out
    lines = out.splitlines()
    assert lines[-1] == "CANARY PASS"
    assert all(line.startswith(("PASS: ", "FAIL: ", "CANARY ")) for line in lines), lines
    assert not [line for line in lines if line.startswith("[")]
    assert all(line.startswith("[21:04:05] drive: ") for line in err.splitlines())


def test_console_canary_session_start_line_prints_before_the_session(tmp_path, capsys):
    held = []

    def peek(repo):
        held.append(capsys.readouterr().err)

    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md", after=peek)
    code, out, err = rig.drive(capsys, canary=True, seams=dict(now=_fixed_now))
    assert code == 0, out
    assert len(held) == 1
    assert held[0].splitlines()[-1] == ("[21:04:05] drive: canary: ufo2p func_000A3980 session: "
                                        "started (timeout 1200 s)")  # fmt: skip
    assert (held[0] + err).count("session: started") == 1
    assert out.splitlines()[-1] == "CANARY PASS"


# ---- 07.2-06 (D-17, D-26): the night model and the hold run ----

HAIKU = "claude-haiku-5-5"


def _held_picks(count: int = 3) -> tuple[Pick, ...]:
    from test_driver import START, UNIT

    return tuple(Pick("ufo2p", START + 0x10 * i, f"func_{START + 0x10 * i:08X}", UNIT, 20, 100 + i)
                 for i in range(count))  # fmt: skip


def _tracked(night: Night) -> dict[str, str]:
    """src/, include/ and config/ as git sees them now: path -> blob of the working tree."""
    out = night.git("ls-files", "-s", "--", "src", "include", "config")
    paths = [line.split("\t", 1)[1] for line in out.splitlines()]
    return {p: (night.repo / p).read_text(encoding="utf-8") for p in paths}


def test_night_model_hold_run(tmp_path):
    """D-17: three picks on Haiku under --hold: one session each although the passes allow
    three, every record a hold run on Haiku, HOLD_EXACT for the plain exit-0 check, PARTIAL or
    GAVE_UP by best percent for the others; the HELD marker; no lint, gate or gate --partial,
    src/ and status.csv unchanged, and the records still committed."""
    from test_driver import Sess, check_line

    sessions = [Sess(checks=(check_line(1, 80.0), check_line(2, 100.0, exit_code=0))),
                Sess(checks=(check_line(1, 55.0),)), Sess(checks=(check_line(1, None),))]
    night = Night(tmp_path, sessions=sessions, picks=_held_picks(), gate_exits=[0, 0, 0])
    before = _tracked(night)
    report = night.run(config={"night_model": HAIKU, "hold": True})
    assert report.event == "ENDED", report.detail
    assert len(night.launched) == 3
    records = night.kinds("attempt")
    assert [r["outcome"] for r in records] == ["HOLD_EXACT", "PARTIAL", "GAVE_UP"]
    assert {(r["model_requested"], r["hold_run"]) for r in records} == {(HAIKU, True)}
    assert [r["attempt"] for r in records] == [1, 1, 1]
    assert (night.repo / "build" / "driver" / NIGHT_RUN / driver.HOLD_RUN_MARKER).is_file()
    assert driver.HOLD_RUN_MARKER == "HELD"
    assert night.gate_calls == [] and night.partial_calls == [] and night.lint_calls == []
    assert _tracked(night) == before
    assert not [s for s in night.commits() if s.startswith("feat(")]
    assert night.commits() == [driver.LOG_SUBJECT]
    assert report.matched == 0


def test_night_model_without_hold_asks_for_that_model(tmp_path):
    """--night-model alone: every session of the matching night asks for the model, with the
    per-session budget a non-Fable model takes."""
    from test_driver import Sess

    night = Night(tmp_path, sessions=[Sess()], gate_exits=[1])
    night.run(config={"night_model": HAIKU, "attempts_per_function": 1})
    record = night.kinds("attempt")[0]
    assert (record["model_requested"], record["budget_usd"], record["hold_run"]) == (
        HAIKU, 5, False)  # fmt: skip
    assert night.launched[0].argv[night.launched[0].argv.index("--model") + 1] == HAIKU


def test_hold_never_matched(tmp_path):
    """D-26: a hold-run check that exited 0 is HOLD_EXACT, never MATCHED, and no match commit
    is made, although the gate would have passed."""
    from test_driver import Sess, check_line

    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 100.0, exit_code=0),))],
                  gate_exits=[0])  # fmt: skip
    report = night.run(config={"hold": True})
    record = night.kinds("attempt")[0]
    assert (record["outcome"], record["hold_run"], record["gate"]) == ("HOLD_EXACT", True, None)
    assert report.matched == 0 and night.gate_calls == []
    assert not [s for s in night.commits() if s.startswith("feat(")]


def test_hold_limit_salvage_lands_nothing(tmp_path):
    """A LIMIT session under --hold that changed its unit is reset unjudged (no lint, no gate);
    the relaunch is the attempt, recorded once."""
    from test_driver import Sess, check_line

    sessions = [Sess("rate_limit"), Sess(checks=(check_line(1, 100.0, exit_code=0),))]
    night = Night(tmp_path, sessions=sessions, gate_exits=[0, 0])
    report = night.run(config={"hold": True})
    assert report.event == "ENDED", report.detail
    assert len(night.launched) == 2 and night.sleeps == [60]
    assert night.gate_calls == [] and night.lint_calls == []
    assert [r["outcome"] for r in night.kinds("attempt")] == ["HOLD_EXACT"]
    assert len(night.kinds("limit")) == 1
    assert not [s for s in night.commits() if s.startswith("feat(")]


def test_run_drive_hands_the_night_model_and_hold_to_the_night(tmp_path, capsys, monkeypatch):
    seen = []

    def fake_drive(config, deps, *, lock=None):
        seen.append(config)
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    monkeypatch.setattr(driver, "drive", fake_drive)
    code, _, _ = Rig(tmp_path).drive(capsys, json=True, night_model=HAIKU, hold=True)
    assert code == 0
    assert (seen[0].night_model, seen[0].hold) == (HAIKU, True)


# ---- 07.2-06 Task 3 (D-17, D-26): --land-held ----

SONNET = "claude-sonnet-5-5"
LAND_RUN = "land1"
HAIKU_COAUTHOR = "Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"
CALLEE = 0x00020010  # a function of another unit the held C calls (made up)
CALLEE_NAME = f"func_{CALLEE:08X}"


def _held_c(value: int) -> str:
    from test_driver import FUNC

    return f'#include "common.h"\n\nint {FUNC}(void)\n{{\n    return {value};\n}}\n'


def _table_night(tmp_path: Path, **over) -> Night:
    """A Night whose status tables are real (empty) ones, so the landing can read what is
    matched; no pick of its own."""
    from reverseapoc import status
    from test_driver_records import _commit

    night = Night(tmp_path, picks=(), **over)
    _commit(night, {f"config/{exe}/status.csv": status.format_status([]) for exe in EXES})
    return night


def _table_gate(night: Night):
    """The container gate in miniature on real status tables: on exit 0 the claimed row is
    written matched (sorted, as gate writes it) and the feed changes."""
    from reverseapoc import status
    from test_driver import SHA_TACP, SHA_UFO2P

    def gate(pick: Pick, attempts: int) -> driver.GateRun:
        night.gate_calls.append((pick, attempts))
        code = night.gate_exits.pop(0) if night.gate_exits else 1
        written = []
        if code == 0:
            path = night.repo / f"config/{pick.exe}/status.csv"
            row = status.StatusRow(pick.start, pick.name, pick.unit, status.MATCHED, 100.0,
                                   attempts, "0" * 64, "2026-11-09")  # fmt: skip
            rows = sorted([*status.read_status(path), row], key=lambda r: r.start)
            path.write_text(status.format_status(rows), encoding="utf-8", newline="\n")
            _write(night.repo / "decomphub.progress.json", '{"matched": 1}\n')
            written.append({"path": path.relative_to(night.repo).as_posix(),
                            "start": f"0x{pick.start:08X}", "name": pick.name,
                            "unit": pick.unit, "status": "matched"})  # fmt: skip
        doc = {"ok": code == 0, "written": written,
               "checks": [{"splice": [{"exe": "UFO2P.EXE", "sha1": SHA_UFO2P},
                                      {"exe": "TACP.EXE", "sha1": SHA_TACP}]}]}  # fmt: skip
        return driver.GateRun(code, doc)

    return gate


def _hold_attempt(night: Night, run: str, n: int, *, cost: float, model: str = HAIKU,
                  text: str | None = None, outcome: str = "HOLD_EXACT",
                  start: int | None = None, tokens: dict | None = None,
                  change: dict | None = None) -> dict:  # fmt: skip
    """One hold-run attempt of FUNC (or of the function at `start`): its committed record (to
    commit) and its attempt directory, with a 60% check, then a plain check that exited 0 on
    `text`, and the view head (HEAD now). Quick 261110-f30: `tokens` replaces the record's
    tokens, and `change` sets other record fields last (backend, harness, model)."""
    from test_attempts_schema import _attempt_v3
    from test_driver import START, UNIT, check_line

    start = START if start is None else start
    func = f"func_{start:08X}"
    directory = night.repo / "build" / "driver" / run / "ufo2p" / func / f"attempt-{n}"
    lines = (check_line(1, 60.0), check_line(2, 100.0, exit_code=0))
    for line, body in zip(lines, ("/* made-up 60% */\n", text or _held_c(1)), strict=True):
        _write(directory / line["source"], body)
    _write(directory / "checks.jsonl", "".join(json.dumps(line) + "\n" for line in lines))
    _write(directory / driver.VIEW_HEAD, night.git("rev-parse", "HEAD").strip() + "\n")
    _write(night.repo / "build" / "driver" / run / driver.HOLD_RUN_MARKER, "hold run\n")
    record = _attempt_v3()
    record.update(run=run, exe="ufo2p", start=f"0x{start:08X}", function=func, unit=UNIT,
                  attempt=n, outcome=outcome, hold_run=True, cost_usd=cost,
                  model_requested=model, model=model, gate=None, **{"pass": 1})  # fmt: skip
    if tokens is not None:
        record["tokens"] = dict(tokens)
    record.update(change or {})
    return record


def _commit_log(night: Night, records: list[dict]) -> None:
    from test_driver import LOG
    from test_driver_records import _commit, _lines

    _commit(night, {LOG: _lines(records)}, "made-up hold-run records")


def _land(night: Night, *runs: str, run_id: str = LAND_RUN) -> driver.DriveReport:
    return night.run(config={"run_id": run_id, "land_held": runs}, gate=_table_gate(night))


def _new(night: Night, before: int, kind: str) -> list[dict]:
    return [r for r in night.records()[before:] if r["kind"] == kind]


SONNET_COAUTHOR = "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
OPUS_COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
LUNA_COAUTHOR = "Co-Authored-By: GPT-6 Luna <noreply@openai.com>"


def test_land_held_cheapest_arm(tmp_path):
    """Two hold runs matched FUNC exactly; on equal tokens the cheaper one at list price
    (Haiku against Sonnet; quick 261110-f30) lands its exit-0 checks/NNNN.c through the land,
    lint and gate: one match commit credited to Haiku, then to Sonnet, which held it exact too,
    one MATCHED landing record naming the attempt and the commit, no attempt record, and the
    cost is counted once (in the held records)."""
    from reverseapoc import stats
    from test_driver import LOG, MATCH_SUBJECT, UNIT_REL

    night = _table_night(tmp_path, gate_exits=[0])
    _commit_log(night, [_hold_attempt(night, "spike012-haiku", 1, cost=0.10),
                        _hold_attempt(night, "spike012-sonnet", 1, cost=0.90, model=SONNET,
                                      text=_held_c(2))])  # fmt: skip
    before = len(night.records())
    cost = stats.collect(night.repo, night.repo / LOG, night.repo / "config",
                         runs=["spike012-*"]).data["totals"]["cost_usd"]  # fmt: skip
    report = _land(night, "spike012-*")
    assert (report.event, report.matched, report.sessions) == ("ENDED", 1, 0), report.detail
    assert [s for s in night.commits() if s.startswith("feat(")] == [MATCH_SUBJECT]
    assert night.file_at("feat(", UNIT_REL) == _held_c(1)
    body = night.message("feat(")
    assert body.rstrip("\n").splitlines()[-3:] == [HAIKU_COAUTHOR, driver.MATCHED_BY,
                                                   SONNET_COAUTHOR]  # fmt: skip
    assert len(night.gate_calls) == 1 and len(night.lint_calls) == 1
    (landing,) = _new(night, before, "landing")
    assert (landing["outcome"], landing["from_run"], landing["from_attempt"]) == (
        "MATCHED", "spike012-haiku", 1)  # fmt: skip
    assert (landing["model"], landing["run"], landing["reason"]) == (HAIKU, LAND_RUN, None)
    assert landing["commit"] == night.sha("feat(")
    driver.validate_record(landing)
    assert _new(night, before, "attempt") == []
    after = stats.collect(night.repo, night.repo / LOG, night.repo / "config",
                          runs=["spike012-*"]).data  # fmt: skip
    assert (cost, after["totals"]["cost_usd"]) == ("1.00", "1.00")
    assert after["per_match"]["matched_functions"] == 1


def test_land_held_across_arms(tmp_path):
    """07.2-16 (D-22): the hold runs of three arms of one multi-arm night (`<run>-<arm>`) land
    each function once, with `--land-held <run>-*`. Quick 261110-f30: from the lowest
    API-equivalent cost (Haiku at equal tokens), not the recorded cost, and every arm that held
    it exact is credited once."""
    from test_driver import MATCH_SUBJECT, UNIT_REL

    night = _table_night(tmp_path, gate_exits=[0])
    arms = ((HAIKU, 0.90, _held_c(1)), (SONNET, 0.10, _held_c(2)),
            ("claude-opus-5-5", 0.50, _held_c(3)))  # fmt: skip
    _commit_log(night, [_hold_attempt(night, f"spike012-{model}", 1, cost=cost, model=model,
                                      text=text) for model, cost, text in arms])  # fmt: skip
    before = len(night.records())
    report = _land(night, "spike012-*")
    assert (report.event, report.matched) == ("ENDED", 1), report.detail
    assert [s for s in night.commits() if s.startswith("feat(")] == [MATCH_SUBJECT]
    assert night.file_at("feat(", UNIT_REL) == _held_c(1)
    lines = night.message("feat(").splitlines()
    assert [lines.count(line) for line in (HAIKU_COAUTHOR, SONNET_COAUTHOR, OPUS_COAUTHOR)] == [
        1, 1, 1]  # fmt: skip
    (landing,) = _new(night, before, "landing")
    assert (landing["from_run"], landing["model"]) == (f"spike012-{HAIKU}", HAIKU)
    assert len(night.gate_calls) == 1


def test_land_held_ranks_by_api_equivalent_not_recorded_cost(tmp_path):
    """Quick 261110-f30: a Codex attempt records cost 0 on Plus, but its tokens at its list
    price cost more than Haiku's (recorded 0.90, few tokens), so Haiku lands; Luna, which held
    the function exact too, gets its own co-author line."""
    night = _table_night(tmp_path, gate_exits=[0])
    luna = _hold_attempt(night, "spike012-gpt-6-luna", 1, cost=0.0, model="gpt-6-luna",
                         text=_held_c(2),
                         tokens={"input": 10_000_000, "output": 1_000_000, "cache_read": 0,
                                 "cache_creation": 0},
                         change={"backend": "openai", "harness": "codex", "model": None,
                                 "cost_source": "estimate"})  # fmt: skip
    haiku = _hold_attempt(night, "spike012-haiku", 1, cost=0.90,
                          tokens={"input": 1000, "output": 100, "cache_read": 0,
                                  "cache_creation": 0})  # fmt: skip
    _commit_log(night, [luna, haiku])
    before = len(night.records())
    report = _land(night, "spike012-*")
    assert (report.event, report.matched) == ("ENDED", 1), report.detail
    body = night.message("feat(").rstrip("\n").splitlines()
    assert body[-3:] == [HAIKU_COAUTHOR, driver.MATCHED_BY, LUNA_COAUTHOR]
    (landing,) = _new(night, before, "landing")
    assert (landing["from_run"], landing["model"]) == ("spike012-haiku", HAIKU)


def test_land_held_credits_every_holder_once(tmp_path):
    """Haiku held FUNC exact on two hold runs and DeepSeek on one; Sonnet's attempt was only
    PARTIAL. Haiku is the cheapest (its list price is below DeepSeek's on the same tokens), so
    it lands: one Haiku line, one DeepSeek line, no Sonnet line."""
    night = _table_night(tmp_path, gate_exits=[0])
    _commit_log(night, [
        _hold_attempt(night, "spike012-haiku-a", 1, cost=0.10),
        _hold_attempt(night, "spike012-haiku-b", 1, cost=0.10),
        _hold_attempt(night, "spike012-deepseek", 1, cost=0.01, model=DEEPSEEK_MODEL,
                      change={"backend": "openrouter", "cost_source": "estimate"}),
        _hold_attempt(night, "spike012-sonnet", 1, cost=0.01, model=SONNET, outcome="PARTIAL"),
    ])  # fmt: skip
    before = len(night.records())
    report = _land(night, "spike012-*")
    assert (report.event, report.matched) == ("ENDED", 1), report.detail
    (landing,) = _new(night, before, "landing")
    assert landing["from_run"] == "spike012-haiku-a"
    lines = night.message("feat(").rstrip("\n").splitlines()
    assert (lines.count(HAIKU_COAUTHOR), lines.count(DEEPSEEK_COAUTHOR)) == (1, 1)
    assert SONNET_COAUTHOR not in lines
    assert lines[-3:] == [HAIKU_COAUTHOR, driver.MATCHED_BY, DEEPSEEK_COAUTHOR]


@pytest.mark.parametrize(("runs", "winner"), [
    ((("spike012-b", 1, 0.5), ("spike012-a", 1, 0.5)), ("spike012-a", 1)),
    ((("spike012-a", 2, 0.5), ("spike012-a", 1, 0.5)), ("spike012-a", 1)),
])  # fmt: skip
def test_land_held_ties(tmp_path, runs, winner):
    """Equal costs: the earlier run id, then the lower attempt number."""
    night = _table_night(tmp_path, gate_exits=[0])
    _commit_log(night, [_hold_attempt(night, run, n, cost=cost) for run, n, cost in runs])
    before = len(night.records())
    _land(night, "spike012-*")
    (landing,) = _new(night, before, "landing")
    assert (landing["from_run"], landing["from_attempt"]) == winner


@pytest.mark.parametrize("rel", ["src/ufo2p/u_00010000.c", "include/common.h"])
def test_land_held_refuses_a_changed_unit(tmp_path, rel):
    """Pitfall 8: the unit or include/ changed since the held attempt's view head: a REFUSED
    landing record and no gate call."""
    from test_driver import SCAFFOLD, UNIT_REL
    from test_driver_records import _commit

    night = _table_night(tmp_path, gate_exits=[0])
    held = _hold_attempt(night, "spike012-haiku", 1, cost=0.10)
    _commit(night, {rel: (night.repo / rel).read_text(encoding="utf-8") + "/* changed */\n"})
    _commit_log(night, [held])
    before = len(night.records())
    report = _land(night, "spike012-haiku")
    assert report.event == "ENDED" and report.matched == 0
    (landing,) = _new(night, before, "landing")
    assert (landing["outcome"], landing["commit"], landing["gate"]) == ("REFUSED", None, None)
    assert landing["reason"] == "unit changed since the hold run; re-run"
    assert night.gate_calls == [] and night.lint_calls == []
    assert not [s for s in night.commits() if s.startswith("feat(")]
    if rel == UNIT_REL:
        assert SCAFFOLD in (night.repo / UNIT_REL).read_text(encoding="utf-8")


START2 = 0x00010020  # a second function of the test unit (made up)
FUNC2 = f"func_{START2:08X}"


def _two_function_unit(first: str, second: str) -> str:
    return f'#include "common.h"\n\n{first}\n\n{second}\n'


def _body(func: str, value: int) -> str:
    return f"int {func}(void)\n{{\n    return {value};\n}}"


def _two_held(tmp_path: Path, *, stale: bool = False) -> tuple[Night, int]:
    """A unit with two INCLUDE_ASM functions, each held exact by its own hold-run attempt (its
    exact check C: the whole unit with its own function defined, the other still asm), both
    from one view head; `stale`: the unit then changes in a commit of its own."""
    from test_driver import FUNC, UNIT_REL
    from test_driver_records import _commit

    night = _table_night(tmp_path, gate_exits=[0, 0])
    asm1, asm2 = f"INCLUDE_ASM({FUNC});", f"INCLUDE_ASM({FUNC2});"
    _commit(night, {UNIT_REL: _two_function_unit(asm1, asm2)}, "made-up two-function unit")
    held = [_hold_attempt(night, "spike012-haiku", 1, cost=0.10,
                          text=_two_function_unit(_body(FUNC, 1), asm2)),
            _hold_attempt(night, "spike012-haiku", 1, cost=0.10, start=START2,
                          text=_two_function_unit(asm1, _body(FUNC2, 2)))]  # fmt: skip
    if stale:
        _commit(night, {UNIT_REL: (night.repo / UNIT_REL).read_text(encoding="utf-8")
                         + "/* changed */\n"})  # fmt: skip
    _commit_log(night, held)
    return night, len(night.records())


def test_land_held_lands_two_functions_of_one_unit(tmp_path):
    """07.2 review WR-06: two held functions of one unit both land, one after the other. The
    second is not stale: the unit changed since its view head only by this run's own landing
    of the first, so its definition is spliced onto the unit as it now is (the first
    function's landed C kept) and the gate proves the result."""
    from test_driver import FUNC, UNIT_REL

    night, before = _two_held(tmp_path)
    report = _land(night, "spike012-haiku")
    assert (report.event, report.matched) == ("ENDED", 2), report.detail
    landings = _new(night, before, "landing")
    assert [(r["function"], r["outcome"], r["reason"]) for r in landings] == [
        (FUNC, "MATCHED", None), (FUNC2, "MATCHED", None)]  # fmt: skip
    assert len(night.gate_calls) == 2
    assert (night.repo / UNIT_REL).read_text(encoding="utf-8") == _two_function_unit(
        _body(FUNC, 1), _body(FUNC2, 2))  # fmt: skip


def test_land_held_still_refuses_two_functions_of_a_unit_changed_elsewhere(tmp_path):
    """WR-06 keeps Pitfall 8: when the unit changed since the hold run by a commit that is not
    this run's landing, neither held function lands."""
    night, before = _two_held(tmp_path, stale=True)
    report = _land(night, "spike012-haiku")
    assert (report.event, report.matched) == ("ENDED", 0), report.detail
    landings = _new(night, before, "landing")
    assert [(r["outcome"], r["reason"]) for r in landings] == [
        ("REFUSED", driver.LAND_HELD_STALE)] * 2  # fmt: skip
    assert night.gate_calls == []


def test_land_held_gate_refusal(tmp_path):
    """The gate refuses: a REFUSED landing record with the gate's verdict, the unit back as
    HEAD has it, nothing committed but the records."""
    from test_driver import SCAFFOLD, UNIT_REL

    night = _table_night(tmp_path, gate_exits=[1])
    _commit_log(night, [_hold_attempt(night, "spike012-haiku", 1, cost=0.10)])
    before = len(night.records())
    report = _land(night, "spike012-haiku")
    assert report.event == "ENDED" and report.matched == 0
    (landing,) = _new(night, before, "landing")
    assert (landing["outcome"], landing["commit"]) == ("REFUSED", None)
    assert landing["gate"]["exit"] == 1 and "gate" in landing["reason"]
    assert (night.repo / UNIT_REL).read_text(encoding="utf-8") == SCAFFOLD
    assert not [s for s in night.commits() if s.startswith("feat(")]
    assert night.git("status", "--porcelain=v1", "--untracked-files=no") == ""


def test_land_held_each_function_once(tmp_path):
    """HOLD_EXACT in three runs lands once; a second --land-held over the same runs skips the
    function as matched (no gate, no landing record). Quick 261110-f30: b has the fewest
    tokens, so the lowest API-equivalent cost."""
    night = _table_night(tmp_path, gate_exits=[0, 0])
    fewer = {"input": 600, "output": 150, "cache_read": 2500, "cache_creation": 400}
    _commit_log(night, [_hold_attempt(night, f"spike012-{arm}", 1, cost=cost, tokens=tokens)
                        for arm, cost, tokens in (("a", 0.3, None), ("b", 0.2, fewer),
                                                  ("c", 0.4, None))])  # fmt: skip
    before = len(night.records())
    assert _land(night, "spike012-*").matched == 1
    (landing,) = _new(night, before, "landing")
    assert landing["from_run"] == "spike012-b"
    assert len(night.gate_calls) == 1
    again = len(night.records())
    report = _land(night, "spike012-*", run_id="land2")
    assert (report.event, report.matched) == ("ENDED", 0)
    assert _new(night, again, "landing") == [] and len(night.gate_calls) == 1


def test_land_held_skips_attempts_that_were_not_exact(tmp_path):
    """Only HOLD_EXACT records land; a hold run's PARTIAL attempt is no candidate."""
    night = _table_night(tmp_path, gate_exits=[0])
    _commit_log(night, [_hold_attempt(night, "spike012-haiku", 1, cost=0.01, outcome="PARTIAL")])
    report = _land(night, "spike012-*")
    assert (report.event, report.matched) == ("ENDED", 0)
    assert night.gate_calls == [] and night.kinds("landing") == []


def test_land_held_unknown_run(tmp_path, capsys):
    """No hold run matches the names: exit 2 naming them, before anything lands."""
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, json=True, land_held=("spike099-*", "other"))
    assert code == 2
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "land held")
    assert "spike099-*" in doc["detail"] and "other" in doc["detail"]
    assert not rig.commands("gate")


def test_land_held_applies_renames_since(tmp_path):
    """A rename committed since the view head is carried into the landed C, as a night's
    landing does (_renames_since)."""
    from reverseapoc.functions import SymbolRow, write_symbols_csv
    from test_driver import UNIT_REL

    calls = _held_c(1).replace("    return 1;", f"    return {CALLEE_NAME}();").replace(
        '#include "common.h"\n', f'#include "common.h"\n\nextern int {CALLEE_NAME}(void);\n')
    night = _table_night(tmp_path, gate_exits=[0])
    held = _hold_attempt(night, "spike012-haiku", 1, cost=0.10, text=calls)
    symbols = night.repo / "config/ufo2p/symbols.csv"
    write_symbols_csv(symbols, [SymbolRow(CALLEE, "SoundMute_", "func")], "UFO2P.EXE")
    night.git("add", "--", "config/ufo2p/symbols.csv")
    night.git("commit", "-q", "-m", f"refactor(ufo2p): rename {CALLEE_NAME} to SoundMute")
    _commit_log(night, [held])
    report = _land(night, "spike012-haiku")
    assert report.matched == 1, report.detail
    landed = night.file_at("feat(", UNIT_REL)
    assert "SoundMute()" in landed and CALLEE_NAME not in landed


def test_run_drive_hands_land_held_to_the_night(tmp_path, capsys, monkeypatch):
    """`drive --land-held` runs the landing through run_drive's preflight and lock, with no
    Ghidra drafts and no claude version check."""
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

    monkeypatch.setattr(driver, "drive", fake_drive)
    code, _, _ = rig.drive(capsys, json=True, land_held=("spike012-*",))
    assert code == 0
    assert seen[0].land_held == ("spike012-*",)
    assert not rig.commands("ghidra-export")
    assert not [c for c in rig.runner.calls if c[1:] == ["--version"]]


# ---- 07.2-12 (D-10, D-11, D-12, D-26): hosted arms ----
#
# Owner rule: no real key reaches a test. `_keyed` drops every inherited variable that could
# hold one (any *_API_KEY, *_TOKEN or ANTHROPIC_* name) before adding made-up values, and no
# assertion below prints a session environment (only single values or key names).

DEEPSEEK = "deepseek-flash"  # the arm; it runs through OpenRouter (owner, 2026-11-10)
DEEPSEEK_MODEL = "deepseek/deepseek-v4.1-flash"  # its OpenRouter model id
DEEPSEEK_URL = "https://openrouter.ai/api"
FAKE_KEY = "made-up-deepseek-value-0001"


def _keyed(env: dict, **values: str) -> dict:
    from test_driver import _Env

    out = _Env((k, v) for k, v in env.items()
               if not (k.endswith(("_API_KEY", "_TOKEN")) or k.startswith("ANTHROPIC_")))
    out.update(values)
    return out


def _hosted_night(tmp_path: Path, monkeypatch, sessions: list) -> tuple[Rig, Night, list]:
    """`drive` on a Rig whose night (run_drive's own DriveConfig, arm table and session env)
    runs in test_driver's night harness: real sessions through fakeclaude, a fake gate."""
    rig = Rig(tmp_path / "rig")
    night = Night(tmp_path / "night", sessions=sessions, gate_exits=[1] * len(sessions))
    real, seen = driver.drive, []

    def drive(config, deps, *, lock=None):
        seen.append(config)
        moved = replace(config, repo_root=night.repo, min_cli_version=(2, 1, 240),
                        attempts_per_function=1)  # fmt: skip
        return real(moved, night.deps())

    monkeypatch.setattr(driver, "drive", drive)
    return rig, night, seen


def test_hosted_arm_reaches_the_session(tmp_path, capsys, monkeypatch):
    """D-11, D-12: chosen twice, the DeepSeek arm's session gets OpenRouter's endpoint with the
    key as its bearer token, and the record names the arm; the key is in no record, console
    line, commit or transcript."""
    from test_driver import LOG, Sess

    rig, night, seen = _hosted_night(tmp_path, monkeypatch, [Sess()])
    env = _keyed(rig.env, OPENROUTER_API_KEY=FAKE_KEY)
    code, out, err = rig.drive(capsys, seams={"base_env": env}, night_model=DEEPSEEK,
                               allow_egress=(DEEPSEEK,), workers=1)  # fmt: skip
    assert code == 0, err
    assert seen[0].night_model == DEEPSEEK
    record = night.kinds("attempt")[0]
    assert (record["backend"], record["model_requested"], record["harness"]) == (
        "openrouter", DEEPSEEK_MODEL, "claude")  # fmt: skip
    launched = night.launched[0]
    assert launched.argv[launched.argv.index("--model") + 1] == DEEPSEEK_MODEL
    assert launched.env.get("ANTHROPIC_BASE_URL") == DEEPSEEK_URL
    assert launched.env.get("ANTHROPIC_AUTH_TOKEN") == FAKE_KEY
    assert launched.env.get("ANTHROPIC_API_KEY") == ""
    assert launched.env.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC") == "1"
    assert "OPENROUTER_API_KEY" not in set(launched.env)
    texts = {"record": (night.repo / LOG).read_text(encoding="utf-8"), "console": out + err,
             "transcript": (night.attempt_dir() / driver.TRANSCRIPT).read_text(encoding="utf-8"),
             "commits": night.git("log", "-p", "--format=%B")}  # fmt: skip
    assert [name for name, text in texts.items() if FAKE_KEY in text] == []


@pytest.mark.parametrize(("allow", "key", "words"), [
    ((), FAKE_KEY, "--allow-egress"),
    ((DEEPSEEK,), "", "OPENROUTER_API_KEY"),
    ((DEEPSEEK,), "   ", "OPENROUTER_API_KEY"),
    ((DEEPSEEK,), None, "OPENROUTER_API_KEY"),
    (("glm-5.3",), FAKE_KEY, "glm-5.3"),
    ((DEEPSEEK, "glm-5.3"), FAKE_KEY, "glm-5.3"),
])  # fmt: skip
def test_hosted_arm_refused_before_any_session(tmp_path, capsys, allow, key, words):
    """D-11, D-26: without --allow-egress, with a missing, empty or blank key (the claude.ai
    login would go to OpenRouter), or with a stray --allow-egress: exit 2 before any command,
    session or attempt directory."""
    rig = Rig(tmp_path)
    env = _keyed(rig.env) if key is None else _keyed(rig.env, OPENROUTER_API_KEY=key)
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": env}, night_model=DEEPSEEK,
                             allow_egress=allow)  # fmt: skip
    assert code == 2
    doc = _refusal(out)
    assert words in doc["detail"], doc
    assert FAKE_KEY not in out
    assert rig.runner.calls == []
    assert list((rig.repo / "build").rglob("attempt-*")) == []


def test_canary_proves_the_egress_refusal(tmp_path, capsys):
    """D-11: the canary of a hosted arm without --allow-egress is refused before its session."""
    rig = Rig(tmp_path)
    env = _keyed(rig.env, OPENROUTER_API_KEY=FAKE_KEY)
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": env}, canary=True,
                             night_model=DEEPSEEK, canary_model=DEEPSEEK)  # fmt: skip
    assert code == 2
    assert "--allow-egress" in _refusal(out)["detail"]
    assert rig.runner.calls == []
    assert not (rig.repo / "build" / "driver" / "canary").exists()


def test_an_unknown_night_model_is_refused_naming_the_arms(tmp_path, capsys):
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, json=True, night_model="gpt-x")
    assert code == 2
    detail = _refusal(out)["detail"]
    assert "gpt-x" in detail and DEEPSEEK in detail and "claude-opus-5-5" in detail


@pytest.mark.parametrize(("argv", "named"), [
    (["--night-model", "claude-haiku-5-5", "--allow-egress", "claude-haiku-5-5"],
     "claude-haiku-5-5"),
    (["--night-model", DEEPSEEK, "--allow-egress", "glm-5.3"], "glm-5.3"),
    (["--allow-egress", DEEPSEEK], DEEPSEEK),
])  # fmt: skip
def test_cli_refuses_a_stray_allow_egress(argv, named, capsys, monkeypatch):
    """D-11: an --allow-egress naming an arm that sends nothing off the machine, or an arm the
    night does not run, exits 2 naming it, before run_drive."""
    seen = []
    monkeypatch.setattr(driver, "run_drive", lambda options, seams: seen.append(options) or 0)
    monkeypatch.setattr(driver, "default_seams", lambda repo: None)
    assert cli.main(["drive", *argv]) == 2
    err = capsys.readouterr().err
    assert "--allow-egress" in err and named in err, err
    assert seen == []


def test_cli_threads_allow_egress(monkeypatch):
    seen = []
    monkeypatch.setattr(driver, "run_drive", lambda options, seams: seen.append(options) or 0)
    monkeypatch.setattr(driver, "default_seams", lambda repo: None)
    assert cli.main(["drive", "--night-model", DEEPSEEK, "--allow-egress", DEEPSEEK]) == 0
    assert (seen[0].night_model, seen[0].allow_egress) == (DEEPSEEK, (DEEPSEEK,))
    assert cli.main(["drive", "--canary", "--night-model", DEEPSEEK, "--allow-egress",
                     DEEPSEEK]) == 0  # fmt: skip
    assert (seen[1].canary_model, seen[1].allow_egress) == (DEEPSEEK, (DEEPSEEK,))


def test_drive_help_lists_allow_egress(capsys):
    with pytest.raises(SystemExit):
        cli.main(["drive", "--help"])
    assert "--allow-egress" in capsys.readouterr().out


# ---- 07.2-12 Task 2 (D-10, D-16, D-26): init, cost, credit and reads of hosted arms ----

DEEPSEEK_COAUTHOR = "Co-Authored-By: DeepSeek V4.1-Flash <noreply@deepseek.com>"
HOSTED_TRAILERS = [driver.MATCHED_BY, f"Matched-By: {DEEPSEEK_MODEL}", DEEPSEEK_COAUTHOR]
# hosted_success.jsonl's tokens at deepseek-flash's prices (input, output, both cache classes
# at the input price): its result event's own total_cost_usd, 9.99, is not trusted.
HOSTED_ESTIMATE = (1200 * 0.30 + 300 * 1.20 + 5000 * 0.30 + 800 * 0.30) / 1_000_000


def _hosted_run(night: Night, **config) -> driver.DriveReport:
    """A night of the DeepSeek arm in the night harness, with a made-up key (D-12)."""
    fields = {"night_model": DEEPSEEK, "attempts_per_function": 1,
              "base_env": _keyed(night.env, OPENROUTER_API_KEY=FAKE_KEY)}  # fmt: skip
    fields.update(config)
    return night.run(config=fields)


def test_hosted_record_is_an_estimate(tmp_path):
    """RESEARCH A3: a hosted session's cost is the estimate from its arm's prices, even when
    its result event reports one; a Claude arm's keeps the CLI's figure."""
    from test_driver import Sess

    night = Night(tmp_path / "hosted", sessions=[Sess("hosted_success")], gate_exits=[1])
    report = _hosted_run(night)
    assert report.event == "ENDED", report.detail
    record = night.kinds("attempt")[0]
    assert (record["backend"], record["cost_source"], record["model"]) == (
        "openrouter", "estimate", DEEPSEEK_MODEL)  # fmt: skip
    assert record["cost_usd"] == pytest.approx(HOSTED_ESTIMATE)
    assert record["duration_ms"] == 45000 and record["tokens"]["input"] == 1200
    driver.validate_record(record)
    claude = Night(tmp_path / "claude", sessions=[Sess()], gate_exits=[1])
    claude.run(config={"attempts_per_function": 1})
    mine = claude.kinds("attempt")[0]
    assert (mine["backend"], mine["cost_source"], mine["cost_usd"]) == ("anthropic", "cli", 0.25)


def test_hosted_init_is_checked_against_the_arms_ids(tmp_path):
    """A hosted session whose init names another model (a provider that maps claude ids to its
    models) stops the night at the init check."""
    from test_driver import Sess

    night = Night(tmp_path, sessions=[Sess("hosted_success")], gate_exits=[0])
    real = night._argv

    def argv(prompt, **values):  # fakeclaude --init-model: the init names another model
        return [*real(prompt, **values), "--init-model", "deepseek-v4-pro"]

    report = night.run(config={"night_model": DEEPSEEK, "attempts_per_function": 1,
                               "base_env": _keyed(night.env, OPENROUTER_API_KEY=FAKE_KEY)},
                       argv=argv)  # fmt: skip
    assert (report.event, report.reason) == ("STOPPED", driver.INIT), report.detail
    assert "deepseek-v4-pro" in report.detail
    assert night.gate_calls == []


def test_hosted_match_trailers(tmp_path):
    """D-26: a hosted arm's match commit carries the driver's trailer, then Matched-By: <model
    id>, then its vendor's co-author line, and no Claude line; stats still classes it
    unattended (RULINGS "Matched-By")."""
    from reverseapoc import stats
    from test_driver import MATCH_SUBJECT, Sess

    night = Night(tmp_path, sessions=[Sess("hosted_success")], gate_exits=[0])
    report = _hosted_run(night)
    assert (report.event, report.matched) == ("ENDED", 1), report.detail
    body = night.message(MATCH_SUBJECT)
    assert body.rstrip("\n").splitlines()[-3:] == HOSTED_TRAILERS
    assert "noreply@anthropic.com" not in body
    assert stats.classify(stats._trailers(body)) == (stats.UNATTENDED, False)
    assert night.kinds("attempt")[0]["outcome"] == "MATCHED"


def test_the_commit_hook_adds_no_claude_line_to_a_hosted_match(tmp_path):
    """RULINGS: the repository's commit-msg hook adds its Claude line only when no
    Co-Authored-By trailer is there, so the vendor line of a hosted match suppresses it."""
    from test_githooks import SH, _coauthor_lines, _env, _run_hook

    if SH is None:
        pytest.skip("needs sh")
    usage = driver.streamjson.Usage(1, 1, 1, 1, 1, 0.0, 1)
    message = driver.commit_message(exe="ufo2p", function="func_00010010", unit="u_00010000",
                                    attempt_n=1, attempts=1, model=DEEPSEEK_MODEL, usage=usage,
                                    seconds=1.0, sha1s=[], requested_model=DEEPSEEK_MODEL,
                                    arm=driver.backends.load_arms()[DEEPSEEK])  # fmt: skip
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(message, encoding="utf-8", newline="\n")
    assert _run_hook(msg, _env(tmp_path, claudecode=True)).returncode == 0
    assert _coauthor_lines(msg.read_text(encoding="utf-8")) == [DEEPSEEK_COAUTHOR]


def test_land_held_credits_a_hosted_arm(tmp_path):
    """06's --land-held credits a hosted hold run to its arm: the same three trailers."""
    night = _table_night(tmp_path, gate_exits=[0])
    record = _hold_attempt(night, "spike012-deepseek", 1, cost=0.01, model=DEEPSEEK_MODEL)
    record["backend"] = "openrouter"
    _commit_log(night, [record])
    report = _land(night, "spike012-*")
    assert (report.event, report.matched) == ("ENDED", 1), report.detail
    body = night.message("feat(")
    assert body.rstrip("\n").splitlines()[-3:] == HOSTED_TRAILERS
    assert "noreply@anthropic.com" not in body


def test_egress_env_set_for_hosted_arms(tmp_path):
    """D-10: a hosted arm's session runs with REVERSEAPOC_EGRESS=1; a Claude arm's never does,
    even when the driver's own environment carries it."""
    from reverseapoc import hooks
    from test_driver import Sess

    night = Night(tmp_path / "hosted", sessions=[Sess("hosted_success")], gate_exits=[1])
    _hosted_run(night)
    assert night.launched[0].env.get(hooks.EGRESS_ENV) == "1"
    claude = Night(tmp_path / "claude", sessions=[Sess()], gate_exits=[1])
    claude.run(config={"attempts_per_function": 1,
                       "base_env": {**claude.env, hooks.EGRESS_ENV: "1"}})  # fmt: skip
    assert hooks.EGRESS_ENV not in set(claude.launched[0].env)


# ---- 07.2-12 Task 3 (D-18): the local llama.cpp arm, last ----

LOCAL = "qwen-local"


def test_local_arm_runs_on_loopback(tmp_path, capsys, monkeypatch):
    """The local arm needs no --allow-egress and no key: its session gets the loopback URL and
    the fixed loopback token, its record says backend local and costs nothing."""
    from test_driver import Sess

    rig, night, seen = _hosted_night(tmp_path, monkeypatch, [Sess()])
    code, _, err = rig.drive(capsys, seams={"base_env": _keyed(rig.env)}, night_model=LOCAL,
                             workers=1)  # fmt: skip
    assert code == 0, err
    launched = night.launched[0]
    assert launched.env.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:8080"
    assert launched.env.get("ANTHROPIC_AUTH_TOKEN") == driver.backends.LOOPBACK_TOKEN
    assert launched.argv[launched.argv.index("--model") + 1] == "qwen3.6-35b-a3b"
    record = night.kinds("attempt")[0]
    assert (record["backend"], record["cost_usd"], record["cost_source"]) == (
        "local", 0.0, "estimate")  # fmt: skip


@pytest.mark.parametrize(("over", "words"), [
    ({"workers": 2}, "max_workers"),
    ({"workers": 1, "allow_egress": (LOCAL,)}, LOCAL),
])  # fmt: skip
def test_local_arm_refusals(tmp_path, capsys, over, words):
    """One worker only (the server has one slot), and no --allow-egress: refused, exit 2,
    before any command."""
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, json=True, night_model=LOCAL, **over)
    assert code == 2
    assert words in _refusal(out)["detail"]
    assert rig.runner.calls == []


def test_cli_refuses_allow_egress_for_the_local_arm(capsys, monkeypatch):
    seen = []
    monkeypatch.setattr(driver, "run_drive", lambda options, seams: seen.append(options) or 0)
    monkeypatch.setattr(driver, "default_seams", lambda repo: None)
    assert cli.main(["drive", "--night-model", LOCAL, "--allow-egress", LOCAL]) == 2
    assert LOCAL in capsys.readouterr().err and seen == []


# ---- 07.2-16 (D-22, D-26): every per-arm gate still holds inside a multi-arm drive ----

LUNA = "gpt-6-luna"
GEMINI = "gemini-flash"


def _no_session_ran(rig: Rig) -> None:
    assert list((rig.repo / "build").rglob("attempt-*")) == []


@pytest.mark.parametrize("arm", [LUNA, GEMINI])
def test_multi_arm_needs_each_signed_in_arms_canary_pass(tmp_path, capsys, arm):
    """D-13, D-21: a Codex or agy arm beside a Claude arm still runs only after its own canary
    passed: refused with exit 2 before any session, naming that arm's canary command."""
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": _keyed(rig.env)},
                             arms=((HAIKU, 1), (arm, 1)), allow_egress=(arm,))  # fmt: skip
    assert code == 2
    assert f"--canary --night-model {arm} --allow-egress {arm}" in _refusal(out)["detail"]
    _no_session_ran(rig)


@pytest.mark.parametrize(("allow", "words"), [
    ((), f"--allow-egress {DEEPSEEK}"),
    (("glm-5.3",), "glm-5.3"),
    ((HAIKU,), HAIKU),
    ((DEEPSEEK, "glm-5.3"), "glm-5.3"),
])  # fmt: skip
def test_multi_arm_egress_is_per_arm(tmp_path, capsys, allow, words):
    """D-11: each egress arm of a multi-arm night needs its own --allow-egress, and an
    --allow-egress naming an arm the night does not run, or one that sends nothing off the
    machine, is refused: exit 2 before any command."""
    rig = Rig(tmp_path)
    env = _keyed(rig.env, OPENROUTER_API_KEY=FAKE_KEY)
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": env},
                             arms=((HAIKU, 1), (DEEPSEEK, 1)), allow_egress=allow)  # fmt: skip
    assert code == 2
    assert words in _refusal(out)["detail"]
    assert rig.runner.calls == []
    _no_session_ran(rig)


@pytest.mark.parametrize("key", ["", "   ", None])
def test_multi_arm_token_leak_guard(tmp_path, capsys, key):
    """D-26: a hosted arm beside a Claude arm with a missing, empty or blank key is refused
    before any command (the claude.ai login would go to its endpoint)."""
    rig = Rig(tmp_path)
    env = _keyed(rig.env) if key is None else _keyed(rig.env, OPENROUTER_API_KEY=key)
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": env},
                             arms=((HAIKU, 1), (DEEPSEEK, 1)), allow_egress=(DEEPSEEK,))
    assert code == 2
    assert "OPENROUTER_API_KEY" in _refusal(out)["detail"]
    assert rig.runner.calls == []


@pytest.mark.parametrize(("arms", "named"), [
    (((HAIKU, 1), (LUNA, 2)), LUNA),
    (((LOCAL, 2), (HAIKU, 1)), LOCAL),
    (((HAIKU, 11),), HAIKU),
])  # fmt: skip
def test_multi_arm_max_workers_per_arm(tmp_path, capsys, arms, named):
    """Each arm's workers stay within its backends.toml max_workers: refused before any
    command, naming the arm."""
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": _keyed(rig.env)}, arms=arms,
                             allow_egress=tuple(a for a, _ in arms if a == LUNA))  # fmt: skip
    assert code == 2
    detail = _refusal(out)["detail"]
    assert "max_workers" in detail and named in detail, detail
    assert rig.runner.calls == []


def test_multi_arm_reaches_the_night(tmp_path, capsys, monkeypatch):
    """run_drive hands the arms to the night, with the sum of their workers."""
    seen = []

    def fake_drive(config, deps, *, lock=None):
        seen.append(config)
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    monkeypatch.setattr(driver, "drive", fake_drive)
    rig = Rig(tmp_path)
    env = _keyed(rig.env, OPENROUTER_API_KEY=FAKE_KEY)
    code, _, err = rig.drive(capsys, json=True, seams={"base_env": env},
                             arms=((HAIKU, 2), (DEEPSEEK, 1)), allow_egress=(DEEPSEEK,))
    assert code == 0, err
    assert (seen[0].arms, seen[0].workers, seen[0].night_model) == (
        ((HAIKU, 2), (DEEPSEEK, 1)), 3, None)  # fmt: skip


def test_multi_arm_keeps_the_codex_audit(tmp_path, capsys, monkeypatch):
    """D-26: a Codex arm's session in a multi-arm night goes through the Codex audit: a stray
    command stops the whole night as a guardrail, and the Claude arm launches nothing after."""
    from test_codex import codex_night, write_pass

    rig, night, env = codex_night(tmp_path, monkeypatch, scenario="stray_command")
    write_pass(rig.repo)
    code, _, _ = rig.drive(capsys, seams={"base_env": env}, arms=((LUNA, 1), (HAIKU, 1)),
                           allow_egress=(LUNA,))  # fmt: skip
    assert code != 0
    stopped = [r for r in night.kinds("run") if r["event"] == "STOPPED"][0]
    assert stopped["reason"] == driver.GUARDRAIL and "type notes.md" in stopped["detail"]
    assert len(night.launched) == 1
    assert night.kinds("attempt")[0]["run"] == f"{RUN}-{LUNA}"


# ---- quick 261112-fds (backlog 999.12a): the size-routed cascade through run_drive ----

SONNET = "claude-sonnet-5-5"
TERRA = "gpt-6.1-terra"
QWEN = "qwen-hosted"  # an egress arm in no committed routing row


def _committed_egress() -> tuple[str, ...]:
    """The committed routing table's arms that send the pack off the machine, in row order:
    the --allow-egress a cascade night needs (read from the config, so a recalibrated table
    does not break the gate tests)."""
    arms = driver.backends.load_arms()
    return tuple(arm for arm in driver.backends.routing_arms(driver.backends.load_routing())
                 if arms[arm].egress)  # fmt: skip


def _openrouter_keyed(rig: Rig) -> dict:
    """The seams of a committed-table night: no real key in the env, a test OpenRouter key so
    the table's OpenRouter arms pass their key check (never sent: no session runs)."""
    return {"base_env": _keyed(rig.env, OPENROUTER_API_KEY="test-key")}


def _cascade_night(tmp_path: Path, monkeypatch, picks) -> tuple[Rig, Night, list]:
    """`drive` on a Rig whose night (run_drive's own DriveConfig) runs in test_driver_workers'
    ArmNight, with D-07's three attempts per function kept."""
    from test_driver_workers import ArmNight

    rig = Rig(tmp_path / "rig")
    night = ArmNight(tmp_path / "night", picks=picks)
    real, seen = driver.drive, []

    def drive(config, deps, *, lock=None):
        seen.append(config)
        return real(replace(config, repo_root=night.repo, min_cli_version=(2, 1, 240)),
                    night.deps())  # fmt: skip

    monkeypatch.setattr(driver, "drive", drive)
    return rig, night, seen


def test_cascade_reaches_the_night_end_to_end(tmp_path, capsys, monkeypatch):
    """999.12a tracer: DriveOptions.routing reaches the night's DriveConfig, and one function's
    attempts climb its row (HAIKU, SONNET, SONNET) under `<run>-<arm>`."""
    from test_driver_workers import _every, _wpick

    rows = _every(HAIKU, SONNET)
    rig, night, seen = _cascade_night(tmp_path, monkeypatch, (_wpick(0),))
    code, _, err = rig.drive(capsys, json=True, routing=rows, workers=1)
    assert code == 0, err
    assert seen[0].routing == rows and seen[0].attempts_per_function == 3
    assert [(r["attempt"], r["model_requested"], r["run"]) for r in night.kinds("attempt")] == [
        (1, HAIKU, f"{RUN}-{HAIKU}"), (2, SONNET, f"{RUN}-{SONNET}"),
        (3, SONNET, f"{RUN}-{SONNET}")]  # fmt: skip


@pytest.mark.parametrize(("allow", "words"), [
    ((), f"--allow-egress {_committed_egress()[0]}"),
    (_committed_egress(), f"--canary --night-model {TERRA}"),
    ((*_committed_egress(), QWEN), QWEN),
], ids=["no-egress", "no-canary", "stray-egress"])  # fmt: skip
def test_cascade_arms_pass_every_per_arm_gate(tmp_path, capsys, allow, words):
    """T-261112-fds-01, -02: each cascade arm that sends the pack off the machine needs its own
    --allow-egress, an --allow-egress naming no cascade arm is refused, and each Codex or agy
    arm needs its canary PASS: exit 2 before any session."""
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, json=True, seams=_openrouter_keyed(rig),
                             routing=driver.backends.load_routing(), allow_egress=allow)
    assert code == 2
    assert words in _refusal(out)["detail"]
    _no_session_ran(rig)


def test_cascade_arm_caps_reach_the_night(tmp_path, capsys, monkeypatch):
    """run_drive hands the cascade's rows, its arm caps and --workers to the night (no --arm
    lanes), and prints the cascade line once, naming each row and each arm's cap."""
    from test_driver_workers import _every

    seen = []

    def fake_drive(config, deps, *, lock=None):
        seen.append(config)
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    monkeypatch.setattr(driver, "drive", fake_drive)
    rows = _every(HAIKU, SONNET)
    rig = Rig(tmp_path)
    code, out, err = rig.drive(capsys, routing=rows, arm_caps=((HAIKU, 5),), workers=2)
    assert code == 0, err
    config = seen[0]
    assert (config.routing, config.arm_caps, config.workers, config.arms) == (
        rows, ((HAIKU, 5),), 2, ())  # fmt: skip
    cascade = [line for line in err.splitlines() if "cascade: " in line]  # console: stderr
    assert len(cascade) == 1, err
    for row in rows:
        assert f"{row.label} {HAIKU} > {SONNET}" in cascade[0]
    assert f"{HAIKU}=5" in cascade[0]


@pytest.mark.parametrize(("caps", "words"), [
    ((("gemini-flash", 21),), ("--arm-cap gemini-flash=21", "max_sessions 20")),
    (((SONNET, 1),), (f"--arm-cap {SONNET}=1", ", ".join(
        driver.backends.routing_arms(driver.backends.load_routing())))),
], ids=["above-max-sessions", "not-a-cascade-arm"])  # fmt: skip
def test_a_cascade_arm_cap_above_max_sessions_is_refused(tmp_path, capsys, caps, words):
    """An --arm-cap above the arm's backends.toml max_sessions, or naming no cascade arm, is
    refused before any session."""
    from test_driver_workers import _every

    rig = Rig(tmp_path)
    rows, allow = driver.backends.load_routing(), _committed_egress()
    if caps[0][0] == "gemini-flash":  # an arm with a max_sessions, in a row of its own
        rows, allow = _every(HAIKU, "gemini-flash"), ("gemini-flash",)
    code, out, _ = rig.drive(capsys, json=True, seams=_openrouter_keyed(rig), routing=rows,
                             arm_caps=caps, allow_egress=allow)  # fmt: skip
    assert code == 2
    detail = _refusal(out)["detail"]
    assert all(word in detail for word in words), detail
    _no_session_ran(rig)


# ---- 261112-fds Task 3: the other modes refused, and the cascade's dry run ----


@pytest.mark.parametrize(("clash", "word"), [
    ({"arms": ((HAIKU, 1), (SONNET, 1))}, "arms"),
    ({"night_model": HAIKU}, "night_model"),
    ({"hold": True}, "hold"),
    ({"session": driver.READABILITY}, "readability"),
    ({"fable_trial": True}, "fable_trial"),
], ids=["arms", "night-model", "hold", "readability", "fable-trial"])  # fmt: skip
def test_a_cascade_config_refuses_the_other_modes(tmp_path, clash, word):
    """A DriveConfig with routing and any other mode is refused before any lane is built."""
    from test_driver_workers import _every

    config = driver.DriveConfig(run_id=RUN, repo_root=tmp_path, tested_major=2,
                                min_cli_version=(2, 1, 240), routing=_every(HAIKU), **clash)
    with pytest.raises(driver.DriverError, match="cascade") as exc:
        driver._lanes(config)
    assert word in str(exc.value)


def _expected_cascade(rig: Rig, rows, exe: str, start: int, size: int) -> tuple[str, int, list]:
    from reverseapoc import session

    passes = driver.pass_index(rig.repo / driver.ATTEMPT_LOG)
    row = driver.backends.route_for(rows, size)
    p = passes.get((exe, start), 0) + 1
    arms = [session.model_for_pass(p, row=row.arms, attempt=n, attempts=3) for n in (1, 2, 3)]
    return row.label, p, arms


def test_cascade_dry_run_prints_each_picks_bucket_and_attempts(tmp_path, capsys):
    """`--dry-run --cascade`: each pick's line ends with its bucket and the arm of each of its
    three attempts; each pick document gains `cascade` {bucket, pass, attempts}."""
    rows = driver.backends.load_routing()
    egress = _committed_egress()
    rig = Rig(tmp_path / "text")
    code, out, _ = rig.drive(capsys, dry_run=True, seams=_openrouter_keyed(rig), routing=rows,
                             allow_egress=egress)
    assert code == 0
    lines = [line for line in out.splitlines() if line.startswith(("ufo2p", "tacp"))]
    assert lines
    for line in lines:
        words = line.split()
        size = int(words[words.index("size") + 1])
        label, _, arms = _expected_cascade(rig, rows, words[0], int(words[1], 16), size)
        assert line.endswith(f" bucket {label} attempts {', '.join(arms)}"), line
    rig = Rig(tmp_path / "json")
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, seams=_openrouter_keyed(rig),
                             routing=rows, allow_egress=egress)
    assert code == 0
    for pick in json.loads(out)["picks"]:
        label, p, arms = _expected_cascade(rig, rows, pick["exe"], int(pick["start"], 16),
                                           pick["size"])  # fmt: skip
        assert pick["cascade"] == {"bucket": label, "pass": p, "attempts": arms}


def test_a_dry_run_without_cascade_is_unchanged(tmp_path, capsys):
    rig = Rig(tmp_path / "text")
    code, out, _ = rig.drive(capsys, dry_run=True)
    assert code == 0 and " bucket " not in out
    rig = Rig(tmp_path / "json")
    code, out, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 0
    picks = json.loads(out)["picks"]
    assert all("cascade" not in pick for pick in picks)
    assert set(picks[0]) == {"exe", "start", "name", "unit", "size", "score", "pack",
                             "pack_bytes"}  # fmt: skip


def test_the_cascade_preview_honours_the_arm_caps():
    """IN-05 (quick 261112-fdr): the preview counts one launch per attempt it shows, pick after
    pick, against each arm's cap, and routes past a capped arm as the night does. Row (HAIKU,
    TERRA), HAIKU capped at 3 and TERRA at 2: p0 runs the plain ladder; p1's attempt 2 finds
    TERRA capped and goes to HAIKU, its attempt 3 finds the whole row capped, which ends its
    pass; p2 finds the whole row capped at attempt 1."""
    from test_driver_workers import _every, _sized

    picks = [_sized(i, 20) for i in range(3)]
    previews = driver._cascade_previews(_every(HAIKU, TERRA), picks, {},
                                        {HAIKU: 3, TERRA: 2})  # fmt: skip
    assert [p["attempts"] for p in previews] == [
        [HAIKU, TERRA, TERRA],
        [HAIKU, f"{HAIKU} ({TERRA} capped)", driver.PREVIEW_ROW_CAPPED],
        [driver.PREVIEW_ROW_CAPPED]]  # fmt: skip
    assert [(p["bucket"], p["pass"]) for p in previews] == [("[0, 64)", 1)] * 3
    uncapped = driver._cascade_previews(_every(HAIKU, TERRA), picks, {}, {HAIKU: None})
    assert [p["attempts"] for p in uncapped] == [[HAIKU, TERRA, TERRA]] * 3


def test_a_cascade_dry_run_reads_the_arm_caps(tmp_path, capsys):
    """IN-05: `--dry-run --cascade --arm-cap` previews with the caps: with every arm capped at 1
    no arm is shown launching twice, and a pick past the caps shows its row capped."""
    rows = driver.backends.load_routing()
    caps = tuple((arm, 1) for arm in driver.backends.routing_arms(rows))
    rig = Rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, seams=_openrouter_keyed(rig),
                             routing=rows, arm_caps=caps,
                             allow_egress=_committed_egress())  # fmt: skip
    assert code == 0
    shown = [a for pick in json.loads(out)["picks"] for a in pick["cascade"]["attempts"]]
    launched = [a.split()[0] for a in shown if a.split()[0] in dict(caps)]
    assert len(launched) == len(set(launched)), shown
    assert driver.PREVIEW_ROW_CAPPED in shown, shown
