"""flags (D-12, D-13, D-16, D-28, D-32): the owner-approval queue of per-unit cflags rules.

`flags propose` turns sweep hits of driver attempts into proposals in config/cflags-proposals.toml,
`flags regate` re-proves a proposal over its whole unit on a copy of src/ under a temporary cflags
file, and `flags list` shows the queue. Every attempt directory, sweep JSON, C text, address and
hash here is made up; the only committed data read is progress/attempts.jsonl (the D-16 list)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT, write_manifest
from reverseapoc import check, contextpack, flags
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
        siblings=(f"{F50} 46.45", f"{FA0} 67.50"),
        alternatives=("wcc386@10.6 -4r -oneatx -s -fpi",),
        source="sweep", candidate=f"build/flags/F-0001/{UNIT}.c", candidate_sha256=SHA,
        evidence=(f"build/driver/{RUN}/ufo2p/{F30}/attempt-3/checks/0010.json",),
        status="proposed", regate_exit=-1, regate_variant="empty", regate_cflags_sha256="",
        regate_log="", approved_by="", approved_date="", reason="",
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
                                        regate_variant="reduced", reason='a "quoted" reason')]
    flags.write_queue(path, proposals)
    assert flags.read_queue(path) == proposals
    text = path.read_text(encoding="ascii")
    assert text.count("[[proposal]]") == 2 and "version = 1" in text
    head = text.index("[[proposal]]")
    first = text[head : text.index("[[proposal]]", head + 1)]
    keys = [line.split(" = ")[0] for line in first.splitlines() if " = " in line]
    assert keys == list(flags.FIELDS)
    flags.write_queue(path, flags.read_queue(path))
    assert path.read_text(encoding="ascii") == text  # byte-stable


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


def test_siblings_listed(tmp_path):
    """D-32: every other partial row of the unit, with its percent; matched rows are keeps."""
    repo = make_repo(tmp_path)
    write_status(repo, "ufo2p", [(0x60C50, "func_00060C50", UNIT, "matched", "100.00"),
                                 (0x61F30, F30, UNIT, "partial", "77.14"),
                                 (0x61F50, F50, UNIT, "partial", "46.45"),
                                 (0x61FA0, FA0, UNIT, "partial", "67.50"),
                                 (0x70000, "func_00070000", "u_00070000", "partial", "12.00")])
    _pilot_attempt(repo)
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    assert p.siblings == (f"{F50} 46.45", f"{FA0} 67.50")
    assert p.keeps == ("func_00060C50",)


def test_merge_into_a_regated_proposal_resets_its_regate(tmp_path):
    repo = make_repo(tmp_path)
    _two_function_unit(repo, {4, 5}, {4, 5})
    make_attempt(repo, F30, run="20261027-000000",
                 checks=[(1, True, sweep_doc(F30, hits={4, 5}), c_text(F30, tag="A"))])
    flags.propose([RUN], repo=repo)
    (p,) = flags.read_queue(queue_of(repo))
    flags.write_queue(queue_of(repo), [dataclasses.replace(
        p, functions=(F30,), status="regated", regate_exit=0, regate_variant="as-written",
        regate_cflags_sha256=SHA, regate_log="build/flags/F-0001/regate.json")])
    # the evidence of F50's hit is already queued; a new run's F30 hit is the same function
    report = flags.propose(["20261027-000000"], repo=repo)
    (q,) = flags.read_queue(queue_of(repo))
    assert report.merged == ("F-0001",) and len(q.evidence) == 3
    assert (q.status, q.regate_exit, q.regate_variant, q.regate_cflags_sha256, q.regate_log) == (
        "proposed", -1, "empty", "", "")
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
