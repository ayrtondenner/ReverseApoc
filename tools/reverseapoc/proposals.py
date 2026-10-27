"""The D-19 naming-proposal format: what a session writes to `<attempt dir>/proposals.jsonl`.

The driver is the only writer of shared naming state (D-19): the names in
`config/<exe>/symbols.csv` and the shared headers under `include/`. A session (its hooks allow
it only its view unit, notes.md and this file) asks for a change by appending one JSON object
per line:

- `{"op": "rename", "exe", "kind", "address", "name", "evidence"}`: give the func or data row
  at `address` (`0x%08X`) of `exe` (`ufo2p` or `tacp`) the C name `name`; the driver derives
  the linker name (unitdefs.c_name_of's rule run backwards);
- `{"op": "header", "path", "text", "evidence"}`: the whole text of one shared header
  `include/<name>.h` (D-19's struct fields, enums and constants are written this way).

`evidence` is `<kind>: <text>`, kind one of EVIDENCE_KINDS, the kinds readlint's header rule
cites (D-21: game evidence first, OpenApoc vocabulary allowed, nothing copied).

parse_line and read_proposals check the shape only: exact key sets, string values, the op,
kind, exe and address forms and the evidence form. Whether a proposal may be applied
(name_problem, rename_problem, header_problem) is a separate question the driver's rename step
(07-34) asks under the gate lock, against the naming state of that moment.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from . import hooks, unitdefs
from .functions import (
    ADDRESS_DIGITS,
    KIND_GAME,
    KIND_RUNTIME,
    KIND_THUNK,
    SYMBOL_KINDS,
    FunctionRow,
    SymbolRow,
    data_name,
    game_name,
)
from .targets import REPO_ROOT

OP_RENAME, OP_HEADER = "rename", "header"
OPS = (OP_RENAME, OP_HEADER)
KINDS = SYMBOL_KINDS  # symbols.csv kinds: ("func", "data")
FUNC_KIND = KINDS[0]
NAME_MAX = 63  # characters of a C name (C89 guarantees only 31 significant; Watcom reads more)
_KIB = 1024
_MIB = 1024 * _KIB
HEADER_TEXT_MAX = 64 * _KIB  # characters (= bytes: the text is ASCII) of one header proposal
# Fix round 1: one line holds one maximal header after JSON escaping (json.dumps doubles a
# newline, tab, quote or backslash), with room for the keys; a file holds a few dozen lines.
PROPOSAL_LINE_MAX = 3 * HEADER_TEXT_MAX  # bytes of one proposals.jsonl line (192 KiB)
PROPOSALS_FILE_MAX = 4 * _MIB  # bytes of one proposals.jsonl
# R5 (owner-confirmed 2026-10-27): Ghidra's and our placeholders; readlint RL01 uses the same.
PLACEHOLDER = re.compile(r"(?:FUN|sub|DAT|LAB|PTR|UNK)_[0-9A-Fa-f]+|func_[0-9A-F]{8}|D_[0-9A-F]{8}")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")  # ASCII only (\w would take letters like é)
# Fix round 1 S2: Watcom's unprefixed keywords and modifiers (the C_KEYWORDS hold the `_`/`__`
# spellings), and the identifiers the asm/pragma ban and INCLUDE_ASM rely on.
WATCOM_BARE_KEYWORDS = frozenset({
    "asm", "based", "cdecl", "export", "far", "fastcall", "fortran", "huge", "inline",
    "interrupt", "loadds", "near", "packed", "pascal", "saveregs", "segment", "segname", "self",
    "stdcall", "syscall", "watcall",
})  # fmt: skip
RESERVED_IDENTIFIERS = frozenset({"_Pragma", "__pragma", "__emit", "INCLUDE_ASM"})
_C_RESERVED = re.compile(r"_[A-Z_]")  # C89 7.1.3: `_` + upper case or a second `_` is reserved
# The hooks' new-header shape: lower case only, so no case variant of a reserved name passes
# on a case-insensitive file system.
_HEADER_PATH = re.compile(r"include/([a-z0-9_]+)\.h")
RESERVED_HEADERS = hooks._RESERVED_HEADERS  # common.h, watcom_compat.h: one list, the hooks'
INCLUDE_DIR = REPO_ROOT / "include"
# Fix round 1: stems Windows opens as DOS devices whatever the extension (con.h is CON).
DEVICE_STEMS = frozenset({"con", "nul", "aux", "prn", *(f"{port}{n}" for port in ("com", "lpt")
                                                        for n in range(1, 10))})  # fmt: skip
_TEXT_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")  # all but tab, LF and CR
# Fix round 1 S1: the directives of a header proposal, read after configure's blanking.
_DIRECTIVE = re.compile(r"\s*(?:#|%:)\s*([A-Za-z_]+)(.*)", re.DOTALL)
_MACRO = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)(\()?(.*)", re.DOTALL)  # after define/undef
_NOT_CONSTANT = re.compile(r"[{};]")  # an object-like body is a constant expression
_DIGRAPH_HASH = "%:"
_HASH = "#"
_RENAMED_KINDS = (KIND_GAME, KIND_THUNK)  # the functions.csv kinds a func rename may name
EXES = ("ufo2p", "tacp")  # config/<exe> stems, as the driver's records name them
EVIDENCE_KINDS = ("string", "table", "call", "vocab")
EVIDENCE_TEXT_MAX = 200  # characters of evidence text after `<kind>: `
_KEYS = {
    OP_RENAME: frozenset({"op", "exe", "kind", "address", "name", "evidence"}),
    OP_HEADER: frozenset({"op", "path", "text", "evidence"}),
}
_ADDRESS = re.compile(rf"0x[0-9A-F]{{{ADDRESS_DIGITS}}}")
_EVIDENCE = re.compile(r"([a-z]+): (.*)", re.DOTALL)
_PRINTABLE = re.compile(r"[\x20-\x7e]*")  # printable ASCII: no newline or control in a record
_HEX_BASE = 16
_LINE_BREAK = "\n"


class ProposalError(ValueError):
    """A proposals.jsonl line that is not one well-formed proposal; the message names the line."""


@dataclass(frozen=True)
class Rename:
    """Give the `kind` row at `address` of `exe` the C name `name`."""

    exe: str
    kind: str
    address: int
    name: str
    evidence: str


@dataclass(frozen=True)
class Header:
    """Write `text` as the whole of the shared header `path` (`include/<name>.h`)."""

    path: str
    text: str
    evidence: str


def _refuse_constant(token: str) -> object:
    raise ValueError(f"{token} is not JSON")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"key {key!r} appears twice")
        obj[key] = value
    return obj


def _load(text: str) -> object:
    """Strict JSON: no NaN or Infinity, no repeated key (the last one would silently win)."""
    return json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_refuse_constant)


def evidence_problem(evidence: str) -> str | None:
    """Why `evidence` is not `<kind>: <text>` (kind in EVIDENCE_KINDS, text 1 to
    EVIDENCE_TEXT_MAX printable ASCII characters, not only spaces), or None."""
    found = _EVIDENCE.fullmatch(evidence)
    if found is None:
        return f"evidence {evidence!r} is not '<kind>: <text>'"
    kind, text = found.groups()
    if kind not in EVIDENCE_KINDS:
        return f"evidence kind {kind!r} is not one of {', '.join(EVIDENCE_KINDS)}"
    if not text.strip():
        return f"evidence {evidence!r} has no text"
    if len(text) > EVIDENCE_TEXT_MAX:
        return f"evidence text is {len(text)} characters, more than {EVIDENCE_TEXT_MAX}"
    if not _PRINTABLE.fullmatch(text):
        return "evidence text is not printable ASCII on one line"
    return None


def _shape_problem(obj: object) -> str | None:
    """Why the decoded line is not one proposal object of the format, or None."""
    if not isinstance(obj, dict):
        return f"a {type(obj).__name__}, not a JSON object"
    op = obj.get("op")
    if op not in OPS:
        return f"op {op!r} is not one of {', '.join(OPS)}"
    keys = set(obj)
    if keys != _KEYS[op]:
        missing, extra = sorted(_KEYS[op] - keys), sorted(keys - _KEYS[op])
        return f"a {op} proposal has exactly {sorted(_KEYS[op])} (missing {missing}, extra {extra})"
    loose = sorted(key for key, value in obj.items() if not isinstance(value, str))
    if loose:
        return f"{', '.join(loose)} must be strings"
    if op == OP_RENAME:
        return _rename_shape_problem(obj)
    return evidence_problem(obj["evidence"])


def _rename_shape_problem(obj: dict[str, str]) -> str | None:
    if obj["exe"] not in EXES:
        return f"exe {obj['exe']!r} is not one of {', '.join(EXES)}"
    if obj["kind"] not in KINDS:
        return f"kind {obj['kind']!r} is not one of {', '.join(KINDS)}"
    if not _ADDRESS.fullmatch(obj["address"]):
        return f"address {obj['address']!r} is not 0x%0{ADDRESS_DIGITS}X"
    return evidence_problem(obj["evidence"])


def parse_line(text: str, lineno: int) -> Rename | Header:
    """The proposal on line `lineno` (counted from 1) of a proposals.jsonl; ProposalError
    naming the line when `text` is not exactly one proposal of the format (also a line longer
    than PROPOSAL_LINE_MAX bytes, or nested too deep for the JSON decoder, fix round 1 I1)."""
    size = len(text.encode("utf-8", "replace"))
    if size > PROPOSAL_LINE_MAX:
        raise ProposalError(f"line {lineno}: {size} bytes, more than {PROPOSAL_LINE_MAX}")
    try:
        obj = _load(text)
    except (ValueError, RecursionError) as exc:
        raise ProposalError(f"line {lineno}: not one JSON value ({exc})") from None
    problem = _shape_problem(obj)
    if problem is not None:
        raise ProposalError(f"line {lineno}: {problem}")
    if obj["op"] == OP_RENAME:
        return Rename(obj["exe"], obj["kind"], int(obj["address"], _HEX_BASE), obj["name"],
                      obj["evidence"])  # fmt: skip
    return Header(obj["path"], obj["text"], obj["evidence"])


def _decode(data: bytes) -> str:
    """`data` as strict UTF-8; ProposalError naming the line of the first bad byte."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        lineno = data.count(_LINE_BREAK.encode(), 0, exc.start) + 1
        raise ProposalError(f"line {lineno}: not UTF-8 ({exc.reason})") from None


def read_proposals(path: Path) -> list[Rename | Header]:
    """Every proposal in the proposals.jsonl at `path`, in file order. A missing file, an empty
    one, and lines holding only whitespace are no proposals (a session that proposes nothing,
    DEC-02). ProposalError naming the first malformed line otherwise; a caller that wants every
    good line of a partly bad file calls parse_line per line. A file larger than
    PROPOSALS_FILE_MAX is refused whole (fix round 1)."""
    path = Path(path)
    if not path.exists():
        return []
    size = path.stat().st_size
    if size > PROPOSALS_FILE_MAX:
        cap = PROPOSALS_FILE_MAX // _MIB
        raise ProposalError(f"{path.name}: {size} bytes, more than {cap} MiB")
    text = _decode(path.read_bytes())
    lines = enumerate(text.split(_LINE_BREAK), start=1)  # only \n: U+2028 may sit in a string
    return [parse_line(line, lineno) for lineno, line in lines if line.strip()]


# ---- may a proposal be applied? (the driver asks under the gate lock, 07-34) ----


def _scanner() -> ModuleType:
    """configure.py, whose translation phases 1-2 and comment/literal blanking the hooks use."""
    return unitdefs.load_configure(REPO_ROOT / unitdefs.CONFIGURE)


def _code_lines(text: str) -> Iterator[tuple[int, str]]:
    """(line number from 1, logical line) of `text` read as wcc386 does: trigraphs mapped,
    continuations spliced, comments and literals blanked. Raises configure's _ConditionalError
    (a ValueError) for a lone CR."""
    cfg = _scanner()
    code = cfg._NOT_CODE.sub(cfg._blank, text)
    for first, _last, logical in cfg._logical_lines(code.split(_LINE_BREAK)):
        yield first + 1, logical


def _defined_names(text: str) -> Iterator[str]:
    """The macro names `text` #defines."""
    for _lineno, logical in _code_lines(text):
        directive = _DIRECTIVE.match(logical)
        if directive is None or directive.group(1) != "define":
            continue
        macro = _MACRO.match(directive.group(2))
        if macro is not None:
            yield macro.group(1)


def reserved_macros(include_dir: Path = INCLUDE_DIR) -> frozenset[str]:
    """INCLUDE_ASM and every macro include/common.h and include/watcom_compat.h #define (their
    guards and the Watcom keyword shims), read from the files now (fix round 1 S1, S2). A
    missing reserved header raises OSError: broken naming state, never an empty list."""
    names = {"INCLUDE_ASM"}
    for header in RESERVED_HEADERS:
        names.update(_defined_names((Path(include_dir) / header).read_text(encoding="utf-8")))
    return frozenset(names)


def name_problem(name: str, *, reserved: Collection[str] | None = None) -> str | None:
    """Why `name` cannot be a C name the driver gives a row, or None: not an ASCII C
    identifier, longer than NAME_MAX, a C89 or Watcom keyword (prefixed or bare), reserved
    (C89's `_X`/`__x`, `_Pragma`, `__pragma`, `__emit`, INCLUDE_ASM, a macro of the reserved
    headers; fix round 1 S2), or placeholder-shaped (a rename that keeps a placeholder look
    would still fail readlint RL01). `reserved` defaults to reserved_macros()."""
    if not _IDENTIFIER.fullmatch(name):
        return f"{name!r} is not a C identifier (ASCII letters, digits and _, no leading digit)"
    if len(name) > NAME_MAX:
        return f"{name} is {len(name)} characters, more than {NAME_MAX}"
    if name in unitdefs.C_KEYWORDS or name in WATCOM_BARE_KEYWORDS:
        return f"{name} is a C89 or Watcom keyword"
    if _C_RESERVED.match(name):
        return f"{name} is reserved: C89 keeps `_` + upper case and `__` names"
    macros = reserved_macros() if reserved is None else reserved
    if name in RESERVED_IDENTIFIERS or name in macros:
        return f"{name} is reserved: the asm/pragma ban or a reserved header relies on it"
    if PLACEHOLDER.fullmatch(name):
        return f"{name} is placeholder-shaped (FUN_/sub_/DAT_/LAB_/PTR_/UNK_, func_, D_)"
    return None


def linker_name(name: str, kind: str) -> str:
    """The linker name of C name `name` (unitdefs.c_name_of run backwards): `Foo` -> `Foo_`
    for a func, `g_vol` -> `_g_vol` for data."""
    if kind == FUNC_KIND:
        return name + unitdefs.FUNC_LINK_SUFFIX
    return unitdefs.DATA_LINK_PREFIX + name


def rename_problem(
    rename: Rename,
    *,
    symbols: Iterable[SymbolRow],
    functions: Sequence[FunctionRow],
    runtime_names: Iterable[str],
    src_names: Mapping[str, str],
    data_ranges: Sequence[tuple[int, int]],
    reserved: Collection[str] | None = None,
) -> str | None:
    """Why `rename` cannot be applied to its EXE's naming state, or None.

    `symbols` and `functions` are the EXE's symbols.csv and functions.csv rows, `runtime_names`
    its runtime publics and aliases (functions.csv runtime rows count too), `src_names` every
    file-scope name of the committed src/ units mapped to where it is used (a repo-relative
    path), `data_ranges` the LE data objects (required, fix round 1 I2: SymbolTable.build
    refuses a data row outside them, so no data object means no data rename), `reserved`
    name_problem's reserved macros.

    Refused: a name_problem; a func rename of an address that starts no game or thunk row; a
    data rename of an address inside a functions.csv row (code) or outside the data objects;
    the row's current C name (nothing to rename); and a name whose C or linker spelling another
    symbols.csv row, a runtime public or a src/ file-scope name already uses (T-07-56). A
    symbols.csv name without Watcom's `_` raises unitdefs.UnitDefsError: that is broken naming
    state, not a bad proposal."""
    problem = (name_problem(rename.name, reserved=reserved)
               or _target_problem(rename, functions, data_ranges))  # fmt: skip
    if problem is not None:
        return problem
    symbol_rows = list(symbols)
    current = _current_name(rename, symbol_rows)
    if rename.name == current:
        return f"{rename.name} is already the C name of {rename.kind} {_hex(rename.address)}"
    spellings = {rename.name, linker_name(rename.name, rename.kind)}
    return (_symbols_use(rename, spellings, symbol_rows)
            or _runtime_use(rename, spellings, runtime_names, functions)
            or _src_use(rename, src_names))  # fmt: skip


def _hex(address: int) -> str:
    return f"0x{address:0{ADDRESS_DIGITS}X}"


def _target_problem(
    rename: Rename, functions: Sequence[FunctionRow], data_ranges: Sequence[tuple[int, int]]
) -> str | None:
    """Why the row `rename` names is not one its kind may rename, or None."""
    where = f"{rename.kind} rename of {_hex(rename.address)}"
    if rename.kind == FUNC_KIND:
        row = next((r for r in functions if r.start == rename.address), None)
        if row is None or row.kind not in _RENAMED_KINDS:
            found = "no row" if row is None else f"the {row.kind} row {row.name}"
            return f"{where}: {found} starts there, not a game or thunk row"
        return None
    row = next((r for r in functions if r.start <= rename.address < r.end), None)
    if row is not None:
        return f"{where}: the address is code, inside the {row.kind} row {row.name}"
    if not any(start <= rename.address < end for start, end in data_ranges):
        return f"{where}: the address lies in no data object"
    return None


def _current_name(rename: Rename, symbols: Sequence[SymbolRow]) -> str:
    """The C name the row has now: its symbols.csv name's, else its placeholder."""
    for symbol in symbols:
        if symbol.address == rename.address and symbol.kind == rename.kind:
            return unitdefs.c_name_of(symbol.name, symbol.kind)
    return game_name(rename.address) if rename.kind == FUNC_KIND else data_name(rename.address)


def _symbols_use(rename: Rename, spellings: set[str], symbols: Sequence[SymbolRow]) -> str | None:
    """Another symbols.csv row whose C or linker name is one of `spellings`, named."""
    for symbol in symbols:
        if symbol.address == rename.address and symbol.kind == rename.kind:
            continue  # the row being renamed gives its name up
        if spellings & {symbol.name, unitdefs.c_name_of(symbol.name, symbol.kind)}:
            return (f"{rename.name} is already used by symbols.csv {symbol.kind} "
                    f"{_hex(symbol.address)} ({symbol.name})")  # fmt: skip
    return None


def _runtime_use(
    rename: Rename, spellings: set[str], runtime_names: Iterable[str],
    functions: Sequence[FunctionRow],
) -> str | None:  # fmt: skip
    """A runtime public whose name, or its C name read as a func or as data, is one of
    `spellings`, named (fail closed: a runtime public's own kind is not known here)."""
    publics = {*runtime_names, *(row.name for row in functions if row.kind == KIND_RUNTIME)}
    for public in sorted(publics):
        taken = {public, public.removesuffix(unitdefs.FUNC_LINK_SUFFIX),
                 public.removeprefix(unitdefs.DATA_LINK_PREFIX)}  # fmt: skip
        if spellings & taken:
            return f"{rename.name} is already used by the runtime public {public}"
    return None


def _src_use(rename: Rename, src_names: Mapping[str, str]) -> str | None:
    where = src_names.get(rename.name)
    if where is None:
        return None
    return f"{rename.name} is already a file-scope name in {where}"


def header_problem(header: Header, *, reserved: Collection[str] | None = None) -> str | None:
    """Why `header` cannot be written, or None (T-07-55).

    The path must be a bare lower-case `include/<name>.h`, not a reserved header (common.h,
    watcom_compat.h: INCLUDE_ASM and the Watcom keyword shims live there) and not a DOS device
    stem. The text must be ASCII without control characters other than tab, LF and CR, at most
    HEADER_TEXT_MAX, and declarations only (fix round 1 S1): no `%:` digraph, no `#` or `##`
    operator, no function-like macro, no #define or #undef of a keyword, a reserved identifier
    or a macro of the reserved headers (`reserved`, default reserved_macros()), and an
    object-like #define body without `{`, `}` or `;`. Then the hooks' strict scans: inline asm,
    any #pragma (M14), and an #include of anything but a bare header name (CR-02). Allowed are
    include guards, typedef/struct/union/enum declarations, prototypes and object-like
    `#define NAME <constant expression>`."""
    found = _HEADER_PATH.fullmatch(header.path)
    if found is None:
        return f"path '{header.path}' is not a bare lower-case include/<name>.h"
    stem = found.group(1)
    if f"{stem}.h" in RESERVED_HEADERS:
        return f"path '{header.path}' is reserved: the driver never writes it (D-19)"
    if stem in DEVICE_STEMS:
        return f"path '{header.path}' names a DOS device (Windows opens {stem}.h as {stem})"
    macros = reserved_macros() if reserved is None else reserved
    return _header_text_problem(header.text, macros)


def _macro_problem(directive: str, rest: str, reserved: Collection[str]) -> str | None:
    """Why one #define or #undef (`rest`: what follows the directive name) is refused."""
    macro = _MACRO.match(rest)
    if macro is None:
        return f"#{directive} names no macro"
    name, paren, body = macro.groups()
    if (name in reserved or name in RESERVED_IDENTIFIERS or name in unitdefs.C_KEYWORDS
            or name in WATCOM_BARE_KEYWORDS):  # fmt: skip
        return f"#{directive} {name}: a reserved macro, keyword or identifier"
    if directive == "undef":
        return None
    if paren:
        return f"#define {name}(...): a function-like macro"
    if _NOT_CONSTANT.search(body):
        return f"#define {name}: the body is not a constant expression ({{, }} or ;)"
    return None


def _directive_problem(text: str, reserved: Collection[str]) -> str | None:
    """The first preprocessor rule `text` breaks, or None (text the scanner cannot read is
    left to hooks.asm_problem, which reports it)."""
    cfg = _scanner()
    try:
        lines = list(_code_lines(text))
    except cfg._ConditionalError:
        return None
    for lineno, logical in lines:
        if _DIGRAPH_HASH in logical:
            return f"line {lineno}: a %: digraph (it spells # or ##)"
        directive = _DIRECTIVE.match(logical)
        if directive is None:
            continue
        name, rest = directive.groups()
        if _HASH in rest:
            return f"line {lineno}: a # or ## preprocessor operator"
        problem = _macro_problem(name, rest, reserved) if name in ("define", "undef") else None
        if problem is not None:
            return f"line {lineno}: {problem}"
    return None


def _header_text_problem(text: str, reserved: Collection[str]) -> str | None:
    if not text.isascii():
        return "header text is not ASCII"
    control = _TEXT_CONTROLS.search(text)
    if control is not None:
        return f"header text holds the control character {control.group()!r}"
    if len(text) > HEADER_TEXT_MAX:
        return f"header text is {len(text)} bytes, more than {HEADER_TEXT_MAX // _KIB} KiB"
    problem = _directive_problem(text, reserved) or hooks.asm_problem(text, any_pragma=True)
    if problem is not None:
        return f"header text: {problem}"
    include = hooks.include_problem(text)
    return f"header text: {include}" if include is not None else None
