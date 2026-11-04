# Derived from NHL95PC tools/permute.py, permute_decls.py and scope_decls.py, https://github.com/abdulahmad/NHL95PC
# (owner's permission; no licence file)
# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc search EXE ADDR FILE`: a permutation search over one function's C (D-01, D-26).

Grown from spike 010's variants.py (.planning/spikes/010-deterministic-matching/variants.py), which
keeps its own copy; its Job, compile_all and judge were not taken (D-07). The declaration pattern
and the type-move loop are adapted from NHL95PC's permute.py (DECL_ANY, DECL1, t_type), the search
for the block holding every use from its scope_decls.py (block_stacks, moves), and the seeded
shuffles of declaration lines from its permute_decls.py.

From the base it walks AXES in order, each move a line or two of C. Each wave of variants goes
through one batch.compile_batch, and batch.judge runs once per distinct batch.body_key, so at most
BUDGET compile jobs run and most of them cost no judging. The best variant is the one with the
highest (exact, stack_score, score) of its cells. A better variant becomes the base and its axis
starts again from it. A statement-order variant stands only when it is exact: reordering can
change behaviour, so byte identity is the only evidence for it (D-26).

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt. A match
is still claimed only by `reverseapoc check` / `gate` (D-16). All output lies under build/.
"""

from __future__ import annotations

import itertools
import json
import random
import re
import shutil
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import batch, check, contextpack, unitdefs
from .cflags import Rule
from .check import ExeInputs
from .fileio import write_atomic
from .functions import FunctionRow

SEED = 20261103
BUDGET = 600  # compile jobs, every cell counted
WAVE = 64  # variants per compile_batch call
WORKERS = 12
SEARCH_CELLS = ("-4r -oneatx -s -fpi",)
OUT = batch.BUILD_ROOT / "search"
AXES = ("type", "statement", "scope", "declaration")  # type first: it moves spills (RESEARCH)

_INT_TYPES = ("int", "unsigned", "short", "unsigned short", "signed char", "unsigned char")
# Spellings our C also uses, as the type each one is; `char` is unsigned, as wcc386 takes it.
_SAME_TYPE = {"char": "unsigned char", "s8": "signed char", "u8": "unsigned char", "s16": "short",
              "u16": "unsigned short", "s32": "int", "u32": "unsigned"}  # fmt: skip
TYPE_MOVES = {local: tuple(t for t in _INT_TYPES if t != _SAME_TYPE.get(local, local))
              for local in (*_INT_TYPES, *_SAME_TYPE)}  # fmt: skip

# A declaration line, read on text with its comments and literals blanked. `static` and `extern`
# locals hold no stack slot, so they are left out by not being specifiers here.
_SPECIFIER = (r"(?:(?:unsigned|signed|short|long|const|volatile|register|struct|union|enum)\s+)*"
              r"[A-Za-z_]\w*")  # fmt: skip
_DECLARATION = re.compile(
    rf"^\s*(?P<spec>{_SPECIFIER})(?P<declarators>(?:\s+\**|\*+)\s*[A-Za-z_][^;{{}}]*);\s*$"
)
_DECLARATOR = re.compile(r"^\s*\**\s*(?P<name>[A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(?:=.*)?$")
_PLAIN_DECLARATOR = re.compile(r"^\s*[A-Za-z_]\w*\s*(?:=.*)?$")
_STATEMENT_WORDS = frozenset(("return", "break", "continue", "goto", "case", "default", "if", "for",
                              "while", "do", "switch", "else", "sizeof"))  # fmt: skip
_CONTROL_WORDS = _STATEMENT_WORDS - {"sizeof"}
_BODY_OPEN = re.compile(r"\s*\{")
_WORD = re.compile(r"[A-Za-z_]\w*")
_LABEL = re.compile(r"\s*[A-Za-z_]\w*\s*:")
_ENDS_A_STATEMENT = (";", "{", "}", ":")  # what the line above a statement of its own ends in


@dataclass(frozen=True)
class Candidate:
    text: str
    axes: tuple[str, ...]  # the axes it moved along; empty for the base


def _rank(record: dict[str, Any]) -> tuple[bool, float, float]:
    return record["exact"], record["stack_score"], record["score"]


@dataclass(frozen=True)
class SearchResult:
    best: Path  # best.c: the winner's text, which every record names
    text: str
    axes: tuple[str, ...]
    records: tuple[dict[str, Any], ...]  # one per cell of the winner, as results.jsonl holds them
    compiles: int
    bodies: int  # distinct function bodies judged
    slots: batch.SlotMap  # the winner's best cell against the row

    @property
    def exact(self) -> bool:
        return any(record["exact"] for record in self.records)

    @property
    def score(self) -> float:
        return max(self.records, key=_rank)["score"]

    @property
    def stack_score(self) -> float:
        return max(self.records, key=_rank)["stack_score"]


# ---- the source: line-level, no C parser ----


def _code(text: str) -> str:
    """`text` with comments and literals blanked, line for line and column for column."""
    return contextpack._blanked(text, check._configure())[0]


def _closing(code: str, at: int, opening: str, closing: str) -> int | None:
    """The index of the `closing` that matches the `opening` at `at`, or None."""
    depth = 0
    for index in range(at, len(code)):
        depth += (code[index] == opening) - (code[index] == closing)
        if not depth:
            return index
    return None


def function_span(text: str, name: str) -> tuple[int, int]:
    """The line numbers of the `{` and the `}` of the definition of `name` (exe.symbols.c_name),
    from 0; BatchError when `text` does not define it. Only a definition has a `{` after the
    parenthesis that closes its parameters."""
    code = _code(text)
    for hit in re.finditer(rf"\b{re.escape(name)}\s*\(", code):
        params_end = _closing(code, hit.end() - 1, "(", ")")
        body = None if params_end is None else _BODY_OPEN.match(code, params_end + 1)
        if body is None:
            continue
        end = _closing(code, body.end() - 1, "{", "}")
        if end is None:
            raise batch.BatchError(f"{name}: the body has no closing brace")
        return code.count("\n", 0, body.end() - 1), code.count("\n", 0, end)
    raise batch.BatchError(f"{name}: the source does not define it")


def _declaration(code: str) -> re.Match[str] | None:
    """The declaration on one blanked line, or None: a statement can look like one."""
    found = _DECLARATION.match(code)
    if found is None or found["spec"].split()[0] in _STATEMENT_WORDS:
        return None
    parts = unitdefs._split_top(found["declarators"], ",")
    return found if all(_DECLARATOR.match(part) for part in parts) else None


def _split_line(line: str, code: str) -> list[str]:
    """`line` as one declaration per declarator; its trailing comment stays on the last one."""
    found = _declaration(code)
    parts = unitdefs._split_top(found["declarators"], ",") if found is not None else []
    if len(parts) < 2:
        return [line]
    head, at = line[: found.end("spec")], found.start("declarators")
    split = []
    for part in parts:
        split.append(f"{head} {line[at : at + len(part)].strip()};")
        at += len(part) + 1
    split[-1] += line[found.end("declarators") + 1 :]
    return split


def split_declarators(text: str, span: tuple[int, int]) -> str:
    """`text` with one declarator per line inside `span`, as the moves need it."""
    first, last = span
    lines = zip(text.split("\n"), _code(text).split("\n"), strict=True)
    split = [_split_line(*pair) if first < n < last else pair[:1] for n, pair in enumerate(lines)]
    return "\n".join(line for group in split for line in group)


def declarations(text: str, span: tuple[int, int]) -> list[int]:
    """The line numbers of the declarations inside `span`, each block's included. C89 puts them
    all at the top of a block, so a declaration line needs no block tracking."""
    first, last = span
    code = _code(text).split("\n")
    return [n for n in range(first + 1, last) if _declaration(code[n]) is not None]


def _local_type(found: re.Match[str]) -> str | None:
    """The type a move may replace: that of a plain scalar local, or None."""
    local = " ".join(found["spec"].split())
    plain = _PLAIN_DECLARATOR.match(found["declarators"]) is not None
    return local if plain and local in TYPE_MOVES else None


def type_moves(text: str, span: tuple[int, int]) -> Iterator[Candidate]:
    """Each plain scalar local under each type TYPE_MOVES gives it, one declaration per move."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    for n in declarations(text, span):
        found = _declaration(code[n])
        local = _local_type(found)
        for new in TYPE_MOVES.get(local, ()):
            line = lines[n][: found.start("spec")] + new + lines[n][found.end("spec") :]
            yield Candidate("\n".join([*lines[:n], line, *lines[n + 1 :]]), ("type",))


def _swapped(lines: Sequence[str], one: int, two: int) -> str:
    moved = list(lines)
    moved[one], moved[two] = moved[two], moved[one]
    return "\n".join(moved)


def _is_simple(code: str, above: str) -> bool:
    """`code` is one whole statement, not governed or continued from `above`, the code line over
    it. Both are blanked lines."""
    words = set(_WORD.findall(code))
    return (code.rstrip().endswith(";") and code.count("(") == code.count(")")
            and "{" not in code and "}" not in code and not words & _CONTROL_WORDS
            and _LABEL.match(code) is None and _declaration(code) is None
            and above.rstrip().endswith(_ENDS_A_STATEMENT))  # fmt: skip


def statement_moves(text: str, span: tuple[int, int]) -> Iterator[Candidate]:
    """Each swap of two adjacent simple statements of one block: only blank lines and comments
    may lie between them, so a label, a brace or a control line ends the run."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    rows = [n for n in range(span[0], span[1]) if code[n].strip()]
    simple = {n for above, n in itertools.pairwise(rows) if _is_simple(code[n], code[above])}
    for one, two in itertools.pairwise(rows):
        if one in simple and two in simple:
            yield Candidate(_swapped(lines, one, two), ("statement",))


def _block_stacks(code: Sequence[str], span: tuple[int, int]) -> dict[int, tuple[int, ...]]:
    """Per line inside `span`, the `{` lines of the blocks open at its start, outermost first; the
    function's own block is left out. A block's header line is outside it."""
    stack: list[int] = []
    stacks = {}
    for n in range(span[0] + 1, span[1]):
        stacks[n] = tuple(stack)
        for char in code[n]:
            if char == "{":
                stack.append(n)
            elif char == "}" and stack:
                stack.pop()
    return stacks


def _name(found: re.Match[str]) -> str:
    return _DECLARATOR.match(found["declarators"])["name"]


def _scope_block(code: Sequence[str], stacks: dict[int, tuple[int, ...]], n: int) -> int | None:
    """The `{` line of the innermost block that holds every use of the local declared on line
    `n`, when that block lies inside the declaration's own and opens at the end of its line."""
    word = re.compile(rf"\b{_name(_declaration(code[n]))}\b")
    uses = [stacks[i] for i in stacks if i != n and word.search(code[i]) is not None]
    if not uses:
        return None
    common = uses[0]
    for stack in uses[1:]:
        common = tuple(a for a, b in zip(common, stack, strict=False) if a == b)
    own = stacks[n]
    if len(common) <= len(own) or common[: len(own)] != own:
        return None
    return common[-1] if code[common[-1]].rstrip().endswith("{") else None


def _moved_into(lines: Sequence[str], n: int, block: int) -> str:
    """`lines` with line `n` moved under the `{` of line `block`, at the indent of what follows."""
    below = lines[block + 1]
    indent = below[: len(below) - len(below.lstrip())]
    moved = [*lines[:n], *lines[n + 1 : block + 1], indent + lines[n].strip(), *lines[block + 1 :]]
    return "\n".join(moved)


def scope_moves(text: str, span: tuple[int, int]) -> Iterator[Candidate]:
    """Each declaration moved to the top of the innermost block holding all its uses, when that
    block is inner. Nothing checks that the C keeps its meaning: only the bytes can say so."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    stacks = _block_stacks(code, span)
    for n in declarations(text, span):
        block = _scope_block(code, stacks, n)
        if block is not None:
            yield Candidate(_moved_into(lines, n, block), ("scope",))


def _in_memory(found: re.Match[str], body: str) -> bool:
    """An address-taken local or an aggregate: the only locals declaration order moves (RESEARCH).
    A bitwise `&` before the name counts too, which only reorders the moves."""
    declarators = found["declarators"]
    if "[" in declarators or re.search(rf"&\s*{_name(found)}\b", body) is not None:
        return True
    return "*" not in declarators and _local_type(found) is None


def _shuffles(lines: Sequence[str], blocks: Sequence[list[int]]) -> Iterator[Candidate]:
    """BUDGET seeded orders of each block's declarations: never more are needed, and the walk
    drops an order it has seen, so a block with few orders still ends."""
    rng = random.Random(SEED)
    for _ in range(BUDGET):
        moved = list(lines)
        for block in blocks:
            for n, source in zip(block, rng.sample(block, len(block)), strict=True):
                moved[n] = lines[source]
        yield Candidate("\n".join(moved), ("declaration",))


def declaration_moves(text: str, span: tuple[int, int]) -> Iterator[Candidate]:
    """Pairwise swaps of the declarations of one block, the pairs with the most address-taken
    locals and aggregates first, then seeded shuffles."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    stacks = _block_stacks(code, span)
    rows = declarations(text, span)
    blocks = [list(group) for _, group in itertools.groupby(rows, key=stacks.__getitem__)]
    blocks = [block for block in blocks if len(block) > 1]
    body = "\n".join(code[span[0] + 1 : span[1]])
    memory = {n for n in rows if _in_memory(_declaration(code[n]), body)}
    pairs = [pair for block in blocks for pair in itertools.combinations(block, 2)]
    for one, two in sorted(pairs, key=lambda pair: -len(memory.intersection(pair))):
        yield Candidate(_swapped(lines, one, two), ("declaration",))
    if blocks:
        yield from _shuffles(lines, blocks)


# ---- the waves ----


@dataclass
class _Run:
    exe: ExeInputs
    row: FunctionRow
    name: str  # the function's C name
    cells: list[tuple[str, Rule]]
    root: Path
    watcom_dir: Path
    compiles: int = 0
    variants: int = 0
    verdicts: dict[str, batch.Verdict] = field(default_factory=dict)  # by batch.body_key


@dataclass(frozen=True)
class _Scored:
    candidate: Candidate
    records: list[dict[str, Any]]  # one per cell
    objects: list[Path]  # one per cell

    @property
    def rank(self) -> tuple[bool, float, float]:
        return max(_rank(record) for record in self.records)

    @property
    def stands(self) -> bool:
        """D-26: a variant with `statement` in its axes stands only when exact."""
        return self.rank[0] or "statement" not in self.candidate.axes


def _verdict(run: _Run, compiled: batch.Compiled) -> batch.Verdict:
    """judge's verdict of one compiled cell: one judge per distinct body. A body that cannot be
    read is keyed by its failure, which judge reports the same way."""
    start = run.row.start
    if not compiled.ok:
        return batch.unjudged(run.row.end - start)
    body = batch.function_body(run.exe, compiled.job.obj, start)
    key = body if isinstance(body, str) else batch.body_key(body)
    if key not in run.verdicts:
        run.verdicts[key] = batch.judge(run.exe, compiled.job.obj, start)
    return run.verdicts[key]


def _records(run: _Run, compiled: Sequence[batch.Compiled]) -> list[dict[str, Any]]:
    """One record per cell of a variant, from the cached verdict (never judged_record, which
    would judge again)."""
    records = []
    for (name, rule), one in zip(run.cells, compiled, strict=True):
        verdict = _verdict(run, one)
        record = batch.cell_record(run.exe.stem, run.row.start, name, rule, one, verdict)
        records.append({**record, "stack_score": verdict.stack_score})
    return records


def _wave(run: _Run, wave: Sequence[Candidate]) -> list[_Scored]:
    """Compile `wave` in one batch, each variant in its own directory (write_cell_jobs names its
    files the same for every variant), and score each variant."""
    row = run.row
    jobs = []
    for candidate in wave:
        out = run.root / f"v{run.variants:04d}"
        run.variants += 1
        jobs += batch.write_cell_jobs(out, candidate.text, run.exe.flat[row.start : row.end],
                                      row.start, run.cells)  # fmt: skip
    compiled = batch.compile_batch(jobs, WORKERS, watcom_dir=run.watcom_dir).compiled
    run.compiles += len(jobs)
    per_variant = len(run.cells)
    scored = []
    for n, candidate in enumerate(wave):
        cells = compiled[n * per_variant : (n + 1) * per_variant]
        scored.append(_Scored(candidate, _records(run, cells), [one.job.obj for one in cells]))
    return scored


def _take(moves: Iterator[Candidate], seen: set[str], limit: int) -> list[Candidate]:
    """Up to `limit` moves whose text has not been seen."""
    wave: list[Candidate] = []
    while len(wave) < limit:
        candidate = next(moves, None)
        if candidate is None:
            break
        if candidate.text not in seen:
            seen.add(candidate.text)
            wave.append(candidate)
    return wave


def _axis_moves(axis: str, best: _Scored, name: str) -> Iterator[Candidate]:
    """The moves of `axis` from `best`, each naming every axis its text moved along."""
    by_axis = {"type": type_moves, "statement": statement_moves, "scope": scope_moves,
               "declaration": declaration_moves}  # fmt: skip
    text, axes = best.candidate.text, best.candidate.axes
    for move in by_axis[axis](text, function_span(text, name)):
        yield Candidate(move.text, (*axes, *(a for a in move.axes if a not in axes)))


def _walk(run: _Run, seen: set[str], best: _Scored, axis: str) -> _Scored:
    """Walk `axis` from `best`: a variant that stands and beats it becomes the base, and the axis
    starts again from there. It ends on exact, at the budget or when the moves run out."""
    moves = _axis_moves(axis, best, run.name)
    while not best.rank[0]:
        wave = _take(moves, seen, min(WAVE, (BUDGET - run.compiles) // len(run.cells)))
        if not wave:
            break
        standing = [scored for scored in _wave(run, wave) if scored.stands]
        found = max([best, *standing], key=lambda scored: scored.rank)
        if found is not best:
            best = found
            moves = _axis_moves(axis, best, run.name)
    return best


def _cells(committed: Rule) -> list[tuple[str, Rule]]:
    """The committed rule, then each search cell whose flags differ from it."""
    texts = [text for text in SEARCH_CELLS
             if batch.cell_rule(committed, text).flags != committed.flags]  # fmt: skip
    return batch.cells_for(committed, texts)


def _result(run: _Run, best: _Scored) -> SearchResult:
    """Write the winner to best.c, which no wave touches, and its records to results.jsonl."""
    text, axes = best.candidate.text, best.candidate.axes
    path = run.root / "best.c"
    write_atomic(path, text.encode("ascii"))
    records = tuple({**batch.with_source(record, path, text), "axes": list(axes)}
                    for record in best.records)  # fmt: skip
    lines = "".join(json.dumps(record) + "\n" for record in records)
    write_atomic(run.root / "results.jsonl", lines.encode("utf-8"))
    cell = max(range(len(records)), key=lambda n: _rank(records[n]))
    slots = batch.function_slots(run.exe, best.objects[cell], run.row.start)
    return SearchResult(path, text, axes, records, run.compiles, len(run.verdicts), slots)


def run_search(
    exe: ExeInputs, row: FunctionRow, text: str, rules: Sequence[Rule], *, watcom_dir: Path
) -> SearchResult:
    """Search `text`, which defines the function of `row`, under the unit's committed rule and
    SEARCH_CELLS: walk AXES, and walk them again while a round improves the base. It stops on an
    exact variant, at BUDGET compile jobs or when the moves run out.
    OUT/<stem>/<start:08x>/ is cleared first: it holds v<nnnn>/, best.c and results.jsonl.
    BatchError when `text` does not define the function; a compile that fails only scores 0."""
    name = exe.symbols.c_name(row.start)
    base = split_declarators(text, function_span(text, name))
    root = OUT / exe.stem / f"{row.start:08x}"
    if root.exists():
        shutil.rmtree(root)
    cells = _cells(batch.committed_rule(rules, exe.stem, row.unit))
    run = _Run(exe, row, name, cells, root, watcom_dir)
    seen = {base}
    (best,) = _wave(run, [Candidate(base, ())])
    before = None
    while best is not before:
        before = best
        for axis in AXES:
            best = _walk(run, seen, best, axis)
    return _result(run, best)
