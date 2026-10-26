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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from reverseapoc import cli, driver
from reverseapoc.driver import DriveOptions, ExeWorld, PackInfo, Seams
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
    version: str = "2.1.302 (Claude Code)"

    def __call__(self, argv) -> subprocess.CompletedProcess:
        argv = list(argv)
        self.calls.append(argv)
        for match, reply in self.replies:
            if match(argv):
                code, out, err = reply
                return subprocess.CompletedProcess(argv, code, out, err)
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, self.version + "\n", "")
        return subprocess.CompletedProcess(argv, 0, "noise on stdout\n", "noise on stderr\n")


def _never_session(*args, **kwargs):
    raise AssertionError("a session was launched")


def _never_argv(prompt: str):
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

    def git(self, args):
        self.git_calls.append(list(args))
        return self._git(args)

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
    assert (args.max_sessions, args.target_matched) == (30, 10)  # D-48
    assert (args.dry_run, args.canary, args.json, args.run) == (False, False, False, None)


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


@dataclass
class Launch:
    argv: list[str]
    env: dict
    cwd: Path


PASSING_CHECK = {"n": 1, "exit": 0, "sweep": False, "best_percent": 100.0, "reloc_ok": True,
                 "bytes_ok": True, "splice_ok": True, "sweep_hit": None,
                 "source": "checks/0001.c"}  # fmt: skip


def _canary_rig(tmp_path, scenario: str, *, write: str | None = None, after=None,
                check: dict | None = PASSING_CHECK,
                raises: BaseException | None = None) -> Rig:  # fmt: skip
    """A rig whose session is fakeclaude replaying `scenario` through the real run_session,
    writing `write` (repo-relative) like a tool call that went through; `check` is the
    checks.jsonl line the wrapper's `attempt check` would have logged (None: no log);
    `after(repo)` runs once the stream ended (a stray the session left); `raises` is raised by
    the session instead."""
    rig = Rig(tmp_path)
    rig.launches = []

    def argv(prompt: str):
        rig.prompt = prompt
        cmd = [sys.executable, str(FAKE), "--scenario", scenario]
        return cmd + (["--write", write] if write else [])

    def session(argv, *, cwd, env, transcript, timeout_s):
        rig.launches.append(Launch(list(argv), dict(env), Path(cwd)))
        if raises is not None:
            raise raises
        result = run_session(argv, cwd=cwd, env=env, transcript=transcript, timeout_s=timeout_s)
        if check is not None:
            _write(Path(env["REVERSEAPOC_ATTEMPT_DIR"]) / "checks.jsonl", json.dumps(check) + "\n")
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
                   "attempt check", "git status"):  # fmt: skip
        assert needle in texts, needle
    assert len(rig.launches) == 1
    assert not rig.commands("gate")


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
                  "uv run --frozen reverseapoc attempt check"):  # fmt: skip
        assert words in rig.prompt, words


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
