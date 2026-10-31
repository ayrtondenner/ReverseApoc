"""Readability nights (plan 07-38; D-17, D-18, D-19, D-20, D-30, DEC-04).

`drive --session readability` runs one session per matched unit through the same driver as a
matching night: the unit is claimed with kind readability, the session's env says so, its /goal
asks for `attempt check` OK with readlint clean, and its argv appends the watcom-readability
skill. After the session the driver applies its proposals (07-34), refuses it when the set of
functions the unit defines in C or marks INCLUDE_ASM changed, lands the view unit, runs the C89
lint and the container gate, then strict readlint on the unit, and commits one
`refactor(<exe>): name and document <unit> (readability)` only when all of them pass.

Every session is tests/fakeclaude.py through the Night harness of test_driver.py, in a tmp git
repo; the gate is a fake that writes status.csv the way the real one does. readlint is the real
one. Every name and address below is made up; no game bytes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from reverseapoc import cli, driver, picker, session
from reverseapoc.driver import GateRun
from reverseapoc.functions import FunctionRow, SymbolRow, write_functions_csv, write_symbols_csv
from reverseapoc.picker import Pick
from reverseapoc.status import MATCHED, StatusRow, lf_sha256, status_path, write_status
from test_drive import Rig
from test_driver import (
    EXE,
    FUNC,
    SHA_TACP,
    SHA_UFO2P,
    START,
    UNIT,
    UNIT_REL,
    Night,
    Sess,
    _git,
    _write,
)

NAME = "tick_count"
STUB_START = START + 0x20  # a second function of the unit, still INCLUDE_ASM
STUB = f"func_{STUB_START:08X}"
FUNCTIONS_REL = f"config/{EXE}/functions.csv"
SYMBOLS_REL = f"config/{EXE}/symbols.csv"
STATUS_REL = f"config/{EXE}/status.csv"
FEED = "decomphub.progress.json"
LOG = "progress/attempts.jsonl"
SUBJECT = f"refactor({EXE}): name and document {UNIT} (readability)"
TRAILER = "Readability-By: reverseapoc drive"
SHA = "ab" * 32
DATE = "2026-10-25"

BODY = f"int {NAME}(void)\n{{\n    return 0;\n}}\n"
HEADER = (f"/*\n * {NAME}: returns the current tick count.\n * Address: UFO2P.EXE 0x{START:08X}\n"
          " * Evidence: call: read by the timer loop\n */\n")  # fmt: skip
HEAD_TEXT = '#include "common.h"\n\n' + BODY  # matched, named, but no header comment (RL02)
READABLE = '#include "common.h"\n\n' + HEADER + BODY  # what a good session leaves
STILL_BAD = HEAD_TEXT + "\n/* a comment after the function is no header */\n"
READ_PICK = Pick(EXE, START, NAME, UNIT, 0x10, 0)  # the unit's lowest matched function, by C name


@dataclass
class RdNight(Night):
    """A Night whose repo holds one matched unit that fails strict readlint (named through
    symbols.csv, no header comment), real status tables, and a fake gate that, on exit 0,
    rewrites status.csv's rows of the unit with a fresh source hash and writes the feed, as the
    real gate does. `head_text` is the unit at HEAD; `stub` adds a second row of the unit that
    HEAD keeps INCLUDE_ASM."""

    picks: tuple[Pick, ...] = (READ_PICK,)
    head_text: str = HEAD_TEXT
    stub: bool = False
    named: bool = True  # symbols.csv names the matched row (else it keeps its placeholder)
    rename_exits: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.rows = [FunctionRow(START, START + 0x10, FUNC, "game", UNIT, "call")]
        if self.stub:
            self.rows.append(FunctionRow(STUB_START, STUB_START + 0x10, STUB, "game", UNIT, "call"))
        write_functions_csv(self.repo / FUNCTIONS_REL, self.rows, "UFO2P.EXE")
        symbols = [SymbolRow(START, f"{NAME}_", "func")] if self.named else []
        write_symbols_csv(self.repo / SYMBOLS_REL, symbols, "UFO2P.EXE")
        name = NAME if self.named else FUNC
        write_status(status_path(self.repo / "config", EXE),
                     [StatusRow(START, name, UNIT, MATCHED, 100.0, 1, SHA, DATE)])
        write_status(status_path(self.repo / "config", "tacp"), [])
        text = self.head_text + (f"\nINCLUDE_ASM({STUB});\n" if self.stub else "")
        _write(self.repo / UNIT_REL, text)
        rels = [FUNCTIONS_REL, SYMBOLS_REL, STATUS_REL, "config/tacp/status.csv", UNIT_REL]
        _git(self.repo, self.env, "add", "--", *rels)
        _git(self.repo, self.env, "commit", "-q", "-m", "readability fixtures")
        self.base = _git(self.repo, self.env, "rev-parse", "HEAD").strip()

    def _symbol_names(self) -> dict[int, str]:
        text = (self.repo / SYMBOLS_REL).read_text(encoding="utf-8")
        cells = [line.split(",") for line in text.splitlines()[2:] if line]
        return {int(c[0], 16): c[1].removesuffix("_") for c in cells}

    def _status_rows(self) -> None:
        names = self._symbol_names()
        unit = (self.repo / UNIT_REL).read_text(encoding="utf-8")
        write_status(status_path(self.repo / "config", EXE),
                     [StatusRow(START, names.get(START, FUNC), UNIT, MATCHED, 100.0, 1,
                                lf_sha256(unit), DATE)])  # fmt: skip
        _write(self.repo / FEED, '{"refreshed": 1}\n')

    def _gate(self, pick, attempts: int) -> GateRun:
        self.gate_calls.append((pick, attempts))
        code = self.gate_exits.pop(0) if self.gate_exits else 1
        written = []
        if code == 0:
            self._status_rows()
            written = [{"path": STATUS_REL, "start": f"0x{START:08X}", "name": NAME,
                        "unit": UNIT, "status": "matched"}]  # fmt: skip
        splice = [{"exe": "UFO2P.EXE", "sha1": SHA_UFO2P}, {"exe": "TACP.EXE", "sha1": SHA_TACP}]
        return GateRun(code, {"ok": code == 0, "written": written, "checks": [{"splice": splice}]})

    def _rename_gate(self, targets) -> GateRun:
        code = self.rename_exits.pop(0) if self.rename_exits else 0
        if code == 0:
            self._status_rows()
        splice = [{"exe": "UFO2P.EXE", "sha1": SHA_UFO2P, "ok": True},
                  {"exe": "TACP.EXE", "sha1": SHA_TACP, "ok": True}]  # fmt: skip
        return GateRun(code, {"ok": code == 0, "checks": [{"splice": splice} for _ in targets]})

    def readability(self, config: dict | None = None, **deps) -> driver.DriveReport:
        deps.setdefault("rename_gate", self._rename_gate)
        return self.run({"session": driver.READABILITY, **(config or {})}, **deps)

    def attempts(self) -> list[dict]:
        records = self.kinds(driver.KIND_ATTEMPT)
        for record in records:
            driver.validate_record(record)
        return records

    def unit_text(self) -> str:
        return (self.repo / UNIT_REL).read_text(encoding="utf-8")

    def refactors(self) -> list[str]:
        return [s for s in self.commits() if s.startswith("refactor(")]


# ---- Task 1: the tracer ----


def test_readability_session_lands(tmp_path):
    night = RdNight(tmp_path, sessions=[Sess(unit_text=READABLE)], gate_exits=[0])
    report = night.readability()
    assert report.event == driver.ENDED, report
    assert night.refactors() == [SUBJECT]
    assert night.commit_files(SUBJECT) == sorted([UNIT_REL, STATUS_REL, FEED, LOG])
    assert night.file_at(SUBJECT, UNIT_REL) == READABLE
    lines = night.message(SUBJECT).rstrip("\n").splitlines()
    assert lines[-2:] == [driver.coauthor(session.OPUS_MODEL), TRAILER]
    (record,) = night.attempts()
    assert (record["session"], record["outcome"]) == (driver.READABILITY, driver.LANDED)
    assert (record["function"], record["start"], record["unit"]) == (NAME, f"0x{START:08X}", UNIT)
    assert record["gate"]["exit"] == 0
    assert '"outcome":"LANDED"' in night.file_at(SUBJECT, LOG)  # the record rides the commit
    assert night.git("status", "--porcelain").strip() == ""


def test_readability_argv(tmp_path):
    night = RdNight(tmp_path, sessions=[Sess(unit_text=READABLE)], gate_exits=[0])
    night.readability()
    assert night.skills == [".claude/skills/watcom-readability/SKILL.md"]
    (launch,) = night.launched
    assert launch.env["REVERSEAPOC_SESSION_KIND"] == driver.READABILITY
    view = f"build/driver/night1/{EXE}/{FUNC}/attempt-1/view/src/{EXE}/{UNIT}.c"
    (prompt,) = night.prompts
    assert prompt.startswith("/goal ") and view in prompt
    assert "readlint" in prompt and "proposals.jsonl" in prompt and "landing" in prompt


def test_build_argv_appends_the_readability_skill():
    argv = session.build_argv("/goal x", claude="claude", skill=session.READABILITY_SKILL)
    at = argv.index("--append-system-prompt-file")
    assert argv[at + 1] == ".claude/skills/watcom-readability/SKILL.md"
    assert session.build_argv("/goal x", claude="claude")[at + 1] == session.SKILL


def test_readability_goal_names_the_unit_and_the_landing_check():
    view = f"build/driver/r1/{EXE}/{FUNC}/attempt-2/view/src/{EXE}/{UNIT}.c"
    goal = session.readability_goal(UNIT, EXE, unit_path=view)
    assert goal.startswith("/goal ") and view in goal and f"{EXE}/{UNIT}" in goal
    assert "pending rename" in goal and "notes.md" in goal
    with pytest.raises(ValueError):
        session.readability_goal("u_other", EXE, unit_path=view)


def test_readability_records_use_opus_and_one_session_per_unit(tmp_path):
    night = RdNight(tmp_path, sessions=[Sess(unit_text=STILL_BAD)], gate_exits=[0])
    night.readability({"attempts_per_function": 3})
    assert len(night.launched) == 1  # one session per unit, whatever attempts_per_function says
    (record,) = night.attempts()
    assert record["model_requested"] == session.OPUS_MODEL


def test_readability_lint_failure_refuses(tmp_path):
    """Owner ruling (2026-10-30): every landing runs the C89 lint before it commits; a failing
    lint refuses the readability landing before the gate."""
    night = RdNight(tmp_path, sessions=[Sess(unit_text=READABLE)], gate_exits=[0],
                    lint_exits=[1])  # fmt: skip
    night.readability()
    assert night.refactors() == [] and night.gate_calls == []
    assert night.lint_calls and night.unit_text() == HEAD_TEXT
    (record,) = night.attempts()
    assert (record["outcome"], record["abort_reason"]) == (driver.REFUSED, driver.LINT)


def test_cli_session_flag(capsys, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        cli.main(["drive", "--session", "readability", "--help"])
    assert exc.value.code == 0
    assert "--session" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["drive", "--session", "other"])
    assert exc.value.code == 2
    assert cli.build_parser().parse_args(["drive"]).session == "matching"
    seen = {}
    monkeypatch.setattr(driver, "run_drive", lambda options, seams: seen.update(o=options) or 0)
    monkeypatch.setattr(driver, "default_seams", lambda repo: "seams")
    assert cli.main(["drive", "--session", "readability", "--dry-run", "--run", "r1"]) == 0
    assert seen["o"].session == driver.READABILITY


# ---- Task 2: the refusals and outcomes ----


def _status_bytes(night: RdNight) -> bytes:
    return (night.repo / STATUS_REL).read_bytes()


def test_bytes_changed_refused(tmp_path):
    """The gate decides: a readability edit that moves a byte fails it, and nothing lands."""
    night = RdNight(tmp_path, sessions=[Sess(unit_text=READABLE)], gate_exits=[1])
    before = _status_bytes(night)
    night.readability()
    assert night.refactors() == [] and len(night.gate_calls) == 1
    assert night.unit_text() == HEAD_TEXT and _status_bytes(night) == before
    (record,) = night.attempts()
    assert (record["outcome"], record["gate"]["exit"]) == (driver.REFUSED, 1)
    assert night.report.event == driver.ENDED


def test_stub_turned_into_c_refused(tmp_path):
    """A readability session never turns an INCLUDE_ASM stub into C (D-17): the defined-set
    check refuses it before the lint and the gate run."""
    stub_c = f"\nint {STUB}(void)\n{{\n    return 1;\n}}\n"
    night = RdNight(tmp_path, stub=True, sessions=[Sess(unit_text=READABLE + stub_c)],
                    gate_exits=[0])  # fmt: skip
    head = night.unit_text()
    night.readability()
    assert night.gate_calls == [] and night.lint_calls == []
    assert night.refactors() == [] and night.unit_text() == head
    (record,) = night.attempts()
    assert (record["outcome"], record["gate"]) == (driver.REFUSED, None)


def test_dropped_definition_refused(tmp_path):
    """The other direction: a defined function turned back into a stub is refused too."""
    stubbed = f'#include "common.h"\n\nINCLUDE_ASM({FUNC});\n'
    night = RdNight(tmp_path, sessions=[Sess(unit_text=stubbed)], gate_exits=[0])
    night.readability()
    assert night.gate_calls == [] and night.refactors() == []
    assert night.attempts()[0]["outcome"] == driver.REFUSED


def test_readlint_still_failing_partial(tmp_path):
    """The gate passes (the bytes did not move) but strict readlint still reports RL02: the
    unit and status.csv go back, the view unit is kept under best/, nothing is committed."""
    night = RdNight(tmp_path, sessions=[Sess(unit_text=STILL_BAD)], gate_exits=[0])
    before = _status_bytes(night)
    night.readability()
    assert len(night.gate_calls) == 1 and night.refactors() == []
    assert night.unit_text() == HEAD_TEXT and _status_bytes(night) == before
    best = night.attempt_dir(1) / "best" / f"{UNIT}.c"
    assert best.read_text(encoding="utf-8") == STILL_BAD
    (record,) = night.attempts()
    assert record["outcome"] == driver.PARTIAL and record["gate"]["exit"] == 0
    assert night.git("status", "--porcelain").strip() == ""


def test_no_change_gave_up(tmp_path):
    night = RdNight(tmp_path, sessions=[Sess(write=None)], gate_exits=[0])
    night.readability()
    assert night.gate_calls == [] and night.lint_calls == [] and night.refactors() == []
    (record,) = night.attempts()
    assert (record["outcome"], record["gate"]) == (driver.GAVE_UP, None)


def _proposals_rel(n: int = 1) -> str:
    return f"build/driver/night1/{EXE}/{FUNC}/attempt-{n}/proposals.jsonl"


def test_proposals_applied_first(tmp_path):
    """The session proposes the name of its unit's function and documents it under the
    placeholder: the driver applies the rename first (its own commit, 07-34), rewrites the view
    unit, then lands the unit's readability commit under the new name."""
    line = json.dumps({"op": "rename", "exe": EXE, "kind": "func", "address": f"0x{START:08X}",
                       "name": NAME, "evidence": "call: read by the timer loop"})  # fmt: skip
    text = READABLE.replace(NAME, FUNC)
    night = RdNight(tmp_path, named=False, head_text=HEAD_TEXT.replace(NAME, FUNC),
                    picks=(Pick(EXE, START, FUNC, UNIT, 0x10, 0),),
                    sessions=[Sess(unit_text=text, files=((_proposals_rel(), line + "\n"),))],
                    gate_exits=[0])  # fmt: skip
    night.readability()
    rename = f"refactor({EXE}): rename {FUNC} to {NAME}"
    assert night.refactors() == [rename, SUBJECT]
    assert night.file_at(SUBJECT, UNIT_REL) == READABLE
    assert [r["outcome"] for r in night.kinds(driver.KIND_RENAME)] == [driver.APPLIED]
    assert night.attempts()[0]["outcome"] == driver.LANDED


def test_read_checks_picks_the_latest_readlint_clean_run(tmp_path):
    """The 07-31 review note: every readability run is 100%, so the record's check summary is
    the latest run whose readlint passed, never simply the first 100% run."""
    lines = [{"n": 1, "exit": 1, "sweep": False, "best_percent": 100.0, "source": "checks/0001.c",
              "sweep_hit": None, "readlint_violations": 3},
             {"n": 2, "exit": 0, "sweep": False, "best_percent": 100.0, "source": "checks/0002.c",
              "sweep_hit": None, "readlint_violations": 0},
             {"n": 3, "exit": 1, "sweep": False, "best_percent": 100.0, "source": "checks/0003.c",
              "sweep_hit": None, "readlint_violations": 1}]  # fmt: skip
    _write(tmp_path / "checks.jsonl", "".join(json.dumps(x) + "\n" for x in lines))
    assert driver.read_checks(tmp_path).best_source == "checks/0001.c"
    summary = driver.read_checks(tmp_path, readability=True)
    assert (summary.runs, summary.best_source, summary.best_percent) == (3, "checks/0002.c", 100.0)
    _write(tmp_path / "checks.jsonl", json.dumps(lines[0]) + "\n")
    assert driver.read_checks(tmp_path, readability=True).best_source is None


# ---- Task 3: the readability queue and the dry run ----


def _unit_pick(unit: str, start: int) -> Pick:
    return Pick(EXE, start, f"name_{start:x}", unit, 0x10, 0)


UNITS = {(EXE, f"u_{n}"): _unit_pick(f"u_{n}", 0x10000 * n) for n in range(1, 6)}


def _keys(picks) -> list[str]:
    return [p.unit for p in picks]


def test_queue_order():
    """Units holding Tier 1 members first, then other signed tiers', then the other matched
    units; a unit already passing readlint is absent."""
    tiers = {(EXE, "u_4"): 1, (EXE, "u_2"): 2, (EXE, "u_5"): 1}
    picks = picker.readability_queue(UNITS, tiers, {}, passes_readlint={(EXE, "u_5")})
    assert _keys(picks) == ["u_4", "u_2", "u_1", "u_3"]
    assert picks[0] == UNITS[(EXE, "u_4")]


def test_bottom_up():
    """u_1 calls a matched function of u_2, which still fails readlint: u_2 comes first and u_1
    is offered once u_2 passes. A unit's callees in its own SCC never block it."""
    callees = {(EXE, "u_1"): [(EXE, "u_2")], (EXE, "u_3"): [(EXE, "u_4")],
               (EXE, "u_4"): [(EXE, "u_3")]}  # fmt: skip
    units = {key: UNITS[key] for key in [(EXE, f"u_{n}") for n in range(1, 5)]}
    first = _keys(picker.readability_queue(units, {}, callees, passes_readlint=set()))
    assert first == ["u_2", "u_3", "u_4"]  # u_3 and u_4 share an SCC
    later = _keys(picker.readability_queue(units, {}, callees, passes_readlint={(EXE, "u_2")}))
    assert later == ["u_1", "u_3", "u_4"]


def test_readability_entries_read_the_committed_units(tmp_path):
    """The real queue's input: each committed unit with a matched row, its lowest matched
    function under its C name, and its strict readlint violation count."""
    night = RdNight(tmp_path)
    entries = driver.readability_entries(night.repo)
    assert [(e.pick, e.violations) for e in entries] == [(READ_PICK, 1)]


def test_empty_readability_queue(tmp_path):
    """DEC-04 empty: every matched unit passes readlint, so no session runs: ENDED nothing to
    do, exit 0."""
    night = RdNight(tmp_path, head_text=READABLE)
    report = night.readability(queue=driver.readability_source(night.repo))
    assert (report.event, report.reason, report.exit_code) == (driver.ENDED,
                                                              driver.NOTHING_TO_DO, 0)
    assert night.launched == [] and night.attempts() == []


def test_readability_source_runs_the_failing_unit(tmp_path):
    night = RdNight(tmp_path, sessions=[Sess(unit_text=READABLE)], gate_exits=[0])
    night.readability(queue=driver.readability_source(night.repo))
    assert night.refactors() == [SUBJECT]
    assert len(night.launched) == 1  # once it passes, the unit is no longer queued


def _readability_rig(tmp_path):
    rig = Rig(tmp_path)
    rows = [FunctionRow(START, START + 0x10, FUNC, "game", UNIT, "call")]
    write_functions_csv(rig.repo / FUNCTIONS_REL, rows, "UFO2P.EXE")
    write_symbols_csv(rig.repo / SYMBOLS_REL, [SymbolRow(START, f"{NAME}_", "func")], "UFO2P.EXE")
    write_status(status_path(rig.repo / "config", EXE),
                 [StatusRow(START, NAME, UNIT, MATCHED, 100.0, 1, SHA, DATE)])
    write_status(status_path(rig.repo / "config", "tacp"), [])
    _write(rig.repo / UNIT_REL, HEAD_TEXT)
    _write(rig.repo / "include/common.h", "/* made up */\n")
    rels = [FUNCTIONS_REL, SYMBOLS_REL, STATUS_REL, "config/tacp/status.csv", UNIT_REL,
            "include/common.h"]  # fmt: skip
    _git(rig.repo, rig.env, "add", "--", *rels)
    _git(rig.repo, rig.env, "commit", "-q", "-m", "readability fixtures")
    return rig


def test_readability_dry_run(tmp_path, capsys):
    """`drive --session readability --dry-run --json` lists the queued units in order with their
    readlint violation counts and launches nothing (no claude, no gate, no pack)."""
    rig = _readability_rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, session=driver.READABILITY)
    assert code == 0, out
    doc = json.loads(out)
    assert doc == {"session": driver.READABILITY,
                   "units": [{"exe": EXE, "unit": UNIT, "start": f"0x{START:08X}",
                              "function": NAME, "violations": 1}]}  # fmt: skip
    assert rig.packs.built == [] and not rig.commands("gate")
    assert not rig.commands("ghidra-export")
    assert not [c for c in rig.runner.calls if c[:1] == ["claude"]]


def test_readability_dry_run_text(tmp_path, capsys):
    rig = _readability_rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True, session=driver.READABILITY)
    assert code == 0
    assert f"{EXE} {UNIT} 0x{START:08X} {NAME} readlint 1 violation" in out
