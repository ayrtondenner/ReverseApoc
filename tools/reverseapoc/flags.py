"""Per-unit cflags proposals: the owner-approval queue of D-12 (plan 07-17).

A sweep hit of a driver attempt (`attempt check --sweep`, D-17/D-15) is a 100% cell under flags
other than its unit's rule. It is never a match and never evidence for the `*` default (D-28, D-33):
`flags propose` turns it into a proposed per-unit rule in the committed review queue
config/cflags-proposals.toml, with the C that hit copied to build/flags/<id>/<unit>.c (gitignored).
`flags list` shows the queue. Nothing here writes config/cflags.txt or src/; only the owner's
approve step (plan 07-24) does.

The queue holds no game bytes: names, flag strings, repo-relative paths under build/, percents,
SHA-256 hex and dates, all printable ASCII. It is written only by `write_queue`, in a fixed key
order, through write_atomic, and read back with tomllib.
"""

from __future__ import annotations

import dataclasses
import json
import re
import tomllib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import driver
from .cflags import load_cflags, select_rule
from .check import unit_rule_path
from .fileio import write_atomic
from .functions import read_functions_csv
from .status import MATCHED, lf_sha256, read_status, status_path
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
_SIBLING = re.compile(r"[A-Za-z_][A-Za-z0-9_]*( (0|[1-9][0-9]{0,2})\.[0-9]{2})")
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
    siblings: tuple[str, ...]  # `<name> <percent>` of the unit's other partial rows (D-32)
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
        if self.reason:
            lines.append(f"  reason {self.reason}")
        return "\n".join(lines)


FIELDS = tuple(f.name for f in dataclasses.fields(Proposal))
_LIST_FIELDS = ("functions", "keeps", "siblings", "alternatives", "evidence")
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


def _cells_100(doc: Mapping[str, Any], base: str) -> tuple[tuple[tuple[int, str], ...], str]:
    """The 100% cells of a sweep's JSON as (number, spec), best first, and the hit's source."""
    found = [(int(c["cell"]), _cell_spec(c)) for c in doc["cells"] if _perfect(c, base)]
    return tuple(sorted(found)), SWEEP


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
        self._names: dict[str, dict[str, int]] = {}

    def _status(self, exe: str) -> list:
        path = status_path(self.config, exe)
        return read_status(path) if path.is_file() else []

    def base(self, exe: str, unit: str) -> str:
        rule = select_rule(self.rules, unit_rule_path(exe, unit))
        return " ".join([rule.spec, *rule.flags])

    def start(self, exe: str, function: str) -> int | None:
        found = _FUNC.fullmatch(function)
        if found:
            return int(found.group(1), _HEX)
        if exe not in self._names:
            path = self.config / exe / "functions.csv"
            rows = read_functions_csv(path) if path.is_file() else []
            self._names[exe] = {row.name: row.start for row in rows}
        return self._names[exe].get(function)

    def matched(self, exe: str, start: int, function: str) -> bool:
        return any(row.status == MATCHED and (row.start == start or row.name == function)
                   for row in self.status[exe])  # fmt: skip

    def keeps(self, exe: str, unit: str) -> tuple[str, ...]:
        return tuple(row.name for row in self.status[exe]
                     if row.unit == unit and row.status == MATCHED)  # fmt: skip


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
        keeps=ctx.keeps(hit.exe, hit.unit), siblings=(), alternatives=tuple(alternatives),
        source=hit.source, candidate=candidate, candidate_sha256=sha, evidence=(hit.evidence,),
        status=PROPOSED, regate_exit=NOT_RUN, regate_variant=EMPTY, regate_cflags_sha256="",
        regate_log="", approved_by="", approved_date="", reason="",
    )  # fmt: skip


def _merge(existing: Proposal, hit: Hit) -> Proposal:
    """A later hit of a unit with an open proposal: its evidence is recorded."""
    return dataclasses.replace(existing, evidence=(*existing.evidence, hit.evidence))


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
        proposals[proposals.index(current)] = _merge(current, hit)
        merged.append(current.id)
    if added or merged:
        write_queue(queue, proposals)
    return ProposeReport(tuple(added), tuple(dict.fromkeys(merged)), tuple(skipped),
                         tuple(proposals))  # fmt: skip
