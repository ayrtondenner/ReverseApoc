"""The split-row detector `mechanics splits` (07-45, owner ruling 2026-10-31; D-23 evidence).

Synthetic LE images only: every byte and address is made up, and each opcode is named in a
comment. The image uses the conftest objects (code at 0x10000, data at 0x20000). Each case is
one block of BLOCK bytes: row A at the block start, row B right after it (touching), and a third
row C after a gap, which references B the way the case needs. The real-file test at the end
reads orig/ and the committed config (it skips without orig/).

The module under test is imported inside the tests, so collection works where it is absent.
"""

from __future__ import annotations

import importlib
import json
import re
import struct
from types import SimpleNamespace

import pytest

from conftest import ORIG_DIR, REPO_ROOT, build_le_image, fixup_record, requires_capstone
from reverseapoc import asmclass, cli, locate, mechanics
from reverseapoc.functions import KIND_GAME, FunctionRow, UnitRow
from reverseapoc.le import LE, SRC_OFF32
from reverseapoc.mechanics import AsmRow

CODE = 0x10000  # object 1
BLOCK = 0x80  # one case: A at +0, B at +ROW, C at +C_AT (a gap before C, so B touches no row)
ROW = 0x20
C_AT = 0x50
GAP_B = 0x30  # case (h): B starts here, so A does not touch it
_NOP = b"\x90"  # nop (Watcom filler)
_RET = b"\xc3"  # ret
_XOR_EAX_EAX = b"\x31\xc0"  # xor eax, eax
_ADD_EAX_EAX = b"\x01\xc0"  # add eax, eax
_PUSH_EBX = b"\x53"  # push ebx (a prologue)
_POP_EAX = b"\x58"  # pop eax
_PUSH_IMM32 = b"\x68"  # push imm32
_MOV_EAX_IMM32 = b"\xb8"  # mov eax, imm32
_CALL = b"\xe8"  # call rel32
_JMP = b"\xe9"  # jmp rel32
_JE = b"\x0f\x84"  # je rel32
_REL32 = 4
_IMM_FIELD = 1  # push imm32 / mov eax, imm32: the imm32 sits one byte into the instruction
_ITEM = 4  # one off32 pointer item
_ZERO = b"\x00"
UNIT, OTHER_UNIT = "u_one", "u_two"
OWNER_REASON = "owner 2026-10-31: x"

CASES = ("a", "b", "c", "d", "e", "f", "f2", "g", "h", "i", "j", "k", "u1", "u2")
BASE = {case: CODE + i * BLOCK for i, case in enumerate(CASES)}


def _a(case: str) -> int:
    return BASE[case]


def _b(case: str) -> int:
    return BASE[case] + (GAP_B if case == "h" else ROW)


def _c(case: str) -> int:
    return BASE[case] + C_AT


def _rel(opcode: bytes, at: int, to: int) -> bytes:
    return opcode + struct.pack("<i", to - (at + len(opcode) + _REL32))


def _imm(opcode: bytes, to: int) -> bytes:
    return opcode + struct.pack("<I", to - CODE)  # the field holds an object offset


def _padded(code: bytes, size: int = ROW) -> bytes:
    return code + _NOP * (size - len(code))


def _fixup(field: int, target: int) -> bytes:
    """One off32 fixup record on the first code page: field -> a code address."""
    return fixup_record(SRC_OFF32, field - CODE, 1, target - CODE)


def _case(case: str) -> tuple[dict[int, bytes], bytes]:
    """The patches and fixup records of one block."""
    a, b, c = _a(case), _b(case), _c(case)
    no_ret_a = _padded(_XOR_EAX_EAX)
    xor_ret = _padded(_XOR_EAX_EAX + _RET)
    pushed = _padded(_imm(_PUSH_IMM32, b) + _POP_EAX + _RET)
    called = _padded(_rel(_CALL, c, b) + _RET)
    table = _padded(_RET + _ZERO * _ITEM)  # ret, then one pointer item at c + 1
    spec = {
        "a": ({a: no_ret_a, b: _padded(_PUSH_EBX + _RET), c: called}, b""),
        "b": ({a: no_ret_a, b: _padded(_RET), c: pushed}, _fixup(c + _IMM_FIELD, b)),
        "c": ({a: no_ret_a, b: xor_ret, c: table}, _fixup(c + len(_RET), b)),
        "d": ({a: no_ret_a, b: xor_ret, c: _padded(_rel(_JE, c, b) + _RET)}, b""),
        "e": ({a: _ZERO * ROW, b: _padded(_RET), c: _padded(_RET)}, b""),
        "f": ({a: _padded(_ZERO * (4 * _ITEM)), b: _padded(_RET), c: _padded(_RET)},
              b"".join(_fixup(a + i * _ITEM, c) for i in range(4))),
        "f2": ({a: _padded(_XOR_EAX_EAX + _ZERO * _ITEM), b: _padded(_RET), c: _padded(_RET)},
               _fixup(a + len(_XOR_EAX_EAX), c)),
        "g": ({a: xor_ret, b: _padded(_PUSH_EBX + _RET), c: called}, b""),
        "h": ({a: no_ret_a, b: _padded(_RET), c: called}, b""),
        "i": ({a: no_ret_a, b: _padded(_PUSH_EBX + _RET), c: called}, b""),
        "j": ({a: no_ret_a, b: _padded(_ADD_EAX_EAX), c: _padded(_imm(_MOV_EAX_IMM32, b) + _RET)},
              _fixup(c + _IMM_FIELD, b)),
        "k": ({a: no_ret_a, b: _padded(_PUSH_EBX + _RET), c: called}, b""),
        "u1": ({a: no_ret_a, b: xor_ret, c: _padded(_rel(_JMP, c, b) + _RET)}, b""),
        "u2": ({a: _padded(_rel(_JE, a, b) + _XOR_EAX_EAX), b: xor_ret, c: _padded(_RET)}, b""),
    }  # fmt: skip
    return spec[case]


def _row(start: int, unit: str = UNIT) -> FunctionRow:
    return FunctionRow(start, start + ROW, f"func_{start:08X}", KIND_GAME, unit, "call")


def _rows() -> list[FunctionRow]:
    rows = []
    for case in CASES:
        b_unit = OTHER_UNIT if case == "i" else UNIT
        rows += [_row(_a(case)), _row(_b(case), b_unit), _row(_c(case))]
    return rows


def _split_exe(stem: str = "ufo2p"):
    patches, fixups = {}, b""
    for case in CASES:
        more, records = _case(case)
        patches |= more
        fixups += records
    le = LE(build_le_image(fixups=[fixups, b"", b""], patches=patches).data)
    flat = bytes(le.load_flat(relocate=False))
    units = (UnitRow(UNIT, CODE, CODE + len(CASES) * BLOCK, "first"),
             UnitRow(OTHER_UNIT, _b("i"), _b("i") + ROW, "hand"))  # fmt: skip
    return SimpleNamespace(stem=stem, le=le, flat=flat, fixups=tuple(le.fixups()),
                           rows=tuple(_rows()), units=units)  # fmt: skip


def _splits():
    return importlib.import_module("reverseapoc.splits")


def _signed_k() -> list[AsmRow]:
    return [AsmRow("ufo2p", _a("k"), "no-terminator", "asm", OWNER_REASON)]


def _pairs(**kwargs) -> dict[int, object]:
    pairs = _splits().classify_splits(_split_exe(), **kwargs)
    return {pair.a: pair for pair in pairs}


EXPECTED = {  # case: the fields the case pins
    "a": {"klass": "fall-through", "calls": 1, "b_head": "prologue", "a_last": "xor"},
    "b": {"klass": "fall-through", "taken": 1, "b_head": "terminator", "b_only_terminator": True},
    "c": {"klass": "label", "table": 1, "taken": 0, "calls": 0},
    "d": {"klass": "label", "cond_jumps": 1, "tail_jumps": 0},
    "e": {"klass": "data"},
    "f": {"klass": "data", "a_code": False, "a_items": True},
    "f2": {"klass": "data", "a_code": True, "a_items": True},
    "g": None,  # A has a ret: not listed
    "h": None,  # a gap between A and B: not listed
    "i": {"klass": "fall-through", "same_unit": False, "a_unit": UNIT, "b_unit": OTHER_UNIT},
    "j": {"klass": "unclear", "taken": 1, "b_terminator": False, "b_head": "other"},
    "k": {"klass": "fall-through", "conflict": True, "a_verdict": "asm"},
}  # fmt: skip


@pytest.mark.parametrize("case", list(EXPECTED))
def test_split_pairs_classes(case):
    requires_capstone()
    found = _pairs(signed_list=_signed_k())
    expected = EXPECTED[case]
    if expected is None:
        assert _a(case) not in found
        return
    pair = found[_a(case)]
    assert (pair.exe, pair.b, pair.a_size, pair.b_size) == ("ufo2p", _b(case), ROW, ROW)
    for field, value in expected.items():
        assert getattr(pair, field) == value, (case, field)
    if case != "k":
        assert pair.conflict is False


def test_split_pair_count_and_conflict_needs_the_list():
    requires_capstone()
    found = _pairs()
    listed = {case for case, expected in EXPECTED.items() if expected is not None}
    assert set(found) == {_a(case) for case in listed | {"u1", "u2"}}
    assert found[_a("k")].conflict is False and found[_a("k")].a_verdict == "-"


def test_unconditional_jump_from_another_row_is_function_evidence():
    requires_capstone()
    found = _pairs()
    jumped = found[_a("u1")]
    assert (jumped.tail_jumps, jumped.cond_jumps, jumped.klass) == (1, 0, "fall-through")
    own = found[_a("u2")]  # A's own jump to B never counts
    assert (own.tail_jumps, own.cond_jumps, own.calls, own.klass) == (0, 0, 0, "unclear")


# ---- the CLI ----

JSON_KEYS = ["exe", "a", "a_size", "a_unit", "a_last", "a_code", "a_items", "b", "b_size",
             "b_unit", "b_head", "b_only_terminator", "b_terminator", "calls", "tail_jumps",
             "cond_jumps", "taken", "data_refs", "table", "same_unit", "a_content", "b_content",
             "b_evidence", "a_verdict", "conflict", "class"]  # fmt: skip
_HEX_RUN = re.compile(r"[0-9A-Fa-f]{9,}")
_OPERAND = re.compile(r"\b(eax|ebx|ecx|edx|esi|edi|esp|ebp|dword|word|byte|ptr|offset)\b|\[")


def _injected(monkeypatch):
    exes = {"ufo2p": _split_exe(), "tacp": _split_exe("tacp")}
    monkeypatch.setattr(locate, "load_inputs", lambda _c, _o, _m, exe: exes[exe])


def _run(capsys, tmp_path, *extra: str) -> tuple[int, str]:
    code = cli.main(["mechanics", "splits", "--config", str(tmp_path), *extra])
    return code, capsys.readouterr().out


def test_cli_splits_json_shape(tmp_path, monkeypatch, capsys):
    requires_capstone()
    _injected(monkeypatch)
    code, out = _run(capsys, tmp_path, "--json")
    assert code == 0
    doc = json.loads(out)
    assert set(doc) == {"pairs", "counts"}
    assert all(list(pair) == JSON_KEYS for pair in doc["pairs"])
    assert {pair["exe"] for pair in doc["pairs"]} == {"ufo2p", "tacp"}
    first = doc["pairs"][0]
    assert re.fullmatch(r"0x[0-9A-F]{8}", first["a"]) and re.fullmatch(r"0x[0-9A-F]{8}", first["b"])
    assert first["a_verdict"] == "-"  # no signed list in this config
    assert doc["counts"]["ufo2p"] == {"data": 3, "fall-through": 5, "label": 2, "unclear": 2}
    code, out = _run(capsys, tmp_path, "--json", "--exe", "ufo2p")
    one = json.loads(out)
    assert code == 0 and set(one["counts"]) == {"ufo2p"}
    assert {pair["exe"] for pair in one["pairs"]} == {"ufo2p"}
    code, text = _run(capsys, tmp_path, "--exe", "ufo2p")
    lines = [line for line in text.splitlines() if line.strip()]
    assert code == 0 and len(lines) == len(one["pairs"]) + 1  # one per pair, one counts line


def _strings(value) -> list[str]:
    """Every string in a JSON document (JSON's own brackets are not operand text)."""
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in [k, *_strings(v)]]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return [value] if isinstance(value, str) else []


def test_split_output_has_no_bytes(tmp_path, monkeypatch, capsys):
    requires_capstone()
    _injected(monkeypatch)
    code, text = _run(capsys, tmp_path)
    assert code == 0 and text.strip()
    assert not _HEX_RUN.search(text) and not _OPERAND.search(text)
    code, out = _run(capsys, tmp_path, "--json")
    assert code == 0 and not _HEX_RUN.search(out)
    assert [s for s in _strings(json.loads(out)) if _OPERAND.search(s)] == []


def test_cli_splits_writes_nothing(tmp_path, monkeypatch, capsys):
    requires_capstone()
    _injected(monkeypatch)
    assert _run(capsys, tmp_path)[0] == 0
    assert list(tmp_path.iterdir()) == []


# ---- real files (main checkout, orig/) ----

REAL_EXES = {"ufo2p": "UFO2P.EXE", "tacp": "TACP.EXE"}
REAL_PAIRS = {  # (exe, A): (B, class, same unit), the planning probe's named pairs
    ("ufo2p", 0x00051D80): (0x00051DA0, "fall-through", True),
    ("ufo2p", 0x000B78A0): (0x000B78D0, "fall-through", True),
    ("ufo2p", 0x00061F30): (0x00061F50, "fall-through", True),
    # cross-unit at planning time; the owner's 07-45 recut put both rows in u_0009a5d0
    ("ufo2p", 0x0009A5B0): (0x0009A5D0, "fall-through", True),
    ("tacp", 0x000A5D70): (0x000A5DA0, "fall-through", True),
    ("ufo2p", 0x0009D388): (0x0009D397, "label", True),
    ("tacp", 0x0001F7F2): (0x0001F828, "label", True),
    ("tacp", 0x00024B20): (0x00024B30, "data", None),
    ("tacp", 0x000B2040): (0x000B20A0, "data", None),
    ("ufo2p", 0x0005CCF0): (0x0005CD00, "fall-through", None),
}  # fmt: skip
REAL_CONFLICT = ("ufo2p", 0x000477B0)  # 07-44 asm, confirmed by the owner at 07-45
REAL_RERULED = ("ufo2p", 0x0005CCF0)  # 07-44 asm, re-ruled c by the owner at 07-45


def test_real_split_pairs():
    requires_capstone()
    missing = [n for n in REAL_EXES.values() if not (ORIG_DIR / n).is_file()]
    if missing:
        pytest.skip(f"orig/{missing[0]} not present (run uv run reverseapoc ingest or set "
                    "REVERSEAPOC_ORIG)")  # fmt: skip
    splits = _splits()
    config = REPO_ROOT / "config"
    signed = splits.signed_list(config)
    found, untagged = {}, []
    for exe in mechanics.EXES:
        inputs = locate.load_inputs(config, ORIG_DIR, config / "targets.toml", exe)
        pairs = splits.classify_splits(inputs, signed_list=signed)
        found |= {(exe, pair.a): pair for pair in pairs}
        tagged = {row.address for row in asmclass.classify(inputs)
                  if "no-terminator" in row.evidence.split(asmclass.SEPARATOR)}  # fmt: skip
        untagged += [(exe, pair.a) for pair in pairs if pair.a not in tagged]
    for key, (b, klass, same_unit) in REAL_PAIRS.items():
        pair = found[key]
        assert (pair.b, pair.klass) == (b, klass), key
        if same_unit is not None:
            assert pair.same_unit is same_unit, key
    assert found[REAL_CONFLICT].conflict is True
    assert (found[REAL_RERULED].a_verdict, found[REAL_RERULED].conflict) == ("c", False)
    assert untagged == []  # every listed A is exactly an asm-list no-terminator row
