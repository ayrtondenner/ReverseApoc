# SPDX-License-Identifier: GPL-3.0-or-later
"""The D-23 asm detector (stub: plan 07-12 Task 3 RED)."""

from __future__ import annotations

from collections.abc import Sequence

from .mechanics import AsmRow

TAGS = ("unaligned", "stack-frame", "enter", "pushal", "iretd", "nop-pad", "library-span")
ALIGNMENT = 16
LIBRARY_UNITS: dict[str, tuple[str, ...]] = {
    "ufo2p": ("u_000161b4", "u_000c8e40", "u_000c1b4b"),
    "tacp": ("u_000cc150",),
}


class AsmClassError(ValueError):
    """The detector's inputs are wrong."""


def classify(exe, *, library: Sequence[str] | None = None) -> list[AsmRow]:
    return []


def merge(existing: Sequence[AsmRow], proposed: Sequence[AsmRow]) -> tuple[list[AsmRow],
                                                                            list[str]]:  # fmt: skip
    return list(existing), []
