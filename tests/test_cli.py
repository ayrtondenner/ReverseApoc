"""Command line: ingest, check-orig, parse-le."""

from __future__ import annotations

import hashlib
import json

import pytest

from conftest import OUTER_STUB_SIZE, write_manifest
from isoimage import build_iso
from reverseapoc.cli import main
from reverseapoc.watcom import MEDIA_NOTICE


def test_parse_le_text(synthetic_le_path, capsys):
    assert main(["parse-le", str(synthetic_le_path)]) == 0
    out = capsys.readouterr().out
    assert "LE header" in out
    assert "0x00010000" in out and "0x00020000" in out
    assert "fixups" in out


def test_parse_le_json(synthetic_le_path, capsys):
    assert main(["parse-le", str(synthetic_le_path), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["stub_size"] == OUTER_STUB_SIZE
    assert [o["base"] for o in summary["objects"]] == [0x10000, 0x20000]


def test_parse_le_rejects_non_le(tmp_path, capsys):
    path = tmp_path / "NOTLE.EXE"
    path.write_bytes(b"MZ" + bytes(0x100))
    assert main(["parse-le", str(path)]) == 1
    assert "no LE header" in capsys.readouterr().err


def test_parse_le_missing_file(tmp_path, capsys):
    assert main(["parse-le", str(tmp_path / "nope.exe")]) == 1
    assert "nope.exe" in capsys.readouterr().err


def test_check_orig_exit_codes(tmp_path, capsys):
    manifest = write_manifest(tmp_path / "m.toml", {"A.EXE": b"alpha"})
    orig = tmp_path / "orig"
    orig.mkdir()
    args = ["check-orig", "--orig", str(orig), "--manifest", str(manifest)]
    assert main(args) == 1
    assert "MISSING" in capsys.readouterr().out
    (orig / "A.EXE").write_bytes(b"alpha")
    assert main(args) == 0
    assert "1 ok, 0 mismatched, 0 missing" in capsys.readouterr().out


def test_ingest_command(tmp_path, monkeypatch, capsys):
    game = tmp_path / "game"
    (game / "SUB").mkdir(parents=True)
    (game / "SUB" / "A.EXE").write_bytes(b"alpha")
    manifest = write_manifest(tmp_path / "m.toml", {"A.EXE": b"alpha"})
    monkeypatch.setenv("APOC_STEAM_FOLDER", str(game))
    monkeypatch.delenv("APOC_GOG_FOLDER", raising=False)
    orig = tmp_path / "orig"
    args = ["ingest", "--orig", str(orig), "--manifest", str(manifest)]
    assert main([*args, "--env-file", str(tmp_path / "absent.env")]) == 0
    assert (orig / "A.EXE").read_bytes() == b"alpha"
    assert "copied" in capsys.readouterr().out


def test_ingest_without_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("APOC_STEAM_FOLDER", raising=False)
    monkeypatch.delenv("APOC_GOG_FOLDER", raising=False)
    code = main(["ingest", "--orig", str(tmp_path / "o"), "--env-file", str(tmp_path / "x")])
    assert code == 1
    assert "APOC_STEAM_FOLDER" in capsys.readouterr().err


def test_subcommand_required():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


# ---- fetch-watcom / install-watcom / check-watcom ----------------------------------------------


def _watcom_manifest(path, payload: bytes, key: bytes) -> None:
    path.write_text(
        "[[media]]\n"
        'version = "9.9"\n'
        'item = "item"\n'
        'file = "sub/TEST.iso"\n'
        f"size = {len(payload)}\n"
        f'md5 = "{hashlib.md5(payload).hexdigest()}"\n'
        f'sha1 = "{hashlib.sha1(payload).hexdigest()}"\n'
        "[[media.key_files]]\n"
        'path = "BIN/KEY.EXE"\n'
        f"size = {len(key)}\n"
        f'md5 = "{hashlib.md5(key).hexdigest()}"\n'
        f'sha1 = "{hashlib.sha1(key).hexdigest()}"\n',
        encoding="utf-8",
    )


def test_fetch_watcom_downloads_then_reports_present(tmp_path, capsys):
    payload = b"pretend iso" * 10
    (tmp_path / "base" / "item" / "sub").mkdir(parents=True)
    (tmp_path / "base" / "item" / "sub" / "TEST.iso").write_bytes(payload)
    manifest = tmp_path / "w.toml"
    _watcom_manifest(manifest, payload, b"key")
    args = [
        "fetch-watcom", "--manifest", str(manifest), "--media", str(tmp_path / "media"),
        "--base-url", (tmp_path / "base").as_uri(),
    ]  # fmt: skip
    assert main(args) == 0
    captured = capsys.readouterr()
    assert MEDIA_NOTICE in captured.err
    assert "DOWNLOADED" in captured.out
    assert (tmp_path / "media" / "TEST.iso").read_bytes() == payload
    assert main(args) == 0
    assert "PRESENT" in capsys.readouterr().out


def test_install_and_check_watcom(tmp_path, capsys):
    key = b"compiler bytes"
    iso = build_iso({"BIN/KEY.EXE": key, "README.TXT": b"hello"})
    media = tmp_path / "media"
    media.mkdir()
    (media / "TEST.iso").write_bytes(iso)
    manifest = tmp_path / "w.toml"
    _watcom_manifest(manifest, iso, key)
    dest = tmp_path / "dest"
    common = ["--manifest", str(manifest)]
    assert main(["install-watcom", *common, "--media", str(media), "--dest", str(dest)]) == 0
    assert (dest / "9.9" / "BIN" / "KEY.EXE").read_bytes() == key
    capsys.readouterr()
    assert main(["check-watcom", *common, "--dest", str(dest)]) == 0
    assert "1 ok" in capsys.readouterr().out
    (dest / "9.9" / "BIN" / "KEY.EXE").write_bytes(b"corrupt")
    assert main(["check-watcom", *common, "--dest", str(dest)]) == 1
    assert "MISMATCH" in capsys.readouterr().out


def test_install_watcom_continues_after_a_failed_version(tmp_path, capsys):
    key = b"compiler bytes"
    iso = build_iso({"BIN/KEY.EXE": key})
    media = tmp_path / "media"
    media.mkdir()
    (media / "SECOND.iso").write_bytes(iso)  # FIRST.iso is deliberately missing
    entries = []
    for version, name in (("1.1", "FIRST.iso"), ("2.2", "SECOND.iso")):
        entries.append(
            "[[media]]\n"
            f'version = "{version}"\nitem = "item"\nfile = "{name}"\n'
            f"size = {len(iso)}\n"
            f'md5 = "{hashlib.md5(iso).hexdigest()}"\n'
            f'sha1 = "{hashlib.sha1(iso).hexdigest()}"\n'
        )
    manifest = tmp_path / "w.toml"
    manifest.write_text("".join(entries), encoding="utf-8")
    dest = tmp_path / "dest"
    args = ["install-watcom", "--manifest", str(manifest), "--media", str(media)]
    assert main([*args, "--dest", str(dest)]) == 1
    err = capsys.readouterr().err
    assert "reverseapoc install-watcom: 1.1:" in err
    assert (dest / "2.2" / "BIN" / "KEY.EXE").read_bytes() == key


def test_watcom_unknown_version(tmp_path, capsys):
    manifest = tmp_path / "w.toml"
    _watcom_manifest(manifest, b"x", b"y")
    assert main(["check-watcom", "7.7", "--manifest", str(manifest)]) == 1
    assert "7.7" in capsys.readouterr().err
