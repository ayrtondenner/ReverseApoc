"""Ghidra 12.1.4 in the Docker image: the install, a headless import of a synthetic LE, and the
real export of both EXEs (SPL-01, D-05, D-06, D-16).

Every test that needs Ghidra calls requires_ghidra() and skips on the host (D-05: Ghidra lives
only in the container). The synthetic image is built by conftest.build_le_image with made-up
bytes; the real tests read orig/ only and assert on counts and addresses, never on game bytes.
"""

from __future__ import annotations

from pathlib import Path

from conftest import build_le_image, requires_ghidra, write_manifest
from reverseapoc.ghidra import export_drafts, export_functions, ghidra_version, read_ghidra_export

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
