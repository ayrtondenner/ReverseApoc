# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry locators for the mechanics map (DEC-01, D-01, D-03, D-26): the production form of spike
007's routes (q1 BIOS tick, q3 strings and fixups, q4 get_text), so every `[[entry]]` of
config/mechanics.toml rests on a command anyone with the game can re-run.

- `string_refs(exe, keyword)`: the NUL-terminated strings of the data object that contain the
  keyword (ASCII, case-insensitive), each with the game/thunk rows holding an LE fixup whose
  target is exactly the string's first byte (file names, format strings, hand-off files);
- `table_refs(exe, lo, hi)`: the game/thunk rows holding an LE fixup whose target lies in
  [lo, hi) (a data table, a record array, a single variable with hi = lo + 1);
- `interrupt_callers(exe, vector)`: each call (or tail jump) to the runtime `int386_` /
  `int386x_` row whose basic block last set eax to the interrupt number (research: the BIOS-tick
  readers call `int386_(0x1A)`).

Register arguments are recovered by a small per-block tracker: within a basic block of one row,
`mov r32, imm` sets a register, `xor r, r` / `sub r, r` zero it and `mov r32, r32` copies a known
value; every other write makes it unknown. The block ends at an in-row jump target and after a
terminal instruction; a call forgets eax and edx (Watcom returns there), `int` forgets eax-edx.
A register set before the block (a value pinned once per row, a loop variable) is not guessed.

Reports carry addresses, counts, interrupt numbers and the keyword the caller typed only: never
string contents, instruction text or table bytes (CLAUDE.md, T-07-34).
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from . import asm
from .callgraph import WALKED_KINDS
from .functions import FunctionRow
from .le import SRC_OFF32
from .x86 import Insn

if TYPE_CHECKING:
    from .check import ExeInputs


class LocateError(ValueError):
    """A locator input is wrong (an empty range or keyword, a get_text table that does not
    decode)."""


INT386_NAMES = ("int386_", "int386x_")  # the runtime rows that take the interrupt number in eax
_NUL = 0
_PRINTABLE = re.compile(r"[ -~]+")

type Range = tuple[int, int]  # [start, end)


@dataclass(frozen=True)
class StringRef:
    """One data string holding `keyword`: its first byte and the rows with an exact fixup to it."""

    address: int
    keyword: str
    rows: tuple[int, ...]


@dataclass(frozen=True)
class Site:
    """One call site: the row it sits in, the call's address and the recovered arguments.
    `partial` is True when an argument the locator needs could not be recovered."""

    caller: int
    call_va: int
    section: int | None = None
    index: int | None = None
    partial: bool = False


def load_inputs(config_root: Path, orig_dir: Path, manifest: Path, exe: str) -> ExeInputs:
    """The user's own EXE with its config (needs orig/; the tests replace this seam)."""
    from .check import load_exe, select_exe  # check pulls in the compiler plumbing
    from .targets import load_manifest

    target = select_exe(load_manifest(manifest), exe, manifest)
    return load_exe(target, orig_dir=orig_dir, manifest=manifest, config_root=config_root)


# ---- the image ----


def _ranges(exe: ExeInputs) -> tuple[Range, Range]:
    """[start, end) of the code object and of the data object."""
    objects = exe.le.objects
    code = next(obj for obj in objects if obj.flags & asm.OBJ_EXECUTABLE)
    data = next(obj for obj in objects if not obj.flags & asm.OBJ_EXECUTABLE)
    return (code.base, code.end), (data.base, data.end)


class _Rows:
    """The functions.csv rows sorted by start, for `containing`."""

    def __init__(self, rows: Sequence[FunctionRow]) -> None:
        self.rows = sorted(rows, key=lambda row: row.start)
        self.starts = [row.start for row in self.rows]

    def containing(self, va: int) -> FunctionRow | None:
        i = bisect_right(self.starts, va) - 1
        if i < 0:
            return None
        row = self.rows[i]
        return row if va < row.end else None

    def walked(self) -> Iterator[FunctionRow]:
        return (row for row in self.rows if row.kind in WALKED_KINDS)


def _code_refs(exe: ExeInputs) -> Iterator[tuple[int, int]]:
    """(target, referencing game/thunk row) of every LE fixup held in such a row."""
    (code, _data), rows = _ranges(exe), _Rows(exe.rows)
    for fx in exe.fixups:
        if not code[0] <= fx.src_va < code[1]:
            continue
        row = rows.containing(fx.src_va)
        if row is not None and row.kind in WALKED_KINDS:
            yield fx.target_va, row.start


# ---- strings ----


def _check_keyword(keyword: str) -> bytes:
    if not _PRINTABLE.fullmatch(keyword):
        raise LocateError(f"keyword {keyword!r} is empty or not printable ASCII")
    return keyword.lower().encode("ascii")


def _string_starts(flat: bytes, data: Range, key: bytes) -> list[int]:
    """The first byte of each NUL-terminated data string that contains `key` (lower case)."""
    lo, hi = data
    blob = bytes(flat[lo:hi]).lower()
    found = set()
    at = blob.find(key)
    while at >= 0:
        found.add(lo + blob.rfind(bytes([_NUL]), 0, at) + 1)
        at = blob.find(key, at + 1)
    return sorted(found)


def string_refs(exe: ExeInputs, keyword: str) -> list[StringRef]:
    """Every data string holding `keyword` (case-insensitive), by address, each with the
    game/thunk rows whose fixup targets its first byte (possibly none: UI text is reached
    through get_text, not by address)."""
    key = _check_keyword(keyword)
    _code, data = _ranges(exe)
    starts = _string_starts(exe.flat, data, key)
    wanted = frozenset(starts)
    rows: defaultdict[int, set[int]] = defaultdict(set)
    for target, row in _code_refs(exe):
        if target in wanted:
            rows[target].add(row)
    return [StringRef(start, keyword, tuple(sorted(rows.get(start, ())))) for start in starts]


def table_refs(exe: ExeInputs, lo: int, hi: int) -> tuple[int, ...]:
    """The game/thunk rows holding an LE fixup whose target lies in [lo, hi), by address."""
    if hi <= lo:
        raise LocateError(f"range [0x{lo:08X}, 0x{hi:08X}) is empty")
    return tuple(sorted({row for target, row in _code_refs(exe) if lo <= target < hi}))


# ---- register arguments ----

_REG32 = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
_SUBREG = {
    "ax": ("eax", 0xFFFF, 0), "al": ("eax", 0xFF, 0), "ah": ("eax", 0xFF, 8),
    "bx": ("ebx", 0xFFFF, 0), "bl": ("ebx", 0xFF, 0), "bh": ("ebx", 0xFF, 8),
    "cx": ("ecx", 0xFFFF, 0), "cl": ("ecx", 0xFF, 0), "ch": ("ecx", 0xFF, 8),
    "dx": ("edx", 0xFFFF, 0), "dl": ("edx", 0xFF, 0), "dh": ("edx", 0xFF, 8),
    "si": ("esi", 0xFFFF, 0), "di": ("edi", 0xFFFF, 0), "bp": ("ebp", 0xFFFF, 0),
    "sp": ("esp", 0xFFFF, 0),
}  # fmt: skip
_FULL = 0xFFFFFFFF
_RETURN_REGS = ("eax", "edx")  # Watcom returns in eax (edx:eax); a call clobbers them
_INT_REGS = ("eax", "ebx", "ecx", "edx")  # `int` may return in any of them
_NO_WRITE = frozenset({"cmp", "test", "push", "out", "bt"})  # their first operand is only read
_ZEROING = frozenset({"xor", "sub"})  # `xor r, r` / `sub r, r` set r to 0
_STRING_OP = re.compile(r"(?:movs|stos|lods|scas|cmps|ins|outs)[bwd]")
_IMPLICIT = (
    (frozenset({"cdq", "cwd", "cbw", "cwde", "mul", "imul", "div", "idiv", "lahf", "xlatb", "in",
                "cpuid", "rdtsc", "aaa", "aas", "aam", "aad", "daa", "das"}), ("eax", "edx")),
    (frozenset({"loop", "loope", "loopne", "jecxz"}), ("ecx",)),
    (frozenset({"pusha", "popa", "pushal", "popal", "xchg", "cmpxchg", "xadd"}), _REG32),
)  # fmt: skip


def _operands(insn: Insn) -> list[str]:
    return [op.strip() for op in insn.op_str.split(",")] if insn.op_str else []


def _immediate(text: str) -> int | None:
    try:
        return int(text, 0) & _FULL
    except ValueError:
        return None


def _implicit_writes(mnemonic: str) -> tuple[str, ...]:
    word = mnemonic.split()[-1]  # `rep movsd` writes like movsd
    if _STRING_OP.fullmatch(word):
        return ("eax", "ecx", "esi", "edi")
    return next((regs for names, regs in _IMPLICIT if word in names), ())


def _part(op: str) -> tuple[str, int, int] | None:
    """(full register, mask, shift) of a register operand, else None."""
    return (op, _FULL, 0) if op in _REG32 else _SUBREG.get(op)


class _Regs:
    """The general registers' known constants inside one basic block."""

    def __init__(self) -> None:
        self.known: dict[str, int] = {}

    def value(self, reg: str) -> int | None:
        return self.known.get(reg)

    def forget(self, regs: Sequence[str] = _REG32) -> None:
        for reg in regs:
            self.known.pop(reg, None)

    def step(self, insn: Insn) -> None:
        """Advance over `insn`."""
        mn = insn.mnemonic
        if insn.is_call:
            self.forget(_RETURN_REGS)
            return
        if mn == "int":
            self.forget(_INT_REGS)
            return
        self.forget(_implicit_writes(mn))
        ops = _operands(insn)
        if insn.is_jump or not ops or mn in _NO_WRITE:
            return
        part = _part(ops[0])
        if part is not None:
            self._write(part, self._source(mn, ops))

    def _source(self, mn: str, ops: list[str]) -> int | None:
        if len(ops) != 2:
            return None
        if mn in _ZEROING and ops[0] == ops[1]:
            return 0
        if mn != "mov":
            return None
        source = _part(ops[1])
        if source is None:
            return _immediate(ops[1])
        reg, mask, shift = source
        full = self.known.get(reg)
        return None if full is None else (full >> shift) & mask

    def _write(self, part: tuple[str, int, int], value: int | None) -> None:
        reg, mask, shift = part
        full = self.known.get(reg)
        if value is not None and mask != _FULL:
            value = None if full is None else (full & ~(mask << shift)) | ((value & mask) << shift)
        if value is None:
            self.known.pop(reg, None)
        else:
            self.known[reg] = value & _FULL


def _row_insns(exe: ExeInputs, index: asm.FixupIndex, row: FunctionRow) -> tuple[list[Insn],
                                                                                 dict]:  # fmt: skip
    near = index.overlapping(row.start, row.end)
    sites = asm.row_sites(row, near)
    code = bytes(exe.flat[row.start : row.end])
    return [item for item in asm.walk(code, row.start, sites) if isinstance(item, Insn)], sites


def _tracked(exe: ExeInputs, index: asm.FixupIndex,
             row: FunctionRow) -> Iterator[tuple[Insn, int | None, _Regs]]:  # fmt: skip
    """Each instruction of the row with its static branch target and the block's register state
    just before it."""
    insns, sites = _row_insns(exe, index, row)
    targets = [asm.branch_target(insn, sites) for insn in insns]
    labels = frozenset(t for insn, t in zip(insns, targets, strict=True)
                       if insn.is_jump and t is not None and row.start <= t < row.end)  # fmt: skip
    regs = _Regs()
    after_terminal = False
    for insn, target in zip(insns, targets, strict=True):
        if after_terminal or insn.va in labels:
            regs.forget()
        yield insn, target, regs
        regs.step(insn)
        after_terminal = insn.is_terminal


def _transfers(insn: Insn) -> bool:
    """A call, or a jump that does not fall through (a tail call)."""
    return insn.is_call or (insn.is_jump and not insn.is_conditional)


def _calls_to(exe: ExeInputs, callee: frozenset[int]) -> Iterator[tuple[FunctionRow, Insn,
                                                                         _Regs]]:  # fmt: skip
    """Every call or tail jump from a game/thunk row onto a row in `callee`."""
    index = asm.FixupIndex(exe.fixups)
    for row in _Rows(exe.rows).walked():
        for insn, target, regs in _tracked(exe, index, row):
            if _transfers(insn) and target in callee:
                yield row, insn, regs


def interrupt_callers(exe: ExeInputs, vector: int) -> list[Site]:
    """Each call (or tail jump) to the runtime int386_/int386x_ rows whose basic block last set
    eax to `vector`, by call address. No such runtime row: none."""
    int386 = frozenset(row.start for row in exe.rows if row.name in INT386_NAMES)
    if not int386:
        return []
    return [Site(row.start, insn.va) for row, insn, regs in _calls_to(exe, int386)
            if regs.value("eax") == vector]  # fmt: skip


# ---- get_text: UI text by (section, index) ----

# Per EXE: the get_text function (section in eax, index in edx), its section-pointer table and
# the table's slot count. Research 07-R1 Q2 gives the function and table; the slot count is
# spike 007 q4's measurement: both tables have 52 slots. UFO2P fills all 52 (research's "50
# sections" is the loop bound of the dump routine next to get_text); TACP fills 21, the rest
# are null.
GET_TEXT: dict[str, tuple[int, int, int]] = {
    "ufo2p": (0x00063800, 0x000F3794, 52),
    "tacp": (0x0005B360, 0x00292D18, 52),
}
_SLOT_SIZE = 4  # one off32 section pointer


@dataclass(frozen=True)
class TextSection:
    """One non-null section: [start, end) of its strings in the text blob (end is the next
    section's start, or the table for the last one) and each string's first byte."""

    section: int
    start: int
    end: int
    strings: tuple[int, ...]


def _get_text(exe: ExeInputs) -> tuple[int, int, int]:
    if exe.stem not in GET_TEXT:
        raise LocateError(f"no get_text facts for {exe.stem!r} (GET_TEXT holds "
                          f"{', '.join(GET_TEXT)})")  # fmt: skip
    return GET_TEXT[exe.stem]


def _word(flat: bytes, va: int) -> int:
    return int.from_bytes(flat[va : va + _SLOT_SIZE], "little")


class _Table:
    """The section-pointer table of one EXE, checked slot by slot."""

    def __init__(self, exe: ExeInputs) -> None:
        _func, self.va, self.slots = _get_text(exe)
        self.flat = exe.flat
        _code, self.data = _ranges(exe)
        end = self.va + (self.slots + 1) * _SLOT_SIZE  # the slot past the last is checked too
        if not (self.data[0] <= self.va and end <= self.data[1]):
            raise LocateError(f"get_text table 0x{self.va:08X} with {self.slots} slots does not "
                              "fit in the data object")  # fmt: skip
        self.fixups = {fx.src_va: fx for fx in exe.fixups if self.va <= fx.src_va < end}

    def _slot_va(self, k: int) -> int:
        return self.va + k * _SLOT_SIZE

    def pointer(self, k: int) -> int | None:
        """Slot k's string start, or None for a null slot."""
        va = self._slot_va(k)
        fx = self.fixups.get(va)
        if fx is None:
            if _word(self.flat, va):
                raise LocateError(f"get_text slot {k} at 0x{va:08X} holds a value with no fixup: "
                                  f"the slot count {self.slots} is wrong")  # fmt: skip
            return None
        if fx.kind != SRC_OFF32 or fx.size != _SLOT_SIZE:
            raise LocateError(f"get_text slot {k} at 0x{va:08X} is not an off32 pointer")
        if not self.data[0] <= fx.target_va < self.va:
            raise LocateError(f"get_text slot {k} points at 0x{fx.target_va:08X}, not into the "
                              "data object below the table")  # fmt: skip
        if fx.target_va > self.data[0] and self.flat[fx.target_va - 1] != _NUL:
            raise LocateError(f"get_text slot {k} points at 0x{fx.target_va:08X}, not at a "
                              "string start")  # fmt: skip
        return fx.target_va

    def check_end(self) -> None:
        """The slot past the last must not be one more text pointer (a count too small)."""
        fx = self.fixups.get(self._slot_va(self.slots))
        if fx is not None and fx.kind == SRC_OFF32 and self.data[0] <= fx.target_va < self.va:
            raise LocateError(f"get_text slot {self.slots} past the last also points into the "
                              f"text: the slot count {self.slots} is too small")  # fmt: skip


def _strings_in(flat: bytes, start: int, end: int) -> tuple[int, ...]:
    """The first byte of each NUL-terminated string in [start, end)."""
    blob = bytes(flat[start:end])
    starts = [start]
    at = blob.find(_NUL)
    while at >= 0 and start + at + 1 < end:
        starts.append(start + at + 1)
        at = blob.find(_NUL, at + 1)
    return tuple(starts)


def get_text_sections(exe: ExeInputs) -> tuple[TextSection, ...]:
    """The non-null sections of the EXE's get_text table, by section number. LocateError when a
    slot is not an off32 pointer to a string start below the table, two slots share a start, a
    slot holds a value without a fixup, or the slot past the last is still a text pointer (the
    last two catch a wrong slot count in GET_TEXT)."""
    table = _Table(exe)
    pointers = {k: start for k in range(table.slots) if (start := table.pointer(k)) is not None}
    table.check_end()
    if len(set(pointers.values())) != len(pointers):
        raise LocateError("get_text slots share a string start")
    by_start = sorted((start, k) for k, start in pointers.items())
    ends = [start for start, _k in by_start[1:]] + [table.va]
    sections = [TextSection(k, start, end, _strings_in(exe.flat, start, end))
                for (start, k), end in zip(by_start, ends, strict=True)]  # fmt: skip
    return tuple(sorted(sections, key=lambda s: s.section))


def get_text_index(sections: Sequence[TextSection], va: int) -> tuple[int, int] | None:
    """(section, index) of the string holding `va`, or None outside every section."""
    ordered = sorted(sections, key=lambda s: s.start)
    i = bisect_right([s.start for s in ordered], va) - 1
    if i < 0 or va >= ordered[i].end:
        return None
    section = ordered[i]
    return section.section, bisect_right(section.strings, va) - 1


def get_text_sites(exe: ExeInputs) -> list[Site]:
    """Every call (or tail jump) to get_text from a game/thunk row, by call address, with the
    section (eax) and index (edx) its basic block last set; `partial` when either is not a
    constant there (a list index, a loop, a value set before the block)."""
    func = _get_text(exe)[0]
    sites = []
    for row, insn, regs in _calls_to(exe, frozenset({func})):
        section, index = regs.value("eax"), regs.value("edx")
        sites.append(Site(row.start, insn.va, section, index, section is None or index is None))
    return sites


# ---- the `mechanics locate` report ----


def _hex(va: int) -> str:
    return f"0x{va:08X}"


def _rows_of(rows) -> list[str]:
    return [_hex(row) for row in sorted(set(rows))]


def report_string(exe: ExeInputs, keyword: str) -> dict:
    refs = string_refs(exe, keyword)
    rows = {row for ref in refs for row in ref.rows}
    return {"string": keyword,
            "strings": [{"address": _hex(ref.address), "rows": _rows_of(ref.rows)} for ref in refs],
            "rows": _rows_of(rows)}  # fmt: skip


def report_range(exe: ExeInputs, lo: int, hi: int) -> dict:
    return {"range": [_hex(lo), _hex(hi)], "rows": _rows_of(table_refs(exe, lo, hi))}


def _site_cells(sites: Sequence[Site]) -> list[dict]:
    return [{"caller": _hex(s.caller), "call": _hex(s.call_va)} for s in sites]


def _text_sites(exe: ExeInputs, section: int, index: int) -> tuple[list[Site], list[int]]:
    """The get_text sites asking for exactly (section, index), and the rows of the section-only
    sites of that section (their index is not a constant: they may or may not show it)."""
    sites = get_text_sites(exe)
    full = [s for s in sites if (s.section, s.index) == (section, index)]
    partial = [s.caller for s in sites if s.section == section and s.index is None]
    return full, partial


def report_get_text(exe: ExeInputs, section: int, index: int) -> dict:
    full, partial = _text_sites(exe, section, index)
    return {"get_text": [section, index], "sites": _site_cells(full),
            "rows": _rows_of(s.caller for s in full),
            "partial_rows": _rows_of(partial)}  # fmt: skip


def report_va(exe: ExeInputs, va: int) -> dict:
    """The rows with a fixup to exactly `va`; when `va` lies in the get_text blob, also its
    (section, index), the sites asking for it (their rows join `rows`) and the section-only
    rows."""
    rows = set(table_refs(exe, va, va + 1))
    pair = get_text_index(get_text_sections(exe), va)
    full: list[Site] = []
    partial: list[int] = []
    if pair is not None:
        full, partial = _text_sites(exe, *pair)
    text = None if pair is None else {"section": pair[0], "index": pair[1]}
    return {"va": _hex(va), "get_text": text, "sites": _site_cells(full),
            "rows": _rows_of(rows | {s.caller for s in full}),
            "partial_rows": _rows_of(partial)}  # fmt: skip


def report_interrupt(exe: ExeInputs, vector: int) -> dict:
    sites = interrupt_callers(exe, vector)
    return {"int": f"0x{vector:02X}", "sites": _site_cells(sites),
            "rows": _rows_of(s.caller for s in sites)}  # fmt: skip


def format_report(exe_name: str, report: dict) -> str:
    """The text form: what was asked, each string or site by address, then `N rows`."""
    lines = []
    for ref in report.get("strings", ()):
        lines.append(f"  string {ref['address']}: rows {' '.join(ref['rows']) or 'none'}")
    if text := report.get("get_text"):
        pair = text if isinstance(text, list) else [text["section"], text["index"]]
        lines.append(f"  get_text section {pair[0]} index {pair[1]}")
    for site in report.get("sites", ()):
        lines.append(f"  site {site['call']} in {site['caller']}")
    if partial := report.get("partial_rows"):
        lines.append(f"  section-only rows (index not a constant): {' '.join(partial)}")
    rows = report["rows"]
    lines.append(f"{exe_name}: {len(rows)} rows" + (f": {' '.join(rows)}" if rows else ""))
    return "\n".join(lines)
