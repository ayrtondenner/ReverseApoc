# Derived from KKND-Decomp tools/split.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""Per-function Intel-syntax listings with symbolic operands (SPL-05, research Pattern 9).

One listing per functions.csv row goes to the gitignored asm/<exe>/<name>.s. A listing is a
reading aid only: it is never assembled, and nothing here prints it.

Operands are named through symbols.py, the one address <-> name mapping, so a listing, the target
writer and the relocation check agree on every name (Pitfall 3):

- a call or jump with a static destination names it: the row starting there by its C name
  (func_X, a runtime public, a symbols.csv name), an address inside a row as that row's name
  plus an offset, and a jump inside the listed row as a local `.LXXXXXXXX` label;
- an operand overlapping an LE fixup field is named after the fixup's linear target. The field
  itself holds an object-relative offset (Pitfall 1), so the raw value is only used to find the
  operand text, never as an address;
- an LE fixup site at an instruction start is inline data (a jump table entry), written as a
  `dd <symbol>` line; decoding resumes after it.

The walker (`walk`) is shared with the scorer, so both see the same instruction boundaries.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fileio import write_atomic
from .functions import FunctionRow
from .le import LE, Fixup
from .symbols import SymbolTable
from .x86 import Insn, decode

OBJ_EXECUTABLE = 0x0004  # LE object flag: executable
LISTING_SUFFIX = ".s"
_MAX_FIELD = 6  # the widest LE fixup field (ptr16:32)
_LITTLE = "little"
_DATA_DIRECTIVES = {1: "db", 2: "dw", 4: "dd", 6: "df"}
# A number as capstone prints it in Intel syntax: 0x-prefixed hex, or decimal below 10.
_NUMBER = re.compile(r"(?<![\w.])(0x[0-9a-f]+|[0-9]+)(?![\w])")
_SAFE_FILE = re.compile(r"[A-Za-z0-9_$@][A-Za-z0-9_$@.]*")


class AsmError(ValueError):
    """A listing cannot be produced (no row contains the requested address)."""


@dataclass(frozen=True, slots=True)
class DataItem:
    """An LE fixup site at an instruction start: inline data, not code."""

    va: int
    size: int
    fixup: Fixup


@dataclass(frozen=True, slots=True)
class RawByte:
    """A byte capstone cannot decode (or an instruction cut by the row end)."""

    va: int
    value: int


type Item = Insn | DataItem | RawByte


def data_ranges(le: LE) -> list[tuple[int, int]]:
    """[start, end) of every LE object that is not executable: the data a D_ name can live in."""
    return [(obj.base, obj.end) for obj in le.objects if not obj.flags & OBJ_EXECUTABLE]


class FixupIndex:
    """The LE fixups sorted by field address, for the fields overlapping a range."""

    def __init__(self, fixups: Iterable[Fixup]) -> None:
        self.fixups = sorted(fixups, key=lambda fx: fx.src_va)
        self.sites = [fx.src_va for fx in self.fixups]

    def overlapping(self, start: int, end: int) -> list[Fixup]:
        """The fixups whose field shares at least one byte with [start, end)."""
        low = bisect.bisect_left(self.sites, start - _MAX_FIELD + 1)
        high = bisect.bisect_left(self.sites, end)
        return [fx for fx in self.fixups[low:high] if fx.src_va + fx.size > start]


def walk(code: bytes, start: int, sites: Mapping[int, Fixup]) -> Iterator[Item]:
    """Instructions, inline data and undecodable bytes of `code` loaded at `start`, in order. A
    fixup in `sites` (by field address) that falls on an instruction start is a DataItem."""
    end = start + len(code)
    pos = start
    while pos < end:
        fixup = sites.get(pos)
        if fixup is not None:
            size = min(fixup.size, end - pos)
            yield DataItem(pos, size, fixup)
            pos += size
            continue
        before = pos
        for insn in decode(code[pos - start :], pos, data_sites=sites):
            yield insn
            pos = insn.va + insn.size
        if pos == before:
            yield RawByte(pos, code[pos - start])
            pos += 1


def row_sites(row: FunctionRow, fixups: Sequence[Fixup]) -> dict[int, Fixup]:
    """The fixups whose field starts inside the row, by field address."""
    return {fx.src_va: fx for fx in fixups if row.start <= fx.src_va < row.end}


# ---- naming ----


def target_name(symbols: SymbolTable, va: int, *, code: bool = False) -> str:
    """The C name for `va`: the row starting there, else the containing row plus an offset, else
    the data name (or, for a branch destination in no row, the bare address)."""
    if symbols.function_at(va) is not None:
        return symbols.c_name(va)
    row = symbols.containing(va)
    if row is not None:
        return f"{symbols.c_name(row.start)}+0x{va - row.start:X}"
    if code:
        return f"0x{va:08X}"
    return symbols.c_name(va, data=True)


def _label(va: int) -> str:
    return f".L{va:08X}"


def branch_target(insn: Insn, fixups: Mapping[int, Fixup]) -> int | None:
    """The destination of a direct call or jump; an LE rel32 fixup on its field wins."""
    if insn.branch_target is None:
        return None
    fixup = fixups.get(insn.rel32_field) if insn.rel32_field is not None else None
    return fixup.target_va if fixup is not None else insn.branch_target


def _local_labels(items: Sequence[Item], row: FunctionRow, fixups: Mapping[int, Fixup]) -> set[int]:
    labels = set()
    for item in items:
        if not isinstance(item, Insn) or not item.is_jump:
            continue
        target = branch_target(item, fixups)
        if target is not None and row.start <= target < row.end:
            labels.add(target)
    return labels


def _substitute(op_str: str, raw: int, name: str, *, last: bool) -> str | None:
    """`op_str` with the number equal to `raw` replaced by `name` (the last such number when the
    field ends the instruction, i.e. an immediate, else the first); None when no number fits."""
    matches = [m for m in _NUMBER.finditer(op_str) if int(m.group(1), 0) == raw]
    if not matches:
        return None
    m = matches[-1] if last else matches[0]
    return op_str[: m.start(1)] + name + op_str[m.end(1) :]


def _field_operands(insn: Insn, op_str: str, fixups: Iterable[Fixup], symbols: SymbolTable) -> str:
    """Rewrite each operand an LE fixup field overlaps to the fixup's target name."""
    notes = []
    for fixup in fixups:
        name = target_name(symbols, fixup.target_va)
        offset = fixup.src_va - insn.va
        raw = int.from_bytes(insn.raw[offset : offset + fixup.size], _LITTLE)
        last = offset + fixup.size == insn.size
        rewritten = _substitute(op_str, raw, name, last=last) if offset >= 0 else None
        if rewritten is None:
            notes.append(f"{fixup.kind_name} -> {name}")
            continue
        op_str = rewritten
    return op_str + "".join(f"  ; {note}" for note in notes)


def _operands(
    insn: Insn, row: FunctionRow, fixups: Mapping[int, Fixup], symbols: SymbolTable
) -> str:
    target = branch_target(insn, fixups)
    if target is not None:
        if insn.is_jump and row.start <= target < row.end:
            return _label(target)
        return target_name(symbols, target, code=True)
    fields = (fixups.get(va) for va in range(insn.va - _MAX_FIELD + 1, insn.va + insn.size))
    inside = [fx for fx in fields if fx is not None and fx.src_va + fx.size > insn.va]
    return _field_operands(insn, insn.op_str, inside, symbols)


def _line(va: int, text: str) -> str:
    return f"  0x{va:08X}  {text}".rstrip()


def _item_line(
    item: Item, row: FunctionRow, fixups: Mapping[int, Fixup], symbols: SymbolTable
) -> str:
    if isinstance(item, DataItem):
        directive = _DATA_DIRECTIVES.get(item.size, "db")
        return _line(item.va, f"{directive} {target_name(symbols, item.fixup.target_va)}")
    if isinstance(item, RawByte):
        return _line(item.va, f"db 0x{item.value:02X}")
    return _line(item.va, f"{item.mnemonic} {_operands(item, row, fixups, symbols)}")


def listing(
    row: FunctionRow, *, flat: bytes | bytearray, fixups: Sequence[Fixup], symbols: SymbolTable
) -> str:
    """The listing text of one row: a header comment, then one line per instruction or data
    item, with `.LXXXXXXXX:` lines at local jump targets. `flat` is load_flat(relocate=False)."""
    near = {fx.src_va: fx for fx in fixups if row.start - fx.size < fx.src_va < row.end}
    sites = row_sites(row, near.values())
    items = list(walk(bytes(flat[row.start : row.end]), row.start, sites))
    labels = _local_labels(items, row, near)
    name = symbols.c_name(row.start)
    size = row.end - row.start
    lines = [f"# {name}  0x{row.start:08X}..0x{row.end:08X}  {size} bytes, {row.kind}"]
    for item in items:
        if item.va in labels:
            lines.append(f"{_label(item.va)}:")
        lines.append(_item_line(item, row, near, symbols))
    return "\n".join(lines) + "\n"


# ---- writing ----


def select_rows(
    rows: Sequence[FunctionRow], symbols: SymbolTable, *, only: int | None = None
) -> list[FunctionRow]:
    """Every row, or with `only` the one row containing that address (orchestrator ruling F3:
    any address inside a row, not just a row start)."""
    if only is None:
        return sorted(rows, key=lambda row: row.start)
    row = symbols.containing(only)
    if row is None:
        raise AsmError(f"no functions.csv row contains 0x{only:08X}")
    return [row]


def file_name(symbols: SymbolTable, row: FunctionRow) -> str:
    """<C name>.s, or <kind>_<start>.s for a name that is not a safe file name or that more than
    one row carries (`symbols.ambiguous`, e.g. _Alphabet in rt_itoa and rt_ltoa), so every row
    gets its own listing (DI-01)."""
    name = symbols.c_name(row.start)
    if not _SAFE_FILE.fullmatch(name) or name in symbols.ambiguous:
        name = f"{row.kind.replace('-', '_')}_{row.start:08X}"
    return name + LISTING_SUFFIX


@dataclass(frozen=True)
class AsmReport:
    count: int
    directory: Path

    def format(self) -> str:
        noun = "listing" if self.count == 1 else "listings"
        return f"wrote {self.count} {noun} to {self.directory}"

    def to_json(self) -> dict[str, Any]:
        return {"count": self.count, "directory": str(self.directory)}


def write_listings(
    rows: Iterable[FunctionRow],
    *,
    flat: bytes | bytearray,
    fixups: Iterable[Fixup],
    symbols: SymbolTable,
    out_dir: Path,
) -> AsmReport:
    """Write one listing per row into `out_dir`, each file atomically."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = FixupIndex(fixups)
    count = 0
    for row in rows:
        near = index.overlapping(row.start, row.end)
        text = listing(row, flat=flat, fixups=near, symbols=symbols)
        write_atomic(out_dir / file_name(symbols, row), text.encode("utf-8"))
        count += 1
    return AsmReport(count, out_dir)
