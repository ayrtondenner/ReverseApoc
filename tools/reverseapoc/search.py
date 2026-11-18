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

The rewrite axis (todo search-rewrite-axis) takes Echo's rule-based refinement: rewrites of one
expression, branch or loop that keep the meaning of the C, each a candidate of its own, greedy as
every axis is (rewrite_moves names them). An if/else of one assignment turned into a ternary, or
back, may convert a value differently, so it is a statement move too and stands only when exact.

The declaration axis asks the slot model first (slots.py). Where it knows the order of the memory
locals it computes the one order the original's slots need, and it moves nothing for the slots
that hold scalars, which declarations cannot reach; the result names those. The plain moves of
declaration_moves stand where it cannot say: the map is empty, or does not place every memory
local; a size is unknown; two blocks reuse a name; a tie has no known order; a float with no
address taken stands in a tie; a plain local is under a slot; a memory local is, and either side
has spills; a parameter has its address taken; an aggregate is initialized; or `(word) & local`
could be a cast.

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt. A match
is still claimed only by `reverseapoc check` / `gate` (D-16). All output lies under build/.
"""

from __future__ import annotations

import itertools
import json
import math
import random
import re
import shutil
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import archive, batch, check, classify, contextpack, omf2elf, relocs, slots, unitdefs
from .cflags import Rule
from .check import ExeInputs
from .fileio import write_atomic
from .functions import FunctionRow

SEED = 20261103
BUDGET = 600  # compile jobs, every cell counted
# The compile jobs one walk of the rewrite axis may spend: a long body gives a rewrite at nearly
# every operator, which would leave the statement, scope and declaration axes nothing.
REWRITE_SHARE = BUDGET // 3
WAVE = 64  # variants per compile_batch call
WORKERS = 12
SEARCH_CELLS = ("-4r -oneatx -s -fpi",)
OUT = batch.BUILD_ROOT / "search"
# type first: it moves spills (RESEARCH); rewrite next, before the shuffles can spend the budget
AXES = ("type", "rewrite", "statement", "scope", "declaration")
# What reading a compiled body can raise past batch.function_body's own failure keys.
_UNREADABLE = (omf2elf.Omf2ElfError, relocs.RelocError)

_INT_TYPES = ("int", "unsigned", "short", "unsigned short", "signed char", "unsigned char")
# Spellings our C also uses, as the type each one is; `char` is unsigned, as wcc386 takes it.
_SAME_TYPE = {"char": "unsigned char", "u8": "unsigned char", "s16": "short",
              "u16": "unsigned short"}  # fmt: skip
TYPE_MOVES = {local: tuple(t for t in _INT_TYPES if t != _SAME_TYPE.get(local, local))
              for local in (*_INT_TYPES, *_SAME_TYPE)}  # fmt: skip

POINTER_SIZE = 4
_SIZES = {"char": 1, "signed char": 1, "unsigned char": 1, "s8": 1, "u8": 1, "short": 2,
          "signed short": 2, "unsigned short": 2, "s16": 2, "u16": 2, "int": 4, "signed": 4,
          "unsigned": 4, "signed int": 4, "unsigned int": 4, "long": 4, "signed long": 4,
          "unsigned long": 4, "s32": 4, "u32": 4, "float": 4, "double": 8}  # fmt: skip
_QUALIFIERS = frozenset(("const", "volatile", "register"))
# A declaration that holds a slot opens with one of these; C89 opens no statement with one.
_TYPE_WORDS = frozenset((*(word for key in _SIZES for word in key.split()), *_QUALIFIERS,
                         "struct", "union", "enum", "void"))  # fmt: skip
_FLOATING = frozenset(("float", "double"))

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
_DIMENSION = re.compile(r"\[([^\]]*)\]")
_PLAIN_DIMENSION = re.compile(r"(?P<octal>0[0-7]*)|[1-9]\d*")
# What stands before a unary `&`: an operator, an opening, `return`, or a cast. A name, a `)`, a
# `]` and a postfix `++` or `--` leave a binary `&`, and so does an operand _operands stands in
# for. `(word) &` with a word outside _SIZES could be either: _ambiguous_and refuses that frame.
_CAST = "|".join(re.escape(spec) for spec in _SIZES)
_BEFORE_ADDRESS = (r"(?:[(,=!?:;{}\[*/%|^<>~]|(?<!\+)\+|(?<!-)-|&&|\breturn|\*\s*\)"
                   rf"|\(\s*(?:{_CAST})\s*\))")  # fmt: skip
_ITSELF = r"\b(?!\s*(?:->|\[))"  # not `&p->x` or `&p[1]`, the address of what a pointer points at
_SIZEOF = re.compile(r"\bsizeof\s*\([^()]*\)")
_OPERAND = "0"
_INITIALIZED_AGGREGATE = re.compile(r"=\s*\{")  # _DECLARATION leaves it out, by its `{`


@dataclass(frozen=True)
class Candidate:
    text: str
    axes: tuple[str, ...]  # the axes it moved along; empty for the base


def _rank(record: dict[str, Any]) -> tuple[bool, float, float]:
    return record["exact"], record["stack_score"], record["score"]


@dataclass(frozen=True)
class Kept:
    """A variant the search kept, by its best cell: what the archive records of it."""

    text: str
    record: dict[str, Any]
    compiled: batch.Compiled


@dataclass(frozen=True)
class SearchResult:
    best: Path  # best.c: the winner's text, which every record names
    axes: tuple[str, ...]
    records: tuple[dict[str, Any], ...]  # one per cell of the winner, as results.jsonl holds them
    compiles: int
    bodies: int  # distinct function bodies judged
    slots: batch.SlotMap  # the winner's best cell against the row
    scalars: tuple[int, ...]  # the winner's mismatched slots that hold scalars
    # What archived_search records: the base, the seeds, each variant that became the base and
    # the winner, each by its best cell (todo candidate-archive).
    kept: tuple[Kept, ...] = ()

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
    """`text` with comments, literals, directives and dead #if 0 branches blanked, line for line
    and column for column; BatchError for a conditional the D-12 parser refuses. These are
    contextpack.definitions' phases, on `text` itself: normalised text would shorten a trigraph
    and shift the columns _split_line slices at, and _live reads whole lines only."""
    cfg = check._configure()
    try:
        live = cfg.code_text(text)
    except cfg._ConditionalError as exc:
        raise batch.BatchError(f"the source cannot be read: {exc}") from None
    return contextpack._live(*contextpack._blanked(text, cfg), live)


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


def _initialised(code: str) -> bool:
    """The declaration on the blanked line `code` runs an initializer."""
    return "=" in _declaration(code)["declarators"]


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
    block is inner. Nothing checks that the C keeps its meaning: only the bytes can say so, so an
    initialized one, whose initializer now runs elsewhere, is a statement move too (D-26)."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    stacks = _block_stacks(code, span)
    for n in declarations(text, span):
        block = _scope_block(code, stacks, n)
        if block is not None:
            axes = ("scope", "statement") if _initialised(code[n]) else ("scope",)
            yield Candidate(_moved_into(lines, n, block), axes)


def _moves_first(found: re.Match[str], body: str) -> bool:
    """An address-taken local or an aggregate, whose pairs declaration_moves tries first. A bitwise
    `&` before the name counts too, which only reorders the moves: the model trusts _in_frame."""
    declarators = found["declarators"]
    if "[" in declarators or re.search(rf"&\s*{_name(found)}\b", body) is not None:
        return True
    return "*" not in declarators and _local_type(found) is None


def _shuffles(lines: Sequence[str], blocks: Sequence[list[int]]) -> Iterator[str]:
    """BUDGET seeded orders of each block's declarations: never more are needed, and the walk
    drops an order it has seen, so a block with few orders still ends."""
    rng = random.Random(SEED)
    for _ in range(BUDGET):
        moved = list(lines)
        for block in blocks:
            for n, source in zip(block, rng.sample(block, len(block)), strict=True):
                moved[n] = lines[source]
        yield "\n".join(moved)


def _declaration_move(text: str, rows: Sequence[int], initialised: Sequence[str]) -> Candidate:
    """`text` as a declaration move, and a statement move too when the lines of `initialised`,
    the initializers in their old order, stand in another order in it (D-26)."""
    lines = text.split("\n")
    same = [lines[n] for n in rows if lines[n] in initialised] == list(initialised)
    return Candidate(text, ("declaration",) if same else ("declaration", "statement"))


def declaration_moves(text: str, span: tuple[int, int]) -> Iterator[Candidate]:
    """Pairwise swaps of the declarations of one block, the pairs with the most address-taken
    locals and aggregates first, then seeded shuffles. A move that runs the initializers in
    another order is a statement move too (D-26)."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    stacks = _block_stacks(code, span)
    rows = declarations(text, span)
    blocks = [list(group) for _, group in itertools.groupby(rows, key=stacks.__getitem__)]
    blocks = [block for block in blocks if len(block) > 1]
    body = "\n".join(code[span[0] + 1 : span[1]])
    first = {n for n in rows if _moves_first(_declaration(code[n]), body)}
    pairs = [pair for block in blocks for pair in itertools.combinations(block, 2)]
    initialised = [lines[n] for n in rows if _initialised(code[n])]
    for one, two in sorted(pairs, key=lambda pair: -len(first.intersection(pair))):
        yield _declaration_move(_swapped(lines, one, two), rows, initialised)
    if blocks:
        for moved in _shuffles(lines, blocks):
            yield _declaration_move(moved, rows, initialised)


def _dimension(text: str) -> int | None:
    """A dimension as C reads it, a leading 0 making it octal, or None past a plain number."""
    plain = _PLAIN_DIMENSION.fullmatch(text.strip())
    if plain is None:
        return None
    return int(plain[0], 8 if plain["octal"] else 10)


def _size(found: re.Match[str]) -> int | None:
    """The bytes of the local declared by `found`, or None: a struct, or a size that is not a
    plain number here."""
    declarator = found["declarators"].split("=")[0]
    spec = " ".join(word for word in found["spec"].split() if word not in _QUALIFIERS)
    element = POINTER_SIZE if "*" in declarator else _SIZES.get(spec)
    dimensions = [_dimension(text) for text in _DIMENSION.findall(declarator)]
    if element is None or None in dimensions:
        return None
    return math.prod(dimensions, start=element)


def _elements(found: re.Match[str]) -> int:
    """The elements of the local declared by `found`, whose size _size has read: 1 with no
    dimension."""
    declarator = found["declarators"].split("=")[0]
    return math.prod(_dimension(text) for text in _DIMENSION.findall(declarator))


def _plain_float(found: re.Match[str]) -> bool:
    """A float or a double itself, not an array of them or a pointer to one."""
    declarator = found["declarators"].split("=")[0]
    return found["spec"].split()[-1] in _FLOATING and not set("*[") & set(declarator)


def _volatile(found: re.Match[str]) -> bool:
    """A volatile local itself, not a pointer to a volatile."""
    return "volatile" in found["spec"].split() and "*" not in found["declarators"].split("=")[0]


def _operands(text: str, span: tuple[int, int]) -> str:
    """The code inside `span` as the `&` rules read it. _code leaves nothing of a literal, and a
    `sizeof(int)` reads as a cast, so each stands here as the operand it is."""
    code = list(_code(text))
    for found in check._configure()._NOT_CODE.pattern.finditer(text):
        if not found.group().startswith("/"):
            code[found.end() - 1] = _OPERAND
    lines = "".join(code).split("\n")
    return _SIZEOF.sub(_OPERAND, "\n".join(lines[span[0] + 1 : span[1]]))


def _address_taken(name: str, body: str) -> bool:
    """`body`, from _operands, takes the address of `name` itself. An array needs no such read of
    `&v[1]`, because _in_frame holds it by its use."""
    return re.search(rf"{_BEFORE_ADDRESS}\s*&\s*{name}{_ITSELF}", body) is not None


def _ambiguous_and(names: Iterable[str], body: str) -> bool:
    """`body`, from _operands, has `(word) & name` for a word _SIZES does not hold: a cast taking
    the address of `name`, or a binary `&`. Only the types could tell."""
    hits = (re.finditer(rf"\(\s*([A-Za-z_]\w*)\s*\)\s*&\s*{name}{_ITSELF}", body) for name in names)
    return any(hit[1] not in _SIZES for hit in itertools.chain.from_iterable(hits))


def _in_frame(
    found: re.Match[str], code: Sequence[str], n: int, span: tuple[int, int], body: str
) -> bool:
    """The local declared on line `n` is held in memory: its address is taken, or it is an array,
    a plain float or double, or a volatile that something uses (pr_slot_unused: nothing else takes
    a slot); a volatile's initializer is a use (pr_slot_volatile_init). The 8087 can hold a float
    with no slot at all: the map then does not place it, and _computable falls back. `body` comes
    from _operands."""
    name = _name(found)
    if _address_taken(name, body) or (_volatile(found) and "=" in found["declarators"]):
        return True
    word = re.compile(rf"\b{name}\b")
    others = (code[i] for i in range(span[0] + 1, span[1]) if i != n)
    framed = "[" in found["declarators"].split("=")[0] or _plain_float(found) or _volatile(found)
    return framed and any(map(word.search, others))


def memory_locals(text: str, span: tuple[int, int]) -> tuple[slots.Local, ...]:
    """The locals inside `span` held in memory, in declaration order: those _in_frame names. A
    size _size cannot read leaves its local out. `text` holds one declarator per line, as
    split_declarators leaves it."""
    code = _code(text).split("\n")
    stacks = _block_stacks(code, span)
    body = _operands(text, span)
    found_locals = []
    for n in declarations(text, span):
        found = _declaration(code[n])
        size = _size(found)
        if size is not None and _in_frame(found, code, n, span, body):
            scope = stacks[n][-1] if stacks[n] else 0
            found_locals.append(slots.Local(_name(found), size, scope, _elements(found) > 1))
    return tuple(found_locals)


def _float_in_a_tie(found: re.Match[str], memory: Sequence[slots.Local], body: str) -> bool:
    """`found` declares a float of `memory` that ties with another local, its address not taken.
    M2 does not place it and declarations still move it (pr_float_tie), so neither the model nor
    the scalars can speak for that frame."""
    name = _name(found)
    tie = [local.name for local in memory if local.size == _size(found)]
    return (_plain_float(found) and name in tie and len(tie) > 1
            and not _address_taken(name, body))  # fmt: skip


def _parameter_words(code: Sequence[str], span: tuple[int, int]) -> set[str]:
    """Every word of the parameter list of the body at `span`: the names, and their types too,
    which cost nothing, because only a name can follow a `&`."""
    head = "\n".join([*code[: span[0]], code[span[0]].split("{")[0]]).rstrip()
    return set(_WORD.findall(head[len(head) - 1 - _closing(head[::-1], 0, ")", "(") :]))


def _unread_declaration(code: str) -> bool:
    """The blanked line `code` opens with a type word, and _declaration does not read it."""
    first = _WORD.match(code.lstrip())
    return first is not None and first[0] in _TYPE_WORDS and _declaration(code) is None


def _readable(text: str, span: tuple[int, int], memory: Sequence[slots.Local]) -> bool:
    """A frame can be read from `span`: every local has a size and a name of its own, no float
    stands in a tie, no `&` is ambiguous, no slot lies outside the declarations, as a parameter
    whose address is taken and an initialized aggregate do, no line that opens with a type word
    is one the reader cannot read, because it hides a local (WR-02), and no local outside
    `memory` is under a slot, because a spilled short can move with its declaration
    (pr_spill_short) and then scalars are not out of reach of declaration moves."""
    code = _code(text).split("\n")
    if any(_unread_declaration(code[n]) for n in range(span[0] + 1, span[1])):
        return False
    found = [_declaration(code[n]) for n in declarations(text, span)]
    names = [_name(one) for one in found]
    sizes = [_size(one) for one in found]
    if len(set(names)) != len(names) or None in sizes:
        return False
    body = _operands(text, span)
    parameters = _parameter_words(code, span)
    if (any(_float_in_a_tie(one, memory, body) for one in found)
            or _ambiguous_and({*names, *parameters}, body)
            or any(_address_taken(word, body) for word in parameters)
            or _INITIALIZED_AGGREGATE.search(body) is not None):  # fmt: skip
        return False
    held = {local.name for local in memory}
    return all(size >= slots.SLOT_ALIGN or name in held
               for name, size in zip(names, sizes, strict=True))  # fmt: skip


def _moved(local: slots.Local, start: int, slot_map: batch.SlotMap) -> set[int]:
    """How far `slot_map` moves the slots of `local`, which ours holds at `start`."""
    return {theirs - ours for ours, theirs in slot_map.pairs
            if start <= ours < start + local.size}  # fmt: skip


def _places_all(memory: Sequence[slots.Local], slot_map: batch.SlotMap) -> bool:
    """The map shows every local of `memory`, each moved one way, and their targets are exactly
    the layout's own offsets. The map of a function that is not exact is often partial, and a
    local it leaves out would make the inverse answer from nothing. The model places locals only
    among its own offsets, so it cannot speak for a target off them, and the plain moves stand,
    whether or not an order reaches it: past this, a None from slots.declaration_order means size
    or a block rules the target out."""
    layout = slots.frame_layout(memory)
    targets = set()
    for local in memory:
        start = layout[local.name]
        moved = _moved(local, start, slot_map)
        if len(moved) != 1:
            return False
        targets.add(start + min(moved))
    return targets == set(layout.values())


def _computable(
    text: str, span: tuple[int, int], memory: Sequence[slots.Local], slot_map: batch.SlotMap
) -> bool:
    """The model can place `memory` in this frame: a map to read, every size, a known order, a map
    that places each local, and no spill on either side under a local smaller than a slot, which
    a spill pushes up the frame."""
    size = slots.frame_size(memory)
    fits = (all(local.size >= slots.SLOT_ALIGN for local in memory)
            or slot_map.frame_ours == slot_map.frame_theirs == size)  # fmt: skip
    return (bool(slot_map.pairs) and _readable(text, span, memory)
            and slots.order_is_known(memory) and _places_all(memory, slot_map)
            and fits)  # fmt: skip


def _target(memory: Sequence[slots.Local], slot_map: batch.SlotMap) -> dict[str, int]:
    """Where the original holds each of `memory`, which _places_all has passed. Any slot of a local
    places all of it: the map may show only an element of an array."""
    layout = slots.frame_layout(memory)
    return {local.name: layout[local.name] + min(_moved(local, layout[local.name], slot_map))
            for local in memory}  # fmt: skip


def _ordered(text: str, span: tuple[int, int], order: Sequence[str]) -> Candidate:
    """`text` with the declarations of `order` standing in that order, on the lines they hold."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    rows = declarations(text, span)
    held = {_name(_declaration(code[n])): n for n in rows}
    moved = list(lines)
    for n, name in zip(sorted(held[name] for name in order), order, strict=True):
        moved[n] = lines[held[name]]
    initialised = [lines[n] for n in rows if _initialised(code[n])]
    return _declaration_move("\n".join(moved), rows, initialised)


def declaration_axis(
    text: str, span: tuple[int, int], slot_map: batch.SlotMap
) -> Iterator[Candidate]:
    """The one order the memory locals need, if it differs from theirs; nothing for slots that
    hold scalars. Where the model cannot place them, declaration_moves stand, and so they do where
    the order the map needs is one order_is_known refuses: its lines turn on where a local is
    declared, so a known frame can need an order past them (pr_line_d_c4_i_h, pr_line_d_i_c4_h)."""
    memory = memory_locals(text, span)
    if not _computable(text, span, memory, slot_map):
        yield from declaration_moves(text, span)
        return
    target = _target(memory, slot_map)
    try:
        order = slots.declaration_order(memory, target)
    except ValueError:  # the order the target needs has no known layout: nothing to compute
        yield from declaration_moves(text, span)
        return
    if order is not None and order != tuple(local.name for local in memory):
        yield _ordered(text, span, order)


def _scalars(text: str, name: str, slot_map: batch.SlotMap) -> tuple[int, ...]:
    """The mismatched slots of `slot_map` that hold scalars and that declarations cannot reach.
    A frame _readable refuses may hold them otherwise, so nothing is said of it."""
    span = function_span(text, name)
    memory = memory_locals(text, span)
    if not _readable(text, span, memory):
        return ()
    mismatched = [ours for ours, theirs in slot_map.pairs if ours != theirs]
    return slots.scalar_slots(memory, mismatched, slot_map.frame_ours)


# ---- the rewrite axis: Echo's rules that keep the meaning (todo search-rewrite-axis) ----

_TOKEN = re.compile(r"->|\+\+|--|<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||[-+*/%&|^]=|\w+|\S")
_NUMBER = re.compile(r"0[xX][0-9A-Fa-f]+[uUlL]*|\d+[uUlL]*")
_IDENTIFIER = re.compile(r"[A-Za-z_]\w*")
_MACRO = re.compile(r"[A-Z0-9_]*[A-Z][A-Z0-9_]*")  # a macro may hide an operator: never an operand
# C's binary operators by precedence, higher binding tighter.
_PRECEDENCE = {"*": 13, "/": 13, "%": 13, "+": 12, "-": 12, "<<": 11, ">>": 11, "<": 10, ">": 10,
               "<=": 10, ">=": 10, "==": 9, "!=": 9, "&": 8, "^": 7, "|": 6, "&&": 5,
               "||": 4}  # fmt: skip
_MAYBE_UNARY = frozenset(("*", "+", "-", "&"))
_ENDS_AN_OPERAND = frozenset((")", "]", "++", "--"))
# What binds looser than any operator a rewrite reads: an operand next to one of these is whole.
_OPENS = frozenset(("(", "[", ",", ";", "?", ":", "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=",
                    "^=", "<<=", ">>=", "return"))  # fmt: skip
_CLOSES = frozenset((")", "]", ",", ";", "?", ":"))
_COMMUTATIVE = ("+", "*", "&", "|", "^", "==", "!=")
_MIRROR = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", **{op: op for op in _COMMUTATIVE}}
_BITWISE = frozenset(("&", "|", "^"))  # associative on every operand C allows them
_ARITHMETIC = frozenset(("+", "*"))  # associative on integers only, as wcc386 wraps them
_FLIPPED = {"==": "!=", "!=": "=="}  # negations that hold for a NaN too
_ELSE_LINE = re.compile(r"\s*\}\s*else\s*\{\s*$")
_RETURN = re.compile(r"\s*return\b")
_CASE = re.compile(r"\b(?:case|default)\b")
_CONTINUE = re.compile(r"\bcontinue\b")
REWRITE = ("rewrite",)
CHANGED = ("rewrite", "statement")  # D-26: may change what the C means, so it stands only exact


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int


def _tokens(code: str) -> list[_Token]:
    return [_Token(found[0], found.start(), found.end()) for found in _TOKEN.finditer(code)]


def _head_operand(text: str) -> bool:
    """A token that can start a simple operand: a number, or a name that is not a keyword, a type
    or a macro."""
    if _NUMBER.fullmatch(text):
        return True
    return (_IDENTIFIER.fullmatch(text) is not None and _MACRO.fullmatch(text) is None
            and text not in _TYPE_WORDS and text not in _STATEMENT_WORDS)  # fmt: skip


def _index(token: _Token) -> bool:
    return any(pattern.fullmatch(token.text) for pattern in (_NUMBER, _IDENTIFIER))


def _operand_end(tokens: Sequence[_Token], at: int) -> int | None:
    """The token past the simple operand that starts at `at`: a number, or a name with members and
    subscripts of one name or number each (`p->n`, `v[i].m`); None when none starts there."""
    if at >= len(tokens) or not _head_operand(tokens[at].text):
        return None
    if _NUMBER.fullmatch(tokens[at].text):
        return at + 1
    end = at + 1
    while end < len(tokens):
        word = tokens[end + 1] if end + 1 < len(tokens) else None
        if tokens[end].text in (".", "->") and word and _IDENTIFIER.fullmatch(word.text):
            end += 2
        elif (tokens[end].text == "[" and end + 2 < len(tokens) and _index(tokens[end + 1])
              and tokens[end + 2].text == "]"):  # fmt: skip
            end += 3
        else:
            break
    return end


def _binary(tokens: Sequence[_Token], at: int) -> bool:
    """The operator at `at` is binary: an operand ends right before it."""
    before = tokens[at - 1].text if at else ""
    return before in _ENDS_AN_OPERAND or _head_operand(before)


def _left_bound(tokens: Sequence[_Token], at: int, op: str) -> bool:
    """The token at `at`, left of an operand of `op`, binds looser than `op`. A line's start does
    not: the expression may go on from the line above."""
    if at < 0:
        return False
    text = tokens[at].text
    if text in _OPENS:
        return True
    looser = text in _PRECEDENCE and _PRECEDENCE[text] < _PRECEDENCE[op]
    return looser and (text not in _MAYBE_UNARY or _binary(tokens, at))


def _right_bound(tokens: Sequence[_Token], at: int, op: str) -> bool:
    """The token at `at`, right of an operand of `op`, leaves it to `op`: C's binary operators
    group from the left, so one of `op`'s own precedence does too."""
    if at >= len(tokens):
        return False
    text = tokens[at].text
    return text in _CLOSES or (text in _PRECEDENCE and _PRECEDENCE[text] <= _PRECEDENCE[op])


def _operand_start(tokens: Sequence[_Token], op_at: int) -> int | None:
    """Where the simple operand that ends right before the operator at `op_at` starts, when what
    stands before it binds looser."""
    op = tokens[op_at].text
    for start in range(op_at - 1, -1, -1):
        if _operand_end(tokens, start) == op_at and _left_bound(tokens, start - 1, op):
            return start
    return None


def _swapped_operands(line: str, tokens: Sequence[_Token], at: int) -> str | None:
    """`line` with the two operands of the operator at `at` swapped, a comparison mirrored."""
    op = tokens[at].text
    if op not in _MIRROR or (op in _MAYBE_UNARY and not _binary(tokens, at)):
        return None
    start = _operand_start(tokens, at)
    end = _operand_end(tokens, at + 1)
    if start is None or end is None or not _right_bound(tokens, end, op):
        return None
    left = line[tokens[start].start : tokens[at - 1].end]
    right = line[tokens[at + 1].start : tokens[end - 1].end]
    head, tail = line[: tokens[start].start], line[tokens[end - 1].end :]
    return f"{head}{right} {_MIRROR[op]} {left}{tail}"


def _regroupable(token: _Token, op: str, integers: set[str]) -> bool:
    """A one-token operand `op` may regroup: an integer for `+` and `*`, any for a bitwise one."""
    if not _head_operand(token.text):
        return False
    return op in _BITWISE or _NUMBER.fullmatch(token.text) is not None or token.text in integers


def _chain(tokens: Sequence[_Token], at: int, shape: str, integers: set[str]) -> str | None:
    """The operator of the chain of `shape` ("a+b+c" or "a+(b+c)") whose first operator is at `at`,
    when it is one associative operator over operands that regroup and stands whole."""
    width = len(shape) - 1  # the tokens after the first operand
    if at < 1 or at + width > len(tokens):
        return None
    op = tokens[at].text
    if op not in _BITWISE | _ARITHMETIC or not _binary(tokens, at):
        return None
    window = tokens[at - 1 : at + width]
    for token, kind in zip(window, shape, strict=True):
        if kind == "a" and not _regroupable(token, op, integers):
            return None
        if kind in "+()" and token.text != {"+": op}.get(kind, kind):
            return None
    whole = _left_bound(tokens, at - 2, op) and _right_bound(tokens, at + width, op)
    return op if whole else None


def _regrouped(line: str, tokens: Sequence[_Token], at: int, integers: set[str]) -> str | None:
    """`line` with `a op b op c` at `at` regrouped as `a op (b op c)`, or that back."""
    for shape in ("a+a+a", "a+(a+a)"):
        op = _chain(tokens, at, shape, integers)
        if op is None:
            continue
        a, b, c = (tokens[at - 1 + n].text for n, kind in enumerate(shape) if kind == "a")
        grouped = f"{a} {op} {b} {op} {c}" if "(" in shape else f"{a} {op} ({b} {op} {c})"
        end = tokens[at + len(shape) - 2].end
        return line[: tokens[at - 1].start] + grouped + line[end:]
    return None


def _expression_rewrites(line: str, code: str, integers: set[str]) -> Iterator[str]:
    """Each operand swap and each regrouping of one line, from its blanked `code`."""
    tokens = _tokens(code)
    for at in range(len(tokens)):
        for moved in (_swapped_operands(line, tokens, at), _regrouped(line, tokens, at, integers)):
            if moved is not None and moved != line:
                yield moved


def _is_integer(found: re.Match[str]) -> bool:
    spec = " ".join(word for word in found["spec"].split() if word not in _QUALIFIERS)
    declarator = found["declarators"].split("=")[0]
    return spec in _SIZES and spec not in _FLOATING and not set("*[") & set(declarator)


def _integer_names(code: Sequence[str], span: tuple[int, int]) -> set[str]:
    """The names the function declares as plain integers, its parameters included, less any name
    it also declares otherwise."""
    head = "\n".join([*code[: span[0]], code[span[0]].split("{")[0]]).rstrip()
    opening = len(head) - 1 - _closing(head[::-1], 0, ")", "(")
    parts = unitdefs._split_top(head[opening + 1 : -1], ",")
    found = [_declaration(part + ";") for part in parts]
    found += [_declaration(code[n]) for n in range(span[0] + 1, span[1])]
    found = [one for one in found if one is not None]
    others = {_name(one) for one in found if not _is_integer(one)}
    return {_name(one) for one in found if _is_integer(one)} - others


def _braces(code: Sequence[str], n: int, column: int) -> Iterator[tuple[int, int]]:
    """(line, depth after it) of each brace from `column` of line `n` on."""
    depth = 0
    for m in range(n, len(code)):
        for char in code[m][column:] if m == n else code[m]:
            if char in "{}":
                depth += 1 if char == "{" else -1
                yield m, depth


def _block_end(code: Sequence[str], n: int) -> int | None:
    """The line of the `}` that closes the `{` ending line `n`."""
    return next((m for m, depth in _braces(code, n, len(code[n].rstrip()) - 1) if not depth), None)


def _enclosing_end(code: Sequence[str], n: int) -> int | None:
    """The line of the `}` that closes the block line `n` stands in, when it opens its line."""
    found = next((m for m, depth in _braces(code, n, 0) if depth < 0), None)
    return found if found is not None and code[found].lstrip().startswith("}") else None


def _header(code: str, word: str) -> tuple[int, int, str] | None:
    """(the `(`, the `)`, what follows it) of a line that opens with `word (...)`."""
    found = re.match(rf"\s*{word}\s*\(", code)
    if found is None:
        return None
    close = _closing(code, found.end() - 1, "(", ")")
    return None if close is None else (found.end() - 1, close, code[close + 1 :].strip())


def _rows(code: Sequence[str], first: int, last: int) -> list[int]:
    """The lines from `first` up to `last` that hold code."""
    return [m for m in range(first, last) if code[m].strip()]


def _governed(code: Sequence[str], n: int) -> bool:
    """A braceless `if`, `else`, loop or a statement split across lines runs on into line `n`."""
    above = next((m for m in range(n - 1, -1, -1) if code[m].strip()), None)
    return above is not None and not code[above].rstrip().endswith(_ENDS_A_STATEMENT)


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _returns(code: Sequence[str], first: int, last: int) -> bool:
    """The lines from `first` up to `last`, a block's inside, end in a return that always runs."""
    rows = _rows(code, first, last)
    if not rows:
        return False
    above = code[rows[-2]] if len(rows) > 1 else code[first - 1]
    return (_RETURN.match(code[rows[-1]]) is not None and code[rows[-1]].rstrip().endswith(";")
            and above.rstrip().endswith(_ENDS_A_STATEMENT))  # fmt: skip


def _whole(tokens: Sequence[_Token], first: int) -> bool:
    """The tokens from `first` are one simple operand."""
    return _operand_end(tokens, first) == len(tokens)


def _negated(text: str, code: str) -> str:
    """The condition `text` negated: `!x` and `!(e)` lose their `!`, `==` and `!=` flip between
    two simple operands, and anything else is wrapped in `!(...)`. A `<` is never flipped to `>=`,
    which a NaN would tell apart."""
    tokens = _tokens(code)
    if tokens and tokens[0].text == "!" and len(tokens) > 1:
        if _whole(tokens, 1):
            return text[tokens[1].start : tokens[-1].end]
        if tokens[1].text == "(" and _closing(code, tokens[1].start, "(", ")") == tokens[-1].start:
            return text[tokens[1].end : tokens[-1].start].strip()
    middle = next((n for n, token in enumerate(tokens) if token.text in _FLIPPED), None)
    if middle is not None and _operand_end(tokens, 0) == middle and _whole(tokens, middle + 1):
        left = text[tokens[0].start : tokens[middle - 1].end]
        right = text[tokens[middle + 1].start : tokens[-1].end]
        return f"{left} {_FLIPPED[tokens[middle].text]} {right}"
    return f"!({text.strip()})"


def _if_else(code: Sequence[str], n: int) -> tuple[int, int, int, int] | None:
    """(the `(`, the `)`, the `} else {` line, the closing line) of a braced if/else on line `n`
    that nothing governs and that is not part of an else-if chain."""
    header = _header(code[n], "if")
    if header is None or header[2] != "{" or _governed(code, n):
        return None
    middle = _block_end(code, n)
    if middle is None or _ELSE_LINE.match(code[middle]) is None:
        return None
    end = _block_end(code, middle)
    if end is None or code[end].strip() != "}":
        return None
    return header[0], header[1], middle, end


Lines = list[str]


def _swapped_branches(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """An if/else with its condition negated and its two bodies swapped."""
    found = _if_else(code, n)
    if found is None:
        return
    opening, close, middle, end = found
    condition = _negated(lines[n][opening + 1 : close], code[n][opening + 1 : close])
    head = f"{lines[n][: opening + 1]}{condition}{lines[n][close:]}"
    yield [*lines[:n], head, *lines[middle + 1 : end], lines[middle], *lines[n + 1 : middle],
           *lines[end:]]  # fmt: skip


def _dropped_else(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """An if/else whose if returns, its else's body moved after it. An else that declares a local
    keeps its block."""
    found = _if_else(code, n)
    if found is None or not _returns(code, n + 1, found[2]):
        return
    _, _, middle, end = found
    if any(_declaration(code[m]) is not None for m in range(middle + 1, end)):
        return
    yield [*lines[:middle], f"{_indent(lines[middle])}}}", *lines[middle + 1 : end],
           *lines[end + 1 :]]  # fmt: skip


def _added_else(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """An if with no else whose body returns, the rest of its block moved into an else. A rest
    holding a case label stays put."""
    header = _header(code[n], "if")
    if header is None or header[2] != "{" or _governed(code, n):
        return
    end = _block_end(code, n)
    if end is None or code[end].strip() != "}" or not _returns(code, n + 1, end):
        return
    close = _enclosing_end(code, end + 1)
    rest = _rows(code, end + 1, close) if close is not None else []
    if not rest or code[rest[0]].lstrip().startswith("else"):
        return
    if any(_CASE.search(code[m]) for m in rest):
        return
    indent = _indent(lines[end])
    yield [*lines[:end], f"{indent}}} else {{", *lines[end + 1 : close], f"{indent}}}",
           *lines[close:]]  # fmt: skip


def _loop(code: Sequence[str], n: int, word: str) -> tuple[int, int, int] | None:
    """(the `(`, the `)`, the closing line) of a braced `word` loop on line `n` whose `}` stands
    alone."""
    header = _header(code[n], word)
    if header is None or header[2] != "{":
        return None
    end = _block_end(code, n)
    return None if end is None or code[end].strip() != "}" else (header[0], header[1], end)


def _for_parts(line: str, code: str, opening: int, close: int) -> list[str] | None:
    """The init, condition and step of a for header, stripped."""
    parts = unitdefs._split_top(code[opening + 1 : close], ";")
    if len(parts) != 3:
        return None
    at, texts = opening + 1, []
    for part in parts:
        texts.append(line[at : at + len(part)].strip())
        at += len(part) + 1
    return texts


def _keyword_head(line: str, opening: int, word: str) -> str:
    """What stands before the keyword of a header: its indent."""
    return line[:opening].rstrip().removesuffix(word)


def _for_to_while(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """`for (i; c; s) {` as `i; while (c) {`, the step last in the body. A body holding a
    `continue` keeps its for: the continue would skip the step. `for (; c;)` is just a while."""
    found = _loop(code, n, "for")
    parts = None if found is None else _for_parts(lines[n], code[n], found[0], found[1])
    if found is None or parts is None:
        return
    opening, close, end = found
    init, condition, step = parts
    keyword = _keyword_head(lines[n], opening, "for")
    head = f"{keyword}while ({condition or '1'}){lines[n][close + 1 :]}"
    if not init and not step:
        yield [*lines[:n], head, *lines[n + 1 :]]
        return
    body = range(n + 1, end)
    if _governed(code, n) or any(_CONTINUE.search(code[m]) for m in body):
        return
    if _declared_in(code, n + 1, end) & set(_WORD.findall(code[n][opening:close])):
        return  # the step would read a local of the body, not the name its header reads
    inner = next((_indent(lines[m]) for m in body if code[m].strip()), _indent(lines[n]) + "    ")
    before = [f"{_indent(lines[n])}{init};"] if init else []
    after = [f"{inner}{step};"] if step else []
    yield [*lines[:n], *before, head, *lines[n + 1 : end], *after, *lines[end:]]


def _declared_in(code: Sequence[str], first: int, last: int) -> set[str]:
    """The names the lines from `first` up to `last` declare."""
    found = (_declaration(code[m]) for m in range(first, last))
    return {_name(one) for one in found if one is not None}


def _statement(line: str, code: str) -> str:
    """The text of the simple statement on `line`, without its `;` or a comment."""
    return line[len(code) - len(code.lstrip()) : code.rstrip().rindex(";")].strip()


def _above(code: Sequence[str], n: int) -> int | None:
    """The nearest line above `n` that holds code."""
    return next((m for m in range(n - 1, -1, -1) if code[m].strip()), None)


def _simple_at(code: Sequence[str], row: int | None) -> bool:
    above = None if row is None else _above(code, row)
    return above is not None and _is_simple(code[row], code[above])


def _while_to_for(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """`while (c) {` as `for (; c;) {`, and with the statement before it and the last of its
    body as the for's init and step, when no `continue` would skip that step."""
    found = _loop(code, n, "while")
    if found is None:
        return
    opening, close, end = found
    condition = lines[n][opening + 1 : close].strip()
    head = f"{_keyword_head(lines[n], opening, 'while')}for ("
    tail = lines[n][close:]
    bare = "" if code[n][opening + 1 : close].strip() == "1" else f" {condition}"
    yield [*lines[:n], f"{head};{bare};{tail}", *lines[n + 1 :]]
    init, body = _above(code, n), _rows(code, n + 1, end)
    if not body or not _simple_at(code, init) or not _simple_at(code, body[-1]):
        return
    if any(_CONTINUE.search(code[m]) for m in body):
        return
    step = body[-1]
    if _declared_in(code, n + 1, end) & set(_WORD.findall(code[step])):
        return  # out of the body, the step would lose a local of it, or read an outer one
    pair = (_statement(lines[init], code[init]), _statement(lines[step], code[step]))
    yield [*lines[:init], *lines[init + 1 : n], f"{head}{pair[0]}; {condition}; {pair[1]}{tail}",
           *lines[n + 1 : step], *lines[step + 1 :]]  # fmt: skip


def _guarded_do(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """`while (c) { b }` as `if (c) { do { b } while (c); }`: c runs as often either way. Under a
    braceless if the new if would take the else after it."""
    found = _loop(code, n, "while")
    if found is None or _governed(code, n):
        return
    opening, close, end = found
    condition = lines[n][opening + 1 : close].strip()
    keyword = _keyword_head(lines[n], opening, "while")
    yield [*lines[:n], f"{keyword}if ({condition}){lines[n][close + 1 :]}",
           f"{_indent(lines[n])}do {{", *lines[n + 1 : end],
           f"{_indent(lines[end])}}} while ({condition});", *lines[end:]]  # fmt: skip


def _assignment(line: str, code: str) -> tuple[str, str] | None:
    """(the target, the value) of a line `x = v;` whose target is a simple operand and whose value
    holds no top-level comma, or None."""
    tokens = _tokens(code)
    end = _operand_end(tokens, 0)
    if end is None or end + 1 >= len(tokens) or tokens[end].text != "=" or tokens[-1].text != ";":
        return None
    if len(unitdefs._split_top(code[tokens[end].end : tokens[-1].start], ",")) != 1:
        return None
    target = line[tokens[0].start : tokens[end - 1].end]
    return target, line[tokens[end].end : tokens[-1].start].strip()


def _operand_text(text: str) -> str:
    """`text` as one operand of `?:`: a simple operand bare, anything else in parentheses."""
    tokens = _tokens(text)
    return text if tokens and _whole(tokens, 0) else f"({text})"


def _branch_pair(
    lines: Sequence[str], code: Sequence[str], n: int
) -> tuple[str, int, int, int] | None:
    """(the condition, the if's line, the else's line, the line past the statement) of an if/else
    on line `n` with one line in each branch, braced or not."""
    header = _header(code[n], "if")
    if header is None or _governed(code, n):
        return None
    opening, close, rest = header
    condition = lines[n][opening + 1 : close].strip()
    if rest == "{":
        found = _if_else(code, n)
        if found is None:
            return None
        _, _, middle, end = found
        rows = (_rows(code, n + 1, middle), _rows(code, middle + 1, end))
        if [len(one) for one in rows] != [1, 1]:
            return None
        return condition, rows[0][0], rows[1][0], end + 1
    if rest or n + 3 >= len(code) or code[n + 2].strip() != "else":
        return None
    return condition, n + 1, n + 3, n + 4


def _to_ternary(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """An if/else assigning one target in each branch as one `x = c ? a : b;`. The value of `?:`
    converts both branches to one type first, which can change the value stored."""
    found = _branch_pair(lines, code, n)
    if found is None:
        return
    condition, first, second, past = found
    one, other = _assignment(lines[first], code[first]), _assignment(lines[second], code[second])
    if one is None or other is None or one[0] != other[0]:
        return
    values = " : ".join(_operand_text(value) for value in (one[1], other[1]))
    yield [*lines[:n], f"{_indent(lines[n])}{one[0]} = {_operand_text(condition)} ? {values};",
           *lines[past:]]  # fmt: skip


def _ternary_parts(line: str, code: str) -> tuple[str, str, str] | None:
    """(the condition, the first value, the second) of the value of `x = c ? a : b;`, each with
    one `?` and one `:` at its top level."""
    value_at = code.index("=") + 1
    value_end = code.rstrip().rindex(";")
    questions = unitdefs._split_top(code[value_at:value_end], "?")
    if len(questions) != 2:
        return None
    colons = unitdefs._split_top(questions[1], ":")
    if len(colons) != 2 or "?" in questions[1]:
        return None
    question = value_at + len(questions[0])
    colon = question + 1 + len(colons[0])
    return (line[value_at:question].strip(), line[question + 1 : colon].strip(),
            line[colon + 1 : value_end].strip())  # fmt: skip


def _from_ternary(lines: Sequence[str], code: Sequence[str], n: int) -> Iterator[Lines]:
    """`x = c ? a : b;` as a braced if/else, the reverse of _to_ternary."""
    found = _assignment(lines[n], code[n])
    parts = None if found is None else _ternary_parts(lines[n], code[n])
    if parts is None or not all(parts) or _governed(code, n):
        return
    (condition, first, second), indent, target = parts, _indent(lines[n]), found[0]
    yield [*lines[:n], f"{indent}if ({condition}) {{", f"{indent}    {target} = {first};",
           f"{indent}}} else {{", f"{indent}    {target} = {second};", f"{indent}}}",
           *lines[n + 1 :]]  # fmt: skip


_BLOCK_REWRITES = ((_swapped_branches, REWRITE), (_dropped_else, REWRITE), (_added_else, REWRITE),
                   (_for_to_while, REWRITE), (_while_to_for, REWRITE), (_guarded_do, REWRITE),
                   (_to_ternary, CHANGED), (_from_ternary, CHANGED))  # fmt: skip


def rewrite_moves(text: str, span: tuple[int, int]) -> Iterator[Candidate]:
    """Each single rewrite of the body at `span`, line by line, after Echo's rules (todo
    search-rewrite-axis): an operand swap that mirrors a comparison or keeps a commutative
    operator, a regrouping of one associative operator (integers only for `+` and `*`), an
    if/else with its condition negated and its bodies swapped, an else dropped after an if that
    returns or added around the rest of its block, a for as a while and back, a while as a
    guarded do-while, and an if/else of one assignment as a ternary and back. Every rewrite keeps
    the meaning of the C but the ternaries, which are a statement move too (D-26). The rewrites
    read whole lines and simple operands only, so an expression split across lines is left
    alone. The branch and loop rewrites of the whole body come first, which Echo's rules aim at
    and REWRITE_SHARE may not leave room past."""
    lines = text.split("\n")
    code = _code(text).split("\n")
    rows = [n for n in range(span[0] + 1, span[1])
            if code[n].strip() and _declaration(code[n]) is None]  # fmt: skip
    for n in rows:
        for rule, axes in _BLOCK_REWRITES:
            for moved_lines in rule(lines, code, n):
                yield Candidate("\n".join(moved_lines), axes)
    integers = _integer_names(code, span)
    for n in rows:
        for moved in _expression_rewrites(lines[n], code[n], integers):
            yield Candidate("\n".join([*lines[:n], moved, *lines[n + 1 :]]), REWRITE)


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
    kept: list[_Scored] = field(default_factory=list)  # what SearchResult.kept is read from


@dataclass(frozen=True)
class _Scored:
    candidate: Candidate
    records: list[dict[str, Any]]  # one per cell
    compiled: list[batch.Compiled]  # one per cell

    @property
    def objects(self) -> list[Path]:
        return [one.job.obj for one in self.compiled]

    @property
    def rank(self) -> tuple[bool, float, float]:
        return max(_rank(record) for record in self.records)

    @property
    def stands(self) -> bool:
        """D-26: a variant with `statement` in its axes stands only when exact."""
        return self.rank[0] or "statement" not in self.candidate.axes


def _verdict(run: _Run, compiled: batch.Compiled) -> batch.Verdict:
    """judge's verdict of one compiled cell: one judge per distinct body. A body that cannot be
    read scores as judge scores it, under its failure key, and one that fails conversion scores
    as unjudged, so the search goes on. Neither counts as a body."""
    start = run.row.start
    if not compiled.ok:
        return batch.unjudged(run.row.end - start)
    try:
        body = batch.function_body(run.exe, compiled.job.obj, start)
        if isinstance(body, str):
            return batch.unjudged(run.row.end - start, body)
        key = batch.body_key(body)
        if key not in run.verdicts:
            run.verdicts[key] = batch.judge(run.exe, compiled.job.obj, start)
    except _UNREADABLE as exc:
        return batch.unjudged(run.row.end - start, f"not judged: {exc}")
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
        scored.append(_Scored(candidate, _records(run, cells), list(cells)))
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


def _best_cell(records: Sequence[dict[str, Any]]) -> int:
    return max(range(len(records)), key=lambda n: _rank(records[n]))


def _axis_moves(run: _Run, axis: str, best: _Scored) -> Iterator[Candidate]:
    """The moves of `axis` from `best`, each naming every axis its text moved along."""
    by_axis = {"type": type_moves, "rewrite": rewrite_moves, "statement": statement_moves,
               "scope": scope_moves}  # fmt: skip
    text, axes = best.candidate.text, best.candidate.axes
    span = function_span(text, run.name)
    if axis == "declaration":
        moves = declaration_axis(text, span, _slots(run, best.objects[_best_cell(best.records)]))
    else:
        moves = by_axis[axis](text, span)
    for move in moves:
        yield Candidate(move.text, (*axes, *(a for a in move.axes if a not in axes)))


def _walk(run: _Run, seen: set[str], best: _Scored, axis: str) -> _Scored:
    """Walk `axis` from `best`: a variant that stands and beats it becomes the base, and the axis
    starts again from there. It ends on exact, at the budget or when the moves run out."""
    moves = _axis_moves(run, axis, best)
    limit = min(BUDGET, run.compiles + REWRITE_SHARE) if axis == "rewrite" else BUDGET
    while not best.rank[0]:
        wave = _take(moves, seen, min(WAVE, (limit - run.compiles) // len(run.cells)))
        if not wave:
            break
        standing = [scored for scored in _wave(run, wave) if scored.stands]
        found = max([best, *standing], key=lambda scored: scored.rank)
        if found is not best:
            best = found
            run.kept.append(best)
            moves = _axis_moves(run, axis, best)
    return best


def _cells(committed: Rule) -> list[tuple[str, Rule]]:
    """The committed rule, then each search cell whose flags differ from it."""
    texts = [text for text in SEARCH_CELLS
             if batch.cell_rule(committed, text).flags != committed.flags]  # fmt: skip
    return batch.cells_for(committed, texts)


def _slots(run: _Run, obj: Path) -> batch.SlotMap:
    """function_slots of the winner. One that fails conversion holds no slot to read, so its map
    is that of an object with no function: the row's frame size is still worth reporting."""
    row = run.row
    try:
        return batch.function_slots(run.exe, obj, row.start)
    except _UNREADABLE:
        return batch.slot_map(b"", run.exe.flat[row.start : row.end], row.start, set())


def _result(run: _Run, best: _Scored) -> SearchResult:
    """Write the winner to best.c, which no wave touches, and its records to results.jsonl."""
    text, axes = best.candidate.text, best.candidate.axes
    path = run.root / "best.c"
    write_atomic(path, text.encode("ascii"))
    records = tuple({**batch.with_source(record, path, text), "axes": list(axes)}
                    for record in best.records)  # fmt: skip
    lines = "".join(json.dumps(record) + "\n" for record in records)
    write_atomic(run.root / "results.jsonl", lines.encode("utf-8"))
    slot_map = _slots(run, best.objects[_best_cell(records)])
    kept = {scored.candidate.text: scored for scored in (*run.kept, best)}
    return SearchResult(path, axes, records, run.compiles, len(run.verdicts), slot_map,
                        _scalars(text, run.name, slot_map),
                        tuple(_kept(scored) for scored in kept.values()))  # fmt: skip


def _kept(scored: _Scored) -> Kept:
    best = _best_cell(scored.records)
    return Kept(scored.candidate.text, scored.records[best], scored.compiled[best])


def _class(exe: ExeInputs, start: int, kept: Kept) -> str | None:
    """classify's class of a kept cell, or None: exact, not compiled, or not readable."""
    try:
        return classify.with_class(kept.record, exe, start, kept.compiled).get("class")
    except _UNREADABLE:
        return None


def _archived(exe: ExeInputs, start: int, kept: Kept) -> archive.Entry:
    record = kept.record
    return archive.Entry(archive.source_key(kept.text), record["exact"], record["score"],
                         record["stack_score"], _class(exe, start, kept), "search",
                         kept.text)  # fmt: skip


def _seed_text(source: str, name: str) -> str | None:
    """`source` ready to stand for the base, or None: not ASCII, refused by the check (a
    #pragma or inline assembly), or with no definition of `name`."""
    if not source.isascii() or batch.refusal(source) is not None:
        return None
    try:
        return split_declarators(source, function_span(source, name))
    except batch.BatchError:
        return None


def _seed_candidates(seeds: Sequence[str], name: str, base: str) -> list[Candidate]:
    """Each seed that can stand for the base and is not the base's own C, once."""
    keys = {archive.source_key(base)}
    found = []
    for seed in seeds:
        text = _seed_text(seed, name)
        if text is None or archive.source_key(text) in keys:
            continue
        keys.add(archive.source_key(text))
        found.append(Candidate(text, ("archive",)))
    return found


def run_search(
    exe: ExeInputs,
    row: FunctionRow,
    text: str,
    rules: Sequence[Rule],
    *,
    watcom_dir: Path,
    seeds: Sequence[str] = (),
) -> SearchResult:
    """Search `text`, which defines the function of `row`, under the unit's committed rule and
    SEARCH_CELLS: walk AXES, and walk them again while a round improves the base. It stops on an
    exact variant, at BUDGET compile jobs or when the moves run out. Each of `seeds`, other C of
    the same function, is compiled beside the base in the first wave, and the best of them all
    is the first base, the base itself on a tie (axis `archive`); with no seeds the search is a
    function of its input alone, as the curve needs it.
    OUT/<stem>/<start:08x>/ is cleared first: it holds v<nnnn>/, best.c and results.jsonl.
    BatchError when `text` does not define the function; a compile or a conversion that fails
    only scores 0."""
    name = exe.symbols.c_name(row.start)
    base = split_declarators(text, function_span(text, name))
    cells = _cells(batch.committed_rule(rules, exe.stem, row.unit))
    root = OUT / exe.stem / f"{row.start:08x}"
    if root.exists():
        shutil.rmtree(root)
    run = _Run(exe, row, name, cells, root, watcom_dir)
    first = [Candidate(base, ()), *_seed_candidates(seeds, name, base)]
    seen = {candidate.text for candidate in first}
    run.kept = _wave(run, first)
    best = max(run.kept, key=lambda scored: scored.rank)
    before = None
    while best is not before:
        before = best
        for axis in AXES:
            best = _walk(run, seen, best, axis)
    return _result(run, best)


def archived_search(
    exe: ExeInputs, row: FunctionRow, text: str, rules: Sequence[Rule], *, watcom_dir: Path
) -> SearchResult:
    """run_search seeded from the row's archive (archive.seeds over archive.load: the best
    candidate of each class, an agent's checks included), and what it kept recorded there.
    `reverseapoc search` runs this; the curve runs run_search, which reads no archive."""
    name = exe.symbols.c_name(row.start)
    base = archive.source_key(split_declarators(text, function_span(text, name)))
    usable = {}
    for entry in archive.load(exe.stem, row.start, name):
        seed = _seed_text(entry.source, name)
        if seed is not None and archive.source_key(seed) != base:
            usable[entry] = seed  # the base's own C takes no seed's place
    seeds = [usable[entry] for entry in archive.seeds(list(usable))]
    result = run_search(exe, row, text, rules, watcom_dir=watcom_dir, seeds=seeds)
    archive.record(exe.stem, row.start, [_archived(exe, row.start, one) for one in result.kept])
    return result
