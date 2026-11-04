"""lift.py on hand-written encodings and a stub EXE. Every encoding is written here, never game
bytes. The lifter reads five things of an EXE: `flat`, `rows`, `fixups`, `symbols` and `stem`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reverseapoc import lift
from reverseapoc.functions import FunctionRow
from reverseapoc.le import Fixup

VA = 0x1000
ROW_SPACING = 0x100  # one row per slot, so a row's address does not depend on the one before it
FIELD_SIZE = 4
TABLE_VA = 0x8000
DISP32_OFFSET = 2  # opcode and modrm come first in `mov eax, [ebp + disp32]`


class StubSymbols:
    def c_name(self, va: int, *, data: bool = False) -> str:
        return f"{'D' if data else 'func'}_{va:08x}"


@dataclass
class StubExe:
    flat: bytes
    rows: tuple[FunctionRow, ...]
    fixups: tuple[Fixup, ...]
    symbols: StubSymbols
    stem: str = "stub"


def stub_exe(*codes: str, fixups: tuple[Fixup, ...] = ()) -> StubExe:
    """One game row per hex string, the first at VA, each ROW_SPACING after the one before."""
    flat = bytearray(VA + ROW_SPACING * len(codes))
    rows = []
    for n, text in enumerate(codes):
        code = bytes.fromhex(text)
        start = VA + ROW_SPACING * n
        flat[start : start + len(code)] = code
        rows.append(FunctionRow(start, start + len(code), f"row{n}", "game", "u_stub", "test"))
    return StubExe(bytes(flat), tuple(rows), fixups, StubSymbols())


def data_fixup(src_va: int, target_va: int) -> Fixup:
    return Fixup(src_va, 7, target_va, 2, target_va, FIELD_SIZE)


def clear_caches() -> None:
    for cache in (lift._RESULT_USED, lift._BUILDING, lift._INDEX, lift._FIXUPS):
        cache.clear()


@pytest.fixture(autouse=True)
def fresh_lifter(monkeypatch, tmp_path):
    """The caches key on a stem and on id(exe), so a stub must never read stale rows, leave rows
    behind for a later test, or write the real census."""
    monkeypatch.setattr(lift, "CACHE_DIR", tmp_path)
    clear_caches()
    yield
    clear_caches()


# ---- ebp ----


def test_ebp_as_a_general_register_lifts():
    # mov ebp, eax; mov eax, [ebp + 4]; ret
    text = lift.lift_row(stub_exe("89c5 8b4504 c3"), VA)
    assert "return *(int *)" in text


def test_a_real_ebp_frame_still_refuses():
    # push ebp; mov ebp, esp; pop ebp; ret
    with pytest.raises(lift.Unliftable, match="frame: ebp frame"):
        lift.lift_row(stub_exe("55 89e5 5d c3"), VA)


def test_ebp_holding_a_scaled_index_reads_an_array_element():
    # lea ebp, [ecx*4]; mov eax, [ebp + disp32]; ret
    field = VA + 7 + DISP32_OFFSET
    exe = stub_exe("8d2c8d00000000 8b8500000000 c3", fixups=(data_fixup(field, TABLE_VA),))
    assert f"((int *)D_{TABLE_VA:08x})[r_ecx]" in lift.lift_row(exe, VA)


# ---- a jump into an instruction ----

BAD_ROW = "31c0 75fd c3"  # xor eax, eax; jne into the xor's second byte; ret


def call_to(src: int, target: int) -> str:
    """`call target` at `src`, as hex."""
    size = 5
    return "e8" + (target - (src + size)).to_bytes(4, "little", signed=True).hex()


def test_a_jump_into_an_instruction_is_unliftable():
    with pytest.raises(lift.Unliftable, match="jump: into an instruction"):
        lift.lift_row(stub_exe(BAD_ROW), VA)


def test_a_bad_callee_leaves_its_signature_unknown():
    # mov eax, 1; call the bad row; ret
    caller = f"b801000000 {call_to(VA + 5, VA + ROW_SPACING)} c3"
    exe = stub_exe(caller, BAD_ROW)
    bad = VA + ROW_SPACING
    callee_second: dict = {}
    text = lift.lift_row(exe, VA, callee_second)
    callee_first: dict = {}
    with pytest.raises(lift.Unliftable):
        lift.lift_row(exe, bad, callee_first)
    assert lift.lift_row(exe, VA, callee_first) == text
    assert callee_second[bad] is None
    assert f"func_{bad:08x}(1)" in text
