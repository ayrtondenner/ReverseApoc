"""flags (D-12, D-13, D-16, D-28, D-32): the owner-approval queue of per-unit cflags rules.

`flags propose` turns sweep hits of driver attempts into proposals in config/cflags-proposals.toml,
`flags regate` re-proves a proposal over its whole unit on a copy of src/ under a temporary cflags
file, and `flags list` shows the queue. Every attempt directory, sweep JSON, C text, address and
hash here is made up; the only committed data read is progress/attempts.jsonl (the D-16 list)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from conftest import REPO_ROOT, write_manifest
from reverseapoc import check, contextpack, driver, flags
from reverseapoc.cflags import parse_cflags, select_rule
from reverseapoc.check import CheckError, CheckResult, ExeLand, FunctionCheck
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, write_functions_csv
from reverseapoc.land import LandResult
from reverseapoc.relocs import RelocResult
from reverseapoc.status import lf_sha256

RUN = "20261026-005209"
BASE = "wcc386@10.6 -4r -s -fpi"  # the committed `*` rule as a sweep cell names it
CFLAGS_TEXT = "# test cflags\n*  wcc386@10.6  -4r -s -fpi\n"
STATUS_HEAD = ("# written by: uv run reverseapoc gate EXE/UNIT; do not edit\n"
               "start,name,unit,status,best_percent,attempts,source_sha256,date\n")  # fmt: skip
SHA = "a" * 64
F30, F50, FA0 = "func_00061F30", "func_00061F50", "func_00061FA0"
UNIT = "u_00060c50"


def spec(number: int) -> str:
    """The D-17 cell `number` as a sweep names it (30-cell layout, no __CHK toggle)."""
    version, cell_flags = check.sweep_cells(chk=False)[number - 1]
    return " ".join([f"wcc386@{version}", *cell_flags])


def cell(number: int, *, hit: bool, version: str | None = None,
         cell_flags: tuple[str, ...] | None = None) -> dict:  # fmt: skip
    if version is None:
        version, cell_flags = check.sweep_cells(chk=False)[number - 1]
    return {"cell": number, "compiler": f"wcc386@{version}", "flags": list(cell_flags or ()),
            "status": "measured", "objdiff_percent": 100.0 if hit else 50.0,
            "reloc_ok": hit, "differing": 0 if hit else 3}  # fmt: skip


def sweep_doc(function: str, *, hits: set[int], unit: str = UNIT, exe: str = "ufo2p",
              stage2: list[dict] | None = None) -> dict:  # fmt: skip
    cells = [cell(n, hit=n in hits) for n in range(1, 31)]
    doc = {"exe": exe, "unit": unit, "function": function, "chk": False, "cells": cells,
           "best": sorted(hits) or [1], "log": "/work/build/logs/sweep.log"}  # fmt: skip
    if stage2 is not None:
        doc["stage2"] = {"from": 4, "cells": stage2, "best": [c["cell"] for c in stage2]}
    return doc


def check_line(n: int, *, sweep: bool, hit: str | None = None) -> dict:
    return {"best_percent": 100.0 if hit else 71.43, "bytes_ok": bool(hit),
            "exit": 0 if sweep else 1, "n": n, "reloc_ok": bool(hit), "source": f"checks/{n:04d}.c",
            "splice_ok": None if sweep else False, "sweep": sweep, "sweep_hit": hit}  # fmt: skip


def c_text(*defined: str, marked: tuple[str, ...] = (), tag: str = "") -> str:
    """A unit file defining `defined` (made-up bodies) and marking `marked` INCLUDE_ASM."""
    lines = [f"/* {tag} */", '#include "apoc.h"', ""]
    lines += [f"INCLUDE_ASM({name});" for name in marked]
    for name in defined:
        lines += ["", f"int {name}(int a)", "{", f"    return a + {len(tag) + len(name)};", "}"]
    return "\n".join(lines) + "\n"


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "config" / "ufo2p").mkdir(parents=True)
    (repo / "config" / "tacp").mkdir(parents=True)
    (repo / "config" / "cflags.txt").write_text(CFLAGS_TEXT, encoding="utf-8", newline="\n")
    return repo


def write_status(repo: Path, exe: str, rows: list[tuple[int, str, str, str, str]]) -> None:
    body = "".join(f"0x{start:08X},{name},{unit},{status},{percent},3,{SHA},2026-10-26\n"
                   for start, name, unit, status, percent in sorted(rows))  # fmt: skip
    path = repo / "config" / exe / "status.csv"
    path.write_text(STATUS_HEAD + body, encoding="utf-8", newline="\n")


def make_attempt(repo: Path, function: str, *, attempt: int = 1, exe: str = "ufo2p",
                 unit: str = UNIT, run: str = RUN,
                 checks: list[tuple[int, bool, dict | None, str]],
                 best: str | None = None) -> Path:  # fmt: skip
    """build/driver/<run>/<exe>/<function>/attempt-N with one (n, sweep, sweep doc, C) per
    check run; a sweep line's sweep_hit is the first hit cell's spec, as attempt writes it."""
    root = repo / "build" / "driver" / run / exe / function / f"attempt-{attempt}"
    (root / "checks").mkdir(parents=True)
    lines = []
    for n, sweep, doc, text in checks:
        (root / "checks" / f"{n:04d}.c").write_text(text, encoding="utf-8", newline="\n")
        hit = None
        if sweep and doc is not None:
            perfect = [c for c in doc["cells"] + (doc.get("stage2") or {}).get("cells", [])
                       if c["reloc_ok"] and c["objdiff_percent"] == 100.0]  # fmt: skip
            hit = " ".join([perfect[0]["compiler"], *perfect[0]["flags"]]) if perfect else None
        payload = doc if doc is not None else {"functions": [], "ok": False}
        (root / "checks" / f"{n:04d}.json").write_text(json.dumps(payload), encoding="utf-8")
        lines.append(json.dumps(check_line(n, sweep=sweep, hit=hit), sort_keys=True))
    (root / "checks.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if best is not None:
        (root / "best").mkdir()
        (root / "best" / f"{unit}.c").write_text(best, encoding="utf-8", newline="\n")
    return root


def queue_of(repo: Path) -> Path:
    return repo / flags.QUEUE


# ---- Task 1: pilot_hits, the queue, propose, the verb ----


def test_pilot_hits_from_committed_log():
    """D-16 (ruling F15: from attempts.jsonl alone): the six never-matched pilot sweep hits;
    func_0008A100 hit and later matched, so it is out."""
    hits = flags.pilot_hits(REPO_ROOT / "progress" / "attempts.jsonl")
    assert hits == [("tacp", "func_0006FBD0"), ("tacp", "func_000779C0"),
                    ("ufo2p", "func_00026FD0"), ("ufo2p", "func_0004DFD0"),
                    ("ufo2p", "func_00061F30"), ("ufo2p", "func_0009C3A0")]  # fmt: skip
    assert ("ufo2p", "func_0008A100") not in hits


def _record(function: str, outcome: str, hit: str | None, attempt: int = 1) -> dict:
    start = "0x" + function.removeprefix("func_")
    return {"kind": "attempt", "run": RUN, "exe": "ufo2p", "function": function, "unit": UNIT,
            "start": start, "attempt": attempt, "outcome": outcome, "abort_reason": None,
            "turns": 1, "tokens": {"input": 1, "output": 1, "cache_read": 0, "cache_creation": 0},
            "cost_usd": 0.1, "seconds": 1.0, "model": None, "cli_version": None,
            "check": {"runs": 1, "best_percent": 50.0, "sweep_hit": hit,
                      "needs": f"needs flags {hit}" if hit else None},
            "pack_bytes": 1, "truncated": [], "date": "2026-10-26"}  # fmt: skip


def test_pilot_hits_drops_a_later_match_and_ignores_status(tmp_path):
    """A hit whose function later has a MATCHED record is out; status.csv is never read."""
    log = tmp_path / "attempts.jsonl"
    records = [_record(F30, "PARTIAL", spec(4)), _record(F50, "PARTIAL", spec(5)),
               _record(F50, "MATCHED", None, attempt=2), _record(FA0, "PARTIAL", None)]  # fmt: skip
    log.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    assert flags.pilot_hits(log) == [("ufo2p", F30)]


def test_pilot_hits_refuses_a_malformed_record(tmp_path):
    log = tmp_path / "attempts.jsonl"
    log.write_text(json.dumps({"kind": "attempt"}) + "\n", encoding="utf-8")
    with pytest.raises(flags.FlagsError, match="line 1"):
        flags.pilot_hits(log)


def _proposal(**changes) -> flags.Proposal:
    fields = dict(
        id="F-0001", exe="ufo2p", unit=UNIT, glob=f"src/ufo2p/{UNIT}.c",
        rule="wcc386@10.6 -4r -ot -s -fpi", base=BASE, functions=(F30,), keeps=(),
        siblings=(f"{F50} partial 46.45", f"{FA0} partial 67.50", "func_00061FC0 unattempted"),
        alternatives=("wcc386@10.6 -4r -oneatx -s -fpi",),
        source="sweep", candidate=f"build/flags/F-0001/{UNIT}.c", candidate_sha256=SHA,
        evidence=(f"build/driver/{RUN}/ufo2p/{F30}/attempt-3/checks/0010.json",),
        status="proposed", regate_exit=-1, regate_variant="empty", regate_cflags_sha256="",
        regate_log="", approved_by="", approved_date="", reason="", variant_sha256="",
        reverted=(),
    )  # fmt: skip
    fields.update(changes)
    return flags.Proposal(**fields)


def test_queue_round_trip(tmp_path):
    path = tmp_path / "cflags-proposals.toml"
    proposals = [_proposal(), _proposal(id="F-0002", exe="tacp", unit="u_0006fbd0",
                                        glob="src/tacp/u_0006fbd0.c", functions=("func_0006FBD0",),
                                        siblings=(), alternatives=(),
                                        candidate="build/flags/F-0002/u_0006fbd0.c",
                                        evidence=(), status="failed", regate_exit=1,
                                        regate_variant="reduced", reason='a "quoted" reason'),
                 _proposal(id="F-0003", functions=("func_00026FD0",), unit="u_00026dd0",
                           glob="src/ufo2p/u_00026dd0.c", siblings=("func_00026FF0 unattempted",),
                           candidate="build/flags/F-0003/u_00026dd0.c", status="regated",
                           regate_exit=0, regate_variant="reduced", variant_sha256="b" * 64,
                           reverted=("func_00026FF0",))]  # fmt: skip
    flags.write_queue(path, proposals)
    assert flags.read_queue(path) == proposals
    text = path.read_text(encoding="ascii")
    assert text.count("[[proposal]]") == 3 and "version = 1" in text
    head = text.index("[[proposal]]")
    first = text[head : text.index("[[proposal]]", head + 1)]
    keys = [line.split(" = ")[0] for line in first.splitlines() if " = " in line]
    assert keys == list(flags.FIELDS)
    assert flags.FIELDS[-3:] == ("reason", "variant_sha256", "reverted")  # fix round 1
    flags.write_queue(path, flags.read_queue(path))
    assert path.read_text(encoding="ascii") == text  # byte-stable


@pytest.mark.parametrize("changes", [
    {"variant_sha256": "b" * 64},  # a variant sha without the functions it reverted
    {"reverted": (F50,)},  # reverted functions without the variant's sha
    {"siblings": (f"{F50} 46.45",)},  # a sibling without its status
    {"siblings": (f"{F50} partial",)},  # a status without its percent
])  # fmt: skip
def test_queue_refuses_inconsistent_fields(tmp_path, changes):
    with pytest.raises(flags.FlagsError):
        flags.write_queue(tmp_path / "q.toml", [_proposal(**changes)])


def test_queue_refuses_non_ascii(tmp_path):
    path = tmp_path / "cflags-proposals.toml"
    with pytest.raises(flags.FlagsError, match="ASCII"):
        flags.write_queue(path, [_proposal(reason="café")])
    assert not path.exists()


def test_read_queue_missing_is_empty(tmp_path):
    assert flags.read_queue(tmp_path / "none.toml") == []


def test_read_queue_refuses_an_unknown_status(tmp_path):
    path = tmp_path / "cflags-proposals.toml"
    flags.write_queue(path, [_proposal()])
    path.write_text(path.read_text(encoding="ascii").replace('"proposed"', '"maybe"'),
                    encoding="ascii")  # fmt: skip
    with pytest.raises(flags.FlagsError, match="status"):
        flags.read_queue(path)


def _pilot_attempt(repo: Path) -> Path:
    """func_00061F30's attempt: plain checks 1-4, a sweep 5 that hits 4/5/14/15, best/ differs."""
    hitting = c_text(F30, F50, marked=(FA0,), tag="the C that hit")
    plain = [(n, False, None, c_text(F30, marked=(F50, FA0), tag=f"plain {n}"))
             for n in range(1, 5)]  # fmt: skip
    return make_attempt(repo, F30, attempt=3,
                        checks=[*plain, (5, True, sweep_doc(F30, hits={4, 5, 14, 15}), hitting)],
                        best=c_text(F30, marked=(F50, FA0), tag="best plain"))  # fmt: skip


def test_propose_uses_the_hitting_snapshot(tmp_path):
    """D-28: the candidate is the sweep line's checks/0005.c, never best/."""
    repo = make_repo(tmp_path)
    write_status(repo, "ufo2p", [(0x61F30, F30, UNIT, "partial", "77.14"),
                                 (0x61F50, F50, UNIT, "partial", "46.45"),
                                 (0x61FA0, FA0, UNIT, "partial", "67.50")])  # fmt: skip
    attempt_dir = _pilot_attempt(repo)
    report = flags.propose([RUN], repo=repo)
    assert report.added == ("F-0001",)
    (p,) = flags.read_queue(queue_of(repo))
    hitting = (attempt_dir / "checks" / "0005.c").read_bytes()
    assert (repo / p.candidate).read_bytes() == hitting
    assert (repo / p.candidate).read_bytes() != (attempt_dir / "best" / f"{UNIT}.c").read_bytes()
    assert p.candidate == f"build/flags/F-0001/{UNIT}.c"
    assert p.candidate_sha256 == lf_sha256(hitting.decode("utf-8"))
    assert (p.exe, p.unit, p.glob, p.functions) == ("ufo2p", UNIT, f"src/ufo2p/{UNIT}.c", (F30,))
    assert p.base == BASE and p.rule == spec(4) and p.alternatives == (spec(5), spec(14), spec(15))
    assert p.source == "sweep" and p.status == "proposed" and p.regate_exit == -1
    assert p.evidence == (f"build/driver/{RUN}/ufo2p/{F30}/attempt-3/checks/0005.json",)
    assert p.keeps == ()


def test_propose_is_idempotent(tmp_path):
    repo = make_repo(tmp_path)
    _pilot_attempt(repo)
    flags.propose([RUN], repo=repo)
    before = queue_of(repo).read_bytes()
    report = flags.propose([RUN], repo=repo)
    assert report.added == () and report.merged == ()
    assert queue_of(repo).read_bytes() == before


def test_propose_skips_a_status_matched_function(tmp_path):
    """Ruling F15: propose, not pilot_hits, skips a function status.csv has matched."""
    repo = make_repo(tmp_path)
    write_status(repo, "ufo2p", [(0x61F30, F30, UNIT, "matched", "100.00")])
    _pilot_attempt(repo)
    report = flags.propose([RUN], repo=repo)
    assert report.added == () and not queue_of(repo).exists()
    assert any(F30 in line and "matched" in line for line in report.skipped)


def test_propose_scans_every_run_by_default(tmp_path):
    repo = make_repo(tmp_path)
    _pilot_attempt(repo)
    assert flags.propose([], repo=repo).added == ("F-0001",)


def test_propose_refuses_an_unknown_run(tmp_path):
    repo = make_repo(tmp_path)
    with pytest.raises(flags.FlagsError, match="no-such-run"):
        flags.propose(["no-such-run"], repo=repo)
    with pytest.raises(flags.FlagsError):
        flags.propose(["../config"], repo=repo)


def test_cli_propose_and_list(tmp_path, capsys):
    repo = make_repo(tmp_path)
    _pilot_attempt(repo)
    assert cli_main(["flags", "propose", "--from-attempts", RUN, "--repo", str(repo)]) == 0
    capsys.readouterr()
    assert cli_main(["flags", "list", "--json", "--repo", str(repo)]) == 0
    doc = json.loads(capsys.readouterr().out)
    (p,) = doc["proposals"]
    assert (p["id"], p["functions"], p["rule"], p["status"]) == ("F-0001", [F30], spec(4),
                                                                   "proposed")  # fmt: skip
    assert cli_main(["flags", "list", "--repo", str(repo)]) == 0
    text = capsys.readouterr().out
    assert "F-0001" in text and F30 in text and spec(4) in text and "proposed" in text


def test_cli_flags_error_exits_2(tmp_path, capsys):
    repo = make_repo(tmp_path)
    assert cli_main(["flags", "propose", "--from-attempts", "nope", "--repo", str(repo)]) == 2
    assert "nope" in capsys.readouterr().err


# ---- Task 2: merging hits per unit, the tie-break, failed proposals, siblings ----


def _two_function_unit(repo: Path, hits_a: set[int], hits_b: set[int]) -> None:
    """func_00061F30 and func_00061F50 of one unit each hit in their own attempt, each snapshot
    defining only its own function."""
    make_attempt(repo, F30, checks=[(1, True, sweep_doc(F30, hits=hits_a),
                                     c_text(F30, marked=(F50, FA0), tag="A"))])  # fmt: skip
    make_attempt(repo, F50, checks=[(1, True, sweep_doc(F50, hits=hits_b),
                                     c_text(F50, marked=(F30, FA0), tag="B"))])  # fmt: skip


def test_merge_by_intersection(tmp_path):
    """Two functions of one unit: one proposal whose rule is in both functions' 100% cells,
    and whose candidate defines both functions as each one hit."""
    repo = make_repo(tmp_path)
    _two_function_unit(repo, {4, 5, 14}, {5, 15})
    report = flags.propose([RUN], repo=repo)
    assert report.added == ("F-0001",) and report.merged == ("F-0001",)
    (p,) = flags.read_queue(queue_of(repo))
    assert p.functions == (F30, F50) and p.rule == spec(5) and p.alternatives == ()
    assert p.status == "proposed" and len(p.evidence) == 2
    candidate = (repo / p.candidate).read_text(encoding="utf-8")
    assert p.candidate_sha256 == lf_sha256(candidate)
    defs = contextpack.definitions(candidate)
    a = (repo / "build/driver" / RUN / "ufo2p" / F30 / "attempt-1/checks/0001.c").read_text()
    b = (repo / "build/driver" / RUN / "ufo2p" / F50 / "attempt-1/checks/0001.c").read_text()
    assert defs[F30].source == contextpack.definitions(a)[F30].source
    assert defs[F50].source == contextpack.definitions(b)[F50].source
    assert f"INCLUDE_ASM({F50});" not in candidate


def test_merge_by_intersection_keeps_the_rest_as_alternatives(tmp_path):
    repo = make_repo(tmp_path)
    _two_function_unit(repo, {4, 5, 14, 15}, {4, 5, 15})
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    assert p.rule == spec(4) and p.alternatives == (spec(5), spec(15))


def test_empty_intersection_fails(tmp_path):
    repo = make_repo(tmp_path)
    _two_function_unit(repo, {4}, {5})
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    assert p.status == "failed" and p.rule == "" and p.alternatives == ()
    assert F30 in p.reason and F50 in p.reason


def test_tie_break(tmp_path):
    """DEC-03 ordering: fewer flags first, then the lower cell number."""
    repo = make_repo(tmp_path)
    # cell 11 is 10.5's `-4r -s -fpi` (three flags), cell 4 10.6's `-4r -ot -s -fpi` (four)
    make_attempt(repo, F30, checks=[(1, True, sweep_doc(F30, hits={4, 11}), c_text(F30))])
    # cells 5 (10.6 -oneatx) and 14 (10.5 -ot): four flags each, so the lower cell wins
    make_attempt(repo, "func_000779C0", exe="tacp", unit="u_000778d0",
                 checks=[(1, True, sweep_doc("func_000779C0", exe="tacp", unit="u_000778d0",
                                             hits={5, 14}), c_text("func_000779C0"))])  # fmt: skip
    make_attempt(repo, "func_0006FBD0", exe="tacp", unit="u_0006fbd0",
                 checks=[(1, True, sweep_doc("func_0006FBD0", exe="tacp", unit="u_0006fbd0",
                                             hits={4, 5}), c_text("func_0006FBD0"))])  # fmt: skip
    flags.propose([RUN], repo=repo)
    by_unit = {p.unit: p for p in flags.read_queue(queue_of(repo))}
    fewer = by_unit[UNIT]
    assert fewer.rule == "wcc386@10.5 -4r -s -fpi" == spec(11)  # the fewer-flags rule wins
    assert fewer.alternatives == (spec(4),)
    assert by_unit["u_000778d0"].rule == "wcc386@10.6 -4r -oneatx -s -fpi" == spec(5)
    assert by_unit["u_0006fbd0"].rule == "wcc386@10.6 -4r -ot -s -fpi" == spec(4)
    assert by_unit["u_0006fbd0"].alternatives == ("wcc386@10.6 -4r -oneatx -s -fpi",)
    # numbered in the order hits are found, sorted by (exe, start): tacp first
    assert [p.id for p in sorted(by_unit.values(), key=lambda p: p.id)] == ["F-0001", "F-0002",
                                                                            "F-0003"]  # fmt: skip
    assert (by_unit["u_0006fbd0"].id, by_unit["u_000778d0"].id, fewer.id) == (
        "F-0001", "F-0002", "F-0003")


def test_stage2_hit_source(tmp_path):
    repo = make_repo(tmp_path)
    stage2 = [cell(31, hit=False, version="10.6", cell_flags=("-4r", "-od", "-s", "-fpi")),
              cell(32, hit=True, version="10.6", cell_flags=("-4r", "-ot", "-s", "-fpi", "-zp4"))]
    make_attempt(repo, F30, checks=[(1, True, sweep_doc(F30, hits=set(), stage2=stage2),
                                     c_text(F30))])  # fmt: skip
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    assert p.source == "sweep2" and p.rule == "wcc386@10.6 -4r -ot -s -fpi -zp4"


def _functions_csv(repo: Path, exe: str, rows: list[tuple[int, str, str, str]]) -> None:
    """functions.csv of (start, name, kind, unit) rows, 0x10 bytes each."""
    manifest = {"ufo2p": "UFO2P.EXE", "tacp": "TACP.EXE"}[exe]
    write_functions_csv(repo / "config" / exe / "functions.csv",
                        [FunctionRow(start, start + 0x10, name, kind, unit, "call")
                         for start, name, kind, unit in sorted(rows)], manifest)  # fmt: skip


def test_siblings_listed(tmp_path):
    """D-32 (fix round 1): every other game and thunk row of the unit, with its status.csv
    status and percent, or `unattempted`; matched rows are also keeps."""
    repo = make_repo(tmp_path)
    write_status(repo, "ufo2p", [(0x60C50, "func_00060C50", UNIT, "matched", "100.00"),
                                 (0x61F30, F30, UNIT, "partial", "77.14"),
                                 (0x61F50, F50, UNIT, "partial", "46.45"),
                                 (0x61FA0, FA0, UNIT, "partial", "67.50"),
                                 (0x70000, "func_00070000", "u_00070000", "partial", "12.00")])
    _functions_csv(repo, "ufo2p", [(0x60C50, "func_00060C50", "game", UNIT),
                                   (0x61F30, F30, "game", UNIT), (0x61F50, F50, "game", UNIT),
                                   (0x61F70, "func_00061F70", "thunk", UNIT),
                                   (0x61FA0, FA0, "game", UNIT),
                                   (0x61FC0, "D_00061FC0", "data-in-code", UNIT),
                                   (0x70000, "func_00070000", "game", "u_00070000")])
    _pilot_attempt(repo)
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    assert p.siblings == ("func_00060C50 matched 100.00", f"{F50} partial 46.45",
                          "func_00061F70 unattempted", f"{FA0} partial 67.50")  # fmt: skip
    assert p.keeps == ("func_00060C50",)
    flags_list = flags.read_queue(queue_of(repo))[0].line()
    assert "sibling func_00061F70 unattempted" in flags_list


def test_siblings_include_the_unattempted_neighbour(tmp_path):
    """tacp u_0006fbd0: no status rows at all, yet D-28's neighbour func_0006FC00 is listed."""
    repo = make_repo(tmp_path)
    unit, func = "u_0006fbd0", "func_0006FBD0"
    _functions_csv(repo, "tacp", [(0x6FBD0, func, "game", unit),
                                  (0x6FC00, "func_0006FC00", "game", unit),
                                  (0x6FC40, "func_0006FC40", "game", unit)])
    make_attempt(repo, func, exe="tacp", unit=unit,
                 checks=[(1, True, sweep_doc(func, exe="tacp", unit=unit, hits={5}),
                          c_text(func, "func_0006FC00"))])  # fmt: skip
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    assert p.siblings == ("func_0006FC00 unattempted", "func_0006FC40 unattempted")


def test_merge_into_a_regated_proposal_resets_its_regate(tmp_path):
    repo = make_repo(tmp_path)
    _two_function_unit(repo, {4, 5}, {4, 5})
    make_attempt(repo, F30, run="20261027-000000",
                 checks=[(1, True, sweep_doc(F30, hits={4, 5}), c_text(F30, tag="A"))])
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    flags.write_queue(queue_of(repo), [dataclasses.replace(
        p, functions=(F30,), status="regated", regate_exit=0, regate_variant="reduced",
        regate_cflags_sha256=SHA, regate_log="build/flags/F-0001/regate.json",
        variant_sha256=SHA, reverted=(F50,))])
    # the evidence of F50's hit is already queued; a new run's F30 hit is the same function
    report = flags.propose(["20261027-000000"], repo=repo)
    (q,) = flags.read_queue(queue_of(repo))
    assert report.merged == ("F-0001",) and len(q.evidence) == 3
    assert (q.status, q.regate_exit, q.regate_variant, q.regate_cflags_sha256, q.regate_log) == (
        "proposed", -1, "empty", "", "")
    assert (q.variant_sha256, q.reverted) == ("", ())
    assert q.candidate_sha256 == p.candidate_sha256  # same function: the candidate stays


# ---- Task 3: flags regate ----

KEEP, OTHER = "func_00060C50", "func_0008A0E0"
STARTS = {KEEP: 0x60C50, F30: 0x61F30, F50: 0x61F50, FA0: 0x61FA0, OTHER: 0x8A0E0}
UNITS = {KEEP: UNIT, F30: UNIT, F50: UNIT, FA0: UNIT, OTHER: "u_00089980"}
SHA1 = "1" * 40


def regate_repo(tmp_path: Path, *, matched: tuple[str, ...] = (OTHER,),
                candidate: str | None = None) -> Path:  # fmt: skip
    """A checkout with a manifest, functions.csv, status.csv (`matched` rows), a committed
    src/ unit of another unit, and F-0001 queued for func_00061F30 of u_00060c50."""
    repo = make_repo(tmp_path)
    write_manifest(repo / "config" / "targets.toml", {"UFO2P.EXE": b"u", "TACP.EXE": b"t"})
    rows = [FunctionRow(start, start + 0x10, name, "game", UNITS[name], "call")
            for name, start in sorted(STARTS.items(), key=lambda item: item[1])]  # fmt: skip
    write_functions_csv(repo / "config" / "ufo2p" / "functions.csv", rows, "UFO2P.EXE")
    write_status(repo, "ufo2p", [(STARTS[n], n, UNITS[n], "matched", "100.00") for n in matched])
    (repo / "src" / "ufo2p").mkdir(parents=True)
    (repo / "src" / "ufo2p" / "u_00089980.c").write_text(c_text(OTHER, tag="committed"),
                                                         encoding="utf-8", newline="\n")
    text = candidate if candidate is not None else c_text(F30, marked=(F50, FA0), tag="hit")
    path = repo / "build" / "flags" / "F-0001" / f"{UNIT}.c"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    keeps = tuple(n for n in matched if UNITS[n] == UNIT)
    flags.write_queue(queue_of(repo), [_proposal(keeps=keeps, candidate_sha256=lf_sha256(text),
                                                 siblings=())])  # fmt: skip
    return repo


class FakeCheck:
    """check_unit stand-in: every function the unit file defines (contextpack.definitions) is
    scored from `scores` (default 100); the land lands every matched start of other units plus
    the defined ones, minus `drop`."""

    def __init__(self, scores: dict[str, float] | None = None, drop: tuple[str, ...] = ()):
        self.scores = scores or {}
        self.drop = {STARTS[name] for name in drop}
        self.calls: list[dict] = []

    def __call__(self, exe, unit, **kw):
        text = (Path(kw["src_root"]) / exe / f"{unit}.c").read_text(encoding="utf-8")
        cflags_text = Path(kw["cflags"]).read_text(encoding="utf-8")
        self.calls.append({**kw, "exe": exe, "unit": unit, "text": text,
                           "cflags_text": cflags_text})  # fmt: skip
        fns = []
        for name in sorted(contextpack.definitions(text)):
            percent = self.scores.get(name, 100.0)
            ok = percent == 100.0
            fns.append(FunctionCheck(name, STARTS[name], 16, percent,
                                     RelocResult(ok, (), frozenset(), frozenset()), ok,
                                     0 if ok else 3, None))  # fmt: skip
        landed = ({STARTS[OTHER]} | {fn.va for fn in fns}) - self.drop
        good = all(fn.ok for fn in fns) and not self.drop
        land = LandResult(b"", SHA1 if good else "f" * 40, SHA1, tuple(sorted(landed)), 0)
        return CheckResult(exe, unit, "wcc386@10.6", ("-4r",), tuple(fns),
                           (ExeLand("UFO2P.EXE", land),))  # fmt: skip


def _snapshot(repo: Path) -> dict[str, tuple[str, int]]:
    """sha256 and mtime of config/cflags.txt and every file under src/."""
    files = [repo / "config" / "cflags.txt", *sorted((repo / "src").rglob("*"))]
    return {p.as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in files if p.is_file()}  # fmt: skip


def test_regate_writes_nothing_shared(tmp_path):
    repo = regate_repo(tmp_path)
    before = _snapshot(repo)
    fake = FakeCheck()
    report = flags.regate(["F-0001"], repo=repo, check_fn=fake)
    assert _snapshot(repo) == before
    (call,) = fake.calls
    work = repo / "build" / "flags" / "F-0001"
    assert Path(call["cflags"]) == work / "cflags.txt"
    assert Path(call["src_root"]) == work / "src"
    assert call["text"] == (work / f"{UNIT}.c").read_text(encoding="utf-8")
    assert (work / "src" / "ufo2p" / "u_00089980.c").is_file()  # the rest of src/ is copied
    committed = (repo / "config" / "cflags.txt").read_text(encoding="utf-8")
    temp = call["cflags_text"]
    assert temp.startswith(committed) and temp[len(committed) :].count("\n") == 1
    rules = parse_cflags(temp, versions=("10.6", "10.5", "11.0"))
    rule = select_rule(rules, f"src/ufo2p/{UNIT}.c")
    assert " ".join([rule.spec, *rule.flags]) == "wcc386@10.6 -4r -ot -s -fpi"
    assert select_rule(rules, "src/ufo2p/u_00089980.c").flags == ("-4r", "-s", "-fpi")
    (p,) = flags.read_queue(queue_of(repo))
    assert (p.status, p.regate_exit, p.regate_variant) == ("regated", 0, "as-written")
    assert (p.variant_sha256, p.reverted) == ("", ())  # the full candidate passed
    assert not (work / f"{UNIT}.reduced.c").exists()
    assert p.regate_log == "build/flags/F-0001/regate.json" and (repo / p.regate_log).is_file()
    assert report.exit_code == 0


def test_regate_refuses_the_committed_cflags(tmp_path):
    repo = regate_repo(tmp_path)
    committed = repo / "config" / "cflags.txt"
    before = committed.read_bytes()
    (p,) = flags.read_queue(queue_of(repo))
    with pytest.raises(flags.FlagsError, match="committed"):
        flags.temp_cflags(committed, committed, p)
    with pytest.raises(flags.FlagsError, match="committed"):
        flags.temp_cflags(repo / "config" / "." / "cflags.txt", committed, p)
    assert committed.read_bytes() == before


def test_regate_kept_function_drop(tmp_path):
    """DEC-03 adjacency: a kept (matched) function of the unit at 99.99 under the rule."""
    repo = regate_repo(tmp_path, matched=(OTHER, KEEP),
                       candidate=c_text(KEEP, F30, marked=(F50, FA0), tag="hit"))
    report = flags.regate(["F-0001"], repo=repo, check_fn=FakeCheck({KEEP: 99.99}))
    (p,) = flags.read_queue(queue_of(repo))
    assert p.keeps == (KEEP,)
    assert (p.status, p.regate_exit, p.regate_variant) == ("failed", 1, "as-written")
    assert KEEP in p.reason and report.exit_code == 1


def test_regate_cross_check_drop(tmp_path):
    """A landed set one matched start short of status.csv fails the cross-check."""
    repo = regate_repo(tmp_path)
    flags.regate(["F-0001"], repo=repo, check_fn=FakeCheck(drop=(OTHER,)))
    (p,) = flags.read_queue(queue_of(repo))
    assert (p.status, p.regate_exit) == ("failed", 1)
    assert OTHER in p.reason


def test_regate_cross_check_drop_with_a_passing_check(tmp_path):
    """The check passes but the cross-check reports a problem: exit 1."""
    repo = regate_repo(tmp_path)
    seen = []

    def cross(splices, matched, defined, *, owners=None):
        seen.append((matched, defined))
        return [f"ufo2p: {OTHER} at 0x0008A0E0 is matched but was not landed"]

    flags.regate(["F-0001"], repo=repo, check_fn=FakeCheck(), cross_check_fn=cross)
    (p,) = flags.read_queue(queue_of(repo))
    assert (p.status, p.regate_exit) == ("failed", 1)
    matched, defined = seen[0]
    assert set(matched["UFO2P.EXE"]) == {STARTS[OTHER]}
    assert defined == {"UFO2P.EXE": {STARTS[F30]: UNIT}}


def test_regate_reduced_variant(tmp_path):
    """D-28: as written, only the co-defined neighbour misses; the reduced candidate (the
    neighbour back to INCLUDE_ASM) passes."""
    repo = regate_repo(tmp_path, candidate=c_text(F30, F50, marked=(FA0,), tag="hit"))
    fake = FakeCheck({F50: 46.45})
    flags.regate(["F-0001"], repo=repo, check_fn=fake)
    (p,) = flags.read_queue(queue_of(repo))
    assert (p.status, p.regate_exit, p.regate_variant) == ("regated", 0, "reduced")
    first, second = fake.calls
    assert f"int {F50}(int a)" in first["text"]
    assert f"INCLUDE_ASM({F50});" in second["text"] and f"int {F50}(" not in second["text"]
    assert f"int {F30}(int a)" in second["text"]
    assert (repo / p.candidate).read_text(encoding="utf-8") == first["text"]  # kept as hit
    # fix round 1: the variant that passed is pinned for 07-24's approve
    reduced = repo / "build" / "flags" / "F-0001" / f"{UNIT}.reduced.c"
    assert reduced.read_text(encoding="utf-8") == second["text"]
    assert flags.variant_path(p) == f"build/flags/F-0001/{UNIT}.reduced.c"
    assert p.variant_sha256 == lf_sha256(second["text"]) and p.reverted == (F50,)
    listed = p.line()
    assert "WARNING" in listed and F50 in listed and "INCLUDE_ASM" in listed


def test_regate_failing_reduced_variant_pins_nothing(tmp_path):
    repo = regate_repo(tmp_path, candidate=c_text(F30, F50, marked=(FA0,), tag="hit"))

    class Neighbour(FakeCheck):
        """F50 misses as written; as INCLUDE_ASM, the target misses too (research A13)."""

        def __call__(self, exe, unit, **kw):
            text = (Path(kw["src_root"]) / exe / f"{unit}.c").read_text(encoding="utf-8")
            self.scores = {F50: 46.45} if f"int {F50}(" in text else {F30: 87.5}
            return super().__call__(exe, unit, **kw)

    flags.regate(["F-0001"], repo=repo, check_fn=Neighbour())
    (p,) = flags.read_queue(queue_of(repo))
    assert (p.status, p.regate_variant, p.variant_sha256, p.reverted) == (
        "failed", "reduced", "", ())
    assert not (repo / "build" / "flags" / "F-0001" / f"{UNIT}.reduced.c").exists()


def test_regate_no_reduced_retry_when_the_target_misses(tmp_path):
    repo = regate_repo(tmp_path, candidate=c_text(F30, F50, marked=(FA0,), tag="hit"))
    fake = FakeCheck({F30: 90.0, F50: 46.45})
    flags.regate(["F-0001"], repo=repo, check_fn=fake)
    (p,) = flags.read_queue(queue_of(repo))
    assert len(fake.calls) == 1 and (p.status, p.regate_variant) == ("failed", "as-written")


def test_reduced_swaps_the_neighbour_for_include_asm():
    text = c_text(F30, F50, marked=(FA0,), tag="hit")
    reduced = flags._reduced(text, F50)
    assert f"INCLUDE_ASM({F50});" in reduced and f"int {F50}(" not in reduced
    assert f"int {F30}(int a)" in reduced and f"INCLUDE_ASM({FA0});" in reduced


def test_regate_records_cflags_sha(tmp_path):
    repo = regate_repo(tmp_path)
    flags.regate(["F-0001"], repo=repo, check_fn=FakeCheck())
    (p,) = flags.read_queue(queue_of(repo))
    committed = (repo / "config" / "cflags.txt").read_text(encoding="utf-8")
    assert p.regate_cflags_sha256 == lf_sha256(committed)
    assert flags.cflags_sha256(repo / "config" / "cflags.txt") == lf_sha256(committed)


def test_regate_check_error_is_exit_2(tmp_path):
    repo = regate_repo(tmp_path)

    def broken(exe, unit, **kw):
        raise CheckError("compile failed: made-up")

    flags.regate(["F-0001"], repo=repo, check_fn=broken)
    (p,) = flags.read_queue(queue_of(repo))
    assert (p.status, p.regate_exit) == ("failed", 2) and "compile failed" in p.reason


def test_regate_refusals(tmp_path):
    repo = regate_repo(tmp_path)
    with pytest.raises(flags.FlagsError, match="F-0009"):
        flags.regate(["F-0009"], repo=repo, check_fn=FakeCheck())
    candidate = repo / "build" / "flags" / "F-0001" / f"{UNIT}.c"
    text = candidate.read_bytes()
    candidate.write_text("changed\n", encoding="utf-8")
    with pytest.raises(flags.FlagsError, match="candidate"):
        flags.regate(["F-0001"], repo=repo, check_fn=FakeCheck())
    candidate.write_bytes(text)
    (p,) = flags.read_queue(queue_of(repo))
    flags.write_queue(queue_of(repo), [dataclasses.replace(p, status="landed")])
    with pytest.raises(flags.FlagsError, match="landed"):
        flags.regate(["F-0001"], repo=repo, check_fn=FakeCheck())


def test_cli_regate(tmp_path, monkeypatch, capsys):
    repo = regate_repo(tmp_path)
    monkeypatch.setattr(check, "check_unit", FakeCheck())
    assert cli_main(["flags", "regate", "F-0001", "--repo", str(repo)]) == 0
    assert "F-0001" in capsys.readouterr().out
    monkeypatch.setattr(check, "check_unit", FakeCheck({F30: 50.0}))
    assert cli_main(["flags", "regate", "F-0001", "--repo", str(repo)]) == 1


# ---- 07-24 Task 1: flags approve lands rule, C, docs row and status in one commit ----

OWNER = "Owner Name"
DAY = "2026-10-28"
MODEL = "claude-opus-5-5"  # ruling F33: the only model with a known co-author line
U2, F26 = "u_00026dd0", "func_00026FD0"
SCAFFOLD = '#include "apoc.h"\n\nINCLUDE_ASM(func_00061F30);\nINCLUDE_ASM(func_00061F50);\n'
MATCHING_DOC = (
    "# Matching notes\n\n## Compiler and flags per module\n\n"
    "| Module / file glob | EXE | Compiler@version | Flags | Evidence | Date |\n"
    "|---|---|---|---|---|---|\n"
    "| * | UFO2P.EXE | wcc386@10.6 | -4r -s -fpi | made up | 2026-10-21 |\n"
    "| * | TACP.EXE | wcc386@10.6 | -4r -s -fpi | made up | 2026-10-21 |\n"
    "\nProse after the table.\n\n## Known idioms\n\n| a | b |\n|---|---|\n| x | y |\n"
)
APPROVE_FILES = ("config/cflags.txt", f"src/ufo2p/{UNIT}.c", f"src/ufo2p/{U2}.c",
                 "config/ufo2p/status.csv", "decomphub.progress.json", "docs/matching.md",
                 "config/cflags-proposals.toml")  # fmt: skip


class GitEnv(dict):
    """The environment without CLAUDECODE and git overrides, an empty global config and a
    made-up identity, so the user's git settings and hooks cannot leak into a tmp repo."""

    def __init__(self, tmp_path: Path) -> None:
        super().__init__((k, v) for k, v in os.environ.items()
                         if k != "CLAUDECODE" and not (k.startswith("GIT_")
                                                       and k != "GIT_EXEC_PATH"))  # fmt: skip
        config = tmp_path / "global.gitconfig"
        config.touch()
        self["GIT_CONFIG_GLOBAL"] = str(config)
        self["GIT_CONFIG_NOSYSTEM"] = "1"
        identity = {"user.name": "Flags Test", "user.email": "flags@example.invalid",
                    "init.defaultBranch": "main", "core.autocrlf": "false"}  # fmt: skip
        for i, (key, value) in enumerate(identity.items()):
            self[f"GIT_CONFIG_KEY_{i}"] = key
            self[f"GIT_CONFIG_VALUE_{i}"] = value
        self["GIT_CONFIG_COUNT"] = str(len(identity))

    def __repr__(self) -> str:
        return "<env>"


def _git(repo: Path, env: dict, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, check=True)
    return done.stdout.decode("utf-8")


def _attempt_record(function: str, unit: str, attempt: int, *,
                    model: str | None = MODEL) -> dict:  # fmt: skip
    record = _record(function, "PARTIAL", spec(4), attempt=attempt)
    record.update(unit=unit, model=model, cli_version="2.1.308")
    return record


class FakeGate:
    """The container `gate EXE/UNIT` stand-in: on a pass it writes the unit's functions as
    matched rows to status.csv and rewrites the feed; on a failure it scribbles over both
    (what a half-run tool might leave) and exits 1."""

    def __init__(self, repo: Path, functions: dict[str, tuple[str, ...]], *,
                 fail: tuple[str, ...] = ()) -> None:  # fmt: skip
        self.repo, self.functions, self.fail = repo, functions, set(fail)
        self.calls: list[list[str]] = []
        self.cflags_seen: list[str] = []

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        self.cflags_seen.append((self.repo / "config" / "cflags.txt").read_text(encoding="utf-8"))
        exe, unit = argv[argv.index("gate") + 1].split("/")
        status = self.repo / "config" / exe / "status.csv"
        feed = self.repo / "decomphub.progress.json"
        if unit in self.fail:
            status.write_text("scribbled\n", encoding="utf-8")
            feed.write_text('{"scribbled": true}\n', encoding="utf-8")
            return subprocess.CompletedProcess(argv, 1, json.dumps({"ok": False}), "made-up miss")
        names = self.functions[unit]
        rows = [line for line in status.read_text(encoding="utf-8").splitlines()[2:]
                if line and line.split(",")[1] not in names]  # fmt: skip
        rows += [f"0x{int(n[5:], 16):08X},{n},{unit},matched,100.00,3,{SHA},{DAY}" for n in names]
        status.write_text(STATUS_HEAD + "".join(r + "\n" for r in sorted(rows)),
                          encoding="utf-8", newline="\n")  # fmt: skip
        feed.write_text(json.dumps({"matched": len(rows)}) + "\n", encoding="utf-8", newline="\n")
        return subprocess.CompletedProcess(argv, 0, json.dumps({"ok": True}), "")


@dataclasses.dataclass
class Approval:
    """A tmp checkout with regated proposals, its git env and the fake container gate."""

    repo: Path
    env: dict
    gate: FakeGate

    def git(self):
        return driver.git_runner(self.repo, env=self.env)

    def head(self) -> str:
        return _git(self.repo, self.env, "rev-parse", "HEAD").strip()

    def files(self) -> dict[str, bytes | None]:
        return {rel: ((self.repo / rel).read_bytes() if (self.repo / rel).is_file() else None)
                for rel in APPROVE_FILES}  # fmt: skip

    def approve(self, ids, **kw):
        kw.setdefault("env", {})
        return flags.approve(ids, OWNER, repo=self.repo, today=DAY, runner=self.gate,
                             git=self.git(), **kw)  # fmt: skip


def _queued(repo: Path, pid: str, unit: str, function: str, text: str, *, attempt: int = 3,
            **changes) -> flags.Proposal:  # fmt: skip
    path = repo / "build" / "flags" / pid / f"{unit}.c"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    fields = dict(id=pid, unit=unit, glob=f"src/ufo2p/{unit}.c", functions=(function,),
                  candidate=f"build/flags/{pid}/{unit}.c", candidate_sha256=lf_sha256(text),
                  evidence=(f"build/driver/{RUN}/ufo2p/{function}/attempt-{attempt}/checks/"
                            "0005.json",),
                  status="regated", regate_exit=0, regate_variant="as-written",
                  regate_cflags_sha256=lf_sha256(CFLAGS_TEXT),
                  regate_log=f"build/flags/{pid}/regate.json")  # fmt: skip
    fields.update(changes)
    return _proposal(**fields)


def approve_repo(tmp_path: Path, *, fail: tuple[str, ...] = (), second: bool = False,
                 records: tuple[dict, ...] | None = None, **changes) -> Approval:  # fmt: skip
    """A committed checkout: cflags.txt (the `*` rule), docs/matching.md, the ufo2p status.csv,
    the feed, attempts.jsonl, scaffolded units, and F-0001 (u_00060c50, func_00061F30)
    regated; with `second`, also F-0002 (u_00026dd0, func_00026FD0)."""
    repo = make_repo(tmp_path)
    env = GitEnv(tmp_path)
    if records is None:
        records = (_attempt_record(F30, UNIT, 3), _attempt_record(F26, U2, 2))
    files = {
        ".gitignore": "build/\n",
        "docs/matching.md": MATCHING_DOC,
        "decomphub.progress.json": "{}\n",
        f"src/ufo2p/{UNIT}.c": SCAFFOLD,
        f"src/ufo2p/{U2}.c": f'#include "apoc.h"\n\nINCLUDE_ASM({F26});\n',
        "progress/attempts.jsonl": "".join(json.dumps(r) + "\n" for r in records),
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    write_status(repo, "ufo2p", [(0x61F30, F30, UNIT, "partial", "77.14"),
                                 (0x61F50, F50, UNIT, "partial", "46.45"),
                                 (0x26FD0, F26, U2, "partial", "50.00")])  # fmt: skip
    proposals = [_queued(repo, "F-0001", UNIT, F30, c_text(F30, marked=(F50,), tag="hit"),
                         **changes)]  # fmt: skip
    if second:
        proposals.append(_queued(repo, "F-0002", U2, F26, c_text(F26, tag="hit two"),
                                 attempt=2, siblings=(), alternatives=()))  # fmt: skip
    flags.write_queue(queue_of(repo), proposals)
    _git(repo, env, "init", "-q")
    _git(repo, env, "add", "-A")
    _git(repo, env, "commit", "-q", "-m", "base")
    return Approval(repo, env, FakeGate(repo, {UNIT: (F30,), U2: (F26,)}, fail=fail))


def test_approve_lands_one_commit(tmp_path):
    """D-12/D-13/D-32: one commit holds the rule, the C, status.csv, the feed, the queue and the
    docs row; the message has the co-author, Matched-By and Flags-Approved-By lines."""
    a = approve_repo(tmp_path)
    base = a.head()
    candidate = (a.repo / "build" / "flags" / "F-0001" / f"{UNIT}.c").read_bytes()
    report = a.approve(["F-0001"])
    assert report.landed == ("F-0001",) and report.exit_code == 0
    assert _git(a.repo, a.env, "rev-list", "--count", f"{base}..HEAD").strip() == "1"
    changed = set(_git(a.repo, a.env, "show", "--name-only", "--format=", "HEAD").split())
    assert changed == {"config/cflags.txt", f"src/ufo2p/{UNIT}.c", "config/ufo2p/status.csv",
                       "decomphub.progress.json", "config/cflags-proposals.toml",
                       "docs/matching.md"}  # fmt: skip
    assert _git(a.repo, a.env, "status", "--porcelain") == ""
    cflags_text = (a.repo / "config" / "cflags.txt").read_text(encoding="utf-8")
    assert cflags_text == CFLAGS_TEXT + (f"src/ufo2p/{UNIT}.c  wcc386@10.6 -4r -ot -s -fpi  "
                                         f"# F-0001 approved {OWNER} {DAY}\n")  # fmt: skip
    assert (a.repo / "src" / "ufo2p" / f"{UNIT}.c").read_bytes() == candidate
    (p,) = flags.read_queue(queue_of(a.repo))
    assert (p.status, p.approved_by, p.approved_date) == ("landed", OWNER, DAY)
    row = (f"| src/ufo2p/{UNIT}.c | UFO2P.EXE | wcc386@10.6 | -4r -ot -s -fpi | F-0001 approved "
           f"by {OWNER} (re-gate log under build/flags/) | {DAY} |\n")  # fmt: skip
    doc = (a.repo / "docs" / "matching.md").read_text(encoding="utf-8")
    assert "| * | TACP.EXE | wcc386@10.6 | -4r -s -fpi | made up | 2026-10-21 |\n" + row in doc
    assert doc.count(row) == 1
    message = _git(a.repo, a.env, "log", "-1", "--format=%B")
    lines = message.splitlines()
    assert lines[0] == f"feat(ufo2p): match {F30} in {UNIT} under approved flags F-0001 (C89)"
    assert driver.COAUTHOR in lines and driver.MATCHED_BY in lines
    assert f"Flags-Approved-By: {OWNER} (F-0001, {DAY})" in lines
    assert f"{F50} partial 46.45" in message  # D-32: the siblings the approval covers
    assert a.gate.calls == [[*driver.CONTAINER_CLI, "gate", f"ufo2p/{UNIT}", "--attempts", "3",
                             "--json"]]  # fmt: skip
    assert "F-0001 approved" in a.gate.cflags_seen[0]  # the gate ran under the new rule
    shown = report.format()
    assert f"sibling {F50} partial 46.45" in shown and "F-0001" in shown


def test_approve_lands_the_reduced_variant(tmp_path):
    """07-17 note: a proposal that re-gated on D-28's reduced variant lands that C."""
    reduced = c_text(F30, marked=(F50,), tag="reduced")
    a = approve_repo(tmp_path, regate_variant="reduced", variant_sha256=lf_sha256(reduced),
                     reverted=(F50,))  # fmt: skip
    path = a.repo / "build" / "flags" / "F-0001" / f"{UNIT}.reduced.c"
    path.write_text(reduced, encoding="utf-8", newline="\n")
    assert a.approve(["F-0001"]).landed == ("F-0001",)
    assert (a.repo / "src" / "ufo2p" / f"{UNIT}.c").read_bytes() == path.read_bytes()


def test_approve_restores_on_gate_failure(tmp_path):
    """A failing gate: every file back byte for byte, the queue row failed with the reason,
    no commit."""
    a = approve_repo(tmp_path, fail=(UNIT,))
    base, before = a.head(), a.files()
    report = a.approve(["F-0001"])
    assert report.exit_code == 1 and report.landed == () and report.failed == ("F-0001",)
    assert a.head() == base
    after = a.files()
    for rel in APPROVE_FILES:
        if rel != "config/cflags-proposals.toml":
            assert after[rel] == before[rel], rel
    (p,) = flags.read_queue(queue_of(a.repo))
    assert p.status == "failed" and "gate" in p.reason and "made-up miss" in p.reason
    assert (p.approved_by, p.approved_date) == ("", "")
    assert _git(a.repo, a.env, "diff", "--cached", "--name-only") == ""


def test_approve_order(tmp_path):
    """DEC-03 ordering: a batch lands in the given ID order, one commit each; the second
    proposal's re-gate on the pre-batch cflags.txt stays valid inside the batch."""
    a = approve_repo(tmp_path, second=True)
    base = a.head()
    report = a.approve(["F-0002", "F-0001"])
    assert report.landed == ("F-0002", "F-0001")
    subjects = _git(a.repo, a.env, "log", "--format=%s", f"{base}..HEAD").splitlines()
    assert subjects == [
        f"feat(ufo2p): match {F30} in {UNIT} under approved flags F-0001 (C89)",
        f"feat(ufo2p): match {F26} in {U2} under approved flags F-0002 (C89)",
    ]
    gated = [call[call.index("gate") + 1] for call in a.gate.calls]
    assert gated == [f"ufo2p/{U2}", f"ufo2p/{UNIT}"]
    text = (a.repo / "config" / "cflags.txt").read_text(encoding="utf-8")
    rules = [line.split()[0] for line in text.splitlines() if "approved" in line]
    assert rules == [f"src/ufo2p/{U2}.c", f"src/ufo2p/{UNIT}.c"]
    assert {p.status for p in flags.read_queue(queue_of(a.repo))} == {"landed"}


def test_cli_approve(tmp_path, monkeypatch, capsys):
    a = approve_repo(tmp_path)
    git = a.git()
    monkeypatch.setattr(driver, "command_runner", lambda repo, **kw: a.gate)
    monkeypatch.setattr(driver, "git_runner", lambda repo, **kw: git)
    monkeypatch.delenv("REVERSEAPOC_CLAIM", raising=False)
    assert cli_main(["flags", "approve", "F-0001", "--by", OWNER, "--repo", str(a.repo)]) == 0
    out = capsys.readouterr().out
    assert "F-0001" in out and "landed" in out
    (p,) = flags.read_queue(queue_of(a.repo))
    assert p.status == "landed" and p.approved_by == OWNER


# ---- 07-24 Task 2: approve refusals ----


def _stale_candidate(a: Approval) -> dict:
    (a.repo / "build" / "flags" / "F-0001" / f"{UNIT}.c").write_text("changed\n", encoding="utf-8")
    return {}


def _claim(a: Approval) -> dict:
    return {"env": {"REVERSEAPOC_CLAIM": f"ufo2p/{UNIT}"}}


def _dirty_unit(a: Approval) -> dict:
    (a.repo / "src" / "ufo2p" / f"{UNIT}.c").write_text("someone's edit\n", encoding="utf-8")
    return {}


def _bad_variant(a: Approval) -> dict:
    path = a.repo / "build" / "flags" / "F-0001" / f"{UNIT}.reduced.c"
    path.write_text("not the C that passed\n", encoding="utf-8")
    return {}


NOT_REGATED = dict(status="proposed", regate_exit=-1, regate_variant="empty",
                   regate_cflags_sha256="", regate_log="")  # fmt: skip
REFUSALS = {
    "proposed": (NOT_REGATED, None, None, "proposed"),
    "regate exit 1": (dict(regate_exit=1), None, None, "re-gate exit 1"),
    "changed candidate": ({}, None, _stale_candidate, "candidate"),
    "stale cflags sha": (dict(regate_cflags_sha256="b" * 64), None, None, "older"),
    "claim set": ({}, None, _claim, "REVERSEAPOC_CLAIM"),
    "unit twice": ({}, None, lambda a: {"ids": ["F-0001", "F-0001"]}, "once"),
    "dirty unit": ({}, None, _dirty_unit, "uncommitted"),
    "variant sha": (dict(regate_variant="reduced", variant_sha256="c" * 64, reverted=(F50,)),
                    None, _bad_variant, "reduced variant"),
    "unknown model": ({}, (_attempt_record(F30, UNIT, 3, model=None),), None, "model unknown"),
    "other model": ({}, (_attempt_record(F30, UNIT, 3, model="claude-other-1"),), None,
                    "claude-other-1"),
    "no attempt record": ({}, (_attempt_record(F30, UNIT, 2),), None, "model unknown"),
}  # fmt: skip


@pytest.mark.parametrize("case", REFUSALS)
def test_approve_refusals(tmp_path, case):
    """D-12 refusals: each is a FlagsError (exit 2) before any write."""
    changes, records, prepare, match = REFUSALS[case]
    a = approve_repo(tmp_path, records=records, **changes)
    extra = prepare(a) if prepare else {}
    ids = extra.pop("ids", ["F-0001"])
    base, before = a.head(), a.files()
    with pytest.raises(flags.FlagsError, match=match):
        a.approve(ids, **extra)
    assert a.head() == base and a.files() == before and a.gate.calls == []


def test_approve_refuses_while_a_drive_holds_the_lock(tmp_path):
    from reverseapoc.locks import DRIVE_LOCK, ProcessLock

    a = approve_repo(tmp_path)
    base, before = a.head(), a.files()
    other = ProcessLock(a.repo / DRIVE_LOCK)
    assert other.try_acquire()
    try:
        with pytest.raises(flags.FlagsError, match="drive"):
            a.approve(["F-0001"])
    finally:
        other.release()
    assert a.head() == base and a.files() == before and a.gate.calls == []
    assert a.approve(["F-0001"]).landed == ("F-0001",)  # the lock is free again


def test_approve_refuses_two_proposals_on_one_unit(tmp_path):
    """A batch never touches a unit twice (the queue itself keeps one open proposal a unit)."""
    a = approve_repo(tmp_path)
    (p,) = flags.read_queue(queue_of(a.repo))
    twin = dataclasses.replace(p, id="F-0002", candidate=f"build/flags/F-0002/{UNIT}.c")
    with pytest.raises(flags.FlagsError, match="both for"):
        flags._approvable(a.repo, [p, twin], ["F-0001", "F-0002"], lf_sha256(CFLAGS_TEXT))


def test_cli_approve_refusal_exits_2(tmp_path, monkeypatch, capsys):
    a = approve_repo(tmp_path)
    monkeypatch.setattr(driver, "command_runner", lambda repo, **kw: a.gate)
    monkeypatch.setenv("REVERSEAPOC_CLAIM", f"ufo2p/{UNIT}")
    assert cli_main(["flags", "approve", "F-0001", "--by", OWNER, "--repo", str(a.repo)]) == 2
    assert "REVERSEAPOC_CLAIM" in capsys.readouterr().err


# ---- 07-24 Task 3: flags default, D-33's evidence bar, pins and the docs update ----

NEW = "wcc386@10.6 -4r -oneatx -s -fpi"  # the made-up candidate default
OLD_STAR = "*  wcc386@10.6  -4r -s -fpi"
NEW_STAR = "*  wcc386@10.6  -4r -oneatx -s -fpi"
BRANCHY = b"\x85\xc0\x74\x02\x31\xc0\xc3"  # test eax,eax; je +2; xor eax,eax; ret
TINY = b"\x31\xc0\xc3"  # xor eax,eax; ret
TOOLCHAIN_DOC = (
    "# Toolchain\n\n"
    f"An old note: the `*` default stays `{OLD_STAR}` until three functions agree.\n\n"
    f"The default rule in `config/cflags.txt` is `{OLD_STAR}`, written explicitly. More prose.\n"
)
DEFAULT_FILES = ("config/cflags.txt", "docs/matching.md", "docs/toolchain.md")


@dataclasses.dataclass(frozen=True)
class Fn:
    """A made-up matched function: EXE, unit, start, and its body bytes (synthetic)."""

    exe: str
    unit: str
    start: int
    body: bytes = BRANCHY
    ruled: bool = True  # its unit has a per-unit rule equal to NEW

    @property
    def name(self) -> str:
        return f"func_{self.start:08X}"


AGREEING = (Fn("ufo2p", "u_00026dd0", 0x26FD0), Fn("ufo2p", "u_0009c1a0", 0x9C3A0),
            Fn("tacp", "u_0006fbd0", 0x6FBD0))  # fmt: skip
UNRULED = (Fn("ufo2p", "u_00089980", 0x8A0E0, ruled=False),
           Fn("tacp", "u_0006ee30", 0x6EE30, ruled=False))  # fmt: skip


class FakeExe:
    """What has_branch_or_loop and the bar read of an EXE: its functions.csv rows and flat
    image (zeros with the made-up bodies placed at their starts)."""

    def __init__(self, fns: list[Fn]) -> None:
        self.rows = tuple(FunctionRow(f.start, f.start + len(f.body), f.name, "game", f.unit,
                                      "call") for f in sorted(fns, key=lambda f: f.start))
        size = max((f.start + len(f.body) for f in fns), default=0)
        flat = bytearray(size)
        for f in fns:
            flat[f.start : f.start + len(f.body)] = f.body
        self.flat = bytes(flat)


class DefaultGate:
    """The container gate stand-in for `gate --all`: records each argv with the text of the
    cflags file it names (the committed one without --cflags); fails the kinds in `fail`
    (`pinned`, `unpinned`, `final`)."""

    def __init__(self, repo: Path, fail: tuple[str, ...] = ()) -> None:
        self.repo, self.fail = repo, set(fail)
        self.calls: list[list[str]] = []
        self.seen: list[str] = []

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        cflags = argv[argv.index("--cflags") + 1] if "--cflags" in argv else "config/cflags.txt"
        self.seen.append((self.repo / cflags).read_text(encoding="utf-8"))
        kind = ("final" if "--cflags" not in argv else
                "unpinned" if "unpinned" in cflags else "pinned")  # fmt: skip
        code = 1 if kind in self.fail else 0
        return subprocess.CompletedProcess(argv, code, json.dumps({"ok": code == 0}),
                                           "made-up gate output")  # fmt: skip


@dataclasses.dataclass
class Default:
    repo: Path
    env: dict
    gate: DefaultGate
    exes: dict[str, FakeExe]

    def head(self) -> str:
        return _git(self.repo, self.env, "rev-parse", "HEAD").strip()

    def files(self) -> dict[str, bytes]:
        return {rel: (self.repo / rel).read_bytes() for rel in DEFAULT_FILES}

    def run(self, **kw):
        kw.setdefault("env", {})
        return flags.default(NEW, OWNER, repo=self.repo, today=DAY, runner=self.gate,
                             git=driver.git_runner(self.repo, env=self.env),
                             exe_loader=self.exes.__getitem__, **kw)  # fmt: skip


def default_repo(tmp_path: Path, fns: tuple[Fn, ...] = AGREEING + UNRULED, *,
                 toolchain: str = TOOLCHAIN_DOC,
                 fail: tuple[str, ...] = ()) -> Default:  # fmt: skip
    """A committed checkout: the `*` rule plus one approved rule equal to NEW per ruled unit,
    their matching.md rows, every function matched in status.csv, and docs/toolchain.md."""
    repo = make_repo(tmp_path)
    env = GitEnv(tmp_path)
    ruled = sorted({(f.exe, f.unit) for f in fns if f.ruled})
    rules = "".join(f"src/{exe}/{unit}.c  {NEW}  # F-0001 approved {OWNER} 2026-10-27\n"
                    for exe, unit in ruled)  # fmt: skip
    rows = "".join(flags.doc_row(f"src/{exe}/{unit}.c", exe, NEW, "F-0001", "2026-10-27") + "\n"
                   for exe, unit in ruled)  # fmt: skip
    table_end = "| * | TACP.EXE | wcc386@10.6 | -4r -s -fpi | made up | 2026-10-21 |\n"
    files = {
        ".gitignore": "build/\n",
        "config/cflags.txt": CFLAGS_TEXT + rules,
        "docs/matching.md": MATCHING_DOC.replace(table_end, table_end + rows),
        "docs/toolchain.md": toolchain,
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    for exe in flags.EXES:
        write_status(repo, exe, [(f.start, f.name, f.unit, "matched", "100.00")
                                 for f in fns if f.exe == exe])  # fmt: skip
    _git(repo, env, "init", "-q")
    _git(repo, env, "add", "-A")
    _git(repo, env, "commit", "-q", "-m", "base")
    exes = {exe: FakeExe([f for f in fns if f.exe == exe]) for exe in flags.EXES}
    return Default(repo, env, DefaultGate(repo, fail), exes)


@pytest.mark.parametrize(("body", "expected"), [
    (BRANCHY, True),  # a conditional jump
    (b"\x49\x75\xfd\xc3", True),  # dec ecx; jne back: a loop
    (b"\x90\xeb\xfd", True),  # nop; jmp back to the nop: a backward jump
    (b"\xe2\xfe\xc3", True),  # loop to itself
    (TINY, False),
    (b"\xeb\x00\xc3", False),  # a forward unconditional jump
    (b"\xe8\x00\x00\x00\x00\xc3", False),  # a call is no branch
])  # fmt: skip
def test_has_branch_or_loop(body, expected):
    fn = Fn("ufo2p", UNIT, 0x40, body)
    exe = FakeExe([fn])
    assert flags.has_branch_or_loop(exe.rows[0], exe) is expected


BAR_REFUSALS = {
    "two agreeing": (AGREEING[:2], "3"),
    "three tiny": (tuple(dataclasses.replace(f, body=TINY) for f in AGREEING),
                   "branch or loop"),
    "one EXE": ((AGREEING[0], AGREEING[1], Fn("ufo2p", "u_000a34f0", 0xA3980)), "both EXEs"),
    "one region": ((AGREEING[0], Fn("ufo2p", "u_00027100", 0x27100), AGREEING[2]),
                   "0x10000 region"),
}  # fmt: skip


@pytest.mark.parametrize("case", BAR_REFUSALS)
def test_default_bar_refusals(tmp_path, case):
    """D-33: three re-gated agreeing functions, each with a branch or loop or at least 64
    bytes, from both EXEs and pairwise different 0x10000 regions; the error names what fails."""
    fns, match = BAR_REFUSALS[case]
    d = default_repo(tmp_path, fns + UNRULED)
    base, before = d.head(), d.files()
    with pytest.raises(flags.FlagsError, match=match):
        d.run()
    assert d.head() == base and d.files() == before and d.gate.calls == []


def test_default_bar_counts_size_without_a_branch(tmp_path):
    """D-33 (planner's value): 64 bytes or more counts without a branch or loop."""
    big = b"\x90" * 63 + b"\xc3"
    fns = tuple(dataclasses.replace(f, body=big) for f in AGREEING)
    d = default_repo(tmp_path, fns + UNRULED)
    evidence = flags.default_evidence(NEW, repo=d.repo, exe_loader=d.exes.__getitem__)
    assert evidence.met and [f.size for f in evidence.functions] == [64, 64, 64]
    short = tuple(dataclasses.replace(f, body=big[1:]) for f in AGREEING)
    d2 = default_repo(tmp_path / "short", short + UNRULED)
    assert not flags.default_evidence(NEW, repo=d2.repo, exe_loader=d2.exes.__getitem__).met


def test_default_evidence_mode(tmp_path):
    """--evidence prints the bar's inputs (function, size, branch/loop, EXE, region) and
    writes nothing, met or not."""
    d = default_repo(tmp_path)
    base, before = d.head(), d.files()
    report = d.run(evidence_only=True)
    text = report.format()
    for f in AGREEING:
        named = [line for line in text.splitlines() if f.name in line]
        assert named, f.name
        line = named[0]
        assert f.exe in line and f"{len(f.body)} bytes" in line and "branch/loop yes" in line
        assert f"region 0x{f.start & 0xFFFF0000:08X}" in line
    assert "met" in text
    assert d.head() == base and d.files() == before and d.gate.calls == []
    assert not (d.repo / "build" / "flags").exists()
    d2 = default_repo(tmp_path / "unmet", AGREEING[:2] + UNRULED)
    assert "not met" in d2.run(evidence_only=True).format()


def test_default_pins_and_gates(tmp_path):
    """D-14: the candidate has the new `*`, the per-unit rules, then one pin per matched unit
    without a rule; gate --all on it, the unpinned dry run, then gate --all on the committed
    file; the docs follow; one commit with the default trailer."""
    d = default_repo(tmp_path)
    base = d.head()
    report = d.run()
    assert report.exit_code == 0
    cli = list(driver.CONTAINER_CLI)
    pinned_rel = f"build/flags/default-{DAY}/cflags.txt"
    unpinned_rel = f"build/flags/default-{DAY}/cflags-unpinned.txt"
    assert d.gate.calls == [[*cli, "gate", "--all", "--cflags", pinned_rel, "--json"],
                            [*cli, "gate", "--all", "--cflags", unpinned_rel, "--json"],
                            [*cli, "gate", "--all", "--json"]]  # fmt: skip
    pinned, unpinned, final = d.gate.seen
    assert final == pinned and "pinned by D-14" not in unpinned
    rules = parse_cflags(pinned, versions=("10.6", "10.5", "11.0"))
    assert rules[0].glob == "*" and " ".join([rules[0].spec, *rules[0].flags]) == NEW
    globs = [r.glob for r in rules[1:]]
    ruled = sorted(f"src/{f.exe}/{f.unit}.c" for f in AGREEING)
    pins = [f"src/{f.exe}/{f.unit}.c" for f in sorted(UNRULED, key=lambda f: (f.exe != "ufo2p",
                                                                              f.unit))]
    assert sorted(globs[: len(ruled)]) == ruled and globs[len(ruled) :] == pins
    for pin in pins:
        rule = select_rule(rules, pin)
        assert " ".join([rule.spec, *rule.flags]) == BASE  # the old default, pinned
    assert (d.repo / "config" / "cflags.txt").read_text(encoding="utf-8") == pinned
    matching = (d.repo / "docs" / "matching.md").read_text(encoding="utf-8")
    for exe in ("UFO2P.EXE", "TACP.EXE"):
        assert f"| * | {exe} | wcc386@10.6 | -4r -oneatx -s -fpi |" in matching
        assert f"| * | {exe} | wcc386@10.6 | -4r -s -fpi |" not in matching
    for pin in pins:
        assert f"| {pin} | " in matching and "pinned by D-14" in matching
    toolchain = (d.repo / "docs" / "toolchain.md").read_text(encoding="utf-8")
    assert f"The default rule in `config/cflags.txt` is `{NEW_STAR}`" in toolchain
    assert f"the `*` default stays `{OLD_STAR}`" in toolchain  # the historical quote stays
    assert _git(d.repo, d.env, "rev-list", "--count", f"{base}..HEAD").strip() == "1"
    changed = set(_git(d.repo, d.env, "show", "--name-only", "--format=", "HEAD").split())
    assert changed == set(DEFAULT_FILES)
    lines = _git(d.repo, d.env, "log", "-1", "--format=%B").splitlines()
    assert f"Flags-Approved-By: {OWNER} (default, {DAY})" in lines
    assert any(f.name in line for f in AGREEING for line in lines)  # the evidence is quoted


def test_default_refuses_unfound_doc_text(tmp_path):
    """Ruling F16: only the canonical sentence of docs/toolchain.md is rewritten; when it is not
    there exactly once, nothing is written and no gate runs."""
    sentence = f"The default rule in `config/cflags.txt` is `{OLD_STAR}`, written explicitly."
    for doc in (TOOLCHAIN_DOC.replace(sentence, "No sentence."),
                TOOLCHAIN_DOC + "\n" + sentence + "\n"):
        root = tmp_path / str(len(doc))
        d = default_repo(root, toolchain=doc)
        base, before = d.head(), d.files()
        with pytest.raises(flags.FlagsError, match="toolchain.md"):
            d.run()
        assert d.head() == base and d.files() == before and d.gate.calls == []
        assert not (d.repo / "build" / "flags").exists()


@pytest.mark.parametrize("kind", ["pinned", "final"])
def test_default_failed_gate_writes_nothing(tmp_path, kind):
    """A failing gate --all on the pinned candidate, or on the committed file after the write,
    leaves cflags.txt and both docs byte for byte as they were and commits nothing."""
    d = default_repo(tmp_path, fail=(kind,))
    base, before = d.head(), d.files()
    with pytest.raises(flags.FlagsError, match="gate --all"):
        d.run()
    assert d.head() == base and d.files() == before


def test_default_unpinned_dry_run_is_evidence_only(tmp_path):
    d = default_repo(tmp_path, fail=("unpinned",))
    report = d.run()
    assert report.exit_code == 0 and "exit 1" in report.format()
    assert "gate --all with the new default and no pins: exit 1" in _git(
        d.repo, d.env, "log", "-1", "--format=%B")  # fmt: skip


def test_default_refusals(tmp_path):
    from reverseapoc.locks import DRIVE_LOCK, ProcessLock

    d = default_repo(tmp_path)
    before = d.files()
    with pytest.raises(flags.FlagsError, match="REVERSEAPOC_CLAIM"):
        d.run(env={"REVERSEAPOC_CLAIM": f"ufo2p/{UNIT}"})
    other = ProcessLock(d.repo / DRIVE_LOCK)
    assert other.try_acquire()
    try:
        with pytest.raises(flags.FlagsError, match="drive"):
            d.run()
    finally:
        other.release()
    with pytest.raises(flags.FlagsError, match="already"):
        flags.default(BASE, OWNER, repo=d.repo, today=DAY, runner=d.gate, env={},
                      git=driver.git_runner(d.repo, env=d.env), exe_loader=d.exes.__getitem__)
    assert d.files() == before and d.gate.calls == []


def test_cli_default_evidence(tmp_path, monkeypatch, capsys):
    d = default_repo(tmp_path)
    monkeypatch.setattr(flags, "_load_exe", lambda repo, exe: d.exes[exe])
    argv = ["flags", "default", "--rule", NEW, "--by", OWNER, "--evidence", "--repo", str(d.repo)]
    assert cli_main(argv) == 0
    out = capsys.readouterr().out
    assert all(f.name in out for f in AGREEING) and "met" in out
