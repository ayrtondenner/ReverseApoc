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


def test_judge_parses_cells_and_json():
    args = cli.build_parser().parse_args(
        ["judge", "ufo2p", ADDRESS, "f.c", "--cell", "-4r -ot -s -fpi",
         "--cell", "-4r -oneatx -s -fpi", "--json"]
    )  # fmt: skip
    assert args.cell == ["-4r -ot -s -fpi", "-4r -oneatx -s -fpi"]
    assert args.json is True
    assert cli.build_parser().parse_args(["judge", "ufo2p", ADDRESS, "f.c"]).cell == []


@pytest.mark.parametrize("cell", ["--cell=-fo=x.obj", "--cell=-i=foo", "--cell=  "])
def test_judge_refuses_a_bad_cell_before_any_compile(tmp_path, capsys, no_load, cell):
    source = tmp_path / "f.c"
    source.write_text("int f(void) { return 0; }\n", encoding="ascii")
    assert _judge(tmp_path, source, cell) == 2
    assert "reverseapoc judge: error:" in capsys.readouterr().err


# ---- reverseapoc batch ----


def _tree(root, names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("int f(void) { return 0; }\n", encoding="ascii")
    return root


def test_batch_sources_lists_every_function_file_sorted(tmp_path):
    root = _tree(tmp_path, ["ufo2p/f_000108e0.c", "tacp/f_00021a90.c", "ufo2p/f_000105d0.c",
                            "ufo2p/notes.json", "ufo2p/x.c", "f_00000010.c"])  # fmt: skip
    assert batch.batch_sources(root) == [
        ("tacp", 0x21A90, root / "tacp" / "f_00021a90.c"),
        ("ufo2p", 0x105D0, root / "ufo2p" / "f_000105d0.c"),
        ("ufo2p", 0x108E0, root / "ufo2p" / "f_000108e0.c"),
    ]


@pytest.mark.parametrize("name", ["f_12.c", "f_0000zz00.c", "f_000108E0.c"])
def test_batch_sources_refuses_a_malformed_name(tmp_path, name):
    root = _tree(tmp_path, [f"ufo2p/{name}"])
    with pytest.raises(batch.BatchError, match=name.replace(".", r"\.")):
        batch.batch_sources(root)


def _batch(tmp_path, root, *extra):
    return main(["batch", str(root), "--orig", str(tmp_path / "noorig"), *extra])


def test_batch_refuses_an_out_outside_build(tmp_path, capsys, no_load):
    root = _tree(tmp_path / "in", ["ufo2p/f_000108e0.c"])
    assert _batch(tmp_path, root, "--out", str(tmp_path / "x.jsonl")) == 2
    assert "reverseapoc batch: error:" in capsys.readouterr().err
    assert not (tmp_path / "x.jsonl").exists()


def test_batch_refuses_an_empty_dir(tmp_path, capsys, no_load):
    root = _tree(tmp_path / "in", ["ufo2p/notes.json"])
    assert _batch(tmp_path, root) == 2
    assert "reverseapoc batch: error:" in capsys.readouterr().err


def test_batch_refuses_an_unknown_exe_dir(tmp_path, capsys, no_load):
    root = _tree(tmp_path / "in", ["notanexe/f_000108e0.c"])
    assert _batch(tmp_path, root) == 2
    assert "reverseapoc batch: error:" in capsys.readouterr().err


@pytest.mark.parametrize("workers", ["0", "-2"])
def test_batch_refuses_bad_workers(tmp_path, capsys, no_load, workers):
    root = _tree(tmp_path / "in", ["ufo2p/f_000108e0.c"])
    assert _batch(tmp_path, root, f"--workers={workers}") == 2
    assert "reverseapoc batch: error:" in capsys.readouterr().err


def test_batch_refuses_a_bad_cell(tmp_path, capsys, no_load):
    root = _tree(tmp_path / "in", ["ufo2p/f_000108e0.c"])
    assert _batch(tmp_path, root, "--cell=-fo=x.obj") == 2
    assert "reverseapoc batch: error:" in capsys.readouterr().err


def test_batch_parses_its_arguments():
    args = cli.build_parser().parse_args(["batch", "d", "--cell", "-4r -ot -s -fpi"])
    assert args.cell == ["-4r -ot -s -fpi"]
    assert args.workers == 8
    assert args.out == batch.BUILD_ROOT / "batch.jsonl"
    assert args.func is cli._cmd_batch
