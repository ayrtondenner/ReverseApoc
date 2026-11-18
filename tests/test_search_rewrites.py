"""`reverseapoc search`'s rewrite axis: Echo's branch, loop and expression rewrites that keep the
meaning of the C (todo search-rewrite-axis). Pure functions on text: no compiler runs here, and
the C below is made up.
"""

from __future__ import annotations

import pytest

from reverseapoc import search

NAME = "func_00010000"


def _fn(*body: str, params: str = "int a, int b") -> str:
    return "\n".join([f"int {NAME}({params})", "{", *body, "}", ""])


def _moves(text: str) -> list[search.Candidate]:
    return list(search.rewrite_moves(text, search.function_span(text, NAME)))


def _texts(text: str) -> list[str]:
    return [move.text for move in _moves(text)]


def _one_line_moves(text: str) -> set[str]:
    """The line each move changed, for moves that change one line in place."""
    before = text.split("\n")
    changed = set()
    for moved in _texts(text):
        after = moved.split("\n")
        if len(after) != len(before):
            continue
        changed.update(new for old, new in zip(before, after, strict=True) if old != new)
    return changed


# ---- expressions ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "swapped"),
    [
        ("    x = a + b;", "    x = b + a;"),
        ("    x = a * b;", "    x = b * a;"),
        ("    x = a & b;", "    x = b & a;"),
        ("    x = a | 3;", "    x = 3 | a;"),
        ("    x = a ^ b;", "    x = b ^ a;"),
        ("    if (a < b) {", "    if (b > a) {"),
        ("    if (a <= b) {", "    if (b >= a) {"),
        ("    if (a > 0x10) {", "    if (0x10 < a) {"),
        ("    if (a >= b) {", "    if (b <= a) {"),
        ("    if (a == b) {", "    if (b == a) {"),
        ("    if (a != b) {", "    if (b != a) {"),
        ("    return p->n + q.m;", "    return q.m + p->n;"),
        ("    x = v[1] + v[a];", "    x = v[a] + v[1];"),
        ("    x = f(a, b + 1);", "    x = f(a, 1 + b);"),
        ("    if (a < b + 1) {", "    if (a < 1 + b) {"),
        ("    if (a + 1 < b) {", "    if (1 + a < b) {"),
        ("    x = a + b - c;", "    x = b + a - c;"),
    ],
)
def test_an_operand_swap_mirrors_a_comparison_and_keeps_a_commutative_operator(line, swapped):
    body = [line, "        x = 0;", "    }"] if line.endswith("{") else [line]
    assert swapped in _one_line_moves(_fn("    int x;", *body))


@pytest.mark.parametrize(
    "line",
    [
        "    x = a - b;",  # not commutative
        "    x = a / b;",
        "    x = *p + b;",  # the operand is `*p`, which no swap reads
        "    x = -a + b;",
        "    x = &a + b;",
        "    x = c - a + b;",  # `a + b` is no operand of its own here
        "    x = a * b + c * d;",
        "    x = a + b * c;",
        "    x = f(a) + b;",
        "    x = a + COUNT;",  # a macro may hide an operator
        "    x = (int)a + b;",
        "    x = a +",
    ],
)
def test_an_operand_swap_reads_only_what_binds_as_one_operand(line):
    text = _fn("    int x;", line, *(["        b;"] if line.endswith("+") else []))
    swapped = {new.strip() for new in _one_line_moves(text)}
    if line == "    x = a * b + c * d;":
        assert swapped == {"x = b * a + c * d;", "x = a * b + d * c;"}
    elif line == "    x = a + b * c;":
        assert swapped == {"x = a + c * b;"}
    else:
        assert swapped == set()


def test_an_operand_swap_skips_comments_literals_and_declarations():
    text = _fn("    int x = a + b;", '    puts("a + b"); /* a + b */')
    assert _one_line_moves(text) == set()


def test_an_operand_swap_keeps_the_comment_of_its_line():
    text = _fn("    int x;", "    x = a + b; /* sum */")
    assert "    x = b + a; /* sum */" in _one_line_moves(text)


@pytest.mark.parametrize(
    ("line", "regrouped"),
    [
        ("    x = a + b + c;", "    x = a + (b + c);"),
        ("    x = a * b * 2;", "    x = a * (b * 2);"),
        ("    x = a + (b + c);", "    x = a + b + c;"),
        ("    x = p & q & r;", "    x = p & (q & r);"),
        ("    x = p | (q | r);", "    x = p | q | r;"),
    ],
)
def test_reassociation_regroups_a_chain_of_one_operator(line, regrouped):
    params = "int a, int b, int c, unsigned p, unsigned q, unsigned r"
    assert regrouped in _one_line_moves(_fn("    int x;", line, params=params))


@pytest.mark.parametrize(
    "line",
    [
        "    x = f + b + c;",  # a float does not reassociate
        "    x = a + g + c;",  # nor does a name the function does not declare
        "    x = s + b + c;",  # nor a pointer
        "    x = a + b + c * 2;",
        "    x = a - b - c;",
        "    x = a + (b + c) * 2;",
        "    x = a + (b - c);",
    ],
)
def test_reassociation_needs_integers_and_one_operator(line):
    text = _fn("    int x;", "    float f;", "    int *s;", line, params="int a, int b, int c")
    assert all(new.count("(") == line.count("(") for new in _one_line_moves(text))


# ---- branches -------------------------------------------------------------------------------

IF_ELSE = ["    if (a) {", "        x = 1;", "    } else {", "        x = 2;", "    }",
           "    return x;"]  # fmt: skip


def test_if_else_swap_inverts_the_condition_and_swaps_the_bodies():
    expected = ["    if (!(a)) {", "        x = 2;", "    } else {", "        x = 1;", "    }",
                "    return x;"]  # fmt: skip
    assert _fn("    int x;", *expected) in _texts(_fn("    int x;", *IF_ELSE))


@pytest.mark.parametrize(
    ("condition", "inverted"),
    [("!a", "a"), ("!(a && b)", "a && b"), ("a == b", "a != b"), ("a != b", "a == b"),
     ("a < b", "!(a < b)"), ("a && b", "!(a && b)"), ("p->n == 0", "p->n != 0")],
)  # fmt: skip
def test_if_else_swap_inverts_without_changing_the_meaning(condition, inverted):
    lines = [f"    if ({condition}) {{", *IF_ELSE[1:]]
    swapped = [f"    if ({inverted}) {{", "        x = 2;", "    } else {", "        x = 1;",
               "    }", "    return x;"]  # fmt: skip
    assert _fn("    int x;", *swapped) in _texts(_fn("    int x;", *lines))


def test_if_else_swap_leaves_an_else_if_chain_and_a_governed_if():
    chain = ["    if (a) {", "        x = 1;", "    } else if (b) {", "        x = 2;", "    }",
             "    return x;"]  # fmt: skip
    governed = ["    while (b)", *IF_ELSE[:5], "    return x;"]
    for body in (chain, governed):
        assert not any("!(" in moved for moved in _texts(_fn("    int x;", *body)))


RETURNS = ["    if (a) {", "        x = 1;", "        return x;", "    } else {", "        x = 2;",
           "    }", "    return x;"]  # fmt: skip


def test_an_else_after_a_return_is_dropped():
    dropped = ["    if (a) {", "        x = 1;", "        return x;", "    }", "        x = 2;",
               "    return x;"]  # fmt: skip
    assert _fn("    int x;", *dropped) in _texts(_fn("    int x;", *RETURNS))


def test_an_else_is_not_dropped_after_a_return_something_governs():
    lines = ["    if (a) {", "        if (b)", "            return 1;", "    } else {",
             "        x = 2;", "    }", "    return x;"]  # fmt: skip
    dropped = [*lines[:3], "    }", *lines[4:5], "    return x;"]
    assert _fn("    int x;", *dropped) not in _texts(_fn("    int x;", *lines))


def test_an_else_holding_a_declaration_is_not_dropped():
    lines = [*RETURNS[:4], "        int y;", "", "        y = 2;", "        x = y;", *RETURNS[5:]]
    assert not any(len(moved.split("\n")) < len(_fn("    int x;", *lines).split("\n"))
                   for moved in _texts(_fn("    int x;", *lines)))  # fmt: skip


def test_the_rest_of_a_block_after_a_return_moves_into_an_else():
    lines = ["    if (a) {", "        return 1;", "    }", "    x = 2;", "    return x;"]
    nested = ["    if (a) {", "        return 1;", "    } else {", "    x = 2;", "    return x;",
              "    }"]  # fmt: skip
    assert _fn("    int x;", *nested) in _texts(_fn("    int x;", *lines))


def test_no_else_is_added_past_a_case_label_or_before_an_else():
    in_switch = ["    switch (b) {", "    case 1:", "        if (a) {", "            return 1;",
                 "        }", "        x = 2;", "    case 2:", "        x = 3;", "    }",
                 "    return x;"]  # fmt: skip
    has_else = ["    if (a) {", "        return 1;", "    }", "    else {", "        x = 2;",
                "    }", "    return x;"]  # fmt: skip
    for lines in (in_switch, has_else):
        assert not any("} else {" in moved for moved in _texts(_fn("    int x;", *lines)))


# ---- loops ----------------------------------------------------------------------------------

WHILE = ["    while (a < b) {", "        a++;", "    }", "    return a;"]


def test_a_while_becomes_a_for_and_a_guarded_do_while():
    texts = _texts(_fn(*WHILE))
    assert _fn("    for (; a < b;) {", *WHILE[1:]) in texts
    guarded = ["    if (a < b) {", "    do {", "        a++;", "    } while (a < b);", "    }",
               "    return a;"]  # fmt: skip
    assert _fn(*guarded) in texts


@pytest.mark.parametrize(
    ("loop", "other"),
    [("    for (; a < b;) {", "    while (a < b) {"), ("    for (;;) {", "    while (1) {"),
     ("    while (1) {", "    for (;;) {")],
)  # fmt: skip
def test_a_for_with_only_a_condition_and_a_while_change_places(loop, other):
    assert _fn(other, *WHILE[1:]) in _texts(_fn(loop, *WHILE[1:]))


def test_a_full_for_becomes_its_init_then_a_while_with_its_step():
    loop = ["    for (a = 0; a < b; a++) {", "        g(a);", "    }", "    return a;"]
    unrolled = ["    a = 0;", "    while (a < b) {", "        g(a);", "        a++;", "    }",
                "    return a;"]  # fmt: skip
    assert _fn(*unrolled) in _texts(_fn(*loop))
    assert _fn(*loop) in _texts(_fn(*unrolled))


def test_a_loop_holding_a_continue_keeps_its_step_in_its_header():
    loop = ["    for (a = 0; a < b; a++) {", "        if (a == 3)", "            continue;",
            "        g(a);", "    }", "    return a;"]  # fmt: skip
    assert not any("while (a < b)" in moved for moved in _texts(_fn(*loop)))


def test_a_step_is_not_moved_where_a_local_of_the_body_would_take_its_name():
    """Review finding: the body's own `k` would capture the step's."""
    loop = ["    for (a = 0; a < b; a += k) {", "        int k;", "", "        k = 2;",
            "        g(k);", "    }", "    return a;"]  # fmt: skip
    assert not any("while (a < b)" in moved for moved in _texts(_fn("    int k;", *loop)))
    unrolled = ["    x = 0;", "    while (a < b) {", "        int t;", "", "        t = g(a);",
                "        x = x + t;", "    }", "    return x;"]  # fmt: skip
    assert not any("for (x = 0" in moved for moved in _texts(_fn("    int x;", *unrolled)))


def test_a_governed_while_gets_no_guard():
    """Review finding: an `if` added under a braceless `if` would take the `else` after it."""
    lines = ["    if (b)", *WHILE[:3], "    else", "        a = 2;", "    return a;"]
    assert not any("do {" in moved for moved in _texts(_fn(*lines)))


@pytest.mark.parametrize(
    ("condition", "inverted"),
    [("!(a && b) /* note */", "a && b"), ("/* c */ !a", "a"), ("a == b /* c */", "a != b")],
)  # fmt: skip
def test_a_comment_in_a_condition_leaves_its_inversion_whole(condition, inverted):
    lines = [f"    if ({condition}) {{", *IF_ELSE[1:]]
    swapped = [f"    if ({inverted}) {{", "        x = 2;", "    } else {", "        x = 1;",
               "    }", "    return x;"]  # fmt: skip
    assert _fn("    int x;", *swapped) in _texts(_fn("    int x;", *lines))


def test_block_rewrites_come_before_expression_rewrites():
    """Echo's rules aim at block order and loop shape first; a budget may end the axis early."""
    axes = [move.text for move in _moves(_fn("    int x;", "    x = a + b;", *IF_ELSE))]
    first_swap = next(n for n, text in enumerate(axes) if "x = b + a;" in text)
    assert any("!(a)" in text for text in axes[:first_swap])


def test_a_governed_for_is_not_split():
    loop = ["    if (b)", "        for (a = 0; a < b; a++) {", "            g(a);", "        }",
            "    return a;"]  # fmt: skip
    assert not any("while (a < b)" in moved for moved in _texts(_fn(*loop)))


# ---- ternaries ------------------------------------------------------------------------------


def test_an_if_else_of_one_assignment_becomes_a_ternary_and_back():
    ternary = ["    x = a ? 1 : (b + 1);", "    return x;"]
    branches = ["    if (a) {", "        x = 1;", "    } else {", "        x = b + 1;", "    }",
                "    return x;"]  # fmt: skip
    found = {move.text: move.axes for move in _moves(_fn("    int x;", *branches))}
    assert found[_fn("    int x;", *ternary)] == ("rewrite", "statement")
    back = {move.text: move.axes for move in _moves(_fn("    int x;", *ternary))}
    assert back[_fn("    int x;", *branches[:3], "        x = (b + 1);", *branches[4:])] == (
        "rewrite", "statement")


def test_a_braceless_if_else_of_one_assignment_becomes_a_ternary():
    branches = ["    if (a)", "        x = 1;", "    else", "        x = 2;", "    return x;"]
    assert _fn("    int x;", "    x = a ? 1 : 2;", "    return x;") in _texts(
        _fn("    int x;", *branches))


def test_no_ternary_from_two_targets_or_a_comma():
    two = ["    if (a) {", "        x = 1;", "    } else {", "        y = 2;", "    }",
           "    return x;"]  # fmt: skip
    comma = ["    x = a ? 1 : 2, y = 3;", "    return x;"]
    for lines in (two, comma):
        assert not any(move.axes == ("rewrite", "statement")
                       for move in _moves(_fn("    int x;", "    int y;", *lines)))  # fmt: skip


# ---- the axis -------------------------------------------------------------------------------


def test_meaning_keeping_rewrites_are_tagged_with_their_axis_alone():
    axes = {move.axes for move in _moves(_fn("    int x;", *IF_ELSE))}
    assert ("rewrite",) in axes
    assert axes <= {("rewrite",), ("rewrite", "statement")}


def test_rewrites_keep_the_other_functions_and_every_brace():
    text = "int other(int a)\n{\n    return a + 1;\n}\n\n" + _fn("    int x;", *IF_ELSE, *WHILE[:3])
    for moved in _texts(text):
        assert moved.startswith("int other(int a)\n{\n    return a + 1;\n}\n")
        assert moved.count("{") == moved.count("}")
        assert search.function_span(moved, NAME)


def test_rewrites_are_the_same_on_every_run():
    text = _fn("    int x;", *IF_ELSE, *WHILE[:3])
    assert _texts(text) == _texts(text)
