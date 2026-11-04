# Derived from NHL95PC tools/permute.py (owner's permission; no licence file), https://github.com/abdulahmad/NHL95PC
# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc search EXE ADDR FILE`: a permutation search over one function's C (D-01, D-26).

Grown from spike 010's variants.py (.planning/spikes/010-deterministic-matching/variants.py), which
keeps its own copy; its Job, compile_all and judge were not taken (D-07). The declaration pattern
and the type-move loop are adapted from NHL95PC's permute.py (DECL_ANY, DECL1, t_type).

From the base it tries the moves of each axis of AXES, one line of C per move. Each wave of
variants goes through one batch.compile_batch, and batch.judge runs once per distinct
batch.body_key, so at most BUDGET compile jobs run and most of them cost no judging. The best
variant is the one with the highest (exact, stack_score, score) of its cells.

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt. A match
is still claimed only by `reverseapoc check` / `gate` (D-16). All output lies under build/.
"""

from __future__ import annotations

import json
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
AXES = ("type",)  # type goes first: type moves spills (RESEARCH)

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
_DECLARATOR = re.compile(r"^\s*\**\s*[A-Za-z_]\w*\s*(?:\[[^\]]*\]\s*)*(?:=.*)?$")
_PLAIN_DECLARATOR = re.compile(r"^\s*[A-Za-z_]\w*\s*(?:=.*)?$")
_STATEMENT_WORDS = frozenset(("return", "break", "continue", "goto", "case", "default", "if", "for",
                              "while", "do", "switch", "else", "sizeof"))  # fmt: skip
_BODY_OPEN = re.compile(r"\s*\{")


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


def _moves(text: str, span: tuple[int, int]) -> Iterator[Candidate]:
    """The moves of each axis of AXES, in that order."""
    by_axis = {"type": type_moves}
    for axis in AXES:
        yield from by_axis[axis](text, span)


# ---- the waves ----


@dataclass
class _Run:
    exe: ExeInputs
    row: FunctionRow
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

    @property
    def rank(self) -> tuple[bool, float, float]:
        return max(_rank(record) for record in self.records)


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
    return [_Scored(candidate, _records(run, compiled[n * per_variant : (n + 1) * per_variant]))
            for n, candidate in enumerate(wave)]  # fmt: skip


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
    return SearchResult(path, text, axes, records, run.compiles, len(run.verdicts))


def run_search(
    exe: ExeInputs, row: FunctionRow, text: str, rules: Sequence[Rule], *, watcom_dir: Path
) -> SearchResult:
    """Search `text`, which defines the function of `row`, under the unit's committed rule and
    SEARCH_CELLS. It stops on an exact variant, at BUDGET compile jobs or when the moves run
    out. OUT/<stem>/<start:08x>/ is cleared first: it holds v<nnnn>/, best.c and results.jsonl.
    BatchError when `text` does not define the function; a compile that fails only scores 0."""
    name = exe.symbols.c_name(row.start)
    base = split_declarators(text, function_span(text, name))
    span = function_span(base, name)
    root = OUT / exe.stem / f"{row.start:08x}"
    if root.exists():
        shutil.rmtree(root)
    cells = _cells(batch.committed_rule(rules, exe.stem, row.unit))
    run = _Run(exe, row, cells, root, watcom_dir)
    seen = {base}
    (best,) = _wave(run, [Candidate(base, ())])
    moves = _moves(base, span)
    while not best.rank[0]:
        wave = _take(moves, seen, min(WAVE, (BUDGET - run.compiles) // len(cells)))
        if not wave:
            break
        best = max([best, *_wave(run, wave)], key=lambda scored: scored.rank)
    return _result(run, best)
