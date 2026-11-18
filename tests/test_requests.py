"""`reverseapoc requests` (todo agent-requests-collector): the tooling requests agents leave in
their attempt notes, grouped with counts and example paths.

Every test builds a synthetic build/driver/<run>/<exe>/<function>/attempt-N/notes.md under
tmp_path; no game bytes, never the real runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reverseapoc import cli, requests


def _notes(repo: Path, run: str, text: str, function: str = "func_00012340", n: int = 1,
           exe: str = "ufo2p") -> Path:  # fmt: skip
    attempt_dir = repo / "build" / "driver" / run / exe / function / f"attempt-{n}"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "notes.md").write_text(text, encoding="utf-8")
    return attempt_dir / "notes.md"


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("3. Tooling request: a disassembly of our object, to confirm the 13-byte reading.",
         ["a disassembly of our object, to confirm the 13-byte reading"]),
        ("- Tooling request (repeated across attempts): let sweep stage 2 run when the only\n"
         "  reloc problem is the length. Other text follows.",
         ["let sweep stage 2 run when the only reloc problem is the length"]),
        ("2. Tooling\n   request, repeated: the driver should not re-claim a function.",
         ["the driver should not re-claim a function"]),
        ("of our own object (tooling request: a window into our compiled bytes) and more.",
         ["a window into our compiled bytes"]),
        ("not read: no disassembly of our object (tooling request).\nCheck 0009: exit 1.", []),
        ("Earlier notes also request review of the function row end.", []),
        ("1. Tooling request: one.\n2. Tooling request: two.", ["one", "two"]),
    ],
    ids=["numbered", "qualified-and-wrapped", "split-marker", "inline", "no-text", "no-tag",
         "two-items"],
)
def test_extract(text, found):
    assert requests.extract(text) == found


def test_group_key_folds_hex_and_cuts_the_first_clause():
    assert requests.group_key("A disassembly of our object, to confirm the 13-byte reading") == (
        "a disassembly of our object")  # fmt: skip
    assert requests.group_key("show the window at 0x0006052B for func_0005F230") == (
        "show the window at N for func_N")  # fmt: skip
    assert requests.group_key("a disassembly of our object would replace the inferences") == (
        "a disassembly of our object")  # fmt: skip


def _two_runs(repo: Path) -> None:
    _notes(repo, "night1", "3. Tooling request: a disassembly of our object, to confirm it.\n"
                           "4. Tooling request: a disassembly of our object would help.\n")
    _notes(repo, "night1", "Tooling request: A disassembly of our object.", n=2)
    _notes(repo, "night2", "1. Tooling request: print the window of a sweep's best cell.",
           function="func_00099990", exe="tacp")  # fmt: skip
    _notes(repo, "night2", "No requests here.", function="func_00099999")


def test_collect_groups_and_counts(tmp_path):
    _two_runs(tmp_path)
    report = requests.collect(tmp_path)
    assert (report.runs, report.notes, report.lines) == (2, 4, 4)
    top, second = report.groups
    assert (top.key, top.count) == ("a disassembly of our object", 2)  # 2 notes files, 3 lines
    assert top.paths == ("build/driver/night1/ufo2p/func_00012340/attempt-1/notes.md",
                         "build/driver/night1/ufo2p/func_00012340/attempt-2/notes.md")  # fmt: skip
    assert top.example == "a disassembly of our object, to confirm it"
    assert (second.key, second.count) == ("print the window of a sweep's best cell", 1)


def test_collect_named_runs_only(tmp_path):
    _two_runs(tmp_path)
    report = requests.collect(tmp_path, ["night2"])
    assert (report.runs, report.notes) == (1, 2)
    assert [g.key for g in report.groups] == ["print the window of a sweep's best cell"]


def test_an_unknown_run_is_refused(tmp_path, capsys):
    _two_runs(tmp_path)
    assert cli.main(["requests", "--repo", str(tmp_path), "nowhere"]) == 2
    assert "nowhere" in capsys.readouterr().err


def test_cli_text(tmp_path, capsys):
    _two_runs(tmp_path)
    assert cli.main(["requests", "--repo", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "tooling requests: 4 lines in 4 notes files of 2 runs, 2 groups" in out
    assert "  2  a disassembly of our object" in out
    assert "      e.g. a disassembly of our object, to confirm it" in out
    assert "      in build/driver/night1/ufo2p/func_00012340/attempt-1/notes.md" in out


def test_cli_json(tmp_path, capsys):
    _two_runs(tmp_path)
    assert cli.main(["requests", "--repo", str(tmp_path), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["groups"][0]["count"] == 2 and doc["notes"] == 4


def test_no_driver_directory_is_empty(tmp_path, capsys):
    assert cli.main(["requests", "--repo", str(tmp_path)]) == 0
    assert "tooling requests: 0 lines in 0 notes files of 0 runs, 0 groups" in (
        capsys.readouterr().out)  # fmt: skip
