# SPDX-License-Identifier: GPL-3.0-or-later
"""readlint (DEC-04, D-20): skeleton; the rules land in the GREEN commit."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .proposals import PLACEHOLDER

__all__ = ["PLACEHOLDER", "ReadlintError", "ReadlintResult", "Skipped", "Violation", "run_readlint"]


class ReadlintError(ValueError):
    """readlint cannot read its input (exit 2)."""


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    message: str


@dataclass(frozen=True)
class Skipped:
    path: str
    reason: str


@dataclass(frozen=True)
class ReadlintResult:
    files_checked: tuple[str, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    violations: tuple[Violation, ...] = ()
    waivers: dict[str, int] = field(default_factory=dict)
    allowlisted: dict[str, int] = field(default_factory=dict)

    def exit_code(self) -> int:
        return 0

    def format(self) -> str:
        return ""


def run_readlint(paths: Sequence[Path | str], *, src_root: Path, config_root: Path,
                 units=None, tier=None, report: bool = False) -> ReadlintResult:  # fmt: skip
    return ReadlintResult()
