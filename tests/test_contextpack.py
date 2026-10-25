"""The per-function context pack (AGT-08, D-13, D-14). Synthetic inputs only: every listing,
draft and LE byte below is made up, and every pack is written under pytest's tmp_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from reverseapoc.contextpack import (
    PACK_CAP,
    ContextPackError,
    Lookalike,
    Neighbour,
    build_pack,
    write_pack,
)

ORDER = (
    "Target listing",
    "Unit file",
    "Callers",
    "Callees",
    "D_ externs",
    "include/common.h",
    "Ghidra draft",
    "Matching idioms",
    "Earlier notes",
    "Look-alikes",
)


def _inputs(**overrides):
    inputs = {
        "function": "func_00010010",
        "listing": "# func_00010010  0x00010010..0x00010020  16 bytes, game\n  0x00010010  ret\n",
        "unit_text": '#include "common.h"\n\nINCLUDE_ASM(func_00010010);\n',
        "callers": (Neighbour("func_00010000", "game", "matched", "void func_00010000(void)"),),
        "callees": (Neighbour("func_00010020", "game", "unmatched", None),),
        "externs": ("D_00020100",),
        "common_h": "#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name\n",
        "draft": "void func_00010010(void)\n{\n}\n",
        "idioms": "## Known idioms\n\nMade-up idiom text.\n",
        "notes": "attempt 1: PARTIAL 80%, the made-up loop order differs\n",
        "lookalikes": (Lookalike("func_00010030", 0x10030, 0.75, "void func_00010030(void)\n{\n}"),),
    }
    inputs.update(overrides)
    return inputs


def _headings(text: str) -> list[str]:
    return [line[3:] for line in text.splitlines() if line.startswith("## ")]


def test_pack_has_every_section_in_order():
    pack = build_pack(**_inputs())
    assert tuple(section.title for section in pack.sections) == ORDER
    assert _headings(pack.text) == list(ORDER)
    body = {section.title: section.body for section in pack.sections}
    assert "```asm\n# func_00010010" in body["Target listing"]
    assert "```c\n#include" in body["Unit file"]
    assert "func_00010000 (game, matched): void func_00010000(void);" in body["Callers"]
    assert "func_00010020 (game, unmatched)" in body["Callees"]
    assert "D_00020100" in body["D_ externs"]
    assert "```c\nvoid func_00010010(void)" in body["Ghidra draft"]
    assert "func_00010030" in body["Look-alikes"] and "0.750" in body["Look-alikes"]
    assert pack.pack_bytes == len(pack.text.encode("utf-8"))
    assert pack.truncated == ()
    assert pack.to_json()["pack_bytes"] == pack.pack_bytes


def test_write_pack_stays_under_build_driver(tmp_path: Path):
    pack = build_pack(**_inputs())
    out = tmp_path / "build" / "driver" / "r" / "ufo2p" / "func_00010010"
    written = write_pack(pack, out)
    assert written == out / "context.md"
    assert written.read_bytes() == pack.text.encode("utf-8")
    with pytest.raises(ContextPackError, match="build/driver"):
        write_pack(pack, tmp_path / "src")
    assert not (tmp_path / "src").exists()


def test_empty_inputs_say_none():
    pack = build_pack(**_inputs(callers=(), callees=(), externs=(), draft=None, notes=None,
                                lookalikes=()))  # fmt: skip
    body = {section.title: section.body for section in pack.sections}
    for title in ("Callers", "Callees", "D_ externs", "Ghidra draft", "Earlier notes",
                  "Look-alikes"):  # fmt: skip
        assert body[title] == "none", title
    assert pack.truncated == ()


def test_pack_cap_is_24_kib():
    assert PACK_CAP == 24576
