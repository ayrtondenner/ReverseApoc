"""land: our checked function bytes, the original kept at every relocated field on either side,
spliced into the EXE, and its SHA-1 compared with the manifest (SPL-10). Every byte, name and
address is made up (tests/relocpair.py)."""

from __future__ import annotations

from conftest import write_manifest
from relocpair import (
    CALL_FIELD,
    GOOD_ORIGINAL,
    GOOD_OURS,
    GOOD_ROW,
    good_original,
    good_segment,
    table,
)
from reverseapoc.land import LandedFunction, land
from reverseapoc.le import LE
from reverseapoc.relocs import check_function
from reverseapoc.targets import load_manifest

FIELD = 4


def checked(orig, row=GOOD_ROW, ours=GOOD_OURS, segment=None):
    result = check_function(
        segment or good_segment(), off=0, size=len(ours), row=row, flat=orig.flat,
        fixups=orig.fixups, symbols=table(row),
    )  # fmt: skip
    assert result.ok, result.problems
    return LandedFunction(row, ours, result)


def test_good_pair_lands_to_the_original(tmp_path):
    orig = good_original()
    (target,) = load_manifest(write_manifest(tmp_path / "m.toml", {"SYNTH.EXE": orig.data}))

    result = land(orig.le, [checked(orig)], expected_sha1=target.sha1)

    assert result.ok, result.format()
    assert result.sha1 == target.sha1
    assert result.data == orig.data
    landed = LE(result.data).load_flat(relocate=False)
    # Pitfall 2: the call field holds the original displacement, not our placeholder
    call = slice(CALL_FIELD, CALL_FIELD + FIELD)
    assert landed[call] == GOOD_ORIGINAL[1:5]
    assert landed[call] != GOOD_OURS[1:5]
