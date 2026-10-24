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
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .libmatch import LibMatchError, select_target
from .targets import DEFAULT_MANIFEST, load_manifest

SCRIPT_DIR = Path(__file__).parent / "ghidra_scripts"
EXPORT_SCRIPT = "ExportFunctions.java"
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


def _target_name(target_name: str, manifest: Path | None) -> str:
    """The manifest name `target_name` selects; free text never becomes a path."""
    path = Path(manifest) if manifest is not None else DEFAULT_MANIFEST
    try:
        return select_target(load_manifest(path), target_name, path).name
    except LibMatchError as exc:
        raise GhidraError(str(exc)) from exc


def _stem(name: str) -> str:
    return PurePosixPath(name).stem


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
    """Run analyzeHeadless on orig_dir/<EXE> and write out_dir/<exe>/functions.raw.csv."""
    name = _target_name(target_name, manifest)
    install = Path(install) if install is not None else install_dir()
    runner = runner if runner is not None else subprocess.run
    out_csv = Path(out_dir) / _stem(name).lower() / EXPORT_NAME
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv.unlink(missing_ok=True)  # a stale export must never pass for this run's
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="reverseapoc-ghidra-") as project:
        argv = headless_argv(install, Path(project), f"p_{_stem(name)}", Path(orig_dir) / name,
                             out_csv, max_cpu=max_cpu)  # fmt: skip
        runner(argv, **_CAPTURE)
    rows = read_ghidra_export(out_csv)
    return ExportResult(out_csv, len(rows), round(time.monotonic() - start, 3))


# ---- the export adapter ----


def _parse_row(cells: list[str]) -> GhidraFunction:
    entry, body_min, body_max, addresses, ranges, thunk, convention, name = cells
    return GhidraFunction(
        entry=int(entry, 16),
        body_min=int(body_min, 16),
        body_max=int(body_max, 16),
        addresses=int(addresses),
        ranges=int(ranges),
        thunk=thunk == "true",
        calling_convention=convention,
        name=name,
    )


def read_ghidra_export(path: Path) -> list[GhidraFunction]:
    """The rows of an ExportFunctions.java CSV, sorted by entry."""
    text = Path(path).read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, [])
    if tuple(header) != EXPORT_COLUMNS:
        raise GhidraError(f"{path}: header is not {','.join(EXPORT_COLUMNS)}")
    rows = [_parse_row(cells) for cells in reader if cells]
    return sorted(rows, key=lambda row: row.entry)
