# SPDX-License-Identifier: GPL-3.0-or-later
"""The split-row detector behind `mechanics splits` (07-45, owner ruling 2026-10-31).

D-23 evidence, read-only: it reads orig/ and the committed config and writes nothing.

A split pair is two game rows (A, B) of functions.csv that touch (A's end is B's start) where A
decodes no asmclass.TERMINATORS mnemonic, so control runs out of A straight into B. Such an A is
exactly an asm-list `no-terminator` row. Each pair gets one class, decided in this order:

- `data`: A decodes no instruction other than filler, A holds an LE pointer item (a table), or A
  or B carries a content data tag (CONTENT_TAGS: text-run, zero-fill, bad-decode). 07-44's
  domain: the owner rules such rows through the asm list;
- `fall-through`: B is called, or jumped to unconditionally from a row other than A and B, or
  its address is taken (an instruction operand or the data object) while B also looks like a
  function: it starts with a terminator or a prologue and decodes a terminator;
- `label`: B is reached only by pointer items inside code rows (a jump table) or by conditional
  jumps from another row;
- `unclear`: anything else.

A taken address alone is no function evidence, because code also takes the address of a data
table (`mov reg, offset table`); B must look like a function too. A conditional jump is no
function evidence either: it is how a branch reaches a label. A jump from A or B itself never
counts.

`fall-through` is the shape Watcom is expected to leave: units.py's docstring (05-RESEARCH
Pattern 4) says the compiler lets one function fall through into the next, and 07-29 (F-0005)
matched func_00061F30 only while the C of func_00061F50 followed it in the same file. A C
function whose last statement calls the function laid out right after it can lose its tail
jump, so A ends without a ret and B is a real function.

Only a `label` pair is a merge candidate. Merging any other pair would leave its calls, jumps
or pointers aimed into the middle of a row, which no C source produces, so the gate could never
match the merged row.

A pair also carries the committed signed list's verdict of A (`a_verdict`, context only: the
class never reads it) and a `conflict` flag: the list rules A `asm` with an owner reason
(07-44) while the class is `fall-through` or `label`.

Pointer references are counted by where the fixup field lies: `taken` inside a decoded
instruction of a code row (game, thunk or runtime), `table` at a pointer item of a code row or
anywhere else in the code object (a data-in-code row, a gap), and `data_refs` outside the code
object. Output holds addresses, sizes, counts, unit names, class words and mnemonics only,
never bytes or operand text (T-07-136).
"""

from __future__ import annotations

import bisect
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import asm, asmclass, locate, mechanics
from .callgraph import WALKED_KINDS
from .functions import KIND_GAME, KIND_RUNTIME, KIND_THUNK, FunctionRow
from .le import SRC_OFF32, SRC_PTR1632
from .mechanics import AsmRow
from .status import MATCHED
from .x86 import Insn, is_alignment_filler, is_filler

if TYPE_CHECKING:
    from .check import ExeInputs

PUSH, SUB, STACK_POINTER = "push", "sub", "esp"
PROLOGUE_MNEMONICS = (PUSH, SUB)  # `push`, or a `sub` whose operand starts with esp
CONTENT_TAGS = (asmclass.TEXT, asmclass.ZERO_FILL, asmclass.BAD_DECODE)
CLASSES = ("data", "fall-through", "label", "unclear")
DATA, FALL_THROUGH, LABEL, UNCLEAR = CLASSES
B_HEADS = ("terminator", "prologue", "other")
HEAD_TERMINATOR, HEAD_PROLOGUE, HEAD_OTHER = B_HEADS
POINTER_KINDS = frozenset({SRC_OFF32, SRC_PTR1632})  # absolute fixups that hold an address
CODE_KINDS = frozenset({KIND_GAME, KIND_THUNK, KIND_RUNTIME})  # the rows decoded as code
NO_VERDICT = "-"  # A is not on the signed list, or the list is not signed
NONE = "-"  # an empty text cell
_TAKEN, _TABLE = "taken", "table"
_CONFLICT_CLASSES = frozenset({FALL_THROUGH, LABEL})


@dataclass(frozen=True)
class SplitPair:
    """One split pair with its evidence: addresses, sizes, counts, names and mnemonics only."""

    exe: str
    a: int
    a_size: int
    a_unit: str
    a_last: str  # A's last non-filler mnemonic (NONE when none decodes)
    a_code: bool  # A decodes a non-filler instruction
    a_items: bool  # A holds an LE pointer item
    b: int
    b_size: int
    b_unit: str
    b_head: str  # one of B_HEADS
    b_only_terminator: bool  # B decodes one terminator and nothing else but filler
    b_terminator: bool  # a TERMINATORS mnemonic decodes in B
    calls: int  # call sites aimed at B
    tail_jumps: int  # unconditional jumps aimed at B from rows other than A and B
    cond_jumps: int  # conditional jumps aimed at B from rows other than A and B
    taken: int  # pointer fixups to B inside a decoded instruction of a code row
    data_refs: int  # pointer fixups to B from outside the code object
    table: int  # pointer fixups to B at a pointer item (or elsewhere in the code object)
    same_unit: bool
    a_content: tuple[str, ...]  # A's CONTENT_TAGS
    b_content: tuple[str, ...]
    b_evidence: str  # B's functions.csv evidence cell
    a_verdict: str  # the signed list's verdict of A, else NO_VERDICT
    conflict: bool
    klass: str  # one of CLASSES ("class" in the JSON)


# ---- decoding and the reference index ----


@dataclass
class _Decoded:
    code: bytes
    items: list[asm.Item]


@dataclass
class _Refs:
    """Every reference to a code address, by target: one pass over the decoded code rows."""

    calls: Counter[int]
    jumps: dict[int, list[int]]  # target -> source row starts (unconditional)
    cond: dict[int, list[int]]  # target -> source row starts (conditional)
    pointers: dict[str, Counter[int]]  # _TAKEN / _TABLE / DATA_REFS -> target counts


_DATA_REFS = "data_refs"


def _code_range(exe: ExeInputs) -> tuple[int, int]:
    obj = next(obj for obj in exe.le.objects if obj.flags & asm.OBJ_EXECUTABLE)
    return obj.base, obj.end


def _decode_all(exe: ExeInputs) -> dict[int, tuple[FunctionRow, _Decoded]]:
    """Every code row decoded once (asmclass's walk), by start."""
    index = asm.FixupIndex(exe.fixups)
    decoded = {}
    for row in exe.rows:
        if row.kind not in CODE_KINDS:
            continue
        code, items = asmclass._walk(exe, index, row)
        decoded[row.start] = (row, _Decoded(code, items))
    return decoded


def _branches(decoded: Mapping[int, tuple[FunctionRow, _Decoded]], refs: _Refs) -> None:
    for start, (_row, dec) in decoded.items():
        for item in dec.items:
            if not isinstance(item, Insn) or item.branch_target is None:
                continue
            if item.is_call:
                refs.calls[item.branch_target] += 1
            elif item.is_jump:
                bucket = refs.cond if item.is_conditional else refs.jumps
                bucket[item.branch_target].append(start)


def _site_kinds(decoded: Mapping[int, tuple[FunctionRow, _Decoded]],
                sites: Sequence[int]) -> dict[int, str]:  # fmt: skip
    """_TAKEN for a pointer site inside a decoded instruction, _TABLE for one at an item."""
    kinds = {}
    for _row, dec in decoded.values():
        for item in dec.items:
            if isinstance(item, asm.DataItem):
                kinds[item.va] = _TABLE
                continue
            if not isinstance(item, Insn):
                continue
            low = bisect.bisect_left(sites, item.va)
            high = bisect.bisect_left(sites, item.va + item.size)
            kinds.update(dict.fromkeys(sites[low:high], _TAKEN))
    return kinds


def _index(exe: ExeInputs, decoded: Mapping[int, tuple[FunctionRow, _Decoded]]) -> _Refs:
    refs = _Refs(Counter(), defaultdict(list), defaultdict(list),
                 {_TAKEN: Counter(), _TABLE: Counter(), _DATA_REFS: Counter()})  # fmt: skip
    _branches(decoded, refs)
    lo, hi = _code_range(exe)
    pointers = [fx for fx in exe.fixups if fx.kind in POINTER_KINDS and lo <= fx.target_va < hi]
    kinds = _site_kinds(decoded, sorted({fx.src_va for fx in pointers}))
    for fx in pointers:
        where = kinds.get(fx.src_va, _TABLE) if lo <= fx.src_va < hi else _DATA_REFS
        refs.pointers[where][fx.target_va] += 1
    return refs


# ---- per-row facts ----


def _real_insns(items: Iterable[asm.Item]) -> list[Insn]:
    return [item for item in items if isinstance(item, Insn) and not is_filler(item)]


def _terminates(items: Iterable[asm.Item]) -> bool:
    return any(isinstance(i, Insn) and i.mnemonic in asmclass.TERMINATORS for i in items)


def _content(row: FunctionRow, dec: _Decoded) -> tuple[str, ...]:
    tags = asmclass._data_tags(asmclass._facts(row, dec.code, dec.items))
    return tuple(tag for tag in CONTENT_TAGS if tag in tags)


def _is_prologue(insn: Insn) -> bool:
    if insn.mnemonic == PUSH:
        return True
    return insn.mnemonic == SUB and insn.op_str.startswith(STACK_POINTER)


def _head(items: Sequence[asm.Item]) -> str:
    first = items[0] if items else None
    if not isinstance(first, Insn):
        return HEAD_OTHER
    if first.mnemonic in asmclass.TERMINATORS:
        return HEAD_TERMINATOR
    return HEAD_PROLOGUE if _is_prologue(first) else HEAD_OTHER


def _only_terminator(items: Sequence[asm.Item]) -> bool:
    rest = [i for i in items if not (isinstance(i, Insn) and is_filler(i))]
    return (len(rest) == 1 and isinstance(rest[0], Insn)
            and rest[0].mnemonic in asmclass.TERMINATORS)  # fmt: skip


def _klass(pair: dict[str, Any]) -> str:
    if not pair["a_code"] or pair["a_items"] or pair["a_content"] or pair["b_content"]:
        return DATA
    function_like = pair["b_head"] in (HEAD_TERMINATOR, HEAD_PROLOGUE) and pair["b_terminator"]
    if pair["calls"] + pair["tail_jumps"]:
        return FALL_THROUGH
    if pair["taken"] + pair["data_refs"]:
        return FALL_THROUGH if function_like else UNCLEAR
    if pair["table"] or pair["cond_jumps"]:
        return LABEL
    return UNCLEAR


def _others(sources: Sequence[int], a: int, b: int) -> int:
    return sum(1 for src in sources if src not in (a, b))


def _pair(exe: str, a: tuple[FunctionRow, _Decoded], b: tuple[FunctionRow, _Decoded],
          refs: _Refs, listed: Mapping[int, AsmRow]) -> SplitPair:  # fmt: skip
    (arow, adec), (brow, bdec) = a, b
    a_insns = _real_insns(adec.items)
    cells: dict[str, Any] = {
        "exe": exe, "a": arow.start, "a_size": arow.end - arow.start, "a_unit": arow.unit,
        "a_last": a_insns[-1].mnemonic if a_insns else NONE, "a_code": bool(a_insns),
        "a_items": any(isinstance(i, asm.DataItem) for i in adec.items),
        "b": brow.start, "b_size": brow.end - brow.start, "b_unit": brow.unit,
        "b_head": _head(bdec.items), "b_only_terminator": _only_terminator(bdec.items),
        "b_terminator": _terminates(bdec.items), "calls": refs.calls[brow.start],
        "tail_jumps": _others(refs.jumps.get(brow.start, ()), arow.start, brow.start),
        "cond_jumps": _others(refs.cond.get(brow.start, ()), arow.start, brow.start),
        "taken": refs.pointers[_TAKEN][brow.start],
        "data_refs": refs.pointers[_DATA_REFS][brow.start],
        "table": refs.pointers[_TABLE][brow.start], "same_unit": arow.unit == brow.unit,
        "a_content": _content(arow, adec), "b_content": _content(brow, bdec),
        "b_evidence": brow.evidence,
    }  # fmt: skip
    ruled = listed.get(arow.start)
    klass = _klass(cells)
    cells["a_verdict"] = ruled.verdict if ruled else NO_VERDICT
    cells["conflict"] = bool(ruled and ruled.verdict == mechanics.VERDICT_ASM and ruled.reason
                             and klass in _CONFLICT_CLASSES)  # fmt: skip
    return SplitPair(**cells, klass=klass)


def _touching(decoded: Mapping[int, tuple[FunctionRow, _Decoded]]):
    game = sorted((start, entry) for start, entry in decoded.items()
                  if entry[0].kind == KIND_GAME)  # fmt: skip
    for (_s, a), (_t, b) in zip(game, game[1:], strict=False):
        if a[0].end == b[0].start and not _terminates(a[1].items):
            yield a, b


def classify_splits(exe: ExeInputs, *, signed_list: Sequence[AsmRow] = ()) -> list[SplitPair]:
    """Every split pair of one EXE, by A's address, with its evidence and class.
    `signed_list` is the committed asm list when signed (`signed_list(config)`): context for
    `a_verdict` and `conflict` only."""
    decoded = _decode_all(exe)
    refs = _index(exe, decoded)
    listed = {row.address: row for row in signed_list if row.exe == exe.stem}
    return [_pair(exe.stem, a, b, refs, listed) for a, b in _touching(decoded)]


def signed_list(config_root: Path) -> list[AsmRow]:
    """The committed asm list when [asm_list] signs it as it stands; otherwise no rows (an
    unsigned or changed list gives no verdict, and `a_verdict` reads NO_VERDICT)."""
    root = Path(config_root)
    toml, path = root / mechanics.MECHANICS_TOML, root / mechanics.ASM_CSV
    if not toml.is_file() or not path.is_file():
        return []
    signoff = mechanics.load(toml).asm_list
    if not signoff.signed or mechanics.asm_list_sha256(path) != signoff.list_sha256:
        return []
    return mechanics.read_asm_list(path)


# ---- output ----


def counts(pairs: Iterable[SplitPair], exes: Iterable[str]) -> dict[str, dict[str, int]]:
    """Pairs per class, per EXE (every class named, zero included)."""
    found = Counter((pair.exe, pair.klass) for pair in pairs)
    return {exe: {klass: found[exe, klass] for klass in CLASSES} for exe in exes}


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def _tags(tags: Sequence[str]) -> str:
    return asmclass.SEPARATOR.join(tags) or NONE


def format_pair(pair: SplitPair) -> str:
    only = "(only)" if pair.b_only_terminator else ""
    unit = "same-unit" if pair.same_unit else "cross-unit"
    conflict = " CONFLICT" if pair.conflict else ""
    return (f"{pair.exe} 0x{pair.a:08X} +{pair.a_size} {pair.a_unit} last={pair.a_last} "
            f"code={_yes(pair.a_code)} items={_yes(pair.a_items)} -> 0x{pair.b:08X} "
            f"+{pair.b_size} {pair.b_unit} head={pair.b_head}{only} "
            f"terminator={_yes(pair.b_terminator)} calls={pair.calls} tail={pair.tail_jumps} "
            f"cond={pair.cond_jumps} taken={pair.taken} data={pair.data_refs} "
            f"table={pair.table} {unit} content={_tags(pair.a_content)}/{_tags(pair.b_content)} "
            f"evidence={pair.b_evidence} verdict={pair.a_verdict}{conflict} {pair.klass}")


def format_splits(pairs: Sequence[SplitPair], exes: Sequence[str]) -> str:
    """One line per pair, then one counts line per EXE."""
    lines = [format_pair(pair) for pair in pairs]
    for exe, per in counts(pairs, exes).items():
        total = sum(per.values())
        lines.append(f"{exe}: {total} pairs: " + ", ".join(f"{n} {k}" for k, n in per.items()))
    return "\n".join(lines)


def pair_json(pair: SplitPair) -> dict[str, Any]:
    """The pair's JSON object, in field order; addresses as 0x%08X, `klass` as "class"."""
    out: dict[str, Any] = {}
    for field in fields(pair):
        value = getattr(pair, field.name)
        if field.name in ("a", "b"):
            value = f"0x{value:08X}"
        elif isinstance(value, tuple):
            value = list(value)
        out["class" if field.name == "klass" else field.name] = value
    return out


def splits_json(pairs: Sequence[SplitPair], exes: Sequence[str]) -> dict[str, Any]:
    return {"pairs": [pair_json(pair) for pair in pairs], "counts": counts(pairs, exes)}


# ---- interior branches: suspected bad splits (`mechanics interior`) ----
#
# A game row whose call or jump lands strictly inside another game or thunk row (not on its
# start) points at a wrong boundary: no C source of one function branches into the middle of
# another, so neither row can match as cut. Runtime and data-in-code rows are not targets, as in
# callgraph's mid-row references (WALKED_KINDS): a Watcom library routine may have several
# entries, and functions.csv does not cut runtime rows. callgraph reports mid-row pointer
# fixups; this report reads the relative calls and jumps, which carry no fixup. Each such
# branch proposes one fix:
#
# - `split`: a call, or a tail-jump stub (a row whose first real instruction is a jmp followed
#   only by alignment filler, such as tacp's func_000AF170), lands on a function entry, so the
#   target row holds a missed split;
# - `merge`: any other jump lands on a label of the function it belongs to, so the source row,
#   the target row and every row between them are one function. Merge spans that share a row
#   are one merge.
#
# A fix that would cut or join a status.csv `matched` row is `review` instead: a matched row's
# boundaries are proven by the gate, so the branch crosses two real functions (a shared tail,
# say) and the owner looks at it; no change is proposed.
#
# Two kinds of branch are noise and only counted (`skipped`): one from or into a row that
# carries a CONTENT_TAGS tag (data read as code: text decodes as jcc, since bytes 0x70 to 0x7F
# are the letters p to DEL), and one whose destination is no instruction start of the decoded
# target row (a real branch lands on an instruction). The fixes are proposals for the owner,
# who rules functions.csv; nothing is written.

BRANCHES = ("call", "jmp", "jcc")
CALL, JMP, JCC = BRANCHES
ACTIONS = ("split", "merge", "review")
SPLIT, MERGE, REVIEW = ACTIONS
_SKIPPED = "skipped"


@dataclass(frozen=True)
class Interior:
    """One branch into the middle of another row: addresses, offsets, names and words only."""

    exe: str
    source: int  # the branching row's start
    source_unit: str
    site: int  # the branch instruction's offset into the source row
    branch: str  # one of BRANCHES
    target: int  # the target row's start
    target_unit: str
    offset: int  # the branch destination's offset into the target row (never 0)
    touching: bool  # one row ends where the other starts
    source_status: str  # status.csv's status of the row, else NONE
    target_status: str
    fix: str  # SPLIT or MERGE: what the branch alone proposes


@dataclass(frozen=True)
class Fix:
    """One proposed functions.csv change: split `rows[0]` at `at`, or merge `rows` into one;
    `review` when that split or merge would touch a matched row."""

    exe: str
    action: str  # one of ACTIONS
    rows: tuple[int, ...]  # row starts, by address
    at: int | None  # the split address; None for a merge


@dataclass(frozen=True)
class InteriorReport:
    exe: str
    suspects: tuple[Interior, ...]  # by source row, then site
    fixes: tuple[Fix, ...]  # splits by address, then merges by first row
    skipped: int  # noise: branches from or into content-tagged rows, or into no insn start


def _branch_word(insn: Insn) -> str:
    if insn.is_call:
        return CALL
    return JCC if insn.is_conditional else JMP


def _merges(spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """(first, last) row-start spans; spans that share a row are made one."""
    out: list[tuple[int, int]] = []
    for lo, hi in sorted(spans):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def _fix(exe: str, action: str, rows: Sequence[int], at: int | None,
         statuses: Mapping[int, str]) -> Fix:  # fmt: skip
    proven = any(statuses.get(row) == MATCHED for row in rows)
    return Fix(exe, REVIEW if proven else action, tuple(rows), at)


def _fixes(exe: str, suspects: Sequence[Interior], starts: Sequence[int],
           statuses: Mapping[int, str]) -> tuple[Fix, ...]:  # fmt: skip
    cuts = sorted({(s.target, s.target + s.offset) for s in suspects if s.fix == SPLIT})
    spans = [(min(s.source, s.target), max(s.source, s.target))
             for s in suspects if s.fix == MERGE]  # fmt: skip
    found = [_fix(exe, SPLIT, (row,), at, statuses) for row, at in cuts]
    for lo, hi in _merges(spans):
        rows = starts[bisect.bisect_left(starts, lo):bisect.bisect_right(starts, hi)]
        found.append(_fix(exe, MERGE, rows, None, statuses))
    return tuple(found)


def _stub(items: Sequence[asm.Item]) -> Insn | None:
    """The jmp of a tail-jump stub: the row's first real instruction is an unconditional jmp
    and only alignment filler follows it."""
    insns = _real_insns(items)
    if not insns or not insns[0].is_jump or insns[0].is_conditional:
        return None
    rest = items[list(items).index(insns[0]) + 1 :]
    filler = all(isinstance(item, Insn) and is_alignment_filler(item) for item in rest)
    return insns[0] if filler else None


def _interior(exe: str, row: FunctionRow, insn: Insn, stub: Insn | None, target: FunctionRow,
              statuses: Mapping[int, str]) -> Interior:  # fmt: skip
    return Interior(
        exe=exe, source=row.start, source_unit=row.unit, site=insn.va - row.start,
        branch=_branch_word(insn), target=target.start, target_unit=target.unit,
        offset=insn.branch_target - target.start,
        touching=row.end == target.start or target.end == row.start,
        source_status=statuses.get(row.start, NONE),
        target_status=statuses.get(target.start, NONE),
        fix=SPLIT if insn.is_call or insn is stub else MERGE)  # fmt: skip


class _Facts:
    """The decoded rows and the per-row facts the report needs, each computed once and only
    for the rows a branch reaches."""

    def __init__(self, exe: ExeInputs) -> None:
        self.decoded = _decode_all(exe)
        self.rows = locate._Rows(exe.rows)
        self._data: dict[int, bool] = {}
        self._heads: dict[int, frozenset[int]] = {}

    def target(self, row: FunctionRow, va: int) -> FunctionRow | None:
        """The game or thunk row other than `row` that `va` lies strictly inside of."""
        target = self.rows.containing(va)
        if target is None or target.kind not in WALKED_KINDS or va == target.start:
            return None
        return None if target.start == row.start else target

    def data(self, start: int) -> bool:
        """The decoded row at `start` carries a CONTENT_TAGS tag."""
        if start not in self._data:
            self._data[start] = bool(_content(*self.decoded[start]))
        return self._data[start]

    def lands(self, start: int, va: int) -> bool:
        """`va` is an instruction start of the decoded row at `start`."""
        if start not in self._heads:
            items = self.decoded[start][1].items
            self._heads[start] = frozenset(i.va for i in items if isinstance(i, Insn))
        return va in self._heads[start]

    def noise(self, row: FunctionRow, target: FunctionRow, va: int) -> bool:
        return self.data(row.start) or self.data(target.start) or not self.lands(target.start, va)


def interior_branches(exe: ExeInputs, *,
                      statuses: Mapping[int, str] | None = None) -> InteriorReport:  # fmt: skip
    """Every call or jump of a game row that lands inside another row, not on its start, with
    the proposed fixes. `statuses` maps a row start to its status.csv status: shown on each
    suspect, and a fix touching a matched row is REVIEW."""
    statuses = statuses or {}
    facts = _Facts(exe)
    suspects, skipped = [], 0
    for row, dec in sorted(facts.decoded.values(), key=lambda entry: entry[0].start):
        if row.kind != KIND_GAME:
            continue
        stub = _stub(dec.items)
        for insn in _real_insns(dec.items):
            target = None if insn.branch_target is None else facts.target(row, insn.branch_target)
            if target is None:
                continue
            if facts.noise(row, target, insn.branch_target):
                skipped += 1
                continue
            suspects.append(_interior(exe.stem, row, insn, stub, target, statuses))
    fixes = _fixes(exe.stem, suspects, facts.rows.starts, statuses)
    return InteriorReport(exe.stem, tuple(suspects), fixes, skipped)


def interior_counts(report: InteriorReport) -> dict[str, int]:
    """Suspects, then per branch word, the skipped branches, then fixes per action."""
    per = Counter(s.branch for s in report.suspects)
    fixes = Counter(f.action for f in report.fixes)
    return {"suspects": len(report.suspects), **{b: per[b] for b in BRANCHES},
            _SKIPPED: report.skipped, **{a: fixes[a] for a in ACTIONS}}  # fmt: skip


def format_interior(suspect: Interior) -> str:
    return (f"{suspect.exe} 0x{suspect.source:08X}+0x{suspect.site:X} {suspect.branch} -> "
            f"0x{suspect.target:08X}+0x{suspect.offset:X} "
            f"unit={suspect.source_unit}/{suspect.target_unit} "
            f"touching={_yes(suspect.touching)} "
            f"status={suspect.source_status}/{suspect.target_status} fix={suspect.fix}")


def format_fix(fix: Fix) -> str:
    """`split ROW at ADDR` or `merge ROWS (N rows)`; `review` in place of the verb when the
    fix touches a matched row."""
    if fix.at is not None:
        return f"{fix.exe} fix: {fix.action} 0x{fix.rows[0]:08X} at 0x{fix.at:08X}"
    rows = " ".join(f"0x{row:08X}" for row in fix.rows)
    return f"{fix.exe} fix: {fix.action} {rows} ({len(fix.rows)} rows)"


def format_interiors(reports: Sequence[InteriorReport]) -> str:
    """One line per suspect, then one per proposed fix, then one counts line per EXE."""
    lines = [format_interior(s) for report in reports for s in report.suspects]
    lines += [format_fix(fix) for report in reports for fix in report.fixes]
    for report in reports:
        per = interior_counts(report)
        lines.append(f"{report.exe}: " + ", ".join(f"{n} {k}" for k, n in per.items()))
    return "\n".join(lines)


def _interior_json(suspect: Interior) -> dict[str, Any]:
    """The suspect's JSON object, in field order; row starts as 0x%08X, offsets as 0x%X."""
    out: dict[str, Any] = {}
    for field in fields(suspect):
        value = getattr(suspect, field.name)
        if field.name in ("source", "target"):
            value = f"0x{value:08X}"
        elif field.name in ("site", "offset"):
            value = f"0x{value:X}"
        out[field.name] = value
    return out


def _fix_json(fix: Fix) -> dict[str, Any]:
    return {"exe": fix.exe, "action": fix.action, "rows": [f"0x{row:08X}" for row in fix.rows],
            "at": None if fix.at is None else f"0x{fix.at:08X}"}  # fmt: skip


def interiors_json(reports: Sequence[InteriorReport]) -> dict[str, Any]:
    return {"suspects": [_interior_json(s) for report in reports for s in report.suspects],
            "fixes": [_fix_json(fix) for report in reports for fix in report.fixes],
            "counts": {report.exe: interior_counts(report) for report in reports}}  # fmt: skip
