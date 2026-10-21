"""Test-only Watcom LIB386 trees and synthetic EXEs for the library matcher.

Every byte here is made up: the module bodies are counting sequences, the libraries come from
tests/omfimage.py and the EXEs from conftest.build_le_image, so no library or game byte is ever
committed. A planted copy of a module body overwrites its masked sites with MASKED_FILL, the way
a linker writes resolved addresses there.
"""

from __future__ import annotations

from pathlib import Path

import omfimage as om
from conftest import build_le_image, fixup_record, write_manifest

OBJ1_BASE = 0x10000
OBJ2_BASE = 0x20000
PLANT_VA = 0x10200  # where the tests plant the first module body in object 1
MASKED_FILL = 0xEE  # what a planted copy holds at the library's masked sites


def body(n: int, seed: int = 0x41) -> bytes:
    """n made-up bytes: a counting sequence from `seed`, with a zero byte written as 0x01."""
    return bytes((seed + i) & 0xFF or 0x01 for i in range(n))


FAKE_CODE = body(40)  # module "fake": abs off32 site at 8, rel32 extern call at 20
FAKE_ABS_SITE = 8
FAKE_CALL_SITE = 20


def abs_fixup(offset: int, seg: int = 1) -> bytes:
    """A segment-relative (M=1) 32-bit offset fixup to segment `seg` of the same module."""
    return om.fixup(offset, location=9, segment_relative=True, frame=(5, None), target=(0, seg))


def call_fixup(offset: int, ext: int = 1) -> bytes:
    """A self-relative 32-bit fixup to extern `ext` (a rel32 call or jump)."""
    return om.fixup(offset, location=9, segment_relative=False, frame=(5, None), target=(2, ext))


def code_module(
    name: str,
    code: bytes,
    *,
    publics: list[tuple[str, int]] | None = None,
    fixups: list[bytes] | None = None,
    externs: list[str] | None = None,
    data: bytes | None = None,
    seg_name: str = "_TEXT",
) -> bytes:
    """One module: a CODE segment (index 1), optionally a DATA segment (index 2)."""
    records = [om.lnames("", seg_name, "CODE", "_DATA", "DATA"), om.segdef32(2, 3, len(code))]
    if data is not None:
        records.append(om.segdef32(4, 5, len(data)))
    records.append(om.pubdef32(1, publics if publics is not None else [(f"{name}_", 0)]))
    if externs:
        records.append(om.extdef(*externs))
    records.append(om.ledata32(1, 0, code))
    if fixups:
        records.append(om.fixupp32(*fixups))
    if data is not None:
        records.append(om.ledata32(2, 0, data))
    return om.module(name, *records)


def fake_module(name: str = "fake", code: bytes = FAKE_CODE) -> bytes:
    return code_module(
        name,
        code,
        publics=[("fake_", 0), ("fake2_", 16)],
        fixups=[abs_fixup(FAKE_ABS_SITE), call_fixup(FAKE_CALL_SITE)],
        externs=["ext_"],
    )


def write_lib(watcom: Path, version: str, relpath: str, modules: list[bytes]) -> Path:
    """Write <watcom>/<version>/LIB386/<relpath> as an OMF library of `modules`."""
    path = watcom / version / "LIB386" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(om.library(modules))
    return path


def planted(code: bytes, sites: tuple[int, ...] = (FAKE_ABS_SITE, FAKE_CALL_SITE)) -> bytes:
    """`code` with MASKED_FILL over the 4 bytes of every fixup site."""
    out = bytearray(code)
    for site in sites:
        out[site : site + 4] = bytes([MASKED_FILL]) * 4
    return bytes(out)


def synth_exe(
    patches: dict[int, bytes], off32_sites: list[tuple[int, int]] | None = None
) -> bytes:
    """A synthetic LE with `patches` written into its pages and an off32 LE fixup at each
    (source VA in page 1 of object 1, target offset in object 2)."""
    sites = off32_sites if off32_sites is not None else [(PLANT_VA + FAKE_ABS_SITE, 0x100)]
    records = b"".join(fixup_record(7, va - OBJ1_BASE, 2, off) for va, off in sites)
    return build_le_image(fixups=[records, b"", b""], patches=patches).data


def planted_fake_exe() -> bytes:
    """The EXE every basic test uses: module "fake" planted at PLANT_VA."""
    return synth_exe({PLANT_VA: planted(FAKE_CODE)})


def cli_workspace(tmp_path: Path, exe: bytes | None = None) -> dict[str, Path]:
    """orig/SYNTH.EXE, its manifest and a Watcom tree holding module "fake" in 10.6."""
    exe = planted_fake_exe() if exe is None else exe
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYNTH.EXE").write_bytes(exe)
    manifest = write_manifest(tmp_path / "targets.toml", {"SYNTH.EXE": exe})
    watcom = tmp_path / "w"
    write_lib(watcom, "10.6", "DOS/CLIB3R.LIB", [fake_module()])
    return {"orig": orig, "manifest": manifest, "watcom": watcom, "out": tmp_path / "out.csv"}
