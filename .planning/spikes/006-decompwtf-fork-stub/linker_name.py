"""Spike 006, claims 2-4 of D-01: does decomp.wtf v0.10.6 fork mode find a Watcom function by
the name objdiff reports, is `_CHEAT` applied to agent submissions only, and what does our
configure.py say about the unit text fork mode would write?

Run (from the repo root, on the host):
    uv run python .planning/spikes/006-decompwtf-fork-stub/linker_name.py SRC [--plant]

SRC is the extracted v0.10.6 tarball. Read with Path.read_text and ast.parse only:
`app/forkengine.py`, `forks/csource.py` and every `src/decompnet/**/*.py` file (the
csource.replace caller scan). The finder pattern is rebuilt from the f-string's literal parts.
Nothing from decomp.wtf is imported or executed (docs/legal.md:26, D-03). From the repo:
configure.py, loaded by path (the cross-check, CONVENTIONS), and reverseapoc.functions and
reverseapoc.symbols, imported. Exit 1 when any claim fails.
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
_STRIPPERS = {"rstrip", "lstrip", "removesuffix", "removeprefix", "replace"}
_SEAM_TRIMS = {"rstrip", "lstrip", "strip"}
# A planted _insert_in_order return that drops the span text[span[0]:span[1]] (the stub).
_DROPS_SPAN = "text[:span[0]] + code + '\\n' + text[span[1]:]"
EXPECTED = {
    "linker-suffix": "_",  # Watcom register convention: objdiff sees func_X_
    "names-symbol": True,  # _names ends with meta["symbol"] and strips no underscore
    "symbol-source": True,  # meta["symbol"] is the objdiff report's function name
    "finder-linker-name": False,  # does csource.find("func_X_") find `int func_X(void) {`?
    "finder-c-name": True,  # does csource.find("func_X") find it?
    "finder-on-marker": False,  # does the finder hit INCLUDE_ASM(func_X); for either spelling?
    "attempt-refuses": True,  # _attempt raises when the submission has no span
    "cheat-sites": {("_attempt", "_strip_comments(source)"), ("edit_file", "_strip_comments(new)")},
    "attempt-inserts": True,  # no span in the unit file -> _attempt calls _insert_in_order
    "insert-keeps-stub": True,  # every _insert_in_order return keeps all of the file text
    "insert-control": False,  # does the keep-check accept a return that drops the span?
    "replace-unused": 0,  # calls of csource.replace anywhere in the package
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
    """The plain-name pattern: the re.compile in the `else` of find's `if "::" in name`."""
    func = function_def(csource, "find")
    for node in ast.walk(func):
        if not (isinstance(node, ast.If) and ast.unparse(node.test) == "'::' in name"):
            continue
        calls = [
            n
            for stmt in node.orelse
            for n in ast.walk(stmt)
            if is_re_call(n, "compile") and n.args and isinstance(n.args[0], ast.JoinedStr)
        ]
        if len(calls) != 1:
            raise SpikeError(f"find's plain-name branch has {len(calls)} f-string re.compile")
        return Pattern(calls[0].args[0], "name", 0)
    raise SpikeError("find has no `if '::' in name` branch")


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


def attempt_inserts(engine: ast.Module) -> tuple[bool, str]:
    """_attempt takes `old_span` from the unit file's text (`before`), and with no span it
    writes the code through _insert_in_order."""
    func = function_def(engine, "_attempt")
    from_file = any(
        isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Tuple)
        and ast.unparse(node.targets[0].elts[-1]) == "old_span"
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "self._find"
        and ast.unparse(node.value.args[0]) == "before"
        for node in ast.walk(func)
    )
    branches = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "old_span"
    ]
    inserts = [
        ast.unparse(call.func)
        for branch in branches
        for stmt in branch.orelse
        for call in ast.walk(stmt)
        if isinstance(call, ast.Call)
    ]
    ok = from_file and len(branches) == 1 and "self._insert_in_order" in inserts
    detail = (
        f"old_span from self._find(before, ...) {from_file}, "
        f"{len(branches)} `if old_span` branch, else calls _insert_in_order "
        f"{'self._insert_in_order' in inserts}"
    )
    return ok, detail


def _trimmed(term: ast.expr) -> ast.expr:
    """`term` without seam trims: x.rstrip("\\n"), x.lstrip(), ... with whitespace args only."""
    while (
        isinstance(term, ast.Call)
        and isinstance(term.func, ast.Attribute)
        and term.func.attr in _SEAM_TRIMS
        and all(isinstance(a, ast.Constant) and not str(a.value).strip() for a in term.args)
    ):
        term = term.func.value
    return term


def _terms(expr: ast.expr) -> list[ast.expr]:
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return _terms(expr.left) + _terms(expr.right)
    return [expr]


def keeps_text(expr: ast.expr) -> bool:
    """True when the concatenation `expr` holds `code` and all of `text`: `text` whole, or
    `text[:x]` followed later by `text[x:]` with the same x; anything else is refused."""
    pieces = []
    has_code = False
    for term in map(_trimmed, _terms(expr)):
        if isinstance(term, ast.Name) and term.id == "code":
            has_code = True
        elif isinstance(term, ast.Name) and term.id == "text":
            pieces.append(("whole", ""))
        elif (
            isinstance(term, ast.Subscript)
            and isinstance(term.value, ast.Name)
            and term.value.id == "text"
            and isinstance(term.slice, ast.Slice)
            and term.slice.step is None
            and (term.slice.lower is None) != (term.slice.upper is None)
        ):
            bound = term.slice.upper if term.slice.lower is None else term.slice.lower
            pieces.append(("head" if term.slice.lower is None else "tail", ast.unparse(bound)))
        elif not (isinstance(term, ast.Constant) and isinstance(term.value, str)):
            return False
    whole = pieces == [("whole", "")]
    split = len(pieces) == 2 and pieces[0][0] == "head" and pieces[1] == ("tail", pieces[0][1])
    return has_code and (whole or split)


def insert_keeps_stub(engine: ast.Module) -> tuple[bool, str]:
    func = function_def(engine, "_insert_in_order")
    params = [arg.arg for arg in func.args.args]
    if params[-2:] != ["text", "code"]:
        raise SpikeError(f"_insert_in_order parameters {params}")
    returns = [node for node in ast.walk(func) if isinstance(node, ast.Return)]
    kept = [ret.value is not None and keeps_text(ret.value) for ret in returns]
    # A store to `text` (x = ..., for text in, walrus) before a return could drop the stub.
    rebinds = [
        node.lineno
        for node in ast.walk(func)
        if isinstance(node, ast.Name) and node.id == "text" and isinstance(node.ctx, ast.Store)
    ]
    ok = bool(returns) and all(kept) and not rebinds
    detail = f"{len(returns)} returns, {kept.count(True)} keep all of `text` around `code`"
    return ok, f"{detail}, `text` rebound at lines {rebinds}"


def replace_callers(src: Path) -> list[str]:
    """Every `csource.replace` call, or import of `replace` from csource, in the package."""
    found = []
    paths = sorted(src.glob("src/decompnet/**/*.py"))
    scanned = {path.relative_to(src).as_posix() for path in paths}
    if "src/decompnet/app/forkengine.py" not in scanned:
        raise SpikeError(
            f"src/decompnet/**/*.py under {src} ({len(paths)} files) lacks forkengine.py"
        )
    for path in paths:
        rel = path.relative_to(src).as_posix()
        for node in ast.walk(parse(path)):
            called = (
                isinstance(node, ast.Attribute)
                and node.attr == "replace"
                and isinstance(node.value, ast.Name)
                and node.value.id == "csource"
            )
            imported = (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").endswith("csource")
                and any(alias.name == "replace" for alias in node.names)
            )
            if called or imported:
                found.append(f"{rel}:{node.lineno}")
    return found


def report(file: str, claim: str, ok: bool, detail: str) -> bool:
    print(f"{'PASS' if ok else 'FAIL'} {file} {claim} {detail}")
    return ok


def shaped(file: str, check, *args):
    """Run `check`, naming `file` in any shape error it raises."""
    try:
        return check(*args)
    except SpikeError as exc:
        raise SpikeError(f"{file} shape {exc}") from None


def run(src: Path, expected: dict) -> list[bool]:
    engine = shaped("forkengine.py", lambda: parse(find_one(src, "app/forkengine.py")))
    csource = shaped("csource.py", lambda: parse(find_one(src, "forks/csource.py")))
    results = []
    ok = FUNCTION_LINK_SUFFIX == expected["linker-suffix"]
    results.append(report("symbols.py", "linker-suffix", ok, f"{NAME} -> {LINKER}"))
    for claim, check in (("names-symbol", names_symbol), ("symbol-source", symbol_source)):
        good, detail = shaped("forkengine.py", check, engine)
        results.append(report("forkengine.py", claim, good == expected[claim], detail))
    finder = shaped("csource.py", finder_pattern, csource)
    for claim, name in (("finder-linker-name", LINKER), ("finder-c-name", NAME)):
        found = finder.compile(name).search(DEFINITION) is not None
        detail = f"find({name!r}) on `int {NAME}(void) {{` matched {found}"
        results.append(report("csource.py", claim, found == expected[claim], detail))
    hits = {name: finder.compile(name).search(MARKER) is not None for name in (NAME, LINKER)}
    ok = not any(hits.values()) if not expected["finder-on-marker"] else all(hits.values())
    detail = f"find on `{MARKER.strip()}` matched {hits}"
    results.append(report("csource.py", "finder-on-marker", ok, detail))
    good, detail = shaped("forkengine.py", attempt_refuses, engine)
    results.append(report("forkengine.py", "attempt-refuses", good, detail))
    sites, uses = shaped("forkengine.py", cheat_sites, engine)
    ok = sites == expected["cheat-sites"] and len(uses) == len(sites)
    results.append(report("forkengine.py", "cheat-sites", ok, f"{sorted(sites)}, {len(uses)} uses"))
    for claim, check in (
        ("attempt-inserts", attempt_inserts),
        ("insert-keeps-stub", insert_keeps_stub),
    ):
        good, detail = shaped("forkengine.py", check, engine)
        results.append(report("forkengine.py", claim, good == expected[claim], detail))
    planted = keeps_text(ast.parse(_DROPS_SPAN, mode="eval").body)
    detail = f"keep-check on `{_DROPS_SPAN}` accepted {planted}"
    results.append(
        report("linker_name.py", "insert-control", planted == expected["insert-control"], detail)
    )
    callers = shaped("package", replace_callers, src)
    ok = len(callers) == expected["replace-unused"]
    results.append(report("package", "replace-unused", ok, f"csource.replace callers {callers}"))
    results.extend(shaped("configure.py", check_unit, expected))
    return results


def check_unit(expected: dict) -> list[bool]:
    configure = load_configure()
    row = FunctionRow(0x000A3980, 0x000A398D, NAME, KIND_GAME, "u_000a34f0", "call")
    # _insert_in_order keeps the marker and adds the definition; D-12 is order-independent.
    written = MARKER + "\n" + DEFINITION
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
        print(f"FAIL {exc}")
        print("1 FAILED")
        return 1
    failed = results.count(False)
    print("ALL PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
