"""config/cflags.txt: the per-file compiler@version and flags table (D-12)."""

from __future__ import annotations

import pytest

from reverseapoc.cflags import CflagsError, Rule, load_cflags, parse_cflags, select_rule

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


# 2. validation: every error names the file and the line ---------------------------------------


def _refused(text: str) -> str:
    with pytest.raises(CflagsError) as info:
        parse_cflags(text, versions=VERSIONS, where="my/cflags.txt")
    return str(info.value)


def test_first_rule_must_be_star():
    message = _refused("# comment\nsrc/*.c  wcc386@10.6  -5r\n")
    assert message.startswith("my/cflags.txt:2:")
    assert "src/*.c" in message


def test_unknown_compiler_and_version():
    message = _refused("*  wcc999@10.6  -5r\n")
    assert message.startswith("my/cflags.txt:1:")
    assert "wcc999" in message
    message = _refused("*  wcc386@10.6  -5r\nsrc/a.c  wcc386@9.9  -5r\n")
    assert message.startswith("my/cflags.txt:2:")
    assert "9.9" in message
    assert "10.6" in message and "11.0" in message  # the known versions


@pytest.mark.parametrize("line", ["*  wcc386  -5r", "*", "*  @10.6", "*  wcc386@"])
def test_missing_at_sign_or_fields(line):
    assert _refused(line + "\n").startswith("my/cflags.txt:1:")


@pytest.mark.parametrize(
    "flag",
    ["-zq", "-zld", "-bt=nt", "-fo=x.obj", "-fr=x.err", "-fi=x.h", "-fh", "-ad=x.d", "-i=C:\\x"],
)
def test_wrapper_owned_flags_refused(flag):
    message = _refused(f"*  wcc386@10.6  -5r {flag}\n")
    assert message.startswith("my/cflags.txt:1:")
    assert flag in message
    assert "wrapper" in message


@pytest.mark.parametrize("flag", ["5r", "-dX=a/b", "-dX=a\\b"])
def test_bad_flag_shapes_refused(flag):
    message = _refused(f"*  wcc386@10.6  {flag}\n")
    assert message.startswith("my/cflags.txt:1:")
    assert flag in message


def test_flags_that_only_share_a_prefix_are_allowed():
    # "-i" is wrapper-owned only as "-i" or "-i=..."; "-fpi" and "-zp4" are ordinary flags.
    rules = parse_cflags("*  wcc386@10.6  -fpi -zp4 -ix\n", versions=VERSIONS)
    assert rules[0].flags == ("-fpi", "-zp4", "-ix")


def test_unmatched_source_refused():
    with pytest.raises(CflagsError, match="'a.c'"):
        select_rule([], "a.c")
    with pytest.raises(CflagsError, match="'a.c'"):
        select_rule([Rule("src/*.c", "wcc386", "10.6", ("-5r",), 1)], "a.c")


def test_glob_is_case_sensitive():
    rules = parse_cflags("*  wcc386@10.6  -5r\nSRC/*.c  wcc386@11.0  -3r\n", versions=VERSIONS)
    assert select_rule(rules, "src/a.c").version == "10.6"
    assert select_rule(rules, "SRC/a.c").version == "11.0"


def test_load_cflags_names_the_file(tmp_path):
    path = tmp_path / "cflags.txt"
    path.write_text("*  wcc386@10.6  -zq\n", encoding="utf-8")
    with pytest.raises(CflagsError) as info:
        load_cflags(path, versions=VERSIONS)
    assert str(info.value).startswith(f"{path}:1:")


def test_default_cflags_parses_against_the_default_manifest():
    rules = load_cflags()
    assert rules[0].glob == "*"
    assert rules[0].spec.startswith("wcc386@")
