#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# ReverseApoc tooling (tools/ is GPLv3 or later, docs/legal.md). Only the design of AnyPS5's
# progress page (treemap, badge, Pages) is reused, none of its code.
"""Derive the published progress figures from the committed CSVs (RPT-02, D-26..D-29, D-50).

Every number comes from config/<exe>/functions.csv, units.csv and the gate-written status.csv
(D-20, D-26), by one deterministic function, `derive`:

- the code bytes are the game and thunk rows; a status.csv `matched` row makes its function
  matched, a `partial` row partial, no row unmatched (status.csv is sparse);
- the uncovered bytes lie inside a units.csv span but in no functions.csv row (D-50). Most are
  alignment filler; they count as unmatched code, so they are in the denominator (D-40);
- the percent is matched bytes over code plus uncovered bytes, per EXE and combined;
- the runtime library ("library, not decompiled") is its own group outside the percentage, and
  data-in-code is excluded (D-26);
- bytes outside every unit span (the 3-byte UFO2P tail past 0x000CFADA) are not in any CSV row
  and are recorded as not counted (D-50).

Outputs hold addresses, names, counts and percents only, never game bytes. Each is JSON with an
indent of 2, LF line endings and a trailing newline, percents rounded to 4 decimals, written
through a temporary file and os.replace, so two runs over the same CSVs give the same bytes and
an interrupted run leaves the previous file whole. The script is stdlib-only and Python 3.12
syntax: the Pages runner runs it with its system `python3 -I` (D-27), where reverseapoc is not
importable. `gate` loads it by path (functools.cache, like check._configure loads configure.py).

    python -I tools/progress.py [--config DIR] [--out DIR] [--commit SHA]

--out DIR writes DIR/progress.json and DIR/progress-shield.json (the shields.io endpoint).
Exit 0 on success, 2 when a CSV is malformed or an argument is wrong.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import dataclasses
import json
import os
import re
import secrets
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config"
# The EXEs by config stem, in publication order, with the label the page shows.
EXES = (("ufo2p", "UFO2P.EXE"), ("tacp", "TACP.EXE"))

FUNCTIONS_CSV, UNITS_CSV, STATUS_CSV = "functions.csv", "units.csv", "status.csv"
FUNCTIONS_COLUMNS = ("start", "end", "name", "kind", "unit", "evidence")
UNITS_COLUMNS = ("unit", "start", "end", "reason")
STATUS_COLUMNS = ("start", "name", "unit", "status", "best_percent", "attempts", "source_sha256",
                  "date")  # fmt: skip
KIND_GAME, KIND_THUNK, KIND_RUNTIME, KIND_DATA = "game", "thunk", "runtime", "data-in-code"
KINDS = (KIND_GAME, KIND_THUNK, KIND_RUNTIME, KIND_DATA)
CODE_KINDS = (KIND_GAME, KIND_THUNK)
MATCHED, PARTIAL, UNMATCHED = "matched", "partial", "unmatched"
_ADDRESS_CELL = re.compile(r"0x[0-9A-F]{8}")  # functions.py's 0x%08X rule
_PERCENT_CELL = re.compile(r"(0|[1-9][0-9]{0,2})\.[0-9]{2}")  # status.py's best_percent rule
_COMMIT = re.compile(r"[0-9a-f]{7,64}")
_COMMENT = "#"

PERCENT_DECIMALS = 4
PERCENT_MAX = 100.0  # also objdiff's figure for a zero total (calc_matched_percent)
PROGRESS_VERSION = 1
PROGRESS_JSON, SHIELD_JSON = "progress.json", "progress-shield.json"
SHIELD_SCHEMA_VERSION = 1
SHIELD_LABEL = "decompiled"
# (lowest percent, shields.io named colour), checked from the top.
SHIELD_COLORS = ((100.0, "brightgreen"), (50.0, "green"), (25.0, "yellowgreen"),
                 (10.0, "yellow"), (1.0, "orange"), (0.0, "red"))  # fmt: skip
NOTES = (
    "uncovered: bytes inside a units.csv span that belong to no functions.csv row. Most are "
    "alignment filler; they count as unmatched code in the denominator until rows reach them "
    "(D-40, D-50).",
    "The 3 bytes of UFO2P past 0x000CFADA lie outside every unit span and are not counted (D-50).",
    "library: the Watcom runtime, not decompiled, kept outside the percentage; data-in-code is "
    "excluded (D-26).",
)


class ProgressError(ValueError):
    """A committed CSV is missing, malformed or inconsistent."""


# ---- the minimal CSV reader (reverseapoc's readers are not importable under -I) ----


@dataclass(frozen=True)
class Row:
    """One functions.csv row: [start, end) in linear addresses."""

    start: int
    end: int
    name: str
    kind: str
    unit: str

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Unit:
    """One units.csv row."""

    unit: str
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Status:
    """One status.csv row, the columns progress reads."""

    start: int
    name: str
    unit: str
    status: str
    best_percent: float


def _records(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    """The data rows of a CSV as dicts; `#` comment lines skipped, the header checked."""
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ProgressError(f"{path}: cannot read ({exc})") from None
    reader = csv.DictReader(line for line in text.splitlines() if not line.startswith(_COMMENT))
    if tuple(reader.fieldnames or ()) != tuple(columns):
        raise ProgressError(f"{path}: header is not {','.join(columns)}")
    records = list(reader)
    for number, record in enumerate(records, start=1):
        if None in record or None in record.values():
            raise ProgressError(f"{path}: data row {number}: not {len(columns)} fields")
    return records


def _address(path: Path, number: int, column: str, cell: str) -> int:
    if not _ADDRESS_CELL.fullmatch(cell):
        raise ProgressError(f"{path}: data row {number}: {column} {cell!r} is not 0x%08X")
    return int(cell, 16)


def _check_span(path: Path, number: int, start: int, end: int, previous_end: int) -> None:
    if end <= start:
        raise ProgressError(f"{path}: data row {number}: end is not after start")
    if start < previous_end:
        raise ProgressError(f"{path}: data row {number}: overlaps or precedes the row before it")


def read_functions(path: Path) -> list[Row]:
    """functions.csv rows, sorted and non-overlapping, each kind one of KINDS."""
    rows: list[Row] = []
    for number, rec in enumerate(_records(path, FUNCTIONS_COLUMNS), start=1):
        row = Row(_address(path, number, "start", rec["start"]),
                  _address(path, number, "end", rec["end"]), rec["name"], rec["kind"],
                  rec["unit"])  # fmt: skip
        if row.kind not in KINDS:
            raise ProgressError(f"{path}: data row {number}: kind {row.kind!r} is not one of "
                                f"{', '.join(KINDS)}")  # fmt: skip
        _check_span(path, number, row.start, row.end, rows[-1].end if rows else 0)
        rows.append(row)
    return rows


def read_units(path: Path) -> list[Unit]:
    """units.csv rows, sorted and non-overlapping."""
    units: list[Unit] = []
    for number, rec in enumerate(_records(path, UNITS_COLUMNS), start=1):
        unit = Unit(rec["unit"], _address(path, number, "start", rec["start"]),
                    _address(path, number, "end", rec["end"]))  # fmt: skip
        _check_span(path, number, unit.start, unit.end, units[-1].end if units else 0)
        units.append(unit)
    return units


def read_status(path: Path) -> list[Status]:
    """status.csv rows; a missing file has none (D-20: sparse)."""
    if not Path(path).exists():
        return []
    rows: list[Status] = []
    for number, rec in enumerate(_records(path, STATUS_COLUMNS), start=1):
        if rec["status"] not in (MATCHED, PARTIAL):
            raise ProgressError(f"{path}: data row {number}: status {rec['status']!r} is not "
                                f"{MATCHED} or {PARTIAL}")  # fmt: skip
        if not _PERCENT_CELL.fullmatch(rec["best_percent"]):
            raise ProgressError(f"{path}: data row {number}: best_percent "
                                f"{rec['best_percent']!r} is not a percent with 2 decimals")
        start = _address(path, number, "start", rec["start"])
        if rows and start <= rows[-1].start:
            raise ProgressError(f"{path}: data row {number}: starts are not sorted and unique")
        rows.append(Status(start, rec["name"], rec["unit"], rec["status"],
                           float(rec["best_percent"])))  # fmt: skip
    return rows


# ---- the derivation ----


def percent(part: int, total: int) -> float:
    """part / total in percent, 4 decimals; a zero total gives 100.0 (objdiff's rule)."""
    if total == 0:
        return PERCENT_MAX
    return round(100.0 * part / total, PERCENT_DECIMALS)


@dataclass(frozen=True)
class Function:
    """A game or thunk function and its status (D-20)."""

    start: int
    end: int
    name: str  # status.csv's name when it has a row (symbols.csv renames), else functions.csv's
    kind: str
    unit: str
    status: str  # MATCHED, PARTIAL or UNMATCHED
    best_percent: float  # 100.0 matched, the partial row's percent, 0.0 unmatched

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Totals:
    """Byte and function counts that add up across EXEs."""

    code_bytes: int = 0  # game + thunk rows
    matched_bytes: int = 0
    partial_bytes: int = 0
    uncovered_bytes: int = 0
    library_bytes: int = 0
    library_functions: int = 0
    data_in_code_bytes: int = 0
    total_functions: int = 0
    matched_functions: int = 0
    partial_functions: int = 0

    def __add__(self, other: Totals) -> Totals:
        return Totals(*(getattr(self, f.name) + getattr(other, f.name)
                        for f in dataclasses.fields(self)))  # fmt: skip

    @property
    def unmatched_bytes(self) -> int:
        return self.code_bytes - self.matched_bytes - self.partial_bytes

    @property
    def denominator_bytes(self) -> int:
        return self.code_bytes + self.uncovered_bytes

    @property
    def percent(self) -> float:
        return percent(self.matched_bytes, self.denominator_bytes)


@dataclass(frozen=True)
class ExeProgress:
    """One EXE: its game/thunk functions with status, its units and their uncovered bytes."""

    stem: str
    label: str
    functions: tuple[Function, ...]
    units: tuple[Unit, ...]
    uncovered: tuple[int, ...]  # per unit, in `units` order
    library_bytes: int
    library_functions: int
    data_in_code_bytes: int

    @property
    def totals(self) -> Totals:
        def total(status: str) -> int:
            return sum(f.size for f in self.functions if f.status == status)

        return Totals(
            code_bytes=sum(f.size for f in self.functions),
            matched_bytes=total(MATCHED),
            partial_bytes=total(PARTIAL),
            uncovered_bytes=sum(self.uncovered),
            library_bytes=self.library_bytes,
            library_functions=self.library_functions,
            data_in_code_bytes=self.data_in_code_bytes,
            total_functions=len(self.functions),
            matched_functions=sum(1 for f in self.functions if f.status == MATCHED),
            partial_functions=sum(1 for f in self.functions if f.status == PARTIAL),
        )


@dataclass(frozen=True)
class Progress:
    """Every EXE in EXES order."""

    exes: tuple[ExeProgress, ...]

    def exe(self, stem: str) -> ExeProgress:
        return next(e for e in self.exes if e.stem == stem)

    @property
    def combined(self) -> Totals:
        out = Totals()
        for exe in self.exes:
            out = out + exe.totals
        return out


def _uncovered(units: Sequence[Unit], rows: Sequence[Row]) -> tuple[int, ...]:
    """Per unit, the bytes of its span that no row covers (rows sorted, non-overlapping)."""
    starts = [row.start for row in rows]
    out = []
    for unit in units:
        first = max(bisect.bisect_right(starts, unit.start) - 1, 0)
        covered = 0
        for row in rows[first:]:
            if row.start >= unit.end:
                break
            covered += max(0, min(row.end, unit.end) - max(row.start, unit.start))
        out.append(unit.size - covered)
    return tuple(out)


def _function(row: Row, status: Status | None) -> Function:
    if status is None:
        return Function(row.start, row.end, row.name, row.kind, row.unit, UNMATCHED, 0.0)
    best = PERCENT_MAX if status.status == MATCHED else status.best_percent
    return Function(row.start, row.end, status.name, row.kind, row.unit, status.status, best)


def _derive_exe(config: Path, stem: str, label: str) -> ExeProgress:
    exe_dir = Path(config) / stem
    rows = read_functions(exe_dir / FUNCTIONS_CSV)
    units = read_units(exe_dir / UNITS_CSV)
    statuses = {s.start: s for s in read_status(exe_dir / STATUS_CSV)}
    code = [row for row in rows if row.kind in CODE_KINDS]
    stray = sorted(set(statuses) - {row.start for row in code})
    if stray:
        raise ProgressError(f"{exe_dir / STATUS_CSV}: the row at 0x{stray[0]:08X} names no game "
                            f"or thunk row of {FUNCTIONS_CSV}")  # fmt: skip
    library = [row for row in rows if row.kind == KIND_RUNTIME]
    return ExeProgress(
        stem=stem,
        label=label,
        functions=tuple(_function(row, statuses.get(row.start)) for row in code),
        units=tuple(units),
        uncovered=_uncovered(units, rows),
        library_bytes=sum(row.size for row in library),
        library_functions=len(library),
        data_in_code_bytes=sum(row.size for row in rows if row.kind == KIND_DATA),
    )


def derive(config_dir: Path = DEFAULT_CONFIG) -> Progress:
    """The progress of every EXE in EXES from config_dir/<stem>/{functions,units,status}.csv."""
    return Progress(tuple(_derive_exe(Path(config_dir), stem, label) for stem, label in EXES))


# ---- outputs ----


def render(doc: object) -> bytes:
    """JSON bytes: indent 2, ASCII, LF, trailing newline."""
    return (json.dumps(doc, indent=2) + "\n").encode("ascii")


def _write_atomic(path: Path, data: bytes) -> None:
    """Write `data` to a fresh temporary file next to `path`, then os.replace it in: a failed
    write leaves the previous file whole and no temporary file behind (fileio.write_atomic's
    rule; reverseapoc is not importable under -I)."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fh = tmp.open("xb")
    try:
        with fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _totals_doc(totals: Totals) -> dict[str, object]:
    return {
        "code_bytes": totals.code_bytes,
        "matched_bytes": totals.matched_bytes,
        "partial_bytes": totals.partial_bytes,
        "unmatched_bytes": totals.unmatched_bytes,
        "uncovered_bytes": totals.uncovered_bytes,
        "denominator_bytes": totals.denominator_bytes,
        "percent": totals.percent,
        "library_bytes": totals.library_bytes,
        "library_functions": totals.library_functions,
        "data_in_code_bytes": totals.data_in_code_bytes,
        "functions": {"total": totals.total_functions, "matched": totals.matched_functions,
                      "partial": totals.partial_functions},  # fmt: skip
    }


def build_progress(progress: Progress, commit: str | None = None) -> dict[str, object]:
    """progress.json: per EXE and combined counts, the percent, and the notes (D-26, D-50)."""
    return {
        "version": PROGRESS_VERSION,
        "commit": commit,
        "exes": {exe.stem: {"label": exe.label, **_totals_doc(exe.totals)}
                 for exe in progress.exes},  # fmt: skip
        "combined": _totals_doc(progress.combined),
        "notes": list(NOTES),
    }


def shield_color(value: float) -> str:
    return next(color for floor, color in SHIELD_COLORS if value >= floor)


def shield_message(value: float) -> str:
    """The percent as progress.json holds it (4 decimals), trailing zeros dropped: today's
    figure is a few thousandths of a percent, which two decimals would publish as 0.00%."""
    return f"{value:.{PERCENT_DECIMALS}f}".rstrip("0").rstrip(".") + "%"


def build_shield(progress: Progress) -> dict[str, object]:
    """The shields.io endpoint document: the combined percent, labelled "decompiled" (D-26)."""
    value = progress.combined.percent
    return {"schemaVersion": SHIELD_SCHEMA_VERSION, "label": SHIELD_LABEL,
            "message": shield_message(value), "color": shield_color(value)}  # fmt: skip


def write_progress_json(progress: Progress, path: Path, commit: str | None = None) -> None:
    _write_atomic(path, render(build_progress(progress, commit)))


def write_shield(progress: Progress, path: Path) -> None:
    _write_atomic(path, render(build_shield(progress)))


# ---- command line ----


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="progress.py", description=__doc__.splitlines()[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                   help="the config tree (default: %(default)s)")  # fmt: skip
    p.add_argument("--out", type=Path, help="write progress.json and progress-shield.json here")
    p.add_argument("--commit", help="the commit the figures come from, recorded in progress.json")
    return p


def _outputs(args: argparse.Namespace) -> Iterable[Path]:
    if args.out is not None:
        yield args.out / PROGRESS_JSON


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.out is None:
        parser.error("nothing to write: give --out")
    if args.commit is not None and not _COMMIT.fullmatch(args.commit):
        parser.error(f"--commit {args.commit!r} is not a lower-case hex commit id")
    try:
        progress = derive(args.config)
        for path in _outputs(args):  # ruling F17: every output's directory is created
            path.parent.mkdir(parents=True, exist_ok=True)
        write_progress_json(progress, args.out / PROGRESS_JSON, args.commit)
        write_shield(progress, args.out / SHIELD_JSON)
    except (ProgressError, OSError) as exc:
        print(f"progress.py: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
