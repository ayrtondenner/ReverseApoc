"""relocs.check_function: the relocation check of our OMF function against its original in the LE,
in flat VA space, without ELF or objdiff (SPL-09). Every byte, name and address is made up
(tests/relocpair.py)."""

from __future__ import annotations

import re

import pytest

from conftest import fixup_record
from relocpair import (
    CALL_FIELD,
    CODE_BASE,
    CONST_INDEX,
    GOOD_ORIGINAL,
    GOOD_OURS,
    GOOD_ROW,
    LOAD_FIELD,
    TEXT_INDEX,
    absolute,
    call,
    game_row,
    good_original,
    good_segment,
    le_off32,
    original,
    our_segment,
    table,
    to_segment,
)
from reverseapoc.relocs import RelocError, RelocResult, check_function

# A dump of hex bytes ("e8 0b 00", "e80b0000") or a bytes repr: no problem may hold one.
_BYTE_DUMP = re.compile(r"\\x[0-9a-fA-F]{2}|\b(?:[0-9a-f]{2} ){2,}|\b(?:[0-9a-f]{2}){3,}\b")
GOOD_EXTERNS = ["func_00010010_", "_D_00020004"]


def check(segment, row, orig, symbols=None, *, off=0, size=None):
    return check_function(
        segment,
        off=off,
        size=len(GOOD_OURS) if size is None else size,
        row=row,
        flat=orig.flat,
        fixups=orig.fixups,
        symbols=symbols or table(row),
    )


def problems_of(result: RelocResult) -> tuple[str, ...]:
    """The problems of a failed check, each checked to start with a VA and carry no bytes."""
    assert not result.ok
    assert result.problems
    for problem in result.problems:
        assert _BYTE_DUMP.search(problem) is None, problem
        assert re.match(r"0x[0-9A-F]{8}: ", problem), problem
    return result.problems


def test_good_pair_passes():
    result = check(good_segment(), GOOD_ROW, good_original())
    assert isinstance(result, RelocResult)
    assert result.ok, result.problems
    assert result.problems == ()
    assert result.theirs == frozenset({LOAD_FIELD})
    assert result.ours == result.theirs | {CALL_FIELD}
    assert result.to_json() == {
        "ok": True,
        "problems": [],
        "ours": [CALL_FIELD, LOAD_FIELD],
        "theirs": [LOAD_FIELD],
    }


# ---- the negative suite (SPL-13) ----------------------------------------------------------------


def test_wrong_call_target():
    wrong = ["func_00010020_", "_D_00020004"]
    segment = our_segment(GOOD_OURS, [call(1, 1), absolute(6, 2)], wrong)
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original()))
    assert problem.startswith(f"0x{CALL_FIELD:08X}: ")
    assert "func_00010020_" in problem


# mov dword [0x20004], offset 0x20010; ret. Both 4-byte fields are relocated, back to back.
STORE_ORIGINAL = bytes.fromhex("c705" "04000000" "10000000" "c3")  # raw fields = target offsets
STORE_OURS = bytes.fromhex("c705" "00000000" "00000000" "c3")
STORE_ROW = game_row(CODE_BASE, CODE_BASE + len(STORE_ORIGINAL))
FIRST_FIELD, SECOND_FIELD = CODE_BASE + 2, CODE_BASE + 6


def store_original():
    fields = le_off32(FIRST_FIELD, 0x4) + le_off32(SECOND_FIELD, 0x10)
    return original({CODE_BASE: STORE_ORIGINAL}, page1=fields)


def store_segment(second: str):
    return our_segment(STORE_OURS, [absolute(2, 1), absolute(6, 2)], ["_D_00020004", second])


def test_adjacent_fields_are_checked_independently():
    result = check(store_segment("_D_00020010"), STORE_ROW, store_original(), size=11)
    assert result.ok, result.problems
    assert result.ours == result.theirs == {FIRST_FIELD, SECOND_FIELD}


def test_wrong_second_relocation():
    """Spike 005 plant P3: objdiff scores this pair 100.0. The check must fail it."""
    result = check(store_segment("_D_00020020"), STORE_ROW, store_original(), size=11)
    (problem,) = problems_of(result)  # the second field only; the first is fine
    assert problem.startswith(f"0x{SECOND_FIELD:08X}: ")
    assert "_D_00020020" in problem


def test_missing_fixup():
    """Our code holds the LE field's raw target offset as a plain constant, with no fixup."""
    segment = our_segment(GOOD_OURS[:6] + GOOD_ORIGINAL[6:], [call(1, 1)], ["func_00010010_"])
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original()))
    assert problem.startswith(f"0x{LOAD_FIELD:08X}: ")
    assert "ours has none" in problem


@pytest.mark.parametrize("local", ["CONST", "CONST2", "_DATA", "_BSS"])
def test_local_segment_reference(local):
    fixups = [call(1, 1), to_segment(6, CONST_INDEX)]
    segment = our_segment(GOOD_OURS, fixups, ["func_00010010_"], local=local)
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original()))
    assert problem.startswith(f"0x{LOAD_FIELD:08X}: {local}: ")
    assert "local segment reference, move data to an extern D_ symbol" in problem


def test_length_mismatch():
    longer = GOOD_OURS + bytes.fromhex("90")
    segment = our_segment(longer, [call(1, 1), absolute(6, 2)], GOOD_EXTERNS)
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original(), size=len(longer)))
    assert problem.startswith(f"0x{GOOD_ROW.end:08X}: ")
    assert "length" in problem


def test_differing_byte():
    changed = GOOD_OURS[:-1] + bytes.fromhex("90")  # nop where the original returns
    segment = our_segment(changed, [call(1, 1), absolute(6, 2)], GOOD_EXTERNS)
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original()))
    assert problem.startswith(f"0x{GOOD_ROW.end - 1:08X}: ")


def test_unknown_symbol():
    segment = our_segment(GOOD_OURS, [call(1, 1), absolute(6, 2)], ["helper_", "_D_00020004"])
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original()))
    assert problem == f"0x{CALL_FIELD:08X}: unknown symbol helper_"


def test_self_relative_fixup_over_an_le_fixup_fails():
    segment = our_segment(GOOD_OURS, [call(1, 1), call(6, 2)], GOOD_EXTERNS)
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original()))
    assert problem.startswith(f"0x{LOAD_FIELD:08X}: _D_00020004: ")


def test_le_fixup_must_be_off32():
    sel16 = fixup_record(2, LOAD_FIELD - CODE_BASE, 2)
    orig = original({CODE_BASE: GOOD_ORIGINAL}, page1=sel16)
    (problem,) = problems_of(check(good_segment(), GOOD_ROW, orig))
    assert problem.startswith(f"0x{LOAD_FIELD:08X}: _D_00020004: ")
    assert "sel16" in problem


def test_our_field_crossing_the_public_end_fails():
    fixups = [call(1, 1), absolute(6, 2), absolute(9, 2)]
    segment = our_segment(GOOD_OURS + bytes(4), fixups, GOOD_EXTERNS)
    (problem,) = problems_of(check(segment, GOOD_ROW, good_original()))
    assert problem.startswith(f"0x{CODE_BASE + 9:08X}: ")
    assert "crosses" in problem


# ---- references to our own _TEXT ---------------------------------------------------------------

FILLER = bytes.fromhex("90909090")  # the public before ours in the same segment


def test_own_segment_absolute_reference_resolves():
    """mov eax, offset <our own entry>: a segment-relative fixup to our own _TEXT. The public
    sits at segment offset 4, so the segment's VA is start - 4."""
    ours = bytes.fromhex("b8" "04000000" "c3")  # stored = the label's segment offset
    orig_code = bytes.fromhex("b8" "00000000" "c3")  # raw field = target offset of obj1:0
    row = game_row(CODE_BASE, CODE_BASE + len(ours))
    orig = original({CODE_BASE: orig_code}, page1=le_off32(CODE_BASE + 1, 0x0, obj=1))
    publics = [("other_", 0), ("func_00010000_", len(FILLER))]
    segment = our_segment(FILLER + ours, [to_segment(5, TEXT_INDEX)], publics=publics)
    result = check(segment, row, orig, off=len(FILLER), size=len(ours))
    assert result.ok, result.problems


def test_own_segment_call_resolves():
    """call <static function right after ours>: a self-relative fixup to our own _TEXT."""
    ours = bytes.fromhex("e8" "06000000" "c3")  # stored = the callee's segment offset
    orig_code = bytes.fromhex("e8" "01000000" "c3")  # rel32 to start + 6
    row = game_row(CODE_BASE, CODE_BASE + len(ours))
    publics = [("func_00010000_", 0), ("static_", 6)]
    fixups = [to_segment(1, TEXT_INDEX, relative=True)]
    segment = our_segment(ours + bytes.fromhex("c3"), fixups, publics=publics)
    result = check(segment, row, original({CODE_BASE: orig_code}), size=len(ours))
    assert result.ok, result.problems


def test_own_segment_reference_to_the_wrong_label_fails():
    ours = bytes.fromhex("e8" "07000000" "c3")
    row = game_row(CODE_BASE, CODE_BASE + len(ours))
    orig = original({CODE_BASE: bytes.fromhex("e8" "01000000" "c3")})
    segment = our_segment(ours + bytes(2), [to_segment(1, TEXT_INDEX, relative=True)])
    (problem,) = problems_of(check(segment, row, orig, size=len(ours)))
    assert problem.startswith(f"0x{CODE_BASE + 1:08X}: _TEXT ")


# ---- edges ---------------------------------------------------------------------------------------


def test_straddler_passes():
    """P3: an off32 LE field crossing the page boundary inside the function is one field."""
    start = 0x10FFD  # mov eax,[0x20040] with its field at 0x10FFE..0x11001; ret
    ours = bytes.fromhex("a1" "00000000" "c3")
    first, second = bytes.fromhex("a1" "4000"), bytes.fromhex("0000" "c3")
    page1 = fixup_record(7, 0xFFE, 2, 0x40, off32=True)
    page2 = fixup_record(7, -2, 2, 0x40, off32=True)  # the same field, listed on page 2 too
    orig = original({start: first, start + len(first): second}, page1=page1, page2=page2)
    row = game_row(start, start + len(ours))
    segment = our_segment(ours, [absolute(1, 1)], ["_D_00020040"])
    result = check(segment, row, orig, size=len(ours))
    assert result.ok, result.problems
    assert result.theirs == {start + 1}


def test_no_relocations():
    code = bytes.fromhex("31c0" "c3")  # xor eax,eax; ret
    row = game_row(CODE_BASE, CODE_BASE + len(code))
    result = check(our_segment(code), row, original({CODE_BASE: code}), size=len(code))
    assert result.ok, result.problems
    assert result.ours == result.theirs == frozenset()


def test_zero_size_public_is_refused():
    with pytest.raises(RelocError, match="size"):
        check(good_segment(), GOOD_ROW, good_original(), size=0)


def test_zero_length_row_is_refused():
    with pytest.raises(RelocError, match="row"):
        check(good_segment(), game_row(CODE_BASE, CODE_BASE), good_original())


def test_public_past_the_segment_end_is_refused():
    with pytest.raises(RelocError, match="segment"):
        check(good_segment(), GOOD_ROW, good_original(), off=1)


def test_problems_sorted():
    wrong = ["func_00010020_", "_D_00020020"]
    forward = our_segment(GOOD_OURS, [call(1, 1), absolute(6, 2)], wrong)
    backward = our_segment(GOOD_OURS, [absolute(6, 2), call(1, 1)], wrong)
    a = problems_of(check(forward, GOOD_ROW, good_original()))
    b = problems_of(check(backward, GOOD_ROW, good_original()))
    assert a == b
    assert [p[:10] for p in a] == [f"0x{CALL_FIELD:08X}", f"0x{LOAD_FIELD:08X}"]
