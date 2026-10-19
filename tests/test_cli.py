"""Command line: ingest, check-orig, parse-le."""

from __future__ import annotations

import json

import pytest

from conftest import OUTER_STUB_SIZE, write_manifest
from reverseapoc.cli import main


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
