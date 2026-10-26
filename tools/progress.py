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

    python -I tools/progress.py [--config DIR] [--out DIR] [--report PATH]
                                [--decomphub PATH] [--commit SHA]

--out DIR writes DIR/progress.json, DIR/progress-shield.json (the combined shields.io endpoint),
DIR/progress-shield-<stem>.json (one endpoint per EXE: progress-shield-ufo2p.json and
progress-shield-tacp.json), DIR/progress.svg (the mosaic: a squarified treemap,
EXE > unit > function), and DIR/progress.html and DIR/index.html (the progress page, under both
names: per-EXE bars and function strips, the mosaic inline);
--report PATH objdiff's report.json (D-28), one unit per unit holding game/thunk rows plus one
<exe>/uncovered unit per EXE; --decomphub PATH the DecompHub progress-v1 feed (D-29), which gate
also rewrites next to config/ after it writes matched rows. Every output's directory is created.
Exit 0 on success, 2 when a CSV is malformed or an argument is wrong.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import dataclasses
import functools
import json
import os
import re
import secrets
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

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
EXE_SHIELD_JSON = "progress-shield-{stem}.json"  # one endpoint per EXE (owner ruling 1)
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


def _records(path: Path, columns: Sequence[str], text: str | None = None
             ) -> list[dict[str, str]]:  # fmt: skip
    """The data rows of a CSV as dicts; `#` comment lines skipped, the header checked. `text`
    stands in for the file's content (gate checks tables it has not written yet)."""
    if text is None:
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


def read_status(path: Path, text: str | None = None) -> list[Status]:
    """status.csv rows; a missing file has none (D-20: sparse). `text`, when given, is the
    table's content in place of the file's."""
    if text is None and not Path(path).exists():
        return []
    rows: list[Status] = []
    for number, rec in enumerate(_records(path, STATUS_COLUMNS, text), start=1):
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
    library_rows: tuple[Row, ...] = ()  # the runtime rows, one library cell each in the mosaic

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


def _derive_exe(config: Path, stem: str, label: str, status_text: str | None) -> ExeProgress:
    exe_dir = Path(config) / stem
    rows = read_functions(exe_dir / FUNCTIONS_CSV)
    units = read_units(exe_dir / UNITS_CSV)
    statuses = {s.start: s for s in read_status(exe_dir / STATUS_CSV, status_text)}
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
        library_rows=tuple(library),
    )


def derive(config_dir: Path = DEFAULT_CONFIG,
           status_texts: Mapping[str, str] | None = None) -> Progress:
    """The progress of every EXE in EXES from config_dir/<stem>/{functions,units,status}.csv.
    `status_texts` maps a stem to status.csv content used in place of the file: gate derives
    the tables it is about to write before it writes any (fix round 1)."""
    texts = status_texts or {}
    return Progress(tuple(_derive_exe(Path(config_dir), stem, label, texts.get(stem))
                          for stem, label in EXES))  # fmt: skip


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


def _shield_doc(label: str, value: float) -> dict[str, object]:
    """A shields.io endpoint document for `value` percent, coloured by SHIELD_COLORS."""
    return {"schemaVersion": SHIELD_SCHEMA_VERSION, "label": label,
            "message": shield_message(value), "color": shield_color(value)}  # fmt: skip


def build_shield(progress: Progress) -> dict[str, object]:
    """The shields.io endpoint document: the combined percent, labelled "decompiled" (D-26)."""
    return _shield_doc(SHIELD_LABEL, progress.combined.percent)


def build_exe_shield(exe: ExeProgress) -> dict[str, object]:
    """One EXE's shields.io endpoint document, labelled with the EXE and coloured by its own
    percent (owner ruling 1, 2026-10-26: the README shows one badge per EXE)."""
    return _shield_doc(exe.label, exe.totals.percent)


def write_progress_json(progress: Progress, path: Path, commit: str | None = None) -> None:
    _write_atomic(path, render(build_progress(progress, commit)))


def write_shield(progress: Progress, path: Path) -> None:
    _write_atomic(path, render(build_shield(progress)))


def write_exe_shield(progress: Progress, path: Path, stem: str) -> None:
    _write_atomic(path, render(build_exe_shield(progress.exe(stem))))


# ---- report.json in objdiff's report shape (D-28, D-49) ----


@dataclass(frozen=True)
class _Tally:
    """What objdiff's Measures sum over units. `fuzzy` is the size-weighted percent sum."""

    code: int = 0
    matched: int = 0
    fuzzy: float = 0.0
    functions: int = 0
    matched_functions: int = 0
    units: int = 0
    complete_units: int = 0
    complete_code: int = 0

    def __add__(self, other: _Tally) -> _Tally:
        return _Tally(*(getattr(self, f.name) + getattr(other, f.name)
                        for f in dataclasses.fields(self)))  # fmt: skip

    def measures(self) -> dict[str, object]:
        """Every report.proto Measures field: u64 as decimal strings (pbjson's proto3 JSON
        mapping), u32 and floats as numbers. No data is measured, so data totals are 0 and
        their percents 100.0, objdiff's figure for a zero total."""
        fuzzy = PERCENT_MAX if self.code == 0 else round(self.fuzzy / self.code, PERCENT_DECIMALS)
        return {
            "fuzzy_match_percent": fuzzy,
            "total_code": str(self.code),
            "matched_code": str(self.matched),
            "matched_code_percent": percent(self.matched, self.code),
            "total_data": "0",
            "matched_data": "0",
            "matched_data_percent": PERCENT_MAX,
            "total_functions": self.functions,
            "matched_functions": self.matched_functions,
            "matched_functions_percent": percent(self.matched_functions, self.functions),
            "complete_code": str(self.complete_code),
            "complete_code_percent": percent(self.complete_code, self.code),
            "complete_data": "0",
            "complete_data_percent": PERCENT_MAX,
            "total_units": self.units,
            "complete_units": self.complete_units,
        }


UNCOVERED_UNIT = "uncovered"
UNASSIGNED_UNIT = "unassigned"  # a functions.csv row whose unit cell is still empty
REPORT_VERSION = 2  # objdiff-core's REPORT_VERSION


def _unit_tally(functions: Sequence[Function]) -> _Tally:
    code = sum(f.size for f in functions)
    complete = all(f.status == MATCHED for f in functions)
    return _Tally(code=code, matched=sum(f.size for f in functions if f.status == MATCHED),
                  fuzzy=sum(f.size * f.best_percent for f in functions),
                  functions=len(functions),
                  matched_functions=sum(1 for f in functions if f.status == MATCHED),
                  units=1, complete_units=int(complete),
                  complete_code=code if complete else 0)  # fmt: skip


def _item(f: Function) -> dict[str, object]:
    # `address` is the function's linear address (0x10000-based, as in functions.csv), not the
    # section-relative offset objdiff writes; recomp.fyi reads only the measures. Keep it linear.
    return {"name": f.name, "size": str(f.size), "fuzzy_match_percent": f.best_percent,
            "address": str(f.start)}  # fmt: skip


def _report_units(exe: ExeProgress) -> list[tuple[dict[str, object], _Tally]]:
    """One report unit per unit holding game/thunk rows, in address order, then the EXE's
    uncovered bytes as one synthetic unit (D-50); runtime rows are in none (D-26)."""
    by_unit: dict[str, list[Function]] = {}
    for f in exe.functions:
        by_unit.setdefault(f.unit or UNASSIGNED_UNIT, []).append(f)
    out = []
    for unit, functions in by_unit.items():
        tally = _unit_tally(functions)
        out.append(({"name": f"{exe.stem}/{unit}", "measures": tally.measures(),
                     "functions": [_item(f) for f in functions],
                     "metadata": {"complete": bool(tally.complete_units),
                                  "progress_categories": [exe.stem]}}, tally))  # fmt: skip
    # A bucket of bytes no row claims yet, never "complete": it cannot be finished, only
    # attributed (a later phase), even when it is empty.
    tally = _Tally(code=sum(exe.uncovered), units=1)
    out.append(({"name": f"{exe.stem}/{UNCOVERED_UNIT}", "measures": tally.measures(),
                 "metadata": {"complete": False, "progress_categories": [exe.stem],
                              "auto_generated": True}}, tally))  # fmt: skip
    return out


def build_report(progress: Progress) -> dict[str, object]:
    """report.json: objdiff's Report with `measures`, `units`, `version` and one category per
    EXE (D-28, D-49). Its combined matched_code_percent is progress.json's combined percent:
    both are matched bytes over game + thunk + uncovered bytes."""
    units: list[dict[str, object]] = []
    categories: list[dict[str, object]] = []
    total = _Tally()
    for exe in progress.exes:
        listed = _report_units(exe)
        category = _Tally()
        for unit, tally in listed:
            units.append(unit)
            category = category + tally
        categories.append({"id": exe.stem, "name": exe.label, "measures": category.measures()})
        total = total + category
    return {"measures": total.measures(), "units": units, "version": REPORT_VERSION,
            "categories": categories}  # fmt: skip


def write_report(progress: Progress, path: Path) -> None:
    _write_atomic(path, render(build_report(progress)))


# ---- decomphub.progress.json, DecompHub progress-v1 (D-29) ----

DECOMPHUB_FORMAT = "decomphub.progress/v1"
REPOSITORY = "https://github.com/ayrtondenner/ReverseApoc"
FUNCTIONS_UNIT = "functions"


def _code_track(exe: ExeProgress) -> dict[str, object]:
    return {
        "id": f"{exe.stem}-code",
        "label": f"{exe.label} code decompiled",
        "scope": (f"Bytes of {exe.label}'s game and thunk functions rebuilt byte for byte from C, "
                  "over all game and thunk bytes plus the bytes inside unit spans that no "
                  "function row covers yet (mostly alignment filler). The Watcom runtime and "
                  "data in code are excluded."),
        "measurement": {"kind": "percent", "value": exe.totals.percent},
    }  # fmt: skip


def _functions_track(exe: ExeProgress) -> dict[str, object]:
    totals = exe.totals
    measurement = None if totals.total_functions == 0 else {
        "kind": "ratio", "completed": totals.matched_functions,
        "total": totals.total_functions, "unit": FUNCTIONS_UNIT}  # fmt: skip
    return {
        "id": f"{exe.stem}-functions",
        "label": f"{exe.label} functions matched",
        "scope": (f"Game and thunk functions of {exe.label} whose rebuilt C is byte-identical "
                  "to the original (matched rows of status.csv), over all game and thunk "
                  "functions in functions.csv."),
        "measurement": measurement,
    }  # fmt: skip


def build_decomphub(progress: Progress) -> dict[str, object]:
    """The progress-v1 feed: a code percent and a function ratio per EXE. No `revision` (a file
    cannot hold its own commit hash) and no timestamp, so it is byte-stable (D-29)."""
    tracks = [_code_track(exe) for exe in progress.exes]
    tracks += [_functions_track(exe) for exe in progress.exes]
    return {"format": DECOMPHUB_FORMAT, "repository": REPOSITORY, "tracks": tracks}


def write_decomphub(progress: Progress, path: Path) -> None:
    _write_atomic(path, render(build_decomphub(progress)))


# ---- progress.svg, the mosaic (D-26, D-50) ----

Rect = tuple[float, float, float, float]  # x, y, width, height


def _worst(total: float, smallest: float, largest: float, side: float) -> float:
    """The worst aspect ratio of a row of areas laid along `side` (Bruls et al., eq. 1)."""
    side2 = side * side
    return max(side2 * largest / (total * total), total * total / (side2 * smallest))


def _row_end(areas: Sequence[float], first: int, side: float) -> int:
    """The end of the row starting at `first`: areas join it while the worst ratio improves."""
    total = smallest = largest = areas[first]
    end = first + 1
    while end < len(areas):
        area = areas[end]
        grown = _worst(total + area, min(smallest, area), max(largest, area), side)
        if grown > _worst(total, smallest, largest, side):
            break
        total, smallest, largest = total + area, min(smallest, area), max(largest, area)
        end += 1
    return end


def _lay_row(row: Sequence[float], rect: Rect, out: list[Rect]) -> Rect:
    """Lay `row` along the shorter side of `rect`, append its rectangles, return the rest."""
    x, y, w, h = rect
    total = sum(row)
    if w >= h:  # a column at the left, as tall as the rectangle
        width = total / h
        for area in row:
            out.append((x, y, width, area / width))
            y += area / width
        return x + width, rect[1], max(w - width, 0.0), h
    height = total / w  # a strip at the top, as wide as the rectangle
    for area in row:
        out.append((x, y, area / height, height))
        x += area / height
    return rect[0], y + height, w, max(h - height, 0.0)


def squarify(sizes: Sequence[float], rect: Rect) -> list[Rect]:
    """Tile `rect` with one rectangle per size, its area proportional to the size, in input
    order: the squarified treemap of Bruls, Huizing and van Wijk (2000). Rows grow while their
    worst aspect ratio improves and are laid along the shorter side. Pass the sizes largest
    first, as the algorithm assumes; every size must be positive."""
    if any(value <= 0 for value in sizes):
        raise ValueError("squarify: every size must be positive")
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return [(x, y, 0.0, 0.0) for _ in sizes]
    total = sum(sizes)
    areas = [value * (w * h) / total for value in sizes]
    out: list[Rect] = []
    first = 0
    while first < len(areas):
        x, y, w, h = rect
        if w <= 0 or h <= 0:  # float drift left no room: the rest are empty
            out.extend((x, y, 0.0, 0.0) for _ in areas[first:])
            break
        end = _row_end(areas, first, min(w, h))
        rect = _lay_row(areas[first:end], rect, out)
        first = end
    return out


LIBRARY, UNCOVERED = "library", "uncovered"
CELL_STATUSES = (MATCHED, PARTIAL, UNMATCHED, LIBRARY, UNCOVERED)
# Fixed colours (D-50), checked with the dataviz palette validator on the light surface: the
# three hues pass CVD separation; unmatched and uncovered are neutral greys on purpose.
TREEMAP_COLORS = {MATCHED: "#008300", PARTIAL: "#eda100", UNMATCHED: "#898781",
                  LIBRARY: "#2a78d6", UNCOVERED: "#d8d6cf"}  # fmt: skip
LEGEND_LABELS = {MATCHED: "matched", PARTIAL: "partial", UNMATCHED: "unmatched",
                 LIBRARY: "library (not decompiled)",
                 UNCOVERED: "uncovered: mostly alignment filler"}  # fmt: skip
PROGRESS_SVG = "progress.svg"
SVG_WIDTH, SVG_HEIGHT = 1200, 800
LEGEND_HEIGHT = 30  # the title and legend row above the map
EXE_HEADER = 20  # each EXE's caption strip
SURFACE, INK, SECONDARY_INK = "#fcfcfb", "#0b0b0b", "#52514e"
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
LEGEND_MARGIN = 8  # the legend ends this far from the right edge
FONT_SIZE = 12  # the SVG's base font size: the legend and the captions
LEGEND_CHAR = 6.6  # px per label character at FONT_SIZE, for spacing the legend items
LEGEND_GAP = 26  # dot, padding and gap between legend items
# Unit labels (owner ruling 2, 2026-10-26): a unit gets one only when it has room for it. A name
# too long for its unit is cut to the characters that fit and ends with one ellipsis (owner ruling
# of 2026-10-26), unless fewer than LABEL_MIN_CHARS of the name would be left.
LABEL_FONT_SIZE = 11
LABEL_CHAR = LEGEND_CHAR * LABEL_FONT_SIZE / FONT_SIZE  # px per label character
LABEL_PAD = 4  # inset from the unit's left edge, and the room kept on its right
LABEL_BASELINE = 14  # the baseline below the unit's top edge, as the EXE caption's
LABEL_MIN_WIDTH = 40  # the fixed minimum unit size for a label
LABEL_MIN_HEIGHT = LABEL_BASELINE + LABEL_PAD
LABEL_MIN_CHARS = 6  # a cut label keeps at least this many characters of the name
LABEL_ELLIPSIS = "…"  # one character, counted as one in the width estimate
# px of SURFACE stroke under the ink, so a label reads on every cell colour (INK alone on the
# grey and blue cells is not enough), without picking a colour per cell.
LABEL_HALO = 3


@dataclass(frozen=True)
class _Cell:
    """One mosaic cell: a function, a library function or a unit's uncovered bytes."""

    size: int
    start: int
    status: str  # one of CELL_STATUSES
    title: str | None = None  # a tooltip, matched cells only
    name: str | None = None  # the function's name; None for uncovered bytes (not in `key`)

    @property
    def key(self) -> tuple[int, int, int]:
        """Largest first, then by address, then by status: a stable, total order."""
        return -self.size, self.start, CELL_STATUSES.index(self.status)


def _xml(text: str) -> str:
    """Text or attribute content, escaped (names come from the CSVs)."""
    return escape(text, {'"': "&quot;"})


def _num(value: float) -> str:
    """A coordinate rounded to 0.1, without a trailing ".0"."""
    text = f"{round(value, 1):.1f}"
    return text[:-2] if text.endswith(".0") else text


def _box(rect: Rect) -> str:
    """x/y/width/height attributes: the edges rounded to 0.1, so neighbours stay flush."""
    x, y, w, h = rect
    left, top, right, bottom = (round(v, 1) for v in (x, y, x + w, y + h))
    return (f'x="{_num(left)}" y="{_num(top)}" width="{_num(right - left)}" '
            f'height="{_num(bottom - top)}"')  # fmt: skip


def _unit_cells(exe: ExeProgress) -> dict[str, list[_Cell]]:
    """The cells of each unit: its game/thunk functions, runtime rows and uncovered bytes.
    Data-in-code is not drawn (D-26)."""
    groups: dict[str, list[_Cell]] = {}
    for f in exe.functions:
        title = f"{f.name}: {f.size:,} bytes, matched" if f.status == MATCHED else None
        groups.setdefault(f.unit or UNASSIGNED_UNIT, []).append(
            _Cell(f.size, f.start, f.status, title, f.name))
    for row in exe.library_rows:
        groups.setdefault(row.unit or UNASSIGNED_UNIT, []).append(
            _Cell(row.size, row.start, LIBRARY, name=row.name))
    for unit, uncovered in zip(exe.units, exe.uncovered, strict=True):
        if uncovered:
            groups.setdefault(unit.unit, []).append(_Cell(uncovered, unit.start, UNCOVERED))
    return groups


def _unit_title(exe: ExeProgress, unit: str, cells: Sequence[_Cell]) -> str:
    def total(*statuses: str) -> int:
        return sum(c.size for c in cells if c.status in statuses)

    code = [c for c in cells if c.status in (MATCHED, PARTIAL, UNMATCHED)]
    parts = [f"{exe.label} {unit}: {total(MATCHED):,} of {total(MATCHED, PARTIAL, UNMATCHED):,} "
             f"code bytes matched, {len(code)} functions"]  # fmt: skip
    if total(LIBRARY):
        parts.append(f"{total(LIBRARY):,} library bytes")
    if total(UNCOVERED):
        parts.append(f"{total(UNCOVERED):,} uncovered bytes")
    return "; ".join(parts)


def _cell_svg(cell: _Cell, rect: Rect) -> str:
    fill = TREEMAP_COLORS[cell.status]
    if cell.title is None:
        return f'<rect {_box(rect)} fill="{fill}"/>'
    return f'<rect {_box(rect)} fill="{fill}"><title>{_xml(cell.title)}</title></rect>'


def _unit_label(unit: str, ordered: Sequence[_Cell]) -> str:
    """The label a unit carries (owner ruling 2): a library unit (runtime rows, no game or thunk
    function) its largest runtime function, the first LIBRARY cell of the key-sorted `ordered`,
    so a size tie goes to the lowest start; any other unit its own name."""
    if any(c.status in (MATCHED, PARTIAL, UNMATCHED) for c in ordered):
        return unit
    library = next((c for c in ordered if c.status == LIBRARY), None)
    if library is None or library.name is None:
        return unit
    return library.name


def _label_room(width: float) -> int:
    """The most label characters a unit `width` wide holds: n with 2 * LABEL_PAD + LABEL_CHAR * n
    <= width. The quotient is only a first guess; the inequality decides, so a float rounding of
    the division cannot move the boundary."""
    room = max(int((width - 2 * LABEL_PAD) / LABEL_CHAR), 0)
    if room > 0 and 2 * LABEL_PAD + LABEL_CHAR * room > width:
        room -= 1
    if 2 * LABEL_PAD + LABEL_CHAR * (room + 1) <= width:
        room += 1
    return room


def _fit_label(label: str, width: float) -> str | None:
    """The raw label text a unit `width` wide shows: the whole name when it fits, else its first
    characters and LABEL_ELLIPSIS in the same room, or None when fewer than LABEL_MIN_CHARS of
    the name would be left. The caller escapes the result, so no escape sequence is cut."""
    room = _label_room(width)
    if len(label) <= room:
        return label
    if room - 1 < LABEL_MIN_CHARS:
        return None
    return label[:room - 1] + LABEL_ELLIPSIS


def _label_svg(label: str, rect: Rect) -> str | None:
    """A unit's label at its top left, cut with an ellipsis when the name is too long, or None
    when the unit is smaller than the fixed minimum or too narrow even for a cut label (decided
    on the unrounded rect). The label ignores the pointer, so the tooltips under it stay
    reachable."""
    x, y, w, h = rect
    if w < LABEL_MIN_WIDTH or h < LABEL_MIN_HEIGHT:
        return None
    text = _fit_label(label, w)
    if text is None:
        return None
    return (f'<text x="{_num(x + LABEL_PAD)}" y="{_num(y + LABEL_BASELINE)}" '
            f'font-size="{LABEL_FONT_SIZE}" fill="{INK}" stroke="{SURFACE}" '
            f'stroke-width="{LABEL_HALO}" stroke-linejoin="round" paint-order="stroke" '
            f'pointer-events="none">{_xml(text)}</text>')  # fmt: skip


def _unit_svg(exe: ExeProgress, unit: str, cells: Sequence[_Cell], rect: Rect) -> list[str]:
    ordered = sorted(cells, key=lambda c: c.key)
    lines = [f'<g data-unit="{_xml(unit)}"><title>{_xml(_unit_title(exe, unit, ordered))}</title>']
    rects = squarify([c.size for c in ordered], rect)
    lines += [_cell_svg(cell, r) for cell, r in zip(ordered, rects, strict=True)]
    label = _label_svg(_unit_label(unit, ordered), rect)
    if label is not None:
        lines.append(label)
    lines.append(f'<rect {_box(rect)} fill="none" stroke="{SURFACE}" stroke-width="1"/></g>')
    return lines


def _drawn_bytes(exe: ExeProgress) -> int:
    return sum(c.size for cells in _unit_cells(exe).values() for c in cells)


def _exe_svg(exe: ExeProgress, rect: Rect) -> list[str]:
    """One EXE: a caption strip, then its units squarified, largest first."""
    x, y, w, h = rect
    totals = exe.totals
    caption = (f"{exe.label}: {shield_message(totals.percent)} decompiled, "
               f"{totals.matched_functions:,} of {totals.total_functions:,} functions matched")
    lines = [f'<g data-exe="{_xml(exe.stem)}">',
             f'<text x="{_num(x + 4)}" y="{_num(y + 14)}" fill="{INK}">{_xml(caption)}</text>']
    groups = _unit_cells(exe)
    order = sorted(groups, key=lambda u: (-sum(c.size for c in groups[u]),
                                          min(c.start for c in groups[u]), u))  # fmt: skip
    area = (x, y + EXE_HEADER, w, max(h - EXE_HEADER, 0.0))
    sizes = [sum(c.size for c in groups[u]) for u in order]
    for unit, unit_rect in zip(order, squarify(sizes, area), strict=True):
        lines += _unit_svg(exe, unit, groups[unit], unit_rect)
    # A wider gap than the units' between the two EXEs' maps.
    lines.append(f'<rect {_box(area)} fill="none" stroke="{SURFACE}" stroke-width="4"/>')
    lines.append("</g>")
    return lines


def _legend_svg(progress: Progress) -> list[str]:
    combined = progress.combined
    heading = (f"X-COM Apocalypse (DOS): {shield_message(combined.percent)} decompiled, "
               f"{combined.matched_functions:,} of {combined.total_functions:,} functions")
    lines = [f'<text x="8" y="20" font-weight="bold" fill="{INK}">{_xml(heading)}</text>']
    widths = [LEGEND_GAP + LEGEND_CHAR * len(LEGEND_LABELS[s]) for s in CELL_STATUSES]
    x = SVG_WIDTH - LEGEND_MARGIN - sum(widths)  # right-aligned, clear of the heading
    for status in CELL_STATUSES:
        label = LEGEND_LABELS[status]
        lines.append(f'<circle cx="{_num(x + 5)}" cy="15" r="5" '
                     f'fill="{TREEMAP_COLORS[status]}"/>')  # fmt: skip
        lines.append(f'<text x="{_num(x + 14)}" y="19" fill="{SECONDARY_INK}">{_xml(label)}</text>')
        x += LEGEND_GAP + LEGEND_CHAR * len(label)
    return lines


def render_svg(progress: Progress) -> str:
    """progress.svg: a squarified treemap nested EXE, unit, then one cell per game, thunk and
    runtime function sized by bytes, plus one cell per unit for its uncovered bytes, in the
    fixed TREEMAP_COLORS (D-26, D-50). EXEs keep EXES order; units and cells go largest first,
    then by address, so the same CSVs give the same bytes. Tooltips (<title>) sit on unit
    groups and matched cells only, coordinates are rounded to 0.1, and no game byte is in it.
    Units large enough carry a label (a game unit its unit name, a library unit its largest
    runtime function), cut with an ellipsis when the name is too long, small units none; labels
    ignore the pointer, so the tooltips stay reachable."""
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" '
             f'height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img" '
             f'aria-label="Decompilation progress mosaic" font-family="{FONT}" '
             f'font-size="{FONT_SIZE}">',
             f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="{SURFACE}"/>']
    lines += _legend_svg(progress)
    exes = [exe for exe in progress.exes if _drawn_bytes(exe) > 0]
    area = (0.0, float(LEGEND_HEIGHT), float(SVG_WIDTH), float(SVG_HEIGHT - LEGEND_HEIGHT))
    for exe, rect in zip(exes, squarify([_drawn_bytes(e) for e in exes], area), strict=True):
        lines += _exe_svg(exe, rect)
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def write_svg(progress: Progress, path: Path) -> None:
    _write_atomic(path, render_svg(progress).encode("utf-8"))


# ---- progress.html, the progress page ----

PROGRESS_HTML = "progress.html"
# The same page at the Pages root, which .recomp.json's Progress link and the docs/listings.md
# drafts point at (orchestrator ruling of 2026-10-26). The page's links are relative or absolute,
# so they resolve the same from both names.
INDEX_HTML = "index.html"
PAGE_TITLE = "ReverseApoc progress"
PAGE_HEADING = "X-COM: Apocalypse (DOS) decompilation progress"
COMMIT_URL = REPOSITORY + "/commit/"
COMMIT_SHORT = 7  # hex digits of the commit shown on the page
# report.json is an artifact of the Pages run, not a Pages file: the page links the workflow.
PAGES_WORKFLOW_URL = REPOSITORY + "/actions/workflows/pages.yml"
README_URL = REPOSITORY + "#progress"
BAR_HEIGHT = 8  # px, the percent bar
# The function strip: one tick per game and thunk function, in address order. A CSS flex-wrap
# row, so it re-wraps at any width instead of scaling: 112 ticks per row at a 375 px viewport.
TICK_CLASSES = {MATCHED: "m", PARTIAL: "p", UNMATCHED: "u"}
TICK_WIDTH = 2  # px; with the 1 px gap a tick stays a distinct mark at 1x
TICK_GAP = 1  # px between ticks
# Matched and partial ticks stand taller, so status does not rest on colour alone (matched and
# unmatched grey are only 1.38:1 apart in luminance); unmatched ticks sit on the same bottom.
TICK_HEIGHT = 14  # px, matched and partial
TICK_SHORT = 8  # px, unmatched, bottom-aligned through a top margin
TICK_ROW_GAP = 3  # px between wrapped rows
STRIP_KEY = ('<p class="key">Each tick is one game or thunk function, in address order: '
             f'<i class="{TICK_CLASSES[MATCHED]}" aria-hidden="true"></i> matched, '
             f'<i class="{TICK_CLASSES[PARTIAL]}" aria-hidden="true"></i> partial, '
             f'<i class="{TICK_CLASSES[UNMATCHED]}" aria-hidden="true"></i> unmatched. Matched '
             "and partial ticks stand taller. The bar is the share of code bytes matched.</p>")
MEASURED = (
    "A function is matched when its C, built with the original Watcom compiler, is "
    "byte-identical to the original, proven by objdiff, the relocation check and the whole-EXE "
    "SHA-1. A partial function scored above 0% in objdiff but is not byte-identical yet; it "
    "counts for nothing in the percentage or the function ratio. Every other game or thunk "
    "function is unmatched: the rebuilt EXE still carries its original bytes.",
    "The percentage is matched bytes of game and thunk functions over all game and thunk bytes "
    "plus the uncovered bytes, the bytes inside a unit that no function row covers (mostly "
    "alignment filler). The function ratio is matched game and thunk functions over all game "
    "and thunk functions. The Watcom runtime library (blue in the mosaic) is not decompiled and "
    "stays outside both; data-in-code is excluded.",
    "Every figure comes from committed tables: the status.csv files that reverseapoc gate "
    "writes, plus each EXE's functions.csv and units.csv. This page is regenerated from them on "
    "every push to main. The raw numbers are in <a href=\"progress.json\">progress.json</a>, the "
    f'objdiff-shaped <a href="{PAGES_WORKFLOW_URL}">report.json</a> is attached to each run of '
    f'the Pages workflow, and the <a href="{README_URL}">README</a> has the full definitions.',
)


def _page_css() -> str:
    """The inline style sheet, one rule per line, from the SVG's own tokens."""
    return "\n".join([
        f":root{{--surface:{SURFACE};--ink:{INK};--secondary:{SECONDARY_INK}}}",
        f"body{{margin:0;background:var(--surface);color:var(--ink);font-family:{FONT};"
        f"font-size:1rem;line-height:1.5}}",
        "main{max-width:75rem;padding:2rem clamp(1rem,5vw,4rem) 3rem}",
        "h1{margin:0 0 .25rem;font-size:1.75rem;line-height:1.2;font-weight:700}",
        "h2{margin:0;font-size:1.125rem;line-height:1.3;font-weight:600}",
        "main>h2{margin-top:2.5rem}",
        "p{max-width:70ch;margin:.5rem 0}",
        ".meta,.key,.caption{color:var(--secondary);font-size:.875rem}",
        "a{color:inherit;text-decoration-thickness:1px;text-underline-offset:.15em}",
        "a:focus-visible{outline:2px solid var(--ink);outline-offset:2px}",
        ".exe{display:grid;grid-template-columns:8rem minmax(0,1fr);column-gap:1.5rem;"
        "align-items:start;margin:2rem 0}",
        ".line{display:flex;flex-wrap:wrap;align-items:center;gap:.25rem 1rem}",
        f".bar{{flex:1 1 12rem;height:{BAR_HEIGHT}px;background:{TREEMAP_COLORS[UNMATCHED]}}}",
        f".bar span{{display:block;height:100%;background:{TREEMAP_COLORS[MATCHED]}}}",
        ".figures{margin:0;font-size:.875rem;font-variant-numeric:tabular-nums}",
        ".strip{display:flex;flex-wrap:wrap;align-items:flex-start;"
        f"gap:{TICK_ROW_GAP}px {TICK_GAP}px;margin-top:.75rem}}",
        f".strip i,.key i{{flex:none;width:{TICK_WIDTH}px;height:{TICK_HEIGHT}px}}",
        ".key i{display:inline-block}",
        # Two-class selectors, so the short tick outranks the base tick rule in any order.
        f".strip .u,.key .u{{height:{TICK_SHORT}px;margin-top:{TICK_HEIGHT - TICK_SHORT}px}}",
        *(f"i.{TICK_CLASSES[status]}{{background:{TREEMAP_COLORS[status]}}}"
          for status in (MATCHED, PARTIAL, UNMATCHED)),
        ".mosaic{margin-top:.75rem}",
        ".mosaic svg{display:block;width:100%;height:auto}",
    ])


def _figures(exe: ExeProgress) -> str:
    t = exe.totals
    return (f"{shield_message(t.percent)} of code bytes, {t.matched_functions:,} of "
            f"{t.total_functions:,} functions matched, {t.partial_functions:,} partial")


def _tick_html(f: Function) -> str:
    """One strip tick; matched and partial ticks carry a tooltip."""
    cls = TICK_CLASSES[f.status]
    if f.status == UNMATCHED:
        return f'<i class="{cls}"></i>'
    return f'<i class="{cls}" title="{_xml(f"{f.name}: {f.size:,} bytes, {f.status}")}"></i>'


def _strip_html(exe: ExeProgress) -> str:
    """The function strip: one tick per game and thunk function in address order, as one
    role=img element whose aria-label holds the counts."""
    t = exe.totals
    unmatched = t.total_functions - t.matched_functions - t.partial_functions
    aria = (f"{exe.label}, one tick per game and thunk function in address order: "
            f"{t.matched_functions:,} matched, {t.partial_functions:,} partial, "
            f"{unmatched:,} unmatched")  # fmt: skip
    ticks = "".join(_tick_html(f) for f in sorted(exe.functions, key=lambda f: f.start))
    return f'<div class="strip" role="img" aria-label="{_xml(aria)}">{ticks}</div>'


def _exe_html(exe: ExeProgress) -> list[str]:
    """One EXE's section: its heading, then the percent bar, the figures in text and the
    function strip."""
    stem, width = _xml(exe.stem), shield_message(exe.totals.percent)
    return [f'<section class="exe" aria-labelledby="exe-{stem}">',
            f'<h2 id="exe-{stem}">{_xml(exe.label)}</h2>',
            "<div>",
            '<div class="line">',
            f'<div class="bar" aria-hidden="true"><span style="width:{width}"></span></div>',
            f'<p class="figures">{_xml(_figures(exe))}</p>',
            "</div>",
            _strip_html(exe),
            "</div>",
            "</section>"]  # fmt: skip


def render_html(progress: Progress, commit: str | None = None) -> str:
    """progress.html (owner rulings 3 and 4, 2026-10-26): per EXE a heading, a percent bar, the
    figures in text and the function strip (one tick per game and thunk function in address
    order; matched and partial ticks stand taller and carry a tooltip; the strip wraps with the
    width), then the strip's key, the labelled mosaic (render_svg's output, verbatim) and how
    the figures are measured. Inline CSS only, no script and no external request: every link is
    relative or to the repository. The same CSVs and commit give the same bytes; without a
    commit only the "Updated from commit" line is missing."""
    lines = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             f"<title>{_xml(PAGE_TITLE)}</title>", "<style>", _page_css(), "</style>",
             "</head>", "<body>", "<main>", f"<h1>{_xml(PAGE_HEADING)}</h1>"]  # fmt: skip
    if commit is not None:
        lines.append(f'<p class="meta">Updated from commit <a href="{_xml(COMMIT_URL + commit)}">'
                     f"{_xml(commit[:COMMIT_SHORT])}</a></p>")  # fmt: skip
    for exe in progress.exes:
        lines += _exe_html(exe)
    lines += [STRIP_KEY,
              "<h2>The mosaic</h2>",
              '<p class="caption">One cell per function, grouped by EXE and unit and sized by '
              "bytes; large units carry their name.</p>",
              '<div class="mosaic">', render_svg(progress).removesuffix("\n"), "</div>",
              "<h2>How it is measured</h2>", *(f"<p>{text}</p>" for text in MEASURED),
              "</main>", "</body>", "</html>"]  # fmt: skip
    return "\n".join(lines) + "\n"


def write_html(progress: Progress, path: Path, commit: str | None = None) -> None:
    _write_atomic(path, render_html(progress, commit).encode("utf-8"))


# ---- command line ----


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="progress.py", description=__doc__.splitlines()[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                   help="the config tree (default: %(default)s)")  # fmt: skip
    p.add_argument("--out", type=Path,
                   help="write progress.json, progress-shield.json, one "
                        "progress-shield-<stem>.json per EXE, progress.svg and the progress "
                        "page as progress.html and index.html here")
    p.add_argument("--report", type=Path, help="write objdiff's report.json here (D-28)")
    p.add_argument("--decomphub", type=Path,
                   help="write the DecompHub progress-v1 feed here (D-29)")  # fmt: skip
    p.add_argument("--commit", help="the commit the figures come from, recorded in progress.json")
    return p


def _writes(args: argparse.Namespace) -> Iterable[tuple[Path, Callable[[Progress, Path], None]]]:
    """(path, writer) for every output the arguments ask for."""
    if args.out is not None:
        yield args.out / PROGRESS_JSON, lambda p, path: write_progress_json(p, path, args.commit)
        yield args.out / SHIELD_JSON, write_shield
        for stem, _label in EXES:  # EXES, not the derived progress: this runs before derive
            yield (args.out / EXE_SHIELD_JSON.format(stem=stem),
                   functools.partial(write_exe_shield, stem=stem))
        yield args.out / PROGRESS_SVG, write_svg
        # One (path, writer) per file: render_html is a pure function of (progress, commit),
        # so the second render gives the same bytes.
        page = functools.partial(write_html, commit=args.commit)
        yield args.out / PROGRESS_HTML, page
        yield args.out / INDEX_HTML, page
    if args.report is not None:
        yield args.report, write_report
    if args.decomphub is not None:
        yield args.decomphub, write_decomphub


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    writes = list(_writes(args))
    if not writes:
        parser.error("nothing to write: give --out, --report or --decomphub")
    if args.commit is not None and not _COMMIT.fullmatch(args.commit):
        parser.error(f"--commit {args.commit!r} is not a lower-case hex commit id")
    try:
        progress = derive(args.config)
        for path, write in writes:
            path.parent.mkdir(parents=True, exist_ok=True)  # ruling F17
            write(progress, path)
    except (ProgressError, OSError) as exc:
        print(f"progress.py: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
