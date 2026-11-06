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

from . import batch, check, contextpack, omf2elf, relocs, slots, unitdefs
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
class SearchResult:
    best: Path  # best.c: the winner's text, which every record names
    axes: tuple[str, ...]
    records: tuple[dict[str, Any], ...]  # one per cell of the winner, as results.jsonl holds them
    compiles: int
    bodies: int  # distinct function bodies judged
    slots: batch.SlotMap  # the winner's best cell against the row
    scalars: tuple[int, ...]  # the winner's mismatched slots that hold scalars

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


def _readable(text: str, span: tuple[int, int], memory: Sequence[slots.Local]) -> bool:
    """A frame can be read from `span`: every local has a size and a name of its own, no float
    stands in a tie, no `&` is ambiguous, no slot lies outside the declarations, as a parameter
    whose address is taken and an initialized aggregate do, and no local outside `memory` is under
    a slot, because a spilled short can move with its declaration (pr_spill_short) and then
    scalars are not out of reach of declaration moves."""
    code = _code(text).split("\n")
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
    hold scalars. Where the model cannot place them, declaration_moves stand."""
    memory = memory_locals(text, span)
    if not _computable(text, span, memory, slot_map):
        yield from declaration_moves(text, span)
        return
    order = slots.declaration_order(memory, _target(memory, slot_map))
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


def _best_cell(records: Sequence[dict[str, Any]]) -> int:
    return max(range(len(records)), key=lambda n: _rank(records[n]))


def _axis_moves(run: _Run, axis: str, best: _Scored) -> Iterator[Candidate]:
    """The moves of `axis` from `best`, each naming every axis its text moved along."""
    by_axis = {"type": type_moves, "statement": statement_moves, "scope": scope_moves}
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
    while not best.rank[0]:
        wave = _take(moves, seen, min(WAVE, (BUDGET - run.compiles) // len(run.cells)))
        if not wave:
            break
        standing = [scored for scored in _wave(run, wave) if scored.stands]
        found = max([best, *standing], key=lambda scored: scored.rank)
        if found is not best:
            best = found
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
    return SearchResult(path, axes, records, run.compiles, len(run.verdicts), slot_map,
                        _scalars(text, run.name, slot_map))  # fmt: skip


def run_search(
    exe: ExeInputs, row: FunctionRow, text: str, rules: Sequence[Rule], *, watcom_dir: Path
) -> SearchResult:
    """Search `text`, which defines the function of `row`, under the unit's committed rule and
    SEARCH_CELLS: walk AXES, and walk them again while a round improves the base. It stops on an
    exact variant, at BUDGET compile jobs or when the moves run out.
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
    seen = {base}
    (best,) = _wave(run, [Candidate(base, ())])
    before = None
    while best is not before:
        before = best
        for axis in AXES:
            best = _walk(run, seen, best, axis)
    return _result(run, best)
