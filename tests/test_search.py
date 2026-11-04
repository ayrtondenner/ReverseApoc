"""`reverseapoc search`: refusals, the four axes, the waves, the slot map and the D-12 queue route.

No compiler runs here: batch.compile_batch, function_body, body_key and judge are stubbed, and a
stubbed verdict is decided by the text of the variant and the cell it was compiled under. The C
below is made up. New names are reached as attributes of `reverseapoc.search`.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

import reverseapoc
from reverseapoc import batch, cli, flags
from reverseapoc.cflags import Rule
from reverseapoc.cli import main
from reverseapoc.functions import FunctionRow
from reverseapoc.status import lf_sha256
from test_flags import A1, CELL, UA, batch_repo, queue_of

START = 0x10000
ADDRESS = f"0x{START:08X}"
COMMITTED = Rule("*", "wcc386", "10.6", ("-4r", "-s", "-fpi"), 1)
ONEATX = Rule("*", "wcc386", "10.6", ("-4r", "-oneatx", "-s", "-fpi"), 1)
AUTHOR = "reverseapoc search"
ROW = FunctionRow(START, START + 16, A1, "game", UA, "call")

TEXT = """/* made-up C */
#include "common.h"

int func_00010000(int a)
{
    int b;
    short c;
    int *p;
    char d[4];

    b = a + 1;
    c = b;
    p = &b;
    d[0] = c;
    return *p;
}
"""
MOVES = 10  # on the type axis: b and c, five types each; the pointer and the array do not move


def _slots():
    """The stubbed slot map: one pair differs, one does not."""
    return batch.SlotMap(((8, 0xC), (0x10, 0x10)), True, 0x10, 0x14)


def _exe() -> SimpleNamespace:
    return SimpleNamespace(stem="ufo2p", flat=bytes(START) + b"\xc3" * 16, rows=(ROW,),
                           symbols=SimpleNamespace(c_name=lambda _va: A1))  # fmt: skip


def verdict(score: float = 50.0, stack: float = 50.0, exact: bool = False) -> batch.Verdict:
    """A judge verdict; an exact one scores 100 on both scores."""
    if exact:
        return batch.Verdict(True, True, True, 0, 16, 16, 100.0, "", stack_score=100.0)
    return batch.Verdict(False, True, False, 3, 16, 16, score, "mov", stack_score=stack)


def _source(obj: Path) -> tuple[str, str]:
    """(the variant's text, its cell file's stem) of an object beside its source."""
    return obj.with_suffix(".c").read_text(encoding="ascii"), obj.stem


class Stubs:
    """The compiler and the judge. `decide(text, cell)` gives a verdict, `key(text, cell)` a body
    key (by default every file is its own body) and `compiles(text)` a compile result."""

    def __init__(self, monkeypatch, out: Path, decide=None) -> None:
        self.decide = decide or (lambda _text, _cell: verdict())
        self.key = lambda text, cell: f"{cell}\n{text}"
        self.compiles = lambda _text: True
        self.waves: list[tuple[batch.Job, ...]] = []
        self.judged: list[Path] = []
        self.slot_objects: list[Path] = []
        monkeypatch.setattr(reverseapoc.search, "OUT", out)
        monkeypatch.setattr(batch, "compile_batch", self._compile_batch)
        monkeypatch.setattr(batch, "function_body", lambda _exe, obj, _start: obj)
        monkeypatch.setattr(batch, "body_key", lambda obj: self.key(*_source(obj)))
        monkeypatch.setattr(batch, "judge", self._judge)
        monkeypatch.setattr(batch, "function_slots", self._function_slots)

    def _function_slots(self, _exe, obj: Path, _start: int) -> batch.SlotMap:
        self.slot_objects.append(obj)
        return _slots()

    def _compile_batch(self, jobs, _workers, **_kwargs) -> batch.BatchResult:
        jobs = tuple(jobs)
        self.waves.append(jobs)
        compiled = tuple(batch.Compiled(job, self.compiles(job.src.read_text(encoding="ascii")),
                                        0.0, "Error! E0: made up") for job in jobs)  # fmt: skip
        return batch.BatchResult(compiled, 0.0, 0.0)

    def _judge(self, _exe, obj: Path, _start: int) -> batch.Verdict:
        self.judged.append(obj)
        return self.decide(*_source(obj))

    @property
    def jobs(self) -> list[batch.Job]:
        return [job for wave in self.waves for job in wave]


@pytest.fixture
def stubs(monkeypatch, tmp_path) -> Stubs:
    return Stubs(monkeypatch, tmp_path / "out")


@pytest.fixture
def type_axis(monkeypatch):
    """Only the type axis, for tests that count its moves."""
    monkeypatch.setattr(reverseapoc.search, "AXES", ("type",))


def _run(text: str = TEXT, rule: Rule = COMMITTED):
    return reverseapoc.search.run_search(_exe(), ROW, text, (rule,), watcom_dir=Path("watcom"))


def _records(result) -> list[dict]:
    path = result.best.parent / "results.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---- refusals: nothing loads or compiles (the shape of tests/test_cli_batch.py) -----------------


@pytest.fixture
def no_load(monkeypatch):
    """Fail the test if the verb loads an EXE or compiles anything."""

    def refuse(*args, **kwargs):
        raise AssertionError("loaded or compiled before refusing")

    monkeypatch.setattr(batch, "load_exe_inputs", refuse)
    monkeypatch.setattr(batch, "compile_batch", refuse)


def _search(tmp_path, source, address: str = ADDRESS) -> int:
    return main(["search", "ufo2p", address, str(source), "--orig", str(tmp_path / "noorig")])


@pytest.mark.parametrize(
    "text", ["#pragma aux f \"*\"\nint f(void) { return 0; }\n", "void f(void) { __asm nop }\n"]
)
def test_search_refuses_pragma_and_inline_asm(tmp_path, capsys, no_load, text):
    source = tmp_path / "f.c"
    source.write_text(text, encoding="ascii")
    assert _search(tmp_path, source) == 2
    assert "reverseapoc search: refused:" in capsys.readouterr().err


def test_search_refuses_a_non_ascii_source(tmp_path, capsys, no_load):
    source = tmp_path / "f.c"
    source.write_bytes("int f(void) { return 0; } /* é */\n".encode())
    assert _search(tmp_path, source) == 2
    assert "reverseapoc search:" in capsys.readouterr().err


def test_search_missing_file_is_a_tool_error(tmp_path, capsys, no_load):
    assert _search(tmp_path, tmp_path / "missing.c") == 2
    assert "reverseapoc search: error:" in capsys.readouterr().err


def test_search_bad_address_is_a_tool_error(tmp_path, capsys, no_load):
    source = tmp_path / "f.c"
    source.write_text("int f(void) { return 0; }\n", encoding="ascii")
    assert _search(tmp_path, source, "0xZZ") == 2
    assert "reverseapoc search: error:" in capsys.readouterr().err


# ---- the verb -----------------------------------------------------------------------------------


def _cli(tmp_path, monkeypatch) -> int:
    """`reverseapoc search` on TEXT, the EXE loader stubbed, under a one-rule cflags file."""
    monkeypatch.setattr(batch, "load_exe_inputs", lambda *_args, **_kwargs: _exe())
    source = tmp_path / "f.c"
    source.write_text(TEXT, encoding="ascii")
    cflags = tmp_path / "cflags.txt"
    cflags.write_text("*  wcc386@10.6  -4r -s -fpi\n", encoding="ascii")
    return main(["search", "ufo2p", ADDRESS, str(source), "--cflags", str(cflags)])


def test_search_exit_codes(tmp_path, monkeypatch, stubs):
    assert _cli(tmp_path, monkeypatch) == 1
    stubs.decide = lambda text, _cell: verdict(exact="    short b;" in text)
    assert _cli(tmp_path, monkeypatch) == 0


def test_search_function_missing_from_file_is_a_tool_error(tmp_path, monkeypatch, capsys, stubs):
    monkeypatch.setattr(batch, "load_exe_inputs", lambda *_args, **_kwargs: _exe())
    source = tmp_path / "f.c"
    source.write_text("int other(void)\n{\n    return 0;\n}\n", encoding="ascii")
    assert main(["search", "ufo2p", ADDRESS, str(source)]) == 2
    assert f"reverseapoc search: error: {A1}" in capsys.readouterr().err
    assert stubs.waves == []


def test_search_prints_one_summary_line(tmp_path, monkeypatch, capsys, stubs, type_axis):
    stubs.key = lambda _text, cell: cell
    stubs.decide = lambda _text, _cell: verdict(91.5, 97.25)
    assert _cli(tmp_path, monkeypatch) == 1
    line = capsys.readouterr().out.splitlines()[0]
    for part in (f"{(MOVES + 1) * 2} compiles", "2 distinct bodies", "exact False", "score 91.5",
                 "stack score 97.25", "axes -", "best.c"):  # fmt: skip
        assert part in line


def test_search_prints_the_slot_map(tmp_path, monkeypatch, capsys, stubs):
    assert _cli(tmp_path, monkeypatch) == 1
    lines = capsys.readouterr().out.splitlines()[1:]
    assert lines == ["frame: ours 0x10, theirs 0x14", "slots: bijection True", "slot 0x8 -> 0xc"]


def test_search_says_when_no_slot_was_compared(tmp_path, monkeypatch, capsys, stubs):
    """An empty map is no bijection: nothing was compared."""
    none = batch.SlotMap((), True, 0, 0x14)
    monkeypatch.setattr(batch, "function_slots", lambda _exe, _obj, _start: none)
    assert _cli(tmp_path, monkeypatch) == 1
    lines = capsys.readouterr().out.splitlines()[1:]
    assert lines == ["frame: ours 0x0, theirs 0x14", "slots: none compared"]


def test_search_parses_its_arguments():
    args = cli.build_parser().parse_args(["search", "ufo2p", ADDRESS, "f.c"])
    assert (args.exe, args.address, str(args.file)) == ("ufo2p", ADDRESS, "f.c")
    assert args.func is cli._cmd_search


@pytest.mark.parametrize("option", ["--cell", "--json", "--workers", "--budget", "--seed"])
def test_search_has_no_option_d01_does_not_name(capsys, option):
    with pytest.raises(SystemExit) as raised:
        cli.build_parser().parse_args(["search", "ufo2p", ADDRESS, "f.c", option, "1"])
    assert raised.value.code == 2


def test_search_help_says_it_never_lands(capsys):
    with pytest.raises(SystemExit):
        main(["search", "--help"])
    assert "never lands" in " ".join(capsys.readouterr().out.split())


# ---- the source: span, declarations, moves ------------------------------------------------------


SHAPES = """int func_00010000(int a);

int func_00010000(int a)
{
    int b;
    struct pos *p;
    unsigned short q = 1;
    /* int hidden; */
    u8 r;
    static int kept;
    /*
    int also_hidden;
    */

    if (a) {
        int inner;

        inner = a;
        b = inner * a;
    }
    func_00010000(b);
    b = a;
    return b;
}
"""


def test_function_span_finds_the_definition():
    lines = SHAPES.split("\n")
    first, last = reverseapoc.search.function_span(SHAPES, A1)
    assert (lines[first], lines[last]) == ("{", "}")
    assert first == 3


def test_function_span_ignores_braces_in_comments_and_strings():
    text = 'int f(int a)\n{\n    /* } */\n    g("}");\n    return a;\n}\nint h;\n'
    assert reverseapoc.search.function_span(text, "f") == (1, 5)


def test_function_span_reads_a_brace_on_the_header_line():
    assert reverseapoc.search.function_span("int f(int a) {\n    return a;\n}\n", "f") == (0, 2)


@pytest.mark.parametrize("text", ["int other(void)\n{\n}\n", "int f(void);\n", "f(1);\n"])
def test_function_span_refuses_a_missing_definition(text):
    with pytest.raises(batch.BatchError, match="f"):
        reverseapoc.search.function_span(text, "f")


def test_function_span_refuses_an_unbalanced_body():
    with pytest.raises(batch.BatchError, match="f"):
        reverseapoc.search.function_span("int f(void)\n{\n    return 0;\n", "f")


def test_declarations_are_the_declaration_lines_of_every_block():
    search = reverseapoc.search
    lines = SHAPES.split("\n")
    span = search.function_span(SHAPES, A1)
    found = [lines[i].strip() for i in search.declarations(SHAPES, span)]
    assert found == ["int b;", "struct pos *p;", "unsigned short q = 1;", "u8 r;", "int inner;"]


def test_split_declarators_gives_one_declarator_per_line():
    search = reverseapoc.search
    text = ("int f(void)\n{\n    int a, *b; /* two */\n    int c = g(1, 2), d[2];\n"
            "    short e;\n\n    return 0;\n}\n")  # fmt: skip
    assert search.split_declarators(text, search.function_span(text, "f")) == (
        "int f(void)\n{\n    int a;\n    int *b; /* two */\n    int c = g(1, 2);\n    int d[2];\n"
        "    short e;\n\n    return 0;\n}\n"
    )  # fmt: skip


def test_split_declarators_leaves_the_other_functions_alone():
    search = reverseapoc.search
    text = "int f(void)\n{\n    int a, b;\n}\n\nint g(void)\n{\n    int c, d;\n}\n"
    split = search.split_declarators(text, search.function_span(text, "g"))
    assert "    int a, b;\n" in split
    assert "    int c;\n    int d;\n" in split


def test_type_moves_change_one_declaration():
    search = reverseapoc.search
    base = TEXT.split("\n")
    moves = list(search.type_moves(TEXT, search.function_span(TEXT, A1)))
    assert len(moves) == MOVES
    for move in moves:
        assert move.axes == ("type",)
        lines = move.text.split("\n")
        assert len(lines) == len(base)
        ((old, new),) = [pair for pair in zip(base, lines, strict=True) if pair[0] != pair[1]]
        old_type, name = old.strip().rstrip(";").rsplit(" ", 1)
        new_type, new_name = new.strip().rstrip(";").rsplit(" ", 1)
        assert name == new_name
        assert new_type in search.TYPE_MOVES[old_type]


def test_type_moves_keep_an_initializer_and_a_comment():
    search = reverseapoc.search
    text = "int f(void)\n{\n    int a = 1; /* one */\n\n    return a;\n}\n"
    moves = [move.text for move in search.type_moves(text, search.function_span(text, "f"))]
    assert "int f(void)\n{\n    short a = 1; /* one */\n\n    return a;\n}\n" in moves


def test_type_moves_skip_a_type_outside_the_table():
    search = reverseapoc.search
    text = "int f(void)\n{\n    struct pos a;\n    float b;\n\n    return 0;\n}\n"
    assert list(search.type_moves(text, search.function_span(text, "f"))) == []


def test_type_table_reads_the_local_types_of_our_c():
    table = reverseapoc.search.TYPE_MOVES
    drawn = {"int", "unsigned", "short", "unsigned short", "signed char", "unsigned char"}
    assert set(table) >= drawn | {"char", "s8", "u8", "s16", "u16", "s32", "u32"}
    for local, moves in table.items():
        assert set(moves) <= drawn
        assert local not in moves
    assert "unsigned char" not in table["u8"]  # a typedef of it: no move
    assert "short" not in table["s16"]


def test_moves_add_no_banned_text():
    search = reverseapoc.search
    span = search.function_span(TEXT, A1)
    moves = [*search.type_moves(TEXT, span), *search.statement_moves(TEXT, span),
             *search.scope_moves(TEXT, span), *search.declaration_moves(TEXT, span)]  # fmt: skip
    assert moves
    for move in moves:
        assert batch.refusal(move.text) is None


def test_axes_run_type_then_statement_then_scope_then_declaration():
    assert reverseapoc.search.AXES == ("type", "statement", "scope", "declaration")


def _body(*lines: str) -> str:
    return "int f(int a)\n{\n" + "".join(f"    {line}\n" for line in lines) + "}\n"


def _swapped(lines: list[str], first: int, second: int) -> str:
    moved = list(lines)
    moved[first], moved[second] = moved[second], moved[first]
    return _body(*moved)


def _moves_of(moves, text: str) -> list[str]:
    return [move.text for move in moves(text, reverseapoc.search.function_span(text, "f"))]


def test_statement_moves_swap_adjacent_simple_statements_only():
    lines = ["int b;", "int c;", "", "b = 1;", "c = 2;", "if (a) {", "    b = 3;", "    c = 4;",
             "}", "a = 5;", "top:", "b = 6;", "c = 7;", "for (c = 0; c < 2; c++)", "    b = 8;",
             "c = 9;", "goto top;", "c = 10;", "while (c) {", "    c--;", "}", "c = 11;",
             "return c;"]  # fmt: skip
    text = _body(*lines)
    assert _moves_of(reverseapoc.search.statement_moves, text) == [
        _swapped(lines, 3, 4), _swapped(lines, 6, 7), _swapped(lines, 11, 12)]  # fmt: skip


@pytest.mark.parametrize("lines", [
    ("a = 1;", "switch (a) {", "a = 2;", "}"),
    ("a = 1;", "do {", "a = 2;", "} while (a);"),
    ("if (a) {", "a = 1;", "} else {", "a = 2;", "}"),
    ("a = 1;", "case 1:", "a = 2;"),
    ("a = 1;", "default:", "a = 2;"),
    ("a = 1;", "break;", "a = 2;"),
    ("a = 1;", "continue;", "a = 2;"),
    ("a = 1;", "return 0;", "a = 2;"),
])  # fmt: skip
def test_statement_moves_never_cross_a_control_line(lines):
    assert _moves_of(reverseapoc.search.statement_moves, _body(*lines)) == []


def test_statement_moves_leave_a_statement_split_across_lines():
    text = _body("a = g(a,", "      1);", "a = 2;")
    assert _moves_of(reverseapoc.search.statement_moves, text) == []


def test_statement_moves_leave_the_body_of_a_braceless_if():
    text = _body("if (a)", "    a = 1;", "a = 2;")
    assert _moves_of(reverseapoc.search.statement_moves, text) == []


def test_statement_moves_swap_across_a_comment_and_keep_it_in_place():
    text = _body("a = 1;", "/* why */", "", "a = sizeof(a);")
    assert _moves_of(reverseapoc.search.statement_moves, text) == [
        _body("a = sizeof(a);", "/* why */", "", "a = 1;")]  # fmt: skip


def test_statement_moves_read_a_ternary_as_a_statement():
    text = _body("a = a ? 1 : 2;", "a = 3;")
    assert _moves_of(reverseapoc.search.statement_moves, text) == [
        _body("a = 3;", "a = a ? 1 : 2;")]  # fmt: skip


def test_statement_moves_are_tagged_with_their_axis():
    search = reverseapoc.search
    moves = list(search.statement_moves(TEXT, search.function_span(TEXT, A1)))
    assert moves
    assert {move.axes for move in moves} == {("statement",)}


def test_scope_move_puts_a_declaration_at_the_top_of_the_block_holding_its_uses():
    text = _body("int b;", "int c;", "", "b = a;", "if (a) {", "    int d;", "", "    c = 1;",
                 "    d = c;", "    b = d;", "}", "return b;")  # fmt: skip
    moved = _body("int b;", "", "b = a;", "if (a) {", "    int c;", "    int d;", "", "    c = 1;",
                  "    d = c;", "    b = d;", "}", "return b;")  # fmt: skip
    assert _moves_of(reverseapoc.search.scope_moves, text) == [moved]


def test_scope_move_takes_the_innermost_block_of_all_the_uses():
    text = _body("int c;", "", "if (a) {", "    while (a) {", "        c = 1;", "        a = c;",
                 "    }", "}", "return a;")  # fmt: skip
    moved = _body("", "if (a) {", "    while (a) {", "        int c;", "        c = 1;",
                  "        a = c;", "    }", "}", "return a;")  # fmt: skip
    assert _moves_of(reverseapoc.search.scope_moves, text) == [moved]


def test_scope_move_keeps_a_local_with_a_use_outside_the_block():
    text = _body("int c;", "", "c = 0;", "if (a) {", "    c = 1;", "}", "return c;")
    assert _moves_of(reverseapoc.search.scope_moves, text) == []


def test_scope_move_keeps_a_local_used_in_the_block_header():
    text = _body("int c;", "", "for (c = 0; c < a; c++) {", "    a = c;", "}", "return a;")
    assert _moves_of(reverseapoc.search.scope_moves, text) == []


def test_scope_move_keeps_a_local_with_no_use():
    assert _moves_of(reverseapoc.search.scope_moves, _body("int c;", "", "return a;")) == []


def test_scope_move_leaves_a_block_that_opens_inside_a_line():
    text = _body("int c;", "", "if (a) { c = 1;", "    a = c; }", "return a;")
    assert _moves_of(reverseapoc.search.scope_moves, text) == []


def test_scope_moves_are_tagged_with_their_axis():
    search = reverseapoc.search
    text = _body("int c;", "", "if (a) {", "    c = 1;", "}", "return a;")
    (move,) = search.scope_moves(text, search.function_span(text, "f"))
    assert move.axes == ("scope",)


def test_scope_move_of_an_initialized_local_is_a_statement_move():
    """D-26: moved into a loop, the initializer runs on every iteration."""
    search = reverseapoc.search
    text = _body("int c = 0;", "", "while (a) {", "    c = c + 1;", "    a = c;", "}", "return a;")
    (move,) = search.scope_moves(text, search.function_span(text, "f"))
    assert move.axes == ("scope", "statement")


def test_declaration_moves_lead_with_address_taken_locals_and_aggregates():
    """b is address-taken and d is an array; c and p are neither."""
    search = reverseapoc.search
    lines = TEXT.split("\n")
    names = {5: "b", 6: "c", 7: "p", 8: "d"}
    moves = list(search.declaration_moves(TEXT, search.function_span(TEXT, A1)))
    swaps = []
    for move in moves[:6]:
        changed = [n for n, line in enumerate(move.text.split("\n")) if line != lines[n]]
        swaps.append("".join(names[n] for n in changed))
    assert swaps == ["bd", "bc", "bp", "cd", "pd", "cp"]
    assert {move.axes for move in moves} == {("declaration",)}


def test_declaration_moves_lead_with_a_struct_local():
    search = reverseapoc.search
    text = _body("int b;", "int c;", "struct pos d;", "int *e;", "", "return a;")
    first = next(search.declaration_moves(text, search.function_span(text, "f")))
    assert first.text == _body("struct pos d;", "int c;", "int b;", "int *e;", "", "return a;")


def test_declaration_moves_stay_inside_one_block():
    search = reverseapoc.search
    text = _body("int b;", "int c;", "", "if (a) {", "    int d;", "    int e;", "", "    d = e;",
                 "}", "return b;")  # fmt: skip
    for move in search.declaration_moves(text, search.function_span(text, "f")):
        lines = move.text.split("\n")
        assert {lines[2].strip(), lines[3].strip()} == {"int b;", "int c;"}
        assert {lines[6].strip(), lines[7].strip()} == {"int d;", "int e;"}


def test_declaration_moves_go_on_to_seeded_shuffles_and_end():
    search = reverseapoc.search
    decls = [f"int v{n};" for n in range(5)]
    text = _body(*decls, "", "return a;")
    span = search.function_span(text, "f")
    moves = [move.text for move in search.declaration_moves(text, span)]
    pairs = 10
    assert len(moves) == pairs + search.BUDGET
    assert len(set(moves[pairs:])) > pairs
    assert moves == [move.text for move in search.declaration_moves(text, span)]


def test_declaration_swap_of_two_initializers_is_a_statement_move():
    """D-26: `int b = g(); int c = h();` swapped runs the two calls in the other order."""
    search = reverseapoc.search
    text = _body("int b = g(a);", "int c = h(a);", "", "return b + c;")
    (move, *_shuffled) = search.declaration_moves(text, search.function_span(text, "f"))
    assert move.text == _body("int c = h(a);", "int b = g(a);", "", "return b + c;")
    assert move.axes == ("declaration", "statement")


def test_declaration_swap_across_an_initializer_is_a_statement_move():
    """`b` and `d` swap, and `c`'s initializer now runs before `b`'s."""
    search = reverseapoc.search
    text = _body("int b = 1;", "int c = 2;", "int d;", "", "return b + c + d;")
    span = search.function_span(text, "f")
    moves = {move.text: move.axes for move in search.declaration_moves(text, span)}
    assert moves[_body("int d;", "int c = 2;", "int b = 1;", "", "return b + c + d;")] == (
        "declaration", "statement")  # fmt: skip


def test_declaration_swap_that_keeps_the_order_of_initializers_stays_on_its_axis():
    search = reverseapoc.search
    text = _body("int b = 1;", "int c;", "", "return b + c;")
    (move, *_shuffled) = search.declaration_moves(text, search.function_span(text, "f"))
    assert move.text == _body("int c;", "int b = 1;", "", "return b + c;")
    assert move.axes == ("declaration",)


def test_declaration_shuffles_tag_each_order_by_its_initializers():
    search = reverseapoc.search
    decls = ["int v0 = g(a);", "int v1 = h(a);", "int v2;", "int v3;"]
    text = _body(*decls, "", "return a;")
    moves = list(search.declaration_moves(text, search.function_span(text, "f")))
    pairs = 6
    tagged = {move.axes for move in moves[pairs:]}
    assert tagged == {("declaration",), ("declaration", "statement")}
    for move in moves[pairs:]:
        kept = move.text.index("int v0") < move.text.index("int v1")
        assert ("statement" in move.axes) is not kept


def test_declaration_moves_of_one_declaration_are_none():
    assert _moves_of(reverseapoc.search.declaration_moves, _body("int b;", "", "return a;")) == []


# ---- the search ---------------------------------------------------------------------------------


def test_budget_caps_the_compiles(stubs):
    search = reverseapoc.search
    decls = "".join(f"    int v{n};\n" for n in range(130))  # 650 moves, two jobs each
    result = _run(f"int func_00010000(void)\n{{\n{decls}\n    return 0;\n}}\n")
    assert len(stubs.jobs) == search.BUDGET
    assert result.compiles == search.BUDGET
    assert all(len(wave) <= search.WAVE * 2 for wave in stubs.waves)


def test_each_variant_has_its_own_directory(stubs, type_axis):
    _run()
    directories = [job.src.parent for job in stubs.jobs]
    assert len(set(directories)) == MOVES + 1
    assert len({job.obj for job in stubs.jobs}) == len(stubs.jobs)
    assert directories[0].name == "v0000"
    assert directories[0].parent == reverseapoc.search.OUT / "ufo2p" / f"{START:08x}"


def test_a_cell_equal_to_the_committed_rule_is_dropped(stubs, type_axis):
    result = _run(rule=ONEATX)
    assert len(stubs.jobs) == MOVES + 1
    assert [record["cell"] for record in _records(result)] == [batch.COMMITTED_CELL]


def test_equal_text_is_compiled_once(monkeypatch, stubs, type_axis):
    search = reverseapoc.search
    other = TEXT.replace("    int b;", "    short b;")
    twice = [search.Candidate(TEXT, ("type",)), search.Candidate(other, ("type",)),
             search.Candidate(other, ("type",))]  # fmt: skip
    monkeypatch.setattr(search, "type_moves", lambda _text, _span: iter(twice))
    result = _run()
    assert len(stubs.jobs) == 4  # the base and `other`, under two cells
    assert result.compiles == 4


def test_equal_body_is_judged_once(stubs, type_axis):
    stubs.key = lambda _text, cell: cell
    result = _run()
    assert len(stubs.jobs) == (MOVES + 1) * 2
    assert len(stubs.judged) == 2  # one per distinct body_key
    assert result.bodies == 2


def test_equal_body_reuses_the_verdict(stubs):
    stubs.key = lambda _text, _cell: "one body"
    stubs.decide = lambda _text, _cell: verdict(77.0, 88.0)
    result = _run()
    assert len(stubs.judged) == 1
    assert [record["score"] for record in _records(result)] == [77.0, 77.0]
    assert [record["stack_score"] for record in _records(result)] == [88.0, 88.0]


def test_a_failed_compile_is_not_judged(stubs):
    stubs.compiles = lambda text: "    short b;" not in text
    stubs.decide = lambda text, _cell: verdict(99.0, 99.0) if "short b;" in text else verdict()
    result = _run()
    assert all("    short b;" not in _source(obj)[0] for obj in stubs.judged)
    assert "    short b;" not in result.text


def test_the_base_is_compiled_first_and_comes_back_when_nothing_beats_it(stubs):
    result = _run()
    assert stubs.waves[0][0].src.read_text(encoding="ascii") == TEXT
    assert len(stubs.waves[0]) == 2  # the base alone, under its two cells
    assert result.text == TEXT
    assert result.axes == ()


def test_the_search_starts_from_one_declarator_per_line(stubs):
    text = "int func_00010000(void)\n{\n    int a, b;\n\n    return a;\n}\n"
    result = _run(text)
    assert "    int a;\n    int b;\n" in result.text
    assert stubs.waves[0][0].src.read_text(encoding="ascii") == result.text


def test_a_one_line_function_keeps_its_text_and_has_no_moves(stubs):
    text = "int func_00010000(void) { int a; return 0; }\n"
    result = _run(text)
    assert result.text == text
    assert len(stubs.waves) == 1


def _scored(table: dict[str, batch.Verdict]):
    """A decide function: the verdict of the first line of `table` the text holds."""

    def decide(text: str, _cell: str) -> batch.Verdict:
        return next((v for line, v in table.items() if line in text), verdict())

    return decide


def test_rank_is_exact_then_stack_then_raw(stubs):
    stubs.decide = _scored({"    unsigned b;": verdict(95.0, 60.0),
                            "    short b;": verdict(60.0, 90.0)})  # fmt: skip
    assert "    short b;" in _run().text  # the higher stack score beats the higher raw score


def test_rank_breaks_a_stack_tie_on_the_raw_score(stubs):
    stubs.decide = _scored({"    unsigned b;": verdict(70.0, 90.0),
                            "    short b;": verdict(80.0, 90.0)})  # fmt: skip
    assert "    short b;" in _run().text


def test_rank_puts_exact_first(stubs):
    stubs.decide = _scored({"    unsigned b;": verdict(99.0, 99.0),
                            "    short b;": verdict(exact=True)})  # fmt: skip
    result = _run()
    assert "    short b;" in result.text
    assert result.exact is True
    assert result.axes == ("type",)


def test_a_tie_keeps_the_earlier_variant(stubs):
    stubs.decide = _scored({"    unsigned b;": verdict(70.0, 70.0),
                            "    short b;": verdict(70.0, 70.0)})  # fmt: skip
    assert "    unsigned b;" in _run().text


def test_the_best_cell_ranks_a_variant(stubs):
    """A variant that scores only under the search cell still wins, and its result reads that
    cell's scores."""

    def decide(text: str, cell: str) -> batch.Verdict:
        return verdict(90.0, 95.0) if "    short b;" in text and cell == "cell-1" else verdict()

    stubs.decide = decide
    result = _run()
    assert "    short b;" in result.text
    assert (result.score, result.stack_score) == (90.0, 95.0)


def test_an_exact_variant_ends_the_search(monkeypatch, stubs):
    monkeypatch.setattr(reverseapoc.search, "WAVE", 2)
    stubs.decide = _scored({"    short b;": verdict(exact=True)})
    result = _run()
    assert result.exact is True
    assert len(stubs.waves) == 2  # the base, then the wave with `unsigned b` and `short b`


def test_an_exact_base_compiles_nothing_else(stubs):
    stubs.decide = lambda _text, _cell: verdict(exact=True)
    result = _run()
    assert len(stubs.waves) == 1
    assert result.axes == ()


SWAPPED = "    c = b;\n    b = a + 1;\n"  # the first two statements of TEXT, swapped
DECLS_SWAPPED = "    short c;\n    int b;\n"  # its first two declarations, swapped


def test_statement_variant_with_a_higher_score_is_dropped(stubs):
    """D-26: not the result, and not the next wave's base, whatever its score."""
    stubs.decide = _scored({SWAPPED: verdict(99.0, 99.0)})
    result = _run()
    assert result.text == TEXT
    assert result.axes == ()
    only_the_swap = TEXT.replace("    b = a + 1;\n    c = b;\n", SWAPPED)
    texts = {job.src.read_text(encoding="ascii") for job in stubs.jobs}
    assert only_the_swap in texts
    assert [text for text in texts if SWAPPED in text and text != only_the_swap] == []


def test_a_dropped_statement_variant_does_not_hide_a_lower_standing_one(stubs):
    stubs.decide = _scored({SWAPPED: verdict(99.0, 99.0), DECLS_SWAPPED: verdict(60.0, 60.0)})
    result = _run()
    assert DECLS_SWAPPED in result.text
    assert SWAPPED not in result.text
    assert result.axes == ("declaration",)


def test_statement_variant_that_is_exact_is_kept(stubs):
    stubs.decide = _scored({SWAPPED: verdict(exact=True)})
    result = _run()
    assert result.exact is True
    assert SWAPPED in result.text
    assert "statement" in result.axes


INITIALIZED = """int func_00010000(int a)
{
    int b = g(a);
    int c = h(a);

    if (a) {
        int d = 1;

        a = d;
    }
    return b + c + a;
}
"""
INITIALIZERS_SWAPPED = "    int c = h(a);\n    int b = g(a);\n"


def test_reordered_initializers_are_dropped_unless_exact(stubs):
    """D-26's rule, reached through the declaration axis: not the result, whatever its score."""
    stubs.decide = _scored({INITIALIZERS_SWAPPED: verdict(99.0, 99.0)})
    result = _run(INITIALIZED)
    assert result.text == INITIALIZED
    assert result.axes == ()


def test_reordered_initializers_that_are_exact_are_kept(stubs):
    stubs.decide = _scored({INITIALIZERS_SWAPPED: verdict(exact=True)})
    result = _run(INITIALIZED)
    assert result.exact is True
    assert INITIALIZERS_SWAPPED in result.text
    assert "statement" in result.axes


def test_a_better_variant_becomes_the_base_and_its_axis_repeats(stubs):
    stubs.decide = _scored({"    short b;": verdict(60.0, 60.0)})
    result = _run()
    assert "    short b;" in result.text
    assert result.axes == ("type",)
    both = "    short b;\n    int c;\n"
    assert any(both in job.src.read_text(encoding="ascii") for job in stubs.jobs)


def test_an_axis_that_improved_brings_a_second_round(stubs):
    """A declaration move lands last in the first round, so a type move on it is the second's."""
    stubs.decide = _scored({DECLS_SWAPPED: verdict(60.0, 60.0)})
    _run()
    second = "    int c;\n    int b;\n"
    assert any(second in job.src.read_text(encoding="ascii") for job in stubs.jobs)


def test_axes_name_each_axis_the_winner_moved_along(stubs):
    stubs.decide = _scored({"    short c;\n    short b;\n": verdict(exact=True),
                            "    short b;": verdict(60.0, 60.0)})  # fmt: skip
    result = _run()
    assert result.exact is True
    assert result.axes == ("type", "declaration")
    assert [record["axes"] for record in _records(result)] == [["type", "declaration"]] * 2


def test_no_text_is_compiled_twice_across_rounds(stubs):
    stubs.decide = _scored({DECLS_SWAPPED: verdict(60.0, 60.0),
                            "    short b;": verdict(50.0, 55.0)})  # fmt: skip
    _run()
    committed = [job.src.read_text(encoding="ascii") for job in stubs.jobs
                 if job.src.stem == "committed"]  # fmt: skip
    assert len(committed) == len(set(committed))


def test_same_input_gives_the_same_result(stubs):
    """A drifting tool makes the curve meaningless."""

    def decide(text: str, cell: str) -> batch.Verdict:
        digest = sha256(f"{cell}{text}".encode("ascii")).digest()
        return verdict(float(digest[0] % 90), float(digest[1] % 90))

    stubs.decide = decide
    first = _run()
    second = _run()
    assert first.text == second.text
    assert first.axes == second.axes
    assert first.records == second.records
    assert first.compiles == second.compiles


def test_result_carries_the_slot_map_of_the_winners_best_cell(stubs):
    def decide(text: str, cell: str) -> batch.Verdict:
        return verdict(90.0, 95.0) if "    short b;" in text and cell == "cell-1" else verdict()

    stubs.decide = decide
    result = _run()
    assert result.slots == _slots()
    (obj,) = stubs.slot_objects
    assert obj.stem == "cell-1"
    assert "    short b;" in obj.with_suffix(".c").read_text(encoding="ascii")


def test_best_source_survives_later_waves(monkeypatch, stubs):
    monkeypatch.setattr(reverseapoc.search, "WAVE", 2)
    stubs.decide = _scored({"    unsigned b;": verdict(90.0, 90.0)})
    result = _run()
    assert len(stubs.waves) > 2
    best = result.best.read_text(encoding="ascii")
    assert "    unsigned b;" in best
    assert result.text == best
    assert result.best.name == "best.c"
    assert result.best.parent == reverseapoc.search.OUT / "ufo2p" / f"{START:08x}"
    for record in _records(result):
        assert record["source"] == result.best.resolve().as_posix()
        assert record["source_sha256"] == lf_sha256(best)


def test_results_hold_one_record_per_cell_of_the_winner(stubs):
    stubs.decide = _scored({"    short b;": verdict(90.0, 95.0)})
    result = _run()
    records = _records(result)
    assert [record["cell"] for record in records] == [batch.COMMITTED_CELL, CELL]
    assert [record["flags"] for record in records] == ["-4r -s -fpi", CELL]
    assert list(result.records) == records
    for record in records:
        assert record["exe"] == "ufo2p"
        assert record["address"] == ADDRESS
        assert record["stack_score"] == 95.0
        assert record["axes"] == ["type"]


def test_the_row_output_is_cleared_at_the_start(stubs):
    stale = reverseapoc.search.OUT / "ufo2p" / f"{START:08x}" / "v0099" / "committed.c"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="ascii")
    _run()
    assert not stale.exists()


def test_a_missing_function_leaves_the_row_output_alone(stubs):
    kept = reverseapoc.search.OUT / "ufo2p" / f"{START:08x}" / "best.c"
    kept.parent.mkdir(parents=True)
    kept.write_text("kept", encoding="ascii")
    with pytest.raises(batch.BatchError, match=A1):
        _run("int other(void)\n{\n    return 0;\n}\n")
    assert kept.is_file()
    assert stubs.waves == []


# ---- the route into the D-12 queue (flags.propose_batch on run_search's own file) ---------------


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    """test_flags.batch_repo with batch.REPO_ROOT inside it, so records name build/ paths."""
    made = batch_repo(tmp_path)
    monkeypatch.setattr(batch, "REPO_ROOT", made)
    return made


def _exact_under(cell: str):
    def decide(text: str, cell_file: str) -> batch.Verdict:
        return verdict(exact="    short b;" in text and cell_file == cell)

    return decide


def _queued_run(monkeypatch, repo: Path, cell_file: str, rule: Rule = COMMITTED):
    stubs = Stubs(monkeypatch, repo / "build" / "batch" / "search", _exact_under(cell_file))
    return stubs, _run(rule=rule)


def test_a_search_result_reaches_the_queue(monkeypatch, repo):
    _stubs, result = _queued_run(monkeypatch, repo, "cell-1")
    report = flags.propose_batch(result.best.parent / "results.jsonl", CELL, AUTHOR, repo=repo)
    assert report.added == ("F-0001",)
    (proposal,) = flags.read_queue(queue_of(repo))
    assert proposal.author == AUTHOR
    assert proposal.source == flags.BATCH
    candidate = (repo / proposal.candidate).read_text(encoding="utf-8")
    assert result.best.read_text(encoding="ascii") in candidate
    assert f"INCLUDE_ASM({A1}" not in candidate


def test_a_committed_rule_result_stays_out_of_the_queue(monkeypatch, repo):
    _stubs, result = _queued_run(monkeypatch, repo, "committed")
    assert result.exact is True
    report = flags.propose_batch(result.best.parent / "results.jsonl", CELL, AUTHOR, repo=repo)
    assert report.added == ()
    assert any("not exact under" in reason for reason in report.skipped)
    assert not queue_of(repo).exists()


def test_a_unit_already_on_the_search_cell_has_no_queue_path(monkeypatch, repo):
    _stubs, result = _queued_run(monkeypatch, repo, "committed", ONEATX)
    assert [record["cell"] for record in result.records] == [batch.COMMITTED_CELL]
    with pytest.raises(flags.FlagsError, match=CELL):
        flags.propose_batch(result.best.parent / "results.jsonl", CELL, AUTHOR, repo=repo)
    assert not queue_of(repo).exists()
