"""The D-23 asm detector and the verdict-preserving asm list write: synthetic LE images only,
every byte and address made up. The real-file checks at the end read the committed units.csv
(always) and orig/ plus a committed config/asm-functions.csv (skip or pass vacuously without).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from conftest import ORIG_DIR, REPO_ROOT, build_le_image, requires_capstone
from reverseapoc import asmclass, cli, locate, mechanics
from reverseapoc.functions import KIND_GAME, KIND_RUNTIME, FunctionRow, UnitRow, read_units_csv
from reverseapoc.le import LE
from reverseapoc.mechanics import AsmRow

CODE = 0x10000  # object 1
_NOP = b"\x90"
_RET = b"\xc3"
_ENTER_8_0 = b"\xc8\x08\x00\x00"  # enter 8, 0
_LEAVE = b"\xc9"
_PUSHAL, _POPAL = b"\x60", b"\x61"
_IRETD = b"\xcf"
_FRAME = b"\x55\x89\xe5"  # push ebp; mov ebp, esp
_ARG_READ = b"\x8b\x45\x08"  # mov eax, [ebp + 8]: a stack argument
_LOCAL_READ = b"\x8b\x45\xfc"  # mov eax, [ebp - 4]: a local
_POP_EBP = b"\x5d"
_XOR_EAX_EAX = b"\x31\xc0"

P = CODE  # aligned, plain: not listed
E = CODE + 0x21  # unaligned: enter
PA = CODE + 0x41  # unaligned: pushal
IR = CODE + 0x61  # unaligned: iretd
SF = CODE + 0x81  # unaligned: a frame reading [ebp + 8]
NP = CODE + 0xA1  # unaligned: three nops inside the body
U = CODE + 0xC1  # unaligned, nothing else (its trailing nops are padding): unclear
L = CODE + 0xE0  # aligned, inside the library unit: asm
SF2 = CODE + 0x101  # unaligned: a frame reading only locals, so no stack-frame tag: unclear
E2 = CODE + 0x120  # aligned with enter, outside the library: not listed
RT = CODE + 0x141  # unaligned runtime row: not listed (game rows only)
END = CODE + 0x160
LIBRARY = ("u_lib",)
UNITS = (UnitRow("u_lib", L, SF2, "hand"),)


def _padded(code: bytes, size: int) -> bytes:
    return code + _NOP * (size - len(code))


def _row(start: int, end: int, kind: str = KIND_GAME) -> FunctionRow:
    return FunctionRow(start, end, f"func_{start:08X}", kind, f"u_{start:08x}", "call")


ROWS = [
    _row(P, E), _row(E, PA), _row(PA, IR), _row(IR, SF), _row(SF, NP), _row(NP, U), _row(U, L),
    _row(L, SF2), _row(SF2, E2), _row(E2, RT), _row(RT, END, KIND_RUNTIME),
]  # fmt: skip
PATCHES = {
    P: _padded(_RET, 0x21),
    E: _padded(_ENTER_8_0 + _LEAVE + _RET, 0x20),
    PA: _padded(_PUSHAL + _POPAL + _RET, 0x20),
    IR: _padded(_IRETD, 0x20),
    SF: _padded(_FRAME + _ARG_READ + _POP_EBP + _RET, 0x20),
    NP: _padded(_XOR_EAX_EAX + _NOP * 3 + _RET, 0x20),
    U: _padded(_RET, 0x1F),
    L: _padded(_RET, 0x21),
    SF2: _padded(_FRAME + _LOCAL_READ + _POP_EBP + _RET, 0x1F),
    E2: _padded(_ENTER_8_0 + _LEAVE + _RET, 0x21),
    RT: _padded(_ENTER_8_0 + _LEAVE + _RET, 0x1F),
}  # fmt: skip
EXPECTED = [
    AsmRow("ufo2p", E, "unaligned;enter", "asm"),
    AsmRow("ufo2p", PA, "unaligned;pushal", "asm"),
    AsmRow("ufo2p", IR, "unaligned;iretd", "asm"),
    AsmRow("ufo2p", SF, "unaligned;stack-frame", "asm"),
    AsmRow("ufo2p", NP, "unaligned;nop-pad", "asm"),
    AsmRow("ufo2p", U, "unaligned", "unclear"),
    AsmRow("ufo2p", L, "library-span", "asm"),
    AsmRow("ufo2p", SF2, "unaligned", "unclear"),
]


def _exe(stem: str = "ufo2p", rows=ROWS, units=UNITS):
    le = LE(build_le_image(fixups=[b"", b"", b""], patches=PATCHES).data)
    flat = bytes(le.load_flat(relocate=False))
    return SimpleNamespace(stem=stem, le=le, flat=flat, fixups=tuple(le.fixups()),
                           rows=tuple(rows), units=tuple(units))  # fmt: skip


def _classify(**kwargs):
    return asmclass.classify(_exe(**kwargs), library=LIBRARY)


def _by_address(rows) -> dict[int, AsmRow]:
    return {row.address: row for row in rows}


def test_tag_and_verdict_vocabulary():
    assert asmclass.TAGS == ("unaligned", "stack-frame", "enter", "pushal", "iretd", "nop-pad",
                             "library-span")  # fmt: skip
    assert asmclass.ALIGNMENT == 16
    assert set(asmclass.LIBRARY_UNITS) == set(mechanics.EXES)


def test_tags():
    found = _by_address(_classify())
    assert found[E].evidence == "unaligned;enter"
    assert found[PA].evidence == "unaligned;pushal"
    assert found[IR].evidence == "unaligned;iretd"
    assert found[SF].evidence == "unaligned;stack-frame"
    assert found[NP].evidence == "unaligned;nop-pad"
    assert found[SF2].evidence == "unaligned"  # locals only: no stack-frame tag
    assert found[U].evidence == "unaligned"  # nops after the last ret are padding
    assert P not in found and E2 not in found  # aligned and outside the library: not listed
    assert RT not in found  # a runtime row: not a game row


def test_exact_proposal():
    assert _classify() == EXPECTED


def test_planted_wrong_proposal_fails():
    with pytest.raises(AssertionError):
        assert _classify() == [*EXPECTED[:5], AsmRow("ufo2p", U, "unaligned", "asm"),
                               *EXPECTED[6:]]  # fmt: skip


def test_unaligned_only_is_unclear():
    found = _by_address(_classify())
    assert found[U].verdict == "unclear"
    assert found[E].verdict == "asm"


def test_library_span_rows():
    assert _by_address(_classify())[L] == AsmRow("ufo2p", L, "library-span", "asm")


def test_library_unit_missing_from_units_is_refused():
    with pytest.raises(asmclass.AsmClassError, match="u_lib"):
        asmclass.classify(_exe(units=()), library=LIBRARY)


def test_classify_reads_library_units_per_exe(monkeypatch):
    monkeypatch.setitem(asmclass.LIBRARY_UNITS, "tacp", LIBRARY)
    rows = asmclass.classify(_exe(stem="tacp"))
    assert _by_address(rows)[L] == AsmRow("tacp", L, "library-span", "asm")


def test_no_unaligned_row_is_empty():
    aligned = [_row(P, E), _row(L, SF2), _row(E2, RT)]
    assert asmclass.classify(_exe(rows=aligned, units=()), library=()) == []


# ---- the verdict-preserving merge (orchestrator ruling F17) ----

GONE = CODE + 0x1001  # a row the detector no longer proposes


def test_merge_keeps_hand_verdicts():
    existing = [
        AsmRow("ufo2p", E, "unaligned;enter", "c", "owner: plain C behind a frame"),
        AsmRow("ufo2p", U, "unaligned", "asm", "owner read it"),
    ]
    rows, changed = asmclass.merge(existing, EXPECTED)
    found = _by_address(rows)
    assert found[E] == existing[0]  # asm -> c kept with its reason
    assert found[U] == existing[1]  # unclear -> asm kept with its reason
    assert found[PA] == _by_address(EXPECTED)[PA]  # a new row gets the proposal
    assert f"ufo2p 0x{E:08X}" not in " ".join(changed)  # owner flips are not changes (F17)
    assert f"ufo2p 0x{U:08X}" not in " ".join(changed)
    assert f"ufo2p 0x{PA:08X} added" in changed


def test_merge_reports_tool_column_changes_and_removed_rows():
    existing = [
        AsmRow("ufo2p", SF, "unaligned", "asm", "owner: frame"),
        AsmRow("tacp", GONE, "unaligned", "unclear"),
    ]
    rows, changed = asmclass.merge(existing, EXPECTED)
    found = _by_address(rows)
    assert found[SF] == AsmRow("ufo2p", SF, "unaligned;stack-frame", "asm", "owner: frame")
    assert GONE not in found
    assert f"ufo2p 0x{SF:08X} evidence" in changed
    assert f"tacp 0x{GONE:08X} removed" in changed


def test_merge_of_its_own_output_changes_nothing():
    rows, changed = asmclass.merge([], EXPECTED)
    again, changed_again = asmclass.merge(rows, EXPECTED)
    assert len(changed) == len(EXPECTED)
    assert again == rows and changed_again == []


# ---- `mechanics asm` ----


def _injected(monkeypatch):
    exes = {"ufo2p": _exe(), "tacp": _exe(stem="tacp", rows=(), units=())}
    monkeypatch.setattr(locate, "load_inputs", lambda _c, _o, _m, exe: exes[exe])
    monkeypatch.setitem(asmclass.LIBRARY_UNITS, "ufo2p", LIBRARY)
    monkeypatch.setitem(asmclass.LIBRARY_UNITS, "tacp", ())


def test_cli_asm_write(tmp_path, monkeypatch, capsys):
    _injected(monkeypatch)
    out = tmp_path / mechanics.ASM_CSV
    assert cli.main(["mechanics", "asm", "--write", "--config", str(tmp_path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdicts"] == {"asm": 6, "c": 0, "unclear": 2}
    assert len(report["changed"]) == len(EXPECTED) and report["written"] is True
    data = out.read_bytes()
    assert data == mechanics.format_asm_csv(EXPECTED).encode("ascii")
    assert b"\r\n" not in data and mechanics.read_asm_list(out) == EXPECTED
    assert cli.main(["mechanics", "asm", "--write", "--config", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["changed"] == []
    assert out.read_bytes() == data  # a second run is byte-identical


def test_cli_asm_without_write_changes_nothing(tmp_path, monkeypatch, capsys):
    _injected(monkeypatch)
    assert cli.main(["mechanics", "asm", "--config", str(tmp_path)]) == 0
    text = capsys.readouterr().out
    assert "8 rows" in text and "6 asm" in text and "2 unclear" in text
    assert not (tmp_path / mechanics.ASM_CSV).exists()


def test_cli_asm_keeps_a_hand_verdict_on_disk(tmp_path, monkeypatch, capsys):
    _injected(monkeypatch)
    out = tmp_path / mechanics.ASM_CSV
    hand = [AsmRow("ufo2p", U, "unaligned", "c", "owner: compiled C")]
    out.write_bytes(mechanics.format_asm_csv(hand).encode("ascii"))
    assert cli.main(["mechanics", "asm", "--write", "--config", str(tmp_path)]) == 0
    assert _by_address(mechanics.read_asm_list(out))[U] == hand[0]
    assert f"0x{U:08X}" not in capsys.readouterr().out  # not reported as a change


# ---- committed data and real files ----

# Research R1 R2: the library spans, by an address each unit was found from.
LIBRARY_EVIDENCE = {
    "ufo2p": {"u_000161b4": 0x000161B4, "u_000c8e40": 0x000C8E41, "u_000c1b4b": 0x000C1B4B},
    "tacp": {"u_000cc150": 0x000CC151},
}  # fmt: skip


def test_library_units_hold_their_research_addresses():
    for exe, evidence in LIBRARY_EVIDENCE.items():
        units = {u.unit: u for u in read_units_csv(REPO_ROOT / "config" / exe / "units.csv")}
        assert asmclass.LIBRARY_UNITS[exe] == tuple(evidence)
        for name, address in evidence.items():
            assert units[name].start <= address < units[name].end, (exe, name)
    vesa = {u.unit: u for u in read_units_csv(REPO_ROOT / "config/ufo2p/units.csv")}["u_000161b4"]
    assert (vesa.start, vesa.end) == (0x000161B4, 0x00018970)  # research's VESA blitter span


def test_asm_list_has_no_drift():
    committed = REPO_ROOT / "config" / mechanics.ASM_CSV
    if not committed.is_file():
        return  # plan 07-20 writes and signs it; nothing to compare yet (F32)
    requires_capstone()
    missing = [n for n in ("UFO2P.EXE", "TACP.EXE") if not (ORIG_DIR / n).is_file()]
    if missing:
        pytest.skip(f"orig/{missing[0]} not present (run uv run reverseapoc ingest or set "
                    "REVERSEAPOC_ORIG)")  # fmt: skip
    config = REPO_ROOT / "config"
    proposed = [row for exe in mechanics.EXES for row in asmclass.classify(
        locate.load_inputs(config, ORIG_DIR, config / "targets.toml", exe))]  # fmt: skip
    rows, changed = asmclass.merge(mechanics.read_asm_list(committed), proposed)
    assert changed == []
    assert mechanics.format_asm_csv(rows).encode("ascii") == committed.read_bytes().replace(
        b"\r\n", b"\n")  # fmt: skip
