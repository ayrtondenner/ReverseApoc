"""configure.py writes the build.ninja skeleton."""

from __future__ import annotations

import json
import os
import sys

import pytest

import configure
from conftest import build_le_image, write_manifest
from reverseapoc import check, unitdefs
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, SymbolRow, write_symbols_csv
from reverseapoc.targets import load_manifest


def test_render_has_phony_targets_and_compile_rules():
    text = configure.render(["orig/UFO2P.EXE", "orig/TACP.EXE"])
    assert "build check-orig: phony" in text
    assert "build parse-le: phony" in text
    assert "uv run reverseapoc check-orig" in text
    assert "uv run reverseapoc parse-le $in" in text
    assert "parse_le orig/UFO2P.EXE" in text
    assert "parse_le orig/TACP.EXE" in text
    assert "rule cc" in text
    assert "rule omf2elf" in text
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
        # The compile rules are here now; nothing promises them for a later phase.
        assert "Phase 5" not in where
        assert "arrive in" not in where
        assert "Verification targets only" not in where
    assert "rule cc" in text
    assert "rule omf2elf" in text
    comments = [line for line in text.splitlines() if line.startswith("#")]
    for target in ("ninja objects", "ninja lint", "ninja asm", "ninja verify"):
        assert any(target in line for line in comments), target


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


def _split_tree(
    tmp_path, *, source=UNIT_SOURCE, units=UNITS_CSV, functions=FUNCTIONS_CSV, exe="UFO2P.EXE"
):
    """A tmp orig, config (with its own targets.toml) and src tree for `exe` with one unit;
    returns configure argv."""
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / exe).write_bytes(b"x")
    write_manifest(_config_dir(tmp_path, "targets.toml"), {exe: b"x"})
    stem = exe.removesuffix(".EXE").lower()
    exe_config = tmp_path / "config" / stem
    exe_config.mkdir(parents=True)
    (exe_config / "units.csv").write_text(units, encoding="utf-8")
    (exe_config / "functions.csv").write_text(functions, encoding="utf-8")
    exe_src = tmp_path / "src" / stem
    exe_src.mkdir(parents=True)
    if source is not None:
        (exe_src / f"{UNIT}.c").write_text(source, encoding="utf-8")
    return [
        "--orig", str(orig),
        "--config", str(tmp_path / "config"),
        "--src", str(tmp_path / "src"),
        "--output", str(tmp_path / "build.ninja"),
    ]  # fmt: skip


def _config_dir(tmp_path, name: str):
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    return config / name


def test_config_dir_brings_its_own_manifest(tmp_path):
    """Code review IN-04: --config DIR reads DIR/targets.toml, not the repository's, so the
    CSVs and the manifest come from one tree. SYN.EXE is in no repository manifest."""
    assert configure.main(_split_tree(tmp_path, exe="SYN.EXE")) == 0
    text = (tmp_path / "build.ninja").read_text(encoding="utf-8")
    obj = f"$builddir/syn/obj/{UNIT}.obj"
    assert _edge(text, obj).startswith(f"build {obj} | {obj}.prov.json: cc src/syn/{UNIT}.c")
    assert "$builddir/ufo2p/" not in text


def test_config_dir_without_a_manifest_is_refused(tmp_path, capsys):
    argv = _split_tree(tmp_path)
    (tmp_path / "config" / "targets.toml").unlink()
    _assert_refused(tmp_path, argv, capsys, str(tmp_path / "config" / "targets.toml"),
                    "--config")  # fmt: skip


def _edge(text: str, output: str) -> str:
    """The `build <output>: ...` line of build.ninja text (or `build <output> | <implicit>: ...`
    for an edge with implicit outputs)."""
    heads = (f"build {output}:", f"build {output} |")
    return next(line for line in text.splitlines() if line.startswith(heads))


def test_cc_edge_headers_are_the_stamped_headers(tmp_path, monkeypatch):
    """Fix round 2, N1: one definition of the project headers. The cc edge's implicit header
    inputs are compiler.project_headers of the repository, the same files the stamp's
    include_sha256 covers, so a refusal for a header is always one `ninja objects` clears."""
    from reverseapoc import compiler

    real = compiler.project_headers(configure.ROOT)
    assert real and all(p.parent == configure.ROOT / "include" and p.suffix == ".h" for p in real)
    fake = tmp_path / "only.h"
    monkeypatch.setattr(configure, "project_headers", lambda root: [fake])
    layout = configure.Layout.for_base(tmp_path, config=tmp_path / "config", src=tmp_path / "src",
                                       output=tmp_path / "build.ninja")  # fmt: skip
    assert [p for p in layout.cc_inputs if p.endswith(".h")] == ["only.h"]


def test_regeneration_edge_watches_the_include_dir(tmp_path):
    """Fix round 2, N1: a header added to include/ changes the cc edges' inputs, so the
    directory is a regeneration input, as each src/<exe> is."""
    assert configure.main(_split_tree(tmp_path)) == 0
    text = (tmp_path / "build.ninja").read_text(encoding="utf-8")
    include = configure.ninja_path(configure._relative(configure.ROOT / "include", tmp_path))
    assert include in _edge(text, "build.ninja").split(" | ", 1)[1].split()


def test_cc_edge_declares_the_stamp(tmp_path):
    """DI-06 part a: the provenance stamp `reverseapoc cc` writes next to the object is an
    implicit output of the cc edge, so ninja rebuilds an object that has no stamp yet."""
    assert configure.main(_split_tree(tmp_path)) == 0
    text = (tmp_path / "build.ninja").read_text(encoding="utf-8")
    obj = f"$builddir/ufo2p/obj/{UNIT}.obj"
    outputs, _, inputs = _edge(text, obj).partition(": cc ")
    assert outputs == f"build {obj} | {obj}.prov.json"
    assert inputs.startswith(f"src/ufo2p/{UNIT}.c")


def test_unit_with_source_gets_compile_edges(tmp_path):
    assert configure.main(_split_tree(tmp_path)) == 0
    text = (tmp_path / "build.ninja").read_text(encoding="utf-8")
    for rule in ("cc", "omf2elf", "target"):
        assert f"rule {rule}" in text
    obj = f"$builddir/ufo2p/obj/{UNIT}.obj"
    base = f"$builddir/ufo2p/base/{UNIT}.o"
    target = f"$builddir/ufo2p/target/{UNIT}.o"
    assert _edge(text, obj).startswith(f"build {obj} | {obj}.prov.json: cc src/ufo2p/{UNIT}.c")
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


GENERATED = ("build.ninja", "objdiff.json", "compile_commands.json")


def _rows(*specs):
    """FunctionRows of UNIT from (start, kind) pairs, each 0x10 bytes long."""
    rows = []
    for start, kind in specs:
        name = f"func_{start:08X}" if kind in ("game", "thunk") else f"D_{start:08X}"
        if kind == "runtime":
            name = f"rt_{start:x}_"
        rows.append(FunctionRow(start, start + 0x10, name, kind, UNIT, "call"))
    return rows


TWO_GAME = _rows((0x10000, "game"), (0x10010, "game"))


def test_unit_source_complete_file_has_no_problems():
    assert configure.check_unit_source(UNIT_SOURCE, TWO_GAME) == []


@pytest.mark.parametrize("include", [
    '#include "../../build/driver/r/ufo2p/func_00010010/attempt-1/notes.md"',
    '#include "sub/x.h"', "#include <../build/x.h>", '#include "notes.md"',
    "#include HEADER", '#include \\\n "../x.h"',
])  # fmt: skip
def test_unit_source_refuses_a_path_include(include, tmp_path):
    """06-REVIEW CR-02: only a bare header name ("name.h" or <name.h>) may be included, so the
    build and the gate refuse a unit that pulls in any other file (the hook's rule, defence in
    depth)."""
    text = UNIT_SOURCE.replace('#include "common.h"', include)
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "#include" in problem and "line 1" in problem
    assert problem.endswith('a bare header name: "name.h" from include/, or <name.h> from '
                            "include/ or the compiler's own headers"), problem  # fmt: skip
    path = tmp_path / f"{UNIT}.c"
    path.write_bytes(text.encode("utf-8"))
    with pytest.raises(configure.ConfigureError, match="#include"):
        configure._check_source(path, TWO_GAME)


@pytest.mark.parametrize("include", ['#include "common.h"', "#include <common.h>",
                                     '  #  include "foo_2.h" /* note */',
                                     "#include <conio.h>", "#include <i86.h>"])  # fmt: skip
def test_unit_source_allows_a_bare_header_include(include):
    text = UNIT_SOURCE.replace('#include "common.h"', include)
    assert configure.check_unit_source(text, TWO_GAME) == []


def test_unit_source_neither_defined_nor_marked():
    text = "int func_00010000(void) { return 0; }\n"
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "neither" in problem


def test_unit_source_defined_and_marked():
    text = UNIT_SOURCE + "INCLUDE_ASM(func_00010000);\n"
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010000" in problem and "both" in problem


def test_unit_source_marked_twice():
    text = UNIT_SOURCE + "INCLUDE_ASM(func_00010010);\n"
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "2 times" in problem


@pytest.mark.parametrize(
    "extra",
    ["INCLUDE_ASM(func_00020000);\n", "void func_00020000(void)\n{\n}\n"],
    ids=["marker", "definition"],
)
def test_unit_source_names_a_function_outside_the_unit(extra):
    (problem,) = configure.check_unit_source(UNIT_SOURCE + extra, TWO_GAME)
    assert "func_00020000" in problem and "not a function of the unit" in problem


def test_unit_source_prototype_and_call_are_not_definitions():
    text = (
        "INCLUDE_ASM(func_00010000);\n"
        "int func_00010010(void);\n"
        "static int f(void)\n{\n    if (func_00010010()) {\n        return 1;\n    }\n"
        "    return func_00010010();\n}\n"
    )
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "neither" in problem


def test_unit_source_ignores_comments():
    text = (
        "/* INCLUDE_ASM(func_00010010); */\n"
        "INCLUDE_ASM(func_00010000);\n"
        "/*\nint func_00010010(void)\n{\n}\n*/\n"
    )
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "neither" in problem


@pytest.mark.parametrize(
    "commented",
    ["// INCLUDE_ASM(func_00010010);\n", "// int func_00010010(void) {\n//}\n"],
    ids=["marker", "definition"],
)
def test_unit_source_ignores_line_comments(commented):
    # Review fix round 1: wcc386 and clang gnu89 accept // comments.
    text = "INCLUDE_ASM(func_00010000);\n" + commented
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "neither" in problem


def test_unit_source_line_comment_inside_a_string_is_not_a_comment():
    text = 'static char *s = "http://x"; INCLUDE_ASM(func_00010010);\nINCLUDE_ASM(func_00010000);\n'
    assert configure.check_unit_source(text, TWO_GAME) == []


def test_unit_source_if0_block_is_dead():
    text = (
        "INCLUDE_ASM(func_00010000);\n"
        "#if 0\n#ifdef FOO\nINCLUDE_ASM(func_00010010);\n#endif\n"
        "int func_00010010(void)\n{\n    return 0;\n}\n#endif\n"
    )
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "neither" in problem


def test_unit_source_if0_else_branch_is_live():
    text = (
        "INCLUDE_ASM(func_00010010);\n"
        "#if 0\nINCLUDE_ASM(func_00010000);\n#else\n"
        "int func_00010000(void)\n{\n    return 0;\n}\n#endif\n"
    )
    assert configure.check_unit_source(text, TWO_GAME) == []


@pytest.mark.parametrize(
    ("text", "line", "directive"),
    [
        ("#ifdef FOO\n#endif\n", 1, "#ifdef"),
        ("#ifndef FOO\n#endif\n", 1, "#ifndef"),
        ("int x;\n#if FOO\n#endif\n", 2, "#if"),
        ("#if 1\n#endif\n", 1, "#if"),
        ("#if 0\n#elif FOO\n#endif\n", 2, "#elif"),
        ("/*\n\n*/\n  #  ifdef FOO\n#endif\n", 4, "#ifdef"),
        ("#endif\n", 1, "#endif"),
        ("#if 0\n#else\n#else\n#endif\n", 3, "#else"),
    ],
    ids=["ifdef", "ifndef", "if-expr", "if-1", "elif", "after-comment", "stray-endif",
         "second-else"],  # fmt: skip
)
def test_unit_source_refuses_conditionals_it_cannot_evaluate(text, line, directive):
    # Orchestrator ruling (review round 1): only #if 0 is understood; anything else fails closed.
    shift = UNIT_SOURCE.count("\n")
    (problem,) = configure.check_unit_source(UNIT_SOURCE + text, TWO_GAME)
    assert f"line {line + shift}" in problem
    assert directive in problem


def test_unit_source_refuses_an_unterminated_if0():
    (problem,) = configure.check_unit_source(UNIT_SOURCE + "#if 0\nint y;\n", TWO_GAME)
    assert "#if 0" in problem and "#endif" in problem


# ---- DI-05 (05-REVIEW item 15): backslash-newline is spliced as in translation phase 2 ---------

# The three 05-REVIEW probe texts: a marker on the continuation line of a `//` comment, a
# definition on the continuation line of a `#define`, and a definition on the continuation line
# of a `//` comment. Each maps to the (marked, defined) sets the compiler would see.
CONTINUATION_PROBES = {
    "line-comment-marker": (
        "INCLUDE_ASM(func_00010000);\n// note \\\nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    "define-definition": (
        "INCLUDE_ASM(func_00010010);\n#define X \\\nint func_00010000(void) { return 0; }\n",
        {"func_00010010"},
        set(),
    ),
    "line-comment-definition": (
        "INCLUDE_ASM(func_00010000);\n// x \\\nint func_00010010(void)\n{\n    return 0;\n}\n",
        {"func_00010000"},
        set(),
    ),
    # 06-03 review I1: a #define continued through a spliced string literal; the marker is in
    # the macro body.
    "define-string": (
        'INCLUDE_ASM(func_00010000);\n#define S "a\\\nb" INCLUDE_ASM(func_00010010);\n',
        {"func_00010000"},
        set(),
    ),
    # 06-03 review M1: translation phase 2 splices before comments are recognised (phase 3),
    # so a backslash-newline inside a comment delimiter still forms it.
    "line-comment-opener-splice": (
        "INCLUDE_ASM(func_00010000);\n/\\\n/ INCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    "block-comment-opener-splice": (
        "INCLUDE_ASM(func_00010000);\n/\\\n* INCLUDE_ASM(func_00010010); */\n",
        {"func_00010000"},
        set(),
    ),
    "block-comment-closer-splice": (
        "/* x *\\\n/ INCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000", "func_00010010"},
        set(),
    ),
    # A comment is one space (phase 3), so a block comment spanning lines inside a #define
    # keeps the directive going: the marker after it is in the macro body.
    "define-block-comment": (
        "INCLUDE_ASM(func_00010000);\n#define X /* a\nb */ INCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    # Splices and multi-line comments inside live code join it as the compiler does.
    "code-splice-marker": (
        "INCLUDE_ASM(func_00010000);\nINCLUDE_\\\nASM(func_00010010);\n",
        {"func_00010000", "func_00010010"},
        set(),
    ),
    "code-comment-in-marker": (
        "INCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010) /*\n*/ ;\n",
        {"func_00010000", "func_00010010"},
        set(),
    ),
    # 06-03 re-review N1: wcc386 10.6 also splices a backslash followed by spaces or tabs and
    # then a newline, in every context (a form feed or vertical tab does not splice); it maps
    # C89 trigraphs first (`??/` is a backslash, `??=` a `#`), and a raw CRLF is one line break.
    # Each expected reading is what `wcc386 -zq -p` (10.6, BINNT) preprocesses the text to.
    "blank-splice-closer-definition": (
        "INCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010);\n"
        "/* x *\\ \n/ int func_00010000(void) { return 0; } /* y */\n",
        {"func_00010000", "func_00010010"},
        {"func_00010000"},
    ),
    "blank-splice-string-definition": (
        'INCLUDE_ASM(func_00010010);\nchar *s = "a\\ \nb"; int func_00010000(void) { return 0; }\n',
        {"func_00010010"},
        {"func_00010000"},
    ),
    "blank-splice-name": (
        "INCLUDE_ASM(func_00010010);\nint func_0001\\ \n0000(void) { return 0; }\n",
        {"func_00010010"},
        {"func_00010000"},
    ),
    "blank-splice-define": (
        "INCLUDE_ASM(func_00010000);\n#define X \\ \nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    "tab-splice-define": (
        "INCLUDE_ASM(func_00010000);\n#define X \\\t \nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    "blank-splice-line-comment": (
        "INCLUDE_ASM(func_00010000);\n// c \\ \nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    "blank-splice-if0": (
        "INCLUDE_ASM(func_00010000);\n#if \\ \n0\nINCLUDE_ASM(func_00010010);\n#endif\n",
        {"func_00010000"},
        set(),
    ),
    "formfeed-is-no-splice": (
        "INCLUDE_ASM(func_00010000);\n// c \\\f\nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000", "func_00010010"},
        set(),
    ),
    "vtab-is-no-splice": (
        "INCLUDE_ASM(func_00010000);\n// c \\\v\nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000", "func_00010010"},
        set(),
    ),
    "trigraph-line-comment": (
        "INCLUDE_ASM(func_00010000);\n// x ??/\nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    "trigraph-closer": (
        "/* x *??/\n/ INCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000", "func_00010010"},
        set(),
    ),
    "trigraph-directive": (
        "INCLUDE_ASM(func_00010000);\n??=define X \\\nINCLUDE_ASM(func_00010010);\n",
        {"func_00010000"},
        set(),
    ),
    "crlf-closer": (
        "/* x *\\\r\n/ INCLUDE_ASM(func_00010000);\r\nINCLUDE_ASM(func_00010010);\r\n",
        {"func_00010000", "func_00010010"},
        set(),
    ),
    "crlf-string": (
        'INCLUDE_ASM(func_00010010);\r\nchar *s = "a\\\r\nb"; '
        "int func_00010000(void) { return 0; }\r\n",
        {"func_00010010"},
        {"func_00010000"},
    ),
}


def test_blank_splice_closer_hides_no_definition():
    """N1: the definition after `*\\ <newline>/` is live for wcc386, so the D-12 check sees it
    next to its marker and reports both (it used to read it as part of the comment)."""
    text, _, _ = CONTINUATION_PROBES["blank-splice-closer-definition"]
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010000" in problem and "both" in problem


INLINE_ASM_PROBES = {
    "blank-splice-closer": "/* x *\\ \n/ void f(void) { _asm int 3 } /* y */\n",
    "blank-splice-string": 'char *s = "a\\ \nb"; void f(void) { _asm int 3 } char *t = "x";\n',
    "trigraph-closer": "/* x *??/\n/ void f(void) { _asm int 3 } /* y */\n",
    "crlf-closer": "/* x *\\\r\n/ void f(void) { _asm int 3 } /* y */\r\n",
}


@pytest.mark.parametrize("probe", sorted(INLINE_ASM_PROBES))
def test_inline_asm_stays_visible_to_the_scanner(probe):
    """06-12's hooks scan the same output for inline asm; wcc386 keeps `_asm int 3` live in
    each probe, so the scanner must too (the chain check.source_marks runs)."""
    text = INLINE_ASM_PROBES[probe]
    code = configure._live_code(configure._NOT_CODE.sub(configure._blank, text))
    assert "_asm int 3" in code


def test_code_text_is_the_shared_entry_point():
    """configure.code_text is the one entry point (phases 1-2, then the scanner) that the
    D-12 check, check.source_marks and 06-12's hooks share."""
    for text in [*INLINE_ASM_PROBES.values(), *(p[0] for p in CONTINUATION_PROBES.values())]:
        expected = configure._live_code(configure._NOT_CODE.sub(configure._blank, text))
        assert configure.code_text(text) == expected


def test_normalisation_keeps_the_line_count():
    text = "a ??/ \r\nb\r\nc ??= ??( ??) ??! ??< ??> ??- ??' \\\t\n\f\v"
    normal = configure.normalize_source(text)
    assert normal == "a \\\nb\nc # [ ] | { } ~ ^ \\\n\f\v"
    assert normal.count("\n") == 3


# 06-03 re-review R2-1: wcc386 ends a // comment at a lone CR but keeps one inside a literal as
# a character, so no single mapping of a lone CR reads as it does; a lone CR is refused.
LONE_CR_IN_LITERAL = (
    'INCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010);\nchar *s = "a\rb"; '
    'int func_00010000(void) { return 0; } char *t = "x";\n'
)
LONE_CR_BEFORE_ASM = 'char *s = "a\rb"; void f(void) { _asm int 3 } char *t = "x";\n'


def test_lone_cr_is_refused_on_raw_text():
    (problem,) = configure.check_unit_source(LONE_CR_IN_LITERAL, TWO_GAME)
    assert problem.startswith("line 3: ") and "carriage return" in problem
    marks = check.source_marks(LONE_CR_IN_LITERAL, TWO_GAME)
    assert marks.marked == marks.defined == frozenset()
    (problem,) = marks.problems
    assert problem.startswith("line 3: ") and "carriage return" in problem


@pytest.mark.parametrize(
    "text",
    [LONE_CR_BEFORE_ASM, "// c\rINCLUDE_ASM(func_00010000);\n"],
    ids=["literal-before-asm", "line-comment"],
)
def test_scanner_refuses_a_lone_cr(text):
    with pytest.raises(configure._ConditionalError, match="line 1: .*carriage return"):
        configure.code_text(text)
    with pytest.raises(configure._ConditionalError, match="carriage return"):
        configure.normalize_source(text)


def test_main_refuses_a_unit_file_with_a_lone_cr(tmp_path, capsys):
    """read_text would turn the lone CR into a line break, so configure checks the bytes."""
    argv = _split_tree(tmp_path)
    unit_file = tmp_path / "src" / "ufo2p" / f"{UNIT}.c"
    unit_file.write_bytes(UNIT_SOURCE.encode("utf-8") + b'char *s = "a\rb";\n')
    line = UNIT_SOURCE.count("\n") + 1
    _assert_refused(tmp_path, argv, capsys, f"{UNIT}.c", f"line {line}", "carriage return")


def test_directive_after_a_multiline_comment_keeps_its_line():
    """N2: a directive on the closing line of a multi-line block comment is reported at the
    line of its `#`, as before the comment was read as one space."""
    markers = "INCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010);\n"
    text = markers + "/* a\nb */ #ifdef FOO\n#endif\n"
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert problem.startswith("line 4: #ifdef")
    (problem,) = configure.check_unit_source("/* a\nb */ #if 0\n", TWO_GAME)
    assert problem.startswith("line 2: #if 0 has no matching #endif")


def test_line_comment_continuation_hides_a_marker():
    text, _, _ = CONTINUATION_PROBES["line-comment-marker"]
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "neither" in problem


def test_define_continuation_hides_a_definition():
    text, _, _ = CONTINUATION_PROBES["define-definition"]
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010000" in problem and "neither" in problem
    code = configure._live_code(configure._NOT_CODE.sub(configure._blank, text))
    assert list(configure._file_scope_definitions(code)) == []


@pytest.mark.parametrize(
    ("prefix", "lines"),
    [
        ("// a \\\ncontinued\n", 2),
        ("#define X \\\n    1 \\\n    + 2\n", 3),
        ('static char *s = "a\\\nb";\n', 2),
        ('#define S "a\\\nb" 1\n', 2),
        ("/* x *\\\n/\n", 2),
        ("#define X /* a\nb */ 1\n", 2),
    ],
    ids=["line-comment", "define", "string", "define-string", "closer-splice", "define-comment"],
)
def test_continuation_keeps_directive_line_numbers(prefix, lines):
    shift = UNIT_SOURCE.count("\n") + lines
    (problem,) = configure.check_unit_source(UNIT_SOURCE + prefix + "#ifdef FOO\n#endif\n",
                                             TWO_GAME)  # fmt: skip
    assert f"line {shift + 1}:" in problem and "#ifdef" in problem


def test_directive_continuation_is_one_directive():
    # `#if \` + `0` is `#if 0` after splicing, and an `#ifdef` inside a #define body is not a
    # directive; both read as the compiler reads them.
    text = "INCLUDE_ASM(func_00010000);\n#if \\\n0\nINCLUDE_ASM(func_00010010);\n#endif\n"
    (problem,) = configure.check_unit_source(text, TWO_GAME)
    assert "func_00010010" in problem and "neither" in problem
    text = UNIT_SOURCE + "#define Y \\\n#ifdef FOO\n"
    assert configure.check_unit_source(text, TWO_GAME) == []


@pytest.mark.parametrize("probe", sorted(CONTINUATION_PROBES))
def test_check_source_marks_agrees_with_configure(probe):
    text, marked, defined = CONTINUATION_PROBES[probe]
    marks = check.source_marks(text, TWO_GAME)
    assert (set(marks.marked), set(marks.defined)) == (marked, defined)
    problems = configure.check_unit_source(text, TWO_GAME)
    neither = {r.name for r in TWO_GAME if any(r.name in p and "neither" in p for p in problems)}
    assert neither == {row.name for row in TWO_GAME} - marked - defined


def test_main_refuses_a_conditional_naming_the_line(tmp_path, capsys):
    argv = _split_tree(tmp_path, source="#ifdef FOO\n#endif\n" + UNIT_SOURCE)
    _assert_refused(tmp_path, argv, capsys, f"{UNIT}.c", "line 1", "#ifdef")


@pytest.mark.parametrize(
    "definition",
    [
        "int func_00010000(void) {\n    return 0;\n}\n",
        "int\nfunc_00010000(int a, int (*cb)(int))\n{\n    return cb(a);\n}\n",
        "static unsigned char *func_00010000 ( char *p )\n\n{\n    return p;\n}\n",
    ],
    ids=["same-line", "nested-parens", "blank-line"],
)
def test_unit_source_definition_shapes(definition):
    text = "INCLUDE_ASM(func_00010010);\n" + definition
    assert configure.check_unit_source(text, TWO_GAME) == []


def test_unit_source_covers_thunk_rows_and_exempts_runtime_and_data():
    # Orchestrator ruling F5: game and thunk rows need C or a marker; runtime and data-in-code
    # rows are exempt.
    rows = _rows((0x10000, "game"), (0x10010, "thunk"), (0x10020, "runtime"),
                 (0x10030, "data-in-code"))  # fmt: skip
    text = "INCLUDE_ASM(func_00010000);\n"
    (problem,) = configure.check_unit_source(text, rows)
    assert "func_00010010" in problem
    assert configure.check_unit_source(text + "INCLUDE_ASM(func_00010010);\n", rows) == []


def test_marker_next_to_definition_is_fine():
    text = "INCLUDE_ASM(func_00010010);\nint func_00010000(void)\n{\n    return 0;\n}\n"
    assert configure.check_unit_source(text, TWO_GAME) == []
    text = "int func_00010000(void)\n{\n    return 0;\n}\nINCLUDE_ASM(func_00010010);\n"
    assert configure.check_unit_source(text, TWO_GAME) == []


FOUR_GAME = _rows((0x10000, "game"), (0x10010, "game"), (0x10020, "game"), (0x10030, "game"))
FOUR_PARTS = {
    "m0": "INCLUDE_ASM(func_00010000);\n",
    "d1": "int func_00010010(void)\n{\n    return 1;\n}\n",
    "m2": "INCLUDE_ASM(func_00010020);\n",
    "d3": "void func_00010030(void)\n{\n}\n",
}


@pytest.mark.parametrize(
    "order",
    [("m0", "m2", "d1", "d3"), ("d1", "d3", "m0", "m2"), ("m0", "d1", "m2", "d3"),
     ("d3", "m2", "d1", "m0")],  # fmt: skip
    ids=["markers-first", "markers-after", "interleaved", "reversed"],
)
def test_order_does_not_matter(order):
    text = "".join(FOUR_PARTS[part] for part in order)
    assert configure.check_unit_source(text, FOUR_GAME) == []
    without_last = "".join(FOUR_PARTS[part] for part in order[:-1])
    (problem,) = configure.check_unit_source(without_last, FOUR_GAME)
    assert "neither" in problem


# ---- 07-09 (D-29): the D-12 check reads symbols.csv C names through the shared finder --------

FOO_SYMBOLS = [SymbolRow(0x10010, "Foo_", "func")]  # symbols.csv renames func_00010010 Foo_
FOO_NAMES = unitdefs.c_names(TWO_GAME, FOO_SYMBOLS)
FOO_DEFINITION = "int Foo(int a)\n{\n    return a;\n}\n"


def test_d12_accepts_a_renamed_definition():
    text = "INCLUDE_ASM(func_00010000);\n" + FOO_DEFINITION
    assert configure.check_unit_source(text, TWO_GAME, names=FOO_NAMES) == []


def test_d12_refuses_a_missing_row():
    (problem,) = configure.check_unit_source("INCLUDE_ASM(func_00010000);\n", TWO_GAME,
                                             names=FOO_NAMES)  # fmt: skip
    assert problem == "Foo is neither defined in C nor marked INCLUDE_ASM (D-12)"


def test_d12_old_marker_still_counts():
    """A marker emits no bytes: a scaffold written before the rename still accounts for it."""
    text = "INCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010);\n"
    assert configure.check_unit_source(text, TWO_GAME, names=FOO_NAMES) == []


def test_d12_refuses_a_stale_placeholder_definition():
    text = "INCLUDE_ASM(func_00010000);\nint func_00010010(int a)\n{\n    return a;\n}\n"
    (problem,) = configure.check_unit_source(text, TWO_GAME, names=FOO_NAMES)
    assert "func_00010010" in problem and "Foo" in problem


def test_d12_refuses_another_units_renamed_function_with_all_names():
    text = UNIT_SOURCE + "void Baz(void)\n{\n}\n"
    assert configure.check_unit_source(text, TWO_GAME) == []  # a helper, without all_names
    (problem,) = configure.check_unit_source(text, TWO_GAME, all_names={"Baz": 0x20000})
    assert problem == "Baz is defined in C but is not a function of the unit"


def test_d12_default_names_unchanged():
    """Without names, the placeholder reading (every D-12 test above) holds."""
    for text in (UNIT_SOURCE, "INCLUDE_ASM(func_00010000);\n" + FOO_DEFINITION):
        assert (configure.check_unit_source(text, TWO_GAME, names=None)
                == configure.check_unit_source(text, TWO_GAME))  # fmt: skip
    (problem,) = configure.check_unit_source("INCLUDE_ASM(func_00010000);\n" + FOO_DEFINITION,
                                             TWO_GAME)  # fmt: skip
    assert problem == "func_00010010 is neither defined in C nor marked INCLUDE_ASM (D-12)"


def _rename_foo(tmp_path, stem: str = "ufo2p") -> None:
    write_symbols_csv(tmp_path / "config" / stem / "symbols.csv", FOO_SYMBOLS, "UFO2P.EXE")


def test_main_accepts_a_unit_defining_a_renamed_function(tmp_path):
    """configure reads config/<exe>/symbols.csv once per EXE and passes its C names to D-12."""
    argv = _split_tree(tmp_path, source="INCLUDE_ASM(func_00010000);\n" + FOO_DEFINITION)
    _rename_foo(tmp_path)
    assert configure.main(argv) == 0
    assert f"src/ufo2p/{UNIT}.c" in (tmp_path / "build.ninja").read_text(encoding="utf-8")


def test_main_refuses_a_stale_placeholder_definition(tmp_path, capsys):
    stale = "INCLUDE_ASM(func_00010000);\nint func_00010010(void)\n{\n    return 0;\n}\n"
    argv = _split_tree(tmp_path, source=stale)
    _rename_foo(tmp_path)
    _assert_refused(tmp_path, argv, capsys, f"{UNIT}.c", "func_00010010", "Foo")


def test_main_refuses_a_symbols_csv_func_name_without_its_underscore(tmp_path, capsys):
    argv = _split_tree(tmp_path)
    write_symbols_csv(tmp_path / "config" / "ufo2p" / "symbols.csv",
                      [SymbolRow(0x10010, "Foo", "func")], "UFO2P.EXE")  # fmt: skip
    _assert_refused(tmp_path, argv, capsys, "symbols.csv", "Foo")


def _assert_refused(tmp_path, argv, capsys, *needles):
    assert configure.main(argv) == 1
    err = capsys.readouterr().err
    assert err.startswith("configure.py: error:")
    for needle in needles:
        assert needle in err
    for name in GENERATED:
        assert not (tmp_path / name).exists(), name


def test_main_refuses_an_incomplete_unit(tmp_path, capsys):
    argv = _split_tree(tmp_path, source="int func_00010000(void)\n{\n    return 0;\n}\n")
    _assert_refused(tmp_path, argv, capsys, f"{UNIT}.c", "func_00010010")


def test_main_refuses_a_bad_unit_name(tmp_path, capsys):
    units = "unit,start,end,reason\nBad-Unit,0x00010000,0x00010020,first\n"
    _assert_refused(tmp_path, _split_tree(tmp_path, source=None, units=units), capsys, "Bad-Unit")


def test_main_refuses_a_stray_source(tmp_path, capsys):
    argv = _split_tree(tmp_path)
    (tmp_path / "src" / "ufo2p" / "stray.c").write_text("int x;\n", encoding="utf-8")
    _assert_refused(tmp_path, argv, capsys, "stray.c", "names no unit")


THREE_UNITS = (
    configure.UnitBuild("ufo2p", "UFO2P.EXE", "u_a", "src/ufo2p/u_a.c"),
    configure.UnitBuild("ufo2p", "UFO2P.EXE", "u_b", None),
    configure.UnitBuild("tacp", "TACP.EXE", "u_c", "src/tacp/u_c.c"),
)
BASES = ("$builddir/ufo2p/base/u_a.o", "$builddir/tacp/base/u_c.o")
TARGETS = (
    "$builddir/ufo2p/target/u_a.o",
    "$builddir/ufo2p/target/u_b.o",
    "$builddir/tacp/target/u_c.o",
)


def _deps(line: str) -> tuple[list[str], list[str]]:
    """The explicit and implicit inputs of a `build out: rule in... | implicit...` line."""
    inputs = line.partition(": ")[2].split(" ")[1:]
    if "|" not in inputs:
        return inputs, []
    bar = inputs.index("|")
    return inputs[:bar], inputs[bar + 1 :]


def test_land_joins_verify():
    text = configure.render([], orig="../elsewhere", units=THREE_UNITS)
    assert "build $builddir/always/verify: rebuild" in text
    lines = text.splitlines()
    assert "build verify: phony $builddir/always/verify $builddir/always/land" in lines
    explicit, implicit = _deps(_edge(text, "$builddir/always/land"))
    assert explicit == []
    assert sorted(implicit) == sorted(BASES)
    assert _command(text, "land") == "command = uv run reverseapoc land --orig ../elsewhere"
    assert REBUILD_CMD + "../elsewhere --out build" in _rule_block(text, "rebuild")


def test_land_without_units_still_joins_verify():
    lines = configure.render([]).splitlines()
    assert "build verify: phony $builddir/always/verify $builddir/always/land" in lines
    assert "build $builddir/always/land: land" in lines


def test_lint_and_asm_edges():
    text = configure.render([], units=THREE_UNITS)
    assert _command(text, "lint") == "command = uv run reverseapoc lint $in --stamp $out"
    stamps = ["$builddir/ufo2p/lint/u_a.stamp", "$builddir/tacp/lint/u_c.stamp"]
    assert _deps(_edge(text, stamps[0]))[0] == ["src/ufo2p/u_a.c"]
    assert _deps(_edge(text, stamps[1]))[0] == ["src/tacp/u_c.c"]
    assert "$builddir/ufo2p/lint/u_b.stamp" not in text
    assert f"build lint: phony {' '.join(stamps)}" in text.splitlines()

    assert _command(text, "asm") == "command = uv run reverseapoc asm $exe --orig orig"
    lines = text.splitlines()
    for exe in ("ufo2p", "tacp"):
        out = f"$builddir/always/asm/{exe}"
        index = lines.index(f"build {out}: asm")
        assert lines[index + 1] == f"  exe = {exe}"
    asm_phony = "build asm: phony $builddir/always/asm/ufo2p $builddir/always/asm/tacp"
    assert asm_phony in lines


def test_regeneration_rule(tmp_path):
    assert configure.main(_split_tree(tmp_path)) == 0
    text = (tmp_path / "build.ninja").read_text(encoding="utf-8")
    assert "generator = 1" in _rule_block(text, "configure")
    command = _command(text, "configure")
    assert "configure.py --orig orig --config config --src src --output $out" in command
    explicit, implicit = _deps(_edge(text, "build.ninja"))
    assert explicit == []
    assert implicit[0].endswith("configure.py")
    for dep in ("config/ufo2p/units.csv", "config/ufo2p/functions.csv", f"src/ufo2p/{UNIT}.c"):
        assert dep in implicit, dep


def test_regeneration_rule_refuses_an_unsafe_config_dir(tmp_path, capsys):
    argv = _split_tree(tmp_path)
    config = tmp_path / "my config"
    (tmp_path / "config").rename(config)
    argv[argv.index("--config") + 1] = str(config)
    _assert_refused(tmp_path, argv, capsys, "my config")


def test_default_builds_objects():
    text = configure.render([], units=THREE_UNITS)
    lines = text.splitlines()
    assert "default check-orig objects" in lines
    line = _edge(text, "objects")
    assert line.startswith("build objects: phony ")
    explicit, implicit = _deps(line)
    assert sorted(explicit) == sorted(BASES + TARGETS)
    assert implicit == []


def test_default_builds_objects_without_units():
    lines = configure.render([]).splitlines()
    assert "default check-orig objects" in lines
    assert "build objects: phony" in lines


def test_gitignore_lists_generated_files():
    lines = (configure.ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    start = lines.index("# --- generated by configure.py ---")
    block = []
    for line in lines[start + 1 :]:
        if not line.strip() or line.startswith("# ---"):
            break
        block.append(line.strip())
    for name in ("build.ninja", "objdiff.json", "compile_commands.json"):
        assert name in block, name


def test_main_creates_the_output_directory(tmp_path):
    out = tmp_path / "cfg-smoke" / "build.ninja"
    assert configure.main(["--orig", str(tmp_path / "orig"), "--output", str(out)]) == 0
    for name in ("build.ninja", "objdiff.json", "compile_commands.json"):
        assert (out.parent / name).is_file(), name


# ---- DI-06 part c: build.ninja rules carry the config tree they were generated from ----------

# Orchestrator ruling F4: the default render over the synthetic one-unit tree of _split_tree,
# pinned as a literal (never over the committed config/ or src/), taken before the change.
DEFAULT_RENDER_GOLDEN = """\
# build.ninja -- generated by configure.py; do not edit, re-run `python configure.py`.
#
#   ninja              the default: check-orig and objects
#   ninja check-orig   verify the orig dir against config/targets.toml (size, CRC32, MD5, SHA-1)
#   ninja parse-le     print the LE layout of every EXE found in the orig dir at configure time
#   ninja objects      every unit's base object (its C) and target object (cut from the LE image)
#   ninja lint         the C89 lint gate over every unit file (clang 18, in the container)
#   ninja asm          per-function listings into the gitignored asm/ directory
#   ninja verify       land matched functions, rebuild every target into build/ and check its
#                      SHA-1 (config/targets.toml)
#
# Compile rules: cc runs wcc386 (Watcom 10.x, user-supplied) under wibo with config/cflags.txt;
# omf2elf converts its OMF object to ELF32 for objdiff; target cuts the unit's bytes and
# relocations from the LE image; land splices every matched function back into the LE image.

ninja_required_version = 1.10
builddir = build

rule check_orig
  command = uv run reverseapoc check-orig --orig orig
  description = CHECK-ORIG orig
  pool = console

rule parse_le
  command = uv run reverseapoc parse-le $in
  description = PARSE-LE $in
  pool = console

rule rebuild
  command = uv run reverseapoc rebuild --orig orig --out build
  description = REBUILD build/
  pool = console

rule cc
  command = uv run reverseapoc cc $in -o $out
  description = CC $in

rule omf2elf
  command = uv run reverseapoc omf2elf $in -o $out
  description = OMF2ELF $out

rule target
  command = uv run reverseapoc target $exe $unit --orig orig -o $out
  description = TARGET $exe/$unit

rule lint
  command = uv run reverseapoc lint $in --stamp $out
  description = LINT $in

rule asm
  command = uv run reverseapoc asm $exe --orig orig
  description = ASM $exe
  pool = console

rule land
  command = uv run reverseapoc land --orig orig
  description = LAND build/
  pool = console

rule configure
  command = uv run python configure.py --orig orig --config config --src src --output $out
  description = CONFIGURE $out
  generator = 1
  pool = console

# Outputs under $builddir/always/ are never written, so these edges run every time they are
# requested; check-orig, verify and parse-le are phony aliases for them.

build $builddir/always/check-orig: check_orig
build check-orig: phony $builddir/always/check-orig
build $builddir/always/verify: rebuild
build $builddir/always/land: land | $builddir/ufo2p/base/u_00010000.o
build verify: phony $builddir/always/verify $builddir/always/land

build $builddir/always/parse-le/UFO2P.EXE: parse_le orig/UFO2P.EXE
build parse-le: phony $builddir/always/parse-le/UFO2P.EXE

build $builddir/ufo2p/target/u_00010000.o: target | orig/UFO2P.EXE config/ufo2p/functions.csv \
config/ufo2p/units.csv
  exe = ufo2p
  unit = u_00010000
build $builddir/ufo2p/obj/u_00010000.obj | $builddir/ufo2p/obj/u_00010000.obj.prov.json: cc \
src/ufo2p/u_00010000.c
build $builddir/ufo2p/base/u_00010000.o: omf2elf $builddir/ufo2p/obj/u_00010000.obj
build objects: phony $builddir/ufo2p/base/u_00010000.o $builddir/ufo2p/target/u_00010000.o

build $builddir/ufo2p/lint/u_00010000.stamp: lint src/ufo2p/u_00010000.c
build lint: phony $builddir/ufo2p/lint/u_00010000.stamp

build $builddir/always/asm/ufo2p: asm
  exe = ufo2p
build asm: phony $builddir/always/asm/ufo2p

build build.ninja: configure | configure.py config/ufo2p/functions.csv config/ufo2p/units.csv \
src/ufo2p/u_00010000.c

default check-orig objects
"""

# The commands of the rules that read config/: none of them names a config path by default.
CONFIG_RULES = ("check_orig", "rebuild", "target", "asm", "land")
CONFIG_FLAGS = ("--config", "--manifest", "--functions", "--symbols")


def test_default_config_render_is_unchanged(tmp_path):
    _split_tree(tmp_path)
    units = configure.collect_units(tmp_path / "config", tmp_path / "src", tmp_path)
    text = configure.render(["orig/UFO2P.EXE"], units=units, layout=configure.Layout())
    assert text == DEFAULT_RENDER_GOLDEN
    for rule in CONFIG_RULES:
        command = _command(text, rule)
        assert not [flag for flag in CONFIG_FLAGS if flag in command], command


def test_default_config_dir_adds_no_rule_flags(tmp_path):
    """--config naming the repository's config tree (the default) is the default text, wherever
    build.ninja is written."""
    out = tmp_path / "elsewhere" / "build.ninja"
    argv = ["--orig", str(tmp_path / "orig"), "--config", str(configure.ROOT / "config"),
            "--output", str(out)]  # fmt: skip
    assert configure.main(argv) == 0
    text = out.read_text(encoding="utf-8")
    for rule in CONFIG_RULES:
        command = _command(text, rule)
        assert not [flag for flag in CONFIG_FLAGS if flag in command], command


def test_custom_config_rules_name_its_manifest(tmp_path):
    argv = _split_tree(tmp_path)
    (tmp_path / "config").rename(tmp_path / "other")
    argv[argv.index("--config") + 1] = str(tmp_path / "other")
    assert configure.main(argv) == 0
    text = (tmp_path / "build.ninja").read_text(encoding="utf-8")
    manifest = "--manifest other/targets.toml"
    for rule in ("check_orig", "rebuild", "target", "land", "asm"):
        assert manifest in _command(text, rule), rule
    for rule in ("target", "land"):
        assert "--config other" in _command(text, rule), rule
    asm = _command(text, "asm")
    assert "--functions other/$exe/functions.csv" in asm
    assert "--symbols other/$exe/symbols.csv" in asm
    assert "configure.py --orig orig --config other --src src" in _command(text, "configure")
