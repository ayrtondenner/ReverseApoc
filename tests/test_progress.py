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
from reverseapoc import mechanics
from reverseapoc.functions import (
    FunctionRow,
    UnitRow,
    read_functions_csv,
    read_units_csv,
    write_functions_csv,
    write_units_csv,
)
from reverseapoc.mechanics import MemberRow
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


# ---- the mechanics coverage view (DEC-05; D-05, D-22, D-23; plan 07-15) ----

TIER_ONE = '[[tier]]\nid = 1\ntitle = "Tick rate and agent training"\n'
ENTRY_997 = ('[[entry]]\nitem = "997"\nexe = "ufo2p"\naddress = "0x00010000"\n'
             'evidence = "bios-tick"\ndetail = "reads the BIOS tick counter"\n')  # fmt: skip
MUST_997 = {"functions": {"total": 3, "matched": 1, "partial": 1, "unmatched": 1},
            "bytes": {"total": 112, "matched": 16, "partial": 32},
            "percent": round(100 * 16 / 112, 4)}  # fmt: skip
CLOSURE_997 = {"functions": {"total": 5, "matched": 1, "partial": 1, "unmatched": 3},
               "bytes": {"total": 260, "matched": 16, "partial": 32},
               "percent": round(100 * 16 / 260, 4)}  # fmt: skip


def item_toml(item_id: str, title: str, *, tier: int = 1, scope: str = "in",
              exes: tuple[str, ...] = EXES, duplicate_of: str = "") -> str:  # fmt: skip
    """One [[item]] table in mechanics.toml's 07-10 format."""
    lines = ["[[item]]", f'id = "{item_id}"', f"issue = {item_id.split('-')[0]}",
             f'title = "{title}"', f"tier = {tier}", f'scope = "{scope}"']  # fmt: skip
    if scope == "in":
        lines.append("exes = [" + ", ".join(f'"{exe}"' for exe in exes) + "]")
    if scope == "duplicate":
        lines.append(f'duplicate_of = "{duplicate_of}"')
    if scope == "out":
        lines.append('reason = "not in the original game"')
    return "\n".join(lines) + "\n"


def write_mechanics(config: Path, *tables: str, members=None) -> None:
    """config/mechanics.toml from `tables` (checked by 07-10's own loader, so the synthetic file
    is valid committed data) and, given `members`, config/mechanics-members.csv written by
    07-10's own writer."""
    path = config / "mechanics.toml"
    path.write_bytes(("schema = 1\n\n" + "\n".join(tables)).encode("ascii"))
    mechanics.load(path)
    if members is not None:
        mechanics.write_members(config / mechanics.MEMBERS_CSV, members)


def member(exe: str, row, items: tuple[str, ...], member_items: tuple[str, ...] = (),
           *, tiers: tuple[int, ...] = (1,), via: str = "direct") -> MemberRow:  # fmt: skip
    """A members row: role member when it has member items, else closure."""
    role = "member" if member_items else "closure"
    return MemberRow(exe, row.start, items, tiers, member_items, via, role)


def tick_members() -> list[MemberRow]:
    """Item 997: three UFO2P member rows (matched, partial, unmatched) and two closure rows (the
    UFO2P thunk and the TACP game row)."""
    one = ("997",)
    return [member("ufo2p", U_MATCHED, one, one, via="entry"),
            member("ufo2p", U_PARTIAL, one, one), member("ufo2p", U_UNMATCHED, one, one),
            member("ufo2p", U_THUNK, one), member("tacp", T_GAME, one, via="pointer")]


def tick_config(root: Path) -> Path:
    config = synthetic_config(root)
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"), ENTRY_997,
                    members=tick_members())  # fmt: skip
    return config


def mechanics_module():
    """progress.py with its mechanics API; a missing name fails the test on this assert."""
    progress = load_progress()
    for name in ("derive_mechanics", "Mechanics", "ItemCoverage", "TierCoverage"):
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def test_mechanics_absent_gives_null(tmp_path):
    """DEC-05 empty: without mechanics.toml, progress.json says "mechanics": null (version 1)
    and the page has no coverage section, byte for byte the page it was before."""
    progress = load_progress()
    config = synthetic_config(tmp_path)
    derived = progress.derive(config)
    doc = progress.build_progress(derived)
    assert doc["version"] == 1 and "mechanics" in doc and doc["mechanics"] is None
    assert mechanics_module().derive_mechanics(config, derived) is None
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    written = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    assert written["mechanics"] is None
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "Mechanics coverage" not in page
    assert page == progress.render_html(derived) == progress.render_html(derived, mechanics=None)


def test_item_figures(tmp_path):
    """D-22: an item's must-match set (role member rows naming it in member_items) and its full
    closure (every row naming it in items, asm rows aside), from status.csv's matched and
    partial rows: 3 members (1 matched, 1 partial) plus 2 closure rows."""
    progress = mechanics_module()
    config = tick_config(tmp_path)
    derived = progress.derive(config)
    found = progress.derive_mechanics(config, derived)
    doc = progress.build_progress(derived, mechanics=found)["mechanics"]
    (item,) = doc["items"]
    assert (item["id"], item["issue"], item["title"], item["tier"]) == ("997", 997, "Tick rate", 1)
    assert (item["signed_off_by"], item["signed_off_date"]) == (None, None)
    assert item["must_match"] == MUST_997
    assert item["full_closure"] == CLOSURE_997
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    written = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    assert written["mechanics"] == json.loads(progress.render(doc))
    assert written["version"] == 1


def test_malformed_member_exits_2(tmp_path):
    """A members row on a runtime row of functions.csv is refused (ProgressError), and the Pages
    job's `main` exits 2."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    stray = member("ufo2p", U_RUNTIME, ("997",), ("997",))
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"), ENTRY_997,
                    members=[*tick_members(), stray])  # fmt: skip
    with pytest.raises(progress.ProgressError, match="0x00010070"):
        progress.derive_mechanics(config, progress.derive(config))
    assert progress.main(["--config", str(config), "--out", str(tmp_path / "out")]) == 2


def write_asm_list(config: Path, verdict: str = "asm") -> Path:
    """config/asm-functions.csv in 07-10's format: the UFO2P unmatched row, with `verdict`."""
    path = config / mechanics.ASM_CSV
    rows = [mechanics.AsmRow("ufo2p", U_UNMATCHED.start, "off-alignment start", verdict)]
    path.write_bytes(mechanics.format_asm_csv(rows).encode("ascii"))
    return path


def asm_signoff(path: Path) -> str:
    """An [asm_list] table that signs the list at `path` off."""
    return (f'[asm_list]\nsigned_off_by = "Owner"\nsigned_off_date = 2026-10-27\n'
            f'list_sha256 = "{mechanics.asm_list_sha256(path)}"\n')  # fmt: skip


def test_schema_only_mechanics_and_asm_list_exit_0(tmp_path):
    """Ruling F2: plan 07-20 commits a schema-only mechanics.toml and an unsigned asm list before
    any members file exists: no items, and the Pages job still exits 0."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    write_asm_list(config)
    write_mechanics(config)
    found = progress.derive_mechanics(config, progress.derive(config))
    assert found is not None and found.items == () and found.tiers == ()
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    doc = json.loads((out / "progress.json").read_text(encoding="utf-8"))["mechanics"]
    assert doc == {"tiers": [], "items": [], "duplicates": []}


def test_members_file_absent_gives_no_items(tmp_path):
    """Ruling F2: a mechanics.toml with items but no members file yet has no items to show."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"), ENTRY_997)
    found = progress.derive_mechanics(config, progress.derive(config))
    assert found is not None and found.items == ()
    assert progress.main(["--config", str(config), "--out", str(tmp_path / "out")]) == 0


def test_every_mechanics_table_is_accepted(tmp_path):
    """Ruling F2: every 07-10 table (schema, asm_list, hub_rule, tier, item, entry, edge) is
    accepted; the page reads tiers and items only."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    hub_rule = "[hub_rule]\nmin_direct_callers = 10\nmin_items = 2\n"
    edge = ('[[edge]]\nexe = "ufo2p"\nfrom = "0x00010000"\nto = "0x00010030"\n'
            'evidence = "a call through a table read by hand"\n')  # fmt: skip
    write_mechanics(config, asm_signoff(write_asm_list(config, "c")), hub_rule, TIER_ONE,
                    item_toml("997", "Tick rate"),
                    item_toml("263-9", "Not in the game", scope="out"),
                    item_toml("264-1", "Tick rate again", scope="duplicate", duplicate_of="997"),
                    ENTRY_997, edge, members=tick_members())  # fmt: skip
    found = progress.derive_mechanics(config, progress.derive(config))
    assert [item.id for item in found.items] == ["997"]
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0


@pytest.mark.parametrize("text", ["schema = 1\nsurprise = 1\n", "schema = 2\n",
                                  "schema = 1\n[[item]\n", "schema = 1\ntier = 3\n"])
def test_malformed_mechanics_toml_exits_2(tmp_path, text):
    """An unknown top-level key, a wrong schema, broken TOML or a table of the wrong shape is a
    ProgressError: the Pages job exits 2."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    (config / "mechanics.toml").write_bytes(text.encode("ascii"))
    with pytest.raises(progress.ProgressError, match="mechanics.toml"):
        progress.derive_mechanics(config, progress.derive(config))
    assert progress.main(["--config", str(config), "--out", str(tmp_path / "out")]) == 2


# ---- Task 2: tier unions, duplicates, located tiers, the assembler group (D-05, D-22, D-23) ----

SIGNED = 'signed_off_by = "Owner"\nsigned_off_date = 2026-10-27\nmembers_sha256 = "' + "b" * 64
TIER_TWO = f'[[tier]]\nid = 2\ntitle = "The rest of the agents"\n{SIGNED}"\n'
TIER_THREE = '[[tier]]\nid = 3\ntitle = "Vehicles"\n'


def shared_members() -> list[MemberRow]:
    """Items 997 and 263-1 (both tier 1) share the partial row as a member."""
    both, tick, agents = ("263-1", "997"), ("997",), ("263-1",)
    return [member("ufo2p", U_MATCHED, tick, tick, via="entry"),
            member("ufo2p", U_PARTIAL, both, both),
            member("ufo2p", U_UNMATCHED, agents, agents, via="entry"),
            member("ufo2p", U_THUNK, both)]  # fmt: skip


def shared_config(root: Path) -> Path:
    config = synthetic_config(root)
    entry = ENTRY_997.replace('"997"', '"263-1"').replace("0x00010000", "0x00010030")
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"),
                    item_toml("263-1", "Agent training"), ENTRY_997, entry,
                    members=shared_members())  # fmt: skip
    return config


def mechanics_doc(progress, config: Path) -> dict:
    derived = progress.derive(config)
    return progress.build_progress(derived, mechanics=progress.derive_mechanics(config, derived))[
        "mechanics"]


def test_tier_union_counts_once(tmp_path):
    """DEC-05 adjacency: a function two items share counts in both items' figures and once in
    their tier's."""
    progress = mechanics_module()
    doc = mechanics_doc(progress, shared_config(tmp_path))
    items = {item["id"]: item for item in doc["items"]}
    assert items["997"]["must_match"]["functions"] == {"total": 2, "matched": 1, "partial": 1,
                                                       "unmatched": 0}  # fmt: skip
    assert items["263-1"]["must_match"]["functions"] == {"total": 2, "matched": 0, "partial": 1,
                                                         "unmatched": 1}  # fmt: skip
    (tier,) = doc["tiers"]
    assert tier["must_match"]["functions"] == {"total": 3, "matched": 1, "partial": 1,
                                               "unmatched": 1}  # fmt: skip
    assert tier["must_match"]["bytes"] == {"total": 112, "matched": 16, "partial": 32}
    assert tier["full_closure"]["functions"]["total"] == 4
    assert tier["full_closure"]["bytes"]["total"] == 112 + size(U_THUNK)
    assert items["997"]["full_closure"]["functions"]["total"] == 3


def test_zero_member_item(tmp_path):
    """DEC-05 empty: an `in` item no members row names has 0 of 0, percent 0.0 (not objdiff's
    100.0 for an empty total), and no division by zero."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"),
                    item_toml("263-2", "Not reached yet"), ENTRY_997,
                    members=tick_members())  # fmt: skip
    items = {item["id"]: item for item in mechanics_doc(progress, config)["items"]}
    empty = {"functions": {"total": 0, "matched": 0, "partial": 0, "unmatched": 0},
             "bytes": {"total": 0, "matched": 0, "partial": 0}, "percent": 0.0}  # fmt: skip
    assert items["263-2"]["must_match"] == empty
    assert items["263-2"]["full_closure"] == empty


def test_located_tier_reads_located(tmp_path):
    """D-05: an unsigned tier with members reads located and not signed off; a signed one reads
    who signed it and when; a tier no row reaches reads not located yet. None reads matched."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    agents = ("263-1",)
    members = [*tick_members()[:3],
               member("ufo2p", U_THUNK, agents, agents, tiers=(2,), via="entry")]  # fmt: skip
    entry = ENTRY_997.replace('"997"', '"263-1"').replace("0x00010000", "0x0001008C")
    write_mechanics(config, TIER_ONE, TIER_TWO, TIER_THREE, item_toml("997", "Tick rate"),
                    item_toml("263-1", "Agent training", tier=2),
                    item_toml("265-1", "Vehicle repair", tier=3), ENTRY_997, entry,
                    members=members)  # fmt: skip
    doc = mechanics_doc(progress, config)
    tiers = {tier["id"]: tier for tier in doc["tiers"]}
    assert (tiers[1]["state"], tiers[1]["signed_off_by"]) == ("located", None)
    assert (tiers[2]["state"], tiers[2]["signed_off_by"]) == ("located", "Owner")
    assert tiers[2]["signed_off_date"] == "2026-10-27"
    assert (tiers[3]["state"], tiers[3]["signed_off_by"]) == ("not located yet", None)
    items = {item["id"]: item for item in doc["items"]}
    assert (items["263-1"]["signed_off_by"], items["263-1"]["signed_off_date"]) == (
        "Owner", "2026-10-27")


def test_tier_reads_matched_only_from_status(tmp_path):
    """RPT-01: a tier reads matched only when status.csv says every must-match function is."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    tick = ("997",)
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"), ENTRY_997,
                    members=[member("ufo2p", U_MATCHED, tick, tick, via="entry"),
                             member("ufo2p", U_THUNK, tick)])  # fmt: skip
    assert mechanics_doc(progress, config)["tiers"][0]["state"] == "matched"
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"), ENTRY_997,
                    members=[member("ufo2p", U_MATCHED, tick, tick, via="entry"),
                             member("ufo2p", U_PARTIAL, tick, tick)])  # fmt: skip
    assert mechanics_doc(progress, config)["tiers"][0]["state"] == "located"


def test_duplicates_listed_once(tmp_path):
    """A duplicate item is listed once, by the item it duplicates, never with figures."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"),
                    item_toml("264-1", "Tick rate again", scope="duplicate", duplicate_of="997"),
                    ENTRY_997, members=tick_members())  # fmt: skip
    doc = mechanics_doc(progress, config)
    assert [item["id"] for item in doc["items"]] == ["997"]
    assert doc["duplicates"] == [{"id": "264-1", "issue": 264, "title": "Tick rate again",
                                  "duplicate_of": "997"}]  # fmt: skip


def test_ordering_and_determinism(tmp_path):
    """DEC-05 ordering: items by tier, issue, item number, whatever the TOML's order; two runs
    over the same config give the same bytes."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    write_mechanics(config, TIER_ONE, TIER_TWO, item_toml("263-1", "Agents", tier=2),
                    item_toml("997", "Tick rate"), item_toml("263-3", "Third"),
                    item_toml("263-2", "Second"), ENTRY_997, members=tick_members())  # fmt: skip
    assert [item["id"] for item in mechanics_doc(progress, config)["items"]] == [
        "263-2", "263-3", "997", "263-1"]
    first, second = tmp_path / "one", tmp_path / "two"
    for out in (first, second):
        assert progress.main(["--config", str(config), "--out", str(out), "--commit", SHA]) == 0
    for name in ("progress.json", "index.html", "progress.svg"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_mechanics_constants_agree():
    """progress.py's own copies of 07-10's formats equal reverseapoc.mechanics' (progress.py
    cannot import it under -I)."""
    progress = mechanics_module()
    for name in ("ASM_CSV", "ASM_COLUMNS", "ASM_VERDICTS"):
        assert hasattr(progress, name), f"progress.py has no {name}"
    assert progress.MECHANICS_TOML == mechanics.MECHANICS_TOML
    assert progress.MEMBERS_CSV == mechanics.MEMBERS_CSV
    assert progress.MEMBERS_COLUMNS == mechanics.MEMBERS_COLUMNS
    assert progress.ROLES == mechanics.ROLES and progress.SCOPES == mechanics.SCOPES
    assert progress.VIAS == mechanics.VIAS and progress.MECHANICS_SCHEMA == mechanics.SCHEMA
    assert progress.MECHANICS_TABLES == mechanics._TOP_KEYS
    assert progress.ASM_CSV == mechanics.ASM_CSV
    assert progress.ASM_COLUMNS == mechanics.ASM_COLUMNS
    assert progress.ASM_VERDICTS == mechanics.ASM_VERDICTS


def asm_config(root: Path) -> Path:
    """The synthetic config with a signed asm list marking the UFO2P unmatched row (64 bytes)."""
    config = synthetic_config(root)
    write_mechanics(config, asm_signoff(write_asm_list(config)))
    return config


ASM_PERCENT = round(100 * 16 / (228 - 64 + 16), 4)  # 8.8889


def test_assembler_group(tmp_path):
    """D-23: a signed asm list moves its rows out of the EXE's percent into an assembler group,
    counted like the library, in progress.json, the shields and report.json."""
    progress = mechanics_module()
    assert hasattr(progress, "exclude_assembler"), "progress.py has no exclude_assembler"
    config = asm_config(tmp_path)
    derived = progress.derive(config)
    found = progress.derive_mechanics(config, derived)
    assert found.assembler == (("ufo2p", U_UNMATCHED.start),)
    shown = progress.exclude_assembler(derived, found.assembler)
    ufo = shown.exe("ufo2p")
    assert [f.start for f in ufo.functions] == [U_MATCHED.start, U_PARTIAL.start, U_THUNK.start]
    assert [r.start for r in ufo.assembler_rows] == [U_UNMATCHED.start]
    assert shown.exe("tacp") == derived.exe("tacp")
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out), "--report",
                          str(out / "report.json")]) == 0  # fmt: skip
    doc = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    exe = doc["exes"]["ufo2p"]
    assert (exe["code_bytes"], exe["assembler_bytes"], exe["assembler_functions"]) == (164, 64, 1)
    assert exe["functions"] == {"total": 3, "matched": 1, "partial": 1}
    assert (exe["library_bytes"], exe["percent"]) == (8, ASM_PERCENT)
    both = doc["combined"]
    assert (both["assembler_bytes"], both["code_bytes"]) == (64, 196)
    assert doc["exes"]["tacp"]["assembler_functions"] == 0
    shield = json.loads((out / "progress-shield-ufo2p.json").read_text(encoding="utf-8"))
    assert shield["message"] == f"{ASM_PERCENT}%"
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["measures"]["matched_code_percent"] == both["percent"]


def test_unsigned_asm_list_moves_nothing(tmp_path):
    """Ruling F2: an asm list not yet signed off in [asm_list] (07-20 commits one before the
    owner's ruling) leaves the figures as they were, without an error."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    write_asm_list(config)
    write_mechanics(config)
    found = progress.derive_mechanics(config, progress.derive(config))
    assert hasattr(found, "assembler"), "Mechanics has no assembler"
    assert found.assembler == ()
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    doc = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    assert (doc["exes"]["ufo2p"]["assembler_functions"], doc["exes"]["ufo2p"]["code_bytes"]) == (
        0, 228)


@pytest.mark.parametrize("change", ["edited", "deleted"])
def test_stale_signed_asm_list_exits_2(tmp_path, change):
    """Fix round 1: once [asm_list] signs the list off, a list edited since its sign-off or
    deleted is refused (as mechanics.signed_asm refuses it), so the Pages job exits 2 instead of
    silently putting the asm rows back into the published percentage."""
    progress = mechanics_module()
    config = asm_config(tmp_path)
    found = progress.derive_mechanics(config, progress.derive(config))
    assert found.assembler == (("ufo2p", U_UNMATCHED.start),)  # signed and matching: excluded
    path = config / mechanics.ASM_CSV
    if change == "edited":
        path.write_bytes(path.read_bytes() + b"ufo2p,0x00010000,off-alignment start,c,\n")
    else:
        path.unlink()
    with pytest.raises(progress.ProgressError, match=r"asm-functions\.csv.*re-sign"):
        progress.derive_mechanics(config, progress.derive(config))
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 2
    assert not (out / "progress.json").exists()


def test_asm_row_off_a_game_row_exits_2(tmp_path):
    """A signed asm row that is not a game or thunk row of functions.csv is refused."""
    progress = mechanics_module()
    config = synthetic_config(tmp_path)
    path = config / mechanics.ASM_CSV
    rows = [mechanics.AsmRow("ufo2p", U_RUNTIME.start, "off-alignment start", "asm")]
    path.write_bytes(mechanics.format_asm_csv(rows).encode("ascii"))
    write_mechanics(config, asm_signoff(path))
    with pytest.raises(progress.ProgressError, match="0x00010070"):
        progress.derive_mechanics(config, progress.derive(config))
    assert progress.main(["--config", str(config), "--out", str(tmp_path / "out")]) == 2


def test_feed_ignores_the_asm_list(tmp_path):
    """T-07-44: gate's DecompHub feed, build_decomphub(derive(config)), is byte-identical with
    and without a signed asm list, and so is main's --decomphub output: committing the list
    never stales the gate-written feed."""
    progress = load_progress()
    config = synthetic_config(tmp_path / "plain")
    before = progress.render(progress.build_decomphub(progress.derive(config)))
    with_asm = asm_config(tmp_path / "asm")
    assert progress.render(progress.build_decomphub(progress.derive(with_asm))) == before
    hub = tmp_path / "hub.json"
    assert progress.main(["--config", str(with_asm), "--decomphub", str(hub)]) == 0
    assert hub.read_bytes() == before
