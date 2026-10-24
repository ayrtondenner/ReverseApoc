"""Tests for the capstone recursive-descent function discovery (tools/reverseapoc/discover.py).

Every byte string here is made up for the test: hand-assembled instructions patched into the
synthetic LE of tests/conftest.py, never bytes copied from a game executable. The synthetic code
object is object 1 at 0x10000 (pages filled with 0x11, which decodes as a run of `adc`), the
data object is object 2 at 0x20000.
"""

from __future__ import annotations

import json
import re
import struct

import pytest

from conftest import build_le_image, fixup_record, requires_capstone
from reverseapoc import discover as disc
from reverseapoc.discover import Discovery, discover
from reverseapoc.le import LE

CODE = 0x10000  # base of the synthetic code object (object 1)
DATA = 0x20000  # base of the synthetic data object (object 2)
RET = b"\xc3"
OFF32 = 7  # LE fixup source type: 32-bit offset
NO_FIXUPS = [b"", b"", b""]


@pytest.fixture(autouse=True)
def _capstone():
    requires_capstone()


def call(at: int, target: int) -> bytes:
    """`call target` (E8 rel32) placed at `at`."""
    return b"\xe8" + struct.pack("<i", target - (at + 5))


def make_le(
    patches: dict[int, bytes],
    *,
    entry: int = 0x100,
    fixups: list[bytes] | None = None,
    objects: list[tuple[int, int, int, int, int]] | None = None,
) -> LE:
    """A synthetic LE whose entry point is object 1 + `entry`."""
    return LE(
        build_le_image(
            fixups=NO_FIXUPS if fixups is None else fixups,
            entry=(1, entry),
            patches=patches,
            objects=objects,
        ).data
    )


def test_call_chain():
    a, b, c = CODE + 0x100, CODE + 0x200, CODE + 0x300
    le = make_le({a: call(a, b) + RET, b: call(b, c) + RET, c: RET})
    found = discover(le)
    assert found.starts == (a, b, c)
    assert found.evidence[a] == frozenset({"entry"})
    assert found.evidence[b] == frozenset({"call"})
    assert found.evidence[c] == frozenset({"call"})
    assert found.decoded_bytes == 6 + 6 + 1
    assert found.ignored_seeds == 0


def test_runtime_seed():
    a, r = CODE + 0x100, CODE + 0x500
    le = make_le({a: RET, r: RET})
    found = discover(le, runtime_starts=[r])
    assert found.starts == (a, r)
    assert found.evidence[r] == frozenset({"runtime"})


def test_fixup_seed():
    """An off32 fixup in the data object (a function-pointer table) seeds its target_va. The raw
    field holds the object-relative target_off (0x400), as wlink writes it; it is not a start."""
    a, f = CODE + 0x100, CODE + 0x400
    pointer = 0x10  # data object offset of the function pointer
    fixups = [b"", b"", fixup_record(OFF32, pointer, 1, f - CODE, off32=True)]
    le = make_le({a: RET, f: RET, DATA + pointer: struct.pack("<I", f - CODE)}, fixups=fixups)
    found = discover(le)
    assert found.starts == (a, f)
    assert found.evidence[f] == frozenset({"fixup"})
    assert f - CODE not in found.evidence


def jmp_table(table_off: int) -> bytes:
    """`jmp dword ptr [eax*4 + table]` (FF 24 85 disp32) with the raw displacement holding the
    object-relative table offset, as wlink leaves it."""
    return b"\xff\x24\x85" + struct.pack("<I", table_off)


def table_fixups(sources: list[int], targets: list[int]) -> bytes:
    """off32 fixups from object-1 page offsets `sources` to object-1 VAs `targets`."""
    return b"".join(
        fixup_record(OFF32, src, 1, dst - CODE, off32=True)
        for src, dst in zip(sources, targets, strict=True)
    )


def test_jump_table():
    """`jmp [eax*4+T]` through three code-to-code off32 fixups: T is one data-in-code range, the
    case labels belong to the same function (not starts), and a call from a case is followed."""
    a, table, d = CODE + 0x100, CODE + 0x200, CODE + 0x400
    cases = [CODE + 0x300, CODE + 0x310, CODE + 0x320]
    disp = a + 3  # the displacement field of the jmp
    entries = [table, table + 4, table + 8]
    fixups = [
        table_fixups([disp - CODE, *(e - CODE for e in entries)], [table, *cases]),
        b"",
        b"",
    ]
    patches = {
        a: jmp_table(table - CODE),
        **{e: struct.pack("<I", c - CODE) for e, c in zip(entries, cases, strict=True)},
        cases[0]: RET,
        cases[1]: call(cases[1], d) + RET,
        cases[2]: RET,
        d: RET,
    }
    found = discover(make_le(patches, fixups=fixups))
    assert found.jump_tables == ((table, table + 12),)
    assert found.starts == (a, d)
    assert found.evidence[d] == frozenset({"call"})
    assert found.decoded_bytes == 7 + 1 + 6 + 1 + 1


def test_evidence_merges():
    """A start that is both called and runtime-seeded carries both kinds of evidence."""
    a, b = CODE + 0x100, CODE + 0x200
    le = make_le({a: call(a, b) + RET, b: RET})
    found = discover(le, runtime_starts=[b])
    assert found.evidence[b] == frozenset({"call", "runtime"})


def test_report_has_counts_only():
    a, b = CODE + 0x100, CODE + 0x200
    found = discover(make_le({a: call(a, b) + RET, b: RET}))
    assert isinstance(found, Discovery)
    text = found.format()
    assert "2" in text
    assert f"{a:x}" not in text.lower()
    report = json.loads(json.dumps(found.to_json()))
    assert report["starts"] == 2
    assert report["decoded_bytes"] == 7
    assert report["ignored_seeds"] == 0
    assert report["jump_tables"] == 0
    assert report["evidence"] == {"call": 1, "entry": 1, "fixup": 0, "runtime": 0}
    for shown in (text, repr(found), json.dumps(found.to_json())):
        assert "0x" not in shown.lower()
        assert re.search(r"\d{5,}", shown) is None  # no address in decimal either


def test_errors_carry_no_address_in_assertions():
    """DiscoverError is checked by type only: its message may name a synthetic address."""
    a = CODE + 0x100
    le = make_le({a: RET})
    found = discover(le)
    outside = Discovery((DATA,), {DATA: frozenset({"runtime"})}, 0, (), 0)
    with pytest.raises(disc.DiscoverError):
        disc.ends(outside, le)
    no_code = [(0x1800, CODE, 0x2043, 1, 2), (0x3000, DATA, 0x2043, 3, 1)]
    with pytest.raises(disc.DiscoverError):
        discover(make_le({a: RET}, objects=no_code))
    assert disc.ends(found, le)[a] == CODE + 0x1800  # no padding after the ret: next limit


# Task 2: leading tables, inline data, the D-07 end rule and the object edges.

FILLER_MOV = b"\x89\xc0"  # mov eax, eax: Watcom alignment filler
XOR_EAX = b"\x31\xc0"  # xor eax, eax: not terminal


def small_code(vsize: int) -> list[tuple[int, int, int, int, int]]:
    """A code object of `vsize` bytes at CODE (bytes past it load as zero) and the data object."""
    return [(vsize, CODE, 0x2045, 1, 2), (0x3000, DATA, 0x2043, 3, 1)]


def test_leading_table():
    """A table directly before a function entry is a jump-table range ending at that entry and
    not the tail of the previous function."""
    a, table, b = CODE + 0x100, CODE + 0x108, CODE + 0x110
    cases = [CODE + 0x200, CODE + 0x210]
    entries = [table, table + 4]
    fixups = [table_fixups([b + 3 - CODE, *(e - CODE for e in entries)], [table, *cases]), b"", b""]
    patches = {
        a: call(a, b) + RET + FILLER_MOV,
        **{e: struct.pack("<I", c - CODE) for e, c in zip(entries, cases, strict=True)},
        b: jmp_table(table - CODE),
        cases[0]: RET,
        cases[1]: RET,
    }
    le = make_le(patches, fixups=fixups)
    found = discover(le)
    assert found.jump_tables == ((table, b),)
    assert found.starts == (a, b)
    assert disc.ends(found, le)[a] == a + 6


def test_inline_data():
    """An LE fixup site at an instruction start ends the path: the field is not decoded (here it
    would decode as a call to a function nothing else reaches)."""
    a, unreached = CODE + 0x100, CODE + 0x200
    site = a + 1
    fixups = [fixup_record(OFF32, site - CODE, 2, 0), b"", b""]
    le = make_le({a: b"\x90" + call(site, unreached), unreached: RET}, fixups=fixups)
    found = discover(le)
    assert found.starts == (a,)
    assert found.decoded_bytes == 1


def test_function_ends():
    """D-07 end rule: the first padding byte (filler or zero) after a terminal instruction, else
    the next start; a function that falls through has no ret and ends at the next start."""
    a, b, c = CODE, CODE + 0xC, CODE + 0xE
    vsize = 0x20
    patches = {
        a: call(a, b) + call(a + 5, c) + RET + b"\x90",
        b: XOR_EAX,  # falls through into c
        c: RET + bytes(vsize - 0xF),  # zero padding to the object end
    }
    le = make_le(patches, entry=0, objects=small_code(vsize))
    found = discover(le)
    assert found.starts == (a, b, c)
    assert found.decoded_bytes == 11 + 2 + 1
    assert disc.ends(found, le) == {a: a + 0xB, b: c, c: c + 1}


def test_ends_leave_gap_code_outside():
    """ret, padding, then decodable code with no start evidence before the next start: the first
    function ends at the padding and the trailing code is a gap no range covers."""
    a, gap, b = CODE, CODE + 0x8, CODE + 0x10
    vsize = 0x20
    patches = {
        a: call(a, b) + RET + b"\x90\x90",
        gap: XOR_EAX + RET + bytes(b - gap - 3),
        b: RET + bytes(vsize - 0x11),
    }
    le = make_le(patches, entry=0, objects=small_code(vsize))
    found = discover(le)
    assert found.starts == (a, b)
    assert found.decoded_bytes == 6 + 1
    end_of = disc.ends(found, le)
    assert end_of == {a: a + 6, b: b + 1}
    assert not any(start <= gap < end for start, end in end_of.items())


def test_seed_outside_code_object():
    a = CODE + 0x100
    found = discover(make_le({a: RET}), runtime_starts=[DATA + 0x10])
    assert found.starts == (a,)
    assert found.ignored_seeds == 1


def test_function_at_object_edges():
    """A function at the object base and one whose ret is the object's last byte."""
    a, b = CODE, CODE + 0xD
    patches = {a: call(a, b) + RET + b"\x90" * 7, b: XOR_EAX + RET}
    le = make_le(patches, entry=0, objects=small_code(0x10))
    found = discover(le)
    assert found.starts == (a, b)
    assert found.decoded_bytes == 6 + 3
    assert disc.ends(found, le) == {a: a + 6, b: CODE + 0x10}


def test_no_read_past_object_edges():
    """A function running off the end of the object stops there: the zero bytes after the
    object (which decode as `add [eax], al`) are never decoded."""
    a, b = CODE, CODE + 0xE
    patches = {a: call(a, b) + RET + b"\x90" * 8, b: XOR_EAX}
    le = make_le(patches, entry=0, objects=small_code(0x10))
    found = discover(le)
    assert found.starts == (a, b)
    assert found.decoded_bytes == 6 + 2
    assert disc.ends(found, le)[b] == CODE + 0x10
