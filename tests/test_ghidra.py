"""Headless Ghidra export (SPL-01, D-05, D-16): the analyzeHeadless argv, the driver against a
fake runner, and the adapter that reads the export script's CSV. Every address and name here is
made up; the real run is in the container (plan 05-12)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from reverseapoc import ghidra

EXE = "UFO2P.EXE"
HEADER = ",".join(ghidra.EXPORT_COLUMNS)
ROWS = (
    "0x00010040,0x00010040,0x0001007F,64,1,false,__stdcall,FUN_00010040",
    "0x00010000,0x00010000,0x0001003F,48,2,true,unknown,thunk_entry",
)


def make_install(root: Path, version: str = "12.1.4") -> Path:
    """A tmp tree shaped like a Ghidra install: support/analyzeHeadless and the properties."""
    install = root / "ghidra"
    (install / "support").mkdir(parents=True)
    (install / "support" / "analyzeHeadless").write_text("#!/bin/sh\n", encoding="utf-8")
    (install / "Ghidra").mkdir()
    props = install / "Ghidra" / "application.properties"
    props.write_text(f"application.name=Ghidra\napplication.version={version}\n", encoding="utf-8")
    return install


def make_orig(root: Path) -> Path:
    orig = root / "orig"
    orig.mkdir()
    (orig / EXE).write_bytes(b"MZ not a game file")
    return orig


class FakeHeadless:
    """Records each argv; checks the project dir exists; writes `rows` after the script name."""

    def __init__(self, rows=ROWS, returncode: int = 0, write: bool = True):
        self.rows, self.returncode, self.write = rows, returncode, write
        self.calls: list[list[str]] = []
        self.project_existed: list[bool] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.project_existed.append(Path(argv[1]).is_dir())
        if self.write and "ExportFunctions.java" in argv:
            out = Path(argv[argv.index("ExportFunctions.java") + 1])
            out.write_text("\n".join((HEADER, *self.rows)) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, self.returncode, "headless out", "headless err")


def _follows(argv: list[str], *parts: str) -> int:
    """The index of `parts` as a contiguous run in argv; fails when absent."""
    for i in range(len(argv) - len(parts) + 1):
        if tuple(argv[i : i + len(parts)]) == parts:
            return i
    raise AssertionError(f"{parts} not in {argv}")


def test_export_runs_headless_and_reads_the_csv(tmp_path):
    install, orig = make_install(tmp_path), make_orig(tmp_path)
    out_dir = tmp_path / "build" / "ghidra"
    fake = FakeHeadless()

    result = ghidra.export_functions(EXE, orig, out_dir, install=install, runner=fake)

    assert result.count == 2
    assert result.path == out_dir / "ufo2p" / "functions.raw.csv"
    assert result.seconds >= 0
    assert fake.project_existed == [True]
    (argv,) = fake.calls
    assert argv[0] == str(install / "support" / "analyzeHeadless")
    assert argv[2] == "p_UFO2P"
    order = [
        _follows(argv, "-import", str(orig / EXE)),
        _follows(argv, "-loader", "LeLoader"),
        _follows(argv, "-processor", "watcom:LE:32:default"),
        _follows(argv, "-cspec", "watcom"),
        _follows(argv, "-postScript", "ExportFunctions.java", str(result.path)),
        _follows(argv, "-scriptPath", str(ghidra.SCRIPT_DIR)),
        _follows(argv, "-deleteProject"),
    ]
    assert order == sorted(order)
    assert (ghidra.SCRIPT_DIR / "ExportFunctions.java").is_file()
    assert not Path(argv[1]).exists()  # the temporary project dir is gone afterwards

    rows = ghidra.read_ghidra_export(result.path)
    assert [r.entry for r in rows] == [0x00010000, 0x00010040]
    first = rows[0]
    assert first == ghidra.GhidraFunction(
        entry=0x00010000,
        body_min=0x00010000,
        body_max=0x0001003F,
        addresses=48,
        ranges=2,
        thunk=True,
        calling_convention="unknown",
        name="thunk_entry",
    )
    assert result.to_json() == {"path": str(result.path), "count": 2, "seconds": result.seconds}
    assert "2 functions" in result.format()
