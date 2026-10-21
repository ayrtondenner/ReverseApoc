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
# Options the wrapper always sets or must control (quiet, no file-dependency info, DOS target,
# object, error file, forced include, precompiled header, auto-dependency file, include path);
# a per-file rule may not set them. "-i" must stay last: _wrapper_owned matches it specially.
WRAPPER_OWNED = ("-zq", "-zld", "-bt", "-fo", "-fr", "-fi", "-fh", "-ad", "-i")


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


def _wrapper_owned(flag: str) -> str | None:
    """The WRAPPER_OWNED option `flag` sets, if any. Each is matched as a prefix, except "-i",
    which only counts as the whole flag or followed by "=": a future "-ix"-style flag is a
    different option and must not be caught by accident."""
    if flag == "-i" or flag.startswith("-i="):
        return "-i"
    return next((owned for owned in WRAPPER_OWNED[:-1] if flag.startswith(owned)), None)


def _check_flag(flag: str) -> None:
    # Flags are quoted with backticks, not repr(): repr doubles a backslash, and the message
    # must show the flag exactly as the file spells it.
    if not flag.startswith("-"):
        raise CflagsError(f"flag `{flag}` must start with `-`")
    owned = _wrapper_owned(flag)
    if owned is not None:
        raise CflagsError(f"flag `{flag}` sets {owned}, which the wrapper owns")
    bad = next((c for c in ("/", "\\") if c in flag), None)
    if bad is not None:
        raise CflagsError(f"flag `{flag}` holds `{bad}`, which Watcom would misread")
    if any(c.isspace() for c in flag):
        raise CflagsError(f"flag `{flag}` holds whitespace")


def _check_spec(compiler: str, version: str, versions: Collection[str]) -> None:
    if compiler not in COMPILERS:
        raise CflagsError(f"unknown compiler {compiler!r}; known: {', '.join(COMPILERS)}")
    if version not in versions:
        raise CflagsError(
            f"unknown Watcom version {version!r}; known: {', '.join(versions)} "
            "(config/watcom.toml)"
        )


def _parse_rule(lineno: int, fields: list[str], versions: Collection[str]) -> Rule:
    if len(fields) < 2:
        raise CflagsError("expected `<glob>  <compiler>@<version>  <flags...>`")
    glob, spec, *flags = fields
    compiler, at, version = spec.partition("@")
    if not (at and compiler and version):
        raise CflagsError(f"expected <compiler>@<version>, got {spec!r}")
    _check_spec(compiler, version, versions)
    for flag in flags:
        _check_flag(flag)
    return Rule(glob, compiler, version, tuple(flags), lineno)


def parse_cflags(text: str, *, versions: Collection[str], where: str = "cflags.txt") -> list[Rule]:
    """The rules of a cflags.txt text, in file order. Every error names `where` and the line:
    a first rule whose glob is not `*`, a malformed compiler@version, an unknown compiler or
    version, and a flag that is wrapper-owned or holds `/`, `\\` or whitespace."""
    rules = []
    for lineno, fields in _fields(text):
        try:
            if not rules and fields[0] != "*":
                raise CflagsError(f"the first rule must be the `*` default, not {fields[0]!r}")
            rules.append(_parse_rule(lineno, fields, versions))
        except CflagsError as exc:
            raise CflagsError(f"{where}:{lineno}: {exc}") from exc
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
