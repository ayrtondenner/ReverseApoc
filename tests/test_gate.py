"""gate (D-21, D-24, AGT-06): the only writer of config/<exe>/status.csv. check itself is faked
here (its own tests are tests/test_check.py): a fake check models a tree of unit files, each
defining some functions, and lands every defined function of every unit file present, as
check's land step does. Every name, address and hash is made up."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from conftest import REPO_ROOT, write_manifest
from reverseapoc import check, gate
from reverseapoc.check import (
    CheckError,
    CheckResult,
    ExeLand,
    FunctionCheck,
    SourceCheck,
    Unaccounted,
    UnitPaths,
    object_root,
)
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import (
    FunctionRow,
    SymbolRow,
    UnitRow,
    read_functions_csv,
    write_functions_csv,
    write_symbols_csv,
    write_units_csv,
)
from reverseapoc.land import LandResult
from reverseapoc.relocs import RelocResult
from reverseapoc.status import MATCHED, StatusRow, lf_sha256, read_status, status_path, write_status
from test_progress import load_progress

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

    def write_unit(self, exe: str, unit: str, starts: list[int], *, crlf: bool = False,
                   names: dict[int, str] | None = None) -> str:  # fmt: skip
        """Write the unit file defining `starts` in C (the other rows of the unit stay
        INCLUDE_ASM) and return its LF text. `names` gives a start its C name after a
        symbols.csv rename (the C defines the new name, as check requires)."""
        rows = [start for start, u in ROWS[exe] if u == unit]
        names = names or {}
        lines = ['#include "common.h"']
        for start in rows:
            c_name = names.get(start, fname(start))
            lines.append(f"int {c_name}(void) {{ return {start}; }}" if start in starts
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


def as_committed(tree: Tree, monkeypatch) -> Tree:
    """The tmp tree stands in for the committed src/ and config/: gate without --partial
    compiles only the committed src tree (fix round 1, M4), and object_root keys on both."""
    monkeypatch.setattr(check, "DEFAULT_SRC", tree.src)
    monkeypatch.setattr(check, "DEFAULT_CONFIG", tree.config)
    # ... and for the repository the compile root is taken from (07-03 fix round 1); configure.py
    # is loaded first, from the real checkout.
    check._configure()
    monkeypatch.setattr(check, "REPO_ROOT", tree.root)
    return tree


@pytest.fixture
def tree(tmp_path, monkeypatch) -> Tree:
    return as_committed(make_tree(tmp_path), monkeypatch)


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
    `error` raises it as a tool error. Like check_unit, it raises when the gated unit's C
    defines no function of the unit."""

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
        if not self.tree.defined.get((name, unit)):
            raise CheckError(f"{self.tree.source(name, unit)} defines no function of unit {unit}")
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


def test_merge_is_order_independent(tmp_path, monkeypatch):
    def run(order):
        tree = as_committed(make_tree(tmp_path / "-".join(order)), monkeypatch)
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
        starts = self.tree.defined.get((exe.target.name, unit), [])
        if not starts:  # as the real check_source does
            raise CheckError(f"{src} defines no function of unit {unit}")
        functions = tuple(ok_function(s, self.percent.get(s, 100.0)) for s in starts)
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
    a = lf_sha256(tree.write_unit(UFO, UNIT_A, [A1]))
    b = lf_sha256(tree.write_unit(UFO, UNIT_B, [B1]))
    t = lf_sha256(tree.write_unit(TACP, UNIT_T, [T1]))
    return {UFO: seed(tree, UFO, [matched(A1, UNIT_A, sha=a), matched(B1, UNIT_B, sha=b)]),
            TACP: seed(tree, TACP, [matched(T1, UNIT_T, sha=t)])}  # fmt: skip


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


# ---- Task 3: gate --partial (D-21, D-23, ruling F7) --------------------------------------------


class FakePartial(FakeAll):
    """check_source for a saved attempt: scores `percent[start]` for each function the saved
    file defines, and writes its object where the real check_source would (object_root of the
    options gate passes), so a test sees which build tree it went to."""

    def __init__(self, tree: Tree, percent: dict[int, float],
                 problems: tuple[Unaccounted, ...] = ()) -> None:  # fmt: skip
        super().__init__(tree, percent=percent)
        self.problems = problems
        self.options: list = []
        self.objects: list[Path] = []
        self.rule_paths: list[str | None] = []

    def source(self, exe, unit, src, rows, *, build_dir, options, **kwargs) -> SourceCheck:
        self.sources.append((exe.target.name, unit))
        self.options.append(options)
        self.rule_paths.append(kwargs.get("rule_path"))
        obj = UnitPaths.of(object_root(build_dir, options), exe.stem, unit).obj
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_bytes(b"custom object")
        self.objects.append(obj)
        unit_starts = {row.start for row in rows}
        functions = tuple(ok_function(s, p) for s, p in sorted(self.percent.items())
                          if s in unit_starts)  # fmt: skip
        return SourceCheck("wcc386", ("-4r",), functions, None, "", self.problems)


@pytest.fixture
def committed(tree) -> Tree:
    """The tree fixture already stands in for the committed src/ and config/, so only the
    saved file's own root can send a compile to check-custom (DI-06 part b)."""
    return tree


def saved_copy(tree: Tree, unit: str, text: str = "int saved(void) { return 1; }\n") -> Path:
    path = tree.root / "build" / "driver" / "run1" / "ufo2p" / fname(B1) / "attempt-1" / "best"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{unit}.c").write_bytes(text.encode("utf-8"))
    return path / f"{unit}.c"


def run_partial(tree: Tree, unit: str, saved: Path, fake: FakePartial, *, attempts: int = 1):
    return gate.gate_partial("ufo2p", unit, saved, roots=tree.roots, attempts=attempts,
                             today=TODAY, load_fn=fake.load, check_source_fn=fake.source,
                             compile_fn=lambda *a, **k: None,
                             objdiff_runner=lambda argv: "")  # fmt: skip


def test_partial_writes_best_percent(committed):
    tree = committed
    ninja_obj = tree.root / "build" / "ufo2p" / "obj" / f"{UNIT_B}.obj"
    ninja_obj.parent.mkdir(parents=True)
    ninja_obj.write_bytes(b"ninja object")
    saved = saved_copy(tree, UNIT_B)
    fake = FakePartial(tree, {B1: 73.5})
    result = run_partial(tree, UNIT_B, saved, fake, attempts=2)
    assert result.exit_code == 0 and result.mode == "partial"
    sha = hashlib.sha256(saved.read_bytes()).hexdigest()
    assert tree.rows(UFO) == [StatusRow(B1, fname(B1), UNIT_B, "partial", 73.5, 2, sha,
                                        "2026-10-25")]  # fmt: skip
    assert "73.50" in tree.status(UFO).read_text(encoding="utf-8")
    (options,) = fake.options
    assert Path(options.src_root) == saved.parent
    (obj,) = fake.objects
    assert obj.is_relative_to(tree.root / "build" / "check-custom")
    assert ninja_obj.read_bytes() == b"ninja object"


def test_partial_never_downgrades_a_matched_row(committed):
    tree = committed
    before = seed(tree, UFO, [matched(A1, UNIT_A, attempts=3)])
    saved = saved_copy(tree, UNIT_A)
    result = run_partial(tree, UNIT_A, saved, FakePartial(tree, {A1: 60.0, A2: 50.0}))
    assert result.exit_code == 0
    rows = tree.rows(UFO)
    assert rows[0] == matched(A1, UNIT_A, attempts=3)
    expected = [(A1, MATCHED, 100.0), (A2, "partial", 50.0)]
    assert [(r.start, r.status, r.best_percent) for r in rows] == expected
    assert tree.status(UFO).read_bytes() != before


def test_partial_keeps_the_higher_percent(committed):
    tree = committed
    old = StatusRow(B1, fname(B1), UNIT_B, "partial", 80.0, 1, "d" * 64, "2026-10-01")
    seed(tree, UFO, [old])
    result = run_partial(tree, UNIT_B, saved_copy(tree, UNIT_B), FakePartial(tree, {B1: 60.0}),
                         attempts=2)  # fmt: skip
    assert result.exit_code == 0
    assert tree.rows(UFO) == [dataclasses.replace(old, attempts=2, date="2026-10-25")]


def test_a_kept_better_partial_row_is_skipped_by_the_picker_today(committed):
    """Review WR-03 (D-09): a function attempted today is not picked again today, even when an
    older partial row scored better and keeps its percent and sha."""
    from reverseapoc import driver

    tree = committed
    seed(tree, UFO, [StatusRow(B1, fname(B1), UNIT_B, "partial", 80.0, 1, "d" * 64,
                               "2026-10-01")])  # fmt: skip
    assert ("ufo2p", B1) not in driver.excluded_keys(tree.config, "2026-10-25")
    assert run_partial(tree, UNIT_B, saved_copy(tree, UNIT_B), FakePartial(tree, {B1: 70.0}),
                       attempts=2).ok  # fmt: skip
    assert ("ufo2p", B1) in driver.excluded_keys(tree.config, "2026-10-25")
    assert ("ufo2p", B1) not in driver.excluded_keys(tree.config, "2026-10-26")


def test_partial_takes_a_higher_percent(committed):
    tree = committed
    seed(tree, UFO, [StatusRow(B1, fname(B1), UNIT_B, "partial", 60.0, 1, "d" * 64,
                               "2026-10-01")])  # fmt: skip
    saved = saved_copy(tree, UNIT_B)
    assert run_partial(tree, UNIT_B, saved, FakePartial(tree, {B1: 80.25}), attempts=2).ok
    (row,) = tree.rows(UFO)
    assert (row.best_percent, row.attempts, row.date) == (80.25, 2, "2026-10-25")
    assert row.source_sha256 == hashlib.sha256(saved.read_bytes()).hexdigest()


def test_partial_with_no_progress_writes_nothing(committed):
    tree = committed
    before = seed(tree, UFO, [matched(A1, UNIT_A)])
    fake = FakePartial(tree, {A1: 100.0, A2: 0.0})  # the matched one is never a partial row
    result = run_partial(tree, UNIT_A, saved_copy(tree, UNIT_A), fake)
    assert result.exit_code == 1 and result.written == ()
    assert tree.status(UFO).read_bytes() == before


def test_partial_cli(committed, monkeypatch, capsys):
    tree = committed
    saved = saved_copy(tree, UNIT_B)
    fake = FakePartial(tree, {B1: 42.0})
    monkeypatch.setattr(gate, "load_exe", fake.load)
    monkeypatch.setattr(gate, "check_source", fake.source)
    monkeypatch.setattr(gate, "default_objdiff_runner", lambda target: lambda argv: "")
    argv = ["gate", f"ufo2p/{UNIT_B}", "--partial", *tree.argv(), "--src", str(saved),
            "--attempts", "2", "--json"]  # fmt: skip
    assert cli_main(argv) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["mode"] == "partial" and [w["best_percent"] for w in doc["written"]] == ["42.00"]


@pytest.mark.parametrize(
    "case", ["no-src", "directory", "not-c", "missing", "two-targets", "with-all"]
)
def test_partial_cli_usage(committed, capsys, case):
    tree = committed
    saved = saved_copy(tree, UNIT_B)
    (saved.parent / "notes.md").write_text("x", encoding="utf-8")
    src = {"no-src": None, "directory": saved.parent, "not-c": saved.parent / "notes.md",
           "missing": saved.parent / "gone.c"}.get(case, saved)  # fmt: skip
    targets = {"two-targets": [f"ufo2p/{UNIT_B}", f"ufo2p/{UNIT_A}"], "with-all": ["--all"]}
    argv = ["gate", *targets.get(case, [f"ufo2p/{UNIT_B}"]), "--partial", *tree.argv()]
    if src is not None:
        argv += ["--src", str(src)]
    else:  # --src left at its default, the committed src root
        argv = [a for a in argv if a not in ("--src", str(tree.src))]
    assert cli_main(argv) == 2
    assert "reverseapoc gate: error:" in capsys.readouterr().err
    assert not tree.status(UFO).exists()


# ---- fix round 1 -------------------------------------------------------------------------------


def test_gate_all_exits_1_on_a_fully_reverted_unit(tree):
    """Important 1: a matched unit whose only C function is back to INCLUDE_ASM is a regression
    (exit 1), not a tool error; it is not compiled, so the land lands nothing of it."""
    before = seeded_tree(tree)
    tree.write_unit(UFO, UNIT_B, [])
    fake = FakeAll(tree)
    result = run_all(tree, fake)
    assert result.exit_code == 1
    assert any(fname(B1) in p and "INCLUDE_ASM" in p for p in result.problems), result.problems
    assert (UFO, UNIT_B) not in fake.sources
    assert (UFO, UNIT_B) not in set(fake.lands[0]["fresh"])
    assert {exe: tree.status(exe).read_bytes() for exe in (UFO, TACP)} == before


def test_gating_a_fully_reverted_matched_unit_exits_1(tree):
    before = seed(tree, UFO, [matched(A1, UNIT_A)])
    tree.write_unit(UFO, UNIT_A, [])
    fake = FakeCheck(tree)
    result = run_gate(tree, f"ufo2p/{UNIT_A}", check=fake)
    assert result.exit_code == 1
    assert any(fname(A1) in p and "INCLUDE_ASM" in p for p in result.problems), result.problems
    assert fake.calls == []
    assert tree.status(UFO).read_bytes() == before


def rename(tree: Tree, start: int, name: str) -> None:
    write_symbols_csv(tree.config / "ufo2p" / "symbols.csv", [SymbolRow(start, name, "func")], UFO)


LINKED = "UnitInit_"  # the symbols.csv name, verbatim: the linker name the object exports
C_NAME = "UnitInit"  # what the C defines for it (Watcom appends the `_`)


def test_regating_a_renamed_function_updates_its_name(tree):
    """Orchestrator ruling (minor 3): a matched row is keyed by (EXE, start); a passing re-gate
    takes the name symbols.csv gives the start, keeping attempts and date (F29). The C defines
    the new name, as the real check requires (fix round 2)."""
    seed(tree, UFO, [matched(A1, UNIT_A, attempts=3, day="2026-10-01")])
    rename(tree, A1, LINKED)
    text = tree.write_unit(UFO, UNIT_A, [A1], names={A1: C_NAME})
    assert f"int {C_NAME}(void)" in text and f"int {fname(A1)}(" not in text
    result = run_gate(tree, f"ufo2p/{UNIT_A}", attempts=1)
    assert result.exit_code == 0, result.problems
    assert tree.rows(UFO) == [dataclasses.replace(
        matched(A1, UNIT_A, attempts=3, day="2026-10-01", sha=lf_sha256(text)), name=LINKED)]


def test_gate_all_passes_with_a_renamed_match(tree):
    """gate --all proves a matched start renamed in symbols.csv whose C defines the new name."""
    text = tree.write_unit(UFO, UNIT_A, [A1], names={A1: C_NAME})
    rename(tree, A1, LINKED)
    before = seed(tree, UFO, [dataclasses.replace(matched(A1, UNIT_A, sha=lf_sha256(text)),
                                                  name=LINKED)])  # fmt: skip
    fake = FakeAll(tree)
    result = run_all(tree, fake)
    assert result.exit_code == 0, result.problems
    assert fake.sources == [(UFO, UNIT_A)]
    assert tree.status(UFO).read_bytes() == before


def test_an_unwritable_name_is_refused_before_check(tree):
    """Minor (ruling): the name column is the symbols.csv name verbatim; one status.csv cannot
    hold is a tool error up front, naming the row, never after a passing check."""
    tree.write_unit(UFO, UNIT_A, [A1], names={A1: "UnitInit"})
    rename(tree, A1, "Unit$Init_")
    fake = FakeCheck(tree)
    with pytest.raises(CheckError, match=r"Unit\$Init_.*0x00010000|0x00010000.*Unit\$Init_"):
        run_gate(tree, f"ufo2p/{UNIT_A}", check=fake)
    assert fake.calls == []
    assert not tree.status(UFO).exists()


def test_partial_refuses_an_unwritable_name_before_check(committed):
    tree = committed
    rename(tree, B1, "Unit$Init_")
    fake = FakePartial(tree, {B1: 50.0})
    with pytest.raises(CheckError, match="0x00010020"):
        run_partial(tree, UNIT_B, saved_copy(tree, UNIT_B), fake)
    assert fake.sources == []
    assert not tree.status(UFO).exists()


def test_a_unit_with_neither_markers_nor_definitions_goes_to_check(tree):
    """Only a unit whose every game/thunk row is marked INCLUDE_ASM is called reverted without
    check; one with neither markers nor the expected definitions goes to check, which refuses
    it as it does today (a tool error)."""
    seed(tree, UFO, [matched(A1, UNIT_A)])
    path = tree.source(UFO, UNIT_A)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'#include "common.h"\n')
    tree.defined[(UFO, UNIT_A)] = []
    fake = FakeCheck(tree)
    with pytest.raises(CheckError, match="defines no function"):
        run_gate(tree, f"ufo2p/{UNIT_A}", check=fake)
    assert len(fake.calls) == 1


def test_a_stale_name_is_refused(tree):
    """The cross-check compares by start; a matched row not re-gated must still carry the name
    functions.csv/symbols.csv give its start."""
    before = seed(tree, UFO, [matched(A1, UNIT_A)])
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(UFO, UNIT_B, [B1])
    rename(tree, A1, "UnitInit")
    result = run_gate(tree, f"ufo2p/{UNIT_B}")
    assert result.exit_code == 1
    assert any("UnitInit" in p and fname(A1) in p for p in result.problems), result.problems
    assert tree.status(UFO).read_bytes() == before


def test_a_failed_second_write_names_the_written_table(tree, monkeypatch):
    """M2: an OS error on the second table names the one already written."""
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(TACP, UNIT_T, [T1])
    real = gate.write_status

    def failing(path, rows):
        if "ufo2p" in Path(path).parts:
            raise OSError("disk full")
        real(path, rows)

    monkeypatch.setattr(gate, "write_status", failing)
    with pytest.raises(CheckError) as caught:
        run_gate(tree, f"ufo2p/{UNIT_A}", f"tacp/{UNIT_T}")
    message = str(caught.value)
    assert str(tree.status(TACP)) in message and str(tree.status(UFO)) in message
    assert "disk full" in message
    assert tree.status(TACP).exists() and not tree.status(UFO).exists()


def test_gate_cli_names_the_written_table_on_a_half_write(tree, monkeypatch, capsys):
    """Review IN-03 (what _cmd_gate's docstring promises): a write that fails after another
    EXE's table was written exits 2, and the CLI's error names the table already written."""
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(TACP, UNIT_T, [T1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    real = gate.write_status

    def failing(path, rows):
        if "ufo2p" in Path(path).parts:
            raise OSError("disk full")
        real(path, rows)

    monkeypatch.setattr(gate, "write_status", failing)
    assert cli_main(["gate", f"ufo2p/{UNIT_A}", f"tacp/{UNIT_T}", *tree.argv()]) == 2
    err = capsys.readouterr().err
    assert err.startswith("reverseapoc gate: error: ")
    assert f"wrote {tree.status(TACP)} but not {tree.status(UFO)}" in err
    assert "restore config/ before committing" in err
    assert tree.status(TACP).exists() and not tree.status(UFO).exists()


def test_gate_refuses_a_non_default_src(tree, tmp_path):
    """M4: gate writes the public status.csv, so it compiles only the committed src tree."""
    other = tmp_path / "elsewhere"
    tree.write_unit(UFO, UNIT_A, [A1])
    roots = dataclasses.replace(tree.roots, src_root=other)
    with pytest.raises(CheckError, match="--src"):
        gate.gate_units([("ufo2p", UNIT_A)], roots=roots, today=TODAY, check_fn=FakeCheck(tree))
    with pytest.raises(CheckError, match="--src"):
        gate.gate_all(roots=roots)
    assert not tree.status(UFO).exists()


@pytest.mark.parametrize("extra", [[f"ufo2p/{UNIT_A}"], ["--all"]], ids=["unit", "all"])
def test_gate_cli_refuses_src_without_partial(tree, tmp_path, monkeypatch, capsys, extra):
    tree.write_unit(UFO, UNIT_A, [A1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    argv = ["gate", *extra, *tree.argv()]
    argv[argv.index("--src") + 1] = str(tmp_path / "elsewhere")
    assert cli_main(argv) == 2
    assert "--src" in capsys.readouterr().err
    assert not tree.status(UFO).exists()


def test_partial_with_source_problems_writes_nothing(committed):
    """M5: a saved file with D-12 account problems scores no partial row."""
    tree = committed
    problem = Unaccounted("func_00099999", None, "is not a function of the unit")
    fake = FakePartial(tree, {B1: 70.0}, problems=(problem,))
    result = run_partial(tree, UNIT_B, saved_copy(tree, UNIT_B), fake)
    assert result.exit_code == 1
    assert any("func_00099999" in p for p in result.problems)
    assert not tree.status(UFO).exists()


def test_a_unit_file_changed_before_the_write_is_refused(tree):
    """M7: each unit file is hashed again just before the write."""
    tree.write_unit(UFO, UNIT_A, [A1])
    tree.write_unit(TACP, UNIT_T, [T1])

    class EditsA(FakeCheck):
        def __call__(self, exe, unit, **kwargs):
            if unit == UNIT_T:
                path = self.tree.source(UFO, UNIT_A)
                path.write_bytes(path.read_bytes() + b"/* edited */\n")
            return super().__call__(exe, unit, **kwargs)

    with pytest.raises(CheckError, match="changed"):
        run_gate(tree, f"ufo2p/{UNIT_A}", f"tacp/{UNIT_T}", check=EditsA(tree))
    assert not tree.status(UFO).exists() and not tree.status(TACP).exists()


def test_gate_all_refuses_a_stale_source_sha(tree):
    """M9: gate --all compares each matched row's source_sha256 with the unit file."""
    before = seeded_tree(tree)
    path = tree.source(UFO, UNIT_A)
    path.write_bytes(path.read_bytes() + b"/* a comment pass */\n")
    result = run_all(tree, FakeAll(tree))
    assert result.exit_code == 1
    assert any("source_sha256" in p and UNIT_A in p for p in result.problems), result.problems
    assert {exe: tree.status(exe).read_bytes() for exe in (UFO, TACP)} == before


def test_gate_all_output_shape(tree):
    """M10: --all never says it did not write; its checks are per unit, its splices apart."""
    seeded_tree(tree)
    failing = run_all(tree, FakeAll(tree, percent={B1: 99.5}))
    text = failing.format()
    assert text.rstrip().endswith("MISMATCH") and "not written" not in text
    assert run_all(tree, FakeAll(tree)).format().rstrip().endswith("ok")
    doc = failing.to_json()
    assert {tuple(sorted(c)) for c in doc["checks"]} == {("exe", "functions", "unit")}
    assert [s["exe"] for s in doc["splice"]] == [UFO, TACP]


# ---- fix round 3: a full revert in a unit that mixes row kinds ---------------------------------

MIXED_NAMES = {"data-in-code": "D_00010010", "runtime": "rt_helper_"}


def mix_unit_a(tree: Tree, kind: str) -> None:
    """UNIT_A becomes A1 (game) plus A2 of `kind`. A2 is exempt from the D-12 account, so the
    C neither marks nor defines it, as in about 50 real units per EXE."""
    rows = [FunctionRow(A1, A1 + 0x10, fname(A1), "game", UNIT_A, "call"),
            FunctionRow(A2, A2 + 0x10, MIXED_NAMES[kind], kind, UNIT_A, "call"),
            FunctionRow(B1, B1 + 0x10, fname(B1), "game", UNIT_B, "call"),
            FunctionRow(C1, C1 + 0x10, fname(C1), "game", UNIT_C, "call")]  # fmt: skip
    write_functions_csv(tree.config / "ufo2p" / "functions.csv", rows, UFO)


def write_marked_a1(tree: Tree) -> str:
    text = f'#include "common.h"\nINCLUDE_ASM({fname(A1)});\n'
    path = tree.source(UFO, UNIT_A)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    tree.defined[(UFO, UNIT_A)] = []
    return text


class FakeAllFromCsv(FakeAll):
    """FakeAll whose ExeInputs rows are the tree's functions.csv, kinds included."""

    def load(self, target, **kwargs) -> FakeExe:
        path = self.tree.config / STEMS[target.name] / "functions.csv"
        return FakeExe(target, STEMS[target.name], tuple(read_functions_csv(path)))


@pytest.mark.parametrize("kind", ["data-in-code", "runtime"])
def test_full_revert_in_a_mixed_unit_exits_1(tree, kind):
    """Only game and thunk rows must be marked for a unit to be reverted (the _reverted filter):
    the matched game row marked again is a mismatch, without check, in a mixed unit too."""
    mix_unit_a(tree, kind)
    before = seed(tree, UFO, [matched(A1, UNIT_A)])
    write_marked_a1(tree)
    fake = FakeCheck(tree)
    result = run_gate(tree, f"ufo2p/{UNIT_A}", check=fake)
    assert result.exit_code == 1
    assert any(fname(A1) in p and "reverted to INCLUDE_ASM" in p for p in result.problems)
    assert fake.calls == []
    assert tree.status(UFO).read_bytes() == before


@pytest.mark.parametrize("kind", ["data-in-code", "runtime"])
def test_full_revert_in_a_mixed_unit_gate_all_exits_1(tree, kind):
    mix_unit_a(tree, kind)
    text = write_marked_a1(tree)
    before = seed(tree, UFO, [matched(A1, UNIT_A, sha=lf_sha256(text))])
    fake = FakeAllFromCsv(tree)
    result = run_all(tree, fake)
    assert result.exit_code == 1
    assert any(fname(A1) in p and "reverted to INCLUDE_ASM" in p for p in result.problems)
    assert (UFO, UNIT_A) not in fake.sources
    assert (UFO, UNIT_A) not in set(fake.lands[0]["fresh"])
    assert tree.status(UFO).read_bytes() == before


# ---- 06-18: gate rewrites decomphub.progress.json (D-21, D-29, ruling F8) ----

FEED = "decomphub.progress.json"


def derived_feed(config: Path) -> bytes:
    """What progress.py derives from the CSVs under `config`, as the committed file holds it."""
    progress = load_progress()
    return progress.render(progress.build_decomphub(progress.derive(config)))


def test_gate_rewrites_the_decomphub_feed(tree):
    """After a passing gate the feed next to config/ (config_root.parent, ruling F8) is
    progress.py's derivation from the tables gate just wrote."""
    tree.write_unit(UFO, UNIT_A, [A1])
    feed = tree.root / FEED
    feed.write_bytes(b"stale\n")
    result = run_gate(tree, f"ufo2p/{UNIT_A}")
    assert result.ok
    assert feed.read_bytes() == derived_feed(tree.config)
    tracks = {t["id"]: t["measurement"] for t in json.loads(feed.read_bytes())["tracks"]}
    assert (tracks["ufo2p-functions"]["completed"], tracks["ufo2p-functions"]["total"]) == (1, 4)
    assert tracks["tacp-functions"]["completed"] == 0


@pytest.mark.parametrize("failure", ["mismatch", "error"])
def test_gate_failure_leaves_the_feed(tree, failure):
    tree.write_unit(UFO, UNIT_A, [A1])
    feed = tree.root / FEED
    feed.write_bytes(b"previous feed\n")
    if failure == "mismatch":
        result = run_gate(tree, f"ufo2p/{UNIT_A}", check=FakeCheck(tree, mismatch=True))
        assert result.exit_code == 1
    else:
        with pytest.raises(CheckError):
            run_gate(tree, f"ufo2p/{UNIT_A}", check=FakeCheck(tree, error=CheckError("objdiff")))
    assert feed.read_bytes() == b"previous feed\n"


def test_gate_with_a_tmp_config_root_leaves_the_repo_feed(tree):
    """Ruling F8: the feed goes next to the config root gate was given, so a gate over a tmp
    tree never touches the repository's decomphub.progress.json."""
    repo_feed = REPO_ROOT / FEED
    before = repo_feed.read_bytes() if repo_feed.exists() else None
    tree.write_unit(UFO, UNIT_A, [A1])
    assert run_gate(tree, f"ufo2p/{UNIT_A}").ok
    assert (tree.root / FEED).is_file()
    assert (repo_feed.read_bytes() if repo_feed.exists() else None) == before


def test_gate_names_the_tables_when_the_feed_write_fails(tree, monkeypatch):
    """The feed is written after status.csv: an OS error there names the written table, so
    config/ is restored before anything is committed (the M2 rule)."""
    tree.write_unit(UFO, UNIT_A, [A1])

    def failing(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(gate, "write_atomic", failing)
    with pytest.raises(CheckError) as caught:
        run_gate(tree, f"ufo2p/{UNIT_A}")
    message = str(caught.value)
    assert str(tree.status(UFO)) in message and FEED in message and "disk full" in message
    assert tree.status(UFO).exists() and not (tree.root / FEED).exists()


def test_gate_refuses_tables_progress_cannot_derive(tree):
    """Fix round 1, minor 1: progress.py derives the tables as they will be after the write,
    in memory, before any status.csv is written. A matched row at a start that is not a game or
    thunk row (here a runtime row a check defined) is a ProgressError: the gate exits 2 with
    nothing written, never a table without its feed."""
    mix_unit_a(tree, "runtime")
    tree.write_unit(UFO, UNIT_A, [A1, A2])
    with pytest.raises(CheckError, match="decomphub.progress.json") as caught:
        run_gate(tree, f"ufo2p/{UNIT_A}")
    assert "0x00010010" in str(caught.value)
    assert not tree.status(UFO).exists() and not (tree.root / FEED).exists()


def test_gate_output_names_the_rewritten_feed(tree, monkeypatch, capsys):
    """Fix round 1, minor 3: the text and --json output name the feed gate rewrote, so a
    by-hand gate (D-21) knows to commit it with status.csv."""
    tree.write_unit(UFO, UNIT_A, [A1])
    result = run_gate(tree, f"ufo2p/{UNIT_A}")
    feed = tree.root / FEED
    assert result.feed == feed
    assert result.to_json()["feed"] == str(feed)
    line = next(line for line in result.format().splitlines() if FEED in line)
    assert str(feed) in line and "commit" in line
    tree.write_unit(TACP, UNIT_T, [T1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    assert cli_main(["gate", f"tacp/{UNIT_T}", "--json", *tree.argv()]) == 0
    assert json.loads(capsys.readouterr().out)["feed"] == str(feed)


def test_gate_output_has_no_feed_when_nothing_was_written(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    result = run_gate(tree, f"ufo2p/{UNIT_A}", check=FakeCheck(tree, mismatch=True))
    assert result.feed is None and result.to_json()["feed"] is None
    assert FEED not in result.format()


def test_gate_without_progress_py_writes_no_table(tree, tmp_path, monkeypatch):
    """progress.py is loaded before any status.csv is written: a checkout without it refuses
    the gate with nothing written, never a table without its feed."""
    tree.write_unit(UFO, UNIT_A, [A1])
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path / "no-checkout")
    gate._progress.cache_clear()
    try:
        with pytest.raises(CheckError, match="progress.py not found"):
            run_gate(tree, f"ufo2p/{UNIT_A}")
    finally:
        gate._progress.cache_clear()
    assert not tree.status(UFO).exists() and not (tree.root / FEED).exists()


# ---- 07-03 (D-27 P2): rows are written only under the committed compile options ---------------

# The GateRoots field of each compile option and its CLI flag.
OPTION_FLAGS = {"cflags": "--cflags", "watcom_manifest": "--watcom-manifest",
                "watcom_dir": "--watcom-dir"}  # fmt: skip


def other_option(tmp_path: Path, field: str) -> Path:
    """An uncommitted value for `field`: a cflags table with other flags, another manifest file
    or another Watcom directory."""
    path = tmp_path / f"other-{field}"
    if field == "watcom_dir":
        path.mkdir()
    else:
        path.write_text("*  wcc386@10.6  -4r -s -fpi -ot\n", encoding="utf-8")
    return path


def published(tree: Tree) -> tuple[bytes, bytes]:
    """status.csv of UFO2P with one matched row (its unit file in place, so a passing check of
    another unit cross-checks clean), and the feed beside config/, as bytes."""
    seed(tree, UFO, [matched(B1, UNIT_B, sha=lf_sha256(tree.write_unit(UFO, UNIT_B, [B1])))])
    (tree.root / FEED).write_bytes(b"previous feed\n")
    return tree.status(UFO).read_bytes(), (tree.root / FEED).read_bytes()


def assert_unchanged(tree: Tree, before: tuple[bytes, bytes]) -> None:
    assert (tree.status(UFO).read_bytes(), (tree.root / FEED).read_bytes()) == before


@pytest.mark.parametrize("field", list(OPTION_FLAGS))
def test_gate_unit_refuses_other_compile_options(tree, tmp_path, field):
    """gate EXE/UNIT under an uncommitted --cflags, --watcom-manifest or --watcom-dir is refused
    before any check: a passing check would write matched rows under unapproved flags."""
    tree.write_unit(UFO, UNIT_A, [A1])
    before = published(tree)
    roots = dataclasses.replace(tree.roots, **{field: other_option(tmp_path, field)})
    fake = FakeCheck(tree)
    with pytest.raises(CheckError, match=OPTION_FLAGS[field]) as info:
        gate.gate_units([("ufo2p", UNIT_A)], roots=roots, today=TODAY, check_fn=fake)
    assert "gate --all" in str(info.value)
    assert fake.calls == []
    assert_unchanged(tree, before)


@pytest.mark.parametrize("field", list(OPTION_FLAGS))
def test_gate_cli_refuses_other_compile_options(tree, tmp_path, monkeypatch, capsys, field):
    """DEC-03 edge: `gate ufo2p/<unit> --cflags tmp.txt` on a passing check exits 2 and leaves
    status.csv and decomphub.progress.json byte-identical."""
    tree.write_unit(UFO, UNIT_A, [A1])
    before = published(tree)
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    argv = ["gate", f"ufo2p/{UNIT_A}", *tree.argv(), OPTION_FLAGS[field],
            str(other_option(tmp_path, field))]  # fmt: skip
    assert cli_main(argv) == 2
    assert OPTION_FLAGS[field] in capsys.readouterr().err
    assert_unchanged(tree, before)


def test_gate_cli_with_the_committed_options_spelled_out_still_writes(tree, monkeypatch):
    """The CLI passes every default explicitly; the committed paths given by hand are the
    committed options, so gate still writes."""
    tree.write_unit(UFO, UNIT_A, [A1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    argv = ["gate", f"ufo2p/{UNIT_A}", *tree.argv(), "--cflags", str(check.DEFAULT_CFLAGS)]
    assert cli_main(argv) == 0
    assert [row.start for row in tree.rows(UFO)] == [A1]


@pytest.mark.parametrize("field", list(OPTION_FLAGS))
def test_gate_partial_refuses_other_compile_options(committed, tmp_path, field):
    tree = committed
    fake = FakePartial(tree, {B1: 70.0})
    roots = dataclasses.replace(tree.roots, **{field: other_option(tmp_path, field)})
    with pytest.raises(CheckError, match=OPTION_FLAGS[field]):
        gate.gate_partial("ufo2p", UNIT_B, saved_copy(tree, UNIT_B), roots=roots, today=TODAY,
                          load_fn=fake.load, check_source_fn=fake.source,
                          compile_fn=lambda *a, **k: None,
                          objdiff_runner=lambda argv: "")  # fmt: skip
    assert fake.sources == []
    assert not tree.status(UFO).exists()


def test_gate_all_accepts_other_cflags(tree, tmp_path):
    """`gate --all --cflags FILE` stays the D-14 dry run: it checks under FILE and writes
    nothing."""
    before = seeded_tree(tree)
    cflags = other_option(tmp_path, "cflags")
    fake = FakeAll(tree)
    result = gate.gate_all(roots=dataclasses.replace(tree.roots, cflags=cflags),
                           load_fn=fake.load, check_source_fn=fake.source, land_fn=fake.land,
                           compile_fn=lambda *a, **k: None,
                           objdiff_runner=lambda argv: "")  # fmt: skip
    assert result.exit_code == 0 and result.written == ()
    assert fake.lands[0]["options"].cflags == cflags
    assert {exe: tree.status(exe).read_bytes() for exe in (UFO, TACP)} == before


def partial_refused(tree: Tree, saved: Path, needle: str) -> None:
    """gate --partial on `saved` raises a CheckError naming `needle`, before any check, and
    writes nothing."""
    fake = FakePartial(tree, {B1: 70.0})
    with pytest.raises(CheckError, match=needle):
        run_partial(tree, UNIT_B, saved, fake)
    assert fake.sources == []
    assert not tree.status(UFO).exists()


def test_partial_refuses_a_saved_file_outside_the_repository(committed, tmp_path):
    """Fix round 1: gate --partial writes the public status.csv, so it scores only a saved file
    inside the repository, compiled from REPO_ROOT with the committed headers."""
    tree = committed
    outside = tmp_path.parent / f"{tmp_path.name}-outside" / "best"
    outside.mkdir(parents=True)
    (outside.parent / "include").mkdir()
    saved = outside / f"{UNIT_B}.c"
    saved.write_text("int saved(void) { return 1; }\n", encoding="utf-8")
    partial_refused(tree, saved, "inside the repository")


def test_partial_refuses_a_saved_file_compiled_from_a_view_root(committed):
    """Fix round 1: a saved file whose compile root would be a view (it sits directly in a D-24
    view's src/) would compile against the view's headers; gate --partial refuses it."""
    tree = committed
    view = tree.root / "build" / "driver" / "run1" / "view"
    (view / "include").mkdir(parents=True)
    (view / "src").mkdir()
    saved = view / "src" / f"{UNIT_B}.c"
    saved.write_text("int saved(void) { return 1; }\n", encoding="utf-8")
    partial_refused(tree, saved, "compile root")


def test_gate_partial_uses_the_unit_rule(committed):
    """D-27 P1 on a saved attempt: best/<unit>.c is scored under src/<exe>/<unit>.c's rule."""
    tree = committed
    fake = FakePartial(tree, {B1: 70.0})
    assert run_partial(tree, UNIT_B, saved_copy(tree, UNIT_B), fake).ok
    assert fake.rule_paths == [f"src/ufo2p/{UNIT_B}.c"]


# ---- 07-16 (D-29): _reverted by start through the shared finder --------------------------------

FOO = "Foo_"  # symbols.csv renames A2 (func_00010010) Foo_; the C writes Foo


def renamed_unit_a(tree: Tree, a2_line: str) -> str:
    """UNIT_A with A1 marked INCLUDE_ASM and `a2_line` for the renamed A2; A2 matched as Foo_."""
    rename(tree, A2, FOO)
    text = f'#include "common.h"\nINCLUDE_ASM({fname(A1)});\n{a2_line}\n'
    path = tree.source(UFO, UNIT_A)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    tree.defined[(UFO, UNIT_A)] = [] if "INCLUDE_ASM" in a2_line else [A2]
    return text


def matched_foo(text: str) -> StatusRow:
    return dataclasses.replace(matched(A2, UNIT_A, sha=lf_sha256(text)), name=FOO)


def assert_reverted_foo(result: gate.GateResult) -> None:
    assert result.exit_code == 1
    assert any(FOO in p and f"0x{A2:08X}" in p and "reverted to INCLUDE_ASM" in p
               for p in result.problems), result.problems  # fmt: skip


@pytest.mark.parametrize("marker", ["Foo", fname(A2)], ids=["new-name", "old-placeholder"])
def test_reverted_after_rename(tree, marker):
    """A matched row renamed in symbols.csv and marked INCLUDE_ASM again, under its new C name
    or its old placeholder, is a reverted match: gate of its unit exits 1 without check."""
    text = renamed_unit_a(tree, f"INCLUDE_ASM({marker});")
    before = seed(tree, UFO, [matched_foo(text)])
    fake = FakeCheck(tree)
    assert_reverted_foo(run_gate(tree, f"ufo2p/{UNIT_A}", check=fake))
    assert fake.calls == []
    assert tree.status(UFO).read_bytes() == before


def test_reverted_with_old_placeholder_marker(tree):
    """gate --all: the old placeholder marker of the renamed row counts as reverted too, and the
    unit is not compiled."""
    text = renamed_unit_a(tree, f"INCLUDE_ASM({fname(A2)});")
    before = seed(tree, UFO, [matched_foo(text)])
    fake = FakeAll(tree)
    assert_reverted_foo(run_all(tree, fake))
    assert (UFO, UNIT_A) not in fake.sources
    assert tree.status(UFO).read_bytes() == before


def test_reverted_after_rename_gate_all(tree):
    text = renamed_unit_a(tree, "INCLUDE_ASM(Foo);")
    before = seed(tree, UFO, [matched_foo(text)])
    fake = FakeAll(tree)
    assert_reverted_foo(run_all(tree, fake))
    assert (UFO, UNIT_A) not in fake.sources
    assert tree.status(UFO).read_bytes() == before


def test_not_reverted_when_defined(tree):
    """The unit defines Foo: no reverted problem; gate --all re-proves it."""
    text = renamed_unit_a(tree, "int Foo(void) { return 1; }")
    before = seed(tree, UFO, [matched_foo(text)])
    fake = FakeAll(tree)
    result = run_all(tree, fake)
    assert result.exit_code == 0, result.problems
    assert fake.sources == [(UFO, UNIT_A)]
    assert tree.status(UFO).read_bytes() == before


def test_gate_writes_renamed_name(tree):
    """A passing (fake) check of the unit defining Foo writes A2's status.csv row under the
    symbols.csv linker name Foo_ (gate's _owners reads symbols.csv)."""
    text = renamed_unit_a(tree, "int Foo(void) { return 1; }")
    result = run_gate(tree, f"ufo2p/{UNIT_A}", attempts=2)
    assert result.exit_code == 0, result.problems
    (row,) = tree.rows(UFO)
    assert (row.start, row.name, row.status) == (A2, FOO, MATCHED)
    assert row.source_sha256 == lf_sha256(text)


def test_reverted_refuses_a_symbols_csv_name_without_its_underscore(tree):
    """The C names come from symbols.csv through unitdefs.c_names: a func name without Watcom's
    `_` is a tool error naming symbols.csv, never a silent 'not reverted'."""
    text = renamed_unit_a(tree, "INCLUDE_ASM(Foo);")
    rename(tree, A2, "Foo")
    seed(tree, UFO, [dataclasses.replace(matched_foo(text), name="Foo")])
    fake = FakeCheck(tree)
    with pytest.raises(CheckError, match=r"symbols\.csv.*Foo"):
        run_gate(tree, f"ufo2p/{UNIT_A}", check=fake)
    assert fake.calls == []
