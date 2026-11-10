# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc compare-objects` (D-08, D-23; plan 07.2-08): did a change to a unit's C change any
byte of its object?

The match check compiles a touched unit at base and at head with the same cflags and hands both
objects here. They are the same when every segment has the same name, class, length and bytes,
every fixup the same place, size, mode, location, frame method, target and displacement, and
every public the same segment and offset. Names are not compared as text: an extern or public
name resolves through its own tree's SymbolTable (functions.csv and symbols.csv) to the original
address it stands for, so a rename that comes with its symbols.csv row compares equal. A name
neither table knows (a runtime external such as `__CHK`) compares as text. A segment or group
target compares by name. THEADR and COMENT 0xE9 (the source path and its timestamp) are not
read, so a comment-only change compares equal as well.

The report names the first difference by segment, offset and kind and never prints a byte value,
so no game byte reaches a CI log. Anything compare-objects cannot judge raises CompareError: an
unreadable object or config, COMDAT records, or a fixup into iterated data (whose target the
reader cannot place).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from . import omf
from .functions import FunctionsError, read_functions_csv, read_symbols_csv
from .symbols import SymbolError, SymbolTable

FUNCTIONS_CSV = "functions.csv"
SYMBOLS_CSV = "symbols.csv"
# The runner has no LE (the game files are never on it), so no data object is known: every
# 32-bit address counts as data, and a data placeholder _D_XXXXXXXX stands for the address it
# spells.
_ADDRESS_SPACE = ((0, 1 << 32),)

KIND_MODULE = "module"
KIND_SEGMENTS = "segments"
KIND_LENGTH = "length"
KIND_CODE = "code bytes"
KIND_DATA = "data bytes"
KIND_RELOCATION = "relocation"
KIND_PUBLIC = "public"

_BY_ADDRESS = "address"  # a name its table resolves
_BY_NAME = "name"  # a name no table knows, compared as text
_ABSOLUTE = ""  # the segment name of an absolute public (segment index 0)

SAME = "same: code, relocations and publics match"


class CompareError(ValueError):
    """An object or a config tree compare-objects cannot read or judge."""


@dataclass(frozen=True)
class Difference:
    segment: str  # "" for the module as a whole
    offset: int | None  # segment-relative; None when the whole segment or module differs
    kind: str  # one of the KIND_ names
    detail: str  # names fields and counts, never a byte value

    def format(self) -> str:
        where = self.segment or KIND_MODULE
        if self.offset is not None:
            where = f"{where}+{self.offset:#x}"
        return f"{where}: {self.kind}: {self.detail}"

    def to_json(self) -> dict:
        return {"segment": self.segment, "offset": self.offset, "kind": self.kind,
                "detail": self.detail}  # fmt: skip


@dataclass(frozen=True)
class Comparison:
    first_difference: Difference | None

    @property
    def ok(self) -> bool:
        return self.first_difference is None

    def format(self) -> str:
        if self.first_difference is None:
            return SAME
        return f"differ: {self.first_difference.format()}"

    def to_json(self) -> dict:
        diff = self.first_difference
        return {"ok": self.ok, "difference": None if diff is None else diff.to_json()}


def compare(
    base: bytes, head: bytes, *, base_symbols: SymbolTable, head_symbols: SymbolTable
) -> Comparison:
    """Compare two compiles of one unit; each side's names resolve through its own table."""
    base_side = _Side(_read(base, "base"), base_symbols)
    head_side = _Side(_read(head, "head"), head_symbols)
    return Comparison(next(_differences(base_side, head_side), None))


def load_symbols(config: Path, exe: str) -> SymbolTable:
    """The table of one tree: config/<exe>/functions.csv and, when present, symbols.csv."""
    folder = Path(config) / exe
    try:
        rows = read_functions_csv(folder / FUNCTIONS_CSV)
        named = read_symbols_csv(folder / SYMBOLS_CSV)
        return SymbolTable.build(rows, named, data_ranges=_ADDRESS_SPACE)
    except (FunctionsError, SymbolError, OSError) as exc:
        raise CompareError(f"{folder}: {exc}") from exc


def compare_files(
    base: Path, head: Path, *, base_config: Path, head_config: Path, exe: str
) -> Comparison:
    """compare() on two object files, each tree's table read from its config directory."""
    return compare(_read_file(base), _read_file(head), base_symbols=load_symbols(base_config, exe),
                   head_symbols=load_symbols(head_config, exe))  # fmt: skip


def _read_file(path: Path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise CompareError(f"{path}: {exc.strerror or exc}") from exc


def _read(data: bytes, side: str) -> omf.Module:
    try:
        module = omf.read_object(data)
    except omf.OMFError as exc:
        raise CompareError(f"the {side} object is not a readable OMF object: {exc}") from exc
    if module.comdats:
        raise CompareError(f"the {side} object holds COMDAT records, which are not compared")
    iterated = next((seg.name for seg in module.segments if seg.unmaskable), None)
    if iterated is not None:
        raise CompareError(f"the {side} object has a fixup into iterated data in {iterated}, "
                           "whose target cannot be placed")  # fmt: skip
    return module


@dataclass(frozen=True)
class _Side:
    module: omf.Module
    symbols: SymbolTable

    def resolve(self, name: str) -> tuple[str, int | str]:
        try:
            return _BY_ADDRESS, self.symbols.address_of(name)
        except SymbolError:
            return _BY_NAME, name

    def segment_name(self, index: int) -> str:
        return self.module.segments[index - 1].name if index else _ABSOLUTE


def _differences(base: _Side, head: _Side) -> Iterator[Difference]:
    if _module_key(base.module) != _module_key(head.module):
        yield Difference("", None, KIND_MODULE, "the memory model or default libraries differ")
    base_layout = [_layout(seg) for seg in base.module.segments]
    head_layout = [_layout(seg) for seg in head.module.segments]
    if base_layout != head_layout:
        counts = f"{len(base_layout)} segments at base, {len(head_layout)} at head"
        yield Difference("", None, KIND_SEGMENTS, f"{counts}, or their names or classes differ")
        return
    for base_seg, head_seg in zip(base.module.segments, head.module.segments, strict=True):
        yield from _segment_differences(base_seg, head_seg)
        yield from _fixup_differences(base_seg, head_seg, base, head)
    yield from _public_differences(base, head)


def _module_key(module: omf.Module) -> tuple:
    return module.model, module.default_libraries, module.easy_omf


def _layout(seg: omf.Segment) -> tuple:
    return seg.index, seg.name, seg.class_name, seg.use32


def _segment_differences(base: omf.Segment, head: omf.Segment) -> Iterator[Difference]:
    if base.length != head.length:
        yield Difference(base.name, None, KIND_LENGTH,
                         f"{base.length:#x} bytes at base, {head.length:#x} at head")  # fmt: skip
        return
    differing = [i for i, (b, h) in enumerate(zip(base.data, head.data, strict=True)) if b != h]
    if differing:
        kind = KIND_CODE if base.is_code else KIND_DATA
        yield Difference(base.name, differing[0], kind,
                         f"{len(differing)} of {base.length} bytes differ")  # fmt: skip
    patched = base.backpatched ^ head.backpatched
    if patched:
        yield Difference(base.name, min(patched), KIND_RELOCATION, "a backpatch differs")


def _fixup_fields(fx: omf.OMFFixup, side: _Side) -> tuple[tuple[str, object], ...]:
    """(field, value) pairs in report order; the target resolved to an address when it can."""
    if fx.target_kind == "extern":
        target: object = side.resolve(fx.target_name)
    elif fx.target_kind == "frame":
        target = (fx.target_kind, fx.target_index)
    else:  # a segment or group, by name
        target = (fx.target_kind, fx.target_name)
    return (("size", fx.size), ("mode", fx.segment_relative), ("location", fx.location),
            ("frame method", fx.frame_method), ("target", target),
            ("displacement", fx.displacement))  # fmt: skip


def _fixup_differences(
    base_seg: omf.Segment, head_seg: omf.Segment, base: _Side, head: _Side
) -> Iterator[Difference]:
    base_fixups = sorted(base_seg.fixups, key=lambda fx: fx.offset)
    head_fixups = sorted(head_seg.fixups, key=lambda fx: fx.offset)
    for base_fx, head_fx in zip(base_fixups, head_fixups, strict=False):  # counts: below
        if base_fx.offset != head_fx.offset:
            yield Difference(base_seg.name, min(base_fx.offset, head_fx.offset), KIND_RELOCATION,
                             "a fixup sits at another offset")  # fmt: skip
            return
        fields = zip(_fixup_fields(base_fx, base), _fixup_fields(head_fx, head), strict=True)
        field = next((name for (name, b), (_, h) in fields if b != h), None)
        if field is not None:
            yield Difference(base_seg.name, base_fx.offset, KIND_RELOCATION, f"{field} differs")
    if len(base_fixups) != len(head_fixups):
        extra = _first_extra(base_fixups, head_fixups)
        counts = f"{len(base_fixups)} fixups at base, {len(head_fixups)} at head"
        yield Difference(base_seg.name, extra.offset, KIND_RELOCATION, counts)


def _first_extra[T](base: list[T], head: list[T]) -> T:
    """The first item of the longer list past the end of the shorter one."""
    shorter, longer = sorted((base, head), key=len)
    return longer[len(shorter)]


def _public_keys(side: _Side) -> list[tuple]:
    return sorted(
        (side.segment_name(pub.segment_index), pub.offset, pub.local, side.resolve(pub.name))
        for pub in side.module.publics
    )


def _public_differences(base: _Side, head: _Side) -> Iterator[Difference]:
    base_keys, head_keys = _public_keys(base), _public_keys(head)
    for base_key, head_key in zip(base_keys, head_keys, strict=False):  # counts: below
        if base_key != head_key:
            segment, offset = min(base_key[:2], head_key[:2])
            yield Difference(segment, offset, KIND_PUBLIC,
                             "a public moved or stands for another address")  # fmt: skip
            return
    if len(base_keys) != len(head_keys):
        segment, offset = _first_extra(base_keys, head_keys)[:2]
        yield Difference(segment, offset, KIND_PUBLIC,
                         f"{len(base_keys)} publics at base, {len(head_keys)} at head")  # fmt: skip
