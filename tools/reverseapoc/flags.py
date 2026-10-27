"""Per-unit cflags proposals (D-12): API stubs for the RED tests of plan 07-17."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

QUEUE = Path("config/cflags-proposals.toml")
FIELDS: tuple[str, ...] = ()


class FlagsError(ValueError):
    """The proposal queue or an attempt directory is malformed, or a flags verb is refused."""


@dataclass(frozen=True)
class Proposal:
    id: str
    exe: str
    unit: str
    glob: str
    rule: str
    base: str
    functions: tuple[str, ...]
    keeps: tuple[str, ...]
    siblings: tuple[str, ...]
    alternatives: tuple[str, ...]
    source: str
    candidate: str
    candidate_sha256: str
    evidence: tuple[str, ...]
    status: str
    regate_exit: int
    regate_variant: str
    regate_cflags_sha256: str
    regate_log: str
    approved_by: str
    approved_date: str
    reason: str


@dataclass(frozen=True)
class ProposeReport:
    added: tuple[str, ...] = ()
    merged: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()


def read_queue(path: Path) -> list[Proposal]:
    return []


def write_queue(path: Path, proposals: Sequence[Proposal]) -> None:
    return None


def pilot_hits(log: Path) -> list[tuple[str, str]]:
    return []


def propose(runs: Sequence[str], *, repo: Path, queue: Path | None = None) -> ProposeReport:
    return ProposeReport()
