"""unitdefs: the one "functions a unit defines" finder (D-29) and the one C-naming rule.

A unit file is read through configure.py's translation phases (normalize_source, code_text);
definitions and INCLUDE_ASM markers are matched by any C identifier and mapped to row starts
through C names, so a function renamed in symbols.csv is found by its start. Every name and
address here is made up."""

from __future__ import annotations

import pytest

from reverseapoc import unitdefs
from reverseapoc.functions import FunctionRow, SymbolRow

UNIT = "u_00010010"
FOO = FunctionRow(0x10010, 0x10020, "func_00010010", "game", UNIT, "call")
BAR = FunctionRow(0x10020, 0x10030, "func_00010020", "game", UNIT, "call")
FAR = FunctionRow(0x10030, 0x10040, "func_00010030", "game", "u_00010030", "call")
ROWS = (FOO, BAR)
EVERY_ROW = (FOO, BAR, FAR)
# 0x10010 is renamed Foo (symbols.csv Foo_); the others keep their placeholders.
NAMES = {"Foo": FOO.start, "func_00010020": BAR.start, "func_00010030": FAR.start}
COMPLETE = "void Foo(void) {}\nINCLUDE_ASM(func_00010020);\n"


def find(text: str, rows=ROWS, **kwargs) -> unitdefs.UnitDefs:
    kwargs.setdefault("names", NAMES)
    kwargs.setdefault("placeholders", unitdefs.placeholders(EVERY_ROW))
    return unitdefs.find(text, rows, **kwargs)


def test_renamed_definition_maps_to_its_start():
    defs = find("void Foo(void) {}\nINCLUDE_ASM(func_00010020);\n")
    assert defs.defined == {FOO.start: "Foo"}
    assert defs.marked == {BAR.start: "func_00010020"}
    assert defs.problems == ()


def test_old_placeholder_marker_accepted():
    """A marker emits no bytes, so a scaffold written before the rename still accounts for its
    row under the old placeholder."""
    defs = find("INCLUDE_ASM(func_00010010);\nINCLUDE_ASM(func_00010020);\n")
    assert defs.marked == {FOO.start: "func_00010010", BAR.start: "func_00010020"}
    assert defs.defined == {}
    assert defs.problems == ()


def test_new_name_marker_accepted():
    defs = find("INCLUDE_ASM(Foo);\nINCLUDE_ASM(func_00010020);\n")
    assert defs.marked == {FOO.start: "Foo", BAR.start: "func_00010020"}
    assert defs.problems == ()


def test_stale_placeholder_definition_is_a_problem():
    """A definition exports bytes under its name, so it must use the row's current C name."""
    defs = find("void func_00010010(void) {}\nINCLUDE_ASM(func_00010020);\n")
    assert FOO.start not in defs.defined
    (problem,) = defs.problems
    assert "func_00010010" in problem and "Foo" in problem
    assert problem in defs.source_problems


def test_keywords_and_inner_braces_ignored():
    text = (
        "void Foo(int x)\n{\n"
        "    if (x) {\n        x = 1;\n    }\n"
        "    while (x) {\n    }\n"
        "    switch (x) {\n    }\n"
        "    int func_00010020(void) { return 0; }\n"  # depth 1: not a file-scope definition
        "}\n"
        "INCLUDE_ASM(func_00010020);\n"
    )
    defs = find(text)
    assert defs.defined == {FOO.start: "Foo"}
    assert defs.marked == {BAR.start: "func_00010020"}
    assert defs.problems == ()


def test_watcom_keyword_before_the_name():
    defs = find("int __watcall Foo(int a, int (*cb)(int))\n{\n    return cb(a);\n}\n"
                "INCLUDE_ASM(func_00010020);\n")  # fmt: skip
    assert defs.defined == {FOO.start: "Foo"} and defs.problems == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (COMPLETE + "void Foo(void) {}\n", "Foo is defined 2 times"),
        (COMPLETE + "INCLUDE_ASM(Foo);\n", "Foo is both defined in C and marked INCLUDE_ASM"),
        (COMPLETE + "INCLUDE_ASM(func_00010010);\n",
         "Foo is both defined in C and marked INCLUDE_ASM"),
        ("INCLUDE_ASM(Foo);\nINCLUDE_ASM(func_00010010);\nINCLUDE_ASM(func_00010020);\n",
         "Foo is marked INCLUDE_ASM 2 times"),
        (COMPLETE + "INCLUDE_ASM(func_00010030);\n",
         "func_00010030 is marked INCLUDE_ASM but is not a function of the unit"),
        (COMPLETE + "void func_00010030(void) {}\n",
         "func_00010030 is defined in C but is not a function of the unit"),
        (COMPLETE + "void func_00099990(void) {}\n",
         "func_00099990 is defined in C but is not a function of the unit"),
        (COMPLETE + "INCLUDE_ASM(helper);\n",
         "helper is marked INCLUDE_ASM but is not a function of the unit"),
        ("INCLUDE_ASM(func_00010020);\n",
         "Foo is neither defined in C nor marked INCLUDE_ASM (D-12)"),
        (COMPLETE + "#ifdef FOO\n#endif\n", "#ifdef"),
    ],
    ids=["duplicate", "defined-and-marked", "defined-and-old-marker", "marked-twice",
         "other-unit-marker", "other-unit-definition", "no-row-placeholder", "unknown-marker",
         "neither", "ifdef"],  # fmt: skip
)
def test_problems(text, expected):
    (problem,) = find(text).problems
    assert expected in problem


def test_conditional_fails_closed():
    defs = find(COMPLETE + "#ifdef FOO\n#endif\n")
    assert defs.defined == {} and defs.marked == {}
    (problem,) = defs.problems
    assert problem.startswith("line 3: #ifdef") and defs.source_problems == defs.problems


def test_another_units_c_name_is_a_problem_with_all_names():
    """Without all_names a definition of an unknown identifier is a helper; with them, one that
    names another unit's row is refused."""
    text = COMPLETE + "void Baz(void) {}\n"
    unit_names = {"Foo": FOO.start, "func_00010020": BAR.start}
    assert find(text, names=unit_names).problems == ()
    (problem,) = find(text, names=unit_names, all_names={"Baz": FAR.start}).problems
    assert problem == "Baz is defined in C but is not a function of the unit"


def test_helpers_comments_and_dead_code_are_not_definitions():
    text = (
        "static int helper(int a) { return a; }\n"
        "/* void func_00010020(void) {} */\n"
        "#if 0\nvoid func_00010020(void) {}\n#endif\n"
        + COMPLETE
    )
    defs = find(text)
    assert defs.defined == {FOO.start: "Foo"} and defs.problems == ()


def test_markers_only_define_nothing():
    """DEC-04 edge: a scaffold of markers only defines nothing, and that is no problem."""
    defs = find("INCLUDE_ASM(Foo);\nINCLUDE_ASM(func_00010020);\n")
    assert defs.defined == {} and defs.problems == ()


def test_runtime_and_data_rows_are_exempt():
    runtime = FunctionRow(0x10020, 0x10030, "exit_", "runtime", UNIT, "runtime")
    data = FunctionRow(0x10030, 0x10040, "D_00010030", "data-in-code", UNIT, "runtime")
    rows = (FOO, runtime, data)
    defs = find("void Foo(void) {}\n", rows=rows)
    assert defs.defined == {FOO.start: "Foo"} and defs.problems == ()


def test_placeholder_names_by_default():
    """With names and placeholders both the rows' placeholders, find reads as the pre-D-29
    parser did."""
    holders = unitdefs.placeholders(ROWS)
    defs = unitdefs.find("void func_00010010(void) {}\nINCLUDE_ASM(func_00010020);\n", ROWS,
                         names=holders, placeholders=holders)  # fmt: skip
    assert defs.defined == {FOO.start: "func_00010010"}
    assert defs.marked == {BAR.start: "func_00010020"}
    assert defs.problems == ()


def test_c_name_of():
    assert unitdefs.c_name_of("Foo_", "func") == "Foo"
    assert unitdefs.c_name_of("_g_vol", "data") == "g_vol"
    assert unitdefs.c_name_of("main_", "func") == "main"
    with pytest.raises(ValueError, match="Foo"):
        unitdefs.c_name_of("Foo", "func")
    with pytest.raises(ValueError, match="g_vol"):
        unitdefs.c_name_of("g_vol", "data")
    with pytest.raises(ValueError):
        unitdefs.c_name_of("_", "func")
    with pytest.raises(ValueError):
        unitdefs.c_name_of("Foo_", "label")


def test_c_names():
    rows = (*EVERY_ROW, FunctionRow(0x10040, 0x10050, "func_00010040", "thunk", UNIT, "call"),
            FunctionRow(0x10050, 0x10060, "exit_", "runtime", UNIT, "runtime"))  # fmt: skip
    symbols = [SymbolRow(0x10010, "Foo_", "func"), SymbolRow(0x10040, "Jump_", "func"),
               SymbolRow(0x10050, "exit_", "func"),
               SymbolRow(0x20000, "_g_vol", "data")]  # fmt: skip
    assert unitdefs.c_names(rows, symbols) == {
        "Foo": 0x10010, "func_00010020": 0x10020, "func_00010030": 0x10030, "Jump": 0x10040}


def test_c_names_refuses_a_func_name_without_its_underscore():
    with pytest.raises(ValueError, match="Foo"):
        unitdefs.c_names(EVERY_ROW, [SymbolRow(0x10010, "Foo", "func")])


def test_placeholders():
    rows = (*EVERY_ROW, FunctionRow(0x10050, 0x10060, "exit_", "runtime", UNIT, "runtime"))
    assert unitdefs.placeholders(rows) == {
        "func_00010010": 0x10010, "func_00010020": 0x10020, "func_00010030": 0x10030}
