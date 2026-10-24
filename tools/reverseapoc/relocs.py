# Derived from KKND-Decomp tools/build_kknd.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""The relocation check (SPL-09): our compiled OMF function against its functions.csv row in the
original LE, in flat VA space, with no ELF and no objdiff (research Pattern 7).

objdiff is not the gate. Spike 005 (plant P3) showed it scores 100.0 when only the second
relocation of one instruction (`mov dword [A], imm32 B`) names the wrong target. This check is
independent of objdiff and fails that case:

1. Length: our public's size equals the row's end - start (`_length`).
2. Fields: `ours` are the VAs our OMF fixups cover (segment offset mapped to start + offset - off);
   `theirs` are the LE fixup fields inside the row.
3. Bytes: every byte outside the fields of both sides is equal (`_bytes`).
4. Each of our fixups lands on the original target `want`:
   - an extern: want = address_of(symbol) + stored + displacement (symbols.py);
   - our own `_TEXT` at segment offset t = stored + displacement (`_own_segment`): inside the
     checked public, want = start + (t - off), its own row; anywhere else, t must lie in one of
     `own_publics`, our unit's other publics with the original row each sits at, and want = that
     row's start + (t - the public's offset). Without such an entry the field is refused, never
     resolved by assuming our whole `_TEXT` sits in the original as in our object. The caller
     owes the map: it builds `own_publics` from the unit's units.csv and functions.csv rows
     (05-17 `check`, 05-18);
   then by the fixup's kind:
   - self-relative: have = F + 4 + int32(original field), and the LE has no fixup at F (a rel32
     call is not an LE fixup) (`_self_relative`);
   - segment-relative: an off32 LE fixup at F whose target_va == want (`_segment_relative`);
   - another segment of our module (CONST, CONST2, _DATA, _BSS) cannot be checked against the
     original's layout and fails (`_local_segment`); an unknown symbol fails with SymbolError's
     message.
5. Reverse coverage: every LE fixup field in the row is one of ours (`_reverse_coverage`). The
   raw LE field holds the target offset, so a constant of ours equal to it would otherwise pass
   the byte compare.

A page-straddling LE field is one Fixup from le.fixups(), checked by its VA like any other.
Problems are `0xVVVVVVVV: <what>` strings sorted by VA, the same for any order of our fixups.
They carry VAs, symbol names, addresses and counts, never byte values.
"""

from __future__ import annotations

import struct
from bisect import bisect_left, bisect_right
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .functions import FunctionRow
from .le import SRC_OFF32, SRC_SIZE, Fixup
from .omf import LOC_OFFSET32, OMFFixup, Segment
from .symbols import SymbolError, SymbolTable

FIELD_SIZE = SRC_SIZE[SRC_OFF32]  # every field the check accepts: offset32 / rel32
_MAX_LE_FIELD = max(SRC_SIZE.values())
_INT32 = struct.Struct("<i")
_ADDRESS_MASK = 0xFFFFFFFF  # VAs and targets are compared modulo 2**32
_TARGET_EXTERN = "extern"
_TARGET_SEGMENT = "segment"
LOCAL_SEGMENT_PROBLEM = "local segment reference, move data to an extern D_ symbol"


class RelocError(ValueError):
    """The inputs of a check do not describe one function."""


@dataclass(frozen=True)
class OwnPublic:
    """Another public of our unit's `_TEXT`: [offset, offset + size) in our segment, and the
    start VA of the functions.csv row it matches in the original."""

    name: str
    offset: int
    size: int
    start: int


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
    own_publics: tuple[OwnPublic, ...]  # sorted by offset

    def va(self, offset: int) -> int:
        """The VA of our segment offset `offset`."""
        return self.row.start + offset - self.off

    def inside(self, fx: OMFFixup) -> bool:
        return self.off <= fx.offset and fx.offset + fx.size <= self.off + self.size

    def stored(self, fx: OMFFixup) -> int:
        return _INT32.unpack_from(self.segment.data, fx.offset)[0]

    def original(self, va: int) -> int:
        return _INT32.unpack_from(self.flat, va)[0]


def _check_inputs(segment: Segment, off: int, size: int, row: FunctionRow, flat: bytes) -> None:
    if size <= 0:
        raise RelocError(f"{row.name}: public size {size} is not positive")
    if row.end <= row.start:
        raise RelocError(f"{row.name}: zero-length row [{_va(row.start)}, {_va(row.end)})")
    if off < 0 or off + size > len(segment.data):
        raise RelocError(
            f"{row.name}: public [{off:#x}, {off + size:#x}) lies outside segment "
            f"{segment.name} ({len(segment.data)} bytes)"
        )
    if row.end > len(flat):
        raise RelocError(f"{row.name}: row ends at {_va(row.end)}, past the image")


def _check_own_publics(own_publics: Sequence[OwnPublic], segment: Segment) -> None:
    for public in own_publics:
        end = public.offset + public.size
        if public.size <= 0 or public.offset < 0 or end > len(segment.data):
            raise RelocError(
                f"own public {public.name}: [{public.offset:#x}, {end:#x}) is empty or lies "
                f"outside segment {segment.name}"
            )


def _le_fields(fixups: Sequence[Fixup], lo: int, hi: int) -> Iterator[Fixup]:
    """LE fixups whose field overlaps [lo, hi). `fixups` must be sorted by src_va; check_function
    sorts them, so a caller's order never matters."""
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


# ---- one helper per rule ----


def _length(pair: _Pair) -> Iterator[str]:
    """Rule 1: equal length, in bytes."""
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
    """Rule 3: every byte in [start, end) outside the fields of both sides is equal."""
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


def _containing(publics: Sequence[OwnPublic], t: int) -> OwnPublic | None:
    """The public with the largest offset <= t, if t lies inside it."""
    index = bisect_right(publics, t, key=lambda public: public.offset) - 1
    if index < 0 or t >= publics[index].offset + publics[index].size:
        return None
    return publics[index]


def _own_segment(pair: _Pair, field: int, fx: OMFFixup) -> tuple[str, int] | str:
    """Rule 4, our own `_TEXT`: (label, want) through the checked public or `own_publics`, or
    the refusal when the target's original row is unknown."""
    t = (pair.stored(fx) + fx.displacement) & _ADDRESS_MASK
    label = f"{fx.target_name}+{t:#x}"
    if pair.off <= t < pair.off + pair.size:
        return label, pair.va(t)
    public = _containing(pair.own_publics, t)
    if public is None:
        return (
            f"{_va(field)}: {fx.target_name}: own _TEXT target {t:#x} outside {pair.row.name} "
            "needs the unit's public-to-row map"
        )
    return f"{label} ({public.name})", (public.start + t - public.offset) & _ADDRESS_MASK


def _local_segment(field: int, fx: OMFFixup) -> str:
    """Rule 4, another segment of our module: the original cannot be compared, so it fails."""
    return f"{_va(field)}: {fx.target_name}: {LOCAL_SEGMENT_PROBLEM}"


def _want(pair: _Pair, field: int, fx: OMFFixup) -> tuple[str, int] | str:
    """(label, the VA our fixup targets), or the problem that stops checking this field."""
    if fx.target_kind == _TARGET_SEGMENT:
        if fx.target_index == pair.segment.index:
            return _own_segment(pair, field, fx)
        return _local_segment(field, fx)
    if fx.target_kind != _TARGET_EXTERN:
        return f"{_va(field)}: {fx.target_name}: fixup target {fx.target_kind} is not supported"
    try:
        base = pair.symbols.address_of(fx.target_name)
    except SymbolError as exc:
        return f"{_va(field)}: {exc}"
    return fx.target_name, (base + pair.stored(fx) + fx.displacement) & _ADDRESS_MASK


def _self_relative(pair: _Pair, field: int, name: str, want: int) -> Iterator[str]:
    """Rule 4, self-relative: the original rel32 lands on the same target, with no LE fixup."""
    if field in pair.theirs:
        yield (
            f"{_va(field)}: {name}: a self-relative fixup where the original has an "
            "LE fixup"
        )
        return
    have = (field + FIELD_SIZE + pair.original(field)) & _ADDRESS_MASK
    if have != want:
        yield (
            f"{_va(field)}: {name} resolves to {_va(want)}, "
            f"the original lands on {_va(have)}"
        )


def _segment_relative(pair: _Pair, field: int, name: str, want: int) -> Iterator[str]:
    """Rule 4, segment-relative: an off32 LE fixup at the field with the same target."""
    le = pair.theirs.get(field)
    if le is None:
        yield f"{_va(field)}: {name}: the original has no LE fixup here"
        return
    if le.kind != SRC_OFF32:
        yield f"{_va(field)}: {name}: the original LE fixup is {le.kind_name}, not off32"
        return
    if le.target_va != want:
        yield (
            f"{_va(field)}: {name} resolves to {_va(want)}, "
            f"the original targets {_va(le.target_va)}"
        )


def _fixup(pair: _Pair, fx: OMFFixup) -> Iterator[str]:
    """Rule 4 for one of our fixups."""
    field = pair.va(fx.offset)
    if not pair.inside(fx):
        yield f"{_va(field)}: {fx.target_name}: the fixup field crosses the function boundary"
        return
    if fx.location != LOC_OFFSET32:
        yield f"{_va(field)}: {fx.target_name}: fixup location {fx.location} is not offset32"
        return
    target = _want(pair, field, fx)
    if isinstance(target, str):
        yield target
        return
    rule = _segment_relative if fx.segment_relative else _self_relative
    yield from rule(pair, field, *target)


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
    own_publics: Sequence[OwnPublic] = (),
) -> RelocResult:
    """Check our public [off, off + size) of `segment` against `row` of the original. `flat` is
    le.load_flat(relocate=False) and `fixups` le.fixups() (any order). `own_publics` maps our
    unit's other publics to their original rows (rule 4); a reference to our own `_TEXT` outside
    the checked public fails without it. Raises RelocError for a zero-size public, a zero-length
    row, or a public, own public or row outside its data."""
    _check_inputs(segment, off, size, row, flat)
    _check_own_publics(own_publics, segment)
    ordered = sorted(fixups, key=lambda fx: fx.src_va)
    theirs = {fx.src_va: fx for fx in _le_fields(ordered, row.start, row.end)}
    publics = tuple(sorted(own_publics, key=lambda public: public.offset))
    pair = _Pair(segment, off, size, row, flat, symbols, theirs, publics)
    ours = list(_our_fixups(pair))
    fields = {pair.va(fx.offset) for fx in ours}
    length = tuple(_length(pair))
    if length:  # the rest compares [start, end) byte for byte, which needs equal lengths
        return RelocResult(False, length, frozenset(fields), frozenset(theirs))
    problems = [
        *_bytes(pair, _masked(pair, ours)),
        *(problem for fx in ours for problem in _fixup(pair, fx)),
        *_reverse_coverage(pair, fields),
    ]
    return RelocResult(not problems, tuple(sorted(problems)), frozenset(fields), frozenset(theirs))
