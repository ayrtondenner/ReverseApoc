# SPDX-License-Identifier: GPL-3.0-or-later
"""The typed call graph of one EXE (DEC-01, D-02). RED stub: the API surface only."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .functions import FunctionRow
from .le import Fixup

DIRECT, POINTER, TABLE, MIDROW, HAND = "direct", "pointer", "table", "midrow", "hand"
EDGE_KINDS = (DIRECT, POINTER, TABLE, MIDROW, HAND)


@dataclass(frozen=True, slots=True)
class Edge:
    src: int
    dst: int
    kind: str


@dataclass(frozen=True)
class CallGraph:
    edges: Mapping[int, tuple[Edge, ...]]
    midrow: tuple[Any, ...] = ()
    indirect: Mapping[int, int] = field(default_factory=dict)
    orphan_tables: tuple[int, ...] = ()

    @classmethod
    def build(
        cls,
        rows: Sequence[FunctionRow],
        flat: bytes | bytearray,
        fixups: Sequence[Fixup],
        *,
        code: tuple[int, int],
        data: tuple[int, int],
    ) -> CallGraph:
        return cls({})

    def callees(self, start: int) -> tuple[Edge, ...]:
        return ()

    def callers(self, start: int) -> tuple[int, ...]:
        return ()


def build_for(exe: Any) -> CallGraph:
    return CallGraph({})


def closure(
    graph: CallGraph, roots: Iterable[int], *, stop: frozenset[int] = frozenset()
) -> frozenset[int]:
    return frozenset(roots)
