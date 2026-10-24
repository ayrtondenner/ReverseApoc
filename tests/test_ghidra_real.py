"""Ghidra 12.1.4 in the Docker image: the install, a headless import of a synthetic LE, and the
real export of both EXEs (SPL-01, D-05, D-06, D-16).

Every test that needs Ghidra calls requires_ghidra() and skips on the host (D-05: Ghidra lives
only in the container). The synthetic image is built by conftest.build_le_image with made-up
bytes; the real tests read orig/ only and assert on counts and addresses, never on game bytes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import ORIG_DIR, build_le_image, requires_ghidra, write_manifest
from reverseapoc.cli import main as cli_main
from reverseapoc.ghidra import (
    draft_name,
    export_drafts,
    export_functions,
    ghidra_version,
    read_ghidra_export,
)
from reverseapoc.le import LE
from reverseapoc.libmatch import read_runtime_csv, runtime_csv_path

GHIDRA_VERSION = "12.1.4"
LOADER_PROPERTIES = ("Ghidra", "Extensions", "ghidra-lx-loader", "extension.properties")
SYNTH_NAME = "SYNTH.EXE"
SYNTH_ENTRY = 0x10123  # conftest.ENTRY: object 1 (base 0x10000) + 0x123
# xor eax, eax; ret: a made-up function body at the synthetic entry point
SYNTH_CODE = b"\x31\xc0\xc3"


def _properties(path: Path) -> dict[str, str]:
    pairs = (line.partition("=") for line in path.read_text(encoding="utf-8").splitlines())
    return {key.strip(): value.strip() for key, sep, value in pairs if sep}


def test_ghidra_install():
    install = requires_ghidra()
    assert ghidra_version(install) == GHIDRA_VERSION
    loader = _properties(install.joinpath(*LOADER_PROPERTIES))
    assert loader.get("version") == GHIDRA_VERSION


def _synthetic_orig(tmp_path: Path) -> tuple[Path, Path]:
    """(orig dir holding SYNTH.EXE, a manifest naming it)."""
    image = build_le_image(ghidra_loadable=True, patches={SYNTH_ENTRY: SYNTH_CODE}).data
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / SYNTH_NAME).write_bytes(image)
    return orig, write_manifest(tmp_path / "targets.toml", {SYNTH_NAME: image})


def test_headless_imports_a_synthetic_le(tmp_path):
    install = requires_ghidra()
    orig, manifest = _synthetic_orig(tmp_path)
    result = export_functions(
        SYNTH_NAME, orig, tmp_path / "out", install=install, manifest=manifest
    )
    assert result.count >= 1
    entries = {row.entry for row in read_ghidra_export(result.path)}
    assert SYNTH_ENTRY in entries  # an LE object address, read back as written


def test_headless_drafts_a_synthetic_le(tmp_path):
    # 05-10 review: ExportDrafts.java resolves addresses with toAddr(long), in the default
    # address space; an LE object address must resolve to the function there.
    install = requires_ghidra()
    orig, manifest = _synthetic_orig(tmp_path)
    result = export_drafts(
        SYNTH_NAME, orig, [SYNTH_ENTRY], tmp_path / "asm", install=install, manifest=manifest
    )
    assert result.written == (SYNTH_ENTRY,)
    assert result.missing == ()
    assert (result.path / f"func_{SYNTH_ENTRY:08X}.c").stat().st_size > 0


# ---- the ghidra-export verb (host-runnable) ----


def test_ghidra_export_verb_host_message(monkeypatch, tmp_path, capsys):
    # D-05: without an install the verb fails early and names the container command.
    monkeypatch.setenv("GHIDRA_INSTALL_DIR", str(tmp_path))
    assert cli_main(["ghidra-export", "UFO2P.EXE", "--out", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "docker compose run --rm build uv run reverseapoc ghidra-export" in err


def test_ghidra_export_verb_refuses_an_unknown_exe(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GHIDRA_INSTALL_DIR", str(tmp_path))
    assert cli_main(["ghidra-export", "NOPE.EXE", "--out", str(tmp_path / "out")]) == 1
    assert "no target named 'NOPE.EXE'" in capsys.readouterr().err


# ---- the real export of both EXEs (container, orig/) ----

REAL_EXES = ("UFO2P.EXE", "TACP.EXE")
MIN_FUNCTIONS = 1_300  # research Pattern 2: 1408 (UFO2P) and 1498 (TACP) at full analysis
MIN_RUNTIME_STARTS = 70  # runtime.csv rows whose start Ghidra also finds
DATA_OBJECT_NOISE = 1  # one-address "functions" Ghidra makes in the data object, per EXE


def _real_param(name: str):
    return pytest.param(
        name,
        id=name,
        marks=pytest.mark.skipif(
            not (ORIG_DIR / name).is_file(),
            reason=f"orig/{name} not present (run uv run reverseapoc ingest)",
        ),
    )


@pytest.fixture(scope="module", params=[_real_param(name) for name in REAL_EXES])
def real_export(request, tmp_path_factory):
    """(name, LE, export rows) for one EXE, analysed once per module."""
    install = requires_ghidra()
    name = request.param
    out = tmp_path_factory.mktemp(f"ghidra-{name}")
    result = export_functions(name, ORIG_DIR, out, install=install)
    return name, LE(ORIG_DIR / name), read_ghidra_export(result.path)


def test_export_real_count(real_export):
    _, _, rows = real_export
    assert len(rows) >= MIN_FUNCTIONS


def test_export_real_entries_in_code_object(real_export):
    # Measured 2026-10-24: Ghidra also makes ONE function in each EXE's data object, a
    # one-address body (FUN_0013bd40 in UFO2P, FUN_002b405c in TACP) with no code behind it.
    # It is analysis noise, never a start candidate: reconcile (05-16) drops entries outside
    # the code object. Every other entry lies in the code object.
    _, le, rows = real_export
    code, data = le.objects[0], le.objects[1]
    outside = [row for row in rows if not code.contains(row.entry)]
    assert len(outside) <= DATA_OBJECT_NOISE
    assert all(data.contains(row.entry) and row.addresses == 1 for row in outside)


def test_export_real_has_the_le_entry_point(real_export):
    _, le, rows = real_export
    assert le.entry_va in {row.entry for row in rows}


def test_export_real_finds_runtime_starts(real_export):
    name, _, rows = real_export
    entries = {row.entry for row in rows}
    starts = {row.start for row in read_runtime_csv(runtime_csv_path(name))}
    assert len(starts & entries) >= MIN_RUNTIME_STARTS


@pytest.mark.skipif(
    not (ORIG_DIR / "UFO2P.EXE").is_file(),
    reason="orig/UFO2P.EXE not present (run uv run reverseapoc ingest)",
)
def test_drafts_real(tmp_path):
    # D-16, and the 05-10 review: the LE entry and the cmain386 runtime row are LE object
    # addresses that ExportDrafts.java's toAddr(long) must resolve to a function.
    install = requires_ghidra()
    name = "UFO2P.EXE"
    cmain = [r.start for r in read_runtime_csv(runtime_csv_path(name)) if r.module == "cmain386"]
    assert len(cmain) == 1
    wanted = [LE(ORIG_DIR / name).entry_va, *cmain]
    result = export_drafts(name, ORIG_DIR, wanted, tmp_path / "asm", install=install)
    assert result.missing == ()
    assert set(result.written) == set(wanted)
    sizes = [(result.path / draft_name(address)).stat().st_size for address in wanted]
    assert all(size > 0 for size in sizes)
