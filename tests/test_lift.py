"""lift.py on hand-written encodings and a stub EXE. Every encoding is written here, never game
bytes. The lifter reads five things of an EXE: `flat`, `rows`, `fixups`, `symbols` and `stem`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from reverseapoc import fileio, lift
from reverseapoc.functions import KIND_DATA_IN_CODE, FunctionRow
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
    assert "(r_edx & -65281) | ((1 & 255) << 8)" in text
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
    assert "return r_eax & -65281;" in lift.lift_row(stub_exe("30e4 c3"), VA)


def test_arithmetic_on_a_high_byte_stays_in_that_byte():
    # add ah, 1; ret
    text = lift.lift_row(stub_exe("80c401 c3"), VA)
    assert "(r_eax & -65281) | (((((r_eax >> 8) & 255) + 1) & 255) << 8)" in text


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


# ---- setcc and sbb ----

COMPARE = "39d0"  # cmp eax, edx
MASK_EAX = "25ff000000"  # and eax, 0FFh
UNSIGNED = "((unsigned)r_eax) {} ((unsigned)r_edx)"
SETCC = {  # the condition: the setcc opcode's second byte, and the C it reads as
    "je": ("94", "r_eax == r_edx"),
    "jne": ("95", "r_eax != r_edx"),
    "jl": ("9c", "r_eax < r_edx"),
    "jge": ("9d", "r_eax >= r_edx"),
    "jg": ("9f", "r_eax > r_edx"),
    "jle": ("9e", "r_eax <= r_edx"),
    "jb": ("92", UNSIGNED.format("<")),
    "jae": ("93", UNSIGNED.format(">=")),
    "ja": ("97", UNSIGNED.format(">")),
    "jbe": ("96", UNSIGNED.format("<=")),
    "js": ("98", "(r_eax - r_edx) < 0"),
    "jns": ("99", "(r_eax - r_edx) >= 0"),
}


def test_setcc_covers_every_condition():
    assert set(SETCC) == set(lift.JCC)


@pytest.mark.parametrize(("opcode", "expected"), SETCC.values(), ids=SETCC)
def test_sete_and_mask_is_a_compare(opcode, expected):
    # cmp eax, edx; set<cc> al; and eax, 0FFh; ret
    text = lift.lift_row(stub_exe(f"{COMPARE} 0f{opcode}c0 {MASK_EAX} c3"), VA)
    assert f"return {expected};" in text


def test_setcc_on_a_result_compares_it_with_zero():
    # test eax, eax; sete al; and eax, 0FFh; ret
    assert "return r_eax == 0;" in lift.lift_row(stub_exe(f"85c0 0f94c0 {MASK_EAX} c3"), VA)


def test_setcc_of_another_register_masks_that_register():
    # cmp eax, edx; sete cl; and ecx, 0FFh; mov eax, ecx; ret
    text = lift.lift_row(stub_exe(f"{COMPARE} 0f94c1 81e1ff000000 89c8 c3"), VA)
    assert "return r_eax == r_edx;" in text


def test_a_byte_mask_still_masks_any_other_value():
    # and eax, 0FFh; ret
    assert "return r_eax & 255;" in lift.lift_row(stub_exe(f"{MASK_EAX} c3"), VA)


def test_setcc_without_a_flag_source_refuses():
    # sete al; ret
    with pytest.raises(lift.Unliftable, match="jcc: no flag source"):
        lift.lift_row(stub_exe("0f94c0 c3"), VA)


def test_a_setcc_with_no_jcc_keeps_its_own_refusal():
    # cmp eax, edx; seto al; ret
    with pytest.raises(lift.Unliftable, match="op: seto"):
        lift.lift_row(stub_exe(f"{COMPARE} 0f90c0 c3"), VA)


def test_sign_jump_after_a_compare_is_the_sign_of_the_difference():
    # cmp eax, edx; js +1; inc eax; ret
    text = lift.lift_row(stub_exe(f"{COMPARE} 7801 40 c3"), VA)
    assert "if ((r_eax - r_edx) < 0) goto" in text


def test_sbb_same_register_after_a_compare():
    # cmp eax, edx; sbb eax, eax; ret
    text = lift.lift_row(stub_exe(f"{COMPARE} 19c0 c3"), VA)
    assert f"return -({UNSIGNED.format('<')});" in text


def test_sbb_without_a_flag_source_still_refuses():
    # sbb eax, eax; ret
    with pytest.raises(lift.Unliftable, match="jcc: no flag source"):
        lift.lift_row(stub_exe("19c0 c3"), VA)


def test_sbb_of_two_registers_keeps_its_refusal():
    # cmp eax, edx; sbb eax, edx; ret
    with pytest.raises(lift.Unliftable, match="op: sbb"):
        lift.lift_row(stub_exe(f"{COMPARE} 19d0 c3"), VA)


def test_sbb_after_a_result_keeps_its_refusal():
    # add eax, edx; sbb ecx, ecx; mov eax, ecx; ret. The carry of an add is not a compare.
    with pytest.raises(lift.Unliftable, match="op: sbb"):
        lift.lift_row(stub_exe("01d0 19c9 89c8 c3"), VA)


# ---- switch tables ----

TABLE_AT = VA - 0x40  # the data-in-code row, right before the function as Watcom lays it out


def table_jump(register: int = 0, table: int = TABLE_AT) -> str:
    """`jmp dword ptr cs:[reg*4 + table]`, the form the game's -4r code has."""
    sib = 0x85 | register << 3
    return f"2eff24{sib:02x}" + table.to_bytes(FIELD_SIZE, "little").hex()


JUMP_SIZE = len(bytes.fromhex(table_jump()))
JUMP_FIELD = JUMP_SIZE - FIELD_SIZE  # the displacement closes the instruction


def with_table(exe: StubExe, entries: tuple[int, ...], jump_at: int, start: int = TABLE_AT):
    """`exe` with a data-in-code row at `start` holding `entries` as off32 fixups, and the fixup
    on the displacement of the jump at `jump_at`."""
    end = start + FIELD_SIZE * len(entries)
    table = FunctionRow(start, end, "table", KIND_DATA_IN_CODE, "u_stub", "test")
    fields = tuple(
        data_fixup(start + FIELD_SIZE * n, target) for n, target in enumerate(entries)
    )
    fixups = (*exe.fixups, data_fixup(jump_at + JUMP_FIELD, start), *fields)
    return StubExe(exe.flat, (table, *exe.rows), fixups, exe.symbols)


# cmp eax, 1; ja DEFAULT; jmp [eax*4 + table]; each target then returns its own constant
GUARDED = f"83f801 7708 {table_jump()} b801000000 c3 b802000000 c3 b803000000 c3"
GUARD_JUMP = VA + 5
CASE_0 = GUARD_JUMP + JUMP_SIZE
CASE_1 = CASE_0 + 6
DEFAULT = CASE_1 + 6


def test_switch_table_lifts_to_a_switch():
    exe = with_table(stub_exe(GUARDED.replace("7708", f"77{DEFAULT - GUARD_JUMP:02x}")),
                     (CASE_0, CASE_1), GUARD_JUMP)  # fmt: skip
    text = lift.lift_row(exe, VA)
    assert "switch (r_eax) {" in text
    assert f"case 0: goto L{CASE_0:X};" in text
    assert f"case 1: goto L{CASE_1:X};" in text
    assert f"default: goto L{DEFAULT:X};" in text
    assert "if (" not in text  # the guard is the default, not a test of its own


def test_a_switch_with_no_guard_has_no_default():
    # jmp [eax*4 + table]; two targets that return
    code = f"{table_jump()} b801000000 c3 b802000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (VA + JUMP_SIZE, VA + JUMP_SIZE + 6), VA), VA)
    assert "switch (r_eax) {" in text
    assert "default:" not in text


def test_a_guard_some_instructions_before_the_jump_still_folds():
    # cmp eax, 1; ja DEFAULT; mov ecx, 5; jmp [eax*4 + table]
    other = "b905000000"
    jump_at = VA + 5 + 5
    first = jump_at + JUMP_SIZE
    default = first + 6
    code = f"83f801 77{default - (VA + 5):02x} {other} {table_jump()} b801000000 c3 b803000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first, first), jump_at), VA)
    assert f"default: goto L{default:X};" in text
    assert "switch (r_eax) {" in text
    assert "if (" not in text


def test_a_guard_on_another_register_stays_a_branch():
    # cmp ebx, 1; ja DEFAULT; jmp [eax*4 + table]
    default = GUARD_JUMP + JUMP_SIZE + 6
    code = f"83fb01 77{default - GUARD_JUMP:02x} {table_jump()} b801000000 c3 b803000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (GUARD_JUMP + JUMP_SIZE,), GUARD_JUMP), VA)
    assert f"if (((unsigned)r_ebx) > 1) goto L{default:X};" in text
    assert "switch (r_eax) {" in text
    assert "default:" not in text


def test_a_guard_on_a_copy_of_the_index_still_folds():
    # mov eax, ebx; cmp ebx, 1; ja DEFAULT; jmp [eax*4 + table]
    jump_at = VA + 2 + 5
    first = jump_at + JUMP_SIZE
    default = first + 6
    code = f"89d8 83fb01 77{default - jump_at:02x} {table_jump()} b801000000 c3 b803000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first,), jump_at), VA)
    assert f"default: goto L{default:X};" in text
    assert "if (" not in text


def test_a_guard_on_a_load_still_folds():
    # mov eax, [ecx]; cmp eax, 1; ja DEFAULT; jmp [eax*4 + table]; the cases read eax
    jump_at = VA + 2 + 5
    first = jump_at + JUMP_SIZE
    default = first + 1
    code = f"8b01 83f801 77{default - jump_at:02x} {table_jump()} c3 b803000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first,), jump_at), VA)
    assert f"default: goto L{default:X};" in text
    assert "if (" not in text


def test_an_index_changed_after_the_guard_stays_a_branch():
    # cmp eax, 1; ja DEFAULT; and eax, 0FFFFh; jmp [eax*4 + table]
    jump_at = VA + 5 + 5
    first = jump_at + JUMP_SIZE
    default = first + 6
    mask = "25ffff0000"
    code = f"83f801 77{default - (VA + 5):02x} {mask} {table_jump()} b801000000 c3 b803000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first,), jump_at), VA)
    assert "switch (r_eax & 65535) {" in text
    assert f"if (((unsigned)r_eax) > 1) goto L{default:X};" in text
    assert "default:" not in text


def test_a_guard_dropped_in_a_row_with_an_array_stays_a_branch():
    # sub esp, 10h; lea ecx, [esp + 8]; cmp ebx, 1; ja DEFAULT; jmp [eax*4 + table]
    guard = VA + 3 + 4 + 3
    jump_at = guard + 2
    first = jump_at + JUMP_SIZE
    default = first + 4
    code = f"83ec10 8d4c2408 83fb01 77{default - jump_at:02x} {table_jump()} 83c410 c3 83c410 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first,), jump_at), VA)
    assert f"if (((unsigned)r_ebx) > 1) goto L{default:X};" in text
    assert "default:" not in text


def test_a_ja_with_no_compare_stays_a_branch():
    # test eax, eax; ja DEFAULT; jmp [eax*4 + table]: this `ja` bounds nothing
    jump_at = VA + 4
    first = jump_at + JUMP_SIZE
    default = first + 6
    code = f"85c0 77{default - jump_at:02x} {table_jump()} b801000000 c3 b803000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first,), jump_at), VA)
    assert f"goto L{default:X};" in text
    assert "if (" in text
    assert "default:" not in text


def test_two_tables_of_one_row_each_end_where_the_next_starts():
    # test ecx, ecx; je SECOND; jmp [eax*4 + first]; A; SECOND: jmp [edx*4 + second]; B
    second_table = TABLE_AT + FIELD_SIZE * 2
    first_jump = VA + 4
    target_a = first_jump + JUMP_SIZE
    second_jump = target_a + 6
    target_b = second_jump + JUMP_SIZE
    code = (f"85c9 74{second_jump - first_jump:02x} {table_jump()} b801000000 c3 "
            f"{table_jump(2, second_table)} b802000000 c3")  # fmt: skip
    exe = with_table(stub_exe(code), (target_a, target_a, target_b, target_b), first_jump)
    field = data_fixup(second_jump + JUMP_FIELD, second_table)
    exe = StubExe(exe.flat, exe.rows, (*exe.fixups, field), exe.symbols)
    text = lift.lift_row(exe, VA)
    assert text.count("switch (") == 2
    assert text.count("case 0:") == 2
    assert text.count("case 1:") == 2
    assert "case 2:" not in text


def test_an_indirect_jump_with_no_table_row_refuses():
    # jmp [eax*4 + table], its displacement naming a game row
    code = f"{table_jump(table=VA + ROW_SPACING)} c3"
    exe = stub_exe(code, "c3", fixups=(data_fixup(VA + JUMP_FIELD, VA + ROW_SPACING),))
    with pytest.raises(lift.Unliftable, match=r"jump: indirect \(switch table\)"):
        lift.lift_row(exe, VA)


def test_an_indirect_jump_with_no_fixup_refuses():
    with pytest.raises(lift.Unliftable, match=r"jump: indirect \(switch table\)"):
        lift.lift_row(stub_exe(f"{table_jump()} c3"), VA)


def test_a_table_jump_of_another_scale_refuses():
    # jmp [eax*2 + table]: no table of dwords is read this way
    code = "2eff2445" + TABLE_AT.to_bytes(FIELD_SIZE, "little").hex() + " c3"
    exe = with_table(stub_exe(code), (VA + JUMP_SIZE,), VA)
    with pytest.raises(lift.Unliftable, match=r"jump: indirect \(switch table\)"):
        lift.lift_row(exe, VA)


def test_a_table_whose_fields_are_not_dwords_in_step_refuses():
    # one entry, then a field two bytes on: the row cannot be a table of dwords
    target = VA + JUMP_SIZE
    exe = with_table(stub_exe(f"{table_jump()} c3"), (target, target), VA)
    bent = data_fixup(TABLE_AT + 2, target)
    exe = StubExe(exe.flat, exe.rows, (*exe.fixups, bent), exe.symbols)
    with pytest.raises(lift.Unliftable, match=r"jump: indirect \(switch table\)"):
        lift.lift_row(exe, VA)


def test_a_case_inside_an_instruction_is_unliftable():
    exe = with_table(stub_exe(f"{table_jump()} b801000000 c3"), (VA + JUMP_SIZE + 1,), VA)
    with pytest.raises(lift.Unliftable, match="jump: into an instruction"):
        lift.lift_row(exe, VA)


def test_a_case_outside_the_row_is_unliftable():
    exe = with_table(stub_exe(f"{table_jump()} c3", "c3"), (VA + ROW_SPACING,), VA)
    with pytest.raises(lift.Unliftable, match="jump: into an instruction"):
        lift.lift_row(exe, VA)


def test_a_register_a_case_reads_is_an_argument():
    # jmp [eax*4 + table]; mov eax, edx; ret: edx is read only past the jump
    exe = with_table(stub_exe(f"{table_jump()} 89d0 c3"), (VA + JUMP_SIZE,), VA)
    assert lift.Lifter(exe, exe.rows[1]).signature().nregs == 2


def test_a_register_live_into_a_merged_case_is_assigned_before_the_switch():
    # mov ecx, 5; jmp [eax*4 + table]; A: inc ecx; B: mov eax, ecx; ret. B has two ways in.
    jump_at = VA + 5
    first = jump_at + JUMP_SIZE
    code = f"b905000000 {table_jump()} 41 89c8 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first, first + 1), jump_at), VA)
    assert text.index("r_ecx = 5;") < text.index("switch (")


def test_a_case_never_inherits_the_flags_of_the_block_above_it():
    # jmp [eax*4 + table]; A: test eax, eax; je +0; B: jne: B is entered from the table too
    first = VA + JUMP_SIZE
    second = first + 4
    code = f"{table_jump()} 85c0 7400 7500 c3"
    exe = with_table(stub_exe(code), (first, second), VA)
    with pytest.raises(lift.Unliftable, match="jcc: no flag source"):
        lift.lift_row(exe, VA)


# ---- x87 ----

FLD_A = "d9442408"  # fld dword ptr [esp + 8]: s_8
FLD_B = "d944240c"  # fld dword ptr [esp + 0Ch]: s_4
FSTP_C = "d95c2404"  # fstp dword ptr [esp + 4]: s_c
FLOAT_GLOBAL = 0x9000


def float_global(opcode: str, code_before: str = "") -> StubExe:
    """`opcode [disp32]` with a fixup on the displacement, inside a frame."""
    field = VA + len(bytes.fromhex(FRAME + code_before)) + len(bytes.fromhex(opcode))
    disp = FLOAT_GLOBAL.to_bytes(FIELD_SIZE, "little").hex()
    code = f"{FRAME} {code_before} {opcode} {disp} {FSTP_C} {UNFRAME}"
    return stub_exe(code, fixups=(data_fixup(field, FLOAT_GLOBAL),))


def test_x87_load_operate_store():
    # fld a; fadd dword ptr [esp + 0Ch]; fstp c
    text = in_frame(f"{FLD_A} d844240c {FSTP_C}")
    assert "s_c = s_8 + s_4;" in text
    assert "float s_c;" in text
    assert "float s_8;" in text
    assert "float s_4;" in text


def test_a_qword_operand_is_a_double():
    # fld qword ptr [esp + 8]; fstp qword ptr [esp]
    text = in_frame("dd442408 dd1c24")
    assert "double s_8;" in text
    assert "double s_10;" in text
    assert "s_10 = s_8;" in text


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("d864240c", "s_8 - s_4"),  # fsub dword ptr [esp + 0Ch]
        ("d86c240c", "s_4 - s_8"),  # fsubr dword ptr [esp + 0Ch]
        ("d874240c", "s_8 / s_4"),  # fdiv dword ptr [esp + 0Ch]
        ("d87c240c", "s_4 / s_8"),  # fdivr dword ptr [esp + 0Ch]
        ("d84c240c", "s_8 * s_4"),  # fmul dword ptr [esp + 0Ch]
    ],
)
def test_x87_arithmetic_with_memory(code, expected):
    assert f"s_c = {expected};" in in_frame(f"{FLD_A} {code} {FSTP_C}")


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("dec1", "s_8 + s_4"),  # faddp st(1)
        ("dec9", "s_8 * s_4"),  # fmulp st(1)
        ("dee9", "s_8 - s_4"),  # fsubp st(1): st(1) - st(0)
        ("dee1", "s_4 - s_8"),  # fsubrp st(1): st(0) - st(1)
        ("def9", "s_8 / s_4"),  # fdivp st(1)
        ("def1", "s_4 / s_8"),  # fdivrp st(1)
    ],
)
def test_x87_arithmetic_that_pops(code, expected):
    # fld a; fld b; <op>; fstp c
    assert f"s_c = {expected};" in in_frame(f"{FLD_A} {FLD_B} {code} {FSTP_C}")


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("d8e1", "s_4 - s_8"),  # fsub st(1): st(0) - st(1)
        ("d8e9", "s_8 - s_4"),  # fsubr st(1): st(1) - st(0)
    ],
)
def test_x87_arithmetic_into_the_top(code, expected):
    # fld a; fld b; <op>; fstp c; fstp st(0)
    assert f"s_c = {expected};" in in_frame(f"{FLD_A} {FLD_B} {code} {FSTP_C} ddd8")


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("dce9", "s_8 - s_4"),  # fsub st(1), st(0): st(1) - st(0)
        ("dce1", "s_4 - s_8"),  # fsubr st(1), st(0): st(0) - st(1)
    ],
)
def test_x87_arithmetic_into_a_lower_register(code, expected):
    # fld a; fld b; <op>; fstp st(0); fstp c
    assert f"s_c = {expected};" in in_frame(f"{FLD_A} {FLD_B} {code} ddd8 {FSTP_C}")


def test_fld_of_a_register_copies_it():
    # fld a; fld st(0); faddp st(1); fstp c
    assert "s_c = s_8 + s_8;" in in_frame(f"{FLD_A} d9c0 dec1 {FSTP_C}")


def test_fstp_of_a_register_overwrites_it():
    # fld a; fld b; fstp st(1); fstp c: b replaces a
    assert "s_c = s_4;" in in_frame(f"{FLD_A} {FLD_B} ddd9 {FSTP_C}")


def test_fst_keeps_the_value_on_the_stack():
    # fld a; fst dword ptr [esp + 4]; fstp dword ptr [esp]
    text = in_frame(f"{FLD_A} d9542404 d91c24")
    assert "s_c = s_8;" in text
    assert "s_10 = s_8;" in text


def test_fild_reads_an_integer():
    # fild dword ptr [esp + 8]; fstp c
    text = in_frame(f"db442408 {FSTP_C}")
    assert "int s_8;" in text
    assert "s_c = (double)s_8;" in text


def test_fild_of_a_word_reads_a_short():
    # fild word ptr [esp + 8]; fstp c
    assert "short s_8;" in in_frame(f"df442408 {FSTP_C}")


def test_fistp_stores_an_integer():
    # fld a; fistp dword ptr [esp + 4]
    text = in_frame(f"{FLD_A} db5c2404")
    assert "int s_c;" in text
    assert "s_c = (int)s_8;" in text


def test_fchs_and_fabs_wrap():
    # fld a; fchs; fabs; fstp c
    text = in_frame(f"{FLD_A} d9e0 d9e1 {FSTP_C}")
    assert "s_c = fabs(-s_8);" in text
    assert "double fabs(double);" in text


def test_a_float_inside_an_array_reads_at_its_own_type():
    # lea eax, [esp + 8]; fld dword ptr [esp + 0Ch]; fstp c
    text = in_frame(f"8d442408 d944240c {FSTP_C}")
    assert "s_c = *(float *)(s_8 + 4);" in text


def test_float_constant_is_an_extern():
    # fld dword ptr [D]; fstp c
    text = lift.lift_row(float_global("d905"), VA)
    assert f"extern char D_{FLOAT_GLOBAL:08x}[];" in text
    assert "*(float *)" in text
    assert not re.search(r"\d\.\d", text)


def test_a_double_constant_operates_through_its_extern():
    # fld a; fmul qword ptr [D]; fstp c
    text = lift.lift_row(float_global("dc0d", FLD_A), VA)
    assert "*(double *)" in text
    assert f"D_{FLOAT_GLOBAL:08x}" in text
    assert not re.search(r"\d\.\d", text)


def test_a_float_array_of_a_global_reads_as_an_element():
    # fld dword ptr [eax*4 + D]; fstp c
    text = lift.lift_row(float_global("d90485"), VA)
    assert f"s_c = ((float *)D_{FLOAT_GLOBAL:08x})[r_eax];" in text


def compare_row(compare: str, jump: str = "72") -> StubExe:
    """`compare; fnstsw ax; sahf; j<cc> +0` in a frame."""
    return stub_exe(f"{FRAME} {compare} dfe0 9e {jump}00 {UNFRAME}")


def test_x87_compare_drives_a_branch():
    # fld a; fcomp dword ptr [esp + 0Ch]; fnstsw ax; sahf; jb
    text = lift.lift_row(compare_row(f"{FLD_A} d85c240c"), VA)
    assert "if (s_8 < s_4) goto" in text
    assert "unsigned" not in text


def test_fcompp_compares_the_two_top_registers():
    # fld a; fld b; fcompp; fnstsw ax; sahf; jae: st(0) is b
    text = lift.lift_row(compare_row(f"{FLD_A} {FLD_B} ded9", "73"), VA)
    assert "if (s_4 >= s_8) goto" in text


def test_fcomp_of_a_register_pops_one():
    # fld a; fld b; fcomp st(1); fnstsw ax; sahf; jbe: a stays loaded past the block's end
    with pytest.raises(lift.Unliftable, match="x87: stack live across a block end"):
        lift.lift_row(compare_row(f"{FLD_A} {FLD_B} d8d9", "76"), VA)


def test_the_status_word_is_no_return_value():
    # the compare row writes ax through fnstsw and nothing else of eax
    assert lift.lift_row(compare_row(f"{FLD_A} d85c240c"), VA).startswith("\nvoid func_")


def test_the_status_word_is_nothing_else_can_read():
    # fld a; fcomp b; fnstsw ax; test ah, 41h; ret
    code = f"{FRAME} {FLD_A} d85c240c dfe0 f6c441 {UNFRAME}"
    with pytest.raises(lift.Unliftable, match="reg: eax read before any write"):
        lift.lift_row(stub_exe(code), VA)


def test_fnstsw_with_no_compare_keeps_its_refusal():
    with pytest.raises(lift.Unliftable, match="op: fnstsw"):
        lift.lift_row(stub_exe("dfe0 9e c3"), VA)


def test_sahf_with_no_status_word_keeps_its_refusal():
    with pytest.raises(lift.Unliftable, match="op: sahf"):
        lift.lift_row(stub_exe("9e c3"), VA)


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        ("d9e8", "op: fld1"),
        ("d9ee", "op: fldz"),
        ("d9c9", "op: fxch"),
        ("d9fa", "op: fsqrt"),
        ("db6c2408", "op: fld"),  # a ten-byte load
        ("df6c2408", "op: fild"),  # a qword integer load
    ],
)
def test_other_x87_forms_keep_their_refusal(code, reason):
    with pytest.raises(lift.Unliftable, match=reason):
        in_frame(f"{FLD_A} {code}")


def test_a_qword_fistp_keeps_its_refusal():
    with pytest.raises(lift.Unliftable, match="op: fistp"):
        in_frame(f"{FLD_A} df7c2404")


def test_a_pop_of_the_empty_stack_refuses():
    with pytest.raises(lift.Unliftable, match="x87: stack read before any load"):
        in_frame(FSTP_C)


def test_fstp_to_a_register_below_the_stack_refuses():
    # fld a; fstp st(1): nothing was loaded under a
    with pytest.raises(lift.Unliftable, match="x87: stack read before any load"):
        in_frame(f"{FLD_A} ddd9")


def test_a_stack_left_at_a_block_end_refuses():
    with pytest.raises(lift.Unliftable, match="x87: stack live across a block end"):
        in_frame(FLD_A)


# ---- holes ----

MOVSD = "a5"  # a form the converter does not take: esi and edi move
HOLED = f"b801000000 {MOVSD} b802000000 c3"  # mov eax, 1; movsd; mov eax, 2; ret
HOLE_AT = VA + 5


def with_holes(exe: StubExe) -> str:
    return lift.Lifter(exe, exe.rows[0], holes=True).lift()


def test_a_hole_keeps_the_lift_going():
    text = with_holes(stub_exe(HOLED))
    assert f"/* HOLE 0x{HOLE_AT:X}: op: movsd */" in text
    assert "return 2;" in text


def test_holes_stay_off_by_default():
    with pytest.raises(lift.Unliftable, match="op: movsd"):
        lift.lift_row(stub_exe(HOLED), VA)


def test_a_frame_refusal_is_never_a_hole():
    # push ebp; mov ebp, esp; pop ebp; ret
    with pytest.raises(lift.Unliftable, match="frame: ebp frame"):
        with_holes(stub_exe("55 89e5 5d c3"))


def test_a_decode_refusal_is_never_a_hole():
    # the row ends inside mov eax, imm32
    with pytest.raises(lift.Unliftable, match="decode: row does not decode to its end"):
        with_holes(stub_exe("b801"))


def test_a_jump_with_no_table_is_never_a_hole():
    with pytest.raises(lift.Unliftable, match=r"jump: indirect \(switch table\)"):
        with_holes(stub_exe(f"{table_jump()} c3"))


def test_the_mark_is_the_spelling_of_a_hole():
    assert lift.HOLE_MARK in with_holes(stub_exe(HOLED))
    assert lift.HOLE_MARK == "/* HOLE "


def test_each_register_a_hole_writes_reads_as_its_local():
    # movsd; mov eax, esi; ret
    text = with_holes(stub_exe(f"{MOVSD} 89f0 c3"))
    assert "int h_1000;" in text
    assert "return h_1000;" in text


def test_a_hole_that_writes_no_register_declares_nothing():
    # fld1 writes no general register: fld1; ret, the stack left behind is its own hole
    text = with_holes(stub_exe("d9e8 c3"))
    assert "op: fld1" in text
    assert "h_" not in text


def test_the_flags_do_not_survive_a_hole():
    # cmp eax, edx; movsd; je +0; ret: movsd may not have kept what je reads, so je is a hole too
    text = with_holes(stub_exe(f"39d0 {MOVSD} 7400 c3"))
    assert "jcc: no flag source" in text
    assert "if (" not in text


def test_a_stack_left_at_a_block_end_is_a_hole():
    assert "x87: stack live across a block end" in with_holes(
        stub_exe(f"{FRAME} {FLD_A} {UNFRAME}")
    )


def test_a_hole_appears_once_when_the_row_runs_twice():
    # lea eax, [esp + 8] takes an address, so the blocks run again with the array known
    text = with_holes(stub_exe(f"{FRAME} 8d442408 {MOVSD} {UNFRAME}"))
    assert text.count(lift.HOLE_MARK) == 1


def test_a_row_with_nothing_to_refuse_has_no_hole():
    exe = stub_exe("89d0 c3")
    assert with_holes(exe) == lift.lift_row(exe, VA)


# ---- the short hint ----

STORE = "89442408"  # mov [esp + 8], eax
READ_MOVSX = "0fbf442408"  # movsx eax, word ptr [esp + 8]


def test_short_hint_types_a_slot_read_only_as_a_word():
    assert "short s_8;" in in_frame(f"{STORE} {READ_MOVSX}")


def test_one_dword_read_keeps_the_slot_as_it_was():
    # the same, then mov edx, [esp + 8]
    text = in_frame(f"{STORE} {READ_MOVSX} 8b542408")
    assert "int s_8;" in text
    assert "short" not in text


def test_a_word_load_widened_by_cwde_is_a_sign_extending_read():
    # mov ax, word ptr [esp + 8]; cwde
    assert "short s_8;" in in_frame(f"{STORE} 668b442408 98")


def test_a_plain_word_load_is_no_sign_extending_read():
    # mov ax, word ptr [esp + 8]
    assert "int s_8;" in in_frame(f"{STORE} 668b442408")


def test_a_zero_extending_read_keeps_the_slot_as_it_was():
    # movsx eax, word ptr [esp + 8]; movzx edx, word ptr [esp + 8]
    assert "int s_8;" in in_frame(f"{STORE} {READ_MOVSX} 0fb7542408")


def test_a_float_read_keeps_the_slot_as_it_was():
    # movsx eax, word ptr [esp + 8]; fild dword ptr [esp + 8]; fstp c
    assert "int s_8;" in in_frame(f"{STORE} {READ_MOVSX} db442408 {FSTP_C}")


def test_a_slot_nothing_reads_keeps_its_type():
    assert "int s_8;" in in_frame(STORE)


def test_a_slot_that_turns_out_to_be_an_array_stays_one():
    # the word read comes before lea eax, [esp + 8], which the first run has not seen yet
    text = in_frame(f"{STORE} 0fbf542408 8d442408")
    assert "char s_8[8];" in text
    assert "short" not in text


# ---- the idiom check ----

# cmp eax, edx; jne T; mov eax, 1; jmp J; T: xor eax, eax; J: ret
BOOLEAN = "39d0 7507 b801000000 eb02 31c0 c3"
BRANCH_AT = VA + 2  # the conditional jump an idiom is named at


def idioms(code: str) -> list[str]:
    exe = stub_exe(code)
    return lift.Lifter(exe, exe.rows[0]).idioms()


def test_idiom_check_names_a_boolean_helper():
    assert idioms(BOOLEAN) == [f"0x{BRANCH_AT:X}: inlined boolean helper"]
    assert f"/* IDIOM 0x{BRANCH_AT:X}: inlined boolean helper */" in lift.lift_row(
        stub_exe(BOOLEAN), VA
    )


def test_a_boolean_helper_may_write_its_values_either_way_round():
    # cmp eax, edx; jne T; xor eax, eax; jmp J; T: mov eax, 1; J: ret
    assert len(idioms("39d0 7504 31c0 eb05 b801000000 c3")) == 1


def test_two_other_constants_are_no_boolean_helper():
    # cmp eax, edx; jne T; mov eax, 2; jmp J; T: xor eax, eax; J: ret
    assert idioms("39d0 7507 b802000000 eb02 31c0 c3") == []


def test_two_registers_are_no_boolean_helper():
    # cmp eax, edx; jne T; mov eax, 1; jmp J; T: xor edx, edx; J: ret
    assert idioms("39d0 7507 b801000000 eb02 31d2 c3") == []


def test_arms_that_do_not_join_are_no_boolean_helper():
    # cmp eax, edx; jne T; mov eax, 1; ret; T: xor eax, eax; ret
    assert idioms("39d0 7506 b801000000 c3 31c0 c3") == []


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("39d0 7e02 89d0 c3", "MIN"),  # cmp eax, edx; jle +2; mov eax, edx; ret
        ("39d0 7c02 89d0 c3", "MIN"),  # jl
        ("39d0 7602 89d0 c3", "MIN"),  # jbe
        ("39d0 7d02 89d0 c3", "MAX"),  # jge
        ("39d0 7f02 89d0 c3", "MAX"),  # jg
        ("39d0 7302 89d0 c3", "MAX"),  # jae
        ("39c2 7e02 89d0 c3", "MAX"),  # cmp edx, eax; jle +2; mov eax, edx: the compare swapped
    ],
)
def test_idiom_check_names_min_and_max(code, name):
    assert idioms(code) == [f"0x{BRANCH_AT:X}: {name} written out"]


def test_a_skip_of_two_moves_is_no_min_or_max():
    # cmp eax, edx; jle +4; mov eax, edx; mov ecx, edx; ret
    assert idioms("39d0 7e04 89d0 89d1 c3") == []


def test_a_move_of_something_else_is_no_min_or_max():
    # cmp eax, edx; jle +2; mov eax, ecx; ret
    assert idioms("39d0 7e02 89c8 c3") == []


def test_an_equality_skip_is_no_min_or_max():
    # cmp eax, edx; je +2; mov eax, edx; ret
    assert idioms("39d0 7402 89d0 c3") == []


def test_a_skip_with_no_compare_is_no_min_or_max():
    # test eax, eax; jle +2; mov eax, edx; ret
    assert idioms("85c0 7e02 89d0 c3") == []


def test_idioms_change_no_code(monkeypatch):
    # a draft is its idiom comments, then what it would be with none
    named = lift.lift_row(stub_exe(BOOLEAN), VA)
    clear_caches()
    monkeypatch.setattr(lift.Lifter, "idioms", lambda self: [])
    plain = lift.lift_row(stub_exe(BOOLEAN), VA)
    first, rest = named.split("\n", 1)
    assert first.startswith("/* IDIOM ")
    assert rest == plain


def test_a_row_with_no_idiom_has_no_comment():
    assert "IDIOM" not in lift.lift_row(stub_exe("89d0 c3"), VA)


# ---- statement order ----


def test_a_counted_loop_steps_once():
    # xor eax, eax; L: inc eax; dec edx; jne L; ret
    text = lift.lift_row(stub_exe("31c0 40 4a 75fc c3"), VA)
    assert "r_edx = r_edx - 1;" in text
    assert f"if (r_edx != 0) goto L{VA + 2:X};" in text


def test_a_jump_reads_the_variable_its_register_just_became():
    # dec edx; jne L; inc eax; L: mov eax, edx; ret
    text = lift.lift_row(stub_exe("4a 7501 40 89d0 c3"), VA)
    assert text.index("r_edx = r_edx - 1;") < text.index("if (r_edx != 0) goto")


def test_an_operand_overwritten_before_the_jump_compares_a_temporary():
    # cmp eax, edx; mov eax, 5; je L; mov eax, 6; L: ret. L is a merge, so r_eax = 5 comes first.
    text = lift.lift_row(stub_exe("39d0 b805000000 7405 b806000000 c3"), VA)
    order = ("t_0 = r_eax;", "r_eax = 5;", "if (t_0 == r_edx) goto")
    assert sorted(order, key=text.index) == list(order)


def test_both_operands_of_a_compare_share_the_temporary():
    # cmp eax, eax; mov eax, 5; je L; mov eax, 6; L: ret
    text = lift.lift_row(stub_exe("39c0 b805000000 7405 b806000000 c3"), VA)
    assert "if (t_0 == t_0) goto" in text
    assert "t_1" not in text


def test_a_flag_overwritten_before_a_store_keeps_its_temporary():
    # cmp eax, edx; mov eax, [ecx]; mov [ecx], edx; je L; inc eax; L: ret
    text = lift.lift_row(stub_exe("39d0 8b01 8911 7401 40 c3"), VA)
    assert text.index("t_0 = r_eax;") < text.index("r_eax = *(int *)")
    assert "if (t_0 == r_edx) goto" in text


def test_the_fall_through_reads_the_temporary_too():
    # cmp eax, edx; mov eax, 5; je L; jb M; inc eax; L: ret; M: ret. Both jumps read one compare.
    text = lift.lift_row(stub_exe("39d0 b805000000 7403 7202 40 c3 c3"), VA)
    assert "if (t_0 == r_edx) goto" in text
    assert "((unsigned)t_0) < ((unsigned)r_edx)" in text


def test_a_flag_written_again_keeps_no_temporary():
    # cmp eax, edx; mov eax, [ecx]; mov [ecx], edx; test eax, eax; je L; inc eax; L: ret
    assert "t_0" not in lift.lift_row(stub_exe("39d0 8b01 8911 85c0 7401 40 c3"), VA)


def test_a_flag_a_call_ends_keeps_no_temporary():
    # cmp eax, edx; mov eax, [ecx]; mov [ecx], edx; call f; ret
    callee = VA + ROW_SPACING
    exe = stub_exe(f"39d0 8b01 8911 {call_to(VA + 6, callee)} c3", "b801000000 c3")
    assert "t_0" not in lift.lift_row(exe, VA)


def test_an_operand_left_in_its_variable_still_compares():
    # cmp eax, edx; mov eax, 5; je L; ret; L: ret. No merge: r_eax keeps the value compared.
    assert "if (r_eax == r_edx) goto" in lift.lift_row(stub_exe("39d0 b805000000 7401 c3 c3"), VA)


def test_a_flag_nothing_reads_keeps_no_temporary():
    # cmp eax, edx; jne L; mov eax, 5; L: ret. The compare's flags reach the fall through unread.
    text = lift.lift_row(stub_exe("39d0 7505 b805000000 c3"), VA)
    assert "r_eax = 5;" in text
    assert "t_0" not in text


def test_a_list_walk_dereferences_once():
    # mov eax, [eax]; test eax, eax; je L; inc eax; L: ret
    text = lift.lift_row(stub_exe("8b00 85c0 7401 40 c3"), VA)
    assert text.count("*(int *)") == 1
    assert "if (r_eax == 0) goto" in text


def test_a_store_to_memory_is_what_the_jump_reads():
    # mov esi, eax; dec dword ptr [esi + 4]; jne L; inc eax; L: ret
    text = lift.lift_row(stub_exe("89c6 ff4e04 7501 40 c3"), VA)
    assert text.count(" - 1") == 1


def test_a_stored_value_is_read_after_the_flush():
    # mov eax, [eax]; mov [edx], eax; inc eax; ret
    text = lift.lift_row(stub_exe("8b00 8902 40 c3"), VA)
    assert "*(int *)((char *)r_edx) = r_eax;" in text


def test_a_call_argument_is_read_after_the_flush():
    # mov edx, [edx]; call f; mov eax, edx; ret
    callee = VA + ROW_SPACING
    exe = stub_exe(f"8b12 {call_to(VA + 2, callee)} 89d0 c3", "c3")
    assert f"func_{callee:08x}(r_eax, r_edx);" in lift.lift_row(exe, VA)


# ---- readers of an overwritten name ----


def test_a_copy_outlives_the_call_that_overwrites_eax():
    # mov ebx, eax; call f; add eax, ebx; ret
    callee = VA + ROW_SPACING
    exe = stub_exe(f"89c3 {call_to(VA + 2, callee)} 01d8 c3", "b801000000 c3")
    text = lift.lift_row(exe, VA)
    assert text.index("r_ebx = r_eax;") < text.index(f"r_eax = func_{callee:08x}(")
    assert "return r_eax + r_ebx;" in text


def test_an_argument_nothing_reads_later_stays_in_the_call():
    # mov ebx, eax; call f; ret: the call reads ebx, and its own statement overwrites eax after
    callee = VA + ROW_SPACING
    exe = stub_exe(f"89c3 {call_to(VA + 2, callee)} c3", "b801000000 c3")
    assert "r_ebx =" not in lift.lift_row(exe, VA)


def test_a_copy_of_the_node_survives_the_step_to_the_next():
    # mov ecx, eax; mov eax, [eax]; mov [edx], ecx; ret
    text = lift.lift_row(stub_exe("89c1 8b00 890a c3"), VA)
    assert text.index("r_ecx = r_eax;") < text.index("r_eax = *(int *)")
    assert "*(int *)((char *)r_edx) = r_ecx;" in text


def test_a_swap_across_a_merge_goes_through_a_temporary():
    # test ebx, ebx; je L; mov ecx, eax; mov eax, edx; mov edx, ecx; L: add eax, edx; ret
    text = lift.lift_row(stub_exe("85db 7406 89c1 89d0 89ca 01d0 c3"), VA)
    assert "int t_0;" in text
    order = ("t_0 = r_edx;", "r_edx = r_eax;", "r_eax = t_0;")
    assert sorted(order, key=text.index) == list(order)


def test_a_slot_read_outlives_the_store_to_the_slot():
    # mov eax, [esp + 8]; mov [esp + 8], edx
    text = in_frame("8b442408 89542408")
    assert text.index("r_eax = s_8;") < text.index("s_8 = r_edx;")
    assert "return r_eax;" in text


def test_a_flag_that_read_a_slot_keeps_it_past_the_store():
    # mov ecx, [esp + 8]; test ecx, ecx; mov [esp + 8], edx; je +0
    text = in_frame("8b4c2408 85c9 89542408 7400")
    assert text.index("t_0 = s_8;") < text.index("s_8 = r_edx;")
    assert "if (t_0 == 0) goto" in text


def test_a_pending_push_keeps_the_value_it_pushed():
    # inc ecx; push eax; mov eax, [eax]; mov [edx], ecx; call f; ret, f taking one stack argument
    callee = VA + ROW_SPACING
    exe = stub_exe(f"41 50 8b00 890a {call_to(VA + 6, callee)} c3", "b801000000 c20400")
    text = lift.lift_row(exe, VA)
    assert text.index("t_0 = r_eax;") < text.index("r_eax = *(int *)")
    assert ", t_0);" in text


def test_a_loaded_float_keeps_the_address_it_was_loaded_from():
    # fld dword ptr [eax]; mov eax, [edx]; mov [edx], ecx; fstp c
    text = in_frame(f"d900 8b02 890a {FSTP_C}")
    assert text.index("t_0 = r_eax;") < text.index("r_eax = *(int *)")
    assert "s_c = *(float *)((char *)t_0);" in text


def test_a_float_stored_over_its_own_slot_needs_no_temporary():
    # fld a; fadd dword ptr [esp + 0Ch]; fstp a
    text = in_frame(f"{FLD_A} d844240c d95c2408")
    assert "s_8 = s_8 + s_4;" in text
    assert "t_0" not in text


def test_a_float_kept_past_the_store_to_its_slot_reads_a_float_temporary():
    # fld a; fadd dword ptr [esp + 0Ch]; fst a; fstp c
    text = in_frame(f"{FLD_A} d844240c d9542408 {FSTP_C}")
    assert "float t_0;" in text
    assert "s_c = t_0 + s_4;" in text


def test_a_flag_on_a_copy_reads_the_variable_the_copy_became():
    # mov ebx, eax; mov eax, 5; test ebx, ebx; je L; mov eax, 6; L: add eax, ebx; ret
    text = lift.lift_row(stub_exe("89c3 b805000000 85db 7405 b806000000 01d8 c3"), VA)
    assert text.index("r_ebx = r_eax;") < text.index("r_eax = 5;")
    assert "if (r_ebx == 0) goto" in text


# ---- the census ----


def test_a_cold_census_gives_the_warm_draft():
    # call B; call D; xor eax, eax; ret. Nobody reads what D leaves in eax, so D is void.
    b, d = VA + ROW_SPACING, VA + 2 * ROW_SPACING
    exe = stub_exe(f"{call_to(VA, b)} {call_to(VA + 5, d)} 31c0 c3", "c3", "b801000000 c3")
    cold = lift.lift_row(exe, VA, {})
    assert lift.lift_row(exe, VA, {}) == cold
    assert f"void func_{d:08x}(void);" in cold


def test_the_census_asks_for_no_signatures():
    exe = stub_exe("c3")
    assert lift.result_used(exe) == (set(), set())


def census_file():
    return lift.CACHE_DIR / "result-used-stub.json"


@pytest.mark.parametrize(
    "bad",
    [
        '{"used": [',
        '{"called": []}',
        "[]",
        '{"used": 1, "called": 2}',
        '{"used": [[]], "called": []}',
    ],
    ids=["truncated", "wrong keys", "a list", "not lists", "unhashable"],
)
def test_a_bad_census_file_reads_as_no_census(bad):
    callee = VA + ROW_SPACING
    exe = stub_exe(f"{call_to(VA, callee)} c3", "c3")
    census_file().write_text(bad, encoding="utf-8")
    assert callee in lift.result_used(exe)[1]
    assert str(callee) in census_file().read_text(encoding="utf-8")


def test_a_failed_census_write_leaves_no_file(monkeypatch):
    def refuse(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(fileio.os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        lift.result_used(stub_exe("c3"))
    assert list(lift.CACHE_DIR.iterdir()) == []


def test_a_failed_census_build_keeps_the_demotion_on(monkeypatch):
    def crash(*_args, **_kwargs):
        raise RuntimeError("bug")

    with monkeypatch.context() as patch:
        patch.setattr(lift.Lifter, "prepare", crash)
        with pytest.raises(RuntimeError, match="bug"):
            lift.result_used(stub_exe("c3"))
    assert lift.result_used(stub_exe("c3")) is not None


# ---- pop and add esp ----


def test_a_pop_restores_what_was_pushed():
    # mov ecx, edx; push eax; mov eax, 1; pop eax; ret
    assert "return r_eax;" in lift.lift_row(stub_exe("89d1 50 b801000000 58 c3"), VA)


def test_add_esp_moves_esp_with_a_push_pending():
    # sub esp, 10h; push eax; call f; add esp, 4; mov eax, [esp]; add esp, 10h; ret
    callee = VA + ROW_SPACING
    code = f"83ec10 50 {call_to(VA + 4, callee)} 83c404 8b0424 83c410 c3"
    text = lift.lift_row(stub_exe(code, "c3"), VA)
    assert "return s_10;" in text
    assert "s_14" not in text


def test_add_esp_drops_the_pushes_it_releases():
    # mov eax, 1; push edx; push eax; add esp, 4; pop eax; ret: the pop finds edx's value
    assert "return r_edx;" in lift.lift_row(stub_exe("b801000000 52 50 83c404 58 c3"), VA)


def test_a_pop_of_nothing_pushed_refuses():
    # mov ecx, edx; pop eax; inc eax; ret
    with pytest.raises(lift.Unliftable, match="pop: value not pushed in the block"):
        lift.lift_row(stub_exe("89d1 58 40 c3"), VA)


def test_a_pop_of_a_register_the_prologue_did_not_save_refuses():
    # mov ecx, edx; pop eax; ret
    with pytest.raises(lift.Unliftable, match="pop: value not pushed in the block"):
        lift.lift_row(stub_exe("89d1 58 c3"), VA)


def test_a_pop_of_a_saved_register_read_later_refuses():
    # push ebx; mov ebx, 1; pop ebx; mov eax, ebx; ret
    with pytest.raises(lift.Unliftable, match="pop: value not pushed in the block"):
        lift.lift_row(stub_exe("53 bb01000000 5b 89d8 c3"), VA)


def test_epilogue_pops_restore_nothing_the_draft_shows():
    # push ebx; push ecx; mov eax, 1; pop ecx; pop ebx; ret
    assert "return 1;" in lift.lift_row(stub_exe("53 51 b801000000 59 5b c3"), VA)


def test_an_epilogue_may_end_in_a_tail_jump():
    # push esi; mov eax, 1; pop esi; jmp g
    callee = VA + ROW_SPACING
    jump = "e9" + (callee - (VA + 12)).to_bytes(4, "little", signed=True).hex()
    assert f"func_{callee:08x}(" in lift.lift_row(stub_exe(f"56 b801000000 5e {jump}", "c3"), VA)


# ---- cdq ----


def test_cdq_reaches_the_divide():
    # cdq; idiv ecx; ret
    assert "return r_eax / r_ecx;" in lift.lift_row(stub_exe("99 f7f9 c3"), VA)


def test_a_sign_made_by_sar_reaches_the_divide():
    # mov edx, eax; sar edx, 31; idiv ecx; ret
    assert "return r_eax / r_ecx;" in lift.lift_row(stub_exe("89c2 c1fa1f f7f9 c3"), VA)


@pytest.mark.parametrize(
    "code",
    [
        "99 31d0 29d0 c3",  # cdq; xor eax, edx; sub eax, edx; ret: abs
        "89c2 c1fa1f 01d0 c3",  # mov edx, eax; sar edx, 31; add eax, edx; ret
        "99 8911 c3",  # cdq; mov [ecx], edx; ret
        "99 85c9 7401 41 f7f9 c3",  # cdq; test ecx, ecx; je L; inc ecx; L: idiv ecx; ret
    ],
    ids=["abs", "sar", "store", "merge"],
)
def test_only_a_divide_reads_a_cdq(code):
    with pytest.raises(lift.Unliftable, match="op: cdq"):
        lift.lift_row(stub_exe(code), VA)


# ---- low parts ----


def test_a_low_read_of_a_wide_value_narrows_it():
    # call f; test al, al; sete al; ret
    callee = VA + ROW_SPACING
    exe = stub_exe(f"{call_to(VA, callee)} 84c0 0f94c0 c3", "b801000000 c3")
    assert "((unsigned char)r_eax) == 0" in lift.lift_row(exe, VA)


def test_a_word_read_of_a_wide_value_narrows_it():
    # mov eax, edx; cmp ax, 5; je +0; ret
    assert "if (((short)r_edx) == 5) goto" in lift.lift_row(stub_exe("89d0 6683f805 7400 c3"), VA)


def test_a_low_read_of_a_narrow_parameter_is_the_parameter():
    # test al, al; je +0; ret
    assert "if (r_eax == 0) goto" in lift.lift_row(stub_exe("84c0 7400 c3"), VA)


def test_a_low_read_of_a_constant_is_the_constant():
    # mov eax, 5; mov [edx], al; ret
    assert "((char *)r_edx) = 5;" in lift.lift_row(stub_exe("b805000000 8802 c3"), VA)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("89d0 0fb6c8 89c8 c3", "return (unsigned char)r_edx;"),  # movzx ecx, al
        ("89d0 0fbec8 89c8 c3", "return (signed char)r_edx;"),  # movsx ecx, al
        ("89d0 98 c3", "return (short)r_edx;"),  # cwde
    ],
)
def test_a_widening_read_casts_once(code, expected):
    # mov eax, edx; <widen>; ret
    assert expected in lift.lift_row(stub_exe(code), VA)


# ---- flags ----


@pytest.mark.parametrize(
    ("jump", "expected"),
    [
        ("77", "((unsigned)t_0) > ((unsigned)r_edx)"),  # ja
        ("72", "((unsigned)t_0) < ((unsigned)r_edx)"),  # jb
        ("74", "t_0 == r_edx"),  # je
        ("7c", "t_0 < r_edx"),  # jl
    ],
    ids=["ja", "jb", "je", "jl"],
)
def test_a_jump_after_a_sub_compares_its_operands(jump, expected):
    # sub eax, edx; j<cc> +0; ret
    assert f"if ({expected}) goto" in lift.lift_row(stub_exe(f"29d0 {jump}00 c3"), VA)


def test_a_sub_of_memory_keeps_its_result():
    # sub [ecx], edx; je +0; ret: the first operand is gone by the jump
    assert "if ((*(int *)((char *)r_ecx)) == 0) goto" in lift.lift_row(stub_exe("2911 7400 c3"), VA)


@pytest.mark.parametrize(
    "code",
    [
        "01d0 7700 c3",  # add eax, edx; ja +0; ret
        "01d0 7200 c3",  # add eax, edx; jb +0; ret
        "40 7600 c3",  # inc eax; jbe +0; ret: inc keeps the carry of whatever came before
        "2911 7700 c3",  # sub [ecx], edx; ja +0; ret
        "01d0 0f92c0 c3",  # add eax, edx; setb al; ret
    ],
    ids=["add ja", "add jb", "inc jbe", "sub memory", "add setb"],
)
def test_an_unsigned_condition_on_a_result_refuses(code):
    with pytest.raises(lift.Unliftable, match="jcc: carry of a result"):
        lift.lift_row(stub_exe(code), VA)


def test_an_unsigned_condition_on_a_test_reads_no_carry():
    # test eax, eax; ja +0; ret: test clears the carry, so this is a compare with zero
    assert "if (((unsigned)r_eax) > 0) goto" in lift.lift_row(stub_exe("85c0 7700 c3"), VA)


def test_not_changes_no_flag():
    # cmp eax, edx; not ecx; je +0; ret
    assert "if (r_eax == r_edx) goto" in lift.lift_row(stub_exe("39d0 f7d1 7400 c3"), VA)


def test_a_xor_of_a_register_with_itself_sets_the_flags():
    # cmp eax, edx; xor ecx, ecx; je +0; ret: the jump is always taken
    assert "if (0 == 0) goto" in lift.lift_row(stub_exe("39d0 31c9 7400 c3"), VA)


# ---- compares and constants ----


def compare_global(opcode: str, imm: str, jump: str) -> str:
    """`cmp <width> ptr [D], imm; j<cc> +0; ret`, with a fixup on the displacement."""
    field = VA + len(bytes.fromhex(opcode))
    disp = FLOAT_GLOBAL.to_bytes(FIELD_SIZE, "little").hex()
    code = f"{opcode} {disp} {imm} {jump}00 c3"
    return lift.lift_row(stub_exe(code, fixups=(data_fixup(field, FLOAT_GLOBAL),)), VA)


BYTE_COMPARE = "803d"
WORD_COMPARE = "66813d"
SHORT_WORD_COMPARE = "66833d"


@pytest.mark.parametrize(
    ("opcode", "imm", "jump", "read", "expected"),
    [
        (BYTE_COMPARE, "ff", "74", "signed char", "== -1"),  # je: a compare that can be true
        (BYTE_COMPARE, "ff", "7c", "signed char", "< -1"),  # jl
        (BYTE_COMPARE, "80", "72", "unsigned char", "< 128"),  # jb: no sign extension first
        (BYTE_COMPARE, "ff", "77", "unsigned char", "> 255"),  # ja
        (WORD_COMPARE, "0080", "73", "unsigned short", ">= 32768"),  # jae
        (WORD_COMPARE, "ffff", "75", "short", "!= -1"),  # jne
        (SHORT_WORD_COMPARE, "ff", "74", "short", "== -1"),  # je, the immediate sign-extended
        (SHORT_WORD_COMPARE, "ff", "76", "unsigned short", "<= 65535"),  # jbe, the same
    ],
)
def test_a_narrow_compare_reads_memory_as_its_condition_does(opcode, imm, jump, read, expected):
    text = compare_global(opcode, imm, jump)
    assert f"*({read} *)" in text
    assert f" {expected}) goto" in text


def test_a_setcc_is_the_condition_of_its_compare():
    # cmp byte ptr [D], 80h; setb al; and eax, 0FFh; ret
    disp = FLOAT_GLOBAL.to_bytes(FIELD_SIZE, "little").hex()
    code = f"803d {disp} 80 0f92c0 {MASK_EAX} c3"
    text = lift.lift_row(stub_exe(code, fixups=(data_fixup(VA + 2, FLOAT_GLOBAL),)), VA)
    assert "*(unsigned char *)" in text
    assert " < 128;" in text


def test_a_dword_compare_keeps_its_read():
    # cmp dword ptr [D], 5; jb +0; ret
    disp = FLOAT_GLOBAL.to_bytes(FIELD_SIZE, "little").hex()
    code = f"833d {disp} 05 7200 c3"
    text = lift.lift_row(stub_exe(code, fixups=(data_fixup(VA + 2, FLOAT_GLOBAL),)), VA)
    assert "*(int *)" in text


def test_a_byte_register_compare_keeps_the_whole_immediate():
    # mov eax, edx; cmp al, 0FFh; je +0; ret
    assert "((unsigned char)r_edx) == 255" in lift.lift_row(stub_exe("89d0 3cff 7400 c3"), VA)


def test_a_word_register_compare_is_a_signed_immediate():
    # mov eax, edx; cmp ax, 0FFFFh; je +0; ret
    assert "((short)r_edx) == -1" in lift.lift_row(stub_exe("89d0 6683f8ff 7400 c3"), VA)


def test_a_large_negative_compare_stays_signed():
    # cmp eax, -5000; jl +0; ret
    assert "if (r_eax < -5000) goto" in lift.lift_row(stub_exe("3d78ecffff 7c00 c3"), VA)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (5, "5"),
        (-1, "-1"),
        (-5000, "-5000"),
        (0xFFFFEC78, "-5000"),
        (65535, "65535"),
        (0x10000, "0x10000"),
        (0x7FFFFFFF, "0x7fffffff"),
        (-0x7FFFFFFF, "-2147483647"),
        (-0x80000000, "(-2147483647 - 1)"),
        (0x80000000, "(-2147483647 - 1)"),
    ],
)
def test_a_constant_prints_as_its_signed_value(value, text):
    assert lift.const(value).text == text


# ---- parameter types ----


@pytest.mark.parametrize(
    "code",
    [
        "88c2 8b08 c3",  # mov dl, al; mov ecx, [eax]; ret
        "88c2 8908 c3",  # mov dl, al; mov [eax], ecx; ret
        "88c2 8b0c82 c3",  # mov dl, al; mov ecx, [edx + eax*4]; ret
        "88c2 8d4801 c3",  # mov dl, al; lea ecx, [eax + 1]; ret
        "84c0 7402 8b00 c3",  # test al, al; je L; mov eax, [eax]; L: ret
        "84c0 7402 89d0 8b00 c3",  # test al, al; je L; mov eax, edx; L: mov eax, [eax]; ret
    ],
    ids=["base", "store base", "index", "lea", "next block", "one path written"],
)
def test_a_parameter_read_whole_anywhere_stays_wide(code):
    assert "int r_eax" in lift.lift_row(stub_exe(code), VA)


def test_a_parameter_written_before_a_later_block_stays_narrow():
    # test al, al; je L; ret; L: mov eax, 1; mov eax, [eax]; ret
    assert "unsigned char r_eax" in lift.lift_row(stub_exe("84c0 7401 c3 b801000000 8b00 c3"), VA)


def test_a_loop_of_narrow_reads_stays_narrow():
    # L: test al, al; jne L; ret
    assert "unsigned char r_eax" in lift.lift_row(stub_exe("84c0 75fc c3"), VA)


def test_a_word_parameter_takes_its_sign_from_its_own_reads():
    # movsx eax, ax; movzx ecx, dx; add eax, ecx; ret
    text = lift.lift_row(stub_exe("0fbfc0 0fb7ca 01c8 c3"), VA)
    assert "(short r_eax, unsigned short r_edx)" in text


# ---- what the excepts let through ----

BUGS = (AttributeError, StopIteration, RecursionError)


@pytest.mark.parametrize("bug", BUGS)
def test_a_bug_in_a_callee_is_no_unknown_signature(monkeypatch, bug):
    callee = VA + ROW_SPACING
    exe = stub_exe(f"{call_to(VA, callee)} c3", "c3")
    signature = lift.Lifter.signature

    def broken(self):
        if self.row.start == callee:
            raise bug("bug")
        return signature(self)

    monkeypatch.setattr(lift.Lifter, "signature", broken)
    with pytest.raises(bug):
        lift.Lifter(exe, exe.rows[0]).callee(callee)


@pytest.mark.parametrize("bug", BUGS)
def test_a_bug_in_a_row_is_no_shorter_census(monkeypatch, bug):
    def broken(*_args, **_kwargs):
        raise bug("bug")

    monkeypatch.setattr(lift.Lifter, "prepare", broken)
    with pytest.raises(bug):
        lift.result_used(stub_exe("c3"))


def test_a_row_the_census_cannot_read_is_left_out():
    # the bad row refuses, and the row beside it still counts
    callee = VA + 2 * ROW_SPACING
    exe = stub_exe(BAD_ROW, f"{call_to(VA + ROW_SPACING, callee)} c3", "c3")
    assert lift.result_used(exe)[1] == {callee}


# ---- a row that calls itself ----


def test_a_recursive_row_is_declared_by_its_definition_alone():
    # test al, al; je +5; call self; ret
    text = lift.lift_row(stub_exe(f"84c0 7405 {call_to(VA + 4, VA)} c3"), VA)
    assert f"func_{VA:08x}(r_eax);" in text
    assert text.count(f"func_{VA:08x}(") == 2  # the definition and the call, no prototype


def test_another_callee_keeps_its_prototype():
    # call f; ret
    callee = VA + ROW_SPACING
    text = lift.lift_row(stub_exe(f"{call_to(VA, callee)} c3", "b801000000 c3"), VA)
    assert f"int func_{callee:08x}(void);" in text


# ---- slot widths ----


@pytest.mark.parametrize(
    "code",
    [
        "88442408 8b442408",  # mov byte ptr [esp + 8], al; mov eax, [esp + 8]
        "6689442408 8b442408",  # mov word ptr [esp + 8], ax; mov eax, [esp + 8]
        f"{FLD_A} dd442408 {FSTP_C} {FSTP_C}",  # fld dword, then fld qword, of the slot at 8
    ],
    ids=["byte", "word", "float"],
)
def test_a_slot_read_wider_than_its_declaration_refuses(code):
    with pytest.raises(lift.Unliftable, match="stack: slot read at two widths"):
        in_frame(code)


def test_a_slot_read_narrower_than_its_declaration_keeps_it():
    # mov [esp + 8], eax; movzx eax, byte ptr [esp + 8]
    assert "int s_8;" in in_frame("89442408 0fb6442408")


def test_the_short_hint_covers_a_word_read_of_a_byte_store():
    # mov byte ptr [esp + 8], al; movsx eax, word ptr [esp + 8]
    assert "short s_8;" in in_frame(f"88442408 {READ_MOVSX}")


def test_a_saved_register_is_no_local():
    # push ebx; mov eax, [esp]; pop ebx; ret
    with pytest.raises(lift.Unliftable, match="stack: saved register slot"):
        lift.lift_row(stub_exe("53 8b0424 5b c3"), VA)


def test_a_store_to_a_saved_register_refuses():
    # push ebx; mov [esp], eax; pop ebx; ret
    with pytest.raises(lift.Unliftable, match="stack: saved register slot"):
        lift.lift_row(stub_exe("53 890424 5b c3"), VA)
