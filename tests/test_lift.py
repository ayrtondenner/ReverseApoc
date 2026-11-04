"""lift.py on hand-written encodings and a stub EXE. Every encoding is written here, never game
bytes. The lifter reads five things of an EXE: `flat`, `rows`, `fixups`, `symbols` and `stem`.
"""

from __future__ import annotations

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
