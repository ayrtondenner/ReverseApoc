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
"""

from __future__ import annotations

import bisect
import itertools
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from . import unitdefs
from .check import CheckError, read_source
from .functions import FunctionsError
from .lint import LintError, collect_sources
from .proposals import EXES, PLACEHOLDER
from .status import MATCHED, StatusError, read_status, status_path
from .targets import REPO_ROOT

EXIT_OK, EXIT_VIOLATIONS, EXIT_TOOL = 0, 1, 2
UNIT_SUFFIX = ".c"

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


@dataclass(frozen=True)
class Skipped:
    path: str
    reason: str


@dataclass(frozen=True)
class ReadlintResult:
    """What one run found. `waivers` and `allowlisted` count, per checked file, the tagged
    waivers and allowlisted references the run accepted."""

    files_checked: tuple[str, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    violations: tuple[Violation, ...] = ()
    waivers: dict[str, int] = field(default_factory=dict)
    allowlisted: dict[str, int] = field(default_factory=dict)
    report: bool = False

    def exit_code(self) -> int:
        """0 clean (or --report), 1 on violations."""
        return EXIT_VIOLATIONS if self.violations and not self.report else EXIT_OK

    def rule_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(v.rule for v in self.violations).items()))

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": not self.violations,
            "report": self.report,
            "files_checked": list(self.files_checked),
            "skipped": [{"path": s.path, "reason": s.reason} for s in self.skipped],
            "violations": [{"path": v.path, "line": v.line, "rule": v.rule, "message": v.message}
                           for v in self.violations],  # fmt: skip
            "rules": self.rule_counts(),
            "waivers": dict(self.waivers),
            "allowlisted": dict(self.allowlisted),
        }

    def format(self) -> str:
        lines = [f"{v.path}:{v.line}: {v.rule} {v.message}" for v in self.violations]
        verdict = "report" if self.report else ("ok" if not self.violations else "FAILED")
        rules = ", ".join(f"{rule} {n}" for rule, n in self.rule_counts().items())
        lines.append(
            f"readlint: {len(self.files_checked)} files checked, {len(self.skipped)} skipped, "
            f"{len(self.violations)} violations{f' ({rules})' if rules else ''}, "
            f"{sum(self.waivers.values())} waivers, {sum(self.allowlisted.values())} "
            f"allowlisted, {verdict}"
        )
        return "\n".join(lines)


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
    """One file's live tokens, with the code tokens (no comments or directives) indexed."""

    path: str  # as reported
    exe: str
    tokens: list[Token]
    definitions: list[str]  # unitdefs.file_scope_definitions, in file order
    code: list[int] = field(init=False)  # indices into tokens
    depth: list[int] = field(init=False)  # brace depth before each code token
    stubs: set[int] = field(init=False)  # code positions of INCLUDE_ASM stub tokens

    def __post_init__(self) -> None:
        self.code = [i for i, t in enumerate(self.tokens) if t.kind not in (COMMENT, DIRECTIVE)]
        depth = 0
        self.depth = []
        for i in self.code:
            text = self.tokens[i].text
            depth -= text == "}"
            self.depth.append(max(depth, 0) if text == "}" else depth)
            depth += text == "{"
        self.stubs = set(self._stub_positions())

    def tok(self, position: int) -> Token:
        """The code token at `position` (an index into self.code)."""
        return self.tokens[self.code[position]]

    def _stub_positions(self) -> Iterator[int]:
        size = len(_STUB)
        for start in range(len(self.code) - size + 1):
            window = [self.tok(start + k) for k in range(size)]
            if all(want is None and t.kind == IDENT or t.text == want
                   for want, t in zip(_STUB, window, strict=True)):  # fmt: skip
                yield from range(start, start + size)


def _read(path: Path, shown: str, exe: str, cfg: ModuleType) -> _Source:
    """A unit file read as configure reads it; ReadlintError for anything it refuses."""
    try:
        text = read_source(path)
    except CheckError as exc:
        raise ReadlintError(str(exc)) from None
    try:
        normalized = cfg.normalize_source(text)
        code = cfg.code_text(text)
    except cfg._ConditionalError as exc:
        raise ReadlintError(f"{shown}: {exc}") from None
    tokens = _live(tokenize(normalized), cfg)
    return _Source(shown, exe, tokens, unitdefs.file_scope_definitions(code))


# ---- the rules ----


def _rl01(src: _Source) -> Iterator[Violation]:
    """Placeholder identifiers in code and directives, stubs excepted."""
    candidates = [src.tok(p) for p in range(len(src.code)) if p not in src.stubs]
    for token in (t for t in src.tokens if t.kind == DIRECTIVE):
        candidates += _directive_tokens(token)
    for token in candidates:
        if token.kind == IDENT and PLACEHOLDER.fullmatch(token.text):
            why = f"{token.text} is a placeholder name: name it (a D-19 rename)"
            yield Violation(src.path, token.line, "RL01", why)


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


def _run(paths: Sequence[Path | str], src_root: Path, config_root: Path, units, tier,
         report: bool) -> ReadlintResult:  # fmt: skip
    if units or tier is not None:
        raise ReadlintError("--units and --tier are not supported yet")
    cfg = _configure()
    matched = {exe: _matched_units(config_root, exe) for exe in EXES}
    checked, skipped, violations = [], [], []
    for path in collect_sources(paths or [src_root]):
        shown = _shown(path, src_root)
        found = _unit_of(path, src_root)
        if found is None:
            skipped.append(Skipped(shown, "not src/<exe>/<unit>.c"))
            continue
        exe, unit = found
        if unit not in matched[exe]:
            skipped.append(Skipped(shown, "no matched row in status.csv"))
            continue
        checked.append(shown)
        violations += _rl01(_read(path, shown, exe, cfg))
    return ReadlintResult(tuple(checked), tuple(skipped), tuple(sorted(violations)), report=report)


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
    except (CheckError, FunctionsError, LintError, StatusError, unitdefs.UnitDefsError,
            OSError) as exc:  # fmt: skip
        raise ReadlintError(str(exc)) from exc
