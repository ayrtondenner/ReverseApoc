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

import pytest

from reverseapoc import driver, unitdefs
from reverseapoc.driver import GateRun
from reverseapoc.functions import (
    FunctionRow,
    SymbolRow,
    write_functions_csv,
    write_symbols_csv,
)
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


# ---- Task 2: collisions, refusals, header proposals, deferral ----

SND_REL = "include/snd.h"
SND_TEXT = "#ifndef SND_H\n#define SND_H\n\n#define SND_MAX 4\n\n#endif\n"
SND_NEW = "#ifndef SND_H\n#define SND_H\n\n#define SND_MAX 8\n\n#endif\n"
B_SND = B_TEXT.replace('#include "common.h"\n', '#include "common.h"\n#include "snd.h"\n')
CLAIM_REL = f"build/driver/claims/{EXE}__{UNIT_B}.json"


def header_line(path: str = SND_REL, text: str = SND_NEW) -> str:
    return json.dumps({"op": "header", "path": path, "text": text,
                       "evidence": "call: made-up evidence"})  # fmt: skip


def _refactors(night: RNight) -> list[str]:
    return [s for s in night.commits() if s.startswith("refactor(")]


def test_collision_refused(tmp_path):
    """DEC-02 adjacency: one name for two addresses; the second proposal meets the first's
    symbols.csv row and is refused."""
    night = RNight(tmp_path, sessions=[proposing(rename_line(), rename_line(START_B))])
    night.readability()
    first, second = _validated(night.renames())
    assert first["outcome"] == driver.APPLIED and first["new"] == NEW
    assert second["outcome"] == driver.REFUSED and second["address"] == f"0x{START_B:08X}"
    assert "already used" in second["reason"]
    assert _refactors(night) == [SUBJECT]


def test_malformed_file_refused(tmp_path):
    night = RNight(tmp_path, sessions=[proposing("{not json", rename_line())])
    night.readability()
    bad, good = _validated(night.renames())
    assert bad["outcome"] == driver.REFUSED and bad["op"] is None
    assert "line 1" in bad["reason"]
    assert good["outcome"] == driver.APPLIED
    assert night.report.event == driver.ENDED


def test_unreadable_file_is_one_refusal(tmp_path):
    """A proposals.jsonl that is not UTF-8 cannot be split into trusted lines: one REFUSED
    record, and the night goes on."""
    sess = Sess(unit_text=EDITED)
    night = RNight(tmp_path, sessions=[sess])
    path = night.repo / proposals_rel()

    def session(argv, **kwargs):
        done = night._session(argv, **kwargs)
        path.write_bytes(b"\xff\xfe" + rename_line().encode() + b"\n")
        return done

    night.readability(session=session)
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED and record["op"] is None
    assert "UTF-8" in record["reason"]
    assert night.report.event == driver.ENDED


def test_name_that_is_no_identifier_is_a_null_op_refusal(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line(name="9lives"))])
    night.readability()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED and record["op"] is None
    assert "9lives" in record["reason"] and "identifier" in record["reason"]


def test_last_line_for_a_row_wins(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line(name="SoundLevel"), rename_line())])
    night.readability()
    early, late = _validated(night.renames())
    assert early["outcome"] == driver.REFUSED and "superseded" in early["reason"]
    assert late["outcome"] == driver.APPLIED and late["new"] == NEW
    assert _refactors(night) == [SUBJECT]


def test_header_proposal_gates_includers(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(header_line())],
                   extra_files={SND_REL: SND_TEXT, UNIT_B_REL: B_SND})  # fmt: skip
    night.readability()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.APPLIED and record["op"] == "header"
    assert record["path"] == SND_REL
    assert night.rename_calls == [[f"{EXE}/{UNIT_B}"]]
    subject = f"refactor(include): write {SND_REL}"
    assert subject in night.commits()
    assert SND_REL in night.commit_files(subject)
    assert night.file_at(subject, SND_REL) == SND_NEW
    assert TRAILER in night.message(subject).splitlines()


def test_header_includers_through_other_headers(tmp_path):
    """An includer of a header that includes the proposed one is gated too."""
    mix = '#ifndef MIX_H\n#define MIX_H\n#include "snd.h"\n#endif\n'
    b_mix = B_TEXT.replace('#include "common.h"\n', '#include "common.h"\n#include <mix.h>\n')
    night = RNight(tmp_path, sessions=[proposing(header_line())],
                   extra_files={SND_REL: SND_TEXT, "include/mix.h": mix, UNIT_B_REL: b_mix})
    night.readability()
    assert night.rename_calls == [[f"{EXE}/{UNIT_B}"]]


def test_header_proposal_failing_gate_restores(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(header_line())], rename_exits=[1],
                   extra_files={SND_REL: SND_TEXT, UNIT_B_REL: B_SND})  # fmt: skip
    night.readability()
    assert (night.repo / SND_REL).read_text(encoding="utf-8") == SND_TEXT
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED and "exited 1" in record["reason"]


def test_new_header_without_includers_writes_it(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(header_line(text=SND_TEXT))])
    night.readability()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.APPLIED
    assert night.rename_calls == [[]]  # no includer: `gate --all` checks every matched unit
    assert night.git("show", f"HEAD:{SND_REL}") == SND_TEXT


def test_reserved_header_refused(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(header_line("include/common.h"))])
    before = night.bytes_of("include/common.h")
    night.readability()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED and "reserved" in record["reason"]
    assert night.bytes_of("include/common.h") == before
    assert night.rename_calls == []


def test_rename_rewrites_a_header_that_names_it(tmp_path):
    proto = f"#ifndef SND_H\n#define SND_H\nint {FUNC}(void);\n#endif\n"
    night = RNight(tmp_path, sessions=[proposing(rename_line())],
                   extra_files={SND_REL: proto, UNIT_B_REL: B_SND})  # fmt: skip
    night.readability()
    assert SND_REL in night.commit_files(SUBJECT)
    assert f"int {NEW}(void);" in night.file_at(SUBJECT, SND_REL)


COMMON = "#ifndef COMMON_H\n#define COMMON_H\ntypedef unsigned char u8;\n#endif\n"
B_STATIC = B_SND.replace("extern int", "static int helper_count;\nextern int")


@pytest.mark.parametrize(("name", "where"), [("u8", "include/common.h"),
                                             ("SND_MAX", SND_REL),
                                             ("helper_count", UNIT_B_REL)])  # fmt: skip
def test_src_names_hold_header_and_file_scope_names(tmp_path, name, where):
    """Ruling (07-19 as built): the typedefs of include/common.h, every name a driver-written
    header declares, and every file-scope name of a committed unit are taken."""
    night = RNight(tmp_path, sessions=[proposing(rename_line(START_B, name))],
                   extra_files={"include/common.h": COMMON, SND_REL: SND_TEXT,
                                UNIT_B_REL: B_STATIC})  # fmt: skip
    night.readability()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED
    assert f"{name} is already a file-scope name in {where}" in record["reason"]
    assert night.rename_calls == []


def test_deferred_behind_live_claim(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    claim = night.repo / CLAIM_REL
    _write(claim, json.dumps({"run": RUN, "worker": 1, "exe": EXE, "unit": UNIT_B}) + "\n")
    seen: list[list[str]] = []

    def lint(pick):  # the other worker's claim is released while this session lands
        seen.append([r["outcome"] for r in night.renames()])
        claim.unlink()
        return 0

    night.readability(lint=lint)
    assert seen == [[driver.DEFERRED]]
    deferred, applied = _validated(night.renames())
    assert deferred["outcome"] == driver.DEFERRED and UNIT_B in deferred["reason"]
    assert deferred["commit"] is None
    assert applied["outcome"] == driver.APPLIED and applied["commit"] == night.sha(SUBJECT)
    assert night.rename_calls == [[f"{EXE}/{UNIT}", f"{EXE}/{UNIT_B}"]]


def test_deferred_still_held_at_the_end_stays_deferred(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    _write(night.repo / CLAIM_REL, json.dumps({"run": RUN, "worker": 1}) + "\n")
    night.readability()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.DEFERRED
    assert _refactors(night) == [] and night.rename_calls == []


def test_two_renames_one_unit_in_order(tmp_path):
    """DEC-02 adjacency: two renames that both touch u_b land as two commits in proposal
    order, the second on the first."""
    night = RNight(tmp_path, sessions=[proposing(rename_line(), rename_line(START_B, "SoundMute"))])
    night.readability()
    second = f"refactor({EXE}): rename {FUNC_B} to SoundMute"
    assert _refactors(night) == [SUBJECT, second]
    text = night.file_at(second, UNIT_B_REL)
    assert NEW in text and "SoundMute" in text and FUNC not in text and FUNC_B not in text
    symbols = night.file_at(second, SYMBOLS_REL).splitlines()
    assert f"0x{START:08X},{NEW}_,func" in symbols and f"0x{START_B:08X},SoundMute_,func" in symbols


def test_rename_claim_is_released(tmp_path):
    """The multi-unit claim of kind rename (D-06) is gone once the commit is made."""
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    held: list[bool] = []

    def gate(targets):
        held.append((night.repo / CLAIM_REL).is_file())
        kind = json.loads((night.repo / CLAIM_REL).read_text(encoding="utf-8"))["kind"]
        held.append(kind == driver.KIND_RENAME)
        return night._rename_gate(targets)

    night.readability(rename_gate=gate)
    assert held == [True, True]
    assert not (night.repo / CLAIM_REL).exists()


def test_file_scope_names():
    """unitdefs.file_scope_names: what a unit or header gives at file scope (07-34)."""
    text = ('#include "common.h"\n#define LIMIT 4\nstatic int count = 0x1F;\n'
            "static char table[SIZE_OF];\ntypedef struct tag { int inner; } thing_t;\n"
            "/* comment_word */\nint f(int param)\n"
            "{\n    int local = 0x10;\n    return local;\n}\n")
    names = unitdefs.file_scope_names(text)
    assert {"LIMIT", "count", "table", "tag", "thing_t", "f"} <= names
    assert not names & {"inner", "param", "local", "comment_word", "x1F", "SIZE_OF", "int",
                        "static", "common", "h"}  # fmt: skip


def test_included_headers():
    text = '#include "snd.h"\n# include <mix.h>\n/* #include "no.h" */\n#include "common.h"\n'
    assert unitdefs.included_headers(text) == {"snd.h", "mix.h", "common.h"}


# ---- Task 3: renames carried into views at landing; the own claim never blocks ----

MUTE = "SoundMute"
# u_a calls u_b's function too, so a rename of func_00020010 reaches the claimed unit u_a.
A_CALLS_B = A_TEXT.replace('#include "common.h"\n',
                           f'#include "common.h"\n\nextern int {FUNC_B}(void);\n').replace(
    "    return 1;", f"    return {FUNC_B}();")  # fmt: skip


def _rename_mid_session(night: RNight) -> None:
    """Another worker's rename commit lands while the session runs: func_00020010 becomes
    SoundMute in symbols.csv and in both committed units."""
    write_symbols_csv(night.repo / SYMBOLS_REL,
                      [SymbolRow(START_B, f"{MUTE}_", "func")], "UFO2P.EXE")  # fmt: skip
    for rel in (UNIT_REL, UNIT_B_REL):
        path = night.repo / rel
        path.write_bytes(path.read_bytes().replace(FUNC_B.encode(), MUTE.encode()))
    _git(night.repo, night.env, "add", "--", SYMBOLS_REL, UNIT_REL, UNIT_B_REL)
    _git(night.repo, night.env, "commit", "-q", "-m", f"refactor({EXE}): rename {FUNC_B} to {MUTE}")


def test_view_picks_up_rename_at_landing(tmp_path):
    night = RNight(tmp_path, sessions=[Sess(unit_text=A_CALLS_B + "/* edited */\n")],
                   extra_files={UNIT_REL: A_CALLS_B})  # fmt: skip
    landed: list[str] = []

    def session(argv, **kwargs):
        done = night._session(argv, **kwargs)
        _rename_mid_session(night)
        return done

    def lint(pick):
        landed.append((night.repo / UNIT_REL).read_text(encoding="utf-8"))
        return 0

    night.run({"attempts_per_function": 1}, session=session, lint=lint)
    assert night.seen[0]["files"][f"src/{EXE}/{UNIT}.c"].count(FUNC_B.encode()) == 2
    (text,) = landed
    assert MUTE in text and FUNC_B not in text and "/* edited */" in text
    view = night.attempt_dir() / "view" / UNIT_REL
    assert FUNC_B not in view.read_text(encoding="utf-8")
    assert night.report.event == driver.ENDED


def test_renames_since_maps_old_to_new(tmp_path):
    """_renames_since(view head): per EXE, every C name symbols.csv changed between the view's
    commit and HEAD, old -> new (a placeholder when the row had no symbols.csv name)."""
    night = RNight(tmp_path)
    before = night.base
    _rename_mid_session(night)
    probe = driver._Night(night.config(), night.deps())
    assert probe._renames_since(before) == {EXE: {FUNC_B: MUTE}}
    assert probe._renames_since(night.git("rev-parse", "HEAD").strip()) == {}


def test_own_claim_not_blocking(tmp_path):
    """The session renames its own unit's function: no DEFERRED, its view unit is rewritten in
    place and lands under the new name, the other committed user is rewritten too."""
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    landed: list[str] = []

    def lint(pick):
        landed.append((night.repo / UNIT_REL).read_text(encoding="utf-8"))
        return 0

    night.readability(lint=lint)
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.APPLIED
    view = (night.attempt_dir() / "view" / UNIT_REL).read_text(encoding="utf-8")
    assert NEW in view and FUNC not in view and "a readability comment" in view
    (text,) = landed
    assert NEW in text and FUNC not in text and "a readability comment" in text
    assert FUNC not in night.file_at(SUBJECT, UNIT_B_REL)


def test_renamed_function_keeps_pass_count_and_history(tmp_path):
    """Ruling note (07-23 as built): records name the C name, so after a rename a function's
    records carry two names; every reader keys them by (exe, start)."""
    from reverseapoc import attempt, flags

    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    night.readability()
    (first,) = night.kinds(driver.KIND_ATTEMPT)
    assert first["function"] == FUNC and first["pass"] == 1
    later = {**first, "function": NEW, "pass": 2, "run": "night2"}
    driver.validate_record(later)
    with (night.repo / LOG).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(later, separators=(",", ":")) + "\n")
    log = night.repo / LOG
    assert driver.pass_index(log)[(EXE, START)] == 2
    assert driver.passes_of(log, (EXE, START)) == 2
    notes = attempt.earlier_notes(night.repo, EXE, FUNC)
    names = [json.loads(r)["function"] for r in notes.records]
    assert names == [FUNC, NEW]
    models = flags._attempt_models(log)
    assert models[(RUN, EXE, START, 1)][0] == 1 and models[("night2", EXE, START, 1)][0] == 2


# ---- failures inside the apply step (self-review, Rule 1) ----

TOUCHED = (SYMBOLS_REL, UNIT_REL, UNIT_B_REL, STATUS_REL, FEED)


def test_unit_claimed_meanwhile_is_deferred(tmp_path, monkeypatch):
    """A rename claim that cannot be taken after all (another taker won the O_EXCL race) is
    DEFERRED, never REFUSED, and nothing is written."""
    real_take = driver.Claims.take

    def take(self, record):
        return False if record["kind"] == driver.KIND_RENAME else real_take(self, record)

    monkeypatch.setattr(driver.Claims, "take", take)
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    before = night.bytes_of(*TOUCHED)
    night.readability()
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.DEFERRED and "claimed meanwhile" in record["reason"]
    assert night.rename_calls == [] and night.bytes_of(*before) == before


def test_commit_failure_restores_and_stops(tmp_path):
    """A naming commit that fails (index.lock twice) puts every path back, status.csv and the
    feed to their bytes before the gate, records the proposal REFUSED and stops the night."""
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    night.fail_verbs = {"commit": 2}
    before = night.bytes_of(*TOUCHED)
    night.readability()
    assert night.report.event == driver.STOPPED and night.report.reason == driver.TOOL
    assert night.bytes_of(*before) == before
    assert night.rename_calls == [[f"{EXE}/{UNIT}", f"{EXE}/{UNIT_B}"]]
    assert _refactors(night) == []
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED and "naming commit failed" in record["reason"]


def test_gate_error_restores_and_stops(tmp_path):
    night = RNight(tmp_path, sessions=[proposing(rename_line())])
    before = night.bytes_of(*TOUCHED)

    def gate(targets):
        _write(night.repo / STATUS_REL, "half written\n")
        raise RuntimeError("the container went away")

    night.readability(rename_gate=gate)
    assert night.report.event == driver.STOPPED and night.report.reason == driver.TOOL
    assert "the container went away" in night.report.detail
    assert night.bytes_of(*before) == before
    (record,) = _validated(night.renames())
    assert record["outcome"] == driver.REFUSED
