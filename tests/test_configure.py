"""configure.py writes the build.ninja skeleton."""

from __future__ import annotations

import json
import os
import sys

import pytest

import configure
from conftest import build_le_image, write_manifest
from reverseapoc.cli import main as cli_main
from reverseapoc.targets import load_manifest


def test_render_has_phony_targets_and_phase5_note():
    text = configure.render(["orig/UFO2P.EXE", "orig/TACP.EXE"])
    assert "build check-orig: phony" in text
    assert "build parse-le: phony" in text
    assert "uv run reverseapoc check-orig" in text
    assert "uv run reverseapoc parse-le $in" in text
    assert "parse_le orig/UFO2P.EXE" in text
    assert "parse_le orig/TACP.EXE" in text
    assert "Phase 5" in text
    assert "builddir = build" in text


def test_render_without_executables_still_defines_parse_le():
    text = configure.render([])
    assert "build parse-le: phony" in text
    assert "parse_le orig/" not in text


def test_parse_le_edges_use_builddir_variable():
    text = configure.render(["orig/UFO2P.EXE"])
    assert "build $builddir/always/parse-le/UFO2P.EXE: parse_le orig/UFO2P.EXE" in text
    assert "build parse-le: phony $builddir/always/parse-le/UFO2P.EXE" in text
    assert "$$" not in text


def test_escapes_ninja_special_characters():
    text = configure.render(["orig/MY GAME.EXE"])
    assert "orig/MY$ GAME.EXE" in text
    assert "$builddir/always/parse-le/MY$ GAME.EXE" in text


def test_find_executables_is_case_insensitive_and_sorted(tmp_path):
    for name in ("UFO2P.EXE", "tacp.exe", "README.TXT"):
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in configure.find_executables(tmp_path)] == ["tacp.exe", "UFO2P.EXE"]
    assert configure.find_executables(tmp_path / "missing") == []


def test_main_writes_build_ninja(tmp_path):
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "UFO2P.EXE").write_bytes(b"x")
    out = tmp_path / "build.ninja"
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "UFO2P.EXE" in text and "build check-orig: phony" in text


def _rule_block(text: str, name: str) -> list[str]:
    """The indented lines that follow `rule <name>` in build.ninja text."""
    lines = text.splitlines()
    start = lines.index(f"rule {name}") + 1
    block = []
    for line in lines[start:]:
        if not line.startswith("  "):
            break
        block.append(line.strip())
    return block


def test_render_has_verify_edge():
    # D-09 / RT-03: `ninja verify` runs the `rebuild` verb next to check-orig and parse-le.
    text = configure.render(["orig/UFO2P.EXE"])
    assert "rule rebuild" in text
    block = _rule_block(text, "rebuild")
    # WR-05: the rebuild command carries the orig dir (default layout: orig/).
    # IN-11: it writes into build, the builddir next to build.ninja, not the repo's build/.
    assert "command = uv run reverseapoc rebuild --orig orig --out build" in block
    assert "description = REBUILD build/" in block
    assert "pool = console" in block
    assert "build $builddir/always/verify: rebuild" in text
    assert "build verify: phony $builddir/always/verify" in text
    header_comment = [line for line in text.splitlines() if line.startswith("#")]
    assert any("ninja verify" in line for line in header_comment)


def test_render_without_executables_still_defines_verify():
    assert "build verify: phony" in configure.render([])


def test_main_writes_verify_edge(tmp_path):
    orig = tmp_path / "orig"
    orig.mkdir()
    out = tmp_path / "build.ninja"
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 0
    assert "build verify: phony" in out.read_text(encoding="utf-8")


# ---- WR-05: --orig reaches the check-orig and verify edges --------------------------------------

CHECK_ORIG_CMD = "command = uv run reverseapoc check-orig --orig "
REBUILD_CMD = "command = uv run reverseapoc rebuild --orig "


def _command(text: str, rule: str) -> str:
    """The `command = ...` line of `rule <rule>` in build.ninja text."""
    return next(line for line in _rule_block(text, rule) if line.startswith("command = "))


def test_render_passes_orig_to_check_orig_and_rebuild():
    text = configure.render([], orig="../elsewhere")
    assert CHECK_ORIG_CMD + "../elsewhere" in _rule_block(text, "check_orig")
    assert REBUILD_CMD + "../elsewhere --out build" in _rule_block(text, "rebuild")
    text = configure.render(["orig/UFO2P.EXE"])
    assert CHECK_ORIG_CMD + "orig" in _rule_block(text, "check_orig")
    assert REBUILD_CMD + "orig --out build" in _rule_block(text, "rebuild")
    # ninja shell-quotes $in itself, so the rule must not quote it again (WR-06).
    assert "command = uv run reverseapoc parse-le $in" in _rule_block(text, "parse_le")


def _orig_from_parse_le_edge(text: str) -> str:
    """The orig dir build.ninja reads UFO2P.EXE from, taken from its parse_le edge line."""
    prefix = "build $builddir/always/parse-le/UFO2P.EXE: parse_le "
    line = next(line for line in text.splitlines() if line.startswith(prefix))
    return line.removeprefix(prefix).removesuffix("/UFO2P.EXE")


@pytest.mark.parametrize(
    ("out_parts", "expected"),
    [(("build.ninja",), "elsewhere"), (("cfg", "build.ninja"), "../elsewhere")],
    ids=["same-dir", "sub-dir"],
)
def test_main_passes_orig_to_check_orig_and_rebuild(tmp_path, out_parts, expected):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "UFO2P.EXE").write_bytes(b"x")
    out = tmp_path.joinpath(*out_parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    assert configure.main(["--orig", str(elsewhere), "--output", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    orig = _orig_from_parse_le_edge(text)
    assert orig == expected
    assert _command(text, "check_orig").endswith(f"--orig {orig}")
    assert _command(text, "rebuild").endswith(f"--orig {orig} --out build")


def test_generated_commands_read_the_orig_dir(tmp_path, monkeypatch, capsys):
    # End to end on the host: the commands ninja would run read the --orig dir, not orig/.
    name = load_manifest()[0].name
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / name).write_bytes(b"not the game")
    out = tmp_path / "build.ninja"
    assert configure.main(["--orig", str(elsewhere), "--output", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    prefix = "command = uv run reverseapoc "

    assert cli_main(_command(text, "rebuild").removeprefix(prefix).split()) == 1
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith("REFUSED") and name in line for line in lines)

    assert cli_main(_command(text, "check_orig").removeprefix(prefix).split()) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "checking elsewhere"
    assert any("MISMATCH" in line and name in line for line in lines)


# ---- WR-06: build.ninja never carries a path ninja or the shell would misread -------------------

UNREPRESENTABLE = ["orig/A|B.EXE", "orig/A\nB.EXE", "orig/A\rB.EXE"]


@pytest.mark.parametrize("path", UNREPRESENTABLE, ids=["pipe", "lf", "cr"])
def test_render_refuses_names_ninja_cannot_represent(path):
    with pytest.raises(configure.ConfigureError) as excinfo:
        configure.render([path])
    assert repr(path) in str(excinfo.value)


def test_main_refuses_names_ninja_cannot_represent(tmp_path, monkeypatch, capsys):
    # find_executables is replaced, so this runs on Windows, where such a file cannot exist.
    orig = tmp_path / "orig"
    monkeypatch.setattr(configure, "find_executables", lambda _dir: [orig / "A|B.EXE"])
    out = tmp_path / "build.ninja"
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("configure.py: error:")
    assert "'|'" in err
    assert not out.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows file names cannot hold | or LF")
@pytest.mark.parametrize("name", ["A|B.exe", "A\nB.exe"], ids=["pipe", "lf"])
def test_main_refuses_real_names_ninja_cannot_represent(tmp_path, name):
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / name).write_bytes(b"x")
    out = tmp_path / "build.ninja"
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 1
    assert not out.exists()


UNSAFE_ORIG_DIRS = ["my orig", "a;b", "a$b", "a`b`", "a'b", 'a"b', "a&b", "a\nb", "~/orig"]


@pytest.mark.parametrize("orig", UNSAFE_ORIG_DIRS)
def test_render_refuses_an_unsafe_orig_dir(orig):
    text = configure.render([], orig="../safe-dir")
    assert CHECK_ORIG_CMD + "../safe-dir" in _rule_block(text, "check_orig")
    assert REBUILD_CMD + "../safe-dir --out build" in _rule_block(text, "rebuild")
    with pytest.raises(configure.ConfigureError) as excinfo:
        configure.render([], orig=orig)
    assert repr(orig) in str(excinfo.value)


@pytest.mark.parametrize("name", ["my orig", "a;b"])
def test_main_refuses_an_unsafe_orig_dir(tmp_path, capsys, name):
    orig = tmp_path / name
    orig.mkdir()
    out = tmp_path / "build.ninja"
    sentinel = b"# sentinel: configure.py must leave this file alone\n"
    out.write_bytes(sentinel)
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("configure.py: error:")
    assert name in err
    assert out.read_bytes() == sentinel


def test_main_keeps_names_with_spaces(tmp_path):
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "MY GAME.EXE").write_bytes(b"x")
    out = tmp_path / "build.ninja"
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 0
    assert "parse_le orig/MY$ GAME.EXE" in out.read_text(encoding="utf-8")


# ---- WR-07: a name build.ninja cannot hold as UTF-8 is refused, and build.ninja stays intact -----

SENTINEL = b"# sentinel: configure.py must leave this file alone\n"
NOT_UTF8 = ["orig/A\udcffB.EXE", "orig/A\ud800B.EXE"]


@pytest.mark.parametrize("path", NOT_UTF8, ids=["low-surrogate", "high-surrogate"])
def test_render_refuses_names_that_are_not_utf8(path):
    with pytest.raises(configure.ConfigureError) as excinfo:
        configure.render([path])
    assert repr(path) in str(excinfo.value)
    assert "UTF-8" in str(excinfo.value)


def test_main_refuses_names_that_are_not_utf8(tmp_path, monkeypatch, capsys):
    # find_executables is replaced, so this runs on Windows too.
    orig = tmp_path / "orig"
    monkeypatch.setattr(configure, "find_executables", lambda _dir: [orig / "A\udcffB.EXE"])
    out = tmp_path / "build.ninja"
    out.write_bytes(SENTINEL)
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("configure.py: error:")
    assert "\\udcff" in err
    assert out.read_bytes() == SENTINEL


@pytest.mark.skipif(
    sys.platform != "linux", reason="needs a file system that stores non-UTF-8 byte names"
)
def test_main_refuses_real_names_that_are_not_utf8(tmp_path):
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / os.fsdecode(b"A\xffB.exe")).write_bytes(b"x")
    out = tmp_path / "build.ninja"
    out.write_bytes(SENTINEL)
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 1
    assert out.read_bytes() == SENTINEL


def test_main_never_truncates_on_an_encoding_failure(tmp_path, monkeypatch, capsys):
    # The bytes exist before build.ninja is opened, even for text that slips past render().
    monkeypatch.setattr(configure, "render", lambda exes, *, orig, **_units: "# A\udcffB\n")
    out = tmp_path / "build.ninja"
    out.write_bytes(SENTINEL)
    assert configure.main(["--orig", str(tmp_path / "orig"), "--output", str(out)]) == 1
    assert capsys.readouterr().err.startswith("configure.py: error:")
    assert out.read_bytes() == SENTINEL


# ---- IN-09: no path in build.ninja reaches reverseapoc's argparse as an option ------------------

OPTION_LIKE_ORIG_DIRS = ["-h", "--orig", "-"]


@pytest.mark.parametrize("orig", OPTION_LIKE_ORIG_DIRS)
def test_render_refuses_an_option_like_orig_dir(orig):
    text = configure.render([], orig="../safe-dir")
    assert CHECK_ORIG_CMD + "../safe-dir" in _rule_block(text, "check_orig")
    with pytest.raises(configure.ConfigureError) as excinfo:
        configure.render([], orig=orig)
    assert repr(orig) in str(excinfo.value)


@pytest.mark.parametrize(
    ("exe", "orig"), [("-h.exe", "."), ("-h/UFO2P.EXE", "orig")], ids=["exe-name", "orig-dir"]
)
def test_render_refuses_an_option_like_exe_path(exe, orig):
    # Only the full path is an argument; a bare name under $builddir/always/ never is.
    assert "parse_le orig/-h.exe" in configure.render(["orig/-h.exe"])
    with pytest.raises(configure.ConfigureError) as excinfo:
        configure.render([exe], orig=orig)
    assert repr(exe) in str(excinfo.value)


def test_main_refuses_an_option_like_orig_dir(tmp_path, capsys):
    orig = tmp_path / "-h"
    orig.mkdir()
    out = tmp_path / "build.ninja"
    out.write_bytes(SENTINEL)
    assert configure.main(["--orig", str(orig), "--output", str(out)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("configure.py: error:")
    assert "'-h'" in err
    assert out.read_bytes() == SENTINEL


def test_main_refuses_an_option_like_exe_name(tmp_path, capsys):
    (tmp_path / "-h.exe").write_bytes(b"x")
    out = tmp_path / "build.ninja"
    out.write_bytes(SENTINEL)
    assert configure.main(["--orig", str(tmp_path), "--output", str(out)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("configure.py: error:")
    assert "'-h.exe'" in err
    assert out.read_bytes() == SENTINEL


# ---- IN-10, IN-11, IN-08: the header names the orig dir it reads and the builddir it writes ----


def test_render_check_orig_description_names_the_orig_dir():
    text = configure.render([], orig="../elsewhere")
    assert "description = CHECK-ORIG ../elsewhere" in _rule_block(text, "check_orig")
    text = configure.render(["orig/UFO2P.EXE"])
    assert "description = CHECK-ORIG orig" in _rule_block(text, "check_orig")


def test_header_comments_name_no_fixed_orig_dir():
    text = configure.render([], orig="../elsewhere")
    comments = [line for line in text.splitlines() if line.startswith("#")]
    assert [line for line in comments if "orig/" in line] == []
    for target in ("ninja check-orig", "ninja parse-le", "ninja verify"):
        assert any(target in line for line in comments), target


def test_rebuild_out_is_the_builddir():
    text = configure.render([], orig="../elsewhere")
    builddir = next(line for line in text.splitlines() if line.startswith("builddir = "))
    out = _command(text, "rebuild").partition(" --out ")[2].split(" ")[0]
    assert out == builddir.removeprefix("builddir = ")


def test_generated_rebuild_writes_into_builddir(tmp_path, monkeypatch, capsys):
    # End to end on the host: `ninja verify` runs in the build.ninja dir and writes into its
    # builddir. The CLI default is moved into tmp_path so a failing run never writes build/.
    monkeypatch.setattr("reverseapoc.cli.DEFAULT_OUT", tmp_path / "default-out")
    data = build_le_image().data
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "IN11.EXE").write_bytes(data)
    manifest = write_manifest(tmp_path / "m.toml", {"IN11.EXE": data})
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    assert configure.main(["--orig", str(elsewhere), "--output", str(cfg / "build.ninja")]) == 0
    text = (cfg / "build.ninja").read_text(encoding="utf-8")
    capsys.readouterr()
    monkeypatch.chdir(cfg)
    argv = _command(text, "rebuild").removeprefix("command = uv run reverseapoc ").split()
    assert cli_main([*argv, "--manifest", str(manifest)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith("OK") and "IN11.EXE" in line for line in lines)
    assert (cfg / "build" / "IN11.EXE").read_bytes() == data
    assert not (tmp_path / "default-out" / "IN11.EXE").exists()


def test_no_stale_phase_wording():
    text = configure.render([])
    for where in (configure.__doc__, text):
        assert "Phase 2" not in where
        assert "skeleton" not in where
    assert "Phase 5" in text


# ---- Phase 5 (SPL-06): units with C become compile, convert and cut edges ----------------------

UNIT = "u_00010000"
FUNCTIONS_CSV = """\
start,end,name,kind,unit,evidence
0x00010000,0x00010010,func_00010000,game,u_00010000,call
0x00010010,0x00010020,func_00010010,game,u_00010000,call
"""
UNITS_CSV = """\
unit,start,end,reason
u_00010000,0x00010000,0x00010020,first
"""
UNIT_SOURCE = """\
#include "common.h"

INCLUDE_ASM(func_00010010);

int func_00010000(void)
{
    return 0;
}
"""


def _split_tree(tmp_path, *, source=UNIT_SOURCE, units=UNITS_CSV, functions=FUNCTIONS_CSV):
    """A tmp orig, config and src tree for UFO2P.EXE with one unit; returns configure argv."""
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "UFO2P.EXE").write_bytes(b"x")
    exe_config = tmp_path / "config" / "ufo2p"
    exe_config.mkdir(parents=True)
    (exe_config / "units.csv").write_text(units, encoding="utf-8")
    (exe_config / "functions.csv").write_text(functions, encoding="utf-8")
    exe_src = tmp_path / "src" / "ufo2p"
    exe_src.mkdir(parents=True)
    if source is not None:
        (exe_src / f"{UNIT}.c").write_text(source, encoding="utf-8")
    return [
        "--orig", str(orig),
        "--config", str(tmp_path / "config"),
        "--src", str(tmp_path / "src"),
        "--output", str(tmp_path / "build.ninja"),
    ]  # fmt: skip


def _edge(text: str, output: str) -> str:
    """The `build <output>: ...` line of build.ninja text."""
    return next(line for line in text.splitlines() if line.startswith(f"build {output}:"))


def test_unit_with_source_gets_compile_edges(tmp_path):
    assert configure.main(_split_tree(tmp_path)) == 0
    text = (tmp_path / "build.ninja").read_text(encoding="utf-8")
    for rule in ("cc", "omf2elf", "target"):
        assert f"rule {rule}" in text
    obj = f"$builddir/ufo2p/obj/{UNIT}.obj"
    base = f"$builddir/ufo2p/base/{UNIT}.o"
    target = f"$builddir/ufo2p/target/{UNIT}.o"
    assert _edge(text, obj).startswith(f"build {obj}: cc src/ufo2p/{UNIT}.c")
    assert _edge(text, base).startswith(f"build {base}: omf2elf {obj}")
    assert _edge(text, target).startswith(f"build {target}: target")

    objdiff = json.loads((tmp_path / "objdiff.json").read_text(encoding="utf-8"))
    (unit,) = [u for u in objdiff["units"] if u["name"] == f"ufo2p/{UNIT}"]
    assert unit["target_path"] == f"build/ufo2p/target/{UNIT}.o"
    assert unit["base_path"] == f"build/ufo2p/base/{UNIT}.o"

    commands = json.loads((tmp_path / "compile_commands.json").read_text(encoding="utf-8"))
    (entry,) = commands
    assert entry["file"].endswith(f"src/ufo2p/{UNIT}.c")
    assert "-std=gnu89" in entry["arguments"]
    assert "-c" in entry["arguments"]


def test_main_creates_the_output_directory(tmp_path):
    out = tmp_path / "cfg-smoke" / "build.ninja"
    assert configure.main(["--orig", str(tmp_path / "orig"), "--output", str(out)]) == 0
    for name in ("build.ninja", "objdiff.json", "compile_commands.json"):
        assert (out.parent / name).is_file(), name
