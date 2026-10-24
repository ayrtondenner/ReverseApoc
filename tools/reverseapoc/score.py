# Derived from KKND-Decomp tools/score_functions.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""The PITFALLS P16 filter and the easiest-first ranking of the first-match candidates (D-15).

A row survives the filter when it is game code outside runtime.csv and:

- has no jump table: no LE fixup inside it whose target lies in a functions.csv row (code);
- references no string: no data target holding at least 3 printable bytes then NUL;
- has no straddling fixup: no field crossing a page boundary or the row's own boundary;
- has no non-off32 LE fixup (sel16 and the rest; orchestrator ruling F11): omf2elf and the
  relocation check reject those anyway;
- has at least one `call rel32` and one absolute (off32) fixup to data, so the relocation check
  is exercised;
- calls (and jumps out to) only functions.csv row starts whose linker name symbols.py produces
  and resolves back to the same address;
- references every data target at an exact address: the target's `_D_` name (or symbols.csv
  name) resolves back to it, so each one is one extern.

Survivors are ranked by (has a __CHK prologue, score, address): a function without a stack
check comes first, so the default `-s` applies; then the smaller score; then the lower address.
The score uses the KKND weights (see `score`). Features are read with asm.walk, which decodes
with x86.decode and treats LE fixup sites at instruction starts as data, so the scorer and the
listings see the same instructions.

Nothing here prints bytes: a candidate is its address, name, size, score and reasons.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Container, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from .asm import FixupIndex, row_sites, walk
from .functions import KIND_DATA_IN_CODE, KIND_GAME, KIND_RUNTIME, FunctionRow
from .le import SRC_OFF32, Fixup
from .symbols import SymbolError, SymbolTable
from .x86 import Insn

LE_PAGE_SIZE = 0x1000  # the page size wlink writes; fixups crossing it are straddlers
STRING_MIN = 3  # printable bytes before the NUL that make a data target a string
_PRINTABLE = frozenset(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}
_NUL = 0
_PUSH_IMM32 = "push"
_FRAME = ("push", "ebp")

# KKND score_functions.py weights (lower is easier).
WEIGHT_CALL = 12
WEIGHT_CS_TABLE = 80
WEIGHT_FPU = 40
WEIGHT_DATA_REF = 30
WEIGHT_RET_N = 20
WEIGHT_FAR_RETURN = 200
WEIGHT_NO_FRAME = 100

REASON_RUNTIME = "runtime"
REASON_NOT_GAME = "not game code"
REASON_JUMP_TABLE = "jump table"
REASON_STRING = "string reference"
REASON_STRADDLER = "straddling fixup"
REASON_OTHER_FIXUP = "non-off32 fixup"
REASON_NO_CALL = "no call rel32"
REASON_NO_ABS = "no absolute fixup"
REASON_CALL_TARGET = "call target is not a nameable functions.csv start"
REASON_DATA_EXACT = "data target not at an exact address"


class ScoreError(ValueError):
    """The scorer was asked for something it cannot give (e.g. --top below 1)."""


@dataclass(frozen=True, slots=True)
class Features:
    size: int
    calls: int  # direct call rel32 instructions
    call_targets_ok: bool  # every call (and jump out of the row) lands on a nameable row start
    abs_fixups: int  # off32 fixups whose target is data (the D_ references)
    data_exact: bool  # every data target resolves through its own linker name
    jump_table: bool  # an LE fixup inside the row targets code
    string_ref: bool  # a data target is a NUL-terminated string of >= STRING_MIN bytes
    straddler: bool  # a fixup field crosses a page or the row boundary
    chk: bool  # starts with push imm32; call __CHK
    fpu: int  # x87 instructions
    ret_n: bool  # ret with an immediate (stack-passed arguments)
    frame: bool  # push ebp opens the function (after a __CHK pair, if any)
    cs_table: int  # operands addressing through cs:
    other_fixups: int = 0  # LE fixups of any kind other than off32 (ruling F11)
    far_return: bool = False  # retf or iretd


@dataclass(frozen=True, slots=True)
class Candidate:
    address: int
    name: str
    size: int
    score: int
    reasons: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {"address": f"0x{self.address:08X}", "name": self.name, "size": self.size,
                "score": self.score, "reasons": list(self.reasons)}  # fmt: skip


# ---- features ----


def _is_code(symbols: SymbolTable, va: int) -> bool:
    """A target inside a functions.csv row (not a data-in-code row) is code. Anything else is
    treated as data, and a data target outside every data object fails `data_exact`."""
    row = symbols.containing(va)
    return row is not None and row.kind != KIND_DATA_IN_CODE


def _is_string(flat: bytes | bytearray, va: int) -> bool:
    """At least STRING_MIN printable bytes at `va`, then a NUL."""
    for count, byte in enumerate(flat[va : va + 4096]):
        if byte == _NUL:
            return count >= STRING_MIN
        if byte not in _PRINTABLE:
            return False
    return False


def _straddles(fixup: Fixup, row: FunctionRow, page_size: int) -> bool:
    first, last = fixup.src_va, fixup.src_va + fixup.size - 1
    if first // page_size != last // page_size:
        return True
    return first < row.start <= last or first < row.end <= last


def _resolves(symbols: SymbolTable, va: int, *, data: bool = False) -> bool:
    """The linker name of `va` exists and names `va` again (no ambiguous runtime name)."""
    try:
        return symbols.address_of(symbols.linker_name(va, data=data)) == va
    except SymbolError:
        return False


def _nameable_start(symbols: SymbolTable, va: int) -> bool:
    return symbols.function_at(va) is not None and _resolves(symbols, va)


def _branch_target(insn: Insn, fixups: dict[int, Fixup]) -> int | None:
    if insn.branch_target is None:
        return None
    fixup = fixups.get(insn.rel32_field) if insn.rel32_field is not None else None
    return fixup.target_va if fixup is not None else insn.branch_target


def _has_chk(insns: Sequence[Insn], fixups: dict[int, Fixup], chk_targets: Container[int]) -> bool:
    if len(insns) < 2 or insns[0].mnemonic != _PUSH_IMM32 or not insns[1].is_call:
        return False
    target = _branch_target(insns[1], fixups)
    return target is not None and target in chk_targets


def _instruction_features(
    insns: Sequence[Insn], row: FunctionRow, fixups: dict[int, Fixup], symbols: SymbolTable
) -> dict[str, Any]:
    calls = 0
    targets_ok = True
    for insn in insns:
        target = _branch_target(insn, fixups)
        if target is None:
            continue
        leaves = not row.start <= target < row.end
        if insn.is_call and insn.rel32_field is not None:
            calls += 1
        if insn.is_call or leaves:
            targets_ok = targets_ok and _nameable_start(symbols, target)
    return {
        "calls": calls,
        "call_targets_ok": targets_ok,
        "fpu": sum(1 for insn in insns if insn.mnemonic.startswith("f")),
        "ret_n": any(insn.mnemonic == "ret" and insn.op_str for insn in insns),
        "far_return": any(insn.mnemonic in ("retf", "iretd", "iret") for insn in insns),
        "cs_table": sum(insn.op_str.count("cs:") for insn in insns),
    }


def _fixup_features(
    fixups: Iterable[Fixup], row: FunctionRow, *, flat: bytes | bytearray,
    symbols: SymbolTable, page_size: int,
) -> dict[str, Any]:  # fmt: skip
    abs_fixups = other = 0
    jump_table = string_ref = straddler = False
    data_exact = True
    for fixup in fixups:
        straddler = straddler or _straddles(fixup, row, page_size)
        if fixup.kind != SRC_OFF32:
            other += 1
            continue
        if _is_code(symbols, fixup.target_va):
            jump_table = True  # code-to-code: a jump or pointer table
            continue
        abs_fixups += 1
        string_ref = string_ref or _is_string(flat, fixup.target_va)
        data_exact = data_exact and _resolves(symbols, fixup.target_va, data=True)
    return {"abs_fixups": abs_fixups, "other_fixups": other, "jump_table": jump_table,
            "string_ref": string_ref, "straddler": straddler, "data_exact": data_exact}  # fmt: skip


def features(
    row: FunctionRow,
    *,
    flat: bytes | bytearray,
    fixups: Iterable[Fixup],
    symbols: SymbolTable,
    chk_targets: Container[int] = frozenset(),
    page_size: int = LE_PAGE_SIZE,
) -> Features:
    """The features of one row. `flat` is load_flat(relocate=False); `fixups` may be every LE
    fixup or only those near the row; `chk_targets` are the addresses of __CHK."""
    inside = [fx for fx in fixups if fx.src_va < row.end and fx.src_va + fx.size > row.start]
    by_field = {fx.src_va: fx for fx in inside}
    items = walk(bytes(flat[row.start : row.end]), row.start, row_sites(row, inside))
    insns = [item for item in items if isinstance(item, Insn)]
    chk = _has_chk(insns, by_field, chk_targets)
    body = insns[2:] if chk else insns
    frame = bool(body) and (body[0].mnemonic, body[0].op_str) == _FRAME
    return Features(
        size=row.end - row.start,
        chk=chk,
        frame=frame,
        **_instruction_features(insns, row, by_field, symbols),
        **_fixup_features(inside, row, flat=flat, symbols=symbols, page_size=page_size),
    )


# ---- filter and score ----


def rejections(
    row: FunctionRow, feats: Features, *, runtime_starts: Container[int] = frozenset()
) -> list[str]:
    """Every P16 reason the row cannot be a first match; empty when it is a candidate."""
    checks = [
        (row.kind == KIND_RUNTIME or row.start in runtime_starts, REASON_RUNTIME),
        (row.kind not in (KIND_GAME, KIND_RUNTIME), REASON_NOT_GAME),
        (feats.jump_table, REASON_JUMP_TABLE),
        (feats.string_ref, REASON_STRING),
        (feats.straddler, REASON_STRADDLER),
        (feats.other_fixups > 0, REASON_OTHER_FIXUP),
        (feats.calls == 0, REASON_NO_CALL),
        (feats.abs_fixups == 0, REASON_NO_ABS),
        (not feats.call_targets_ok, REASON_CALL_TARGET),
        (not feats.data_exact, REASON_DATA_EXACT),
    ]
    return [reason for failed, reason in checks if failed]


def score(feats: Features) -> int:
    """KKND score_functions.py, lower is easier: size in bytes + 12 per call + 80 per cs: operand
    + 40 per x87 instruction + 30 per D_ reference + 20 for `ret N` + 200 for retf/iretd + 100
    when no `push ebp` frame opens the function."""
    return (
        feats.size
        + WEIGHT_CALL * feats.calls
        + WEIGHT_CS_TABLE * feats.cs_table
        + WEIGHT_FPU * feats.fpu
        + WEIGHT_DATA_REF * feats.abs_fixups
        + WEIGHT_RET_N * feats.ret_n
        + WEIGHT_FAR_RETURN * feats.far_return
        + WEIGHT_NO_FRAME * (not feats.frame)
    )


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def score_reasons(feats: Features) -> tuple[str, ...]:
    """The terms behind a score, in words."""
    reasons = [f"size {feats.size}", _plural(feats.calls, "call"),
               _plural(feats.abs_fixups, "D_ reference")]  # fmt: skip
    optional = [
        (feats.cs_table, _plural(feats.cs_table, "cs: operand")),
        (feats.fpu, _plural(feats.fpu, "x87 instruction")),
        (feats.ret_n, "ret N"),
        (feats.far_return, "far return"),
        (not feats.frame, "no push ebp frame"),
        (feats.chk, "__CHK prologue"),
    ]
    return tuple(reasons + [text for present, text in optional if present])


@dataclass(frozen=True)
class Assessment:
    row: FunctionRow
    features: Features
    rejected: tuple[str, ...]


def assess(
    rows: Iterable[FunctionRow],
    *,
    flat: bytes | bytearray,
    fixups: Iterable[Fixup],
    symbols: SymbolTable,
    chk_targets: Container[int] = frozenset(),
    runtime_starts: Container[int] = frozenset(),
    page_size: int = LE_PAGE_SIZE,
) -> list[Assessment]:
    """Features and P16 rejections of every row, in address order."""
    index = FixupIndex(fixups)
    out = []
    for row in sorted(rows, key=lambda r: r.start):
        near = index.overlapping(row.start, row.end)
        feats = features(row, flat=flat, fixups=near, symbols=symbols, chk_targets=chk_targets,
                         page_size=page_size)  # fmt: skip
        out.append(Assessment(row, feats, tuple(rejections(row, feats,
                                                           runtime_starts=runtime_starts))))
    return out


def candidates(assessments: Iterable[Assessment], symbols: SymbolTable) -> list[Candidate]:
    """The survivors, easiest first: no __CHK prologue first, then score, then address."""
    survivors = [a for a in assessments if not a.rejected]
    survivors.sort(key=lambda a: (a.features.chk, score(a.features), a.row.start))
    return [Candidate(a.row.start, symbols.c_name(a.row.start), a.features.size,
                      score(a.features), score_reasons(a.features)) for a in survivors]  # fmt: skip


def rank(
    rows: Iterable[FunctionRow],
    *,
    flat: bytes | bytearray,
    fixups: Iterable[Fixup],
    symbols: SymbolTable,
    chk_targets: Container[int] = frozenset(),
    runtime_starts: Container[int] = frozenset(),
    page_size: int = LE_PAGE_SIZE,
) -> list[Candidate]:
    """The P16 survivors of `rows`, easiest first."""
    assessments = assess(rows, flat=flat, fixups=fixups, symbols=symbols, chk_targets=chk_targets,
                         runtime_starts=runtime_starts, page_size=page_size)  # fmt: skip
    return candidates(assessments, symbols)


@dataclass(frozen=True)
class ScoreReport:
    exe: str
    functions: int
    rejected: dict[str, int]  # reason -> rows it rejects (a row may count under several)
    candidates: tuple[Candidate, ...]  # every survivor, easiest first
    top: int

    @classmethod
    def build(cls, exe: str, assessments: Sequence[Assessment], symbols: SymbolTable,
              top: int) -> ScoreReport:  # fmt: skip
        if top < 1:
            raise ScoreError(f"--top must be at least 1, not {top}")
        counts = Counter(reason for a in assessments for reason in a.rejected)
        return cls(exe, len(assessments), dict(sorted(counts.items())),
                   tuple(candidates(assessments, symbols)), top)  # fmt: skip

    def format(self) -> str:
        rejected = ", ".join(f"{reason} {n}" for reason, n in self.rejected.items()) or "none"
        lines = [f"{self.exe}: {len(self.candidates)} of {self.functions} functions pass the P16 "
                 f"filter (rejected: {rejected})"]  # fmt: skip
        for c in self.candidates[: self.top]:
            lines.append(f"  0x{c.address:08X}  {c.name}  size {c.size}  score {c.score}  "
                         f"({'; '.join(c.reasons)})")  # fmt: skip
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        return {"exe": self.exe, "functions": self.functions, "eligible": len(self.candidates),
                "rejected": self.rejected,
                "candidates": [c.to_json() for c in self.candidates[: self.top]]}  # fmt: skip
