"""`reverseapoc judge` and `reverseapoc batch`: argument parsing and every refusal that must
happen before an EXE is loaded or a compiler runs.

Each refusal test passes a nonexistent --orig and replaces the EXE loader and the batch compile
with functions that fail the test, so a refusal that came too late would show.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from reverseapoc import batch, cli, lift
from reverseapoc.cli import main
from reverseapoc.functions import FunctionRow

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


def test_batch_records_name_their_source(tmp_path, monkeypatch):
    """07-48c: every record of `batch` names its input C file (repo-relative POSIX) and the
    file's LF sha256, a refused record too. The EXE loader is a stub holding one row, and
    nothing compiles (a #pragma source is refused before any compile)."""
    from reverseapoc.status import lf_sha256

    text = '#pragma aux f "*"\nint func_000108E0(void) { return 0; }\n'
    source = tmp_path / "in" / "ufo2p" / "f_000108e0.c"
    source.parent.mkdir(parents=True)
    source.write_text(text, encoding="ascii", newline="\n")
    row = FunctionRow(0x108E0, 0x108F0, "func_000108E0", "game", "u_000108e0", "call")
    stub = SimpleNamespace(stem="ufo2p", rows=(row,), flat=b"\0" * 0x20000,
                           target=SimpleNamespace(name="UFO2P.EXE"))  # fmt: skip
    monkeypatch.setattr(batch, "load_exe_inputs", lambda *a, **kw: stub)
    monkeypatch.setattr(batch, "compile_batch",
                        lambda jobs, *a, **kw: batch.BatchResult((), 0.0, 0.0))  # fmt: skip
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "DEFAULT_BUILD", tmp_path / "build")
    out = tmp_path / "build" / "out.jsonl"
    assert _batch(tmp_path, tmp_path / "in", "--out", str(out), "--cell", "-4r -ot -s -fpi") == 0
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["cell"] for r in records] == ["committed", "-4r -ot -s -fpi"]
    for record in records:
        assert record["key"].startswith("refused: ")
        assert record["source"] == "in/ufo2p/f_000108e0.c"
        assert record["source_sha256"] == lf_sha256(text)


# ---- class and route, end to end through the batch ----

START = 0x108E0
PLAIN_C = "int func_000108E0(void) { return 0; }\n"
OURS = bytes.fromhex("53 83ec10 8b442404 83c410 5b c3")  # the two differ in one stack offset
THEIRS = bytes.fromhex("53 83ec10 8b442408 83c410 5b c3")
NO_RELOCS = SimpleNamespace(ok=True, ours=set(), theirs=set())
LOAD_RELOCATED = SimpleNamespace(ok=True, ours={START + 4}, theirs=set())  # the one difference
PAST_THE_ROW = b"\xc3" * 0x20  # a byte of this read as the row would be one more ret


def _stub_verdict(score: float = 50.0, exact_trim: bool = False) -> batch.Verdict:
    return batch.Verdict(False, True, False, 1, len(OURS), len(THEIRS), score,
                         "mov R, N | mov R, N", exact_trim, 100.0)  # fmt: skip


def _stubbed_run(
    tmp_path, monkeypatch, text=PLAIN_C, *, ok=True, cells=(), relocs=NO_RELOCS, verdicts=()
):
    """`reverseapoc batch` over one source, with a stub EXE, a stub compile and a stub judge: no
    compiler and no object. `verdicts` are the judge's, one per cell in order, then the plain
    stub's. Returns the records and the Compiled of each job."""
    source = tmp_path / "in" / "ufo2p" / "f_000108e0.c"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="ascii", newline="\n")
    row = FunctionRow(START, START + len(THEIRS), "func_000108E0", "game", "u_000108e0", "call")
    flat = b"\0" * START + THEIRS + PAST_THE_ROW
    stub = SimpleNamespace(stem="ufo2p", rows=(row,), flat=flat,
                           target=SimpleNamespace(name="UFO2P.EXE"))  # fmt: skip
    done = []

    def compile_batch(jobs, *args, **kwargs):
        done.extend(batch.Compiled(job, ok, 0.0, "" if ok else "Error! E1000") for job in jobs)
        return batch.BatchResult(tuple(done), 0.0, 0.0)

    defined = SimpleNamespace(ours=OURS)
    body = batch.FunctionBody(None, (row,), defined)
    queue = iter(verdicts)
    monkeypatch.setattr(batch, "load_exe_inputs", lambda *a, **kw: stub)
    monkeypatch.setattr(batch, "compile_batch", compile_batch)
    monkeypatch.setattr(batch, "judge", lambda *a: next(queue, _stub_verdict()))
    monkeypatch.setattr(batch, "function_body", lambda *a: body)
    monkeypatch.setattr(batch, "with_relocs", lambda *a: [(defined, relocs)])
    monkeypatch.setattr(batch, "BUILD_ROOT", tmp_path / "build" / "batch")
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "DEFAULT_BUILD", tmp_path / "build")
    out = tmp_path / "build" / "out.jsonl"
    cell_args = [arg for cell in cells for arg in ("--cell", cell)]
    assert _batch(tmp_path, tmp_path / "in", "--out", str(out), *cell_args) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines], done


def test_batch_records_carry_class_and_route(tmp_path, monkeypatch):
    (record,), (done,) = _stubbed_run(tmp_path, monkeypatch)
    assert (record["class"], record["route"]) == ("slot", "search")
    expected = batch.cell_record("ufo2p", START, "committed", done.job.rule, done, _stub_verdict())
    assert {name: record[name] for name in expected} == expected


def test_a_failed_relocation_check_is_not_class_slot(tmp_path, monkeypatch):
    """Relocated operands are masked before any class is chosen, and the search permutes
    declarations, so it reaches no relocation."""
    failed = SimpleNamespace(ok=False, ours=set(), theirs=set())
    (record,), _ = _stubbed_run(tmp_path, monkeypatch, relocs=failed)
    assert (record["class"], record["route"]) == ("mixed", "agent")


def test_the_class_reads_the_verdicts_exact_trim(tmp_path, monkeypatch):
    verdict = _stub_verdict(exact_trim=True)
    (record,), _ = _stubbed_run(tmp_path, monkeypatch, verdicts=[verdict])
    assert record["class"] == "tail"


def test_the_class_reads_the_relocation_mask(tmp_path, monkeypatch):
    """The mask takes the one differing operand away, so no stack offset is left to explain."""
    (record,), _ = _stubbed_run(tmp_path, monkeypatch, relocs=LOAD_RELOCATED)
    assert record["class"] == "mixed"


def test_a_refused_record_has_no_class(tmp_path, monkeypatch):
    (record,), _ = _stubbed_run(tmp_path, monkeypatch, f'#pragma aux f "*"\n{PLAIN_C}')
    assert record["key"].startswith("refused: ")
    assert "class" not in record
    assert record["route"] == "converter"


def test_a_failed_compile_routes_to_an_agent(tmp_path, monkeypatch):
    (record,), _ = _stubbed_run(tmp_path, monkeypatch, ok=False)
    assert record["compiled"] is False
    assert "class" not in record
    assert record["route"] == "agent"


def test_batch_prints_the_routes(tmp_path, monkeypatch, capsys):
    """Two cells of one row: the row counts once."""
    _stubbed_run(tmp_path, monkeypatch, cells=("-4r -ot -s -fpi",))
    assert "routes: converter 0, search 1, agent 0" in capsys.readouterr().out


def test_the_route_line_reads_the_best_cell(tmp_path, monkeypatch, capsys):
    """The first cell routes to an agent and the second, near, to the converter."""
    verdicts = [_stub_verdict(score=50.0), _stub_verdict(score=95.0)]
    records, _ = _stubbed_run(tmp_path, monkeypatch, cells=("-4r -ot -s -fpi",),
                              relocs=LOAD_RELOCATED, verdicts=verdicts)  # fmt: skip
    assert [record["route"] for record in records] == ["agent", "converter"]
    assert "routes: converter 1, search 0, agent 0" in capsys.readouterr().out


def test_batch_routes_a_hole_draft_to_an_agent(tmp_path, monkeypatch):
    (plain,), _ = _stubbed_run(tmp_path, monkeypatch)
    assert plain["route"] == "search"
    holed = f"{PLAIN_C}{lift.HOLE_MARK}0x108E0: op: movsd */\n"
    (record,), _ = _stubbed_run(tmp_path, monkeypatch, holed)
    assert (record["class"], record["route"]) == ("slot", "agent")
