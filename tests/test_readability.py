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

from dataclasses import dataclass, field

import pytest

from reverseapoc import cli, driver, session
from reverseapoc.driver import GateRun
from reverseapoc.functions import FunctionRow, SymbolRow, write_functions_csv, write_symbols_csv
from reverseapoc.status import MATCHED, StatusRow, lf_sha256, status_path, write_status
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


@dataclass
class RdNight(Night):
    """A Night whose repo holds one matched unit that fails strict readlint (named through
    symbols.csv, no header comment), real status tables, and a fake gate that, on exit 0,
    rewrites status.csv's rows of the unit with a fresh source hash and writes the feed, as the
    real gate does. `head_text` is the unit at HEAD; `stub` adds a second row of the unit that
    HEAD keeps INCLUDE_ASM."""

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
