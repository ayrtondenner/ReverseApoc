"""Per-unit cflags proposals: the owner-approval queue of D-12 (plan 07-17).

A sweep hit of a driver attempt (`attempt check --sweep`, D-17/D-15) is a 100% cell under flags
other than its unit's rule. It is never a match and never evidence for the `*` default (D-28, D-33):
`flags propose` turns it into a proposed per-unit rule in the committed review queue
config/cflags-proposals.toml, with the C that hit copied to build/flags/<id>/<unit>.c (gitignored).
`flags regate` re-proves it over the whole unit on a copy, and `flags list` shows the queue.
Nothing here writes config/cflags.txt or src/; only the owner's approve step (plan 07-24) does.

The queue holds no game bytes: names, flag strings, repo-relative paths under build/, percents,
SHA-256 hex and dates, all printable ASCII. It is written only by `write_queue`, in a fixed key
order, through write_atomic, and read back with tomllib. Its format, `version = 1` then one
`[[proposal]]` table per proposal with the keys of `Proposal` in field order:

- id, exe, unit, glob, rule, base: what is proposed (glob is always src/<exe>/<unit>.c).
- functions, keeps: the functions that hit under `rule`; the unit's matched functions.
- siblings (D-32, fix round 1): every other game and thunk row of the unit, each
  `<name> <status> <percent>` from status.csv (`matched`/`partial`) or `<name> unattempted`.
  The rule binds them all, so the owner's approval covers them knowingly.
- alternatives, source, candidate, candidate_sha256, evidence: the other rules every function hit
  under, sweep | sweep2 | owner, the C that hit (build/flags/<id>/<unit>.c) and its LF sha256,
  the hits' checks/NNNN.json paths.
- status, regate_exit, regate_variant, regate_cflags_sha256, regate_log: the review state and the
  last re-gate (exit -1 and variant `empty` before one).
- approved_by, approved_date, reason: the owner's approval (07-24) and why a proposal failed.
- variant_sha256, reverted (fix round 1): set only when a re-gate passed on D-28's reduced
  variant. `reverted` names the co-defined functions turned back into INCLUDE_ASM, and
  `variant_sha256` is the LF sha256 of that C, written to build/flags/<id>/<unit>.reduced.c
  (`variant_path`). Approve lands that file, not the candidate. Both are empty when the full
  candidate passed or no re-gate passed.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import tomllib
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import check, contextpack, driver, gate
from .cflags import DEFAULT_CFLAGS, CflagsError, load_cflags, parse_cflags, select_rule
from .check import unit_rule_path
from .fileio import write_atomic
from .functions import (
    KIND_GAME,
    KIND_THUNK,
    FunctionRow,
    read_functions_csv,
    read_symbols_csv,
)
from .status import MATCHED, format_percent, lf_sha256, read_status, status_path
from .targets import load_manifest
from .watcom import DEFAULT_WATCOM_MANIFEST, load_watcom_manifest

QUEUE = Path("config/cflags-proposals.toml")
QUEUE_VERSION = 1
QUEUE_HEADER = (
    "# config/cflags-proposals.toml: proposed per-unit cflags rules (D-12). Written only by\n"
    "# `reverseapoc flags`; config/cflags.txt changes only through the owner's `flags approve`.\n"
)
PROPOSED, REGATED, FAILED = "proposed", "regated", "failed"
APPROVED, LANDED, REJECTED, SUPERSEDED = "approved", "landed", "rejected", "superseded"
STATUSES = (PROPOSED, REGATED, FAILED, APPROVED, LANDED, REJECTED, SUPERSEDED)
OPEN_STATUSES = (PROPOSED, REGATED, FAILED)  # a unit has at most one; a new hit merges into it
SWEEP, SWEEP2, OWNER = "sweep", "sweep2", "owner"
SOURCES = (SWEEP, SWEEP2, OWNER)
AS_WRITTEN, REDUCED, EMPTY = "as-written", "reduced", "empty"
VARIANTS = (AS_WRITTEN, REDUCED, EMPTY)  # EMPTY: no re-gate has run
NOT_RUN = -1  # regate_exit before a re-gate
EXES = ("ufo2p", "tacp")
FLAGS_DIR = Path("build") / "flags"
DRIVER_DIR = Path("build") / "driver"
CHECKS_LOG = "checks.jsonl"  # attempt.CHECK_LOG
MEASURED = "measured"  # a sweep cell's status once compiled and diffed
PERFECT = 100.0
_ID = re.compile(r"F-([0-9]{4})")
_UNIT = re.compile(r"[a-z0-9_]+")
_C_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FUNC = re.compile(r"func_([0-9A-F]{8})")
_SPEC = re.compile(r"wcc386@[0-9][0-9.]*( -[A-Za-z0-9_=.+]+)*")
UNATTEMPTED = "unattempted"  # a sibling with no status.csv row
_SIBLING = re.compile(r"[A-Za-z_][A-Za-z0-9_]* "
                      r"(unattempted|(matched|partial) (0|[1-9][0-9]{0,2})\.[0-9]{2})")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_RUN = re.compile(r"[A-Za-z0-9_.-]+")
_ATTEMPT = re.compile(r"attempt-([0-9]+)")
_SOURCE = re.compile(r"checks/[0-9]{4}\.c")  # attempt.CheckLogLine.source
_PRINTABLE = re.compile(r"[\x20-\x7e]*")
_HEX = 16


class FlagsError(ValueError):
    """The proposal queue or an attempt directory is malformed, or a flags verb is refused."""


@dataclass(frozen=True)
class Proposal:
    """One [[proposal]] of the queue (D-12), its fields in the file's fixed order."""

    id: str  # F-nnnn: sequential, never reused
    exe: str
    unit: str
    glob: str  # always the exact unit path src/<exe>/<unit>.c
    rule: str  # what follows the glob in cflags.txt: `wcc386@10.6 -4r -ot -s -fpi`
    base: str  # the unit's committed rule when proposed
    functions: tuple[str, ...]  # functions that hit under `rule`
    keeps: tuple[str, ...]  # matched functions of the unit the re-gate must keep matched
    siblings: tuple[str, ...]  # every other game/thunk row: `<name> <status> <pct>`|`unattempted`
    alternatives: tuple[str, ...]  # other rules every function hit under, best first
    source: str  # sweep | sweep2 | owner
    candidate: str  # build/flags/<id>/<unit>.c, the C that hit (gitignored)
    candidate_sha256: str  # of the candidate's text with CRLF read as LF
    evidence: tuple[str, ...]  # the hits' checks/NNNN.json paths under build/
    status: str
    regate_exit: int  # NOT_RUN, else the re-gate's exit code
    regate_variant: str  # as-written | reduced | empty
    regate_cflags_sha256: str  # sha of the committed cflags.txt the re-gate was built on
    regate_log: str  # build/flags/<id>/regate.json
    approved_by: str
    approved_date: str
    reason: str  # why it failed or was rejected
    variant_sha256: str  # the reduced variant that passed (variant_path), else ""
    reverted: tuple[str, ...]  # functions that variant returned to INCLUDE_ASM, else ()

    def to_json(self) -> dict[str, Any]:
        return {key: list(value) if isinstance(value, tuple) else value
                for key, value in dataclasses.asdict(self).items()}  # fmt: skip

    def line(self) -> str:
        regate = "not re-gated" if self.regate_exit == NOT_RUN else (
            f"re-gate exit {self.regate_exit} ({self.regate_variant})")  # fmt: skip
        lines = [f"{self.id}  {self.status}  {self.exe}/{self.unit}  {', '.join(self.functions)}",
                 f"  rule {self.rule or '(none)'}  (base {self.base}; {regate}; {self.source})"]
        lines += [f"  alternative {rule}" for rule in self.alternatives]
        lines += [f"  keeps {name}" for name in self.keeps]
        lines += [f"  sibling {text}" for text in self.siblings]
        lines += [f"  evidence {path}" for path in self.evidence]
        lines.append(f"  candidate {self.candidate}")
        if self.reverted:
            lines.append(f"  WARNING the re-gate passed only with {', '.join(self.reverted)} "
                         f"returned to INCLUDE_ASM: approving lands {variant_path(self)}, "
                         "not the candidate")  # fmt: skip
        if self.reason:
            lines.append(f"  reason {self.reason}")
        return "\n".join(lines)


FIELDS = tuple(f.name for f in dataclasses.fields(Proposal))
_LIST_FIELDS = ("functions", "keeps", "siblings", "alternatives", "evidence", "reverted")
_INT_FIELDS = ("regate_exit",)


# ---- the queue file ----


def _printable(value: str, where: str) -> str:
    if not _PRINTABLE.fullmatch(value):
        raise FlagsError(f"{where}: {value!r} is not printable ASCII (the queue is ASCII only)")
    return value


def _build_path(value: str) -> bool:
    """A repo-relative POSIX path under build/ with no `.`/`..` part."""
    parts = value.split("/")
    return parts[0] == "build" and len(parts) > 1 and all(p not in ("", ".", "..") for p in parts)


def _field_problem(p: Proposal) -> str | None:
    """Why `p` cannot be in the queue, or None."""
    checks = {
        "id": _ID.fullmatch(p.id) is not None,
        "exe": p.exe in EXES,
        "unit": _UNIT.fullmatch(p.unit) is not None,
        "glob": p.glob == unit_rule_path(p.exe, p.unit),
        "rule": p.rule == "" or _SPEC.fullmatch(p.rule) is not None,
        "base": _SPEC.fullmatch(p.base) is not None,
        "functions": all(_C_NAME.fullmatch(name) for name in p.functions),
        "keeps": all(_C_NAME.fullmatch(name) for name in p.keeps),
        "siblings": all(_SIBLING.fullmatch(text) for text in p.siblings),
        "alternatives": all(_SPEC.fullmatch(rule) for rule in p.alternatives),
        "source": p.source in SOURCES,
        "candidate": p.candidate == (FLAGS_DIR / p.id / f"{p.unit}.c").as_posix(),
        "candidate_sha256": _SHA256.fullmatch(p.candidate_sha256) is not None,
        "evidence": all(_build_path(path) for path in p.evidence),
        "status": p.status in STATUSES,
        "regate_exit": p.regate_exit >= NOT_RUN,
        "regate_variant": p.regate_variant in VARIANTS,
        "regate_cflags_sha256": p.regate_cflags_sha256 == ""
        or _SHA256.fullmatch(p.regate_cflags_sha256) is not None,
        "regate_log": p.regate_log in ("", (FLAGS_DIR / p.id / "regate.json").as_posix()),
        "variant_sha256": p.variant_sha256 == ""
        or _SHA256.fullmatch(p.variant_sha256) is not None,
        "reverted": all(_C_NAME.fullmatch(name) for name in p.reverted)
        and (p.variant_sha256 == "") == (not p.reverted),
        "approved_date": p.approved_date == "" or _DATE.fullmatch(p.approved_date) is not None,
    }
    bad = [key for key, ok in checks.items() if not ok]
    return f"{p.id}: bad value for {', '.join(bad)}" if bad else None


def _check_queue(proposals: Sequence[Proposal], where: str) -> None:
    seen: set[str] = set()
    open_units: dict[tuple[str, str], str] = {}
    for p in proposals:
        for key in FIELDS:
            value = getattr(p, key)
            for text in value if isinstance(value, tuple) else (value,):
                if isinstance(text, str):
                    _printable(text, f"{where}: {p.id}.{key}")
        problem = _field_problem(p)
        if problem:
            raise FlagsError(f"{where}: {problem}")
        if p.id in seen:
            raise FlagsError(f"{where}: {p.id} appears twice")
        seen.add(p.id)
        if p.status in OPEN_STATUSES:
            other = open_units.setdefault((p.exe, p.unit), p.id)
            if other != p.id:
                raise FlagsError(f"{where}: {other} and {p.id} are both open for "
                                 f"{p.exe}/{p.unit}")  # fmt: skip


def _proposal(table: object, where: str) -> Proposal:
    if not isinstance(table, dict) or set(table) != set(FIELDS):
        keys = sorted(table) if isinstance(table, dict) else type(table).__name__
        raise FlagsError(f"{where}: a [[proposal]] has exactly the keys {', '.join(FIELDS)}, "
                         f"got {keys}")  # fmt: skip
    values: dict[str, Any] = {}
    for key in FIELDS:
        value = table[key]
        if key in _LIST_FIELDS:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise FlagsError(f"{where}: {key} is a list of strings")
            value = tuple(value)
        elif key in _INT_FIELDS:
            if type(value) is not int:
                raise FlagsError(f"{where}: {key} is an integer")
        elif not isinstance(value, str):
            raise FlagsError(f"{where}: {key} is a string")
        values[key] = value
    return Proposal(**values)


def read_queue(path: Path) -> list[Proposal]:
    """The queue's proposals in file order; [] when the file does not exist."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        doc = tomllib.loads(path.read_bytes().decode("ascii"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise FlagsError(f"{path}: {exc}") from None
    if set(doc) - {"version", "proposal"} or doc.get("version") != QUEUE_VERSION:
        raise FlagsError(f"{path}: expected `version = {QUEUE_VERSION}` and [[proposal]] "
                         "tables only")  # fmt: skip
    tables = doc.get("proposal", [])
    if not isinstance(tables, list):
        raise FlagsError(f"{path}: `proposal` is an array of tables")
    proposals = [_proposal(table, str(path)) for table in tables]
    _check_queue(proposals, str(path))
    return proposals


def _toml_value(value: str | int | tuple[str, ...]) -> str:
    """A TOML value: a string through json.dumps (valid TOML for printable ASCII), an int, or
    an inline array of strings."""
    if isinstance(value, tuple):
        return "[" + ", ".join(json.dumps(item) for item in value) + "]"
    if isinstance(value, int):
        return str(value)
    return json.dumps(value)


def format_queue(proposals: Sequence[Proposal]) -> str:
    """The queue's text: the header, `version`, then each proposal's keys in FIELDS order."""
    _check_queue(proposals, str(QUEUE))
    parts = [QUEUE_HEADER, f"version = {QUEUE_VERSION}\n"]
    for p in proposals:
        parts.append("\n[[proposal]]\n")
        parts += [f"{key} = {_toml_value(getattr(p, key))}\n" for key in FIELDS]
    return "".join(parts)


def write_queue(path: Path, proposals: Sequence[Proposal]) -> None:
    """Write the queue whole (write_atomic); a proposal that fails validation writes nothing."""
    text = format_queue(proposals)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_atomic(Path(path), text.encode("ascii"))


# ---- the D-16 pilot list ----


def pilot_hits(log: Path) -> list[tuple[str, str]]:
    """(exe, function) of every function with an attempt record holding a sweep_hit and no
    MATCHED attempt record, sorted by (exe, start). Read from attempts.jsonl alone (D-16, ruling
    F15): status.csv is not consulted, so the list does not change when the owner approves."""
    hits: dict[tuple[str, int], str] = {}
    matched: set[tuple[str, int]] = set()
    text = Path(log).read_text(encoding="utf-8")
    for number, raw in enumerate(text.splitlines(), start=1):
        try:
            record = json.loads(raw)
            driver.validate_record(record)
        except ValueError as exc:  # json and RecordError
            raise FlagsError(f"{log} line {number}: {exc}") from None
        if record["kind"] != driver.KIND_ATTEMPT:
            continue
        key = (record["exe"], int(record["start"], _HEX))
        if record["outcome"] == driver.MATCHED:
            matched.add(key)
        if record["check"]["sweep_hit"]:
            hits[key] = record["function"]
    return [(exe, hits[(exe, start)]) for exe, start in sorted(set(hits) - matched)]


# ---- reading attempts ----


@dataclass(frozen=True)
class Hit:
    """One sweep line whose cells hold a 100% cell under flags other than the unit's rule."""

    exe: str
    unit: str
    function: str
    start: int
    snapshot: Path  # the attempt's checks/NNNN.c: the C that hit (D-28)
    evidence: str  # its checks/NNNN.json, repo-relative POSIX
    cells: tuple[tuple[int, str], ...]  # (cell number, spec) at 100%, best first
    source: str  # sweep (a stage-1 cell hit) or sweep2 (only a stage-2 cell did)

    @property
    def specs(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(spec for _, spec in self.cells))


def _cell_spec(cell: Mapping[str, Any]) -> str:
    return " ".join([str(cell["compiler"]), *map(str, cell["flags"])])


def _perfect(cell: Mapping[str, Any], base: str) -> bool:
    """attempt._is_hit: objdiff 100, relocations ok, no differing byte, not the unit's rule."""
    measured = cell.get("status") == MEASURED and cell.get("objdiff_percent") == PERFECT
    ok = measured and cell.get("reloc_ok") is True and cell.get("differing") == 0
    return ok and _cell_spec(cell) != base


def _flag_count(spec: str) -> int:
    return len(spec.split()) - 1  # the fields after `wcc386@<version>`


def _cells_100(doc: Mapping[str, Any], base: str) -> tuple[tuple[tuple[int, str], ...], str]:
    """The 100% cells of a sweep's JSON over stage 1 and the D-15 stage 2 as (number, spec),
    ranked by the number of flags, then the cell number (DEC-03 ordering), and the hit's
    source: sweep when a stage-1 cell hit, else sweep2."""
    stage2 = doc.get("stage2")
    later = stage2["cells"] if isinstance(stage2, Mapping) else []
    first = [(int(c["cell"]), _cell_spec(c)) for c in doc["cells"] if _perfect(c, base)]
    second = [(int(c["cell"]), _cell_spec(c)) for c in later if _perfect(c, base)]
    ranked = sorted([*first, *second], key=lambda c: (_flag_count(c[1]), c[0]))
    return tuple(ranked), SWEEP if first else SWEEP2


def _sweep_lines(attempt_dir: Path) -> Iterator[str]:
    """The `source` of every sweep line of the attempt's checks.jsonl."""
    log = attempt_dir / CHECKS_LOG
    if not log.is_file():
        return
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        source = line.get("source") if isinstance(line, dict) else None
        if line.get("sweep") is True and isinstance(source, str) and _SOURCE.fullmatch(source):
            yield source


def _attempt_dirs(run_dir: Path) -> Iterator[tuple[str, str, Path]]:
    """(exe, function, attempt dir) under a run directory, in a stable order."""
    for exe in EXES:
        exe_dir = run_dir / exe
        functions = sorted(exe_dir.iterdir()) if exe_dir.is_dir() else []
        for fdir in functions:
            if not fdir.is_dir() or not _C_NAME.fullmatch(fdir.name):
                continue
            attempts = [(int(m.group(1)), d) for d in fdir.iterdir()
                        if d.is_dir() and (m := _ATTEMPT.fullmatch(d.name))]  # fmt: skip
            for _, attempt_dir in sorted(attempts):
                yield exe, fdir.name, attempt_dir


def _run_dirs(repo: Path, runs: Sequence[str]) -> list[Path]:
    """build/driver/<RUN> for each RUN, or every run directory when none is named."""
    root = repo / DRIVER_DIR
    if not runs:
        return sorted(d for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
    out = []
    for run in runs:
        path = root / run
        if not _RUN.fullmatch(run) or run in (".", "..") or not path.is_dir():
            raise FlagsError(f"no driver run {run!r} under {root}")
        out.append(path)
    return out


class _Context:
    """What propose reads once: the committed rules, the status tables, functions.csv names."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.config = repo / "config"
        watcom = self.config / "watcom.toml"
        versions_from = watcom if watcom.is_file() else DEFAULT_WATCOM_MANIFEST
        self.rules = load_cflags(self.config / "cflags.txt",
                                 versions=tuple(load_watcom_manifest(versions_from)))  # fmt: skip
        self.status = {exe: self._status(exe) for exe in EXES}
        self._rows: dict[str, list[FunctionRow]] = {}

    def _status(self, exe: str) -> list:
        path = status_path(self.config, exe)
        return read_status(path) if path.is_file() else []

    def rows(self, exe: str) -> list[FunctionRow]:
        """functions.csv's rows of `exe`, each named as symbols.csv names its start now (the
        name gate writes to status.csv); [] when the EXE has no functions.csv."""
        if exe not in self._rows:
            path = self.config / exe / "functions.csv"
            rows = read_functions_csv(path) if path.is_file() else []
            symbols = read_symbols_csv(self.config / exe / "symbols.csv")
            renames = {s.address: s.name for s in symbols if s.kind == gate.FUNC_SYMBOL}
            self._rows[exe] = [dataclasses.replace(row, name=renames.get(row.start, row.name))
                               for row in rows]  # fmt: skip
        return self._rows[exe]

    def base(self, exe: str, unit: str) -> str:
        rule = select_rule(self.rules, unit_rule_path(exe, unit))
        return " ".join([rule.spec, *rule.flags])

    def start(self, exe: str, function: str) -> int | None:
        found = _FUNC.fullmatch(function)
        if found:
            return int(found.group(1), _HEX)
        return next((row.start for row in self.rows(exe) if row.name == function), None)

    def matched(self, exe: str, start: int, function: str) -> bool:
        return any(row.status == MATCHED and (row.start == start or row.name == function)
                   for row in self.status[exe])  # fmt: skip

    def keeps(self, exe: str, unit: str) -> tuple[str, ...]:
        return tuple(row.name for row in self.status[exe]
                     if row.unit == unit and row.status == MATCHED)  # fmt: skip

    def siblings(self, exe: str, unit: str, functions: Iterable[str]) -> tuple[str, ...]:
        """Every game and thunk row of the unit other than `functions`, by start (D-32, fix
        round 1): `<name> <status> <percent>` from status.csv, or `<name> unattempted`. The
        rule binds them all, so the owner's approval covers them knowingly. Without a
        functions.csv the unit's status.csv rows stand in."""
        skip = set(functions)
        status = {row.start: row for row in self.status[exe]}
        names = {row.start: row.name for row in self.rows(exe)
                 if row.unit == unit and row.kind in (KIND_GAME, KIND_THUNK)}  # fmt: skip
        if not self.rows(exe):
            names = {row.start: row.name for row in self.status[exe] if row.unit == unit}
        out = []
        for start, name in sorted(names.items()):
            row = status.get(start)
            if name in skip or (row is not None and row.name in skip):
                continue
            out.append(f"{name} {UNATTEMPTED}" if row is None
                       else f"{name} {row.status} {format_percent(row.best_percent)}")
        return tuple(out)


REDUCED_SUFFIX = ".reduced.c"  # the reduced variant a re-gate passed on, next to the candidate


def variant_path(p: Proposal) -> str:
    """build/flags/<id>/<unit>.reduced.c: where a re-gate that passed on the reduced variant
    leaves that C (variant_sha256 is its LF sha256); approve lands it instead of the
    candidate."""
    return (FLAGS_DIR / p.id / f"{p.unit}{REDUCED_SUFFIX}").as_posix()


def _relative(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def _hit(ctx: _Context, exe: str, function: str, attempt_dir: Path, source: str,
         notes: list[str]) -> Hit | None:  # fmt: skip
    """The hit of one sweep line, or None (a line without a 100% cell, or a note why not)."""
    evidence = attempt_dir / Path(source).with_suffix(".json")
    where = _relative(ctx.repo, evidence)
    try:
        doc = json.loads(evidence.read_text(encoding="utf-8"))
        unit = doc["unit"]
        if doc["exe"] != exe or doc["function"] != function or not _UNIT.fullmatch(unit):
            notes.append(f"{where}: names {doc['exe']}/{unit} {doc['function']}, not its "
                         f"directory's {exe} {function}")  # fmt: skip
            return None
        cells, kind = _cells_100(doc, ctx.base(exe, unit))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        notes.append(f"{where}: unreadable sweep JSON ({type(exc).__name__}: {exc})")
        return None
    if not cells:
        return None
    start = ctx.start(exe, function)
    if start is None:
        notes.append(f"{where}: {function} is no functions.csv row of {exe}")
        return None
    snapshot = attempt_dir / source
    return Hit(exe, unit, function, start, snapshot, where, cells, kind)


def find_hits(repo: Path, runs: Sequence[str], ctx: _Context | None = None
              ) -> tuple[list[Hit], list[str]]:  # fmt: skip
    """Every sweep hit of the named runs' attempts (all runs when none is named), sorted by
    (exe, start) and then in the order found, and the notes on lines that could not be read."""
    repo = Path(repo)
    ctx = ctx or _Context(repo)
    hits: list[Hit] = []
    notes: list[str] = []
    for run_dir in _run_dirs(repo, runs):
        for exe, function, attempt_dir in _attempt_dirs(run_dir):
            for source in _sweep_lines(attempt_dir):
                hit = _hit(ctx, exe, function, attempt_dir, source, notes)
                if hit is not None:
                    hits.append(hit)
    order = {id(hit): n for n, hit in enumerate(hits)}
    return sorted(hits, key=lambda h: (h.exe, h.start, order[id(h)])), notes


# ---- propose ----


@dataclass(frozen=True)
class ProposeReport:
    added: tuple[str, ...] = ()
    merged: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    proposals: tuple[Proposal, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {"added": list(self.added), "merged": list(self.merged),
                "skipped": list(self.skipped),
                "proposals": [p.to_json() for p in self.proposals]}  # fmt: skip

    def format(self) -> str:
        lines = [f"added {pid}" for pid in self.added]
        lines += [f"merged into {pid}" for pid in self.merged]
        lines += [f"skipped {text}" for text in self.skipped]
        return "\n".join(lines or ["no new sweep hit: the queue is unchanged"])


def _next_id(proposals: Iterable[Proposal]) -> str:
    numbers = [int(m.group(1)) for p in proposals if (m := _ID.fullmatch(p.id))]
    return f"F-{max(numbers, default=0) + 1:04d}"


def _candidate(repo: Path, pid: str, hit: Hit) -> tuple[str, str]:
    """Copy the C that hit to build/flags/<id>/<unit>.c: (its path, its LF sha256)."""
    data = hit.snapshot.read_bytes()
    try:
        sha = lf_sha256(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise FlagsError(f"{hit.snapshot}: not UTF-8 ({exc})") from None
    rel = FLAGS_DIR / pid / f"{hit.unit}.c"
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    write_atomic(repo / rel, data)
    return rel.as_posix(), sha


def _new_proposal(repo: Path, ctx: _Context, pid: str, hit: Hit) -> Proposal:
    candidate, sha = _candidate(repo, pid, hit)
    rule, *alternatives = hit.specs
    return Proposal(
        id=pid, exe=hit.exe, unit=hit.unit, glob=unit_rule_path(hit.exe, hit.unit), rule=rule,
        base=ctx.base(hit.exe, hit.unit), functions=(hit.function,),
        keeps=ctx.keeps(hit.exe, hit.unit),
        siblings=ctx.siblings(hit.exe, hit.unit, (hit.function,)), alternatives=tuple(alternatives),
        source=hit.source, candidate=candidate, candidate_sha256=sha, evidence=(hit.evidence,),
        status=PROPOSED, regate_exit=NOT_RUN, regate_variant=EMPTY, regate_cflags_sha256="",
        regate_log="", approved_by="", approved_date="", reason="", variant_sha256="",
        reverted=(),
    )  # fmt: skip


_MARKER = r"\bINCLUDE_ASM\s*\(\s*{name}\s*\)\s*;"


def _spliced(candidate: str, function: str, hitting: str) -> str | None:
    """`candidate` with `function` defined as `hitting` (the C that hit for it) defines it:
    its definition slice (contextpack.definitions) replaces the candidate's own definition or
    INCLUDE_ASM marker. None when either is not there."""
    new = contextpack.definitions(hitting).get(function)
    if new is None:
        return None
    old = contextpack.definitions(candidate).get(function)
    if old is not None:
        return candidate.replace(old.source, new.source, 1)
    marker = re.search(_MARKER.format(name=re.escape(function)), candidate)
    if marker is None:
        return None
    return candidate[: marker.start()] + new.source + candidate[marker.end() :]


def _failed(p: Proposal, reason: str) -> Proposal:
    return dataclasses.replace(p, status=FAILED, rule="", alternatives=(), reason=reason)


def _merge(repo: Path, ctx: _Context, existing: Proposal, hit: Hit) -> Proposal:
    """A later hit of a unit with an open proposal. Its evidence is recorded and any re-gate
    result is void. Another hit of a function the proposal holds changes nothing else (the
    candidate is that function's C that hit first). A new function narrows the rules to those
    every function hit under (its order stays the DEC-03 ranking); none left is FAILED with a
    reason naming the functions. Its definition from the C that hit is spliced into the
    candidate."""
    merged = dataclasses.replace(
        existing, evidence=(*existing.evidence, hit.evidence), status=PROPOSED,
        regate_exit=NOT_RUN, regate_variant=EMPTY, regate_cflags_sha256="", regate_log="",
        reason="", variant_sha256="", reverted=(),
    )  # fmt: skip
    if hit.function in existing.functions:
        return merged if existing.rule else dataclasses.replace(merged, status=FAILED,
                                                                reason=existing.reason)
    functions = (*existing.functions, hit.function)
    merged = dataclasses.replace(merged, functions=functions,
                                 keeps=ctx.keeps(hit.exe, hit.unit),
                                 siblings=ctx.siblings(hit.exe, hit.unit, functions))  # fmt: skip
    held = (existing.rule, *existing.alternatives) if existing.rule else ()
    common = [rule for rule in held if rule in hit.specs]
    if not common:
        before = ", ".join(held) or "no rule in common"
        return _failed(merged, f"no rule gives 100% for every function: "
                               f"{', '.join(existing.functions)} under {before}; "
                               f"{hit.function} under {', '.join(hit.specs)}")  # fmt: skip
    path = repo / existing.candidate
    text = _spliced(path.read_bytes().decode("utf-8"), hit.function,
                    hit.snapshot.read_bytes().decode("utf-8"))  # fmt: skip
    if text is None:
        return _failed(merged, f"{hit.function}'s definition in {hit.evidence[:-5]}.c cannot "
                               f"be put into {existing.candidate}")  # fmt: skip
    write_atomic(path, text.encode("utf-8"))
    return dataclasses.replace(merged, rule=common[0], alternatives=tuple(common[1:]),
                               candidate_sha256=lf_sha256(text))  # fmt: skip


def propose(runs: Sequence[str], *, repo: Path, queue: Path | None = None) -> ProposeReport:
    """Add or merge a proposal for every sweep hit of the named runs (D-12, D-13, D-28). A hit
    whose evidence the queue already holds adds nothing, so a re-run is idempotent; a function
    status.csv has matched is skipped (ruling F15)."""
    repo = Path(repo)
    queue = Path(queue) if queue is not None else repo / QUEUE
    proposals = read_queue(queue)
    ctx = _Context(repo)
    hits, notes = find_hits(repo, runs, ctx)
    added: list[str] = []
    merged: list[str] = []
    skipped = list(notes)
    for hit in hits:
        if any(hit.evidence in p.evidence for p in proposals):
            continue
        if ctx.matched(hit.exe, hit.start, hit.function):
            skipped.append(f"{hit.exe} {hit.function}: matched in status.csv ({hit.evidence})")
            continue
        unit = [p for p in proposals if (p.exe, p.unit) == (hit.exe, hit.unit)]
        held = next((p for p in unit if p.status == APPROVED), None)
        if held is not None:
            skipped.append(f"{hit.exe} {hit.function}: {held.id} for {hit.unit} is approved "
                           f"and awaits landing ({hit.evidence})")  # fmt: skip
            continue
        current = next((p for p in unit if p.status in OPEN_STATUSES), None)
        if current is None:
            proposal = _new_proposal(repo, ctx, _next_id(proposals), hit)
            proposals.append(proposal)
            added.append(proposal.id)
            continue
        proposals[proposals.index(current)] = _merge(repo, ctx, current, hit)
        merged.append(current.id)
    if added or merged:
        write_queue(queue, proposals)
    return ProposeReport(tuple(added), tuple(dict.fromkeys(merged)), tuple(skipped),
                         tuple(proposals))  # fmt: skip


# ---- regate: the whole-unit re-proof on a copy (D-12, D-28) ----

REGATE_LOG = "regate.json"
TEMP_CFLAGS = "cflags.txt"
SRC_COPY = "src"
BUILD_COPY = "build"
EXIT_OK, EXIT_MISMATCH, EXIT_TOOL = 0, 1, 2  # check's exit codes
_REASON_CAP = 600  # characters of problems kept in a proposal's reason
_NOT_PRINTABLE = re.compile(r"[^\x20-\x7e]")


def _ascii(text: str) -> str:
    return _NOT_PRINTABLE.sub("?", text)


def cflags_sha256(path: Path) -> str:
    """lf_sha256 of a cflags file: what regate_cflags_sha256 records and approve compares."""
    try:
        return lf_sha256(Path(path).read_bytes().decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise FlagsError(f"{path}: not UTF-8 ({exc})") from None


def _versions(config: Path) -> tuple[str, ...]:
    watcom = config / "watcom.toml"
    return tuple(load_watcom_manifest(watcom if watcom.is_file() else DEFAULT_WATCOM_MANIFEST))


def temp_cflags(dest: Path, committed: Path, proposal: Proposal, *,
                versions: Sequence[str] | None = None) -> str:  # fmt: skip
    """Write `dest`: the committed cflags text plus one rule line for the proposal's exact unit
    path, validated with parse_cflags. Refused when `dest` resolves to the committed file or to
    config/cflags.txt (T-07-49, the T-05-38 guard): a re-gate never edits them."""
    dest, committed = Path(dest), Path(committed)
    if dest.resolve() in {committed.resolve(), DEFAULT_CFLAGS.resolve()}:
        raise FlagsError(f"{dest} is the committed cflags file; a re-gate writes only "
                         f"{FLAGS_DIR.as_posix()}/<id>/{TEMP_CFLAGS}")  # fmt: skip
    text = committed.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    text += f"{proposal.glob}  {proposal.rule}  # {proposal.id} (proposed)\n"
    try:
        rules = parse_cflags(text, versions=versions or _versions(committed.parent),
                             where=str(dest))  # fmt: skip
        rule = select_rule(rules, proposal.glob)
    except CflagsError as exc:
        raise FlagsError(str(exc)) from None
    if " ".join([rule.spec, *rule.flags]) != proposal.rule:
        raise FlagsError(f"{proposal.id}: {proposal.rule!r} is not the rule {proposal.glob} "
                         f"takes in {dest}")  # fmt: skip
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(dest, text.encode("utf-8"))
    return text


def _reduced(text: str, neighbour: str) -> str:
    """`text` with the neighbour's definition slice (contextpack.definitions) turned back into
    its INCLUDE_ASM marker (D-28's reduced variant)."""
    found = contextpack.definitions(text).get(neighbour)
    if found is None:
        raise FlagsError(f"{neighbour} has no definition to turn back into INCLUDE_ASM")
    return text.replace(found.source, f"INCLUDE_ASM({neighbour});", 1)


@dataclass(frozen=True)
class Variant:
    """One check of the unit with one candidate text."""

    name: str  # AS_WRITTEN or REDUCED
    exit: int
    problems: tuple[str, ...]
    check: Mapping[str, Any] | None = None  # check's JSON; None when it raised

    def to_json(self) -> dict[str, Any]:
        return {"variant": self.name, "exit": self.exit, "problems": list(self.problems),
                "check": self.check}  # fmt: skip


@dataclass(frozen=True)
class RegateReport:
    proposals: tuple[Proposal, ...]  # each re-gated proposal as the queue now holds it
    variants: tuple[tuple[Variant, ...], ...]  # the checks run for each, in order

    @property
    def exit_code(self) -> int:
        return EXIT_OK if all(p.regate_exit == EXIT_OK for p in self.proposals) else EXIT_MISMATCH

    def to_json(self) -> dict[str, Any]:
        return {"ok": self.exit_code == EXIT_OK,
                "proposals": [{**p.to_json(), "variants": [v.to_json() for v in runs]}
                              for p, runs in zip(self.proposals, self.variants, strict=True)]}

    def format(self) -> str:
        lines = []
        for p, runs in zip(self.proposals, self.variants, strict=True):
            lines.append(f"{p.id}  {p.exe}/{p.unit} under {p.rule}: {p.status} (exit "
                         f"{p.regate_exit}, {p.regate_variant}); log {p.regate_log}")  # fmt: skip
            for run in runs:
                lines.append(f"  {run.name}: exit {run.exit}")
                lines += [f"    {problem}" for problem in run.problems]
        lines.append("a re-gate is evidence for the owner's approval; it never edits "
                     "config/cflags.txt or src/")  # fmt: skip
        return "\n".join(lines)


@dataclass(frozen=True)
class _Regate:
    """The roots and tools of one regate call."""

    repo: Path
    orig_dir: Path
    build_dir: Path | None
    watcom_dir: Path | None
    check_fn: Callable[..., check.CheckResult]
    cross_check_fn: Callable[..., list[str]]

    @property
    def config(self) -> Path:
        return self.repo / "config"

    @property
    def manifest(self) -> Path:
        return self.config / "targets.toml"

    def work(self, p: Proposal) -> Path:
        return self.repo / FLAGS_DIR / p.id


def _function_problem(fn: check.FunctionCheck) -> str:
    reloc = "reloc ok" if fn.reloc.ok else "reloc FAILED"
    same = "bytes ok" if fn.bytes_ok else f"{fn.differing} bytes differ"
    return f"{fn.name} at 0x{fn.va:08X}: objdiff {fn.objdiff_percent:g}%, {reloc}, {same}"


def _src_copy(env: _Regate, p: Proposal, text: str) -> Path:
    """build/flags/<id>/src: a fresh copy of src/ with the candidate text as the unit file."""
    copy = env.work(p) / SRC_COPY
    if not copy.resolve().is_relative_to((env.repo / FLAGS_DIR).resolve()):
        raise FlagsError(f"{copy} is not under {env.repo / FLAGS_DIR}")
    if copy.exists():
        shutil.rmtree(copy)
    src = env.repo / "src"
    if src.is_dir():
        shutil.copytree(src, copy)
    unit_file = copy / p.exe / f"{p.unit}.c"
    unit_file.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(unit_file, text.encode("utf-8"))
    return copy


def _cross(env: _Regate, p: Proposal, result: check.CheckResult) -> list[str]:
    """gate's D-24 cross-check of the copy's land, as gate_units runs it for one unit."""
    known = load_manifest(env.manifest)
    name = check.select_exe(known, p.exe, env.manifest).name
    tables = gate._tables(env.config, known)
    defined = {name: {fn.va: p.unit for fn in result.functions}}
    return list(env.cross_check_fn(result.splices, gate._matched(tables), defined,
                                   owners=gate._owners(env.config, known)))  # fmt: skip


def _variant(env: _Regate, p: Proposal, name: str, text: str, cflags: Path
             ) -> tuple[Variant, check.CheckResult | None]:  # fmt: skip
    """check_unit of the unit with `text` on a copy of src/ under the temporary cflags, then the
    cross-check. A tool error (the compile, the land, the manifest) is exit 2."""
    work = env.work(p)
    watcom = env.config / "watcom.toml"
    try:
        result = env.check_fn(
            p.exe, p.unit, orig_dir=env.orig_dir, manifest=env.manifest, config_root=env.config,
            src_root=_src_copy(env, p, text), build_dir=env.build_dir or work / BUILD_COPY,
            watcom_dir=env.watcom_dir, cflags=cflags,
            watcom_manifest=watcom if watcom.is_file() else None, log=work / "cc.log",
        )  # fmt: skip
        problems = [_function_problem(fn) for fn in result.functions if not fn.ok]
        problems += [item.format() for item in result.problems]
        problems += [f"{s.exe}: the landed EXE is not SHA-1 identical"
                     for s in result.splices if not s.ok]  # fmt: skip
        problems += _cross(env, p, result)
    except (ValueError, OSError, RuntimeError) as exc:
        return Variant(name, EXIT_TOOL, (_ascii(f"{type(exc).__name__}: {exc}"),)), None
    failed = result.exit_code != EXIT_OK or bool(problems)
    return Variant(name, EXIT_MISMATCH if failed else EXIT_OK, tuple(problems),
                   result.to_json()), result  # fmt: skip


def _neighbours(p: Proposal, result: check.CheckResult) -> list[str]:
    """The co-defined functions that alone kept the check from passing (D-28): every function
    of the proposal and every kept one defined and passing, and only others failing."""
    wanted = {*p.functions, *p.keeps}
    by_name = {fn.name: fn for fn in result.functions}
    if result.problems or not all(n in by_name and by_name[n].ok for n in wanted):
        return []
    return [fn.name for fn in result.functions if not fn.ok]


def _reduce_all(text: str, neighbours: Sequence[str]) -> str | None:
    try:
        for name in neighbours:
            text = _reduced(text, name)
    except FlagsError:
        return None
    return text


def _regate_one(env: _Regate, p: Proposal) -> tuple[Proposal, tuple[Variant, ...]]:
    committed = env.config / "cflags.txt"
    sha = cflags_sha256(committed)
    work = env.work(p)
    cflags = work / TEMP_CFLAGS
    temp_cflags(cflags, committed, p, versions=_versions(env.config))
    text = (env.repo / p.candidate).read_bytes().decode("utf-8")
    first, result = _variant(env, p, AS_WRITTEN, text, cflags)
    runs = [first]
    neighbours = _neighbours(p, result) if result is not None and first.exit else []
    reduced = _reduce_all(text, neighbours) if neighbours else None
    if reduced is not None:
        runs.append(_variant(env, p, REDUCED, reduced, cflags)[0])
    final = runs[-1]
    pinned = _pin_variant(env, p, final, reduced, neighbours)
    log = work / REGATE_LOG
    record = {"id": p.id, "exe": p.exe, "unit": p.unit, "rule": p.rule,
              "cflags": _relative(env.repo, cflags), "cflags_sha256": sha,
              "candidate_sha256": p.candidate_sha256, "variant_sha256": pinned.variant_sha256,
              "reverted": list(pinned.reverted),
              "variants": [run.to_json() for run in runs]}  # fmt: skip
    write_atomic(log, (json.dumps(record, indent=2) + "\n").encode("ascii"))
    reason = "" if final.exit == EXIT_OK else _ascii(
        f"re-gate exit {final.exit} ({final.name}): {'; '.join(final.problems)}")[:_REASON_CAP]
    return dataclasses.replace(
        pinned, status=REGATED if final.exit == EXIT_OK else FAILED, regate_exit=final.exit,
        regate_variant=final.name, regate_cflags_sha256=sha,
        regate_log=_relative(env.repo, log), reason=reason,
    ), tuple(runs)  # fmt: skip


def _pin_variant(env: _Regate, p: Proposal, final: Variant, reduced: str | None,
                 neighbours: Sequence[str]) -> Proposal:  # fmt: skip
    """Fix round 1: a pass on the reduced variant writes that C to variant_path and records
    its sha and the functions it returned to INCLUDE_ASM, so approve (07-24) lands exactly the C
    that passed; any other outcome clears both fields and removes a stale variant file."""
    path = env.repo / variant_path(p)
    if final.name == REDUCED and final.exit == EXIT_OK and reduced is not None:
        write_atomic(path, reduced.encode("utf-8"))
        return dataclasses.replace(p, variant_sha256=lf_sha256(reduced),
                                   reverted=tuple(neighbours))  # fmt: skip
    path.unlink(missing_ok=True)
    return dataclasses.replace(p, variant_sha256="", reverted=())


def _check_unit(exe: str, unit: str, **roots: Any) -> check.CheckResult:
    """check.check_unit, looked up when called (so the verb's tests can stand a fake in)."""
    return check.check_unit(exe, unit, **roots)


def _cross_check(splices: Any, matched: Any, defined: Any, **kwargs: Any) -> list[str]:
    """gate.cross_check, looked up when called."""
    return gate.cross_check(splices, matched, defined, **kwargs)


def _regatable(proposals: Sequence[Proposal], ids: Sequence[str], repo: Path) -> list[Proposal]:
    """The proposals `ids` names, each refused unless open, with a rule and its candidate as
    queued (the C that hit, by its sha256)."""
    by_id = {p.id: p for p in proposals}
    if len(set(ids)) != len(ids) or not ids:
        raise FlagsError(f"name each proposal once: {' '.join(ids) or '(none)'}")
    out = []
    for pid in ids:
        p = by_id.get(pid)
        if p is None:
            raise FlagsError(f"{pid} is not in the queue")
        if p.status not in OPEN_STATUSES:
            raise FlagsError(f"{pid} is {p.status}; only {', '.join(OPEN_STATUSES)} proposals "
                             "are re-gated")  # fmt: skip
        if not p.rule:
            raise FlagsError(f"{pid} has no rule to re-gate ({p.reason})")
        path = repo / p.candidate
        if not path.is_file() or cflags_sha256(path) != p.candidate_sha256:
            raise FlagsError(f"{pid}: the candidate {p.candidate} is missing or changed since it "
                             "was proposed; run `flags propose` again")  # fmt: skip
        out.append(p)
    return out


def regate(
    ids: Sequence[str],
    *,
    repo: Path,
    queue: Path | None = None,
    orig_dir: Path | None = None,
    build_dir: Path | None = None,
    watcom_dir: Path | None = None,
    check_fn: Callable[..., check.CheckResult] | None = None,
    cross_check_fn: Callable[..., list[str]] | None = None,
) -> RegateReport:
    """Re-prove each proposal over its whole unit and both EXEs (D-12): check_unit of a copy of
    src/ with the candidate in place (build/flags/<id>/src) under the committed cflags plus the
    proposal's one rule line (build/flags/<id>/cflags.txt), then gate's cross-check. When only
    co-defined neighbours miss, the reduced variant retries with them as INCLUDE_ASM (D-28).
    Writes regate_exit, regate_variant, regate_cflags_sha256, regate_log and the status to the
    queue after each proposal; never writes src/ or config/cflags.txt."""
    repo = Path(repo)
    queue = Path(queue) if queue is not None else repo / QUEUE
    proposals = read_queue(queue)
    env = _Regate(repo, Path(orig_dir) if orig_dir is not None else repo / "orig", build_dir,
                  watcom_dir, check_fn or _check_unit, cross_check_fn or _cross_check)  # fmt: skip
    done: list[Proposal] = []
    runs: list[tuple[Variant, ...]] = []
    for p in _regatable(proposals, ids, repo):
        updated, variants = _regate_one(env, p)
        proposals[proposals.index(p)] = updated
        write_queue(queue, proposals)
        done.append(updated)
        runs.append(variants)
    return RegateReport(tuple(done), tuple(runs))
