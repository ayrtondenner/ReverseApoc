"""Spike 006, claim 1 of D-01: does decomp.wtf v0.10.6's stub finder (`forks/csource.py`,
`_stub`) recognise the repo's `INCLUDE_ASM(func_X);` marker?

Run (from the repo root, on the host):
    uv run python .planning/spikes/006-decompwtf-fork-stub/stub_regex.py SRC [--plant]

SRC is the extracted v0.10.6 tarball (build/spike006/src/decomp.wtf-0.10.6/). Its source is
untrusted data: this script reads `forks/csource.py` with Path.read_text, parses it with
ast.parse and rebuilds the `_stub` pattern from the f-string's literal parts. Nothing from
decomp.wtf is imported or executed (docs/legal.md:26, D-03). Exit 1 when any claim fails.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FILE = "csource.py"
NAME = "func_000A34F0"
# D-01: the class before the name needs `"`, `/`, `,` or a space, so a bare marker misses.
EXPECTED = {
    "bare-marker": False,  # is INCLUDE_ASM(func_000A34F0); found by _stub?
    "quoted-marker": True,  # is INCLUDE_ASM("x", func_000A34F0); found by _stub?
    "char-class": {'"': True, "/": True, ",": True, " ": True, "(": False},
    "repo-markers": False,  # is any INCLUDE_ASM line under src/ found by _stub?
}
_FLAGS = {
    "M": re.MULTILINE,
    "MULTILINE": re.MULTILINE,
    "S": re.DOTALL,
    "DOTALL": re.DOTALL,
    "I": re.IGNORECASE,
    "IGNORECASE": re.IGNORECASE,
    "X": re.VERBOSE,
    "VERBOSE": re.VERBOSE,
}
_LAST_CLASS = re.compile(r"\[((?:\\.|[^\]\\])*)\][^\[]*$")
_REPO_MARKER = re.compile(r"^[ \t]*INCLUDE_ASM\s*\(\s*(func_[0-9A-F]{8})\s*\)\s*;", re.M)


class SpikeError(Exception):
    """The source does not have the shape the claims are about."""


def find_file(src: Path) -> Path:
    found = sorted(src.glob(f"**/forks/{FILE}"))
    if len(found) != 1:
        raise SpikeError(f"expected one forks/{FILE} under {src}, found {len(found)}")
    return found[0]


def function_def(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise SpikeError(f"no def {name}")


def is_re_call(node: ast.AST, attr: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "re"
    )


def flag_value(node: ast.expr) -> int:
    """`re.M`, `re.S | re.M`, ...; anything else is refused."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return flag_value(node.left) | flag_value(node.right)
    if isinstance(node, ast.Attribute) and node.attr in _FLAGS:
        return _FLAGS[node.attr]
    raise SpikeError(f"unknown flag expression {ast.unparse(node)}")


def compile_call(func: ast.FunctionDef) -> ast.Call:
    calls = [node for node in ast.walk(func) if is_re_call(node, "compile")]
    if len(calls) != 1:
        raise SpikeError(f"{func.name}: expected one re.compile, found {len(calls)}")
    return calls[0]


class Pattern:
    """An f-string pattern whose only replacement fields are `re.escape(<param>)`."""

    def __init__(self, joined: ast.JoinedStr, param: str, flags: int) -> None:
        self.parts: list[str | None] = []
        for value in joined.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                self.parts.append(value.value)
                continue
            if not self._is_escape(value, param):
                raise SpikeError(f"unexpected field {ast.unparse(value)}")
            self.parts.append(None)
        self.flags = flags

    @staticmethod
    def _is_escape(value: ast.expr, param: str) -> bool:
        if not isinstance(value, ast.FormattedValue):
            return False
        if value.conversion != -1 or value.format_spec is not None:
            return False
        call = value.value
        if not is_re_call(call, "escape") or len(call.args) != 1:
            return False
        arg = call.args[0]
        return isinstance(arg, ast.Name) and arg.id == param

    def compile(self, name: str) -> re.Pattern[str]:
        text = "".join(re.escape(name) if part is None else part for part in self.parts)
        return re.compile(text, self.flags)

    def before_name(self) -> str:
        index = self.parts.index(None)
        before = self.parts[index - 1]
        if before is None:
            raise SpikeError("two fields in a row")
        return before


def stub_pattern(path: Path) -> Pattern:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    func = function_def(tree, "_stub")
    params = [arg.arg for arg in func.args.args]
    if params[:2] != ["text", "name"]:
        raise SpikeError(f"_stub parameters {params}")
    call = compile_call(func)
    joined = call.args[0]
    if not isinstance(joined, ast.JoinedStr):
        raise SpikeError("_stub's pattern is not an f-string")
    flags = 0
    if len(call.args) > 1:
        flags = flag_value(call.args[1])
    for keyword in call.keywords:
        if keyword.arg == "flags":
            flags |= flag_value(keyword.value)
    return Pattern(joined, "name", flags)


def repo_markers() -> list[tuple[str, str]]:
    """(file, name) of every INCLUDE_ASM line in the repo's unit files."""
    found = []
    for path in sorted((REPO / "src").glob("*/*.c")):
        rel = path.relative_to(REPO).as_posix()
        for match in _REPO_MARKER.finditer(path.read_text(encoding="utf-8")):
            found.append((rel, match.group(1)))
    return found


def report(claim: str, ok: bool, detail: str) -> bool:
    print(f"{'PASS' if ok else 'FAIL'} {FILE} {claim} {detail}")
    return ok


def run(pattern: Pattern, expected: dict) -> list[bool]:
    results = []
    stub = pattern.compile(NAME)
    for claim, line in (
        ("bare-marker", f"INCLUDE_ASM({NAME});\n"),
        ("quoted-marker", f'INCLUDE_ASM("x", {NAME});\n'),
    ):
        found = stub.search(line) is not None
        detail = f"{line.strip()} matched {found} (expect {expected[claim]})"
        results.append(report(claim, found == expected[claim], detail))
    found_class = _LAST_CLASS.search(pattern.before_name())
    if found_class is None:
        raise SpikeError("no character class before the name")
    char_class = "[" + found_class.group(1) + "]"
    held = {ch: re.fullmatch(char_class, ch) is not None for ch in expected["char-class"]}
    shown = " ".join(f"{ch!r}:{held[ch]}" for ch in held)
    results.append(report("char-class", held == expected["char-class"], f"{char_class} {shown}"))
    markers = repo_markers()
    hits = [
        f"{rel}:{name}"
        for rel, name in markers
        if pattern.compile(name).search((REPO / rel).read_text(encoding="utf-8")) is not None
    ]
    ok = bool(markers) and bool(hits) == expected["repo-markers"]
    detail = f"{len(markers)} markers under src/, {len(hits)} found by _stub {hits}"
    results.append(report("repo-markers", ok, detail))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path, help="the extracted decomp.wtf v0.10.6 source root")
    parser.add_argument("--plant", action="store_true", help="flip the first expectation")
    args = parser.parse_args(argv)
    expected = dict(EXPECTED)
    if args.plant:
        expected["bare-marker"] = not expected["bare-marker"]
    try:
        pattern = stub_pattern(find_file(args.src))
        results = run(pattern, expected)
    except SpikeError as exc:
        print(f"FAIL {FILE} shape {exc}")
        print("1 FAILED")
        return 1
    failed = results.count(False)
    print("ALL PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
