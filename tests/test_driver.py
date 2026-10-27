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

import pytest

from reverseapoc import attempt, driver, hooks
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
VIEW = "<view unit>"  # Sess.write: the session edits its view unit (fakeclaude --write-env-unit)
SESSION_TEXT = "/* written by tests/fakeclaude.py */\nint fake_written;\n"


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
        ".gitignore": "build/\n.venv/\n.claude/settings.local.json\n.claude/hooks/\n"
        ".claude/worktrees/\n__pycache__/\n",
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
    """One scripted session: the stream fixture fakeclaude replays, the file it writes (VIEW,
    the default: its view unit, 07-13; else a repo-relative path written directly, `--write`),
    extra files the "agent" leaves (written after the stream), the
    checks.jsonl lines the wrapper would have logged, a wall-clock timeout, or an exception
    (raised after `files` are written). `link` plants (repo-relative link, target directory):
    a junction on Windows (no privilege needed), a symlink elsewhere."""

    scenario: str = "success"
    write: str | None = VIEW
    files: tuple[tuple[str, str], ...] = ()
    checks: tuple[dict, ...] = ()
    timeout: bool = False
    raises: BaseException | None = None
    link: tuple[str, Path] | None = None
    append: tuple[tuple[str, str], ...] = ()  # (repo-relative file, text appended to it)
    unit_text: str | None = None  # 07-13: fakeclaude --write-env-unit, the view unit's new text


def _plant_dir_link(link: Path, target: Path) -> None:
    """A directory link that needs no privilege: a junction on Windows, a symlink elsewhere. An
    empty directory already there (the driver's quarantine root) is replaced."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_dir() and not any(link.iterdir()):
        link.rmdir()
    elif link.is_dir():
        link.rename(link.with_name(link.name + ".moved"))  # the session swapped the directory
    elif link.is_file():
        link.unlink()  # the session replaced a file by a directory link
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


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
    # The starts a passing gate writes matched rows for, like the real gate's JSON `written`
    # (every function of the unit that passed). None: the claimed pick's start only.
    gate_written: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        self.tmp_path.mkdir(parents=True, exist_ok=True)
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
        self.scaffold_dests: list[Path | None] = []  # 07-13: where each scaffold was written
        self.packed: list[tuple[Pick, Path, Path | None]] = []  # (pick, attempt dir, src root)
        self.seen: list[dict] = []  # 07-13: the view and src/ unit as each session found them
        self.sleeps: list[float] = []
        self.now = 1000.0
        self.inject: list[str] = []
        self.on_git = None  # called with each git argv before it runs
        self.gate_names = ("UFO2P.EXE", "TACP.EXE")  # the EXE names the fake gate reports
        self.git_at_launch = -1
        self.prompts: list[str] = []
        self.raise_verbs: dict[str, BaseException] = {}  # git verb -> exception, raised once
        self.fail_verbs: dict[str, int] = {}  # git verb -> how many calls fail with LOCK_ERROR
        self.fail_plan: dict[str, list[bool]] = {}  # git verb -> per-call schedule
        self.fail_from_launch = 1  # failures arm once this many sessions have launched
        self._current = Sess()
        self._git = git_runner(self.repo, env=self.env)

    # --- the fakes ---

    def _queue(self, difficult):
        return [p for p in self.picks if (p.exe, p.start) not in difficult]

    def _scaffold(self, pick: Pick, dest: Path | None = None) -> None:
        self.scaffolded.append(pick)
        self.scaffold_dests.append(dest)
        _write(dest if dest is not None else self.repo / f"src/{pick.exe}/{pick.unit}.c", SCAFFOLD)

    def _pack(self, pick: Pick, attempt_dir: Path, src: Path | None = None) -> PackInfo:
        self.packed.append((pick, attempt_dir, src))
        _write(attempt_dir / "context.md", "made-up pack\n")
        return PackInfo(2048, ("look-alikes",))

    def _argv(self, prompt: str) -> list[str]:
        self._current = self.sessions.pop(0) if self.sessions else Sess(write=None)
        self.prompts.append(prompt)
        spec = self._current
        argv = [sys.executable, str(FAKE), "--scenario", spec.scenario, "--env-unit-paths"]
        text = spec.unit_text or (SESSION_TEXT if spec.write == VIEW else None)
        argv += ["--write", spec.write] if spec.write and spec.write != VIEW else []
        return argv + (["--write-env-unit", text] if text else [])

    def _see(self, env: dict) -> None:
        """07-13: what the session finds at launch: every file of its view (bytes), the view's
        directories, and whether src/ holds the claimed unit."""
        view = Path(env[attempt.DIR_ENV]) / "view"
        files = {p.relative_to(view).as_posix(): p.read_bytes()
                 for p in sorted(view.rglob("*")) if p.is_file()}  # fmt: skip
        dirs = {p.relative_to(view).as_posix() for p in view.rglob("*") if p.is_dir()}
        unit = self.repo / f"src/{EXE}/{UNIT}.c"
        self.seen.append({"files": files, "dirs": dirs, "view": view.is_dir(),
                          "src_unit": unit.read_bytes() if unit.is_file() else None})  # fmt: skip

    def _session(self, argv, *, cwd, env, transcript, timeout_s):
        spec = self._current
        self.launched.append(Launch(list(argv), dict(env), Path(cwd), timeout_s))
        self._see(env)
        self.git_at_launch = len(self.git_calls)
        self.now += 45.0
        if spec.raises is not None:
            for rel, text in spec.files:
                _write(Path(cwd) / rel, text)
            raise spec.raises
        extra = {"clock": _JumpClock()} if spec.timeout else {}
        result = run_session(argv, cwd=cwd, env=env, transcript=transcript, timeout_s=timeout_s,
                             **extra)  # fmt: skip
        for rel, text in spec.files:
            _write(Path(cwd) / rel, text)
        for rel, text in spec.append:
            with (Path(cwd) / rel).open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        if spec.link is not None:
            _plant_dir_link(Path(cwd) / spec.link[0], spec.link[1])
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
        written = []
        if code == 0:
            rel = f"config/{pick.exe}/status.csv"
            starts = (pick.start,) if self.gate_written is None else self.gate_written
            with (self.repo / rel).open("a", encoding="utf-8", newline="\n") as fh:
                for start in starts:
                    name = f"func_{start:08X}"
                    fh.write(f"0x{start:08X},{name},{pick.unit},matched,100.00,{attempts}\n")
                    written.append({"path": rel, "start": f"0x{start:08X}", "name": name,
                                    "unit": pick.unit, "status": "matched"})  # fmt: skip
            _write(self.repo / "decomphub.progress.json", '{"matched": 1}\n')
        doc = {
            "ok": code == 0,
            "written": written,
            "checks": [
                {
                    "splice": [
                        {"exe": self.gate_names[0], "sha1": SHA_UFO2P},
                        {"exe": self.gate_names[1], "sha1": SHA_TACP},
                    ]
                }
            ],
        }
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
        """The real git in the tmp repo, recording every argv. After the first launch, a
        `status` also reports the made-up untracked entries in `self.inject` (a name NTFS
        cannot hold, such as `include/*.h`, can only reach the driver this way)."""
        self.git_calls.append(list(args))
        if self.on_git is not None:
            self.on_git(list(args))
        verb = _verb(list(args))
        if self.launched and verb in self.raise_verbs:  # once, after the first launch
            raise self.raise_verbs.pop(verb)
        armed = len(self.launched) >= self.fail_from_launch
        if armed and self.fail_verbs.get(verb, 0) > 0:  # a lock someone else holds
            self.fail_verbs[verb] -= 1
            return subprocess.CompletedProcess(args, 128, b"", LOCK_ERROR)
        if armed and self.fail_plan.get(verb):  # per call: True fails, False runs
            if self.fail_plan[verb].pop(0):
                return subprocess.CompletedProcess(args, 128, b"", LOCK_ERROR)
        done = self._git(args)
        if "status" in args and self.launched and self.inject:
            extra = b"".join(f"?? {path}\0".encode() for path in self.inject)
            out = (done.stdout or b"") + extra
            done = subprocess.CompletedProcess(done.args, done.returncode, out, done.stderr)
        return done

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

    @property
    def quarantine(self) -> Path:
        return self.repo / "build" / "driver" / RUN / "quarantine"

    def attempt_dir(self, n: int = 1, func: str = FUNC) -> Path:
        return self.repo / "build" / "driver" / RUN / EXE / func / f"attempt-{n}"


MATCH_SUBJECT = f"feat({EXE}): match {FUNC} in {UNIT} (C89)"
LOCK_ERROR = b"fatal: Unable to create '.git/index.lock': File exists (made up).\n"
FEED_NAME = "decomphub.progress.json"


def _verb(call: list[str]) -> str | None:
    """The git subcommand of a recorded argv (the first token that is not a global option)."""
    return next((token for token in call if not token.startswith("-")), None)


# ---- Task 1: the tracer ----


def test_match_commits_one_function(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    assert [s for s in night.commits() if s.startswith("feat(")] == [MATCH_SUBJECT]
    assert night.commit_files("feat(") == sorted(
        [UNIT_REL, f"config/{EXE}/status.csv", "decomphub.progress.json", LOG]
    )
    body = night.message("feat(")
    for needle in ("attempt 1/3", "model claude-opus-5-5", "turns 3", "1200 input",
                   "300 output", "5000 cache read", "800 cache creation", "seconds 45",
                   "objdiff 100%", "relocation ok", f"UFO2P.EXE {SHA_UFO2P}",
                   f"TACP.EXE {SHA_TACP}"):  # fmt: skip
        assert needle in body, needle
    assert body.rstrip("\n").splitlines()[-2:] == [COAUTHOR, MATCHED_BY]
    assert night.gate_calls == [(PICK, 1)]
    adds = [call for call in night.git_calls if _verb(call) == "add"]
    assert adds and all(call[call.index("add") + 1] == "--" for call in adds)
    assert not [c for c in night.git_calls if "-A" in c or "--all" in c or c[-1:] == ["."]]
    commit = next(call for call in night.git_calls if _verb(call) == "commit")
    assert "-F" in commit and commit[commit.index("--") + 1 :] == adds[0][adds[0].index("--") + 1 :]
    # Security ruling (06-23 commit_match): paths are never globs.
    assert all(call[0] == "--literal-pathspecs" for call in night.git_calls
               if _verb(call) in ("add", "commit"))  # fmt: skip


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
    """F5: a unit scaffolded in the attempt (untracked at HEAD) lands in the match commit
    through `git add -- <paths>`. 07-13 (D-19): a matching session writes no header, so the old
    include/x.h half of this test is now test_no_header_is_committed."""
    night = Night(tmp_path, unit_committed=False, gate_exits=[0], sessions=[Sess()])
    night.run()
    assert night.scaffolded == [PICK]
    assert night.commit_files("feat(") == sorted(
        [UNIT_REL, f"config/{EXE}/status.csv", "decomphub.progress.json", LOG]
    )


# ---- Task 2: caps, backoff, stop classes, the audit and the reset ----


def _pick(i: int) -> Pick:
    start = START + 0x10 * i
    return Pick(EXE, start, f"func_{start:08X}", UNIT, 20, 100 + i)


def _runs(night: Night) -> list[tuple[str, str]]:
    return [(r["event"], r["reason"]) for r in night.kinds("run")]


def _unit_text(night: Night) -> str:
    return (night.repo / UNIT_REL).read_text(encoding="utf-8")


def _one(items: list):
    assert len(items) == 1, items
    return items[0]


def _feats(night: Night) -> list[str]:
    return [s for s in night.commits() if s.startswith("feat(")]


def test_partial_resets_and_logs(tmp_path):
    """F10/F7: the best C is the checks/NNNN.c of the highest plain best_percent (ties go to the
    earliest; sweep lines and null percents never count), saved under best/ and passed to the
    partial gate as a repo-relative POSIX path."""
    checks = (check_line(1, 40.0), check_line(2, 73.5), check_line(3, 73.5),
              check_line(4, 100.0, sweep=True, exit_code=0, sweep_hit="wcc386@10.5 -4r -ox"),
              check_line(5, None))  # fmt: skip
    night = Night(tmp_path, sessions=[Sess(checks=checks)], gate_exits=[1])
    night.run(config={"attempts_per_function": 1})
    assert _unit_text(night) == SCAFFOLD  # restored to HEAD
    best = night.attempt_dir(1) / "best" / f"{UNIT}.c"
    assert best.read_text(encoding="utf-8") == "/* made-up C of check 2 */\n"
    src = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/best/{UNIT}.c"
    assert [(p, s, n) for p, s, n, _ in night.partial_calls] == [(PICK, src, 1)]
    record = _one(night.kinds("attempt"))
    assert record["outcome"] == "PARTIAL"
    assert record["check"]["best_percent"] == 73.5
    assert record["check"]["runs"] == 5
    assert record["check"]["sweep_hit"] == "wcc386@10.5 -4r -ox"
    assert record["check"]["needs"] == "needs flags wcc386@10.5 -4r -ox"
    assert _feats(night) == []


def test_gave_up_resets(tmp_path):
    night = Night(tmp_path, unit_committed=False,
                  sessions=[Sess(checks=(check_line(1, 0.0), check_line(2, None)))])  # fmt: skip
    night.run(config={"attempts_per_function": 1})
    assert night.scaffolded == [PICK]
    assert not (night.repo / UNIT_REL).exists()  # the unit scaffolded this attempt is deleted
    record = _one(night.kinds("attempt"))
    assert record["outcome"] == "GAVE_UP"
    assert night.partial_calls == []


def test_hundred_percent_with_failing_gate_is_partial(tmp_path):
    """AGT-03 adjacency: objdiff 100.0 in the check log, but the gate exits 1 (a relocation
    check fails): PARTIAL, never MATCHED, nothing committed."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 100.0, exit_code=0),))],
                  gate_exits=[1])  # fmt: skip
    night.run(config={"attempts_per_function": 1})
    record = _one(night.kinds("attempt"))
    assert record["outcome"] == "PARTIAL"
    assert night.gate_calls == [(PICK, 1)]
    assert _feats(night) == []
    assert night.report.matched == 0


def _difficult(night: Night) -> list[dict]:
    path = night.repo / "build" / "driver" / "difficult.json"
    return json.loads(path.read_text(encoding="utf-8"))["difficult"]


def test_three_attempts_then_difficult(tmp_path):
    """AGT-02 adjacency: attempt 3 of 3 runs, no fourth session starts in the pass, and the
    function lands on the difficult list exactly once."""
    night = Night(tmp_path, sessions=[Sess(), Sess(), Sess(), Sess()])
    night.run()
    assert len(night.launched) == 3
    assert [r["attempt"] for r in night.kinds("attempt")] == [1, 2, 3]
    assert [(e["exe"], e["start"]) for e in _difficult(night)] == [(EXE, f"0x{START:08X}")]


def test_difficult_returns_only_through_requeue(tmp_path):
    night = Night(tmp_path, sessions=[Sess()] * 3)
    night.run()
    night.run()  # the difficult function is skipped: requeue gives nothing back
    assert len(night.launched) == 3
    assert _runs(night)[-1] == ("ENDED", "nothing to do")
    night.run(requeue=lambda difficult: tuple(difficult))  # requeued: eligible again
    assert len(night.launched) == 6
    assert len(_difficult(night)) == 1


def test_empty_queue_runs_nothing(tmp_path):
    night = Night(tmp_path, picks=())
    report = night.run()
    assert night.launched == []
    assert _runs(night) == [("STARTED", "start"), ("ENDED", "nothing to do")]
    assert (report.event, report.reason, report.exit_code) == ("ENDED", "nothing to do", 0)


def test_max_sessions_and_target_matched(tmp_path):
    night = Night(tmp_path / "a", picks=tuple(_pick(i) for i in range(3)))
    report = night.run(config={"max_sessions": 2})
    assert len(night.launched) == 2
    assert (report.reason, report.sessions) == ("max sessions", 2)
    night = Night(tmp_path / "b", picks=tuple(_pick(i) for i in range(3)),
                  sessions=[Sess()] * 3, gate_exits=[0, 0, 0])  # fmt: skip
    report = night.run(config={"target_matched": 2})
    assert len(night.launched) == 2
    assert (report.reason, report.matched) == ("target matched", 2)
    assert len(_feats(night)) == 2


def test_limit_backs_off_and_is_not_counted(tmp_path):
    sessions = [Sess("rate_limit", write=None), Sess("rate_limit", write=None), Sess()]
    night = Night(tmp_path, sessions=sessions, gate_exits=[0])
    report = night.run()
    assert night.sleeps == [60, 120]
    assert report.sessions == 1
    assert [(r["attempt"], r["outcome"]) for r in night.kinds("attempt")] == [(1, "MATCHED")]


def test_limit_polls_every_five_minutes(tmp_path):
    sessions = [Sess("rate_limit", write=None)] * 5 + [Sess()]
    night = Night(tmp_path, sessions=sessions, gate_exits=[0])
    night.run()
    assert night.sleeps == [60, 120, 240, 300, 300]
    assert night.report.sessions == 1


def test_a_limit_relaunch_gets_a_fresh_attempt_dir(tmp_path):
    """The uncounted launch's directory moves aside, so the counted session starts with no
    stale checks.jsonl (its 90.0 must not make the attempt PARTIAL)."""
    sessions = [Sess("rate_limit", write=None, checks=(check_line(1, 90.0),)), Sess()]
    night = Night(tmp_path, sessions=sessions)
    night.run(config={"attempts_per_function": 1})
    record = _one(night.kinds("attempt"))
    assert record["outcome"] == "GAVE_UP"
    aside = night.attempt_dir(1).parent / "attempt-1-uncounted-1"
    assert (aside / "transcript.jsonl").is_file()
    assert not (night.attempt_dir(1) / attempt.CHECK_LOG).exists()


def test_limit_session_keeps_its_work(tmp_path):
    """06-17 review: a session the stream classifies LIMIT keeps its work: the gate runs on it
    as usual and a pass is a counted MATCHED, before the backoff."""
    night = Night(tmp_path, sessions=[Sess("rejected")], gate_exits=[0])
    report = night.run()
    assert _feats(night) == [MATCH_SUBJECT]
    assert night.sleeps == [60]
    assert (report.sessions, report.matched) == (1, 1)


@pytest.mark.parametrize(("scenario", "reason"), [
    ("auth", "stop signal"), ("billing", "stop signal"), ("credits", "stop signal"),
    ("not_logged_in", "stop signal"), ("bad_init_model", "init"), ("bad_init_v3", "init"),
])  # fmt: skip
def test_stop_classes_end_the_run(tmp_path, scenario, reason):
    night = Night(tmp_path, sessions=[Sess(scenario)], picks=(_pick(0), _pick(1)))
    report = night.run()
    assert len(night.launched) == 1
    assert [r for r in _runs(night) if r[0] == "STOPPED"] == [("STOPPED", reason)]
    assert (report.event, report.reason, report.exit_code) == ("STOPPED", reason, 1)
    assert _unit_text(night) == SCAFFOLD
    assert night.kinds("attempt") == []


def test_transient_retries_then_aborts(tmp_path):
    """AGT-03 empty, D-08 literally ("3 retries, then the attempt is aborted"): the first
    launch and 3 retries without a result -> one abort record with retries 3, no tri-state
    record (minor 6)."""
    sessions = [Sess("overloaded", write=None), Sess("no_result", write=None),
                Sess("overloaded", write=None), Sess("no_result", write=None)]  # fmt: skip
    night = Night(tmp_path, sessions=sessions)
    report = night.run()
    assert len(night.launched) == 4
    abort = _one(night.kinds("abort"))
    assert (abort["abort_reason"], abort["retries"], abort["attempt"]) == ("transient", 3, 1)
    assert night.kinds("attempt") == []
    assert report.sessions == 0


def test_stray_write_resets_and_stops(tmp_path):
    """D-17: a write outside the allowlist resets the attempt and stops the night. F11: the
    session ran in the tmp checkout, so the real checkout never got the file."""
    sess = Sess(write="tools/x.py", files=((UNIT_REL, "int edited;\n"),))
    night = Night(tmp_path, picks=(_pick(0), _pick(1)), sessions=[sess])
    report = night.run()
    assert len(night.launched) == 1
    assert [r for r in _runs(night) if r[0] == "STOPPED"] == [("STOPPED", "guardrail")]
    assert "tools/x.py" in report.detail
    assert _unit_text(night) == SCAFFOLD
    # Security ruling (guardrail stop): never left in place, never deleted: quarantined.
    assert not (night.repo / "tools" / "x.py").exists()
    assert (night.quarantine / "tools" / "x.py").is_file()
    assert not (Path(__file__).resolve().parents[1] / "tools" / "x.py").exists()
    assert night.gate_calls == []


def test_session_editing_status_stops_the_night(tmp_path):
    """F3: the session wrote config/ufo2p/status.csv, which only gate may write."""
    night = Night(tmp_path, sessions=[Sess(write=f"config/{EXE}/status.csv")])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")


def test_partial_then_second_session_has_no_guardrail_stop(tmp_path):
    """F3: the driver's own uncommitted changes (attempts.jsonl, partial status.csv rows) sit
    in the pre-session snapshot, so the next session is not a breach."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),)), Sess()])
    report = night.run(config={"attempts_per_function": 2})
    assert len(night.launched) == 2
    assert [r["outcome"] for r in night.kinds("attempt")] == ["PARTIAL", "GAVE_UP"]
    assert report.event == "ENDED"


def test_timeout_is_counted(tmp_path):
    night = Night(tmp_path, sessions=[Sess("no_result", write=None, timeout=True)])
    report = night.run(config={"attempts_per_function": 1})
    record = _one(night.kinds("attempt"))
    assert (record["outcome"], record["abort_reason"]) == ("GAVE_UP", "timeout")
    assert report.sessions == 1


def test_lint_failure_with_a_score_is_partial_and_commits_nothing(tmp_path):
    """06-15 note: the C89 lint runs before a match is committed; a failed lint after a check
    scored above 0% is PARTIAL "lint" and the gate never runs."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),))], gate_exits=[0],
                  lint_exits=[1])  # fmt: skip
    night.run(config={"attempts_per_function": 1})
    assert night.lint_calls == [PICK]
    assert night.gate_calls == []
    record = _one(night.kinds("attempt"))
    assert (record["outcome"], record["abort_reason"]) == ("PARTIAL", "lint")
    assert _feats(night) == []


def test_lint_failure_without_a_score_is_gave_up(tmp_path):
    """Review IN-02: PARTIAL means a score above 0% in objdiff (README), so a failed lint with
    no check above 0% is GAVE_UP "lint", and status.csv is untouched."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0], lint_exits=[1])
    night.run(config={"attempts_per_function": 1})
    assert night.lint_calls == [PICK]
    assert night.gate_calls == []
    record = _one(night.kinds("attempt"))
    assert (record["outcome"], record["abort_reason"]) == ("GAVE_UP", "lint")
    assert record["check"]["best_percent"] is None
    assert _feats(night) == []


def test_session_exception_stops_the_run(tmp_path):
    """06-17 note: run_session re-raises after killing the tree; the driver records a STOP."""
    night = Night(tmp_path, sessions=[Sess(raises=RuntimeError("made-up crash"))],
                  picks=(_pick(0), _pick(1)))  # fmt: skip
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert "made-up crash" in report.detail
    assert len(night.removed) == 1  # the orphan-container cleanup still ran
    assert len(night.launched) == 1


def test_gate_tool_error_stops_the_run(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[2], picks=(_pick(0), _pick(1)))
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert len(night.launched) == 1
    assert _unit_text(night) == SCAFFOLD


def test_records_are_in_order(tmp_path):
    """AGT-03 ordering: records in execution order, attempts 1..3 per function per pass, and the
    log only grows (the copy in the match commit is a prefix of the final log)."""
    picks = (_pick(0), _pick(1))
    night = Night(tmp_path, picks=picks, sessions=[Sess()] * 4, gate_exits=[1, 1, 0, 1])
    night.run()
    seq = [(r["kind"], r.get("event") or r.get("function"), r.get("attempt"))
           for r in night.records()]  # fmt: skip
    f0, f1 = picks[0].name, picks[1].name
    assert seq[:5] == [("run", "STARTED", None), ("attempt", f0, 1), ("attempt", f0, 2),
                       ("attempt", f0, 3), ("attempt", f1, 1)]  # fmt: skip
    final = (night.repo / LOG).read_text(encoding="utf-8")
    assert final.startswith(night.file_at("feat(", LOG))


def test_transcript_paths_are_judged_against_the_checkout():
    """The audit reads write-tool paths from the transcript: one under the session's cwd (the
    CLI reports it in init) is repo-relative, one outside is None; reads and Bash are not
    writes."""
    events = [
        {"type": "system", "subtype": "init", "cwd": "/repo"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/repo/src/ufo2p/u.c"}},
            {"type": "tool_use", "name": "Write", "input": {"file_path": "/elsewhere/x.c"}},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/elsewhere/y.c"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        ]}},
    ]  # fmt: skip
    repo = Path(__file__).resolve().parents[1]
    assert driver.transcript_paths(events, repo) == [["src/ufo2p/u.c"], None]


# ---- Security ruling (06-23 commit_match): only plain new headers, literal pathspecs ----


@pytest.mark.parametrize("entry", ["include/*.h", "include/x[1].h", "include/a.txt"])
def test_an_untracked_include_entry_outside_the_header_form_stops(tmp_path, entry):
    """An untracked include/ entry that is not include/<name>.h ([A-Za-z0-9_] parts) is a
    guardrail STOP: the gate never runs, nothing is committed, and the run record names it."""
    night = Night(tmp_path, gate_exits=[0])
    if "*" in entry:  # NTFS cannot hold the name: the fake git reports it
        night.inject.append(entry)
        night.sessions.append(Sess())
    else:
        night.sessions.append(Sess(files=((entry, "/* made up */\n"),)))
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert entry in report.detail
    stopped = _one([r for r in night.kinds("run") if r["event"] == "STOPPED"])
    assert entry in stopped["detail"]
    assert night.gate_calls == []
    assert night.commits() == []


# ---- Task 3: the end-of-night chore commit (D-23) ----

CHORE = "chore(driver): attempt log"


def test_failed_attempts_are_committed_at_the_end(tmp_path):
    """A night whose last attempts failed ends with one chore commit holding the log and the
    status.csv its partial rows changed, and nothing else; the tree is clean after it."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),)), Sess(), Sess()])
    report = night.run()
    assert report.event == "ENDED"
    assert night.commits() == [CHORE]
    assert night.commit_files(CHORE) == sorted([LOG, f"config/{EXE}/status.csv"])
    assert night.git("status", "--porcelain=v1").strip() == ""
    assert night.file_at(CHORE, LOG) == (night.repo / LOG).read_text(encoding="utf-8")


def test_a_night_without_partial_rows_commits_only_the_log(tmp_path):
    night = Night(tmp_path, sessions=[Sess()] * 3)
    night.run()
    assert night.commits() == [CHORE]
    assert night.commit_files(CHORE) == [LOG]


def test_a_match_night_ends_with_the_run_record_in_a_chore_commit(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    assert night.commits() == [MATCH_SUBJECT, CHORE]
    assert night.commit_files(CHORE) == [LOG]
    assert night.records()[-1]["event"] == "ENDED"


def test_a_stopped_night_commits_only_the_log(tmp_path):
    """After a STOP, status.csv may hold a gate's half-write: only the log is committed."""
    night = Night(tmp_path, picks=(_pick(0), _pick(1)),
                  sessions=[Sess(checks=(check_line(1, 50.0),)), Sess("auth")])  # fmt: skip
    report = night.run(config={"attempts_per_function": 1})
    assert (report.event, report.reason) == ("STOPPED", "stop signal")
    assert night.commits() == [CHORE]
    assert night.commit_files(CHORE) == [LOG]


def test_a_guardrail_stop_commits_nothing(tmp_path):
    """D-17 and the security ruling: after a breach the owner inspects the tree as it is."""
    night = Night(tmp_path, sessions=[Sess(write=f"config/{EXE}/status.csv")])
    night.run()
    assert night.commits() == []


# ---- Security rulings (06-23): paths outside git's view, and a stop that cleans up ----

SETTINGS_LOCAL = ".claude/settings.local.json"
PTH_DIR = ".venv/Lib/site-packages"


def _stopped(night: Night) -> dict:
    return _one([r for r in night.kinds("run") if r["event"] == "STOPPED"])


def test_a_session_adding_a_git_hook_stops_and_the_hook_is_quarantined(tmp_path):
    night = Night(tmp_path, sessions=[Sess(write=".git/hooks/pre-commit")], gate_exits=[0])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert ".git/hooks/pre-commit" in _stopped(night)["detail"]
    assert not (night.repo / ".git" / "hooks" / "pre-commit").exists()
    assert (night.quarantine / ".git" / "hooks" / "pre-commit").is_file()
    assert night.gate_calls == []
    assert night.commits() == []


def test_a_session_editing_settings_local_stops_and_the_old_bytes_come_back(tmp_path):
    night = Night(tmp_path, sessions=[Sess(write=SETTINGS_LOCAL)])
    _write(night.repo / SETTINGS_LOCAL, '{"made": "up"}\n')
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert SETTINGS_LOCAL in report.detail
    assert (night.repo / SETTINGS_LOCAL).read_text(encoding="utf-8") == '{"made": "up"}\n'
    assert (night.quarantine / SETTINGS_LOCAL).read_text(encoding="utf-8").startswith("/*")


def test_a_session_adding_a_pth_file_stops(tmp_path):
    night = Night(tmp_path, sessions=[Sess(write=f"{PTH_DIR}/made_up.pth")])
    (night.repo / PTH_DIR).mkdir(parents=True)
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert f"{PTH_DIR}/made_up.pth" in report.detail
    assert not (night.repo / PTH_DIR / "made_up.pth").exists()
    assert (night.quarantine / PTH_DIR / "made_up.pth").is_file()


def test_a_session_writing_only_its_attempt_dir_does_not_stop(tmp_path):
    """build/ stays out of the audit by design: the wrapper writes the attempt dir."""
    scratch = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/scratch.txt"
    night = Night(tmp_path, sessions=[Sess(write=scratch)])
    report = night.run(config={"attempts_per_function": 1})
    assert report.event == "ENDED"


def test_a_guardrail_stop_restores_tracked_strays_and_quarantines_new_ones(tmp_path):
    sess = Sess(write="tools/x.py", files=(("tools/keep.py", "# changed by the agent\n"),))
    night = Night(tmp_path, sessions=[sess])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert (night.repo / "tools" / "keep.py").read_text(encoding="utf-8") == "# made up\n"
    assert night.git("status", "--porcelain=v1", "--", "tools/keep.py").strip() == ""
    assert (night.quarantine / "tools" / "keep.py").read_text(encoding="utf-8") == (
        "# changed by the agent\n"
    )
    assert not (night.repo / "tools" / "x.py").exists()
    assert (night.quarantine / "tools" / "x.py").is_file()
    detail = _stopped(night)["detail"]
    assert "restored: tools/keep.py" in detail
    assert "tools/x.py" in detail.split("quarantined:", 1)[1]


def test_a_guardrail_stop_keeps_the_drivers_own_pending_rows(tmp_path):
    """A stray edit of a file the driver itself had changed this night (status.csv with a
    partial row) goes back to its pre-session bytes, not to HEAD."""
    sessions = [Sess(checks=(check_line(1, 50.0),)), Sess(write=f"config/{EXE}/status.csv")]
    night = Night(tmp_path, sessions=sessions)
    report = night.run(config={"attempts_per_function": 2})
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    status = (night.repo / f"config/{EXE}/status.csv").read_text(encoding="utf-8")
    assert status.startswith(STATUS_HEAD) and ",partial," in status


# ---- Security rulings, third pass (06-23) ----

QUARANTINE_REL = f"build/driver/{RUN}/quarantine"


def test_the_quarantine_exists_before_any_session(tmp_path):
    night = Night(tmp_path, picks=())
    night.run()
    assert night.quarantine.is_dir()


def test_a_linked_quarantine_component_stops_and_writes_nothing(tmp_path):
    """HIGH: a link planted inside the quarantine (a junction on Windows, a symlink elsewhere)
    is refused before any containment write; nothing lands outside."""
    outside = tmp_path / "outside"
    outside.mkdir()
    sess = Sess(write="tools/x.py", link=(f"{QUARANTINE_REL}/tools", outside))
    night = Night(tmp_path, sessions=[sess])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert "link" in report.detail
    assert list(outside.iterdir()) == []


def test_a_symlinked_quarantine_at_run_start_stops_before_any_session(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py")])
    link = night.quarantine
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation needs privileges on this host")
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert night.launched == []
    assert list(outside.iterdir()) == []


def test_a_quarantined_file_is_never_overwritten(tmp_path):
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py")])
    _write(night.quarantine / "tools" / "x.py", "earlier evidence\n")
    night.run()
    assert (night.quarantine / "tools" / "x.py").read_text(encoding="utf-8") == (
        "earlier evidence\n"
    )
    assert (night.quarantine / "tools" / "x.py.1").is_file()


def test_a_pinned_change_after_containment_is_reported(tmp_path):
    """The pinned snapshot is taken again after containment; a path that still differs is
    named in the STOPPED record."""
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py",
                                           files=(("tools/keep.py", "# changed\n"),))])  # fmt: skip
    exclude = night.repo / ".git" / "info" / "exclude"

    def late_write(args):
        if "--worktree" in args:  # containment is restoring: something writes again
            _write(exclude, "late change\n")

    night.on_git = late_write
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert "still changed after containment: .git/info/exclude" in report.detail


@pytest.mark.parametrize("rel", [".git/info/exclude", ".git/info/attributes",
                                 ".venv/sitecustomize.py",
                                 ".venv/Lib/site-packages/usercustomize.py"])  # fmt: skip
def test_more_pinned_paths_stop_the_night(tmp_path, rel):
    night = Night(tmp_path, sessions=[Sess(write=rel)])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert rel in report.detail


@pytest.mark.parametrize("rel", [".venv/Lib/site-packages/made_up/__init__.py",
                                 "tools/__pycache__/keep.cpython-314.pyc"])  # fmt: skip
def test_a_fingerprint_change_stops_the_night(tmp_path, rel):
    night = Night(tmp_path, sessions=[Sess(write=rel)])
    (night.repo / ".venv" / "Lib" / "site-packages").mkdir(parents=True)
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert rel in report.detail


def test_a_pycache_under_build_is_not_fingerprinted(tmp_path):
    rel = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/__pycache__/x.pyc"
    night = Night(tmp_path, sessions=[Sess(write=rel)])
    report = night.run(config={"attempts_per_function": 1})
    assert report.event == "ENDED"


def test_a_raising_session_has_its_strays_contained(tmp_path):
    """MEDIUM: a session that raises is measured and contained before the ERROR stop."""
    files = (("tools/x.py", "# made up\n"), (".git/info/exclude", "made up\n"))
    sess = Sess(raises=RuntimeError("made-up crash"), files=files)
    night = Night(tmp_path, sessions=[sess])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert "made-up crash" in report.detail
    assert "tools/x.py" in report.detail and ".git/info/exclude" in report.detail
    assert not (night.repo / "tools" / "x.py").exists()
    assert (night.quarantine / "tools" / "x.py").is_file()
    assert (night.quarantine / ".git" / "info" / "exclude").is_file()


def test_a_refused_quarantine_never_skips_restoration(tmp_path):
    """Fourth pass: with the quarantine root replaced by a link, the stray tracked edit and the
    changed pinned file are still restored; the untracked stray stays in place, named "not
    contained"; each refusal is recorded per file; nothing lands outside."""
    outside = tmp_path / "outside"
    outside.mkdir()
    files = (("tools/keep.py", "# changed\n"), (".git/info/exclude", "changed\n"))
    sess = Sess(write="tools/x.py", files=files, link=(QUARANTINE_REL, outside))
    night = Night(tmp_path, sessions=[sess])
    exclude = night.repo / ".git" / "info" / "exclude"
    exclude_before = exclude.read_bytes()
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert (night.repo / "tools" / "keep.py").read_text(encoding="utf-8") == "# made up\n"
    assert exclude.read_bytes() == exclude_before
    assert (night.repo / "tools" / "x.py").is_file()
    detail = _stopped(night)["detail"]
    assert "not contained: tools/x.py" in detail
    for name in ("tools/keep.py", ".git/info/exclude", "tools/x.py"):
        assert f"refused {name}:" in detail, name
    assert list(outside.iterdir()) == []


# ---- Fix round 1 (review-06-23, fixround-06-23-r1) ----


def _run_contained(night: Night, **deps) -> DriveReport:
    """drive() must end every night with a report: an escaping exception fails the test."""
    try:
        return night.run(**deps)
    except Exception as exc:  # noqa: BLE001 - the escape is the failure under test
        pytest.fail(f"drive() let {type(exc).__name__} escape: {exc}")


def _assert_stopped_error_and_only_the_log(night: Night, report, needle: str) -> None:
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert needle in report.detail
    assert night.records()[-1]["event"] == "STOPPED"
    assert night.records()[-1]["reason"] == "error"
    assert night.commits() in ([], [CHORE])
    if night.commits():
        assert night.commit_files(CHORE) == [LOG]


def test_a_raising_queue_ends_the_night_with_a_stopped_record(tmp_path):
    """I1: an exception outside an attempt is a STOPPED error, not an escape."""
    night = Night(tmp_path, sessions=[Sess()])

    def queue(difficult):
        yield PICK
        raise RuntimeError("made-up picker failure")

    report = _run_contained(night, queue=queue)
    _assert_stopped_error_and_only_the_log(night, report, "made-up picker failure")


def test_a_corrupt_difficult_list_ends_the_night_with_a_stopped_record(tmp_path):
    night = Night(tmp_path, sessions=[Sess()])
    _write(night.repo / "build" / "driver" / "difficult.json", "not json\n")
    report = _run_contained(night)
    _assert_stopped_error_and_only_the_log(night, report, "DriverError")
    assert night.launched == []


def test_a_failing_difficult_save_ends_the_night_with_a_stopped_record(tmp_path):
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),))] + [Sess()] * 2)
    (night.repo / "build" / "driver" / "difficult.json").mkdir(parents=True)  # unwritable
    report = _run_contained(night)
    _assert_stopped_error_and_only_the_log(night, report, "difficult.json")
    assert len(night.launched) == 3


def test_an_interrupt_is_contained_recorded_and_re_raised(tmp_path):
    """Minor 8: Ctrl-C mid-session: contain first, record STOPPED interrupted, re-raise."""
    sess = Sess(raises=KeyboardInterrupt(), files=(("tools/x.py", "# made up\n"),))
    night = Night(tmp_path, sessions=[sess])
    with pytest.raises(KeyboardInterrupt):
        night.run()
    last = night.records()[-1]
    assert (last["event"], last["reason"]) == ("STOPPED", "interrupted")
    assert "tools/x.py" in last["detail"]
    assert not (night.repo / "tools" / "x.py").exists()
    assert (night.quarantine / "tools" / "x.py").is_file()
    assert night.commits() == []


REFUSE_FEAT_HOOK = """#!/bin/sh
case "$(head -n 1 "$1")" in
  feat\\(*) echo "made-up hook refusal" >&2; exit 1 ;;
esac
exit 0
"""


def test_a_failed_match_commit_leaves_no_trace_of_a_match(tmp_path):
    """I2: `git add` succeeds, `git commit` fails (a commit-msg hook that predates the night
    refuses feat messages): nothing stays staged, status.csv, the feed and the log are back to
    their pre-attempt bytes, the attempt is GAVE_UP `tool`, and no MATCHED record is ever
    committed."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    hook = night.repo / ".git" / "hooks" / "commit-msg"
    _write(hook, REFUSE_FEAT_HOOK)
    hook.chmod(0o755)
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert "made-up hook refusal" in report.detail
    assert [r.get("outcome") for r in night.kinds("attempt")] == ["GAVE_UP"]
    assert night.kinds("attempt")[0]["abort_reason"] == "tool"
    assert night.git("diff", "--cached", "--name-only").strip() == ""
    assert (night.repo / f"config/{EXE}/status.csv").read_text(encoding="utf-8") == STATUS_HEAD
    assert (night.repo / "decomphub.progress.json").read_text(encoding="utf-8") == "{}\n"
    assert _unit_text(night) == SCAFFOLD
    assert night.commits() == [CHORE]
    assert night.commit_files(CHORE) == [LOG]
    assert "MATCHED" not in night.file_at(CHORE, LOG)


def test_a_failed_match_commit_unstages_new_files_too(tmp_path):
    """I2 with an untracked path: the landed unit HEAD lacks was `git add`ed; after the failed
    commit it stays neither in the index nor on disk (07-13: no header is ever added)."""
    night = Night(tmp_path, unit_committed=False, sessions=[Sess()], gate_exits=[0])
    hook = night.repo / ".git" / "hooks" / "commit-msg"
    _write(hook, REFUSE_FEAT_HOOK)
    hook.chmod(0o755)
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert night.git("diff", "--cached", "--name-only").strip() == ""
    assert not (night.repo / UNIT_REL).exists()


def test_a_third_transient_retry_that_succeeds_is_counted(tmp_path):
    """Minor 6: three transient launches are not yet an abort; the 4th launch counts."""
    sessions = [Sess("overloaded", write=None)] * 3 + [Sess()]
    night = Night(tmp_path, sessions=sessions)
    night.run(config={"attempts_per_function": 1})
    assert night.kinds("abort") == []
    assert _one(night.kinds("attempt"))["outcome"] == "GAVE_UP"


def test_containers_are_removed_before_a_raising_session_is_measured(tmp_path):
    """Minor 1: nothing is measured until the attempt's containers are gone."""
    night = Night(tmp_path, sessions=[Sess(raises=RuntimeError("made-up crash"))])
    order: list[int] = []
    night.run(remove_containers=lambda prefix: order.append(len(night.git_calls)))
    assert order == [night.git_at_launch]


@pytest.mark.parametrize("rel", [".venv/Scripts/made_up.exe", ".claude/hooks/made_up.js"])
def test_the_whole_venv_and_ignored_claude_trees_are_fingerprinted(tmp_path, rel):
    """Minor 2 (widened): stat-only fingerprint of all of .venv and of every gitignored tree
    under .claude/."""
    night = Night(tmp_path, sessions=[Sess(write=rel)])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert rel in report.detail


def test_claude_worktrees_are_not_fingerprinted(tmp_path):
    rel = ".claude/worktrees/agent-made-up/notes.txt"
    night = Night(tmp_path, sessions=[Sess(write=rel)])
    report = night.run(config={"attempts_per_function": 1})
    assert report.event == "ENDED", report.detail


def test_the_session_env_forbids_bytecode_writes(tmp_path):
    """Minor 3: the wrapper must not write .pyc files mid-session."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    assert night.launched[0].env.get("PYTHONDONTWRITEBYTECODE") == "1"


def test_a_restore_write_through_a_link_is_refused(tmp_path):
    """Minor 4: restoring a pinned file goes through the same link checks as quarantine
    writes; a swapped .claude/ (a junction or symlink) is refused and named "not restored"."""
    outside = tmp_path / "outside"
    outside.mkdir()
    sess = Sess(write=None, files=((SETTINGS_LOCAL, "changed\n"),), link=(".claude", outside))
    night = Night(tmp_path, sessions=[sess])
    _write(night.repo / SETTINGS_LOCAL, '{"made": "up"}\n')
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert f"not restored: {SETTINGS_LOCAL}" in report.detail
    assert list(outside.iterdir()) == []


def test_an_untracked_header_from_before_the_session_is_named(tmp_path):
    """Minor 5, 07-13 (D-24 invariant a): an untracked include/<name>.h that neither HEAD nor
    the driver wrote is a stray at the audit, whoever left it: the night stops naming it before
    any gate, and the file is moved into the quarantine, never deleted."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    _write(night.repo / "include" / "old.h", "/* the owner's, uncommitted */\n")
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert "include/old.h" in report.detail
    assert _feats(night) == []
    assert night.gate_calls == []
    assert (night.quarantine / "include" / "old.h").is_file()


def test_a_gate_naming_other_exes_is_a_tool_failure(tmp_path):
    """Minor 7: both SHA-1s must belong to the two EXEs (config stems ufo2p and tacp)."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.gate_names = ("UFO2P.EXE", "OTHER.EXE")
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert _feats(night) == []


def test_a_directory_stray_is_named_not_contained(tmp_path):
    """Minor 9: git lists a nested repository as one `dir/` entry; it is reported."""
    night = Night(tmp_path, sessions=[Sess(files=(("vendor/x/a.txt", "made up\n"),))])
    night.inject.append("vendor/x/")
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert "not contained: vendor/x/" in report.detail


def _docker_down(prefix: str) -> None:
    raise RuntimeError("made-up docker failure")


def test_a_failed_container_removal_never_gates_containment(tmp_path):
    """S1: remove_containers raising after a normal session: the strays are still audited and
    contained, and the record says the containers were not removed."""
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py")])
    report = night.run(remove_containers=_docker_down)
    assert report.event == "STOPPED"
    assert "containers not removed: RuntimeError: made-up docker failure" in report.detail
    assert "tools/x.py" in report.detail
    assert not (night.repo / "tools" / "x.py").exists()
    assert (night.quarantine / "tools" / "x.py").is_file()


def test_a_failed_container_removal_alone_stops_the_night(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0], picks=(_pick(0), _pick(1)))
    report = night.run(remove_containers=_docker_down)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert "containers not removed" in report.detail
    assert len(night.launched) == 1
    assert _feats(night) == []
    # Fix round 2 minor 4: the counted session still gets its attempt record.
    record = _one(night.kinds("attempt"))
    assert (record["outcome"], record["abort_reason"]) == ("GAVE_UP", "tool")
    assert report.sessions == 1


def test_a_failed_container_removal_on_the_raise_path_still_contains(tmp_path):
    sess = Sess(raises=RuntimeError("made-up crash"), files=(("tools/x.py", "# made up\n"),))
    night = Night(tmp_path, sessions=[sess])
    report = night.run(remove_containers=_docker_down)
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert "containers not removed" in report.detail and "made-up crash" in report.detail
    assert (night.quarantine / "tools" / "x.py").is_file()


def test_a_pinned_file_replaced_by_a_junction_or_symlink_dir_comes_back(tmp_path):
    """S2: a leaf link is replaced, not refused: the pinned file is restored to its bytes as a
    regular file (a junction on Windows, a directory symlink elsewhere); the target is never
    written."""
    outside = tmp_path / "outside"
    outside.mkdir()
    night = Night(tmp_path, sessions=[Sess(write=None, link=(SETTINGS_LOCAL, outside))])
    _write(night.repo / SETTINGS_LOCAL, '{"made": "up"}\n')
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    leaf = night.repo / SETTINGS_LOCAL
    assert not os.path.islink(leaf) and not os.path.isjunction(leaf)
    assert leaf.read_text(encoding="utf-8") == '{"made": "up"}\n'
    assert list(outside.iterdir()) == []


def test_a_pinned_file_replaced_by_a_file_symlink_comes_back(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("outside\n", encoding="utf-8")
    night = Night(tmp_path, sessions=[Sess(write=None)])
    leaf = night.repo / SETTINGS_LOCAL
    _write(leaf, '{"made": "up"}\n')
    probe = tmp_path / "probe-link"
    try:
        probe.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation needs privileges on this host")
    probe.unlink()

    swapped = []

    def swap(args):  # the "agent" swaps the file for a link once, while the session runs
        if night.launched and not swapped:
            swapped.append(True)
            leaf.unlink()
            leaf.symlink_to(outside)

    night.on_git = swap
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert not os.path.islink(leaf)
    assert leaf.read_text(encoding="utf-8") == '{"made": "up"}\n'
    assert outside.read_text(encoding="utf-8") == "outside\n"


# ---- Fix round 2 (rereview-06-23-r1, fixround-06-23-r2) ----


def _no_match_anywhere(night: Night) -> None:
    """No MATCHED record on disk or in any commit, nothing staged, the tables as at HEAD."""
    assert all(r.get("outcome") != "MATCHED" for r in night.records())
    for sha in night.git("log", "--format=%H", f"{night.base}..HEAD").split():
        assert "MATCHED" not in night.git("show", f"{sha}:{LOG}")
    assert (night.repo / f"config/{EXE}/status.csv").read_text(encoding="utf-8") == STATUS_HEAD
    assert (night.repo / "decomphub.progress.json").read_text(encoding="utf-8") == "{}\n"
    assert _feats(night) == []


def test_a_raising_match_commit_leaves_no_trace_of_a_match(tmp_path):
    """J1: commit_paths fails with something other than a DriverError (a raising git)."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.raise_verbs["commit"] = RuntimeError("made-up git crash")
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert "made-up git crash" in report.detail
    assert _one(night.kinds("attempt"))["abort_reason"] == "tool"
    assert night.git("diff", "--cached", "--name-only").strip() == ""
    _no_match_anywhere(night)


def test_an_unwritable_message_file_leaves_no_trace_of_a_match(tmp_path):
    """J1: the commit message file cannot be written (a directory stands in its place)."""
    msg_dir = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/commit-msg.txt/blocker"
    night = Night(tmp_path, sessions=[Sess(files=((msg_dir, "made up\n"),))], gate_exits=[0])
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert _one(night.kinds("attempt"))["abort_reason"] == "tool"
    _no_match_anywhere(night)


def test_a_lock_held_through_the_undo_still_records_and_names_what_stays_staged(tmp_path):
    """J1: the commit fails on a lock that is still held for the unstage and the reset: the
    GAVE_UP record is still written, and every path left staged is named."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.fail_verbs.update({"commit": 1, "restore": 2})
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert _one(night.kinds("attempt"))["abort_reason"] == "tool"
    staged = night.git("diff", "--cached", "--name-only").split()
    assert staged, "the probe needs paths left staged"
    for path in staged:
        assert path in report.detail, path
    assert "still staged:" in report.detail
    assert all(r.get("outcome") != "MATCHED" for r in night.records())
    for sha in night.git("log", "--format=%H", f"{night.base}..HEAD").split():
        assert "MATCHED" not in night.git("show", f"{sha}:{LOG}")


def test_an_interrupt_during_the_match_commit_is_undone_and_named(tmp_path):
    """Minor 3: Ctrl-C between the MATCHED record and the commit runs the same undo first."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.raise_verbs["commit"] = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        night.run()
    last = night.records()[-1]
    assert (last["event"], last["reason"]) == ("STOPPED", "interrupted")
    assert "match commit" in last["detail"]
    assert night.git("diff", "--cached", "--name-only").strip() == ""
    _no_match_anywhere(night)


def test_a_refused_pre_gate_restore_is_named(tmp_path, monkeypatch):
    """Minor 1: a pre-gate restore that fails is named in the record, never silent."""
    real = driver.write_atomic

    def refuse_status(path, data):
        if Path(path).name == "status.csv":
            raise OSError("made-up disk failure")
        return real(path, data)

    monkeypatch.setattr(driver, "write_atomic", refuse_status)
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.gate_names = ("UFO2P.EXE", "OTHER.EXE")  # a tool failure after a passing gate
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert f"not restored: config/{EXE}/status.csv" in report.detail
    assert "made-up disk failure" in report.detail


def test_a_failing_restore_during_containment_spares_the_other_strays(tmp_path):
    """J2: a lock at the first git restore of containment: that file is named "not
    restored", the other strays are still restored or quarantined, the reason stays
    guardrail, and nothing is committed."""
    files = (("tools/keep.py", "# changed\n"), ("decomphub.progress.json", "agent\n"))
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py", files=files)])
    night.fail_verbs["restore"] = 1
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert "not restored: decomphub.progress.json (" in report.detail
    assert (night.repo / "tools" / "keep.py").read_text(encoding="utf-8") == "# made up\n"
    assert (night.quarantine / "tools" / "x.py").is_file()
    assert night.commits() == []


def test_a_session_edit_of_the_log_and_a_table_is_never_committed(tmp_path):
    """J2: the session appends to attempts.jsonl and edits config/tacp/status.csv, and the
    first restore meets a lock: neither is committed, both are named, the log is restored."""
    sess = Sess(append=((LOG, '{"agent":"line"}\n'),),
                files=(("config/tacp/status.csv", "agent edit\n"),))  # fmt: skip
    night = Night(tmp_path, sessions=[sess])
    night.fail_verbs["restore"] = 1
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert night.commits() == []
    assert '"agent"' not in (night.repo / LOG).read_text(encoding="utf-8")
    assert "config/tacp/status.csv" in report.detail and LOG in report.detail


def test_a_raising_session_with_strays_commits_nothing(tmp_path):
    """J2: containment ran, so the breach is sticky: even an `error` stop commits nothing."""
    sess = Sess(raises=RuntimeError("made-up crash"), files=(("tools/x.py", "# made up\n"),))
    night = Night(tmp_path, sessions=[sess])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert night.commits() == []


# ---- Fix round 3 (rereview-06-23-r2, fixround-06-23-r3) ----


def _refuse_writes_to(monkeypatch, name: str) -> None:
    """write_atomic raises for files called `name` (an os.replace onto a file held open)."""
    real = driver.write_atomic

    def refuse(path, data):
        if Path(path).name == name:
            raise PermissionError(f"made-up: {name} is held open")
        return real(path, data)

    monkeypatch.setattr(driver, "write_atomic", refuse)


def _failed_commit_night(tmp_path) -> Night:
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    hook = night.repo / ".git" / "hooks" / "commit-msg"
    _write(hook, REFUSE_FEAT_HOOK)
    hook.chmod(0o755)
    return night


@pytest.mark.parametrize("step", ["log", "table", "feed", "unstage", "reset"])
def test_a_failed_undo_step_commits_nothing(tmp_path, monkeypatch, step):
    """K1: after a failed match commit, any undo step that fails sets the no-commit flag:
    nothing is committed that night, not even the log, and the record names the failure."""
    night = _failed_commit_night(tmp_path)
    if step == "log":  # F19: the log is truncated to its length before the MATCHED record

        def refuse(path, size):
            raise PermissionError("made-up: attempts.jsonl is held open")

        monkeypatch.setattr(driver, "_truncate", refuse)
    elif step in ("table", "feed"):
        name = {"table": "status.csv", "feed": FEED_NAME}[step]
        _refuse_writes_to(monkeypatch, name)
    elif step == "unstage":
        night.fail_plan["restore"] = [True]
    else:  # the reset's git restore, after a working unstage
        night.fail_plan["restore"] = [False, True]
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert night.commits() == []
    expected = {"log": "not restored: progress/attempts.jsonl", "table": "not restored: config/",
                "feed": f"not restored: {FEED_NAME}", "unstage": "could not unstage",
                "reset": "could not reset the attempt"}[step]  # fmt: skip
    assert expected in report.detail


def test_a_restored_stray_that_cannot_be_unstaged_is_named_so(tmp_path):
    """Minor 2: the bytes came back but `git restore --staged` failed: "restored; could not
    unstage", not "not restored"."""
    sessions = [Sess(checks=(check_line(1, 50.0),)), Sess(write=f"config/{EXE}/status.csv")]
    night = Night(tmp_path, sessions=sessions)
    night.fail_from_launch = 2
    night.fail_verbs["restore"] = 1
    report = night.run(config={"attempts_per_function": 2})
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert f"restored; could not unstage: config/{EXE}/status.csv (" in report.detail
    assert f"not restored: config/{EXE}/status.csv" not in report.detail


def test_a_night_after_a_breach_refuses_to_start(tmp_path):
    """Minor 1: a breached night leaves the log modified and uncommitted; the next drive()
    refuses to start (exit 2, before STARTED, nothing written), naming the path."""
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py")])
    first = night.run()
    assert (first.event, first.reason) == ("STOPPED", "guardrail")
    log_before = (night.repo / LOG).read_bytes()
    night.sessions.append(Sess())
    report = night.run()
    assert (report.event, report.exit_code) == ("REFUSED", 2)
    assert LOG in report.detail
    assert (night.repo / LOG).read_bytes() == log_before
    assert len(night.launched) == 1
    assert night.commits() == []


@pytest.mark.parametrize("rel", [f"config/{EXE}/status.csv", "config/tacp/status.csv",
                                 "decomphub.progress.json"])  # fmt: skip
def test_a_dirty_or_staged_table_refuses_the_start(tmp_path, rel):
    night = Night(tmp_path, sessions=[Sess()])
    _write(night.repo / rel, "left over\n")
    night.git("add", "--", rel)  # staged counts too
    report = night.run()
    assert (report.event, report.exit_code) == ("REFUSED", 2)
    assert rel in report.detail
    assert night.launched == []
    assert (night.repo / LOG).read_text(encoding="utf-8") == ""


# ---- Fix round 4 (rereview-06-23-r3, fixround-06-23-r4) ----


def test_end_of_run_checks_land_in_the_ended_record_before_the_chore_commit(tmp_path):
    """L1 (consumer contract for 06-25): end_of_run runs after the last session and before
    the ENDED record; its failed checks are pinned under checks_failed and the night exits 1;
    the chore commit comes after the record."""
    night = Night(tmp_path, sessions=[Sess()])
    seen: list[tuple[int, list[str], int]] = []

    def end_of_run():
        seen.append((len(night.launched), [r.get("event") for r in night.kinds("run")],
                     len(night.commits())))  # fmt: skip
        return ["ninja verify exit 1", "gate --all exit 1"]

    report = night.run(end_of_run=end_of_run)
    assert seen == [(3, ["STARTED"], 0)]
    ended = night.records()[-1]
    assert (ended["event"], ended.get("checks_failed")) == (
        "ENDED", ["ninja verify exit 1", "gate --all exit 1"])  # fmt: skip
    assert (report.event, report.exit_code) == ("ENDED", 1)
    assert night.commits() == [CHORE]
    assert '"checks_failed":["ninja verify exit 1"' in night.file_at(CHORE, LOG)


def test_a_clean_end_of_run_keeps_exit_0(tmp_path):
    night = Night(tmp_path, picks=())
    report = night.run(end_of_run=lambda: [])
    assert (report.event, report.exit_code) == ("ENDED", 0)
    assert night.records()[-1].get("checks_failed") == []


def test_a_raising_end_of_run_is_a_stopped_error(tmp_path):
    def broken():
        raise RuntimeError("made-up ninja crash")

    night = Night(tmp_path, picks=())
    report = _run_contained(night, end_of_run=broken)
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert "made-up ninja crash" in report.detail


def test_a_stopped_night_names_its_uncommitted_partial_rows(tmp_path):
    """L2: a STOPPED night that leaves a partial row uncommitted names it, so the owner knows
    why the next drive is refused."""
    night = Night(tmp_path, picks=(_pick(0), _pick(1)),
                  sessions=[Sess(checks=(check_line(1, 50.0),)), Sess("auth")])  # fmt: skip
    report = night.run(config={"attempts_per_function": 1})
    assert (report.event, report.reason) == ("STOPPED", "stop signal")
    stopped = night.records()[-1]
    assert stopped.get("uncommitted") == [f"config/{EXE}/status.csv: 0x{START:08X} partial"]
    assert night.commit_files(CHORE) == [LOG]


def test_a_failing_outputs_check_refuses_the_start(tmp_path):
    """L3: the git call of the dirty-outputs check fails: REFUSED (exit 2), never an escape."""

    def broken_git(args):
        raise RuntimeError("made-up git failure")

    night = Night(tmp_path, sessions=[Sess()])
    report = _run_contained(night, git=broken_git)
    assert (report.event, report.exit_code) == ("REFUSED", 2)
    assert "made-up git failure" in report.detail
    assert night.launched == []
    assert (night.repo / LOG).read_text(encoding="utf-8") == ""


# ---- quick 261026-9ue: drive timestamps (the night says, the verb's console stamps) ----

LABEL = "ufo2p func_00010010 attempt"


def test_console_attempt_lines_name_the_attempt_and_its_outcome(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    lines = []
    night.run(say=lines.append)
    assert lines == [f"{LABEL} 1/3: started", f"{LABEL} 1/3: MATCHED after 45.0 s"]


def test_console_attempt_lines_for_each_gave_up_attempt(tmp_path):
    night = Night(tmp_path, sessions=[Sess(), Sess(), Sess()])
    lines = []
    night.run(say=lines.append)
    assert lines == [line for n in (1, 2, 3)
                     for line in (f"{LABEL} {n}/3: started",
                                  f"{LABEL} {n}/3: GAVE_UP after 45.0 s")]  # fmt: skip


def test_console_attempt_seconds_cover_relaunches_and_backoffs(tmp_path):
    night = Night(tmp_path, sessions=[Sess("rate_limit", write=None),
                                      Sess("rate_limit", write=None), Sess()],
                  gate_exits=[0])  # fmt: skip
    lines = []
    night.run(say=lines.append)
    assert lines == [f"{LABEL} 1/3: started",
                     f"{LABEL} 1/3: usage limit, next launch in 60 s",
                     f"{LABEL} 1/3: usage limit, next launch in 120 s",
                     f"{LABEL} 1/3: MATCHED after 315.0 s"]  # fmt: skip


def test_console_attempt_aborted_after_transient_retries(tmp_path):
    night = Night(tmp_path, sessions=[Sess("overloaded", write=None),
                                      Sess("no_result", write=None),
                                      Sess("overloaded", write=None),
                                      Sess("no_result", write=None)])  # fmt: skip
    lines = []
    night.run(say=lines.append)
    assert lines == [f"{LABEL} 1/3: started", f"{LABEL} 1/3: ABORTED (transient) after 180.0 s"]


def test_console_attempt_stop_prints_only_the_start_line(tmp_path):
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py",
                                           files=((UNIT_REL, "int edited;\n"),))])  # fmt: skip
    lines = []
    report = night.run(say=lines.append)
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert lines == [f"{LABEL} 1/3: started"]


def test_console_night_is_silent_by_default(tmp_path, capsys):
    Night(tmp_path, sessions=[Sess()], gate_exits=[0]).run()
    out, err = capsys.readouterr()
    assert (out, err) == ("", "")


# ---- 06-REVIEW CR-01: a gate pass is a match only when it wrote the claimed function's row ----

SIBLING = START - 0x10  # a function of the same unit, matched before tonight (made up)
SIBLING_ROW = f"0x{SIBLING:08X},func_{SIBLING:08X},{UNIT},matched,100.00,1\n"


def _night_with_matched_sibling(tmp_path: Path, **over) -> Night:
    """A unit that already holds a matched function: its gate passes whatever the session did
    to the claimed function (stubs are not checked), so the gate's exit alone proves nothing."""
    night = Night(tmp_path, **over)
    _write(night.repo / f"config/{EXE}/status.csv", STATUS_HEAD + SIBLING_ROW)
    night.git("commit", "-q", "-am", "a sibling matched earlier")
    night.base = night.git("rev-parse", "HEAD").strip()
    return night


def test_gate_pass_without_the_claimed_row_is_no_match(tmp_path):
    night = _night_with_matched_sibling(tmp_path, sessions=[Sess()], gate_exits=[0],
                                        gate_written=(SIBLING,))  # fmt: skip
    report = night.run(config={"attempts_per_function": 1})
    assert _feats(night) == []
    assert report.matched == 0
    record = _one(night.kinds("attempt"))
    assert record["outcome"] == "GAVE_UP"
    assert _unit_text(night) == SCAFFOLD  # D-34: the attempt was reset
    # the gate's rewrite of the sibling's row and of the feed is undone
    status = (night.repo / f"config/{EXE}/status.csv").read_text(encoding="utf-8")
    assert status == STATUS_HEAD + SIBLING_ROW
    assert (night.repo / FEED_NAME).read_text(encoding="utf-8") == "{}\n"


def test_gate_pass_without_the_claimed_row_keeps_a_partial(tmp_path):
    sess = Sess(checks=(check_line(1, 80.0),))
    night = _night_with_matched_sibling(tmp_path, sessions=[sess], gate_exits=[0],
                                        gate_written=(SIBLING,))  # fmt: skip
    report = night.run(config={"attempts_per_function": 1})
    assert _feats(night) == []
    assert report.matched == 0
    assert _one(night.kinds("attempt"))["outcome"] == "PARTIAL"
    assert len(night.partial_calls) == 1


def test_limit_salvage_without_the_claimed_row_is_no_match(tmp_path):
    night = _night_with_matched_sibling(tmp_path, sessions=[Sess("rejected")], gate_exits=[0],
                                        gate_written=(SIBLING,))  # fmt: skip
    report = night.run(config={"attempts_per_function": 1})
    assert _feats(night) == []
    assert report.matched == 0
    assert "MATCHED" not in [r["outcome"] for r in night.kinds("attempt")]
    status = (night.repo / f"config/{EXE}/status.csv").read_text(encoding="utf-8")
    assert status == STATUS_HEAD + SIBLING_ROW


@pytest.mark.parametrize("refused", [f"config/{EXE}/status.csv", FEED_NAME])
def test_unclaimed_pass_with_a_refused_restore_stops_the_night(tmp_path, monkeypatch, refused):
    """Fix round 2: when the pre-gate bytes of status.csv or the feed cannot be put back after
    a pass without the claimed row (_restore_bytes refuses a link or a path outside the
    checkout), the night STOPS on a tool failure naming the file: no MATCHED record, no feat
    commit, and nothing committed but the attempt log."""
    real = driver._Night._restore_bytes

    def refuse(self, name, path, data):
        return False if name == refused else real(self, name, path, data)

    monkeypatch.setattr(driver._Night, "_restore_bytes", refuse)
    night = _night_with_matched_sibling(tmp_path, sessions=[Sess()], gate_exits=[0],
                                        gate_written=(SIBLING,))  # fmt: skip
    report = night.run(config={"attempts_per_function": 1})
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert driver._UNCLAIMED_PASS in report.detail
    assert f"not restored: {refused} (refused: a link or outside the checkout)" in report.detail
    assert report.matched == 0
    assert all(r.get("outcome") != "MATCHED" for r in night.records())
    assert _feats(night) == []
    assert night.commits() == [CHORE]
    assert night.commit_files(CHORE) == [LOG]


def test_gate_pass_with_the_claimed_row_beside_a_sibling_commits(tmp_path):
    night = _night_with_matched_sibling(tmp_path, sessions=[Sess()], gate_exits=[0],
                                        gate_written=(SIBLING, START))  # fmt: skip
    report = night.run(config={"attempts_per_function": 1})
    assert _feats(night) == [MATCH_SUBJECT]
    assert report.matched == 1
    assert _one(night.kinds("attempt"))["outcome"] == "MATCHED"


# ---- 07-13 Task 1: private per-attempt views, landing (D-24) ----

VIEW_TEXT = "/* made-up view edit */\nint view_edit;\n"
VIEW_UNIT_REL = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/view/src/{EXE}/{UNIT}.c"
STATUS_REL = f"config/{EXE}/status.csv"


def _view_session(**over) -> Sess:
    """A session that edits only its view unit (the stand-in writes REVERSEAPOC_UNIT_FILE)."""
    return Sess(**{"write": None, "unit_text": VIEW_TEXT, **over})


def test_view_is_head_snapshot(tmp_path):
    """D-24: the view is HEAD's src/, include/ and config/ (git archive), never the worktree:
    an uncommitted edit and an untracked unit in src/ are not in it, a file committed since the
    base is, and nothing outside the three trees is."""
    night = Night(tmp_path, sessions=[_view_session()], gate_exits=[1])
    _write(night.repo / "include" / "extra.h", "/* made-up committed header */\n")
    night.git("add", "--", "include/extra.h")
    night.git("commit", "-q", "-m", "extra header")
    _write(night.repo / UNIT_REL, "int dirty_worktree_edit;\n")
    _write(night.repo / "src" / EXE / "u_untracked.c", "int untracked;\n")
    night.run(config={"attempts_per_function": 1})
    files = night.seen[0]["files"]
    assert files[f"src/{EXE}/{UNIT}.c"] == SCAFFOLD.encode()
    assert files["include/common.h"] == b"/* made up */\n"
    assert files["include/extra.h"] == b"/* made-up committed header */\n"
    assert files[STATUS_REL] == STATUS_HEAD.encode()
    assert f"src/{EXE}/u_untracked.c" not in files
    assert sorted({name.split("/")[0] for name in files}) == ["config", "include", "src"]


def test_view_always_has_include(tmp_path):
    """Orchestrator note (07-11 as built): a view without include/ would compile against the
    committed headers, so the driver creates include/ in every view, even when HEAD has none."""
    night = Night(tmp_path, sessions=[_view_session()], gate_exits=[1])
    night.git("rm", "-q", "--", "include/common.h")
    night.git("commit", "-q", "-m", "no headers")
    night.run(config={"attempts_per_function": 1})
    assert "include" in night.seen[0]["dirs"]


def test_missing_unit_is_scaffolded_into_the_view(tmp_path):
    """A unit HEAD lacks is scaffolded into the view (Deps.scaffold(pick, dest)), never into
    src/: the session finds no src/ unit at launch."""
    night = Night(tmp_path, unit_committed=False, sessions=[_view_session()], gate_exits=[1])
    night.run(config={"attempts_per_function": 1})
    view_unit = night.attempt_dir(1) / "view" / "src" / EXE / f"{UNIT}.c"
    assert night.scaffolded == [PICK]
    assert night.scaffold_dests == [view_unit]
    assert night.seen[0]["files"][f"src/{EXE}/{UNIT}.c"] == SCAFFOLD.encode()
    assert night.seen[0]["src_unit"] is None


def test_session_env_has_view_paths(tmp_path):
    """The stand-in claude sees the view unit (absolute), the attempt's proposals.jsonl and the
    session kind next to the Phase 6 claim variables, and writes the unit the env names."""
    night = Night(tmp_path, sessions=[_view_session()], gate_exits=[1])
    night.run(config={"attempts_per_function": 1})
    env = night.launched[0].env
    attempt_dir = night.attempt_dir(1)
    view_unit = attempt_dir / "view" / "src" / EXE / f"{UNIT}.c"
    assert env[hooks.UNIT_FILE_ENV] == str(view_unit)
    assert Path(env[hooks.UNIT_FILE_ENV]).is_absolute()
    assert env[hooks.PROPOSALS_ENV] == str(attempt_dir / "proposals.jsonl")
    assert env[hooks.SESSION_KIND_ENV] == "matching"
    assert env["REVERSEAPOC_CLAIM"] == f"{EXE}/{UNIT}"
    assert view_unit.read_text(encoding="utf-8") == VIEW_TEXT  # the view is kept for inspection


def test_goal_prompt_of_a_night_names_the_view_unit(tmp_path):
    night = Night(tmp_path, sessions=[_view_session()], gate_exits=[1])
    night.run(config={"attempts_per_function": 1})
    assert VIEW_UNIT_REL in night.prompts[0]


def test_view_records_its_head_commit(tmp_path):
    """Orchestrator ruling F34: the commit the view was taken from is recorded beside it (07-34's
    renames-since check reads it)."""
    night = Night(tmp_path, sessions=[_view_session()], gate_exits=[1])
    night.run(config={"attempts_per_function": 1})
    head = (night.attempt_dir(1) / driver.VIEW_HEAD).read_text(encoding="utf-8").strip()
    assert head == night.base


def test_pack_reads_the_view_src(tmp_path):
    night = Night(tmp_path, sessions=[_view_session()], gate_exits=[1])
    night.run(config={"attempts_per_function": 1})
    attempt_dir = night.attempt_dir(1)
    assert night.packed == [(PICK, attempt_dir, attempt_dir / "view" / "src")]


@pytest.mark.parametrize("committed", [True, False])
def test_view_unit_lands_and_commits(tmp_path, committed):
    """The driver copies the view unit into src/ before the lint and the gate; at that moment
    src/ differs from HEAD only in the claimed unit, and the match commit holds exactly the
    unit, status.csv, the feed and the log."""
    night = Night(tmp_path, unit_committed=committed, sessions=[_view_session()], gate_exits=[0])
    seen_by: dict[str, list] = {"lint": [], "gate": []}

    def src_state() -> tuple[str, str]:
        status = night.git("status", "--porcelain=v1", "--untracked-files=all", "--", "src")
        return status, (night.repo / UNIT_REL).read_text(encoding="utf-8")

    def lint(pick):
        seen_by["lint"].append(src_state())
        return night._lint(pick)

    def gate(pick, n):
        seen_by["gate"].append(src_state())
        return night._gate(pick, n)

    night.run(lint=lint, gate=gate)
    code = " M" if committed else "??"
    assert seen_by["gate"] == [(f"{code} {UNIT_REL}\n", VIEW_TEXT)]
    assert seen_by["lint"] == seen_by["gate"]
    assert night.commit_files("feat(") == sorted([UNIT_REL, STATUS_REL, FEED_NAME, LOG])
    assert night.file_at("feat(", UNIT_REL) == VIEW_TEXT
    assert night.git("status", "--porcelain=v1", "--", "src") == ""


@pytest.mark.parametrize("committed", [True, False])
def test_failed_gate_restores_only_the_unit(tmp_path, committed):
    """A mismatch puts back only the landed unit: to HEAD's bytes, or deleted when HEAD has no
    such file; include/ is never restored (no restore of all of include/, D-27 P4)."""
    night = Night(tmp_path, unit_committed=committed, sessions=[_view_session()],
                  gate_exits=[1])  # fmt: skip
    night.run(config={"attempts_per_function": 1})
    if committed:
        assert _unit_text(night) == SCAFFOLD
    else:
        assert not (night.repo / UNIT_REL).exists()
    assert night.git("status", "--porcelain=v1", "--untracked-files=all", "--", "src") == ""
    restores = [call for call in night.git_calls if _verb(call) == "restore"]
    assert not [call for call in restores if any(a.startswith("include") for a in call)]
    assert _one(night.kinds("attempt"))["outcome"] == "GAVE_UP"


# ---- 07-13 Task 2: the ledger and the view-hash audit; no headers; the pre-gate restore ----

VIEW_REL = f"build/driver/{RUN}/{EXE}/{FUNC}/attempt-1/view"
OTHER_RECORD = {"kind": "abort", "run": "other", "exe": EXE, "function": "func_00020000",
                "unit": UNIT, "start": "0x00020000", "attempt": 1, "abort_reason": "transient",
                "retries": 3, "date": "2026-10-25"}  # made up: another worker's record


@pytest.mark.parametrize("rel", ["tools/keep.py", "tools/x.py", UNIT_REL])
def test_tracked_edit_outside_the_view_stops_the_night(tmp_path, rel):
    """D-24 edge (DEC-02 adjacency): a session that writes anything git can see, its own unit
    in src/ included, is a stray: STOPPED `guardrail` naming the path, the gate never runs,
    the file is quarantined and put back (HEAD's bytes, or moved out when new)."""
    night = Night(tmp_path, sessions=[Sess(write=rel)], gate_exits=[0])
    before = (night.repo / rel).read_bytes() if (night.repo / rel).is_file() else None
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert rel in report.detail
    assert night.gate_calls == []
    assert night.commits() == []
    assert (night.quarantine / rel).is_file()
    after = (night.repo / rel).read_bytes() if (night.repo / rel).is_file() else None
    assert after == before


@pytest.mark.parametrize("rel", ["include/common.h", f"src/{EXE}/u_other.c",
                                 f"config/{EXE}/status.csv"])  # fmt: skip
def test_view_edit_outside_the_unit_is_caught(tmp_path, rel):
    """Invariant (b): every view file but the unit and view/build/ is hashed at launch and
    again before landing; an edit or a new file elsewhere in the view stops the night."""
    sess = Sess(files=((f"{VIEW_REL}/{rel}", "/* made-up tamper */\n"),))
    night = Night(tmp_path, sessions=[sess], gate_exits=[0])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert f"{VIEW_REL}/{rel}" in report.detail
    assert night.gate_calls == []
    assert night.commits() == []


def test_view_build_output_is_not_a_stray(tmp_path):
    """The wrapper's container check writes the view's build/ (objects, logs): not hashed."""
    sess = Sess(files=((f"{VIEW_REL}/build/logs/cc.log", "made-up log\n"),))
    night = Night(tmp_path, sessions=[sess], gate_exits=[0])
    report = night.run()
    assert report.event == "ENDED"
    assert _feats(night) == [MATCH_SUBJECT]


def test_driver_written_files_are_not_strays(tmp_path):
    """Invariant (a): after the first session the driver's own uncommitted status.csv row and
    attempts.jsonl records differ from HEAD; the ledger explains them at the next audit."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),)), Sess()])
    report = night.run(config={"attempts_per_function": 2})
    assert [r["outcome"] for r in night.kinds("attempt")] == ["PARTIAL", "GAVE_UP"]
    assert report.event == "ENDED"


def test_a_table_change_the_driver_did_not_write_is_a_stray(tmp_path):
    """Invariant (a): the audit compares the tree with HEAD plus the ledger, not with the
    pre-session snapshot, so a status.csv change the driver did not write is a stray even when
    it happened before the session's snapshot (another writer between sessions)."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),)), Sess()])

    def tamper(args: list[str]) -> None:
        if len(night.launched) == 1 and "HEAD^{commit}" in args:
            with (night.repo / STATUS_REL).open("a", encoding="utf-8", newline="\n") as fh:
                fh.write("0x00099990,func_00099990,u_x,matched,100.00,1\n")

    night.on_git = tamper
    report = night.run(config={"attempts_per_function": 2})
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert STATUS_REL in report.detail


def test_ledger_explains_only_the_bytes_the_driver_wrote(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / STATUS_REL, STATUS_HEAD)
    ledger = driver._Ledger(repo)
    assert not ledger.knows(STATUS_REL)
    ledger.note(STATUS_REL)
    assert ledger.knows(STATUS_REL)
    assert ledger.matches(STATUS_REL)
    _write(repo / STATUS_REL, STATUS_HEAD + "0x1,func_1,u,partial,1.00,1\n")
    assert not ledger.matches(STATUS_REL)
    ledger.note(STATUS_REL)
    assert ledger.matches(STATUS_REL)
    (repo / STATUS_REL).unlink()
    assert not ledger.matches(STATUS_REL)


def test_no_header_is_committed(tmp_path):
    """D-19 (CONTEXT default): a matching session writes no include/ header. The old F5 case,
    a new include/x.h beside a match, now stops the night and the header is quarantined."""
    sess = Sess(files=(("include/x.h", "/* made-up header */\n"),))
    night = Night(tmp_path, sessions=[sess], gate_exits=[0])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert "include/x.h" in report.detail
    assert not (night.repo / "include" / "x.h").exists()
    assert (night.quarantine / "include" / "x.h").is_file()
    assert night.gate_calls == []
    assert night.commits() == []


def _gate_with_another_record(night: Night):
    """A gate during which another writer appends one record to the log (07-18's workers)."""

    def gate(pick, n):
        with (night.repo / LOG).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(OTHER_RECORD, separators=(",", ":")) + "\n")
        return night._gate(pick, n)

    return gate


def test_pre_gate_restore_keeps_the_log(tmp_path):
    """D-27 P4 (first half): after an unclaimed pass, status.csv and the feed go back to their
    pre-gate bytes, and progress/attempts.jsonl keeps every record (never restored)."""
    night = _night_with_matched_sibling(tmp_path, sessions=[Sess()], gate_exits=[0],
                                        gate_written=(SIBLING,))  # fmt: skip
    night.run(config={"attempts_per_function": 1}, gate=_gate_with_another_record(night))
    assert (night.repo / STATUS_REL).read_text(encoding="utf-8") == STATUS_HEAD + SIBLING_ROW
    assert (night.repo / FEED_NAME).read_text(encoding="utf-8") == "{}\n"
    assert OTHER_RECORD in night.records()
    assert _one(night.kinds("attempt"))["outcome"] == "GAVE_UP"


def test_undo_match_drops_only_its_matched_record(tmp_path):
    """F19: a failed match commit truncates the log to its length before the MATCHED append,
    so a record another writer appended before it stays."""
    night = _failed_commit_night(tmp_path)
    report = _run_contained(night, gate=_gate_with_another_record(night))
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert OTHER_RECORD in night.records()
    assert [r.get("outcome") for r in night.kinds("attempt")] == ["GAVE_UP"]
    assert "MATCHED" not in (night.repo / LOG).read_text(encoding="utf-8")


def test_a_view_unit_that_is_no_longer_a_file_is_a_stray(tmp_path):
    """The landing section copies only a regular file: a view unit the session replaced by a
    directory link stops the night before anything lands."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    night = Night(tmp_path, sessions=[Sess(link=(VIEW_UNIT_REL, elsewhere))], gate_exits=[0])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert VIEW_UNIT_REL in report.detail
    assert night.gate_calls == []
    assert _unit_text(night) == SCAFFOLD
