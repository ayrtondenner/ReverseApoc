"""config/<exe>/boundary-fixes.csv: the owner's split and merge rulings that `functions --write`
applies after the D-07 rule (todo suspected-bad-splits, batch 261119-bhi). Every address below
is made up."""

from __future__ import annotations

from pathlib import Path

import pytest

from reverseapoc.cli import main as cli_main
from reverseapoc.functions import (
    BOUNDARY_FIXES_CSV,
    BOUNDARY_FIXES_CSV_COLUMNS,
    BoundaryFix,
    FunctionRow,
    FunctionsError,
    apply_boundary_fixes,
    read_boundary_fixes_csv,
    read_functions_csv,
)
from reverseapoc.status import MATCHED, StatusRow, write_status
from reverseapoc.targets import REPO_ROOT
from test_functions import A, B, C, ghidra_line, tracer_image, verb_setup

HEADER = ",".join(BOUNDARY_FIXES_CSV_COLUMNS)
DAY = "2026-11-19"
WHY = "a call into the row's middle (mechanics interior)"

R1, R2, R3, DIC, TH = 0x10100, 0x10140, 0x10180, 0x101C0, 0x101D0


def game(start: int, end: int, evidence: str = "call") -> FunctionRow:
    return FunctionRow(start, end, f"func_{start:08X}", "game", "u_x", evidence)


ROWS = (
    game(R1, R2),
    game(R2, R3, "fixup"),
    game(R3, DIC),
    FunctionRow(DIC, TH, f"D_{DIC:08X}", "data-in-code", "u_x", "fixup"),
    FunctionRow(TH, TH + 5, f"func_{TH:08X}", "thunk", "u_x", "ghidra"),
)


def fix(action: str, row: int, at: int) -> BoundaryFix:
    return BoundaryFix(action, row, at, DAY, WHY)


def fixes_file(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / BOUNDARY_FIXES_CSV
    path.write_text("\n".join([HEADER, *lines]) + "\n", encoding="utf-8")
    return path


# ---- the reader ----


def test_header():
    assert BOUNDARY_FIXES_CSV_COLUMNS == ("action", "row", "at", "ruled_on", "evidence")


def test_read_boundary_fixes(tmp_path):
    path = fixes_file(tmp_path, f"split,0x{R1:08X},0x00010120,{DAY},{WHY}",
                      f"merge,0x{R1:08X},0x{R2:08X},{DAY},a jcc into the next row")  # fmt: skip
    assert read_boundary_fixes_csv(path) == [
        fix("split", R1, 0x10120),
        BoundaryFix("merge", R1, R2, DAY, "a jcc into the next row"),
    ]


def test_a_missing_or_header_only_file_has_no_fixes(tmp_path):
    assert read_boundary_fixes_csv(tmp_path / "absent.csv") == []
    assert read_boundary_fixes_csv(fixes_file(tmp_path)) == []


@pytest.mark.parametrize(
    ("line", "what"),
    [
        pytest.param(f"cut,0x{R1:08X},0x00010120,{DAY},{WHY}", "action 'cut'", id="action"),
        pytest.param(f"split,0x10100,0x00010120,{DAY},{WHY}", "row '0x10100'", id="row"),
        pytest.param(f"split,0x{R1:08X},0x10120,{DAY},{WHY}", "at '0x10120'", id="at"),
        pytest.param(f"split,0x{R1:08X},0x{R1:08X},{DAY},{WHY}", "is not above row", id="same"),
        pytest.param(f"merge,0x{R2:08X},0x{R1:08X},{DAY},{WHY}", "is not above row", id="below"),
        pytest.param(f"split,0x{R1:08X},0x00010120,2026-13-01,{WHY}", "ruled_on", id="month"),
        pytest.param(f"split,0x{R1:08X},0x00010120,20261119,{WHY}", "ruled_on", id="undashed"),
        pytest.param(f"split,0x{R1:08X},0x00010120,{DAY},", "evidence is empty", id="evidence"),
        pytest.param(f"split,0x{R1:08X},0x00010120,{DAY},{WHY},x", "more fields", id="extra"),
    ],
)
def test_reader_refusals(tmp_path, line, what):
    path = fixes_file(tmp_path, line)
    with pytest.raises(FunctionsError) as info:
        read_boundary_fixes_csv(path)
    message = str(info.value)
    assert message.startswith(f"{path}: data row 1: ")
    assert what in message


def test_reader_refuses_an_address_fixed_twice(tmp_path):
    path = fixes_file(tmp_path, f"split,0x{R1:08X},0x{R2:08X},{DAY},{WHY}",
                      f"merge,0x{R1:08X},0x{R2:08X},{DAY},{WHY}")  # fmt: skip
    with pytest.raises(FunctionsError, match=r"data row 2: at 0x00010140 is listed twice"):
        read_boundary_fixes_csv(path)


def test_reader_refuses_a_wrong_header(tmp_path):
    path = tmp_path / BOUNDARY_FIXES_CSV
    path.write_text("action,row,at,evidence\n", encoding="utf-8")
    with pytest.raises(FunctionsError, match="header is not action,row,at,ruled_on,evidence"):
        read_boundary_fixes_csv(path)


@pytest.mark.parametrize("exe", ["ufo2p", "tacp"])
def test_the_committed_files_parse(exe):
    """Both EXEs carry the file (header only until the owner rules a fix)."""
    path = REPO_ROOT / "config" / exe / BOUNDARY_FIXES_CSV
    assert path.read_text(encoding="utf-8").splitlines()[0] == HEADER
    assert isinstance(read_boundary_fixes_csv(path), list)


# ---- applying them ----


def test_no_fixes_change_nothing():
    assert apply_boundary_fixes(ROWS, [], matched=frozenset()) == ROWS


def test_a_split_adds_a_start_inside_the_row():
    out = apply_boundary_fixes(ROWS, [fix("split", R1, 0x10120)], matched=frozenset())
    assert out[:3] == (
        game(R1, 0x10120),
        FunctionRow(0x10120, R2, "func_00010120", "game", "u_x", "hand"),
        ROWS[1],
    )
    assert out[3:] == ROWS[2:]


def test_two_splits_of_one_row():
    out = apply_boundary_fixes(ROWS, [fix("split", R1, 0x10130), fix("split", R1, 0x10110)],
                               matched=frozenset())  # fmt: skip
    assert [(r.start, r.end) for r in out[:3]] == [(R1, 0x10110), (0x10110, 0x10130),
                                                   (0x10130, R2)]  # fmt: skip


def test_a_merge_removes_the_start_of_the_next_row():
    out = apply_boundary_fixes(ROWS, [fix("merge", R1, R2)], matched=frozenset())
    assert out == (game(R1, R3), *ROWS[2:])


def test_a_three_row_merge_is_two_adjacent_pairs():
    fixes = [fix("merge", R2, R3), fix("merge", R1, R2)]
    assert apply_boundary_fixes(ROWS, fixes, matched=frozenset()) == (game(R1, DIC), *ROWS[3:])


def test_a_merge_takes_in_the_gap_and_a_thunk_becomes_game():
    rows = (game(R1, R2 - 4), FunctionRow(R2, R2 + 5, f"func_{R2:08X}", "thunk", "u_x", "call"))
    out = apply_boundary_fixes(rows, [fix("merge", R1, R2)], matched=frozenset())
    assert out == (game(R1, R2 + 5),)
    out = apply_boundary_fixes(rows[1:], [fix("split", R2, R2 + 2)], matched=frozenset())
    assert [(r.start, r.end, r.kind) for r in out] == [(R2, R2 + 2, "game"),
                                                       (R2 + 2, R2 + 5, "game")]  # fmt: skip


def test_a_split_inside_a_merged_row():
    out = apply_boundary_fixes(ROWS, [fix("merge", R1, R2), fix("split", R2, 0x10150)],
                               matched=frozenset())  # fmt: skip
    assert [(r.start, r.end) for r in out[:2]] == [(R1, 0x10150), (0x10150, R3)]


@pytest.mark.parametrize(
    ("one", "matched", "what"),
    [
        pytest.param(fix("split", 0x10110, 0x10120), (), "0x00010110 starts no row", id="row"),
        pytest.param(fix("split", R1, R2), (), "not inside the row", id="row-end"),
        pytest.param(fix("split", R1, R3), (), "not inside the row", id="past"),
        pytest.param(fix("merge", R1, R3), (), "the row after 0x00010100 is 0x00010140",
                     id="not-adjacent"),  # fmt: skip
        pytest.param(fix("merge", R3, DIC), (), "data-in-code", id="data-row"),
        pytest.param(fix("split", DIC, DIC + 4), (), "data-in-code", id="data-split"),
        pytest.param(fix("merge", TH, TH + 0x10), (), "no row follows", id="last-row"),
        pytest.param(fix("split", R1, 0x10120), (R1,), "matched", id="matched-split"),
        pytest.param(fix("merge", R1, R2), (R2,), "matched", id="matched-merged"),
        pytest.param(fix("merge", R1, R2), (R1,), "matched", id="matched-kept"),
    ],
)
def test_apply_refusals(one, matched, what):
    with pytest.raises(FunctionsError) as info:
        apply_boundary_fixes(ROWS, [one], matched=frozenset(matched))
    message = str(info.value)
    assert message.startswith(f"boundary fix {one.action} 0x{one.row:08X} at 0x{one.at:08X}: ")
    assert what in message


# ---- the functions verb ----


def _ghidra() -> tuple[str, ...]:
    return ghidra_line(A), ghidra_line(B), ghidra_line(C)


def test_the_verb_without_fixes_writes_the_same_bytes(tmp_path: Path, capsys):
    """An empty or missing boundary-fixes.csv leaves the generated functions.csv byte-identical."""
    args = verb_setup(tmp_path, tracer_image(), *_ghidra())
    out = tmp_path / "out"
    assert cli_main(["functions", *args, "--output", str(out)]) == 0, capsys.readouterr().err
    before = (out / "functions.csv").read_bytes()
    fixes_file(out)
    assert cli_main(["functions", *args, "--output", str(out)]) == 0, capsys.readouterr().err
    assert (out / "functions.csv").read_bytes() == before


def test_the_verb_applies_a_split(tmp_path: Path, capsys):
    args = verb_setup(tmp_path, tracer_image(), *_ghidra())
    out = tmp_path / "out"
    out.mkdir()
    fixes_file(out, f"split,0x{A:08X},0x{A + 5:08X},{DAY},{WHY}")
    assert cli_main(["functions", *args, "--output", str(out)]) == 0, capsys.readouterr().err
    rows = read_functions_csv(out / "functions.csv")
    assert [(r.start, r.end, r.evidence) for r in rows[:2]] == [(A, A + 5, "entry"),
                                                                (A + 5, A + 6, "hand")]  # fmt: skip
    assert "4 functions (4 game" in capsys.readouterr().out


def test_the_verb_refuses_a_fix_of_a_matched_row(tmp_path: Path, capsys):
    args = verb_setup(tmp_path, tracer_image(), *_ghidra())
    out = tmp_path / "out"
    out.mkdir()
    fixes_file(out, f"split,0x{A:08X},0x{A + 5:08X},{DAY},{WHY}")
    write_status(out / "status.csv", [StatusRow(A, f"func_{A:08X}", "u_x", MATCHED, 100.0, 1,
                                                "0" * 64, DAY)])  # fmt: skip
    assert cli_main(["functions", *args, "--output", str(out)]) != 0
    assert "matched" in capsys.readouterr().err
    assert not (out / "functions.csv").exists()
