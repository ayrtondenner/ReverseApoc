# Derived from KKND-Decomp tools/build_kknd.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""The relocation check (SPL-09): our compiled OMF function against its functions.csv row in the
original LE, in flat VA space, with no ELF and no objdiff (research Pattern 7).

objdiff is not the gate. Spike 005 (plant P3) showed it scores 100.0 when only the second
relocation of one instruction (`mov dword [A], imm32 B`) names the wrong target. This check is
independent of it and catches that case:

1. Length: our public's size equals the row's end - start.
2. Fields: `ours` are the VAs our OMF fixups cover (offset mapped to start + offset - off);
   `theirs` are the LE fixup fields inside the row.
3. Bytes: every byte outside the fields of both sides is equal.
4. Each of our fixups lands on the original target:
   - self-relative: have = F + 4 + int32(original field), want = address_of(symbol) + stored +
     displacement, and the LE has no fixup at F (a rel32 call is not an LE fixup);
   - segment-relative to an extern: an off32 LE fixup at F whose target_va == want.
5. Reverse coverage: every LE fixup field in the row is one of ours. The raw LE field holds the
   target offset, so a constant of ours equal to it would otherwise pass the byte compare.

Problems carry VAs, symbol names and addresses, never byte values.
"""

from __future__ import annotations

import struct
from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .functions import FunctionRow
from .le import SRC_OFF32, SRC_SIZE, Fixup
from .omf import LOC_OFFSET32, OMFFixup, Segment
from .symbols import SymbolTable

FIELD_SIZE = SRC_SIZE[SRC_OFF32]  # every field the check accepts: offset32 / rel32
_MAX_LE_FIELD = max(SRC_SIZE.values())
_INT32 = struct.Struct("<i")
_ADDRESS_MASK = 0xFFFFFFFF  # VAs and targets are compared modulo 2**32
_TARGET_EXTERN = "extern"


class RelocError(ValueError):
    """The inputs of a check do not describe one function."""


@dataclass(frozen=True)
class RelocResult:
    """The verdict of one function. `ours` and `theirs` are field start VAs; `problems` are
    `0xVVVVVVVV: <what>` strings sorted by VA. Addresses and names only, never bytes."""

    ok: bool
    problems: tuple[str, ...]
    ours: frozenset[int]
    theirs: frozenset[int]

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "problems": list(self.problems),
            "ours": sorted(self.ours),
            "theirs": sorted(self.theirs),
        }


def _va(va: int) -> str:
    return f"0x{va:08X}"


@dataclass(frozen=True)
class _Pair:
    segment: Segment
    off: int
    size: int
    row: FunctionRow
    flat: bytes
    symbols: SymbolTable
    theirs: Mapping[int, Fixup]  # LE fixups whose field overlaps the row, by src_va

    def va(self, offset: int) -> int:
        """The VA of our segment offset `offset`."""
        return self.row.start + offset - self.off

    def stored(self, fx: OMFFixup) -> int:
        return _INT32.unpack_from(self.segment.data, fx.offset)[0]

    def original(self, va: int) -> int:
        return _INT32.unpack_from(self.flat, va)[0]


def _le_fields(fixups: Sequence[Fixup], lo: int, hi: int) -> Iterator[Fixup]:
    """LE fixups (sorted by src_va, as le.fixups() returns them) whose field overlaps [lo, hi)."""
    first = bisect_left(fixups, lo - _MAX_LE_FIELD + 1, key=lambda fx: fx.src_va)
    for fx in fixups[first:]:
        if fx.src_va >= hi:
            return
        if fx.src_va + fx.size > lo:
            yield fx


def _our_fixups(pair: _Pair) -> Iterator[OMFFixup]:
    """Our fixups whose field overlaps the public [off, off + size)."""
    for fx in pair.segment.fixups:
        if fx.offset < pair.off + pair.size and fx.offset + fx.size > pair.off:
            yield fx


def _length(pair: _Pair) -> Iterator[str]:
    """Rule 1: equal length."""
    length = pair.row.end - pair.row.start
    if pair.size != length:
        at = pair.row.start + min(pair.size, length)
        yield f"{_va(at)}: length differs: ours {pair.size} bytes, original {length} bytes"


def _masked(pair: _Pair, ours: Sequence[OMFFixup]) -> set[int]:
    """Every VA a field of either side covers."""
    covered = {pair.va(fx.offset) + i for fx in ours for i in range(fx.size)}
    covered.update(fx.src_va + i for fx in pair.theirs.values() for i in range(fx.size))
    return covered


def _bytes(pair: _Pair, masked: set[int]) -> Iterator[str]:
    """Rule 3: every byte outside the fields of both sides is equal."""
    data, flat, start = pair.segment.data, pair.flat, pair.row.start
    differing = [
        start + i
        for i in range(pair.size)
        if start + i not in masked and data[pair.off + i] != flat[start + i]
    ]
    if differing:
        yield (
            f"{_va(differing[0])}: first of {len(differing)} differing bytes outside the "
            "relocated fields"
        )


def _target(pair: _Pair, fx: OMFFixup) -> int:
    return pair.symbols.address_of(fx.target_name)


def _self_relative(pair: _Pair, field: int, fx: OMFFixup, want: int) -> Iterator[str]:
    """Rule 4, self-relative: the original rel32 lands on the same target, with no LE fixup."""
    if field in pair.theirs:
        yield (
            f"{_va(field)}: {fx.target_name}: a self-relative fixup where the original has an "
            "LE fixup"
        )
        return
    have = (field + FIELD_SIZE + pair.original(field)) & _ADDRESS_MASK
    if have != want:
        yield (
            f"{_va(field)}: {fx.target_name} resolves to {_va(want)}, "
            f"the original lands on {_va(have)}"
        )


def _segment_relative(pair: _Pair, field: int, fx: OMFFixup, want: int) -> Iterator[str]:
    """Rule 4, segment-relative: an off32 LE fixup at the field with the same target."""
    le = pair.theirs.get(field)
    if le is None or le.src_va != field:
        yield f"{_va(field)}: {fx.target_name}: the original has no LE fixup here"
        return
    if le.kind != SRC_OFF32:
        yield f"{_va(field)}: {fx.target_name}: the original LE fixup is {le.kind_name}, not off32"
        return
    if le.target_va != want:
        yield (
            f"{_va(field)}: {fx.target_name} resolves to {_va(want)}, "
            f"the original targets {_va(le.target_va)}"
        )


def _fixup(pair: _Pair, fx: OMFFixup) -> Iterator[str]:
    """Rule 4 for one of our fixups."""
    field = pair.va(fx.offset)
    if fx.location != LOC_OFFSET32:
        yield f"{_va(field)}: {fx.target_name}: fixup location {fx.location} is not offset32"
        return
    if fx.target_kind != _TARGET_EXTERN:
        yield f"{_va(field)}: {fx.target_name}: fixup target {fx.target_kind} is not supported"
        return
    want = (_target(pair, fx) + pair.stored(fx) + fx.displacement) & _ADDRESS_MASK
    rule = _segment_relative if fx.segment_relative else _self_relative
    yield from rule(pair, field, fx, want)


def _reverse_coverage(pair: _Pair, ours: set[int]) -> Iterator[str]:
    """Rule 5: every LE fixup field in the row is one of ours."""
    for va, fx in pair.theirs.items():
        if va not in ours:
            yield (
                f"{_va(va)}: the original has an {fx.kind_name} LE fixup here and ours has "
                "none (a constant where the original has an address)"
            )


def check_function(
    segment: Segment,
    *,
    off: int,
    size: int,
    row: FunctionRow,
    flat: bytes,
    fixups: Sequence[Fixup],
    symbols: SymbolTable,
) -> RelocResult:
    """Check our public [off, off + size) of `segment` against `row` of the original. `flat` is
    le.load_flat(relocate=False) and `fixups` le.fixups(), sorted by src_va."""
    theirs = {fx.src_va: fx for fx in _le_fields(fixups, row.start, row.end)}
    pair = _Pair(segment, off, size, row, flat, symbols, theirs)
    length = list(_length(pair))
    ours = list(_our_fixups(pair))
    fields = {pair.va(fx.offset) for fx in ours}
    if length:
        return RelocResult(False, tuple(length), frozenset(fields), frozenset(theirs))
    problems = [
        *_bytes(pair, _masked(pair, ours)),
        *(problem for fx in ours for problem in _fixup(pair, fx)),
        *_reverse_coverage(pair, fields),
    ]
    return RelocResult(not problems, tuple(sorted(problems)), frozenset(fields), frozenset(theirs))
