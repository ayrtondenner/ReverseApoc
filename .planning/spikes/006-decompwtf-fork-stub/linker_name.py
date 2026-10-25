"""Spike 006, claims 2-4 of D-01: does decomp.wtf v0.10.6 fork mode find a Watcom function by
the name objdiff reports, is `_CHEAT` applied to agent submissions only, and what does our
configure.py say about the unit text fork mode would write?

Run (from the repo root, on the host):
    uv run python .planning/spikes/006-decompwtf-fork-stub/linker_name.py SRC [--plant]

SRC is the extracted v0.10.6 tarball. `app/forkengine.py` and `forks/csource.py` are read with
Path.read_text and ast.parse only; the finder pattern is rebuilt from the f-string's literal
parts. Nothing from decomp.wtf is imported or executed (docs/legal.md:26, D-03). The repo's own
configure.py is loaded by path (the cross-check, CONVENTIONS). Exit 1 when any claim fails.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from pathlib import Path

from stub_regex import Pattern, SpikeError, function_def, is_re_call

from reverseapoc.functions import KIND_GAME, FunctionRow
from reverseapoc.symbols import FUNCTION_LINK_SUFFIX

REPO = Path(__file__).resolve().parents[3]
NAME = "func_000A3980"
LINKER = NAME + FUNCTION_LINK_SUFFIX
DEFINITION = f"int {NAME}(void)\n{{\n    return 0;\n}}\n"
MARKER = f"INCLUDE_ASM({NAME});\n"
_FINDER_PREFIX = "(?<![\\w:~])(?:[\\w~<>]+::)*"
_STRIPPERS = {"rstrip", "lstrip", "removesuffix", "removeprefix", "replace"}
EXPECTED = {
    "linker-suffix": "_",  # Watcom register convention: objdiff sees func_X_
    "names-symbol": True,  # _names ends with meta["symbol"] and strips no underscore
    "symbol-source": True,  # meta["symbol"] is the objdiff report's function name
    "finder-linker-name": False,  # csource.find("func_X_") finds `int func_X(void) {`
    "finder-c-name": True,  # csource.find("func_X") finds it
    "attempt-refuses": True,  # _attempt raises when the submission has no span
    "cheat-sites": {("_attempt", "_strip_comments(source)"), ("edit_file", "_strip_comments(new)")},
    "replace-appends": True,  # csource.replace appends the code when find returns None
    "check-refuses": f"{NAME} is both defined in C and marked INCLUDE_ASM",
    "check-control": [],  # the definition alone is accepted
}


def find_one(src: Path, rel: str) -> Path:
    found = sorted(src.glob(f"**/{rel}"))
    if len(found) != 1:
        raise SpikeError(f"expected one {rel} under {src}, found {len(found)}")
    return found[0]


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def load_configure():
    spec = importlib.util.spec_from_file_location("configure", REPO / "configure.py")
    if spec is None or spec.loader is None:
        raise SpikeError("cannot load configure.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["configure"] = module
    spec.loader.exec_module(module)
    return module


def method_calls(func: ast.FunctionDef) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(func)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def names_symbol(engine: ast.Module) -> tuple[bool, str]:
    func = function_def(engine, "_names")
    last = func.body[-2] if isinstance(func.body[-1], ast.Return) else func.body[-1]
    text = ast.unparse(last)
    takes_symbol = "meta.get('symbol')" in text and text.startswith("out.append(")
    strips = sorted(method_calls(func) & _STRIPPERS)
    bare_strip = all(
        not node.args
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "strip"
    )
    ok = takes_symbol and not strips and bare_strip
    return (
        ok,
        f"last spelling {text!r}, stripping calls {strips}, strip() without args {bare_strip}",
    )


def symbol_source(engine: ast.Module) -> tuple[bool, str]:
    """Each dict literal with a "symbol" key takes a name assigned from `f["name"]`."""
    found = []
    for func in (n for n in ast.walk(engine) if isinstance(n, ast.FunctionDef)):
        assigned = {
            node.targets[0].id: ast.unparse(node.value)
            for node in ast.walk(func)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        }
        for node in (n for n in ast.walk(func) if isinstance(n, ast.Dict)):
            for key, value in zip(node.keys, node.values, strict=True):
                if not (isinstance(key, ast.Constant) and key.value == "symbol"):
                    continue
                source = assigned.get(value.id) if isinstance(value, ast.Name) else None
                found.append((func.name, ast.unparse(value), source))
    ok = bool(found) and all(source == "f['name']" for _, _, source in found)
    return ok, f"symbol dicts {found}"


def finder_pattern(csource: ast.Module) -> Pattern:
    func = function_def(csource, "find")
    for node in ast.walk(func):
        if not (is_re_call(node, "compile") and isinstance(node.args[0], ast.JoinedStr)):
            continue
        first = node.args[0].values[0]
        if isinstance(first, ast.Constant) and first.value == _FINDER_PREFIX:
            return Pattern(node.args[0], "name", 0)
    raise SpikeError("find has no plain-name pattern")


def attempt_refuses(engine: ast.Module) -> tuple[bool, str]:
    func = function_def(engine, "_attempt")
    for node in ast.walk(func):
        if not isinstance(node, ast.If):
            continue
        test = ast.unparse(node.test)
        if test == "span is None" and isinstance(node.body[0], ast.Raise):
            return True, f"if {test}: {ast.unparse(node.body[0])[:80]}"
    return False, "no `if span is None: raise` in _attempt"


def cheat_sites(engine: ast.Module) -> tuple[set[tuple[str, str]], list[str]]:
    sites = set()
    for func in (n for n in ast.walk(engine) if isinstance(n, ast.FunctionDef)):
        params = {arg.arg for arg in func.args.args + func.args.kwonlyargs}
        for node in ast.walk(func):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "search"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "_CHEAT"
            ):
                continue
            arg = node.args[0]
            inner = arg.args[0] if isinstance(arg, ast.Call) and arg.args else arg
            if isinstance(inner, ast.Name) and inner.id in params:
                sites.add((func.name, ast.unparse(arg)))
            else:
                sites.add((func.name, "non-parameter " + ast.unparse(arg)))
    uses = [
        ast.unparse(n)
        for n in ast.walk(engine)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "_CHEAT"
    ]
    return sites, uses


def replace_appends(csource: ast.Module) -> tuple[bool, str]:
    func = function_def(csource, "replace")
    for node in ast.walk(func):
        if isinstance(node, ast.If) and ast.unparse(node.test) == "span is None":
            body = node.body[0]
            text = ast.unparse(body)
            ok = (
                isinstance(body, ast.Return)
                and text.startswith("return text")
                and text.endswith("+ code")
            )
            return ok, text
    return False, "no `if span is None` in replace"


def report(file: str, claim: str, ok: bool, detail: str) -> bool:
    print(f"{'PASS' if ok else 'FAIL'} {file} {claim} {detail}")
    return ok


def run(src: Path, expected: dict) -> list[bool]:
    engine = parse(find_one(src, "app/forkengine.py"))
    csource = parse(find_one(src, "forks/csource.py"))
    results = []
    ok = FUNCTION_LINK_SUFFIX == expected["linker-suffix"]
    results.append(report("symbols.py", "linker-suffix", ok, f"{NAME} -> {LINKER}"))
    for claim, check in (("names-symbol", names_symbol), ("symbol-source", symbol_source)):
        good, detail = check(engine)
        results.append(report("forkengine.py", claim, good == expected[claim], detail))
    finder = finder_pattern(csource)
    for claim, name in (("finder-linker-name", LINKER), ("finder-c-name", NAME)):
        found = finder.compile(name).search(DEFINITION) is not None
        detail = f"find({name!r}) on `int {NAME}(void) {{` matched {found}"
        results.append(report("csource.py", claim, found == expected[claim], detail))
    good, detail = attempt_refuses(engine)
    results.append(report("forkengine.py", "attempt-refuses", good, detail))
    sites, uses = cheat_sites(engine)
    ok = sites == expected["cheat-sites"] and len(uses) == len(sites)
    results.append(report("forkengine.py", "cheat-sites", ok, f"{sorted(sites)}, {len(uses)} uses"))
    good, detail = replace_appends(csource)
    results.append(report("csource.py", "replace-appends", good, detail))
    results.extend(check_unit(expected))
    return results


def check_unit(expected: dict) -> list[bool]:
    configure = load_configure()
    row = FunctionRow(0x000A3980, 0x000A398D, NAME, KIND_GAME, "u_000a34f0", "call")
    written = MARKER + "\n" + DEFINITION  # csource.replace appends: marker stays, definition added
    problems = configure.check_unit_source(written, [row])
    ok = problems == [expected["check-refuses"]]
    out = [report("configure.py", "check-refuses", ok, f"marker+definition -> {problems}")]
    control = configure.check_unit_source(DEFINITION, [row])
    ok = control == expected["check-control"]
    out.append(report("configure.py", "check-control", ok, f"definition only -> {control}"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path, help="the extracted decomp.wtf v0.10.6 source root")
    parser.add_argument("--plant", action="store_true", help="flip one expectation")
    args = parser.parse_args(argv)
    expected = dict(EXPECTED)
    if args.plant:
        expected["finder-linker-name"] = not expected["finder-linker-name"]
    try:
        results = run(args.src, expected)
    except SpikeError as exc:
        print(f"FAIL forkengine.py shape {exc}")
        print("1 FAILED")
        return 1
    failed = results.count(False)
    print("ALL PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
