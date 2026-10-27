# SPDX-License-Identifier: GPL-3.0-or-later
"""readlint (DEC-04, D-20, D-21, D-30, backlog 999.2): the readability linter for matched units.

The tool decides readability, not the agent. `uv run reverseapoc readlint [PATHS]` reads the C
units under PATHS (default: src/) and checks only matched units: a unit with at least one
`matched` row in config/<exe>/status.csv. Every other file is reported as skipped. Exit 0 clean,
1 on violations, 2 when a file or table cannot be read (ReadlintError).

Reading. Each unit is read as strict UTF-8 (check.read_source), then through configure.py's
translation phases (normalize_source; code_text refuses anything but `#if 0` and a lone CR),
and tokenized: comments, strings, chars, directives, numbers, identifiers and punctuators, each
with its 1-based physical line. Splices are read as the compiler reads them. Tokens of a dead
`#if 0` branch are dropped. `INCLUDE_ASM(name);` stubs are exempt from every rule.

Rules:

- RL01: a placeholder identifier (proposals.PLACEHOLDER: `FUN_`, `sub_`, `DAT_`, `LAB_`,
  `PTR_`, `UNK_` + hex, `func_` + 8 upper-case hex digits, `D_` + 8 upper-case hex digits)
  outside stubs, comments and strings; directives included.
- RL02: a definition (a depth-0 `name ( ... ) {` by any identifier, through
  unitdefs.file_scope_definitions) without a header comment: the last comment between the
  previous depth-0 boundary (a `;`, a function body's `}`, a directive, the start of the file)
  and the declaration.
- RL03: a malformed header (D-21): the first line `<name>: <purpose of 3 words or more>`; one
  line `Address: <UFO2P.EXE|TACP.EXE> 0x%08X` naming the unit's EXE and the start of the row the
  name maps to (unitdefs.c_names: symbols.csv for a renamed row, else the placeholder); one or
  more `Evidence: <string|table|call|vocab>: <text>` lines (proposals.evidence_problem).
- RL04: a struct or union field named like unk/unknown/field_0x/pad/padding/gap/filler/
  undefined (plus an optional hex or `_` suffix), in bodies at any depth.
- RL05: a pointer cast over a parenthesised additive expression holding a non-zero integer
  literal, such as `*(int *)(p + 0x10)`.
- RL06: an integer literal outside #define and enum bodies other than 0 and 1 (so -1 too);
  masks (2^k, 2^k - 1, their 32-bit complement) in bitwise context; shift counts 1..31 and a
  2^k shifted; 2, 4 or 8 as an operand of binary `* / + -` (or the compound forms) or inside
  `[ ]`. A tagged waiver `/* lit: <reason> */` on the same line accepts it and is counted.
  Character literals are not integers. Floating literals are no violation; `--report` lists
  them (research R5, owner-confirmed).

Headers. The bare project headers a matched unit includes (`"name.h"` from the unit's directory
or include/ beside the src root, `<name.h>` from include/; never common.h or watcom_compat.h),
and the headers those include, are read once per run (strict UTF-8, no lone CR; include guards
allowed) and checked for RL01 and RL04, reported against include/<name>.h.

Allowlist (D-30). config/readlint-allow.csv (`exe,name,reason`) lists placeholder-named callees
a matched unit may reference (a prototype, an extern, a call, a use) before they are named: hubs
and asm rows that Tier 1 calls. It never exempts a definition: a function definition, or a
declarator of a file-scope declaration without `extern` or `typedef`. Allowlisted references
and tagged waivers are counted per file and reported. Headers get no allowlist.

Selectors. `--units EXE/UNIT,...` and `--tier N` (the units holding the tier's `member` rows of
config/mechanics-members.csv, mapped to units through functions.csv) narrow the files checked;
the others are reported as skipped. `--src` and `--config` name other roots (plan 07-31 lints a
view). `--report` exits 0 and adds per-file counts and the floating literals.
"""

from __future__ import annotations

import bisect
import csv
import itertools
import re
from collections import Counter
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from . import mechanics, unitdefs
from .check import CheckError, read_source
from .functions import FunctionsError, read_functions_csv, read_symbols_csv
from .lint import LintError, collect_sources
from .mechanics import MechanicsError
from .proposals import EVIDENCE_KINDS, EXES, PLACEHOLDER, RESERVED_HEADERS, evidence_problem
from .status import MATCHED, StatusError, read_status, status_path
from .targets import REPO_ROOT

EXIT_OK, EXIT_VIOLATIONS, EXIT_TOOL = 0, 1, 2
UNIT_SUFFIX = ".c"
FUNCTIONS_CSV, SYMBOLS_CSV = "functions.csv", "symbols.csv"  # under config/<exe>/
ALLOWLIST = "readlint-allow.csv"  # under config/ (D-30)
ALLOWLIST_COLUMNS = ("exe", "name", "reason")
INCLUDE_DIR = "include"  # beside the src root
_COMMENT_LINE = "#"
_UNIT_SELECTOR = re.compile(r"([a-z0-9]+)/([a-z0-9_]+)")
_INCLUDE = re.compile(r'(?:#|%:)[ \t]*include[ \t]*(?:"([A-Za-z0-9_]+\.h)"|<([A-Za-z0-9_]+\.h)>)')

COMMENT, STRING, CHAR, DIRECTIVE, NUMBER, IDENT, PUNCT = (
    "comment", "string", "char", "directive", "number", "ident", "punct")  # fmt: skip
_SPLICE = "\\\n"  # a backslash-newline joins two physical lines (translation phase 2)
_COMMENT_RE = r"/\*.*?(?:\*/|\Z)|//[^\n]*"
_STRING_RE = r'"(?:\\.|[^"\\\n])*"'
_CHAR_RE = r"'(?:\\.|[^'\\\n])*'"
_PUNCTUATORS = ("...", "<<=", ">>=", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&",
                "||", "*=", "/=", "%=", "+=", "-=", "&=", "^=", "|=", "##")  # fmt: skip
_TOKEN = re.compile(
    rf"(?P<{COMMENT}>{_COMMENT_RE})|(?P<{STRING}>{_STRING_RE})|(?P<{CHAR}>{_CHAR_RE})"
    rf"|(?P<{NUMBER}>\.?[0-9](?:[eEpP][+-]|[0-9A-Za-z_.])*)"
    rf"|(?P<{IDENT}>[A-Za-z_][A-Za-z0-9_]*)"
    rf"|(?P<{PUNCT}>{'|'.join(re.escape(p) for p in _PUNCTUATORS)}|[^\sA-Za-z0-9_])"
    r"|(?P<space>\s+)",
    re.DOTALL,
)
# A directive runs to the end of its logical line; a comment inside it may span lines.
_DIRECTIVE_TOKEN = re.compile(rf"(?:#|%:)(?:{_COMMENT_RE}|{_STRING_RE}|{_CHAR_RE}|[^\n])*",
                              re.DOTALL)  # fmt: skip
_DIRECTIVE_NAME = re.compile(r"(?:#|%:)[ \t]*([A-Za-z_]+)(.*)", re.DOTALL)
_COMMENTS = re.compile(_COMMENT_RE, re.DOTALL)
_STUB = ("INCLUDE_ASM", "(", None, ")", ";")  # None: the stub's identifier
_CLOSERS = {")": "(", "]": "[", "}": "{"}
_OPENERS = frozenset(_CLOSERS.values())

# RL03: the header comment (D-21)
PURPOSE_WORDS = 3
ADDRESS, EVIDENCE = "Address:", "Evidence:"
_NAME_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*): (.+)")
# RL04: Ghidra-style and padding field names, with an optional hex or `_` suffix
_UNNAMED_FIELD = re.compile(
    r"(?i)(?:unk|unknown|field|pad|padding|gap|filler|undefined)(?:_?(?:0x)?[0-9a-f]*)?(?:_\w*)?"
)
_FIELD_ENDS = (";", ",", "[", ":")
_DECLARATOR_ENDS = ("=", ",", ";", "[")
# RL06: the allowed literal contexts (D-20, research R5)
WAIVER = re.compile(r"/\*\s*lit:\s*\S.*\*/")
_U32 = 0xFFFFFFFF  # masks are 32-bit (wcc386 flat)
_SHIFT_LIMIT = 32  # a shift count of a 32-bit int is below this
_PLAIN = (0, 1)
_SIZES = (2, 4, 8)
_BITWISE = ("&", "|", "^", "~", "&=", "|=", "^=")
_BITWISE_BINARY = ("&", "|", "^")
_SHIFTS = ("<<", ">>", "<<=", ">>=")
_SHIFT_OPERATORS = ("<<", ">>")
_ARITHMETIC = ("*", "/", "+", "-")
_ARITHMETIC_ASSIGN = ("*=", "/=", "+=", "-=")


_NONE_TEXT = ""


class ReadlintError(ValueError):
    """readlint cannot read its input: a file that is not UTF-8, holds a lone CR or a
    conditional other than `#if 0`, a missing path, or a broken config table (exit 2)."""


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int  # 1-based physical line of the token's first character


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    line: int
    rule: str
    message: str


@dataclass(frozen=True, order=True)
class FloatLiteral:
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class Skipped:
    path: str
    reason: str


@dataclass(frozen=True)
class ReadlintResult:
    """What one run found. `waivers` and `allowlisted` count, per checked file, the tagged
    waivers and allowlisted references the run accepted."""

    files_checked: tuple[str, ...] = ()
    headers_checked: tuple[str, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    violations: tuple[Violation, ...] = ()
    waivers: dict[str, int] = field(default_factory=dict)
    allowlisted: dict[str, int] = field(default_factory=dict)
    floats: tuple[FloatLiteral, ...] = ()  # collected in --report mode only
    report: bool = False

    def exit_code(self) -> int:
        """0 clean (or --report), 1 on violations."""
        return EXIT_VIOLATIONS if self.violations and not self.report else EXIT_OK

    def rule_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(v.rule for v in self.violations).items()))

    def per_file(self) -> dict[str, dict[str, Any]]:
        """Violations by rule, waivers and allowlisted references of every file checked."""
        rules: dict[str, Counter[str]] = {}
        for v in self.violations:
            rules.setdefault(v.path, Counter())[v.rule] += 1
        return {path: {"violations": sum(rules.get(path, Counter()).values()),
                       "rules": dict(sorted(rules.get(path, Counter()).items())),
                       "waivers": self.waivers.get(path, 0),
                       "allowlisted": self.allowlisted.get(path, 0)}
                for path in (*self.files_checked, *self.headers_checked)}  # fmt: skip

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": not self.violations,
            "report": self.report,
            "files_checked": list(self.files_checked),
            "headers_checked": list(self.headers_checked),
            "skipped": [{"path": s.path, "reason": s.reason} for s in self.skipped],
            "violations": [{"path": v.path, "line": v.line, "rule": v.rule, "message": v.message}
                           for v in self.violations],  # fmt: skip
            "rules": self.rule_counts(),
            "waivers": dict(self.waivers),
            "allowlisted": dict(self.allowlisted),
            "floats": [{"path": f.path, "line": f.line, "text": f.text} for f in self.floats],
            "per_file": self.per_file(),
        }

    def format(self) -> str:
        lines = [f"{v.path}:{v.line}: {v.rule} {v.message}" for v in self.violations]
        lines += [f"{f.path}:{f.line}: float {f.text}" for f in self.floats]
        verdict = "report" if self.report else ("ok" if not self.violations else "FAILED")
        rules = ", ".join(f"{rule} {n}" for rule, n in self.rule_counts().items())
        if self.report:
            lines += ["per file:", *(_file_line(path, counts)
                                     for path, counts in self.per_file().items())]  # fmt: skip
        lines.append(
            f"readlint: {len(self.files_checked)} files checked, {len(self.headers_checked)} "
            f"headers, {len(self.skipped)} skipped, "
            f"{len(self.violations)} violations{f' ({rules})' if rules else ''}, "
            f"{sum(self.waivers.values())} waivers, {sum(self.allowlisted.values())} "
            f"allowlisted, {verdict}"
        )
        return "\n".join(lines)


_NONE = Token(PUNCT, _NONE_TEXT, 0)  # what _Source.tok gives past either end


def _file_line(path: str, counts: Mapping[str, Any]) -> str:
    rules = ", ".join(f"{rule} {n}" for rule, n in counts["rules"].items())
    return (f"  {path}: {counts['violations']} violations{f' ({rules})' if rules else ''}, "
            f"{counts['waivers']} waivers, {counts['allowlisted']} allowlisted")  # fmt: skip


# ---- reading and tokenizing ----


def _configure() -> ModuleType:
    """configure.py, whose translation phases readlint reads files through."""
    return unitdefs.load_configure(REPO_ROOT / unitdefs.CONFIGURE)


class _Lines:
    """Physical line numbers of offsets into the spliced text (splices removed)."""

    def __init__(self, parts: Sequence[str], spliced: str) -> None:
        self.splices = list(itertools.accumulate((len(p) for p in parts[:-1]), initial=0))
        self.newlines = [match.start() for match in re.finditer("\n", spliced)]

    def at(self, offset: int) -> int:
        spliced_before = bisect.bisect_right(self.splices, offset) - 1
        return 1 + bisect.bisect_left(self.newlines, offset) + spliced_before


def _at_line_start(text: str, pos: int) -> bool:
    return not text[text.rfind("\n", 0, pos) + 1 : pos].strip(" \t")


def tokenize(text: str) -> list[Token]:
    """The tokens of `text` (normalize_source's output) with 1-based physical lines; white space
    is dropped, comments and directives are kept. A directive is a `#` (or `%:`) first on its
    logical line and runs to the line's end."""
    parts = text.split(_SPLICE)
    spliced = "".join(parts)
    lines = _Lines(parts, spliced)
    tokens = []
    pos = 0
    while pos < len(spliced):
        directive = None
        if spliced[pos] in "#%" and _at_line_start(spliced, pos):
            directive = _DIRECTIVE_TOKEN.match(spliced, pos)
        if directive is not None and directive.group():
            tokens.append(Token(DIRECTIVE, directive.group(), lines.at(pos)))
            pos = directive.end()
            continue
        match = _TOKEN.match(spliced, pos)
        if match.lastgroup != "space":
            tokens.append(Token(match.lastgroup, match.group(), lines.at(pos)))
        pos = match.end()
    return tokens


def _directive(text: str) -> tuple[str, str] | None:
    """(name, rest) of a directive token, its comments blanked; None for a null directive."""
    found = _DIRECTIVE_NAME.match(_COMMENTS.sub(" ", text))
    return None if found is None else (found.group(1), found.group(2).strip())


def _live(tokens: Sequence[Token], cfg: ModuleType) -> list[Token]:
    """`tokens` without the dead branches of `#if 0`, read with configure's _directive_step so
    readlint and the D-12 check agree on what is dead."""
    dead = live_else = 0
    live = []
    for token in tokens:
        parsed = _directive(token.text) if token.kind == DIRECTIVE else None
        if parsed is not None:
            before = dead
            try:
                dead, live_else = cfg._directive_step(token.line, *parsed, dead, live_else)
            except cfg._ConditionalError as exc:
                raise ReadlintError(str(exc)) from None
            if not before or not dead:
                live.append(token)
        elif not dead:
            live.append(token)
    return live


def _directive_tokens(token: Token) -> list[Token]:
    """The tokens inside a directive (after its `#`), on their physical lines."""
    return [Token(t.kind, t.text, token.line + t.line - 1) for t in tokenize(token.text[1:])]


# ---- one source file ----


@dataclass
class _Source:
    """One file's live tokens, with the code tokens (no comments or directives) indexed by
    position: brace depth, matching brackets, the innermost open bracket, and stub tokens."""

    path: str  # as reported
    exe: str
    tokens: list[Token]
    definitions: list[str]  # unitdefs.file_scope_definitions, in file order
    code: list[int] = field(init=False)  # indices into tokens
    depth: list[int] = field(init=False)  # brace depth (a `}` gets the depth it closes to)
    inner: list[str | None] = field(init=False)  # innermost open bracket around each token
    parent: list[int] = field(init=False)  # its position (-1 at file level)
    position: dict[int, int] = field(init=False)  # token index -> code position
    match: dict[int, int] = field(init=False)  # open bracket position <-> close position
    stubs: set[int] = field(init=False)  # code positions of INCLUDE_ASM stub tokens

    def __post_init__(self) -> None:
        self.code = [i for i, t in enumerate(self.tokens) if t.kind not in (COMMENT, DIRECTIVE)]
        self.position = {i: p for p, i in enumerate(self.code)}
        self.depth, self.inner, self.parent, self.match = [], [], [], {}
        depth = 0
        stack: list[tuple[int, str]] = []
        for position, i in enumerate(self.code):
            text = self.tokens[i].text
            if text in _CLOSERS and stack and stack[-1][1] == _CLOSERS[text]:
                opened = stack.pop()[0]
                self.match[opened], self.match[position] = position, opened
            depth -= text == "}"
            depth = max(depth, 0)
            self.depth.append(depth)
            self.inner.append(stack[-1][1] if stack else None)
            self.parent.append(stack[-1][0] if stack else -1)
            depth += text == "{"
            if text in _OPENERS:
                stack.append((position, text))
        self.stubs = set(self._stub_positions())

    def tok(self, position: int) -> Token:
        """The code token at `position` (an index into self.code); an empty punctuator past
        either end."""
        if 0 <= position < len(self.code):
            return self.tokens[self.code[position]]
        return _NONE

    def checked(self) -> Iterator[int]:
        """Code positions outside INCLUDE_ASM stubs."""
        return (p for p in range(len(self.code)) if p not in self.stubs)

    def _stub_positions(self) -> Iterator[int]:
        size = len(_STUB)
        for start in range(len(self.code) - size + 1):
            window = [self.tok(start + k) for k in range(size)]
            if all(want is None and t.kind == IDENT or t.text == want
                   for want, t in zip(_STUB, window, strict=True)):  # fmt: skip
                yield from range(start, start + size)

    def body(self, keyword: str) -> Iterator[tuple[int, int]]:
        """(open, close) positions of every `struct`/`union`/`enum` body, at any depth."""
        for p in self.checked():
            if self.tok(p).text != keyword:
                continue
            opened = p + 1 if self.tok(p + 1).text == "{" else p + 2
            if self.tok(opened).text == "{" and opened in self.match:
                yield opened, self.match[opened]

    def definition_positions(self) -> list[int]:
        """The code position of each definition's name, paired in order with
        unitdefs.file_scope_definitions: a depth-0 `name ( ... ) {`."""
        found, start = [], 0
        for name in self.definitions:
            position = next((p for p in range(start, len(self.code)) if self._defines(p, name)),
                            None)  # fmt: skip
            if position is None:
                raise ReadlintError(f"{self.path}: cannot place the definition of {name}")
            found.append(position)
            start = position + 1
        return found

    def _defines(self, p: int, name: str) -> bool:
        close = self.match.get(p + 1)
        return (self.depth[p] == 0 and self.tok(p).text == name and self.tok(p + 1).text == "("
                and close is not None and self.tok(close + 1).text == "{")  # fmt: skip

    def defined_positions(self) -> set[int]:
        """Code positions of every name the file defines: function definitions and the
        declarators of file-scope declarations without `extern` or `typedef`."""
        found = set(self.definition_positions())
        start = 0
        for p in range(len(self.code)):
            if not self._boundary(p):
                continue
            if self.tok(p).text == ";":
                found.update(self._declarators(start, p))
            start = p + 1
        return found

    def _declarators(self, start: int, end: int) -> Iterator[int]:
        """The declarator names of the file-scope declaration at code positions start..end."""
        level = [p for p in range(start, end) if self.inner[p] is None]
        if any(self.tok(p).text in ("extern", "typedef") for p in level):
            return
        initializer = False
        for p in level:
            token = self.tok(p)
            if token.text in ("=", ","):
                initializer = token.text == "="
            elif (not initializer and token.kind == IDENT and token.text not in unitdefs.C_KEYWORDS
                  and self.tok(p + 1).text in _DECLARATOR_ENDS):  # fmt: skip
                yield p

    def header_comment(self, position: int) -> Token | None:
        """The last comment between the previous depth-0 boundary (a `;`, a function body's
        `}`, a directive or the start of the file) and the declaration holding `position`."""
        first = index = self.code[position]
        while index > 0:
            index -= 1
            token = self.tokens[index]
            if token.kind == DIRECTIVE or index in self.position and self._boundary(
                    self.position[index]):  # fmt: skip
                break
            if token.kind != COMMENT:
                first = index
        before = self.tokens[first - 1] if first > 0 else None
        return before if before is not None and before.kind == COMMENT else None

    def _boundary(self, p: int) -> bool:
        if self.depth[p] or self.tok(p).text not in (";", "}"):
            return False
        return self.tok(p).text == ";" or self.tok(self.match.get(p, 0) - 1).text == ")"


def _read(path: Path, shown: str, exe: str, cfg: ModuleType, *, unit: bool = True) -> _Source:
    """A unit file read as configure reads it, or (unit=False) a header: the same strict UTF-8
    and translation phases, but conditionals (include guards) are not evaluated and no
    definitions are placed. ReadlintError for anything refused."""
    try:
        text = read_source(path)
    except CheckError as exc:
        raise ReadlintError(str(exc)) from None
    try:
        normalized = cfg.normalize_source(text)
        code = cfg.code_text(text) if unit else ""
    except cfg._ConditionalError as exc:
        raise ReadlintError(f"{shown}: {exc}") from None
    tokens = tokenize(normalized)
    if not unit:
        return _Source(shown, exe, tokens, [])
    return _Source(shown, exe, _live(tokens, cfg), unitdefs.file_scope_definitions(code))


def _includes(src: _Source, here: Path, include_dir: Path) -> Iterator[Path]:
    """The project headers `src` includes that exist: `"name.h"` from `here` then include/,
    `<name.h>` from include/; the reserved headers left out."""
    for token in src.tokens:
        found = _INCLUDE.match(_COMMENTS.sub(" ", token.text)) if token.kind == DIRECTIVE else None
        if found is None:
            continue
        name = found.group(1) or found.group(2)
        places = [here / name, include_dir / name] if found.group(1) else [include_dir / name]
        path = next((p for p in places if p.is_file()), None)
        if name not in RESERVED_HEADERS and path is not None:
            yield path


def read_allowlist(path: Path) -> dict[tuple[str, str], str]:
    """(exe, name) -> reason of config/readlint-allow.csv (D-30): `#` comment lines, the header
    `exe,name,reason`, then one row per placeholder-named callee matched units may reference
    before it is named. A missing file allows nothing; a malformed one raises ReadlintError."""
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReadlintError(f"{path}: not UTF-8 ({exc})") from None
    lines = [line for line in text.splitlines() if line.strip() and not
             line.startswith(_COMMENT_LINE)]  # fmt: skip
    rows = list(csv.reader(lines))
    if not rows or tuple(rows[0]) != ALLOWLIST_COLUMNS:
        raise ReadlintError(f"{path}: the header is not {','.join(ALLOWLIST_COLUMNS)}")
    allowed: dict[tuple[str, str], str] = {}
    for number, cells in enumerate(rows[1:], start=1):
        problem = _allow_problem(cells, allowed)
        if problem is not None:
            raise ReadlintError(f"{path}: data row {number}: {problem}")
        allowed[(cells[0], cells[1])] = cells[2].strip()
    return allowed


def _allow_problem(cells: Sequence[str], allowed: Mapping[tuple[str, str], str]) -> str | None:
    if len(cells) != len(ALLOWLIST_COLUMNS):
        return f"{len(cells)} cells, not {len(ALLOWLIST_COLUMNS)}"
    exe, name, reason = cells
    if exe not in EXES:
        return f"exe {exe!r} is not one of {', '.join(EXES)}"
    if not PLACEHOLDER.fullmatch(name):
        return f"{name!r} is not a placeholder name (a named callee needs no allowlist)"
    if not reason.strip():
        return f"{exe},{name} has no reason"
    if (exe, name) in allowed:
        return f"{exe},{name} is listed twice"
    return None


# ---- literals ----


def _is_float(text: str) -> bool:
    lower = text.lower()
    if lower.startswith("0x"):
        return "p" in lower
    return "." in lower or "e" in lower


def _int_value(text: str) -> int | None:
    """The value of an integer literal (suffixes dropped), None when it is malformed."""
    body = text.rstrip("uUlL")
    try:
        if body[:2].lower() == "0x":
            return int(body[2:], 16)
        return int(body, 8) if len(body) > 1 and body[0] == "0" else int(body, 10)
    except ValueError:
        return None


def _is_pow2(value: int) -> bool:
    return value > 0 and not value & (value - 1)


def _is_mask(value: int) -> bool:
    """2^k, 2^k - 1 or the 32-bit complement of 2^k - 1."""
    if not 0 <= value <= _U32:
        return False
    return _is_pow2(value) or _is_pow2(value + 1) or _is_pow2((~value & _U32) + 1)


def _ends_operand(token: Token) -> bool:
    """True when `token` can end an operand, so an operator after it is binary."""
    if token.kind == IDENT:
        return token.text not in unitdefs.C_KEYWORDS
    return token.kind in (NUMBER, STRING, CHAR) or token.text in (")", "]", "++", "--")


def _literal_allowed(src: _Source, p: int, value: int | None) -> bool:
    """RL06's allowed contexts for the integer literal at code position `p` (D-20, R5)."""
    if value is None:
        return False
    if value in _PLAIN:
        return True
    before, after = src.tok(p - 1).text, src.tok(p + 1).text
    if (before in _BITWISE or after in _BITWISE_BINARY) and _is_mask(value):
        return True
    if before in _SHIFTS and 0 < value < _SHIFT_LIMIT:
        return True
    if after in _SHIFT_OPERATORS and _is_pow2(value):
        return True
    if value not in _SIZES:
        return False
    binary_before = before in _ARITHMETIC and _ends_operand(src.tok(p - 2))
    return binary_before or before in _ARITHMETIC_ASSIGN or after in _ARITHMETIC or (
        src.inner[p] == "[")  # fmt: skip


# ---- the rules ----


def _identifiers(src: _Source) -> Iterator[tuple[Token, int | None]]:
    """Identifier tokens outside stubs with their code positions; those inside directives
    have none (a directive defines no object)."""
    for p in src.checked():
        if src.tok(p).kind == IDENT:
            yield src.tok(p), p
    for token in (t for t in src.tokens if t.kind == DIRECTIVE):
        yield from ((t, None) for t in _directive_tokens(token) if t.kind == IDENT)


def _rl01(src: _Source, allowed: Collection[str] = ()) -> tuple[list[Violation], int]:
    """Placeholder identifiers in code and directives, stubs excepted; a reference to an
    `allowed` name is counted instead, a definition of one never is (D-30)."""
    defined = src.defined_positions() if allowed else set()
    found, accepted = [], 0
    for token, position in _identifiers(src):
        if not PLACEHOLDER.fullmatch(token.text):
            continue
        if token.text in allowed and position not in defined:
            accepted += 1
            continue
        why = f"{token.text} is a placeholder name: name it (a D-19 rename)"
        found.append(Violation(src.path, token.line, "RL01", why))
    return found, accepted


def _comment_lines(text: str) -> list[str]:
    """The non-blank lines of a comment, its delimiters and leading `*` gutters removed."""
    body = text[2:].removesuffix("*/") if text.startswith("/*") else text[2:]
    lines = (line.strip() for line in body.split("\n"))
    return [stripped for line in lines if (stripped := line.removeprefix("*").strip())]


def _header_problems(lines: Sequence[str], name: str, exe: str,
                     names: Mapping[str, int]) -> Iterator[str]:  # fmt: skip
    """RL03 (D-21): `<name>: <purpose>`, one `Address: <EXE> 0x%08X` naming the row `name`
    maps to, and one or more `Evidence: <kind>: <text>` lines."""
    first = _NAME_LINE.fullmatch(lines[0]) if lines else None
    if first is None or first.group(1) != name:
        yield f"the first line is not '{name}: <purpose>'"
    elif len(first.group(2).split()) < PURPOSE_WORDS:
        yield f"the purpose '{first.group(2)}' has fewer than {PURPOSE_WORDS} words"
    exe_file = f"{exe.upper()}.EXE"
    addresses = [line.removeprefix(ADDRESS).strip() for line in lines if line.startswith(ADDRESS)]
    start = names.get(name)
    if start is None:
        yield f"{name} names no game or thunk row of {exe_file}"
    elif not addresses:
        yield f"no '{ADDRESS} {exe_file} 0x{start:08X}' line"
    elif len(addresses) > 1:
        yield f"{len(addresses)} '{ADDRESS}' lines, not one"
    elif addresses[0] != f"{exe_file} 0x{start:08X}":
        yield f"'{ADDRESS} {addresses[0]}' is not '{ADDRESS} {exe_file} 0x{start:08X}'"
    evidence = [line.removeprefix(EVIDENCE).strip() for line in lines if line.startswith(EVIDENCE)]
    if not evidence:
        yield f"no '{EVIDENCE} <{'|'.join(EVIDENCE_KINDS)}>: <text>' line"
    yield from filter(None, map(evidence_problem, evidence))


def _rl02_rl03(src: _Source, names: Mapping[str, int]) -> Iterator[Violation]:
    """Each definition has a header comment (RL02) in the D-21 form (RL03)."""
    for position in src.definition_positions():
        token = src.tok(position)
        header = src.header_comment(position)
        if header is None:
            why = f"{token.text} has no header comment (purpose, Address and Evidence, D-20)"
            yield Violation(src.path, token.line, "RL02", why)
            continue
        for problem in _header_problems(_comment_lines(header.text), token.text, src.exe, names):
            yield Violation(src.path, header.line, "RL03", f"{token.text}: {problem}")


def _rl04(src: _Source) -> Iterator[Violation]:
    """Unnamed struct or union fields, in bodies at any depth."""
    for keyword in ("struct", "union"):
        for opened, closed in src.body(keyword):
            for p in range(opened + 1, closed):
                token = src.tok(p)
                own_level = src.depth[p] == src.depth[opened] + 1 and src.inner[p] == "{"
                if not own_level or token.kind != IDENT or src.tok(p + 1).text not in _FIELD_ENDS:
                    continue
                if _UNNAMED_FIELD.fullmatch(token.text):
                    why = f"{token.text} is an unnamed {keyword} field: name it"
                    yield Violation(src.path, token.line, "RL04", why)


def _pointer_cast(src: _Source, opened: int) -> bool:
    """True when the parentheses at `opened` hold a cast to a pointer type: type words, then
    one or more `*`."""
    texts = [src.tok(p) for p in range(opened + 1, src.match.get(opened, opened))]
    stars = len(texts) - len(list(itertools.dropwhile(lambda t: t.text == "*", reversed(texts))))
    words = texts[: len(texts) - stars]
    return bool(stars and words) and all(t.kind == IDENT for t in words)


def _literal_offset(src: _Source, opened: int) -> bool:
    """True when the parenthesised operand at `opened` adds or subtracts at its own level and
    holds a non-zero integer literal."""
    inside = range(opened + 1, src.match[opened])
    level = [p for p in inside if src.parent[p] == opened]
    additive = any(src.tok(p).text in ("+", "-") for p in level)
    literal = any(src.tok(p).kind == NUMBER and not _is_float(src.tok(p).text)
                  and _int_value(src.tok(p).text) != 0 for p in inside)  # fmt: skip
    return additive and literal


def _rl05(src: _Source) -> Iterator[Violation]:
    """A pointer cast over a parenthesised additive expression with a literal offset."""
    for p in src.checked():
        if src.tok(p).text != "(" or p not in src.match or not _pointer_cast(src, p):
            continue
        operand = src.match[p] + 1
        if src.tok(operand).text == "(" and operand in src.match and _literal_offset(src, operand):
            why = "raw offset access: a pointer cast over an offset expression; use a named field"
            yield Violation(src.path, src.tok(p).line, "RL05", why)


@dataclass
class _Literals:
    """RL06's findings in one file: violations, the waiver comments used, the floats."""

    violations: list[Violation] = field(default_factory=list)
    waivers: set[int] = field(default_factory=set)  # token indices of waiver comments used
    floats: list[FloatLiteral] = field(default_factory=list)


def _rl06(src: _Source) -> _Literals:
    """Magic integer literals outside #define and enum bodies, unless a tagged waiver
    `/* lit: <reason> */` sits on the same line; floating literals are collected apart."""
    found = _Literals()
    enums = {p for opened, closed in src.body("enum") for p in range(opened, closed)}
    waivers: dict[int, int] = {}
    for index, token in enumerate(src.tokens):
        if token.kind == COMMENT and WAIVER.fullmatch(token.text):
            waivers.setdefault(token.line, index)
    for p in src.checked():
        token = src.tok(p)
        if token.kind != NUMBER or p in enums:
            continue
        if _is_float(token.text):
            found.floats.append(FloatLiteral(src.path, token.line, token.text))
        elif not _literal_allowed(src, p, _int_value(token.text)):
            if token.line in waivers:
                found.waivers.add(waivers[token.line])
                continue
            why = (f"magic literal {token.text}: name it with #define or enum, or waive it on "
                   "the line with /* lit: <reason> */")  # fmt: skip
            found.violations.append(Violation(src.path, token.line, "RL06", why))
    return found


# ---- selection and the run ----


def _shown(path: Path, src_root: Path) -> str:
    """`path` as reported: relative to the directory holding the src root when inside it."""
    try:
        return path.resolve().relative_to(src_root.resolve().parent).as_posix()
    except ValueError:
        return path.as_posix()


def _unit_of(path: Path, src_root: Path) -> tuple[str, str] | None:
    """(exe, unit) of src/<exe>/<unit>.c, else None."""
    try:
        parts = path.resolve().relative_to(src_root.resolve()).parts
    except ValueError:
        return None
    if len(parts) != 2 or parts[0] not in EXES or not parts[1].endswith(UNIT_SUFFIX):
        return None
    return parts[0], parts[1].removesuffix(UNIT_SUFFIX)


def _matched_units(config_root: Path, exe: str) -> frozenset[str]:
    rows = read_status(status_path(config_root, exe))
    return frozenset(row.unit for row in rows if row.status == MATCHED)


def _parse_units(units: Sequence[str]) -> frozenset[tuple[str, str]]:
    found = set()
    for cell in units:
        match = _UNIT_SELECTOR.fullmatch(cell)
        if match is None or match.group(1) not in EXES:
            raise ReadlintError(f"--units {cell!r} is not <{'|'.join(EXES)}>/<unit>")
        found.add((match.group(1), match.group(2)))
    return frozenset(found)


def _tier_units(config_root: Path, tier: int) -> frozenset[tuple[str, str]]:
    """(exe, unit) of every `member` row of a tier-N item (mechanics-members.csv), mapped to
    its unit through functions.csv."""
    mech, members = mechanics.read_committed(config_root)
    if mech.tier(tier) is None:
        raise ReadlintError(f"--tier {tier}: no [[tier]] with that id in mechanics.toml")
    items = {item.id for item in mech.items if item.tier == tier}
    member = mechanics.ROLE_MEMBER
    starts = {(row.exe, row.address) for row in members
              if row.role == member and items.intersection(row.member_items)}  # fmt: skip
    units = set()
    for exe in sorted({exe for exe, _start in starts}):
        rows = read_functions_csv(config_root / exe / FUNCTIONS_CSV)
        units.update((exe, row.unit) for row in rows if (exe, row.start) in starts and row.unit)
    return frozenset(units)


def _selected(config_root: Path, units: Sequence[str] | None,
              tier: int | None) -> frozenset[tuple[str, str]] | None:  # fmt: skip
    """The units --units and --tier select (both: the units both select); None: every unit."""
    chosen = [_parse_units(units)] if units else []
    if tier is not None:
        chosen.append(_tier_units(config_root, tier))
    return frozenset.intersection(*chosen) if chosen else None


@dataclass
class _Run:
    """One run's roots, tables (read once per EXE) and findings."""

    src_root: Path
    config_root: Path
    report: bool
    cfg: ModuleType
    allow: dict[tuple[str, str], str]
    names: dict[str, dict[str, int]] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)
    waivers: dict[str, int] = field(default_factory=dict)
    allowlisted: dict[str, int] = field(default_factory=dict)
    floats: list[FloatLiteral] = field(default_factory=list)
    headers: dict[Path, str] = field(default_factory=dict)  # resolved path -> as reported

    def c_names(self, exe: str) -> dict[str, int]:
        """C name -> row start of every game and thunk row of `exe` (unitdefs.c_names)."""
        if exe not in self.names:
            tables = self.config_root / exe
            self.names[exe] = unitdefs.c_names(read_functions_csv(tables / FUNCTIONS_CSV),
                                               read_symbols_csv(tables / SYMBOLS_CSV))  # fmt: skip
        return self.names[exe]

    def lint(self, path: Path, shown: str, exe: str) -> None:
        src = _read(path, shown, exe, self.cfg)
        allowed = {name for allow_exe, name in self.allow if allow_exe == exe}
        found, accepted = _rl01(src, allowed)
        self.violations += found
        if accepted:
            self.allowlisted[src.path] = accepted
        if src.definitions:
            self.violations += _rl02_rl03(src, self.c_names(src.exe))
        self.violations += _rl04(src)
        self.violations += _rl05(src)
        literals = _rl06(src)
        self.violations += literals.violations
        if literals.waivers:
            self.waivers[src.path] = len(literals.waivers)
        if self.report:
            self.floats += literals.floats
        self.lint_headers(src, path.parent)

    def lint_headers(self, src: _Source, here: Path) -> None:
        """RL01 (no allowlist) and RL04 over the project headers `src` includes, each once."""
        include_dir = self.src_root.parent / INCLUDE_DIR
        pending = list(_includes(src, here, include_dir))
        while pending:
            path = pending.pop(0)
            if path.resolve() in self.headers:
                continue
            shown = self.headers[path.resolve()] = _shown(path, self.src_root)
            header = _read(path, shown, src.exe, self.cfg, unit=False)
            self.violations += _rl01(header)[0]
            self.violations += _rl04(header)
            pending += _includes(header, path.parent, include_dir)


def _run(paths: Sequence[Path | str], src_root: Path, config_root: Path, units, tier,
         report: bool) -> ReadlintResult:  # fmt: skip
    wanted = _selected(config_root, units, tier)
    files = [(path, _shown(path, src_root), _unit_of(path, src_root))
             for path in collect_sources(paths or [src_root])]  # fmt: skip
    missing = sorted(_parse_units(units or ()) - {found for *_rest, found in files})
    if missing:
        raise ReadlintError(f"--units {', '.join(f'{e}/{u}' for e, u in missing)}: no such unit "
                            "file under PATHS")  # fmt: skip
    matched = {exe: _matched_units(config_root, exe) for exe in EXES}
    run = _Run(src_root, config_root, report, _configure(),
               read_allowlist(config_root / ALLOWLIST))  # fmt: skip
    checked, skipped = [], []
    for path, shown, found in files:
        if found is None:
            skipped.append(Skipped(shown, "not src/<exe>/<unit>.c"))
        elif wanted is not None and found not in wanted:
            skipped.append(Skipped(shown, "not selected by --units/--tier"))
        elif found[1] not in matched[found[0]]:
            skipped.append(Skipped(shown, "no matched row in status.csv"))
        else:
            checked.append(shown)
            run.lint(path, shown, found[0])
    violations, floats = tuple(sorted(run.violations)), tuple(sorted(run.floats))
    return ReadlintResult(tuple(checked), tuple(sorted(run.headers.values())), tuple(skipped),
                          violations, run.waivers, run.allowlisted, floats, report)  # fmt: skip


def run_readlint(
    paths: Sequence[Path | str],
    *,
    src_root: Path,
    config_root: Path,
    units: Sequence[str] | None = None,
    tier: int | None = None,
    report: bool = False,
) -> ReadlintResult:
    """Lint the matched units under `paths` (default: `src_root`), reading status.csv and the
    other tables under `config_root`. ReadlintError (exit 2) for anything unreadable."""
    try:
        return _run(paths, Path(src_root), Path(config_root), units, tier, report)
    except (CheckError, FunctionsError, LintError, MechanicsError, StatusError,
            unitdefs.UnitDefsError, OSError) as exc:  # fmt: skip
        raise ReadlintError(str(exc)) from exc
