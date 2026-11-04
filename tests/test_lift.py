"""lift.py on hand-written encodings and a stub EXE. Every encoding is written here, never game
bytes. The lifter reads five things of an EXE: `flat`, `rows`, `fixups`, `symbols` and `stem`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from reverseapoc import lift
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
    # cmp eax, 1; ja DEFAULT; and eax, 0FFFFh; jmp [eax*4 + table]
    mask = "25ffff0000"
    jump_at = VA + 5 + 5
    first = jump_at + JUMP_SIZE
    default = first + 6
    code = f"83f801 77{default - (VA + 5):02x} {mask} {table_jump()} b801000000 c3 b803000000 c3"
    text = lift.lift_row(with_table(stub_exe(code), (first, first), jump_at), VA)
    assert f"default: goto L{default:X};" in text
    assert "switch (r_eax & 65535) {" in text
    assert "if (" not in text


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


def test_an_operand_overwritten_before_the_jump_never_prints():
    # cmp eax, edx; mov eax, 5; je L; mov eax, 6; L: ret. L is a merge, so r_eax = 5 comes first.
    with pytest.raises(lift.Unliftable, match="flags: operand reassigned before the jump"):
        lift.lift_row(stub_exe("39d0 b805000000 7405 b806000000 c3"), VA)


def test_an_operand_left_in_its_variable_still_compares():
    # cmp eax, edx; mov eax, 5; je L; ret; L: ret. No merge: r_eax keeps the value compared.
    assert "if (r_eax == r_edx) goto" in lift.lift_row(stub_exe("39d0 b805000000 7401 c3 c3"), VA)


def test_a_flag_nothing_reads_refuses_nothing():
    # cmp eax, edx; jne L; mov eax, 5; L: ret. The compare's flags reach the fall through unread.
    assert "r_eax = 5;" in lift.lift_row(stub_exe("39d0 7505 b805000000 c3"), VA)


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
