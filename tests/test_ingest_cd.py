"""`ingest --cd IMAGE`: the [[cd_builds]] executables out of a plain ISO9660 image or a MODE1/2352
raw image into orig/cd/, verified against config/targets.toml. Every image is synthetic
(tests/isoimage.py); no game bytes."""

from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

import pytest

from conftest import write_manifest
from isoimage import SECTOR, build_iso
from reverseapoc.cli import main as cli_main
from reverseapoc.ingest import CD_DIR, ingest_cd, load_cd_builds
from reverseapoc.iso9660 import ISOError

UFO = b"MZ synthetic cityscape build" * 100  # spans two sectors
TAC = b"MZ synthetic tactical build"
TREE = {
    "XCOM3/UFOEXE/UFO2P.EXE": UFO,
    "XCOM3/TACEXE/TACP.EXE": TAC,
    "XCOM3/README.TXT": b"read me",
}
RAW_SECTOR = 2352
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
EDC_ECC = 288


def _bcd(n: int) -> int:
    return (n // 10) << 4 | n % 10


def mode1(image: bytes, *, mode: int = 1) -> bytes:
    """`image` as a MODE1/2352 raw image: sync, BCD MSF address and mode, 2048 data bytes, and
    zeroed EDC/ECC (ingest does not check them) per sector."""
    out = bytearray()
    for lba in range(len(image) // SECTOR):
        frames = lba + 150  # the two-second lead-in
        msf = bytes([_bcd(frames // 4500), _bcd(frames // 75 % 60), _bcd(frames % 75)])
        out += SYNC + msf + bytes([mode]) + image[lba * SECTOR : (lba + 1) * SECTOR]
        out += bytes(EDC_ECC)
    return bytes(out)


def cd_entry(name: str, path: str, content: bytes) -> str:
    return ("[[cd_builds]]\n"
            f'name = "{name}"\n'
            f'path = "{path}"\n'
            f"size = {len(content)}\n"
            f"crc32 = {zlib.crc32(content):#x}\n"
            f'md5 = "{hashlib.md5(content).hexdigest()}"\n'
            f'sha1 = "{hashlib.sha1(content).hexdigest()}"\n')  # fmt: skip


def make_manifest(tmp_path: Path, cd: dict[str, tuple[str, bytes]] | None = None) -> Path:
    """A manifest with one [[targets]] entry (ingest --cd ignores it) and the [[cd_builds]]."""
    path = write_manifest(tmp_path / "targets.toml", {"OTHER.EXE": b"installed build"})
    cd = cd if cd is not None else {
        "UFO2P.EXE": ("XCOM3/UFOEXE/UFO2P.EXE", UFO),
        "TACP.EXE": ("XCOM3/TACEXE/TACP.EXE", TAC),
    }  # fmt: skip
    extra = "".join("\n" + cd_entry(name, rel, data) for name, (rel, data) in cd.items())
    path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return path


def write_image(tmp_path: Path, data: bytes, name: str = "disc.iso") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_load_cd_builds_reads_only_cd_entries(tmp_path):
    builds = load_cd_builds(make_manifest(tmp_path))
    assert [(b.name, b.path, b.size) for b in builds] == [
        ("UFO2P.EXE", "XCOM3/UFOEXE/UFO2P.EXE", len(UFO)),
        ("TACP.EXE", "XCOM3/TACEXE/TACP.EXE", len(TAC)),
    ]


@pytest.mark.parametrize("raw", [False, True], ids=["iso9660", "mode1-2352"])
def test_extracts_and_verifies_both_builds(tmp_path, raw):
    image = build_iso(TREE)
    path = write_image(tmp_path, mode1(image) if raw else image)
    orig = tmp_path / "orig"

    result = ingest_cd(path, orig_dir=orig, manifest=make_manifest(tmp_path))

    assert result.ok
    assert result.layout == ("MODE1/2352" if raw else "ISO9660")
    assert (orig / CD_DIR / "UFO2P.EXE").read_bytes() == UFO
    assert (orig / CD_DIR / "TACP.EXE").read_bytes() == TAC
    assert sorted(p.name for p in (orig / CD_DIR).iterdir()) == ["TACP.EXE", "UFO2P.EXE"]
    text = result.format()
    assert f"OK        UFO2P.EXE  {len(UFO)} bytes  sha1 {hashlib.sha1(UFO).hexdigest()}" in text
    assert "2 ok, 0 mismatched, 0 missing" in text


def test_names_match_case_insensitively(tmp_path):
    image = build_iso(TREE, raw_names={"XCOM3": b"xcom3", "XCOM3/TACEXE/TACP.EXE": b"tacp.exe;1"})
    result = ingest_cd(write_image(tmp_path, image), orig_dir=tmp_path / "orig",
                       manifest=make_manifest(tmp_path))  # fmt: skip
    assert result.ok
    assert (tmp_path / "orig" / CD_DIR / "TACP.EXE").read_bytes() == TAC


def test_a_hash_mismatch_writes_nothing(tmp_path):
    image = build_iso({**TREE, "XCOM3/TACEXE/TACP.EXE": b"MZ another build"})
    orig = tmp_path / "orig"
    result = ingest_cd(write_image(tmp_path, image), orig_dir=orig,
                       manifest=make_manifest(tmp_path))  # fmt: skip
    assert not result.ok
    assert not (orig / CD_DIR / "TACP.EXE").exists()
    assert (orig / CD_DIR / "UFO2P.EXE").read_bytes() == UFO
    assert "MISMATCH  TACP.EXE   size: expected" in result.format()


def test_a_mismatch_leaves_an_existing_file_alone(tmp_path):
    orig = tmp_path / "orig"
    (orig / CD_DIR).mkdir(parents=True)
    (orig / CD_DIR / "TACP.EXE").write_bytes(TAC)
    image = build_iso({**TREE, "XCOM3/TACEXE/TACP.EXE": b"MZ another build"})
    ingest_cd(write_image(tmp_path, image), orig_dir=orig, manifest=make_manifest(tmp_path))
    assert (orig / CD_DIR / "TACP.EXE").read_bytes() == TAC


def test_a_missing_file_is_reported(tmp_path):
    image = build_iso({k: v for k, v in TREE.items() if "TACP" not in k})
    result = ingest_cd(write_image(tmp_path, image), orig_dir=tmp_path / "orig",
                       manifest=make_manifest(tmp_path))  # fmt: skip
    assert not result.ok
    assert "MISSING   TACP.EXE   XCOM3/TACEXE/TACP.EXE is not in the image" in result.format()


def test_a_manifest_without_cd_builds_is_refused(tmp_path):
    manifest = write_manifest(tmp_path / "targets.toml", {"OTHER.EXE": b"x"})
    with pytest.raises(ValueError, match="no \\[\\[cd_builds\\]\\]"):
        load_cd_builds(manifest)


def test_not_a_disc_image_is_refused(tmp_path):
    path = write_image(tmp_path, bytes(40 * SECTOR), "zero.bin")
    with pytest.raises(ISOError, match="neither"):
        ingest_cd(path, orig_dir=tmp_path / "orig", manifest=make_manifest(tmp_path))


def test_a_raw_sector_that_is_not_mode1_is_refused(tmp_path):
    raw = bytearray(mode1(build_iso(TREE)))
    last = len(raw) // RAW_SECTOR - 1  # the last data sector of the cityscape build
    raw[last * RAW_SECTOR + len(SYNC) + 3] = 2  # MODE2
    path = write_image(tmp_path, bytes(raw), "disc.bin")
    with pytest.raises(ISOError, match=f"sector {last} is not a MODE1 sector"):
        ingest_cd(path, orig_dir=tmp_path / "orig", manifest=make_manifest(tmp_path))


def test_a_partial_raw_sector_is_refused(tmp_path):
    path = write_image(tmp_path, mode1(build_iso(TREE)) + b"\x00" * 100, "disc.bin")
    with pytest.raises(ISOError, match="not a whole number of 2352-byte sectors"):
        ingest_cd(path, orig_dir=tmp_path / "orig", manifest=make_manifest(tmp_path))


def test_cli_ingest_cd(tmp_path, capsys):
    path = write_image(tmp_path, mode1(build_iso(TREE)), "disc.bin")
    argv = ["ingest", "--cd", str(path), "--orig", str(tmp_path / "orig"),
            "--manifest", str(make_manifest(tmp_path))]  # fmt: skip
    assert cli_main(argv) == 0
    out = capsys.readouterr().out
    assert "MODE1/2352" in out and "2 ok" in out
    bad = write_image(tmp_path, build_iso({}), "empty.iso")
    argv[2] = str(bad)
    assert cli_main(argv) == 1
