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

When config/mechanics.toml exists, `derive_mechanics` adds the per-item coverage view (DEC-05,
D-22): each OpenApoc checklist item's must-match and full-closure figures from
config/mechanics-members.csv, joined with the same status.csv rows; progress.json's "mechanics"
is null without it. When [asm_list] in it signs config/asm-functions.csv off (D-23),
`exclude_assembler` moves the listed rows out of the percentage into an assembler group counted
like the library, for every output but the DecompHub feed: gate writes that feed from `derive`
alone, so committing the list never stales it.

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
EXE > unit > function), and DIR/index.html (the progress page, served at the Pages root:
per-EXE bars and function strips, the mosaic inline and, when --config sits in a git checkout,
the progress-over-days chart re-derived from its history; a shallow clone gets a note instead);
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
import datetime
import functools
import hashlib
import json
import math
import os
import re
import secrets
import subprocess
import sys
import tomllib
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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
    "assembler: game functions on the owner-signed config/asm-functions.csv, hand-written "
    "assembly that cannot match from C, kept outside the percentage like the library here, in "
    "the shields and in report.json; decomphub.progress.json still counts them as code (D-23).",
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


def read_functions(path: Path, text: str | None = None) -> list[Row]:
    """functions.csv rows, sorted and non-overlapping, each kind one of KINDS. `text`, when
    given, is the table's content in place of the file's (the timeline reads past commits)."""
    rows: list[Row] = []
    for number, rec in enumerate(_records(path, FUNCTIONS_COLUMNS, text), start=1):
        row = Row(_address(path, number, "start", rec["start"]),
                  _address(path, number, "end", rec["end"]), rec["name"], rec["kind"],
                  rec["unit"])  # fmt: skip
        if row.kind not in KINDS:
            raise ProgressError(f"{path}: data row {number}: kind {row.kind!r} is not one of "
                                f"{', '.join(KINDS)}")  # fmt: skip
        _check_span(path, number, row.start, row.end, rows[-1].end if rows else 0)
        rows.append(row)
    return rows


def read_units(path: Path, text: str | None = None) -> list[Unit]:
    """units.csv rows, sorted and non-overlapping; `text` as read_functions'."""
    units: list[Unit] = []
    for number, rec in enumerate(_records(path, UNITS_COLUMNS, text), start=1):
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
    assembler_bytes: int = 0  # signed asm rows (D-23), outside the percentage like the library
    assembler_functions: int = 0
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
    # Game/thunk rows on the signed asm list (D-23), moved out of `functions` by
    # exclude_assembler: drawn like library rows and counted like the library.
    assembler_rows: tuple[Row, ...] = ()

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
            assembler_bytes=sum(row.size for row in self.assembler_rows),
            assembler_functions=len(self.assembler_rows),
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
    return _exe_progress(exe_dir, stem, label, read_functions(exe_dir / FUNCTIONS_CSV),
                         read_units(exe_dir / UNITS_CSV),
                         read_status(exe_dir / STATUS_CSV, status_text))  # fmt: skip


def _exe_progress(exe_dir: Path, stem: str, label: str, rows: Sequence[Row],
                  units: Sequence[Unit], status_rows: Iterable[Status]) -> ExeProgress:  # fmt: skip
    """One EXE from its parsed tables; `exe_dir` names them in errors (a directory, or a past
    commit's `<sha>:config/<stem>` for the timeline)."""
    statuses = {s.start: s for s in status_rows}
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


# ---- the mechanics coverage view (DEC-05; D-05, D-22, D-23) ----
#
# config/mechanics.toml (hand-edited) and config/mechanics-members.csv (written by `reverseapoc
# mechanics write`) are reverseapoc.mechanics' formats (plan 07-10); progress.py reads them with
# its own stdlib readers, since reverseapoc is not importable under -I. tests/test_progress.py
# pins these constants to mechanics.py's.

MECHANICS_TOML, MEMBERS_CSV = "mechanics.toml", "mechanics-members.csv"
MECHANICS_SCHEMA = 1
MECHANICS_TABLES = ("schema", "asm_list", "hub_rule", "tier", "item", "entry", "edge")
MEMBERS_COLUMNS = ("exe", "address", "items", "tiers", "member_items", "via", "role", "hub")
ROLES = ("member", "hub", "closure", "asm")
ROLE_MEMBER, ROLE_HUB, ROLE_CLOSURE, ROLE_ASM = ROLES
_YES, _NO = "yes", "no"  # the members hub cell (plan 07-43)
VIAS = ("entry", "direct", "pointer", "table", "midrow", "hand")
SCOPES = ("in", "out", "duplicate")
SCOPE_IN, SCOPE_OUT, SCOPE_DUPLICATE = SCOPES
# config/asm-functions.csv (D-23): the rows the owner signed off as hand-written assembly.
ASM_CSV = "asm-functions.csv"
ASM_COLUMNS = ("exe", "address", "evidence", "verdict", "reason")
ASM_VERDICTS = ("asm", "c", "unclear")
VERDICT_ASM = "asm"
_ITEM_ID = re.compile(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?")
_TIER_IDS = re.compile(r"[1-9][0-9]*(;[1-9][0-9]*)*")
_LIST = ";"
# A tier's state on the page: matched only when status.csv says every must-match function is.
TIER_MATCHED, TIER_LOCATED, TIER_UNLOCATED = "matched", "located", "not located yet"


@dataclass(frozen=True)
class Coverage:
    """One figure set over game/thunk functions (D-22): counts and bytes by status."""

    functions: int = 0
    matched: int = 0
    partial: int = 0
    total_bytes: int = 0
    matched_bytes: int = 0
    partial_bytes: int = 0

    @property
    def unmatched(self) -> int:
        return self.functions - self.matched - self.partial

    @property
    def percent(self) -> float:
        """Matched bytes over the set's bytes; an empty set is 0.0, not done."""
        if self.total_bytes == 0:
            return 0.0
        return percent(self.matched_bytes, self.total_bytes)


def _coverage(functions: Iterable[Function]) -> Coverage:
    found = list(functions)

    def count(status: str) -> int:
        return sum(1 for f in found if f.status == status)

    def size(status: str) -> int:
        return sum(f.size for f in found if f.status == status)

    return Coverage(len(found), count(MATCHED), count(PARTIAL), sum(f.size for f in found),
                    size(MATCHED), size(PARTIAL))  # fmt: skip


@dataclass(frozen=True)
class TierCoverage:
    """A [[tier]]: its sign-off and the figures over the union of its `in` items' rows, so a
    function two of its items share counts once."""

    id: int
    title: str
    signed_off_by: str
    signed_off_date: str  # ISO date, "" when not signed off
    must_match: Coverage
    full_closure: Coverage

    @property
    def state(self) -> str:
        """Matched only when status.csv says every must-match function is (RPT-01)."""
        must = self.must_match
        if must.functions and must.matched == must.functions:
            return TIER_MATCHED
        return TIER_LOCATED if self.full_closure.functions else TIER_UNLOCATED

    @property
    def sign_off(self) -> str:
        if not self.signed_off_by:
            return "not signed off"
        return f"signed off by {self.signed_off_by} on {self.signed_off_date}"


@dataclass(frozen=True)
class ItemCoverage:
    """An `in` checklist item: the must-match set (role member rows naming it in member_items)
    and the full closure (every row naming it in items, asm rows aside), D-22."""

    id: str
    issue: int
    number: int  # 0 for the issue itself ("997"), else the n of "<issue>-<n>"
    title: str
    tier: int
    must_match: Coverage
    full_closure: Coverage

    @property
    def key(self) -> tuple[int, int, int]:
        return self.tier, self.issue, self.number


@dataclass(frozen=True)
class Duplicate:
    """A `duplicate` item: listed once, by the item it duplicates, never with figures."""

    id: str
    issue: int
    number: int
    title: str
    duplicate_of: str


@dataclass(frozen=True)
class Mechanics:
    """The coverage view: tiers by id, `in` items by (tier, issue, number), duplicates by
    (issue, number), and the (stem, start) of every row on the signed asm list (D-23)."""

    tiers: tuple[TierCoverage, ...] = ()
    items: tuple[ItemCoverage, ...] = ()
    duplicates: tuple[Duplicate, ...] = ()
    assembler: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class _ItemSpec:
    id: str
    issue: int
    number: int
    title: str
    tier: int
    scope: str
    duplicate_of: str


@dataclass(frozen=True)
class _Member:
    exe: str
    start: int
    items: tuple[str, ...]
    member_items: tuple[str, ...]
    role: str


def _toml_error(path: Path, where: str, problem: str) -> ProgressError:
    return ProgressError(f"{path}: {where}: {problem}")


def _read_toml(path: Path) -> dict:
    """mechanics.toml's top level, each of 07-10's tables checked for its shape only; an
    unknown top-level key or another schema is refused (ruling F2)."""
    try:
        data = tomllib.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ProgressError(f"{path}: cannot read ({exc})") from None
    unknown = sorted(set(data) - set(MECHANICS_TABLES))
    if unknown:
        raise _toml_error(path, "top level", f"unknown key {unknown[0]!r}")
    schema = data.get("schema")
    if isinstance(schema, bool) or schema != MECHANICS_SCHEMA:
        raise _toml_error(path, "top level", f"schema {schema!r} is not {MECHANICS_SCHEMA}")
    for key in ("asm_list", "hub_rule"):
        if not isinstance(data.get(key, {}), dict):
            raise _toml_error(path, "top level", f"{key} is not a table")
    for key in ("tier", "item", "entry", "edge"):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            raise _toml_error(path, "top level", f"{key} is not an array of tables")
    return data


def _value(path: Path, where: str, body: Mapping, key: str, kind: type, *,
           required: bool = True) -> object:  # fmt: skip
    """body[key] when it is a `kind` (bool is no int), None when absent and not required."""
    if key not in body:
        if required:
            raise _toml_error(path, where, f"key {key!r} is missing")
        return None
    value = body[key]
    wrong_bool = isinstance(value, bool) and kind is not bool
    if wrong_bool or not isinstance(value, kind) or isinstance(value, datetime.datetime):
        raise _toml_error(path, where, f"key {key!r}: {value!r} is not a {kind.__name__}")
    return value


def _tier_specs(path: Path, data: Mapping) -> list[tuple[int, str, str, str]]:
    """(id, title, signed_off_by, ISO date) per [[tier]], ids unique; who and date together."""
    tiers = []
    for i, body in enumerate(data.get("tier", [])):
        where = f"tier[{i}]"
        tier_id = _value(path, where, body, "id", int)
        title = _value(path, where, body, "title", str)
        who = _value(path, where, body, "signed_off_by", str, required=False) or ""
        date = _value(path, where, body, "signed_off_date", datetime.date, required=False)
        if bool(who) != (date is not None):
            raise _toml_error(path, where, "signed_off_by and signed_off_date come together")
        if any(tier_id == t[0] for t in tiers):
            raise _toml_error(path, where, f"id {tier_id} appears twice")
        tiers.append((tier_id, title, who, date.isoformat() if date else ""))
    return tiers


def _item_spec(path: Path, i: int, body: Mapping) -> _ItemSpec:
    where = f"item[{i}]"
    item_id = _value(path, where, body, "id", str)
    issue = _value(path, where, body, "issue", int)
    match = _ITEM_ID.fullmatch(item_id)
    if match is None or int(match.group(1)) != issue:
        raise _toml_error(path, where, f"id {item_id!r} is not <issue> or <issue>-<n>")
    scope = _value(path, where, body, "scope", str)
    if scope not in SCOPES:
        raise _toml_error(path, where, f"scope {scope!r} is not one of {', '.join(SCOPES)}")
    duplicate_of = _value(path, where, body, "duplicate_of", str,
                          required=scope == SCOPE_DUPLICATE) or ""  # fmt: skip
    return _ItemSpec(item_id, issue, int(match.group(2) or 0),
                     _value(path, where, body, "title", str),
                     _value(path, where, body, "tier", int), scope, duplicate_of)  # fmt: skip


def _item_specs(path: Path, data: Mapping, tier_ids: Iterable[int]) -> list[_ItemSpec]:
    """Every [[item]]: ids unique, each tier a [[tier]] id, each duplicate_of an `in` item."""
    specs = [_item_spec(path, i, body) for i, body in enumerate(data.get("item", []))]
    known = set(tier_ids)
    scopes = {}
    for spec in specs:
        if spec.id in scopes:
            raise _toml_error(path, f"item {spec.id}", "id appears twice")
        if spec.tier not in known:
            raise _toml_error(path, f"item {spec.id}", f"tier {spec.tier} is not a [[tier]] id")
        scopes[spec.id] = spec.scope
    for spec in specs:
        if spec.scope == SCOPE_DUPLICATE and scopes.get(spec.duplicate_of) != SCOPE_IN:
            raise _toml_error(path, f"item {spec.id}",
                              f"duplicate_of {spec.duplicate_of!r} is not an `in` item")
    return specs


def _id_cell(path: Path, number: int, column: str, cell: str, known: Container[str]
             ) -> tuple[str, ...]:  # fmt: skip
    ids = tuple(cell.split(_LIST)) if cell else ()
    stray = [item_id for item_id in ids if item_id not in known]
    if stray:
        raise ProgressError(f"{path}: data row {number}: {column} names {stray[0]!r}, not an "
                            f"`in` item of {MECHANICS_TOML}")  # fmt: skip
    return ids


def _member(path: Path, number: int, rec: Mapping[str, str], known: Container[str]) -> _Member:
    exe = rec["exe"]
    if exe not in (stem for stem, _label in EXES):
        raise ProgressError(f"{path}: data row {number}: exe {exe!r} is not a config stem")
    items = _id_cell(path, number, "items", rec["items"], known)
    members = _id_cell(path, number, "member_items", rec["member_items"], known)
    if not items or not set(members) <= set(items):
        raise ProgressError(f"{path}: data row {number}: items is empty or misses a member item")
    if not _TIER_IDS.fullmatch(rec["tiers"]):
        raise ProgressError(f"{path}: data row {number}: tiers {rec['tiers']!r} is not a list")
    if rec["via"] not in VIAS or rec["role"] not in ROLES:
        raise ProgressError(f"{path}: data row {number}: via {rec['via']!r} or role "
                            f"{rec['role']!r} is not a known value")  # fmt: skip
    if (rec["role"] == ROLE_MEMBER) != bool(members):
        raise ProgressError(f"{path}: data row {number}: role {rec['role']} disagrees with "
                            "member_items")  # fmt: skip
    _check_hub_cell(path, number, rec["role"], rec["hub"])
    return _Member(exe, _address(path, number, "address", rec["address"]), items, members,
                   rec["role"])  # fmt: skip


def _check_hub_cell(path: Path, number: int, role: str, cell: str) -> None:
    """The hub cell is yes or no, yes on a role hub row and no on a role closure row (07-43)."""
    if cell not in (_YES, _NO):
        raise ProgressError(f"{path}: data row {number}: hub {cell!r} is not {_YES} or {_NO}")
    if (role == ROLE_HUB and cell == _NO) or (role == ROLE_CLOSURE and cell == _YES):
        raise ProgressError(f"{path}: data row {number}: role {role} disagrees with hub {cell!r}")


def _read_members(path: Path, known: Container[str],
                  functions: Mapping[tuple[str, int], Function]) -> list[_Member]:  # fmt: skip
    """The members rows; each must be a game or thunk row of its EXE's functions.csv, once."""
    rows: list[_Member] = []
    seen: set[tuple[str, int]] = set()
    for number, rec in enumerate(_records(path, MEMBERS_COLUMNS), start=1):
        row = _member(path, number, rec, known)
        key = (row.exe, row.start)
        if key not in functions:
            raise ProgressError(f"{path}: data row {number}: the row at 0x{row.start:08X} names "
                                f"no game or thunk row of config/{row.exe}/{FUNCTIONS_CSV}")
        if key in seen:
            raise ProgressError(f"{path}: data row {number}: 0x{row.start:08X} appears twice")
        seen.add(key)
        rows.append(row)
    return rows


def _figures_over(members: Sequence[_Member], ids: Container[str],
                  functions: Mapping[tuple[str, int], Function]) -> tuple[Coverage, Coverage]:
    """(must match, full closure) over the rows naming any of `ids`: a set of rows, so a row
    two of the items share counts once."""
    must = [functions[(m.exe, m.start)] for m in members
            if m.role == ROLE_MEMBER and any(i in ids for i in m.member_items)]  # fmt: skip
    closure = [functions[(m.exe, m.start)] for m in members
               if m.role != ROLE_ASM and any(i in ids for i in m.items)]  # fmt: skip
    return _coverage(must), _coverage(closure)


def _asm_signed(toml_path: Path, data: Mapping, list_path: Path) -> bool:
    """True when [asm_list] is signed off and its list_sha256 is the SHA-256 of the list's
    bytes with CRLF read as LF (mechanics.asm_list_sha256's rule); False when it is not signed
    off (ruling F2: an unsigned list counts for nothing, `mechanics check` reports it). A
    signed list that is missing or changed since its sign-off is a ProgressError, as
    mechanics.signed_asm refuses it: otherwise its rows would silently go back into the
    published percentage (fix round 1)."""
    body = data.get("asm_list", {})
    who = _value(toml_path, "asm_list", body, "signed_off_by", str, required=False)
    digest = _value(toml_path, "asm_list", body, "list_sha256", str, required=False)
    if not who or not digest:
        return False
    if not list_path.is_file():
        raise ProgressError(f"[asm_list] in {toml_path} is signed off but {list_path} is missing "
                            "(D-23): restore it or re-sign [asm_list]")  # fmt: skip
    try:
        text = list_path.read_bytes().replace(b"\r\n", b"\n")
    except OSError as exc:
        raise ProgressError(f"{list_path}: cannot read ({exc})") from None
    now = hashlib.sha256(text).hexdigest()
    if now != digest:
        raise ProgressError(f"{list_path} changed since its sign-off (D-23): re-sign [asm_list] "
                            f"in {toml_path} (list_sha256 is now {now})")  # fmt: skip
    return True


def _assembler(path: Path, functions: Mapping[tuple[str, int], Function]
               ) -> tuple[tuple[str, int], ...]:  # fmt: skip
    """(stem, start) of each `asm` row of the signed list, each a game or thunk row, once."""
    stems = [stem for stem, _label in EXES]
    found: list[tuple[str, int]] = []
    for number, rec in enumerate(_records(path, ASM_COLUMNS), start=1):
        if rec["exe"] not in stems or rec["verdict"] not in ASM_VERDICTS:
            raise ProgressError(f"{path}: data row {number}: exe {rec['exe']!r} or verdict "
                                f"{rec['verdict']!r} is not a known value")  # fmt: skip
        key = (rec["exe"], _address(path, number, "address", rec["address"]))
        if key in found:
            raise ProgressError(f"{path}: data row {number}: 0x{key[1]:08X} appears twice")
        if rec["verdict"] != VERDICT_ASM:
            continue
        if key not in functions:
            raise ProgressError(f"{path}: data row {number}: the row at 0x{key[1]:08X} names no "
                                f"game or thunk row of config/{key[0]}/{FUNCTIONS_CSV}")
        found.append(key)
    return tuple(sorted(found, key=lambda k: (stems.index(k[0]), k[1])))


def derive_mechanics(config_dir: Path, progress: Progress) -> Mechanics | None:
    """The per-item coverage view (DEC-05) from config_dir/mechanics.toml and
    config_dir/mechanics-members.csv, joined by (exe, address) with `progress` (derive's
    output, so status.csv decides matched), and the rows of config_dir/asm-functions.csv when
    [asm_list] signs it off (D-23). None without mechanics.toml; no items when it has no `in`
    item or the members file is absent (ruling F2). A malformed file, a members or signed asm
    row that is not a game or thunk row of functions.csv, or a signed asm list that is missing
    or changed since its sign-off, is a ProgressError."""
    config = Path(config_dir)
    path = config / MECHANICS_TOML
    if not path.exists():
        return None
    data = _read_toml(path)
    tier_specs = _tier_specs(path, data)
    specs = _item_specs(path, data, (t[0] for t in tier_specs))
    in_items = [spec for spec in specs if spec.scope == SCOPE_IN]
    functions = {(exe.stem, f.start): f for exe in progress.exes for f in exe.functions}
    asm_path = config / ASM_CSV
    assembler = _assembler(asm_path, functions) if _asm_signed(path, data, asm_path) else ()
    members_path = config / MEMBERS_CSV
    if not in_items or not members_path.exists():
        return Mechanics(assembler=assembler)
    members = _read_members(members_path, {spec.id for spec in in_items}, functions)
    items = sorted((ItemCoverage(spec.id, spec.issue, spec.number, spec.title, spec.tier,
                                 *_figures_over(members, {spec.id}, functions))
                    for spec in in_items), key=lambda item: item.key)  # fmt: skip
    tiers = sorted((TierCoverage(tier_id, title, who, date, *_figures_over(
                        members, {s.id for s in in_items if s.tier == tier_id}, functions))
                    for tier_id, title, who, date in tier_specs), key=lambda t: t.id)  # fmt: skip
    duplicates = sorted((Duplicate(s.id, s.issue, s.number, s.title, s.duplicate_of)
                         for s in specs if s.scope == SCOPE_DUPLICATE),
                        key=lambda d: (d.issue, d.number))  # fmt: skip
    return Mechanics(tuple(tiers), tuple(items), tuple(duplicates), assembler)


def _without(exe: ExeProgress, starts: Container[int]) -> ExeProgress:
    moved = tuple(Row(f.start, f.end, f.name, f.kind, f.unit)
                  for f in exe.functions if f.start in starts)  # fmt: skip
    if not moved:
        return exe
    return dataclasses.replace(
        exe, functions=tuple(f for f in exe.functions if f.start not in starts),
        assembler_rows=exe.assembler_rows + moved)  # fmt: skip


def exclude_assembler(progress: Progress, asm_starts: Iterable[tuple[str, int]]) -> Progress:
    """`progress` with each (stem, start) of the signed asm list moved from the EXE's functions
    to its assembler_rows: outside the percentage and the function ratio, drawn and counted like
    the library (D-23). For the page, progress.json, the shields, progress.svg and report.json
    only; the DecompHub feed stays build_decomphub(derive(...)), so committing the list never
    stales the gate-written feed. A start that is no function of `progress` is an error."""
    wanted = set(asm_starts)
    known = {(exe.stem, f.start) for exe in progress.exes for f in exe.functions}
    stray = sorted(wanted - known)
    if stray:
        raise ProgressError(f"asm row {stray[0][0]} 0x{stray[0][1]:08X} is no game or thunk row")
    return Progress(tuple(_without(exe, {start for stem, start in wanted if stem == exe.stem})
                          for exe in progress.exes))  # fmt: skip


# ---- the timeline: matched percent over days (todo progress-timeline-chart) ----
#
# Per EXE, the percent at the end of each day since the first commit, re-derived (with
# _exe_progress and the signed asm rows moved out, so with the tables committed the last day is
# the page's figure) at each first-parent commit of HEAD that changed one of the EXE's three
# tables: the day a change reached the mainline is the day the figure moves. What each day did
# comes from every commit by its own committer date (a merge only by count, unless it changed
# the tables), the drive runs of progress/attempts.jsonl and the dated headings of
# docs/learnings.md. build_timeline is pure; load_timeline is the thin git layer around it.

TIMELINE_FILES = (FUNCTIONS_CSV, UNITS_CSV, STATUS_CSV)
ATTEMPTS_JSONL = Path("progress") / "attempts.jsonl"
LEARNINGS_MD = Path("docs") / "learnings.md"
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_LEARNING = re.compile(r"## ([0-9]{4}-[0-9]{2}-[0-9]{2}): (.+)")
_SUBJECT = re.compile(r"([a-z]+)(?:\(([^)]*)\))?!?: ")  # a conventional-commit prefix
_MATCH_SUBJECT = re.compile(r"feat\([^)]*\)!?: match (.*)")
_MATCH_COUNT = re.compile(r"([0-9]+) ")  # "match 23 Tier 1 functions ..."
_MATCH_NAME = re.compile(r"func_[0-9A-F]{8}")
_FLAG_ID = re.compile(r"F-([0-9]{4})")
_FLAGS_TEXT = " under approved flags "
TOOLING_TYPES = ("feat", "fix", "refactor", "perf", "test", "build", "ci", "style")
PLAN_TYPES = ("docs",)
CO_AUTHOR, MATCHED_BY = "co-authored-by", "matched-by"
CREDIT_NAMES = 2  # a match with more co-authors than this is credited to their count
MATCHED_BY_TOOL = "reverseapoc "  # Matched-By: reverseapoc drive / lift name the tool, no model
RUN_KIND, RUN_FINAL = "run", ("ENDED", "STOPPED")  # STARTED alone is a run still going
_GIT_SAFE = ("-c", "safe.directory=*")
_RECORD, _UNIT_SEP, _TRAILER_SEP = "\x1e", "\x1f", "\x1d"
SHALLOW_NOTE = ("This checkout is a shallow clone, so the history the chart is drawn from is "
                "cut; the chart is left out.")  # fmt: skip


@dataclass(frozen=True)
class Snapshot:
    """A first-parent commit that changed an EXE's tables: per stem, the (functions, units,
    status) texts after it, None for a table the commit does not have."""

    sha: str
    day: str  # committer date, YYYY-MM-DD in the committer's zone
    texts: Mapping[str, tuple[str | None, str | None, str | None]]


@dataclass(frozen=True)
class LoggedCommit:
    """A commit: its subject, its trailers as (key, value), and whether it is a merge."""

    sha: str
    day: str
    subject: str
    trailers: tuple[tuple[str, str], ...] = ()
    merge: bool = False


@dataclass(frozen=True)
class RunLog:
    """A drive run's last ENDED or STOPPED record: (model, sessions, matched) per model."""

    run: str
    day: str
    sessions: int
    matched: int
    by_model: tuple[tuple[str, int, int], ...] = ()


@dataclass(frozen=True)
class Day:
    """One calendar day: each EXE's percent at its end (None before its tables exist) and the
    change from the day before (None on the EXE's first day), its biggest driver and summary."""

    date: str
    index: int  # days since the first commit's day
    percents: tuple[float | None, ...]
    deltas: tuple[float | None, ...]
    driver: str  # "" on a day with nothing logged
    summary: str

    @property
    def active(self) -> bool:
        return bool(self.driver)


@dataclass(frozen=True)
class Timeline:
    """The days from the first commit's to the last logged one, EXE figures in EXES order; no
    days and a note when the history cannot be read (a shallow clone)."""

    labels: tuple[str, ...]
    days: tuple[Day, ...] = ()
    note: str = ""


def parse_runs(text: str, path: Path = ATTEMPTS_JSONL) -> tuple[RunLog, ...]:
    """Each run's last ENDED or STOPPED record of an attempts.jsonl, in first-seen order. A line
    that is not JSON, or a final run record missing its run, date, sessions or matched, is a
    ProgressError naming its line."""
    final: dict[str, RunLog] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProgressError(f"{path}: line {number}: not JSON ({exc})") from None
        if not isinstance(record, dict) or record.get("kind") != RUN_KIND:
            continue
        if record.get("event") not in RUN_FINAL:
            continue
        found = _run_log(record)
        if found is None:
            raise ProgressError(f"{path}: line {number}: a run record without a run, a date, "
                                "sessions or matched")  # fmt: skip
        final[found.run] = found
    return tuple(final.values())


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _run_log(record: Mapping) -> RunLog | None:
    run, day = record.get("run"), record.get("date")
    sessions, matched = _count(record.get("sessions")), _count(record.get("matched"))
    if not isinstance(run, str) or not isinstance(day, str) or not _DATE.fullmatch(day):
        return None
    try:
        datetime.date.fromisoformat(day)
    except ValueError:  # month 13 and the like; the caller names the line
        return None
    if sessions is None or matched is None:
        return None
    totals = record.get("totals")
    by_model = totals.get("by_model") if isinstance(totals, dict) else None
    models = []
    for model, figures in sorted((by_model or {}).items()):
        if isinstance(figures, dict):
            models.append((model, _count(figures.get("sessions")) or 0,
                           _count(figures.get("matched")) or 0))  # fmt: skip
    return RunLog(run, day, sessions, matched, tuple(models))


def parse_learnings(text: str) -> tuple[tuple[str, str], ...]:
    """(date, title) of each `## YYYY-MM-DD: title` heading of docs/learnings.md, in order."""
    return tuple((m[1], m[2].strip()) for line in text.splitlines()
                 if (m := _LEARNING.fullmatch(line.rstrip())))  # fmt: skip


def _timeline_dir(sha: str, stem: str) -> PurePosixPath:
    """How a past commit's table is named in an error: `<sha>:config/<stem>/<file>`."""
    return PurePosixPath(f"{sha}:config/{stem}")


def _snapshot_percent(snap: Snapshot, stem: str, label: str, asm: Container[int],
                      parsed: dict[tuple[str, str], list]) -> float | None:  # fmt: skip
    """The EXE's percent after `snap`, None while it has no functions.csv or units.csv. The
    big tables are parsed once per distinct text (`parsed`), status.csv at every snapshot."""
    functions, units, status = snap.texts[stem]
    if functions is None or units is None:
        return None
    where = _timeline_dir(snap.sha, stem)
    if (FUNCTIONS_CSV, functions) not in parsed:
        parsed[(FUNCTIONS_CSV, functions)] = read_functions(where / FUNCTIONS_CSV, functions)
    if (UNITS_CSV, units) not in parsed:
        parsed[(UNITS_CSV, units)] = read_units(where / UNITS_CSV, units)
    statuses = [] if status is None else read_status(where / STATUS_CSV, status)
    exe = _exe_progress(where, stem, label, parsed[(FUNCTIONS_CSV, functions)],
                        parsed[(UNITS_CSV, units)], statuses)  # fmt: skip
    return _without(exe, asm).totals.percent


def _day_figures(snapshots: Sequence[Snapshot], asm: Iterable[tuple[str, int]]
                 ) -> dict[str, tuple[float | None, ...]]:  # fmt: skip
    """Per day with a snapshot, each EXE's percent after its last snapshot of that day. A
    snapshot dated before the one it follows (committer dates can go back along the mainline:
    another zone, a rebase) counts on that one's day, so no figure moves into the past. An EXE
    is re-derived only when its texts changed."""
    wanted = set(asm)
    parsed: dict[tuple[str, str], list] = {}
    current: list[float | None] = [None] * len(EXES)
    seen: dict[str, tuple[str | None, ...]] = {}
    out: dict[str, tuple[float | None, ...]] = {}
    day = ""
    for snap in snapshots:
        day = max(day, snap.day)
        for i, (stem, label) in enumerate(EXES):
            if stem not in snap.texts or seen.get(stem) == snap.texts[stem]:
                continue
            seen[stem] = snap.texts[stem]
            starts = {start for s, start in wanted if s == stem}
            current[i] = _snapshot_percent(snap, stem, label, starts, parsed)
        out[day] = tuple(current)
    return out


def _conventional(subject: str) -> tuple[str, str]:
    """(type, scope) of a conventional-commit subject, ("", "") for any other."""
    found = _SUBJECT.match(subject)
    return (found[1], found[2] or "") if found else ("", "")


def _match_size(rest: str) -> int:
    """Functions one match commit lands: `match 23 ...` 23, else the func_ names before ` in `
    (at least one)."""
    count = _MATCH_COUNT.match(rest)
    if count:
        return int(count[1])
    return max(len(_MATCH_NAME.findall(rest.split(" in ", 1)[0])), 1)


def _credit(trailers: Iterable[tuple[str, str]]) -> str:
    """Who a match is credited to: its Co-Authored-By name (two joined by "and", more counted),
    else the model a Matched-By names, else "no co-author"."""
    pairs = [(key.strip().lower(), value.strip()) for key, value in trailers]
    names = sorted({value.split(" <", 1)[0] for key, value in pairs if key == CO_AUTHOR})
    if len(names) > CREDIT_NAMES:
        return f"{len(names)} co-authors"
    if names:
        return " and ".join(names)
    models = [value for key, value in pairs
              if key == MATCHED_BY and not value.startswith(MATCHED_BY_TOOL)]  # fmt: skip
    return models[0] if models else "no co-author"


def _flag_ranges(ids: Iterable[int]) -> str:
    """F-0069, F-0070, F-0071, F-0073 as "F-0069..F-0071, F-0073"."""
    ordered = sorted(set(ids))
    spans: list[list[int]] = []
    for n in ordered:
        if spans and n == spans[-1][1] + 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return ", ".join(f"F-{a:04d}" if a == b else f"F-{a:04d}..F-{b:04d}" for a, b in spans)


def _plural(count: int, word: str, many: str | None = None) -> str:
    return f"{count} {word if count == 1 else many or word + 's'}"


@dataclass
class _DayLog:
    """What one day logged, gathered before it is worded."""

    credits: dict[str, int] = dataclasses.field(default_factory=dict)  # credit -> functions
    unflagged: dict[str, int] = dataclasses.field(default_factory=dict)  # the same, no flags
    flagged: int = 0  # functions landed under approved flags
    flags: set[int] = dataclasses.field(default_factory=set)
    tooling: dict[str, int] = dataclasses.field(default_factory=dict)  # scope -> commits
    plans: int = 0
    other: int = 0
    merges: int = 0
    table_merges: list[str] = dataclasses.field(default_factory=list)  # their subjects
    runs: list[RunLog] = dataclasses.field(default_factory=list)
    learnings: list[str] = dataclasses.field(default_factory=list)

    def add(self, commit: LoggedCommit, snapshots: Container[str]) -> None:
        """Count `commit`; a merge in `snapshots` (it changed the tables) is kept by subject,
        since its branch's matches are credited on their own days."""
        if commit.merge:
            self.merges += 1
            if commit.sha in snapshots:
                self.table_merges.append(commit.subject)
            return
        match = _MATCH_SUBJECT.match(commit.subject)
        kind, scope = _conventional(commit.subject)
        if match is not None:
            size = _match_size(match[1])
            credit = _credit(commit.trailers)
            self.credits[credit] = self.credits.get(credit, 0) + size
            if _FLAGS_TEXT in match[1]:
                self.flagged += size
                self.flags |= {int(n) for n in _FLAG_ID.findall(match[1])}
            else:
                self.unflagged[credit] = self.unflagged.get(credit, 0) + size
        elif kind in TOOLING_TYPES:
            self.tooling[scope] = self.tooling.get(scope, 0) + 1
        elif kind in PLAN_TYPES:
            self.plans += 1
        else:
            self.other += 1


def _most(counts: Mapping[str, int]) -> tuple[str, int]:
    """The key with the highest count, the first in sort order on a tie."""
    return min(counts.items(), key=lambda item: (-item[1], item[0]))


def _driver(log: _DayLog) -> str:
    """The day's biggest driver: the largest match group (the flagged matches together, else
    each credit), else the last merge that changed the tables, its largest drive run, its top
    tooling scope, its plans, its other commits, its merges or its learnings; "" for a day with
    nothing logged."""
    groups = dict(log.unflagged)
    if log.flagged:
        groups[f"flags {_flag_ranges(log.flags)}"] = log.flagged
    if groups:
        name, size = _most(groups)
        return f"{name}: {_plural(size, 'match', 'matches')}"
    if log.table_merges:
        return f"merge: {log.table_merges[-1]}"
    if log.runs:
        run = min(log.runs, key=lambda r: (-r.sessions, r.run))
        return f"drive run {run.run}: {run.sessions} sessions, {run.matched} matched"
    if log.tooling:
        scope, count = _most(log.tooling)
        return f"tooling: {scope} ({_plural(count, 'commit')})" if scope else (
            f"tooling: {_plural(count, 'unscoped commit')}")
    if log.plans:
        return f"plans or docs: {_plural(log.plans, 'commit')}"
    if log.other:
        return _plural(log.other, "other commit")
    if log.merges:
        return _plural(log.merges, "merge")
    return "learnings" if log.learnings else ""


def _by_count(counts: Mapping[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _runs_text(runs: Sequence[RunLog]) -> str:
    """The day's drive runs in one clause, with each model's matched of its sessions."""
    models: dict[str, list[int]] = {}
    for run in runs:
        for model, sessions, matched in run.by_model:
            figures = models.setdefault(model, [0, 0])
            figures[0] += sessions
            figures[1] += matched
    detail = (f"{sum(r.sessions for r in runs)} sessions, "
              f"{sum(r.matched for r in runs)} matched")  # fmt: skip
    if models:
        detail += ": " + ", ".join(f"{model} {matched} of {sessions}"
                                   for model, (sessions, matched) in sorted(models.items()))
    return f"{_plural(len(runs), 'drive run')} ({detail})"


def _summary(log: _DayLog) -> str:
    """The day in one sentence: matches by credit, flags, drive runs, tooling, plan and other
    commits, then the learnings by title."""
    parts = []
    total = sum(log.credits.values())
    if total:
        who = ", ".join(f"{name} {size}" for name, size in _by_count(log.credits))
        parts.append(f"{_plural(total, 'match', 'matches')} ({who})")
    if log.flags:
        parts.append(f"flags {_flag_ranges(log.flags)}")
    if log.runs:
        parts.append(_runs_text(log.runs))
    if log.tooling:
        parts.append(_plural(sum(log.tooling.values()), "tooling commit"))
    if log.plans:
        parts.append(_plural(log.plans, "plan or docs commit"))
    if log.other:
        parts.append(_plural(log.other, "other commit"))
    if log.merges:
        parts.append(_plural(log.merges, "merge"))
    if log.learnings:
        word = "learning" if len(log.learnings) == 1 else "learnings"
        parts.append(f"{word}: {'; '.join(log.learnings)}")
    return "; ".join(parts) + "." if parts else ""


def _delta(now: float | None, before: float | None) -> float | None:
    if now is None or before is None:
        return None
    return round(now - before, PERCENT_DECIMALS)


def build_timeline(snapshots: Sequence[Snapshot], commits: Iterable[LoggedCommit],
                   runs: Iterable[RunLog], learnings: Iterable[tuple[str, str]],
                   asm: Iterable[tuple[str, int]]) -> Timeline:  # fmt: skip
    """Every calendar day from the first logged day to the last (snapshots, commits and runs;
    learnings dated outside that span are left out): each EXE's percent at the day's end, carried
    over days without a snapshot, the change from the day before, the biggest driver and a
    summary. `snapshots` are first-parent order, oldest first; `asm` the (stem, start) of the
    signed asm rows, moved out of every day as the page moves them out (D-23). A table the
    reader refuses is a ProgressError naming `<sha>:config/<stem>/<file>`."""
    labels = tuple(label for _stem, label in EXES)
    figures = _day_figures(snapshots, asm)
    movers = {snap.sha for snap in snapshots}
    logs: dict[str, _DayLog] = {}
    for logged in commits:
        logs.setdefault(logged.day, _DayLog()).add(logged, movers)
    for run in runs:
        logs.setdefault(run.day, _DayLog()).runs.append(run)
    dates = sorted(set(logs) | set(figures))
    if not dates:
        return Timeline(labels)
    first, last = (datetime.date.fromisoformat(d) for d in (dates[0], dates[-1]))
    for day, title in learnings:
        if dates[0] <= day <= dates[-1]:
            logs.setdefault(day, _DayLog()).learnings.append(title)
    days = []
    current: tuple[float | None, ...] = (None,) * len(EXES)
    for index in range((last - first).days + 1):
        date = (first + datetime.timedelta(days=index)).isoformat()
        before, current = current, figures.get(date, current)
        log = logs.get(date, _DayLog())
        days.append(Day(date, index, current,
                        tuple(_delta(now, then) for now, then in zip(current, before, strict=True)),
                        _driver(log), _summary(log)))  # fmt: skip
    return Timeline(labels, tuple(days))


def _git(repo: Path, args: Sequence[str], data: bytes | None = None) -> bytes:
    """`git -c safe.directory=* -C repo <args>`'s output; a failure is a ProgressError."""
    try:
        done = subprocess.run(["git", *_GIT_SAFE, "-C", str(repo), *args], input=data,
                              capture_output=True, check=False)  # fmt: skip
    except OSError as exc:
        raise ProgressError(f"git {args[0]}: cannot run ({exc})") from None
    if done.returncode != 0:
        why = done.stderr.decode("utf-8", "replace").strip()
        raise ProgressError(f"git {args[0]} failed in {repo}: {why}")
    return done.stdout


def _table_changes(repo: Path) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """(sha, day, the (stem, file) tables it changed) of each first-parent commit of HEAD that
    changed one, oldest first; a merge counts what it changed against its first parent."""
    tracked = {f"config/{stem}/{name}": (stem, name)
               for stem, _label in EXES for name in TIMELINE_FILES}  # fmt: skip
    raw = _git(repo, ["log", "--first-parent", "--diff-merges=first-parent", "--reverse",
                      "--name-only", f"--format={_RECORD}%H %cs", "HEAD"])  # fmt: skip
    out = []
    for chunk in raw.decode("utf-8", "replace").split(_RECORD)[1:]:
        head, *paths = chunk.splitlines()
        sha, day = head.split()
        touched = [tracked[p] for p in paths if p in tracked]
        if touched:
            out.append((sha, day, touched))
    return out


def _cat_files(repo: Path, specs: Sequence[str]) -> list[str | None]:
    """The text of each `<sha>:<path>` through one `git cat-file --batch`, None when the commit
    has no such file."""
    if not specs:
        return []
    raw = _git(repo, ["cat-file", "--batch"], ("\n".join(specs) + "\n").encode("utf-8"))
    out: list[str | None] = []
    pos = 0
    for spec in specs:
        end = raw.find(b"\n", pos)
        header = raw[pos:end].decode("utf-8", "replace").split() if end >= 0 else []
        pos = end + 1
        if header[-1:] == ["missing"]:
            out.append(None)
            continue
        if len(header) != 3 or header[1] != "blob" or not header[2].isdigit():
            raise ProgressError(f"git cat-file: {spec}: unexpected answer {' '.join(header)!r}")
        size = int(header[2])
        try:
            out.append(raw[pos:pos + size].decode("utf-8"))
        except UnicodeDecodeError:
            raise ProgressError(f"{spec}: not UTF-8") from None
        pos += size + 1
    return out


def _snapshots(repo: Path) -> list[Snapshot]:
    """One Snapshot per first-parent commit that changed a table. Only the changed tables are
    read (all three on an EXE's first change); the others carry over from the snapshot before."""
    changes = _table_changes(repo)
    wanted: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for i, (_sha, _day, touched) in enumerate(changes):
        for stem in dict.fromkeys(stem for stem, _name in touched):
            names = [name for s, name in touched if s == stem] if stem in seen else TIMELINE_FILES
            seen.add(stem)
            wanted += [(i, stem, name) for name in names]
    texts = _cat_files(repo, [f"{changes[i][0]}:config/{stem}/{name}" for i, stem, name in wanted])
    read: dict[int, list[tuple[str, str, str | None]]] = {}
    for (i, stem, name), text in zip(wanted, texts, strict=True):
        read.setdefault(i, []).append((stem, name, text))
    state: dict[str, list[str | None]] = {}
    out = []
    for i, (sha, day, _touched) in enumerate(changes):
        for stem, name, text in read[i]:
            state.setdefault(stem, [None] * len(TIMELINE_FILES))[TIMELINE_FILES.index(name)] = text
        out.append(Snapshot(sha, day, {stem: tuple(now) for stem, now in state.items()}))
    return out


def _logged_commits(repo: Path) -> list[LoggedCommit]:
    """Every commit of HEAD, oldest first, with its subject and trailers; a commit with more
    than one parent is a merge."""
    fmt = f"--format={_RECORD}%H{_UNIT_SEP}%P{_UNIT_SEP}%cs{_UNIT_SEP}%s{_UNIT_SEP}" + (
        "%(trailers:only,unfold,separator=%x1d)")
    raw = _git(repo, ["log", "--reverse", fmt, "HEAD"])
    out = []
    for chunk in raw.decode("utf-8", "replace").split(_RECORD)[1:]:
        sha, parents, day, subject, trailers = chunk.rstrip("\n").split(_UNIT_SEP, 4)
        pairs = tuple((key.strip(), value.strip()) for key, sep, value
                      in (t.partition(":") for t in trailers.split(_TRAILER_SEP)) if sep)
        out.append(LoggedCommit(sha, day, subject, pairs, len(parents.split()) > 1))
    return out


def _repo_text(path: Path) -> str:
    """A repository file's text, "" when it is absent."""
    try:
        return path.read_bytes().decode("utf-8") if path.exists() else ""
    except (OSError, UnicodeDecodeError) as exc:
        raise ProgressError(f"{path}: cannot read ({exc})") from None


def load_timeline(repo: Path, asm: Iterable[tuple[str, int]]) -> Timeline | None:
    """The timeline of the checkout at `repo` (the directory holding config/): None when it is
    no checkout (no .git: a config tree on its own has no history), no days and SHALLOW_NOTE in
    a shallow clone. A git failure or a table the reader refuses is a ProgressError."""
    repo = Path(repo)
    if not (repo / ".git").exists():
        return None
    if _git(repo, ["rev-parse", "--is-shallow-repository"]).strip() == b"true":
        return Timeline(tuple(label for _stem, label in EXES), note=SHALLOW_NOTE)
    return build_timeline(_snapshots(repo), _logged_commits(repo),
                          parse_runs(_repo_text(repo / ATTEMPTS_JSONL), ATTEMPTS_JSONL),
                          parse_learnings(_repo_text(repo / LEARNINGS_MD)), asm)  # fmt: skip



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
        "assembler_bytes": totals.assembler_bytes,
        "assembler_functions": totals.assembler_functions,
        "data_in_code_bytes": totals.data_in_code_bytes,
        "functions": {"total": totals.total_functions, "matched": totals.matched_functions,
                      "partial": totals.partial_functions},  # fmt: skip
    }


def _coverage_doc(coverage: Coverage) -> dict[str, object]:
    return {"functions": {"total": coverage.functions, "matched": coverage.matched,
                          "partial": coverage.partial, "unmatched": coverage.unmatched},
            "bytes": {"total": coverage.total_bytes, "matched": coverage.matched_bytes,
                      "partial": coverage.partial_bytes},
            "percent": coverage.percent}  # fmt: skip


def _sign_off_doc(tier: TierCoverage) -> dict[str, object]:
    return {"signed_off_by": tier.signed_off_by or None,
            "signed_off_date": tier.signed_off_date or None}  # fmt: skip


def build_mechanics(mechanics: Mechanics | None) -> dict[str, object] | None:
    """progress.json's "mechanics": per tier and per `in` item the must-match and full-closure
    figures and the tier's sign-off, and the duplicates; None without mechanics.toml."""
    if mechanics is None:
        return None
    tiers = {tier.id: tier for tier in mechanics.tiers}
    return {
        "tiers": [{"id": t.id, "title": t.title, "state": t.state, **_sign_off_doc(t),
                   "must_match": _coverage_doc(t.must_match),
                   "full_closure": _coverage_doc(t.full_closure)}
                  for t in mechanics.tiers],
        "items": [{"id": i.id, "issue": i.issue, "title": i.title, "tier": i.tier,
                   **_sign_off_doc(tiers[i.tier]), "must_match": _coverage_doc(i.must_match),
                   "full_closure": _coverage_doc(i.full_closure)}
                  for i in mechanics.items],
        "duplicates": [{"id": d.id, "issue": d.issue, "title": d.title,
                        "duplicate_of": d.duplicate_of} for d in mechanics.duplicates],
    }  # fmt: skip


def build_progress(progress: Progress, commit: str | None = None,
                   mechanics: Mechanics | None = None) -> dict[str, object]:  # fmt: skip
    """progress.json: per EXE and combined counts, the percent, the mechanics coverage view
    (null without mechanics.toml) and the notes (D-26, D-50, DEC-05)."""
    return {
        "version": PROGRESS_VERSION,
        "commit": commit,
        "exes": {exe.stem: {"label": exe.label, **_totals_doc(exe.totals)}
                 for exe in progress.exes},  # fmt: skip
        "combined": _totals_doc(progress.combined),
        "mechanics": build_mechanics(mechanics),
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


def write_progress_json(progress: Progress, path: Path, commit: str | None = None,
                        mechanics: Mechanics | None = None) -> None:  # fmt: skip
    _write_atomic(path, render(build_progress(progress, commit, mechanics)))


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
                 # D-23: signed asm rows are library cells too. Not longer than this: the SVG
                 # legend is right-aligned and a longer label meets the bold heading at 1200 px.
                 LIBRARY: "library or assembler",
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
    title: str | None = None  # a tooltip, matched and partial cells only
    name: str | None = None  # the function's name; None for uncovered bytes (not in `key`)
    best_percent: float = 0.0  # Function.best_percent for a function cell (not in `key`)

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


def _best(value: float) -> str:
    """A best_percent as status.csv stores it: 2 decimals (status.py's rule)."""
    return f"{value:.2f}%"


def _function_title(f: Function) -> str | None:
    """A function cell's tooltip: matched and partial cells only, a partial one with its best
    score (the counting is unchanged: a partial still adds no matched byte)."""
    if f.status == MATCHED:
        return f"{f.name}: {f.size:,} bytes, matched"
    if f.status == PARTIAL:
        return f"{f.name}: {f.size:,} bytes, partial, best {_best(f.best_percent)}"
    return None


def _unit_cells(exe: ExeProgress) -> dict[str, list[_Cell]]:
    """The cells of each unit: its game/thunk functions, runtime and signed asm rows (both
    library cells, D-23) and uncovered bytes. Data-in-code is not drawn (D-26)."""
    groups: dict[str, list[_Cell]] = {}
    for f in exe.functions:
        groups.setdefault(f.unit or UNASSIGNED_UNIT, []).append(
            _Cell(f.size, f.start, f.status, _function_title(f), f.name, f.best_percent))
    for row in (*exe.library_rows, *exe.assembler_rows):
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
    partial = [c.best_percent for c in cells if c.status == PARTIAL]
    if partial:
        parts.append(f"{len(partial)} partial (best {_best(max(partial))})")
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
    groups (a unit with partials names their count and best score) and on matched and partial
    cells only (a partial one with its best score), coordinates are rounded to 0.1, and no
    game byte is in it. Units large enough carry a label (a game unit its unit name, a library
    unit its largest runtime function), cut with an ellipsis when the name is too long, small
    units none; labels ignore the pointer, so the tooltips stay reachable."""
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


# ---- index.html, the progress page ----

# Written once, as index.html, so the Pages root (which the README, .recomp.json's Progress link
# and the docs/listings.md drafts point at) serves it (owner ruling of 2026-10-26: no second,
# byte-identical progress.html).
INDEX_HTML = "index.html"
PAGE_TITLE = "ReverseApoc progress"
PAGE_HEADING = "X-COM: Apocalypse (DOS) decompilation progress"
COMMIT_URL = REPOSITORY + "/commit/"
COMMIT_SHORT = 7  # hex digits of the commit shown on the page
# report.json is an artifact of the Pages run, not a Pages file: the page links the workflow.
PAGES_WORKFLOW_URL = REPOSITORY + "/actions/workflows/pages.yml"
README_URL = REPOSITORY + "#progress"
BAR_HEIGHT = 8  # px, the percent bar
# The dark scheme swaps surface, ink and secondary only, to warm near-blacks like the palette's
# warm greys; the status hues stay the D-50 ones in both schemes. Measured (WCAG 2.x): ink
# 15.18:1, secondary 7.44:1; on the dark surface matched 3.66, partial 8.36, unmatched 5.04,
# library 4.10, uncovered 12.45 (all >= 3:1 for graphics, WCAG 1.4.11).
DARK_SURFACE, DARK_INK, DARK_SECONDARY_INK = "#161615", "#ecebe7", "#a8a6a0"
# The inline mosaic's scheme paints, each mapped to its page variable (render_svg is unchanged,
# so progress.svg on its own stays light).
MOSAIC_PAINTS = (("fill", SURFACE, "surface"), ("stroke", SURFACE, "surface"),
                 ("fill", INK, "ink"), ("fill", SECONDARY_INK, "secondary"))  # fmt: skip
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
# D-23: a signed asm row keeps its place in the strip as a short tick in the library colour.
ASSEMBLER_TICK = "l"
ASSEMBLER_KEY = (f'<p class="key"><i class="{ASSEMBLER_TICK}" aria-hidden="true"></i> assembler: '
                 "hand-written assembly on the owner-signed list, not decompiled and outside the "
                 "percentage like the runtime library.</p>")  # fmt: skip
# Backlog 999.4 fix #2 (06-UI-REVIEW.md): below 40rem the 1200 px mosaic would scale to about 31%
# (labels near 3.5 px), so there it keeps a 48rem minimum width (_page_css) and its box scrolls
# sideways. The box takes keyboard focus so the arrow keys scroll it, and an HTML legend above it
# stays in view.
MOSAIC_REGION = ('<div class="mosaic" tabindex="0" role="region" '
                 'aria-label="Decompilation mosaic, scrolls sideways">')  # fmt: skip
SWATCH_SIZE = ".75rem"  # the HTML legend's colour square
# Backlog 999.4 fix #1: the strip's tooltips need a mouse, so each EXE also lists them as text.
TOOLTIP_LIST_SUMMARY = "Matched and partial functions"
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
    "stays outside both; data-in-code is excluded. Game functions on the owner-signed assembler "
    "list (config/asm-functions.csv: hand-written assembly, which cannot match from C) are drawn "
    "and counted with the library, outside both, on this page, in progress.json, the badges and "
    "report.json; the DecompHub feed decomphub.progress.json still counts them as game code.",
    "Every figure comes from committed tables: the status.csv files that reverseapoc gate "
    "writes, plus each EXE's functions.csv and units.csv. This page is regenerated from them on "
    "every push to main. The raw numbers are in <a href=\"progress.json\">progress.json</a>, the "
    f'objdiff-shaped <a href="{PAGES_WORKFLOW_URL}">report.json</a> is attached to each run of '
    f'the Pages workflow, and the <a href="{README_URL}">README</a> has the full definitions.',
)


def _coverage_css() -> list[str]:
    """The coverage section's rules: its lists, and its bar of matched, partial and unmatched
    segments, each non-zero one at least 2 px wide (the 999.4 fix #3 rule)."""
    return [
        ".items,.tiers,.duplicates{max-width:70ch;margin:.75rem 0 0;padding-left:1.25rem}",
        ".items li,.tiers li{margin-bottom:.75rem}",
        f".cov{{display:flex;height:{BAR_HEIGHT}px;max-width:24rem;margin-top:.25rem;"
        "overflow:hidden}",
        ".cov span{flex:none;height:100%}",
        ".cov .nz{min-width:2px}",
        *(f".cov .{TICK_CLASSES[status]}{{background:{TREEMAP_COLORS[status]}}}"
          for status in (MATCHED, PARTIAL, UNMATCHED)),
    ]


def _assembler_css() -> list[str]:
    """The assembler tick: short like an unmatched one, in the library colour (D-23)."""
    return [f"i.{ASSEMBLER_TICK}{{background:{TREEMAP_COLORS[LIBRARY]}}}",
            f".strip .{ASSEMBLER_TICK},.key .{ASSEMBLER_TICK}{{height:{TICK_SHORT}px;"
            f"margin-top:{TICK_HEIGHT - TICK_SHORT}px}}"]  # fmt: skip


def _page_css(coverage: bool = False, assembler: bool = False, timeline: bool = False) -> str:
    """The inline style sheet, one rule per line, from the SVG's own tokens; the coverage
    section's, the assembler tick's and the timeline chart's rules only when the page has
    them."""
    return "\n".join([
        f":root{{--surface:{SURFACE};--ink:{INK};--secondary:{SECONDARY_INK};"
        "color-scheme:light dark}",
        f"@media (prefers-color-scheme: dark){{:root{{--surface:{DARK_SURFACE};--ink:{DARK_INK};"
        f"--secondary:{DARK_SECONDARY_INK}}}}}",
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
        ".bar .nz{min-width:2px}",
        ".figures{margin:0;font-size:.875rem;font-variant-numeric:tabular-nums}",
        ".strip{display:flex;flex-wrap:wrap;align-items:flex-start;"
        f"gap:{TICK_ROW_GAP}px {TICK_GAP}px;margin-top:.75rem}}",
        f".strip i,.key i{{flex:none;width:{TICK_WIDTH}px;height:{TICK_HEIGHT}px}}",
        ".key i{display:inline-block}",
        # Two-class selectors, so the short tick outranks the base tick rule in any order.
        f".strip .u,.key .u{{height:{TICK_SHORT}px;margin-top:{TICK_HEIGHT - TICK_SHORT}px}}",
        *(f"i.{TICK_CLASSES[status]}{{background:{TREEMAP_COLORS[status]}}}"
          for status in (MATCHED, PARTIAL, UNMATCHED)),
        *(_assembler_css() if assembler else []),
        "details{margin-top:.75rem;font-size:.875rem}",
        "details ul{margin:.5rem 0 0;padding-left:1.25rem;font-variant-numeric:tabular-nums}",
        "summary:focus-visible{outline:2px solid var(--ink);outline-offset:2px}",
        ".legend{display:flex;flex-wrap:wrap;gap:.25rem 1rem;margin:.75rem 0 0;padding:0;"
        "list-style:none;color:var(--secondary);font-size:.875rem}",
        f".swatch{{display:inline-block;width:{SWATCH_SIZE};height:{SWATCH_SIZE};"
        "margin-right:.375rem;vertical-align:-.0625rem}",
        ".mosaic{margin-top:.75rem;overflow-x:auto}",
        ".mosaic:focus-visible{outline:2px solid var(--ink);outline-offset:2px}",
        ".mosaic svg{display:block;width:100%;height:auto}",
        *(f'.mosaic [{attr}="{token}"]{{{attr}:var(--{var})}}'
          for attr, token, var in MOSAIC_PAINTS),
        *(_coverage_css() if coverage else []),
        *(_timeline_css() if timeline else []),
        "@media (max-width: 40rem){.exe{grid-template-columns:minmax(0,1fr)}"
        ".exe h2{margin-bottom:.5rem}.mosaic svg{min-width:48rem}}",
    ])


def _figures(exe: ExeProgress) -> str:
    t = exe.totals
    text = (f"{shield_message(t.percent)} of code bytes, {t.matched_functions:,} of "
            f"{t.total_functions:,} functions matched, {t.partial_functions:,} partial")
    if not t.assembler_functions:
        return text
    plural = "" if t.assembler_functions == 1 else "s"
    return (f"{text}; {t.assembler_functions:,} assembler function{plural} "
            f"({t.assembler_bytes:,} bytes) outside the percentage")


def _tick_html(f: Function) -> str:
    """One strip tick; matched and partial ticks carry the mosaic cell's tooltip (a partial one
    with its best score)."""
    cls = TICK_CLASSES[f.status]
    title = _function_title(f)
    if title is None:
        return f'<i class="{cls}"></i>'
    return f'<i class="{cls}" title="{_xml(title)}"></i>'


def _strip_html(exe: ExeProgress) -> str:
    """The function strip: one tick per game and thunk function in address order, a signed asm
    row as an assembler tick in its place (D-23), as one role=img element whose aria-label holds
    the counts."""
    t = exe.totals
    unmatched = t.total_functions - t.matched_functions - t.partial_functions
    aria = (f"{exe.label}, one tick per game and thunk function in address order: "
            f"{t.matched_functions:,} matched, {t.partial_functions:,} partial, "
            f"{unmatched:,} unmatched")  # fmt: skip
    if t.assembler_functions:
        aria += f", {t.assembler_functions:,} assembler"
    ticks = sorted([(f.start, _tick_html(f)) for f in exe.functions]
                   + [(row.start, f'<i class="{ASSEMBLER_TICK}"></i>')
                      for row in exe.assembler_rows])  # fmt: skip
    return (f'<div class="strip" role="img" aria-label="{_xml(aria)}">'
            f'{"".join(tick for _start, tick in ticks)}</div>')


def _bar_html(percent: float) -> str:
    """The percent bar. A non-zero share's segment gets the `nz` class, whose 2 px minimum width
    keeps a tiny matched share visible (backlog 999.4 fix #3); the stated figure is unchanged."""
    nonzero = ' class="nz"' if percent > 0 else ""
    return (f'<div class="bar" aria-hidden="true"><span{nonzero} '
            f'style="width:{shield_message(percent)}"></span></div>')  # fmt: skip


def _tooltip_list_html(exe: ExeProgress) -> list[str]:
    """Every matched and partial function's tooltip as a text list, in address order, so keyboard
    and touch users reach what the strip's `title` attributes hold (backlog 999.4 fix #1). Empty
    when the EXE has none."""
    titles = [title for f in sorted(exe.functions, key=lambda f: f.start)
              if (title := _function_title(f)) is not None]  # fmt: skip
    if not titles:
        return []
    return [f"<details><summary>{TOOLTIP_LIST_SUMMARY} ({len(titles)})</summary><ul>",
            *(f"<li>{_xml(title)}</li>" for title in titles),
            "</ul></details>"]  # fmt: skip


def _exe_html(exe: ExeProgress) -> list[str]:
    """One EXE's section: its heading, then the percent bar, the figures in text, the function
    strip and the list of its matched and partial functions."""
    stem = _xml(exe.stem)
    return [f'<section class="exe" aria-labelledby="exe-{stem}">',
            f'<h2 id="exe-{stem}">{_xml(exe.label)}</h2>',
            "<div>",
            '<div class="line">',
            _bar_html(exe.totals.percent),
            f'<p class="figures">{_xml(_figures(exe))}</p>',
            "</div>",
            _strip_html(exe),
            *_tooltip_list_html(exe),
            "</div>",
            "</section>"]  # fmt: skip


def _legend_html() -> list[str]:
    """The mosaic's legend in HTML, one item per cell status in CELL_STATUSES order: it stays in
    view while the mosaic scrolls sideways on a phone (the SVG keeps its own legend, since
    progress.svg is also published alone)."""
    items = [f'<li><span class="swatch" style="background:{TREEMAP_COLORS[status]}" '
             f'aria-hidden="true"></span>{_xml(LEGEND_LABELS[status])}</li>'
             for status in CELL_STATUSES]  # fmt: skip
    return ['<ul class="legend">', *items, "</ul>"]


COVERAGE_HEADING = "Mechanics coverage"
COVERAGE_CAPTION = (
    "Each OpenApoc checklist item mapped to the original code, with two figures. Must match "
    "counts the functions the item needs, stopping at hub functions many items share; full "
    "closure counts every game or thunk function its call tree reaches. Hand-written assembly "
    "is in neither. A function two items share counts for both, and once for their tier. A "
    "tier reads matched only when status.csv says every must-match function is matched. The "
    "bar shows the must-match functions: matched, partial and unmatched.")
COVERAGE_EMPTY = "No checklist item is mapped to functions yet."


def _coverage_text(coverage: Coverage) -> str:
    return (f"{coverage.matched:,} of {coverage.functions:,} functions matched, "
            f"{coverage.partial:,} partial ({shield_message(coverage.percent)} of "
            f"{coverage.total_bytes:,} bytes matched)")  # fmt: skip


def _coverage_bar(coverage: Coverage) -> str:
    """The must-match bar: matched, partial and unmatched segments by function count, each
    non-zero one with the `nz` 2 px minimum; an empty set draws no segment."""
    parts = ((MATCHED, coverage.matched), (PARTIAL, coverage.partial),
             (UNMATCHED, coverage.unmatched))  # fmt: skip
    spans = "".join(f'<span class="{TICK_CLASSES[status]} nz" '
                    f'style="width:{shield_message(percent(count, coverage.functions))}"></span>'
                    for status, count in parts if count)  # fmt: skip
    return f'<div class="cov" aria-hidden="true">{spans}</div>'


def _figure_pair(must: Coverage, closure: Coverage) -> str:
    return f"must match {_coverage_text(must)}; full closure {_coverage_text(closure)}"


def _tier_state(tier: TierCoverage) -> str:
    return f"{tier.state}, {tier.sign_off}"


def _mechanics_html(mechanics: Mechanics | None) -> list[str]:
    """The `Mechanics coverage` section (DEC-05): the tiers, then one <li> per `in` item in
    (tier, issue, number) order, its text first and its bar after, then the duplicates, each
    once, by the item it duplicates. Issue numbers are text, never links (no OpenApoc contact
    in Milestone 1). Nothing without mechanics.toml."""
    if mechanics is None:
        return []
    lines = [f"<h2>{COVERAGE_HEADING}</h2>", f'<p class="caption">{_xml(COVERAGE_CAPTION)}</p>']
    if not mechanics.items:
        return [*lines, f"<p>{_xml(COVERAGE_EMPTY)}</p>"]
    tiers = {tier.id: tier for tier in mechanics.tiers}
    lines.append('<ul class="tiers">')
    lines += [f"<li>{_xml(f'Tier {t.id} ({t.title}): {_tier_state(t)}; ')}"
              f"{_xml(_figure_pair(t.must_match, t.full_closure))}."
              f"{_coverage_bar(t.must_match)}</li>" for t in mechanics.tiers]  # fmt: skip
    lines += ["</ul>", '<ul class="items">']
    lines += [f"<li>{_xml(f'#{i.id} {i.title}: ')}"
              f"{_xml(_figure_pair(i.must_match, i.full_closure))}. "
              f"{_xml(f'Tier {i.tier}: {_tier_state(tiers[i.tier])}.')}"
              f"{_coverage_bar(i.must_match)}</li>" for i in mechanics.items]  # fmt: skip
    lines.append("</ul>")
    if mechanics.duplicates:
        lines.append('<ul class="duplicates">')
        lines += [f"<li>{_xml(f'#{d.id} {d.title}: a duplicate of #{d.duplicate_of}')}</li>"
                  for d in mechanics.duplicates]  # fmt: skip
        lines.append("</ul>")
    return lines


TIMELINE_HEADING = "Progress over days"
# One line per EXE in EXES order: the dataviz reference palette's categorical slots 1 to 3 (blue,
# orange, aqua), light and dark, validated with its validate_palette.js on SURFACE and
# DARK_SURFACE: all pass; slot 3's light contrast is 2.74:1 (a warning), covered by the direct
# labels and the table. A slot is the EXE's, never its rank.
SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a")
DARK_SERIES_COLORS = ("#3987e5", "#d95926", "#199e70")
# The chart's own coordinates. At a 390 px phone the column is about 351 px, so the 400-unit
# viewBox draws its 13-unit text near 11.4 px; on a desktop it stops at CHART_MAX_WIDTH.
CHART_WIDTH, CHART_HEIGHT = 400, 240
CHART_FONT = 13
CHART_LEFT, CHART_RIGHT, CHART_TOP, CHART_BOTTOM = 44, 46, 26, 40  # margins around the plot
CHART_MAX_WIDTH = "32rem"
CHART_TICK_GAP = 6  # tick label to axis
CHART_LABEL_GAP = 14  # the least room between two direct labels at the right edge
CHART_DOT = 3.5  # a marker's radius
X_STEPS = (1, 2, 5, 7, 14, 30, 60, 91, 182, 365)  # day-axis tick steps, the first that fits
X_TICKS_MAX = 6
Y_INTERVALS = 4  # about this many grid intervals; the step rounds up to 1, 2, 2.5 or 5
_Y_MANTISSAS = (1.0, 2.0, 2.5, 5.0, 10.0)


def _short(label: str) -> str:
    return label.removesuffix(".EXE")


def _y_scale(top: float) -> tuple[float, int]:
    """(step, decimals) of the percent axis: a 1, 2, 2.5 or 5 step near top / Y_INTERVALS."""
    raw = top / Y_INTERVALS if top > 0 else 0.25
    magnitude = 10.0 ** math.floor(math.log10(raw))
    mantissa = next(m for m in _Y_MANTISSAS if m * magnitude >= raw * (1 - 1e-9))
    step = mantissa * magnitude
    decimals = max(0, -math.floor(math.log10(step) + 1e-9)) + (1 if mantissa == 2.5 else 0)
    return step, decimals


def _x_step(last: int) -> int:
    return next((s for s in X_STEPS if last / s <= X_TICKS_MAX), math.ceil(last / X_TICKS_MAX))


def _change(percent_value: float | None, delta: float | None) -> str:
    """A day's figure for the table and the tooltips: the percent and its change."""
    if percent_value is None:
        return "not started"
    shown = shield_message(percent_value)
    if delta is None:
        return f"{shown} (first day)"
    if delta == 0:
        return f"{shown} (no change)"
    return f"{shown} ({f'{delta:+.{PERCENT_DECIMALS}f}'.rstrip('0').rstrip('.')})"


def _series(timeline: Timeline) -> list[int]:
    """The EXE indexes that have a figure on some day."""
    return [i for i in range(len(timeline.labels))
            if any(d.percents[i] is not None for d in timeline.days)]  # fmt: skip


@dataclass(frozen=True)
class _Plot:
    """The chart's scales: x(day index) and y(percent) in viewBox units, and the percent axis
    as `intervals` steps of `step` from 0, labelled with `decimals` decimals."""

    last: int  # the last day's index, at least 1
    step: float
    intervals: int
    decimals: int

    def x(self, index: int) -> float:
        return CHART_LEFT + (CHART_WIDTH - CHART_LEFT - CHART_RIGHT) * index / self.last

    def y(self, value: float) -> float:
        height = CHART_HEIGHT - CHART_TOP - CHART_BOTTOM
        return CHART_TOP + height * (1 - value / (self.step * self.intervals))


def _plot(timeline: Timeline) -> _Plot:
    highest = max((p for d in timeline.days for p in d.percents if p is not None), default=0.0)
    step, decimals = _y_scale(highest)
    intervals = max(math.ceil(highest / step - 1e-9), 1)
    return _Plot(max(timeline.days[-1].index, 1), step, intervals, decimals)


def _axes_svg(timeline: Timeline, plot: _Plot) -> list[str]:
    """The axis title, the percent grid with its labels, the day ticks and the day axis title."""
    x, y, decimals = plot.x, plot.y, plot.decimals
    lines = [f'<text class="tl-axis" x="0" y="{CHART_FONT}">matched code, %</text>']
    for k in range(plot.intervals + 1):
        value = round(k * plot.step, 10)
        lines.append(f'<line class="tl-grid" x1="{CHART_LEFT}" x2="{CHART_WIDTH - CHART_RIGHT}" '
                     f'y1="{_num(y(value))}" y2="{_num(y(value))}"/>')
        lines.append(f'<text class="tl-axis" x="{CHART_LEFT - CHART_TICK_GAP}" '
                     f'y="{_num(y(value) + CHART_FONT / 3)}" text-anchor="end">'
                     f"{value:.{decimals}f}%</text>")  # fmt: skip
    last = timeline.days[-1].index
    base = CHART_HEIGHT - CHART_BOTTOM
    for index in range(0, last + 1, _x_step(last)):
        lines.append(f'<text class="tl-axis" x="{_num(x(index))}" '
                     f'y="{base + CHART_FONT + CHART_TICK_GAP}" text-anchor="middle">'
                     f"{index}</text>")  # fmt: skip
    lines.append(f'<text class="tl-axis" x="{_num((CHART_LEFT + CHART_WIDTH - CHART_RIGHT) / 2)}" '
                 f'y="{CHART_HEIGHT - 4}" text-anchor="middle">'
                 f"{_xml(f'days since the first commit, {timeline.days[0].date}')}</text>")
    return lines


def _line_svg(timeline: Timeline, i: int, plot: _Plot) -> list[str]:
    """EXE i's line, unbroken over the days it has a figure, and a marker per active day with
    the day's figure and driver as its tooltip."""
    x, y = plot.x, plot.y
    points, dots = [], []
    for day in timeline.days:
        value = day.percents[i]
        if value is None:
            continue
        points.append(f"{'L' if points else 'M'}{_num(x(day.index))},{_num(y(value))}")
        if not day.active:
            continue
        title = (f"Day {day.index}, {day.date}: {_short(timeline.labels[i])} "
                 f"{_change(value, day.deltas[i])}. {day.driver}")
        dots.append(f'<circle class="tl-dot s{i}" cx="{_num(x(day.index))}" '
                    f'cy="{_num(y(value))}" r="{CHART_DOT}"><title>{_xml(title)}</title></circle>')
    return [f'<path class="tl-line s{i}" d="{" ".join(points)}"/>', *dots]


def _end_labels_svg(timeline: Timeline, series: Sequence[int], plot: _Plot) -> list[str]:
    """Each line's short name at its last figure, right of the plot, pushed apart so two lines
    ending close together keep readable labels, and then back up from the plot's bottom so none
    lands on the day axis."""
    ends = sorted((plot.y(next(d.percents[i] for d in reversed(timeline.days)
                          if d.percents[i] is not None)), i) for i in series)  # fmt: skip
    placed: list[tuple[float, int]] = []
    for at, i in ends:
        if placed and at - placed[-1][0] < CHART_LABEL_GAP:
            at = placed[-1][0] + CHART_LABEL_GAP
        placed.append((at, i))
    limit = float(CHART_HEIGHT - CHART_BOTTOM)
    for k in reversed(range(len(placed))):
        at, i = placed[k]
        placed[k] = (min(at, limit), i)
        limit = placed[k][0] - CHART_LABEL_GAP
    x = CHART_WIDTH - CHART_RIGHT + CHART_TICK_GAP
    return [f'<text class="tl-name" x="{x}" y="{_num(at + CHART_FONT / 3)}">'
            f"{_xml(_short(timeline.labels[i]))}</text>" for at, i in placed]


def render_timeline_svg(timeline: Timeline) -> str:
    """The chart: matched percent (y, from 0) against days since the first commit (x), one line
    per EXE with a figure, a marker with a tooltip per active day, direct labels at the right;
    colours come from the page's rules (light and dark), so it is only drawn inline."""
    series = _series(timeline)
    plot = _plot(timeline)
    last = timeline.days[-1]
    figures = ", ".join(f"{timeline.labels[i]} {_change(last.percents[i], None).split(' (')[0]}"
                        for i in series)  # fmt: skip
    aria = (f"Matched code percent per EXE over the {last.index + 1} days since the first commit "
            f"on {timeline.days[0].date}; on {last.date}: {figures}. The table below holds the "
            "same data.")
    lines = [f'<svg class="tl-chart" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" role="img" '
             f'aria-label="{_xml(aria)}" font-size="{CHART_FONT}">',
             *_axes_svg(timeline, plot)]  # fmt: skip
    for i in series:
        lines += _line_svg(timeline, i, plot)
    lines += _end_labels_svg(timeline, series, plot)
    lines.append("</svg>")
    return "\n".join(lines)


def _timeline_css() -> list[str]:
    """The chart's and the day table's rules: series colours per scheme, recessive axes."""
    def colours(palette: Sequence[str]) -> str:
        return "".join(f".tl-line.s{i}{{stroke:{c}}}.tl-dot.s{i}{{fill:{c}}}"
                       f".tl-key.s{i}{{background:{c}}}" for i, c in enumerate(palette))

    return [
        ".tl{margin-top:.75rem}",
        f".tl svg{{display:block;width:100%;height:auto;max-width:{CHART_MAX_WIDTH}}}",
        ".tl-axis,.tl-name{fill:var(--secondary)}",
        ".tl-grid{stroke:var(--secondary);stroke-opacity:.25;stroke-width:1}",
        ".tl-line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}",
        ".tl-dot{stroke:var(--surface);stroke-width:1.5}",
        colours(SERIES_COLORS),
        f"@media (prefers-color-scheme: dark){{{colours(DARK_SERIES_COLORS)}}}",
        ".days{width:100%;border-collapse:collapse;margin-top:.5rem;font-size:.875rem;"
        "font-variant-numeric:tabular-nums}",
        ".days th,.days td{padding:0 .75rem .25rem 0;text-align:left;vertical-align:top}",
        ".days thead th{font-weight:600}",
        ".days tbody th{font-weight:400;white-space:nowrap}",
        ".days .fig>*{padding-top:.75rem}",
        ".days .what{overflow-wrap:anywhere}",
    ]


def _days_table_html(timeline: Timeline) -> list[str]:
    """The chart's data as a table, newest day first. A day is two rows under its Day header:
    the EXE figures, then the driver and summary across the EXE columns, so at 390 px the
    figures keep their width instead of yielding it to a long summary column."""
    active = [d for d in reversed(timeline.days) if d.active]
    head = "".join(f'<th scope="col">{_xml(label)}</th>' for label in timeline.labels)
    rows = []
    for d in active:
        figures = "".join(f"<td>{_xml(_change(p, delta))}</td>"
                          for p, delta in zip(d.percents, d.deltas, strict=True))  # fmt: skip
        rows += [f'<tr class="fig"><th scope="row" rowspan="2">Day {d.index}<br>{_xml(d.date)}'
                 f"</th>{figures}</tr>",
                 f'<tr><td class="what" colspan="{len(timeline.labels)}"><strong>'
                 f"{_xml(d.driver)}</strong><br>{_xml(d.summary)}</td></tr>"]  # fmt: skip
    return [f"<details><summary>Day by day ({len(active)} days with commits, runs or "
            "learnings, newest first)</summary>",
            '<table class="days">',
            f'<thead><tr><th scope="col">Day</th>{head}</tr></thead>',
            "<tbody>", *rows, "</tbody>", "</table>", "</details>"]  # fmt: skip


TIMELINE_CAPTION = (
    "Matched code per EXE at the end of each day since the first commit, re-derived from the "
    "history of each EXE's status, functions and units tables the way the figures above are "
    "(a change counts on the day it reached main). Each marker's tooltip and the table name the "
    "day's biggest driver; the table also sums what the day did: match commits by co-author, "
    "flags approvals, drive runs, tooling and plan commits, and learnings.")


def _timeline_html(timeline: Timeline | None) -> list[str]:
    """The `Progress over days` section: the chart, its legend and the day table, or the note
    alone when the history cannot be read; nothing without a timeline."""
    if timeline is None:
        return []
    lines = ['<section class="timeline" aria-labelledby="timeline">',
             f'<h2 id="timeline">{TIMELINE_HEADING}</h2>']
    if not timeline.days:
        return [*lines, f'<p class="caption">{_xml(timeline.note)}</p>', "</section>"]
    keys = [f'<li><span class="swatch tl-key s{i}" aria-hidden="true"></span>'
            f"{_xml(timeline.labels[i])}</li>" for i in _series(timeline)]  # fmt: skip
    return [*lines, f'<p class="caption">{_xml(TIMELINE_CAPTION)}</p>',
            '<ul class="legend">', *keys, "</ul>",
            '<div class="tl">', render_timeline_svg(timeline), "</div>",
            *_days_table_html(timeline), "</section>"]  # fmt: skip


def render_html(progress: Progress, commit: str | None = None,
                mechanics: Mechanics | None = None,
                timeline: Timeline | None = None) -> str:  # fmt: skip
    """The progress page, written as index.html (owner rulings 3 and 4, 2026-10-26): per EXE a
    heading, a percent bar, the figures in text and the function strip (one tick per game and
    thunk function in address order; matched and partial ticks stand taller and carry the mosaic
    cell's tooltip, a partial one with its best score;
    the strip wraps with the width) and those tooltips again as a text list in a <details>, then
    the strip's key, an HTML legend, the labelled mosaic
    (render_svg's output, verbatim, in a focusable box) and how the figures are measured. Under
    prefers-color-scheme: dark only the surface, ink and secondary swap (the mosaic follows
    through MOSAIC_PAINTS; status hues are unchanged); below 40rem the EXE heading stacks over its
    bar and the mosaic keeps a 48rem width and scrolls sideways. Inline CSS only, no script and
    no external request: every link is relative or to the repository. The same CSVs and commit
    give the same bytes; without a commit only the "Updated from commit" line is missing. Given
    `mechanics` (derive_mechanics), the `Mechanics coverage` section follows the strip's key;
    without it the page has no such section and no rule of it. Signed asm rows that
    exclude_assembler moved out are stated per EXE, drawn as assembler ticks and library cells,
    and keyed under the strip's key (D-23)."""
    assembler = any(exe.assembler_rows for exe in progress.exes)
    lines = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<meta name="color-scheme" content="light dark">',
             f"<title>{_xml(PAGE_TITLE)}</title>", "<style>",
             _page_css(coverage=mechanics is not None, assembler=assembler,
                       timeline=timeline is not None and bool(timeline.days)), "</style>",
             "</head>", "<body>", "<main>", f"<h1>{_xml(PAGE_HEADING)}</h1>"]  # fmt: skip
    if commit is not None:
        lines.append(f'<p class="meta">Updated from commit <a href="{_xml(COMMIT_URL + commit)}">'
                     f"{_xml(commit[:COMMIT_SHORT])}</a></p>")  # fmt: skip
    for exe in progress.exes:
        lines += _exe_html(exe)
    lines += [STRIP_KEY,
              *([ASSEMBLER_KEY] if assembler else []),
              *_mechanics_html(mechanics),
              *_timeline_html(timeline),
              "<h2>The mosaic</h2>",
              '<p class="caption">One cell per function, grouped by EXE and unit and sized by '
              "bytes; large units carry their name.</p>",
              *_legend_html(), MOSAIC_REGION, render_svg(progress).removesuffix("\n"), "</div>",
              "<h2>How it is measured</h2>", *(f"<p>{text}</p>" for text in MEASURED),
              "</main>", "</body>", "</html>"]  # fmt: skip
    return "\n".join(lines) + "\n"


def write_html(progress: Progress, path: Path, commit: str | None = None,
               mechanics: Mechanics | None = None,
               timeline: Timeline | None = None) -> None:  # fmt: skip
    _write_atomic(path, render_html(progress, commit, mechanics, timeline).encode("utf-8"))


# ---- command line ----


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="progress.py", description=__doc__.splitlines()[0])
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                   help="the config tree (default: %(default)s)")  # fmt: skip
    p.add_argument("--out", type=Path,
                   help="write progress.json, progress-shield.json, one "
                        "progress-shield-<stem>.json per EXE, progress.svg and the progress "
                        "page as index.html here")
    p.add_argument("--report", type=Path, help="write objdiff's report.json here (D-28)")
    p.add_argument("--decomphub", type=Path,
                   help="write the DecompHub progress-v1 feed here (D-29)")  # fmt: skip
    p.add_argument("--commit", help="the commit the figures come from, recorded in progress.json")
    return p


@dataclass(frozen=True)
class _Derived:
    """What main derives once: derive's progress (the DecompHub feed's, as gate writes it), the
    same with the signed asm rows moved out (every other output, D-23), the coverage view
    (None without mechanics.toml) and the timeline (None outside a checkout or without --out)."""

    progress: Progress
    shown: Progress
    mechanics: Mechanics | None
    timeline: Timeline | None = None


Writer = Callable[[_Derived, Path], None]


def _on_shown(write: Callable[[Progress, Path], None]) -> Writer:
    return lambda derived, path: write(derived.shown, path)


def _writes(args: argparse.Namespace) -> Iterable[tuple[Path, Writer]]:
    """(path, writer) for every output the arguments ask for."""
    if args.out is not None:
        yield args.out / PROGRESS_JSON, lambda d, path: write_progress_json(
            d.shown, path, args.commit, d.mechanics)
        yield args.out / SHIELD_JSON, _on_shown(write_shield)
        for stem, _label in EXES:  # EXES, not the derived progress: this runs before derive
            yield (args.out / EXE_SHIELD_JSON.format(stem=stem),
                   _on_shown(functools.partial(write_exe_shield, stem=stem)))
        yield args.out / PROGRESS_SVG, _on_shown(write_svg)
        yield args.out / INDEX_HTML, lambda d, path: write_html(
            d.shown, path, args.commit, d.mechanics, d.timeline)
    if args.report is not None:
        yield args.report, _on_shown(write_report)
    if args.decomphub is not None:
        # gate writes this feed from derive() alone (T-07-44): the asm list never changes it.
        yield args.decomphub, lambda d, path: write_decomphub(d.progress, path)


HISTORY_FAILED_NOTE = ("The chart is left out: the repository history could not be read; the "
                       "log of the run that built this page says why.")  # fmt: skip


def _timeline(config: Path, mechanics: Mechanics | None) -> Timeline | None:
    """The timeline of the checkout holding `config`. A history the walk cannot read leaves the
    chart out with a note on the page and a warning on stderr; the page is still written."""
    asm = mechanics.assembler if mechanics else ()
    try:
        return load_timeline(Path(config).resolve().parent, asm)
    except ProgressError as exc:
        print(f"progress.py: warning: the progress-over-days chart is left out: {exc}",
              file=sys.stderr)  # fmt: skip
        return Timeline(tuple(label for _stem, label in EXES), note=HISTORY_FAILED_NOTE)


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
        found = derive_mechanics(args.config, progress)
        shown = exclude_assembler(progress, found.assembler) if found else progress
        timeline = _timeline(args.config, found) if args.out is not None else None
        derived = _Derived(progress, shown, found, timeline)
        for path, write in writes:
            path.parent.mkdir(parents=True, exist_ok=True)  # ruling F17
            write(derived, path)
    except (ProgressError, OSError) as exc:
        print(f"progress.py: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
