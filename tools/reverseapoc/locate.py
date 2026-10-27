# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry locators (stub: plan 07-12 Task 1 RED)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class LocateError(ValueError):
    """A locator input is wrong."""


@dataclass(frozen=True)
class StringRef:
    address: int
    keyword: str
    rows: tuple[int, ...]


@dataclass(frozen=True)
class Site:
    caller: int
    call_va: int
    section: int | None = None
    index: int | None = None
    partial: bool = False


def load_inputs(config_root: Path, orig_dir: Path, manifest: Path, exe: str):
    raise NotImplementedError


def string_refs(exe, keyword: str) -> list[StringRef]:
    return []


def table_refs(exe, lo: int, hi: int) -> tuple[int, ...]:
    return ()


def interrupt_callers(exe, vector: int) -> list[Site]:
    return []
