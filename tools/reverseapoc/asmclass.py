# SPDX-License-Identifier: GPL-3.0-or-later
"""The D-23 asm detector: proposes the hand-written assembly list the owner signs (plan 07-20).

Rows the detector lists: every game row whose start is off Watcom's 16-byte function alignment
(research: about 213 UFO2P / 216 TACP rows), every game row inside a known library unit, and
every game row with data-in-code evidence (07-44). Each gets evidence tags (TAGS order):

- `unaligned`: the start is not a multiple of ALIGNMENT;
- `stack-frame`: `push ebp; mov ebp, esp` among the first FRAME_WINDOW instructions and a read
  of a stack argument (`[ebp + n]`, n >= 8): a stack calling convention, not Watcom's register
  one (a C function with more than four arguments looks the same, so alone it decides nothing);
- `enter`, `pushal`, `iretd`: instructions Watcom C does not emit for game code;
- `nop-pad`: a run of NOP_RUN or more `nop`s followed by more code in the same row (padding an
  assembler put inside a body; Watcom's own filler only follows the last instruction);
- `library-span`: the row lies in one of LIBRARY_UNITS (research 07-R1 R2), resolved from the
  committed config/<exe>/units.csv:
  - UFO2P `u_000161b4` (0x000161B4-0x00018970, the VESA blitters, found from its start),
    `u_000c8e40` (the unit holding the sound library's PIT code at 0x000C8E41) and its C
    wrapper unit `u_000c1b4b` (found from its start, 0x000C1B4B);
  - TACP `u_000cc150` (the unit holding the sound library's PIT code at 0x000CC151).

Data-in-code evidence (07-44, owner ruling 2026-10-31), mechanics.DATA_TAGS, on any game row:

- `no-terminator`: no TERMINATORS mnemonic (ret, retf, iret, iretd, jmp, ljmp) decodes in the
  span. Weak alone: a C function that ends in a call to an exit-like function has no ret (the
  planning probe found it on 25 of 537 runtime rows);
- `text-run`: a run of at least TEXT_RUN printable ASCII bytes ended by a zero byte (a string);
- `zero-fill`: every byte zero, or a zero run of at least ZERO_RUN bytes, longer than any
  alignment filler (at most ALIGNMENT - 1 bytes);
- `bad-decode`: a byte asm.walk cannot decode more than MAX_INSN_BYTES bytes before the row end
  (closer to the end it may be an instruction the end cuts).

The thresholds come from the planning probe on main: no data tag fires on any matched game row
or on any of the signed asm rows, and zero-fill never fires on library code.

The proposed verdict is `asm` for a library-span row or an unaligned row with any code tag, and
`unclear` otherwise: a row that is only unaligned (research A5 assumes most such rows are asm;
the owner rules them), and a row proposed for data evidence alone, which no data tag makes
`asm`. The detector never decides alone: only the owner turns a data row into `asm` or `c`, an
`unclear` row with data evidence is held out of the tier queue until then, other `unclear` rows
stay in the C queue, and only an owner-signed list leaves the must-match sets (D-23).

`merge` writes a re-run into an existing list without erasing a ruling. The tool owns the exe,
address and evidence columns, the owner the verdict and reason: an existing row keeps its
verdict and reason whatever the new proposal, and only a tool-owned change is reported (new
evidence, a row added, a row the detector no longer proposes removed; orchestrator ruling F17).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import asm
from .functions import KIND_GAME, FunctionRow
from .mechanics import ASM_VERDICTS, DATA_TAGS, AsmRow
from .x86 import Insn

if TYPE_CHECKING:
    from .check import ExeInputs

TAGS = ("unaligned", "stack-frame", "enter", "pushal", "iretd", "nop-pad", "library-span",
        *DATA_TAGS)  # the data-in-code tags last, so existing evidence keeps its order (07-44)
(UNALIGNED, STACK_FRAME, ENTER, PUSHAL, IRETD, NOP_PAD, LIBRARY_SPAN,
 NO_TERMINATOR, TEXT, ZERO_FILL, BAD_DECODE) = TAGS
ALIGNMENT = 16  # Watcom aligns every C function start to 16 bytes
FRAME_WINDOW = 4  # instructions searched for `push ebp; mov ebp, esp` (saved registers first)
FIRST_STACK_ARG = 8  # [ebp + 8]: the first argument above the saved ebp and return address
NOP_RUN = 3
TERMINATORS = frozenset({"ret", "retf", "iret", "iretd", "jmp", "ljmp"})  # flow ends here
TEXT_RUN = 6  # printable ASCII bytes ended by a zero byte: a C string
ZERO_RUN = ALIGNMENT  # longer than any alignment filler, which is at most ALIGNMENT - 1 bytes
MAX_INSN_BYTES = 15  # the longest x86 instruction: a RawByte this close to the end may be cut
PRINTABLE_LOW, PRINTABLE_HIGH = 0x20, 0x7E  # printable ASCII: space through tilde
VERDICT_ASM, VERDICT_UNCLEAR = "asm", "unclear"  # two of mechanics.ASM_VERDICTS
LIBRARY_UNITS = {
    "ufo2p": ("u_000161b4", "u_000c8e40", "u_000c1b4b"),
    "tacp": ("u_000cc150",),
}
SEPARATOR = ";"
_MNEMONIC_TAGS = {"enter": ENTER, "pushal": PUSHAL, "pushad": PUSHAL, "pusha": PUSHAL,
                  "iretd": IRETD, "iret": IRETD}  # fmt: skip
_ASM_TAGS = frozenset({STACK_FRAME, ENTER, PUSHAL, IRETD, NOP_PAD})
_LISTED = frozenset({UNALIGNED, LIBRARY_SPAN, *DATA_TAGS})  # a game row with one is proposed
_FRAME = ("push", "ebp", "mov", "ebp, esp")  # push ebp; mov ebp, esp
_STACK_ARG = re.compile(r"\[ebp \+ (0x[0-9a-f]+|\d+)\]")


class AsmClassError(ValueError):
    """A library unit named in LIBRARY_UNITS is not in the EXE's units.csv."""


# ---- tags ----


Decoded = tuple[bytes, list[asm.Item]]  # a row's bytes and its asm.walk items


def _walk(exe: ExeInputs, index: asm.FixupIndex, row: FunctionRow) -> Decoded:
    """The row's bytes and its decode (asm.walk, once per row)."""
    sites = asm.row_sites(row, index.overlapping(row.start, row.end))
    code = bytes(exe.flat[row.start : row.end])
    return code, list(asm.walk(code, row.start, sites))


def _insns(items: Sequence[asm.Item]) -> list[Insn]:
    return [item for item in items if isinstance(item, Insn)]


def _has_frame(insns: Sequence[Insn]) -> bool:
    head = insns[:FRAME_WINDOW]
    pairs = zip(head, head[1:], strict=False)
    return any((a.mnemonic, a.op_str, b.mnemonic, b.op_str) == _FRAME for a, b in pairs)


def _reads_stack_arg(insns: Sequence[Insn]) -> bool:
    return any(int(m.group(1), 0) >= FIRST_STACK_ARG
               for insn in insns for m in _STACK_ARG.finditer(insn.op_str))  # fmt: skip


def _nop_pad(insns: Sequence[Insn]) -> bool:
    """NOP_RUN or more consecutive `nop`s with a non-nop instruction after them in the row."""
    run = 0
    for insn in insns:
        if insn.mnemonic == "nop":
            run += 1
            continue
        if run >= NOP_RUN:
            return True
        run = 0
    return False


def _code_tags(insns: Sequence[Insn]) -> set[str]:
    tags = {_MNEMONIC_TAGS[i.mnemonic] for i in insns if i.mnemonic in _MNEMONIC_TAGS}
    if _has_frame(insns) and _reads_stack_arg(insns):
        tags.add(STACK_FRAME)
    if _nop_pad(insns):
        tags.add(NOP_PAD)
    return tags


def _spans(exe: ExeInputs, library: Sequence[str]) -> list[tuple[int, int]]:
    units = {unit.unit: unit for unit in exe.units}
    missing = [name for name in library if name not in units]
    if missing:
        raise AsmClassError(f"{exe.stem}: library unit(s) {', '.join(missing)} not in units.csv "
                            "(re-cut? update asmclass.LIBRARY_UNITS)")  # fmt: skip
    return [(units[name].start, units[name].end) for name in library]


# ---- data-in-code evidence (07-44) ----


@dataclass(frozen=True)
class DataFacts:
    """What the data tags read from one row: counts and a mnemonic, never bytes (T-07-132)."""

    size: int
    terminator: bool  # a TERMINATORS mnemonic decodes in the row
    text_run: int  # the longest printable ASCII run ended by a zero byte
    zero_run: int  # the longest run of zero bytes
    zeros: int  # zero bytes in the row
    early_raw: int  # RawBytes more than MAX_INSN_BYTES bytes before the row end
    last_mnemonic: str  # the last decoded instruction's mnemonic ("" when none decodes)


def _text_run(code: bytes) -> int:
    best = run = 0
    for byte in code:
        if byte == 0:
            best = max(best, run)
        run = run + 1 if PRINTABLE_LOW <= byte <= PRINTABLE_HIGH else 0
    return best


def _zero_run(code: bytes) -> int:
    best = run = 0
    for byte in code:
        run = run + 1 if byte == 0 else 0
        best = max(best, run)
    return best


def _facts(row: FunctionRow, code: bytes, items: Sequence[asm.Item]) -> DataFacts:
    insns = _insns(items)
    cut = row.end - MAX_INSN_BYTES
    early = sum(1 for item in items if isinstance(item, asm.RawByte) and item.va < cut)
    last = insns[-1].mnemonic if insns else ""
    return DataFacts(size=len(code), terminator=any(i.mnemonic in TERMINATORS for i in insns),
                     text_run=_text_run(code), zero_run=_zero_run(code), zeros=code.count(0),
                     early_raw=early, last_mnemonic=last)  # fmt: skip


def data_facts(exe: ExeInputs, index: asm.FixupIndex, row: FunctionRow) -> DataFacts:
    """The data-in-code facts of one row (decoded once): what `_data_tags` reads and the
    owner's evidence report shows."""
    code, items = _walk(exe, index, row)
    return _facts(row, code, items)


def _data_tags(facts: DataFacts) -> set[str]:
    tags = set()
    if not facts.terminator:
        tags.add(NO_TERMINATOR)
    if facts.text_run >= TEXT_RUN:
        tags.add(TEXT)
    if facts.size and (facts.zeros == facts.size or facts.zero_run >= ZERO_RUN):
        tags.add(ZERO_FILL)
    if facts.early_raw:
        tags.add(BAD_DECODE)
    return tags


def _tags(row: FunctionRow, insns: Sequence[Insn],
          spans: Sequence[tuple[int, int]]) -> set[str]:  # fmt: skip
    tags = _code_tags(insns)
    if row.start % ALIGNMENT:
        tags.add(UNALIGNED)
    if any(lo <= row.start < hi for lo, hi in spans):
        tags.add(LIBRARY_SPAN)
    return tags


def _verdict(tags: set[str]) -> str:
    if LIBRARY_SPAN in tags or (UNALIGNED in tags and tags & _ASM_TAGS):
        return VERDICT_ASM
    return VERDICT_UNCLEAR


def classify(exe: ExeInputs, *, library: Sequence[str] | None = None) -> list[AsmRow]:
    """The proposed asm list rows of one EXE, by address: every game row that is unaligned, in a
    library unit (`library`, default LIBRARY_UNITS[exe.stem]) or carries a data-in-code tag
    (07-44), with its tags and proposed verdict. Each game row is decoded once. No such row: an
    empty list."""
    names = LIBRARY_UNITS.get(exe.stem, ()) if library is None else library
    spans = _spans(exe, names)
    index = asm.FixupIndex(exe.fixups)
    rows = []
    for row in sorted(exe.rows, key=lambda r: r.start):
        if row.kind != KIND_GAME:
            continue
        code, items = _walk(exe, index, row)
        tags = _tags(row, _insns(items), spans) | _data_tags(_facts(row, code, items))
        if not tags & _LISTED:
            continue
        evidence = SEPARATOR.join(tag for tag in TAGS if tag in tags)
        rows.append(AsmRow(exe.stem, row.start, evidence, _verdict(tags)))
    return rows


# ---- the verdict-preserving merge ----


def _key(row: AsmRow) -> tuple[str, int]:
    return row.exe, row.address


def _label(row: AsmRow, what: str) -> str:
    return f"{row.exe} 0x{row.address:08X} {what}"


def merge(existing: Sequence[AsmRow], proposed: Sequence[AsmRow]) -> tuple[list[AsmRow],
                                                                            list[str]]:  # fmt: skip
    """The new list and its tool-owned changes. A row in both keeps its verdict and reason and
    takes the proposal's evidence ("evidence" when that differs); a proposed row not yet listed
    comes in as proposed ("added"); a listed row no longer proposed leaves ("removed"). Verdicts
    and reasons are never compared with the proposal (F17). Rows keep proposal order; the
    caller writes them through mechanics.format_asm_csv, which sorts."""
    old = {_key(row): row for row in existing}
    new_keys = {_key(row) for row in proposed}
    rows, changed = [], []
    for row in proposed:
        before = old.get(_key(row))
        if before is None:
            rows.append(row)
            changed.append(_label(row, "added"))
            continue
        rows.append(AsmRow(row.exe, row.address, row.evidence, before.verdict, before.reason))
        if before.evidence != row.evidence:
            changed.append(_label(row, "evidence"))
    changed += [_label(row, "removed") for row in existing if _key(row) not in new_keys]
    return rows, changed


def verdict_counts(rows: Sequence[AsmRow]) -> dict[str, int]:
    """Rows per verdict, in ASM_VERDICTS order."""
    counts = Counter(row.verdict for row in rows)
    return {verdict: counts[verdict] for verdict in ASM_VERDICTS}
