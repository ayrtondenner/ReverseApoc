"""Command line: ingest, check-orig, parse-le, rebuild, and the Watcom media commands."""

from __future__ import annotations

import hashlib
import json

import pytest

from conftest import OUTER_STUB_SIZE, build_le_image, write_manifest
from isoimage import build_iso
from reverseapoc.cli import main
from reverseapoc.le import LE
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


# ---- rebuild ------------------------------------------------------------------------------------


def _rebuild_setup(tmp_path, *, name: str = "SYNTH.EXE", orig_data: bytes | None = None):
    """A synthetic LE described by a manifest under `name`; orig/ holds `orig_data` (default:
    the same bytes) as SYNTH.EXE, or nothing when orig_data is b""."""
    data = build_le_image().data
    orig = tmp_path / "orig"
    orig.mkdir()
    orig_data = data if orig_data is None else orig_data
    if orig_data:
        (orig / "SYNTH.EXE").write_bytes(orig_data)
    manifest = write_manifest(tmp_path / "m.toml", {name: data})
    out = tmp_path / "build"
    args = ["rebuild", "--orig", str(orig), "--manifest", str(manifest), "--out", str(out)]
    return data, orig, out, args


def test_rebuild_ok_line_and_exit_code(tmp_path, capsys):
    data, _, out, args = _rebuild_setup(tmp_path)
    assert main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    line = lines[0]
    assert line.startswith("OK")
    assert "SYNTH.EXE" in line
    assert f"sha1 {hashlib.sha1(data).hexdigest()}" in line
    assert line.endswith("== manifest")
    assert (out / "SYNTH.EXE").read_bytes() == data


def test_rebuild_missing_target_exits_1(tmp_path, capsys):
    _, _, out, args = _rebuild_setup(tmp_path, orig_data=b"")
    assert main(args) == 1
    assert capsys.readouterr().out.startswith("MISSING")
    assert not (out / "SYNTH.EXE").exists()


def test_rebuild_refuses_orig_that_fails_the_manifest(tmp_path, capsys):
    data = build_le_image().data
    changed = bytearray(data)
    changed[-1] ^= 0xFF
    _, _, out, args = _rebuild_setup(tmp_path, orig_data=bytes(changed))
    assert main(args) == 1
    line = capsys.readouterr().out
    assert line.startswith("REFUSED")
    assert "check-orig" in line
    assert not (out / "SYNTH.EXE").exists()


@pytest.mark.parametrize("inside", [False, True], ids=["equal", "subdirectory"])
def test_rebuild_refuses_out_inside_orig(tmp_path, capsys, inside):
    _, orig, _, args = _rebuild_setup(tmp_path)
    out = orig / "sub" if inside else orig
    args[args.index("--out") + 1] = str(out)
    assert main(args) == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "orig" in err
    assert sorted(p.name for p in orig.iterdir()) == ["SYNTH.EXE"]


def test_rebuild_refuses_target_name_with_a_path(tmp_path, capsys):
    _, _, out, args = _rebuild_setup(tmp_path, name="SUB/SYNTH.EXE")
    assert main(args) == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "SUB/SYNTH.EXE" in err
    assert not out.exists()


def test_rebuild_mismatch_exits_1(tmp_path, capsys, monkeypatch):
    import reverseapoc.splice as splice

    data, _, _, args = _rebuild_setup(tmp_path)
    flip_at = LE(data).pages[0].file_offset + 0x10
    real_reassemble = splice.reassemble

    def flipped(le, decomposition):
        out = bytearray(real_reassemble(le, decomposition))
        out[flip_at] ^= 0xFF
        return bytes(out)

    monkeypatch.setattr(splice, "reassemble", flipped)
    assert main(args) == 1
    line = capsys.readouterr().out
    expected = hashlib.sha1(data).hexdigest()
    mutated = bytearray(data)
    mutated[flip_at] ^= 0xFF
    got = hashlib.sha1(bytes(mutated)).hexdigest()
    assert line.startswith("MISMATCH")
    assert f"sha1 {got}" in line
    assert f"manifest {expected}" in line


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
