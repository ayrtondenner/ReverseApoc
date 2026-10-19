"""Hash manifest loader and orig/ checker."""

from __future__ import annotations

import hashlib
import re

import pytest

from conftest import write_manifest
from reverseapoc.targets import (
    DEFAULT_MANIFEST,
    ManifestError,
    Target,
    check_orig,
    load_manifest,
)


def test_default_manifest_lists_the_three_targets():
    targets = load_manifest()
    assert DEFAULT_MANIFEST.name == "targets.toml"
    by_name = {t.name: t for t in targets}
    assert list(by_name) == ["UFO2P.EXE", "TACP.EXE", "SMKP.EXE"]

    ufo = by_name["UFO2P.EXE"]
    assert ufo.path == "UFOEXE/UFO2P.EXE"
    assert ufo.size == 1705790
    assert ufo.md5 == "d2e874a76344cb9c48afce57357aab31"
    assert ufo.sha1 == "e7488bf3de2efeaa3c1c72d3763eeeb35f727c56"
    assert ufo.crc32 == 0xDBD3B41D

    tac = by_name["TACP.EXE"]
    assert (tac.path, tac.size) == ("TACEXE/TACP.EXE", 3161594)
    assert tac.md5 == "644382a6caa787cff613c50a170b5152"
    assert tac.sha1 == "48ef00969d8880a0a152de1b652853fa7ac27393"

    smk = by_name["SMKP.EXE"]
    assert (smk.path, smk.size) == ("UFOEXE/SMKP.EXE", 271436)
    assert smk.md5 == "2d7933f255348a60536d811391b461ba"
    assert smk.sha1 == "efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc"

    for t in targets:
        assert isinstance(t, Target)
        assert len(t.md5) == 32 and len(t.sha1) == 40


def test_custom_manifest(tmp_path):
    manifest = write_manifest(tmp_path / "m.toml", {"A.EXE": b"alpha"})
    (target,) = load_manifest(manifest)
    assert target.name == "A.EXE"
    assert target.path == "SUB/A.EXE"
    assert target.size == 5
    assert target.sha1 == hashlib.sha1(b"alpha").hexdigest()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("", "no [[targets]]"),
        (
            '[[targets]]\nname = "A.EXE"\npath = "A.EXE"\nsize = 1\n'
            'md5 = "d41d8cd98f00b204e9800998ecf8427e"\n',
            "'sha1'",
        ),
        (
            '[[targets]]\nname = "A.EXE"\npath = "A.EXE"\nsize = "big"\nmd5 = "0"\nsha1 = "0"\n',
            "size",
        ),
        (
            '[[targets]]\nname = "A.EXE"\npath = "A.EXE"\nsize = 1\nmd5 = "xyz"\n'
            'sha1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"\n',
            "md5",
        ),
    ],
)
def test_invalid_manifest(tmp_path, body, message):
    path = tmp_path / "bad.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_manifest(path)


def test_check_orig_all_ok(tmp_path):
    files = {"A.EXE": b"alpha", "B.EXE": b"bravo!"}
    manifest = write_manifest(tmp_path / "m.toml", files)
    orig = tmp_path / "orig"
    orig.mkdir()
    for name, content in files.items():
        (orig / name).write_bytes(content)

    report = check_orig(orig, manifest)
    assert report.ok
    assert [r.status for r in report.results] == ["ok", "ok"]
    assert report.missing == [] and report.mismatched == []
    assert "A.EXE" in report.format() and "OK" in report.format()


def test_check_orig_reports_missing_and_mismatched(tmp_path):
    files = {"A.EXE": b"alpha", "B.EXE": b"bravo!", "C.EXE": b"charlie"}
    manifest = write_manifest(tmp_path / "m.toml", files)
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "A.EXE").write_bytes(b"alpha")
    (orig / "B.EXE").write_bytes(b"BRAVO!")  # same size, different bytes

    report = check_orig(orig, manifest)
    assert not report.ok
    status = {r.target.name: r.status for r in report.results}
    assert status == {"A.EXE": "ok", "B.EXE": "mismatch", "C.EXE": "missing"}
    assert [r.target.name for r in report.missing] == ["C.EXE"]
    (bad,) = report.mismatched
    assert {p.split(":")[0] for p in bad.problems} == {"crc32", "md5", "sha1"}
    text = report.format()
    assert "MISSING" in text and "MISMATCH" in text and "C.EXE" in text


def test_check_orig_size_mismatch(tmp_path):
    manifest = write_manifest(tmp_path / "m.toml", {"A.EXE": b"alpha"})
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "A.EXE").write_bytes(b"alphabet")
    (result,) = check_orig(orig, manifest).results
    assert result.status == "mismatch"
    assert any(p.startswith("size: expected 5, got 8") for p in result.problems)


def test_check_orig_missing_directory(tmp_path):
    manifest = write_manifest(tmp_path / "m.toml", {"A.EXE": b"alpha"})
    report = check_orig(tmp_path / "nowhere", manifest)
    assert not report.ok
    assert [r.status for r in report.results] == ["missing"]
