"""Tests for the capstone recursive-descent function discovery (tools/reverseapoc/discover.py).

Every byte string here is made up for the test: hand-assembled instructions patched into the
synthetic LE of tests/conftest.py, never bytes copied from a game executable. The synthetic code
object is object 1 at 0x10000 (pages filled with 0x11, which decodes as a run of `adc`), the
data object is object 2 at 0x20000.
"""

from __future__ import annotations

import json
import struct

import pytest

from conftest import build_le_image, fixup_record, requires_capstone
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
