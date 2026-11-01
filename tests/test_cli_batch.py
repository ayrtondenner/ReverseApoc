"""`reverseapoc judge` and `reverseapoc batch`: argument parsing and every refusal that must
happen before an EXE is loaded or a compiler runs.

Each refusal test passes a nonexistent --orig and replaces the EXE loader and the batch compile
with functions that fail the test, so a refusal that came too late would show.
"""

from __future__ import annotations

import pytest

from reverseapoc import batch, cli
from reverseapoc.cli import main

ADDRESS = "0x000108E0"


@pytest.fixture
def no_load(monkeypatch):
    """Fail the test if the verb loads an EXE or compiles anything."""

    def refuse(*args, **kwargs):
        raise AssertionError("loaded or compiled before refusing")

    monkeypatch.setattr(batch, "load_exe_inputs", refuse)
    monkeypatch.setattr(batch, "compile_batch", refuse)


def _judge(tmp_path, source, *extra):
    return main(["judge", "ufo2p", ADDRESS, str(source), "--orig", str(tmp_path / "noorig"),
                 *extra])  # fmt: skip


@pytest.mark.parametrize(
    "text", ["#pragma aux f \"*\"\nint f(void) { return 0; }\n", "void f(void) { __asm nop }\n"]
)
def test_judge_refuses_pragma_and_inline_asm(tmp_path, capsys, no_load, text):
    source = tmp_path / "f.c"
    source.write_text(text, encoding="ascii")
    assert _judge(tmp_path, source) == 2
    err = capsys.readouterr().err
    assert "reverseapoc judge: refused:" in err


def test_judge_refuses_a_non_ascii_source(tmp_path, capsys, no_load):
    source = tmp_path / "f.c"
    source.write_bytes("int f(void) { return 0; } /* é */\n".encode())
    assert _judge(tmp_path, source) == 2
    assert "reverseapoc judge:" in capsys.readouterr().err


def test_judge_missing_file_is_a_tool_error(tmp_path, capsys, no_load):
    assert _judge(tmp_path, tmp_path / "missing.c") == 2
    assert "reverseapoc judge: error:" in capsys.readouterr().err


def test_judge_bad_address_is_a_tool_error(tmp_path, capsys, no_load):
    source = tmp_path / "f.c"
    source.write_text("int f(void) { return 0; }\n", encoding="ascii")
    code = main(["judge", "ufo2p", "0xZZ", str(source), "--orig", str(tmp_path / "noorig")])
    assert code == 2
    assert "reverseapoc judge: error:" in capsys.readouterr().err


def test_judge_parses_its_arguments():
    args = cli.build_parser().parse_args(["judge", "ufo2p", ADDRESS, "f.c"])
    assert (args.exe, args.address, str(args.file)) == ("ufo2p", ADDRESS, "f.c")
    assert args.func is cli._cmd_judge
