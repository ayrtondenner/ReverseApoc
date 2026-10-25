"""tools/progress.py (RPT-02, D-26, D-40, D-50): the committed CSVs become progress.json and the
shield endpoint. progress.py runs under the Pages runner's system `python3 -I` (D-27), so it is a
stdlib script loaded here by path, the way check._configure loads configure.py. The synthetic
tables use made-up addresses and names; the committed-file tests read config/ only (no game
bytes)."""

from __future__ import annotations

import ast
import functools
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.functions import (
    FunctionRow,
    UnitRow,
    read_functions_csv,
    read_units_csv,
    write_functions_csv,
    write_units_csv,
)
from reverseapoc.status import MATCHED, PARTIAL, StatusRow, read_status, status_path, write_status

PROGRESS = REPO_ROOT / "tools" / "progress.py"
CONFIG = REPO_ROOT / "config"
EXES = ("ufo2p", "tacp")
EXE_NAMES = {"ufo2p": "UFO2P.EXE", "tacp": "TACP.EXE"}
# Measured on 2026-10-25 with set arithmetic over reverseapoc's own readers (every byte of every
# units.csv span minus every byte of every functions.csv row), after 06-04's 26 shorter rows.
COMMITTED_UNCOVERED = {"ufo2p": 25_787, "tacp": 35_349}
SHA = "a" * 64
DAY = "2026-10-25"


@functools.cache
def load_progress():
    """tools/progress.py, loaded by path under a private module name (once per session). Called
    in each test body, so a missing script fails the test on this assert."""
    assert PROGRESS.is_file(), f"{PROGRESS} does not exist"
    spec = importlib.util.spec_from_file_location("_test_progress", PROGRESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their module up while it executes
    spec.loader.exec_module(module)
    return module


# ---- a synthetic config tree ----

# UFO2P: one unit [0x10000, 0x10100) holding a matched, a partial and an unmatched game row, a
# runtime row, a data-in-code row, a 16-byte gap in no row, and an unmatched thunk.
U_MATCHED = FunctionRow(0x10000, 0x10010, "func_00010000", "game", "u_00010000", "call")  # 16
U_PARTIAL = FunctionRow(0x10010, 0x10030, "func_00010010", "game", "u_00010000", "call")  # 32
U_UNMATCHED = FunctionRow(0x10030, 0x10070, "func_00010030", "game", "u_00010000", "call")  # 64
U_RUNTIME = FunctionRow(0x10070, 0x10078, "__rt_helper", "runtime", "u_00010000", "runtime")  # 8
U_DATA = FunctionRow(0x10078, 0x1007C, "D_00010078", "data-in-code", "u_00010000", "runtime")  # 4
GAP = 0x1008C - 0x1007C  # 16 bytes inside the unit, in no row
U_THUNK = FunctionRow(0x1008C, 0x10100, "func_0001008C", "thunk", "u_00010000", "call")  # 116
U_UNIT = UnitRow("u_00010000", 0x10000, 0x10100, "hand")
# TACP: one unit, one unmatched game row filling it.
T_GAME = FunctionRow(0x20000, 0x20020, "func_00020000", "game", "u_00020000", "call")  # 32
T_UNIT = UnitRow("u_00020000", 0x20000, 0x20020, "hand")


def synthetic_config(root: Path) -> Path:
    """config/<exe>/{functions,units,status}.csv for the two EXEs above, written by
    reverseapoc's own writers, so the format is exactly the committed one."""
    config = root / "config"
    tables = {
        "ufo2p": ([U_MATCHED, U_PARTIAL, U_UNMATCHED, U_RUNTIME, U_DATA, U_THUNK], [U_UNIT]),
        "tacp": ([T_GAME], [T_UNIT]),
    }
    for exe, (rows, units) in tables.items():
        write_functions_csv(config / exe / "functions.csv", rows, EXE_NAMES[exe])
        write_units_csv(config / exe / "units.csv", units, EXE_NAMES[exe])
    write_status(status_path(config, "ufo2p"), [
        StatusRow(U_MATCHED.start, U_MATCHED.name, U_MATCHED.unit, MATCHED, 100.0, 0, SHA, DAY),
        StatusRow(U_PARTIAL.start, U_PARTIAL.name, U_PARTIAL.unit, PARTIAL, 50.0, 1, SHA, DAY),
    ])  # fmt: skip
    return config  # tacp has no status.csv: sparse, every function unmatched


def size(row: FunctionRow) -> int:
    return row.end - row.start


def progress_doc(progress, config: Path, out: Path) -> dict:
    progress.write_progress_json(progress.derive(config), out / "progress.json")
    return json.loads((out / "progress.json").read_text(encoding="utf-8"))


# ---- Task 1 ----


def test_progress_is_stdlib_and_312_compatible():
    """The Pages runner's python3 is 3.12 or newer (research A8) and -I sees no venv: the script
    parses as 3.12 and imports only top-level stdlib modules, never reverseapoc."""
    assert PROGRESS.is_file(), f"{PROGRESS} does not exist"
    tree = ast.parse(PROGRESS.read_text(encoding="utf-8"), feature_version=(3, 12))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "progress.py is a script: no relative imports"
            imported.add((node.module or "").split(".")[0])
    assert imported, "progress.py imports nothing?"
    assert sorted(imported - set(sys.stdlib_module_names)) == []
    assert "reverseapoc" not in imported


@pytest.mark.parametrize("exe", EXES)
def test_reader_agrees_with_reverseapoc(exe):
    progress = load_progress()
    """progress.py's own minimal CSV reader gives the rows reverseapoc's readers give."""
    config = CONFIG / exe
    ours = progress.read_functions(config / "functions.csv")
    theirs = read_functions_csv(config / "functions.csv")
    assert [(r.start, r.end, r.name, r.kind, r.unit) for r in ours] == [
        (r.start, r.end, r.name, r.kind, r.unit) for r in theirs]
    ours_units = progress.read_units(config / "units.csv")
    assert [(u.unit, u.start, u.end) for u in ours_units] == [
        (u.unit, u.start, u.end) for u in read_units_csv(config / "units.csv")]
    ours_status = progress.read_status(status_path(CONFIG, exe))
    assert ours_status, f"config/{exe}/status.csv has no row"
    assert [(r.start, r.name, r.unit, r.status, r.best_percent) for r in ours_status] == [
        (r.start, r.name, r.unit, r.status, r.best_percent)
        for r in read_status(status_path(CONFIG, exe))]


def test_reader_refuses_a_wrong_header(tmp_path):
    progress = load_progress()
    config = synthetic_config(tmp_path)
    path = config / "ufo2p" / "functions.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("evidence", "proof"),
                    encoding="utf-8")  # fmt: skip
    with pytest.raises(progress.ProgressError, match="header"):
        progress.derive(config)


def test_derive_counts_on_synthetic_csvs(tmp_path):
    progress = load_progress()
    """Matched, partial, unmatched, uncovered and library bytes and the percent, by hand: the
    percent is matched / (game + thunk + uncovered), library and data-in-code stay outside it."""
    doc = progress_doc(progress, synthetic_config(tmp_path), tmp_path)
    code = size(U_MATCHED) + size(U_PARTIAL) + size(U_UNMATCHED) + size(U_THUNK)
    ufo = doc["exes"]["ufo2p"]
    assert ufo["label"] == "UFO2P.EXE"
    assert ufo["code_bytes"] == code == 228
    assert ufo["matched_bytes"] == size(U_MATCHED) == 16
    assert ufo["partial_bytes"] == size(U_PARTIAL) == 32
    assert ufo["unmatched_bytes"] == size(U_UNMATCHED) + size(U_THUNK) == 180
    assert ufo["uncovered_bytes"] == GAP == 16
    assert ufo["denominator_bytes"] == 244
    assert ufo["library_bytes"] == size(U_RUNTIME) == 8
    assert ufo["library_functions"] == 1
    assert ufo["data_in_code_bytes"] == size(U_DATA) == 4
    assert ufo["functions"] == {"total": 4, "matched": 1, "partial": 1}
    assert ufo["percent"] == round(100 * 16 / 244, 4) == 6.5574
    tacp = doc["exes"]["tacp"]
    assert (tacp["code_bytes"], tacp["matched_bytes"], tacp["uncovered_bytes"]) == (32, 0, 0)
    assert tacp["percent"] == 0.0
    both = doc["combined"]
    assert (both["code_bytes"], both["matched_bytes"], both["partial_bytes"]) == (260, 16, 32)
    assert (both["uncovered_bytes"], both["denominator_bytes"]) == (16, 276)
    assert both["library_bytes"] == 8
    assert both["functions"] == {"total": 5, "matched": 1, "partial": 1}
    assert both["percent"] == round(100 * 16 / 276, 4) == 5.7971


def test_notes_name_the_filler_and_the_ufo2p_tail(tmp_path):
    progress = load_progress()
    doc = progress_doc(progress, synthetic_config(tmp_path), tmp_path)
    notes = " ".join(doc["notes"])
    assert "filler" in notes and "uncovered" in notes
    assert "0x000CFADA" in notes and "not counted" in notes


def test_uncovered_on_committed_csvs(tmp_path):
    progress = load_progress()
    """D-50 on today's committed CSVs: the bytes inside unit spans in no functions.csv row,
    pinned, and equal to a set computation over reverseapoc's readers."""
    doc = progress_doc(progress, CONFIG, tmp_path)
    for exe in EXES:
        inside = set()
        for unit in read_units_csv(CONFIG / exe / "units.csv"):
            inside.update(range(unit.start, unit.end))
        for row in read_functions_csv(CONFIG / exe / "functions.csv"):
            inside.difference_update(range(row.start, row.end))
        assert doc["exes"][exe]["uncovered_bytes"] == len(inside) == COMMITTED_UNCOVERED[exe]


def test_shield_shape(tmp_path):
    progress = load_progress()
    config = synthetic_config(tmp_path)
    progress.write_shield(progress.derive(config), tmp_path / "progress-shield.json")
    shield = json.loads((tmp_path / "progress-shield.json").read_text(encoding="utf-8"))
    assert set(shield) == {"schemaVersion", "label", "message", "color"}
    assert shield["schemaVersion"] == 1
    assert shield["label"] == "decompiled"
    assert shield["message"] == "5.80%"  # the combined 5.7971, two decimals
    assert shield["message"].endswith("%")
    assert isinstance(shield["color"], str) and shield["color"]


def test_outputs_are_byte_stable_and_atomic(tmp_path, monkeypatch):
    progress = load_progress()
    """Two runs give identical bytes (indent 2, LF, trailing newline); a write whose os.replace
    fails leaves the previous file whole and no temporary file behind."""
    config = synthetic_config(tmp_path)
    first, second = tmp_path / "one", tmp_path / "two"
    for out in (first, second):
        out.mkdir()
        progress.write_progress_json(progress.derive(config), out / "progress.json")
        progress.write_shield(progress.derive(config), out / "progress-shield.json")
    for name in ("progress.json", "progress-shield.json"):
        data = (first / name).read_bytes()
        assert data == (second / name).read_bytes()
        assert data.endswith(b"}\n") and b"\r" not in data
    before = (first / "progress.json").read_bytes()
    write_status(status_path(config, "tacp"), [
        StatusRow(T_GAME.start, T_GAME.name, T_GAME.unit, MATCHED, 100.0, 0, SHA, DAY)])

    def broken_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(progress.os, "replace", broken_replace)
    with pytest.raises(OSError, match="disk full"):
        progress.write_progress_json(progress.derive(config), first / "progress.json")
    assert (first / "progress.json").read_bytes() == before
    assert sorted(p.name for p in first.iterdir()) == ["progress-shield.json", "progress.json"]


def test_script_runs_isolated(tmp_path):
    """`python -I tools/progress.py --out DIR` runs with no venv and no reverseapoc on the path,
    and creates DIR (ruling F17)."""
    out = tmp_path / "site" / "deep"
    done = subprocess.run([sys.executable, "-I", str(PROGRESS), "--out", str(out)],
                          capture_output=True, text=True, timeout=120)  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert json.loads((out / "progress.json").read_text(encoding="utf-8"))["exes"]
    assert json.loads((out / "progress-shield.json").read_text(encoding="utf-8"))["label"]


def test_main_creates_every_output_parent(tmp_path):
    progress = load_progress()
    """Ruling F17: main creates the parent directory of every output it writes."""
    config = synthetic_config(tmp_path)
    out = tmp_path / "a" / "b"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    assert (out / "progress.json").is_file() and (out / "progress-shield.json").is_file()
