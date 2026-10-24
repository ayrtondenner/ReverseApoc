"""land: our checked function bytes, the original kept at every relocated field on either side,
spliced into the EXE, and its SHA-1 compared with the manifest (SPL-10). Every byte, name and
address is made up (tests/relocpair.py)."""

from __future__ import annotations

import hashlib
import json

import pytest

from conftest import write_manifest
from relocpair import (
    CALL_FIELD,
    CODE_BASE,
    GOOD_ORIGINAL,
    GOOD_OURS,
    GOOD_ROW,
    LOAD_FIELD,
    game_row,
    good_original,
    good_segment,
    le_off32,
    original,
    our_segment,
    table,
)
from reverseapoc import land as land_module
from reverseapoc.land import LandedFunction, LandError, LandResult, build_patch, land, write_landed
from reverseapoc.le import LE
from reverseapoc.relocs import RelocResult, check_function
from reverseapoc.splice import SpliceError, splice
from reverseapoc.targets import load_manifest

FIELD = 4
NEXT_CODE = bytes.fromhex("31c0" "c3")  # xor eax,eax; ret: touches the good pair's end
NEXT_ROW = game_row(GOOD_ROW.end, GOOD_ROW.end + len(NEXT_CODE))
FAR_START = CODE_BASE + 0x100
FAR_CODE = bytes.fromhex("40" "c3")  # inc eax; ret
FAR_ROW = game_row(FAR_START, FAR_START + len(FAR_CODE))


def checked(orig, row=GOOD_ROW, ours=GOOD_OURS, segment=None):
    result = check_function(
        segment or good_segment(), off=0, size=len(ours), row=row, flat=orig.flat,
        fixups=orig.fixups, symbols=table(row),
    )  # fmt: skip
    assert result.ok, result.problems
    return LandedFunction(row, ours, result)


def three_functions():
    """The good pair, a function touching its end, and one further on, all in one image."""
    patches = {CODE_BASE: GOOD_ORIGINAL + NEXT_CODE, FAR_START: FAR_CODE}
    orig = original(patches, page1=le_off32(LOAD_FIELD, 0x4))
    good = checked(orig)
    nxt = checked(orig, NEXT_ROW, NEXT_CODE, our_segment(NEXT_CODE))
    far = checked(orig, FAR_ROW, FAR_CODE, our_segment(FAR_CODE))
    return orig, good, nxt, far


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def forged(row, ours, *, fields=frozenset()):
    """A function whose relocation result claims ok whatever its bytes are."""
    return LandedFunction(row, ours, RelocResult(True, (), frozenset(fields), frozenset()))


def test_good_pair_lands_to_the_original(tmp_path):
    orig = good_original()
    (target,) = load_manifest(write_manifest(tmp_path / "m.toml", {"SYNTH.EXE": orig.data}))

    result = land(orig.le, [checked(orig)], expected_sha1=target.sha1)

    assert result.ok, result.format()
    assert result.sha1 == target.sha1
    assert result.data == orig.data
    assert result.first_difference is None
    landed = LE(result.data).load_flat(relocate=False)
    # Pitfall 2: the call field holds the original displacement, not our placeholder
    call = slice(CALL_FIELD, CALL_FIELD + FIELD)
    assert landed[call] == GOOD_ORIGINAL[1:5]
    assert landed[call] != GOOD_OURS[1:5]


def test_build_patch_keeps_the_original_at_both_sides_fields():
    orig = good_original()
    patch = build_patch(checked(orig), orig.flat)
    assert patch == GOOD_ORIGINAL  # the call field (ours) and the load field (both sides)


def test_refuses_a_failed_check(monkeypatch):
    orig = good_original()
    verdict = RelocResult(False, ("0x00010001: wrong target",), frozenset(), frozenset())
    failed = LandedFunction(GOOD_ROW, GOOD_OURS, verdict)

    def no_splice(*args, **kwargs):
        raise AssertionError("land spliced although a check failed")

    monkeypatch.setattr(land_module, "splice", no_splice)
    with pytest.raises(LandError, match=GOOD_ROW.name):
        land(orig.le, [failed], expected_sha1=sha1(orig.data))
    with pytest.raises(LandError, match=GOOD_ROW.name):
        build_patch(failed, orig.flat)


def test_refuses_bytes_of_the_wrong_length():
    orig = good_original()
    with pytest.raises(LandError, match="bytes"):
        build_patch(forged(GOOD_ROW, GOOD_OURS + b"\x00"), orig.flat)


def test_refuses_a_field_outside_the_row():
    orig = good_original()
    with pytest.raises(LandError, match="outside"):
        build_patch(forged(GOOD_ROW, GOOD_OURS, fields={GOOD_ROW.end}), orig.flat)


def test_no_functions():
    orig = good_original()
    result = land(orig.le, [], expected_sha1=sha1(orig.data))
    assert result.ok
    assert result.data == splice(orig.le, {}).data
    assert result.landed == ()
    assert result.masked == 0


def test_order_independent():
    orig, good, _, far = three_functions()
    a = land(orig.le, [good, far], expected_sha1=sha1(orig.data))
    b = land(orig.le, [far, good], expected_sha1=sha1(orig.data))
    assert a.ok and b.ok
    assert (a.data, a.sha1, a.landed) == (b.data, b.sha1, b.landed)
    assert a.landed == (GOOD_ROW.start, FAR_START)


def test_adjacent_functions():
    orig, good, nxt, _ = three_functions()
    assert good.row.end == nxt.row.start
    result = land(orig.le, [nxt, good], expected_sha1=sha1(orig.data))
    assert result.ok, result.format()
    assert result.landed == (GOOD_ROW.start, NEXT_ROW.start)


def test_overlapping_patches_are_refused_by_splice():
    orig = good_original()
    inner = game_row(GOOD_ROW.start + 8, GOOD_ROW.end)
    whole = forged(GOOD_ROW, GOOD_ORIGINAL)
    tail = forged(inner, GOOD_ORIGINAL[8:])
    with pytest.raises(SpliceError, match="overlap"):
        land(orig.le, [whole, tail], expected_sha1=sha1(orig.data))


def test_two_functions_at_one_start_are_refused():
    orig = good_original()
    whole = forged(GOOD_ROW, GOOD_ORIGINAL)
    with pytest.raises(LandError, match=f"0x{GOOD_ROW.start:08X}"):
        land(orig.le, [whole, whole], expected_sha1=sha1(orig.data))


def test_mutated_byte_changes_the_sha1():
    """The SHA-1 gate is independent of the check: a forged ok result does not land a wrong byte."""
    orig = good_original()
    good = checked(orig)
    changed = GOOD_OURS[:-1] + bytes.fromhex("90")
    mutated = LandedFunction(GOOD_ROW, changed, good.reloc)
    result = land(orig.le, [mutated], expected_sha1=sha1(orig.data))
    assert not result.ok
    assert result.first_difference == GOOD_ROW.end - 1
    assert f"0x{GOOD_ROW.end - 1:08X}" in result.format()


def test_land_result_json_holds_addresses_counts_and_sha1s_only():
    orig = good_original()
    result = land(orig.le, [checked(orig)], expected_sha1=sha1(orig.data))
    data = result.to_json()
    assert data == {
        "ok": True,
        "sha1": sha1(orig.data),
        "expected_sha1": sha1(orig.data),
        "landed": [GOOD_ROW.start],
        "functions": 1,
        "masked_fields": 1,
        "first_difference": None,
    }
    json.dumps(data)  # plain JSON data


def test_format():
    orig = good_original()
    ok = land(orig.le, [checked(orig)], expected_sha1=sha1(orig.data))
    assert ok.format().startswith("OK ")
    assert sha1(orig.data) in ok.format()
    bad = LandResult(orig.data, sha1(orig.data), "0" * 40, (GOOD_ROW.start,), 1, GOOD_ROW.start)
    assert bad.format().startswith("MISMATCH ")
    assert f"0x{GOOD_ROW.start:08X}" in bad.format()


def test_write_landed(tmp_path):
    orig_dir = tmp_path / "orig"
    orig_dir.mkdir()
    source = orig_dir / "SYNTH.EXE"
    orig = good_original()
    source.write_bytes(orig.data)
    result = land(orig.le, [checked(orig)], expected_sha1=sha1(orig.data))

    out = tmp_path / "build" / "SYNTH.EXE"
    write_landed(result, out, orig_dir=orig_dir, source=source)
    assert out.read_bytes() == result.data
    write_landed(result, out, orig_dir=orig_dir, source=source)  # an existing output is replaced
    assert sorted(p.name for p in out.parent.iterdir()) == ["SYNTH.EXE"]  # no temp file left


def test_write_landed_refuses_orig_and_the_source(tmp_path):
    orig_dir = tmp_path / "orig"
    orig_dir.mkdir()
    orig = good_original()
    result = land(orig.le, [], expected_sha1=sha1(orig.data))
    with pytest.raises(LandError, match="orig"):
        write_landed(result, orig_dir / "OUT.EXE", orig_dir=orig_dir, source=orig_dir / "X.EXE")
    source = tmp_path / "elsewhere" / "SYNTH.EXE"
    source.parent.mkdir()
    source.write_bytes(orig.data)
    with pytest.raises(LandError, match="same file"):
        write_landed(result, source, orig_dir=orig_dir, source=source)
    assert source.read_bytes() == orig.data
