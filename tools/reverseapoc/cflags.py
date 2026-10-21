"""config/cflags.txt: which compiler, Watcom version and flags build each source (D-12).

One rule per line, fields separated by whitespace:

    <glob>  <compiler>@<version>  <flags...>

`#` starts a comment (whole line or trailing). The first rule must be the `*` default. A source
takes the LAST rule whose glob matches its repository-relative POSIX path (fnmatchcase: `*`
crosses `/`, matching is case-sensitive). A source no rule matches is refused.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

from .targets import REPO_ROOT
from .watcom import load_watcom_manifest

DEFAULT_CFLAGS = REPO_ROOT / "config" / "cflags.txt"
COMPILERS = ("wcc386", "wpp386")


class CflagsError(ValueError):
    """config/cflags.txt has a malformed rule, or no rule matches a source."""


@dataclass(frozen=True)
class Rule:
    glob: str
    compiler: str
    version: str
    flags: tuple[str, ...]
    lineno: int

    @property
    def spec(self) -> str:
        return f"{self.compiler}@{self.version}"


def _fields(text: str):
    """(line number, fields) for every line that holds a rule once comments are stripped."""
    for lineno, line in enumerate(text.splitlines(), start=1):
        fields = line.split("#", 1)[0].split()
        if not fields:
            continue
        yield lineno, fields


def _parse_rule(lineno: int, fields: list[str]) -> Rule:
    glob, spec, *flags = fields
    compiler, _, version = spec.partition("@")
    return Rule(glob, compiler, version, tuple(flags), lineno)


def parse_cflags(text: str, *, versions: Collection[str], where: str = "cflags.txt") -> list[Rule]:
    """The rules of a cflags.txt text, in file order; errors name `where` and the line."""
    rules = []
    for lineno, fields in _fields(text):
        rule = _parse_rule(lineno, fields)
        if not rules and rule.glob != "*":
            raise CflagsError(
                f"{where}:{lineno}: the first rule must be the `*` default, not {rule.glob!r}"
            )
        rules.append(rule)
    return rules


def load_cflags(
    path: Path | str | None = None, *, versions: Collection[str] | None = None
) -> list[Rule]:
    """Parse a cflags file (default: config/cflags.txt). `versions` defaults to the versions of
    config/watcom.toml."""
    path = Path(path) if path is not None else DEFAULT_CFLAGS
    if versions is None:
        versions = tuple(load_watcom_manifest())
    return parse_cflags(path.read_text(encoding="utf-8"), versions=versions, where=str(path))


def select_rule(rules: Sequence[Rule], relpath: str) -> Rule:
    """The last rule whose glob matches `relpath` (repository-relative, POSIX)."""
    matches = [rule for rule in rules if fnmatch.fnmatchcase(relpath, rule.glob)]
    if not matches:
        raise CflagsError(f"no cflags rule matches {relpath!r}; add one to config/cflags.txt")
    return matches[-1]
