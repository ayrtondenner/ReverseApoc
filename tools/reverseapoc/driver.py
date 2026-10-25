# SPDX-License-Identifier: GPL-3.0-or-later
"""The night driver's loop (AGT-01..AGT-04, AGT-06; D-05, D-07, D-08, D-17, D-21, D-23..D-25).

Skeleton: the public interface only, so the plan 06-23 tests fail on their assertions.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .picker import Key, Pick
from .session import TIMEOUT_S, SessionResult

COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
MATCHED_BY = "Matched-By: reverseapoc drive"


class DriverError(RuntimeError):
    """A driver step failed in a way no session caused (git, a malformed driver file)."""


@dataclass(frozen=True)
class DriveConfig:
    run_id: str
    repo_root: Path
    tested_major: int
    min_cli_version: tuple[int, int, int]
    max_sessions: int = 30
    target_matched: int = 10
    attempts_per_function: int = 3
    wall_clock_s: float = TIMEOUT_S
    base_env: Mapping[str, str] | None = None


@dataclass(frozen=True)
class PackInfo:
    pack_bytes: int
    truncated: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateRun:
    exit_code: int
    doc: Mapping | None = None


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


@dataclass(frozen=True)
class Deps:
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
    event: str
    reason: str
    sessions: int
    matched: int
    detail: str | None = None

    @property
    def exit_code(self) -> int:
        return 0 if self.event == "ENDED" else 1


def git_runner(repo: Path, *, env: Mapping[str, str] | None = None):
    """`git <args>` in `repo` as an argv list; stdout and stderr captured as bytes."""

    def git(args: Sequence[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=repo, env=None if env is None else dict(env),
                              capture_output=True, check=False)  # fmt: skip

    return git


def drive(config: DriveConfig, deps: Deps) -> DriveReport:
    return DriveReport("ENDED", "nothing to do", 0, 0)
