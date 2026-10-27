"""flags (D-12, D-13, D-16, D-28, D-32): the owner-approval queue of per-unit cflags rules.

`flags propose` turns sweep hits of driver attempts into proposals in config/cflags-proposals.toml,
`flags regate` re-proves a proposal over its whole unit on a copy of src/ under a temporary cflags
file, and `flags list` shows the queue. Every attempt directory, sweep JSON, C text, address and
hash here is made up; the only committed data read is progress/attempts.jsonl (the D-16 list)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc import check, flags
from reverseapoc.cli import main as cli_main
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
                   for start, name, unit, status, percent in rows)  # fmt: skip
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
