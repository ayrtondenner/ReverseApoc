"""The D-19 naming-proposal format (interface skeleton; behaviour follows in GREEN)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .functions import SYMBOL_KINDS

OPS = ("rename", "header")
KINDS = SYMBOL_KINDS  # symbols.csv kinds: ("func", "data")
EVIDENCE_KINDS = ("string", "table", "call", "vocab")


class ProposalError(ValueError):
    """A proposals.jsonl line that is not one well-formed proposal; the message names the line."""


@dataclass(frozen=True)
class Rename:
    exe: str
    kind: str
    address: int
    name: str
    evidence: str


@dataclass(frozen=True)
class Header:
    path: str
    text: str
    evidence: str


def parse_line(text: str, lineno: int) -> Rename | Header | None:
    return None


def read_proposals(path: Path) -> list[Rename | Header]:
    return []
