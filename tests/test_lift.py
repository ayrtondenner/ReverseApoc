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


# ---- declaration order ----


def test_locals_declare_by_distance_from_entry():
    # sub esp, 10h; mov [esp], eax; mov [esp + 8], edx; mov eax, [esp]; add eax, [esp + 8];
    # add esp, 10h; ret
    text = lift.lift_row(stub_exe("83ec10 890424 89542408 8b0424 03442408 83c410 c3"), VA)
    assert text.index("int s_8;") < text.index("int s_10;")


# ---- use and def ----


def test_sbb_of_a_register_with_itself_reads_nothing():
    # cmp eax, edx; sbb ecx, ecx; mov eax, ecx; ret. A read of ecx would invent a parameter.
    exe = stub_exe("39d0 19c9 89c8 c3")
    assert lift.Lifter(exe, exe.rows[0]).signature().nregs == 2


# ---- high bytes ----


def first_insn(code: str):
    exe = stub_exe(code)
    return lift.Lifter(exe, exe.rows[0]).decode()[0]


def test_high_byte_read_lifts():
    # movzx eax, ah; ret
    assert "(r_eax >> 8) & 255" in lift.lift_row(stub_exe("0fb6c4 c3"), VA)


def test_high_byte_read_is_a_byte_of_any_register():
    # mov eax, 0; mov al, dh; ret: dh reads edx, and the result is that one byte
    text = lift.lift_row(stub_exe("b800000000 88f0 c3"), VA)
    assert "(r_edx >> 8) & 255" in text


def test_a_parameter_read_through_its_high_byte_stays_wide():
    # movzx eax, ah; ret. As an `unsigned char` the parameter would have no high byte to read.
    assert "unsigned char r_eax" not in lift.lift_row(stub_exe("0fb6c4 c3"), VA)


def test_high_byte_write_keeps_the_low_bytes():
    # mov eax, edx; mov ah, 1; ret
    text = lift.lift_row(stub_exe("89d0 b401 c3"), VA)
    assert "(r_edx & 0xffff00ff) | ((1 & 255) << 8)" in text
    assert lift._use_def(first_insn("b401 c3")) == ({"eax"}, {"eax"})


def test_a_high_byte_write_is_a_use_so_the_register_is_an_argument():
    # mov dh, 1; mov eax, edx; ret. As a plain def, the write would end edx's liveness.
    exe = stub_exe("b601 89d0 c3")
    assert lift.Lifter(exe, exe.rows[0]).signature().nregs == 2


def test_a_high_byte_write_returns_the_full_register():
    # mov ah, 1; ret. A byte return type would drop the byte just written.
    assert lift.lift_row(stub_exe("b401 c3"), VA).startswith("\nint func_")


def test_clearing_a_high_byte_keeps_the_rest_and_reads_it():
    # xor ah, ah; ret. `xor r, r` reads nothing, but this one keeps three bytes of eax.
    assert lift._use_def(first_insn("30e4 c3")) == ({"eax"}, {"eax"})
    assert "return r_eax & 0xffff00ff;" in lift.lift_row(stub_exe("30e4 c3"), VA)


def test_arithmetic_on_a_high_byte_stays_in_that_byte():
    # add ah, 1; ret
    text = lift.lift_row(stub_exe("80c401 c3"), VA)
    assert "(r_eax & 0xffff00ff) | (((((r_eax >> 8) & 255) + 1) & 255) << 8)" in text


# ---- stack structs ----

FRAME = "83ec10"  # sub esp, 10h
UNFRAME = "83c410 c3"  # add esp, 10h; ret


def in_frame(code: str) -> str:
    return lift.lift_row(stub_exe(f"{FRAME} {code} {UNFRAME}"), VA)


def test_esp_read_is_the_address_of_the_lowest_local():
    # mov eax, esp
    text = in_frame("89e0")
    assert "char s_10[16];" in text
    assert "return (int)s_10;" in text


def test_lea_of_a_stack_slot_makes_a_memory_local():
    # lea eax, [esp + 8]; mov [esp + 8], edx; mov edx, [esp + 0Ch]; add eax, edx
    text = in_frame("8d442408 89542408 8b54240c 01d0")
    assert "char s_8[8];" in text
    assert "*(int *)s_8 = r_edx;" in text
    assert "(int)s_8" in text
    assert "*(int *)(s_8 + 4)" in text


def test_a_word_inside_an_array_reads_at_its_own_width():
    # lea eax, [esp + 8]; movsx eax, word ptr [esp + 0Ah]
    assert "*(short *)(s_8 + 2)" in in_frame("8d442408 0fbf44240a")


def test_an_array_runs_to_the_next_address_taken_slot():
    # lea eax, [esp + 4]; lea edx, [esp + 8]; add eax, edx
    text = in_frame("8d442404 8d542408 01d0")
    assert "char s_c[4];" in text
    assert "char s_8[8];" in text


def test_an_array_found_late_still_covers_an_earlier_access():
    # mov [esp + 0Ch], edx; lea eax, [esp + 8]: the store comes first, and is still inside it
    assert "*(int *)(s_8 + 4) = r_edx;" in in_frame("8954240c 8d442408")


def test_a_slot_below_every_array_stays_a_scalar():
    # mov [esp], edx; lea eax, [esp + 8]; add eax, [esp]
    text = in_frame("891424 8d442408 030424")
    assert "int s_10;" in text
    assert "s_10 = r_edx;" in text


def test_indexed_slot_reads_through_the_local():
    # mov eax, [esp + ecx*4 + 8]
    text = in_frame("8b448c08")
    assert "char s_8[8];" in text
    assert "return ((int *)s_8)[r_ecx];" in text


def test_indexed_slot_writes_through_the_local():
    # mov [esp + ecx*4 + 8], eax
    assert "((int *)s_8)[r_ecx] = r_eax;" in in_frame("89448c08")


def test_an_indexed_slot_of_another_scale_is_an_address():
    # mov eax, [esp + ecx*2 + 8]
    assert "*(int *)(s_8 + (r_ecx * 2))" in in_frame("8b444c08")


def test_a_store_through_the_array_keeps_its_order_with_a_read():
    # lea ecx, [esp + 8]; mov eax, [esp + 8]; mov [ecx], edx: eax must not read after the store
    text = in_frame("8d4c2408 8b442408 8911")
    assert text.index("r_eax = *(int *)s_8;") < text.index("= r_edx;")


def test_a_row_with_no_address_taken_keeps_its_scalars():
    # mov [esp + 8], eax; mov eax, [esp + 8]
    text = in_frame("89442408 8b442408")
    assert "int s_8;" in text
    assert "char" not in text


def test_an_address_outside_the_frame_refuses():
    # push eax; mov edx, esp; pop eax; ret: this esp is the pushed value, below the frame
    with pytest.raises(lift.Unliftable, match="stack: address outside the frame"):
        lift.lift_row(stub_exe("50 89e2 58 c3"), VA)
