"""The driver's rename and header apply step (plan 07-34; D-19, D-29, DEC-02, DEC-04).

After a readability session (ruling F34: never a matching one) the driver reads the session's
`<attempt dir>/proposals.jsonl`, validates every proposal against the naming state of that
moment and applies the valid ones under the gate lock: symbols.csv, every committed user in
src/ and the shared header are written, one container gate runs over every affected unit (all
or nothing) and a pass is one `refactor(<exe>): rename <old> to <new>` commit with the trailer
`Renamed-By: reverseapoc drive`; a failure puts every path back byte for byte.

Every session is tests/fakeclaude.py through the Night harness of test_driver.py, in a tmp git
repo; the rename gate is a fake that records its targets. Every name and address below is made
up; no game bytes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from reverseapoc import driver
from reverseapoc.driver import GateRun
from reverseapoc.functions import FunctionRow, write_functions_csv, write_symbols_csv
from test_driver import (
    EXE,
    FUNC,
    LOG,
    RUN,
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

UNIT_B = "u_00020000"
UNIT_B_REL = f"src/{EXE}/{UNIT_B}.c"
START_B = 0x00020010
FUNC_B = f"func_{START_B:08X}"
NEW = "SoundVolume"
SYMBOLS_REL = f"config/{EXE}/symbols.csv"
FUNCTIONS_REL = f"config/{EXE}/functions.csv"
STATUS_REL = f"config/{EXE}/status.csv"
FEED = "decomphub.progress.json"
TRAILER = "Renamed-By: reverseapoc drive"
SUBJECT = f"refactor({EXE}): rename {FUNC} to {NEW}"
# u_a defines the renamed function, u_b calls it (the plan's two committed units).
A_TEXT = (f'#include "common.h"\n\n/* {FUNC}: made-up purpose of three words */\n'
          f"int {FUNC}(void)\n{{\n    return 1;\n}}\n")  # fmt: skip
B_TEXT = (f'#include "common.h"\n\nextern int {FUNC}(void);\n\n/* {FUNC_B}: calls {FUNC} */\n'
          f"int {FUNC_B}(void)\n{{\n    return {FUNC}();\n}}\n")  # fmt: skip
EDITED = A_TEXT + "/* a readability comment */\n"  # what the session leaves in its view unit


def proposals_rel(func: str = FUNC, n: int = 1) -> str:
    """Where a session of `func`'s attempt `n` writes its proposals (the driver's layout)."""
    return f"build/driver/{RUN}/{EXE}/{func}/attempt-{n}/proposals.jsonl"


def rename_line(address: int = START, name: str = NEW, *, exe: str = EXE, kind: str = "func"
                ) -> str:  # fmt: skip
    return json.dumps({"op": "rename", "exe": exe, "kind": kind, "address": f"0x{address:08X}",
                       "name": name, "evidence": "call: made-up evidence"})  # fmt: skip


def proposing(*lines: str, unit_text: str = EDITED) -> Sess:
    """A readability session that edits its view unit and leaves `lines` as its proposals."""
    return Sess(unit_text=unit_text, files=((proposals_rel(), "".join(f"{x}\n" for x in lines)),))


@dataclass
class RNight(Night):
    """A Night whose repo also holds a functions.csv, an empty symbols.csv and the two units,
    and whose fake rename gate records its targets and, on exit 0, writes a matched row per
    function of each target unit under its current symbols.csv name (as the real gate does)."""

    rename_exits: list[int] = field(default_factory=list)
    extra_files: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.rows = [FunctionRow(START, START + 0x10, FUNC, "game", UNIT, "call"),
                     FunctionRow(START_B, START_B + 0x10, FUNC_B, "game", UNIT_B, "call")]
        write_functions_csv(self.repo / FUNCTIONS_REL, self.rows, "UFO2P.EXE")
        write_symbols_csv(self.repo / SYMBOLS_REL, [], "UFO2P.EXE")
        files = {UNIT_REL: A_TEXT, UNIT_B_REL: B_TEXT, **self.extra_files}
        for rel, text in files.items():
            _write(self.repo / rel, text)
        _git(self.repo, self.env, "add", "--", FUNCTIONS_REL, SYMBOLS_REL, *files)
        _git(self.repo, self.env, "commit", "-q", "-m", "rename fixtures")
        self.base = _git(self.repo, self.env, "rev-parse", "HEAD").strip()
        self.rename_calls: list[list[str]] = []

    def _rename_gate(self, targets) -> GateRun:
        self.rename_calls.append(list(targets))
        code = self.rename_exits.pop(0) if self.rename_exits else 0
        if code == 0:
            names = self._linker_names()
            with (self.repo / STATUS_REL).open("a", encoding="utf-8", newline="\n") as fh:
                for target in targets:
                    unit = target.partition("/")[2]
                    for row in (r for r in self.rows if r.unit == unit):
                        name = names.get(row.start, row.name)
                        fh.write(f"0x{row.start:08X},{name},{unit},matched,100.00,0\n")
            _write(self.repo / FEED, '{"renamed": 1}\n')
        doc = {"ok": code == 0, "written": [], "checks": [{"splice": [
            {"exe": "UFO2P.EXE", "sha1": SHA_UFO2P}, {"exe": "TACP.EXE", "sha1": SHA_TACP}]}]}
        return GateRun(code, doc)

    def _linker_names(self) -> dict[int, str]:
        text = (self.repo / SYMBOLS_REL).read_text(encoding="utf-8")
        cells = [line.split(",") for line in text.splitlines()[2:] if line]
        return {int(c[0], 16): c[1] for c in cells}

    def readability(self, config: dict | None = None, **deps) -> driver.DriveReport:
        """One readability night (one attempt per function unless `config` says otherwise)
        with the fake rename gate wired."""
        deps.setdefault("rename_gate", self._rename_gate)
        return self.run({"session": driver.READABILITY, "attempts_per_function": 1,
                         **(config or {})}, **deps)  # fmt: skip

    def bytes_of(self, *rels: str) -> dict[str, bytes]:
        return {rel: (self.repo / rel).read_bytes() for rel in rels}

    def renames(self) -> list[dict]:
        return self.kinds(driver.KIND_RENAME)


def _validated(records: list[dict]) -> list[dict]:
    for record in records:
        driver.validate_record(record)
    return records


# ---- Task 1: the tracer ----


def test_rename_end_to_end(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    night.readability()
    assert SUBJECT in night.commits()
    assert night.commit_files(SUBJECT) == sorted([SYMBOLS_REL, UNIT_REL, UNIT_B_REL, STATUS_REL,
                                                  FEED])  # fmt: skip
    assert f"0x{START:08X},{NEW}_,func" in night.file_at(SUBJECT, SYMBOLS_REL).splitlines()
    for rel in (UNIT_REL, UNIT_B_REL):
        text = night.file_at(SUBJECT, rel)
        assert NEW in text and FUNC not in text, rel
    assert f"{NEW}_" in night.file_at(SUBJECT, STATUS_REL)
    assert TRAILER in night.message(SUBJECT).splitlines()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.APPLIED
    assert (record["op"], record["exe"], record["address"]) == ("rename", EXE, f"0x{START:08X}")
    assert (record["old"], record["new"]) == (FUNC, NEW)
    assert record["commit"] == night.sha(SUBJECT)
    assert night.git("status", "--porcelain").strip() == ""


def test_fake_gate_saw_all_units(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    night.readability()
    assert night.rename_calls == [[f"{EXE}/{UNIT}", f"{EXE}/{UNIT_B}"]]


def test_gate_failure_restores(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line())], rename_exits=[1])
    before = night.bytes_of(SYMBOLS_REL, UNIT_REL, UNIT_B_REL, STATUS_REL, FEED)
    night.readability()
    assert night.bytes_of(*before) == before
    assert not [s for s in night.commits() if s.startswith("refactor(")]
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED and record["commit"] is None
    assert "gate" in record["reason"] and "exited 1" in record["reason"]
    assert night.report.event == driver.ENDED


def test_matching_sessions_apply_no_proposal(tmp_path):
    """Ruling F34: matching nights keep the placeholders (D-17); a matching session's
    proposals.jsonl is never applied."""
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    night.run(rename_gate=night._rename_gate)
    assert night.rename_calls == [] and night.renames() == []
    assert not [s for s in night.commits() if s.startswith("refactor(")]


def test_records_name_the_readability_session(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    night.readability()
    attempts = night.kinds(driver.KIND_ATTEMPT)
    assert attempts and {a["session"] for a in attempts} == {driver.READABILITY}
    assert {s.env["REVERSEAPOC_SESSION_KIND"] for s in night.launched} == {driver.READABILITY}


def test_log_lists_the_rename_after_its_commit(tmp_path):
    """The APPLIED record names a commit, so it is appended after the rename commit and goes out
    with the night's log (never inside the rename commit)."""
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    night.readability()
    assert LOG not in night.commit_files(SUBJECT)
    committed = night.git("show", f"HEAD:{LOG}")
    assert '"kind":"rename"' in committed

