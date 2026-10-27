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


# ---- get_text (stubs: plan 07-12 Task 2 RED) ----

GET_TEXT: dict[str, tuple[int, int, int]] = {
    "ufo2p": (0x00063800, 0x000F3794, 0),
    "tacp": (0x0005B360, 0x00292D18, 0),
}


@dataclass(frozen=True)
class TextSection:
    section: int
    start: int
    end: int
    strings: tuple[int, ...]


def get_text_sections(exe: ExeInputs) -> tuple[TextSection, ...]:
    return ()


def get_text_index(sections: Sequence[TextSection], va: int) -> tuple[int, int] | None:
    return None


def get_text_sites(exe: ExeInputs) -> list[Site]:
    return []


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


def report_va(exe: ExeInputs, va: int) -> dict:
    return {"va": _hex(va), "rows": _rows_of(table_refs(exe, va, va + 1))}


def report_interrupt(exe: ExeInputs, vector: int) -> dict:
    sites = interrupt_callers(exe, vector)
    return {"int": f"0x{vector:02X}",
            "sites": [{"caller": _hex(s.caller), "call": _hex(s.call_va)} for s in sites],
            "rows": _rows_of(s.caller for s in sites)}  # fmt: skip


def format_report(exe_name: str, report: dict) -> str:
    """The text form: what was asked, each site or string by address, then `N rows`."""
    lines = []
    for ref in report.get("strings", ()):
        lines.append(f"  string {ref['address']}: rows {' '.join(ref['rows']) or 'none'}")
    for site in report.get("sites", ()):
        lines.append(f"  site {site['call']} in {site['caller']}")
    rows = report["rows"]
    lines.append(f"{exe_name}: {len(rows)} rows" + (f": {' '.join(rows)}" if rows else ""))
    return "\n".join(lines)
