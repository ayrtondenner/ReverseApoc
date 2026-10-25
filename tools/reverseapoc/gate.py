"""`reverseapoc gate`: the only writer of config/<exe>/status.csv (D-21) and the zero-regression
gate the driver runs before every commit (D-24, AGT-06).

`gate EXE/UNIT [EXE/UNIT ...]` runs `check` (check.check_unit) for each target. Only when every
check exits 0 and the cross-check passes does it write `matched` rows (status.py) for every
function the targets define: best_percent 100.00, the LF-normalised SHA-256 of the unit file
(taken before and after the check, so a file edited while it ran is refused), `--attempts N`
(0 = by hand) and today's UTC date. A unit gated again keeps the attempts and date of its
matched rows; only their source_sha256, and their name when symbols.csv renames the start, are
rewritten (ruling F29, fix round 1): a matched row is keyed by (EXE, start). The targets are all
or nothing: one failure writes no row of any (ruling F1), and each unit file is hashed again
just before the write. gate (and gate --all) compiles only the committed src tree: it writes the
public status.csv, so a non-default --src is for --partial only. A gated unit with matched rows
whose C now defines none of its functions (every match reverted to INCLUDE_ASM) is a mismatch,
exit 1, without running check.

The cross-check (`cross_check`, D-24): for each EXE, the row starts check's land step landed
must equal status.csv's matched starts plus the functions the gated units now define. That
catches what the whole-EXE SHA-1 cannot: a match reverted to INCLUDE_ASM (its original bytes
land again, the SHA-1 still matches, but the start is missing from the landed set), a compiled
unit nobody gated, and a matched row whose function moved to another unit.

`gate --all` re-proves every matched function without writing: check_source for each unit
with matched rows, then ONE land_all (never check_unit per unit, which would recompile every
unit for each one), the cross-check, and both SHA-1s through ExeLand.ok. It also compares each
matched row's source_sha256 with the unit file, and reports a unit whose C defines none of its
functions any more without compiling it (so the land lands nothing of it).

`gate EXE/UNIT --partial --src FILE` scores a saved attempt (the driver's best C) with
check_source, never landing it: its compile goes to build/check-custom (the saved file's
directory is a non-default src root, DI-06 part b, ruling F7), so ninja's objects are never
touched. Every function of the unit that is not matched and scores above 0% gets a `partial`
row with that percent and the saved file's SHA-256; an existing partial row with a higher (or
equal) percent is kept, with the larger attempts count. A matched row is never touched, and a
saved file with D-12 account problems writes nothing.

On any mismatch gate writes nothing and exits 1; on a tool error (CheckError, StatusError, the
CLI's tool errors) it writes nothing and exits 2. No flag, environment variable or helper writes
a matched row without a passing check: the verdict is check's own, in the container, never an
agent's transcript (D-24, AGT-01).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# check_unit, check_source, land_all, load_exe and compile_source are looked up at call time
# (`check_fn or check_unit`), so a test can stand a fake in for each.
from . import check as _check  # DEFAULT_SRC, read at call time (tests stand a tree in)
from .check import (
    EXIT_MISMATCH,
    EXIT_OK,
    SOURCE_SUFFIX,
    CheckError,
    CheckResult,
    CompileOptions,
    ExeLand,
    FunctionCheck,
    SourceCheck,
    check_source,
    check_unit,
    default_objdiff_runner,
    exe_stem,
    land_all,
    load_exe,
    object_root,
    read_source,
    select_exe,
    source_marks,
)
from .compiler import compile_source
from .functions import FunctionRow, _address, read_functions_csv, read_symbols_csv
from .status import (
    MATCHED,
    PARTIAL,
    PERCENT_MAX,
    StatusRow,
    format_percent,
    format_status,
    lf_sha256,
    read_status,
    round_percent,
    status_path,
    write_status,
)
from .targets import Target, load_manifest

MODE_UNIT, MODE_ALL, MODE_PARTIAL = "unit", "all", "partial"
UNITS_CSV = "units.csv"
FUNCTIONS_CSV = "functions.csv"
SYMBOLS_CSV = "symbols.csv"
FUNC_SYMBOL = "func"  # the symbols.csv kind of a function name


@dataclass(frozen=True)
class GateRoots:
    """The trees and tool options gate hands to check (the `check` verb's options)."""

    orig_dir: Path
    manifest: Path
    config_root: Path
    src_root: Path
    build_dir: Path
    watcom_dir: Path | None = None
    cflags: Path | None = None
    watcom_manifest: Path | None = None
    log: Path | None = None

    def check_kwargs(self) -> dict[str, Any]:
        return {"orig_dir": self.orig_dir, "manifest": self.manifest,
                "config_root": self.config_root, "src_root": self.src_root,
                "build_dir": self.build_dir, "watcom_dir": self.watcom_dir,
                "cflags": self.cflags, "watcom_manifest": self.watcom_manifest,
                "log": self.log}  # fmt: skip

    def options(self, *, src_root: Path | None = None) -> CompileOptions:
        """check_unit's CompileOptions for these roots; `src_root` stands in for the src tree."""
        return CompileOptions(self.cflags, self.watcom_manifest, self.watcom_dir, self.log,
                              src_root=Path(src_root or self.src_root),
                              config_root=Path(self.config_root))  # fmt: skip

    def unit_file(self, stem: str, unit: str) -> Path:
        return Path(self.src_root) / stem / f"{unit}{SOURCE_SUFFIX}"


@dataclass(frozen=True)
class Written:
    """One row gate wrote, and the table it went to."""

    path: Path
    row: StatusRow

    def line(self) -> str:
        r = self.row
        return (f"wrote {r.status} {r.name}  {_address(r.start)}  {r.unit}  "
                f"{format_percent(r.best_percent)}  -> {self.path}")  # fmt: skip

    def to_json(self) -> dict[str, Any]:
        r = self.row
        return {"path": str(self.path), "start": _address(r.start), "name": r.name,
                "unit": r.unit, "status": r.status,
                "best_percent": format_percent(r.best_percent), "attempts": r.attempts,
                "source_sha256": r.source_sha256, "date": r.date}  # fmt: skip


@dataclass(frozen=True)
class GateResult:
    """What one gate run checked, found and wrote. `ok` is exit 0."""

    mode: str
    targets: tuple[str, ...]
    exit_code: int
    reports: tuple[str, ...] = ()  # each check's text report
    checks: tuple[dict[str, Any], ...] = ()  # each check's JSON
    problems: tuple[str, ...] = ()  # why gate refused, beyond the checks' own verdicts
    written: tuple[Written, ...] = ()
    splices: tuple[dict[str, Any], ...] = ()  # gate --all's one land, per EXE

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK

    def to_json(self) -> dict[str, Any]:
        return {"mode": self.mode, "targets": list(self.targets), "ok": self.ok,
                "exit_code": self.exit_code, "checks": list(self.checks),
                "problems": list(self.problems), "splice": list(self.splices),
                "written": [w.to_json() for w in self.written]}  # fmt: skip

    def format(self) -> str:
        lines = [*self.reports]
        lines += [f"GATE REFUSED  {problem}" for problem in self.problems]
        lines += [w.line() for w in self.written]
        if self.mode == MODE_ALL:  # --all never writes: its verdict alone
            lines.append("ok" if self.ok else "MISMATCH")
            return "\n".join(lines)
        if self.ok and not self.written:
            lines.append("wrote nothing")
        lines.append("ok" if self.ok else "MISMATCH: status.csv not written")
        return "\n".join(lines)


# ---- inputs ----


def _today(today: date | None) -> str:
    return (today or datetime.now(UTC).date()).isoformat()


def _check_attempts(attempts: int) -> None:
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
        raise CheckError(f"--attempts must be a count (0 = by hand), got {attempts!r}")


def source_sha256(path: Path) -> str:
    """lf_sha256 of a unit file read strictly as UTF-8 (check's read_source rule)."""
    try:
        return lf_sha256(Path(path).read_bytes().decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise CheckError(f"{path}: not UTF-8 ({exc})") from None


def _hash_or_none(path: Path) -> str | None:
    return source_sha256(path) if Path(path).is_file() else None


def _committed_src(roots: GateRoots) -> None:
    """gate writes (and gate --all proves) the public status.csv: only the committed src tree
    counts (fix round 1, M4). A non-default --src is for --partial's saved attempt."""
    if Path(roots.src_root).resolve() != Path(_check.DEFAULT_SRC).resolve():
        raise CheckError(f"gate checks only the committed src tree {_check.DEFAULT_SRC}; --src "
                         f"{roots.src_root} is for --partial --src FILE only")  # fmt: skip


def _tables(config_root: Path, known: Iterable[Target]) -> dict[str, list[StatusRow]]:
    """Every manifest target's status.csv rows by manifest name ([] for a missing table)."""
    return {t.name: read_status(status_path(config_root, exe_stem(t.name))) for t in known}


def _matched(tables: Mapping[str, Sequence[StatusRow]]) -> dict[str, dict[int, StatusRow]]:
    return {name: {r.start: r for r in rows if r.status == MATCHED}
            for name, rows in tables.items()}  # fmt: skip


def _functions(config_root: Path, known: Iterable[Target]) -> dict[str, dict[int, FunctionRow]]:
    """functions.csv rows by start, for every manifest target that has the file."""
    out = {}
    for t in known:
        path = Path(config_root) / exe_stem(t.name) / FUNCTIONS_CSV
        if path.is_file():
            out[t.name] = {row.start: row for row in read_functions_csv(path)}
    return out


def _owners(config_root: Path, known: Iterable[Target]) -> dict[str, dict[int, FunctionRow]]:
    """_functions with each row named as the start is named at gate time: its symbols.csv
    function name when there is one (Phase 7 renames, DEC-04), else its functions.csv name."""
    out = _functions(config_root, known)
    for t in known:
        rows = out.get(t.name)
        path = Path(config_root) / exe_stem(t.name) / SYMBOLS_CSV
        if rows is None or not path.is_file():
            continue
        for symbol in read_symbols_csv(path):
            if symbol.kind == FUNC_SYMBOL and symbol.address in rows:
                rows[symbol.address] = dataclasses.replace(rows[symbol.address], name=symbol.name)
    return out


def _reverted(name: str, src: Path, unit_rows: Sequence[FunctionRow],
              matched: Iterable[StatusRow], unit: str) -> list[str]:  # fmt: skip
    """When the unit file's C defines none of `unit_rows` (configure.py's D-12 parser, as
    check reads it), every matched row of the unit is a reverted match (Important 1);
    otherwise []. check itself refuses such a file as a tool error, so gate looks first."""
    if not Path(src).is_file():
        return []
    defined = source_marks(read_source(src), unit_rows).defined
    if any(row.name in defined for row in unit_rows):
        return []
    return [_function_problem(name, row, None, unit) or "" for row in matched]


# ---- the cross-check (D-24) ----


def _label(start: int, matched: Mapping[int, StatusRow],
           owners: Mapping[int, FunctionRow] | None) -> str:  # fmt: skip
    row = matched.get(start) or (owners or {}).get(start)
    return f"{row.name} at {_address(start)}" if row is not None else _address(start)


def _moved(exe: str, matched: Mapping[int, StatusRow], defined: Mapping[int, str],
           owners: Mapping[int, FunctionRow] | None) -> list[str]:  # fmt: skip
    """Matched rows whose function is now defined by, or in functions.csv belongs to, another
    unit than status.csv records, and rows not re-gated now whose start has another name
    (functions.csv/symbols.csv) than the row records. Rows are keyed by start: a re-gated start
    takes its new name (merge_matched)."""
    out = []
    for start, row in sorted(matched.items()):
        where = f"{exe}: {row.name} at {_address(start)} is matched in unit {row.unit}"
        if start in defined and defined[start] != row.unit:
            out.append(f"{where} but is now defined by unit {defined[start]}")
        owner = None if owners is None else owners.get(start)
        if owners is not None and owner is None:
            out.append(f"{where} but functions.csv has no row at {_address(start)}")
        elif owner is not None and owner.unit != row.unit:
            out.append(f"{where} but functions.csv puts {owner.name} in unit {owner.unit}")
        elif owner is not None and owner.name != row.name and start not in defined:
            out.append(f"{where} but its start is now named {owner.name} "
                       f"(functions.csv/symbols.csv); re-gate unit {row.unit}")  # fmt: skip
    return out


def _cross_check_exe(exe: str, landed: set[int] | None, matched: Mapping[int, StatusRow],
                     defined: Mapping[int, str], owners: Mapping[int, FunctionRow] | None
                     ) -> list[str]:  # fmt: skip
    if landed is None:
        return [f"{exe}: status.csv has matched rows or a gated unit defines functions, but "
                f"nothing landed for {exe} (no config/<exe>/{UNITS_CSV}?)"]  # fmt: skip
    expected = set(matched) | set(defined)
    out = []
    for start in sorted(expected - landed):
        what = (f"is matched in status.csv (unit {matched[start].unit})" if start in matched
                else f"is defined by gated unit {defined[start]}")  # fmt: skip
        out.append(f"{exe}: {_label(start, matched, owners)} {what} but was not landed "
                   "(reverted to INCLUDE_ASM, or its unit file is gone)")  # fmt: skip
    for start in sorted(landed - expected):
        out.append(f"{exe}: {_label(start, matched, owners)} landed but is neither matched in "
                   "status.csv nor defined by a gated unit; gate its unit too")  # fmt: skip
    return out + _moved(exe, matched, defined, owners)


def cross_check(
    splices: Iterable[ExeLand],
    matched_by_exe: Mapping[str, Mapping[int, StatusRow]],
    defined_now: Mapping[str, Mapping[int, str]],
    *,
    owners: Mapping[str, Mapping[int, FunctionRow]] | None = None,
) -> list[str]:
    """D-24: for each EXE (by manifest name, ExeLand.exe) the landed row starts equal the matched
    starts of status.csv plus `defined_now` (start -> the gated unit defining it); every matched
    row's function is still in its unit (the gated units and, given `owners`, functions.csv).
    Returns the problems, [] when it passes. Pure: reads and writes nothing."""
    landed = {s.exe: set(s.result.landed) for s in splices}
    names = (set(landed) | {exe for exe, rows in matched_by_exe.items() if rows}
             | {exe for exe, rows in defined_now.items() if rows})  # fmt: skip
    problems = []
    for exe in sorted(names):
        problems += _cross_check_exe(exe, landed.get(exe), matched_by_exe.get(exe, {}),
                                     defined_now.get(exe, {}),
                                     None if owners is None else owners.get(exe, {}))  # fmt: skip
    return problems


# ---- gate EXE/UNIT [EXE/UNIT ...] ----


@dataclass(frozen=True)
class _Target:
    """One EXE/UNIT to gate, resolved against the manifest."""

    exe: str  # as given
    unit: str
    name: str  # the manifest name, ExeLand.exe
    stem: str

    @property
    def label(self) -> str:
        return f"{self.exe}/{self.unit}"


def _resolve(targets: Iterable[tuple[str, str]], known: Sequence[Target],
             manifest: Path) -> list[_Target]:  # fmt: skip
    out: list[_Target] = []
    for exe, unit in targets:
        name = select_exe(known, exe, manifest).name
        target = _Target(exe, unit, name, exe_stem(name))
        if any((t.name, t.unit) == (target.name, unit) for t in out):
            raise CheckError(f"{target.label} is named twice")
        out.append(target)
    if not out:
        raise CheckError("gate needs at least one EXE/UNIT")
    return out


def _checked(target: _Target, roots: GateRoots, check_fn: Callable[..., CheckResult]
             ) -> tuple[CheckResult, str]:  # fmt: skip
    """check of one target, with the unit file's hash taken before and after it."""
    src = roots.unit_file(target.stem, target.unit)
    before = _hash_or_none(src)
    result = check_fn(target.exe, target.unit, **roots.check_kwargs())
    after = _hash_or_none(src)
    if before is None or after != before:
        raise CheckError(f"{src} changed while it was checked; gate it again")
    return result, after


def merge_matched(rows: Iterable[StatusRow], new: Iterable[StatusRow]) -> list[StatusRow]:
    """`rows` with `new` merged in, sorted by start: a start already matched keeps its row,
    its attempts and date, and takes the new source_sha256 and name (ruling F29; renames, fix
    round 1); any other start takes the new row."""
    by_start = {row.start: row for row in rows}
    for row in new:
        old = by_start.get(row.start)
        by_start[row.start] = (
            dataclasses.replace(old, source_sha256=row.source_sha256, name=row.name)
            if old is not None and old.status == MATCHED else row)  # fmt: skip
    return sorted(by_start.values(), key=lambda r: r.start)


def _defined(passed: Iterable[tuple[_Target, CheckResult, str]]
             ) -> tuple[dict[str, dict[int, str]], list[str]]:  # fmt: skip
    """start -> gated unit, by manifest name; a start two targets define is a problem."""
    defined: dict[str, dict[int, str]] = {}
    problems = []
    for target, result, _ in passed:
        mine = defined.setdefault(target.name, {})
        for fn in result.functions:
            if fn.va in mine:
                problems.append(f"{target.name}: {fn.name} at {_address(fn.va)} is defined by "
                                f"both {mine[fn.va]} and {target.unit}")  # fmt: skip
            mine[fn.va] = target.unit
    return defined, problems


def _name(owners: Mapping[str, Mapping[int, FunctionRow]], exe: str, fn: FunctionCheck) -> str:
    owner = owners.get(exe, {}).get(fn.va)
    return owner.name if owner is not None else fn.name


def _write_tables(config_root: Path, tables: Mapping[str, Sequence[StatusRow]],
                  passed: Sequence[tuple[_Target, CheckResult, str]], attempts: int,
                  day: str, owners: Mapping[str, Mapping[int, FunctionRow]]
                  ) -> tuple[Written, ...]:  # fmt: skip
    """Every touched table merged first, then written: a refused row writes no table. An OS
    error after a table was written names it (M2): restore config/ before committing."""
    new: dict[str, list[StatusRow]] = {}
    for target, result, sha in passed:
        new.setdefault(target.name, []).extend(
            StatusRow(fn.va, _name(owners, target.name, fn), target.unit, MATCHED, PERCENT_MAX,
                      attempts, sha, day)
            for fn in result.functions)  # fmt: skip
    merged = {name: merge_matched(tables.get(name, []), rows) for name, rows in new.items()}
    paths = {name: status_path(config_root, exe_stem(name)) for name in merged}
    for rows in merged.values():
        format_status(rows)  # a row write_status would refuse fails before any table is written
    written: list[Written] = []
    done: list[Path] = []
    for name in sorted(merged, key=exe_stem):
        try:
            write_status(paths[name], merged[name])
        except OSError as exc:
            if not done:
                raise
            raise CheckError(f"wrote {', '.join(map(str, done))} but not {paths[name]}: {exc}; "
                             "restore config/ before committing") from exc  # fmt: skip
        done.append(paths[name])
        starts = {row.start for row in new[name]}
        written += [Written(paths[name], row) for row in merged[name] if row.start in starts]
    return tuple(written)


def gate_units(
    targets: Sequence[tuple[str, str]],
    *,
    roots: GateRoots,
    attempts: int = 0,
    today: date | None = None,
    check_fn: Callable[..., CheckResult] | None = None,
) -> GateResult:
    """Check each (EXE, UNIT) of `targets`; when every check exits 0 and the cross-check passes,
    write matched rows for every function they define, else write nothing (exit 1)."""
    _check_attempts(attempts)
    _committed_src(roots)
    check_fn = check_fn or check_unit
    known = load_manifest(roots.manifest)
    resolved = _resolve(targets, known, roots.manifest)
    labels = tuple(t.label for t in resolved)
    tables = _tables(roots.config_root, known)
    functions = _functions(roots.config_root, known)
    owners = _owners(roots.config_root, known)
    reports, docs, passed = [], [], []
    for target in resolved:
        matched_here = [r for r in _matched(tables).get(target.name, {}).values()
                        if r.unit == target.unit]  # fmt: skip
        unit_rows = [r for r in functions.get(target.name, {}).values() if r.unit == target.unit]
        reverted = _reverted(target.name, roots.unit_file(target.stem, target.unit), unit_rows,
                             matched_here, target.unit) if matched_here else []  # fmt: skip
        if reverted:
            return GateResult(MODE_UNIT, labels, EXIT_MISMATCH, tuple(reports), tuple(docs),
                              tuple(reverted))  # fmt: skip
        result, sha = _checked(target, roots, check_fn)
        reports.append(result.format())
        docs.append(result.to_json())
        if result.exit_code != EXIT_OK:
            return GateResult(MODE_UNIT, labels, EXIT_MISMATCH, tuple(reports), tuple(docs))
        passed.append((target, result, sha))
    defined, problems = _defined(passed)
    for _, result, _ in passed:
        found = cross_check(result.splices, _matched(tables), defined, owners=owners)
        problems += [p for p in found if p not in problems]
    if problems:
        return GateResult(MODE_UNIT, labels, EXIT_MISMATCH, tuple(reports), tuple(docs),
                          tuple(problems))  # fmt: skip
    for target, _, sha in passed:  # M7: the file each row will name is still the one checked
        src = roots.unit_file(target.stem, target.unit)
        if _hash_or_none(src) != sha:
            raise CheckError(f"{src} changed after its check; gate it again")
    written = _write_tables(roots.config_root, tables, passed, attempts, _today(today), owners)
    return GateResult(MODE_UNIT, labels, EXIT_OK, tuple(reports), tuple(docs), (), written)


def gate_unit(
    exe: str,
    unit: str,
    *,
    roots: GateRoots,
    attempts: int = 0,
    today: date | None = None,
    check_fn: Callable[..., CheckResult] | None = None,
) -> GateResult:
    """gate_units for one target."""
    return gate_units([(exe, unit)], roots=roots, attempts=attempts, today=today,
                      check_fn=check_fn)  # fmt: skip


# ---- gate --all ----


def _function_problem(exe: str, row: StatusRow, fn: FunctionCheck | None, unit: str) -> str | None:
    where = f"{exe}: {row.name} at {_address(row.start)} is matched"
    if fn is None:
        return f"{where} but unit {unit} no longer defines it in C (reverted to INCLUDE_ASM)"
    if fn.ok:
        return None
    reloc = "reloc ok" if fn.reloc.ok else f"reloc FAILED ({len(fn.reloc.problems)})"
    same = "bytes ok" if fn.bytes_ok else f"{fn.differing} bytes differ"
    return f"{where} but now scores objdiff {fn.objdiff_percent:g}%, {reloc}, {same}"


@dataclass
class _AllRun:
    """What gate --all collects across the EXEs before its one land."""

    roots: GateRoots
    check_source_fn: Callable[..., SourceCheck]
    compile_fn: Callable[..., Any]
    objdiff_runner: Callable[[Sequence[str]], str] | None
    problems: list[str] = dataclasses.field(default_factory=list)
    reports: list[str] = dataclasses.field(default_factory=list)
    checks: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    fresh: set[tuple[str, str]] = dataclasses.field(default_factory=set)

    def recheck(self, exe: Any, name: str, unit: str, rows: Sequence[StatusRow]) -> None:
        """check_source of one matched unit: every matched row still defined and ok, and its
        source_sha256 still the unit file's (M9). A unit whose C defines none of its functions
        is reported reverted and not compiled (Important 1)."""
        src = self.roots.unit_file(exe.stem, unit)
        self.checks.append({"exe": exe.stem, "unit": unit, "functions": []})
        if not src.is_file():
            self.problems.append(f"{name}: unit {unit} has matched rows but {src} is missing")
            return
        try:
            unit_rows = exe.unit_rows(unit)
        except CheckError as exc:
            self.problems.append(f"{name}: unit {unit} has matched rows: {exc}")
            return
        sha = source_sha256(src)
        if any(row.source_sha256 != sha for row in rows):
            self.problems.append(f"{name}: unit {unit}: status.csv's source_sha256 is not "
                                 f"the hash of {src} (changed since it was gated); re-gate "
                                 "it")  # fmt: skip
        reverted = _reverted(name, src, unit_rows, rows, unit)
        if reverted:
            self.problems += reverted
            return
        runner = self.objdiff_runner or default_objdiff_runner(f"{exe.stem}/{unit}")
        source = self.check_source_fn(
            exe, unit, src, unit_rows, build_dir=self.roots.build_dir,
            compile_fn=self.compile_fn, objdiff_runner=runner, options=self.roots.options(),
        )  # fmt: skip
        self.fresh.add((name, unit))
        by_va = {fn.va: fn for fn in source.functions}
        for row in rows:
            problem = _function_problem(name, row, by_va.get(row.start), unit)
            if problem is not None:
                self.problems.append(problem)
        self.problems += [f"{name}/{unit}: {p.format().strip()}" for p in source.problems]
        self.reports.append("\n".join([f"check {exe.stem}/{unit}"]
                                      + [line for fn in source.functions
                                         for line in fn.format()]))  # fmt: skip
        self.checks[-1]["functions"] = [fn.to_json() for fn in source.functions]


def gate_all(
    *,
    roots: GateRoots,
    check_source_fn: Callable[..., SourceCheck] | None = None,
    land_fn: Callable[..., list[ExeLand]] | None = None,
    load_fn: Callable[..., Any] | None = None,
    compile_fn: Callable[..., Any] | None = None,
    objdiff_runner: Callable[[Sequence[str]], str] | None = None,
) -> GateResult:
    """Re-prove every matched function and write nothing (D-24): exit 0 only when each is still
    objdiff 100.0 with a passing relocation check and identical bytes, the landed set equals the
    matched set, and both SHA-1s equal config/targets.toml."""
    _committed_src(roots)
    known = load_manifest(roots.manifest)
    run = _AllRun(roots, check_source_fn or check_source, compile_fn or compile_source,
                  objdiff_runner)  # fmt: skip
    matched = _matched(_tables(roots.config_root, known))
    loaded, owners = {}, _owners(roots.config_root, known)
    for target in known:
        stem = exe_stem(target.name)
        if not (Path(roots.config_root) / stem / UNITS_CSV).is_file():
            continue  # cross_check reports matched rows of an EXE that cannot land
        exe = (load_fn or load_exe)(target, orig_dir=roots.orig_dir, manifest=roots.manifest,
                                    config_root=roots.config_root)  # fmt: skip
        loaded[target.name] = exe
        rows = sorted(matched.get(target.name, {}).values(), key=lambda r: r.start)
        for unit in sorted({row.unit for row in rows}):
            run.recheck(exe, target.name, unit, [r for r in rows if r.unit == unit])
    splices = (land_fn or land_all)(
        roots.manifest, orig_dir=roots.orig_dir, config_root=roots.config_root,
        src_root=roots.src_root, build_dir=roots.build_dir, compile_fn=run.compile_fn,
        options=roots.options(), fresh=frozenset(run.fresh), loaded=loaded,
    )  # fmt: skip
    run.problems += cross_check(splices, matched, {}, owners=owners)
    run.problems += [f"{s.exe}: splice {' / '.join(s.format())}" for s in splices if not s.ok]
    run.reports += [line for s in splices for line in s.format()]
    code = EXIT_MISMATCH if run.problems else EXIT_OK
    return GateResult(MODE_ALL, (), code, tuple(run.reports), tuple(run.checks),
                      tuple(run.problems), (), tuple(s.to_json() for s in splices))  # fmt: skip


# ---- gate EXE/UNIT --partial --src FILE ----


def _merge_partial(table: Iterable[StatusRow], functions: Iterable[FunctionCheck], unit: str,
                   sha: str, attempts: int, day: str
                   ) -> tuple[list[StatusRow], list[StatusRow]]:  # fmt: skip
    """The table with a partial row for each unmatched function scoring above 0% (the best
    percent wins, ties keep the earlier row; attempts take the larger count), and those rows."""
    by_start = {row.start: row for row in table}
    touched = []
    for fn in functions:
        percent = round_percent(fn.objdiff_percent)
        old = by_start.get(fn.va)
        if percent <= 0.0 or (old is not None and old.status == MATCHED):
            continue
        row = StatusRow(fn.va, fn.name, unit, PARTIAL, percent, attempts, sha, day)
        if old is not None:
            best = old if old.best_percent >= percent else row
            row = dataclasses.replace(best, attempts=max(old.attempts, attempts))
        by_start[fn.va] = row
        touched.append(row)
    return sorted(by_start.values(), key=lambda r: r.start), touched


def _saved_file(path: Path) -> Path:
    saved = Path(path)
    if saved.suffix != SOURCE_SUFFIX or not saved.is_file():
        raise CheckError(f"--partial --src must name the saved attempt's existing "
                         f"{SOURCE_SUFFIX} file, got {saved}")  # fmt: skip
    return saved


def gate_partial(
    exe: str,
    unit: str,
    saved_file: Path,
    *,
    roots: GateRoots,
    attempts: int = 0,
    today: date | None = None,
    check_source_fn: Callable[..., SourceCheck] | None = None,
    load_fn: Callable[..., Any] | None = None,
    compile_fn: Callable[..., Any] | None = None,
    objdiff_runner: Callable[[Sequence[str]], str] | None = None,
) -> GateResult:
    """Score `saved_file` as unit `unit` and write partial rows (D-21): exit 0 when a function
    that is not matched scored above 0%, 1 when none did (nothing written), CheckError (exit 2)
    for a tool or usage problem."""
    _check_attempts(attempts)
    saved = _saved_file(saved_file)
    known = load_manifest(roots.manifest)
    target = select_exe(known, exe, roots.manifest)
    stem = exe_stem(target.name)
    inputs = (load_fn or load_exe)(target, orig_dir=roots.orig_dir, manifest=roots.manifest,
                                   config_root=roots.config_root)  # fmt: skip
    rows = inputs.unit_rows(unit)
    options = roots.options(src_root=saved.parent)
    if object_root(roots.build_dir, options) == Path(roots.build_dir):
        raise CheckError(f"{saved} would compile into ninja's object paths; save it outside "
                         "the committed src tree")  # fmt: skip
    before = source_sha256(saved)
    source = (check_source_fn or check_source)(
        inputs, unit, saved, rows, build_dir=roots.build_dir,
        compile_fn=compile_fn or compile_source,
        objdiff_runner=objdiff_runner or default_objdiff_runner(f"{exe}/{unit}"), options=options,
    )  # fmt: skip
    if source_sha256(saved) != before:
        raise CheckError(f"{saved} changed while it was checked; gate it again")
    path = status_path(roots.config_root, stem)
    owners = _owners(roots.config_root, [target]).get(target.name, {})
    named = [dataclasses.replace(fn, name=owners[fn.va].name) if fn.va in owners else fn
             for fn in source.functions]  # fmt: skip
    merged, touched = _merge_partial(read_status(path), named, unit, before, attempts,
                                     _today(today))  # fmt: skip
    label = (f"{exe}/{unit}",)
    report = "\n".join([f"check {exe}/{unit} --partial {saved}"]
                       + [line for fn in source.functions for line in fn.format()])  # fmt: skip
    doc = {"exe": exe, "unit": unit, "src": str(saved),
           "functions": [fn.to_json() for fn in source.functions]}  # fmt: skip
    if source.problems:  # M5: an account check would refuse this file; it scores no row
        refused = tuple(f"{exe}/{unit}: {p.format().strip()}" for p in source.problems)
        return GateResult(MODE_PARTIAL, label, EXIT_MISMATCH, (report,), (doc,), refused)
    if not touched:
        none = f"no function of {unit} that is not matched scored above 0%"
        return GateResult(MODE_PARTIAL, label, EXIT_MISMATCH, (report,), (doc,), (none,))
    write_status(path, merged)
    return GateResult(MODE_PARTIAL, label, EXIT_OK, (report,), (doc,), (),
                      tuple(Written(path, row) for row in touched))  # fmt: skip
