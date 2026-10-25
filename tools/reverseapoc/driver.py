# SPDX-License-Identifier: GPL-3.0-or-later
"""The night driver's loop (AGT-01..AGT-04, AGT-06; D-05, D-07, D-08, D-17, D-21, D-23..D-25).

`drive(config, deps)` takes the picks one by one and gives each function fresh `claude -p`
sessions (session.py) in the checkout root. Only the driver's own container gate decides a match
(D-24): never the transcript, the result event or /goal's verdict. A match is committed with
explicit paths only (D-25); everything else is reset.

Every effect is an injected dependency (`Deps`), so the tests run the stand-in claude
(tests/fakeclaude.py), fake gates and a tmp git repo. The `drive` verb that wires the real ones
follows in plan 06-25.

Layout of one session (gitignored): build/driver/<run>/<exe>/<func>/attempt-<n>/ holds
transcript.jsonl, context.md, notes.md and the wrapper's checks/ and checks.jsonl.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import attempt, streamjson
from .fileio import write_atomic
from .picker import Key, Pick
from .session import TIMEOUT_S, SessionResult, goal_prompt

ATTEMPT_LOG = attempt.ATTEMPT_LOG  # progress/attempts.jsonl, committed (D-23)
DRIVER_DIR = Path(*attempt.DRIVER_PARTS)  # build/driver
FEED = "decomphub.progress.json"  # gate-written, committed with status.csv
TRANSCRIPT = "transcript.jsonl"
COMMIT_MSG = "commit-msg.txt"
COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"  # D-25, set explicitly
MATCHED_BY = "Matched-By: reverseapoc drive"
EXIT_OK = 0
MATCHED = "MATCHED"
KIND_ATTEMPT = "attempt"
_RUN_ID = re.compile(r"[A-Za-z0-9_.-]+")
_SHA1 = re.compile(r"[0-9a-f]{40}")


class DriverError(RuntimeError):
    """A driver step failed in a way no session caused (git, the gate's output, a driver file)."""


@dataclass(frozen=True)
class DriveConfig:
    """One night. `max_sessions` counts counted sessions only (D-08, D-48)."""

    run_id: str
    repo_root: Path
    tested_major: int  # F28; plan 06-25 passes session's TESTED_MAJOR
    min_cli_version: tuple[int, int, int]  # F28; plan 06-25 passes MIN_CLI_VERSION
    max_sessions: int = 30  # D-48
    target_matched: int = 10  # D-48
    attempts_per_function: int = 3  # D-07, per pass
    wall_clock_s: float = TIMEOUT_S  # D-07
    base_env: Mapping[str, str] | None = None  # the sessions' environment; None: os.environ


@dataclass(frozen=True)
class PackInfo:
    """What `reverseapoc context --json` reports for attempts.jsonl (D-14)."""

    pack_bytes: int
    truncated: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateRun:
    """`gate EXE/UNIT --attempts N --json` in the container: its exit code and parsed JSON."""

    exit_code: int
    doc: Mapping | None = None


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


@dataclass(frozen=True)
class Deps:
    """Every effect of the loop (D-05). `queue(difficult)` yields the picks, skipping the
    difficult keys; `requeue(difficult)` is picker.requeue wired with the matched set, callees
    and pool state; `matched_callees(pick)` is the snapshot kept with a capped function;
    `scaffold(pick)` writes src/<exe>/<unit>.c from the committed CSVs; `pack(pick, dir)` runs
    the context verb into the attempt dir; `argv(prompt)` is the claude argv
    (session.build_argv); `session` is session.run_session; `lint(pick)` is the C89 lint of the
    unit (0/1/2); `gate(pick, n)` and `partial_gate(pick, src, n)` are the container gates;
    `remove_containers(prefix)` removes containers by name prefix; `git(args)` runs git in the
    checkout."""

    queue: Callable[[Container[Key]], Iterable[Pick]]
    requeue: Callable[[Mapping[Key, tuple[Key, ...]]], Iterable[Key]]
    matched_callees: Callable[[Pick], tuple[Key, ...]]
    scaffold: Callable[[Pick], None]
    pack: Callable[[Pick, Path], PackInfo]
    argv: Callable[[str], Sequence[str]]
    session: Callable[..., SessionResult]
    lint: Callable[[Pick], int]
    gate: Callable[[Pick, int], GateRun]
    partial_gate: Callable[[Pick, str, int], int]
    remove_containers: Callable[[str], None]
    git: Callable[[Sequence[str]], subprocess.CompletedProcess]
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    today: Callable[[], str] = _today


@dataclass(frozen=True)
class DriveReport:
    """How the night ended: ENDED or STOPPED, why, and its counts."""

    event: str
    reason: str
    sessions: int
    matched: int
    detail: str | None = None

    @property
    def exit_code(self) -> int:
        return 0 if self.event == "ENDED" else 1


def git_runner(repo: Path, *, env: Mapping[str, str] | None = None):
    """`git <args>` in `repo` as an argv list, never a shell; stdout and stderr as bytes."""

    def git(args: Sequence[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=repo, env=None if env is None else dict(env),
                              capture_output=True, check=False)  # fmt: skip

    return git


def _git_ok(git: Callable[[Sequence[str]], subprocess.CompletedProcess], args: list[str]) -> bytes:
    done = git(args)
    if done.returncode != 0:
        why = (done.stderr or b"").decode("utf-8", "replace").strip()
        raise DriverError(f"git {' '.join(args[:2])} failed: {why}")
    return done.stdout or b""


# ---- the attempt log ----


def append_record(path: Path, record: Mapping) -> None:
    """Append one compact JSON line (LF) to `path`; a record is never rewritten (D-23)."""
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        fh.write(line.encode("ascii"))


# ---- the commit (D-25) ----


def commit_message(
    *,
    exe: str,
    function: str,
    unit: str,
    attempt_n: int,
    attempts: int,
    model: str | None,
    usage: streamjson.Usage,
    seconds: float,
    sha1s: Sequence[tuple[str, str]],
) -> str:
    """D-25's message for one match: subject, the attempt's figures, both SHA-1s, trailers."""
    lines = [
        f"feat({exe}): match {function} in {unit} (C89)",
        "",
        f"attempt {attempt_n}/{attempts}",
        f"model {model or 'unknown'}",
        f"turns {usage.turns}",
        f"tokens {usage.input_tokens} input, {usage.output_tokens} output, "
        f"{usage.cache_read_tokens} cache read, {usage.cache_creation_tokens} cache creation",
        f"seconds {round(seconds)}",
        "objdiff 100%",
        "relocation ok",
        *(f"sha1 {name} {sha1}" for name, sha1 in sha1s),
        "",
        COAUTHOR,
        MATCHED_BY,
    ]
    return "\n".join(lines) + "\n"


def commit_paths(git, *, message: str, message_file: Path, paths: Sequence[str]) -> None:
    """`git add -- <paths>` (a new unit or header is untracked, F5), then
    `git commit -F <file> -- <paths>`: explicit paths only, never `-A` or `.`."""
    write_atomic(message_file, message.encode("utf-8"))
    _git_ok(git, ["add", "--", *paths])
    _git_ok(git, ["commit", "-q", "-F", str(message_file), "--", *paths])


def gate_sha1s(doc: Mapping | None) -> list[tuple[str, str]]:
    """(EXE name, SHA-1) of each landed EXE in a gate's JSON (its checks' `splice` entries)."""
    found: dict[str, str] = {}
    checks = doc.get("checks") if isinstance(doc, Mapping) else None
    for check in checks if isinstance(checks, list) else ():
        splices = check.get("splice") if isinstance(check, Mapping) else None
        for entry in splices if isinstance(splices, list) else ():
            name = entry.get("exe") if isinstance(entry, Mapping) else None
            sha1 = entry.get("sha1") if isinstance(entry, Mapping) else None
            if isinstance(name, str) and isinstance(sha1, str) and _SHA1.fullmatch(sha1):
                found.setdefault(name, sha1)
    return sorted(found.items())


# ---- one claim ----


@dataclass(frozen=True)
class _Claim:
    """One session's claim and where its files go."""

    pick: Pick
    run: str
    repo: Path
    n: int

    @property
    def function(self) -> str:
        return f"func_{self.pick.start:08X}"

    @property
    def unit_rel(self) -> str:
        return f"src/{self.pick.exe}/{self.pick.unit}.c"

    @property
    def status_rel(self) -> str:
        return f"config/{self.pick.exe}/status.csv"

    @property
    def attempt_dir(self) -> Path:
        return self.repo.joinpath(DRIVER_DIR, self.run, self.pick.exe, self.function,
                                  f"attempt-{self.n}")  # fmt: skip

    @property
    def notes(self) -> Path:
        return self.attempt_dir / attempt.NOTES_FILE

    def env(self, base: Mapping[str, str]) -> dict[str, str]:
        """The session's environment: the base plus the four claim variables (absolute, F28)."""
        return {**base, attempt.CLAIM_ENV: f"{self.pick.exe}/{self.pick.unit}",
                attempt.FUNC_ENV: self.function, attempt.DIR_ENV: str(self.attempt_dir),
                attempt.NOTES_ENV: str(self.notes)}  # fmt: skip


@dataclass(frozen=True)
class _Session:
    """A finished session and what the driver measured around it."""

    claim: _Claim
    result: SessionResult
    pack: PackInfo
    seconds: float

    @property
    def init(self) -> Mapping:
        return streamjson.init_event(self.result.events) or {}

    @property
    def usage(self) -> streamjson.Usage:
        results = [e for e in self.result.events if e.get("type") == "result"]
        return streamjson.usage(results[-1] if results else {})

    @property
    def model(self) -> str | None:
        model = self.init.get("model")
        return model if isinstance(model, str) else None


class _Night:
    def __init__(self, config: DriveConfig, deps: Deps) -> None:
        if not _RUN_ID.fullmatch(config.run_id):
            raise DriverError(f"run id {config.run_id!r} is not [A-Za-z0-9_.-]+")
        self.config = config
        self.deps = deps
        self.repo = Path(config.repo_root)
        self.log = self.repo / ATTEMPT_LOG
        self.sessions = 0
        self.matched = 0

    def run(self) -> DriveReport:
        for pick in self.deps.queue(frozenset()):
            claim = _Claim(pick, self.config.run_id, self.repo, 1)
            self._counted(self._launch(claim))
        return DriveReport("ENDED", "queue exhausted", self.sessions, self.matched)

    def _launch(self, claim: _Claim) -> _Session:
        unit = self.repo / claim.unit_rel
        if not unit.exists():
            self.deps.scaffold(claim.pick)
        claim.attempt_dir.mkdir(parents=True, exist_ok=True)
        pack = self.deps.pack(claim.pick, claim.attempt_dir)
        prompt = goal_prompt(claim.function, claim.pick.unit, claim.pick.exe)
        base = self.config.base_env
        env = claim.env(dict(base) if base is not None else dict(os.environ))
        start = self.deps.clock()
        try:
            result = self.deps.session(self.deps.argv(prompt), cwd=self.repo, env=env,
                                       transcript=claim.attempt_dir / TRANSCRIPT,
                                       timeout_s=self.config.wall_clock_s)  # fmt: skip
        finally:
            self.deps.remove_containers(attempt.container_prefix(claim.attempt_dir))
        return _Session(claim, result, pack, self.deps.clock() - start)

    def _counted(self, session: _Session) -> None:
        self.sessions += 1
        claim = session.claim
        gate = self.deps.gate(claim.pick, claim.n)
        if gate.exit_code == EXIT_OK:
            self._commit_match(session, gate)

    def _commit_match(self, session: _Session, gate: GateRun) -> None:
        claim = session.claim
        append_record(self.log, {"kind": KIND_ATTEMPT, "run": claim.run, "exe": claim.pick.exe,
                                 "function": claim.function, "unit": claim.pick.unit,
                                 "attempt": claim.n, "outcome": MATCHED})  # fmt: skip
        message = commit_message(exe=claim.pick.exe, function=claim.function,
                                 unit=claim.pick.unit, attempt_n=claim.n,
                                 attempts=self.config.attempts_per_function,
                                 model=session.model, usage=session.usage,
                                 seconds=session.seconds, sha1s=gate_sha1s(gate.doc))  # fmt: skip
        status = _git_ok(self.deps.git, ["status", "--porcelain=v1", "--untracked-files=all",
                                         "-z", "--", "include"])  # fmt: skip
        headers = [entry[3:] for entry in status.decode("utf-8", "surrogateescape").split("\0")
                   if entry.startswith("?? ")]  # fmt: skip
        paths = [claim.unit_rel, claim.status_rel, FEED, ATTEMPT_LOG.as_posix(), *headers]
        commit_paths(self.deps.git, message=message, message_file=claim.attempt_dir / COMMIT_MSG,
                     paths=paths)  # fmt: skip
        self.matched += 1


def drive(config: DriveConfig, deps: Deps) -> DriveReport:
    """Run one night (see the module docstring)."""
    return _Night(config, deps).run()
