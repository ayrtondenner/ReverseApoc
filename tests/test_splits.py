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
from reverseapoc import asmclass, cli, locate, mechanics, status
from reverseapoc.functions import KIND_GAME, KIND_RUNTIME, FunctionRow, UnitRow
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
    # splits batch 2 (2026-11-20) merged the label pair tacp 0x0001F7F2 / 0x0001F828 into
    # 0x0001F2B0; the switch-table head before it is the pair left
    ("tacp", 0x0001F270): (0x0001F2B0, "data", True),
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


# ---- interior branches: a branch into the middle of another row (suspected bad splits) ----
#
# Its own synthetic image (code at 0x10000, rows of ROW bytes):
#   P    +0x000  call Q+8 (a suspect: split Q), call R (a row start), jmp P+0x10 (its own
#                row), ret
#   Q    +0x040  (a gap before it, so P and Q do not touch) xor, xor, ret
#   A    +0x080  je B+4 (a suspect: A and B touch, merge them), ret
#   B    +0x0A0  xor, xor, ret
#   C    +0x0C0  xor, ret
#   D    +0x0E0  xor, jmp B+4 (a suspect: merge B..D; it shares B with A..B, so one fix
#                merges A..D), ret
#   X    +0x120  je Q+4, then "abcdef" and a zero (a text-run row: data read as code, skipped)
#   R    +0x160  call X+6 (into a text-run row: skipped), call RT+2 (a runtime row: ignored), ret
#   S    +0x180  jmp Q+0x10 and nothing else (a tail-jump stub: its target is an entry, split Q)
#   M    +0x1C0  xor, jmp Q+1 (inside Q's first xor: no instruction starts there, skipped)
#   G    +0x200  xor, jne H+4 (a suspect: merge G..H, or review it when MID is matched), ret
#   MID  +0x220  ret
#   H    +0x240  xor, xor, ret
#   L    +0x260  jmp H+4 as its first instruction, then xor and ret (no stub: merge H..L, which
#                shares H with G..H, so one fix merges G..L)
#   RT   +0x280  a runtime row: xor, ret

_OFFSETS = (0x000, 0x040, 0x080, 0x0A0, 0x0C0, 0x0E0, 0x120, 0x160, 0x180, 0x1C0, 0x200, 0x220,
            0x240, 0x260, 0x280)  # fmt: skip
_P, _Q, _A, _B, _C, _D, _X, _R, _S, _M, _G, _MID, _H, _L, _RT = (CODE + off for off in _OFFSETS)
_TEXT = b"abcdef\x00"  # printable ASCII ended by a zero (asmclass TEXT_RUN is 6)
_JMP_OWN = 0x10  # P's jump into itself
_STUB_TO = 0x10  # S's jump into Q: one of Q's nops
_MID_XOR = 1  # M's jump: the second byte of Q's first xor
_JNE = b"\x0f\x85"  # jne rel32
_X2 = len(_XOR_EAX_EAX)
_AFTER_JE = len(_JE) + _REL32  # X+6: the first text byte, an instruction start


def _interior_exe(stem: str = "ufo2p"):
    call_q = _rel(_CALL, _P, _Q + 8)
    call_r = _rel(_CALL, _P + len(call_q), _R)
    own_at = _P + 2 * len(call_q)
    patches = {
        _P: _padded(call_q + call_r + _rel(_JMP, own_at, _P + _JMP_OWN) + _RET),
        _Q: _padded(_XOR_EAX_EAX * 2 + _RET),
        _A: _padded(_rel(_JE, _A, _B + 4) + _RET),
        _B: _padded(_XOR_EAX_EAX * 2 + _RET),
        _C: _padded(_XOR_EAX_EAX + _RET),
        _D: _padded(_XOR_EAX_EAX + _rel(_JMP, _D + _X2, _B + 4) + _RET),
        _X: _padded(_rel(_JE, _X, _Q + 4) + _TEXT),
        _R: _padded(_rel(_CALL, _R, _X + _AFTER_JE) + _rel(_CALL, _R + 5, _RT + _X2) + _RET),
        _S: _padded(_rel(_JMP, _S, _Q + _STUB_TO)),
        _M: _padded(_XOR_EAX_EAX + _rel(_JMP, _M + _X2, _Q + _MID_XOR) + _RET),
        _G: _padded(_XOR_EAX_EAX + _rel(_JNE, _G + _X2, _H + 4) + _RET),
        _MID: _padded(_RET),
        _H: _padded(_XOR_EAX_EAX * 2 + _RET),
        _L: _padded(_rel(_JMP, _L, _H + 4) + _XOR_EAX_EAX + _RET),
        _RT: _padded(_XOR_EAX_EAX + _RET),
    }  # fmt: skip
    le = LE(build_le_image(fixups=[b"", b"", b""], patches=patches).data)
    flat = bytes(le.load_flat(relocate=False))
    rows = tuple(_row(start, OTHER_UNIT if start == _Q else UNIT) for start in sorted(patches)
                 if start != _RT)  # fmt: skip
    rows += (FunctionRow(_RT, _RT + ROW, "rt_one", KIND_RUNTIME, "rt_unit", "runtime"),)
    units = (UnitRow(UNIT, CODE, _RT, "first"),)
    return SimpleNamespace(stem=stem, le=le, flat=flat, fixups=tuple(le.fixups()), rows=rows,
                           units=units)  # fmt: skip


def _interior(**kwargs):
    return _splits().interior_branches(_interior_exe(), **kwargs)


def test_interior_branch_suspects():
    requires_capstone()
    report = _interior(statuses={_Q: "matched"})
    found = [(s.source, s.site, s.branch, s.target, s.offset, s.touching, s.fix)
             for s in report.suspects]  # fmt: skip
    assert found == [
        (_P, 0, "call", _Q, 8, False, "split"),
        (_A, 0, "jcc", _B, 4, True, "merge"),
        (_D, _X2, "jmp", _B, 4, False, "merge"),
        (_S, 0, "jmp", _Q, _STUB_TO, False, "split"),
        (_G, _X2, "jcc", _H, 4, False, "merge"),
        (_L, 0, "jmp", _H, 4, True, "merge"),
    ]
    first = report.suspects[0]
    assert (first.exe, first.source_unit, first.target_unit) == ("ufo2p", UNIT, OTHER_UNIT)
    assert (first.source_status, first.target_status) == ("-", "matched")
    assert report.skipped == 3  # X's je and R's call (text-run rows), M's jmp (no insn start)


def test_interior_branch_fixes():
    requires_capstone()
    fixes = [(f.action, f.rows, f.at) for f in _interior().fixes]
    assert fixes == [
        ("split", (_Q,), _Q + 8),
        ("split", (_Q,), _Q + _STUB_TO),
        ("merge", (_A, _B, _C, _D), None),  # A..B and B..D share B: one merge
        ("merge", (_G, _MID, _H, _L), None),  # G..H and H..L share H: one merge
    ]


def test_interior_fix_on_a_matched_row_is_review():
    requires_capstone()
    statuses = {_MID: "matched", _Q: "partial"}
    fixes = [(f.action, f.rows, f.at) for f in _interior(statuses=statuses).fixes]
    assert fixes[-1] == ("review", (_G, _MID, _H, _L), None)  # MID's boundaries are proven
    assert [f[0] for f in fixes[:3]] == ["split", "split", "merge"]  # partial proves nothing
    report = _interior(statuses={_Q: "matched"})
    assert [(f.action, f.at) for f in report.fixes[:2]] == [("review", _Q + 8),
                                                            ("review", _Q + _STUB_TO)]


def _interior_run(capsys, config, *extra: str) -> tuple[int, str]:
    code = cli.main(["mechanics", "interior", "--config", str(config), *extra])
    return code, capsys.readouterr().out


INTERIOR_KEYS = ["exe", "source", "source_unit", "site", "branch", "target", "target_unit",
                 "offset", "touching", "source_status", "target_status", "fix"]  # fmt: skip


def _interior_injected(monkeypatch):
    exes = {"ufo2p": _interior_exe(), "tacp": _interior_exe("tacp")}
    monkeypatch.setattr(locate, "load_inputs", lambda _c, _o, _m, exe: exes[exe])


def test_cli_interior_json_and_text(tmp_path, monkeypatch, capsys):
    requires_capstone()
    _interior_injected(monkeypatch)
    code, out = _interior_run(capsys, tmp_path, "--json")
    assert code == 0
    doc = json.loads(out)
    assert set(doc) == {"suspects", "fixes", "counts"}
    assert all(list(s) == INTERIOR_KEYS for s in doc["suspects"])
    first = doc["suspects"][0]
    assert (first["source"], first["site"], first["target"], first["offset"]) == (
        f"0x{_P:08X}", "0x0", f"0x{_Q:08X}", "0x8")  # fmt: skip
    assert doc["fixes"][0] == {"exe": "ufo2p", "action": "split", "rows": [f"0x{_Q:08X}"],
                               "at": f"0x{_Q + 8:08X}"}  # fmt: skip
    assert doc["fixes"][2]["at"] is None
    assert doc["counts"]["tacp"] == {"suspects": 6, "call": 1, "jmp": 3, "jcc": 2, "skipped": 3,
                                     "split": 2, "merge": 2, "review": 0}  # fmt: skip
    code, text = _interior_run(capsys, tmp_path, "--exe", "ufo2p")
    lines = [line for line in text.splitlines() if line.strip()]
    assert code == 0 and len(lines) == 6 + 4 + 1  # suspects, fixes, one counts line
    assert lines[0].startswith(f"ufo2p 0x{_P:08X}+0x0 call -> 0x{_Q:08X}+0x8 ")
    assert lines[6] == f"ufo2p fix: split 0x{_Q:08X} at 0x{_Q + 8:08X}"
    assert lines[9] == (f"ufo2p fix: merge 0x{_G:08X} 0x{_MID:08X} 0x{_H:08X} 0x{_L:08X} "
                        "(4 rows)")  # fmt: skip
    assert not _HEX_RUN.search(text) and not _OPERAND.search(text)
    assert list(tmp_path.iterdir()) == []  # writes nothing


def test_cli_interior_reads_status_csv(tmp_path, monkeypatch, capsys):
    requires_capstone()
    _interior_injected(monkeypatch)
    row = status.StatusRow(_MID, f"func_{_MID:08X}", UNIT, status.MATCHED, 100.0, 1,
                           "0" * 64, "2026-11-18")  # fmt: skip
    status.write_status(status.status_path(tmp_path, "ufo2p"), [row])
    code, out = _interior_run(capsys, tmp_path, "--json")
    doc = json.loads(out)
    assert code == 0
    assert doc["counts"]["ufo2p"]["review"] == 1 and doc["counts"]["tacp"]["review"] == 0
    review = [fix for fix in doc["fixes"] if fix["action"] == "review"]
    assert review == [{"exe": "ufo2p", "action": "review",
                       "rows": [f"0x{_G:08X}", f"0x{_MID:08X}", f"0x{_H:08X}", f"0x{_L:08X}"],
                       "at": None}]


# checked by hand 2026-11-18. Splits batch 2 (2026-11-20) landed the ufo2p 0x00024470 merge and the
# 0x0002E100 split at 0x0002E280, so their examples are now the skipped merge 0x00018577 +
# 0x0001863E (a shared exit of two hand-asm routines) and the partial row's jcc into 0x0002E100
# (the cluster's fix is a review: it holds matched rows)
REAL_INTERIOR = {  # (exe, source, site): (target, offset, fix)
    ("ufo2p", 0x0001863E, 0x20): (0x00018577, 0xB5, "merge"),  # into a shared exit
    ("ufo2p", 0x0002FAF0, 0x44C): (0x0002E100, 0x171, "merge"),  # a fix of review
    ("tacp", 0x000AF170, 0x0): (0x000B12E0, 0x100, "split"),  # a tail-jump stub
}
REAL_FIXES = {
    ("ufo2p", "merge", (0x00018577, 0x0001863E), None),
    ("tacp", "split", (0x000B12E0,), 0x000B13E0),
}


def test_real_interior_branches():
    requires_capstone()
    missing = [n for n in REAL_EXES.values() if not (ORIG_DIR / n).is_file()]
    if missing:
        pytest.skip(f"orig/{missing[0]} not present (run uv run reverseapoc ingest or set "
                    "REVERSEAPOC_ORIG)")  # fmt: skip
    config = REPO_ROOT / "config"
    found, fixes = {}, set()
    for exe in mechanics.EXES:
        inputs = locate.load_inputs(config, ORIG_DIR, config / "targets.toml", exe)
        report = _splits().interior_branches(inputs)
        found |= {(exe, s.source, s.site): (s.target, s.offset, s.fix) for s in report.suspects}
        fixes |= {(exe, f.action, f.rows, f.at) for f in report.fixes}
        assert report.skipped > 0  # text read as code is there to skip
    for key, expected in REAL_INTERIOR.items():
        assert found[key] == expected, key
    assert REAL_FIXES <= fixes
