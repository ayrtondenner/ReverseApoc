"""readlint (DEC-04, D-20, D-21, D-30, backlog 999.2): the readability linter for matched units.

Every test writes made-up C into a tmp_path src/ tree beside a synthetic config/ tree (status.csv
marking the unit matched, functions.csv, symbols.csv when a test renames a row). No game bytes.
Files are written as bytes so the host never translates line ends.
"""

from __future__ import annotations

import json

import pytest

from conftest import REPO_ROOT
from reverseapoc import readlint
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, SymbolRow, write_functions_csv, write_symbols_csv
from reverseapoc.mechanics import MEMBERS_CSV, MemberRow, write_members
from reverseapoc.readlint import ReadlintError, run_readlint
from reverseapoc.status import MATCHED, PARTIAL, StatusRow, read_status, status_path, write_status

EXE = "ufo2p"
UNIT = "u_00010000"
F1 = 0x00010000  # the unit's matched function
F2 = 0x00010040  # a second row of the unit
SHA = "ab" * 32
DATE = "2026-10-27"
EXE_FILE = "UFO2P.EXE"

GOOD_HEADER = """/*
 * tick_count: returns the current tick count.
 * Address: UFO2P.EXE 0x00010000
 * Evidence: call: read by the timer loop
 */
"""
CLEAN = '#include "common.h"\n\n' + GOOD_HEADER + "int tick_count(void)\n{\n    return 0;\n}\n"
PLACEHOLDERS = ("FUN_1234", "sub_1234", "DAT_1234", "LAB_1234", "PTR_1234", "UNK_1234",
                "func_0001ABCD", "D_0001ABCD")  # fmt: skip


def write_tree(tmp_path, text, *, unit=UNIT, exe=EXE, status=MATCHED, symbols=(), data=None):
    """src/<exe>/<unit>.c holding `text` (or the bytes `data`), and config/<exe>/ with two game
    rows of the unit, a status row for F1 (none when status is None) and `symbols`."""
    src, config = tmp_path / "src", tmp_path / "config"
    path = src / exe / f"{unit}.c"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8") if data is None else data)
    rows = [FunctionRow(F1, F2, f"func_{F1:08X}", "game", unit, "call"),
            FunctionRow(F2, F2 + 0x10, f"func_{F2:08X}", "game", unit, "call")]  # fmt: skip
    write_functions_csv(config / exe / "functions.csv", rows, f"{exe.upper()}.EXE")
    if symbols:
        write_symbols_csv(config / exe / "symbols.csv", symbols, f"{exe.upper()}.EXE")
    if status is not None:
        percent = 100.0 if status == MATCHED else 50.0
        row = StatusRow(F1, f"func_{F1:08X}", unit, status, percent, 1, SHA, DATE)
        write_status(status_path(config, exe), [row])
    return src, config, path


def lint(tmp_path, text, **kwargs):
    tree = {k: kwargs.pop(k) for k in ("unit", "exe", "status", "symbols", "data") if k in kwargs}
    src, config, _path = write_tree(tmp_path, text, **tree)
    return run_readlint([src], src_root=src, config_root=config, **kwargs)


def hits(result, rule):
    """(line, message) of every violation of `rule`."""
    return [(v.line, v.message) for v in result.violations if v.rule == rule]


TICK = SymbolRow(F1, "tick_count_", "func")


# ---- Task 1: tokenizer, structure and RL01 through the verb ----


FORMS = {  # form -> (C text with {n} for the name, the line the name is on)
    "definition": ("/* x */\nvoid {n}(void)\n{{\n}}\n", 2),
    "prototype": ("void {n}(void);\n", 1),
    "extern": ("extern int {n};\n", 1),
    "use": ("int g(void)\n{{\n    return {n};\n}}\n", 3),
}


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("name", PLACEHOLDERS)
def test_rl01_each_pattern(tmp_path, name, form):
    text, line = FORMS[form]
    result = lint(tmp_path, text.format(n=name))
    assert [ln for ln, _m in hits(result, "RL01")] == [line]
    assert name in hits(result, "RL01")[0][1]
    assert f"src/{EXE}/{UNIT}.c:{line}: RL01" in result.format()


@pytest.mark.parametrize("name", PLACEHOLDERS)
def test_rl01_exempt_contexts(tmp_path, name):
    text = (f'#include "common.h"\n\nINCLUDE_ASM({name});\n/* {name} is not named yet */\n'
            f'char *s = "{name}";\nint c = \'x\';\n#if 0\nvoid {name}(void);\n#else\n'
            f"int ok;\n#endif\n")  # fmt: skip
    assert hits(lint(tmp_path, text), "RL01") == []


def test_rl01_in_a_directive(tmp_path):
    result = lint(tmp_path, "#define TICK func_0001ABCD\n")
    assert [ln for ln, _m in hits(result, "RL01")] == [1]


def test_rl01_case_exact(tmp_path):
    result = lint(tmp_path, "void func_000a3980(void);\nvoid func_000A3980(void);\n")
    assert [ln for ln, _m in hits(result, "RL01")] == [2]


def test_rl01_across_a_splice(tmp_path):
    result = lint(tmp_path, "int a;\nvoid func_0001\\\nABCD(void);\nint b;\n")
    assert [ln for ln, _m in hits(result, "RL01")] == [2]


def test_unmatched_unit_skipped(tmp_path):
    for status in (PARTIAL, None):
        result = lint(tmp_path, "void func_0001ABCD(void);\n", status=status)
        assert result.files_checked == ()
        assert [s.path for s in result.skipped] == [f"src/{EXE}/{UNIT}.c"]
        assert result.violations == ()
        assert result.exit_code() == 0


def test_file_outside_exe_dirs_skipped(tmp_path):
    src, config, _path = write_tree(tmp_path, CLEAN, symbols=[TICK])
    (src / "stray.c").write_bytes(b"void func_0001ABCD(void);\n")
    result = run_readlint([src], src_root=src, config_root=config)
    assert "src/stray.c" in [s.path for s in result.skipped]
    assert result.files_checked == (f"src/{EXE}/{UNIT}.c",)


TOOL_ERRORS = {
    "ifdef": ("#ifdef X\nint a;\n#endif\n", None, "#ifdef"),
    "lone-cr": (None, b"int a;\rint b;\n", "carriage return"),
    "not-utf8": (None, b"int a; /* \xff */\n", "UTF-8"),
}


@pytest.mark.parametrize("case", TOOL_ERRORS)
def test_tool_errors(tmp_path, capsys, case):
    text, data, why = TOOL_ERRORS[case]
    src, config, _path = write_tree(tmp_path, text or "", data=data)
    with pytest.raises(ReadlintError, match=why):
        run_readlint([src], src_root=src, config_root=config)
    argv = ["readlint", str(src), "--src", str(src), "--config", str(config)]
    assert cli_main(argv) == 2
    err = capsys.readouterr().err
    assert f"{UNIT}.c" in err and why in err


def test_cli_exit_codes(tmp_path, capsys):
    src, config, path = write_tree(tmp_path, CLEAN, symbols=[TICK])
    argv = ["readlint", "--src", str(src), "--config", str(config)]
    assert cli_main(argv) == 0
    capsys.readouterr()
    path.write_bytes((CLEAN + "void func_0001ABCD(void);\n").encode("ascii"))
    assert cli_main(argv) == 1
    out = capsys.readouterr().out
    assert f"src/{EXE}/{UNIT}.c:12: RL01" in out
    assert cli_main([*argv, "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    for key in ("files_checked", "skipped", "violations", "waivers", "allowlisted"):
        assert key in data
    assert data["files_checked"] == [f"src/{EXE}/{UNIT}.c"]
    assert data["violations"] == [{"path": f"src/{EXE}/{UNIT}.c", "line": 12, "rule": "RL01",
                                   "message": data["violations"][0]["message"]}]  # fmt: skip


def test_help_lists_options(capsys):
    with pytest.raises(SystemExit):
        cli_main(["readlint", "--help"])
    out = capsys.readouterr().out
    for option in ("--units", "--tier", "--report", "--src", "--config", "--json"):
        assert option in out


def test_placeholder_is_proposals():
    from reverseapoc import proposals

    assert readlint.PLACEHOLDER is proposals.PLACEHOLDER


# ---- Task 2: RL02-RL06, the tagged waiver and floats in report mode ----


def in_function(statements: str, prefix: str = "") -> str:
    """A matched unit whose one definition, tick_count (renamed F1), holds `statements`."""
    head = f'#include "common.h"\n\n{prefix}{GOOD_HEADER}int tick_count(int x, int *a, int i)\n'
    return f"{head}{{\n    {statements}\n    return 0;\n}}\n"


def test_clean_unit_has_no_violation(tmp_path):
    result = lint(tmp_path, CLEAN, symbols=[TICK])
    assert result.violations == ()
    assert result.files_checked == (f"src/{EXE}/{UNIT}.c",)


def test_rl02_no_comment(tmp_path):
    text = '#include "common.h"\n\nint tick_count(void)\n{\n    return 0;\n}\n'
    result = lint(tmp_path, text, symbols=[TICK])
    assert [ln for ln, _m in hits(result, "RL02")] == [3]


def test_rl02_comment_separated_by_a_declaration(tmp_path):
    text = (f'#include "common.h"\n\n{GOOD_HEADER}int other;\n'
            "int tick_count(void)\n{\n    return 0;\n}\n")  # fmt: skip
    result = lint(tmp_path, text, symbols=[TICK])
    assert [ln for ln, _m in hits(result, "RL02")] == [9]
    assert hits(result, "RL03") == []


def test_rl02_comment_inside_the_declaration_is_not_a_header(tmp_path):
    text = '#include "common.h"\n\nint /* tick_count: a b c */ tick_count(void)\n{\n}\n'
    assert [ln for ln, _m in hits(lint(tmp_path, text, symbols=[TICK]), "RL02")] == [3]


BAD_HEADERS = {
    "wrong-name": ("tick_count: returns", "other_count: returns"),
    "two-word-purpose": ("returns the current tick count.", "returns count."),
    "no-purpose": ("tick_count: returns the current tick count.", "tick_count returns ticks"),
    "wrong-exe": ("UFO2P.EXE 0x00010000", "TACP.EXE 0x00010000"),
    "wrong-address": ("UFO2P.EXE 0x00010000", "UFO2P.EXE 0x00010040"),
    "lower-case-address": ("UFO2P.EXE 0x00010000", "UFO2P.EXE 0x0001000a"),
    "no-address": (" * Address: UFO2P.EXE 0x00010000\n", ""),
    "two-addresses": (" * Address: UFO2P.EXE 0x00010000\n",
                      " * Address: UFO2P.EXE 0x00010000\n * Address: UFO2P.EXE 0x00010000\n"),
    "evidence-kind": ("Evidence: call:", "Evidence: wiki:"),
    "empty-evidence": ("Evidence: call: read by the timer loop", "Evidence: call:"),
    "blank-evidence": ("Evidence: call: read by the timer loop", "Evidence: call:    "),
    "no-evidence": (" * Evidence: call: read by the timer loop\n", ""),
}  # fmt: skip


@pytest.mark.parametrize("case", BAD_HEADERS)
def test_rl03(tmp_path, case):
    old, new = BAD_HEADERS[case]
    assert old in CLEAN
    result = lint(tmp_path, CLEAN.replace(old, new), symbols=[TICK])
    assert hits(result, "RL03"), result.format()
    assert hits(result, "RL02") == []


def test_rl03_placeholder_row_and_second_evidence(tmp_path):
    header = ("/*\n * func_00010040: clears the second counter value.\n"
              " * Address: UFO2P.EXE 0x00010040\n * Evidence: string: 0x0012EFAC\n"
              " * Evidence: vocab: Agent\n */\n")  # fmt: skip
    text = f"{header}void func_00010040(void)\n{{\n}}\n"
    result = lint(tmp_path, text)
    assert hits(result, "RL03") == []
    assert [ln for ln, _m in hits(result, "RL01")] == [7]


def test_rl03_name_with_no_row(tmp_path):
    text = CLEAN.replace("tick_count", "helper_count")
    result = lint(tmp_path, text, symbols=[TICK])
    assert any("helper_count" in m for _ln, m in hits(result, "RL03"))


def test_rl03_tacp_unit(tmp_path):
    text = CLEAN.replace("UFO2P.EXE", "TACP.EXE")
    symbols = [SymbolRow(F1, "tick_count_", "func")]
    assert lint(tmp_path, text, exe="tacp", symbols=symbols).violations == ()


def test_rl04(tmp_path):
    text = ("struct S { int unk_4; int field_0x8; char pad[2]; int ok; };\n"
            "struct T { int padding_end; };\nstruct U { int paddle; int gaps2; };\n"
            "union V { struct { int unk; } inner; long filler, undefined1; };\n"
            "typedef struct { int Unknown; int fieldOfView; } W;\n")  # fmt: skip
    result = lint(tmp_path, text)
    found = sorted(m.split()[0] for _ln, m in hits(result, "RL04"))
    assert found == sorted(["unk_4", "field_0x8", "pad", "padding_end", "unk", "filler",
                            "undefined1", "Unknown"])  # fmt: skip


def test_rl04_in_a_function(tmp_path):
    result = lint(tmp_path, in_function("struct { int gap_0; } s;"), symbols=[TICK])
    assert [m.split()[0] for _ln, m in hits(result, "RL04")] == ["gap_0"]


RL05 = {
    "*(int *)(a + 0x10)": 1,
    "(short *)((char *)a + 16)": 1,
    "*(int *)(a - 4)": 1,
    "*(unsigned char *)(a + 2 + i)": 1,
    "*(int *)a": 0,
    "(T *)q": 0,
    "*(int *)(a + i)": 0,
    "*(int *)(a + 0)": 0,
    "(int)(x + 4)": 0,
    "f(a * 4)": 0,
}


@pytest.mark.parametrize("expr", RL05)
def test_rl05(tmp_path, expr):
    result = lint(tmp_path, in_function(f"x = {expr};"), symbols=[TICK])
    assert len(hits(result, "RL05")) == RL05[expr]


RL06 = [  # (file-scope prefix, statement, RL06 violations, waivers)
    ("", "x = 36;", 1, 0),
    ("", "switch (x) { case 36: break; }", 1, 0),
    ("", "f(4);", 1, 0),
    ("", "x = a[i * 4];", 0, 0),
    ("", "x = a[4];", 0, 0),
    ("", "x = x & 0xFF;", 0, 0),
    ("", "x = x & 0xF0;", 1, 0),
    ("", "x &= 0xFFFFFF00;", 0, 0),
    ("", "x = ~0x7;", 0, 0),
    ("", "x = x << 3;", 0, 0),
    ("", "x = x << 32;", 1, 0),
    ("", "x = 4 << i;", 0, 0),
    ("", "x = x * 3;", 1, 0),
    ("", "x = x * 4;", 0, 0),
    ("", "x = 8 + i;", 0, 0),
    ("", "x = -4;", 1, 0),
    ("", "x = -1;", 0, 0),
    ("", "x = 0;", 0, 0),
    ("", "x = 1u;", 0, 0),
    ("#define TICKS 36\n", "x = TICKS;", 0, 0),
    ("enum { TICKS = 36 };\n", "x = TICKS;", 0, 0),
    ("", "x = 36; /* lit: ticks per game second */", 0, 1),
    ("", "x = 36; /* ticks per game second */", 1, 0),
    ("", "x = 36; /* lit: */", 1, 0),
    ("", "x = 'A';", 0, 0),
]


@pytest.mark.parametrize(("prefix", "statement", "count", "waivers"), RL06,
                         ids=[case[0].strip() or case[1] for case in RL06])  # fmt: skip
def test_rl06_table(tmp_path, prefix, statement, count, waivers):
    result = lint(tmp_path, in_function(statement, prefix), symbols=[TICK])
    assert len(hits(result, "RL06")) == count, result.format()
    assert sum(result.waivers.values()) == waivers


def test_floats_report_only(tmp_path):
    text = in_function("x = 0.5;")
    strict = lint(tmp_path, text, symbols=[TICK])
    assert strict.violations == () and strict.floats == ()
    report = lint(tmp_path, text, symbols=[TICK], report=True)
    assert [(f.line, f.text) for f in report.floats] == [(10, "0.5")]
    assert "0.5" in report.format()
    assert report.to_json()["floats"] == [{"path": f"src/{EXE}/{UNIT}.c", "line": 10,
                                           "text": "0.5"}]  # fmt: skip


# ---- Task 3: allowlist, selectors, headers, report mode, the committed tree ----


ALLOW_FILE = "readlint-allow.csv"  # under config/
ALLOW_HEAD = "# references to callees not named yet (D-30); never definitions\nexe,name,reason\n"


def write_allowlist(config, *rows):
    (config / ALLOW_FILE).write_bytes((ALLOW_HEAD + "".join(rows)).encode("ascii"))


def test_allowlist_references_only(tmp_path):
    src, config, path = write_tree(tmp_path, in_function("func_00010040();"), symbols=[TICK])
    write_allowlist(config, "ufo2p,func_00010040,a hub Tier 1 calls\n")
    result = run_readlint([src], src_root=src, config_root=config)
    assert hits(result, "RL01") == []
    assert result.allowlisted == {f"src/{EXE}/{UNIT}.c": 1}
    header = ("/*\n * func_00010040: clears the second counter value.\n"
              " * Address: UFO2P.EXE 0x00010040\n"
              " * Evidence: call: after the tick read\n */\n")  # fmt: skip
    path.write_bytes(f"{header}void func_00010040(void)\n{{\n}}\n".encode("ascii"))
    result = run_readlint([src], src_root=src, config_root=config)
    assert [ln for ln, _m in hits(result, "RL01")] == [6]
    assert result.allowlisted == {}


def test_allowlist_never_a_data_definition(tmp_path):
    text = "extern int D_0001ABCD;\nint D_00012345 = 0, D_0001ABCD;\nint use(void);\n"
    src, config, _path = write_tree(tmp_path, text)
    write_allowlist(config, "ufo2p,D_0001ABCD,table read by the loop\n",
                    "ufo2p,D_00012345,table read by the loop\n")  # fmt: skip
    result = run_readlint([src], src_root=src, config_root=config)
    assert sorted(m.split()[0] for _ln, m in hits(result, "RL01")) == ["D_00012345",
                                                                       "D_0001ABCD"]  # fmt: skip
    assert result.allowlisted == {f"src/{EXE}/{UNIT}.c": 1}


def test_allowlist_is_per_exe(tmp_path):
    src, config, _path = write_tree(tmp_path, "void func_0001ABCD(void);\n")
    write_allowlist(config, "tacp,func_0001ABCD,a TACP hub\n")
    result = run_readlint([src], src_root=src, config_root=config)
    assert len(hits(result, "RL01")) == 1


def test_read_allowlist(tmp_path):
    path = tmp_path / ALLOW_FILE
    path.write_bytes((ALLOW_HEAD + "ufo2p,func_0001ABCD,a hub\ntacp,D_00012345,a table\n").encode())
    assert readlint.read_allowlist(path) == {("ufo2p", "func_0001ABCD"): "a hub",
                                    ("tacp", "D_00012345"): "a table"}  # fmt: skip
    assert readlint.read_allowlist(tmp_path / "missing.csv") == {}
    assert (REPO_ROOT / "config" / ALLOW_FILE).read_bytes().startswith(ALLOW_HEAD.encode())
    assert readlint.ALLOWLIST == ALLOW_FILE


BAD_ALLOWLISTS = {
    "header": "exe,name\nufo2p,func_0001ABCD\n",
    "exe": ALLOW_HEAD + "ufo3,func_0001ABCD,a hub\n",
    "name": ALLOW_HEAD + "ufo2p,tick_count,named already\n",
    "reason": ALLOW_HEAD + "ufo2p,func_0001ABCD, \n",
    "cells": ALLOW_HEAD + "ufo2p,func_0001ABCD,a,b\n",
    "repeat": ALLOW_HEAD + "ufo2p,func_0001ABCD,a\nufo2p,func_0001ABCD,b\n",
    "utf8": ALLOW_HEAD + "ufo2p,func_0001ABCD,\xe9\n",
}


@pytest.mark.parametrize("case", BAD_ALLOWLISTS)
def test_bad_allowlist_is_a_tool_error(tmp_path, case):
    src, config, _path = write_tree(tmp_path, CLEAN, symbols=[TICK])
    data = BAD_ALLOWLISTS[case].encode("latin-1")
    (config / ALLOW_FILE).write_bytes(data)
    with pytest.raises(ReadlintError, match=ALLOW_FILE):
        run_readlint([src], src_root=src, config_root=config)
    assert cli_main(["readlint", "--src", str(src), "--config", str(config)]) == 2


F3 = 0x00020000  # the second unit's matched function
UNIT2 = "u_00020000"
MECHANICS = """schema = 1

[[tier]]
id = 1
title = "Tier 1"

[[tier]]
id = 2
title = "Tier 2"

[[item]]
id = "997"
issue = 997
title = "Item 997"
url = "https://github.com/OpenApoc/OpenApoc/issues/997"
tier = 1
scope = "in"
exes = ["ufo2p"]

[[item]]
id = "998"
issue = 998
title = "Item 998"
url = "https://github.com/OpenApoc/OpenApoc/issues/998"
tier = 2
scope = "in"
exes = ["ufo2p"]

[[entry]]
item = "997"
exe = "ufo2p"
address = "0x00010000"
evidence = "bios-tick"
detail = "reads the tick"
source = "spike 007"

[[entry]]
item = "998"
exe = "ufo2p"
address = "0x00020000"
evidence = "bios-tick"
detail = "reads the tick"
source = "spike 007"
"""


def two_units(tmp_path):
    """Two matched ufo2p units: UNIT (clean) and UNIT2 (one placeholder), Tier 1 and 2."""
    src, config, _path = write_tree(tmp_path, CLEAN, symbols=[TICK])
    (src / EXE / f"{UNIT2}.c").write_bytes(b"void func_0001ABCD(void);\n")
    rows = [FunctionRow(F1, F2, f"func_{F1:08X}", "game", UNIT, "call"),
            FunctionRow(F2, F2 + 0x10, f"func_{F2:08X}", "game", UNIT, "call"),
            FunctionRow(F3, F3 + 0x10, f"func_{F3:08X}", "game", UNIT2, "call")]  # fmt: skip
    write_functions_csv(config / EXE / "functions.csv", rows, EXE_FILE)
    status = [StatusRow(start, f"func_{start:08X}", unit, MATCHED, 100.0, 1, SHA, DATE)
              for start, unit in ((F1, UNIT), (F3, UNIT2))]  # fmt: skip
    write_status(status_path(config, EXE), status)
    (config / "mechanics.toml").write_bytes(MECHANICS.encode("ascii"))
    members = [MemberRow(EXE, F1, ("997",), (1,), ("997",), "entry", "member"),
               MemberRow(EXE, F3, ("998",), (2,), ("998",), "entry", "member")]  # fmt: skip
    write_members(config / MEMBERS_CSV, members)
    return src, config


def test_units_and_tier_selectors(tmp_path):
    src, config = two_units(tmp_path)
    everything = run_readlint([src], src_root=src, config_root=config)
    assert everything.files_checked == (f"src/{EXE}/{UNIT}.c", f"src/{EXE}/{UNIT2}.c")
    only = run_readlint([src], src_root=src, config_root=config, units=[f"{EXE}/{UNIT}"])
    assert only.files_checked == (f"src/{EXE}/{UNIT}.c",) and only.violations == ()
    assert f"src/{EXE}/{UNIT2}.c" in [s.path for s in only.skipped]
    tier1 = run_readlint([src], src_root=src, config_root=config, tier=1)
    assert tier1.files_checked == (f"src/{EXE}/{UNIT}.c",)
    tier2 = run_readlint([src], src_root=src, config_root=config, tier=2)
    assert tier2.files_checked == (f"src/{EXE}/{UNIT2}.c",)
    argv = ["readlint", "--src", str(src), "--config", str(config)]
    assert cli_main([*argv, "--units", f"{EXE}/{UNIT}"]) == 0
    assert cli_main([*argv, "--units", f"{EXE}/{UNIT},{EXE}/{UNIT2}"]) == 1
    assert cli_main([*argv, "--tier", "1"]) == 0
    assert cli_main([*argv, "--tier", "2"]) == 1


@pytest.mark.parametrize("selector", [{"units": ["u_00010000"]}, {"units": ["ufo3/u_00010000"]},
                                      {"units": ["ufo2p/u_00099999"]}, {"tier": 3}])  # fmt: skip
def test_bad_selector_is_a_tool_error(tmp_path, selector):
    src, config = two_units(tmp_path)
    with pytest.raises(ReadlintError):
        run_readlint([src], src_root=src, config_root=config, **selector)


def test_included_header_scanned(tmp_path):
    text = '#include "common.h"\n#include "snd.h"\n#include <snd.h>\n#include <conio.h>\n'
    src, config, _path = write_tree(tmp_path, text)
    include = tmp_path / "include"
    include.mkdir()
    (include / "common.h").write_bytes(b"struct C { int unk_0; };\nvoid func_0001ABCD(void);\n")
    (include / "snd.h").write_bytes(b"#ifndef SND_H\n#define SND_H\n/* func_0001ABCD */\n"
                                    b'#include "voice.h"\nstruct Snd {\n    int unk_0;\n'
                                    b"    int volume;\n};\n#endif\n")  # fmt: skip
    (include / "voice.h").write_bytes(b"extern int D_0001ABCD;\n")
    result = run_readlint([src], src_root=src, config_root=config)
    assert result.headers_checked == ("include/snd.h", "include/voice.h")
    assert [(v.path, v.line, v.rule) for v in result.violations] == [
        ("include/snd.h", 6, "RL04"), ("include/voice.h", 1, "RL01")]  # fmt: skip


def test_unreadable_header_is_a_tool_error(tmp_path):
    src, config, _path = write_tree(tmp_path, '#include "snd.h"\n')
    (tmp_path / "include").mkdir()
    (tmp_path / "include" / "snd.h").write_bytes(b"int a;\rint b;\n")
    with pytest.raises(ReadlintError, match="snd.h"):
        run_readlint([src], src_root=src, config_root=config)


def test_report_mode_exit_0(tmp_path, capsys):
    src, config = two_units(tmp_path)
    result = run_readlint([src], src_root=src, config_root=config, report=True)
    assert result.violations and result.exit_code() == 0
    text = result.format()
    assert "RL01 1" in text
    assert f"src/{EXE}/{UNIT}.c: 0 violations" in text
    assert f"src/{EXE}/{UNIT2}.c: 1 violations (RL01 1)" in text
    assert result.to_json()["per_file"][f"src/{EXE}/{UNIT2}.c"] == {
        "violations": 1, "rules": {"RL01": 1}, "waivers": 0, "allowlisted": 0}  # fmt: skip
    argv = ["readlint", "--src", str(src), "--config", str(config)]
    assert cli_main([*argv, "--report"]) == 0
    assert cli_main(argv) == 1


def test_committed_tree_report(capsys):
    """CI pin: `readlint --report src/` on the committed tree exits 0 and checks exactly the
    units status.csv marks matched (strict mode stays the phase gate)."""
    matched = {f"src/{exe}/{row.unit}.c" for exe in readlint.EXES
               for row in read_status(status_path(REPO_ROOT / "config", exe))
               if row.status == MATCHED}  # fmt: skip
    result = run_readlint([REPO_ROOT / "src"], src_root=REPO_ROOT / "src",
                          config_root=REPO_ROOT / "config", report=True)  # fmt: skip
    assert set(result.files_checked) == matched
    assert result.exit_code() == 0
    assert cli_main(["readlint", "--report", str(REPO_ROOT / "src")]) == 0
    out = capsys.readouterr().out
    for path in matched:
        assert f"{path}: " in out


@pytest.mark.parametrize("text", ["", '#include "common.h"\n\nINCLUDE_ASM(func_00010000);\n'
                                      "INCLUDE_ASM(func_00010040);\n"])  # fmt: skip
def test_empty_unit(tmp_path, text):
    result = lint(tmp_path, text)
    assert result.files_checked == (f"src/{EXE}/{UNIT}.c",)
    assert result.violations == ()
