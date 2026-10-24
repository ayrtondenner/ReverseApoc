"""Headless Ghidra export (SPL-01, D-05, D-16): the analyzeHeadless argv, the driver against a
fake runner, and the adapter that reads the export script's CSV. Every address and name here is
made up; the real run is in the container (plan 05-12)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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


# ---- the adapter refuses bad or empty exports ----


def write_export(path: Path, *lines: str, header: str = HEADER) -> Path:
    path.write_text("\n".join((header, *lines)) + "\n", encoding="utf-8")
    return path


def test_header_only_export(tmp_path):
    path = write_export(tmp_path / "functions.raw.csv")
    with pytest.raises(ghidra.GhidraError, match="export holds no functions"):
        ghidra.read_ghidra_export(path)


def test_rows_sorted_and_unique(tmp_path):
    rows = [
        "0x00010080,0x00010080,0x0001008F,16,1,false,unknown,FUN_00010080",
        "0x00010040,0x00010040,0x0001007F,64,1,false,unknown,FUN_00010040",
        "0x00010000,0x00010000,0x0001003F,64,1,false,unknown,FUN_00010000",
    ]
    path = write_export(tmp_path / "reverse.csv", *rows)
    assert [r.entry for r in ghidra.read_ghidra_export(path)] == [0x10000, 0x10040, 0x10080]

    dup = write_export(tmp_path / "dup.csv", rows[1], rows[0], rows[1])
    with pytest.raises(ghidra.GhidraError, match="0x00010040"):
        ghidra.read_ghidra_export(dup)


@pytest.mark.parametrize(
    ("lines", "header", "needle"),
    [
        ((ROWS[0],), "entry,body_min,name", "header"),
        (("0x0001ZZ40,0x00010040,0x0001007F,64,1,false,unknown,FUN_x",), HEADER, "data row 1"),
        ((ROWS[0], "0x00010100,0x00010100,0x0001010F,16,1,maybe,unknown,f"), HEADER, "data row 2"),
        (("0x00010040,0x00010040,0x0001007F,64,1,false,unknown",), HEADER, "data row 1"),
        (("10040,0x00010040,0x0001007F,64,1,false,unknown,FUN_x",), HEADER, "data row 1"),
    ],
    ids=["wrong-header", "non-hex-address", "bad-thunk", "short-row", "no-0x-prefix"],
)
def test_bad_rows(tmp_path, lines, header, needle):
    path = write_export(tmp_path / "bad.csv", *lines, header=header)
    with pytest.raises(ghidra.GhidraError, match=needle):
        ghidra.read_ghidra_export(path)


def test_quoted_name_reads_back(tmp_path):
    path = write_export(
        tmp_path / "quoted.csv",
        '0x00010000,0x00010000,0x0001000F,16,1,false,unknown,"operator,""odd"""',
    )
    (row,) = ghidra.read_ghidra_export(path)
    assert row.name == 'operator,"odd"'


# ---- version, install and refusals ----


def test_version(tmp_path):
    assert ghidra.ghidra_version(make_install(tmp_path)) == "12.1.4"
    with pytest.raises(ghidra.GhidraError, match="application.properties"):
        ghidra.ghidra_version(tmp_path / "nowhere")


def test_version_without_the_key(tmp_path):
    install = make_install(tmp_path)
    (install / "Ghidra" / "application.properties").write_text("a=b\n", encoding="utf-8")
    with pytest.raises(ghidra.GhidraError, match="application.version"):
        ghidra.ghidra_version(install)


def test_missing_install(tmp_path):
    orig, fake = make_orig(tmp_path), FakeHeadless()
    with pytest.raises(ghidra.GhidraError) as info:
        ghidra.export_functions(EXE, orig, tmp_path / "out", install=tmp_path / "none",
                                runner=fake)  # fmt: skip
    assert "docker compose run --rm build uv run reverseapoc ghidra-export" in str(info.value)
    assert fake.calls == []


def test_missing_exe_is_refused(tmp_path):
    install, fake = make_install(tmp_path), FakeHeadless()
    (tmp_path / "orig").mkdir()
    with pytest.raises(ghidra.GhidraError, match="reverseapoc ingest"):
        ghidra.export_functions(EXE, tmp_path / "orig", tmp_path / "out", install=install,
                                runner=fake)  # fmt: skip
    assert fake.calls == []


def test_unknown_target_is_refused(tmp_path):
    install, orig, fake = make_install(tmp_path), make_orig(tmp_path), FakeHeadless()
    with pytest.raises(ghidra.GhidraError, match="no target named"):
        ghidra.export_functions("../UFO2P.EXE", orig, tmp_path / "out", install=install,
                                runner=fake)  # fmt: skip
    assert fake.calls == []


def test_refuses_output_in_orig(tmp_path):
    install, orig, fake = make_install(tmp_path), make_orig(tmp_path), FakeHeadless()
    with pytest.raises(ghidra.GhidraError, match="inside"):
        ghidra.export_functions(EXE, orig, orig / "ghidra", install=install, runner=fake)
    assert fake.calls == []
    assert not (orig / "ghidra").exists()


@pytest.mark.parametrize(
    ("fake", "needle"),
    [(FakeHeadless(returncode=1), "exit code 1"), (FakeHeadless(write=False), "exit code 0")],
    ids=["exit-1", "no-csv"],
)
def test_runner_failure(tmp_path, fake, needle):
    install, orig = make_install(tmp_path), make_orig(tmp_path)
    with pytest.raises(ghidra.GhidraError, match=needle):
        ghidra.export_functions(EXE, orig, tmp_path / "out", install=install, runner=fake)


def test_runner_failure_never_reads_a_stale_export(tmp_path):
    install, orig = make_install(tmp_path), make_orig(tmp_path)
    out_dir = tmp_path / "out"
    ghidra.export_functions(EXE, orig, out_dir, install=install, runner=FakeHeadless())
    with pytest.raises(ghidra.GhidraError, match="exit code 0"):
        ghidra.export_functions(EXE, orig, out_dir, install=install,
                                runner=FakeHeadless(write=False))  # fmt: skip


# ---- decompile drafts (D-16) ----


def test_drafts_argv(tmp_path):
    install, orig, fake = make_install(tmp_path), make_orig(tmp_path), FakeHeadless()
    asm_dir = tmp_path / "asm"
    result = ghidra.export_drafts(EXE, orig, [0x00010040, 0x00010000], asm_dir, install=install,
                                  runner=fake)  # fmt: skip

    drafts = asm_dir / "ufo2p" / "ghidra"
    assert result.path == drafts
    assert drafts.is_dir()
    assert fake.project_existed == [True]
    (argv,) = fake.calls
    _follows(argv, "-postScript", "ExportDrafts.java", str(drafts), "0x00010040", "0x00010000")
    _follows(argv, "-loader", "LeLoader")
    _follows(argv, "-scriptPath", str(ghidra.SCRIPT_DIR))
    assert (ghidra.SCRIPT_DIR / "ExportDrafts.java").is_file()

    fake2 = FakeHeadless()
    with pytest.raises(ghidra.GhidraError, match="inside"):
        ghidra.export_drafts(EXE, orig, [0x00010000], orig / "asm", install=install, runner=fake2)
    assert fake2.calls == []


def test_drafts_report_written_and_missing(tmp_path):
    install, orig = make_install(tmp_path), make_orig(tmp_path)
    asm_dir = tmp_path / "asm"

    def writes_one(argv, **kwargs):
        out = Path(argv[argv.index("ExportDrafts.java") + 1])
        (out / "func_00010000.c").write_text("/* draft */\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")

    result = ghidra.export_drafts(EXE, orig, [0x00010000, 0x00010040], asm_dir, install=install,
                                  runner=writes_one)  # fmt: skip
    assert result.written == (0x00010000,)
    assert result.missing == (0x00010040,)
    assert result.to_json()["missing"] == ["0x00010040"]


@pytest.mark.parametrize("addresses", [[], [-1], [1 << 32]], ids=["none", "negative", "too-big"])
def test_drafts_refuse_bad_addresses(tmp_path, addresses):
    install, orig, fake = make_install(tmp_path), make_orig(tmp_path), FakeHeadless()
    with pytest.raises(ghidra.GhidraError, match="address"):
        ghidra.export_drafts(EXE, orig, addresses, tmp_path / "asm", install=install, runner=fake)
    assert fake.calls == []


def test_default_outputs_are_gitignored():
    root = ghidra.REPO_ROOT
    ignored = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    for default in (ghidra.DEFAULT_EXPORT_DIR, ghidra.DEFAULT_ASM_DIR):
        top = default.relative_to(root).parts[0]
        assert f"{top}/" in ignored
