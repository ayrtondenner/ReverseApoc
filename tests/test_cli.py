"""Command line: ingest, check-orig, parse-le, rebuild, and the Watcom media commands."""

from __future__ import annotations

import argparse
import hashlib
import json

import pytest

from conftest import OUTER_STUB_SIZE, SYNTHETIC_TRAILER, build_le_image, write_manifest
from cpptree import init_exe, write_cpp_lib, write_init_lib
from isoimage import build_iso
from libtree import body, cli_workspace, code_module, write_lib
from reverseapoc import probe as probe_module
from reverseapoc import targets
from reverseapoc.cli import build_parser, main
from reverseapoc.le import LE
from reverseapoc.libmatch import RUNTIME_CSV_COLUMNS, RUNTIME_CSV_COMMENT, SWEPT_VERSIONS
from reverseapoc.probe import IDIOMS, Calibration, Cell
from reverseapoc.splice import RebuildResult
from reverseapoc.targets import DEFAULT_MANIFEST, DEFAULT_ORIG, REPO_ROOT, load_manifest
from reverseapoc.watcom import MEDIA_NOTICE
from watcomtree import TREE_FILES, FakeCompiler, make_tree, write_watcom_manifest


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


def test_parse_le_reports_trailer_without_bytes(tmp_path, capsys):
    img = build_le_image(trailer=SYNTHETIC_TRAILER)
    path = tmp_path / "TRAILED.EXE"
    path.write_bytes(img.data)
    sha1 = hashlib.sha1(SYNTHETIC_TRAILER).hexdigest()
    leaked = ("SYNTHETIC", SYNTHETIC_TRAILER.hex(), SYNTHETIC_TRAILER.hex().upper())

    assert main(["parse-le", str(path)]) == 0
    text = capsys.readouterr().out
    (row,) = [line for line in text.splitlines() if line.startswith("trailer")]
    assert f"{len(SYNTHETIC_TRAILER)} bytes at {img.trailer_offset:#010x}" in row
    assert sha1 in row

    assert main(["parse-le", str(path), "--json"]) == 0
    raw = capsys.readouterr().out
    trailer = json.loads(raw)["trailer"]
    assert trailer == {"offset": img.trailer_offset, "length": len(SYNTHETIC_TRAILER), "sha1": sha1}

    for output in (text, raw):
        assert not any(marker in output for marker in leaked)


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


INVALID_TOML = '[[targets]\nname = "A.EXE"\n'


@pytest.mark.parametrize(
    "verb",
    [["check-orig"], ["rebuild"], ["rebuild", "--json"]],
    ids=["check-orig", "rebuild", "rebuild-json"],
)
def test_malformed_manifest_is_an_error_line(tmp_path, capsys, verb):
    # IN-06: one error line and exit 1, not a traceback (with --json, stdout is "[]": WR-04)
    bad = tmp_path / "bad.toml"
    bad.write_text(INVALID_TOML, encoding="utf-8")
    args = [*verb, "--orig", str(tmp_path / "orig"), "--manifest", str(bad)]
    if verb[0] == "rebuild":
        args += ["--out", str(tmp_path / "build")]
    assert main(args) == 1
    err = capsys.readouterr().err
    assert f"reverseapoc {verb[0]}: error:" in err
    assert str(bad) in err
    assert not (tmp_path / "build").exists()


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


JSON_KEYS = {
    "name",
    "status",
    "output",
    "sha1",
    "expected_sha1",
    "first_diff",
    "diff_bytes",
    "masked_fields",
}


def test_rebuild_json_output(tmp_path, capsys):
    _, _, out, args = _rebuild_setup(tmp_path)
    assert main([*args, "--json"]) == 0
    results = json.loads(capsys.readouterr().out)
    assert isinstance(results, list)
    assert len(results) == 1
    (obj,) = results
    assert set(obj) == JSON_KEYS
    expected = load_manifest(tmp_path / "m.toml")[0].sha1
    assert obj["name"] == "SYNTH.EXE"
    assert obj["status"] == "ok"
    assert obj["output"] == str(out / "SYNTH.EXE")
    assert obj["sha1"] == obj["expected_sha1"] == expected
    assert obj["first_diff"] is None
    assert obj["diff_bytes"] == 0
    assert obj["masked_fields"] == 0


def test_rebuild_json_missing(tmp_path, capsys):
    _, _, _, args = _rebuild_setup(tmp_path, orig_data=b"")
    assert main([*args, "--json"]) == 1
    (obj,) = json.loads(capsys.readouterr().out)
    assert set(obj) == JSON_KEYS
    assert obj["status"] == "missing"
    assert obj["output"] is None
    assert obj["sha1"] is None
    assert obj["expected_sha1"] == load_manifest(tmp_path / "m.toml")[0].sha1


def _elsewhere_setup(tmp_path, *, present: bool = True):
    """SYNTH.EXE with its last byte flipped in tmp_path/elsewhere (nothing there when not
    `present`) and tmp_path/custom.toml describing the unchanged bytes: neither is the default
    orig dir or manifest (VN-01)."""
    data = build_le_image().data
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    if present:
        changed = bytearray(data)
        changed[-1] ^= 0xFF
        (elsewhere / "SYNTH.EXE").write_bytes(bytes(changed))
    custom = write_manifest(tmp_path / "custom.toml", {"SYNTH.EXE": data})
    args = ["rebuild", "--orig", str(elsewhere), "--manifest", str(custom)]
    return elsewhere, custom, [*args, "--out", str(tmp_path / "build")]


def test_rebuild_refused_names_the_input_and_manifest(tmp_path, capsys):
    elsewhere, custom, args = _elsewhere_setup(tmp_path)
    assert main(args) == 1
    line = capsys.readouterr().out
    assert line.startswith("REFUSED")
    assert str(elsewhere / "SYNTH.EXE") in line
    assert str(custom) in line
    assert "check-orig" in line
    assert "config/targets.toml" not in line


def test_rebuild_missing_names_the_input(tmp_path, capsys):
    elsewhere, _, args = _elsewhere_setup(tmp_path, present=False)
    assert main(args) == 1
    line = capsys.readouterr().out
    assert line.startswith("MISSING")
    assert str(elsewhere / "SYNTH.EXE") in line


def _hint_args(line: str, verb: str) -> argparse.Namespace:
    """Parse the command a REFUSED or MISSING hint tells the user to run (paths without spaces)."""
    command = line.split(f"run uv run reverseapoc {verb}", 1)[1].rstrip(")\n")
    return build_parser().parse_args([verb, *command.split()])


def test_rebuild_refused_hint_names_the_same_orig_and_manifest(tmp_path, capsys):
    # IN-12: following the hint must check the files the REFUSED line is about
    elsewhere, custom, args = _elsewhere_setup(tmp_path)
    assert main(args) == 1
    line = capsys.readouterr().out.rstrip("\n")
    source = elsewhere / "SYNTH.EXE"
    assert line == (
        f"REFUSED   SYNTH.EXE  {source} does not match {custom}; "
        f"run uv run reverseapoc check-orig --orig {elsewhere} --manifest {custom}"
    )
    hint = _hint_args(line, "check-orig")
    assert (hint.orig, hint.manifest) == (elsewhere, custom)


def test_rebuild_missing_hint_names_the_same_orig_and_manifest(tmp_path, capsys):
    elsewhere, custom, args = _elsewhere_setup(tmp_path, present=False)
    assert main(args) == 1
    line = capsys.readouterr().out.rstrip("\n")
    source = elsewhere / "SYNTH.EXE"
    assert line == (
        f"MISSING   SYNTH.EXE  ({source} not found; "
        f"run uv run reverseapoc ingest --orig {elsewhere} --manifest {custom})"
    )
    hint = _hint_args(line, "ingest")
    assert (hint.orig, hint.manifest) == (elsewhere, custom)


def _synth_target(tmp_path):
    (target,) = load_manifest(write_manifest(tmp_path / "m.toml", {"SYNTH.EXE": b"synthetic"}))
    return target


@pytest.mark.parametrize(
    ("status", "hint"),
    [
        ("refused", "; run uv run reverseapoc check-orig"),
        ("missing", "; run uv run reverseapoc ingest)"),
    ],
)
def test_rebuild_hint_without_options_for_the_defaults(tmp_path, status, hint):
    result = RebuildResult(_synth_target(tmp_path), status, None, source=DEFAULT_ORIG / "SYNTH.EXE")
    assert result.format(9, DEFAULT_MANIFEST).endswith(hint)


def test_rebuild_hint_names_only_the_options_that_differ(tmp_path):
    target = _synth_target(tmp_path)
    custom_orig = RebuildResult(target, "refused", None, source=tmp_path / "SYNTH.EXE")
    line = custom_orig.format(9, DEFAULT_MANIFEST)
    assert line.endswith(f"; run uv run reverseapoc check-orig --orig {tmp_path}")
    custom_manifest = RebuildResult(target, "missing", None, source=DEFAULT_ORIG / "SYNTH.EXE")
    line = custom_manifest.format(9, tmp_path / "m.toml")
    assert line.endswith(f"; run uv run reverseapoc ingest --manifest {tmp_path / 'm.toml'})")


def test_rebuild_hint_quotes_a_path_with_a_space(tmp_path):
    spaced = tmp_path / "my orig"
    result = RebuildResult(_synth_target(tmp_path), "refused", None, source=spaced / "SYNTH.EXE")
    assert result.format(9, DEFAULT_MANIFEST).endswith(f'check-orig --orig "{spaced}"')


def test_rebuild_json_refused_keeps_the_eight_keys(tmp_path, capsys):
    # the control: passes before and after VN-01, the new fields stay out of --json
    _, _, args = _elsewhere_setup(tmp_path)
    assert main([*args, "--json"]) == 1
    (obj,) = json.loads(capsys.readouterr().out)
    assert set(obj) == JSON_KEYS
    assert obj["status"] == "refused"


def _two_target_setup(tmp_path):
    """SYNTH.EXE (bound fixture) and OTHER.EXE (unbound fixture), both in orig/ and the
    manifest."""
    files = {"SYNTH.EXE": build_le_image().data, "OTHER.EXE": build_le_image(bound=False).data}
    orig = tmp_path / "orig"
    orig.mkdir()
    for name, data in files.items():
        (orig / name).write_bytes(data)
    manifest = write_manifest(tmp_path / "m.toml", files)
    out = tmp_path / "build"
    args = ["rebuild", "--orig", str(orig), "--manifest", str(manifest), "--out", str(out)]
    return out, args


def test_rebuild_exe_filter_case_insensitive(tmp_path, capsys):
    out, args = _two_target_setup(tmp_path)
    assert main([*args, "--exe", "synth.exe"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("OK")
    assert "SYNTH.EXE" in lines[0]
    assert sorted(p.name for p in out.iterdir()) == ["SYNTH.EXE"]


def test_rebuild_unknown_exe_lists_known_names(tmp_path, capsys):
    out, args = _two_target_setup(tmp_path)
    assert main([*args, "--exe", "NOPE.EXE"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    for name in ("NOPE.EXE", "SYNTH.EXE", "OTHER.EXE"):
        assert name in captured.err
    assert not out.exists()


def test_rebuild_mismatch_line_and_json(tmp_path, capsys, monkeypatch):
    import reverseapoc.splice as splice

    img = build_le_image(fixups=[b"", b"", b""])
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYNTH.EXE").write_bytes(img.data)
    manifest = write_manifest(tmp_path / "m.toml", {"SYNTH.EXE": img.data})
    args = ["rebuild", "--orig", str(orig), "--manifest", str(manifest)]
    args += ["--out", str(tmp_path / "build")]
    real_splice = splice.splice
    monkeypatch.setattr(splice, "splice", lambda le, _patches: real_splice(le, {0x10800: b"\x5a"}))
    offset = img.page_offsets[0] + 0x800
    region = "page 1 of object 1, VA 0x00010800"

    assert main(args) == 1
    line = capsys.readouterr().out.strip()
    assert line.startswith("MISMATCH")
    assert f"first difference at {offset:#x} ({region})" in line
    assert "1 bytes differ" in line

    assert main([*args, "--json"]) == 1
    (obj,) = json.loads(capsys.readouterr().out)
    assert obj["status"] == "mismatch"
    assert obj["first_diff"] == {"offset": offset, "region": region, "va": 0x10800}
    assert obj["diff_bytes"] == 1


def _erroring_middle_target_setup(tmp_path):
    """SYNTH.EXE and OTHER.EXE rebuild fine; BAD.EXE, between them in the manifest, matches it
    but has a non-resident name table, which layout() refuses (D-19)."""
    files = {
        "SYNTH.EXE": build_le_image().data,
        "BAD.EXE": build_le_image(extra_header_fields={0x88: 0x10}).data,
        "OTHER.EXE": build_le_image(bound=False).data,
    }
    orig = tmp_path / "orig"
    orig.mkdir()
    for name, data in files.items():
        (orig / name).write_bytes(data)
    manifest = write_manifest(tmp_path / "m.toml", files)
    out = tmp_path / "build"
    args = ["rebuild", "--orig", str(orig), "--manifest", str(manifest), "--out", str(out)]
    return out, args


def test_rebuild_json_reports_a_target_error_and_keeps_the_others(tmp_path, capsys):
    # WR-04: an error in one target is a per-target status; --json still prints every target
    out, args = _erroring_middle_target_setup(tmp_path)
    assert main([*args, "--json"]) == 1
    results = json.loads(capsys.readouterr().out)
    assert [(r["name"], r["status"]) for r in results] == [
        ("SYNTH.EXE", "ok"),
        ("BAD.EXE", "error"),
        ("OTHER.EXE", "ok"),
    ]
    bad = results[1]
    assert set(bad) == JSON_KEYS | {"error"}
    assert not bad["error"].startswith("BAD.EXE")  # the name is already in "name"
    assert "non-resident name table" in bad["error"]
    assert (bad["output"], bad["sha1"], bad["first_diff"]) == (None, None, None)
    assert bad["expected_sha1"] == load_manifest(tmp_path / "m.toml")[1].sha1
    assert all(set(r) == JSON_KEYS for r in (results[0], results[2]))
    assert sorted(p.name for p in out.iterdir()) == ["OTHER.EXE", "SYNTH.EXE"]


def test_rebuild_text_reports_a_target_error_and_keeps_the_others(tmp_path, capsys):
    _, args = _erroring_middle_target_setup(tmp_path)
    assert main(args) == 1
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert [line[:20] for line in lines] == [
        "OK        SYNTH.EXE ",
        "ERROR     BAD.EXE   ",
        "OK        OTHER.EXE ",
    ]
    assert "non-resident name table" in lines[1]
    assert lines[1].count("BAD.EXE") == 1  # named once, by the column
    assert captured.err == ""


@pytest.mark.parametrize("option", ["--exe", "--manifest"], ids=["unknown-exe", "no-manifest"])
def test_rebuild_json_run_error_still_prints_a_list(tmp_path, capsys, option):
    # a failure before any target has no per-target entry: stdout is an empty list
    _, args = _two_target_setup(tmp_path)
    value = "NOPE.EXE" if option == "--exe" else str(tmp_path / "absent.toml")
    assert main([*args, option, value, "--json"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert "reverseapoc rebuild: error:" in captured.err


def test_rebuild_default_options():
    args = build_parser().parse_args(["rebuild"])
    assert args.orig == DEFAULT_ORIG
    assert args.manifest == DEFAULT_MANIFEST
    assert args.out == REPO_ROOT / "build"
    assert args.exe is None
    assert args.json is False


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


# ---- cc: the compiler wrapper ----


@pytest.fixture
def cc_workspace(tmp_path, monkeypatch):
    """A fake 10.6 tree, manifest and cflags under tmp_path, with tmp_path standing in for the
    repository root and a FakeCompiler standing in for subprocess.run."""
    from reverseapoc import compiler

    make_tree(tmp_path / "w", "10.6")
    manifest = write_watcom_manifest(tmp_path / "watcom.toml", {"10.6": TREE_FILES["10.6"]})
    cflags = tmp_path / "cflags.txt"
    cflags.write_text("*  wcc386@10.6  -5r -s\n", encoding="utf-8")
    src = tmp_path / "src" / "a.c"
    src.parent.mkdir()
    src.write_text("int x;\n")
    runner = FakeCompiler()
    monkeypatch.setattr(compiler, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(compiler, "DEFAULT_STAMPS", tmp_path / "cache")
    monkeypatch.setattr(compiler, "runner_prefix", lambda platform: [])
    monkeypatch.setattr(compiler.subprocess, "run", runner)
    options = [
        "--cflags", str(cflags), "--manifest", str(manifest),
        "--watcom-dir", str(tmp_path / "w"), "--log", str(tmp_path / "logs" / "cc.log"),
    ]  # fmt: skip
    return argparse.Namespace(root=tmp_path, src=src, options=options, runner=runner)


def test_cc_ok_line_and_exit_code(cc_workspace, capsys):
    ws = cc_workspace
    obj = ws.root / "out" / "a.obj"
    assert main(["cc", str(ws.src), "-o", str(obj), *ws.options]) == 0
    lines = capsys.readouterr().out.splitlines()
    ok = [line for line in lines if line.startswith("OK")]
    assert len(ok) == 1
    assert "wcc386@10.6" in ok[0]
    assert "WATCOM C32 Optimizing Compiler  Version 10.6" in ok[0]
    assert "src/a.c" in ok[0] and "out/a.obj" in ok[0]
    assert obj.is_file()


def test_cc_json(cc_workspace, capsys):
    ws = cc_workspace
    obj = ws.root / "out" / "a.obj"
    assert main(["cc", str(ws.src), "-o", str(obj), *ws.options, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["spec"] == "wcc386@10.6"
    assert data["returncode"] == 0
    assert "Version 10.6" in data["banner"]
    assert [path for path, _sha1 in data["gate"]] == ["BINNT/WCC386.EXE", "BINW/WCC386.EXE"]


def test_cc_help_lists_options(capsys):
    with pytest.raises(SystemExit):
        main(["cc", "--help"])
    out = capsys.readouterr().out
    for option in ("-o", "--cflags", "--manifest", "--watcom-dir", "--log", "--json"):
        assert option in out


def test_cc_failed_compile_exits_1(cc_workspace, capsys):
    ws = cc_workspace
    ws.runner.rc = 2
    ws.runner.output = "t.c(1): Error! E1009: fake error\n"
    obj = ws.root / "out" / "a.obj"
    assert main(["cc", str(ws.src), "-o", str(obj), *ws.options]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "t.c(1): Error! E1009: fake error" in lines
    failed = [line for line in lines if line.startswith("FAILED")]
    assert len(failed) == 1
    assert "exit 2" in failed[0]
    assert not obj.exists()


def test_cc_refuses_a_source_with_a_space(cc_workspace, capsys):
    ws = cc_workspace
    src = ws.root / "src" / "a b.c"
    src.write_text("int x;\n")
    assert main(["cc", str(src), "-o", str(ws.root / "a.obj"), *ws.options]) == 1
    assert "space" in capsys.readouterr().err
    assert ws.runner.calls == []


def test_cc_refusal_is_an_error_line(cc_workspace, capsys):
    ws = cc_workspace
    (ws.root / "w" / "10.6" / "BINW" / "WCC386.EXE").unlink()
    assert main(["cc", str(ws.src), "-o", str(ws.root / "a.obj"), *ws.options]) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc cc: error:")
    assert "install-watcom 10.6" in err


NOT_UTF8 = b"* \xff wcc386@10.6\n"  # one byte that no UTF-8 sequence starts with


def test_cc_cflags_that_is_not_utf8_is_an_error_line(cc_workspace, capsys):
    ws = cc_workspace
    bad = ws.root / "bad-cflags.txt"
    bad.write_bytes(NOT_UTF8)
    options = list(ws.options)
    options[options.index("--cflags") + 1] = str(bad)
    assert main(["cc", str(ws.src), "-o", str(ws.root / "a.obj"), *options]) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc cc: error:")
    assert "bad-cflags.txt" in err and "not UTF-8" in err
    assert ws.runner.calls == []


def test_cc_object_without_a_name_is_an_error_line(cc_workspace, capsys, monkeypatch):
    ws = cc_workspace
    monkeypatch.chdir(ws.root)  # `-o .` names the repository root itself, which has no name
    assert main(["cc", str(ws.src), "-o", ".", *ws.options]) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc cc: error:")
    assert ".obj" in err
    assert ws.runner.calls == []


@pytest.mark.parametrize("log_name", [".", "/"])
def test_cc_log_without_a_name_is_an_error_line(cc_workspace, capsys, monkeypatch, log_name):
    ws = cc_workspace
    monkeypatch.chdir(ws.root)  # `--log .` names the repository root itself, which has no name
    obj = ws.root / "out" / "a.obj"
    obj.parent.mkdir(parents=True, exist_ok=True)
    obj.write_bytes(b"keep")  # the refusal comes before the stale-object unlink (IN-13)
    options = list(ws.options)
    options[options.index("--log") + 1] = log_name
    assert main(["cc", str(ws.src), "-o", str(obj), *options]) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc cc: error:")
    assert len(err.splitlines()) == 1
    assert "Traceback" not in err
    assert "--log" in err
    assert ws.runner.calls == []
    assert obj.read_bytes() == b"keep"


# ---- libmatch ----


def _libmatch_args(ws, exe="SYNTH.EXE", *extra):
    return [
        "libmatch",
        exe,
        "--orig",
        str(ws["orig"]),
        "--manifest",
        str(ws["manifest"]),
        "--watcom-dir",
        str(ws["watcom"]),
        *extra,
    ]


FAKE_CSV_ROW = "0x00010200,0x00010228,_TEXT,fake,DOS/CLIB3R.LIB,10.6,fake2_;fake_,unique,"


def test_libmatch_writes_output(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--output", str(ws["out"]))) == 0
    assert FAKE_CSV_ROW in ws["out"].read_text(encoding="utf-8").splitlines()
    out = capsys.readouterr().out
    assert [line for line in out.splitlines() if line.startswith("0x")] == [
        "0x00010200-0x00010228  fake  DOS/CLIB3R.LIB  10.6  unique"
    ]


def test_libmatch_exe_is_case_insensitive_and_takes_the_stem(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    assert main(_libmatch_args(ws, "synth", "--output", str(ws["out"]))) == 0
    assert "# generated by: uv run reverseapoc libmatch SYNTH.EXE" in ws["out"].read_text()


def test_libmatch_json(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--json")) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["exe"] == "SYNTH.EXE"
    (row,) = report["ranges"]
    assert (row["start"], row["end"], row["module"]) == (0x10200, 0x10228, "fake")


def _full_sweep(ws, *, but: str | None = None):
    """Give every swept version except `but` a library (10.6 already holds module "fake"); the
    extra ones hold a module that occurs nowhere in the EXE, so the rows stay the same."""
    other = code_module("other", body(40, 0x90))
    for version in SWEPT_VERSIONS:
        if version not in ("10.6", but):
            write_lib(ws["watcom"], version, "DOS/CLIB3R.LIB", [other])


def test_libmatch_write_goes_to_the_config_dir(tmp_path, capsys, monkeypatch):
    ws = cli_workspace(tmp_path)
    _full_sweep(ws)
    monkeypatch.setattr(targets, "REPO_ROOT", tmp_path / "repo")
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--write")) == 0
    path = tmp_path / "repo" / "config" / "synth" / "runtime.csv"
    assert FAKE_CSV_ROW in path.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("gap", ["no-lib386", "no-omf-library", "versions-subset"])
def test_libmatch_write_refuses_a_partial_sweep(tmp_path, capsys, monkeypatch, gap):
    """--write writes the committed D-06 map, which records no swept-version list: every swept
    version must load a library, or the rows would silently lack it (review WR-04)."""
    ws = cli_workspace(tmp_path)
    _full_sweep(ws, but="11.0")
    if gap == "no-omf-library":
        junk = ws["watcom"] / "11.0" / "LIB386" / "DOS" / "CLIB3R.LIB"
        junk.parent.mkdir(parents=True)
        junk.write_bytes(b"not an OMF library")
    if gap == "versions-subset":
        _full_sweep(ws)
    monkeypatch.setattr(targets, "REPO_ROOT", tmp_path / "repo")
    extra = ["--versions", "10.5", "10.6"] if gap == "versions-subset" else []
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--write", *extra)) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc libmatch: error:")
    assert "--write" in err and "11.0" in err
    assert not (tmp_path / "repo" / "config" / "synth" / "runtime.csv").exists()


def test_libmatch_output_still_takes_a_partial_sweep(tmp_path, capsys):
    ws = cli_workspace(tmp_path)  # 10.6 only: --output is a scratch file, not the D-06 map
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--output", str(ws["out"]))) == 0
    assert FAKE_CSV_ROW in ws["out"].read_text(encoding="utf-8").splitlines()


def test_libmatch_write_and_output_are_exclusive(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    with pytest.raises(SystemExit):
        main(_libmatch_args(ws, "SYNTH.EXE", "--write", "--output", str(ws["out"])))
    assert not ws["out"].exists()


def test_libmatch_refuses_unknown_exe(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    assert main(_libmatch_args(ws, "NOPE.EXE", "--output", str(ws["out"]))) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc libmatch: error:") and "NOPE.EXE" in err
    assert not ws["out"].exists()


def test_libmatch_refuses_orig_mismatch(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    (ws["orig"] / "SYNTH.EXE").write_bytes(b"MZ not the manifest's file")
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--output", str(ws["out"]))) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc libmatch: error:") and "does not match" in err
    assert not ws["out"].exists()


def test_libmatch_refuses_missing_orig(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    (ws["orig"] / "SYNTH.EXE").unlink()
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--output", str(ws["out"]))) == 1
    assert "reverseapoc libmatch: error:" in capsys.readouterr().err
    assert not ws["out"].exists()


def test_libmatch_refuses_output_inside_orig(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    inside = ws["orig"] / "runtime.csv"
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--output", str(inside))) == 1
    assert "orig" in capsys.readouterr().err
    assert not inside.exists()


@pytest.mark.parametrize("default", ["DEFAULT_ORIG", "DEFAULT_INSTALL"])
def test_libmatch_refuses_output_inside_the_default_trees(tmp_path, capsys, monkeypatch, default):
    """--orig and --watcom-dir point elsewhere, yet the default orig/ and Watcom tree stay
    protected: they are only ever read (CLAUDE.md)."""
    ws = cli_workspace(tmp_path)
    protected = tmp_path / "default-tree"
    protected.mkdir()
    monkeypatch.setattr(f"reverseapoc.cli.{default}", protected)
    inside = protected / "TACP.EXE"
    assert main(_libmatch_args(ws, "SYNTH.EXE", "--output", str(inside))) == 1
    assert "refusing to write" in capsys.readouterr().err
    assert not inside.exists()


def test_libmatch_refuses_a_tree_without_libraries(tmp_path, capsys):
    ws = cli_workspace(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    args = _libmatch_args(ws, "SYNTH.EXE", "--output", str(ws["out"]))
    args[args.index(str(ws["watcom"]))] = str(empty)
    assert main(args) == 1
    assert "no OMF library" in capsys.readouterr().err
    assert not ws["out"].exists()


def test_libmatch_help_lists_options(capsys):
    with pytest.raises(SystemExit):
        main(["libmatch", "--help"])
    out = capsys.readouterr().out
    for option in ("--orig", "--manifest", "--watcom-dir", "--versions", "--write", "--output",
                   "--json"):  # fmt: skip
        assert option in out


# ---- cppscan ----


def _cppscan_workspace(tmp_path, *, cpp_library=True, **exe_args):
    """cli_workspace with the inirt386 EXE and library instead of module "fake", plus a C++
    runtime library (without one the C++-only module signal cannot be computed)."""
    ws = cli_workspace(tmp_path, exe=init_exe(**exe_args))
    write_init_lib(ws["watcom"])
    if cpp_library:
        write_cpp_lib(ws["watcom"])
    return ws


def _cppscan_args(ws, *extra, verb="cppscan"):
    return [verb, "SYNTH.EXE", "--orig", str(ws["orig"]), "--manifest", str(ws["manifest"]),
            "--watcom-dir", str(ws["watcom"]), *extra]  # fmt: skip


def test_cppscan_missing_runtime_map(tmp_path, capsys):
    ws = _cppscan_workspace(tmp_path)
    assert main(_cppscan_args(ws, "--runtime", str(tmp_path / "absent.csv"))) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc cppscan: error:")
    assert "libmatch SYNTH.EXE --write" in err


def test_cppscan_runtime_map_that_is_not_utf8_is_an_error_line(tmp_path, capsys):
    ws = _cppscan_workspace(tmp_path)
    bad = tmp_path / "bad-runtime.csv"
    bad.write_bytes(NOT_UTF8)
    assert main(_cppscan_args(ws, "--runtime", str(bad))) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc cppscan: error:")
    assert "bad-runtime.csv" in err and "not UTF-8" in err


def test_cppscan_default_runtime_is_the_config_dir(tmp_path, capsys, monkeypatch):
    ws = _cppscan_workspace(tmp_path)
    monkeypatch.setattr(targets, "REPO_ROOT", tmp_path / "repo")
    assert main(_cppscan_args(ws)) == 1
    err = capsys.readouterr().err
    assert str(tmp_path / "repo" / "config" / "synth" / "runtime.csv") in err


def test_cppscan_prints_the_verdict(tmp_path, capsys):
    ws = _cppscan_workspace(tmp_path)
    assert main(_cppscan_args(ws, "--output", str(ws["out"]), verb="libmatch")) == 0
    capsys.readouterr()
    assert main(_cppscan_args(ws, "--runtime", str(ws["out"]))) == 0
    out = capsys.readouterr().out
    assert out.startswith("SYNTH.EXE: C (wcc386): ")


def test_cppscan_without_cpp_libraries_does_not_report_a_full_c_verdict(tmp_path, capsys):
    ws = _cppscan_workspace(tmp_path, cpp_library=False)
    assert main(_cppscan_args(ws, "--output", str(ws["out"]), verb="libmatch")) == 0
    capsys.readouterr()
    assert main(_cppscan_args(ws, "--runtime", str(ws["out"]))) == 0
    out = capsys.readouterr().out
    assert out.startswith("SYNTH.EXE: C (wcc386) on partial evidence")
    assert "C++-only runtime rows: not computed" in out
    assert main(_cppscan_args(ws, "--runtime", str(ws["out"]), "--json")) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["cpp_only_modules_computed"] is False
    assert "no C++ library" in report["cpp_only_modules_gap"]
    assert not report["verdict"].startswith("C (wcc386): ")


def test_cppscan_cpp_verdict_still_exits_0(tmp_path, capsys):
    ws = _cppscan_workspace(tmp_path, xi=(64,))
    assert main(_cppscan_args(ws, "--output", str(ws["out"]), verb="libmatch")) == 0
    capsys.readouterr()
    assert main(_cppscan_args(ws, "--runtime", str(ws["out"]), "--json")) == 0
    report = json.loads(capsys.readouterr().out)
    assert "XI priority 64" in report["verdict"]


def test_cppscan_refuses_orig_mismatch(tmp_path, capsys):
    ws = _cppscan_workspace(tmp_path)
    assert main(_cppscan_args(ws, "--output", str(ws["out"]), verb="libmatch")) == 0
    (ws["orig"] / "SYNTH.EXE").write_bytes(b"MZ not the manifest's file")
    capsys.readouterr()
    assert main(_cppscan_args(ws, "--runtime", str(ws["out"]))) == 1
    assert "does not match" in capsys.readouterr().err


def test_cppscan_help_lists_options(capsys):
    with pytest.raises(SystemExit):
        main(["cppscan", "--help"])
    out = capsys.readouterr().out
    for option in ("--orig", "--manifest", "--watcom-dir", "--runtime", "--json"):
        assert option in out


# ---- probe ----

# cmp al,5; sete al; and eax,0FFh; ret (a hand-written encoding, as in tests/test_probe.py)
PROBE_SETCC_AND = b"\x3c\x05\x0f\x94\xc0\x25\xff\x00\x00\x00\xc3"
PROBE_RUNTIME_ROW = "0x00010500,0x00010520,_TEXT,fake,DOS/CLIB3R.LIB,10.6,fake_,unique,"


def _probe_workspace(tmp_path):
    """cli_workspace whose SYNTH.EXE holds one setcc;and in game code, plus a runtime map."""
    exe = build_le_image(fixups=[b"", b"", b""], patches={0x10400: PROBE_SETCC_AND}).data
    ws = cli_workspace(tmp_path, exe=exe)
    ws["runtime"] = tmp_path / "runtime.csv"
    header = ",".join(RUNTIME_CSV_COLUMNS)
    comment = RUNTIME_CSV_COMMENT.format(name="SYNTH.EXE")
    ws["runtime"].write_text(f"{comment}\n{header}\n{PROBE_RUNTIME_ROW}\n", encoding="utf-8")
    return ws


def _probe_args(ws, *extra):
    return ["probe", "scan", "SYNTH.EXE", "--orig", str(ws["orig"]), "--manifest",
            str(ws["manifest"]), *extra]  # fmt: skip


def test_probe_scan_missing_runtime_map(tmp_path, capsys):
    ws = _probe_workspace(tmp_path)
    assert main(_probe_args(ws, "--runtime", str(tmp_path / "absent.csv"))) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc probe: error:")
    assert "libmatch SYNTH.EXE --write" in err


def test_probe_scan_runtime_map_that_is_not_utf8_is_an_error_line(tmp_path, capsys):
    ws = _probe_workspace(tmp_path)
    ws["runtime"].write_bytes(NOT_UTF8)
    assert main(_probe_args(ws, "--runtime", str(ws["runtime"]))) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc probe: error:")
    assert "runtime.csv" in err and "not UTF-8" in err


def test_probe_scan_default_runtime_is_the_config_dir(tmp_path, capsys, monkeypatch):
    ws = _probe_workspace(tmp_path)
    monkeypatch.setattr(targets, "REPO_ROOT", tmp_path / "repo")
    assert main(_probe_args(ws)) == 1
    err = capsys.readouterr().err
    assert str(tmp_path / "repo" / "config" / "synth" / "runtime.csv") in err


def test_probe_scan_prints_counts(tmp_path, capsys):
    ws = _probe_workspace(tmp_path)
    assert main(_probe_args(ws, "--runtime", str(ws["runtime"]))) == 0
    out = capsys.readouterr().out
    counted = {}
    for line in out.splitlines():
        words = line.split()
        if len(words) == 2 and words[0] in IDIOMS:
            counted[words[0]] = int(words[1])
    assert list(counted) == list(IDIOMS)
    assert counted == {name: int(name == "setcc_and") for name in IDIOMS}


def test_probe_scan_json(tmp_path, capsys):
    ws = _probe_workspace(tmp_path)
    assert main(_probe_args(ws, "--runtime", str(ws["runtime"]), "--json")) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["exe"] == "SYNTH.EXE"
    assert data["counts"]["setcc_and"] == 1
    assert data["lib_bytes"] == 0x20
    # the sized struct copies (none in this EXE), and their evidence line beside the cpu line
    assert data["struct_copy_sizes"] == {"movsd_runs": {}, "rep_movsd": {}}
    cpu = next(i for i, line in enumerate(data["evidence"]) if line.startswith("cpu:"))
    assert data["evidence"][cpu + 1].startswith("struct-copy sizes (cpu -4/-5 evidence")


def test_probe_scan_refuses_orig_mismatch(tmp_path, capsys):
    ws = _probe_workspace(tmp_path)
    (ws["orig"] / "SYNTH.EXE").write_bytes(b"MZ not the manifest's file")
    assert main(_probe_args(ws, "--runtime", str(ws["runtime"]))) == 1
    assert "does not match" in capsys.readouterr().err


def test_probe_requires_a_subcommand(capsys):
    with pytest.raises(SystemExit):
        main(["probe"])
    err = capsys.readouterr().err
    assert "invalid choice" not in err  # the verb exists ...
    assert "required" in err  # ... and wants calibrate or scan


def test_probe_scan_help_lists_options(capsys):
    with pytest.raises(SystemExit):
        main(["probe", "scan", "--help"])
    out = capsys.readouterr().out
    for option in ("--orig", "--manifest", "--runtime", "--json"):
        assert option in out


def _probe_cell(version, flags, sha1, **counts):
    return Cell(version, flags, {name: counts.get(name, 0) for name in IDIOMS}, 0,
                ("math387r", "emu387"), sha1)  # fmt: skip


def _probe_calibration() -> Calibration:
    """Four hand-made cells: the -5r pair ties and emits setcc;and (consistent with
    PROBE_SETCC_AND), the -3r pair ties too but emits only setcc;movzx (not consistent)."""
    five, three = ("-5r", "-s"), ("-3r", "-s")
    return Calibration(
        (
            _probe_cell("10.5", five, "a" * 40, setcc_and=1),
            _probe_cell("10.6", five, "a" * 40, setcc_and=1),
            _probe_cell("10.6", three, "c" * 40, setcc_movzx=1),
            _probe_cell("11.0", three, "c" * 40, setcc_movzx=1),
        ),
        skipped=(),
    )


def test_probe_help_lists_calibrate_and_scan(capsys):
    with pytest.raises(SystemExit):
        main(["probe", "--help"])
    out = capsys.readouterr().out
    assert "calibrate" in out and "scan" in out


def test_probe_calibrate_writes_json(tmp_path, capsys, monkeypatch):
    cal = _probe_calibration()
    seen = {}

    def fake_calibrate(versions, **kwargs):
        seen.update(versions=tuple(versions), **kwargs)
        return cal

    monkeypatch.setattr(probe_module, "calibrate", fake_calibrate)
    output = tmp_path / "cal" / "calibration.json"
    args = ["probe", "calibrate", "--watcom-dir", str(tmp_path / "w"), "--output", str(output)]
    assert main(args) == 0
    assert cal.format() in capsys.readouterr().out
    assert Calibration.from_json(json.loads(output.read_text(encoding="utf-8"))) == cal
    assert seen["versions"] == SWEPT_VERSIONS
    assert seen["watcom_dir"] == tmp_path / "w"


def test_probe_calibrate_json_and_versions(tmp_path, capsys, monkeypatch):
    seen = {}

    def fake_calibrate(versions, **kwargs):
        seen["versions"] = tuple(versions)
        return _probe_calibration()

    monkeypatch.setattr(probe_module, "calibrate", fake_calibrate)
    output = tmp_path / "calibration.json"
    args = ["probe", "calibrate", "--versions", "11.0", "10.6", "--output", str(output), "--json"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == _probe_calibration().to_json()
    assert seen["versions"] == ("11.0", "10.6")


def test_probe_calibrate_refuses_output_inside_the_watcom_tree(tmp_path, capsys, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("calibrate must not run")

    monkeypatch.setattr(probe_module, "calibrate", fail)
    watcom = tmp_path / "w"
    watcom.mkdir()
    output = watcom / "calibration.json"
    assert main(["probe", "calibrate", "--watcom-dir", str(watcom), "--output", str(output)]) == 1
    assert "refusing to write" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("cells", ["some", "none"])
def test_probe_calibrate_gate_refusal_is_fatal(tmp_path, capsys, monkeypatch, cells):
    """A version the D-13 gate refuses fails the run and writes no calibration, as in `cc`;
    a partial calibration would make a later `probe scan` silently leave the version out."""
    kept = _probe_calibration().cells if cells == "some" else ()
    refused = Calibration(kept, skipped=(("11.0", "BINNT/WCC386.EXE is mismatch"),))
    monkeypatch.setattr(probe_module, "calibrate", lambda versions, **kwargs: refused)
    output = tmp_path / "calibration.json"
    assert main(["probe", "calibrate", "--output", str(output)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc probe: error:")
    assert "11.0: BINNT/WCC386.EXE is mismatch" in err
    assert not output.exists()


@pytest.mark.parametrize("default", ["DEFAULT_ORIG", "DEFAULT_INSTALL"])
def test_probe_calibrate_refuses_output_inside_the_default_trees(
    tmp_path, capsys, monkeypatch, default
):
    def fail(*args, **kwargs):
        raise AssertionError("calibrate must not run")

    monkeypatch.setattr(probe_module, "calibrate", fail)
    protected = tmp_path / "default-tree"
    protected.mkdir()
    monkeypatch.setattr(f"reverseapoc.cli.{default}", protected)
    output = protected / "UFO2P.EXE"
    args = ["probe", "calibrate", "--watcom-dir", str(tmp_path / "w"), "--output", str(output)]
    assert main(args) == 1
    assert "refusing to write" in capsys.readouterr().err
    assert not output.exists()


def test_probe_calibrate_help_lists_options(capsys):
    with pytest.raises(SystemExit):
        main(["probe", "calibrate", "--help"])
    out = capsys.readouterr().out
    for option in ("--versions", "--manifest", "--watcom-dir", "--output", "--json"):
        assert option in out


def _write_calibration(path, cal: Calibration):
    path.write_text(json.dumps(cal.to_json()), encoding="utf-8")
    return path


def test_probe_scan_with_calibration(tmp_path, capsys):
    ws = _probe_workspace(tmp_path)
    cal_path = _write_calibration(tmp_path / "calibration.json", _probe_calibration())
    args = _probe_args(ws, "--runtime", str(ws["runtime"]), "--calibration", str(cal_path))
    assert main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    # the plan's verify greps `^consistent:`, so that stays the literal line prefix (review N-1)
    (at,) = [i for i, line in enumerate(lines) if line.startswith("consistent:")]
    # the qualifier follows the count and names what the cells were filtered by: the decisive
    # idiom families only, so a cell the convention, fpu or stack line contradicts can still be
    # listed (review M1)
    assert lines[at] == (
        "consistent: 2 of 4 calibration cells (decisive idiom families byte_compare, "
        "struct_copy only; not checked against the other evidence lines)"
    )
    assert lines[at + 1 : at + 3] == ["  10.5 -5r -s", "  10.6 -5r -s"]
    (ties,) = [line for line in lines if line.startswith("ties:")]
    assert ties == "ties: -5r -s: 10.5 10.6"  # the -3r tie is not among the consistent cells


def test_probe_scan_with_calibration_json(tmp_path, capsys):
    ws = _probe_workspace(tmp_path)
    cal_path = _write_calibration(tmp_path / "calibration.json", _probe_calibration())
    args = _probe_args(ws, "--runtime", str(ws["runtime"]), "--calibration", str(cal_path))
    assert main([*args, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["consistent"] == [
        {"version": "10.5", "flags": ["-5r", "-s"]},
        {"version": "10.6", "flags": ["-5r", "-s"]},
    ]
    assert data["ties"] == [{"flags": ["-5r", "-s"], "versions": ["10.5", "10.6"]}]


@pytest.mark.parametrize("text", ["{not json", "[]", '{"idioms": []}'])
def test_probe_scan_bad_calibration_json(tmp_path, capsys, text):
    ws = _probe_workspace(tmp_path)
    cal_path = tmp_path / "calibration.json"
    cal_path.write_text(text, encoding="utf-8")
    args = _probe_args(ws, "--runtime", str(ws["runtime"]), "--calibration", str(cal_path))
    assert main(args) == 1
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc probe: error:")
    assert str(cal_path) in err
