# Derived from KKND-Decomp tools/find_functions.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""Independent capstone function discovery: the second boundary list beside Ghidra's (SPL-02).

D-07 lets neither tool win a boundary disagreement by default: evidence from the LE decides. This
pass produces that evidence for every start it finds:

- `entry`: the LE entry point;
- `runtime`: a start the caller passes in (the runtime.csv module starts);
- `fixup`: the target of an absolute LE fixup (off32, or the offset half of ptr16:32) that lands
  in the code object: a function pointer in data or in an instruction operand;
- `call`: the static target of a `call rel32` reached by the descent.

A `jmp [reg*4+T]` whose displacement field is a fixup to T in the code object starts a jump
table: the run of consecutive code-to-code off32 fixups from T. The table is a data-in-code range,
its targets are case labels decoded as part of the same function, and neither the table entries
nor the jmp's own field count as `fixup` evidence. Watcom may place the table before the function
entry (a leading table, 05-RESEARCH Pattern 3).

It is a recursive descent with a worklist (no recursion) and a visited set over le.py's
unrelocated image (`load_flat(relocate=False)`). Bytes and relocations come only from le.py,
never from Ghidra (P4). Every operand that overlaps an LE fixup field is resolved through
`LE.fixups()` (`target_va`): wlink stored the object-relative `target_off` in every field
(05-RESEARCH Pitfall 1), so the raw field is never read as an address. An instruction start that
is an LE fixup site is inline data and ends decoding of that path.

All decoding goes through `x86.decode`, in windows clipped to the containing object's end so a
path never reads past it. The report holds addresses and counts only, never instruction bytes.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from . import x86
from .le import LE, SRC_OFF32, SRC_PTR1632, LEObject

_OBJ_EXECUTABLE = 0x0004  # LE object flag: executable
_POINTER_KINDS = frozenset({SRC_OFF32, SRC_PTR1632})  # fixups whose target_va is an address
_WINDOW = 0x200  # bytes handed to capstone per decode call (it decodes a whole buffer at once)
_MAX_INSN = 15  # longest x86 instruction: a shorter tail may hold a truncated one
_TABLE_ENTRY = 4  # bytes per jump-table entry: one off32 field
_TABLE_INDEX = "*4"  # the scaled index of a jump-table jmp operand, as capstone prints it

EVIDENCE_ENTRY = "entry"
EVIDENCE_RUNTIME = "runtime"
EVIDENCE_FIXUP = "fixup"
EVIDENCE_CALL = "call"
DISCOVERY_EVIDENCE = (EVIDENCE_CALL, EVIDENCE_ENTRY, EVIDENCE_FIXUP, EVIDENCE_RUNTIME)


class DiscoverError(ValueError):
    """The executable cannot be searched for functions (no code object)."""


@dataclass(frozen=True)
class Discovery:
    """What one discovery run found: starts with their evidence, the bytes decoded as code,
    jump tables as [start, end) data-in-code ranges, and the seeds outside the code object."""

    starts: tuple[int, ...]
    evidence: Mapping[int, frozenset[str]]
    decoded_bytes: int
    jump_tables: tuple[tuple[int, int], ...]
    ignored_seeds: int

    @property
    def jump_table_bytes(self) -> int:
        return sum(end - start for start, end in self.jump_tables)

    def evidence_counts(self) -> dict[str, int]:
        """Number of starts carrying each kind of evidence."""
        counts = dict.fromkeys(DISCOVERY_EVIDENCE, 0)
        for kinds in self.evidence.values():
            for kind in kinds:
                counts[kind] += 1
        return counts

    def to_json(self) -> dict[str, Any]:
        """Counts only: no addresses and no bytes of the executable."""
        return {
            "starts": len(self.starts),
            "evidence": self.evidence_counts(),
            "decoded_bytes": self.decoded_bytes,
            "jump_tables": len(self.jump_tables),
            "jump_table_bytes": self.jump_table_bytes,
            "ignored_seeds": self.ignored_seeds,
        }

    def __repr__(self) -> str:
        return f"Discovery({self.format()})"

    def format(self) -> str:
        counts = ", ".join(f"{kind} {n}" for kind, n in self.evidence_counts().items())
        return (
            f"{len(self.starts)} function starts ({counts}); "
            f"{self.decoded_bytes} bytes decoded; "
            f"{len(self.jump_tables)} jump tables ({self.jump_table_bytes} bytes); "
            f"{self.ignored_seeds} seeds outside the code object ignored"
        )


def code_objects(le: LE) -> list[LEObject]:
    """The executable objects of `le`."""
    return [obj for obj in le.objects if obj.flags & _OBJ_EXECUTABLE]


class _Image:
    """le.py's unrelocated image with its code objects and LE fixup sites."""

    def __init__(self, le: LE) -> None:
        self.code = code_objects(le)
        if not self.code:
            raise DiscoverError("the executable has no executable object")
        self.flat = le.load_flat(relocate=False)
        self.fixups = {fx.src_va: fx for fx in le.fixups()}
        self.sites = frozenset(self.fixups)

    def code_object(self, va: int) -> LEObject | None:
        return next((obj for obj in self.code if obj.contains(va)), None)


class _Descent(_Image):
    """State of one discovery run over an LE."""

    def __init__(self, le: LE) -> None:
        super().__init__(le)
        self.evidence: dict[int, set[str]] = defaultdict(set)
        self.visited: set[int] = set()
        self.decoded = 0
        self.pending: list[int] = []
        self.tables: dict[int, int] = {}  # jump table start -> end
        self.table_entries: set[int] = set()  # src_va of every jump-table entry

    def add_start(self, va: int, kind: str) -> bool:
        """Record `kind` evidence for a start at `va`; False when `va` is outside the code."""
        if self.code_object(va) is None:
            return False
        self.evidence[va].add(kind)
        self.pending.append(va)
        return True

    def code_pointer(self, src_va: int) -> int | None:
        """target_va of the absolute fixup at `src_va` when it points into the code object."""
        fx = self.fixups.get(src_va)
        if fx is None or fx.kind not in _POINTER_KINDS:
            return None
        return fx.target_va if self.code_object(fx.target_va) is not None else None

    def in_table(self, va: int) -> bool:
        return any(start <= va < end for start, end in self.tables.items())

    def pointer_targets(self) -> set[int]:
        """Targets of the code-pointing fixups that are function pointers: not a jump-table
        entry, and not a reference to a jump table (the jmp's own displacement field)."""
        targets = set()
        for src_va in self.fixups:
            target = self.code_pointer(src_va)
            if target is None or src_va in self.table_entries or self.in_table(target):
                continue
            targets.add(target)
        return targets

    def insns(self, va: int) -> Iterator[x86.Insn]:
        """Linear decode from `va` to the end of its object, a window at a time."""
        end = self.code_object(va).end
        pos = va
        while pos < end:
            stop = min(pos + _WINDOW, end)
            last = pos
            for insn in x86.decode(bytes(self.flat[pos:stop]), pos, data_sites=self.sites):
                last = insn.va + insn.size
                yield insn
            if last == pos or stop == end or last in self.sites or stop - last >= _MAX_INSN:
                return
            pos = last

    def walk(self, va: int) -> None:
        """Decode one path from `va` until a terminal instruction, a visited instruction, inline
        data, an undecodable byte or the object end."""
        for insn in self.insns(va):
            if insn.va in self.visited:
                return
            self.visited.add(insn.va)
            self.decoded += insn.size
            self.branch(insn)
            if insn.is_terminal:
                return

    def branch(self, insn: x86.Insn) -> None:
        target = insn.branch_target
        if target is None:
            self.jump_table(insn)
            return
        if self.code_object(target) is None:
            return
        if insn.is_call:
            self.add_start(target, EVIDENCE_CALL)
        else:
            self.pending.append(target)  # a jump continues the same function

    def table_of(self, insn: x86.Insn) -> int | None:
        """The jump table an indirect `jmp [reg*4+T]` reads: the code-pointing fixup inside the
        instruction (its displacement field) gives T."""
        if not (insn.is_jump and insn.is_terminal and _TABLE_INDEX in insn.op_str):
            return None
        fields = (self.code_pointer(va) for va in range(insn.va, insn.va + insn.size))
        return next((t for t in fields if t is not None), None)

    def jump_table(self, insn: x86.Insn) -> None:
        """Record the table behind a jump-table jmp and queue its case labels."""
        start = self.table_of(insn)
        if start is None or start in self.tables:
            return
        end = start
        while (case := self.code_pointer(end)) is not None and end not in self.table_entries:
            self.table_entries.add(end)
            self.pending.append(case)
            end += _TABLE_ENTRY
        if end > start:
            self.tables[start] = end

    def run(self) -> None:
        while self.pending:
            self.walk(self.pending.pop())

    def seed_pointers(self) -> None:
        """Seed function pointers until no new one appears: a descent from a pointer can find a
        jump table whose entries must not count as pointers."""
        seeded: set[int] = set()
        while new := self.pointer_targets() - seeded:
            for va in sorted(new):
                self.add_start(va, EVIDENCE_FIXUP)
            seeded |= new
            self.run()
        for va in seeded - self.pointer_targets():  # turned out to be a table entry's target
            self.drop_evidence(va, EVIDENCE_FIXUP)

    def drop_evidence(self, va: int, kind: str) -> None:
        kinds = self.evidence[va]
        kinds.discard(kind)
        if not kinds:
            del self.evidence[va]


def discover(le: LE, *, runtime_starts: Iterable[int] = ()) -> Discovery:
    """Recursive descent over `le`'s code object, seeded with the entry point, `runtime_starts`
    and the code-pointing absolute LE fixups."""
    descent = _Descent(le)
    ignored = 0
    seeds = [(le.entry_va, EVIDENCE_ENTRY)] if le.entry_va is not None else []
    seeds += [(va, EVIDENCE_RUNTIME) for va in sorted(set(runtime_starts))]
    for va, kind in seeds:
        if not descent.add_start(va, kind):
            ignored += 1
    descent.run()
    descent.seed_pointers()
    evidence = {va: frozenset(kinds) for va, kinds in sorted(descent.evidence.items())}
    return Discovery(
        starts=tuple(evidence),
        evidence=MappingProxyType(evidence),
        decoded_bytes=descent.decoded,
        jump_tables=tuple(sorted(descent.tables.items())),
        ignored_seeds=ignored,
    )


class _EndScan(_Image):
    """The D-07 end rule over the unrelocated image, with the jump tables as data-in-code."""

    def __init__(self, le: LE, tables: Iterable[tuple[int, int]]) -> None:
        super().__init__(le)
        self.tables = sorted(tables)
        self.table_starts = [start for start, _ in self.tables]

    def table_at(self, va: int) -> tuple[int, int] | None:
        """The jump table [start, end) containing `va`, else None."""
        i = bisect_right(self.table_starts, va) - 1
        if i < 0 or va >= self.tables[i][1]:
            return None
        return self.tables[i]

    def table_end(self, va: int) -> int | None:
        """End of the jump table containing `va`, else None."""
        table = self.table_at(va)
        return table[1] if table is not None else None

    def case_targets(self, va: int) -> Iterator[int]:
        """The case labels of the jump table containing `va` (none when `va` is in no table)."""
        table = self.table_at(va)
        if table is None:
            return
        for entry in range(table[0], table[1], _TABLE_ENTRY):
            if (fx := self.fixups.get(entry)) is not None:
                yield fx.target_va

    def after_tables(self, va: int, limit: int, reached: set[int]) -> int | None:
        """End of the run of jump tables at `va` when the code after it, up to `limit`, is
        reached by no target in `reached` and no case label of those tables: that code is not
        part of the function (05-REVIEW row 11). None when no table starts the run, or when the
        function goes on past it."""
        if self.table_at(va) is None:
            return None
        end = va
        cases: list[int] = []
        while (table := self.table_at(end)) is not None:
            cases.extend(self.case_targets(end))
            end = table[1]
        if any(end <= target < limit for targets in (reached, cases) for target in targets):
            return None
        return end

    def read_tables(self, insn: x86.Insn) -> Iterator[int]:
        """The case labels of every jump table an indirect jmp reads (through a fixup in its
        operand to a table start), wherever that table lies: a table past the scan position
        can still reach code before it (review 06-04 minor 1)."""
        if not insn.is_jump or insn.branch_target is not None:
            return
        for va in range(insn.va, insn.va + insn.size):
            fx = self.fixups.get(va)
            if fx is not None and self.table_at(fx.target_va) is not None:
                yield from self.case_targets(fx.target_va)

    def skip(self, va: int) -> int | None:
        """Where code resumes after the jump table or inline LE fixup field at `va`."""
        end = self.table_end(va)
        if end is not None:
            return end
        fx = self.fixups.get(va)
        return va + fx.size if fx is not None else None

    def padding_size(self, va: int, limit: int) -> int:
        """Size of the padding item at `va` (a zero byte or a filler instruction), else 0."""
        if self.flat[va] == 0:
            return 1
        if va in self.sites:
            return 0
        insn = x86.decode_one(bytes(self.flat[va : min(va + _MAX_INSN, limit)]), va)
        return insn.size if insn is not None and x86.is_filler(insn) else 0

    def only_padding(self, va: int, limit: int) -> bool:
        """True when [va, limit) holds only filler instructions, zero bytes and jump tables (a
        leading table of the next function)."""
        while va < limit:
            if (end := self.table_end(va)) is not None:
                va = end
                continue
            if not (size := self.padding_size(va, limit)):
                return False
            va += size
        return True

    def ends_here(self, va: int, limit: int) -> bool:
        """True when a terminal instruction ending at `va` ends the function: padding starts at
        `va`, or only jump tables and padding remain up to `limit`."""
        return va >= limit or bool(self.padding_size(va, limit)) or self.only_padding(va, limit)

    def end_of(self, start: int, limit: int) -> int:
        """The first padding byte after a terminal instruction in [start, limit), or the end of
        the jump tables right after one when no branch or case label of the code scanned so far
        reaches the code behind them; else limit (a function that falls through into the next
        one has no ret). The case labels counted are those of every table the scan stepped over
        or the scanned code's jmps read, wherever that table lies. Code after that padding or
        those tables is not part of the function: it stays a gap for the reconcile step to
        judge."""
        pos = start
        reached: set[int] = set()  # jump targets and case labels of the code scanned so far
        while pos < limit:
            if (resume := self.skip(pos)) is not None:
                reached.update(self.case_targets(pos))
                pos = resume
                continue
            last = pos
            for insn in x86.decode(bytes(self.flat[pos:limit]), pos, data_sites=self.sites):
                last = insn.va + insn.size
                if insn.branch_target is not None and not insn.is_call:
                    reached.add(insn.branch_target)
                reached.update(self.read_tables(insn))
                if not insn.is_terminal:
                    continue
                if self.ends_here(last, limit):
                    return last
                if (end := self.after_tables(last, limit, reached)) is not None:
                    return end
            pos = last if last > pos else pos + 1  # step over an undecodable byte
        return limit


def ends(discovery: Discovery, le: LE) -> dict[int, int]:
    """End of every start by the D-07 rule: the first padding byte (filler or zero) after a
    terminal instruction, or the end of a terminal instruction followed only by jump tables and
    padding up to the next start, or the end of the jump tables right after a terminal
    instruction when no jump target or case label of the function's code scanned so far lies
    behind them (05-REVIEW row 11); else the next start (or the object end). Ranges never
    overlap; code after a function's padding or trailing tables that has no start of its own
    is left uncovered (a gap). Decoding never reads past the containing object."""
    scan = _EndScan(le, discovery.jump_tables)
    starts = discovery.starts
    result = {}
    for i, start in enumerate(starts):
        obj = scan.code_object(start)
        if obj is None:
            raise DiscoverError(f"start {start:#x} lies in no code object")
        limit = obj.end
        if i + 1 < len(starts):
            limit = min(limit, starts[i + 1])
        result[start] = scan.end_of(start, limit)
    return result
