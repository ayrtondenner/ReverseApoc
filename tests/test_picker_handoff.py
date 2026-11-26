"""Todo long-tail-handoff-board, the picker side: config/handoff.csv lists the functions retired
from every agent queue, and every queue skips them. Every address below is made up."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from reverseapoc import driver, picker
from reverseapoc.functions import read_functions_csv
from reverseapoc.picker import PickerError
from reverseapoc.status import MATCHED, STATUS_FILE, read_status
from reverseapoc.targets import REPO_ROOT
from test_driver_pick import (
    TA,
    TB,
    TC,
    TS,
    UFO2P,
    _member,
    _nm_rig,
    _picks_file,
    _rig_world,
    _signed_rig,
    _tq,
)

HEADER = "exe,address,reason,retired_on,return_rule\n"
RULE = "returns when the owner deletes this row (a new model or tool to try)"


def _board(rows: list[str]) -> str:
    return HEADER + "".join(f"{row}\n" for row in rows)


def _row(exe: str, address: int, *, reason: str = "4 models capped", date: str = "2026-11-18",
         rule: str = RULE) -> str:  # fmt: skip
    return f"{exe},0x{address:08X},{reason},{date},{rule}"


def test_the_committed_board_has_the_fixed_header():
    """The progress page reads the board by this exact header, so it never changes."""
    path = REPO_ROOT / "config" / picker.HANDOFF_CSV
    assert path.read_text(encoding="utf-8").splitlines()[0] == HEADER.strip()
    assert ",".join(picker.HANDOFF_HEADER) == HEADER.strip()
    assert isinstance(picker.read_handoff(path), frozenset)


def test_read_handoff(tmp_path):
    path = tmp_path / "handoff.csv"
    path.write_text(_board([_row("ufo2p", TA), _row("tacp", TB)]), encoding="utf-8")
    assert picker.read_handoff(path) == {(UFO2P, TA), ("tacp", TB)}


def test_a_missing_board_retires_nothing(tmp_path):
    assert picker.read_handoff(tmp_path / "handoff.csv") == frozenset()


@pytest.mark.parametrize(("text", "where"), [
    ("exe,address,reason\n", "header"),
    (_board([_row("ufo3", TA)]), "line 2"),
    (_board([f"ufo2p,0x{TA:X},r,2026-11-18,{RULE}"]), "line 2"),
    (_board([_row("ufo2p", TA, reason="")]), "reason"),
    (_board([_row("ufo2p", TA, rule="")]), "return_rule"),
    (_board([_row("ufo2p", TA, date="18/11/2026")]), "retired_on"),
    (_board([_row("ufo2p", TA), _row("ufo2p", TA)]), "line 3"),
    (_board(["ufo2p,0x00020000,r,2026-11-18"]), "line 2"),
])  # fmt: skip
def test_read_handoff_refuses_a_bad_board(tmp_path, text, where):
    path = tmp_path / "handoff.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PickerError, match=where):
        picker.read_handoff(path)


def test_tier_queue_leaves_retired_rows_out_and_nothing_waits_on_them():
    """A retired row is never queued, its caller does not wait on it, and it is no held row."""
    rows = [_member(a) for a in (TA, TB, TC)]
    q = _tq(rows, [(TA, TB), (TB, TC)], retired=frozenset({(UFO2P, TB)}))
    assert [i.pick.start for i in q.preview(10)] == [TA, TC]  # both leaves now, by rank
    assert q.held == ()


def _retire(rig, *keys) -> None:
    from test_drive import _git

    path = rig.repo / "config" / picker.HANDOFF_CSV
    path.write_text(_board([_row(exe, start) for exe, start in keys]), encoding="utf-8",
                    newline="\n")  # fmt: skip
    _git(rig.repo, rig.env, "add", "--", "config/handoff.csv")
    _git(rig.repo, rig.env, "commit", "-q", "-m", "hand-off board (made up)")


def test_a_dry_run_skips_board_rows_on_the_tier_and_near_miss_lanes(tmp_path, capsys):
    """_nm_rig's tier lane is TC (TB is a near-miss row); with TS and TC on the board the near-miss
    lane holds TB alone and the tier lane nothing."""
    rig, worlds = _nm_rig(tmp_path)
    _retire(rig, (UFO2P, TS), (UFO2P, TC))
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, near_miss=80.0,
                             seams={"world": lambda: worlds})  # fmt: skip
    assert code == 0, out
    assert [int(p["start"], 16) for p in json.loads(out)["picks"]] == [TB]


def test_pools_skip_board_rows(tmp_path):
    from test_drive import BASE, Rig
    from test_drive import _world as _pools_world

    rig = Rig(tmp_path / "rig")
    retired = (UFO2P, BASE[UFO2P])
    _retire(rig, retired)
    deps = driver.real_deps(rig.options(), rig.seams(), _pools_world(rig.packs))
    keys = [(p.exe, p.start) for p in deps.queue(frozenset())]
    assert keys and retired not in keys


def test_picks_on_the_board_are_refused(tmp_path, capsys):
    rows = [_member(a) for a in (TA, TB)]
    rig = _signed_rig(tmp_path, rows)
    worlds = _rig_world(rig.packs, (TA, TB), ())
    _retire(rig, (UFO2P, TA))
    picks = _picks_file(tmp_path, [(UFO2P, TA), (UFO2P, TB)])
    code, out, _ = rig.drive(capsys, json=True, picks=picks, seams={"world": lambda: worlds})
    assert code == 2
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "picks")
    assert f"on the hand-off board ({picker.HANDOFF_CSV}): ufo2p 0x{TA:08X}" in doc["detail"]
    assert f"0x{TB:08X}" not in doc["detail"]


def test_a_malformed_board_refuses_the_drive(tmp_path, capsys):
    from test_drive import _git

    rig, worlds = _nm_rig(tmp_path)
    path: Path = rig.repo / "config" / picker.HANDOFF_CSV
    path.write_text("exe,address\n", encoding="utf-8", newline="\n")
    _git(rig.repo, rig.env, "add", "--", "config/handoff.csv")
    _git(rig.repo, rig.env, "commit", "-q", "-m", "a malformed board (made up)")
    code, out, _ =rig.drive(capsys, dry_run=True, json=True, seams={"world": lambda: worlds})
    assert code == 2
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "handoff")


def test_read_handoff_takes_only_dashed_dates(tmp_path):
    """fromisoformat alone would take 20261118 or 2026-W47-3; the board writes YYYY-MM-DD."""
    path = tmp_path / "handoff.csv"
    for date in ("20261118", "2026-W47-3", "2026-11-31"):
        path.write_text(_board([_row("ufo2p", TA, date=date)]), encoding="utf-8")
        with pytest.raises(PickerError, match="retired_on"):
            picker.read_handoff(path)


def test_read_handoff_names_a_csv_error(tmp_path):
    path = tmp_path / "handoff.csv"
    path.write_text(_board([_row("ufo2p", TA, reason="r" * 200_000)]), encoding="utf-8")
    with pytest.raises(PickerError, match="field larger than field limit"):
        picker.read_handoff(path)


def test_a_board_row_must_be_a_function_row(tmp_path, capsys):
    """A typo retires nothing silently: a board row that is no functions.csv row start of its
    EXE refuses the drive, naming it."""
    rig, worlds = _nm_rig(tmp_path)
    _retire(rig, (UFO2P, TA + 1))
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, seams={"world": lambda: worlds})
    assert code == 2
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "handoff")
    assert f"ufo2p 0x{TA + 1:08X}" in doc["detail"]


SPLIT_REASON, SPLIT_RULE = "suspected bad split", "boundary fixed"


def test_the_committed_suspected_splits_are_unmatched_function_rows():
    """Ruling 2026-11-19: until its boundary fix lands, every unmatched row of a fix that
    `mechanics interior` proposes sits on the board, sorted by EXE then address. The drive
    refuses a board row that is no functions.csv row start of its EXE, and the progress page
    one that is no game or thunk row (a data-in-code row is neither)."""
    path = REPO_ROOT / "config" / picker.HANDOFF_CSV
    with path.open(encoding="utf-8", newline="") as handle:
        suspects = [row for row in csv.DictReader(handle) if row["reason"] == SPLIT_REASON]
    assert suspects
    assert {row["return_rule"] for row in suspects} == {SPLIT_RULE}
    keys = [(row["exe"], int(row["address"], 16)) for row in suspects]
    assert keys == sorted(keys, key=lambda key: (picker.EXE_ORDER.index(key[0]), key[1]))
    for exe in picker.EXE_ORDER:
        config = REPO_ROOT / "config" / exe
        starts = {row.start for row in read_functions_csv(config / "functions.csv")
                  if row.kind in ("game", "thunk")}  # fmt: skip
        matched = {row.start for row in read_status(config / STATUS_FILE)
                   if row.status == MATCHED}  # fmt: skip
        mine = {address for owner, address in keys if owner == exe}
        assert mine <= starts, sorted(mine - starts)
        assert not mine & matched, sorted(mine & matched)


# ---- reserved benchmark sets (owner ruling 2026-11-25, todo held-v2-lookalikes) ----

RESERVED = "benchmarks/reserved.txt"  # under config/


def _reserve(rig, sets: dict[str, list[tuple[str, int]]], *, extra: str = "") -> None:
    """Each set as a picks file under config/benchmarks/, all named in reserved.txt."""
    from test_drive import _git

    bench = rig.repo / "config" / "benchmarks"
    bench.mkdir(parents=True, exist_ok=True)
    for name, keys in sets.items():
        (bench / name).write_text("".join(f"{exe} 0x{start:08X}\n" for exe, start in keys),
                                  encoding="utf-8", newline="\n")  # fmt: skip
    text = "# reserved (made up)\n" + "".join(f"{name}\n" for name in sets) + extra
    (bench / "reserved.txt").write_text(text, encoding="utf-8", newline="\n")
    _git(rig.repo, rig.env, "add", "--", "config/benchmarks")
    _git(rig.repo, rig.env, "commit", "-q", "-m", "reserved sets (made up)")


def test_the_committed_reserved_list_reads():
    path = REPO_ROOT / "config" / RESERVED
    assert path.read_text(encoding="utf-8").startswith("# ")
    assert isinstance(driver.reserved_keys(REPO_ROOT / "config"), frozenset)


def test_an_absent_or_empty_reserved_list_reserves_nothing(tmp_path):
    assert driver.reserved_keys(tmp_path) == frozenset()
    (tmp_path / "benchmarks").mkdir()
    (tmp_path / RESERVED).write_text("# nothing yet\n\n", encoding="utf-8")
    assert driver.reserved_keys(tmp_path) == frozenset()


def test_reserved_keys_reads_every_named_set(tmp_path):
    bench = tmp_path / "benchmarks"
    bench.mkdir()
    (bench / "a.txt").write_text(f"ufo2p 0x{TA:08X}\n", encoding="utf-8")
    (bench / "b.txt").write_text(f"tacp 0x{TB:08X}\nufo2p 0x{TA:08X}\n", encoding="utf-8")
    (bench / "reserved.txt").write_text("# two sets\na.txt\n\nb.txt  # the second\n",
                                        encoding="utf-8")  # fmt: skip
    assert driver.reserved_keys(tmp_path) == {(UFO2P, TA), ("tacp", TB)}


@pytest.mark.parametrize(("lines", "line"), [
    ("held-v9.txt\n", 2),
    ("a.txt\n../a.txt\n", 3),
    ("sub/a.txt\n", 2),
    ("a.txt b.txt\n", 2),
])  # fmt: skip
def test_reserved_keys_refuses_a_bad_name(tmp_path, lines, line):
    bench = tmp_path / "benchmarks"
    bench.mkdir()
    (bench / "a.txt").write_text(f"ufo2p 0x{TA:08X}\n", encoding="utf-8")
    (bench / "reserved.txt").write_text("# head\n" + lines, encoding="utf-8")
    with pytest.raises(driver.DriverError, match=f"line {line}"):
        driver.reserved_keys(tmp_path)


def test_a_bad_reserved_list_refuses_the_drive(tmp_path, capsys):
    rig, worlds = _nm_rig(tmp_path)
    _reserve(rig, {}, extra="held-v9.txt\n")
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, seams={"world": lambda: worlds})
    assert code == 2
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "reserved")
    assert "line 2" in doc["detail"] and "held-v9.txt" in doc["detail"]


def test_pools_skip_reserved_rows(tmp_path):
    from test_drive import BASE, Rig
    from test_drive import _world as _pools_world

    rig = Rig(tmp_path / "rig")
    reserved = (UFO2P, BASE[UFO2P])
    _reserve(rig, {"held-v2.txt": [reserved]})
    deps = driver.real_deps(rig.options(), rig.seams(), _pools_world(rig.packs))
    keys = [(p.exe, p.start) for p in deps.queue(frozenset())]
    assert keys and reserved not in keys


def test_a_tier_night_skips_reserved_rows_and_the_dry_run_says_so(tmp_path, capsys):
    rig = _signed_rig(tmp_path, [_member(a) for a in (TA, TB, TC)])
    worlds = _rig_world(rig.packs, (TA, TB, TC), ())
    code, out, _ = rig.drive(capsys, dry_run=True, seams={"world": lambda: worlds})
    assert code == 0, out
    assert not [line for line in out.splitlines() if line.startswith("reserved")]
    _reserve(rig, {"held-v2.txt": [(UFO2P, TB)]})
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, seams={"world": lambda: worlds})
    assert code == 0, out
    assert {int(p["start"], 16) for p in json.loads(out)["picks"]} == {TA, TC}
    deps = driver.real_deps(rig.options(), rig.seams(world=lambda: worlds), worlds)
    assert (UFO2P, TB) not in {i.key for i in deps.queue(frozenset()).items}
    code, out, _ = rig.drive(capsys, dry_run=True, seams={"world": lambda: worlds})
    assert code == 0, out
    assert "reserved rows left out: 1 (held-v2.txt)" in out.splitlines()


def test_the_near_miss_lane_skips_reserved_rows(tmp_path, capsys):
    """_nm_rig at 80%: the lane is TB, TS, TC; with TB reserved it is TS, TC, and the tier lane
    (TC and TB) holds nothing."""
    rig, worlds = _nm_rig(tmp_path)
    _reserve(rig, {"held-v2.txt": [(UFO2P, TB)]})
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, near_miss=80.0,
                             seams={"world": lambda: worlds})  # fmt: skip
    assert code == 0, out
    assert [int(p["start"], 16) for p in json.loads(out)["picks"]] == [TS, TC]
    build = driver.near_miss_source(rig.repo / "config", worlds, 80.0)
    assert [i.pick.start for i in build().preview(10)] == [TS, TC]


def test_a_held_run_on_a_reserved_set_queues_all_its_picks(tmp_path):
    """The held runs: `--hold --picks config/benchmarks/held-v2.txt` keeps every row of the set,
    refuse_picks takes them, and the dry-run line names only the other set."""
    rig = _signed_rig(tmp_path, [_member(a) for a in (TA, TB, TC)])
    worlds = _rig_world(rig.packs, (TA, TB, TC), ())
    _reserve(rig, {"held-v2.txt": [(UFO2P, TA), (UFO2P, TB)], "held-v3.txt": [(UFO2P, TC)]})
    options = rig.options(picks=rig.repo / "config" / "benchmarks" / "held-v2.txt", hold=True)
    driver.refuse_reserved(options)
    driver.refuse_picks(options, worlds)
    deps = driver.real_deps(options, rig.seams(world=lambda: worlds), worlds)
    assert {i.key for i in deps.queue(frozenset()).items} == {(UFO2P, TA), (UFO2P, TB)}
    assert {e.key for e in driver.restricted_picks(options, worlds, 10)} == {(UFO2P, TA),
                                                                             (UFO2P, TB)}
    assert driver.reserved_line(options) == "reserved rows left out: 1 (held-v3.txt)"


def test_a_picks_night_on_a_reserved_set_without_hold_is_refused(tmp_path, capsys):
    rig = _signed_rig(tmp_path, [_member(a) for a in (TA, TB)])
    worlds = _rig_world(rig.packs, (TA, TB), ())
    _reserve(rig, {"held-v2.txt": [(UFO2P, TA), (UFO2P, TB)]})
    picks = rig.repo / "config" / "benchmarks" / "held-v2.txt"
    code, out, _ = rig.drive(capsys, json=True, picks=picks, seams={"world": lambda: worlds})
    assert code == 2, out
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "reserved")
    assert "held-v2.txt" in doc["detail"] and "--hold" in doc["detail"]
    assert [c for c in rig.runner.calls if c[:1] == ["claude"]] == [["claude", "--version"]]


def test_a_dry_run_of_a_reserved_picks_file_lists_none_of_it(tmp_path, capsys):
    """A dry run (never --hold) draws from the filtered queue: no reserved row is listed."""
    rig = _signed_rig(tmp_path, [_member(a) for a in (TA, TB, TC)])
    worlds = _rig_world(rig.packs, (TA, TB, TC), ())
    _reserve(rig, {"held-v2.txt": [(UFO2P, TA), (UFO2P, TB)]})
    picks = rig.repo / "config" / "benchmarks" / "held-v2.txt"
    code, out, _ = rig.drive(capsys, dry_run=True, picks=picks, seams={"world": lambda: worlds})
    assert code == 0, out
    assert not [line for line in out.splitlines() if line.startswith(UFO2P)]
    assert "reserved rows left out: 2 (held-v2.txt)" in out.splitlines()


def test_another_picks_file_overlapping_a_reserved_set_drops_its_reserved_picks(tmp_path):
    """Even on a --hold night: only the reserved file itself queues the set."""
    rig = _signed_rig(tmp_path, [_member(a) for a in (TA, TB, TC)])
    worlds = _rig_world(rig.packs, (TA, TB, TC), ())
    _reserve(rig, {"held-v2.txt": [(UFO2P, TA), (UFO2P, TB)]})
    picks = _picks_file(tmp_path, [(UFO2P, TA), (UFO2P, TC)])
    for hold in (False, True):
        options = rig.options(picks=picks, hold=hold)
        driver.refuse_reserved(options)
        driver.refuse_picks(options, worlds)
        deps = driver.real_deps(options, rig.seams(world=lambda: worlds), worlds)
        assert {i.key for i in deps.queue(frozenset()).items} == {(UFO2P, TC)}
        assert driver.reserved_line(options) == "reserved rows left out: 2 (held-v2.txt)"


def test_pools_picks_nights_and_reserved_sets(tmp_path):
    """Without a signed tier: a held run on the reserved file queues the whole set; an
    overlapping other picks file queues only its unreserved picks."""
    from test_drive import BASE, Rig
    from test_drive import _world as _pools_world

    rig = Rig(tmp_path / "rig")
    keys = [(UFO2P, BASE[UFO2P] + 0x20000), ("tacp", BASE["tacp"])]
    _reserve(rig, {"held-v2.txt": keys})
    worlds = _pools_world(rig.packs)
    options = rig.options(picks=rig.repo / "config" / "benchmarks" / "held-v2.txt", hold=True)
    driver.refuse_picks(options, worlds)
    deps = driver.real_deps(options, rig.seams(), worlds)
    assert sorted((p.exe, p.start) for p in deps.queue(frozenset())) == sorted(keys)
    free = (UFO2P, BASE[UFO2P])
    options = rig.options(picks=_picks_file(tmp_path, [keys[0], free]), hold=True)
    driver.refuse_picks(options, worlds)
    deps = driver.real_deps(options, rig.seams(), worlds)
    assert [(p.exe, p.start) for p in deps.queue(frozenset())] == [free]
