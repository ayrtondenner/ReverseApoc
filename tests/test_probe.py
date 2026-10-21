"""Idiom counters and calibration bookkeeping of tools/reverseapoc/probe.py (CID-03, D-10).

Every input here is a short x86 encoding written as a literal in this file and annotated with its
mnemonics, never bytes taken from a compiler object or the game.
"""

from __future__ import annotations

from reverseapoc.probe import IDIOMS, count_idioms

# cmp al,5; sete al; and eax,0FFh; ret
SETCC_AND = b"\x3c\x05\x0f\x94\xc0\x25\xff\x00\x00\x00\xc3"
SETCC_AND_START = 2  # offset of the 0F of sete inside SETCC_AND
SETCC_AND_END = 10  # one past the last 00 of the and immediate
# setne al; movzx eax,al
SETCC_MOVZX = b"\x0f\x95\xc0\x0f\xb6\xc0"


def test_idioms_order():
    assert IDIOMS == (
        "setcc_and",
        "setcc_movzx",
        "movsd_unrolled",
        "rep_movsd_small",
        "loop_rotated",
        "loop_top_tested",
        "switch_ascending",
        "switch_descending",
    )


def test_setcc_forms():
    counts = count_idioms(SETCC_AND)
    assert list(counts) == list(IDIOMS)
    assert counts["setcc_and"] == 1
    assert counts["setcc_movzx"] == 0
    counts = count_idioms(SETCC_MOVZX)
    assert counts["setcc_movzx"] == 1
    assert counts["setcc_and"] == 0


def test_mask_and_exclude_block_matches():
    # one masked byte anywhere inside the match drops it: first, middle and last byte
    for offset in (SETCC_AND_START, SETCC_AND_START + 3, SETCC_AND_END - 1):
        assert count_idioms(SETCC_AND, mask=frozenset({offset}))["setcc_and"] == 0
    # a masked byte just outside the match does not
    for offset in (SETCC_AND_START - 1, SETCC_AND_END):
        assert count_idioms(SETCC_AND, mask=frozenset({offset}))["setcc_and"] == 1
    base = 0x10000
    # an excluded VA range [start, end) overlapping one byte of the match drops it ...
    first = base + SETCC_AND_START
    last = base + SETCC_AND_END - 1
    assert count_idioms(SETCC_AND, base=base, exclude=[(first, first + 1)])["setcc_and"] == 0
    assert count_idioms(SETCC_AND, base=base, exclude=[(last, last + 1)])["setcc_and"] == 0
    assert count_idioms(SETCC_AND, base=base, exclude=[(base - 4, first + 1)])["setcc_and"] == 0
    # ... and a range ending at the match's first byte or starting after its last does not
    assert count_idioms(SETCC_AND, base=base, exclude=[(base, first)])["setcc_and"] == 1
    assert count_idioms(SETCC_AND, base=base, exclude=[(last + 1, last + 9)])["setcc_and"] == 1


def test_empty_and_fully_excluded():
    assert count_idioms(b"") == dict.fromkeys(IDIOMS, 0)
    code = SETCC_AND + SETCC_MOVZX
    base = 0x20000
    assert count_idioms(code, base=base, exclude=[(base, base + len(code))]) == dict.fromkeys(
        IDIOMS, 0
    )
    # two ranges that together cover the code exclude everything as well
    split = base + 5
    assert count_idioms(
        code, base=base, exclude=[(base, split), (split, base + len(code))]
    ) == dict.fromkeys(IDIOMS, 0)
