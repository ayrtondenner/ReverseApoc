# SPDX-License-Identifier: GPL-3.0-or-later
"""The D-23 asm detector: proposes the hand-written assembly list the owner signs (plan 07-20).

Rows the detector looks at: every game row whose start is off Watcom's 16-byte function alignment
(research: about 213 UFO2P / 216 TACP rows), and every game row inside a known library unit.
Each gets evidence tags (TAGS order):

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

The proposed verdict is `asm` for a library-span row or an unaligned row with any other tag, and
`unclear` for a row that is only unaligned (research A5 assumes most such rows are asm; the
owner rules them). The detector never decides alone: `unclear` rows stay in the C queue unless
the owner marks them `asm`, and only an owner-signed list leaves the must-match sets (D-23).

`merge` writes a re-run into an existing list without erasing a ruling. The tool owns the exe,
address and evidence columns, the owner the verdict and reason: an existing row keeps its
verdict and reason whatever the new proposal, and only a tool-owned change is reported (new
evidence, a row added, a row the detector no longer proposes removed; orchestrator ruling F17).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

from . import asm
from .functions import KIND_GAME, FunctionRow
from .mechanics import ASM_VERDICTS, AsmRow
from .x86 import Insn

if TYPE_CHECKING:
    from .check import ExeInputs

TAGS = ("unaligned", "stack-frame", "enter", "pushal", "iretd", "nop-pad", "library-span")
(UNALIGNED, STACK_FRAME, ENTER, PUSHAL, IRETD, NOP_PAD, LIBRARY_SPAN) = TAGS
ALIGNMENT = 16  # Watcom aligns every C function start to 16 bytes
FRAME_WINDOW = 4  # instructions searched for `push ebp; mov ebp, esp` (saved registers first)
FIRST_STACK_ARG = 8  # [ebp + 8]: the first argument above the saved ebp and return address
NOP_RUN = 3
VERDICT_ASM, VERDICT_UNCLEAR = "asm", "unclear"  # two of mechanics.ASM_VERDICTS
LIBRARY_UNITS = {
    "ufo2p": ("u_000161b4", "u_000c8e40", "u_000c1b4b"),
    "tacp": ("u_000cc150",),
}
SEPARATOR = ";"
_MNEMONIC_TAGS = {"enter": ENTER, "pushal": PUSHAL, "pushad": PUSHAL, "pusha": PUSHAL,
                  "iretd": IRETD, "iret": IRETD}  # fmt: skip
_ASM_TAGS = frozenset({STACK_FRAME, ENTER, PUSHAL, IRETD, NOP_PAD})
_FRAME = ("push", "ebp", "mov", "ebp, esp")  # push ebp; mov ebp, esp
_STACK_ARG = re.compile(r"\[ebp \+ (0x[0-9a-f]+|\d+)\]")


class AsmClassError(ValueError):
    """A library unit named in LIBRARY_UNITS is not in the EXE's units.csv."""


# ---- tags ----


def _insns(exe: ExeInputs, index: asm.FixupIndex, row: FunctionRow) -> list[Insn]:
    sites = asm.row_sites(row, index.overlapping(row.start, row.end))
    code = bytes(exe.flat[row.start : row.end])
    return [item for item in asm.walk(code, row.start, sites) if isinstance(item, Insn)]


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


def _tags(exe: ExeInputs, index: asm.FixupIndex, row: FunctionRow,
          spans: Sequence[tuple[int, int]]) -> set[str]:  # fmt: skip
    tags = _code_tags(_insns(exe, index, row))
    if row.start % ALIGNMENT:
        tags.add(UNALIGNED)
    if any(lo <= row.start < hi for lo, hi in spans):
        tags.add(LIBRARY_SPAN)
    return tags


def _verdict(tags: set[str]) -> str:
    if LIBRARY_SPAN in tags or (UNALIGNED in tags and tags & _ASM_TAGS):
        return VERDICT_ASM
    return VERDICT_UNCLEAR


def _candidates(exe: ExeInputs, spans: Sequence[tuple[int, int]]) -> Iterator[FunctionRow]:
    for row in sorted(exe.rows, key=lambda r: r.start):
        if row.kind != KIND_GAME:
            continue
        if row.start % ALIGNMENT or any(lo <= row.start < hi for lo, hi in spans):
            yield row


def classify(exe: ExeInputs, *, library: Sequence[str] | None = None) -> list[AsmRow]:
    """The proposed asm list rows of one EXE, by address: every unaligned game row and every
    game row in a library unit (`library`, default LIBRARY_UNITS[exe.stem]), with its tags and
    proposed verdict. No such row: an empty list."""
    names = LIBRARY_UNITS.get(exe.stem, ()) if library is None else library
    spans = _spans(exe, names)
    index = asm.FixupIndex(exe.fixups)
    rows = []
    for row in _candidates(exe, spans):
        tags = _tags(exe, index, row, spans)
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
