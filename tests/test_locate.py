"""The entry locators (DEC-01, D-01, D-03; spike 007 q1, q3, q4): synthetic LE images only, every
byte and address made up.

The images use the conftest objects: code at 0x10000 (two pages), data at 0x20000 (one short
page). Each test patches made-up instructions and strings over the page fill. The real-file pins
live at the end of this file and skip without orig/.
"""

from __future__ import annotations

import json
import struct
from types import SimpleNamespace

import pytest

from conftest import build_le_image, fixup_record
from reverseapoc import cli, locate
from reverseapoc.functions import KIND_GAME, KIND_RUNTIME, FunctionRow
from reverseapoc.le import LE, SRC_OFF32
from reverseapoc.locate import StringRef

CODE = 0x10000  # object 1
DATA = 0x20000  # object 2
_CALL = b"\xe8"  # call rel32
_PUSH_IMM32 = b"\x68"  # push imm32
_MOV_EAX_IMM = b"\xb8"  # mov eax, imm32
_RET = b"\xc3"
_NOP = b"\x90"
_INSN_REL32 = 5  # opcode + rel32
_IMM_FIELD = 1  # the imm32 of push/mov sits one byte into the instruction
_ZERO32 = b"\x00" * 4
_NUL = b"\x00"

KEYWORD = "x.dat"
FILE_NAME = b"scenario/" + KEYWORD.encode()  # a made-up file name
OTHER_NAME = b"other.txt"  # a made-up string nothing references
STRING = DATA + 0x41  # FILE_NAME starts here, after a NUL at DATA + 0x40
OTHER = DATA + 0x60  # OTHER_NAME starts here, after a NUL at DATA + 0x5F
TABLE_LO, TABLE_HI = DATA + 0x100, DATA + 0x110


def _rel(opcode: bytes, at: int, to: int) -> bytes:
    return opcode + struct.pack("<i", to - (at + _INSN_REL32))


def _row(start: int, end: int, kind: str = KIND_GAME, name: str = "") -> FunctionRow:
    return FunctionRow(start, end, name or f"func_{start:08X}", kind, f"u_{start:08x}", "call")


def _padded(code: bytes, size: int) -> bytes:
    return code + _NOP * (size - len(code))


def _to_data(field: int, target: int) -> bytes:
    """One off32 fixup record on the first code page, field -> a data address."""
    return fixup_record(SRC_OFF32, field - CODE, 2, target - DATA)


def _exe(rows, patches: dict[int, bytes], code_fixups: bytes, data_fixups: bytes = b"",
         stem: str = "ufo2p", units=()):  # fmt: skip
    """An ExeInputs stand-in: the fields the locators read."""
    image = build_le_image(fixups=[code_fixups, b"", data_fixups], patches=patches)
    le = LE(image.data)
    flat = bytes(le.load_flat(relocate=False))
    return SimpleNamespace(stem=stem, le=le, flat=flat, fixups=tuple(le.fixups()),
                           rows=tuple(rows), units=tuple(units))  # fmt: skip


# ---- task 1 image: a file-name string, a table range, int386_ callers ----

A = CODE  # push offset STRING; push offset TABLE_LO; ret
B = CODE + 0x20  # push offset TABLE_HI - 4; ret
C = CODE + 0x40  # push offset TABLE_HI (just past the range); ret
I1 = CODE + 0x60  # mov eax, 0x1a; call INT386; ret
I2 = CODE + 0x80  # mov eax, 0x21; call INT386; ret
I3 = CODE + 0xA0  # mov eax, 0x1a; call C; call INT386; ret  (eax lost at the first call)
INT386 = CODE + 0xC0  # runtime int386_: ret
END = CODE + 0xE0
VECTOR_BIOS_TICK = 0x1A
VECTOR_DOS = 0x21
ROWS = [
    _row(A, B), _row(B, C), _row(C, I1), _row(I1, I2), _row(I2, I3), _row(I3, INT386),
    _row(INT386, END, KIND_RUNTIME, "int386_"),
]  # fmt: skip


def _int_call(at: int, vector: int) -> bytes:
    return _padded(_MOV_EAX_IMM + struct.pack("<I", vector) + _rel(_CALL, at + 5, INT386) + _RET,
                   0x20)  # fmt: skip


PATCHES = {
    A: _padded(_PUSH_IMM32 + _ZERO32 + _PUSH_IMM32 + _ZERO32 + _RET, 0x20),
    B: _padded(_PUSH_IMM32 + _ZERO32 + _RET, 0x20),
    C: _padded(_PUSH_IMM32 + _ZERO32 + _RET, 0x20),
    I1: _int_call(I1, VECTOR_BIOS_TICK),
    I2: _int_call(I2, VECTOR_DOS),
    I3: _padded(_MOV_EAX_IMM + struct.pack("<I", VECTOR_BIOS_TICK) + _rel(_CALL, I3 + 5, C)
                + _rel(_CALL, I3 + 10, INT386) + _RET, 0x20),
    INT386: _padded(_RET, 0x20),
    STRING - 1: _NUL + FILE_NAME + _NUL,
    OTHER - 1: _NUL + OTHER_NAME + _NUL,
}  # fmt: skip
FIXUPS = (
    _to_data(A + _IMM_FIELD, STRING)
    + _to_data(A + 5 + _IMM_FIELD, TABLE_LO)
    + _to_data(B + _IMM_FIELD, TABLE_HI - 4)
    + _to_data(C + _IMM_FIELD, TABLE_HI)
)  # fmt: skip


def _task1():
    return _exe(ROWS, PATCHES, FIXUPS)


def test_string_refs():
    assert locate.string_refs(_task1(), KEYWORD) == [StringRef(STRING, KEYWORD, (A,))]


def test_string_refs_lists_an_unreferenced_string_with_no_rows():
    assert locate.string_refs(_task1(), "other") == [StringRef(OTHER, "other", ())]


def test_string_refs_ignores_case():
    assert [ref.address for ref in locate.string_refs(_task1(), "X.DAT")] == [STRING]


def test_table_refs():
    assert locate.table_refs(_task1(), TABLE_LO, TABLE_HI) == (A, B)  # C's fixup is at hi


def test_table_refs_refuses_an_empty_range():
    with pytest.raises(locate.LocateError):
        locate.table_refs(_task1(), TABLE_HI, TABLE_LO)


def test_interrupt_callers():
    callers = locate.interrupt_callers(_task1(), VECTOR_BIOS_TICK)
    assert [site.caller for site in callers] == [I1]  # not I2 (0x21), not I3 (eax lost)
    assert callers[0].call_va == I1 + 5
    assert [site.caller for site in locate.interrupt_callers(_task1(), VECTOR_DOS)] == [I2]


def test_planted_interrupt_caller_fails():
    with pytest.raises(AssertionError):
        assert [s.caller for s in locate.interrupt_callers(_task1(), VECTOR_BIOS_TICK)] == [I3]


def test_no_int386_row_gives_no_callers():
    rows = [r for r in ROWS if r.start != INT386]
    assert locate.interrupt_callers(_exe(rows, PATCHES, FIXUPS), VECTOR_BIOS_TICK) == []


def test_no_match_is_empty(monkeypatch, capsys):
    exe = _task1()
    assert locate.string_refs(exe, "no-such-keyword") == []
    assert locate.table_refs(exe, DATA + 0x800, DATA + 0x900) == ()
    monkeypatch.setattr(locate, "load_inputs", lambda *a, **k: exe)
    for selector in (["--string", "no-such-keyword"], ["--range", "0x20800", "0x20900"],
                     ["--int", "0x10"], ["--va", "0x20800"]):  # fmt: skip
        assert cli.main(["mechanics", "locate", "--exe", "ufo2p", *selector]) == 0
        assert "0 rows" in capsys.readouterr().out


def _locate_json(monkeypatch, capsys, *selector: str) -> dict:
    monkeypatch.setattr(locate, "load_inputs", lambda *a, **k: _task1())
    assert cli.main(["mechanics", "locate", "--exe", "ufo2p", *selector, "--json"]) == 0
    out = capsys.readouterr().out
    assert "scenario" not in out and OTHER_NAME.decode() not in out  # never string contents
    return json.loads(out)


def test_cli_locate_string_json(monkeypatch, capsys):
    report = _locate_json(monkeypatch, capsys, "--string", KEYWORD)
    assert report["string"] == KEYWORD
    assert report["strings"] == [{"address": f"0x{STRING:08X}", "rows": [f"0x{A:08X}"]}]
    assert report["rows"] == [f"0x{A:08X}"]


def test_cli_locate_range_va_and_int_json(monkeypatch, capsys):
    rng = _locate_json(monkeypatch, capsys, "--range", hex(TABLE_LO), hex(TABLE_HI))
    assert rng["rows"] == [f"0x{A:08X}", f"0x{B:08X}"]
    va = _locate_json(monkeypatch, capsys, "--va", hex(TABLE_HI))
    assert va["rows"] == [f"0x{C:08X}"]
    found = _locate_json(monkeypatch, capsys, "--int", "0x1a")
    assert found["rows"] == [f"0x{I1:08X}"]
    assert found["sites"] == [{"caller": f"0x{I1:08X}", "call": f"0x{I1 + 5:08X}"}]


def test_cli_locate_text_prints_addresses_and_counts(monkeypatch, capsys):
    monkeypatch.setattr(locate, "load_inputs", lambda *a, **k: _task1())
    assert cli.main(["mechanics", "locate", "--exe", "ufo2p", "--string", KEYWORD]) == 0
    out = capsys.readouterr().out
    assert f"0x{STRING:08X}" in out and f"0x{A:08X}" in out and "1 rows" in out
    assert "scenario" not in out


def test_cli_locate_refuses_an_unknown_exe(monkeypatch, capsys):
    monkeypatch.setattr(locate, "load_inputs", lambda *a, **k: pytest.fail("not loaded"))
    assert cli.main(["mechanics", "locate", "--exe", "smkp", "--string", KEYWORD]) == 2
    assert "smkp" in capsys.readouterr().err


def test_cli_locate_selectors_are_exclusive(capsys):
    with pytest.raises(SystemExit):
        cli.main(["mechanics", "locate", "--exe", "ufo2p", "--string", "a", "--int", "0x1a"])
    with pytest.raises(SystemExit):
        cli.main(["mechanics", "locate", "--exe", "ufo2p"])
