"""configure.py writes the build.ninja skeleton."""

from __future__ import annotations

import configure


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
    assert "command = uv run reverseapoc rebuild" in block
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
