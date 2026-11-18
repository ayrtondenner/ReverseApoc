# SPDX-License-Identifier: GPL-3.0-or-later
"""A per-function archive of the candidate sources tried on one row (todo candidate-archive).

After AlphaEvolve's program database and MAP-Elites cells
(docs/research/notes-ideas-tooling-reproducibility.md #9): many good candidates, one cell per
failure class, instead of one best. `build/batch/archive/<exe>/<start:08x>.jsonl` holds one line
per distinct source, keyed by source_key, with its score, its stack score, its class
(classify.CLASSES; null for an agent's check, which no class was read for) and where it came
from. It is local and gitignored: the C is our own candidates', but it is a cache, not a record.

Two kinds of candidate reach it. `search` records what it compiled and kept (its base, its seeds,
each variant that became the base and the winner), measured under its own cells. An agent's
checks are read from the driver's attempt directories each time a search loads the archive, so
nothing in `attempt check` changes; a check of a source the archive already holds is left out,
because the search's measurement carries a class. A check's percent is objdiff's, a search's
score is batch.judge's: both run from 0 to 100, and the seed a search picks is judged again by
its own first wave, so the mix only orders the seeds.

source_key hashes the C tokens of the whole source: comments and layout do not change it, a
literal does, and a directive keeps its line. It is this module's own normalisation (a hash of
normalised C for repeated checks in attempt.py is another worker's and not shared).

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import attempt, batch, check
from .check import EXIT_TOOL
from .fileio import write_atomic
from .targets import REPO_ROOT

ROOT = batch.BUILD_ROOT / "archive"
DRIVER = REPO_ROOT.joinpath(*attempt.DRIVER_PARTS)  # build/driver/<run>/<exe>/<func>/attempt-<n>/
HOLD_RUN_MARKER = attempt.HOLD_RUN_MARKER  # D-17: a hold run's work never reaches another arm
KEEP = 4  # the entries kept per class
SEEDS = 3  # the archived candidates a search compiles beside its base
_LITERAL = r"\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'"
_TOKEN = re.compile(rf"{_LITERAL}|->|\+\+|--|<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||##|\.\.\."
                    r"|[-+*/%&|^]=|\w+|\S")  # fmt: skip
_FIELDS = {"key": str, "exact": bool, "score": (int, float),
           "stack_score": (int, float, type(None)), "class": (str, type(None)), "origin": str,
           "source": str}  # fmt: skip


class ArchiveError(batch.BatchError):
    """An archive file that is not one: the line and what is wrong with it."""


@dataclass(frozen=True)
class Entry:
    key: str  # source_key(source)
    exact: bool
    score: float
    stack_score: float | None  # None: an agent's check, which reports none
    klass: str | None  # classify's class of the best cell; None: not read
    origin: str  # "search", or "check <run>/attempt-<n>/<NNNN>"
    source: str  # the whole C file that was compiled


def _blank_comment(found: re.Match[str]) -> str:
    """A comment as spaces, its line breaks kept, so a directive keeps its line; a literal as is."""
    text = found.group()
    return re.sub(r"[^\n]", " ", text) if text.startswith("/") else text


def normalized(text: str) -> str:
    """The C tokens of `text`, joined by one space, a directive's line ending with a newline."""
    uncommented = check._configure()._NOT_CODE.sub(_blank_comment, text)
    out: list[str] = []
    for line in uncommented.split("\n"):
        tokens = _TOKEN.findall(line)
        out.extend(tokens)
        if tokens and tokens[0] == "#":
            out.append("\n")
    return " ".join(out)


def source_key(text: str) -> str:
    return hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()


def path(stem: str, start: int) -> Path:
    return ROOT / stem / f"{start:08x}.jsonl"


def _rank(entry: Entry) -> tuple[bool, float, float]:
    stack = entry.score if entry.stack_score is None else entry.stack_score
    return entry.exact, stack, entry.score


def ranked(entries: Iterable[Entry]) -> list[Entry]:
    """`entries` best first, as search ranks its variants: exact, then the stack score, then the
    raw score. A check reports no stack score, so its score stands in for one."""
    return sorted(entries, key=_rank, reverse=True)


def to_json(entry: Entry) -> dict[str, Any]:
    return {"key": entry.key, "exact": entry.exact, "score": entry.score,
            "stack_score": entry.stack_score, "class": entry.klass, "origin": entry.origin,
            "source": entry.source}  # fmt: skip


def _typed(value: object, kinds: type | tuple[type, ...]) -> bool:
    """`value` is of `kinds`; a bool is no number here."""
    if kinds is bool:
        return isinstance(value, bool)
    return isinstance(value, kinds) and not isinstance(value, bool)


def _entry(raw: str) -> Entry:
    """One archive line; ValueError naming what is wrong."""
    line = json.loads(raw)
    if not isinstance(line, dict) or set(line) != set(_FIELDS):
        raise ValueError(f"not an archive entry: the fields are {sorted(_FIELDS)}")
    wrong = [name for name, kinds in _FIELDS.items() if not _typed(line[name], kinds)]
    if wrong:
        raise ValueError(f"{wrong[0]} has the wrong type")
    return Entry(line["key"], line["exact"], float(line["score"]),
                 None if line["stack_score"] is None else float(line["stack_score"]),
                 line["class"], line["origin"], line["source"])  # fmt: skip


def read(stem: str, start: int) -> list[Entry]:
    """The archive of one row, best first; none when nothing was archived. ArchiveError for a
    line that is not an entry."""
    file = path(stem, start)
    if not file.is_file():
        return []
    entries = []
    for number, raw in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
        try:
            entries.append(_entry(raw))
        except ValueError as exc:  # json.JSONDecodeError is one
            raise ArchiveError(f"{file}:{number}: {exc}") from None
    return ranked(entries)


def _kept(entries: Iterable[Entry]) -> list[Entry]:
    """The best KEEP entries of each class, best first."""
    counts: dict[str | None, int] = {}
    kept = []
    for entry in ranked(entries):
        counts[entry.klass] = counts.get(entry.klass, 0) + 1
        if counts[entry.klass] <= KEEP:
            kept.append(entry)
    return kept


def record(stem: str, start: int, entries: Iterable[Entry]) -> None:
    """Merge `entries` into the row's archive: a source already there takes the new measurement,
    and each class keeps its best KEEP."""
    merged = {entry.key: entry for entry in read(stem, start)}
    merged.update((entry.key, entry) for entry in entries)
    lines = "".join(json.dumps(to_json(entry)) + "\n" for entry in _kept(merged.values()))
    path(stem, start).parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path(stem, start), lines.encode("utf-8"))


def _scored_check(line: dict[str, Any] | None) -> bool:
    """A plain, scored check: no sweep (its percent is under other flags), no tool error, a
    percent, and a source of attempt.py's form (attempt._SAVED_SOURCE, as attempt._plain_runs
    reads it)."""
    if line is None or line.get("sweep") is not False or line.get("exit") == EXIT_TOOL:
        return False
    percent, source = line.get("best_percent"), line.get("source")
    if not isinstance(percent, int | float) or isinstance(percent, bool):
        return False
    return isinstance(source, str) and attempt._SAVED_SOURCE.fullmatch(source) is not None


def _check_lines(log: Path) -> Iterator[dict[str, Any]]:
    """The plain, scored checks of one checks.jsonl. A line that is not JSON is skipped, as
    driver.read_checks skips it."""
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = attempt._parse(raw)
        if _scored_check(line):
            yield line


def _source(file: Path) -> str | None:
    """The C of one check, or None when it is gone or not UTF-8, as attempt's earlier best C
    leaves such a record out."""
    try:
        return file.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _checks(stem: str, func: str) -> Iterator[Entry]:
    """Every plain check of `func` in the driver's attempt directories, hold runs left out."""
    for log in sorted(DRIVER.glob(f"*/{stem}/{func}/attempt-*/{attempt.CHECK_LOG}")):
        run = log.relative_to(DRIVER).parts[0]
        if (DRIVER / run / HOLD_RUN_MARKER).exists():
            continue
        for line in _check_lines(log):
            text = _source(log.parent / line["source"])
            if text is None:
                continue
            origin = f"check {run}/{log.parent.name}/{Path(line['source']).stem}"
            yield Entry(source_key(text), False, float(line["best_percent"]), None, None, origin,
                        text)  # fmt: skip


def load(stem: str, start: int, func: str) -> list[Entry]:
    """The row's archive, plus each agent's check of `func` whose source it does not hold yet,
    the best check of one source kept; best first. Nothing is written."""
    entries = {entry.key: entry for entry in read(stem, start)}
    for entry in ranked(_checks(stem, func)):
        entries.setdefault(entry.key, entry)
    return ranked(entries.values())


def seeds(entries: Sequence[Entry]) -> list[Entry]:
    """The best entry of each class, best first, at most SEEDS: two near misses that fail for
    different reasons carry different information."""
    best: dict[str | None, Entry] = {}
    for entry in ranked(entries):
        best.setdefault(entry.klass, entry)
    return ranked(best.values())[:SEEDS]
