"""Headless Ghidra export (SPL-01, D-03, D-05): the analyzeHeadless driver and the adapter that
reads what the committed export script writes.

Ghidra 12.1.4 with the lastonesky LE loader runs only in the container (D-05: no host install, no
fetch or install verbs here). The driver builds the analyzeHeadless argv as a list from named parts,
imports orig/<EXE> into a temporary project that is deleted afterwards, and runs the committed Java
GhidraScript `ghidra_scripts/ExportFunctions.java` (Java because 12.1.4 ships Jython uninstalled and
PyGhidra's JPype wheels stop at cp313). The export holds function entries, body bounds and names
only. Ghidra never supplies bytes, instructions or relocations: target bytes and fixups come from
le.py alone (P4), and downstream only `entry` is a start candidate, because Ghidra bodies are
address sets, not contiguous ranges.
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .libmatch import LibMatchError, refuse_output, select_target
from .targets import DEFAULT_MANIFEST, load_manifest

SCRIPT_DIR = Path(__file__).parent / "ghidra_scripts"
EXPORT_SCRIPT = "ExportFunctions.java"
DRAFTS_SCRIPT = "ExportDrafts.java"
DRAFTS_DIR = "ghidra"  # drafts go to the gitignored asm/<exe>/ghidra/ (D-16), never committed
# D-05: Ghidra is never installed on the host and this module never fetches or installs it.
CONTAINER_HINT = "docker compose run --rm build uv run reverseapoc ghidra-export {exe}"
_TAIL_LINES = 5  # output lines quoted in a failed run's error
_MAX_ADDRESS = 0xFFFFFFFF  # LE linear addresses are 32-bit
LOADER = "LeLoader"  # analyzeHeadless takes the loader's class simple name
PROCESSOR = "watcom:LE:32:default"  # passed explicitly so a loader update cannot change it
CSPEC = "watcom"
DEFAULT_INSTALL = Path("/opt/ghidra")  # where the Docker image installs Ghidra
HEADLESS = ("support", "analyzeHeadless")
EXPORT_NAME = "functions.raw.csv"
EXPORT_COLUMNS = (
    "entry",
    "body_min",
    "body_max",
    "addresses",
    "ranges",
    "thunk",
    "calling_convention",
    "name",
)

# How analyzeHeadless is started: list argv, no shell, output captured as text.
_CAPTURE: dict[str, Any] = dict(
    capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
)

Runner = Callable[..., subprocess.CompletedProcess]


class GhidraError(ValueError):
    """The export cannot run safely, or its output is not a valid function list."""


@dataclass(frozen=True)
class GhidraFunction:
    """One row of the export: addresses and a name, never bytes."""

    entry: int
    body_min: int
    body_max: int
    addresses: int
    ranges: int
    thunk: bool
    calling_convention: str
    name: str


@dataclass(frozen=True)
class ExportResult:
    path: Path
    count: int
    seconds: float

    def format(self) -> str:
        return f"{self.path}: {self.count} functions exported in {self.seconds:.1f}s"

    def to_json(self) -> dict[str, Any]:
        return {"path": str(self.path), "count": self.count, "seconds": self.seconds}


def install_dir() -> Path:
    """The Ghidra install: GHIDRA_INSTALL_DIR when set, read at call time, else /opt/ghidra."""
    return Path(os.environ.get("GHIDRA_INSTALL_DIR") or DEFAULT_INSTALL)


def headless_argv(
    install: Path,
    project_dir: Path,
    project_name: str,
    exe_path: Path,
    out_csv: Path,
    *,
    max_cpu: int = 4,
) -> list[str]:
    """The analyzeHeadless argv that imports `exe_path` and runs ExportFunctions.java."""
    return _argv(install, project_dir, project_name, exe_path, EXPORT_SCRIPT, [str(out_csv)],
                 max_cpu=max_cpu)  # fmt: skip


def _argv(
    install: Path,
    project_dir: Path,
    project_name: str,
    exe_path: Path,
    script: str,
    script_args: list[str],
    *,
    max_cpu: int,
) -> list[str]:
    return [
        str(Path(install).joinpath(*HEADLESS)),
        str(project_dir),
        project_name,
        "-import",
        str(exe_path),
        "-loader",
        LOADER,
        "-processor",
        PROCESSOR,
        "-cspec",
        CSPEC,
        "-postScript",
        script,
        *script_args,
        "-scriptPath",
        str(SCRIPT_DIR),
        "-deleteProject",
        "-max-cpu",
        str(max_cpu),
    ]


# ---- refusals and the run itself ----


def _target_name(target_name: str, manifest: Path | None) -> str:
    """The manifest name `target_name` selects; free text never becomes a path."""
    path = Path(manifest) if manifest is not None else DEFAULT_MANIFEST
    try:
        return select_target(load_manifest(path), target_name, path).name
    except LibMatchError as exc:
        raise GhidraError(str(exc)) from exc


def _stem(name: str) -> str:
    return PurePosixPath(name).stem


def _refuse_inside_orig(path: Path, orig_dir: Path) -> None:
    """orig/ is only ever read: no export or draft is written inside it."""
    try:
        refuse_output(path, orig_dir)
    except LibMatchError as exc:
        raise GhidraError(str(exc)) from exc


def _check_install(install: Path, name: str) -> None:
    """support/analyzeHeadless under `install`, or the hint that Ghidra lives in the container."""
    headless = Path(install).joinpath(*HEADLESS)
    if not headless.is_file():
        raise GhidraError(
            f"{headless} not found. Ghidra runs in the container: "
            f"{CONTAINER_HINT.format(exe=_stem(name).lower())}"
        )


def _check_exe(orig_dir: Path, name: str) -> Path:
    exe = Path(orig_dir) / name
    if not exe.is_file():
        raise GhidraError(f"{exe} not found; run `uv run reverseapoc ingest`")
    return exe


def _tail(proc: subprocess.CompletedProcess) -> str:
    """The last lines of the run's output, for an error message."""
    lines = f"{proc.stdout or ''}\n{proc.stderr or ''}".strip().splitlines()
    return " | ".join(lines[-_TAIL_LINES:]) or "no output"


def _preflight(target_name: str, orig_dir: Path, out: Path, install: Path | None,
               manifest: Path | None, leaf: str) -> tuple[str, Path, Path]:  # fmt: skip
    """Every refusal before anything is written or run: the manifest name, an output inside
    orig/, a missing install (with the container hint) and a missing EXE. Returns the name,
    the output path out/<exe>/<leaf> and the install."""
    name = _target_name(target_name, manifest)
    path = Path(out) / _stem(name).lower() / leaf
    _refuse_inside_orig(path, orig_dir)
    install = Path(install) if install is not None else install_dir()
    _check_install(install, name)
    _check_exe(orig_dir, name)
    return name, path, install


def _run_headless(
    name: str,
    orig_dir: Path,
    install: Path,
    runner: Runner | None,
    script: str,
    script_args: list[str],
    max_cpu: int,
) -> subprocess.CompletedProcess:
    """Run analyzeHeadless on orig_dir/<name> in a temporary project that exists before the run
    (Pitfall 6) and is deleted after it; a non-zero exit raises naming the exit code."""
    exe = Path(orig_dir) / name
    runner = runner if runner is not None else subprocess.run
    with tempfile.TemporaryDirectory(prefix="reverseapoc-ghidra-") as project:
        argv = _argv(install, Path(project), f"p_{_stem(name)}", exe, script, script_args,
                     max_cpu=max_cpu)  # fmt: skip
        proc = runner(argv, **_CAPTURE)
    if proc.returncode != 0:
        raise GhidraError(f"analyzeHeadless exit code {proc.returncode} on {exe}: {_tail(proc)}")
    return proc


# ---- the function export ----


def export_functions(
    target_name: str,
    orig_dir: Path,
    out_dir: Path,
    *,
    install: Path | None = None,
    runner: Runner | None = None,
    manifest: Path | None = None,
    max_cpu: int = 4,
) -> ExportResult:
    """Run analyzeHeadless with ExportFunctions.java on orig_dir/<EXE> and read back
    out_dir/<exe>/functions.raw.csv. Refuses an output inside orig_dir, a missing install and a
    missing EXE before anything runs; a failed run or a missing CSV raises with the exit code."""
    name, out_csv, install = _preflight(target_name, orig_dir, out_dir, install, manifest,
                                        EXPORT_NAME)  # fmt: skip
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv.unlink(missing_ok=True)  # a stale export must never pass for this run's
    start = time.monotonic()
    proc = _run_headless(name, orig_dir, install, runner, EXPORT_SCRIPT, [str(out_csv)], max_cpu)
    if not out_csv.is_file():
        raise GhidraError(
            f"analyzeHeadless exit code {proc.returncode} but {out_csv} was not written "
            f"(did {EXPORT_SCRIPT} fail?): {_tail(proc)}"
        )
    rows = read_ghidra_export(out_csv)
    return ExportResult(out_csv, len(rows), round(time.monotonic() - start, 3))


# ---- decompile drafts (D-16) ----


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def draft_name(address: int) -> str:
    """The draft file for the function at `address`: func_XXXXXXXX.c."""
    return f"func_{address:08X}.c"


@dataclass(frozen=True)
class DraftResult:
    path: Path
    written: tuple[int, ...]
    missing: tuple[int, ...]
    seconds: float

    def format(self) -> str:
        lines = [f"{self.path}: {len(self.written)} drafts written in {self.seconds:.1f}s"]
        lines += [f"  no draft for {_hex(address)}" for address in self.missing]
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "written": [_hex(address) for address in self.written],
            "missing": [_hex(address) for address in self.missing],
            "seconds": self.seconds,
        }


def _check_address(address: object) -> int:
    if isinstance(address, bool) or not isinstance(address, int):
        raise GhidraError(f"address {address!r} is not an integer")
    if not 0 <= address <= _MAX_ADDRESS:
        raise GhidraError(f"address {address:#x} is outside 0x0..{_hex(_MAX_ADDRESS)}")
    return address


def _check_addresses(addresses: Sequence[int]) -> tuple[int, ...]:
    """At least one address, each a 32-bit unsigned int; duplicates dropped, order kept."""
    if not addresses:
        raise GhidraError("export_drafts needs at least one address")
    return tuple(dict.fromkeys(_check_address(address) for address in addresses))


def export_drafts(
    target_name: str,
    orig_dir: Path,
    addresses: Sequence[int],
    asm_dir: Path,
    *,
    install: Path | None = None,
    runner: Runner | None = None,
    manifest: Path | None = None,
    max_cpu: int = 4,
) -> DraftResult:
    """Decompile the functions at `addresses` with ExportDrafts.java into the gitignored
    asm_dir/<exe>/ghidra/func_XXXXXXXX.c. Drafts are a reading aid, never a match (D-16); an
    address with no function is reported in `missing`, not raised."""
    wanted = _check_addresses(addresses)
    name, drafts, install = _preflight(target_name, orig_dir, asm_dir, install, manifest,
                                       DRAFTS_DIR)  # fmt: skip
    drafts.mkdir(parents=True, exist_ok=True)
    for address in wanted:  # a stale draft must never pass for this run's
        (drafts / draft_name(address)).unlink(missing_ok=True)
    start = time.monotonic()
    script_args = [str(drafts), *(_hex(address) for address in wanted)]
    _run_headless(name, orig_dir, install, runner, DRAFTS_SCRIPT, script_args, max_cpu)
    written = tuple(a for a in wanted if (drafts / draft_name(a)).is_file())
    missing = tuple(a for a in wanted if a not in written)
    return DraftResult(drafts, written, missing, round(time.monotonic() - start, 3))


# ---- the export adapter ----

_HEX_CELL = re.compile(r"0x[0-9A-F]{8}")  # what ExportFunctions.java writes: 0x%08X
_COUNT_CELL = re.compile(r"[0-9]+")
_THUNK = {"true": True, "false": False}


def _address(cell: str, column: str) -> int:
    if not _HEX_CELL.fullmatch(cell):
        raise ValueError(f"{column} {cell!r} is not 0x and 8 upper-case hex digits")
    return int(cell, 16)


def _count(cell: str, column: str) -> int:
    if not _COUNT_CELL.fullmatch(cell):
        raise ValueError(f"{column} {cell!r} is not a decimal count")
    return int(cell)


def _thunk(cell: str) -> bool:
    if cell not in _THUNK:
        raise ValueError(f"thunk {cell!r} is not true or false")
    return _THUNK[cell]


def _parse_row(cells: list[str]) -> GhidraFunction:
    if len(cells) != len(EXPORT_COLUMNS):
        raise ValueError(f"expected {len(EXPORT_COLUMNS)} cells, got {len(cells)}")
    entry, body_min, body_max, addresses, ranges, thunk, convention, name = cells
    if not name:
        raise ValueError("empty name")
    row = GhidraFunction(
        entry=_address(entry, "entry"),
        body_min=_address(body_min, "body_min"),
        body_max=_address(body_max, "body_max"),
        addresses=_count(addresses, "addresses"),
        ranges=_count(ranges, "ranges"),
        thunk=_thunk(thunk),
        calling_convention=convention,
        name=name,
    )
    if row.body_min > row.body_max:
        raise ValueError(f"body_min {body_min} lies after body_max {body_max}")
    return row


def _read_rows(path: Path) -> list[GhidraFunction]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise GhidraError(f"{path}: not UTF-8 ({exc})") from exc
    reader = csv.reader(io.StringIO(text))
    if tuple(next(reader, ())) != EXPORT_COLUMNS:
        raise GhidraError(f"{path}: header is not {','.join(EXPORT_COLUMNS)}")
    rows = []
    for number, cells in enumerate(reader, start=1):
        try:
            rows.append(_parse_row(cells))
        except ValueError as exc:
            raise GhidraError(f"{path}: data row {number}: {exc}") from exc
    return rows


def _check_unique(path: Path, rows: list[GhidraFunction]) -> None:
    seen: set[int] = set()
    for row in rows:
        if row.entry in seen:
            raise GhidraError(f"{path}: duplicate entry {_hex(row.entry)}")
        seen.add(row.entry)


def read_ghidra_export(path: Path) -> list[GhidraFunction]:
    """The rows of an ExportFunctions.java CSV, sorted by entry. A header-only export, a wrong
    header, a malformed row (named by its data row number) and a duplicated entry (named by its
    address) are refused. Downstream only `entry` is a start candidate: bodies are address sets."""
    rows = _read_rows(path)
    if not rows:
        raise GhidraError(f"{path}: export holds no functions")
    _check_unique(path, rows)
    return sorted(rows, key=lambda row: row.entry)


# ---- version (D-06 smoke test) ----

_VERSION_KEY = "application.version"


def ghidra_version(install: Path | None = None) -> str:
    """`application.version` from <install>/Ghidra/application.properties; analyzeHeadless has
    no -version flag (it prints usage)."""
    install = Path(install) if install is not None else install_dir()
    props = install / "Ghidra" / "application.properties"
    try:
        text = props.read_text(encoding="utf-8")
    except OSError as exc:
        raise GhidraError(f"{props}: cannot read ({exc})") from exc
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == _VERSION_KEY and value.strip():
            return value.strip()
    raise GhidraError(f"{props}: no {_VERSION_KEY}")
