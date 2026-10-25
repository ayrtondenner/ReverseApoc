"""The night driver (plan 06-23; AGT-01..AGT-04, AGT-06; D-05, D-07, D-08, D-17, D-24, D-25, D-34).

Owner rule: no test runs the real `claude` or docker. Every session here is tests/fakeclaude.py
replaying a synthetic stream through the real session.run_session, in a tmp git repo that stands
in for the checkout; the gate, the partial gate, the lint, the pack, the scaffold and the
container cleanup are fakes that record their calls. Every name, address and SHA-1 below is made
up (the fixtures' own `src/ufo2p/u_00010000.c` claim).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from reverseapoc import attempt
from reverseapoc.driver import (
    COAUTHOR,
    MATCHED_BY,
    Deps,
    DriveConfig,
    DriveReport,
    GateRun,
    PackInfo,
    drive,
    git_runner,
)
from reverseapoc.picker import Pick
from reverseapoc.session import run_session

FAKE = Path(__file__).resolve().parent / "fakeclaude.py"
EXE = "ufo2p"
UNIT = "u_00010000"  # the unit the stream fixtures' tool_use names
START = 0x00010010
FUNC = f"func_{START:08X}"
UNIT_REL = f"src/{EXE}/{UNIT}.c"
RUN = "night1"
PICK = Pick(EXE, START, FUNC, UNIT, 20, 100)
SHA_UFO2P = "1" * 40  # made up, never a manifest hash
SHA_TACP = "2" * 40
SCAFFOLD = f'#include "common.h"\n\nINCLUDE_ASM({FUNC});\n'
STATUS_HEAD = "# written by: gate (made up)\nstart,name,unit,status,best_percent,attempts\n"
LOG = "progress/attempts.jsonl"


class _Env(dict):
    """A subprocess environment whose repr stays short (no user variables in a failing assert)."""

    def __repr__(self) -> str:
        return "<env>"


def _git_env(tmp_path: Path) -> _Env:
    """The current environment without CLAUDECODE and git's overrides, an empty global config
    and a made-up identity, so the user's own git settings and hooks cannot leak in."""
    env = _Env(
        (k, v)
        for k, v in os.environ.items()
        if k != "CLAUDECODE" and not (k.startswith("GIT_") and k != "GIT_EXEC_PATH")
    )
    config = tmp_path / "global.gitconfig"
    config.touch()
    env["GIT_CONFIG_GLOBAL"] = str(config)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    identity = {"user.name": "Driver Test", "user.email": "driver@example.invalid",
                "init.defaultBranch": "main", "core.autocrlf": "false"}  # fmt: skip
    for i, (key, value) in enumerate(identity.items()):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    env["GIT_CONFIG_COUNT"] = str(len(identity))
    return env


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _git(repo: Path, env: dict, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, check=True)
    return done.stdout.decode("utf-8")


def _make_repo(tmp_path: Path, env: dict, *, unit: bool) -> Path:
    repo = tmp_path / "repo"
    files = {
        ".gitignore": "build/\n",
        "include/common.h": "/* made up */\n",
        f"config/{EXE}/status.csv": STATUS_HEAD,
        "config/tacp/status.csv": STATUS_HEAD,
        "decomphub.progress.json": "{}\n",
        LOG: "",
        "tools/keep.py": "# made up\n",
    }
    if unit:
        files[UNIT_REL] = SCAFFOLD
    for rel, text in files.items():
        _write(repo / rel, text)
    _git(repo, env, "init", "-q")
    _git(repo, env, "add", "--", *files)
    _git(repo, env, "commit", "-q", "-m", "base")
    return repo


@dataclass(frozen=True)
class Sess:
    """One scripted session: the stream fixture fakeclaude replays, the repo-relative file it
    writes (`--write`), extra files the "agent" leaves (written after the stream), the
    checks.jsonl lines the wrapper would have logged, a wall-clock timeout, or an exception."""

    scenario: str = "success"
    write: str | None = UNIT_REL
    files: tuple[tuple[str, str], ...] = ()
    checks: tuple[dict, ...] = ()
    timeout: bool = False
    raises: BaseException | None = None


@dataclass
class Launch:
    argv: list[str]
    env: dict[str, str]
    cwd: Path
    timeout_s: float


def check_line(n: int, percent: float | None, *, sweep: bool = False, exit_code: int = 1,
               sweep_hit: str | None = None) -> dict:  # fmt: skip
    """A checks.jsonl line as attempt.CheckLogLine writes it."""
    return {"n": n, "exit": exit_code, "sweep": sweep, "best_percent": percent,
            "reloc_ok": None if percent is None else percent == 100.0,
            "bytes_ok": None if percent is None else percent == 100.0,
            "splice_ok": None if sweep else True, "sweep_hit": sweep_hit,
            "source": f"checks/{n:04d}.c"}  # fmt: skip


class _JumpClock:
    """A clock for run_session that is past any deadline after its first reading: the session
    times out deterministically, without a real wait."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return 0.0 if self.calls == 1 else 1.0e9


@dataclass
class Night:
    """A tmp repo plus the fakes of one night. `run()` drives it and keeps the report."""

    tmp_path: Path
    sessions: list[Sess] = field(default_factory=list)
    gate_exits: list[int] = field(default_factory=list)
    lint_exits: list[int] = field(default_factory=list)
    partial_exits: list[int] = field(default_factory=list)
    picks: tuple[Pick, ...] = (PICK,)
    unit_committed: bool = True

    def __post_init__(self) -> None:
        self.env = _git_env(self.tmp_path)
        self.repo = _make_repo(self.tmp_path, self.env, unit=self.unit_committed)
        self.base = _git(self.repo, self.env, "rev-parse", "HEAD").strip()
        self.launched: list[Launch] = []
        self.git_calls: list[list[str]] = []
        self.gate_calls: list[tuple[Pick, int]] = []
        self.partial_calls: list[tuple[Pick, str, int, str]] = []
        self.lint_calls: list[Pick] = []
        self.removed: list[str] = []
        self.scaffolded: list[Pick] = []
        self.sleeps: list[float] = []
        self.now = 1000.0
        self._current = Sess()
        self._git = git_runner(self.repo, env=self.env)

    # --- the fakes ---

    def _queue(self, difficult):
        return [p for p in self.picks if (p.exe, p.start) not in difficult]

    def _scaffold(self, pick: Pick) -> None:
        self.scaffolded.append(pick)
        _write(self.repo / f"src/{pick.exe}/{pick.unit}.c", SCAFFOLD)

    def _pack(self, pick: Pick, attempt_dir: Path) -> PackInfo:
        _write(attempt_dir / "context.md", "made-up pack\n")
        return PackInfo(2048, ("look-alikes",))

    def _argv(self, prompt: str) -> list[str]:
        self._current = self.sessions.pop(0) if self.sessions else Sess(write=None)
        spec = self._current
        argv = [sys.executable, str(FAKE), "--scenario", spec.scenario]
        return argv + (["--write", spec.write] if spec.write else [])

    def _session(self, argv, *, cwd, env, transcript, timeout_s):
        spec = self._current
        self.launched.append(Launch(list(argv), dict(env), Path(cwd), timeout_s))
        self.now += 45.0
        if spec.raises is not None:
            raise spec.raises
        extra = {"clock": _JumpClock()} if spec.timeout else {}
        result = run_session(argv, cwd=cwd, env=env, transcript=transcript, timeout_s=timeout_s,
                             **extra)  # fmt: skip
        for rel, text in spec.files:
            _write(Path(cwd) / rel, text)
        attempt_dir = Path(env[attempt.DIR_ENV])
        for line in spec.checks:
            _write(attempt_dir / line["source"], f"/* made-up C of check {line['n']} */\n")
            with (attempt_dir / attempt.CHECK_LOG).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, sort_keys=True) + "\n")
        return result

    def _lint(self, pick: Pick) -> int:
        self.lint_calls.append(pick)
        return self.lint_exits.pop(0) if self.lint_exits else 0

    def _gate(self, pick: Pick, attempts: int) -> GateRun:
        self.gate_calls.append((pick, attempts))
        code = self.gate_exits.pop(0) if self.gate_exits else 1
        if code == 0:
            status = self.repo / f"config/{pick.exe}/status.csv"
            with status.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(f"0x{pick.start:08X},{pick.name},{pick.unit},matched,100.00,{attempts}\n")
            _write(self.repo / "decomphub.progress.json", '{"matched": 1}\n')
        doc = {"ok": code == 0, "checks": [{"splice": [{"exe": "UFO2P.EXE", "sha1": SHA_UFO2P},
                                                       {"exe": "TACP.EXE", "sha1": SHA_TACP}]}]}
        return GateRun(code, doc)

    def _partial(self, pick: Pick, src: str, attempts: int) -> int:
        saved = (self.repo / src).read_text(encoding="utf-8")
        self.partial_calls.append((pick, src, attempts, saved))
        code = self.partial_exits.pop(0) if self.partial_exits else 0
        if code == 0:
            status = self.repo / f"config/{pick.exe}/status.csv"
            with status.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(f"0x{pick.start:08X},{pick.name},{pick.unit},partial,50.00,{attempts}\n")
        return code

    def _recorded_git(self, args):
        self.git_calls.append(list(args))
        return self._git(args)

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def deps(self, **over) -> Deps:
        fields = dict(queue=self._queue, requeue=lambda difficult: (),
                      matched_callees=lambda pick: (), scaffold=self._scaffold, pack=self._pack,
                      argv=self._argv, session=self._session, lint=self._lint, gate=self._gate,
                      partial_gate=self._partial, remove_containers=self.removed.append,
                      git=self._recorded_git, clock=lambda: self.now, sleep=self._sleep,
                      today=lambda: "2026-10-25")  # fmt: skip
        fields.update(over)
        return Deps(**fields)

    def config(self, **over) -> DriveConfig:
        fields = dict(run_id=RUN, repo_root=self.repo, tested_major=2,
                      min_cli_version=(2, 1, 240), base_env=self.env)  # fmt: skip
        fields.update(over)
        return DriveConfig(**fields)

    def run(self, config: dict | None = None, **deps) -> DriveReport:
        self.report = drive(self.config(**(config or {})), self.deps(**deps))
        return self.report

    # --- reading the result ---

    def git(self, *args: str) -> str:
        return _git(self.repo, self.env, *args)

    def commits(self) -> list[str]:
        """The subjects of the commits the night made, oldest first."""
        out = self.git("log", "--reverse", "--format=%s", f"{self.base}..HEAD")
        return out.splitlines()

    def sha(self, subject_prefix: str) -> str:
        for line in self.git("log", "--format=%H %s", f"{self.base}..HEAD").splitlines():
            sha, subject = line.split(" ", 1)
            if subject.startswith(subject_prefix):
                return sha
        raise AssertionError(f"no commit starting {subject_prefix!r}")

    def commit_files(self, subject_prefix: str) -> list[str]:
        sha = self.sha(subject_prefix)
        return sorted(self.git("show", "--format=", "--name-only", sha).split())

    def file_at(self, subject_prefix: str, rel: str) -> str:
        return self.git("show", f"{self.sha(subject_prefix)}:{rel}")

    def message(self, subject_prefix: str) -> str:
        for sha in self.git("log", "--format=%H", f"{self.base}..HEAD").split():
            body = self.git("log", "-1", "--format=%B", sha)
            if body.startswith(subject_prefix):
                return body
        raise AssertionError(f"no commit starting {subject_prefix!r}")

    def records(self) -> list[dict]:
        text = (self.repo / LOG).read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def kinds(self, kind: str) -> list[dict]:
        return [r for r in self.records() if r.get("kind") == kind]

    def attempt_dir(self, n: int = 1, func: str = FUNC) -> Path:
        return self.repo / "build" / "driver" / RUN / EXE / func / f"attempt-{n}"


MATCH_SUBJECT = f"feat({EXE}): match {FUNC} in {UNIT} (C89)"


# ---- Task 1: the tracer ----


def test_match_commits_one_function(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    assert [s for s in night.commits() if s.startswith("feat(")] == [MATCH_SUBJECT]
    assert night.commit_files("feat(") == sorted(
        [UNIT_REL, f"config/{EXE}/status.csv", "decomphub.progress.json", LOG])
    body = night.message("feat(")
    for needle in ("attempt 1/3", "model claude-opus-5-5", "turns 3", "1200 input",
                   "300 output", "5000 cache read", "800 cache creation", "seconds 45",
                   "objdiff 100%", "relocation ok", f"UFO2P.EXE {SHA_UFO2P}",
                   f"TACP.EXE {SHA_TACP}"):  # fmt: skip
        assert needle in body, needle
    assert body.rstrip("\n").splitlines()[-2:] == [COAUTHOR, MATCHED_BY]
    assert night.gate_calls == [(PICK, 1)]
    adds = [call for call in night.git_calls if call[:1] == ["add"]]
    assert adds and all(call[1] == "--" for call in adds)
    assert not [c for c in night.git_calls if "-A" in c or "--all" in c or c[-1:] == ["."]]
    commit = next(call for call in night.git_calls if call[:1] == ["commit"])
    assert "-F" in commit and commit[commit.index("--") + 1:] == adds[0][2:]


def test_match_record_is_appended(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    attempts = night.kinds("attempt")
    assert len(attempts) == 1
    record = attempts[0]
    assert (record["outcome"], record["exe"], record["function"], record["unit"],
            record["attempt"], record["run"]) == ("MATCHED", EXE, FUNC, UNIT, 1, RUN)  # fmt: skip
    assert '"outcome":"MATCHED"' in night.file_at("feat(", LOG)  # the record rides the match


def test_session_env_names_the_claim(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    assert len(night.launched) == 1
    launch = night.launched[0]
    attempt_dir = night.attempt_dir(1)
    assert launch.env["REVERSEAPOC_CLAIM"] == f"{EXE}/{UNIT}"
    assert launch.env["REVERSEAPOC_FUNC"] == FUNC
    assert launch.env["REVERSEAPOC_ATTEMPT_DIR"] == str(attempt_dir)  # absolute (F28)
    assert launch.env["REVERSEAPOC_ATTEMPT_NOTES"] == str(attempt_dir / "notes.md")
    assert Path(launch.env["REVERSEAPOC_ATTEMPT_DIR"]).is_absolute()
    assert launch.cwd == night.repo  # F11: the session runs in the checkout root
    assert launch.timeout_s == 1800
    assert (attempt_dir / "transcript.jsonl").is_file()
    assert night.removed == [attempt.container_prefix(attempt_dir)]


def test_match_commit_adds_new_files(tmp_path):
    """F5: a unit scaffolded in the attempt (untracked) and a new include/x.h land in the
    match commit through `git add -- <paths>`."""
    night = Night(tmp_path, unit_committed=False, gate_exits=[0],
                  sessions=[Sess(files=(("include/x.h", "/* made-up header */\n"),))])  # fmt: skip
    night.run()
    assert night.scaffolded == [PICK]
    assert night.commit_files("feat(") == sorted(
        [UNIT_REL, "include/x.h", f"config/{EXE}/status.csv", "decomphub.progress.json", LOG])
