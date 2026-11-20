"""Relocation-masked function bodies: twin transfer between and inside the EXEs (`reverseapoc
twins`) and the installed-to-CD function map (`reverseapoc cd-map`).

One matcher serves both (`masked`): a span's bytes with every LE fixup field and every rel32 field
of a call or jump leaving the span zeroed, plus the offsets it zeroed. Two spans with equal masked
bodies differ only in where they point. UFO2P.EXE and TACP.EXE share engine functions, and the
installed ("4") build shares part of its code with the CD v1.00 build, at shifted addresses (a
third of the rows on 2026-11-18; most others were compiled differently, not only moved).

twins (docs/workflow.md, Select): the game and thunk rows of every EXE with units, grouped by
masked body. A group with a matched row and an unmatched one is a transfer: the matched C, renamed
into the target's address space, at the target's INCLUDE_ASM marker. The renames come from the
pair itself: each LE fixup field and outgoing rel32 field at one offset of both bodies names a
source address and a target address. A name of the source's C whose address the body references
(exactly, or as the start of the data a displaced field points into, the nearest name below it) is
renamed to the target's name for the paired address; any other name is left as written. The C
copied is the definition and the file-scope declarations it needs (transitively; a function the
source unit defines is declared by its head), minus those the target unit already declares.

`twins --dry-run` prints the counts and the planned transfers and writes nothing. `twins` lands
each transfer through `flags approve`'s landing step (flags.land_unit): the unit written, the
container C89 lint, the container `gate EXE/UNIT --attempts 0` (the byte gate decides, never this
module), and one commit of the unit, status.csv and the feed whose trailer is
`Matched-By: reverseapoc twins`, so
stats count twin landings apart from model matches. A failed lint or gate restores every file and
the next transfer runs. Refused while a drive runs or inside a matching session.

cd-map: each functions.csv row of the installed build looked up in the CD build: at the address
the previous mapped row's shift predicts, else anywhere its longest unmasked run of at least
_MIN_ANCHOR bytes occurs and the whole masked body verifies (the nearest such address wins; no
two rows take one address). `identical` is the same address, `moved` another one, `unmapped`
none. OpenApoc's offsets describe the CD build (docs/toolchain.md), so the map translates them.
`cd-map --write`, like `twins`, is refused while a drive holds build/driver/drive.lock.
"""

from __future__ import annotations

import bisect
import functools
import os
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import contextpack, driver, flags, unitdefs, x86
from .check import ExeInputs, exe_stem, load_exe, select_exe, unit_rule_path
from .fileio import write_atomic
from .functions import (
    KIND_GAME,
    KIND_THUNK,
    FunctionRow,
    _address,
    _format_csv,
)
from .hooks import CLAIM_ENV
from .ingest import load_cd_builds
from .le import LE, Fixup
from .libmatch import _OBJ_EXECUTABLE, _unmasked_runs
from .status import MATCHED, read_status, status_path
from .symbols import SymbolError, SymbolTable
from .targets import hash_file, load_manifest, target_problems
from .units import UnitsError, scaffold_unit

_REL32 = 4  # bytes of a rel32 call or jump displacement
_GROUPED_KINDS = (KIND_GAME, KIND_THUNK)  # the rows a status.csv row can match
MATCHED_BY = "Matched-By: reverseapoc twins"  # the trailer of a twin landing (stats class by it)
TWINS_DIR = Path("build") / "twins"  # the commit message file, gitignored
COMMIT_MSG = "commit-msg.txt"
UNITS_CSV = "units.csv"
FUNC, DATA = "func", "data"  # how a C name links: `name_` or `_name` (unitdefs.c_name_of)

Runner = Callable[..., object]
Git = Callable[..., object]
Body = tuple[bytes, tuple[int, ...]]  # masked bytes, masked offsets


class TwinsError(ValueError):
    """A span lies outside the code, an input is missing or wrong, or twins may not run now."""


# ---- the matcher ----


@dataclass(frozen=True)
class Code:
    """One LE as the matcher sees it: the flat image, its fixups by field address, every byte
    a fixup field covers, and the [base, end) of its executable object."""

    flat: bytes
    fixups: Mapping[int, Fixup]
    fixup_bytes: frozenset[int]
    base: int
    end: int

    @classmethod
    def of(cls, le: LE) -> Code:
        obj = next((o for o in le.objects if o.flags & _OBJ_EXECUTABLE), None)
        if obj is None:
            raise TwinsError("the EXE has no executable object")
        fixups = le.fixups()
        covered = frozenset(fx.src_va + k for fx in fixups for k in range(fx.size))
        return cls(bytes(le.load_flat()), {fx.src_va: fx for fx in fixups}, covered, obj.base,
                   obj.end)  # fmt: skip

    def check_span(self, start: int, length: int) -> None:
        if length <= 0 or start < self.base or start + length > self.end:
            raise TwinsError(f"{_address(start)}+{length:#x} lies outside the code object "
                             f"{_address(self.base)}..{_address(self.end)}")  # fmt: skip


def _outgoing(code: Code, start: int, length: int) -> Iterator[x86.Insn]:
    """The rel32 calls and jumps of the span whose destination lies outside it."""
    end = start + length
    for insn in x86.decode(code.flat[start:end], start):
        if insn.rel32_field is not None and not start <= insn.branch_target < end:
            yield insn


def masked(code: Code, start: int, length: int) -> Body:
    """The span's bytes with its LE fixup fields and outgoing rel32 fields zeroed, and the
    offsets zeroed, sorted."""
    code.check_span(start, length)
    zeroed = {va - start for va in range(start, start + length) if va in code.fixup_bytes}
    for insn in _outgoing(code, start, length):
        zeroed.update(range(insn.rel32_field - start, insn.rel32_field - start + _REL32))
    offsets = tuple(sorted(k for k in zeroed if k < length))
    body = bytearray(code.flat[start : start + length])
    for k in offsets:
        body[k] = 0
    return bytes(body), offsets


# ---- twins: grouping ----


@dataclass(frozen=True)
class Member:
    exe: str  # manifest name
    row: FunctionRow
    matched: bool
    c_name: str  # what C calls it: the symbols.csv name when renamed, else the placeholder


@dataclass(frozen=True)
class ExeCount:
    exe: str
    rows: int  # game and thunk rows
    groups: int  # bodies two or more of its rows share
    grouped: int  # the rows in those groups


@dataclass(frozen=True)
class Transfer:
    source: Member  # matched
    target: Member  # unmatched
    reason: str = ""  # why there is no candidate; "" when there is one
    renames: Mapping[str, str] = field(default_factory=dict)
    prelude: tuple[str, ...] = ()  # the renamed file-scope items the definition needs
    definition: str = ""  # the renamed definition
    candidate: str = ""  # the target unit with both at its marker (`place`), as planned

    def line(self) -> str:
        t, s = self.target, self.source
        what = (f"{t.exe} {t.row.name} ({t.row.unit}) <- {s.exe} {s.row.name} ({s.row.unit})")
        if self.reason:
            return f"  skipped   {what}: {self.reason}"
        return f"  candidate {what}, {len(self.renames)} renames"


@dataclass(frozen=True)
class TwinsPlan:
    counts: tuple[ExeCount, ...]
    cross_bodies: int  # bodies rows of two or more EXEs share
    cross_rows: Mapping[str, int]  # per EXE, its rows in those bodies
    transfers: tuple[Transfer, ...]

    def lines(self) -> list[str]:
        lines = ["twins: game and thunk rows whose relocation-masked bodies are identical"]
        width = max((len(c.exe) for c in self.counts), default=0)
        lines += [f"  {c.exe.ljust(width)}  {c.rows} rows; {c.groups} bodies shared by 2+ rows "
                  f"inside the EXE ({c.grouped} rows)" for c in self.counts]  # fmt: skip
        per_exe = ", ".join(f"{exe} {n} rows" for exe, n in self.cross_rows.items())
        lines.append(f"  across the EXEs: {self.cross_bodies} bodies ({per_exe})")
        ready = [t for t in self.transfers if not t.reason]
        lines.append(f"  {len(self.transfers)} unmatched rows have a matched twin: {len(ready)} "
                     f"candidates, {len(self.transfers) - len(ready)} skipped")  # fmt: skip
        lines += [t.line() for t in self.transfers]
        return lines


def _groups(exes: Mapping[str, ExeInputs], codes: Mapping[str, Code],
            matched: Mapping[str, set[int]]) -> dict[Body, list[Member]]:  # fmt: skip
    groups: dict[Body, list[Member]] = defaultdict(list)
    for name, inputs in exes.items():
        for row in inputs.rows:
            if row.kind not in _GROUPED_KINDS or row.end <= row.start:
                continue
            body = masked(codes[name], row.start, row.end - row.start)
            c_name = inputs.symbols.c_name(row.start)
            groups[body].append(Member(name, row, row.start in matched[name], c_name))
    return groups


def _counts(groups: Mapping[Body, list[Member]], names: Sequence[str]) -> tuple[ExeCount, ...]:
    out = []
    for name in names:
        sizes = [n for n in (sum(m.exe == name for m in g) for g in groups.values()) if n]
        shared = [n for n in sizes if n > 1]
        out.append(ExeCount(name, sum(sizes), len(shared), sum(shared)))
    return tuple(out)


def _pairs(groups: Mapping[Body, list[Member]]) -> Iterator[tuple[list[Member], Member]]:
    """(the group's matched rows in manifest and address order, target) for each unmatched row
    of a group with a matched row."""
    for members in groups.values():
        sources = [m for m in members if m.matched]
        if not sources:
            continue
        for target in members:
            if not target.matched:
                yield sources, target


def _first_candidate(sources: Sequence[Member], target: Member,
                     attempt: Callable[[Member, Member], Transfer]) -> Transfer:  # fmt: skip
    """The first source that gives a candidate, else the first source's reason."""
    first = None
    for source in sources:
        transfer = attempt(source, target)
        if not transfer.reason:
            return transfer
        first = first or transfer
    return first


# ---- twins: the C of a transfer ----

_COMMENT_OR_LITERAL = re.compile(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'",
                                 re.S)  # fmt: skip
_NOT_NEWLINE = re.compile(r"[^\n]")
_IDENT = re.compile(unitdefs._IDENT)
_DIRECTIVE = re.compile(r"[ \t]*#[ \t]*(\w*)")
_DEFINE_NAME = re.compile(r"[ \t]*#[ \t]*define[ \t]+(\w+)")
_IF_ZERO = re.compile(r"[ \t]*#[ \t]*if[ \t]+0\b")
_OPENS = frozenset({"if", "ifdef", "ifndef"})
_COMMON_H = '#include "common.h"'
DECL, DEF, INCLUDE, MACRO, MARKER, DIRECTIVE = ("decl", "def", "include", "define", "marker",
                                                "directive")  # fmt: skip


@dataclass(frozen=True)
class _Item:
    """One file-scope piece of a unit: a declaration, a definition, or a directive line."""

    kind: str
    text: str  # from its first code character; a definition: its head as a prototype
    declared: frozenset[str]
    used: frozenset[str]  # a definition: by its head
    source: str = ""  # a definition: all of it


def _blank(text: str) -> str:
    """`text` with comments and literals turned into spaces, newlines kept: same length."""
    return _COMMENT_OR_LITERAL.sub(lambda m: _NOT_NEWLINE.sub(" ", m.group()), text)


def _idents(code: str) -> frozenset[str]:
    return frozenset(_IDENT.findall(code)) - unitdefs.C_KEYWORDS


def _directive(line: str) -> _Item:
    """An #include (copied), a #define (copied when needed) or any other directive (never
    copied: configure.py allows no live conditional, and an #undef is the target's business)."""
    kind = _DIRECTIVE.match(line).group(1)
    text = line.strip()
    if kind == "include":
        return _Item(INCLUDE, text, frozenset(), frozenset())
    define = _DEFINE_NAME.match(line)
    if define is not None:
        return _Item(MACRO, text, frozenset({define.group(1)}), _idents(_blank(line)))
    return _Item(DIRECTIVE, text, frozenset(), frozenset())


def _line_end(blank: str, i: int) -> int:
    """The index after the logical line starting at `i`: a backslash before the newline
    continues it."""
    while True:
        stop = blank.find("\n", i)
        if stop < 0:
            return len(blank)
        if not blank[i:stop].rstrip(" \t\r").endswith("\\"):
            return stop + 1
        i = stop + 1


def _dead_line(stack: list[str], line: str) -> bool:
    """Whether `line` is blanked as part of an `#if 0` branch, updating `stack` ("dead",
    "nested" inside a dead branch, or "else" for the live #else of an `#if 0`)."""
    directive = _DIRECTIVE.match(line)
    word = directive.group(1) if directive else None
    top = stack[-1] if stack else None
    if top not in ("dead", "nested"):
        if _IF_ZERO.match(line):
            stack.append("dead")
            return True
        if top == "else" and word == "endif":
            stack.pop()
            return True
        if top == "else" and word in _OPENS:
            stack.append("live")
        elif top == "live" and word == "endif":
            stack.pop()
        return False
    if word in _OPENS:
        stack.append("nested")
    elif word == "else" and top == "dead":
        stack[-1] = "else"
    elif word == "endif":
        stack.pop()
    return True


def _drop_dead(blank: str) -> str:
    """`blank` with each `#if 0` branch and its own directives turned into spaces; the #else
    branch of one stays (configure.py's code_text drops the same branches)."""
    stack: list[str] = []
    lines = blank.split("\n")
    return "\n".join(_NOT_NEWLINE.sub(" ", line) if _dead_line(stack, line) else line
                     for line in lines)  # fmt: skip


def _piece(text: str, blank: str, start: int, end: int, brace: int | None) -> _Item | None:
    """The item text[start:end] (comments before its first code character dropped); `brace` is
    the `{` of a definition's body."""
    first = start + len(blank[start:end]) - len(blank[start:end].lstrip())
    if first >= end:
        return None
    if brace is not None:
        head = text[first:brace].rstrip()
        return _Item(DEF, head + ";", unitdefs.declared_names(head + ";"),
                     _idents(blank[first:brace]), text[first:end])  # fmt: skip
    piece = text[first:end]
    if re.fullmatch(contextpack.INCLUDE_ASM_MARKER.format(name=unitdefs._IDENT), piece):
        return _Item(MARKER, piece, frozenset(), frozenset())
    return _Item(DECL, piece, unitdefs.declared_names(piece), _idents(blank[first:end]))


def _items(text: str) -> list[_Item]:
    """The file-scope items of a unit, in file order: a `;` at brace depth 0 ends a declaration,
    the `}` closing a body that follows a `)` ends a definition, and a directive line outside
    any pending item is an item of its own."""
    blank = _drop_dead(_blank(text))
    items: list[_Item | None] = []
    start = depth = i = 0
    brace: int | None = None
    while i < len(blank):
        line_start = i == 0 or blank[i - 1] == "\n"
        if depth == 0 and line_start and _DIRECTIVE.match(blank, i) and not blank[start:i].strip():
            stop = _line_end(blank, i)
            items.append(_directive(text[i:stop]))
            start = i = stop
            continue
        char = blank[i]
        if char == "{":
            if depth == 0:
                brace = i if blank[start:i].rstrip().endswith(")") else None
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and brace is not None:
                items.append(_piece(text, blank, start, i + 1, brace))
                start, brace = i + 1, None
        elif char == ";" and depth == 0:
            items.append(_piece(text, blank, start, i + 1, None))
            start = i + 1
        i += 1
    return [item for item in items if item is not None]


def _needed(items: Sequence[_Item], definition: str, own: str) -> list[_Item]:
    """The items `definition` needs, transitively, in file order: each that declares a name it
    (or an item already needed) uses, but never the definition of `own`. Every #include but
    common.h is kept."""
    used = set(_idents(_blank(definition)))
    chosen: set[int] = set()
    grew = True
    while grew:
        grew = False
        for k, item in enumerate(items):
            if k in chosen or item.kind == MARKER or not item.declared & used:
                continue
            if item.kind == DEF and own in item.declared:
                continue
            chosen.add(k)
            used |= item.used
            grew = True
    return [item for k, item in enumerate(items)
            if k in chosen or (item.kind == INCLUDE and item.text != _COMMON_H)]  # fmt: skip


def _link(table: SymbolTable, ident: str) -> tuple[int, str] | None:
    """(address, FUNC or DATA) of a C name in `table`, or None for a name that is no symbol."""
    for kind, linker in ((FUNC, ident + unitdefs.FUNC_LINK_SUFFIX),
                         (DATA, unitdefs.DATA_LINK_PREFIX + ident)):  # fmt: skip
        try:
            return table.address_of(linker), kind
        except SymbolError:
            continue
    return None


def _c_name(table: SymbolTable, va: int, kind: str) -> str | None:
    """The C name `table` gives `va` linked as `kind`, or None when it has none."""
    try:
        linker = table.linker_name(va, data=kind == DATA)
    except SymbolError:
        return None
    if kind == FUNC:
        suffix = unitdefs.FUNC_LINK_SUFFIX
        return linker[: -len(suffix)] if linker.endswith(suffix) else None
    prefix = unitdefs.DATA_LINK_PREFIX
    return linker[len(prefix) :] if linker.startswith(prefix) else None


_CONFLICT = -1  # one source address paired with two target addresses


def address_pairs(a: Code, a_start: int, b: Code, b_start: int, length: int) -> dict[int, int]:
    """Source address -> target address for every LE fixup field and outgoing rel32 field at
    one offset of two spans with equal masked bodies (_CONFLICT for a source address paired
    with two target addresses)."""
    pairs: dict[int, int] = {}

    def add(va_a: int, va_b: int) -> None:
        pairs[va_a] = va_b if pairs.get(va_a, va_b) == va_b else _CONFLICT

    for k in range(length):
        fa, fb = a.fixups.get(a_start + k), b.fixups.get(b_start + k)
        if fa is not None and fb is not None:
            add(fa.target_va, fb.target_va)
    theirs = {i.va - b_start: i.branch_target for i in _outgoing(b, b_start, length)}
    for insn in _outgoing(a, a_start, length):
        if insn.va - a_start in theirs:
            add(insn.branch_target, theirs[insn.va - a_start])
    return pairs


def _paired(va: int, kind: str, pairs: Mapping[int, int], above: int | None) -> int | None:
    """The target address of `va`: its own pair, else (data) the nearest paired address in
    (va, above) shifted back by its displacement; None when the body never references it."""
    if va in pairs:
        return pairs[va]
    if kind == FUNC:
        return None
    inside = [t for t in pairs if va < t and (above is None or t < above)]
    if not inside:
        return None
    nearest = min(inside)
    return _CONFLICT if pairs[nearest] == _CONFLICT else pairs[nearest] - (nearest - va)


def _renames(names: Iterable[str], a: SymbolTable, b: SymbolTable,
             pairs: Mapping[int, int]) -> tuple[dict[str, str], str]:  # fmt: skip
    """(source C name -> target C name, "") or ({}, why not). A displaced field is searched no
    further than the next address a name here or a symbols.csv row of the source gives."""
    linked = {ident: found for ident in sorted(names) if (found := _link(a, ident)) is not None}
    addresses = sorted({va for va, _ in linked.values()} | set(a.symbols))
    renames: dict[str, str] = {}
    for ident, (va, kind) in linked.items():
        nxt = bisect.bisect_right(addresses, va)
        target = _paired(va, kind, pairs, addresses[nxt] if nxt < len(addresses) else None)
        if target is None:
            continue
        if target == _CONFLICT:
            return {}, f"{ident} pairs with two target addresses"
        name = _c_name(b, target, kind)
        if name is None:
            return {}, (f"{ident} pairs with {_address(target)}, which the target EXE names no "
                        f"{kind}")
        if name != ident:
            renames[ident] = name
    return renames, ""


def _rename(text: str, renames: Mapping[str, str]) -> str:
    """`text` with each name renamed in code and comments, never inside a string or character
    literal (its bytes are data the gate compares)."""
    if not renames:
        return text
    literals = [m.span() for m in _COMMENT_OR_LITERAL.finditer(text) if m.group()[0] in "\"'"]
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, renames)) + r")\b")

    def swap(m: re.Match[str]) -> str:
        inside = any(lo <= m.start() < hi for lo, hi in literals)
        return m.group(1) if inside else renames[m.group(1)]

    return pattern.sub(swap, text)


def _read_unit(path: Path) -> str:
    """A unit file as UTF-8 text with LF line ends (the committed form, .gitattributes), so a
    block from one file never mixes line ends into another."""
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _unit_text(repo: Path, inputs: ExeInputs, unit: str) -> str:
    """The committed src/<exe>/<unit>.c, or its INCLUDE_ASM scaffold when there is none."""
    path = repo / unit_rule_path(inputs.stem, unit)
    if path.is_file():
        return _read_unit(path)
    unit_row = next((u for u in inputs.units if u.unit == unit), None)
    if unit_row is None:
        raise TwinsError(f"{inputs.target.name}: no unit {unit} in {inputs.units_path}")
    try:
        return scaffold_unit(inputs.target.name, unit_row, inputs.rows)
    except UnitsError as exc:
        raise TwinsError(f"{inputs.target.name}/{unit}: cannot scaffold the unit ({exc})") from None


def place(unit_text: str, target: Member, prelude: Sequence[str], definition: str) -> str | None:
    """`unit_text` with the target's INCLUDE_ASM marker (its functions.csv placeholder, or after
    a symbols.csv rename its new C name, as unitdefs allows) replaced by the prelude items the
    text before the marker does not declare or include yet, then `definition`. None without a
    marker (the unit defines the row already)."""
    names = "|".join(re.escape(n) for n in sorted({target.row.name, target.c_name}))
    marker = re.search(contextpack.INCLUDE_ASM_MARKER.format(name=f"(?:{names})"), unit_text)
    if marker is None:
        return None
    before = unit_text[: marker.start()]
    declared, lines = unitdefs.declared_names(before), set(before.splitlines())
    kept = [text for text in prelude if text not in lines
            and not (unitdefs.declared_names(text) or {text}) <= declared]  # fmt: skip
    block = "\n".join(kept) + "\n\n" + definition if kept else definition
    return before + block + unit_text[marker.end() :]


@dataclass(frozen=True)
class _Exes:
    repo: Path
    inputs: Mapping[str, ExeInputs]
    codes: Mapping[str, Code]


def _transfer(exes: _Exes, source: Member, target: Member) -> Transfer:
    a, b = exes.inputs[source.exe], exes.inputs[target.exe]
    own_a, own_b = source.c_name, target.c_name
    path = unit_rule_path(a.stem, source.row.unit)
    if not (exes.repo / path).is_file():
        return Transfer(source, target, f"{path} is missing")
    text = _read_unit(exes.repo / path)
    items = _items(text)
    definition = next((i.source for i in items if i.kind == DEF and own_a in i.declared), None)
    if definition is None:
        return Transfer(source, target, f"{path} does not define {own_a}")
    pairs = address_pairs(exes.codes[source.exe], source.row.start, exes.codes[target.exe],
                          target.row.start, source.row.end - source.row.start)  # fmt: skip
    needed = _needed(items, definition, own_a)
    # the names the body can reference: its own and those of the macros it expands
    names = _idents(_blank(definition)).union(*(i.used for i in needed if i.kind == MACRO))
    renames, why = _renames(names - {own_a}, a.symbols, b.symbols, pairs)
    if why:
        return Transfer(source, target, why)
    renames = {**renames, own_a: own_b} if own_a != own_b else renames
    unit = _unit_text(exes.repo, b, target.row.unit)
    prelude = tuple(_rename(item.text, renames) for item in needed)
    definition = _rename(definition, renames)
    candidate = place(unit, target, prelude, definition)
    if candidate is None:
        return Transfer(source, target, f"{unit_rule_path(b.stem, target.row.unit)} has no "
                                        f"INCLUDE_ASM({target.row.name}) marker")  # fmt: skip
    return Transfer(source, target, "", renames, prelude, definition, candidate)


def plan_twins(*, repo: Path, orig_dir: Path, manifest: Path) -> TwinsPlan:
    """Group the game and thunk rows of every EXE with units by masked body and plan each
    transfer. Reads only."""
    repo = Path(repo)
    config = repo / "config"
    targets = [t for t in load_manifest(manifest)
               if (config / exe_stem(t.name) / UNITS_CSV).is_file()]  # fmt: skip
    names = [t.name for t in targets]
    inputs = {t.name: load_exe(t, orig_dir=Path(orig_dir), manifest=Path(manifest),
                               config_root=config) for t in targets}  # fmt: skip
    codes = {name: Code.of(i.le) for name, i in inputs.items()}
    matched = {name: {r.start for r in read_status(status_path(config, i.stem))
                      if r.status == MATCHED} for name, i in inputs.items()}  # fmt: skip
    groups = _groups(inputs, codes, matched)
    order = {name: n for n, name in enumerate(names)}
    for members in groups.values():
        members.sort(key=lambda m: (order[m.exe], m.row.start))
    cross = [g for g in groups.values() if len({m.exe for m in g}) > 1]
    cross_rows = {name: sum(m.exe == name for g in cross for m in g) for name in names}
    exes = _Exes(repo, inputs, codes)
    attempt = functools.partial(_transfer, exes)
    transfers = tuple(_first_candidate(s, t, attempt) for s, t in _pairs(groups))
    return TwinsPlan(_counts(groups, names), len(cross), cross_rows, transfers)


# ---- twins: landing ----


@dataclass(frozen=True)
class LandReport:
    landed: tuple[tuple[str, str], ...]  # (EXE, function)
    failed: tuple[tuple[str, str, str], ...]  # (EXE, function, why)
    lines: tuple[str, ...]

    def format(self) -> str:
        return "\n".join(self.lines)


def _message(t: Transfer, stem: str, source_stem: str) -> str:
    s, row = t.source, t.target.row
    lines = [f"feat({stem}): match {row.name} in {row.unit} as a twin of {source_stem} "
             f"{s.row.name} (C89)", "",
             f"twin of {s.exe} {s.row.name} ({s.row.unit}): the relocation-masked bodies are "
             "identical; no model session",
             *(f"rename {old} -> {new}" for old, new in sorted(t.renames.items())),
             "container lint ok, gate ok (relocation check and both SHA-1s)", "",
             MATCHED_BY]  # fmt: skip
    return "\n".join(lines) + "\n"


class _Lander:
    def __init__(self, repo: Path, plan: TwinsPlan, runner: Runner, git: Git) -> None:
        self.repo, self.runner, self.git = repo, runner, git
        self.stems = {c.exe: exe_stem(c.exe) for c in plan.counts}

    def paths(self, t: Transfer) -> list[str]:
        stem = self.stems[t.target.exe]
        return [unit_rule_path(stem, t.target.row.unit),
                status_path(Path("config"), stem).as_posix(), driver.FEED]  # fmt: skip

    def land(self, t: Transfer) -> tuple[bool, str]:
        """(True, commit) or (False, why) with every file restored; a path with uncommitted
        changes fails the transfer before anything is written."""
        paths = self.paths(t)
        try:
            flags.refuse_dirty(self.git, paths)
        except flags.FlagsError as exc:
            return False, str(exc)
        stem = self.stems[t.target.exe]
        try:
            commit = flags.land_unit(self.repo, self.runner, self.git, paths=paths, unit=paths[0],
                                     gate_unit=f"{stem}/{t.target.row.unit}", attempts=0,
                                     write=functools.partial(self._write, t, paths[0]),
                                     passed=functools.partial(self._check_matched, t, stem),
                                     message=_message(t, stem, self.stems[t.source.exe]),
                                     message_file=self.repo / TWINS_DIR / COMMIT_MSG)  # fmt: skip
            return True, commit
        except flags.LandingFailed as exc:
            return False, str(exc)

    def _write(self, t: Transfer, rel: str) -> None:
        """The target unit as it is now (an earlier landing may have changed it) with the
        transfer placed at the marker."""
        path = self.repo / rel
        text = (place(_read_unit(path), t.target, t.prelude, t.definition) if path.is_file()
                else t.candidate)  # no file yet: the candidate was planned on the scaffold
        if text is None:
            raise flags.LandingFailed(f"{rel} has no INCLUDE_ASM({t.target.row.name}) marker "
                                      "any more")  # fmt: skip
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, text.encode("utf-8"))

    def _check_matched(self, t: Transfer, stem: str) -> None:
        rows = read_status(status_path(self.repo / "config", stem))
        if not any(r.start == t.target.row.start and r.status == MATCHED for r in rows):
            raise flags.LandingFailed("the gate passed without a matched row for "
                                      f"{t.target.row.name}")  # fmt: skip


def land_twins(*, repo: Path, orig_dir: Path, manifest: Path, runner: Runner | None = None,
               git: Git | None = None,
               env: Mapping[str, str] | None = None) -> LandReport:  # fmt: skip
    """Plan, then land every candidate in order (module docstring). Refused inside a matching
    session and while a drive holds build/driver/drive.lock (held throughout)."""
    repo = Path(repo)
    if (os.environ if env is None else env).get(CLAIM_ENV):
        raise TwinsError(f"{CLAIM_ENV} is set: a matching session never lands twins; run "
                         "`reverseapoc twins` outside the driver")  # fmt: skip
    lock = flags.hold_drive_lock(repo)
    try:
        plan = plan_twins(repo=repo, orig_dir=orig_dir, manifest=manifest)
        lander = _Lander(repo, plan, runner or driver.command_runner(repo),
                         git or driver.git_runner(repo))  # fmt: skip
        landed, failed, lines = [], [], plan.lines()
        for t in (t for t in plan.transfers if not t.reason):
            ok, detail = lander.land(t)
            who = (t.target.exe, t.target.row.name)
            if ok:
                landed.append(who)
                lines.append(f"landed {who[0]} {who[1]} in commit {detail}")
            else:
                failed.append((*who, detail))
                lines.append(f"failed {who[0]} {who[1]}: {detail}; every file is restored")
        lines.append(f"{len(landed)} twins landed, {len(failed)} failed the lint or the gate")
        return LandReport(tuple(landed), tuple(failed), tuple(lines))
    finally:
        lock.release()


# ---- cd-map: the installed build against the CD v1.00 build ----

IDENTICAL, MOVED, UNMAPPED = "identical", "moved", "unmapped"
CD_MAP_CSV = "cd-map.csv"
CD_MAP_COLUMNS = ("start", "end", "name", "kind", "cd_start", "status")
CD_MAP_COMMENT = "# generated by: uv run reverseapoc cd-map {name} --write; do not edit"
_MIN_ANCHOR = 4  # the shortest unmasked run a row is searched for away from its predicted place


@dataclass(frozen=True)
class CdMapRow:
    row: FunctionRow  # the installed build's
    cd_start: int | None
    status: str


@dataclass(frozen=True)
class _Wanted:
    """One installed row's masked body and its unmasked runs (the bytes a candidate must
    hold as they are)."""

    body: Body
    runs: tuple[tuple[int, int], ...]

    @classmethod
    def of(cls, body: Body) -> _Wanted:
        return cls(body, tuple(_unmasked_runs(len(body[0]), frozenset(body[1]))))


def _verifies(cd: Code, at: int, want: _Wanted) -> bool:
    """The masked body of the CD span at `at` equals the row's: its unmasked runs compared
    first, as raw bytes, before the decode."""
    data, length = want.body[0], len(want.body[0])
    if at < cd.base or at + length > cd.end:
        return False
    if any(cd.flat[at + lo : at + hi] != data[lo:hi] for lo, hi in want.runs):
        return False
    return masked(cd, at, length) == want.body


def _find(cd: Code, want: _Wanted, predicted: int, taken: set[int]) -> int | None:
    """Where in the CD code the row is: `predicted`, else the nearest verified hit of its
    longest unmasked run; never an address another row took."""
    if predicted not in taken and _verifies(cd, predicted, want):
        return predicted
    lo, hi = max(want.runs, key=lambda run: run[1] - run[0], default=(0, 0))
    if hi - lo < _MIN_ANCHOR:
        return None
    needle, found = want.body[0][lo:hi], []
    hit = cd.flat.find(needle, cd.base + lo, cd.end)
    while hit >= 0:
        at = hit - lo
        if at not in taken and _verifies(cd, at, want):
            found.append(at)
        hit = cd.flat.find(needle, hit + 1, cd.end)
    return min(found, key=lambda at: (abs(at - predicted), at), default=None)


def cd_map(rows: Sequence[FunctionRow], installed: Code, cd: Code) -> list[CdMapRow]:
    """Each row of the installed build placed in the CD build (module docstring); no two rows
    share a CD address."""
    out, shift, taken = [], 0, set()
    for row in sorted(rows, key=lambda r: r.start):
        at = None
        if row.end > row.start:
            want = _Wanted.of(masked(installed, row.start, row.end - row.start))
            at = _find(cd, want, row.start + shift, taken)
        if at is None:
            out.append(CdMapRow(row, None, UNMAPPED))
            continue
        taken.add(at)
        shift = at - row.start
        out.append(CdMapRow(row, at, IDENTICAL if at == row.start else MOVED))
    return out


def coverage(mapped: Sequence[CdMapRow]) -> str:
    parts = []
    for status in (IDENTICAL, MOVED, UNMAPPED):
        rows = [m.row for m in mapped if m.status == status]
        parts.append(f"{len(rows)} {status} ({sum(r.end - r.start for r in rows)} bytes)")
    return f"{', '.join(parts)} of {len(mapped)} rows"


def format_cd_map(mapped: Sequence[CdMapRow], name: str) -> str:
    comment = CD_MAP_COMMENT.format(name=name) + f"\n# coverage: {coverage(mapped)}"
    cells = ([_address(m.row.start), _address(m.row.end), m.row.name, m.row.kind,
              "" if m.cd_start is None else _address(m.cd_start), m.status]
             for m in mapped)  # fmt: skip
    return _format_csv(comment, CD_MAP_COLUMNS, cells)


def build_cd_map(exe: str, *, orig_dir: Path, manifest: Path, config_root: Path,
                 cd_dir: Path) -> tuple[str, list[CdMapRow]]:  # fmt: skip
    """(manifest name, the map) of one EXE: its installed build from orig/, its CD build from
    `cd_dir` (where `ingest --cd` puts it), each verified against the manifest."""
    target = select_exe(load_manifest(manifest), exe, manifest)
    inputs = load_exe(target, orig_dir=orig_dir, manifest=manifest, config_root=config_root)
    build = next((b for b in load_cd_builds(manifest) if b.name == target.name), None)
    if build is None:
        raise TwinsError(f"{manifest}: no [[cd_builds]] entry named {target.name}")
    path = Path(cd_dir) / build.name
    if not path.is_file():
        raise TwinsError(f"{path} not found: extract the CD build with `uv run reverseapoc "
                         "ingest --cd IMAGE`")  # fmt: skip
    problems = target_problems(build, hash_file(path))
    if problems:
        raise TwinsError(f"{path} is not the CD build: {'; '.join(problems)}")
    return target.name, cd_map(inputs.rows, Code.of(inputs.le), Code.of(LE(path)))


def cd_map_path(config_root: Path, name: str) -> Path:
    return Path(config_root) / exe_stem(name) / CD_MAP_CSV


def write_cd_map(config_root: Path, name: str, mapped: Sequence[CdMapRow]) -> Path:
    """config/<exe>/cd-map.csv, written while build/driver/drive.lock of the checkout that
    holds `config_root` is free (nothing writes the checkout during a drive)."""
    path = cd_map_path(config_root, name)
    lock = flags.hold_drive_lock(Path(config_root).resolve().parent)
    try:
        write_atomic(path, format_cd_map(mapped, name).encode("utf-8"))
    finally:
        lock.release()
    return path
