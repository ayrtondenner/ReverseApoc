"""config/cflags.txt: the per-file compiler@version and flags table (D-12)."""

from __future__ import annotations

from reverseapoc.cflags import Rule, parse_cflags, select_rule

VERSIONS = ("10.6", "11.0")


def test_star_rule_selects():
    rules = parse_cflags("*  wcc386@10.6  -5r -s\n", versions=VERSIONS)
    # fnmatchcase: `*` crosses `/`, so the default rule matches nested sources.
    assert select_rule(rules, "src/a/b.c") == Rule("*", "wcc386", "10.6", ("-5r", "-s"), 1)
    assert rules[0].spec == "wcc386@10.6"


def test_last_matching_rule_wins():
    text = "*  wcc386@10.6  -5r -s\nsrc/b*.c  wcc386@11.0  -3r\n"
    rules = parse_cflags(text, versions=VERSIONS)
    b1 = select_rule(rules, "src/b1.c")
    assert (b1.version, b1.flags, b1.lineno) == ("11.0", ("-3r",), 2)
    a = select_rule(rules, "src/a.c")
    assert (a.version, a.flags, a.lineno) == ("10.6", ("-5r", "-s"), 1)


def test_comments_and_blank_lines_ignored():
    text = "# header comment\n\n*  wcc386@10.6  -5r -s   # the default\n   \n# trailing\n"
    rules = parse_cflags(text, versions=VERSIONS)
    assert rules == [Rule("*", "wcc386", "10.6", ("-5r", "-s"), 3)]
