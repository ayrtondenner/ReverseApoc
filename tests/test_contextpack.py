"""The per-function context pack (AGT-08, D-13, D-14). Synthetic inputs only: every listing,
draft and LE byte below is made up, and every pack is written under pytest's tmp_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import REPO_ROOT, build_le_image, fixup_record
from reverseapoc import contextpack
from reverseapoc.contextpack import (
    PACK_CAP,
    ContextPackError,
    Lookalike,
    Neighbour,
    build_pack,
    write_pack,
)
from reverseapoc.functions import FunctionRow, SymbolRow
from reverseapoc.le import LE
from reverseapoc.symbols import SymbolTable

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
        "lookalikes": (
            Lookalike("func_00010030", 0x10030, 0.75, "void func_00010030(void)\n{\n}"),
        ),
    }
    inputs.update(overrides)
    return inputs


def _headings(text: str) -> list[str]:
    """The `## ` headings outside fenced blocks (fenced inputs may hold headings of their own)."""
    headings, fence = [], None
    for line in text.splitlines():
        run = len(line) - len(line.lstrip("`"))
        if run >= 3 and (fence is None or (run >= fence and not line[run:].strip())):
            fence = run if fence is None else None
            continue
        if fence is None and line.startswith("## "):
            headings.append(line[3:])
    return headings


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


# ---- the neighbourhood from a synthetic LE (Task 2) ----

CODE = 0x10000
FUNC_A = CODE  # calls B; also loads the address of C (a code pointer, not a call or extern)
FUNC_B = CODE + 0x10  # reads and writes two data words, then calls C
FUNC_C = CODE + 0x20
END = CODE + 0x30
A_BYTES = (
    b"\xe8\x0b\x00\x00\x00"  # call FUNC_B (rel32 0xB from FUNC_A + 5)
    + b"\xb8\x20\x00\x00\x00"  # mov eax, 0x20 (off32 field, LE fixup -> FUNC_C)
    + b"\xc3"  # ret
    + b"\x90" * 5
)
B_BYTES = (
    b"\xa1\x00\x02\x00\x00"  # mov eax, [0x200] (off32 field -> data + 0x200)
    + b"\xa3\x00\x01\x00\x00"  # mov [0x100], eax (off32 field -> data + 0x100)
    + b"\xe8\x01\x00\x00\x00"  # call FUNC_C (rel32 1 from FUNC_B + 15)
    + b"\xc3"  # ret
)
C_BYTES = b"\xc3" + b"\x90" * 15
UNIT_AB = "u_00010000"
UNIT_C = "u_00010020"
UNIT_AB_TEXT = (
    '#include "common.h"\n'
    "\n"
    "extern int D_00020100;\n"
    "\n"
    "/* made-up comment\n"
    "   with a { and a ; */ int func_00010000(void)\n"
    "{\n"
    "    return func_00010010();\n"
    "}\n"
    "\n"
    "int func_00010010(void)\n"
    "{\n"
    "    return D_00020100;\n"
    "}\n"
)


def _le_inputs():
    records = (
        fixup_record(7, 0x06, 1, 0x20)
        + fixup_record(7, 0x11, 2, 0x200)
        + fixup_record(7, 0x16, 2, 0x100)
    )
    data = build_le_image(
        fixups=[records, b"", b""], patches={FUNC_A: A_BYTES, FUNC_B: B_BYTES, FUNC_C: C_BYTES}
    ).data
    le = LE(data)
    rows = [
        FunctionRow(FUNC_A, FUNC_B, "func_00010000", "game", UNIT_AB, "call"),
        FunctionRow(FUNC_B, FUNC_C, "func_00010010", "game", UNIT_AB, "call"),
        FunctionRow(FUNC_C, END, "func_00010020", "game", UNIT_C, "call"),
    ]
    data_ranges = [(obj.base, obj.end) for obj in le.objects if not obj.flags & 0x4]
    symbols = SymbolTable.build(
        rows, [SymbolRow(0x20200, "_g_counter", "data")], data_ranges=data_ranges
    )
    return rows, le.load_flat(relocate=False), le.fixups(), symbols


def _gather(row, tmp_path: Path, status, **overrides):
    rows, flat, fixups, symbols = _le_inputs()
    kwargs = {
        "rows": rows,
        "flat": flat,
        "fixups": fixups,
        "symbols": symbols,
        "status": status,
        "unit_texts": {UNIT_AB: UNIT_AB_TEXT},
        "listing_dir": tmp_path / "asm",
        "draft_dir": tmp_path / "asm" / "ghidra",
        "common_h": "/* made-up common.h */\n",
        "idioms": "made-up idioms\n",
        "notes": None,
    }
    kwargs.update(overrides)
    return contextpack.gather(rows[row], **kwargs)


def test_callers_and_callees_from_the_le(tmp_path: Path):
    rows, flat, fixups, _ = _le_inputs()
    index = contextpack.CallIndex.build(rows, flat, fixups)
    assert index.callees_of(FUNC_A) == (FUNC_B,)
    assert index.callees_of(FUNC_B) == (FUNC_C,)
    assert index.callers_of(FUNC_B) == (FUNC_A,)
    assert index.callers_of(FUNC_C) == (FUNC_B,)  # the code pointer in A is not a call
    (tmp_path / "asm").mkdir()
    (tmp_path / "asm" / "func_00010010.s").write_text("# made-up listing\n", encoding="utf-8")
    inputs = _gather(1, tmp_path, {FUNC_A: "matched", FUNC_C: "partial"})
    assert inputs["callers"] == (
        contextpack.Neighbour("func_00010000", "game", "matched", "int func_00010000(void)"),
    )
    assert inputs["callees"] == (contextpack.Neighbour("func_00010020", "game", "partial", None),)
    assert inputs["listing"] == "# made-up listing\n"
    assert inputs["draft"] is None  # no draft file: the section says none
    assert inputs["unit_text"] == UNIT_AB_TEXT
    build_pack(**inputs)  # gather's dict is exactly build_pack's keywords


def test_matched_callee_carries_its_prototype(tmp_path: Path):
    inputs = _gather(0, tmp_path, {FUNC_B: "matched"})
    assert inputs["callees"] == (
        contextpack.Neighbour("func_00010010", "game", "matched", "int func_00010010(void)"),
    )
    unmatched = _gather(1, tmp_path, {})
    assert unmatched["callees"] == (
        contextpack.Neighbour("func_00010020", "game", "unmatched", None),
    )


def test_externs_are_the_d_symbols_the_row_touches(tmp_path: Path):
    assert _gather(1, tmp_path, {})["externs"] == ("D_00020100", "_g_counter")
    assert _gather(0, tmp_path, {})["externs"] == ()  # its only off32 targets code
    assert _gather(2, tmp_path, {})["externs"] == ()


# ---- definition heads sliced from the original text (orchestrator ruling R2-3) ----

TRICKY_UNIT = (
    '#include "common.h"\r\n'
    "#if 0\r\n"
    "int func_00010000(int a) { return a; }\r\n"
    "#endif\r\n"
    'static const char trigraphs[] = "??=??( {";\r\n'
    "/* a comment with a { brace\r\n"
    "   and a ; */ int func_00010000(void)\r\n"
    "{\r\n"
    "    return 1; /* } */\r\n"
    "}\r\n"
    "#define LIMIT 3\r\n"
    "unsigned\r\n"
    "func_00010010(void)\r\n"
    "{\r\n"
    "    return LIMIT;\r\n"
    "}\r\n"
)


def test_callee_prototype_offsets_survive_comments_trigraphs_and_crlf():
    found = contextpack.definitions(TRICKY_UNIT)
    assert set(found) == {"func_00010000", "func_00010010"}
    first = found["func_00010000"]
    assert first.head == "int func_00010000(void)"  # the #if 0 copy is dead code
    assert first.source == "int func_00010000(void)\r\n{\r\n    return 1; /* } */\r\n}"
    assert found["func_00010010"].head == "unsigned\r\nfunc_00010010(void)"  # not the #define


def test_callee_prototype_on_the_real_tacp_unit():
    """src/tacp/u_00054f20.c is the file R2-3 names: its comment block before the definition
    holds braces and backticks, and code_text's offsets do not map onto it."""
    text = (REPO_ROOT / "src" / "tacp" / "u_00054f20.c").read_text(encoding="utf-8")
    found = contextpack.definitions(text)
    assert set(found) == {"func_00055080"}
    assert found["func_00055080"].head == "void func_00055080(void)"
    assert found["func_00055080"].source == (
        "void func_00055080(void)\n{\n    D_0028DF70 = func_00011500();\n}"
    )


def test_callee_prototype_unreadable_unit_gives_none():
    # a lone CR and an #if the D-12 parser cannot evaluate: no head is guessed
    assert contextpack.definitions("int func_00010000(void) {}\r\n#if FOO\n#endif\n") == {}
    assert contextpack.definitions("int func_00010000(void) {}\rint x;\n") == {}


# ---- look-alikes and the 24 KB cap (Task 3) ----

TARGET = tuple("abcdefghij")  # made-up mnemonics; SequenceMatcher ratio = 2 * matches / 20


def test_lookalikes_rank_by_mnemonic_similarity():
    matched = {
        0x300: (*TARGET[:9], "z"),  # 0.9
        0x100: (*TARGET[:7], "x", "y", "z"),  # 0.7
        0x200: (*TARGET[:5], "v", "w", "x", "y", "z"),  # 0.5, under the 0.6 floor
    }
    assert contextpack.lookalikes(TARGET, matched) == [(0x300, 0.9), (0x100, 0.7)]
    tied = {0x400: (*TARGET[:9], "z"), **matched, 0x050: (*TARGET[:9], "y")}
    assert contextpack.lookalikes(TARGET, tied) == [(0x050, 0.9), (0x300, 0.9), (0x400, 0.9)]
    assert contextpack.lookalikes(TARGET, tied, top=1) == [(0x050, 0.9)]


def test_lookalikes_come_from_matched_rows_with_c(tmp_path: Path):
    rows, flat, fixups, _ = _le_inputs()
    assert contextpack.mnemonics(rows[1], flat, fixups) == ("mov", "mov", "call", "ret")
    # C (ret + 15 nops) against A (call, mov, ret, 5 nops): 6 of 24 mnemonics pair up, 0.5
    inputs = _gather(2, tmp_path, {FUNC_A: "matched"}, lookalike_floor=0.5)
    (only,) = inputs["lookalikes"]
    assert (only.name, only.start, only.ratio) == ("func_00010000", FUNC_A, 0.5)
    assert only.source.startswith("int func_00010000(void)\n{")
    assert _gather(2, tmp_path, {FUNC_A: "matched"})["lookalikes"] == ()  # floor 0.6


def _big_inputs(pad: int = 1, **overrides):
    """Inputs with three 2000-byte look-alikes, three long caller lines and a 3000-byte draft;
    `pad` (at least 1, so the fenced section grows byte for byte) ASCII bytes go into the
    required idioms section."""
    lookalikes = tuple(
        Lookalike(f"func_0001{n}000", 0x10000 + n * 0x1000, 0.9 - n / 10, "/*" + "x" * 2000 + "*/")
        for n in range(1, 4)
    )
    callers = tuple(Neighbour(f"func_0002{n}000", "game", "matched", "int " + "y" * 200)
                    for n in range(1, 4))  # fmt: skip
    inputs = {
        "lookalikes": lookalikes,
        "callers": callers,
        "draft": "z" * 3000,
        "idioms": "i" * pad,
    }
    inputs.update(overrides)
    return _inputs(**inputs)


def _size(**inputs) -> int:
    return build_pack(**inputs, cap=10**9).pack_bytes


def test_pack_at_the_cap_is_kept_whole():
    pad = PACK_CAP - _size(**_big_inputs()) + 1  # the base has pad 1
    pack = build_pack(**_big_inputs(pad))
    assert pack.pack_bytes == PACK_CAP
    assert pack.truncated == ()
    assert len(pack.text.encode("utf-8")) == PACK_CAP


def test_pack_one_byte_over_is_truncated_in_order():
    looks = ("look-alike func_00013000", "look-alike func_00012000", "look-alike func_00011000")
    callers = ("caller func_00023000", "caller func_00022000", "caller func_00021000")
    stages = [
        (_size(**_big_inputs()), looks[:1]),
        (_size(**_big_inputs(lookalikes=())), (*looks, callers[0])),
        (_size(**_big_inputs(lookalikes=(), callers=())), (*looks, *callers, "draft")),
    ]
    for full, expected in stages:
        pad = PACK_CAP - full + 2  # one byte over: the base has pad 1
        pack = build_pack(**_big_inputs(pad))
        assert pack.truncated == expected
        assert pack.pack_bytes <= PACK_CAP
        assert f"Truncated: {', '.join(expected)}" in pack.text
        whole = build_pack(**_big_inputs(pad), cap=10**9)
        required = ("Target listing", "Unit file", "Callees", "D_ externs", "include/common.h",
                    "Matching idioms", "Earlier notes")  # fmt: skip
        kept = {s.title: s.body for s in pack.sections}
        assert all(kept[s.title] == s.body for s in whole.sections if s.title in required)
        assert pack.to_json()["truncated"] == list(expected)


def test_required_sections_alone_over_the_cap():
    with pytest.raises(ContextPackError, match=r"\d+ bytes"):
        build_pack(**_big_inputs(unit_text="u" * PACK_CAP))


def test_pack_is_deterministic():
    assert build_pack(**_big_inputs(5000)).text == build_pack(**_big_inputs(5000)).text
    forward = {0x100: (*TARGET[:8], "y", "z"), 0x200: (*TARGET[:8], "z", "y")}
    backward = dict(reversed(forward.items()))
    assert contextpack.lookalikes(TARGET, forward) == contextpack.lookalikes(TARGET, backward)
