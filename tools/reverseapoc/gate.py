"""`reverseapoc gate EXE/UNIT [EXE/UNIT ...]`: the only writer of config/<exe>/status.csv (D-21).

gate runs `check` (check.check_unit) for each target and writes `matched` rows (status.py) for
every function each target unit defines, only when every check exits 0. The rows carry
best_percent 100.00, the LF-normalised SHA-256 of the unit file (taken before and after the
check, so a file edited while it ran is refused), `--attempts N` (0 = by hand) and today's UTC
date. On any mismatch gate writes nothing and exits 1; on a tool error (CheckError, StatusError,
the CLI's tool errors) it writes nothing and exits 2.

No flag, environment variable or helper writes a matched row without a passing check: the
verdict is check's own, in the container, never an agent's transcript (D-24, AGT-01).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .check import (
    EXIT_MISMATCH,
    EXIT_OK,
    CheckError,
    CheckResult,
    check_unit,  # looked up at call time (`check_fn or check_unit`), so a test can patch it
    exe_stem,
    select_exe,
)
from .functions import _address
from .status import (
    MATCHED,
    PERCENT_MAX,
    StatusRow,
    format_percent,
    lf_sha256,
    read_status,
    status_path,
    write_status,
)
from .targets import load_manifest

MODE_UNIT = "unit"


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


@dataclass(frozen=True)
class Written:
    """One row gate wrote, and the table it went to."""

    path: Path
    row: StatusRow

    def line(self) -> str:
        r = self.row
        return (f"wrote {r.status} {r.name}  {_address(r.start)}  {r.unit}  "
                f"{format_percent(r.best_percent)}  -> {self.path}")

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

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK

    def to_json(self) -> dict[str, Any]:
        return {"mode": self.mode, "targets": list(self.targets), "ok": self.ok,
                "exit_code": self.exit_code, "checks": list(self.checks),
                "problems": list(self.problems),
                "written": [w.to_json() for w in self.written]}  # fmt: skip

    def format(self) -> str:
        lines = [*self.reports]
        lines += [f"GATE REFUSED  {problem}" for problem in self.problems]
        lines += [w.line() for w in self.written]
        if self.ok and not self.written:
            lines.append("wrote nothing")
        lines.append("ok" if self.ok else "MISMATCH: status.csv not written")
        return "\n".join(lines)


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


def _resolve(targets: Iterable[tuple[str, str]], manifest: Path) -> list[_Target]:
    known = load_manifest(manifest)
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
    src = Path(roots.src_root) / target.stem / f"{target.unit}.c"
    before = _hash_or_none(src)
    result = check_fn(target.exe, target.unit, **roots.check_kwargs())
    after = _hash_or_none(src)
    if before is None or after != before:
        raise CheckError(f"{src} changed while it was checked; gate it again")
    return result, after


def _matched_rows(result: CheckResult, unit: str, sha: str, attempts: int, today: str
                  ) -> list[StatusRow]:  # fmt: skip
    return [StatusRow(fn.va, fn.name, unit, MATCHED, PERCENT_MAX, attempts, sha, today)
            for fn in result.functions]  # fmt: skip


def merge_matched(rows: Iterable[StatusRow], new: Iterable[StatusRow]) -> list[StatusRow]:
    """`rows` with each of `new` in place of the row at its start, sorted by start."""
    by_start = {row.start: row for row in rows}
    for row in new:
        by_start[row.start] = row
    return sorted(by_start.values(), key=lambda r: r.start)


def _report(result: CheckResult) -> tuple[str, dict[str, Any]]:
    return result.format(), result.to_json()


def gate_units(
    targets: Sequence[tuple[str, str]],
    *,
    roots: GateRoots,
    attempts: int = 0,
    today: date | None = None,
    check_fn: Callable[..., CheckResult] | None = None,
) -> GateResult:
    """Check each (EXE, UNIT) of `targets`; when every check exits 0, write matched rows for
    every function they define, else write nothing (exit 1)."""
    _check_attempts(attempts)
    check_fn = check_fn or check_unit
    resolved = _resolve(targets, roots.manifest)
    labels = tuple(t.label for t in resolved)
    reports, docs, passed = [], [], []
    for target in resolved:
        result, sha = _checked(target, roots, check_fn)
        report, doc = _report(result)
        reports.append(report)
        docs.append(doc)
        if result.exit_code != EXIT_OK:
            return GateResult(MODE_UNIT, labels, EXIT_MISMATCH, tuple(reports), tuple(docs))
        passed.append((target, result, sha))
    day = _today(today)
    new: dict[str, list[StatusRow]] = {}
    for target, result, sha in passed:
        new.setdefault(target.stem, []).extend(_matched_rows(result, target.unit, sha, attempts,
                                                             day))  # fmt: skip
    written = _write_tables(roots.config_root, new)
    return GateResult(MODE_UNIT, labels, EXIT_OK, tuple(reports), tuple(docs), (), written)


def _write_tables(config_root: Path, new: dict[str, list[StatusRow]]) -> tuple[Written, ...]:
    """Every table merged first, then written: a refused row writes no table."""
    tables = {}
    for stem, rows in sorted(new.items()):
        path = status_path(config_root, stem)
        tables[path] = merge_matched(read_status(path), rows)
    for path, rows in tables.items():
        write_status(path, rows)
    return tuple(Written(status_path(config_root, stem), row) for stem, rows in sorted(new.items())
                 for row in sorted(rows, key=lambda r: r.start))  # fmt: skip


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

