"""tools/progress.py (RPT-02, D-26, D-40, D-50): the committed CSVs become progress.json and the
shield endpoints (combined and per EXE). progress.py runs under the Pages runner's system
`python3 -I` (D-27), so it is a stdlib script loaded here by path, the way check._configure loads
configure.py. The synthetic tables use made-up addresses and names; the committed-file tests read
config/ only (no game bytes)."""

from __future__ import annotations

import ast
import functools
import importlib.util
import json
import re
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
    """progress.py's own minimal CSV reader gives the rows reverseapoc's readers give."""
    progress = load_progress()
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
    """Matched, partial, unmatched, uncovered and library bytes and the percent, by hand: the
    percent is matched / (game + thunk + uncovered), library and data-in-code stay outside it."""
    progress = load_progress()
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
    """D-50 on today's committed CSVs: the bytes inside unit spans in no functions.csv row,
    pinned, and equal to a set computation over reverseapoc's readers."""
    progress = load_progress()
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
    assert shield["message"] == "5.7971%"  # the combined percent as progress.json has it
    assert shield["message"].endswith("%")
    assert isinstance(shield["color"], str) and shield["color"]


@pytest.mark.parametrize(("value", "message"), [(0.0016, "0.0016%"), (5.7971, "5.7971%"),
                                                (12.5, "12.5%"), (100.0, "100%"), (0.0, "0%")])
def test_shield_message_keeps_small_percents(value, message):
    """Today's figure is a few thousandths of a percent: two decimals would publish 0.00%."""
    assert load_progress().shield_message(value) == message


def test_outputs_are_byte_stable_and_atomic(tmp_path, monkeypatch):
    """Two runs give identical bytes (indent 2, LF, trailing newline); a write whose os.replace
    fails leaves the previous file whole and no temporary file behind."""
    progress = load_progress()
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
    for stem in EXES:
        shield = json.loads((out / f"progress-shield-{stem}.json").read_text(encoding="utf-8"))
        assert shield["label"] == EXE_NAMES[stem]


def test_exe_shield_shape(tmp_path):
    """Owner ruling 1 (2026-10-26): one shields.io endpoint document per EXE, labelled with the
    EXE and coloured by its own percent, keys in the combined document's order."""
    progress = load_progress()
    assert hasattr(progress, "build_exe_shield"), "progress.py has no build_exe_shield"
    derived = progress.derive(synthetic_config(tmp_path))
    ufo = progress.build_exe_shield(derived.exe("ufo2p"))
    assert ufo == {"schemaVersion": 1, "label": "UFO2P.EXE", "message": "6.5574%",
                   "color": "orange"}  # fmt: skip
    tacp = progress.build_exe_shield(derived.exe("tacp"))
    assert tacp == {"schemaVersion": 1, "label": "TACP.EXE", "message": "0%", "color": "red"}
    for doc in (ufo, tacp):
        assert list(doc) == ["schemaVersion", "label", "message", "color"]
        assert list(doc) == list(progress.build_shield(derived))


def test_main_writes_one_shield_per_exe(tmp_path):
    """--out writes progress-shield-<stem>.json per EXE, byte-stable and atomic, next to the
    combined progress-shield.json, which keeps its label and figure."""
    progress = load_progress()
    assert hasattr(progress, "build_exe_shield"), "progress.py has no build_exe_shield"
    config = synthetic_config(tmp_path)
    first, second = tmp_path / "one", tmp_path / "two"
    for out in (first, second):
        assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    derived = progress.derive(config)
    for stem in EXES:
        name = f"progress-shield-{stem}.json"
        data = (first / name).read_bytes()
        assert data == progress.render(progress.build_exe_shield(derived.exe(stem)))
        assert data.endswith(b"}\n") and b"\r" not in data
        assert data == (second / name).read_bytes()
    assert not list(first.glob(".*.tmp"))
    combined = json.loads((first / "progress-shield.json").read_text(encoding="utf-8"))
    assert (combined["label"], combined["message"]) == ("decompiled", "5.7971%")


def test_main_creates_every_output_parent(tmp_path):
    """Ruling F17: main creates the parent directory of every output it writes."""
    progress = load_progress()
    config = synthetic_config(tmp_path)
    out = tmp_path / "a" / "b"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    assert (out / "progress.json").is_file() and (out / "progress-shield.json").is_file()


# ---- Task 2: the DecompHub progress-v1 feed (D-29) ----

# from decomphub.com/schemas/progress-v1.json, 2026-10-24
FEED_FORMAT = "decomphub.progress/v1"
FEED_TOP_REQUIRED = frozenset({"format", "repository", "tracks"})
FEED_REPOSITORY_MAX = 2048
FEED_TRACKS_MIN, FEED_TRACKS_MAX = 1, 20
TRACK_REQUIRED = frozenset({"id", "label", "scope", "measurement"})
TRACK_OPTIONAL = frozenset({"measuredAt"})
TRACK_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
LABEL_MAX, SCOPE_MAX, UNIT_MAX = 120, 300, 40
PERCENT_KEYS = frozenset({"kind", "value", "valueMax", "approximate"})
RATIO_KEYS = frozenset({"kind", "completed", "total", "unit", "approximate"})
# D-29
REPOSITORY = "https://github.com/ayrtondenner/ReverseApoc"
TRACK_IDS = ["ufo2p-code", "tacp-code", "ufo2p-functions", "tacp-functions"]


def check_progress_v1(doc: dict) -> None:
    """Every progress-v1 rule a test can check without the network."""
    assert set(doc) == FEED_TOP_REQUIRED  # D-29: no revision (a file cannot hold its own hash)
    assert doc["format"] == FEED_FORMAT
    assert doc["repository"] == REPOSITORY and len(doc["repository"]) <= FEED_REPOSITORY_MAX
    tracks = doc["tracks"]
    assert FEED_TRACKS_MIN <= len(tracks) <= FEED_TRACKS_MAX
    assert [t["id"] for t in tracks] == TRACK_IDS
    assert len({t["id"] for t in tracks}) == len(tracks)
    for track in tracks:
        assert TRACK_REQUIRED <= set(track) <= TRACK_REQUIRED | TRACK_OPTIONAL, track
        assert TRACK_ID.fullmatch(track["id"]), track["id"]
        assert 1 <= len(track["label"]) <= LABEL_MAX and 1 <= len(track["scope"]) <= SCOPE_MAX
        check_measurement(track["measurement"])


def check_measurement(m: dict | None) -> None:
    if m is None:
        return
    if m["kind"] == "percent":
        assert set(m) <= PERCENT_KEYS and isinstance(m["value"], int | float)
        assert 0 <= m["value"] <= 100
        return
    assert m["kind"] == "ratio" and set(m) <= RATIO_KEYS
    assert isinstance(m["completed"], int) and isinstance(m["total"], int)
    assert 0 <= m["completed"] <= m["total"] and m["total"] > 0
    assert m["unit"] == "functions" and 1 <= len(m["unit"]) <= UNIT_MAX


def feed(config: Path) -> dict:
    progress = load_progress()
    assert hasattr(progress, "build_decomphub"), "progress.py has no build_decomphub"
    return progress.build_decomphub(progress.derive(config))


def test_decomphub_feed_follows_progress_v1(tmp_path):
    for config in (synthetic_config(tmp_path), CONFIG):
        check_progress_v1(feed(config))


def test_decomphub_feed_values(tmp_path):
    """Code tracks are progress.json's percents, function tracks matched over game+thunk."""
    tracks = {t["id"]: t["measurement"] for t in feed(synthetic_config(tmp_path))["tracks"]}
    assert tracks["ufo2p-code"] == {"kind": "percent", "value": 6.5574}
    assert tracks["tacp-code"] == {"kind": "percent", "value": 0.0}
    assert tracks["ufo2p-functions"] == {"kind": "ratio", "completed": 1, "total": 4,
                                         "unit": "functions"}  # fmt: skip
    assert tracks["tacp-functions"] == {"kind": "ratio", "completed": 0, "total": 1,
                                        "unit": "functions"}  # fmt: skip


def test_decomphub_feed_is_byte_stable(tmp_path):
    progress = load_progress()
    config = synthetic_config(tmp_path)
    for name in ("a.json", "b.json"):
        progress.write_decomphub(progress.derive(config), tmp_path / name)
    data = (tmp_path / "a.json").read_bytes()
    assert data == (tmp_path / "b.json").read_bytes()
    assert data == progress.render(feed(config)) and data.endswith(b"}\n")


def test_main_writes_report_and_feed(tmp_path):
    """--report and --decomphub write their files, creating their directories (ruling F17)."""
    progress = load_progress()
    config = synthetic_config(tmp_path)
    report, hub = tmp_path / "c" / "report.json", tmp_path / "d" / "decomphub.progress.json"
    assert progress.main(["--config", str(config), "--report", str(report),
                          "--decomphub", str(hub)]) == 0  # fmt: skip
    assert json.loads(report.read_text(encoding="utf-8"))["version"] == 2
    check_progress_v1(json.loads(hub.read_text(encoding="utf-8")))
    assert not (tmp_path / "progress.json").exists()
