"""The units draft (D-11), unit assignment and the INCLUDE_ASM scaffold (D-12).

Every address, name and string here is made up for the test: rows are synthetic, and the bytes
are patched into the synthetic LE of tests/conftest.py (code object at 0x10000, pages filled
with 0x11, data object at 0x20000). No byte comes from a game executable.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from conftest import build_le_image, fixup_record, requires_capstone, write_manifest
from reverseapoc import cli
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import (
    FunctionRow,
    UnitRow,
    check_unit_assignment,
    read_functions_csv,
    read_units_csv,
    write_functions_csv,
    write_units_csv,
)
from reverseapoc.le import LE
from reverseapoc.libmatch import RUNTIME_CSV_COLUMNS, MatchRange
from reverseapoc.units import (
    UnitsError,
    assign_units,
    chk_callers,
    draft_units,
    scaffold_unit,
    write_unit_source,
)

CODE = 0x10000
DATA = 0x20000
OFF32 = 7  # LE fixup source type: 32-bit offset
NOP = b"\x90"
UNIT_NAME = re.compile(r"[a-z0-9_]+")


@pytest.fixture(autouse=True)
def _capstone():
    requires_capstone()


def game(start: int, end: int) -> FunctionRow:
    return FunctionRow(start, end, f"func_{start:08X}", "game", "", "call")


def runtime(start: int, end: int, name: str) -> FunctionRow:
    return FunctionRow(start, end, name, "runtime", "", "runtime")


def table(start: int, end: int) -> FunctionRow:
    return FunctionRow(start, end, f"D_{start:08X}", "data-in-code", "", "fixup")


def module(name: str, start: int, end: int, *publics: str) -> MatchRange:
    return MatchRange(start, end, "_TEXT", name, ("DOS/CLIB3R.LIB",), ("10.6",), publics,
                      "unique")  # fmt: skip


def string_ref(site: int, string: int) -> bytes:
    """An off32 fixup at code address `site` naming data address `string`."""
    return fixup_record(OFF32, site - CODE, 2, string - DATA, off32=True)


def image(patches: dict[int, bytes] | None = None, code_fixups: bytes = b"") -> LE:
    return LE(build_le_image(fixups=[code_fixups, b"", b""], patches=patches or {}).data)


def draft(le: LE, rows: list[FunctionRow], *, modules=(), callers=()) -> list[UnitRow]:
    return draft_units(le, rows, runtime=list(modules), chk_callers=set(callers),
                       flat=le.load_flat(relocate=False), fixups=le.fixups())  # fmt: skip


def shape(units: list[UnitRow]) -> list[tuple[str, int, int, str]]:
    return [(u.unit, u.start, u.end, u.reason) for u in units]


def test_runtime_modules_are_units():
    """Each runtime module's rows form one unit rt_<module>; the unit after a module is cut
    there too."""
    rows = [game(0x10000, 0x10010), runtime(0x10100, 0x10110, "a_"),
            runtime(0x10110, 0x10120, "b_"), runtime(0x10120, 0x10130, "c_"),
            game(0x10200, 0x10210)]  # fmt: skip
    modules = [module("moda", 0x10100, 0x10120, "a_", "b_"), module("modb", 0x10120, 0x10130, "c_")]
    assert shape(draft(image(), rows, modules=modules)) == [
        ("u_00010000", 0x10000, 0x10100, "first"),
        ("rt_moda", 0x10100, 0x10120, "runtime"),
        ("rt_modb", 0x10120, 0x10200, "runtime"),
        ("u_00010200", 0x10200, 0x10210, "runtime"),
    ]


def test_chk_cluster_cut():
    """A run of __CHK callers next to non-callers is cut at each edge of the cluster."""
    rows = [game(CODE + 0x100 * i, CODE + 0x100 * i + 0x10) for i in range(4)]
    callers = [rows[0].start, rows[1].start, rows[3].start]
    assert [(u.start, u.reason) for u in draft(image(), rows, callers=callers)] == [
        (rows[0].start, "first"),
        (rows[2].start, "chk-cluster"),
        (rows[3].start, "chk-cluster"),
    ]


def test_source_string_names_the_unit():
    """A function referencing a source-file string starts the unit named after the file stem
    (the leading jump table right before it goes with it); another reference to the same file
    stays in the unit; an assert string naming another file starts that file's unit."""
    g1, lead, g2, g3, g4 = CODE + 0x100, CODE + 0x200, CODE + 0x208, CODE + 0x300, CODE + 0x400
    grafix, assertion = DATA + 0x40, DATA + 0x80
    patches = {grafix: b"source\\grafix.c\x00",
               assertion: b"Assertion failed: x, file engine.c, line 3\x00"}  # fmt: skip
    fixups = string_ref(g2 + 1, grafix) + string_ref(g3 + 1, grafix) + string_ref(g4 + 1, assertion)
    rows = [game(g1, g1 + 0x10), table(lead, g2), game(g2, g2 + 0x10), game(g3, g3 + 0x10),
            game(g4, g4 + 0x10)]  # fmt: skip
    assert shape(draft(image(patches, fixups), rows)) == [
        (f"u_{g1:08x}", g1, lead, "first"),
        ("grafix", lead, g4, "source-string"),
        ("engine", g4, g4 + 0x10, "source-string"),
    ]


def test_data_order_and_gap_cuts():
    """A string reference below the strings the unit has referenced so far cuts with data-order;
    filler before a 16-aligned start cuts with alignment-gap."""
    g1, g2, g3 = CODE + 0x100, CODE + 0x108, CODE + 0x120
    alpha, beta = DATA + 0x80, DATA + 0x40
    patches = {alpha: b"alpha\x00", beta: b"beta\x00", g2 + 0x10: NOP * 8}
    fixups = string_ref(g1 + 1, alpha) + string_ref(g2 + 1, beta)
    rows = [game(g1, g2), game(g2, g2 + 0x10), game(g3, g3 + 0x10)]
    assert [(u.start, u.reason) for u in draft(image(patches, fixups), rows)] == [
        (g1, "first"),
        (g2, "data-order"),
        (g3, "alignment-gap"),
    ]


def test_unit_names_are_unique():
    """Two units named by the same file get _2."""
    g1, g2, g3 = CODE + 0x100, CODE + 0x200, CODE + 0x300
    one, other = DATA + 0x40, DATA + 0x80
    patches = {one: b"grafix.c\x00", other: b"engine.c\x00"}
    fixups = string_ref(g1 + 1, one) + string_ref(g2 + 1, other) + string_ref(g3 + 1, one)
    rows = [game(g1, g1 + 0x10), game(g2, g2 + 0x10), game(g3, g3 + 0x10)]
    names = [u.unit for u in draft(image(patches, fixups), rows)]
    assert names == ["grafix", "engine", "grafix_2"]


def mixed_rows() -> tuple[list[FunctionRow], list[MatchRange]]:
    rows = [game(0x10000, 0x10010), game(0x10010, 0x10020), runtime(0x10100, 0x10110, "a_"),
            table(0x10200, 0x10208), game(0x10208, 0x10210), game(0x10300, 0x10380)]  # fmt: skip
    return rows, [module("moda", 0x10100, 0x10110, "a_")]


def test_every_function_in_one_unit():
    rows, modules = mixed_rows()
    units = draft(image(), rows, modules=modules, callers=[0x10010, 0x10300])
    assigned = assign_units(rows, units)
    assert check_unit_assignment(assigned, units) == []
    names = [u.unit for u in units]
    assert len(set(names)) == len(names)
    assert all(UNIT_NAME.fullmatch(name) for name in names)
    assert all(row.unit for row in assigned)


def test_draft_refuses_no_functions():
    with pytest.raises(UnitsError, match="no function"):
        draft(image(), [])


def test_chk_callers_reads_the_prologue():
    """`push imm32; call rel32` into a runtime row publishing __CHK at a function's start."""
    chk, caller, other = CODE + 0x500, CODE + 0x100, CODE + 0x200
    prologue = b"\x68" + struct.pack("<I", 0x40) + b"\xe8" + struct.pack("<i", chk - (caller + 10))
    le = image({caller: prologue, other: b"\x68" + struct.pack("<I", 0x40) + NOP * 5})
    rows = [game(caller, caller + 0x10), game(other, other + 0x10), runtime(chk, chk + 8, "__CHK")]
    flat = le.load_flat(relocate=False)
    assert chk_callers(rows, flat, [(chk, chk + 8)]) == {caller}


UNIT = UnitRow("grafix", 0x10000, 0x10100, "source-string")
SCAFFOLD_ROWS = [
    FunctionRow(0x10040, 0x10050, "func_00010040", "thunk", "grafix", "call"),
    FunctionRow(0x10000, 0x10010, "func_00010000", "game", "grafix", "entry"),
    FunctionRow(0x10010, 0x10020, "zork_", "runtime", "grafix", "runtime"),
    FunctionRow(0x10020, 0x10028, "D_00010020", "data-in-code", "grafix", "fixup"),
    FunctionRow(0x10100, 0x10110, "func_00010100", "game", "other", "call"),
]


def test_scaffold():
    """#include "common.h" and one INCLUDE_ASM marker per game and thunk row of the unit, in
    address order (orchestrator ruling F5); comments are /* */ and nothing else is code."""
    text = scaffold_unit("SYN.EXE", UNIT, SCAFFOLD_ROWS)
    assert "//" not in text
    code = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines = [line for line in code.splitlines() if line.strip()]
    assert lines == [
        '#include "common.h"',
        "INCLUDE_ASM(func_00010000);",
        "INCLUDE_ASM(func_00010040);",
    ]


def test_scaffold_refuses_a_unit_without_game_functions():
    runtime_unit = UnitRow("rt_moda", 0x10010, 0x10020, "runtime")
    with pytest.raises(UnitsError, match="no game or thunk"):
        scaffold_unit("SYN.EXE", runtime_unit, SCAFFOLD_ROWS)


def test_write_unit_source_refuses_an_existing_file(tmp_path):
    path = tmp_path / "src" / "syn" / "grafix.c"
    write_unit_source(path, "/* one */\n")
    with pytest.raises(UnitsError, match="exists"):
        write_unit_source(path, "/* two */\n")
    assert path.read_text(encoding="ascii") == "/* one */\n"


# ---- the verb ----


def verb_setup(tmp_path: Path) -> list[str]:
    """SYN.EXE, its manifest, an empty runtime.csv and a functions.csv of two game rows."""
    data = build_le_image().data
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYN.EXE").write_bytes(data)
    manifest = write_manifest(tmp_path / "targets.toml", {"SYN.EXE": data})
    runtime_csv = tmp_path / "runtime.csv"
    runtime_csv.write_text(",".join(RUNTIME_CSV_COLUMNS) + "\n", encoding="utf-8")
    functions = tmp_path / "functions.csv"
    write_functions_csv(functions, [game(0x10000, 0x10010), game(0x10010, 0x10020)], "SYN.EXE")
    return ["SYN.EXE", "--orig", str(orig), "--manifest", str(manifest), "--runtime",
            str(runtime_csv), "--functions", str(functions)]  # fmt: skip


def test_units_verb(tmp_path: Path, capsys):
    args = verb_setup(tmp_path)
    out = tmp_path / "out"
    src = tmp_path / "src"
    rc = cli_main(["units", *args, "--output", str(out)])
    assert rc == 0, capsys.readouterr().err
    units = read_units_csv(out / "units.csv")
    assert [u.unit for u in units] == ["u_00010000"]
    assert {row.unit for row in read_functions_csv(out / "functions.csv")} == {"u_00010000"}
    scaffold = ["units", *args, "--output", str(out), "--write-src", "u_00010000",
                "--src-root", str(src)]  # fmt: skip
    assert cli_main(scaffold) == 0
    written = src / "syn" / "u_00010000.c"
    assert "INCLUDE_ASM(func_00010010);" in written.read_text(encoding="ascii")
    assert cli_main(scaffold) == 1
    assert "exists" in capsys.readouterr().err


def test_write_src_runs_on_its_own(tmp_path: Path, capsys):
    """Orchestrator ruling F2: --write-src without --write/--output reads the committed
    units.csv and functions.csv (here given by path) and writes only the unit source."""
    args = verb_setup(tmp_path)
    units = tmp_path / "units.csv"
    write_units_csv(units, [UnitRow("grafix", 0x10000, 0x10020, "hand")], "SYN.EXE")
    src = tmp_path / "src"
    run = ["units", *args, "--units", str(units), "--write-src", "grafix", "--src-root", str(src)]
    assert cli_main(run) == 0, capsys.readouterr().err
    assert (src / "syn" / "grafix.c").is_file()
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "functions.csv", "orig", "runtime.csv", "src", "targets.toml", "units.csv"
    ]  # fmt: skip
    assert cli_main(run) == 1
    assert cli_main(["units", *args, "--units", str(units), "--write-src", "nosuch",
                     "--src-root", str(src)]) == 1  # fmt: skip


def test_units_verb_needs_an_action(tmp_path: Path, capsys):
    assert cli_main(["units", *verb_setup(tmp_path)]) == 1
    assert "--write-src" in capsys.readouterr().err


def test_units_write_keeps_a_hand_recut(tmp_path: Path, monkeypatch, capsys):
    """--write never replaces an existing units.csv (a hand re-cut) unless --redraft."""
    config = tmp_path / "config"
    monkeypatch.setattr(cli, "config_dir", lambda name: config / Path(name).stem.lower())
    args = verb_setup(tmp_path)
    units = config / "syn" / "units.csv"
    write_units_csv(units, [UnitRow("grafix", 0x10000, 0x10020, "hand")], "SYN.EXE")
    assert cli_main(["units", *args, "--write"]) == 1
    assert "--redraft" in capsys.readouterr().err
    assert [u.unit for u in read_units_csv(units)] == ["grafix"]
    assert cli_main(["units", *args, "--write", "--redraft"]) == 0
    assert [u.unit for u in read_units_csv(units)] == ["u_00010000"]
