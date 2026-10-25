"""gate (D-21, D-24, AGT-06): the only writer of config/<exe>/status.csv. check itself is faked
here (its own tests are tests/test_check.py): a fake check models a tree of unit files, each
defining some functions, and lands every defined function of every unit file present, as
check's land step does. Every name, address and hash is made up."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from conftest import write_manifest
from reverseapoc import gate
from reverseapoc.check import CheckError, CheckResult, ExeLand, FunctionCheck, SourceCheck
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, UnitRow, write_functions_csv, write_units_csv
from reverseapoc.land import LandResult
from reverseapoc.relocs import RelocResult
from reverseapoc.status import MATCHED, StatusRow, lf_sha256, read_status, status_path, write_status

UFO, TACP = "UFO2P.EXE", "TACP.EXE"
STEMS = {UFO: "ufo2p", TACP: "tacp"}
A1, A2, B1, C1 = 0x10000, 0x10010, 0x10020, 0x10030  # UFO2P
T1 = 0x20000  # TACP
UNIT_A, UNIT_B, UNIT_C, UNIT_T = "u_00010000", "u_00010020", "u_00010030", "u_00020000"
ROWS = {
    UFO: [(A1, UNIT_A), (A2, UNIT_A), (B1, UNIT_B), (C1, UNIT_C)],
    TACP: [(T1, UNIT_T)],
}
TODAY = date(2026, 10, 25)
SHA1 = "0" * 40


def fname(start: int) -> str:
    return f"func_{start:08X}"


@dataclass
class Tree:
    """A tmp repository: manifest, config/<exe>/{functions,units}.csv, src/<exe>/<unit>.c, and
    which functions each unit file defines in C (`defined`)."""

    root: Path
    defined: dict[tuple[str, str], list[int]] = field(default_factory=dict)

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def src(self) -> Path:
        return self.root / "src"

    @property
    def roots(self) -> gate.GateRoots:
        return gate.GateRoots(orig_dir=self.root / "orig", manifest=self.root / "targets.toml",
                              config_root=self.config, src_root=self.src,
                              build_dir=self.root / "build")  # fmt: skip

    def argv(self) -> list[str]:
        r = self.roots
        pairs = {"--orig": r.orig_dir, "--manifest": r.manifest, "--config": r.config_root,
                 "--src": r.src_root, "--build": r.build_dir}  # fmt: skip
        return [part for option, path in pairs.items() for part in (option, str(path))]

    def source(self, exe: str, unit: str) -> Path:
        return self.src / STEMS[exe] / f"{unit}.c"

    def write_unit(self, exe: str, unit: str, starts: list[int], *, crlf: bool = False) -> str:
        """Write the unit file defining `starts` in C (the other rows of the unit stay
        INCLUDE_ASM) and return its LF text."""
        rows = [start for start, u in ROWS[exe] if u == unit]
        lines = ['#include "common.h"']
        for start in rows:
            lines.append(f"int {fname(start)}(void) {{ return {start}; }}" if start in starts
                         else f"INCLUDE_ASM({fname(start)});")  # fmt: skip
        text = "\n".join(lines) + "\n"
        path = self.source(exe, unit)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        self.defined[(exe, unit)] = list(starts)
        return text

    def remove_unit(self, exe: str, unit: str) -> None:
        self.source(exe, unit).unlink()
        del self.defined[(exe, unit)]

    def status(self, exe: str) -> Path:
        return status_path(self.config, STEMS[exe])

    def rows(self, exe: str) -> list[StatusRow]:
        return read_status(self.status(exe))


def make_tree(root: Path) -> Tree:
    root.mkdir(parents=True, exist_ok=True)
    write_manifest(root / "targets.toml", {UFO: b"ufo", TACP: b"tacp"})
    for exe, rows in ROWS.items():
        config = root / "config" / STEMS[exe]
        functions = [FunctionRow(s, s + 0x10, fname(s), "game", u, "call") for s, u in rows]
        write_functions_csv(config / "functions.csv", functions, exe)
        starts = {u: [s for s, x in rows if x == u] for _, u in rows}
        spans = [UnitRow(u, min(s), max(s) + 0x10, "hand") for u, s in sorted(starts.items())]
        write_units_csv(config / "units.csv", spans, exe)
    return Tree(root)


@pytest.fixture
def tree(tmp_path) -> Tree:
    return make_tree(tmp_path)


def ok_function(start: int, percent: float = 100.0, *, ok: bool = True) -> FunctionCheck:
    reloc = RelocResult(ok, () if ok else ("0x00010001: wrong target",), frozenset(), frozenset(),
                        start, 0x10, "1" * 40)  # fmt: skip
    return FunctionCheck(fname(start), start, 0x10, percent, reloc, ok, 0 if ok else 1,
                         None if ok else start)  # fmt: skip


def splice(exe: str, landed, *, ok: bool = True) -> ExeLand:
    result = LandResult(b"", SHA1 if ok else "f" * 40, SHA1, tuple(sorted(landed)), 0)
    return ExeLand(exe, result)


class FakeCheck:
    """Stands in for check_unit. It defines the functions the tree's unit file defines, all at
    100.0 unless `percent` says otherwise, and lands every function every present unit file
    defines (or `landed[exe]` when given). `mismatch` makes the gated unit's check fail;
    `error` raises it as a tool error."""

    def __init__(self, tree: Tree, *, mismatch: bool = False, error: Exception | None = None,
                 landed: dict[str, set[int]] | None = None) -> None:  # fmt: skip
        self.tree, self.mismatch, self.error = tree, mismatch, error
        self.landed = landed or {}
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, exe: str, unit: str, **kwargs) -> CheckResult:
        self.calls.append((exe, unit, kwargs))
        if self.error is not None:
            raise self.error
        name = next(n for n, s in STEMS.items() if s == exe.lower() or n.lower() == exe.lower())
        functions = tuple(ok_function(s, 50.0 if self.mismatch else 100.0)
                          for s in self.tree.defined.get((name, unit), []))  # fmt: skip
        splices = []
        for other in (UFO, TACP):
            default = {s for (e, _), starts in self.tree.defined.items() if e == other
                       for s in starts}  # fmt: skip
            splices.append(splice(other, self.landed.get(other, default)))
        return CheckResult(exe, unit, "wcc386", ("-4r",), functions, tuple(splices))


def run_gate(tree: Tree, *targets: str, check: FakeCheck | None = None, attempts: int = 0):
    pairs = [tuple(t.split("/")) for t in targets]
    return gate.gate_units(pairs, roots=tree.roots, attempts=attempts, today=TODAY,
                           check_fn=check or FakeCheck(tree))  # fmt: skip


# ---- Task 1: the tracer -------------------------------------------------------------------------


def test_gate_writes_matched_rows_on_pass(tree):
    text = tree.write_unit(UFO, UNIT_A, [A1], crlf=True)
    check = FakeCheck(tree)
    result = gate.gate_unit("ufo2p", UNIT_A, roots=tree.roots, attempts=2, today=TODAY,
                            check_fn=check)  # fmt: skip
    assert result.exit_code == 0 and result.ok
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert lf_sha256(text) == sha
    assert tree.rows(UFO) == [StatusRow(A1, fname(A1), UNIT_A, MATCHED, 100.0, 2, sha,
                                        "2026-10-25")]  # fmt: skip
    assert not tree.status(TACP).exists()  # sparse: no row, no file
    assert [(exe, unit) for exe, unit, _ in check.calls] == [("ufo2p", UNIT_A)]
    doc = result.to_json()
    assert doc["ok"] is True and doc["exit_code"] == 0
    assert [w["start"] for w in doc["written"]] == ["0x00010000"]


def test_gate_writes_nothing_on_mismatch(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    write_status(tree.status(UFO), [StatusRow(B1, fname(B1), UNIT_B, MATCHED, 100.0, 1,
                                              "c" * 64, "2026-10-01")])  # fmt: skip
    before = tree.status(UFO).read_bytes()
    result = run_gate(tree, f"ufo2p/{UNIT_A}", check=FakeCheck(tree, mismatch=True))
    assert result.exit_code == 1 and not result.ok
    assert result.written == ()
    assert tree.status(UFO).read_bytes() == before


def test_gate_writes_nothing_on_a_tool_error(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    with pytest.raises(CheckError, match="objdiff"):
        run_gate(tree, f"ufo2p/{UNIT_A}", check=FakeCheck(tree, error=CheckError("objdiff")))
    assert not tree.status(UFO).exists()


def test_gate_refuses_negative_attempts(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    with pytest.raises(CheckError, match="attempts"):
        run_gate(tree, f"ufo2p/{UNIT_A}", attempts=-1)
    assert not tree.status(UFO).exists()


@pytest.mark.parametrize(
    ("fake", "code"),
    [({}, 0), ({"mismatch": True}, 1), ({"error": CheckError("objdiff-cli not found")}, 2)],
    ids=["pass", "mismatch", "tool"],
)
def test_gate_cli_exit_codes(tree, monkeypatch, capsys, fake, code):
    tree.write_unit(UFO, UNIT_A, [A1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree, **fake))
    assert cli_main(["gate", f"ufo2p/{UNIT_A}", *tree.argv(), "--attempts", "1", "--json"]) == code
    out = capsys.readouterr()
    if code == 2:
        assert "reverseapoc gate: error: objdiff-cli not found" in out.err
        assert not tree.status(UFO).exists()
    else:
        assert json.loads(out.out)["ok"] is (code == 0)
        assert (tree.rows(UFO)[0].attempts == 1) if code == 0 else not tree.status(UFO).exists()


@pytest.mark.parametrize("target", ["ufo2p", "ufo2p/", "/u_x", "ufo2p/a/b"])
def test_gate_cli_refuses_a_bad_target(tree, monkeypatch, capsys, target):
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    assert cli_main(["gate", target, *tree.argv()]) == 2
    assert "expected EXE/UNIT" in capsys.readouterr().err


def test_gate_cli_text_output(tree, monkeypatch, capsys):
    tree.write_unit(UFO, UNIT_A, [A1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    assert cli_main(["gate", f"ufo2p/{UNIT_A}", *tree.argv()]) == 0
    out = capsys.readouterr().out
    assert f"matched {fname(A1)}" in out
    assert out.rstrip().endswith("ok")


# ---- Task 2: the cross-check (D-24, AGT-06), several targets (F1), re-gating (F29) -------------


def matched(start: int, unit: str, *, attempts: int = 0, day: str = "2026-10-01",
            sha: str = "c" * 64) -> StatusRow:  # fmt: skip
    return StatusRow(start, fname(start), unit, MATCHED, 100.0, attempts, sha, day)


def seed(tree: Tree, exe: str, rows: list[StatusRow]) -> bytes:
    write_status(tree.status(exe), rows)
    return tree.status(exe).read_bytes()


def owner_rows(exe: str) -> dict[int, FunctionRow]:
    return {s: FunctionRow(s, s + 0x10, fname(s), "game", u, "call") for s, u in ROWS[exe]}


def test_crosscheck_refuses_a_reverted_match(tree):
    before = seed(tree, UFO, [matched(A1, UNIT_A)])
    tree.write_unit(UFO, UNIT_A, [])  # func_A1 back to INCLUDE_ASM
    tree.write_unit(UFO, UNIT_B, [B1])
    result = run_gate(tree, f"ufo2p/{UNIT_B}")
    assert result.exit_code == 1 and result.written == ()
    assert any(fname(A1) in p and "not landed" in p for p in result.problems)
    assert tree.status(UFO).read_bytes() == before


def test_crosscheck_refuses_an_extra_landed_function(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(UFO, UNIT_B, [B1])  # compiled and landed, never gated
    result = run_gate(tree, f"ufo2p/{UNIT_A}")
    assert result.exit_code == 1
    assert any(fname(B1) in p and "landed" in p for p in result.problems)
    assert not tree.status(UFO).exists()


@pytest.mark.parametrize("gated", [UNIT_A, UNIT_C], ids=["the-new-unit", "a-third-unit"])
def test_crosscheck_refuses_a_moved_function(tree, gated):
    """status.csv says func_A1 is matched in UNIT_B; functions.csv and the C now put it in
    UNIT_A."""
    before = seed(tree, UFO, [matched(A1, UNIT_B)])
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(UFO, UNIT_C, [C1])
    result = run_gate(tree, f"ufo2p/{gated}")
    assert result.exit_code == 1
    assert any(fname(A1) in p and UNIT_B in p and UNIT_A in p for p in result.problems)
    assert tree.status(UFO).read_bytes() == before


def test_crosscheck_adjacency():
    """A landed set one start away from the expected set, either way, is refused."""
    rows = {UFO: {A1: matched(A1, UNIT_A), A2: matched(A2, UNIT_A)}}
    owners = {UFO: owner_rows(UFO)}
    assert gate.cross_check([splice(UFO, {A1, A2})], rows, {}, owners=owners) == []
    assert gate.cross_check([splice(UFO, {A1})], rows, {}, owners=owners)
    assert gate.cross_check([splice(UFO, {A1, A2, B1})], rows, {}, owners=owners)
    assert gate.cross_check([splice(UFO, {A1, A2, B1})], rows, {UFO: {B1: UNIT_B}},
                            owners=owners) == []  # fmt: skip
    assert gate.cross_check([splice(UFO, {A1, A2})], rows, {UFO: {B1: UNIT_B}}, owners=owners)


def test_crosscheck_refuses_matched_rows_of_an_exe_that_did_not_land():
    rows = {TACP: {T1: matched(T1, UNIT_T)}}
    problems = gate.cross_check([splice(UFO, set())], rows, {})
    assert any(TACP in p and "nothing landed" in p for p in problems)


def test_crosscheck_reads_the_exeland_exe_field():
    rows = {TACP: {T1: matched(T1, UNIT_T)}}
    assert gate.cross_check([splice(UFO, set()), splice(TACP, {T1})], rows, {}) == []


def test_gate_two_targets_writes_both_rows(tree):
    """Ruling F1: with empty tables and a unit of each EXE compiled, one gate run of both writes
    both rows; one of them alone fails on the other's landed, unlisted function."""
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(TACP, UNIT_T, [T1])
    alone = run_gate(tree, f"ufo2p/{UNIT_A}")
    assert alone.exit_code == 1 and any(fname(T1) in p for p in alone.problems)
    assert not tree.status(UFO).exists() and not tree.status(TACP).exists()
    both = run_gate(tree, f"ufo2p/{UNIT_A}", f"tacp/{UNIT_T}")
    assert both.exit_code == 0
    assert [r.start for r in tree.rows(UFO)] == [A1]
    assert [r.start for r in tree.rows(TACP)] == [T1]
    assert [w.row.start for w in both.written] == [T1, A1]  # by table (tacp, ufo2p), then start


def test_gate_targets_are_all_or_nothing(tree):
    """F1: one failing target of several writes no row of any."""
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(TACP, UNIT_T, [T1])

    class OneFails(FakeCheck):
        def __call__(self, exe, unit, **kwargs):
            self.mismatch = unit == UNIT_T
            return super().__call__(exe, unit, **kwargs)

    result = run_gate(tree, f"ufo2p/{UNIT_A}", f"tacp/{UNIT_T}", check=OneFails(tree))
    assert result.exit_code == 1
    assert not tree.status(UFO).exists() and not tree.status(TACP).exists()


def test_gate_refuses_a_target_named_twice(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    with pytest.raises(CheckError, match="twice"):
        run_gate(tree, f"ufo2p/{UNIT_A}", f"UFO2P.EXE/{UNIT_A}")


def test_regating_keeps_attempts_and_date(tree):
    """Ruling F29: a re-gated unit's matched rows keep attempts and date; only source_sha256
    is rewritten. A function newly defined in it gets today's row."""
    seed(tree, UFO, [matched(A1, UNIT_A, attempts=3, day="2026-10-01")])
    text = tree.write_unit(UFO, UNIT_A, [A1, A2])
    result = run_gate(tree, f"ufo2p/{UNIT_A}", attempts=1)
    assert result.exit_code == 0
    sha = lf_sha256(text)
    kept = matched(A1, UNIT_A, attempts=3, day="2026-10-01", sha=sha)
    assert tree.rows(UFO) == [kept, matched(A2, UNIT_A, attempts=1, day="2026-10-25", sha=sha)]


def test_a_match_replaces_a_partial_row(tree):
    seed(tree, UFO, [StatusRow(A1, fname(A1), UNIT_A, "partial", 80.0, 2, "d" * 64, "2026-10-01")])
    text = tree.write_unit(UFO, UNIT_A, [A1])
    assert run_gate(tree, f"ufo2p/{UNIT_A}", attempts=3).exit_code == 0
    assert tree.rows(UFO) == [matched(A1, UNIT_A, attempts=3, day="2026-10-25",
                                      sha=lf_sha256(text))]  # fmt: skip


def test_merge_is_order_independent(tmp_path):
    def run(order):
        tree = make_tree(tmp_path / "-".join(order))
        for unit in order:
            tree.write_unit(UFO, unit, {UNIT_A: [A1], UNIT_B: [B1]}[unit])
            assert run_gate(tree, f"ufo2p/{unit}", attempts=1).exit_code == 0
        return tree.status(UFO).read_bytes()

    assert run([UNIT_A, UNIT_B]) == run([UNIT_B, UNIT_A])


# ---- gate --all --------------------------------------------------------------------------------


@dataclass
class FakeExe:
    """The part of check.ExeInputs gate --all reads."""

    target: object
    stem: str
    rows: tuple[FunctionRow, ...]

    def unit_rows(self, unit: str) -> list[FunctionRow]:
        rows = [row for row in self.rows if row.unit == unit]
        if not rows:
            raise CheckError(f"no unit {unit!r}")
        return rows


class FakeAll:
    """load_exe, check_source and land_all for gate --all, counting their calls."""

    def __init__(self, tree: Tree, *, percent: dict[int, float] | None = None,
                 landed: dict[str, set[int]] | None = None,
                 bad_sha: frozenset[str] = frozenset()) -> None:  # fmt: skip
        self.tree, self.percent, self.landed = tree, percent or {}, landed or {}
        self.bad_sha = bad_sha
        self.sources: list[tuple[str, str]] = []
        self.lands: list[dict] = []

    def load(self, target, **kwargs) -> FakeExe:
        return FakeExe(target, STEMS[target.name], tuple(owner_rows(target.name).values()))

    def source(self, exe, unit, src, rows, **kwargs) -> SourceCheck:
        assert Path(src) == self.tree.source(exe.target.name, unit)
        self.sources.append((exe.target.name, unit))
        functions = tuple(ok_function(s, self.percent.get(s, 100.0))
                          for s in self.tree.defined.get((exe.target.name, unit), []))  # fmt: skip
        return SourceCheck("wcc386", ("-4r",), functions, None, "")

    def land(self, manifest, **kwargs) -> list[ExeLand]:
        self.lands.append(kwargs)
        out = []
        for exe in (UFO, TACP):
            default = {s for (e, _), starts in self.tree.defined.items() if e == exe
                       for s in starts}  # fmt: skip
            out.append(splice(exe, self.landed.get(exe, default), ok=exe not in self.bad_sha))
        return out


def run_all(tree: Tree, fake: FakeAll) -> gate.GateResult:
    return gate.gate_all(roots=tree.roots, load_fn=fake.load, check_source_fn=fake.source,
                         land_fn=fake.land, compile_fn=lambda *a, **k: None,
                         objdiff_runner=lambda argv: "")  # fmt: skip


def seeded_tree(tree: Tree) -> dict[str, bytes]:
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(UFO, UNIT_B, [B1])
    tree.write_unit(TACP, UNIT_T, [T1])
    return {UFO: seed(tree, UFO, [matched(A1, UNIT_A), matched(B1, UNIT_B)]),
            TACP: seed(tree, TACP, [matched(T1, UNIT_T)])}  # fmt: skip


def test_gate_all_passes_and_writes_nothing(tree):
    before = seeded_tree(tree)
    result = run_all(tree, FakeAll(tree))
    assert result.exit_code == 0 and result.written == ()
    assert {exe: tree.status(exe).read_bytes() for exe in (UFO, TACP)} == before


def test_gate_all_runs_one_land(tree, monkeypatch):
    seeded_tree(tree)

    def no_check_unit(*args, **kwargs):
        raise AssertionError("gate --all must not call check_unit")

    monkeypatch.setattr(gate, "check_unit", no_check_unit)
    fake = FakeAll(tree)
    assert run_all(tree, fake).exit_code == 0
    assert sorted(fake.sources) == sorted([(UFO, UNIT_A), (UFO, UNIT_B), (TACP, UNIT_T)])
    assert len(fake.lands) == 1
    assert set(fake.lands[0]["fresh"]) == set(fake.sources)


def test_gate_all_with_empty_status(tree):
    write_status(tree.status(UFO), [])  # header only: a valid, empty table
    fake = FakeAll(tree)
    result = run_all(tree, fake)
    assert result.exit_code == 0
    assert fake.sources == [] and len(fake.lands) == 1 and set(fake.lands[0]["fresh"]) == set()


@pytest.mark.parametrize(
    ("fake", "needle"),
    [({"percent": {B1: 99.5}}, fname(B1)),
     ({"landed": {UFO: {A1}}}, fname(B1)),
     ({"landed": {TACP: {T1, 0x20010}}}, "0x00020010"),
     ({"bad_sha": frozenset({TACP})}, TACP)],
    ids=["objdiff-regression", "reverted", "extra-landed", "sha1"],
)  # fmt: skip
def test_gate_all_refuses_a_regression(tree, fake, needle):
    before = seeded_tree(tree)
    result = run_all(tree, FakeAll(tree, **fake))
    assert result.exit_code == 1
    assert any(needle in p for p in result.problems), result.problems
    assert {exe: tree.status(exe).read_bytes() for exe in (UFO, TACP)} == before


def test_gate_all_refuses_a_matched_unit_without_c(tree):
    seeded_tree(tree)
    tree.remove_unit(UFO, UNIT_B)
    result = run_all(tree, FakeAll(tree))
    assert result.exit_code == 1
    assert any(UNIT_B in p for p in result.problems)


def test_gate_cli_all(tree, monkeypatch, capsys):
    seeded_tree(tree)
    fake = FakeAll(tree)
    monkeypatch.setattr(gate, "load_exe", fake.load)
    monkeypatch.setattr(gate, "check_source", fake.source)
    monkeypatch.setattr(gate, "land_all", fake.land)
    monkeypatch.setattr(gate, "compile_source", lambda *a, **k: None)
    monkeypatch.setattr(gate, "default_objdiff_runner", lambda target: lambda argv: "")
    assert cli_main(["gate", "--all", *tree.argv(), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["mode"] == "all" and doc["ok"] is True and doc["written"] == []


@pytest.mark.parametrize("argv", [["gate"], ["gate", "--all", f"ufo2p/{UNIT_A}"],
                                  ["gate", "--all", "--attempts", "2"]])  # fmt: skip
def test_gate_cli_target_usage(tree, capsys, argv):
    assert cli_main([*argv, *tree.argv()]) == 2
    assert "reverseapoc gate: error:" in capsys.readouterr().err
