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
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from reverseapoc import cli, driver
from reverseapoc.driver import DriveOptions, ExeWorld, PackInfo, Seams
from reverseapoc.picker import Pick
from reverseapoc.score import Candidate
from test_driver import _git, _git_env, _write

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
