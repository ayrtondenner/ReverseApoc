"""readlint (DEC-04, D-20, D-21, D-30, backlog 999.2): the readability linter for matched units.

Every test writes made-up C into a tmp_path src/ tree beside a synthetic config/ tree (status.csv
marking the unit matched, functions.csv, symbols.csv when a test renames a row). No game bytes.
Files are written as bytes so the host never translates line ends.
"""

from __future__ import annotations

import json

import pytest

from reverseapoc import readlint
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, SymbolRow, write_functions_csv, write_symbols_csv
from reverseapoc.readlint import ReadlintError, run_readlint
from reverseapoc.status import MATCHED, PARTIAL, StatusRow, status_path, write_status

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
