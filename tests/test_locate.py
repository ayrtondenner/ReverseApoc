"""The entry locators (DEC-01, D-01, D-03; spike 007 q1, q3, q4): synthetic LE images only, every
byte and address made up.

The images use the conftest objects: code at 0x10000 (two pages), data at 0x20000 (one short
page). Each test patches made-up instructions and strings over the page fill. The real-file pins
live at the end of this file and skip without orig/.
"""

from __future__ import annotations

import json
import struct
from functools import cache
from types import SimpleNamespace

import pytest

from conftest import ORIG_DIR, REPO_ROOT, build_le_image, fixup_record, requires_capstone
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


# ---- task 2 parts of the same image: a get_text function, its callers, a sectioned blob ----

GT = CODE + 0x100  # get_text(section in eax, index in edx): ret
R1 = CODE + 0x120  # mov edx, 4; mov eax, 2; call GT; ret
R2 = CODE + 0x140  # xor eax, eax; mov edx, 1; call GT; ret
R3 = CODE + 0x160  # mov eax, 1; lea edx, [ebx + 3]; call GT; ret  (index computed)
R4 = CODE + 0x180  # mov eax, 3; mov edx, 2; jmp GT  (a tail call)
END2 = CODE + 0x1A0
_MOV_EDX_IMM = b"\xba"  # mov edx, imm32
_XOR_EAX_EAX = b"\x31\xc0"
_LEA_EDX_EBX_3 = b"\x8d\x53\x03"  # lea edx, [ebx + 3]
_JMP = b"\xe9"  # jmp rel32
# The blob: NUL, then section 0 "a" "bb", section 1 "ccc", section 3 "d" "e" "f" (made up),
# ending right below the table. Slot 2 is null; the word after slot 3 is page fill.
BLOB = DATA + 0x80
S0, S1, S3 = DATA + 0x81, DATA + 0x86, DATA + 0x8A
TEXT_TABLE = DATA + 0x90
TEXT_SLOTS = 4
BLOB_BYTES = b"\x00a\x00bb\x00ccc\x00d\x00e\x00f\x00"
SYNTHETIC_GET_TEXT = (GT, TEXT_TABLE, TEXT_SLOTS)
ROWS2 = [_row(GT, R1), _row(R1, R2), _row(R2, R3), _row(R3, R4), _row(R4, END2)]


def _imm(opcode: bytes, value: int) -> bytes:
    return opcode + struct.pack("<I", value)


PATCHES2 = {
    GT: _padded(_RET, 0x20),
    R1: _padded(_imm(_MOV_EDX_IMM, 4) + _imm(_MOV_EAX_IMM, 2) + _rel(_CALL, R1 + 10, GT) + _RET,
                0x20),
    R2: _padded(_XOR_EAX_EAX + _imm(_MOV_EDX_IMM, 1) + _rel(_CALL, R2 + 7, GT) + _RET, 0x20),
    R3: _padded(_imm(_MOV_EAX_IMM, 1) + _LEA_EDX_EBX_3 + _rel(_CALL, R3 + 8, GT) + _RET, 0x20),
    R4: _padded(_imm(_MOV_EAX_IMM, 3) + _imm(_MOV_EDX_IMM, 2) + _rel(_JMP, R4 + 10, GT), 0x20),
    BLOB: BLOB_BYTES,
    TEXT_TABLE: _ZERO32 * TEXT_SLOTS,
}  # fmt: skip
R1_CALL, R2_CALL, R3_CALL, R4_JMP = R1 + 10, R2 + 7, R3 + 8, R4 + 10


def _slot(k: int, target: int) -> bytes:
    """One off32 fixup record on the data page: get_text slot k -> a string start."""
    return fixup_record(SRC_OFF32, TEXT_TABLE + 4 * k - DATA, 2, target - DATA)


DATA_FIXUPS = _slot(0, S0) + _slot(1, S1) + _slot(3, S3)


def _task1(data_fixups: bytes = DATA_FIXUPS):
    return _exe(ROWS + ROWS2, PATCHES | PATCHES2, FIXUPS, data_fixups)


@pytest.fixture
def text_table(monkeypatch):
    """The synthetic get_text function and section table stand in for UFO2P's."""
    monkeypatch.setitem(locate.GET_TEXT, "ufo2p", SYNTHETIC_GET_TEXT)


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


def test_no_match_is_empty(monkeypatch, capsys, text_table):
    exe = _task1()
    assert locate.string_refs(exe, "no-such-keyword") == []
    assert locate.table_refs(exe, DATA + 0x800, DATA + 0x900) == ()
    monkeypatch.setattr(locate, "load_inputs", lambda *a, **k: exe)
    for selector in (["--string", "no-such-keyword"], ["--range", "0x20800", "0x20900"],
                     ["--int", "0x10"], ["--va", "0x20800"], ["--get-text", "9", "9"]):  # fmt: skip
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


def test_cli_locate_range_va_and_int_json(monkeypatch, capsys, text_table):
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


# ---- task 2: the get_text route ----


def test_get_text_table_holds_both_exes():
    assert set(locate.GET_TEXT) == {"ufo2p", "tacp"}
    assert locate.GET_TEXT["ufo2p"][:2] == (0x00063800, 0x000F3794)
    assert locate.GET_TEXT["tacp"][:2] == (0x0005B360, 0x00292D18)


def test_get_text_sections(text_table):
    sections = locate.get_text_sections(_task1())
    assert [(s.section, s.start, s.end) for s in sections] == [
        (0, S0, S1), (1, S1, S3), (3, S3, TEXT_TABLE)]  # fmt: skip
    assert [s.strings for s in sections] == [
        (S0, S0 + 2), (S1,), (S3, S3 + 2, S3 + 4)]  # fmt: skip


def test_get_text_index(text_table):
    sections = locate.get_text_sections(_task1())
    assert locate.get_text_index(sections, S0 + 2) == (0, 1)
    assert locate.get_text_index(sections, S0 + 3) == (0, 1)  # inside "bb"
    assert locate.get_text_index(sections, S1) == (1, 0)
    assert locate.get_text_index(sections, S3 + 4) == (3, 2)
    assert locate.get_text_index(sections, STRING) is None  # a data string outside the blob
    assert locate.get_text_index(sections, TEXT_TABLE) is None


def test_get_text_sites_constant(text_table):
    sites = {site.call_va: site for site in locate.get_text_sites(_task1())}
    assert sites[R1_CALL] == locate.Site(R1, R1_CALL, 2, 4, False)


def test_get_text_sites_xor(text_table):
    sites = {site.call_va: site for site in locate.get_text_sites(_task1())}
    assert sites[R2_CALL] == locate.Site(R2, R2_CALL, 0, 1, False)


def test_get_text_sites_computed(text_table):
    sites = {site.call_va: site for site in locate.get_text_sites(_task1())}
    assert sites[R3_CALL] == locate.Site(R3, R3_CALL, 1, None, True)


def test_get_text_sites_tail_jump_and_order(text_table):
    sites = locate.get_text_sites(_task1())
    assert [site.call_va for site in sites] == [R1_CALL, R2_CALL, R3_CALL, R4_JMP]
    assert sites[-1] == locate.Site(R4, R4_JMP, 3, 2, False)


@pytest.mark.parametrize("slots", [TEXT_SLOTS - 1, TEXT_SLOTS + 1])
def test_planted_section_count_fails(monkeypatch, slots):
    monkeypatch.setitem(locate.GET_TEXT, "ufo2p", (GT, TEXT_TABLE, slots))
    with pytest.raises(locate.LocateError, match="slot"):
        locate.get_text_sections(_task1())


def test_get_text_refuses_a_slot_inside_a_string(text_table):
    planted = _slot(0, S0) + _slot(1, S1 + 1) + _slot(3, S3)  # S1 + 1 is inside "ccc"
    with pytest.raises(locate.LocateError, match="string start"):
        locate.get_text_sections(_task1(planted))


def test_get_text_refuses_shared_starts(text_table):
    planted = _slot(0, S0) + _slot(1, S1) + _slot(3, S1)
    with pytest.raises(locate.LocateError, match="share"):
        locate.get_text_sections(_task1(planted))


def test_get_text_refuses_a_pointer_outside_the_blob(text_table):
    planted = _slot(0, S0) + _slot(1, S1) + _slot(3, TEXT_TABLE + 0x100)  # past the table
    with pytest.raises(locate.LocateError, match="below the table"):
        locate.get_text_sections(_task1(planted))


def test_cli_get_text_json(monkeypatch, capsys, text_table):
    report = _locate_json(monkeypatch, capsys, "--get-text", "2", "4")
    assert report["get_text"] == [2, 4]
    assert report["sites"] == [{"caller": f"0x{R1:08X}", "call": f"0x{R1_CALL:08X}"}]
    assert report["rows"] == [f"0x{R1:08X}"]
    partial = _locate_json(monkeypatch, capsys, "--get-text", "1", "7")
    assert partial["rows"] == []  # R3 asks for section 1 with a computed index
    assert partial["partial_rows"] == [f"0x{R3:08X}"]


def test_cli_va_on_a_text_string(monkeypatch, capsys, text_table):
    report = _locate_json(monkeypatch, capsys, "--va", hex(S0 + 2))
    assert report["get_text"] == {"section": 0, "index": 1}
    assert report["sites"] == [{"caller": f"0x{R2:08X}", "call": f"0x{R2_CALL:08X}"}]
    assert report["rows"] == [f"0x{R2:08X}"]
    outside = _locate_json(monkeypatch, capsys, "--va", hex(STRING))
    assert outside["get_text"] is None
    assert outside["rows"] == [f"0x{A:08X}"]


# ---- real files (skip without orig/) ----

REAL_EXES = {"ufo2p": "UFO2P.EXE", "tacp": "TACP.EXE"}
REAL_CONFIG = REPO_ROOT / "config"


def _real_param(exe: str):
    name = REAL_EXES[exe]
    return pytest.param(exe, id=exe, marks=pytest.mark.skipif(
        not (ORIG_DIR / name).is_file(),
        reason=f"orig/{name} not present (run uv run reverseapoc ingest or set REVERSEAPOC_ORIG)"))


@cache
def _real(exe: str):
    requires_capstone()
    return locate.load_inputs(REAL_CONFIG, ORIG_DIR, REAL_CONFIG / "targets.toml", exe)


@cache
def _real_sites(exe: str) -> tuple[locate.Site, ...]:
    return tuple(locate.get_text_sites(_real(exe)))


# Spike 007 q4 (README "q4 strings"): both tables have 52 slots. UFO2P fills all 52; research's
# "50 sections" is the loop bound of the dump routine next to get_text, not the table's size.
# TACP fills 21 of its 52 slots.
REAL_SECTIONS = {"ufo2p": 52, "tacp": 21}
REAL_CALLER_ROWS = {"ufo2p": 180, "tacp": 88}  # research's get_text caller counts
# q4 speed labels (README "#997" table): call site -> (section, index)
SPEED_LABEL_SITES = {
    "ufo2p": {0x000523C1: (38, 43), 0x00052439: (38, 44), 0x000524B1: (38, 45),
              0x0005252C: (38, 46)},
    "tacp": {0x000A751A: (36, 0), 0x000A758C: (36, 1), 0x000A75FE: (36, 2),
             0x000A7670: (36, 3)},
}  # fmt: skip
INT_1A_CALLERS = {"ufo2p": {0x00011430}, "tacp": {0x00011500, 0x000116B0}}  # research, q1


@pytest.mark.parametrize("exe", [_real_param("ufo2p")])
def test_ufo2p_get_text_has_52_sections(exe):
    sections = locate.get_text_sections(_real(exe))
    assert [s.section for s in sections] == list(range(REAL_SECTIONS[exe]))


@pytest.mark.parametrize("exe", [_real_param("tacp")])
def test_tacp_get_text_has_21_sections(exe):
    assert len(locate.get_text_sections(_real(exe))) == REAL_SECTIONS[exe]


@pytest.mark.parametrize("exe", [_real_param(e) for e in REAL_EXES])
def test_get_text_caller_rows(exe):
    assert len({site.caller for site in _real_sites(exe)}) == REAL_CALLER_ROWS[exe]


@pytest.mark.parametrize("exe", [_real_param(e) for e in REAL_EXES])
def test_speed_label_sites(exe):
    sites = {site.call_va: (site.section, site.index) for site in _real_sites(exe)}
    assert {va: sites.get(va) for va in SPEED_LABEL_SITES[exe]} == SPEED_LABEL_SITES[exe]


@pytest.mark.parametrize("exe", [_real_param(e) for e in REAL_EXES])
def test_interrupt_0x1a_callers(exe):
    callers = {site.caller for site in locate.interrupt_callers(_real(exe), VECTOR_BIOS_TICK)}
    assert callers == INT_1A_CALLERS[exe]
