"""config/<exe>/status.csv (D-20): the sparse per-function status table.

One row per matched or partial function, none for an unmatched one, so a missing row (or a
missing file) means unmatched. Columns `start,name,unit,status,best_percent,attempts,
source_sha256,date`:

- `start`: the functions.csv row start, `0x%08X` (functions.py's IN-05 rule);
- `name`, `unit`: the row's name and the unit file it is defined in;
- `status`: `matched` or `partial`;
- `best_percent`: objdiff's percent with two decimals, `100.00` for a matched row;
- `attempts`: a decimal count, 0 for a match by hand;
- `source_sha256`: SHA-256 of the unit file read as UTF-8 with CRLF as LF (`lf_sha256`), so any
  edit of matched C must be re-gated (D-22); for a partial row, of the saved attempt it scored;
- `date`: the UTC date of the gate run, `YYYY-MM-DD`.

There is no commit column: a commit cannot contain its own hash. The file starts with the
comment line STATUS_COMMENT, then the exact header; rows are sorted by start, one per start, LF
line endings, written through fileio.write_atomic. The only writer is `reverseapoc gate`
(gate.py, D-21). The reader is strict: a wrong comment or header, a CR, a blank line, an
unsorted or duplicate start, an unknown status or any malformed cell is a StatusError naming the
file line, so a hand edit is refused, never half-read.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .fileio import write_atomic
from .functions import (
    FunctionsError,
    _address,
    _format_csv,
    _parse_address,
    _read_records,
)

STATUS_COLUMNS = ("start", "name", "unit", "status", "best_percent", "attempts", "source_sha256", "date")  # noqa: E501
STATUS_COMMENT = "# written by: uv run reverseapoc gate EXE/UNIT; do not edit"
STATUS_FILE = "status.csv"
MATCHED, PARTIAL = "matched", "partial"
STATUSES = (MATCHED, PARTIAL)
PERCENT_MAX = 100.0  # objdiff's match_percent of an identical symbol
_PERCENT_DECIMALS = 2
_PERCENT_CELL = re.compile(r"(0|[1-9][0-9]{0,2})\.[0-9]{2}")
_COUNT_CELL = re.compile(r"0|[1-9][0-9]*")
_SHA256_CELL = re.compile(r"[0-9a-f]{64}")
_DATE_CELL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")  # a C function name
_UNIT_NAME = re.compile(r"[a-z0-9_]+")  # the units.csv rule
_FIRST_DATA_LINE = 3  # line 1 is the comment, line 2 the header


class StatusError(ValueError):
    """status.csv is malformed, or a row cannot be written to it."""


@dataclass(frozen=True)
class StatusRow:
    start: int
    name: str
    unit: str
    status: str
    best_percent: float
    attempts: int
    source_sha256: str
    date: str  # YYYY-MM-DD


def status_path(config_root: Path, exe_stem: str) -> Path:
    """config/<exe>/status.csv, next to functions.csv."""
    return Path(config_root) / exe_stem / STATUS_FILE


def lf_sha256(text: str) -> str:
    """SHA-256 (hex) of `text` encoded as UTF-8 with every CRLF read as LF, so a CRLF checkout of
    a unit file hashes as the committed (LF) file does."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def format_percent(percent: float) -> str:
    return f"{percent:.{_PERCENT_DECIMALS}f}"


def round_percent(percent: float) -> float:
    """`percent` as the table stores it (two decimals)."""
    return round(float(percent), _PERCENT_DECIMALS)


def check_row(row: StatusRow) -> None:
    """ValueError unless `row` is one the reader accepts: the writer refuses what it could not
    read back."""
    if not _NAME.fullmatch(row.name):
        raise ValueError(f"name {row.name!r} is not a C function name")
    if not _UNIT_NAME.fullmatch(row.unit):
        raise ValueError(f"unit {row.unit!r} must match [a-z0-9_]+")
    if row.status not in STATUSES:
        raise ValueError(f"status {row.status!r} is not one of {', '.join(STATUSES)}")
    percent = row.best_percent
    number = isinstance(percent, (int, float)) and not isinstance(percent, bool)
    if not (number and math.isfinite(percent) and 0.0 <= percent <= PERCENT_MAX
            and round_percent(percent) == percent):  # fmt: skip
        raise ValueError(f"best_percent {percent!r} is not a percent with two decimals")
    if row.status == MATCHED and percent != PERCENT_MAX:
        raise ValueError(f"a matched row has best_percent {format_percent(PERCENT_MAX)}, "
                         f"not {format_percent(percent)}")  # fmt: skip
    if isinstance(row.attempts, bool) or not isinstance(row.attempts, int) or row.attempts < 0:
        raise ValueError(f"attempts {row.attempts!r} is not a count")
    if not _SHA256_CELL.fullmatch(row.source_sha256):
        raise ValueError(f"source_sha256 {row.source_sha256!r} is not 64 lower-case hex digits")
    if not _DATE_CELL.fullmatch(row.date):
        raise ValueError(f"date {row.date!r} is not YYYY-MM-DD")
    date.fromisoformat(row.date)  # a real day: 2026-02-30 is a ValueError


def _cell(record: dict[str, str], column: str, pattern: re.Pattern[str], what: str) -> str:
    cell = record[column]
    if cell is None or not pattern.fullmatch(cell):
        raise ValueError(f"{column} {cell!r} is not {what}")
    return cell


def _parse(record: dict[str, str]) -> StatusRow:
    if None in record:
        raise ValueError("more fields than the header")
    row = StatusRow(
        start=_parse_address(record, "start"),
        name=record["name"] or "",
        unit=record["unit"] or "",
        status=record["status"] or "",
        best_percent=float(_cell(record, "best_percent", _PERCENT_CELL, "a percent like 73.50")),
        attempts=int(_cell(record, "attempts", _COUNT_CELL, "a decimal count")),
        source_sha256=record["source_sha256"] or "",
        date=record["date"] or "",
    )
    check_row(row)
    return row


def _check_lines(path: Path, data: bytes) -> None:
    """The line rules _read_records does not see: LF only, the comment first, a final LF, no
    other comment and no blank line, so data row n is file line n + 2."""
    if b"\r" in data:
        raise StatusError(f"{path}: line endings must be LF only")
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines[0] != STATUS_COMMENT:
        raise StatusError(f"{path}: line 1 is not {STATUS_COMMENT!r}")
    if not text.endswith("\n"):
        raise StatusError(f"{path}: line {len(lines)} has no final LF")
    body = lines[1:-1] if text.endswith("\n") else lines[1:]
    for number, line in enumerate(body, start=2):
        if not line or line.startswith("#"):
            raise StatusError(f"{path}: line {number}: a blank or comment line inside the table")


def read_status(path: Path) -> list[StatusRow]:
    """The rows of a status.csv, validated; a missing file has none (D-20: sparse)."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    _check_lines(path, data)
    try:
        records = _read_records(path, STATUS_COLUMNS)
    except FunctionsError as exc:
        raise StatusError(str(exc)) from exc
    rows: list[StatusRow] = []
    for number, record in enumerate(records, start=_FIRST_DATA_LINE):
        try:
            row = _parse(record)
        except (TypeError, ValueError) as exc:
            raise StatusError(f"{path}: line {number}: {exc}") from exc
        if rows and row.start == rows[-1].start:
            raise StatusError(f"{path}: line {number}: duplicate start {_address(row.start)}")
        if rows and row.start < rows[-1].start:
            raise StatusError(f"{path}: line {number}: start {_address(row.start)} is not after "
                              f"{_address(rows[-1].start)}; rows are sorted by start")  # fmt: skip
        rows.append(row)
    _check_bytes(path, data, rows)
    return rows


def _check_bytes(path: Path, data: bytes, rows: Sequence[StatusRow]) -> None:
    """The file is exactly what write_status writes for its rows (fix round 1, M8): a quoted or
    otherwise re-spelled cell that csv would accept is refused, naming its line."""
    expected = format_status(rows).encode("utf-8")
    if data == expected:
        return
    for number, (got, want) in enumerate(zip(data.split(b"\n"), expected.split(b"\n"),
                                             strict=False), start=1):  # fmt: skip
        if got != want:
            raise StatusError(f"{path}: line {number}: not written the way gate writes it "
                              "(a quoted or re-spelled cell)")  # fmt: skip
    raise StatusError(f"{path}: not written the way gate writes it")


def _cells(row: StatusRow) -> list[str]:
    return [_address(row.start), row.name, row.unit, row.status, format_percent(row.best_percent),
            str(row.attempts), row.source_sha256, row.date]  # fmt: skip


def format_status(rows: Iterable[StatusRow]) -> str:
    """The table text for `rows`, sorted by start; StatusError for a duplicate start or a row
    the reader would refuse."""
    ordered = sorted(rows, key=lambda r: r.start)
    for before, after in zip(ordered, ordered[1:], strict=False):
        if before.start == after.start:
            raise StatusError(f"duplicate start {_address(after.start)}")
    for row in ordered:
        try:
            check_row(row)
        except (TypeError, ValueError) as exc:
            raise StatusError(f"row {_address(row.start)}: {exc}") from exc
    return _format_csv(STATUS_COMMENT, STATUS_COLUMNS, [_cells(row) for row in ordered])


def write_status(path: Path, rows: Iterable[StatusRow]) -> None:
    """Write the table atomically (fileio.write_atomic), creating config/<exe>/; nothing is
    written when a row is refused. Only gate.py calls this (D-21)."""
    text = format_status(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, text.encode("utf-8"))
