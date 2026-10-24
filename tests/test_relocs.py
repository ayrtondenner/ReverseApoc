"""relocs.check_function: the relocation check of our OMF function against its original in the LE,
in flat VA space, without ELF or objdiff (SPL-09). Every byte, name and address is made up
(tests/relocpair.py)."""

from __future__ import annotations

from relocpair import (
    CALL_FIELD,
    GOOD_OURS,
    GOOD_ROW,
    LOAD_FIELD,
    good_original,
    good_segment,
    table,
)
from reverseapoc.relocs import RelocResult, check_function


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
